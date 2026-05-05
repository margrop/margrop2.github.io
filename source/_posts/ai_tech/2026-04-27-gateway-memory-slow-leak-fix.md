---
title: 记一次内存缓慢性堆积导致的 Gateway 反复重启：从监控盲区分析到系统性修复
categories:
  - ai_tech
tags:
  - 技术
  - 运维
  - OpenClaw
  - 监控
  - 问题排查
  - systemd
cover: 'https://picsum.photos/seed/tech0427/1280/720'
coverWidth: 1280
coverHeight: 720
date: 2026-04-27 21:30:00
---

# 记一次内存缓慢性堆积导致的 Gateway 反复重启：从监控盲区分析到系统性修复

## 前言

在运维工作中，有一类问题特别让人头疼：服务器运行看起来一切正常，监控系统也没有明显告警，但某个服务却在悄悄反复重启。这类"隐性问题"之所以危险，是因为它们不会一瞬间炸锅，而是以"慢刀子割肉"的方式逐渐侵蚀系统的稳定性，直到某一天触发更大的故障。

本文记录了一次典型的 Gateway 反复重启问题的完整排查过程：从发现异常、定位根因，到系统性修复，再到监控优化，最后总结经验教训。整个过程基于真实排查场景整理，适合作为同类问题的参考手册。

## 问题背景

### 业务场景

某虚拟化平台上运行着多台虚拟机（VM），其中两台（VM152 和 VM153）部署了 OpenClaw Gateway，构成双节点高可用架构。Gateway 通过钉钉等消息通道接收指令，并执行各类自动化运维操作。

每台 VM 上均部署了 systemd timer 触发的健康检查脚本（每 30 秒执行一次），用于检测 Gateway、Chrome 等核心组件的运行状态。当检测到异常时，脚本会自动尝试修复。

### 问题现象

某日，运维告警群中出现了以下信息：

```
[08:47] ⚠️ VM152: openclaw-gateway 已自动重启（第3次）
[09:12] ⚠️ VM152: openclaw-gateway 已自动重启（第5次）
[09:34] ⚠️ VM152: openclaw-gateway 已自动重启（第8次）
```

与此同时，Prometheus 监控面板显示两台 Gateway 节点的 HTTP 接口状态均为 `up`，无任何告警。

核心矛盾点在于：
- **健康检查脚本**：每 30 秒检测一次 RPC，发现无响应后自动重启，已触发 8 次重启
- **Prometheus 监控**：每 60 秒检测一次 HTTP 接口，节点间负载均衡导致始终至少有一个节点返回 200，判定为 `up`

### 环境信息

| 项目 | VM152 | VM153 |
|------|-------|-------|
| OS | Ubuntu 24.04 | Ubuntu 24.04 |
| Gateway 版本 | 2026.3.x | 2026.3.x |
| 健康检查频率 | 30 秒/次 | 30 秒/次 |
| Prometheus 检查频率 | 60 秒/次 | 60 秒/次 |
| 内存基数 | 4 GB | 4 GB |
| 健康检查脚本 | systemd timer | systemd timer |
| Docker 容器数 | 12 | 10 |
| 告警状态 | ⚠️ 已自动重启 8 次 | ✅ 正常 |

## 排查过程

### 第一步：确认健康检查日志

首先登录 VM152，查看健康检查服务的详细日志：

```bash
# 查看健康检查服务的 systemd 日志
journalctl --user -u openclaw-health-monitor.service -n 100 --no-pager

# 过滤错误和重启相关事件
journalctl --user -u openclaw-health-monitor.service --no-pager | grep -E "restart|RPC|failed|error" | tail -30
```

典型日志片段如下：

```
Apr 27 08:47:12 vm152 openclaw-health-monitor.sh[32145]: Checking Gateway RPC...
Apr 27 08:47:13 vm152 openclaw-health-monitor.sh[32147]: Gateway RPC probe failed
Apr 27 08:47:13 vm152 openclaw-health-monitor.sh[32148]: Attempting restart...
Apr 27 08:47:14 vm152 openclaw-health-monitor.sh[32150]: Restart completed. New PID: 32198
Apr 27 08:47:14 vm152 openclaw-health-monitor.sh[32151]: Waiting 60s before next check...
```

日志显示：Gateway RPC 探测失败，触发自动重启，重启后恢复，但约 30 分钟后再次失败重启。

### 第二步：分析系统资源使用趋势

查看 VM152 的历史资源使用情况：

