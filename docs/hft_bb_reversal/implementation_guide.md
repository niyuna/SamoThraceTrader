# 实现指南

## 实现步骤

### 步骤1: 添加数据结构

在 `hft_bb_reversal_strategy.py` 文件顶部添加：

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class TriggerLevels:
    """触发价格水平"""
    upper_trigger: float    # 上轨触发价格
    upper_limit: float      # 上轨限价价格
    lower_trigger: float    # 下轨触发价格
    lower_limit: float      # 下轨限价价格
```

### 步骤2: 扩展StockContext

在 `IntradayStrategyBase` 的 `StockContext` 类中添加字段：

```python
# 在 StockContext 类中添加
trigger_levels: Optional[TriggerLevels] = None  # 触发价格水平
can_trade: bool = False                          # X条件满足标志
bb_levels: Optional[dict] = None                 # 布林带水平
```

### 步骤3: 实现触发价格计算

```python
def _calculate_trigger_levels(self, bb_levels: dict) -> TriggerLevels:
    """计算触发价格水平"""
    try:
        upper_bb = bb_levels['upper']
        lower_bb = bb_levels['lower']
        middle_bb = bb_levels['middle']
        
        # 计算触发价格（可以根据策略需求调整）
        upper_trigger = upper_bb * 0.999  # 上轨触发价格
        upper_limit = upper_bb * 1.001    # 上轨限价价格
        lower_trigger = lower_bb * 1.001  # 下轨触发价格
        lower_limit = lower_bb * 0.999    # 下轨限价价格
        
        return TriggerLevels(
            upper_trigger=upper_trigger,
            upper_limit=upper_limit,
            lower_trigger=lower_trigger,
            lower_limit=lower_limit
        )
    except KeyError as e:
        self.write_log(f"计算触发价格失败: {e}")
        return None
```

### 步骤4: 修改on_1min_bar方法

```python
def on_1min_bar(self, bar: BarData):
    """1分钟K线回调函数"""
    symbol = bar.symbol
    context = self.contexts.get(symbol)
    
    if not context:
        return
    
    # 1. 更新技术指标和触发价格
    if symbol in self.indicator_managers:
        indicators = self.indicator_managers[symbol].update_bar(bar)
        bb_levels = self._calculate_bb_levels(symbol, indicators)
        
        if bb_levels:
            # 更新BB水平和触发价格
            context.bb_levels = bb_levels
            context.trigger_levels = self._calculate_trigger_levels(bb_levels)
            
            # 2. 检查X条件并更新交易标志
            context.can_trade = self.check_x_condition(symbol, bar.datetime)
            
            # 3. 如果有持仓，维护出场订单
            if context.position != 0:
                self._manage_exit_order(symbol, bb_levels)
    
    # 调用父类方法（保持原有逻辑）
    super().on_1min_bar(bar)
```

### 步骤5: 修改on_tick方法

```python
def on_tick(self, event):
    """Tick数据回调函数"""
    tick = event.data
    symbol = tick.symbol
    context = self.contexts.get(symbol)
    
    if not context or not context.trigger_levels:
        return
    
    # 1. 检查X条件是否满足
    if not context.can_trade:
        return
    
    # 2. 检查入场订单逻辑
    self._check_entry_logic(symbol, tick, context)
    
    # 调用父类方法（保持原有逻辑）
    super().on_tick(event)
```

### 步骤6: 实现入场逻辑检查

```python
def _check_entry_logic(self, symbol: str, tick: TickData, context: StockContext):
    """检查入场逻辑"""
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
        self._send_entry_order(symbol, order_direction, order_price, context.quantity)
```

### 步骤7: 实现订单发送方法

```python
def _send_entry_order(self, symbol: str, direction: Direction, price: float, quantity: int):
    """发送入场订单"""
    context = self.contexts[symbol]
    
    try:
        # 使用父类的send_order方法
        order_id = self.send_order(
            symbol=symbol,
            exchange=Exchange.TSE,
            direction=direction,
            offset=Offset.OPEN,
            type=OrderType.LIMIT,
            price=price,
            volume=quantity,
            reference=f"ENTRY_{symbol}_{direction.value}"
        )
        
        if order_id:
            context.entry_order_id = order_id
            context.entry_order_price = price
            # 更新状态为等待入场
            self.update_context_state(symbol, StrategyState.WAITING_ENTRY)
            self.write_log(f"发送入场订单: {symbol} {direction.value} 价格{price:.2f}")
        else:
            self.write_log(f"入场订单发送失败: {symbol}")
            
    except Exception as e:
        self.write_log(f"发送入场订单异常: {symbol} {e}")

def _send_exit_order(self, symbol: str, context: StockContext, bb_levels: dict):
    """发送出场订单"""
    try:
        if context.position > 0:  # 多头持仓
            direction = Direction.SHORT
            price = bb_levels['exit_long']
        else:  # 空头持仓
            direction = Direction.LONG
            price = bb_levels['exit_short']
        
        # 使用父类的send_order方法
        order_id = self.send_order(
            symbol=symbol,
            exchange=Exchange.TSE,
            direction=direction,
            offset=Offset.CLOSE,
            type=OrderType.LIMIT,
            price=price,
            volume=abs(context.position),
            reference=f"EXIT_{symbol}_{direction.value}"
        )
        
        if order_id:
            context.exit_order_id = order_id
            context.exit_order_price = price
            # 更新状态为等待出场
            self.update_context_state(symbol, StrategyState.WAITING_EXIT)
            self.write_log(f"发送出场订单: {symbol} {direction.value} 价格{price:.2f}")
        else:
            self.write_log(f"出场订单发送失败: {symbol}")
            
    except Exception as e:
        self.write_log(f"发送出场订单异常: {symbol} {e}")
