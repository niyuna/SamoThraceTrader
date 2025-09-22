#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import unittest
from unittest.mock import Mock, patch
from datetime import datetime, time

from hft_bb_reversal_strategy import HFTBBReversalStrategy


class TestActiveEntryOrderXCondition(unittest.TestCase):
    """测试活跃entry订单的X条件逻辑"""
    
    def setUp(self):
        """设置测试环境"""
        self.strategy = HFTBBReversalStrategy()
        self.strategy.write_log = Mock()
        
        # 添加测试股票
        self.strategy.add_symbol("9984")
        self.context = self.strategy.get_hft_context("9984")
        
        # 设置BB levels
        self.context.bb_levels = {
            'std': 0.8,
            'middle': 1000.0,
            'upper': 1003.0,
            'lower': 997.0,
            'exit_long': 1001.0,
            'exit_short': 999.0
        }
        
    def test_x_condition_with_active_entry_order(self):
        """测试有活跃entry订单时仍然进行正常X条件检查"""
        # 设置活跃的entry订单
        self.context.entry_order_id = "test_order_123"
        
        # 设置早上时间（满足时间窗口）
        morning_time = datetime(2024, 1, 1, 9, 20)
        
        with patch('hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = morning_time
            result = self.strategy.check_x_condition("9984")
        
        # 现在有entry订单时不再有优先级，需要满足所有条件
        self.assertTrue(result)
        self.strategy.write_log.assert_any_call(
            "X条件检查通过: 9984 morning std_pct=0.000800 morning时段股价0符合4000以下限制 允许方向: ['long', 'short']"
        )
        
    def test_x_condition_with_active_entry_order_ignores_position(self):
        """测试有活跃entry订单时不再忽略持仓状态"""
        # 设置活跃的entry订单
        self.context.entry_order_id = "test_order_123"
        
        # 设置模拟持仓（entry时间在窗口内且方向匹配，应该允许交易）
        self.strategy.simulated_positions["9984"] = {
            'long': True, 
            'short': False,
            'long_entry_time': datetime(2024, 1, 1, 9, 15, 0),  # 在morning窗口内
            'short_entry_time': None,
            'long_exit_time': None,
            'short_exit_time': None
        }
        
        # 设置早上时间（满足时间窗口）
        morning_time = datetime(2024, 1, 1, 9, 20)
        
        with patch('hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = morning_time
            result = self.strategy.check_x_condition("9984")
        
        # 由于entry时间在窗口内且方向匹配，应该允许交易
        self.assertTrue(result)
        self.strategy.write_log.assert_any_call(
            "X条件检查通过: 9984 模拟持仓方向匹配，允许long交易"
        )
        
    def test_x_condition_with_active_entry_order_ignores_time_window(self):
        """测试有活跃entry订单时不再忽略时间窗口限制"""
        # 设置活跃的entry订单
        self.context.entry_order_id = "test_order_123"
        
        # 设置非交易时间（通常会导致X条件失败）
        outside_time = datetime(2024, 1, 1, 10, 0)  # 不在任何交易窗口内
        
        with patch('hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = outside_time
            result = self.strategy.check_x_condition("9984")
        
        # 现在有entry订单时不再有优先级，时间窗口外应该失败
        self.assertFalse(result)
        self.strategy.write_log.assert_any_call(
            "X条件检查失败: 当前时间不在交易窗口内"
        )
        
    def test_x_condition_with_active_entry_order_ignores_std_pct(self):
        """测试有活跃entry订单时不再忽略std_pct限制"""
        # 设置活跃的entry订单
        self.context.entry_order_id = "test_order_123"
        
        # 设置较低的std值，使其低于早上阈值
        self.context.bb_levels['std'] = 0.1  # std_pct = 0.1/1000 = 0.0001 < 0.00073
        
        # 设置早上时间（满足时间窗口但std_pct不足）
        morning_time = datetime(2024, 1, 1, 9, 20)
        
        with patch('hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = morning_time
            result = self.strategy.check_x_condition("9984")
        
        # 现在有entry订单时不再有优先级，std_pct不足应该失败
        self.assertFalse(result)
        self.strategy.write_log.assert_any_call(
            "X条件检查失败: 9984 std_pct=0.000100 低于morning阈值0.000700"
        )
        
    def test_x_condition_without_active_entry_order_normal_check(self):
        """测试没有活跃entry订单时进行正常检查"""
        # 确保没有活跃的entry订单
        self.context.entry_order_id = ""
        
        # 设置早上时间（满足时间窗口和std_pct）
        morning_time = datetime(2024, 1, 1, 9, 20)
        
        with patch('hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = morning_time
            result = self.strategy.check_x_condition("9984")
        
        # 应该通过正常的X条件检查
        self.assertTrue(result)
        self.strategy.write_log.assert_any_call(
            "X条件检查通过: 9984 morning std_pct=0.000800 morning时段股价0符合4000以下限制 允许方向: ['long', 'short']"
        )
        
    def test_x_condition_without_active_entry_order_with_position(self):
        """测试没有活跃entry订单但有持仓时X条件失败"""
        # 确保没有活跃的entry订单
        self.context.entry_order_id = ""
        
        # 设置模拟持仓（entry时间在窗口内且方向匹配，应该允许交易）
        self.strategy.simulated_positions["9984"] = {
            'long': True, 
            'short': False,
            'long_entry_time': datetime(2024, 1, 1, 9, 15, 0),  # 在morning窗口内
            'short_entry_time': None,
            'long_exit_time': None,
            'short_exit_time': None
        }
        
        # 设置早上时间（满足时间窗口和std_pct）
        morning_time = datetime(2024, 1, 1, 9, 20)
        
        with patch('hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = morning_time
            result = self.strategy.check_x_condition("9984")
        
        # 由于entry时间在窗口内且方向匹配，应该允许交易
        self.assertTrue(result)
        self.strategy.write_log.assert_any_call(
            "X条件检查通过: 9984 模拟持仓方向匹配，允许long交易"
        )
        
    def test_x_condition_empty_entry_order_id(self):
        """测试entry_order_id为空字符串时进行正常检查"""
        # 设置空的entry_order_id
        self.context.entry_order_id = ""
        
        # 设置早上时间（满足时间窗口和std_pct）
        morning_time = datetime(2024, 1, 1, 9, 20)
        
        with patch('hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = morning_time
            result = self.strategy.check_x_condition("9984")
        
        # 应该通过正常的X条件检查
        self.assertTrue(result)
        self.strategy.write_log.assert_any_call(
            "X条件检查通过: 9984 morning std_pct=0.000800 morning时段股价0符合4000以下限制 允许方向: ['long', 'short']"
        )
        
    def test_x_condition_priority_order(self):
        """测试X条件检查的优先级顺序（现在entry订单不再有优先级）"""
        # 设置活跃的entry订单
        self.context.entry_order_id = "test_order_123"
        
        # 设置所有会导致X条件失败的条件
        # 1. 不在eligible_stocks中
        self.strategy.eligible_stocks.discard("9984")
        
        # 2. 有持仓
        self.strategy.simulated_positions["9984"] = {
            'long': True, 
            'short': False,
            'long_entry_time': datetime(2024, 1, 1, 9, 15, 0),
            'short_entry_time': None,
            'long_exit_time': None,
            'short_exit_time': None
        }
        
        # 3. 非交易时间
        outside_time = datetime(2024, 1, 1, 10, 0)
        
        # 4. 低std_pct
        self.context.bb_levels['std'] = 0.1
        
        with patch('hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = outside_time
            result = self.strategy.check_x_condition("9984")
        
        # 现在有entry订单时不再有优先级，应该失败
        self.assertFalse(result)
        self.strategy.write_log.assert_any_call(
            "X条件检查失败: 9984 不在eligible_stocks中"
        )


if __name__ == '__main__':
    unittest.main()
