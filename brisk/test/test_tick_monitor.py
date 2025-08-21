"""
测试Tick监控策略
"""

import time
import unittest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dummy_tick_monitor_strategy import DummyTickMonitorStrategy


class TestDummyTickMonitorStrategy(unittest.TestCase):
    """测试DummyTickMonitorStrategy类"""
    
    def setUp(self):
        """测试前准备"""
        self.strategy = DummyTickMonitorStrategy(use_mock_gateway=True)
    
    def tearDown(self):
        """测试后清理"""
        if hasattr(self.strategy, 'check_timer_active'):
            self.strategy.check_timer_active = False
        self.strategy.close()
    
    def test_initialization(self):
        """测试策略初始化"""
        self.assertIsNotNone(self.strategy.monitor_symbols)
        self.assertIsNotNone(self.strategy.warning_threshold)
        self.assertIsNotNone(self.strategy.critical_threshold)
        self.assertIsNotNone(self.strategy.check_interval)
        
        # 验证默认配置
        self.assertEqual(len(self.strategy.monitor_symbols), 2)
        self.assertIn("9984", self.strategy.monitor_symbols)
        self.assertIn("7011", self.strategy.monitor_symbols)
    
    def test_market_time_validation(self):
        """测试市场时间验证"""
        # 测试市场开放时间
        with patch('dummy_tick_monitor_strategy.datetime') as mock_datetime:
            # 模拟工作日 9:30 (市场开放时间)
            mock_datetime.now.return_value = datetime(2024, 1, 15, 9, 30, 0)  # 周一
            mock_datetime.now.return_value = mock_datetime.now.return_value.replace(tzinfo=ZoneInfo("Asia/Tokyo"))
            
            self.assertTrue(self.strategy._is_market_open())
            
            # 模拟工作日 11:45 (午休时间)
            mock_datetime.now.return_value = datetime(2024, 1, 15, 11, 45, 0)
            mock_datetime.now.return_value = mock_datetime.now.return_value.replace(tzinfo=ZoneInfo("Asia/Tokyo"))
            
            self.assertFalse(self.strategy._is_market_open())
            
            # 模拟工作日 13:00 (市场开放时间)
            mock_datetime.now.return_value = datetime(2024, 1, 15, 13, 0, 0)
            mock_datetime.now.return_value = mock_datetime.now.return_value.replace(tzinfo=ZoneInfo("Asia/Tokyo"))
            
            self.assertTrue(self.strategy._is_market_open())
            
            # 模拟工作日 16:00 (市场关闭时间)
            mock_datetime.now.return_value = datetime(2024, 1, 15, 16, 0, 0)
            mock_datetime.now.return_value = mock_datetime.now.return_value.replace(tzinfo=ZoneInfo("Asia/Tokyo"))
            
            self.assertFalse(self.strategy._is_market_open())
            
            # 模拟周末
            mock_datetime.now.return_value = datetime(2024, 1, 13, 10, 0, 0)  # 周六
            mock_datetime.now.return_value = mock_datetime.now.return_value.replace(tzinfo=ZoneInfo("Asia/Tokyo"))
            
            self.assertFalse(self.strategy._is_market_open())
    
    def test_tick_stats_update(self):
        """测试tick统计更新"""
        # 创建模拟tick数据
        mock_tick = Mock()
        mock_tick.symbol = "9984"
        
        # 模拟tick事件
        mock_event = Mock()
        mock_event.data = mock_tick
        
        # 调用on_tick
        self.strategy.on_tick(mock_event)
        
        # 验证统计更新
        self.assertEqual(self.strategy.total_tick_count, 1)
        self.assertEqual(self.strategy.tick_count["9984"], 1)
        self.assertIn("9984", self.strategy.last_tick_time)
        
        # 再次接收tick
        self.strategy.on_tick(mock_event)
        self.assertEqual(self.strategy.total_tick_count, 2)
        self.assertEqual(self.strategy.tick_count["9984"], 2)
    
    def test_monitoring_status(self):
        """测试监控状态获取"""
        # 创建模拟tick数据
        mock_tick = Mock()
        mock_tick.symbol = "9984"
        
        mock_event = Mock()
        mock_event.data = mock_tick
        
        # 接收一个tick
        self.strategy.on_tick(mock_event)
        
        # 获取监控状态
        status = self.strategy.get_monitoring_status()
        
        # 验证状态内容
        self.assertIn("current_time", status)
        self.assertIn("market_open", status)
        self.assertIn("total_tick_count", status)
        self.assertIn("system_last_tick_time", status)
        self.assertIn("symbols_status", status)
        
        # 验证股票状态
        self.assertIn("9984", status["symbols_status"])
        self.assertEqual(status["symbols_status"]["9984"]["tick_count"], 1)
        self.assertEqual(status["symbols_status"]["9984"]["status"], "normal")
    
    def test_warning_thresholds(self):
        """测试警告阈值"""
        # 设置一个很早的最后tick时间
        old_time = datetime.now(ZoneInfo("Asia/Tokyo")) - timedelta(minutes=10)
        self.strategy.system_last_tick_time = old_time
        
        # 模拟市场开放时间
        with patch.object(self.strategy, '_is_market_open', return_value=True):
            # 调用健康检查
            self.strategy._check_tick_health()
            
            # 验证应该触发严重警告（超过5分钟）
            # 注意：这里我们只是测试逻辑，实际的日志输出需要更复杂的测试设置


def run_quick_test():
    """运行快速测试"""
    print("运行Tick监控策略快速测试...")
    
    # 创建策略实例
    strategy = DummyTickMonitorStrategy(use_mock_gateway=True)
    
    try:
        print("1. 测试初始化...")
        print(f"   监控股票: {strategy.monitor_symbols}")
        print(f"   警告阈值: {strategy.warning_threshold}")
        print(f"   严重警告阈值: {strategy.critical_threshold}")
        print(f"   检查间隔: {strategy.check_interval}秒")
        
        print("\n2. 测试市场时间判断...")
        current_time = datetime.now(ZoneInfo("Asia/Tokyo"))
        is_market_open = strategy._is_market_open()
        print(f"   当前时间: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   市场状态: {'开放' if is_market_open else '关闭'}")
        
        print("\n3. 测试监控状态...")
        status = strategy.get_monitoring_status()
        print(f"   总Tick数: {status['total_tick_count']}")
        print(f"   系统最后Tick: {status['system_last_tick_time']}")
        
        print("\n4. 测试配置...")
        print(f"   市场开盘时间: {strategy.market_open_time}")
        print(f"   市场收盘时间: {strategy.market_close_time}")
        print(f"   午休时间: {strategy.lunch_start_time} - {strategy.lunch_end_time}")
        
        print("\n✅ 快速测试完成！")
        
    except Exception as e:
        print(f"❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        strategy.close()


if __name__ == "__main__":
    # 运行快速测试
    run_quick_test()
    
    # 如果要运行完整的单元测试，取消下面的注释
    # unittest.main() 