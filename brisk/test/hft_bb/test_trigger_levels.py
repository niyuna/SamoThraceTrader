"""
测试TriggerLevels数据结构
"""

import unittest
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hft_bb_reversal_strategy import TriggerLevels


class TestTriggerLevels(unittest.TestCase):
    """测试TriggerLevels数据结构"""
    
    def test_trigger_levels_creation(self):
        """测试TriggerLevels创建"""
        trigger_levels = TriggerLevels(
            upper_trigger=100.0,
            upper_limit=101.0,
            lower_trigger=99.0,
            lower_limit=98.0
        )
        
        self.assertEqual(trigger_levels.upper_trigger, 100.0)
        self.assertEqual(trigger_levels.upper_limit, 101.0)
        self.assertEqual(trigger_levels.lower_trigger, 99.0)
        self.assertEqual(trigger_levels.lower_limit, 98.0)
    
    def test_trigger_levels_equality(self):
        """测试TriggerLevels相等性"""
        trigger_levels1 = TriggerLevels(
            upper_trigger=100.0,
            upper_limit=101.0,
            lower_trigger=99.0,
            lower_limit=98.0
        )
        
        trigger_levels2 = TriggerLevels(
            upper_trigger=100.0,
            upper_limit=101.0,
            lower_trigger=99.0,
            lower_limit=98.0
        )
        
        self.assertEqual(trigger_levels1, trigger_levels2)
    
    def test_trigger_levels_inequality(self):
        """测试TriggerLevels不相等性"""
        trigger_levels1 = TriggerLevels(
            upper_trigger=100.0,
            upper_limit=101.0,
            lower_trigger=99.0,
            lower_limit=98.0
        )
        
        trigger_levels2 = TriggerLevels(
            upper_trigger=100.1,  # 不同的值
            upper_limit=101.0,
            lower_trigger=99.0,
            lower_limit=98.0
        )
        
        self.assertNotEqual(trigger_levels1, trigger_levels2)


if __name__ == '__main__':
    unittest.main()
