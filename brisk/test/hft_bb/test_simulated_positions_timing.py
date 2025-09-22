#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import unittest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

from brisk.hft_bb_reversal_strategy import HFTBBReversalStrategy, HFTBBStockContext
from vnpy.trader.constant import Direction, Exchange
from vnpy.trader.object import TickData


class TestSimulatedPositionsTiming(unittest.TestCase):
    """测试模拟持仓时间记录功能"""
    
    def setUp(self):
        """设置测试环境"""
        self.strategy = HFTBBReversalStrategy()
        self.strategy.write_log = Mock()
        
        # 创建测试用的 context
        self.context = HFTBBStockContext(symbol="9984")
        self.context.bb_levels = {
            'upper': 105.0,
            'lower': 95.0,
            'exit_long': 100.0,
            'exit_short': 100.0
        }
        
        # 模拟 get_hft_context 方法
        self.strategy.get_hft_context = Mock(return_value=self.context)
        
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
    
    def test_long_entry_timing(self):
        """测试多头入场时间记录"""
        with patch('brisk.hft_bb_reversal_strategy.datetime') as mock_datetime:
            # 模拟特定时间
            test_time = datetime(2024, 1, 1, 9, 30, 15)
            mock_datetime.now.return_value = test_time
            
            # 触发多头入场
            self.tick.last_price = 94.0  # 低于下轨
            self.strategy._update_simulated_positions(self.tick)
            
            # 验证持仓状态和时间记录
            positions = self.strategy.simulated_positions["9984"]
            self.assertTrue(positions['long'])
            self.assertFalse(positions['short'])
            self.assertEqual(positions['long_entry_time'], test_time)
            self.assertIsNone(positions['short_entry_time'])
            self.assertIsNone(positions['long_exit_time'])
            self.assertIsNone(positions['short_exit_time'])
            
            # 验证日志
            self.strategy.write_log.assert_called_with(
                f"模拟Long Entry触发: 9984 价格: 94.00 <= 95.00 时间: {test_time.strftime('%H:%M:%S')}"
            )
    
    def test_short_entry_timing(self):
        """测试空头入场时间记录"""
        with patch('brisk.hft_bb_reversal_strategy.datetime') as mock_datetime:
            # 模拟特定时间
            test_time = datetime(2024, 1, 1, 10, 15, 30)
            mock_datetime.now.return_value = test_time
            
            # 触发空头入场
            self.tick.last_price = 106.0  # 高于上轨
            self.strategy._update_simulated_positions(self.tick)
            
            # 验证持仓状态和时间记录
            positions = self.strategy.simulated_positions["9984"]
            self.assertFalse(positions['long'])
            self.assertTrue(positions['short'])
            self.assertIsNone(positions['long_entry_time'])
            self.assertEqual(positions['short_entry_time'], test_time)
            self.assertIsNone(positions['long_exit_time'])
            self.assertIsNone(positions['short_exit_time'])
            
            # 验证日志
            self.strategy.write_log.assert_called_with(
                f"模拟Short Entry触发: 9984 价格: 106.00 >= 105.00 时间: {test_time.strftime('%H:%M:%S')}"
            )
    
    def test_long_exit_timing(self):
        """测试多头出场时间记录和持仓时长计算"""
        with patch('brisk.hft_bb_reversal_strategy.datetime') as mock_datetime:
            # 先设置多头持仓
            entry_time = datetime(2024, 1, 1, 9, 30, 0)
            exit_time = datetime(2024, 1, 1, 9, 35, 15)
            
            # 模拟入场
            mock_datetime.now.return_value = entry_time
            self.tick.last_price = 94.0
            self.strategy._update_simulated_positions(self.tick)
            
            # 模拟出场
            mock_datetime.now.return_value = exit_time
            self.tick.last_price = 101.0  # 高于出场价格
            self.strategy._update_simulated_positions(self.tick)
            
            # 验证持仓状态和时间记录
            positions = self.strategy.simulated_positions["9984"]
            self.assertFalse(positions['long'])
            self.assertFalse(positions['short'])
            self.assertEqual(positions['long_entry_time'], entry_time)
            self.assertEqual(positions['long_exit_time'], exit_time)
            
            # 验证日志包含持仓时长
            expected_duration = exit_time - entry_time
            self.strategy.write_log.assert_any_call(
                f"模拟Long Exit触发: 9984 价格: 101.00 >= 100.00 时间: {exit_time.strftime('%H:%M:%S')} (持仓时长: {expected_duration})"
            )
    
    def test_short_exit_timing(self):
        """测试空头出场时间记录和持仓时长计算"""
        with patch('brisk.hft_bb_reversal_strategy.datetime') as mock_datetime:
            # 先设置空头持仓
            entry_time = datetime(2024, 1, 1, 10, 15, 0)
            exit_time = datetime(2024, 1, 1, 10, 20, 30)
            
            # 模拟入场
            mock_datetime.now.return_value = entry_time
            self.tick.last_price = 106.0
            self.strategy._update_simulated_positions(self.tick)
            
            # 模拟出场
            mock_datetime.now.return_value = exit_time
            self.tick.last_price = 99.0  # 低于出场价格
            self.strategy._update_simulated_positions(self.tick)
            
            # 验证持仓状态和时间记录
            positions = self.strategy.simulated_positions["9984"]
            self.assertFalse(positions['long'])
            self.assertFalse(positions['short'])
            self.assertEqual(positions['short_entry_time'], entry_time)
            self.assertEqual(positions['short_exit_time'], exit_time)
            
            # 验证日志包含持仓时长
            expected_duration = exit_time - entry_time
            self.strategy.write_log.assert_any_call(
                f"模拟Short Exit触发: 9984 价格: 99.00 <= 100.00 时间: {exit_time.strftime('%H:%M:%S')} (持仓时长: {expected_duration})"
            )
    
    def test_multiple_entries_and_exits(self):
        """测试多次入场出场的时间记录"""
        with patch('brisk.hft_bb_reversal_strategy.datetime') as mock_datetime:
            # 第一次多头入场
            long_entry1 = datetime(2024, 1, 1, 9, 30, 0)
            mock_datetime.now.return_value = long_entry1
            self.tick.last_price = 94.0
            self.strategy._update_simulated_positions(self.tick)
            
            # 第一次多头出场
            long_exit1 = datetime(2024, 1, 1, 9, 35, 0)
            mock_datetime.now.return_value = long_exit1
            self.tick.last_price = 101.0
            self.strategy._update_simulated_positions(self.tick)
            
            # 第二次空头入场
            short_entry = datetime(2024, 1, 1, 10, 15, 0)
            mock_datetime.now.return_value = short_entry
            self.tick.last_price = 106.0
            self.strategy._update_simulated_positions(self.tick)
            
            # 第二次空头出场
            short_exit = datetime(2024, 1, 1, 10, 20, 0)
            mock_datetime.now.return_value = short_exit
            self.tick.last_price = 99.0
            self.strategy._update_simulated_positions(self.tick)
            
            # 验证所有时间记录
            positions = self.strategy.simulated_positions["9984"]
            self.assertEqual(positions['long_entry_time'], long_entry1)
            self.assertEqual(positions['long_exit_time'], long_exit1)
            self.assertEqual(positions['short_entry_time'], short_entry)
            self.assertEqual(positions['short_exit_time'], short_exit)
            
            # 验证最终状态
            self.assertFalse(positions['long'])
            self.assertFalse(positions['short'])
    
    def test_data_structure_initialization(self):
        """测试数据结构初始化"""
        # 确保初始状态正确
        self.assertEqual(len(self.strategy.simulated_positions), 0)
        
        # 触发第一次更新
        self.tick.last_price = 94.0
        self.strategy._update_simulated_positions(self.tick)
        
        # 验证数据结构
        positions = self.strategy.simulated_positions["9984"]
        expected_keys = {'long', 'short', 'long_entry_time', 'short_entry_time', 'long_exit_time', 'short_exit_time'}
        self.assertEqual(set(positions.keys()), expected_keys)
        
        # 验证初始值
        self.assertTrue(positions['long'])
        self.assertFalse(positions['short'])
        self.assertIsNotNone(positions['long_entry_time'])
        self.assertIsNone(positions['short_entry_time'])
        self.assertIsNone(positions['long_exit_time'])
        self.assertIsNone(positions['short_exit_time'])
    
    def test_no_bb_levels_skip_update(self):
        """测试没有BB水平时跳过更新"""
        # 设置没有BB水平
        self.context.bb_levels = None
        
        # 尝试更新
        self.tick.last_price = 94.0
        self.strategy._update_simulated_positions(self.tick)
        
        # 验证没有创建持仓记录
        self.assertEqual(len(self.strategy.simulated_positions), 0)
        self.strategy.write_log.assert_not_called()


if __name__ == '__main__':
    unittest.main()
