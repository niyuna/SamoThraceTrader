"""
测试BriskHistoricalDataProvider
"""

import unittest
import os
import tempfile
import pandas as pd
from datetime import datetime, time
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hft_bb_indicators import BriskHistoricalDataProvider
from vnpy.trader.object import BarData
from vnpy.trader.constant import Exchange, Interval


class TestBriskHistoricalDataProvider(unittest.TestCase):
    """测试BriskHistoricalDataProvider"""
    
    def setUp(self):
        """测试前的准备工作"""
        # 创建临时目录
        self.temp_dir = tempfile.mkdtemp()
        self.provider = BriskHistoricalDataProvider(self.temp_dir)
        
        # 创建测试数据
        self.test_date = "20250724"
        self.create_test_csv()
    
    def tearDown(self):
        """测试后的清理工作"""
        # 清理临时文件
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def create_test_csv(self):
        """创建测试用的CSV文件"""
        # 创建测试数据
        test_data = []
        
        # 为股票9984创建数据（最后20个bar，时间范围910-930）
        for i in range(20):
            ts_1m = 910 + i  # 15:10 到 15:30
            test_data.append({
                'sc': '9984',  # 确保是字符串
                'ts_1m': ts_1m,
                'vol': 1000 + i * 10,
                'turnover': (1000 + i * 10) * (1000 + i * 0.5),
                'o': 1000 + i * 0.5,
                'h': 1000 + i * 0.5 + 0.2,
                'l': 1000 + i * 0.5 - 0.2,
                'c': 1000 + i * 0.5 + 0.1,
                'buy': 500 + i * 5,
                'sell': 500 + i * 5,
                'vol_cum': 10000 + i * 100,
                'turnover_cum': 10000000 + i * 1000
            })
        
        # 为股票6098创建数据
        for i in range(20):
            ts_1m = 910 + i
            test_data.append({
                'sc': '6098',  # 确保是字符串
                'ts_1m': ts_1m,
                'vol': 800 + i * 8,
                'turnover': (800 + i * 8) * (800 + i * 0.4),
                'o': 800 + i * 0.4,
                'h': 800 + i * 0.4 + 0.15,
                'l': 800 + i * 0.4 - 0.15,
                'c': 800 + i * 0.4 + 0.08,
                'buy': 400 + i * 4,
                'sell': 400 + i * 4,
                'vol_cum': 8000 + i * 80,
                'turnover_cum': 8000000 + i * 800
            })
        
        # 创建DataFrame并保存为CSV
        df = pd.DataFrame(test_data)
        file_path = os.path.join(self.temp_dir, f"brisk_ohlc_{self.test_date}_ts_1m.csv")
        df.to_csv(file_path, index=False)
    
    def test_initialization(self):
        """测试初始化"""
        self.assertEqual(self.provider.data_dir, self.temp_dir)
        self.assertEqual(self.provider.cached_data, {})
        self.assertEqual(self.provider.required_columns, ['sc', 'ts_1m', 'vol', 'turnover', 'o', 'h', 'l', 'c'])
    
    def test_is_data_available(self):
        """测试数据可用性检查"""
        # 测试存在的文件
        self.assertTrue(self.provider.is_data_available("9984", self.test_date))
        
        # 测试不存在的文件
        self.assertFalse(self.provider.is_data_available("9984", "20250101"))
    
    def test_load_daily_data_single_symbol(self):
        """测试加载单个股票的数据"""
        # 加载单个股票数据
        self.provider.load_daily_data(self.test_date, ["9984"])
        
        # 检查缓存
        self.assertIn(self.test_date, self.provider.cached_data)
        self.assertIn("9984", self.provider.cached_data[self.test_date])
        
        # 检查数据量
        bars = self.provider.cached_data[self.test_date]["9984"]
        self.assertEqual(len(bars), 20)
        
        # 检查第一个bar
        first_bar = bars[0]
        self.assertEqual(first_bar.symbol, "9984")
        self.assertEqual(first_bar.exchange, Exchange.TSE)
        self.assertEqual(first_bar.interval, Interval.MINUTE)
        self.assertEqual(first_bar.gateway_name, "BriskData")
        
        # 检查时间转换（第一个bar应该是15:10）
        expected_time = datetime.combine(datetime.strptime(self.test_date, "%Y%m%d").date(), time(15, 10))
        self.assertEqual(first_bar.datetime, expected_time)
    
    def test_load_daily_data_multiple_symbols(self):
        """测试加载多个股票的数据"""
        # 加载多个股票数据
        symbols = ["9984", "6098"]
        self.provider.load_daily_data(self.test_date, symbols)
        
        # 检查缓存
        self.assertIn(self.test_date, self.provider.cached_data)
        for symbol in symbols:
            self.assertIn(symbol, self.provider.cached_data[self.test_date])
            self.assertEqual(len(self.provider.cached_data[self.test_date][symbol]), 20)
    
    def test_get_historical_bars(self):
        """测试获取历史数据"""
        # 获取历史数据
        bars = self.provider.get_historical_bars("9984", self.test_date, 20)
        
        # 检查返回结果
        self.assertEqual(len(bars), 20)
        self.assertIsInstance(bars[0], BarData)
        
        # 检查数据顺序（应该按时间升序）
        for i in range(1, len(bars)):
            self.assertLessEqual(bars[i-1].datetime, bars[i].datetime)
        
        # 检查价格数据
        self.assertGreater(bars[0].open_price, 0)
        self.assertGreater(bars[0].high_price, 0)
        self.assertGreater(bars[0].low_price, 0)
        self.assertGreater(bars[0].close_price, 0)
        self.assertGreater(bars[0].volume, 0)
        self.assertGreater(bars[0].turnover, 0)
    
    def test_get_historical_bars_partial_count(self):
        """测试获取部分数据"""
        # 获取最后10个bar
        bars = self.provider.get_historical_bars("9984", self.test_date, 10)
        
        # 检查返回结果
        self.assertEqual(len(bars), 10)
        
        # 检查时间顺序（应该是最后10个）
        for i in range(1, len(bars)):
            self.assertLessEqual(bars[i-1].datetime, bars[i].datetime)
    
    def test_get_multiple_symbols_data(self):
        """测试批量获取多个股票数据"""
        symbols = ["9984", "6098"]
        result = self.provider.get_multiple_symbols_data(symbols, self.test_date, 20)
        
        # 检查返回结果
        self.assertEqual(len(result), 2)
        for symbol in symbols:
            self.assertIn(symbol, result)
            self.assertEqual(len(result[symbol]), 20)
    
    def test_cache_functionality(self):
        """测试缓存功能"""
        # 第一次获取数据
        bars1 = self.provider.get_historical_bars("9984", self.test_date, 20)
        
        # 第二次获取数据（应该从缓存获取）
        bars2 = self.provider.get_historical_bars("9984", self.test_date, 20)
        
        # 检查缓存信息
        cache_info = self.provider.get_cache_info()
        self.assertIn(self.test_date, cache_info["cached_dates"])
        self.assertEqual(cache_info["total_symbols"], 1)
        
        # 清除缓存
        self.provider.clear_cache(self.test_date)
        cache_info = self.provider.get_cache_info()
        self.assertEqual(cache_info["total_symbols"], 0)
    
    def test_data_conversion_accuracy(self):
        """测试数据转换的准确性"""
        bars = self.provider.get_historical_bars("9984", self.test_date, 20)
        
        # 检查第一个bar的数据转换
        first_bar = bars[0]
        
        # 检查时间转换（ts_1m=910应该对应15:10）
        expected_datetime = datetime.combine(
            datetime.strptime(self.test_date, "%Y%m%d").date(),
            time(15, 10)
        )
        self.assertEqual(first_bar.datetime, expected_datetime)
        
        # 检查价格数据（第一个bar的o应该是1000.0）
        self.assertEqual(first_bar.open_price, 1000.0)
        self.assertEqual(first_bar.high_price, 1000.2)
        self.assertEqual(first_bar.low_price, 999.8)
        self.assertEqual(first_bar.close_price, 1000.1)
        
        # 检查成交量数据
        self.assertEqual(first_bar.volume, 1000)
        self.assertEqual(first_bar.turnover, 1000 * 1000.0)
    
    def test_error_handling(self):
        """测试错误处理"""
        # 测试不存在的文件
        bars = self.provider.get_historical_bars("9984", "20250101", 20)
        self.assertEqual(len(bars), 0)
        
        # 测试不存在的股票
        bars = self.provider.get_historical_bars("9999", self.test_date, 20)
        self.assertEqual(len(bars), 0)
    
    def test_time_range_validation(self):
        """测试时间范围验证"""
        bars = self.provider.get_historical_bars("9984", self.test_date, 20)
        
        # 检查所有bar的时间都在合理范围内（15:10-15:30）
        for bar in bars:
            hour = bar.datetime.hour
            minute = bar.datetime.minute
            
            # 应该在15:10到15:30之间
            self.assertGreaterEqual(hour, 15)
            if hour == 15:
                self.assertGreaterEqual(minute, 10)
                self.assertLessEqual(minute, 30)


def run_tests():
    """运行所有测试"""
    print("开始测试BriskHistoricalDataProvider...")
    
    # 创建测试套件
    test_suite = unittest.TestSuite()
    
    # 添加测试用例
    test_suite.addTest(unittest.TestLoader().loadTestsFromTestCase(TestBriskHistoricalDataProvider))
    
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
