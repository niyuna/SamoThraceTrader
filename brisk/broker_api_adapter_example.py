"""
券商API适配实现示例
展示如何在只支持orderId查询或时间范围查询的券商API基础上，
实现vnpy框架所需的事件驱动机制
"""

import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional
from dataclasses import dataclass
from collections import defaultdict
import concurrent.futures

from vnpy.trader.gateway import BaseGateway
from vnpy.trader.object import OrderData, TradeData, BarData
from vnpy.trader.constant import Status, Direction, OrderType, Exchange
from vnpy.trader.event import EventEngine
from vnpy.event import Event


@dataclass
class BrokerOrder:
    """券商订单数据结构"""
    order_id: str
    symbol: str
    side: str  # "buy" or "sell"
    price: float
    quantity: float
    filled_quantity: float = 0.0
    status: str = "pending"  # pending, submitted, partial_filled, filled, cancelled, rejected
    created_at: datetime = None
    updated_at: datetime = None
    client_order_id: str = ""


class MockBrokerAPI:
    """模拟券商API，只支持orderId查询和时间范围查询"""
    
    def __init__(self):
        self.orders: Dict[str, BrokerOrder] = {}
        self.order_counter = 0
        
    def send_order(self, symbol: str, side: str, price: float, quantity: float) -> str:
        """发送订单"""
        self.order_counter += 1
        order_id = f"ORDER_{self.order_counter:06d}"
        
        order = BrokerOrder(
            order_id=order_id,
            symbol=symbol,
            side=side,
            price=price,
            quantity=quantity,
            status="pending",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        self.orders[order_id] = order
        
        # 模拟订单状态变化
        self._simulate_order_status_change(order_id)
        
        return order_id
    
    def query_order(self, order_id: str) -> Optional[BrokerOrder]:
        """查询单个订单状态"""
        return self.orders.get(order_id)
    
    def query_orders_since(self, since_time: datetime) -> List[BrokerOrder]:
        """查询指定时间之后的订单"""
        return [
            order for order in self.orders.values()
            if order.created_at >= since_time
        ]
    
    def cancel_order(self, order_id: str) -> bool:
        """撤销订单"""
        if order_id in self.orders:
            self.orders[order_id].status = "cancelled"
            self.orders[order_id].updated_at = datetime.now()
            return True
        return False
    
    def _simulate_order_status_change(self, order_id: str):
        """模拟订单状态变化（实际环境中由券商处理）"""
        def status_change_worker():
            order = self.orders[order_id]
            
            # 模拟订单确认
            time.sleep(0.1)
            order.status = "submitted"
            order.updated_at = datetime.now()
            
            # 模拟部分成交
            time.sleep(0.2)
            if order.status == "submitted":
                order.status = "partial_filled"
                order.filled_quantity = order.quantity * 0.3
                order.updated_at = datetime.now()
            
            # 模拟完全成交
            time.sleep(0.3)
            if order.status == "partial_filled":
                order.status = "filled"
                order.filled_quantity = order.quantity
                order.updated_at = datetime.now()
        
        thread = threading.Thread(target=status_change_worker, daemon=True)
        thread.start()


class OrderCache:
    """订单缓存管理器"""
    
    def __init__(self):
        self.orders: Dict[str, OrderData] = {}
        self.order_timestamps: Dict[str, datetime] = {}
        self.pending_orders: Set[str] = set()
        self.active_orders: Set[str] = set()
    
    def add_order(self, order: OrderData):
        """添加新订单到缓存"""
        self.orders[order.vt_orderid] = order
        self.order_timestamps[order.vt_orderid] = datetime.now()
        
        if order.status == Status.SUBMITTING:
            self.pending_orders.add(order.vt_orderid)
        
        if order.is_active():
            self.active_orders.add(order.vt_orderid)
    
    def update_order(self, order: OrderData) -> bool:
        """更新订单状态，返回是否有状态变化"""
        old_order = self.orders.get(order.vt_orderid)
        has_change = False
        
        if old_order:
            # 检查状态变化
            if old_order.status != order.status:
                has_change = True
                self.write_log(f"Order {order.vt_orderid} status changed: {old_order.status} -> {order.status}")
            
            # 检查成交数量变化
            if old_order.traded != order.traded:
                has_change = True
                self.write_log(f"Order {order.vt_orderid} traded changed: {old_order.traded} -> {order.traded}")
        
        # 更新缓存
        self.orders[order.vt_orderid] = order
        self.order_timestamps[order.vt_orderid] = datetime.now()
        
        # 更新集合
        if order.status == Status.SUBMITTING:
            self.pending_orders.add(order.vt_orderid)
        else:
            self.pending_orders.discard(order.vt_orderid)
        
        if order.is_active():
            self.active_orders.add(order.vt_orderid)
        else:
            self.active_orders.discard(order.vt_orderid)
        
        return has_change
    
    def get_pending_orders(self) -> List[str]:
        """获取等待确认的订单ID列表"""
        return list(self.pending_orders)
    
    def get_active_orders(self) -> List[str]:
        """获取活跃订单ID列表"""
        return list(self.active_orders)
    
    def get_orders_since(self, since_time: datetime) -> List[str]:
        """获取指定时间之后的订单ID列表"""
        return [
            orderid for orderid, timestamp in self.order_timestamps.items()
            if timestamp >= since_time
        ]
    
    def write_log(self, msg: str):
        """写日志"""
        print(f"[OrderCache] {msg}")


class SmartPollingManager:
    """智能轮询管理器"""
    
    def __init__(self):
        self.polling_intervals = {
            "high_frequency": 0.5,    # 高频轮询（等待确认的订单）
            "normal": 2.0,            # 正常轮询
            "low_frequency": 10.0     # 低频轮询（已完成的订单）
        }
        self.last_poll_time = defaultdict(datetime.now)
    
    def should_poll_order(self, orderid: str, order: OrderData) -> bool:
        """判断是否应该轮询该订单"""
        now = datetime.now()
        last_poll = self.last_poll_time[orderid]
        
        if order.status in [Status.SUBMITTING, Status.NOTTRADED]:
            interval = self.polling_intervals["high_frequency"]
        elif order.status == Status.PARTTRADED:
            interval = self.polling_intervals["normal"]
        else:
            interval = self.polling_intervals["low_frequency"]
        
        return (now - last_poll).total_seconds() >= interval
    
    def record_poll_time(self, orderid: str):
        """记录轮询时间"""
        self.last_poll_time[orderid] = datetime.now()


class BriskGatewayWithPolling(BaseGateway):
    """支持轮询的Brisk Gateway"""
    
    default_name: str = "BRISK_POLLING"
    default_setting = {
        "api_key": "",
        "secret_key": "",
        "endpoint": "",
        "polling_interval": 1.0,
        "max_retries": 3,
        "retry_delay": 1.0,
        "concurrent_workers": 5
    }
    
    exchanges = [Exchange.SSE, Exchange.SZSE]
    
    def __init__(self, event_engine: EventEngine, gateway_name: str):
        super().__init__(event_engine, gateway_name)
        
        # 券商API
        self.broker_api = MockBrokerAPI()
        
        # 订单缓存
        self.order_cache = OrderCache()
        
        # 轮询管理器
        self.polling_manager = SmartPollingManager()
        
        # 轮询配置
        self.polling_interval = 1.0
        self.max_retries = 3
        self.retry_delay = 1.0
        self.concurrent_workers = 5
        
        # 轮询线程
        self.polling_thread = None
        self.polling_active = False
        
        # 性能监控
        self.query_times = []
        self.query_counts = defaultdict(int)
        self.error_counts = defaultdict(int)
    
    def connect(self, setting: dict) -> None:
        """连接券商"""
        self.api_key = setting["api_key"]
        self.secret_key = setting["secret_key"]
        self.endpoint = setting["endpoint"]
        self.polling_interval = setting.get("polling_interval", 1.0)
        self.max_retries = setting.get("max_retries", 3)
        self.retry_delay = setting.get("retry_delay", 1.0)
        self.concurrent_workers = setting.get("concurrent_workers", 5)
        
        # 启动轮询线程
        self._start_polling()
        
        self.write_log("Brisk Gateway connected with polling enabled")
    
    def disconnect(self) -> None:
        """断开连接"""
        self._stop_polling()
        self.write_log("Brisk Gateway disconnected")
    
    def send_order(self, req) -> str:
        """发送订单"""
        # 调用券商API发送订单
        order_id = self.broker_api.send_order(
            symbol=req.symbol,
            side="buy" if req.direction == Direction.LONG else "sell",
            price=req.price,
            quantity=req.volume
        )
        
        # 创建vnpy订单对象
        order = req.create_order_data(order_id, self.gateway_name)
        
        # 添加到缓存
        self.order_cache.add_order(order)
        
        # 推送订单事件
        self.on_order(order)
        
        return order.vt_orderid
    
    def cancel_order(self, req) -> None:
        """撤销订单"""
        # 从vt_orderid中提取order_id
        order_id = req.orderid
        
        # 调用券商API撤销订单
        success = self.broker_api.cancel_order(order_id)
        
        if success:
            # 更新本地缓存
            if req.vt_orderid in self.order_cache.orders:
                order = self.order_cache.orders[req.vt_orderid]
                order.status = Status.CANCELLED
                self.on_order(order)
    
    def query_account(self) -> None:
        """查询账户"""
        # 实现账户查询逻辑
        pass
    
    def query_position(self) -> None:
        """查询持仓"""
        # 实现持仓查询逻辑
        pass
    
    def _start_polling(self):
        """启动轮询线程"""
        if self.polling_thread and self.polling_thread.is_alive():
            return
        
        self.polling_active = True
        self.polling_thread = threading.Thread(target=self._polling_worker, daemon=True)
        self.polling_thread.start()
    
    def _stop_polling(self):
        """停止轮询线程"""
        self.polling_active = False
        if self.polling_thread:
            self.polling_thread.join(timeout=5)
    
    def _polling_worker(self):
        """轮询工作线程"""
        while self.polling_active:
            try:
                self._poll_orders()
                time.sleep(self.polling_interval)
            except Exception as e:
                self.write_log(f"Polling error: {e}")
                time.sleep(self.polling_interval * 2)  # 错误时延长间隔
    
    def _poll_orders(self):
        """轮询订单状态"""
        start_time = time.time()
        
        # 获取需要轮询的订单
        orders_to_poll = []
        for orderid, order in self.order_cache.orders.items():
            if self.polling_manager.should_poll_order(orderid, order):
                orders_to_poll.append(orderid)
        
        if not orders_to_poll:
            return
        
        # 并发查询订单状态
        self._concurrent_query_orders(orders_to_poll)
        
        # 记录性能统计
        duration = time.time() - start_time
        self._record_query_time("batch_poll", duration)
    
    def _concurrent_query_orders(self, orderids: List[str]):
        """并发查询订单状态"""
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.concurrent_workers) as executor:
            future_to_orderid = {
                executor.submit(self._query_single_order, orderid): orderid
                for orderid in orderids
            }
            
            for future in concurrent.futures.as_completed(future_to_orderid):
                orderid = future_to_orderid[future]
                try:
                    order = future.result()
                    if order:
                        # 记录轮询时间
                        self.polling_manager.record_poll_time(orderid)
                except Exception as e:
                    self.write_log(f"Query order {orderid} failed: {e}")
                    self._record_error("single_query")
    
    def _query_single_order(self, orderid: str) -> Optional[OrderData]:
        """查询单个订单状态"""
        start_time = time.time()
        
        try:
            # 调用券商API查询订单状态
            broker_order = self.broker_api.query_order(orderid)
            
            if not broker_order:
                return None
            
            # 转换为vnpy格式
            order = self._convert_broker_order_to_vnpy(broker_order)
            
            # 检查状态是否发生变化
            if self.order_cache.update_order(order):
                # 推送订单状态变化事件
                self.on_order(order)
            
            # 记录查询时间
            duration = time.time() - start_time
            self._record_query_time("single_query", duration)
            
            return order
            
        except Exception as e:
            self.write_log(f"Query order {orderid} failed: {e}")
            self._record_error("single_query")
            return None
    
    def _convert_broker_order_to_vnpy(self, broker_order: BrokerOrder) -> OrderData:
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
            symbol=broker_order.symbol,
            exchange=Exchange.SSE,  # 根据实际情况设置
            orderid=broker_order.order_id,
            type=OrderType.LIMIT,
            direction=direction_mapping.get(broker_order.side, Direction.LONG),
            offset=Offset.NONE,
            price=broker_order.price,
            volume=broker_order.quantity,
            traded=broker_order.filled_quantity,
            status=status_mapping.get(broker_order.status, Status.SUBMITTING),
            datetime=broker_order.created_at or datetime.now(),
            reference=broker_order.client_order_id
        )
        
        return order
    
    def _record_query_time(self, query_type: str, duration: float):
        """记录查询时间"""
        self.query_times.append((query_type, duration))
        self.query_counts[query_type] += 1
        
        # 保持最近1000条记录
        if len(self.query_times) > 1000:
            self.query_times = self.query_times[-1000:]
    
    def _record_error(self, query_type: str):
        """记录错误"""
        self.error_counts[query_type] += 1
    
    def get_performance_stats(self) -> Dict:
        """获取性能统计"""
        stats = {}
        
        for query_type in self.query_counts:
            times = [t for qtype, t in self.query_times if qtype == query_type]
            if times:
                stats[f"{query_type}_avg_time"] = sum(times) / len(times)
                stats[f"{query_type}_count"] = self.query_counts[query_type]
                stats[f"{query_type}_error_count"] = self.error_counts[query_type]
                stats[f"{query_type}_error_rate"] = (
                    self.error_counts[query_type] / self.query_counts[query_type]
                    if self.query_counts[query_type] > 0 else 0
                )
        
        return stats


