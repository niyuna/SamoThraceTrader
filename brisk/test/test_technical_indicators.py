"""
测试Technical Indicators V3模块
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from vnpy.trader.object import BarData
from vnpy.trader.constant import Exchange, Interval
import sys
import os
import numpy as np

# 添加父目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from technical_indicators import TechnicalIndicatorManager, VWAPCalculator, BarStatistics


def create_test_bar(symbol: str, dt: datetime, open_price: float, high_price: float, 
                   low_price: float, close_price: float, volume: float, turnover: float) -> BarData:
    """创建测试用的BarData"""
    return BarData(
        symbol=symbol,
        exchange=Exchange.TSE,
        interval=Interval.MINUTE,
        datetime=dt,
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
        result = stats.update_bar(bar, vwap=vwap)
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


def test_current_implementation_verification():
    """验证当前实现的ATR和Volume MA5计算 - 锁定基准值"""
    print("\n=== 验证当前实现 - 锁定基准值 ===")
    
    manager = TechnicalIndicatorManager("TEST", size=15)  # 使用size=15
    base_time = datetime(2024, 1, 1, 9, 30, 0)
    
    # 创建测试数据 - 使用固定的价格模式
    bars = []
    for i in range(20):
        # 创建有规律的价格波动
        base_price = 100 + (i % 4) * 2  # 100, 102, 104, 106, 100, 102, ...
        high_price = base_price + 1.0
        low_price = base_price - 1.0
        close_price = base_price + (i % 3 - 1) * 0.5
        
        bar = create_test_bar(
            "TEST", 
            base_time + timedelta(minutes=i), 
            base_price, 
            high_price, 
            low_price, 
            close_price, 
            1000 + i * 100, 
            (1000 + i * 100) * base_price
        )
        bars.append(bar)
    
    print("锁定当前实现的ATR和Volume MA5计算:")
    print("=" * 60)
    
    # 存储关键点的指标值用于验证
    key_indicators = {}
    
    for i, bar in enumerate(bars):
        try:
            indicators = manager.update_bar(bar)
            
            # 显示关键数据点
            if i < 5 or i in [13, 14, 15, 16, 19]:  # 显示前5个和关键初始化点
                print(f"\nBar {i+1:2d}: {bar.datetime.strftime('%H:%M')}")
                print(f"  价格: 开:{bar.open_price:6.2f} 高:{bar.high_price:6.2f} 低:{bar.low_price:6.2f} 收:{bar.close_price:6.2f}")
                print(f"  成交量: {bar.volume:6.0f}")
                print(f"  指标: ATR(14):{indicators['atr_14']:8.4f} Volume MA5:{indicators['volume_ma5']:8.0f}")
                
                if i == 13:
                    print(f"  *** 第14个bar: ATR应该开始计算 ***")
                elif i == 14:
                    print(f"  *** 第15个bar: ATR第一次完整计算 ***")
                    key_indicators['bar_15'] = indicators
                elif i == 15:
                    print(f"  *** 第16个bar: ArrayManager初始化完成 ***")
                    key_indicators['bar_16'] = indicators
                elif i == 19:
                    print(f"  *** 第20个bar: 最终结果 ***")
                    key_indicators['bar_20'] = indicators
        except Exception as e:
            print(f"Bar {i+1} failed with error: {e}")
            import traceback
            traceback.print_exc()
    
    # 获取最终指标
    final_indicators = manager.get_indicators()
    print(f"\n" + "=" * 60)
    print(f"最终锁定值:")
    print(f"  ATR(14): {final_indicators['atr_14']:.4f}")
    print(f"  Volume MA5: {final_indicators['volume_ma5']:.0f}")
    print(f"  VWAP: {final_indicators['vwap']:.2f}")
    print(f"  Above VWAP count: {final_indicators['above_vwap_count']}")
    print(f"  Below VWAP count: {final_indicators['below_vwap_count']}")
    
    # 分析ArrayManager状态
    am = manager.am
    print(f"\nArrayManager状态:")
    print(f"  count: {am.count}, size: {am.size}, inited: {am.inited}")
    
    if am.inited:
        print(f"  high_array: {am.high_array}")
        print(f"  low_array: {am.low_array}")
        print(f"  close_array: {am.close_array}")
        print(f"  volume_array: {am.volume_array}")
        
        # 尝试理解ATR计算逻辑
        if am.count >= 14:
            print(f"\nATR计算分析:")
            print(f"  最近14个high: {am.high_array[-14:]}")
            print(f"  最近14个low: {am.low_array[-14:]}")
            print(f"  最近14个close: {am.close_array[-14:]}")
            
            # 计算True Range
            high = am.high_array
            low = am.low_array
            close = am.close_array
            
            tr1 = high - low
            tr2 = np.abs(high - np.roll(close, 1))
            tr3 = np.abs(low - np.roll(close, 1))
            tr = np.maximum(tr1, np.maximum(tr2, tr3))
            
            print(f"  最近14个True Range: {tr[-14:]}")
            print(f"  True Range平均值: {np.mean(tr[-14:]):.4f}")
            
            # 尝试理解系统的ATR计算
            print(f"  系统ATR值: {final_indicators['atr_14']:.4f}")
            print(f"  差异: {abs(np.mean(tr[-14:]) - final_indicators['atr_14']):.6f}")
    
    print("=" * 60)
    
    # ==================== 使用基准值进行Assert验证 ====================
    print("\n=== 基准值Assert验证 ===")
    print("开始执行assert验证...")
    
    # 验证第15个bar的指标值
    print("检查key_indicators内容...")
    print(f"key_indicators keys: {list(key_indicators.keys())}")
    
    assert 'bar_15' in key_indicators, "第15个bar的指标值未记录"
    print("✓ bar_15检查通过")
    bar_15_indicators = key_indicators['bar_15']
    
    # ATR(14)在第15个bar应该开始计算
    expected_atr_15 = 3.8929
    actual_atr_15 = bar_15_indicators['atr_14']
    print(f"第15个bar ATR验证: 期望{expected_atr_15}, 实际{actual_atr_15}")
    
    diff = abs(actual_atr_15 - expected_atr_15)
    print(f"差值: {diff}, 阈值: 0.001, 是否通过: {diff < 0.001}")
    
    assert diff < 0.001, \
        f"第15个bar的ATR(14)值不匹配: 期望{expected_atr_15}, 实际{actual_atr_15}"
    print(f"✓ 第15个bar ATR(14)验证通过: {actual_atr_15:.4f}")
    
    # Volume MA5在第15个bar应该开始计算
    expected_vol_ma5_15 = 2200
    actual_vol_ma5_15 = bar_15_indicators['volume_ma5']
    assert abs(actual_vol_ma5_15 - expected_vol_ma5_15) < 0.1, \
        f"第15个bar的Volume MA5值不匹配: 期望{expected_vol_ma5_15}, 实际{actual_vol_ma5_15}"
    print(f"✓ 第15个bar Volume MA5验证通过: {actual_vol_ma5_15:.0f}")
    
    # 验证第16个bar的指标值
    assert 'bar_16' in key_indicators, "第16个bar的指标值未记录"
    bar_16_indicators = key_indicators['bar_16']
    
    # ATR(14)在第16个bar应该继续计算
    expected_atr_16 = 3.7934
    actual_atr_16 = bar_16_indicators['atr_14']
    assert abs(actual_atr_16 - expected_atr_16) < 0.001, \
        f"第16个bar的ATR(14)值不匹配: 期望{expected_atr_16}, 实际{actual_atr_16}"
    print(f"✓ 第16个bar ATR(14)验证通过: {actual_atr_16:.4f}")
    
    # Volume MA5在第16个bar应该继续计算
    expected_vol_ma5_16 = 2300
    actual_vol_ma5_16 = bar_16_indicators['volume_ma5']
    assert abs(actual_vol_ma5_16 - expected_vol_ma5_16) < 0.1, \
        f"第16个bar的Volume MA5值不匹配: 期望{expected_vol_ma5_16}, 实际{actual_vol_ma5_16}"
    print(f"✓ 第16个bar Volume MA5验证通过: {actual_vol_ma5_16:.0f}")
    
    # 验证第20个bar的指标值
    assert 'bar_20' in key_indicators, "第20个bar的指标值未记录"
    bar_20_indicators = key_indicators['bar_20']
    
    # ATR(14)在第20个bar的最终值
    expected_atr_20 = 3.7926
    actual_atr_20 = bar_20_indicators['atr_14']
    assert abs(actual_atr_20 - expected_atr_20) < 0.001, \
        f"第20个bar的ATR(14)值不匹配: 期望{expected_atr_20}, 实际{actual_atr_20}"
    print(f"✓ 第20个bar ATR(14)验证通过: {actual_atr_20:.4f}")
    
    # Volume MA5在第20个bar的最终值
    expected_vol_ma5_20 = 2700
    actual_vol_ma5_20 = bar_20_indicators['volume_ma5']
    assert abs(actual_vol_ma5_20 - expected_vol_ma5_20) < 0.1, \
        f"第20个bar的Volume MA5值不匹配: 期望{expected_vol_ma5_20}, 实际{actual_vol_ma5_20}"
    print(f"✓ 第20个bar Volume MA5验证通过: {actual_vol_ma5_20:.0f}")
    
    # 验证最终指标值
    expected_vwap_final = 103.13
    actual_vwap_final = final_indicators['vwap']
    assert abs(actual_vwap_final - expected_vwap_final) < 0.01, \
        f"最终VWAP值不匹配: 期望{expected_vwap_final}, 实际{actual_vwap_final}"
    print(f"✓ 最终VWAP验证通过: {actual_vwap_final:.2f}")
    
    expected_above_vwap_count = 12
    actual_above_vwap_count = final_indicators['above_vwap_count']
    assert actual_above_vwap_count == expected_above_vwap_count, \
        f"Above VWAP count不匹配: 期望{expected_above_vwap_count}, 实际{actual_above_vwap_count}"
    print(f"✓ Above VWAP count验证通过: {actual_above_vwap_count}")
    
    expected_below_vwap_count = 8
    actual_below_vwap_count = final_indicators['below_vwap_count']
    assert actual_below_vwap_count == expected_below_vwap_count, \
        f"Below VWAP count不匹配: 期望{expected_below_vwap_count}, 实际{actual_below_vwap_count}"
    print(f"✓ Below VWAP count验证通过: {actual_below_vwap_count}")
    
    print("\n🎯 所有基准值验证通过！这些值将作为重构时的黄金标准。")
    print("=" * 60)


def test_manual_calculator_combination():
    """测试手动组合Calculator的示例"""
    print("\n=== 测试手动组合Calculator的示例 ===")
    
    from technical_indicators import SimpleATRStrategy, VolumeStrategy, CustomStrategy
    
    base_time = datetime(2024, 1, 1, 9, 30, 0)
    
    # 创建测试数据
    bars = []
    for i in range(20):
        base_price = 100 + (i % 4) * 2
        high_price = base_price + 1.0
        low_price = base_price - 1.0
        close_price = base_price + (i % 3 - 1) * 0.5
        
        bar = create_test_bar(
            "TEST",
            base_time + timedelta(minutes=i),
            base_price,
            high_price,
            low_price,
            close_price,
            1000 + i * 100,
            (1000 + i * 100) * base_price
        )
        bars.append(bar)
    
    # 测试1：SimpleATRStrategy
    print("测试1：SimpleATRStrategy（只计算ATR）")
    atr_strategy = SimpleATRStrategy("TEST", size=15)
    
    for i, bar in enumerate(bars):
        atr = atr_strategy.update_bar(bar)
        if i in [13, 14, 15, 16, 19]:  # 关键点
            print(f"Bar {i+1:2d}: ATR(14) = {atr:.4f}")
    
    print(f"最终ATR: {atr_strategy.get_atr():.4f}")
    
    # 测试2：VolumeStrategy
    print("\n测试2：VolumeStrategy（只计算Volume MA）")
    volume_strategy = VolumeStrategy("TEST", size=15)
    
    for i, bar in enumerate(bars):
        vol_ma = volume_strategy.update_bar(bar)
        if i in [13, 14, 15, 16, 19]:  # 关键点
            print(f"Bar {i+1:2d}: Volume MA(10) = {vol_ma:.0f}")
    
    print(f"最终Volume MA: {volume_strategy.get_volume_ma():.0f}")
    
    # 测试3：CustomStrategy
    print("\n测试3：CustomStrategy（组合多个计算器）")
    custom_strategy = CustomStrategy("TEST", size=15)
    
    for i, bar in enumerate(bars):
        indicators = custom_strategy.update_bar(bar)
        if i in [13, 14, 15, 16, 19]:  # 关键点
            print(f"Bar {i+1:2d}: ATR(20)={indicators.get('atr_20', 0):8.4f} "
                  f"Volume MA(3)={indicators.get('volume_ma3', 0):8.0f} "
                  f"VWAP={indicators.get('vwap', 0):6.2f}")
    
    final_indicators = custom_strategy.get_indicators()
    print(f"\n最终结果:")
    print(f"  ATR(20): {final_indicators.get('atr_20', 0):.4f}")
    print(f"  Volume MA(3): {final_indicators.get('volume_ma3', 0):.0f}")
    print(f"  VWAP: {final_indicators.get('vwap', 0):.2f}")
    
    print("\n✓ 手动组合Calculator测试完成！")


def test_base_strategy_flexibility():
    """测试修复后的base strategy是否能够灵活处理不同的技术指标"""
    print("\n=== 测试修复后的base strategy灵活性 ===")
    
    from technical_indicators import SimpleATRStrategy, VolumeStrategy, CustomStrategy
    from intraday_strategy_base import IntradayStrategyBase
    
    # 创建一个测试用的base strategy
    class TestStrategy(IntradayStrategyBase):
        def __init__(self):
            super().__init__()
            # 不调用add_symbol，手动设置indicator_managers
        
        def get_entry_direction(self, symbol: str) -> str:
            return 'long'  # 简单返回long
        
        def _calculate_entry_price(self, context, bar, indicators) -> float:
            return bar.close_price
        
        def _calculate_exit_price(self, context, bar, indicators) -> float:
            return bar.close_price
    
    strategy = TestStrategy()
    
    # 测试1：使用SimpleATRStrategy作为indicator manager
    print("测试1：使用SimpleATRStrategy（只有ATR指标）")
    atr_manager = SimpleATRStrategy("TEST", size=15)
    strategy.indicator_managers["TEST"] = atr_manager
    
    # 创建测试数据
    base_time = datetime(2024, 1, 1, 9, 30, 0)
    test_bar = create_test_bar(
        "TEST", base_time + timedelta(minutes=15), 104, 105, 103, 104.5, 2400, 249600
    )
    
    # 更新指标
    indicators = atr_manager.update_bar(test_bar)
    print(f"ATR指标: {indicators}")
    
    # 测试print_summary
    print("\n调用print_summary:")
    strategy.print_summary()
    
    # 测试2：使用VolumeStrategy作为indicator manager
    print("\n测试2：使用VolumeStrategy（只有Volume MA指标）")
    volume_manager = VolumeStrategy("TEST2", size=15)
    strategy.indicator_managers["TEST2"] = volume_manager
    
    # 更新指标
    indicators = volume_manager.update_bar(test_bar)
    print(f"Volume MA指标: {indicators}")
    
    # 再次测试print_summary
    print("\n调用print_summary:")
    strategy.print_summary()
    
    # 测试3：使用CustomStrategy作为indicator manager
    print("\n测试3：使用CustomStrategy（组合多个指标）")
    custom_manager = CustomStrategy("TEST3", size=15)
    strategy.indicator_managers["TEST3"] = custom_manager
    
    # 更新指标
    indicators = custom_manager.update_bar(test_bar)
    print(f"自定义指标: {indicators}")
    
    # 最终测试print_summary
    print("\n最终print_summary:")
    strategy.print_summary()
    
    print("\n✓ Base Strategy灵活性测试完成！")


if __name__ == "__main__":
    print("开始测试Technical Indicators V3模块...\n")
    
    try:
        test_vwap_calculator()
        test_bar_statistics()
        test_technical_indicator_manager()
        test_daily_reset()
        test_current_implementation_verification()  # 锁定当前实现的基准值
        test_manual_calculator_combination()        # 测试手动组合的示例
        test_base_strategy_flexibility()            # 测试修复后的base strategy
        
        print("\n所有测试完成！")
        
    except Exception as e:
        print(f"测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc() 