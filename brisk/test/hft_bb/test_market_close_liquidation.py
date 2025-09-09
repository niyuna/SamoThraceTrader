#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, time

from brisk.hft_bb_reversal_strategy import HFTBBReversalStrategy, HFTBBStockContext, StrategyState
# from brisk.intraday_strategy_base import StrategyState
from vnpy.trader.constant import Direction, Offset, Status, OrderType
from vnpy.trader.object import OrderData


class TestMarketCloseLiquidation(unittest.TestCase):
    """测试收盘前平仓功能"""
    
    def setUp(self):
        """设置测试环境"""
        self.strategy = HFTBBReversalStrategy()
        self.strategy.write_log = Mock()
        self.strategy.event_engine = Mock()
        self.strategy._cancel_order_safely = Mock(return_value=True)
        self.strategy._execute_exit = Mock(return_value="test_exit_order_123")
        self.strategy.get_order = Mock()
        
        # 添加测试股票
        self.strategy.add_symbol("9984")
        self.context = self.strategy.get_hft_context("9984")
        
    def test_market_close_timer_registration(self):
        """测试收盘前平仓定时器注册"""
        self.strategy._register_market_close_timer()
        
        # 验证event_engine.register被调用
        self.strategy.event_engine.register.assert_called_once()
        self.strategy.write_log.assert_called_with("收盘前平仓定时器已注册")
        
    def test_market_close_timer_disabled(self):
        """测试收盘前平仓功能禁用时"""
        self.strategy.market_close_liquidation_enabled = False
        self.strategy._register_market_close_timer()
        
        # 验证event_engine.register没有被调用
        self.strategy.event_engine.register.assert_not_called()
        
    def test_market_close_timer_no_event_engine(self):
        """测试没有event_engine时"""
        # 清除之前的write_log调用
        self.strategy.write_log.reset_mock()
        
        self.strategy.event_engine = None
        self.strategy._register_market_close_timer()
        
        # 验证没有异常，但没有注册
        self.strategy.write_log.assert_not_called()
        
    def test_timer_callback_before_check_time(self):
        """测试在检查时间之前调用timer"""
        # 清除之前的write_log调用
        self.strategy.write_log.reset_mock()
        
        # 设置时间为15:20（早于15:25）
        with patch('brisk.hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 1, 15, 20, 0)
            
            self.strategy._on_market_close_timer(Mock())
            
            # 验证没有执行平仓逻辑（除了定时器日志）
            calls = self.strategy.write_log.call_args_list
            self.assertEqual(len(calls), 1)
            self.assertIn("收盘前平仓定时器运行中", calls[0][0][0])
            
    def test_timer_callback_after_liquidation_executed(self):
        """测试在已执行平仓后调用timer"""
        # 清除之前的write_log调用
        self.strategy.write_log.reset_mock()
        
        self.strategy.liquidation_executed = True
        
        with patch('brisk.hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 1, 15, 30, 0)
            
            self.strategy._on_market_close_timer(Mock())
            
            # 验证没有执行平仓逻辑（除了定时器日志）
            calls = self.strategy.write_log.call_args_list
            self.assertEqual(len(calls), 1)
            self.assertIn("收盘前平仓定时器运行中", calls[0][0][0])
            
    def test_timer_callback_executes_liquidation(self):
        """测试timer在正确时间执行平仓"""
        with patch('brisk.hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 1, 15, 30, 0)
            
            self.strategy._on_market_close_timer(Mock())
            
            # 验证执行了平仓逻辑
            self.strategy.write_log.assert_any_call("开始执行收盘前平仓流程...")
            
    def test_timer_callback_logs_every_minute(self):
        """测试timer每分钟输出日志"""
        with patch('brisk.hft_bb_reversal_strategy.datetime') as mock_datetime:
            # 模拟15:30:00（每分钟的0秒）
            mock_datetime.now.return_value = datetime(2024, 1, 1, 15, 30, 0)
            
            self.strategy._on_market_close_timer(Mock())
            
            # 验证输出了定时器运行日志
            self.strategy.write_log.assert_any_call(
                "收盘前平仓定时器运行中，当前时间: 15:30:00, liquidation_executed: False"
            )
            
    def test_execute_liquidation_with_entry_order(self):
        """测试平仓时取消entry订单"""
        self.context.entry_order_id = "test_entry_123"
        self.context.position = 100  # 多头持仓
        
        self.strategy._execute_market_close_liquidation()
        
        # 验证取消了entry订单
        self.strategy._cancel_order_safely.assert_any_call("test_entry_123", "9984")
        self.assertEqual(self.context.entry_order_id, "")
        self.assertIsNone(self.context.entry_order_time)
        
    def test_execute_liquidation_with_exit_order(self):
        """测试平仓时取消exit订单并发送market订单"""
        self.context.exit_order_id = "test_exit_123"
        self.context.position = 100  # 多头持仓
        
        self.strategy._execute_market_close_liquidation()
        
        # 验证取消了exit订单
        self.strategy._cancel_order_safely.assert_any_call("test_exit_123", "9984")
        
        # 验证发送了market订单
        self.strategy._execute_exit.assert_called_once()
        call_args = self.strategy._execute_exit.call_args
        self.assertEqual(call_args[0][3], Direction.SHORT)  # 平仓方向
        self.assertEqual(call_args[0][4], OrderType.MARKET)  # 订单类型
        
    def test_execute_liquidation_short_position(self):
        """测试空头持仓的平仓"""
        self.context.position = -100  # 空头持仓
        
        self.strategy._execute_market_close_liquidation()
        
        # 验证发送了正确的平仓订单
        self.strategy._execute_exit.assert_called_once()
        call_args = self.strategy._execute_exit.call_args
        self.assertEqual(call_args[0][3], Direction.LONG)  # 买入平仓
        self.assertEqual(call_args[0][4], OrderType.MARKET)  # market订单
        
    def test_execute_liquidation_no_position(self):
        """测试没有持仓时不发送平仓订单"""
        self.context.position = 0
        
        self.strategy._execute_market_close_liquidation()
        
        # 验证没有发送平仓订单
        self.strategy._execute_exit.assert_not_called()
        
    def test_execute_liquidation_skip_closing_state(self):
        """测试跳过已在closing处理的股票"""
        # 清除之前的write_log调用
        self.strategy.write_log.reset_mock()
        
        # 确保我们操作的是hft_contexts中的同一个对象
        context = self.strategy.hft_contexts["9984"]
        context.state = StrategyState.WAITING_TIMEOUT_EXIT
        context.position = 100
        
        # 验证状态设置正确
        self.assertEqual(context.state, StrategyState.WAITING_TIMEOUT_EXIT)
        
        # 添加调试信息
        print(f"Before liquidation - Context state: {context.state}")
        print(f"StrategyState.WAITING_TIMEOUT_EXIT: {StrategyState.WAITING_TIMEOUT_EXIT}")
        print(f"Are they equal? {context.state == StrategyState.WAITING_TIMEOUT_EXIT}")
        
        # 验证context确实是hft_contexts中的对象
        self.assertIs(context, self.strategy.hft_contexts["9984"])
        
        self.strategy._execute_market_close_liquidation()
        
        # 验证跳过了已在closing处理的股票
        self.strategy.write_log.assert_any_call("跳过已在closing处理的股票: 9984")
        self.strategy._execute_exit.assert_not_called()
        
    def test_execute_liquidation_success(self):
        """测试平仓成功的情况"""
        self.context.position = 100
        self.context.entry_order_id = "test_entry_123"
        
        self.strategy._execute_market_close_liquidation()
        
        # 验证liquidation_executed被设置为True
        self.assertTrue(self.strategy.liquidation_executed)
        self.strategy.write_log.assert_any_call("收盘前平仓订单发送完成，成功: 2个")
        
    def test_execute_liquidation_with_failures(self):
        """测试平仓有失败的情况"""
        # 清除之前的write_log调用
        self.strategy.write_log.reset_mock()
        
        self.context.position = 100
        self.strategy._cancel_order_safely.return_value = False  # 模拟取消失败
        self.strategy._execute_exit.return_value = None  # 模拟发送失败
        
        self.strategy._execute_market_close_liquidation()
        
        # 验证liquidation_executed保持False
        self.assertFalse(self.strategy.liquidation_executed)
        self.strategy.write_log.assert_any_call("收盘前平仓部分失败，成功: 0个，失败: 1个，将重试")
        
    def test_execute_liquidation_mixed_success_failure(self):
        """测试部分成功部分失败的情况"""
        # 清除之前的write_log调用
        self.strategy.write_log.reset_mock()
        
        # 添加第二个股票
        self.strategy.add_symbol("6098")
        context2 = self.strategy.get_hft_context("6098")
        context2.position = 50
        context2.entry_order_id = "test_entry_456"
        
        # 第一个股票成功，第二个股票失败
        def mock_cancel_order_safely(order_id, symbol):
            return symbol == "9984"  # 只有9984成功
            
        def mock_execute_exit(context, bar, price, direction, order_type):
            return "test_exit_123" if context.symbol == "9984" else None
            
        self.strategy._cancel_order_safely.side_effect = mock_cancel_order_safely
        self.strategy._execute_exit.side_effect = mock_execute_exit
        
        self.strategy._execute_market_close_liquidation()
        
        # 验证liquidation_executed保持False（因为有失败）
        self.assertFalse(self.strategy.liquidation_executed)
        # 打印所有日志调用来调试
        calls = self.strategy.write_log.call_args_list
        print(f"Actual log calls: {calls}")
        # 检查是否有失败日志（不检查具体数量）
        failure_log_found = any("收盘前平仓部分失败" in str(call) for call in calls)
        self.assertTrue(failure_log_found, "应该输出失败日志")
        
    def test_execute_liquidation_updates_context_state(self):
        """测试平仓时更新context状态"""
        self.context.position = 100
        
        self.strategy._execute_market_close_liquidation()
        
        # 验证context状态被更新
        self.assertEqual(self.context.state.value, StrategyState.WAITING_TIMEOUT_EXIT.value)
        self.assertEqual(self.context.exit_order_id, "test_exit_order_123")
        
    def test_execute_liquidation_clears_entry_order_time(self):
        """测试平仓时清除entry_order_time"""
        self.context.entry_order_id = "test_entry_123"
        self.context.entry_order_time = datetime.now()
        
        self.strategy._execute_market_close_liquidation()
        
        # 验证entry_order_time被清除
        self.assertIsNone(self.context.entry_order_time)


if __name__ == '__main__':
    unittest.main()
