"""
测试修改后的on_1min_bar方法
"""

import unittest
import sys
import os
from unittest.mock import Mock, patch
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hft_bb_reversal_strategy import HFTBBReversalStrategy, HFTBBStockContext, TriggerLevels
from vnpy.trader.object import BarData
from vnpy.trader.constant import Exchange


class TestOn1MinBar(unittest.TestCase):
    """测试修改后的on_1min_bar方法"""
    
    def setUp(self):
        """设置测试环境"""
        self.strategy = HFTBBReversalStrategy(use_mock_gateway=True)
        # Mock write_log方法
        self.strategy.write_log = Mock()
        # 创建测试用的HFT context
        self.strategy.create_hft_context("2330")
    
    @patch('intraday_strategy_base.IntradayStrategyBase.on_1min_bar')
    def test_on_1min_bar_without_indicator_manager(self, mock_super_on_1min_bar):
        """测试没有技术指标管理器的情况"""
        bar = BarData(
            symbol="2330",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            interval="1m",
            volume=1000,
            open_price=100.0,
            high_price=101.0,
            low_price=99.0,
            close_price=100.5,
            gateway_name="test"
        )
        
        # 确保没有技术指标管理器
        self.strategy.indicator_managers = {}
        
        self.strategy.on_1min_bar(bar)
        
        # 验证日志记录
        self.strategy.write_log.assert_called()
        # 验证调用了父类方法
        mock_super_on_1min_bar.assert_called_once_with(bar)
    
    @patch('intraday_strategy_base.IntradayStrategyBase.on_1min_bar')
    def test_on_1min_bar_with_indicator_manager(self, mock_super_on_1min_bar):
        """测试有技术指标管理器的情况"""
        bar = BarData(
            symbol="2330",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            interval="1m",
            volume=1000,
            open_price=100.0,
            high_price=101.0,
            low_price=99.0,
            close_price=100.5,
            gateway_name="test"
        )
        
        # Mock技术指标管理器
        mock_manager = Mock()
        mock_indicators = {
            'bb_upper': 101.0,
            'bb_lower': 99.0,
            'bb_middle': 100.0
        }
        mock_manager.update_bar.return_value = mock_indicators
        
        self.strategy.indicator_managers = {"2330": mock_manager}
        
        # Mock _calculate_bb_levels方法
        self.strategy._calculate_bb_levels = Mock(return_value={
            'upper': 101.0,
            'lower': 99.0,
            'middle': 100.0,
            'exit_long': 100.5,
            'exit_short': 99.5,
            'std': 1.0
        })
        
        # Mock check_x_condition方法
        self.strategy.check_x_condition = Mock(return_value=True)
        
        self.strategy.on_1min_bar(bar)
        
        # 验证技术指标管理器被调用
        mock_manager.update_bar.assert_called_once_with(bar)
        
        # 验证BB水平计算被调用
        self.strategy._calculate_bb_levels.assert_called_once_with("2330", mock_indicators)
        
        # 验证X条件检查被调用
        self.strategy.check_x_condition.assert_called_once_with("2330", bar.datetime)
        
        # 验证context被正确更新
        context = self.strategy.get_hft_context("2330")
        self.assertIsNotNone(context.bb_levels)
        self.assertIsNotNone(context.trigger_levels)
        self.assertTrue(context.can_trade)
    
    @patch('intraday_strategy_base.IntradayStrategyBase.on_1min_bar')
    def test_on_1min_bar_with_position(self, mock_super_on_1min_bar):
        """测试有持仓的情况"""
        bar = BarData(
            symbol="2330",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            interval="1m",
            volume=1000,
            open_price=100.0,
            high_price=101.0,
            low_price=99.0,
            close_price=100.5,
            gateway_name="test"
        )
        
        # 设置持仓
        context = self.strategy.get_hft_context("2330")
        context.position = 100  # 多头持仓
        
        # Mock技术指标管理器
        mock_manager = Mock()
        mock_indicators = {
            'bb_upper': 101.0,
            'bb_lower': 99.0,
            'bb_middle': 100.0
        }
        mock_manager.update_bar.return_value = mock_indicators
        
        self.strategy.indicator_managers = {"2330": mock_manager}
        
        # Mock _calculate_bb_levels方法
        self.strategy._calculate_bb_levels = Mock(return_value={
            'upper': 101.0,
            'lower': 99.0,
            'middle': 100.0,
            'exit_long': 100.5,
            'exit_short': 99.5,
            'std': 1.0
        })
        
        # Mock check_x_condition方法
        self.strategy.check_x_condition = Mock(return_value=True)
        
        # Mock _execute_exit方法
        self.strategy._execute_exit = Mock(return_value="EXIT_ORDER_123")
        
        self.strategy.on_1min_bar(bar)
        
        # 验证_manage_exit_order被调用（通过日志验证）
        # 由于_manage_exit_order会记录日志，我们可以验证日志调用
        log_calls = [call[0][0] for call in self.strategy.write_log.call_args_list]
        self.assertTrue(any("管理出场订单" in call for call in log_calls))
    
    @patch('intraday_strategy_base.IntradayStrategyBase.on_1min_bar')
    def test_on_1min_bar_bb_levels_none(self, mock_super_on_1min_bar):
        """测试BB水平为None的情况"""
        bar = BarData(
            symbol="2330",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            interval="1m",
            volume=1000,
            open_price=100.0,
            high_price=101.0,
            low_price=99.0,
            close_price=100.5,
            gateway_name="test"
        )
        
        # Mock技术指标管理器
        mock_manager = Mock()
        mock_indicators = {
            'bb_upper': 101.0,
            'bb_lower': 99.0,
            'bb_middle': 100.0
        }
        mock_manager.update_bar.return_value = mock_indicators
        
        self.strategy.indicator_managers = {"2330": mock_manager}
        
        # Mock _calculate_bb_levels方法返回None
        self.strategy._calculate_bb_levels = Mock(return_value=None)
        
        self.strategy.on_1min_bar(bar)
        
        # 验证技术指标管理器被调用
        mock_manager.update_bar.assert_called_once_with(bar)
        
        # 验证BB水平计算被调用
        self.strategy._calculate_bb_levels.assert_called_once_with("2330", mock_indicators)
        
        # 验证context没有被更新
        context = self.strategy.get_hft_context("2330")
        self.assertIsNone(context.bb_levels)
        self.assertIsNone(context.trigger_levels)


if __name__ == '__main__':
    unittest.main()
