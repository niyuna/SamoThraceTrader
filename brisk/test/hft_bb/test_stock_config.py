"""
测试个股配置功能
"""

import unittest
import sys
import os
import tempfile
import json
from unittest.mock import Mock, patch
from datetime import datetime, time

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from stock_config import StockConfig, TradingWindow, StockConfigManager
from hft_bb_reversal_strategy import HFTBBReversalStrategy


class TestStockConfig(unittest.TestCase):
    """测试个股配置类"""
    
    def test_trading_window_creation(self):
        """测试交易窗口创建"""
        window = TradingWindow(
            start_time=time(9, 30),
            end_time=time(11, 30),
            allowed_directions=['long', 'short']
        )
        self.assertEqual(window.start_time, time(9, 30))
        self.assertEqual(window.end_time, time(11, 30))
        self.assertEqual(window.allowed_directions, ['long', 'short'])
    
    def test_stock_config_creation(self):
        """测试个股配置创建"""
        config = StockConfig(
            symbol="9984",
            bb_entry_std_multiplier=2.5,
            bb_exit_std_multiplier=1.8,
            trading_windows=[
                TradingWindow(time(9, 30), time(11, 30), ['long', 'short'])
            ],
            exclude_minutes=[time(12, 0), time(15, 0)]
        )
        self.assertEqual(config.symbol, "9984")
        self.assertEqual(config.bb_entry_std_multiplier, 2.5)
        self.assertEqual(config.bb_exit_std_multiplier, 1.8)
        self.assertEqual(len(config.trading_windows), 1)
        self.assertEqual(len(config.exclude_minutes), 2)


class TestStockConfigManager(unittest.TestCase):
    """测试个股配置管理器"""
    
    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, "test_config.json")
    
    def tearDown(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_load_json_configs(self):
        """测试加载JSON配置文件"""
        config_data = {
            "999Z": {
                "bb_entry_std_multiplier": 2.5,
                "bb_exit_std_multiplier": 1.8,
                "trading_windows": [
                    {
                        "start_time": "09:30",
                        "end_time": "11:30",
                        "allowed_directions": ["long", "short"]
                    }
                ],
                "exclude_minutes": ["12:00", "15:00"]
            }
        }
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config_data, f)
        
        manager = StockConfigManager(self.config_file)
        
        # 测试获取配置
        config = manager.get_stock_config("999Z")
        self.assertIsNotNone(config)
        self.assertEqual(config.symbol, "999Z")
        self.assertEqual(config.bb_entry_std_multiplier, 2.5)
        self.assertEqual(config.bb_exit_std_multiplier, 1.8)
        self.assertEqual(len(config.trading_windows), 1)
        self.assertEqual(len(config.exclude_minutes), 2)
        
        # 测试不存在的股票
        config = manager.get_stock_config("9999")
        self.assertIsNone(config)
        
        # 测试是否有自定义配置
        self.assertTrue(manager.has_custom_config("999Z"))
        self.assertFalse(manager.has_custom_config("9999"))
    
    def test_load_nonexistent_config(self):
        """测试加载不存在的配置文件"""
        manager = StockConfigManager("nonexistent.json")
        self.assertEqual(len(manager.stock_configs), 0)
    
    def test_parse_time(self):
        """测试时间解析"""
        manager = StockConfigManager("dummy.json")
        self.assertEqual(manager._parse_time("09:30"), time(9, 30))
        self.assertEqual(manager._parse_time("15:00"), time(15, 0))


