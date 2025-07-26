"""
vnpy logging configuration for brisk strategies
为brisk策略模块配置vnpy的logging系统
"""

import os
from pathlib import Path
from vnpy.trader.setting import SETTINGS
from vnpy.trader.logger import DEBUG, INFO, WARNING, ERROR, CRITICAL


def setup_vnpy_logging(
    level=INFO,
    console=True,
    file=True,
    active=True,
    log_dir=None
):
    """
    配置vnpy的logging系统
    
    Args:
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        console: 是否在控制台输出
        file: 是否输出到文件
        active: 是否激活日志功能
        log_dir: 日志文件目录，如果为None则使用默认目录
    """
    # 设置日志级别
    SETTINGS["log.active"] = active
    SETTINGS["log.level"] = level
    SETTINGS["log.console"] = console
    SETTINGS["log.file"] = file
    
    # 如果指定了日志目录，创建目录
    if log_dir and file:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        print(f"日志文件将保存到: {log_path.absolute()}")
    
    print(f"vnpy logging配置完成:")
    print(f"  - 日志级别: {level}")
    print(f"  - 控制台输出: {console}")
    print(f"  - 文件输出: {file}")
    print(f"  - 日志激活: {active}")


def setup_development_logging():
    """开发环境配置 - 详细日志，适合调试"""
    setup_vnpy_logging(
        level=DEBUG,
        console=True,
        file=True,
        active=True,
        log_dir="./logs"
    )


def setup_production_logging():
    """生产环境配置 - 只记录重要信息"""
    setup_vnpy_logging(
        level=WARNING,
        console=False,
        file=True,
        active=True,
        log_dir="./logs"
    )


def setup_testing_logging():
    """测试环境配置 - 中等详细程度"""
    setup_vnpy_logging(
        level=INFO,
        console=True,
        file=True,
        active=True,
        log_dir="./logs"
    )


def setup_performance_logging():
    """性能敏感场景配置 - 最小日志输出"""
    setup_vnpy_logging(
        level=ERROR,
        console=False,
        file=True,
        active=True,
        log_dir="./logs"
    )


def setup_strategy_logging(strategy_name, level=INFO):
    """
    为特定策略配置logging
    
    Args:
        strategy_name: 策略名称
        level: 日志级别
    """
    # 创建策略专用的日志目录
    log_dir = f"./logs/{strategy_name}"
    
    setup_vnpy_logging(
        level=level,
        console=True,
        file=True,
        active=True,
        log_dir=log_dir
    )


def get_logging_configs():
    """获取所有可用的logging配置"""
    return {
        "development": setup_development_logging,
        "production": setup_production_logging,
        "testing": setup_testing_logging,
        "performance": setup_performance_logging
    }


# 使用示例
if __name__ == "__main__":
    # 根据环境变量选择配置
    env = os.getenv("BRISK_ENV", "development")
    
    configs = get_logging_configs()
    if env in configs:
        configs[env]()
        print(f"使用 {env} 环境的logging配置")
    else:
        setup_development_logging()
        print("使用默认开发环境配置") 