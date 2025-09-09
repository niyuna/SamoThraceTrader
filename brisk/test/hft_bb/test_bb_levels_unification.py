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
from vnpy.trader.object import TickData, BarData


class TestBBLevelsUnification(unittest.TestCase):
    """测试BB levels数据结构的统一化"""
    
    def setUp(self):
        """设置测试环境"""
        self.strategy = HFTBBReversalStrategy()
        self.strategy.write_log = Mock()
        
        # 添加测试股票
        self.strategy.add_symbol("9984")
        self.context = self.strategy.get_hft_context("9984")
        
        # 设置BB levels
        self.bb_levels = {
            'std': 0.8,
            'middle': 1000.0,
            'upper': 1003.0,
            'lower': 997.0,
            'exit_long': 1001.0,
            'exit_short': 999.0
        }
        
    def test_no_self_bb_levels_attribute(self):
        """测试策略不再有self.bb_levels属性"""
        # 验证self.bb_levels不存在
        self.assertFalse(hasattr(self.strategy, 'bb_levels'))
        
    def test_context_bb_levels_storage(self):
        """测试BB levels存储在context中"""
        # 设置BB levels到context
        self.context.bb_levels = self.bb_levels
        
        # 验证存储成功
        self.assertEqual(self.context.bb_levels, self.bb_levels)
        self.assertIsNotNone(self.context.bb_levels)
        
    def test_simulated_positions_uses_context_bb_levels(self):
        """测试模拟持仓使用context中的BB levels"""
        # 设置context中的BB levels
        self.context.bb_levels = self.bb_levels
        
        # 创建tick数据
        tick = TickData(
            symbol="9984",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            name="测试股票",
            last_price=996.0,  # 低于lower，应该触发long entry
            volume=100,
            turnover=100000.0,
            open_interest=0.0,
            bid_price_1=995.5,
            bid_volume_1=100,
            ask_price_1=996.5,
            ask_volume_1=100,
            gateway_name="test"
        )
        
        # 调用模拟持仓更新
        self.strategy._update_simulated_positions(tick)
        
        # 验证模拟持仓被正确设置
        self.assertTrue(self.strategy.simulated_positions["9984"]['long'])
        self.assertFalse(self.strategy.simulated_positions["9984"]['short'])
        
    def test_simulated_positions_no_bb_levels(self):
        """测试没有BB levels时模拟持仓不更新"""
        # 确保context中没有BB levels
        self.context.bb_levels = None
        
        # 创建tick数据
        tick = TickData(
            symbol="9984",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            name="测试股票",
            last_price=996.0,
            volume=100,
            turnover=100000.0,
            open_interest=0.0,
            bid_price_1=995.5,
            bid_volume_1=100,
            ask_price_1=996.5,
            ask_volume_1=100,
            gateway_name="test"
        )
        
        # 调用模拟持仓更新
        self.strategy._update_simulated_positions(tick)
        
        # 验证模拟持仓没有被设置（因为BB levels为None）
        self.assertNotIn("9984", self.strategy.simulated_positions)
        
    def test_strategy_status_uses_context_bb_levels(self):
        """测试策略状态显示使用context中的BB levels"""
        # 设置context中的BB levels
        self.context.bb_levels = self.bb_levels
        
        # 设置模拟持仓
        self.strategy.simulated_positions["9984"] = {'long': True, 'short': False}
        
        # Mock print函数来捕获输出
        with patch('builtins.print') as mock_print:
            self.strategy.print_simulation_summary()
            
            # 验证输出包含BB信息
            print_calls = [call[0][0] for call in mock_print.call_args_list]
            bb_output = next((call for call in print_calls if 'BB:' in call), None)
            self.assertIsNotNone(bb_output)
            self.assertIn('U=1003.00', bb_output)
            self.assertIn('L=997.00', bb_output)
            self.assertIn('M=1000.00', bb_output)
            
    def test_strategy_status_no_bb_levels(self):
        """测试没有BB levels时策略状态不显示BB信息"""
        # 确保context中没有BB levels
        self.context.bb_levels = None
        
        # 设置模拟持仓
        self.strategy.simulated_positions["9984"] = {'long': True, 'short': False}
        
        # Mock print函数来捕获输出
        with patch('builtins.print') as mock_print:
            self.strategy.print_simulation_summary()
            
            # 验证输出不包含BB信息
            print_calls = [call[0][0] for call in mock_print.call_args_list]
            bb_output = next((call for call in print_calls if 'BB:' in call), None)
            self.assertIsNone(bb_output)
            
    def test_preload_historical_data_stores_to_context(self):
        """测试预加载历史数据时存储到context中"""
        # 启用真实数据模式
        self.strategy.use_real_data = True
        self.strategy.data_provider = Mock()
        self.strategy.data_provider.get_historical_bars.return_value = [Mock()] * 25  # 足够的数据
        
        # Mock indicator manager
        mock_indicator = Mock()
        mock_indicator.is_ready_for_trading.return_value = True
        mock_indicator.get_bb_levels.return_value = self.bb_levels
        mock_indicator.preload_historical_bars = Mock()
        
        self.strategy.indicator_managers["9984"] = mock_indicator
        
        # 调用预加载
        self.strategy.preload_historical_data(["9984"], "20250101")
        
        # 验证BB levels存储到context中
        self.assertEqual(self.context.bb_levels, self.bb_levels)
        
    def test_bb_levels_consistency_across_methods(self):
        """测试BB levels在不同方法间的一致性"""
        # 设置BB levels到context
        self.context.bb_levels = self.bb_levels
        
        # 测试模拟持仓
        tick = TickData(
            symbol="9984",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            name="测试股票",
            last_price=996.0,
            volume=100,
            turnover=100000.0,
            open_interest=0.0,
            bid_price_1=995.5,
            bid_volume_1=100,
            ask_price_1=996.5,
            ask_volume_1=100,
            gateway_name="test"
        )
        
        self.strategy._update_simulated_positions(tick)
        
        # 测试策略状态
        with patch('builtins.print') as mock_print:
            self.strategy.print_simulation_summary()
            
        # 验证所有方法都使用相同的BB levels数据
        self.assertEqual(self.context.bb_levels, self.bb_levels)
        
    def test_bb_levels_update_in_on_1min_bar(self):
        """测试在on_1min_bar中更新BB levels"""
        # Mock bar数据
        bar = BarData(
            symbol="9984",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            interval="1m",
            volume=1000,
            turnover=1000000.0,
            open_interest=0.0,
            open_price=1000.0,
            high_price=1002.0,
            low_price=998.0,
            close_price=1001.0,
            gateway_name="test"
        )
        
        # Mock indicator manager
        mock_indicator = Mock()
        mock_indicator.update_bar.return_value = {'bb_levels': self.bb_levels}
        mock_indicator.get_indicators.return_value = self.bb_levels
        self.strategy.indicator_managers["9984"] = mock_indicator
        
        # 调用on_1min_bar
        self.strategy.on_1min_bar(bar)
        
        # 验证BB levels被更新到context中
        self.assertEqual(self.context.bb_levels, self.bb_levels)
        
    def test_bb_levels_used_in_std_pct_calculation(self):
        """测试std_pct计算使用context中的BB levels"""
        # 设置BB levels到context
        self.context.bb_levels = self.bb_levels
        
        # 调用std_pct计算
        result = self.strategy._calculate_and_check_std_pct("9984", 0.0005)
        
        # 验证计算正确
        expected_std_pct = 0.8 / 1000.0  # std / middle
        self.assertEqual(result['std_pct'], expected_std_pct)
        self.assertTrue(result['ok'])  # 0.0008 > 0.0005
        
    def test_bb_levels_used_in_exit_order_management(self):
        """测试exit订单管理使用context中的BB levels"""
        # 设置BB levels到context
        self.context.bb_levels = self.bb_levels
        
        # 设置持仓
        self.context.position = 100  # 多头持仓
        
        # Mock _execute_exit方法
        with patch.object(self.strategy, '_execute_exit') as mock_execute:
            mock_execute.return_value = "test_exit_order_123"
            self.strategy._manage_exit_order("9984", self.bb_levels)
            
            # 验证调用了_execute_exit
            mock_execute.assert_called_once()
            
            # 验证参数正确
            call_args = mock_execute.call_args
            self.assertEqual(call_args[0][2], 1001.0)  # exit_long价格
            self.assertEqual(call_args[0][3], Direction.SHORT)  # 平仓方向


if __name__ == '__main__':
    unittest.main()
