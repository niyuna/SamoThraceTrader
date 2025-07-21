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
from vnpy.trader.constant import Exchange
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


if __name__ == "__main__":
    # 运行所有测试
    unittest.main(verbosity=2) 