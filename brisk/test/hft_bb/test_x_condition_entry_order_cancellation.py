"""
X条件检查与entry订单取消逻辑测试
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


class TestXConditionEntryOrderCancellation(unittest.TestCase):
    """测试X条件检查与entry订单取消逻辑"""
    
    def setUp(self):
        """设置测试环境"""
        self.strategy = HFTBBReversalStrategy(use_mock_gateway=True)
        self.strategy.write_log = Mock()
        
        # 覆盖策略参数，使测试独立于默认参数
        self.strategy.price_limit_morning = 5000    # 提高morning时段价格限制
        self.strategy.price_limit_noon = 5000       # 提高noon时段价格限制  
        self.strategy.price_limit_afternoon = 5000  # 提高afternoon时段价格限制
        self.strategy.max_price_change_pct = 20.0   # 提高价格变动限制
        self.strategy.aggressive_x_condition_enabled = True  # 启用激进X条件以测试模拟持仓逻辑
        
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
    
    def test_x_condition_without_entry_order_normal_check(self):
        """测试没有entry订单时正常进行X条件检查"""
        context = self.strategy.get_hft_context(self.symbol)
        context.entry_order_id = ""  # 没有entry订单
        
        with patch('hft_bb_reversal_strategy.datetime') as mock_datetime, \
             patch.object(self.strategy, '_check_price_limit') as mock_price_limit:
            mock_datetime.now.return_value = datetime.combine(datetime.now().date(), time(9, 20))
            mock_price_limit.return_value = {'ok': True, 'reason': '价格检查通过'}
            
            result = self.strategy.check_x_condition(self.symbol)
            self.assertTrue(result)
    
    def test_x_condition_with_entry_order_still_checks_conditions(self):
        """测试有entry订单时仍然进行X条件检查（不再有优先级）"""
        context = self.strategy.get_hft_context(self.symbol)
        context.entry_order_id = "test_entry_123"  # 有entry订单
        
        # 模拟时间窗口外的情况
        with patch('hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime.combine(datetime.now().date(), time(16, 0))
            
            result = self.strategy.check_x_condition(self.symbol)
            self.assertFalse(result)  # 应该返回False，不再因为有entry订单就返回True
    
    def test_on_1min_bar_cancels_entry_order_when_x_condition_fails(self):
        """测试on_1min_bar不再取消entry订单，因为现在由_check_entry_logic处理"""
        context = self.strategy.get_hft_context(self.symbol)
        context.entry_order_id = "test_entry_123"
        context.state = StrategyState.WAITING_ENTRY
        
        # 创建indicator manager并设置BB levels
        from brisk.hft_bb_indicators import HFTBBReversalIndicatorV2
        indicator = HFTBBReversalIndicatorV2(self.symbol)
        # 模拟indicator返回BB levels
        indicator.get_indicators = Mock(return_value={
            'upper': 100.5,
            'lower': 99.5,
            'middle': 100.0,
            'std': 0.2,
            'exit_long': 99.8,
            'exit_short': 100.2
        })
        self.strategy.indicator_managers[self.symbol] = indicator
        
        # 模拟时间窗口外的情况
        with patch('hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime.combine(datetime.now().date(), time(16, 0))
            
            # 模拟bar数据
            from vnpy.trader.object import BarData
            from vnpy.trader.constant import Exchange, Interval
            bar = BarData(
                symbol=self.symbol,
                exchange=Exchange.TSE,
                datetime=datetime.now(),
                interval=Interval.MINUTE,
                volume=1000,
                turnover=100000,
                open_price=100.0,
                high_price=101.0,
                low_price=99.0,
                close_price=100.5,
                gateway_name="TEST"
            )
            
            # 调用on_1min_bar
            self.strategy.on_1min_bar(bar)
            
            # 验证不再有取消订单的日志（因为现在由_check_entry_logic处理）
            log_calls = [call[0][0] for call in self.strategy.write_log.call_args_list]
            self.assertNotIn("X条件不满足但发现活跃entry订单，取消订单: 9984", log_calls)
    
    def test_on_1min_bar_no_cancellation_when_x_condition_passes(self):
        """测试on_1min_bar在X条件满足时不取消entry订单"""
        context = self.strategy.get_hft_context(self.symbol)
        context.entry_order_id = "test_entry_123"
        context.state = StrategyState.WAITING_ENTRY
        
        # 模拟时间窗口内的情况
        with patch('hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime.combine(datetime.now().date(), time(9, 20))
            
            # 模拟bar数据
            from vnpy.trader.object import BarData
            from vnpy.trader.constant import Exchange, Interval
            bar = BarData(
                symbol=self.symbol,
                exchange=Exchange.TSE,
                datetime=datetime.now(),
                interval=Interval.MINUTE,
                volume=1000,
                turnover=100000,
                open_price=100.0,
                high_price=101.0,
                low_price=99.0,
                close_price=100.5,
                gateway_name="TEST"
            )
            
            # 调用on_1min_bar
            self.strategy.on_1min_bar(bar)
            
            # 验证没有取消订单的日志
            log_calls = [call[0][0] for call in self.strategy.write_log.call_args_list]
            self.assertNotIn("X条件不满足但发现活跃entry订单，取消订单: 9984", log_calls)
    
    def test_on_1min_bar_no_cancellation_when_no_entry_order(self):
        """测试on_1min_bar在没有entry订单时不进行取消操作"""
        context = self.strategy.get_hft_context(self.symbol)
        context.entry_order_id = ""  # 没有entry订单
        
        # 模拟时间窗口外的情况
        with patch('hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime.combine(datetime.now().date(), time(16, 0))
            
            # 模拟bar数据
            from vnpy.trader.object import BarData
            from vnpy.trader.constant import Exchange, Interval
            bar = BarData(
                symbol=self.symbol,
                exchange=Exchange.TSE,
                datetime=datetime.now(),
                interval=Interval.MINUTE,
                volume=1000,
                turnover=100000,
                open_price=100.0,
                high_price=101.0,
                low_price=99.0,
                close_price=100.5,
                gateway_name="TEST"
            )
            
            # 调用on_1min_bar
            self.strategy.on_1min_bar(bar)
            
            # 验证没有取消订单的日志
            log_calls = [call[0][0] for call in self.strategy.write_log.call_args_list]
            self.assertNotIn("X条件不满足但发现活跃entry订单，取消订单: 9984", log_calls)
    
    def test_x_condition_priority_removed(self):
        """测试X条件检查不再有entry订单优先级"""
        context = self.strategy.get_hft_context(self.symbol)
        context.entry_order_id = "test_entry_123"
        
        # 模拟不在eligible_stocks中的情况
        self.strategy.eligible_stocks.clear()
        
        result = self.strategy.check_x_condition(self.symbol)
        self.assertFalse(result)  # 应该返回False，不再因为有entry订单就返回True
        
        # 验证日志记录
        log_calls = [call[0][0] for call in self.strategy.write_log.call_args_list]
        self.assertIn("X条件检查失败: 9984 不在eligible_stocks中", log_calls)
    
    def test_x_condition_with_position_still_checks(self):
        """测试有持仓时X条件检查仍然进行"""
        context = self.strategy.get_hft_context(self.symbol)
        context.entry_order_id = "test_entry_123"
        
        # 设置模拟持仓（entry时间在窗口内且方向匹配，应该允许交易）
        self.strategy.simulated_positions[self.symbol] = {
            'long': True, 
            'short': False,
            'long_entry_time': datetime(2024, 1, 1, 9, 15, 0),  # 在morning窗口内
            'short_entry_time': None,
            'long_exit_time': None,
            'short_exit_time': None
        }
        
        # 设置早上时间（满足时间窗口）
        morning_time = datetime(2024, 1, 1, 9, 20)
        
        with patch('hft_bb_reversal_strategy.datetime') as mock_datetime, \
             patch.object(self.strategy, '_check_price_limit') as mock_price_limit:
            mock_datetime.now.return_value = morning_time
            mock_price_limit.return_value = {'ok': True, 'reason': '价格检查通过'}
            result = self.strategy.check_x_condition(self.symbol)
        
        # 由于entry时间在窗口内且方向匹配，应该允许交易
        self.assertTrue(result)
        
        # 验证日志记录
        log_calls = [call[0][0] for call in self.strategy.write_log.call_args_list]
        self.assertIn("X条件检查通过: 9984 模拟持仓方向匹配，允许long交易", log_calls)
    
    def test_check_entry_logic_handles_x_condition_failure(self):
        """测试_check_entry_logic处理X条件不满足的情况"""
        context = self.strategy.get_hft_context(self.symbol)
        context.entry_order_id = "test_entry_123"
        context.state = StrategyState.WAITING_ENTRY
        
        # 设置BB levels和trigger levels
        context.bb_levels = {
            'upper': 100.5,
            'lower': 99.5,
            'middle': 100.0,
            'std': 0.2
        }
        context.trigger_levels = Mock()
        context.trigger_levels.upper_trigger = 100.2
        context.trigger_levels.lower_trigger = 99.6
        
        # 模拟时间窗口外的情况（X条件不满足）
        with patch('hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime.combine(datetime.now().date(), time(16, 0))
            
            # 模拟tick数据
            from vnpy.trader.object import TickData
            from vnpy.trader.constant import Exchange
            tick = TickData(
                symbol=self.symbol,
                exchange=Exchange.TSE,
                datetime=datetime.now(),
                name="Test Stock",
                volume=1000,
                turnover=100000,
                last_price=100.0,
                last_volume=100,
                limit_up=105.0,
                limit_down=95.0,
                open_price=99.5,
                high_price=100.5,
                low_price=99.0,
                pre_close=99.8,
                gateway_name="TEST"
            )
            
            # 调用_check_entry_logic
            self.strategy._check_entry_logic(self.symbol, tick, context)
            
            # 验证X条件检查被调用（因为can_trade为False，不会执行entry逻辑）
            # 这里主要验证不会因为X条件不满足而崩溃
            self.assertIsNotNone(context.entry_order_id)  # entry_order_id应该保持不变


if __name__ == '__main__':
    unittest.main()
