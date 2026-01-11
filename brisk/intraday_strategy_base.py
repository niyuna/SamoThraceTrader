"""
Intraday Strategy Base Class
"""

import time
from datetime import datetime, timedelta
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Optional, List, Any
from enum import Enum

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine, LogEngine
from vnpy.trader.object import SubscribeRequest, Exchange, BarData, Interval
from enhanced_bargenerator import EnhancedBarGenerator

from brisk_gateway import BriskGateway
from mock_brisk_gateway import MockBriskGateway
from brisk_eshiten_gateway import BriskEshitenGateway
from brisk_click_gateway import BriskClickGateway
from kabus_gateway import KabusGateway

from vnpy.trader.event import EVENT_TICK, EVENT_LOG, EVENT_ORDER, EVENT_TRADE
from vnpy.event import Event
from technical_indicators import TechnicalIndicatorManager
from vnpy.trader.object import OrderRequest, CancelRequest
from vnpy.trader.constant import Direction, Offset, OrderType, Status

from common.trading_common import normalize_price
from vnpy.trader.logger import setup_logger

# 动态参数系统导入
from util.dynamic_config import ConfigurationProvider
from util.dynamic_param_manager import DynamicParamManager


class StrategyState(Enum):
    """策略状态枚举"""
    IDLE = "idle"                    # 空闲状态，等待 entry 信号
    WAITING_ENTRY = "waiting_entry"  # 等待 entry 订单成交
    HOLDING = "holding"              # 持仓中，等待 exit 信号
    WAITING_EXIT = "waiting_exit"    # 等待 exit 订单成交
    WAITING_TIMEOUT_EXIT = "waiting_timeout_exit"  # 等待timeout exit limit order


class GatewayType(Enum):
    """Gateway类型枚举"""
    MOCK = "mock"
    BRISK = "brisk"
    BRISK_ESHITEN = "brisk_eshiten"
    BRISK_CLICK = "brisk_click"
    KABUS = "kabus"


@dataclass
class StockContext:
    """股票 Context 数据结构"""
    symbol: str
    state: StrategyState = StrategyState.IDLE
    trade_count: int = 0                    # 当日交易次数
    timeout_trade_count: int = 0            # 完成的timeout exit交易数量
    entry_order_id: str = ""                # entry订单ID
    exit_order_id: str = ""                 # exit订单ID
    entry_price: float = 0.0                # entry成交价格
    entry_time: datetime = None             # entry成交时间
    exit_start_time: datetime = None        # exit订单开始时间
    timeout_exit_start_time: datetime = None  # timeout exit开始时间
    max_exit_wait_time: timedelta = timedelta(minutes=5)  # exit订单最大等待时间
    position_size: int = 100                # 持仓数量
    already_traded: int = 0                 # 已成交数量
    exit_price: float = 0.0                # exit成交价格
    # 新增：延迟执行相关字段
    entry_trigger_price: float = 0.0        # 触发价格（距离目标价格2个ATR）
    entry_trigger_order_price: float = 0.0  # 触发时的订单价格
    # 新增：风险控制相关字段
    trading_banned: bool = False            # 是否被禁止交易
    # 新增：成交量异常相关字段
    entry_canceled_by_vol_ma5: bool = False  # 是否被成交量异常取消，每分钟reset


