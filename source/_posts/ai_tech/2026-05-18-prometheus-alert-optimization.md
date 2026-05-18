---
title: Prometheus告警规则优化指南：从"狼来了"到精准告警
categories:
  - ai_tech
tags:
  - 技术
  - 运维
  - Prometheus
  - 告警
  - 监控
cover: 'https://picsum.photos/seed/tech0518/1280/720'
coverWidth: 1280
coverHeight: 720
date: 2026-05-18 21:30:00
---

## 前言

作为一名运维工程师，我每天都要和各种各样的监控系统打交道。在所有监控系统中，Prometheus 无疑是最受欢迎的选择之一。它强大的查询语言（PromQL）和灵活的告警规则配置，让我能够精准地监控系统的各项指标。

然而，随着监控规模的扩大，告警问题也逐渐凸显出来：**告警太多了！**

- 真正需要处理的告警只有 10%
- 剩下的 90% 都是"噪音"——网络抖动、瞬间负载波动、健康检查超时等
- 这些"噪音"不仅浪费了运维人员的精力，还让大家对真正的告警产生了麻木

本文将分享我在 Prometheus 告警规则优化方面的实践经验，希望能帮助大家从"狼来了"的困境中解脱出来。

## 问题背景

### 故障描述

在实际工作中，我们遇到了以下告警问题：

1. **告警数量过多**：每天触发数百条告警，但真正需要处理的只有几十条
2. **告警重复**：同一个问题触发多条告警，比如某某服务器同时出现 CPU 高、内存高、磁盘满的情况，结果发了三条告警
3. **告警不准**：阈值设得太低，稍微有点波动就告警，但实际上服务是正常的
4. **告警不及时**：有些真正的故障反而没有被及时发现，因为告警太多了，被"淹没"了

### 环境信息

- **监控系统**：Prometheus + Alertmanager
- **监控对象**：多台服务器和容器集群
- **告警通道**：钉钉、企业微信
- **告警规则**：约 50 条规则

## 常见告警问题分析

### 问题一：阈值设置不合理

这是最常见的问题。很多告警规则的阈值是"拍脑袋"设置的，没有基于历史数据进行调整。

**问题现象**：
```yaml
# 原来的配置
- alert: HighCPU
  expr: node_cpu_usage > 0.6  # 60% 就告警
  labels:
    severity: warning
```

**实际情况**：服务器的 CPU 使用率平时就跑在 50-70% 之间，稍微有点负载波动就会触发告警。

**优化方法**：观察历史数据，找到"异常值"和"正常值"的分界线。

```yaml
# 优化后的配置
- alert: HighCPU
  expr: node_cpu_usage > 0.85  # 85% 才告警
  labels:
    severity: warning
```

### 问题二：缺少"for"参数

健康检查类的告警最容易出现这个问题。

**问题现象**：
```yaml
# 原来的配置
- alert: ServiceDown
  expr: up == 0
  labels:
    severity: critical
```

**实际情况**：网络稍微有点抖动，健康检查就会超时，触发告警。但实际上，下一次检查就正常了。

**优化方法**：给告警加上"for"参数，让它"持续多久才触发"。

```yaml
# 优化后的配置
- alert: ServiceDown
  expr: up == 0
  for: 3m  # 持续 3 分钟才触发
  labels:
    severity: critical
```

### 问题三：告警聚合没配好

当一个实例出现多个指标异常时，会触发多条告警，增加运维人员的处理负担。

**问题现象**：
- 某某服务器同时出现 CPU 高、内存高、磁盘满的情况
- 结果发了三条告警：HighCPU、HighMemory、DiskFull

**优化方法**：使用 Alertmanager 的分组（group）功能，将同类告警聚合在一起。

```yaml
# alertmanager.yml 配置
route:
  group_by: ['instance']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  receiver: 'dingtalk'
```

### 问题四：标签（labels）使用不当

标签是告警聚合和路由的基础。如果标签使用不当，会导致告警无法正确聚合和路由。

**问题现象**：
- 同一个服务的告警，不同实例使用了不同的标签
- 导致告警分散，无法聚合

**优化方法**：统一标签命名规范，确保同类告警使用相同的标签。

```yaml
# 好的实践
- alert: HighCPU
  expr: node_cpu_usage > 0.85
  labels:
    service: myapp  # 统一使用 service 标签
    severity: warning
  annotations:
    summary: "服务 {{ $labels.service }} 的 CPU 使用率过高"
```

## 实战：告警优化步骤

### 第一步：统计现有告警数据

首先，我们需要了解当前的告警情况。

```bash
# 查看 Alertmanager 的告警状态
curl -s 'http://localhost:9093/api/v1/alerts' | jq '.data'

# 查看 Prometheus 的告警规则
curl -s 'http://localhost:9090/api/v1/rules' | jq '.data.groups[].rules[] | select(.type=="alerting")'
```

