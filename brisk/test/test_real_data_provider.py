"""
使用真实数据测试BriskHistoricalDataProvider
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hft_bb_indicators import BriskHistoricalDataProvider
from vnpy.trader.object import BarData
from datetime import datetime

def test_real_data():
    """使用真实数据测试BriskHistoricalDataProvider"""
    print("=== 使用真实数据测试BriskHistoricalDataProvider ===")
    
    # 创建provider，使用真实数据目录
    provider = BriskHistoricalDataProvider("../data/brisk_agged_ohlc")
    
    # 测试日期
    test_date = "20250724"
    symbols = ["6098", "9984"]
    
    print(f"测试日期: {test_date}")
    print(f"测试股票: {symbols}")
    
    # 检查数据可用性
    print("\n1. 检查数据可用性:")
    for symbol in symbols:
        available = provider.is_data_available(symbol, test_date)
        print(f"  {symbol}: {'可用' if available else '不可用'}")
    
    # 测试单个股票数据获取
    print("\n2. 测试单个股票数据获取:")
    for symbol in symbols:
        print(f"\n获取 {symbol} 的数据:")
        bars = provider.get_historical_bars(symbol, test_date, 20)
        print(f"  获取到 {len(bars)} 个bar")
        
        if bars:
            first_bar = bars[0]
            last_bar = bars[-1]
            print(f"  第一个bar: {first_bar.datetime} - 价格: {first_bar.close_price}")
            print(f"  最后一个bar: {last_bar.datetime} - 价格: {last_bar.close_price}")
            print(f"  时间范围: {first_bar.datetime.time()} 到 {last_bar.datetime.time()}")
    
    # 测试批量数据获取
    print("\n3. 测试批量数据获取:")
    all_data = provider.get_multiple_symbols_data(symbols, test_date, 20)
    for symbol, bars in all_data.items():
        print(f"  {symbol}: {len(bars)} 个bar")
    
    # 测试缓存功能
    print("\n4. 测试缓存功能:")
    cache_info = provider.get_cache_info()
    print(f"  缓存信息: {cache_info}")
    
    # 测试HFTBBReversalIndicatorV2与真实数据
    print("\n5. 测试HFTBBReversalIndicatorV2与真实数据:")
    from hft_bb_indicators import HFTBBReversalIndicatorV2
    
    for symbol in symbols:
        print(f"\n测试 {symbol}:")
        indicator = HFTBBReversalIndicatorV2(symbol, size=20, bb_period=20)
        
        # 获取历史数据
        historical_bars = provider.get_historical_bars(symbol, test_date, 20)
        print(f"  获取到 {len(historical_bars)} 个历史bar")
        
        if len(historical_bars) >= 20:
            # 预加载历史数据
            indicator.preload_historical_bars(historical_bars)
            print(f"  预加载完成: {indicator.is_preloaded}")
            print(f"  准备交易: {indicator.is_ready_for_trading()}")
            print(f"  已初始化: {indicator.is_inited()}")
            
            # 获取BB水平
            bb_levels = indicator.get_bb_levels()
            print(f"  BB水平: {bb_levels}")
            
            # 获取指标
            indicators = indicator.get_indicators()
            print(f"  指标: SMA={indicators.get('sma', 0):.2f}, STD={indicators.get('std', 0):.2f}")
        else:
            print(f"  数据不足，需要至少20个bar，实际只有{len(historical_bars)}个")

if __name__ == "__main__":
    test_real_data()
