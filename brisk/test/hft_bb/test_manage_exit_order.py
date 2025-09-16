"""
测试_manage_exit_order方法
"""

import unittest
from unittest.mock import Mock, patch
from datetime import datetime

# 添加项目根目录到Python路径
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from hft_bb_reversal_strategy import HFTBBReversalStrategy, HFTBBStockContext, TriggerLevels
from vnpy.trader.constant import Direction, OrderType, Exchange, Interval
from vnpy.trader.object import BarData, TickData
from intraday_strategy_base import StrategyState


class TestManageExitOrder(unittest.TestCase):
    """测试_manage_exit_order方法"""
    
    def setUp(self):
        """设置测试环境"""
        self.strategy = HFTBBReversalStrategy(use_mock_gateway=True)
        # Mock write_log方法
        self.strategy.write_log = Mock()
        # 创建测试用的HFT context
        self.strategy.create_hft_context("2330")
    
    def test_manage_exit_order_no_position(self):
        """测试无持仓的情况"""
        context = self.strategy.get_hft_context("2330")
        context.position = 0
        
        bb_levels = {
            'upper': 101.0,
            'lower': 99.0,
            'middle': 100.0,
            'exit_long': 100.5,
            'exit_short': 99.5,
            'std': 1.0
        }
        
        # 调用方法
        self.strategy._manage_exit_order("2330", bb_levels)
        
        # 验证没有订单操作
        self.assertEqual(context.exit_order_id, "")
        self.assertEqual(context.exit_order_price, 0.0)
    
    def test_manage_exit_order_long_position_new_order(self):
        """测试多头持仓，发送新出场订单"""
        context = self.strategy.get_hft_context("2330")
        context.position = 100  # 多头持仓
        context.exit_order_id = ""  # 没有现有订单
        
        bb_levels = {
            'upper': 101.0,
            'lower': 99.0,
            'middle': 100.0,
            'exit_long': 100.5,
            'exit_short': 99.5,
            'std': 1.0
        }
        
        # Mock _execute_exit方法
        with patch.object(self.strategy, '_execute_exit') as mock_execute_exit:
            def mock_execute_exit_side_effect(ctx, bar, price, direction, order_type):
                ctx.exit_order_id = "EXIT_2330_SHORT_10050"
                ctx.exit_price = price  # 设置exit_price
                return "EXIT_2330_SHORT_10050"
            
            mock_execute_exit.side_effect = mock_execute_exit_side_effect
            
            # 调用方法
            self.strategy._manage_exit_order("2330", bb_levels, None)
            
            # 验证调用参数
            mock_execute_exit.assert_called_once_with(
                context, None, 100.5, Direction.SHORT, OrderType.LIMIT
            )
            
            # 验证context更新
            self.assertEqual(context.exit_order_id, "EXIT_2330_SHORT_10050")
            self.assertEqual(context.exit_price, 100.5)
    
    def test_manage_exit_order_short_position_new_order(self):
        """测试空头持仓，发送新出场订单"""
        context = self.strategy.get_hft_context("2330")
        context.position = -100  # 空头持仓
        context.exit_order_id = ""  # 没有现有订单
        
        bb_levels = {
            'upper': 101.0,
            'lower': 99.0,
            'middle': 100.0,
            'exit_long': 100.5,
            'exit_short': 99.5,
            'std': 1.0
        }
        
        # Mock _execute_exit方法
        with patch.object(self.strategy, '_execute_exit') as mock_execute_exit:
            def mock_execute_exit_side_effect(ctx, bar, price, direction, order_type):
                ctx.exit_order_id = "EXIT_2330_LONG_9950"
                ctx.exit_price = price  # 设置exit_price
                return "EXIT_2330_LONG_9950"
            
            mock_execute_exit.side_effect = mock_execute_exit_side_effect
            
            # 调用方法
            self.strategy._manage_exit_order("2330", bb_levels, None)
            
            # 验证调用参数
            mock_execute_exit.assert_called_once_with(
                context, None, 99.5, Direction.LONG, OrderType.LIMIT
            )
            
            # 验证context更新
            self.assertEqual(context.exit_order_id, "EXIT_2330_LONG_9950")
            self.assertEqual(context.exit_price, 99.5)
    
    def test_manage_exit_order_price_update_needed(self):
        """测试需要更新出场订单价格的情况"""
        context = self.strategy.get_hft_context("2330")
        context.position = 100  # 多头持仓
        context.exit_order_id = "OLD_EXIT_ORDER"
        context.exit_order_price = 100.0  # 旧价格
        
        bb_levels = {
            'upper': 101.0,
            'lower': 99.0,
            'middle': 100.0,
            'exit_long': 100.5,  # 新价格，差异超过0.01
            'exit_short': 99.5,
            'std': 1.0
        }
        
        # Mock方法
        with patch.object(self.strategy, '_cancel_order_safely') as mock_cancel, \
             patch.object(self.strategy, '_execute_exit') as mock_execute_exit:
            
            mock_cancel.return_value = True
            
            def mock_execute_exit_side_effect(ctx, bar, price, direction, order_type):
                ctx.exit_order_id = "NEW_EXIT_ORDER"
                ctx.exit_price = price  # 设置exit_price
                return "NEW_EXIT_ORDER"
            
            mock_execute_exit.side_effect = mock_execute_exit_side_effect
            
            # 调用方法
            self.strategy._manage_exit_order("2330", bb_levels, None)
            
            # 验证取消旧订单
            mock_cancel.assert_called_once_with("OLD_EXIT_ORDER", "2330")
            
            # 验证发送新订单
            mock_execute_exit.assert_called_once_with(
                context, None, 100.5, Direction.SHORT, OrderType.LIMIT
            )
            
            # 验证context更新
            self.assertEqual(context.exit_order_id, "NEW_EXIT_ORDER")
            self.assertEqual(context.exit_price, 100.5)
    
    def test_manage_exit_order_price_no_update_needed(self):
        """测试不需要更新出场订单价格的情况"""
        context = self.strategy.get_hft_context("2330")
        context.position = 100  # 多头持仓
        context.exit_order_id = "EXISTING_EXIT_ORDER"
        context.exit_price = 100.5  # 与bb_levels中的exit_long相同
        
        bb_levels = {
            'upper': 101.0,
            'lower': 99.0,
            'middle': 100.0,
            'exit_long': 100.5,  # 价格相同
            'exit_short': 99.5,
            'std': 1.0
        }
        
        # Mock方法
        with patch.object(self.strategy, '_cancel_order_safely') as mock_cancel, \
             patch.object(self.strategy, '_execute_exit') as mock_execute_exit:
            
            # 调用方法
            self.strategy._manage_exit_order("2330", bb_levels)
            
            # 验证没有取消订单
            mock_cancel.assert_not_called()
            
            # 验证没有发送新订单
            mock_execute_exit.assert_not_called()
            
            # 验证context没有变化
            self.assertEqual(context.exit_order_id, "EXISTING_EXIT_ORDER")
            self.assertEqual(context.exit_price, 100.5)
    
    def test_manage_exit_order_execute_exit_failure(self):
        """测试_execute_exit失败的情况"""
        context = self.strategy.get_hft_context("2330")
        context.position = 100  # 多头持仓
        context.exit_order_id = ""  # 没有现有订单
        
        bb_levels = {
            'upper': 101.0,
            'lower': 99.0,
            'middle': 100.0,
            'exit_long': 100.5,
            'exit_short': 99.5,
            'std': 1.0
        }
        
        # Mock _execute_exit方法返回None（失败）
        with patch.object(self.strategy, '_execute_exit') as mock_execute_exit:
            mock_execute_exit.return_value = None
            
            # 调用方法
            self.strategy._manage_exit_order("2330", bb_levels, None)
            
            # 验证调用
            mock_execute_exit.assert_called_once_with(
                context, None, 100.5, Direction.SHORT, OrderType.LIMIT
            )
            
            # 验证context没有更新
            self.assertEqual(context.exit_order_id, "")
            self.assertEqual(context.exit_order_price, 0.0)


if __name__ == '__main__':
    unittest.main()
