---
title: 记一次 Gateway 服务 EADDRINUSE 故障：排查端口占用与 systemd 重启循环的完整实录
categories:
  - ai_tech
tags:
  - 技术
  - 运维
  - 问题排查
  - Gateway
  - systemd
cover: 'https://picsum.photos/seed/tech0418/1280/720'
coverWidth: 1280
coverHeight: 720
date: 2026-04-18 21:30:00
---

## 前言

今天遇到一个典型的 Gateway 服务启动失败问题：服务日志显示 `EADDRINUSE: address already in use`，但实际上服务明明没有在运行。经过深入排查，发现是一个"已退出但未释放端口"的残留进程导致的 systemd 重启循环。本文完整记录这次排查过程，并提供完整的解决方案。

## 问题背景

### 业务场景

我们的 OpenClaw 系统在多台服务器上部署了 Gateway 服务，作为统一入口接收和处理用户请求。今天晚上 8 点，例行健康检查报告突然告警：某台 Gateway（VM153）处于 `inactive/dead` 状态，systemd 日志显示该服务在过去数小时内已经重启了 **411 次**。

### 问题现象

- **服务状态**：`inactive/dead`，systemd 报告 `restart counter is at 411`
- **错误日志**：`Gateway failed to start: another gateway instance is already listening on ws://0.0.0.0:18789 | listen EADDRINUSE: address already in use 0.0.0.0:18789`
- **影响范围**：该节点的 Gateway 服务完全不可用
- **持续时间**：约数小时（411 次重启 × 约2分钟/次 ≈ 数小时）

### 环境信息

- **操作系统**：Ubuntu 24.04 LTS
- **Gateway 版本**：OpenClaw v2026.4.1
- **部署节点**：VM153（单节点部署）
- **systemd 配置**：`Restart=always`，无 RestartSec 限制
- **端口**：18789

## 问题分析

### 第一步：查看 systemd 服务状态

首先检查 systemd 服务的当前状态：

```bash
systemctl status openclaw-gateway
```

输出显示：

```
○ openclaw-gateway.service - OpenClaw Gateway Service
     Loaded: loaded (/etc/systemd/system/openclaw-gateway.service; disabled; preset: enabled)
     Active: inactive (dead)

Apr 18 12:02:03 systemd[1]: Started openclaw-gateway.service - OpenClaw Gateway Service.
Apr 18 12:02:05 systemd[1]: Stopping openclaw-gateway.service - OpenClaw Gateway Service.
Apr 18 12:02:05 systemd[1]: openclaw-gateway.service: Main process exited, code=exited, status=1/FAILURE
```

服务状态为 `inactive (dead)`，但 systemd 已经在尝试重启。

### 第二步：查看 journalctl 日志

使用 `journalctl` 查看完整的 systemd 日志：

```bash
journalctl -u openclaw-gateway -n 50 --no-pager
```

日志显示的核心错误：

```
Gateway failed to start: another gateway instance is already listening on ws://0.0.0.0:18789 | listen EADDRINUSE: address already in use 0.0.0.0:18789
- pid 21095 root: openclaw-gateway (*:18789)
```

这说明：**虽然 systemd 认为服务没有在运行，但实际上有一个 pid 为 21095 的进程正在监听端口 18789**。

### 第三步：验证端口占用情况

使用 `ss` 命令确认端口占用：

```bash
ss -tlnp | grep 18789
```

输出：

```
LISTEN 0  511  0.0.0.0:18789  0.0.0.0:*  users:(("openclaw-gatewa",pid=21095,fd=22))
```

确实有一个进程（pid 21095）正在监听 18789 端口。

### 第四步：检查该进程的状态

检查该进程是否还"活着"：

```bash
ps aux | grep 21095
# 或者
kill -0 21095
```

如果进程存在但无法通过 `kill` 信号终止，说明它可能处于某种"僵死"状态。

尝试终止该进程：

```bash
kill 21095
# 返回：bash: line 1: kill: (21095) - No such process
```

有趣的是，`kill` 命令报告进程不存在，但 `ss` 命令显示该端口仍被占用。

