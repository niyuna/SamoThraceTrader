"""
测试 Windows Toast 通知功能
"""

import time
from dummy_tick_monitor_strategy import DummyTickMonitorStrategy


def test_toast_notification():
    """测试 Toast 通知功能"""
    print("测试 Windows Toast 通知功能...")
    
    # 创建策略实例
    strategy = DummyTickMonitorStrategy()
    
    try:
        # 测试直接发送通知
        print("1. 测试直接发送通知...")
        strategy._send_toast_notification("测试通知", "这是一个测试通知", "INFO")
        time.sleep(2)
        
        print("2. 测试警告通知...")
        strategy._send_toast_notification("测试警告", "这是一个测试警告", "WARN")
        time.sleep(2)
        
        print("3. 测试严重警告通知...")
        strategy._send_toast_notification("测试严重警告", "这是一个测试严重警告", "CRIT")
        time.sleep(2)
        
        # 测试通知冷却机制
        print("4. 测试通知冷却机制（1分钟内重复通知应该被忽略）...")
        strategy._send_toast_notification("测试冷却", "这个通知应该被忽略", "INFO")
        time.sleep(1)
        
        # 显示状态
        print("5. 显示通知状态...")
        strategy.print_monitoring_status()
        
        print("\n测试完成！请检查是否收到了 Windows Toast 通知。")
        
    except Exception as e:
        print(f"测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        strategy.close()


if __name__ == "__main__":
    test_toast_notification() 