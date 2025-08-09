"""
VWAP Failure 日内交易策略
基于intraday_strategy_base实现，寻找gap up/down后的VWAP failure机会
"""
import time
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, Set

from vnpy.trader.constant import Direction, Offset, Status, OrderType, Exchange
from vnpy.trader.object import OrderData, OrderRequest, TradeData, CancelRequest

from intraday_strategy_base import IntradayStrategyBase, StrategyState
from mock_brisk_gateway import MockBriskGateway

from common.trading_common import next_tick_price, TypicalTimes


class VWAPFailureStrategy(IntradayStrategyBase):
    """VWAP Failure 日内交易策略"""
    
    def __init__(self, use_mock_gateway=True, enable_delayed_entry=False):
        super().__init__(use_mock_gateway=use_mock_gateway)
        
        # 设置延迟执行标志
        self.enable_delayed_entry = enable_delayed_entry
        
        # 策略参数
        self.market_cap_threshold = 100_000_000_000  # 1000亿日元
        self.gap_up_threshold = 0.02    # 2% gap up
        self.gap_down_threshold = -0.02 # -2% gap down
        self.failure_threshold_gap_up = 3      # Gap Up时的VWAP failure次数阈值
        self.failure_threshold_gap_down = 2    # Gap Down时的VWAP failure次数阈值
        self.entry_factor_gap_up = 1.5         # Gap Up时的ATR倍数
        self.entry_factor_gap_down = 1.2       # Gap Down时的ATR倍数
        self.max_daily_trades_gap_up = 3       # Gap Up时单个股票单日最多执行策略次数
        self.max_daily_trades_gap_down = 2     # Gap Down时单个股票单日最多执行策略次数
        self.latest_entry_time = "14:30:00"  # 最晚入场时间
        self.exit_factor_gap_up = 1.0          # Gap Up时的平仓ATR倍数
        self.exit_factor_gap_down = 0.8        # Gap Down时的平仓ATR倍数
        self.max_exit_wait_time_gap_up = 30    # Gap Up时的最大平仓等待时间（分钟）
        self.max_exit_wait_time_gap_down = 20  # Gap Down时的最大平仓等待时间（分钟）
        self.max_vol_ma5_ratio_threshold_gap_up = 2.0    # Gap Up时当前bar的vol/vol_ma5比例上限
        self.max_vol_ma5_ratio_threshold_gap_down = 1.5  # Gap Down时当前bar的vol/vol_ma5比例上限
        self.timeout_exit_max_period = 5       # timeout exit limit order最大等待时间（分钟）
        
        # 新增：风险控制参数（设置较高的默认值）
        self.exit_vol_ma5_ratio_threshold = 5.0    # exit时的成交量比例阈值（默认5倍）
        self.force_exit_atr_factor = 3.0           # 强制平仓的ATR倍数（默认3倍）
        
        # 新增：延迟执行ATR倍数参数
        self.delayed_entry_atr_multiplier = 2.0    # 延迟执行的ATR倍数（默认2倍，保持向后兼容）
        
        # 股票状态管理
        self.market_cap_eligible = set()  # 仅满足市值条件的股票
        self.eligible_stocks = set()    # 真正满足所有条件的股票
        self.first_tick_prices = {}     # 记录每个股票当天第一个tick价格
        self.gap_direction = {}         # 记录gap方向：'up', 'down', 'none'
        self.trading_date = None        # 当前交易日期
        
        # 信号统计
        self.signal_count = 0           # 信号计数
        self.signals = []               # 信号记录
    
    def initialize_stock_filter(self):
        """初始化股票筛选器"""
        self.write_log("初始化股票筛选器...")
        
        # 1. 获取股票基础信息
        self.initialize_stock_master()
        
        # 2. 基于市值预筛选股票
        self._pre_filter_by_market_cap()
        
        # 3. 订阅市值符合条件的股票（用于获取第一个tick价格）
        if self.market_cap_eligible:
            self.subscribe(list(self.market_cap_eligible))
            self.write_log(f"订阅了 {len(self.market_cap_eligible)} 只市值符合条件的股票")
        else:
            self.write_log("没有找到市值符合条件的股票")
        
    def _pre_filter_by_market_cap(self):
        """基于市值预筛选股票"""
        for symbol, stock_info in self.stock_master.items():
            market_cap = stock_info.get('market_cap', 0)
            prefix = stock_info.get('prefix', '')
            if market_cap >= self.market_cap_threshold and prefix != 'E':
                self.market_cap_eligible.add(symbol)
                # print(f"股票 {symbol} 通过市值筛选: {market_cap:,.0f} 日元")
        
        self.write_log(f"市值筛选后符合条件的股票数量: {len(self.market_cap_eligible)}")
    
    def on_tick(self, event):
        """重写tick处理逻辑"""
        tick = event.data
        
        # 检查是否是新的一天（在第一个tick时就检查）
        self._check_new_trading_day(tick.datetime)
        
        # 只处理市值符合条件的股票
        if tick.symbol not in self.market_cap_eligible:
            return
            
        # 记录第一个tick价格并评估gap条件
        if tick.symbol not in self.first_tick_prices:
            self.first_tick_prices[tick.symbol] = tick.last_price
            self._evaluate_gap_condition(tick.symbol)
        
        # 只处理真正符合条件的股票
        if tick.symbol in self.eligible_stocks:
            # 先调用父类方法，确保技术指标和bar都已更新
            super().on_tick(event)
            
            # 检查当前bar的成交量异常并取消订单
            self._check_current_bar_volume_anomaly_and_cancel(tick)
            
            # 新增：检查exit风险控制
            self._check_exit_risk_control(tick)
    
    def _check_new_trading_day(self, datetime_obj):
        """检查是否是新交易日，如果是则重置相关数据"""
        current_date = datetime_obj.date()
        
        if self.trading_date != current_date:
            self.write_log(f"新交易日开始: {current_date}")
            self.trading_date = current_date
            
            # 重置所有 Context - 使用父类方法
            self.reset_all_contexts()
            
            # 重置其他状态
            self.first_tick_prices.clear()
            self.gap_direction.clear()
            self.eligible_stocks.clear()
            
            # 重置信号统计
            self.signal_count = 0
            self.signals.clear()
            
            self.write_log("策略状态已重置")
    
    def _evaluate_gap_condition(self, symbol):
        """评估gap条件"""
        if symbol not in self.first_tick_prices:
            return
        
        first_price = self.first_tick_prices[symbol]
        prev_close = self.get_stock_prev_close(symbol)
        
        if prev_close > 0:
            gap_ratio = (first_price - prev_close) / prev_close
            
            if gap_ratio >= self.gap_up_threshold:
                self.gap_direction[symbol] = 'up'
                self.eligible_stocks.add(symbol)
                self.write_log(f"股票 {symbol} 满足 Gap Up 条件: {gap_ratio:.2%}")
            elif gap_ratio <= self.gap_down_threshold:
                self.gap_direction[symbol] = 'down'
                self.eligible_stocks.add(symbol)
                self.write_log(f"股票 {symbol} 满足 Gap Down 条件: {gap_ratio:.2%}")
            else:
                self.gap_direction[symbol] = 'none'

    def on_order(self, event):
        """订单状态变化回调"""
        order = event.data
        context = self.get_context_by_order_id(order.orderid)
        if not context:
            return

        self.write_log(f"Order event: {order.orderid} for {context.symbol}, "
                      f"entry_order_id: {context.entry_order_id}, "
                      f"exit_order_id: {context.exit_order_id}")
        
        if order.orderid == context.entry_order_id:
            self._handle_entry_order_update(order, context)
        elif order.orderid == context.exit_order_id:
            self._handle_exit_order_update(order, context)

    def on_trade(self, event):
        """成交回调"""
        trade = event.data
        context = self.get_context_by_order_id(trade.orderid)
        if not context:
            return
        
        # 添加调试信息
        self.write_log(f"Trade event: {trade.orderid} for {context.symbol}, "
                      f"entry_order_id: {context.entry_order_id}, "
                      f"exit_order_id: {context.exit_order_id}")
        
        if trade.orderid == context.entry_order_id:
            self._handle_entry_trade(trade, context)
        elif trade.orderid == context.exit_order_id:
            self._handle_exit_trade(trade, context)
        else:
            self.write_log(f"Trade order ID {trade.orderid} doesn't match any known order")

    def _handle_entry_order_update(self, order: OrderData, context):
        """处理 entry 订单状态更新"""
        if order.status == Status.REJECTED:
            # entry 订单被拒绝，回到 IDLE 状态
            self.update_context_state(context.symbol, StrategyState.IDLE)
            context.entry_order_id = ""
            self.write_log(f"Entry order rejected for {context.symbol}")
            
        elif order.status == Status.ALLTRADED:
            # entry 订单完全成交，状态迁移到 HOLDING
            self.update_context_state(context.symbol, StrategyState.HOLDING)
            self.write_log(f"Entry order completed for {context.symbol}")
            context.already_traded = 0
            
            # 生成 exit 订单（统一在on_order中处理）
            self._generate_exit_order_from_order(context, order)
        
        elif order.status == Status.PARTTRADED:
            context.already_traded = order.traded
            self.write_log(f"Entry order partially filled for {context.symbol}, already_traded: {context.already_traded}")

    def _handle_exit_order_update(self, order: OrderData, context):
        """处理 exit 订单状态更新"""
        self.write_log(f"exit order update: {order}")
        if order.status == Status.REJECTED:
            # exit 订单被拒绝，回到 HOLDING 状态
            self.update_context_state(context.symbol, StrategyState.HOLDING)
            context.exit_order_id = ""
            self.write_log(f"Exit order rejected for {context.symbol}")
            
        elif order.status == Status.ALLTRADED:
            # exit 订单完全成交，交易完成，增加交易次数
            context.trade_count += 1
            
            # 检查是否应该增加timeout_trade_count
            should_increment_timeout_count = (
                order.type == OrderType.MARKET or 
                context.state == StrategyState.WAITING_TIMEOUT_EXIT
            )
            
            if should_increment_timeout_count:
                context.timeout_trade_count += 1
                self.write_log(f"Timeout trade completed for {context.symbol}, "
                              f"timeout_trade_count: {context.timeout_trade_count}")
            
            context.already_traded = 0
            self.update_context_state(context.symbol, StrategyState.IDLE)
            context.exit_order_id = ""
            self.write_log(f"_handle_exit_order_update: Trade completed for {context.symbol}, count: {context.trade_count}")
            
        elif order.status == Status.CANCELLED:
            # 订单被取消 - 只记录日志，不处理逻辑
            # 因为cancel是同步的，逻辑已经在cancel成功后处理
            self.write_log(f"_handle_exit_order_update: Exit order cancelled for {context.symbol}")

        elif order.status == Status.PARTTRADED:
            context.already_traded = order.traded
            self.write_log(f"Exit order partially filled for {context.symbol}, already_traded: {context.already_traded}")

    def _handle_entry_trade(self, trade: TradeData, context):
        """处理 entry 成交（简化版本，主要逻辑在on_order中处理）"""
        # 只记录成交信息，不重复处理状态和exit订单生成
        self.write_log(f"Entry trade filled for {context.symbol}: {trade.volume} @ {trade.price}")

    def _handle_exit_trade(self, trade: TradeData, context):
        """处理 exit 成交（简化版本，主要逻辑在on_order中处理）"""
        # 只记录成交信息，不重复处理状态
        self.write_log(f"Exit trade filled for {context.symbol}: {trade.volume} @ {trade.price}")

    def _generate_exit_order_from_order(self, context, entry_order: OrderData):
        """从entry订单生成exit订单"""
        # 记录 entry 成交信息（使用订单价格）
        context.entry_price = entry_order.price
        context.entry_time = entry_order.datetime
        
        self.write_log(f"Generating exit order for {context.symbol} after entry order {entry_order.orderid} completed")
        
        # 获取技术指标并计算 exit 价格
        indicators = self.get_indicators(context.symbol)
        exit_price = self._calculate_exit_price(context, None, indicators)
        
        # 根据 gap 方向使用对应的 exit 方法
        if self._is_gap_up(context.symbol):
            # Gap Up 策略是做空，平仓需要买入
            exit_order_id = self._execute_exit(context, None, exit_price, Direction.LONG, OrderType.LIMIT)
        else:
            # Gap Down 策略是做多，平仓需要卖出
            exit_order_id = self._execute_exit(context, None, exit_price, Direction.SHORT, OrderType.LIMIT)
        
        self.write_log(f"Exit order generated: {exit_order_id} for {context.symbol}")

    def _is_gap_up(self, symbol: str) -> bool:
        """判断是否为 gap up"""
        return self.gap_direction.get(symbol, 'none') == 'up'
    
    def _get_failure_threshold(self, symbol: str) -> int:
        """根据gap方向获取对应的failure_threshold"""
        if self._is_gap_up(symbol):
            return self.failure_threshold_gap_up
        else:
            return self.failure_threshold_gap_down
    
    def _get_entry_factor(self, symbol: str) -> float:
        """根据gap方向获取对应的entry_factor"""
        if self._is_gap_up(symbol):
            return self.entry_factor_gap_up
        else:
            return self.entry_factor_gap_down
    
    def _get_exit_factor(self, symbol: str) -> float:
        """根据gap方向获取对应的exit_factor"""
        if self._is_gap_up(symbol):
            return self.exit_factor_gap_up
        else:
            return self.exit_factor_gap_down
    
    def _get_daily_trades_for_gap(self, symbol: str) -> int:
        """根据gap方向获取对应的max_daily_trades"""
        if self._is_gap_up(symbol):
            return self.max_daily_trades_gap_up
        else:
            return self.max_daily_trades_gap_down
    
    def _get_exit_wait_time(self, symbol: str) -> int:
        """根据gap方向获取对应的max_exit_wait_time"""
        if self._is_gap_up(symbol):
            return self.max_exit_wait_time_gap_up
        else:
            return self.max_exit_wait_time_gap_down
    
    def _get_max_vol_ma5_ratio_threshold(self, symbol: str) -> float:
        """根据gap方向获取对应的max_vol_ma5_ratio_threshold"""
        if self._is_gap_up(symbol):
            return self.max_vol_ma5_ratio_threshold_gap_up
        else:
            return self.max_vol_ma5_ratio_threshold_gap_down
    
    def _check_current_bar_volume_anomaly_and_cancel(self, tick):
        """检查当前1分钟bar的成交量异常并取消订单"""
        symbol = tick.symbol
        context = self.get_context(symbol)
        
        # 检查状态是否为waiting_entry
        if context.state != StrategyState.WAITING_ENTRY:
            return
        
        # 获取当前正在构建的1分钟bar
        current_bar = self._get_current_bar(symbol)
        if not current_bar:
            return
        
        # 获取技术指标
        indicators = self.get_indicators(symbol)
        if not indicators:
            return
        
        # 计算成交量比例
        current_bar_volume = current_bar.volume  # 当前1分钟bar的成交量
        vol_ma5 = indicators.get('volume_ma5', 0)
        max_ratio = self._get_max_vol_ma5_ratio_threshold(symbol)

        # 检查是否超过阈值
        if vol_ma5 > 0 and (current_bar_volume / vol_ma5) > max_ratio:
            # 取消订单
            if context.entry_order_id and not context.entry_canceled_by_vol_ma5:
                if self._cancel_order_safely(context.entry_order_id, symbol):
                    # 重置状态
                    context.entry_order_id = ""
                    self.update_context_state(symbol, StrategyState.IDLE)
                    
                    # 记录日志
                    self.write_log(f"当前bar成交量异常取消订单: {symbol}, "
                                f"当前bar成交量: {current_bar_volume}, "
                                f"MA5: {vol_ma5:.0f}, "
                                f"比例: {current_bar_volume/vol_ma5:.2f}, "
                                f"阈值: {max_ratio}")
                else:
                    context.entry_canceled_by_vol_ma5 = True
                    self.write_log(f"当前bar成交量异常取消订单失败: {symbol}, order id: {context.entry_order_id} may be already filled")

    def on_1min_bar(self, bar):
        """重写1分钟K线处理逻辑"""
        # 只处理真正符合条件的股票
        if bar.symbol not in self.eligible_stocks:
            return
            
        # 调用父类方法更新技术指标
        super().on_1min_bar(bar)
        
        # reset the entry_canceled_by_vol_ma5 flag
        context = self.get_context(bar.symbol)
        context.entry_canceled_by_vol_ma5 = False

        # 获取技术指标
        indicators = self.get_indicators(bar.symbol)
        if not indicators:
            return
        
        # 更新等待中的订单价格（基于 Context）
        self._update_pending_orders(bar, indicators)
        
        # 生成交易信号（基于 Context 状态）
        self._generate_trading_signal(bar, indicators)

    def _update_pending_orders(self, bar, indicators):
        """更新等待中的订单价格 - 完全基于 Context"""
        symbol = bar.symbol
        context = self.get_context(symbol)
        
        # 更新 entry 订单
        # for entry case, if it's alreadsy past the latest_entry_time, cancel the the existing order if any instead of updating the price
        if context.state == StrategyState.WAITING_ENTRY and context.entry_order_id:
            if not self._is_within_trading_time(bar.datetime):
                entry_order = self.gateway.query_local_order(context.entry_order_id)
                self._cancel_order_safely(context.entry_order_id, symbol)
                if context.already_traded > 0:
                    self.write_log(f"entry order {context.entry_order_id} is partially filled, execute exit")
                    self._execute_exit(context, None, 0, Direction.LONG if self._is_gap_up(symbol) else Direction.SHORT, OrderType.MARKET)
                context.entry_order_id = ""
                self.update_context_state(symbol, StrategyState.IDLE)
                return
            self._update_entry_order_price(context, bar, indicators, change_only=True)
        
        # 更新 exit 订单
        elif (context.state == StrategyState.WAITING_EXIT or context.state == StrategyState.WAITING_TIMEOUT_EXIT) and context.exit_order_id:
            if not self._check_exit_timeout(context, bar):
                self._update_exit_order_price(context, bar, indicators, change_only=True)

    def _check_exit_timeout(self, context, bar):
        """检查 exit 订单是否超时"""
        if not context.exit_start_time or not context.exit_order_id:
            return False
        
        # TODO: tricky edge case which need specific test to prove. but we still prefer to use bar.datetime instead of datetime.now() to sync time
        current_time = bar.datetime + timedelta(minutes=1)
        max_wait_time = timedelta(minutes=self._get_exit_wait_time(context.symbol) - 1)
        self.write_log(f"current_time: {current_time}, context.exit_start_time: {context.exit_start_time}, max_wait_time: {max_wait_time}, context: {context}")
        
        # for exit case, if it's alreadsy past the latest_entry_time, enter the timeout exit flow
        # 第一阶段：检查是否达到初始timeout
        if context.state == StrategyState.WAITING_EXIT and ((current_time - context.exit_start_time) >= max_wait_time or self._is_within_one_min_before_morning_closing_start(current_time - timedelta(minutes=1))):
            # 撤单并进入timeout exit阶段
            if self._cancel_order_safely(context.exit_order_id, context.symbol):
                self._start_timeout_exit(context)
                return True
        
        # 第二阶段：检查timeout exit limit order是否超时
        elif context.state == StrategyState.WAITING_TIMEOUT_EXIT:
            timeout_exit_max_period = timedelta(minutes=self.timeout_exit_max_period)
            if (current_time - context.timeout_exit_start_time) >= timeout_exit_max_period or self._is_within_morning_closing_time(current_time - timedelta(minutes=1)):
                self._force_market_exit(context)
            return True
        
        return False

    def _start_timeout_exit(self, context):
        """开始timeout exit流程"""
        # 获取当前last price
        current_bar = self._get_current_bar(context.symbol)
        if not current_bar:
            # 如果没有bar数据，直接使用market order
            self.write_log(f"_start_timeout_exit: No bar data, use last tick price instead")
            bar_gen = self.bar_generators.get(context.symbol)
            limit_price = None
            if bar_gen:
                # this branch will be reached when force_flush_bar is called
                limit_price = bar_gen.get_last_tick_price()
            if limit_price is None:
                self._force_market_exit(context)
                return
        else:
            # 使用last price挂limit order
            limit_price = current_bar.close_price
        
        # 根据gap方向确定平仓方向
        # note _execute_exit will update context.exit_order_id and context.exit_start_time
        if self._is_gap_up(context.symbol):
            # Gap Up策略是做空，平仓需要买入
            self._execute_exit(context, current_bar, limit_price, Direction.LONG, OrderType.LIMIT)
        else:
            # Gap Down策略是做多，平仓需要卖出
            self._execute_exit(context, current_bar, limit_price, Direction.SHORT, OrderType.LIMIT)
        
        # 更新状态和时间
        self.update_context_state(context.symbol, StrategyState.WAITING_TIMEOUT_EXIT)
        context.timeout_exit_start_time = datetime.now()
        
        self.write_log(f"Started timeout exit for {context.symbol} with limit price: {limit_price}")

    def _force_market_exit(self, context):
        """强制使用market order平仓"""
        # 先取消当前的limit order（如果存在）
        if context.exit_order_id:
            self._cancel_order_safely(context.exit_order_id, context.symbol)
        
        # 然后使用market order平仓
        if self._is_gap_up(context.symbol):
            # Gap Up策略是做空，平仓需要买入
            self._execute_exit(context, None, 0, Direction.LONG, OrderType.MARKET)
        else:
            # Gap Down策略是做多，平仓需要卖出
            self._execute_exit(context, None, 0, Direction.SHORT, OrderType.MARKET)
        
        self.write_log(f"Force market exit for {context.symbol} after timeout exit period")

    def _generate_trading_signal(self, bar, indicators):
        """生成交易信号 - 基于 Context 状态"""
        # 检查交易时间限制
        if not self._is_within_trading_time(bar.datetime):
            return
        
        # 获取 Context
        context = self.get_context(bar.symbol)
        
        # 检查交易次数限制 - 直接使用 Context 中的交易次数
        if context.trade_count >= self._get_daily_trades_for_gap(bar.symbol):
            return
        
        # 检查当前状态
        if context.state != StrategyState.IDLE:
            return
        
        # 检查 gap 条件
        gap_dir = self.gap_direction.get(bar.symbol, 'none')
        if gap_dir == 'none':
            return
        
        # 新增：timeout_trade_count 检查
        if context.timeout_trade_count > 0:
            # 计算当前entry价格
            entry_price = self._calculate_entry_price(context, bar, indicators)
            
            # 检查entry_price是否在当前bar的high和low范围内
            if not (bar.low_price <= entry_price <= bar.high_price):
                self.write_log(f"跳过entry信号: {context.symbol}, "
                              f"entry_price: {entry_price:.2f}, "
                              f"bar range: [{bar.low_price:.2f}, {bar.high_price:.2f}], "
                              f"timeout_trade_count: {context.timeout_trade_count}")
                return
        
        vwap = indicators['vwap']
        atr = indicators['atr_14']
        
        if gap_dir == 'up':
            # Gap Up策略：寻找VWAP failure做空机会
            below_vwap_count = indicators['below_vwap_count']
            
            if below_vwap_count >= self._get_failure_threshold(bar.symbol):
                # 计算目标价格
                target_price = self._calculate_entry_price(context, bar, indicators)
                
                # 新增：延迟执行逻辑
                if self.enable_delayed_entry:
                    # 检查价格距离
                    current_price = bar.close_price
                    if self._is_price_within_atr_range(current_price, target_price, atr, atr_multiplier=None):  # 使用策略参数
                        # 距离在ATR倍数以内，直接执行
                        self._execute_entry(context, bar, target_price, Direction.SHORT)
                    else:
                        # 距离超过ATR倍数，设置触发价格
                        self._set_trigger_prices(context, bar, indicators, target_price)
                        self.write_log(f"设置延迟执行: {context.symbol} 当前价格={current_price:.2f} "
                                      f"目标价格={target_price:.2f} ATR倍数={self.delayed_entry_atr_multiplier}")
                else:
                    # 原有逻辑：直接执行
                    self._execute_entry(context, bar, target_price, Direction.SHORT)
                
        elif gap_dir == 'down':
            # Gap Down策略：寻找VWAP failure做多机会
            above_vwap_count = indicators['above_vwap_count']
            
            if above_vwap_count >= self._get_failure_threshold(bar.symbol):
                # 计算目标价格
                target_price = self._calculate_entry_price(context, bar, indicators)
                
                # 新增：延迟执行逻辑
                if self.enable_delayed_entry:
                    # 检查价格距离
                    current_price = bar.close_price
                    if self._is_price_within_atr_range(current_price, target_price, atr, atr_multiplier=None):  # 使用策略参数
                        # 距离在ATR倍数以内，直接执行
                        self._execute_entry(context, bar, target_price, Direction.LONG)
                    else:
                        # 距离超过ATR倍数，设置触发价格
                        self._set_trigger_prices(context, bar, indicators, target_price)
                        self.write_log(f"设置延迟执行: {context.symbol} 当前价格={current_price:.2f} "
                                      f"目标价格={target_price:.2f} ATR倍数={self.delayed_entry_atr_multiplier}")
                else:
                    # 原有逻辑：直接执行
                    self._execute_entry(context, bar, target_price, Direction.LONG)
    
    def _is_within_trading_time(self, bar_datetime):
        """检查是否在允许交易的时间范围内"""
        current_time = bar_datetime.time()
        latest_time = datetime.strptime(self.latest_entry_time, "%H:%M:%S").time()
        return current_time <= latest_time
    
    def _is_within_morning_closing_time(self, bar_datetime):
        """检查是否在早盘收盘时间范围内"""
        current_time = bar_datetime.time()
        return current_time >= datetime.strptime(TypicalTimes.MORNING_CLOSING_START, "%H:%M:%S").time() and current_time <= datetime.strptime(TypicalTimes.MORNING_CLOSING, "%H:%M:%S").time()

    def _is_within_one_min_before_morning_closing_start(self, bar_datetime):
        """检查是否在早盘收盘前1分钟"""
        current_time = bar_datetime.time()
        return current_time >= datetime.strptime(TypicalTimes.ONE_MIN_BEFORE_MORNING_CLOSING_START, "%H:%M:%S").time() and current_time < datetime.strptime(TypicalTimes.MORNING_CLOSING, "%H:%M:%S").time()

    def _is_within_morning_trading_time(self, bar_datetime):
        """检查是否在早盘交易时间范围内"""
        current_time = bar_datetime.time()
        return current_time >= datetime.strptime(TypicalTimes.MORNING_START, "%H:%M:%S").time() and current_time < datetime.strptime(TypicalTimes.MORNING_CLOSING, "%H:%M:%S").time()

    def _is_within_afternoon_closing_time(self, bar_datetime):
        """检查是否在午后收盘时间范围内"""
        pass

    # ==================== 实现抽象方法 ====================
    
    def _calculate_entry_price(self, context, bar, indicators) -> float:
        """计算 entry 价格"""
        vwap = indicators['vwap']
        atr = indicators['atr_14']
        
        if self._is_gap_up(context.symbol):
            return next_tick_price(context.symbol, vwap + (atr * self._get_entry_factor(context.symbol)), upside=False)  # 做空
        else:
            return next_tick_price(context.symbol, vwap - (atr * self._get_entry_factor(context.symbol)), upside=True)  # 做多
    
    def _calculate_exit_price(self, context, bar, indicators) -> float:
        """计算 exit 价格"""
        if not indicators:
            # 如果没有技术指标，使用简单的固定比例
            if self._is_gap_up(context.symbol):
                # Gap Up 策略是做空，平仓需要买入
                return next_tick_price(context.symbol, context.entry_price - (self._get_exit_factor(context.symbol) * 0.01), upside=True)
            else:
                # Gap Down 策略是做多，平仓需要卖出
                return next_tick_price(context.symbol, context.entry_price + (self._get_exit_factor(context.symbol) * 0.01), upside=False)
        else:
            # 使用技术指标计算
            vwap = indicators['vwap']
            atr = indicators['atr_14']
            
            if self._is_gap_up(context.symbol):
                return next_tick_price(context.symbol, vwap - (atr * self._get_exit_factor(context.symbol)), upside=True)  # 做空平仓
            else:
                return next_tick_price(context.symbol, vwap + (atr * self._get_exit_factor(context.symbol)), upside=False)  # 做多平仓
    
    def _execute_entry_with_direction(self, context, bar, price):
        """根据策略逻辑执行 entry 订单"""
        if self._is_gap_up(context.symbol):
            self._execute_entry(context, bar, price, Direction.SHORT)
        else:
            self._execute_entry(context, bar, price, Direction.LONG)
    
    def _execute_exit_with_direction(self, context, bar, price):
        """根据策略逻辑执行 exit 订单"""
        if self._is_gap_up(context.symbol):
            # Gap Up 策略是做空，平仓需要买入
            self._execute_exit(context, bar, price, Direction.LONG)
        else:
            # Gap Down 策略是做多，平仓需要卖出
            self._execute_exit(context, bar, price, Direction.SHORT)

    def set_strategy_params(self, 
                          market_cap_threshold=100_000_000_000,
                          gap_up_threshold=0.02,
                          gap_down_threshold=-0.02,
                          failure_threshold_gap_up=3,
                          failure_threshold_gap_down=2,
                          entry_factor_gap_up=1.5,
                          entry_factor_gap_down=1.2,
                          max_daily_trades_gap_up=3,
                          max_daily_trades_gap_down=2,
                          latest_entry_time="14:30:00",
                          exit_factor_gap_up=1.0,
                          exit_factor_gap_down=0.8,
                          max_exit_wait_time_gap_up=30,
                          max_exit_wait_time_gap_down=20,
                          max_vol_ma5_ratio_threshold_gap_up=2.0,
                          max_vol_ma5_ratio_threshold_gap_down=1.5,
                          timeout_exit_max_period=5,
                          single_stock_max_position=1_000_000,
                          # 新增风险控制参数
                          exit_vol_ma5_ratio_threshold=5.0,
                          force_exit_atr_factor=3.0,
                          # 新增延迟执行参数
                          delayed_entry_atr_multiplier=2.0):
        """设置策略参数"""
        self.market_cap_threshold = market_cap_threshold
        self.gap_up_threshold = gap_up_threshold
        self.gap_down_threshold = gap_down_threshold
        self.failure_threshold_gap_up = failure_threshold_gap_up
        self.failure_threshold_gap_down = failure_threshold_gap_down
        self.entry_factor_gap_up = entry_factor_gap_up
        self.entry_factor_gap_down = entry_factor_gap_down
        self.max_daily_trades_gap_up = max_daily_trades_gap_up
        self.max_daily_trades_gap_down = max_daily_trades_gap_down
        self.latest_entry_time = latest_entry_time
        self.exit_factor_gap_up = exit_factor_gap_up
        self.exit_factor_gap_down = exit_factor_gap_down
        self.max_exit_wait_time_gap_up = max_exit_wait_time_gap_up
        self.max_exit_wait_time_gap_down = max_exit_wait_time_gap_down
        self.max_vol_ma5_ratio_threshold_gap_up = max_vol_ma5_ratio_threshold_gap_up
        self.max_vol_ma5_ratio_threshold_gap_down = max_vol_ma5_ratio_threshold_gap_down
        self.timeout_exit_max_period = timeout_exit_max_period
        self.single_stock_max_position = single_stock_max_position
        
        # 新增风险控制参数
        self.exit_vol_ma5_ratio_threshold = exit_vol_ma5_ratio_threshold
        self.force_exit_atr_factor = force_exit_atr_factor
        
        # 新增延迟执行参数
        self.delayed_entry_atr_multiplier = delayed_entry_atr_multiplier
        
        print(f"策略参数设置完成:")
        print(f"  市值阈值: {market_cap_threshold:,.0f} 日元")
        print(f"  Gap Up阈值: {gap_up_threshold:.1%}")
        print(f"  Gap Down阈值: {gap_down_threshold:.1%}")
        print(f"  Gap Up VWAP Failure阈值: {failure_threshold_gap_up}")
        print(f"  Gap Down VWAP Failure阈值: {failure_threshold_gap_down}")
        print(f"  Gap Up Entry ATR倍数: {entry_factor_gap_up}")
        print(f"  Gap Down Entry ATR倍数: {entry_factor_gap_down}")
        print(f"  Gap Up Exit ATR倍数: {exit_factor_gap_up}")
        print(f"  Gap Down Exit ATR倍数: {exit_factor_gap_down}")
        print(f"  Gap Up 单日最大交易次数: {max_daily_trades_gap_up}")
        print(f"  Gap Down 单日最大交易次数: {max_daily_trades_gap_down}")
        print(f"  最晚入场时间: {latest_entry_time}")
        print(f"  Gap Up 最大平仓等待时间: {max_exit_wait_time_gap_up} 分钟")
        print(f"  Gap Down 最大平仓等待时间: {max_exit_wait_time_gap_down} 分钟")
        print(f"  Gap Up 当前bar的vol/vol_ma5比例上限: {max_vol_ma5_ratio_threshold_gap_up}")
        print(f"  Gap Down 当前bar的vol/vol_ma5比例上限: {max_vol_ma5_ratio_threshold_gap_down}")
        print(f"  Timeout Exit最大等待时间: {timeout_exit_max_period} 分钟")
        print(f"  单只股票最大持仓量: {single_stock_max_position:,.0f} 日元")
    
    def print_strategy_status(self):
        """打印策略状态"""
        self.write_log(f"\n=== VWAP Failure 策略状态 ===")
        self.write_log(f"市值符合条件的股票数量: {len(self.market_cap_eligible)}")
        self.write_log(f"真正符合条件的股票数量: {len(self.eligible_stocks)}")
        self.write_log(f"信号计数: {self.signal_count}")
        self.write_log(f"当前交易日期: {self.trading_date}")
        
        # 显示 Context 状态
        context_summary = self.get_context_summary()
        self.write_log(f"\nContext 汇总:")
        self.write_log(f"  总 Context 数量: {context_summary['total_contexts']}")
        self.write_log(f"  符合条件的股票: {context_summary['eligible_stocks']}")
        self.write_log(f"  空闲状态: {context_summary['idle_count']}")
        self.write_log(f"  等待入场: {context_summary['waiting_entry_count']}")
        self.write_log(f"  持仓中: {context_summary['holding_count']}")
        self.write_log(f"  等待出场: {context_summary['waiting_exit_count']}")
        self.write_log(f"  等待timeout出场: {context_summary['waiting_timeout_exit_count']}")
        self.write_log(f"  总交易次数: {context_summary['total_trades']}")
        
        # 显示符合条件的股票详情
        if self.eligible_stocks:
            self.write_log(f"\n符合条件的股票详情:")
            for symbol in self.eligible_stocks:
                context = self.get_context(symbol)
                gap_dir = self.gap_direction.get(symbol, 'none')
                self.write_log(f"  {symbol}: {gap_dir} | {context.state.value} | "
                      f"交易次数: {context.trade_count}/{self._get_daily_trades_for_gap(symbol)}")
    
    def get_signals_summary(self) -> dict:
        """获取信号汇总信息"""
        return {
            'signal_count': self.signal_count,
            'gap_up_count': len([s for s in self.gap_direction.values() if s == 'up']),
            'gap_down_count': len([s for s in self.gap_direction.values() if s == 'down']),
            'none_count': len([s for s in self.gap_direction.values() if s == 'none'])
        }

    def print_context_status(self):
        """打印所有 Context 状态"""
        self.write_log(f"\n=== Context 状态监控 ===")
        for symbol, context in self.contexts.items():
            if symbol in self.eligible_stocks:
                self.write_log(f"{symbol}: {context.state.value} | "
                      f"交易次数: {context.trade_count}/{self._get_daily_trades_for_gap(symbol)} | "
                      f"Entry订单: {context.entry_order_id[:8] if context.entry_order_id else 'None'} | "
                      f"Exit订单: {context.exit_order_id[:8] if context.exit_order_id else 'None'}")

    def get_context_summary(self) -> dict:
        """获取 Context 汇总信息"""
        summary = {
            'total_contexts': len(self.contexts),
            'eligible_stocks': len(self.eligible_stocks),
            'idle_count': 0,
            'waiting_entry_count': 0,
            'holding_count': 0,
            'waiting_exit_count': 0,
            'waiting_timeout_exit_count': 0,
            'total_trades': 0
        }
        
        for context in self.contexts.values():
            summary[f'{context.state.value}_count'] += 1
            summary['total_trades'] += context.trade_count
        
        return summary


