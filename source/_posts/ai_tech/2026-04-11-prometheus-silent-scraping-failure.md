---
title: 记一次Prometheus监控"沉默失效"排查：targets显示up但数据停止更新
categories:
  - ai_tech
tags:
  - 技术
  - 运维
  - Prometheus
  - 监控
  - 问题排查
cover: 'https://picsum.photos/seed/tech0411/1280/720'
coverWidth: 1280
coverHeight: 720
date: 2026-04-11 21:30:00
---

# 记一次Prometheus监控"沉默失效"排查：targets显示up但数据停止更新

## 前言

Prometheus 是目前最流行的开源监控系统之一，凭借其强大的多维数据模型和灵活的查询语言，被广泛应用于云原生环境的监控场景。然而，在实际使用中，Prometheus 有一种"沉默的失效"模式——服务看起来完全正常，targets 页面显示 up，但实际上数据已经停止更新了。

今天我们就来详细复盘一次这样的故障排查过程，聊聊如何发现、排查和解决这类问题，以及如何设置合理的告警规则来预防类似情况再次发生。

## 问题背景

### 业务场景

我们的基础设施监控体系使用 Prometheus + Grafana 组合：

- Prometheus：负责从各个目标（node_exporter、MySQL Exporter、Blackbox Exporter 等）抓取指标数据
- Grafana：负责可视化展示 Prometheus 中的指标数据
- Alertmanager：负责在触发告警时发送通知

Prometheus 部署在某台内网服务器上，监控着 34 个 targets，包括：

- Linux 主机（通过 node_exporter）
- PVE 服务器
- macOS 主机
- Windows 主机
- 磁盘监控（通过 smartctl）

### 问题现象

- **故障时间**：持续约 48 小时（2026-04-09 14:23 至 2026-04-11 14:00）
- **Grafana 表现**：所有仪表盘图表右端变成平直线，没有新数据更新
- **Prometheus targets 页面**：显示所有 34 个 targets 状态为 up
- **Prometheus alerts 页面**：告警列表为空，无任何告警触发
- **实际影响**：监控数据中断 48 小时，运维人员完全不知情

### 环境信息

| 项目 | 值 |
|------|-----|
| Prometheus 版本 | 最新稳定版 |
| 部署方式 | systemd |
| 监控 targets 数量 | 34 |
| 问题持续时间 | 约 48 小时 |
| 告警发送方式 | Alertmanager + 钉钉 |

## 问题分析

### 初步观察：Grafana 无数据但 Prometheus 显示 up

当发现 Grafana 图表停止更新时，我们首先想到的是 Prometheus 本身出了问题。但当我们打开 Prometheus 的 targets 页面时，看到的却是这样一幅"和谐"的画面：

```
Target                          State      Labels
node_exporter/某内网主机A:9100   UP         job=node_exporter
node_exporter/某内网主机B:9100   UP         job=node_exporter
node_exporter/某内网主机C:9100   UP         job=node_exporter
...
```

所有 targets 状态都是 UP，没有任何告警。

这很奇怪。Grafana 拿不到数据，但 Prometheus 本身显示一切正常。

### 深入查看：lastScrape 时间戳暴露真相

我们打开 Prometheus 的 targets API 接口，查看更详细的信息：

```bash
curl -s "http://localhost:9090/api/v1/targets" | jq '.data.activeTargets[] | {job: .labels.job, health: .health, lastError: .lastError, lastScrape: .lastScrape}'
```

输出结果揭示了真相：

```json
{
  "job": "node_exporter",
  "health": "up",
  "lastError": "",
  "lastScrape": "2026-04-09T14:23:45.123Z"
}
```

注意到了吗？`health: "up"` 但 `lastScrape` 是 48 小时前的时间戳！

这说明：**Prometheus 依然认为目标可达（health = up），但实际上已经 48 小时没有成功抓取数据了。**

### 查看 Prometheus 日志：找到根因

我们检查了 Prometheus 的日志：

```bash
journalctl -u prometheus -n 200 | grep -E "error|warn|fail"
```

发现了以下关键错误信息：

```
level=warn ts=2026-04-09T14:23:45.123Z caller=scrape.go:1234 component=scrape_manager target=node_exporter msg="append failed" err="persistence queue is full"

level=error ts=2026-04-09T14:23:45.456Z caller=persistence.go:789 component=persistence msg="failed to flush chunks" err="no space left on device"
```

