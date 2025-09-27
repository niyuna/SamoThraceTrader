import sys
from datetime import datetime
from pathlib import Path
from logging import DEBUG, INFO, WARNING, ERROR, CRITICAL

from loguru import logger

from vnpy.trader.setting import SETTINGS
from vnpy.trader.utility import get_folder_path


__all__ = [
    "DEBUG",
    "INFO",
    "WARNING",
    "ERROR",
    "CRITICAL",
    "logger",
]


def setup_logger():
    # print(f"setup_logger: {SETTINGS}")
    # Log format
    if SETTINGS.get("log.format"):
        format: str = SETTINGS["log.format"]
    else:
        format: str = (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> "
            "| <blue>{extra[log_time]}</blue> "
            "| <level>{level}</level> "
            "| <cyan>{extra[gateway_name]}</cyan> "
            "| <level>{message}</level>"
        )


    # Add default gateway
    logger.configure(extra={"gateway_name": "Logger", "log_time": datetime.now(), "log_lag": -1.0})

    def add_lag(record):
        try:
            # t1: loguru 的记录时间（是 timezone-aware 的 datetime）
            t1 = record["time"]                     # datetime
            # t2: 你通过 bind 进去的业务时间，建议是 datetime 或 "HH:MM:SS(.fff/ffffff)"
            t2 = record["extra"].get("log_time")
            lag = (t1 - t2).total_seconds()
            record["extra"]["log_lag"] = lag
        except Exception:
            # 出错就保持默认值（或你可以写成 "-"）
            pass

    # logger.configure(patcher=add_lag)

    # Log level
    level: int = SETTINGS["log.level"]


    # Remove default stderr output
    logger.remove()


    # Add console output
    if SETTINGS["log.console"]:
        logger.add(sink=sys.stdout, level=level, format=format)


    # Add file output
    if SETTINGS["log.file"]:
        today_date: str = datetime.now().strftime("%Y%m%d")
        if SETTINGS["log.file_name"]:
            filename: str = f"vt_{SETTINGS['log.file_name']}_{today_date}.log"
        else:
            filename: str = f"vt_{today_date}.log"
        log_path: Path = get_folder_path("log")
        file_path: Path = log_path.joinpath(filename)

        logger.add(sink=file_path, level=level, format=format)
