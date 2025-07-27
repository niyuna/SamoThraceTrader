"""
增强版BarGenerator
支持开盘成交量和强制收线功能
"""

import threading
from datetime import datetime, timedelta
from typing import Callable, Optional
from vnpy.trader.object import TickData, BarData
from vnpy.trader.constant import Interval
from vnpy.trader.utility import ZoneInfo
from vnpy.event import EVENT_TIMER


class EnhancedBarGenerator:
    """
    Enhanced BarGenerator with opening volume and auto-flush support.
    
    Features:
    1. Opening volume calculation - handles first tick of the day
    2. Auto-flush mechanism - forces bar completion for illiquid stocks
    """

    def __init__(
        self,
        on_bar: Callable,
        window: int = 0,
        on_window_bar: Callable | None = None,
        interval: Interval = Interval.MINUTE,
        daily_end: Optional[datetime] = None,
        enable_opening_volume: bool = True,    # 是否启用开盘成交量
        enable_auto_flush: bool = False,       # 是否启用强制收线（默认关闭）
        main_engine=None                       # 传入main_engine以使用timer
    ) -> None:
        """Constructor"""
        self.bar: BarData | None = None
        self.on_bar: Callable = on_bar

        self.interval: Interval = interval
        self.interval_count: int = 0

        self.hour_bar: BarData | None = None
        self.daily_bar: BarData | None = None

        self.window: int = window
        self.window_bar: BarData | None = None
        self.on_window_bar: Callable | None = on_window_bar

        self.last_tick: TickData | None = None

        self.daily_end: Optional[datetime] = daily_end
        if self.interval == Interval.DAILY and not self.daily_end:
            raise RuntimeError("合成日K线必须传入每日收盘时间")

        # 增强功能配置
        self.enable_opening_volume = enable_opening_volume
        self.enable_auto_flush = enable_auto_flush
        self.main_engine = main_engine
        
        # 新增属性
        self.is_first_tick_of_day = True

        # 注册timer事件处理
        if self.enable_auto_flush and self.main_engine:
            self.main_engine.event_engine.register(EVENT_TIMER, self._on_timer)

    def _on_timer(self, event):
        """处理timer事件"""
        if self.bar and self.should_flush_bar():
            self.force_complete_bar()

    def should_flush_bar(self):
        """判断是否应该强制完成bar"""
        if not self.bar:
            return False
        
        # 使用expected completion time
        current_time = datetime.now()
        expected_completion_time = self.bar.datetime.replace(second=0, microsecond=0)
        time_diff = current_time - expected_completion_time
        
        return time_diff.total_seconds() >= 61

    def force_complete_bar(self):
        """强制完成当前bar"""
        if not self.bar:
            return
        
        # 直接使用bar的原始时间，对齐到分钟
        self.bar.datetime = self.bar.datetime.replace(second=0, microsecond=0)
        self.on_bar(self.bar)
        self.bar = None
        
        self.write_log(f"Force completed bar at {self.bar.datetime} for {self.bar.symbol}")

    def update_tick(self, tick: TickData) -> None:
        """
        Update new tick data into generator.
        """
        new_minute: bool = False

        # Filter tick data with 0 last price
        if not tick.last_price:
            return

        # 检查是否需要强制完成bar
        if self.enable_auto_flush and self.bar and self.should_flush_bar():
            self.force_complete_bar()

        # 检测是否是新的一天
        if self.enable_opening_volume and self.is_new_day(tick.datetime):
            self.is_first_tick_of_day = True

        if not self.bar:
            new_minute = True
        elif (
            (self.bar.datetime.minute != tick.datetime.minute)
            or (self.bar.datetime.hour != tick.datetime.hour)
        ):
            self.bar.datetime = self.bar.datetime.replace(
                second=0, microsecond=0
            )
            self.on_bar(self.bar)

            new_minute = True

        if new_minute:
            self.bar = BarData(
                symbol=tick.symbol,
                exchange=tick.exchange,
                interval=Interval.MINUTE,
                datetime=tick.datetime,
                gateway_name=tick.gateway_name,
                open_price=tick.last_price,
                high_price=tick.last_price,
                low_price=tick.last_price,
                close_price=tick.last_price,
                open_interest=tick.open_interest
            )
        elif self.bar:
            self.bar.high_price = max(self.bar.high_price, tick.last_price)
            if self.last_tick and tick.high_price > self.last_tick.high_price:
                self.bar.high_price = max(self.bar.high_price, tick.high_price)

            self.bar.low_price = min(self.bar.low_price, tick.last_price)
            if self.last_tick and tick.low_price < self.last_tick.low_price:
                self.bar.low_price = min(self.bar.low_price, tick.low_price)

            self.bar.close_price = tick.last_price
            self.bar.open_interest = tick.open_interest
            self.bar.datetime = tick.datetime

        # 成交量计算逻辑
        if self.enable_opening_volume and self.is_first_tick_of_day and self.bar:
            # 当天第一个tick：直接使用成交量
            self.bar.volume = tick.volume
            self.bar.turnover = tick.turnover
            self.is_first_tick_of_day = False
        elif self.last_tick and self.bar:
            # 正常成交量计算
            volume_change: float = tick.volume - self.last_tick.volume
            self.bar.volume += max(volume_change, 0)

            turnover_change: float = tick.turnover - self.last_tick.turnover
            self.bar.turnover += max(turnover_change, 0)

        self.last_tick = tick

    def is_new_day(self, tick_datetime):
        """检测是否是新的一天"""
        if not self.last_tick:
            return True
        
        last_date = self.last_tick.datetime.date()
        current_date = tick_datetime.date()
        return current_date > last_date

    def update_bar(self, bar: BarData) -> None:
        """
        Update 1 minute bar into generator
        """
        if self.interval == Interval.MINUTE:
            self.update_bar_minute_window(bar)
        elif self.interval == Interval.HOUR:
            self.update_bar_hour_window(bar)
        else:
            self.update_bar_daily_window(bar)

    def update_bar_minute_window(self, bar: BarData) -> None:
        """"""
        # If not inited, create window bar object
        if not self.window_bar:
            dt: datetime = bar.datetime.replace(second=0, microsecond=0)
            self.window_bar = BarData(
                symbol=bar.symbol,
                exchange=bar.exchange,
                datetime=dt,
                gateway_name=bar.gateway_name,
                open_price=bar.open_price,
                high_price=bar.high_price,
                low_price=bar.low_price
            )
        # Otherwise, update high/low price into window bar
        else:
            self.window_bar.high_price = max(
                self.window_bar.high_price,
                bar.high_price
            )
            self.window_bar.low_price = min(
                self.window_bar.low_price,
                bar.low_price
            )

        # Update close price/volume/turnover into window bar
        self.window_bar.close_price = bar.close_price
        self.window_bar.volume += bar.volume
        self.window_bar.turnover += bar.turnover
        self.window_bar.open_interest = bar.open_interest

        # Check if window bar completed
        self.interval_count += 1
        if not (self.interval_count < self.window):
            self.interval_count = 0
            self.on_window_bar(self.window_bar)
            self.window_bar = None

    def update_bar_hour_window(self, bar: BarData) -> None:
        """"""
        # If not inited, create hour bar object
        if not self.hour_bar:
            dt: datetime = bar.datetime.replace(minute=0, second=0, microsecond=0)
            self.hour_bar = BarData(
                symbol=bar.symbol,
                exchange=bar.exchange,
                datetime=dt,
                gateway_name=bar.gateway_name,
                open_price=bar.open_price,
                high_price=bar.high_price,
                low_price=bar.low_price
            )
        # Otherwise, update high/low price into hour bar
        else:
            self.hour_bar.high_price = max(
                self.hour_bar.high_price,
                bar.high_price
            )
            self.hour_bar.low_price = min(
                self.hour_bar.low_price,
                bar.low_price
            )

        # Update close price/volume/turnover into hour bar
        self.hour_bar.close_price = bar.close_price
        self.hour_bar.volume += bar.volume
        self.hour_bar.turnover += bar.turnover
        self.hour_bar.open_interest = bar.open_interest

        # Check if hour bar completed
        if bar.datetime.hour != self.hour_bar.datetime.hour:
            self.on_hour_bar(self.hour_bar)
            self.hour_bar = None

    def on_hour_bar(self, bar: BarData) -> None:
        """"""
        if self.on_window_bar:
            self.on_window_bar(bar)

    def update_bar_daily_window(self, bar: BarData) -> None:
        """"""
        # If not inited, create daily bar object
        if not self.daily_bar:
            dt: datetime = bar.datetime.replace(hour=0, minute=0, second=0, microsecond=0)
            self.daily_bar = BarData(
                symbol=bar.symbol,
                exchange=bar.exchange,
                datetime=dt,
                gateway_name=bar.gateway_name,
                open_price=bar.open_price,
                high_price=bar.high_price,
                low_price=bar.low_price
            )
        # Otherwise, update high/low price into daily bar
        else:
            self.daily_bar.high_price = max(
                self.daily_bar.high_price,
                bar.high_price
            )
            self.daily_bar.low_price = min(
                self.daily_bar.low_price,
                bar.low_price
            )

        # Update close price/volume/turnover into daily bar
        self.daily_bar.close_price = bar.close_price
        self.daily_bar.volume += bar.volume
        self.daily_bar.turnover += bar.turnover
        self.daily_bar.open_interest = bar.open_interest

        # Check if daily bar completed
        if bar.datetime.date() != self.daily_bar.datetime.date():
            self.on_daily_bar(self.daily_bar)
            self.daily_bar = None

    def on_daily_bar(self, bar: BarData) -> None:
        """"""
        if self.on_window_bar:
            self.on_window_bar(bar)

    def generate(self) -> BarData | None:
        """"""
        bar = self.bar
        if self.bar:
            bar.datetime = bar.datetime.replace(second=0, microsecond=0)
        return bar

    def __del__(self):
        """清理timer事件注册"""
        if self.enable_auto_flush and self.main_engine:
            self.main_engine.event_engine.unregister(EVENT_TIMER, self._on_timer) 

    def write_log(self, msg: str):
        """写日志"""
        self.main_engine.write_log(msg, self.__class__.__name__)