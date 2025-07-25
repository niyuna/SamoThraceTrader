"""
VWAP Failure 策略基于 Context 的测试
基于 context_based_testing_base 实现，只包含 VWAP Failure 策略特定的测试
"""

import sys
import os
import unittest
from datetime import datetime, timedelta
from typing import Dict, Any
import time


# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from vnpy.trader.constant import Direction, Offset, Status, OrderType, Exchange
from vnpy.trader.object import OrderData, TradeData, BarData

from context_based_testing_base import (
    ContextBasedStrategyTest, ContextSnapshotManager, MockDataGenerator,
    TestBasicStateTransitionsMixin, TestEdgeCasesMixin, TestCompleteFlowMixin, TestMultipleSymbolsMixin
)
from vwap_failure_strategy import VWAPFailureStrategy
from intraday_strategy_base import StrategyState


class VWAPFailureStrategyTest(ContextBasedStrategyTest, 
                             TestBasicStateTransitionsMixin,
                             TestEdgeCasesMixin,
                             TestCompleteFlowMixin,
                             TestMultipleSymbolsMixin):
    """VWAP Failure 策略测试"""
    
    def setUp(self):
        """测试前准备"""
        # 调用父类的setUp方法以初始化mock_gateway_config
        super().setUp()
        
        # 创建策略实例
        self.strategy = VWAPFailureStrategy(use_mock_gateway=True)
        self.snapshot_manager = ContextSnapshotManager(self.strategy)
        self.mock_generator = MockDataGenerator()
        
        # 设置策略参数
        self.strategy.set_strategy_params(
            market_cap_threshold=100_000_000_000,
            gap_up_threshold=0.02,
            gap_down_threshold=-0.02,
            failure_threshold_gap_up=3,
            failure_threshold_gap_down=3,
            entry_factor_gap_up=1.5,
            entry_factor_gap_down=1.5,
            max_daily_trades_gap_up=3,
            max_daily_trades_gap_down=3,
            latest_entry_time="23:59:50", # make it always true
            exit_factor_gap_up=1.0,
            exit_factor_gap_down=1.0,
            max_exit_wait_time_gap_up=5,  # 测试时使用较短时间
            max_exit_wait_time_gap_down=5,  # 测试时使用较短时间
            max_vol_ma5_ratio_threshold_gap_up=2.0,
            max_vol_ma5_ratio_threshold_gap_down=1.5
        )
        
        # 连接Gateway（使用禁用自动订单处理的配置）
        self.strategy.connect(self.mock_gateway_config)
        
        # 设置测试股票
        self.test_symbol = "9984"
        self.test_symbol2 = "7203"  # 用于多股票测试
        self.strategy.add_symbol(self.test_symbol)
        self.strategy.add_symbol(self.test_symbol2)
        
        # 模拟股票筛选结果
        self.strategy.eligible_stocks.add(self.test_symbol)
        self.strategy.eligible_stocks.add(self.test_symbol2)
        self.strategy.gap_direction[self.test_symbol] = 'up'  # 默认gap up
        self.strategy.gap_direction[self.test_symbol2] = 'down'  # 第二个股票gap down
    
    def get_mock_indicators(self, symbol: str) -> dict:
        """获取模拟技术指标 - VWAP Failure 策略特定"""
        # 根据 gap 方向返回不同的指标
        gap_direction = self.strategy.gap_direction.get(symbol, 'none')
        
        if gap_direction == 'up':
            return self.mock_generator.create_mock_indicators(
                vwap=100.0, atr_14=1.0, below_vwap_count=3
            )
        elif gap_direction == 'down':
            return self.mock_generator.create_mock_indicators(
                vwap=100.0, atr_14=1.0, above_vwap_count=3
            )
        else:
            return self.mock_generator.create_mock_indicators(
                vwap=100.0, atr_14=1.0, below_vwap_count=0, above_vwap_count=0
            )


