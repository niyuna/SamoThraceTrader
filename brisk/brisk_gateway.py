# Brisk Gateway for Japanese Stock Market
import asyncio
import json
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from urllib.parse import urljoin
from zoneinfo import ZoneInfo
import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

from vnpy.trader.object import Exchange, Product, ContractData, TickData, OrderRequest, CancelRequest, HistoryRequest, SubscribeRequest, BarData
from vnpy.trader.gateway import BaseGateway
from vnpy.event import EventEngine
from vnpy.trader.constant import Exchange, Interval

# 日股交易所映射
JAPANESE_EXCHANGES = {
    "TSE": Exchange.TSE,  # 东京证券交易所
    "OSE": Exchange.TSE,  # 大阪证券交易所
    "JASDAQ": Exchange.TSE,  # JASDAQ
    "FSE": Exchange.TSE,  # 福冈证券交易所
    "SES": Exchange.TSE,  # 札幌证券交易所
}

# 默认交易所
DEFAULT_EXCHANGE = Exchange.TSE


class BriskGateway(BaseGateway):
    """
    Brisk Gateway for Japanese Stock Market
    """

    default_name: str = "BRISK"
    default_setting: Dict[str, str | int | float | bool] = {
        "tick_server_url": "ws://127.0.0.1:8001/ws",
        "tick_server_http_url": "http://127.0.0.1:8001",
        "reconnect_interval": 5,
        "heartbeat_interval": 30,
        "max_reconnect_attempts": 10,
    }
    exchanges: List[Exchange] = [Exchange.TSE]

    def __init__(self, event_engine: EventEngine, gateway_name: str) -> None:
        """Constructor"""
        super().__init__(event_engine, gateway_name)

        # WebSocket连接相关
        self._ws: Optional[websockets.WebSocketServerProtocol] = None
        self._ws_url: str = ""
        self._http_url: str = ""
        self._connected: bool = False
        self._reconnect_interval: int = 5
        self._heartbeat_interval: int = 30
        self._max_reconnect_attempts: int = 10
        self._reconnect_attempts: int = 0
        self._last_heartbeat: float = 0

        # 线程相关
        self._ws_thread: Optional[threading.Thread] = None
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._active: bool = False

        # 数据缓存
        self._subscribed_symbols: set = set()
        self._contracts: Dict[str, ContractData] = {}
        self._ticks: Dict[str, TickData] = {}

        # 成交量和成交额缓存 - 用于累计计算
        self._trading_cache = {}  # {
        #   symbol: {
        #       'last_volume': 0,
        #       'current_volume': 0,
        #       'last_turnover': 0,
        #       'current_turnover': 0,
        #       'last_timestamp': 0,
        #       'last_date': None
        #   }
        # }

        # 锁
        self._lock: threading.Lock = threading.Lock()

    def connect(self, setting: Dict) -> None:
        """连接服务器"""
        self._ws_url = setting.get("tick_server_url", self.default_setting["tick_server_url"])
        self._http_url = setting.get("tick_server_http_url", self.default_setting["tick_server_http_url"])
        self._reconnect_interval = setting.get("reconnect_interval", self.default_setting["reconnect_interval"])
        self._heartbeat_interval = setting.get("heartbeat_interval", self.default_setting["heartbeat_interval"])
        self._max_reconnect_attempts = setting.get("max_reconnect_attempts", self.default_setting["max_reconnect_attempts"])

        self._active = True
        
        self._ws_thread = threading.Thread(target=self._run_websocket)
        self._ws_thread.daemon = True
        self._ws_thread.start()

        # 对于本地连接，禁用心跳检测
        # self._heartbeat_thread = threading.Thread(target=self._run_heartbeat)
        # self._heartbeat_thread.daemon = True
        # self._heartbeat_thread.start()

        self.write_log("Brisk Gateway启动成功")

    def close(self) -> None:
        """关闭连接"""
        self._active = False
        self._connected = False

        # 不直接关闭WebSocket，让线程自然结束
        # if self._ws:
        #     asyncio.run(self._ws.close())

        self.write_log("Brisk Gateway已关闭")

    def subscribe(self, req: SubscribeRequest) -> None:
        """订阅行情"""
        with self._lock:
            # hacky way to do batch subscription. TODO: design a better way
            for real_symbol in req.symbol.split(','):
                self._subscribed_symbols.add(real_symbol)

        self.write_log(f"订阅行情成功: {req.vt_symbol}")
        
        # 如果WebSocket已连接，立即发送完整的订阅列表
        # TODO：这里需要优化，不要每次订阅都发送完整的订阅列表
        if self._connected and self._ws:
            # 使用asyncio.run在同步方法中调用异步方法
            try:
                asyncio.run(self._send_subscribe_message())
            except Exception as e:
                self.write_log(f"发送订阅消息失败: {e}")

    def send_order(self, req: OrderRequest) -> str:
        """发送委托"""
        # 日股交易功能暂未实现
        self.write_log("日股交易功能暂未实现")
        return ""

    def cancel_order(self, req: CancelRequest) -> None:
        """撤销委托"""
        # 日股交易功能暂未实现
        self.write_log("日股交易功能暂未实现")

    def query_account(self) -> None:
        """查询资金"""
        # 日股交易功能暂未实现
        self.write_log("日股交易功能暂未实现")

    def query_position(self) -> None:
        """查询持仓"""
        # 日股交易功能暂未实现
        self.write_log("日股交易功能暂未实现")

    def query_history(self, req: HistoryRequest) -> List[BarData]:
        """查询历史数据"""
        # 从tick_server获取历史数据
        try:
            # 这里需要实现从tick_server的HTTP接口获取历史数据
            # 并转换为BarData格式
            self.write_log(f"查询历史数据: {req.vt_symbol}")
            return []
        except Exception as e:
            self.write_log(f"查询历史数据失败: {e}")
            return []


    def _run_websocket(self) -> None:
        """运行WebSocket连接"""
        while self._active:
            try:
                asyncio.run(self._connect_websocket())
            except Exception as e:
                self.write_log(f"WebSocket连接异常: {e}")
                time.sleep(self._reconnect_interval)

    async def _connect_websocket(self) -> None:
        """连接WebSocket"""
        try:
            self._ws = await websockets.connect(self._ws_url)
            self._connected = True
            self._reconnect_attempts = 0
            self.write_log("WebSocket连接成功")

            # 发送订阅消息
            await self._send_subscribe_message()

            # 接收消息
            async for message in self._ws:
                if not self._active:
                    break
                await self._on_message(message)

        except ConnectionClosed:
            self.write_log("WebSocket连接已关闭")
        except WebSocketException as e:
            self.write_log(f"WebSocket异常: {e}")
        except Exception as e:
            self.write_log(f"WebSocket连接失败: {e}")
        finally:
            self._connected = False
            if self._ws:
                await self._ws.close()

    async def _send_subscribe_message(self) -> None:
        """发送订阅消息"""
        if not self._ws:
            return

        subscribe_msg = {
            "type": "subscribe",
            "symbols": list(self._subscribed_symbols)
        }
        self.write_log(f"发送订阅消息: {subscribe_msg}")
        await self._ws.send(json.dumps(subscribe_msg))



    async def _on_message(self, message: str) -> None:
        """处理接收到的消息"""
        try:
            data = json.loads(message)
            
            # 处理tick数据
            if "frames" in data:
                await self._process_tick_data(data["frames"])
            
            # 处理心跳
            elif data.get("type") == "heartbeat":
                self._last_heartbeat = time.time()
                
        except json.JSONDecodeError as e:
            self.write_log(f"JSON解析失败: {e}")
        except Exception as e:
            self.write_log(f"消息处理失败: {e}")

    async def _process_tick_data(self, frames: Dict[str, List[Dict]]) -> None:
        """处理tick数据"""
        for symbol, frame_list in frames.items():
            for frame_data in frame_list:
                tick = self._convert_frame_to_tick(symbol, frame_data)
                if tick:
                    # 发送tick事件
                    self.on_tick(tick)

    def _reset_daily_cache(self, symbol: str, new_date):
        """重置指定symbol的每日缓存"""
        if symbol in self._trading_cache:
            self._trading_cache[symbol] = {
                'last_volume': 0,
                'current_volume': 0,
                'last_turnover': 0,
                'current_turnover': 0,
                'last_timestamp': 0,
                'last_date': new_date
            }
            self.write_log(f"重置 {symbol} 的每日缓存")

    def _convert_frame_to_tick(self, symbol: str, frame: Dict, date_str: str = None) -> Optional[TickData]:
        """将Frame转换为TickData（增强版 - 支持累计成交量和成交额）"""
        try:
            # 解析时间戳 - frame中的timestamp是距离当天JST 0点的微秒数
            micro_seconds = frame.get("timestamp", 0)
            
            # 如果没有提供日期，使用当前日期
            if date_str is None:
                date_str = datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y%m%d")
            
            # 创建当天0点的时间
            base_date = datetime.strptime(date_str, "%Y%m%d").replace(tzinfo=ZoneInfo("Asia/Tokyo"))
            
            # 将微秒转换为秒，然后加到基础时间上
            seconds = micro_seconds / 1_000_000  # 微秒转秒
            dt = base_date + timedelta(seconds=seconds)
            
            # 处理成交量和成交额
            frame_volume = frame.get("quantity", 0)
            frame_price = frame.get("price10", 0) / 10.0  # 转换为实际价格
            frame_turnover = frame_volume * frame_price   # 计算单次成交额
            frame_timestamp = frame.get("timestamp", 0)
            
            # 初始化缓存
            if symbol not in self._trading_cache:
                self._trading_cache[symbol] = {
                    'last_volume': 0,
                    'current_volume': 0,
                    'last_turnover': 0,
                    'current_turnover': 0,
                    'last_timestamp': 0,
                    'last_date': None
                }
            
            cache = self._trading_cache[symbol]
            
            # 检查是否需要重置每日数据
            frame_date = base_date.date()
            if cache['last_date'] is not None and cache['last_date'] != frame_date:
                self._reset_daily_cache(symbol, frame_date)
                cache = self._trading_cache[symbol]  # 重新获取缓存引用
            
            # 检查时间戳，确保按顺序处理
            if frame_timestamp < cache['last_timestamp']:
                self.write_log(f"警告：{symbol} 时间戳倒序，跳过frame (当前:{frame_timestamp}, 上次:{cache['last_timestamp']})")
                return None
            
            # 更新累计成交量和成交额
            cache['last_volume'] = cache['current_volume']
            cache['last_turnover'] = cache['current_turnover']
            cache['current_volume'] += frame_volume
            cache['current_turnover'] += frame_turnover
            cache['last_timestamp'] = frame_timestamp
            cache['last_date'] = frame_date
            
            # 创建TickData
            tick = TickData(
                symbol=symbol,
                exchange=DEFAULT_EXCHANGE,
                datetime=dt,
                gateway_name=self.gateway_name,
                name=symbol,
                volume=cache['current_volume'],             # 累计成交量
                turnover=cache['current_turnover'],         # 累计成交额
                last_price=frame_price,
                last_volume=frame_volume,                   # 单次成交量
                localtime=datetime.now(ZoneInfo("Asia/Tokyo"))
            )
            
            return tick
            
        except Exception as e:
            self.write_log(f"数据转换失败: symbol={symbol}, frame={frame}, error={e}")
            return None

    def _run_heartbeat(self) -> None:
        """运行心跳检测"""
        while self._active:
            try:
                if self._connected:
                    current_time = time.time()
                    if current_time - self._last_heartbeat > self._heartbeat_interval * 2:
                        self.write_log("心跳超时，准备重连")
                        self._connected = False
                        break
                time.sleep(self._heartbeat_interval)
            except Exception as e:
                self.write_log(f"心跳检测异常: {e}")

    def _create_contract(self, symbol: str) -> ContractData:
        """创建合约信息"""
        contract = ContractData(
            symbol=symbol,
            exchange=DEFAULT_EXCHANGE,
            name=symbol,
            product=Product.EQUITY,
            size=1,
            pricetick=0.01,
            min_volume=1,
            gateway_name=self.gateway_name,
        )
        return contract
