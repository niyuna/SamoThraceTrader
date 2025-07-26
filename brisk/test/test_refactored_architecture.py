"""
测试重构后的架构
验证Gateway抽象和Strategy接口的正确性
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


def test_mock_gateway_replay():
    """测试Mock Gateway的replay功能"""
    print("=== 测试Mock Gateway Replay模式 ===")
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    
    # 创建策略实例（使用Mock Gateway）
    strategy = VWAPFailureStrategy(use_mock_gateway=True)
    
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
        mock_setting = {
            "tick_mode": "replay",
            "replay_data_dir": "D:\\dev\\github\\brisk-hack\\brisk_in_day_frames",
            "replay_date": "20250718",  # 根据实际数据文件调整
            "replay_speed": 20.0,       # 20倍速回放
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
        print("等待接收数据...")
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


def test_mock_gateway_mock_tick():
    """测试Mock Gateway的mock tick功能"""
    print("=== 测试Mock Gateway Mock Tick模式 ===")
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    
    # 创建策略实例（使用Mock Gateway）
    strategy = VWAPFailureStrategy(use_mock_gateway=True)
    
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
            max_exit_wait_time_gap_down=3
        )
        
        # 配置Mock Gateway的mock tick模式
        mock_setting = {
            "tick_mode": "mock",
            "mock_tick_interval": 1.0,
            "mock_price_volatility": 0.01,
            "mock_volume_range": (100, 1000),
            "mock_base_prices": {
                "7203": 1000.0,
                "6758": 2000.0,
                "9984": 3000.0,
            },
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
        print("等待接收Mock Tick数据...")
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
    # 选择测试模式
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "mock":
        test_mock_gateway_mock_tick()
    else:
        test_mock_gateway_replay() 