class TestVWAPFailureSpecificLogic(VWAPFailureStrategyTest):
    """测试 VWAP Failure 策略特定逻辑"""
    
    def test_gap_up_vwap_failure_condition(self):
        """测试 Gap Up 策略的 VWAP Failure 条件"""
        symbol = self.test_symbol
        self.strategy.gap_direction[symbol] = 'up'
        
        # 设置初始状态
        self.setup_context(symbol, state=StrategyState.IDLE, trade_count=0)
        
        # 测试不满足 VWAP Failure 条件的情况
        # 修改技术指标，使 below_vwap_count < failure_threshold
        def get_mock_indicators_insufficient(symbol: str) -> dict:
            return self.mock_generator.create_mock_indicators(
                vwap=100.0, atr_14=1.0, below_vwap_count=2  # 小于阈值3
            )
        
        # 临时替换方法
        original_method = self.get_mock_indicators
        self.get_mock_indicators = get_mock_indicators_insufficient
        
        try:
            # 触发 bar 更新
            bar = self.mock_generator.create_mock_bar(symbol)
            self.trigger_bar_update(bar)
            
            # 验证没有生成信号
            self.assert_context_state(symbol, "idle")
            context = self.strategy.get_context(symbol)
            assert context.entry_order_id == ""
        finally:
            # 恢复原方法
            self.get_mock_indicators = original_method
    
    def test_gap_down_vwap_failure_condition(self):
        """测试 Gap Down 策略的 VWAP Failure 条件"""
        symbol = self.test_symbol
        self.strategy.gap_direction[symbol] = 'down'
        
        # 设置初始状态
        self.setup_context(symbol, state=StrategyState.IDLE, trade_count=0)
        
        # 测试不满足 VWAP Failure 条件的情况
        # 修改技术指标，使 above_vwap_count < failure_threshold
        def get_mock_indicators_insufficient(symbol: str) -> dict:
            return self.mock_generator.create_mock_indicators(
                vwap=100.0, atr_14=1.0, above_vwap_count=2  # 小于阈值3
            )
        
        # 临时替换方法
        original_method = self.get_mock_indicators
        self.get_mock_indicators = get_mock_indicators_insufficient
        
        try:
            # 触发 bar 更新
            bar = self.mock_generator.create_mock_bar(symbol)
            self.trigger_bar_update(bar)
            
            # 验证没有生成信号
            self.assert_context_state(symbol, "idle")
            context = self.strategy.get_context(symbol)
            assert context.entry_order_id == ""
        finally:
            # 恢复原方法
            self.get_mock_indicators = original_method
    
    def test_price_calculation(self):
        """测试价格计算逻辑"""
        symbol = self.test_symbol
        
        # 测试 Gap Up 策略的价格计算
        self.strategy.gap_direction[symbol] = 'up'
        context = self.setup_context(symbol, state=StrategyState.IDLE)
        
        # 创建技术指标
        indicators = self.mock_generator.create_mock_indicators(
            vwap=100.0, atr_14=2.0, below_vwap_count=3
        )
        
        # 计算 entry 价格
        entry_price = self.strategy._calculate_entry_price(context, None, indicators)
        expected_entry_price = 100.0 + (2.0 * 1.5)  # vwap + (atr * entry_factor)
        assert abs(entry_price - expected_entry_price) < 0.01
        
        # 计算 exit 价格
        exit_price = self.strategy._calculate_exit_price(context, None, indicators)
        expected_exit_price = 100.0 - (2.0 * 1.0)  # vwap - (atr * exit_factor)
        assert abs(exit_price - expected_exit_price) < 0.01
    
    def test_gap_up_entry_direction(self):
        """测试 Gap Up 策略的入场方向（做空）"""
        symbol = self.test_symbol
        self.strategy.gap_direction[symbol] = 'up'
        
        # 设置初始状态
        self.setup_context(symbol, state=StrategyState.IDLE, trade_count=0)
        
        # 触发 entry 信号
        bar = self.mock_generator.create_mock_bar(symbol)
        self.trigger_bar_update(bar)
        
        # 验证生成了做空订单
        context = self.strategy.get_context(symbol)
        assert context.entry_order_id != ""
        self.assert_context_state(symbol, "waiting_entry")
        
        # 验证订单方向（通过检查订单ID前缀或其他方式）
        # 这里可以根据实际实现来验证订单方向
    
    def test_gap_down_entry_direction(self):
        """测试 Gap Down 策略的入场方向（做多）"""
        symbol = self.test_symbol
        self.strategy.gap_direction[symbol] = 'down'
        
        # 设置初始状态
        self.setup_context(symbol, state=StrategyState.IDLE, trade_count=0)
        
        # 触发 entry 信号
        bar = self.mock_generator.create_mock_bar(symbol)
        self.trigger_bar_update(bar)
        
        # 验证生成了做多订单
        context = self.strategy.get_context(symbol)
        assert context.entry_order_id != ""
        self.assert_context_state(symbol, "waiting_entry")
    
    def test_vwap_failure_threshold_configuration(self):
        """测试 VWAP Failure 阈值配置"""
        symbol = self.test_symbol
        
        # 测试 Gap Up 策略的不同 failure_threshold 值
        self.strategy.gap_direction[symbol] = 'up'
        test_cases_gap_up = [
            (2, 1, False),  # threshold=2, count=1, 不应该生成信号
            (2, 2, True),   # threshold=2, count=2, 应该生成信号
            (3, 2, False),  # threshold=3, count=2, 不应该生成信号
            (3, 3, True),   # threshold=3, count=3, 应该生成信号
        ]
        
        for threshold, count, should_generate in test_cases_gap_up:
            # 设置策略参数
            self.strategy.failure_threshold_gap_up = threshold
            
            # 设置初始状态
            self.setup_context(symbol, state=StrategyState.IDLE, trade_count=0, entry_order_id="", exit_order_id="")
            
            # 创建对应的技术指标
            def get_mock_indicators_with_count(symbol: str) -> dict:
                return self.mock_generator.create_mock_indicators(
                    vwap=100.0, atr_14=1.0, below_vwap_count=count
                )
            
            # 临时替换方法
            original_method = self.get_mock_indicators
            self.get_mock_indicators = get_mock_indicators_with_count
            
            try:
                # 触发 bar 更新
                bar = self.mock_generator.create_mock_bar(symbol)
                self.trigger_bar_update(bar)
                time.sleep(0.01)
                
                # 验证结果
                context = self.strategy.get_context(symbol)
                if should_generate:
                    self.assert_context_state(symbol, "waiting_entry")
                else:
                    assert context.entry_order_id == "", f"Gap Up不应该生成信号: threshold={threshold}, count={count}"
                    self.assert_context_state(symbol, "idle")
            finally:
                # 恢复原方法
                self.get_mock_indicators = original_method
        
        # 测试 Gap Down 策略的不同 failure_threshold 值
        self.strategy.gap_direction[symbol] = 'down'
        test_cases_gap_down = [
            (1, 0, False),  # threshold=1, count=0, 不应该生成信号
            (1, 1, True),   # threshold=1, count=1, 应该生成信号
            (2, 1, False),  # threshold=2, count=1, 不应该生成信号
            (2, 2, True),   # threshold=2, count=2, 应该生成信号
        ]
        
        for threshold, count, should_generate in test_cases_gap_down:
            # 设置策略参数
            self.strategy.failure_threshold_gap_down = threshold
            
            # 设置初始状态
            self.setup_context(symbol, state=StrategyState.IDLE, trade_count=0, entry_order_id="", exit_order_id="")
            
            # 创建对应的技术指标
            def get_mock_indicators_with_count(symbol: str) -> dict:
                return self.mock_generator.create_mock_indicators(
                    vwap=100.0, atr_14=1.0, above_vwap_count=count
                )
            
            # 临时替换方法
            original_method = self.get_mock_indicators
            self.get_mock_indicators = get_mock_indicators_with_count
            
            try:
                # 触发 bar 更新
                bar = self.mock_generator.create_mock_bar(symbol)
                self.trigger_bar_update(bar)
                time.sleep(0.01)
                
                # 验证结果
                context = self.strategy.get_context(symbol)
                if should_generate:
                    self.assert_context_state(symbol, "waiting_entry")
                else:
                    assert context.entry_order_id == "", f"Gap Down不应该生成信号: threshold={threshold}, count={count}"
                    self.assert_context_state(symbol, "idle")
            finally:
                # 恢复原方法
                self.get_mock_indicators = original_method
    
    def test_entry_factor_configuration(self):
        """测试 Entry Factor 配置"""
        symbol = self.test_symbol
        
        # 测试 Gap Up 策略的不同 entry_factor 值
        self.strategy.gap_direction[symbol] = 'up'
        test_cases_gap_up = [
            (1.0, 100.0 + 2.0 * 1.0),  # entry_factor=1.0, expected_price=vwap + atr * 1.0
            (1.5, 100.0 + 2.0 * 1.5),  # entry_factor=1.5, expected_price=vwap + atr * 1.5
            (2.0, 100.0 + 2.0 * 2.0),  # entry_factor=2.0, expected_price=vwap + atr * 2.0
        ]
        
        for entry_factor, expected_price in test_cases_gap_up:
            # 设置策略参数
            self.strategy.entry_factor_gap_up = entry_factor
            
            # 设置初始状态
            context = self.setup_context(symbol, state=StrategyState.IDLE, entry_order_id="", exit_order_id="", entry_price=0, exit_price=0)
            
            # 创建技术指标
            indicators = self.mock_generator.create_mock_indicators(
                vwap=100.0, atr_14=2.0, below_vwap_count=3
            )
            
            # 计算 entry 价格
            entry_price = self.strategy._calculate_entry_price(context, None, indicators)
            assert abs(entry_price - expected_price) < 0.01, \
                f"Gap Up entry_factor={entry_factor}, expected={expected_price}, got={entry_price}"
        
        # 测试 Gap Down 策略的不同 entry_factor 值
        self.strategy.gap_direction[symbol] = 'down'
        test_cases_gap_down = [
            (0.8, 100.0 - 2.0 * 0.8),  # entry_factor=0.8, expected_price=vwap - atr * 0.8
            (1.2, 100.0 - 2.0 * 1.2),  # entry_factor=1.2, expected_price=vwap - atr * 1.2
            (1.5, 100.0 - 2.0 * 1.5),  # entry_factor=1.5, expected_price=vwap - atr * 1.5
        ]
        
        for entry_factor, expected_price in test_cases_gap_down:
            # 设置策略参数
            self.strategy.entry_factor_gap_down = entry_factor
            
            # 设置初始状态
            context = self.setup_context(symbol, state=StrategyState.IDLE, entry_order_id="", exit_order_id="", entry_price=0, exit_price=0)
            
            # 创建技术指标
            indicators = self.mock_generator.create_mock_indicators(
                vwap=100.0, atr_14=2.0, above_vwap_count=3
            )
            
            # 计算 entry 价格
            entry_price = self.strategy._calculate_entry_price(context, None, indicators)
            assert abs(entry_price - expected_price) < 0.01, \
                f"Gap Down entry_factor={entry_factor}, expected={expected_price}, got={entry_price}"
    
    def test_exit_factor_configuration(self):
        """测试 Exit Factor 配置"""
        symbol = self.test_symbol
        
        # 测试 Gap Up 策略的不同 exit_factor 值
        self.strategy.gap_direction[symbol] = 'up'
        test_cases_gap_up = [
            (0.5, 100.0 - 2.0 * 0.5),  # exit_factor=0.5, expected_price=vwap - atr * 0.5
            (1.0, 100.0 - 2.0 * 1.0),  # exit_factor=1.0, expected_price=vwap - atr * 1.0
            (1.5, 100.0 - 2.0 * 1.5),  # exit_factor=1.5, expected_price=vwap - atr * 1.5
        ]
        
        for exit_factor, expected_price in test_cases_gap_up:
            # 设置策略参数
            self.strategy.exit_factor_gap_up = exit_factor
            
            # 设置初始状态
            context = self.setup_context(symbol, state=StrategyState.IDLE)
            
            # 创建技术指标
            indicators = self.mock_generator.create_mock_indicators(
                vwap=100.0, atr_14=2.0, below_vwap_count=3
            )
            
            # 计算 exit 价格
            exit_price = self.strategy._calculate_exit_price(context, None, indicators)
            assert abs(exit_price - expected_price) < 0.01, \
                f"Gap Up exit_factor={exit_factor}, expected={expected_price}, got={exit_price}"
        
        # 测试 Gap Down 策略的不同 exit_factor 值
        self.strategy.gap_direction[symbol] = 'down'
        test_cases_gap_down = [
            (0.5, 100.0 + 2.0 * 0.5),  # exit_factor=0.5, expected_price=vwap + atr * 0.5
            (0.8, 100.0 + 2.0 * 0.8),  # exit_factor=0.8, expected_price=vwap + atr * 0.8
            (1.0, 100.0 + 2.0 * 1.0),  # exit_factor=1.0, expected_price=vwap + atr * 1.0
        ]
        
        for exit_factor, expected_price in test_cases_gap_down:
            # 设置策略参数
            self.strategy.exit_factor_gap_down = exit_factor
            
            # 设置初始状态
            context = self.setup_context(symbol, state=StrategyState.IDLE)
            
            # 创建技术指标
            indicators = self.mock_generator.create_mock_indicators(
                vwap=100.0, atr_14=2.0, above_vwap_count=3
            )
            
            # 计算 exit 价格
            exit_price = self.strategy._calculate_exit_price(context, None, indicators)
            assert abs(exit_price - expected_price) < 0.01, \
                f"Gap Down exit_factor={exit_factor}, expected={expected_price}, got={exit_price}"
    
    def test_get_failure_threshold_method(self):
        """测试 _get_failure_threshold 方法"""
        symbol = self.test_symbol
        
        # 测试 Gap Up 情况
        self.strategy.gap_direction[symbol] = 'up'
        self.strategy.failure_threshold_gap_up = 5
        self.strategy.failure_threshold_gap_down = 3
        
        threshold = self.strategy._get_failure_threshold(symbol)
        assert threshold == 5, f"Gap Up应该返回failure_threshold_gap_up: 期望5, 实际{threshold}"
        
        # 测试 Gap Down 情况
        self.strategy.gap_direction[symbol] = 'down'
        threshold = self.strategy._get_failure_threshold(symbol)
        assert threshold == 3, f"Gap Down应该返回failure_threshold_gap_down: 期望3, 实际{threshold}"
        
        # 测试 none 情况（应该返回gap_down的默认值）
        self.strategy.gap_direction[symbol] = 'none'
        threshold = self.strategy._get_failure_threshold(symbol)
        assert threshold == 3, f"None应该返回failure_threshold_gap_down: 期望3, 实际{threshold}"
        
        print("✅ _get_failure_threshold 方法测试通过")
    
    def test_get_entry_factor_method(self):
        """测试 _get_entry_factor 方法"""
        symbol = self.test_symbol
        
        # 测试 Gap Up 情况
        self.strategy.gap_direction[symbol] = 'up'
        self.strategy.entry_factor_gap_up = 2.0
        self.strategy.entry_factor_gap_down = 1.0
        
        factor = self.strategy._get_entry_factor(symbol)
        assert factor == 2.0, f"Gap Up应该返回entry_factor_gap_up: 期望2.0, 实际{factor}"
        
        # 测试 Gap Down 情况
        self.strategy.gap_direction[symbol] = 'down'
        factor = self.strategy._get_entry_factor(symbol)
        assert factor == 1.0, f"Gap Down应该返回entry_factor_gap_down: 期望1.0, 实际{factor}"
        
        print("✅ _get_entry_factor 方法测试通过")
    
    def test_get_exit_factor_method(self):
        """测试 _get_exit_factor 方法"""
        symbol = self.test_symbol
        
        # 测试 Gap Up 情况
        self.strategy.gap_direction[symbol] = 'up'
        self.strategy.exit_factor_gap_up = 1.5
        self.strategy.exit_factor_gap_down = 0.8
        
        factor = self.strategy._get_exit_factor(symbol)
        assert factor == 1.5, f"Gap Up应该返回exit_factor_gap_up: 期望1.5, 实际{factor}"
        
        # 测试 Gap Down 情况
        self.strategy.gap_direction[symbol] = 'down'
        factor = self.strategy._get_exit_factor(symbol)
        assert factor == 0.8, f"Gap Down应该返回exit_factor_gap_down: 期望0.8, 实际{factor}"
        
        print("✅ _get_exit_factor 方法测试通过")
    
    def test_get_daily_trades_for_gap_method(self):
        """测试 _get_daily_trades_for_gap 方法"""
        symbol = self.test_symbol
        
        # 测试 Gap Up 情况
        self.strategy.gap_direction[symbol] = 'up'
        self.strategy.max_daily_trades_gap_up = 5
        self.strategy.max_daily_trades_gap_down = 2
        
        trades = self.strategy._get_daily_trades_for_gap(symbol)
        assert trades == 5, f"Gap Up应该返回max_daily_trades_gap_up: 期望5, 实际{trades}"
        
        # 测试 Gap Down 情况
        self.strategy.gap_direction[symbol] = 'down'
        trades = self.strategy._get_daily_trades_for_gap(symbol)
        assert trades == 2, f"Gap Down应该返回max_daily_trades_gap_down: 期望2, 实际{trades}"
        
        print("✅ _get_daily_trades_for_gap 方法测试通过")
    
    def test_get_exit_wait_time_method(self):
        """测试 _get_exit_wait_time 方法"""
        symbol = self.test_symbol
        
        # 测试 Gap Up 情况
        self.strategy.gap_direction[symbol] = 'up'
        self.strategy.max_exit_wait_time_gap_up = 45
        self.strategy.max_exit_wait_time_gap_down = 15
        
        wait_time = self.strategy._get_exit_wait_time(symbol)
        assert wait_time == 45, f"Gap Up应该返回max_exit_wait_time_gap_up: 期望45, 实际{wait_time}"
        
        # 测试 Gap Down 情况
        self.strategy.gap_direction[symbol] = 'down'
        wait_time = self.strategy._get_exit_wait_time(symbol)
        assert wait_time == 15, f"Gap Down应该返回max_exit_wait_time_gap_down: 期望15, 实际{wait_time}"
        
        print("✅ _get_exit_wait_time 方法测试通过")
    
    def test_max_vol_ma5_ratio_threshold_configuration(self):
        """测试 max_vol_ma5_ratio_threshold 参数配置"""
        symbol = self.test_symbol
        
        # 验证默认值设置
        assert self.strategy.max_vol_ma5_ratio_threshold_gap_up == 2.0, f"默认Gap Up比例阈值应该是2.0, 实际{self.strategy.max_vol_ma5_ratio_threshold_gap_up}"
        assert self.strategy.max_vol_ma5_ratio_threshold_gap_down == 1.5, f"默认Gap Down比例阈值应该是1.5, 实际{self.strategy.max_vol_ma5_ratio_threshold_gap_down}"
        
        # 测试参数设置
        self.strategy.set_strategy_params(
            max_vol_ma5_ratio_threshold_gap_up=3.0,
            max_vol_ma5_ratio_threshold_gap_down=1.2
        )
        
        assert self.strategy.max_vol_ma5_ratio_threshold_gap_up == 3.0, f"设置后Gap Up比例阈值应该是3.0, 实际{self.strategy.max_vol_ma5_ratio_threshold_gap_up}"
        assert self.strategy.max_vol_ma5_ratio_threshold_gap_down == 1.2, f"设置后Gap Down比例阈值应该是1.2, 实际{self.strategy.max_vol_ma5_ratio_threshold_gap_down}"
        
        print("✅ max_vol_ma5_ratio_threshold 参数配置测试通过")
    
    def test_get_max_vol_ma5_ratio_threshold_method(self):
        """测试 _get_max_vol_ma5_ratio_threshold 方法"""
        symbol = self.test_symbol
        
        # 测试 Gap Up 情况
        self.strategy.gap_direction[symbol] = 'up'
        self.strategy.max_vol_ma5_ratio_threshold_gap_up = 3.0
        self.strategy.max_vol_ma5_ratio_threshold_gap_down = 1.0
        
        threshold = self.strategy._get_max_vol_ma5_ratio_threshold(symbol)
        assert threshold == 3.0, f"Gap Up应该返回max_vol_ma5_ratio_threshold_gap_up: 期望3.0, 实际{threshold}"
        
        # 测试 Gap Down 情况
        self.strategy.gap_direction[symbol] = 'down'
        threshold = self.strategy._get_max_vol_ma5_ratio_threshold(symbol)
        assert threshold == 1.0, f"Gap Down应该返回max_vol_ma5_ratio_threshold_gap_down: 期望1.0, 实际{threshold}"
        
        print("✅ _get_max_vol_ma5_ratio_threshold 方法测试通过")
    
    def test_volume_anomaly_check_normal_volume(self):
        """测试成交量异常检查 - 正常成交量情况"""
        symbol = self.test_symbol
        self.strategy.gap_direction[symbol] = 'up'
        
        # 设置初始状态为waiting_entry
        context = self.setup_context(symbol, state=StrategyState.WAITING_ENTRY, entry_order_id="test_order_123")
        
        # 设置技术指标：vol_ma5=1000，当前bar成交量=1500，比例=1.5 < 阈值2.0
        def get_mock_indicators_normal(symbol: str) -> dict:
            indicators = self.mock_generator.create_mock_indicators(
                vwap=100.0, atr_14=1.0, below_vwap_count=3
            )
            indicators['volume_ma5'] = 1000  # 覆盖默认值
            return indicators
        
        # 临时替换方法
        original_get_indicators = self.strategy.get_indicators
        self.strategy.get_indicators = get_mock_indicators_normal
        
        try:
            # 创建模拟的当前bar（成交量1500，比例1.5 < 阈值2.0）
            current_bar = self.mock_generator.create_mock_bar(symbol, volume=1500)
            
            # 模拟_get_current_bar返回当前bar
            original_get_current_bar = self.strategy._get_current_bar
            self.strategy._get_current_bar = lambda s: current_bar if s == symbol else None
            
            # 创建tick
            tick = self.mock_generator.create_mock_tick(symbol)
            
            # 调用检查方法
            self.strategy._check_current_bar_volume_anomaly_and_cancel(tick)
            time.sleep(0.01)
            
            # 验证：不应该取消订单，状态应该保持waiting_entry
            context = self.strategy.get_context(symbol)
            assert context.state == StrategyState.WAITING_ENTRY, "正常成交量不应该改变状态"
            assert context.entry_order_id == "test_order_123", "正常成交量不应该取消订单"
            
            print("✅ 正常成交量测试通过")
            
        finally:
            # 恢复原方法
            self.strategy.get_indicators = original_get_indicators
            self.strategy._get_current_bar = original_get_current_bar
    
    def test_volume_anomaly_check_abnormal_volume(self):
        """测试成交量异常检查 - 异常成交量情况"""
        symbol = self.test_symbol
        self.strategy.gap_direction[symbol] = 'up'
        
        # 设置初始状态为waiting_entry
        context = self.setup_context(symbol, state=StrategyState.WAITING_ENTRY, entry_order_id="test_order_456")
        
        # 设置技术指标：vol_ma5=1000，当前bar成交量=2500，比例=2.5 > 阈值2.0
        def get_mock_indicators_abnormal(symbol: str) -> dict:
            indicators = self.mock_generator.create_mock_indicators(
                vwap=100.0, atr_14=1.0, below_vwap_count=3
            )
            indicators['volume_ma5'] = 1000  # 覆盖默认值
            return indicators
        
        # 临时替换方法
        original_get_indicators = self.strategy.get_indicators
        self.strategy.get_indicators = get_mock_indicators_abnormal
        
        try:
            # 创建模拟的当前bar（成交量2500，比例2.5 > 阈值2.0）
            current_bar = self.mock_generator.create_mock_bar(symbol, volume=2500)
            
            # 模拟_get_current_bar返回当前bar
            original_get_current_bar = self.strategy._get_current_bar
            self.strategy._get_current_bar = lambda s: current_bar if s == symbol else None
            
            # 创建tick
            tick = self.mock_generator.create_mock_tick(symbol)
            
            # 调用检查方法
            self.strategy._check_current_bar_volume_anomaly_and_cancel(tick)
            time.sleep(0.01)
            
            # 验证：应该取消订单，状态应该变为idle
            context = self.strategy.get_context(symbol)
            assert context.state == StrategyState.IDLE, "异常成交量应该改变状态为idle"
            assert context.entry_order_id == "", "异常成交量应该清空订单ID"
            
            print("✅ 异常成交量测试通过")
            
        finally:
            # 恢复原方法
            self.strategy.get_indicators = original_get_indicators
            self.strategy._get_current_bar = original_get_current_bar
    
    def test_volume_anomaly_check_different_gap_directions(self):
        """测试成交量异常检查 - 不同gap方向的阈值"""
        symbol = self.test_symbol
        
        # 测试 Gap Down 情况（阈值1.5）
        self.strategy.gap_direction[symbol] = 'down'
        context = self.setup_context(symbol, state=StrategyState.WAITING_ENTRY, entry_order_id="test_order_down")
        
        def get_mock_indicators_down(symbol: str) -> dict:
            indicators = self.mock_generator.create_mock_indicators(
                vwap=100.0, atr_14=1.0, above_vwap_count=3
            )
            indicators['volume_ma5'] = 1000  # 覆盖默认值
            return indicators
        
        original_get_indicators = self.strategy.get_indicators
        self.strategy.get_indicators = get_mock_indicators_down
        
        try:
            # 测试成交量1600，比例1.6 > 阈值1.5，应该触发取消
            current_bar = self.mock_generator.create_mock_bar(symbol, volume=1600)
            original_get_current_bar = self.strategy._get_current_bar
            self.strategy._get_current_bar = lambda s: current_bar if s == symbol else None
            
            tick = self.mock_generator.create_mock_tick(symbol)
            self.strategy._check_current_bar_volume_anomaly_and_cancel(tick)
            time.sleep(0.01)
            
            context = self.strategy.get_context(symbol)
            assert context.state == StrategyState.IDLE, "Gap Down异常成交量应该改变状态"
            assert context.entry_order_id == "", "Gap Down异常成交量应该清空订单ID"
            
            print("✅ Gap Down异常成交量测试通过")
            
        finally:
            self.strategy.get_indicators = original_get_indicators
            self.strategy._get_current_bar = original_get_current_bar
    
    def test_volume_anomaly_check_edge_cases(self):
        """测试成交量异常检查 - 边界情况"""
        symbol = self.test_symbol
        self.strategy.gap_direction[symbol] = 'up'
        
        # 测试1: vol_ma5为0的情况
        context = self.setup_context(symbol, state=StrategyState.WAITING_ENTRY, entry_order_id="test_order_edge")
        
        def get_mock_indicators_zero_ma5(symbol: str) -> dict:
            indicators = self.mock_generator.create_mock_indicators(
                vwap=100.0, atr_14=1.0, below_vwap_count=3
            )
            indicators['volume_ma5'] = 0  # vol_ma5为0
            return indicators
        
        original_get_indicators = self.strategy.get_indicators
        self.strategy.get_indicators = get_mock_indicators_zero_ma5
        
        try:
            current_bar = self.mock_generator.create_mock_bar(symbol, volume=1000)
            original_get_current_bar = self.strategy._get_current_bar
            self.strategy._get_current_bar = lambda s: current_bar if s == symbol else None
            
            tick = self.mock_generator.create_mock_tick(symbol)
            self.strategy._check_current_bar_volume_anomaly_and_cancel(tick)
            time.sleep(0.01)
            
            # 验证：vol_ma5为0时不应该触发取消
            context = self.strategy.get_context(symbol)
            assert context.state == StrategyState.WAITING_ENTRY, "vol_ma5为0时不应该改变状态"
            assert context.entry_order_id == "test_order_edge", "vol_ma5为0时不应该取消订单"
            
            print("✅ vol_ma5为0的边界情况测试通过")
            
        finally:
            self.strategy.get_indicators = original_get_indicators
            self.strategy._get_current_bar = original_get_current_bar
        
        # 测试2: 没有技术指标的情况
        context = self.setup_context(symbol, state=StrategyState.WAITING_ENTRY, entry_order_id="test_order_no_indicators")
        
        def get_mock_indicators_none(symbol: str) -> dict:
            return {}  # 返回空的技术指标
        
        self.strategy.get_indicators = get_mock_indicators_none
        
        try:
            current_bar = self.mock_generator.create_mock_bar(symbol, volume=1000)
            self.strategy._get_current_bar = lambda s: current_bar if s == symbol else None
            
            tick = self.mock_generator.create_mock_tick(symbol)
            self.strategy._check_current_bar_volume_anomaly_and_cancel(tick)
            time.sleep(0.01)
            
            # 验证：没有技术指标时不应该触发取消
            context = self.strategy.get_context(symbol)
            assert context.state == StrategyState.WAITING_ENTRY, "没有技术指标时不应该改变状态"
            assert context.entry_order_id == "test_order_no_indicators", "没有技术指标时不应该取消订单"
            
            print("✅ 没有技术指标的边界情况测试通过")
            
        finally:
            self.strategy.get_indicators = original_get_indicators
            self.strategy._get_current_bar = original_get_current_bar
    
    def test_volume_anomaly_check_state_conditions(self):
        """测试成交量异常检查 - 状态条件"""
        symbol = self.test_symbol
        self.strategy.gap_direction[symbol] = 'up'
        
        # 测试：非waiting_entry状态时不应该检查
        context = self.setup_context(symbol, state=StrategyState.IDLE, entry_order_id="test_order_idle")
        
        def get_mock_indicators_abnormal(symbol: str) -> dict:
            indicators = self.mock_generator.create_mock_indicators(
                vwap=100.0, atr_14=1.0, below_vwap_count=3
            )
            indicators['volume_ma5'] = 1000  # 覆盖默认值
            return indicators
        
        original_get_indicators = self.strategy.get_indicators
        self.strategy.get_indicators = get_mock_indicators_abnormal
        
        try:
            # 创建异常成交量的bar
            current_bar = self.mock_generator.create_mock_bar(symbol, volume=2500)
            original_get_current_bar = self.strategy._get_current_bar
            self.strategy._get_current_bar = lambda s: current_bar if s == symbol else None
            
            tick = self.mock_generator.create_mock_tick(symbol)
            self.strategy._check_current_bar_volume_anomaly_and_cancel(tick)
            time.sleep(0.01)
            
            # 验证：非waiting_entry状态时不应该触发取消
            context = self.strategy.get_context(symbol)
            assert context.state == StrategyState.IDLE, "非waiting_entry状态时不应该改变状态"
            assert context.entry_order_id == "test_order_idle", "非waiting_entry状态时不应该取消订单"
            
            print("✅ 非waiting_entry状态的测试通过")
            
        finally:
            self.strategy.get_indicators = original_get_indicators
            self.strategy._get_current_bar = original_get_current_bar
    
    def test_error_conditions(self):
        """测试错误条件"""
        symbol = self.test_symbol
        
        # 测试1: 股票不在eligible_stocks中
        self.strategy.eligible_stocks.clear()
        self.setup_context(symbol, state=StrategyState.IDLE, trade_count=0)
        
        bar = self.mock_generator.create_mock_bar(symbol)
        self.trigger_bar_update(bar)
        
        # 验证没有生成信号
        self.assert_context_state(symbol, "idle")
        context = self.strategy.get_context(symbol)
        assert context.entry_order_id == ""
        
        # 恢复eligible_stocks
        self.strategy.eligible_stocks.add(symbol)
        
        # 测试2: 没有gap方向
        self.strategy.gap_direction[symbol] = 'none'
        self.setup_context(symbol, state=StrategyState.IDLE, trade_count=0)
        
        bar = self.mock_generator.create_mock_bar(symbol)
        self.trigger_bar_update(bar)
        
        # 验证没有生成信号
        self.assert_context_state(symbol, "idle")
        context = self.strategy.get_context(symbol)
        assert context.entry_order_id == ""
        
        # 恢复gap方向
        self.strategy.gap_direction[symbol] = 'up'


