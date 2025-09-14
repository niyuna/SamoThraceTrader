"""
测试entry价格变化时的订单逻辑
"""

import unittest
import sys
import os
from unittest.mock import Mock, patch, call
from datetime import datetime, time

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from hft_bb_reversal_strategy import HFTBBReversalStrategy
from vnpy.trader.object import TickData, OrderData
from vnpy.trader.constant import Exchange, Direction, Offset, Status
from intraday_strategy_base import StrategyState


class TestEntryPriceChangeLogic(unittest.TestCase):
    """测试entry价格变化时的订单逻辑"""
    
    def setUp(self):
        """设置测试环境"""
        self.strategy = HFTBBReversalStrategy()
        self.symbol = "9984"
        
        # 创建HFT context
        self.strategy.create_hft_context(self.symbol)
        context = self.strategy.get_hft_context(self.symbol)
        
        # 设置trigger levels
        from hft_bb_reversal_strategy import TriggerLevels
        context.trigger_levels = TriggerLevels(
            upper_trigger=100.5,
            upper_limit=100.0,
            lower_trigger=99.5,
            lower_limit=99.0
        )
        
        # 设置entry价格
        context.entry_price = 98.5  # 当前订单价格（与新的order_price不同）
        context.entry_order_id = "test_entry_123"
        context.entry_order_time = datetime.now()
        context.state = StrategyState.WAITING_ENTRY
        
        # Mock gateway
        self.strategy.gateway = Mock()
        self.strategy.gateway.send_order = Mock(return_value="new_order_456")
        
        # Mock _cancel_order_with_verification
        self.strategy._cancel_order_with_verification = Mock(return_value=True)
        
        # Mock write_log
        self.strategy.write_log = Mock()
    
    def test_price_change_cancels_and_places_new_order(self):
        """测试价格变化时取消旧订单并下新订单"""
        context = self.strategy.get_hft_context(self.symbol)
        
        # 设置订单时间为2分钟前，确保可以取消
        from datetime import timedelta
        context.entry_order_time = datetime.now() - timedelta(minutes=2)
        
        # 模拟价格变化：从99.0变为99.4，应该触发新的LONG订单
        tick = TickData(
            symbol=self.symbol,
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            name="Test Stock",
            volume=1000,
            turnover=100000,
            last_price=99.4,  # 价格在lower_trigger以下，应该触发LONG
            last_volume=100,
            limit_up=105.0,
            limit_down=95.0,
            open_price=99.0,
            high_price=99.5,
            low_price=98.8,
            pre_close=99.0,
            gateway_name="TEST"
        )
        
        # 调用_check_entry_logic
        self.strategy._check_entry_logic(self.symbol, tick, context)
        
        # 验证取消订单被调用
        self.strategy._cancel_order_with_verification.assert_called_once_with(
            "test_entry_123", self.symbol
        )
        
        # 验证新订单被发送
        self.strategy.gateway.send_order.assert_called_once()
        
        # 验证日志记录
        log_calls = [call[0][0] for call in self.strategy.write_log.call_args_list]
        self.assertIn("取消订单原因: 价格不同 当前:98.50 应该:99.00", log_calls)
        self.assertIn("价格变化，立即下新订单: 9984 Long 99.00", log_calls)
    
    def test_price_change_cancel_failure_no_new_order(self):
        """测试取消订单失败时不下新订单"""
        context = self.strategy.get_hft_context(self.symbol)
        
        # 设置订单时间为2分钟前，确保可以取消
        from datetime import timedelta
        context.entry_order_time = datetime.now() - timedelta(minutes=2)
        
        # Mock取消订单失败
        self.strategy._cancel_order_with_verification = Mock(return_value=False)
        
        # 模拟价格变化
        tick = TickData(
            symbol=self.symbol,
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            name="Test Stock",
            volume=1000,
            turnover=100000,
            last_price=99.4,
            last_volume=100,
            limit_up=105.0,
            limit_down=95.0,
            open_price=99.0,
            high_price=99.5,
            low_price=98.8,
            pre_close=99.0,
            gateway_name="TEST"
        )
        
        # 调用_check_entry_logic
        self.strategy._check_entry_logic(self.symbol, tick, context)
        
        # 验证取消订单被调用
        self.strategy._cancel_order_with_verification.assert_called_once_with(
            "test_entry_123", self.symbol
        )
        
        # 验证新订单没有被发送
        self.strategy.gateway.send_order.assert_not_called()
        
        # 验证日志记录
        log_calls = [call[0][0] for call in self.strategy.write_log.call_args_list]
        self.assertIn("取消入场订单失败，等待订单状态更新: 9984 订单ID: test_entry_123", log_calls)
    
    def test_price_in_trigger_range_cancels_without_new_order(self):
        """测试价格在触发区间内时取消订单但不下新订单"""
        context = self.strategy.get_hft_context(self.symbol)
        
        # 设置订单时间为2分钟前，确保可以取消
        from datetime import timedelta
        context.entry_order_time = datetime.now() - timedelta(minutes=2)
        
        # 模拟价格在触发区间内
        tick = TickData(
            symbol=self.symbol,
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            name="Test Stock",
            volume=1000,
            turnover=100000,
            last_price=99.8,  # 在99.5和100.5之间
            last_volume=100,
            limit_up=105.0,
            limit_down=95.0,
            open_price=99.0,
            high_price=100.0,
            low_price=99.5,
            pre_close=99.0,
            gateway_name="TEST"
        )
        
        # 调用_check_entry_logic
        self.strategy._check_entry_logic(self.symbol, tick, context)
        
        # 验证取消订单被调用
        self.strategy._cancel_order_with_verification.assert_called_once_with(
            "test_entry_123", self.symbol
        )
        
        # 验证新订单没有被发送
        self.strategy.gateway.send_order.assert_not_called()
        
        # 验证日志记录
        log_calls = [call[0][0] for call in self.strategy.write_log.call_args_list]
        self.assertIn("取消订单原因: 价格在触发区间内 99.80", log_calls)
    
    def test_same_minute_protection_prevents_cancellation(self):
        """测试同一分钟内不取消订单的保护机制"""
        context = self.strategy.get_hft_context(self.symbol)
        
        # 设置订单时间为当前时间（同一分钟内）
        context.entry_order_time = datetime.now()
        
        # 模拟价格变化
        tick = TickData(
            symbol=self.symbol,
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            name="Test Stock",
            volume=1000,
            turnover=100000,
            last_price=99.2,
            last_volume=100,
            limit_up=105.0,
            limit_down=95.0,
            open_price=99.0,
            high_price=99.5,
            low_price=98.8,
            pre_close=99.0,
            gateway_name="TEST"
        )
        
        # 调用_check_entry_logic
        self.strategy._check_entry_logic(self.symbol, tick, context)
        
        # 验证取消订单没有被调用
        self.strategy._cancel_order_with_verification.assert_not_called()
        
        # 验证新订单没有被发送
        self.strategy.gateway.send_order.assert_not_called()
        
        # 验证日志记录
        log_calls = [call[0][0] for call in self.strategy.write_log.call_args_list]
        self.assertIn("跳过取消订单: 9984 订单在同一分钟内发送，避免频繁撤单", log_calls)
    
    def test_upper_band_price_change(self):
        """测试上轨价格变化的情况"""
        context = self.strategy.get_hft_context(self.symbol)
        context.entry_price = 99.5  # 当前是LONG订单（与新的order_price不同）
        context.entry_order_id = "test_entry_123"
        from datetime import timedelta
        context.entry_order_time = datetime.now() - timedelta(minutes=2)  # 2分钟前
        
        # 模拟价格触发上轨
        tick = TickData(
            symbol=self.symbol,
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            name="Test Stock",
            volume=1000,
            turnover=100000,
            last_price=100.6,  # 触发上轨
            last_volume=100,
            limit_up=105.0,
            limit_down=95.0,
            open_price=100.0,
            high_price=101.0,
            low_price=99.5,
            pre_close=100.0,
            gateway_name="TEST"
        )
        
        # 调用_check_entry_logic
        self.strategy._check_entry_logic(self.symbol, tick, context)
        
        # 验证取消订单被调用
        self.strategy._cancel_order_with_verification.assert_called_once_with(
            "test_entry_123", self.symbol
        )
        
        # 验证新订单被发送（SHORT订单）
        self.strategy.gateway.send_order.assert_called_once()
        
        # 验证日志记录
        log_calls = [call[0][0] for call in self.strategy.write_log.call_args_list]
        self.assertIn("取消订单原因: 价格不同 当前:99.50 应该:100.00", log_calls)
        self.assertIn("价格变化，立即下新订单: 9984 Short 100.00", log_calls)


if __name__ == '__main__':
    unittest.main()
