---
title: 记一次 OpenClaw Gateway 服务"冻死"的完整排查：从发现到恢复的全流程记录
categories:
  - ai_tech
tags:
  - 技术
  - 运维
  - OpenClaw
  - 问题排查
  - 虚拟机
cover: 'https://picsum.photos/seed/tech0406/1280/720'
coverWidth: 1280
coverHeight: 720
date: 2026-04-06 21:30:00
---

## 前言

运维工作中有一种经典的故障类型，叫做"服务假死"——进程还在，端口还通，但就是不响应任何请求。这种故障排查起来往往比较棘手，因为从表面上看一切正常，但实际功能已经不可用了。

本文记录一次典型的 OpenClaw Gateway 服务"冻死"故障的完整排查过程：从现象发现、根因定位，到临时恢复，再到后续改进建议。整篇文章基于真实排查过程整理，希望能为遇到类似问题的同学提供一些参考。

## 问题背景

### 业务场景

某虚拟化平台（PVE）上运行着多台虚拟机（VM），其中一台 Ubuntu 虚拟机（VM152）部署了 OpenClaw Gateway，作为核心管理节点。Gateway 通过 WebSocket 长连接接收来自钉钉等消息通道的指令，并执行各种自动化运维操作。

该 VM 采用虚拟化平台的标准模板部署，分配了 4 核 CPU 和 4GB 内存，托管在 PVE 集群中的一台物理服务器上。

### 问题现象

某天中午，监控系统发出告警：该 VM 上部署的 OpenClaw Gateway HTTP 接口无响应。

具体表现：
- **端口可达**：`curl -v 192.168.102.1xx:18789` 能建立 TCP 连接，但没有 HTTP 响应
- **SSH 正常**：通过虚拟化平台的 VNC 或 SSH 可以正常登录 VM，操作系统运行正常
- **进程存在**：`ps aux | grep openclaw` 显示进程还在运行
- **但应用层无响应**：`curl http://192.168.102.1xx:18789/health` 一直等待，最终超时

这是一个典型的"服务假死"现象：底层进程还在，但应用层已经完全不工作了。

### 环境信息

| 组件 | 信息 |
|------|------|
| 虚拟机管理平台 | PVE245 |
| VM ID | 152 |
| VM IP | 192.168.102.1xx |
| Gateway 端口 | 18789 |
| VM 配置 | 4核 / 4GB / Ubuntu |
| Guest Agent | 未运行 |

## 排查过程

### 第一步：确认问题范围

首先从外部测试问题的范围，确认是单个服务异常还是 VM 整体异常：

```bash
# 测试 VM 的基本网络连通性
ping -c 5 192.168.102.1xx

# 测试端口可达性（TCP 三次握手）
nc -zv -w 5 192.168.102.1xx 18789

# 测试其他常用端口（SSH）
ssh root@192.168.102.1xx "echo 'SSH OK'"

# 测试 VM 本地健康检查
ssh root@192.168.102.1xx "curl -s --connect-timeout 3 http://127.0.0.1:18789/health"
```

排查结果：

| 测试项 | 结果 | 说明 |
|--------|------|------|
| ping | ✅ 正常 | 网络层连通 |
| nc 18789 | ✅ TCP 连接成功 | 端口在监听 |
| SSH | ✅ 正常 | VM 操作系统正常 |
| 本地 curl | ❌ 超时 | 服务层无响应 |

**关键发现**：VM 的网络和 SSH 都正常，说明问题不在 VM 层面，而是 OpenClaw Gateway 服务本身"冻死"了。

### 第二步：分析可能原因

服务假死的可能原因有以下几类：

**1. 进程阻塞**
- Gateway 主线程被某个耗时操作阻塞（如同步调用卡住）
- 线程池耗尽（所有工作线程都在等待，无法处理新请求）
- 死锁（多个线程相互等待，形成死循环）

**2. 资源耗尽**
- 内存耗尽，GC 压力过大，导致进程无法正常响应
- 文件描述符耗尽（达到系统限制，新的连接无法建立）
- 句柄泄漏（某些资源没有正确释放）

**3. 依赖服务异常**
- 数据库连接池耗尽
- 外部 API 超时阻塞
- 消息队列连接断开

**4. JVM/运行时问题（如果是 Java 服务）**
- JIT 编译导致 CPU 占用飙升
- GC 停顿导致长时间无响应

### 第三步：尝试在 VM 内部诊断

登录 VM 后，进行以下检查：

```bash
# 1. 查看 OpenClaw 进程状态
ps aux | grep -E 'openclaw|node' | grep -v grep

# 2. 查看进程启动时间和运行时间
ps -eo pid,lstart,etime,cmd | grep openclaw

# 3. 检查进程的文件描述符使用情况
ls -la /proc/$(pgrep -f openclaw)/fd | wc -l

# 4. 检查系统最大文件描述符限制
cat /proc/sys/fs/file-max
ulimit -n

# 5. 查看 OpenClaw 日志
tail -100 /tmp/openclaw-$(date +%Y-%m-%d).log

# 6. 检查系统资源使用
free -h
df -h
uptime
```

