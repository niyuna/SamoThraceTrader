"""
HFT BB Reversal策略专用技术指标类 - 修正版本
"""

from typing import List, Dict, Any
from vnpy.trader.object import BarData
from vnpy.trader.utility import ArrayManager


class HFTBBReversalIndicatorV2:
    """HFT BB Reversal策略专用技术指标类 - 修正版本"""
    
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
        
        # 预加载状态（新增功能）
        self.is_preloaded = False
    
    def preload_historical_bars(self, historical_bars: List[BarData]):
        """预加载历史bar数据（前一天最后20个bar）"""
        if not historical_bars:
            print(f"警告: {self.symbol} 没有历史数据可加载")
            return
        
        # 将历史数据添加到ArrayManager
        for bar in historical_bars:
            self.am.update_bar(bar)
        
        # 计算初始BB指标并保存结果
        if len(historical_bars) >= self.bb_period:
            bb_levels = self._calculate_bb_levels()  # 保存返回值
            
            # 缓存结果
            self.latest_bb_levels = bb_levels
            self.latest_sma = bb_levels.get('middle', 0.0)
            self.latest_std = bb_levels.get('std', 0.0)
            
            self.is_preloaded = True
            print(f"{self.symbol} 预加载完成，BB指标已计算:")
            print(f"  Upper: {bb_levels.get('upper', 0):.2f}")
            print(f"  Lower: {bb_levels.get('lower', 0):.2f}")
            print(f"  Middle: {bb_levels.get('middle', 0):.2f}")
        else:
            print(f"警告: {self.symbol} 历史数据不足，需要{self.bb_period}个bar，实际{len(historical_bars)}个")
            self.is_preloaded = False
    
    def update_bar(self, bar: BarData) -> Dict[str, Any]:
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
        """处理日期变化 - 简化版本"""
        # 记录当前日期，用于日志和调试
        self.current_date = new_date
        
        # 注意：不需要保存prev_day_last_bar，因为策略每天独立启动
        # 历史数据通过preload_historical_bars方法加载
    
    def _calculate_bb_levels(self) -> Dict[str, Any]:
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
    
    def is_ready_for_trading(self) -> bool:
        """检查是否准备好开始交易"""
        return self.is_preloaded and bool(self.latest_bb_levels)
    
    def get_bb_levels(self) -> Dict[str, Any]:
        """获取最新BB价格水平"""
        if not self.is_ready_for_trading():
            return {}
        return self.latest_bb_levels.copy()
    
    def get_sma(self) -> float:
        """获取最新SMA值"""
        return self.latest_sma
    
    def get_std(self) -> float:
        """获取最新STD值"""
        return self.latest_std
    
    def get_indicators(self) -> Dict[str, Any]:
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
    
    def get_historical_bars_needed(self) -> int:
        """获取需要的历史bar数量"""
        return self.bb_period


class HistoricalDataProvider:
    """历史数据提供者接口"""
    
    def get_historical_bars(self, symbol: str, date: str, count: int = 20) -> List[BarData]:
        """获取历史bar数据"""
        raise NotImplementedError("子类必须实现此方法")
    
    def is_data_available(self, symbol: str, date: str) -> bool:
        """检查数据是否可用"""
        raise NotImplementedError("子类必须实现此方法")


class MockHistoricalDataProvider(HistoricalDataProvider):
    """模拟历史数据提供者"""
    
    def __init__(self):
        self.mock_data = {}
    
    def generate_mock_bars(self, symbol: str, base_price: float = 1000.0, count: int = 20) -> List[BarData]:
        """生成模拟的历史bar数据"""
        from vnpy.trader.object import BarData
        from vnpy.trader.constant import Exchange, Interval
        from datetime import datetime, timedelta
        import random
        
        bars = []
        current_time = datetime.now().replace(hour=15, minute=30, second=0, microsecond=0)  # 前一天收盘时间
        
        for i in range(count):
            # 生成价格数据，添加一些随机波动
            price_change = random.uniform(-0.5, 0.5)
            open_price = base_price + i * 0.1 + price_change
            high_price = open_price + random.uniform(0, 0.3)
            low_price = open_price - random.uniform(0, 0.3)
            close_price = open_price + random.uniform(-0.2, 0.2)
            
            bar = BarData(
                symbol=symbol,
                exchange=Exchange.TSE,
                datetime=current_time - timedelta(minutes=count-i-1),
                interval=Interval.MINUTE,
                volume=1000 + random.randint(-200, 200),
                turnover=(1000 + random.randint(-200, 200)) * close_price,
                open_price=open_price,
                high_price=high_price,
                low_price=low_price,
                close_price=close_price,
                gateway_name="MOCK"
            )
            bars.append(bar)
        
        return bars
    
    def get_historical_bars(self, symbol: str, date: str, count: int = 20) -> List[BarData]:
        """返回模拟的历史数据"""
        if symbol not in self.mock_data:
            # 为不同股票生成不同的基础价格
            base_prices = {"9984": 1000.0, "6098": 800.0}
            base_price = base_prices.get(symbol, 1000.0)
            self.mock_data[symbol] = self.generate_mock_bars(symbol, base_price, count)
        
        return self.mock_data[symbol][:count]
    
    def is_data_available(self, symbol: str, date: str) -> bool:
        """检查模拟数据是否可用"""
        return True