### 第二步：分析告警触发原因

对于每一条告警，我们需要分析：
- 触发原因是什么？
- 是真正的故障还是误报？
- 如果是误报，原因是阈值不合理还是缺少 for 参数？

```promql
# 查看某个指标的历史数据
# 帮助确定合理的阈值
node_cpu_usage

# 查看某个服务的可用性历史
up{service="myapp"}
```

### 第三步：优化告警规则

根据分析结果，优化告警规则。

```yaml
# prometheus/rules/common.yml
groups:
- name: service_alerts
  rules:
  # 1. 服务存活告警：加上 for 参数
  - alert: ServiceDown
    expr: up == 0
    for: 3m
    labels:
      severity: critical
    annotations:
      summary: "服务 {{ $labels.job }} 实例 {{ $labels.instance }} 不可用"
      description: "服务已经停止运行超过 3 分钟"

  # 2. CPU 告警：提高阈值
  - alert: HighCPU
    expr: node_cpu_usage > 0.85
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "服务 {{ $labels.instance }} 的 CPU 使用率过高"
      description: "CPU 使用率：{{ $value | humanizePercentage }}"

  # 3. 内存告警：考虑趋势
  - alert: HighMemory
    expr: (node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes > 0.85
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "服务 {{ $labels.instance }} 的内存使用率过高"
      description: "内存使用率：{{ $value | humanizePercentage }}"

  # 4. 磁盘告警：区分系统盘和数据盘
  - alert: DiskSpaceWarning
    expr: node_filesystem_avail_bytes{mountpoint!~"/boot|/efi"} / node_filesystem_size_bytes{mountpoint!~"/boot|/efi"} < 0.15
    for: 10m
    labels:
      severity: warning
    annotations:
      summary: "服务 {{ $labels.instance }} 的磁盘空间不足"
      description: "挂载点 {{ $labels.mountpoint }} 可用空间：{{ $value | humanize }}"

  # 5. 服务响应超时：设置合理的超时时间
  - alert: HTTPRequestDurationHigh
    expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 5
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "服务 {{ $labels.job }} 的请求延迟过高"
      description: "P95 延迟：{{ $value | humanizeDuration }}"
```

### 第四步：配置 Alertmanager 聚合

```yaml
# alertmanager.yml
global:
  resolve_timeout: 5m

route:
  receiver: 'dingtalk'
  group_by: ['alertname', 'service']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  
  # 根据 severity 分配不同的接收者
  routes:
  - match:
      severity: critical
    receiver: 'dingtalk-critical'
    # critical 告警不等待，立即发送
    group_wait: 0s
    repeat_interval: 1h
  - match:
      severity: warning
    receiver: 'dingtalk-warning'

receivers:
- name: 'dingtalk'
  webhook_configs:
  - url: 'http://your-webhook-server/dingtalk'
    send_resolved: true

- name: 'dingtalk-critical'
  webhook_configs:
  - url: 'http://your-webhook-server/dingtalk-critical'
    send_resolved: true
```

### 第五步：持续监控和调整

告警优化不是一劳永逸的事情，需要持续进行。

```bash
# 定期检查告警触发情况
# 如果发现某条告警经常触发，可能需要调整阈值

# 查看告警触发历史
curl -s 'http://localhost:9090/api/v1/query?query=ALERTS{alertname="HighCPU"}' | jq '.data.result'

# 查看告警持续时间
curl -s 'http://localhost:9090/api/v1/query?query=ALERTS{alertname="HighCPU"}' | jq '.data.result[].value'
```

## 一键优化脚本

为了方便大家快速优化告警规则，我写了一个一键优化脚本：

