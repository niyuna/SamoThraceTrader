#!/usr/bin/env python3
"""
测试StockConfigManager支持逗号分隔的股票代码功能
"""

import unittest
import tempfile
import os
import json
from datetime import time

# 添加brisk目录到路径
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from stock_config import StockConfigManager, StockConfig, TradingWindow


class TestStockConfigCommaSeparated(unittest.TestCase):
    """测试逗号分隔的股票代码功能"""
    
    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, 'test_config.json')
    
    def tearDown(self):
        """清理测试环境"""
        if os.path.exists(self.config_file):
            os.remove(self.config_file)
        os.rmdir(self.temp_dir)
    
    def test_single_symbol_config(self):
        """测试单个股票代码配置"""
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
                "exclude_minutes": ["12:00"]
            }
        }
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config_data, f)
        
        manager = StockConfigManager(self.config_file)
        
        # 测试单个股票配置
        config = manager.get_stock_config("999Z")
        self.assertIsNotNone(config)
        self.assertEqual(config.symbol, "999Z")
        self.assertEqual(config.bb_entry_std_multiplier, 2.5)
        self.assertEqual(config.bb_exit_std_multiplier, 1.8)
        self.assertEqual(len(config.trading_windows), 1)
        self.assertEqual(len(config.exclude_minutes), 1)
        
        # 测试不存在的股票
        self.assertIsNone(manager.get_stock_config("999X"))
    
    def test_comma_separated_symbols_config(self):
        """测试逗号分隔的多个股票代码配置"""
        config_data = {
            "999A,999B,999C": {
                "bb_entry_std_multiplier": 3.0,
                "bb_exit_std_multiplier": 2.0,
                "trading_windows": [
                    {
                        "start_time": "09:30",
                        "end_time": "11:30",
                        "allowed_directions": ["long"]
                    },
                    {
                        "start_time": "14:00",
                        "end_time": "15:25",
                        "allowed_directions": ["long", "short"]
                    }
                ],
                "exclude_minutes": ["12:00", "15:00"]
            }
        }
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config_data, f)
        
        manager = StockConfigManager(self.config_file)
        
        # 测试所有三个股票都有相同的配置
        for symbol in ["999A", "999B", "999C"]:
            config = manager.get_stock_config(symbol)
            self.assertIsNotNone(config, f"Config for {symbol} should exist")
            self.assertEqual(config.symbol, symbol)
            self.assertEqual(config.bb_entry_std_multiplier, 3.0)
            self.assertEqual(config.bb_exit_std_multiplier, 2.0)
            self.assertEqual(len(config.trading_windows), 2)
            self.assertEqual(len(config.exclude_minutes), 2)
            
            # 验证时间窗口
            self.assertEqual(config.trading_windows[0].start_time, time(9, 30))
            self.assertEqual(config.trading_windows[0].end_time, time(11, 30))
            self.assertEqual(config.trading_windows[0].allowed_directions, ["long"])
            
            self.assertEqual(config.trading_windows[1].start_time, time(14, 0))
            self.assertEqual(config.trading_windows[1].end_time, time(15, 25))
            self.assertEqual(config.trading_windows[1].allowed_directions, ["long", "short"])
            
            # 验证排除时间
            self.assertEqual(config.exclude_minutes, [time(12, 0), time(15, 0)])
    
    def test_mixed_single_and_comma_separated(self):
        """测试混合单个和逗号分隔的股票代码配置"""
        config_data = {
            "999X": {
                "bb_entry_std_multiplier": 1.5,
                "bb_exit_std_multiplier": 1.0,
                "trading_windows": [
                    {
                        "start_time": "09:30",
                        "end_time": "11:30",
                        "allowed_directions": ["long"]
                    }
                ],
                "exclude_minutes": []
            },
            "999Y,999Z": {
                "bb_entry_std_multiplier": 2.5,
                "bb_exit_std_multiplier": 2.0,
                "trading_windows": [
                    {
                        "start_time": "10:00",
                        "end_time": "15:00",
                        "allowed_directions": ["long", "short"]
                    }
                ],
                "exclude_minutes": ["12:00"]
            }
        }
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config_data, f)
        
        manager = StockConfigManager(self.config_file)
        
        # 测试单个股票配置
        config_x = manager.get_stock_config("999X")
        self.assertIsNotNone(config_x)
        self.assertEqual(config_x.bb_entry_std_multiplier, 1.5)
        self.assertEqual(len(config_x.trading_windows), 1)
        self.assertEqual(len(config_x.exclude_minutes), 0)
        
        # 测试逗号分隔的股票配置
        for symbol in ["999Y", "999Z"]:
            config = manager.get_stock_config(symbol)
            self.assertIsNotNone(config)
            self.assertEqual(config.bb_entry_std_multiplier, 2.5)
            self.assertEqual(len(config.trading_windows), 1)
            self.assertEqual(len(config.exclude_minutes), 1)
    
    def test_whitespace_handling(self):
        """测试空格处理"""
        config_data = {
            " 999A , 999B , 999C ": {
                "bb_entry_std_multiplier": 3.0,
                "bb_exit_std_multiplier": 2.0,
                "trading_windows": [],
                "exclude_minutes": []
            }
        }
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config_data, f)
        
        manager = StockConfigManager(self.config_file)
        
        # 测试空格被正确去除
        for symbol in ["999A", "999B", "999C"]:
            config = manager.get_stock_config(symbol)
            self.assertIsNotNone(config)
            self.assertEqual(config.symbol, symbol)
    
    def test_has_custom_config(self):
        """测试has_custom_config方法"""
        config_data = {
            "999A,999B": {
                "bb_entry_std_multiplier": 3.0,
                "bb_exit_std_multiplier": 2.0,
                "trading_windows": [],
                "exclude_minutes": []
            }
        }
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config_data, f)
        
        manager = StockConfigManager(self.config_file)
        
        # 测试逗号分隔的股票都有配置
        self.assertTrue(manager.has_custom_config("999A"))
        self.assertTrue(manager.has_custom_config("999B"))
        self.assertFalse(manager.has_custom_config("999C"))
    
    def test_empty_config_file(self):
        """测试空配置文件"""
        config_data = {}
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config_data, f)
        
        manager = StockConfigManager(self.config_file)
        
        # 测试空配置
        self.assertIsNone(manager.get_stock_config("999Z"))
        self.assertFalse(manager.has_custom_config("999Z"))


if __name__ == '__main__':
    unittest.main()
