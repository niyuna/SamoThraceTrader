"""
Mock Gateway 测试文件
验证Mock Brisk Gateway的基本功能
"""

import sys
import os
import time
from datetime import datetime

# 添加父目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.object import SubscribeRequest, Exchange
from vnpy.trader.event import EVENT_TICK, EVENT_LOG, EVENT_ORDER, EVENT_TRADE
from vnpy.event import Event

from mock_brisk_gateway import MockBriskGateway


class MockGatewayTester:
    """Mock Gateway测试器"""
    
    def __init__(self):
        """初始化测试器"""
        self.tick_count = 0
        self.order_count = 0
        self.trade_count = 0
        
    def on_tick(self, event: Event):
        """Tick数据回调"""
        tick = event.data
        self.tick_count += 1
        print(f"收到Tick {self.tick_count}: {tick.symbol} - 价格: {tick.last_price:.2f}, "
              f"成交量: {tick.last_volume}, 时间: {tick.datetime.strftime('%H:%M:%S')}")
        
    def on_order(self, event: Event):
        """订单回调"""
        order = event.data
        self.order_count += 1
        print(f"收到订单 {self.order_count}: {order.symbol} - {order.direction.value} "
              f"{order.offset.value} {order.volume}股 @ {order.price:.2f} - 状态: {order.status.value}")
        
    def on_trade(self, event: Event):
        """成交回调"""
        trade = event.data
        self.trade_count += 1
        print(f"收到成交 {self.trade_count}: {trade.symbol} - {trade.direction.value} "
              f"{trade.offset.value} {trade.volume}股 @ {trade.price:.2f}")
        
    def on_log(self, event: Event):
        """日志回调"""
        log = event.data
        print(f"[{log.time}] {log.level}: {log.msg}")


def test_mock_tick_mode():
    """测试Mock Tick模式"""
    print("\n=== 测试Mock Tick模式 ===")
    
    # 创建事件引擎
    event_engine = EventEngine()
    
    # 创建主引擎
    main_engine = MainEngine(event_engine)
    
    # 添加Mock Gateway
    main_engine.add_gateway(MockBriskGateway)
    mock_gateway = main_engine.get_gateway("MOCK_BRISK")
    
    # 创建测试器
    tester = MockGatewayTester()
    
    # 注册事件处理函数
    event_engine.register(EVENT_TICK, tester.on_tick)
    event_engine.register(EVENT_ORDER, tester.on_order)
    event_engine.register(EVENT_TRADE, tester.on_trade)
    event_engine.register(EVENT_LOG, tester.on_log)
    
    # 配置Mock Tick模式
    setting = {
        "tick_mode": "mock",
        "mock_tick_interval": 0.5,        # 500ms间隔
        "mock_price_volatility": 0.005,   # 0.5%波动率
        "mock_volume_range": (100, 500),  # 成交量范围
        "mock_base_prices": {
            "7203": 2500.0,  # 丰田
            "6758": 1800.0,  # 索尼
        },
        "mock_account_balance": 10000000,
        "mock_commission_rate": 0.001,
        "mock_fill_delay": 0.1,           # 100ms成交延迟
    }
    
    # 连接Gateway
    main_engine.connect(setting, "MOCK_BRISK")
    
    # 等待连接建立
    time.sleep(1)
    
    # 订阅股票
    symbols = ["7203", "6758"]
    for symbol in symbols:
        req = SubscribeRequest(symbol=symbol, exchange=Exchange.TSE)
        main_engine.subscribe(req, "MOCK_BRISK")
        print(f"订阅股票: {symbol}")
    
    # 运行一段时间
    print("开始接收Mock Tick数据...")
    try:
        time.sleep(5)
    except KeyboardInterrupt:
        print("\n用户中断测试")
        return
    
    # 测试下单
    print("\n开始测试下单...")
    from vnpy.trader.object import OrderRequest
    from vnpy.trader.constant import Direction, Offset, OrderType
    
    # 下市价买单
    order_req = OrderRequest(
        symbol="7203",
        exchange=Exchange.TSE,
        direction=Direction.LONG,
        type=OrderType.MARKET,
        volume=100,
        offset=Offset.OPEN,
        reference="test_order"
    )
    
    order_id = main_engine.send_order(order_req, "MOCK_BRISK")
    print(f"发送订单: {order_id}")
    
    # 等待成交
    try:
        time.sleep(2)
    except KeyboardInterrupt:
        print("\n用户中断测试")
        return
    
    # 查询账户和持仓
    print("\n查询账户信息...")
    account = main_engine.get_account("MOCK_BRISK.MOCK_ACCOUNT")
    if account:
        print(f"账户余额: {account.balance:.2f}, 可用: {account.available:.2f}")
    
    print("\n查询持仓信息...")
    positions = main_engine.get_all_positions()
    for position in positions:
        if position.gateway_name == "MOCK_BRISK":
            print(f"持仓: {position.symbol} - {position.direction.value} {position.volume}股")
    
    # 等待一段时间
    try:
        time.sleep(2)
    except KeyboardInterrupt:
        print("\n用户中断测试")
        return
    
    # 关闭连接
    main_engine.close()
    
    print(f"\n测试完成:")
    print(f"收到Tick数据: {tester.tick_count}条")
    print(f"收到订单: {tester.order_count}条")
    print(f"收到成交: {tester.trade_count}条")


