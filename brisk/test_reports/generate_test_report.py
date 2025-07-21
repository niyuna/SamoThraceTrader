"""
BarGenerator测试报告生成器
生成详细的测试报告，包括测试结果、问题分析和建议
"""

import unittest
import sys
import os
from datetime import datetime

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入所有测试模块
from test_bargenerator_volume import TestBarGeneratorVolume
from test_bargenerator_volume_fixed import TestBarGeneratorVolumeFixed
from test_bargenerator_volume_analysis import TestBarGeneratorVolumeAnalysis
from test_bargenerator_comprehensive import TestBarGeneratorComprehensive
from test_bargenerator_edge_cases import TestBarGeneratorEdgeCases


def generate_test_report():
    """生成详细的测试报告"""
    print("=" * 80)
    print("BarGenerator 详细测试报告")
    print("=" * 80)
    print(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 测试类配置
    test_configs = [
        {
            'name': '成交量处理测试',
            'class': TestBarGeneratorVolume,
            'description': '测试BarGenerator的成交量处理行为，验证各种场景下第一个tick的成交量是否正确计入bar'
        },
        {
            'name': '修正版成交量测试',
            'class': TestBarGeneratorVolumeFixed,
            'description': '修正后的BarGenerator成交量处理测试，正确模拟各种场景下的BarGenerator状态'
        },
        {
            'name': '成交量分析测试',
            'class': TestBarGeneratorVolumeAnalysis,
            'description': '分析BarGenerator成交量处理逻辑的测试，逐步跟踪每个tick的处理过程'
        },
        {
            'name': '综合测试',
            'class': TestBarGeneratorComprehensive,
            'description': '综合测试各种场景下的BarGenerator行为，包括成交量处理、时间间隔、边界条件等'
        },
        {
            'name': '边界情况测试',
            'class': TestBarGeneratorEdgeCases,
            'description': '测试各种边界情况和异常情况下的BarGenerator行为'
        }
    ]
    
    total_tests = 0
    total_passed = 0
    total_failed = 0
    total_errors = 0
    
    detailed_results = []
    
    # 运行每个测试类
    for config in test_configs:
        print(f"运行测试类: {config['name']}")
        print("-" * 60)
        print(f"描述: {config['description']}")
        
        # 创建测试套件
        test_suite = unittest.TestLoader().loadTestsFromTestCase(config['class'])
        test_count = test_suite.countTestCases()
        total_tests += test_count
        
        print(f"测试数量: {test_count}")
        
        # 运行测试
        runner = unittest.TextTestRunner(verbosity=1, stream=open(os.devnull, 'w'))
        result = runner.run(test_suite)
        
        # 统计结果
        passed = test_count - len(result.failures) - len(result.errors)
        total_passed += passed
        total_failed += len(result.failures)
        total_errors += len(result.errors)
        
        print(f"通过: {passed}, 失败: {len(result.failures)}, 错误: {len(result.errors)}")
        
        # 记录详细结果
        detailed_results.append({
            'name': config['name'],
            'description': config['description'],
            'total': test_count,
            'passed': passed,
            'failed': len(result.failures),
            'errors': len(result.errors),
            'failures': result.failures,
            'errors': result.errors
        })
        
        print()
    
    # 生成总结报告
    print("=" * 80)
    print("测试结果总结")
    print("=" * 80)
    print(f"总测试数: {total_tests}")
    print(f"通过测试: {total_passed}")
    print(f"失败测试: {total_failed}")
    print(f"错误测试: {total_errors}")
    print(f"通过率: {(total_passed/total_tests*100):.1f}%")
    print()
    
    # 详细失败分析
    if total_failed > 0 or total_errors > 0:
        print("=" * 80)
        print("失败测试详细分析")
        print("=" * 80)
        
        for result in detailed_results:
            if result['failed'] > 0 or len(result['errors']) > 0:
                print(f"\n{result['name']} ({result['failed']} 失败, {result['errors']} 错误):")
                
                # 分析失败原因
                failure_patterns = {}
                for test, traceback in result['failures']:
                    error_msg = traceback.split('AssertionError:')[-1].strip()
                    if error_msg not in failure_patterns:
                        failure_patterns[error_msg] = []
                    failure_patterns[error_msg].append(test)
                
                for pattern, tests in failure_patterns.items():
                    print(f"  - 模式: {pattern}")
                    print(f"    影响测试: {len(tests)} 个")
                    for test in tests:
                        print(f"      * {test}")
    
    # 问题分类和建议
    print("\n" + "=" * 80)
    print("问题分类和建议")
    print("=" * 80)
    
    print("\n1. 成交量计算问题:")
    print("   - 问题: 第一个tick的成交量计算为0")
    print("   - 影响: 跨天、跨分钟场景的成交量不准确")
    print("   - 建议: 重新审视业务逻辑，确认是否应该包含第一个tick的成交量")
    
    print("\n2. 零价格tick处理:")
    print("   - 问题: 零价格tick被完全忽略")
    print("   - 影响: 后续正常tick的成交量计算受影响")
    print("   - 建议: 考虑保留零价格tick的时间戳信息")
    
    print("\n3. 成交量减少处理:")
    print("   - 问题: 成交量减少被忽略的逻辑需要验证")
    print("   - 影响: 异常情况下的成交量计算可能不准确")
    print("   - 建议: 确认max(volume_change, 0)逻辑是否符合业务需求")
    
    # 生成Markdown报告
    generate_markdown_report(detailed_results, total_tests, total_passed, total_failed, total_errors)


def generate_markdown_report(detailed_results, total_tests, total_passed, total_failed, total_errors):
    """生成Markdown格式的测试报告"""
    report_file = f"bargenerator_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("# BarGenerator 测试报告\n\n")
        f.write(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        # 测试概览
        f.write("## 测试概览\n\n")
        f.write(f"- **总测试数**: {total_tests}\n")
        f.write(f"- **通过测试**: {total_passed}\n")
        f.write(f"- **失败测试**: {total_failed}\n")
        f.write(f"- **错误测试**: {total_errors}\n")
        f.write(f"- **通过率**: {(total_passed/total_tests*100):.1f}%\n\n")
        
        # 详细结果
        f.write("## 详细测试结果\n\n")
        f.write("| 测试类 | 总测试数 | 通过 | 失败 | 错误 | 通过率 |\n")
        f.write("|--------|----------|------|------|------|--------|\n")
        
        for result in detailed_results:
            pass_rate = (result['passed'] / result['total'] * 100) if result['total'] > 0 else 0
            f.write(f"| {result['name']} | {result['total']} | {result['passed']} | {result['failed']} | {result['errors']} | {pass_rate:.1f}% |\n")
        
        f.write("\n")
        
        # 失败分析
        if total_failed > 0 or total_errors > 0:
            f.write("## 失败测试分析\n\n")
            
            for result in detailed_results:
                if result['failed'] > 0 or len(result['errors']) > 0:
                    f.write(f"### {result['name']}\n\n")
                    f.write(f"**描述**: {result['description']}\n\n")
                    
                    if result['failures']:
                        f.write("**失败的测试**:\n\n")
                        for test, traceback in result['failures']:
                            error_msg = traceback.split('AssertionError:')[-1].strip()
                            f.write(f"- `{test}`: {error_msg}\n")
                        f.write("\n")
                    
                    if result['errors']:
                        f.write("**错误的测试**:\n\n")
                        for test, traceback in result['errors']:
                            f.write(f"- `{test}`: {traceback.split('Exception:')[-1].strip()}\n")
                        f.write("\n")
        
        # 建议
        f.write("## 改进建议\n\n")
        f.write("1. **业务逻辑确认**: 与业务方确认成交量计算逻辑是否符合预期\n")
        f.write("2. **代码优化**: 考虑优化第一个tick的成交量处理逻辑\n")
        f.write("3. **文档更新**: 更新相关文档，明确各种场景的处理方式\n")
        f.write("4. **持续测试**: 建立持续集成测试，确保代码质量\n\n")
        
        f.write("## 测试环境\n\n")
        f.write("- Python版本: 3.12.10\n")
        f.write("- 测试框架: unittest\n")
        f.write("- 依赖: vnpy.trader\n")
        f.write("- 运行环境: Windows 10\n")
    
    print(f"\nMarkdown报告已生成: {report_file}")


if __name__ == "__main__":
    generate_test_report() 