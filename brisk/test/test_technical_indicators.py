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
import pandas as pd
# import pandas_ta as ta

# 添加父目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from technical_indicators import TechnicalIndicatorManager, VWAPCalculator, BarStatistics


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


def test_atr_with_real_csv_data():
    """使用真实CSV数据测试ATR计算"""
    print("\n=== 使用真实CSV数据测试ATR计算 ===")
    
    import pandas as pd
    import numpy as np
    from datetime import datetime
    
    # 读取CSV文件
    csv_path = r"D:\dev\github\brisk-hack\gomihiroi\atr_test_2432.csv"
    try:
        df = pd.read_csv(csv_path)
        print(f"成功读取CSV文件，共{len(df)}行数据")
        print(f"列名: {list(df.columns)}")
        
        # 显示前几行数据
        print("\n前5行数据:")
        print(df.head())
        
    except Exception as e:
        print(f"读取CSV文件失败: {e}")
        return
    
    # 创建技术指标管理器
    manager = TechnicalIndicatorManager("2432", size=15)
    
    # 处理每一行数据
    for idx, row in df.iterrows():
        try:
            # 解析datetime
            dt_str = str(row['datetime'])
            if pd.isna(dt_str) or dt_str == 'nan':
                continue
                
            # 处理datetime格式
            if '0000' in dt_str:
                dt_str = dt_str.replace('0000', '00')
            
            dt = pd.to_datetime(dt_str)
            
            # 创建BarData
            bar = create_test_bar(
                symbol="2432",
                dt=dt,
                open_price=float(row['o']),
                high_price=float(row['h']),
                low_price=float(row['l']),
                close_price=float(row['c']),
                volume=float(row['vol']),
                turnover=float(row['turnover'])
            )
            
            # 更新技术指标
            indicators = manager.update_bar(bar)
            
            # 显示关键数据点
            if idx >= 130: #idx < 5 or idx >= len(df) - 5 or (idx + 1) % 50 == 0 or idx >= 130:
                print(f"\nBar {idx+1}: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"  价格: 开:{bar.open_price:.2f} 高:{bar.high_price:.2f} 低:{bar.low_price:.2f} 收:{bar.close_price:.2f}")
                print(f"  指标: VWAP:{indicators['vwap']:.2f} ATR(14):{indicators['atr_14']:.4f}")
                
                # 手动验证ATR计算
                if manager.am.count >= 14:
                    am = manager.am
                    high = am.high_array
                    low = am.low_array
                    close = am.close_array
                    
                    # 显示最近14期的True Range值
                    if idx < 10:  # 只在前几个bar显示详细信息
                        print(f"  最近14期True Range: {tr[-14:]}")
                
        except Exception as e:
            print(f"处理第{idx+1}行数据时出错: {e}")
            continue
    
    print(f"\n测试完成，共处理了{len(df)}行数据")


def test_atr_with_pandas_ta_comparison():
    """使用pandas_ta库对比ATR计算"""
    print("\n=== 使用pandas_ta库对比ATR计算 ===")
    
    import pandas as pd
    import pandas_ta as ta
    import numpy as np
    from datetime import datetime
    
    # 读取CSV文件
    csv_path = r"D:\dev\github\brisk-hack\gomihiroi\atr_test_2432.csv"
    try:
        df = pd.read_csv(csv_path)
        print(f"成功读取CSV文件，共{len(df)}行数据")
        
        # 预处理数据
        df['datetime'] = pd.to_datetime(df['datetime'].str.replace('0000', '00'))
        df = df.sort_values('datetime').reset_index(drop=True)
        
        # 使用pandas_ta计算ATR
        df['atr_pandas_ta'] = df.ta.atr(length=14, high='h', low='l', close='c')
        
        print(f"pandas_ta ATR计算完成")
        print(f"前5行pandas_ta ATR值: {df['atr_pandas_ta'].head().tolist()}")
        
    except Exception as e:
        print(f"读取CSV文件或计算pandas_ta ATR失败: {e}")
        return
    
    # 创建技术指标管理器
    manager = TechnicalIndicatorManager("2432", size=20)
    
    # 手动计算ATR的辅助函数
    def calculate_true_range(high, low, close):
        """计算True Range"""
        tr1 = high - low
        tr2 = np.abs(high - np.roll(close, 1))
        tr3 = np.abs(low - np.roll(close, 1))
        return np.maximum(tr1, np.maximum(tr2, tr3))
    
    def calculate_atr_manual(high_array, low_array, close_array, period=14):
        """手动计算ATR"""
        if len(high_array) < period:
            return 0.0
        
        tr = calculate_true_range(high_array, low_array, close_array)
        return np.mean(tr[-period:])
    
    # 对比结果
    comparison_results = []
    
    # 处理每一行数据
    for idx, row in df.iterrows():
        try:
            # 创建BarData
            bar = create_test_bar(
                symbol="2432",
                dt=row['datetime'],
                open_price=float(row['o']),
                high_price=float(row['h']),
                low_price=float(row['l']),
                close_price=float(row['c']),
                volume=float(row['vol']),
                turnover=float(row['turnover'])
            )
            
            # 更新技术指标
            indicators = manager.update_bar(bar)
            
            # 获取pandas_ta的ATR值
            atr_pandas_ta = row['atr_pandas_ta']
            atr_system = indicators['atr_14']
            
            # 手动计算ATR进行验证
            if manager.am.inited and manager.am.count >= 14:
                am = manager.am
                atr_manual = calculate_atr_manual(am.high_array, am.low_array, am.close_array, 14)
            else:
                atr_manual = 0.0
            
            # 记录对比结果
            comparison_results.append({
                'bar_idx': idx + 1,
                'datetime': row['datetime'],
                'close': bar.close_price,
                'atr_system': atr_system,
                'atr_pandas_ta': atr_pandas_ta,
                'atr_manual': atr_manual,
                'diff_system_pandas': abs(atr_system - atr_pandas_ta) if not pd.isna(atr_pandas_ta) else float('inf'),
                'diff_system_manual': abs(atr_system - atr_manual),
                'diff_pandas_manual': abs(atr_pandas_ta - atr_manual) if not pd.isna(atr_pandas_ta) else float('inf')
            })
            
            # 显示关键数据点
            if idx < 5 or idx >= len(df) - 5 or (idx + 1) % 30 == 0:
                print(f"\nBar {idx+1}: {row['datetime'].strftime('%H:%M:%S')}")
                print(f"  价格: 收:{bar.close_price:.2f}")
                print(f"  系统ATR: {atr_system:.4f}")
                print(f"  pandas_ta ATR: {atr_pandas_ta:.4f}" if not pd.isna(atr_pandas_ta) else "  pandas_ta ATR: NaN")
                print(f"  手动ATR: {atr_manual:.4f}")
                
                if not pd.isna(atr_pandas_ta):
                    print(f"  系统-pandas_ta差异: {abs(atr_system - atr_pandas_ta):.6f}")
                print(f"  系统-手动差异: {abs(atr_system - atr_manual):.6f}")
                
        except Exception as e:
            print(f"处理第{idx+1}行数据时出错: {e}")
            continue
    
    # 分析对比结果
    comparison_df = pd.DataFrame(comparison_results)
    
    print(f"\n=== ATR计算对比分析 ===")
    print(f"总数据点: {len(comparison_df)}")
    
    # 统计有效数据点（pandas_ta不为NaN的）
    valid_data = comparison_df[~comparison_df['atr_pandas_ta'].isna()]
    print(f"有效数据点: {len(valid_data)}")
    
    if len(valid_data) > 0:
        print(f"\n系统 vs pandas_ta:")
        print(f"  平均差异: {valid_data['diff_system_pandas'].mean():.6f}")
        print(f"  最大差异: {valid_data['diff_system_pandas'].max():.6f}")
        print(f"  标准差: {valid_data['diff_system_pandas'].std():.6f}")
        
        # 找出差异最大的几个点
        max_diff_idx = valid_data['diff_system_pandas'].idxmax()
        max_diff_row = valid_data.loc[max_diff_idx]
        print(f"\n最大差异点 (Bar {max_diff_row['bar_idx']}):")
        print(f"  系统ATR: {max_diff_row['atr_system']:.4f}")
        print(f"  pandas_ta ATR: {max_diff_row['atr_pandas_ta']:.4f}")
        print(f"  差异: {max_diff_row['diff_system_pandas']:.6f}")
    
    print(f"\n系统 vs 手动计算:")
    print(f"  平均差异: {comparison_df['diff_system_manual'].mean():.6f}")
    print(f"  最大差异: {comparison_df['diff_system_manual'].max():.6f}")
    print(f"  标准差: {comparison_df['diff_system_manual'].std():.6f}")
    
    # 检查是否有显著差异
    significant_diff_threshold = 0.001
    significant_diffs = comparison_df[comparison_df['diff_system_manual'] > significant_diff_threshold]
    if len(significant_diffs) > 0:
        print(f"\n*** 发现{len(significant_diffs)}个显著差异点 (> {significant_diff_threshold}) ***")
        for _, row in significant_diffs.head(3).iterrows():
            print(f"  Bar {row['bar_idx']}: 系统={row['atr_system']:.4f}, 手动={row['atr_manual']:.4f}, 差异={row['diff_system_manual']:.6f}")
    else:
        print(f"\n✓ 所有ATR计算差异都在阈值范围内 (< {significant_diff_threshold})")
    
    print(f"\n测试完成，共处理了{len(df)}行数据")


if __name__ == "__main__":
    print("开始测试Technical Indicators V3模块...\n")
    
    try:
        # test_vwap_calculator()
        # test_bar_statistics()
        # test_technical_indicator_manager()
        # test_daily_reset()
        test_atr_with_real_csv_data()  # 添加新的CSV数据测试
        # test_atr_with_pandas_ta_comparison()  # 添加pandas_ta对比测试
        
        print("所有测试完成！")
        
    except Exception as e:
        print(f"测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc() 