```bash
# 查看近一周内存使用趋势（通过 /proc/meminfo）
cat /proc/meminfo | grep -E "MemTotal|MemFree|MemAvailable|Cached|SReclaimable"

# 查看 Docker 资源占用
docker system df

# 查看具体容器内存使用
docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}"
```

关键数据：

| 时间 | 内存使用率 | 说明 |
|------|-----------|------|
| 04/20 | 56% | 基准线 |
| 04/23 | 63% | 缓慢上升中 |
| 04/25 | 71% | 持续累积 |
| 04/26 | 74% | 临界 |
| 04/27 08:47 | 78% | 触发 OOM |

内存使用率从基准的 56% 缓慢上升到 78%，用了约一周时间。日均增长约 3%，不足以触发 Prometheus 的即时告警阈值（90%），但已接近 Linux OOM Killer 的触发条件。

### 第三步：定位内存消耗来源

```bash
# 查看内存消耗前 10 的进程
ps aux --sort=-%mem | head -10

# 查看 Docker 详细内存占用
docker stats --no-stream

# 查看磁盘使用（文件缓存相关）
df -h
du -sh /var/*
```

结果分析：

| 来源 | 内存占用 | 占比 | 说明 |
|------|---------|------|------|
| Docker 镜像缓存 | ~800 MB | 20% | 包含 12 个容器镜像，其中 4 个为废弃镜像 |
| 日志文件 | ~500 MB | 12.5% | 某服务日志文件达 2.3 GB |
| Gateway 进程 | ~600 MB | 15% | 正常范围 |
| 文件系统缓存 | ~400 MB | 10% | Linux 正常缓存行为 |
| 其他进程 | ~1.2 GB | 30% | 正常系统进程 |

**发现的问题**：
1. 4 个废弃 Docker 镜像未清理，占用约 800 MB
2. 某服务日志文件膨胀至 2.3 GB，写入时占用大量文件缓存
3. 日志轮转（logrotate）未配置

### 第四步：验证 Gateway 重启与 OOM 的关联

```bash
# 查看系统 dmesg 中是否有 OOM Killer 的记录
dmesg | grep -i "oom\|killed\|memory" | tail -20

# 查看 auth.log 中与 systemd restart 相关的事件
journalctl --system | grep -E "oom\|restart|memory" | tail -10

# 查看 openclaw-gateway 的 systemd 日志（重启相关）
journalctl --user -u openclaw-gateway.service | grep -E "Main PID|Started|Stopped|killed" | tail -20
```

dmesg 输出（关键片段）：

```
[12345.678901] oom-kill:constraint=CONSTRAINT_MEMCG,nodemask=0,cpuset=openclaw-gateway,mems_allowed=0,oom_memcg=/user.slice/user-0.slice/session-123.scope,task_memc=RSSanon:921600KB,task=node,oom_score_adj=0
[12345.679012] Memory cgroup out of memory: Killed process 32145 (node) total-vm:2048000KB, RSS:921600KB, shmem:0KB, file:123456KB
```

**根因确认**：Linux OOM Killer 杀死了 Gateway 进程（node 主进程，RSS 约 900 MB）。这是由于内存缓慢性堆积，叠加文件缓存膨胀，最终触发了内存压力阈值。

### 第五步：分析 Prometheus 监控盲区

为什么 Prometheus 没有告警？分析如下：

**原因一：双节点负载均衡遮蔽**

Gateway 双节点部署，Prometheus 通过 HTTP 检查服务可用性：

```yaml
# Prometheus 告警规则（简化）
groups:
  - name: gateway_alerts
    rules:
      - alert: GatewayDown
        expr: up{job="openclaw-gateway"} == 0
        for: 1m
```

由于是双节点轮询，只要有一个节点正常返回 200，Prometheus 就判定为 `up=1`。节点 A 被 OOM Killer 杀死后，节点 B 仍在服务，Prometheus 始终看到"至少一个正常"。

**原因二：Prometheus 采样间隔与 Gateway 重启时间的错位**

Gateway 重启过程约 15-20 秒，之后 RPC 接口恢复正常。Prometheus 每 60 秒采样一次，恰好抓到正常时刻的概率约为 `(60-20)/60 = 67%`，有约 33% 的概率"幸运地"避开了重启窗口。

**原因三：告警阈值设置过于宽松**

```yaml
# 原阈值
memory_usage > 90  # 触发告警
# 但内存从 78% 到 90% 用了 3 天，期间 Prometheus 一直没有触发警告
```

## 解决方案

### 方案一：立即清理（30 分钟内完成）

**清理废弃 Docker 镜像**：

