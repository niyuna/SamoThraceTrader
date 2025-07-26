# 基于Polling的订单状态更新机制实现

## 概述

本文档描述了在BriskGateway中实现的基于轮询的订单状态更新机制，该机制通过定期调用 `kabus_api.query_orders_after()` 来获取订单状态变化，并维护本地缓存以检测状态变化并推送事件。

## 实现架构

### 1. 核心组件

#### 1.1 订单缓存管理
```python
# 本地订单缓存
self.local_orders: Dict[str, OrderData] = {}  # key: orderid (ID字段)

# 轮询时间管理
# 设置初始时间为当天的早上8点50分，确保获取当天所有订单
today = datetime.now()
self.last_updtime: str = today.strftime("%Y%m%d") + "085000"  # 格式: yyyyMMddHHmmss
self.polling_interval: int = 1  # 轮询间隔（秒）
self._polling_active: bool = False
```

#### 1.2 轮询线程
```python
def _start_polling_thread(self):
    """启动订单状态轮询线程"""
    self._polling_active = True
    self._polling_thread = threading.Thread(target=self._run_polling)
    self._polling_thread.daemon = True
    self._polling_thread.start()

def _run_polling(self):
    """运行订单状态轮询"""
    while self._polling_active:
        try:
            self._poll_orders()
            time.sleep(self.polling_interval)
        except Exception as e:
            self.write_log(f"订单轮询错误: {e}")
            time.sleep(self.polling_interval)
```

### 2. 轮询逻辑

#### 2.1 主要轮询流程
```python
def _poll_orders(self):
    """轮询订单状态"""
    # 1. 记录当前时间作为本次查询的updtime
    current_time = datetime.now().strftime("%Y%m%d%H%M%S")
    
    # 2. 拉取所有 self.last_updtime 之后的订单
    orders = kabus_api.query_orders_after(self.last_updtime)
    if not orders:
        # 即使没有订单，也要更新时间，避免重复查询
        self.last_updtime = current_time
        return

    # 3. 遍历订单，转换格式，检测状态变化
    for broker_order in orders:
        order = self._convert_broker_order_to_vnpy(broker_order)
        orderid = order.orderid  # 使用broker_order['ID']
        old_order = self.local_orders.get(orderid)
        
        # 检测状态变化：状态不同 或 成交量不同
        if (not old_order) or (old_order.status != order.status or old_order.traded != order.traded):
            self.local_orders[orderid] = order
            self.on_order(order)  # 推送事件
            self.write_log(f"订单状态更新: {orderid} {old_order.status if old_order else 'NEW'} -> {order.status}")

    # 4. 更新last_updtime为当前时间
    self.last_updtime = current_time
```

### 3. 数据格式转换

#### 3.1 状态映射（暂时假设）
```python
# 状态映射 (基于broker_order['State']和['OrderState'])
state_mapping = {
    1: Status.SUBMITTING,    # 假设1=提交中
    2: Status.NOTTRADED,     # 假设2=未成交
    3: Status.ALLTRADED,     # 假设3=全部成交
    4: Status.CANCELLED,     # 假设4=已撤销
    5: Status.REJECTED,      # 假设5=已拒绝
}

# 方向映射 (基于broker_order['Side'])
direction_mapping = {
    "1": Direction.SHORT,    # 1=卖出
    "2": Direction.LONG,     # 2=买入
}

# 订单类型映射 (基于broker_order['OrdType'])
order_type_mapping = {
    1: OrderType.MARKET,     # 假设1=市价单
    2: OrderType.LIMIT,      # 假设2=限价单
}
```