# 使用示例
def demo_usage():
    """演示使用方法"""
    from vnpy.event import EventEngine
    from vnpy.trader.engine import MainEngine
    from vnpy.trader.object import OrderRequest
    
    # 创建事件引擎
    event_engine = EventEngine()
    
    # 创建主引擎
    main_engine = MainEngine(event_engine)
    
    # 添加Gateway
    gateway = BriskGatewayWithPolling(event_engine, "BRISK_POLLING")
    main_engine.add_gateway(gateway)
    
    # 连接Gateway
    setting = {
        "api_key": "demo_key",
        "secret_key": "demo_secret",
        "endpoint": "https://api.brisk.com",
        "polling_interval": 1.0,
        "max_retries": 3,
        "retry_delay": 1.0,
        "concurrent_workers": 5
    }
    gateway.connect(setting)
    
    # 发送订单
    req = OrderRequest(
        symbol="000001.SZSE",
        exchange=Exchange.SZSE,
        direction=Direction.LONG,
        type=OrderType.LIMIT,
        volume=100,
        price=10.0
    )
    
    orderid = gateway.send_order(req)
    print(f"Order sent: {orderid}")
    
    # 运行一段时间观察轮询效果
    time.sleep(10)
    
    # 获取性能统计
    stats = gateway.get_performance_stats()
    print("Performance stats:", stats)
    
    # 断开连接
    gateway.disconnect()


if __name__ == "__main__":
    demo_usage() 