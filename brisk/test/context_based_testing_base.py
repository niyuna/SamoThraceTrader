"""
基于 Context 的测试基类
提供通用的 Context 快照、模拟数据生成等工具
"""

import sys
import os
import unittest
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List
from dataclasses import asdict
import json

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from vnpy.trader.constant import Direction, Offset, Status, OrderType, Exchange
from vnpy.trader.object import OrderData, TradeData, BarData, Interval, TickData
from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine

from intraday_strategy_base import StrategyState, StockContext


class ContextSnapshot:
    """Context 快照工具"""
    
    def __init__(self, description: str, contexts: Dict[str, Dict[str, Any]], 
                 timestamp: datetime, metadata: Dict[str, Any] = None):
        self.description = description
        self.contexts = contexts
        self.timestamp = timestamp
        self.metadata = metadata or {}


class ContextSnapshotManager:
    """Context 快照管理器"""
    
    def __init__(self, strategy):
        self.strategy = strategy
        self.snapshots: List[ContextSnapshot] = []
    
    def take_snapshot(self, description: str, metadata: Dict[str, Any] = None) -> ContextSnapshot:
        """拍摄 Context 快照"""
        contexts_data = {}
        
        for symbol, context in self.strategy.contexts.items():
            # 获取 Context 的所有属性
            context_dict = asdict(context)
            # 确保 datetime 对象可以序列化
            for key, value in context_dict.items():
                if isinstance(value, datetime):
                    context_dict[key] = value.isoformat()
                elif isinstance(value, timedelta):
                    context_dict[key] = value.total_seconds()
            
            contexts_data[symbol] = context_dict
        
        snapshot = ContextSnapshot(
            description=description,
            contexts=contexts_data,
            timestamp=datetime.now(),
            metadata=metadata or {}
        )
        
        self.snapshots.append(snapshot)
        return snapshot
    
    def assert_state_transition(self, symbol: str, from_state: str, to_state: str, 
                               snapshot_index: int = -1):
        """断言状态转换"""
        if len(self.snapshots) < 2:
            raise ValueError("Need at least 2 snapshots")
        
        if snapshot_index == -1:
            prev_snapshot = self.snapshots[-2]
            curr_snapshot = self.snapshots[-1]
        else:
            prev_snapshot = self.snapshots[snapshot_index - 1]
            curr_snapshot = self.snapshots[snapshot_index]
        
        prev_state = prev_snapshot.contexts[symbol]['state']
        curr_state = curr_snapshot.contexts[symbol]['state']
        
        # 处理枚举值的情况
        if hasattr(prev_state, 'value'):
            prev_state = prev_state.value
        if hasattr(curr_state, 'value'):
            curr_state = curr_state.value
        
        assert prev_state == from_state, f"Expected {from_state}, got {prev_state}"
        assert curr_state == to_state, f"Expected {to_state}, got {curr_state}"
    
    def assert_context_field(self, symbol: str, field: str, expected_value: Any, 
                           snapshot_index: int = -1):
        """断言 Context 字段值"""
        snapshot = self.snapshots[snapshot_index]
        actual_value = snapshot.contexts[symbol][field]
        assert actual_value == expected_value, f"Expected {expected_value}, got {actual_value}"
    
    def export_snapshots(self, filepath: str):
        """导出快照到文件"""
        snapshots_data = []
        for snapshot in self.snapshots:
            snapshot_dict = asdict(snapshot)
            snapshots_data.append(snapshot_dict)
        
        with open(filepath, 'w') as f:
            json.dump(snapshots_data, f, indent=2, default=str)
    
    def load_snapshots(self, filepath: str):
        """从文件加载快照"""
        with open(filepath, 'r') as f:
            snapshots_data = json.load(f)
        
        self.snapshots = []
        for snapshot_dict in snapshots_data:
            snapshot = ContextSnapshot(**snapshot_dict)
            self.snapshots.append(snapshot)


