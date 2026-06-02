---
title: 记一次排查 Gateway 端口被旧进程占用的完整流程
categories:
  - ai_tech
tags:
  - 技术
  - 运维
  - 问题排查
  - Gateway
  - OpenClaw
cover: 'https://picsum.photos/seed/tech0509/1280/720'
coverWidth: 1280
coverHeight: 720
date: 2026-02-26 21:30:00
---

## 前言

在运维工作中，经常会遇到这样的问题：服务重启后无法启动，报错显示端口被占用。但当你 `netstat` 查一下，发现并没有进程在监听这个端口。这种"幽灵占用"问题排查起来往往让人摸不着头脑。

本文将记录一次完整的 Gateway 端口冲突排查过程，最终定位到是旧版本的进程没有正确退出导致的。

## 问题背景

### 故障描述

- **故障时间**：近期某日晚上
- **故障表现**：Gateway 服务无法启动，报错 `Port 18789 is already in use`
- **影响范围**：Gateway 无法提供 Web UI 服务

### 环境信息

- **操作系统**：CentOS 7
- **服务**：OpenClaw Gateway
- **端口**：18789

## 排查过程

### 第一步：确认端口占用情况

首先检查端口是否真的被占用：

```bash
# 检查端口 18789 是否被占用
ss -tlnp | grep 18789

# 输出显示
tcp    0    0 0.0.0.0:18789    0.0.0.0:*    LISTEN    2756798/openclaw-ga
```

好家伙，有进程在监听！而且 PID 是 2756798，进程名是 `openclaw-ga`。

### 第二步：检查进程详情

查看这个进程是什么：

```bash
# 查看进程详情
ps aux | grep 2756798

# 输出显示
root  2756798  0.0  0.4 1234567 89012 ?  Ss  Mar23  ?  1:30 /opt/openclaw/openclaw-gateway --config=/etc/openclaw/config.yml
```

问题来了：进程名显示是 `openclaw-ga`，而且从 3 月 23 号就在运行了。这说明什么？

**这是一个旧版本的 Gateway 进程，没有正确退出。**

### 第三步：检查当前服务状态

查看当前的 Gateway 服务状态：

```bash
# 查看 systemd 服务状态
systemctl status openclaw-gateway

# 输出显示
● openclaw-gateway.service - OpenClaw Gateway
   Loaded: loaded (/etc/systemd/system/openclaw-gateway.service; enabled)
   Active: inactive (dead) since Sun 20:00:00 CST 2026; 30min ago
```

服务状态是 `inactive (dead)`，说明 systemd 认为服务没有在运行。但端口却被占用了，说明有一个进程在跑，但不是通过 systemd 启动的。

### 第四步：分析根因

这种情况通常是因为：

1. **手动启动的进程**：有人直接运行了 `./openclaw-gateway`，没有通过 systemd
2. **升级时的遗留**：升级过程中旧的进程没有完全退出
3. **脚本残留**：某个启动脚本里既有 systemd 启动又有直接运行

对于我们的场景，最可能的原因是：**之前手动启动了一个 Gateway，后来用 systemd 重启服务时，旧的进程没有被清理**。

### 第五步：处理旧进程

既然知道是旧进程在占用端口，那就把它杀掉：

```bash
# 先确认这个进程是否可以安全杀掉
ps -p 2756798 -o pid,ppid,etime,cmd

# 如果确认是旧进程，杀掉它
kill 2756798

# 等待几秒，确认进程已退出
sleep 2
ss -tlnp | grep 18789
```

### 第六步：启动服务

旧进程杀掉后，启动服务：

```bash
# 通过 systemd 启动服务
systemctl start openclaw-gateway

# 检查服务状态
systemctl status openclaw-gateway

# 验证端口监听
ss -tlnp | grep 18789
```

### 第七步：设置开机自启

为了防止这个问题再次发生，确保服务是 enabled 状态：

```bash
# 确保服务开机自启
systemctl enable openclaw-gateway

# 查看当前是否 enabled
systemctl is-enabled openclaw-gateway
```

## 根因分析

### 问题根因

这次问题的根本原因是：**旧版本进程没有正确退出，占用了新版本需要使用的端口**。

具体情况可能是：

1. 某次升级时，旧的 Gateway 进程还在运行
2. 新版本的启动脚本没有检查并清理旧进程
3. 直接 `./openclaw-gateway` 启动的进程没有被 systemd 管理

### 为什么之前没有发现

这个问题之前没有暴露出来，可能是因为：

1. 机器很久没有重启过
2. 升级后旧进程和新进程恰好用了不同的配置文件端口
3. systemd 服务的启动顺序问题

## 一键解决方案

如果你遇到了类似的"端口被幽灵进程占用"问题，可以使用以下脚本快速排查和解决：

