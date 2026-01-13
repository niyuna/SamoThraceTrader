"""
Dotenkun策略测试套件
参考hft_bb策略的测试结构
"""

import unittest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenkun_strategy import DotenkunStrategy, DotenkunContext
from dotenkun_indicators import DotenkunIndicator
from intraday_strategy_base import StrategyState
from vnpy.trader.object import BarData, TickData, OrderData
from vnpy.trader.constant import Exchange, Interval, Direction, Offset, Status, OrderType
from vnpy.event import Event


class TestDotenkunContext(unittest.TestCase):
    """测试DotenkunContext数据结构"""
    
    def test_context_creation(self):
        """测试Context创建"""
        context = DotenkunContext(symbol="161030023", k=1.0)
        
        self.assertEqual(context.symbol, "161030023")
        self.assertEqual(context.k, 1.0)
        self.assertEqual(context.position, 0)
        self.assertEqual(context.pending_entry_direction, "")
        self.assertEqual(context.signal_triggered, "")
        self.assertEqual(context.latest_5min_bar_open, 0.0)
    
    def test_context_default_values(self):
        """测试Context默认值"""
        context = DotenkunContext(symbol="161030023")
        
        self.assertEqual(context.k, 1.0)  # 默认值
        self.assertEqual(context.position, 0)
        self.assertEqual(context.pending_entry_direction, "")
        self.assertEqual(context.signal_triggered, "")
        self.assertEqual(context.state, StrategyState.IDLE)