class MockDataGenerator:
    """模拟数据生成器"""
    
    def __init__(self):
        self.order_counter = 0
        self.trade_counter = 0
    
    def create_mock_order(self, symbol: str, status: Status, 
                         direction: Direction = Direction.LONG,
                         order_type: OrderType = OrderType.LIMIT,
                         volume: int = 100,
                         price: float = 100.0,
                         order_id: str = None) -> OrderData:
        """创建模拟订单"""
        self.order_counter += 1
        return OrderData(
            symbol=symbol,
            exchange=Exchange.TSE,
            orderid=order_id or f"mock_order_{self.order_counter}",
            direction=direction,
            type=order_type,
            volume=volume,
            price=price,
            status=status,
            datetime=datetime.now(),
            gateway_name="MOCK_BRISK"
        )
    
    def create_mock_trade(self, symbol: str, price: float, volume: int,
                         direction: Direction = Direction.LONG,
                         trade_id: str = None,
                         order_id: str = None) -> TradeData:
        """创建模拟成交"""
        self.trade_counter += 1
        return TradeData(
            symbol=symbol,
            exchange=Exchange.TSE,
            tradeid=trade_id or f"mock_trade_{self.trade_counter}",
            orderid=order_id or f"mock_order_{self.order_counter}",
            direction=direction,
            volume=volume,
            price=price,
            datetime=datetime.now(),
            gateway_name="MOCK_BRISK"
        )
    
    def create_mock_bar(self, symbol: str, 
                       datetime_obj: datetime = None,
                       open_price: float = 100.0,
                       high_price: float = 101.0,
                       low_price: float = 99.0,
                       close_price: float = 100.5,
                       volume: int = 1000,
                       turnover: float = 100000) -> BarData:
        """创建模拟K线"""
        return BarData(
            symbol=symbol,
            exchange=Exchange.TSE,
            datetime=datetime_obj or datetime.now(),
            interval=Interval.MINUTE,
            volume=volume,
            turnover=turnover,
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            close_price=close_price,
            gateway_name="MOCK_BRISK"
        )
    
    def create_mock_tick(self, symbol: str,
                        datetime_obj: datetime = None,
                        price: float = 100.0,
                        volume: int = 100) -> TickData:
        """创建模拟Tick数据"""
        return TickData(
            symbol=symbol,
            exchange=Exchange.TSE,
            datetime=datetime_obj or datetime.now(),
            last_price=price,
            last_volume=volume,
            volume=volume,
            turnover=price * volume,
            gateway_name="MOCK_BRISK"
        )
    
    def create_mock_indicators(self, vwap: float = 100.0, 
                             atr_14: float = 1.0,
                             above_vwap_count: int = 0,
                             below_vwap_count: int = 0) -> dict:
        """创建模拟技术指标"""
        return {
            'vwap': vwap,
            'atr_14': atr_14,
            'above_vwap_count': above_vwap_count,
            'below_vwap_count': below_vwap_count,
            'equal_vwap_count': 0,
            'volume_ma5': 1000,
            'daily_acc_volume': 10000,
            'daily_acc_turnover': 1000000
        }


