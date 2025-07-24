# 基于 Context 的策略测试设计文档

## 概述

本文档描述了基于 Context 的策略测试设计，该设计适用于所有继承 `IntradayStrategyBase` 的策略。通过将策略状态完全内化到 Context 中，我们可以通过设定 Context snapshot 和模拟外部输入来对策略状态机进行精确测试。

## 1. 测试架构设计

### 1.1 核心设计理念

#### **状态完全内化**
```python
# 所有策略状态都保存在 Context 中
@dataclass
class StockContext:
    symbol: str
    state: StrategyState = StrategyState.IDLE
    trade_count: int = 0
    entry_order_id: str = ""
    exit_order_id: str = ""
    entry_price: float = 0.0
    entry_time: datetime = None
    exit_start_time: datetime = None
    max_exit_wait_time: timedelta = timedelta(minutes=5)
    position_size: int = 100
    # 策略可以扩展更多字段
    strategy_specific_data: dict = field(default_factory=dict)
```

#### **外部输入明确**
```python
# 外部输入只有三种类型
def on_order(self, order: OrderData):  # 订单状态变化
def on_trade(self, trade: TradeData):  # 成交事件
def on_1min_bar(self, bar):           # K线数据更新
```

#### **状态转换可预测**
```python
# 每个状态转换都有明确的触发条件和结果
def _handle_entry_order_update(self, order: OrderData, context: StockContext):
    if order.status == Status.ALLTRADED:
        context.trade_count += 1
        self.update_context_state(context.symbol, StrategyState.HOLDING)
```

### 1.2 测试架构优势

#### **确定性测试**
- ✅ 所有状态都在 Context 中，可以精确控制
- ✅ 外部输入明确，可以精确模拟
- ✅ 状态转换可预测，可以精确验证

#### **隔离性测试**
- ✅ 每个 Context 独立，可以单独测试
- ✅ 不依赖外部系统，可以离线测试
- ✅ 不依赖真实数据，可以快速测试

#### **可重复性测试**
- ✅ 相同的输入产生相同的结果
- ✅ 可以精确重现问题场景
- ✅ 可以自动化回归测试

#### **全面性测试**
- ✅ 可以测试所有状态转换路径
- ✅ 可以测试所有边界条件
- ✅ 可以测试所有异常情况

## 2. 测试工具设计

### 2.1 Context Snapshot 工具

```python
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Any
import json

@dataclass
class ContextSnapshot:
    """Context 快照工具"""
    description: str
    contexts: Dict[str, Dict[str, Any]]
    timestamp: datetime
    metadata: Dict[str, Any] = None

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
```

### 2.2 模拟数据生成器

```python
from datetime import datetime, timedelta
from vnpy.trader.constant import Direction, Offset, Status, OrderType, Exchange
from vnpy.trader.object import OrderData, TradeData, BarData, Interval
import time

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
            datetime=datetime.now()
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
            type=OrderType.LIMIT,
            volume=volume,
            price=price,
            datetime=datetime.now()
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
            close_price=close_price
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
```

### 2.3 策略测试基类

```python
from abc import ABC, abstractmethod
from typing import Type, Dict, Any

class StrategyTestBase(ABC):
    """策略测试基类"""
    
    def __init__(self, strategy_class: Type, strategy_params: Dict[str, Any] = None):
        self.strategy_class = strategy_class
        self.strategy_params = strategy_params or {}
        self.strategy = None
        self.snapshot_manager = None
        self.mock_generator = MockDataGenerator()
    
    def setup_strategy(self):
        """设置策略实例"""
        self.strategy = self.strategy_class(**self.strategy_params)
        self.snapshot_manager = ContextSnapshotManager(self.strategy)
        self._setup_mock_indicators()
    
    def _setup_mock_indicators(self):
        """设置模拟技术指标"""
        # 子类可以重写这个方法来自定义技术指标设置
        pass
    
    def get_mock_indicators(self, symbol: str) -> dict:
        """获取模拟技术指标"""
        # 子类可以重写这个方法来自定义技术指标逻辑
        return self.mock_generator.create_mock_indicators()
    
    def setup_context(self, symbol: str, **kwargs):
        """设置 Context 初始状态"""
        context = self.strategy.get_context(symbol)
        for key, value in kwargs.items():
            if hasattr(context, key):
                setattr(context, key, value)
        return context
    
    def trigger_order_update(self, order: OrderData):
        """触发订单更新"""
        self.strategy.on_order(order)
    
    def trigger_trade(self, trade: TradeData):
        """触发成交事件"""
        self.strategy.on_trade(trade)
    
    def trigger_bar_update(self, bar: BarData):
        """触发K线更新"""
        # 模拟技术指标
        indicators = self.get_mock_indicators(bar.symbol)
        # 调用策略的 on_1min_bar 方法
        self.strategy.on_1min_bar(bar)
    
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
    
    @abstractmethod
    def test_basic_state_transitions(self):
        """测试基本状态转换"""
        pass
    
    @abstractmethod
    def test_edge_cases(self):
        """测试边界条件"""
        pass
    
    @abstractmethod
    def test_error_conditions(self):
        """测试错误条件"""
        pass
```

