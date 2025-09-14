"""
调试entry逻辑
"""

import sys
import os
from datetime import datetime, timedelta

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from hft_bb_reversal_strategy import HFTBBReversalStrategy, TriggerLevels
from vnpy.trader.object import TickData
from vnpy.trader.constant import Exchange, Direction
from intraday_strategy_base import StrategyState
from unittest.mock import Mock

# 创建策略
strategy = HFTBBReversalStrategy()
symbol = "9984"

# 创建HFT context
strategy.create_hft_context(symbol)
context = strategy.get_hft_context(symbol)

# 设置trigger levels
context.trigger_levels = TriggerLevels(
    upper_trigger=100.5,
    upper_limit=100.0,
    lower_trigger=99.5,
    lower_limit=99.0
)

# 设置entry价格
context.entry_price = 98.5  # 当前订单价格（与新的order_price不同）
context.entry_order_id = "test_entry_123"
context.entry_order_time = datetime.now() - timedelta(minutes=2)  # 2分钟前
context.state = StrategyState.WAITING_ENTRY

# Mock gateway
strategy.gateway = Mock()
strategy.gateway.send_order = Mock(return_value="new_order_456")
strategy._cancel_order_with_verification = Mock(return_value=True)
strategy.write_log = Mock()

# 模拟价格变化
tick = TickData(
    symbol=symbol,
    exchange=Exchange.TSE,
    datetime=datetime.now(),
    name="Test Stock",
    volume=1000,
    turnover=100000,
    last_price=99.4,  # 价格在lower_trigger以下，应该触发LONG
    last_volume=100,
    limit_up=105.0,
    limit_down=95.0,
    open_price=99.0,
    high_price=99.5,
    low_price=98.8,
    pre_close=99.0,
    gateway_name="TEST"
)

print("Before _check_entry_logic:")
print(f"  current_price: {tick.last_price}")
print(f"  lower_trigger: {context.trigger_levels.lower_trigger}")
print(f"  upper_trigger: {context.trigger_levels.upper_trigger}")
print(f"  entry_price: {context.entry_price}")
print(f"  entry_order_id: {context.entry_order_id}")
print(f"  lower_trigger check: {tick.last_price <= context.trigger_levels.lower_trigger}")

# 调用_check_entry_logic
strategy._check_entry_logic(symbol, tick, context)

print("\nAfter _check_entry_logic:")
print(f"  Log calls: {[call[0][0] for call in strategy.write_log.call_args_list]}")
print(f"  Cancel calls: {strategy._cancel_order_with_verification.call_args_list}")
print(f"  Send order calls: {strategy.gateway.send_order.call_args_list}")

# 手动检查逻辑
print("\nManual logic check:")
print(f"  current_price <= lower_trigger: {tick.last_price <= context.trigger_levels.lower_trigger}")
print(f"  order_price should be: {context.trigger_levels.lower_limit}")
print(f"  entry_price != order_price: {context.entry_price != context.trigger_levels.lower_limit}")
print(f"  order_price > 0: {context.trigger_levels.lower_limit > 0}")
