"""
Intraday Strategy Base Class
"""

import time
from datetime import datetime, timedelta
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Optional
from enum import Enum

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine, LogEngine
from vnpy.trader.object import SubscribeRequest, Exchange, BarData, Interval
from enhanced_bargenerator import EnhancedBarGenerator

from brisk_gateway import BriskGateway
from mock_brisk_gateway import MockBriskGateway

from vnpy.trader.event import EVENT_TICK, EVENT_LOG, EVENT_ORDER, EVENT_TRADE
from vnpy.event import Event
from technical_indicators import TechnicalIndicatorManager
from vnpy.trader.object import OrderRequest, CancelRequest
from vnpy.trader.constant import Direction, Offset, OrderType

from common.trading_common import normalize_price


class StrategyState(Enum):
    """策略状态枚举"""
    IDLE = "idle"                    # 空闲状态，等待 entry 信号
    WAITING_ENTRY = "waiting_entry"  # 等待 entry 订单成交
    HOLDING = "holding"              # 持仓中，等待 exit 信号
    WAITING_EXIT = "waiting_exit"    # 等待 exit 订单成交
    WAITING_TIMEOUT_EXIT = "waiting_timeout_exit"  # 等待timeout exit limit order


@dataclass
class StockContext:
    """股票 Context 数据结构"""
    symbol: str
    state: StrategyState = StrategyState.IDLE
    trade_count: int = 0                    # 当日交易次数
    entry_order_id: str = ""                # entry订单ID
    exit_order_id: str = ""                 # exit订单ID
    entry_price: float = 0.0                # entry成交价格
    entry_time: datetime = None             # entry成交时间
    exit_start_time: datetime = None        # exit订单开始时间
    timeout_exit_start_time: datetime = None  # timeout exit开始时间
    max_exit_wait_time: timedelta = timedelta(minutes=5)  # exit订单最大等待时间
    position_size: int = 100                # 持仓数量


