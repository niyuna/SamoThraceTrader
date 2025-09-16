"""
个股配置系统
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import time
import json
import os


@dataclass
class TradingWindow:
    """交易时间窗口"""
    start_time: time  # 开始时间，如 time(9, 30)
    end_time: time    # 结束时间，如 time(11, 30)
    allowed_directions: List[str]  # 允许的方向，如 ['long', 'short'] 或 ['long'] 或 ['short']


@dataclass
class StopLossConfig:
    """止损配置"""
    first_stage_threshold: float = 0.02   # 第一阶段止损阈值（百分比）
    second_stage_threshold: float = 0.05  # 第二阶段止损阈值（百分比）
    enabled: bool = True                  # 是否启用止损


@dataclass
class StockConfig:
    """个股配置"""
    symbol: str
    bb_entry_std_multiplier: Optional[float] = None  # 入场布林带标准差倍数
    bb_exit_std_multiplier: Optional[float] = None   # 出场布林带标准差倍数
    trading_windows: List[TradingWindow] = field(default_factory=list)  # 交易时间窗口列表
    exclude_minutes: List[time] = field(default_factory=list)  # 排除的分钟列表，如 [time(12, 0), time(15, 0)]
    stop_loss_config: Optional[StopLossConfig] = None  # 止损配置


class StockConfigManager:
    """个股配置管理器"""
    
    def __init__(self, config_file_path: str):
        self.config_file_path = config_file_path
        self.stock_configs: Dict[str, StockConfig] = {}
        self.load_configs()
    
    def load_configs(self):
        """加载配置文件"""
        try:
            if not os.path.exists(self.config_file_path):
                print(f"Warning: Stock config file not found: {self.config_file_path}")
                return
                
            if self.config_file_path.endswith('.json'):
                self._load_json_configs()
            elif self.config_file_path.endswith('.yaml') or self.config_file_path.endswith('.yml'):
                self._load_yaml_configs()
            else:
                raise ValueError("Unsupported config file format")
        except Exception as e:
            print(f"Warning: Failed to load stock configs: {e}")
            self.stock_configs = {}
    
    def get_stock_config(self, symbol: str) -> Optional[StockConfig]:
        """获取个股配置，如果没有则返回 None"""
        return self.stock_configs.get(symbol)
    
    def has_custom_config(self, symbol: str) -> bool:
        """检查个股是否有自定义配置"""
        return symbol in self.stock_configs
    
    def _load_json_configs(self):
        """加载JSON配置文件"""
        with open(self.config_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        for symbol_key, config_data in data.items():
            # 检查symbol_key是否包含逗号，如果包含则分割为多个symbol
            symbols = [s.strip() for s in symbol_key.split(',')] if ',' in symbol_key else [symbol_key]
            
            print(f"Loading config for {symbols}")
            print(config_data)
            
            # 解析时间窗口
            trading_windows = []
            for window_data in config_data.get('trading_windows', []):
                trading_windows.append(TradingWindow(
                    start_time=self._parse_time(window_data['start_time']),
                    end_time=self._parse_time(window_data['end_time']),
                    allowed_directions=window_data['allowed_directions']
                ))
            
            # 解析排除时间
            exclude_minutes = [self._parse_time(t) for t in config_data.get('exclude_minutes', [])]
            
            # 解析止损配置
            stop_loss_config = None
            if 'stop_loss_config' in config_data:
                stop_loss_data = config_data['stop_loss_config']
                stop_loss_config = StopLossConfig(
                    first_stage_threshold=stop_loss_data.get('first_stage_threshold', 0.02),
                    second_stage_threshold=stop_loss_data.get('second_stage_threshold', 0.05),
                    enabled=stop_loss_data.get('enabled', True)
                )
            
            # 为每个symbol创建配置
            for symbol in symbols:
                self.stock_configs[symbol] = StockConfig(
                    symbol=symbol,
                    bb_entry_std_multiplier=config_data.get('bb_entry_std_multiplier'),
                    bb_exit_std_multiplier=config_data.get('bb_exit_std_multiplier'),
                    trading_windows=trading_windows,
                    exclude_minutes=exclude_minutes,
                    stop_loss_config=stop_loss_config
                )
    
    def _load_yaml_configs(self):
        """加载YAML配置文件"""
        try:
            import yaml
            with open(self.config_file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            for symbol_key, config_data in data.items():
                # 检查symbol_key是否包含逗号，如果包含则分割为多个symbol
                symbols = [s.strip() for s in symbol_key.split(',')] if ',' in symbol_key else [symbol_key]
                
                # 解析时间窗口
                trading_windows = []
                for window_data in config_data.get('trading_windows', []):
                    trading_windows.append(TradingWindow(
                        start_time=self._parse_time(window_data['start_time']),
                        end_time=self._parse_time(window_data['end_time']),
                        allowed_directions=window_data['allowed_directions']
                    ))
                
                # 解析排除时间
                exclude_minutes = [self._parse_time(t) for t in config_data.get('exclude_minutes', [])]
                
                # 解析止损配置
                stop_loss_config = None
                if 'stop_loss_config' in config_data:
                    stop_loss_data = config_data['stop_loss_config']
                    stop_loss_config = StopLossConfig(
                        first_stage_threshold=stop_loss_data.get('first_stage_threshold', 0.02),
                        second_stage_threshold=stop_loss_data.get('second_stage_threshold', 0.05),
                        enabled=stop_loss_data.get('enabled', True)
                    )
                
                # 为每个symbol创建配置
                for symbol in symbols:
                    self.stock_configs[symbol] = StockConfig(
                        symbol=symbol,
                        bb_entry_std_multiplier=config_data.get('bb_entry_std_multiplier'),
                        bb_exit_std_multiplier=config_data.get('bb_exit_std_multiplier'),
                        trading_windows=trading_windows,
                        exclude_minutes=exclude_minutes,
                        stop_loss_config=stop_loss_config
                    )
        except ImportError:
            raise ValueError("YAML support requires PyYAML package")
    
    def _parse_time(self, time_str: str) -> time:
        """解析时间字符串，如 '09:30' -> time(9, 30)"""
        hour, minute = map(int, time_str.split(':'))
        return time(hour, minute)
    
    def validate_stock_config(self, config: StockConfig) -> bool:
        """验证个股配置的有效性"""
        # 验证时间窗口
        for window in config.trading_windows:
            if window.start_time >= window.end_time:
                return False
            if not window.allowed_directions:
                return False
            for direction in window.allowed_directions:
                if direction not in ['long', 'short']:
                    return False
        
        # 验证排除时间
        for exclude_time in config.exclude_minutes:
            if not isinstance(exclude_time, time):
                return False
        
        return True
