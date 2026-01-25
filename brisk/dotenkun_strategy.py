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
    
    def __init__(self, log_suffix=None, k: float = 2.0, initial_position: int = 0):
        """
        初始化Dotenkun策略
        
        Args:
            log_suffix: 日志后缀
            k: K参数，用于计算信号阈值
            initial_position: 初始持仓数量（正数为多头，负数为空头，0表示无持仓）
        """
        # 使用kabus gateway
        super().__init__(gateway_type="kabus", log_suffix=log_suffix)
        
        # 策略参数
        self.k = k  # K参数，用于计算信号阈值
        self.initial_position = initial_position  # 初始持仓数量
        
        # 自定义Bar Generator和技术指标配置
        self.bar_window = 5            # 使用5分钟K线
        self.indicator_size = 6       # ArrayManager的大小（用于未来扩展）
        self.hl_range_period = 5

        # 固定订阅的股票
        # self.fixed_symbol = "161030019" # nk mini
        self.fixed_symbol = '161030023' # nk micro
    
    def calculate_position_size(self, symbol: str) -> int:
        """计算持仓数量，基于单只股票最大持仓量"""
        if symbol == self.fixed_symbol:
            return 10
        return 0

    def get_context(self, symbol: str) -> DotenkunContext:
        """获取或创建DotenkunContext"""
        if symbol not in self.contexts:
            context = DotenkunContext(symbol=symbol, k=self.k)
            context.position_size = self.calculate_position_size(symbol)
            
            # 如果是fixed_symbol且有初始position，设置初始position
            if symbol == self.fixed_symbol and self.initial_position != 0:
                context.position = self.initial_position
                # 如果有初始position，设置状态为HOLDING
                context.state = StrategyState.HOLDING
                self.write_log(f"初始化context: {symbol} 初始position={self.initial_position}, 状态={context.state.value}")
            
            self.contexts[symbol] = context
        return self.contexts[symbol]
    
    def create_context(self, symbol: str) -> DotenkunContext:
        """创建新的DotenkunContext"""
        context = DotenkunContext(symbol=symbol, k=self.k)
        context.position_size = self.calculate_position_size(symbol)
        
        # 如果是fixed_symbol且有初始position，设置初始position
        if symbol == self.fixed_symbol and self.initial_position != 0:
            context.position = self.initial_position
            # 如果有初始position，设置状态为HOLDING
            context.state = StrategyState.HOLDING
            self.write_log(f"创建context: {symbol} 初始position={self.initial_position}, 状态={context.state.value}")
        
        self.contexts[symbol] = context
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
    
    def _get_latest_1min_bar(self, symbol: str) -> Optional[BarData]:
        """获取最新的1分钟bar（当前正在构建的）"""
        bar_gen = self.bar_generators.get(symbol)
        if bar_gen and hasattr(bar_gen, 'bar') and bar_gen.bar:
            return bar_gen.bar
        return None
    
    def _is_5min_bar_valid(self, symbol: str, tick_datetime: datetime) -> tuple[bool, Optional[BarData]]:
        """检查5分钟bar是否有效（datetime匹配当前5分钟窗口）
        
        Args:
            symbol: 股票代码
            tick_datetime: 当前tick的datetime
            
        Returns:
            (is_valid, window_bar): is_valid表示window_bar是否有效，window_bar是当前的window_bar（可能为None）
        """
        bar_gen = self.bar_generators.get(symbol)
        if not bar_gen or not hasattr(bar_gen, 'window_bar'):
            return (False, None)
        
        window_bar = bar_gen.window_bar
        if not window_bar:
            return (False, None)
        
        # 计算当前tick应该属于的5分钟窗口
        aligned_minute = (tick_datetime.minute // 5) * 5
        expected_datetime = tick_datetime.replace(minute=aligned_minute, second=0, microsecond=0)
        window_bar_aligned = window_bar.datetime.replace(second=0, microsecond=0)
        
        # 检查日期和datetime是否匹配
        if (tick_datetime.date() != window_bar.datetime.date() or 
            expected_datetime != window_bar_aligned):
            # window_bar过期，无效
            return (False, window_bar)
        
        return (True, window_bar)
    
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
        
        # 验证5分钟bar的有效性
        is_valid, latest_5min_bar = self._is_5min_bar_valid(symbol, tick.datetime)
        
        if not is_valid:
            # window_bar无效（None或过期），fallback到1分钟bar的open_price
            latest_1min_bar = self._get_latest_1min_bar(symbol)
            if latest_1min_bar:
                # 确保open_price是float类型（避免Mock对象导致的格式化错误）
                effective_open_price = float(latest_1min_bar.open_price) if latest_1min_bar.open_price else 0.0
                self.write_log(f"5分钟bar无效（过期或None），使用1分钟bar的open_price: {symbol} 1min_open={effective_open_price:.2f}")
            else:
                # 如果连1分钟bar都没有，使用tick.last_price
                effective_open_price = float(tick.last_price) if tick.last_price else 0.0
                self.write_log(f"5分钟bar和1分钟bar都无效，使用tick.last_price: {symbol} tick_price={effective_open_price:.2f}")
            
            # 使用fallback价格更新context，但不继续处理信号（数据不足）
            context.latest_5min_bar_open = effective_open_price
            return
        else:
            # 正常情况：使用5分钟bar的open_price
            effective_open_price = latest_5min_bar.open_price
        
        # 检查OC异常并使用修正后的open价格
        oc_corrected = False
        
        # 获取上一个完成的5分钟bar信息
        last_close = indicators.get('last_completed_bar_close', 0.0)
        last_datetime = indicators.get('last_completed_bar_datetime', None)
        
        # 检查OC异常：时间差 <= 10分钟 且 价格差 >= 15
        if last_close > 0 and last_datetime:
            time_diff = (latest_5min_bar.datetime - last_datetime).total_seconds() / 60
            price_diff = abs(latest_5min_bar.open_price - last_close)
            
            # TODO: use a better price_diff threshold, 15 only works for futures right now
            if time_diff <= 10 and price_diff >= 15:
                # 使用OC平均值作为修正后的open价格
                effective_open_price = (last_close + latest_5min_bar.open_price) / 2.0
                oc_corrected = True
                self.write_log(f"检测到OC异常，使用修正后的open价格: {symbol} "
                              f"原始open={latest_5min_bar.open_price:.2f} "
                              f"上一个close={last_close:.2f} "
                              f"修正后open={effective_open_price:.2f} "
                              f"价格差={price_diff:.2f} "
                              f"时间差={time_diff:.2f}分钟")
        
        # 使用effective_open_price更新context
        context.latest_5min_bar_open = effective_open_price
        
        # 使用effective_open_price计算信号阈值
        up_threshold = effective_open_price + context.k * hl_range_ma
        down_threshold = effective_open_price - context.k * hl_range_ma
        
        # 检查信号
        current_price = tick.last_price
        signal_triggered = False
        
        if current_price > up_threshold:
            # UP信号
            context.signal_triggered = 'up'
            signal_triggered = True
            open_price_label = '修正后' if oc_corrected else '原始'
            self.write_log(f"UP信号触发: {symbol} {open_price_label}open price={effective_open_price:.2f}, price={current_price:.2f} >= threshold={up_threshold:.2f}")
        elif current_price < down_threshold:
            # DOWN信号
            context.signal_triggered = 'down'
            signal_triggered = True
            open_price_label = '修正后' if oc_corrected else '原始'
            self.write_log(f"DOWN信号触发: {symbol} {open_price_label}open price={effective_open_price:.2f}, price={current_price:.2f} <= threshold={down_threshold:.2f}")
        
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
                # Edge case处理：如果已经发送了close订单，不要再次发送
                if context.exit_order_id:
                    self.write_log(f"检测到相反position但已有close订单: {symbol} {position_direction.value} qty={position_qty}, exit_order_id={context.exit_order_id}, 跳过close")
                else:
                    # 有相反的position，立即close
                    self.write_log(f"检测到相反position: {symbol} {position_direction.value} qty={position_qty}, 立即close")
                    self._close_position_immediately(context, tick, target_direction, position_qty)
            else:
                # 已有相同方向的position，不应该再entry
                self.write_log(f"已有相同方向的position: {symbol} {position_direction.value} qty={position_qty}, 跳过entry")
                return  # 直接返回，不设置pending_entry_direction
        
        # 设置delayed entry（在下一根5分钟bar的open执行）
        # 只有在没有position或position方向相反（已close）时才设置
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
            price=None,  # market order
            volume=qty,
            reference="dotenkun_close"
        )
        
        order_id = self.gateway.send_order(order_req)
        if order_id:
            context.exit_order_id = order_id
            self.write_log(f"发送close订单: {context.symbol} {direction.value} MARKET qty={qty} order_id={order_id}")
    
    def on_order(self, event):
        """订单状态变化回调"""
        order = event.data
        symbol = order.symbol
        
        if symbol != self.fixed_symbol:
            return
        
        context = self.get_context(symbol)
        
        # 修正：根据订单状态更新context中的position
        # 参考hft_bb_reversal_strategy的实现
        if order.status == Status.ALLTRADED:
            # 完全成交
            if order.orderid == context.entry_order_id:
                # Entry订单成交
                if order.direction == Direction.LONG:
                    context.position = order.volume  # 多头持仓为正数
                else:  # Direction.SHORT
                    context.position = -order.volume  # 空头持仓为负数
                
                context.entry_price = order.price
                context.entry_time = order.datetime
                context.entry_order_id = ""
                self.update_context_state(symbol, StrategyState.HOLDING)
                self.write_log(f"Entry订单成交: {symbol} {order.direction.value} position={context.position} price={order.price:.2f}")
            
            elif order.orderid == context.exit_order_id:
                # Exit订单成交
                context.position = 0  # 平仓后position为0
                context.exit_price = order.price
                context.exit_order_id = ""
                self.update_context_state(symbol, StrategyState.IDLE)
                self.write_log(f"Exit订单成交: {symbol} {order.direction.value} position={context.position} price={order.price:.2f}")
        
        elif order.status == Status.PARTTRADED:
            # 部分成交，更新position
            if order.orderid == context.entry_order_id:
                if order.direction == Direction.LONG:
                    context.position = order.traded
                else:  # SHORT
                    context.position = -order.traded
            elif order.orderid == context.exit_order_id:
                if order.direction == Direction.LONG:
                    # Close LONG position: position减少
                    context.position = -int(order.volume) + order.traded
                else:  # SHORT
                    # Close SHORT position: position增加
                    context.position = int(order.volume) - order.traded
            
            self.write_log(f"部分成交更新position: {symbol} position={context.position} traded={order.traded}")
    
    def on_trade(self, event):
        """成交回调"""
        trade = event.data
        symbol = trade.symbol
        
        if symbol != self.fixed_symbol:
            return
        
        context = self.get_context(symbol)
        
        # 更新成交信息（position已在on_order中更新）
        if trade.orderid == context.entry_order_id:
            self.write_log(f"Entry成交: {symbol} price={trade.price:.2f} volume={trade.volume}")
        
        if trade.orderid == context.exit_order_id:
            self.write_log(f"Exit成交: {symbol} price={trade.price:.2f} volume={trade.volume}")
    
    def on_5min_bar(self, bar: BarData):
        """5分钟K线回调函数"""
        # 调用父类方法（记录日志等，父类已经调用了indicator.update_bar）
        super().on_5min_bar(bar)
        
        symbol = bar.symbol
        context = self.get_context(symbol)
        
        # 更新最新5分钟bar的open价格
        context.latest_5min_bar_open = bar.open_price
        
        # 检查是否有pending entry
        if context.pending_entry_direction:
            self._execute_delayed_entry(context, bar)
            context.pending_entry_direction = ""  # 清除pending标志
            context.signal_triggered = ""  # 清除信号标志
        
        # 获取指标值并记录
        if symbol in self.indicator_managers:
            indicator = self.indicator_managers[symbol]
            indicators = indicator.get_indicators()
            
            hl_range_ma = indicators.get('hl_range_ma_5', 0.0)
            hl_range_count = indicators.get('hl_range_count', 0)
            
            self.write_log(f"5分钟K线: {symbol} HL Range MA(5) = {hl_range_ma:.2f} "
                          f"(数据点: {hl_range_count}/{self.hl_range_period})")
    
    def _execute_delayed_entry(self, context: DotenkunContext, bar: BarData):
        """执行delayed entry订单（在5分钟bar的open）"""
        symbol = context.symbol
        
        # Edge case处理：如果已经发送了entry订单，不要再次发送
        if context.entry_order_id:
            self.write_log(f"已有entry订单在等待: {symbol} entry_order_id={context.entry_order_id}, 跳过delayed entry")
            return
        
        # 确定entry方向
        if context.pending_entry_direction == 'long':
            direction = Direction.LONG
        elif context.pending_entry_direction == 'short':
            direction = Direction.SHORT
        else:
            return
        
        # 双重检查：如果已有相同方向的position，不应该再entry
        current_position = context.position
        if current_position != 0:
            position_direction = Direction.LONG if current_position > 0 else Direction.SHORT
            if position_direction == direction:
                self.write_log(f"已有相同方向的position: {symbol} {position_direction.value} qty={abs(current_position)}, 跳过delayed entry")
                context.pending_entry_direction = ""  # 清除pending标志
                return
        
        # 使用market order在open价格执行
        order_req = OrderRequest(
            symbol=symbol,
            exchange=bar.exchange,
            direction=direction,
            type=OrderType.MARKET,
            offset=Offset.OPEN,
            price=None,  # market order
            volume=context.position_size,  # 固定quantity为1
            reference="dotenkun_entry"
        )
        
        order_id = self.gateway.send_order(order_req)
        if order_id:
            context.entry_order_id = order_id
            context.entry_price = bar.open_price
            context.entry_time = bar.datetime
            self.update_context_state(symbol, StrategyState.WAITING_ENTRY)
            self.write_log(f"执行delayed entry: {symbol} {direction.value} MARKET at open={bar.open_price:.2f} order_id={order_id}")
        else:
            self.write_log(f"执行delayed entry失败: {symbol} {direction.value}")
    
    # 子类必须实现的抽象方法
    def get_entry_direction(self, symbol: str) -> str:
        """获取指定股票的entry方向"""
        context = self.get_context(symbol)
        if context.pending_entry_direction:
            return context.pending_entry_direction
        return 'none'
    
    def _calculate_entry_price(self, context, bar, indicators) -> float:
        """计算 entry 价格（使用market order，返回0）"""
        return 0.0  # market order
    
    def _calculate_exit_price(self, context, bar, indicators) -> float:
        """计算 exit 价格（使用market order，返回0）"""
        return 0.0  # market order


