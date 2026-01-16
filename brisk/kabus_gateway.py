# Brisk Gateway for Japanese Stock Market
import asyncio
import json
import threading
import time
import os
import glob
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from urllib.parse import urljoin
from zoneinfo import ZoneInfo
import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

from vnpy.trader.object import Exchange, Product, ContractData, TickData, OrderRequest, CancelRequest, HistoryRequest, SubscribeRequest, BarData, OrderData
from vnpy.trader.gateway import BaseGateway
from vnpy.event import EventEngine
from vnpy.trader.constant import Exchange, Interval, Direction, Offset, Status, OrderType

from common import kabus_api
from common.trading_common import TradingSide

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

Direction_to_TradingSide = {
    Direction.LONG: TradingSide.LONG,
    Direction.SHORT: TradingSide.SHORT,
}

class KabusGateway(BaseGateway):
    """
    Kabus Gateway for Japanese Stock Market
    """

    default_name: str = "KABUS"
    default_setting: Dict[str, str | int | float | bool] = {
        "tick_server_url": "ws://192.168.50.131:16080/kabusapi/websocket",
        "tick_server_http_url": "http://192.168.50.131:16080/kabusapi/websocket",
        "reconnect_interval": 5,
        "max_reconnect_attempts": 20,
        "polling_interval": 1,  # 订单状态轮询间隔（秒）
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
        self._max_reconnect_attempts: int = 10
        self._reconnect_attempts: int = 0

        # 线程相关
        self._ws_thread: Optional[threading.Thread] = None
        self._polling_thread: Optional[threading.Thread] = None
        self._active: bool = False

        # 数据缓存
        self._subscribed_symbols: set = set()
        self._contracts: Dict[str, ContractData] = {}
        self._ticks: Dict[str, TickData] = {}

        # 成交量和成交额缓存 - 用于累计计算
        self._trading_cache = {}  

        # 订单状态轮询相关
        self.local_orders: Dict[str, OrderData] = {}  # key: orderid (ID字段)
        # 设置初始时间为当天的早上8点50分，确保获取当天所有订单
        today = datetime.now()
        self.last_updtime: str = today.strftime("%Y%m%d") + "085000"  # 格式: yyyyMMddHHmmss
        # self.last_updtime: str = "20250725085000"  # temporarily setting this for testing

        # set it longer because right now we only use this for futures trading
        self.polling_interval: int = 10  # 轮询间隔（秒）
        self._polling_active: bool = False

        # token = kabus_api.init_trading_api(init_rate_limiter=True)
        token = kabus_api.init_trading_api_from_general_config_server(init_rate_limiter=True)
        if token is None:
            self.write_log("Kabus API token is None")
            return
        self.write_log(f"Kabus API token: {token}")

        # 锁
        self._lock: threading.Lock = threading.Lock()
        
        # Replay相关
        self.replay_engine = None
        self.replay_mode = False

    def connect(self, setting: Dict) -> None:
        """连接服务器"""
        # 检查是否是replay模式
        tick_mode = setting.get("tick_mode", "live")
        
        if tick_mode == "replay":
            self.replay_mode = True
            self._init_replay_engine(setting)
            self._active = True
            # 启动订单状态轮询线程（如果需要）
            self._start_polling_thread()
            self.write_log("Kabus Gateway启动成功（Replay模式）")
        else:
            # 原有的实时连接逻辑
            self._ws_url = setting.get("tick_server_url", self.default_setting["tick_server_url"])
            self._http_url = setting.get("tick_server_http_url", self.default_setting["tick_server_http_url"])
            self._reconnect_interval = setting.get("reconnect_interval", self.default_setting["reconnect_interval"])
            self._max_reconnect_attempts = setting.get("max_reconnect_attempts", self.default_setting["max_reconnect_attempts"])
            self.polling_interval = setting.get("polling_interval", self.default_setting["polling_interval"])

            self._active = True
            
            self._ws_thread = threading.Thread(target=self._run_websocket)
            self._ws_thread.daemon = True
            self._ws_thread.start()

            # 启动订单状态轮询线程
            self._start_polling_thread()

            self.write_log("Kabus Gateway启动成功")

    def close(self) -> None:
        """关闭连接"""
        self._active = False
        self._connected = False
        self._polling_active = False
        
        # 停止replay（如果正在运行）
        if self.replay_engine:
            self.replay_engine.stop_replay()

        self.write_log("Kabus Gateway已关闭")

    def subscribe(self, req: SubscribeRequest, is_future: bool = True) -> None:
        """订阅行情"""
        for real_symbol in req.symbol.split(','):
            self._subscribed_symbols.add(real_symbol)

        # 在replay模式下，不需要调用kabus_api注册
        if not self.replay_mode:
            kabus_api.register_sc_lst(list(self._subscribed_symbols), exchange=2 if is_future else 1)

        self.write_log(f"订阅行情成功: {req.vt_symbol}, 已订阅symbols: {list(self._subscribed_symbols)}")

    def send_order(self, req: OrderRequest) -> str:
        is_future = len(req.symbol) > 4
        self.write_log(f"send_order: {req}")
        # right now only support future trading her
        if not is_future:
            raise Exception(f"only support future trading here: {req.symbol}")

        if req.offset == Offset.OPEN:
            order_id = kabus_api.send_future_init_trading_order(req.symbol, Direction_to_TradingSide[req.direction], req.price, req.volume)
        elif req.offset == Offset.CLOSE:
            order_id = kabus_api.send_future_close_position_order(req.symbol, Direction_to_TradingSide[req.direction], req.price, req.volume)
        else:
            raise Exception(f"不支持的委托方向: {req.offset}")
        
        # 创建初始订单对象并添加到本地缓存
        if order_id:
            initial_order = OrderData(
                gateway_name=self.gateway_name,
                symbol=req.symbol,
                exchange=req.exchange,
                orderid=order_id,
                type=req.type,
                direction=req.direction,
                offset=req.offset,
                price=req.price,
                volume=req.volume,
                traded=0.0,  # 初始成交量为0
                status=Status.SUBMITTING,  # 初始状态为提交中
                datetime=datetime.now(),
                reference=req.reference
            )
            self._add_order(initial_order)
            self.write_log(f"订单已发送并添加到缓存: {order_id}")
        
        return order_id

    def cancel_order(self, req: CancelRequest) -> None:
        cancel_result = kabus_api.cancel_order(req.orderid)
        if not cancel_result:
            raise Exception(f"撤销委托失败: {req.orderid}")

    def query_account(self) -> None:
        """查询资金"""
        # 日股交易功能暂未实现
        self.write_log("日股交易功能暂未实现")

    def query_position(self) -> None:
        """查询持仓"""
        # 日股交易功能暂未实现
        self.write_log("日股交易功能暂未实现")
    
    def get_positions(self) -> List[dict]:
        """获取实际持仓数据
        
        Returns:
            List[dict]: 持仓数据列表，每个元素包含 Symbol, LeavesQty, HoldQty, Side 等
        """
        try:
            # 调用 kabus_api.get_positions() 获取持仓数据
            # only 3 means future only
            positions = kabus_api.get_positions(product='3')
            return positions
        except Exception as e:
            self.write_log(f"获取持仓数据失败: {e}")
            return []

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

    async def _cleanup_pending_tasks(self):
        # 取消并回收当前 loop 上除自己外的所有挂起任务
        this = asyncio.current_task()
        pending = [t for t in asyncio.all_tasks() if t is not this and not t.done()]
        if not pending:
            return
        for t in pending:
            t.cancel()
        await asyncio.gather(*pending, return_exceptions=True)

    def _run_websocket(self) -> None:
        self.write_log("WebSocket线程启动")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # 可选：便于抓未处理任务的异常
        loop.set_exception_handler(
            lambda l, ctx: self.write_log(f"[loop异常] {ctx.get('message')}: {ctx.get('exception')!r}")
        )

        try:
            while self._active:
                try:
                    self.write_log(f"开始连接WebSocket，_active={self._active}")
                    loop.run_until_complete(self._connect_websocket())
                    self.write_log("WebSocket连接协程自然返回（将重连）")
                except Exception as e:
                    # 这里保留你的退避重连逻辑（也可加 except*）
                    self._reconnect_attempts += 1
                    wait = min(self._reconnect_interval * (2 ** (self._reconnect_attempts - 1)), 60)
                    self.write_log(f"第 {self._reconnect_attempts} 次重连尝试，等待 {wait} 秒...")
                    time.sleep(wait)
                finally:
                    # 关键：每轮结束后，把残留任务清空，避免越积越多
                    loop.run_until_complete(self._cleanup_pending_tasks())
        finally:
            # 只在真正退出线程时做一次全量收尾
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.run_until_complete(loop.shutdown_default_executor())
            loop.close()
            self.write_log("WebSocket线程结束")

    async def _connect_websocket(self) -> None:
        """连接WebSocket"""
        try:
            reason = "normal-return"
            self._ws = await websockets.connect(self._ws_url, ping_timeout=None)
            self._connected = True
            self._reconnect_attempts = 0
            self.write_log("WebSocket连接成功")
            
            # 接收消息
            async for message in self._ws:
                if not self._active:
                    reason = "break-by-inactive"
                    break
                await self._on_message(message)

        except ConnectionClosed as e:
            self.write_log(f"WebSocket连接已关闭: {e}")
            self.write_log(f"ConnectionClosed异常即将重新抛出")
            reason = f"raise:{type(e).__name__}"
            raise  # 重新抛出异常以触发重连
        except WebSocketException as e:
            self.write_log(f"WebSocket异常: {e}")
            self.write_log(f"WebSocketException异常即将重新抛出")
            reason = f"raise:{type(e).__name__}"
            raise  # 重新抛出异常以触发重连
        except Exception as e:
            self.write_log(f"WebSocket连接失败: {e}")
            self.write_log(f"Exception异常即将重新抛出")
            reason = f"raise:{type(e).__name__}"
            raise  # 重新抛出异常以触发重连
        finally:
            self.write_log(f"_connect_websocket 退出，reason={reason}")
            self._connected = False
            if self._ws:
                self.write_log("准备 close() ...")
                try:
                    await asyncio.wait_for(self._ws.close(), timeout=3)  # 先限时
                except Exception as e:
                    self.write_log(f"close() 出错或超时，忽略继续: {e!r}")
                finally:
                    self.write_log("close() 结束，准备返回")
                    self._ws = None
        self.write_log("[_connect_websocket] RETURNING")

    async def _on_message(self, message: str) -> None:
        """处理接收到的Kabus WebSocket消息"""
        try:
            data = json.loads(message)
            
            # 提取Symbol字段
            symbol = data.get("Symbol")
            if not symbol:
                self.write_log(f"消息缺少Symbol字段: {data}")
                return
            
            # 检查是否已订阅该symbol
            if symbol not in self._subscribed_symbols:
                # 未订阅的symbol，忽略消息
                return
            
            # 调用转换方法处理消息
            tick = self._convert_kabus_message_to_tick(symbol, data)
            
            # 如果检测到tick变化，生成TickData并推送
            if tick:
                self.on_tick(tick)
                
        except json.JSONDecodeError as e:
            self.write_log(f"JSON解析失败: {e}, message: {message[:200]}")
        except Exception as e:
            self.write_log(f"消息处理失败: {e}, message: {message[:200]}")
            # 如果是连接相关异常，重新抛出以触发重连
            if "ConnectionClosed" in str(type(e)) or "WebSocketException" in str(type(e)):
                raise

    def _reset_daily_cache(self, symbol: str, new_date):
        """重置指定symbol的每日缓存"""
        if symbol in self._trading_cache:
            self._trading_cache[symbol] = {
                'last_trading_volume': 0,
                'last_trading_volume_time': '',
                'volume': 0,  # 累计成交量
                'turnover': 0,  # 累计成交额
                'last_date': new_date
            }
            self.write_log(f"重置 {symbol} 的每日缓存，日期: {new_date}")

    def _convert_kabus_message_to_tick(self, symbol: str, message: Dict) -> Optional[TickData]:
        """将Kabus WebSocket消息转换为TickData
        
        检测tick变化：只有当TradingVolume或TradingVolumeTime变化时才生成tick
        """
        try:
            # 初始化缓存
            if symbol not in self._trading_cache:
                self._trading_cache[symbol] = {
                    'last_trading_volume': 0,
                    'last_trading_volume_time': '',
                    'volume': 0,  # 累计成交量
                    'turnover': 0,  # 累计成交额
                    'last_date': None
                }
            
            cache = self._trading_cache[symbol]
            
            # 提取TradingVolume和TradingVolumeTime用于检测tick变化
            current_volume = message.get('TradingVolume') or 0
            current_volume_time = message.get('TradingVolumeTime', '')
            
            # 检查日期变化，必要时重置每日数据
            if current_volume_time:
                try:
                    # 解析时间字符串获取日期
                    dt_volume = datetime.fromisoformat(current_volume_time)
                    current_date = dt_volume.date()
                    
                    if cache['last_date'] is not None and cache['last_date'] != current_date:
                        self._reset_daily_cache(symbol, current_date)
                        cache = self._trading_cache[symbol]  # 重新获取缓存引用
                except Exception as e:
                    self.write_log(f"解析TradingVolumeTime失败: {e}, time={current_volume_time}")
            
            # 检测tick变化：只有当TradingVolume或TradingVolumeTime变化时才生成tick
            if (current_volume == cache['last_trading_volume'] and 
                current_volume_time == cache['last_trading_volume_time']):
                # 只是orderbook更新，不生成tick
                return None
            
            # 首次收到该symbol的消息，初始化缓存但不生成tick（可选）
            if cache['last_trading_volume'] == 0 and cache['last_trading_volume_time'] == '':
                cache['last_trading_volume'] = current_volume
                cache['last_trading_volume_time'] = current_volume_time
                cache['volume'] = current_volume
                cache['turnover'] = message.get('TradingValue') or 0
                if current_volume_time:
                    try:
                        dt_volume = datetime.fromisoformat(current_volume_time)
                        cache['last_date'] = dt_volume.date()
                    except:
                        pass
                # 首次不生成tick，等待下一次变化
                return None
            
            # 解析时间 - 使用TradingVolumeTime或CurrentPriceTime
            time_str = current_volume_time or message.get('CurrentPriceTime', '')
            if not time_str:
                # before current price is decided
                if message.get('CurrentPrice') is None or message.get('CurrentPrice') == 0:
                    time_str = datetime.now().isoformat()
                self.write_log(f"消息缺少时间字段: symbol={symbol}")
                return None
            
            try:
                # 处理ISO 8601格式的时间字符串
                dt = datetime.fromisoformat(time_str)
                # 如果没有时区信息，假设是JST
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=ZoneInfo("Asia/Tokyo"))
            except Exception as e:
                self.write_log(f"时间解析失败: {e}, time_str={time_str}")
                return None
            
            # 提取价格数据
            last_price = float(message.get('CurrentPrice') or 0)
            pre_close = float(message.get('PreviousClose') or 0)
            open_price = float(message.get('OpeningPrice') or 0)
            high_price = float(message.get('HighPrice') or 0)
            low_price = float(message.get('LowPrice') or 0)
            
            # 提取成交量数据
            volume = float(current_volume or 0)  # 累计成交量
            turnover = float(message.get('TradingValue') or 0)  # 累计成交额
            
            # 计算本次变化量
            last_volume = volume - cache['volume'] if cache.get('volume', 0) is not None and cache.get('volume', 0) > 0 else 0
            
            # 提取订单簿数据
            # BidPrice/AskPrice是第1档
            bid_price_1 = float(message.get('BidPrice') or 0)
            bid_volume_1 = float(message.get('BidQty') or 0)
            ask_price_1 = float(message.get('AskPrice') or 0)
            ask_volume_1 = float(message.get('AskQty') or 0)
            
            # 初始化订单簿数组（共5档）
            bid_prices = [bid_price_1]
            bid_volumes = [bid_volume_1]
            ask_prices = [ask_price_1]
            ask_volumes = [ask_volume_1]
            
            # Buy2-6对应买盘（bid）的第2-5档，价格从高到低
            for i in range(2, 6):  # Buy2-5
                buy_key = f'Buy{i}'
                if buy_key in message and isinstance(message[buy_key], dict):
                    buy_data = message[buy_key]
                    bid_prices.append(float(buy_data.get('Price') or 0))
                    bid_volumes.append(float(buy_data.get('Qty') or 0))
                else:
                    bid_prices.append(0.0)
                    bid_volumes.append(0.0)
            
            # Sell2-6对应卖盘（ask）的第2-5档，价格从低到高
            for i in range(2, 6):  # Sell2-5
                sell_key = f'Sell{i}'
                if sell_key in message and isinstance(message[sell_key], dict):
                    sell_data = message[sell_key]
                    ask_prices.append(float(sell_data.get('Price', 0) or 0))
                    ask_volumes.append(float(sell_data.get('Qty', 0) or 0))
                else:
                    ask_prices.append(0.0)
                    ask_volumes.append(0.0)
            
            # 更新缓存
            cache['last_trading_volume'] = current_volume
            cache['last_trading_volume_time'] = current_volume_time
            cache['volume'] = volume
            cache['turnover'] = turnover
            if current_volume_time:
                try:
                    dt_volume = datetime.fromisoformat(current_volume_time)
                    cache['last_date'] = dt_volume.date()
                except:
                    pass
            
            # 创建TickData对象
            tick = TickData(
                symbol=symbol,
                exchange=DEFAULT_EXCHANGE,
                datetime=dt,
                gateway_name=self.gateway_name,
                name=message.get('SymbolName', symbol),
                volume=volume,
                turnover=turnover,
                last_price=last_price,
                last_volume=last_volume,
                pre_close=pre_close,
                open_price=open_price,
                high_price=high_price,
                low_price=low_price,
                bid_price_1=bid_prices[0] if len(bid_prices) > 0 else 0,
                bid_price_2=bid_prices[1] if len(bid_prices) > 1 else 0,
                bid_price_3=bid_prices[2] if len(bid_prices) > 2 else 0,
                bid_price_4=bid_prices[3] if len(bid_prices) > 3 else 0,
                bid_price_5=bid_prices[4] if len(bid_prices) > 4 else 0,
                ask_price_1=ask_prices[0] if len(ask_prices) > 0 else 0,
                ask_price_2=ask_prices[1] if len(ask_prices) > 1 else 0,
                ask_price_3=ask_prices[2] if len(ask_prices) > 2 else 0,
                ask_price_4=ask_prices[3] if len(ask_prices) > 3 else 0,
                ask_price_5=ask_prices[4] if len(ask_prices) > 4 else 0,
                bid_volume_1=bid_volumes[0] if len(bid_volumes) > 0 else 0,
                bid_volume_2=bid_volumes[1] if len(bid_volumes) > 1 else 0,
                bid_volume_3=bid_volumes[2] if len(bid_volumes) > 2 else 0,
                bid_volume_4=bid_volumes[3] if len(bid_volumes) > 3 else 0,
                bid_volume_5=bid_volumes[4] if len(bid_volumes) > 4 else 0,
                ask_volume_1=ask_volumes[0] if len(ask_volumes) > 0 else 0,
                ask_volume_2=ask_volumes[1] if len(ask_volumes) > 1 else 0,
                ask_volume_3=ask_volumes[2] if len(ask_volumes) > 2 else 0,
                ask_volume_4=ask_volumes[3] if len(ask_volumes) > 3 else 0,
                ask_volume_5=ask_volumes[4] if len(ask_volumes) > 4 else 0,
                localtime=datetime.now(ZoneInfo("Asia/Tokyo"))
            )
            
            return tick
            
        except Exception as e:
            self.write_log(f"数据转换失败: symbol={symbol}, error={e}, message_keys={list(message.keys())[:10]}")
            import traceback
            self.write_log(f"Traceback: {traceback.format_exc()}")
            return None

    def _start_polling_thread(self):
        """启动订单状态轮询线程"""
        self._polling_active = True
        self._polling_thread = threading.Thread(target=self._run_polling)
        self._polling_thread.daemon = True
        self._polling_thread.start()
        self.write_log("订单状态轮询线程已启动")

    def _run_polling(self):
        """运行订单状态轮询"""
        while self._polling_active:
            try:
                self._poll_orders()
                time.sleep(self.polling_interval)
            except Exception as e:
                self.write_log(f"订单轮询错误: {e}")
                time.sleep(self.polling_interval)

    # shoud need no change on this
    def _poll_orders(self):
        """轮询订单状态"""
        # 1. 记录当前时间作为本次查询的updtime
        current_time = datetime.now().strftime("%Y%m%d%H%M%S")
        
        # 2. 拉取所有 self.last_updtime 之后的订单
        orders = kabus_api.query_orders_after(self.last_updtime)
        # None means API call quota exceeded, we should retry later
        if orders == list():
            # 即使没有订单，也要更新时间，避免重复查询
            # self.write_log(f"empty orders, updating last_updtime to {current_time}")
            self.last_updtime = current_time
            return
        elif orders is None:
            self.write_log(f"API call quota exceeded, updating last_updtime to {current_time}")
            return

        # 3. 遍历订单，转换格式，检测状态变化
        for broker_order in orders:
            try:
                order = self._convert_broker_order_to_vnpy(broker_order)
                orderid = order.orderid  # 使用broker_order['ID']
                old_order = self.local_orders.get(orderid)
                # 检测状态变化：状态不同 或 成交量不同
                if (not old_order) or (old_order.status != order.status or old_order.traded != order.traded):
                    self.local_orders[orderid] = order
                    self.on_order(order)  # 推送事件
                    self.write_log(f"订单状态更新: {orderid} {old_order.status if old_order else 'NEW'} -> {order.status}")
                else:
                    self.write_log(f"WARNING: kabus query order API: 订单状态未变化: {orderid} {old_order.status if old_order else 'NEW'} -> {order.status}")
            except Exception as e:
                self.write_log(f"订单转换失败: {e}")

        # 4. 更新last_updtime为当前时间
        self.last_updtime = current_time


    def query_single_order(self, orderid: str) -> OrderData:
        """查询单个订单"""
        try:
            broker_order = kabus_api.query_order_status(orderid)
            order = self._convert_broker_order_to_vnpy(broker_order)
            old_order = self.local_orders.get(orderid)
            if (not old_order) or (old_order.status != order.status or old_order.traded != order.traded):
                self.local_orders[orderid] = order
                self.on_order(order)  # 推送事件
                self.write_log(f"(query_single_order) 订单状态更新: {orderid} {old_order.status if old_order else 'NEW'} -> {order.status}")
            else:
                self.write_log(f"(query_single_order) WARNING: kabus query order API: 订单状态未变化: {orderid} {old_order.status if old_order else 'NEW'} -> {order.status}")

            return order
        except Exception as e:
            self.write_log(f"查询订单失败: {e}")
            return None

    def _convert_broker_order_to_vnpy(self, broker_order: Dict) -> OrderData:
        """将kabus API订单格式转换为vnpy格式"""
        volume = float(broker_order["OrderQty"])
        traded = float(broker_order["CumQty"])

        state = Status.SUBMITTING
        if broker_order["State"] in [1, 2, 4]:
            state = Status.SUBMITTING
        elif broker_order["State"] == 3:
            if traded == 0:
                state = Status.NOTTRADED
            else:
                state = Status.PARTTRADED
        elif broker_order["State"] == 5:
            if traded == volume and traded > 0:
                state = Status.ALLTRADED
            else:
                # in cancelled state, traded could > 0
                state = Status.CANCELLED
        
        # 方向映射 (基于broker_order['Side'])
        direction_mapping = {
            "1": Direction.SHORT,    # 1=卖出
            "2": Direction.LONG,     # 2=买入
        }
        
        # 订单类型映射 (基于broker_order['OrdType'])
        order_type_mapping = {
            1: OrderType.MARKET,     # 假设1=市价单
            2: OrderType.LIMIT,      # 假设2=限价单
        }
        
        # 交易所映射 (基于broker_order['Exchange'])
        exchange_mapping = {
            1: Exchange.TSE,         # 1: TSE
            9: Exchange.TSE,         # 9: SOR
            27: Exchange.TSE,        # 27: TSE+
        }
        
        # 解析时间
        recv_time = broker_order["RecvTime"]
        # recv_time is in JST
        dt = datetime.fromisoformat(recv_time)
        
        # avg traded price
        trades = list(filter(lambda x: x.get("ExecutionID") != None, broker_order["Details"]))
        avg_price = sum(float(trade["Price"]) * float(trade["Qty"]) for trade in trades) / sum(float(trade["Qty"]) for trade in trades) if trades else 0
        self.write_log(f"converting broker order to vnpy order: orderId: {broker_order['ID']}, symbol: {broker_order['Symbol']}, state: {state}, traded: {traded}, volume: {volume},avg_price: {avg_price}")

        order = OrderData(
            gateway_name=self.gateway_name,
            symbol=broker_order["Symbol"],
            exchange=exchange_mapping.get(broker_order["Exchange"], Exchange.TSE),
            orderid=broker_order["ID"],  # 直接使用ID字段
            type=OrderType.LIMIT if broker_order['Price'] > 0 else OrderType.MARKET,
            direction=direction_mapping.get(broker_order["Side"], Direction.LONG),
            offset=Offset.OPEN if broker_order['CashMargin'] == 2 else Offset.CLOSE,  # 暂时设为NONE，后续可根据CashMargin和DelivType判断
            price=float(broker_order["Price"]),
            volume=volume,
            traded=traded,  # 累计成交量
            status=state,
            datetime=dt,
            reference=""  # 可以根据需要设置
        )
        
        return order

    def _add_order(self, order: OrderData):
        """添加新订单到本地缓存"""
        self.local_orders[order.orderid] = order
        self.write_log(f"添加订单到缓存: {order.orderid}")

    def query_local_order(self, orderid: str) -> OrderData:
        """查询本地缓存中的订单"""
        return self.local_orders.get(orderid)

    # not used for now
    def update_order(self, order: OrderData):
        """更新订单状态"""
        orderid = order.orderid
        old_order = self.local_orders.get(orderid)
        if old_order and (old_order.status != order.status or old_order.traded != order.traded):
            # 状态发生变化，需要推送事件
            return True
        self.local_orders[orderid] = order
        return False

    # not used for now
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
    
    def _init_replay_engine(self, setting: dict) -> None:
        """初始化replay引擎"""
        self.replay_engine = KabusReplayEngine(setting, self)
    
    def start_replay(self, date: str, symbols: list = None) -> None:
        """开始历史数据回放"""
        if self.replay_engine:
            self.replay_engine.start_replay()
        else:
            self.write_log("Replay引擎未初始化")
    
    def stop_replay(self) -> None:
        """停止历史数据回放"""
        if self.replay_engine:
            self.replay_engine.stop_replay()
        else:
            self.write_log("Replay引擎未初始化")


