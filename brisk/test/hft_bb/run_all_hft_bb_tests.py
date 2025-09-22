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
    'test_tick_price_alignment',       # tick价格对齐测试
    'test_eligible_stocks',            # eligible stock功能测试
    'test_entry_order_time_optimization',  # entry_order_time优化测试
    'test_partial_fill_logging',       # 部分成交日志记录测试
    'test_partial_fill_handling',      # 部分成交处理测试
    'test_std_pct_x_condition',        # std_pct X条件测试
    'test_active_entry_order_x_condition',  # 活跃entry订单X条件测试
    'test_entry_logic_position_protection',  # entry逻辑持仓保护测试
    'test_bb_levels_unification',           # BB levels统一化测试
    'test_preload_context_edge_case',       # preload context edge case测试
    'test_market_close_liquidation',        # 收盘前平仓测试
    'test_enhanced_cancel_order',           # 增强撤单功能测试
    'test_lunch_break_cancel',              # 午休时间取消entry orders测试
    'test_afternoon_time_window_exclusion', # 下午时间窗口排除15:00分钟测试
    'test_x_condition_entry_order_cancellation', # X条件检查与entry订单取消逻辑测试
    'test_entry_price_change_logic',             # entry价格变化逻辑测试
    'test_on_1min_bar',
    'test_on_tick',
    'test_entry_logic',
    'test_manage_exit_order',
    'test_on_order',
    'test_hft_bb_complete',
    'test_x_condition',
    'test_parameter_update',           # 参数更新系统测试
    'test_position_size_usage',        # position_size使用测试
    'test_time_window_directions',     # 时间窗口交易方向配置测试
    'test_can_trade_direction_control', # can_trade方向控制测试
    'test_stop_loss',                  # 止损功能测试
    'test_lunch_break_cancel_protection', # 中午休市期间取消订单保护测试
    'test_15_24_cancel_protection'     # 15:24分钟取消订单保护测试
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
            print(f"  - {test}: {traceback.split('AssertionError: ')[-1].split('\n')[0]}")
    
    if result.errors:
        print("\n错误的测试:")
        for test, traceback in result.errors:
            error_lines = traceback.split('\n')
            error_msg = error_lines[-2] if len(error_lines) > 1 else traceback
            print(f"  - {test}: {error_msg}")
    
    # 返回是否所有测试都通过
    return len(result.failures) == 0 and len(result.errors) == 0

if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)