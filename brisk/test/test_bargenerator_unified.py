"""
统一的BarGenerator测试文件
整合了所有BarGenerator相关的测试用例，包括：
- 基础成交量计算测试
- 边缘情况测试
- 时间边界测试
- 价格极值测试
- 异常情况测试
"""

import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, call
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vnpy.trader.object import TickData, BarData
from vnpy.trader.constant import Exchange
from vnpy.trader.utility import ZoneInfo
from vnpy.trader.utility import BarGenerator


class BarGeneratorUnifiedTest(unittest.TestCase):
    """统一的BarGenerator测试类"""
    
    def setUp(self):
        """测试前的设置"""
        self.mock_callback = Mock()
        self.bar_generator = BarGenerator(on_bar=self.mock_callback)
        
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

    def test_basic_volume_calculation(self):
        """测试基础成交量计算"""
        # 第一个tick - 成交量为0
        tick1 = self.create_tick(
            datetime(2024, 1, 1, 9, 30, 0),
            last_price=10.0,
            volume=1000,
            turnover=5000
        )
        self.bar_generator.update_tick(tick1)
        
        # 验证第一个tick的bar
        self.assertIsNotNone(self.bar_generator.bar)
        self.assertEqual(self.bar_generator.bar.volume, 0)
        self.assertEqual(self.bar_generator.bar.turnover, 0)
        
        # 第二个tick - 计算成交量增量
        tick2 = self.create_tick(
            datetime(2024, 1, 1, 9, 30, 30),
            last_price=10.5,
            volume=1500,
            turnover=7500
        )
        self.bar_generator.update_tick(tick2)
        
        # 验证成交量增量计算
        self.assertEqual(self.bar_generator.bar.volume, 500)  # 1500 - 1000
        self.assertEqual(self.bar_generator.bar.turnover, 2500)  # 7500 - 5000

    def test_multiple_minute_bars(self):
        """测试多个分钟bar的生成"""
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
        self.assertEqual(completed_bar.volume, 500)  # 只有第二个tick的增量
        self.assertEqual(completed_bar.datetime.minute, 30)
        
        # 验证新bar的成交量
        self.assertEqual(self.bar_generator.bar.volume, 500)  # 新bar的第一个tick仍然计算增量

    def test_zero_price_tick_handling(self):
        """测试零价格tick的处理"""
        # 正常tick
        tick1 = self.create_tick(
            datetime(2024, 1, 1, 9, 30, 0),
            last_price=10.0,
            volume=1000
        )
        self.bar_generator.update_tick(tick1)
        
        # 零价格tick - 应该被忽略
        tick2 = self.create_tick(
            datetime(2024, 1, 1, 9, 30, 30),
            last_price=0.0,
            volume=1500
        )
        self.bar_generator.update_tick(tick2)
        
        # 验证零价格tick被忽略
        self.assertEqual(self.bar_generator.bar.volume, 0)
        self.assertEqual(self.bar_generator.bar.close_price, 10.0)  # 仍然是第一个tick的价格
        
        # 正常tick - 成交量计算受影响
        tick3 = self.create_tick(
            datetime(2024, 1, 1, 9, 30, 45),
            last_price=11.0,
            volume=2000
        )
        self.bar_generator.update_tick(tick3)
        
        # 验证成交量计算基于第一个tick
        self.assertEqual(self.bar_generator.bar.volume, 1000)  # 2000 - 1000

    def test_volume_decrease_handling(self):
        """测试成交量减少的处理"""
        # 第一个tick
        tick1 = self.create_tick(
            datetime(2024, 1, 1, 9, 30, 0),
            last_price=10.0,
            volume=1000
        )
        self.bar_generator.update_tick(tick1)
        
        # 成交量减少的tick
        tick2 = self.create_tick(
            datetime(2024, 1, 1, 9, 30, 30),
            last_price=10.5,
            volume=800  # 减少200
        )
        self.bar_generator.update_tick(tick2)
        
        # 验证成交量减少被忽略
        self.assertEqual(self.bar_generator.bar.volume, 0)  # max(-200, 0) = 0
        
        # 成交量增加的tick
        tick3 = self.create_tick(
            datetime(2024, 1, 1, 9, 30, 45),
            last_price=11.0,
            volume=1200  # 增加400
        )
        self.bar_generator.update_tick(tick3)
        
        # 验证只计算正值增量
        self.assertEqual(self.bar_generator.bar.volume, 400)  # 1200 - 800

    def test_turnover_calculation(self):
        """测试成交额计算"""
        # 第一个tick
        tick1 = self.create_tick(
            datetime(2024, 1, 1, 9, 30, 0),
            last_price=10.0,
            volume=1000,
            turnover=5000
        )
        self.bar_generator.update_tick(tick1)
        
        # 成交额减少的tick
        tick2 = self.create_tick(
            datetime(2024, 1, 1, 9, 30, 30),
            last_price=10.5,
            volume=1500,
            turnover=4000  # 减少1000
        )
        self.bar_generator.update_tick(tick2)
        
        # 验证成交额减少被忽略
        self.assertEqual(self.bar_generator.bar.turnover, 0)  # max(-1000, 0) = 0
        
        # 成交额增加的tick
        tick3 = self.create_tick(
            datetime(2024, 1, 1, 9, 30, 45),
            last_price=11.0,
            volume=2000,
            turnover=6000  # 增加2000
        )
        self.bar_generator.update_tick(tick3)
        
        # 验证只计算正值增量
        self.assertEqual(self.bar_generator.bar.turnover, 2000)  # 6000 - 4000

    def test_price_extremes(self):
        """测试价格极值处理"""
        # 第一个tick
        tick1 = self.create_tick(
            datetime(2024, 1, 1, 9, 30, 0),
            last_price=10.0,
            volume=1000
        )
        self.bar_generator.update_tick(tick1)
        
        # 验证开盘价
        self.assertEqual(self.bar_generator.bar.open_price, 10.0)
        self.assertEqual(self.bar_generator.bar.high_price, 10.0)
        self.assertEqual(self.bar_generator.bar.low_price, 10.0)
        self.assertEqual(self.bar_generator.bar.close_price, 10.0)
        
        # 更高价格的tick
        tick2 = self.create_tick(
            datetime(2024, 1, 1, 9, 30, 30),
            last_price=10.5,
            volume=1500
        )
        self.bar_generator.update_tick(tick2)
        
        # 验证最高价更新
        self.assertEqual(self.bar_generator.bar.high_price, 10.5)
        self.assertEqual(self.bar_generator.bar.close_price, 10.5)
        
        # 更低价格的tick
        tick3 = self.create_tick(
            datetime(2024, 1, 1, 9, 30, 45),
            last_price=9.5,
            volume=2000
        )
        self.bar_generator.update_tick(tick3)
        
        # 验证最低价更新
        self.assertEqual(self.bar_generator.bar.low_price, 9.5)
        self.assertEqual(self.bar_generator.bar.close_price, 9.5)

    def test_time_boundary_conditions(self):
        """测试时间边界条件"""
        # 9:29:59的tick
        tick1 = self.create_tick(
            datetime(2024, 1, 1, 9, 29, 59),
            last_price=10.0,
            volume=1000
        )
        self.bar_generator.update_tick(tick1)
        
        # 9:30:00的tick - 应该触发新bar
        tick2 = self.create_tick(
            datetime(2024, 1, 1, 9, 30, 0),
            last_price=10.5,
            volume=1500
        )
        self.bar_generator.update_tick(tick2)
        
        # 验证第一个bar被完成
        self.mock_callback.assert_called_once()
        completed_bar = self.mock_callback.call_args[0][0]
        self.assertEqual(completed_bar.datetime.minute, 29)
        self.assertEqual(completed_bar.datetime.second, 0)
        self.assertEqual(completed_bar.datetime.microsecond, 0)

    def test_cross_day_handling(self):
        """测试跨天处理"""
        # 上一天最后一个tick
        tick1 = self.create_tick(
            datetime(2024, 1, 1, 15, 0, 0),
            last_price=10.0,
            volume=100000
        )
        self.bar_generator.update_tick(tick1)
        
        # 下一天第一个tick
        tick2 = self.create_tick(
            datetime(2024, 1, 2, 9, 30, 0),
            last_price=10.5,
            volume=100500
        )
        self.bar_generator.update_tick(tick2)
        
        # 验证跨天处理
        self.assertEqual(self.bar_generator.bar.volume, 500)  # 新天的第一个tick仍然计算增量
        
        # 下一天第二个tick
        tick3 = self.create_tick(
            datetime(2024, 1, 2, 9, 30, 30),
            last_price=11.0,
            volume=101000
        )
        self.bar_generator.update_tick(tick3)
        
        # 验证成交量计算
        self.assertEqual(self.bar_generator.bar.volume, 1000)  # 500 + 500 (两个tick的增量)

    def test_zero_volume_ticks(self):
        """测试零成交量tick"""
        # 第一个tick
        tick1 = self.create_tick(
            datetime(2024, 1, 1, 9, 30, 0),
            last_price=10.0,
            volume=1000
        )
        self.bar_generator.update_tick(tick1)
        
        # 零成交量tick
        tick2 = self.create_tick(
            datetime(2024, 1, 1, 9, 30, 30),
            last_price=10.5,
            volume=1000  # 相同成交量
        )
        self.bar_generator.update_tick(tick2)
        
        # 验证零成交量增量
        self.assertEqual(self.bar_generator.bar.volume, 0)  # 1000 - 1000 = 0

    def test_single_tick_bar(self):
        """测试单个tick的bar"""
        # 单个tick
        tick1 = self.create_tick(
            datetime(2024, 1, 1, 9, 30, 0),
            last_price=10.0,
            volume=1000
        )
        self.bar_generator.update_tick(tick1)
        
        # 验证单个tick的bar
        self.assertIsNotNone(self.bar_generator.bar)
        self.assertEqual(self.bar_generator.bar.volume, 0)  # 第一个tick成交量为0
        self.assertEqual(self.bar_generator.bar.open_price, 10.0)
        self.assertEqual(self.bar_generator.bar.close_price, 10.0)

    def test_consecutive_zero_volume_ticks(self):
        """测试连续零成交量tick"""
        # 第一个tick
        tick1 = self.create_tick(
            datetime(2024, 1, 1, 9, 30, 0),
            last_price=10.0,
            volume=1000
        )
        self.bar_generator.update_tick(tick1)
        
        # 连续零成交量tick
        for i in range(1, 6):
            tick = self.create_tick(
                datetime(2024, 1, 1, 9, 30, i * 10),
                last_price=10.0 + i * 0.1,
                volume=1000  # 相同成交量
            )
            self.bar_generator.update_tick(tick)
        
        # 验证成交量保持为0
        self.assertEqual(self.bar_generator.bar.volume, 0)

    def test_mixed_volume_ticks(self):
        """测试混合成交量tick"""
        # 第一个tick
        tick1 = self.create_tick(
            datetime(2024, 1, 1, 9, 30, 0),
            last_price=10.0,
            volume=1000
        )
        self.bar_generator.update_tick(tick1)
        
        # 成交量增加的tick
        tick2 = self.create_tick(
            datetime(2024, 1, 1, 9, 30, 30),
            last_price=10.5,
            volume=1500
        )
        self.bar_generator.update_tick(tick2)
        
        # 零成交量tick
        tick3 = self.create_tick(
            datetime(2024, 1, 1, 9, 30, 45),
            last_price=11.0,
            volume=1500  # 相同成交量
        )
        self.bar_generator.update_tick(tick3)
        
        # 成交量减少的tick
        tick4 = self.create_tick(
            datetime(2024, 1, 1, 9, 30, 50),
            last_price=11.5,
            volume=1200  # 减少300
        )
        self.bar_generator.update_tick(tick4)
        
        # 验证成交量计算
        self.assertEqual(self.bar_generator.bar.volume, 500)  # 只有第二个tick的增量

    def test_turnover_decrease_handling(self):
        """测试成交额减少处理"""
        # 第一个tick
        tick1 = self.create_tick(
            datetime(2024, 1, 1, 9, 30, 0),
            last_price=10.0,
            volume=1000,
            turnover=5000
        )
        self.bar_generator.update_tick(tick1)
        
        # 成交额减少的tick
        tick2 = self.create_tick(
            datetime(2024, 1, 1, 9, 30, 30),
            last_price=10.5,
            volume=1500,
            turnover=4000  # 减少1000
        )
        self.bar_generator.update_tick(tick2)
        
        # 验证成交额减少被忽略
        self.assertEqual(self.bar_generator.bar.turnover, 0)  # max(-1000, 0) = 0

    def test_liquidity_gap_handling(self):
        """测试流动性间隔处理"""
        # 第一个tick
        tick1 = self.create_tick(
            datetime(2024, 1, 1, 9, 30, 0),
            last_price=10.0,
            volume=1000
        )
        self.bar_generator.update_tick(tick1)
        
        # 间隔较长的tick
        tick2 = self.create_tick(
            datetime(2024, 1, 1, 9, 30, 45),
            last_price=10.5,
            volume=1500
        )
        self.bar_generator.update_tick(tick2)
        
        # 验证正常处理
        self.assertEqual(self.bar_generator.bar.volume, 500)  # 1500 - 1000

    def test_multiple_bars_with_gaps(self):
        """测试有间隔的多个bar"""
        # 第一个bar的第一个tick
        tick1 = self.create_tick(
            datetime(2024, 1, 1, 9, 30, 0),
            last_price=10.0,
            volume=1000
        )
        self.bar_generator.update_tick(tick1)
        
        # 第一个bar的第二个tick
        tick2 = self.create_tick(
            datetime(2024, 1, 1, 9, 30, 30),
            last_price=10.5,
            volume=1500
        )
        self.bar_generator.update_tick(tick2)
        
        # 第二个bar的第一个tick - 触发bar完成
        tick3 = self.create_tick(
            datetime(2024, 1, 1, 9, 31, 0),
            last_price=11.0,
            volume=2000
        )
        self.bar_generator.update_tick(tick3)
        
        # 验证第一个bar
        self.mock_callback.assert_called_once()
        completed_bar = self.mock_callback.call_args[0][0]
        self.assertEqual(completed_bar.volume, 500)  # 只有第二个tick的增量
        
        # 第二个bar的第二个tick
        tick4 = self.create_tick(
            datetime(2024, 1, 1, 9, 31, 30),
            last_price=11.5,
            volume=2500
        )
        self.bar_generator.update_tick(tick4)
        
        # 验证第二个bar
        self.assertEqual(self.bar_generator.bar.volume, 1000)  # 2500 - 1500 (基于上一个tick)


if __name__ == "__main__":
    # 运行所有测试
    unittest.main(verbosity=2) 