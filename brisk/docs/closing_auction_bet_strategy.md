# Closing Auction Bet Strategy

收盘竞价策略 - 在收盘竞价前建仓，竞价内平仓的日内交易策略

## 策略概述

这是一个基于时间窗口的日内交易策略，专门针对日股的收盘竞价（Closing Auction）设计。策略在收盘竞价开始前建仓，在竞价内平仓，利用收盘竞价的价格发现机制获取收益。

## 核心特性

### 1. 时间驱动
- **14:50前**: 策略不初始化，节省计算资源
- **15:00**: 记录1分钟K线close price作为base price
- **15:22-15:25**: 建仓窗口，监控触发价格
- **15:25后**: 平仓窗口，使用market单平仓

### 2. 价格机制
- **Base Price**: 15:00的1分钟K线close price（如果15:00没有成交，使用15:00后第一根有成交的K线）
- **目标价格**:
  - 做多: `base_price * long_multiplier` (默认0.995)
  - 做空: `base_price * short_multiplier` (默认1.0055)
- **触发价格**:
  - 做多: `target_price + 3个tick`
  - 做空: `target_price - 3个tick`

### 3. 交易逻辑
- 使用触发价格机制，避免在不利价格建仓
- 当tick价格达到触发价格时发送limit单
- 当tick价格远离触发价格时取消订单
- 在15:25后使用market单平仓

## 文件结构

```
brisk/
├── closing_auction_bet_strategy.py          # 主策略文件
├── test/
│   ├── test_closing_auction_bet.py          # 测试脚本
│   └── demo_closing_auction_bet.py          # 演示脚本
├── docs/
│   └── closing_auction_bet_strategy.md      # 本文档
└── config/strategies/
    └── closing_auction_bet_strategy.yaml    # 策略配置文件
```

## 配置参数

策略参数通过YAML配置文件管理，支持动态调整：

```yaml
params:
  long_multiplier: 0.995      # 做多目标价格倍数
  short_multiplier: 1.0055    # 做空目标价格倍数
  trigger_tick_count: 3       # 触发价格距离目标价格的tick数量
  position_size: 100          # 每只股票的持仓数量
  entry_start_time: "15:22"   # 建仓开始时间
  entry_end_time: "15:25"     # 建仓结束时间
  exit_start_time: "15:25"    # 平仓开始时间
  strategy_init_time: "14:50" # 策略初始化时间
```

## 使用方法

### 1. 基本使用

```python
from closing_auction_bet_strategy import ClosingAuctionBetStrategy
from common.trading_common import topix500

# 创建策略实例
strategy = ClosingAuctionBetStrategy(
    use_mock_gateway=False, 
    gateway_type="brisk_eshiten"
)

# 启动策略
strategy.start()

# 订阅股票
for symbol in topix500:
    strategy.subscribe(symbol)

# 设置策略为已初始化
strategy.strategy_initialized = True
```

### 2. 直接运行

```bash
# 确保BriskEshitenGateway正常运行
python closing_auction_bet_strategy.py
```

### 3. 测试和演示

```bash
# 运行测试
python brisk/test/test_closing_auction_bet.py

# 运行演示
python brisk/test/demo_closing_auction_bet.py
```

## 策略状态

策略提供状态监控功能：

```python
status = strategy.get_strategy_status()
print(f"策略初始化: {status['strategy_initialized']}")
print(f"建仓窗口活跃: {status['entry_window_active']}")
print(f"平仓窗口活跃: {status['exit_window_active']}")
print(f"总股票数量: {status['total_symbols']}")
print(f"活跃持仓: {status['active_positions']}")
print(f"待处理订单: {status['pending_orders']}")
```

## 技术架构

### 继承关系
- 继承自 `IntradayStrategyBase`
- 复用现有的gateway连接、订单管理、事件处理等基础设施

### Gateway选择
- 使用 `BriskEshitenGateway`（避免brisk gateway的API配额限制）
- 支持mock模式用于测试

### 状态管理
- 使用简化的状态机：`IDLE` -> `WAITING_ENTRY` -> `HOLDING` -> `WAITING_EXIT`
- 每个股票维护独立的Context

## 风险控制

1. **触发价格机制**: 避免在不利价格建仓
2. **时间窗口限制**: 严格按时间窗口执行
3. **订单管理**: 及时取消未成交订单
4. **Market单平仓**: 确保在竞价内完成平仓

## 与HFT BB策略的对比

| 特性 | HFT BB策略 | Closing Auction Bet策略 |
|------|------------|------------------------|
| 信号来源 | 布林带 + X条件 | 时间窗口 |
| 技术指标 | 复杂（BB, ATR等） | 无 |
| 交易时间 | 全天 | 15:22-15:25 |
| 平仓方式 | 技术信号 | 时间驱动 |
| 复杂度 | 高 | 低 |
| 资源消耗 | 高 | 低 |

## 注意事项

1. **时间同步**: 确保系统时间准确
2. **Gateway连接**: 确保BriskEshitenGateway正常运行
3. **市场时间**: 策略仅在日本股市交易时间内有效
4. **参数调整**: 根据市场情况调整价格倍数和触发tick数量

## 扩展性

策略设计具有良好的扩展性：

1. **参数调整**: 通过YAML配置文件动态调整参数
2. **时间窗口**: 可以调整建仓和平仓时间窗口
3. **触发机制**: 可以调整触发价格的计算方式
4. **股票筛选**: 可以添加股票筛选条件

## 测试覆盖

- ✅ 策略初始化测试
- ✅ Context创建测试
- ✅ 价格计算测试
- ✅ 时间窗口逻辑测试
- ✅ 配置加载测试
- ✅ 策略状态测试

## 版本历史

- **v1.0.0**: 初始版本，实现基本的收盘竞价策略功能
