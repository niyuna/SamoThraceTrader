"""
Closing Auction Bet Strategy
收盘竞价策略 - 在收盘竞价前建仓，竞价内平仓
"""

import time as time_module
from datetime import datetime, timedelta, time
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, field

from vnpy.trader.object import BarData, TickData
from vnpy.trader.constant import Direction, Offset, OrderType, Status
from vnpy.trader.object import OrderRequest, CancelRequest
from vnpy.trader.event import EVENT_ORDER, EVENT_TRADE

from intraday_strategy_base import IntradayStrategyBase, StrategyState
from enhanced_bargenerator import EnhancedBarGenerator
from common.trading_common import next_n_tick_price, topix500, normalize_price

# 动态参数系统导入
from util.yaml_config_provider import YAMLConfigurationProvider


@dataclass
class ClosingAuctionContext:
    """收盘竞价策略的股票Context"""
    symbol: str
    state: StrategyState = StrategyState.IDLE
    
    # 基础交易字段
    entry_order_id: str = ""
    exit_order_id: str = ""
    position: int = 0  # 持仓数量（正数为多头，负数为空头）
    position_size: int = 100
    already_traded: int = 0  # 已交易数量（base strategy使用）
    
    # 价格相关字段
    base_price: float = 0.0              # 15:00的1分钟K线close price
    long_target_price: float = 0.0       # 做多目标价格
    short_target_price: float = 0.0      # 做空目标价格
    long_trigger_price: float = 0.0      # 做多触发价格
    short_trigger_price: float = 0.0     # 做空触发价格
    entry_price: float = 0.0             # 实际成交价格
    entry_time: Optional[datetime] = None # 成交时间
    entry_trigger_price: float = 0.0     # entry触发价格（base strategy使用）
    entry_trigger_order_price: float = 0.0  # entry触发订单价格（base strategy使用）
    exit_price: float = 0.0                # exit成交价格
    exit_start_time: Optional[datetime] = None  # exit开始时间
    
    # 状态标记
    base_price_set: bool = False         # 是否已设置base price
    trigger_prices_set: bool = False     # 是否已设置触发价格
    entry_window_active: bool = False    # 是否在建仓窗口内
    
    # Base strategy 需要的字段
    trading_banned: bool = False         # 是否被禁止交易
    trade_count: int = 0                 # 交易次数
    timeout_trade_count: int = 0         # 超时交易次数
    timeout_exit_start_time: Optional[datetime] = None  # 超时退出开始时间