```bash
#!/bin/bash
# prometheus_alert_optimizer.sh

PROMETHEUS_URL="http://localhost:9090"
RULES_FILE="/etc/prometheus/rules/optimized.yml"

echo "=== Prometheus 告警规则优化工具 ==="
echo ""

# 1. 导出当前告警规则
echo "1. 导出当前告警规则..."
curl -s "${PROMETHEUS_URL}/api/v1/rules" | jq -r '.data.groups[].rules[] | select(.type=="alerting") | .name' > /tmp/current_alerts.txt

# 2. 统计告警数量
echo "2. 当前告警规则数量：$(wc -l < /tmp/current_alerts.txt)"

# 3. 统计告警触发情况
echo "3. 过去 24 小时告警触发情况..."
curl -s "${PROMETHEUS_URL}/api/v1/query?query=count(ALERTS) by (alertname)" | jq -r '.data.result[] | "\(.metric.alertname): \(.value[1])"'

# 4. 检查缺少 for 参数的告警
echo "4. 检查缺少 for 参数的告警..."
curl -s "${PROMETHEUS_URL}/api/v1/rules" | jq -r '.data.groups[].rules[] | select(.type=="alerting" and .query != null) | select(.for == null or .for == "0m") | .name'

echo ""
echo "=== 优化建议 ==="
echo "1. 检查上述告警，添加合适的 for 参数"
echo "2. 根据历史数据调整阈值"
echo "3. 配置 Alertmanager 进行告警聚合"
echo ""

# 5. 生成优化后的规则模板
echo "5. 生成优化后的规则模板..."
cat > "${RULES_FILE}.template" << 'EOF'
groups:
- name: optimized_alerts
  rules:
  # 请根据实际情况修改阈值和 for 参数
  # 模板：
  # - alert: YourAlertName
  #   expr: your_query
  #   for: 5m  # 建议添加
  #   labels:
  #     severity: warning
  #   annotations:
  #     summary: "告警摘要"
  #     description: "告警详情"
EOF

echo "优化模板已保存到：${RULES_FILE}.template"
echo "请根据实际情况修改并加载到 Prometheus"
```

## 常见问题解答

**Q：告警阈值设多少才合理？**

A：这需要根据业务特点和历史数据来确定。一般来说：
- CPU：85-90%
- 内存：85-90%
- 磁盘：85%
- 响应延迟：P99 延迟的 2-3 倍

建议先观察一段时间（1-2 周），了解指标的正常波动范围，然后再设置阈值。

**Q：for 参数设多久才合适？**

A：这取决于你的业务对可用性的要求：
- 核心服务：1-3 分钟
- 非核心服务：5-10 分钟
- 批处理任务：30 分钟以上

**Q：告警太多了，怎么处理？**

A：可以从以下几个方面入手：
1. 提高阈值，减少误报
2. 添加 for 参数，过滤瞬间波动
3. 配置 Alertmanager 聚合，合并同类告警
4. 使用路由规则，对不同级别的告警使用不同的处理方式

**Q：如何避免"告警疲劳"？**

A：几个建议：
1. 区分告警级别（critical、warning、info）
2. 对不同级别的告警使用不同的通知方式（短信、邮件、钉钉）
3. 设置合理的重复间隔，避免同一告警重复发送
4. 定期回顾告警规则，删除无效的告警

**Q：Prometheus 和 Alertmanager 的版本不兼容怎么办？**

A：确保 Prometheus 和 Alertmanager 的版本兼容：
- Prometheus 2.x 配合 Alertmanager 0.x 或 1.x
- 如果遇到 API 不兼容问题，可以升级其中一个到对应版本

**Q：告警规则生效了但没有触发告警，怎么排查？**

A：排查步骤：
1. 检查 Prometheus 是否能正常采集到数据：`curl -s 'http://localhost:9090/api/v1/query?query=your_expr'`
2. 检查告警规则是否正确加载：`curl -s 'http://localhost:9090/api/v1/rules'`
3. 检查 Alertmanager 是否可达：`curl -s 'http://localhost:9093/api/v1/status'`
4. 查看 Prometheus 日志：`journalctl -u prometheus -n 100`

## 经验总结

1. **告警优化是一个持续的过程**：不要期望一次配置就能解决所有问题，需要持续监控和调整。

2. **基于数据设置阈值**：不要"拍脑袋"设置阈值，要基于历史数据来调整。

3. **合理使用 for 参数**：for 参数可以过滤掉很多"噪音"，但也要注意不要设得太长，以免错过真正的故障。

4. **配置告警聚合**：告警聚合可以大大减少告警数量，提高运维效率。

5. **区分告警级别**：不同的告警级别应该使用不同的处理方式，避免"一刀切"。

6. **定期回顾告警规则**：随着业务的变化，告警规则也需要不断调整。建议每月回顾一次告警规则，删除无效的告警，调整不合理的阈值。

## 延伸阅读

- [Prometheus 官方文档](https://prometheus.io/docs/alerting/latest/alertmanager/)
- [Alertmanager 配置指南](https://www.cncf.io/blog/2020/07/23/alertmanager-configuration-best-practices/)
- [PromQL 常用函数](https://prometheus.io/docs/prometheus/latest/querying/functions/)

## 结语

告警优化是运维工作中非常重要的一环。一个好的告警系统应该做到：
- 只在真正需要关注的时候才告警
- 告警信息清晰、易于理解
- 能够快速定位问题

希望本文的分享能够帮助大家告别"狼来了"的困扰，建立一个精准、高效的告警系统。

如果有问题，欢迎在评论区讨论。

---

*作者：小六，一个今天终于让告警系统安静下来的技术博主*