class IntradayStrategyBase:
    """日内策略基础框架 - 集成技术指标和K线生成"""
    
    def __init__(self, use_mock_gateway=False, gateway_type: str = "brisk", log_suffix=None):
        """
        初始化日内策略基础框架
        
        Args:
            use_mock_gateway: 是否使用mock gateway（向后兼容参数）
            gateway_type: Gateway类型 ("mock", "brisk", "brisk_eshiten", "brisk_click", "kabus")
            log_suffix: 日志后缀
        """
        # 保持向后兼容性
        self.use_mock_gateway = use_mock_gateway
        self.gateway_type = gateway_type
        
        # 如果同时提供了两个参数，gateway_type优先级更高
        if gateway_type != "brisk":  # 如果明确指定了gateway_type
            self.use_mock_gateway = (gateway_type == "mock")
        elif use_mock_gateway:  # 如果只使用了旧的参数
            self.gateway_type = "mock"
            
        self.log_suffix = log_suffix
        self.event_engine = None
        self.main_engine = None
        self.gateway = None
        self.gateway_name = None
        self.brisk_gateway = None
        self.bar_generators = {}
        self.indicator_managers = {}
        self.bars_count = defaultdict(int)
        
        # 新增：Context 管理
        self.contexts: Dict[str, StockContext] = {}
        
        # 新增：股票基础信息管理
        self.stock_master = {}  # 股票基础信息
        
        # 新增：单只股票最大持仓量
        self.single_stock_max_position = 1_000_000
        
        # 新增：延迟执行标志
        self.enable_delayed_entry = False
        self.delayed_entry_atr_multiplier = 2.0
        
        # 新增：风险控制参数（子类可以重写）
        self.exit_vol_ma5_ratio_threshold = 3.0  # 成交量异常阈值
        self.force_exit_atr_factor = 1.5         # 强制平仓ATR倍数
        
        # 新增：Bar Generator和技术指标配置（子类可以重写）
        self.bar_window = 5                      # 5分钟K线窗口
        self.bar_interval = Interval.MINUTE      # K线间隔
        self.enable_opening_volume = True        # 启用开盘成交量
        self.enable_auto_flush = False           # 不启用强制收线（replay模式）
        self.indicator_size = 15                 # 技术指标计算所需的历史bar数量
        
        # 新增：Black List管理
        self.black_list = set()  # 使用set提高查找效率
        self.black_list_enabled = True  # 是否启用black list功能

        # new: short ban list because some stocks are not eligible for short
        self.short_ban_list = set(['6574', '2160', '3350', '5016', '7685', '6758', '6201', '4676', '3391', '6028', '6406', '4626', '7732', '3778', '5449'])
        
        # 动态参数系统相关
        self.dynamic_param_manager: Optional[DynamicParamManager] = None
        self.enable_dynamic_params: bool = True
        self.config_check_interval: int = 60  # 默认60秒检查一次
        
        from vnpy.trader.setting import SETTINGS
        # by default, will read ".vntrader/vt_setting.json", set in setting.py
        SETTINGS["log.active"] = True
        SETTINGS["log.level"] = 20
        SETTINGS["log.console"] = True
        SETTINGS["log.file_name"] = self._get_log_filename()
        # SETTINGS["log.format"] = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{extra[gateway_name]}</cyan> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
        setup_logger()
        # log file will be ".vntrader/log/vt_{today_date}.log", set in logger.py
        
        # 初始化动态参数系统
        self._init_dynamic_param_system()
    
    def _get_log_filename(self):
        """生成日志文件名"""
        base_name = self.__class__.__name__
        if self.log_suffix:
            return f"{base_name}_{self.log_suffix}"
        return base_name
        
    # ==================== context management and base methods ====================

    def get_context(self, symbol: str) -> StockContext:
        """获取或创建股票 Context"""
        if symbol not in self.contexts:
            self.contexts[symbol] = StockContext(symbol=symbol)
            self.contexts[symbol].position_size = self.calculate_position_size(symbol)
        return self.contexts[symbol]
    
    def update_context_state(self, symbol: str, new_state: StrategyState):
        """更新 Context 状态"""
        context = self.get_context(symbol)
        old_state = context.state
        context.state = new_state
        self.write_log(f"Context state changed for {symbol}: {old_state.value} -> {new_state.value}")
    
    # TODO: having lots of contexts will lead to performance issue, need optimization here
    def get_context_by_order_id(self, order_id: str) -> Optional[StockContext]:
        """根据订单ID查找对应的 Context"""
        for context in self.contexts.values():
            if context.entry_order_id == order_id or context.exit_order_id == order_id:
                return context
        return None
    
    def initialize_stock_master(self):
        """初始化股票基础信息 - 子类可以重写"""
        try:
            from stock_master import get_stockmaster
            self.stock_master = get_stockmaster()
            self.write_log(f"获取到 {len(self.stock_master)} 只股票的基础信息")
        except ImportError:
            self.write_log("警告: 无法导入stock_master模块，stock_master将为空")
            self.stock_master = {}
    
    def get_stock_info(self, symbol: str) -> dict:
        """获取股票基础信息"""
        return self.stock_master.get(symbol, {})
    
    def get_stock_market_cap(self, symbol: str) -> float:
        """获取股票市值"""
        stock_info = self.get_stock_info(symbol)
        return stock_info.get('market_cap', 0)
    
    def get_stock_prev_close(self, symbol: str) -> float:
        """获取股票前一日收盘价"""
        stock_info = self.get_stock_info(symbol)
        base_price = stock_info.get('basePrice10', 0)
        return base_price / 10 if base_price > 0 else 0
    
    def calculate_position_size(self, symbol: str) -> int:
        """计算持仓数量，基于单只股票最大持仓量"""
        price = self.get_stock_prev_close(symbol)
        if price <= 0:
            return 100  # 默认持仓数量
        
        # 计算基于价格的持仓数量
        # 2025/11/04
        earning_stocks = '4506,4587,7003,9501,9509,4516'
        earning_stocks = earning_stocks.split(',')
        if not symbol in earning_stocks:
            position_size = round(self.single_stock_max_position / price / 100) * 100
        else:
            position_size = round(self.single_stock_max_position / 2 / price / 100) * 100

        return max(position_size, 100)
    
    def _ban_symbol_trading(self, symbol):
        """禁止交易指定股票"""
        # 从eligible_stocks中移除
        if hasattr(self, 'eligible_stocks'):
            self.eligible_stocks.discard(symbol)
        
        # 设置禁止标志
        context = self.get_context(symbol)
        context.trading_banned = True
        
        self.write_log(f"禁止交易股票: {symbol}")

    def write_log(self, msg: str):
        if self.main_engine:
            self.main_engine.write_log(msg, self.__class__.__name__)
        else:
            # 在main_engine未初始化时，使用print输出
            print(f"[{self.__class__.__name__}] {msg}")
    
    def reset_all_contexts(self):
        """重置所有 Context 状态 - 子类可以重写"""
        for context in self.contexts.values():
            context.state = StrategyState.IDLE
            context.trade_count = 0
            context.timeout_trade_count = 0
            context.entry_order_id = ""
            context.exit_order_id = ""
            context.entry_price = 0.0
            context.entry_time = None
            context.exit_start_time = None
            context.timeout_exit_start_time = None
            # 新增：重置触发价格字段
            context.entry_trigger_price = 0.0
            context.entry_trigger_order_price = 0.0
            # 新增：重置禁止交易标志
            context.trading_banned = False
        self.write_log("All contexts reset")
        
        # 新增：重置黑名单（可选，根据策略需求决定）
        # self.black_list.clear()
        # self.write_log("Black list cleared")
    
    # ==================== dynamic param system ====================

    def _init_dynamic_param_system(self):
        """初始化动态参数系统"""
        if self.enable_dynamic_params:
            self.write_log("动态参数系统已启用")
        else:
            self.write_log("动态参数系统已禁用")
    
    def _register_config_check_timer(self):
        """注册配置检查定时器"""
        if not self.enable_dynamic_params or not self.event_engine:
            return
            
        # 使用正确的timer注册方式，参考enhanced_bargenerator.py
        from vnpy.trader.event import EVENT_TIMER
        self.event_engine.register(EVENT_TIMER, self._on_config_check_timer)
        self.write_log(f"配置检查定时器已注册，检查间隔: {self.config_check_interval}秒")
    
    def _on_config_check_timer(self, event):
        """定时器回调：检查配置更新"""
        if not self.dynamic_param_manager:
            return
            
        if self.dynamic_param_manager.should_check_config():
            self._check_and_update_dynamic_params()
    
    def _check_and_update_dynamic_params(self):
        """检查并更新动态参数"""
        config = self.dynamic_param_manager.fetch_config()
        if not config:
            return
        
        # 更新通用参数
        self._update_common_dynamic_params(config.params)
        
        # 更新策略特定参数
        self._update_strategy_specific_params(config.params)
        
        # 记录日志
        self.write_log(f"动态参数更新完成，版本: {config.version}")
    
    def _update_common_dynamic_params(self, params: Dict[str, Any]):
        """更新通用动态参数"""
        # 增量更新黑名单
        if 'black_list' in params:
            final_black_list = []
            for sol in params['black_list']:
                if isinstance(sol, str):
                    for s in sol.split(','):
                        final_black_list.append(s)
                else:
                    final_black_list.append(sol)
            self._update_black_list_incrementally(final_black_list)
        
        # 更新其他通用参数
        common_params = ['enable_dynamic_params', 'config_check_interval']
        for param in common_params:
            if param in params:
                setattr(self, param, params[param])
    
    def _update_black_list_incrementally(self, new_black_list: List[str]):
        """增量更新黑名单"""
        if not isinstance(new_black_list, list):
            return
            
        # 获取当前黑名单
        current_black_list = set(self.black_list)
        
        # 解析增量更新指令
        from util.dynamic_config import BlackListUpdateParser
        update_info = BlackListUpdateParser.parse_update(new_black_list)
        
        # 应用更新
        for symbol in update_info['adds']:
            if symbol not in current_black_list:
                current_black_list.add(symbol)
                self.write_log(f"黑名单添加: {symbol}")
                # 从eligible_stocks中移除
                self.remove_from_eligible_stocks(symbol)
        
        for symbol in update_info['removes']:
            if symbol in current_black_list:
                current_black_list.discard(symbol)
                self.write_log(f"黑名单移除: {symbol}")
                # 重新添加到eligible_stocks（如果策略支持）
                if hasattr(self, 'eligible_stocks'):
                    self.eligible_stocks.add(symbol)
        
        # 更新黑名单
        self.black_list = list(current_black_list)
        self.write_log(f"黑名单更新完成，当前数量: {len(self.black_list)}")
    
    def _update_strategy_specific_params(self, params: Dict[str, Any]):
        """更新策略特定参数 - 子类需要实现"""
        pass
    
    def set_configuration_provider(self, config_provider: ConfigurationProvider, check_interval: int = 20):
        """设置配置提供者"""
        self.dynamic_param_manager = DynamicParamManager(self, config_provider, check_interval)
        self.write_log("配置提供者设置完成")
        
        # 注册定时器
        self._register_config_check_timer()
    
    def set_config_check_interval(self, interval: int):
        """设置配置检查间隔（秒）"""
        self.config_check_interval = interval
        if self.dynamic_param_manager:
            # 重新注册定时器
            self._register_config_check_timer()
            self.write_log(f"配置检查间隔设置为: {interval}秒")

    # ==================== 核心交易执行方法 ====================
    
    # call flow: _check_and_execute_trigger -> _execute_triggered_entry -> _execute_entry/_execute_exit -> _execute_trade -> _execute_order

    def _execute_order(self, context, bar, price: float, direction: Direction, offset: Offset, order_type: OrderType = OrderType.LIMIT, reference_prefix: str = "order", quantity: int = None):
        """统一的订单执行方法"""
        # 确定订单数量
        if quantity is not None:
            order_volume = quantity
        else:
            order_volume = context.position_size - context.already_traded
            
        # 创建OrderRequest
        order_req = OrderRequest(
            symbol=context.symbol,
            exchange=bar.exchange if bar else Exchange.TSE,
            direction=direction,
            type=order_type,
            volume=order_volume,
            price=price, # should make this 0 or None for market order
            offset=offset,
            reference=f"{reference_prefix}_{context.symbol}_{datetime.now().strftime('%H%M%S')}"
        )
        
        # 执行下单
        order_id = self.gateway.send_order(order_req)
        
        if order_id:
            self.write_log(f"订单已提交: {context.symbol} {direction.value} {offset.value} 价格: {price if price else 'N/A'} 订单ID: {order_id}")
            return order_id
        else:
            self.write_log(f"订单被拒绝: {context.symbol} {direction.value} {offset.value}")
            return None

    def _execute_trade(self, context, bar, price: float, direction: Direction, offset: Offset, order_type: OrderType = OrderType.LIMIT, trade_type: str = "order"):
        """统一的交易执行方法 - 合并 entry 和 exit"""
        # 确定交易类型和日志信息
        if offset == Offset.OPEN:
            action = "开仓"
            reference_prefix = f"entry_{direction.value.lower()}"
        else:  # Offset.CLOSE
            action = "平仓"
            reference_prefix = f"exit_{direction.value.lower()}"
        
        d = "做空" if direction == Direction.SHORT else "做多"
        order_type_str = "市价" if order_type == OrderType.MARKET else "限价"
        time_str = bar.datetime.strftime('%H:%M:%S') if bar and bar.datetime else 'N/A'
        self.write_log(f"执行{d}{action}({order_type_str}): {context.symbol} 价格: {price if price else 'N/A'} "
              f"时间: {time_str}")
        
        # 执行订单
        order_id = self._execute_order(
            context=context,
            bar=bar,
            price=price,
            direction=direction,
            offset=offset,
            order_type=order_type,
            reference_prefix=reference_prefix
        )
        
        if order_id:
            if offset == Offset.OPEN:
                # Entry 订单
                context.entry_order_id = order_id
                context.entry_price = price
                context.entry_time = datetime.now()
                # 新增：重置触发价格字段
                context.entry_trigger_price = 0.0
                context.entry_trigger_order_price = 0.0
                self.update_context_state(context.symbol, StrategyState.WAITING_ENTRY)
            else:
                # Exit 订单
                context.exit_order_id = order_id
                context.exit_price = price
                # this part is tricky, for the case of price update, we should not update the exit_start_time, but for a new order, we should
                # maybe a better way is to set this to None after a exit order is filled
                if context.exit_start_time is None:
                    context.exit_start_time = datetime.now()
                self.update_context_state(context.symbol, StrategyState.WAITING_EXIT)
        
        return order_id

    # 新增：延迟执行相关方法
    # note: this is a general way to only send order if the price is within the ATR range, regardless of the direction and specific strategy
    
    def _is_price_within_atr_range(self, current_price: float, target_price: float, atr: float, atr_multiplier: float = None) -> bool:
        """检查当前价格是否在目标价格的ATR范围内"""
        if atr <= 0:
            return True  # 如果ATR无效，默认允许交易
        
        # 如果没有指定atr_multiplier，使用策略参数
        if atr_multiplier is None:
            atr_multiplier = self.delayed_entry_atr_multiplier
        
        distance = abs(current_price - target_price)
        threshold = atr * atr_multiplier
        return distance <= threshold
    
    def _set_trigger_prices(self, context, bar, indicators, target_price: float):
        """设置触发价格和订单价格"""
        atr = indicators.get('atr_14', 100.0)
        entry_direction = self.get_entry_direction(context.symbol)
        
        # 使用策略参数
        atr_multiplier = self.delayed_entry_atr_multiplier
        
        if entry_direction == 'short':
            # 做空：触发价格 = 目标价格 - atr_multiplier*ATR
            context.entry_trigger_price = target_price - (atr_multiplier * atr)
            context.entry_trigger_order_price = target_price
        elif entry_direction == 'long':
            # 做多：触发价格 = 目标价格 + atr_multiplier*ATR
            context.entry_trigger_price = target_price + (atr_multiplier * atr)
            context.entry_trigger_order_price = target_price
        
        self.write_log(f"设置触发价格: {context.symbol} 触发价格={context.entry_trigger_price:.2f} "
                       f"订单价格={context.entry_trigger_order_price:.2f} ATR倍数={atr_multiplier}")
    
    def _check_and_execute_trigger(self, tick) -> bool:
        """检查并执行触发条件"""
        symbol = tick.symbol
        context = self.get_context(symbol)
        # 检查是否有有效的触发条件
        if context.entry_trigger_price <= 0 or context.entry_trigger_order_price <= 0:
            return False
        
        # 检查当前状态
        if context.state != StrategyState.IDLE:
            return False
        
        # 检查是否在eligible_stocks中（如果存在该属性）
        if hasattr(self, 'eligible_stocks') and symbol not in self.eligible_stocks:
            return False
        
        # 检查价格是否满足触发条件
        current_price = tick.last_price
        entry_direction = self.get_entry_direction(symbol)
        
        if entry_direction == 'short':
            # 做空：当前价格 <= 触发价格时触发
            if current_price >= context.entry_trigger_price:
                self._execute_triggered_entry(context, tick, context.entry_trigger_order_price, Direction.SHORT)
                return True
        elif entry_direction == 'long':
            # 做多：当前价格 >= 触发价格时触发
            if current_price <= context.entry_trigger_price:
                self._execute_triggered_entry(context, tick, context.entry_trigger_order_price, Direction.LONG)
                return True
        
        return False
    
    def _execute_triggered_entry(self, context, tick, price: float, direction: Direction):
        """执行触发的entry订单"""
        # 创建模拟的bar用于订单执行
        from vnpy.trader.object import BarData
        bar = BarData(
            symbol=context.symbol,
            exchange=tick.exchange,
            datetime=tick.datetime,
            interval=None,
            volume=0,
            turnover=0,
            open_price=tick.last_price,
            high_price=tick.last_price,
            low_price=tick.last_price,
            close_price=tick.last_price,
            gateway_name=tick.gateway_name
        )
        
        # 执行entry订单
        self._execute_entry(context, bar, price, direction)
        self.write_log(f"触发执行entry订单: {context.symbol} 价格={price:.2f} 方向={direction.value}")

    # 新增：风险控制相关方法
    
    def _get_price_movement_direction(self, context, bar):
        """获取价格波动方向，判断是否对持仓有利"""
        entry_direction = self.get_entry_direction(context.symbol)
        
        if entry_direction == 'short':
            # 做空策略，价格下跌有利
            if bar.close_price < bar.open_price:
                return 'favorable'  # 价格下跌，对做空有利
            else:
                return 'unfavorable'  # 价格上涨，对做空不利
        elif entry_direction == 'long':
            # 做多策略，价格上涨有利
            if bar.close_price > bar.open_price:
                return 'favorable'  # 价格上涨，对做多有利
            else:
                return 'unfavorable'  # 价格下跌，对做多不利
        
        return 'unknown'
    
    def _check_exit_risk_control(self, tick):
        """检查exit风险控制 - 考虑波动方向"""
        symbol = tick.symbol
        context = self.get_context(symbol)
        
        # 只在EXIT状态下检查
        if context.state != StrategyState.WAITING_EXIT and context.state != StrategyState.WAITING_TIMEOUT_EXIT:
            return

        # 获取当前bar和技术指标
        current_bar = self._get_current_bar(symbol)
        if not current_bar:
            return

        indicators = self.get_indicators(symbol)
        if not indicators:
            return
        
        # 灵活获取Volume MA指标（支持不同的周期）
        vol_ma_keys = [key for key in indicators.keys() if key.startswith('volume_ma')]
        if not vol_ma_keys:
            # 如果没有Volume MA指标，跳过风险控制
            return
        
        # 使用第一个可用的Volume MA指标
        vol_ma_key = vol_ma_keys[0]
        vol_ma = indicators.get(vol_ma_key, 0)
        if vol_ma <= 0:
            return
        
        current_volume = current_bar.volume
        vol_ratio = current_volume / vol_ma

        # 灵活获取ATR指标（支持不同的周期）
        atr_keys = [key for key in indicators.keys() if key.startswith('atr_')]
        if not atr_keys:
            # 如果没有ATR指标，跳过风险控制
            return
        
        # 使用第一个可用的ATR指标
        atr_key = atr_keys[0]
        atr = indicators.get(atr_key, 0)
        if atr <= 0:
            return
        
        # 检查价格波动异常
        price_change = abs(current_bar.close_price - current_bar.open_price)
        
        entry_direction = self.get_entry_direction(context.symbol)
        # 根据entry方向调整ATR阈值：做空时使用较小阈值，做多时使用较大阈值
        atr_threshold = atr * self.force_exit_atr_factor if entry_direction == 'short' else atr * self.force_exit_atr_factor * 10
        # print(f"context: {context}, current_bar: {current_bar}, indicators: {indicators}, vol_ratio: {vol_ratio}, current_volume: {current_volume}, vol_ma_key: {vol_ma_key}, vol_ma: {vol_ma}, atr_key: {atr_key}, atr: {atr}, atr_threshold: {atr_threshold}, price_change: {price_change}")

        if vol_ma <= 1000:
            self.write_log(f"成交量异常: {symbol} 成交量={current_volume} {vol_ma_key}={vol_ma}, skip due to low volume")
            return

        self.write_log(f"成交量比例: {vol_ratio:.2f} (阈值: {self.exit_vol_ma5_ratio_threshold}) current_volume: {current_volume} {vol_ma_key}: {vol_ma}")

        # 判断是否触发风险控制（只在不利方向时）
        if (vol_ratio >= self.exit_vol_ma5_ratio_threshold and 
            price_change >= atr_threshold):
            
            # 检查波动方向
            movement_direction = self._get_price_movement_direction(context, current_bar)
            
            if movement_direction == 'unfavorable':
                # 只有在不利方向时才触发风险控制
                self._force_exit_due_to_risk_control(context, current_bar, vol_ratio, price_change, atr_threshold)
            else:
                # 有利方向时记录但不触发
                self.write_log(f"检测到风险条件但方向有利: {symbol} "
                              f"vol_ratio={vol_ratio:.2f} price_change={price_change:.2f} "
                              f"direction={movement_direction}")
    
    def _force_exit_due_to_risk_control(self, context, bar, vol_ratio, price_change, atr_threshold):
        """由于风险控制强制平仓"""
        symbol = context.symbol
        
        # 记录详细的风险控制事件
        self.write_log(f"触发风险控制强制平仓: {symbol}")
        self.write_log(f"  成交量比例: {vol_ratio:.2f} (阈值: {self.exit_vol_ma5_ratio_threshold})")
        self.write_log(f"  价格波动: {price_change:.2f} (阈值: {atr_threshold:.2f})")
        self.write_log(f"  波动方向: {self._get_price_movement_direction(context, bar)}")
        self.write_log(f"  Bar价格: 开{bar.open_price:.2f} 收{bar.close_price:.2f}")
        
        # 强制市价平仓
        self._force_market_exit(context)
        
        # 禁止交易当前股票
        self._ban_symbol_trading(symbol)
    
    def _execute_entry(self, context, bar, price, direction: Direction):
        """统一的 entry 订单执行方法"""
        
        order_id = self._execute_trade(
            context=context,
            bar=bar,
            price=price,
            direction=direction,
            offset=Offset.OPEN
        )
        
        if not order_id:
            # 订单被拒绝，回到 IDLE 状态
            self.update_context_state(context.symbol, StrategyState.IDLE)
            context.entry_order_id = ""

    def _execute_exit(self, context, bar, price, direction: Direction, order_type: OrderType = OrderType.LIMIT):
        """统一的 exit 订单执行方法"""
        return self._execute_trade(
            context=context,
            bar=bar,
            price=price,
            direction=direction,
            offset=Offset.CLOSE,
            order_type=order_type
        )

    def _cancel_order_safely(self, order_id: str, symbol: str) -> bool:
        """安全撤单，返回是否撤单成功"""
        if not order_id:
            return True  # 没有订单需要撤单
        
        try:
            # 创建 CancelRequest 对象
            cancel_req = CancelRequest(
                orderid=order_id,
                symbol=symbol,
                exchange=Exchange.TSE
            )
            self.gateway.cancel_order(cancel_req)
            self.write_log(f"Cancel order: {order_id}")
            
            # 等待一小段时间确保撤单处理
            time.sleep(0.1)
            
            return True
        except Exception as e:
            self.write_log(f"撤单失败: {order_id}, 错误: {e}")
            return False

    def _query_order_status_and_update(self, order_id: str, symbol: str) -> bool:
        """
        查询订单状态并触发on_order事件
        
        Args:
            order_id: 订单ID
            symbol: 股票代码
            
        Returns:
            bool: 查询是否成功
        """
        if not order_id or not self.brisk_gateway:
            return False
            
        try:
            order_data = self.brisk_gateway.query_single_order(order_id)
            if order_data:
                self.write_log(f"查询订单状态成功: {symbol} 订单ID: {order_id} 状态: {order_data.status}")
                return True
            else:
                self.write_log(f"查询订单状态失败: {symbol} 订单ID: {order_id}")
                return False
        except Exception as e:
            self.write_log(f"查询订单状态异常: {symbol} 订单ID: {order_id} 错误: {e}")
            return False

    def _cancel_order_with_verification(self, order_id: str, symbol: str) -> bool:
        """
        撤单并验证结果，如果撤单失败则查询订单状态
        
        Args:
            order_id: 订单ID
            symbol: 股票代码
            
        Returns:
            bool: 撤单是否成功
        """
        if not order_id:
            return True
            
        # 尝试撤单
        success = self._cancel_order_safely(order_id, symbol)
        
        if success:
            self.write_log(f"撤单成功: {symbol} 订单ID: {order_id}")
            return True
        else:
            self.write_log(f"撤单失败，查询订单状态: {symbol} 订单ID: {order_id}")
            
            # 撤单失败时，查询订单状态以获取最新信息
            query_success = self._query_order_status_and_update(order_id, symbol)
            
            if query_success:
                self.write_log(f"订单状态查询成功，等待on_order事件更新状态: {symbol} 订单ID: {order_id}")
            else:
                self.write_log(f"订单状态查询失败: {symbol} 订单ID: {order_id}")
                
            return False  # 撤单失败

    def _update_entry_order_price(self, context, bar, indicators, change_only: bool = False):
        """更新 entry 订单价格 - 子类可以重写"""
        # 安全性验证：确保在 WAITING_ENTRY 状态下调用
        if context.state != StrategyState.WAITING_ENTRY:
            self.write_log(f"Warning: _update_entry_order_price called in state {context.state.value} for {context.symbol}")
            return
        
        # 安全性验证：确保 entry_price 和 entry_order_id 已正确设置
        if context.entry_price <= 0 or not context.entry_order_id:
            self.write_log(f"Warning: Invalid entry_price ({context.entry_price}) or entry_order_id ({context.entry_order_id}) for {context.symbol}")
            return

        entry_order = self.gateway.query_local_order(context.entry_order_id)

        if entry_order and entry_order.status == Status.PARTTRADED:
            self.write_log(f"entry order {context.entry_order_id} is partially filled, no need to update")
            return
        
        # 计算新的 entry 价格 - 子类需要实现具体的价格计算逻辑
        old_entry_price = context.entry_price  # 当前未成交订单的下单价格
        new_entry_price = self._calculate_entry_price(context, bar, indicators)

        self.write_log(f"updating entry price for {context.symbol} old entry price: {old_entry_price:.2f} new entry price: {new_entry_price:.2f}")
        if new_entry_price != old_entry_price or not change_only:
            # 撤单并重新下单
            if self._cancel_order_safely(context.entry_order_id, context.symbol):
                # 撤单成功，重新下单 - 子类需要实现具体的下单逻辑
                self._execute_entry_with_direction(context, bar, new_entry_price)
        else:
            self.write_log(f"entry price not changed for {context.symbol}, no need to update")

    def _update_exit_order_price(self, context, bar, indicators, change_only: bool = False):
        """更新 exit 订单价格 - 子类可以重写"""
        # 安全性验证：确保在 WAITING_EXIT 状态下调用
        if context.state != StrategyState.WAITING_EXIT:
            self.write_log(f"Warning: _update_exit_order_price called in state {context.state.value} for {context.symbol}")
            return
        
        # 安全性验证：确保 exit_price 和 exit_order_id 已正确设置
        if context.exit_price <= 0 or not context.exit_order_id:
            self.write_log(f"Warning: Invalid exit_price ({context.exit_price}) or exit_order_id ({context.exit_order_id}) for {context.symbol}")
            return

        exit_order = self.gateway.query_local_order(context.exit_order_id)
        if exit_order and exit_order.status == Status.PARTTRADED:
            self.write_log(f"exit order {context.exit_order_id} is partially filled, no need to update")
            return
        
        # 计算新的 exit 价格
        old_exit_price = context.exit_price  # 当前未成交订单的下单价格
        new_exit_price = self._calculate_exit_price(context, bar, indicators)
        
        self.write_log(f"updating exit price for {context.symbol} old exit price: {old_exit_price:.2f} new exit price: {new_exit_price:.2f}")
        if new_exit_price != old_exit_price or not change_only:
            # 撤单并重新下单
            if self._cancel_order_safely(context.exit_order_id, context.symbol):
                # 撤单成功，重新下单 - 子类需要实现具体的下单逻辑
                self._execute_exit_with_direction(context, bar, new_exit_price)

    # ==================== 已实现的方法 ====================
    
    def _execute_entry_with_direction(self, context, bar, price):
        """根据策略逻辑执行 entry 订单 - 现在可以在base strategy中实现"""
        entry_direction = self.get_entry_direction(context.symbol)
        
        if entry_direction == 'short':
            self._execute_entry(context, bar, price, Direction.SHORT)
        elif entry_direction == 'long':
            self._execute_entry(context, bar, price, Direction.LONG)
        else:
            self.write_log(f"警告: {context.symbol} 的entry方向为 'none'，跳过entry订单执行")
    
    def _execute_exit_with_direction(self, context, bar, price):
        """根据策略逻辑执行 exit 订单 - 现在可以在base strategy中实现"""
        entry_direction = self.get_entry_direction(context.symbol)
        
        if entry_direction == 'short':
            # 做空策略，平仓需要买入
            self._execute_exit(context, bar, price, Direction.LONG)
        elif entry_direction == 'long':
            # 做多策略，平仓需要卖出
            self._execute_exit(context, bar, price, Direction.SHORT)
        else:
            self.write_log(f"警告: {context.symbol} 的entry方向为 'none'，跳过exit订单执行")

    # ==================== 子类需要实现的抽象方法 ====================
    
    def get_entry_direction(self, symbol: str) -> str:
        """获取指定股票的entry方向 - 子类必须实现
        
        Returns:
            str: 'long' 表示做多, 'short' 表示做空, 'none' 表示不交易
        """
        raise NotImplementedError("子类必须实现 get_entry_direction 方法")
    
    def _calculate_entry_price(self, context, bar, indicators) -> float:
        """计算 entry 价格 - 子类必须实现"""
        raise NotImplementedError("子类必须实现 _calculate_entry_price 方法")
    
    def _calculate_exit_price(self, context, bar, indicators) -> float:
        """计算 exit 价格 - 子类必须实现"""
        raise NotImplementedError("子类必须实现 _calculate_exit_price 方法")
    
    def on_order(self, event):
        """订单状态变化回调 - 子类可以重写"""
        pass
    
    def on_trade(self, event):
        """成交回调 - 子类可以重写"""
        pass
    
    def add_symbol(self, symbol: str):
        """为指定股票创建BarGenerator和技术指标管理器
        
        子类可以重写此方法来自定义bar generator和技术指标的配置
        """
        # 创建增强版K线生成器
        self.bar_generators[symbol] = self._create_bar_generator(symbol)
        
        # 创建技术指标管理器
        self.indicator_managers[symbol] = self._create_indicator_manager(symbol)
        
        self.write_log(f"为 {symbol} 创建了BarGenerator和技术指标管理器")
    
    def _create_bar_generator(self, symbol: str):
        """创建BarGenerator - 子类可以重写此方法来自定义配置"""
        return EnhancedBarGenerator(
            on_bar=self.on_1min_bar,
            window=self.bar_window,  # 使用配置的窗口大小
            on_window_bar=self.on_5min_bar,
            interval=self.bar_interval,  # 使用配置的间隔
            enable_opening_volume=self.enable_opening_volume,  # 使用配置的开盘成交量设置
            enable_auto_flush=self.enable_auto_flush,  # 使用配置的强制收线设置
            main_engine=self.main_engine  # 传入main_engine
        )
    
    def _create_indicator_manager(self, symbol: str):
        """创建技术指标管理器 - 子类可以重写此方法来自定义配置"""
        return TechnicalIndicatorManager(symbol, size=self.indicator_size)  # 使用配置的大小
    
    def on_tick(self, event: Event):
        """Tick数据回调函数"""
        tick = event.data
        
        # 新增：在更新bar和技术指标之前检查触发条件
        if self.enable_delayed_entry:
            self._check_and_execute_trigger(tick)
            
        # 更新对应的BarGenerator
        if tick.symbol in self.bar_generators:
            self.bar_generators[tick.symbol].update_tick(tick)
    
    def on_1min_bar(self, bar: BarData):
        """1分钟K线回调函数"""
        self.write_log(f"on_1min_bar triggered: {bar.symbol}")
        self.bars_count[f"{bar.symbol}_1min"] += 1
        
        # 更新技术指标
        if bar.symbol in self.indicator_managers:
            indicators = self.indicator_managers[bar.symbol].update_bar(bar)
            
            # 打印详细的指标信息
            print(f"\n=== 1分钟K线: {bar.symbol} {bar.datetime.strftime('%Y-%m-%d %H:%M:%S')} ===")
            print(f"价格数据:")
            print(f"  开盘: {bar.open_price:.2f}  最高: {bar.high_price:.2f}  最低: {bar.low_price:.2f}  收盘: {bar.close_price:.2f}")
            print(f"  成交量: {bar.volume:.0f}  成交额: {bar.turnover:.0f}")
            
            print(f"技术指标:")
            # 灵活处理VWAP指标
            if 'vwap' in indicators:
                print(f"  VWAP: {indicators['vwap']:.2f}")
            
            # 灵活处理ATR指标（支持不同的周期）
            atr_keys = [key for key in indicators.keys() if key.startswith('atr_')]
            for atr_key in atr_keys:
                print(f"  {atr_key.upper()}: {indicators[atr_key]:.2f}")
            
            # 灵活处理Volume MA指标（支持不同的周期）
            vol_ma_keys = [key for key in indicators.keys() if key.startswith('volume_ma')]
            for vol_ma_key in vol_ma_keys:
                print(f"  {vol_ma_key.upper()}: {indicators[vol_ma_key]:.0f}")
            
            print(f"统计信息:")
            # 灵活处理VWAP统计信息
            if 'above_vwap_count' in indicators:
                print(f"  Close > VWAP: {indicators['above_vwap_count']} 次")
            if 'below_vwap_count' in indicators:
                print(f"  Close < VWAP: {indicators['below_vwap_count']} 次")
            if 'equal_vwap_count' in indicators:
                print(f"  Close = VWAP: {indicators['equal_vwap_count']} 次")
            
            print(f"累计数据:")
            # 灵活处理累计数据
            if 'daily_acc_volume' in indicators:
                print(f"  当日累计成交量: {indicators['daily_acc_volume']:.0f}")
            if 'daily_acc_turnover' in indicators:
                print(f"  当日累计成交额: {indicators['daily_acc_turnover']:.0f}")
            print(f"=== ===\n")
            
            # 计算一些额外的指标（只在相关数据存在时）
            if 'daily_acc_volume' in indicators and 'daily_acc_turnover' in indicators:
                if indicators['daily_acc_volume'] > 0:
                    avg_price = indicators['daily_acc_turnover'] / indicators['daily_acc_volume']
                    print(f"  当日平均价格: {avg_price:.2f}")
            
            if 'above_vwap_count' in indicators and 'below_vwap_count' in indicators:
                if indicators['above_vwap_count'] + indicators['below_vwap_count'] > 0:
                    above_ratio = indicators['above_vwap_count'] / (indicators['above_vwap_count'] + indicators['below_vwap_count'])
                    print(f"  Close > VWAP 比例: {above_ratio:.2%}")
    
    def on_5min_bar(self, bar: BarData):
        """5分钟K线回调函数"""
        self.bars_count[f"{bar.symbol}_5min"] += 1
        self.write_log(f"生成5分钟K线: {bar.symbol} {bar.datetime.strftime('%Y-%m-%d %H:%M:%S')} - "
              f"开:{bar.open_price:.2f} 高:{bar.high_price:.2f} 低:{bar.low_price:.2f} "
              f"收:{bar.close_price:.2f} 量:{bar.volume}")
    
    def connect(self, setting: dict = None):
        """连接Gateway，支持多种gateway类型"""
        # 根据gateway_type选择对应的gateway类
        if self.gateway_type == "mock":
            gateway_cls = MockBriskGateway
            gateway_name = "MOCK_BRISK"
        elif self.gateway_type == "brisk_eshiten":
            gateway_cls = BriskEshitenGateway
            gateway_name = "BRISK_ESHITEN"
        elif self.gateway_type == "brisk_click":
            gateway_cls = BriskClickGateway
            gateway_name = "BRISK_CLICK"
        elif self.gateway_type == "kabus":
            gateway_cls = KabusGateway
            gateway_name = "KABUS"
        else:  # 默认使用brisk
            gateway_cls = BriskGateway
            gateway_name = "BRISK"

        if not self.main_engine:
            self.event_engine = EventEngine()
            self.main_engine = MainEngine(self.event_engine)
            self.main_engine.add_gateway(gateway_cls)
            self.gateway = self.main_engine.get_gateway(gateway_name)
            self.gateway_name = gateway_name
            self.brisk_gateway = self.gateway
            # 注册事件
            self.event_engine.register(EVENT_TICK, self.on_tick)
            # self.event_engine.register(EVENT_LOG, self.on_log)
            self.event_engine.register(EVENT_ORDER, self.on_order)
            self.event_engine.register(EVENT_TRADE, self.on_trade)

        log_engine: LogEngine = self.main_engine.get_engine("log")       # type: ignore
        self.event_engine.register(EVENT_LOG, log_engine.process_log_event)

        if setting is None:
            if self.gateway_type == "mock":
                setting = {
                    "tick_mode": "mock",
                    "mock_account_balance": 10000000,
                }
            elif self.gateway_type == "brisk_eshiten":
                setting = {
                    "tick_server_url": "ws://127.0.0.1:8001/ws",
                    "tick_server_http_url": "http://127.0.0.1:8001",
                    "reconnect_interval": 5,
                    "heartbeat_interval": 30,
                    "max_reconnect_attempts": 20,
                    "polling_interval": 1,
                }
            elif self.gateway_type == "brisk_click":
                setting = {
                    "tick_server_url": "ws://127.0.0.1:8001/ws",
                    "tick_server_http_url": "http://127.0.0.1:8001",
                    "reconnect_interval": 5,
                    "heartbeat_interval": 30,
                    "max_reconnect_attempts": 20,
                    "polling_interval": 5,
                }
            elif self.gateway_type == "kabus":
                setting = {
                    "tick_server_url": "ws://192.168.50.131:16080/kabusapi/websocket",
                    "tick_server_http_url": "http://192.168.50.131:16080/kabusapi/websocket",
                    "reconnect_interval": 5,
                    "max_reconnect_attempts": 20,
                    "polling_interval": 10,
                }
            else:  # brisk
                setting = {
                    "tick_server_url": "ws://127.0.0.1:8001/ws",
                    "tick_server_http_url": "http://127.0.0.1:8001",
                }
        self.main_engine.connect(setting, self.gateway_name)
        self.write_log(f"{self.gateway_name} Gateway连接成功")
    
    def subscribe(self, symbols: list):
        """订阅股票"""
        for symbol in symbols:
            # 添加股票到技术指标管理器
            self.add_symbol(symbol)
            
        # 订阅行情
        # hacky way to do batch subscription. TODO: design a better way
        req = SubscribeRequest(symbol=','.join(symbols), exchange=Exchange.TSE)
        self.main_engine.subscribe(req, self.gateway_name)
        self.write_log(f"subscribe: {','.join(symbols)}")
    
    def start_replay(self, date: str, symbols: list = None):
        """开始历史数据回放"""
        if symbols is None:
            symbols = list(self.indicator_managers.keys())
        
        # 统一调用Gateway的回放方法
        if hasattr(self.gateway, 'start_replay'):
            self.gateway.start_replay(date, symbols)
            print(f"开始回放 {date} 的历史数据")
        else:
            print(f"当前Gateway不支持回放功能")
    
    def stop_replay(self):
        """停止历史数据回放"""
        if hasattr(self.gateway, 'stop_replay'):
            self.gateway.stop_replay()
            print("停止历史数据回放")
        else:
            print("当前Gateway不支持回放功能")
    
    def get_indicators(self, symbol: str) -> dict:
        """获取指定股票的技术指标"""
        if symbol in self.indicator_managers:
            return self.indicator_managers[symbol].get_indicators()
        return {}
    
    def _get_current_bar(self, symbol: str) -> Optional[BarData]:
        """获取当前正在构建的1分钟bar"""
        bar_gen = self.bar_generators.get(symbol)
        if bar_gen and hasattr(bar_gen, 'bar'):
            return bar_gen.bar
        return None
    
    def get_all_indicators(self) -> dict:
        """获取所有股票的技术指标"""
        all_indicators = {}
        for symbol in self.indicator_managers:
            all_indicators[symbol] = self.get_indicators(symbol)
        return all_indicators
    
    def print_summary(self):
        """打印统计摘要"""
        print("\n=== 统计摘要 ===")
        print("K线生成统计:")
        for key, count in self.bars_count.items():
            print(f"  {key}: {count} 根")
        
        print("\n技术指标状态:")
        for symbol in self.indicator_managers:
            manager = self.indicator_managers[symbol]
            indicators = manager.get_indicators()
            if indicators:
                # 灵活处理VWAP指标
                vwap_info = ""
                if 'vwap' in indicators:
                    vwap_info += f"VWAP={indicators['vwap']:.2f}, "
                
                # 灵活处理ATR指标（支持不同的周期）
                atr_info = ""
                atr_keys = [key for key in indicators.keys() if key.startswith('atr_')]
                for atr_key in atr_keys:
                    atr_info += f"{atr_key.upper()}={indicators[atr_key]:.2f}, "
                
                # 灵活处理VWAP统计信息
                stats_info = ""
                if 'above_vwap_count' in indicators:
                    stats_info += f"Close>VWAP={indicators['above_vwap_count']}"
                
                # 组合所有信息
                all_info = vwap_info + atr_info + stats_info
                if all_info:
                    # 移除最后的逗号和空格
                    all_info = all_info.rstrip(', ')
                    print(f"  {symbol}: {all_info}")
                else:
                    print(f"  {symbol}: 无可用指标")
    
    def close(self):
        """关闭连接"""
        self.brisk_gateway.close()
        self.event_engine.stop()
        print("Brisk Gateway Demo已关闭")

    # 新增：Black List管理方法
    
    def set_black_list(self, symbols: list):
        """设置黑名单（主要用于初始化）"""
        self.black_list = set(symbols)
        self.write_log(f"设置黑名单: {len(symbols)}只股票")

    def is_symbol_blacklisted(self, symbol: str) -> bool:
        """检查股票是否在黑名单中"""
        if not self.black_list_enabled:
            return False
        return symbol in self.black_list

    def get_black_list(self) -> set:
        """获取当前黑名单"""
        return self.black_list.copy()

    def clear_black_list(self):
        """清空黑名单"""
        removed_count = len(self.black_list)
        self.black_list.clear()
        self.write_log(f"清空黑名单，移除{removed_count}只股票")

    def remove_from_eligible_stocks(self, symbol: str):
        """从eligible_stocks中移除股票"""
        if hasattr(self, 'eligible_stocks') and symbol in self.eligible_stocks:
            self.eligible_stocks.discard(symbol)
            self.write_log(f"从eligible_stocks中移除股票: {symbol}")

    def add_to_eligible_stocks(self, symbol: str):
        """添加股票到eligible_stocks时自动过滤黑名单"""
        if hasattr(self, 'eligible_stocks'):
            # 检查是否在黑名单中
            if not self.is_symbol_blacklisted(symbol):
                # 直接操作set，避免递归调用
                self.eligible_stocks.add(symbol)
                self.write_log(f"添加股票到eligible_stocks: {symbol}")
            else:
                self.write_log(f"跳过黑名单股票: {symbol}")

    def batch_remove_from_eligible_stocks(self, symbols: list):
        """批量从eligible_stocks中移除股票"""
        if hasattr(self, 'eligible_stocks'):
            removed = []
            for symbol in symbols:
                if symbol in self.eligible_stocks:
                    self.eligible_stocks.discard(symbol)
                    removed.append(symbol)
            
            if removed:
                self.write_log(f"批量从eligible_stocks中移除股票: {removed}")

    def batch_add_to_eligible_stocks(self, symbols: list):
        """批量添加股票到eligible_stocks（自动过滤黑名单）"""
        if hasattr(self, 'eligible_stocks'):
            added = []
            skipped = []
            for symbol in symbols:
                if not self.is_symbol_blacklisted(symbol):
                    self.eligible_stocks.add(symbol)
                    added.append(symbol)
                else:
                    skipped.append(symbol)
            
            if added:
                self.write_log(f"批量添加到eligible_stocks: {added}")
            if skipped:
                self.write_log(f"跳过黑名单股票: {skipped}")


def main():
    """主函数"""
    print("启动日内策略基础框架...")
    
    # 创建策略实例
    strategy = IntradayStrategyBase()
    
    try:
        # 连接Gateway
        strategy.connect()
        
        # 订阅股票（这里使用示例股票代码）
        # symbols = ["7203", "6758", "9984"]  # 丰田、索尼、软银
        symbols = ["9984"]  # 软银
        strategy.subscribe(symbols)
        
        # 等待一段时间接收数据
        print("等待接收数据...")
        time.sleep(1)
        
        # 打印摘要
        # strategy.print_summary()
        
        # 或者开始历史数据回放
        strategy.start_replay("20250725", symbols)
        # time.sleep(30)
        # strategy.stop_replay()
        
        # 保持运行
        print("按Ctrl+C退出...")
        while True:
            time.sleep(1)
            
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