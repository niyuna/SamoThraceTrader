"""
测试position_size参数的使用
"""

import unittest
from unittest.mock import Mock, patch
from datetime import datetime, time
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from hft_bb_reversal_strategy import HFTBBReversalStrategy, HFTBBStockContext
from vnpy.trader.object import TickData
from vnpy.trader.constant import Exchange


class TestPositionSizeUsage(unittest.TestCase):
    """测试position_size参数的使用"""
    
    def setUp(self):
        """设置测试环境"""
        self.strategy = HFTBBReversalStrategy(use_mock_gateway=True)
        
        # 模拟gateway
        self.strategy.gateway = Mock()
        self.strategy.gateway.send_order = Mock()
        
        # 创建测试context
        self.context = HFTBBStockContext(symbol="TEST")
        self.context.position_size = 200  # 设置自定义position_size
        self.strategy.hft_contexts["TEST"] = self.context
        
        # 模拟BB水平
        self.context.bb_levels = {
            'upper': 105.0,
            'lower': 95.0,
            'middle': 100.0
        }
        self.context.can_trade = ['long', 'short']
    
    def test_position_size_in_entry_order(self):
        """测试入场订单使用position_size"""
        # 模拟tick数据
        tick = TickData(
            gateway_name="test",
            symbol="TEST",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            last_price=94.0,  # 触发下轨
            volume=1000,
            last_volume=100,
            bid_price_1=93.9,
            ask_price_1=94.1,
            bid_volume_1=100,
            ask_volume_1=100
        )
        
        # 创建模拟事件对象
        event = Mock()
        event.data = tick
        
        # 调用on_tick
        self.strategy.on_tick(event)
        
        # 验证订单数量使用了position_size
        if self.strategy.gateway.send_order.called:
            call_args = self.strategy.gateway.send_order.call_args
            order_req = call_args[0][0]
            self.assertEqual(order_req.volume, 200)  # 应该使用position_size
            self.assertEqual(order_req.symbol, "TEST")
    
    def test_position_size_in_cancel_and_reorder(self):
        """测试取消订单并重新下单时使用position_size"""
        # 设置现有订单
        self.context.entry_order_id = "test_order_123"
        self.context.entry_price = 100.0  # 与新的触发价格不同
        
        # 模拟tick数据
        tick = TickData(
            gateway_name="test",
            symbol="TEST",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            last_price=94.0,  # 触发下轨
            volume=1000,
            last_volume=100,
            bid_price_1=93.9,
            ask_price_1=94.1,
            bid_volume_1=100,
            ask_volume_1=100
        )
        
        # 创建模拟事件对象
        event = Mock()
        event.data = tick
        
        # 调用on_tick
        self.strategy.on_tick(event)
        
        # 验证新订单数量使用了position_size
        if self.strategy.gateway.send_order.called:
            call_args = self.strategy.gateway.send_order.call_args
            order_req = call_args[0][0]
            self.assertEqual(order_req.volume, 200)  # 应该使用position_size
    
    def test_different_position_sizes(self):
        """测试不同股票的position_size"""
        # 创建第二个context
        context2 = HFTBBStockContext(symbol="TEST2")
        context2.position_size = 500  # 不同的position_size
        context2.bb_levels = {
            'upper': 105.0,
            'lower': 95.0,
            'middle': 100.0
        }
        context2.can_trade = ['long', 'short']
        self.strategy.hft_contexts["TEST2"] = context2
        
        # 模拟两个tick
        tick1 = TickData(
            gateway_name="test",
            symbol="TEST",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            last_price=94.0,
            volume=1000,
            last_volume=100,
            bid_price_1=93.9,
            ask_price_1=94.1,
            bid_volume_1=100,
            ask_volume_1=100
        )
        
        tick2 = TickData(
            gateway_name="test",
            symbol="TEST2",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            last_price=94.0,
            volume=1000,
            last_volume=100,
            bid_price_1=93.9,
            ask_price_1=94.1,
            bid_volume_1=100,
            ask_volume_1=100
        )
        
        # 创建模拟事件对象
        event1 = Mock()
        event1.data = tick1
        event2 = Mock()
        event2.data = tick2
        
        # 调用on_tick
        self.strategy.on_tick(event1)
        self.strategy.on_tick(event2)
        
        # 验证不同股票的订单数量
        if self.strategy.gateway.send_order.call_count >= 2:
            calls = self.strategy.gateway.send_order.call_args_list
            
            # 找到TEST的订单
            test_order = None
            test2_order = None
            for call in calls:
                order_req = call[0][0]
                if order_req.symbol == "TEST":
                    test_order = order_req
                elif order_req.symbol == "TEST2":
                    test2_order = order_req
            
            if test_order:
                self.assertEqual(test_order.volume, 200)  # TEST的position_size
            if test2_order:
                self.assertEqual(test2_order.volume, 500)  # TEST2的position_size
    
    def test_position_size_default_value(self):
        """测试position_size的默认值"""
        # 创建新的context，不设置position_size
        context = HFTBBStockContext(symbol="DEFAULT")
        self.strategy.hft_contexts["DEFAULT"] = context
        
        # 验证默认值
        self.assertEqual(context.position_size, 100)  # 默认值应该是100


if __name__ == '__main__':
    unittest.main()