class TestDotenkunSignalLogic(unittest.TestCase):
    """测试信号触发逻辑"""
    
    def setUp(self):
        """测试前的准备工作"""
        self.strategy = DotenkunStrategy(k=1.0, log_suffix="test")
        self.strategy.fixed_symbol = "161030023"
        
        # Mock gateway
        self.strategy.gateway = Mock()
        self.strategy.gateway.send_order = Mock(return_value="test_order_123")
        
        # Mock write_log
        self.strategy.write_log = Mock()
        
        # Mock bar generator
        self.mock_bar_gen = Mock()
        self.mock_bar_gen.window_bar = None
        self.strategy.bar_generators = {"161030023": self.mock_bar_gen}
        
        # Mock indicator manager
        self.mock_indicator = Mock(spec=DotenkunIndicator)
        self.strategy.indicator_managers = {"161030023": self.mock_indicator}
    
    def test_signal_generation_with_insufficient_data(self):
        """测试数据不足时不生成信号"""
        # 设置hl_range_count < 5
        self.mock_indicator.get_indicators.return_value = {
            'hl_range_count': 3,
            'hl_range_ma_5': 2.0
        }
        
        # 创建tick
        tick = TickData(
            symbol="161030023",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            last_price=105.0,
            gateway_name="TEST"
        )
        
        # Mock get_indicators方法
        self.strategy.get_indicators = Mock(return_value={
            'hl_range_count': 3,
            'hl_range_ma_5': 2.0
        })
        
        # 调用on_tick
        event = Event("test", tick)
        self.strategy.on_tick(event)
        
        # 验证没有生成信号（pending_entry_direction应该为空）
        context = self.strategy.get_context("161030023")
        self.assertEqual(context.pending_entry_direction, "")
        self.assertEqual(context.signal_triggered, "")
    
    def test_up_signal_trigger(self):
        """测试UP信号触发"""
        # 设置充足的数据
        self.mock_indicator.get_indicators.return_value = {
            'hl_range_count': 5,
            'hl_range_ma_5': 2.0
        }
        
        # 创建5分钟bar（open=100.0）
        bar_5min = BarData(
            symbol="161030023",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            interval=None,
            open_price=100.0,
            high_price=102.0,
            low_price=98.0,
            close_price=101.0,
            gateway_name="TEST"
        )
        self.mock_bar_gen.window_bar = bar_5min
        
        # Mock get_indicators方法
        self.strategy.get_indicators = Mock(return_value={
            'hl_range_count': 5,
            'hl_range_ma_5': 2.0
        })
        
        # 创建tick价格 >= open + K * hl_range_ma (100 + 1.0 * 2.0 = 102.0)
        tick = TickData(
            symbol="161030023",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            last_price=102.5,  # >= 102.0
            gateway_name="TEST"
        )
        
        # 调用on_tick
        event = Event("test", tick)
        self.strategy.on_tick(event)
        
        # 验证UP信号被触发
        context = self.strategy.get_context("161030023")
        self.assertEqual(context.signal_triggered, 'up')
        self.assertEqual(context.pending_entry_direction, 'long')
    
    def test_down_signal_trigger(self):
        """测试DOWN信号触发"""
        # 设置充足的数据
        self.mock_indicator.get_indicators.return_value = {
            'hl_range_count': 5,
            'hl_range_ma_5': 2.0
        }
        
        # 创建5分钟bar（open=100.0）
        bar_5min = BarData(
            symbol="161030023",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            interval=None,
            open_price=100.0,
            high_price=102.0,
            low_price=98.0,
            close_price=99.0,
            gateway_name="TEST"
        )
        self.mock_bar_gen.window_bar = bar_5min
        
        # Mock get_indicators方法
        self.strategy.get_indicators = Mock(return_value={
            'hl_range_count': 5,
            'hl_range_ma_5': 2.0
        })
        
        # 创建tick价格 <= open - K * hl_range_ma (100 - 1.0 * 2.0 = 98.0)
        tick = TickData(
            symbol="161030023",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            last_price=97.5,  # <= 98.0
            gateway_name="TEST"
        )
        
        # 调用on_tick
        event = Event("test", tick)
        self.strategy.on_tick(event)
        
        # 验证DOWN信号被触发
        context = self.strategy.get_context("161030023")
        self.assertEqual(context.signal_triggered, 'down')
        self.assertEqual(context.pending_entry_direction, 'short')
    
    def test_no_signal_when_price_in_range(self):
        """测试价格在范围内时不触发信号"""
        # 设置充足的数据
        self.strategy.get_indicators = Mock(return_value={
            'hl_range_count': 5,
            'hl_range_ma_5': 2.0
        })
        
        # 创建5分钟bar（open=100.0）
        bar_5min = BarData(
            symbol="161030023",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            interval=None,
            open_price=100.0,
            high_price=102.0,
            low_price=98.0,
            close_price=100.5,
            gateway_name="TEST"
        )
        self.mock_bar_gen.window_bar = bar_5min
        
        # 创建tick价格在范围内 (98.0 < 99.5 < 102.0)
        tick = TickData(
            symbol="161030023",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            last_price=99.5,
            gateway_name="TEST"
        )
        
        # 调用on_tick
        event = Event("test", tick)
        self.strategy.on_tick(event)
        
        # 验证没有信号
        context = self.strategy.get_context("161030023")
        self.assertEqual(context.signal_triggered, "")
        self.assertEqual(context.pending_entry_direction, "")


