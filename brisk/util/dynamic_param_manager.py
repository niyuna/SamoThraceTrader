"""
动态参数管理器
负责获取、验证和管理策略配置
"""

from typing import Optional
from datetime import datetime
from .dynamic_config import ConfigurationProvider, StrategyConfig


class DynamicParamManager:
    """动态参数管理器"""
    
    def __init__(self, strategy, config_provider: ConfigurationProvider):
        self.strategy = strategy
        self.config_provider = config_provider
        self.last_check_time: Optional[datetime] = None
        self.last_config: Optional[StrategyConfig] = None
        self.check_interval: int = 30  # 默认60秒检查一次
        
    def should_check_config(self) -> bool:
        """判断是否应该检查配置"""
        if not self.last_check_time:
            return True
        
        elapsed = (datetime.now() - self.last_check_time).total_seconds()
        return elapsed >= self.check_interval
        
    def fetch_config(self) -> Optional[StrategyConfig]:
        """获取配置"""
        try:
            strategy_name = self.strategy.__class__.__name__
            raw_config = self.config_provider.get_strategy_config(
                strategy_name, self.last_check_time
            )
            
            # 提取参数和元数据
            params = raw_config.get('params', {})
            metadata = raw_config.get('metadata', {})
            
            # 处理时间字段
            last_updated = None
            if 'last_updated' in metadata and metadata['last_updated']:
                try:
                    # 解析ISO格式的时间字符串（无时区）
                    last_updated = datetime.fromisoformat(metadata['last_updated'])
                except ValueError:
                    last_updated = None
            
            # 提取其他元数据字段
            version = metadata.get('version', '1.0')
            is_valid = metadata.get('is_valid', True)
            
            # 创建StrategyConfig对象
            config = StrategyConfig(
                params=params,
                metadata=metadata,
                last_updated=last_updated,
                version=version,
                is_valid=is_valid
            )
            
            # 验证配置有效性
            if not self._validate_config(config):
                self.strategy.write_log(f"配置验证失败: {config}")
                return None
            
            self.last_check_time = datetime.now()
            self.last_config = config
            
            return config
            
        except Exception as e:
            self.strategy.write_log(f"获取配置失败: {e}")
            return None
    
    def _validate_config(self, config: StrategyConfig) -> bool:
        """验证配置有效性"""
        if not config.is_valid:
            return False
        
        if config.is_expired():
            self.strategy.write_log("配置已过期")
            return False
        
        return True 