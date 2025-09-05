"""
测试入场逻辑检查
"""

import unittest
import sys
import os
from unittest.mock import Mock, patch
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from hft_bb_reversal_strategy import HFTBBReversalStrategy, HFTBBStockContext, TriggerLevels
from vnpy.trader.object import TickData
from vnpy.trader.constant import Exchange, Direction
from intraday_strategy_base import StrategyState


class TestEntryLogic(unittest.TestCase):
    """测试入场逻辑检查"""
    
    def setUp(self):
        """设置测试环境"""
        self.strategy = HFTBBReversalStrategy(use_mock_gateway=True)
        # Mock write_log方法
        self.strategy.write_log = Mock()
        # Mock update_context_state方法
        self.strategy.update_context_state = Mock()
        # 创建测试用的HFT context
        self.strategy.create_hft_context("2330")
    
    def test_check_entry_logic_trigger_upper_band(self):
        """测试触发上轨的情况"""
        tick = TickData(
            symbol="2330",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            name="台积电",
            volume=1000,
            last_price=101.5,  # 高于上轨触发价格
            gateway_name="test"
        )
        
        # 使用策略中创建的context
        context = self.strategy.get_hft_context("2330")
        context.trigger_levels = TriggerLevels(
            upper_trigger=101.0,
            upper_limit=101.5,
            lower_trigger=99.0,
            lower_limit=98.5
        )
        context.entry_order_id = ""  # 没有现有订单
        
        # Mock _execute_entry方法
        def mock_execute_entry(ctx, bar, price, direction):
            ctx.entry_order_id = "ENTRY_2330_Short_10150"
            ctx.entry_price = price
            self.strategy.update_context_state("2330", StrategyState.WAITING_ENTRY)
        
        self.strategy._execute_entry = mock_execute_entry
        
        self.strategy._check_entry_logic("2330", tick, context)
        
        # 验证发送了空头订单
        self.assertEqual(context.entry_order_id, "ENTRY_2330_Short_10150")
        self.assertEqual(context.entry_price, 101.5)
        self.strategy.update_context_state.assert_called_with("2330", StrategyState.WAITING_ENTRY)
        
        # 验证日志记录
        log_calls = [call[0][0] for call in self.strategy.write_log.call_args_list]
        self.assertTrue(any("发送入场订单" in call and "Short" in call for call in log_calls))
    
    def test_check_entry_logic_trigger_lower_band(self):
        """测试触发下轨的情况"""
        tick = TickData(
            symbol="2330",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            name="台积电",
            volume=1000,
            last_price=98.0,  # 低于下轨触发价格
            gateway_name="test"
        )
        
        context = self.strategy.get_hft_context("2330")
        context.trigger_levels = TriggerLevels(
            upper_trigger=101.0,
            upper_limit=101.5,
            lower_trigger=99.0,
            lower_limit=98.5
        )
        context.entry_order_id = ""  # 没有现有订单
        
        # Mock _execute_entry方法
        def mock_execute_entry(ctx, bar, price, direction):
            ctx.entry_order_id = "ENTRY_2330_Long_9850"
            ctx.entry_price = price
            self.strategy.update_context_state("2330", StrategyState.WAITING_ENTRY)
        
        self.strategy._execute_entry = mock_execute_entry
        
        self.strategy._check_entry_logic("2330", tick, context)
        
        # 验证发送了多头订单
        self.assertEqual(context.entry_order_id, "ENTRY_2330_Long_9850")
        self.assertEqual(context.entry_price, 98.5)
        self.strategy.update_context_state.assert_called_with("2330", StrategyState.WAITING_ENTRY)
        
        # 验证日志记录
        log_calls = [call[0][0] for call in self.strategy.write_log.call_args_list]
        self.assertTrue(any("发送入场订单" in call and "Long" in call for call in log_calls))
    
    def test_check_entry_logic_price_in_middle(self):
        """测试价格在中间的情况"""
        tick = TickData(
            symbol="2330",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            name="台积电",
            volume=1000,
            last_price=100.0,  # 在两个触发价格之间
            gateway_name="test"
        )
        
        context = self.strategy.get_hft_context("2330")
        context.trigger_levels = TriggerLevels(
            upper_trigger=101.0,
            upper_limit=101.5,
            lower_trigger=99.0,
            lower_limit=98.5
        )
        context.entry_order_id = "EXISTING_ORDER"  # 有现有订单
        
        # Mock _cancel_order_safely方法
        self.strategy._cancel_order_safely = Mock(return_value=True)
        
        self.strategy._check_entry_logic("2330", tick, context)
        
        # 验证取消了现有订单
        self.assertEqual(context.entry_order_id, "")
        self.assertEqual(context.entry_price, 0.0)
        self.strategy.update_context_state.assert_called_with("2330", StrategyState.IDLE)
        
        # 验证日志记录
        log_calls = [call[0][0] for call in self.strategy.write_log.call_args_list]
        self.assertTrue(any("取消入场订单" in call for call in log_calls))
    
    def test_check_entry_logic_existing_order_different_price(self):
        """测试现有订单价格不同的情况"""
        tick = TickData(
            symbol="2330",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            name="台积电",
            volume=1000,
            last_price=101.5,  # 触发上轨
            gateway_name="test"
        )
        
        context = self.strategy.get_hft_context("2330")
        context.trigger_levels = TriggerLevels(
            upper_trigger=101.0,
            upper_limit=101.5,
            lower_trigger=99.0,
            lower_limit=98.5
        )
        context.entry_order_id = "EXISTING_ORDER"
        context.entry_price = 100.0  # 与当前应该下的价格不同
        
        # Mock _cancel_order_safely方法
        self.strategy._cancel_order_safely = Mock(return_value=True)
        
        self.strategy._check_entry_logic("2330", tick, context)
        
        # 验证取消了现有订单
        self.assertEqual(context.entry_order_id, "")
        self.assertEqual(context.entry_price, 100.0)  # entry_price不会被清空
        self.strategy.update_context_state.assert_called_with("2330", StrategyState.IDLE)
        
        # 验证日志记录
        log_calls = [call[0][0] for call in self.strategy.write_log.call_args_list]
        self.assertTrue(any("取消入场订单" in call for call in log_calls))
    
    def test_check_entry_logic_no_action_needed(self):
        """测试无需操作的情况"""
        tick = TickData(
            symbol="2330",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            name="台积电",
            volume=1000,
            last_price=100.0,  # 在两个触发价格之间
            gateway_name="test"
        )
        
        context = self.strategy.get_hft_context("2330")
        context.trigger_levels = TriggerLevels(
            upper_trigger=101.0,
            upper_limit=101.5,
            lower_trigger=99.0,
            lower_limit=98.5
        )
        context.entry_order_id = ""  # 没有现有订单
        
        self.strategy._check_entry_logic("2330", tick, context)
        
        # 验证没有发送订单
        self.assertEqual(context.entry_order_id, "")
        self.assertEqual(context.entry_price, 0.0)
        
        # 验证没有调用update_context_state
        self.strategy.update_context_state.assert_not_called()
    
    def test_check_entry_logic_existing_order_same_price(self):
        """测试现有订单价格相同的情况"""
        tick = TickData(
            symbol="2330",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            name="台积电",
            volume=1000,
            last_price=101.5,  # 触发上轨
            gateway_name="test"
        )
        
        context = self.strategy.get_hft_context("2330")
        context.trigger_levels = TriggerLevels(
            upper_trigger=101.0,
            upper_limit=101.5,
            lower_trigger=99.0,
            lower_limit=98.5
        )
        context.entry_order_id = "EXISTING_ORDER"
        context.entry_order_price = 101.5  # 与当前应该下的价格相同
        
        self.strategy._check_entry_logic("2330", tick, context)
        
        # 验证没有取消订单
        self.assertEqual(context.entry_order_id, "EXISTING_ORDER")
        self.assertEqual(context.entry_order_price, 101.5)
        
        # 验证没有调用update_context_state
        self.strategy.update_context_state.assert_not_called()


if __name__ == '__main__':
    unittest.main()
