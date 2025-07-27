"""
测试timeout exit优化功能
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta
from vnpy.trader.constant import Direction, OrderType, Status
from vnpy.trader.object import OrderData

from vwap_failure_strategy import VWAPFailureStrategy
from intraday_strategy_base import StrategyState


def test_timeout_exit_optimization():
    """测试timeout exit优化功能"""
    print("=== 测试timeout exit优化功能 ===")
    
    # 创建策略实例
    strategy = VWAPFailureStrategy(use_mock_gateway=True)
    
    # 设置策略参数
    strategy.set_strategy_params(
        timeout_exit_max_period=5  # 5分钟timeout exit等待时间
    )
    
    # 创建测试context
    context = strategy.get_context("TEST_SYMBOL")
    context.state = StrategyState.WAITING_EXIT
    context.exit_order_id = "test_exit_order"
    context.exit_start_time = datetime.now() - timedelta(minutes=31)  # 模拟超时
    
    print(f"初始状态: {context.state.value}")
    print(f"Exit订单ID: {context.exit_order_id}")
    print(f"Exit开始时间: {context.exit_start_time}")
    
    # 测试_check_exit_timeout方法
    print("\n--- 测试第一阶段timeout ---")
    result = strategy._check_exit_timeout(context)
    print(f"Timeout检查结果: {result}")
    print(f"当前状态: {context.state.value}")
    print(f"Timeout exit开始时间: {context.timeout_exit_start_time}")
    
    # 模拟timeout exit limit order超时
    print("\n--- 测试第二阶段timeout ---")
    context.timeout_exit_start_time = datetime.now() - timedelta(minutes=6)  # 模拟timeout exit超时
    result = strategy._check_exit_timeout(context)
    print(f"Timeout检查结果: {result}")
    print(f"当前状态: {context.state.value}")
    
    print("\n=== 测试完成 ===")


def test_strategy_state_enum():
    """测试策略状态枚举"""
    print("=== 测试策略状态枚举 ===")
    
    # 检查新状态是否存在
    print(f"WAITING_TIMEOUT_EXIT状态: {StrategyState.WAITING_TIMEOUT_EXIT}")
    print(f"WAITING_TIMEOUT_EXIT值: {StrategyState.WAITING_TIMEOUT_EXIT.value}")
    
    # 检查所有状态
    print("\n所有策略状态:")
    for state in StrategyState:
        print(f"  {state.name}: {state.value}")
    
    print("=== 状态枚举测试完成 ===")


def test_context_fields():
    """测试Context字段"""
    print("=== 测试Context字段 ===")
    
    strategy = VWAPFailureStrategy(use_mock_gateway=True)
    context = strategy.get_context("TEST_SYMBOL")
    
    print(f"Context字段:")
    print(f"  symbol: {context.symbol}")
    print(f"  state: {context.state}")
    print(f"  timeout_exit_start_time: {context.timeout_exit_start_time}")
    
    # 测试reset功能
    print("\n测试reset功能:")
    context.timeout_exit_start_time = datetime.now()
    print(f"设置timeout_exit_start_time后: {context.timeout_exit_start_time}")
    
    strategy.reset_all_contexts()
    print(f"Reset后timeout_exit_start_time: {context.timeout_exit_start_time}")
    
    print("=== Context字段测试完成 ===")


if __name__ == "__main__":
    test_strategy_state_enum()
    print()
    test_context_fields()
    print()
    test_timeout_exit_optimization() 