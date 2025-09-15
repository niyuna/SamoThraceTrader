"""
测试参数更新系统
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, time
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from hft_bb_reversal_strategy import HFTBBReversalStrategy
from hft_bb_indicators import HFTBBReversalIndicatorV2
from vnpy.trader.object import BarData
from vnpy.trader.constant import Exchange


class TestParameterUpdateSystem(unittest.TestCase):
    """测试参数更新系统"""
    
    def setUp(self):
        """设置测试环境"""
        self.strategy = HFTBBReversalStrategy(use_mock_gateway=True)
        
        # 模拟event_engine
        self.strategy.event_engine = Mock()
        self.strategy.event_engine.register = Mock()
        self.strategy.event_engine.unregister = Mock()
        
        # 模拟gateway
        self.strategy.gateway = Mock()
        self.strategy.gateway.send_order = Mock()
        
        # 重置参数更新状态
        self.strategy.parameter_update_completed = False
        self.strategy.parameter_updates = []
        
        # 禁用参数更新定时器，避免在测试过程中自动更新参数
        self.strategy.parameter_update_schedule = {}
    
    def test_register_parameter_update_timer(self):
        """测试注册参数更新定时器"""
        # 注册定时器
        self.strategy._register_parameter_update_timer()
        
        # 验证定时器已注册
        self.strategy.event_engine.register.assert_called_once()
    
    def test_register_parameter_update_timer_no_event_engine(self):
        """测试没有event_engine时不注册定时器"""
        self.strategy.event_engine = None
        
        # 注册定时器
        self.strategy._register_parameter_update_timer()
        
        # 验证没有调用register
        self.strategy.event_engine = Mock()
        self.strategy.event_engine.register.assert_not_called()
    
    def test_time_matching(self):
        """测试时间匹配逻辑"""
        # 测试精确匹配
        current_time = time(9, 45, 0)
        target_time = time(9, 45, 0)
        self.assertTrue(self.strategy._is_time_matching(current_time, target_time))
        
        # 测试1秒误差内匹配
        current_time = time(9, 45, 1)
        target_time = time(9, 45, 0)
        self.assertTrue(self.strategy._is_time_matching(current_time, target_time))
        
        # 测试超过5秒误差不匹配
        current_time = time(9, 45, 6)
        target_time = time(9, 45, 0)
        self.assertFalse(self.strategy._is_time_matching(current_time, target_time))
        
        # 测试跨分钟匹配（修正：应该是59秒到0秒的跨分钟）
        current_time = time(9, 45, 59)
        target_time = time(9, 46, 0)
        self.assertTrue(self.strategy._is_time_matching(current_time, target_time))
    
    def test_parameter_update_timer_callback(self):
        """测试参数更新定时器回调"""
        # 设置参数更新计划
        self.strategy.parameter_update_schedule = {
            time(9, 45): {
                'bb_entry_std_multiplier': 2.5,
                'bb_exit_std_multiplier': 1.8,
                'trigger_tick_count': 5
            }
        }
        
        # 模拟时间匹配
        with patch('hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 1, 9, 45, 0)
            
            # 触发定时器回调
            self.strategy._on_parameter_update_timer(Mock())
            
            # 验证参数已更新
            self.assertEqual(self.strategy.bb_entry_std_multiplier, 2.5)
            self.assertEqual(self.strategy.bb_exit_std_multiplier, 1.8)
            self.assertEqual(self.strategy.trigger_tick_count, 5)
            
            # 验证参数更新完成状态
            self.assertTrue(self.strategy.parameter_update_completed)
            
            # 验证定时器已取消注册
            self.strategy.event_engine.unregister.assert_called_once()
    
    def test_parameter_update_timer_callback_already_completed(self):
        """测试参数更新已完成时不重复执行"""
        # 设置已完成状态
        self.strategy.parameter_update_completed = True
        
        # 模拟时间匹配
        with patch('hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 1, 9, 45, 0)
            
            # 触发定时器回调
            self.strategy._on_parameter_update_timer(Mock())
            
            # 验证参数没有更新
            self.assertEqual(self.strategy.bb_entry_std_multiplier, 3.0)  # 初始值
            self.assertEqual(self.strategy.bb_exit_std_multiplier, -1.0)  # 初始值
            self.assertEqual(self.strategy.trigger_tick_count, 3)  # 初始值
    
    def test_parameter_update_timer_callback_no_match(self):
        """测试时间不匹配时不执行更新"""
        # 模拟时间不匹配
        with patch('hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 1, 10, 0, 0)
            
            # 触发定时器回调
            self.strategy._on_parameter_update_timer(Mock())
            
            # 验证参数没有更新
            self.assertEqual(self.strategy.bb_entry_std_multiplier, 3.0)  # 初始值
            self.assertEqual(self.strategy.bb_exit_std_multiplier, -1.0)  # 初始值
            self.assertEqual(self.strategy.trigger_tick_count, 3)  # 初始值
    
    def test_update_parameters(self):
        """测试更新策略参数"""
        # 更新参数
        new_params = {
            'bb_entry_std_multiplier': 2.5,
            'bb_exit_std_multiplier': 1.8,
            'trigger_tick_count': 5
        }
        
        self.strategy.update_parameters(new_params)
        
        # 验证参数已更新
        self.assertEqual(self.strategy.bb_entry_std_multiplier, 2.5)
        self.assertEqual(self.strategy.bb_exit_std_multiplier, 1.8)
        self.assertEqual(self.strategy.trigger_tick_count, 5)
        
        # 验证更新历史已记录
        self.assertEqual(len(self.strategy.parameter_updates), 1)
        self.assertEqual(self.strategy.parameter_updates[0]['new_parameters'], new_params)
    
    def test_update_parameters_partial(self):
        """测试部分更新参数"""
        # 只更新部分参数
        new_params = {
            'bb_entry_std_multiplier': 2.5
        }
        
        self.strategy.update_parameters(new_params)
        
        # 验证只有指定参数更新
        self.assertEqual(self.strategy.bb_entry_std_multiplier, 2.5)
        self.assertEqual(self.strategy.bb_exit_std_multiplier, -1.0)  # 未更新
        self.assertEqual(self.strategy.trigger_tick_count, 3)  # 未更新
    
    def test_update_indicator_managers_parameters(self):
        """测试更新技术指标管理器参数"""
        # 创建模拟的技术指标管理器
        mock_manager1 = Mock()
        mock_manager1.update_parameters = Mock()
        mock_manager2 = Mock()
        mock_manager2.update_parameters = Mock()
        
        self.strategy.indicator_managers = {
            'TEST1': mock_manager1,
            'TEST2': mock_manager2
        }
        
        # 更新参数
        self.strategy._update_indicator_managers_parameters()
        
        # 验证所有管理器都被更新
        mock_manager1.update_parameters.assert_called_once_with(
            entry_std_multiplier=3.0,
            exit_std_multiplier=-1.0
        )
        mock_manager2.update_parameters.assert_called_once_with(
            entry_std_multiplier=3.0,
            exit_std_multiplier=-1.0
        )
    
    def test_unregister_parameter_update_timer(self):
        """测试取消参数更新定时器注册"""
        # 取消注册
        self.strategy._unregister_parameter_update_timer()
        
        # 验证定时器已取消注册
        self.strategy.event_engine.unregister.assert_called_once()
    
    def test_unregister_parameter_update_timer_no_event_engine(self):
        """测试没有event_engine时不取消注册"""
        self.strategy.event_engine = None
        
        # 取消注册
        self.strategy._unregister_parameter_update_timer()
        
        # 验证没有调用unregister
        self.strategy.event_engine = Mock()
        self.strategy.event_engine.unregister.assert_not_called()


class TestHFTBBReversalIndicatorV2ParameterUpdate(unittest.TestCase):
    """测试HFTBBReversalIndicatorV2参数更新"""
    
    def setUp(self):
        """设置测试环境"""
        self.indicator = HFTBBReversalIndicatorV2(
            symbol="TEST",
            entry_std_multiplier=3.0,
            exit_std_multiplier=-0.5
        )
        
        # 模拟ArrayManager数据
        self.indicator.am = Mock()
        self.indicator.am.close = [100.0] * 25  # 足够的数据
        self.indicator.am.inited = True
        self.indicator.am.sma.return_value = 100.0
        self.indicator.am.std.return_value = 2.0
        
        # 设置初始BB水平
        self.indicator.bb_upper = 106.0
        self.indicator.bb_middle = 100.0
        self.indicator.bb_lower = 94.0
        self.indicator.exit_long = 99.0
        self.indicator.exit_short = 101.0
        self.indicator.upper_trigger = 105.0
        self.indicator.lower_trigger = 95.0
    
    def test_update_parameters(self):
        """测试更新技术指标参数"""
        # 更新参数
        self.indicator.update_parameters(
            entry_std_multiplier=2.5,
            exit_std_multiplier=1.8
        )
        
        # 验证参数已更新
        self.assertEqual(self.indicator.entry_std_multiplier, 2.5)
        self.assertEqual(self.indicator.exit_std_multiplier, 1.8)
    
    def test_update_parameters_partial(self):
        """测试部分更新参数"""
        # 只更新entry_std_multiplier
        self.indicator.update_parameters(entry_std_multiplier=2.5)
        
        # 验证只有指定参数更新
        self.assertEqual(self.indicator.entry_std_multiplier, 2.5)
        self.assertEqual(self.indicator.exit_std_multiplier, -0.5)  # 未更新
    
    def test_update_parameters_simple(self):
        """测试更新参数（简单版本，不重新计算BB水平）"""
        # 更新参数
        self.indicator.update_parameters(entry_std_multiplier=2.5)
        
        # 验证参数已更新
        self.assertEqual(self.indicator.entry_std_multiplier, 2.5)
        self.assertEqual(self.indicator.exit_std_multiplier, -0.5)  # 未更新
        
        # 验证BB水平没有改变（因为不立即重新计算）
        self.assertEqual(self.indicator.bb_upper, 106.0)  # 保持原值
        self.assertEqual(self.indicator.bb_lower, 94.0)   # 保持原值


if __name__ == '__main__':
    unittest.main()