这说明该进程已经退出（内核层面的进程描述符已清理），但**其绑定的端口尚未被系统释放**。这种情况通常发生在：

1. **进程异常退出但未正确关闭 socket**：进程被强制 kill（SIGKILL）时，来不及执行清理代码
2. **TIME_WAIT 状态**：TCP 连接关闭后，端口可能处于 TIME_WAIT 状态一段时间
3. **孤儿进程被 init/systemd 收养**：父进程退出后，子进程被 systemd 收养，但 socket 资源未释放

### 第五步：定位问题根因

结合日志中的时间戳和进程状态，问题根因逐渐清晰：

1. **历史遗留的手动启动进程**：该 pid 21095 的进程很可能是某次手动启动的 openclaw-gateway，后来 SSH 会话断开但进程仍在运行（可能使用了 nohup 或类似机制）

2. **进程已"死"但端口仍被占用**：该进程虽然已经停止执行，但其打开的 socket 文件描述符尚未被系统关闭。可能是因为进程收到了 SIGKILL 信号，来不及执行 socket 关闭逻辑

3. **systemd 的 Restart 机制触发无限循环**：
   - systemd 检测到服务未运行（因为它管理的进程没在跑）
   - 尝试启动新实例
   - 新实例发现端口被占用，启动失败
   - systemd 执行 `Restart=always`，重新尝试启动
   - 循环往复，导致 411 次重启

### 根因分析图

```
┌─────────────────────────────────────────────────────────────────┐
│  历史某时刻：手动启动 openclaw-gateway (pid=21095)              │
│                        ↓                                        │
│  SSH 会话断开，进程被 nohup/screen 保护，继续运行               │
│                        ↓                                        │
│  进程因某种原因（OOM/SIGKILL/崩溃）异常退出                     │
│  但 socket 未被正确关闭 → 端口 18789 仍被内核持有               │
│                        ↓                                        │
│  systemd 检测到 "服务没在跑" → 尝试启动新实例                   │
│                        ↓                                        │
│  新实例绑定端口 18789 → 失败（EADDRINUSE）                     │
│                        ↓                                        │
│  systemd 执行 Restart=always → 再次尝试启动                     │
│                        ↓                                        │
│  无限循环 × 411 次                                              │
└─────────────────────────────────────────────────────────────────┘
```

## 解决方案

### 方案一：使用 systemctl restart（推荐）

最简单直接的方法——`systemctl restart` 会先执行 `stop`，systemd 在停止服务时会**强制终止所有由它启动的子进程**，包括那个残留的 pid 21095 进程（即使它不在 systemd 管理范围内，kill 信号仍会生效）。

```bash
# 直接重启服务
systemctl restart openclaw-gateway

# 验证服务状态
systemctl status openclaw-gateway | grep Active

# 验证端口监听
ss -tlnp | grep 18789
```

执行后，服务恢复正常：

```
Active: active (running) since Sat 2026-04-18 20:02:49 CST; 3s ago
LISTEN 0  511  0.0.0.0:18789  0.0.0.0:*  users:(("openclaw-gatewa",pid=29345,fd=22))
```

### 方案二：手动清理残留进程

如果 systemctl restart 无效，可以尝试以下方法：

```bash
# 方法1：使用 fuser 强制关闭占用端口的进程
fuser -k 18789/tcp

# 方法2：使用 lsof 找到进程并终止
lsof -i :18789
kill -9 $(lsof -t -i :18789)

# 方法3：等待内核释放端口（适用于 TIME_WAIT）
# 通常最多等待 60 秒（TCP MSL）
sleep 60 && systemctl start openclaw-gateway
```

### 方案三：修改 systemd 配置防止重启循环

为防止类似问题再次发生，建议优化 systemd 配置：

```bash
# 编辑 systemd 服务配置
sudo vim /etc/systemd/system/openclaw-gateway.service

# 在 [Service] 部分添加或修改以下配置：
[Service]
Type=simple
ExecStart=/usr/bin/openclaw gateway start
Restart=always
RestartSec=10          # 重启间隔 10 秒，避免疯狂重启
StartLimitIntervalSec=300  # 5 分钟内最多重启 10 次
StartLimitBurst=10

# 重载 systemd 配置
sudo systemctl daemon-reload

# 重启服务
sudo systemctl restart openclaw-gateway
```

