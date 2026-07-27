"""
日志工具 - 统一的日志记录
"""
import os
import logging
from datetime import datetime
from pathlib import Path


def setup_logger(name: str = "pipeline", log_dir: str = "data/logs") -> logging.Logger:
    """设置日志记录器"""
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    # 文件 handler - 按日期命名
    date_str = datetime.now().strftime("%Y%m%d")
    fh = logging.FileHandler(log_path / f"pipeline_{date_str}.log", encoding="utf-8")
    fh.setLevel(logging.DEBUG)

    # 控制台 handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)

    # 格式
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)-8s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger


def get_today_str() -> str:
    """获取今天的日期字符串"""
    return datetime.now().strftime("%Y-%m-%d")


def get_timestamp_str() -> str:
    """获取时间戳字符串"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
