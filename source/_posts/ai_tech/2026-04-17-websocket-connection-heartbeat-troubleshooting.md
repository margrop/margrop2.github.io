---
title: 排查一次 WebSocket 连接意外断连：从心跳机制到连接保活的实战总结
categories:
  - ai_tech
tags:
  - 技术
  - 运维
  - WebSocket
  - 问题排查
  - 连接保活
cover: 'https://picsum.photos/seed/tech0417/1280/720'
coverWidth: 1280
coverHeight: 720
date: 2026-04-17 21:30:00
---

## 前言

在使用 WebSocket 实现长连接通信时，最让人头疼的问题之一就是连接莫名其妙地断开了。用户正在正常使用，突然就显示连接断开，体验大打折扣。

今天遇到一个典型的案例：钉钉 Stream 模式的 WebSocket 连接在工作时间段内频繁断开，每次断开后都需要重新建立连接。经过详细排查，发现是心跳机制和连接保活配置出了问题。本文将完整记录这次排查过程，分析问题根因，并提供完整的解决方案。

## 问题背景

### 业务场景

我们的 OpenClaw 系统通过钉钉 Stream 模式接收用户消息。Stream 模式本质上是 WebSocket 长连接，客户端与钉钉服务器建立连接后，通过这个通道实时接收消息。

### 问题现象

- **故障时间**：工作日工作时间，连接频繁断开
- **故障频率**：平均每30-60分钟断开一次
- **影响范围**：所有通过钉钉收发消息的用户都受影响
- **恢复方式**：自动重连，但重连期间消息丢失

### 环境信息

- **操作系统**：Ubuntu 24.04 LTS
- **消息通道**：钉钉 Stream 模式（WebSocket）
- **OpenClaw 版本**：v2026.4.1
- **部署节点**：VM151、VM152
- **网络环境**：内网访问，有固定出口IP

## 问题分析

### 第一步：确认连接断开时的错误日志

首先查看 Gateway 日志，确认连接断开时的具体错误信息：

```bash
# 查看最近的错误日志
tail -500 /tmp/openclaw-gateway.log | grep -E "(WebSocket|disconnect|heartbeat|timeout|error)" -i

# 典型错误日志示例：
# [2026-04-17T09:15:23.456Z] WARN - WebSocket heartbeat timeout, closing connection
# [2026-04-17T09:15:23.789Z] WARN - DingTalk WebSocket disconnected: heartbeat timeout
# [2026-04-17T09:15:24.012Z] INFO - Attempting to reconnect to DingTalk Stream...
# [2026-04-17T09:15:24.345Z] INFO - Successfully reconnected to DingTalk Stream
```

日志显示连接断开的原因是 **heartbeat timeout**。这说明问题出在心跳机制上。

### 第二步：分析心跳机制原理

钉钉 Stream 模式的工作原理是这样的：

1. 客户端与钉钉服务器建立 WebSocket 连接
2. 钉钉服务器定期发送心跳包（ping）维持连接活跃
3. 客户端收到心跳包后回复 pong
4. 如果连续多次没有收到心跳包或心跳响应，服务器主动断开连接

关键参数是心跳超时时间。根据钉钉官方文档，心跳超时时间默认是 **30秒**。也就是说，如果 30 秒内没有收到心跳包或心跳响应，连接就会被断开。

### 第三步：排查心跳包发送情况

使用 tcpdump 抓包分析心跳包收发情况：

```bash
# 使用 tcpdump 抓取 WebSocket 相关的网络包
# 注意：WebSocket 默认端口是 443（HTTPS/WSS）
sudo tcpdump -i any -n 'tcp port 443' -A | grep -E "(ping|pong|WebSocket)" | head -50

# 抓取更详细的数据包
sudo tcpdump -i any -n 'tcp port 443' -w /tmp/ws_traffic.pcap &
# 等待一段时间
sleep 60
# 停止抓包
sudo killall tcpdump

# 分析抓包文件
sudo tcpdump -r /tmp/ws_traffic.pcap | grep -E "(ping|pong)" | head -20
```

