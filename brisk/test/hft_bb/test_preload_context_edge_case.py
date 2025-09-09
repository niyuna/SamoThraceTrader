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


class TestPreloadContextEdgeCase(unittest.TestCase):
    """测试preload_historical_data中context创建时机的问题"""
    
    def setUp(self):
        """设置测试环境"""
        self.strategy = HFTBBReversalStrategy(use_real_data=True, data_dir="test_data")
        self.strategy.write_log = Mock()
        
        # 设置数据提供者
        self.strategy.data_provider = Mock()
        self.strategy.data_provider.get_historical_bars.return_value = [Mock()] * 25  # 足够的数据
        
        # 设置BB levels
        self.bb_levels = {
            'std': 0.8,
            'middle': 1000.0,
            'upper': 1003.0,
            'lower': 997.0,
            'exit_long': 1001.0,
            'exit_short': 999.0
        }
        
    def test_preload_historical_data_creates_context_when_missing(self):
        """测试preload_historical_data在context不存在时自动创建"""
        symbol = "9984"
        
        # 确保context不存在
        self.assertNotIn(symbol, self.strategy.hft_contexts)
        
        # Mock indicator manager
        mock_indicator = Mock()
        mock_indicator.is_ready_for_trading.return_value = True
        mock_indicator.get_bb_levels.return_value = self.bb_levels
        mock_indicator.preload_historical_bars = Mock()
        
        self.strategy.indicator_managers[symbol] = mock_indicator
        
        # 调用preload_historical_data
        self.strategy.preload_historical_data([symbol], "20250101")
        
        # 验证context被创建
        self.assertIn(symbol, self.strategy.hft_contexts)
        context = self.strategy.hft_contexts[symbol]
        self.assertEqual(context.symbol, symbol)
        
        # 验证BB levels被存储到context中
        self.assertEqual(context.bb_levels, self.bb_levels)
        
    def test_preload_historical_data_uses_existing_context(self):
        """测试preload_historical_data使用已存在的context"""
        symbol = "9984"
        
        # 预先创建context
        self.strategy.create_hft_context(symbol)
        original_context = self.strategy.hft_contexts[symbol]
        
        # Mock indicator manager
        mock_indicator = Mock()
        mock_indicator.is_ready_for_trading.return_value = True
        mock_indicator.get_bb_levels.return_value = self.bb_levels
        mock_indicator.preload_historical_bars = Mock()
        
        self.strategy.indicator_managers[symbol] = mock_indicator
        
        # 调用preload_historical_data
        self.strategy.preload_historical_data([symbol], "20250101")
        
        # 验证使用的是同一个context对象
        self.assertIs(self.strategy.hft_contexts[symbol], original_context)
        
        # 验证BB levels被存储到context中
        self.assertEqual(original_context.bb_levels, self.bb_levels)
        
    def test_preload_historical_data_no_bb_levels_no_context_creation(self):
        """测试当没有BB levels时不创建context"""
        symbol = "9984"
        
        # 确保context不存在
        self.assertNotIn(symbol, self.strategy.hft_contexts)
        
        # Mock indicator manager返回None
        mock_indicator = Mock()
        mock_indicator.is_ready_for_trading.return_value = True
        mock_indicator.get_bb_levels.return_value = None
        mock_indicator.preload_historical_bars = Mock()
        
        self.strategy.indicator_managers[symbol] = mock_indicator
        
        # 调用preload_historical_data
        self.strategy.preload_historical_data([symbol], "20250101")
        
        # 验证context没有被创建
        self.assertNotIn(symbol, self.strategy.hft_contexts)
        
    def test_preload_historical_data_not_ready_no_context_creation(self):
        """测试当指标管理器未准备就绪时不创建context"""
        symbol = "9984"
        
        # 确保context不存在
        self.assertNotIn(symbol, self.strategy.hft_contexts)
        
        # Mock indicator manager未准备就绪
        mock_indicator = Mock()
        mock_indicator.is_ready_for_trading.return_value = False
        mock_indicator.preload_historical_bars = Mock()
        
        self.strategy.indicator_managers[symbol] = mock_indicator
        
        # 调用preload_historical_data
        self.strategy.preload_historical_data([symbol], "20250101")
        
        # 验证context没有被创建
        self.assertNotIn(symbol, self.strategy.hft_contexts)
        
    def test_preload_historical_data_insufficient_data_no_context_creation(self):
        """测试当数据不足时不创建context"""
        symbol = "9984"
        
        # 确保context不存在
        self.assertNotIn(symbol, self.strategy.hft_contexts)
        
        # 设置数据提供者返回不足的数据
        self.strategy.data_provider.get_historical_bars.return_value = [Mock()] * 10  # 不足的数据
        
        # 调用preload_historical_data
        self.strategy.preload_historical_data([symbol], "20250101")
        
        # 验证context没有被创建
        self.assertNotIn(symbol, self.strategy.hft_contexts)
        
    def test_preload_historical_data_multiple_symbols_mixed_context_creation(self):
        """测试多个股票时部分创建context的情况"""
        symbols = ["9984", "6098", "7203"]
        
        # 预先为9984创建context
        self.strategy.create_hft_context("9984")
        
        # 设置数据提供者
        self.strategy.data_provider.get_historical_bars.return_value = [Mock()] * 25
        
        # Mock indicator managers
        for symbol in symbols:
            mock_indicator = Mock()
            if symbol == "9984":
                # 9984准备就绪且有BB levels
                mock_indicator.is_ready_for_trading.return_value = True
                mock_indicator.get_bb_levels.return_value = self.bb_levels
            elif symbol == "6098":
                # 6098准备就绪但没有BB levels
                mock_indicator.is_ready_for_trading.return_value = True
                mock_indicator.get_bb_levels.return_value = None
            else:
                # 7203未准备就绪
                mock_indicator.is_ready_for_trading.return_value = False
                mock_indicator.get_bb_levels.return_value = self.bb_levels
            
            mock_indicator.preload_historical_bars = Mock()
            self.strategy.indicator_managers[symbol] = mock_indicator
        
        # 调用preload_historical_data
        self.strategy.preload_historical_data(symbols, "20250101")
        
        # 验证只有9984有context（预先创建的）
        self.assertIn("9984", self.strategy.hft_contexts)
        self.assertNotIn("6098", self.strategy.hft_contexts)
        self.assertNotIn("7203", self.strategy.hft_contexts)
        
        # 验证9984的BB levels被更新
        context_9984 = self.strategy.hft_contexts["9984"]
        self.assertEqual(context_9984.bb_levels, self.bb_levels)


if __name__ == '__main__':
    unittest.main()
