---
title: VPS防火墙配置实战：18789端口内网访问限制完整指南
categories:
  - ai_tech
tags:
  - 技术
  - 运维
  - 安全
  - 防火墙
  - Docker
cover: 'https://picsum.photos/seed/tech0307/1280/720'
coverWidth: 1280
coverHeight: 720
date: 2026-03-07 21:30:00
---

## 前言

在运维工作中，服务器安全是一个永恒的话题。今天我遇到一个典型的问题：某台有公网 IP 的 VPS 服务器上，OpenClaw Gateway 的 18789 端口暴露在公网，存在严重的安全隐患。本文将详细记录从发现问题的完整排查过程，以及最终的解决方案，希望给遇到类似问题的同学一些参考。

## 问题背景

### 业务场景

我们的 OpenClaw 系统部署在多台服务器上，其中包括一台有公网 IP 的 VPS（VPS4）。这台机器需要对外提供 Web 服务（443、8443 端口），同时运行 OpenClaw Gateway 管理内部 Agent。

### 发现问题

在一次安全检查中，发现了一个严重的问题：

- **VPS 公网 IP**：某VPS（已脱敏）
- **OpenClaw Gateway 端口**：18789
- **问题**：18789 端口可以从公网直接访问

这意味着任何人都可以通过 `http://某域名:18789/` 访问到 OpenClaw Gateway 的管理接口，这是非常危险的行为。

### 环境信息

- **服务器类型**：VPS（有公网 IP）
- **操作系统**：Ubuntu 24.04
- **部署方式**：Docker 容器
- **应用**：OpenClaw Gateway
- **需要暴露的端口**：22（SSH）、443（HTTPS）、8443
- **需要限制的端口**：18789（仅内网）

## 问题分析

### 第一层：防火墙配置

首先检查防火墙规则。VPS 默认使用 iptables 或 ufw 作为防火墙软件。

```bash
# 查看当前防火墙规则
iptables -L -n

# 查看端口监听状态
netstat -tlnp | grep 18789
```

理论上，防火墙应该阻止从公网访问 18789 端口。但实际上，公网依然可以访问这个端口。

### 第二层：Docker 端口绑定

问题出在 Docker 的端口映射配置上。

```bash
# 查看 Docker 端口映射
docker ps
docker port <container_id>
```

原来，在启动容器时，端口映射是这样配置的：

```bash
# 原来的端口映射（有问题）
docker run -p 0.0.0.0:18789:18789 ...
```

`0.0.0.0:18789` 意味着绑定所有网络接口，包括公网网卡。这导致流量直接通过 Docker 端口映射进来，根本没有走防火墙。

### 根因总结

这是一个典型的"层层失守"问题：

1. **第一层失守**：Docker 端口绑定到 `0.0.0.0`
2. **第二层失守**：防火墙规则虽然配置了，但没有起到作用

流量路径：
```
公网用户 -> VPS 公网网卡 -> Docker 端口映射 -> 容器
                ↑             ↑
            防火墙未生效   直接绑定所有接口
```

## 解决方案

### 方案一：修改 Docker 端口绑定（推荐）

最直接的解决方案是将 Docker 端口映射改为仅绑定本地地址：

```bash
# 停止并删除旧容器
docker stop <container_id>
docker rm <container_id>

# 使用 127.0.0.1 绑定（仅本地访问）
docker run -p 127.0.0.1:18789:18789 ...

# 或者使用内网 IP 绑定
docker run -p 192.168.x.x:18789:18789 ...
```

**验证结果**：

| 来源 | 访问 18789 | 状态 |
|------|-----------|------|
| localhost (127.0.0.1) | ✅ | 正常 |
| 内网 (192.168.x.x) | ✅ | 正常 |
| 公网 (某VPS) | ❌ | 已阻止 |

### 方案二：防火墙 + Docker 双重防护

除了修改 Docker 配置，还应该配置防火墙规则作为第二层防护：

```bash
# 允许特定端口
iptables -A INPUT -p tcp --dport 22 -j ACCEPT
iptables -A INPUT -p tcp --dport 443 -j ACCEPT
iptables -A INPUT -p tcp --dport 8443 -j ACCEPT

# 限制 18789 仅内网访问
iptables -A INPUT -p tcp --dport 18789 -s 192.168.0.0/16 -j ACCEPT
iptables -A INPUT -p tcp --dport 18789 -j DROP
```

### 方案三：使用 Docker 网络模式

