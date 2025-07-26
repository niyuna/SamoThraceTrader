"""
Mock Brisk Gateway for Testing
支持Mock tick数据和历史数据回放
交易功能完全Mock化
"""

import os
import json
import glob
import time
import threading
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
from zoneinfo import ZoneInfo

from vnpy.trader.object import (
    Exchange, Product, ContractData, TickData, OrderData, TradeData,
    OrderRequest, CancelRequest, HistoryRequest, SubscribeRequest, 
    BarData, PositionData, AccountData
)
from vnpy.trader.gateway import BaseGateway
from vnpy.event import EventEngine
from vnpy.trader.constant import Status, Direction, Offset, OrderType


class MockTickGenerator:
    """模拟tick数据生成器"""
    
    def __init__(self, config: dict, gateway):
        self.config = config
        self.gateway = gateway
        self.base_prices = config.get("mock_base_prices", {})
        self.current_prices = {}
        self.volume_cache = {}
        self.turnover_cache = {}
        self.active_symbols = set()
        self.tick_thread = None
        self.active = False
        
        # 从配置中获取参数
        self.tick_interval = config.get("mock_tick_interval", 1.0)
        self.price_volatility = config.get("mock_price_volatility", 0.01)
        self.volume_range = config.get("mock_volume_range", (100, 1000))
        
    def add_symbol(self, symbol: str) -> None:
        """添加股票到Mock生成器"""
        self.active_symbols.add(symbol)
        
        # 初始化价格
        if symbol not in self.base_prices:
            self.base_prices[symbol] = self._generate_base_price(symbol)
        self.current_prices[symbol] = self.base_prices[symbol]
        
        # 初始化缓存
        self.volume_cache[symbol] = {
            'last_volume': 0,
            'current_volume': 0,
            'last_turnover': 0,
            'current_turnover': 0,
            'last_timestamp': 0,
            'last_date': None
        }
        
        self.gateway.write_log(f"Mock Tick Generator: 添加股票 {symbol}")
        
    def start(self) -> None:
        """启动Mock tick生成"""
        self.active = True
        self.tick_thread = threading.Thread(target=self._run_tick_generation)
        self.tick_thread.daemon = True
        self.tick_thread.start()
        self.gateway.write_log("Mock Tick Generator: 启动成功")
        
    def stop(self) -> None:
        """停止Mock tick生成"""
        self.active = False
        # 等待线程结束
        if self.tick_thread and self.tick_thread.is_alive():
            self.tick_thread.join(timeout=2.0)
        self.gateway.write_log("Mock Tick Generator: 停止")
        
    def reset(self) -> None:
        """重置状态"""
        self.current_prices = {}
        self.volume_cache = {}
        self.turnover_cache = {}
        for symbol in self.active_symbols:
            if symbol in self.base_prices:
                self.current_prices[symbol] = self.base_prices[symbol]
                
    def _run_tick_generation(self) -> None:
        """运行tick生成循环"""
        while self.active:
            for symbol in self.active_symbols:
                tick = self.generate_tick(symbol, datetime.now())
                if tick:
                    self.gateway.on_tick(tick)
            
            time.sleep(self.tick_interval)
            
    def generate_tick(self, symbol: str, timestamp: datetime) -> Optional[TickData]:
        """生成模拟tick数据"""
        try:
            # 1. 生成价格波动
            price_change = random.gauss(0, self.price_volatility)
            new_price = self.current_prices[symbol] * (1 + price_change)
            
            # 确保价格为正数
            new_price = max(new_price, 1.0)
            
            # 2. 生成成交量
            volume = random.randint(self.volume_range[0], self.volume_range[1])
            
            # 3. 更新缓存
            self.current_prices[symbol] = new_price
            self._update_volume_cache(symbol, volume, new_price)
            
            # 4. 创建TickData
            tick = TickData(
                symbol=symbol,
                exchange=Exchange.TSE,
                datetime=timestamp,
                last_price=new_price,
                last_volume=volume,
                volume=self.volume_cache[symbol]['current_volume'],
                turnover=self.volume_cache[symbol]['current_turnover'],
                gateway_name="MOCK_BRISK"
            )
            
            return tick
            
        except Exception as e:
            self.gateway.write_log(f"生成Mock Tick失败: {e}")
            return None
            
    def _generate_base_price(self, symbol: str) -> float:
        """生成基准价格"""
        # 根据股票代码生成合理的基准价格
        if symbol == "7203":  # 丰田
            return 2500.0
        elif symbol == "6758":  # 索尼
            return 1800.0
        elif symbol == "9984":  # 软银
            return 8000.0
        else:
            # 随机生成一个合理的价格
            return random.uniform(1000.0, 10000.0)
            
    def _update_volume_cache(self, symbol: str, volume: int, price: float) -> None:
        """更新成交量缓存"""
        cache = self.volume_cache[symbol]
        current_date = datetime.now().date()
        
        # 如果是新的一天，重置累计数据
        if cache['last_date'] != current_date:
            cache['current_volume'] = volume
            cache['current_turnover'] = volume * price
            cache['last_date'] = current_date
        else:
            cache['current_volume'] += volume
            cache['current_turnover'] += volume * price
            
        cache['last_volume'] = volume
        cache['last_turnover'] = volume * price
        cache['last_timestamp'] = time.time()


