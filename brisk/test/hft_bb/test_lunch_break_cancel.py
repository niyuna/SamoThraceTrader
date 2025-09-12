"""
午休时间取消 Entry Orders 测试
"""

import unittest
import sys
import os
from datetime import datetime, time
from unittest.mock import Mock, patch, call

# 添加路径以导入模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from hft_bb_reversal_strategy import HFTBBReversalStrategy
from intraday_strategy_base import StrategyState
from vnpy.trader.constant import Direction, Offset, OrderType, Status
from vnpy.trader.object import OrderData


class TestLunchBreakCancel(unittest.TestCase):
    """测试午休时间取消 entry orders 功能"""
    
    def setUp(self):
        """设置测试环境"""
        self.strategy = HFTBBReversalStrategy(use_mock_gateway=True)
        self.strategy.brisk_gateway = Mock()
        self.strategy.brisk_gateway.cancel_order = Mock(return_value=True)
        self.strategy.brisk_gateway.query_single_order = Mock()
        self.strategy.write_log = Mock()
        
        # 创建测试用的 context
        self.symbol1 = "9984"
        self.symbol2 = "6098"
        self.strategy.create_hft_context(self.symbol1)
        self.strategy.create_hft_context(self.symbol2)
        
        # 设置 context 状态
        context1 = self.strategy.get_hft_context(self.symbol1)
        context1.entry_order_id = "entry_9984_123"
        context1.state = StrategyState.WAITING_ENTRY
        context1.entry_order_time = datetime.now()
        
        context2 = self.strategy.get_hft_context(self.symbol2)
        context2.entry_order_id = "entry_6098_456"
        context2.state = StrategyState.WAITING_ENTRY
        context2.entry_order_time = datetime.now()
        
        # 重置 mock
        self.strategy.write_log.reset_mock()
    
    def test_lunch_break_cancel_success(self):
        """测试午休时间成功取消所有 entry orders"""
        # 模拟午休时间
        lunch_time = time(12, 12, 30)
        
        with patch('hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime.combine(datetime.now().date(), lunch_time)
            
            # 模拟取消订单成功
            with patch.object(self.strategy, '_cancel_order_with_verification', return_value=True) as mock_cancel:
                with patch.object(self.strategy, 'update_context_state') as mock_update_state:
                    with patch('hft_bb_reversal_strategy.time_module.sleep') as mock_sleep:
                        self.strategy._cancel_all_entry_orders_during_lunch_break()
                        
                        # 验证调用了取消订单方法
                        self.assertEqual(mock_cancel.call_count, 2)
                        mock_cancel.assert_any_call("entry_9984_123", "9984")
                        mock_cancel.assert_any_call("entry_6098_456", "6098")
                        
                        # 验证调用了状态更新方法
                        self.assertEqual(mock_update_state.call_count, 2)
                        mock_update_state.assert_any_call("9984", StrategyState.IDLE)
                        mock_update_state.assert_any_call("6098", StrategyState.IDLE)
                        
                        # 验证调用了 sleep 方法
                        self.assertEqual(mock_sleep.call_count, 2)
                        mock_sleep.assert_has_calls([call(0.5), call(0.5)])
                        
                        # 验证 context 状态被清理
                        context1 = self.strategy.get_hft_context(self.symbol1)
                        context2 = self.strategy.get_hft_context(self.symbol2)
                        self.assertEqual(context1.entry_order_id, "")
                        self.assertIsNone(context1.entry_order_time)
                        self.assertEqual(context2.entry_order_id, "")
                        self.assertIsNone(context2.entry_order_time)
    
    def test_lunch_break_cancel_partial_failure(self):
        """测试午休时间部分取消失败的情况"""
        # 模拟午休时间
        lunch_time = time(12, 12, 30)
        
        with patch('hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime.combine(datetime.now().date(), lunch_time)
            
            # 模拟第一个取消成功，第二个失败
            def mock_cancel_side_effect(order_id, symbol):
                if symbol == "9984":
                    return True
                else:
                    return False
            
            with patch.object(self.strategy, '_cancel_order_with_verification', side_effect=mock_cancel_side_effect) as mock_cancel:
                with patch.object(self.strategy, 'update_context_state') as mock_update_state:
                    with patch('hft_bb_reversal_strategy.time_module.sleep') as mock_sleep:
                        self.strategy._cancel_all_entry_orders_during_lunch_break()
                        
                        # 验证调用了取消订单方法
                        self.assertEqual(mock_cancel.call_count, 2)
                        
                        # 验证只更新了成功的 context 状态
                        self.assertEqual(mock_update_state.call_count, 1)
                        mock_update_state.assert_called_with("9984", StrategyState.IDLE)
                        
                        # 验证调用了 sleep 方法
                        self.assertEqual(mock_sleep.call_count, 2)
    
    def test_lunch_break_cancel_no_entry_orders(self):
        """测试没有 entry orders 时的情况"""
        # 清除所有 entry_order_id
        context1 = self.strategy.get_hft_context(self.symbol1)
        context2 = self.strategy.get_hft_context(self.symbol2)
        context1.entry_order_id = ""
        context2.entry_order_id = ""
        
        with patch.object(self.strategy, '_cancel_order_with_verification') as mock_cancel:
            with patch('hft_bb_reversal_strategy.time_module.sleep') as mock_sleep:
                self.strategy._cancel_all_entry_orders_during_lunch_break()
                
                # 验证没有调用取消订单方法
                mock_cancel.assert_not_called()
                
                # 验证没有调用 sleep 方法
                mock_sleep.assert_not_called()
    
    def test_lunch_break_cancel_wrong_state(self):
        """测试 context 状态不是 WAITING_ENTRY 时的情况"""
        # 修改 context 状态
        context1 = self.strategy.get_hft_context(self.symbol1)
        context2 = self.strategy.get_hft_context(self.symbol2)
        context1.state = StrategyState.HOLDING
        context2.state = StrategyState.IDLE
        
        with patch.object(self.strategy, '_cancel_order_with_verification') as mock_cancel:
            with patch('hft_bb_reversal_strategy.time_module.sleep') as mock_sleep:
                self.strategy._cancel_all_entry_orders_during_lunch_break()
                
                # 验证没有调用取消订单方法
                mock_cancel.assert_not_called()
                
                # 验证没有调用 sleep 方法
                mock_sleep.assert_not_called()
    
    def test_timer_callback_lunch_break_time(self):
        """测试定时器在午休时间调用取消逻辑"""
        # 模拟午休时间
        lunch_time = time(12, 12, 30)
        
        with patch('hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime.combine(datetime.now().date(), lunch_time)
            
            with patch.object(self.strategy, '_cancel_all_entry_orders_during_lunch_break') as mock_cancel_all:
                with patch.object(self.strategy, '_execute_market_close_liquidation') as mock_liquidation:
                    # 创建模拟的 event 对象
                    mock_event = Mock()
                    
                    self.strategy._on_market_close_timer(mock_event)
                    
                    # 验证调用了取消方法，没有调用平仓方法
                    mock_cancel_all.assert_called_once()
                    mock_liquidation.assert_not_called()
    
    def test_timer_callback_normal_time(self):
        """测试定时器在非午休时间不调用取消逻辑"""
        # 模拟非午休时间
        normal_time = time(14, 30, 0)
        
        with patch('hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime.combine(datetime.now().date(), normal_time)
            
            with patch.object(self.strategy, '_cancel_all_entry_orders_during_lunch_break') as mock_cancel_all:
                with patch.object(self.strategy, '_execute_market_close_liquidation') as mock_liquidation:
                    # 创建模拟的 event 对象
                    mock_event = Mock()
                    
                    self.strategy._on_market_close_timer(mock_event)
                    
                    # 验证没有调用取消方法
                    mock_cancel_all.assert_not_called()
    
    def test_lunch_break_time_window_boundary(self):
        """测试午休时间窗口边界"""
        # 测试 12:10 边界
        boundary_time = time(12, 10, 0)
        
        with patch('hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime.combine(datetime.now().date(), boundary_time)
            
            with patch.object(self.strategy, '_cancel_all_entry_orders_during_lunch_break') as mock_cancel_all:
                mock_event = Mock()
                self.strategy._on_market_close_timer(mock_event)
                mock_cancel_all.assert_called_once()
        
        # 测试 12:15 边界
        boundary_time = time(12, 15, 0)
        
        with patch('hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime.combine(datetime.now().date(), boundary_time)
            
            with patch.object(self.strategy, '_cancel_all_entry_orders_during_lunch_break') as mock_cancel_all:
                mock_event = Mock()
                self.strategy._on_market_close_timer(mock_event)
                mock_cancel_all.assert_called_once()
        
        # 测试 12:09 不在窗口内
        outside_time = time(12, 9, 59)
        
        with patch('hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime.combine(datetime.now().date(), outside_time)
            
            with patch.object(self.strategy, '_cancel_all_entry_orders_during_lunch_break') as mock_cancel_all:
                mock_event = Mock()
                self.strategy._on_market_close_timer(mock_event)
                mock_cancel_all.assert_not_called()
        
        # 测试 12:16 不在窗口内
        outside_time = time(12, 16, 0)
        
        with patch('hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime.combine(datetime.now().date(), outside_time)
            
            with patch.object(self.strategy, '_cancel_all_entry_orders_during_lunch_break') as mock_cancel_all:
                mock_event = Mock()
                self.strategy._on_market_close_timer(mock_event)
                mock_cancel_all.assert_not_called()


if __name__ == '__main__':
    unittest.main()
