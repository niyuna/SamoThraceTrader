"""
动态配置系统
提供策略参数的动态更新功能
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass


@dataclass
class StrategyConfig:
    """策略配置数据结构"""
    params: Dict[str, Any]                    # 策略参数
    metadata: Dict[str, Any]                  # 元数据
    last_updated: Optional[datetime] = None   # 最后更新时间
    version: str = "1.0"                      # 配置版本
    is_valid: bool = True                     # 配置是否有效
    
    def is_expired(self, max_age_hours: int = 8) -> bool:
        """检查配置是否过期"""
        if not self.last_updated:
            return True
        age = datetime.now() - self.last_updated
        return age.total_seconds() > max_age_hours * 3600


class ConfigurationProvider(ABC):
    """配置提供者接口"""
    
    @abstractmethod
    def get_strategy_config(self, strategy_class_name: str, 
                           last_check_time: Optional[datetime] = None) -> Dict[str, Any]:
        """
        获取策略配置
        
        Args:
            strategy_class_name: 策略类名
            last_check_time: 上次检查时间，用于增量更新
            
        Returns:
            配置字典，包含参数和元数据
        """
        pass


class MockConfigurationProvider(ConfigurationProvider):
    """Mock配置提供者，用于测试"""
    
    def __init__(self):
        self.configs = {}
    
    def set_strategy_config(self, strategy_class_name: str, config: Dict[str, Any]):
        """设置策略配置"""
        self.configs[strategy_class_name] = config
    
    def get_strategy_config(self, strategy_class_name: str, 
                           last_check_time: Optional[datetime] = None) -> Dict[str, Any]:
        """获取策略配置"""
        if strategy_class_name not in self.configs:
            return {"params": {}, "metadata": {"last_updated": None, "version": "1.0"}}
        
        config = self.configs[strategy_class_name].copy()
        
        # 模拟API延迟
        import time
        time.sleep(0.01)
        
        return config


class BlackListUpdateParser:
    """黑名单增量更新解析器"""
    
    @staticmethod
    def parse_update(update_data: Any) -> Dict[str, List[str]]:
        """
        解析黑名单更新数据
        
        支持格式：
        1. 简单列表: ["9984", "7203"]
        2. 增量操作: [
            {"operation": "add", "symbol": "9984"},
            {"operation": "remove", "symbol": "7203"}
        ]
        3. 混合格式: ["9984", {"operation": "remove", "symbol": "7203"}]
        """
        adds = []
        removes = []
        
        if isinstance(update_data, list):
            for item in update_data:
                if isinstance(item, dict):
                    operation = item.get('operation', 'add')
                    symbol = item.get('symbol', '')
                    
                    if operation == 'add' and symbol:
                        adds.append(symbol)
                    elif operation == 'remove' and symbol:
                        removes.append(symbol)
                else:
                    # 直接添加
                    adds.append(str(item))
        
        return {
            'adds': adds,
            'removes': removes
        } 