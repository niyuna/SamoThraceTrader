from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware

import threading
from collections import OrderedDict
from typing import Dict, List

from loguru import logger
logger.add('C:\\dev\\brisk_general_config_server.log', rotation="08:00", compression="zip")

app = FastAPI()
shared_vars = {}
shared_vars['active_ws_connection'] = []

origins = [
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
