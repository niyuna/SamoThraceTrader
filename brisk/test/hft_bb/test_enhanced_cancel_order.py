"""
测试增强的撤单功能
"""

import unittest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from hft_bb_reversal_strategy import HFTBBReversalStrategy, HFTBBStockContext, StrategyState
from vnpy.trader.object import OrderData
from vnpy.trader.constant import Status, Direction, Exchange, Offset


class TestEnhancedCancelOrder(unittest.TestCase):
    """测试增强的撤单功能"""
    
    def setUp(self):
        """设置测试环境"""
        self.strategy = HFTBBReversalStrategy(use_mock_gateway=True)
        # 设置mock gateway
        self.strategy.gateway = Mock()
        self.strategy.brisk_gateway = Mock()
        # Mock write_log方法
        self.strategy.write_log = Mock()
        # 创建测试用的HFT context
        self.strategy.create_hft_context("9984")
        self.context = self.strategy.get_hft_context("9984")
    
    def test_query_order_status_and_update_success(self):
        """测试查询订单状态成功的情况"""
        # 设置mock数据
        mock_order = OrderData(
            symbol="9984",
            exchange=Exchange.TSE,
            orderid="test_order_123",
            direction=Direction.LONG,
            offset=Offset.OPEN,
            price=100.0,
            volume=100,
            status=Status.ALLTRADED,
            gateway_name="BriskGateway"
        )
        self.strategy.brisk_gateway.query_single_order.return_value = mock_order
        
        # 调用方法
        result = self.strategy._query_order_status_and_update("test_order_123", "9984")
        
        # 验证结果
        self.assertTrue(result)
        self.strategy.brisk_gateway.query_single_order.assert_called_once_with("test_order_123")
        self.strategy.write_log.assert_called_with("查询订单状态成功: 9984 订单ID: test_order_123 状态: Status.ALLTRADED")
    
    def test_query_order_status_and_update_failure(self):
        """测试查询订单状态失败的情况"""
        # 设置mock数据
        self.strategy.brisk_gateway.query_single_order.return_value = None
        
        # 调用方法
        result = self.strategy._query_order_status_and_update("test_order_123", "9984")
        
        # 验证结果
        self.assertFalse(result)
        self.strategy.brisk_gateway.query_single_order.assert_called_once_with("test_order_123")
        self.strategy.write_log.assert_called_with("查询订单状态失败: 9984 订单ID: test_order_123")
    
    def test_query_order_status_and_update_exception(self):
        """测试查询订单状态异常的情况"""
        # 设置mock数据
        self.strategy.brisk_gateway.query_single_order.side_effect = Exception("Network error")
        
        # 调用方法
        result = self.strategy._query_order_status_and_update("test_order_123", "9984")
        
        # 验证结果
        self.assertFalse(result)
        self.strategy.brisk_gateway.query_single_order.assert_called_once_with("test_order_123")
        self.strategy.write_log.assert_called_with("查询订单状态异常: 9984 订单ID: test_order_123 错误: Network error")
    
    def test_query_order_status_and_update_no_gateway(self):
        """测试没有gateway的情况"""
        # 设置mock数据
        self.strategy.brisk_gateway = None
        
        # 调用方法
        result = self.strategy._query_order_status_and_update("test_order_123", "9984")
        
        # 验证结果
        self.assertFalse(result)
        # 由于brisk_gateway为None，无法调用query_single_order
    
    def test_query_order_status_and_update_empty_order_id(self):
        """测试空订单ID的情况"""
        # 调用方法
        result = self.strategy._query_order_status_and_update("", "9984")
        
        # 验证结果
        self.assertFalse(result)
        self.strategy.brisk_gateway.query_single_order.assert_not_called()
    
    def test_cancel_order_with_verification_success(self):
        """测试撤单成功的情况"""
        # Mock _cancel_order_safely方法
        with patch.object(self.strategy, '_cancel_order_safely', return_value=True) as mock_cancel:
            # 调用方法
            result = self.strategy._cancel_order_with_verification("test_order_123", "9984")
            
            # 验证结果
            self.assertTrue(result)
            mock_cancel.assert_called_once_with("test_order_123", "9984")
            self.strategy.write_log.assert_called_with("撤单成功: 9984 订单ID: test_order_123")
    
    def test_cancel_order_with_verification_failure_with_query_success(self):
        """测试撤单失败但查询成功的情况"""
        # Mock _cancel_order_safely方法
        with patch.object(self.strategy, '_cancel_order_safely', return_value=False) as mock_cancel:
            # Mock _query_order_status_and_update方法
            with patch.object(self.strategy, '_query_order_status_and_update', return_value=True) as mock_query:
                # 调用方法
                result = self.strategy._cancel_order_with_verification("test_order_123", "9984")
                
                # 验证结果
                self.assertFalse(result)
                mock_cancel.assert_called_once_with("test_order_123", "9984")
                mock_query.assert_called_once_with("test_order_123", "9984")
                self.strategy.write_log.assert_called_with("订单状态查询成功，等待on_order事件更新状态: 9984 订单ID: test_order_123")
    
    def test_cancel_order_with_verification_failure_with_query_failure(self):
        """测试撤单失败且查询也失败的情况"""
        # Mock _cancel_order_safely方法
        with patch.object(self.strategy, '_cancel_order_safely', return_value=False) as mock_cancel:
            # Mock _query_order_status_and_update方法
            with patch.object(self.strategy, '_query_order_status_and_update', return_value=False) as mock_query:
                # 调用方法
                result = self.strategy._cancel_order_with_verification("test_order_123", "9984")
                
                # 验证结果
                self.assertFalse(result)
                mock_cancel.assert_called_once_with("test_order_123", "9984")
                mock_query.assert_called_once_with("test_order_123", "9984")
                self.strategy.write_log.assert_called_with("订单状态查询失败: 9984 订单ID: test_order_123")
    
    def test_cancel_order_with_verification_empty_order_id(self):
        """测试空订单ID的情况"""
        # 重置write_log mock
        self.strategy.write_log.reset_mock()
        
        # 调用方法
        result = self.strategy._cancel_order_with_verification("", "9984")
        
        # 验证结果
        self.assertTrue(result)
        self.strategy.write_log.assert_not_called()
    
    def test_cancel_entry_order_success(self):
        """测试取消入场订单成功的情况"""
        # 设置context状态
        self.context.entry_order_id = "test_entry_123"
        self.context.entry_order_time = datetime.now()
        self.context.state = StrategyState.WAITING_ENTRY
        
        # 重置write_log mock
        self.strategy.write_log.reset_mock()
        
        # Mock _cancel_order_with_verification方法
        with patch.object(self.strategy, '_cancel_order_with_verification', return_value=True) as mock_cancel:
            # 调用方法
            self.strategy._cancel_entry_order("9984", self.context)
            
            # 验证结果
            mock_cancel.assert_called_once_with("test_entry_123", "9984")
            self.assertEqual(self.context.entry_order_id, "")
            self.assertIsNone(self.context.entry_order_time)
            self.assertEqual(self.context.state, StrategyState.IDLE)
            # 检查日志调用
            log_calls = [call[0][0] for call in self.strategy.write_log.call_args_list]
            self.assertIn("取消入场订单成功: 9984 订单ID: test_entry_123", log_calls)
            self.assertIn("Context state changed for 9984: waiting_entry -> idle", log_calls)
    
    def test_cancel_entry_order_failure(self):
        """测试取消入场订单失败的情况"""
        # 设置context状态
        self.context.entry_order_id = "test_entry_123"
        self.context.entry_order_time = datetime.now()
        self.context.state = StrategyState.WAITING_ENTRY
        
        # Mock _cancel_order_with_verification方法
        with patch.object(self.strategy, '_cancel_order_with_verification', return_value=False) as mock_cancel:
            # 调用方法
            self.strategy._cancel_entry_order("9984", self.context)
            
            # 验证结果
            mock_cancel.assert_called_once_with("test_entry_123", "9984")
            # 状态不应该被更新
            self.assertEqual(self.context.entry_order_id, "test_entry_123")
            self.assertIsNotNone(self.context.entry_order_time)
            self.assertEqual(self.context.state, StrategyState.WAITING_ENTRY)
            self.strategy.write_log.assert_called_with("取消入场订单失败，等待订单状态更新: 9984 订单ID: test_entry_123")
    
    def test_cancel_entry_order_no_order_id(self):
        """测试没有订单ID的情况"""
        # 设置context状态
        self.context.entry_order_id = ""
        self.context.state = StrategyState.IDLE
        
        # 重置write_log mock
        self.strategy.write_log.reset_mock()
        
        # 调用方法
        self.strategy._cancel_entry_order("9984", self.context)
        
        # 验证结果
        self.strategy.write_log.assert_not_called()


if __name__ == '__main__':
    unittest.main()
