# HFT BB Reversal Strategy 设计文档

## 概述

HFT BB Reversal Strategy 是一个基于布林带反转的高频交易策略，通过复用 `IntradayStrategyBase` 中已有的方法和状态管理，实现高效的订单管理和风险控制。

## 核心设计原则

1. **最大化复用**：尽可能使用 `IntradayStrategyBase` 中已有的方法
2. **状态一致性**：使用 base strategy 中定义的 `StockContext` 结构
3. **订单管理复用**：复用 base strategy 的订单发送、取消、状态管理逻辑
4. **专注策略逻辑**：只实现策略特定的触发价格计算和入场逻辑

## 策略特点

- **延迟触发机制**：入场订单在价格接近触发点时才发送，提高资金效率
- **实时出场管理**：出场订单持续维护，每个1分钟K线更新价格
- **X条件控制**：基于时间窗口和持仓状态的交易条件控制
- **状态机管理**：清晰的订单状态转换和持仓管理

## 文档结构

- [状态机设计](state_machine_design.md) - 详细的状态转换和数据结构
- [交互序列图](interaction_sequences.md) - 各组件间的交互流程
- [API设计](api_design.md) - 新增和修改的方法接口
- [实现指南](implementation_guide.md) - 具体的代码实现步骤

## 快速开始

1. 阅读 [状态机设计](state_machine_design.md) 了解整体架构
2. 查看 [交互序列图](interaction_sequences.md) 理解执行流程
3. 参考 [API设计](api_design.md) 了解方法接口
4. 按照 [实现指南](implementation_guide.md) 进行代码实现