class ContextBasedStrategyTest(unittest.TestCase):
    """基于 Context 的策略测试基类"""
    
    def setUp(self):
        """测试前准备 - 子类需要重写"""
        self.strategy = None
        self.snapshot_manager = None
        self.mock_generator = MockDataGenerator()
        
        # 配置Mock Gateway不自动处理订单
        self.mock_gateway_config = {
            "mock_auto_process_orders": False,  # 禁用自动订单处理
            "tick_mode": "mock",
            "mock_tick_interval": 1.0, # will not trigger any real tick unless we subscribe to a specific symbol
        }
        
    def tearDown(self):
        """测试后清理"""
        if self.strategy:
            self.strategy.close()
    
    def setup_context(self, symbol: str, **kwargs):
        """设置 Context 初始状态"""
        context = self.strategy.get_context(symbol)
        for key, value in kwargs.items():
            if hasattr(context, key):
                setattr(context, key, value)
        return context
    
    def trigger_order_update(self, order: OrderData):
        """触发订单更新"""
        # 使用Mock Gateway的手动处理功能
        success = False
        if hasattr(self.strategy, 'gateway') and hasattr(self.strategy.gateway, 'manually_process_order'):
            # 使用Mock Gateway的手动处理
            success = self.strategy.gateway.manually_process_order(order.orderid, order.status)
        if not success:
            # 回退到直接触发事件
            from vnpy.trader.event import EVENT_ORDER
            from vnpy.event import Event
            event = Event(EVENT_ORDER, order)
            self.strategy.on_order(event)
    
    def trigger_trade(self, trade: TradeData):
        """触发成交事件"""
        # 创建事件
        from vnpy.trader.event import EVENT_TRADE
        from vnpy.event import Event
        event = Event(EVENT_TRADE, trade)
        self.strategy.on_trade(event)
    
    def trigger_bar_update(self, bar: BarData):
        """触发K线更新"""
        # 直接mock技术指标，覆盖策略的get_indicators方法
        indicators = self.get_mock_indicators(bar.symbol)
        
        # 临时替换策略的get_indicators方法
        original_get_indicators = self.strategy.get_indicators
        
        def mock_get_indicators(symbol: str) -> dict:
            if symbol == bar.symbol:
                return indicators
            return original_get_indicators(symbol)
        
        self.strategy.get_indicators = mock_get_indicators
        
        try:
            # 调用策略的 on_1min_bar 方法
            self.strategy.on_1min_bar(bar)
        finally:
            # 恢复原方法
            self.strategy.get_indicators = original_get_indicators
    
    # this should be overridden by the subclass
    def get_mock_indicators(self, symbol: str) -> dict:
        """获取模拟技术指标 - 子类可以重写"""
        return self.mock_generator.create_mock_indicators()
    
    def assert_context_state(self, symbol: str, expected_state: str):
        """断言 Context 状态"""
        context = self.strategy.get_context(symbol)
        assert context.state.value == expected_state, \
            f"Expected state {expected_state}, got {context.state.value}"
    
    def assert_context_field(self, symbol: str, field: str, expected_value: Any):
        """断言 Context 字段值"""
        context = self.strategy.get_context(symbol)
        actual_value = getattr(context, field)
        assert actual_value == expected_value, \
            f"Expected {field}={expected_value}, got {actual_value}"
    
    # ==================== 通用测试方法 ====================
    
    def test_basic_state_transitions(self):
        """测试基本状态转换 - 子类需要实现"""
        # 如果子类没有实现，跳过这个测试
        self.skipTest("子类需要实现 test_basic_state_transitions 方法")
    
    def test_edge_cases(self):
        """测试边界条件 - 子类需要实现"""
        # 如果子类没有实现，跳过这个测试
        self.skipTest("子类需要实现 test_edge_cases 方法")
    
    def test_complete_flow(self):
        """测试完整流程 - 子类需要实现"""
        # 如果子类没有实现，跳过这个测试
        self.skipTest("子类需要实现 test_complete_flow 方法")
    
    def test_error_conditions(self):
        """测试错误条件 - 子类需要实现"""
        # 如果子类没有实现，跳过这个测试
        self.skipTest("子类需要实现 test_error_conditions 方法")


