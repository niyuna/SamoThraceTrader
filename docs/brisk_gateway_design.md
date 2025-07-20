# Brisk Gateway 设计文档

## 概述

BriskGateway是基于vnpy框架开发的日股券商gateway，用于连接brisk tick_server并接收日股tick数据。该gateway支持实时数据接收和历史数据回放功能。

## 架构设计

### 1. 整体架构

```
┌─────────────────┐    WebSocket    ┌─────────────────┐    HTTP POST    ┌─────────────────┐
│   BriskGateway  │ ◄──────────────► │   tick_server   │ ◄──────────────► │   数据源        │
│   (vnpy)        │                 │   (FastAPI)     │                 │   (brisk)       │
└─────────────────┘                 └─────────────────┘                 └─────────────────┘
         │                                   │                                   │
         │                                   │                                   │
         ▼                                   ▼                                   ▼
┌─────────────────┐                 ┌─────────────────┐                 ┌─────────────────┐
│   本地文件存储   │                 │   内存缓存       │                 │   实时数据流     │
│   (历史数据)     │                 │   (实时数据)     │                 │   (tick数据)     │
└─────────────────┘                 └─────────────────┘                 └─────────────────┘
```

### 2. 数据流

1. **实时数据流**：
   - 数据源 → tick_server → WebSocket → BriskGateway → vnpy事件系统
   
2. **历史数据流**：
   - 本地文件 → BriskGateway → vnpy事件系统

3. **数据存储**：
   - tick_server将接收到的数据同时存储到内存和本地文件

## 核心功能

### 1. 实时数据接收

- **WebSocket连接**：与tick_server建立WebSocket连接
- **自动重连**：连接断开时自动重连
- **心跳检测**：定期发送心跳包保持连接
- **数据转换**：将brisk的Frame格式转换为vnpy的TickData格式

### 2. 历史数据回放

- **文件读取**：从tick_server存储的本地文件读取历史数据
- **时间同步**：按原始时间戳顺序回放数据
- **速度控制**：支持调整回放速度
- **选择性回放**：支持指定股票代码进行回放

### 3. 数据格式转换

**Brisk Frame格式**：
```json
{
    "frameNumber": 1,
    "price10": 1500,
    "quantity": 100,
    "timestamp": 1701234567,
    "type": 1
}
```

**vnpy TickData格式**：
```python
TickData(
    symbol="7203",
    exchange=Exchange.TSE,
    datetime=datetime(...),
    last_price=150.0,  # price10 / 10
    last_volume=100,
    volume=100,
    gateway_name="BRISK"
)
```

## 配置参数

### Gateway配置

```python
setting = {
    "tick_server_url": "ws://127.0.0.1:8001/ws",          # WebSocket地址
    "tick_server_http_url": "http://127.0.0.1:8001",      # HTTP地址
    "frames_output_dir": "D:\\dev\\github\\brisk-hack\\brisk_in_day_frames",  # 数据文件目录
    "reconnect_interval": 5,                               # 重连间隔(秒)
    "heartbeat_interval": 30,                              # 心跳间隔(秒)
    "max_reconnect_attempts": 10,                          # 最大重连次数
    "replay_speed": 1.0,                                   # 回放速度倍数
}
```

## 使用方法

### 1. 基本使用

```python
from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.object import SubscribeRequest
from vnpy.trader.constant import Exchange
from vnpy.trader.gateway.brisk_gateway import BriskGateway

# 创建引擎
event_engine = EventEngine()
main_engine = MainEngine(event_engine)

# 添加Gateway
main_engine.add_gateway(BriskGateway)

# 连接配置
setting = {
    "tick_server_url": "ws://127.0.0.1:8001/ws",
    "tick_server_http_url": "http://127.0.0.1:8001",
    "frames_output_dir": "D:\\dev\\github\\brisk-hack\\brisk_in_day_frames",
}

# 连接Gateway
main_engine.connect(setting, "BRISK")

# 订阅股票
req = SubscribeRequest(symbol="7203", exchange=Exchange.TSE)
main_engine.subscribe(req, "BRISK")
```

### 2. 历史数据回放

```python
# 获取Gateway实例
gateway = main_engine.get_gateway("BRISK")

# 开始回放
gateway.start_replay("20241201", ["7203", "6758"])

# 停止回放
gateway.stop_replay()
```

### 3. 事件处理

```python
def on_tick(tick):
    print(f"收到Tick: {tick.symbol} - 价格: {tick.last_price}")

def on_log(log):
    print(f"日志: {log.msg}")

# 注册事件处理函数
event_engine.register("eTick", on_tick)
event_engine.register("eLog", on_log)
```

## 设计优势

### 1. 实时性
- WebSocket连接确保数据实时推送
- 最小化数据延迟

### 2. 可靠性
- 自动重连机制
- 心跳检测
- 本地文件备份

### 3. 灵活性
- 支持实时和历史数据
- 可配置的回放速度
- 选择性数据订阅

### 4. 扩展性
- 基于vnpy框架，易于集成
- 模块化设计，便于维护

## 改进建议

### 1. 性能优化
- 实现数据批量处理
- 添加数据压缩
- 优化内存使用

### 2. 功能增强
- 支持更多数据格式
- 添加数据质量监控
- 实现数据过滤功能

### 3. 监控和日志
- 添加详细的性能监控
- 实现数据统计功能
- 增强错误处理

### 4. 配置管理
- 支持动态配置更新
- 添加配置验证
- 实现配置热重载

## 部署说明

### 1. 环境要求
- Python 3.8+
- vnpy框架
- websockets库
- aiohttp库

### 2. 启动步骤
1. 启动tick_server
2. 配置Gateway参数
3. 运行Gateway
4. 订阅所需股票

### 3. 注意事项
- 确保tick_server正常运行
- 检查网络连接
- 验证数据文件路径
- 监控系统资源使用

## 总结

BriskGateway设计合理，实现了实时数据接收和历史数据回放的核心功能。通过WebSocket连接和本地文件存储，既保证了数据的实时性，又提供了历史数据的回放能力。该设计具有良好的扩展性和维护性，为日股交易系统提供了可靠的数据基础。 