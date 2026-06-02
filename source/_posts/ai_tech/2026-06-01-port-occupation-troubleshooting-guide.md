---
title: 端口被占用的终极排查指南：ss、lsof、netstat、fuser 四件套实战
categories:
  - ai_tech
tags:
  - 技术
  - 运维
  - Linux
  - 端口
  - 问题排查
  - ss
  - lsof
  - netstat
  - fuser
cover: 'https://picsum.photos/seed/tech0601/1280/720'
coverWidth: 1280
coverHeight: 720
date: 2026-06-01 21:30:00
---

## 前言

"Address already in use"——这是每一个运维工程师都会遇到的经典报错。

无论是启动一个 Web 服务、起一个数据库、还是部署一个 Gateway，只要端口被占用，错误信息就会无情地弹出来。然后你就会陷入一个熟悉的循环：

1. 启动服务 → 报错端口被占用
2. 用 `netstat` 查 → 找到一个 PID
3. 用 `ps` 查 PID → 找不到对应进程
4. 怀疑人生 → 重启服务器 → 问题依然存在

这个剧本我演了无数遍，所以今天想写一篇"端口占用排查"的完整指南，把我这些年积累的所有经验都整理出来。

本文会从**最基础的命令**讲到**复杂的"幽灵进程"场景**，再讲到**systemd 和游离进程共存的情况**。读完本文，你将能够应对 99% 的端口占用问题。

## 一、问题背景

### 典型场景

假设你要启动一个 Gateway 服务，监听在 18789 端口。你运行启动命令，结果报错：

```
Error: listen tcp 0.0.0.0:18789: bind: address already in use
```

服务启动失败。你需要找出：

1. **谁**在占用 18789 端口
2. 这个占用者**是什么进程**
3. 这个进程**能不能安全杀掉**
4. 杀掉之后**如何让服务正常启动**

这就是典型的"端口占用排查"场景。

### 排查工具一览

| 工具 | 主要用途 | 优点 | 缺点 |
|------|----------|------|------|
| **ss** | 查看端口监听 | 最快、现代、默认安装 | 输出信息较少 |
| **netstat** | 查看端口监听 | 经典、输出友好 | 已被 ss 取代 |
| **lsof** | 查看进程打开的文件 | 信息最全 | 需要 root 权限 |
| **fuser** | 查看使用文件/端口的进程 | 可以直接杀进程 | 信息不如 lsof 全 |
| **/proc** | 直接读取内核信息 | 最权威 | 操作复杂 |

## 二、第一招：使用 ss 命令（最推荐）

`ss`（Socket Statistics）是 `netstat` 的现代替代品，读取 `/proc/net` 直接获取信息，速度比 `netstat` 快几个数量级。

### 基础用法

```bash
# 查看所有 TCP 端口的监听状态
ss -tlnp

# 只查看特定端口
ss -tlnp | grep 18789

# 查看所有状态的连接（包括 ESTABLISHED、TIME_WAIT 等）
ss -tnp

# 查看 UDP 端口
ss -ulnp
```

**参数说明：**
- `-t`：TCP
- `-u`：UDP
- `-l`：只显示 LISTEN 状态
- `-n`：不解析服务名（显示数字端口）
- `-p`：显示进程信息

### 输出示例

```
LISTEN 0  128  0.0.0.0:18789  0.0.0.0:*  users:(("openclaw-gatewa",pid=281750,fd=7))
```

从输出中你可以读到：
- **协议**：LISTEN（监听状态）
- **地址**：`0.0.0.0:18789`（IPv4 所有地址的 18789 端口）
- **进程**：`openclaw-gatewa` (pid 281750)
- **文件描述符**：fd 7

### 进阶用法

```bash
# 查看 IPv4 + IPv6 监听
ss -tlnp -A inet

# 按进程名过滤
ss -tlnp 'sport = :18789'

# 查看进程所属的网络命名空间
ss -tlnp -n netns

# 显示 socket 详细信息（包括内存、计时器等）
ss -tlnepi
```

**实战建议**：在生产环境中，`ss -tlnp` 是你**应该**第一反应使用的命令。它速度快、输出清晰、大部分 Linux 发行版都默认安装。

