---
title: systemd-socket-proxyd 报 "Didn't get any sockets passed in"：缺失 .socket 文件的排查与修复
categories:
  - ai_tech
tags:
  - 技术
  - 运维
  - Linux
  - systemd
  - socket-proxyd
  - 问题排查
  - loopback-proxy
cover: 'https://picsum.photos/seed/tech0602/1280/720'
coverWidth: 1280
coverHeight: 720
date: 2026-06-02 21:30:00
---

## 前言

"Gateway unreachable (ECONNREFUSED 127.0.0.1:18789)"——这是今天下午我在 VPS4 上遇到的一个真实报错。

报错的现象很诡异：

- 实际的 gateway 进程**正在运行**
- HTTP 18789 端口**公网可访问**
- 但是**本机 CLI 工具**却报"连接被拒绝"

排查了大约 20 分钟，最终定位到一个**反直觉的根因**：

> `systemd-socket-proxyd` 必须和 `.socket` 文件**配套使用**才能工作。
>
> 单独配置 `.service` 文件，是不会让 socket-activated 模式生效的。

本文会从**现象**开始，逐步拆解这个坑，最后给出一键修复脚本。

## 一、问题背景

### 1.1 典型场景

我的 VPS4 部署架构是这样的：

```
公网 192.168.160.xx:18789  ←→  openclaw-gateway (绑定 0.0.0.0:18789)
                                 ↓
                           （本机 CLI 想通过 127.0.0.1:18789 访问）
```

为了让本机 CLI 工具和外部访问都能连到 gateway，我在 VPS4 上配了一个 `openclaw-loopback-proxy` 服务：

- 它监听 `127.0.0.1:18789`
- 把请求转发到 `192.168.160.xx:18789`（同机公网 IP）

这样设计的目的是：**让本机 CLI 和外部 HTTP 客户端走同一条路径，避免出现"本机能连但 curl 不行"的诡异问题。**

### 1.2 配置文件

我当时的 `openclaw-loopback-proxy.service` 文件是这样的：

```ini
[Unit]
Description=OpenClaw loopback proxy
After=network.target

[Service]
ExecStart=/lib/systemd/systemd-socket-proxyd 192.168.160.xx:18789
Restart=always
RestartSec=5
```

看起来很合理对吧？

**错就错在这里。**

### 1.3 报错现象

跑了一天之后，今天下午我注意到：

```bash
$ openclaw status
Gateway unreachable (ECONNREFUSED 127.0.0.1:18789)
```

但同时：

```bash
$ curl http://192.168.160.xx:18789/readyz
{"ready": true}
```

**公网可以，本机不行。**

而且这个状态从昨天（2026-05-30 08:27:59）就开始了。**也就是说，我部署的 loopback proxy 从一开始就没工作过。**

只是因为公网直接能访问 gateway，我平时测试都是走公网，所以一直没发现本机 CLI 用不了。

## 二、错误日志

先看一下 systemd 日志：

```bash
$ journalctl -u openclaw-loopback-proxy --no-pager -n 20
```

输出：

```
Jun 02 16:15:01 vps4 systemd[1]: openclaw-loopback-proxy.service: Scheduled restart job, restart counter is at 1234.
Jun 02 16:15:01 vps4 systemd[1]: Started OpenClaw loopback proxy.
Jun 02 16:15:01 vps4 systemd[1]: openclaw-loopback-proxy.service: Main process exited, code=exited, status=1/FAILURE
Jun 02 16:15:01 vps4 systemd[1]: openclaw-loopback-proxy.service: Failed with result 'exit-code'.
Jun 02 16:15:01 vps4 systemd-socket-proxyd[12345]: Didn't get any sockets passed in.
```

**核心报错：**

> `systemd-socket-proxyd: Didn't get any sockets passed in.`

这个报错很直白：systemd 启动 proxyd 的时候，**没有把 listening socket 传给它**。

为什么会没有？

## 三、根因分析

### 3.1 systemd 的 socket activation 机制

systemd 的 socket activation 是一种"延迟绑定"的设计模式：

1. **`.socket` 文件**负责监听端口（systemd 帮我们 listen）
2. **`.service` 文件**负责处理连接（systemd 把 fd 传给服务）
3. 客户端连接时，systemd 才启动 service，**把 listening fd 通过 `FD_LISTEN_START` 环境变量传给进程**

这个机制的优点是：

- 服务不用关心端口管理
- 服务挂了，socket 还在监听（不会丢连接）
- 多个服务可以共享一个 socket（SO_REUSEPORT）

### 3.2 我们的服务缺了什么

`systemd-socket-proxyd` 是一个**专门的 socket-activated 代理服务**——它的工作就是把 systemd 传给它的 socket 转发到后端。

**它不自己 listen 端口。**

也就是说：

| 文件 | 职责 |
|------|------|
| `openclaw-loopback-proxy.socket` | 监听 `127.0.0.1:18789` |
| `openclaw-loopback-proxy.service` | 接收 fd，启动 proxyd，转发到后端 |

