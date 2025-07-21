"""
VWAP Failure 策略步骤1测试
测试开仓订单执行逻辑
使用Mock Brisk Gateway进行测试
"""

import sys
import os
import time
from datetime import datetime, timedelta
from collections import defaultdict

# 添加父目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vnpy.trader.constant import Direction, Offset, Status, OrderType, Exchange
from vnpy.trader.object import OrderData, OrderRequest, BarData
from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.object import SubscribeRequest

from vwap_failure_strategy import VWAPFailureStrategy
from mock_brisk_gateway import MockBriskGateway


class VWAPFailureStep1Tester:
    """VWAP Failure 策略步骤1测试器"""
    
    def __init__(self):
        """初始化测试器"""
        self.strategy = None
        self.mock_gateway = None
        self.test_results = {
            'entry_orders_created': 0,
            'entry_orders_rejected': 0,
            'entry_orders_filled': 0,
            'price_updates': 0,
            'signals_generated': 0
        }
        self.test_status = {}  # 记录每个测试的通过状态
        
    def setup_strategy(self):
        """设置策略"""
        # 创建事件引擎
        event_engine = EventEngine()
        
        # 创建主引擎
        main_engine = MainEngine(event_engine)
        
        # 添加Mock Brisk Gateway
        main_engine.add_gateway(MockBriskGateway)
        self.mock_gateway = main_engine.get_gateway("MOCK_BRISK")
        
        # 配置Mock Gateway
        setting = {
            "tick_mode": "mock",
            "mock_tick_interval": 0.1,  # 快速生成tick用于测试
            "mock_price_volatility": 0.01,
            "mock_volume_range": (100, 1000),
            "mock_base_prices": {
                "7203": 2500.0,  # 丰田
                "6758": 1800.0,  # 索尼
                "9984": 8000.0,  # 软银
            },
            "mock_account_balance": 10000000,  # 1000万日元
            "mock_commission_rate": 0.001,
            "mock_slippage": 0.0,
            "mock_fill_delay": 0.1,
        }
        
        # 创建策略实例
        self.strategy = VWAPFailureStrategy()
        self.strategy.event_engine = event_engine
        self.strategy.main_engine = main_engine
        self.strategy.gateway = self.mock_gateway
        self.strategy.gateway_name = "MOCK_BRISK"
        self.strategy.brisk_gateway = self.mock_gateway
        
        # 设置策略参数
        self.strategy.set_strategy_params(
            market_cap_threshold=100_000_000_000,  # 1000亿日元
            gap_up_threshold=0.02,      # 2% gap up
            gap_down_threshold=-0.02,   # -2% gap down
            failure_threshold=3,        # VWAP failure次数阈值
            entry_factor=1.5,           # ATR倍数
            max_daily_trades=3,         # 单日最大交易次数
            latest_entry_time="14:30:00"  # 最晚入场时间
        )
        
        # 连接Mock Gateway（使用我们的配置）
        main_engine.connect(setting, "MOCK_BRISK")
        
        # 初始化股票筛选器
        self.strategy.initialize_stock_filter()
        
        print("策略设置完成，使用Mock Brisk Gateway")
    
    def mock_stock_data(self):
        """模拟股票数据"""
        # 模拟股票基础信息
        self.strategy.stock_master = {
            "7203": {
                "market_cap": 150_000_000_000,  # 1500亿日元
                "basePrice10": 2500,  # 昨日收盘价250日元
                "calcSharesOutstanding": 6000000000
            },
            "6758": {
                "market_cap": 120_000_000_000,  # 1200亿日元
                "basePrice10": 1800,  # 昨日收盘价180日元
                "calcSharesOutstanding": 6666666667
            },
            "9984": {
                "market_cap": 80_000_000_000,   # 800亿日元（不满足条件）
                "basePrice10": 8000,  # 昨日收盘价800日元
                "calcSharesOutstanding": 1000000000
            }
        }
        
        # 模拟市值筛选结果
        self.strategy.market_cap_eligible = {"7203", "6758"}
        self.strategy.eligible_stocks = {"7203", "6758"}
        
        # 模拟gap方向
        self.strategy.gap_direction = {
            "7203": "up",    # Gap Up
            "6758": "down"   # Gap Down
        }
        
        # 模拟第一个tick价格
        self.strategy.first_tick_prices = {
            "7203": 255.0,  # Gap Up 2%
            "6758": 176.4   # Gap Down -2%
        }
        
        print("模拟股票数据设置完成")
    
    def create_mock_bar(self, symbol, time_str, close_price, vwap, atr, above_vwap_count, below_vwap_count):
        """创建模拟K线数据"""
        bar = BarData(
            symbol=symbol,
            exchange=Exchange.TSE,
            datetime=datetime.strptime(f"2025-07-18 {time_str}", "%Y-%m-%d %H:%M:%S"),
            interval=None,
            volume=1000,
            turnover=close_price * 1000,
            open_price=close_price,
            high_price=close_price + 1,
            low_price=close_price - 1,
            close_price=close_price,
            gateway_name="MOCK_BRISK"
        )
        
        # 创建模拟技术指标
        indicators = {
            'vwap': vwap,
            'atr_14': atr,
            'above_vwap_count': above_vwap_count,
            'below_vwap_count': below_vwap_count,
            'equal_vwap_count': 0,
            'volume_ma5': 1000,
            'daily_acc_volume': 10000,
            'daily_acc_turnover': vwap * 10000
        }
        
        return bar, indicators
    
    def test_entry_signal_generation(self):
        """测试开仓信号生成"""
        print("\n=== 测试开仓信号生成 ===")
        
        # 测试Gap Up股票的做空信号
        print("测试Gap Up股票(7203)的做空信号:")
        bar, indicators = self.create_mock_bar(
            symbol="7203",
            time_str="09:15:00",
            close_price=250.0,
            vwap=252.0,
            atr=2.0,
            above_vwap_count=0,
            below_vwap_count=3  # 满足failure阈值
        )
        
        # 手动调用信号生成
        self.strategy._generate_trading_signal(bar, indicators)
        
        # 检查是否创建了entry订单
        short_order_created = "7203" in self.strategy.entry_orders
        if short_order_created:
            order = self.strategy.entry_orders["7203"]
            print(f"✓ 成功创建做空entry订单: {order.direction.value} 价格: {order.price:.2f}")
            self.test_results['entry_orders_created'] += 1
            self.test_results['signals_generated'] += 1
        else:
            print("✗ 未创建entry订单")
        
        # 测试Gap Down股票的做多信号
        print("\n测试Gap Down股票(6758)的做多信号:")
        bar, indicators = self.create_mock_bar(
            symbol="6758",
            time_str="09:16:00",
            close_price=180.0,
            vwap=178.0,
            atr=1.5,
            above_vwap_count=3,  # 满足failure阈值
            below_vwap_count=0
        )
        
        # 手动调用信号生成
        self.strategy._generate_trading_signal(bar, indicators)
        
        # 检查是否创建了entry订单
        long_order_created = "6758" in self.strategy.entry_orders
        if long_order_created:
            order = self.strategy.entry_orders["6758"]
            print(f"✓ 成功创建做多entry订单: {order.direction.value} 价格: {order.price:.2f}")
            self.test_results['entry_orders_created'] += 1
            self.test_results['signals_generated'] += 1
        else:
            print("✗ 未创建entry订单")
        
        # 记录测试状态
        test_passed = short_order_created and long_order_created
        self.test_status['entry_signal_generation'] = test_passed
        return test_passed
    
    def test_order_rejection(self):
        """测试订单拒绝处理"""
        print("\n=== 测试订单拒绝处理 ===")
        
        # 模拟订单被拒绝的情况
        print("测试订单拒绝处理:")
        
        # 创建一个会被拒绝的订单
        order_req = OrderRequest(
            symbol="7203",
            exchange=Exchange.TSE,
            direction=Direction.SHORT,
            type=OrderType.LIMIT,
            volume=100,
            price=255.0,
            offset=Offset.OPEN,
            reference="test_rejection"
        )
        
        # 手动调用拒绝处理
        self.strategy._handle_entry_rejection("7203", order_req)
        
        # 检查订单状态
        test_passed = False
        if "7203" in self.strategy.entry_orders:
            order = self.strategy.entry_orders["7203"]
            if order.status == Status.REJECTED:
                print("✓ 订单拒绝处理正确")
                self.test_results['entry_orders_rejected'] += 1
                test_passed = True
            else:
                print(f"✗ 订单状态错误: {order.status}")
        else:
            print("✗ 未找到被拒绝的订单")
        
        # 记录测试状态
        self.test_status['order_rejection'] = test_passed
        return test_passed
    
    def test_price_update(self):
        """测试订单价格更新"""
        print("\n=== 测试订单价格更新 ===")
        
        # 创建一个活跃的entry订单
        order_data = OrderData(
            symbol="7203",
            exchange=Exchange.TSE,
            orderid="test_update",
            type=OrderType.LIMIT,
            direction=Direction.SHORT,
            offset=Offset.OPEN,
            price=255.0,
            volume=100,
            status=Status.NOTTRADED,
            gateway_name="MOCK_BRISK"
        )
        
        self.strategy.entry_orders["7203"] = order_data
        
        print("测试订单价格更新:")
        old_price = order_data.price
        
        # 创建新的bar和indicators
        bar, indicators = self.create_mock_bar(
            symbol="7203",
            time_str="09:17:00",
            close_price=248.0,
            vwap=250.0,
            atr=2.5,
            above_vwap_count=0,
            below_vwap_count=4
        )
        
        # 手动调用价格更新
        self.strategy._update_entry_order_price(order_data, bar, indicators)
        
        # 检查价格是否更新
        test_passed = order_data.price != old_price
        if test_passed:
            print(f"✓ 订单价格已更新: {old_price:.2f} -> {order_data.price:.2f}")
            self.test_results['price_updates'] += 1
        else:
            print("✗ 订单价格未更新")
        
        # 记录测试状态
        self.test_status['price_update'] = test_passed
        return test_passed
    
    def test_signal_blocking(self):
        """测试信号阻塞（当有活跃订单时不应生成新信号）"""
        print("\n=== 测试信号阻塞 ===")
        self.strategy.entry_orders.clear()
        self.strategy.gap_direction["7203"] = "up"
        # 第一次调用：应该生成订单
        bar1, indicators1 = self.create_mock_bar(
            symbol="7203",
            time_str="09:15:00",
            close_price=245.0,
            vwap=248.0,
            atr=2.0,
            above_vwap_count=0,
            below_vwap_count=5
        )
        initial_call_count = self.mock_gateway.order_call_count
        self.strategy._generate_trading_signal(bar1, indicators1)
        after_first_call = self.mock_gateway.order_call_count
        if after_first_call == initial_call_count + 1:
            print(f"✓ 第一次信号触发下单，order_call_count: {initial_call_count} -> {after_first_call}")
        else:
            print(f"✗ 第一次信号未触发下单，order_call_count: {initial_call_count} -> {after_first_call}")
            self.test_status['signal_blocking'] = False
            return False
        # 第二次调用：应该被阻塞
        bar2, indicators2 = self.create_mock_bar(
            symbol="7203",
            time_str="09:18:00",
            close_price=240.0,
            vwap=248.0,
            atr=2.0,
            above_vwap_count=0,
            below_vwap_count=6
        )
        self.strategy._generate_trading_signal(bar2, indicators2)
        after_second_call = self.mock_gateway.order_call_count
        test_passed = after_second_call == after_first_call
        if test_passed:
            print(f"✓ 成功阻止新信号生成（有活跃订单时），order_call_count未变: {after_first_call}")
        else:
            print(f"✗ 未能阻止新信号生成，order_call_count变化: {after_first_call} -> {after_second_call}")
        self.test_status['signal_blocking'] = test_passed
        return test_passed
    
    def test_daily_trade_limit(self):
        """测试单日交易次数限制"""
        print("\n=== 测试单日交易次数限制 ===")
        self.strategy.entry_orders.clear()
        self.strategy.gap_direction["7203"] = "up"
        self.strategy.daily_trade_counts["7203"] = 3  # 达到最大限制
        bar, indicators = self.create_mock_bar(
            symbol="7203",
            time_str="09:19:00",
            close_price=240.0,
            vwap=245.0,
            atr=2.0,
            above_vwap_count=0,
            below_vwap_count=6
        )
        initial_call_count = self.mock_gateway.order_call_count
        self.strategy._generate_trading_signal(bar, indicators)
        after_call_count = self.mock_gateway.order_call_count
        test_passed = after_call_count == initial_call_count
        if test_passed:
            print(f"✓ 成功阻止新信号生成（达到交易次数限制），order_call_count未变: {after_call_count}")
        else:
            print(f"✗ 未能阻止新信号生成，order_call_count变化: {initial_call_count} -> {after_call_count}")
        self.test_status['daily_trade_limit'] = test_passed
        return test_passed
    
    def test_trading_time_limit(self):
        """测试交易时间限制"""
        print("\n=== 测试交易时间限制 ===")
        self.strategy.entry_orders.clear()
        self.strategy.gap_direction["7203"] = "up"
        bar, indicators = self.create_mock_bar(
            symbol="7203",
            time_str="14:35:00",  # 超过14:30:00
            close_price=240.0,
            vwap=245.0,
            atr=2.0,
            above_vwap_count=0,
            below_vwap_count=6
        )
        initial_call_count = self.mock_gateway.order_call_count
        self.strategy._generate_trading_signal(bar, indicators)
        after_call_count = self.mock_gateway.order_call_count
        test_passed = after_call_count == initial_call_count
        if test_passed:
            print(f"✓ 成功阻止新信号生成（超过交易时间），order_call_count未变: {after_call_count}")
        else:
            print(f"✗ 未能阻止新信号生成，order_call_count变化: {initial_call_count} -> {after_call_count}")
        self.test_status['trading_time_limit'] = test_passed
        return test_passed
    
    def test_mock_gateway_integration(self):
        """测试Mock Gateway集成"""
        print("\n=== 测试Mock Gateway集成 ===")
        
        # 测试Mock Gateway状态
        test_passed = True
        
        # 检查Mock Gateway是否正常初始化
        if not self.mock_gateway:
            print("✗ Mock Gateway未初始化")
            test_passed = False
        else:
            print("✓ Mock Gateway初始化成功")
        
        # 检查Mock账户
        try:
            account = self.mock_gateway.get_mock_account()
            if account and account.balance > 0:
                print(f"✓ Mock账户正常，余额: {account.balance}")
            else:
                print("✗ Mock账户异常")
                test_passed = False
        except Exception as e:
            print(f"✗ 获取Mock账户失败: {e}")
            test_passed = False
        
        # 检查Mock持仓
        try:
            positions = self.mock_gateway.get_mock_positions()
            print(f"✓ Mock持仓获取成功，持仓数量: {len(positions)}")
        except Exception as e:
            print(f"✗ 获取Mock持仓失败: {e}")
            test_passed = False
        
        # 记录测试状态
        self.test_status['mock_gateway_integration'] = test_passed
        return test_passed
    
    def run_all_tests(self):
        """运行所有测试"""
        print("开始VWAP Failure策略步骤1测试（使用Mock Brisk Gateway）...")
        
        # 设置策略
        self.setup_strategy()
        
        # 模拟股票数据
        self.mock_stock_data()
        
        # 运行各项测试并收集结果
        test_results = []
        test_results.append(("Mock Gateway集成", self.test_mock_gateway_integration()))
        test_results.append(("开仓信号生成", self.test_entry_signal_generation()))
        test_results.append(("订单拒绝处理", self.test_order_rejection()))
        test_results.append(("价格更新功能", self.test_price_update()))
        test_results.append(("信号阻塞功能", self.test_signal_blocking()))
        test_results.append(("交易次数限制", self.test_daily_trade_limit()))
        test_results.append(("交易时间限制", self.test_trading_time_limit()))
        
        # 打印测试结果
        self.print_test_results(test_results)
        
        # 清理
        print("开始清理资源...")
        if self.strategy:
            try:
                # 停止事件引擎
                if hasattr(self.strategy, 'event_engine') and self.strategy.event_engine:
                    print("停止事件引擎...")
                    self.strategy.event_engine.stop()
                
                # 关闭策略
                print("关闭策略...")
                self.strategy.close()
                
                print("策略清理完成")
            except Exception as e:
                print(f"清理过程中出现错误: {e}")
                import traceback
                traceback.print_exc()
        
        print("测试完成")
    
    def print_test_results(self, test_results):
        """打印测试结果"""
        print("\n=== 测试结果汇总 ===")
        print(f"开仓订单创建: {self.test_results['entry_orders_created']}")
        print(f"开仓订单拒绝: {self.test_results['entry_orders_rejected']}")
        print(f"开仓订单成交: {self.test_results['entry_orders_filled']}")
        print(f"价格更新次数: {self.test_results['price_updates']}")
        print(f"信号生成次数: {self.test_results['signals_generated']}")
        
        print(f"\n=== 测试项目详情 ===")
        passed_tests = 0
        total_tests = len(test_results)
        
        for test_name, passed in test_results:
            status = "✓ 通过" if passed else "✗ 失败"
            print(f"{test_name}: {status}")
            if passed:
                passed_tests += 1
        
        print(f"\n测试通过率: {passed_tests}/{total_tests} ({passed_tests/total_tests*100:.1f}%)")
        
        if passed_tests == total_tests:
            print("🎉 所有测试通过！")
        else:
            print(f"⚠️  有 {total_tests - passed_tests} 个测试失败")


def main():
    """主函数"""
    try:
        tester = VWAPFailureStep1Tester()
        tester.run_all_tests()
        print("\n程序正常结束")
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    except Exception as e:
        print(f"\n程序运行出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("程序退出")


if __name__ == "__main__":
    main() 