## 三、第二招：使用 lsof（信息最全）

`lsof`（List Open Files）可以列出进程打开的所有文件，包括网络连接。它是排查端口问题的"瑞士军刀"。

### 基础用法

```bash
# 查看占用特定端口的进程
lsof -i :18789

# 查看 IPv4 端口
lsof -i4 :18789

# 查看 IPv6 端口
lsof -i6 :18789

# 同时查看协议类型
lsof -i tcp:18789
lsof -i udp:18789
```

### 输出示例

```
COMMAND     PID   USER   FD   TYPE   DEVICE SIZE/OFF NODE NAME
openclaw-g 281750 root    7u  IPv4  1234567      0t0  TCP *:18789 (LISTEN)
openclaw-g 281750 root    8u  IPv6  1234568      0t0  TCP *:18789 (LISTEN)
```

**字段解读：**
- **COMMAND**：命令名
- **PID**：进程 ID
- **USER**：进程所属用户
- **FD**：文件描述符（`7u` 表示 7 号 fd，u 表示可读写）
- **TYPE**：socket 类型（IPv4/IPv6）
- **DEVICE**：设备号
- **NODE**：协议和地址
- **NAME**：连接信息

### 进阶用法

```bash
# 查看进程打开的所有网络连接
lsof -p 281750

# 查看进程打开的所有文件
lsof -p 281750 | head -30

# 查看用户打开的网络连接
lsof -u root -i

# 反向查询：根据 inode 找进程
lsof -i @127.0.0.1

# 持续监控
lsof -i :18789 -r 5  # 每 5 秒刷新一次
```

**实战建议**：`lsof` 是排查"找不到进程"问题的神器。当 `ss` 显示有进程占用但 `ps` 找不到时，`lsof` 往往能给你答案。

## 四、第三招：使用 netstat（兼容性最好）

虽然 `ss` 是新欢，但 `netstat` 在很多老系统上仍然是默认工具。掌握它也很有必要。

### 基础用法

```bash
# 查看所有监听端口
netstat -tlnp

# 查看特定端口
netstat -tlnp | grep 18789

# 查看所有连接（包括非监听）
netstat -anp

# 查看 UNIX 域套接字
netstat -xlnp
```

**参数说明：**
- `-t`：TCP
- `-u`：UDP
- `-l`：LISTEN 状态
- `-n`：数字端口
- `-p`：进程
- `-a`：所有连接

### 输出示例

```
tcp  0  0  0.0.0.0:18789  0.0.0.0:*  LISTEN  281750/openclaw-ga
tcp  0  0  [::]:18789     [::]:*     LISTEN  281750/openclaw-gw
```

### 注意事项

```bash
# 如果 netstat 命令不存在，需要安装
# CentOS/RHEL:
yum install -y net-tools

# Ubuntu/Debian:
apt-get install -y net-tools
```

**实战建议**：在写脚本或者文档时，建议优先使用 `ss`。但在 SSH 到老系统时，先试试 `netstat` 也无妨。

## 五、第四招：使用 fuser（最暴力）

`fuser` 可以显示"使用某个文件/端口的所有进程"，并支持直接发送信号。

### 基础用法

```bash
# 查看占用 18789 端口的进程
fuser 18789/tcp

# 查看详细信息
fuser -v 18789/tcp

# 直接杀死占用进程（慎用！）
fuser -k 18789/tcp

# 发送特定信号
fuser -k -TERM 18789/tcp
fuser -k -KILL 18789/tcp  # 等同于 -9
```

### 输出示例

```
18789/tcp:           281750
```

只显示 PID，简单直接。

### 进阶用法

```bash
# 查看进程使用的所有文件
fuser -v /var/log/openclaw/

# 查看挂载点的占用
fuser -mv /mnt/data

# 命名空间级别
fuser -m /mnt/data
```

**实战建议**：`fuser -k` 是"一键杀进程"工具，但**慎用**！在生产环境使用前，务必确认这个进程可以杀。

## 六、终极招：直接查 /proc

当所有命令都"找不到进程"时，那就只能直接读 `/proc` 了。

### 查看占用 18789 的进程

```bash
# 找到占用 18789 端口的 socket inode
cat /proc/net/tcp | awk '$2 ~ /:4935$/ {print $10}'
# 18789 的十六进制是 4935
```