class ClosingAuctionBetStrategy(IntradayStrategyBase):
    """收盘竞价策略 - 基于收盘竞价的时间驱动策略"""
    
    def __init__(self, use_mock_gateway=False, gateway_type: str = "brisk_eshiten", log_suffix=None):
        super().__init__(use_mock_gateway=use_mock_gateway, gateway_type=gateway_type, log_suffix=log_suffix)
        
        # 策略参数（默认值，会被YAML配置覆盖）
        self.long_multiplier = 0.995
        self.short_multiplier = 1.0055
        self.trigger_tick_count = 3
        self.position_size = 100
        self.entry_start_time = time(15, 22)
        self.entry_end_time = time(15, 25)
        self.exit_start_time = time(15, 25)
        self.strategy_init_time = time(14, 50)
        
        # 策略状态
        self.contexts: Dict[str, ClosingAuctionContext] = {}
        self.strategy_initialized = False
        self.entry_window_active = False
        self.exit_window_active = False
        self.liquidation_executed = False  # 是否已执行平仓
        
        # 动态参数管理（由基类处理）
        # 不需要在这里初始化，由基类的set_configuration_provider方法处理
        
        self.write_log(f"收盘竞价策略初始化完成 - 建仓窗口: {self.entry_start_time}-{self.entry_end_time}, 平仓窗口: {self.exit_start_time}开始")
    
    def _register_market_close_timer(self):
        """注册收盘前平仓定时器"""
        if not self.event_engine:
            return
            
        from vnpy.trader.event import EVENT_TIMER
        self.event_engine.register(EVENT_TIMER, self._on_market_close_timer)
        self.write_log("收盘前平仓定时器已注册")
    
    def _on_market_close_timer(self, event):
        """收盘前平仓定时器回调"""
        current_time = datetime.now().time()
        
        # 检查是否已执行平仓
        if self.liquidation_executed:
            return
            
        # 检查是否到了平仓时间
        if current_time < self.exit_start_time:
            self.write_log(f"当前时间 {current_time} 早于平仓时间 {self.exit_start_time}，等待中...")
            return
            
        self.write_log(f"当前时间 {current_time} 已达到平仓时间 {self.exit_start_time}，开始执行收盘前平仓流程...")
        self._execute_market_close_liquidation()
        self.liquidation_executed = True
    
    def _update_strategy_specific_params(self, params: Dict[str, Any]):
        """更新收盘竞价策略特定参数"""
        # 更新价格倍数参数
        multiplier_params = [
            'long_multiplier',
            'short_multiplier'
        ]
        
        for param in multiplier_params:
            if param in params:
                old_value = getattr(self, param, None)
                new_value = params[param]
                setattr(self, param, new_value)
                self.write_log(f"价格倍数参数 {param} 更新: {old_value} -> {new_value}")
        
        # 更新其他策略参数
        other_params = [
            'trigger_tick_count',
            'position_size'
        ]
        
        for param in other_params:
            if param in params:
                old_value = getattr(self, param, None)
                new_value = params[param]
                setattr(self, param, new_value)
                self.write_log(f"策略参数 {param} 更新: {old_value} -> {new_value}")
        
        # 更新时间参数
        time_params = [
            'entry_start_time',
            'entry_end_time', 
            'exit_start_time',
            'strategy_init_time'
        ]
        
        for param in time_params:
            if param in params:
                old_value = getattr(self, param, None)
                time_str = params[param]
                new_value = time(*map(int, time_str.split(":")))
                setattr(self, param, new_value)
                self.write_log(f"时间参数 {param} 更新: {old_value} -> {new_value}")
    
    def create_context(self, symbol: str) -> ClosingAuctionContext:
        """创建股票Context"""
        context = ClosingAuctionContext(
            symbol=symbol,
            position_size=self.position_size
        )
        self.contexts[symbol] = context
        self.write_log(f"创建Context: {symbol}")
        return context
    
    def get_context(self, symbol: str) -> ClosingAuctionContext:
        """获取股票Context"""
        if symbol not in self.contexts:
            return self.create_context(symbol)
        return self.contexts[symbol]
    
    def on_tick(self, event):
        """Tick数据回调函数"""
        if not self.strategy_initialized:
            return
            
        tick = event.data
        symbol = tick.symbol
        context = self.get_context(symbol)
        
        current_time = tick.datetime.time()
        
        # 1. 更新BarGenerator
        if symbol not in self.bar_generators:
            self.bar_generators[symbol] = EnhancedBarGenerator(self.on_1min_bar)
        self.bar_generators[symbol].update_tick(tick)
        
        # 2. 检查时间窗口
        self._check_time_windows(current_time)
        
        # 3. 处理建仓逻辑
        if self.entry_window_active and context.state == StrategyState.IDLE:
            self._handle_entry_logic(symbol, context, tick)
        
        # 4. 平仓逻辑现在通过timer处理，不在这里处理
    
    def on_1min_bar(self, bar: BarData):
        """1分钟K线回调函数"""
        symbol = bar.symbol
        context = self.get_context(symbol)
        
        # 检查是否是15:00的K线，设置base price
        if bar.datetime.time() == time(15, 0) and not context.base_price_set:
            context.base_price = bar.close_price
            context.base_price_set = True
            self.write_log(f"设置base price: {symbol} = {context.base_price}")
            
            # 计算目标价格和触发价格
            self._calculate_target_and_trigger_prices(context)
        
        # 如果15:00没有成交，使用15:00后第一根有成交的K线
        elif bar.datetime.time() > time(15, 0) and not context.base_price_set and bar.close_price > 0:
            context.base_price = bar.close_price
            context.base_price_set = True
            self.write_log(f"设置base price (延迟): {symbol} = {context.base_price}")
            
            # 计算目标价格和触发价格
            self._calculate_target_and_trigger_prices(context)
    
    def _check_time_windows(self, current_time: time):
        """检查时间窗口"""
        # 检查建仓窗口
        if self.entry_start_time <= current_time < self.entry_end_time:
            if not self.entry_window_active:
                self.entry_window_active = True
                self.write_log(f"进入建仓窗口: {current_time}")
        elif current_time >= self.entry_end_time and self.entry_window_active:
            self.entry_window_active = False
            self.write_log(f"退出建仓窗口: {current_time}")
        
        # 注意：平仓逻辑现在通过timer处理，不在这里检查
    
    def _calculate_target_and_trigger_prices(self, context: ClosingAuctionContext):
        """计算目标价格和触发价格"""
        if context.base_price <= 0:
            return
        
        # 计算目标价格并进行tick调整
        # long_target_price向上调整，short_target_price向下调整
        from common.trading_common import next_tick_price
        
        context.long_target_price = next_tick_price(
            context.symbol, context.base_price * self.long_multiplier, upside=True
        )
        context.short_target_price = next_tick_price(
            context.symbol, context.base_price * self.short_multiplier, upside=False
        )
        
        # 计算触发价格
        context.long_trigger_price = next_n_tick_price(
            self.trigger_tick_count, context.symbol, context.long_target_price, upside=True
        )
        context.short_trigger_price = next_n_tick_price(
            self.trigger_tick_count, context.symbol, context.short_target_price, upside=False
        )
        
        context.trigger_prices_set = True
        
        self.write_log(f"价格计算完成: {context.symbol} - base={context.base_price:.2f}, "
                      f"long_target={context.long_target_price:.2f}, short_target={context.short_target_price:.2f}, "
                      f"long_trigger={context.long_trigger_price:.2f}, short_trigger={context.short_trigger_price:.2f}")
    
    def _handle_entry_logic(self, symbol: str, context: ClosingAuctionContext, tick: TickData):
        """处理建仓逻辑"""
        if not context.trigger_prices_set:
            return
        
        current_price = tick.last_price
        
        # 检查做多触发
        if current_price <= context.long_trigger_price and not context.entry_order_id:
            self.write_log(f"做多触发: {symbol} {context.long_trigger_price:.2f} {current_price:.2f}")
            self._send_entry_order(context, Direction.LONG, context.long_target_price)
        
        # 检查做空触发
        elif current_price >= context.short_trigger_price and not context.entry_order_id:
            self.write_log(f"做空触发: {symbol} {context.short_trigger_price:.2f} {current_price:.2f}")
            self._send_entry_order(context, Direction.SHORT, context.short_target_price)

        else:
            self.write_log(f"未触发: {symbol} {tick.datetime} {current_price:.2f} trigger: {context.long_trigger_price:.2f} {context.short_trigger_price:.2f}")
    
    def _send_entry_order(self, context: ClosingAuctionContext, direction: Direction, price: float):
        """发送建仓订单"""
        order_id = self._execute_entry(
            context, None, price, direction
        )
        if order_id:
            # Base strategy已经在_execute_trade中更新了context.entry_order_id和context.state
            self.write_log(f"发送建仓订单: {context.symbol} {direction.value} {price:.2f} {order_id}")
    
    def _execute_market_close_liquidation(self):
        """执行收盘前平仓"""
        liquidation_count = 0
        canceled_orders = 0
        
        for symbol, context in self.contexts.items():
            # 1. 取消未成交的entry订单 - 使用state判断更安全
            if context.state == StrategyState.WAITING_ENTRY:
                if context.entry_order_id:
                    if self._cancel_order_safely(context.entry_order_id, symbol):
                        canceled_orders += 1
                        self.write_log(f"取消未成交entry订单: {symbol} {context.entry_order_id}")
                        context.entry_order_id = ""
                        context.state = StrategyState.IDLE
                    else:
                        self.write_log(f"取消entry订单失败: {symbol} {context.entry_order_id}")
                else:
                    # 状态是WAITING_ENTRY但没有订单ID，直接重置状态
                    self.write_log(f"重置异常状态: {symbol} 状态为WAITING_ENTRY但无订单ID")
                    context.state = StrategyState.IDLE
            
            # 2. 对已有持仓发送平仓订单
            if context.position != 0 and not context.exit_order_id:
                direction = Direction.SHORT if context.position > 0 else Direction.LONG
                order_id = self._execute_exit(context, None, 0, direction, OrderType.MARKET)
                if order_id:
                    liquidation_count += 1
                    self.write_log(f"发送平仓订单: {symbol} {direction.value} MARKET {order_id}")
                
            time_module.sleep(0.3)

        # 输出总结
        if canceled_orders > 0:
            self.write_log(f"收盘前取消完成，共取消 {canceled_orders} 个未成交entry订单")
        if liquidation_count > 0:
            self.write_log(f"收盘前平仓完成，共发送 {liquidation_count} 个平仓订单")
        
        if canceled_orders == 0 and liquidation_count == 0:
            self.write_log("收盘前清算完成，无需要取消的订单或无持仓需要平仓")
    
    def on_order(self, event):
        """订单状态回调"""
        order = event.data
        self.write_log(f"订单状态更新: {order.orderid} {order.symbol} {order.direction.value} {order.offset.value} "
                      f"状态: {order.status.value} 价格: {order.price:.2f} 数量: {order.volume}")
        
        # 查找对应的context
        context = self._find_context_by_order_id(order.orderid)
        if not context:
            self.write_log(f"警告: 未找到订单ID {order.orderid} 对应的context")
            return
        
        # 处理部分成交情况
        if order.status == Status.PARTTRADED:
            self.write_log(f"部分成交: {order.symbol} {order.direction.value} {order.offset.value} "
                          f"已成交数量: {order.traded} 剩余数量: {order.volume - order.traded}")
            
            # 更新已成交数量和持仓
            context.already_traded = order.traded
            
            # 更新持仓（部分成交）
            if order.offset == Offset.OPEN:
                if order.direction == Direction.LONG:
                    context.position = order.traded
                else:  # SHORT
                    context.position = -order.traded
            elif order.offset == Offset.CLOSE:
                if order.direction == Direction.LONG:
                    context.position += order.traded
                else:  # SHORT
                    context.position -= order.traded
            
            self.write_log(f"更新持仓: {order.symbol} position={context.position} already_traded={context.already_traded}")
            return
        
        # 只处理完全成交的订单
        if order.status != Status.ALLTRADED:
            return
        
        # 处理入场订单成交
        if order.orderid == context.entry_order_id:
            self._handle_entry_filled(order.symbol, context, order)
        # 处理出场订单成交
        elif order.orderid == context.exit_order_id:
            self._handle_exit_filled(order.symbol, context, order)
        else:
            self.write_log(f"警告: 订单ID {order.orderid} 不匹配任何已知订单")
    
    def _find_context_by_order_id(self, order_id: str):
        """通过订单ID查找对应的context"""
        for context in self.contexts.values():
            if context.entry_order_id == order_id or context.exit_order_id == order_id:
                return context
        return None
    
    def _handle_entry_filled(self, symbol: str, context: ClosingAuctionContext, order):
        """处理入场订单成交"""
        # 更新持仓
        if order.direction == Direction.LONG:
            context.position = order.volume
        else:  # Direction.SHORT
            context.position = -order.volume
        
        # 清除入场订单信息
        context.entry_order_id = ""
        context.entry_price = order.price
        context.entry_time = order.datetime
        
        # 更新状态
        self.update_context_state(symbol, StrategyState.HOLDING)
        
        self.write_log(f"建仓成交: {symbol} {order.direction.value} {order.volume} @ {order.price:.2f}")
    
    def _handle_exit_filled(self, symbol: str, context: ClosingAuctionContext, order):
        """处理出场订单成交"""
        # 清除持仓
        context.position = 0
        
        # 清除出场订单信息
        context.exit_order_id = ""
        context.exit_price = order.price
        
        # 更新状态
        self.update_context_state(symbol, StrategyState.IDLE)
        
        self.write_log(f"平仓成交: {symbol} {order.direction.value} {order.volume} @ {order.price:.2f}")
    
    def on_trade(self, event):
        """成交回调"""
        trade = event.data
        symbol = trade.symbol
        context = self.get_context(symbol)
        
        self.write_log(f"成交: {symbol} {trade.direction.value} {trade.volume} @ {trade.price}")
    
    def get_strategy_status(self) -> Dict[str, Any]:
        """获取策略状态"""
        status = {
            "strategy_initialized": self.strategy_initialized,
            "entry_window_active": self.entry_window_active,
            "exit_window_active": self.exit_window_active,
            "total_symbols": len(self.contexts),
            "active_positions": sum(1 for ctx in self.contexts.values() if ctx.position != 0),
            "pending_orders": sum(1 for ctx in self.contexts.values() if ctx.entry_order_id or ctx.exit_order_id)
        }
        return status