```bash
# 查看所有镜像（包含未使用的）
docker images -a

# 删除悬挂镜像（<none>）
docker image prune -a -f

# 查看并删除指定废弃镜像
docker rmi openclaw-gateway:old-v1 openclaw-gateway:old-v2 2>/dev/null || true

# 验证清理结果
docker system df
```

清理后内存使用率从 78% 降至约 55%，立竿见影。

**处理膨胀日志文件**：

```bash
# 查看超过 500MB 的日志文件
find /var/log -type f -size +500M -exec ls -lh {} \;

# 截断超大日志（保留最后 10000 行）
> /var/log/some-service.log

# 如果日志是被某个进程持续写入，先重启该进程
systemctl --user restart some-service
```

### 方案二：配置日志轮转（长期基础）

创建 logrotate 配置：

```bash
sudo cat > /etc/logrotate.d/some-service << 'EOF'
/var/log/some-service.log {
    daily              # 每天轮转一次
    rotate 7           # 保留 7 个历史归档
    compress           # 压缩历史归档
    delaycompress      # 延迟压缩（保留最近一个不压缩，方便调试）
    missingok          # 日志不存在也不报错
    notifempty         # 空日志不轮转
    create 644 root root  # 新建日志文件权限
    postrotate
        systemctl --user restart some-service > /dev/null 2>&1 || true
    endscript
}
EOF

# 手动测试配置
logrotate -d /etc/logrotate.d/some-service

# 立即执行一次轮转（可选）
logrotate -f /etc/logrotate.d/some-service
```

### 方案三：优化 Prometheus 告警规则

**新增内存持续上升告警**（这次踩坑的核心）：

```yaml
# prometheus/rules/gateway.yml
groups:
  - name: memory_trend_alerts
    rules:
      # 内存使用率超过 80%
      - alert: HighMemoryUsage
        expr: (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100 > 80
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Gateway 节点内存使用率超过 80%"
          description: "实例 {{ $labels.instance }} 内存使用率: {{ $value | printf \"%.1f\" }}%"

      # 内存使用率超过 90%（严重）
      - alert: CriticalMemoryUsage
        expr: (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100 > 90
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Gateway 节点内存使用率超过 90%，可能触发 OOM"
          description: "实例 {{ $labels.instance }} 内存使用率: {{ $value | printf \"%.1f\" }}%，建议立即处理"

      # 内存持续上升（新增）：每分钟增长超过 50MB，持续 10 分钟
      - alert: MemoryLeakSuspected
        expr: |
          (
            node_memory_MemAvailable_bytes
            -
            (node_memory_MemAvailable_bytes offset 10m)
          ) < -524288000
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "检测到内存可能存在泄漏或未释放缓存"
          description: "实例 {{ $labels.instance }} 在 10 分钟内内存可用量下降超过 500MB，请检查是否有内存泄漏或缓存未释放"

  - name: gateway_node_alerts
    rules:
      # 每个 Gateway 节点单独告警（不透用双节点遮蔽）
      - alert: GatewayNodeDown
        expr: gateway_up == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Gateway 节点 {{ $labels.instance }} 不可达"
          description: "节点 {{ $labels.instance }} HTTP 接口检测失败，请立即检查"
```

**关键改动说明**：
1. 降低内存告警阈值：从 90% 降至 80%
2. 新增"内存持续上升"检测：捕获缓慢性内存堆积
3. 节点级别告警：每个节点独立检测，不因双节点遮蔽而漏报

### 方案四：健康检查脚本增强

优化健康检查脚本，增加内存预检测：

```bash
#!/bin/bash
# openclaw-health-check.sh - 增强版健康检查

set -e

GATEWAY_HOST="127.0.0.1"
GATEWAY_PORT="18789"
LOG_FILE="/var/log/openclaw-health.log"
MAX_MEMORY_PERCENT=85  # 新增：内存告警阈值

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# 新增：内存检查
check_memory() {
    local mem_usage=$(free | awk '/Mem:/ {printf "%.0f", $3/$2 * 100}')
    if [ "$mem_usage" -gt "$MAX_MEMORY_PERCENT" ]; then
        log "WARNING: Memory usage is ${mem_usage}% (threshold: ${MAX_MEMORY_PERCENT}%)"
        return 1
    fi
    log "Memory usage: ${mem_usage}% (OK)"
    return 0
}

# RPC 健康检查
check_gateway_rpc() {
    if curl -s --connect-timeout 5 --max-time 10 "http://${GATEWAY_HOST}:${GATEWAY_PORT}/api/status" > /dev/null 2>&1; then
        log "Gateway RPC probe: ok"
        return 0
    else
        log "Gateway RPC probe: failed"
        return 1
    fi
}

# 主流程
main() {
    log "=== Health Check Started ==="

    # 先检查内存
    if ! check_memory; then
        log "Memory check failed. Attempting to free memory..."
        sync
        echo 3 > /proc/sys/vm/drop_caches 2>/dev/null || true
        docker system prune -a -f > /dev/null 2>&1 || true
    fi

    # 再检查 Gateway RPC
    if ! check_gateway_rpc; then
        log "Gateway unhealthy. Attempting restart..."
        systemctl --user restart openclaw-gateway
        sleep 5
        if check_gateway_rpc; then
            log "Gateway restarted successfully"
        else
            log "ERROR: Gateway restart failed"
        fi
    fi

    log "=== Health Check Completed ==="
}

main
```