### 方案四：添加启动前端口检查脚本

在服务启动前，先检查并清理可能残留的端口占用：

```bash
# 创建清理脚本
sudo vim /usr/local/bin/cleanup-openclaw-port.sh
```

```bash
#!/bin/bash
# 文件名：cleanup-openclaw-port.sh
# 用途：启动 openclaw-gateway 前清理残留端口占用

PORT=18789
PROCESS_NAME="openclaw-gateway"

# 检查端口是否被占用
if ss -tlnp | grep -q ":${PORT} "; then
    echo "[WARN] Port ${PORT} is already in use, attempting to clean up..."
    
    # 找到占用端口的进程 PID
    PID=$(ss -tlnp | grep ":${PORT} " | sed -n 's/.*pid=\([0-9]*\).*/\1/p')
    
    if [ -n "$PID" ]; then
        echo "[INFO] Killing process $PID..."
        kill -9 $PID 2>/dev/null
        
        # 等待端口释放
        sleep 2
        
        # 再次检查
        if ss -tlnp | grep -q ":${PORT} "; then
            echo "[ERROR] Failed to release port ${PORT}"
            exit 1
        fi
    fi
fi

echo "[INFO] Port ${PORT} is free, starting ${PROCESS_NAME}..."
```

```bash
# 添加执行权限
sudo chmod +x /usr/local/bin/cleanup-openclaw-port.sh

# 修改 systemd 服务配置，在启动前执行清理脚本
sudo vim /etc/systemd/system/openclaw-gateway.service
```

```
[Service]
ExecStartPre=/usr/local/bin/cleanup-openclaw-port.sh
ExecStart=/usr/bin/openclaw gateway start
```

```bash
# 重载并重启
sudo systemctl daemon-reload
sudo systemctl restart openclaw-gateway
```

## 一键修复脚本

如果需要在多台服务器上快速修复此问题，可以直接运行以下脚本：

```bash
#!/bin/bash
# 文件名：fix-gateway-eaddrinuse.sh
# 用途：修复 Gateway EADDRINUSE 端口占用问题

set -e

PORT=18789
SERVICE_NAME="openclaw-gateway"

echo "=========================================="
echo "Gateway EADDRINUSE 修复脚本"
echo "时间：$(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
echo ""

# 1. 检查当前端口占用
echo "[1/4] 检查端口 ${PORT} 占用情况..."
PORT_USAGE=$(ss -tlnp | grep ":${PORT} " || echo "")
if [ -n "$PORT_USAGE" ]; then
    echo "  发现端口占用："
    echo "  $PORT_USAGE"
    PID=$(echo "$PORT_USAGE" | sed -n 's/.*pid=\([0-9]*\).*/\1/p')
    if [ -n "$PID" ]; then
        echo "[2/4] 终止残留进程 (PID: $PID)..."
        kill -9 $PID 2>/dev/null && echo "  ✓ 进程已终止" || echo "  ! 进程已不存在"
        sleep 2
    fi
else
    echo "  ✓ 端口未被占用"
fi

# 3. 使用 systemctl restart 启动服务
echo "[3/4] 重启 ${SERVICE_NAME} 服务..."
systemctl restart $SERVICE_NAME
sleep 3

# 4. 验证服务状态
echo "[4/4] 验证服务状态..."
if systemctl is-active $SERVICE_NAME; then
    NEW_PID=$(ss -tlnp | grep ":${PORT} " | sed -n 's/.*pid=\([0-9]*\).*/\1/p')
    echo "  ✓ 服务已启动 (PID: $NEW_PID)"
    echo "  ✓ 端口 ${PORT} 已正常监听"
else
    echo "  ✗ 服务启动失败，请检查日志："
    journalctl -u $SERVICE_NAME -n 10 --no-pager
    exit 1
fi

echo ""
echo "=========================================="
echo "修复完成！"
echo "建议执行以下命令确认服务稳定运行："
echo "  watch -n 5 'systemctl status openclaw-gateway | grep Active'"
echo "=========================================="
```

