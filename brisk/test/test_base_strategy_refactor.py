#!/usr/bin/env python3
"""
测试Base Strategy重构后的功能
"""

import unittest
import sys
import os
from unittest.mock import Mock, patch
from datetime import datetime

# 添加上级目录到Python路径，以便导入模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from intraday_strategy_base import IntradayStrategyBase, StrategyState, StockContext


class MockStrategy(IntradayStrategyBase):
    """模拟策略类，用于测试"""
    
    def get_entry_direction(self, symbol: str) -> str:
        """模拟实现entry方向判断"""
        if symbol == "7203":
            return "short"  # 做空
        elif symbol == "6758":
            return "long"   # 做多
        else:
            return "none"   # 不交易
    
    def _calculate_entry_price(self, context, bar, indicators) -> float:
        """模拟实现entry价格计算"""
        return 100.0
    
    def _calculate_exit_price(self, context, bar, indicators) -> float:
        """模拟实现exit价格计算"""
        return 101.0
    
    def _execute_entry_with_direction(self, context, bar, price):
        """模拟实现entry订单执行"""
        pass
    
    def _execute_exit_with_direction(self, context, bar, price):
        """模拟实现exit订单执行"""
        pass


class TestBaseStrategyRefactor(unittest.TestCase):
    """测试Base Strategy重构"""
    
    def setUp(self):
        """测试前准备"""
        self.strategy = MockStrategy()
        self.strategy.enable_delayed_entry = True
        self.strategy.delayed_entry_atr_multiplier = 2.0
        
        # 创建测试context
        self.context = StockContext(symbol="7203")
        self.strategy.contexts["7203"] = self.context
        
        # 模拟技术指标
        self.indicators = {
            'atr_14': 10.0,
            'volume_ma5': 1000,
            'vwap': 100.0
        }
    
    def test_get_entry_direction(self):
        """测试entry方向获取"""
        # 测试做空
        direction = self.strategy.get_entry_direction("7203")
        self.assertEqual(direction, "short")
        
        # 测试做多
        direction = self.strategy.get_entry_direction("6758")
        self.assertEqual(direction, "long")
        
        # 测试不交易
        direction = self.strategy.get_entry_direction("9999")
        self.assertEqual(direction, "none")
    
    def test_set_trigger_prices_short(self):
        """测试设置做空触发价格"""
        target_price = 100.0
        self.strategy._set_trigger_prices(self.context, None, self.indicators, target_price)
        
        # 做空：触发价格 = 目标价格 - atr_multiplier*ATR
        expected_trigger = target_price - (2.0 * 10.0)  # 100 - 20 = 80
        self.assertEqual(self.context.entry_trigger_price, expected_trigger)
        self.assertEqual(self.context.entry_trigger_order_price, target_price)
    
    def test_set_trigger_prices_long(self):
        """测试设置做多触发价格"""
        # 创建做多的context
        long_context = StockContext(symbol="6758")
        self.strategy.contexts["6758"] = long_context
        
        target_price = 100.0
        self.strategy._set_trigger_prices(long_context, None, self.indicators, target_price)
        
        # 做多：触发价格 = 目标价格 + atr_multiplier*ATR
        expected_trigger = target_price + (2.0 * 10.0)  # 100 + 20 = 120
        self.assertEqual(long_context.entry_trigger_price, expected_trigger)
        self.assertEqual(long_context.entry_trigger_order_price, target_price)
    
    def test_get_price_movement_direction_short(self):
        """测试做空策略的价格波动方向判断"""
        # 模拟bar数据
        from vnpy.trader.object import BarData
        bar = Mock(spec=BarData)
        bar.open_price = 100.0
        bar.close_price = 95.0  # 价格下跌，对做空有利
        
        direction = self.strategy._get_price_movement_direction(self.context, bar)
        self.assertEqual(direction, "favorable")
        
        # 价格上涨，对做空不利
        bar.close_price = 105.0
        direction = self.strategy._get_price_movement_direction(self.context, bar)
        self.assertEqual(direction, "unfavorable")
    
    def test_get_price_movement_direction_long(self):
        """测试做多策略的价格波动方向判断"""
        # 创建做多的context
        long_context = StockContext(symbol="6758")
        
        # 模拟bar数据
        from vnpy.trader.object import BarData
        bar = Mock(spec=BarData)
        bar.open_price = 100.0
        bar.close_price = 105.0  # 价格上涨，对做多有利
        
        direction = self.strategy._get_price_movement_direction(long_context, bar)
        self.assertEqual(direction, "favorable")
        
        # 价格下跌，对做多不利
        bar.close_price = 95.0
        direction = self.strategy._get_price_movement_direction(long_context, bar)
        self.assertEqual(direction, "unfavorable")
    
    def test_risk_control_atr_threshold(self):
        """测试风险控制ATR阈值计算"""
        # 测试做空时的ATR阈值
        atr = 10.0
        short_threshold = atr * self.strategy.force_exit_atr_factor  # 10 * 1.5 = 15
        
        # 测试做多时的ATR阈值
        long_threshold = atr * self.strategy.force_exit_atr_factor * 10  # 10 * 1.5 * 10 = 150
        
        self.assertEqual(short_threshold, 15.0)
        self.assertEqual(long_threshold, 150.0)


if __name__ == "__main__":
    unittest.main() 