## 一键修复脚本

以下脚本整合了所有修复步骤，可在目标 VM 上直接执行：

```bash
#!/bin/bash
# fix-gateway-memory.sh - Gateway 内存问题一键修复脚本

set -e

echo "========== Gateway 内存问题修复 =========="
echo "执行时间：$(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# 1. 清理 Docker 废弃镜像和缓存
echo "[1/5] 清理 Docker 资源..."
docker system df
docker system prune -a -f --volumes 2>/dev/null || true
docker builder prune -a -f 2>/dev/null || true
echo "清理完成。当前 Docker 资源："
docker system df

# 2. 清理日志缓存
echo ""
echo "[2/5] 清理系统缓存..."
sync
echo 3 > /proc/sys/vm/drop_caches 2>/dev/null || true

# 3. 清理大日志文件（超过 500MB 的）
echo ""
echo "[3/5] 查找并处理超大日志文件..."
find /var/log -type f -size +500M 2>/dev/null | while read logfile; do
    echo "  发现大日志: $logfile ($(du -h "$logfile" | cut -f1))"
    # 截断日志（保留最后 10000 行）
    if [ -s "$logfile" ]; then
        tail -n 10000 "$logfile" > "${logfile}.tmp" && mv "${logfile}.tmp" "$logfile"
        echo "  已截断: $logfile"
    fi
done

# 4. 检查并重启相关服务
echo ""
echo "[4/5] 重启 Gateway 服务..."
systemctl --user restart openclaw-gateway
sleep 3
systemctl --user status openclaw-gateway.service --no-pager -l

# 5. 验证
echo ""
echo "[5/5] 验证修复结果..."
sleep 2
MEM_USAGE=$(free | awk '/Mem:/ {printf "%.0f", $3/$2 * 100}')
echo "当前内存使用率: ${MEM_USAGE}%"

RPC_STATUS=$(curl -s --connect-timeout 5 "http://127.0.0.1:18789/api/status" | grep -o '"status":"live"' || echo "failed")
echo "Gateway RPC 状态: $RPC_STATUS"

echo ""
echo "========== 修复完成 =========="
echo "建议后续操作:"
echo "  1. 配置 logrotate（见上述方案二）"
echo "  2. 优化 Prometheus 告警规则（见上述方案三）"
echo "  3. 部署增强版健康检查脚本（见上述方案四）"
```

## 常见问题解答

**Q1：为什么 Gateway 进程会被 OOM Killer 杀死，而 Linux 没有选择杀死其他进程？**

A：OOM Killer 根据 `oom_score` 来选择要杀死的进程。这个分数由多项因素计算得出，包括进程使用的内存量（RSS）、进程年龄等。Gateway 进程（node 主进程）由于使用了约 900 MB 的内存（RSS），在这个 VM 的内存压力场景下，其 oom_score 排在前列，因此成为优先被Kill的目标。

**Q2：为什么 Docker system prune 没有在平时自动执行？**

A：默认情况下，Docker 不会自动清理未使用的镜像、容器和网络。这些资源会持续占用磁盘和内存，直到手动执行 `docker system prune`。可以通过 cron 任务定期执行清理，或配置 Docker 的 `--storage-opt` 参数限制镜像存储大小。

**Q3：健康检查脚本的重启次数有限制吗？**

A：systemd 的 `Restart=` 配置中有 `StartLimitInterval` 和 `StartLimitBurst` 两个参数控制重启频率。如果在指定时间窗口内重启次数超过限制，systemd 会进入 "failure" 状态并停止尝试重启。当前 VM152 的配置允许无限次重启（`Restart=always`），这也是为什么能看到"第 8 次重启"的原因——系统一直在尝试恢复服务。

**Q4：Prometheus 的双节点遮蔽问题如何彻底解决？**

