"""
测试EnhancedBarGenerator的开盘成交量功能
"""

import unittest
from datetime import datetime
from unittest.mock import Mock
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vnpy.trader.object import TickData, BarData
from vnpy.trader.constant import Exchange, Interval
import sys
import os

# 添加父目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from enhanced_bargenerator import EnhancedBarGenerator


class EnhancedBarGeneratorTest(unittest.TestCase):
    """测试EnhancedBarGenerator的开盘成交量功能"""
    
    def setUp(self):
        """测试前的设置"""
        self.mock_callback = Mock()
        self.bar_generator = EnhancedBarGenerator(
            on_bar=self.mock_callback,
            enable_opening_volume=True,  # 启用开盘成交量
            enable_auto_flush=False      # 不启用强制收线
        )
        
        # 基础测试数据
        self.symbol = "test_symbol"
        self.exchange = Exchange.LOCAL
        self.gateway_name = "test_gateway"
        
    def create_tick(self, datetime_obj, last_price, volume, turnover=0):
        """创建测试用的TickData"""
        return TickData(
            symbol=self.symbol,
            exchange=self.exchange,
            datetime=datetime_obj,
            name="Test",
            volume=volume,
            turnover=turnover,
            open_interest=0,
            last_price=last_price,
            last_volume=0,
            limit_up=0,
            limit_down=0,
            open_price=0,
            high_price=0,
            low_price=0,
            pre_close=0,
            gateway_name=self.gateway_name
        )

    def test_opening_volume_calculation(self):
        """测试开盘成交量计算"""
        # 当天第一个tick - 应该直接使用成交量
        tick1 = self.create_tick(
            datetime(2024, 1, 1, 9, 30, 0),
            last_price=10.0,
            volume=1000,
            turnover=5000
        )
        self.bar_generator.update_tick(tick1)
        
        # 验证第一个tick的bar
        self.assertIsNotNone(self.bar_generator.bar)
        self.assertEqual(self.bar_generator.bar.volume, 1000)  # 直接使用成交量
        self.assertEqual(self.bar_generator.bar.turnover, 5000)  # 直接使用成交额
        
        # 第二个tick - 计算成交量增量
        tick2 = self.create_tick(
            datetime(2024, 1, 1, 9, 30, 30),
            last_price=10.5,
            volume=1500,
            turnover=7500
        )
        self.bar_generator.update_tick(tick2)
        
        # 验证成交量增量计算
        self.assertEqual(self.bar_generator.bar.volume, 1500)  # 1000 + (1500-1000)
        self.assertEqual(self.bar_generator.bar.turnover, 7500)  # 5000 + (7500-5000)

    def test_cross_day_opening_volume(self):
        """测试跨天开盘成交量"""
        # 上一天最后一个tick
        tick1 = self.create_tick(
            datetime(2024, 1, 1, 15, 0, 0),
            last_price=10.0,
            volume=100000
        )
        self.bar_generator.update_tick(tick1)
        
        # 下一天第一个tick - 应该重新计算开盘成交量
        tick2 = self.create_tick(
            datetime(2024, 1, 2, 9, 30, 0),
            last_price=10.5,
            volume=100500
        )
        self.bar_generator.update_tick(tick2)
        
        # 验证跨天处理
        self.assertEqual(self.bar_generator.bar.volume, 100500)  # 直接使用成交量
        
        # 下一天第二个tick
        tick3 = self.create_tick(
            datetime(2024, 1, 2, 9, 30, 30),
            last_price=11.0,
            volume=101000
        )
        self.bar_generator.update_tick(tick3)
        
        # 验证成交量计算
        self.assertEqual(self.bar_generator.bar.volume, 101000)  # 100500 + (101000-100500)

    def test_opening_volume_disabled(self):
        """测试禁用开盘成交量功能"""
        # 创建禁用开盘成交量的BarGenerator
        bar_generator_disabled = EnhancedBarGenerator(
            on_bar=self.mock_callback,
            enable_opening_volume=False,  # 禁用开盘成交量
            enable_auto_flush=False
        )
        
        # 第一个tick
        tick1 = self.create_tick(
            datetime(2024, 1, 1, 9, 30, 0),
            last_price=10.0,
            volume=1000
        )
        bar_generator_disabled.update_tick(tick1)
        
        # 验证第一个tick的bar成交量为0（原始行为）
        self.assertIsNotNone(bar_generator_disabled.bar)
        self.assertEqual(bar_generator_disabled.bar.volume, 0)  # 原始行为

    def test_multiple_minute_bars_with_opening_volume(self):
        """测试多个分钟bar的开盘成交量"""
        # 第一个分钟的第一个tick
        tick1 = self.create_tick(
            datetime(2024, 1, 1, 9, 30, 0),
            last_price=10.0,
            volume=1000
        )
        self.bar_generator.update_tick(tick1)
        
        # 第一个分钟的第二个tick
        tick2 = self.create_tick(
            datetime(2024, 1, 1, 9, 30, 30),
            last_price=10.5,
            volume=1500
        )
        self.bar_generator.update_tick(tick2)
        
        # 第二个分钟的第一个tick - 应该触发bar完成
        tick3 = self.create_tick(
            datetime(2024, 1, 1, 9, 31, 0),
            last_price=11.0,
            volume=2000
        )
        self.bar_generator.update_tick(tick3)
        
        # 验证第一个bar被完成
        self.mock_callback.assert_called_once()
        completed_bar = self.mock_callback.call_args[0][0]
        self.assertEqual(completed_bar.volume, 1500)  # 1000 + (1500-1000)
        self.assertEqual(completed_bar.datetime.minute, 30)
        
        # 验证新bar的成交量
        self.assertEqual(self.bar_generator.bar.volume, 500)  # 2000 - 1500 = 500增量

    def create_bar(self, datetime_obj, open_price, high_price, low_price, close_price, volume=100, turnover=1000):
        """创建测试用的BarData"""
        return BarData(
            symbol=self.symbol,
            exchange=self.exchange,
            interval=Interval.MINUTE,
            datetime=datetime_obj,
            gateway_name=self.gateway_name,
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            close_price=close_price,
            volume=volume,
            turnover=turnover,
            open_interest=0
        )

    def test_5min_alignment_start_from_9_00(self):
        """测试从9:00开始的5分钟对齐"""
        window_callback = Mock()
        bar_generator = EnhancedBarGenerator(
            on_bar=self.mock_callback,
            window=5,
            on_window_bar=window_callback,
            interval=Interval.MINUTE
        )
        
        # 9:00的bar - 应该创建window_bar，datetime=9:00
        bar1 = self.create_bar(datetime(2024, 1, 1, 9, 0, 0), 10.0, 10.5, 9.8, 10.2)
        bar_generator.update_bar(bar1)
        
        self.assertIsNotNone(bar_generator.window_bar)
        self.assertEqual(bar_generator.window_bar.datetime.minute, 0)  # 对齐到9:00
        self.assertEqual(bar_generator.window_bar.datetime.hour, 9)
        window_callback.assert_not_called()
        
        # 9:01-9:03的bar - 应该更新window_bar
        for minute in [1, 2, 3]:
            bar = self.create_bar(datetime(2024, 1, 1, 9, minute, 0), 10.0, 10.5, 9.8, 10.2)
            bar_generator.update_bar(bar)
            self.assertIsNotNone(bar_generator.window_bar)
            self.assertEqual(bar_generator.window_bar.datetime.minute, 0)  # 仍然在9:00窗口
            window_callback.assert_not_called()
        
        # 9:04的bar - 应该完成9:00的window_bar（minute % 5 == 4）
        bar4 = self.create_bar(datetime(2024, 1, 1, 9, 4, 0), 10.0, 10.5, 9.8, 10.2)
        bar_generator.update_bar(bar4)
        
        # 验证第一个window_bar被完成
        window_callback.assert_called_once()
        completed_bar = window_callback.call_args[0][0]
        self.assertEqual(completed_bar.datetime.minute, 0)  # 9:00-9:04的bar
        
        # 验证window_bar已被清空
        self.assertIsNone(bar_generator.window_bar)
        
        # 9:05的bar - 应该创建新的window_bar，datetime=9:05
        bar5 = self.create_bar(datetime(2024, 1, 1, 9, 5, 0), 10.0, 10.5, 9.8, 10.2)
        bar_generator.update_bar(bar5)
        self.assertIsNotNone(bar_generator.window_bar)
        self.assertEqual(bar_generator.window_bar.datetime.minute, 5)  # 对齐到9:05

    def test_5min_alignment_start_from_9_01(self):
        """测试从9:01开始的5分钟对齐（策略启动）"""
        window_callback = Mock()
        bar_generator = EnhancedBarGenerator(
            on_bar=self.mock_callback,
            window=5,
            on_window_bar=window_callback,
            interval=Interval.MINUTE
        )
        
        # 9:01的bar - 应该创建window_bar，datetime对齐到9:00（不是9:01）
        bar1 = self.create_bar(datetime(2024, 1, 1, 9, 1, 0), 10.0, 10.5, 9.8, 10.2)
        bar_generator.update_bar(bar1)
        
        self.assertIsNotNone(bar_generator.window_bar)
        self.assertEqual(bar_generator.window_bar.datetime.minute, 0)  # 对齐到9:00
        self.assertEqual(bar_generator.window_bar.datetime.hour, 9)
        window_callback.assert_not_called()
        
        # 9:02-9:03的bar - 应该更新window_bar
        for minute in [2, 3]:
            bar = self.create_bar(datetime(2024, 1, 1, 9, minute, 0), 10.0, 10.5, 9.8, 10.2)
            bar_generator.update_bar(bar)
            self.assertIsNotNone(bar_generator.window_bar)
            self.assertEqual(bar_generator.window_bar.datetime.minute, 0)  # 仍然在9:00窗口
            window_callback.assert_not_called()
        
        # 9:04的bar - 应该完成9:00的window_bar（minute % 5 == 4）
        bar4 = self.create_bar(datetime(2024, 1, 1, 9, 4, 0), 10.0, 10.5, 9.8, 10.2)
        bar_generator.update_bar(bar4)
        
        # 验证第一个window_bar被完成
        window_callback.assert_called_once()
        completed_bar = window_callback.call_args[0][0]
        self.assertEqual(completed_bar.datetime.minute, 0)  # 9:00-9:04的bar
        
        # 验证window_bar已被清空
        self.assertIsNone(bar_generator.window_bar)
        
        # 9:05的bar - 应该创建新的window_bar，datetime=9:05
        bar5 = self.create_bar(datetime(2024, 1, 1, 9, 5, 0), 10.0, 10.5, 9.8, 10.2)
        bar_generator.update_bar(bar5)
        self.assertIsNotNone(bar_generator.window_bar)
        self.assertEqual(bar_generator.window_bar.datetime.minute, 5)  # 对齐到9:05

    def test_5min_alignment_start_from_9_03(self):
        """测试从9:03开始的5分钟对齐"""
        window_callback = Mock()
        bar_generator = EnhancedBarGenerator(
            on_bar=self.mock_callback,
            window=5,
            on_window_bar=window_callback,
            interval=Interval.MINUTE
        )
        
        # 9:03的bar - 应该创建window_bar，datetime对齐到9:00
        bar1 = self.create_bar(datetime(2024, 1, 1, 9, 3, 0), 10.0, 10.5, 9.8, 10.2)
        bar_generator.update_bar(bar1)
        
        self.assertIsNotNone(bar_generator.window_bar)
        self.assertEqual(bar_generator.window_bar.datetime.minute, 0)  # 对齐到9:00
        window_callback.assert_not_called()
        
        # 9:04的bar - 应该完成9:00的window_bar（minute % 5 == 4）
        bar2 = self.create_bar(datetime(2024, 1, 1, 9, 4, 0), 10.0, 10.5, 9.8, 10.2)
        bar_generator.update_bar(bar2)
        
        # 验证第一个window_bar被完成
        window_callback.assert_called_once()
        completed_bar = window_callback.call_args[0][0]
        self.assertEqual(completed_bar.datetime.minute, 0)  # 9:00-9:04的bar
        
        # 验证window_bar已被清空
        self.assertIsNone(bar_generator.window_bar)
        
        # 9:05的bar - 应该创建新的window_bar，datetime=9:05
        bar5 = self.create_bar(datetime(2024, 1, 1, 9, 5, 0), 10.0, 10.5, 9.8, 10.2)
        bar_generator.update_bar(bar5)
        self.assertIsNotNone(bar_generator.window_bar)
        self.assertEqual(bar_generator.window_bar.datetime.minute, 5)  # 对齐到9:05

    def test_5min_alignment_multiple_windows(self):
        """测试多个5分钟窗口的对齐"""
        window_callback = Mock()
        bar_generator = EnhancedBarGenerator(
            on_bar=self.mock_callback,
            window=5,
            on_window_bar=window_callback,
            interval=Interval.MINUTE
        )
        
        # 9:01-9:03的bar - 第一个窗口
        for minute in [1, 2, 3]:
            bar = self.create_bar(datetime(2024, 1, 1, 9, minute, 0), 10.0, 10.5, 9.8, 10.2)
            bar_generator.update_bar(bar)
        
        # 9:04的bar - 完成第一个窗口（minute % 5 == 4）
        bar4 = self.create_bar(datetime(2024, 1, 1, 9, 4, 0), 10.0, 10.5, 9.8, 10.2)
        bar_generator.update_bar(bar4)
        self.assertEqual(window_callback.call_count, 1)
        completed_bar1 = window_callback.call_args[0][0]
        self.assertEqual(completed_bar1.datetime.minute, 0)  # 9:00-9:04的bar
        
        # 9:05-9:08的bar - 第二个窗口
        for minute in [5, 6, 7, 8]:
            bar = self.create_bar(datetime(2024, 1, 1, 9, minute, 0), 10.0, 10.5, 9.8, 10.2)
            bar_generator.update_bar(bar)
            self.assertEqual(bar_generator.window_bar.datetime.minute, 5)  # 仍然在9:05窗口
        
        # 9:09的bar - 完成第二个窗口（minute % 5 == 4）
        bar9 = self.create_bar(datetime(2024, 1, 1, 9, 9, 0), 10.0, 10.5, 9.8, 10.2)
        bar_generator.update_bar(bar9)
        self.assertEqual(window_callback.call_count, 2)
        
        # 验证第二个window_bar被完成
        completed_bar2 = window_callback.call_args[0][0]
        self.assertEqual(completed_bar2.datetime.minute, 5)  # 9:05-9:09的bar
        
        # 验证window_bar已被清空
        self.assertIsNone(bar_generator.window_bar)
        
        # 9:10的bar - 应该创建新的window_bar，datetime=9:10
        bar10 = self.create_bar(datetime(2024, 1, 1, 9, 10, 0), 10.0, 10.5, 9.8, 10.2)
        bar_generator.update_bar(bar10)
        self.assertIsNotNone(bar_generator.window_bar)
        self.assertEqual(bar_generator.window_bar.datetime.minute, 10)  # 对齐到9:10

    def test_5min_alignment_start_from_9_04(self):
        """测试从9:04开始的5分钟对齐（边界情况）"""
        window_callback = Mock()
        bar_generator = EnhancedBarGenerator(
            on_bar=self.mock_callback,
            window=5,
            on_window_bar=window_callback,
            interval=Interval.MINUTE
        )
        
        # 9:04的bar - 应该创建window_bar，datetime对齐到9:00，并立即完成（minute % 5 == 4）
        bar4 = self.create_bar(datetime(2024, 1, 1, 9, 4, 0), 10.0, 10.5, 9.8, 10.2)
        bar_generator.update_bar(bar4)
        
        # 验证window_bar被立即完成
        window_callback.assert_called_once()
        completed_bar = window_callback.call_args[0][0]
        self.assertEqual(completed_bar.datetime.minute, 0)  # 9:00-9:04的bar
        
        # 验证window_bar已被清空
        self.assertIsNone(bar_generator.window_bar)
        
        # 9:05的bar - 应该创建新的window_bar，datetime=9:05
        bar5 = self.create_bar(datetime(2024, 1, 1, 9, 5, 0), 10.0, 10.5, 9.8, 10.2)
        bar_generator.update_bar(bar5)
        self.assertIsNotNone(bar_generator.window_bar)
        self.assertEqual(bar_generator.window_bar.datetime.minute, 5)  # 对齐到9:05

    def test_missing_bar_5min_reset(self):
        """测试缺失9:04的bar时，9:05的bar是否正确reset window_bar"""
        window_callback = Mock()
        bar_generator = EnhancedBarGenerator(
            on_bar=self.mock_callback,
            window=5,
            on_window_bar=window_callback,
            interval=Interval.MINUTE
        )
        
        # 9:00-9:03的bar - 创建window_bar（9:00窗口）
        for minute in [0, 1, 2, 3]:
            bar = self.create_bar(datetime(2024, 1, 1, 9, minute, 0), 10.0, 10.5, 9.8, 10.2)
            bar_generator.update_bar(bar)
            self.assertIsNotNone(bar_generator.window_bar)
            self.assertEqual(bar_generator.window_bar.datetime.minute, 0)  # 9:00窗口
        
        # 验证window_bar存在且包含9:00-9:03的数据
        self.assertIsNotNone(bar_generator.window_bar)
        self.assertEqual(bar_generator.window_bar.datetime.minute, 0)
        window_callback.assert_not_called()
        
        # 缺失9:04的bar，直接传入9:05的bar
        # 应该强制完成旧的window_bar（9:00），并创建新的window_bar（9:05）
        bar5 = self.create_bar(datetime(2024, 1, 1, 9, 5, 0), 11.0, 11.5, 10.8, 11.2)
        bar_generator.update_bar(bar5)
        
        # 验证旧的window_bar被完成
        window_callback.assert_called_once()
        completed_bar = window_callback.call_args[0][0]
        self.assertEqual(completed_bar.datetime.minute, 0)  # 9:00-9:03的bar
        
        # 验证新的window_bar被创建，且使用9:05的open_price
        self.assertIsNotNone(bar_generator.window_bar)
        self.assertEqual(bar_generator.window_bar.datetime.minute, 5)  # 9:05窗口
        self.assertEqual(bar_generator.window_bar.open_price, 11.0)  # 使用9:05的open_price

    def test_cross_session_5min_bar_reset(self):
        """测试跨session时window_bar是否正确reset"""
        window_callback = Mock()
        bar_generator = EnhancedBarGenerator(
            on_bar=self.mock_callback,
            window=5,
            on_window_bar=window_callback,
            interval=Interval.MINUTE
        )
        
        # 早盘session：6:01的bar - 创建window_bar（6:00窗口）
        bar1 = self.create_bar(datetime(2024, 1, 1, 6, 1, 0), 10.0, 10.5, 9.8, 10.2)
        bar_generator.update_bar(bar1)
        self.assertIsNotNone(bar_generator.window_bar)
        self.assertEqual(bar_generator.window_bar.datetime.minute, 0)  # 6:00窗口
        window_callback.assert_not_called()
        
        # 跨session：8:45的bar（午盘session开始）
        # 应该强制完成旧的window_bar（6:00），并创建新的window_bar（8:45对齐到8:45）
        bar2 = self.create_bar(datetime(2024, 1, 1, 8, 45, 0), 12.0, 12.5, 11.8, 12.2)
        bar_generator.update_bar(bar2)
        
        # 验证旧的window_bar被完成
        window_callback.assert_called_once()
        completed_bar = window_callback.call_args[0][0]
        self.assertEqual(completed_bar.datetime.hour, 6)  # 6:00窗口
        self.assertEqual(completed_bar.datetime.minute, 0)
        
        # 验证新的window_bar被创建，且使用8:45的open_price
        self.assertIsNotNone(bar_generator.window_bar)
        self.assertEqual(bar_generator.window_bar.datetime.hour, 8)
        self.assertEqual(bar_generator.window_bar.datetime.minute, 45)  # 8:45窗口
        self.assertEqual(bar_generator.window_bar.open_price, 12.0)  # 使用8:45的open_price

    def test_5min_bar_validation_edge_cases(self):
        """测试5分钟bar有效性验证的edge cases"""
        window_callback = Mock()
        bar_generator = EnhancedBarGenerator(
            on_bar=self.mock_callback,
            window=5,
            on_window_bar=window_callback,
            interval=Interval.MINUTE
        )
        
        # 测试1：正常情况 - window_bar有效
        # 9:00-9:03的bar
        for minute in [0, 1, 2, 3]:
            bar = self.create_bar(datetime(2024, 1, 1, 9, minute, 0), 10.0, 10.5, 9.8, 10.2)
            bar_generator.update_bar(bar)
        
        # 验证window_bar存在
        self.assertIsNotNone(bar_generator.window_bar)
        self.assertEqual(bar_generator.window_bar.datetime.minute, 0)
        
        # 测试2：跨天情况 - window_bar应该被reset
        # 上一天9:03的bar已创建window_bar
        # 下一天9:00的bar应该创建新的window_bar
        bar_next_day = self.create_bar(datetime(2024, 1, 2, 9, 0, 0), 11.0, 11.5, 10.8, 11.2)
        bar_generator.update_bar(bar_next_day)
        
        # 验证旧的window_bar被完成（跨天）
        window_callback.assert_called()
        # 验证新的window_bar被创建
        self.assertIsNotNone(bar_generator.window_bar)
        self.assertEqual(bar_generator.window_bar.datetime.date(), datetime(2024, 1, 2).date())
        self.assertEqual(bar_generator.window_bar.datetime.minute, 0)
        self.assertEqual(bar_generator.window_bar.open_price, 11.0)
        
        # 测试3：window_bar完成后的gap期间
        # 9:00-9:03的bar创建window_bar
        window_callback2 = Mock()
        bar_generator2 = EnhancedBarGenerator(
            on_bar=self.mock_callback,
            window=5,
            on_window_bar=window_callback2,
            interval=Interval.MINUTE
        )
        
        for minute in [0, 1, 2, 3]:
            bar = self.create_bar(datetime(2024, 1, 1, 9, minute, 0), 10.0, 10.5, 9.8, 10.2)
            bar_generator2.update_bar(bar)
        
        # 9:04的bar完成window_bar
        bar4 = self.create_bar(datetime(2024, 1, 1, 9, 4, 0), 10.0, 10.5, 9.8, 10.2)
        bar_generator2.update_bar(bar4)
        
        # 验证window_bar被完成并清空
        self.assertIsNone(bar_generator2.window_bar)
        
        # 在9:04完成到9:05创建之间的gap期间，window_bar应该是None
        # 这是正常的，应该fallback到1分钟bar


if __name__ == "__main__":
    # 运行所有测试
    unittest.main(verbosity=2) 