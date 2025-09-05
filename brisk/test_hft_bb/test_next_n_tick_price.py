#!/usr/bin/env python3
"""测试next_n_tick_price函数的行为"""

from common.trading_common import next_n_tick_price

# 测试9984（在topix500中）
print("测试9984（在topix500中）:")
print(f"next_n_tick_price(3, '9984', 100.5, False): {next_n_tick_price(3, '9984', 100.5, False)}")
print(f"next_n_tick_price(3, '9984', 99.5, True): {next_n_tick_price(3, '9984', 99.5, True)}")

# 测试2330（不在topix500中）
print("\n测试2330（不在topix500中）:")
print(f"next_n_tick_price(3, '2330', 100.5, False): {next_n_tick_price(3, '2330', 100.5, False)}")
print(f"next_n_tick_price(3, '2330', 99.5, True): {next_n_tick_price(3, '2330', 99.5, True)}")
