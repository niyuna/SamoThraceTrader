"""
YAML 配置提供者测试
"""

import sys
import os
import unittest
import tempfile
import shutil
from datetime import datetime
from typing import Dict, Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from util.yaml_config_provider import YAMLConfigurationProvider
from util.strategy_config_manager import StrategyConfigManager


class TestYAMLConfigurationProvider(unittest.TestCase):
    """测试 YAML 配置提供者"""
    
    def setUp(self):
        """测试前准备"""
        # 创建临时测试目录
        self.test_config_dir = tempfile.mkdtemp()
        
        self.provider = YAMLConfigurationProvider(
            config_dir=self.test_config_dir,
            environment="test"
        )
    
    def test_strategy_class_to_filename(self):
        """测试策略类名到文件名的转换"""
        # 测试驼峰命名转换
        filename = self.provider._strategy_class_to_filename("VWAPFailureStrategy")
        assert filename == "vwap_failure_strategy.yaml"
        
        # 测试简单命名
        filename = self.provider._strategy_class_to_filename("SimpleStrategy")
        assert filename == "simple_strategy.yaml"
        
        # 测试连续大写字母
        filename = self.provider._strategy_class_to_filename("APIStrategy")
        assert filename == "api_strategy.yaml"
    
    def test_load_config_from_file(self):
        """测试从文件加载配置"""
        # 创建测试配置文件
        config_file = os.path.join(self.test_config_dir, "test_strategy.yaml")
        test_config = {
            "strategy_name": "TestStrategy",
            "params": {"test_param": "test_value"},
            "metadata": {"version": "1.0.0"}
        }
        
        import yaml
        with open(config_file, 'w') as f:
            yaml.dump(test_config, f)
        
        # 加载配置
        config = self.provider.get_strategy_config("TestStrategy")
        assert config["params"]["test_param"] == "test_value"
        assert config["metadata"]["version"] == "1.0.0"
    
    def test_missing_file_returns_default(self):
        """测试文件不存在时返回默认配置"""
        config = self.provider.get_strategy_config("NonExistentStrategy")
        assert "params" in config
        assert "metadata" in config
        assert config["metadata"]["environment"] == "test"
        assert config["metadata"]["is_valid"] == True
    
    def test_invalid_config_returns_default(self):
        """测试无效配置时返回默认配置"""
        # 创建无效的配置文件
        config_file = os.path.join(self.test_config_dir, "invalid_strategy.yaml")
        invalid_config = {
            "params": {"test_param": "test_value"}
            # 缺少 required fields
        }
        
        import yaml
        with open(config_file, 'w') as f:
            yaml.dump(invalid_config, f)
        
        # 应该返回默认配置
        config = self.provider.get_strategy_config("InvalidStrategy")
        assert "params" in config
        assert "metadata" in config
    
    def test_normalize_config_data(self):
        """测试配置数据标准化"""
        raw_config = {
            "strategy_name": "TestStrategy",
            "params": {"param1": "value1"},
            "metadata": {"description": "Test config"},
            "version": "2.0.0",
            "is_valid": True
        }
        
        normalized = self.provider._normalize_config_data(raw_config)
        
        # 验证标准化后的结构
        assert "params" in normalized
        assert "metadata" in normalized
        assert normalized["params"]["param1"] == "value1"
        assert normalized["metadata"]["description"] == "Test config"
        assert normalized["metadata"]["version"] == "2.0.0"
        assert normalized["metadata"]["environment"] == "test"
    
    def test_environment_override(self):
        """测试环境覆盖"""
        # 创建不同环境的配置
        provider_prod = YAMLConfigurationProvider(
            config_dir=self.test_config_dir,
            environment="production"
        )
        
        config = provider_prod.get_strategy_config("NonExistentStrategy")
        assert config["metadata"]["environment"] == "production"
    
    def tearDown(self):
        """测试后清理"""
        shutil.rmtree(self.test_config_dir)


