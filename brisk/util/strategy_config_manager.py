"""
策略配置管理工具
"""

import os
import yaml
from datetime import datetime
from typing import Dict, Any, List
from .yaml_config_provider import YAMLConfigurationProvider


class StrategyConfigManager:
    """策略配置管理工具"""
    
    def __init__(self, config_dir: str = "config/strategies"):
        self.config_dir = config_dir
    
    def create_config_template(self, strategy_class_name: str, 
                             environment: str = "production") -> str:
        """创建配置模板"""
        template = f"""# {strategy_class_name} 配置模板
strategy_name: "{strategy_class_name}"
environment: "{environment}"
version: "1.0.0"
last_updated: "{datetime.now().strftime('%Y-%m-%dT%H:%M:%S')}"
is_valid: true

params:
  # 在这里添加策略参数
  # 示例:
  # gap_up_threshold: 0.025
  # black_list: ["9984", "7203"]

metadata:
  description: "{strategy_class_name} {environment}环境配置"
  author: "trading_team"
  risk_level: "medium"
  tags: []
"""
        
        filename = self._strategy_class_to_filename(strategy_class_name)
        filepath = os.path.join(self.config_dir, filename)
        
        os.makedirs(self.config_dir, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(template)
        
        return filepath
    
    def validate_config(self, strategy_class_name: str) -> bool:
        """验证配置文件"""
        config_file = self._get_config_file_path(strategy_class_name)
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            
            # 验证配置结构
            return self._validate_config_structure(config_data)
            
        except Exception as e:
            print(f"❌ 配置文件验证失败: {e}")
            return False
    
    def backup_config(self, strategy_class_name: str) -> str:
        """备份配置文件"""
        config_file = self._get_config_file_path(strategy_class_name)
        
        if not os.path.exists(config_file):
            raise FileNotFoundError(f"配置文件不存在: {config_file}")
        
        backup_file = f"{config_file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        import shutil
        shutil.copy2(config_file, backup_file)
        return backup_file
    
    def list_configs(self) -> List[str]:
        """列出所有配置文件"""
        if not os.path.exists(self.config_dir):
            return []
        
        configs = []
        for filename in os.listdir(self.config_dir):
            if filename.endswith('.yaml') or filename.endswith('.yml'):
                configs.append(filename)
        
        return sorted(configs)
    
    def get_config_info(self, strategy_class_name: str) -> Dict[str, Any]:
        """获取配置信息"""
        config_file = self._get_config_file_path(strategy_class_name)
        
        if not os.path.exists(config_file):
            return {}
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            
            # 获取文件信息
            stat = os.stat(config_file)
            
            return {
                "file_path": config_file,
                "file_size": stat.st_size,
                "modified_time": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "strategy_name": config_data.get("strategy_name", ""),
                "environment": config_data.get("environment", ""),
                "version": config_data.get("version", ""),
                "is_valid": config_data.get("is_valid", True),
                "description": config_data.get("metadata", {}).get("description", "")
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def _strategy_class_to_filename(self, strategy_class_name: str) -> str:
        """将策略类名转换为文件名"""
        import re
        filename = re.sub(r'([a-z])([A-Z])', r'\1_\2', strategy_class_name).lower()
        return f"{filename}.yaml"
    
    def _get_config_file_path(self, strategy_class_name: str) -> str:
        """获取配置文件路径"""
        filename = self._strategy_class_to_filename(strategy_class_name)
        return os.path.join(self.config_dir, filename)
    
    def _validate_config_structure(self, config_data: Dict[str, Any]) -> bool:
        """验证配置结构"""
        required_fields = ["strategy_name", "params", "metadata"]
        return all(field in config_data for field in required_fields) 