"""
测试VWAP Failure策略使用Mock Gateway
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


def test_vwap_failure_with_mock_gateway():
    """测试VWAP Failure策略使用Mock Gateway"""
    print("=== 测试VWAP Failure策略使用Mock Gateway ===")
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    
    # 创建策略实例（使用Mock Gateway）
    strategy = VWAPFailureStrategy(use_mock_gateway=True)
    
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
            "replay_date": "20241201",  # 根据实际数据文件调整
            "replay_speed": 20.0,       # 20倍速回放
            "replay_symbols": ["7203", "6758", "9984"],  # 指定要回放的股票
            "mock_account_balance": 10000000,
            "mock_commission_rate": 0.001,
            "mock_slippage": 0.0,
            "mock_fill_delay": 0.1,
        }
        
        print("连接Mock Gateway...")
        strategy.connect(mock_setting)
        
        print("初始化股票筛选器...")
        strategy.initialize_stock_filter()
        
        # 等待一段时间接收数据
        print("等待接收回放数据...")
        time.sleep(3)
        
        # 保持运行
        print("策略运行中，按Ctrl+C退出...")
        tick_count = 0
        while True:
            time.sleep(1)
            tick_count += 1
            if tick_count % 10 == 0:
                print(f"已运行 {tick_count} 秒...")
                
    except KeyboardInterrupt:
        print("\n收到退出信号...")
    except Exception as e:
        print(f"运行过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 打印策略状态
        print("\n=== 策略运行结果 ===")
        strategy.print_strategy_status()
        print(strategy.get_signals_summary())
        strategy.close()
        print("测试完成")


if __name__ == "__main__":
    test_vwap_failure_with_mock_gateway() 