两个关键信息：

1. **"persistence queue is full"**：持久化队列满了，Prometheus 无法将抓取到的数据写入磁盘
2. **"no space left on device"**：磁盘空间不足

### 根因分析

经过排查，我们确定了这次"沉默失效"的完整链路：

1. **触发点**：Prometheus 数据目录所在磁盘空间不足（或 I/O 瓶颈）
2. **第一层影响**：Prometheus 无法将数据写入磁盘，内存中的数据队列积压
3. **第二层影响**：为了防止内存溢出，Prometheus 跳过后续的抓取周期（scrape cycle）
4. **第三层影响**：抓取任务静默失败，不产生错误（因为目标本身可达）
5. **表象**：health check 通过（网络可达），但 lastScrape 停滞
6. **最终结果**：Grafana 无新数据，但 Prometheus 界面依然显示 targets up

### 为什么默认告警没有触发？

Prometheus 默认的告警规则是这样的：

```yaml
- alert: PrometheusTargetMissing
  expr: up == 0
  for: 5m
  labels:
    severity: critical
  annotations:
    summary: "Prometheus target missing"
```

这条规则只会检测 `up == 0` 的情况，即目标完全不可达。但在这个故障场景中，目标依然是可达的（网络没问题），只是数据写入失败。

因此，这条默认规则根本无法检测到"数据停滞"这类"沉默的失效"问题。

## 排查过程详解

### 第一步：确认Grafana数据停止更新

这是最初的异常发现。打开 Grafana，选择任意一个仪表盘，发现图表右端是平直线，选择"最近 1 小时"时间范围后显示空白。

### 第二步：检查Prometheus状态

```bash
# 检查 Prometheus 服务状态
systemctl status prometheus

# 检查 Prometheus 进程
ps aux | grep prometheus | grep -v grep

# 检查 Prometheus 版本
prometheus --version
```

服务状态正常，进程在运行，版本是最新稳定版。

### 第三步：检查targets状态

```bash
# 通过 API 查看 targets
curl -s "http://localhost:9090/api/v1/targets" | jq

# 查看活跃 targets
curl -s "http://localhost:9090/api/v1/targets?state=active" | jq '.data.activeTargets | length'
```

结果：34 个 targets 全部 active，health 全部为 up。

### 第四步：检查lastScrape时间戳

```bash
# 检查所有 targets 的最后抓取时间
curl -s "http://localhost:9090/api/v1/targets" | jq -r '.data.activeTargets[] | "\(.labels.job) @ \(.lastScrape)"'

# 对比当前时间
date -u
```

发现：所有 targets 的 lastScrape 时间都是约 48 小时前。

### 第五步：检查Prometheus日志

```bash
# 查看最近的日志
journalctl -u prometheus -n 500 --since "48 hours ago" | grep -E "error|warn|fail" | tail -50

# 查看完整的错误上下文
journalctl -u prometheus -n 500 | grep -B5 -A5 "no space left"
```

发现了关键错误：`no space left on device`。

### 第六步：检查磁盘状态

```bash
# 查看磁盘使用情况
df -h

# 查看 Prometheus 数据目录
du -sh /var/lib/prometheus/

# 查看大数据文件
find /var/lib/prometheus/ -type f -exec ls -lh {} \; | sort -k5 -h | tail -20
```

发现：Prometheus 数据目录所在磁盘使用率达到 95%，剩余空间不足 1GB。

### 第七步：确认数据目录位置

```bash
# 查看 Prometheus 配置
cat /etc/prometheus/prometheus.yml | grep -A10 "storage"

# 或者查看 systemd 启动参数
systemctl cat prometheus | grep -i storage
```

## 解决方案

### 紧急修复：清理磁盘空间

**第一步：备份重要数据**

```bash
# 备份最近的监控数据
tar -czf /tmp/prometheus_backup_$(date +%Y%m%d).tar.gz /var/lib/prometheus/

# 或者只备份规则和配置
tar -czf /tmp/prometheus_config_backup.tar.gz /etc/prometheus/
```

**第二步：清理旧数据**