if __name__ == "__main__":
    from datetime import datetime, time as dt_time
    import argparse
    
    # 设置命令行参数解析
    parser = argparse.ArgumentParser(description='收盘竞价策略')
    parser.add_argument('--mock', action='store_true', default=False,
                       help='使用模拟数据')
    parser.add_argument('--debug', action='store_true', default=True,
                       help='启用调试模式')
    
    args = parser.parse_args()
    
    print("启动收盘竞价策略...")
    
    using_mock_data = args.mock
    debug = args.debug
    
    # 检查当前时间，14:50前不初始化策略
    init_time = dt_time(14, 50)
    
    while True:
        current_time = datetime.now().time()
        if current_time >= init_time:
            print(f"当前时间 {current_time} 已达到策略初始化时间 {init_time}，开始初始化...")
            break
        else:
            print(f"当前时间 {current_time} 早于策略初始化时间 {init_time}，等待中...")
            time_module.sleep(60)  # 每分钟检查一次
    
    # 创建策略实例
    strategy = ClosingAuctionBetStrategy(use_mock_gateway=using_mock_data, gateway_type="brisk_eshiten" if not using_mock_data else "mock")
    
    try:
        # 连接Gateway
        if using_mock_data:
            mock_setting = {
                "tick_mode": "replay",
                "replay_data_dir": "F:\\brisk_in_day_frames",
                "replay_date": "20251001",
                "replay_speed": 100.0,
                "mock_account_balance": 10000000,
            }
            strategy.connect(mock_setting)
        else:
            # 真实交易环境
            strategy.connect({})
        
        # 准备股票列表
        symbols = []
        if using_mock_data:
            symbols = ["8136"]  # 使用单只股票进行测试
        else:
            # 使用topix500股票列表
            symbols = list(topix500)
        
        print(f"订阅股票数量: {len(symbols)}")
        print(f"订阅股票: {symbols[:10]}..." if len(symbols) > 10 else f"订阅股票: {symbols}")
                
        # 订阅股票
        strategy.subscribe(symbols)
        
        # 设置动态参数配置提供者
        strategy.set_configuration_provider(YAMLConfigurationProvider("config/strategies", "production"))
        
        # 注册收盘前平仓定时器
        strategy._register_market_close_timer()
        
        # 等待一段时间接收数据
        print("等待接收数据...")
        time_module.sleep(2)
        
        # 设置策略为已初始化
        strategy.strategy_initialized = True
        print("收盘竞价策略启动完成")
        
        # 开始历史数据回放（如果使用模拟数据）
        if using_mock_data:
            strategy.start_replay(mock_setting["replay_date"], symbols)
        
        # 保持运行
        print("按Ctrl+C退出...")
        while True:
            time_module.sleep(30)
            # 定期打印策略状态
            if debug:
                status = strategy.get_strategy_status()
                print(f"策略状态: 初始化={status['strategy_initialized']}, "
                      f"建仓窗口={status['entry_window_active']}, "
                      f"平仓窗口={status['exit_window_active']}, "
                      f"活跃持仓={status['active_positions']}")
            
    except KeyboardInterrupt:
        print("\n收到退出信号...")
    except Exception as e:
        print(f"运行过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        strategy.close()
