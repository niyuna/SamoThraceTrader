"""
VWAP Failure 日内交易策略
基于intraday_strategy_base实现，寻找gap up/down后的VWAP failure机会
"""

from datetime import datetime
from collections import defaultdict
from typing import Dict, Set

from vnpy.trader.constant import Direction, Offset, Status, OrderType
from vnpy.trader.object import OrderData, OrderRequest

from intraday_strategy_base import IntradayStrategyBase
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
        self.failure_threshold = 3      # VWAP failure次数阈值
        self.entry_factor = 1.5         # ATR倍数
        self.max_daily_trades = 3       # 单个股票单日最多执行策略次数
        self.latest_entry_time = "14:30:00"  # 最晚入场时间
        
        # 股票状态管理
        self.stock_master = {}          # 股票基础信息
        self.market_cap_eligible = set()  # 仅满足市值条件的股票
        self.eligible_stocks = set()    # 真正满足所有条件的股票
        self.first_tick_prices = {}     # 记录每个股票当天第一个tick价格
        self.gap_direction = {}         # 记录gap方向：'up', 'down', 'none'
        self.daily_trade_counts = defaultdict(int)  # 记录每个股票当日交易次数
        self.trading_date = None        # 当前交易日期
        
        # 信号统计
        self.signal_count = 0           # 信号计数
        self.signals = []               # 信号记录
        
        # 订单状态管理 - 使用vnpy的OrderData
        self.entry_orders = {}          # 每个股票的entry订单: symbol -> OrderData
        self.exit_orders = {}           # 每个股票的exit订单: symbol -> OrderData
        
        # 订单相关参数
        self.exit_factor = 1.0          # 平仓ATR倍数
        self.max_exit_wait_time = 30    # 最大平仓等待时间（分钟）
        
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
                print(f"股票 {symbol} 通过市值筛选: {market_cap:,.0f} 日元")
        
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
            
            # 重置所有状态
            self.daily_trade_counts.clear()
            self.first_tick_prices.clear()
            self.gap_direction.clear()
            self.eligible_stocks.clear()  # 重置符合条件的股票列表
            
            # 重置订单状态
            self.entry_orders.clear()
            self.exit_orders.clear()
            
            print("策略状态已重置")
    
    def _evaluate_gap_condition(self, symbol):
        """评估股票是否满足gap条件"""
        if symbol not in self.stock_master:
            return
            
        stock_info = self.stock_master[symbol]
        first_tick_price = self.first_tick_prices[symbol]
        base_price = stock_info.get('basePrice10', 0) / 10  # 昨日收盘价
        
        if base_price <= 0:
            print(f"股票 {symbol} 昨日收盘价无效: {base_price}")
            return
        
        # 计算gap程度
        gap_ratio = (first_tick_price - base_price) / base_price
        
        # 检查gap条件
        if gap_ratio >= self.gap_up_threshold:
            self.eligible_stocks.add(symbol)
            self.gap_direction[symbol] = 'up'
            print(f"股票 {symbol} 满足所有条件: Gap Up {gap_ratio:.2%} "
                  f"(开盘: {first_tick_price:.2f}, 昨收: {base_price:.2f})")
        elif gap_ratio <= self.gap_down_threshold:
            self.eligible_stocks.add(symbol)
            self.gap_direction[symbol] = 'down'
            print(f"股票 {symbol} 满足所有条件: Gap Down {gap_ratio:.2%} "
                  f"(开盘: {first_tick_price:.2f}, 昨收: {base_price:.2f})")
        else:
            print(f"股票 {symbol} 不满足gap条件: Gap {gap_ratio:.2%} "
                  f"(开盘: {first_tick_price:.2f}, 昨收: {base_price:.2f})")
    
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
        
        # 更新等待中的订单价格
        self._update_pending_orders(bar, indicators)
        
        # 生成交易信号（只有在没有活跃订单时才生成）
        self._generate_trading_signal(bar, indicators)
    
    def _generate_trading_signal(self, bar, indicators):
        """生成交易信号"""
        # 检查交易时间限制
        if not self._is_within_trading_time(bar.datetime):
            return
            
        # 检查当日交易次数限制
        if self.daily_trade_counts[bar.symbol] >= self.max_daily_trades:
            return
            
        # 检查当前是否有活跃的entry订单 - 使用vnpy的is_active()方法
        if bar.symbol in self.entry_orders and self.entry_orders[bar.symbol].is_active():
            return
            
        gap_dir = self.gap_direction.get(bar.symbol, 'none')
        if gap_dir == 'none':
            return
            
        vwap = indicators['vwap']
        atr = indicators['atr_14']
        
        if gap_dir == 'up':
            # Gap Up策略：寻找VWAP failure做空机会
            below_vwap_count = indicators['below_vwap_count']
            
            if below_vwap_count >= self.failure_threshold:
                # 在VWAP + ATR * entry_factor位置做空
                short_price = vwap + (atr * self.entry_factor)
                
                # 执行做空开仓
                self._execute_short_entry(bar, short_price, atr, vwap, below_vwap_count)
                
        elif gap_dir == 'down':
            # Gap Down策略：寻找VWAP failure做多机会
            above_vwap_count = indicators['above_vwap_count']
            
            if above_vwap_count >= self.failure_threshold:
                # 在VWAP - ATR * entry_factor位置做多
                long_price = vwap - (atr * self.entry_factor)
                
                # 执行做多开仓
                self._execute_long_entry(bar, long_price, atr, vwap, above_vwap_count)
    
    def _is_within_trading_time(self, bar_datetime):
        """检查是否在允许交易的时间范围内"""
        current_time = bar_datetime.time()
        latest_time = datetime.strptime(self.latest_entry_time, "%H:%M:%S").time()
        return current_time <= latest_time
    
    def set_strategy_params(self, 
                          market_cap_threshold=100_000_000_000,
                          gap_up_threshold=0.02,
                          gap_down_threshold=-0.02,
                          failure_threshold=3,
                          entry_factor=1.5,
                          max_daily_trades=3,
                          latest_entry_time="14:30:00"):
        """设置策略参数"""
        self.market_cap_threshold = market_cap_threshold
        self.gap_up_threshold = gap_up_threshold
        self.gap_down_threshold = gap_down_threshold
        self.failure_threshold = failure_threshold
        self.entry_factor = entry_factor
        self.max_daily_trades = max_daily_trades
        self.latest_entry_time = latest_entry_time
        
        print(f"策略参数设置完成:")
        print(f"  市值阈值: {market_cap_threshold:,.0f} 日元")
        print(f"  Gap Up阈值: {gap_up_threshold:.1%}")
        print(f"  Gap Down阈值: {gap_down_threshold:.1%}")
        print(f"  VWAP Failure阈值: {failure_threshold}")
        print(f"  ATR倍数: {entry_factor}")
        print(f"  单日最大交易次数: {max_daily_trades}")
        print(f"  最晚入场时间: {latest_entry_time}")
    
    def print_strategy_status(self):
        """打印策略状态"""
        print(f"\n=== VWAP Failure 策略状态 ===")
        print(f"市值符合条件的股票数量: {len(self.market_cap_eligible)}")
        print(f"真正符合条件的股票数量: {len(self.eligible_stocks)}")
        print(f"Gap Up股票: {[s for s, d in self.gap_direction.items() if d == 'up']}")
        print(f"Gap Down股票: {[s for s, d in self.gap_direction.items() if d == 'down']}")
        print(f"当日交易次数: {dict(self.daily_trade_counts)}")
        print(f"总信号数量: {self.signal_count}")
        
        if self.signals:
            print(f"\n最近5个信号:")
            for signal in self.signals[-5:]:
                print(f"  {signal['datetime'].strftime('%H:%M:%S')} "
                      f"{signal['symbol']} {signal['direction']} "
                      f"价格: {signal['price']:.2f}")
    
    def get_signals_summary(self):
        """获取信号摘要"""
        if not self.signals:
            return "没有生成任何信号"
        
        summary = f"\n=== 信号摘要 ==="
        summary += f"\n总信号数量: {len(self.signals)}"
        
        # 按方向统计
        long_signals = [s for s in self.signals if s['direction'] == 'long']
        short_signals = [s for s in self.signals if s['direction'] == 'short']
        summary += f"\n做多信号: {len(long_signals)}"
        summary += f"\n做空信号: {len(short_signals)}"
        
        # 按股票统计
        symbol_counts = defaultdict(int)
        for signal in self.signals:
            symbol_counts[signal['symbol']] += 1
        
        summary += f"\n按股票统计:"
        for symbol, count in sorted(symbol_counts.items()):
            summary += f"\n  {symbol}: {count} 个信号"
        
        return summary

    def _execute_short_entry(self, bar, price, atr, vwap, failure_count):
        """执行做空开仓"""
        print(f"执行做空开仓: {bar.symbol} 价格: {price:.2f} VWAP: {vwap:.2f} "
              f"ATR: {atr:.2f} Failure次数: {failure_count} "
              f"时间: {bar.datetime.strftime('%H:%M:%S')}")
        
        # 创建OrderRequest - 使用vnpy的抽象
        order_req = OrderRequest(
            symbol=bar.symbol,
            exchange=bar.exchange,
            direction=Direction.SHORT,      # 使用vnpy的Direction
            type=OrderType.LIMIT,           # 使用vnpy的OrderType
            volume=100,                     # 固定数量，后续可参数化
            price=price,
            offset=Offset.OPEN,             # 使用vnpy的Offset
            reference=f"entry_short_{bar.symbol}_{bar.datetime.strftime('%H%M%S')}"
        )
        
        # 执行下单（使用Mock Gateway）
        order_id = self.gateway.send_order(order_req)
        
        if order_id:
            print(f"做空开仓订单已提交: {bar.symbol} 订单ID: {order_id}")
            
            # 使用vnpy的create_order_data方法创建OrderData
            order_data = order_req.create_order_data(order_id, self.gateway_name)
            self.entry_orders[bar.symbol] = order_data
        else:
            # 订单被拒绝
            self._handle_entry_rejection(bar.symbol, order_req)

    def _execute_long_entry(self, bar, price, atr, vwap, failure_count):
        """执行做多开仓"""
        print(f"执行做多开仓: {bar.symbol} 价格: {price:.2f} VWAP: {vwap:.2f} "
              f"ATR: {atr:.2f} Failure次数: {failure_count} "
              f"时间: {bar.datetime.strftime('%H:%M:%S')}")
        
        # 创建OrderRequest - 使用vnpy的抽象
        order_req = OrderRequest(
            symbol=bar.symbol,
            exchange=bar.exchange,
            direction=Direction.LONG,       # 使用vnpy的Direction
            type=OrderType.LIMIT,           # 使用vnpy的OrderType
            volume=100,                     # 固定数量，后续可参数化
            price=price,
            offset=Offset.OPEN,             # 使用vnpy的Offset
            reference=f"entry_long_{bar.symbol}_{bar.datetime.strftime('%H%M%S')}"
        )
        
        # 执行下单（使用Mock Gateway）
        order_id = self.gateway.send_order(order_req)
        
        if order_id:
            print(f"做多开仓订单已提交: {bar.symbol} 订单ID: {order_id}")
            
            # 使用vnpy的create_order_data方法创建OrderData
            order_data = order_req.create_order_data(order_id, self.gateway_name)
            self.entry_orders[bar.symbol] = order_data
        else:
            # 订单被拒绝
            self._handle_entry_rejection(bar.symbol, order_req)

    def _handle_entry_rejection(self, symbol, order_req):
        """处理开仓订单被拒绝"""
        print(f"开仓订单被拒绝: {symbol} 订单ID: {order_req.reference}")
        
        # 创建被拒绝的OrderData
        rejected_order = order_req.create_order_data(
            orderid=order_req.reference,
            gateway_name=self.gateway_name
        )
        rejected_order.status = Status.REJECTED  # 使用vnpy的Status
        
        # 保存订单记录（用于日志）
        self.entry_orders[symbol] = rejected_order
        
        print(f"股票 {symbol} 订单被拒绝，可以重新寻找entry信号")

    def _update_pending_orders(self, bar, indicators):
        """更新等待中的订单价格"""
        symbol = bar.symbol
        
        # 更新entry订单价格
        if symbol in self.entry_orders:
            entry_order = self.entry_orders[symbol]
            if entry_order.is_active():  # 使用vnpy的is_active()方法
                self._update_entry_order_price(entry_order, bar, indicators)
        
        # 更新exit订单价格（步骤2中实现）
        if symbol in self.exit_orders:
            exit_order = self.exit_orders[symbol]
            if exit_order.is_active():  # 使用vnpy的is_active()方法
                self._update_exit_order_price(exit_order, bar, indicators)

    def _update_entry_order_price(self, entry_order, bar, indicators):
        """更新entry订单价格"""
        vwap = indicators['vwap']
        atr = indicators['atr_14']
        
        # 计算新的entry价格
        if entry_order.direction == Direction.SHORT:  # 使用vnpy的Direction
            new_price = vwap + (atr * self.entry_factor)
        else:  # Direction.LONG
            new_price = vwap - (atr * self.entry_factor)
        
        # 更新订单价格
        old_price = entry_order.price
        entry_order.price = new_price
        
        print(f"更新entry订单价格: {bar.symbol} {entry_order.direction.value} "
              f"旧价格: {old_price:.2f} -> 新价格: {new_price:.2f} "
              f"时间: {bar.datetime.strftime('%H:%M:%S')}")
        
        # 执行订单更新（使用Mock Gateway）
        # 注意：Mock Gateway会自动处理订单更新，这里只需要记录日志
        print(f"订单价格已更新: {entry_order.vt_orderid}")

    def _update_exit_order_price(self, exit_order, bar, indicators):
        """更新exit订单价格（步骤2中实现）"""
        # TODO: 实现exit订单价格更新逻辑
        pass


def main():
    """主函数 - 测试VWAP Failure策略"""
    print("启动VWAP Failure策略 (Mock Gateway Replay模式)...")
    
    # 创建策略实例（使用Mock Gateway）
    strategy = VWAPFailureStrategy(use_mock_gateway=False)
    
    try:
        # 设置策略参数
        strategy.set_strategy_params(
            market_cap_threshold=100_000_000_000,  # 1000亿日元
            gap_up_threshold=0.02,      # 2% gap up
            gap_down_threshold=-0.02,   # -2% gap down
            failure_threshold=3,        # VWAP failure次数阈值
            entry_factor=1.5,           # ATR倍数
            max_daily_trades=3,         # 单日最大交易次数
            latest_entry_time="14:30:00"  # 最晚入场时间
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