```bash
# 查看数据文件的时间分布
find /var/lib/prometheus/ -type f -name "*.db" -exec ls -lh {} \; | head -20

# 清理 7 天前的数据块（Chunks）
find /var/lib/prometheus/ -type f -mtime +7 -delete

# 或者清理超过 30 天的数据
find /var/lib/prometheus/ -type f -mtime +30 -delete
```

**第三步：检查磁盘空间**

```bash
df -h /var/lib/prometheus/
```

确保有足够的剩余空间（建议至少 10GB）。

**第四步：重启 Prometheus**

```bash
systemctl restart prometheus
```

**第五步：验证修复**

等待 1-2 分钟后：

```bash
# 检查 targets 的 lastScrape 是否更新
curl -s "http://localhost:9090/api/v1/targets" | jq -r '.data.activeTargets[0].lastScrape'

# 检查 Grafana 是否有新数据
# 打开 Grafana，选择"最近 5 分钟"，确认图表在流动
```

### 长期优化：防止磁盘空间问题

**方案一：配置 Prometheus 存储容量限制**

```yaml
# prometheus.yml
storage:
  tsdb:
    path: /var/lib/prometheus
    retention.time: 15d    # 保留 15 天数据
    retention.size: 10GB  # 最多保留 10GB 数据
```

**方案二：配置 Prometheus 告警**

添加磁盘空间告警：

```yaml
# prometheus_rules.yml
- alert: PrometheusDiskSpaceLow
  expr: (node_filesystem_avail_bytes{mountpoint="/var/lib/prometheus"} / node_filesystem_size_bytes{mountpoint="/var/lib/prometheus"}) < 0.1
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "Prometheus 数据目录所在磁盘空间不足"
    description: "磁盘剩余空间低于 10%，当前剩余 {{ $value | humanizePercentage }}"
```

**方案三：使用 LVM 或独立磁盘**

将 Prometheus 数据目录放在独立磁盘或 LVM 逻辑卷上，避免与其他服务竞争磁盘 I/O 和空间。

## 一键排查脚本

如果你的 Prometheus 也遇到了类似问题，可以使用以下脚本进行快速排查：

```bash
#!/bin/bash

echo "=== Prometheus 数据停滞问题排查脚本 ==="
echo ""

# 1. 检查 Prometheus 进程
echo "[1/7] 检查 Prometheus 进程..."
if pgrep -x prometheus > /dev/null; then
    echo "✅ Prometheus 进程运行中"
    ps aux | grep prometheus | grep -v grep | awk '{print "   PID: "$2" 运行时长: " $10}'
else
    echo "❌ Prometheus 进程未运行"
    exit 1
fi

# 2. 检查 targets 状态
echo ""
echo "[2/7] 检查 targets 状态..."
TARGETS=$(curl -s "http://localhost:9090/api/v1/targets" | jq '.data.activeTargets | length')
echo "   总 targets 数: $TARGETS"

UP_COUNT=$(curl -s "http://localhost:9090/api/v1/targets" | jq '[.data.activeTargets[] | select(.health == "up")] | length')
echo "   健康 targets: $UP_COUNT"

# 3. 检查 lastScrape 时间
echo ""
echo "[3/7] 检查最后抓取时间..."
LAST_SCRAPE=$(curl -s "http://localhost:9090/api/v1/targets" | jq -r '.data.activeTargets[0].lastScrape')
echo "   最近一次抓取: $LAST_SCRAPE"

NOW=$(date -u +"%Y-%m-%dT%H:%M:%S")
echo "   当前时间: $NOW"

SCRAPE_AGE=$(($(date -d "$NOW" +%s) - $(date -d "$LAST_SCRAPE" +%s)))
echo "   距最后抓取: $((SCRAPE_AGE/60)) 分钟"

if [ $SCRAPE_AGE -gt 300 ]; then
    echo "⚠️  警告: 最后抓取时间超过 5 分钟"
fi

# 4. 检查磁盘空间
echo ""
echo "[4/7] 检查磁盘空间..."
df -h /var/lib/prometheus 2>/dev/null || df -h / | grep -v "tmpfs\|devtmpfs\|loop"

# 5. 检查 Prometheus 日志
echo ""
echo "[5/7] 检查 Prometheus 错误日志..."
ERROR_COUNT=$(journalctl -u prometheus --since "1 hour ago" 2>/dev/null | grep -ciE "error|warn|fail")
echo "   最近 1 小时错误/警告数: $ERROR_COUNT"

if [ $ERROR_COUNT -gt 0 ]; then
    echo "   最近几条错误:"
    journalctl -u prometheus --since "1 hour ago" 2>/dev/null | grep -iE "error|warn|fail" | tail -5 | sed 's/^/   /'
fi

# 6. 检查 Prometheus 内存使用
echo ""
echo "[6/7] 检查 Prometheus 内存使用..."
MEM=$(ps aux | grep prometheus | grep -v grep | awk '{print $6}')
echo "   内存使用: $(echo "scale=2; $MEM/1024" | bc) MB"

# 7. 检查 Prometheus 配置的保留策略
echo ""
echo "[7/7] 检查数据保留策略..."
grep -E "retention" /etc/prometheus/prometheus.yml 2>/dev/null || echo "   未配置 retention（使用默认 15 天）"

echo ""
echo "=== 排查完成 ==="
echo ""
echo "如果发现数据停滞，请检查："
echo "1. 磁盘空间是否不足"
echo "2. Prometheus 日志是否有写入错误"
echo "3. 数据目录权限是否正确"
echo "4. Prometheus 配置的 retention 是否合理"
```

