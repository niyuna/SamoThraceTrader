# 券商API适配设计文档

## 问题描述

假设brisk对应的券商API只支持以下查询方式：
1. 通过 `orderId` 查询特定订单状态
2. 通过时间范围查询该时间之后的所有订单

而vnpy框架需要实时的事件驱动机制，包括：
- 订单状态变化的实时推送
- 成交回报的实时推送
- 持仓变化的实时推送

## 解决方案设计

### 1. 轮询 + 缓存机制

#### 1.1 核心思路
- 维护本地订单缓存，记录所有已发送订单的最新状态
- 定期轮询券商API，获取订单状态更新
- 比较本地缓存与券商返回的状态，检测变化并推送事件

#### 1.2 实现架构

```python
class BriskGateway(BaseGateway):
    def __init__(self, event_engine: EventEngine, gateway_name: str):
        super().__init__(event_engine, gateway_name)
        
        # 本地订单缓存
        self.local_orders: Dict[str, OrderData] = {}
        self.order_timestamps: Dict[str, datetime] = {}
        
        # 轮询配置
        self.polling_interval: int = 1  # 轮询间隔（秒）
        self.last_query_time: datetime = datetime.now()
        
        # 启动轮询线程
        self._start_polling_thread()
    
    def _start_polling_thread(self):
        """启动轮询线程"""
        def polling_worker():
            while True:
                try:
                    self._poll_orders()
                    time.sleep(self.polling_interval)
                except Exception as e:
                    self.write_log(f"Polling error: {e}")
        
        thread = Thread(target=polling_worker, daemon=True)
        thread.start()
```

### 2. 订单状态管理

#### 2.1 本地订单缓存

```python
class OrderCache:
    def __init__(self):
        self.orders: Dict[str, OrderData] = {}
        self.order_timestamps: Dict[str, datetime] = {}
        self.pending_orders: Set[str] = set()  # 等待确认的订单
    
    def add_order(self, order: OrderData):
        """添加新订单到缓存"""
        self.orders[order.vt_orderid] = order
        self.order_timestamps[order.vt_orderid] = datetime.now()
        if order.status == Status.SUBMITTING:
            self.pending_orders.add(order.vt_orderid)
    
    def update_order(self, order: OrderData):
        """更新订单状态"""
        old_order = self.orders.get(order.vt_orderid)
        if old_order and old_order.status != order.status:
            # 状态发生变化，需要推送事件
            return True
        self.orders[order.vt_orderid] = order
        return False
    
    def get_pending_orders(self) -> List[str]:
        """获取等待确认的订单ID列表"""
        return list(self.pending_orders)
    
    def get_orders_since(self, since_time: datetime) -> List[str]:
        """获取指定时间之后的订单ID列表"""
        return [
            orderid for orderid, timestamp in self.order_timestamps.items()
            if timestamp >= since_time
        ]
```

#### 2.2 轮询逻辑实现

```python
def _poll_orders(self):
    """轮询订单状态"""
    current_time = datetime.now()
    
    # 方法1：查询等待确认的订单
    pending_orders = self.order_cache.get_pending_orders()
    for orderid in pending_orders:
        self._query_single_order(orderid)
    
    # 方法2：查询时间范围内的所有订单
    orders_since = self.order_cache.get_orders_since(self.last_query_time)
    if orders_since:
        self._query_orders_by_time(self.last_query_time, current_time)
    
    self.last_query_time = current_time

def _query_single_order(self, orderid: str):
    """查询单个订单状态"""
    try:
        # 调用券商API查询订单状态
        broker_order = self.broker_api.query_order(orderid)
        
        # 转换为vnpy格式
        order = self._convert_broker_order_to_vnpy(broker_order)
        
        # 检查状态是否发生变化
        if self.order_cache.update_order(order):
            # 推送订单状态变化事件
            self.on_order(order)
            
    except Exception as e:
        self.write_log(f"Query order {orderid} failed: {e}")

def _query_orders_by_time(self, start_time: datetime, end_time: datetime):
    """查询时间范围内的订单"""
    try:
        # 调用券商API查询时间范围内的订单
        broker_orders = self.broker_api.query_orders_since(start_time)
        
        for broker_order in broker_orders:
            # 转换为vnpy格式
            order = self._convert_broker_order_to_vnpy(broker_order)
            
            # 检查状态是否发生变化
            if self.order_cache.update_order(order):
                # 推送订单状态变化事件
                self.on_order(order)
                
    except Exception as e:
        self.write_log(f"Query orders by time failed: {e}")
```

