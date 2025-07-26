# Mock Brisk Gateway 使用说明

## 概述

Mock Brisk Gateway 是一个专为测试设计的模拟网关，支持两种tick数据模式：
1. **Mock Tick模式**: 生成模拟的tick数据
2. **Replay模式**: 回放真实的历史数据

交易功能完全Mock化，确保测试安全。

## 功能特性

- ✅ 支持Mock tick数据生成
- ✅ 支持历史数据回放（只发送已订阅股票的tick数据）
- ✅ 完全Mock化的交易功能
- ✅ 可配置的账户和持仓
- ✅ 模拟手续费和滑点
- ✅ 线程安全设计
- ✅ 与vnpy框架完全兼容

## 配置说明

### 基本配置

```python
setting = {
    # Tick数据模式: "mock" 或 "replay"
    "tick_mode": "mock",
    
    # Mock交易配置
    "mock_account_balance": 10000000,  # 账户余额
    "mock_commission_rate": 0.001,     # 手续费率
    "mock_slippage": 0.0,              # 滑点
    "mock_fill_delay": 0.1,            # 成交延迟(秒)
}
```

### Mock Tick模式配置

```python
setting = {
    "tick_mode": "mock",
    
    # Mock Tick配置
    "mock_tick_interval": 1.0,         # Tick间隔(秒)
    "mock_price_volatility": 0.01,     # 价格波动率
    "mock_volume_range": (100, 1000),  # 成交量范围
    "mock_base_prices": {              # 基准价格
        "7203": 2500.0,  # 丰田
        "6758": 1800.0,  # 索尼
        "9984": 8000.0,  # 软银
    },
}
```

### Replay模式配置

```python
setting = {
    "tick_mode": "replay",
    
    # Replay配置
    "replay_data_dir": "D:\\dev\\github\\brisk-hack\\brisk_in_day_frames",
    "replay_date": "20241201",         # 回放日期
    "replay_speed": 10.0,              # 回放速度倍数
}
```

**重要说明**：
1. **数据加载**：Mock Gateway会加载指定日期的所有股票数据
2. **订阅过滤**：只向策略发送已订阅股票的tick数据
3. **简化配置**：不需要指定`replay_symbols`，通过`subscribe`方法控制要接收的股票
4. **行为一致性**：与真实Gateway的行为保持一致

## 使用方法

### 1. 基本使用

```python
from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.object import SubscribeRequest, Exchange
from mock_brisk_gateway import MockBriskGateway

# 创建引擎
event_engine = EventEngine()
main_engine = MainEngine(event_engine)

# 添加Mock Gateway
main_engine.add_gateway(MockBriskGateway)
mock_gateway = main_engine.get_gateway("MOCK_BRISK")

# 配置
setting = {
    "tick_mode": "mock",
    "mock_tick_interval": 0.5,
    "mock_base_prices": {"7203": 2500.0},
    "mock_account_balance": 10000000,
}

# 连接
main_engine.connect(setting, "MOCK_BRISK")

# 订阅股票
req = SubscribeRequest(symbol="7203", exchange=Exchange.TSE)
main_engine.subscribe(req, "MOCK_BRISK")
```

### 2. 策略测试使用

```python
# 在策略中使用Mock Gateway
def setup_strategy(self):
    """设置策略"""
    event_engine = EventEngine()
    main_engine = MainEngine(event_engine)
    
    # 添加Mock Gateway
    main_engine.add_gateway(MockBriskGateway)
    self.mock_gateway = main_engine.get_gateway("MOCK_BRISK")
    
    # 配置Mock模式
    setting = {
        "tick_mode": "mock",
        "mock_tick_interval": 0.1,     # 快速生成tick
        "mock_base_prices": {
            "7203": 2500.0,
            "6758": 1800.0,
        },
        "mock_account_balance": 10000000,
    }
    
    main_engine.connect(setting, "MOCK_BRISK")
```

### 3. 历史数据回测

