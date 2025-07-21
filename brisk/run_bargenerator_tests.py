#!/usr/bin/env python3
"""
BarGenerator测试运行器
运行统一的BarGenerator测试文件
"""

import sys
import os
import unittest
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run_bargenerator_tests():
    """运行BarGenerator测试"""
    print("=" * 60)
    print("BarGenerator 统一测试")
    print("=" * 60)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 导入测试模块
    from test_bargenerator_unified import BarGeneratorUnifiedTest
    
    # 创建测试套件
    test_suite = unittest.TestLoader().loadTestsFromTestCase(BarGeneratorUnifiedTest)
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # 输出结果统计
    print("\n" + "=" * 60)
    print("测试结果统计")
    print("=" * 60)
    print(f"运行测试数: {result.testsRun}")
    print(f"失败测试数: {len(result.failures)}")
    print(f"错误测试数: {len(result.errors)}")
    print(f"跳过测试数: {len(result.skipped) if hasattr(result, 'skipped') else 0}")
    
    if result.failures:
        print("\n失败测试详情:")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback.split('AssertionError:')[-1].strip()}")
    
    if result.errors:
        print("\n错误测试详情:")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback.split('Exception:')[-1].strip()}")
    
    print(f"\n结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return result.wasSuccessful()

if __name__ == "__main__":
    success = run_bargenerator_tests()
    sys.exit(0 if success else 1) 