class TestBasicStateTransitionsMixin:
    """基本状态转换测试混入类"""
    
    def test_idle_to_waiting_entry(self):
        """测试 IDLE -> WAITING_ENTRY 转换"""
        symbol = self.test_symbol
        
        # 设置初始状态
        self.setup_context(symbol, state=StrategyState.IDLE, trade_count=0)
        
        # 拍摄初始快照
        self.snapshot_manager.take_snapshot("Initial state")
        
        # 触发 entry 信号（通过 bar 更新）
        bar = self.mock_generator.create_mock_bar(symbol)
        self.trigger_bar_update(bar)
        time.sleep(0.01)
        
        # 拍摄快照并验证状态转换
        self.snapshot_manager.take_snapshot("After entry signal")
        self.snapshot_manager.assert_state_transition(symbol, "idle", "waiting_entry")
        
        # 验证生成了订单
        context = self.strategy.get_context(symbol)
        print(f"context: {context}")
        assert context.entry_order_id != ""
    
    def test_waiting_entry_to_holding(self):
        """测试 WAITING_ENTRY -> HOLDING 转换"""
        symbol = self.test_symbol
        
        # 设置初始状态
        context = self.setup_context(symbol, state=StrategyState.WAITING_ENTRY)
        context.entry_order_id = "mock_entry_order"
        
        # 拍摄初始快照
        self.snapshot_manager.take_snapshot("Initial state")
        
        # 触发 entry 订单成交
        order = self.mock_generator.create_mock_order(
            symbol, Status.ALLTRADED, order_id="mock_entry_order"
        )
        self.trigger_order_update(order)
        time.sleep(0.01)
        
        # 拍摄快照并验证状态转换
        self.snapshot_manager.take_snapshot("After entry order completed")
        # no holding state here because on_order will handle the state transition
        self.snapshot_manager.assert_state_transition(symbol, "waiting_entry", "waiting_exit")
    
    def test_waiting_exit_to_idle(self):
        """测试 WAITING_EXIT -> IDLE 转换"""
        symbol = self.test_symbol
        
        # 设置初始状态
        context = self.setup_context(symbol, state=StrategyState.WAITING_EXIT)
        context.exit_order_id = "mock_exit_order"
        context.trade_count = 0
        
        # 拍摄初始快照
        self.snapshot_manager.take_snapshot("Initial state")
        
        # 触发 exit 订单成交
        order = self.mock_generator.create_mock_order(
            symbol, Status.ALLTRADED, order_id="mock_exit_order"
        )
        self.trigger_order_update(order)
        
        # 拍摄快照并验证状态转换
        self.snapshot_manager.take_snapshot("After exit order completed")
        self.snapshot_manager.assert_state_transition(symbol, "waiting_exit", "idle")
        self.snapshot_manager.assert_context_field(symbol, "trade_count", 1)


class TestEdgeCasesMixin:
    """边界条件测试混入类"""
    
    def test_trade_count_limit(self):
        """测试交易次数限制"""
        symbol = self.test_symbol
        
        # 设置已达到最大交易次数
        self.setup_context(symbol, trade_count=3, state=StrategyState.IDLE)
        
        # 尝试生成新信号
        bar = self.mock_generator.create_mock_bar(symbol)
        self.trigger_bar_update(bar)
        
        # 验证状态没有变化
        self.assert_context_state(symbol, "idle")
        self.assert_context_field(symbol, "trade_count", 3)
    
    def test_entry_order_rejection(self):
        """测试 entry 订单被拒绝"""
        symbol = self.test_symbol
        
        # 设置等待 entry 状态
        context = self.setup_context(symbol, state=StrategyState.WAITING_ENTRY)
        context.entry_order_id = "mock_entry_order"
        
        # 拍摄初始快照
        self.snapshot_manager.take_snapshot("Initial state")
        
        # 触发订单被拒绝
        order = self.mock_generator.create_mock_order(
            symbol, Status.REJECTED, order_id="mock_entry_order"
        )
        self.trigger_order_update(order)
        
        # 拍摄快照并验证状态转换
        self.snapshot_manager.take_snapshot("After order rejection")
        self.snapshot_manager.assert_state_transition(symbol, "waiting_entry", "idle")
        self.snapshot_manager.assert_context_field(symbol, "entry_order_id", "")
    
    def test_exit_order_rejection(self):
        """测试 exit 订单被拒绝"""
        symbol = self.test_symbol
        
        # 设置等待 exit 状态
        context = self.setup_context(symbol, state=StrategyState.WAITING_EXIT)
        context.exit_order_id = "mock_exit_order"
        
        # 拍摄初始快照
        self.snapshot_manager.take_snapshot("Initial state")
        
        # 触发订单被拒绝
        order = self.mock_generator.create_mock_order(
            symbol, Status.REJECTED, order_id="mock_exit_order"
        )
        self.trigger_order_update(order)
        
        # 拍摄快照并验证状态转换
        self.snapshot_manager.take_snapshot("After order rejection")
        self.snapshot_manager.assert_state_transition(symbol, "waiting_exit", "holding")
        self.snapshot_manager.assert_context_field(symbol, "exit_order_id", "")
    
    def test_trading_time_limit(self):
        """测试交易时间限制"""
        symbol = self.test_symbol
        
        # 设置初始状态
        self.setup_context(symbol, state=StrategyState.IDLE, trade_count=0)
        
        # 创建超过交易时间的 bar
        late_time = datetime.now().replace(hour=23, minute=59, second=59)  # 15:00
        bar = self.mock_generator.create_mock_bar(symbol, datetime_obj=late_time)
        
        # 尝试生成信号
        self.trigger_bar_update(bar)
        
        # 验证状态没有变化
        self.assert_context_state(symbol, "idle")


