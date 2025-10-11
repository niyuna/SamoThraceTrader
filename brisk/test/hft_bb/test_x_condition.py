"""
测试X条件功能
"""

import unittest
import sys
import os
from datetime import datetime, time
from unittest.mock import patch, Mock

# 添加路径以导入模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from hft_bb_reversal_strategy import HFTBBReversalStrategy
from vnpy.trader.object import BarData
from vnpy.trader.constant import Exchange, Interval, Direction


class TestXCondition(unittest.TestCase):
    """测试X条件功能"""
    
    def setUp(self):
        """测试前的准备工作"""
        self.strategy = HFTBBReversalStrategy(use_mock_gateway=True)
        
        # 覆盖策略参数，使测试独立于默认参数
        self.strategy.price_limit_morning = 5000    # 提高morning时段价格限制
        self.strategy.price_limit_noon = 5000       # 提高noon时段价格限制  
        self.strategy.price_limit_afternoon = 5000  # 提高afternoon时段价格限制
        self.strategy.max_price_change_pct = 20.0   # 提高价格变动限制
        self.strategy.aggressive_x_condition_enabled = True  # 启用激进X条件以测试模拟持仓逻辑
        
    def test_x_condition_time_windows(self):
        """测试X条件时间窗口"""
        print("测试X条件时间窗口")
        
        # 测试早上时间窗口 9:15~9:35
        morning_time = datetime(2025, 1, 1, 9, 20, 0)
        self.assertTrue(self.strategy._check_time_window(morning_time))
        
        # 测试中午时间窗口 11:29~11:30
        noon_time = datetime(2025, 1, 1, 11, 29, 30)
        self.assertTrue(self.strategy._check_time_window(noon_time))
        
        # 测试下午时间窗口 14:35~15:20
        afternoon_time = datetime(2025, 1, 1, 15, 0, 0)
        self.assertTrue(self.strategy._check_time_window(afternoon_time))
        
        # 测试不在时间窗口内的时间
        off_time = datetime(2025, 1, 1, 10, 0, 0)
        self.assertFalse(self.strategy._check_time_window(off_time))
        
        print("✓ 时间窗口测试通过")
        
    def test_x_condition_no_position(self):
        """测试X条件持仓检查"""
        print("测试X条件持仓检查")
        
        symbol = "9984"
        
        # 测试没有持仓的情况
        self.assertTrue(self.strategy._check_no_position(symbol))
        
        # 模拟设置持仓
        self.strategy.simulated_positions[symbol] = {'long': False, 'short': False}
        self.assertTrue(self.strategy._check_no_position(symbol))
        
        # 模拟设置多头持仓
        self.strategy.simulated_positions[symbol] = {'long': True, 'short': False}
        self.assertFalse(self.strategy._check_no_position(symbol))
        
        # 模拟设置空头持仓
        self.strategy.simulated_positions[symbol] = {'long': False, 'short': True}
        self.assertFalse(self.strategy._check_no_position(symbol))
        
        print("✓ 持仓检查测试通过")
        
    def test_x_condition_complete(self):
        """测试完整的X条件检查"""
        print("测试完整的X条件检查")
        
        symbol = "9984"
        
        # 先将股票添加到eligible_stocks中
        self.strategy.eligible_stocks.add(symbol)
        
        # 添加股票到策略并设置BB levels
        self.strategy.add_symbol(symbol)
        context = self.strategy.get_hft_context(symbol)
        context.bb_levels = {
            'std': 0.8,
            'middle': 1000.0,
            'upper': 1003.0,
            'lower': 997.0,
            'exit_long': 1001.0,
            'exit_short': 999.0
        }
        
        # 模拟get_stock_prev_close返回合理价格
        self.strategy.get_stock_prev_close = Mock(return_value=2000.0)
        
        # 测试满足X条件的情况（无模拟持仓）
        morning_time = datetime(2025, 1, 1, 9, 20, 0)
        with patch('hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = morning_time
            result = self.strategy.check_x_condition(symbol)
            self.assertEqual(result, ['long', 'short'])
        
        # 测试不满足时间窗口的情况
        off_time = datetime(2025, 1, 1, 10, 0, 0)
        with patch('hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = off_time
            result = self.strategy.check_x_condition(symbol)
            self.assertEqual(result, [])
        
        # 测试模拟持仓entry时间在窗口内且方向匹配的情况
        self.strategy.simulated_positions[symbol] = {
            'long': True, 
            'short': False,
            'long_entry_time': datetime(2025, 1, 1, 9, 15, 0),  # 在morning窗口内
            'short_entry_time': None,
            'long_exit_time': None,
            'short_exit_time': None
        }
        with patch('hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = morning_time
            result = self.strategy.check_x_condition(symbol)
            self.assertEqual(result, ['long', 'short'])  # 方向匹配，允许交易
        
        # 测试模拟持仓entry时间不在窗口内的情况
        self.strategy.simulated_positions[symbol] = {
            'long': True, 
            'short': False,
            'long_entry_time': datetime(2025, 1, 1, 8, 0, 0),  # 不在任何窗口内
            'short_entry_time': None,
            'long_exit_time': None,
            'short_exit_time': None
        }
        with patch('hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = morning_time
            result = self.strategy.check_x_condition(symbol)
            self.assertEqual(result, [])  # entry时间不在窗口内，不允许交易
        
        print("✓ 完整X条件检查测试通过")
        
        



def run_x_condition_tests():
    """运行X条件测试"""
    print("开始运行X条件测试...")
    print("=" * 50)
    
    # 创建测试套件
    test_suite = unittest.TestSuite()
    test_suite.addTest(unittest.TestLoader().loadTestsFromTestCase(TestXCondition))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    print("=" * 50)
    if result.wasSuccessful():
        print("🎉 所有X条件测试通过！")
    else:
        print(f"❌ 测试失败: {len(result.failures)} 个失败, {len(result.errors)} 个错误")
        
    return result.wasSuccessful()


if __name__ == "__main__":
    run_x_condition_tests()
