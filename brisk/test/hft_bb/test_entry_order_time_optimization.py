"""
测试entry_order_time优化功能，防止频繁撤单
"""

import unittest
import sys
import os
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from hft_bb_reversal_strategy import HFTBBReversalStrategy, HFTBBStockContext, TriggerLevels
from vnpy.trader.constant import Direction


class TestEntryOrderTimeOptimization(unittest.TestCase):
    """测试entry_order_time优化功能"""
    
    def setUp(self):
        """设置测试环境"""
        self.strategy = HFTBBReversalStrategy(use_mock_gateway=True)
        self.strategy.write_log = Mock()
        self.strategy.create_hft_context("9984")
        self.context = self.strategy.get_hft_context("9984")
        
        # 设置trigger_levels
        self.context.trigger_levels = TriggerLevels(
            upper_trigger=100.2,
            upper_limit=100.5,
            lower_trigger=99.6,
            lower_limit=99.5
        )
        self.context.can_trade = True
    
    def test_entry_order_time_initialization(self):
        """测试entry_order_time初始化"""
        self.assertIsNone(self.context.entry_order_time)
    
    def test_entry_order_time_set_on_send(self):
        """测试发送订单时设置entry_order_time"""
        # 模拟发送订单
        with patch.object(self.strategy, '_execute_entry') as mock_execute:
            mock_execute.return_value = None
            # 模拟订单发送成功
            self.context.entry_order_id = "TEST_ORDER_123"
            
            self.strategy._send_entry_order("9984", Direction.LONG, 99.5, 100)
            
            # 验证entry_order_time被设置
            self.assertIsNotNone(self.context.entry_order_time)
            self.assertIsInstance(self.context.entry_order_time, datetime)
    
    def test_same_minute_no_cancel(self):
        """测试同一分钟内不取消订单"""
        # 设置当前订单
        self.context.entry_order_id = "TEST_ORDER_123"
        self.context.entry_price = 99.5
        self.context.entry_order_time = datetime.now()  # 刚刚发送的订单
        
        # 创建tick，价格在触发区间内（应该取消订单的情况）
        tick = Mock()
        tick.last_price = 99.8  # 在触发区间内
        tick.symbol = "9984"
        
        with patch.object(self.strategy, '_cancel_entry_order') as mock_cancel:
            self.strategy._check_entry_logic("9984", tick, self.context)
            
            # 验证没有调用取消订单方法
            mock_cancel.assert_not_called()
    
    def test_different_minute_cancel_order(self):
        """测试不同分钟时正常取消订单"""
        # 设置当前订单（2分钟前发送）
        self.context.entry_order_id = "TEST_ORDER_123"
        self.context.entry_price = 99.5
        self.context.entry_order_time = datetime.now() - timedelta(minutes=2)
        
        # 创建tick，价格在触发区间内
        tick = Mock()
        tick.last_price = 99.8  # 在触发区间内
        tick.symbol = "9984"
        
        with patch.object(self.strategy, '_cancel_entry_order') as mock_cancel:
            self.strategy._check_entry_logic("9984", tick, self.context)
            
            # 验证调用了取消订单方法
            mock_cancel.assert_called_once_with("9984", self.context, None)
    
    def test_no_entry_order_time_cancel_order(self):
        """测试没有entry_order_time时正常取消订单"""
        # 设置当前订单（没有entry_order_time）
        self.context.entry_order_id = "TEST_ORDER_123"
        self.context.entry_price = 99.5
        self.context.entry_order_time = None
        
        # 创建tick，价格在触发区间内
        tick = Mock()
        tick.last_price = 99.8  # 在触发区间内
        tick.symbol = "9984"
        
        with patch.object(self.strategy, '_cancel_entry_order') as mock_cancel:
            self.strategy._check_entry_logic("9984", tick, self.context)
            
            # 验证调用了取消订单方法
            mock_cancel.assert_called_once_with("9984", self.context, None)
    
    def test_cancel_order_clears_entry_order_time(self):
        """测试取消订单时清除entry_order_time"""
        # 设置当前订单
        self.context.entry_order_id = "TEST_ORDER_123"
        self.context.entry_order_time = datetime.now()
        
        with patch.object(self.strategy, '_cancel_order_safely') as mock_cancel_safe:
            mock_cancel_safe.return_value = True
            
            self.strategy._cancel_entry_order("9984", self.context)
            
            # 验证entry_order_time被清除
            self.assertIsNone(self.context.entry_order_time)
    
    def test_entry_filled_clears_entry_order_time(self):
        """测试订单成交时清除entry_order_time"""
        # 设置当前订单
        self.context.entry_order_id = "TEST_ORDER_123"
        self.context.entry_order_time = datetime.now()
        
        # 创建模拟订单
        order = Mock()
        order.direction = Direction.LONG
        order.volume = 100
        order.price = 99.5
        order.datetime = datetime.now()
        
        with patch.object(self.strategy, '_manage_exit_order') as mock_manage_exit:
            self.strategy._handle_entry_filled("9984", self.context, order)
            
            # 验证entry_order_time被清除
            self.assertIsNone(self.context.entry_order_time)
    
    def test_same_minute_skip_new_order(self):
        """测试同一分钟内跳过新订单发送"""
        # 设置当前订单
        self.context.entry_order_id = "TEST_ORDER_123"
        self.context.entry_price = 99.5
        self.context.entry_order_time = datetime.now()  # 刚刚发送的订单
        
        # 创建tick，触发下轨（应该发送新订单的情况）
        tick = Mock()
        tick.last_price = 99.4  # 触发下轨
        tick.symbol = "9984"
        
        with patch.object(self.strategy, '_send_entry_order') as mock_send:
            self.strategy._check_entry_logic("9984", tick, self.context)
            
            # 验证没有调用发送订单方法（因为同一分钟内有订单）
            mock_send.assert_not_called()
    
    def test_different_minute_cancel_order(self):
        """测试不同分钟时正常取消订单"""
        # 设置当前订单（2分钟前发送）
        self.context.entry_order_id = "TEST_ORDER_123"
        self.context.entry_price = 99.5
        self.context.entry_order_time = datetime.now() - timedelta(minutes=2)
        
        # 创建tick，价格在触发区间内（应该取消订单）
        tick = Mock()
        tick.last_price = 99.8  # 在触发区间内
        tick.symbol = "9984"
        
        with patch.object(self.strategy, '_cancel_entry_order') as mock_cancel:
            self.strategy._check_entry_logic("9984", tick, self.context)
            
            # 验证调用了取消订单方法
            mock_cancel.assert_called_once_with("9984", self.context, None)
    
    def test_no_existing_order_send_new_order(self):
        """测试没有现有订单时发送新订单"""
        # 没有现有订单
        self.context.entry_order_id = ""
        self.context.entry_price = 0.0
        self.context.entry_order_time = None
        
        # 创建tick，触发下轨
        tick = Mock()
        tick.last_price = 99.4  # 触发下轨
        tick.symbol = "9984"
        
        with patch.object(self.strategy, '_send_entry_order') as mock_send:
            self.strategy._check_entry_logic("9984", tick, self.context)
            
            # 验证调用了发送订单方法
            mock_send.assert_called_once_with("9984", Direction.LONG, 99.5, 100)


if __name__ == '__main__':
    unittest.main()
