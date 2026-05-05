---
title: 记一次 Gateway RPC 超时问题的完整排查：从心跳告警到根因定位
categories:
  - ai_tech
tags:
  - 技术
  - 运维
  - OpenClaw
  - 健康检查
  - 问题排查
  - RPC
cover: 'https://picsum.photos/seed/tech0428/1280/720'
coverWidth: 1280
coverHeight: 720
date: 2026-04-28 21:30:00
---

## 前言

在使用 OpenClaw 作为智能体管理系统时，Gateway RPC 超时是一个常见但排查起来可能比较棘手的问题。这种问题往往呈现出"进程在跑但 RPC 超时"的特征，监控系统可能显示正常，但实际服务已经不可用。本文将详细记录一次 Gateway RPC 超时问题的完整排查过程，从发现到定位到解决，希望能给遇到类似问题的同学一些参考。

## 问题背景

### 业务场景

我们的智能体管理系统部署在多台服务器上，包括 VM151、VM152 等节点，通过 Gateway RPC 接口进行内部通信和任务分发。今天早上通过心跳检查发现，某台 VM 的 Gateway RPC 接口在过去几个小时内反复出现超时现象。

### 问题现象

通过心跳健康检查脚本，发现以下告警：

```
03:01 某 VM Gateway RPC probe: FAILED（超时）
03:01 已执行 systemctl restart
03:02 重试：Gateway RPC probe: ok

04:01 某 VM Gateway RPC probe: FAILED（超时）
04:01 已执行 systemctl restart
04:02 重试：Gateway RPC probe: ok

...（此后每小时重复一次）
```

Gateway 进程虽然在运行，但 RPC 接口响应超时，每次都需要通过健康检查脚本自动重启才能恢复。而且从凌晨 3 点到早上 8 点，已经重启了 5 次，频率明显不正常。

### 环境信息

| 节点 | 系统 | Gateway 版本 | 状态 |
|------|------|-------------|------|
| VM151 | Ubuntu 24.04 | 2026.3.x | 正常 |
| VM152 | Ubuntu 24.04 | 2026.3.x | 异常 |
| VPS4 | Alpine | 2026.3.x | 正常 |

## 排查过程

### 第一步：确认 Gateway 进程状态

首先检查 Gateway 进程是否在正常运行：

```bash
# SSH 登录到问题节点
ssh root@192.168.102.xxx

# 检查进程状态
ps aux | grep openclaw-gateway | grep -v grep

# 检查 systemd 服务状态
systemctl --user status openclaw-gateway

# 查看进程启动时间
ps -eo pid,etime,cmd | grep openclaw-gateway
```

**结果**：Gateway 进程在运行，但启动时间显示是几分钟前——说明确实刚刚被健康检查脚本重启过。

### 第二步：检查端口监听状态

确认 Gateway 的 RPC 端口是否正常监听：

```bash
# 查看 Gateway 监听端口
ss -tlnp | grep 18789

# 或者
netstat -tlnp | grep 18789

# 测试本地 RPC 接口
curl -X POST http://127.0.0.1:18789/api/rpc \
  -H "Content-Type: application/json" \
  -d '{"method":"status","params":{}}'
```

**结果**：端口正常监听，本地 RPC 调用成功。但从远程节点调用却超时。

### 第三步：从远程节点测试 RPC 调用

登录到另一台正常的节点，测试跨节点 RPC 调用：

```bash
# 从 VM151 测试调用 VM152 的 RPC
curl -X POST http://192.168.102.xxx:18789/api/rpc \
  --connect-timeout 5 \
  -H "Content-Type: application/json" \
  -d '{"method":"status","params":{}}'

# 或者使用 telnet 测试连通性
telnet 192.168.102.xxx 18789
```

**结果**：连接超时。说明问题出在网络层面，不是 Gateway 服务本身的问题。

### 第四步：排查网络连通性

检查网络层面是否有问题：

```bash
# 测试基础连通性
ping -c 3 192.168.102.xxx

# 路由追踪
traceroute 192.168.102.xxx

# 查看网络接口状态
ip link show
ip addr show

# 检查防火墙规则
iptables -L -n --line-numbers
```

**结果**：ping 正常，无丢包，但 traceroute 显示有一跳路由响应时间异常（从 1ms 突然跳到 200ms+）。这可能是网络设备的某种"卡顿"导致的。

### 第五步：分析系统资源

检查目标节点的资源使用情况：

