import os
import yaml
import time
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class ThanosSidecar:
    """运行在Thanos Store Gateway Pod中的Sidecar容器"""

    def __init__(self, config_path: str = "/etc/thanos-operator/config.yaml"):
        self.config_path = config_path
        self.time_range_env_path = "/etc/thanos/time-range.env"
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

    def update_time_range_env(self, min_time: str, max_time: str):
        """更新时间范围环境变量文件"""
        try:
            env_content = f"MIN_TIME={min_time}\nMAX_TIME={max_time}\n"

            # 确保目录存在
            os.makedirs(os.path.dirname(self.time_range_env_path), exist_ok=True)

            with open(self.time_range_env_path, 'w') as f:
                f.write(env_content)

            logger.info(
                f"Updated time range env file for pod {self.pod_name}: min_time={min_time}, max_time={max_time}")

            # 发送信号给Thanos进程，让它重启
            self.restart_thanos()

        except Exception as e:
            logger.error(f"Failed to update time range env: {e}")

    def restart_thanos(self):
        """重启Thanos进程"""
        try:
            # 发送SIGTERM信号给Thanos进程，让它优雅退出
            # kubelet会自动重启容器
            import signal
            import subprocess

            result = subprocess.run(['pgrep', '-f', 'thanos store'], capture_output=True, text=True)
            if result.returncode == 0:
                pid = result.stdout.strip()
                if pid:
                    os.kill(int(pid), signal.SIGTERM)
                    logger.info(f"Sent SIGTERM to Thanos process {pid} to trigger restart")
            else:
                logger.warning("Thanos process not found")
        except Exception as e:
            logger.error(f"Failed to restart Thanos: {e}")

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
                                min_time = pod_config['min_time']
                                max_time = pod_config['max_time']
                            else:
                                logger.error(f"No time range found in config for pod {self.pod_name}")
                                continue

                            # 更新时间范围环境变量
                            self.update_time_range_env(min_time, max_time)

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