class TestStockConfigIntegration(unittest.TestCase):
    """测试个股配置与策略的集成"""
    
    def setUp(self):
        """设置测试环境"""
        self.strategy = HFTBBReversalStrategy(use_mock_gateway=True)
        self.symbol = "999Z"
        
        # 创建测试配置文件
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, "test_config.json")
        
        config_data = {
            "999Z": {
                "bb_entry_std_multiplier": 2.5,
                "bb_exit_std_multiplier": 1.8,
                "trading_windows": [
                    {
                        "start_time": "09:30",
                        "end_time": "11:30",
                        "allowed_directions": ["long", "short"]
                    },
                    {
                        "start_time": "13:00",
                        "end_time": "15:00",
                        "allowed_directions": ["long"]
                    }
                ],
                "exclude_minutes": ["12:00", "15:00"]
            }
        }
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config_data, f)
        
        # 替换配置管理器
        self.strategy.stock_config_manager = StockConfigManager(self.config_file)
    
    def tearDown(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_create_indicator_manager_with_config(self):
        """测试使用个股配置创建指标管理器"""
        # 创建指标管理器
        indicator_manager = self.strategy._create_indicator_manager(self.symbol)
        
        # 验证使用了自定义参数
        self.assertEqual(indicator_manager.entry_std_multiplier, 2.5)
        self.assertEqual(indicator_manager.exit_std_multiplier, 1.8)
    
    def test_create_indicator_manager_without_config(self):
        """测试没有个股配置时使用默认参数"""
        # 使用没有配置的股票
        indicator_manager = self.strategy._create_indicator_manager("9999")
        
        # 验证使用了默认参数
        self.assertEqual(indicator_manager.entry_std_multiplier, self.strategy.bb_entry_std_multiplier)
        self.assertEqual(indicator_manager.exit_std_multiplier, self.strategy.bb_exit_std_multiplier)
    
    @patch('hft_bb_reversal_strategy.datetime')
    def test_check_x_condition_with_custom_config(self, mock_datetime):
        """测试使用自定义配置的X条件检查"""
        # 设置模拟时间
        mock_datetime.now.return_value = datetime(2024, 1, 1, 10, 0)  # 10:00
        
        # 设置策略状态
        self.strategy.eligible_stocks.add(self.symbol)
        self.strategy.x_condition_enabled = True
        
        # 创建context
        context = self.strategy.create_hft_context(self.symbol)
        context.position = 0  # 无持仓
        
        # 测试X条件检查
        result = self.strategy.check_x_condition(self.symbol)
        
        # 验证结果（顺序可能不同）
        self.assertEqual(set(result), {'long', 'short'})
    
    @patch('hft_bb_reversal_strategy.datetime')
    def test_check_x_condition_exclude_minute(self, mock_datetime):
        """测试排除分钟功能"""
        # 设置模拟时间为排除的分钟
        mock_datetime.now.return_value = datetime(2024, 1, 1, 12, 0)  # 12:00
        
        # 设置策略状态
        self.strategy.eligible_stocks.add(self.symbol)
        self.strategy.x_condition_enabled = True
        
        # 创建context
        context = self.strategy.create_hft_context(self.symbol)
        context.position = 0  # 无持仓
        
        # 测试X条件检查
        result = self.strategy.check_x_condition(self.symbol)
        
        # 验证结果（应该被排除）
        self.assertEqual(result, [])
    
    @patch('hft_bb_reversal_strategy.datetime')
    def test_check_x_condition_outside_window(self, mock_datetime):
        """测试在交易窗口外的情况"""
        # 设置模拟时间在窗口外
        mock_datetime.now.return_value = datetime(2024, 1, 1, 12, 30)  # 12:30
        
        # 设置策略状态
        self.strategy.eligible_stocks.add(self.symbol)
        self.strategy.x_condition_enabled = True
        
        # 创建context
        context = self.strategy.create_hft_context(self.symbol)
        context.position = 0  # 无持仓
        
        # 测试X条件检查
        result = self.strategy.check_x_condition(self.symbol)
        
        # 验证结果（应该在窗口外）
        self.assertEqual(result, [])
    
    @patch('hft_bb_reversal_strategy.datetime')
    def test_check_x_condition_direction_restriction(self, mock_datetime):
        """测试方向限制功能"""
        # 设置模拟时间在只允许long的窗口内
        mock_datetime.now.return_value = datetime(2024, 1, 1, 14, 0)  # 14:00
        
        # 设置策略状态
        self.strategy.eligible_stocks.add(self.symbol)
        self.strategy.x_condition_enabled = True
        
        # 创建context
        context = self.strategy.create_hft_context(self.symbol)
        context.position = 0  # 无持仓
        
        # 测试X条件检查
        result = self.strategy.check_x_condition(self.symbol)
        
        # 验证结果（应该只允许long）
        self.assertEqual(result, ['long'])
    
    def test_check_x_condition_without_config(self):
        """测试没有个股配置时使用默认逻辑"""
        # 使用没有配置的股票
        symbol = "9999"
        self.strategy.eligible_stocks.add(symbol)
        self.strategy.x_condition_enabled = True
        
        # 创建context
        context = self.strategy.create_hft_context(symbol)
        context.position = 0  # 无持仓
        
        # 测试X条件检查（应该使用默认逻辑）
        with patch('hft_bb_reversal_strategy.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 1, 10, 0)  # 10:00
            
            result = self.strategy.check_x_condition(symbol)
            
            # 验证结果（应该使用默认逻辑）
            self.assertIsInstance(result, list)


if __name__ == '__main__':
    unittest.main()
