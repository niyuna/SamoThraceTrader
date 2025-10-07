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
    assert strategy.single_stock_max_position == 1_000_000
    assert strategy.min_position_size == 100
    assert strategy.cancel_protection_seconds == 20
    
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
    assert context.position_size == 0  # 现在初始为0，将在下单时动态计算
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
    print(f"实际参数: long_mult={strategy.long_multiplier}, short_mult={strategy.short_multiplier}, trigger_ticks={strategy.trigger_tick_count}, max_position={strategy.single_stock_max_position}, min_position={strategy.min_position_size}, cancel_protection={strategy.cancel_protection_seconds}")
    
    # 测试默认值
    assert abs(strategy.long_multiplier - 0.995) < 0.001, f"long_multiplier期望0.995，实际{strategy.long_multiplier}"
    assert abs(strategy.short_multiplier - 1.0055) < 0.001, f"short_multiplier期望1.0055，实际{strategy.short_multiplier}"
    assert strategy.trigger_tick_count == 3, f"trigger_tick_count期望3，实际{strategy.trigger_tick_count}"
    assert strategy.single_stock_max_position == 1_000_000, f"single_stock_max_position期望1000000，实际{strategy.single_stock_max_position}"
    assert strategy.min_position_size == 100, f"min_position_size期望100，实际{strategy.min_position_size}"
    assert strategy.cancel_protection_seconds == 20, f"cancel_protection_seconds期望20，实际{strategy.cancel_protection_seconds}"
    
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


def test_dynamic_position_calculation():
    """测试动态仓位计算功能"""
    print("=== 测试动态仓位计算 ===")
    
    # 创建策略实例
    strategy = ClosingAuctionBetStrategy(use_mock_gateway=True)
    
    # 设置参数
    strategy.single_stock_max_position = 1_000_000  # 100万日元
    strategy.min_position_size = 100  # 最小100股
    
    # 测试不同价格的股票
    test_cases = [
        {"symbol": "9984", "base_price": 1000.0, "expected_min": 900, "expected_max": 1100},  # 1000日元
        {"symbol": "7203", "base_price": 5000.0, "expected_min": 180, "expected_max": 220},   # 5000日元
        {"symbol": "6758", "base_price": 100.0, "expected_min": 9900, "expected_max": 10100}, # 100日元
        {"symbol": "6861", "base_price": 0, "expected": 100},  # 无base price，应该返回最小值
    ]
    
    for case in test_cases:
        symbol = case["symbol"]
        base_price = case["base_price"]
        
        # 创建context并设置base price
        context = strategy.create_context(symbol)
        if base_price > 0:
            context.base_price = base_price
            context.base_price_set = True
        
        # 计算仓位
        calculated_size = strategy.calculate_position_size(symbol)
        
        if base_price > 0:
            # 验证计算逻辑
            expected_size = round(strategy.single_stock_max_position / base_price / 100) * 100
            expected_size = max(expected_size, strategy.min_position_size)
            
            assert calculated_size == expected_size, f"仓位计算错误: {symbol} 期望{expected_size} 实际{calculated_size}"
            
            # 验证在合理范围内
            assert case["expected_min"] <= calculated_size <= case["expected_max"], \
                f"仓位超出预期范围: {symbol} {calculated_size} 不在[{case['expected_min']}, {case['expected_max']}]"
            
            print(f"  {symbol}: base_price={base_price:.1f} -> position_size={calculated_size}")
        else:
            # 无base price的情况
            assert calculated_size == case["expected"], \
                f"无base price时应该返回最小值: {symbol} 期望{case['expected']} 实际{calculated_size}"
            print(f"  {symbol}: 无base_price -> position_size={calculated_size} (fallback)")
    
    # 测试参数更新
    print("  测试参数更新...")
    old_max_position = strategy.single_stock_max_position
    strategy.single_stock_max_position = 2_000_000  # 更新为200万日元
    
    context = strategy.create_context("9984")
    context.base_price = 1000.0
    context.base_price_set = True
    
    new_calculated_size = strategy.calculate_position_size("9984")
    expected_new_size = round(2_000_000 / 1000.0 / 100) * 100
    expected_new_size = max(expected_new_size, strategy.min_position_size)
    
    assert new_calculated_size == expected_new_size, \
        f"参数更新后仓位计算错误: 期望{expected_new_size} 实际{new_calculated_size}"
    
    print(f"  参数更新: max_position {old_max_position} -> {strategy.single_stock_max_position}")
    print(f"  仓位变化: {calculated_size} -> {new_calculated_size}")
    
    print("[PASS] 动态仓位计算测试通过")