#### 3.2 转换函数
```python
def _convert_broker_order_to_vnpy(self, broker_order: Dict) -> OrderData:
    """将kabus API订单格式转换为vnpy格式"""
    
    # 解析时间
    recv_time = broker_order["RecvTime"]
    if "+09:00" in recv_time:
        dt = datetime.fromisoformat(recv_time.replace("+09:00", "+09:00"))
    else:
        dt = datetime.fromisoformat(recv_time)
    
    order = OrderData(
        gateway_name=self.gateway_name,
        symbol=broker_order["Symbol"],
        exchange=exchange_mapping.get(broker_order["Exchange"], Exchange.TSE),
        orderid=broker_order["ID"],  # 直接使用ID字段
        type=order_type_mapping.get(broker_order["OrdType"], OrderType.LIMIT),
        direction=direction_mapping.get(broker_order["Side"], Direction.LONG),
        offset=Offset.NONE,  # 暂时设为NONE，后续可根据CashMargin和DelivType判断
        price=float(broker_order["Price"]),
        volume=float(broker_order["OrderQty"]),
        traded=float(broker_order["CumQty"]),  # 累计成交量
        status=state_mapping.get(broker_order["State"], Status.SUBMITTING),
        datetime=dt,
        reference=""
    )
    
    return order
```

### 4. 订单发送集成

#### 4.1 发送订单时添加到缓存
```python
def send_order(self, req: OrderRequest) -> str:
    # ... 发送订单逻辑 ...
    
    # 创建初始订单对象并添加到本地缓存
    if order_id:
        initial_order = OrderData(
            gateway_name=self.gateway_name,
            symbol=req.symbol,
            exchange=req.exchange,
            orderid=order_id,
            type=req.type,
            direction=req.direction,
            offset=req.offset,
            price=req.price,
            volume=req.volume,
            traded=0.0,  # 初始成交量为0
            status=Status.SUBMITTING,  # 初始状态为提交中
            datetime=datetime.now(),
            reference=req.reference
        )
        self.add_order(initial_order)
        self.write_log(f"订单已发送并添加到缓存: {order_id}")
    
    return order_id
```

## 配置选项

### Gateway设置
```python
default_setting: Dict[str, str | int | float | bool] = {
    "tick_server_url": "ws://127.0.0.1:8001/ws",
    "tick_server_http_url": "http://127.0.0.1:8001",
    "reconnect_interval": 5,
    "heartbeat_interval": 30,
    "max_reconnect_attempts": 10,
    "polling_interval": 1,  # 订单状态轮询间隔（秒）
}
```

## 使用示例

### 1. 基本使用
```python
from vnpy.event import EventEngine
from brisk_gateway import BriskGateway

# 创建事件引擎和gateway
event_engine = EventEngine()
gateway = BriskGateway(event_engine, "BRISK")

# 连接设置
setting = {
    "polling_interval": 2,  # 2秒轮询一次
}

# 连接gateway
gateway.connect(setting)
```

### 2. 测试脚本
```python
# 运行测试脚本
python test_polling_mechanism.py
```

## 关键特性

### 1. 时间管理
- **初始时间**：设置为当天的早上8点50分（`"yyyyMMdd085000"`），确保获取当天所有订单
- **更新时间**：使用API调用前的当前时间，确保不遗漏订单
- **格式统一**：与kabus_api中的时间格式保持一致

### 2. 状态变化检测
- **状态变化**：`old_order.status != order.status`
- **成交量变化**：`old_order.traded != order.traded`
- **新订单**：`not old_order`

### 3. 事件推送
- 只有在检测到状态变化时才调用 `self.on_order(order)`
- 避免重复推送相同状态的订单

### 4. 错误处理
- 轮询线程异常时记录日志并继续运行
- 使用try-catch包装所有API调用

## 注意事项

### 1. 状态映射假设
当前使用的状态映射是基于假设的，需要根据实际的kabus API文档进行验证和调整：
- `State` 字段的具体含义
- `OrderState` 字段的具体含义
- `OrdType` 字段的具体含义

### 2. 性能考虑
- 轮询间隔不宜过短，避免API调用过于频繁
- 可以根据订单状态动态调整轮询频率
- 考虑添加批量查询优化

### 3. 数据一致性
- 确保本地缓存与券商数据的一致性
- 考虑添加数据校验机制
- 处理网络异常导致的数据不一致

## 后续优化方向

### 1. 智能轮询
- 根据订单状态调整轮询频率
- 未完成订单高频轮询，已完成订单低频轮询

### 2. 批量优化
- 如果API支持批量查询，优先使用批量接口
- 实现并发查询以提高效率

### 3. 状态映射完善
- 根据实际API文档完善状态映射
- 添加更详细的订单状态处理

### 4. 监控和日志
- 添加轮询性能监控
- 完善日志记录和错误追踪 