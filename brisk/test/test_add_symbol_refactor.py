#!/usr/bin/env python3
"""
测试add_symbol重构后的功能
"""

import unittest
import sys
import os
from unittest.mock import Mock, patch

# 添加上级目录到Python路径，以便导入模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from intraday_strategy_base import IntradayStrategyBase, StrategyState, StockContext
from vwap_failure_strategy import VWAPFailureStrategy


class TestAddSymbolRefactor(unittest.TestCase):
    """测试add_symbol重构"""
    
    def setUp(self):
        """测试前准备"""
        self.base_strategy = IntradayStrategyBase()
        self.vwap_strategy = VWAPFailureStrategy()
    
    def test_base_strategy_default_config(self):
        """测试base strategy的默认配置"""
        # 检查默认配置
        self.assertEqual(self.base_strategy.bar_window, 5)
        self.assertEqual(self.base_strategy.indicator_size, 15)
        self.assertEqual(self.base_strategy.bar_interval.value, '1m')  # Interval.MINUTE
        self.assertTrue(self.base_strategy.enable_opening_volume)
        self.assertFalse(self.base_strategy.enable_auto_flush)
    
    def test_vwap_strategy_custom_config(self):
        """测试VWAP策略的自定义配置"""
        # 检查VWAP策略的自定义配置
        self.assertEqual(self.vwap_strategy.bar_window, 5)
        self.assertEqual(self.vwap_strategy.indicator_size, 15)
        
        # 其他配置应该继承自base strategy
        self.assertEqual(self.vwap_strategy.bar_interval.value, '1m')
        self.assertTrue(self.vwap_strategy.enable_opening_volume)
        self.assertFalse(self.vwap_strategy.enable_auto_flush)
    
    def test_base_strategy_add_symbol(self):
        """测试base strategy的add_symbol方法"""
        symbol = "7203"
        
        # Mock EnhancedBarGenerator和TechnicalIndicatorManager
        with patch('intraday_strategy_base.EnhancedBarGenerator') as mock_bar_gen_cls, \
             patch('intraday_strategy_base.TechnicalIndicatorManager') as mock_indicator_cls:
            
            mock_bar_gen = Mock()
            mock_indicator = Mock()
            mock_bar_gen_cls.return_value = mock_bar_gen
            mock_indicator_cls.return_value = mock_indicator
            
            # 调用add_symbol
            self.base_strategy.add_symbol(symbol)
            
            # 验证创建了bar generator和indicator manager
            self.assertIn(symbol, self.base_strategy.bar_generators)
            self.assertIn(symbol, self.base_strategy.indicator_managers)
            
            # 验证EnhancedBarGenerator被正确调用
            mock_bar_gen_cls.assert_called_once()
            call_args = mock_bar_gen_cls.call_args
            self.assertEqual(call_args[1]['window'], 5)
            # TechnicalIndicatorManager的size参数在_create_indicator_manager中设置
            
            # 验证TechnicalIndicatorManager被正确调用
            mock_indicator_cls.assert_called_once_with(symbol, size=15)
    
    def test_vwap_strategy_add_symbol(self):
        """测试VWAP策略的add_symbol方法"""
        symbol = "7203"
        
        # Mock EnhancedBarGenerator和TechnicalIndicatorManager
        with patch('intraday_strategy_base.EnhancedBarGenerator') as mock_bar_gen_cls, \
             patch('intraday_strategy_base.TechnicalIndicatorManager') as mock_indicator_cls:
            
            mock_bar_gen = Mock()
            mock_indicator = Mock()
            mock_bar_gen_cls.return_value = mock_bar_gen
            mock_indicator_cls.return_value = mock_indicator
            
            # 调用add_symbol
            self.vwap_strategy.add_symbol(symbol)
            
            # 验证创建了bar generator和indicator manager
            self.assertIn(symbol, self.vwap_strategy.bar_generators)
            self.assertIn(symbol, self.vwap_strategy.indicator_managers)
            
            # 验证EnhancedBarGenerator被正确调用，使用VWAP策略的自定义配置
            mock_bar_gen_cls.assert_called_once()
            call_args = mock_bar_gen_cls.call_args
            self.assertEqual(call_args[1]['window'], 5)  # VWAP策略的配置
            
            # 验证TechnicalIndicatorManager被正确调用
            mock_indicator_cls.assert_called_once_with(symbol, size=15)
    
    def test_subscribe_calls_add_symbol(self):
        """测试subscribe方法会调用add_symbol"""
        symbols = ["7203", "6758"]
        
        # Mock add_symbol方法
        with patch.object(self.base_strategy, 'add_symbol') as mock_add_symbol:
            # Mock main_engine.subscribe
            with patch.object(self.base_strategy, 'main_engine') as mock_main_engine:
                mock_main_engine.subscribe = Mock()
                
                # 调用subscribe
                self.base_strategy.subscribe(symbols)
                
                # 验证add_symbol被调用了两次，每个symbol一次
                self.assertEqual(mock_add_symbol.call_count, 2)
                mock_add_symbol.assert_any_call("7203")
                mock_add_symbol.assert_any_call("6758")


if __name__ == "__main__":
    unittest.main() 