def main():
    """主函数 - 测试VWAP Failure策略"""
    print("启动VWAP Failure策略 ...")
    
    strategy = VWAPFailureStrategy(use_mock_gateway=False, enable_delayed_entry=True)
    
    try:
        # 设置策略参数
        strategy.set_strategy_params(
            market_cap_threshold=100_000_000_000,  # 1000亿日元
            latest_entry_time="11:23:00",  # 最晚入场时间
            timeout_exit_max_period=5, # 超时退出最大等待时间
            single_stock_max_position=1_000_000, # 单只股票最大持仓量
            delayed_entry_atr_multiplier=1.0,
            
            exit_vol_ma5_ratio_threshold=5.0,
            force_exit_atr_factor=10.0, # temperarily disable this by setting a very huge value, we don't see this to be really useful

            # disable it for now
            gap_up_threshold=0.5,      # 2% gap up 
            failure_threshold_gap_up=30,        # Gap Up时的VWAP failure次数阈值
            entry_factor_gap_up=1.5,           # Entry ATR倍数
            exit_factor_gap_up=1.0,            # Exit ATR倍数
            max_daily_trades_gap_up=3,         # 单日最大交易次数
            max_exit_wait_time_gap_up=30,     # 最大平仓等待时间（分钟）
            max_vol_ma5_ratio_threshold_gap_up=2.0, # Gap Up时的成交量MA5阈值
            
            gap_down_threshold=-0.02,   # -2% gap down
            failure_threshold_gap_down=35,      # Gap Down时的VWAP failure次数阈值
            entry_factor_gap_down=1.6,         # Entry ATR倍数
            exit_factor_gap_down=1.9,          # Exit ATR倍数
            max_daily_trades_gap_down=2,       # 单日最大交易次数
            max_exit_wait_time_gap_down=40,    # 最大平仓等待时间（分钟）
            max_vol_ma5_ratio_threshold_gap_down=3.0, # Gap Down时的成交量MA5阈值
        )
        
        # 配置Mock Gateway的replay模式
        # mock_setting = {
        #     "tick_mode": "replay",
        #     "replay_data_dir": "D:\\dev\\github\\brisk-hack\\brisk_in_day_frames",
        #     "replay_date": "20250718",  # 根据实际数据文件调整
        #     "replay_speed": 10.0,       # 10倍速回放
        #     "mock_account_balance": 10000000,
        # }
        
        # 连接Gateway
        # strategy.connect(mock_setting)
        
        strategy.connect()
        
        # 初始化股票筛选器
        strategy.initialize_stock_filter()
        
        # 等待一段时间接收数据
        print("等待接收数据...")
        time.sleep(5)
        
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
        # 打印策略状态
        strategy.print_strategy_status()
        print(strategy.get_signals_summary())
        strategy.close()


if __name__ == "__main__":
    main() 