class TestDotenkunPositionManagement(unittest.TestCase):
    """测试position管理"""
    
    def setUp(self):
        """测试前的准备工作"""
        self.strategy = DotenkunStrategy(k=1.0, log_suffix="test")
        self.strategy.fixed_symbol = "161030023"
        self.strategy.gateway = Mock()
        self.strategy.gateway.send_order = Mock(return_value="test_order_123")
        self.strategy.write_log = Mock()
    
    def test_position_update_on_entry_order_filled_long(self):
        """测试entry订单成交时更新position（多头）"""
        context = self.strategy.get_context("161030023")
        context.entry_order_id = "entry_order_123"
        context.position = 0
        
        # 创建entry订单，状态为ALLTRADED
        order = OrderData(
            symbol="161030023",
            exchange=Exchange.TSE,
            orderid="entry_order_123",
            direction=Direction.LONG,
            type=OrderType.MARKET,
            volume=1,
            price=100.0,
            status=Status.ALLTRADED,
            datetime=datetime.now(),
            gateway_name="TEST"
        )
        
        # 调用on_order
        event = Event("test", order)
        self.strategy.on_order(event)
        
        # 验证context.position被正确更新
        self.assertEqual(context.position, 1)  # 多头持仓为正数
        self.assertEqual(context.entry_price, 100.0)
        self.assertEqual(context.entry_order_id, "")  # 订单ID被清除
        self.assertEqual(context.state, StrategyState.HOLDING)
    
    def test_position_update_on_entry_order_filled_short(self):
        """测试entry订单成交时更新position（空头）"""
        context = self.strategy.get_context("161030023")
        context.entry_order_id = "entry_order_123"
        context.position = 0
        
        # 创建entry订单，状态为ALLTRADED
        order = OrderData(
            symbol="161030023",
            exchange=Exchange.TSE,
            orderid="entry_order_123",
            direction=Direction.SHORT,
            type=OrderType.MARKET,
            volume=1,
            price=100.0,
            status=Status.ALLTRADED,
            datetime=datetime.now(),
            gateway_name="TEST"
        )
        
        # 调用on_order
        event = Event("test", order)
        self.strategy.on_order(event)
        
        # 验证context.position被正确更新
        self.assertEqual(context.position, -1)  # 空头持仓为负数
        self.assertEqual(context.entry_price, 100.0)
        self.assertEqual(context.entry_order_id, "")
        self.assertEqual(context.state, StrategyState.HOLDING)
    
    def test_position_update_on_exit_order_filled(self):
        """测试exit订单成交时更新position"""
        context = self.strategy.get_context("161030023")
        context.exit_order_id = "exit_order_123"
        context.position = 1  # 当前有多头持仓
        
        # 创建exit订单，状态为ALLTRADED
        order = OrderData(
            symbol="161030023",
            exchange=Exchange.TSE,
            orderid="exit_order_123",
            direction=Direction.LONG,
            type=OrderType.MARKET,
            offset=Offset.CLOSE,
            volume=1,
            price=101.0,
            status=Status.ALLTRADED,
            datetime=datetime.now(),
            gateway_name="TEST"
        )
        
        # 调用on_order
        event = Event("test", order)
        self.strategy.on_order(event)
        
        # 验证context.position被设为0
        self.assertEqual(context.position, 0)
        self.assertEqual(context.exit_price, 101.0)
        self.assertEqual(context.exit_order_id, "")
        self.assertEqual(context.state, StrategyState.IDLE)
    
    def test_position_update_on_partial_fill_entry_long(self):
        """测试entry订单部分成交时更新position（多头）"""
        context = self.strategy.get_context("161030023")
        context.entry_order_id = "entry_order_123"
        context.position = 0
        
        # 创建entry订单，状态为PARTTRADED
        order = OrderData(
            symbol="161030023",
            exchange=Exchange.TSE,
            orderid="entry_order_123",
            direction=Direction.LONG,
            type=OrderType.MARKET,
            volume=2,
            traded=1,  # 部分成交
            price=100.0,
            status=Status.PARTTRADED,
            datetime=datetime.now(),
            gateway_name="TEST"
        )
        
        # 调用on_order
        event = Event("test", order)
        self.strategy.on_order(event)
        
        # 验证position被更新
        self.assertEqual(context.position, 1)  # traded数量
    
    def test_close_opposite_position_on_signal(self):
        """测试信号触发时close相反position"""
        context = self.strategy.get_context("161030023")
        context.position = 1  # 当前有多头持仓
        context.signal_triggered = 'down'  # 触发DOWN信号（空头）
        
        # Mock bar generator和indicator
        bar_5min = BarData(
            symbol="161030023",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            interval=None,
            open_price=100.0,
            high_price=102.0,
            low_price=98.0,
            close_price=99.0,
            gateway_name="TEST"
        )
        mock_bar_gen = Mock()
        mock_bar_gen.window_bar = bar_5min
        self.strategy.bar_generators = {"161030023": mock_bar_gen}
        
        self.strategy.get_indicators = Mock(return_value={
            'hl_range_count': 5,
            'hl_range_ma_5': 2.0
        })
        
        # 创建tick触发DOWN信号
        tick = TickData(
            symbol="161030023",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            last_price=97.5,
            gateway_name="TEST"
        )
        
        # 调用on_tick
        event = Event("test", tick)
        self.strategy.on_tick(event)
        
        # 验证close订单被发送
        self.strategy.gateway.send_order.assert_called()
        call_args = self.strategy.gateway.send_order.call_args[0][0]
        self.assertEqual(call_args.offset, Offset.CLOSE)
        self.assertEqual(call_args.direction, Direction.LONG)  # close多头持仓
        self.assertEqual(call_args.volume, 1)
        
        # 验证pending_entry_direction被设置
        self.assertEqual(context.pending_entry_direction, 'short')
    
    def test_no_entry_when_same_direction_position_exists(self):
        """测试已有相同方向position时，触发相同方向信号不会执行entry"""
        # 创建策略，设置initial_position=1（已有long position）
        self.strategy = DotenkunStrategy(k=1.0, initial_position=1, log_suffix="test")
        self.strategy.fixed_symbol = "161030023"
        self.strategy.gateway = Mock()
        self.strategy.gateway.send_order = Mock(return_value="test_order_123")
        self.strategy.write_log = Mock()
        
        # 获取context（应该已经有position=1）
        context = self.strategy.get_context("161030023")
        self.assertEqual(context.position, 1)  # 验证初始position
        
        # Mock bar generator和indicator
        bar_5min = BarData(
            symbol="161030023",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            interval=None,
            open_price=100.0,
            high_price=102.0,
            low_price=98.0,
            close_price=101.0,
            gateway_name="TEST"
        )
        mock_bar_gen = Mock()
        mock_bar_gen.window_bar = bar_5min
        self.strategy.bar_generators = {"161030023": mock_bar_gen}
        
        self.strategy.get_indicators = Mock(return_value={
            'hl_range_count': 5,
            'hl_range_ma_5': 2.0
        })
        
        # 创建tick触发UP信号（与现有position方向相同）
        tick = TickData(
            symbol="161030023",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            last_price=102.5,  # >= 100 + 1.0 * 2.0 = 102.0，触发UP信号
            gateway_name="TEST"
        )
        
        # 调用on_tick
        event = Event("test", tick)
        self.strategy.on_tick(event)
        
        # 验证：不应该设置pending_entry_direction（因为已有相同方向的position）
        self.assertEqual(context.pending_entry_direction, "")
        
        # 验证：不应该发送任何订单（既不应该close，也不应该entry）
        self.strategy.gateway.send_order.assert_not_called()
        
        # 验证：position保持不变
        self.assertEqual(context.position, 1)
    
    def test_no_delayed_entry_when_same_direction_position_exists(self):
        """测试delayed entry执行时，如果已有相同方向position，不应该执行entry"""
        context = self.strategy.get_context("161030023")
        context.position = 1  # 已有long position
        context.pending_entry_direction = 'long'  # 假设之前错误地设置了pending entry
        context.signal_triggered = 'up'
        
        # 创建下一根5分钟bar
        bar = BarData(
            symbol="161030023",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            interval=None,
            open_price=102.0,
            high_price=103.0,
            low_price=101.0,
            close_price=102.5,
            gateway_name="TEST"
        )
        
        # Mock indicator manager
        mock_indicator = Mock()
        mock_indicator.get_indicators.return_value = {
            'hl_range_ma_5': 2.0,
            'hl_range_count': 5
        }
        self.strategy.indicator_managers = {"161030023": mock_indicator}
        
        # 重置send_order mock（因为之前可能被调用过）
        self.strategy.gateway.send_order.reset_mock()
        
        # 调用on_5min_bar
        self.strategy.on_5min_bar(bar)
        
        # 验证：不应该发送entry订单（因为已有相同方向的position）
        self.strategy.gateway.send_order.assert_not_called()
        
        # 验证：pending_entry_direction被清除
        self.assertEqual(context.pending_entry_direction, "")
        
        # 验证：position保持不变
        self.assertEqual(context.position, 1)


