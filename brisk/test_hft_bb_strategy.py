"""
测试HFT BB Reversal策略的基本功能
"""

import time
from hft_bb_reversal_strategy import HFTBBReversalStrategy


def test_strategy_initialization():
    """测试策略初始化"""
    print("=== 测试策略初始化 ===")
    
    try:
        strategy = HFTBBReversalStrategy(use_mock_gateway=True)
        print("✓ 策略创建成功")
        
        # 测试技术指标管理器创建
        indicator_manager = strategy._create_indicator_manager("9984")
        print("✓ 技术指标管理器创建成功")
        
        # 测试BarGenerator创建
        bar_generator = strategy._create_bar_generator("9984")
        print("✓ BarGenerator创建成功")
        
        return strategy
        
    except Exception as e:
        print(f"✗ 策略初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_technical_indicators():
    """测试技术指标计算"""
    print("\n=== 测试技术指标计算 ===")
    
    try:
        from hft_bb_indicators import HFTBBReversalIndicatorV2 as HFTBBReversalIndicator
        from vnpy.trader.object import BarData
        from vnpy.trader.constant import Exchange, Interval
        from datetime import datetime
        
        # 创建技术指标管理器
        indicator = HFTBBReversalIndicator("9984", size=25, bb_period=20)
        print("✓ 技术指标管理器创建成功")
        
        # 创建模拟的bar数据
        base_price = 1000.0
        for i in range(25):
            bar = BarData(
                symbol="9984",
                exchange=Exchange.TSE,
                datetime=datetime.now(),
                interval=Interval.MINUTE,
                volume=1000,
                turnover=1000000,
                open_price=base_price + i * 0.1,
                high_price=base_price + i * 0.1 + 0.5,
                low_price=base_price + i * 0.1 - 0.5,
                close_price=base_price + i * 0.1 + 0.2,
                gateway_name="TEST"
            )
            
            # 更新指标
            bb_levels = indicator.update_bar(bar)
            
            if i == 24:  # 最后一个bar
                print(f"✓ 技术指标计算完成")
                print(f"  SMA: {bb_levels.get('middle', 'N/A'):.2f}")
                print(f"  STD: {bb_levels.get('std', 'N/A'):.2f}")
                print(f"  Upper: {bb_levels.get('upper', 'N/A'):.2f}")
                print(f"  Lower: {bb_levels.get('lower', 'N/A'):.2f}")
                print(f"  Exit_Long: {bb_levels.get('exit_long', 'N/A'):.2f}")
                print(f"  Exit_Short: {bb_levels.get('exit_short', 'N/A'):.2f}")
        
        return True
        
    except Exception as e:
        print(f"✗ 技术指标测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_simulation_logic():
    """测试模拟持仓逻辑"""
    print("\n=== 测试模拟持仓逻辑 ===")
    
    try:
        strategy = HFTBBReversalStrategy(use_mock_gateway=True)
        
        # 模拟BB价格水平
        strategy.bb_levels["9984"] = {
            'upper': 1005.0,      # short entry
            'lower': 995.0,       # long entry
            'middle': 1000.0,     # BB中轴
            'exit_long': 999.5,   # long exit
            'exit_short': 1000.5, # short exit
            'std': 5.0
        }
        
        # 模拟tick数据
        from vnpy.trader.object import TickData
        from vnpy.trader.constant import Exchange
        from datetime import datetime
        
        # 测试long entry
        tick1 = TickData(
            symbol="9984",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            name="9984",
            volume=1000,
            turnover=1000000,
            open_interest=0,
            last_price=994.0,  # 低于lower，应该触发long entry
            last_volume=1000,
            limit_up=1100.0,
            limit_down=900.0,
            open_price=1000.0,
            high_price=1005.0,
            low_price=994.0,
            pre_close=1000.0,
            gateway_name="TEST"
        )
        
        strategy._update_simulated_positions(tick1)
        print(f"✓ Long Entry测试: {strategy.simulated_positions['9984']}")
        
        # 测试long exit
        tick2 = TickData(
            symbol="9984",
            exchange=Exchange.TSE,
            datetime=datetime.now(),
            name="9984",
            volume=1000,
            turnover=1000000,
            open_interest=0,
            last_price=1000.0,  # 高于exit_long，应该触发long exit
            last_volume=1000,
            limit_up=1100.0,
            limit_down=900.0,
            open_price=1000.0,
            high_price=1005.0,
            low_price=994.0,
            pre_close=1000.0,
            gateway_name="TEST"
        )
        
        strategy._update_simulated_positions(tick2)
        print(f"✓ Long Exit测试: {strategy.simulated_positions['9984']}")
        
        return True
        
    except Exception as e:
        print(f"✗ 模拟持仓逻辑测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("开始测试HFT BB Reversal策略...")
    
    # 测试1: 策略初始化
    strategy = test_strategy_initialization()
    if not strategy:
        return
    
    # 测试2: 技术指标计算
    if not test_technical_indicators():
        return
    
    # 测试3: 模拟持仓逻辑
    if not test_simulation_logic():
        return
    
    print("\n=== 所有测试通过！ ===")
    print("策略基本功能正常，可以开始运行。")


if __name__ == "__main__":
    main() 