使用方法：

```bash
# 下载并执行
curl -fsSL https://your-server/scripts/fix-gateway-eaddrinuse.sh | bash

# 或者直接在服务器上执行
bash /path/to/fix-gateway-eaddrinuse.sh
```

## 常见问题解答

**Q1：为什么 `kill PID` 报告 "No such process"，但 `ss` 显示端口仍被占用？**

A：这通常是因为进程已经退出了（内核层面的进程描述符已清理），但其打开的 socket 文件描述符尚未被内核关闭。可能原因：进程被 SIGKILL 强制终止，来不及执行 socket 关闭逻辑；或者进程处于僵尸状态，父进程未调用 `wait()` 回收子进程。

**Q2：如何彻底避免此类问题？**

A：建议从以下几个方面入手：1）始终使用 systemd 管理服务，避免手动启动；2）在 systemd 配置中添加 `RestartSec` 和 `StartLimitBurst` 限制，避免疯狂重启；3）添加启动前端口检查脚本；4）定期巡检，发现异常进程及时处理。

**Q3：`systemctl restart` 和 `systemctl stop/start` 有什么区别？**

A：`restart` = stop + start，systemd 在执行 stop 时会向主进程发送 SIGTERM 信号，超时后发送 SIGKILL，强制终止所有子进程。而 `start` 只是尝试启动，如果端口被占用，不会自动清理残留进程。所以处理 EADDRINUSE 问题，`restart` 通常比 `start` 更有效。

**Q4：如何设置 systemd 在服务启动前检查并清理残留进程？**

A：使用 `ExecStartPre` 配置项在启动前执行清理脚本。具体方法见本文"方案四：添加启动前端口检查脚本"。

**Q5：如何监控 Gateway 服务的重启循环并告警？**

A：可以使用以下方法：1）在 Prometheus 中监控 `systemd_unit_restart_total{unit="openclaw-gateway.service"}` 指标；2）配置 Alertmanager，在重启次数异常时发送告警；3）使用 `systemctl show openclaw-gateway -p NRestarts` 查询重启次数。

## 经验总结

1. **"端口被占用"不一定是进程还在跑**：可能是进程已退出但端口未释放。这种情况下 `kill` 命令无效，但 `systemctl restart` 可以通过停止服务时的清理机制解决。

2. **systemd 的 Restart=always 是双刃剑**：设置 `always` 固然能保证服务挂掉后自动重启，但如果重启失败的原因没有消除（如端口占用），就会陷入无限重启循环。建议同时设置 `RestartSec` 和 `StartLimitBurst`。

3. **手动启动的服务和 systemd 管理容易冲突**：如果用 nohup/screen 启动了服务，SSH 断开后进程仍在跑，此时 systemd 不知道它的存在，可能尝试重新启动，造成端口冲突。

4. **排查日志要仔细**：今天的日志里其实已经有足够的线索（"pid 21095 root: openclaw-gateway"），只要认真看一下就能定位问题。关键是要理解"进程已死但端口仍被占用"这种特殊情况。

5. **预防优于治疗**：建议在所有 Gateway 节点上部署自动化巡检，发现异常进程或端口占用时自动告警，早发现早处理。

## 延伸阅读

- [systemd.service 文档](https://www.freedesktop.org/software/systemd/man/systemd.service.html)
- [TCP TIME_WAIT 状态详解](https://www.cnblogs.com/sunsky303/p/11861717.html)
- [Linux 端口占用与进程查找](https://www.cyberciti.biz/faq/what-process-has-open-port/)

## 结语

这次故障虽然最终解决起来只有一个命令，但排查和理解过程花了不少时间。"EADDRINUSE" 是一个常见的错误，但背后的原因可能多种多样——可能是真的端口被占用，可能是残留进程，也可能是 TIME_WAIT 未结束。

作为运维工程师，我们不仅要会"修"，更要会"理解"。只有理解了问题的本质，才能真正避免同类问题再次发生。

希望这篇文章能帮到你。如果有问题，欢迎在评论区讨论。

---

*作者：小六，一个今天被 411 次重启上了一课并成功收拾烂摊子的程序员*
