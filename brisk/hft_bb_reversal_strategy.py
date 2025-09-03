"""
HFT BB Reversal Strategy
基于布林带反转的日内高频交易策略
"""

import time as time_module
from datetime import datetime, timedelta, time
from typing import Dict, Optional, List, Any
from dataclasses import dataclass

from vnpy.trader.object import BarData, TickData
from vnpy.trader.constant import Direction, Offset, OrderType, Status
from vnpy.trader.object import OrderRequest, CancelRequest
from vnpy.trader.event import EVENT_ORDER, EVENT_TRADE

from intraday_strategy_base import IntradayStrategyBase, StrategyState
from hft_bb_indicators import HFTBBReversalIndicatorV2 as HFTBBReversalIndicator, BriskHistoricalDataProvider
from enhanced_bargenerator import EnhancedBarGenerator


@dataclass
class TriggerLevels:
    """触发价格水平"""
    upper_trigger: float    # 上轨触发价格
    upper_limit: float      # 上轨限价价格
    lower_trigger: float    # 下轨触发价格
    lower_limit: float      # 下轨限价价格


@dataclass
class HFTBBStockContext:
    """HFT BB策略扩展的股票Context"""
    # 基础字段（复用base strategy的StockContext）
    symbol: str
    state: StrategyState = StrategyState.IDLE
    entry_order_id: str = ""
    exit_order_id: str = ""
    position: int = 0  # 持仓数量（正数为多头，负数为空头）
    
    # HFT BB策略特定字段
    trigger_levels: Optional[TriggerLevels] = None  # 触发价格水平
    can_trade: bool = False                          # X条件满足标志
    bb_levels: Optional[dict] = None                 # 布林带水平
    entry_order_price: float = 0.0                   # 入场订单价格
    exit_order_price: float = 0.0                    # 出场订单价格


