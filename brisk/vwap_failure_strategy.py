"""
VWAP Failure 日内交易策略
基于intraday_strategy_base实现，寻找gap up/down后的VWAP failure机会
"""

from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, Set

from vnpy.trader.constant import Direction, Offset, Status, OrderType, Exchange
from vnpy.trader.object import OrderData, OrderRequest, TradeData, CancelRequest

from intraday_strategy_base import IntradayStrategyBase, StrategyState
from stock_master import get_stockmaster
from mock_brisk_gateway import MockBriskGateway


class VWAPFailureStrategy(IntradayStrategyBase):
    """VWAP Failure 日内交易策略"""
    
    def __init__(self, use_mock_gateway=True):
        super().__init__(use_mock_gateway=use_mock_gateway)
        
        # 策略参数
        self.market_cap_threshold = 100_000_000_000  # 1000亿日元
        self.gap_up_threshold = 0.02    # 2% gap up
        self.gap_down_threshold = -0.02 # -2% gap down
        self.failure_threshold_gap_up = 3      # Gap Up时的VWAP failure次数阈值
        self.failure_threshold_gap_down = 2    # Gap Down时的VWAP failure次数阈值
        self.entry_factor = 1.5         # ATR倍数
        self.max_daily_trades = 3       # 单个股票单日最多执行策略次数
        self.latest_entry_time = "14:30:00"  # 最晚入场时间
        self.exit_factor = 1.0          # 平仓ATR倍数
        self.max_exit_wait_time = 30    # 最大平仓等待时间（分钟）
        
        # 股票状态管理
        self.stock_master = {}          # 股票基础信息
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
        print("初始化股票筛选器...")
        
        # 1. 获取股票基础信息
        self.stock_master = get_stockmaster()
        print(f"获取到 {len(self.stock_master)} 只股票的基础信息")
        
        # 2. 基于市值预筛选股票
        self._pre_filter_by_market_cap()
        
        # 3. 订阅市值符合条件的股票（用于获取第一个tick价格）
        if self.market_cap_eligible:
            self.subscribe(list(self.market_cap_eligible))
            print(f"订阅了 {len(self.market_cap_eligible)} 只市值符合条件的股票")
        else:
            print("没有找到市值符合条件的股票")
        
    def _pre_filter_by_market_cap(self):
        """基于市值预筛选股票"""
        for symbol, stock_info in self.stock_master.items():
            market_cap = stock_info.get('market_cap', 0)
            if market_cap >= self.market_cap_threshold:
                self.market_cap_eligible.add(symbol)
                # print(f"股票 {symbol} 通过市值筛选: {market_cap:,.0f} 日元")
        
        print(f"市值筛选后符合条件的股票数量: {len(self.market_cap_eligible)}")
    
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
            super().on_tick(event)
    
    def _check_new_trading_day(self, datetime_obj):
        """检查是否是新交易日，如果是则重置相关数据"""
        current_date = datetime_obj.date()
        
        if self.trading_date != current_date:
            print(f"新交易日开始: {current_date}")
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
            
            print("策略状态已重置")
    
    def _evaluate_gap_condition(self, symbol):
        """评估gap条件"""
        if symbol not in self.first_tick_prices:
            return
        
        first_price = self.first_tick_prices[symbol]
        prev_close = self.stock_master[symbol].get('basePrice10', 0) / 10
        
        
        if prev_close > 0:
            gap_ratio = (first_price - prev_close) / prev_close
            
            if gap_ratio >= self.gap_up_threshold:
                self.gap_direction[symbol] = 'up'
                self.eligible_stocks.add(symbol)
                print(f"股票 {symbol} 满足 Gap Up 条件: {gap_ratio:.2%}")
            elif gap_ratio <= self.gap_down_threshold:
                self.gap_direction[symbol] = 'down'
                self.eligible_stocks.add(symbol)
                print(f"股票 {symbol} 满足 Gap Down 条件: {gap_ratio:.2%}")
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
        # self.write_log(f"order: {order}")
        
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
            
            # 生成 exit 订单（统一在on_order中处理）
            self._generate_exit_order_from_order(context, order)

    def _handle_exit_order_update(self, order: OrderData, context):
        """处理 exit 订单状态更新"""
        print(f"exit order update: {order}")
        if order.status == Status.REJECTED:
            # exit 订单被拒绝，回到 HOLDING 状态
            self.update_context_state(context.symbol, StrategyState.HOLDING)
            context.exit_order_id = ""
            self.write_log(f"Exit order rejected for {context.symbol}")
            
        elif order.status == Status.ALLTRADED:
            # exit 订单完全成交，交易完成，增加交易次数
            context.trade_count += 1
            self.update_context_state(context.symbol, StrategyState.IDLE)
            context.exit_order_id = ""
            self.write_log(f"Trade completed for {context.symbol}, count: {context.trade_count}")

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
    
    def on_1min_bar(self, bar):
        """重写1分钟K线处理逻辑"""
        # 只处理真正符合条件的股票
        if bar.symbol not in self.eligible_stocks:
            return
            
        # 调用父类方法更新技术指标
        super().on_1min_bar(bar)
        
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
        if context.state == StrategyState.WAITING_ENTRY and context.entry_order_id:
            self._update_entry_order_price(context, bar, indicators)
        
        # 更新 exit 订单
        elif context.state == StrategyState.WAITING_EXIT and context.exit_order_id:
            # check timeout first 
            if not self._check_exit_timeout(context):
                self._update_exit_order_price(context, bar, indicators)

    def _check_exit_timeout(self, context):
        """检查 exit 订单是否超时"""
        if not context.exit_start_time or not context.exit_order_id:
            return False
        
        # 使用策略参数而不是 Context 中的固定值
        max_wait_time = timedelta(minutes=self.max_exit_wait_time)
        if (datetime.now() - context.exit_start_time) > max_wait_time:
            # 超时，撤单并以市价单平仓
            if self._cancel_order_safely(context.exit_order_id, context.symbol):
                # 根据 gap 方向使用对应的市价平仓方法
                if self._is_gap_up(context.symbol):
                    # Gap Up 策略是做空，平仓需要买入
                    self._execute_exit(context, None, 0, Direction.LONG, OrderType.MARKET)
                else:
                    # Gap Down 策略是做多，平仓需要卖出
                    self._execute_exit(context, None, 0, Direction.SHORT, OrderType.MARKET)
                
                self.write_log(f"Exit order timeout for {context.symbol}, switching to market order")
                return True
        return False

    def _generate_trading_signal(self, bar, indicators):
        """生成交易信号 - 基于 Context 状态"""
        # 检查交易时间限制
        if not self._is_within_trading_time(bar.datetime):
            return
        
        # 获取 Context
        context = self.get_context(bar.symbol)
        
        # 检查交易次数限制 - 直接使用 Context 中的交易次数
        if context.trade_count >= self.max_daily_trades:
            return
        
        # 检查当前状态
        if context.state != StrategyState.IDLE:
            return
        
        # 检查 gap 条件
        gap_dir = self.gap_direction.get(bar.symbol, 'none')
        if gap_dir == 'none':
            return
        
        vwap = indicators['vwap']
        atr = indicators['atr_14']
        
        if gap_dir == 'up':
            # Gap Up策略：寻找VWAP failure做空机会
            below_vwap_count = indicators['below_vwap_count']
            
            if below_vwap_count >= self._get_failure_threshold(bar.symbol):
                # 在VWAP + ATR * entry_factor位置做空
                short_price = vwap + (atr * self.entry_factor)
                self._execute_entry(context, bar, short_price, Direction.SHORT)
                
        elif gap_dir == 'down':
            # Gap Down策略：寻找VWAP failure做多机会
            above_vwap_count = indicators['above_vwap_count']
            
            if above_vwap_count >= self._get_failure_threshold(bar.symbol):
                # 在VWAP - ATR * entry_factor位置做多
                long_price = vwap - (atr * self.entry_factor)
                self._execute_entry(context, bar, long_price, Direction.LONG)
    
    def _is_within_trading_time(self, bar_datetime):
        """检查是否在允许交易的时间范围内"""
        current_time = bar_datetime.time()
        latest_time = datetime.strptime(self.latest_entry_time, "%H:%M:%S").time()
        return current_time <= latest_time
    
    # ==================== 实现抽象方法 ====================
    
    def _calculate_entry_price(self, context, bar, indicators) -> float:
        """计算 entry 价格"""
        vwap = indicators['vwap']
        atr = indicators['atr_14']
        
        if self._is_gap_up(context.symbol):
            return vwap + (atr * self.entry_factor)  # 做空
        else:
            return vwap - (atr * self.entry_factor)  # 做多
    
    def _calculate_exit_price(self, context, bar, indicators) -> float:
        """计算 exit 价格"""
        if not indicators:
            # 如果没有技术指标，使用简单的固定比例
            if self._is_gap_up(context.symbol):
                # Gap Up 策略是做空，平仓需要买入
                return context.entry_price - (self.exit_factor * 0.01)
            else:
                # Gap Down 策略是做多，平仓需要卖出
                return context.entry_price + (self.exit_factor * 0.01)
        else:
            # 使用技术指标计算
            vwap = indicators['vwap']
            atr = indicators['atr_14']
            
            if self._is_gap_up(context.symbol):
                return vwap - (atr * self.exit_factor)  # 做空平仓
            else:
                return vwap + (atr * self.exit_factor)  # 做多平仓
    
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
                          entry_factor=1.5,
                          max_daily_trades=3,
                          latest_entry_time="14:30:00",
                          exit_factor=1.0,
                          max_exit_wait_time=30):
        """设置策略参数"""
        self.market_cap_threshold = market_cap_threshold
        self.gap_up_threshold = gap_up_threshold
        self.gap_down_threshold = gap_down_threshold
        self.failure_threshold_gap_up = failure_threshold_gap_up
        self.failure_threshold_gap_down = failure_threshold_gap_down
        self.entry_factor = entry_factor
        self.max_daily_trades = max_daily_trades
        self.latest_entry_time = latest_entry_time
        self.exit_factor = exit_factor
        self.max_exit_wait_time = max_exit_wait_time
        
        print(f"策略参数设置完成:")
        print(f"  市值阈值: {market_cap_threshold:,.0f} 日元")
        print(f"  Gap Up阈值: {gap_up_threshold:.1%}")
        print(f"  Gap Down阈值: {gap_down_threshold:.1%}")
        print(f"  Gap Up VWAP Failure阈值: {failure_threshold_gap_up}")
        print(f"  Gap Down VWAP Failure阈值: {failure_threshold_gap_down}")
        print(f"  Entry ATR倍数: {entry_factor}")
        print(f"  Exit ATR倍数: {exit_factor}")
        print(f"  单日最大交易次数: {max_daily_trades}")
        print(f"  最晚入场时间: {latest_entry_time}")
        print(f"  最大平仓等待时间: {max_exit_wait_time} 分钟")
    
    def print_strategy_status(self):
        """打印策略状态"""
        print(f"\n=== VWAP Failure 策略状态 ===")
        print(f"市值符合条件的股票数量: {len(self.market_cap_eligible)}")
        print(f"真正符合条件的股票数量: {len(self.eligible_stocks)}")
        print(f"信号计数: {self.signal_count}")
        print(f"当前交易日期: {self.trading_date}")
        
        # 显示 Context 状态
        context_summary = self.get_context_summary()
        print(f"\nContext 汇总:")
        print(f"  总 Context 数量: {context_summary['total_contexts']}")
        print(f"  符合条件的股票: {context_summary['eligible_stocks']}")
        print(f"  空闲状态: {context_summary['idle_count']}")
        print(f"  等待入场: {context_summary['waiting_entry_count']}")
        print(f"  持仓中: {context_summary['holding_count']}")
        print(f"  等待出场: {context_summary['waiting_exit_count']}")
        print(f"  总交易次数: {context_summary['total_trades']}")
        
        # 显示符合条件的股票详情
        if self.eligible_stocks:
            print(f"\n符合条件的股票详情:")
            for symbol in self.eligible_stocks:
                context = self.get_context(symbol)
                gap_dir = self.gap_direction.get(symbol, 'none')
                print(f"  {symbol}: {gap_dir} | {context.state.value} | "
                      f"交易次数: {context.trade_count}/{self.max_daily_trades}")
    
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
        print(f"\n=== Context 状态监控 ===")
        for symbol, context in self.contexts.items():
            if symbol in self.eligible_stocks:
                print(f"{symbol}: {context.state.value} | "
                      f"交易次数: {context.trade_count}/{self.max_daily_trades} | "
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
            'total_trades': 0
        }
        
        for context in self.contexts.values():
            summary[f'{context.state.value}_count'] += 1
            summary['total_trades'] += context.trade_count
        
        return summary


def main():
    """主函数 - 测试VWAP Failure策略"""
    print("启动VWAP Failure策略 ...")
    
    # 创建策略实例（使用Mock Gateway）
    strategy = VWAPFailureStrategy(use_mock_gateway=False)
    
    try:
        # 设置策略参数
        strategy.set_strategy_params(
            market_cap_threshold=100_000_000_000,  # 1000亿日元
            gap_up_threshold=0.02,      # 2% gap up
            gap_down_threshold=-0.02,   # -2% gap down
            failure_threshold_gap_up=30,        # Gap Up时的VWAP failure次数阈值
            failure_threshold_gap_down=20,      # Gap Down时的VWAP failure次数阈值
            entry_factor=1.5,           # Entry ATR倍数
            max_daily_trades=3,         # 单日最大交易次数
            latest_entry_time="11:23:00",  # 最晚入场时间
            exit_factor=1.0,            # Exit ATR倍数
            max_exit_wait_time=30       # 最大平仓等待时间（分钟）
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
        import time
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