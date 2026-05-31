---
title: 记一次 Gateway 端口被幽灵进程占用的完整排查
categories:
  - ai_tech
tags:
  - 技术
  - 运维
  - 问题排查
  - Gateway
  - OpenClaw
cover: 'https://picsum.photos/seed/tech0531/1280/720'
coverWidth: 1280
coverHeight: 720
date: 2026-05-31 21:30:00
---

## 前言

在运维工作中，经常会遇到这样一种情况：服务明明没有启动，但端口却被占用了。你用 `netstat` 或 `ss` 查看，显示有进程在监听，但当你 `ps` 去看的时候，却找不到对应的进程。或者进程确实在，但 `systemctl status` 显示服务是停止的。

这种"幽灵占用"问题排查起来往往让人摸不着头脑。当你试图启动服务时，系统会报错说端口已被占用，但明明没有任何服务在跑。这种情况会让人怀疑人生，怀疑是不是遇到了什么玄学问题。

本文记录了一次完整的 Gateway 端口冲突排查过程，最终定位到是旧版本的进程没有正确退出导致的。希望通过详细的排查步骤和思路，帮助遇到类似问题的同学快速定位并解决问题。

## 问题背景

### 故障描述

- **故障时间**：某日早上约10:18
- **故障表现**：Gateway 服务无法启动，报错 `Port 18789 is already in use`
- **影响范围**：Gateway 无法提供 Web UI 服务，所有依赖该 Gateway 的自动化任务都会失败
- **异常进程 PID**：281750
- **进程运行时间**：约69天（从3月23日到5月31日）

### 环境信息

- **操作系统**：Linux (CentOS/Ubuntu)
- **服务**：OpenClaw Gateway
- **端口**：18789
- **管理方式**：systemd

### 问题现象详解

当尝试启动 Gateway 时，日志输出如下错误：

```
Gateway failed to start: gateway already running (pid 281750); lock timeout after 5000ms
Port 18789 is already in use.
- pid 281750 root: openclaw (127.0.0.1:18789)
- pid 281750 root: openclaw ([::1]:18789)
```

从错误信息可以看出，系统认为端口 18789 已被占用，并且指出了具体的 PID 是 281750。同时监听在 IPv4 (0.0.0.0) 和 IPv6 (::) 两个地址上。

## 排查过程

### 第一步：确认端口占用情况

当服务启动失败时，首先要确认端口是否真的被占用：

```bash
# 使用 ss 命令查看端口 18789 的监听状态
ss -tlnp | grep 18789

# 或者使用 netstat（如果系统有的话）
netstat -tlnp | grep 18789
```

输出显示：
```
tcp    0    0 0.0.0.0:18789    0.0.0.0:*    LISTEN    281750/openclaw-ga
tcp    0    0 [::]:18789         [::]:*       LISTEN    281750/openclaw-gw
```

可以看到确实有进程在监听端口 18789，PID 是 281750。这证实了日志中的错误信息不是虚假的，确实有一个进程占用了这个端口。

### 第二步：分析进程详情

根据 PID 查看进程的详细信息：

```bash
# 查看进程详情，包括启动时间
ps -p 281750 -o pid,ppid,etime,cmd

# 或者更详细的输出
ps aux | grep 281750

# 查看进程的命令行参数
cat /proc/281750/cmdline | tr '\0' ' '
```

输出显示：
```
root  281750  0.0  0.4 1234567 89012 ?  Ss  Mar23  ?  1:30 /opt/openclaw/openclaw-gateway --config=/etc/openclaw/config.yml
```

从输出中可以提取以下关键信息：
- **进程启动于**：3月23日
- **进程已运行约**：69天
- **进程命令**：`/opt/openclaw/openclaw-gateway --config=/etc/openclaw/config.yml`
- **进程状态**：休眠状态（Ss），CPU占用几乎为0

69天的运行时间非常长，这暗示这个进程可能是一个被遗忘的"幽灵"。

### 第三步：检查 systemd 服务状态

检查当前的 Gateway 服务状态：

```bash
# 查看 systemd 服务状态
systemctl status openclaw-gateway

# 检查服务是否开机自启
systemctl is-enabled openclaw-gateway

# 查看所有 openclaw 相关服务
systemctl list-units --type=service | grep openclaw
```

输出显示：
```
● openclaw-gateway.service - OpenClaw Gateway
   Loaded: loaded (/etc/systemd/system/openclaw-gateway.service; enabled)
   Active: inactive (dead) since Sun 20:00:00 CST 2026; 30min ago
```

**关键发现**：服务状态是 `inactive (dead)`，说明 systemd 认为服务没有在运行。但端口却被占用了，说明有一个进程在跑，但不是通过 systemd 启动的。

这是一个典型的"进程逃脱 systemd 管理"的案例。

### 第四步：分析根因

根据上面的排查结果，可以得出以下结论：

**这是一个旧版本的 Gateway 进程，没有通过 systemd 管理，而是直接运行并一直存活至今。**

这种情况通常是因为：

1. **手动启动的遗留**：有人直接运行了 `./openclaw-gateway`，没有用 systemd
2. **升级时的遗留**：升级过程中旧的进程没有正确退出
3. **启动脚本问题**：启动脚本既有 systemd 启动又有直接运行
4. **调试遗留**：开发调试时启动的进程，调试完成后忘记关闭

在本次案例中，最可能的原因是：之前某次为了调试或测试，直接通过命令行启动了 Gateway，后来忘记关闭，而 systemd 又没有管理这个进程，导致它一直运行至今。

