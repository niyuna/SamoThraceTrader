"""
测试时间戳修复
验证Mock Gateway的tick数据时间戳是否正确
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


def test_timestamp_fix():
    """测试时间戳修复"""
    print("=== 测试时间戳修复 ===")
    
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
            received_ticks[tick.symbol] = []
        
        # 记录前10个tick的详细信息
        if len(received_ticks[tick.symbol]) < 10:
            received_ticks[tick.symbol].append({
                'datetime': tick.datetime,
                'price': tick.last_price,
                'volume': tick.last_volume
            })
            print(f"收到tick: {tick.symbol} - 时间: {tick.datetime} - 价格: {tick.last_price:.2f} - 成交量: {tick.last_volume}")
        
        original_on_tick(event)
    
    strategy.on_tick = on_tick_with_logging
    
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
        mock_setting = {
            "tick_mode": "replay",
            "replay_data_dir": "D:\\dev\\github\\brisk-hack\\brisk_in_day_frames",
            "replay_date": "20250718",  # 根据实际数据文件调整
            "replay_speed": 100.0,      # 100倍速回放
            "mock_account_balance": 10000000,
        }
        
        print("连接Mock Gateway...")
        strategy.connect(mock_setting)
        
        print("初始化股票筛选器...")
        strategy.initialize_stock_filter()
        
        # 等待一段时间接收数据
        print("等待接收数据...")
        time.sleep(3)
        
        # 打印订阅状态
        print(f"\n=== 订阅状态 ===")
        print(f"Gateway订阅的股票: {strategy.gateway.subscribed_symbols}")
        print(f"策略市值筛选后的股票: {strategy.market_cap_eligible}")
        
        # 保持运行一段时间
        print("\n策略运行中，按Ctrl+C退出...")
        tick_count = 0
        while True:
            time.sleep(1)
            tick_count += 1
            if tick_count % 5 == 0:
                print(f"\n=== 运行 {tick_count} 秒后的统计 ===")
                for symbol, ticks in received_ticks.items():
                    if ticks:
                        print(f"{symbol}: 收到 {len(ticks)} 个tick")
                        # 显示时间范围
                        first_time = ticks[0]['datetime']
                        last_time = ticks[-1]['datetime']
                        print(f"  时间范围: {first_time} 到 {last_time}")
                        print(f"  价格范围: {min(t['price'] for t in ticks):.2f} - {max(t['price'] for t in ticks):.2f}")
                
                # 检查时间戳是否正确
                for symbol, ticks in received_ticks.items():
                    if ticks:
                        # 检查时间戳是否在合理范围内（应该是2025年7月18日）
                        for tick_info in ticks:
                            dt = tick_info['datetime']
                            if dt.year != 2025 or dt.month != 7 or dt.day != 18:
                                print(f"⚠️  警告：{symbol} 时间戳异常: {dt}")
                            else:
                                print(f"✅ {symbol} 时间戳正确: {dt}")
                        break  # 只检查第一个股票
                
    except KeyboardInterrupt:
        print("\n收到退出信号...")
    except Exception as e:
        print(f"运行过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 打印最终统计
        print("\n=== 最终统计 ===")
        for symbol, ticks in received_ticks.items():
            if ticks:
                print(f"\n{symbol} 的tick数据:")
                for i, tick_info in enumerate(ticks[:5]):  # 只显示前5个
                    print(f"  {i+1}. 时间: {tick_info['datetime']} - 价格: {tick_info['price']:.2f}")
                if len(ticks) > 5:
                    print(f"  ... 还有 {len(ticks) - 5} 个tick")
        
        strategy.close()
        print("测试完成")


if __name__ == "__main__":
    test_timestamp_fix() 