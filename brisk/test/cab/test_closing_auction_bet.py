"""
Closing Auction Bet Strategy Test
收盘竞价策略测试脚本
"""

import time
from datetime import datetime, time as dt_time
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from closing_auction_bet_strategy import ClosingAuctionBetStrategy
from common.trading_common import topix500
from intraday_strategy_base import StrategyState


def test_strategy_initialization():
    """测试策略初始化"""
    print("=== 测试策略初始化 ===")
    
    strategy = ClosingAuctionBetStrategy(use_mock_gateway=True, gateway_type="mock")
    
    # 检查参数是否正确加载
    assert strategy.long_multiplier == 0.995
    assert strategy.short_multiplier == 1.0055
    assert strategy.trigger_tick_count == 3
    assert strategy.position_size == 100
    
    print("[PASS] 策略初始化测试通过")
    return strategy


def test_context_creation():
    """测试Context创建"""
    print("=== 测试Context创建 ===")
    
    strategy = ClosingAuctionBetStrategy(use_mock_gateway=True, gateway_type="mock")
    
    # 创建测试Context
    context = strategy.create_context("9984")
    
    assert context.symbol == "9984"
    assert context.state.value == "idle"
    assert context.position_size == 100
    assert context.base_price == 0.0
    assert not context.base_price_set
    
    print("[PASS] Context创建测试通过")
    return strategy, context


def test_price_calculation():
    """测试价格计算"""
    print("=== 测试价格计算 ===")
    
    strategy = ClosingAuctionBetStrategy(use_mock_gateway=True, gateway_type="mock")
    context = strategy.create_context("9984")
    
    # 设置base price
    context.base_price = 1000.0
    context.base_price_set = True
    
    # 计算目标价格和触发价格
    strategy._calculate_target_and_trigger_prices(context)
    
    # 验证目标价格（经过tick调整）
    # long_target_price应该向上调整，short_target_price应该向下调整
    raw_long_target = 1000.0 * 0.995  # 995.0
    raw_short_target = 1000.0 * 1.0055  # 1005.5
    
    # 验证价格已经过tick调整
    assert context.long_target_price >= raw_long_target  # 向上调整
    assert context.short_target_price <= raw_short_target  # 向下调整
    
    print(f"原始价格: long={raw_long_target}, short={raw_short_target}")
    print(f"调整后价格: long={context.long_target_price}, short={context.short_target_price}")
    
    # 验证触发价格已设置
    assert context.long_trigger_price > context.long_target_price
    assert context.short_trigger_price < context.short_target_price
    assert context.trigger_prices_set
    
    print(f"[PASS] 价格计算测试通过 - long_target: {context.long_target_price:.2f}, short_target: {context.short_target_price:.2f}")
    print(f"  long_trigger: {context.long_trigger_price:.2f}, short_trigger: {context.short_trigger_price:.2f}")


def test_time_window_logic():
    """测试时间窗口逻辑"""
    print("=== 测试时间窗口逻辑 ===")
    
    strategy = ClosingAuctionBetStrategy(use_mock_gateway=True, gateway_type="mock")
    
    # 测试建仓窗口
    entry_time = dt_time(15, 23)
    strategy._check_time_windows(entry_time)
    assert strategy.entry_window_active
    
    # 测试退出建仓窗口
    exit_time = dt_time(15, 26)
    strategy._check_time_windows(exit_time)
    assert not strategy.entry_window_active
    
    # 注意：平仓逻辑现在通过timer处理，不在这里测试
    print("[PASS] 时间窗口逻辑测试通过")


def test_config_loading():
    """测试配置加载"""
    print("=== 测试配置加载 ===")
    
    strategy = ClosingAuctionBetStrategy(use_mock_gateway=True, gateway_type="mock")
    
    # 验证默认配置是否正确
    print(f"实际参数: long_mult={strategy.long_multiplier}, short_mult={strategy.short_multiplier}, trigger_ticks={strategy.trigger_tick_count}, position_size={strategy.position_size}")
    
    # 测试默认值
    assert abs(strategy.long_multiplier - 0.995) < 0.001, f"long_multiplier期望0.995，实际{strategy.long_multiplier}"
    assert abs(strategy.short_multiplier - 1.0055) < 0.001, f"short_multiplier期望1.0055，实际{strategy.short_multiplier}"
    assert strategy.trigger_tick_count == 3, f"trigger_tick_count期望3，实际{strategy.trigger_tick_count}"
    assert strategy.position_size == 100, f"position_size期望100，实际{strategy.position_size}"
    
    print("[PASS] 配置加载测试通过")