对于更严格的隔离，可以使用 Docker 的网络模式：

```bash
# 创建自定义网络（仅内网）
docker network create --subnet 192.168.200.0/24 internal_network

# 容器加入内网网络
docker run --network internal_network ...
```

这样容器就不会暴露到宿主机的公网接口上。

## 完整操作步骤

### 步骤 1：检查当前状态

```bash
# 1. 查看容器运行状态
docker ps | grep openclaw

# 2. 查看端口映射
docker port <container_id>

# 3. 测试公网访问（从有公网IP的机器测试）
curl http://127.0.0.1:18789/
curl http://<内网IP>:18789/

# 4. 从另一台机器测试内网访问
curl http://<VPS内网IP>:18789/
```

### 步骤 2：修改 Docker 启动配置

```bash
# 1. 停止容器
docker stop openclaw-gateway

# 2. 删除容器（保留镜像）
docker rm openclaw-gateway

# 3. 重新启动，绑定到 127.0.0.1
docker run -d \
  --name openclaw-gateway \
  -p 127.0.0.1:18789:18789 \
  -p 127.0.0.1:9229:9229 \
  -v /opt/openclaw:/data \
  openclaw/gateway:latest
```

### 步骤 3：配置防火墙（可选但推荐）

```bash
# 1. 安装 ufw（如果未安装）
apt install ufw

# 2. 配置规则
ufw allow 22/tcp    # SSH
ufw allow 443/tcp   # HTTPS
ufw allow 8443/tcp  # 自定义端口

# 3. 限制 18789 仅内网
ufw allow from 192.168.0.0/16 to any port 18789
ufw deny 18789

# 4. 启用防火墙
ufw enable
```

### 步骤 4：验证修复效果

```bash
# 1. 从本地测试
curl http://127.0.0.1:18789/  # 应该成功

# 2. 从内网其他机器测试
curl http://<VPS内网IP>:18789/  # 应该成功

# 3. 从公网测试（模拟）
# 如果有公网机器，执行：
curl http://<VPS公网IP>:18789/  # 应该失败

# 4. 查看日志确认
docker logs openclaw-gateway
```

## 常见问题解答

**Q：为什么防火墙规则没有生效？**

A：Docker 的端口映射在防火墙之前处理流量。如果 Docker 绑定到 `0.0.0.0`，流量直接进入容器，不会经过防火墙。需要同时修改 Docker 配置和防火墙规则。

**Q：如何判断端口是否暴露在公网？**

A：从有公网 IP 的机器（或使用在线端口检测工具）尝试连接。如果能连上，说明暴露了。

**Q：修改 Docker 端口绑定后内网还能访问吗？**

A：取决于你绑定到哪个地址。绑定到 `127.0.0.1` 仅本地可访问；绑定到内网 IP（如 `192.168.x.x`）则内网可访问。

**Q：生产环境应该怎么做更安全？**

A：建议多层防护：
1. 不暴露管理端口到公网
2. 使用 VPN 或内网访问
3. 配置防火墙规则
4. 使用认证和鉴权机制

## 安全最佳实践

### 1. 端口暴露原则

- **SSH（22）**：可暴露，但建议使用密钥登录
- **Web 服务（80/443）**：需要暴露，但建议配置 HTTPS
- **管理端口（18789、9000 等）**：不应暴露在公网

### 2. Docker 安全建议

```bash
# 1. 不使用 0.0.0.0 绑定
-p 127.0.0.1:8080:8080

# 2. 使用只读文件系统
--read-only

# 3. 限制容器资源
--memory=512m --cpus=0.5

# 4. 不以 root 运行
--user 1000:1000
```

### 3. 定期安全检查

建议定期执行以下检查：

```bash
# 1. 检查端口暴露情况
ss -tlnp | grep -E ':(22|80|443|18789|9000)\s'

# 2. 检查 Docker 网络
docker network ls
docker network inspect bridge

# 3. 检查防火墙规则
iptables -L -n -v
```

## 总结

本文记录了一次典型的 VPS 端口暴露安全问题及其修复过程。核心教训是：

1. **Docker 端口映射要谨慎**：不要绑定到 `0.0.0.0`，尤其是管理端口
2. **多层防护**：防火墙 + Docker 配置 + 应用认证
3. **定期检查**：安全不是一次性工作，需要持续关注

希望这篇文章能帮到你。如果有问题，欢迎在评论区讨论。

---

*作者：小六，一个在上海努力搬砖的程序员*
