"""
测试触发价格计算方法
"""

import unittest
import sys
import os
from unittest.mock import Mock

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from hft_bb_reversal_strategy import HFTBBReversalStrategy, TriggerLevels


class TestTriggerCalculation(unittest.TestCase):
    """测试触发价格计算方法"""
    
    def setUp(self):
        """设置测试环境"""
        self.strategy = HFTBBReversalStrategy(use_mock_gateway=True)
        # Mock write_log方法
        self.strategy.write_log = Mock()
    
    def test_calculate_trigger_levels_success(self):
        """测试成功计算触发价格水平"""
        bb_levels = {
            'upper': 100.0,
            'lower': 99.0,
            'middle': 99.5
        }
        
        result = self.strategy._calculate_trigger_levels("9984", bb_levels)
        
        self.assertIsNotNone(result)
        self.assertIsInstance(result, TriggerLevels)
        
        # 验证计算结果（使用tick调整）
        # upper_limit和lower_limit直接使用BB价格
        self.assertEqual(result.upper_limit, 100.0)
        self.assertEqual(result.lower_limit, 99.0)
        
        # trigger价格被tick调整
        self.assertNotEqual(result.upper_trigger, 100.1)  # 应该被调整
        self.assertNotEqual(result.lower_trigger, 99.0)   # 应该被调整
        
        # 验证调整方向正确
        self.assertLess(result.upper_trigger, 100.1)  # upper_trigger应该小于upper_bb
        self.assertGreater(result.lower_trigger, 99.0)  # lower_trigger应该大于lower_bb
    
    def test_calculate_trigger_levels_missing_upper(self):
        """测试缺少上轨数据的情况"""
        bb_levels = {
            'lower': 99.0,
            'middle': 99.5
        }
        
        result = self.strategy._calculate_trigger_levels("9984", bb_levels)
        
        self.assertIsNone(result)
        self.strategy.write_log.assert_called_with("布林带数据不完整: {'lower': 99.0, 'middle': 99.5}")
    
    def test_calculate_trigger_levels_missing_lower(self):
        """测试缺少下轨数据的情况"""
        bb_levels = {
            'upper': 100.0,
            'middle': 99.5
        }
        
        result = self.strategy._calculate_trigger_levels("9984", bb_levels)
        
        self.assertIsNone(result)
        self.strategy.write_log.assert_called_with("布林带数据不完整: {'upper': 100.0, 'middle': 99.5}")
    
    def test_calculate_trigger_levels_missing_middle(self):
        """测试缺少中轨数据的情况"""
        bb_levels = {
            'upper': 100.0,
            'lower': 99.0
        }
        
        result = self.strategy._calculate_trigger_levels("9984", bb_levels)
        
        self.assertIsNone(result)
        self.strategy.write_log.assert_called_with("布林带数据不完整: {'upper': 100.0, 'lower': 99.0}")
    
    def test_calculate_trigger_levels_empty_dict(self):
        """测试空字典的情况"""
        bb_levels = {}
        
        result = self.strategy._calculate_trigger_levels("9984", bb_levels)
        
        self.assertIsNone(result)
        self.strategy.write_log.assert_called_with("布林带数据不完整: {}")
    
    def test_calculate_trigger_levels_none_values(self):
        """测试包含None值的情况"""
        bb_levels = {
            'upper': None,
            'lower': 99.0,
            'middle': 99.5
        }
        
        result = self.strategy._calculate_trigger_levels("9984", bb_levels)
        
        self.assertIsNone(result)
        self.strategy.write_log.assert_called_with("布林带数据不完整: {'upper': None, 'lower': 99.0, 'middle': 99.5}")
    
    def test_calculate_trigger_levels_zero_values(self):
        """测试包含零值的情况"""
        bb_levels = {
            'upper': 0.0,
            'lower': 0.0,
            'middle': 0.0
        }
        
        result = self.strategy._calculate_trigger_levels("9984", bb_levels)
        
        self.assertIsNotNone(result)
        # upper_limit和lower_limit直接使用BB价格
        self.assertEqual(result.upper_limit, 0.0)
        self.assertEqual(result.lower_limit, 0.0)
        
        # trigger价格被tick调整（即使是零值也会被调整）
        self.assertNotEqual(result.upper_trigger, 0.0)  # 应该被调整
        self.assertNotEqual(result.lower_trigger, 0.0)  # 应该被调整


if __name__ == '__main__':
    unittest.main()
