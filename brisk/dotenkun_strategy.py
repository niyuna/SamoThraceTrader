"""
Dotenkun 日内交易策略
基于intraday_strategy_base实现，使用kabus gateway
"""
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass

from vnpy.trader.constant import Direction, Offset, Status, OrderType, Exchange
from vnpy.trader.object import BarData, TickData, OrderRequest
from vnpy.event import Event

from intraday_strategy_base import IntradayStrategyBase, StrategyState, StockContext
from dotenkun_indicators import DotenkunIndicator


@dataclass
class DotenkunContext(StockContext):
    """Dotenkun策略专用的Context"""
    k: float = 1.0  # K参数，用于计算信号阈值
    pending_entry_direction: str = ""  # 待执行的entry方向：'long'或'short'，空字符串表示无待执行订单
    latest_5min_bar_open: float = 0.0  # 最新5分钟bar的open价格
    signal_triggered: str = ""  # 触发的信号：'up'或'down'，空字符串表示无信号
    position: int = 0  # 持仓数量（正数为多头，负数为空头，0表示无持仓）


class DotenkunStrategy(IntradayStrategyBase):
    """Dotenkun 日内交易策略"""
    
    def __init__(self, log_suffix=None, k: float = 1.0):
        # 使用kabus gateway
        super().__init__(gateway_type="kabus", log_suffix=log_suffix)
        
        # 策略参数
        self.k = k  # K参数，用于计算信号阈值
        
        # 自定义Bar Generator和技术指标配置
        self.bar_window = 5            # 使用5分钟K线
        self.indicator_size = 6       # ArrayManager的大小（用于未来扩展）
        self.hl_range_period = 5

        # 固定订阅的股票
        # self.fixed_symbol = "161030019" # nk mini
        self.fixed_symbol = '161030023' # nk micro
    
    def get_context(self, symbol: str) -> DotenkunContext:
        """获取或创建DotenkunContext"""
        if symbol not in self.contexts:
            self.contexts[symbol] = DotenkunContext(symbol=symbol, k=self.k)
            self.contexts[symbol].position_size = self.calculate_position_size(symbol)
        return self.contexts[symbol]
    
    def create_context(self, symbol: str) -> DotenkunContext:
        """创建新的DotenkunContext"""
        context = DotenkunContext(symbol=symbol, k=self.k)
        self.contexts[symbol] = context
        context.position_size = self.calculate_position_size(symbol)
        return context
    
    def _create_indicator_manager(self, symbol: str):
        """创建Dotenkun策略专用的技术指标管理器"""
        # 使用独立的DotenkunIndicator类，不依赖TechnicalIndicatorManager
        return DotenkunIndicator(symbol=symbol, size=self.indicator_size, hl_range_period=self.hl_range_period)
    
    def _get_latest_5min_bar(self, symbol: str) -> Optional[BarData]:
        """获取最新的5分钟bar（当前正在构建的）"""
        # 从bar_generator获取window_bar（5分钟bar）
        bar_gen = self.bar_generators.get(symbol)
        if bar_gen and hasattr(bar_gen, 'window_bar') and bar_gen.window_bar:
            return bar_gen.window_bar
        
        # 如果没有window_bar，返回None
        return None
    
    def get_indicators(self, symbol: str) -> Dict[str, Any]:
        """获取指定股票的指标值"""
        if symbol in self.indicator_managers:
            return self.indicator_managers[symbol].get_indicators()
        return {}
    
    def on_tick(self, event: Event):
        """Tick数据回调函数"""
        tick = event.data
        symbol = tick.symbol
        
        # 调用父类方法更新bar
        super().on_tick(event)
        
        # 只处理订阅的symbol
        if symbol != self.fixed_symbol:
            return
        
        context = self.get_context(symbol)
        
        # 获取最新的5分钟bar和指标
        indicators = self.get_indicators(symbol)
        if not indicators:
            return
        
        # 修正：检查hl_range_count，确保数据充足
        hl_range_count = indicators.get('hl_range_count', 0)
        if hl_range_count < 5:
            return  # 数据不足，不生成信号
        
        hl_range_ma = indicators.get('hl_range_ma_5', 0.0)
        if hl_range_ma <= 0:
            return  # 指标未准备好
        
        # 获取最新5分钟bar的open价格
        latest_5min_bar = self._get_latest_5min_bar(symbol)
        if not latest_5min_bar:
            return
        
        context.latest_5min_bar_open = latest_5min_bar.open_price
        
        # 计算信号阈值
        up_threshold = latest_5min_bar.open_price + context.k * hl_range_ma
        down_threshold = latest_5min_bar.open_price - context.k * hl_range_ma
        
        # 检查信号
        current_price = tick.last_price
        signal_triggered = False
        
        if current_price >= up_threshold:
            # UP信号
            context.signal_triggered = 'up'
            signal_triggered = True
            self.write_log(f"UP信号触发: {symbol} price={current_price:.2f} >= threshold={up_threshold:.2f}")
        elif current_price <= down_threshold:
            # DOWN信号
            context.signal_triggered = 'down'
            signal_triggered = True
            self.write_log(f"DOWN信号触发: {symbol} price={current_price:.2f} <= threshold={down_threshold:.2f}")
        
        if signal_triggered:
            self._handle_signal(context, tick)
    
    def _handle_signal(self, context: DotenkunContext, tick: TickData):
        """处理触发的信号"""
        symbol = context.symbol
        
        # 确定目标方向
        target_direction = Direction.LONG if context.signal_triggered == 'up' else Direction.SHORT
        
        # 修正：使用context中的position而不是从gateway查询
        current_position = context.position
        
        # 检查是否有相反的position
        if current_position != 0:
            position_direction = Direction.LONG if current_position > 0 else Direction.SHORT
            position_qty = abs(current_position)
            
            if position_direction != target_direction:
                # 有相反的position，立即close
                self.write_log(f"检测到相反position: {symbol} {position_direction.value} qty={position_qty}, 立即close")
                self._close_position_immediately(context, tick, position_direction, position_qty)
        
        # 设置delayed entry（在下一根5分钟bar的open执行）
        if context.signal_triggered == 'up':
            context.pending_entry_direction = 'long'
        else:
            context.pending_entry_direction = 'short'
        
        self.write_log(f"设置delayed entry: {symbol} direction={context.pending_entry_direction}")
    
    def _close_position_immediately(self, context: DotenkunContext, tick: TickData, direction: Direction, qty: int):
        """立即close position"""
        # 使用market order立即平仓
        order_req = OrderRequest(
            symbol=context.symbol,
            exchange=tick.exchange,
            direction=direction,
            type=OrderType.MARKET,
            offset=Offset.CLOSE,
            price=0,  # market order
            volume=qty,
            reference="dotenkun_close"
        )
        
        order_id = self.gateway.send_order(order_req)
        if order_id:
            context.exit_order_id = order_id
            self.write_log(f"发送close订单: {context.symbol} {direction.value} MARKET qty={qty} order_id={order_id}")
    
    def on_5min_bar(self, bar: BarData):
        """5分钟K线回调函数"""
        # 调用父类方法（记录日志等，父类已经调用了indicator.update_bar）
        super().on_5min_bar(bar)
        
        # 获取指标值（不需要再次调用update_bar，因为父类已经调用了）
        if bar.symbol in self.indicator_managers:
            indicator = self.indicator_managers[bar.symbol]
            indicators = indicator.get_indicators()  # 只获取指标值，不更新
            
            # 记录指标值
            hl_range_ma = indicators.get('hl_range_ma_5', 0.0)
            hl_range_count = indicators.get('hl_range_count', 0)
            
            self.write_log(f"5分钟K线: {bar.symbol} HL Range MA(5) = {hl_range_ma:.2f} "
                          f"(数据点: {hl_range_count}/{self.hl_range_period})")
        
        # 策略逻辑（后续实现）
        # self._check_entry_signal(bar)
        # self._check_exit_signal(bar)
    
    # 子类必须实现的抽象方法
    def get_entry_direction(self, symbol: str) -> str:
        """获取指定股票的entry方向"""
        # 暂时返回'none'，等策略逻辑确定后再实现
        return 'none'
    
    def _calculate_entry_price(self, context, bar, indicators) -> float:
        """计算 entry 价格"""
        # 暂时返回0，等策略逻辑确定后再实现
        return 0.0
    
    def _calculate_exit_price(self, context, bar, indicators) -> float:
        """计算 exit 价格"""
        # 暂时返回0，等策略逻辑确定后再实现
        return 0.0


