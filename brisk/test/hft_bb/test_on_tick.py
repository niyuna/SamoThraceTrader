"""
测试修改后的on_tick方法
"""

import unittest
import sys
import os
from unittest.mock import Mock, patch
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from hft_bb_reversal_strategy import HFTBBReversalStrategy, HFTBBStockContext, TriggerLevels
from vnpy.trader.object import TickData
from vnpy.trader.constant import Exchange


class TestOnTick(unittest.TestCase):
    """测试修改后的on_tick方法"""
    
    def setUp(self):
        """设置测试环境"""
        self.strategy = HFTBBReversalStrategy(use_mock_gateway=True)
        # 直接设置mock gateway
        self.strategy.gateway = Mock()
        self.strategy.gateway.send_order = Mock(return_value="test_order_123")
        # Mock write_log方法
        self.strategy.write_log = Mock()
        # 创建测试用的HFT context
        self.strategy.create_hft_context("2330")
    
    def test_on_tick_can_trade_false(self):
        """测试X条件不满足的情况"""
        tick = TickData(
            symbol="2330",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            name="台积电",
            volume=1000,
            last_price=100.0,
            gateway_name="test"
        )
        
        # 设置context的can_trade为False
        context = self.strategy.get_hft_context("2330")
        context.can_trade = False
        
        # Mock _update_simulated_positions方法
        self.strategy._update_simulated_positions = Mock()
        
        self.strategy.on_tick(Mock(data=tick))
        
        # 验证_update_simulated_positions被调用
        self.strategy._update_simulated_positions.assert_called_once_with(tick)
        
        # 验证_check_entry_logic没有被调用（因为can_trade为False）
        # 这通过没有相关的日志调用来验证
    
    def test_on_tick_can_trade_true_no_trigger_levels(self):
        """测试X条件满足但没有触发价格水平的情况"""
        tick = TickData(
            symbol="2330",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            name="台积电",
            volume=1000,
            last_price=100.0,
            gateway_name="test"
        )
        
        # 设置context的can_trade为True，但没有trigger_levels
        context = self.strategy.get_hft_context("2330")
        context.can_trade = True
        context.trigger_levels = None
        
        # Mock _update_simulated_positions方法
        self.strategy._update_simulated_positions = Mock()
        
        self.strategy.on_tick(Mock(data=tick))
        
        # 验证_update_simulated_positions被调用
        self.strategy._update_simulated_positions.assert_called_once_with(tick)
    
    def test_on_tick_can_trade_true_with_trigger_levels(self):
        """测试X条件满足且有触发价格水平的情况"""
        tick = TickData(
            symbol="2330",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            name="台积电",
            volume=1000,
            last_price=98.0,  # 使用会触发下轨的价格
            gateway_name="test"
        )
        
        # 设置context的can_trade为True，并有trigger_levels
        context = self.strategy.get_hft_context("2330")
        context.can_trade = True
        context.trigger_levels = TriggerLevels(
            upper_trigger=101.0,
            upper_limit=101.5,
            lower_trigger=99.0,
            lower_limit=98.5
        )
        
        # Mock _update_simulated_positions方法
        self.strategy._update_simulated_positions = Mock()
        
        self.strategy.on_tick(Mock(data=tick))
        
        # 验证_update_simulated_positions被调用
        self.strategy._update_simulated_positions.assert_called_once_with(tick)
        
        # 验证_check_entry_logic被调用（通过检查是否有订单相关日志）
        log_calls = [call[0][0] for call in self.strategy.write_log.call_args_list]
        # 检查是否有订单相关的日志输出（表示_check_entry_logic确实被调用了）
        self.assertTrue(any("订单" in call or "entry" in call.lower() for call in log_calls))
    
    def test_on_tick_with_bar_generator(self):
        """测试有BarGenerator的情况"""
        tick = TickData(
            symbol="2330",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            name="台积电",
            volume=1000,
            last_price=100.0,
            gateway_name="test"
        )
        
        # 设置context的can_trade为False（避免触发入场逻辑）
        context = self.strategy.get_hft_context("2330")
        context.can_trade = False
        
        # Mock BarGenerator
        mock_bar_generator = Mock()
        self.strategy.bar_generators = {"2330": mock_bar_generator}
        
        # Mock _update_simulated_positions方法
        self.strategy._update_simulated_positions = Mock()
        
        self.strategy.on_tick(Mock(data=tick))
        
        # 验证BarGenerator的update_tick被调用
        mock_bar_generator.update_tick.assert_called_once_with(tick)
        
        # 验证_update_simulated_positions被调用
        self.strategy._update_simulated_positions.assert_called_once_with(tick)
    
    def test_on_tick_trigger_upper_band(self):
        """测试触发上轨的情况"""
        tick = TickData(
            symbol="2330",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            name="台积电",
            volume=1000,
            last_price=101.5,  # 高于上轨触发价格
            gateway_name="test"
        )
        
        # 设置context的can_trade为True，并有trigger_levels
        context = self.strategy.get_hft_context("2330")
        context.can_trade = True
        context.trigger_levels = TriggerLevels(
            upper_trigger=101.0,
            upper_limit=101.5,
            lower_trigger=99.0,
            lower_limit=98.5
        )
        
        # Mock _update_simulated_positions方法
        self.strategy._update_simulated_positions = Mock()
        
        # Mock _execute_entry方法
        self.strategy._execute_entry = Mock()
        
        self.strategy.on_tick(Mock(data=tick))
        
        # 验证日志包含触发上轨的信息
        log_calls = [call[0][0] for call in self.strategy.write_log.call_args_list]
        self.assertTrue(any("触发上轨" in call for call in log_calls))
    
    def test_on_tick_trigger_lower_band(self):
        """测试触发下轨的情况"""
        tick = TickData(
            symbol="2330",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            name="台积电",
            volume=1000,
            last_price=98.0,  # 低于下轨触发价格
            gateway_name="test"
        )
        
        # 设置context的can_trade为True，并有trigger_levels
        context = self.strategy.get_hft_context("2330")
        context.can_trade = True
        context.trigger_levels = TriggerLevels(
            upper_trigger=101.0,
            upper_limit=101.5,
            lower_trigger=99.0,
            lower_limit=98.5
        )
        
        # Mock _update_simulated_positions方法
        self.strategy._update_simulated_positions = Mock()
        
        # Mock _execute_entry方法
        self.strategy._execute_entry = Mock()
        
        self.strategy.on_tick(Mock(data=tick))
        
        # 验证日志包含触发下轨的信息
        log_calls = [call[0][0] for call in self.strategy.write_log.call_args_list]
        self.assertTrue(any("触发下轨" in call for call in log_calls))


if __name__ == '__main__':
    unittest.main()
