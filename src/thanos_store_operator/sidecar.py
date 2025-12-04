import os
import yaml
import json
import time
import signal
import subprocess
import logging
from typing import Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

class ThanosSidecar:
    """运行在Thanos Store Gateway Pod中的Sidecar容器"""
    
    def __init__(self, config_path: str = "/etc/thanos-operator/config.yaml"):
        self.config_path = config_path
        self.thanos_config_path = "/etc/thanos/config.yaml"
        self.pod_name = os.getenv('POD_NAME', '')
        self.pod_index = self._extract_pod_index()
        
    def _extract_pod_index(self) -> int:
        """从Pod名称中提取索引"""
        try:
            # 假设Pod名称格式: thanos-store-gateway-0
            if '-' in self.pod_name:
                index_str = self.pod_name.split('-')[-1]
                return int(index_str)
        except (ValueError, IndexError):
            pass
        return 0
    
    def load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return {}
    
    def generate_thanos_config(self, shard_config: Dict) -> Dict:
        """生成Thanos配置"""
        base_config = {
            'type': 'STORE',
            'grpc_address': f'0.0.0.0:{shard_config.get("grpc_port", 10901)}',
            'http_address': f'0.0.0.0:{shard_config.get("http_port", 10902)}',
            'data_dir': '/data',
            'objstore_config': {
                'type': 'S3',
                'config': {
                    'bucket': 'thanos',
                    'endpoint': 'minio.monitoring.svc.cluster.local:9000',
                    'access_key': 'minioadmin',
                    'secret_key': 'minioadmin',
                    'insecure': True
                }
            },
            'index_cache': {
                'type': 'IN-MEMORY',
                'config': {
                    'max_size': '512MB'
                }
            },
            'store': {
                'grpc': {
                    'series_max_concurrency': 10,
                    'series_sample_limit': 0
                }
            },
            'min_time': shard_config['time_range']['min_time'],
            'max_time': shard_config['time_range']['max_time']
        }
        
        return base_config
    
    def update_thanos_config(self, new_config: Dict):
        """更新Thanos配置文件并发送重载信号"""
        # 写入新配置
        config_yaml = yaml.dump(new_config, default_flow_style=False)
        
        with open(self.thanos_config_path, 'w') as f:
            f.write(config_yaml)
        
        logger.info(f"Updated Thanos config for pod {self.pod_name}")
        
        # 发送重载信号给Thanos进程
        try:
            # 查找Thanos进程
            result = subprocess.run(['pgrep', 'thanos'], capture_output=True, text=True)
            if result.returncode == 0:
                pid = result.stdout.strip()
                if pid:
                    os.kill(int(pid), signal.SIGHUP)
                    logger.info(f"Sent SIGHUP to Thanos process {pid}")
        except Exception as e:
            logger.error(f"Failed to send reload signal: {e}")
    
    def watch_for_changes(self):
        """监听配置变化"""
        last_hash = None
        
        while True:
            try:
                # 检查配置是否变化
                if os.path.exists(self.config_path):
                    with open(self.config_path, 'rb') as f:
                        current_hash = hash(f.read())
                    
                    if last_hash is None or current_hash != last_hash:
                        logger.info(f"Config changed for pod {self.pod_name}")
                        config = self.load_config()
                        
                        # 获取Pod对应的分片配置
                        shard_config = config.get('pods', {}).get(self.pod_name)
                        if shard_config:
                            thanos_config = self.generate_thanos_config(shard_config)
                            self.update_thanos_config(thanos_config)
                        
                        last_hash = current_hash
            except Exception as e:
                logger.error(f"Error watching config: {e}")
            
            time.sleep(30)  # 每30秒检查一次
