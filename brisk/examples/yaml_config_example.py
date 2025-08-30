#!/usr/bin/env python3
"""
YAML 配置系统使用示例
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from util.yaml_config_provider import YAMLConfigurationProvider
from util.strategy_config_manager import StrategyConfigManager
from util.dynamic_param_manager import DynamicParamManager


def demonstrate_config_management():
    """演示配置管理功能"""
    print("=== 配置管理演示 ===\n")
    
    # 创建配置管理器
    manager = StrategyConfigManager("config/strategies")
    
    # 列出现有配置
    print("现有配置文件:")
    configs = manager.list_configs()
    for config in configs:
        print(f"  - {config}")
    
    # 创建新策略的配置模板
    print("\n创建新策略配置模板...")
    new_config_path = manager.create_config_template("NewTradingStrategy", "staging")
    print(f"配置模板已创建: {new_config_path}")
    
    # 验证配置
    print("\n验证配置...")
    is_valid = manager.validate_config("NewTradingStrategy")
    print(f"配置验证结果: {'✓ 有效' if is_valid else '✗ 无效'}")
    
    # 获取配置信息
    print("\n获取配置信息...")
    info = manager.get_config_info("NewTradingStrategy")
    for key, value in info.items():
        print(f"  {key}: {value}")


def demonstrate_config_provider():
    """演示配置提供者功能"""
    print("\n=== 配置提供者演示 ===\n")
    
    # 创建配置提供者
    provider = YAMLConfigurationProvider("config/strategies", "production")
    
    # 获取 VWAPFailureStrategy 配置
    print("获取 VWAPFailureStrategy 配置...")
    config = provider.get_strategy_config("VWAPFailureStrategy")
    
    print("配置参数:")
    for key, value in config["params"].items():
        print(f"  {key}: {value}")
    
    print("\n配置元数据:")
    for key, value in config["metadata"].items():
        print(f"  {key}: {value}")


def demonstrate_dynamic_param_integration():
    """演示动态参数集成"""
    print("\n=== 动态参数集成演示 ===\n")
    
    # 创建配置提供者
    provider = YAMLConfigurationProvider("config/strategies", "production")
    
    # 创建一个模拟的策略对象
    class MockStrategy:
        def __init__(self, name):
            self.name = name
        
        @property
        def __class__(self):
            class MockClass:
                __name__ = self.name
            return MockClass()
        
        def write_log(self, msg):
            print(f"[LOG] {msg}")
    
    # 创建动态参数管理器
    mock_strategy = MockStrategy("VWAPFailureStrategy")
    manager = DynamicParamManager(mock_strategy, provider)
    
    # 获取配置
    print("获取动态配置...")
    config = manager.fetch_config()
    
    if config:
        print("✓ 配置获取成功")
        print(f"  版本: {config.version}")
        print(f"  最后更新: {config.last_updated}")
        print(f"  是否有效: {config.is_valid}")
        print(f"  是否过期: {config.is_expired}")
        
        print("\n配置参数:")
        for key, value in config.params.items():
            print(f"  {key}: {value}")
    else:
        print("✗ 配置获取失败")


def demonstrate_filename_conversion():
    """演示文件名转换功能"""
    print("\n=== 文件名转换演示 ===\n")
    
    provider = YAMLConfigurationProvider()
    
    test_cases = [
        "VWAPFailureStrategy",
        "SimpleStrategy", 
        "APIStrategy",
        "MyStrategy",
        "Strategy",
        "ComplexTradingStrategy",
        "RiskManagementStrategy"
    ]
    
    print("策略类名到文件名的转换:")
    for class_name in test_cases:
        filename = provider._strategy_class_to_filename(class_name)
        print(f"  {class_name} -> {filename}")


def main():
    """主函数"""
    print("YAML 配置系统使用示例\n")
    print("=" * 50)
    
    try:
        # 演示各种功能
        demonstrate_config_management()
        demonstrate_config_provider()
        demonstrate_dynamic_param_integration()
        demonstrate_filename_conversion()
        
        print("\n" + "=" * 50)
        print("所有演示完成！")
        
    except Exception as e:
        print(f"\n演示过程中出现错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main() 