class TestDotenkunDelayedEntry(unittest.TestCase):
    """测试delayed entry逻辑"""
    
    def setUp(self):
        """测试前的准备工作"""
        self.strategy = DotenkunStrategy(k=1.0, log_suffix="test")
        self.strategy.fixed_symbol = "161030023"
        self.strategy.gateway = Mock()
        self.strategy.gateway.send_order = Mock(return_value="delayed_entry_order_123")
        self.strategy.write_log = Mock()
    
    def test_delayed_entry_execution_long(self):
        """测试delayed entry在下一根5分钟bar执行（多头）"""
        context = self.strategy.get_context("161030023")
        context.pending_entry_direction = 'long'
        context.signal_triggered = 'up'
        
        # 创建下一根5分钟bar
        bar = BarData(
            symbol="161030023",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            interval=None,
            open_price=102.0,
            high_price=103.0,
            low_price=101.0,
            close_price=102.5,
            gateway_name="TEST"
        )
        
        # Mock indicator manager
        mock_indicator = Mock()
        mock_indicator.get_indicators.return_value = {
            'hl_range_ma_5': 2.0,
            'hl_range_count': 5
        }
        self.strategy.indicator_managers = {"161030023": mock_indicator}
        
        # 调用on_5min_bar
        self.strategy.on_5min_bar(bar)
        
        # 验证entry订单在bar.open执行
        self.strategy.gateway.send_order.assert_called_once()
        call_args = self.strategy.gateway.send_order.call_args[0][0]
        self.assertEqual(call_args.direction, Direction.LONG)
        self.assertEqual(call_args.offset, Offset.OPEN)
        self.assertEqual(call_args.type, OrderType.MARKET)
        self.assertEqual(call_args.volume, 1)
        
        # 验证context被更新
        self.assertEqual(context.entry_order_id, "delayed_entry_order_123")
        self.assertEqual(context.entry_price, 102.0)  # bar.open_price
        self.assertEqual(context.pending_entry_direction, "")  # 清除pending标志
        self.assertEqual(context.signal_triggered, "")  # 清除信号标志
        self.assertEqual(context.state, StrategyState.WAITING_ENTRY)
    
    def test_delayed_entry_execution_short(self):
        """测试delayed entry在下一根5分钟bar执行（空头）"""
        context = self.strategy.get_context("161030023")
        context.pending_entry_direction = 'short'
        context.signal_triggered = 'down'
        
        # 创建下一根5分钟bar
        bar = BarData(
            symbol="161030023",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            interval=None,
            open_price=98.0,
            high_price=99.0,
            low_price=97.0,
            close_price=98.5,
            gateway_name="TEST"
        )
        
        # Mock indicator manager
        mock_indicator = Mock()
        mock_indicator.get_indicators.return_value = {
            'hl_range_ma_5': 2.0,
            'hl_range_count': 5
        }
        self.strategy.indicator_managers = {"161030023": mock_indicator}
        
        # 调用on_5min_bar
        self.strategy.on_5min_bar(bar)
        
        # 验证entry订单在bar.open执行
        self.strategy.gateway.send_order.assert_called_once()
        call_args = self.strategy.gateway.send_order.call_args[0][0]
        self.assertEqual(call_args.direction, Direction.SHORT)
        self.assertEqual(call_args.offset, Offset.OPEN)
        self.assertEqual(call_args.type, OrderType.MARKET)
        self.assertEqual(call_args.volume, 1)
        
        # 验证context被更新
        self.assertEqual(context.entry_order_id, "delayed_entry_order_123")
        self.assertEqual(context.entry_price, 98.0)
        self.assertEqual(context.pending_entry_direction, "")
        self.assertEqual(context.signal_triggered, "")
    
    def test_no_delayed_entry_when_no_pending(self):
        """测试没有pending entry时不执行"""
        context = self.strategy.get_context("161030023")
        context.pending_entry_direction = ""  # 没有pending entry
        
        # 创建5分钟bar
        bar = BarData(
            symbol="161030023",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            interval=None,
            open_price=100.0,
            high_price=101.0,
            low_price=99.0,
            close_price=100.5,
            gateway_name="TEST"
        )
        
        # Mock indicator manager
        mock_indicator = Mock()
        mock_indicator.get_indicators.return_value = {
            'hl_range_ma_5': 2.0,
            'hl_range_count': 5
        }
        self.strategy.indicator_managers = {"161030023": mock_indicator}
        
        # 调用on_5min_bar
        self.strategy.on_5min_bar(bar)
        
        # 验证没有发送订单
        self.strategy.gateway.send_order.assert_not_called()


if __name__ == '__main__':
    unittest.main()