### 反向查找

```bash
# 根据 inode 找到进程
find /proc -path "*/fd/*" -exec ls -l {} \; 2>/dev/null | grep "socket:[1234567]"
```

### 查看进程命令行

```bash
# 根据 PID 查看完整命令行
cat /proc/281750/cmdline | tr '\0' ' '

# 查看进程状态
cat /proc/281750/status

# 查看进程启动时间
ps -p 281750 -o lstart=
```

**实战建议**：直接查 `/proc` 是"核武器"级别的方法。一般情况下用 `ss` 和 `lsof` 就够了，但遇到诡异问题时，这是最后的退路。

## 七、常见疑难场景

### 场景 1：ss 显示有进程，ps 找不到

这是经典的"幽灵进程"问题。

**症状**：
```bash
ss -tlnp | grep 18789
# 输出：users:(("openclaw-gatewa",pid=281750,fd=7))

ps -p 281750
# 输出：error: process ID list syntax error
```

**原因**：
- 进程是 zombie 状态（`Z`），已死但未释放资源
- 进程是 namespace 隔离的，主机 ps 看不到
- 进程在容器里，ps 只能看到容器内的

**排查方法**：
```bash
# 查看所有进程（不限于当前会话）
ps auxf

# 查看 zombie 进程
ps -eo pid,ppid,stat,cmd | awk '$3 ~ /Z/'

# 查看进程的父进程
ps -o ppid= -p 281750
```

**解决方法**：
- 如果是 zombie，找到父进程，重启父进程
- 如果是 namespace 问题，进入对应 namespace
- 如果是容器问题，进入容器查看

### 场景 2：端口被 TIME_WAIT 占用

**症状**：
```bash
ss -tan | grep 18789
# 输出：TIME-WAIT 状态的连接一大堆
```

**原因**：
服务刚刚关闭，但 TCP 连接还在 TIME_WAIT 状态（等待 2MSL 时间，确保最后的 ACK 被对端收到）。这个状态下，端口虽然没人在用，但内核不允许新进程绑定。

**解决方法**：
```bash
# 方法 1：等待 1-2 分钟（推荐）
# 让 TIME_WAIT 自然消失

# 方法 2：开启 SO_REUSEADDR（推荐在代码中处理）
# 允许绑定 TIME_WAIT 状态的地址

# 方法 3：调整内核参数（不推荐）
net.ipv4.tcp_tw_reuse = 1
sysctl -p

# 方法 4：使用 SO_REUSEPORT（应用层处理）
# 允许多个进程绑定同一端口（负载均衡场景）
```

### 场景 3：systemd 一直在 restart loop

**症状**：
```bash
systemctl status openclaw-gateway
# Active: activating (auto-restart) (Result: exit-code)
# 状态: failed
```

但实际上服务在用——某个游离进程占用了 18789 端口，systemd 启动失败但又不停重启。

**排查方法**：
```bash
# 1. 查看端口占用
ss -tlnp | grep 18789

# 2. 如果有游离进程，杀掉它
kill <pid>

# 3. 等待端口释放
ss -tlnp | grep 18789  # 确认无监听

# 4. 重启 systemd 服务
systemctl restart openclaw-gateway
```

**预防方法**：
- 永远只通过 systemd 启动服务
- 禁止直接运行 `xxx-daemon &`
- 定期巡检是否有游离进程

### 场景 4：容器内端口被占用的错觉

**症状**：
- 主机上 `ss -tlnp` 看不到占用
- 容器内 `ss -tlnp` 看到端口被占用

**原因**：
容器有自己的网络命名空间，主机和容器的端口是隔离的。容器内占用不代表主机占用。

**排查方法**：
```bash
# 进入容器查看
docker exec -it <container> ss -tlnp

# 或者使用 nsenter
nsenter -t <container_pid> -n ss -tlnp

# 查看容器端口映射
docker port <container>
```

## 八、一键排查脚本

把上面的方法组合起来，写一个"端口占用一键排查"脚本：

