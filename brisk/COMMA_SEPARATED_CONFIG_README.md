# StockConfigManager 逗号分隔股票代码功能

## 概述

`StockConfigManager` 现在支持在配置文件中使用逗号分隔的股票代码，这样同一个配置可以应用到多个股票上。这大大简化了配置管理，特别是当多个股票需要相同配置时。

## 功能特性

- **逗号分隔支持**: 在配置文件的键中使用逗号分隔多个股票代码
- **自动分割**: 系统会自动将逗号分隔的字符串分割为多个独立的股票代码
- **空格处理**: 自动去除股票代码前后的空格
- **向后兼容**: 完全兼容现有的单个股票代码配置
- **混合配置**: 可以在同一个配置文件中混合使用单个和逗号分隔的股票代码

## 使用方法

### 1. JSON 配置文件示例

```json
{
  "999Z": {
    "bb_entry_std_multiplier": 2.5,
    "bb_exit_std_multiplier": 1.8,
    "trading_windows": [
      {
        "start_time": "09:30",
        "end_time": "11:30",
        "allowed_directions": ["long", "short"]
      }
    ],
    "exclude_minutes": ["12:00", "15:00"]
  },
  "999Y,999A,999B": {
    "bb_entry_std_multiplier": 3.0,
    "bb_exit_std_multiplier": 2.0,
    "trading_windows": [
      {
        "start_time": "09:30",
        "end_time": "11:00",
        "allowed_directions": ["short"]
      },
      {
        "start_time": "14:00",
        "end_time": "15:25",
        "allowed_directions": ["long", "short"]
      }
    ],
    "exclude_minutes": ["12:00", "15:00"]
  },
  "8593,7272,2330": {
    "bb_entry_std_multiplier": 3.0,
    "bb_exit_std_multiplier": -0.5,
    "trading_windows": [
      {
        "start_time": "10:00",
        "end_time": "15:25",
        "allowed_directions": ["long"]
      }
    ],
    "exclude_minutes": ["12:30", "13:00", "14:00", "14:30", "15:00"]
  }
}
```

### 2. 代码使用示例

```python
from stock_config import StockConfigManager

# 加载配置文件
manager = StockConfigManager("configs/stock_configs.json")

# 获取单个股票配置
config_999z = manager.get_stock_config("999Z")
print(f"999Z 入场标准差倍数: {config_999z.bb_entry_std_multiplier}")

# 获取逗号分隔的股票配置
for symbol in ["999Y", "999A", "999B"]:
    config = manager.get_stock_config(symbol)
    print(f"{symbol} 入场标准差倍数: {config.bb_entry_std_multiplier}")

# 检查配置是否存在
print(f"999Y 有配置: {manager.has_custom_config('999Y')}")
print(f"999X 有配置: {manager.has_custom_config('999X')}")
```

## 配置处理逻辑

1. **键解析**: 系统检查配置键是否包含逗号
2. **分割处理**: 如果包含逗号，则按逗号分割并去除空格
3. **配置复制**: 为每个分割后的股票代码创建相同的配置对象
4. **独立存储**: 每个股票代码都有独立的配置条目

## 示例输出

当加载上述配置文件时，系统会输出：

```
Loading config for ['999Z']
Loading config for ['999Y', '999A', '999B']
Loading config for ['8593', '7272', '2330']
```

最终会创建以下股票配置：
- 999Z (单独配置)
- 999Y, 999A, 999B (共享配置)
- 8593, 7272, 2330 (共享配置)

## 注意事项

1. **空格处理**: 系统会自动去除股票代码前后的空格，所以 `" 999A , 999B "` 会被正确处理为 `["999A", "999B"]`
2. **配置一致性**: 逗号分隔的股票代码会共享完全相同的配置，包括所有参数
3. **向后兼容**: 现有的单个股票代码配置完全不受影响
4. **错误处理**: 如果配置文件格式错误，系统会输出警告但不会崩溃

## 测试

运行测试来验证功能：

```bash
python brisk/test/test_stock_config_comma_separated.py
```

运行演示脚本：

```bash
python brisk/demo_comma_separated_config.py
```
