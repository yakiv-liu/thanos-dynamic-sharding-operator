import datetime
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)

class TimeShardCalculator:
    """计算动态时间分片的类"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.sharding_config = config.get('sharding', {})
        
    def calculate_shard_ranges(self) -> List[Dict]:
        """计算所有分片的时间范围"""
        total_shards = self.sharding_config.get('total_shards', 3)
        retention_days = self.sharding_config.get('data_retention_days', 370)
        overlap_days = self.sharding_config.get('shard_overlap_days', 1)
        future_hours = self.sharding_config.get('future_buffer_hours', 24)
        
        # 计算每个分片负责的天数（包含重叠）
        days_per_shard = retention_days // total_shards + overlap_days
        
        ranges = []
        now = datetime.datetime.utcnow()
        future_buffer = datetime.timedelta(hours=future_hours)
        
        # 计算分片0的特殊处理（包含未来时间）
        max_time = now + future_buffer
        
        for shard_index in range(total_shards):
            # 分片0的特殊处理
            if shard_index == 0:
                # 分片0: 负责最近的数据，max_time为未来时间
                shard_max_time = max_time
                shard_min_time = max_time - datetime.timedelta(days=days_per_shard)
            else:
                # 其他分片：逐步向后推移
                offset_end = (shard_index * (days_per_shard - overlap_days))
                offset_start = offset_end + days_per_shard
                
                shard_max_time = now - datetime.timedelta(days=offset_end)
                shard_min_time = now - datetime.timedelta(days=offset_start)
            
            ranges.append({
                'shard_index': shard_index,
                'min_time': shard_min_time.isoformat() + "Z",
                'max_time': shard_max_time.isoformat() + "Z",
                'min_time_timestamp': int(shard_min_time.timestamp()),
                'max_time_timestamp': int(shard_max_time.timestamp()),
                'days_covered': days_per_shard,
                'overlap_days': overlap_days
            })
        
        return ranges
    
    def get_shard_for_pod(self, pod_index: int, pod_ranges: List[Dict]) -> Dict:
        """根据Pod索引获取对应的分片配置"""
        total_shards = self.sharding_config.get('total_shards', 3)
        replicas_per_shard = self.sharding_config.get('replicas_per_shard', 2)
        
        shard_index = pod_index // replicas_per_shard
        
        if shard_index >= len(pod_ranges):
            # 如果Pod索引超出范围，返回最后一个分片
            shard_index = len(pod_ranges) - 1
        
        return pod_ranges[shard_index]