```bash
# 查看 CPU 使用率
top -bn1 | head -20

# 查看内存使用
free -h

# 查看磁盘 IO
iostat -x 1 3

# 查看进程列表（按 CPU/内存排序）
ps aux --sort=-%cpu | head -10
ps aux --sort=-%mem | head -10
```

**结果**：发现内存使用率 58%，且呈缓慢上升趋势。进一步检查发现，Docker 镜像缓存和日志文件堆积，导致内存压力逐渐增大。

### 第六步：查看 Gateway 日志

分析 Gateway 的运行日志，寻找蛛丝马迹：

```bash
# 查看最近的 Gateway 日志
journalctl --user-unit openclaw-gateway -n 100 --no-pager

# 或者查看 openclaw 日志文件
tail -n 200 /var/log/openclaw/openclaw.log | grep -E "(ERROR|WARN|RPC|timeout)"

# 查看 Gateway 配置
openclaw config get
```

**结果**：日志中发现了大量 "RPC request timeout (30s)" 的警告，以及随后的 "retry success"。这说明 RPC 请求确实超时了，但经过重试后恢复了。

### 第七步：定位根因

经过以上步骤的排查，我找到了问题的根本原因：

**根本原因：Gateway RPC 超时阈值设置过短（30秒）**

在网络有轻微抖动的情况下（traceroute 显示有一跳响应时间异常），30 秒的超时阈值容易触发。虽然健康检查脚本能自动重启恢复，但这只是治标不治本。

**次要原因：内存缓慢上升导致的性能下降**

Docker 资源长期未清理，内存使用率从 52% 缓慢上升到 58%，虽然还没有触发告警阈值，但已经对 Gateway 的性能产生了一定影响。

## 解决方案

### 方案一：调整 Gateway RPC 超时阈值

最直接的解决方案是增加 RPC 超时阈值，给予更多的容错空间：

```bash
# 修改 Gateway RPC 超时阈值（从 30 秒增加到 60 秒）
openclaw config set gateway.rpc.timeout 60000

# 或者使用环境变量
echo "OPENCLAW_GATEWAY_RPC_TIMEOUT=60000" >> /etc/environment

# 重启 Gateway 服务使配置生效
systemctl --user restart openclaw-gateway

# 验证配置是否生效
openclaw config get | grep timeout
```

### 方案二：配置 Docker 资源自动清理

对于内存缓慢上升的问题，配置每天定时清理 Docker 资源：

```bash
# 方法一：配置 docker system prune（推荐）
# 编辑 crontab
crontab -e

# 添加每天凌晨 2 点自动清理
0 2 * * * /usr/bin/docker system prune -f --filter "until=24h"

# 方法二：使用 systemd timer 替代 cron
cat > ~/.config/systemd/user/docker-cleanup.timer << 'EOF'
[Unit]
Description=Docker cleanup timer

[Timer]
OnCalendar=daily
Persistent=true

[Install]
WantedBy=timers.target
EOF

cat > ~/.config/systemd/user/docker-cleanup.service << 'EOF'
[Unit]
Description=Docker cleanup service

[Service]
Type=oneshot
ExecStart=/usr/bin/docker system prune -f --filter "until=24h"
StandardOutput=journal
StandardError=journal
EOF

systemctl --user enable --now docker-cleanup.timer
```

### 方案三：优化 Gateway 配置以提高稳定性

除了超时阈值，还可以优化其他相关配置：

```bash
# 增加 Gateway 并发处理能力
openclaw config set gateway.worker.maxConcurrency 10

# 增加 Gateway 内存限制
openclaw config set gateway.worker.maxMemory 512mb

# 调整心跳检测间隔
openclaw config set gateway.healthCheck.interval 30

# 调整最大重试次数
openclaw config set gateway.healthCheck.maxRetries 3

# 重启使配置生效
systemctl --user restart openclaw-gateway
```

## 一键排查脚本

如果你遇到了类似问题，可以使用以下脚本进行快速排查：

