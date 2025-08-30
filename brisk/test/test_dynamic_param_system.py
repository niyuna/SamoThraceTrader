"""
动态参数系统测试
测试策略参数的动态更新功能
"""

import sys
import os
import unittest
from datetime import datetime, timedelta
from typing import Dict, Any
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from common.dynamic_config import (
    ConfigurationProvider, MockConfigurationProvider, 
    StrategyConfig, BlackListUpdateParser
)
from common.dynamic_param_manager import DynamicParamManager
from vwap_failure_strategy import VWAPFailureStrategy
from intraday_strategy_base import StrategyState


class TestDynamicConfigSystem(unittest.TestCase):
    """测试动态配置系统基础功能"""
    
    def setUp(self):
        """测试前准备"""
        self.provider = MockConfigurationProvider()
    
    def test_basic_config_retrieval(self):
        """测试基本配置获取"""
        config = {
            "params": {"test_param": "test_value"},
            "metadata": {
                "last_updated": datetime.now().isoformat(),
                "version": "1.0.0",
                "is_valid": True
            }
        }
        
        self.provider.set_strategy_config("TestStrategy", config)
        retrieved = self.provider.get_strategy_config("TestStrategy")
        
        assert retrieved["params"]["test_param"] == "test_value"
        assert retrieved["metadata"]["version"] == "1.0.0"
    
    def test_black_list_update_parser(self):
        """测试黑名单增量更新解析器"""
        # 测试简单列表
        simple_list = ["9984", "7203"]
        result = BlackListUpdateParser.parse_update(simple_list)
        assert result['adds'] == ["9984", "7203"]
        assert result['removes'] == []
        
        # 测试增量操作
        incremental_ops = [
            {"operation": "add", "symbol": "6758"},
            {"operation": "remove", "symbol": "9984"}
        ]
        result = BlackListUpdateParser.parse_update(incremental_ops)
        assert result['adds'] == ["6758"]
        assert result['removes'] == ["9984"]
        
        # 测试混合格式
        mixed_format = ["9984", {"operation": "remove", "symbol": "7203"}]
        result = BlackListUpdateParser.parse_update(mixed_format)
        assert result['adds'] == ["9984"]
        assert result['removes'] == ["7203"]
    
    def test_strategy_config_validation(self):
        """测试策略配置验证"""
        # 测试有效配置
        valid_config = StrategyConfig(
            params={"param1": "value1"},
            metadata={"version": "1.0"},
            last_updated=datetime.now(),
            is_valid=True
        )
        assert not valid_config.is_expired()
        
        # 测试过期配置
        expired_config = StrategyConfig(
            params={"param1": "value1"},
            metadata={"version": "1.0"},
            last_updated=datetime.now() - timedelta(hours=9),
            is_valid=True
        )
        assert expired_config.is_expired()
        
        # 测试无效配置
        invalid_config = StrategyConfig(
            params={"param1": "value1"},
            metadata={"version": "1.0"},
            last_updated=datetime.now(),
            is_valid=False
        )
        assert not invalid_config.is_expired()  # 过期检查不依赖is_valid


class TestDynamicParamManager(unittest.TestCase):
    """测试动态参数管理器"""
    
    def setUp(self):
        """测试前准备"""
        self.provider = MockConfigurationProvider()
        self.strategy = VWAPFailureStrategy(use_mock_gateway=True)
        self.manager = DynamicParamManager(self.strategy, self.provider)
    
    def test_should_check_config(self):
        """测试配置检查时机判断"""
        # 初始状态应该检查
        assert self.manager.should_check_config()
        
        # 设置检查间隔
        self.manager.check_interval = 1  # 1秒
        
        # 刚检查过，不应该再次检查
        self.manager.last_check_time = datetime.now()
        assert not self.manager.should_check_config()
        
        # 等待超过间隔时间后应该检查
        time.sleep(1.1)
        assert self.manager.should_check_config()
    
    def test_fetch_config_success(self):
        """测试成功获取配置"""
        config_data = {
            "params": {"gap_up_threshold": 0.03},
            "metadata": {
                "last_updated": datetime.now().isoformat(),
                "version": "1.0.0",
                "is_valid": True
            }
        }
        
        self.provider.set_strategy_config("VWAPFailureStrategy", config_data)
        config = self.manager.fetch_config()
        
        assert config is not None
        assert config.params["gap_up_threshold"] == 0.03
        assert config.metadata["version"] == "1.0.0"
    
    def test_fetch_config_invalid(self):
        """测试获取无效配置"""
        # 设置无效配置
        invalid_config = {
            "params": {"gap_up_threshold": 0.03},
            "metadata": {
                "last_updated": datetime.now().isoformat(),
                "version": "1.0.0",
                "is_valid": False
            }
        }
        
        self.provider.set_strategy_config("VWAPFailureStrategy", invalid_config)
        config = self.manager.fetch_config()
        
        # 应该返回None（被验证过滤）
        assert config is None
    
    def test_fetch_config_expired(self):
        """测试获取过期配置"""
        # 设置过期配置
        expired_config = {
            "params": {"gap_up_threshold": 0.03},
            "metadata": {
                "last_updated": (datetime.now() - timedelta(hours=25)).isoformat(),
                "version": "1.0.0",
                "is_valid": True
            }
        }
        
        self.provider.set_strategy_config("VWAPFailureStrategy", expired_config)
        config = self.manager.fetch_config()
        
        # 应该返回None（被过期检查过滤）
        assert config is None


