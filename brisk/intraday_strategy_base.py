"""
Brisk Gateway Demo V3
展示如何使用BriskGateway接收实时tick数据并自动构建K线，集成V3技术指标模块
"""

import time
from datetime import datetime
from collections import defaultdict

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.object import SubscribeRequest, Exchange, BarData, Interval
from enhanced_bargenerator import EnhancedBarGenerator
from brisk_gateway import BriskGateway
from vnpy.trader.event import EVENT_TICK, EVENT_LOG
from vnpy.event import Event
from technical_indicators import TechnicalIndicatorManager


class IntradayStrategyBase:
    """日内策略基础框架 - 集成技术指标和K线生成"""
    
    def __init__(self):
        """初始化日内策略基础框架"""
        # 创建事件引擎
        self.event_engine = EventEngine()
        
        # 创建主引擎
        self.main_engine = MainEngine(self.event_engine)
        
        # 添加Brisk Gateway
        self.main_engine.add_gateway(BriskGateway)
        self.brisk_gateway = self.main_engine.get_gateway("BRISK")
        
        # 为每个股票创建BarGenerator和技术指标管理器
        self.bar_generators = {}
        self.indicator_managers = {}
        self.bars_count = defaultdict(int)
        
        # 注册事件处理函数
        self.event_engine.register(EVENT_TICK, self.on_tick)
        self.event_engine.register(EVENT_LOG, self.on_log)
        
    def add_symbol(self, symbol: str):
        """为指定股票创建BarGenerator和技术指标管理器"""
        # 创建增强版1分钟K线生成器
        self.bar_generators[symbol] = EnhancedBarGenerator(
            on_bar=self.on_1min_bar,
            window=5,  # 5分钟K线
            on_window_bar=self.on_5min_bar,
            interval=Interval.MINUTE,
            enable_opening_volume=True,  # 启用开盘成交量
            enable_auto_flush=False,     # 不启用强制收线（replay模式）
            main_engine=self.main_engine # 传入main_engine
        )
        
        # 创建技术指标管理器
        self.indicator_managers[symbol] = TechnicalIndicatorManager(symbol, size=15)
        
        print(f"为 {symbol} 创建增强版K线生成器和技术指标管理器")
        
    def on_tick(self, event: Event):
        """Tick数据回调函数"""
        tick = event.data
        # self.brisk_gateway.write_log(f"收到Tick数据: {tick.symbol} - 价格: {tick.last_price}, 成交量: {tick.last_volume}, 时间: {tick.datetime}, 累计成交量: {tick.volume}, 累计成交额: {tick.turnover}")
        
        # 更新对应的BarGenerator
        if tick.symbol in self.bar_generators:
            self.bar_generators[tick.symbol].update_tick(tick)
    
    def on_1min_bar(self, bar: BarData):
        """1分钟K线回调函数"""
        self.bars_count[f"{bar.symbol}_1min"] += 1
        
        # 更新技术指标
        if bar.symbol in self.indicator_managers:
            indicators = self.indicator_managers[bar.symbol].update_bar(bar)
            
            # 打印详细的指标信息
            print(f"\n=== 1分钟K线: {bar.symbol} {bar.datetime.strftime('%Y-%m-%d %H:%M:%S')} ===")
            print(f"价格数据:")
            print(f"  开盘: {bar.open_price:.2f}  最高: {bar.high_price:.2f}  最低: {bar.low_price:.2f}  收盘: {bar.close_price:.2f}")
            print(f"  成交量: {bar.volume:.0f}  成交额: {bar.turnover:.0f}")
            
            print(f"技术指标:")
            print(f"  VWAP: {indicators['vwap']:.2f}")
            print(f"  ATR(14): {indicators['atr_14']:.2f}")
            print(f"  Volume MA5: {indicators['volume_ma5']:.0f}")
            
            print(f"统计信息:")
            print(f"  Close > VWAP: {indicators['above_vwap_count']} 次")
            print(f"  Close < VWAP: {indicators['below_vwap_count']} 次")
            print(f"  Close = VWAP: {indicators['equal_vwap_count']} 次")
            
            print(f"累计数据:")
            print(f"  当日累计成交量: {indicators['daily_acc_volume']:.0f}")
            print(f"  当日累计成交额: {indicators['daily_acc_turnover']:.0f}")
            
            # 计算一些额外的指标
            if indicators['daily_acc_volume'] > 0:
                avg_price = indicators['daily_acc_turnover'] / indicators['daily_acc_volume']
                print(f"  当日平均价格: {avg_price:.2f}")
            
            if indicators['above_vwap_count'] + indicators['below_vwap_count'] > 0:
                above_ratio = indicators['above_vwap_count'] / (indicators['above_vwap_count'] + indicators['below_vwap_count'])
                print(f"  Close > VWAP 比例: {above_ratio:.2%}")
    
    def on_5min_bar(self, bar: BarData):
        """5分钟K线回调函数"""
        self.bars_count[f"{bar.symbol}_5min"] += 1
        print(f"生成5分钟K线: {bar.symbol} {bar.datetime.strftime('%Y-%m-%d %H:%M:%S')} - "
              f"开:{bar.open_price:.2f} 高:{bar.high_price:.2f} 低:{bar.low_price:.2f} "
              f"收:{bar.close_price:.2f} 量:{bar.volume}")
    
    def on_log(self, event: Event):
        """日志回调函数"""
        log = event.data
        print(f"[{log.time}] {log.level}: {log.msg}")
    
    def connect(self, setting: dict = None):
        """连接Brisk Gateway"""
        if setting is None:
            setting = {
                "tick_server_url": "ws://127.0.0.1:8001/ws",
                "tick_server_http_url": "http://127.0.0.1:8001",
                "frames_output_dir": "D:\\dev\\github\\brisk-hack\\brisk_in_day_frames",
                "reconnect_interval": 5,
                "heartbeat_interval": 30,
                "max_reconnect_attempts": 10,
                "replay_speed": 15,
            }
        
        self.main_engine.connect(setting, "BRISK")
        print("Brisk Gateway连接成功")
    
    def subscribe(self, symbols: list):
        """订阅股票"""
        for symbol in symbols:
            # 添加股票到技术指标管理器
            self.add_symbol(symbol)
            
            # 订阅行情
            req = SubscribeRequest(symbol=symbol, exchange=Exchange.TSE)
            self.main_engine.subscribe(req, "BRISK")
            print(f"订阅股票: {symbol}")
    
    def start_replay(self, date: str, symbols: list = None):
        """开始历史数据回放"""
        if symbols is None:
            symbols = list(self.indicator_managers.keys())
        
        self.brisk_gateway.start_replay(date, symbols)
        print(f"开始回放 {date} 的历史数据")
    
    def stop_replay(self):
        """停止历史数据回放"""
        self.brisk_gateway.stop_replay()
        print("停止历史数据回放")
    
    def get_indicators(self, symbol: str) -> dict:
        """获取指定股票的技术指标"""
        if symbol in self.indicator_managers:
            return self.indicator_managers[symbol].get_indicators()
        return {}
    
    def get_all_indicators(self) -> dict:
        """获取所有股票的技术指标"""
        all_indicators = {}
        for symbol in self.indicator_managers:
            all_indicators[symbol] = self.get_indicators(symbol)
        return all_indicators
    
    def print_summary(self):
        """打印统计摘要"""
        print("\n=== 统计摘要 ===")
        print("K线生成统计:")
        for key, count in self.bars_count.items():
            print(f"  {key}: {count} 根")
        
        print("\n技术指标状态:")
        for symbol in self.indicator_managers:
            manager = self.indicator_managers[symbol]
            indicators = manager.get_indicators()
            if indicators:
                print(f"  {symbol}: VWAP={indicators['vwap']:.2f}, "
                      f"ATR(14)={indicators['atr_14']:.2f}, "
                      f"Close>VWAP={indicators['above_vwap_count']}")
    
    def close(self):
        """关闭连接"""
        self.brisk_gateway.close()
        self.event_engine.stop()
        print("Brisk Gateway Demo已关闭")


def main():
    """主函数"""
    print("启动日内策略基础框架...")
    
    # 创建策略实例
    strategy = IntradayStrategyBase()
    
    try:
        # 连接Gateway
        strategy.connect()
        
        # 订阅股票（这里使用示例股票代码）
        # symbols = ["7203", "6758", "9984"]  # 丰田、索尼、软银
        symbols = ["9984"]  # 软银
        strategy.subscribe(symbols)
        
        # 等待一段时间接收数据
        print("等待接收数据...")
        time.sleep(1)
        
        # 打印摘要
        # strategy.print_summary()
        
        # 或者开始历史数据回放
        strategy.start_replay("20250718", symbols)
        # time.sleep(30)
        # strategy.stop_replay()
        
        # 保持运行
        print("按Ctrl+C退出...")
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n收到退出信号...")
    except Exception as e:
        print(f"运行过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        strategy.close()


if __name__ == "__main__":
    main() 