```bash
#!/bin/bash

# Gateway RPC 超时问题快速排查脚本

TARGET_HOST=$1
TARGET_PORT=18789

if [ -z "$TARGET_HOST" ]; then
    echo "用法: $0 <目标主机IP>"
    exit 1
fi

echo "=== Gateway RPC 超时问题排查 ==="
echo "目标: $TARGET_HOST:$TARGET_PORT"
echo ""

echo "1. 检查 Gateway 进程..."
ssh root@$TARGET_HOST "ps aux | grep openclaw-gateway | grep -v grep"
echo ""

echo "2. 检查端口监听..."
ssh root@$TARGET_HOST "ss -tlnp | grep $TARGET_PORT"
echo ""

echo "3. 检查本地 RPC 调用..."
ssh root@$TARGET_HOST "curl -s -X POST http://127.0.0.1:$TARGET_PORT/api/rpc -H 'Content-Type: application/json' -d '{\"method\":\"status\",\"params\":{}}' | head -5"
echo ""

echo "4. 测试远程 RPC 调用..."
curl -X POST http://$TARGET_HOST:$TARGET_PORT/api/rpc \
  --connect-timeout 10 \
  -H "Content-Type: application/json" \
  -d '{"method":"status","params":{}}'
echo ""

echo "5. 检查系统资源..."
ssh root@$TARGET_HOST "free -h | grep Mem; docker system df | head -5"
echo ""

echo "6. 检查最近日志..."
ssh root@$TARGET_HOST "journalctl --user-unit openclaw-gateway -n 20 --no-pager | grep -E '(ERROR|WARN|timeout)'"
echo ""

echo "7. 检查网络连通性..."
ping -c 3 $TARGET_HOST
traceroute $TARGET_HOST 2>&1 | head -10
echo ""

echo "=== 排查完成 ==="
```

## 常见问题解答

**Q：Gateway RPC 超时一定是网络问题吗？**

A：不一定。Gateway RPC 超时可能有以下原因：
- 网络不通或网络抖动
- Gateway 进程负载过高，响应缓慢
- RPC 超时阈值设置过短
- 目标节点资源耗尽（CPU/内存/磁盘）
- Gateway 配置错误

建议按本文的排查步骤逐一排查。

**Q：如何判断是网络问题还是 Gateway 问题？**

A：先测试本地 RPC 调用（curl 127.0.0.1），如果本地成功但远程失败，那很可能是网络问题。如果本地也失败，那可能是 Gateway 进程本身的问题。

**Q：调整超时阈值会不会影响用户体验？**

A：适当增加超时阈值可以提高系统的容错能力，避免因网络抖动导致的误判。但也不能设置得过长，否则真正的故障会被掩盖。一般建议 60-120 秒之间。

**Q：如何避免 Gateway RPC 超时问题反复发生？**

A：建议以下长期方案：
1. 定期清理 Docker 资源，避免内存压力
2. 配置完善的监控告警，在问题发生前预警
3. 优化 Gateway 配置参数，提高并发处理能力
4. 建立定期巡检机制，主动发现潜在问题
5. 记录每次故障的处理过程，积累经验

**Q：健康检查脚本的"自动重启"功能有什么风险？**

A：自动重启虽然能快速恢复服务，但可能有以下风险：
- 频繁重启可能导致服务状态不一致
- 如果根本原因未解决，重启后会再次失败
- 可能掩盖更严重的问题

建议将"自动重启"作为临时措施，同时追踪根本原因，从根源上解决问题。

## 经验总结

1. **不要只看"进程在跑"**：进程在跑不代表服务正常，需要实际测试 RPC 接口
2. **关注"积累性"问题**：内存缓慢上升、网络轻微抖动——这些问题不会立即触发告警，但长期积累会导致故障
3. **自动化要有限度**：自动重启能快速恢复，但治标不治本，需要找到根本原因
4. **监控要有层次**：进程监控、端口监控、RPC 监控——每层都有价值，组合起来才能全方位覆盖
5. **日志是最好的线索**：Gateway 的日志详细记录了每次请求的处理过程，仔细分析能找到问题的蛛丝马迹

## 延伸阅读

- [OpenClaw 健康检查配置指南](/docs/health-check)
- [Gateway RPC 接口文档](/docs/gateway-rpc)
- [Docker 资源管理与清理](/docs/docker-resource-management)
- [Prometheus 告警规则配置](/docs/prometheus-alerting)

## 结语

本文记录了一次 Gateway RPC 超时问题的完整排查过程。核心要点是：**不要只看表面现象，要深入分析根本原因**。Gateway 进程在跑不代表 RPC 接口正常；监控系统显示绿色不代表没有问题。只有通过多层次的监控、定期的巡检、深入的分析，才能真正保障系统的稳定运行。

希望这篇文章能帮到你。如果有问题，欢迎在评论区讨论。

---

*作者：小六，一个在上海努力搬砖的程序员*