class TestDynamicParamSystem(unittest.TestCase):
    """测试动态参数系统集成功能"""
    
    def setUp(self):
        """测试前准备"""
        # 创建策略实例
        self.strategy = VWAPFailureStrategy(use_mock_gateway=True)
        
        # 初始化event_engine以便定时器能够工作
        from vnpy.event import EventEngine
        from vnpy.trader.engine import MainEngine
        self.strategy.event_engine = EventEngine()
        self.strategy.main_engine = MainEngine(self.strategy.event_engine)
        
        # 创建Mock配置提供者
        self.mock_provider = MockConfigurationProvider()
        self.strategy.set_configuration_provider(self.mock_provider)
        
        # 设置较短的检查间隔以便测试
        self.strategy.set_config_check_interval(1)  # 1秒检查一次
        
        # 等待定时器注册
        time.sleep(0.1)
    
    def test_basic_dynamic_param_update(self):
        """测试基本动态参数更新"""
        # 设置初始参数
        initial_threshold = self.strategy.gap_up_threshold
        
        # 设置新的配置
        self.mock_provider.set_strategy_config("VWAPFailureStrategy", {
            "params": {
                "gap_up_threshold": 0.03,  # 从0.02更新到0.03
                "black_list": ["9984"]
            },
            "metadata": {
                "last_updated": datetime.now().isoformat(),
                "version": "1.0.0",
                "is_valid": True
            }
        })
        
        # 等待定时器触发
        time.sleep(2)
        
        # 验证参数更新
        assert self.strategy.gap_up_threshold == 0.03, f"参数应该更新: 期望0.03, 实际{self.strategy.gap_up_threshold}"
        assert "9984" in self.strategy.black_list, "黑名单应该包含9984"
        
        print("✅ 基本动态参数更新测试通过")
    
    def test_incremental_black_list_update(self):
        """测试增量黑名单更新"""
        # 设置初始黑名单
        self.strategy.black_list = ["9984", "7203"]
        
        # 测试增量更新：添加新股票，移除现有股票
        self.mock_provider.set_strategy_config("VWAPFailureStrategy", {
            "params": {
                "black_list": [
                    {"operation": "add", "symbol": "6758"},
                    {"operation": "remove", "symbol": "9984"}
                ]
            },
            "metadata": {
                "last_updated": datetime.now().isoformat(),
                "version": "1.0.0",
                "is_valid": True
            }
        })
        
        # 等待定时器触发
        time.sleep(2)
        
        # 验证黑名单更新
        assert "6758" in self.strategy.black_list, "应该添加6758"
        assert "9984" not in self.strategy.black_list, "应该移除9984"
        assert "7203" in self.strategy.black_list, "7203应该保持不变"
        
        print("✅ 增量黑名单更新测试通过")
    
    def test_strategy_specific_param_update(self):
        """测试策略特定参数更新"""
        # 设置初始参数
        initial_entry_factor = self.strategy.entry_factor_gap_up
        initial_exit_factor = self.strategy.exit_factor_gap_up
        
        # 更新策略特定参数
        self.mock_provider.set_strategy_config("VWAPFailureStrategy", {
            "params": {
                "entry_factor_gap_up": 2.0,
                "exit_factor_gap_up": 1.2
            },
            "metadata": {
                "last_updated": datetime.now().isoformat(),
                "version": "1.0.0",
                "is_valid": True
            }
        })
        
        # 等待定时器触发
        time.sleep(2)
        
        # 验证参数更新
        assert self.strategy.entry_factor_gap_up == 2.0, f"entry_factor应该更新: 期望2.0, 实际{self.strategy.entry_factor_gap_up}"
        assert self.strategy.exit_factor_gap_up == 1.2, f"exit_factor应该更新: 期望1.2, 实际{self.strategy.exit_factor_gap_up}"
        
        print("✅ 策略特定参数更新测试通过")


def run_dynamic_param_tests():
    """运行动态参数系统测试"""
    # 运行基础功能测试
    print("\n=== 运行基础功能测试 ===")
    basic_tests = unittest.TestLoader().loadTestsFromTestCase(TestDynamicConfigSystem)
    basic_result = unittest.TextTestRunner(verbosity=2).run(basic_tests)
    
    # 运行参数管理器测试
    print("\n=== 运行参数管理器测试 ===")
    manager_tests = unittest.TestLoader().loadTestsFromTestCase(TestDynamicParamManager)
    manager_result = unittest.TextTestRunner(verbosity=2).run(manager_tests)
    
    # 运行集成测试
    print("\n=== 运行集成测试 ===")
    integration_tests = unittest.TestLoader().loadTestsFromTestCase(TestDynamicParamSystem)
    integration_result = unittest.TextTestRunner(verbosity=2).run(integration_tests)
    
    # 汇总结果
    total_tests = basic_result.testsRun + manager_result.testsRun + integration_result.testsRun
    total_failures = len(basic_result.failures) + len(manager_result.failures) + len(integration_result.failures)
    total_errors = len(basic_result.errors) + len(manager_result.errors) + len(integration_result.errors)
    
    print(f"\n=== 动态参数系统测试汇总 ===")
    print(f"总测试数: {total_tests}")
    print(f"总失败数: {total_failures}")
    print(f"总错误数: {total_errors}")
    print(f"总成功率: {(total_tests - total_failures - total_errors) / total_tests:.2%}" if total_tests > 0 else "总成功率: 0.00%")
    
    return [basic_result, manager_result, integration_result]


if __name__ == "__main__":
    run_dynamic_param_tests() 