### 3. 券商API适配层

#### 3.1 券商API接口抽象

```python
class BrokerAPI:
    """券商API抽象接口"""
    
    def query_order(self, orderid: str) -> Dict:
        """查询单个订单状态"""
        raise NotImplementedError
    
    def query_orders_since(self, since_time: datetime) -> List[Dict]:
        """查询指定时间之后的订单"""
        raise NotImplementedError
    
    def send_order(self, order_request: Dict) -> str:
        """发送订单"""
        raise NotImplementedError
    
    def cancel_order(self, orderid: str) -> bool:
        """撤销订单"""
        raise NotImplementedError

class BriskBrokerAPI(BrokerAPI):
    """Brisk券商API实现"""
    
    def __init__(self, api_key: str, secret_key: str, endpoint: str):
        self.api_key = api_key
        self.secret_key = secret_key
        self.endpoint = endpoint
        self.session = requests.Session()
    
    def query_order(self, orderid: str) -> Dict:
        """查询单个订单状态"""
        url = f"{self.endpoint}/order/{orderid}"
        headers = self._get_auth_headers()
        
        response = self.session.get(url, headers=headers)
        response.raise_for_status()
        
        return response.json()
    
    def query_orders_since(self, since_time: datetime) -> List[Dict]:
        """查询指定时间之后的订单"""
        url = f"{self.endpoint}/orders"
        params = {
            "since": since_time.isoformat(),
            "limit": 100  # 限制返回数量
        }
        headers = self._get_auth_headers()
        
        response = self.session.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        return response.json()["orders"]
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """获取认证头"""
        # 实现具体的认证逻辑
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
```

#### 3.2 数据格式转换

```python
def _convert_broker_order_to_vnpy(self, broker_order: Dict) -> OrderData:
    """将券商订单格式转换为vnpy格式"""
    
    # 状态映射
    status_mapping = {
        "pending": Status.SUBMITTING,
        "submitted": Status.NOTTRADED,
        "partial_filled": Status.PARTTRADED,
        "filled": Status.ALLTRADED,
        "cancelled": Status.CANCELLED,
        "rejected": Status.REJECTED
    }
    
    # 方向映射
    direction_mapping = {
        "buy": Direction.LONG,
        "sell": Direction.SHORT
    }
    
    order = OrderData(
        gateway_name=self.gateway_name,
        symbol=broker_order["symbol"],
        exchange=Exchange.SSE,  # 根据实际情况设置
        orderid=broker_order["order_id"],
        type=OrderType.LIMIT,
        direction=direction_mapping.get(broker_order["side"], Direction.LONG),
        offset=Offset.NONE,
        price=float(broker_order["price"]),
        volume=float(broker_order["quantity"]),
        traded=float(broker_order.get("filled_quantity", 0)),
        status=status_mapping.get(broker_order["status"], Status.SUBMITTING),
        datetime=datetime.fromisoformat(broker_order["created_at"]),
        reference=broker_order.get("client_order_id", "")
    )
    
    return order
```

### 4. 优化策略

#### 4.1 智能轮询

