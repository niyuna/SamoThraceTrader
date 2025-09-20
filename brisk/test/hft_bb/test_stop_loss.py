#!/usr/bin/env python3
"""
测试止损功能
"""

import unittest
from unittest.mock import Mock, patch
from datetime import datetime, time
import sys
import os

# 添加brisk目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from hft_bb_reversal_strategy import HFTBBReversalStrategy, HFTBBStockContext, StopLossConfig
from vnpy.trader.constant import Direction, OrderType, Exchange
from vnpy.trader.object import BarData


class TestStopLoss(unittest.TestCase):
    """测试止损功能"""
    
    def setUp(self):
        """设置测试环境"""
        self.strategy = HFTBBReversalStrategy()
        self.strategy.write_log = Mock()
        self.strategy._execute_exit = Mock(return_value="test_order_123")
        
        # 创建测试用的context
        self.context = HFTBBStockContext(
            symbol="9984",
            position_size=100,
            position=100,  # 多头持仓
            entry_price=100.0
        )
        self.strategy.hft_contexts["9984"] = self.context
    
    def test_calculate_loss_percentage_long_position(self):
        """测试多头持仓的损失百分比计算"""
        # 测试盈利情况
        loss_pct = self.strategy._calculate_loss_percentage(self.context, 105.0)
        self.assertEqual(loss_pct, 0.0)  # 盈利时损失为0
        
        # 测试损失情况
        loss_pct = self.strategy._calculate_loss_percentage(self.context, 95.0)
        self.assertEqual(loss_pct, 0.05)  # 5%损失
        
        # 测试更大损失
        loss_pct = self.strategy._calculate_loss_percentage(self.context, 90.0)
        self.assertEqual(loss_pct, 0.10)  # 10%损失
    
    def test_calculate_loss_percentage_short_position(self):
        """测试空头持仓的损失百分比计算"""
        self.context.position = -100  # 空头持仓
        
        # 测试盈利情况
        loss_pct = self.strategy._calculate_loss_percentage(self.context, 95.0)
        self.assertEqual(loss_pct, 0.0)  # 盈利时损失为0
        
        # 测试损失情况
        loss_pct = self.strategy._calculate_loss_percentage(self.context, 105.0)
        self.assertEqual(loss_pct, 0.05)  # 5%损失
        
        # 测试更大损失
        loss_pct = self.strategy._calculate_loss_percentage(self.context, 110.0)
        self.assertEqual(loss_pct, 0.10)  # 10%损失
    
    def test_calculate_loss_percentage_no_position(self):
        """测试无持仓时的损失百分比计算"""
        self.context.position = 0
        loss_pct = self.strategy._calculate_loss_percentage(self.context, 95.0)
        self.assertEqual(loss_pct, 0.0)
    
    def test_calculate_loss_percentage_no_entry_price(self):
        """测试无入场价格时的损失百分比计算"""
        self.context.entry_price = 0
        loss_pct = self.strategy._calculate_loss_percentage(self.context, 95.0)
        self.assertEqual(loss_pct, 0.0)
    
    def test_get_time_period(self):
        """测试时间段判断"""
        # 早上时间段
        morning_time = time(10, 0)
        period = self.strategy._get_time_period(morning_time)
        self.assertEqual(period, "morning")
        
        # 中午时间段
        noon_time = time(12, 0)
        period = self.strategy._get_time_period(noon_time)
        self.assertEqual(period, "noon")
        
        # 下午时间段
        afternoon_time = time(14, 0)
        period = self.strategy._get_time_period(afternoon_time)
        self.assertEqual(period, "afternoon")
        
        # 默认时间段
        default_time = time(8, 0)
        period = self.strategy._get_time_period(default_time)
        self.assertEqual(period, "default")
    
    def test_get_stop_loss_config_morning(self):
        """测试获取早上时间段止损配置"""
        # 直接测试早上配置
        morning_config = self.strategy.stop_loss_by_time["morning"]
        self.assertEqual(morning_config.first_stage_threshold, 0.005)  # 早上更保守
        self.assertEqual(morning_config.second_stage_threshold, 0.0055)
        self.assertTrue(morning_config.enabled)
    
    def test_get_stop_loss_config_noon(self):
        """测试获取中午时间段止损配置"""
        # 直接测试中午配置
        noon_config = self.strategy.stop_loss_by_time["noon"]
        self.assertEqual(noon_config.first_stage_threshold, 0.006)  # 中午稍微宽松
        self.assertEqual(noon_config.second_stage_threshold, 0.0065)
        self.assertTrue(noon_config.enabled)
    
    def test_get_stop_loss_config_afternoon(self):
        """测试获取下午时间段止损配置"""
        # 直接测试下午配置
        afternoon_config = self.strategy.stop_loss_by_time["afternoon"]
        self.assertEqual(afternoon_config.first_stage_threshold, 0.005)  # 下午跟早上一样保守
        self.assertEqual(afternoon_config.second_stage_threshold, 0.0055)
        self.assertTrue(afternoon_config.enabled)
    
    def test_get_stop_loss_config_default(self):
        """测试获取默认止损配置"""
        # 直接测试默认配置
        default_config = self.strategy.default_stop_loss_config
        self.assertEqual(default_config.first_stage_threshold, 0.02)  # 默认配置
        self.assertEqual(default_config.second_stage_threshold, 0.05)
        self.assertTrue(default_config.enabled)
    
    def test_check_stop_loss_no_config(self):
        """测试无配置时不触发止损"""
        # 模拟个股配置为None，但全局配置被禁用
        self.strategy.stock_config_manager.get_stock_config = Mock(return_value=None)
        self.strategy.default_stop_loss_config.enabled = False
        # 同时禁用所有时间段配置
        for config in self.strategy.stop_loss_by_time.values():
            config.enabled = False
        
        stop_loss_price = self.strategy._check_stop_loss("9984", self.context, 95.0)
        self.assertIsNone(stop_loss_price)
    
    def test_check_stop_loss_disabled(self):
        """测试止损禁用时不触发"""
        # 创建禁用的配置
        disabled_config = StopLossConfig(0.02, 0.05, False)
        self.strategy.stock_config_manager.get_stock_config = Mock(return_value=Mock(stop_loss_config=disabled_config))
        
        stop_loss_price = self.strategy._check_stop_loss("9984", self.context, 95.0)
        self.assertIsNone(stop_loss_price)
    
    def test_check_stop_loss_first_stage(self):
        """测试第一阶段止损触发"""
        # 创建配置
        config = StopLossConfig(0.02, 0.05, True)
        self.strategy.stock_config_manager.get_stock_config = Mock(return_value=Mock(stop_loss_config=config))
        
        # 3%损失，应该触发第一阶段止损
        stop_loss_price = self.strategy._check_stop_loss("9984", self.context, 97.0)
        self.assertEqual(stop_loss_price, 97.0)
    
    def test_check_stop_loss_second_stage(self):
        """测试第二阶段止损触发"""
        # 创建配置
        config = StopLossConfig(0.02, 0.05, True)
        self.strategy.stock_config_manager.get_stock_config = Mock(return_value=Mock(stop_loss_config=config))
        
        # 6%损失，应该触发第二阶段止损
        stop_loss_price = self.strategy._check_stop_loss("9984", self.context, 94.0)
        self.assertEqual(stop_loss_price, 94.0)
    
    def test_is_second_stage_stop_loss(self):
        """测试第二阶段止损判断"""
        # 创建配置
        config = StopLossConfig(0.02, 0.05, True)
        self.strategy.stock_config_manager.get_stock_config = Mock(return_value=Mock(stop_loss_config=config))
        
        # 3%损失，不是第二阶段
        is_second = self.strategy._is_second_stage_stop_loss("9984", self.context, 97.0)
        self.assertFalse(is_second)
        
        # 6%损失，是第二阶段
        is_second = self.strategy._is_second_stage_stop_loss("9984", self.context, 94.0)
        self.assertTrue(is_second)
    
    def test_manage_exit_order_with_stop_loss(self):
        """测试带止损的出场订单管理"""
        # 创建BB水平数据
        bb_levels = {
            'middle': 97.0,  # BB中轨
            'exit_long': 98.0,  # 正常出场价格
            'exit_short': 92.0
        }
        
        # 创建bar数据
        bar = BarData(
            symbol="9984",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            interval="1m",
            volume=1000,
            open_price=100.0,
            high_price=101.0,
            low_price=94.0,
            close_price=95.0,  # 收盘价，5%损失
            gateway_name="test"
        )
        
        # 创建配置，3%损失触发止损
        config = StopLossConfig(0.03, 0.06, True)
        self.strategy.stock_config_manager.get_stock_config = Mock(return_value=Mock(stop_loss_config=config))
        
        # 调用_manage_exit_order
        self.strategy._manage_exit_order("9984", bb_levels, bar)
        
        # 验证_execute_exit被调用
        self.strategy._execute_exit.assert_called_once()
        
        # 验证日志记录
        self.strategy.write_log.assert_any_call("止损出场: 9984 第一阶段 损失5.00% 价格95.00")
    
    def test_manage_exit_order_without_stop_loss(self):
        """测试无止损的正常出场订单管理"""
        # 创建BB水平数据
        bb_levels = {
            'middle': 97.0,  # BB中轨
            'exit_long': 98.0,  # 正常出场价格
            'exit_short': 92.0
        }
        
        # 创建bar数据（无损失）
        bar = BarData(
            symbol="9984",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            interval="1m",
            volume=1000,
            open_price=100.0,
            high_price=102.0,
            low_price=99.0,
            close_price=101.0,  # 收盘价，1%盈利
            gateway_name="test"
        )
        
        # 创建配置
        config = StopLossConfig(0.03, 0.06, True)
        self.strategy.stock_config_manager.get_stock_config = Mock(return_value=Mock(stop_loss_config=config))
        
        # 调用_manage_exit_order
        self.strategy._manage_exit_order("9984", bb_levels, bar)
        
        # 验证_execute_exit被调用
        self.strategy._execute_exit.assert_called_once()
        
        # 验证日志记录
        self.strategy.write_log.assert_any_call("管理出场订单: 9984 多头持仓100，出场价格: 98.00")
    
    def test_manage_exit_order_no_bar_no_stop_loss(self):
        """测试没有bar时不执行止损"""
        # 创建BB水平数据
        bb_levels = {
            'middle': 95.0,  # BB中轨
            'exit_long': 98.0,  # 正常出场价格
            'exit_short': 92.0
        }
        
        # 创建配置，3%损失触发止损
        config = StopLossConfig(0.03, 0.06, True)
        self.strategy.stock_config_manager.get_stock_config = Mock(return_value=Mock(stop_loss_config=config))
        
        # 调用_manage_exit_order（不传递bar）
        self.strategy._manage_exit_order("9984", bb_levels, None)
        
        # 验证_execute_exit被调用
        self.strategy._execute_exit.assert_called_once()
        
        # 验证日志记录（应该使用正常出场价格，不是止损价格）
        self.strategy.write_log.assert_any_call("管理出场订单: 9984 多头持仓100，出场价格: 98.00")


if __name__ == '__main__':
    unittest.main()
