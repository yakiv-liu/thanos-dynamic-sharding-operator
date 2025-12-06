import yaml
import json
import time
import logging
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from typing import Dict, List
from datetime import datetime

from .time_shard import TimeShardCalculator
from .config_manager import ConfigManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ThanosStoreOperator:
    """Thanos Store Gateway Operator"""

    def __init__(self, config_path: str = None):
        # 如果没有指定，使用默认路径
        if config_path is None:
            config_path = "/app/config/config.yaml"
        self.config_manager = ConfigManager(config_path)
        self.operator_config = self.config_manager.load_config()
        self.shard_calculator = TimeShardCalculator(self.operator_config)

        # 初始化Kubernetes客户端
        try:
            config.load_incluster_config()
        except:
            config.load_kube_config()

        self.core_v1 = client.CoreV1Api()
        self.apps_v1 = client.AppsV1Api()

    def reconcile_statefulset(self):
        """协调StatefulSet配置"""
        namespace = self.operator_config['operator']['namespace']
        statefulset_name = self.operator_config['operator']['statefulset_name']

        try:
            # 获取StatefulSet
            # sts = self.apps_v1.read_namespaced_stateful_set(
            #     name=statefulset_name,
            #     namespace=namespace
            # )

            # 获取所有Pod
            pods = self.core_v1.list_namespaced_pod(
                namespace=namespace,
                label_selector=f"app={statefulset_name}"
            )

            # 计算新的分片配置
            pod_configs = self._calculate_pod_configs(pods.items)

            # 更新ConfigMap
            self._update_configmap(pod_configs)

            # 如果需要，直接更新Pod的配置
            self._update_pod_configs(pods.items, pod_configs)

            logger.info(f"Reconciled {len(pod_configs)} pods")

        except ApiException as e:
            logger.error(f"Kubernetes API error: {e}")

    def _calculate_pod_configs(self, pods: List) -> Dict:
        """为每个Pod计算配置 - 只包含时间范围"""
        # 计算所有分片的时间范围
        shard_ranges = self.shard_calculator.calculate_shard_ranges()

        pod_configs = {}

        for pod in pods:
            pod_name = pod.metadata.name
            pod_index = self._extract_pod_index(pod_name)

            # 获取Pod对应的分片
            shard_config = self.shard_calculator.get_shard_for_pod(pod_index, shard_ranges)

            # 只生成包含时间范围的配置
            pod_configs[pod_name] = {
                'pod_index': pod_index,
                'shard_index': shard_config['shard_index'],
                'time_range': {
                    'min_time': shard_config['min_time'],
                    'max_time': shard_config['max_time'],
                    'min_timestamp': shard_config['min_time_timestamp'],
                    'max_timestamp': shard_config['max_time_timestamp']
                }
            }

        return pod_configs

    def _extract_pod_index(self, pod_name: str) -> int:
        """从Pod名称提取索引"""
        try:
            parts = pod_name.split('-')
            return int(parts[-1])
        except (ValueError, IndexError):
            return 0

    def _update_configmap(self, pod_configs: Dict):
        """更新ConfigMap - 包含完整配置信息供sidecar使用"""
        namespace = self.operator_config['operator']['namespace']
        configmap_name = self.operator_config['operator']['configmap_name']

        # 构建完整的配置信息，包括operator和分片配置
        config_data = {
            'operator': self.operator_config['operator'],
            'sharding': self.operator_config['sharding'],
            'thanos': self.operator_config['thanos'],
            'pods': pod_configs,
            'last_updated': datetime.utcnow().isoformat() + "Z"
        }

        configmap_data = {
            'config.yaml': yaml.dump(config_data, default_flow_style=False),
            'config.json': json.dumps(config_data, indent=2)
        }

        try:
            # 尝试更新现有ConfigMap
            cm = self.core_v1.read_namespaced_config_map(
                name=configmap_name,
                namespace=namespace
            )
            cm.data = configmap_data
            self.core_v1.replace_namespaced_config_map(
                name=configmap_name,
                namespace=namespace,
                body=cm
            )
        except ApiException:
            # 创建新的ConfigMap
            cm = client.V1ConfigMap(
                metadata=client.V1ObjectMeta(
                    name=configmap_name,
                    namespace=namespace
                ),
                data=configmap_data
            )
            self.core_v1.create_namespaced_config_map(
                namespace=namespace,
                body=cm
            )

    def _update_pod_configs(self, pods: List, pod_configs: Dict):
        """更新Pod的配置文件 - 只包含时间范围"""
        for pod in pods:
            pod_name = pod.metadata.name
            if pod_name in pod_configs:
                pod_config = pod_configs[pod_name]

                # 生成只包含时间范围的配置文件
                time_range_config = {
                    'min_time': pod_config['time_range']['min_time'],
                    'max_time': pod_config['time_range']['max_time']
                }

                # 这里可以添加逻辑来直接更新Pod的配置文件
                # 例如，通过k8s API在Pod中创建或更新配置文件
                # 或者依赖sidecar容器来更新配置文件
                logger.debug(f"Pod {pod_name} time range: {time_range_config}")

    def run(self):
        """运行Operator主循环"""
        update_interval = self.operator_config['operator'].get('update_interval', 300)

        logger.info("Starting Thanos Store Operator")

        while True:
            try:
                self.reconcile_statefulset()
                time.sleep(update_interval)
            except KeyboardInterrupt:
                logger.info("Shutting down operator")
                break
            except Exception as e:
                logger.error(f"Error in operator loop: {e}")
                time.sleep(60)


def main():
    """Operator主入口点"""
    import os
    config_path = os.environ.get('OPERATOR_CONFIG_PATH', '/app/config/config.yaml')

    operator = ThanosStoreOperator(config_path=config_path)
    operator.run()


if __name__ == "__main__":
    main()