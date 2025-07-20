"""
Brisk Gateway Demo
展示如何使用BriskGateway接收实时tick数据并自动构建K线，支持实时模式和回放模式
"""

import time
from datetime import datetime
from collections import defaultdict

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.object import SubscribeRequest, Exchange, BarData, Interval
from vnpy.trader.utility import BarGenerator
from brisk_gateway import BriskGateway
from vnpy.trader.event import EVENT_TICK, EVENT_LOG
from vnpy.event import Event


class BarDemo:
    """K线构建演示类"""
    
    def __init__(self):
        # 为每个股票创建BarGenerator
        self.bar_generators = {}
        self.bars_count = defaultdict(int)
        
    def add_symbol(self, symbol: str):
        """为指定股票创建BarGenerator"""
        # 创建1分钟K线生成器
        self.bar_generators[symbol] = BarGenerator(
            on_bar=self.on_1min_bar,
            window=5,  # 5分钟K线
            on_window_bar=self.on_5min_bar,
            interval=Interval.MINUTE
        )
        print(f"为 {symbol} 创建K线生成器")
        
    def on_tick(self, event: Event):
        """Tick数据回调函数"""
        tick = event.data
        print(f"收到Tick数据: {tick.symbol} - 价格: {tick.last_price}, 成交量: {tick.last_volume}, 时间: {tick.datetime}")
        
        # 更新对应的BarGenerator
        if tick.symbol in self.bar_generators:
            self.bar_generators[tick.symbol].update_tick(tick)
    
    def on_1min_bar(self, bar: BarData):
        """1分钟K线回调函数"""
        self.bars_count[f"{bar.symbol}_1min"] += 1
        print(f"生成1分钟K线: {bar.symbol} {bar.datetime.strftime('%Y-%m-%d %H:%M:%S')} - 开:{bar.open_price:.2f} 高:{bar.high_price:.2f} 低:{bar.low_price:.2f} 收:{bar.close_price:.2f} 量:{bar.volume}")
    
    def on_5min_bar(self, bar: BarData):
        """5分钟K线回调函数"""
        self.bars_count[f"{bar.symbol}_5min"] += 1
        print(f"生成5分钟K线: {bar.symbol} {bar.datetime.strftime('%Y-%m-%d %H:%M:%S')} - 开:{bar.open_price:.2f} 高:{bar.high_price:.2f} 低:{bar.low_price:.2f} 收:{bar.close_price:.2f} 量:{bar.volume}")


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
    
    # 创建K线演示对象
    bar_demo = BarDemo()
    
    # 注册事件处理函数
    event_engine.register(EVENT_TICK, bar_demo.on_tick)
    event_engine.register(EVENT_LOG, on_log)
    
    # 连接配置
    setting = {
        "tick_server_url": "ws://127.0.0.1:8001/ws",
        "tick_server_http_url": "http://127.0.0.1:8001",
        "frames_output_dir": "D:\\dev\\github\\brisk-hack\\brisk_in_day_frames",
        "reconnect_interval": 5,
        "heartbeat_interval": 30,
        "max_reconnect_attempts": 10,
        "replay_speed": 5.0,  # 回放速度
    }
    
    # 连接Gateway
    main_engine.connect(setting, "BRISK")
    
    # 等待连接建立
    time.sleep(2)
    
    # 获取Gateway实例
    gateway = main_engine.get_gateway("BRISK")
    
    # 订阅股票
    symbols = ["7203", "6758", "9984"]  # 丰田、索尼、软银
    
    for symbol in symbols:
        req = SubscribeRequest(
            symbol=symbol,
            exchange=Exchange.TSE
        )
        main_engine.subscribe(req, "BRISK")
        print(f"订阅股票: {symbol}")
        
        # 为每个股票创建K线生成器
        bar_demo.add_symbol(symbol)
    
    # 选择运行模式
    print("\n请选择运行模式:")
    print("1. 实时模式 - 接收实时tick数据")
    print("2. 回放模式 - 回放历史数据")
    
    while True:
        try:
            choice = input("请输入选择 (1 或 2): ").strip()
            if choice == "1":
                print("启动实时模式...")
                print("等待实时tick数据并自动构建K线...")
                print("按Ctrl+C退出")
                
                try:
                    # 保持运行
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    print("正在退出实时模式...")
                    break
                    
            elif choice == "2":
                print("启动回放模式...")
                replay_date = input("请输入回放日期 (格式: YYYYMMDD，如20250718): ").strip()
                if not replay_date:
                    replay_date = "20250718"  # 默认日期
                
                print(f"开始回放 {replay_date} 的历史数据...")
                gateway.start_replay(replay_date, symbols)
                
                print("按Ctrl+C退出")
                try:
                    # 保持运行
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    print("正在退出回放模式...")
                    gateway.stop_replay()
                    break
            else:
                print("无效选择，请输入 1 或 2")
                continue
                
        except KeyboardInterrupt:
            print("正在退出...")
            break
    
    print("K线统计:")
    for key, count in bar_demo.bars_count.items():
        print(f"  {key}: {count} 根")
    main_engine.close()


if __name__ == "__main__":
    main() 