"""
Technical Indicators V3 - 基于ArrayManager的技术指标计算模块
使用组合模式设计，包含VWAP计算、Bar统计和技术指标管理
"""

from datetime import datetime
from typing import Dict, Optional

from vnpy.trader.object import BarData
from vnpy.trader.utility import ArrayManager


class VWAPCalculator:
    """VWAP计算器 - 从当天第一根bar开始累计"""
    
    def __init__(self):
        self.daily_acc_volume = 0.0      # 当日累计成交量
        self.daily_acc_turnover = 0.0    # 当日累计成交额
        self.current_date = None         # 当前日期
        self.vwap = 0.0                  # 当前VWAP值
    
    def update_bar(self, bar: BarData) -> float:
        """更新bar数据并计算VWAP"""
        # 检查是否是新的一天
        bar_date = bar.datetime.date()
        if self.current_date != bar_date:
            self._reset_daily_data(bar_date)
        
        # 累计成交量和成交额
        self.daily_acc_volume += bar.volume
        self.daily_acc_turnover += bar.turnover
        
        # 计算VWAP
        if self.daily_acc_volume > 0:
            self.vwap = self.daily_acc_turnover / self.daily_acc_volume
        else:
            self.vwap = 0.0
        
        return self.vwap
    
    def _reset_daily_data(self, new_date):
        """重置每日数据"""
        self.current_date = new_date
        self.daily_acc_volume = 0.0
        self.daily_acc_turnover = 0.0
        self.vwap = 0.0
    
    def get_vwap(self) -> float:
        """获取当前VWAP值"""
        return self.vwap
    
    def get_daily_stats(self) -> dict:
        """获取当日统计信息"""
        return {
            'acc_volume': self.daily_acc_volume,
            'acc_turnover': self.daily_acc_turnover,
            'vwap': self.vwap,
            'date': self.current_date
        }


class BarStatistics:
    """Bar统计器 - 统计close与VWAP的关系"""
    
    def __init__(self):
        self.above_vwap_count = 0    # close > VWAP的bar数量
        self.below_vwap_count = 0    # close < VWAP的bar数量
        self.equal_vwap_count = 0    # close = VWAP的bar数量
        self.current_date = None     # 当前日期
    
    def update_bar(self, bar: BarData, vwap: float) -> dict:
        """更新bar统计信息"""
        # 检查是否是新的一天
        bar_date = bar.datetime.date()
        if self.current_date != bar_date:
            self._reset_daily_data(bar_date)
        
        # 统计close与VWAP的关系
        close_price = bar.close_price
        if close_price > vwap:
            self.above_vwap_count += 1
        elif close_price < vwap:
            self.below_vwap_count += 1
        else:
            self.equal_vwap_count += 1
        
        return self.get_stats()
    
    def _reset_daily_data(self, new_date):
        """重置每日数据"""
        self.current_date = new_date
        self.above_vwap_count = 0
        self.below_vwap_count = 0
        self.equal_vwap_count = 0
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            'above_vwap_count': self.above_vwap_count,
            'below_vwap_count': self.below_vwap_count,
            'equal_vwap_count': self.equal_vwap_count,
            'total_count': self.above_vwap_count + self.below_vwap_count + self.equal_vwap_count
        }


class TechnicalIndicatorManager:
    """技术指标管理器 - 组合各个计算器"""
    
    def __init__(self, symbol: str, size: int = 100):
        self.symbol = symbol
        self.am = ArrayManager(size)          # 基础技术指标
        self.vwap_calc = VWAPCalculator()     # VWAP计算器
        self.stats = BarStatistics()          # 统计器
        
        # 缓存最新指标值
        self.latest_indicators = {}
    
    def update_bar(self, bar: BarData) -> dict:
        """更新bar数据并计算所有指标"""
        # 1. 更新基础技术指标
        self.am.update_bar(bar)
        
        # 2. 计算VWAP
        vwap = self.vwap_calc.update_bar(bar)
        
        # 3. 更新统计信息
        stats = self.stats.update_bar(bar, vwap)
        
        # 4. 计算其他技术指标
        indicators = self._calculate_indicators()
        
        # 5. 合并所有指标
        self.latest_indicators = {
            'symbol': self.symbol,
            'datetime': bar.datetime,
            'vwap': vwap,
            'atr_14': indicators.get('atr_14', 0),
            'volume_ma5': indicators.get('volume_ma5', 0),
            'above_vwap_count': stats['above_vwap_count'],
            'below_vwap_count': stats['below_vwap_count'],
            'equal_vwap_count': stats['equal_vwap_count'],
            'daily_acc_volume': self.vwap_calc.daily_acc_volume,
            'daily_acc_turnover': self.vwap_calc.daily_acc_turnover
        }
        
        return self.latest_indicators
    
    def _calculate_indicators(self) -> dict:
        """计算基础技术指标"""
        indicators = {}
        
        if self.am.inited:
            # ATR actually is not a simple moving average, it is a weighted moving average, which means the oldest tr will contribute as well
            if self.am.count <= 14:
                indicators['atr_14'] = 0
            elif self.am.count == 15:
                indicators['atr_14'] = self.am.atr(14)
            else:
                indicators['atr_14'] = (self.am.atr(1) + self.latest_indicators.get('atr_14', 0) * 13) / 14
            
            # Volume MA(5) - 使用numpy计算volume的移动平均
            import numpy as np
            volume_array = self.am.volume
            # 只取最后5个非零值（有效数据）
            valid_volumes = volume_array[volume_array > 0]
            if len(valid_volumes) >= 5:
                indicators['volume_ma5'] = np.mean(valid_volumes[-5:])
            else:
                indicators['volume_ma5'] = 0
        
        return indicators
    
    def get_indicators(self) -> dict:
        """获取最新指标值"""
        return self.latest_indicators.copy()
    
    def get_vwap(self) -> float:
        """获取当前VWAP"""
        return self.vwap_calc.get_vwap()
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        return self.stats.get_stats()
    
    def is_inited(self) -> bool:
        """检查是否已初始化"""
        return self.am.inited 