**排查结果**：

```
# 进程状态
root 12345  0.0  0.0  123456  78900  ?        S    10:00   0:00  openclaw-gateway

# 日志最后几行（无异常）
[10:00:01] INFO: Gateway started on port 18789
[10:00:02] INFO: Connected to DingTalk channel
...（无新的日志输出）...

# 系统资源
free -h
              total        used        free      shared  buff/cache   available
Mem:          3.8Gi       2.1Gi       200Mi        50Mi        1.5Gi       1.2Gi

# 文件描述符
ls -la /proc/$(pgrep -f openclaw)/fd | wc -l
512
```

**关键发现**：
- 进程还在，但最后一条日志停在"正常启动"阶段，之后没有任何新日志
- 内存使用 2.1GB / 3.8GB，不是内存耗尽
- 文件描述符使用 512 个，远未达到限制
- 系统负载正常

这说明**进程启动后就完全卡住了，没有任何新的处理记录**。

### 第四步：尝试恢复服务

由于无法远程判断具体阻塞原因，最快的恢复方式是重启 VM：

```bash
# 方案1：通过虚拟化平台强制重启 VM（推荐）
# 在 PVE 控制台上操作：
# PVE245 → VM152 → 操作 → 重启

# 方案2：通过 SSH 执行系统重启（可能无效，因为 SSH 也可能受影响）
ssh root@192.168.102.1xx "reboot"

# 方案3：强制终止进程并重启（如果 SSH 可用）
ssh root@192.168.102.1xx "pkill -9 openclaw && systemctl start openclaw-gateway"
```

由于 SSH 本身还能连接，我们先尝试了方案3（杀进程并重启）。但执行 `pkill -9` 后，发现进程虽然被杀死，但 `systemctl start` 命令没有响应——说明 VM 内部的 systemd 也可能受到了某种影响。

### 第五步：通过虚拟化平台强制重启

最终，我们通过 PVE 控制台执行了强制重启：

```bash
# 在 PVE 物理机上操作
# 1. 解锁 VM（如果 VM 处于锁定状态）
qm unlock 152

# 2. 强制停止 VM
qm stop 152

# 3. 等待几秒后重新启动 VM
qm start 152
```

**操作记录**：

```bash
# 查看 VM 当前状态
qm status 152
# 输出：status = 'running' （但应用层无响应）

# 解锁 VM（防止有残留锁）
qm unlock 152

# 强制停止
qm stop 152
# 等待约10秒...

# 确认已停止
qm status 152
# 输出：status = 'stopped'

# 重新启动
qm start 152
# 等待约30秒...

# 确认已启动
qm status 152
# 输出：status = 'running'
```

### 第六步：验证恢复

VM 重启后，耐心等待约1分钟，让 OpenClaw Gateway 完全启动，然后验证：

```bash
# 测试 HTTP 健康接口
curl -s --connect-timeout 5 http://192.168.102.1xx:18789/health
# 预期输出：{"ok":true,"status":"live"}

# 测试 WebSocket 连接
curl -v --no-buffer \
  -H "Upgrade: websocket" \
  -H "Connection: Upgrade" \
  http://192.168.102.1xx:18789/ 2>&1 | head -20

# 查看 VM 内进程状态
ssh root@192.168.102.1xx "ps aux | grep openclaw"
```

**验证结果**：

```
curl http://192.168.102.1xx:18789/health
{"ok":true,"status":"live"}

WebSocket handshake: Upgrading to websocket
Connection: Upgrade
...
handshake successful
```

✅ **服务恢复，Gateway 正常工作**。

## 根因分析

### 为什么会"冻死"？

结合整个排查过程，我们推测最可能的原因是**Gateway 进程在启动后的某个初始化阶段发生了阻塞**，导致主线程卡住，HTTP 接口完全无法响应。

具体可能场景：

**场景一：外部依赖超时**

Gateway 启动时需要连接钉钉等外部服务进行认证。如果在启动阶段网络有问题或者认证服务响应慢，可能会导致启动过程卡住，且没有超时保护机制。

**场景二：线程池初始化死锁**

Gateway 内部使用了线程池处理并发请求。如果线程池初始化时发生了某种竞态条件，可能导致所有线程相互等待，形成死锁。

**场景三：虚拟化层面问题**

VM 内部的 qemu-guest-agent 未运行，说明虚拟机和宿主机之间的通信存在问题。这可能导致某些虚拟化相关的操作超时或失败。

### 为什么 SSH 还能用？

