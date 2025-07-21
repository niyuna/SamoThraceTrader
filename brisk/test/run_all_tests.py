#!/usr/bin/env python3
"""
测试运行脚本
运行所有测试文件
"""

import sys
import os
import subprocess
from pathlib import Path

def run_test_file(test_file):
    """运行单个测试文件"""
    print(f"\n{'='*60}")
    print(f"运行测试: {test_file}")
    print(f"{'='*60}")
    
    try:
        # 切换到brisk目录运行测试
        result = subprocess.run([
            sys.executable, test_file
        ], cwd=Path(__file__).parent.parent, capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            print(f"✅ {test_file} 运行成功")
            if result.stdout:
                print("输出:")
                print(result.stdout)
        else:
            print(f"❌ {test_file} 运行失败")
            if result.stderr:
                print("错误:")
                print(result.stderr)
            if result.stdout:
                print("输出:")
                print(result.stdout)
                
    except subprocess.TimeoutExpired:
        print(f"⏰ {test_file} 运行超时")
    except Exception as e:
        print(f"💥 {test_file} 运行异常: {e}")

def main():
    """主函数"""
    print("🚀 开始运行所有测试...")
    
    # 获取所有测试文件
    test_dir = Path(__file__).parent
    test_files = [
        "test_mock_gateway.py",
        "test_vwap_failure_step1.py",
        "test_vwap_failure_mock.py",
        "test_timestamp_fix.py",
        "test_simplified_replay.py",
        "test_refactored_architecture.py",
        "test_subscription_filter.py",
        "test_technical_indicators.py",
        "test_enhanced_bargenerator.py",
        "test_brisk_gateway_volume.py",
        "test_bargenerator_unified.py",
        "test_tick_data.py"
    ]
    
    # 运行每个测试文件
    for test_file in test_files:
        test_path = test_dir / test_file
        if test_path.exists():
            run_test_file(str(test_path))
        else:
            print(f"⚠️  测试文件不存在: {test_file}")
    
    print(f"\n{'='*60}")
    print("🎉 所有测试运行完成！")
    print(f"{'='*60}")

if __name__ == "__main__":
    main() 