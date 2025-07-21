"""
测试Brisk Gateway的成交量和成交额累计功能
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from vnpy.trader.object import TickData
from vnpy.trader.constant import Exchange
from brisk_gateway import BriskGateway
from vnpy.event import EventEngine


def create_test_frame(symbol: str, timestamp: int, price10: int, quantity: int) -> dict:
    """创建测试用的frame数据"""
    return {
        "timestamp": timestamp,
        "price10": price10,
        "quantity": quantity
    }


def test_volume_accumulation():
    """测试成交量和成交额累计功能"""
    print("=== 测试成交量和成交额累计功能 ===")
    
    # 创建EventEngine和BriskGateway
    event_engine = EventEngine()
    gateway = BriskGateway(event_engine, "BRISK")
    
    # 测试数据
    symbol = "7203"
    base_timestamp = 34200000000  # 9:30:00 的微秒时间戳
    date_str = "20240115"
    
    # 创建测试frames
    frames = [
        create_test_frame(symbol, base_timestamp + 1000000, 1010, 100),   # 9:30:01, 101.0, 100股
        create_test_frame(symbol, base_timestamp + 2000000, 1020, 200),   # 9:30:02, 102.0, 200股
        create_test_frame(symbol, base_timestamp + 3000000, 1030, 150),   # 9:30:03, 103.0, 150股
        create_test_frame(symbol, base_timestamp + 4000000, 1040, 300),   # 9:30:04, 104.0, 300股
    ]
    
    print(f"测试股票: {symbol}")
    print(f"测试日期: {date_str}")
    print()
    
    # 处理每个frame
    for i, frame in enumerate(frames):
        tick = gateway._convert_frame_to_tick(symbol, frame, date_str)
        
        if tick:
            print(f"Frame {i+1}:")
            print(f"  时间: {tick.datetime.strftime('%H:%M:%S')}")
            print(f"  价格: {tick.last_price:.2f}")
            print(f"  单次成交量: {tick.last_volume}")
            print(f"  累计成交量: {tick.volume}")
            print(f"  累计成交额: {tick.turnover:.2f}")
            
            # 验证累计计算
            expected_volume = sum(frames[j]["quantity"] for j in range(i+1))
            expected_turnover = sum(frames[j]["quantity"] * frames[j]["price10"] / 10.0 for j in range(i+1))
            
            print(f"  预期累计成交量: {expected_volume}")
            print(f"  预期累计成交额: {expected_turnover:.2f}")
            print(f"  成交量验证: {'✅' if tick.volume == expected_volume else '❌'}")
            print(f"  成交额验证: {'✅' if abs(tick.turnover - expected_turnover) < 0.01 else '❌'}")
            print()
        else:
            print(f"Frame {i+1}: 转换失败")
            print()


def test_daily_reset():
    """测试每日重置功能"""
    print("\n=== 测试每日重置功能 ===")
    
    # 创建EventEngine和BriskGateway
    event_engine = EventEngine()
    gateway = BriskGateway(event_engine, "BRISK")
    
    symbol = "7203"
    base_timestamp = 34200000000  # 9:30:00 的微秒时间戳
    
    # 第一天
    print("第一天 (20240115):")
    frames_day1 = [
        create_test_frame(symbol, base_timestamp + 1000000, 1010, 100),
        create_test_frame(symbol, base_timestamp + 2000000, 1020, 200),
    ]
    
    for i, frame in enumerate(frames_day1):
        tick = gateway._convert_frame_to_tick(symbol, frame, "20240115")
        if tick:
            print(f"  Frame {i+1}: 累计成交量={tick.volume}, 累计成交额={tick.turnover:.2f}")
    
    # 第二天
    print("\n第二天 (20240116):")
    frames_day2 = [
        create_test_frame(symbol, base_timestamp + 1000000, 2010, 300),  # 不同的价格和成交量
        create_test_frame(symbol, base_timestamp + 2000000, 2020, 400),
    ]
    
    for i, frame in enumerate(frames_day2):
        tick = gateway._convert_frame_to_tick(symbol, frame, "20240116")
        if tick:
            print(f"  Frame {i+1}: 累计成交量={tick.volume}, 累计成交额={tick.turnover:.2f}")
    
    # 验证重置
    cache = gateway._trading_cache[symbol]
    print(f"\n缓存状态:")
    print(f"  当前累计成交量: {cache['current_volume']}")
    print(f"  当前累计成交额: {cache['current_turnover']:.2f}")
    print(f"  最后日期: {cache['last_date']}")


def test_timestamp_order():
    """测试时间戳顺序检查"""
    print("\n=== 测试时间戳顺序检查 ===")
    
    # 创建EventEngine和BriskGateway
    event_engine = EventEngine()
    gateway = BriskGateway(event_engine, "BRISK")
    
    symbol = "7203"
    base_timestamp = 34200000000  # 9:30:00 的微秒时间戳
    date_str = "20240115"
    
    # 创建乱序的frames
    frames = [
        create_test_frame(symbol, base_timestamp + 3000000, 1030, 150),   # 9:30:03
        create_test_frame(symbol, base_timestamp + 1000000, 1010, 100),   # 9:30:01 (时间戳倒序)
        create_test_frame(symbol, base_timestamp + 2000000, 1020, 200),   # 9:30:02
    ]
    
    print(f"测试股票: {symbol}")
    print("处理乱序frames:")
    
    for i, frame in enumerate(frames):
        tick = gateway._convert_frame_to_tick(symbol, frame, date_str)
        
        if tick:
            print(f"  Frame {i+1}: 时间={tick.datetime.strftime('%H:%M:%S')}, 累计成交量={tick.volume}")
        else:
            print(f"  Frame {i+1}: 被跳过 (时间戳倒序)")


if __name__ == "__main__":
    print("开始测试Brisk Gateway的成交量和成交额累计功能...\n")
    
    try:
        test_volume_accumulation()
        test_daily_reset()
        test_timestamp_order()
        
        print("\n所有测试完成！")
        
    except Exception as e:
        print(f"测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc() 