def main():
    """主函数"""
    import time
    
    print("启动Dotenkun策略...")
    
    # 创建策略实例
    strategy = DotenkunStrategy()
    
    try:
        # 配置replay模式（如果需要使用replay，取消下面的注释并设置正确的路径和日期）
        use_replay = False  # 设置为True启用replay模式
        
        if use_replay:
            # Replay模式配置
            replay_setting = {
                "tick_mode": "replay",
                "replay_data_dir": r"D:\\dev\\github\\brisk-hack\\misc_data",  # 用户需要指定实际路径
                "replay_date": "2026-01-09",  # 用户需要指定实际日期（格式：YYYYMMDD）
                "replay_speed": 10.0,  # 回放速度倍数（1.0 = 实时，2.0 = 2倍速等）
            }
            
            # 连接Gateway（replay模式）
            strategy.connect(replay_setting)
            
            # 订阅固定股票
            strategy.subscribe([strategy.fixed_symbol])
            
            # 开始replay
            strategy.start_replay(replay_setting["replay_date"], [strategy.fixed_symbol])
            
            print("Replay模式已启动，按Ctrl+C退出...")
        else:
            # 实时模式
            strategy.connect()
            
            # 订阅固定股票
            strategy.subscribe([strategy.fixed_symbol])
            
            # 等待一段时间接收数据
            print("等待接收数据...")
            time.sleep(1)
            
            print("实时模式已启动，按Ctrl+C退出...")
        
        # 保持运行
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n收到退出信号...")
        if use_replay:
            strategy.stop_replay()
    except Exception as e:
        print(f"运行过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        strategy.close()


if __name__ == "__main__":
    main()
