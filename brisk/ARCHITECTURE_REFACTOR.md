# 架构重构说明

## 重构目标

1. **BriskGateway专注于实时数据连接**：移除回放功能，专注于WebSocket实时数据接收
2. **回放功能由Gateway自己实现**：每个Gateway根据自己的特点实现回放功能
3. **Strategy类通过统一接口调用Gateway**：Strategy不应该理解Gateway内部实现，而是通过标准接口调用

## 重构内容

### 1. BriskGateway重构

**移除的功能：**
- `start_replay()` 方法
- `stop_replay()` 方法
- `_load_replay_data()` 方法
- `_run_replay()` 方法
- 所有回放相关的成员变量和配置

**保留的功能：**
- WebSocket实时数据连接
- 实时tick数据处理
- 基础交易接口（send_order, cancel_order等）

### 2. IntradayStrategyBase重构

**改进的接口设计：**
```python
def start_replay(self, date: str, symbols: list = None):
    """开始历史数据回放"""
    if hasattr(self.gateway, 'start_replay'):
        self.gateway.start_replay(date, symbols)
        print(f"开始回放 {date} 的历史数据")
    else:
        print(f"当前Gateway不支持回放功能")

def stop_replay(self):
    """停止历史数据回放"""
    if hasattr(self.gateway, 'stop_replay'):
        self.gateway.stop_replay()
        print("停止历史数据回放")
    else:
        print("当前Gateway不支持回放功能")
```

**设计原则：**
- 使用`hasattr()`检查Gateway是否支持特定功能
- Strategy不关心Gateway的具体实现
- 通过统一的接口调用Gateway方法

### 3. VWAPFailureStrategy重构

**移除的功能：**
- 所有mock交易方法（`_place_mock_order`, `_update_mock_order`等）
- 对Gateway内部实现的直接依赖

**改进的功能：**
- 使用Mock Gateway的标准交易接口
- 通过`self.gateway.send_order()`发送订单
- 通过`self.gateway_name`获取Gateway名称

## 架构优势

### 1. 职责分离
- **BriskGateway**：专注于实时数据连接
- **MockBriskGateway**：提供Mock数据和回放功能
- **Strategy**：专注于策略逻辑，不关心数据来源

### 2. 接口统一
- 所有Gateway都实现相同的接口
- Strategy通过统一接口调用Gateway功能
- 支持功能检查，优雅处理不支持的功能

### 3. 可扩展性
- 可以轻松添加新的Gateway类型
- 每个Gateway可以有自己的特色功能
- Strategy可以无缝切换不同的Gateway

### 4. 测试友好
- Mock Gateway提供完整的测试环境
- 支持Mock Tick和Replay两种模式
- 交易功能完全Mock化，安全可靠

## 使用示例

### 使用Mock Gateway Replay模式
```python
strategy = VWAPFailureStrategy(use_mock_gateway=True)
mock_setting = {
    "tick_mode": "replay",
    "replay_data_dir": "path/to/data",
    "replay_date": "20241201",
    "replay_speed": 20.0,
}
strategy.connect(mock_setting)
```

### 使用Mock Gateway Mock Tick模式
```python
strategy = VWAPFailureStrategy(use_mock_gateway=True)
mock_setting = {
    "tick_mode": "mock",
    "mock_tick_interval": 1.0,
    "mock_price_volatility": 0.01,
    "mock_base_prices": {"7203": 1000.0},
}
strategy.connect(mock_setting)
```

### 使用真实Brisk Gateway
```python
strategy = VWAPFailureStrategy(use_mock_gateway=False)
brisk_setting = {
    "tick_server_url": "ws://127.0.0.1:8001/ws",
    "tick_server_http_url": "http://127.0.0.1:8001",
}
strategy.connect(brisk_setting)
```

## 测试文件

- `test_refactored_architecture.py`：测试重构后的架构
- `test_vwap_failure_mock.py`：测试VWAP Failure策略使用Mock Gateway

## 总结

重构后的架构更加清晰、模块化，符合单一职责原则和依赖倒置原则。Strategy类不再依赖具体的Gateway实现，而是通过统一的接口进行交互，大大提高了代码的可维护性和可扩展性。 