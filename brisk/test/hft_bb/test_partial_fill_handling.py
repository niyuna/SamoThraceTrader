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


class TestPartialFillHandling(unittest.TestCase):
    """测试部分成交处理功能"""
    
    def setUp(self):
        """设置测试环境"""
        self.strategy = HFTBBReversalStrategy()
        self.strategy.write_log = Mock()
        self.strategy._cancel_order_safely = Mock(return_value=True)
        self.strategy._execute_exit = Mock(return_value="exit_123")
        
        # 添加测试股票
        self.strategy.add_symbol("9984")
        self.context = self.strategy.get_hft_context("9984")
        
        # 设置基本参数
        self.context.position_size = 1000
        self.context.already_traded = 0
        self.context.position = 0
        
    def test_partial_fill_entry_order_updates_position(self):
        """测试部分成交入场订单更新持仓"""
        # 设置入场订单ID
        self.context.entry_order_id = "entry_123"
        
        # 创建部分成交的入场订单事件
        order = OrderData(
            symbol="9984",
            exchange=Exchange.TSE,
            orderid="entry_123",
            type=OrderType.LIMIT,
            direction=Direction.LONG,
            offset=Offset.OPEN,
            price=100.0,
            volume=1000,
            traded=400,  # 部分成交400股
            status=Status.PARTTRADED,
            datetime=datetime.now(),
            gateway_name="BriskGateway"
        )
        
        event = Mock()
        event.data = order
        
        # 调用on_order
        self.strategy.on_order(event)
        
        # 验证持仓更新
        self.assertEqual(self.context.position, 400)
        self.assertEqual(self.context.already_traded, 400)
        
        # 验证日志记录
        self.strategy.write_log.assert_any_call(
            "更新持仓: 9984 position=400 already_traded=400"
        )
        
    def test_partial_fill_short_entry_order_updates_position(self):
        """测试部分成交空头入场订单更新持仓"""
        # 设置入场订单ID
        self.context.entry_order_id = "entry_123"
        
        # 创建部分成交的空头入场订单事件
        order = OrderData(
            symbol="9984",
            exchange=Exchange.TSE,
            orderid="entry_123",
            type=OrderType.LIMIT,
            direction=Direction.SHORT,
            offset=Offset.OPEN,
            price=100.0,
            volume=1000,
            traded=300,  # 部分成交300股
            status=Status.PARTTRADED,
            datetime=datetime.now(),
            gateway_name="BriskGateway"
        )
        
        event = Mock()
        event.data = order
        
        # 调用on_order
        self.strategy.on_order(event)
        
        # 验证持仓更新
        self.assertEqual(self.context.position, -300)
        self.assertEqual(self.context.already_traded, 300)
        
    def test_partial_fill_exit_order_updates_position(self):
        """测试部分成交出场订单更新持仓"""
        # 设置初始持仓
        self.context.position = 1000
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
            volume=1000,
            traded=200,  # 部分成交200股
            status=Status.PARTTRADED,
            datetime=datetime.now(),
            gateway_name="BriskGateway"
        )
        
        event = Mock()
        event.data = order
        
        # 调用on_order
        self.strategy.on_order(event)
        
        # 验证持仓更新
        self.assertEqual(self.context.position, 800)  # 1000 - 200
        self.assertEqual(self.context.already_traded, 200)
        
    def test_manage_exit_order_with_partial_fill_cancels_entry(self):
        """测试部分成交时管理出场订单会取消入场订单"""
        # 设置部分成交状态
        self.context.position = 400  # 部分成交400股
        self.context.already_traded = 400
        self.context.entry_order_id = "entry_123"
        self.context.position_size = 1000
        
        # 设置BB水平
        bb_levels = {
            'exit_long': 99.0,
            'exit_short': 101.0
        }
        
        # 调用_manage_exit_order
        self.strategy._manage_exit_order("9984", bb_levels)
        
        # 验证取消了入场订单
        self.strategy._cancel_order_safely.assert_called_once_with("entry_123", "9984")
        self.assertEqual(self.context.entry_order_id, "")
        self.assertEqual(self.context.entry_order_time, None)
        
        # 验证发送了出场订单
        self.strategy._execute_exit.assert_called_once()
        
    def test_manage_exit_order_adjusts_already_traded(self):
        """测试管理出场订单时调整already_traded"""
        # 设置部分成交状态
        self.context.position = 400  # 部分成交400股
        self.context.already_traded = 400
        self.context.position_size = 1000
        
        # 设置BB水平
        bb_levels = {
            'exit_long': 99.0,
            'exit_short': 101.0
        }
        
        # 调用_manage_exit_order
        self.strategy._manage_exit_order("9984", bb_levels)
        
        # 验证already_traded被调整
        self.assertEqual(self.context.already_traded, 600)  # 1000 - 400
        
        # 验证日志记录
        self.strategy.write_log.assert_any_call(
            "调整already_traded为600 用于发送400股exit订单"
        )
        
    def test_manage_exit_order_with_full_position(self):
        """测试完整持仓时管理出场订单不调整already_traded"""
        # 设置完整持仓状态
        self.context.position = 1000  # 完整持仓1000股
        self.context.already_traded = 0
        self.context.position_size = 1000
        
        # 设置BB水平
        bb_levels = {
            'exit_long': 99.0,
            'exit_short': 101.0
        }
        
        # 调用_manage_exit_order
        self.strategy._manage_exit_order("9984", bb_levels)
        
        # 验证already_traded被调整
        self.assertEqual(self.context.already_traded, 0)  # 1000 - 1000
        
        # 验证发送了出场订单
        self.strategy._execute_exit.assert_called_once()
        
    def test_manage_exit_order_short_position(self):
        """测试空头持仓时管理出场订单"""
        # 设置空头持仓状态
        self.context.position = -500  # 空头持仓500股
        self.context.already_traded = 0
        self.context.position_size = 1000
        
        # 设置BB水平
        bb_levels = {
            'exit_long': 99.0,
            'exit_short': 101.0
        }
        
        # 调用_manage_exit_order
        self.strategy._manage_exit_order("9984", bb_levels)
        
        # 验证already_traded被调整
        self.assertEqual(self.context.already_traded, 500)  # 1000 - 500
        
        # 验证发送了出场订单
        self.strategy._execute_exit.assert_called_once()
        
    def test_manage_exit_order_no_position(self):
        """测试无持仓时不发送出场订单"""
        # 设置无持仓状态
        self.context.position = 0
        self.context.already_traded = 0
        
        # 设置BB水平
        bb_levels = {
            'exit_long': 99.0,
            'exit_short': 101.0
        }
        
        # 调用_manage_exit_order
        self.strategy._manage_exit_order("9984", bb_levels)
        
        # 验证没有发送出场订单
        self.strategy._execute_exit.assert_not_called()
        
    def test_partial_fill_entry_then_exit_flow(self):
        """测试部分成交入场后发送出场订单的完整流程"""
        # 设置入场订单ID
        self.context.entry_order_id = "entry_123"
        
        # 1. 部分成交入场订单
        entry_order = OrderData(
            symbol="9984",
            exchange=Exchange.TSE,
            orderid="entry_123",
            type=OrderType.LIMIT,
            direction=Direction.LONG,
            offset=Offset.OPEN,
            price=100.0,
            volume=1000,
            traded=400,  # 部分成交400股
            status=Status.PARTTRADED,
            datetime=datetime.now(),
            gateway_name="BriskGateway"
        )
        
        event = Mock()
        event.data = entry_order
        
        # 调用on_order
        self.strategy.on_order(event)
        
        # 验证持仓更新
        self.assertEqual(self.context.position, 400)
        self.assertEqual(self.context.already_traded, 400)
        
        # 2. 设置BB水平并调用_manage_exit_order
        bb_levels = {
            'exit_long': 99.0,
            'exit_short': 101.0
        }
        
        # 调用_manage_exit_order
        self.strategy._manage_exit_order("9984", bb_levels)
        
        # 验证already_traded被调整
        self.assertEqual(self.context.already_traded, 600)  # 1000 - 400
        
        # 验证发送了出场订单
        self.strategy._execute_exit.assert_called_once()
        
    def test_partial_fill_exit_order_updates_already_traded(self):
        """测试部分成交出场订单更新already_traded"""
        # 设置初始状态
        self.context.position = 1000
        self.context.exit_order_id = "exit_456"
        self.context.already_traded = 0
        
        # 创建部分成交的出场订单事件
        order = OrderData(
            symbol="9984",
            exchange=Exchange.TSE,
            orderid="exit_456",
            type=OrderType.LIMIT,
            direction=Direction.SHORT,
            offset=Offset.CLOSE,
            price=99.0,
            volume=1000,
            traded=300,  # 部分成交300股
            status=Status.PARTTRADED,
            datetime=datetime.now(),
            gateway_name="BriskGateway"
        )
        
        event = Mock()
        event.data = order
        
        # 调用on_order
        self.strategy.on_order(event)
        
        # 验证already_traded更新
        self.assertEqual(self.context.already_traded, 300)
        self.assertEqual(self.context.position, 700)  # 1000 - 300


if __name__ == '__main__':
    unittest.main()
