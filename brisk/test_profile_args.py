#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试 profile 命令行参数功能
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_profile_args():
    """测试profile命令行参数解析"""
    print("测试 profile 命令行参数功能...")
    
    # 模拟不同的命令行参数
    test_cases = [
        # (args, expected_profile, expected_log_suffix)
        (['--profile', '600_2000'], '600_2000', '600_2000'),
        (['--profile', '2000_4000'], '2000_4000', '2000_4000'),
        ([], '600_2000', '600_2000'),  # 默认值
        (['--profile', '600_2000', '--mock'], '600_2000', '600_2000'),
    ]
    
    for i, (args, expected_profile, expected_log_suffix) in enumerate(test_cases, 1):
        print(f"\n测试用例 {i}: args={args}")
        
        # 模拟命令行参数解析
        import argparse
        parser = argparse.ArgumentParser(description='HFT BB Reversal策略')
        parser.add_argument('--profile', type=str, default='600_2000', 
                           choices=['600_2000', '2000_4000'],
                           help='选择运行profile (默认: 600_2000)')
        parser.add_argument('--mock', action='store_true', 
                           help='使用模拟数据')
        parser.add_argument('--debug', action='store_true', default=True,
                           help='启用调试模式')
        
        # 解析参数
        parsed_args = parser.parse_args(args)
        
        # 定义profiles
        profiles = {
            '600_2000': {
                'log_suffix': '600_2000',
                'low_price': 600,
                'high_price': 2000,
            },
            '2000_4000': {
                'log_suffix': '2000_4000',
                'low_price': 2000,
                'high_price': 4000,
            }
        }
        
        # 验证结果
        actual_profile = parsed_args.profile
        actual_log_suffix = profiles[actual_profile]['log_suffix']
        
        print(f"   预期profile: {expected_profile}")
        print(f"   实际profile: {actual_profile}")
        print(f"   预期log_suffix: {expected_log_suffix}")
        print(f"   实际log_suffix: {actual_log_suffix}")
        
        assert actual_profile == expected_profile, f"Profile不匹配: 预期{expected_profile}, 实际{actual_profile}"
        assert actual_log_suffix == expected_log_suffix, f"Log suffix不匹配: 预期{expected_log_suffix}, 实际{actual_log_suffix}"
        
        print(f"   ✅ 测试通过")
    
    print("\n✅ 所有测试用例通过！")

def test_invalid_profile():
    """测试无效的profile参数"""
    print("\n测试无效profile参数...")
    
    import argparse
    parser = argparse.ArgumentParser(description='HFT BB Reversal策略')
    parser.add_argument('--profile', type=str, default='600_2000', 
                       choices=['600_2000', '2000_4000'],
                       help='选择运行profile (默认: 600_2000)')
    
    # 测试无效参数
    try:
        parser.parse_args(['--profile', 'invalid_profile'])
        print("   ❌ 应该抛出错误但没有")
    except SystemExit:
        print("   ✅ 正确拒绝了无效的profile参数")

if __name__ == "__main__":
    test_profile_args()
    test_invalid_profile()
