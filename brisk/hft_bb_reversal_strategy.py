"""
HFT BB Reversal Strategy
基于布林带反转的日内高频交易策略
"""

from os import truncate
import time as time_module
from datetime import datetime, timedelta, time
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, field
from stock_config import StockConfigManager

from vnpy.trader.object import BarData, TickData
from vnpy.trader.constant import Direction, Offset, OrderType, Status
from vnpy.trader.object import OrderRequest, CancelRequest
from vnpy.trader.event import EVENT_ORDER, EVENT_TRADE

from intraday_strategy_base import IntradayStrategyBase, StrategyState
from hft_bb_indicators import HFTBBReversalIndicatorV2 as HFTBBReversalIndicator, BriskHistoricalDataProvider
from enhanced_bargenerator import EnhancedBarGenerator
from common.trading_common import next_n_tick_price, topix500


@dataclass
class TriggerLevels:
    """触发价格水平"""
    upper_trigger: float    # 上轨触发价格
    upper_limit: float      # 上轨限价价格
    lower_trigger: float    # 下轨触发价格
    lower_limit: float      # 下轨限价价格


@dataclass
class StopLossConfig:
    """止损配置"""
    first_stage_threshold: float = 0.02   # 第一阶段止损阈值（百分比）
    second_stage_threshold: float = 0.05  # 第二阶段止损阈值（百分比）
    enabled: bool = True                  # 是否启用止损


@dataclass
class HFTBBStockContext:
    """HFT BB策略扩展的股票Context"""
    # 基础字段（复用base strategy的StockContext）
    symbol: str
    state: StrategyState = StrategyState.IDLE
    entry_order_id: str = ""
    exit_order_id: str = ""
    position: int = 0  # 持仓数量（正数为多头，负数为空头）
    
    # Base strategy需要的字段
    position_size: int = 100                # 持仓数量
    already_traded: int = 0                 # 已成交数量
    exit_price: float = 0.0                # exit成交价格
    entry_trigger_price: float = 0.0        # 触发价格（距离目标价格2个ATR）
    entry_trigger_order_price: float = 0.0  # 触发时的订单价格
    trade_count: int = 0                    # 当日交易次数
    timeout_trade_count: int = 0            # 完成的timeout exit交易数量
    entry_price: float = 0.0               # entry成交价格
    entry_time: Optional[datetime] = None  # entry成交时间
    exit_start_time: Optional[datetime] = None  # exit开始时间
    
    # HFT BB策略特定字段
    trigger_levels: Optional[TriggerLevels] = None  # 触发价格水平
    can_trade: List[str] = field(default_factory=list)  # X条件满足标志，存储允许的交易方向
    bb_levels: Optional[dict] = None                 # 布林带水平
    entry_order_price: float = 0.0                   # 入场订单价格
    exit_order_price: float = 0.0                    # 出场订单价格
    entry_order_time: Optional[datetime] = None      # 入场订单发送时间