def main():
    """主函数"""
    import time
    import argparse
    
    # 设置命令行参数解析
    parser = argparse.ArgumentParser(description='Dotenkun策略')
    parser.add_argument('--initial-position', type=int, default=0,
                       help='初始持仓数量（正数为多头，负数为空头，0表示无持仓，默认: 0）')
    parser.add_argument('--use-replay', action='store_true', default=False,
                       help='启用replay模式（默认: False）')
    parser.add_argument('--replay-data-dir', type=str, 
                       default=r"D:\dev\github\brisk-hack\misc_data",
                       help='Replay数据文件目录（默认: D:\\dev\\github\\brisk-hack\\misc_data）')
    parser.add_argument('--replay-date', type=str, default='2026-01-09',
                       help='Replay日期（格式: YYYY-MM-DD 或 YYYYMMDD，默认: 2026-01-09）')
    parser.add_argument('--replay-speed', type=float, default=10.0,
                       help='Replay速度倍数（1.0 = 实时，默认: 10.0）')
    
    args = parser.parse_args()
    
    print("启动Dotenkun策略...")
    print(f"初始持仓: {args.initial_position}")
    print(f"Replay模式: {args.use_replay}")
    if args.use_replay:
        print(f"Replay数据目录: {args.replay_data_dir}")
        print(f"Replay日期: {args.replay_date}")
        print(f"Replay速度: {args.replay_speed}x")
    
    # 创建策略实例
    strategy = DotenkunStrategy(initial_position=args.initial_position)
    
    try:
        if args.use_replay:
            # Replay模式配置
            replay_setting = {
                "tick_mode": "replay",
                "replay_data_dir": args.replay_data_dir,
                "replay_date": args.replay_date,
                "replay_speed": args.replay_speed,
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
        if args.use_replay:
            strategy.stop_replay()
    except Exception as e:
        print(f"运行过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        strategy.close()


if __name__ == "__main__":
    main()
