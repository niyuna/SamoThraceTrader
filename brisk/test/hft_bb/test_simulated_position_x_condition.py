"""
测试模拟持仓智能X条件检查功能
"""

import unittest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, time
from vnpy.trader.constant import Exchange

# 添加路径以导入模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from hft_bb_reversal_strategy import HFTBBReversalStrategy, HFTBBStockContext


class TestSimulatedPositionXCondition(unittest.TestCase):
    """测试模拟持仓智能X条件检查功能"""
    
    def setUp(self):
        """设置测试环境"""
        self.strategy = HFTBBReversalStrategy(use_mock_gateway=True)
        self.symbol = "9984"
        
        # 创建HFT context
        self.context = self.strategy.create_hft_context(self.symbol)
        self.context.bb_levels = {
            'upper': 100.0,
            'lower': 90.0,
            'middle': 95.0,
            'std': 2.0
        }
        
        # 添加到eligible_stocks
        self.strategy.eligible_stocks.add(self.symbol)
        
        # 模拟get_stock_prev_close返回合理价格
        self.strategy.get_stock_prev_close = Mock(return_value=2000.0)
    
    def test_no_simulated_position_allows_trading(self):
        """测试无模拟持仓时允许交易"""
        # 确保没有模拟持仓
        if self.symbol in self.strategy.simulated_positions:
            del self.strategy.simulated_positions[self.symbol]
        
        # 测试morning时间窗口
        current_time = datetime(2024, 1, 1, 9, 30, 0)
        result = self.strategy._check_default_x_condition(self.symbol, current_time)
        
        # 应该允许交易
        self.assertEqual(result, ['long', 'short'])
    
    def test_simulated_position_entry_time_in_window_direction_match(self):
        """测试模拟持仓entry时间在窗口内且方向匹配时允许交易"""
        # 设置模拟持仓 - long方向，entry时间在morning窗口内
        entry_time = datetime(2024, 1, 1, 9, 20, 0)  # morning窗口内
        self.strategy.simulated_positions[self.symbol] = {
            'long': True,
            'short': False,
            'long_entry_time': entry_time,
            'short_entry_time': None,
            'long_exit_time': None,
            'short_exit_time': None
        }
        
        # 测试morning时间窗口
        current_time = datetime(2024, 1, 1, 9, 30, 0)
        result = self.strategy._check_default_x_condition(self.symbol, current_time)
        
        # 应该允许交易（因为方向匹配）
        self.assertEqual(result, ['long', 'short'])
    
    def test_simulated_position_entry_time_in_window_direction_mismatch(self):
        """测试模拟持仓entry时间在窗口内但方向不匹配时不允许交易"""
        # 设置模拟持仓 - long方向，entry时间在morning窗口内
        entry_time = datetime(2024, 1, 1, 9, 20, 0)  # morning窗口内
        self.strategy.simulated_positions[self.symbol] = {
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
            
            current_time = datetime(2024, 1, 1, 9, 30, 0)
            result = self.strategy._check_default_x_condition(self.symbol, current_time)
            
            # 应该不允许交易（方向不匹配）
            self.assertEqual(result, [])
    
    def test_simulated_position_entry_time_outside_window(self):
        """测试模拟持仓entry时间不在任何窗口内时不允许交易"""
        # 设置模拟持仓 - long方向，entry时间在窗口外
        entry_time = datetime(2024, 1, 1, 8, 0, 0)  # 窗口外
        self.strategy.simulated_positions[self.symbol] = {
            'long': True,
            'short': False,
            'long_entry_time': entry_time,
            'short_entry_time': None,
            'long_exit_time': None,
            'short_exit_time': None
        }
        
        current_time = datetime(2024, 1, 1, 9, 30, 0)
        result = self.strategy._check_default_x_condition(self.symbol, current_time)
        
        # 应该不允许交易（entry时间不在窗口内）
        self.assertEqual(result, [])
    
    def test_simulated_position_entry_time_none(self):
        """测试模拟持仓entry时间为None时不允许交易"""
        # 设置模拟持仓 - entry时间为None
        self.strategy.simulated_positions[self.symbol] = {
            'long': True,
            'short': False,
            'long_entry_time': None,  # None
            'short_entry_time': None,
            'long_exit_time': None,
            'short_exit_time': None
        }
        
        current_time = datetime(2024, 1, 1, 9, 30, 0)
        result = self.strategy._check_default_x_condition(self.symbol, current_time)
        
        # 应该不允许交易（entry时间为None）
        self.assertEqual(result, [])
    
    def test_simulated_position_no_position_allows_trading(self):
        """测试模拟持仓没有持仓时允许交易（正常状态）"""
        # 设置模拟持仓 - 既不是long也不是short（没有持仓的正常状态）
        entry_time = datetime(2024, 1, 1, 9, 20, 0)
        self.strategy.simulated_positions[self.symbol] = {
            'long': False,
            'short': False,  # 没有持仓，这是正常状态
            'long_entry_time': entry_time,
            'short_entry_time': None,
            'long_exit_time': None,
            'short_exit_time': None
        }
        
        current_time = datetime(2024, 1, 1, 9, 30, 0)
        result = self.strategy._check_default_x_condition(self.symbol, current_time)
        
        # 应该允许交易（没有持仓是正常状态）
        self.assertEqual(result, ['long', 'short'])
    
    def test_simulated_position_short_direction_match(self):
        """测试模拟持仓为short方向且匹配时允许交易"""
        # 设置模拟持仓 - short方向，entry时间在noon窗口内
        entry_time = datetime(2024, 1, 1, 11, 30, 0)  # noon窗口内
        self.strategy.simulated_positions[self.symbol] = {
            'long': False,
            'short': True,
            'long_entry_time': None,
            'short_entry_time': entry_time,
            'long_exit_time': None,
            'short_exit_time': None
        }
        
        # 测试noon时间窗口
        current_time = datetime(2024, 1, 1, 11, 30, 0)
        result = self.strategy._check_default_x_condition(self.symbol, current_time)
        
        # 应该允许交易（方向匹配）
        self.assertEqual(result, ['long', 'short'])
    
    def test_is_entry_time_in_any_window_morning(self):
        """测试_is_entry_time_in_any_window方法 - morning窗口"""
        entry_time = datetime(2024, 1, 1, 9, 20, 0)  # morning窗口内
        result = self.strategy._is_entry_time_in_any_window(entry_time)
        self.assertTrue(result)
        
        entry_time = datetime(2024, 1, 1, 8, 0, 0)  # 窗口外
        result = self.strategy._is_entry_time_in_any_window(entry_time)
        self.assertFalse(result)
    
    def test_is_entry_time_in_any_window_noon(self):
        """测试_is_entry_time_in_any_window方法 - noon窗口"""
        entry_time = datetime(2024, 1, 1, 11, 30, 0)  # noon窗口内
        result = self.strategy._is_entry_time_in_any_window(entry_time)
        self.assertTrue(result)
        
        entry_time = datetime(2024, 1, 1, 12, 0, 0)  # 窗口外
        result = self.strategy._is_entry_time_in_any_window(entry_time)
        self.assertFalse(result)
    
    def test_is_entry_time_in_any_window_afternoon(self):
        """测试_is_entry_time_in_any_window方法 - afternoon窗口"""
        entry_time = datetime(2024, 1, 1, 14, 40, 0)  # afternoon窗口内
        result = self.strategy._is_entry_time_in_any_window(entry_time)
        self.assertTrue(result)
        
        entry_time = datetime(2024, 1, 1, 16, 0, 0)  # 窗口外
        result = self.strategy._is_entry_time_in_any_window(entry_time)
        self.assertFalse(result)
    
    def test_get_simulated_position_direction_long(self):
        """测试_get_simulated_position_direction方法 - long方向"""
        self.strategy.simulated_positions[self.symbol] = {
            'long': True,
            'short': False,
            'long_entry_time': datetime.now(),
            'short_entry_time': None,
            'long_exit_time': None,
            'short_exit_time': None
        }
        
        result = self.strategy._get_simulated_position_direction(self.symbol)
        self.assertEqual(result, 'long')
    
    def test_get_simulated_position_direction_short(self):
        """测试_get_simulated_position_direction方法 - short方向"""
        self.strategy.simulated_positions[self.symbol] = {
            'long': False,
            'short': True,
            'long_entry_time': None,
            'short_entry_time': datetime.now(),
            'long_exit_time': None,
            'short_exit_time': None
        }
        
        result = self.strategy._get_simulated_position_direction(self.symbol)
        self.assertEqual(result, 'short')
    
    def test_get_simulated_position_direction_none(self):
        """测试_get_simulated_position_direction方法 - 无持仓"""
        self.strategy.simulated_positions[self.symbol] = {
            'long': False,
            'short': False,
            'long_entry_time': None,
            'short_entry_time': None,
            'long_exit_time': None,
            'short_exit_time': None
        }
        
        result = self.strategy._get_simulated_position_direction(self.symbol)
        self.assertIsNone(result)
    
    def test_get_simulated_position_direction_no_symbol(self):
        """测试_get_simulated_position_direction方法 - 符号不存在"""
        result = self.strategy._get_simulated_position_direction("NONEXISTENT")
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