```python
# 使用历史数据回放
setting = {
    "tick_mode": "replay",
    "replay_data_dir": "D:\\dev\\github\\brisk-hack\\brisk_in_day_frames",
    "replay_date": "20241201",
    "replay_speed": 10.0,              # 10倍速回放
    "replay_symbols": ["7203", "6758"],
    "mock_account_balance": 10000000,
}
```

## 测试专用方法

Mock Gateway 提供了一些测试专用的方法：

```python
# 获取Mock状态
positions = mock_gateway.get_mock_positions()
account = mock_gateway.get_mock_account()

# 重置Mock状态
mock_gateway.reset_mock_state()

# 控制回放
mock_gateway.pause_replay()
mock_gateway.resume_replay()

# 设置自定义数据（预留接口）
mock_gateway.set_mock_tick_data("7203", custom_tick_data)
mock_gateway.set_mock_order_response("order_id", response_data)
```

## 事件处理

Mock Gateway 会推送以下事件：

- `EVENT_TICK`: Tick数据事件
- `EVENT_ORDER`: 订单事件
- `EVENT_TRADE`: 成交事件
- `EVENT_ACCOUNT`: 账户事件
- `EVENT_POSITION`: 持仓事件
- `EVENT_LOG`: 日志事件

```python
def on_tick(event):
    tick = event.data
    print(f"收到Tick: {tick.symbol} - 价格: {tick.last_price}")

def on_order(event):
    order = event.data
    print(f"收到订单: {order.symbol} - 状态: {order.status}")

# 注册事件处理函数
event_engine.register(EVENT_TICK, on_tick)
event_engine.register(EVENT_ORDER, on_order)
```

## 运行测试

### 1. 运行Mock Tick测试

```bash
# 激活虚拟环境
..\venv\Scripts\Activate.ps1

# 运行测试
python test_mock_gateway.py
```

### 2. 在VWAP Failure策略测试中使用

```python
# 修改test_vwap_failure_step1.py中的setup_strategy方法
def setup_strategy(self):
    """设置策略"""
    event_engine = EventEngine()
    main_engine = MainEngine(event_engine)
    
    # 使用Mock Gateway替代BriskGateway
    main_engine.add_gateway(MockBriskGateway)
    self.mock_gateway = main_engine.get_gateway("MOCK_BRISK")
    
    # 配置Mock模式
    setting = {
        "tick_mode": "mock",
        "mock_tick_interval": 0.1,
        "mock_base_prices": {
            "7203": 2500.0,
            "6758": 1800.0,
        },
        "mock_account_balance": 10000000,
    }
    
    main_engine.connect(setting, "MOCK_BRISK")
```

## 注意事项

1. **数据文件路径**: 使用Replay模式时，确保数据文件路径正确
2. **日期格式**: 回放日期格式为 "YYYYMMDD"
3. **股票代码**: 确保股票代码与数据文件中的代码一致
4. **内存使用**: 大量历史数据回放时注意内存使用
5. **线程安全**: 所有操作都是线程安全的

## 故障排除

### 1. 无法连接
- 检查配置参数是否正确
- 确认数据文件路径存在（Replay模式）

### 2. 没有收到Tick数据
- 检查是否已订阅股票
- 确认tick_mode配置正确
- 查看日志输出

### 3. 订单不成交
- 检查订单类型（市价单通常立即成交）
- 确认账户余额充足
- 查看成交延迟设置

## 扩展功能

Mock Gateway 设计为可扩展的，可以轻松添加新功能：

1. **自定义价格模型**: 修改MockTickGenerator中的价格生成逻辑
2. **复杂成交逻辑**: 在MockTradingEngine中添加更复杂的成交规则
3. **风险控制**: 添加仓位限制、风险检查等功能
4. **数据源扩展**: 支持其他格式的历史数据

## 版本历史

- v1.0.0: 初始版本，支持Mock Tick和Replay模式
- 支持基本的交易功能Mock
- 提供测试专用接口 