"""
测试HFT BB策略的on_order方法
"""

import unittest
from unittest.mock import Mock, patch
from datetime import datetime
from vnpy.trader.constant import Direction, Offset, Status, Exchange
from vnpy.trader.object import OrderData, TickData

from hft_bb_reversal_strategy import HFTBBReversalStrategy, HFTBBStockContext, TriggerLevels
from intraday_strategy_base import StrategyState


class TestOnOrder(unittest.TestCase):
    """测试on_order方法"""
    
    def setUp(self):
        """设置测试环境"""
        self.strategy = HFTBBReversalStrategy(use_mock_gateway=True)
        self.strategy.write_log = Mock()
        self.strategy.update_context_state = Mock()
        self.strategy.create_hft_context("2330")
        
        # 确保base strategy context fields are initialized for testing
        context = self.strategy.get_hft_context("2330")
        context.position_size = 100
        context.already_traded = 0
    
    def test_find_hft_context_by_order_id_entry_order(self):
        """测试根据入场订单ID查找HFT context"""
        context = self.strategy.get_hft_context("2330")
        context.entry_order_id = "ENTRY_ORDER_123"
        context.exit_order_id = "EXIT_ORDER_456"
        
        # 测试查找入场订单
        found_context = self.strategy._find_hft_context_by_order_id("ENTRY_ORDER_123")
        self.assertEqual(found_context, context)
        
        # 测试查找出场订单
        found_context = self.strategy._find_hft_context_by_order_id("EXIT_ORDER_456")
        self.assertEqual(found_context, context)
        
        # 测试查找不存在的订单
        found_context = self.strategy._find_hft_context_by_order_id("NONEXISTENT_ORDER")
        self.assertIsNone(found_context)
    
    def test_on_order_non_alltraded_status(self):
        """测试非ALLTRADED状态的订单处理"""
        order = OrderData(
            symbol="2330",
            exchange=Exchange.TSE,
            orderid="TEST_ORDER",
            direction=Direction.LONG,
            offset=Offset.OPEN,
            price=100.0,
            volume=100,
            status=Status.SUBMITTING,  # 非ALLTRADED状态
            datetime=datetime.now(),
            gateway_name="test"
        )
        
        event = Mock(data=order)
        
        # 调用on_order
        self.strategy.on_order(event)
        
        # 验证没有调用任何处理方法
        self.strategy.update_context_state.assert_not_called()
    
    def test_on_order_entry_filled_long(self):
        """测试多头入场订单成交处理"""
        context = self.strategy.get_hft_context("2330")
        context.entry_order_id = "ENTRY_ORDER_123"
        context.bb_levels = {
            'upper': 101.0,
            'lower': 99.0,
            'middle': 100.0,
            'exit_long': 100.5,
            'exit_short': 99.5,
            'std': 1.0
        }
        
        order = OrderData(
            symbol="2330",
            exchange=Exchange.TSE,
            orderid="ENTRY_ORDER_123",
            direction=Direction.LONG,
            offset=Offset.OPEN,
            price=100.0,
            volume=100,
            status=Status.ALLTRADED,
            datetime=datetime.now(),
            gateway_name="test"
        )
        
        event = Mock(data=order)
        
        # Mock _manage_exit_order方法
        self.strategy._manage_exit_order = Mock()
        
        # 调用on_order
        self.strategy.on_order(event)
        
        # 验证context更新
        self.assertEqual(context.position, 100)  # 多头持仓
        self.assertEqual(context.entry_order_id, "")  # 清除订单ID
        self.assertEqual(context.entry_price, 100.0)  # 设置成交价格
        self.assertIsNotNone(context.entry_time)  # 设置成交时间
        
        # 验证状态更新
        self.strategy.update_context_state.assert_called_with("2330", StrategyState.HOLDING)
        
        # 验证发送出场订单
        self.strategy._manage_exit_order.assert_called_once_with("2330", context.bb_levels)
        
        # 验证日志记录
        log_calls = [call[0][0] for call in self.strategy.write_log.call_args_list]
        self.assertTrue(any("入场订单成交" in call and "Long" in call for call in log_calls))
    
    def test_on_order_entry_filled_short(self):
        """测试空头入场订单成交处理"""
        context = self.strategy.get_hft_context("2330")
        context.entry_order_id = "ENTRY_ORDER_123"
        context.bb_levels = {
            'upper': 101.0,
            'lower': 99.0,
            'middle': 100.0,
            'exit_long': 100.5,
            'exit_short': 99.5,
            'std': 1.0
        }
        
        order = OrderData(
            symbol="2330",
            exchange=Exchange.TSE,
            orderid="ENTRY_ORDER_123",
            direction=Direction.SHORT,
            offset=Offset.OPEN,
            price=100.0,
            volume=100,
            status=Status.ALLTRADED,
            datetime=datetime.now(),
            gateway_name="test"
        )
        
        event = Mock(data=order)
        
        # Mock _manage_exit_order方法
        self.strategy._manage_exit_order = Mock()
        
        # 调用on_order
        self.strategy.on_order(event)
        
        # 验证context更新
        self.assertEqual(context.position, -100)  # 空头持仓
        self.assertEqual(context.entry_order_id, "")  # 清除订单ID
        self.assertEqual(context.entry_price, 100.0)  # 设置成交价格
        self.assertIsNotNone(context.entry_time)  # 设置成交时间
        
        # 验证状态更新
        self.strategy.update_context_state.assert_called_with("2330", StrategyState.HOLDING)
        
        # 验证发送出场订单
        self.strategy._manage_exit_order.assert_called_once_with("2330", context.bb_levels)
        
        # 验证日志记录
        log_calls = [call[0][0] for call in self.strategy.write_log.call_args_list]
        self.assertTrue(any("入场订单成交" in call and "Short" in call for call in log_calls))
    
    def test_on_order_entry_filled_no_bb_levels(self):
        """测试入场订单成交但没有BB水平数据的情况"""
        context = self.strategy.get_hft_context("2330")
        context.entry_order_id = "ENTRY_ORDER_123"
        context.bb_levels = None  # 没有BB水平数据
        
        order = OrderData(
            symbol="2330",
            exchange=Exchange.TSE,
            orderid="ENTRY_ORDER_123",
            direction=Direction.LONG,
            offset=Offset.OPEN,
            price=100.0,
            volume=100,
            status=Status.ALLTRADED,
            datetime=datetime.now(),
            gateway_name="test"
        )
        
        event = Mock(data=order)
        
        # Mock _manage_exit_order方法
        self.strategy._manage_exit_order = Mock()
        
        # 调用on_order
        self.strategy.on_order(event)
        
        # 验证context更新
        self.assertEqual(context.position, 100)
        self.assertEqual(context.entry_order_id, "")
        
        # 验证没有发送出场订单
        self.strategy._manage_exit_order.assert_not_called()
        
        # 验证警告日志
        log_calls = [call[0][0] for call in self.strategy.write_log.call_args_list]
        self.assertTrue(any("没有BB水平数据" in call for call in log_calls))
    
    def test_on_order_exit_filled(self):
        """测试出场订单成交处理"""
        context = self.strategy.get_hft_context("2330")
        context.exit_order_id = "EXIT_ORDER_456"
        context.position = 100  # 有持仓
        context.trade_count = 0
        
        order = OrderData(
            symbol="2330",
            exchange=Exchange.TSE,
            orderid="EXIT_ORDER_456",
            direction=Direction.SHORT,
            offset=Offset.CLOSE,
            price=100.5,
            volume=100,
            status=Status.ALLTRADED,
            datetime=datetime.now(),
            gateway_name="test"
        )
        
        event = Mock(data=order)
        
        # 调用on_order
        self.strategy.on_order(event)
        
        # 验证context更新
        self.assertEqual(context.position, 0)  # 清除持仓
        self.assertEqual(context.exit_order_id, "")  # 清除订单ID
        self.assertEqual(context.exit_price, 100.5)  # 设置成交价格
        self.assertEqual(context.trade_count, 1)  # 增加交易次数
        
        # 验证状态更新
        self.strategy.update_context_state.assert_called_with("2330", StrategyState.IDLE)
        
        # 验证日志记录
        log_calls = [call[0][0] for call in self.strategy.write_log.call_args_list]
        self.assertTrue(any("出场订单成交" in call and "Short" in call for call in log_calls))
    
    def test_on_order_unknown_order_id(self):
        """测试未知订单ID的处理"""
        order = OrderData(
            symbol="2330",
            exchange=Exchange.TSE,
            orderid="UNKNOWN_ORDER",
            direction=Direction.LONG,
            offset=Offset.OPEN,
            price=100.0,
            volume=100,
            status=Status.ALLTRADED,
            datetime=datetime.now(),
            gateway_name="test"
        )
        
        event = Mock(data=order)
        
        # 调用on_order
        self.strategy.on_order(event)
        
        # 验证没有调用任何处理方法
        self.strategy.update_context_state.assert_not_called()
        
        # 验证警告日志
        log_calls = [call[0][0] for call in self.strategy.write_log.call_args_list]
        self.assertTrue(any("未找到订单ID" in call for call in log_calls))
    
    def test_on_order_mismatched_order_id(self):
        """测试订单ID不匹配的情况"""
        # 这个测试实际上和test_on_order_unknown_order_id是重复的
        # 因为我们的逻辑中，如果订单ID不在任何context中，就会记录"未找到订单ID"
        # 如果订单ID在context中但不匹配entry_order_id或exit_order_id，这种情况不会发生
        # 因为_find_hft_context_by_order_id只会返回匹配的context
        
        # 让我们测试一个更实际的情况：订单ID存在但context为空
        context = self.strategy.get_hft_context("2330")
        context.entry_order_id = ""  # 空字符串
        context.exit_order_id = ""   # 空字符串
        
        order = OrderData(
            symbol="2330",
            exchange=Exchange.TSE,
            orderid="SOME_ORDER_ID",
            direction=Direction.LONG,
            offset=Offset.OPEN,
            price=100.0,
            volume=100,
            status=Status.ALLTRADED,
            datetime=datetime.now(),
            gateway_name="test"
        )
        
        event = Mock(data=order)
        
        # 调用on_order
        self.strategy.on_order(event)
        
        # 验证没有调用任何处理方法
        self.strategy.update_context_state.assert_not_called()
        
        # 验证警告日志
        log_calls = [call[0][0] for call in self.strategy.write_log.call_args_list]
        self.assertTrue(any("未找到订单ID" in call for call in log_calls))


if __name__ == '__main__':
    unittest.main()