## 新增告警规则：检测数据停滞

除了紧急修复，我们还需要添加专门检测"数据停滞"的告警规则：

```yaml
# 文件：/etc/prometheus/rules/scrape_stalled.yml

groups:
  - name: prometheus_scrape_health
    interval: 30s
    rules:
      # 规则1：检测 targets 整体停滞
      - alert: PrometheusScrapeStalled
        expr: |
          (time() - prometheus_target_last_scrape_timestamp_seconds) > (prometheus_target_scrape_interval_seconds * 2)
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Prometheus 抓取停滞"
          description: "Job {{ $labels.job }} (instance: {{ $labels.instance }}) 已经超过 2 倍抓取间隔未更新数据"

      # 规则2：检测特定目标停滞
      - alert: PrometheusTargetStalled
        expr: |
          (time() - prometheus_target_last_scrape_timestamp_seconds) > 300
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Prometheus 目标数据停滞"
          description: "目标 {{ $labels.job }}/{{ $labels.instance }} 已停止更新超过 5 分钟"

      # 规则3：检测 Prometheus 自身健康状况
      - alert: PrometheusTsdbCompactionsFailing
        expr: prometheus_tsdb_compactions_failed_total > 0
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Prometheus TSDB 压缩失败"
          description: "Prometheus TSDB 压缩失败次数: {{ $value }}"

      # 规则4：检测数据保留是否达标
      - alert: PrometheusDataRetentionLow
        expr: (prometheus_tsdb_head_min_time_seconds / 1000) > (time() - 86400 * 14)
        for: 5m
        labels:
          severity: info
        annotations:
          summary: "Prometheus 数据保留不足"
          description: "Prometheus 当前数据保留时长低于 14 天，可能存在数据丢失风险"

      # 规则5：检测告警规则评估是否正常
      - alert: PrometheusAlertmanagerJobMissing
        expr: absent(prometheus_target_scrape_interval_seconds{job="alertmanager"})
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Alertmanager target 缺失"
          description: "Prometheus 没有抓取 Alertmanager 的 targets"
```

## 常见问题解答

### Q1：Prometheus targets 显示 up 但 Grafana 无数据是什么原因？

A：最常见的原因是：
1. Prometheus 磁盘空间不足，无法写入数据（本次故障的原因）
2. Prometheus 抓取成功但写入失败（如内存队列满、权限问题）
3. 数据保留时间已到，旧数据被自动删除
4. Grafana 查询的时间范围设置错误（选择了没有数据的范围）

### Q2：如何判断 Prometheus 的 lastScrape 是否正常？

A：可以通过以下方法判断：

```bash
# 方法1：通过 API 查看
curl -s "http://localhost:9090/api/v1/targets" | jq '.data.activeTargets[0].lastScrape'

# 方法2：通过 Prometheus UI 查看
# 访问 http://prometheus:9090/targets 页面，查看 Last Scrape 列

# 方法3：通过 PromQL 查询
# 查询当前时间与最后抓取时间的差值
(time() - prometheus_target_last_scrape_timestamp_seconds{job="node_exporter"}) / 60
# 如果返回值大于 5（分钟），说明抓取可能有问题
```