def test_replay_mode():
    """测试历史数据回放模式"""
    print("\n=== 测试历史数据回放模式 ===")
    
    # 创建事件引擎
    event_engine = EventEngine()
    
    # 创建主引擎
    main_engine = MainEngine(event_engine)
    
    # 添加Mock Gateway
    main_engine.add_gateway(MockBriskGateway)
    mock_gateway = main_engine.get_gateway("MOCK_BRISK")
    
    # 创建测试器
    tester = MockGatewayTester()
    
    # 注册事件处理函数
    event_engine.register(EVENT_TICK, tester.on_tick)
    event_engine.register(EVENT_LOG, tester.on_log)
    
    # 配置Replay模式
    setting = {
        "tick_mode": "replay",
        "replay_data_dir": "D:\\dev\\github\\brisk-hack\\brisk_in_day_frames",
        "replay_date": "20250718",  # 需要根据实际数据文件调整
        "replay_speed": 50.0,       # 50倍速回放，更快
        "replay_symbols": ["7203", "6758"],
        "mock_account_balance": 10000000,
    }
    
    # 连接Gateway
    main_engine.connect(setting, "MOCK_BRISK")
    
    # 等待连接建立
    time.sleep(1)
    
    # 订阅股票
    symbols = ["7203"]
    for symbol in symbols:
        req = SubscribeRequest(symbol=symbol, exchange=Exchange.TSE)
        main_engine.subscribe(req, "MOCK_BRISK")
        print(f"订阅股票: {symbol}")
    
    # 运行一段时间
    print("开始历史数据回放...")
    print("等待回放数据 (按Ctrl+C中断)...")
    
    # 分6次等待，每次10秒，显示进度
    for i in range(6):
        try:
            time.sleep(10)
            print(f"已等待 {(i+1)*10} 秒，收到 {tester.tick_count} 条tick数据")
            
            # 如果收到足够的数据，可以提前退出
            if tester.tick_count > 100:
                print("收到足够的数据，提前结束")
                break
                
        except KeyboardInterrupt:
            print("\n用户中断测试")
            return
    
    # 关闭连接
    main_engine.close()
    
    print(f"\n回放测试完成:")
    print(f"收到Tick数据: {tester.tick_count}条")


def main():
    """主函数"""
    try:
        # 测试Mock Tick模式
        # test_mock_tick_mode()
        
        # 测试Replay模式（需要实际数据文件）
        test_replay_mode()
        
        print("\n所有测试完成")
        
    except KeyboardInterrupt:
        print("\n测试被用户中断")
    except Exception as e:
        print(f"\n测试出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main() 