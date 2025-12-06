import yaml
import os
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class ConfigManager:
    """配置文件管理器"""

    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config = {}

    def load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            with open(self.config_path, 'r') as f:
                self.config = yaml.safe_load(f)
            logger.info(f"Loaded config from {self.config_path}")

            # 基本验证
            if not self.config:
                raise ValueError(f"Config file is empty: {self.config_path}")

            if 'operator' not in self.config:
                raise ValueError(f"Missing 'operator' section in config: {self.config_path}")

        except FileNotFoundError:
            logger.error(f"Config file not found at {self.config_path}")
            raise  # 直接抛出异常
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            raise  # 直接抛出异常

        return self.config