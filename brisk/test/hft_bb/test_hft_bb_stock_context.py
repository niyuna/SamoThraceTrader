"""
测试HFTBBStockContext数据结构
"""

import unittest
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from hft_bb_reversal_strategy import HFTBBStockContext, TriggerLevels
from intraday_strategy_base import StrategyState


class TestHFTBBStockContext(unittest.TestCase):
    """测试HFTBBStockContext数据结构"""
    
    def test_hft_bb_stock_context_creation(self):
        """测试HFTBBStockContext创建"""
        context = HFTBBStockContext(symbol="2330")
        
        self.assertEqual(context.symbol, "2330")
        self.assertEqual(context.state, StrategyState.IDLE)
        self.assertEqual(context.entry_order_id, "")
        self.assertEqual(context.exit_order_id, "")
        self.assertEqual(context.position, 0)
        self.assertIsNone(context.trigger_levels)
        self.assertFalse(context.can_trade)
        self.assertIsNone(context.bb_levels)
        self.assertEqual(context.entry_order_price, 0.0)
        self.assertEqual(context.exit_order_price, 0.0)
    
    def test_hft_bb_stock_context_with_trigger_levels(self):
        """测试HFTBBStockContext与TriggerLevels结合使用"""
        trigger_levels = TriggerLevels(
            upper_trigger=100.0,
            upper_limit=101.0,
            lower_trigger=99.0,
            lower_limit=98.0
        )
        
        context = HFTBBStockContext(
            symbol="2330",
            trigger_levels=trigger_levels,
            can_trade=True,
            bb_levels={'upper': 100.0, 'lower': 99.0, 'middle': 99.5}
        )
        
        self.assertEqual(context.symbol, "2330")
        self.assertEqual(context.trigger_levels, trigger_levels)
        self.assertTrue(context.can_trade)
        self.assertEqual(context.bb_levels['upper'], 100.0)
        self.assertEqual(context.bb_levels['lower'], 99.0)
        self.assertEqual(context.bb_levels['middle'], 99.5)
    
    def test_hft_bb_stock_context_state_transition(self):
        """测试HFTBBStockContext状态转换"""
        context = HFTBBStockContext(symbol="2330")
        
        # 初始状态
        self.assertEqual(context.state, StrategyState.IDLE)
        
        # 模拟状态转换
        context.state = StrategyState.WAITING_ENTRY
        self.assertEqual(context.state, StrategyState.WAITING_ENTRY)
        
        context.state = StrategyState.HOLDING
        self.assertEqual(context.state, StrategyState.HOLDING)
        
        context.state = StrategyState.WAITING_EXIT
        self.assertEqual(context.state, StrategyState.WAITING_EXIT)
        
        context.state = StrategyState.IDLE
        self.assertEqual(context.state, StrategyState.IDLE)


if __name__ == '__main__':
    unittest.main()
