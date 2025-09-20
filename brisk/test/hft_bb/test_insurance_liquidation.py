#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from unittest.mock import Mock, patch
from datetime import datetime, time

from brisk.hft_bb_reversal_strategy import HFTBBReversalStrategy
from vnpy.trader.constant import Direction, Offset, OrderType


class TestInsuranceLiquidation(unittest.TestCase):
    """测试保险平仓功能"""
    
    def setUp(self):
        """设置测试环境"""
        self.strategy = HFTBBReversalStrategy()
        self.strategy.write_log = Mock()
        self.strategy.gateway = Mock()
        self.strategy._execute_order = Mock(return_value="test_order_123")
        
    def test_insurance_liquidation_with_uncovered_positions(self):
        """测试有未覆盖持仓时的保险平仓"""
        # Mock gateway.get_positions 返回有未覆盖持仓的数据
        mock_positions = [
            {
                "Symbol": "9984",
                "LeavesQty": 100,  # 总持有数量
                "HoldQty": 50,     # 被平仓订单锁定的数量
                "Side": "2"        # 多头持仓
            },
            {
                "Symbol": "6098", 
                "LeavesQty": 200,  # 总持有数量
                "HoldQty": 200,    # 被平仓订单锁定的数量（完全锁定）
                "Side": "1"        # 空头持仓
            },
            {
                "Symbol": "2330",
                "LeavesQty": 150,  # 总持有数量
                "HoldQty": 0,      # 没有被平仓订单锁定
                "Side": "1"        # 空头持仓
            }
        ]
        
        self.strategy.gateway.get_positions.return_value = mock_positions
        
        # 执行保险平仓
        self.strategy._execute_market_close_liquidation()
        
        # 验证调用了 get_positions
        self.strategy.gateway.get_positions.assert_called_once()
        
        # 验证为未覆盖的持仓发送了平仓订单
        # 9984: 100 - 50 = 50股未覆盖，多头持仓需要卖空平仓
        # 2330: 150 - 0 = 150股未覆盖，空头持仓需要买多平仓
        expected_calls = [
            # 9984 的平仓订单
            unittest.mock.call(
                context=unittest.mock.ANY,
                bar=None,
                price=0,
                direction=Direction.SHORT,
                offset=Offset.CLOSE,
                order_type=OrderType.MARKET,
                reference_prefix="insurance_liquidation",
                quantity=50
            ),
            # 2330 的平仓订单
            unittest.mock.call(
                context=unittest.mock.ANY,
                bar=None,
                price=0,
                direction=Direction.LONG,
                offset=Offset.CLOSE,
                order_type=OrderType.MARKET,
                reference_prefix="insurance_liquidation",
                quantity=150
            )
        ]
        
        # 验证 _execute_order 被调用了2次（9984和2330）
        self.assertEqual(self.strategy._execute_order.call_count, 2)
        
        # 验证日志输出
        self.strategy.write_log.assert_any_call("开始执行保险平仓检查...")
        # 检查是否包含成功发送订单的日志（使用更宽松的匹配）
        success_logs = [call for call in self.strategy.write_log.call_args_list 
                       if "保险平仓订单发送成功" in str(call)]
        self.assertEqual(len(success_logs), 2)
        
    def test_insurance_liquidation_no_uncovered_positions(self):
        """测试没有未覆盖持仓时的保险平仓"""
        # Mock gateway.get_positions 返回没有未覆盖持仓的数据
        mock_positions = [
            {
                "Symbol": "9984",
                "LeavesQty": 100,  # 总持有数量
                "HoldQty": 100,    # 被平仓订单锁定的数量（完全锁定）
                "Side": "2"        # 多头持仓
            }
        ]
        
        self.strategy.gateway.get_positions.return_value = mock_positions
        
        # 执行保险平仓
        self.strategy._execute_market_close_liquidation()
        
        # 验证调用了 get_positions
        self.strategy.gateway.get_positions.assert_called_once()
        
        # 验证没有发送平仓订单
        self.strategy._execute_order.assert_not_called()
        
        # 验证日志输出
        self.strategy.write_log.assert_any_call("开始执行保险平仓检查...")
        
    def test_insurance_liquidation_get_positions_failure(self):
        """测试获取持仓数据失败时的保险平仓"""
        # Mock gateway.get_positions 返回空列表
        self.strategy.gateway.get_positions.return_value = []
        
        # 执行保险平仓
        self.strategy._execute_market_close_liquidation()
        
        # 验证调用了 get_positions
        self.strategy.gateway.get_positions.assert_called_once()
        
        # 验证没有发送平仓订单
        self.strategy._execute_order.assert_not_called()
        
        # 验证日志输出
        self.strategy.write_log.assert_any_call("开始执行保险平仓检查...")
        self.strategy.write_log.assert_any_call("无法获取实际持仓数据，跳过保险平仓")
        
    def test_insurance_liquidation_exception_handling(self):
        """测试保险平仓异常处理"""
        # Mock gateway.get_positions 抛出异常
        self.strategy.gateway.get_positions.side_effect = Exception("网络错误")
        
        # 执行保险平仓
        self.strategy._execute_market_close_liquidation()
        
        # 验证调用了 get_positions
        self.strategy.gateway.get_positions.assert_called_once()
        
        # 验证没有发送平仓订单
        self.strategy._execute_order.assert_not_called()
        
        # 验证异常日志
        self.strategy.write_log.assert_any_call("开始执行保险平仓检查...")
        self.strategy.write_log.assert_any_call("保险平仓检查异常: 网络错误")


if __name__ == '__main__':
    unittest.main()