```bash
#!/bin/bash
# check_port.sh - 端口占用一键排查

PORT=${1:-18789}

echo "=== 端口 $PORT 占用情况排查 ==="
echo

echo "1. ss 命令结果:"
ss -tlnp 2>/dev/null | grep ":$PORT " || echo "  无 LISTEN 状态占用"
echo

echo "2. lsof 命令结果:"
lsof -i :$PORT 2>/dev/null || echo "  lsof 不可用或无占用"
echo

echo "3. netstat 命令结果:"
netstat -tlnp 2>/dev/null | grep ":$PORT " || echo "  netstat 不可用或无占用"
echo

echo "4. fuser 命令结果:"
fuser -v $PORT/tcp 2>&1 || echo "  fuser 不可用或无占用"
echo

echo "5. /proc/net/tcp 原始数据:"
HEX_PORT=$(printf "%04X" $PORT)
echo "  端口 $PORT 的十六进制: $HEX_PORT"
cat /proc/net/tcp 2>/dev/null | awk -v hp="$HEX_PORT" '$2 ~ ":"hp"$" || $3 ~ ":"hp"$" {print "  "$0}' | head -5
echo

echo "6. TIME_WAIT 状态连接数:"
ss -tan 2>/dev/null | grep ":$PORT " | grep TIME-WAIT | wc -l
echo

echo "=== 排查完成 ==="
```

**使用方法**：
```bash
chmod +x check_port.sh
./check_port.sh 18789
```

## 九、Q&A

### Q1：ss 和 netstat 应该用哪个？

**A**：优先用 `ss`。`ss` 速度更快、信息更全、是 `iproute2` 包的一部分。在 CentOS 7+、Ubuntu 16.04+、所有现代 Linux 发行版上都默认安装。

只在老系统或者脚本兼容性要求高时才用 `netstat`。

### Q2：lsof 在容器里查不到东西怎么办？

**A**：在容器里使用 `lsof` 需要特权模式，或者直接进入容器的网络命名空间：

```bash
# 方法 1：特权模式启动
docker run --privileged ...

# 方法 2：共享网络命名空间
docker run --network host ...

# 方法 3：使用 nsenter
PID=$(docker inspect -f '{{.State.Pid}}' <container>)
nsenter -t $PID -n lsof -i :18789
```

### Q3：杀进程后端口还是占用怎么办？

**A**：有以下几种可能：

1. **进程没杀干净**——可能存在父子进程，需要全部杀掉
2. **TIME_WAIT 状态**——等待几分钟自然消失
3. **内核还在回收**——`cat /proc/net/sockstat` 查看 socket 状态
4. **多个进程占用**——`lsof -i :PORT` 看完整列表

### Q4：如何避免端口被占用的问题？

**A**：

1. **统一管理**：所有服务都通过 systemd 或容器编排管理，禁止手动启动
2. **配置端口白名单**：在防火墙中只开放需要的端口
3. **监控告警**：对端口状态做监控，异常时及时告警
4. **定期巡检**：定期检查游离进程和端口占用情况

### Q5：lsof 很慢，有更快的替代品吗？

**A**：`ss` 已经是更快的替代品了。如果 `lsof` 还是慢，可以考虑：

- `fuser`：速度更快，但信息少
- 直接读 `/proc/net/tcp`：最快，但要自己解析
- `pidstat`：看进程级别的网络活动

## 十、总结

端口占用排查是运维的基本功，看似简单，实则涉及很多细节。本文从 `ss`、`lsof`、`netstat`、`fuser` 四个工具入手，配合 `/proc` 底层分析，覆盖了：

1. ✅ 基础端口查看
2. ✅ 进程 PID 定位
3. ✅ 幽灵进程排查
4. ✅ TIME_WAIT 处理
5. ✅ systemd restart loop
6. ✅ 容器网络命名空间
7. ✅ 一键排查脚本

**核心要点**：
- **首选 `ss`**，信息全、速度快、现代化
- **`lsof` 排查诡异问题**，信息最全
- **`fuser` 一键杀进程**，但要慎用
- **`/proc` 终极武器**，所有命令失效时的最后退路

希望本文能成为大家排查端口占用问题的"案头手册"。下次再遇到"Address already in use"，相信你不会再一头雾水了。

---

*作者：小六，一个在上海努力生存的普通打工人*
