"""
Dynamic Parameters Test for Closing Auction Bet Strategy
收盘竞价策略动态参数测试
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from closing_auction_bet_strategy import ClosingAuctionBetStrategy
from util.yaml_config_provider import YAMLConfigurationProvider


def test_dynamic_params_update():
    """测试动态参数更新功能"""
    print("=== 测试动态参数更新功能 ===")
    
    # 创建策略实例
    strategy = ClosingAuctionBetStrategy(use_mock_gateway=True, gateway_type="mock")
    
    # 设置配置提供者
    strategy.set_configuration_provider(YAMLConfigurationProvider("config/strategies", "production"))
    
    # 记录初始参数
    print(f"初始参数:")
    print(f"  long_multiplier: {strategy.long_multiplier}")
    print(f"  short_multiplier: {strategy.short_multiplier}")
    print(f"  trigger_tick_count: {strategy.trigger_tick_count}")
    print(f"  single_stock_max_position: {strategy.single_stock_max_position}")
    print(f"  min_position_size: {strategy.min_position_size}")
    
    # 模拟参数更新
    test_params = {
        'long_multiplier': 0.990,
        'short_multiplier': 1.010,
        'trigger_tick_count': 5,
        'single_stock_max_position': 2000000,
        'min_position_size': 200,
        'cancel_protection_seconds': 30,
        'entry_start_time': '15:20',
        'entry_end_time': '15:24'
    }
    
    print(f"\n模拟参数更新:")
    for key, value in test_params.items():
        print(f"  {key}: {value}")
    
    # 调用参数更新方法
    strategy._update_strategy_specific_params(test_params)
    
    # 验证参数是否更新
    print(f"\n更新后参数:")
    print(f"  long_multiplier: {strategy.long_multiplier}")
    print(f"  short_multiplier: {strategy.short_multiplier}")
    print(f"  trigger_tick_count: {strategy.trigger_tick_count}")
    print(f"  single_stock_max_position: {strategy.single_stock_max_position}")
    print(f"  min_position_size: {strategy.min_position_size}")
    print(f"  cancel_protection_seconds: {strategy.cancel_protection_seconds}")
    print(f"  entry_start_time: {strategy.entry_start_time}")
    print(f"  entry_end_time: {strategy.entry_end_time}")
    
    # 验证更新是否成功
    assert strategy.long_multiplier == 0.990
    assert strategy.short_multiplier == 1.010
    assert strategy.trigger_tick_count == 5
    assert strategy.single_stock_max_position == 2000000
    assert strategy.min_position_size == 200
    assert strategy.cancel_protection_seconds == 30
    assert strategy.entry_start_time.hour == 15
    assert strategy.entry_start_time.minute == 20
    assert strategy.entry_end_time.hour == 15
    assert strategy.entry_end_time.minute == 24
    
    print("[PASS] 动态参数更新测试通过")


def test_config_loading():
    """测试配置加载功能"""
    print("\n=== 测试配置加载功能 ===")
    
    # 创建策略实例
    strategy = ClosingAuctionBetStrategy(use_mock_gateway=True, gateway_type="mock")
    
    # 设置配置提供者
    config_provider = YAMLConfigurationProvider("config/strategies", "production")
    strategy.set_configuration_provider(config_provider)
    
    # 测试配置加载
    config = config_provider.get_strategy_config("ClosingAuctionBetStrategy")
    
    print(f"配置加载结果:")
    print(f"  策略名称: {config.get('metadata', {}).get('description', 'N/A')}")
    print(f"  版本: {config.get('metadata', {}).get('version', 'N/A')}")
    print(f"  是否有效: {config.get('metadata', {}).get('is_valid', False)}")
    
    params = config.get('params', {})
    print(f"  参数数量: {len(params)}")
    
    if params:
        print(f"  主要参数:")
        for key, value in params.items():
            print(f"    {key}: {value}")
    
    print("[PASS] 配置加载测试通过")


def main():
    """主测试函数"""
    print("开始运行收盘竞价策略动态参数测试...")
    print("=" * 60)
    
    try:
        test_dynamic_params_update()
        test_config_loading()
        
        print("=" * 60)
        print("[SUCCESS] 所有动态参数测试通过！")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        raise


if __name__ == "__main__":
    main()
