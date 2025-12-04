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
        except FileNotFoundError:
            logger.warning(f"Config file not found at {self.config_path}, using defaults")
            self.config = self._get_default_config()
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            self.config = self._get_default_config()
        
        return self.config
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            'operator': {
                'update_interval': 300,
                'namespace': 'monitoring',
                'statefulset_name': 'thanos-store-gateway',
                'configmap_name': 'thanos-store-config'
            },
            'sharding': {
                'total_shards': 3,
                'replicas_per_shard': 2,
                'data_retention_days': 370,
                'shard_overlap_days': 1,
                'future_buffer_hours': 24
            },
            'thanos': {
                'grpc_port': 10901,
                'http_port': 10902,
                'config_reload_signal': 'SIGHUP',
                'config_path': '/etc/thanos/config.yaml'
            }
        }
