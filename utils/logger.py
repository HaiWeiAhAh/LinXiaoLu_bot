import logging
import os
from typing import Any, Optional, Dict, Union
from logging.handlers import RotatingFileHandler

# 导入你已有的配置管理类（读取config.ini）
from utils.config import ConfigManager  # 请根据实际路径调整


class LoggerManager:
    """
    适配ConfigManager风格的日志管理类（基于ini配置，支持异步场景）
    用法：实例化后传入子任务，通过get_logger()获取日志器打日志
    """
    # 类级缓存：避免重复创建相同名称的logger
    _logger_cache: Dict[str, logging.Logger] = {}

    def __init__(self, config_file: str = "config.ini"):
        """
        初始化日志管理器（读取config.ini中的[logging]配置节）
        :param config_file: 配置文件路径，和ConfigManager保持一致
        """
        # 复用ConfigManager读取日志配置，保证配置源统一
        self.config_manager = ConfigManager(config_file)
        self.config_file = config_file

        # 预加载日志配置，提前检查关键配置是否存在
        try:
            self.config_manager.get_section("logging")
        except KeyError as e:
            raise KeyError(f"配置文件中缺少[logging]配置节！{e}")

    def _get_log_level(self, level_str: str) -> int:
        """
        内部方法：将配置中的日志级别字符串转为logging常量（如"INFO"→logging.INFO）
        """
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL
        }
        level = level_map.get(level_str.upper())
        if not level:
            raise ValueError(f"无效的日志级别：{level_str}，可选值：{list(level_map.keys())}")
        return level

    def _create_formatter(self, fmt_key: str) -> logging.Formatter:
        """
        内部方法：创建日志格式器（从配置读取格式）
        """
        default_fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        default_datefmt = "%Y-%m-%d %H:%M:%S"

        fmt = self.config_manager.get("logging", fmt_key, default_fmt)
        datefmt = self.config_manager.get("logging", "date_format", default_datefmt)
        return logging.Formatter(fmt=fmt, datefmt=datefmt)

    def get_logger(self, logger_name: str = "default") -> logging.Logger:
        """
        核心方法：获取指定名称的logger实例（单例模式，避免重复初始化）
        :param logger_name: 日志器名称（如"adapter"、"bot"），便于区分不同模块日志
        :return: 配置好的logging.Logger实例
        """
        # 缓存命中：直接返回已创建的logger
        if logger_name in self._logger_cache:
            return self._logger_cache[logger_name]

        # 1. 创建logger实例并设置全局级别
        logger = logging.getLogger(logger_name)
        global_level = self._get_log_level(self.config_manager.get("logging", "level", "INFO"))
        logger.setLevel(global_level)

        # 避免重复添加处理器（异步场景下多次调用get_logger会重复加handler）
        if logger.handlers:
            logger.handlers.clear()

        # 2. 添加控制台处理器（默认开启）
        if self.config_manager.get("logging", "enable_console", True):
            console_handler = logging.StreamHandler()
            console_level = self._get_log_level(self.config_manager.get("logging", "console_level", "INFO"))
            console_handler.setLevel(console_level)
            console_handler.setFormatter(self._create_formatter("console_format"))
            logger.addHandler(console_handler)

        # 3. 添加文件处理器（默认开启，支持日志轮转）
        if self.config_manager.get("logging", "enable_file", True):
            # 读取文件日志配置
            log_file = self.config_manager.get("logging", "file_path", "logs/app.log")
            max_bytes = self.config_manager.get("logging", "max_bytes", 10 * 1024 * 1024)  # 10MB
            backup_count = self.config_manager.get("logging", "backup_count", 5)
            encoding = self.config_manager.get("logging", "file_encoding", "utf-8")

            # 确保日志目录存在
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)

            # 创建轮转文件处理器（异步场景安全）
            file_handler = RotatingFileHandler(
                filename=log_file,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding=encoding
            )
            file_level = self._get_log_level(self.config_manager.get("logging", "file_level", "DEBUG"))
            file_handler.setLevel(file_level)
            file_handler.setFormatter(self._create_formatter("file_format"))
            logger.addHandler(file_handler)

        # 禁用日志向上传播（避免root logger重复输出）
        logger.propagate = False

        # 存入缓存
        self._logger_cache[logger_name] = logger
        return logger

    # 便捷方法：快速获取默认logger（简化子任务调用）
    @property
    def logger(self) -> logging.Logger:
        """快捷属性：获取默认名称的logger"""
        return self.get_logger()

    def get_log_config(self) -> Dict[str, Any]:
        """
        读取[logging]配置节的所有配置（和ConfigManager的get_section对齐）
        """
        return self.config_manager.get_section("logging")