"""
Closing Auction Bet Strategy Demo
收盘竞价策略演示脚本
"""

import time
from datetime import datetime, time as dt_time
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from closing_auction_bet_strategy import ClosingAuctionBetStrategy
from common.trading_common import topix500


def demo_strategy_parameters():
    """演示策略参数"""
    print("=== 收盘竞价策略参数演示 ===")
    
    strategy = ClosingAuctionBetStrategy(use_mock_gateway=True, gateway_type="mock")
    
    print(f"策略名称: ClosingAuctionBetStrategy")
    print(f"做多倍数: {strategy.long_multiplier}")
    print(f"做空倍数: {strategy.short_multiplier}")
    print(f"触发tick数量: {strategy.trigger_tick_count}")
    print(f"单只股票最大持仓金额: {strategy.single_stock_max_position:,} 日元")
    print(f"最小持仓数量: {strategy.min_position_size}")
    print(f"建仓窗口: {strategy.entry_start_time} - {strategy.entry_end_time}")
    print(f"平仓窗口: {strategy.exit_start_time} 开始")
    print(f"策略初始化时间: {strategy.strategy_init_time}")
    
    print("\n=== 价格计算示例 ===")
    context = strategy.create_context("9984")
    context.base_price = 1000.0
    context.base_price_set = True
    strategy._calculate_target_and_trigger_prices(context)
    
    print(f"股票代码: {context.symbol}")
    print(f"Base Price: {context.base_price:.2f}")
    print(f"做多目标价格: {context.long_target_price:.2f}")
    print(f"做空目标价格: {context.short_target_price:.2f}")
    print(f"做多触发价格: {context.long_trigger_price:.2f}")
    print(f"做空触发价格: {context.short_trigger_price:.2f}")
    
    # 演示动态仓位计算
    print("\n=== 动态仓位计算示例 ===")
    calculated_size = strategy.calculate_position_size("9984")
    print(f"股票代码: 9984")
    print(f"Base Price: {context.base_price:.2f}")
    print(f"计算出的持仓数量: {calculated_size}")
    print(f"计算逻辑: round({strategy.single_stock_max_position:,} / {context.base_price:.2f} / 100) * 100 = {calculated_size}")
    
    # 演示不同价格的股票
    print("\n不同价格股票的仓位计算:")
    test_prices = [100, 500, 1000, 5000, 10000]
    for price in test_prices:
        test_context = strategy.create_context(f"TEST{price}")
        test_context.base_price = price
        test_context.base_price_set = True
        size = strategy.calculate_position_size(f"TEST{price}")
        print(f"  价格 {price:>5} 日元 -> 持仓数量 {size:>4} 股")
    
    print("\n=== 交易逻辑说明 ===")
    print("1. 14:50前: 策略不初始化，节省资源")
    print("2. 15:00: 记录1分钟K线close price作为base price")
    print("3. 15:22-15:25: 建仓窗口，监控触发价格")
    print("4. 15:25后: 平仓窗口，使用market单平仓")
    print("5. 触发条件:")
    print("   - 做多: 当前价格 >= 做多触发价格")
    print("   - 做空: 当前价格 <= 做空触发价格")
    print("6. 仓位管理:")
    print("   - 基于base price动态计算持仓数量")
    print("   - 确保每只股票的投资金额相对固定")


def demo_time_windows():
    """演示时间窗口"""
    print("\n=== 时间窗口演示 ===")
    
    strategy = ClosingAuctionBetStrategy(use_mock_gateway=True, gateway_type="mock")
    
    # 模拟不同时间点
    time_points = [
        ("14:30", "策略未初始化"),
        ("14:50", "策略初始化，开始监控"),
        ("15:00", "记录base price"),
        ("15:22", "进入建仓窗口"),
        ("15:23", "建仓窗口活跃"),
        ("15:25", "退出建仓窗口，进入平仓窗口"),
        ("15:30", "平仓窗口活跃")
    ]
    
    for time_str, description in time_points:
        hour, minute = map(int, time_str.split(":"))
        current_time = dt_time(hour, minute)
        
        # 检查时间窗口
        strategy._check_time_windows(current_time)
        
        print(f"{time_str}: {description}")
        print(f"  建仓窗口: {'活跃' if strategy.entry_window_active else '非活跃'}")
        print(f"  平仓窗口: {'活跃' if strategy.exit_window_active else '非活跃'}")
        print()


def demo_stock_list():
    """演示股票列表"""
    print("=== TOPIX500 股票列表演示 ===")
    
    symbols = list(topix500)
    print(f"总股票数量: {len(symbols)}")
    print("前20只股票:")
    for i, symbol in enumerate(symbols[:20]):
        print(f"  {i+1:2d}. {symbol}")
    
    print("...")
    print(f"最后5只股票:")
    for i, symbol in enumerate(symbols[-5:], len(symbols)-4):
        print(f"  {i:2d}. {symbol}")


def demo_strategy_status():
    """演示策略状态"""
    print("\n=== 策略状态演示 ===")
    
    strategy = ClosingAuctionBetStrategy(use_mock_gateway=True, gateway_type="mock")
    
    # 创建一些测试Context
    test_symbols = ["9984", "7203", "6758", "6861", "9983"]
    for symbol in test_symbols:
        strategy.create_context(symbol)
    
    # 模拟一些状态
    strategy.contexts["9984"].position = 100  # 多头持仓
    strategy.contexts["7203"].position = -100  # 空头持仓
    strategy.contexts["6758"].entry_order_id = "order_123"
    strategy.contexts["6861"].exit_order_id = "order_456"
    
    status = strategy.get_strategy_status()
    
    print(f"策略初始化: {status['strategy_initialized']}")
    print(f"建仓窗口活跃: {status['entry_window_active']}")
    print(f"平仓窗口活跃: {status['exit_window_active']}")
    print(f"总股票数量: {status['total_symbols']}")
    print(f"活跃持仓: {status['active_positions']}")
    print(f"待处理订单: {status['pending_orders']}")
    
    print("\n详细状态:")
    for symbol, context in strategy.contexts.items():
        print(f"  {symbol}: {context.state.value}, 持仓: {context.position}, "
              f"Entry订单: {context.entry_order_id or '无'}, "
              f"Exit订单: {context.exit_order_id or '无'}")


def main():
    """主演示函数"""
    print("收盘竞价策略 (Closing Auction Bet Strategy) 演示")
    print("=" * 60)
    
    demo_strategy_parameters()
    demo_time_windows()
    demo_stock_list()
    demo_strategy_status()
    
    print("\n" + "=" * 60)
    print("演示完成！")
    print("\n使用方法:")
    print("1. 确保BriskEshitenGateway正常运行")
    print("2. 运行: python closing_auction_bet_strategy.py")
    print("3. 策略会在14:50自动初始化")
    print("4. 监控15:22-15:25的建仓窗口")
    print("5. 在15:25后自动平仓")


if __name__ == "__main__":
    main()
