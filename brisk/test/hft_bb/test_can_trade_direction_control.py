"""
测试can_trade对交易方向的控制功能
"""

import unittest
from unittest.mock import Mock, patch
from datetime import datetime, time, timedelta
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from hft_bb_reversal_strategy import HFTBBReversalStrategy, HFTBBStockContext, StrategyState, Direction
from vnpy.trader.constant import Exchange
from vnpy.trader.object import TickData


class TestCanTradeDirectionControl(unittest.TestCase):
    """测试can_trade对交易方向的控制"""
    
    def setUp(self):
        """设置测试环境"""
        self.strategy = HFTBBReversalStrategy(use_mock_gateway=True)
        
        # 模拟gateway
        self.strategy.gateway = Mock()
        self.strategy.gateway.send_order = Mock()
        self.strategy.gateway.cancel_order = Mock(return_value=True)
        
        # 模拟write_log
        self.strategy.write_log = Mock()
        
        # 模拟_cancel_order_with_verification方法
        self.strategy._cancel_order_with_verification = Mock(return_value=True)
        
        # 添加测试股票到eligible_stocks
        self.strategy.eligible_stocks = ["9984"]
        
        # 创建测试context
        self.strategy.hft_contexts["9984"] = HFTBBStockContext(symbol="9984")
        context = self.strategy.hft_contexts["9984"]
        
        # 设置BB levels和trigger levels
        context.bb_levels = {
            'upper': 100.0,
            'lower': 99.0,
            'middle': 99.5,
            'std': 0.8  # 添加std值用于std_pct计算
        }
        
        from hft_bb_reversal_strategy import TriggerLevels
        context.trigger_levels = TriggerLevels(
            upper_trigger=99.8,
            upper_limit=99.9,
            lower_trigger=99.2,
            lower_limit=99.1
        )
        
        # 设置position_size
        context.position_size = 100
    
    def test_cancel_and_reorder_respects_can_trade_long_only(self):
        """测试只允许多头时，取消重下订单会遵守限制"""
        context = self.strategy.hft_contexts["9984"]
        
        # 设置只允许多头交易
        context.can_trade = ['long']
        
        # 模拟已有空头订单（设置较早的时间以避免同一分钟保护）
        context.entry_order_id = "test_order_123"
        context.entry_price = 99.8  # 空头订单价格（与上轨价格不同）
        context.entry_order_time = datetime.now().replace(second=0, microsecond=0) - timedelta(minutes=1)  # 设置为1分钟前
        
        # 创建触发下轨的tick（应该下多头订单）
        tick = TickData(
            symbol="9984",
            exchange=Exchange.SSE,
            datetime=datetime.now(),
            name="测试股票",
            volume=1000,
            turnover=100000,
            open_price=99.0,
            high_price=99.5,
            low_price=98.8,
            pre_close=99.0,
            last_price=99.0,  # 明确触发下轨
            gateway_name="test"
        )
        
        # 调用_check_entry_logic
        self.strategy._check_entry_logic("9984", tick, context)
        
        # 验证gateway.send_order被调用（应该下多头订单）
        self.strategy.gateway.send_order.assert_called_once()
        call_args = self.strategy.gateway.send_order.call_args[0]
        self.assertEqual(call_args[0].direction, Direction.LONG)
    
    def test_cancel_and_reorder_respects_can_trade_short_only(self):
        """测试只允许空头时，取消重下订单会遵守限制"""
        context = self.strategy.hft_contexts["9984"]
        
        # 设置只允许空头交易
        context.can_trade = ['short']
        
        # 模拟已有空头订单（设置较早的时间以避免同一分钟保护）
        context.entry_order_id = "test_order_123"
        context.entry_price = 99.8  # 空头订单价格（与upper_limit不同）
        context.entry_order_time = datetime.now().replace(second=0, microsecond=0) - timedelta(minutes=1)  # 设置为1分钟前
        
        # 创建触发上轨的tick（应该下空头订单）
        tick = TickData(
            symbol="9984",
            exchange=Exchange.SSE,
            datetime=datetime.now(),
            name="测试股票",
            volume=1000,
            turnover=100000,
            open_price=100.0,
            high_price=100.5,
            low_price=99.8,
            pre_close=100.0,
            last_price=99.9,  # 触发上轨 (99.9 >= 99.8)
            gateway_name="test"
        )
        
        # 模拟下午时间，确保在交易窗口内
        with patch('brisk.hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 1, 14, 40)
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            
            # 调用_check_entry_logic
            self.strategy._check_entry_logic("9984", tick, context)
        
        # 验证gateway.send_order被调用（应该下空头订单）
        self.strategy.gateway.send_order.assert_called_once()
        call_args = self.strategy.gateway.send_order.call_args[0]
        self.assertEqual(call_args[0].direction, Direction.SHORT)
    
    def test_cancel_and_reorder_blocks_disallowed_direction(self):
        """测试取消重下订单时阻止不允许的方向"""
        context = self.strategy.hft_contexts["9984"]
        
        # 设置只允许多头交易
        context.can_trade = ['long']
        
        # 模拟已有多头订单（设置较早的时间以避免同一分钟保护）
        context.entry_order_id = "test_order_123"
        context.entry_price = 99.1  # 多头订单价格（与下轨价格不同）
        context.entry_order_time = datetime.now().replace(second=0, microsecond=0) - timedelta(minutes=1)  # 设置为1分钟前
        
        # 创建触发上轨的tick（应该下空头订单，但不被允许）
        tick = TickData(
            symbol="9984",
            exchange=Exchange.SSE,
            datetime=datetime.now(),
            name="测试股票",
            volume=1000,
            turnover=100000,
            open_price=100.0,
            high_price=100.5,
            low_price=99.8,
            pre_close=100.0,
            last_price=99.9,  # 明确触发上轨
            gateway_name="test"
        )
        
        # 调用_check_entry_logic
        self.strategy._check_entry_logic("9984", tick, context)
        
        # 验证gateway.send_order没有被调用（因为空头不被允许）
        self.strategy.gateway.send_order.assert_not_called()
    
    def test_cancel_and_reorder_blocks_disallowed_direction_short_only(self):
        """测试只允许空头时，取消重下订单阻止多头方向"""
        context = self.strategy.hft_contexts["9984"]
        
        # 设置只允许空头交易
        context.can_trade = ['short']
        
        # 模拟已有多头订单（设置较早的时间以避免同一分钟保护）
        context.entry_order_id = "test_order_123"
        context.entry_price = 99.1  # 多头订单价格
        context.entry_order_time = datetime.now().replace(second=0, microsecond=0) - timedelta(minutes=1)  # 设置为1分钟前
        
        # 创建触发下轨的tick（应该下多头订单，但不被允许）
        tick = TickData(
            symbol="9984",
            exchange=Exchange.SSE,
            datetime=datetime.now(),
            name="测试股票",
            volume=1000,
            turnover=100000,
            open_price=99.0,
            high_price=99.5,
            low_price=98.8,
            pre_close=99.0,
            last_price=99.1,  # 触发下轨
            gateway_name="test"
        )
        
        # 调用_check_entry_logic
        self.strategy._check_entry_logic("9984", tick, context)
        
        # 验证gateway.send_order没有被调用（因为多头不被允许）
        self.strategy.gateway.send_order.assert_not_called()
    
    def test_cancel_and_reorder_allows_both_directions(self):
        """测试允许双向交易时，取消重下订单正常工作"""
        context = self.strategy.hft_contexts["9984"]
        
        # 设置允许双向交易
        context.can_trade = ['long', 'short']
        
        # 模拟已有空头订单（设置较早的时间以避免同一分钟保护）
        context.entry_order_id = "test_order_123"
        context.entry_price = 99.8  # 空头订单价格（与upper_limit不同）
        context.entry_order_time = datetime.now().replace(second=0, microsecond=0) - timedelta(minutes=1)  # 设置为1分钟前
        
        # 创建触发上轨的tick（应该下空头订单）
        tick = TickData(
            symbol="9984",
            exchange=Exchange.SSE,
            datetime=datetime.now(),
            name="测试股票",
            volume=1000,
            turnover=100000,
            open_price=100.0,
            high_price=100.5,
            low_price=99.8,
            pre_close=100.0,
            last_price=99.9,  # 触发上轨 (99.9 >= 99.8)
            gateway_name="test"
        )
        
        # 模拟下午时间，确保在交易窗口内
        with patch('brisk.hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 1, 14, 40)
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            
            # 调用_check_entry_logic
            self.strategy._check_entry_logic("9984", tick, context)
        
        # 验证gateway.send_order被调用（应该下空头订单）
        self.strategy.gateway.send_order.assert_called_once()
        call_args = self.strategy.gateway.send_order.call_args[0]
        self.assertEqual(call_args[0].direction, Direction.SHORT)
    
    def test_cancel_and_reorder_no_directions_allowed(self):
        """测试不允许任何方向时，取消重下订单被阻止"""
        context = self.strategy.hft_contexts["9984"]
        
        # 设置不允许任何交易
        context.can_trade = []
        
        # 模拟已有订单（设置较早的时间以避免同一分钟保护）
        context.entry_order_id = "test_order_123"
        context.entry_price = 99.9
        context.entry_order_time = datetime.now().replace(second=0, microsecond=0) - timedelta(minutes=1)  # 设置为1分钟前
        
        # 创建触发上轨的tick
        tick = TickData(
            symbol="9984",
            exchange=Exchange.SSE,
            datetime=datetime.now(),
            name="测试股票",
            volume=1000,
            turnover=100000,
            open_price=100.0,
            high_price=100.5,
            low_price=99.8,
            pre_close=100.0,
            last_price=99.9,  # 触发上轨 (99.9 >= 99.8)
            gateway_name="test"
        )
        
        # 调用_check_entry_logic
        self.strategy._check_entry_logic("9984", tick, context)
        
        # 验证gateway.send_order没有被调用
        self.strategy.gateway.send_order.assert_not_called()
    
    def test_log_messages_for_direction_control(self):
        """测试方向控制的日志消息"""
        context = self.strategy.hft_contexts["9984"]
        
        # 设置只允许多头交易
        context.can_trade = ['long']
        
        # 模拟已有空头订单（设置较早的时间以避免同一分钟保护）
        context.entry_order_id = "test_order_123"
        context.entry_price = 99.8  # 空头订单价格（与upper_limit不同）
        context.entry_order_time = datetime.now().replace(second=0, microsecond=0) - timedelta(minutes=1)  # 设置为1分钟前
        
        # 创建触发上轨的tick（应该下空头订单，但不被允许）
        tick = TickData(
            symbol="9984",
            exchange=Exchange.SSE,
            datetime=datetime.now(),
            name="测试股票",
            volume=1000,
            turnover=100000,
            open_price=100.0,
            high_price=100.5,
            low_price=99.8,
            pre_close=100.0,
            last_price=99.9,  # 触发上轨 (99.9 >= 99.8)
            gateway_name="test"
        )
        
        # 模拟下午时间，确保在交易窗口内
        with patch('brisk.hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 1, 14, 40)
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            
            # 调用_check_entry_logic
            self.strategy._check_entry_logic("9984", tick, context)
        
        # 验证日志消息包含方向限制信息
        self.strategy.write_log.assert_any_call(
            "取消订单原因: 价格不同 当前:99.80 应该:99.90 但不重下订单(方向short不在允许范围内)"
        )


if __name__ == '__main__':
    unittest.main()