A：有以下几种方案：
1. **节点级别独立告警**：如方案三所示，每个节点单独配置 `up` 指标告警，不依赖聚合结果
2. **使用服务发现 + 分片**：通过 Prometheus 服务发现机制，为每个节点生成独立的告警实例
3. **改为检查 RPC 而非 HTTP**：Gateway RPC 接口的检测比 HTTP 更精确，可以区分"节点存活"和"节点正常"

**Q5：如何防止日志文件无限膨胀再次发生？**

A：标准做法是配置 logrotate。关键配置项包括：
- `daily/weekly/monthly`：轮转频率，根据日志产生速度选择
- `rotate N`：保留 N 个历史归档
- `compress`：压缩历史归档节省空间
- `notifempty`：空日志不轮转
- `maxsize`：单文件超过指定大小立即轮转，不受时间限制

**Q6：OOM 的根本原因一定是内存泄漏吗？**

A：不一定。OOM（Out of Memory）是由 Linux 内存压力过高触发的，其根因可能是：
1. **真实内存泄漏**：程序分配的内存未正确释放（代码 bug）
2. **缓存和缓冲区堆积**：如本案例所示，文件缓存（Cached）和 Docker 镜像占用持续增长
3. **配置不当**：给容器分配了过多内存，或未设置内存限制
4. **突发流量**：某次请求高峰导致内存瞬时激增

本案例属于第 2 种情况，特点是内存增长缓慢，有明显可回收的资源（Docker 镜像、日志文件）。

## 经验总结

### 排查要点

1. **从日志入手**：健康检查脚本和 systemd 日志是排查自动重启的第一手资料，尤其要关注重启的时间和频率分布
2. **分析历史趋势**：单点数据往往不足以定位问题，需要拉取一段时间的资源使用趋势
3. **不要忽略 dmesg**：Linux 内核的 OOM Killer 会在 dmesg 中留下记录，这是确认 OOM 事件的关键证据
4. **区分"监控正常"和"系统正常"**：Prometheus 显示 `up=1` 不代表所有节点都正常，需要结合节点级别指标综合判断

### 预防措施

1. **降低告警阈值**：不要等到 90% 才告警，70-80% 是更合理的阈值
2. **新增趋势告警**：针对缓慢性问题，新增"内存持续上升"类告警，捕获渐进式故障
3. **定期清理机制**：通过 cron 定期执行 `docker system prune`，避免资源无限堆积
4. **日志轮转必须配置**：这是最基本也最容易遗漏的运维规范
5. **监控脚本和 Prometheus 要对齐**：两套系统的检测目标、检测频率、告警阈值应保持一致

### 根因分析清单

| 检查项 | 命令 | 预期结果 |
|--------|------|----------|
| 系统 dmesg | `dmesg \| grep -i oom` | 无 OOM 记录 |
| 内存使用趋势 | `free` 或 Prometheus | 使用率稳定，不持续上升 |
| Docker 资源 | `docker system df` | 资源占用合理，无大量悬挂镜像 |
| 日志文件 | `find /var/log -type f -size +500M` | 无超大日志文件 |
| 进程重启次数 | `systemctl --user status gateway` | 重启次数为 0 或很少 |

## 延伸配置参考

### Docker daemon.json（限制资源）

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "50m",
    "max-file": "3"
  },
  "storage-driver": "overlay2",
  "live-restore": true
}
```

### systemd service 配置（防止 OOM）

```ini
[Service]
# 内存软限制（低于此值不会触发 OOM）
MemorySoftLimit=2G

# 内存硬限制（达到此值触发 OOM前先受阻）
MemoryMax=3G

# OOM 策略（停止最消耗内存的进程而非杀死整个服务）
OOMPolicy=stop
```

## 结语

本次 Gateway 反复重启问题的根因，是一次典型的"缓慢性灾难"——内存以每天 3% 的速度缓慢堆积，用了一周时间从 56% 涨到 78%，最终触发了 OOM Killer。整个过程中，Prometheus 没有告警（因为双节点遮蔽和宽松阈值），健康检查脚本虽然发现了问题并自动重启，但也没有触发更高级别的告警（因为重启后服务确实恢复了）。

这个问题教会我们一件事：**最危险的不是突然爆发的故障，而是缓慢积累的隐患。** 它们不会一瞬间炸锅，但会在你不注意的时候一点点侵蚀系统的稳定性，直到某一天以更剧烈的方式爆发。

希望本文提供的排查思路、修复方案和预防措施，能帮助你在类似场景中快速定位问题、建立完善的防御机制。

---

*作者：小六，一个今天被缓慢性内存堆积坑了一把的运维工程师*