class HFTBBReversalStrategy(IntradayStrategyBase):
    """HFT BB Reversal策略 - 基于布林带反转的日内高频交易策略"""
    
    def __init__(self, use_mock_gateway=False, use_real_data=False, data_dir="data/brisk_agged_ohlc"):
        super().__init__(use_mock_gateway)
        
        # BB策略特定参数
        self.bb_period = 20
        self.bb_entry_std_multiplier = 3.0
        self.bb_exit_std_multiplier = 0.1
        
        # 模拟持仓管理
        self.simulated_positions = {}  # symbol -> {'long': bool, 'short': bool}
        self.bb_levels = {}            # symbol -> BB价格水平

        self.indicator_size = 20  # 修改为20以匹配真实数据
        
        # 历史数据提供者
        self.use_real_data = use_real_data
        self.data_provider = None
        if use_real_data:
            self.data_provider = BriskHistoricalDataProvider(data_dir)
            self.write_log(f"启用真实数据模式，数据目录: {data_dir}")
        
        # 策略状态
        self.strategy_name = "HFT_BB_Reversal"
        
        # X条件相关参数
        self.x_condition_enabled = True  # 是否启用X条件
        self.x_condition_time_windows = [
            (time(9, 15), time(9, 35)),    # 早上 9:15~9:35
            (time(11, 29), time(11, 30)),  # 中午 11:29~11:30
            (time(14, 35), time(15, 20))   # 下午 14:35~15:20
        ]
        
        self.write_log(f"策略初始化完成: {self.strategy_name}")
        
        # HFT BB策略特定的context管理
        self.hft_contexts: Dict[str, HFTBBStockContext] = {}
    
    def get_hft_context(self, symbol: str) -> HFTBBStockContext:
        """获取HFT BB策略的股票Context"""
        if symbol not in self.hft_contexts:
            raise ValueError(f"HFT context for symbol {symbol} not found. Please ensure the symbol is subscribed first.")
        return self.hft_contexts[symbol]
    
    def create_hft_context(self, symbol: str) -> HFTBBStockContext:
        """创建HFT BB策略的股票Context"""
        if symbol in self.hft_contexts:
            self.write_log(f"Warning: HFT context for symbol {symbol} already exists, returning existing one.")
        else:
            self.hft_contexts[symbol] = HFTBBStockContext(symbol=symbol)
            self.write_log(f"Created HFT context for symbol {symbol}")
        return self.hft_contexts[symbol]
    
    def check_x_condition(self, symbol: str, current_time: datetime = None) -> bool:
        """
        检查X条件是否满足
        
        X条件包括：
        1. 模拟持仓检查 - 目前没有持仓
        2. 时间窗口检查 - 在指定的交易时间段内
        
        Args:
            symbol: 股票代码
            current_time: 当前时间，如果为None则使用系统当前时间
            
        Returns:
            bool: 是否满足X条件
        """
        if not self.x_condition_enabled:
            return True
            
        # 1. 检查模拟持仓 - 目前没有持仓
        if not self._check_no_position(symbol):
            self.write_log(f"X条件检查失败: {symbol} 已有持仓")
            return False
            
        # 2. 检查时间窗口
        if not self._check_time_window(current_time):
            self.write_log(f"X条件检查失败: 当前时间不在交易窗口内")
            return False
            
        self.write_log(f"X条件检查通过: {symbol}")
        return True
    
    def _check_no_position(self, symbol: str) -> bool:
        """
        检查是否没有持仓
        
        Args:
            symbol: 股票代码
            
        Returns:
            bool: 是否没有持仓
        """
        if symbol not in self.simulated_positions:
            return True
            
        position = self.simulated_positions[symbol]
        has_long = position.get('long', False)
        has_short = position.get('short', False)
        
        return not (has_long or has_short)
    
    def _check_time_window(self, current_time: datetime = None) -> bool:
        """
        检查当前时间是否在交易窗口内
        
        Args:
            current_time: 当前时间，如果为None则使用系统当前时间
            
        Returns:
            bool: 是否在交易窗口内
        """
        if current_time is None:
            current_time = datetime.now()
            
        current_time_only = current_time.time()
        
        for start_time, end_time in self.x_condition_time_windows:
            if start_time <= current_time_only <= end_time:
                return True
                
        return False
    
    def preload_historical_data(self, symbols: List[str], date: str = None):
        """预加载历史数据"""
        if not self.use_real_data or not self.data_provider:
            self.write_log("未启用真实数据模式，跳过历史数据预加载")
            return
        
        if date is None:
            # 使用当前日期
            date = datetime.now().strftime("%Y%m%d")
        
        self.write_log(f"开始预加载历史数据: 日期={date}, 股票={symbols}")
        
        for symbol in symbols:
            try:
                # 获取历史数据
                historical_bars = self.data_provider.get_historical_bars(symbol, date, self.indicator_size)
                
                if len(historical_bars) >= self.bb_period:
                    # 创建指标管理器
                    if symbol not in self.indicator_managers:
                        self.indicator_managers[symbol] = self._create_indicator_manager(symbol)
                    
                    # 预加载历史数据
                    self.indicator_managers[symbol].preload_historical_bars(historical_bars)
                    
                    # 检查是否准备就绪
                    if self.indicator_managers[symbol].is_ready_for_trading():
                        self.write_log(f"✓ {symbol} 历史数据预加载成功，准备交易")
                        
                        # 获取初始BB水平
                        bb_levels = self.indicator_managers[symbol].get_bb_levels()
                        if bb_levels:
                            self.bb_levels[symbol] = bb_levels
                            self.write_log(f"  {symbol} 初始BB水平:")
                            self.write_log(f"    Upper: {bb_levels['upper']:.2f}")
                            self.write_log(f"    Lower: {bb_levels['lower']:.2f}")
                            self.write_log(f"    Middle: {bb_levels['middle']:.2f}")
                    else:
                        self.write_log(f"⚠ {symbol} 历史数据预加载完成但未准备交易")
                else:
                    self.write_log(f"✗ {symbol} 历史数据不足，需要{self.bb_period}个bar，实际{len(historical_bars)}个")
                    
            except Exception as e:
                self.write_log(f"✗ {symbol} 历史数据预加载失败: {e}")
    
    def add_symbol(self, symbol: str):
        """重写add_symbol方法，避免覆盖已预加载的指标管理器"""
        # 创建HFT context
        self.create_hft_context(symbol)
        
        # 如果指标管理器已存在且已预加载，不要重新创建
        if symbol in self.indicator_managers and self.indicator_managers[symbol].is_preloaded:
            self.write_log(f"股票 {symbol} 的指标管理器已存在且已预加载，跳过重新创建")
            # 只创建BarGenerator
            self.bar_generators[symbol] = self._create_bar_generator(symbol)
            return
        
        # 否则调用父类方法
        super().add_symbol(symbol)
    
    def _create_indicator_manager(self, symbol: str):
        """创建BB策略专用的技术指标管理器"""
        return HFTBBReversalIndicator(
            symbol=symbol, 
            size=self.indicator_size,
            bb_period=self.bb_period,
            entry_std_multiplier=self.bb_entry_std_multiplier,
            exit_std_multiplier=self.bb_exit_std_multiplier
        )
    
    def _create_bar_generator(self, symbol: str):
        """创建BarGenerator - 使用1分钟K线"""
        return EnhancedBarGenerator(
            on_bar=self.on_1min_bar,
            window=1,  # 1分钟K线
            on_window_bar=self.on_1min_bar,  # 直接使用1分钟bar
            interval=self.bar_interval,
            enable_opening_volume=self.enable_opening_volume,
            enable_auto_flush=self.enable_auto_flush,
            main_engine=self.main_engine
        )
    
    def on_1min_bar(self, bar: BarData):
        """1分钟K线回调函数"""
        symbol = bar.symbol
        context = self.get_hft_context(symbol)
        
        self.write_log(f"收到1分钟K线: {symbol} {bar.datetime.strftime('%H:%M:%S')} "
                      f"开:{bar.open_price:.2f} 高:{bar.high_price:.2f} 低:{bar.low_price:.2f} "
                      f"收:{bar.close_price:.2f} 量:{bar.volume}")
        
        # 1. 更新技术指标和触发价格
        if symbol in self.indicator_managers:
            indicators = self.indicator_managers[symbol].update_bar(bar)
            bb_levels = self._calculate_bb_levels(symbol, indicators)
            
            if bb_levels:
                # 更新BB水平和触发价格
                context.bb_levels = bb_levels
                context.trigger_levels = self._calculate_trigger_levels(bb_levels)
                
                self.write_log(f"更新BB价格水平: {symbol}")
                self.write_log(f"  Upper: {bb_levels['upper']:.2f} (Short Entry)")
                self.write_log(f"  Lower: {bb_levels['lower']:.2f} (Long Entry)")
                self.write_log(f"  Middle: {bb_levels['middle']:.2f} (SMA)")
                self.write_log(f"  Exit_Long: {bb_levels['exit_long']:.2f}")
                self.write_log(f"  Exit_Short: {bb_levels['exit_short']:.2f}")
                self.write_log(f"  STD: {bb_levels['std']:.2f}")
                
                if context.trigger_levels:
                    self.write_log(f"更新触发价格水平: {symbol}")
                    self.write_log(f"  上轨触发: {context.trigger_levels.upper_trigger:.2f}")
                    self.write_log(f"  上轨限价: {context.trigger_levels.upper_limit:.2f}")
                    self.write_log(f"  下轨触发: {context.trigger_levels.lower_trigger:.2f}")
                    self.write_log(f"  下轨限价: {context.trigger_levels.lower_limit:.2f}")
                
                # 2. 检查X条件并更新交易标志
                context.can_trade = self.check_x_condition(symbol, bar.datetime)
                
                # 3. 如果有持仓，维护出场订单
                if context.position != 0:
                    self._manage_exit_order(symbol, bb_levels)
        
        # 调用父类方法（保持原有逻辑）
        super().on_1min_bar(bar)
    
    def _calculate_bb_levels(self, symbol: str, indicators: dict) -> dict:
        """计算BB策略的各个价格水平"""
        # 新的HFTBBReversalIndicatorV2直接返回BB水平
        if 'upper' in indicators and 'lower' in indicators:
            return indicators
        
        # 兼容旧版本
        bb_levels = indicators.get('bb_levels', {})
        if bb_levels:
            return bb_levels
        
        return {}
    
    def on_tick(self, event):
        """Tick数据回调函数"""
        tick = event.data
        symbol = tick.symbol
        context = self.get_hft_context(symbol)

        # print(f"收到Tick: {symbol} {tick.datetime.strftime('%H:%M:%S')} {tick.last_price}")
        
        # 1. 检查X条件是否满足，如果满足则检查入场订单逻辑
        if context.can_trade and context.trigger_levels:
            self._check_entry_logic(symbol, tick, context)
        
        # 2. 更新BarGenerator（复用base strategy方法）
        if symbol in self.bar_generators:
            self.bar_generators[symbol].update_tick(tick)
        
        # 3. 更新模拟持仓（复用base strategy方法）
        self._update_simulated_positions(tick)
    
    def _update_simulated_positions(self, tick):
        """根据tick价格更新模拟持仓状态"""
        symbol = tick.symbol
        if symbol not in self.bb_levels:
            return
        
        current_price = tick.last_price
        bb_levels = self.bb_levels[symbol]
        
        # 初始化模拟持仓
        if symbol not in self.simulated_positions:
            self.simulated_positions[symbol] = {'long': False, 'short': False}
        
        positions = self.simulated_positions[symbol]
        
        # 检查entry信号（当前没有仓位时）
        if not positions['long'] and not positions['short']:
            # 检查long entry
            if current_price <= bb_levels['lower']:
                positions['long'] = True
                self.write_log(f"模拟Long Entry触发: {symbol} 价格: {current_price:.2f} <= {bb_levels['lower']:.2f}")
            
            # 检查short entry
            elif current_price >= bb_levels['upper']:
                positions['short'] = True
                self.write_log(f"模拟Short Entry触发: {symbol} 价格: {current_price:.2f} >= {bb_levels['upper']:.2f}")
        
        # 检查exit信号（当前有仓位时）
        elif positions['long']:
            # Long仓位平仓
            if current_price >= bb_levels['exit_long']:
                positions['long'] = False
                self.write_log(f"模拟Long Exit触发: {symbol} 价格: {current_price:.2f} >= {bb_levels['exit_long']:.2f}")
        
        elif positions['short']:
            # Short仓位平仓
            if current_price <= bb_levels['exit_short']:
                positions['short'] = False
                self.write_log(f"模拟Short Exit触发: {symbol} 价格: {current_price:.2f} <= {bb_levels['exit_short']:.2f}")
    
    def on_order(self, event):
        """订单状态变化回调"""
        order = event.data
        self.write_log(f"订单状态更新: {order.symbol} {order.direction.value} {order.offset.value} "
                      f"状态: {order.status.value} 价格: {order.price:.2f} 数量: {order.volume}")
        
        # 更新Context状态
        context = self.get_context_by_order_id(order.orderid)
        if context:
            if order.status == Status.ALLTRADED:
                if order.offset == Offset.OPEN:
                    # Entry订单完全成交
                    context.already_traded = order.volume
                    if context.already_traded >= context.position_size:
                        self.update_context_state(context.symbol, StrategyState.HOLDING)
                        self.write_log(f"Entry订单完全成交: {context.symbol}")
                else:
                    # Exit订单完全成交
                    self.update_context_state(context.symbol, StrategyState.IDLE)
                    context.trade_count += 1
                    self.write_log(f"Exit订单完全成交: {context.symbol}")
    
    def on_trade(self, event):
        """成交回调"""
        trade = event.data
        self.write_log(f"成交: {trade.symbol} {trade.direction.value} {trade.offset.value} "
                      f"价格: {trade.price:.2f} 数量: {trade.volume}")
    
    def get_entry_direction(self, symbol: str) -> str:
        """获取指定股票的entry方向 - 暂时返回none，等待X条件实现"""
        # TODO: 实现X条件判断
        return 'none'
    
    def _calculate_entry_price(self, context, bar, indicators) -> float:
        """计算entry价格 - 基于BB指标"""
        bb_levels = indicators.get('bb_levels', {})
        if not bb_levels:
            return 0.0
        
        entry_direction = self.get_entry_direction(context.symbol)
        if entry_direction == 'long':
            return bb_levels.get('lower', 0.0)
        elif entry_direction == 'short':
            return bb_levels.get('upper', 0.0)
        
        return 0.0
    
    def _calculate_exit_price(self, context, bar, indicators) -> float:
        """计算exit价格 - 基于BB指标"""
        bb_levels = indicators.get('bb_levels', {})
        if not bb_levels:
            return 0.0
        
        entry_direction = self.get_entry_direction(context.symbol)
        if entry_direction == 'long':
            return bb_levels.get('exit_long', 0.0)
        elif entry_direction == 'short':
            return bb_levels.get('exit_short', 0.0)
        
        return 0.0
    
    def print_simulation_summary(self):
        """打印模拟持仓摘要"""
        print("\n=== 模拟持仓摘要 ===")
        for symbol, positions in self.simulated_positions.items():
            status = []
            if positions['long']:
                status.append("LONG")
            if positions['short']:
                status.append("SHORT")
            if not status:
                status.append("NONE")
            
            bb_info = ""
            if symbol in self.bb_levels:
                bb = self.bb_levels[symbol]
                bb_info = f" | BB: U={bb['upper']:.2f} L={bb['lower']:.2f} M={bb['middle']:.2f}"
            
            print(f"  {symbol}: {', '.join(status)}{bb_info}")
        
        print("\n技术指标状态:")
        for symbol in self.indicator_managers:
            manager = self.indicator_managers[symbol]
            if manager.is_inited():
                indicators = manager.get_indicators()
                if indicators:
                    bb_info = f"BB已初始化 (周期: {indicators.get('period', 'N/A')})"
                else:
                    bb_info = "BB未初始化"
                print(f"  {symbol}: {bb_info}")
            else:
                print(f"  {symbol}: 技术指标未初始化")

    def _calculate_trigger_levels(self, bb_levels: dict) -> Optional[TriggerLevels]:
        """
        计算触发价格水平
        
        Args:
            bb_levels: 布林带水平字典
            
        Returns:
            TriggerLevels: 触发价格水平对象，计算失败返回None
        """
        try:
            upper_bb = bb_levels.get('upper')
            lower_bb = bb_levels.get('lower')
            middle_bb = bb_levels.get('middle')
            
            if upper_bb is None or lower_bb is None or middle_bb is None:
                self.write_log(f"布林带数据不完整: {bb_levels}")
                return None
            
            # 计算触发价格（可以根据策略需求调整）
            # 上轨触发：当价格接近上轨时触发
            upper_trigger = upper_bb * 0.999  # 上轨触发价格（上轨的99.9%）
            upper_limit = upper_bb * 1.001    # 上轨限价价格（上轨的100.1%）
            
            # 下轨触发：当价格接近下轨时触发
            lower_trigger = lower_bb * 1.001  # 下轨触发价格（下轨的100.1%）
            lower_limit = lower_bb * 0.999    # 下轨限价价格（下轨的99.9%）
            
            return TriggerLevels(
                upper_trigger=upper_trigger,
                upper_limit=upper_limit,
                lower_trigger=lower_trigger,
                lower_limit=lower_limit
            )
            
        except Exception as e:
            self.write_log(f"计算触发价格失败: {e}")
            return None

    def _manage_exit_order(self, symbol: str, bb_levels: dict):
        """
        管理出场订单（临时实现）
        
        Args:
            symbol: 股票代码
            bb_levels: 布林带水平
        """
        context = self.get_hft_context(symbol)
        
        if context.position == 0:
            return  # 无持仓，不需要出场订单
        
        # 临时实现：只记录日志
        self.write_log(f"管理出场订单: {symbol} 持仓{context.position}")
        if context.position > 0:
            self.write_log(f"  多头持仓，出场价格: {bb_levels.get('exit_long', 'N/A')}")
        else:
            self.write_log(f"  空头持仓，出场价格: {bb_levels.get('exit_short', 'N/A')}")

    def _check_entry_logic(self, symbol: str, tick, context: HFTBBStockContext):
        """
        检查入场逻辑
        
        Args:
            symbol: 股票代码
            tick: Tick数据
            context: 股票上下文
        """
        trigger_levels = context.trigger_levels
        current_price = tick.last_price
        
        # 检查是否需要下单
        should_order = False
        order_direction = None
        order_price = 0.0
        
        # 检查上轨触发
        if current_price >= trigger_levels.upper_trigger:
            should_order = True
            order_direction = Direction.SHORT
            order_price = trigger_levels.upper_limit
        
        # 检查下轨触发
        elif current_price <= trigger_levels.lower_trigger:
            should_order = True
            order_direction = Direction.LONG
            order_price = trigger_levels.lower_limit
        
        # 检查是否需要取消订单
        should_cancel = False
        if context.entry_order_id:
            # 如果当前价格在两个触发价格之间，取消订单
            if (trigger_levels.lower_trigger < current_price < trigger_levels.upper_trigger):
                should_cancel = True
            # 如果订单价格与当前应该下的价格不同，取消订单
            elif context.entry_order_price != order_price:
                should_cancel = True
        
        # 执行订单操作
        if should_cancel:
            self._cancel_entry_order(symbol, context)
        elif should_order and not context.entry_order_id:
            self._send_entry_order(symbol, order_direction, order_price, 100)  # 使用固定数量100

    def _cancel_entry_order(self, symbol: str, context: HFTBBStockContext):
        """
        取消入场订单（临时实现）
        
        Args:
            symbol: 股票代码
            context: 股票上下文
        """
        if context.entry_order_id:
            # 临时实现：只记录日志
            self.write_log(f"取消入场订单: {symbol} 订单ID: {context.entry_order_id}")
            context.entry_order_id = ""
            context.entry_order_price = 0.0
            # 更新状态为空闲
            self.update_context_state(symbol, StrategyState.IDLE)

    def _send_entry_order(self, symbol: str, direction: Direction, price: float, quantity: int):
        """
        发送入场订单（临时实现）
        
        Args:
            symbol: 股票代码
            direction: 交易方向
            price: 订单价格
            quantity: 订单数量
        """
        context = self.get_hft_context(symbol)
        
        # 临时实现：只记录日志，模拟订单ID
        order_id = f"ENTRY_{symbol}_{direction.value}_{int(price * 100)}"
        context.entry_order_id = order_id
        context.entry_order_price = price
        
        # 更新状态为等待入场
        self.update_context_state(symbol, StrategyState.WAITING_ENTRY)
        
        self.write_log(f"发送入场订单: {symbol} {direction.value} 价格{price:.2f} 数量{quantity} 订单ID: {order_id}")


