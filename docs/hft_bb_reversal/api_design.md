# API设计

## 新增数据结构

### TriggerLevels

```python
@dataclass
class TriggerLevels:
    """触发价格水平"""
    upper_trigger: float    # 上轨触发价格
    upper_limit: float      # 上轨限价价格
    lower_trigger: float    # 下轨触发价格
    lower_limit: float      # 下轨限价价格
```

## 扩展的StockContext字段

```python
# 在 IntradayStrategyBase.StockContext 中添加
trigger_levels: Optional[TriggerLevels] = None  # 触发价格水平
can_trade: bool = False                          # X条件满足标志
bb_levels: Optional[dict] = None                 # 布林带水平
```

## 新增方法

### 1. 触发价格计算

```python
def _calculate_trigger_levels(self, bb_levels: dict) -> TriggerLevels:
    """
    计算触发价格水平
    
    Args:
        bb_levels: 布林带水平字典
        
    Returns:
        TriggerLevels: 触发价格水平对象
    """
    pass
```

### 2. 入场逻辑检查

```python
def _check_entry_logic(self, symbol: str, tick: TickData, context: StockContext):
    """
    检查入场逻辑
    
    Args:
        symbol: 股票代码
        tick: Tick数据
        context: 股票上下文
    """
    pass
```

### 3. 入场订单发送

```python
def _send_entry_order(self, symbol: str, direction: Direction, price: float, quantity: int):
    """
    发送入场订单
    
    Args:
        symbol: 股票代码
        direction: 交易方向 (LONG/SHORT)
        price: 订单价格
        quantity: 订单数量
        
    Returns:
        str: 订单ID，失败返回None
    """
    pass
```

### 4. 出场订单发送

```python
def _send_exit_order(self, symbol: str, context: StockContext, bb_levels: dict):
    """
    发送出场订单
    
    Args:
        symbol: 股票代码
        context: 股票上下文
        bb_levels: 布林带水平
    """
    pass
```

### 5. 入场订单取消

```python
def _cancel_entry_order(self, symbol: str, context: StockContext):
    """
    取消入场订单
    
    Args:
        symbol: 股票代码
        context: 股票上下文
    """
    pass
```

### 6. 出场订单管理

```python
def _manage_exit_order(self, symbol: str, bb_levels: dict):
    """
    管理出场订单
    
    Args:
        symbol: 股票代码
        bb_levels: 布林带水平
    """
    pass
```

### 7. 订单成交处理

```python
def _handle_entry_filled(self, symbol: str, context: StockContext, order: OrderData):
    """
    处理入场订单成交
    
    Args:
        symbol: 股票代码
        context: 股票上下文
        order: 订单数据
    """
    pass

def _handle_exit_filled(self, symbol: str, context: StockContext, order: OrderData):
    """
    处理出场订单成交
    
    Args:
        symbol: 股票代码
        context: 股票上下文
        order: 订单数据
    """
    pass
```

### 8. 上下文查找

```python
def _find_context_by_order_id(self, order_id: str) -> tuple:
    """
    根据订单ID查找对应的股票和context
    
    Args:
        order_id: 订单ID
        
    Returns:
        tuple: (symbol, context) 或 (None, None)
    """
    pass
```

### 9. 状态查询

```python
def get_stock_state(self, symbol: str) -> StrategyState:
    """
    获取股票当前状态
    
    Args:
        symbol: 股票代码
        
    Returns:
        StrategyState: 策略状态枚举
            - StrategyState.IDLE: 空闲状态
            - StrategyState.WAITING_ENTRY: 等待入场
            - StrategyState.HOLDING: 持仓中
            - StrategyState.WAITING_EXIT: 等待出场
            - StrategyState.WAITING_TIMEOUT_EXIT: 等待超时出场
    """
    pass
```

## 修改的现有方法

### 1. on_1min_bar

```python
def on_1min_bar(self, bar: BarData):
    """
    1分钟K线回调函数 - 修改版本
    
    新增逻辑：
    1. 计算并更新触发价格水平
    2. 检查X条件并更新交易标志
    3. 管理出场订单
    """
    # 原有逻辑保持不变
    # 新增逻辑...
```

### 2. on_tick

```python
def on_tick(self, event):
    """
    Tick数据回调函数 - 修改版本
    
    新增逻辑：
    1. 检查X条件
    2. 执行入场逻辑检查
    """
    # 原有逻辑保持不变
    # 新增逻辑...
```

### 3. on_order

```python
def on_order(self, event):
    """
    订单回调函数 - 修改版本
    
    新增逻辑：
    1. 只处理ALLTRADED状态
    2. 区分入场和出场订单处理
    """
    # 原有逻辑保持不变
    # 新增逻辑...
```

## 复用的Base Strategy方法

### 订单管理方法

```python
# 复用以下方法，无需重新实现
self.send_order()           # 发送订单
self.cancel_order()         # 取消订单
self._update_simulated_positions()  # 更新模拟持仓
```

### 状态管理方法

```python
# 复用以下方法，无需重新实现
self.contexts[symbol]       # 获取股票上下文
self.write_log()            # 记录日志
```

### Bar生成方法

```python
# 复用以下方法，无需重新实现
self.bar_generators[symbol].update_tick(tick)  # 更新Bar数据
```

## 配置参数

### 新增参数

```python
# 在 __init__ 方法中添加
self.x_condition_enabled: bool = True                    # X条件启用标志
self.x_condition_time_windows: List[Tuple[time, time]] = [  # X条件时间窗口
    (time(9, 15), time(9, 35)),
    (time(11, 29), time(11, 30)),
    (time(14, 35), time(15, 20))
]
```

## 错误处理

### 异常类型

```python
class TriggerLevelsError(Exception):
    """触发价格计算错误"""
    pass

class OrderManagementError(Exception):
    """订单管理错误"""
    pass

class StateInconsistencyError(Exception):
    """状态不一致错误"""
    pass
```

### 错误处理策略

1. **订单发送失败**：记录错误日志，不更新状态
2. **订单取消失败**：记录警告日志，继续执行
3. **数据缺失**：跳过处理，等待下次更新
4. **状态不一致**：通过订单ID查找和验证状态