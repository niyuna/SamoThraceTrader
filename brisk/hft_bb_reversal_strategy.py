"""
HFT BB Reversal Strategy
基于布林带反转的日内高频交易策略
"""

import time as time_module
from datetime import datetime, timedelta, time
from typing import Dict, Optional, List, Any
from dataclasses import dataclass

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
    can_trade: bool = False                          # X条件满足标志
    bb_levels: Optional[dict] = None                 # 布林带水平
    entry_order_price: float = 0.0                   # 入场订单价格
    exit_order_price: float = 0.0                    # 出场订单价格
    entry_order_time: Optional[datetime] = None      # 入场订单发送时间


class HFTBBReversalStrategy(IntradayStrategyBase):
    """HFT BB Reversal策略 - 基于布林带反转的日内高频交易策略"""
    
    def __init__(self, use_mock_gateway=False, use_real_data=False, data_dir="data/brisk_agged_ohlc"):
        super().__init__(use_mock_gateway)
        
        # BB策略特定参数
        self.bb_period = 20
        self.bb_entry_std_multiplier = 3.0
        self.bb_exit_std_multiplier = 0.1
        self.trigger_tick_count = 3  # trigger价格调整的tick数量
        
        # X条件std_pct阈值参数
        self.std_pct_threshold_morning = 0.00073    # 早上9:15-9:35阈值
        self.std_pct_threshold_noon = 0.000001      # 中午11:29-11:30阈值（极小的值，几乎总是通过）
        self.std_pct_threshold_afternoon = 0.00036  # 下午14:35-15:20阈值
        
        # 收盘前平仓参数
        self.market_close_liquidation_enabled = True  # 是否启用收盘前平仓
        self.market_close_time = time(15, 24)        # 普通交易结束时间
        self.liquidation_check_time = time(15, 25)   # 平仓检查时间
        self.liquidation_executed = False            # 是否已执行平仓
        
        # 模拟持仓管理
        self.simulated_positions = {}  # symbol -> {'long': bool, 'short': bool}

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
        self.x_condition_time_windows = [
            (time(9, 15), time(9, 35)),    # 早上 9:15~9:35
            (time(11, 29), time(11, 30)),  # 中午 11:29~11:30
            (time(14, 35), time(15, 20))   # 下午 14:35~15:20
        ]

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
            self.hft_contexts[symbol] = HFTBBStockContext(symbol=symbol)
            self.write_log(f"Created HFT context for symbol {symbol}")
        return self.hft_contexts[symbol]
    
    def check_x_condition(self, symbol: str, current_time: datetime = None) -> bool:
        """
        检查X条件是否满足
        
        X条件包括：
        1. 股票是否在eligible_stocks中
        2. 模拟持仓检查 - 目前没有持仓
        3. 时间窗口检查 - 在指定的交易时间段内
        4. std_pct阈值检查 - 根据时间段检查不同的波动率阈值
        
        Args:
            symbol: 股票代码
            current_time: 当前时间，如果为None则使用系统当前时间
            
        Returns:
            bool: 是否满足X条件
        """
        if not self.x_condition_enabled:
            return True
            
        # 1. 检查是否有活跃的entry订单（最高优先级）
        context = self.get_hft_context(symbol)
        if context.entry_order_id:  # 非空字符串表示有活跃订单
            self.write_log(f"X条件检查通过: {symbol} 有活跃的entry订单，允许继续交易")
            return True
            
        # 2. 检查股票是否在eligible_stocks中
        if symbol not in self.eligible_stocks:
            self.write_log(f"X条件检查失败: {symbol} 不在eligible_stocks中")
            return False
            
        # 3. 检查模拟持仓 - 目前没有持仓
        if not self._check_no_position(symbol):
            self.write_log(f"X条件检查失败: {symbol} 已有持仓")
            return False
            
        # 4. 检查时间窗口和std_pct阈值
        time_window_result = self._check_time_window_with_std_pct(symbol, current_time)
        if not time_window_result['in_window']:
            self.write_log(f"X条件检查失败: 当前时间不在交易窗口内")
            return False
            
        if not time_window_result['std_pct_ok']:
            self.write_log(f"X条件检查失败: {symbol} std_pct={time_window_result['std_pct']:.6f} "
                          f"低于{time_window_result['time_period']}阈值{time_window_result['threshold']:.6f}")
            return False
            
        self.write_log(f"X条件检查通过: {symbol} {time_window_result['time_period']} "
                      f"std_pct={time_window_result['std_pct']:.6f}")
        return True
    
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
        
        # 定义时间窗口和对应的阈值
        time_windows = [
            {
                'start': time(9, 15),
                'end': time(9, 35),
                'threshold': self.std_pct_threshold_morning,
                'name': 'morning'
            },
            {
                'start': time(11, 29),
                'end': time(11, 30),
                'threshold': self.std_pct_threshold_noon,
                'name': 'noon'
            },
            {
                'start': time(14, 35),
                'end': time(15, 20),
                'threshold': self.std_pct_threshold_afternoon,
                'name': 'afternoon'
            }
        ]
        
        # 检查是否在时间窗口内
        for window in time_windows:
            # 检查下午窗口时排除15:00
            if window['name'] == 'afternoon':
                if window['start'] <= current_time_only <= window['end'] and current_time_only != time(15, 0):
                    # 在时间窗口内，检查std_pct
                    std_pct_result = self._calculate_and_check_std_pct(symbol, window['threshold'])
                    return {
                        'in_window': True,
                        'time_period': window['name'],
                        'threshold': window['threshold'],
                        'std_pct': std_pct_result['std_pct'],
                        'std_pct_ok': std_pct_result['ok']
                    }
            else:
                if window['start'] <= current_time_only <= window['end']:
                    # 在时间窗口内，检查std_pct
                    std_pct_result = self._calculate_and_check_std_pct(symbol, window['threshold'])
                    return {
                        'in_window': True,
                        'time_period': window['name'],
                        'threshold': window['threshold'],
                        'std_pct': std_pct_result['std_pct'],
                        'std_pct_ok': std_pct_result['ok']
                    }
        
        return {
            'in_window': False,
            'time_period': None,
            'threshold': None,
            'std_pct': None,
            'std_pct_ok': False
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
        """创建BB策略专用的技术指标管理器"""
        return HFTBBReversalIndicator(
            symbol=symbol, 
            size=self.indicator_size,
            bb_period=self.bb_period,
            entry_std_multiplier=self.bb_entry_std_multiplier,
            exit_std_multiplier=self.bb_exit_std_multiplier
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
        
        # 1. 更新技术指标和触发价格
        if symbol in self.indicator_managers:
            indicators = self.indicator_managers[symbol].update_bar(bar)
            bb_levels = self._calculate_bb_levels(symbol, indicators)
            
            if bb_levels:
                # 更新BB水平和触发价格
                context.bb_levels = bb_levels
                context.trigger_levels = self._calculate_trigger_levels(symbol, bb_levels)
                
                self.write_log(f"更新BB价格水平: {symbol}")
                self.write_log(f"  Upper: {bb_levels['upper']:.2f} (Short Entry)")
                self.write_log(f"  Lower: {bb_levels['lower']:.2f} (Long Entry)")
                self.write_log(f"  Middle: {bb_levels['middle']:.2f} (SMA)")
                self.write_log(f"  Exit_Long: {bb_levels['exit_long']:.2f}")
                self.write_log(f"  Exit_Short: {bb_levels['exit_short']:.2f}")
                self.write_log(f"  STD: {bb_levels['std']:.2f}")
                
                if context.trigger_levels:
                    self.write_log(f"更新触发价格水平: {symbol}")
                    self.write_log(f"  上轨触发: {context.trigger_levels.upper_trigger:.2f}")
                    self.write_log(f"  上轨限价: {context.trigger_levels.upper_limit:.2f}")
                    self.write_log(f"  下轨触发: {context.trigger_levels.lower_trigger:.2f}")
                    self.write_log(f"  下轨限价: {context.trigger_levels.lower_limit:.2f}")
                
                # 2. 检查X条件并更新交易标志
                context.can_trade = self.check_x_condition(symbol, bar.datetime)
                
                # 3. 如果有持仓，维护出场订单
                if context.position != 0:
                    self._manage_exit_order(symbol, bb_levels)
        
        # 调用父类方法（保持原有逻辑）
        super().on_1min_bar(bar)
    
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
        
        # 1. 检查X条件是否满足，如果满足则检查入场订单逻辑
        if context.can_trade and context.trigger_levels:
            self._check_entry_logic(symbol, tick, context)
        
        # 2. 更新BarGenerator（复用base strategy方法）
        if symbol in self.bar_generators:
            self.bar_generators[symbol].update_tick(tick)
        
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
            self.simulated_positions[symbol] = {'long': False, 'short': False}
        
        positions = self.simulated_positions[symbol]
        
        # 检查entry信号（当前没有仓位时）
        if not positions['long'] and not positions['short']:
            # 检查long entry
            if current_price <= bb_levels['lower']:
                positions['long'] = True
                self.write_log(f"模拟Long Entry触发: {symbol} 价格: {current_price:.2f} <= {bb_levels['lower']:.2f}")
            
            # 检查short entry
            elif current_price >= bb_levels['upper']:
                positions['short'] = True
                self.write_log(f"模拟Short Entry触发: {symbol} 价格: {current_price:.2f} >= {bb_levels['upper']:.2f}")
        
        # 检查exit信号（当前有仓位时）
        elif positions['long']:
            # Long仓位平仓
            if current_price >= bb_levels['exit_long']:
                positions['long'] = False
                self.write_log(f"模拟Long Exit触发: {symbol} 价格: {current_price:.2f} >= {bb_levels['exit_long']:.2f}")
        
        elif positions['short']:
            # Short仓位平仓
            if current_price <= bb_levels['exit_short']:
                positions['short'] = False
                self.write_log(f"模拟Short Exit触发: {symbol} 价格: {current_price:.2f} <= {bb_levels['exit_short']:.2f}")
    
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
        self.write_log(f"订单状态更新: {order.symbol} {order.direction.value} {order.offset.value} "
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
            self._manage_exit_order(symbol, context.bb_levels)
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
        
        print("\n技术指标状态:")
        for symbol in self.indicator_managers:
            manager = self.indicator_managers[symbol]
            if manager.is_inited():
                indicators = manager.get_indicators()
                if indicators:
                    bb_info = f"BB已初始化 (周期: {indicators.get('period', 'N/A')})"
                else:
                    bb_info = "BB未初始化"
                print(f"  {symbol}: {bb_info}")
            else:
                print(f"  {symbol}: 技术指标未初始化")

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
                success = self._cancel_order_safely(context.entry_order_id, symbol)
                if success:
                    context.entry_order_id = ""
                    context.entry_order_time = None
                    liquidation_count += 1
                else:
                    failed_count += 1
                    self.write_log(f"取消entry订单失败: {symbol} {context.entry_order_id}")
                
            # 2. 处理exit订单
            if context.exit_order_id:
                # 取消原limit订单
                self.write_log(f"取消原exit订单: {symbol} {context.exit_order_id}")
                success = self._cancel_order_safely(context.exit_order_id, symbol)
                if not success:
                    failed_count += 1
                    self.write_log(f"取消exit订单失败: {symbol} {context.exit_order_id}")
                
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
                    context.state = StrategyState.WAITING_TIMEOUT_EXIT  # 标记为closing状态
                    liquidation_count += 1
                    self.write_log(f"发送market平仓订单成功: {symbol} {order_id}")
                else:
                    failed_count += 1
                    self.write_log(f"发送market平仓订单失败: {symbol}")
        
        # 只有当没有失败时才设置liquidation_executed为True
        if failed_count == 0:
            self.liquidation_executed = True
            self.write_log(f"收盘前平仓订单发送完成，成功: {liquidation_count}个")
        else:
            self.write_log(f"收盘前平仓部分失败，成功: {liquidation_count}个，失败: {failed_count}个，将重试")

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

    def _manage_exit_order(self, symbol: str, bb_levels: dict):
        """
        管理出场订单
        
        Args:
            symbol: 股票代码
            bb_levels: 布林带水平
        """
        context = self.get_hft_context(symbol)
        
        if context.position == 0:
            return  # 无持仓，不需要出场订单
        
        # 确定出场价格和方向
        if context.position > 0:
            # 多头持仓，需要卖出平仓
            exit_price = bb_levels.get('exit_long', 0)  # 使用exit_long作为出场价格
            exit_direction = Direction.SHORT
            self.write_log(f"管理出场订单: {symbol} 多头持仓{context.position}，出场价格: {exit_price:.2f}")
        else:
            # 空头持仓，需要买入平仓
            exit_price = bb_levels.get('exit_short', 0)  # 使用exit_short作为出场价格
            exit_direction = Direction.LONG
            self.write_log(f"管理出场订单: {symbol} 空头持仓{abs(context.position)}，出场价格: {exit_price:.2f}")
        
        # 检查是否有部分成交的入场订单需要取消
        if (context.entry_order_id and 
            context.already_traded > 0 and 
            context.already_traded < context.position_size):
            # 取消部分成交的入场订单
            self.write_log(f"取消部分成交的入场订单: {symbol} 已成交{context.already_traded}")
            self._cancel_order_safely(context.entry_order_id, symbol)
            context.entry_order_id = ""
            context.entry_order_time = None
        
        # 检查是否需要更新出场订单
        if context.exit_order_id:
            # 已有出场订单，检查价格是否需要更新
            if abs(context.exit_price - exit_price) > 0.01:  # 价格差异超过0.01
                # 取消旧订单
                self._cancel_order_safely(context.exit_order_id, symbol)
                context.exit_order_id = ""
                self.write_log(f"取消旧出场订单: {symbol} 价格差异过大")
            else:
                # 价格相同，无需更新
                return
        
        # 发送新的出场订单
        if exit_price > 0:
            # 关键：调整already_traded为position_size - 实际持仓
            # 这样base strategy会计算正确的数量
            context.already_traded = context.position_size - abs(context.position)
            
            self.write_log(f"调整already_traded为{context.already_traded} "
                          f"用于发送{abs(context.position)}股exit订单")
            
            # _execute_exit会自动更新context.exit_order_id, context.exit_price等字段
            order_id = self._execute_exit(context, None, exit_price, exit_direction)
            if order_id:
                self.write_log(f"发送出场订单成功: {symbol} {exit_direction.value} 价格{exit_price:.2f} 订单ID: {order_id}")
            else:
                self.write_log(f"发送出场订单失败: {symbol} {exit_direction.value} 价格{exit_price:.2f}")

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
        
        self.write_log(f"检查入场逻辑: {symbol} 价格{tick.last_price:.2f}")
        trigger_levels = context.trigger_levels
        current_price = tick.last_price
        
        # 检查是否需要下单
        should_order = False
        order_direction = None
        order_price = 0.0
        
        # 检查上轨触发
        if current_price >= trigger_levels.upper_trigger and not context.entry_order_id:
            should_order = True
            order_direction = Direction.SHORT
            order_price = trigger_levels.upper_limit
            self.write_log(f"触发上轨: {symbol} 价格{current_price:.2f} >= 触发价格{trigger_levels.upper_trigger:.2f}")
        
        # 检查下轨触发
        elif current_price <= trigger_levels.lower_trigger and not context.entry_order_id:
            should_order = True
            order_direction = Direction.LONG
            order_price = trigger_levels.lower_limit
            self.write_log(f"触发下轨: {symbol} 价格{current_price:.2f} <= 触发价格{trigger_levels.lower_trigger:.2f}")
        
        # 检查是否需要取消订单
        should_cancel = False
        if context.entry_order_id:
            # 检查是否在同一分钟内发送的订单，如果是则不取消
            current_time = datetime.now()
            if context.entry_order_time:
                # 检查是否在同一分钟内
                time_diff = current_time - context.entry_order_time
                if time_diff.total_seconds() < 60:  # 同一分钟内
                    self.write_log(f"跳过取消订单: {symbol} 订单在同一分钟内发送，避免频繁撤单")
                    return  # 直接返回，不执行任何订单操作
            
            # 如果当前价格在两个触发价格之间，取消订单
            if (trigger_levels.lower_trigger < current_price < trigger_levels.upper_trigger):
                should_cancel = True
                self.write_log(f"取消订单原因: 价格在触发区间内 {current_price:.2f}")
            # 如果订单价格与当前应该下的价格不同，取消订单
            elif context.entry_price != order_price:
                should_cancel = True
                self.write_log(f"取消订单原因: 价格不同 当前:{context.entry_price:.2f} 应该:{order_price:.2f}")
        
        # 执行订单操作
        if should_cancel:
            self._cancel_entry_order(symbol, context)
        elif not context.entry_order_id and should_order:
            self._send_entry_order(symbol, order_direction, order_price, 100)  # 使用固定数量100

    def _cancel_entry_order(self, symbol: str, context: HFTBBStockContext):
        """
        取消入场订单
        
        Args:
            symbol: 股票代码
            context: 股票上下文
        """
        if context.entry_order_id:
            # 使用base strategy的撤单方法
            success = self._cancel_order_safely(context.entry_order_id, symbol)
            if success:
                self.write_log(f"取消入场订单成功: {symbol} 订单ID: {context.entry_order_id}")
                context.entry_order_id = ""
                context.entry_order_time = None  # 清除订单发送时间
                # 更新状态为空闲
                self.update_context_state(symbol, StrategyState.IDLE)
            else:
                self.write_log(f"取消入场订单失败: {symbol} 订单ID: {context.entry_order_id}")

    def _send_entry_order(self, symbol: str, direction: Direction, price: float, quantity: int):
        """
        发送入场订单
        
        Args:
            symbol: 股票代码
            direction: 交易方向
            price: 订单价格
            quantity: 订单数量（暂时不使用，数量从context中获取）
        """
        context = self.get_hft_context(symbol)
        
        # 使用base strategy的入场订单执行方法
        # 注意：_execute_entry需要bar参数，但在on_tick中我们没有bar，所以传递None
        # _execute_entry会自动更新context.entry_order_id, context.entry_price等字段
        self._execute_entry(context, None, price, direction)
        
        # 检查订单是否成功发送
        if context.entry_order_id:
            # 更新订单发送时间
            context.entry_order_time = datetime.now()
            self.write_log(f"发送入场订单成功: {symbol} {direction.value} 价格{price:.2f} 订单ID: {context.entry_order_id}")
        else:
            self.write_log(f"发送入场订单失败: {symbol} {direction.value} 价格{price:.2f}")


def main():
    """主函数"""
    print("启动HFT BB Reversal策略...")
    
    using_mock_data = False
    debug = True

    # 创建策略实例
    strategy = HFTBBReversalStrategy(use_mock_gateway=using_mock_data, use_real_data=True, data_dir="data/brisk_agged_ohlc")
    
    try:
        # 连接Gateway
        mock_setting = {
            "tick_mode": "replay",
            # "replay_data_dir": "D:\\dev\\github\\brisk-hack\\brisk_in_day_frames",
            "replay_data_dir": "F:\\brisk_in_day_frames",
            "replay_date": "20250905",  # 根据实际数据文件调整
            "replay_speed": 100.0,       # 100倍速回放
            "mock_account_balance": 10000000,
        }
        
        # 连接Gateway
        strategy.connect(mock_setting)
        
        # 订阅股票
        # we will be using a static symbols list for this strategy, it should be a subset of TOPIX500
        # symbols = ["9984", "6098"]  # 软银、乐天
        symbols = []
        strategy.initialize_stock_master()
        for symbol in topix500:
            prev_close = strategy.get_stock_prev_close(symbol)
            # morning test
            if 1000 >= prev_close > 600:
                symbols.append(symbol)
            # after noon use 1500 >= prev_close > 1000
        
        print(f"订阅股票: {symbols}")
        print(f"订阅股票数量: {len(symbols)}")

        if using_mock_data:
            preload_yyyymmdd = "20250904"
        else:
            from common.date_utils import prev_working_day
            preload_yyyymmdd = prev_working_day(datetime.now().strftime("%Y%m%d"))

        # strategy.preload_historical_data(symbols, preload_yyyymmdd)
        strategy.subscribe(symbols)
        
        # 注册收盘前平仓定时器
        strategy._register_market_close_timer()
        
        
        # 等待一段时间接收数据
        print("等待接收数据...")
        time_module.sleep(2)
        
        # 打印摘要
        strategy.print_simulation_summary()
        
        # 或者开始历史数据回放
        if using_mock_data:
            strategy.start_replay("20250905", symbols)
        
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