def main():
    """主函数"""
    print("启动HFT BB Reversal策略...")
    
    using_mock_data = True
    debug = True

    # 创建策略实例
    strategy = HFTBBReversalStrategy(use_mock_gateway=using_mock_data, use_real_data=True, data_dir="data/brisk_agged_ohlc")
    
    try:
        # 连接Gateway
        mock_setting = {
            "tick_mode": "replay",
            "replay_data_dir": "D:\\dev\\github\\brisk-hack\\brisk_in_day_frames",
            "replay_date": "20250718",  # 根据实际数据文件调整
            "replay_speed": 100.0,       # 100倍速回放
            "mock_account_balance": 10000000,
        }
        
        # 连接Gateway
        strategy.connect(mock_setting)
        
        # 订阅股票
        # we will be using a static symbols list for this strategy, it should be a subset of TOPIX500
        symbols = ["9984", "6098"]  # 软银、乐天

        if using_mock_data:
            preload_yyyymmdd = "20250717"
        else:
            from common.date_utils import prev_working_day
            preload_yyyymmdd = prev_working_day(datetime.now().strftime("%Y%m%d"))

        strategy.preload_historical_data(symbols, preload_yyyymmdd)
        strategy.subscribe(symbols)
        
        # 等待一段时间接收数据
        print("等待接收数据...")
        time_module.sleep(2)
        
        # 打印摘要
        strategy.print_simulation_summary()
        
        # 或者开始历史数据回放
        if using_mock_data:
            strategy.start_replay("20250718", symbols)
        
        # 保持运行
        print("按Ctrl+C退出...")
        while True:
            time_module.sleep(5)
            # 定期打印模拟持仓状态
            if debug:
                strategy.print_simulation_summary()
            
    except KeyboardInterrupt:
        print("\n收到退出信号...")
    except Exception as e:
        print(f"运行过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        strategy.close()


if __name__ == "__main__":
    main() 