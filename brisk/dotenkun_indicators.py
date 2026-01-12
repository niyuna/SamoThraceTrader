"""
Dotenkun策略专用技术指标类
"""
from typing import Dict, Any, List
from datetime import datetime
from vnpy.trader.object import BarData
from vnpy.trader.utility import ArrayManager


class DotenkunIndicator:
    """Dotenkun策略专用技术指标类
    
    计算HL Range MA：过去N个5分钟线的(high-low)平均值
    """
    
    def __init__(self, symbol: str, size: int = 100, hl_range_period: int = 5):
        self.symbol = symbol
        self.am = ArrayManager(size)  # 用于存储5分钟bar
        
        # HL Range MA参数
        self.hl_range_period = hl_range_period
        
        # 存储过去N个5分钟bar的h-l值
        self.hl_ranges: List[float] = []
        
        # 缓存最新指标值
        self.latest_hl_range_ma = 0.0
        self.current_date = None
    
    def update_bar(self, bar: BarData) -> Dict[str, Any]:
        """更新5分钟bar并计算HL Range MA
        
        注意：这个方法只处理5分钟bar，如果传入1分钟bar会被忽略
        """
        # 检查bar的interval：如果是MINUTE（1分钟bar），则忽略
        # 5分钟bar的interval通常是None（因为EnhancedBarGenerator没有设置）
        # 但我们通过检查bar是否来自window_bar来判断
        # 更安全的方式：只处理interval不是MINUTE的bar（即5分钟bar）
        from vnpy.trader.constant import Interval
        
        # 如果bar的interval是MINUTE，说明这是1分钟bar，应该忽略
        if bar.interval == Interval.MINUTE:
            # 这是1分钟bar，不应该在这里处理，直接返回当前指标值
            return self.get_indicators()
        
        # 检查是否是新的一天
        bar_date = bar.datetime.date()
        if self.current_date != bar_date:
            self.reset_daily(bar_date)
        
        # 更新ArrayManager（用于其他可能的指标）
        self.am.update_bar(bar)
        
        # 计算当前bar的h-l值
        hl_range = bar.high_price - bar.low_price
        
        # 添加到列表
        self.hl_ranges.append(hl_range)
        
        # 只保留最近period个值
        if len(self.hl_ranges) > self.hl_range_period:
            self.hl_ranges.pop(0)
        
        # 计算平均值
        if len(self.hl_ranges) >= self.hl_range_period:
            self.latest_hl_range_ma = sum(self.hl_ranges) / len(self.hl_ranges)
        else:
            # 如果数据不足，使用当前已有的数据计算平均值
            if len(self.hl_ranges) > 0:
                self.latest_hl_range_ma = sum(self.hl_ranges) / len(self.hl_ranges)
            else:
                self.latest_hl_range_ma = 0.0
        
        # 返回指标字典
        return self.get_indicators()
    
    def get_indicators(self) -> Dict[str, Any]:
        """获取所有指标值 - 实现统一接口"""
        return {
            'hl_range_ma_5': self.latest_hl_range_ma,
            'hl_range_count': len(self.hl_ranges),  # 当前存储的h-l值数量
            'symbol': self.symbol
        }
    
    def get_hl_range_ma(self) -> float:
        """获取当前HL Range MA值"""
        return self.latest_hl_range_ma
    
    def is_inited(self) -> bool:
        """检查是否已初始化（有足够的数据）"""
        return len(self.hl_ranges) >= self.hl_range_period
    
    def reset_daily(self, new_date):
        """重置每日数据"""
        self.current_date = new_date
        self.hl_ranges.clear()
        self.latest_hl_range_ma = 0.0
    
    def get_array_manager(self) -> ArrayManager:
        """获取ArrayManager引用（用于扩展其他指标）"""
        return self.am
