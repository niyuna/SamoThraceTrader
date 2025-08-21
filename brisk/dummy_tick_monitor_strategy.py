"""
Dummy Tick Monitor Strategy
用于监控 brisk_gateway 是否正常工作并发送 tick 数据
"""

import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Dict, List

import apprise

from intraday_strategy_base import IntradayStrategyBase
from vnpy.trader.object import TickData
from vnpy.event import Event


class DummyTickMonitorStrategy(IntradayStrategyBase):
    """
    Dummy策略：监控 brisk_gateway 的 tick 数据流
    主要功能：
    1. 订阅指定的流动性股票
    2. 监控 tick 数据接收情况
    3. 检测长时间无 tick 的异常情况
    """
    
    def __init__(self, use_mock_gateway=False):
        """初始化策略"""
        super().__init__(use_mock_gateway)
        
        # 监控配置
        self.monitor_symbols = ["9984", "7011", "6098", "7203"]  # 软银集团、三菱重工
        self.warning_threshold = timedelta(minutes=3)  # 3分钟警告阈值
        self.critical_threshold = timedelta(minutes=5)  # 5分钟严重警告阈值
        self.check_interval = 30  # 检查间隔（秒）
        self.log_interval = 100  # 每100个tick记录一次状态
        
        # 监控状态
        self.last_tick_time: Dict[str, datetime] = {}  # 每个股票的最后tick时间
        self.system_last_tick_time: datetime = None  # 整个系统的最后tick时间
        self.tick_count: Dict[str, int] = {}  # 每个股票的tick计数
        self.total_tick_count = 0  # 总tick计数
        
        # 市场时间配置（日本时间）
        self.market_open_time = "09:00"  # 市场开盘时间
        self.market_close_time = "15:30"  # 市场收盘时间
        self.lunch_start_time = "11:30"  # 午休开始时间
        self.lunch_end_time = "12:30"    # 午休结束时间
        
        # 定时器相关
        self.last_check_time = None
        self.check_timer_active = False
        
        # Windows Toast 通知配置
        self.toast_enabled = True
        self.toast_apprise = apprise.Apprise()
        self.toast_apprise.add("windows://?duration=5")  # Windows Toast，显示5秒
        
        # 通知状态跟踪（避免重复通知）
        self.last_warning_notification = {}  # 记录每个级别的最后通知时间
        self.notification_cooldown = timedelta(minutes=1)  # 通知冷却时间
        
        self.write_log("DummyTickMonitorStrategy 初始化完成")
        self.write_log(f"监控股票: {', '.join(self.monitor_symbols)}")
        self.write_log(f"警告阈值: {self.warning_threshold}")
        self.write_log(f"严重警告阈值: {self.critical_threshold}")
        self.write_log(f"检查间隔: {self.check_interval}秒")
        self.write_log(f"Windows Toast 通知: {'启用' if self.toast_enabled else '禁用'}")
    
    def connect(self, setting: dict = None):
        """连接Gateway并启动监控"""
        # 使用默认设置或传入的设置
        if setting is None:
            setting = {
                "tick_server_url": "ws://127.0.0.1:8001/ws",
                "tick_server_http_url": "http://127.0.0.1:8001",
            }
            self.write_log("使用默认Gateway设置")
        
        super().connect(setting)
        
        # 启动定时器检查
        self._start_check_timer()
        
        # 订阅监控股票
        self.subscribe(self.monitor_symbols)
        
        self.write_log(f"开始监控股票: {', '.join(self.monitor_symbols)}")
    
    def on_tick(self, event: Event):
        """Tick数据回调函数"""
        tick = event.data
        
        # 更新tick统计
        self._update_tick_stats(tick)
        
        # 调用父类的on_tick处理
        super().on_tick(event)
    
    def _update_tick_stats(self, tick: TickData):
        """更新tick统计信息"""
        symbol = tick.symbol
        current_time = datetime.now(ZoneInfo("Asia/Tokyo"))
        
        # 更新单个股票的tick统计
        if symbol not in self.tick_count:
            self.tick_count[symbol] = 0
        self.tick_count[symbol] += 1
        
        # 更新最后tick时间
        self.last_tick_time[symbol] = current_time
        self.system_last_tick_time = current_time
        
        # 更新总计数
        self.total_tick_count += 1
        
        # 按配置间隔记录状态
        if self.total_tick_count % self.log_interval == 0:
            tick_summary = ", ".join([f"{symbol}: {self.tick_count.get(symbol, 0)}" 
                                    for symbol in self.monitor_symbols])
            self.write_log(f"Tick统计更新 - 总计: {self.total_tick_count}, {tick_summary}")
    
    def _start_check_timer(self):
        """启动定时器检查"""
        self.check_timer_active = True
        self.last_check_time = datetime.now(ZoneInfo("Asia/Tokyo"))
        
        # 启动定时器线程
        import threading
        self.check_timer_thread = threading.Thread(target=self._run_check_timer, daemon=True)
        self.check_timer_thread.start()
        
        self.write_log("Tick监控定时器已启动")
    
    def _run_check_timer(self):
        """运行定时器检查"""
        while self.check_timer_active:
            try:
                current_time = datetime.now(ZoneInfo("Asia/Tokyo"))
                
                # 检查是否需要执行检查
                if (self.last_check_time is None or 
                    (current_time - self.last_check_time).total_seconds() >= self.check_interval):
                    
                    self._check_tick_health()
                    self.last_check_time = current_time
                
                time.sleep(1)  # 每秒检查一次
                
            except Exception as e:
                self.write_log(f"定时器检查异常: {e}")
                time.sleep(5)  # 异常时等待5秒
    
    def _check_tick_health(self):
        """检查tick健康状态"""
        if not self._is_market_open():
            return  # 市场关闭时不检查
        
        if self.system_last_tick_time is None:
            self.write_log("警告: 尚未收到任何tick数据")
            return
        
        current_time = datetime.now(ZoneInfo("Asia/Tokyo"))
        time_since_last_tick = current_time - self.system_last_tick_time
        
        # 检查是否超过严重警告阈值
        if time_since_last_tick >= self.critical_threshold:
            self.write_log(f"严重警告: 系统已 {time_since_last_tick.total_seconds()/60:.1f} 分钟未收到tick数据！")
            self.write_log(f"最后tick时间: {self.system_last_tick_time.strftime('%Y-%m-%d %H:%M:%S')}")
            self.write_log(f"当前时间: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
            self._send_toast_notification(
                "严重警告", 
                f"系统已 {time_since_last_tick.total_seconds()/60:.1f} 分钟未收到tick数据！", 
                "CRIT"
            )
            
        # 检查是否超过警告阈值
        elif time_since_last_tick >= self.warning_threshold:
            self.write_log(f"警告: 系统已 {time_since_last_tick.total_seconds()/60:.1f} 分钟未收到tick数据")
            self.write_log(f"最后tick时间: {self.system_last_tick_time.strftime('%Y-%m-%d %H:%M:%S')}")
            self._send_toast_notification(
                "系统警告", 
                f"系统已 {time_since_last_tick.total_seconds()/60:.1f} 分钟未收到tick数据", 
                "WARN"
            )
        
        # 检查各股票的tick状态
        for symbol in self.monitor_symbols:
            if symbol in self.last_tick_time:
                symbol_time_since_last_tick = current_time - self.last_tick_time[symbol]
                if symbol_time_since_last_tick >= self.warning_threshold:
                    self.write_log(f"警告: {symbol} 已 {symbol_time_since_last_tick.total_seconds()/60:.1f} 分钟未收到tick数据")
    
    def _is_market_open(self) -> bool:
        """判断当前是否为市场开放时间"""
        current_time = datetime.now(ZoneInfo("Asia/Tokyo"))
        current_time_str = current_time.strftime("%H:%M")
        
        # 检查是否为工作日（简单判断，实际使用时可能需要更复杂的逻辑）
        if current_time.weekday() >= 5:  # 周六、周日
            return False
        
        # 检查是否在交易时间内
        if (self.market_open_time <= current_time_str < self.lunch_start_time or
            self.lunch_end_time <= current_time_str < self.market_close_time):
            return True
        
        return False
    
    def _send_toast_notification(self, title: str, body: str, level: str = "INFO"):
        """发送Windows Toast通知"""
        if not self.toast_enabled:
            return
        
        # 检查通知冷却时间，避免重复通知
        notification_key = f"{title}_{level}"
        current_time = datetime.now(ZoneInfo("Asia/Tokyo"))
        
        if (notification_key in self.last_warning_notification and 
            current_time - self.last_warning_notification[notification_key] < self.notification_cooldown):
            return  # 还在冷却时间内，跳过通知
        
        try:
            # 发送toast通知
            self.toast_apprise.notify(
                title=f"[{level}] {title}",
                body=body
            )
            
            # 记录通知时间
            self.last_warning_notification[notification_key] = current_time
            
            # 记录日志
            self.write_log(f"已发送Toast通知: [{level}] {title} - {body}")
            
        except Exception as e:
            self.write_log(f"发送Toast通知失败: {e}")
    
    def get_monitoring_status(self) -> Dict:
        """获取监控状态"""
        current_time = datetime.now(ZoneInfo("Asia/Tokyo"))
        
        status = {
            "current_time": current_time.strftime("%Y-%m-%d %H:%M:%S"),
            "market_open": self._is_market_open(),
            "total_tick_count": self.total_tick_count,
            "system_last_tick_time": (self.system_last_tick_time.strftime("%Y-%m-%d %H:%M:%S") 
                                     if self.system_last_tick_time else "None"),
            "toast_notifications": {
                "enabled": self.toast_enabled,
                "last_notifications": {k: v.strftime("%Y-%m-%d %H:%M:%S") 
                                     for k, v in self.last_warning_notification.items()}
            },
            "symbols_status": {}
        }
        
        for symbol in self.monitor_symbols:
            if symbol in self.last_tick_time:
                time_since_last_tick = current_time - self.last_tick_time[symbol]
                status["symbols_status"][symbol] = {
                    "tick_count": self.tick_count.get(symbol, 0),
                    "last_tick_time": self.last_tick_time[symbol].strftime("%Y-%m-%d %H:%M:%S"),
                    "minutes_since_last_tick": time_since_last_tick.total_seconds() / 60,
                    "status": "normal" if time_since_last_tick < self.warning_threshold else "warning"
                }
            else:
                status["symbols_status"][symbol] = {
                    "tick_count": 0,
                    "last_tick_time": "None",
                    "minutes_since_last_tick": float('inf'),
                    "status": "no_data"
                }
        
        return status
    
    def print_monitoring_status(self):
        """打印监控状态"""
        status = self.get_monitoring_status()
        
        print("\n=== Tick监控状态 ===")
        print(f"当前时间: {status['current_time']}")
        print(f"市场状态: {'开放' if status['market_open'] else '关闭'}")
        print(f"总Tick数: {status['total_tick_count']}")
        print(f"系统最后Tick: {status['system_last_tick_time']}")
        print(f"Toast通知: {'启用' if status['toast_notifications']['enabled'] else '禁用'}")
        
        # 显示最近的通知记录
        if status['toast_notifications']['last_notifications']:
            print("最近通知记录:")
            for notification_key, notification_time in status['toast_notifications']['last_notifications'].items():
                print(f"  {notification_key}: {notification_time}")
        
        print("\n各股票状态:")
        for symbol, symbol_status in status["symbols_status"].items():
            print(f"  {symbol}:")
            print(f"    Tick数量: {symbol_status['tick_count']}")
            print(f"    最后Tick: {symbol_status['last_tick_time']}")
            print(f"    距最后Tick: {symbol_status['minutes_since_last_tick']:.1f} 分钟")
            print(f"    状态: {symbol_status['status']}")
        
        print("=== ===\n")
    
    def close(self):
        """关闭策略"""
        self.check_timer_active = False
        
        # 安全关闭父类资源
        try:
            if hasattr(self, 'brisk_gateway') and self.brisk_gateway:
                self.brisk_gateway.close()
        except Exception as e:
            self.write_log(f"关闭brisk_gateway时出错: {e}")
        
        try:
            if hasattr(self, 'event_engine') and self.event_engine:
                self.event_engine.stop()
        except Exception as e:
            self.write_log(f"停止event_engine时出错: {e}")
        
        self.write_log("DummyTickMonitorStrategy 已关闭")


def main():
    """主函数"""
    print("启动Tick监控策略...")
    
    # 创建策略实例
    strategy = DummyTickMonitorStrategy()
    
    try:
        # 连接Gateway
        strategy.connect()
        
        # 保持运行并定期打印状态
        print("Tick监控策略运行中，按Ctrl+C退出...")
        while True:
            time.sleep(60)  # 每分钟打印一次状态
            strategy.print_monitoring_status()
            
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