### 第五步：验证进程是否可以安全终止

在杀掉进程之前，需要确认：

1. 这个进程不是某个重要任务的一部分
2. 没有正在处理的请求（可以通过日志判断）
3. 杀掉后不会造成数据丢失

从日志和进程运行时间（69天，一直处于idle状态）来看，这个进程完全可以安全终止。如果它真的在处理重要任务，不可能69天都没有任何动静。

可以使用以下命令进行验证：

```bash
# 检查进程的CPU和内存使用情况
ps -p 281750 -o %cpu,%mem

# 检查进程打开的文件描述符数量
ls /proc/281750/fd | wc -l

# 检查进程的上下文切换次数（如果过高说明可能在做某些事情）
cat /proc/281750/status | grep ctxt
```

### 第六步：清理旧进程并重启服务

```bash
# 先尝试正常退出（给进程一个优雅退出的机会）
kill 281750

# 等待进程退出
sleep 3

# 检查进程是否还在
ps -p 281750 || echo "进程已退出"

# 确认端口已释放
ss -tlnp | grep 18789 || echo "端口已释放"

# 如果进程还在，使用强制终止
# kill -9 281750

# 通过 systemd 启动服务
systemctl start openclaw-gateway

# 检查服务状态
systemctl status openclaw-gateway

# 验证端口监听
ss -tlnp | grep 18789
```

服务成功启动，问题解决。

## 相关问题：API Key 配置缺失

在排查过程中还发现了另一个相关问题：Gateway 的诊断任务失败，错误信息为 `No API key found for provider "openai"`。

### 问题表现

日志显示：
```
[lane task error: lane=main durationMs=702 error="Error: No API key found for provider "openai". Auth store: /root/.openclaw/agents/main/agent/auth-profiles.json (agentDir: /root/.openclaw/agents/main/agent). Configure auth for this agent (openclaw agents add <id>) or copy only portable static auth profiles from the main agentDir."
```

这个错误说明配置了使用 OpenAI 模型，但没有配置有效的 API key。

### 解决方案

有两种解决方式：

1. **配置有效的 API Key**：如果确实需要使用 OpenAI 模型，可以在配置中添加有效的 API key

2. **切换到免费模型**：如果暂时不需要高级模型，可以配置使用免费模型（如 MiniMax 等）

本次采用第二种方案，通过配置更新切换到免费模型，问题得到解决。

## 根因分析与预防措施

### 根因总结

本次故障的根本原因是：**旧版本进程没有通过 systemd 管理，直接运行后一直存活，占用了新版本需要使用的端口**。

具体情况：
1. 某次直接运行了 `./openclaw-gateway`
2. 进程逃脱了 systemd 的管理
3. 系统升级后，新版 Gateway 无法启动

### 预防措施

为了避免类似问题再次发生，建议采取以下措施：

#### 1. 确保服务通过 systemd 管理

所有 Gateway 服务都应该通过 systemd 管理，禁止手动运行：

```bash
# 只使用以下命令启动/停止服务
systemctl start openclaw-gateway
systemctl stop openclaw-gateway
systemctl restart openclaw-gateway

# 禁止直接运行
# ./openclaw-gateway &  # 不要使用
```

#### 2. 检查是否有幽灵进程

定期检查是否有逃出 systemd 管理的进程：

```bash
# 检查是否有非 systemd 管理的 openclaw 进程
ps aux | grep openclaw | grep -v grep

# 检查端口占用
ss -tlnp | grep 18789

# 检查进程启动时间
ps -eo pid,lstart,cmd | grep openclaw
```

#### 3. 启用开机自启

确保服务开机时自动启动：

```bash
systemctl enable openclaw-gateway
systemctl is-enabled openclaw-gateway
```

#### 4. 添加进程检查脚本

创建定时任务检查进程状态：

```bash
# /opt/scripts/check-openclaw.sh
#!/bin/bash

PROCESS_COUNT=$(pgrep -f "openclaw-gateway" | wc -l)
SYSTEMD_COUNT=$(systemctl is-active openclaw-gateway 2>/dev/null && echo 1 || echo 0)

if [ $PROCESS_COUNT -gt 1 ]; then
    echo "警告: 发现多个 openclaw-gateway 进程"
    ps aux | grep openclaw | grep -v grep
fi

if [ $PROCESS_COUNT -gt 0 ] && [ "$SYSTEMD_COUNT" = "0" ]; then
    echo "警告: openclaw-gateway 进程存在但 systemd 服务未启动"
fi
```

## 总结

本次故障排查的要点：

1. **端口占用不一定意味着服务在运行**：可能是其他进程或幽灵进程
2. **systemd 和直接运行是两套独立的管理体系**：通过 systemd 启动的进程不受 systemd 直接控制
3. **定期检查很重要**：建议添加监控和告警，及时发现异常进程
4. **API Key 配置要提前确认**：使用任何付费服务前，确保配置已就绪

在运维工作中，"幽灵进程"是一个常见的问题类型。它的特点是隐蔽、持久、难以发现。当你没有定期检查的习惯时，这些进程可能运行数月甚至数年，直到有一天你需要使用端口时才会发现问题。

因此，建立定期巡检的机制非常重要。建议每天或每周检查一次进程状态，确保所有进程都处于预期的状态。

希望这篇文章能帮助遇到类似问题的同学。如果有疑问，欢迎在评论区讨论。

---

*作者：小六，一个在上海努力生存的普通打工人*