#!/usr/bin/env python3
"""
测试_execute_entry_with_direction和_execute_exit_with_direction方法的新实现
"""

import unittest
import sys
import os
from unittest.mock import Mock, patch

# 添加上级目录到Python路径，以便导入模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from intraday_strategy_base import IntradayStrategyBase, StrategyState, StockContext
from vnpy.trader.constant import Direction


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


class TestExecuteMethods(unittest.TestCase):
    """测试执行方法"""
    
    def setUp(self):
        """测试前准备"""
        self.strategy = MockStrategy()
        
        # 创建测试context
        self.context = StockContext(symbol="7203")
        self.strategy.contexts["7203"] = self.context
        
        # 模拟bar数据
        from vnpy.trader.object import BarData
        from vnpy.trader.constant import Exchange
        self.mock_bar = BarData(
            symbol="7203",
            exchange=Exchange.TSE,
            datetime=None,
            interval=None,
            volume=0,
            turnover=0,
            open_price=100.0,
            high_price=100.0,
            low_price=100.0,
            close_price=100.0,
            gateway_name="TEST"
        )
    
    def test_execute_entry_with_direction_short(self):
        """测试做空entry执行"""
        # Mock _execute_entry方法
        with patch.object(self.strategy, '_execute_entry') as mock_execute_entry:
            self.strategy._execute_entry_with_direction(self.context, self.mock_bar, 100.0)
            
            # 验证调用了_execute_entry，方向为SHORT
            mock_execute_entry.assert_called_once_with(self.context, self.mock_bar, 100.0, Direction.SHORT)
    
    def test_execute_entry_with_direction_long(self):
        """测试做多entry执行"""
        # 创建做多的context
        long_context = StockContext(symbol="6758")
        self.strategy.contexts["6758"] = long_context
        
        with patch.object(self.strategy, '_execute_entry') as mock_execute_entry:
            self.strategy._execute_entry_with_direction(long_context, self.mock_bar, 100.0)
            
            # 验证调用了_execute_entry，方向为LONG
            mock_execute_entry.assert_called_once_with(long_context, self.mock_bar, 100.0, Direction.LONG)
    
    def test_execute_entry_with_direction_none(self):
        """测试无方向entry执行"""
        # 创建无方向的context
        none_context = StockContext(symbol="9999")
        self.strategy.contexts["9999"] = none_context
        
        with patch.object(self.strategy, '_execute_entry') as mock_execute_entry:
            self.strategy._execute_entry_with_direction(none_context, self.mock_bar, 100.0)
            
            # 验证没有调用_execute_entry
            mock_execute_entry.assert_not_called()
    
    def test_execute_exit_with_direction_short(self):
        """测试做空exit执行（平仓需要买入）"""
        with patch.object(self.strategy, '_execute_exit') as mock_execute_exit:
            self.strategy._execute_exit_with_direction(self.context, self.mock_bar, 100.0)
            
            # 验证调用了_execute_exit，方向为LONG（买入平仓）
            mock_execute_exit.assert_called_once_with(self.context, self.mock_bar, 100.0, Direction.LONG)
    
    def test_execute_exit_with_direction_long(self):
        """测试做多exit执行（平仓需要卖出）"""
        # 创建做多的context
        long_context = StockContext(symbol="6758")
        self.strategy.contexts["6758"] = long_context
        
        with patch.object(self.strategy, '_execute_exit') as mock_execute_exit:
            self.strategy._execute_exit_with_direction(long_context, self.mock_bar, 100.0)
            
            # 验证调用了_execute_exit，方向为SHORT（卖出平仓）
            mock_execute_exit.assert_called_once_with(long_context, self.mock_bar, 100.0, Direction.SHORT)
    
    def test_execute_exit_with_direction_none(self):
        """测试无方向exit执行"""
        # 创建无方向的context
        none_context = StockContext(symbol="9999")
        self.strategy.contexts["9999"] = none_context
        
        with patch.object(self.strategy, '_execute_exit') as mock_execute_exit:
            self.strategy._execute_exit_with_direction(none_context, self.mock_bar, 100.0)
            
            # 验证没有调用_execute_exit
            mock_execute_exit.assert_not_called()


if __name__ == "__main__":
    unittest.main() 