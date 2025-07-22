from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from pydantic import BaseModel

import json
from datetime import datetime, timedelta
import os
import threading
from collections import OrderedDict, defaultdict
import tempfile
import shutil
from collections import defaultdict, deque
from threading import Lock
from typing import Dict, List

import logging
from logging_config import setup_logging
setup_logging()

from loguru import logger
logger.add('C:\\dev\\brisk_tick_server.log', rotation="08:00", compression="zip")

app = FastAPI()
FRAMES_OUTPUT_DIR = os.environ.get('FRAMES_OUTPUT_DIR', 'D:\\dev\\github\\brisk-hack\\brisk_in_day_frames')


shared_vars = {}
shared_vars['active_ws_connection'] = []

origins = [
    "http://localhost:3000",
    "https://sbi.brisk.jp",
    "https://docs.google.com",
    "http://localhost:8888",
    "http://localhost:8080",
    "https://monex.brisk.jp",
    "https://smbcnikko.brisk.jp",
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Frame(BaseModel):
    frameNumber: int
    price10: int
    quantity: int
    timestamp: int
    type: int

# WebSocket连接管理器
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.subscribed_symbols: Dict[WebSocket, set] = {}
        self.lock = Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        with self.lock:
            self.active_connections.append(websocket)
            self.subscribed_symbols[websocket] = set()
        logger.info(f"WebSocket连接建立，当前连接数: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        with self.lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
            if websocket in self.subscribed_symbols:
                del self.subscribed_symbols[websocket]
        logger.info(f"WebSocket连接断开，当前连接数: {len(self.active_connections)}")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"发送个人消息失败: {e}")
            self.disconnect(websocket)

    async def broadcast(self, message: str):
        with self.lock:
            disconnected = []
            for connection in self.active_connections:
                try:
                    await connection.send_text(message)
                except Exception as e:
                    logger.error(f"广播消息失败: {e}")
                    disconnected.append(connection)
            
            # 清理断开的连接
            for connection in disconnected:
                self.disconnect(connection)

    async def broadcast_tick_data(self, frames: Dict[str, List[Frame]]):
        """广播tick数据到所有订阅了相关股票的连接"""
        if not frames:
            return
            
        message = {
            "type": "tick_data",
            "frames": frames,
            "timestamp": datetime.now().isoformat()
        }
        
        with self.lock:
            disconnected = []
            for connection in self.active_connections:
                try:
                    # 检查连接是否订阅了相关股票
                    subscribed = self.subscribed_symbols.get(connection, set())
                    relevant_frames = {symbol: frame_list for symbol, frame_list in frames.items() 
                                     if symbol in subscribed or symbol + ".TSE" in subscribed or not subscribed}  # 如果没订阅任何股票，接收所有数据
                    
                    if relevant_frames:
                        message["frames"] = relevant_frames
                        await connection.send_text(json.dumps(message, default=lambda x: x.dict() if hasattr(x, 'dict') else x))
                except Exception as e:
                    logger.error(f"广播tick数据失败: {e}")
                    disconnected.append(connection)
            
            # 清理断开的连接
            for connection in disconnected:
                self.disconnect(connection)

    def update_subscription(self, websocket: WebSocket, symbols: List[str]):
        """更新订阅的股票列表"""
        with self.lock:
            if websocket in self.subscribed_symbols:
                self.subscribed_symbols[websocket] = set(symbols)
                logger.info(f"更新订阅: {symbols}")

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # 接收客户端消息
            data = await websocket.receive_text()
            logger.info(f"收到WebSocket消息: {data}")
            try:
                message = json.loads(data)
                message_type = message.get("type")
                logger.info(f"消息类型: {message_type}, 完整消息: {message}")
                
                if message_type == "subscribe":
                    symbols = message.get("symbols", [])
                    manager.update_subscription(websocket, symbols)
                    await manager.send_personal_message(
                        json.dumps({"type": "subscription_confirmed", "symbols": symbols}),
                        websocket
                    )
                    logger.info(f"订阅确认: {symbols}")
                
                elif message_type == "ping":
                    await manager.send_personal_message(
                        json.dumps({"type": "pong"}),
                        websocket
                    )
                    
            except json.JSONDecodeError:
                logger.error("无效的JSON消息")
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# @app.on_event("startup")
# def startup():
#     pass

# @app.on_event("shutdown")
# def shutdown():
#     """应用关闭时保存数据"""
#     try:
#         if hasattr(app.state, "realtime_feature_ita_store"):
#             app.state.realtime_feature_ita_store.stop_auto_save()
#         print("Application shutdown completed")
#     except Exception as e:
#         print(f"Error during shutdown: {str(e)}")


class TimestampQueue:
    def __init__(self, maxlen=1000):
        self.lock = Lock()
        self.queue = deque(maxlen=maxlen)  # (timestamp, message)

    def append(self, msg: Dict):
        with self.lock:
            self.queue.appendleft(msg)

    def get(self, after_ts: str, max_frames: int = 500) -> List[Dict]:
        with self.lock:
            result = []
            for msg in self.queue:
                if msg["timestamp"] > after_ts:
                    result.append(msg)
                    if len(result) >= max_frames:
                        break
                else:
                    break
            return list(reversed(result))


class MultiDayTimestampQueue:
    def __init__(self, maxlen_per_day=10000):
        self.queues: Dict[str, TimestampQueue] = {}
        self.maxlen = maxlen_per_day
        self.lock = Lock()

    def _extract_date(self, ts: str) -> str:
        # ts 格式: "YYYYMMDDhhmmss"，提取前 8 位作为日期
        return ts[:8]

    def append(self, msg: Dict):
        ts = msg["timestamp"]
        date_key = self._extract_date(ts)
        with self.lock:
            if date_key not in self.queues:
                self.queues[date_key] = TimestampQueue(maxlen=self.maxlen)
            self.queues[date_key].append(msg)


    def get(self, after_ts: str, max_frames: int = 500) -> List[Dict]:
        date_key = self._extract_date(after_ts)
        with self.lock:
            queue = self.queues.get(date_key)
            if queue:
                return queue.get(after_ts, max_frames)
            else:
                return []

multi_day_queue = MultiDayTimestampQueue()

@app.get("/inDayFrames/{ts}/{max_frames}")
def get_in_day_frames(ts: str, max_frames: int):
    return multi_day_queue.get(ts, max_frames)


@app.post("/inDayFrames")
async def post_in_day_frames(frames: Dict[str, List[Frame]]):
    """
    保存日内帧数据到文件，使用临时文件和 fsync 确保写入原子性
    
    参数:
    - frames: 股票代码到帧列表的映射
    
    返回:
    - 操作结果信息
    """
    data_dict = frames
    
    ts = int(datetime.now().timestamp())
    current_date = datetime.now()
    formatted_date = current_date.strftime("%Y%m%d")
    new_frame_cnt = len(data_dict)
    
    if new_frame_cnt > 0:
        # write to multi_day_queue first
        multi_day_queue.append({'timestamp': f'{formatted_date}_{ts}', 'frames': data_dict})

        # 通过WebSocket广播tick数据
        await manager.broadcast_tick_data(data_dict)

        # then to file
        # 确保输出目录存在
        os.makedirs(FRAMES_OUTPUT_DIR, exist_ok=True)
        
        # 目标文件路径
        target_file_path = f"{FRAMES_OUTPUT_DIR}/brisk_in_day_frames_{formatted_date}_{ts}.json"
        
        # 创建临时文件
        temp_fd, temp_file_path = tempfile.mkstemp(suffix='.json', dir=FRAMES_OUTPUT_DIR)
        
        try:
            # 使用文件描述符写入数据
            with os.fdopen(temp_fd, 'w') as temp_file:
                json.dump(data_dict, temp_file, default=vars)
                
                # 确保数据写入磁盘
                temp_file.flush()
                os.fsync(temp_file.fileno())
            
            # 原子性地重命名临时文件为目标文件
            # 在大多数文件系统上，重命名操作是原子的
            shutil.move(temp_file_path, target_file_path)
            
            print(f"Successfully wrote {new_frame_cnt} frames to {target_file_path}")
            return ['ok', f'new frame cnt: {new_frame_cnt}']
            
        except Exception as e:
            # 发生错误时，尝试清理临时文件
            print(f"Error writing frames: {str(e)}")
            try:
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
            except:
                pass  # 忽略清理临时文件时的错误
            
            raise HTTPException(status_code=500, detail=f"Error writing frames: {str(e)}")
    
    return ['ok', f'no new frames to write']


class ThreadSafeCache:
    def __init__(self, max_size=100):
        self.cache = OrderedDict()
        self.lock = threading.RLock()
        self.max_size = max_size
    
    def get(self, key, default=None):
        with self.lock:
            if key in self.cache:
                # 将访问的项移到末尾，表示最近使用
                value = self.cache.pop(key)
                self.cache[key] = value
                return value
            return default
    
    def set(self, key, value):
        with self.lock:
            # 如果键已存在，先移除它
            if key in self.cache:
                self.cache.pop(key)
            
            # 添加新项
            self.cache[key] = value
            
            # 如果超过最大大小，删除最早的项
            if len(self.cache) > self.max_size:
                self.cache.popitem(last=False)  # 删除第一个项（最早的）
    
    def __contains__(self, key):
        with self.lock:
            return key in self.cache
    
    def __len__(self):
        with self.lock:
            return len(self.cache)
    
    def clear(self):
        with self.lock:
            self.cache.clear()
    
    def keys(self):
        with self.lock:
            return list(self.cache.keys())
    
    def items(self):
        with self.lock:
            return list(self.cache.items())

# 创建线程安全的缓存实例
trade_cache = ThreadSafeCache(max_size=1000)

@app.post("/metadata/")
def post_metadata(data: Dict[str, str] = Body(...)):
    for key, value in data.items():
        trade_cache.set(key, value)
    return ['ok']

@app.get("/metadata/{key}")
def get_metadata(key: str):
    return trade_cache.get(key, None)