class TestStrategyConfigManager(unittest.TestCase):
    """测试策略配置管理工具"""
    
    def setUp(self):
        """测试前准备"""
        # 创建临时测试目录
        self.test_config_dir = tempfile.mkdtemp()
        
        self.manager = StrategyConfigManager(
            config_dir=self.test_config_dir
        )
    
    def test_create_config_template(self):
        """测试创建配置模板"""
        filepath = self.manager.create_config_template("TestStrategy", "staging")
        
        # 验证文件已创建
        assert os.path.exists(filepath)
        
        # 验证文件内容
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert "TestStrategy" in content
        assert "staging" in content
        assert "strategy_name:" in content
        assert "params:" in content
        assert "metadata:" in content
    
    def test_validate_config(self):
        """测试配置验证"""
        # 创建有效配置
        filepath = self.manager.create_config_template("ValidStrategy")
        assert self.manager.validate_config("ValidStrategy")
        
        # 创建无效配置
        invalid_file = os.path.join(self.test_config_dir, "invalid_strategy.yaml")
        invalid_config = {
            "params": {"test": "value"}
            # 缺少 required fields
        }
        
        import yaml
        with open(invalid_file, 'w') as f:
            yaml.dump(invalid_config, f)
        
        # 应该验证失败
        assert not self.manager.validate_config("InvalidStrategy")
    
    def test_backup_config(self):
        """测试配置备份"""
        # 创建配置
        filepath = self.manager.create_config_template("BackupTest")
        
        # 备份配置
        backup_file = self.manager.backup_config("BackupTest")
        
        # 验证备份文件存在
        assert os.path.exists(backup_file)
        assert backup_file != filepath
        
        # 验证备份文件内容
        with open(backup_file, 'r', encoding='utf-8') as f:
            backup_content = f.read()
        
        with open(filepath, 'r', encoding='utf-8') as f:
            original_content = f.read()
        
        assert backup_content == original_content
    
    def test_list_configs(self):
        """测试列出配置文件"""
        # 创建多个配置
        self.manager.create_config_template("Strategy1")
        self.manager.create_config_template("Strategy2")
        
        # 列出配置
        configs = self.manager.list_configs()
        
        # 验证结果
        assert len(configs) == 2
        assert "strategy1.yaml" in configs
        assert "strategy2.yaml" in configs
    
    def test_get_config_info(self):
        """测试获取配置信息"""
        # 创建配置
        self.manager.create_config_template("InfoTest", "production")
        
        # 获取配置信息
        info = self.manager.get_config_info("InfoTest")
        
        # 验证信息
        assert "file_path" in info
        assert "file_size" in info
        assert "modified_time" in info
        assert info["strategy_name"] == "InfoTest"
        assert info["environment"] == "production"
        assert info["is_valid"] == True
    
    def test_backup_nonexistent_config(self):
        """测试备份不存在的配置"""
        with self.assertRaises(FileNotFoundError):
            self.manager.backup_config("NonExistentStrategy")
    
    def tearDown(self):
        """测试后清理"""
        shutil.rmtree(self.test_config_dir)


class TestYAMLConfigurationProviderIntegration(unittest.TestCase):
    """测试 YAML 配置提供者集成功能"""
    
    def setUp(self):
        """测试前准备"""
        # 创建临时测试目录
        self.test_config_dir = tempfile.mkdtemp()
        
        self.provider = YAMLConfigurationProvider(
            config_dir=self.test_config_dir,
            environment="production"
        )
        
        self.manager = StrategyConfigManager(
            config_dir=self.test_config_dir
        )
    
    def test_full_workflow(self):
        """测试完整工作流程"""
        # 1. 创建配置模板
        filepath = self.manager.create_config_template("WorkflowTest", "staging")
        
        # 2. 验证配置
        assert self.manager.validate_config("WorkflowTest")
        
        # 3. 通过 provider 获取配置
        config = self.provider.get_strategy_config("WorkflowTest")
        
        # 4. 验证配置结构
        assert "params" in config
        assert "metadata" in config
        assert config["metadata"]["environment"] == "staging"
        
        # 5. 备份配置
        backup_file = self.manager.backup_config("WorkflowTest")
        assert os.path.exists(backup_file)
    
    def test_config_update_workflow(self):
        """测试配置更新工作流程"""
        # 1. 创建初始配置
        self.manager.create_config_template("UpdateTest")
        
        # 2. 获取初始配置
        initial_config = self.provider.get_strategy_config("UpdateTest")
        initial_version = initial_config["metadata"]["version"]
        
        # 3. 手动更新配置文件
        config_file = os.path.join(self.test_config_dir, "update_test.yaml")
        updated_config = {
            "strategy_name": "UpdateTest",
            "environment": "production",
            "version": "2.0.0",
            "last_updated": datetime.now().isoformat(),
            "is_valid": True,
            "params": {
                "new_param": "new_value"
            },
            "metadata": {
                "description": "Updated config",
                "author": "trading_team"
            }
        }
        
        import yaml
        with open(config_file, 'w') as f:
            yaml.dump(updated_config, f)
        
        # 4. 获取更新后的配置
        updated_config_result = self.provider.get_strategy_config("UpdateTest")
        
        # 5. 验证更新
        assert updated_config_result["metadata"]["version"] == "2.0.0"
        assert updated_config_result["params"]["new_param"] == "new_value"
        assert updated_config_result["metadata"]["description"] == "Updated config"
    
    def tearDown(self):
        """测试后清理"""
        shutil.rmtree(self.test_config_dir)


def run_yaml_config_tests():
    """运行 YAML 配置系统测试"""
    # 运行所有测试
    test_classes = [
        TestYAMLConfigurationProvider,
        TestStrategyConfigManager,
        TestYAMLConfigurationProviderIntegration
    ]
    
    all_results = []
    for test_class in test_classes:
        print(f"\n=== 运行测试类: {test_class.__name__} ===")
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        result = unittest.TextTestRunner(verbosity=2).run(tests)
        all_results.append(result)
    
    # 汇总结果
    total_tests = sum(r.testsRun for r in all_results)
    total_failures = sum(len(r.failures) for r in all_results)
    total_errors = sum(len(r.errors) for r in all_results)
    
    print(f"\n=== YAML 配置系统测试汇总 ===")
    print(f"总测试数: {total_tests}")
    print(f"总失败数: {total_failures}")
    print(f"总错误数: {total_errors}")
    print(f"总成功率: {(total_tests - total_failures - total_errors) / total_tests:.2%}" if total_tests > 0 else "总成功率: 0.00%")
    
    return all_results


if __name__ == "__main__":
    run_yaml_config_tests() 