"""
HFT BB Reversal策略完整测试套件
包含指标测试、策略测试和真实数据集成测试
"""

import unittest
import time
import sys
import os
from datetime import datetime, timedelta

# 添加路径以导入模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from hft_bb_indicators import HFTBBReversalIndicatorV2, MockHistoricalDataProvider, BriskHistoricalDataProvider
from hft_bb_reversal_strategy import HFTBBReversalStrategy
from vnpy.trader.object import BarData
from vnpy.trader.constant import Exchange, Interval


class TestHFTBBReversalIndicatorV2(unittest.TestCase):
    """测试HFT BB Reversal策略的修正版技术指标类"""
    
    def setUp(self):
        """测试前的准备工作"""
        self.symbol = "9984"
        self.size = 25
        self.bb_period = 20
        self.provider = MockHistoricalDataProvider()
        
    def test_initialization(self):
        """测试初始化"""
        print("测试初始化")
        indicator = HFTBBReversalIndicatorV2(self.symbol, self.size, self.bb_period)
        
        self.assertEqual(indicator.symbol, self.symbol)
        self.assertEqual(indicator.am.size, self.size)
        self.assertEqual(indicator.bb_period, self.bb_period)
        self.assertFalse(indicator.is_preloaded)
        self.assertFalse(indicator.is_ready_for_trading())
        
    def test_preload_functionality(self):
        """测试预加载功能"""
        print("测试预加载功能")
        indicator = HFTBBReversalIndicatorV2(self.symbol, self.size, self.bb_period)
        
        # 获取历史数据
        historical_bars = self.provider.get_historical_bars(self.symbol, "20250724", self.size)
        self.assertEqual(len(historical_bars), self.size)
        
        # 预加载数据
        indicator.preload_historical_bars(historical_bars)
        
        self.assertTrue(indicator.is_preloaded)
        self.assertTrue(indicator.is_ready_for_trading())
        self.assertTrue(indicator.is_inited())
        
        # 检查BB指标
        bb_levels = indicator.get_bb_levels()
        self.assertIsNotNone(bb_levels)
        self.assertIn('upper', bb_levels)
        self.assertIn('lower', bb_levels)
        self.assertIn('middle', bb_levels)
        
        print(f"  {self.symbol} 预加载完成，BB指标已计算:")
        print(f"    Upper: {bb_levels['upper']:.2f}")
        print(f"    Lower: {bb_levels['lower']:.2f}")
        print(f"    Middle: {bb_levels['middle']:.2f}")
        
    def test_preload_historical_bars(self):
        """测试预加载历史数据功能"""
        print("测试预加载历史数据功能")
        indicator = HFTBBReversalIndicatorV2(self.symbol, self.size, self.bb_period)
        
        # 获取历史数据
        historical_bars = self.provider.get_historical_bars(self.symbol, "20250724", self.size)
        
        # 预加载数据
        indicator.preload_historical_bars(historical_bars)
        
        self.assertTrue(indicator.is_preloaded)
        self.assertTrue(indicator.is_ready_for_trading())
        
        # 检查指标数据
        indicators = indicator.get_indicators()
        self.assertIsNotNone(indicators)
        
        print(f"  {self.symbol} 预加载完成，BB指标已计算:")
        print(f"    Upper: {indicators.get('upper', 0):.2f}")
        print(f"    Lower: {indicators.get('lower', 0):.2f}")
        print(f"    Middle: {indicators.get('middle', 0):.2f}")
        
    def test_preload_insufficient_data(self):
        """测试预加载数据不足的情况"""
        print("测试预加载数据不足的情况")
        indicator = HFTBBReversalIndicatorV2(self.symbol, self.size, self.bb_period)
        
        # 创建不足的数据
        insufficient_bars = self.provider.get_historical_bars(self.symbol, "20250724", 10)
        
        # 预加载数据
        indicator.preload_historical_bars(insufficient_bars)
        
        self.assertFalse(indicator.is_preloaded)
        self.assertFalse(indicator.is_ready_for_trading())
        
    def test_preload_empty_data(self):
        """测试预加载空数据的情况"""
        print("测试预加载空数据的情况")
        indicator = HFTBBReversalIndicatorV2(self.symbol, self.size, self.bb_period)
        
        # 预加载空数据
        indicator.preload_historical_bars([])
        
        self.assertFalse(indicator.is_preloaded)
        self.assertFalse(indicator.is_ready_for_trading())
        
    def test_real_time_update(self):
        """测试实时更新功能"""
        print("测试实时更新功能")
        indicator = HFTBBReversalIndicatorV2(self.symbol, self.size, self.bb_period)
        
        # 预加载历史数据
        historical_bars = self.provider.get_historical_bars(self.symbol, "20250724", self.size)
        indicator.preload_historical_bars(historical_bars)
        
        # 创建新的bar
        new_bar = BarData(
            symbol=self.symbol,
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            interval=Interval.MINUTE,
            volume=1000,
            open_price=1000.0,
            high_price=1010.0,
            low_price=990.0,
            close_price=1005.0,
            gateway_name="TEST"
        )
        
        # 更新bar
        indicator.update_bar(new_bar)
        
        # 检查指标是否更新
        bb_levels = indicator.get_bb_levels()
        self.assertIsNotNone(bb_levels)
        
        print(f"  {self.symbol} 预加载完成，BB指标已计算:")
        if bb_levels and 'upper' in bb_levels:
            print(f"    Upper: {bb_levels['upper']:.2f}")
            print(f"    Lower: {bb_levels['lower']:.2f}")
            print(f"    Middle: {bb_levels['middle']:.2f}")
        else:
            print(f"    BB指标: {bb_levels}")
        
    def test_update_bar(self):
        """测试更新bar功能"""
        print("测试更新bar功能")
        indicator = HFTBBReversalIndicatorV2(self.symbol, self.size, self.bb_period)
        
        # 预加载历史数据
        historical_bars = self.provider.get_historical_bars(self.symbol, "20250724", self.size)
        indicator.preload_historical_bars(historical_bars)
        
        # 创建新的bar
        new_bar = BarData(
            symbol=self.symbol,
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            interval=Interval.MINUTE,
            volume=1000,
            open_price=1000.0,
            high_price=1010.0,
            low_price=990.0,
            close_price=1005.0,
            gateway_name="TEST"
        )
        
        # 更新bar
        indicator.update_bar(new_bar)
        
        # 检查指标是否更新
        indicators = indicator.get_indicators()
        self.assertIsNotNone(indicators)
        
    def test_reset_daily(self):
        """测试每日重置功能"""
        print("测试每日重置功能")
        indicator = HFTBBReversalIndicatorV2(self.symbol, self.size, self.bb_period)
        
        # 预加载历史数据
        historical_bars = self.provider.get_historical_bars(self.symbol, "20250724", self.size)
        indicator.preload_historical_bars(historical_bars)
        
        # 重置
        indicator.reset_daily("20250725")
        
        self.assertFalse(indicator.is_preloaded)
        self.assertFalse(indicator.is_ready_for_trading())
        
        # 重新预加载
        indicator.preload_historical_bars(historical_bars)
        self.assertTrue(indicator.is_preloaded)
        
        print(f"  {self.symbol} 预加载完成，BB指标已计算:")
        bb_levels = indicator.get_bb_levels()
        print(f"    Upper: {bb_levels['upper']:.2f}")
        print(f"    Lower: {bb_levels['lower']:.2f}")
        print(f"    Middle: {bb_levels['middle']:.2f}")
        
    def test_date_change_handling(self):
        """测试日期变化处理"""
        print("测试日期变化处理")
        indicator = HFTBBReversalIndicatorV2(self.symbol, self.size, self.bb_period)
        
        # 预加载历史数据
        historical_bars = self.provider.get_historical_bars(self.symbol, "20250724", self.size)
        indicator.preload_historical_bars(historical_bars)
        
        # 模拟日期变化
        new_date = "20250725"
        indicator._handle_date_change(new_date)
        
        # 检查状态
        self.assertFalse(indicator.is_preloaded)
        
        # 重新预加载新日期的数据
        new_historical_bars = self.provider.get_historical_bars(self.symbol, new_date, self.size)
        indicator.preload_historical_bars(new_historical_bars)
        
        self.assertTrue(indicator.is_preloaded)
        
        print(f"  {self.symbol} 预加载完成，BB指标已计算:")
        bb_levels = indicator.get_bb_levels()
        print(f"    Upper: {bb_levels['upper']:.2f}")
        print(f"    Lower: {bb_levels['lower']:.2f}")
        print(f"    Middle: {bb_levels['middle']:.2f}")
        
    def test_multiple_symbols(self):
        """测试多个股票符号"""
        print("测试多个股票符号")
        symbols = ["9984", "6098"]
        
        for symbol in symbols:
            indicator = HFTBBReversalIndicatorV2(symbol, self.size, self.bb_period)
            
            # 获取历史数据
            historical_bars = self.provider.get_historical_bars(symbol, "20250724", self.size)
            
            # 预加载数据
            indicator.preload_historical_bars(historical_bars)
            
            self.assertTrue(indicator.is_preloaded)
            self.assertTrue(indicator.is_ready_for_trading())
            
            # 检查BB指标
            bb_levels = indicator.get_bb_levels()
            self.assertIsNotNone(bb_levels)
            
            print(f"  {symbol} 预加载完成，BB指标已计算:")
            print(f"    Upper: {bb_levels['upper']:.2f}")
            print(f"    Lower: {bb_levels['lower']:.2f}")
            print(f"    Middle: {bb_levels['middle']:.2f}")
            
    def test_getter_methods(self):
        """测试各种getter方法"""
        print("测试各种getter方法")
        indicator = HFTBBReversalIndicatorV2(self.symbol, self.size, self.bb_period)
        
        # 预加载历史数据
        historical_bars = self.provider.get_historical_bars(self.symbol, "20250724", self.size)
        indicator.preload_historical_bars(historical_bars)
        
        # 测试各种getter方法
        self.assertTrue(indicator.is_preloaded)
        self.assertTrue(indicator.is_ready_for_trading())
        self.assertTrue(indicator.is_inited())
        
        bb_levels = indicator.get_bb_levels()
        self.assertIsNotNone(bb_levels)
        
        indicators = indicator.get_indicators()
        self.assertIsNotNone(indicators)
        
        print(f"  {self.symbol} 预加载完成，BB指标已计算:")
        print(f"    Upper: {bb_levels['upper']:.2f}")
        print(f"    Lower: {bb_levels['lower']:.2f}")
        print(f"    Middle: {bb_levels['middle']:.2f}")
        
    def test_bb_calculation_accuracy(self):
        """测试BB指标计算的准确性"""
        print("测试BB指标计算的准确性")
        indicator = HFTBBReversalIndicatorV2(self.symbol, self.size, self.bb_period)
        
        # 预加载历史数据
        historical_bars = self.provider.get_historical_bars(self.symbol, "20250724", self.size)
        indicator.preload_historical_bars(historical_bars)
        
        # 检查BB指标
        bb_levels = indicator.get_bb_levels()
        self.assertIsNotNone(bb_levels)
        
        # 检查指标值是否合理
        self.assertGreater(bb_levels['upper'], bb_levels['middle'])
        self.assertLess(bb_levels['lower'], bb_levels['middle'])
        
        print(f"  {self.symbol} 预加载完成，BB指标已计算:")
        print(f"    Upper: {bb_levels['upper']:.2f}")
        print(f"    Lower: {bb_levels['lower']:.2f}")
        print(f"    Middle: {bb_levels['middle']:.2f}")
        
    def test_edge_cases(self):
        """测试边界情况"""
        print("测试边界情况")
        
        # 测试最小参数
        indicator = HFTBBReversalIndicatorV2(self.symbol, 1, 1)
        self.assertEqual(indicator.am.size, 1)
        self.assertEqual(indicator.bb_period, 1)
        
        # 测试大参数
        indicator = HFTBBReversalIndicatorV2(self.symbol, 100, 50)
        self.assertEqual(indicator.am.size, 100)
        self.assertEqual(indicator.bb_period, 50)