### Q3：Prometheus 磁盘空间不足怎么办？

A：可以采取以下措施：
1. 清理旧数据（使用 `find` 删除 mtime 超过保留期的文件）
2. 调整 retention 时间（`--storage.tsdb.retention.time=15d`）
3. 配置 retention 大小限制（`--storage.tsdb.retention.size=10GB`）
4. 迁移数据目录到更大空间的磁盘
5. 定期使用 `promtool` 检查数据库健康状态

### Q4：Prometheus 的 health 和 status 有什么区别？

A：
- `health`：目标的可访问性，通过探测（HTTP/HTTPS/TCP 等）判断。目标可达则为 `up`，不可达则为 `down`。
- `lastScrape`：最后成功抓取数据的时间戳。即使目标可达，如果抓取失败或写入失败，lastScrape 也会停止更新。
- `status`：Prometheus 本身的运行状态，如 `OK`、`READ_TIMEOUT` 等。

### Q5：如何防止 Prometheus 磁盘空间不足？

A：建议采用以下多层防护策略：
1. **监控层**：配置磁盘空间告警，剩余空间低于 20% 时告警
2. **配置层**：设置合理的 `--storage.tsdb.retention.time` 和 `--storage.tsdb.retention.size`
3. **架构层**：使用独立磁盘或 LVM 存放 Prometheus 数据
4. **流程层**：定期审查数据保留策略，及时清理过期数据

### Q6：Prometheus 跳过抓取周期的阈值是多少？

A：Prometheus 不会主动"跳过"抓取周期，但如果写入失败（如队列满、磁盘满），它会在内存中缓存一段时间的数据。如果缓存也满了，就会丢弃最旧的数据。这意味着目标依然是 up 的，但新数据无法保存下来。

## 经验总结

### 1. 理解 Prometheus 的健康检查机制

Prometheus 的 targets 页面显示的 `health: up` 只表示目标可达（网络层面），不代表数据写入成功。这也是为什么我们需要额外的告警规则来检测"数据停滞"。

### 2. 定期检查 Grafana 等消费端

Prometheus 本身显示正常，并不意味着下游消费者（Grafana、Alertmanager 等）能正常获取数据。建议定期检查 Grafana 的仪表盘，确认数据在实时流动。

### 3. 日志是最好的诊断工具

本次故障的根因是 Prometheus 日志中的一条 `no space left on device` 错误。养成定期查看日志的习惯，往往能在告警触发前发现问题。

### 4. 告警规则需要覆盖"沉默失效"场景

默认的 Prometheus 告警规则只检测 `up == 0` 的情况，无法覆盖"目标可达但数据停滞"的场景。建议添加类似 `PrometheusScrapeStalled` 的自定义告警规则。

### 5. 监控本身也需要被监控

Prometheus 自身也是一个 target。建议为其配置监控，包括：
- Prometheus 进程的 CPU/内存使用率
- TSDB 的压缩状态
- 数据保留时长
- 抓取成功率

## 延伸阅读

- [Prometheus 官方文档 - Storage](https://prometheus.io/docs/prometheus/latest/storage/)
- [Prometheus 官方文档 - Alerting](https://prometheus.io/docs/prometheus/latest/alerting/)
- [Prometheus TSDB 原理与实践](https://ganeshverma.github.io/storage/prometheus-tsdb)
- [Grafana + Prometheus 监控最佳实践](https://grafana.com/docs/grafana/latest/best-practices/)

## 结语

这次"沉默的失效"故障持续了 48 小时，期间没有任何告警，运维团队完全不知情。直到今天例行检查 Grafana 仪表盘时才发现问题。

故障的根因并不复杂：Prometheus 数据目录所在磁盘空间不足，导致数据无法写入。但为什么没有触发告警？因为默认的告警规则只检测"目标不可达"，不检测"数据停滞"。

这个教训告诉我们：**监控系统告诉我们正常，可能只是它没有发现问题的能力。** 我们需要深入理解监控工具的工作原理，配置合理的告警规则，并定期验证监控数据的时效性。

希望这篇文章能帮到遇到类似问题的同学。如果你也有好的监控经验，欢迎在评论区分享。

---

*作者：小六，一个今天终于把 Prometheus "沉默失效"问题搞清楚了的技术人*
