import os
import yaml
import time
import signal
import subprocess
import logging
from typing import Dict, Any

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

    def load_current_thanos_config(self) -> Dict[str, Any]:
        """加载当前Thanos配置文件"""
        try:
            if os.path.exists(self.thanos_config_path):
                with open(self.thanos_config_path, 'r') as f:
                    return yaml.safe_load(f)
            else:
                # 如果配置文件不存在，创建默认配置
                logger.warning(f"Thanos config file not found at {self.thanos_config_path}, creating default")
                default_config = {
                    'min_time': '0000-01-01T00:00:00.000Z',
                    'max_time': '9999-12-31T23:59:59.999Z'
                }
                return default_config
        except Exception as e:
            logger.error(f"Failed to load Thanos config: {e}")
            return {'min_time': '0000-01-01T00:00:00.000Z', 'max_time': '9999-12-31T23:59:59.999Z'}

    def update_thanos_time_range(self, min_time: str, max_time: str):
        """只更新Thanos配置文件中的时间范围"""
        try:
            # 1. 加载当前的Thanos配置
            current_config = self.load_current_thanos_config()

            # 2. 只更新min_time和max_time字段，保持其他所有配置不变
            current_config['min_time'] = min_time
            current_config['max_time'] = max_time

            # 3. 写入更新后的配置
            config_yaml = yaml.dump(current_config, default_flow_style=False)

            with open(self.thanos_config_path, 'w') as f:
                f.write(config_yaml)

            logger.info(
                f"Updated time range in Thanos config for pod {self.pod_name}: min_time={min_time}, max_time={max_time}")

            # 4. 发送重载信号给Thanos进程
            self.send_reload_signal()

        except Exception as e:
            logger.error(f"Failed to update Thanos time range: {e}")

    def send_reload_signal(self):
        """发送SIGHUP信号给Thanos进程"""
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

        logger.info(f"Starting sidecar for pod: {self.pod_name}")

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
                        pods_config = config.get('pods', {})

                        # 查找当前pod的配置
                        pod_config = None
                        if self.pod_name in pods_config:
                            pod_config = pods_config[self.pod_name]
                        else:
                            # 通过pod索引查找
                            for pod_name, config_data in pods_config.items():
                                if config_data.get('pod_index') == self.pod_index:
                                    pod_config = config_data
                                    break

                        if pod_config:
                            # 获取时间范围
                            if 'time_range' in pod_config:
                                min_time = pod_config['time_range']['min_time']
                                max_time = pod_config['time_range']['max_time']
                            elif 'min_time' in pod_config and 'max_time' in pod_config:
                                # 兼容直接包含min_time/max_time的格式
                                min_time = pod_config['min_time']
                                max_time = pod_config['max_time']
                            else:
                                logger.error(f"No time range found in config for pod {self.pod_name}")
                                continue

                            # 只更新时间范围
                            self.update_thanos_time_range(min_time, max_time)

                        last_hash = current_hash
                else:
                    logger.warning(f"Config file not found: {self.config_path}")

            except Exception as e:
                logger.error(f"Error watching config: {e}")

            time.sleep(30)


if __name__ == "__main__":
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    sidecar = ThanosSidecar()
    print(f"Starting sidecar for pod: {sidecar.pod_name}")
    sidecar.watch_for_changes()