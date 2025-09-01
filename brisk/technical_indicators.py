"""
Technical Indicators V3 - 基于ArrayManager的技术指标计算模块
使用组合模式设计，包含VWAP计算、Bar统计和技术指标管理
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Optional

from vnpy.trader.object import BarData
from vnpy.trader.utility import ArrayManager


class BaseCalculator(ABC):
    """技术指标计算器基类"""
    
    @abstractmethod
    def update_bar(self, bar: BarData, **kwargs) -> any:
        """更新bar数据并计算指标"""
        pass
    
    @abstractmethod
    def reset_daily(self, new_date):
        """重置每日数据"""
        pass


class VWAPCalculator(BaseCalculator):
    """VWAP计算器 - 从当天第一根bar开始累计"""
    
    def __init__(self):
        self.daily_acc_volume = 0.0      # 当日累计成交量
        self.daily_acc_turnover = 0.0    # 当日累计成交额
        self.current_date = None         # 当前日期
        self.vwap = 0.0                  # 当前VWAP值
    
    def update_bar(self, bar: BarData, **kwargs) -> float:
        """更新bar数据并计算VWAP"""
        # 检查是否是新的一天
        bar_date = bar.datetime.date()
        if self.current_date != bar_date:
            self.reset_daily(bar_date)
        
        # 累计成交量和成交额
        self.daily_acc_volume += bar.volume
        self.daily_acc_turnover += bar.turnover
        
        # 计算VWAP
        if self.daily_acc_volume > 0:
            self.vwap = self.daily_acc_turnover / self.daily_acc_volume
        else:
            self.vwap = 0.0
        
        return self.vwap
    
    def reset_daily(self, new_date):
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


class BarStatistics(BaseCalculator):
    """Bar统计器 - 统计close与VWAP的关系"""
    
    def __init__(self):
        self.above_vwap_count = 0    # close > VWAP的bar数量
        self.below_vwap_count = 0    # close < VWAP的bar数量
        self.equal_vwap_count = 0    # close = VWAP的bar数量
        self.current_date = None     # 当前日期
    
    def update_bar(self, bar: BarData, **kwargs) -> dict:
        """更新bar统计信息"""
        # 从kwargs获取VWAP值
        vwap = kwargs.get('vwap', 0.0)
        
        # 检查是否是新的一天
        bar_date = bar.datetime.date()
        if self.current_date != bar_date:
            self.reset_daily(bar_date)
        
        # 统计close与VWAP的关系
        close_price = bar.close_price
        if close_price > vwap:
            self.above_vwap_count += 1
        elif close_price < vwap:
            self.below_vwap_count += 1
        else:
            self.equal_vwap_count += 1
        
        return self.get_stats()
    
    def reset_daily(self, new_date):
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


class ATRCalculator(BaseCalculator):
    """ATR计算器 - 使用EMA算法计算ATR"""
    
    def __init__(self, period: int = 14):
        self.period = period
        self.current_date = None
        self.latest_atr = 0.0
        self.am = None  # 将由外部设置
    
    def set_array_manager(self, am: ArrayManager):
        """设置ArrayManager引用"""
        self.am = am
    
    def update_bar(self, bar: BarData, **kwargs) -> float:
        """更新bar数据并计算ATR"""
        # 检查是否是新的一天
        bar_date = bar.datetime.date()
        if self.current_date != bar_date:
            self.reset_daily(bar_date)
        
        if not self.am or not self.am.inited:
            return 0.0
        
        # 使用EMA算法计算ATR
        if self.am.count <= self.period:
            self.latest_atr = 0.0
        elif self.am.count == self.period + 1:
            # 第一次完整计算
            self.latest_atr = self.am.atr(self.period)
        else:
            # 使用EMA算法更新
            current_atr = self.am.atr(1)
            self.latest_atr = (current_atr + self.latest_atr * (self.period - 1)) / self.period
        
        return self.latest_atr
    
    def reset_daily(self, new_date):
        """重置每日数据"""
        self.current_date = new_date
        # 注意：ATR不需要每日重置，因为它是连续计算的
    
    def get_atr(self) -> float:
        """获取当前ATR值"""
        return self.latest_atr


class VolumeMACalculator(BaseCalculator):
    """Volume MA计算器 - 计算成交量移动平均"""
    
    def __init__(self, period: int = 5):
        self.period = period
        self.current_date = None
        self.latest_volume_ma = 0.0
        self.am = None  # 将由外部设置
    
    def set_array_manager(self, am: ArrayManager):
        """设置ArrayManager引用"""
        self.am = am
    
    def update_bar(self, bar: BarData, **kwargs) -> float:
        """更新bar数据并计算Volume MA"""
        # 检查是否是新的一天
        bar_date = bar.datetime.date()
        if self.current_date != bar_date:
            self.reset_daily(bar_date)
        
        if not self.am or not self.am.inited:
            return 0.0
        
        # 计算Volume MA
        import numpy as np
        volume_array = self.am.volume
        # 只取最后period个非零值（有效数据）
        valid_volumes = volume_array[volume_array > 0]
        if len(valid_volumes) >= self.period:
            self.latest_volume_ma = np.mean(valid_volumes[-self.period:])
        else:
            self.latest_volume_ma = 0.0
        
        return self.latest_volume_ma
    
    def reset_daily(self, new_date):
        """重置每日数据"""
        self.current_date = new_date
        # 注意：Volume MA不需要每日重置，因为它是连续计算的
    
    def get_volume_ma(self) -> float:
        """获取当前Volume MA值"""
        return self.latest_volume_ma


class TechnicalIndicatorManager:
    """技术指标管理器 - 组合各个计算器"""
    
    def __init__(self, symbol: str, size: int = 100):
        self.symbol = symbol
        self.am = ArrayManager(size)          # 基础技术指标
        self.vwap_calc = VWAPCalculator()     # VWAP计算器
        self.stats = BarStatistics()          # 统计器
        
        # 新增：使用专门的计算器
        self.atr_calc = ATRCalculator(period=14)      # ATR计算器
        self.volume_ma_calc = VolumeMACalculator(period=5)  # Volume MA计算器
        
        # 设置ArrayManager引用
        self.atr_calc.set_array_manager(self.am)
        self.volume_ma_calc.set_array_manager(self.am)
        
        # 缓存最新指标值
        self.latest_indicators = {}
    
    def update_bar(self, bar: BarData) -> dict:
        """更新bar数据并计算所有指标"""
        # 1. 更新基础技术指标
        self.am.update_bar(bar)
        
        # 2. 计算VWAP
        vwap = self.vwap_calc.update_bar(bar)
        
        # 3. 更新统计信息
        stats = self.stats.update_bar(bar, vwap=vwap)
        
        # 4. 使用专门的计算器计算技术指标
        atr_14 = self.atr_calc.update_bar(bar)
        volume_ma5 = self.volume_ma_calc.update_bar(bar)
        
        # 5. 合并所有指标
        self.latest_indicators = {
            'symbol': self.symbol,
            'datetime': bar.datetime,
            'vwap': vwap,
            'atr_14': atr_14,
            'volume_ma5': volume_ma5,
            'above_vwap_count': stats['above_vwap_count'],
            'below_vwap_count': stats['below_vwap_count'],
            'equal_vwap_count': stats['equal_vwap_count'],
            'daily_acc_volume': self.vwap_calc.daily_acc_volume,
            'daily_acc_turnover': self.vwap_calc.daily_acc_turnover
        }
        
        return self.latest_indicators
    
    def _calculate_indicators(self) -> dict:
        """计算基础技术指标 - 保持向后兼容性"""
        indicators = {}
        
        if self.am.inited:
            # 使用专门的计算器
            indicators['atr_14'] = self.atr_calc.get_atr()
            indicators['volume_ma5'] = self.volume_ma_calc.get_volume_ma()
        
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


# ==================== 手动组合Calculator的示例 ====================

class SimpleATRStrategy:
    """简单ATR策略示例 - 只需要ATR指标"""
    
    def __init__(self, symbol: str, size: int = 100):
        self.symbol = symbol
        self.am = ArrayManager(size)
        
        # 手动组合：只需要ATR计算器
        self.atr_calc = ATRCalculator(period=14)
        self.atr_calc.set_array_manager(self.am)
        
        self.latest_atr = 0.0
    
    def update_bar(self, bar: BarData) -> float:
        """更新bar并计算ATR"""
        self.am.update_bar(bar)
        self.latest_atr = self.atr_calc.update_bar(bar)
        return self.latest_atr
    
    def get_atr(self) -> float:
        """获取当前ATR值"""
        return self.latest_atr
    
    def get_indicators(self) -> dict:
        """获取指标值 - 实现统一接口"""
        return {
            'atr_14': self.latest_atr
        }


class VolumeStrategy:
    """成交量策略示例 - 只需要Volume MA指标"""
    
    def __init__(self, symbol: str, size: int = 100):
        self.symbol = symbol
        self.am = ArrayManager(size)
        
        # 手动组合：只需要Volume MA计算器
        self.volume_ma_calc = VolumeMACalculator(period=10)  # 使用10期
        self.volume_ma_calc.set_array_manager(self.am)
        
        self.latest_volume_ma = 0.0
    
    def update_bar(self, bar: BarData) -> float:
        """更新bar并计算Volume MA"""
        self.am.update_bar(bar)
        self.latest_volume_ma = self.volume_ma_calc.update_bar(bar)
        return self.latest_volume_ma
    
    def get_volume_ma(self) -> float:
        """获取当前Volume MA值"""
        return self.latest_volume_ma
    
    def get_indicators(self) -> dict:
        """获取指标值 - 实现统一接口"""
        return {
            'volume_ma10': self.latest_volume_ma
        }


class CustomStrategy:
    """自定义策略示例 - 组合多个计算器"""
    
    def __init__(self, symbol: str, size: int = 100):
        self.symbol = symbol
        self.am = ArrayManager(size)
        
        # 手动组合：选择需要的计算器
        self.vwap_calc = VWAPCalculator()
        self.atr_calc = ATRCalculator(period=20)  # 使用20期
        self.volume_ma_calc = VolumeMACalculator(period=3)  # 使用3期
        
        # 设置ArrayManager引用
        self.atr_calc.set_array_manager(self.am)
        self.volume_ma_calc.set_array_manager(self.am)
        
        self.latest_indicators = {}
    
    def update_bar(self, bar: BarData) -> dict:
        """更新bar并计算选择的指标"""
        self.am.update_bar(bar)
        
        # 计算选择的指标
        vwap = self.vwap_calc.update_bar(bar)
        atr_20 = self.atr_calc.update_bar(bar)
        volume_ma3 = self.volume_ma_calc.update_bar(bar)
        
        # 合并结果
        self.latest_indicators = {
            'symbol': self.symbol,
            'datetime': bar.datetime,
            'vwap': vwap,
            'atr_20': atr_20,
            'volume_ma3': volume_ma3,
            'daily_acc_volume': self.vwap_calc.daily_acc_volume,
        }
        
        return self.latest_indicators
    
    def get_indicators(self) -> dict:
        """获取最新指标值"""
        return self.latest_indicators.copy() 


class HFTBBReversalIndicator:
    """HFT BB Reversal策略专用技术指标类"""
    
    def __init__(self, symbol: str, size: int = 100, bb_period: int = 20, 
                 entry_std_multiplier: float = 3.0, exit_std_multiplier: float = 0.1):
        self.symbol = symbol
        self.am = ArrayManager(size)
        
        # BB策略参数
        self.bb_period = bb_period
        self.entry_std_multiplier = entry_std_multiplier
        self.exit_std_multiplier = exit_std_multiplier
        
        # 缓存最新指标值
        self.latest_bb_levels = {}
        self.latest_sma = 0.0
        self.latest_std = 0.0
        
        # 历史数据缓存（用于跨日补齐）
        self.prev_day_last_bar = None
        self.current_date = None
    
    def update_bar(self, bar: BarData) -> dict:
        """更新bar并计算BB指标"""
        # 检查是否是新的一天
        bar_date = bar.datetime.date()
        if self.current_date != bar_date:
            self._handle_date_change(bar_date)
        
        # 更新ArrayManager
        self.am.update_bar(bar)
        
        # 计算BB指标
        bb_levels = self._calculate_bb_levels()
        
        # 缓存结果
        self.latest_bb_levels = bb_levels
        self.latest_sma = bb_levels.get('middle', 0.0)
        self.latest_std = bb_levels.get('std', 0.0)
        
        return bb_levels
    
    def _handle_date_change(self, new_date):
        """处理日期变化 - 保存前一日最后bar用于补齐"""
        if self.current_date is not None and self.am.inited:
            # 保存前一日最后bar
            self.prev_day_last_bar = {
                'open': self.am.open[-1],
                'high': self.am.high[-1], 
                'low': self.am.low[-1],
                'close': self.am.close[-1],
                'volume': self.am.volume[-1],
                'turnover': self.am.turnover[-1]
            }
        
        self.current_date = new_date
    
    def _calculate_bb_levels(self) -> dict:
        """计算布林带各个价格水平"""
        if not self.am.inited:
            return {}
        
        # 获取SMA和STD
        sma = self.am.sma(self.bb_period)
        std = self.am.std(self.bb_period)
        
        if sma is None or std is None:
            return {}
        
        # 计算BB价格水平
        bb_levels = {
            'upper': sma + (self.entry_std_multiplier * std),      # short entry
            'lower': sma - (self.entry_std_multiplier * std),      # long entry  
            'middle': sma,                                          # BB中轴
            'exit_long': sma - (self.exit_std_multiplier * std),   # long exit
            'exit_short': sma + (self.exit_std_multiplier * std),  # short exit
            'std': std,                                             # 标准差
            'period': self.bb_period,                              # 周期
            'entry_multiplier': self.entry_std_multiplier,         # entry倍数
            'exit_multiplier': self.exit_std_multiplier            # exit倍数
        }
        
        return bb_levels
    
    def get_bb_levels(self) -> dict:
        """获取最新BB价格水平"""
        return self.latest_bb_levels.copy()
    
    def get_sma(self) -> float:
        """获取最新SMA值"""
        return self.latest_sma
    
    def get_std(self) -> float:
        """获取最新STD值"""
        return self.latest_std
    
    def get_indicators(self) -> dict:
        """获取所有指标值 - 实现统一接口"""
        return self.latest_bb_levels.copy()
    
    def is_inited(self) -> bool:
        """检查是否已初始化"""
        return self.am.inited
    
    def get_array_manager(self) -> ArrayManager:
        """获取ArrayManager引用"""
        return self.am
    
    def reset_daily(self, new_date):
        """重置每日数据 - 保持向后兼容性"""
        self._handle_date_change(new_date) 