class HistoricalReplayEngine:
    """历史数据回放引擎"""
    
    def __init__(self, config: dict, gateway):
        self.config = config
        self.gateway = gateway
        self.data_dir = config.get("replay_data_dir", "")
        self.replay_date = config.get("replay_date", "")
        self.replay_speed = config.get("replay_speed", 1.0)
        
        self.replay_data = []
        self.replay_index = 0
        self.replay_thread = None
        self.active = False
        self.paused = False
        
    def load_replay_data(self) -> bool:
        """加载回放数据"""
        if not self.replay_date or not self.data_dir:
            self.gateway.write_log("回放配置不完整")
            return False
            
        try:
            # 查找指定日期的数据文件
            pattern = os.path.join(self.data_dir, f"brisk_in_day_frames_{self.replay_date}_*.json")
            files = glob.glob(pattern)
            
            if not files:
                self.gateway.write_log(f"未找到{self.replay_date}的历史数据文件")
                return False
                
            # 加载和排序数据
            self.replay_data = self._load_and_sort_data(files)
            self.gateway.write_log(f"加载回放数据成功，共{len(self.replay_data)}条记录")
            return True
            
        except Exception as e:
            self.gateway.write_log(f"加载回放数据失败: {e}")
            return False
            
    def start_replay(self) -> None:
        """开始回放"""
        if not self.replay_data:
            if not self.load_replay_data():
                return
                
        self.active = True
        self.paused = False
        self.replay_thread = threading.Thread(target=self._run_replay)
        self.replay_thread.daemon = True
        self.replay_thread.start()
        self.gateway.write_log("开始历史数据回放")
        
    def stop_replay(self) -> None:
        """停止回放"""
        self.active = False
        # 等待线程结束
        if self.replay_thread and self.replay_thread.is_alive():
            self.replay_thread.join(timeout=2.0)
        self.gateway.write_log("停止历史数据回放")
        
    def pause(self) -> None:
        """暂停回放"""
        self.paused = True
        self.gateway.write_log("暂停历史数据回放")
        
    def resume(self) -> None:
        """恢复回放"""
        self.paused = False
        self.gateway.write_log("恢复历史数据回放")
        
    def _load_and_sort_data(self, files: List[str]) -> List[Dict]:
        """加载并排序数据"""
        replay_data = []
        
        for file_path in files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # 提取时间戳
                    filename = os.path.basename(file_path)
                    timestamp_str = filename.split('_')[-1].replace('.json', '')
                    timestamp = int(timestamp_str)
                    
                    # 处理每个股票的数据（加载所有股票的数据）
                    for symbol, frames in data.items():
                        for frame in frames:
                            replay_data.append({
                                'timestamp': frame.get("timestamp", 0),
                                'symbol': symbol,
                                'frame': frame,
                                'date_str': self.replay_date
                            })
                            
            except Exception as e:
                self.gateway.write_log(f"读取文件{file_path}失败: {e}")
                continue

        # 按时间戳排序
        replay_data.sort(key=lambda x: x['timestamp'])
        return replay_data
        
    def _run_replay(self) -> None:
        """运行回放循环"""
        if not self.replay_data:
            return
            
        last_timestamp = None
        
        for i, data in enumerate(self.replay_data):
            if not self.active:
                break
                
            # 处理暂停
            while self.paused and self.active:
                time.sleep(0.1)
                
            if not self.active:
                break
                
            # 计算时间间隔
            if last_timestamp is not None:
                time_diff = (data['timestamp'] - last_timestamp) / 1000000  # 转换为秒
                sleep_time = time_diff / self.replay_speed
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    
            last_timestamp = data['timestamp']
            
            # 转换并推送tick数据（只推送已订阅的股票）
            tick = self._convert_frame_to_tick(data)
            if tick and tick.symbol in self.gateway.subscribed_symbols:
                self.gateway.on_tick(tick)
                
    def _convert_frame_to_tick(self, data: Dict) -> Optional[TickData]:
        """转换frame数据为tick数据"""
        try:
            frame = data['frame']
            symbol = data['symbol']
            date_str = data['date_str']
            
            # 转换价格（price10 / 10）
            price = frame.get("price10", 0) / 10.0
            volume = frame.get("quantity", 0)
            
            # 解析时间戳 - frame中的timestamp是距离当天JST 0点的微秒数
            micro_seconds = frame.get("timestamp", 0)
            
            # 创建当天0点的时间
            base_date = datetime.strptime(date_str, "%Y%m%d").replace(tzinfo=ZoneInfo("Asia/Tokyo"))
            
            # 将微秒转换为秒，然后加到基础时间上
            seconds = micro_seconds / 1_000_000  # 微秒转秒
            dt = base_date + timedelta(seconds=seconds)
            
            tick = TickData(
                symbol=symbol,
                exchange=Exchange.TSE,
                datetime=dt,
                last_price=price,
                last_volume=volume,
                volume=volume,
                turnover=price * volume,
                gateway_name="MOCK_BRISK"
            )
            
            return tick
            
        except Exception as e:
            self.gateway.write_log(f"转换tick数据失败: {e}")
            return None


