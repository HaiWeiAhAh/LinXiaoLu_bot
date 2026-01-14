import configparser
import os
from typing import Any, Optional


class ConfigManager:
    """简单实用的配置管理类（基于ini文件）"""

    def __init__(self, config_file: str = "config.ini"):
        """
        初始化配置管理器
        :param config_file: 配置文件路径，默认项目根目录的config.ini
        """
        self.config = configparser.ConfigParser(interpolation=None)
        self.config_file = config_file

        # 检查配置文件是否存在，不存在则抛出明确异常
        if not os.path.exists(config_file):
            raise FileNotFoundError(f"配置文件 {config_file} 不存在，请检查路径！")

        # 读取配置文件（支持中文）
        self.config.read(config_file, encoding="utf-8")

    def get(self, section: str, key: str, default: Any = None) -> Any:
        """
        读取通用配置项（自动处理类型）
        :param section: 配置节（如database、logging）
        :param key: 配置键
        :param default: 配置缺失时的默认值
        :return: 配置值（自动转换为对应类型）
        """
        try:
            # 先尝试读取原始值
            value = self.config.get(section, key)

            # 自动类型转换（适配常见类型）
            # 布尔值
            if value.lower() in ["true", "false"]:
                return value.lower() == "true"
            # 整数
            try:
                return int(value)
            except ValueError:
                pass
            # 浮点数
            try:
                return float(value)
            except ValueError:
                pass
            # 字符串（默认）
            return value
        except (configparser.NoSectionError, configparser.NoOptionError):
            # 配置缺失时返回默认值
            if default is not None:
                return default
            raise KeyError(f"配置项 [{section}] {key} 不存在，且未设置默认值！")

    def get_section(self, section: str) -> dict:
        """
        读取整个配置节的所有配置项
        :param section: 配置节名称
        :return: 该节的所有配置项（键值对）
        """
        if section not in self.config.sections():
            raise KeyError(f"配置节 [{section}] 不存在！")
        # 转换为字典并自动处理类型
        section_dict = {}
        for key, value in self.config[section].items():
            section_dict[key] = self.get(section, key)
        return section_dict


# ------------------- 测试使用示例 -------------------
if __name__ == "__main__":
    # 初始化配置管理器
    try:
        cfg = ConfigManager("../config.ini")

        # 1. 读取单个配置项（带类型转换）
        db_host = cfg.get("database", "host")
        db_port = cfg.get("database", "port")  # 自动转为int
        app_debug = cfg.get("app", "debug")  # 自动转为bool
        api_timeout = cfg.get("app", "api_timeout")  # 自动转为int

        print(f"数据库地址: {db_host}:{db_port}")
        print(f"应用调试模式: {app_debug}")
        print(f"API超时时间: {api_timeout}秒")

        # 2. 读取配置项（带默认值，防止配置缺失）
        redis_port = cfg.get("database", "redis_port", default=6379)
        print(f"Redis端口（默认值）: {redis_port}")

        # 3. 读取整个配置节
        logging_config = cfg.get_section("logging")
        print("\n日志配置:")
        for key, value in logging_config.items():
            print(f"  {key}: {value} (类型: {type(value)})")

    except Exception as e:
        print(f"配置读取失败: {e}")