**我之前的 `.service` 文件是孤立的——它自己启动 `systemd-socket-proxyd`，但没有任何 `.socket` 文件告诉 systemd "嘿，帮我 listen 一下 127.0.0.1:18789"。**

所以 systemd 启动 proxyd 的时候，**没有任何 fd 可以传给它**。

**proxyd 启动失败 → 退出码 1 → systemd 标记 failed → 5 秒后重启 → 还是失败 → 循环 → 1165 次。**

### 3.3 为什么一开始看起来"工作"

你可能会问：那为什么公网能访问，本机不能？

答案：

- **公网走的是 `openclaw-gateway` 自己的 listen**（绑定 0.0.0.0:18789），跟 loopback proxy 无关
- **本机 CLI 想走 `127.0.0.1:18789`**，必须经过 loopback proxy
- loopback proxy 从来就没工作过（因为缺 .socket 文件）
- 但平时我用 `curl http://192.168.160.xx:18789/...` 测试，看的是公网端口，**根本不会发现 loopback proxy 是挂的**

**所以这个故障从 2026-05-30 08:27:59 就开始了，潜伏了 3 天才被我发现。**

## 四、修复方案

### 4.1 正确的配置文件

需要**两个文件**配套使用：

#### `openclaw-loopback-proxy.socket`

```ini
[Unit]
Description=OpenClaw loopback proxy socket
Before=openclaw-loopback-proxy.service

[Socket]
ListenStream=127.0.0.1:18789
Accept=false

[Install]
WantedBy=sockets.target
```

关键字段：

- `ListenStream=127.0.0.1:18789`：监听本机 18789 端口（只接受 IPv4，外部访问不到）
- `Accept=false`：每个连接都启动一个新的 service 实例（proxyd 是单连接的，所以 false）
- `Before=openclaw-loopback-proxy.service`：socket 先于 service 起来

#### `openclaw-loopback-proxy.service`

```ini
[Unit]
Description=OpenClaw loopback proxy
After=network.target

[Service]
ExecStart=/lib/systemd/systemd-socket-proxyd 192.168.160.xx:18789
Restart=always
RestartSec=5
StandardInput=socket
StandardError=journal
```

**注意：socket-activated 模式下，不需要 `ExecStartPre` 之类的预启动命令。** systemd 会自动注入 fd。

### 4.2 启用与启动

```bash
# 1. 重新加载 systemd 配置
systemctl daemon-reload

# 2. 启用并启动 socket（关键！要启 .socket，不是 .service）
systemctl enable --now openclaw-loopback-proxy.socket

# 3. 验证
systemctl status openclaw-loopback-proxy.socket
systemctl status openclaw-loopback-proxy.service
```

### 4.3 验证修复

```bash
# 1. 看 socket 是否在监听
$ ss -tlnp | grep 18789
LISTEN 0  128  0.0.0.0:18789  ...  users:(("openclaw-gatewa",pid=281750,fd=7))
LISTEN 0  128  127.0.0.1:18789 ...  users:(("systemd",pid=1,fd=42))

# 127.0.0.1:18789 后面是 systemd，说明是 socket-activated 模式

# 2. 测试本机 CLI
$ curl http://127.0.0.1:18789/readyz
{"ready": true}

# 3. 测试 openclaw status
$ openclaw status
Gateway: ready, uptime 9h+
```

**修复完成。**

## 五、socket-activated vs 传统模式

如果你不想用 socket activation，也可以用传统模式（自己 listen）。

### 传统模式的服务文件

```ini
[Unit]
Description=OpenClaw loopback proxy (traditional)
After=network.target

[Service]
ExecStart=/usr/bin/socat TCP-LISTEN:18789,bind=127.0.0.1,fork TCP:192.168.160.xx:18789
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**用 socat 而不是 systemd-socket-proxyd，自己 listen 端口。**

| 模式 | 优点 | 缺点 |
|------|------|------|
| **socket-activated** | 端口管理交给 systemd，服务挂了端口还在监听 | 需要配套 .socket 文件，配置略复杂 |
| **传统模式 (socat)** | 配置简单，单独一个 .service 即可 | 服务挂了端口就没了，需要 Restart=always 才能恢复 |

**对于代理服务，强烈推荐 socket-activated 模式**——因为代理服务通常很重要，需要"端口永远在 listen"。

## 六、一键修复脚本

把整个排查 + 修复过程封装成一个脚本：

```bash
#!/bin/bash
# fix-loopback-proxy.sh
# 用途：检查并修复 openclaw-loopback-proxy 的 .socket 缺失问题

set -e

SERVICE_NAME="openclaw-loopback-proxy"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
SOCKET_FILE="/etc/systemd/system/${SERVICE_NAME}.socket"
BACKEND="${1:-192.168.160.xx:18789}"  # 默认后端地址

echo "=== 1. 检查当前状态 ==="
if systemctl is-active --quiet ${SERVICE_NAME}.service 2>/dev/null; then
  echo "服务状态: $(systemctl is-active ${SERVICE_NAME}.service)"
  echo "重启次数: $(systemctl show ${SERVICE_NAME} -p NRestarts --value)"
else
  echo "服务未运行"
fi
echo