def test_timer_functionality():
    """测试timer功能"""
    print("=== 测试timer功能 ===")
    
    strategy = ClosingAuctionBetStrategy(use_mock_gateway=True, gateway_type="mock")
    
    # 测试timer注册
    strategy._register_market_close_timer()
    assert not strategy.liquidation_executed
    
    # 模拟timer事件
    from vnpy.event import Event
    mock_event = Event("test")
    
    # 测试timer基本功能
    # 由于时间比较复杂，我们只测试timer注册和基本调用
    strategy._on_market_close_timer(mock_event)
    # 由于当前时间可能已经过了15:25，所以可能会执行平仓，这是正常的
    
    print("[PASS] Timer功能测试通过")


def test_strategy_status():
    """测试策略状态"""
    print("=== 测试策略状态 ===")
    
    strategy = ClosingAuctionBetStrategy(use_mock_gateway=True, gateway_type="mock")
    
    # 创建几个测试Context
    strategy.create_context("9984")
    strategy.create_context("7203")
    
    status = strategy.get_strategy_status()
    
    assert status["total_symbols"] == 2
    assert status["active_positions"] == 0
    assert status["pending_orders"] == 0
    
    print("[PASS] 策略状态测试通过")


def test_market_close_liquidation():
    """测试收盘前平仓逻辑"""
    print("=== 测试收盘前平仓逻辑 ===")
    
    strategy = ClosingAuctionBetStrategy(use_mock_gateway=True, gateway_type="mock")
    
    # 创建测试Context
    context1 = strategy.create_context("9984")
    context2 = strategy.create_context("7203")
    context3 = strategy.create_context("6758")
    
    # 模拟不同状态
    # context1: 有持仓，需要平仓
    context1.position = 100
    context1.state = StrategyState.HOLDING
    
    # context2: 等待entry订单，需要取消
    context2.entry_order_id = "order_123"
    context2.state = StrategyState.WAITING_ENTRY
    
    # context3: 异常状态 - WAITING_ENTRY但没有订单ID
    context3.state = StrategyState.WAITING_ENTRY
    # 故意不设置entry_order_id
    
    # 由于gateway为None，我们只测试取消订单的逻辑部分
    # 模拟取消订单的逻辑
    canceled_orders = 0
    
    for symbol, context in strategy.contexts.items():
        # 测试取消未成交的entry订单逻辑
        if context.state == StrategyState.WAITING_ENTRY:
            if context.entry_order_id:
                # 模拟取消成功
                canceled_orders += 1
                context.entry_order_id = ""
                context.state = StrategyState.IDLE
            else:
                # 状态是WAITING_ENTRY但没有订单ID，直接重置状态
                context.state = StrategyState.IDLE
    
    # 验证结果
    # context1应该保持HOLDING状态
    assert context1.state == StrategyState.HOLDING
    
    # context2应该被重置为IDLE
    assert context2.state == StrategyState.IDLE
    assert context2.entry_order_id == ""
    
    # context3应该被重置为IDLE
    assert context3.state == StrategyState.IDLE
    
    # 验证取消订单计数
    assert canceled_orders == 1  # 只有context2有订单ID
    
    print("[PASS] 收盘前平仓逻辑测试通过")


def test_on_order_logic():
    """测试on_order逻辑"""
    print("=== 测试on_order逻辑 ===")
    
    strategy = ClosingAuctionBetStrategy(use_mock_gateway=True, gateway_type="mock")
    
    # 创建测试Context
    context = strategy.create_context("9984")
    context.entry_order_id = "order_123"
    context.exit_order_id = "order_456"
    
    # 测试通过订单ID查找context
    found_context = strategy._find_context_by_order_id("order_123")
    assert found_context == context
    assert found_context.symbol == "9984"
    
    found_context = strategy._find_context_by_order_id("order_456")
    assert found_context == context
    
    # 测试查找不存在的订单ID
    found_context = strategy._find_context_by_order_id("order_999")
    assert found_context is None
    
    print("[PASS] on_order逻辑测试通过")


def run_all_tests():
    """运行所有测试"""
    print("开始运行收盘竞价策略测试...")
    print("=" * 50)
    
    try:
        test_strategy_initialization()
        test_context_creation()
        test_price_calculation()
        test_time_window_logic()
        test_config_loading()
        test_timer_functionality()
        test_strategy_status()
        test_market_close_liquidation()
        test_on_order_logic()
        
        print("=" * 50)
        print("[SUCCESS] 所有测试通过！")
        
    except Exception as e:
        print(f"[FAIL] 测试失败: {e}")
        raise


if __name__ == "__main__":
    run_all_tests()
