#!/usr/bin/env python3
"""
运行CAB（Closing Auction Bet）策略所有测试的脚本
"""

import sys
import os
import subprocess
import time
from datetime import datetime

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

def run_cab_test(test_name, test_path, description=""):
    """运行单个CAB测试"""
    print(f"\n{'='*60}")
    print(f"🧪 运行CAB测试: {test_name}")
    if description:
        print(f"📝 描述: {description}")
    print(f"📁 路径: {test_path}")
    print(f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print('='*60)
    
    try:
        # 使用虚拟环境运行测试
        cmd = [sys.executable, test_path]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=project_root)
        
        if result.returncode == 0:
            print(f"✅ {test_name} - 测试通过")
            if result.stdout:
                print("📤 输出:")
                print(result.stdout)
        else:
            print(f"❌ {test_name} - 测试失败")
            if result.stderr:
                print("🚨 错误:")
                print(result.stderr)
            if result.stdout:
                print("📤 输出:")
                print(result.stdout)
        
        return result.returncode == 0
        
    except Exception as e:
        print(f"💥 {test_name} - 运行异常: {e}")
        return False

def main():
    """主函数"""
    print("🚀 开始运行CAB策略所有测试...")
    print(f"📅 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📂 项目根目录: {project_root}")
    
    # 定义CAB测试
    cab_tests = [
        {
            "name": "CAB主测试",
            "path": "test/cab/test_closing_auction_bet.py",
            "description": "收盘竞价策略核心功能测试"
        },
        {
            "name": "CAB动态参数测试",
            "path": "test/cab/test_dynamic_params.py",
            "description": "收盘竞价策略动态参数更新测试"
        },
        {
            "name": "CAB演示脚本",
            "path": "test/cab/demo_closing_auction_bet.py",
            "description": "收盘竞价策略演示和参数展示"
        }
    ]
    
    # 运行所有CAB测试
    results = []
    total_tests = len(cab_tests)
    passed_tests = 0
    
    for i, test in enumerate(cab_tests, 1):
        print(f"\n📊 进度: {i}/{total_tests}")
        success = run_cab_test(test["name"], test["path"], test["description"])
        results.append({
            "name": test["name"],
            "success": success,
            "path": test["path"]
        })
        
        if success:
            passed_tests += 1
        
        # 测试间暂停
        if i < total_tests:
            time.sleep(1)
    
    # 输出总结
    print(f"\n{'='*60}")
    print("📊 CAB测试总结")
    print('='*60)
    print(f"📅 完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📈 总测试数: {total_tests}")
    print(f"✅ 通过数量: {passed_tests}")
    print(f"❌ 失败数量: {total_tests - passed_tests}")
    print(f"📊 通过率: {(passed_tests/total_tests)*100:.1f}%")
    
    print(f"\n📋 详细结果:")
    for result in results:
        status = "✅ 通过" if result["success"] else "❌ 失败"
        print(f"  {status} - {result['name']}")
    
    # 返回总体结果
    all_passed = all(result["success"] for result in results)
    if all_passed:
        print(f"\n🎉 所有CAB测试都通过了！")
        return 0
    else:
        print(f"\n⚠️  有 {total_tests - passed_tests} 个CAB测试失败")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
