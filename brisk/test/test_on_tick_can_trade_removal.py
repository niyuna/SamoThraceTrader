#!/usr/bin/env python3
"""
测试移除on_tick中的can_trade检查后的行为
"""

import unittest
from unittest.mock import Mock, patch
from datetime import datetime, time
import sys
import os

# 添加brisk目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from hft_bb_reversal_strategy import HFTBBReversalStrategy, HFTBBStockContext, TriggerLevels
from vnpy.trader.constant import Direction, Exchange
from vnpy.trader.object import TickData


class TestOnTickCanTradeRemoval(unittest.TestCase):
    """测试移除on_tick中的can_trade检查后的行为"""
    
    def setUp(self):
        """设置测试环境"""
        self.strategy = HFTBBReversalStrategy()
        self.strategy.write_log = Mock()
        self.strategy._cancel_entry_order = Mock()
        self.strategy._send_entry_order = Mock()
        
        # 创建测试用的context
        self.context = HFTBBStockContext(
            symbol="9984",
            position_size=100,
            trigger_levels=TriggerLevels(
                upper_trigger=100.0,
                upper_limit=99.5,
                lower_trigger=95.0,
                lower_limit=95.5
            ),
            bb_levels={
                'upper': 100.0,
                'lower': 95.0,
                'middle': 97.5,
                'std': 0.8
            }
        )
        self.strategy.hft_contexts["9984"] = self.context
    
    def test_on_tick_calls_check_entry_logic_when_can_trade_empty(self):
        """测试当can_trade为空列表时，on_tick仍然会调用_check_entry_logic"""
        # 设置can_trade为空列表
        self.context.can_trade = []
        
        # 创建tick数据
        tick = TickData(
            symbol="9984",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            gateway_name="test",
            last_price=96.0
        )
        
        # 创建event对象
        event = Mock()
        event.data = tick
        
        # 调用on_tick
        self.strategy.on_tick(event)
        
        # 验证_check_entry_logic被调用（通过检查_cancel_entry_order是否被调用）
        # 因为can_trade为空，_check_entry_logic应该取消现有订单
        self.context.entry_order_id = "test_order_123"
        self.strategy.on_tick(event)
        
        # 验证_cancel_entry_order被调用
        self.strategy._cancel_entry_order.assert_called()
    
    def test_on_tick_calls_check_entry_logic_when_can_trade_none(self):
        """测试当can_trade为None时，on_tick仍然会调用_check_entry_logic"""
        # 设置can_trade为None
        self.context.can_trade = None
        
        # 创建tick数据
        tick = TickData(
            symbol="9984",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            gateway_name="test",
            last_price=96.0
        )
        
        # 创建event对象
        event = Mock()
        event.data = tick
        
        # 调用on_tick
        self.strategy.on_tick(event)
        
        # 验证_check_entry_logic被调用（通过检查_cancel_entry_order是否被调用）
        # 因为can_trade为None，_check_entry_logic应该取消现有订单
        self.context.entry_order_id = "test_order_123"
        self.strategy.on_tick(event)
        
        # 验证_cancel_entry_order被调用
        self.strategy._cancel_entry_order.assert_called()
    
    def test_on_tick_calls_check_entry_logic_when_can_trade_false(self):
        """测试当can_trade为False时，on_tick仍然会调用_check_entry_logic"""
        # 设置can_trade为False（虽然这不应该发生，但测试边界情况）
        self.context.can_trade = False
        
        # 创建tick数据
        tick = TickData(
            symbol="9984",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            gateway_name="test",
            last_price=96.0
        )
        
        # 创建event对象
        event = Mock()
        event.data = tick
        
        # 调用on_tick
        self.strategy.on_tick(event)
        
        # 验证_check_entry_logic被调用（通过检查_cancel_entry_order是否被调用）
        # 因为can_trade为False，_check_entry_logic应该取消现有订单
        self.context.entry_order_id = "test_order_123"
        self.strategy.on_tick(event)
        
        # 验证_cancel_entry_order被调用
        self.strategy._cancel_entry_order.assert_called()
    
    def test_on_tick_does_not_call_check_entry_logic_when_no_trigger_levels(self):
        """测试当没有trigger_levels时，on_tick不会调用_check_entry_logic"""
        # 设置trigger_levels为None
        self.context.trigger_levels = None
        
        # 创建tick数据
        tick = TickData(
            symbol="9984",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            gateway_name="test",
            last_price=96.0
        )
        
        # 创建event对象
        event = Mock()
        event.data = tick
        
        # 调用on_tick
        self.strategy.on_tick(event)
        
        # 验证_check_entry_logic没有被调用
        self.strategy._cancel_entry_order.assert_not_called()
        self.strategy._send_entry_order.assert_not_called()
    
    def test_check_entry_logic_handles_empty_can_trade_correctly(self):
        """测试_check_entry_logic正确处理空的can_trade"""
        # 设置can_trade为空列表
        self.context.can_trade = []
        self.context.entry_order_id = "test_order_123"
        
        # 创建tick数据
        tick = TickData(
            symbol="9984",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            gateway_name="test",
            last_price=96.0
        )
        
        # 调用_check_entry_logic
        self.strategy._check_entry_logic("9984", tick, self.context)
        
        # 验证取消订单被调用
        self.strategy._cancel_entry_order.assert_called_with("9984", self.context)
    
    def test_check_entry_logic_handles_none_can_trade_correctly(self):
        """测试_check_entry_logic正确处理None的can_trade"""
        # 设置can_trade为None
        self.context.can_trade = None
        self.context.entry_order_id = "test_order_123"
        
        # 创建tick数据
        tick = TickData(
            symbol="9984",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            gateway_name="test",
            last_price=96.0
        )
        
        # 调用_check_entry_logic
        self.strategy._check_entry_logic("9984", tick, self.context)
        
        # 验证取消订单被调用
        self.strategy._cancel_entry_order.assert_called_with("9984", self.context)


if __name__ == '__main__':
    unittest.main()
