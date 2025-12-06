# Thanos Store Gateway 动态时间分片 Operator

## 概述

这是一个用于解决 **Thanos Store Gateway 长期数据查询动态分片** 问题的 Kubernetes Operator。它能够自动为 Store Gateway 的 Pod 计算并滚动更新时间查询范围，无需手动干预或重启 Pod，实现真正的“动态时间分片”。

## 核心特性

*   **动态时间滚动**：基于当前时间自动计算各分片的时间窗口（`min-time` / `max-time`），实现全年数据查询的无缝覆盖。
*   **零重启热更新**：通过 Sidecar 向 Thanos 进程发送 `SIGHUP` 信号，触发配置热重载，避免服务中断。
*   **企业级高可用**：支持为每个时间分片配置多个副本，Operator 自动管理所有副本的配置。
*   **智能重叠设计**：分片间具有可配置的时间重叠，确保查询边界数据的完整性，规避时间同步误差。
*   **未来时间缓冲**：首个分片（Shard 0）的 `max-time` 设置为未来时间，减少因时间推移而产生的频繁配置更新。
*   **简洁架构**：采用标准的 “Operator + Sidecar” 模式，无侵入性，不引入额外的代理或路由层，保持 Thanos 原生架构。

## 架构与工作原理

```
                      [ Operator Pod ]
                            |
                            | 1. 监听 & 计算
                            v
                    [ ConfigMap 更新 ]
                            |
         -------------------|-------------------
         |                                      |
         | 2. 挂载                            | 2. 挂载
         v                                      v
[ Store Gateway Pod-0 ]            [ Store Gateway Pod-N ]
    |- thanos (主容器)                 |- thanos (主容器)
    |- config-sidecar (边车) <------> |- config-sidecar (边车)
         |                                      |
         | 3. 监听变化 & 生成新配置             |
         | 4. 发送 SIGHUP 热重载               |
         v                                      v
    配置生效，时间窗口更新                配置生效，时间窗口更新
```

1.  **Operator**：周期性（默认5分钟）计算所有 Pod 应有的时间分片范围，并将结果写入统一的 `ConfigMap`。
2.  **ConfigMap**：作为配置的唯一真相源，被所有 Store Gateway Pod 挂载。
3.  **Sidecar**：运行在每个 Store Gateway Pod 内，监听 `ConfigMap` 变化。一旦检测到属于本 Pod 的配置变更，则生成新的 `thanos` 配置文件并发送 `SIGHUP` 信号。
4.  **Thanos Store Gateway**：接收 `SIGHUP` 信号，重新加载配置文件，更新内存中的 `min-time`/`max-time`，完成动态更新。

## 快速开始

### 前提条件

*   Kubernetes 集群 (>=1.19)
*   `kubectl` 已配置
*   已存在 `monitoring` 命名空间
*   已部署 Thanos 对象存储（如 MinIO）及相关 Secret (`thanos-objstore-config`)

### 部署步骤

1.  **构建镜像**
    ```bash
    # 构建 Operator 镜像
    docker build -t harbor.local/thanos-store-operator:v1.0.0 .
    # 构建 Sidecar 镜像
    docker build -f sidecar/Dockerfile -t harbor.local/thanos-config-sidecar:v1.0.0 .
    docker push harbor.local/thanos-store-operator:v1.0.0
    docker push harbor.local/thanos-config-sidecar:v1.0.0
    ```

2.  **部署配置和 Operator**
    ```bash
    # 创建 Operator 配置文件
    kubectl create configmap thanos-operator-config -n monitoring --from-file=config/config.yaml
    # 部署 Operator RBAC 和 Deployment
    kubectl apply -f manifests/operator-rbac.yaml
    kubectl apply -f manifests/operator-deployment.yaml
    ```

3.  **部署动态分片的 Store Gateway**
    ```bash
    # 应用更新后的 StatefulSet 和 Service
    kubectl apply -f manifests/thanos-store-gateway.yaml
    kubectl apply -f manifests/thanos-store-gateway-svc.yaml
    ```

## 配置说明

主要配置位于 `config/config.yaml`：

```yaml
operator:
  update_interval: 300          # Operator 计算周期（秒）
  namespace: monitoring
  statefulset_name: thanos-store-gateway
  configmap_name: thanos-store-config

sharding:
  total_shards: 3               # 时间分片总数
  replicas_per_shard: 2         # 每个分片的副本数
  data_retention_days: 370      # 数据保留总天数（如 12 个月 + 缓冲）
  shard_overlap_days: 1         # 分片间重叠天数（保证查询连续性）
  future_buffer_hours: 24       # 分片0的未来时间缓冲（小时）
```

## 监控与运维

*   **Operator 指标**：Operator Pod 的 `/metrics` 端点提供协调次数、配置更新状态等指标。(还未实现)
*   **Sidecar 日志**：每个 Store Gateway Pod 中的 `config-sidecar` 容器会输出配置变更日志。
*   **验证配置**：检查 `thanos-store-config` ConfigMap 的内容，或通过 Thanos Query 的 `/stores` 端点查看各 Store Gateway 上报的时间范围标签。

## 高级特性

*   **优雅切换**：通过配置时间重叠，可在更新时实现查询的平滑过渡。
*   **未来缓冲**：分片0包含未来时间，最小化因实时时钟推移导致的配置更新频率。

## 许可证

[请选择您的许可证，例如 Apache 2.0]

这个README提供了从理解到部署的完整指南，您可以直接使用或根据实际情况调整。如果需要针对某个部分（如监控指标的具体定义）进行更详细的说明，我可以继续为您补充。
