"""
运行所有HFT BB相关的测试
"""

import unittest
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def run_all_tests():
    """运行所有HFT BB相关的测试"""
    
    # 创建测试套件
    test_suite = unittest.TestSuite()
    
    # 添加所有测试模块
    test_modules = [
        'test_trigger_levels',
        'test_hft_bb_stock_context', 
        'test_trigger_calculation',
        'test_on_1min_bar',
        'test_on_tick',
        'test_entry_logic',
        'test_manage_exit_order',
        'test_on_order',
        'test_hft_bb_complete',
        'test_x_condition'
    ]
    
    # 加载并添加每个测试模块
    for module_name in test_modules:
        try:
            module = __import__(module_name)
            test_suite.addTest(unittest.defaultTestLoader.loadTestsFromModule(module))
            print(f"✓ 加载测试模块: {module_name}")
        except ImportError as e:
            print(f"✗ 无法加载测试模块 {module_name}: {e}")
        except Exception as e:
            print(f"✗ 加载测试模块 {module_name} 时出错: {e}")
    
    # 运行测试
    print(f"\n开始运行 {test_suite.countTestCases()} 个测试...")
    print("=" * 60)
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # 输出结果摘要
    print("\n" + "=" * 60)
    print("测试结果摘要:")
    print(f"  总测试数: {result.testsRun}")
    print(f"  成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"  失败: {len(result.failures)}")
    print(f"  错误: {len(result.errors)}")
    
    if result.failures:
        print("\n失败的测试:")
        for test, traceback in result.failures:
            print(f"  - {test}: {traceback.split('AssertionError: ')[-1].split('\\n')[0]}")
    
    if result.errors:
        print("\n错误的测试:")
        for test, traceback in result.errors:
            error_lines = traceback.split('\\n')
            error_msg = error_lines[-2] if len(error_lines) > 1 else traceback
            print(f"  - {test}: {error_msg}")
    
    # 返回是否所有测试都通过
    return len(result.failures) == 0 and len(result.errors) == 0

if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
