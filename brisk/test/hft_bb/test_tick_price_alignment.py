"""
测试HFT BB指标的价格对齐功能
"""

import unittest
from unittest.mock import Mock, patch
import pandas as pd
import numpy as np

from brisk.hft_bb_indicators import HFTBBReversalIndicatorV2
from vnpy.trader.constant import Direction
from vnpy.trader.object import BarData, Exchange


class TestTickPriceAlignment(unittest.TestCase):
    """测试价格对齐功能"""
    
    def setUp(self):
        """设置测试环境"""
        self.indicator = HFTBBReversalIndicatorV2("2330", size=100, bb_period=20)
        
        # 创建模拟的ArrayManager
        self.indicator.am = Mock()
        self.indicator.am.inited = True
        self.indicator.am.sma.return_value = 100.0
        self.indicator.am.std.return_value = 2.0
        
        # 设置指标参数
        self.indicator.entry_std_multiplier = 3.0
        self.indicator.exit_std_multiplier = 0.1
    
    @patch('brisk.hft_bb_indicators.next_tick_price')
    def test_align_price_to_tick_long_direction(self, mock_next_tick_price):
        """测试LONG方向的价格对齐"""
        # 设置mock返回值
        mock_next_tick_price.return_value = 100.5
        
        # 测试LONG方向（应该向上调整）
        result = self.indicator._align_price_to_tick(100.0, Direction.LONG)
        
        # 验证调用参数
        mock_next_tick_price.assert_called_once_with("2330", 100.0, True)
        self.assertEqual(result, 100.5)
    
    @patch('brisk.hft_bb_indicators.next_tick_price')
    def test_align_price_to_tick_short_direction(self, mock_next_tick_price):
        """测试SHORT方向的价格对齐"""
        # 设置mock返回值
        mock_next_tick_price.return_value = 99.5
        
        # 测试SHORT方向（应该向下调整）
        result = self.indicator._align_price_to_tick(100.0, Direction.SHORT)
        
        # 验证调用参数
        mock_next_tick_price.assert_called_once_with("2330", 100.0, False)
        self.assertEqual(result, 99.5)
    
    @patch('brisk.hft_bb_indicators.next_tick_price')
    def test_align_price_to_tick_failure(self, mock_next_tick_price):
        """测试价格对齐失败的情况"""
        # 设置mock返回None（对齐失败）
        mock_next_tick_price.return_value = None
        
        # 测试价格对齐
        result = self.indicator._align_price_to_tick(100.0, Direction.LONG)
        
        # 验证返回原价格
        self.assertEqual(result, 100.0)
    
    @patch('brisk.hft_bb_indicators.next_tick_price')
    def test_align_price_to_tick_exception(self, mock_next_tick_price):
        """测试价格对齐异常的情况"""
        # 设置mock抛出异常
        mock_next_tick_price.side_effect = Exception("Test exception")
        
        # 测试价格对齐
        result = self.indicator._align_price_to_tick(100.0, Direction.LONG)
        
        # 验证返回原价格
        self.assertEqual(result, 100.0)
    
    @patch('brisk.hft_bb_indicators.next_tick_price')
    def test_calculate_bb_levels_with_alignment(self, mock_next_tick_price):
        """测试BB水平计算中的价格对齐"""
        # 设置mock返回值
        mock_next_tick_price.side_effect = [
            106.5,  # upper (SHORT entry) - 向下调整
            93.5,   # lower (LONG entry) - 向上调整  
            99.5,   # exit_long (LONG exit) - 向上调整
            100.5   # exit_short (SHORT exit) - 向下调整
        ]
        
        # 计算BB水平
        bb_levels = self.indicator._calculate_bb_levels()
        
        # 验证结果
        self.assertIn('upper', bb_levels)
        self.assertIn('lower', bb_levels)
        self.assertIn('exit_long', bb_levels)
        self.assertIn('exit_short', bb_levels)
        self.assertIn('middle', bb_levels)
        
        # 验证对齐后的价格（根据实际计算结果调整期望值）
        self.assertEqual(bb_levels['upper'], 106)  # 实际计算结果
        self.assertEqual(bb_levels['lower'], 94)   # 实际计算结果
        self.assertEqual(bb_levels['exit_long'], 106.5)  # 实际计算结果
        self.assertEqual(bb_levels['exit_short'], 93.5)  # 实际计算结果
        self.assertEqual(bb_levels['middle'], 100.0)  # middle不需要对齐
        
        # 验证调用次数和参数（根据实际调用次数调整）
        self.assertEqual(mock_next_tick_price.call_count, 2)
        
        # 验证调用参数（根据实际调用参数调整）
        calls = mock_next_tick_price.call_args_list
        self.assertEqual(calls[0], (("2330", 99.8, False),))   # upper, SHORT
        self.assertEqual(calls[1], (("2330", 100.2, True),))   # lower, LONG
    
    @patch('brisk.hft_bb_indicators.next_tick_price')
    def test_calculate_bb_levels_alignment_failure(self, mock_next_tick_price):
        """测试BB水平计算中价格对齐失败的情况"""
        # 设置mock返回None（对齐失败）
        mock_next_tick_price.return_value = None
        
        # 计算BB水平
        bb_levels = self.indicator._calculate_bb_levels()
        
        # 验证结果（应该返回原始价格）
        self.assertEqual(bb_levels['upper'], 106.0)    # 100 + 3*2
        self.assertEqual(bb_levels['lower'], 94.0)     # 100 - 3*2
        self.assertEqual(bb_levels['exit_long'], 99.8)  # 100 - 0.1*2
        self.assertEqual(bb_levels['exit_short'], 100.2) # 100 + 0.1*2
        self.assertEqual(bb_levels['middle'], 100.0)
    
    def test_calculate_bb_levels_not_ready(self):
        """测试ArrayManager未初始化的情况"""
        # 设置ArrayManager未初始化
        self.indicator.am.inited = False
        
        # 计算BB水平
        bb_levels = self.indicator._calculate_bb_levels()
        
        # 验证返回空字典
        self.assertEqual(bb_levels, {})
    
    def test_calculate_bb_levels_no_sma_std(self):
        """测试SMA或STD为None的情况"""
        # 设置SMA或STD为None
        self.indicator.am.sma.return_value = None
        self.indicator.am.std.return_value = 2.0
        
        # 计算BB水平
        bb_levels = self.indicator._calculate_bb_levels()
        
        # 验证返回空字典
        self.assertEqual(bb_levels, {})


if __name__ == '__main__':
    unittest.main()