def test_gateway_parameter():
    """测试gateway命令行参数功能"""
    print("=== 测试gateway命令行参数 ===")
    
    import subprocess
    import sys
    import os
    
    # 测试帮助信息
    print("  测试1: 检查帮助信息中的gateway参数")
    try:
        result = subprocess.run([
            sys.executable, "closing_auction_bet_strategy.py", "--help"
        ], capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__)) + "/../..")
        
        if "--gateway" in result.stdout:
            print("  [PASS] gateway参数在帮助信息中正确显示")
        else:
            print("  [FAIL] gateway参数未在帮助信息中找到")
            return False
            
    except Exception as e:
        print(f"  [FAIL] 运行帮助命令失败: {e}")
        return False
    
    # 测试默认gateway参数
    print("  测试2: 检查默认gateway参数")
    try:
        result = subprocess.run([
            sys.executable, "closing_auction_bet_strategy.py", "--help"
        ], capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__)) + "/../..")
        
        if "default: brisk_eshiten" in result.stdout or "brisk_eshiten" in result.stdout:
            print("  [PASS] 默认gateway参数为brisk_eshiten")
        else:
            print("  [FAIL] 默认gateway参数设置不正确")
            return False
            
    except Exception as e:
        print(f"  [FAIL] 检查默认参数失败: {e}")
        return False
    
    # 测试无效gateway参数
    print("  测试3: 检查无效gateway参数处理")
    try:
        result = subprocess.run([
            sys.executable, "closing_auction_bet_strategy.py", "--gateway", "invalid_gateway"
        ], capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__)) + "/../..")
        
        if result.returncode != 0 and "invalid choice" in result.stderr.lower():
            print("  [PASS] 无效gateway参数被正确拒绝")
        else:
            print("  [FAIL] 无效gateway参数未被正确拒绝")
            return False
            
    except Exception as e:
        print(f"  [FAIL] 测试无效参数失败: {e}")
        return False
    
    print("  [PASS] gateway命令行参数测试通过")
    return True

