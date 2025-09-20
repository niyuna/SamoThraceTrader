#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from unittest.mock import Mock, patch
from datetime import datetime

from brisk.hft_bb_reversal_strategy import HFTBBReversalStrategy


class TestSingleStockMaxPosition(unittest.TestCase):
    """测试单只股票最大持仓金额功能"""
    
    def setUp(self):
        """设置测试环境"""
        self.strategy = HFTBBReversalStrategy()
        self.strategy.write_log = Mock()
        self.strategy.gateway = Mock()
        
    def test_single_stock_max_position_initialization(self):
        """测试single_stock_max_position参数初始化"""
        self.assertEqual(self.strategy.single_stock_max_position, 1_000_000)
        
    def test_create_hft_context_uses_calculate_position_size(self):
        """测试create_hft_context使用calculate_position_size计算position_size"""
        # Mock get_stock_prev_close 返回不同的价格
        with patch.object(self.strategy, 'get_stock_prev_close') as mock_get_price:
            mock_get_price.return_value = 1000.0  # 1000日元
            
            # 创建 context
            context = self.strategy.create_hft_context("9984")
            
            # 验证 position_size 被正确计算
            # 期望: round(1000000 / 1000 / 100) * 100 = 1000
            expected_position_size = 1000
            self.assertEqual(context.position_size, expected_position_size)
            
            # 验证日志输出
            self.strategy.write_log.assert_any_call("Created HFT context for symbol 9984 with position_size=1000")
    
    def test_create_hft_context_different_prices(self):
        """测试不同价格股票的position_size计算"""
        test_cases = [
            (500.0, 2000),   # 500日元 -> 2000股
            (2000.0, 500),   # 2000日元 -> 500股
            (100.0, 10000),  # 100日元 -> 10000股
            (5000.0, 200),   # 5000日元 -> 200股
        ]
        
        for price, expected_position_size in test_cases:
            with patch.object(self.strategy, 'get_stock_prev_close') as mock_get_price:
                mock_get_price.return_value = price
                
                # 创建 context
                context = self.strategy.create_hft_context(f"TEST{int(price)}")
                
                # 验证 position_size 计算正确
                self.assertEqual(context.position_size, expected_position_size)
    
    def test_create_hft_context_price_zero_fallback(self):
        """测试价格为0时的fallback逻辑"""
        with patch.object(self.strategy, 'get_stock_prev_close') as mock_get_price:
            mock_get_price.return_value = 0.0  # 价格为0
            
            # 创建 context
            context = self.strategy.create_hft_context("9984")
            
            # 验证使用默认值100
            self.assertEqual(context.position_size, 100)
    
    def test_create_hft_context_price_negative_fallback(self):
        """测试价格为负数时的fallback逻辑"""
        with patch.object(self.strategy, 'get_stock_prev_close') as mock_get_price:
            mock_get_price.return_value = -100.0  # 价格为负数
            
            # 创建 context
            context = self.strategy.create_hft_context("9984")
            
            # 验证使用默认值100
            self.assertEqual(context.position_size, 100)
    
    def test_update_parameters_single_stock_max_position(self):
        """测试更新single_stock_max_position参数"""
        # 创建一些现有的 context
        with patch.object(self.strategy, 'get_stock_prev_close') as mock_get_price:
            mock_get_price.return_value = 1000.0
            context1 = self.strategy.create_hft_context("9984")
            context2 = self.strategy.create_hft_context("6098")
            
            # 验证初始 position_size
            self.assertEqual(context1.position_size, 1000)
            self.assertEqual(context2.position_size, 1000)
            
            # 更新 single_stock_max_position 参数
            new_params = {'single_stock_max_position': 2_000_000}
            self.strategy.update_parameters(new_params)
            
            # 验证参数已更新
            self.assertEqual(self.strategy.single_stock_max_position, 2_000_000)
            
            # 验证现有 context 的 position_size 已重新计算
            # 期望: round(2000000 / 1000 / 100) * 100 = 2000
            self.assertEqual(context1.position_size, 2000)
            self.assertEqual(context2.position_size, 2000)
            
            # 验证日志输出
            self.strategy.write_log.assert_any_call("参数 single_stock_max_position 更新: 1000000 -> 2000000")
            self.strategy.write_log.assert_any_call("更新 9984 的持仓数量: 2000")
            self.strategy.write_log.assert_any_call("更新 6098 的持仓数量: 2000")
    
    def test_update_parameters_partial_update(self):
        """测试部分参数更新（不包含single_stock_max_position）"""
        # 创建 context
        with patch.object(self.strategy, 'get_stock_prev_close') as mock_get_price:
            mock_get_price.return_value = 1000.0
            context = self.strategy.create_hft_context("9984")
            original_position_size = context.position_size
            
            # 只更新其他参数
            new_params = {'bb_entry_std_multiplier': 2.5}
            self.strategy.update_parameters(new_params)
            
            # 验证 single_stock_max_position 和 position_size 没有改变
            self.assertEqual(self.strategy.single_stock_max_position, 1_000_000)
            self.assertEqual(context.position_size, original_position_size)
    
    def test_calculate_position_size_minimum_value(self):
        """测试calculate_position_size的最小值限制"""
        with patch.object(self.strategy, 'get_stock_prev_close') as mock_get_price:
            # 设置一个很高的价格，使得计算结果小于100
            mock_get_price.return_value = 20000.0  # 20000日元
            
            # 创建 context
            context = self.strategy.create_hft_context("9984")
            
            # 验证 position_size 至少为100（最小值限制）
            # 计算: round(1000000 / 20000 / 100) * 100 = 0，但最小值为100
            self.assertEqual(context.position_size, 100)


if __name__ == '__main__':
    unittest.main()