抓包结果发现：心跳包是正常发送的，但客户端有时在 25-28 秒时才响应 pong，而服务器的超时阈值是 30 秒。差一点点就超时了。

### 第四步：检查网络延迟

使用 mtr 检查到钉钉服务器的网络路径和延迟：

```bash
# 使用 mtr 检查到钉钉服务器的网络质量
mtr --report --report-cycles 10 api.dingtalk.com

# 输出示例：
# HOST: local                Loss%   Snt   Last   Avg  Best   Wrst StDev
# 1.|-- gateway              0.0%    10    0.3   0.4   0.2   0.6   0.1
# 2.|-- core-router          0.0%    10    0.8   1.1   0.6   2.1   0.4
# 3.|-- isp-border           0.0%    10   12.3  15.6  11.2  22.4   3.2
# 4.|-- ???                  100.0%   10    0.0   0.0   0.0   0.0   0.0
# 5.|-- api.dingtalk.com     0.0%    10   28.4  32.1  26.8  45.2   5.8
```

发现到钉钉服务器的单向延迟已经达到 **28-45ms**，往返延迟约 60-90ms。这个延迟虽然不算高，但对于心跳保活来说，是一个不稳定的因素。

### 第五步：检查客户端心跳处理逻辑

查看 OpenClaw 代码中的心跳处理逻辑：

```javascript
// 位置：gateway/channels/dingtalk/stream.js
class DingTalkStreamClient {
  constructor(options) {
    this.options = options;
    this.heartbeatInterval = options.heartbeatInterval || 30000; // 默认30秒
    this.heartbeatTimeout = options.heartbeatTimeout || 60000;   // 默认60秒
    this.reconnectInterval = options.reconnectInterval || 5000;   // 重连间隔5秒
    this.maxReconnectAttempts = options.maxReconnectAttempts || 10;
  }

  start() {
    this.ws = new WebSocket(this.getStreamUrl());
    
    // 设置心跳定时器
    this.heartbeatTimer = setInterval(() => {
      this.sendPing();
    }, this.heartbeatInterval);

    // 设置心跳超时检测
    this.heartbeatTimeoutTimer = setTimeout(() => {
      this.handleHeartbeatTimeout();
    }, this.heartbeatTimeout);
  }

  // 发送心跳
  sendPing() {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: 'ping'
      }));
      log.debug('Sent heartbeat ping');
    }
  }

  // 处理心跳超时
  handleHeartbeatTimeout() {
    log.warn('Heartbeat timeout, closing connection');
    this.ws.close(4001, 'Heartbeat timeout');
    this.scheduleReconnect();
  }

  // 收到pong响应
  onPong() {
    // 重置心跳超时定时器
    clearTimeout(this.heartbeatTimeoutTimer);
    this.heartbeatTimeoutTimer = setTimeout(() => {
      this.handleHeartbeatTimeout();
    }, this.heartbeatTimeout);
    log.debug('Received heartbeat pong');
  }
}
```

问题分析：代码逻辑本身是对的，但有两个潜在问题：

1. **心跳间隔设置过长**：默认 30 秒发送一次心跳，而钉钉服务器要求在 30 秒内至少有一次交互。如果网络稍有抖动，30 秒的心跳间隔加上网络延迟就可能触发超时。

2. **心跳超时设置过短**：默认 60 秒的心跳超时看着很宽松，但考虑到心跳是每 30 秒才发一次，实际只容许丢一个心跳包就超时。

### 第六步：定位根因

经过以上排查，问题根因逐渐清晰：

**根因一：心跳间隔与服务器超时阈值接近**

钉钉服务器的心跳超时阈值是 30 秒，而客户端默认每 30 秒才发一次心跳。加上网络往返延迟（约 60-90ms），服务器可能在第 29-30 秒才收到心跳，响应可能在第 30 秒后才到达，网络稍有抖动就会超时。

**根因二：心跳超时检测不够灵敏**

