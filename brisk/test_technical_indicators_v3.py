"""
测试Technical Indicators V3模块
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from vnpy.trader.object import BarData
from vnpy.trader.constant import Exchange, Interval
from technical_indicators_v3 import TechnicalIndicatorManager, VWAPCalculator, BarStatistics


def create_test_bar(symbol: str, dt: datetime, open_price: float, high_price: float, 
                   low_price: float, close_price: float, volume: float, turnover: float) -> BarData:
    """创建测试用的BarData"""
    return BarData(
        symbol=symbol,
        exchange=Exchange.TSE,
        datetime=dt,
        interval=Interval.MINUTE,
        open_price=open_price,
        high_price=high_price,
        low_price=low_price,
        close_price=close_price,
        volume=volume,
        turnover=turnover,
        gateway_name="TEST"
    )


def test_vwap_calculator():
    """测试VWAP计算器"""
    print("=== 测试VWAP计算器 ===")
    
    vwap_calc = VWAPCalculator()
    
    # 创建测试数据
    base_time = datetime(2024, 1, 1, 9, 30, 0)
    
    bars = [
        create_test_bar("TEST", base_time + timedelta(minutes=1), 100, 102, 99, 101, 1000, 101000),
        create_test_bar("TEST", base_time + timedelta(minutes=2), 101, 103, 100, 102, 1500, 153000),
        create_test_bar("TEST", base_time + timedelta(minutes=3), 102, 104, 101, 103, 2000, 206000),
    ]
    
    for i, bar in enumerate(bars):
        vwap = vwap_calc.update_bar(bar)
        print(f"Bar {i+1}: Close={bar.close_price}, Volume={bar.volume}, Turnover={bar.turnover}, VWAP={vwap:.2f}")
    
    stats = vwap_calc.get_daily_stats()
    print(f"当日统计: {stats}")


def test_bar_statistics():
    """测试Bar统计器"""
    print("\n=== 测试Bar统计器 ===")
    
    stats = BarStatistics()
    
    # 创建测试数据
    base_time = datetime(2024, 1, 1, 9, 30, 0)
    vwap = 101.5  # 假设VWAP为101.5
    
    bars = [
        create_test_bar("TEST", base_time + timedelta(minutes=1), 100, 102, 99, 102, 1000, 101000),  # close > vwap
        create_test_bar("TEST", base_time + timedelta(minutes=2), 101, 103, 100, 101, 1500, 153000),  # close < vwap
        create_test_bar("TEST", base_time + timedelta(minutes=3), 102, 104, 101, 101.5, 2000, 206000),  # close = vwap
        create_test_bar("TEST", base_time + timedelta(minutes=4), 102, 104, 101, 103, 2000, 206000),  # close > vwap
    ]
    
    for i, bar in enumerate(bars):
        result = stats.update_bar(bar, vwap)
        print(f"Bar {i+1}: Close={bar.close_price}, VWAP={vwap}, 统计={result}")


def test_technical_indicator_manager():
    """测试技术指标管理器"""
    print("\n=== 测试技术指标管理器 ===")
    
    manager = TechnicalIndicatorManager("TEST", size=20)
    
    # 创建测试数据
    base_time = datetime(2024, 1, 1, 9, 30, 0)
    
    bars = [
        create_test_bar("TEST", base_time + timedelta(minutes=1), 100, 102, 99, 101, 1000, 101000),
        create_test_bar("TEST", base_time + timedelta(minutes=2), 101, 103, 100, 102, 1500, 153000),
        create_test_bar("TEST", base_time + timedelta(minutes=3), 102, 104, 101, 103, 2000, 206000),
        create_test_bar("TEST", base_time + timedelta(minutes=4), 103, 105, 102, 104, 2500, 260000),
        create_test_bar("TEST", base_time + timedelta(minutes=5), 104, 106, 103, 105, 3000, 315000),
        create_test_bar("TEST", base_time + timedelta(minutes=6), 105, 107, 104, 106, 3500, 371000),
        create_test_bar("TEST", base_time + timedelta(minutes=7), 106, 108, 105, 107, 4000, 428000),
        create_test_bar("TEST", base_time + timedelta(minutes=8), 107, 109, 106, 108, 4500, 486000),
        create_test_bar("TEST", base_time + timedelta(minutes=9), 108, 110, 107, 109, 5000, 545000),
        create_test_bar("TEST", base_time + timedelta(minutes=10), 109, 111, 108, 110, 5500, 605000),
        create_test_bar("TEST", base_time + timedelta(minutes=11), 110, 112, 109, 111, 6000, 666000),
        create_test_bar("TEST", base_time + timedelta(minutes=12), 111, 113, 110, 112, 6500, 728000),
        create_test_bar("TEST", base_time + timedelta(minutes=13), 112, 114, 111, 113, 7000, 791000),
        create_test_bar("TEST", base_time + timedelta(minutes=14), 113, 115, 112, 114, 7500, 855000),
        create_test_bar("TEST", base_time + timedelta(minutes=15), 114, 116, 113, 115, 8000, 920000),
        create_test_bar("TEST", base_time + timedelta(minutes=16), 115, 117, 114, 116, 8500, 986000),
        create_test_bar("TEST", base_time + timedelta(minutes=17), 116, 118, 115, 117, 9000, 1053000),
        create_test_bar("TEST", base_time + timedelta(minutes=18), 117, 119, 116, 118, 9500, 1121000),
        create_test_bar("TEST", base_time + timedelta(minutes=19), 118, 120, 117, 119, 10000, 1190000),
        create_test_bar("TEST", base_time + timedelta(minutes=20), 119, 121, 118, 120, 10500, 1260000),
        create_test_bar("TEST", base_time + timedelta(minutes=21), 120, 122, 119, 121, 11000, 1331000),
        create_test_bar("TEST", base_time + timedelta(minutes=22), 121, 123, 120, 122, 11500, 1403000),
        create_test_bar("TEST", base_time + timedelta(minutes=23), 122, 124, 121, 123, 12000, 1476000),
        create_test_bar("TEST", base_time + timedelta(minutes=24), 123, 125, 122, 124, 12500, 1550000),
        create_test_bar("TEST", base_time + timedelta(minutes=25), 124, 126, 123, 125, 13000, 1625000),
    ]
    
    for i, bar in enumerate(bars):
        indicators = manager.update_bar(bar)
        # 只显示前5个和后5个bar，以及关键的初始化点
        if i < 5 or i >= len(bars) - 5 or i == 19:  # 第20个bar是初始化点
            print(f"Bar {i+1}: {bar.datetime.strftime('%H:%M')}")
            print(f"  价格: 开:{bar.open_price:.2f} 高:{bar.high_price:.2f} 低:{bar.low_price:.2f} 收:{bar.close_price:.2f}")
            print(f"  指标: VWAP:{indicators['vwap']:.2f} ATR(14):{indicators['atr_14']:.2f} Vol MA5:{indicators['volume_ma5']:.0f}")
            print(f"  统计: Close>VWAP:{indicators['above_vwap_count']} Close<VWAP:{indicators['below_vwap_count']}")
            print(f"  累计: Volume:{indicators['daily_acc_volume']:.0f} Turnover:{indicators['daily_acc_turnover']:.0f}")
            if i == 19:
                print(f"  *** ArrayManager 初始化完成 (count={i+1} >= size=20) ***")
                # 打印ArrayManager内部数组内容
                am = manager.am
                print(f"  *** ArrayManager 调试信息 ***")
                print(f"    count: {am.count}, size: {am.size}, inited: {am.inited}")
                print(f"    high_array: {am.high_array}")
                print(f"    low_array: {am.low_array}")
                print(f"    close_array: {am.close_array}")
                print(f"    volume_array: {am.volume_array}")
                # 尝试手动计算ATR
                import numpy as np
                high = am.high_array
                low = am.low_array
                close = am.close_array
                print(f"    high[-14:]: {high[-14:]}")
                print(f"    low[-14:]: {low[-14:]}")
                print(f"    close[-14:]: {close[-14:]}")
                # 计算True Range
                tr1 = high - low
                tr2 = np.abs(high - np.roll(close, 1))
                tr3 = np.abs(low - np.roll(close, 1))
                tr = np.maximum(tr1, np.maximum(tr2, tr3))
                print(f"    True Range: {tr}")
                print(f"    ATR(14) 手动计算: {np.mean(tr[-14:]) if len(tr) >= 14 else '数据不足'}")
            print()


def test_daily_reset():
    """测试每日重置功能"""
    print("\n=== 测试每日重置功能 ===")
    
    manager = TechnicalIndicatorManager("TEST", size=10)
    
    # 第一天
    day1_time = datetime(2024, 1, 1, 9, 30, 0)
    bar1 = create_test_bar("TEST", day1_time + timedelta(minutes=1), 100, 102, 99, 101, 1000, 101000)
    indicators1 = manager.update_bar(bar1)
    print(f"第一天: VWAP={indicators1['vwap']:.2f}, 统计={indicators1['above_vwap_count']}")
    
    # 第二天
    day2_time = datetime(2024, 1, 2, 9, 30, 0)
    bar2 = create_test_bar("TEST", day2_time + timedelta(minutes=1), 200, 202, 199, 201, 2000, 402000)
    indicators2 = manager.update_bar(bar2)
    print(f"第二天: VWAP={indicators2['vwap']:.2f}, 统计={indicators2['above_vwap_count']}")


if __name__ == "__main__":
    print("开始测试Technical Indicators V3模块...\n")
    
    try:
        test_vwap_calculator()
        test_bar_statistics()
        test_technical_indicator_manager()
        test_daily_reset()
        
        print("所有测试完成！")
        
    except Exception as e:
        print(f"测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc() 