class KabusReplayEngine:
    """Kabus历史数据回放引擎"""
    
    def __init__(self, config: dict, gateway):
        self.config = config
        self.gateway = gateway
        self.replay_data_dir = config.get("replay_data_dir", "")
        self.replay_date = config.get("replay_date", "")
        self.replay_speed = config.get("replay_speed", 1.0)
        
        self.replay_data = []
        self.replay_thread = None
        self.active = False
        self.paused = False
        
        # 字段名解压缩映射（反向映射）
        self.field_decompress_map = {
            "s": "Symbol",
            "sn": "SymbolName",
            "ex": "Exchange",
            "exn": "ExchangeName",
            "st": "SecurityType",
            "ct": "currentTime",
            "px": "CurrentPrice",
            "pxt": "CurrentPriceTime",
            "pxcs": "CurrentPriceChangeStatus",
            "pxst": "CurrentPriceStatus",
            "cpx": "CalcPrice",
            "pc": "PreviousClose",
            "pct": "PreviousCloseTime",
            "chg": "ChangePreviousClose",
            "chgp": "ChangePreviousClosePer",
            "op": "OpeningPrice",
            "opt": "OpeningPriceTime",
            "hp": "HighPrice",
            "hpt": "HighPriceTime",
            "lp": "LowPrice",
            "lpt": "LowPriceTime",
            "v": "TradingVolume",
            "vt": "TradingVolumeTime",
            "vwap": "VWAP",
            "tv": "TradingValue",
            "clr": "ClearingPrice",
        }
    
    def load_replay_data(self) -> bool:
        """加载回放数据"""
        if not self.replay_date or not self.replay_data_dir:
            self.gateway.write_log("回放配置不完整")
            return False
        
        try:
            # 标准化日期格式：支持多种输入格式（2026-01-09, 20260109等）
            date_str = self.replay_date.replace("-", "").replace("/", "").replace("_", "")
            if len(date_str) == 8:  # YYYYMMDD格式
                normalized_date = date_str
            else:
                # 尝试解析其他格式
                normalized_date = self.replay_date
            
            # 查找指定日期的jsonl文件
            # 支持多种文件命名格式
            patterns = [
                os.path.join(self.replay_data_dir, f"*{normalized_date}*.jsonl"),
                os.path.join(self.replay_data_dir, f"*{self.replay_date}*.jsonl"),  # 保留原始格式
                os.path.join(self.replay_data_dir, f"orderbook_*_{normalized_date}*.jsonl"),
                os.path.join(self.replay_data_dir, f"orderbook_*_{self.replay_date}*.jsonl"),
            ]
            
            files = []
            for pattern in patterns:
                files.extend(glob.glob(pattern))
            
            # 去重
            files = list(set(files))
            
            if not files:
                self.gateway.write_log(f"未找到{self.replay_date}的历史数据文件，搜索路径: {self.replay_data_dir}")
                self.gateway.write_log(f"尝试的搜索模式: {patterns}")
                return False
            
            # 加载和排序数据
            self.gateway.write_log(f"加载回放数据文件: {len(files)} 个")
            self.replay_data = self._load_and_sort_data(files)
            self.gateway.write_log(f"加载回放数据成功，共{len(self.replay_data)}条记录")
            return True
            
        except Exception as e:
            self.gateway.write_log(f"加载回放数据失败: {e}")
            import traceback
            self.gateway.write_log(traceback.format_exc())
            return False
    
    def _load_and_sort_data(self, files: List[str]) -> List[Dict]:
        """加载并排序数据"""
        replay_data = []
        
        for file_path in files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        if not line.strip():
                            continue
                        try:
                            compressed_data = json.loads(line)
                            # 解压缩数据
                            decompressed_data = self._decompress_message(compressed_data)
                            
                            # 提取时间戳用于排序
                            current_time_str = decompressed_data.get("currentTime", "")
                            if not current_time_str:
                                continue
                            
                            # 解析时间戳
                            try:
                                # 处理ISO 8601格式的时间字符串
                                dt = datetime.fromisoformat(current_time_str.replace('Z', '+00:00'))
                                timestamp = dt.timestamp()
                            except Exception as e:
                                self.gateway.write_log(f"解析时间戳失败: {current_time_str}, error: {e}")
                                continue
                            
                            replay_data.append({
                                'timestamp': timestamp,
                                'data': decompressed_data
                            })
                        except json.JSONDecodeError as e:
                            self.gateway.write_log(f"解析JSON失败: {file_path}:{line_num}, error: {e}")
                            continue
            except Exception as e:
                self.gateway.write_log(f"读取文件{file_path}失败: {e}")
                continue
        
        # 按时间戳排序
        replay_data.sort(key=lambda x: x['timestamp'])
        return replay_data
    
    def _decompress_message(self, compressed: Dict) -> Dict:
        """解压缩消息（将短字段名还原为长字段名）"""
        decompressed = {}
        
        # 解压缩顶层字段
        for short_key, long_key in self.field_decompress_map.items():
            if short_key in compressed:
                decompressed[long_key] = compressed[short_key]
        
        # 解压缩订单簿数据
        if "S" in compressed:
            sell_orderbook = self._decompress_orderbook_side(compressed["S"], "Sell")
            decompressed.update(sell_orderbook)
        
        if "B" in compressed:
            buy_orderbook = self._decompress_orderbook_side(compressed["B"], "Buy")
            decompressed.update(buy_orderbook)
        
        return decompressed
    
    def _decompress_orderbook_side(self, levels: List, prefix: str) -> Dict:
        """解压缩订单簿一侧的数据"""
        orderbook = {}
        for i, level in enumerate(levels, 1):
            if level is None:
                continue
            if isinstance(level, list) and len(level) >= 2:
                price = level[0]
                qty = level[1]
                sign = level[2] if len(level) > 2 else None
                
                if price is not None and qty is not None and (price != 0.0 or qty != 0.0):
                    level_data = {"Price": price, "Qty": qty}
                    if sign is not None:
                        level_data["Sign"] = sign
                    orderbook[f"{prefix}{i}"] = level_data
        
        return orderbook
    
    def start_replay(self) -> None:
        """开始回放"""
        if not self.replay_data:
            if not self.load_replay_data():
                return
        
        # 检查订阅状态
        if not self.gateway._subscribed_symbols:
            self.gateway.write_log("警告: 开始replay时没有已订阅的symbols，replay数据将被过滤")
        else:
            self.gateway.write_log(f"开始replay，已订阅的symbols: {list(self.gateway._subscribed_symbols)}")
        
        self.active = True
        self.paused = False
        self.replay_thread = threading.Thread(target=self._run_replay)
        self.replay_thread.daemon = True
        self.replay_thread.start()
        self.gateway.write_log("开始历史数据回放")
    
    def stop_replay(self) -> None:
        """停止回放"""
        self.active = False
        if self.replay_thread and self.replay_thread.is_alive():
            self.replay_thread.join(timeout=2.0)
        self.gateway.write_log("停止历史数据回放")
    
    def _run_replay(self) -> None:
        """运行回放循环"""
        if not self.replay_data:
            return
        print('start replay')
        last_timestamp = None
        
        for i, item in enumerate(self.replay_data):
            if not self.active:
                break
            
            # 处理暂停
            while self.paused and self.active:
                time.sleep(0.1)
            
            if not self.active:
                break
            
            # 计算时间间隔
            if last_timestamp is not None:
                time_diff = item['timestamp'] - last_timestamp
                sleep_time = time_diff / self.replay_speed
                if sleep_time > 0:
                    time.sleep(sleep_time)
            
            last_timestamp = item['timestamp']
            
            # 转换并推送tick数据
            data = item['data']
            symbol = data.get("Symbol")
            
            # 调试信息：每100条记录打印一次
            if i % 100 == 0:
                self.gateway.write_log(f"Replay进度: {i}/{len(self.replay_data)}, symbol: {symbol}, subscribed: {symbol in self.gateway._subscribed_symbols if symbol else False}")
            
            if symbol:
                # 检查是否已订阅（如果未订阅，记录日志但不阻止处理，因为订阅可能在replay开始后才完成）
                if symbol not in self.gateway._subscribed_symbols:
                    # 只在第一次遇到未订阅的symbol时记录
                    if i < 10 or i % 1000 == 0:
                        self.gateway.write_log(f"跳过未订阅的symbol: {symbol} (已订阅: {list(self.gateway._subscribed_symbols)})")
                    continue
                
                # 使用gateway的转换方法
                tick = self.gateway._convert_kabus_message_to_tick(symbol, data)
                if tick:
                    self.gateway.on_tick(tick)
                else:
                    if i < 10:
                        self.gateway.write_log(f"转换tick失败: symbol={symbol}")