class HFTBBReversalStrategy(IntradayStrategyBase):
    """HFT BB Reversal策略 - 基于布林带反转的日内高频交易策略"""
    
    def __init__(self, use_mock_gateway=False, use_real_data=False, data_dir="data/brisk_agged_ohlc", log_suffix=None):
        super().__init__(use_mock_gateway, log_suffix)
        
        # BB策略特定参数
        self.bb_period = 20
        self.bb_entry_std_multiplier = 3.0
        self.bb_exit_std_multiplier = -1.0
        self.trigger_tick_count = 3  # trigger价格调整的tick数量
        
        # X条件std_pct阈值参数
        self.std_pct_threshold_morning = 0.0007    # 早上9:05-9:35阈值
        self.std_pct_threshold_noon = 0.000001      # 中午11:29-11:30阈值（极小的值，几乎总是通过）
        self.std_pct_threshold_afternoon = 0.00030  # 下午14:35-15:20阈值
        
        # 价格限制配置（前一天收盘价上限）
        self.price_limit_morning = 4000    # 早上时段价格上限
        self.price_limit_noon = 4000       # 中午时段价格上限
        self.price_limit_afternoon = 3000  # 下午时段价格上限
        
        # 收盘前平仓参数
        self.market_close_liquidation_enabled = True  # 是否启用收盘前平仓
        self.market_close_time = time(15, 24)        # 普通交易结束时间
        self.liquidation_check_time = time(15, 26)   # 平仓检查时间
        self.liquidation_executed = False            # 是否已执行平仓
        
        # 模拟持仓管理
        self.simulated_positions = {}  # symbol -> {'long': bool, 'short': bool, 'long_entry_time': datetime, 'short_entry_time': datetime, 'long_exit_time': datetime, 'short_exit_time': datetime}
        
        # 单只股票最大持仓金额（日元）
        self.single_stock_max_position = 250_000
        self.stock_config_manager = StockConfigManager("configs/stock_configs.json")
        
        # 止损配置
        self.default_stop_loss_config = StopLossConfig(0.02, 0.05, True)
        self.stop_loss_by_time = {
            "morning": StopLossConfig(0.005, 0.0055, True),  # 早上更保守
            "noon": StopLossConfig(0.0045, 0.005, True),     # 中午稍微宽松
            "afternoon": StopLossConfig(0.005, 0.0055, True),  # 下午跟早上一样保守
        }

        self.indicator_size = 20  # 修改为20以匹配真实数据
        
        # 历史数据提供者
        self.use_real_data = use_real_data
        self.data_provider = None
        if use_real_data:
            self.data_provider = BriskHistoricalDataProvider(data_dir)
            self.write_log(f"启用真实数据模式，数据目录: {data_dir}")
        
        # 策略状态
        self.strategy_name = "HFT_BB_Reversal"
        
        # X条件相关参数
        self.x_condition_enabled = True  # 是否启用X条件
        
        # 统一的时间窗口配置
        self.time_windows = [
            {
                'start': time(9, 5),
                'end': time(9, 41),
                'threshold': self.std_pct_threshold_morning,
                'name': 'morning',
                'allowed_directions': ['long', 'short'],  # 早上窗口允许多空双向
                'exclude_minutes': []  # 排除的分钟（如15:00）
            },
            {
                'start': time(11, 25),
                'end': time(11, 31),
                'threshold': self.std_pct_threshold_noon,
                'name': 'noon',
                'allowed_directions': ['long', 'short'],  # 中午窗口允许多空双向
                'exclude_minutes': []  # 排除的分钟
            },
            {
                'start': time(14, 10),
                'end': time(15, 25),
                'threshold': self.std_pct_threshold_afternoon,
                'name': 'afternoon',
                'allowed_directions': ['long', 'short'],  # 下午窗口允许多空双向
                'exclude_minutes': [(14, 30), (15, 0)]  # 排除14:30和15:00分钟
            }
        ]
        
        # 为了向后兼容，保留简单的元组格式
        self.x_condition_time_windows = [(w['start'], w['end']) for w in self.time_windows]

        # 参数更新配置
        self.parameter_update_schedule = {
            time(9, 41): {
                'bb_entry_std_multiplier': 3.0,
                'bb_exit_std_multiplier': -0.5,
                'trigger_tick_count': 3
            }
        }
        
        # 参数更新历史
        self.parameter_updates = []
        
        # 参数更新状态
        self.parameter_update_completed = False
        
        # 注册参数更新定时器
        self._register_parameter_update_timer()

        self.write_log(f"策略初始化完成: {self.strategy_name}")
        
        # HFT BB策略特定的context管理
        self.hft_contexts: Dict[str, HFTBBStockContext] = {}
        
        # Eligible stock管理（使用black list功能）
        self.eligible_stocks = set()  # 真正满足所有条件的股票
    
    def get_hft_context(self, symbol: str) -> HFTBBStockContext:
        """获取HFT BB策略的股票Context"""
        if symbol not in self.hft_contexts:
            raise ValueError(f"HFT context for symbol {symbol} not found. Please ensure the symbol is subscribed first.")
        return self.hft_contexts[symbol]
    
    def create_hft_context(self, symbol: str) -> HFTBBStockContext:
        """创建HFT BB策略的股票Context"""
        if symbol in self.hft_contexts:
            self.write_log(f"Warning: HFT context for symbol {symbol} already exists, returning existing one.")
        else:
            # 使用基类的 calculate_position_size 方法计算基于价格的持仓数量
            position_size = self.calculate_position_size(symbol)
            self.hft_contexts[symbol] = HFTBBStockContext(symbol=symbol)
            self.hft_contexts[symbol].position_size = position_size
            self.write_log(f"Created HFT context for symbol {symbol} with position_size={position_size}")
        return self.hft_contexts[symbol]
    
    def check_x_condition(self, symbol: str, current_time: datetime = None) -> List[str]:
        """
        检查X条件是否满足，优先使用个股配置
        
        X条件包括：
        1. 股票是否在eligible_stocks中
        2. 模拟持仓检查 - 目前没有持仓
        3. 时间窗口检查 - 在指定的交易时间段内
        4. std_pct阈值检查 - 根据时间段检查不同的波动率阈值
        
        Args:
            symbol: 股票代码
            current_time: 当前时间，如果为None则使用系统当前时间
            
        Returns:
            List[str]: 允许的交易方向列表，如 ['long', 'short'] 或 []
        """
        if not self.x_condition_enabled:
            return ['long', 'short']
        
        # 检查个股是否有自定义配置
        stock_config = self.stock_config_manager.get_stock_config(symbol)
        if stock_config and stock_config.trading_windows:
            return self._check_custom_trading_windows(symbol, stock_config, current_time)
        else:
            # 使用默认的X条件检查逻辑
            return self._check_default_x_condition(symbol, current_time)
    
    def _check_custom_trading_windows(self, symbol: str, stock_config, current_time: datetime = None) -> List[str]:
        """检查自定义交易窗口（完全使用个股配置）"""
        if current_time is None:
            current_time = datetime.now()
        
        current_time_only = current_time.time()
        
        # 1. 检查股票是否在eligible_stocks中
        if symbol not in self.eligible_stocks:
            self.write_log(f"X条件检查失败: {symbol} 不在eligible_stocks中")
            return []
            
        # 2. 检查模拟持仓 - 目前没有持仓
        if not self._check_no_position(symbol):
            self.write_log(f"X条件检查失败: {symbol} 已有持仓")
            return []
        
        # 3. 检查是否在排除的分钟内
        for exclude_minute in stock_config.exclude_minutes:
            if self._is_time_in_exclude_minute(current_time_only, exclude_minute):
                self.write_log(f"X条件检查失败: {symbol} 在排除分钟内 {exclude_minute}")
                return []
        
        # 4. 检查是否在任何交易窗口内
        allowed_directions = set()
        for window in stock_config.trading_windows:
            if self._is_time_in_window(current_time_only, window.start_time, window.end_time):
                allowed_directions.update(window.allowed_directions)
        
        if allowed_directions:
            result = list(allowed_directions)
            self.write_log(f"X条件检查通过: {symbol} 自定义窗口 {result}")
            return result
        else:
            self.write_log(f"X条件检查失败: {symbol} 不在任何交易窗口内")
            return []
    
    def _check_default_x_condition(self, symbol: str, current_time: datetime = None) -> List[str]:
        """检查默认X条件（原有逻辑 + 模拟持仓智能检查）"""
        # 1. 检查股票是否在eligible_stocks中
        if symbol not in self.eligible_stocks:
            self.write_log(f"X条件检查失败: {symbol} 不在eligible_stocks中")
            return []
            
        # 2. 检查模拟持仓 - 智能检查逻辑
        if symbol in self.simulated_positions:
            positions = self.simulated_positions[symbol]
            if positions['long'] or positions['short']:
                # 获取模拟持仓的entry时间
                entry_time = positions['long_entry_time'] if positions['long'] else positions['short_entry_time']
                
                if entry_time is None:
                    self.write_log(f"X条件检查失败: {symbol} 模拟持仓entry时间为None")
                    return []
                
                # 检查entry时间是否在任意窗口内
                if not self._is_entry_time_in_any_window(entry_time):
                    self.write_log(f"X条件检查失败: {symbol} 模拟持仓entry时间不在任何交易窗口内")
                    return []
                
                # 获取模拟持仓方向
                simulated_direction = self._get_simulated_position_direction(symbol)
                if simulated_direction is None:
                    self.write_log(f"X条件检查失败: {symbol} 无法确定模拟持仓方向")
                    return []
                
                # 先获取时间窗口结果以确定允许的交易方向
                time_window_result = self._check_time_window_with_std_pct(symbol, current_time)
                if not time_window_result['in_window']:
                    self.write_log(f"X条件检查失败: 当前时间不在交易窗口内")
                    return []
                
                # 检查价格限制
                if not time_window_result['price_check_ok']:
                    self.write_log(f"X条件检查失败: {symbol} {time_window_result['price_check_reason']}")
                    return []
                    
                if not time_window_result['std_pct_ok']:
                    self.write_log(f"X条件检查失败: {symbol} std_pct={time_window_result['std_pct']:.6f} "
                                  f"低于{time_window_result['time_period']}阈值{time_window_result['threshold']:.6f}")
                    return []
                
                # 检查方向是否匹配
                allowed_directions = time_window_result['allowed_directions']
                if simulated_direction in allowed_directions:
                    self.write_log(f"X条件检查通过: {symbol} 模拟持仓方向匹配，允许{simulated_direction}交易")
                    return allowed_directions
                else:
                    self.write_log(f"X条件检查失败: {symbol} 模拟持仓方向{simulated_direction}与允许方向{allowed_directions}不匹配")
                    return []
        
        # 3. 没有模拟持仓或有模拟持仓记录但没有持仓，使用原有逻辑
        # if not self._check_no_position(symbol):
        #     self.write_log(f"X条件检查失败: {symbol} 已有持仓")
        #     return []
            
        # 3. 检查时间窗口和std_pct阈值
        time_window_result = self._check_time_window_with_std_pct(symbol, current_time)
        if not time_window_result['in_window']:
            self.write_log(f"X条件检查失败: 当前时间不在交易窗口内")
            return []
        
        # 4. 检查价格限制
        if not time_window_result['price_check_ok']:
            self.write_log(f"X条件检查失败: {symbol} {time_window_result['price_check_reason']}")
            return []
            
        if not time_window_result['std_pct_ok']:
            self.write_log(f"X条件检查失败: {symbol} std_pct={time_window_result['std_pct']:.6f} "
                          f"低于{time_window_result['time_period']}阈值{time_window_result['threshold']:.6f}")
            return []
            
        # 使用时间窗口配置的允许交易方向
        allowed_directions = time_window_result['allowed_directions']
        self.write_log(f"X条件检查通过: {symbol} {time_window_result['time_period']} "
                      f"std_pct={time_window_result['std_pct']:.6f} {time_window_result['price_check_reason']} 允许方向: {allowed_directions}")
        return allowed_directions
    
    def _is_entry_time_in_any_window(self, entry_time: datetime) -> bool:
        """
        检查entry时间是否在任意一个交易窗口内
        
        Args:
            entry_time: 模拟持仓的entry时间
            
        Returns:
            bool: 是否在任意窗口内
        """
        entry_time_only = entry_time.time()
        
        # 遍历所有交易窗口，检查entry_time是否在其中任何一个
        for window_start, window_end in self.x_condition_time_windows:
            if window_start <= entry_time_only <= window_end:
                return True
        return False
    
    def _get_simulated_position_direction(self, symbol: str) -> Optional[str]:
        """
        获取模拟持仓的方向
        
        Args:
            symbol: 股票代码
            
        Returns:
            str: 'long' 或 'short' 或 None
        """
        if symbol not in self.simulated_positions:
            return None
        
        positions = self.simulated_positions[symbol]
        if positions['long']:
            return 'long'
        elif positions['short']:
            return 'short'
        else:
            return None

    def _is_time_in_exclude_minute(self, current_time: time, exclude_minute: time) -> bool:
        """检查当前时间是否在排除的分钟内"""
        return (current_time.hour == exclude_minute.hour and 
                current_time.minute == exclude_minute.minute)
    
    def _is_time_in_window(self, current_time: time, start_time: time, end_time: time) -> bool:
        """检查当前时间是否在窗口内"""
        if start_time <= end_time:
            # 同一天内的窗口
            return start_time <= current_time < end_time
        else:
            # 跨天的窗口（如 23:00 到 01:00）
            return current_time >= start_time or current_time < end_time
    
    def get_eligible_stocks(self) -> set:
        """获取当前eligible_stocks列表"""
        return self.eligible_stocks.copy()
    
    def is_eligible_stock(self, symbol: str) -> bool:
        """检查股票是否在eligible_stocks中"""
        return symbol in self.eligible_stocks
    
    def _check_no_position(self, symbol: str) -> bool:
        """
        检查是否没有持仓
        
        Args:
            symbol: 股票代码
            
        Returns:
            bool: 是否没有持仓
        """
        if symbol not in self.simulated_positions:
            return True
            
        position = self.simulated_positions[symbol]
        has_long = position.get('long', False)
        has_short = position.get('short', False)
        
        return not (has_long or has_short)
    
    def _check_time_window(self, current_time: datetime = None) -> bool:
        """
        检查当前时间是否在交易窗口内
        
        Args:
            current_time: 当前时间，如果为None则使用系统当前时间
            
        Returns:
            bool: 是否在交易窗口内
        """
        if current_time is None:
            current_time = datetime.now()
            
        current_time_only = current_time.time()
        
        for start_time, end_time in self.x_condition_time_windows:
            if start_time <= current_time_only <= end_time:
                return True
                
        return False
    
    def _check_time_window_with_std_pct(self, symbol: str, current_time: datetime = None) -> dict:
        """
        检查当前时间是否在交易窗口内，并验证std_pct阈值
        
        Args:
            symbol: 股票代码
            current_time: 当前时间，如果为None则使用系统当前时间
            
        Returns:
            dict: 包含检查结果的字典
        """
        if current_time is None:
            current_time = datetime.now()
            
        current_time_only = current_time.time()
        
        # 获取前一天收盘价并检查价格限制
        try:
            prev_close = self.get_stock_prev_close(symbol)
            if prev_close is None:
                return {
                    'in_window': False,
                    'time_period': None,
                    'threshold': None,
                    'std_pct': None,
                    'std_pct_ok': False,
                    'allowed_directions': [],
                    'price_check_ok': False,
                    'price_check_reason': '无法获取前一天收盘价'
                }
        except Exception as e:
            return {
                'in_window': False,
                'time_period': None,
                'threshold': None,
                'std_pct': None,
                'std_pct_ok': False,
                'allowed_directions': [],
                'price_check_ok': False,
                'price_check_reason': f'获取前一天收盘价失败: {e}'
            }
        
        # 使用统一的时间窗口配置
        time_windows = self.time_windows
        
        # 检查是否在时间窗口内
        for window in time_windows:
            # 检查是否在时间窗口内
            if window['start'] <= current_time_only <= window['end']:
                # 检查是否在排除的分钟内
                is_excluded = False
                for exclude_hour, exclude_minute in window['exclude_minutes']:
                    if current_time_only.hour == exclude_hour and current_time_only.minute == exclude_minute:
                        is_excluded = True
                        break
                
                if not is_excluded:
                    # 在时间窗口内，检查价格限制
                    price_check_result = self._check_price_limit(prev_close, window['name'])
                    if not price_check_result['ok']:
                        return {
                            'in_window': True,
                            'time_period': window['name'],
                            'threshold': window['threshold'],
                            'std_pct': None,
                            'std_pct_ok': False,
                            'allowed_directions': [],
                            'price_check_ok': False,
                            'price_check_reason': price_check_result['reason']
                        }
                    
                    # 价格检查通过，检查std_pct
                    std_pct_result = self._calculate_and_check_std_pct(symbol, window['threshold'])
                    return {
                        'in_window': True,
                        'time_period': window['name'],
                        'threshold': window['threshold'],
                        'std_pct': std_pct_result['std_pct'],
                        'std_pct_ok': std_pct_result['ok'],
                        'allowed_directions': window['allowed_directions'],
                        'price_check_ok': True,
                        'price_check_reason': price_check_result['reason']
                    }
        
        return {
            'in_window': False,
            'time_period': None,
            'threshold': None,
            'std_pct': None,
            'std_pct_ok': False,
            'allowed_directions': [],
            'price_check_ok': True,
            'price_check_reason': '不在交易窗口内'
        }
    
    def _check_price_limit(self, prev_close: float, time_period: str) -> dict:
        """
        检查前一天收盘价是否满足时间段的限制
        
        Args:
            prev_close: 前一天收盘价
            time_period: 时间段 ('morning', 'noon', 'afternoon' 或自定义名称)
            
        Returns:
            dict: 包含检查结果的字典
        """
        # 获取对应时间段的价格限制
        price_limit_map = {
            'morning': self.price_limit_morning,
            'noon': self.price_limit_noon,
            'afternoon': self.price_limit_afternoon
        }
        
        # 如果时间段不在预定义列表中，使用默认的价格限制（最宽松的限制）
        if time_period not in price_limit_map:
            # 对于自定义时间段，使用最宽松的价格限制
            price_limit = max(self.price_limit_morning, self.price_limit_noon, self.price_limit_afternoon)
            return {
                'ok': True,
                'reason': f'{time_period}时段股价{prev_close}符合自定义时间段限制（使用默认限制{price_limit}）'
            }
        
        price_limit = price_limit_map[time_period]
        
        if prev_close >= price_limit:
            return {
                'ok': False,
                'reason': f'{time_period}时段股价{prev_close}超过{price_limit}限制'
            }
        else:
            return {
                'ok': True,
                'reason': f'{time_period}时段股价{prev_close}符合{price_limit}以下限制'
            }
    
    def _calculate_and_check_std_pct(self, symbol: str, threshold: float) -> dict:
        """
        计算并检查std_pct是否满足阈值
        
        Args:
            symbol: 股票代码
            threshold: 阈值
            
        Returns:
            dict: 包含std_pct计算结果和是否满足阈值
        """
        try:
            # 获取BB levels
            context = self.get_hft_context(symbol)
            if not context.bb_levels:
                return {'std_pct': 0.0, 'ok': False}
            
            bb_levels = context.bb_levels
            std = bb_levels.get('std', 0)
            middle = bb_levels.get('middle', 0)
            
            if middle == 0:
                return {'std_pct': 0.0, 'ok': False}
            
            # 计算std_pct
            std_pct = std / middle
            
            return {
                'std_pct': std_pct,
                'ok': std_pct > threshold
            }
            
        except Exception as e:
            self.write_log(f"计算std_pct失败: {e}")
            return {'std_pct': 0.0, 'ok': False}
    
    def preload_historical_data(self, symbols: List[str], date: str = None):
        """预加载历史数据"""
        if not self.use_real_data or not self.data_provider:
            self.write_log("未启用真实数据模式，跳过历史数据预加载")
            return
        
        if date is None:
            # 使用当前日期
            date = datetime.now().strftime("%Y%m%d")
        
        self.write_log(f"开始预加载历史数据: 日期={date}, 股票={symbols}")
        
        for symbol in symbols:
            try:
                # 获取历史数据
                historical_bars = self.data_provider.get_historical_bars(symbol, date, self.indicator_size)
                
                if len(historical_bars) >= self.bb_period:
                    # 创建指标管理器
                    if symbol not in self.indicator_managers:
                        self.indicator_managers[symbol] = self._create_indicator_manager(symbol)
                    
                    # 预加载历史数据
                    self.indicator_managers[symbol].preload_historical_bars(historical_bars)
                    
                    # 检查是否准备就绪
                    if self.indicator_managers[symbol].is_ready_for_trading():
                        self.write_log(f"✓ {symbol} 历史数据预加载成功，准备交易")
                        
                        # 获取初始BB水平并存储到context中
                        bb_levels = self.indicator_managers[symbol].get_bb_levels()
                        if bb_levels:
                            # 确保context存在，如果不存在则创建
                            if symbol not in self.hft_contexts:
                                self.create_hft_context(symbol)
                            context = self.get_hft_context(symbol)
                            context.bb_levels = bb_levels
                            self.write_log(f"  {symbol} 初始BB水平:")
                            self.write_log(f"    Upper: {bb_levels['upper']:.2f}")
                            self.write_log(f"    Lower: {bb_levels['lower']:.2f}")
                            self.write_log(f"    Middle: {bb_levels['middle']:.2f}")
                    else:
                        self.write_log(f"⚠ {symbol} 历史数据预加载完成但未准备交易")
                else:
                    self.write_log(f"✗ {symbol} 历史数据不足，需要{self.bb_period}个bar，实际{len(historical_bars)}个")
                    
            except Exception as e:
                self.write_log(f"✗ {symbol} 历史数据预加载失败: {e}")
    
    def add_symbol(self, symbol: str):
        """重写add_symbol方法，避免覆盖已预加载的指标管理器"""
        # 创建HFT context
        self.create_hft_context(symbol)
        
        # 添加股票到eligible_stocks（使用base strategy的black list功能）
        self.add_to_eligible_stocks(symbol)
        
        # 如果指标管理器已存在且已预加载，不要重新创建
        if symbol in self.indicator_managers and self.indicator_managers[symbol].is_preloaded:
            self.write_log(f"股票 {symbol} 的指标管理器已存在且已预加载，跳过重新创建")
            # 只创建BarGenerator
            self.bar_generators[symbol] = self._create_bar_generator(symbol)
            return
        
        # 否则调用父类方法
        super().add_symbol(symbol)
    
    def _create_indicator_manager(self, symbol: str):
        """创建BB策略专用的技术指标管理器，使用个股配置"""
        # 获取个股配置
        stock_config = self.stock_config_manager.get_stock_config(symbol)
        
        # 确定使用的参数
        if stock_config and stock_config.bb_entry_std_multiplier is not None:
            entry_std_multiplier = stock_config.bb_entry_std_multiplier
        else:
            entry_std_multiplier = self.bb_entry_std_multiplier
        
        if stock_config and stock_config.bb_exit_std_multiplier is not None:
            exit_std_multiplier = stock_config.bb_exit_std_multiplier
        else:
            exit_std_multiplier = self.bb_exit_std_multiplier
        
        return HFTBBReversalIndicator(
            symbol=symbol, 
            size=self.indicator_size,
            bb_period=self.bb_period,
            entry_std_multiplier=entry_std_multiplier,
            exit_std_multiplier=exit_std_multiplier
        )
    
    def _create_bar_generator(self, symbol: str):
        """创建BarGenerator - 使用1分钟K线"""
        return EnhancedBarGenerator(
            on_bar=self.on_1min_bar,
            window=1,  # 1分钟K线
            on_window_bar=self.on_1min_bar,  # 直接使用1分钟bar
            interval=self.bar_interval,
            enable_opening_volume=self.enable_opening_volume,
            enable_auto_flush=self.enable_auto_flush,
            main_engine=self.main_engine
        )
    
    def on_1min_bar(self, bar: BarData):
        """1分钟K线回调函数"""
        symbol = bar.symbol
        context = self.get_hft_context(symbol)
        
        self.write_log(f"收到1分钟K线: {symbol} {bar.datetime.strftime('%H:%M:%S')} "
                      f"开:{bar.open_price:.2f} 高:{bar.high_price:.2f} 低:{bar.low_price:.2f} "
                      f"收:{bar.close_price:.2f} 量:{bar.volume}")
        
        # 先调用父类方法（更新指标并打印信息）
        super().on_1min_bar(bar)
        
        # 1. 获取技术指标和触发价格（不再重复调用update_bar）
        if symbol in self.indicator_managers:
            indicators = self.indicator_managers[symbol].get_indicators()
            bb_levels = self._calculate_bb_levels(symbol, indicators)
            
            if bb_levels:
                # 更新BB水平和触发价格
                context.bb_levels = bb_levels
                context.trigger_levels = self._calculate_trigger_levels(symbol, bb_levels)
                
                self.write_log(f"更新BB价格水平: {symbol}")
                self.write_log(f"  Upper: {bb_levels['upper']:.4f} (Short Entry)")
                self.write_log(f"  Lower: {bb_levels['lower']:.4f} (Long Entry)")
                self.write_log(f"  Middle: {bb_levels['middle']:.4f} (SMA)")
                self.write_log(f"  Exit_Long: {bb_levels['exit_long']:.4f}")
                self.write_log(f"  Exit_Short: {bb_levels['exit_short']:.4f}")
                self.write_log(f"  STD: {bb_levels['std']:.4f}")
                
                if context.trigger_levels:
                    self.write_log(f"更新触发价格水平: {symbol}")
                    self.write_log(f"  上轨触发: {context.trigger_levels.upper_trigger:.4f}")
                    self.write_log(f"  上轨限价: {context.trigger_levels.upper_limit:.4f}")
                    self.write_log(f"  下轨触发: {context.trigger_levels.lower_trigger:.4f}")
                    self.write_log(f"  下轨限价: {context.trigger_levels.lower_limit:.4f}")
                
                # 2. 检查X条件并更新交易标志
                allowed_directions = self.check_x_condition(symbol)
                context.can_trade = allowed_directions
                
                # 3. 如果有持仓，维护出场订单
                if context.position != 0:
                    self._manage_exit_order(symbol, bb_levels, bar)
    
    def _calculate_bb_levels(self, symbol: str, indicators: dict) -> dict:
        """计算BB策略的各个价格水平"""
        # 新的HFTBBReversalIndicatorV2直接返回BB水平
        if 'upper' in indicators and 'lower' in indicators:
            return indicators
        
        # 兼容旧版本
        bb_levels = indicators.get('bb_levels', {})
        if bb_levels:
            return bb_levels
        
        return {}
    
    def on_tick(self, event):
        """Tick数据回调函数"""
        tick = event.data
        symbol = tick.symbol
        if symbol not in self.hft_contexts:
            self.create_hft_context(symbol)
        context = self.get_hft_context(symbol)

        # print(f"收到Tick: {symbol} {tick.datetime.strftime('%H:%M:%S')} {tick.last_price}")
        
        # 1. 先更新BarGenerator（可能触发on_1min_bar更新BB levels）
        if symbol in self.bar_generators:
            self.bar_generators[symbol].update_tick(tick)
        
        # 2. 再检查入场订单逻辑（使用最新的BB levels）
        if context.trigger_levels:
            self._check_entry_logic(symbol, tick, context)
        
        # 3. 更新模拟持仓（复用base strategy方法）
        self._update_simulated_positions(tick)
    
    def _update_simulated_positions(self, tick):
        """根据tick价格更新模拟持仓状态"""
        symbol = tick.symbol
        context = self.get_hft_context(symbol)
        if not context.bb_levels:
            return
        
        current_price = tick.last_price
        bb_levels = context.bb_levels
        
        # 初始化模拟持仓
        if symbol not in self.simulated_positions:
            self.simulated_positions[symbol] = {
                'long': False, 
                'short': False,
                'long_entry_time': None,
                'short_entry_time': None,
                'long_exit_time': None,
                'short_exit_time': None
            }
        
        positions = self.simulated_positions[symbol]
        current_time = datetime.now()
        
        # 检查entry信号（当前没有仓位时）
        if not positions['long'] and not positions['short']:
            # 检查long entry
            if current_price <= bb_levels['lower']:
                positions['long'] = True
                positions['long_entry_time'] = current_time
                self.write_log(f"模拟Long Entry触发: {symbol} 价格: {current_price:.2f} <= {bb_levels['lower']:.2f} 时间: {current_time.strftime('%H:%M:%S')}")
            
            # 检查short entry
            elif current_price >= bb_levels['upper']:
                positions['short'] = True
                positions['short_entry_time'] = current_time
                self.write_log(f"模拟Short Entry触发: {symbol} 价格: {current_price:.2f} >= {bb_levels['upper']:.2f} 时间: {current_time.strftime('%H:%M:%S')}")
        
        # 检查exit信号（当前有仓位时）
        elif positions['long']:
            # Long仓位平仓
            if current_price >= bb_levels['exit_long']:
                positions['long'] = False
                positions['long_exit_time'] = current_time
                entry_time_str = positions['long_entry_time'].strftime('%H:%M:%S') if positions['long_entry_time'] else '未知'
                self.write_log(f"模拟Long Exit触发: {symbol} 价格: {current_price:.2f} >= {bb_levels['exit_long']:.2f} 时间: {current_time.strftime('%H:%M:%S')} (持仓时长: {current_time - positions['long_entry_time'] if positions['long_entry_time'] else '未知'})")
        
        elif positions['short']:
            # Short仓位平仓
            if current_price <= bb_levels['exit_short']:
                positions['short'] = False
                positions['short_exit_time'] = current_time
                entry_time_str = positions['short_entry_time'].strftime('%H:%M:%S') if positions['short_entry_time'] else '未知'
                self.write_log(f"模拟Short Exit触发: {symbol} 价格: {current_price:.2f} <= {bb_levels['exit_short']:.2f} 时间: {current_time.strftime('%H:%M:%S')} (持仓时长: {current_time - positions['short_entry_time'] if positions['short_entry_time'] else '未知'})")
    
    def _find_hft_context_by_order_id(self, order_id: str) -> Optional[HFTBBStockContext]:
        """
        根据订单ID查找HFT context
        
        Args:
            order_id: 订单ID
            
        Returns:
            HFTBBStockContext或None
        """
        for symbol, context in self.hft_contexts.items():
            if context.entry_order_id == order_id or context.exit_order_id == order_id:
                return context
        return None
    
    def on_order(self, event):
        """
        订单状态变化回调
        
        根据设计文档，只处理ALLTRADED状态：
        1. 入场订单成交：更新position，清除entry_order_id，发送出场订单
        2. 出场订单成交：清除position，清除exit_order_id
        """
        order = event.data
        self.write_log(f"订单状态更新: {order.orderid} {order.symbol} {order.direction.value} {order.offset.value} "
                      f"状态: {order.status.value} 价格: {order.price:.2f} 数量: {order.volume}")
        
        # 记录部分成交情况
        if order.status == Status.PARTTRADED:
            self.write_log(f"部分成交: {order.symbol} {order.direction.value} {order.offset.value} "
                          f"已成交数量: {order.traded} 剩余数量: {order.volume - order.traded}")
            
            # 更新已成交数量和持仓
            context = self._find_hft_context_by_order_id(order.orderid)
            if context:
                context.already_traded = order.traded
                
                # 更新持仓（部分成交）
                if order.offset == Offset.OPEN:
                    if order.direction == Direction.LONG:
                        context.position = order.traded
                    else:  # SHORT
                        context.position = -order.traded
                elif order.offset == Offset.CLOSE:
                    if order.direction == Direction.LONG:
                        context.position += order.traded
                    else:  # SHORT
                        context.position -= order.traded
                
                self.write_log(f"更新持仓: {order.symbol} position={context.position} already_traded={context.already_traded}")
            
            return
        
        # 只处理完全成交的订单
        if order.status != Status.ALLTRADED:
            return
        
        # 查找对应的HFT context
        context = self._find_hft_context_by_order_id(order.orderid)
        if not context:
            self.write_log(f"警告: 未找到订单ID {order.orderid} 对应的HFT context")
            return
        
        # 处理入场订单成交
        if order.orderid == context.entry_order_id:
            self._handle_entry_filled(order.symbol, context, order)
        # 处理出场订单成交
        elif order.orderid == context.exit_order_id:
            self._handle_exit_filled(order.symbol, context, order)
        else:
            self.write_log(f"警告: 订单ID {order.orderid} 不匹配任何已知订单")
    
    def _handle_entry_filled(self, symbol: str, context: HFTBBStockContext, order):
        """
        处理入场订单成交
        
        Args:
            symbol: 股票代码
            context: HFT context
            order: 订单数据
        """
        # 更新持仓
        if order.direction == Direction.LONG:
            context.position = order.volume
        else:  # Direction.SHORT
            context.position = -order.volume
        
        # 清除入场订单信息
        context.entry_order_id = ""
        context.entry_order_time = None  # 清除订单发送时间
        context.entry_price = order.price
        context.entry_time = order.datetime
        
        # 更新状态
        self.update_context_state(symbol, StrategyState.HOLDING)
        
        self.write_log(f"入场订单成交: {symbol} {order.direction.value} 价格{order.price:.2f} 数量{order.volume}")
        
        # 立即发送出场订单
        if context.bb_levels:
            self._manage_exit_order(symbol, context.bb_levels, None)  # 没有bar时不执行止损
        else:
            self.write_log(f"警告: {symbol} 没有BB水平数据，无法发送出场订单")
    
    def _handle_exit_filled(self, symbol: str, context: HFTBBStockContext, order):
        """
        处理出场订单成交
        
        Args:
            symbol: 股票代码
            context: HFT context
            order: 订单数据
        """
        # 清除持仓
        context.position = 0
        
        # 清除出场订单信息
        context.exit_order_id = ""
        context.exit_price = order.price
        
        # 更新交易统计
        context.trade_count += 1
        
        # 更新状态
        self.update_context_state(symbol, StrategyState.IDLE)
        
        self.write_log(f"出场订单成交: {symbol} {order.direction.value} 价格{order.price:.2f} 数量{order.volume}")
    
    def on_trade(self, event):
        """成交回调"""
        trade = event.data
        self.write_log(f"成交: {trade.symbol} {trade.direction.value} {trade.offset.value} "
                      f"价格: {trade.price:.2f} 数量: {trade.volume}")
    
    def get_entry_direction(self, symbol: str) -> str:
        """获取指定股票的entry方向 - 暂时返回none，等待X条件实现"""
        # TODO: 实现X条件判断
        return 'none'
    
    def _calculate_entry_price(self, context, bar, indicators) -> float:
        """计算entry价格 - 基于BB指标"""
        bb_levels = indicators.get('bb_levels', {})
        if not bb_levels:
            return 0.0
        
        entry_direction = self.get_entry_direction(context.symbol)
        if entry_direction == 'long':
            return bb_levels.get('lower', 0.0)
        elif entry_direction == 'short':
            return bb_levels.get('upper', 0.0)
        
        return 0.0
    
    def _calculate_exit_price(self, context, bar, indicators) -> float:
        """计算exit价格 - 基于BB指标"""
        bb_levels = indicators.get('bb_levels', {})
        if not bb_levels:
            return 0.0
        
        entry_direction = self.get_entry_direction(context.symbol)
        if entry_direction == 'long':
            return bb_levels.get('exit_long', 0.0)
        elif entry_direction == 'short':
            return bb_levels.get('exit_short', 0.0)
        
        return 0.0
    
    def print_simulation_summary(self):
        """打印模拟持仓摘要"""
        print("\n=== 模拟持仓摘要 ===")
        for symbol, positions in self.simulated_positions.items():
            status = []
            if positions['long']:
                status.append("LONG")
            if positions['short']:
                status.append("SHORT")
            if not status:
                status.append("NONE")
            
            bb_info = ""
            context = self.get_hft_context(symbol)
            if context.bb_levels:
                bb = context.bb_levels
                bb_info = f" | BB: U={bb['upper']:.2f} L={bb['lower']:.2f} M={bb['middle']:.2f}"
            
            print(f"  {symbol}: {', '.join(status)}{bb_info}")
        
        # print("\n技术指标状态:")
        # for symbol in self.indicator_managers:
        #     manager = self.indicator_managers[symbol]
        #     if manager.is_inited():
        #         indicators = manager.get_indicators()
        #         if indicators:
        #             bb_info = f"BB已初始化 (周期: {indicators.get('period', 'N/A')})"
        #         else:
        #             bb_info = "BB未初始化"
        #         print(f"  {symbol}: {bb_info}")
        #     else:
        #         print(f"  {symbol}: 技术指标未初始化")

    def _register_market_close_timer(self):
        """注册收盘前平仓定时器"""
        if not self.market_close_liquidation_enabled or not self.event_engine:
            return
            
        from vnpy.trader.event import EVENT_TIMER
        self.event_engine.register(EVENT_TIMER, self._on_market_close_timer)
        self.write_log("收盘前平仓定时器已注册")

    def _on_market_close_timer(self, event):
        """收盘前平仓定时器回调"""
        current_time = datetime.now().time()
        
        # 每1分钟输出log验证执行
        if current_time.second <= 1:  # 每分钟的0秒输出
            self.write_log(f"收盘前平仓定时器运行中，当前时间: {current_time.strftime('%H:%M:%S')}, "
                          f"liquidation_executed: {self.liquidation_executed}")
        
        # 午休时间取消 entry orders (12:10 ~ 12:15)
        if time(12, 10) <= current_time <= time(12, 15):
            self._cancel_all_entry_orders_during_lunch_break()
            return  # 午休时间只处理取消订单，不执行其他逻辑
        
        if self.liquidation_executed:
            return  # 已经下了所有平仓订单，避免重复
            
        if current_time < self.liquidation_check_time:
            return  # 还没到检查时间
            
        self.write_log("开始执行收盘前平仓流程...")
        self._execute_market_close_liquidation()

    def _execute_market_close_liquidation(self):
        """执行收盘前平仓"""
        liquidation_count = 0
        failed_count = 0
        
        for symbol in list(self.hft_contexts.keys()):
            context = self.hft_contexts[symbol]

            # 检查是否已经在进行closing处理
            if context.state == StrategyState.WAITING_TIMEOUT_EXIT:
                self.write_log(f"跳过已在closing处理的股票: {symbol}")
                continue
                
            # 1. 取消entry订单
            if context.entry_order_id:
                self.write_log(f"取消entry订单: {symbol} {context.entry_order_id}")
                success = self._cancel_order_with_verification(context.entry_order_id, symbol)
                if success:
                    context.entry_order_id = ""
                    context.entry_order_time = None
                    liquidation_count += 1
                else:
                    failed_count += 1
                    self.write_log(f"取消entry订单失败: {symbol} {context.entry_order_id}")
                
                time_module.sleep(0.3)
                
            # 2. 处理exit订单
            if context.exit_order_id:
                # 取消原limit订单
                self.write_log(f"取消原exit订单: {symbol} {context.exit_order_id}")
                success = self._cancel_order_with_verification(context.exit_order_id, symbol)
                if not success:
                    failed_count += 1
                    self.write_log(f"取消exit订单失败: {symbol} {context.exit_order_id}")
                
                time_module.sleep(0.3)
                
            # 3. 发送market订单（如果有持仓）
            if context.position != 0:
                if context.position > 0:
                    # 多头持仓，卖出平仓
                    direction = Direction.SHORT
                else:
                    # 空头持仓，买入平仓
                    direction = Direction.LONG
                    
                # 发送market订单
                order_id = self._execute_exit(context, None, 0, direction, OrderType.MARKET)
                if order_id:
                    context.exit_order_id = order_id
                    context.state = StrategyState.WAITING_TIMEOUT_EXIT  # 标记为closing状态, override the status update in execute order
                    liquidation_count += 1
                    self.write_log(f"发送market平仓订单成功: {symbol} {order_id}")
                else:
                    failed_count += 1
                    self.write_log(f"发送market平仓订单失败: {symbol}")
                
                time_module.sleep(0.3)
        
        # 保险平仓机制
        self.write_log("开始执行保险平仓检查...")
        
        try:
            # 1. 通过 gateway 获取实际持仓
            positions = self.gateway.get_positions()
            if not positions:
                self.write_log("无法获取实际持仓数据，跳过保险平仓")
            else:
                # 2. 分析未覆盖的持仓并发送平仓订单
                for position in positions:
                    symbol = position["Symbol"]
                    leaves_qty = position["LeavesQty"]  # 总持有数量
                    hold_qty = position["HoldQty"]      # 被平仓订单锁定的数量
                    side = position["Side"]             # "1"=空头持仓, "2"=多头持仓
                    
                    # 计算未锁定的数量
                    uncovered_qty = leaves_qty - hold_qty
                    
                    if uncovered_qty > 0:
                        # 确定平仓方向（与持仓方向相反）
                        if side == "1":  # 空头持仓，需要买多平仓
                            direction = Direction.LONG
                        else:  # 多头持仓，需要卖空平仓
                            direction = Direction.SHORT
                        
                        # 创建临时的 context 用于发送订单
                        temp_context = type('TempContext', (), {
                            'symbol': symbol,
                            'position_size': uncovered_qty,
                            'already_traded': 0
                        })()
                        
                        # 发送 market 平仓订单
                        order_id = self._execute_order(
                            context=temp_context,
                            bar=None,
                            price=0,  # market order
                            direction=direction,
                            offset=Offset.CLOSE,
                            order_type=OrderType.MARKET,
                            reference_prefix="insurance_liquidation",
                            quantity=uncovered_qty
                        )
                        
                        if order_id:
                            self.write_log(f"保险平仓订单发送成功: {symbol} {direction} {uncovered_qty}股, 订单ID: {order_id}")
                            liquidation_count += 1
                        else:
                            self.write_log(f"保险平仓订单发送失败: {symbol} {direction} {uncovered_qty}股")
                            failed_count += 1
                        
                        time_module.sleep(0.5)  # 避免过于频繁的订单
                        
        except Exception as e:
            self.write_log(f"保险平仓检查异常: {e}")
            failed_count += 1  # 异常也算失败
        
        # 只有当没有失败时才设置liquidation_executed为True
        if failed_count == 0:
            self.liquidation_executed = True
            self.write_log(f"收盘前平仓订单发送完成，成功: {liquidation_count}个")
        else:
            self.write_log(f"收盘前平仓部分失败，成功: {liquidation_count}个，失败: {failed_count}个，将重试")

    def _cancel_all_entry_orders_during_lunch_break(self):
        """午休时间取消所有未成交的 entry orders"""
        cancelled_count = 0
        failed_count = 0
        
        self.write_log("午休时间开始，取消所有未成交的 entry orders")
        
        for symbol in list(self.hft_contexts.keys()):
            context = self.hft_contexts[symbol]
            
            # 只处理有 entry_order_id 且状态为 WAITING_ENTRY 的 context
            if context.entry_order_id and context.state == StrategyState.WAITING_ENTRY:
                success = self._cancel_order_with_verification(
                    context.entry_order_id, 
                    symbol
                )
                
                if success:
                    cancelled_count += 1
                    # 更新 context 状态
                    context.entry_order_id = ""
                    context.entry_order_time = None
                    self.update_context_state(symbol, StrategyState.IDLE)
                    self.write_log(f"午休取消 entry 订单成功: {symbol}")
                else:
                    failed_count += 1
                    self.write_log(f"午休取消 entry 订单失败: {symbol}")
                
                # 每个取消操作之间sleep 0.5秒防止过度调用API
                time_module.sleep(0.5)
        
        self.write_log(f"午休取消 entry 订单完成: 成功 {cancelled_count} 个，失败 {failed_count} 个")

    def _register_parameter_update_timer(self):
        """注册参数更新定时器"""
        if not self.event_engine:
            return
            
        from vnpy.trader.event import EVENT_TIMER
        self.event_engine.register(EVENT_TIMER, self._on_parameter_update_timer)
        self.write_log("参数更新定时器已注册")

    def _on_parameter_update_timer(self, event):
        """参数更新定时器回调"""
        # 如果已经完成参数更新，直接返回
        if self.parameter_update_completed:
            return
            
        current_time = datetime.now().time()
        
        # 检查是否有需要更新的参数
        for update_time, params in self.parameter_update_schedule.items():
            if self._is_time_matching(current_time, update_time):
                self._execute_parameter_update(params)
                return

    def _is_time_matching(self, current_time: time, target_time: time) -> bool:
        """检查当前时间是否匹配目标时间（允许1秒误差）"""
        time_diff = abs((current_time.hour * 3600 + current_time.minute * 60 + current_time.second) - 
                       (target_time.hour * 3600 + target_time.minute * 60))
        return time_diff <= 5  # 允许5秒误差

    def _execute_parameter_update(self, params: dict):
        """执行参数更新"""
        try:
            self.update_parameters(params)
            self.write_log(f"参数更新成功: {params}")
            
            # 标记参数更新完成
            self.parameter_update_completed = True
            
            # 取消定时器注册以节省运算开支
            self._unregister_parameter_update_timer()
            
        except Exception as e:
            self.write_log(f"参数更新失败: {e}")

    def _unregister_parameter_update_timer(self):
        """取消参数更新定时器注册"""
        if self.event_engine:
            from vnpy.trader.event import EVENT_TIMER
            self.event_engine.unregister(EVENT_TIMER, self._on_parameter_update_timer)
            self.write_log("已取消参数更新定时器注册")

    def update_parameters(self, new_params: dict):
        """更新策略参数"""
        # 记录更新前的参数
        old_params = {
            'bb_entry_std_multiplier': self.bb_entry_std_multiplier,
            'bb_exit_std_multiplier': self.bb_exit_std_multiplier,
            'trigger_tick_count': self.trigger_tick_count,
            'single_stock_max_position': self.single_stock_max_position
        }
        
        # 更新策略参数
        if 'bb_entry_std_multiplier' in new_params:
            self.bb_entry_std_multiplier = new_params['bb_entry_std_multiplier']
        if 'bb_exit_std_multiplier' in new_params:
            self.bb_exit_std_multiplier = new_params['bb_exit_std_multiplier']
        if 'trigger_tick_count' in new_params:
            self.trigger_tick_count = new_params['trigger_tick_count']
        if 'single_stock_max_position' in new_params:
            old_value = self.single_stock_max_position
            self.single_stock_max_position = new_params['single_stock_max_position']
            self.write_log(f"参数 single_stock_max_position 更新: {old_value} -> {self.single_stock_max_position}")
            
            # 重新计算所有现有 context 的 position_size
            for symbol, context in self.hft_contexts.items():
                new_position_size = self.calculate_position_size(symbol)
                context.position_size = new_position_size
                self.write_log(f"更新 {symbol} 的持仓数量: {new_position_size}")
        
        # 更新所有技术指标管理器的参数
        self._update_indicator_managers_parameters()
        
        # 记录更新历史
        self.parameter_updates.append({
            'timestamp': datetime.now(),
            'old_parameters': old_params,
            'new_parameters': new_params
        })
        
        self.write_log(f"策略参数已更新: {old_params} -> {new_params}")

    def _update_indicator_managers_parameters(self):
        """更新所有技术指标管理器的参数"""
        for symbol, manager in self.indicator_managers.items():
            if hasattr(manager, 'update_parameters'):
                manager.update_parameters(
                    entry_std_multiplier=self.bb_entry_std_multiplier,
                    exit_std_multiplier=self.bb_exit_std_multiplier
                )
                self.write_log(f"已更新 {symbol} 的技术指标参数")

    def _calculate_trigger_levels(self, symbol: str, bb_levels: dict) -> Optional[TriggerLevels]:
        """
        计算触发价格水平
        
        Args:
            symbol: 股票代码
            bb_levels: 布林带水平字典
            
        Returns:
            TriggerLevels: 触发价格水平对象，计算失败返回None
        """
        try:
            upper_bb = bb_levels.get('upper')
            lower_bb = bb_levels.get('lower')
            middle_bb = bb_levels.get('middle')
            
            if upper_bb is None or lower_bb is None or middle_bb is None:
                self.write_log(f"布林带数据不完整: {bb_levels}")
                return None
            
            # 计算触发价格
            # upper_limit和lower_limit直接使用BB价格（已在tech indicator中tick对齐）
            upper_limit = upper_bb
            lower_limit = lower_bb
            
            # trigger价格使用next_n_tick_price进行调整
            # upper_trigger: 从upper_bb向下调整trigger_tick_count个tick
            upper_trigger = next_n_tick_price(self.trigger_tick_count, symbol, upper_bb, upside=False)
            
            # lower_trigger: 从lower_bb向上调整trigger_tick_count个tick  
            lower_trigger = next_n_tick_price(self.trigger_tick_count, symbol, lower_bb, upside=True)
            
            return TriggerLevels(
                upper_trigger=upper_trigger,
                upper_limit=upper_limit,
                lower_trigger=lower_trigger,
                lower_limit=lower_limit
            )
            
        except Exception as e:
            self.write_log(f"计算触发价格失败: {e}")
            return None

    def _manage_exit_order(self, symbol: str, bb_levels: dict, bar: BarData = None):
        """
        管理出场订单
        
        Args:
            symbol: 股票代码
            bb_levels: 布林带水平
            bar: K线数据，用于获取最新价格进行止损判断
        """
        context = self.get_hft_context(symbol)
        
        if context.position == 0:
            return  # 无持仓，不需要出场订单
        
        # 获取当前价格（优先使用bar的收盘价，如果没有bar则不执行止损）
        if bar is not None:
            current_price = bar.close_price
            # 检查是否需要止损
            stop_loss_price = self._check_stop_loss(symbol, context, current_price)
        else:
            current_price = bb_levels.get('middle', 0)
            stop_loss_price = None  # 没有bar时不执行止损
        
        if stop_loss_price is not None:
            # 使用止损价格
            exit_price = stop_loss_price
            is_second_stage = self._is_second_stage_stop_loss(symbol, context, current_price)
            loss_pct = self._calculate_loss_percentage(context, current_price)
            stage = "第二阶段" if is_second_stage else "第一阶段"
            self.write_log(f"止损出场: {symbol} {stage} 损失{loss_pct:.2%} 价格{exit_price:.2f}")
        else:
            # 使用原有的BB逻辑
            if context.position > 0:
                # 多头持仓，需要卖出平仓
                exit_price = bb_levels.get('exit_long', 0)  # 使用exit_long作为出场价格
                self.write_log(f"管理出场订单: {symbol} 多头持仓{context.position}，出场价格: {exit_price:.2f}")
            else:
                # 空头持仓，需要买入平仓
                exit_price = bb_levels.get('exit_short', 0)  # 使用exit_short作为出场价格
                self.write_log(f"管理出场订单: {symbol} 空头持仓{abs(context.position)}，出场价格: {exit_price:.2f}")
        
        # 确定出场方向
        if context.position > 0:
            exit_direction = Direction.SHORT
        else:
            exit_direction = Direction.LONG
        
        # 检查是否有部分成交的入场订单需要取消
        if (context.entry_order_id and 
            context.already_traded > 0 and 
            context.already_traded < context.position_size):
            # 取消部分成交的入场订单
            self.write_log(f"取消部分成交的入场订单: {symbol} 已成交{context.already_traded}")
            if self._cancel_order_with_verification(context.entry_order_id, symbol):
                context.entry_order_id = ""
                context.entry_order_time = None
        
        # 检查是否需要更新出场订单
        if context.exit_order_id:
            # 已有出场订单，检查价格是否需要更新
            if abs(context.exit_price - exit_price) > 0.1:  # 价格差异超过0.01
                # 取消旧订单
                if self._cancel_order_with_verification(context.exit_order_id, symbol):
                    context.exit_order_id = ""
                    self.write_log(f"取消旧出场订单: {symbol} 价格差异过大")
                else:
                    self.write_log(f"取消旧出场订单失败: {symbol} 价格差异过大")
            else:
                # 价格相同，无需更新
                self.write_log(f"价格相同，无需更新出场订单: {symbol} 价格{exit_price:.2f}")
                return
        
        # 发送新的出场订单
        if exit_price > 0:
            # 关键：调整already_traded为position_size - 实际持仓
            # 这样base strategy会计算正确的数量
            context.already_traded = context.position_size - abs(context.position)
            
            self.write_log(f"调整already_traded为{context.already_traded} "
                          f"用于发送{abs(context.position)}股exit订单")
            
            # 确定订单类型
            if stop_loss_price is not None and self._is_second_stage_stop_loss(symbol, context, current_price):
                # 第二阶段止损使用market order
                order_type = OrderType.MARKET
                self.write_log(f"使用市价单进行第二阶段止损: {symbol}")
            else:
                # 其他情况使用limit order
                order_type = OrderType.LIMIT
            
            # _execute_exit会自动更新context.exit_order_id, context.exit_price等字段
            order_id = self._execute_exit(context, None, exit_price, exit_direction, order_type)
            if order_id:
                order_type_str = "市价单" if order_type == OrderType.MARKET else "限价单"
                self.write_log(f"发送出场订单成功: {symbol} {exit_direction.value} 价格{exit_price:.2f} {order_type_str} 订单ID: {order_id}")
            else:
                self.write_log(f"发送出场订单失败: {symbol} {exit_direction.value} 价格{exit_price:.2f}")
    
    def _check_stop_loss(self, symbol: str, context: HFTBBStockContext, current_price: float) -> Optional[float]:
        """
        检查是否需要止损
        
        Args:
            symbol: 股票代码
            context: 股票上下文
            current_price: 当前价格
            
        Returns:
            Optional[float]: 如果需要止损返回止损价格，否则返回None
        """
        # 1. 获取止损配置
        stop_loss_config = self._get_stop_loss_config(symbol)
        if not stop_loss_config or not stop_loss_config.enabled:
            return None
        
        # 2. 计算损失百分比
        loss_pct = self._calculate_loss_percentage(context, current_price)
        
        # 3. 检查止损条件
        if loss_pct >= stop_loss_config.first_stage_threshold:
            return current_price  # 使用当前价格作为止损价格
        else:
            return None
    
    def _is_second_stage_stop_loss(self, symbol: str, context: HFTBBStockContext, current_price: float) -> bool:
        """检查是否为第二阶段止损（需要market order）"""
        stop_loss_config = self._get_stop_loss_config(symbol)
        if not stop_loss_config:
            return False
        
        loss_pct = self._calculate_loss_percentage(context, current_price)
        return loss_pct >= stop_loss_config.second_stage_threshold
    
    def _calculate_loss_percentage(self, context: HFTBBStockContext, current_price: float) -> float:
        """计算损失百分比"""
        if context.position == 0 or context.entry_price == 0:
            return 0.0
        
        if context.position > 0:  # 多头持仓
            loss_pct = (context.entry_price - current_price) / context.entry_price
        else:  # 空头持仓
            loss_pct = (current_price - context.entry_price) / context.entry_price
        
        return max(0.0, loss_pct)  # 只返回正数（损失）
    
    def _get_stop_loss_config(self, symbol: str) -> Optional[StopLossConfig]:
        """获取止损配置"""
        # 1. 检查个股配置
        stock_config = self.stock_config_manager.get_stock_config(symbol)
        if stock_config and hasattr(stock_config, 'stop_loss_config') and stock_config.stop_loss_config:
            return stock_config.stop_loss_config
        
        # 2. 使用全局时间段配置
        current_time = datetime.now().time()
        time_period = self._get_time_period(current_time)
        config = self.stop_loss_by_time.get(time_period, self.default_stop_loss_config)
        return config
    
    def _get_time_period(self, current_time: time) -> str:
        """根据时间确定时间段"""
        if time(9, 0) <= current_time <= time(11, 30):
            return "morning"
        elif time(11, 30) <= current_time <= time(13, 0):
            return "noon"
        elif time(13, 0) <= current_time <= time(15, 25):
            return "afternoon"
        else:
            return "default"

    def _check_entry_logic(self, symbol: str, tick, context: HFTBBStockContext):
        """
        检查入场逻辑
        
        Args:
            symbol: 股票代码
            tick: Tick数据
            context: 股票上下文
        """
        # 如果已经有持仓，不应该再下entry订单
        if context.position != 0:
            self.write_log(f"跳过entry逻辑: {symbol} 已有持仓 {context.position}")
            return
            
        # 如果已经有exit订单，也不应该再下entry订单
        if context.exit_order_id:
            self.write_log(f"跳过entry逻辑: {symbol} 已有exit订单")
            return
        
        # 如果X条件不满足，取消现有的entry订单
        if context.entry_order_id and not context.can_trade:
            self.write_log(f"X条件不满足，取消entry订单: {symbol}")
            self._cancel_entry_order(symbol, context)
            return
        
        # self.write_log(f"检查入场逻辑: {symbol} 价格{tick.last_price:.2f}")
        trigger_levels = context.trigger_levels
        current_price = tick.last_price
        
        # 检查是否需要下单
        should_order = False
        order_direction = None
        order_price = 0.0
        
        # 检查上轨触发
        if current_price >= trigger_levels.upper_trigger:
            order_direction = Direction.SHORT  # 总是设置方向
            if not context.entry_order_id and 'short' in context.can_trade:
                should_order = True
                self.write_log(f"触发上轨: {symbol} 价格{current_price:.2f} >= 触发价格{trigger_levels.upper_trigger:.2f}")
            order_price = trigger_levels.upper_limit
        
        # 检查下轨触发
        elif current_price <= trigger_levels.lower_trigger :
            order_direction = Direction.LONG  # 总是设置方向
            if not context.entry_order_id and 'long' in context.can_trade:
                should_order = True
                self.write_log(f"触发下轨: {symbol} 价格{current_price:.2f} <= 触发价格{trigger_levels.lower_trigger:.2f}")
            order_price = trigger_levels.lower_limit

        # 检查是否需要取消订单
        should_cancel = False
        new_order_info = None  # 用于存储新订单信息
        
        if context.entry_order_id:
            # 检查是否在同一分钟内发送的订单，如果是则不取消
            current_time = datetime.now()
            if context.entry_order_time:
                # 检查是否在同一分钟内
                time_diff = current_time - context.entry_order_time
                if time_diff.total_seconds() < 60:  # 同一分钟内
                    self.write_log(f"跳过取消订单: {symbol} 订单在同一分钟内发送，避免频繁撤单")
                    return  # 直接返回，不执行任何订单操作
            
            # 检查是否在中午休市时间（11:30-11:31），如果是则不取消订单
            current_hour = current_time.hour
            current_minute = current_time.minute
            if current_hour == 11 and current_minute >= 30 and current_minute <= 31:
                self.write_log(f"跳过取消订单: {symbol} 当前时间在中午休市期间({current_time.strftime('%H:%M')})，broker不接受新订单")
                return  # 直接返回，不执行任何订单操作
            
            # 检查是否在15:24分钟，如果是则不取消订单（避免收盘前频繁撤单损耗API配额）
            if current_hour == 15 and current_minute == 24:
                self.write_log(f"跳过取消订单: {symbol} 当前时间在15:24分钟({current_time.strftime('%H:%M')})，避免收盘前频繁撤单损耗API配额")
                return  # 直接返回，不执行任何订单操作
            
            # 如果当前价格在两个触发价格之间，取消订单（不立即下新订单）
            if (trigger_levels.lower_trigger < current_price < trigger_levels.upper_trigger):
                should_cancel = True
                self.write_log(f"取消订单原因: 价格在触发区间内 {current_price:.2f}")
            # 如果订单价格与当前应该下的价格不同，取消订单并准备下新订单
            elif context.entry_price != order_price and order_price > 0:
                should_cancel = True
                # 重新检查can_trade限制
                if order_direction == Direction.LONG and 'long' in context.can_trade:
                    new_order_info = (order_direction, order_price, context.position_size)
                    self.write_log(f"取消订单原因: 价格不同 当前:{context.entry_price:.2f} 应该:{order_price:.2f} 将重下多头订单")
                elif order_direction == Direction.SHORT and 'short' in context.can_trade:
                    new_order_info = (order_direction, order_price, context.position_size)
                    self.write_log(f"取消订单原因: 价格不同 当前:{context.entry_price:.2f} 应该:{order_price:.2f} 将重下空头订单")
                else:
                    # 不允许的方向，只取消不重下
                    new_order_info = None
                    direction_str = 'long' if order_direction == Direction.LONG else 'short'
                    self.write_log(f"取消订单原因: 价格不同 当前:{context.entry_price:.2f} 应该:{order_price:.2f} 但不重下订单(方向{direction_str}不在允许范围内)")
        
        # 执行订单操作
        if should_cancel:
            self._cancel_entry_order(symbol, context, new_order_info)
        elif not context.entry_order_id and should_order:
            self._send_entry_order(symbol, order_direction, order_price, context.position_size)  # 使用context中的position_size

    def update_context_state(self, symbol: str, new_state: StrategyState):
        """更新 HFT Context 状态"""
        context = self.get_hft_context(symbol)
        old_state = context.state
        context.state = new_state
        self.write_log(f"Context state changed for {symbol}: {old_state.value} -> {new_state.value}")

    def _cancel_entry_order(self, symbol: str, context: HFTBBStockContext, new_order_info=None):
        """
        取消入场订单
        
        Args:
            symbol: 股票代码
            context: 股票上下文
            new_order_info: 新订单信息，格式为 (direction, price, quantity)，如果提供则在取消成功后立即下新订单
        """
        if context.entry_order_id:
            # 使用增强的撤单方法
            success = self._cancel_order_with_verification(
                context.entry_order_id, 
                symbol
            )
            
            if success:
                # 撤单成功，立即更新状态
                self.write_log(f"取消入场订单成功: {symbol} 订单ID: {context.entry_order_id}")
                # actually this is risky because the cancel API might return True even the cancel failed in the broker side, 
                # this edge case only happens when cancel is right after send order in a very short interval
                context.entry_order_id = ""
                context.entry_order_time = None
                self.update_context_state(symbol, StrategyState.IDLE)
                
                # 如果提供了新订单信息，立即下新订单
                if new_order_info:
                    direction, price, quantity = new_order_info
                    self.write_log(f"价格变化，立即下新订单: {symbol} {direction.value} {price:.2f}")
                    self._send_entry_order(symbol, direction, price, quantity)
            else:
                # 撤单失败，不更新状态，等待on_order事件处理
                self.write_log(f"取消入场订单失败，等待订单状态更新: {symbol} 订单ID: {context.entry_order_id}")
                # 注意：不更新context状态，让on_order事件自然处理

    def _send_entry_order(self, symbol: str, direction: Direction, price: float, quantity: int = None):
        """
        发送入场订单
        
        Args:
            symbol: 股票代码
            direction: 交易方向
            price: 订单价格
            quantity: 订单数量（已弃用，数量从context.position_size中获取）
        """
        context = self.get_hft_context(symbol)
        
        # 使用base strategy的入场订单执行方法
        # 注意：_execute_entry需要bar参数，但在on_tick中我们没有bar，所以传递None
        # _execute_entry会自动更新context.entry_order_id, context.entry_price等字段
        # 订单数量从context.position_size中获取，quantity参数已弃用
        self._execute_entry(context, None, price, direction)
        
        # 检查订单是否成功发送
        if context.entry_order_id:
            # 更新订单发送时间
            context.entry_order_time = datetime.now()
            self.write_log(f"发送入场订单成功: {symbol} {direction.value} 价格{price:.2f} 订单ID: {context.entry_order_id}")
        else:
            self.write_log(f"发送入场订单失败: {symbol} {direction.value} 价格{price:.2f}")
    
    def _update_strategy_specific_params(self, params: Dict[str, Any]):
        """更新HFT BB Reversal策略特定参数"""
        # 更新价格限制参数
        price_limit_params = [
            'price_limit_morning',
            'price_limit_noon', 
            'price_limit_afternoon'
        ]
        
        for param in price_limit_params:
            if param in params:
                old_value = getattr(self, param, None)
                new_value = params[param]
                setattr(self, param, new_value)
                self.write_log(f"价格限制参数 {param} 更新: {old_value} -> {new_value}")
        
        # 更新其他策略特定参数（如果需要的话）
        other_params = [
            'bb_entry_std_multiplier',
            'bb_exit_std_multiplier',
            'trigger_tick_count'
        ]
        
        for param in other_params:
            if param in params:
                old_value = getattr(self, param, None)
                new_value = params[param]
                setattr(self, param, new_value)
                self.write_log(f"策略参数 {param} 更新: {old_value} -> {new_value}")


