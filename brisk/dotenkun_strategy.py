"""
Dotenkun 日内交易策略
基于intraday_strategy_base实现，使用kabus gateway
"""
from datetime import datetime
from typing import Dict, Any

from vnpy.trader.constant import Direction, Offset, Status, OrderType, Exchange
from vnpy.trader.object import BarData

from intraday_strategy_base import IntradayStrategyBase, StrategyState
from dotenkun_indicators import DotenkunIndicator


class DotenkunStrategy(IntradayStrategyBase):
    """Dotenkun 日内交易策略"""
    
    def __init__(self, log_suffix=None):
        # 使用kabus gateway
        super().__init__(gateway_type="kabus", log_suffix=log_suffix)
        
        # 策略参数（后续可以添加）
        # 暂时留空，等策略逻辑确定后再添加
        
        # 自定义Bar Generator和技术指标配置
        self.bar_window = 5            # 使用5分钟K线
        self.indicator_size = 6       # ArrayManager的大小（用于未来扩展）
        self.hl_range_period = 5

        # 固定订阅的股票
        self.fixed_symbol = "161030019"
        
    
    def _create_indicator_manager(self, symbol: str):
        """创建Dotenkun策略专用的技术指标管理器"""
        # 使用独立的DotenkunIndicator类，不依赖TechnicalIndicatorManager
        return DotenkunIndicator(symbol=symbol, size=self.indicator_size, hl_range_period=self.hl_range_period)
    
    def on_5min_bar(self, bar: BarData):
        """5分钟K线回调函数"""
        # 调用父类方法（记录日志等，父类已经调用了indicator.update_bar）
        super().on_5min_bar(bar)
        
        # 获取指标值（不需要再次调用update_bar，因为父类已经调用了）
        if bar.symbol in self.indicator_managers:
            indicator = self.indicator_managers[bar.symbol]
            indicators = indicator.get_indicators()  # 只获取指标值，不更新
            
            # 记录指标值
            hl_range_ma = indicators.get('hl_range_ma_5', 0.0)
            hl_range_count = indicators.get('hl_range_count', 0)
            
            self.write_log(f"5分钟K线: {bar.symbol} HL Range MA(5) = {hl_range_ma:.2f} "
                          f"(数据点: {hl_range_count}/{self.hl_range_period})")
        
        # 策略逻辑（后续实现）
        # self._check_entry_signal(bar)
        # self._check_exit_signal(bar)
    
    # 子类必须实现的抽象方法
    def get_entry_direction(self, symbol: str) -> str:
        """获取指定股票的entry方向"""
        # 暂时返回'none'，等策略逻辑确定后再实现
        return 'none'
    
    def _calculate_entry_price(self, context, bar, indicators) -> float:
        """计算 entry 价格"""
        # 暂时返回0，等策略逻辑确定后再实现
        return 0.0
    
    def _calculate_exit_price(self, context, bar, indicators) -> float:
        """计算 exit 价格"""
        # 暂时返回0，等策略逻辑确定后再实现
        return 0.0


def main():
    """主函数"""
    import time
    
    print("启动Dotenkun策略...")
    
    # 创建策略实例
    strategy = DotenkunStrategy()
    
    try:
        # 配置replay模式（如果需要使用replay，取消下面的注释并设置正确的路径和日期）
        use_replay = True  # 设置为True启用replay模式
        
        if use_replay:
            # Replay模式配置
            replay_setting = {
                "tick_mode": "replay",
                "replay_data_dir": r"D:\\dev\\github\\brisk-hack\\misc_data",  # 用户需要指定实际路径
                "replay_date": "2026-01-09",  # 用户需要指定实际日期（格式：YYYYMMDD）
                "replay_speed": 10.0,  # 回放速度倍数（1.0 = 实时，2.0 = 2倍速等）
            }
            
            # 连接Gateway（replay模式）
            strategy.connect(replay_setting)
            
            # 订阅固定股票
            strategy.subscribe([strategy.fixed_symbol])
            
            # 开始replay
            strategy.start_replay(replay_setting["replay_date"], [strategy.fixed_symbol])
            
            print("Replay模式已启动，按Ctrl+C退出...")
        else:
            # 实时模式
            strategy.connect()
            
            # 订阅固定股票
            strategy.subscribe([strategy.fixed_symbol])
            
            # 等待一段时间接收数据
            print("等待接收数据...")
            time.sleep(1)
            
            print("实时模式已启动，按Ctrl+C退出...")
        
        # 保持运行
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n收到退出信号...")
        if use_replay:
            strategy.stop_replay()
    except Exception as e:
        print(f"运行过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        strategy.close()


if __name__ == "__main__":
    main()
