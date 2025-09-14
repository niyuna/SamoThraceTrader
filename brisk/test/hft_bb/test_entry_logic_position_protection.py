#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

import unittest
from unittest.mock import Mock, patch
from datetime import datetime

from brisk.hft_bb_reversal_strategy import HFTBBReversalStrategy
from vnpy.trader.constant import Direction, Offset, Exchange
from vnpy.trader.object import TickData


class TestEntryLogicPositionProtection(unittest.TestCase):
    """测试entry逻辑的持仓保护机制"""
    
    def setUp(self):
        """设置测试环境"""
        self.strategy = HFTBBReversalStrategy()
        self.strategy.write_log = Mock()
        
        # 添加测试股票
        self.strategy.add_symbol("9984")
        self.context = self.strategy.get_hft_context("9984")
        
        # 设置BB levels和trigger levels
        self.context.bb_levels = {
            'std': 0.8,
            'middle': 1000.0,
            'upper': 1003.0,
            'lower': 997.0,
            'exit_long': 1001.0,
            'exit_short': 999.0
        }
        
        # 设置trigger levels
        from brisk.hft_bb_reversal_strategy import TriggerLevels
        self.context.trigger_levels = TriggerLevels(
            upper_trigger=1002.0,
            upper_limit=1003.0,
            lower_trigger=998.0,
            lower_limit=997.0
        )
        
        # 设置can_trade为True（模拟X条件通过）
        self.context.can_trade = True
        
        # 创建模拟tick数据
        self.tick = TickData(
            symbol="9984",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            name="测试股票",
            last_price=1001.0,
            volume=100,
            turnover=100000.0,
            open_interest=0.0,
            bid_price_1=1000.5,
            bid_volume_1=100,
            ask_price_1=1001.5,
            ask_volume_1=100,
            gateway_name="test"
        )
        
    def test_entry_logic_with_position_skips(self):
        """测试有持仓时跳过entry逻辑"""
        # 设置持仓
        self.context.position = 100  # 多头持仓
        
        # 调用entry逻辑
        self.strategy._check_entry_logic("9984", self.tick, self.context)
        
        # 验证日志
        self.strategy.write_log.assert_any_call(
            "跳过entry逻辑: 9984 已有持仓 100"
        )
        
        # 验证没有发送订单（通过检查日志中没有"触发上轨"或"触发下轨"）
        log_calls = [call[0][0] for call in self.strategy.write_log.call_args_list]
        self.assertNotIn("触发上轨", " ".join(log_calls))
        self.assertNotIn("触发下轨", " ".join(log_calls))
        
    def test_entry_logic_with_short_position_skips(self):
        """测试有空头持仓时跳过entry逻辑"""
        # 设置空头持仓
        self.context.position = -100
        
        # 调用entry逻辑
        self.strategy._check_entry_logic("9984", self.tick, self.context)
        
        # 验证日志
        self.strategy.write_log.assert_any_call(
            "跳过entry逻辑: 9984 已有持仓 -100"
        )
        
    def test_entry_logic_with_exit_order_skips(self):
        """测试有exit订单时跳过entry逻辑"""
        # 设置exit订单
        self.context.exit_order_id = "exit_order_123"
        
        # 调用entry逻辑
        self.strategy._check_entry_logic("9984", self.tick, self.context)
        
        # 验证日志
        self.strategy.write_log.assert_any_call(
            "跳过entry逻辑: 9984 已有exit订单"
        )
        
    def test_entry_logic_with_position_and_exit_order_skips(self):
        """测试同时有持仓和exit订单时跳过entry逻辑"""
        # 设置持仓和exit订单
        self.context.position = 100
        self.context.exit_order_id = "exit_order_123"
        
        # 调用entry逻辑
        self.strategy._check_entry_logic("9984", self.tick, self.context)
        
        # 验证日志（应该先检查持仓）
        self.strategy.write_log.assert_any_call(
            "跳过entry逻辑: 9984 已有持仓 100"
        )
        
    def test_entry_logic_without_position_or_exit_order_proceeds(self):
        """测试没有持仓和exit订单时正常执行entry逻辑"""
        # 确保没有持仓和exit订单
        self.context.position = 0
        self.context.exit_order_id = ""
        
        # 设置价格触发下轨
        self.tick.last_price = 997.5  # 低于lower_trigger (998.0)
        
        # Mock _send_entry_order方法
        with patch.object(self.strategy, '_send_entry_order') as mock_send:
            # 调用entry逻辑
            self.strategy._check_entry_logic("9984", self.tick, self.context)
            
            # 验证没有跳过日志
            log_calls = [call[0][0] for call in self.strategy.write_log.call_args_list]
            self.assertNotIn("跳过entry逻辑", " ".join(log_calls))
            
            # 验证触发了下轨逻辑
            self.strategy.write_log.assert_any_call(
                "触发下轨: 9984 价格997.50 <= 触发价格998.00"
            )
            
            # 验证调用了_send_entry_order
            mock_send.assert_called_once()
            
    def test_entry_logic_with_existing_entry_order_proceeds(self):
        """测试有entry订单但没有持仓和exit订单时正常执行逻辑"""
        # 设置entry订单但没有持仓和exit订单
        self.context.entry_order_id = "entry_order_123"
        self.context.position = 0
        self.context.exit_order_id = ""
        self.context.entry_price = 1000.0  # 设置一个不同的价格
        
        # 设置价格在触发范围内（应该触发取消）
        self.tick.last_price = 1000.5  # 在998.0 < 1000.5 < 1002.0范围内
        
        # Mock _cancel_entry_order方法
        with patch.object(self.strategy, '_cancel_entry_order') as mock_cancel:
            # 调用entry逻辑
            self.strategy._check_entry_logic("9984", self.tick, self.context)
            
            # 验证没有跳过日志
            log_calls = [call[0][0] for call in self.strategy.write_log.call_args_list]
            self.assertNotIn("跳过entry逻辑", " ".join(log_calls))
            
            # 验证触发了取消逻辑（价格在触发范围内）
            mock_cancel.assert_called_once_with("9984", self.context, None)
            
    def test_entry_logic_position_check_priority(self):
        """测试持仓检查的优先级高于exit订单检查"""
        # 同时设置持仓和exit订单
        self.context.position = 50
        self.context.exit_order_id = "exit_order_123"
        
        # 调用entry逻辑
        self.strategy._check_entry_logic("9984", self.tick, self.context)
        
        # 验证先检查持仓
        log_calls = [call[0][0] for call in self.strategy.write_log.call_args_list]
        position_log = "跳过entry逻辑: 9984 已有持仓 50"
        exit_log = "跳过entry逻辑: 9984 已有exit订单"
        
        self.assertIn(position_log, log_calls)
        self.assertNotIn(exit_log, log_calls)  # 不应该检查exit订单，因为已经因为持仓跳过了
        
    def test_entry_logic_zero_position_not_skipped(self):
        """测试零持仓时不被跳过"""
        # 设置零持仓
        self.context.position = 0
        self.context.exit_order_id = ""
        
        # 设置价格触发上轨
        self.tick.last_price = 1002.5  # 高于upper_trigger (1002.0)
        
        # Mock _send_entry_order方法
        with patch.object(self.strategy, '_send_entry_order') as mock_send:
            # 调用entry逻辑
            self.strategy._check_entry_logic("9984", self.tick, self.context)
            
            # 验证没有跳过日志
            log_calls = [call[0][0] for call in self.strategy.write_log.call_args_list]
            self.assertNotIn("跳过entry逻辑", " ".join(log_calls))
            
            # 验证触发了上轨逻辑
            self.strategy.write_log.assert_any_call(
                "触发上轨: 9984 价格1002.50 >= 触发价格1002.00"
            )


if __name__ == '__main__':
    unittest.main()