def main():
    """主函数"""
    import argparse
    
    # 设置命令行参数解析
    parser = argparse.ArgumentParser(description='HFT BB Reversal策略')
    parser.add_argument('--profile', type=str, default='600_2000', 
                       choices=['600_2000', '2000_4000', '600_4000'],
                       help='选择运行profile (默认: 600_2000)')
    parser.add_argument('--mock', action='store_true', default=False,
                       help='使用模拟数据')
    parser.add_argument('--debug', action='store_true', default=True,
                       help='启用调试模式')
    
    args = parser.parse_args()
    
    print("启动HFT BB Reversal策略...")
    print(f"使用Profile: {args.profile}")
    
    using_mock_data = args.mock
    debug = args.debug

    # 定义所有可用的profiles
    profiles = {
        '600_2000': {
            'log_suffix': '600_2000',
            'low_price': 600,
            'high_price': 2000,
        },
        '2000_4000': {
            'log_suffix': '2000_4000',
            'low_price': 2000,
            'high_price': 4000,
        },
        '600_4000': {
            'log_suffix': '600_4000',
            'low_price': 600,
            'high_price': 4000,
        }
    }
    
    # 根据命令行参数选择profile
    if args.profile not in profiles:
        print(f"错误: 不支持的profile '{args.profile}'")
        print(f"支持的profiles: {list(profiles.keys())}")
        return
    
    profile = profiles[args.profile]
    print(f"Profile配置: {profile}")

    # 创建策略实例
    strategy = HFTBBReversalStrategy(use_mock_gateway=using_mock_data, use_real_data=True, data_dir="data/brisk_agged_ohlc", log_suffix=profile['log_suffix'])
    
    try:
        # 连接Gateway
        mock_setting = {
            "tick_mode": "replay",
            # "replay_data_dir": "D:\\dev\\github\\brisk-hack\\brisk_in_day_frames",
            "replay_data_dir": "F:\\brisk_in_day_frames",
            "replay_date": "20250909",  # 根据实际数据文件调整
            "replay_speed": 100.0,       # 100倍速回放
            "mock_account_balance": 10000000,
        }
        
        # 连接Gateway
        strategy.connect(mock_setting)
        
        # 订阅股票
        # we will be using a static symbols list for this strategy, it should be a subset of TOPIX500
        symbols = []
        if using_mock_data:
            symbols = ["9501"]
        else:
            strategy.initialize_stock_master()
            for symbol in topix500:
                prev_close = strategy.get_stock_prev_close(symbol)
                # 600~1500 63 stocks
                # 600~2000 contains ~140 stocks, we will do further filter in x_condition
                # 2000~3000 contains 97 stock
                # 3000~4000 contains 89 stock
                # 4000~5000 contains 66 stock
                # 5000~10000 contains 76 stocks
                # >10000 only 29 stocks
                if profile['high_price'] >= prev_close > profile['low_price']:
                    symbols.append(symbol)
                # after noon use 1500 >= prev_close > 1000
        
        print(f"订阅股票: {symbols}")
        print(f"订阅股票数量: {len(symbols)}")

        if using_mock_data:
            preload_yyyymmdd = "20250908"
        else:
            from common.date_utils import prev_working_day
            preload_yyyymmdd = prev_working_day(datetime.now().strftime("%Y%m%d"))

        # strategy.preload_historical_data(symbols, preload_yyyymmdd)
        strategy.subscribe(symbols)
        
        # 注册收盘前平仓定时器
        strategy._register_market_close_timer()
        
        # 设置动态参数配置提供者
        from util.yaml_config_provider import YAMLConfigurationProvider
        strategy.set_configuration_provider(YAMLConfigurationProvider("config/strategies", "production"))
        
        # 等待一段时间接收数据
        print("等待接收数据...")
        time_module.sleep(2)
        
        # 打印摘要
        strategy.print_simulation_summary()
        
        # 或者开始历史数据回放
        if using_mock_data:
            strategy.start_replay(mock_setting["replay_date"], symbols)
        
        # 保持运行
        print("按Ctrl+C退出...")
        while True:
            time_module.sleep(30)
            # 定期打印模拟持仓状态
            if debug:
                strategy.print_simulation_summary()
            
    except KeyboardInterrupt:
        print("\n收到退出信号...")
    except Exception as e:
        print(f"运行过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        strategy.close()


if __name__ == "__main__":
    main() 