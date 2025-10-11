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

from vnpy.trader.object import Exchange, Product, ContractData, TickData, OrderRequest, CancelRequest, HistoryRequest, SubscribeRequest, BarData, OrderData
from vnpy.trader.gateway import BaseGateway
from vnpy.event import EventEngine
from vnpy.trader.constant import Exchange, Interval, Direction, Offset, Status, OrderType

# from common import kabus_api
from common import click_api
from common.trading_common import TradingSide, FrontOrderType

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
    Direction.LONG: 'long',
    Direction.SHORT: 'short',
}

class BriskClickGateway(BaseGateway):
    """
    Brisk Gateway for Japanese Stock Market
    """

    default_name: str = "BRISK_CLICK"
    default_setting: Dict[str, str | int | float | bool] = {
        "tick_server_url": "ws://127.0.0.1:8001/ws",
        "tick_server_http_url": "http://127.0.0.1:8001",
        "reconnect_interval": 5,
        "heartbeat_interval": 30,
        "max_reconnect_attempts": 20,
        "polling_interval": 5,  # 订单状态轮询间隔（秒）
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
        self.formatted_date: str = today.strftime("%Y%m%d")
        # self.last_updtime: str = "20250725085000"  # temporarily setting this for testing

        self.polling_interval: int = 1  # 轮询间隔（秒）
        self._polling_active: bool = False

        click_api.init_gmo_click()
        test_query_orders = click_api.query_orders()
        if not test_query_orders:
            self.write_log("Click API is not working")
            return
        else:
            self.write_log("Click API init done")

        # 锁
        self._lock: threading.Lock = threading.Lock()

    def connect(self, setting: Dict) -> None:
        """连接服务器"""
        self._ws_url = setting.get("tick_server_url", self.default_setting["tick_server_url"])
        self._http_url = setting.get("tick_server_http_url", self.default_setting["tick_server_http_url"])
        self._reconnect_interval = setting.get("reconnect_interval", self.default_setting["reconnect_interval"])
        self._heartbeat_interval = setting.get("heartbeat_interval", self.default_setting["heartbeat_interval"])
        self._max_reconnect_attempts = setting.get("max_reconnect_attempts", self.default_setting["max_reconnect_attempts"])
        self.polling_interval = setting.get("polling_interval", self.default_setting["polling_interval"])

        self._active = True
        
        self._ws_thread = threading.Thread(target=self._run_websocket)
        self._ws_thread.daemon = True
        self._ws_thread.start()

        # 启动订单状态轮询线程
        self._start_polling_thread()

        # 启动心跳检测
        self._heartbeat_thread = threading.Thread(target=self._run_heartbeat)
        self._heartbeat_thread.daemon = True
        self._heartbeat_thread.start()

        self.write_log("Brisk Gateway启动成功")

    def close(self) -> None:
        """关闭连接"""
        self._active = False
        self._connected = False
        self._polling_active = False

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

    # TODO: need update to brisk api: done
    def send_order(self, req: OrderRequest) -> str:
        self.write_log(f"send_order: {req}")
        # note order_id is actually a custom order id created by ourselves, it can't be used to cancel the order. the parameter to cancel order is order key
        order_id = None

        status_ok, custom_order_id, raw_xml = click_api.send_order(
            req.symbol, int(req.volume), req.price, True if not req.price else False, Direction_to_TradingSide[req.direction], 'open' if req.offset == Offset.OPEN else 'close')
        if status_ok:
            order_id = custom_order_id            
        
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
        
        # special sleep because this is a web simulation api
        time.sleep(0.2)
        return order_id

    # TODO: need check: done
    def query_order_key_from_order_id(self, order_id: str) -> str:
        order = self.local_orders.get(order_id)
        if order:
            return order.orderkey
        return None
        
    # TODO: need update to brisk api: done
    def cancel_order(self, req: CancelRequest) -> None:
        order_key = self.query_order_key_from_order_id(req.orderid)
        if not order_key:
            raise Exception(f"撤销委托失败: {req.orderid}")
        cancel_result = click_api.cancel_order(order_key)
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
    
    # TODO: need update to brisk api: done
    def get_positions(self) -> List[dict]:
        """获取实际持仓数据
        
        Returns:
            List[dict]: 持仓数据列表，每个元素包含 Symbol, LeavesQty, HoldQty, Side 等
        """
        raise NotImplementedError("to be implemented")

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
            self._ws = await websockets.connect(self._ws_url, ping_timeout=None)
            self._connected = True
            self._reconnect_attempts = 0
            # 设置心跳时间为过去的时间，确保立即发送第一个ping，但不会触发超时
            self._last_heartbeat = time.time() - self._heartbeat_interval + 1
            self.write_log("WebSocket连接成功")

            # 发送订阅消息
            await self._send_subscribe_message()

            # 接收消息
            async for message in self._ws:
                if not self._active:
                    break
                await self._on_message(message)

        except ConnectionClosed as e:
            self.write_log(f"WebSocket连接已关闭: {e}")
            self.write_log(f"ConnectionClosed异常即将重新抛出")
            raise  # 重新抛出异常以触发重连
        except WebSocketException as e:
            self.write_log(f"WebSocket异常: {e}")
            self.write_log(f"WebSocketException异常即将重新抛出")
            raise  # 重新抛出异常以触发重连
        except Exception as e:
            self.write_log(f"WebSocket连接失败: {e}")
            self.write_log(f"Exception异常即将重新抛出")
            raise  # 重新抛出异常以触发重连
        finally:
            self._connected = False
            if self._ws:
                try:
                    await self._ws.close()
                except Exception as e:
                    self.write_log(f"关闭WebSocket连接时出错: {e}")
                finally:
                    self._ws = None

    async def _send_subscribe_message(self) -> None:
        """发送订阅消息"""
        if not self._ws:
            return

        subscribe_msg = {
            "type": "subscribe",
            "symbols": list(self._subscribed_symbols)
        }
        self.write_log(f"发送订阅消息: {subscribe_msg}")
        try:
            await self._ws.send(json.dumps(subscribe_msg))
        except Exception as e:
            self.write_log(f"发送订阅消息失败: {e}")
            raise  # 重新抛出异常以触发重连

    async def _on_message(self, message: str) -> None:
        """处理接收到的消息"""
        try:
            data = json.loads(message)
            
            # 处理tick数据
            if "frames" in data:
                await self._process_tick_data(data["frames"])
            
            # 处理心跳pong响应
            elif data.get("type") == "pong":
                self._last_heartbeat = time.time()
                self.write_log("收到心跳pong响应")
                
        except json.JSONDecodeError as e:
            self.write_log(f"JSON解析失败: {e}")
        except Exception as e:
            self.write_log(f"消息处理失败: {e}")
            # 如果是连接相关异常，重新抛出以触发重连
            if "ConnectionClosed" in str(type(e)) or "WebSocketException" in str(type(e)):
                raise

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
            base_date = datetime.strptime(date_str, "%Y%m%d")
            #.replace(tzinfo=ZoneInfo("Asia/Tokyo"))
            
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
                if self._connected and self._ws:
                    current_time = time.time()
                    time_since_last_heartbeat = current_time - self._last_heartbeat
                    
                    # 添加调试日志
                    self.write_log(f"心跳检测: 连接状态={self._connected}, 距离上次心跳={time_since_last_heartbeat:.1f}秒, 心跳间隔={self._heartbeat_interval}秒")
                    
                    # 先检查心跳超时（超过2倍间隔没有收到pong）
                    if time_since_last_heartbeat > self._heartbeat_interval * 3:
                        self.write_log("心跳超时，准备重连")
                        self._connected = False
                        # 强制关闭连接以触发重连
                        try:
                            asyncio.run(self._ws.close())
                            self.write_log("心跳检测：已关闭WebSocket连接")
                        except Exception as e:
                            self.write_log(f"心跳检测：关闭连接失败: {e}")
                        break
                    
                    # 再检查是否超过心跳间隔，需要发送ping
                    elif time_since_last_heartbeat > self._heartbeat_interval:
                        # 发送ping消息
                        try:
                            ping_msg = {"type": "ping"}
                            asyncio.run(self._ws.send(json.dumps(ping_msg)))
                            self.write_log("发送心跳ping")
                            # 更新心跳时间，避免重复发送
                            self._last_heartbeat = current_time
                            self.write_log(f"更新心跳时间后: _last_heartbeat={self._last_heartbeat}")
                        except Exception as e:
                            self.write_log(f"发送心跳ping失败: {e}")
                            self._connected = False
                            break
                else:
                    # 添加调试日志：为什么心跳检测被跳过
                    self.write_log(f"心跳检测跳过: _connected={self._connected}, _ws={self._ws is not None}")
                
                time.sleep(self._heartbeat_interval)
            except Exception as e:
                self.write_log(f"心跳检测异常: {e}")

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

    # TODO: need update to click api: done
    def _poll_orders(self):
        """轮询订单状态"""
        # click can only return full day orders
        orders = click_api.query_orders()

        # none return means error
        if not orders:
            self.write_log(f"empty orders or error")
            return

        # 3. 遍历订单，转换格式，检测状态变化
        for broker_order in orders:
            try:
                order = self._convert_broker_order_to_vnpy(broker_order)
                if not order:
                    # self.write_log(f"skip irregular or non-margin order: {broker_order}")
                    continue
                orderid = order.orderid
                old_order = self.local_orders.get(orderid)
                # 检测状态变化：状态不同 或 成交量不同
                if (not old_order) or (old_order.status != order.status or old_order.traded != order.traded):
                    self.local_orders[orderid] = order
                    self.on_order(order)  # 推送事件
                    self.write_log(f"订单状态更新: {orderid} {order.symbol} {old_order.status if old_order else 'NEW'} -> {order.status}")
                # else:
                #     self.write_log(f"WARNING: click query order API: 订单状态未变化: {orderid} {old_order.status if old_order else 'NEW'} -> {order.status}")
            except Exception as e:
                self.write_log(f"订单转换失败: {e}")

    # TODO: need update to click api: done
    def query_single_order(self, orderid: str) -> OrderData:
        """查询单个订单"""
        raise NotImplementedError("to be implemented")
        # try:
        #     broker_order = kabus_api.query_order_status(orderid)
        #     order = self._convert_broker_order_to_vnpy(broker_order)
        #     old_order = self.local_orders.get(orderid)
        #     if (not old_order) or (old_order.status != order.status or old_order.traded != order.traded):
        #         self.local_orders[orderid] = order
        #         self.on_order(order)  # 推送事件
        #         self.write_log(f"(query_single_order) 订单状态更新: {orderid} {old_order.status if old_order else 'NEW'} -> {order.status}")
        #     else:
        #         self.write_log(f"(query_single_order) WARNING: kabus query order API: 订单状态未变化: {orderid} {old_order.status if old_order else 'NEW'} -> {order.status}")

        #     return order
        # except Exception as e:
        #     self.write_log(f"查询订单失败: {e}")
        #     return None

    # TODO: need update to click api: done
    # {'orderModify': '変更',
    #     'orderCancel': '取消',
    #     'meigara': '大成建設1801東証',
    #     'meigaraName': '大成建設',
    #     'securityCode': '1801',
    #     'marketCode': '東証',
    #     'torihikiKbn': '信用返済',
    #     'baibaiKbn': '売',
    #     'orderAmount': 100.0,
    #     'notExecutionAmount': 100.0,
    #     'limitPrice': None,
    #     'realPrice': 10755.0,
    #     'tateTanka': 10990.0,
    #     'leaveOrderType': '通常',
    #     'triggerPrice': '',
    #     'shikkouKbn': 'なし',
    #     'orderStatus': '発注受付',
    #     'failureReason': '',
    #     'kouzaKbn': '特定',
    #     'shinyouKbn': '一般(無期限)',
    #     'jyuchuDatetime': '10/09  21:30',
    #     'actualInvalidDate': '10/10まで',
    #     'orderKey': '0001',
    #     'orderKeyLink': '0001',
    #     'modifyHistory': '取消・変更の履歴閉じる',
    #     'ajx': '',
    #     'orderModify_href': 'https://kabu.click-sec.com/sec1/kabu/orderModify.do?orderKey=251010110340770001',
    #     'orderCancel_href': 'https://kabu.click-sec.com/sec1/kabu/orderCancel.do?orderKey=251010110340770001',
    #     'meigara_href': 'https://kabu.click-sec.com/sec1/kabu/meigaraInfo.do?meigaraCode=0180100',
    #     'orderKeyLink_onclick': "CLK_OrderModifyHistory.openWindow(this, {url: 'https://kabu.click-sec.com/sec1/kabu/ajax/orderModifyHistory.do',orderKey: '251010110340770001',divId:'#ajx0'})",
    #     'orderKey_long': '251010110340770001',
    #     'orderKeyLink_href': 'javascript:void(0);',
    #     'customOrderId': '1801_close_100_short_202510092130'}
    def _convert_broker_order_to_vnpy(self, broker_order: Dict) -> OrderData:
        """将kabus API订单格式转换为vnpy格式"""

        if not broker_order.get('torihikiKbn') in ['信用返済', '信用新規']:
            return None

        volume = float(broker_order.get('orderAmount', 0))
        traded = float(broker_order.get('yakujyoSuuryo', 0))

        state = Status.SUBMITTING
        broker_status = broker_order["orderStatus"]
        if broker_status == '一部約定':
            state = Status.PARTTRADED
        elif broker_status == '全量約定':
            state = Status.ALLTRADED
        # elif broker_status in ['7', '12']: # canceled order will not show up in the order list
        #     state = Status.CANCELLED
        elif broker_status == '発注受付':
            state = Status.NOTTRADED
        else:
            state = Status.SUBMITTING
        
        # 方向映射 (基于broker_order['Side'])
        direction_mapping = {
            "売": Direction.SHORT,    # 1=卖出
            "買": Direction.LONG,     # 2=买入
        }
        
        # 解析时间: e.g. '20250930090301'
        recv_time = broker_order["customOrderId"][-12:]
        # recv_time is in JST
        dt = datetime.strptime(recv_time, "%Y%m%d%H%M")
        
        order = OrderData(
            gateway_name=self.gateway_name,
            symbol=broker_order["securityCode"],
            exchange=Exchange.TSE,
            orderid=broker_order["customOrderId"],
            type=OrderType.LIMIT if broker_order['limitPrice'] else OrderType.MARKET,
            direction=direction_mapping.get(broker_order["baibaiKbn"], Direction.LONG),
            offset=Offset.OPEN if broker_order['torihikiKbn'] == '信用新規' else Offset.CLOSE,  # 暂时设为NONE，后续可根据CashMargin和DelivType判断
            price=0 if not broker_order["limitPrice"] else float(broker_order["limitPrice"]),
            volume=volume,
            traded=traded,  # 累计成交量
            status=state,
            datetime=dt,
            reference=""  # 可以根据需要设置
        )

        order.orderkey = broker_order["orderKey_long"]

        # self.write_log(f"symbol: {order.symbol}, offset: {order.offset}, price: {order.price}, direction: {order.direction}, state: {order.status}, volume: {order.volume}, traded: {order.traded}, datetime: {order.datetime}")

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