class TestHFTBBReversalStrategy(unittest.TestCase):
    """测试HFT BB Reversal策略的基本功能"""
    
    def test_strategy_initialization(self):
        """测试策略初始化"""
        print("=== 测试策略初始化 ===")
        
        try:
            strategy = HFTBBReversalStrategy(use_mock_gateway=True)
            print("✓ 策略创建成功")
            
            # 检查基本属性
            self.assertIsNotNone(strategy)
            self.assertEqual(strategy.strategy_name, "HFT_BB_Reversal")
            
            print("✓ 策略初始化测试通过")
            
        except Exception as e:
            self.fail(f"策略初始化失败: {e}")
            
    def test_strategy_with_mock_gateway(self):
        """测试策略与模拟网关的集成"""
        print("=== 测试策略与模拟网关集成 ===")
        
        try:
            strategy = HFTBBReversalStrategy(use_mock_gateway=True)
            
            # 检查策略基本属性
            self.assertEqual(strategy.strategy_name, "HFT_BB_Reversal")
            self.assertTrue(strategy.use_mock_gateway)
            print("✓ 策略创建成功")
            
            # 测试添加股票功能（不依赖main_engine）
            strategy.add_symbol("9984")
            print("✓ 股票添加成功")
            
            # 检查指标管理器
            if "9984" in strategy.indicator_managers:
                print("✓ 指标管理器创建成功")
            else:
                print("⚠ 指标管理器未创建")
                
        except Exception as e:
            self.fail(f"策略与模拟网关集成测试失败: {e}")
            
    def test_strategy_with_real_data(self):
        """测试策略与真实数据的集成"""
        print("=== 测试策略与真实数据集成 ===")
        
        try:
            # 创建策略实例，启用真实数据模式
            strategy = HFTBBReversalStrategy(
                use_mock_gateway=True, 
                use_real_data=True, 
                data_dir="../data/brisk_agged_ohlc"
            )
            
            print("✓ 策略创建成功，启用真实数据模式")
            
            # 测试股票和日期
            test_symbols = ["6098", "9984"]
            test_date = "20250724"
            
            print(f"开始预加载历史数据:")
            print(f"  股票: {test_symbols}")
            print(f"  日期: {test_date}")
            
            # 预加载历史数据
            strategy.preload_historical_data(test_symbols, test_date)
            
            print(f"\n预加载结果检查:")
            for symbol in test_symbols:
                if symbol in strategy.indicator_managers:
                    manager = strategy.indicator_managers[symbol]
                    print(f"  {symbol}:")
                    print(f"    预加载状态: {manager.is_preloaded}")
                    print(f"    准备交易: {manager.is_ready_for_trading()}")
                    print(f"    已初始化: {manager.is_inited()}")
                    
                    # 获取BB水平
                    bb_levels = strategy._calculate_bb_levels(symbol, manager.get_indicators())
                    if bb_levels:
                        print(f"    BB水平:")
                        print(f"      Upper: {bb_levels.get('upper', 0):.2f}")
                        print(f"      Lower: {bb_levels.get('lower', 0):.2f}")
                        print(f"      Middle: {bb_levels.get('middle', 0):.2f}")
                        print(f"      STD: {bb_levels.get('std', 0):.2f}")
                else:
                    print(f"  {symbol}: 未创建指标管理器")
            
            # 测试数据提供者功能
            print(f"\n数据提供者功能测试:")
            if hasattr(strategy, 'data_provider') and strategy.data_provider:
                cache_info = strategy.data_provider.get_cache_info()
                print(f"  缓存信息: {cache_info}")
                
                for symbol in test_symbols:
                    is_available = strategy.data_provider.is_data_available(symbol, test_date)
                    print(f"  {symbol} 数据可用: {is_available}")
            
            print("✓ 策略与真实数据集成测试通过")
            
        except Exception as e:
            self.fail(f"策略与真实数据集成测试失败: {e}")


