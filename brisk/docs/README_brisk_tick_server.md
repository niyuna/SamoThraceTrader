# Brisk 模块说明

## 概述

Brisk模块是一个基于FastAPI的Web服务，用于处理实时交易数据。它提供了REST API接口来接收和查询交易帧数据。

## 功能特性

- **实时数据处理**: 接收和处理实时交易帧数据
- **数据存储**: 将数据保存到JSON文件
- **内存缓存**: 使用线程安全的缓存机制
- **REST API**: 提供HTTP接口进行数据查询
- **CORS支持**: 支持跨域请求

## 依赖要求

- fastapi 0.116.1+
- uvicorn 0.35.0+
- pydantic 2.11.7+
- loguru 0.7.3+

## 启动服务

### 方法1: 使用批处理文件（推荐）
```bash
# 在brisk目录下
launch_tick_server_venv.bat
```

### 方法2: 使用PowerShell脚本
```powershell
# 在brisk目录下
.\launch_tick_server_venv.ps1
```

### 方法3: 手动启动
```bash
# 激活虚拟环境
..\venv\Scripts\Activate.ps1

# 启动服务
uvicorn tick_server:app --host=0.0.0.0 --port=8001 --log-level info
```

## API接口

### 1. 获取帧数据
```
GET /inDayFrames/{ts}/{max_frames}
```
- `ts`: 时间戳
- `max_frames`: 最大帧数

### 2. 提交帧数据
```
POST /inDayFrames
```
- 请求体: 包含帧数据的JSON对象

### 3. 提交元数据
```
POST /metadata/
```
- 请求体: 键值对数据

### 4. 获取元数据
```
GET /metadata/{key}
```
- `key`: 元数据键名

## 配置

### 环境变量
- `FRAMES_OUTPUT_DIR`: 帧数据输出目录（默认: `D:\dev\github\brisk-hack\brisk_in_day_frames`）

### 日志配置
- 日志文件: `C:\dev\relay_lightweight.log`
- 日志轮转: 每天08:00
- 压缩格式: ZIP

## 文件结构

```
brisk/
├── tick_server.py          # 主服务文件
├── logging_config.py       # 日志配置
├── launch_tick_server.bat  # 原始启动脚本
├── launch_tick_server_venv.bat  # 虚拟环境启动脚本
├── launch_tick_server_venv.ps1  # PowerShell启动脚本
└── README.md              # 本说明文件
```

## 使用示例

### 启动服务
```bash
cd brisk
launch_tick_server_venv.bat
```

### 测试API
```bash
# 获取帧数据
curl http://localhost:8001/inDayFrames/20240101/100

# 提交元数据
curl -X POST http://localhost:8001/metadata/ \
  -H "Content-Type: application/json" \
  -d '{"key": "value"}'
```

## 注意事项

1. **端口**: 服务默认运行在8001端口
2. **数据目录**: 确保输出目录有写入权限
3. **日志文件**: 确保日志文件路径可写
4. **虚拟环境**: 使用项目配置的虚拟环境运行

## 故障排除

1. **端口占用**: 如果8001端口被占用，可以修改启动脚本中的端口号
2. **权限问题**: 确保有足够的文件系统权限
3. **依赖问题**: 确保所有依赖都已正确安装 