```bash
#!/bin/bash

# 端口冲突快速排查脚本
PORT=${1:-18789}
SERVICE_NAME="openclaw-gateway"

echo "=== 端口 ${PORT} 冲突排查 ==="
echo ""

# 1. 检查端口占用
echo "1. 检查端口占用情况..."
ss -tlnp | grep ":${PORT} "
echo ""

# 2. 检查进程详情
echo "2. 检查占用进程的详细信息..."
PID=$(ss -tlnp | grep ":${PORT} " | grep -oP 'pid=\K\d+')
if [ -n "$PID" ]; then
    ps -p $PID -o pid,ppid,etime,cmd
    echo ""
    echo "进程运行时间: $(ps -p $PID -o etime --no-headers)"
else
    echo "端口未被占用"
fi
echo ""

# 3. 检查 systemd 服务状态
echo "3. 检查 systemd 服务状态..."
systemctl status $SERVICE_NAME --no-pager
echo ""

# 4. 提供解决方案
echo "=== 解决方案 ==="
if [ -n "$PID" ]; then
    echo "发现旧进程 PID=$PID 占用了端口"
    echo ""
    echo "执行以下命令清理旧进程并重启服务:"
    echo "  kill $PID"
    echo "  sleep 2"
    echo "  systemctl restart $SERVICE_NAME"
    echo ""
    echo "是否现在执行? (y/n)"
    read -r answer
    if [ "$answer" = "y" ]; then
        kill $PID
        sleep 2
        systemctl restart $SERVICE_NAME
        echo "服务已重启"
        systemctl status $SERVICE_NAME --no-pager
    fi
else
    echo "端口未被占用，服务可能正常"
fi
```

## 预防措施

### 1. 确保服务通过 systemd 管理

所有 Gateway 服务都应该通过 systemd 管理，禁止直接运行：

```bash
# 禁止直接运行的方式
# 使用 systemctl start 而不是 ./openclaw-gateway
```

### 2. 升级脚本中加入进程检查

在升级脚本中加入旧进程检查和清理逻辑：

```bash
#!/bin/bash

# 升级脚本示例

# 1. 检查是否有旧进程在运行
OLD_PID=$(ps aux | grep 'openclaw-gateway' | grep -v grep | awk '{print $2}')
if [ -n "$OLD_PID" ]; then
    echo "发现旧进程 PID=$OLD_PID，正在停止..."
    kill $OLD_PID
    sleep 3
fi

# 2. 执行升级
echo "开始升级..."

# 3. 启动新服务
systemctl restart openclaw-gateway
```

### 3. 使用 pid 文件

让服务使用 pid 文件，方便检查和清理：

```bash
# 在启动命令中加入 --pidfile 参数
/opt/openclaw/openclaw-gateway --config=/etc/openclaw/config.yml --pidfile=/var/run/openclaw-gateway.pid
```

### 4. 定期检查服务状态

配置监控，定期检查服务状态和端口占用情况：

```bash
# 添加到 crontab
*/5 * * * * /opt/scripts/check-gateway.sh
```

## 常见问题解答

**Q：端口显示被占用，但找不到进程怎么办？**

A：可能是僵尸进程。尝试使用 `ps aux | grep -v grep | grep 18789` 确认，或者重启服务器（谨慎操作）。

**Q：杀掉进程后服务还是无法启动怎么办？**

A：检查一下是否有残留的 socket 文件：`ls -la /var/run/openclaw-gateway.*`。如果有，删除后再试。

**Q：如何避免这种情况再次发生？**

A：确保所有启动都通过 systemd，禁止手动直接运行服务。升级时先停止旧服务再启动新服务。

**Q：能否自动检测并清理旧进程？**

A：可以。创建一个定时任务，检测端口占用情况，如果发现非 systemd 管理的进程，自动清理。

**Q：服务显示 active，但端口没监听是怎么回事？**

A：可能是服务启动失败。可以查看日志：`journalctl -u openclaw-gateway -n 50`，根据错误信息进一步排查。

## 经验总结

1. **端口被占用不一定是服务在跑**：可能是旧进程残留
2. **systemd 状态和实际进程状态可能不一致**：需要交叉验证
3. **升级时要先清理旧进程**：不能假设旧进程会自动退出
4. **所有服务都应该通过 systemd 管理**：避免"幽灵进程"

## 延伸阅读

- [systemd 服务管理最佳实践](/docs/systemd-management)
- [端口冲突排查指南](/docs/port-conflict-troubleshooting)
- [OpenClaw Gateway 官方文档](/docs/openclaw-gateway)

## 结语

这次端口冲突问题的排查过程虽然不复杂，但很有代表性。很多时候，问题的根因并不是"服务挂了"，而是"旧的东西没有清理干净"。

在运维工作中，我们需要养成一个习惯：**每次重启/升级时，确保旧的进程/配置已经被完全清理**。只有这样，才能避免类似的"幽灵占用"问题。

希望这篇文章能帮到你。如果有问题，欢迎在评论区讨论。

---

*作者：小六，一个在上海努力搬砖的程序员*
