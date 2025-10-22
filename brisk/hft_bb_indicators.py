"""
HFT BB Reversal策略专用技术指标类 - 修正版本
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, time
import pandas as pd
import os
from vnpy.trader.object import BarData
from vnpy.trader.constant import Exchange, Interval, Direction
from vnpy.trader.utility import ArrayManager
from common.trading_common import next_tick_price, get_tick_size, normalize_price


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
    
    def update_parameters(self, entry_std_multiplier: float = None, exit_std_multiplier: float = None):
        """更新技术指标参数"""
        if entry_std_multiplier is not None:
            self.entry_std_multiplier = entry_std_multiplier
        if exit_std_multiplier is not None:
            self.exit_std_multiplier = exit_std_multiplier
        # 注意：BB水平将在下次bar更新时使用新参数重新计算
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
        
        # 重置预加载状态
        self.is_preloaded = False
        
        # 注意：不需要保存prev_day_last_bar，因为策略每天独立启动
        # 历史数据通过preload_historical_bars方法加载
    
    def _calculate_bb_levels(self) -> Dict[str, Any]:
        """计算布林带各个价格水平"""
        if not self.am.inited:
            return {}
        
        # 获取SMA和STD
        # print(self.am.close)
        # print(len(self.am.close))
        # print(sum(self.am.close) / len(self.am.close))
        sma = self.am.sma(self.bb_period)
        std = self.am.std(self.bb_period)
        
        if sma is None or std is None:
            return {}

        # 计算BB价格水平
        upper_raw = sma + (self.entry_std_multiplier * std)      # short entry
        lower_raw = sma - (self.entry_std_multiplier * std)      # long entry  
        exit_long_raw = sma - (self.exit_std_multiplier * std)   # long exit
        exit_short_raw = sma + (self.exit_std_multiplier * std)  # short exit
        
        tick_size = get_tick_size(self.symbol, sma)
        need_tick_adjustment = tick_size / std < 0.5
        
        # 对实际会发送到broker的价格进行tick对齐
        # upper用于SHORT entry，向下调整
        upper_aligned = self._align_price_to_tick(upper_raw, Direction.SHORT) if need_tick_adjustment else normalize_price(self.symbol, upper_raw)
        # lower用于LONG entry，向上调整  
        lower_aligned = self._align_price_to_tick(lower_raw, Direction.LONG) if need_tick_adjustment else normalize_price(self.symbol, lower_raw)
        # exit_long用于平仓LONG头寸，是SHORT订单，向下调整
        exit_long_aligned = self._align_price_to_tick(exit_long_raw, Direction.SHORT) if need_tick_adjustment else normalize_price(self.symbol, exit_long_raw)
        # exit_short用于平仓SHORT头寸，是LONG订单，向上调整
        exit_short_aligned = self._align_price_to_tick(exit_short_raw, Direction.LONG) if need_tick_adjustment else normalize_price(self.symbol, exit_short_raw)
        
        bb_levels = {
            'upper': upper_aligned,                                # short entry (对齐后)
            'lower': lower_aligned,                                # long entry (对齐后)
            'middle': sma,                                          # BB中轴 (不需要对齐)
            'exit_long': exit_long_aligned,                        # long exit (对齐后)
            'exit_short': exit_short_aligned,                      # short exit (对齐后)
            'std': std,                                             # 标准差
            'period': self.bb_period,                              # 周期
            'entry_multiplier': self.entry_std_multiplier,         # entry倍数
            'exit_multiplier': self.exit_std_multiplier            # exit倍数
        }
        
        return bb_levels
    
    def _align_price_to_tick(self, price: float, direction: Direction) -> float:
        """
        将价格对齐到tick价格
        
        Args:
            price: 原始价格
            direction: 交易方向 (LONG/SHORT)
            
        Returns:
            float: 对齐后的价格
        """
        try:
            # 根据交易方向确定upside参数
            # LONG订单向上调整，SHORT订单向下调整
            upside = (direction == Direction.LONG)
            
            # 调用next_tick_price进行价格对齐
            aligned_price = next_tick_price(self.symbol, price, upside)
            
            # 如果对齐失败，返回原价格
            if aligned_price is None:
                return price
            
            return aligned_price
            
        except Exception as e:
            # 如果对齐失败，返回原价格
            return price
    
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


class BriskHistoricalDataProvider(HistoricalDataProvider):
    """基于Brisk CSV数据的真实历史数据提供者"""
    
    def __init__(self, data_dir: str = "brisk/data/brisk_agged_ohlc"):
        self.data_dir = data_dir
        # 缓存结构：{date: {symbol: [BarData]}}
        # 只缓存实际请求过的股票数据
        self.cached_data = {}  
        self.cached_date = None
        self.required_columns = ['sc', 'ts_1m', 'vol', 'turnover', 'o', 'h', 'l', 'c']
    
    def load_daily_data(self, date: str, symbols: Optional[List[str]] = None) -> None:
        """
        加载指定日期的数据，只加载指定股票的数据
        只保留每个股票的最后20个bar
        """
        file_path = f"{self.data_dir}/brisk_ohlc_{date}_ts_1m.csv"
        
        if not os.path.exists(file_path):
            print(f"警告: 数据文件不存在: {file_path}")
            return
        
        try:
            if symbols is None:
                # 读取所有数据（不推荐）
                df = pd.read_csv(file_path, usecols=self.required_columns, low_memory=False)
            else:
                # 只读取指定股票的数据
                df = pd.read_csv(file_path, usecols=self.required_columns, low_memory=False)
                # 确保sc列是字符串类型，symbols也是字符串类型
                df['sc'] = df['sc'].astype(str)
                symbols = [str(s) for s in symbols]
                
                df = df[df['sc'].isin(symbols)]
            
            # 按股票分组，每个股票只保留最后20行
            self.cached_data[date] = {}
            for symbol, group in df.groupby('sc'):
                # 按ts_1m升序排序，取最后20行
                last_20_rows = group.sort_values('ts_1m').tail(20)
                
                # 只转换这20行
                bars = self._convert_rows_to_bardata(last_20_rows, symbol, date)
                self.cached_data[date][symbol] = bars
                
            print(f"成功加载 {date} 的数据，包含 {len(self.cached_data[date])} 个股票")
            
        except Exception as e:
            print(f"加载数据失败: {e}")
            import traceback
            traceback.print_exc()
            self.cached_data[date] = {}
    
    def _convert_rows_to_bardata(self, df_rows, symbol: str, date: str) -> List[BarData]:
        """
        将DataFrame行转换为BarData列表
        只处理传入的有限行数
        """
        bars = []
        base_date = datetime.strptime(date, "%Y%m%d").date()
        
        for _, row in df_rows.iterrows():
            # ts_1m范围：540~930 (09:00~15:30)
            minutes_from_midnight = int(row['ts_1m'])
            
            # 计算具体时间
            hour = minutes_from_midnight // 60
            minute = minutes_from_midnight % 60
            bar_datetime = datetime.combine(base_date, time(hour, minute))
            
            bar = BarData(
                symbol=symbol,
                exchange=Exchange.TSE,
                datetime=bar_datetime,
                interval=Interval.MINUTE,
                volume=int(row['vol']),
                turnover=float(row['turnover']),
                open_price=float(row['o']),
                high_price=float(row['h']),
                low_price=float(row['l']),
                close_price=float(row['c']),
                gateway_name="BriskData"
            )
            bars.append(bar)
        
        return bars
    
    def get_historical_bars(self, symbol: str, date: str, count: int = 20) -> List[BarData]:
        """获取历史bar数据"""
        # 检查缓存
        if date not in self.cached_data or symbol not in self.cached_data[date]:
            # 只加载这一个股票的数据
            self.load_daily_data(date, [symbol])
        
        # 从缓存返回数据
        if date in self.cached_data and symbol in self.cached_data[date]:
            bars = self.cached_data[date][symbol]
            return bars[-count:] if len(bars) >= count else bars
        else:
            print(f"警告: 无法获取 {symbol} 在 {date} 的数据")
            return []
    
    def is_data_available(self, symbol: str, date: str) -> bool:
        """检查数据是否可用"""
        file_path = f"{self.data_dir}/brisk_ohlc_{date}_ts_1m.csv"
        return os.path.exists(file_path)
    
    def get_multiple_symbols_data(self, symbols: List[str], date: str, count: int = 20) -> Dict[str, List[BarData]]:
        """
        批量获取多个股票的数据，优化性能
        """
        # 检查哪些股票需要加载
        missing_symbols = []
        for symbol in symbols:
            if date not in self.cached_data or symbol not in self.cached_data[date]:
                missing_symbols.append(symbol)
        
        # 批量加载缺失的数据
        if missing_symbols:
            self.load_daily_data(date, missing_symbols)
        
        # 返回所有请求的数据
        result = {}
        for symbol in symbols:
            if date in self.cached_data and symbol in self.cached_data[date]:
                bars = self.cached_data[date][symbol]
                result[symbol] = bars[-count:] if len(bars) >= count else bars
            else:
                result[symbol] = []
        
        return result
    
    def clear_cache(self, date: Optional[str] = None):
        """清除缓存"""
        if date is None:
            self.cached_data.clear()
            print("已清除所有缓存")
        elif date in self.cached_data:
            del self.cached_data[date]
            print(f"已清除 {date} 的缓存")
    
    def get_cache_info(self) -> Dict[str, Any]:
        """获取缓存信息"""
        total_symbols = sum(len(symbols) for symbols in self.cached_data.values())
        return {
            "cached_dates": list(self.cached_data.keys()),
            "total_symbols": total_symbols,
            "memory_usage": f"{len(self.cached_data)} dates, {total_symbols} symbols"
        }
