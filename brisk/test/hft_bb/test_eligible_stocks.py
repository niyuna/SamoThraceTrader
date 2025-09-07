"""
测试HFT BB策略的eligible stock功能
"""

import unittest
import sys
import os
from unittest.mock import Mock, patch
from datetime import datetime, time

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from hft_bb_reversal_strategy import HFTBBReversalStrategy, HFTBBStockContext, TriggerLevels
from intraday_strategy_base import StrategyState
from vnpy.trader.constant import Direction, Status, Offset, Exchange
from vnpy.trader.object import OrderData


class TestEligibleStocks(unittest.TestCase):
    """测试eligible stock功能"""
    
    def setUp(self):
        """设置测试环境"""
        self.strategy = HFTBBReversalStrategy(use_mock_gateway=True)
        self.strategy.write_log = Mock()
        self.strategy.create_hft_context("2330")
        self.strategy.create_hft_context("9984")
    
    def test_eligible_stocks_initialization(self):
        """测试eligible_stocks初始化"""
        # 验证eligible_stocks已初始化
        self.assertIsInstance(self.strategy.eligible_stocks, set)
        self.assertEqual(len(self.strategy.eligible_stocks), 0)
    
    def test_add_symbol_to_eligible_stocks(self):
        """测试add_symbol时添加到eligible_stocks"""
        # 清空eligible_stocks
        self.strategy.eligible_stocks.clear()
        
        # 添加股票
        self.strategy.add_symbol("2330")
        
        # 验证股票已添加到eligible_stocks
        self.assertIn("2330", self.strategy.eligible_stocks)
        
        # 验证日志记录
        log_calls = [call[0][0] for call in self.strategy.write_log.call_args_list]
        self.assertTrue(any("添加股票到eligible_stocks: 2330" in call for call in log_calls))
    
    def test_add_symbol_blacklisted_stock(self):
        """测试添加黑名单股票到eligible_stocks"""
        # 清空eligible_stocks
        self.strategy.eligible_stocks.clear()
        
        # 将股票添加到黑名单
        self.strategy.set_black_list(["2330"])
        
        # 添加股票
        self.strategy.add_symbol("2330")
        
        # 验证股票未添加到eligible_stocks
        self.assertNotIn("2330", self.strategy.eligible_stocks)
        
        # 验证日志记录
        log_calls = [call[0][0] for call in self.strategy.write_log.call_args_list]
        self.assertTrue(any("跳过黑名单股票: 2330" in call for call in log_calls))
    
    def test_get_eligible_stocks(self):
        """测试获取eligible_stocks列表"""
        # 添加一些股票
        self.strategy.eligible_stocks.add("2330")
        self.strategy.eligible_stocks.add("9984")
        
        # 获取列表
        eligible_stocks = self.strategy.get_eligible_stocks()
        
        # 验证返回的是副本
        self.assertIsInstance(eligible_stocks, set)
        self.assertEqual(eligible_stocks, {"2330", "9984"})
        self.assertIsNot(eligible_stocks, self.strategy.eligible_stocks)
    
    def test_is_eligible_stock(self):
        """测试检查股票是否在eligible_stocks中"""
        # 添加股票
        self.strategy.eligible_stocks.add("2330")
        
        # 测试存在的股票
        self.assertTrue(self.strategy.is_eligible_stock("2330"))
        
        # 测试不存在的股票
        self.assertFalse(self.strategy.is_eligible_stock("9984"))
    
    def test_remove_from_eligible_stocks(self):
        """测试从eligible_stocks中移除股票（使用base strategy方法）"""
        # 添加股票
        self.strategy.eligible_stocks.add("2330")
        self.strategy.eligible_stocks.add("9984")
        
        # 移除股票（使用base strategy方法）
        self.strategy.remove_from_eligible_stocks("2330")
        
        # 验证股票已移除
        self.assertNotIn("2330", self.strategy.eligible_stocks)
        self.assertIn("9984", self.strategy.eligible_stocks)
        
        # 验证日志记录
        log_calls = [call[0][0] for call in self.strategy.write_log.call_args_list]
        self.assertTrue(any("从eligible_stocks中移除股票: 2330" in call for call in log_calls))
    
    def test_remove_from_eligible_stocks_nonexistent(self):
        """测试移除不存在的股票（使用base strategy方法）"""
        # 清空eligible_stocks
        self.strategy.eligible_stocks.clear()
        
        # 尝试移除不存在的股票
        self.strategy.remove_from_eligible_stocks("2330")
        
        # 验证eligible_stocks仍然为空
        self.assertEqual(len(self.strategy.eligible_stocks), 0)
    
    def test_add_to_eligible_stocks_normal_stock(self):
        """测试添加正常股票到eligible_stocks（使用base strategy方法）"""
        # 清空eligible_stocks
        self.strategy.eligible_stocks.clear()
        
        # 添加股票（使用base strategy方法）
        self.strategy.add_to_eligible_stocks("2330")
        
        # 验证股票已添加
        self.assertIn("2330", self.strategy.eligible_stocks)
        
        # 验证日志记录
        log_calls = [call[0][0] for call in self.strategy.write_log.call_args_list]
        self.assertTrue(any("添加股票到eligible_stocks: 2330" in call for call in log_calls))
    
    def test_add_to_eligible_stocks_blacklisted_stock(self):
        """测试添加黑名单股票到eligible_stocks（使用base strategy方法）"""
        # 清空eligible_stocks
        self.strategy.eligible_stocks.clear()
        
        # 将股票添加到黑名单
        self.strategy.set_black_list(["2330"])
        
        # 尝试添加股票（使用base strategy方法）
        self.strategy.add_to_eligible_stocks("2330")
        
        # 验证股票未添加
        self.assertNotIn("2330", self.strategy.eligible_stocks)
        
        # 验证日志记录
        log_calls = [call[0][0] for call in self.strategy.write_log.call_args_list]
        self.assertTrue(any("跳过黑名单股票: 2330" in call for call in log_calls))
    
    def test_x_condition_with_eligible_stock(self):
        """测试X条件检查包含eligible stock验证"""
        # 添加股票到eligible_stocks
        self.strategy.eligible_stocks.add("2330")
        
        # 添加股票到策略并设置BB levels
        self.strategy.add_symbol("2330")
        context = self.strategy.get_hft_context("2330")
        context.bb_levels = {
            'std': 0.8,
            'middle': 1000.0,
            'upper': 1003.0,
            'lower': 997.0,
            'exit_long': 1001.0,
            'exit_short': 999.0
        }
        
        # 设置时间在交易窗口内
        test_time = datetime.now().replace(hour=9, minute=20, second=0, microsecond=0)
        
        # 测试X条件
        result = self.strategy.check_x_condition("2330", test_time)
        
        # 验证X条件通过
        self.assertTrue(result)
        
        # 验证日志记录
        log_calls = [call[0][0] for call in self.strategy.write_log.call_args_list]
        self.assertTrue(any("X条件检查通过: 2330" in call for call in log_calls))
    
    def test_x_condition_without_eligible_stock(self):
        """测试X条件检查不包含eligible stock的情况"""
        # 确保股票不在eligible_stocks中
        self.strategy.eligible_stocks.discard("2330")
        
        # 设置时间在交易窗口内
        test_time = datetime.now().replace(hour=9, minute=20, second=0, microsecond=0)
        
        # 测试X条件
        result = self.strategy.check_x_condition("2330", test_time)
        
        # 验证X条件失败
        self.assertFalse(result)
        
        # 验证日志记录
        log_calls = [call[0][0] for call in self.strategy.write_log.call_args_list]
        self.assertTrue(any("X条件检查失败: 2330 不在eligible_stocks中" in call for call in log_calls))
    
    def test_x_condition_disabled(self):
        """测试X条件禁用时的情况"""
        # 禁用X条件
        self.strategy.x_condition_enabled = False
        
        # 确保股票不在eligible_stocks中
        self.strategy.eligible_stocks.discard("2330")
        
        # 测试X条件
        result = self.strategy.check_x_condition("2330")
        
        # 验证X条件通过（因为已禁用）
        self.assertTrue(result)
    
    def test_black_list_integration(self):
        """测试black list与eligible_stocks的集成"""
        # 添加股票到eligible_stocks
        self.strategy.eligible_stocks.add("2330")
        self.strategy.eligible_stocks.add("9984")
        
        # 将股票添加到黑名单（使用增量更新方法）
        self.strategy._update_black_list_incrementally(["2330"])
        
        # 验证黑名单股票已从eligible_stocks中移除
        self.assertNotIn("2330", self.strategy.eligible_stocks)
        self.assertIn("9984", self.strategy.eligible_stocks)
        
        # 验证日志记录
        log_calls = [call[0][0] for call in self.strategy.write_log.call_args_list]
        self.assertTrue(any("从eligible_stocks中移除股票: 2330" in call for call in log_calls))
    
    def test_black_list_removal_integration(self):
        """测试从黑名单移除股票时重新添加到eligible_stocks"""
        # 先将股票添加到eligible_stocks
        self.strategy.eligible_stocks.add("2330")
        
        # 将股票添加到黑名单（使用增量更新方法）
        self.strategy._update_black_list_incrementally(["2330"])
        
        # 验证股票不在eligible_stocks中
        self.assertNotIn("2330", self.strategy.eligible_stocks)
        
        # 手动将股票重新添加到eligible_stocks（模拟从黑名单移除后的操作）
        self.strategy.eligible_stocks.add("2330")
        
        # 验证股票已重新添加到eligible_stocks
        self.assertIn("2330", self.strategy.eligible_stocks)
        
        # 验证日志记录
        log_calls = [call[0][0] for call in self.strategy.write_log.call_args_list]
        self.assertTrue(any("从eligible_stocks中移除股票: 2330" in call for call in log_calls))


if __name__ == '__main__':
    unittest.main()