```python
class SmartPollingManager:
    def __init__(self):
        self.polling_intervals = {
            "high_frequency": 0.5,    # 高频轮询（等待确认的订单）
            "normal": 2.0,            # 正常轮询
            "low_frequency": 10.0     # 低频轮询（已完成的订单）
        }
        self.order_priorities = {}  # 订单优先级
    
    def get_polling_interval(self, orderid: str) -> float:
        """根据订单状态获取轮询间隔"""
        order = self.get_order(orderid)
        if not order:
            return self.polling_intervals["normal"]
        
        if order.status in [Status.SUBMITTING, Status.NOTTRADED]:
            return self.polling_intervals["high_frequency"]
        elif order.status in [Status.PARTTRADED]:
            return self.polling_intervals["normal"]
        else:
            return self.polling_intervals["low_frequency"]
```

#### 4.2 批量查询优化

```python
def _batch_query_orders(self, orderids: List[str]) -> Dict[str, OrderData]:
    """批量查询订单状态"""
    if not orderids:
        return {}
    
    # 如果券商支持批量查询，优先使用
    if hasattr(self.broker_api, 'batch_query_orders'):
        return self._batch_query_via_api(orderids)
    
    # 否则使用并发查询
    return self._concurrent_query_orders(orderids)

def _concurrent_query_orders(self, orderids: List[str]) -> Dict[str, OrderData]:
    """并发查询订单状态"""
    import concurrent.futures
    
    results = {}
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_orderid = {
            executor.submit(self._query_single_order, orderid): orderid
            for orderid in orderids
        }
        
        for future in concurrent.futures.as_completed(future_to_orderid):
            orderid = future_to_orderid[future]
            try:
                order = future.result()
                if order:
                    results[orderid] = order
            except Exception as e:
                self.write_log(f"Query order {orderid} failed: {e}")
    
    return results
```

### 5. 错误处理和重试机制

```python
class RetryManager:
    def __init__(self, max_retries: int = 3, retry_delay: float = 1.0):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.retry_count = {}
    
    def execute_with_retry(self, func, *args, **kwargs):
        """带重试的执行函数"""
        orderid = kwargs.get('orderid') or args[0] if args else None
        
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise e
                
                # 指数退避
                delay = self.retry_delay * (2 ** attempt)
                time.sleep(delay)
                
                if orderid:
                    self.retry_count[orderid] = self.retry_count.get(orderid, 0) + 1
```

### 6. 性能监控

```python
class PerformanceMonitor:
    def __init__(self):
        self.query_times = []
        self.query_counts = defaultdict(int)
        self.error_counts = defaultdict(int)
    
    def record_query_time(self, query_type: str, duration: float):
        """记录查询时间"""
        self.query_times.append((query_type, duration))
        self.query_counts[query_type] += 1
        
        # 保持最近1000条记录
        if len(self.query_times) > 1000:
            self.query_times = self.query_times[-1000:]
    
    def get_average_query_time(self, query_type: str) -> float:
        """获取平均查询时间"""
        times = [t for qtype, t in self.query_times if qtype == query_type]
        return sum(times) / len(times) if times else 0
    
    def get_error_rate(self, query_type: str) -> float:
        """获取错误率"""
        total = self.query_counts[query_type]
        errors = self.error_counts[query_type]
        return errors / total if total > 0 else 0
```

### 7. 配置示例

```python
# gateway配置
gateway_setting = {
    "api_key": "your_api_key",
    "secret_key": "your_secret_key",
    "endpoint": "https://api.brisk.com",
    "polling_interval": 1.0,
    "max_retries": 3,
    "retry_delay": 1.0,
    "batch_size": 50,
    "concurrent_workers": 5
}
```

## 总结

通过轮询 + 缓存机制，我们可以有效地适配只支持orderId查询或时间范围查询的券商API，使其满足vnpy框架的事件驱动需求。关键点包括：

1. **本地缓存**：维护订单状态缓存，避免重复查询
2. **智能轮询**：根据订单状态调整轮询频率
3. **批量优化**：尽可能使用批量查询减少API调用
4. **错误处理**：实现重试机制和错误恢复
5. **性能监控**：监控查询性能和错误率

这种方案虽然不如真正的实时推送高效，但能够很好地适配现有的券商API限制，同时保持与vnpy框架的兼容性。 