代码中只发送 ping 包，没有主动检测服务器发来的 ping 包。如果钉钉服务器发送了 ping 但客户端没有及时响应 pong，服务器就会主动断开连接。

**根因三：重连策略不够平滑**

断开后 5 秒就开始重连，如果重连失败，会立即再次尝试，可能触发钉钉的限流机制，导致更长时间无法连接。

## 解决方案

### 方案一：优化心跳配置（推荐）

调整心跳间隔和超时时间，留出足够的缓冲空间：

```yaml
# OpenClaw 配置文件 - channels.dingtalk 部分
channels:
  dingtalk:
    enabled: true
    mode: stream
    
    # 心跳配置优化
    heartbeatInterval: 20000  # 从30秒缩短到20秒，留出10秒缓冲
    heartbeatTimeout: 45000   # 从60秒缩短到45秒，保证至少2个心跳周期
    
    # 重连配置优化
    reconnectInterval: 10000   # 从5秒延长到10秒，避免触发限流
    maxReconnectAttempts: 20   # 从10次增加到20次，增加恢复机会
    reconnectBackoff: true     # 启用指数退避，避免连续重连
```

### 方案二：增强心跳保活机制

主动响应服务器的心跳，并加入 TCP keepalive：

```javascript
// 增强后的心跳处理逻辑
class DingTalkStreamClient {
  // ...

  start() {
    this.ws = new WebSocket(this.getStreamUrl());
    
    // 设置主动心跳（每20秒一次）
    this.heartbeatTimer = setInterval(() => {
      this.sendPing();
    }, 20000);

    // 监听服务器的心跳
    this.ws.on('message', (data) => {
      const msg = JSON.parse(data);
      
      if (msg.type === 'ping') {
        // 立即响应服务器的ping
        this.sendPong();
        log.debug('Received server ping, sent pong immediately');
      } else if (msg.type === 'pong') {
        // 收到pong响应，重置超时
        this.resetHeartbeatTimeout();
        log.debug('Received pong response');
      } else {
        // 其他消息也视为心跳保活
        this.resetHeartbeatTimeout();
      }
    });

    // 设置超时检测
    this.resetHeartbeatTimeout();
  }

  sendPing() {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      try {
        this.ws.send(JSON.stringify({ type: 'ping' }));
        log.debug('Sent heartbeat ping');
      } catch (err) {
        log.error('Failed to send ping:', err);
      }
    }
  }

  sendPong() {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      try {
        this.ws.send(JSON.stringify({ type: 'pong' }));
      } catch (err) {
        log.error('Failed to send pong:', err);
      }
    }
  }

  resetHeartbeatTimeout() {
    clearTimeout(this.heartbeatTimeoutTimer);
    this.heartbeatTimeoutTimer = setTimeout(() => {
      this.handleHeartbeatTimeout();
    }, 45000); // 45秒超时
  }
}
```

### 方案三：添加 TCP 层 Keepalive

除了应用层心跳，还需要在 TCP 层面启用 keepalive：

```bash
# 查看当前 TCP keepalive 参数
sysctl net.ipv4.tcp_keepalive_time
sysctl net.ipv4.tcp_keepalive_intvl
sysctl net.ipv4.tcp_keepalive_probes

# 当前值通常是：
# net.ipv4.tcp_keepalive_time = 7200 (2小时，太长了)
# net.ipv4.tcp_keepalive_intvl = 75
# net.ipv4.tcp_keepalive_probes = 9

# 优化 TCP keepalive 参数（针对 WebSocket 连接）
# 添加到 /etc/sysctl.conf 或使用 sysctl 命令
sysctl -w net.ipv4.tcp_keepalive_time=60      # 60秒开始首次探测
sysctl -w net.ipv4.tcp_keepalive_intvl=10       # 每10秒探测一次
sysctl -w net.ipv4.tcp_keepalive_probes=5      # 探测5次失败后断开

# 验证配置
sysctl net.ipv4.tcp_keepalive_time
sysctl net.ipv4.tcp_keepalive_intvl
sysctl net.ipv4.tcp_keepalive_probes
```