这是因为 SSH 和 Gateway 运行在不同的层面：
- SSH 是操作系统层的服务，有独立的进程（sshd）
- Gateway 是应用层服务，运行在 Node.js 运行时上

当 Gateway"冻死"时，操作系统本身不受影响，SSH 连接还能正常使用。但 Gateway 应用层已经完全无响应。

## 经验总结

### 排查要点

1. **先确认问题范围**：是网络问题、VM 问题还是应用问题？通过 ping、SSH、本地 curl 等方式逐层排查。

2. **检查进程状态和资源使用**：`ps`、`free`、`df`、`ulimit` 等命令能快速判断是否有资源耗尽。

3. **关注日志的最后一条记录**：如果日志停在某个阶段不动，往往说明问题发生在那个阶段之后。

4. **保留现场**：在重启之前，尽量记录更多的诊断信息，方便事后复盘。

### 预防措施

1. **部署 Guest Agent**：启用虚拟化平台的 qemu-guest-agent，可以更方便地进行 VM 内部诊断和远程操作。

2. **配置进程守护**：使用 systemd 的 `Restart=` 配置，让 Gateway 进程异常退出时自动重启：
   ```ini
   [Service]
   Restart=always
   RestartSec=10
   ```

3. **健康检查 + 自动恢复**：配置外部监控系统定期检测 Gateway 健康状态，检测失败时自动触发重启。

4. **启动超时配置**：在 Gateway 配置中添加启动超时和初始化超时限制，避免无限等待。

5. **日志轮转**：配置日志轮转，避免日志文件过大：
   ```bash
   /var/log/openclaw/*.log {
       daily
       rotate 7
       compress
       delaycompress
       missingok
       notifempty
       create 644 root root
   }
   ```

## 改进建议

### 短期改进

1. **启用 qemu-guest-agent**：方便后续远程诊断
2. **配置 systemd 自动重启**：添加 `Restart=always`
3. **添加外部监控**：通过 Prometheus 或 Uptime Kuma 监控 Gateway HTTP 接口

### 长期改进

1. **Gateway 健康检查增强**：在 Gateway 内部添加更详细的自检机制，发现问题时主动记录诊断信息
2. **初始化阶段超时保护**：对所有外部依赖调用添加超时限制，避免无限等待
3. **VM 高可用**：将 Gateway 部署在多台 VM 上，通过负载均衡实现高可用

## 常见问题解答

**Q1：为什么不直接重启 Gateway 进程而是重启整个 VM？**

A：因为通过 SSH 登录后发现，`systemctl restart` 命令本身也没有响应，说明 VM 内部的 systemd 可能也受到了影响。在这种情况下，重启 VM 是最可靠的恢复方式。

**Q2：如何避免 Gateway 冻死问题再次发生？**

A：核心是做好预防和监控：
1. 配置 systemd 自动重启
2. 部署外部健康检查 + 自动恢复
3. 添加 Gateway 内部超时保护机制

**Q3：Guest Agent 有什么作用，为什么重要？**

A：qemu-guest-agent 运行在 VM 内部，可以与宿主机上的 PVE 进行通信，实现以下功能：
- 优雅关闭 VM（而非强制关机）
- 冻结 VM 文件系统（便于快照）
- 获取 VM 内部 IP 地址等信息
- 远程执行命令（不依赖 SSH）

启用 Guest Agent 后，未来的排查和恢复操作会更方便。

**Q4：服务恢复了，但不知道根本原因怎么办？**

A：这种情况很常见。可以：
1. 检查日志，看是否有异常但被忽略的警告
2. 复盘当时的操作，看是否有配置变更
3. 持续监控一段时间，看是否复发
4. 做好预防措施，即使不知道根因也要防止下次再发生

**Q5：还有其他需要注意的点吗？**

A：有以下几点建议：
- 定期检查 VM 的资源使用趋势，提前发现潜在问题
- 保持 OpenClaw 和 Node.js 版本更新，获得更好的稳定性
- 重要服务的 VM 建议配置告警，资源使用异常时及时通知

## 总结

本次故障排查的核心要点：

1. **问题定位**：端口通、SSH 通、应用层不通 → 确定是 Gateway 应用层"冻死"
2. **根因推测**：最可能是 Gateway 启动阶段发生了阻塞或死锁，具体原因需要后续添加更多诊断信息才能确定
3. **恢复方案**：通过 PVE 强制重启 VM 是最可靠的恢复方式
4. **预防措施**：配置 systemd 自动重启、部署外部监控、启用 Guest Agent

服务假死是运维工作中比较棘手的问题类型，因为表面现象和实际情况往往有差距。希望本文提供的排查思路和方法，能帮助遇到类似问题的同学快速定位和解决故障。

---

*作者：小六，一个在上海努力搬砖的程序员*
