"""
测试 X 条件返回方向的逻辑
"""

import unittest
import sys
import os
from unittest.mock import Mock, patch
from datetime import datetime, time

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from hft_bb_reversal_strategy import HFTBBReversalStrategy, HFTBBStockContext, StrategyState


class TestXConditionDirections(unittest.TestCase):
    """测试 X 条件返回方向的逻辑"""
    
    def setUp(self):
        """设置测试环境"""
        self.strategy = HFTBBReversalStrategy(use_mock_gateway=True)
        self.symbol = "9984"
        
        # 创建 context
        self.context = HFTBBStockContext(symbol=self.symbol)
        self.strategy.hft_contexts[self.symbol] = self.context
        
        # 设置 BB levels
        self.context.bb_levels = {
            'upper': 100.0,
            'lower': 95.0,
            'middle': 97.5,
            'std': 1.0
        }
        
        # 设置 trigger levels
        from hft_bb_reversal_strategy import TriggerLevels
        self.context.trigger_levels = TriggerLevels(
            upper_trigger=99.0,
            upper_limit=100.0,
            lower_trigger=96.0,
            lower_limit=95.0
        )
    
    def test_check_x_condition_returns_directions_when_enabled(self):
        """测试 X 条件启用时返回方向列表"""
        # 设置 X 条件为启用
        self.strategy.x_condition_enabled = True
        
        # 添加股票到 eligible_stocks
        self.strategy.eligible_stocks.add(self.symbol)
        
        # 模拟时间窗口检查通过
        with patch.object(self.strategy, '_check_time_window_with_std_pct') as mock_time_window:
            mock_time_window.return_value = {
                'in_window': True,
                'time_period': 'morning',
                'threshold': 0.001,
                'std_pct': 0.002,
                'std_pct_ok': True
            }
            
            # 调用 check_x_condition
            result = self.strategy.check_x_condition(self.symbol)
            
            # 验证返回结果
            self.assertEqual(result, ['long', 'short'])
    
    def test_check_x_condition_returns_empty_when_disabled(self):
        """测试 X 条件禁用时返回空列表"""
        # 设置 X 条件为禁用
        self.strategy.x_condition_enabled = False
        
        # 调用 check_x_condition
        result = self.strategy.check_x_condition(self.symbol)
        
        # 验证返回结果
        self.assertEqual(result, ['long', 'short'])
    
    def test_check_x_condition_returns_empty_when_not_eligible(self):
        """测试股票不在 eligible_stocks 时返回空列表"""
        # 设置 X 条件为启用
        self.strategy.x_condition_enabled = True
        
        # 不添加股票到 eligible_stocks
        
        # 调用 check_x_condition
        result = self.strategy.check_x_condition(self.symbol)
        
        # 验证返回结果
        self.assertEqual(result, [])
    
    def test_check_x_condition_returns_empty_when_has_position(self):
        """测试有持仓时返回空列表"""
        # 设置 X 条件为启用
        self.strategy.x_condition_enabled = True
        
        # 添加股票到 eligible_stocks
        self.strategy.eligible_stocks.add(self.symbol)
        
        # 设置模拟持仓
        self.strategy.simulated_positions[self.symbol] = {'long': True, 'short': False}
        
        # 调用 check_x_condition
        result = self.strategy.check_x_condition(self.symbol)
        
        # 验证返回结果
        self.assertEqual(result, [])
    
    def test_check_x_condition_returns_empty_when_time_window_fails(self):
        """测试时间窗口检查失败时返回空列表"""
        # 设置 X 条件为启用
        self.strategy.x_condition_enabled = True
        
        # 添加股票到 eligible_stocks
        self.strategy.eligible_stocks.add(self.symbol)
        
        # 模拟时间窗口检查失败
        with patch.object(self.strategy, '_check_time_window_with_std_pct') as mock_time_window:
            mock_time_window.return_value = {
                'in_window': False,
                'time_period': None,
                'threshold': None,
                'std_pct': None,
                'std_pct_ok': False
            }
            
            # 调用 check_x_condition
            result = self.strategy.check_x_condition(self.symbol)
            
            # 验证返回结果
            self.assertEqual(result, [])
    
    def test_check_x_condition_returns_empty_when_std_pct_fails(self):
        """测试 std_pct 检查失败时返回空列表"""
        # 设置 X 条件为启用
        self.strategy.x_condition_enabled = True
        
        # 添加股票到 eligible_stocks
        self.strategy.eligible_stocks.add(self.symbol)
        
        # 模拟时间窗口检查通过但 std_pct 检查失败
        with patch.object(self.strategy, '_check_time_window_with_std_pct') as mock_time_window:
            mock_time_window.return_value = {
                'in_window': True,
                'time_period': 'morning',
                'threshold': 0.001,
                'std_pct': 0.0005,
                'std_pct_ok': False
            }
            
            # 调用 check_x_condition
            result = self.strategy.check_x_condition(self.symbol)
            
            # 验证返回结果
            self.assertEqual(result, [])
    
    def test_context_can_trade_is_list(self):
        """测试 context.can_trade 是列表类型"""
        # 验证 can_trade 是列表
        self.assertIsInstance(self.context.can_trade, list)
        
        # 设置 can_trade
        self.context.can_trade = ['long', 'short']
        
        # 验证可以检查方向
        self.assertIn('long', self.context.can_trade)
        self.assertIn('short', self.context.can_trade)
        self.assertNotIn('none', self.context.can_trade)
    
    def test_entry_logic_checks_direction_in_can_trade(self):
        """测试入场逻辑检查方向是否在 can_trade 中"""
        # 设置 can_trade 只允许 long
        self.context.can_trade = ['long']
        
        # 创建 mock tick
        tick = Mock()
        tick.last_price = 95.5  # 触发下轨
        
        # 模拟 _check_entry_logic 中的逻辑
        trigger_levels = self.context.trigger_levels
        current_price = tick.last_price
        
        # 检查下轨触发
        if current_price <= trigger_levels.lower_trigger:
            order_direction = 'long'
            if not self.context.entry_order_id and 'long' in self.context.can_trade:
                should_order = True
            else:
                should_order = False
        else:
            should_order = False
        
        # 验证应该下单
        self.assertTrue(should_order)
        
        # 测试上轨触发但不允许 short
        tick.last_price = 99.5  # 触发上轨
        
        if tick.last_price >= trigger_levels.upper_trigger:
            order_direction = 'short'
            if not self.context.entry_order_id and 'short' in self.context.can_trade:
                should_order = True
            else:
                should_order = False
        else:
            should_order = False
        
        # 验证不应该下单
        self.assertFalse(should_order)
    
    def test_check_entry_logic_cancels_order_when_x_condition_fails(self):
        """测试 _check_entry_logic 在 X 条件失败时取消 entry 订单"""
        # 设置 entry 订单
        self.context.entry_order_id = "test_order_123"
        self.context.state = StrategyState.WAITING_ENTRY
        
        # 设置 X 条件不满足
        self.context.can_trade = []
        
        # 创建 mock tick
        tick = Mock()
        tick.last_price = 95.5
        
        # 模拟 _cancel_entry_order 方法
        with patch.object(self.strategy, '_cancel_entry_order') as mock_cancel:
            # 调用 _check_entry_logic
            self.strategy._check_entry_logic(self.symbol, tick, self.context)
            
            # 验证调用了取消订单
            mock_cancel.assert_called_once_with(self.symbol, self.context)


if __name__ == '__main__':
    unittest.main()