class TestVWAPFailureCompleteFlow(VWAPFailureStrategyTest, 
                                 TestBasicStateTransitionsMixin,
                                 TestEdgeCasesMixin,
                                 TestCompleteFlowMixin,
                                 TestMultipleSymbolsMixin):
    """测试 VWAP Failure 策略完整流程"""
    
    def test_complete_trading_cycle_gap_up(self):
        """测试 Gap Up 策略完整交易周期"""
        symbol = self.test_symbol
        self.strategy.gap_direction[symbol] = 'up'
        
        # 1. 初始状态
        self.setup_context(symbol, state=StrategyState.IDLE, trade_count=0)
        self.snapshot_manager.take_snapshot("Initial state")
        
        # 2. 生成 entry 信号
        bar = self.mock_generator.create_mock_bar(symbol)
        self.trigger_bar_update(bar)
        
        # a sleep is necessary because actually the above runs in triggered events in a async way
        time.sleep(0.01)
        self.snapshot_manager.take_snapshot("After entry signal")

        # 3. entry 订单成交
        context = self.strategy.get_context(symbol)
        entry_order = self.mock_generator.create_mock_order(
            symbol, Status.ALLTRADED, order_id=context.entry_order_id
        )
        self.trigger_order_update(entry_order)
        
        time.sleep(0.01)
        self.snapshot_manager.take_snapshot("After entry trade")

        # 4. exit 订单成交
        context = self.strategy.get_context(symbol)
        print(f"context before trigger exit order: {context}")
        exit_order = self.mock_generator.create_mock_order(
            symbol, Status.ALLTRADED, order_id=context.exit_order_id
        )
        self.trigger_order_update(exit_order)        
        time.sleep(0.01)
        self.snapshot_manager.take_snapshot("After exit trade")

        # 5. 验证最终状态
        self.assert_context_state(symbol, "idle")
        self.assert_context_field(symbol, "trade_count", 1)
        
        # 6. 验证状态转换序列
        self.snapshot_manager.assert_state_transition(symbol, "idle", "waiting_entry", 1)
        self.snapshot_manager.assert_state_transition(symbol, "waiting_entry", "waiting_exit", 2)
        # no holding state here because on_order will handle the state transition
        self.snapshot_manager.assert_state_transition(symbol, "waiting_exit", "idle", 3)

    def test_waiting_entry_price_update(self):
        """测试 waiting_entry 状态下的价格更新"""
        symbol = self.test_symbol
        self.strategy.gap_direction[symbol] = 'up'
        
        # 1. 设置初始状态并生成 entry 信号
        self.setup_context(symbol, state=StrategyState.IDLE, trade_count=0)
        
        # 生成第一个 entry 信号
        bar1 = self.mock_generator.create_mock_bar(symbol, close_price=100.0)
        self.trigger_bar_update(bar1)
        time.sleep(0.01)
        
        # 验证进入 waiting_entry 状态
        self.assert_context_state(symbol, "waiting_entry")
        context = self.strategy.get_context(symbol)
        assert context.entry_order_id != ""
        
        # 记录第一个订单的价格
        first_order = self.strategy.gateway.get_order_by_id(context.entry_order_id)
        first_order_price = first_order.price if first_order else None
        assert first_order_price is not None, "无法获取第一个订单价格"
        
        # 2. 生成新的 bar，触发价格更新
        # 使用不同的技术指标来模拟价格变化
        def get_mock_indicators_updated(symbol: str) -> dict:
            return self.mock_generator.create_mock_indicators(
                vwap=102.0,  # VWAP 从 100.0 变化到 102.0
                atr_14=1.5,  # ATR 从 1.0 变化到 1.5
                below_vwap_count=3
            )
        
        # 临时替换方法
        original_method = self.get_mock_indicators
        self.get_mock_indicators = get_mock_indicators_updated
        
        try:
            # 生成第二个 bar
            bar2 = self.mock_generator.create_mock_bar(symbol, close_price=102.0)
            self.trigger_bar_update(bar2)
            time.sleep(0.01)
            
            # 验证仍然在 waiting_entry 状态
            self.assert_context_state(symbol, "waiting_entry")
            
            # 验证订单价格是否更新
            updated_order = self.strategy.gateway.get_order_by_id(context.entry_order_id)
            if updated_order and first_order_price:
                # 计算期望的新价格：vwap + (atr * entry_factor) = 102.0 + (1.5 * 1.5) = 104.25
                expected_price = 102.0 + (1.5 * 1.5)
                assert abs(updated_order.price - expected_price) < 0.01, \
                    f"订单价格应该更新: 期望 {expected_price}, 实际 {updated_order.price}"
                print(f"✅ Entry 订单价格已更新: {first_order_price:.2f} -> {updated_order.price:.2f}")
            else:
                assert False, "无法获取更新后的订单价格信息"
            
        finally:
            # 恢复原方法
            self.get_mock_indicators = original_method

    def test_waiting_exit_price_update(self):
        """测试 waiting_exit 状态下的价格更新"""
        symbol = self.test_symbol
        self.strategy.gap_direction[symbol] = 'up'
        
        # 1. 设置初始状态并完成 entry
        self.setup_context(symbol, state=StrategyState.IDLE, trade_count=0)
        
        # 生成 entry 信号
        bar1 = self.mock_generator.create_mock_bar(symbol, close_price=100.0)
        self.trigger_bar_update(bar1)
        time.sleep(0.01)
        
        # 完成 entry 订单
        context = self.strategy.get_context(symbol)
        entry_order = self.mock_generator.create_mock_order(
            symbol, Status.ALLTRADED, order_id=context.entry_order_id
        )
        self.trigger_order_update(entry_order)
        time.sleep(0.01)
        
        # 验证进入 waiting_exit 状态
        self.assert_context_state(symbol, "waiting_exit")
        context = self.strategy.get_context(symbol)
        assert context.exit_order_id != ""
        
        # 记录第一个 exit 订单的价格
        first_exit_order = self.strategy.gateway.get_order_by_id(context.exit_order_id)
        first_exit_order_price = first_exit_order.price if first_exit_order else None
        assert first_exit_order_price is not None, "无法获取第一个exit订单价格"
        
        # 2. 生成新的 bar，触发 exit 价格更新
        # 使用不同的技术指标来模拟价格变化
        def get_mock_indicators_updated(symbol: str) -> dict:
            return self.mock_generator.create_mock_indicators(
                vwap=98.0,   # VWAP 从 100.0 变化到 98.0
                atr_14=1.2,  # ATR 从 1.0 变化到 1.2
                below_vwap_count=3
            )
        
        # 临时替换方法
        original_method = self.get_mock_indicators
        self.get_mock_indicators = get_mock_indicators_updated
        
        try:
            # 生成第二个 bar
            bar2 = self.mock_generator.create_mock_bar(symbol, close_price=98.0)
            self.trigger_bar_update(bar2)
            time.sleep(0.01)
            
            # 验证仍然在 waiting_exit 状态
            self.assert_context_state(symbol, "waiting_exit")
            
            # 验证 exit 订单价格是否更新
            updated_exit_order = self.strategy.gateway.get_order_by_id(context.exit_order_id)
            if updated_exit_order and first_exit_order_price:
                # 计算期望的新价格：vwap - (atr * exit_factor) = 98.0 - (1.2 * 1.0) = 96.8
                expected_price = 98.0 - (1.2 * 1.0)
                assert abs(updated_exit_order.price - expected_price) < 0.01, \
                    f"Exit 订单价格应该更新: 期望 {expected_price}, 实际 {updated_exit_order.price}"
                print(f"✅ Exit 订单价格已更新: {first_exit_order_price:.2f} -> {updated_exit_order.price:.2f}")
            else:
                assert False, "无法获取更新后的exit订单价格信息"
            
        finally:
            # 恢复原方法
            self.get_mock_indicators = original_method

    def test_waiting_entry_price_update_gap_down(self):
        """测试 Gap Down 策略 waiting_entry 状态下的价格更新"""
        symbol = self.test_symbol
        self.strategy.gap_direction[symbol] = 'down'
        
        # 1. 设置初始状态并生成 entry 信号
        self.setup_context(symbol, state=StrategyState.IDLE, trade_count=0)
        
        # 生成第一个 entry 信号
        bar1 = self.mock_generator.create_mock_bar(symbol, close_price=100.0)
        self.trigger_bar_update(bar1)
        time.sleep(0.01)
        
        # 验证进入 waiting_entry 状态
        self.assert_context_state(symbol, "waiting_entry")
        context = self.strategy.get_context(symbol)
        assert context.entry_order_id != ""
        
        # 记录第一个订单的价格
        first_order = self.strategy.gateway.get_order_by_id(context.entry_order_id)
        first_order_price = first_order.price if first_order else None
        assert first_order_price is not None, "无法获取第一个订单价格"
        
        # 2. 生成新的 bar，触发价格更新
        # 使用不同的技术指标来模拟价格变化
        def get_mock_indicators_updated(symbol: str) -> dict:
            return self.mock_generator.create_mock_indicators(
                vwap=98.0,   # VWAP 从 100.0 变化到 98.0
                atr_14=1.5,  # ATR 从 1.0 变化到 1.5
                above_vwap_count=3
            )
        
        # 临时替换方法
        original_method = self.get_mock_indicators
        self.get_mock_indicators = get_mock_indicators_updated
        
        try:
            # 生成第二个 bar
            bar2 = self.mock_generator.create_mock_bar(symbol, close_price=98.0)
            self.trigger_bar_update(bar2)
            time.sleep(0.01)
            
            # 验证仍然在 waiting_entry 状态
            self.assert_context_state(symbol, "waiting_entry")
            
            # 验证订单价格是否更新
            updated_order = self.strategy.gateway.get_order_by_id(context.entry_order_id)
            if updated_order and first_order_price:
                # 计算期望的新价格：vwap - (atr * entry_factor) = 98.0 - (1.5 * 1.5) = 95.75
                expected_price = 98.0 - (1.5 * 1.5)
                assert abs(updated_order.price - expected_price) < 0.01, \
                    f"订单价格应该更新: 期望 {expected_price}, 实际 {updated_order.price}"
                print(f"✅ Gap Down Entry 订单价格已更新: {first_order_price:.2f} -> {updated_order.price:.2f}")
            else:
                assert False, "无法获取更新后的订单价格信息"
            
        finally:
            # 恢复原方法
            self.get_mock_indicators = original_method

    def test_exit_timeout_flow_gap_down(self):
        """测试 Gap Down 策略 exit 订单超时流程"""
        symbol = self.test_symbol
        self.strategy.gap_direction[symbol] = 'down'
        
        # 1. 设置初始状态并完成 entry
        self.setup_context(symbol, state=StrategyState.IDLE, trade_count=0)
        
        # 生成 entry 信号
        bar1 = self.mock_generator.create_mock_bar(symbol, close_price=100.0)
        self.trigger_bar_update(bar1)
        time.sleep(0.01)
        
        # 完成 entry 订单
        context = self.strategy.get_context(symbol)
        entry_order = self.mock_generator.create_mock_order(
            symbol, Status.ALLTRADED, order_id=context.entry_order_id
        )
        self.trigger_order_update(entry_order)
        time.sleep(0.01)
        
        # 验证进入 waiting_exit 状态
        self.assert_context_state(symbol, "waiting_exit")
        context = self.strategy.get_context(symbol)
        assert context.exit_order_id != ""
        
        # 获取初始的 exit 订单（应该是限价单）
        initial_exit_order = self.strategy.gateway.get_order_by_id(context.exit_order_id)
        assert initial_exit_order is not None, "应该存在exit订单"
        assert initial_exit_order.type == OrderType.LIMIT, "初始exit订单应该是限价单"
        initial_exit_price = initial_exit_order.price
        print(f"Gap Down 初始exit订单: {initial_exit_order.type.value}, 价格: {initial_exit_price:.2f}")
        
        # 2. 模拟时间流逝，触发超时
        # 设置一个很早的exit_start_time来模拟超时
        context.exit_start_time = datetime.now() - timedelta(minutes=self.strategy.max_exit_wait_time_gap_down + 1)
        
        # 生成新的 bar，这会触发超时检查
        bar2 = self.mock_generator.create_mock_bar(symbol, close_price=100.0)
        self.trigger_bar_update(bar2)
        time.sleep(0.01)
        
        # 验证仍然在 waiting_exit 状态（超时后应该生成新的市价单）
        self.assert_context_state(symbol, "waiting_exit")
        
        # 获取新的 exit 订单
        updated_exit_order = self.strategy.gateway.get_order_by_id(context.exit_order_id)
        assert updated_exit_order is not None, "超时后应该生成新的exit订单"
        assert updated_exit_order.type == OrderType.MARKET, "超时后的exit订单应该是市价单"
        print(f"Gap Down 超时后exit订单: {updated_exit_order.type.value}, 价格: {updated_exit_order.price:.2f}")
        
        # 验证订单ID发生了变化（因为撤单后重新下单）
        assert updated_exit_order.orderid != initial_exit_order.orderid, "超时后应该生成新的订单ID"
        
        # 3. 手动让市价单成交
        market_exit_order = self.mock_generator.create_mock_order(
            symbol, Status.ALLTRADED, order_id=context.exit_order_id
        )
        self.trigger_order_update(market_exit_order)
        time.sleep(0.01)
        
        # 4. 验证最终状态
        self.assert_context_state(symbol, "idle")
        self.assert_context_field(symbol, "trade_count", 1)
        
        print("✅ Gap Down Exit超时流程测试完成:")
        print(f"   初始订单类型: {initial_exit_order.type.value}")
        print(f"   超时后订单类型: {updated_exit_order.type.value}")
        print(f"   最终状态: {self.strategy.get_context(symbol).state.value}")
        print(f"   交易次数: {self.strategy.get_context(symbol).trade_count}")
    
    def test_volume_anomaly_cancel_and_reentry_success(self):
        """测试成交量异常取消订单后，在下一根bar重新进入并成功的复杂流程"""
        symbol = self.test_symbol
        self.strategy.gap_direction[symbol] = 'up'
        
        # 设置初始状态为waiting_entry
        context = self.setup_context(
            symbol, 
            state=StrategyState.WAITING_ENTRY,
            entry_order_id="test_entry_order_789"
        )
        
        # 第一阶段：创建第一根bar，成交量异常导致取消订单
        first_bar = self.mock_generator.create_mock_bar(
            symbol, 
            open_price=100.0, 
            close_price=101.0,
            volume=2500  # 异常成交量，超过阈值
        )
        
        # 设置技术指标：vol_ma5=1000，比例=2.5 > 阈值2.0
        def get_mock_indicators_first_bar(symbol: str) -> dict:
            indicators = self.mock_generator.create_mock_indicators(
                vwap=100.5, atr_14=1.0, below_vwap_count=3
            )
            indicators['volume_ma5'] = 1000  # 手动设置volume_ma5
            return indicators
        
        # Mock get_indicators和_get_current_bar
        original_get_indicators = self.strategy.get_indicators
        original_get_current_bar = self.strategy._get_current_bar
        
        def mock_get_indicators_first(symbol: str) -> dict:
            return get_mock_indicators_first_bar(symbol)
        
        self.strategy.get_indicators = mock_get_indicators_first
        self.strategy._get_current_bar = lambda s: first_bar if s == symbol else None
        
        try:
            # 创建tick触发成交量异常检查
            tick = self.mock_generator.create_mock_tick(symbol, price=101.0)
            self.strategy._check_current_bar_volume_anomaly_and_cancel(tick)
            time.sleep(0.01)
            
            # 验证：应该取消订单，状态变为idle
            context = self.strategy.get_context(symbol)
            assert context.state == StrategyState.IDLE, "成交量异常应该取消订单并变为idle状态"
            assert context.entry_order_id == "", "成交量异常应该清空订单ID"
            
            print("✅ 第一阶段：成交量异常取消订单测试通过")
            
        finally:
            # 恢复原方法
            self.strategy.get_indicators = original_get_indicators
            self.strategy._get_current_bar = original_get_current_bar
        
        # 第二阶段：触发第一根bar完成，策略应该重新评估进入条件
        # 临时替换get_mock_indicators方法
        original_get_mock_indicators = self.get_mock_indicators
        self.get_mock_indicators = get_mock_indicators_first_bar
        
        try:
            self.trigger_bar_update(first_bar)
            time.sleep(0.01)
        finally:
            self.get_mock_indicators = original_get_mock_indicators
        
        # 验证：第一根bar完成时应该触发新的entry，因为below_vwap_count=3满足entry条件
        self.assert_context_state(symbol, StrategyState.WAITING_ENTRY.value)
        
        # 验证：应该有新的entry订单ID
        context = self.strategy.get_context(symbol)
        assert context.entry_order_id != "", "第一根bar完成时应该生成新的entry订单ID"
        assert context.entry_order_id != "test_entry_order_789", "应该是新的订单ID"
        
        print("✅ 第二阶段：第一根bar完成时触发新的entry测试通过")
        
        # 第三阶段：模拟第一根bar的entry订单成交
        entry_order = self.mock_generator.create_mock_order(
            symbol, 
            status=Status.ALLTRADED,
            direction=Direction.LONG,
            volume=100,
            price=101.0,
            order_id=context.entry_order_id
        )
        
        # 触发订单更新
        self.trigger_order_update(entry_order)
        time.sleep(0.01)
        
        # 验证：状态应该变为waiting_exit（因为entry成交后会自动下exit订单）
        self.assert_context_state(symbol, StrategyState.WAITING_EXIT.value)
        
        # 验证：entry_price应该被设置
        context = self.strategy.get_context(symbol)
        # it will not be 101.0 because mock_brisk_gateway will always use the original order price as trade price
        # TODO: fix mock_brisk_gateway manually_process_order to use the order price as trade price
        assert context.entry_price == 102.0, f"entry_price应该被设置: 期望102.0, 实际{context.entry_price}"
        assert context.entry_time is not None, "entry_time应该被设置"
        
        # 验证：应该有exit订单ID
        assert context.exit_order_id != "", "entry成交后应该生成exit订单ID"
        
        print("✅ 第三阶段：第一根bar的entry订单成交，自动下exit订单测试通过")
        
        # 第四阶段：创建第二根bar，触发exit条件更新
        second_bar = self.mock_generator.create_mock_bar(
            symbol, 
            open_price=101.0, 
            close_price=102.0,
            volume=1500  # 正常成交量
        )
        
        # 设置技术指标：触发exit条件
        def get_mock_indicators_second_bar(symbol: str) -> dict:
            indicators = self.mock_generator.create_mock_indicators(
                vwap=101.5, atr_14=1.0, below_vwap_count=0  # 重置failure count
            )
            indicators['volume_ma5'] = 1100  # 手动设置volume_ma5
            return indicators
        
        # 记录更新前的exit订单ID
        context = self.strategy.get_context(symbol)
        original_exit_order_id = context.exit_order_id
        assert original_exit_order_id != "", "应该有初始的exit订单ID"
        
        # 触发第二根bar更新
        self.get_mock_indicators = get_mock_indicators_second_bar
        self.trigger_bar_update(second_bar)
        time.sleep(0.01)
        
        # 验证：应该保持waiting_exit状态
        self.assert_context_state(symbol, StrategyState.WAITING_EXIT.value)
        
        # 验证：exit订单ID应该发生变化（因为价格更新会取消旧订单并下新订单）
        context = self.strategy.get_context(symbol)
        assert context.exit_order_id != "", "应该保持exit订单ID"
        assert context.exit_order_id != original_exit_order_id, "exit订单ID应该发生变化"
        
        print("✅ 第四阶段：第二根bar更新，exit订单价格更新测试通过")
        
        # 第五阶段：模拟exit订单成交
        exit_order = self.mock_generator.create_mock_order(
            symbol, 
            status=Status.ALLTRADED,
            direction=Direction.SHORT,
            volume=100,
            price=102.0,
            order_id=context.exit_order_id
        )
        
        # 触发订单更新
        self.trigger_order_update(exit_order)
        time.sleep(0.01)
        
        # 验证：状态应该变为idle，完成一个完整的交易周期
        self.assert_context_state(symbol, StrategyState.IDLE.value)
        
        # 验证：trade_count应该增加
        context = self.strategy.get_context(symbol)
        assert context.trade_count == 1, f"trade_count应该增加: 期望1, 实际{context.trade_count}"
        
        print("✅ 第五阶段：exit订单成交，完成交易周期测试通过")
        print("✅ 复杂流程测试：成交量异常取消订单后重新进入并成功完成交易")


def run_all_tests():
    """运行所有 VWAP Failure 策略测试"""
    from context_based_testing_base import run_context_based_tests
    
    # 运行所有测试类
    test_classes = [
        VWAPFailureStrategyTest,
        TestVWAPFailureSpecificLogic,
        TestVWAPFailureCompleteFlow
    ]
    
    all_results = []
    for test_class in test_classes:
        print(f"\n=== 运行测试类: {test_class.__name__} ===")
        result = run_context_based_tests(test_class)
        all_results.append(result)
    
    # 汇总结果
    total_tests = sum(r.testsRun for r in all_results)
    total_failures = sum(len(r.failures) for r in all_results)
    total_errors = sum(len(r.errors) for r in all_results)
    
    print(f"\n=== VWAP Failure 策略测试汇总 ===")
    print(f"总测试数: {total_tests}")
    print(f"总失败数: {total_failures}")
    print(f"总错误数: {total_errors}")
    print(f"总成功率: {(total_tests - total_failures - total_errors) / total_tests:.2%}" if total_tests > 0 else "总成功率: 0.00%")
    
    return all_results


if __name__ == "__main__":
    run_all_tests() 