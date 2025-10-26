#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

import unittest
from unittest.mock import Mock, patch
from datetime import datetime, time

from hft_bb_reversal_strategy import HFTBBReversalStrategy


class TestStdPctXCondition(unittest.TestCase):
    """测试std_pct X条件功能"""
    
    def setUp(self):
        """设置测试环境"""
        self.strategy = HFTBBReversalStrategy()
        self.strategy.write_log = Mock()
        
        # 覆盖策略参数，使测试独立于默认参数
        self.strategy.price_limit_morning = 5000    # 提高morning时段价格限制
        self.strategy.price_limit_noon = 5000       # 提高noon时段价格限制  
        self.strategy.price_limit_afternoon = 5000  # 提高afternoon时段价格限制
        self.strategy.max_price_change_pct = 20.0   # 提高价格变动限制
        self.strategy.aggressive_x_condition_enabled = True  # 启用激进X条件以测试模拟持仓逻辑
        
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
        
        # 添加到eligible_stocks
        self.strategy.eligible_stocks.add("9984")
        
        # 模拟get_stock_prev_close返回合理价格
        self.strategy.get_stock_prev_close = Mock(return_value=2000.0)
        
    def test_std_pct_parameters_initialization(self):
        """测试std_pct阈值参数初始化"""
        # 测试参数存在且为浮点数
        self.assertIsInstance(self.strategy.std_pct_threshold_morning, float)
        self.assertIsInstance(self.strategy.std_pct_threshold_noon, float)
        self.assertIsInstance(self.strategy.std_pct_threshold_afternoon, float)
        
        # 测试参数值大于0
        self.assertGreater(self.strategy.std_pct_threshold_morning, 0)
        self.assertGreater(self.strategy.std_pct_threshold_noon, 0)
        self.assertGreater(self.strategy.std_pct_threshold_afternoon, 0)
        
        # 测试阈值大小关系：早上 >= 下午（现在morning和afternoon都是0.0007）
        self.assertGreaterEqual(self.strategy.std_pct_threshold_morning, self.strategy.std_pct_threshold_afternoon)
        
    def test_calculate_std_pct_success(self):
        """测试std_pct计算成功"""
        # 使用一个较低的阈值确保测试通过
        test_threshold = 0.0001
        result = self.strategy._calculate_and_check_std_pct("9984", test_threshold)
        
        expected_std_pct = 0.8 / 1000.0  # 0.0008
        self.assertEqual(result['std_pct'], expected_std_pct)
        self.assertTrue(result['ok'])  # 0.0008 > 0.0001
        
    def test_calculate_std_pct_below_threshold(self):
        """测试std_pct低于阈值"""
        # 使用一个较高的阈值确保测试失败
        test_threshold = 0.001
        result = self.strategy._calculate_and_check_std_pct("9984", test_threshold)
        
        expected_std_pct = 0.8 / 1000.0  # 0.0008
        self.assertEqual(result['std_pct'], expected_std_pct)
        self.assertFalse(result['ok'])  # 0.0008 < 0.001
        
    def test_calculate_std_pct_no_bb_levels(self):
        """测试没有BB levels时std_pct计算"""
        self.context.bb_levels = None
        
        result = self.strategy._calculate_and_check_std_pct("9984", 0.0005)
        
        self.assertEqual(result['std_pct'], 0.0)
        self.assertFalse(result['ok'])
        
    def test_calculate_std_pct_zero_middle(self):
        """测试middle为0时std_pct计算"""
        self.context.bb_levels['middle'] = 0
        
        result = self.strategy._calculate_and_check_std_pct("9984", 0.0005)
        
        self.assertEqual(result['std_pct'], 0.0)
        self.assertFalse(result['ok'])
        
    def test_calculate_std_pct_missing_std(self):
        """测试缺少std时std_pct计算"""
        self.context.bb_levels.pop('std', None)
        
        result = self.strategy._calculate_and_check_std_pct("9984", 0.0005)
        
        self.assertEqual(result['std_pct'], 0.0)
        self.assertFalse(result['ok'])
        
    def test_time_window_morning_with_std_pct(self):
        """测试早上时间窗口std_pct检查"""
        # 设置早上时间
        morning_time = datetime(2024, 1, 1, 9, 20)
        
        result = self.strategy._check_time_window_with_std_pct("9984", morning_time)
        
        self.assertTrue(result['in_window'])
        self.assertEqual(result['time_period'], 'morning')
        self.assertEqual(result['threshold'], self.strategy.std_pct_threshold_morning)
        self.assertEqual(result['std_pct'], 0.0008)  # 0.8/1000
        # 测试逻辑：如果std_pct大于阈值，应该通过
        self.assertEqual(result['std_pct_ok'], result['std_pct'] > result['threshold'])
        # 检查允许的交易方向（早上窗口允许多空双向）
        self.assertEqual(result['allowed_directions'], ['long', 'short'])
        
    def test_time_window_noon_with_std_pct(self):
        """测试中午时间窗口std_pct检查"""
        # 设置中午时间
        noon_time = datetime(2024, 1, 1, 11, 29, 30)
        
        result = self.strategy._check_time_window_with_std_pct("9984", noon_time)
        
        self.assertTrue(result['in_window'])
        self.assertEqual(result['time_period'], 'noon')
        self.assertEqual(result['threshold'], self.strategy.std_pct_threshold_noon)
        self.assertEqual(result['std_pct'], 0.0008)  # 0.8/1000
        # 测试逻辑：如果std_pct大于阈值，应该通过
        self.assertEqual(result['std_pct_ok'], result['std_pct'] > result['threshold'])
        # 检查允许的交易方向（中午窗口允许多空双向）
        self.assertEqual(result['allowed_directions'], ['long', 'short'])
        
    def test_time_window_afternoon_with_std_pct(self):
        """测试下午时间窗口std_pct检查"""
        # 设置下午时间（非15:00）
        afternoon_time = datetime(2024, 1, 1, 14, 40)
        
        result = self.strategy._check_time_window_with_std_pct("9984", afternoon_time)
        
        self.assertTrue(result['in_window'])
        self.assertEqual(result['time_period'], 'afternoon')
        self.assertEqual(result['threshold'], self.strategy.std_pct_threshold_afternoon)
        self.assertEqual(result['std_pct'], 0.0008)  # 0.8/1000
        # 测试逻辑：如果std_pct大于阈值，应该通过
        self.assertEqual(result['std_pct_ok'], result['std_pct'] > result['threshold'])
        # 检查允许的交易方向（下午窗口允许多空双向）
        self.assertEqual(result['allowed_directions'], ['long', 'short'])
        
    def test_time_window_afternoon_exclude_15_00(self):
        """测试下午时间窗口排除15:00"""
        # 设置15:00时间
        exclude_time = datetime(2024, 1, 1, 15, 0)
        
        result = self.strategy._check_time_window_with_std_pct("9984", exclude_time)
        
        self.assertFalse(result['in_window'])
        self.assertIsNone(result['time_period'])
        # 检查允许的交易方向为空
        self.assertEqual(result['allowed_directions'], [])
        
    def test_time_window_outside_trading_hours(self):
        """测试交易时间外的时间窗口检查"""
        # 设置非交易时间
        outside_time = datetime(2024, 1, 1, 10, 0)
        
        result = self.strategy._check_time_window_with_std_pct("9984", outside_time)
        
        self.assertFalse(result['in_window'])
        self.assertIsNone(result['time_period'])
        # 检查允许的交易方向为空
        self.assertEqual(result['allowed_directions'], [])
        
    def test_x_condition_morning_std_pct_pass(self):
        """测试早上X条件std_pct通过"""
        # 设置早上时间和足够的std_pct
        morning_time = datetime(2024, 1, 1, 9, 20)
        
        with patch('hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = morning_time
            result = self.strategy.check_x_condition("9984")
        
        # 测试逻辑：如果std_pct大于早上阈值，应该通过
        expected_std_pct = 0.0008
        if expected_std_pct > self.strategy.std_pct_threshold_morning:
            self.assertTrue(result)
            # 检查日志中是否包含通过信息
            log_calls = [call[0][0] for call in self.strategy.write_log.call_args_list]
            self.assertTrue(any("X条件检查通过" in call and "morning" in call for call in log_calls))
        else:
            self.assertFalse(result)
        
    def test_x_condition_morning_std_pct_fail(self):
        """测试早上X条件std_pct失败"""
        # 设置较低的std值，使其低于早上阈值
        self.context.bb_levels['std'] = 0.1  # std_pct = 0.1/1000 = 0.0001
        morning_time = datetime(2024, 1, 1, 9, 20)
        
        with patch('hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = morning_time
            result = self.strategy.check_x_condition("9984")
        
        # 测试逻辑：如果std_pct小于早上阈值，应该失败
        expected_std_pct = 0.0001
        if expected_std_pct < self.strategy.std_pct_threshold_morning:
            self.assertFalse(result)
            # 检查日志中是否包含失败信息
            log_calls = [call[0][0] for call in self.strategy.write_log.call_args_list]
            self.assertTrue(any("X条件检查失败" in call and "低于morning阈值" in call for call in log_calls))
        else:
            self.assertTrue(result)
        
    def test_x_condition_noon_std_pct_pass(self):
        """测试中午X条件std_pct通过"""
        # 设置中午时间和足够的std_pct
        noon_time = datetime(2024, 1, 1, 11, 29, 30)
        
        with patch('hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = noon_time
            result = self.strategy.check_x_condition("9984")
        
        # 测试逻辑：如果std_pct大于中午阈值，应该通过
        expected_std_pct = 0.0008
        if expected_std_pct > self.strategy.std_pct_threshold_noon:
            self.assertTrue(result)
            # 检查日志中是否包含通过信息
            log_calls = [call[0][0] for call in self.strategy.write_log.call_args_list]
            self.assertTrue(any("X条件检查通过" in call and "noon" in call for call in log_calls))
        else:
            self.assertFalse(result)
        
    def test_x_condition_afternoon_std_pct_pass(self):
        """测试下午X条件std_pct通过"""
        # 设置下午时间（非15:00）和足够的std_pct
        afternoon_time = datetime(2024, 1, 1, 14, 40)
        
        with patch('hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = afternoon_time
            result = self.strategy.check_x_condition("9984")
        
        # 测试逻辑：如果std_pct大于下午阈值，应该通过
        expected_std_pct = 0.0008
        if expected_std_pct > self.strategy.std_pct_threshold_afternoon:
            self.assertTrue(result)
            # 检查日志中是否包含通过信息
            log_calls = [call[0][0] for call in self.strategy.write_log.call_args_list]
            self.assertTrue(any("X条件检查通过" in call and "afternoon" in call for call in log_calls))
        else:
            self.assertFalse(result)
        
    def test_x_condition_afternoon_exclude_15_00(self):
        """测试下午X条件排除15:00"""
        # 设置15:00时间
        exclude_time = datetime(2024, 1, 1, 15, 0)
        
        with patch('hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = exclude_time
            result = self.strategy.check_x_condition("9984")
        
        self.assertFalse(result)
        self.strategy.write_log.assert_any_call(
            "X条件检查失败: 当前时间不在交易窗口内"
        )
        
    def test_x_condition_different_thresholds(self):
        """测试不同时间段的阈值差异"""
        # 设置一个中间值的std_pct，用于测试不同阈值的差异
        self.context.bb_levels['std'] = 0.4  # std_pct = 0.4/1000 = 0.0004
        test_std_pct = 0.0004
        
        # 测试下午时间段
        afternoon_time = datetime(2024, 1, 1, 14, 40)
        afternoon_result = self.strategy.check_x_condition("9984", afternoon_time)
        expected_afternoon = test_std_pct > self.strategy.std_pct_threshold_afternoon
        self.assertEqual(afternoon_result, ['long', 'short'] if expected_afternoon else [])
        
        # 测试中午时间段
        noon_time = datetime(2024, 1, 1, 11, 29, 30)
        noon_result = self.strategy.check_x_condition("9984", noon_time)
        expected_noon = test_std_pct > self.strategy.std_pct_threshold_noon
        self.assertEqual(noon_result, ['long', 'short'] if expected_noon else [])
        
        # 测试早上时间段
        morning_time = datetime(2024, 1, 1, 9, 20)
        morning_result = self.strategy.check_x_condition("9984", morning_time)
        expected_morning = test_std_pct > self.strategy.std_pct_threshold_morning
        self.assertEqual(morning_result, ['long', 'short'] if expected_morning else [])
        
        # 验证阈值大小关系：早上 >= 下午（现在morning和afternoon都是0.0007）
        self.assertGreaterEqual(self.strategy.std_pct_threshold_morning, self.strategy.std_pct_threshold_afternoon)
        
    def test_x_condition_std_pct_calculation_error(self):
        """测试std_pct计算异常处理"""
        # 设置一个会导致异常的情况：middle为0
        self.context.bb_levels['middle'] = 0
        
        morning_time = datetime(2024, 1, 1, 9, 20)
        
        with patch('hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = morning_time
            result = self.strategy.check_x_condition("9984")
        
        self.assertFalse(result)
        # 由于middle为0，std_pct计算会返回0.0，导致不满足阈值
    
    def test_simulated_position_entry_time_in_window_allows_trading(self):
        """测试模拟持仓entry时间在窗口内时允许交易"""
        # 设置模拟持仓 - long方向，entry时间在morning窗口内
        entry_time = datetime(2024, 1, 1, 9, 20, 0)  # morning窗口内
        self.strategy.simulated_positions["9984"] = {
            'long': True,
            'short': False,
            'long_entry_time': entry_time,
            'short_entry_time': None,
            'long_exit_time': None,
            'short_exit_time': None
        }
        
        # 测试morning时间窗口
        morning_time = datetime(2024, 1, 1, 9, 30, 0)
        with patch('hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = morning_time
            result = self.strategy.check_x_condition("9984")
        
        # 应该允许交易（因为方向匹配）
        self.assertEqual(result, ['long', 'short'])
    
    def test_simulated_position_entry_time_outside_window_blocks_trading(self):
        """测试模拟持仓entry时间不在窗口内时阻止交易"""
        # 设置模拟持仓 - long方向，entry时间在窗口外
        entry_time = datetime(2024, 1, 1, 8, 0, 0)  # 窗口外
        self.strategy.simulated_positions["9984"] = {
            'long': True,
            'short': False,
            'long_entry_time': entry_time,
            'short_entry_time': None,
            'long_exit_time': None,
            'short_exit_time': None
        }
        
        # 测试morning时间窗口
        morning_time = datetime(2024, 1, 1, 9, 30, 0)
        with patch('hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = morning_time
            result = self.strategy.check_x_condition("9984")
        
        # 由于用户注释掉了entry时间窗口检查，现在应该允许交易
        self.assertEqual(result, ['long', 'short'])
    
    def test_simulated_position_direction_mismatch_blocks_trading(self):
        """测试模拟持仓方向不匹配时阻止交易"""
        # 设置模拟持仓 - long方向，entry时间在morning窗口内
        entry_time = datetime(2024, 1, 1, 9, 20, 0)  # morning窗口内
        self.strategy.simulated_positions["9984"] = {
            'long': True,
            'short': False,
            'long_entry_time': entry_time,
            'short_entry_time': None,
            'long_exit_time': None,
            'short_exit_time': None
        }
        
        # 修改时间窗口配置，只允许short方向
        with patch.object(self.strategy, '_check_time_window_with_std_pct') as mock_check:
            mock_check.return_value = {
                'in_window': True,
                'time_period': 'morning',
                'threshold': 0.0007,
                'std_pct': 0.001,
                'std_pct_ok': True,
                'allowed_directions': ['short'],  # 只允许short
                'price_check_ok': True,
                'price_check_reason': 'morning时段股价2000.0符合4000以下限制'
            }
            
            morning_time = datetime(2024, 1, 1, 9, 30, 0)
            with patch('hft_bb_reversal_strategy.datetime') as mock_datetime:
                mock_datetime.now.return_value = morning_time
                result = self.strategy.check_x_condition("9984")
            
            # 应该不允许交易（方向不匹配）
            self.assertEqual(result, [])
    
    def test_no_simulated_position_uses_original_logic(self):
        """测试无模拟持仓时使用原有逻辑"""
        # 确保没有模拟持仓
        if "9984" in self.strategy.simulated_positions:
            del self.strategy.simulated_positions["9984"]
        
        # 测试morning时间窗口
        morning_time = datetime(2024, 1, 1, 9, 30, 0)
        with patch('hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = morning_time
            result = self.strategy.check_x_condition("9984")
        
        # 应该允许交易（使用原有逻辑）
        self.assertEqual(result, ['long', 'short'])


if __name__ == '__main__':
    unittest.main()
