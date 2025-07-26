"""
测试订阅过滤功能
验证Mock Gateway在replay模式下只发送已订阅股票的tick数据
"""

import sys
import os
import time
import signal

# 添加父目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vwap_failure_strategy import VWAPFailureStrategy


def signal_handler(signum, frame):
    """信号处理器，用于优雅退出"""
    print("\n收到退出信号，正在关闭...")
    sys.exit(0)


def test_subscription_filter():
    """测试订阅过滤功能"""
    print("=== 测试订阅过滤功能 ===")
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    
    # 创建策略实例（使用Mock Gateway）
    strategy = VWAPFailureStrategy(use_mock_gateway=True)
    
    # 记录接收到的tick数据
    received_ticks = {}
    
    # 重写on_tick方法来记录接收到的tick
    original_on_tick = strategy.on_tick
    def on_tick_with_logging(event):
        tick = event.data
        if tick.symbol not in received_ticks:
            received_ticks[tick.symbol] = 0
        received_ticks[tick.symbol] += 1
        print(f"收到tick: {tick.symbol} - 价格: {tick.last_price:.2f} - 累计: {received_ticks[tick.symbol]}")
        original_on_tick(event)
    
    strategy.on_tick = on_tick_with_logging
    
    try:
        # 设置策略参数
        strategy.set_strategy_params(
            market_cap_threshold=100_000_000_000,
            gap_up_threshold=0.02,
            gap_down_threshold=-0.02,
            failure_threshold_gap_up=3,        # Gap Up时的VWAP failure次数阈值
            failure_threshold_gap_down=2,      # Gap Down时的VWAP failure次数阈值
            entry_factor_gap_up=1.5,
            entry_factor_gap_down=1.2,
            max_daily_trades_gap_up=3,
            max_daily_trades_gap_down=2,
            latest_entry_time="23:59:50",
            exit_factor_gap_up=1.0,
            exit_factor_gap_down=0.8,
            max_exit_wait_time_gap_up=5,
            max_exit_wait_time_gap_down=3,
            max_vol_ma5_ratio_threshold_gap_up=2.0,
            max_vol_ma5_ratio_threshold_gap_down=1.5
        )
        
        # 配置Mock Gateway的replay模式
        # 注意：现在会加载所有股票的数据，但策略只会订阅部分股票
        mock_setting = {
            "tick_mode": "replay",
            "replay_data_dir": "D:\\dev\\github\\brisk-hack\\brisk_in_day_frames",
            "replay_date": "20250718",  # 根据实际数据文件调整
            "replay_speed": 50.0,       # 50倍速回放
            "mock_account_balance": 10000000,
        }
        
        print("连接Mock Gateway...")
        strategy.connect(mock_setting)
        
        print("初始化股票筛选器...")
        strategy.initialize_stock_filter()
        
        # 等待一段时间接收数据
        print("等待接收数据...")
        time.sleep(5)
        
        # 打印订阅状态
        print(f"\n=== 订阅状态 ===")
        print(f"Gateway订阅的股票: {strategy.gateway.subscribed_symbols}")
        print(f"策略市值筛选后的股票: {strategy.market_cap_eligible}")
        print(f"策略最终符合条件的股票: {strategy.eligible_stocks}")
        
        # 保持运行一段时间
        print("\n策略运行中，按Ctrl+C退出...")
        tick_count = 0
        while True:
            time.sleep(1)
            tick_count += 1
            if tick_count % 10 == 0:
                print(f"\n=== 运行 {tick_count} 秒后的统计 ===")
                print(f"接收到的tick统计: {received_ticks}")
                total_ticks = sum(received_ticks.values())
                print(f"总tick数量: {total_ticks}")
                
                # 检查是否只收到了订阅股票的tick
                unsubscribed_ticks = {symbol: count for symbol, count in received_ticks.items() 
                                    if symbol not in strategy.gateway.subscribed_symbols}
                if unsubscribed_ticks:
                    print(f"⚠️  警告：收到了未订阅股票的tick: {unsubscribed_ticks}")
                else:
                    print("✅ 正确：只收到了已订阅股票的tick")
                
    except KeyboardInterrupt:
        print("\n收到退出信号...")
    except Exception as e:
        print(f"运行过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 打印最终统计
        print("\n=== 最终统计 ===")
        print(f"接收到的tick统计: {received_ticks}")
        total_ticks = sum(received_ticks.values())
        print(f"总tick数量: {total_ticks}")
        
        # 检查订阅过滤效果
        subscribed_ticks = {symbol: count for symbol, count in received_ticks.items() 
                           if symbol in strategy.gateway.subscribed_symbols}
        unsubscribed_ticks = {symbol: count for symbol, count in received_ticks.items() 
                             if symbol not in strategy.gateway.subscribed_symbols}
        
        print(f"已订阅股票的tick: {subscribed_ticks}")
        print(f"未订阅股票的tick: {unsubscribed_ticks}")
        
        if unsubscribed_ticks:
            print("❌ 测试失败：收到了未订阅股票的tick数据")
        else:
            print("✅ 测试成功：只收到了已订阅股票的tick数据")
        
        strategy.close()
        print("测试完成")


if __name__ == "__main__":
    test_subscription_filter() 