class IntradayStrategyBase:
    """日内策略基础框架 - 集成技术指标和K线生成"""
    
    def __init__(self, use_mock_gateway=False):
        """初始化日内策略基础框架"""
        self.use_mock_gateway = use_mock_gateway
        self.event_engine = None
        self.main_engine = None
        self.gateway = None
        self.gateway_name = None
        self.brisk_gateway = None
        self.bar_generators = {}
        self.indicator_managers = {}
        self.bars_count = defaultdict(int)
        
        # 新增：Context 管理
        self.contexts: Dict[str, StockContext] = {}
        
        from vnpy.trader.setting import SETTINGS
        # by default, will read ".vntrader/vt_setting.json", set in setting.py
        SETTINGS["log.active"] = True
        SETTINGS["log.level"] = 20
        SETTINGS["log.console"] = True
        SETTINGS["log.file_name"] = self.__class__.__name__
        # SETTINGS["log.format"] = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{extra[gateway_name]}</cyan> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
        from vnpy.trader.logger import setup_logger
        setup_logger()
        # log file will be ".vntrader/log/vt_{today_date}.log", set in logger.py
        
    def get_context(self, symbol: str) -> StockContext:
        """获取或创建股票 Context"""
        if symbol not in self.contexts:
            self.contexts[symbol] = StockContext(symbol=symbol)
        return self.contexts[symbol]
    
    def update_context_state(self, symbol: str, new_state: StrategyState):
        """更新 Context 状态"""
        context = self.get_context(symbol)
        old_state = context.state
        context.state = new_state
        self.write_log(f"Context state changed for {symbol}: {old_state.value} -> {new_state.value}")
    
    def get_context_by_order_id(self, order_id: str) -> Optional[StockContext]:
        """根据订单ID查找对应的 Context"""
        for context in self.contexts.values():
            if context.entry_order_id == order_id or context.exit_order_id == order_id:
                return context
        return None
    
    def write_log(self, msg: str):
        self.main_engine.write_log(msg, self.__class__.__name__)
    
    def reset_all_contexts(self):
        """重置所有 Context 状态 - 子类可以重写"""
        for context in self.contexts.values():
            context.state = StrategyState.IDLE
            context.trade_count = 0
            context.entry_order_id = ""
            context.exit_order_id = ""
            context.entry_price = 0.0
            context.entry_time = None
            context.exit_start_time = None
            context.timeout_exit_start_time = None
        self.write_log("All contexts reset")

    # ==================== 核心交易执行方法 ====================
    
    def _execute_order(self, context, bar, price: float, direction: Direction, offset: Offset, order_type: OrderType = OrderType.LIMIT, reference_prefix: str = "order"):
        """统一的订单执行方法"""
        # 创建OrderRequest
        order_req = OrderRequest(
            symbol=context.symbol,
            exchange=bar.exchange if bar else Exchange.TSE,
            direction=direction,
            type=order_type,
            volume=context.position_size,
            price=price,
            offset=offset,
            reference=f"{reference_prefix}_{context.symbol}_{datetime.now().strftime('%H%M%S')}"
        )
        
        # 执行下单
        order_id = self.gateway.send_order(order_req)
        
        if order_id:
            self.write_log(f"订单已提交: {context.symbol} {direction.value} {offset.value} 价格: {price if price else 'N/A'} 订单ID: {order_id}")
            return order_id
        else:
            self.write_log(f"订单被拒绝: {context.symbol} {direction.value} {offset.value}")
            return None

    def _execute_trade(self, context, bar, price: float, direction: Direction, offset: Offset, order_type: OrderType = OrderType.LIMIT, trade_type: str = "order"):
        """统一的交易执行方法 - 合并 entry 和 exit"""
        # 确定交易类型和日志信息
        if offset == Offset.OPEN:
            action = "开仓"
            reference_prefix = f"entry_{direction.value.lower()}"
        else:  # Offset.CLOSE
            action = "平仓"
            reference_prefix = f"exit_{direction.value.lower()}"
        
        d = "做空" if direction == Direction.SHORT else "做多"
        order_type_str = "市价" if order_type == OrderType.MARKET else "限价"
        time_str = bar.datetime.strftime('%H:%M:%S') if bar and bar.datetime else 'N/A'
        self.write_log(f"执行{d}{action}({order_type_str}): {context.symbol} 价格: {price if price else 'N/A'} "
              f"时间: {time_str}")
        
        # 执行订单
        order_id = self._execute_order(
            context=context,
            bar=bar,
            price=price,
            direction=direction,
            offset=offset,
            order_type=order_type,
            reference_prefix=reference_prefix
        )
        
        if order_id:
            if offset == Offset.OPEN:
                # Entry 订单
                context.entry_order_id = order_id
                self.update_context_state(context.symbol, StrategyState.WAITING_ENTRY)
            else:
                # Exit 订单
                context.exit_order_id = order_id
                context.exit_start_time = datetime.now()
                self.update_context_state(context.symbol, StrategyState.WAITING_EXIT)
        
        return order_id

    def _execute_entry(self, context, bar, price, direction: Direction):
        """统一的 entry 订单执行方法"""
        # action = "做空" if direction == Direction.SHORT else "做多"
        # time_str = bar.datetime.strftime('%H:%M:%S') if bar and bar.datetime else 'N/A'
        # self.write_log(f"执行{action}开仓: {context.symbol} 价格: {price:.2f} "
        #       f"时间: {time_str}")
        
        order_id = self._execute_trade(
            context=context,
            bar=bar,
            price=price,
            direction=direction,
            offset=Offset.OPEN
        )
        
        if not order_id:
            # 订单被拒绝，回到 IDLE 状态
            self.update_context_state(bar.symbol, StrategyState.IDLE)
            context.entry_order_id = ""

    def _execute_exit(self, context, bar, price, direction: Direction, order_type: OrderType = OrderType.LIMIT):
        """统一的 exit 订单执行方法"""
        return self._execute_trade(
            context=context,
            bar=bar,
            price=price,
            direction=direction,
            offset=Offset.CLOSE,
            order_type=order_type
        )

    def _cancel_order_safely(self, order_id: str, symbol: str) -> bool:
        """安全撤单，返回是否撤单成功"""
        if not order_id:
            return True  # 没有订单需要撤单
        
        try:
            # 创建 CancelRequest 对象
            cancel_req = CancelRequest(
                orderid=order_id,
                symbol=symbol,
                exchange=Exchange.TSE
            )
            self.gateway.cancel_order(cancel_req)
            self.write_log(f"Cancel order: {order_id}")
            
            # 等待一小段时间确保撤单处理
            import time
            time.sleep(0.1)
            
            return True
        except Exception as e:
            self.write_log(f"撤单失败: {order_id}, 错误: {e}")
            return False

    def _update_entry_order_price(self, context, bar, indicators, change_only: bool = False):
        """更新 entry 订单价格 - 子类可以重写"""
        # 计算新的 entry 价格 - 子类需要实现具体的价格计算逻辑
        old_entry_price = context.entry_price
        new_entry_price = self._calculate_entry_price(context, bar, indicators)
        # not needed any more because we always ensure the price is normalized in calculate_entry_price/calculate_exit_price
        # if change_only:
            # old_entry_price = normalize_price(context.symbol, old_entry_price)

        if new_entry_price != old_entry_price or not change_only:
            self.write_log(f"更新 entry 订单价格: {context.symbol} 旧价格: {old_entry_price:.2f} 新价格: {new_entry_price:.2f}")
            # 撤单并重新下单
            if self._cancel_order_safely(context.entry_order_id, context.symbol):
                # 撤单成功，重新下单 - 子类需要实现具体的下单逻辑
                self._execute_entry_with_direction(context, bar, new_entry_price)

    def _update_exit_order_price(self, context, bar, indicators, change_only: bool = False):
        """更新 exit 订单价格 - 子类可以重写"""
        # 计算新的 exit 价格 - 子类需要实现具体的价格计算逻辑
        # old_exit_price = context.exit_price
        new_exit_price = self._calculate_exit_price(context, bar, indicators)
        
        # 撤单并重新下单
        # if new_exit_price != old_exit_price or not change_only:
        self.write_log(f"更新 exit 订单价格: {context.symbol} 新价格: {new_exit_price:.2f}")
        if self._cancel_order_safely(context.exit_order_id, context.symbol):
            # 撤单成功，重新下单 - 子类需要实现具体的下单逻辑
            self._execute_exit_with_direction(context, bar, new_exit_price)

    # ==================== 子类需要实现的抽象方法 ====================
    
    def _calculate_entry_price(self, context, bar, indicators) -> float:
        """计算 entry 价格 - 子类必须实现"""
        raise NotImplementedError("子类必须实现 _calculate_entry_price 方法")
    
    def _calculate_exit_price(self, context, bar, indicators) -> float:
        """计算 exit 价格 - 子类必须实现"""
        raise NotImplementedError("子类必须实现 _calculate_exit_price 方法")
    
    def _execute_entry_with_direction(self, context, bar, price):
        """根据策略逻辑执行 entry 订单 - 子类必须实现"""
        raise NotImplementedError("子类必须实现 _execute_entry_with_direction 方法")
    
    def _execute_exit_with_direction(self, context, bar, price):
        """根据策略逻辑执行 exit 订单 - 子类必须实现"""
        raise NotImplementedError("子类必须实现 _execute_exit_with_direction 方法")
    
    def on_order(self, event):
        """订单状态变化回调 - 子类可以重写"""
        pass
    
    def on_trade(self, event):
        """成交回调 - 子类可以重写"""
        pass
    
    def add_symbol(self, symbol: str):
        """为指定股票创建BarGenerator和技术指标管理器"""
        # 创建增强版1分钟K线生成器
        self.bar_generators[symbol] = EnhancedBarGenerator(
            on_bar=self.on_1min_bar,
            window=5,  # 5分钟K线
            on_window_bar=self.on_5min_bar,
            interval=Interval.MINUTE,
            enable_opening_volume=True,  # 启用开盘成交量
            enable_auto_flush=False,     # 不启用强制收线（replay模式）
            main_engine=self.main_engine # 传入main_engine
        )
        
        # 创建技术指标管理器
        self.indicator_managers[symbol] = TechnicalIndicatorManager(symbol, size=15)
        # print(f"为 {symbol} 创建增强版K线生成器和技术指标管理器")
        
    def on_tick(self, event: Event):
        """Tick数据回调函数"""
        tick = event.data
        # self.brisk_gateway.write_log(f"收到Tick数据: {tick.symbol} - 价格: {tick.last_price}, 成交量: {tick.last_volume}, 时间: {tick.datetime}, 累计成交量: {tick.volume}, 累计成交额: {tick.turnover}")
        
        # 更新对应的BarGenerator
        if tick.symbol in self.bar_generators:
            self.bar_generators[tick.symbol].update_tick(tick)
    
    def on_1min_bar(self, bar: BarData):
        """1分钟K线回调函数"""
        self.write_log(f"on_1min_bar triggered: {bar.symbol}")
        self.bars_count[f"{bar.symbol}_1min"] += 1
        
        # 更新技术指标
        if bar.symbol in self.indicator_managers:
            indicators = self.indicator_managers[bar.symbol].update_bar(bar)
            
            # 打印详细的指标信息
            print(f"\n=== 1分钟K线: {bar.symbol} {bar.datetime.strftime('%Y-%m-%d %H:%M:%S')} ===")
            print(f"价格数据:")
            print(f"  开盘: {bar.open_price:.2f}  最高: {bar.high_price:.2f}  最低: {bar.low_price:.2f}  收盘: {bar.close_price:.2f}")
            print(f"  成交量: {bar.volume:.0f}  成交额: {bar.turnover:.0f}")
            
            print(f"技术指标:")
            print(f"  VWAP: {indicators['vwap']:.2f}")
            print(f"  ATR(14): {indicators['atr_14']:.2f}")
            print(f"  Volume MA5: {indicators['volume_ma5']:.0f}")
            
            print(f"统计信息:")
            print(f"  Close > VWAP: {indicators['above_vwap_count']} 次")
            print(f"  Close < VWAP: {indicators['below_vwap_count']} 次")
            print(f"  Close = VWAP: {indicators['equal_vwap_count']} 次")
            
            print(f"累计数据:")
            print(f"  当日累计成交量: {indicators['daily_acc_volume']:.0f}")
            print(f"  当日累计成交额: {indicators['daily_acc_turnover']:.0f}")
            print(f"=== ===\n")
            
            # 计算一些额外的指标
            if indicators['daily_acc_volume'] > 0:
                avg_price = indicators['daily_acc_turnover'] / indicators['daily_acc_volume']
                print(f"  当日平均价格: {avg_price:.2f}")
            
            if indicators['above_vwap_count'] + indicators['below_vwap_count'] > 0:
                above_ratio = indicators['above_vwap_count'] / (indicators['above_vwap_count'] + indicators['below_vwap_count'])
                print(f"  Close > VWAP 比例: {above_ratio:.2%}")
    
    def on_5min_bar(self, bar: BarData):
        """5分钟K线回调函数"""
        self.bars_count[f"{bar.symbol}_5min"] += 1
        self.write_log(f"生成5分钟K线: {bar.symbol} {bar.datetime.strftime('%Y-%m-%d %H:%M:%S')} - "
              f"开:{bar.open_price:.2f} 高:{bar.high_price:.2f} 低:{bar.low_price:.2f} "
              f"收:{bar.close_price:.2f} 量:{bar.volume}")
    
    def connect(self, setting: dict = None):
        """连接Gateway，支持mock和真实gateway"""
        if self.use_mock_gateway:
            gateway_cls = MockBriskGateway
            gateway_name = "MOCK_BRISK"
        else:
            gateway_cls = BriskGateway
            gateway_name = "BRISK"

        if not self.main_engine:
            self.event_engine = EventEngine()
            self.main_engine = MainEngine(self.event_engine)
            self.main_engine.add_gateway(gateway_cls)
            self.gateway = self.main_engine.get_gateway(gateway_name)
            self.gateway_name = gateway_name
            self.brisk_gateway = self.gateway
            # 注册事件
            self.event_engine.register(EVENT_TICK, self.on_tick)
            # self.event_engine.register(EVENT_LOG, self.on_log)
            self.event_engine.register(EVENT_ORDER, self.on_order)
            self.event_engine.register(EVENT_TRADE, self.on_trade)

        log_engine: LogEngine = self.main_engine.get_engine("log")       # type: ignore
        self.event_engine.register(EVENT_LOG, log_engine.process_log_event)

        if setting is None:
            if self.use_mock_gateway:
                setting = {
                    "tick_mode": "mock",
                    "mock_account_balance": 10000000,
                }
            else:
                setting = {
                    "tick_server_url": "ws://127.0.0.1:8001/ws",
                    "tick_server_http_url": "http://127.0.0.1:8001",
                }
        self.main_engine.connect(setting, self.gateway_name)
        self.write_log(f"{self.gateway_name} Gateway连接成功")
    
    def subscribe(self, symbols: list):
        """订阅股票"""
        # hacky way to do batch subscription. TODO: design a better way
        for symbol in symbols:
            # 添加股票到技术指标管理器
            self.add_symbol(symbol)
            
        # 订阅行情
        req = SubscribeRequest(symbol=','.join(symbols), exchange=Exchange.TSE)
        self.main_engine.subscribe(req, self.gateway_name)
        self.write_log(f"subscribe: {','.join(symbols)}")
    
    def start_replay(self, date: str, symbols: list = None):
        """开始历史数据回放"""
        if symbols is None:
            symbols = list(self.indicator_managers.keys())
        
        # 统一调用Gateway的回放方法
        if hasattr(self.gateway, 'start_replay'):
            self.gateway.start_replay(date, symbols)
            print(f"开始回放 {date} 的历史数据")
        else:
            print(f"当前Gateway不支持回放功能")
    
    def stop_replay(self):
        """停止历史数据回放"""
        if hasattr(self.gateway, 'stop_replay'):
            self.gateway.stop_replay()
            print("停止历史数据回放")
        else:
            print("当前Gateway不支持回放功能")
    
    def get_indicators(self, symbol: str) -> dict:
        """获取指定股票的技术指标"""
        if symbol in self.indicator_managers:
            return self.indicator_managers[symbol].get_indicators()
        return {}
    
    def _get_current_bar(self, symbol: str) -> Optional[BarData]:
        """获取当前正在构建的1分钟bar"""
        bar_gen = self.bar_generators.get(symbol)
        if bar_gen and hasattr(bar_gen, 'bar'):
            return bar_gen.bar
        return None
    
    def get_all_indicators(self) -> dict:
        """获取所有股票的技术指标"""
        all_indicators = {}
        for symbol in self.indicator_managers:
            all_indicators[symbol] = self.get_indicators(symbol)
        return all_indicators
    
    def print_summary(self):
        """打印统计摘要"""
        print("\n=== 统计摘要 ===")
        print("K线生成统计:")
        for key, count in self.bars_count.items():
            print(f"  {key}: {count} 根")
        
        print("\n技术指标状态:")
        for symbol in self.indicator_managers:
            manager = self.indicator_managers[symbol]
            indicators = manager.get_indicators()
            if indicators:
                print(f"  {symbol}: VWAP={indicators['vwap']:.2f}, "
                      f"ATR(14)={indicators['atr_14']:.2f}, "
                      f"Close>VWAP={indicators['above_vwap_count']}")
    
    def close(self):
        """关闭连接"""
        self.brisk_gateway.close()
        self.event_engine.stop()
        print("Brisk Gateway Demo已关闭")


def main():
    """主函数"""
    print("启动日内策略基础框架...")
    
    # 创建策略实例
    strategy = IntradayStrategyBase()
    
    try:
        # 连接Gateway
        strategy.connect()
        
        # 订阅股票（这里使用示例股票代码）
        # symbols = ["7203", "6758", "9984"]  # 丰田、索尼、软银
        symbols = ["9984"]  # 软银
        strategy.subscribe(symbols)
        
        # 等待一段时间接收数据
        print("等待接收数据...")
        time.sleep(1)
        
        # 打印摘要
        # strategy.print_summary()
        
        # 或者开始历史数据回放
        strategy.start_replay("20250725", symbols)
        # time.sleep(30)
        # strategy.stop_replay()
        
        # 保持运行
        print("按Ctrl+C退出...")
        while True:
            time.sleep(1)
            
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