```

### 步骤8: 实现订单取消方法

```python
def _cancel_entry_order(self, symbol: str, context: StockContext):
    """取消入场订单"""
    if context.entry_order_id:
        try:
            # 使用父类的cancel_order方法
            self.cancel_order(context.entry_order_id)
            context.entry_order_id = None
            context.entry_order_price = 0.0
            # 更新状态为空闲
            self.update_context_state(symbol, StrategyState.IDLE)
            self.write_log(f"取消入场订单: {symbol}")
        except Exception as e:
            self.write_log(f"取消入场订单异常: {symbol} {e}")
```

### 步骤9: 实现出场订单管理

```python
def _manage_exit_order(self, symbol: str, bb_levels: dict):
    """管理出场订单"""
    context = self.contexts[symbol]
    
    if context.position == 0:
        return  # 无持仓，不需要出场订单
    
    try:
        if context.exit_order_id:
            # 检查是否需要更新价格
            if context.position > 0:
                new_price = bb_levels['exit_long']
            else:
                new_price = bb_levels['exit_short']
            
            # 如果价格相同，不需要更新
            if context.exit_order_price == new_price:
                return
            
            # 取消旧订单，发送新订单
            self.cancel_order(context.exit_order_id)
            context.exit_order_id = None
            self._send_exit_order(symbol, context, bb_levels)
        else:
            # 创建新的出场订单
            self._send_exit_order(symbol, context, bb_levels)
            
    except Exception as e:
        self.write_log(f"管理出场订单异常: {symbol} {e}")
```

### 步骤10: 修改on_order方法

```python
def on_order(self, event):
    """订单回调函数"""
    order = event.data
    symbol, context = self._find_context_by_order_id(order.orderid)
    
    if not context:
        return
    
    # 只处理成交情况
    if order.status != Status.ALLTRADED:
        return
    
    try:
        if order.orderid == context.entry_order_id:
            # 入场订单成交
            self._handle_entry_filled(symbol, context, order)
        elif order.orderid == context.exit_order_id:
            # 出场订单成交
            self._handle_exit_filled(symbol, context, order)
    except Exception as e:
        self.write_log(f"处理订单成交异常: {symbol} {e}")
    
    # 调用父类方法（保持原有逻辑）
    super().on_order(event)
```

### 步骤11: 实现订单成交处理

```python
def _handle_entry_filled(self, symbol: str, context: StockContext, order: OrderData):
    """处理入场订单成交"""
    # 更新持仓
    if order.direction == Direction.LONG:
        context.position = order.traded_volume
    else:  # SHORT
        context.position = -order.traded_volume
    
    # 清除入场订单信息
    context.entry_order_id = None
    context.entry_order_price = 0.0
    
    # 更新状态为持仓中
    self.update_context_state(symbol, StrategyState.HOLDING)
    
    # 立即发送出场订单
    if context.bb_levels:
        self._send_exit_order(symbol, context, context.bb_levels)
    
    self.write_log(f"入场订单成交: {symbol} 持仓{context.position}")

def _handle_exit_filled(self, symbol: str, context: StockContext, order: OrderData):
    """处理出场订单成交"""
    # 清除持仓
    context.position = 0
    context.exit_order_id = None
    context.exit_order_price = 0.0
    
    # 更新状态为空闲
    self.update_context_state(symbol, StrategyState.IDLE)
    
    self.write_log(f"出场订单成交: {symbol} 持仓清零")
```

### 步骤12: 实现辅助方法

```python
def _find_context_by_order_id(self, order_id: str) -> tuple:
    """根据订单ID查找对应的股票和context"""
    for symbol, context in self.contexts.items():
        if context.entry_order_id == order_id or context.exit_order_id == order_id:
            return symbol, context
    return None, None

def get_stock_state(self, symbol: str) -> StrategyState:
    """获取股票当前状态"""
    context = self.contexts.get(symbol)
    if not context:
        return StrategyState.IDLE
    
    return context.state
```

## 测试验证

### 单元测试

创建测试文件 `test/test_hft_bb_reversal_implementation.py`：

```python
import unittest
from unittest.mock import Mock, patch
from datetime import datetime, time
from vnpy.trader.constant import Direction, Status, OrderType, Offset
from vnpy.trader.object import BarData, TickData, OrderData

class TestHFTBBReversalImplementation(unittest.TestCase):
    def setUp(self):
        # 设置测试环境
        pass
    
    def test_trigger_levels_calculation(self):
        """测试触发价格计算"""
        pass
    
    def test_entry_logic_check(self):
        """测试入场逻辑检查"""
        pass
    
    def test_exit_order_management(self):
        """测试出场订单管理"""
        pass
    
    def test_order_fill_handling(self):
        """测试订单成交处理"""
        pass

if __name__ == '__main__':
    unittest.main()
```

### 集成测试

1. **模拟数据测试**：使用历史数据验证策略逻辑
2. **实时数据测试**：在模拟环境中测试实时交易
3. **压力测试**：测试高频数据下的性能表现

## 部署注意事项

1. **配置检查**：确保所有配置参数正确设置
2. **数据源验证**：确保数据源稳定可靠
3. **风险控制**：设置合理的止损和仓位限制
4. **监控告警**：建立完善的监控和告警机制
5. **日志记录**：确保关键操作都有日志记录