class MockTradingEngine:
    """模拟交易引擎"""
    
    def __init__(self, config: dict, gateway):
        self.config = config
        self.gateway = gateway
        self.orders = {}  # 订单缓存
        self.trades = {}  # 成交缓存
        self.positions = {}  # 持仓缓存
        self.order_id_counter = 0
        self.trade_id_counter = 0
        
        # 从配置中获取参数
        self.account_balance = config.get("mock_account_balance", 10000000)
        self.commission_rate = config.get("mock_commission_rate", 0.001)
        self.slippage = config.get("mock_slippage", 0.0)
        self.fill_delay = config.get("mock_fill_delay", 0.1)
        self.auto_process_orders = config.get("mock_auto_process_orders", True)
        
        # 创建模拟账户
        self.account = self._create_mock_account()
        
    def send_order(self, req: OrderRequest) -> str:
        """发送订单"""
        order_id = f"MOCK_{self.order_id_counter}"
        self.order_id_counter += 1
        
        # 创建订单数据
        order = OrderData(
            symbol=req.symbol,
            exchange=req.exchange,
            orderid=order_id,
            type=req.type,
            direction=req.direction,
            offset=req.offset,
            price=req.price,
            volume=req.volume,
            status=Status.SUBMITTING,
            gateway_name="MOCK_BRISK"
        )
        
        self.orders[order_id] = order
        
        # 推送订单事件
        self.gateway.on_order(order)
        
        # 只有在启用自动处理时才模拟订单处理
        if self.auto_process_orders:
            self._process_order(order)
        
        print(f'send_order: {order}')
        return order_id
        
    def cancel_order(self, req: CancelRequest) -> None:
        """撤销订单"""
        if req.orderid in self.orders:
            order = self.orders[req.orderid]
            if order.status == Status.SUBMITTING:
                order.status = Status.CANCELLED
                self.gateway.on_order(order)
                self.gateway.write_log(f"订单撤销成功: {req.orderid}")
            else:
                self.gateway.write_log(f"订单状态不允许撤销: {req.orderid} - {order.status}")
        else:
            self.gateway.write_log(f"未找到订单: {req.orderid}")
            
    def get_account(self) -> AccountData:
        """获取账户信息"""
        return self.account
        
    def get_positions(self) -> Dict[str, PositionData]:
        """获取持仓信息"""
        return self.positions
        
    def reset(self) -> None:
        """重置状态"""
        self.orders.clear()
        self.trades.clear()
        self.positions.clear()
        # 重新创建模拟账户
        self.account = self._create_mock_account()
        self.order_id_counter = 0
        self.trade_id_counter = 0
    
    def manually_process_order(self, order_id: str, target_status: Status) -> bool:
        """手动处理订单状态（用于测试）"""
        if order_id not in self.orders:
            return False
        
        order = self.orders[order_id]
        # 如果订单成交，生成成交事件
        if target_status == Status.ALLTRADED:
            # no need to trigger on_order here because _fill_order will do that
            self._fill_order(order)
        else:
            self.gateway.on_order(order)
        
        return True
    
    def get_order_by_id(self, order_id: str) -> Optional[OrderData]:
        """根据订单ID获取订单（用于测试）"""
        return self.orders.get(order_id)
        
    def _create_mock_account(self) -> AccountData:
        """创建模拟账户"""
        return AccountData(
            accountid="MOCK_ACCOUNT",
            balance=self.account_balance,
            frozen=0.0,
            gateway_name="MOCK_BRISK"
        )
        
    def _process_order(self, order: OrderData) -> None:
        """处理订单（模拟成交逻辑）"""
        # 模拟订单成交
        if order.status == Status.SUBMITTING:
            # 根据订单类型和当前价格判断是否成交
            if self._should_fill_order(order):
                # 延迟成交
                threading.Timer(self.fill_delay, self._fill_order, args=[order]).start()
                
    def _should_fill_order(self, order: OrderData) -> bool:
        """判断订单是否应该成交"""
        # 简化逻辑：市价单立即成交，限价单根据价格判断
        if order.type == OrderType.MARKET:
            return True
        elif order.type == OrderType.LIMIT:
            # 这里需要获取当前市场价格来判断
            # 简化处理：80%概率成交
            return random.random() < 0.8
        return False
        
    def _fill_order(self, order: OrderData) -> None:
        """成交订单"""
        if order.status != Status.SUBMITTING:
            return
            
        # 更新订单状态
        order.status = Status.ALLTRADED
        order.traded = order.volume
        
        # 创建成交记录
        trade_id = f"MOCK_TRADE_{self.trade_id_counter}"
        self.trade_id_counter += 1
        
        # 计算成交价格（考虑滑点）
        fill_price = order.price
        if order.direction == Direction.LONG:
            fill_price *= (1 + self.slippage)
        else:
            fill_price *= (1 - self.slippage)
            
        trade = TradeData(
            symbol=order.symbol,
            exchange=order.exchange,
            orderid=order.orderid,
            tradeid=trade_id,
            direction=order.direction,
            offset=order.offset,
            price=fill_price,
            volume=order.volume,
            gateway_name="MOCK_BRISK"
        )
        
        self.trades[trade_id] = trade
        
        # 更新持仓
        self._update_position(trade)
        
        # 更新账户
        self._update_account(trade)
        
        # 推送事件
        self.gateway.on_order(order)
        self.gateway.on_trade(trade)
        
    def _update_position(self, trade: TradeData) -> None:
        """更新持仓"""
        symbol = trade.symbol
        if symbol not in self.positions:
            self.positions[symbol] = PositionData(
                symbol=symbol,
                exchange=trade.exchange,
                direction=trade.direction,
                volume=0,
                price=0.0,
                pnl=0.0,
                gateway_name="MOCK_BRISK"
            )
            
        position = self.positions[symbol]
        
        if trade.direction == Direction.LONG:
            if trade.offset == Offset.OPEN:
                # 开多仓
                if position.volume == 0:
                    position.price = trade.price
                    position.volume = trade.volume
                else:
                    # 计算平均价格
                    total_value = position.price * position.volume + trade.price * trade.volume
                    position.volume += trade.volume
                    position.price = total_value / position.volume
            else:  # CLOSE
                # 平多仓
                position.volume -= trade.volume
                if position.volume <= 0:
                    position.volume = 0
                    position.price = 0.0
        else:  # SHORT
            if trade.offset == Offset.OPEN:
                # 开空仓
                if position.volume == 0:
                    position.price = trade.price
                    position.volume = -trade.volume
                else:
                    # 计算平均价格
                    total_value = abs(position.price * position.volume) + trade.price * trade.volume
                    position.volume -= trade.volume
                    position.price = total_value / abs(position.volume)
            else:  # CLOSE
                # 平空仓
                position.volume += trade.volume
                if position.volume >= 0:
                    position.volume = 0
                    position.price = 0.0
                    
    def _update_account(self, trade: TradeData) -> None:
        """更新账户"""
        # 计算交易金额
        trade_value = trade.price * trade.volume
        
        # 计算手续费
        commission = trade_value * self.commission_rate
        
        if trade.direction == Direction.LONG:
            if trade.offset == Offset.OPEN:
                # 开多仓：扣除资金
                self.account.balance -= (trade_value + commission)
                self.account.available -= (trade_value + commission)
            else:  # CLOSE
                # 平多仓：增加资金
                self.account.balance += (trade_value - commission)
                self.account.available += (trade_value - commission)
        else:  # SHORT
            if trade.offset == Offset.OPEN:
                # 开空仓：增加资金
                self.account.balance += (trade_value - commission)
                self.account.available += (trade_value - commission)
            else:  # CLOSE
                # 平空仓：扣除资金
                self.account.balance -= (trade_value + commission)
                self.account.available -= (trade_value + commission)


