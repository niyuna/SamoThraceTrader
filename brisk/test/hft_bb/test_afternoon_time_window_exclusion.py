"""
下午时间窗口排除15:00分钟测试
"""

import unittest
import sys
import os
from datetime import datetime, time
from unittest.mock import patch, Mock

# 添加路径以导入模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from hft_bb_reversal_strategy import HFTBBReversalStrategy
from intraday_strategy_base import StrategyState


class TestAfternoonTimeWindowExclusion(unittest.TestCase):
    """测试下午时间窗口排除15:00分钟功能"""
    
    def setUp(self):
        """设置测试环境"""
        self.strategy = HFTBBReversalStrategy(use_mock_gateway=True)
        self.strategy.write_log = Mock()
        
        # 覆盖策略参数，使测试独立于默认参数
        self.strategy.price_limit_morning = 5000    # 提高morning时段价格限制
        self.strategy.price_limit_noon = 5000       # 提高noon时段价格限制  
        self.strategy.price_limit_afternoon = 5000  # 提高afternoon时段价格限制
        self.strategy.max_price_change_pct = 20.0   # 提高价格变动限制
        
        # 创建测试用的 context
        self.symbol = "9984"
        self.strategy.create_hft_context(self.symbol)
        context = self.strategy.get_hft_context(self.symbol)
        
        # 设置 BB levels 用于测试
        context.bb_levels = {
            'upper': 100.5,
            'lower': 99.5,
            'middle': 100.0,
            'std': 0.2
        }
        
        # 添加股票到 eligible_stocks
        self.strategy.eligible_stocks.add(self.symbol)
    
    def test_15_00_exact_time_excluded(self):
        """测试15:00:00被排除"""
        test_time = time(15, 0, 0)
        
        with patch('hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime.combine(datetime.now().date(), test_time)
            
            result = self.strategy.check_x_condition(self.symbol)
            self.assertFalse(result)
    
    def test_15_00_30_excluded(self):
        """测试15:00:30被排除"""
        test_time = time(15, 0, 30)
        
        with patch('hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime.combine(datetime.now().date(), test_time)
            
            result = self.strategy.check_x_condition(self.symbol)
            self.assertFalse(result)
    
    def test_15_00_59_excluded(self):
        """测试15:00:59被排除"""
        test_time = time(15, 0, 59)
        
        with patch('hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime.combine(datetime.now().date(), test_time)
            
            result = self.strategy.check_x_condition(self.symbol)
            self.assertFalse(result)
    
    def test_15_01_allowed(self):
        """测试15:01:00被允许"""
        test_time = time(15, 1, 0)
        
        with patch('hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime.combine(datetime.now().date(), test_time)
            
            result = self.strategy.check_x_condition(self.symbol)
            self.assertTrue(result)
    
    def test_14_59_allowed(self):
        """测试14:59:59被允许"""
        test_time = time(14, 59, 59)
        
        with patch('hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime.combine(datetime.now().date(), test_time)
            
            result = self.strategy.check_x_condition(self.symbol)
            self.assertTrue(result)
    
    def test_15_25_allowed(self):
        """测试15:25:00被排除（超出时间窗口）"""
        test_time = time(15, 25, 0)
        
        with patch('hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime.combine(datetime.now().date(), test_time)
            
            result = self.strategy.check_x_condition(self.symbol)
            self.assertFalse(result)
    
    def test_15_26_excluded(self):
        """测试15:26:00被排除（超出时间窗口）"""
        test_time = time(15, 26, 0)
        
        with patch('hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime.combine(datetime.now().date(), test_time)
            
            result = self.strategy.check_x_condition(self.symbol)
            self.assertFalse(result)
    
    def test_morning_window_not_affected(self):
        """测试早上时间窗口不受影响"""
        test_time = time(9, 20, 0)  # 早上时间
        
        with patch('hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime.combine(datetime.now().date(), test_time)
            
            result = self.strategy.check_x_condition(self.symbol)
            self.assertTrue(result)
    
    def test_noon_window_not_affected(self):
        """测试中午时间窗口不受影响"""
        test_time = time(11, 29, 30)  # 中午时间
        
        with patch('hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime.combine(datetime.now().date(), test_time)
            
            result = self.strategy.check_x_condition(self.symbol)
            self.assertTrue(result)


if __name__ == '__main__':
    unittest.main()