echo "=== 2. 检查 .socket 文件 ==="
if [ -f "$SOCKET_FILE" ]; then
  echo "✅ .socket 文件存在: $SOCKET_FILE"
else
  echo "❌ .socket 文件不存在，需要创建"
  NEED_SOCKET=1
fi
echo

echo "=== 3. 检查错误日志 ==="
if journalctl -u ${SERVICE_NAME} --no-pager -n 50 2>/dev/null | grep -q "Didn't get any sockets passed in"; then
  echo "❌ 发现 'Didn't get any sockets passed in' 错误"
  NEED_SOCKET=1
else
  echo "✅ 没有 socket 传递错误"
fi
echo

if [ "$NEED_SOCKET" = "1" ]; then
  echo "=== 4. 创建 .socket 文件 ==="
  cat > "$SOCKET_FILE" <<EOF
[Unit]
Description=OpenClaw loopback proxy socket
Before=${SERVICE_NAME}.service

[Socket]
ListenStream=127.0.0.1:18789
Accept=false

[Install]
WantedBy=sockets.target
EOF
  echo "✅ 已创建: $SOCKET_FILE"
  echo

  echo "=== 5. 重新加载 systemd 配置 ==="
  systemctl daemon-reload
  echo "✅ daemon-reload 完成"
  echo

  echo "=== 6. 启动 .socket（注意是 .socket，不是 .service）==="
  systemctl enable --now ${SERVICE_NAME}.socket
  echo "✅ .socket 已启用"
  echo

  echo "=== 7. 验证 ==="
  sleep 2
  systemctl status ${SERVICE_NAME}.socket --no-pager
  echo
  if curl -s -m 3 http://127.0.0.1:18789/readyz; then
    echo "✅ 本机 loopback proxy 工作正常"
  else
    echo "❌ 本机 loopback proxy 仍有问题，请检查"
    exit 1
  fi
else
  echo "=== 4. 一切正常，无需修复 ==="
fi

echo
echo "=== 修复完成 ==="
```

**使用方法**：

```bash
chmod +x fix-loopback-proxy.sh
sudo ./fix-loopback-proxy.sh
```

## 七、Q&A

### Q1：为什么必须用 .socket + .service 配套？

**A**：这是 systemd 的设计——`.socket` 负责端口监听，`.service` 负责业务处理。`systemd-socket-proxyd` 是个特殊服务，它**只**处理"已经被 systemd 监听"的 socket。如果你只配 `.service`，proxyd 启动时拿不到任何 fd，就会立刻退出。

### Q2：我能不能用 socat 替代 systemd-socket-proxyd？

**A**：完全可以。socat 更简单，配置一个 `.service` 文件就能用。区别是：
- **socat**：自己 listen 端口，服务挂了端口就没了
- **systemd-socket-proxyd**：systemd 帮你 listen 端口，服务挂了端口还在

对于高可用代理服务，推荐 socket-activated 模式。

### Q3：怎么快速判断当前用的是 socket-activated 还是传统模式？

**A**：

```bash
# 看 18789 端口的 listen 者是 systemd 还是别的进程
ss -tlnp | grep 18789
```

- `users:(("systemd",pid=1,fd=42))` → socket-activated 模式
- `users:(("socat",pid=1234,fd=7))` → 传统模式

### Q4：能不能让公网和 127.0.0.1 同时可访问？

**A**：可以。在 `.socket` 文件里写多个 `ListenStream`：

```ini
[Socket]
ListenStream=127.0.0.1:18789
ListenStream=0.0.0.0:18789
Accept=false
```

但一般不推荐这样——公网应该直接走真正的服务（openclaw-gateway），loopback proxy 只是个"绕路方案"。

### Q5：如何避免类似问题？

**A**：

1. **写好 systemd unit 之前先看官方文档**——`man systemd-socket-proxyd` 里有明确说明
2. **部署后立刻验证**——`curl http://127.0.0.1:PORT/` 测一遍
3. **加监控**——对 NRestarts > 阈值的情况告警
4. **在 AGENTS.md 里记录**——这次事故我已经记到 `AGENTS.md` 的"已修复"清单，避免再犯

## 八、总结

`systemd-socket-proxyd` 报 `Didn't get any sockets passed in`，**100% 是缺配套 `.socket` 文件**。

核心要点：

1. ✅ **`systemd-socket-proxyd` 必须配 `.socket` 文件**——它自己不 listen
2. ✅ **`.socket` 文件要单独 `enable --now`**——启 `.service` 没用
3. ✅ **socket-activated 模式更可靠**——端口管理交给 systemd
4. ✅ **部署后必须验证本机访问**——`curl http://127.0.0.1:PORT/`
5. ✅ **对 NRestarts > 阈值要告警**——避免"循环 fail"长期无人发现

这次事故的教训：**系统"看起来工作"和"实际上健康"是两回事。** 我的 loopback proxy 静默 fail 了 3 天才被发现，就是因为我的监控只看了"公网能不能访问"，没看"本机 CLI 能不能用"。

**多视角、全链路的监控，才是真正的健康监控。**

---

*作者：小六，一个在上海努力生存的普通打工人*