### 方案四：完善重连策略

使用指数退避策略，避免频繁重连触发限流：

```javascript
// 增强的重连策略
class DingTalkStreamClient {
  // ...
  
  scheduleReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      log.error('Max reconnect attempts reached, giving up');
      this.emit('reconnect_failed');
      return;
    }

    // 指数退避计算重连间隔
    // 初始间隔 10秒，最大间隔 5分钟
    const baseInterval = 10000;
    const maxInterval = 300000;
    const backoffMultiplier = 1.5;
    
    const delay = Math.min(
      baseInterval * Math.pow(backoffMultiplier, this.reconnectAttempts),
      maxInterval
    );

    log.info(`Scheduling reconnect attempt ${this.reconnectAttempts + 1} in ${delay}ms`);
    
    setTimeout(() => {
      this.reconnectAttempts++;
      this.start();
    }, delay);
  }
}
```

## 一键部署脚本

如果需要在多台服务器上快速部署修复，可以直接运行以下脚本：

```bash
#!/bin/bash
# 文件名：fix-dingtalk-heartbeat.sh
# 用途：修复钉钉 Stream 模式心跳配置

echo "=========================================="
echo "钉钉 Stream 心跳配置修复脚本"
echo "时间：$(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
echo ""

# 备份原配置
echo "[1/5] 备份原配置文件..."
cp /opt/openclaw/config.yml /opt/openclaw/config.yml.bak.$(date +%Y%m%d%H%M%S)
echo "  ✓ 备份完成：$(ls -la /opt/openclaw/config.yml.bak.* | tail -1 | awk '{print $NF}')"

# 修改心跳配置
echo "[2/5] 修改心跳配置..."
# 使用 sed 直接替换关键参数
sed -i 's/heartbeatInterval: 30000/heartbeatInterval: 20000/g' /opt/openclaw/config.yml
sed -i 's/heartbeatTimeout: 60000/heartbeatTimeout: 45000/g' /opt/openclaw/config.yml
sed -i 's/reconnectInterval: 5000/reconnectInterval: 10000/g' /opt/openclaw/config.yml
echo "  ✓ 心跳配置已更新"

# 验证配置修改
echo "[3/5] 验证配置修改..."
grep -E "(heartbeatInterval|heartbeatTimeout|reconnectInterval)" /opt/openclaw/config.yml

# 优化 TCP keepalive
echo "[4/5] 优化 TCP keepalive 参数..."
sysctl -w net.ipv4.tcp_keepalive_time=60 2>/dev/null && echo "  ✓ tcp_keepalive_time = 60"
sysctl -w net.ipv4.tcp_keepalive_intvl=10 2>/dev/null && echo "  ✓ tcp_keepalive_intvl = 10"
sysctl -w net.ipv4.tcp_keepalive_probes=5 2>/dev/null && echo "  ✓ tcp_keepalive_probes = 5"

# 使配置永久生效
if ! grep -q "net.ipv4.tcp_keepalive_time" /etc/sysctl.conf; then
  echo "net.ipv4.tcp_keepalive_time = 60" >> /etc/sysctl.conf
  echo "net.ipv4.tcp_keepalive_intvl = 10" >> /etc/sysctl.conf
  echo "net.ipv4.tcp_keepalive_probes = 5" >> /etc/sysctl.conf
  echo "  ✓ 已写入 /etc/sysctl.conf"
fi

# 重启 Gateway 服务
echo "[5/5] 重启 Gateway 服务..."
systemctl --user restart openclaw-gateway
sleep 3
if systemctl --user is-active openclaw-gateway; then
  echo "  ✓ Gateway 服务已重启"
else
  echo "  ✗ Gateway 服务重启失败，请检查日志"
  exit 1
fi

echo ""
echo "=========================================="
echo "修复完成！"
echo "建议观察接下来 30 分钟的日志，确认连接稳定："
echo "  tail -f /tmp/openclaw-gateway.log | grep -E '(heartbeat|reconnect|WebSocket)'"
echo "=========================================="
```