## 3. 测试用例设计

### 3.1 通用测试用例

#### **基本状态转换测试**
```python
class BasicStateTransitionTest(StrategyTestBase):
    """基本状态转换测试"""
    
    def test_idle_to_waiting_entry(self):
        """测试 IDLE -> WAITING_ENTRY 转换"""
        self.setup_strategy()
        symbol = "AAPL"
        
        # 设置初始状态
        self.setup_context(symbol, state=StrategyState.IDLE, trade_count=0)
        
        # 拍摄初始快照
        self.snapshot_manager.take_snapshot("Initial state")
        
        # 触发 entry 信号（通过 bar 更新）
        bar = self.mock_generator.create_mock_bar(symbol)
        self.trigger_bar_update(bar)
        
        # 拍摄快照并验证状态转换
        self.snapshot_manager.take_snapshot("After entry signal")
        self.snapshot_manager.assert_state_transition(symbol, "idle", "waiting_entry")
    
    def test_waiting_entry_to_holding(self):
        """测试 WAITING_ENTRY -> HOLDING 转换"""
        self.setup_strategy()
        symbol = "AAPL"
        
        # 设置初始状态
        context = self.setup_context(symbol, state=StrategyState.WAITING_ENTRY)
        context.entry_order_id = "mock_entry_order"
        
        # 拍摄初始快照
        self.snapshot_manager.take_snapshot("Initial state")
        
        # 触发 entry 订单成交
        order = self.mock_generator.create_mock_order(symbol, Status.ALLTRADED, "mock_entry_order")
        self.trigger_order_update(order)
        
        # 拍摄快照并验证状态转换
        self.snapshot_manager.take_snapshot("After entry order completed")
        self.snapshot_manager.assert_state_transition(symbol, "waiting_entry", "holding")
    
    def test_holding_to_waiting_exit(self):
        """测试 HOLDING -> WAITING_EXIT 转换"""
        self.setup_strategy()
        symbol = "AAPL"
        
        # 设置初始状态
        context = self.setup_context(symbol, state=StrategyState.HOLDING)
        context.entry_price = 100.0
        
        # 拍摄初始快照
        self.snapshot_manager.take_snapshot("Initial state")
        
        # 触发 exit 信号生成
        bar = self.mock_generator.create_mock_bar(symbol)
        self.trigger_bar_update(bar)
        
        # 拍摄快照并验证状态转换
        self.snapshot_manager.take_snapshot("After exit signal")
        self.snapshot_manager.assert_state_transition(symbol, "holding", "waiting_exit")
    
    def test_waiting_exit_to_idle(self):
        """测试 WAITING_EXIT -> IDLE 转换"""
        self.setup_strategy()
        symbol = "AAPL"
        
        # 设置初始状态
        context = self.setup_context(symbol, state=StrategyState.WAITING_EXIT)
        context.exit_order_id = "mock_exit_order"
        context.trade_count = 0
        
        # 拍摄初始快照
        self.snapshot_manager.take_snapshot("Initial state")
        
        # 触发 exit 订单成交
        order = self.mock_generator.create_mock_order(symbol, Status.ALLTRADED, "mock_exit_order")
        self.trigger_order_update(order)
        
        # 拍摄快照并验证状态转换
        self.snapshot_manager.take_snapshot("After exit order completed")
        self.snapshot_manager.assert_state_transition(symbol, "waiting_exit", "idle")
        self.snapshot_manager.assert_context_field(symbol, "trade_count", 1)
```

#### **边界条件测试**
```python
class EdgeCaseTest(StrategyTestBase):
    """边界条件测试"""
    
    def test_trade_count_limit(self):
        """测试交易次数限制"""
        self.setup_strategy()
        symbol = "AAPL"
        
        # 设置已达到最大交易次数
        self.setup_context(symbol, trade_count=3, state=StrategyState.IDLE)
        
        # 尝试生成新信号
        bar = self.mock_generator.create_mock_bar(symbol)
        self.trigger_bar_update(bar)
        
        # 验证状态没有变化
        self.assert_context_state(symbol, "idle")
        self.assert_context_field(symbol, "trade_count", 3)
    
    def test_order_rejection(self):
        """测试订单被拒绝"""
        self.setup_strategy()
        symbol = "AAPL"
        
        # 设置等待 entry 状态
        context = self.setup_context(symbol, state=StrategyState.WAITING_ENTRY)
        context.entry_order_id = "mock_entry_order"
        
        # 触发订单被拒绝
        order = self.mock_generator.create_mock_order(symbol, Status.REJECTED, "mock_entry_order")
        self.trigger_order_update(order)
        
        # 验证回到 IDLE 状态
        self.assert_context_state(symbol, "idle")
        self.assert_context_field(symbol, "entry_order_id", "")
    
    def test_exit_timeout(self):
        """测试 exit 订单超时"""
        self.setup_strategy()
        symbol = "AAPL"
        
        # 设置等待 exit 状态，并设置超时时间
        context = self.setup_context(symbol, state=StrategyState.WAITING_EXIT)
        context.exit_order_id = "mock_exit_order"
        context.exit_start_time = datetime.now() - timedelta(minutes=10)  # 超时
        
        # 触发超时检查
        bar = self.mock_generator.create_mock_bar(symbol)
        self.trigger_bar_update(bar)
        
        # 验证状态转换（应该生成市价单）
        # 注意：这里需要模拟市价单的生成逻辑
        pass
```

