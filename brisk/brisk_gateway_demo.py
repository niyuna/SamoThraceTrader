"""
Brisk Gateway Demo
展示如何使用BriskGateway连接tick_server并接收日股tick数据
"""

import time
from datetime import datetime

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.object import SubscribeRequest
from vnpy.trader.constant import Exchange
from brisk_gateway import BriskGateway
from vnpy.trader.event import EVENT_TICK, EVENT_LOG


def on_tick(event):
    """Tick数据回调函数"""
    tick = event.data
    print(f"收到Tick数据: {tick.symbol} - 价格: {tick.last_price}, 成交量: {tick.last_volume}, 时间: {tick.datetime}")


def on_log(event):
    """日志回调函数"""
    log = event.data
    print(f"[{log.time}] {log.msg}")


def main():
    """主函数"""
    # 创建事件引擎
    event_engine = EventEngine()
        
    # 创建主引擎
    main_engine = MainEngine(event_engine)
    
    # 添加BriskGateway
    main_engine.add_gateway(BriskGateway)
    
    # 注册事件处理函数
    event_engine.register(EVENT_TICK, on_tick)
    event_engine.register(EVENT_LOG, on_log)
    
    # 连接配置
    setting = {
        "tick_server_url": "ws://127.0.0.1:8001/ws",
        "tick_server_http_url": "http://127.0.0.1:8001",
        "reconnect_interval": 5,
        "heartbeat_interval": 30,
        "max_reconnect_attempts": 10,
    }
    
    # 连接Gateway
    main_engine.connect(setting, "BRISK")
    
    # 等待连接建立
    time.sleep(2)
    
    # 订阅股票
    symbols = ["7203", "6758", "9984"]  # 丰田、索尼、软银
    
    for symbol in symbols:
        req = SubscribeRequest(
            symbol=symbol,
            exchange=Exchange.TSE
        )
        main_engine.subscribe(req, "BRISK")
        print(f"订阅股票: {symbol}")
    
    print("开始接收tick数据...")
    print("按Ctrl+C退出")
    
    try:
        # 保持运行
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("正在退出...")
        main_engine.close()


if __name__ == "__main__":
    main() 