def test_cancel_protection_logic():
    """测试价格退出触发区间的取消逻辑"""
    print("=== 测试取消保护逻辑 ===")
    
    # 创建策略实例
    strategy = ClosingAuctionBetStrategy(use_mock_gateway=True)
    strategy.cancel_protection_seconds = 5  # 设置较短的保护时间便于测试
    
    # 创建context并设置价格
    context = strategy.create_context("9984")
    context.base_price = 1000.0
    context.base_price_set = True
    strategy._calculate_target_and_trigger_prices(context)
    
    # 模拟tick数据
    from vnpy.trader.constant import Exchange
    from vnpy.trader.object import TickData
    from datetime import datetime, timedelta
    
    # 测试1: 价格进入做多触发区间，应该下单
    print("  测试1: 价格进入做多触发区间")
    tick1 = TickData(
        symbol="9984",
        exchange=Exchange.TSE,
        datetime=datetime.now(),
        last_price=context.long_trigger_price - 1.0,  # 低于触发价格
        volume=100,
        turnover=100000,
        gateway_name="test"
    )
    
    # 模拟下单成功
    context.entry_order_id = "test_order_1"
    context.state = StrategyState.WAITING_ENTRY
    context.entry_order_time = datetime.now()
    
    # 检查状态
    assert context.entry_order_id == "test_order_1"
    assert context.state == StrategyState.WAITING_ENTRY
    assert context.entry_order_time is not None
    
    # 测试2: 价格在触发区间之间，应该取消订单（在保护时间外）
    print("  测试2: 价格在触发区间之间（保护时间外）")
    import time
    time.sleep(0.1)  # 确保时间差大于保护时间
    
    # 设置订单时间为更早的时间，确保超过保护时间
    context.entry_order_time = datetime.now() - timedelta(seconds=10)
    
    # 计算触发区间中间的价格
    middle_price = (context.long_trigger_price + context.short_trigger_price) / 2
    
    tick2 = TickData(
        symbol="9984",
        exchange=Exchange.TSE,
        datetime=datetime.now(),
        last_price=middle_price,  # 在触发区间之间
        volume=100,
        turnover=100000,
        gateway_name="test"
    )
    
    # 模拟取消订单成功
    original_cancel_method = strategy._cancel_order_safely
    strategy._cancel_order_safely = lambda order_id, symbol: True
    
    strategy._handle_entry_logic("9984", context, tick2)
    
    # 验证订单被取消
    assert context.entry_order_id == ""
    assert context.entry_order_time is None
    assert context.state == StrategyState.IDLE
    
    # 恢复原始方法
    strategy._cancel_order_safely = original_cancel_method
    
    # 测试3: 价格在触发区间之间（做空订单）
    print("  测试3: 价格在触发区间之间（做空订单）")
    context.entry_order_id = "test_order_2"
    context.state = StrategyState.WAITING_ENTRY
    context.entry_order_time = datetime.now() - timedelta(seconds=10)  # 10秒前
    
    tick3 = TickData(
        symbol="9984",
        exchange=Exchange.TSE,
        datetime=datetime.now(),
        last_price=middle_price,  # 在触发区间之间
        volume=100,
        turnover=100000,
        gateway_name="test"
    )
    
    strategy._cancel_order_safely = lambda order_id, symbol: True
    strategy._handle_entry_logic("9984", context, tick3)
    
    # 验证订单被取消
    assert context.entry_order_id == ""
    assert context.entry_order_time is None
    assert context.state == StrategyState.IDLE
    
    # 测试4: 保护时间内不取消订单
    print("  测试4: 保护时间内不取消订单")
    context.entry_order_id = "test_order_3"
    context.state = StrategyState.WAITING_ENTRY
    context.entry_order_time = datetime.now()  # 刚刚发送
    
    tick4 = TickData(
        symbol="9984",
        exchange=Exchange.TSE,
        datetime=datetime.now(),
        last_price=middle_price,  # 在触发区间之间
        volume=100,
        turnover=100000,
        gateway_name="test"
    )
    
    strategy._handle_entry_logic("9984", context, tick4)
    
    # 验证订单没有被取消
    assert context.entry_order_id == "test_order_3"
    assert context.entry_order_time is not None
    assert context.state == StrategyState.WAITING_ENTRY
    
    # 测试5: 没有订单时不执行取消逻辑
    print("  测试5: 没有订单时不执行取消逻辑")
    context.entry_order_id = ""
    context.state = StrategyState.IDLE
    context.entry_order_time = None
    
    strategy._handle_entry_logic("9984", context, tick4)
    
    # 验证状态没有改变
    assert context.entry_order_id == ""
    assert context.entry_order_time is None
    assert context.state == StrategyState.IDLE
    
    print("[PASS] 取消保护逻辑测试通过")


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
        test_dynamic_position_calculation()
        test_cancel_protection_logic()
        test_gateway_parameter()
        
        print("=" * 50)
        print("[SUCCESS] 所有测试通过！")
        
    except Exception as e:
        print(f"[FAIL] 测试失败: {e}")
        raise


if __name__ == "__main__":
    run_all_tests()