#### **完整流程测试**
```python
class CompleteFlowTest(StrategyTestBase):
    """完整流程测试"""
    
    def test_complete_trading_cycle(self):
        """测试完整的交易周期"""
        self.setup_strategy()
        symbol = "AAPL"
        
        # 1. 初始状态
        self.setup_context(symbol, state=StrategyState.IDLE, trade_count=0)
        self.snapshot_manager.take_snapshot("Initial state")
        
        # 2. 生成 entry 信号
        bar = self.mock_generator.create_mock_bar(symbol)
        self.trigger_bar_update(bar)
        self.snapshot_manager.take_snapshot("After entry signal")
        
        # 3. entry 订单成交
        context = self.strategy.get_context(symbol)
        entry_order = self.mock_generator.create_mock_order(
            symbol, Status.ALLTRADED, context.entry_order_id
        )
        self.trigger_order_update(entry_order)
        self.snapshot_manager.take_snapshot("After entry trade")
        
        # 4. exit 订单成交
        context = self.strategy.get_context(symbol)
        exit_order = self.mock_generator.create_mock_order(
            symbol, Status.ALLTRADED, context.exit_order_id
        )
        self.trigger_order_update(exit_order)
        self.snapshot_manager.take_snapshot("After exit trade")
        
        # 5. 验证最终状态
        self.assert_context_state(symbol, "idle")
        self.assert_context_field(symbol, "trade_count", 1)
        
        # 6. 验证状态转换序列
        self.snapshot_manager.assert_state_transition(symbol, "idle", "waiting_entry", 1)
        self.snapshot_manager.assert_state_transition(symbol, "waiting_entry", "holding", 2)
        self.snapshot_manager.assert_state_transition(symbol, "holding", "waiting_exit", 3)
        self.snapshot_manager.assert_state_transition(symbol, "waiting_exit", "idle", 4)
```

## 4. 特定策略测试

### 4.1 VWAP Failure 策略测试

```python
class VWAPFailureStrategyTest(StrategyTestBase):
    """VWAP Failure 策略测试"""
    
    def __init__(self):
        super().__init__(VWAPFailureStrategy)
    
    def _setup_mock_indicators(self):
        """设置 VWAP Failure 策略特定的技术指标"""
        # 可以在这里设置策略特定的技术指标逻辑
        pass
    
    def get_mock_indicators(self, symbol: str) -> dict:
        """获取 VWAP Failure 策略特定的技术指标"""
        # 根据 gap 方向返回不同的指标
        gap_direction = getattr(self.strategy, 'gap_direction', {}).get(symbol, 'none')
        
        if gap_direction == 'up':
            return self.mock_generator.create_mock_indicators(
                vwap=100.0, atr_14=1.0, below_vwap_count=3
            )
        elif gap_direction == 'down':
            return self.mock_generator.create_mock_indicators(
                vwap=100.0, atr_14=1.0, above_vwap_count=3
            )
        else:
            return self.mock_generator.create_mock_indicators(
                vwap=100.0, atr_14=1.0, below_vwap_count=0, above_vwap_count=0
            )
    
    def test_gap_up_strategy(self):
        """测试 Gap Up 策略"""
        self.setup_strategy()
        symbol = "AAPL"
        
        # 设置 gap up 条件
        self.strategy.gap_direction[symbol] = 'up'
        self.strategy.eligible_stocks.add(symbol)
        
        # 设置初始状态
        self.setup_context(symbol, state=StrategyState.IDLE, trade_count=0)
        
        # 触发信号生成
        bar = self.mock_generator.create_mock_bar(symbol)
        self.trigger_bar_update(bar)
        
        # 验证生成了做空订单
        context = self.strategy.get_context(symbol)
        assert context.entry_order_id != ""
        self.assert_context_state(symbol, "waiting_entry")
    
    def test_gap_down_strategy(self):
        """测试 Gap Down 策略"""
        self.setup_strategy()
        symbol = "AAPL"
        
        # 设置 gap down 条件
        self.strategy.gap_direction[symbol] = 'down'
        self.strategy.eligible_stocks.add(symbol)
        
        # 设置初始状态
        self.setup_context(symbol, state=StrategyState.IDLE, trade_count=0)
        
        # 触发信号生成
        bar = self.mock_generator.create_mock_bar(symbol)
        self.trigger_bar_update(bar)
        
        # 验证生成了做多订单
        context = self.strategy.get_context(symbol)
        assert context.entry_order_id != ""
        self.assert_context_state(symbol, "waiting_entry")
```

