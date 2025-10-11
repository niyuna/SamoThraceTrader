#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import unittest
from unittest.mock import Mock, patch
from datetime import datetime

from brisk.hft_bb_reversal_strategy import HFTBBReversalStrategy, HFTBBStockContext, TriggerLevels
from vnpy.trader.constant import Direction, Exchange
from vnpy.trader.object import TickData


class Test1524CancelProtection(unittest.TestCase):
    """测试15:24分钟取消订单保护功能"""
    
    def setUp(self):
        """设置测试环境"""
        self.strategy = HFTBBReversalStrategy()
        self.strategy.write_log = Mock()
        self.strategy._cancel_entry_order = Mock()
        self.strategy._send_entry_order = Mock()
        
        # 覆盖策略参数，使测试独立于默认参数
        self.strategy.price_limit_morning = 5000    # 提高morning时段价格限制
        self.strategy.price_limit_noon = 5000       # 提高noon时段价格限制  
        self.strategy.price_limit_afternoon = 5000  # 提高afternoon时段价格限制
        self.strategy.max_price_change_pct = 20.0   # 提高价格变动限制
        
        # 创建测试用的 context
        self.context = HFTBBStockContext(symbol="9984")
        self.context.position = 0
        self.context.entry_order_id = "test_order_123"
        self.context.entry_price = 100.0
        self.context.entry_order_time = datetime(2024, 1, 1, 10, 0, 0)  # 设置为较早时间，避免同一分钟保护
        self.context.can_trade = ['long', 'short']
        self.context.position_size = 100
        
        # 设置触发水平
        self.context.trigger_levels = TriggerLevels(
            upper_trigger=105.0,
            lower_trigger=95.0,
            upper_limit=104.0,
            lower_limit=96.0
        )
        
        # 创建测试用的 tick
        self.tick = TickData(
            symbol="9984",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            name="Test Stock",
            volume=1000,
            last_price=100.0,
            last_volume=100,
            limit_up=110.0,
            limit_down=90.0,
            open_price=99.0,
            high_price=101.0,
            low_price=98.0,
            pre_close=99.5,
            gateway_name="TEST"
        )
    
    def test_15_24_no_cancel(self):
        """测试15:24时不取消订单"""
        with patch('brisk.hft_bb_reversal_strategy.datetime') as mock_datetime:
            # 模拟15:24时间
            mock_datetime.now.return_value = datetime(2024, 1, 1, 15, 24, 0)
            
            # 价格在触发区间内，正常情况下应该取消订单
            self.tick.last_price = 100.0  # 在95-105之间
            
            self.strategy._check_entry_logic("9984", self.tick, self.context)
            
            # 验证没有调用取消订单
            self.strategy._cancel_entry_order.assert_not_called()
            
            # 验证日志输出
            self.strategy.write_log.assert_any_call(
                "跳过取消订单: 9984 当前时间在15:24分钟(15:24)，避免收盘前频繁撤单损耗API配额"
            )
    
    def test_15_24_price_different_no_cancel(self):
        """测试15:24时价格不同也不取消订单"""
        with patch('brisk.hft_bb_reversal_strategy.datetime') as mock_datetime:
            # 模拟15:24时间
            mock_datetime.now.return_value = datetime(2024, 1, 1, 15, 24, 0)
            
            # 价格触发下轨，应该取消并重下订单
            self.tick.last_price = 94.0  # 触发下轨
            
            self.strategy._check_entry_logic("9984", self.tick, self.context)
            
            # 验证没有调用取消订单
            self.strategy._cancel_entry_order.assert_not_called()
            
            # 验证日志输出
            self.strategy.write_log.assert_any_call(
                "跳过取消订单: 9984 当前时间在15:24分钟(15:24)，避免收盘前频繁撤单损耗API配额"
            )
    
    def test_15_23_cancel_allowed(self):
        """测试15:23时允许取消订单"""
        with patch('brisk.hft_bb_reversal_strategy.datetime') as mock_datetime:
            # 模拟15:23时间（不在保护期间）
            mock_datetime.now.return_value = datetime(2024, 1, 1, 15, 23, 0)
            
            # 价格在触发区间内，应该取消订单
            self.tick.last_price = 100.0  # 在95-105之间
            
            self.strategy._check_entry_logic("9984", self.tick, self.context)
            
            # 验证调用了取消订单
            self.strategy._cancel_entry_order.assert_called_once()
    
    def test_15_25_cancel_allowed(self):
        """测试15:25时允许取消订单"""
        with patch('brisk.hft_bb_reversal_strategy.datetime') as mock_datetime:
            # 模拟15:25时间（不在保护期间）
            mock_datetime.now.return_value = datetime(2024, 1, 1, 15, 25, 0)
            
            # 价格在触发区间内，应该取消订单
            self.tick.last_price = 100.0  # 在95-105之间
            
            self.strategy._check_entry_logic("9984", self.tick, self.context)
            
            # 验证调用了取消订单
            self.strategy._cancel_entry_order.assert_called_once()
    
    def test_other_hours_cancel_allowed(self):
        """测试其他时间允许取消订单"""
        test_times = [
            (9, 30),   # 早上
            (10, 15),  # 上午
            (11, 32),  # 中午后
            (12, 30),  # 下午
            (14, 30),  # 下午
            (15, 0),   # 收盘前
        ]
        
        for hour, minute in test_times:
            with patch('brisk.hft_bb_reversal_strategy.datetime') as mock_datetime:
                # 模拟不同时间
                mock_datetime.now.return_value = datetime(2024, 1, 1, hour, minute, 0)
                
                # 重置 mock 和 context 状态
                self.strategy._cancel_entry_order.reset_mock()
                self.strategy.write_log.reset_mock()
                
                # 确保 context 有 entry_order_id
                self.context.entry_order_id = "test_order_123"
                self.context.entry_order_time = datetime(2024, 1, 1, 9, 0, 0)  # 确保不是同一分钟
                
                # 价格在触发区间内，应该取消订单
                self.tick.last_price = 100.0  # 在95-105之间
                
                self.strategy._check_entry_logic("9984", self.tick, self.context)
                
                # 验证调用了取消订单
                self.strategy._cancel_entry_order.assert_called_once()
    
    def test_15_24_with_different_seconds(self):
        """测试15:24的不同秒数都不取消订单"""
        test_seconds = [0, 15, 30, 45, 59]
        
        for second in test_seconds:
            with patch('brisk.hft_bb_reversal_strategy.datetime') as mock_datetime:
                # 模拟15:24的不同秒数
                mock_datetime.now.return_value = datetime(2024, 1, 1, 15, 24, second)
                
                # 重置 mock
                self.strategy._cancel_entry_order.reset_mock()
                self.strategy.write_log.reset_mock()
                
                # 价格在触发区间内，正常情况下应该取消订单
                self.tick.last_price = 100.0  # 在95-105之间
                
                self.strategy._check_entry_logic("9984", self.tick, self.context)
                
                # 验证没有调用取消订单
                self.strategy._cancel_entry_order.assert_not_called()
                
                # 验证日志输出
                self.strategy.write_log.assert_any_call(
                    f"跳过取消订单: 9984 当前时间在15:24分钟(15:24)，避免收盘前频繁撤单损耗API配额"
                )


if __name__ == '__main__':
    unittest.main()
