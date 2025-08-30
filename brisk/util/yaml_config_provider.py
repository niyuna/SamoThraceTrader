"""
基于 YAML 文件的配置提供者
"""

import os
import yaml
from datetime import datetime
from typing import Dict, Any, Optional
from .dynamic_config import ConfigurationProvider


class YAMLConfigurationProvider(ConfigurationProvider):
    """基于 YAML 文件的配置提供者"""
    
    def __init__(self, config_dir: str = "config/strategies", 
                 environment: str = "production"):
        self.config_dir = config_dir
        self.environment = environment
    
    def get_strategy_config(self, strategy_class_name: str, 
                           last_check_time: Optional[datetime] = None) -> Dict[str, Any]:
        """从 YAML 文件获取策略配置"""
        try:
            # 构建配置文件路径
            config_file = self._get_config_file_path(strategy_class_name)
            
            # 检查文件是否存在
            if not os.path.exists(config_file):
                return self._get_default_config(strategy_class_name)
            
            # 从文件加载配置
            config_data = self._load_config_from_file(config_file)
            
            # 验证配置数据
            if self._validate_config_data(config_data):
                return self._normalize_config_data(config_data)
            else:
                return self._get_default_config(strategy_class_name)
                
        except Exception as e:
            # 异常情况下返回默认配置
            return self._get_default_config(strategy_class_name)
    
    def _get_config_file_path(self, strategy_class_name: str) -> str:
        """获取配置文件路径"""
        filename = self._strategy_class_to_filename(strategy_class_name)
        return os.path.join(self.config_dir, filename)
    
    def _strategy_class_to_filename(self, strategy_class_name: str) -> str:
        """将策略类名转换为文件名"""
        # VWAPFailureStrategy -> vwap_failure_strategy.yaml
        import re
        # 智能驼峰转换：处理连续大写字母的情况
        # 先找到所有大写字母序列的边界
        filename = re.sub(r'([a-z])([A-Z])', r'\1_\2', strategy_class_name)
        # 处理连续大写字母的情况（如 VWAP -> V_WAP）
        filename = re.sub(r'([A-Z])([A-Z][a-z])', r'\1_\2', filename)
        # 转小写
        filename = filename.lower()
        return f"{filename}.yaml"
    
    def _load_config_from_file(self, config_file: str) -> Dict[str, Any]:
        """从文件加载配置"""
        with open(config_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def _validate_config_data(self, config_data: Dict[str, Any]) -> bool:
        """验证配置数据"""
        required_fields = ["strategy_name", "params", "metadata"]
        return all(field in config_data for field in required_fields)
    
    def _normalize_config_data(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """标准化配置数据格式"""
        # 提取核心字段
        normalized = {
            "params": config_data.get("params", {}),
            "metadata": {
                "last_updated": config_data.get("last_updated", datetime.now().strftime('%Y-%m-%dT%H:%M:%S')),
                "version": config_data.get("version", "1.0.0"),
                "is_valid": config_data.get("is_valid", True),
                "environment": config_data.get("environment", self.environment),
                "description": config_data.get("metadata", {}).get("description", ""),
                "author": config_data.get("metadata", {}).get("author", "")
            }
        }
        
        return normalized
    
    def _get_default_config(self, strategy_class_name: str) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "params": {},
            "metadata": {
                "last_updated": datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
                "version": "1.0.0",
                "is_valid": True,
                "environment": self.environment
            }
        } 