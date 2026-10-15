"""全局日志对象（配置来自 config.yml -> logging / paths）。"""
import os
import sys

from loguru import logger

from utils.config import CONFIG, ensure_dir

# 日志目录（不存在则创建）
log_dir = ensure_dir(CONFIG.path("paths.log_dir"))

# Trace < Debug < Info < Success < Warning < Error < Critical
_CONSOLE_FORMAT = (
    "<green>{time:YYYYMMDD HH:mm:ss}</green> | "  # 时间
    "{process.name} | "  # 进程名
    "{thread.name} | "  # 线程名
    "<cyan>{module}</cyan>.<cyan>{function}</cyan>"  # 模块名.方法名
    ":<cyan>{line}</cyan> | "  # 行号
    "<level>{level}</level>: "  # 等级
    "<level>{message}</level>"  # 日志内容
)

_FILE_FORMAT = (
    "{time:YYYYMMDD HH:mm:ss} - {process.name} | {thread.name} | "
    "{module}.{function}:{line} - {level} - {message}"
)


class MyLogger:
    def __init__(self):
        self.logger = logger
        self.logger.remove()  # 清空 loguru 默认设置

        level = CONFIG.get("logging.level", "DEBUG")
        # 控制台输出
        self.logger.add(sys.stdout, level=level, format=_CONSOLE_FORMAT)

        # 可选：输出到文件
        if CONFIG.get("logging.to_file", False):
            log_file_path = os.path.join(log_dir, "app.log")
            self.logger.add(
                log_file_path,
                level=level,
                encoding="UTF-8",
                format=_FILE_FORMAT,
                rotation=CONFIG.get("logging.rotation", "10 MB"),
                retention=CONFIG.get("logging.retention", 20),
            )

    def get_logger(self):
        return self.logger


log = MyLogger().get_logger()