class TestCompleteFlowMixin:
    """完整流程测试混入类"""
    
    def test_complete_trading_cycle(self):
        """测试完整交易周期"""
        symbol = self.test_symbol
        
        # 1. 初始状态
        self.setup_context(symbol, state=StrategyState.IDLE, trade_count=0)
        self.snapshot_manager.take_snapshot("Initial state")
        
        # 2. 生成 entry 信号
        bar = self.mock_generator.create_mock_bar(symbol)
        self.trigger_bar_update(bar)
        time.sleep(0.01)
        self.snapshot_manager.take_snapshot("After entry signal")
        
        # 3. entry 订单成交
        context = self.strategy.get_context(symbol)
        entry_order = self.mock_generator.create_mock_order(
            symbol, Status.ALLTRADED, order_id=context.entry_order_id
        )
        self.trigger_order_update(entry_order)
        time.sleep(0.01)
        self.snapshot_manager.take_snapshot("After entry trade")
        
        # 4. exit 订单成交
        context = self.strategy.get_context(symbol)
        if context.exit_order_id:  # 确保有exit订单ID
            exit_order = self.mock_generator.create_mock_order(
                symbol, Status.ALLTRADED, order_id=context.exit_order_id
            )
            self.trigger_order_update(exit_order)
            time.sleep(0.01)
            self.snapshot_manager.take_snapshot("After exit trade")
        else:
            # 如果没有exit订单ID，说明策略没有生成exit订单
            print(f"Warning: No exit order ID found for {symbol}")
            time.sleep(0.01)
            self.snapshot_manager.take_snapshot("No exit order generated")
        
        # 5. 验证最终状态
        self.assert_context_state(symbol, "idle")
        self.assert_context_field(symbol, "trade_count", 1)
        
        # 6. 验证状态转换序列
        self.snapshot_manager.assert_state_transition(symbol, "idle", "waiting_entry", 1)
        self.snapshot_manager.assert_state_transition(symbol, "waiting_entry", "waiting_exit", 2)
        # no holding state here because on_order will handle the state transition
        # self.snapshot_manager.assert_state_transition(symbol, "holding", "waiting_exit", 3)
        self.snapshot_manager.assert_state_transition(symbol, "waiting_exit", "idle", 3)


class TestMultipleSymbolsMixin:
    """多股票测试混入类"""
    
    def test_multiple_symbols_independent(self):
        """测试多股票独立交易"""
        symbol1 = self.test_symbol
        symbol2 = self.test_symbol2
        
        # 设置初始状态
        self.setup_context(symbol1, state=StrategyState.IDLE, trade_count=0)
        self.setup_context(symbol2, state=StrategyState.IDLE, trade_count=0)
        
        # 拍摄初始快照
        self.snapshot_manager.take_snapshot("Initial state")
        
        # 同时触发两个股票的 entry 信号
        bar1 = self.mock_generator.create_mock_bar(symbol1)
        bar2 = self.mock_generator.create_mock_bar(symbol2)
        self.trigger_bar_update(bar1)
        self.trigger_bar_update(bar2)
        
        # 拍摄快照并验证状态转换
        self.snapshot_manager.take_snapshot("After entry signals")
        self.snapshot_manager.assert_state_transition(symbol1, "idle", "waiting_entry")
        self.snapshot_manager.assert_state_transition(symbol2, "idle", "waiting_entry")
        
        # 验证两个股票都有订单
        context1 = self.strategy.get_context(symbol1)
        context2 = self.strategy.get_context(symbol2)
        assert context1.entry_order_id != ""
        assert context2.entry_order_id != ""
        assert context1.entry_order_id != context2.entry_order_id


