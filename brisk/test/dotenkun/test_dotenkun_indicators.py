"""
Dotenkun指标测试
"""

import unittest
import sys
import os
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenkun_indicators import DotenkunIndicator
from vnpy.trader.object import BarData
from vnpy.trader.constant import Exchange, Interval


class TestDotenkunIndicator(unittest.TestCase):
    """测试DotenkunIndicator"""
    
    def setUp(self):
        """测试前的准备工作"""
        self.symbol = "161030023"
        self.size = 10
        self.hl_range_period = 5
    
    def test_initialization(self):
        """测试初始化"""
        indicator = DotenkunIndicator(symbol=self.symbol, size=self.size, hl_range_period=self.hl_range_period)
        
        self.assertEqual(indicator.symbol, self.symbol)
        self.assertEqual(indicator.hl_range_period, self.hl_range_period)
        self.assertEqual(len(indicator.hl_ranges), 0)
        self.assertEqual(indicator.latest_hl_range_ma, 0.0)
    
    def test_hl_range_count_check(self):
        """测试hl_range_count检查"""
        indicator = DotenkunIndicator(symbol=self.symbol, size=self.size, hl_range_period=self.hl_range_period)
        
        # 添加少于5个bar
        for i in range(4):
            bar = BarData(
                symbol=self.symbol,
                exchange=Exchange.TSE,
                datetime=datetime.now(),
                interval=None,  # 5分钟bar的interval通常是None
                volume=1000,
                open_price=100.0 + i,
                high_price=101.0 + i,
                low_price=99.0 + i,
                close_price=100.5 + i,
                gateway_name="TEST"
            )
            indicator.update_bar(bar)
        
        indicators = indicator.get_indicators()
        self.assertLess(indicators['hl_range_count'], 5)
        self.assertEqual(indicators['hl_range_count'], 4)
        
        # 添加第5个bar
        bar = BarData(
            symbol=self.symbol,
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            interval=None,
            volume=1000,
            open_price=104.0,
            high_price=105.0,
            low_price=103.0,
            close_price=104.5,
            gateway_name="TEST"
        )
        indicator.update_bar(bar)
        
        indicators = indicator.get_indicators()
        self.assertEqual(indicators['hl_range_count'], 5)
    
    def test_hl_range_ma_calculation(self):
        """测试HL Range MA计算"""
        indicator = DotenkunIndicator(symbol=self.symbol, size=self.size, hl_range_period=self.hl_range_period)
        
        # 添加5个bar，每个bar的high-low都是2.0
        for i in range(5):
            bar = BarData(
                symbol=self.symbol,
                exchange=Exchange.TSE,
                datetime=datetime.now(),
                interval=None,
                volume=1000,
                open_price=100.0 + i,
                high_price=101.0 + i,  # high = open + 1.0
                low_price=99.0 + i,    # low = open - 1.0
                close_price=100.5 + i,
                gateway_name="TEST"
            )
            indicator.update_bar(bar)
        
        indicators = indicator.get_indicators()
        # 每个bar的high-low = 2.0，平均值应该是2.0
        self.assertEqual(indicators['hl_range_ma_5'], 2.0)
        self.assertEqual(indicators['hl_range_count'], 5)
    
    def test_hl_range_ma_with_different_ranges(self):
        """测试不同high-low范围的MA计算"""
        indicator = DotenkunIndicator(symbol=self.symbol, size=self.size, hl_range_period=self.hl_range_period)
        
        # 添加5个bar，high-low分别为1.0, 2.0, 3.0, 4.0, 5.0
        ranges = [1.0, 2.0, 3.0, 4.0, 5.0]
        for i, range_val in enumerate(ranges):
            bar = BarData(
                symbol=self.symbol,
                exchange=Exchange.TSE,
                datetime=datetime.now(),
                interval=None,
                volume=1000,
                open_price=100.0 + i,
                high_price=100.0 + i + range_val / 2,
                low_price=100.0 + i - range_val / 2,
                close_price=100.5 + i,
                gateway_name="TEST"
            )
            indicator.update_bar(bar)
        
        indicators = indicator.get_indicators()
        # 平均值 = (1.0 + 2.0 + 3.0 + 4.0 + 5.0) / 5 = 3.0
        self.assertEqual(indicators['hl_range_ma_5'], 3.0)
    
    def test_hl_range_ma_rolling_window(self):
        """测试滚动窗口功能"""
        indicator = DotenkunIndicator(symbol=self.symbol, size=self.size, hl_range_period=self.hl_range_period)
        
        # 添加5个bar，high-low都是2.0
        for i in range(5):
            bar = BarData(
                symbol=self.symbol,
                exchange=Exchange.TSE,
                datetime=datetime.now(),
                interval=None,
                volume=1000,
                open_price=100.0 + i,
                high_price=101.0 + i,
                low_price=99.0 + i,
                close_price=100.5 + i,
                gateway_name="TEST"
            )
            indicator.update_bar(bar)
        
        indicators = indicator.get_indicators()
        self.assertEqual(indicators['hl_range_ma_5'], 2.0)
        
        # 添加第6个bar，high-low为10.0
        bar = BarData(
            symbol=self.symbol,
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            interval=None,
            volume=1000,
            open_price=105.0,
            high_price=110.0,  # high-low = 10.0
            low_price=100.0,
            close_price=105.5,
            gateway_name="TEST"
        )
        indicator.update_bar(bar)
        
        indicators = indicator.get_indicators()
        # 现在应该只保留最后5个，平均值 = (2.0 + 2.0 + 2.0 + 2.0 + 10.0) / 5 = 3.6
        self.assertEqual(indicators['hl_range_ma_5'], 3.6)
        self.assertEqual(indicators['hl_range_count'], 5)  # 仍然只有5个
    
    def test_ignore_1minute_bar(self):
        """测试忽略1分钟bar"""
        indicator = DotenkunIndicator(symbol=self.symbol, size=self.size, hl_range_period=self.hl_range_period)
        
        # 添加1分钟bar（应该被忽略）
        bar_1min = BarData(
            symbol=self.symbol,
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            interval=Interval.MINUTE,  # 1分钟bar
            volume=1000,
            open_price=100.0,
            high_price=101.0,
            low_price=99.0,
            close_price=100.5,
            gateway_name="TEST"
        )
        indicator.update_bar(bar_1min)
        
        indicators = indicator.get_indicators()
        # 1分钟bar应该被忽略，hl_range_count应该还是0
        self.assertEqual(indicators['hl_range_count'], 0)
        
        # 添加5分钟bar（应该被处理）
        bar_5min = BarData(
            symbol=self.symbol,
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            interval=None,  # 5分钟bar
            volume=1000,
            open_price=100.0,
            high_price=101.0,
            low_price=99.0,
            close_price=100.5,
            gateway_name="TEST"
        )
        indicator.update_bar(bar_5min)
        
        indicators = indicator.get_indicators()
        # 5分钟bar应该被处理
        self.assertEqual(indicators['hl_range_count'], 1)
    
    def test_is_inited(self):
        """测试is_inited方法"""
        indicator = DotenkunIndicator(symbol=self.symbol, size=self.size, hl_range_period=self.hl_range_period)
        
        # 初始状态
        self.assertFalse(indicator.is_inited())
        
        # 添加少于5个bar
        for i in range(4):
            bar = BarData(
                symbol=self.symbol,
                exchange=Exchange.TSE,
                datetime=datetime.now(),
                interval=None,
                volume=1000,
                open_price=100.0 + i,
                high_price=101.0 + i,
                low_price=99.0 + i,
                close_price=100.5 + i,
                gateway_name="TEST"
            )
            indicator.update_bar(bar)
        
        self.assertFalse(indicator.is_inited())
        
        # 添加第5个bar
        bar = BarData(
            symbol=self.symbol,
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            interval=None,
            volume=1000,
            open_price=104.0,
            high_price=105.0,
            low_price=103.0,
            close_price=104.5,
            gateway_name="TEST"
        )
        indicator.update_bar(bar)
        
        self.assertTrue(indicator.is_inited())


if __name__ == '__main__':
    unittest.main()