class MockBriskGateway(BaseGateway):
    """
    简化的Mock Brisk Gateway
    支持Mock tick数据和历史数据回放
    交易功能完全Mock化
    """

    default_name: str = "MOCK_BRISK"
    default_setting: Dict[str, str | int | float | bool] = {
        # Tick数据模式配置
        "tick_mode": "mock",  # "mock" 或 "replay"
        
        # Mock Tick配置
        "mock_tick_interval": 1.0,       # Mock tick间隔(秒)
        "mock_price_volatility": 0.01,   # Mock价格波动率
        "mock_volume_range": (100, 1000), # Mock成交量范围
        "mock_base_prices": {},          # Mock基准价格 {symbol: price}
        
        # Replay配置
        "replay_data_dir": "D:\\dev\\github\\brisk-hack\\brisk_in_day_frames",
        "replay_date": "",               # 回放日期 "20241201"
        "replay_speed": 1.0,             # 回放速度倍数
        
        # Mock交易配置
        "mock_account_balance": 10000000,  # 模拟账户余额
        "mock_commission_rate": 0.001,   # 模拟手续费率
        "mock_slippage": 0.0,            # 模拟滑点
        "mock_fill_delay": 0.1,          # 模拟成交延迟(秒)
        "mock_auto_process_orders": True,  # 是否自动处理订单状态
    }
    exchanges: List[Exchange] = [Exchange.TSE]

    def __init__(self, event_engine: EventEngine, gateway_name: str) -> None:
        """Constructor"""
        super().__init__(event_engine, gateway_name)

        # 配置相关
        self.tick_mode = "mock"
        self.config = {}
        
        # 组件
        self.mock_tick_generator = None
        self.replay_engine = None
        self.mock_trading_engine = None
        
        # 订阅的股票
        self.subscribed_symbols = set()
        
        # 状态
        self.connected = False
        self.order_call_count = 0

    def connect(self, setting: Dict) -> None:
        """连接服务器"""
        # 1. 解析配置
        self._parse_config(setting)
        
        # 2. 初始化tick数据源
        if self.tick_mode == "mock":
            self._init_mock_tick_generator()
        else:  # replay
            self._init_replay_engine()
            
        # 3. 初始化Mock交易引擎
        self._init_mock_trading_engine()
        
        # 4. 启动数据流
        self._start_data_flow()
        
        self.connected = True
        self.write_log("Mock Brisk Gateway连接成功")

    def close(self) -> None:
        """关闭连接"""
        self.connected = False
        
        # 停止tick数据源
        if self.tick_mode == "mock" and self.mock_tick_generator:
            self.mock_tick_generator.stop()
        elif self.tick_mode == "replay" and self.replay_engine:
            self.replay_engine.stop_replay()
            
        self.write_log("Mock Brisk Gateway已关闭")

    def subscribe(self, req: SubscribeRequest) -> None:
        """订阅行情"""
        self.subscribed_symbols.add(req.symbol)
        
        if self.tick_mode == "mock":
            self.mock_tick_generator.add_symbol(req.symbol)
        # 在replay模式下，订阅请求会被记录，但数据由回放引擎控制
            
        self.write_log(f"订阅行情成功: {req.symbol}")

    def send_order(self, req: OrderRequest) -> str:
        self.order_call_count += 1
        """发送委托"""
        return self.mock_trading_engine.send_order(req)

    def cancel_order(self, req: CancelRequest) -> None:
        """撤销委托"""
        self.mock_trading_engine.cancel_order(req)

    def query_account(self) -> None:
        """查询资金"""
        self.on_account(self.mock_trading_engine.get_account())

    def query_position(self) -> None:
        """查询持仓"""
        positions = self.mock_trading_engine.get_positions()
        for position in positions.values():
            self.on_position(position)

    def query_history(self, req: HistoryRequest) -> List[BarData]:
        """查询历史数据"""
        # Mock Gateway暂不支持历史数据查询
        self.write_log("Mock Gateway暂不支持历史数据查询")
        return []

    def _parse_config(self, setting: Dict) -> None:
        """解析配置"""
        self.config = {**self.default_setting, **setting}
        self.tick_mode = self.config.get("tick_mode", "mock")
        
    def _init_mock_tick_generator(self) -> None:
        """初始化Mock tick生成器"""
        self.mock_tick_generator = MockTickGenerator(self.config, self)
        
    def _init_replay_engine(self) -> None:
        """初始化回放引擎"""
        self.replay_engine = HistoricalReplayEngine(self.config, self)
        
    def _init_mock_trading_engine(self) -> None:
        """初始化Mock交易引擎"""
        self.mock_trading_engine = MockTradingEngine(self.config, self)
        
    def _start_data_flow(self) -> None:
        """启动数据流"""
        if self.tick_mode == "mock":
            self.mock_tick_generator.start()
        else:  # replay
            self.replay_engine.start_replay()

    # 测试专用方法
    def set_mock_tick_data(self, symbol: str, tick_data: List[TickData]) -> None:
        """设置Mock tick数据（用于测试）"""
        if self.tick_mode == "mock":
            # 这里可以实现自定义tick数据设置
            self.write_log(f"设置Mock tick数据: {symbol}")
            
    def set_mock_order_response(self, order_id: str, response: dict) -> None:
        """设置Mock订单响应（用于测试）"""
        self.write_log(f"设置Mock订单响应: {order_id}")
        
    def get_mock_positions(self) -> Dict[str, PositionData]:
        """获取Mock持仓信息"""
        return self.mock_trading_engine.get_positions()
        
    def get_mock_account(self) -> AccountData:
        """获取Mock账户信息"""
        return self.mock_trading_engine.get_account()
        
    def reset_mock_state(self) -> None:
        """重置Mock状态（用于测试）"""
        self.mock_trading_engine.reset()
        if self.tick_mode == "mock" and self.mock_tick_generator:
            self.mock_tick_generator.reset()
            
    def pause_replay(self) -> None:
        """暂停回放"""
        if self.tick_mode == "replay" and self.replay_engine:
            self.replay_engine.pause()
            
    def resume_replay(self) -> None:
        """恢复回放"""
        if self.tick_mode == "replay" and self.replay_engine:
            self.replay_engine.resume()
    
    def manually_process_order(self, order_id: str, target_status: Status) -> bool:
        """手动处理订单状态（用于测试）"""
        if self.mock_trading_engine:
            self.write_log(f"mock brisk gateway manually_process_order: {order_id} -> {target_status}")
            return self.mock_trading_engine.manually_process_order(order_id, target_status)
        return False
    
    def get_order_by_id(self, order_id: str) -> Optional[OrderData]:
        """根据订单ID获取订单（用于测试）"""
        if self.mock_trading_engine:
            return self.mock_trading_engine.get_order_by_id(order_id)
        return None 