## 5. 测试执行和报告

### 5.1 测试执行器

```python
class StrategyTestRunner:
    """策略测试执行器"""
    
    def __init__(self):
        self.test_results = []
    
    def run_test_suite(self, test_class: Type[StrategyTestBase]):
        """运行测试套件"""
        test_instance = test_class()
        
        # 获取所有测试方法
        test_methods = [method for method in dir(test_instance) 
                       if method.startswith('test_')]
        
        for method_name in test_methods:
            try:
                # 运行测试方法
                method = getattr(test_instance, method_name)
                method()
                
                # 记录成功结果
                self.test_results.append({
                    'test_class': test_class.__name__,
                    'test_method': method_name,
                    'status': 'PASSED',
                    'error': None
                })
                
                print(f"✓ {test_class.__name__}.{method_name} PASSED")
                
            except Exception as e:
                # 记录失败结果
                self.test_results.append({
                    'test_class': test_class.__name__,
                    'test_method': method_name,
                    'status': 'FAILED',
                    'error': str(e)
                })
                
                print(f"✗ {test_class.__name__}.{method_name} FAILED: {e}")
    
    def generate_report(self, output_file: str = None):
        """生成测试报告"""
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r['status'] == 'PASSED'])
        failed_tests = total_tests - passed_tests
        
        report = {
            'summary': {
                'total_tests': total_tests,
                'passed_tests': passed_tests,
                'failed_tests': failed_tests,
                'success_rate': passed_tests / total_tests if total_tests > 0 else 0
            },
            'results': self.test_results
        }
        
        if output_file:
            with open(output_file, 'w') as f:
                json.dump(report, f, indent=2)
        
        return report
```

### 5.2 使用示例

```python
def main():
    """主函数 - 运行所有测试"""
    runner = StrategyTestRunner()
    
    # 运行基本状态转换测试
    runner.run_test_suite(BasicStateTransitionTest)
    
    # 运行边界条件测试
    runner.run_test_suite(EdgeCaseTest)
    
    # 运行完整流程测试
    runner.run_test_suite(CompleteFlowTest)
    
    # 运行特定策略测试
    runner.run_test_suite(VWAPFailureStrategyTest)
    
    # 生成测试报告
    report = runner.generate_report("test_report.json")
    
    print(f"\n测试完成:")
    print(f"总测试数: {report['summary']['total_tests']}")
    print(f"通过测试: {report['summary']['passed_tests']}")
    print(f"失败测试: {report['summary']['failed_tests']}")
    print(f"成功率: {report['summary']['success_rate']:.2%}")

if __name__ == "__main__":
    main()
```

## 6. 最佳实践

### 6.1 测试设计原则

#### **单一职责原则**
- 每个测试方法只测试一个特定的功能或状态转换
- 测试方法名称应该清楚地描述测试的内容

#### **可重复性原则**
- 每个测试都应该是独立的，不依赖其他测试的结果
- 测试应该能够重复运行并产生相同的结果

#### **可维护性原则**
- 使用通用的测试工具和基类，减少重复代码
- 将测试数据和测试逻辑分离

### 6.2 测试数据管理

#### **测试数据隔离**
- 每个测试使用独立的测试数据
- 避免测试之间的数据污染

#### **测试数据可配置**
- 测试数据应该可以通过参数配置
- 支持不同的测试场景

### 6.3 测试覆盖率

#### **状态转换覆盖率**
- 测试所有可能的状态转换路径
- 测试所有边界条件和异常情况

#### **业务逻辑覆盖率**
- 测试所有业务规则和约束
- 测试所有策略特定的逻辑

## 7. 总结

基于 Context 的测试设计提供了以下核心优势：

1. **确定性测试**：所有状态都在 Context 中，可以精确控制和验证
2. **隔离性测试**：每个 Context 独立，可以单独测试
3. **可重复性测试**：相同的输入产生相同的结果
4. **全面性测试**：可以测试所有状态转换路径和边界条件
5. **可扩展性**：适用于所有继承 `IntradayStrategyBase` 的策略

这种设计使得策略状态机的测试变得简单、可靠和全面，是现代软件工程中"可测试性"设计原则的完美体现。 