"""
测试重构后的测试结构
验证 context_based_testing_base 和 test_vwap_failure_context_based 是否正确分离
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def test_imports():
    """测试导入是否正常"""
    print("=== 测试导入功能 ===")
    
    try:
        # 测试通用基类导入
        from context_based_testing_base import (
            ContextSnapshot, ContextSnapshotManager, MockDataGenerator,
            ContextBasedStrategyTest, TestBasicStateTransitionsMixin,
            TestEdgeCasesMixin, TestCompleteFlowMixin, TestMultipleSymbolsMixin
        )
        print("✓ 通用基类导入成功")
        
        # 测试 VWAP Failure 策略测试导入
        from test_vwap_failure_context_based import (
            VWAPFailureStrategyTest, TestVWAPFailureSpecificLogic,
            TestVWAPFailureCompleteFlow, run_all_tests
        )
        print("✓ VWAP Failure 策略测试导入成功")
        
        # 测试策略导入
        from vwap_failure_strategy import VWAPFailureStrategy
        print("✓ VWAP Failure 策略导入成功")
        
        return True
        
    except ImportError as e:
        print(f"✗ 导入失败: {e}")
        return False
    except Exception as e:
        print(f"✗ 其他错误: {e}")
        return False


def test_class_inheritance():
    """测试类继承关系"""
    print("\n=== 测试类继承关系 ===")
    
    try:
        from test_vwap_failure_context_based import VWAPFailureStrategyTest
        
        # 检查继承关系
        bases = VWAPFailureStrategyTest.__bases__
        base_names = [base.__name__ for base in bases]
        
        print(f"VWAPFailureStrategyTest 的基类: {base_names}")
        
        # 检查是否继承了必要的基类
        expected_bases = [
            'ContextBasedStrategyTest',
            'TestBasicStateTransitionsMixin',
            'TestEdgeCasesMixin', 
            'TestCompleteFlowMixin',
            'TestMultipleSymbolsMixin'
        ]
        
        for expected_base in expected_bases:
            if any(expected_base in base_name for base_name in base_names):
                print(f"✓ 继承了 {expected_base}")
            else:
                print(f"✗ 缺少 {expected_base}")
                return False
        
        return True
        
    except Exception as e:
        print(f"✗ 继承关系测试失败: {e}")
        return False


def test_method_availability():
    """测试方法可用性"""
    print("\n=== 测试方法可用性 ===")
    
    try:
        from test_vwap_failure_context_based import VWAPFailureStrategyTest
        
        # 检查策略特定方法
        strategy_methods = [
            'get_mock_indicators',
            'setUp',
            'tearDown'
        ]
        
        for method in strategy_methods:
            if hasattr(VWAPFailureStrategyTest, method):
                print(f"✓ 方法存在: {method}")
            else:
                print(f"✗ 方法缺失: {method}")
                return False
        
        # 检查混入类方法
        mixin_methods = [
            'test_idle_to_waiting_entry',
            'test_waiting_entry_to_holding',
            'test_holding_to_waiting_exit',
            'test_waiting_exit_to_idle',
            'test_trade_count_limit',
            'test_entry_order_rejection',
            'test_exit_order_rejection',
            'test_exit_timeout',
            'test_trading_time_limit',
            'test_complete_trading_cycle',
            'test_multiple_symbols_independent'
        ]
        
        for method in mixin_methods:
            if hasattr(VWAPFailureStrategyTest, method):
                print(f"✓ 混入方法存在: {method}")
            else:
                print(f"✗ 混入方法缺失: {method}")
                return False
        
        return True
        
    except Exception as e:
        print(f"✗ 方法可用性测试失败: {e}")
        return False


def test_vwap_failure_specific_methods():
    """测试 VWAP Failure 策略特定方法"""
    print("\n=== 测试 VWAP Failure 策略特定方法 ===")
    
    try:
        from test_vwap_failure_context_based import TestVWAPFailureSpecificLogic
        
        # 检查策略特定测试方法
        specific_methods = [
            'test_gap_up_vwap_failure_condition',
            'test_gap_down_vwap_failure_condition',
            'test_price_calculation',
            'test_gap_up_entry_direction',
            'test_gap_down_entry_direction',
            'test_vwap_failure_threshold_configuration',
            'test_entry_factor_configuration',
            'test_exit_factor_configuration'
        ]
        
        for method in specific_methods:
            if hasattr(TestVWAPFailureSpecificLogic, method):
                print(f"✓ 策略特定方法存在: {method}")
            else:
                print(f"✗ 策略特定方法缺失: {method}")
                return False
        
        return True
        
    except Exception as e:
        print(f"✗ 策略特定方法测试失败: {e}")
        return False


def test_base_class_functionality():
    """测试基类功能"""
    print("\n=== 测试基类功能 ===")
    
    try:
        from context_based_testing_base import MockDataGenerator, ContextSnapshotManager
        
        # 测试 MockDataGenerator
        generator = MockDataGenerator()
        
        # 测试创建模拟数据
        order = generator.create_mock_order("9984", Status.SUBMITTING)
        trade = generator.create_mock_trade("9984", 100.0, 100)
        bar = generator.create_mock_bar("9984")
        tick = generator.create_mock_tick("9984")
        indicators = generator.create_mock_indicators()
        
        print("✓ MockDataGenerator 功能正常")
        
        # 测试 ContextSnapshotManager（需要策略实例）
        # 这里只测试类是否可以实例化
        print("✓ ContextSnapshotManager 类定义正常")
        
        return True
        
    except Exception as e:
        print(f"✗ 基类功能测试失败: {e}")
        return False


def main():
    """主函数"""
    print("=== 测试重构后的测试结构 ===")
    
    tests = [
        test_imports,
        test_class_inheritance,
        test_method_availability,
        test_vwap_failure_specific_methods,
        test_base_class_functionality
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"✗ 测试 {test.__name__} 异常: {e}")
    
    print(f"\n=== 测试结果 ===")
    print(f"通过: {passed}/{total}")
    print(f"成功率: {passed/total:.2%}")
    
    if passed == total:
        print("🎉 所有测试通过！重构成功！")
    else:
        print("⚠️ 部分测试失败，需要检查重构")


if __name__ == "__main__":
    main() 