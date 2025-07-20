#!/usr/bin/env python3
"""
测试脚本：发送模拟tick数据到tick server
"""

import asyncio
import json
import time
from datetime import datetime, timezone, timedelta
import aiohttp

# tick server的HTTP接口地址
TICK_SERVER_URL = "http://127.0.0.1:8001"

def create_mock_frame(symbol: str, price: float, quantity: int, timestamp_microseconds: int):
    """创建模拟的Frame数据"""
    return {
        "frameNumber": int(time.time() * 1000) % 10000,
        "price10": int(price * 10),  # price10是价格的10倍
        "quantity": quantity,
        "timestamp": timestamp_microseconds,  # 距离当天JST 0点的微秒数
        "type": 1
    }

async def send_mock_data():
    """发送模拟数据到tick server"""
    async with aiohttp.ClientSession() as session:
        # 获取当前时间
        now = datetime.now(timezone(timedelta(hours=9)))  # JST时间
        base_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # 计算距离当天0点的微秒数
        time_diff = now - base_time
        microseconds = int(time_diff.total_seconds() * 1_000_000)
        
        # 创建模拟数据
        mock_frames = {
            "7203": [  # 丰田
                create_mock_frame("7203", 2500.0, 100, microseconds),
                create_mock_frame("7203", 2501.0, 50, microseconds + 1000000),  # 1秒后
            ],
            "6758": [  # 索尼
                create_mock_frame("6758", 12000.0, 200, microseconds),
                create_mock_frame("6758", 12001.0, 75, microseconds + 2000000),  # 2秒后
            ],
            "9984": [  # 软银
                create_mock_frame("9984", 8000.0, 150, microseconds),
                create_mock_frame("9984", 8001.0, 80, microseconds + 1500000),  # 1.5秒后
            ]
        }
        
        # 发送数据到tick server
        url = f"{TICK_SERVER_URL}/inDayFrames"
        try:
            async with session.post(url, json=mock_frames) as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"✅ 成功发送模拟数据: {result}")
                else:
                    print(f"❌ 发送数据失败: {response.status}")
                    print(await response.text())
        except Exception as e:
            print(f"❌ 发送数据异常: {e}")

async def main():
    """主函数"""
    print("🚀 开始发送模拟tick数据...")
    
    # 发送3次数据，每次间隔2秒
    for i in range(3):
        print(f"\n📊 第{i+1}次发送数据...")
        await send_mock_data()
        
        if i < 2:  # 最后一次不需要等待
            print("⏳ 等待2秒...")
            await asyncio.sleep(2)
    
    print("\n✅ 模拟数据发送完成！")

if __name__ == "__main__":
    asyncio.run(main()) 