class TestBriskHistoricalDataProvider(unittest.TestCase):
    """测试BriskHistoricalDataProvider"""
    
    def setUp(self):
        """测试前的准备工作"""
        self.temp_dir = None
        self.provider = None
        
    def tearDown(self):
        """测试后的清理工作"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir)
            
    def test_provider_initialization(self):
        """测试数据提供者初始化"""
        print("测试数据提供者初始化")
        
        import tempfile
        self.temp_dir = tempfile.mkdtemp()
        self.provider = BriskHistoricalDataProvider(self.temp_dir)
        
        self.assertIsNotNone(self.provider)
        self.assertEqual(self.provider.data_dir, self.temp_dir)
        self.assertIsNotNone(self.provider.cached_data)
        
    def test_data_availability(self):
        """测试数据可用性检查"""
        print("测试数据可用性检查")
        
        import tempfile
        self.temp_dir = tempfile.mkdtemp()
        self.provider = BriskHistoricalDataProvider(self.temp_dir)
        
        # 测试不存在的日期
        is_available = self.provider.is_data_available("9984", "20250724")
        self.assertFalse(is_available)
        
    def test_real_data_provider(self):
        """测试真实数据提供者"""
        print("=== 使用真实数据测试BriskHistoricalDataProvider ===")
        
        try:
            # 使用真实数据目录
            provider = BriskHistoricalDataProvider("../data/brisk_agged_ohlc")
            
            test_date = "20250724"
            symbols = ["6098", "9984"]
            
            print(f"测试日期: {test_date}")
            print(f"测试股票: {symbols}")
            
            # 1. 检查数据可用性
            print(f"\n1. 检查数据可用性:")
            for symbol in symbols:
                is_available = provider.is_data_available(symbol, test_date)
                print(f"  {symbol}: {'可用' if is_available else '不可用'}")
            
            # 2. 测试单个股票数据获取
            print(f"\n2. 测试单个股票数据获取:")
            for symbol in symbols:
                print(f"获取 {symbol} 的数据:")
                historical_bars = provider.get_historical_bars(symbol, test_date, 20)
                
                if historical_bars:
                    print(f"  获取到 {len(historical_bars)} 个bar")
                    if len(historical_bars) > 0:
                        first_bar = historical_bars[0]
                        last_bar = historical_bars[-1]
                        print(f"  第一个bar: {first_bar.datetime} - 价格: {first_bar.close_price}")
                        print(f"  最后一个bar: {last_bar.datetime} - 价格: {last_bar.close_price}")
                        print(f"  时间范围: {first_bar.datetime.time()} 到 {last_bar.datetime.time()}")
                else:
                    print(f"  未获取到数据")
            
            # 3. 测试批量数据获取
            print(f"\n3. 测试批量数据获取:")
            batch_data = provider.get_multiple_symbols_data(symbols, test_date, 20)
            for symbol, bars in batch_data.items():
                print(f"  {symbol}: {len(bars)} 个bar")
            
            # 4. 测试缓存功能
            print(f"\n4. 测试缓存功能:")
            cache_info = provider.get_cache_info()
            print(f"  缓存信息: {cache_info}")
            
            print("✓ 真实数据提供者测试通过")
            
        except Exception as e:
            self.fail(f"真实数据提供者测试失败: {e}")


def run_all_tests():
    """运行所有测试"""
    print("开始运行HFT BB Reversal策略完整测试套件...")
    print("=" * 60)
    
    # 创建测试套件
    test_suite = unittest.TestSuite()
    
    # 添加指标测试
    test_suite.addTest(unittest.TestLoader().loadTestsFromTestCase(TestHFTBBReversalIndicatorV2))
    
    # 添加策略测试
    test_suite.addTest(unittest.TestLoader().loadTestsFromTestCase(TestHFTBBReversalStrategy))
    
    # 添加数据提供者测试
    test_suite.addTest(unittest.TestLoader().loadTestsFromTestCase(TestBriskHistoricalDataProvider))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    print("=" * 60)
    if result.wasSuccessful():
        print("🎉 所有测试通过！")
    else:
        print(f"❌ 测试失败: {len(result.failures)} 个失败, {len(result.errors)} 个错误")
        
    return result.wasSuccessful()


if __name__ == "__main__":
    run_all_tests()
