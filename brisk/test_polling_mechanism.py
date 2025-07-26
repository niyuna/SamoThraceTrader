#!/usr/bin/env python3
"""
测试基于polling的订单状态更新机制
"""

import time
import threading
from datetime import datetime
from vnpy.event import EventEngine
from vnpy.trader.object import OrderRequest
from vnpy.trader.constant import Direction, Offset, OrderType
from vnpy.trader.constant import Exchange

from brisk_gateway import BriskGateway

def test_polling_mechanism():
    """测试轮询机制"""
    
    # 创建事件引擎
    event_engine = EventEngine()
    
    # 创建gateway
    gateway = BriskGateway(event_engine, "BRISK")
    
    # 连接设置
    setting = {
        "tick_server_url": "ws://127.0.0.1:8001/ws",
        "tick_server_http_url": "http://127.0.0.1:8001",
        "polling_interval": 2,  # 2秒轮询一次
    }
    
    # 连接gateway
    gateway.connect(setting)
    
    print("Gateway已连接，开始测试轮询机制...")
    print(f"当前时间: {datetime.now()}")
    print(f"初始updtime (当天8:50): {gateway.last_updtime}")
    
    # 等待一段时间让轮询机制运行
    print("等待10秒观察轮询机制...")
    time.sleep(10)
    
    # 检查本地订单缓存
    print(f"本地订单缓存数量: {len(gateway.local_orders)}")
    for orderid, order in gateway.local_orders.items():
        print(f"订单: {orderid}, 状态: {order.status}, 成交量: {order.traded}, recv_time: {order.datetime}, symbol: {order.symbol}")
    
    # 尝试发送一个测试订单（如果需要的话）
    # test_order_request = OrderRequest(
    #     symbol="7203",  # 丰田汽车
    #     exchange=Exchange.TSE,
    #     direction=Direction.LONG,
    #     type=OrderType.LIMIT,
    #     volume=100,
    #     price=2800.0,
    #     offset=Offset.OPEN,
    #     reference="test_order"
    # )
    # order_id = gateway.send_order(test_order_request)
    # print(f"测试订单已发送: {order_id}")
    
    # 继续观察一段时间
    print("继续观察轮询机制...")
    time.sleep(20)
    
    # 再次检查订单状态
    print(f"最终本地订单缓存数量: {len(gateway.local_orders)}")
    for orderid, order in gateway.local_orders.items():
        print(f"订单: {orderid}, 状态: {order.status}, 成交量: {order.traded}")
    
    # 关闭gateway
    gateway.close()
    print("测试完成")

if __name__ == "__main__":
    test_polling_mechanism() 