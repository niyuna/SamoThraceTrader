"""
测试HFT BB Reversal策略的修正版技术指标类
"""

import unittest
from datetime import datetime, timedelta
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hft_bb_indicators import HFTBBReversalIndicatorV2, MockHistoricalDataProvider
from vnpy.trader.object import BarData
from vnpy.trader.constant import Exchange, Interval


class TestHFTBBReversalIndicatorV2(unittest.TestCase):
    """测试HFT BB Reversal策略的修正版技术指标类"""
    
    def setUp(self):
        """测试前的准备工作"""
        self.symbol = "9984"
        self.indicator = HFTBBReversalIndicatorV2(self.symbol, size=25, bb_period=20)
        self.provider = MockHistoricalDataProvider()
    
    def test_initialization(self):
        """测试初始化"""
        self.assertEqual(self.indicator.symbol, self.symbol)
        self.assertEqual(self.indicator.bb_period, 20)
        self.assertEqual(self.indicator.entry_std_multiplier, 3.0)
        self.assertEqual(self.indicator.exit_std_multiplier, 0.1)
        self.assertFalse(self.indicator.is_preloaded)
        self.assertFalse(self.indicator.is_ready_for_trading())
        self.assertFalse(self.indicator.is_inited())
        self.assertEqual(self.indicator.get_historical_bars_needed(), 20)
    
    def test_preload_historical_bars(self):
        """测试预加载历史数据功能"""
        # 获取历史数据
        historical_bars = self.provider.get_historical_bars(self.symbol, "20250725", 25)
        self.assertEqual(len(historical_bars), 25)
        
        # 预加载历史数据
        self.indicator.preload_historical_bars(historical_bars)
        
        # 检查预加载状态
        self.assertTrue(self.indicator.is_preloaded)
        self.assertTrue(self.indicator.is_ready_for_trading())
        self.assertTrue(self.indicator.is_inited())
        
        # 检查BB指标是否计算正确
        bb_levels = self.indicator.get_bb_levels()
        self.assertIsInstance(bb_levels, dict)
        self.assertIn("upper", bb_levels)
        self.assertIn("lower", bb_levels)
        self.assertIn("middle", bb_levels)
        self.assertIn("exit_long", bb_levels)
        self.assertIn("exit_short", bb_levels)
        self.assertIn("std", bb_levels)
        self.assertIn("period", bb_levels)
        self.assertIn("entry_multiplier", bb_levels)
        self.assertIn("exit_multiplier", bb_levels)
        
        # 检查价格水平是否合理
        self.assertGreater(bb_levels["upper"], bb_levels["middle"])
        self.assertLess(bb_levels["lower"], bb_levels["middle"])
        self.assertGreater(bb_levels["exit_short"], bb_levels["middle"])
        self.assertLess(bb_levels["exit_long"], bb_levels["middle"])
        
        # 检查参数是否正确
        self.assertEqual(bb_levels["period"], 20)
        self.assertEqual(bb_levels["entry_multiplier"], 3.0)
        self.assertEqual(bb_levels["exit_multiplier"], 0.1)
    
    def test_preload_insufficient_data(self):
        """测试预加载数据不足的情况"""
        # 只提供10个bar，少于需要的20个
        historical_bars = self.provider.get_historical_bars(self.symbol, "20250725", 10)
        self.assertEqual(len(historical_bars), 10)
        
        # 预加载历史数据
        self.indicator.preload_historical_bars(historical_bars)
        
        # 检查预加载状态应该为False
        self.assertFalse(self.indicator.is_preloaded)
        self.assertFalse(self.indicator.is_ready_for_trading())
    
    def test_preload_empty_data(self):
        """测试预加载空数据的情况"""
        # 预加载空数据
        self.indicator.preload_historical_bars([])
        
        # 检查预加载状态应该为False
        self.assertFalse(self.indicator.is_preloaded)
        self.assertFalse(self.indicator.is_ready_for_trading())
    
    def test_update_bar(self):
        """测试更新bar数据功能"""
        # 先预加载历史数据
        historical_bars = self.provider.get_historical_bars(self.symbol, "20250725", 25)
        self.indicator.preload_historical_bars(historical_bars)
        
        # 创建新的bar数据
        new_bar = BarData(
            symbol=self.symbol,
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            interval=Interval.MINUTE,
            volume=1500,
            turnover=1500 * 1005.0,
            open_price=1004.0,
            high_price=1006.0,
            low_price=1003.0,
            close_price=1005.0,
            gateway_name="TEST"
        )
        
        # 更新bar
        bb_levels = self.indicator.update_bar(new_bar)
        
        # 检查返回的BB指标
        self.assertIsInstance(bb_levels, dict)
        self.assertIn("upper", bb_levels)
        self.assertIn("lower", bb_levels)
        self.assertIn("middle", bb_levels)
        
        # 检查缓存的指标值
        self.assertGreater(self.indicator.get_sma(), 0)
        self.assertGreater(self.indicator.get_std(), 0)
    
    def test_date_change_handling(self):
        """测试日期变化处理"""
        # 先预加载历史数据
        historical_bars = self.provider.get_historical_bars(self.symbol, "20250725", 25)
        self.indicator.preload_historical_bars(historical_bars)
        
        # 记录初始日期
        initial_date = self.indicator.current_date
        
        # 创建新日期的bar
        new_date = datetime.now().date()
        new_bar = BarData(
            symbol=self.symbol,
            exchange=Exchange.TSE,
            datetime=datetime.combine(new_date, datetime.min.time()),
            interval=Interval.MINUTE,
            volume=1500,
            turnover=1500 * 1005.0,
            open_price=1004.0,
            high_price=1006.0,
            low_price=1003.0,
            close_price=1005.0,
            gateway_name="TEST"
        )
        
        # 更新bar（应该触发日期变化处理）
        self.indicator.update_bar(new_bar)
        
        # 检查日期是否更新
        self.assertEqual(self.indicator.current_date, new_date)
    
    def test_getter_methods(self):
        """测试各种getter方法"""
        # 先预加载历史数据
        historical_bars = self.provider.get_historical_bars(self.symbol, "20250725", 25)
        self.indicator.preload_historical_bars(historical_bars)
        
        # 测试get_bb_levels
        bb_levels = self.indicator.get_bb_levels()
        self.assertIsInstance(bb_levels, dict)
        self.assertGreater(len(bb_levels), 0)
        
        # 测试get_sma
        sma = self.indicator.get_sma()
        self.assertIsInstance(sma, float)
        self.assertGreater(sma, 0)
        
        # 测试get_std
        std = self.indicator.get_std()
        self.assertIsInstance(std, float)
        self.assertGreater(std, 0)
        
        # 测试get_indicators（统一接口）
        indicators = self.indicator.get_indicators()
        self.assertIsInstance(indicators, dict)
        self.assertEqual(indicators, bb_levels)
        
        # 测试get_array_manager
        am = self.indicator.get_array_manager()
        self.assertIsNotNone(am)
        self.assertTrue(am.inited)
    
    def test_reset_daily(self):
        """测试每日重置功能"""
        # 先预加载历史数据
        historical_bars = self.provider.get_historical_bars(self.symbol, "20250725", 25)
        self.indicator.preload_historical_bars(historical_bars)
        
        # 设置一个日期
        test_date = datetime.now().date()
        self.indicator.reset_daily(test_date)
        
        # 检查日期是否设置正确
        self.assertEqual(self.indicator.current_date, test_date)
    
    def test_bb_calculation_accuracy(self):
        """测试BB指标计算的准确性"""
        # 创建已知价格的测试数据
        test_bars = []
        base_price = 1000.0
        
        for i in range(25):
            price = base_price + i * 0.5  # 线性增长
            bar = BarData(
                symbol=self.symbol,
                exchange=Exchange.TSE,
                datetime=datetime.now() - timedelta(minutes=25-i),
                interval=Interval.MINUTE,
                volume=1000,
                turnover=1000 * price,
                open_price=price,
                high_price=price + 0.1,
                low_price=price - 0.1,
                close_price=price,
                gateway_name="TEST"
            )
            test_bars.append(bar)
        
        # 预加载测试数据
        self.indicator.preload_historical_bars(test_bars)
        
        # 获取BB指标
        bb_levels = self.indicator.get_bb_levels()
        
        # 验证BB指标的基本关系
        self.assertGreater(bb_levels["upper"], bb_levels["middle"])
        self.assertLess(bb_levels["lower"], bb_levels["middle"])
        self.assertGreater(bb_levels["exit_short"], bb_levels["middle"])
        self.assertLess(bb_levels["exit_long"], bb_levels["middle"])
        
        # 验证entry和exit水平的关系
        self.assertGreater(bb_levels["upper"], bb_levels["exit_short"])
        self.assertLess(bb_levels["lower"], bb_levels["exit_long"])
    
    def test_multiple_symbols(self):
        """测试多个股票符号"""
        # 创建另一个股票指标
        symbol2 = "6098"
        indicator2 = HFTBBReversalIndicatorV2(symbol2, size=25, bb_period=20)
        
        # 获取不同股票的数据
        bars1 = self.provider.get_historical_bars(self.symbol, "20250725", 25)
        bars2 = self.provider.get_historical_bars(symbol2, "20250725", 25)
        
        # 预加载数据
        self.indicator.preload_historical_bars(bars1)
        indicator2.preload_historical_bars(bars2)
        
        # 检查两个指标都正确初始化
        self.assertTrue(self.indicator.is_ready_for_trading())
        self.assertTrue(indicator2.is_ready_for_trading())
        
        # 检查两个指标的数据不同（因为基础价格不同）
        bb1 = self.indicator.get_bb_levels()
        bb2 = indicator2.get_bb_levels()
        
        self.assertNotEqual(bb1["middle"], bb2["middle"])
    
    def test_edge_cases(self):
        """测试边界情况"""
        # 测试未初始化时的getter方法
        self.assertEqual(self.indicator.get_bb_levels(), {})
        self.assertEqual(self.indicator.get_sma(), 0.0)
        self.assertEqual(self.indicator.get_std(), 0.0)
        self.assertEqual(self.indicator.get_indicators(), {})
        
        # 测试ArrayManager未初始化时的状态
        self.assertFalse(self.indicator.is_inited())
        self.assertFalse(self.indicator.is_ready_for_trading())
    
    def test_preload_functionality(self):
        """测试预加载功能"""
        # 创建模拟数据提供者
        provider = MockHistoricalDataProvider()
        
        # 获取历史数据
        historical_bars = provider.get_historical_bars(self.symbol, "20250725", 25)
        self.assertEqual(len(historical_bars), 25)
        
        # 预加载历史数据
        self.indicator.preload_historical_bars(historical_bars)
        
        # 检查预加载状态
        self.assertTrue(self.indicator.is_ready_for_trading())
        bb_levels = self.indicator.get_bb_levels()
        self.assertGreater(bb_levels.get('upper', 0), 0)
        self.assertGreater(bb_levels.get('lower', 0), 0)
        self.assertGreater(bb_levels.get('middle', 0), 0)
    
    def test_real_time_update(self):
        """测试实时更新功能"""
        # 先预加载历史数据
        historical_bars = self.provider.get_historical_bars(self.symbol, "20250725", 25)
        self.indicator.preload_historical_bars(historical_bars)
        
        # 创建新的bar数据
        new_bar = BarData(
            symbol=self.symbol,
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            interval=Interval.MINUTE,
            volume=1200,
            turnover=1200000,
            open_price=1001.0,
            high_price=1002.0,
            low_price=1000.5,
            close_price=1001.5,
            gateway_name="MOCK"
        )
        
        # 更新指标
        bb_levels = self.indicator.update_bar(new_bar)
        
        # 检查更新结果
        self.assertIsInstance(bb_levels, dict)
        self.assertIn("upper", bb_levels)
        self.assertIn("lower", bb_levels)
        self.assertIn("middle", bb_levels)
        self.assertGreater(bb_levels.get('upper', 0), 0)
        self.assertGreater(bb_levels.get('lower', 0), 0)
        self.assertGreater(bb_levels.get('middle', 0), 0)


def run_tests():
    """运行所有测试"""
    print("开始测试HFT BB Reversal策略的修正版技术指标类...")
    
    # 创建测试套件
    test_suite = unittest.TestSuite()
    
    # 添加测试用例
    test_suite.addTest(unittest.TestLoader().loadTestsFromTestCase(TestHFTBBReversalIndicatorV2))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # 返回测试结果
    return result.wasSuccessful()


def main():
    """主测试函数"""
    success = run_tests()
    if success:
        print("\n=== 所有测试通过！ ===")
    else:
        print("\n=== 部分测试失败！ ===")


if __name__ == "__main__":
    main()