## 常见问题解答

**Q1：为什么缩短心跳间隔能解决问题？**

A：钉钉服务器的心跳超时阈值是 30 秒。如果心跳间隔也是 30 秒，加上网络往返延迟（约 60-90ms），几乎没有任何缓冲空间。网络稍有抖动就会超时。缩短到 20 秒后，留出了 10 秒的缓冲空间，即使网络有点慢，也能在超时前收到响应。

**Q2：心跳间隔是不是越短越好？**

A：不是。心跳间隔太短会增加服务器负担，还可能触发限流。建议根据实际网络状况调整，一般保持在 20-30 秒之间比较合适。

**Q3：TCP keepalive 和应用层心跳有什么区别？**

A：TCP keepalive 是操作系统层面的保活机制，检测的是 TCP 连接是否存活，但检测周期较长（默认 2 小时）。应用层心跳是自定义的心跳机制，可以更灵活地控制检测频率和检测内容。两者配合使用，可以更好地保证连接稳定性。

**Q4：重连失败怎么办？**

A：可以设置最大重连次数和指数退避策略，避免无限重连。如果超过最大重连次数，建议发送告警通知运维人员手动处理。同时也要检查是否是钉钉服务本身的限流问题。

**Q5：如何监控 WebSocket 连接状态？**

A：建议添加以下监控指标：
- 连接断开次数和频率
- 心跳成功率
- 重连成功率和平均重连时间
- 当前在线连接数

使用 Prometheus 采集这些指标，配合 Grafana 可视化，可以及时发现连接问题。

## 性能影响分析

### 配置优化前后对比

| 参数 | 优化前 | 优化后 | 影响 |
|------|--------|--------|------|
| 心跳间隔 | 30秒 | 20秒 | 更频繁的保活，连接更稳定 |
| 心跳超时 | 60秒 | 45秒 | 更灵敏的超时检测 |
| 重连间隔 | 5秒 | 10秒 | 避免频繁重连触发限流 |
| TCP keepalive | 2小时 | 60秒 | TCP层更及时检测死连接 |

### 带宽消耗

- 优化前：每 30 秒发送 1 个心跳包（约 100 字节）
- 优化后：每 20 秒发送 1 个心跳包（约 100 字节）

带宽增加约 50%，但对于日常消息通信来说，心跳占用的带宽可以忽略不计。

## 经验总结

1. **WebSocket 连接稳定性需要多层次保障**。应用层心跳、TCP keepalive、重连策略，三者配合使用才能保证连接的可靠性。

2. **心跳间隔要留足缓冲空间**。不要让心跳间隔太接近服务器的超时阈值，网络稍有抖动就会出问题。

3. **重连策略要使用指数退避**。避免频繁重连触发服务器限流，导致更长时间无法连接。

4. **监控是保障**。添加心跳成功率和连接断开次数的监控，可以第一时间发现连接问题，而不是等用户投诉才知道。

5. **定期检查和优化**。随着业务增长和网络环境变化，原有的心跳配置可能不再适用，需要定期 review 和调整。

## 延伸阅读

- [钉钉开放平台 Stream 模式文档](https://open.dingtalk.com/document/stream/overview)
- [WebSocket 心跳保活最佳实践](https://www.rfc-editor.org/rfc/rfc6455#section-5.5.2)
- [TCP Keepalive 详解](https://www.tldp.org/HOWTO/html_single/TCP-Keepalive-HOWTO/)

## 结语

这次问题虽然最终解决了，但排查过程让我深刻认识到 WebSocket 连接保活的重要性。**连接建立只是开始，保持连接稳定才是真正的挑战。**

心跳机制看似简单，实际上涉及客户端配置、网络状况、服务器策略等多个方面。任何一环出了问题，都可能导致连接意外断开。

希望这篇文章能帮到你。如果你也有类似的排查经历，欢迎在评论区分享。

---

*作者：小六，一个在上海努力搬砖的程序员*
