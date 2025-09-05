#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

import unittest
from unittest.mock import Mock, patch
from datetime import datetime
from vnpy.trader.constant import Direction, Offset, Status, OrderType, Exchange
from vnpy.trader.object import OrderData

from brisk.hft_bb_reversal_strategy import HFTBBReversalStrategy


class TestPartialFillLogging(unittest.TestCase):
    """测试部分成交日志记录功能"""
    
    def setUp(self):
        """设置测试环境"""
        self.strategy = HFTBBReversalStrategy()
        self.strategy.write_log = Mock()
        
        # 添加测试股票
        self.strategy.add_symbol("9984")
        self.context = self.strategy.get_hft_context("9984")
        
        # 设置入场订单
        self.context.entry_order_id = "entry_123"
        self.context.position = 0
        
    def test_partial_fill_entry_order_logging(self):
        """测试入场订单部分成交的日志记录"""
        # 创建部分成交的订单事件
        order = OrderData(
            symbol="9984",
            exchange=Exchange.TSE,
            orderid="entry_123",
            type=OrderType.LIMIT,
            direction=Direction.LONG,
            offset=Offset.OPEN,
            price=100.0,
            volume=100,
            traded=50,  # 部分成交
            status=Status.PARTTRADED,
            datetime=datetime.now(),
            gateway_name="BriskGateway"
        )
        
        event = Mock()
        event.data = order
        
        # 调用on_order
        self.strategy.on_order(event)
        
        # 验证日志记录
        self.strategy.write_log.assert_any_call(
            "订单状态更新: 9984 Long Open 状态: Part Traded 价格: 100.00 数量: 100"
        )
        self.strategy.write_log.assert_any_call(
            "部分成交: 9984 Long Open 已成交数量: 50 剩余数量: 50"
        )
        
        # 验证没有处理成交逻辑（因为只是部分成交）
        # 检查position是否仍然为0
        self.assertEqual(self.context.position, 0)
        self.assertEqual(self.context.entry_order_id, "entry_123")
        
    def test_partial_fill_exit_order_logging(self):
        """测试出场订单部分成交的日志记录"""
        # 设置持仓和出场订单
        self.context.position = 100
        self.context.exit_order_id = "exit_456"
        
        # 创建部分成交的出场订单事件
        order = OrderData(
            symbol="9984",
            exchange=Exchange.TSE,
            orderid="exit_456",
            type=OrderType.LIMIT,
            direction=Direction.SHORT,
            offset=Offset.CLOSE,
            price=99.0,
            volume=100,
            traded=30,  # 部分成交
            status=Status.PARTTRADED,
            datetime=datetime.now(),
            gateway_name="BriskGateway"
        )
        
        event = Mock()
        event.data = order
        
        # 调用on_order
        self.strategy.on_order(event)
        
        # 验证日志记录
        self.strategy.write_log.assert_any_call(
            "订单状态更新: 9984 Short Close 状态: Part Traded 价格: 99.00 数量: 100"
        )
        self.strategy.write_log.assert_any_call(
            "部分成交: 9984 Short Close 已成交数量: 30 剩余数量: 70"
        )
        
        # 验证没有处理成交逻辑（因为只是部分成交）
        # 检查position是否仍然为100
        self.assertEqual(self.context.position, 100)
        self.assertEqual(self.context.exit_order_id, "exit_456")
        
    def test_partial_fill_unknown_order_logging(self):
        """测试未知订单部分成交的日志记录"""
        # 创建未知订单的部分成交事件
        order = OrderData(
            symbol="9984",
            exchange=Exchange.TSE,
            orderid="unknown_789",
            type=OrderType.LIMIT,
            direction=Direction.LONG,
            offset=Offset.OPEN,
            price=100.0,
            volume=100,
            traded=25,  # 部分成交
            status=Status.PARTTRADED,
            datetime=datetime.now(),
            gateway_name="BriskGateway"
        )
        
        event = Mock()
        event.data = order
        
        # 调用on_order
        self.strategy.on_order(event)
        
        # 验证日志记录
        self.strategy.write_log.assert_any_call(
            "订单状态更新: 9984 Long Open 状态: Part Traded 价格: 100.00 数量: 100"
        )
        self.strategy.write_log.assert_any_call(
            "部分成交: 9984 Long Open 已成交数量: 25 剩余数量: 75"
        )
        
    def test_all_traded_still_processed(self):
        """测试完全成交的订单仍然正常处理"""
        # 创建完全成交的订单事件
        order = OrderData(
            symbol="9984",
            exchange=Exchange.TSE,
            orderid="entry_123",
            type=OrderType.LIMIT,
            direction=Direction.LONG,
            offset=Offset.OPEN,
            price=100.0,
            volume=100,
            traded=100,  # 完全成交
            status=Status.ALLTRADED,
            datetime=datetime.now(),
            gateway_name="BriskGateway"
        )
        
        event = Mock()
        event.data = order
        
        # 调用on_order
        self.strategy.on_order(event)
        
        # 验证日志记录
        self.strategy.write_log.assert_any_call(
            "订单状态更新: 9984 Long Open 状态: All Traded 价格: 100.00 数量: 100"
        )
        
        # 验证没有部分成交日志
        partial_fill_logs = [call for call in self.strategy.write_log.call_args_list 
                           if "部分成交" in str(call)]
        self.assertEqual(len(partial_fill_logs), 0)
        
        # 验证position被更新（通过_handle_entry_filled）
        self.assertEqual(self.context.position, 100)
        self.assertEqual(self.context.entry_order_id, "")
        
    def test_other_status_not_processed(self):
        """测试其他状态（如NOTTRADED）不处理部分成交逻辑"""
        # 创建未成交的订单事件
        order = OrderData(
            symbol="9984",
            exchange=Exchange.TSE,
            orderid="entry_123",
            type=OrderType.LIMIT,
            direction=Direction.LONG,
            offset=Offset.OPEN,
            price=100.0,
            volume=100,
            traded=0,  # 未成交
            status=Status.NOTTRADED,
            datetime=datetime.now(),
            gateway_name="BriskGateway"
        )
        
        event = Mock()
        event.data = order
        
        # 调用on_order
        self.strategy.on_order(event)
        
        # 验证只有基本日志记录
        self.strategy.write_log.assert_any_call(
            "订单状态更新: 9984 Long Open 状态: Not Traded 价格: 100.00 数量: 100"
        )
        
        # 验证没有部分成交日志
        partial_fill_logs = [call for call in self.strategy.write_log.call_args_list 
                           if "部分成交" in str(call)]
        self.assertEqual(len(partial_fill_logs), 0)


if __name__ == '__main__':
    unittest.main()
