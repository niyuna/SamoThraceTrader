# HFT BB Reversal Strategy 测试

这个目录包含了所有与HFT BB Reversal策略相关的测试文件。

## 测试文件说明

### 核心数据结构测试
- `test_trigger_levels.py` - 测试TriggerLevels数据结构
- `test_hft_bb_stock_context.py` - 测试HFTBBStockContext数据结构

### 核心功能测试
- `test_trigger_calculation.py` - 测试触发价格计算方法
- `test_on_1min_bar.py` - 测试1分钟K线处理方法
- `test_on_tick.py` - 测试Tick数据处理方法
- `test_entry_logic.py` - 测试入场逻辑检查

### 集成测试
- `test_hft_bb_complete.py` - 完整的HFT BB策略集成测试
- `test_x_condition.py` - 测试X条件逻辑

## 运行测试

### 运行所有HFT BB测试
```bash
cd brisk/test/hft_bb
python run_all_hft_bb_tests.py
```

### 运行单个测试文件
```bash
cd brisk/test/hft_bb
python test_trigger_levels.py
python test_hft_bb_stock_context.py
python test_trigger_calculation.py
python test_on_1min_bar.py
python test_on_tick.py
python test_entry_logic.py
python test_hft_bb_complete.py
python test_x_condition.py
```

### 从项目根目录运行
```bash
# 运行所有HFT BB测试
python -m brisk.test.hft_bb.run_all_hft_bb_tests

# 运行单个测试
python -m brisk.test.hft_bb.test_trigger_levels
```

## 测试覆盖范围

### 已完成的测试
- ✅ TriggerLevels数据结构
- ✅ HFTBBStockContext数据结构
- ✅ 触发价格计算
- ✅ 1分钟K线处理
- ✅ Tick数据处理
- ✅ 入场逻辑检查
- ✅ X条件逻辑

### 待完成的测试
- ⏳ 订单发送和取消方法
- ⏳ 订单成交处理
- ⏳ 出场订单管理
- ⏳ 辅助方法
- ⏳ 完整策略集成测试

## 测试原则

1. **单元测试**: 每个方法都有对应的单元测试
2. **集成测试**: 测试各个组件之间的交互
3. **边界测试**: 测试各种边界条件和异常情况
4. **Mock测试**: 使用Mock对象隔离外部依赖
5. **状态测试**: 验证状态转换的正确性

## 注意事项

- 所有测试都使用Mock对象，不会实际连接交易网关
- 测试数据使用模拟的BarData和TickData
- 确保在运行测试前已正确设置Python路径
- 测试结果会显示详细的成功/失败统计信息
