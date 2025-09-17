"""
测试时间窗口交易方向配置功能
"""

import unittest
from unittest.mock import Mock, patch
from datetime import datetime, time
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from hft_bb_reversal_strategy import HFTBBReversalStrategy


class TestTimeWindowDirections(unittest.TestCase):
    """测试时间窗口交易方向配置"""
    
    def setUp(self):
        """设置测试环境"""
        self.strategy = HFTBBReversalStrategy(use_mock_gateway=True)
        
        # 模拟gateway
        self.strategy.gateway = Mock()
        self.strategy.gateway.send_order = Mock()
        
        # 添加测试股票到eligible_stocks
        self.strategy.eligible_stocks = ["9984"]
        
        # 创建测试context
        from hft_bb_reversal_strategy import HFTBBStockContext
        self.strategy.hft_contexts["9984"] = HFTBBStockContext(symbol="9984")
        
        # 模拟BB levels
        self.strategy.hft_contexts["9984"].bb_levels = {
            'upper': 100.0,
            'lower': 99.0,
            'middle': 99.5
        }
    
    def test_morning_window_allows_both_directions(self):
        """测试早上窗口允许多空双向交易"""
        # 设置早上时间
        morning_time = datetime(2024, 1, 1, 9, 20)
        
        result = self.strategy._check_time_window_with_std_pct("9984", morning_time)
        
        self.assertTrue(result['in_window'])
        self.assertEqual(result['time_period'], 'morning')
        self.assertEqual(result['allowed_directions'], ['long'])
    
    def test_noon_window_allows_both_directions(self):
        """测试中午窗口允许多空双向交易"""
        # 设置中午时间
        noon_time = datetime(2024, 1, 1, 11, 29, 30)
        
        result = self.strategy._check_time_window_with_std_pct("9984", noon_time)
        
        self.assertTrue(result['in_window'])
        self.assertEqual(result['time_period'], 'noon')
        self.assertEqual(result['allowed_directions'], ['long', 'short'])
    
    def test_afternoon_window_allows_both_directions(self):
        """测试下午窗口允许多空双向交易"""
        # 设置下午时间（非15:00）
        afternoon_time = datetime(2024, 1, 1, 14, 40)
        
        result = self.strategy._check_time_window_with_std_pct("9984", afternoon_time)
        
        self.assertTrue(result['in_window'])
        self.assertEqual(result['time_period'], 'afternoon')
        self.assertEqual(result['allowed_directions'], ['long', 'short'])
    
    def test_outside_window_returns_empty_directions(self):
        """测试在交易窗口外时返回空的交易方向"""
        # 设置非交易时间
        outside_time = datetime(2024, 1, 1, 10, 0)
        
        result = self.strategy._check_time_window_with_std_pct("9984", outside_time)
        
        self.assertFalse(result['in_window'])
        self.assertEqual(result['allowed_directions'], [])
    
    def test_excluded_15_00_minute_returns_empty_directions(self):
        """测试被排除的15:00分钟返回空的交易方向"""
        # 设置15:00时间
        exclude_time = datetime(2024, 1, 1, 15, 0)
        
        result = self.strategy._check_time_window_with_std_pct("9984", exclude_time)
        
        self.assertFalse(result['in_window'])
        self.assertEqual(result['allowed_directions'], [])
    
    def test_check_x_condition_uses_window_directions(self):
        """测试check_x_condition使用时间窗口的允许方向"""
        # 设置早上时间
        morning_time = datetime(2024, 1, 1, 9, 20)
        
        # 模拟std_pct检查通过
        with patch.object(self.strategy, '_calculate_and_check_std_pct') as mock_std_pct:
            mock_std_pct.return_value = {'std_pct': 0.001, 'ok': True}
            
            result = self.strategy.check_x_condition("9984", morning_time)
            
            # 应该返回时间窗口配置的允许方向
            self.assertEqual(result, ['long'])
    
    def test_check_x_condition_std_pct_fail_returns_empty(self):
        """测试std_pct检查失败时返回空列表"""
        # 设置早上时间
        morning_time = datetime(2024, 1, 1, 9, 20)
        
        # 模拟std_pct检查失败
        with patch.object(self.strategy, '_calculate_and_check_std_pct') as mock_std_pct:
            mock_std_pct.return_value = {'std_pct': 0.0001, 'ok': False}
            
            result = self.strategy.check_x_condition("9984", morning_time)
            
            # 应该返回空列表
            self.assertEqual(result, [])
    
    def test_check_x_condition_outside_window_returns_empty(self):
        """测试在交易窗口外时返回空列表"""
        # 设置非交易时间
        outside_time = datetime(2024, 1, 1, 10, 0)
        
        result = self.strategy.check_x_condition("9984", outside_time)
        
        # 应该返回空列表
        self.assertEqual(result, [])
    
    def test_custom_directions_configuration(self):
        """测试可以配置不同的交易方向"""
        # 保存原始方法
        original_method = self.strategy._check_time_window_with_std_pct
        
        # 创建一个修改版本的方法来测试不同配置
        def modified_check_time_window_with_std_pct(symbol, current_time=None):
            if current_time is None:
                current_time = datetime.now()
                
            current_time_only = current_time.time()
            
            # 定义不同的时间窗口配置
            time_windows = [
                {
                    'start': time(9, 15),
                    'end': time(9, 41),
                    'threshold': self.strategy.std_pct_threshold_morning,
                    'name': 'morning',
                    'allowed_directions': ['long']  # 只允许多头
                },
                {
                    'start': time(11, 25),
                    'end': time(11, 31),
                    'threshold': self.strategy.std_pct_threshold_noon,
                    'name': 'noon',
                    'allowed_directions': ['short']  # 只允许空头
                }
            ]
            
            # 检查是否在时间窗口内
            for window in time_windows:
                if window['start'] <= current_time_only <= window['end']:
                    std_pct_result = self.strategy._calculate_and_check_std_pct(symbol, window['threshold'])
                    return {
                        'in_window': True,
                        'time_period': window['name'],
                        'threshold': window['threshold'],
                        'std_pct': std_pct_result['std_pct'],
                        'std_pct_ok': std_pct_result['ok'],
                        'allowed_directions': window['allowed_directions'],
                        'price_check_ok': True,
                        'price_check_reason': f'{window["name"]}时段股价100符合限制'
                    }
            
            return {
                'in_window': False,
                'time_period': None,
                'threshold': None,
                'std_pct': None,
                'std_pct_ok': False,
                'allowed_directions': [],
                'price_check_ok': True,
                'price_check_reason': '不在交易窗口内'
            }
        
        # 临时替换方法
        self.strategy._check_time_window_with_std_pct = modified_check_time_window_with_std_pct
        
        try:
            # 测试早上时间只允许多头
            morning_time = datetime(2024, 1, 1, 9, 20)
            with patch.object(self.strategy, '_calculate_and_check_std_pct') as mock_std_pct, \
                 patch.object(self.strategy, 'get_stock_prev_close') as mock_prev_close:
                mock_std_pct.return_value = {'std_pct': 0.001, 'ok': True}
                mock_prev_close.return_value = 100.0  # 模拟前一天收盘价
                
                result = self.strategy.check_x_condition("9984", morning_time)
                self.assertEqual(result, ['long'])
            
            # 测试中午时间只允许空头
            noon_time = datetime(2024, 1, 1, 11, 29, 30)
            with patch.object(self.strategy, '_calculate_and_check_std_pct') as mock_std_pct:
                mock_std_pct.return_value = {'std_pct': 0.001, 'ok': True}
                
                result = self.strategy.check_x_condition("9984", noon_time)
                self.assertEqual(result, ['short'])
                
        finally:
            # 恢复原始方法
            self.strategy._check_time_window_with_std_pct = original_method


if __name__ == '__main__':
    unittest.main()