class TestPositionSizeMixin:
    """持仓数量测试混入类"""
    
    def test_calculate_position_size_basic(self):
        """测试基本持仓数量计算"""
        symbol = self.test_symbol
        
        # Mock stock_master数据
        mock_stock_data = {
            symbol: {
                'basePrice10': 1500,  # 150.0日元
                'market_cap': 200_000_000_000,  # 2000亿日元
                'calcSharesOutstanding': 1000000
            }
        }
        
        # Mock get_stockmaster函数
        original_get_stockmaster = None
        try:
            import stock_master
            original_get_stockmaster = stock_master.get_stockmaster
            stock_master.get_stockmaster = lambda: mock_stock_data
        except ImportError:
            # 如果无法导入stock_master，直接mock策略的stock_master
            self.strategy.stock_master = mock_stock_data
        
        try:
            # 初始化stock_master
            self.strategy.initialize_stock_master()
            
            # 测试持仓数量计算
            position_size = self.strategy.calculate_position_size(symbol)
            
            # 验证计算结果
            # 预期: 1000_000 / 150.0 / 100 = 66.67，round(66.67) = 67，67 * 100 = 6700
            expected_position = 6700
            assert position_size == expected_position, f"持仓数量应该是{expected_position}，实际是{position_size}"
            
        finally:
            # 恢复原始函数
            if original_get_stockmaster:
                stock_master.get_stockmaster = original_get_stockmaster
    
    def test_calculate_position_size_different_prices(self):
        """测试不同价格下的持仓数量计算"""
        symbol = self.test_symbol
        
        # Mock stock_master数据
        mock_stock_data = {
            symbol: {
                'basePrice10': 5000,  # 500.0日元
                'market_cap': 200_000_000_000,
                'calcSharesOutstanding': 1000000
            }
        }
        
        # Mock get_stockmaster函数
        original_get_stockmaster = None
        try:
            import stock_master
            original_get_stockmaster = stock_master.get_stockmaster
            stock_master.get_stockmaster = lambda: mock_stock_data
        except ImportError:
            self.strategy.stock_master = mock_stock_data
        
        try:
            # 初始化stock_master
            self.strategy.initialize_stock_master()
            
            # 测试不同价格的情况
            position_size = self.strategy.calculate_position_size(symbol)
            expected_position = 2000  # 1000_000 / 500.0 / 100 = 20，round(20) = 20，20 * 100 = 2000
            assert position_size == expected_position, f"持仓数量应该是{expected_position}，实际是{position_size}"
            
            # 测试价格过高的情况（应该返回最小持仓数量）
            mock_stock_data[symbol]['basePrice10'] = 500000  # 50000.0日元
            position_size2 = self.strategy.calculate_position_size(symbol)
            expected_position2 = 100  # 最小持仓数量
            assert position_size2 == expected_position2, f"持仓数量应该是{expected_position2}，实际是{position_size2}"
            
        finally:
            # 恢复原始函数
            if original_get_stockmaster:
                stock_master.get_stockmaster = original_get_stockmaster
    
    def test_calculate_position_size_invalid_data(self):
        """测试无效数据时的持仓数量计算"""
        symbol = self.test_symbol
        
        # Mock无效的stock_master数据
        mock_stock_data = {
            symbol: {
                'basePrice10': 0,  # 无效价格
                'market_cap': 0,
                'calcSharesOutstanding': 0
            }
        }
        
        # Mock get_stockmaster函数
        original_get_stockmaster = None
        try:
            import stock_master
            original_get_stockmaster = stock_master.get_stockmaster
            stock_master.get_stockmaster = lambda: mock_stock_data
        except ImportError:
            self.strategy.stock_master = mock_stock_data
        
        try:
            # 初始化stock_master
            self.strategy.initialize_stock_master()
            
            # 测试无效数据时的持仓数量计算
            position_size = self.strategy.calculate_position_size(symbol)
            
            # 应该返回默认持仓数量
            expected_position = 100
            assert position_size == expected_position, f"无效数据时持仓数量应该是{expected_position}，实际是{position_size}"
            
        finally:
            # 恢复原始函数
            if original_get_stockmaster:
                stock_master.get_stockmaster = original_get_stockmaster
    
    def test_calculate_position_size_missing_symbol(self):
        """测试缺失股票时的持仓数量计算"""
        symbol = "NONEXISTENT"
        
        # Mock空的stock_master数据
        mock_stock_data = {}
        
        # Mock get_stockmaster函数
        original_get_stockmaster = None
        try:
            import stock_master
            original_get_stockmaster = stock_master.get_stockmaster
            stock_master.get_stockmaster = lambda: mock_stock_data
        except ImportError:
            self.strategy.stock_master = mock_stock_data
        
        try:
            # 初始化stock_master
            self.strategy.initialize_stock_master()
            
            # 测试缺失股票时的持仓数量计算
            position_size = self.strategy.calculate_position_size(symbol)
            
            # 应该返回默认持仓数量
            expected_position = 100
            assert position_size == expected_position, f"缺失股票时持仓数量应该是{expected_position}，实际是{position_size}"
            
        finally:
            # 恢复原始函数
            if original_get_stockmaster:
                stock_master.get_stockmaster = original_get_stockmaster
    
    def test_single_stock_max_position_parameter(self):
        """测试single_stock_max_position参数"""
        # 测试默认值
        assert self.strategy.single_stock_max_position == 1000_000, f"默认值应该是1000_000，实际是{self.strategy.single_stock_max_position}"
        
        # 测试参数设置（如果策略支持set_strategy_params）
        if hasattr(self.strategy, 'set_strategy_params'):
            self.strategy.set_strategy_params(single_stock_max_position=500_000)
            assert self.strategy.single_stock_max_position == 500_000, f"设置后应该是500_000，实际是{self.strategy.single_stock_max_position}"
            
            # 测试参数重置
            self.strategy.set_strategy_params(single_stock_max_position=2000_000)
            assert self.strategy.single_stock_max_position == 2000_000, f"重置后应该是2000_000，实际是{self.strategy.single_stock_max_position}"
    
    def test_position_size_rounding(self):
        """测试持仓数量的取整逻辑"""
        symbol = self.test_symbol
        
        # Mock stock_master数据，测试取整逻辑
        mock_stock_data = {
            symbol: {
                'basePrice10': 3333,  # 333.3日元，测试取整
                'market_cap': 200_000_000_000,
                'calcSharesOutstanding': 1000000
            }
        }
        
        # Mock get_stockmaster函数
        original_get_stockmaster = None
        try:
            import stock_master
            original_get_stockmaster = stock_master.get_stockmaster
            stock_master.get_stockmaster = lambda: mock_stock_data
        except ImportError:
            self.strategy.stock_master = mock_stock_data
        
        try:
            # 初始化stock_master
            self.strategy.initialize_stock_master()
            
            # 测试取整逻辑
            # 1000_000 / 333.3 / 100 = 30.003，round(30.003) = 30，30 * 100 = 3000
            position_size = self.strategy.calculate_position_size(symbol)
            expected_position = 3000  # 应该取整到3000
            assert position_size == expected_position, f"持仓数量应该是{expected_position}，实际是{position_size}"
            
            # 测试另一个取整案例
            mock_stock_data[symbol]['basePrice10'] = 2500  # 250.0日元
            position_size2 = self.strategy.calculate_position_size(symbol)
            expected_position2 = 4000  # 1000_000 / 250.0 / 100 = 40，round(40) = 40，40 * 100 = 4000
            assert position_size2 == expected_position2, f"持仓数量应该是{expected_position2}，实际是{position_size2}"
            
        finally:
            # 恢复原始函数
            if original_get_stockmaster:
                stock_master.get_stockmaster = original_get_stockmaster
    
    def test_stock_master_initialization(self):
        """测试stock_master初始化"""
        # 测试初始化方法存在
        assert hasattr(self.strategy, 'initialize_stock_master'), "策略应该有initialize_stock_master方法"
        assert hasattr(self.strategy, 'stock_master'), "策略应该有stock_master属性"
        
        # 测试辅助方法存在
        assert hasattr(self.strategy, 'get_stock_info'), "策略应该有get_stock_info方法"
        assert hasattr(self.strategy, 'get_stock_market_cap'), "策略应该有get_stock_market_cap方法"
        assert hasattr(self.strategy, 'get_stock_prev_close'), "策略应该有get_stock_prev_close方法"
        assert hasattr(self.strategy, 'calculate_position_size'), "策略应该有calculate_position_size方法"
        
        # 测试初始化调用
        try:
            self.strategy.initialize_stock_master()
            print(f"✅ Stock master初始化成功，获取到 {len(self.strategy.stock_master)} 只股票")
        except Exception as e:
            print(f"⚠️ Stock master初始化失败（预期）: {e}")
    
    def test_position_size_round_logic_detailed(self):
        """详细测试持仓数量的round逻辑"""
        symbol = self.test_symbol
        
        # Mock stock_master数据
        mock_stock_data = {
            symbol: {
                'basePrice10': 0,  # 将在测试中修改
                'market_cap': 200_000_000_000,
                'calcSharesOutstanding': 1000000
            }
        }
        
        # Mock get_stockmaster函数
        original_get_stockmaster = None
        try:
            import stock_master
            original_get_stockmaster = stock_master.get_stockmaster
            stock_master.get_stockmaster = lambda: mock_stock_data
        except ImportError:
            self.strategy.stock_master = mock_stock_data
        
        try:
            # 初始化stock_master
            self.strategy.initialize_stock_master()
            
            # 测试各种round情况
            test_cases = [
                # (basePrice10, expected_position, description)
                (1000, 10000, "100日元: 1000_000/100/100=100, round(100)=100, 100*100=10000"),  # 100日元
                (1500, 6700, "150日元: 1000_000/150/100=66.67, round(66.67)=67, 67*100=6700"),   # 150日元
                (2000, 5000, "200日元: 1000_000/200/100=50, round(50)=50, 50*100=5000"),         # 200日元
                (2500, 4000, "250日元: 1000_000/250/100=40, round(40)=40, 40*100=4000"),         # 250日元
                (3333, 3000, "333.3日元: 1000_000/333.3/100=30.003, round(30.003)=30, 30*100=3000"), # 333.3日元
                (5000, 2000, "500日元: 1000_000/500/100=20, round(20)=20, 20*100=2000"),         # 500日元
                (10000, 1000, "1000日元: 1000_000/1000/100=10, round(10)=10, 10*100=1000"),      # 1000日元
                (500000, 100, "50000日元: 1000_000/50000/100=0.2, round(2)=2, 2*100=200") # 50000日元
            ]
            
            for base_price, expected_position, description in test_cases:
                mock_stock_data[symbol]['basePrice10'] = base_price
                position_size = self.strategy.calculate_position_size(symbol)
                assert position_size == expected_position, f"{description}，实际得到{position_size}"
                print(f"✅ {description} -> {position_size}")
            
        finally:
            # 恢复原始函数
            if original_get_stockmaster:
                stock_master.get_stockmaster = original_get_stockmaster 


def run_context_based_tests(test_class):
    """运行基于 Context 的测试"""
    # 创建测试套件
    test_suite = unittest.TestSuite()
    
    # 添加测试类
    tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
    test_suite.addTests(tests)
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # 生成测试报告
    print(f"\n=== 测试结果汇总 ===")
    print(f"运行测试数: {result.testsRun}")
    print(f"失败测试数: {len(result.failures)}")
    print(f"错误测试数: {len(result.errors)}")
    
    if result.failures:
        print(f"\n失败测试:")
        for test, traceback in result.failures:
            print(f"  {test}: {traceback}")
    
    if result.errors:
        print(f"\n错误测试:")
        for test, traceback in result.errors:
            print(f"  {test}: {traceback}")
    
    return result 