#!/usr/bin/env python3
"""
演示StockConfigManager支持逗号分隔的股票代码功能
"""

import sys
import os

# 添加brisk目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from stock_config import StockConfigManager


def demo_comma_separated_config():
    """演示逗号分隔的股票代码配置功能"""
    
    print("=== StockConfigManager 逗号分隔股票代码功能演示 ===\n")
    
    # 使用示例配置文件
    config_file = "brisk/configs/stock_configs_comma_example.json"
    manager = StockConfigManager(config_file)
    
    print("1. 单个股票代码配置:")
    print("   999Z 的配置:")
    config_999z = manager.get_stock_config("999Z")
    if config_999z:
        print(f"   - 入场标准差倍数: {config_999z.bb_entry_std_multiplier}")
        print(f"   - 出场标准差倍数: {config_999z.bb_exit_std_multiplier}")
        print(f"   - 交易窗口数量: {len(config_999z.trading_windows)}")
        print(f"   - 排除分钟数量: {len(config_999z.exclude_minutes)}")
    else:
        print("   未找到配置")
    
    print("\n2. 逗号分隔的多个股票代码配置:")
    print("   999Y,999A,999B 共享相同配置:")
    for symbol in ["999Y", "999A", "999B"]:
        config = manager.get_stock_config(symbol)
        if config:
            print(f"   {symbol}:")
            print(f"   - 入场标准差倍数: {config.bb_entry_std_multiplier}")
            print(f"   - 出场标准差倍数: {config.bb_exit_std_multiplier}")
            print(f"   - 交易窗口数量: {len(config.trading_windows)}")
            print(f"   - 排除分钟数量: {len(config.exclude_minutes)}")
        else:
            print(f"   {symbol}: 未找到配置")
    
    print("\n3. 另一组逗号分隔的股票代码配置:")
    print("   8593,7272,2330 共享相同配置:")
    for symbol in ["8593", "7272", "2330"]:
        config = manager.get_stock_config(symbol)
        if config:
            print(f"   {symbol}:")
            print(f"   - 入场标准差倍数: {config.bb_entry_std_multiplier}")
            print(f"   - 出场标准差倍数: {config.bb_exit_std_multiplier}")
            print(f"   - 交易窗口数量: {len(config.trading_windows)}")
            print(f"   - 排除分钟数量: {len(config.exclude_minutes)}")
        else:
            print(f"   {symbol}: 未找到配置")
    
    print("\n4. 检查配置是否存在:")
    test_symbols = ["999Z", "999Y", "999A", "999B", "8593", "7272", "2330", "9984", "6098", "999X"]
    for symbol in test_symbols:
        has_config = manager.has_custom_config(symbol)
        print(f"   {symbol}: {'有配置' if has_config else '无配置'}")
    
    print("\n5. 配置统计:")
    print(f"   总共加载了 {len(manager.stock_configs)} 个股票配置")
    print("   配置的股票代码:")
    for symbol in sorted(manager.stock_configs.keys()):
        print(f"   - {symbol}")


if __name__ == "__main__":
    demo_comma_separated_config()
