---
title: 记一次内网服务认证失败导致 IP 被封的故障排查与解决
categories:
  - ai_tech
tags:
  - 技术
  - 运维
  - 安全
  - 故障排查
  - 认证
cover: 'https://picsum.photos/seed/tech0423/1280/720'
coverWidth: 1280
coverHeight: 720
date: 2026-04-23 21:30:00
---

## 前言

内网服务的安全性往往被忽视，很多人认为"内网等于安全"，但实际上内网服务一旦出问题，影响范围可能比外网更大。最近我们就遇到了这样一个案例：某台运行着 Node-RED 的内网服务器，因为认证失败被 NAS 封了 IP。表面上看是一个简单的"认证失败"告警，深入排查后却发现了多个安全隐患。本文记录了完整的问题排查和解决过程，希望能给遇到类似问题的同学一些参考。

## 问题背景

### 业务场景

我们的自动化运维系统中，有一台跑着 Node-RED 的内网服务器，负责多个自动化流程的调度和管理。Node-RED 是一个低代码编程工具，用于连接各种硬件设备、API 和在线服务。通过 Node-RED，我们可以实现诸如定时任务、消息推送、数据采集等功能。

### 问题现象

- **故障时间**：某日凌晨
- **故障表现**：NAS 发来告警，某内网 IP 在凌晨因 Chat API 认证连续失败十次被封禁
- **影响范围**：该 IP 地址无法访问 NAS 相关服务
- **环境信息**：
  - 操作系统：Ubuntu（具体版本未记录）
  - 内网服务：Node-RED
  - NAS：群晖（Synology）系统
  - 端口：1880（Node-RED 默认端口）

### 初步分析

根据 NAS 告警信息，可能的原因有以下几种：

1. **认证信息过期**：调用方使用的 Token 或凭证已过期
2. **配置错误**：认证信息配置有误
3. **接口变更**：NAS Chat 接口有更新，导致认证方式变化
4. **安全问题**：存在恶意访问或暴力破解
5. **代码逻辑问题**：调用方没有正确处理认证失败的情况

## 排查过程

### 第一步：定位来源 IP

首先确认告警中的 IP 地址对应的具体机器：

```bash
# 查看 NAS 上的封禁记录（通常在日志中可以找到）
cat /var/log/synology_logs/chat.log | grep "blocked\|blocked_ip\|ban"

# 或者查看 NAS 管理界面的安全日志

# 确认 IP 对应的机器名（如果有 DNS 反向解析）
host <目标IP>

# 或者查看内网的 IP 地址分配表
cat /etc/hosts | grep <目标IP>
```

通过排查，确认该 IP 对应的是跑着 Node-RED 的那台内网服务器。

### 第二步：检查 Node-RED 进程和配置

登录到目标服务器，检查 Node-RED 的运行状态：

```bash
# 查看 Node-RED 进程
ps aux | grep node-red | grep -v grep

# 查看 Node-RED 版本
node-red --version

# 查看 Node-RED 配置文件
cat ~/.node-red/settings.js | grep -A5 "chat"

# 或者查看 flows 配置文件
cat ~/.node-red/flows.json | jq '.[] | select(.type=="chat")'
```

检查结果：Node-RED 进程正常运行，但存在一个很老的 flow 配置了调用 NAS Chat 的历史记录接口。

### 第三步：追溯认证失败原因

查看 Node-RED 日志，确认具体的认证失败原因：

```bash
# 查看 Node-RED 日志
journalctl -u node-red -f

# 或者查看 Node-RED 的控制台输出
cat ~/.node-red/.node-red.log

# 搜索认证相关的错误
grep -i "auth\|token\|401\|403" ~/.node-red/.node-red.log
```

发现问题原因：**NAS Chat 的 Token 早已过期**，但 Node-RED 中的 flow 还在持续调用这个接口，每次调用都会尝试使用过期的 Token 进行认证，从而触发认证失败。

### 第四步：分析根因（关键发现）

找到 Token 过期的原因后，我进一步检查了 NAS 的安全策略：

```bash
# 查看 NAS 的安全策略配置
cat /etc/synology/smsd.conf | grep -i "fail\|block\|auth"

# 或者登录 NAS 管理界面查看
# 安全策略 -> 防护 -> 封锁规则
```

结果发现 NAS 配置了"自动封锁"策略：**同一 IP 在 5 分钟内认证失败 10 次，将被自动封禁**。

这就是为什么过期的 Token 持续被调用会被封 IP 的原因。Node-RED 的 flow 每隔一段时间就会调用一次 NAS Chat 接口，每次调用都带着过期的 Token，每次都是认证失败。累积 10 次后，NAS 就自动封锁了这个 IP。

### 第五步：评估影响范围

被封禁后，该服务器将无法：

- 调用 NAS Chat 的历史记录接口
- 访问 NAS 的文件服务
- 访问 NAS 的其他 API

这将影响依赖 NAS 的自动化流程。

### 第六步：检查 Node-RED 端口暴露情况（更严重的问题）

正当我准备处理 Token 过期的简单问题时，我顺手检查了一下 Node-RED 的网络配置，结果发现了一个更大的安全隐患：

```bash
# 检查 Node-RED 监听的地址和端口
netstat -tlnp | grep 1880

# 检查防火墙规则
iptables -L -n | grep 1880

# 检查 Node-RED 的启动参数
ps aux | grep "node-red" | grep -v grep
```

**发现：Node-RED 的 1880 端口对全网监听，没有任何认证。**

这意味着在同一内网的任何人，只要知道这台机器的 IP，就能：

1. **访问 Node-RED 编辑器界面**
   - 虽然 Node-RED 编辑器默认需要输入用户名密码，但如果配置不当，可能完全没有认证

2. **调用 Node-RED 的 HTTP API**
   ```
   POST http://<IP>:1880/chat/gemini/receiveMsg
   POST http://<IP>:1880/oneCallControl/openPort
   POST http://<IP>:1880/push/工单系统/工单
   ```
   这些接口没有任何访问控制，直接调用即可执行对应操作

3. **获取敏感信息**
   - 通过 API 可以获取 flow 配置、变量值、连接凭证等

**这就是一个赤裸裸的内网横向渗透入口！**

## 解决方案

### 问题一：NAS 封 IP 解除

#### 1. 在 NAS 管理界面解除封锁

```bash
# 如果有 SSH 权限，也可以命令行解除
# 登录 NAS
ssh admin@<NAS_IP>

# 查看被封锁的 IP 列表
sudo cat /etc/hosts.deny

# 移除封锁记录（需要管理员权限）
sudo vi /etc/hosts.deny
# 删除对应的 IP 记录
```

#### 2. 配置自动解封（推荐）

```bash
# 在 NAS 的安全策略中配置
# 封锁规则 -> 自动解除封锁时间：设置为 30 分钟或 24 小时
```

### 问题二：修复过期的 Token

```bash
# 1. 登录 NAS Chat 开放平台
# 找到对应的应用，获取新的 Access Token

# 2. 更新 Node-RED flow 中的配置
# 编辑 flows.json，找到对应的 chat 节点
# 更新 token 字段

# 3. 或者使用环境变量管理敏感信息
# 在 Node-RED 的 settings.js 中添加：
# process.env.NAS_CHAT_TOKEN = "your_new_token"

# 4. 重启 Node-RED
systemctl restart nodered
```

### 问题三：修复 Node-RED 端口暴露问题（关键）

#### 方案一：限制监听地址（推荐）

```bash
# 修改 Node-RED 启动脚本，限制只监听本地
# 编辑 systemd 服务文件
sudo vi /etc/systemd/system/node-red.service

# 在 [Service] 部分添加：
Environment="NODE_OPTIONS=--max-http-header-size=100000"
ExecStart=/usr/bin/node-red -v -t /root/.node-red --listenLocal

# 或者修改 Node-RED 的 settings.js：
# 在 settings.js 中添加：
node-red/admin-ui: { middleware: require('connect')... }

# 更好的方式是配置 Node-RED 只监听 127.0.0.1
# 在启动参数中指定：
node-red --listenLocal 127.0.0.1
```

#### 方案二：配置防火墙规则

```bash
# 只允许特定 IP 访问 1880 端口
# 例如，只允许监控服务器（192.168.100.xxx）访问

iptables -A INPUT -p tcp --dport 1880 -s 192.168.100.0/24 -j ACCEPT
iptables -A INPUT -p tcp --dport 1880 -j DROP

# 保存规则
iptables-save > /etc/iptables/rules.v4
```

#### 方案三：配置 Node-RED 认证（必须）

```bash
# 在 Node-RED 的 settings.js 中启用认证：

adminAuth: {
    type: "credentials",
    users: [{
        username: "admin",
        password: "$2a$08$XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
        permissions: "*"
    }]
},

// 还需要为 HTTP 节点配置认证
httpNodeAuth: {
    user: "api_user",
    pass: "$2a$08$YYYYYYYYYYYYYYYY..."
},

httpRootAuth: {
    user: "root_user",
    pass: "$2a$08$ZZZZZZZZZZZZZZZZ..."
}
```

#### 方案四：使用反向代理配合认证

```bash
# 使用 nginx 反向代理并配置 Basic Auth

# 安装 nginx
sudo apt install nginx

# 配置 nginx
sudo vi /etc/nginx/sites-available/nodered

server {
    listen 443 ssl;
    server_name nodered.internal.example.com;

    ssl_certificate /etc/ssl/certs/nodered.crt;
    ssl_certificate_key /etc/ssl/private/nodered.key;

    location / {
        # Basic Auth
        auth_basic "Restricted Access";
        auth_basic_user_file /etc/nginx/.htpasswd;

        # 转发到 Node-RED
        proxy_pass http://127.0.0.1:1880;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}

# 创建密码文件
sudo apt install apache2-utils
sudo htpasswd -c /etc/nginx/.htpasswd admin

# 启用站点
sudo ln -s /etc/nginx/sites-available/nodered /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 问题四：优化 Node-RED flow 逻辑

```javascript
// 在调用外部 API 的节点中添加错误处理

// 1. 添加 Retry 配置，限制重试次数
// 在 HTTP Request 节点中设置：
maxRetries: 3
retryDelay: 5000

// 2. 添加错误处理分支
// 当收到 401/403 响应时，停止流程并发送告警

// 3. 添加 Token 过期检测
// 在每次请求前检测 Token 是否过期
// 如果 Token 过期，自动刷新或发送告警

// 示例：检测 Token 有效期
function checkTokenExpiry() {
    const tokenExpiry = context.get('nas_token_expiry') || 0;
    const now = Date.now();
    if (now > tokenExpiry) {
        node.warn('NAS Token 已过期，请更新！');
        // 发送告警
        node.send({payload: {alert: 'NAS Token 过期'}});
        return false;
    }
    return true;
}
```

## 一键排查脚本

如果你遇到了类似的"认证失败导致 IP 被封"问题，可以使用以下脚本进行快速排查：

```bash
#!/bin/bash

# 内网服务认证失败导致 IP 被封 - 快速排查脚本

echo "=== 认证失败告警快速排查 ==="
echo ""

# 1. 检查 NAS 封禁记录
echo "1. 检查 NAS 封禁记录："
echo "   如果可以 SSH 到 NAS，执行："
echo "   sudo cat /etc/hosts.deny | grep <被封IP>"
echo ""

# 2. 确认目标机器
echo "2. 确认目标机器："
read -p "请输入被封禁的 IP 地址: " TARGET_IP
echo "   正在查询 $TARGET_IP ..."

# 3. 检查目标机器上的服务
echo "3. 检查目标机器上的服务："
ssh -o ConnectTimeout=5 nodered@$TARGET_IP "ps aux | grep -E 'node-red|nodered' | grep -v grep" 2>/dev/null || echo "   无法连接到目标机器"
echo ""

# 4. 检查端口暴露情况
echo "4. 检查端口暴露情况："
ssh -o ConnectTimeout=5 nodered@$TARGET_IP "netstat -tlnp | grep -E '1880|3000|8080'" 2>/dev/null || echo "   无法连接到目标机器"
echo ""

# 5. 检查认证配置
echo "5. 检查 Node-RED 认证配置："
ssh -o ConnectTimeout=5 nodered@$TARGET_IP "cat ~/.node-red/settings.js | grep -E 'auth|Auth|user|pass'" 2>/dev/null || echo "   无法连接到目标机器"
echo ""

# 6. 检查 Token 配置
echo "6. 检查 Token 配置："
ssh -o ConnectTimeout=5 nodered@$TARGET_IP "grep -r 'token\|Token' ~/.node-red/flows*.json 2>/dev/null | head -5" 2>/dev/null || echo "   无法连接到目标机器"
echo ""

# 7. 建议修复步骤
echo "7. 建议的修复步骤："
echo "   a. 登录 NAS 管理界面，手动解除 IP 封锁"
echo "   b. 更新 NAS Chat 的 Token"
echo "   c. 配置 Node-RED 只监听 localhost"
echo "   d. 启用 Node-RED 认证"
echo "   e. 限制 1880 端口的访问范围"
echo ""

echo "=== 排查完成 ==="
```

## 常见问题解答

**Q1：为什么 NAS 会自动封锁 IP？**

A：这是 NAS 的安全策略之一，目的是防止暴力破解攻击。当同一 IP 在短时间内认证失败次数达到阈值（通常是 5-10 次），NAS 会自动封禁该 IP。这是保护 NAS 安全的必要措施，但如果内部服务的认证配置不当，就会触发误封。

**Q2：Token 过期了为什么还要持续调用？**

A：这通常是程序设计问题。良好的 API 调用逻辑应该在收到 401/403 响应后：
1. 记录错误日志
2. 停止继续调用
3. 发送告警通知管理员
4. 等待人工介入更新 Token

但很多老旧的 flow 或脚本没有实现这个逻辑，导致即使 Token 过期也会持续调用。

**Q3：内网服务需要认证吗？**

A：**必须需要**。很多人认为"内网等于安全"，但实际上：
1. 内网中可能存在恶意用户或其他被入侵的机器
2. 内网服务一旦被攻陷，可以作为跳板进一步渗透
3. 内网服务往往包含更多敏感数据

因此，所有内网服务都应该配置认证，并且遵循最小权限原则。

**Q4：如何防止类似问题再次发生？**

A：建议采取以下措施：
1. **完善监控**：监控 Token 过期时间，提前告警
2. **错误处理**：API 调用必须做好错误处理，不要无限重试
3. **定期审计**：定期检查所有内网服务的认证配置
4. **最小暴露**：只暴露必要的端口，使用防火墙限制访问
5. **日志分析**：分析认证失败日志，及时发现异常

**Q5：Node-RED 如何配置才安全？**

A：Node-RED 安全配置要点：
1. **启用认证**：adminAuth、httpNodeAuth 必须配置
2. **限制监听**：只监听 127.0.0.1，不要对全网监听
3. **HTTPS**：生产环境必须使用 HTTPS
4. **定期更新**：及时更新 Node-RED 到最新版本
5. **访问控制**：使用防火墙限制访问来源

## 根因分析与预防措施

### 根因分析

这次问题的根本原因有两个层面：

**浅层原因**：NAS Chat Token 过期后，Node-RED 中的 flow 没有正确处理认证失败的情况，继续使用过期 Token 调用 API，触发了 NAS 的自动封锁机制。

**深层原因**：Node-RED 的 1880 端口对全网监听且没有任何认证，这是一个严重的安全配置失误。内网服务不等于安全服务，任何服务都应该配置认证和访问控制。

### 预防措施

1. **建立 Token 管理制度**：
   - 记录所有外部 API 的 Token 有效期
   - 设置 Token 过期前的自动告警（如提前 7 天）
   - 定期轮换 Token

2. **完善错误处理逻辑**：
   - 所有 API 调用必须处理 401/403 响应
   - 认证失败后停止重试，发送告警
   - 不要让程序在错误状态下"死循环"

3. **内网服务也必须认证**：
   - 所有 HTTP 服务都需要认证
   - 使用强密码策略
   - 定期更换密码

4. **限制端口暴露**：
   - 遵循"最小暴露"原则
   - 使用防火墙限制访问来源
   - 定期扫描端口，发现异常暴露

5. **定期安全审计**：
   - 定期检查内网服务的认证配置
   - 扫描所有端口，发现异常暴露
   - 分析认证失败日志，发现潜在问题

6. **监控告警**：
   - 监控认证失败次数
   - 监控 Token 剩余有效期
   - 监控异常访问行为

## 经验总结

1. **认证失败只是症状**：看到"认证失败"告警，不要只想着"Token 过期"这一层。认证失败往往是更深层问题的症状——为什么 Token 过期了还在被调用？为什么没有人知道这个老旧的 flow？

2. **内网不等于安全**：很多运维人员有一个误区，认为"只要在内网就不会有问题"。但实际上，内网服务的安全问题往往比外网更隐蔽，因为大家默认信任内网。

3. **老旧配置是安全盲区**：老旧的 flow、老旧的 token、老旧的配置——这些才是真正的安全盲区。它们往往被遗忘在角落里，没有人知道它们存在，但它们一直在运行，一直在积累风险。

4. **自动化需要容错**：自动化提高了效率，但也放大了错误。一个有 bug 的自动化脚本，可能在几分钟内触发成百上千次错误请求，导致服务瘫痪或 IP 被封。

5. **监控要全面**：不仅要看服务是否正常运行，还要看认证是否正常、Token 是否即将过期、错误率是否异常。监控不仅是运维的眼睛，也是安全的第一道防线。

## 结语

这次故障表面上是"NAS 封 IP"，实际上暴露了多个安全隐患：Token 过期没有处理、Node-RED 端口裸奔、认证机制缺失。这些问题单独看都不大，但叠加在一起就成了一个完整的安全漏洞。

安全无小事，内网服务也需要认真对待。希望通过本文的排查过程和解决方案，能帮助大家避免类似的"内网裸奔"问题。

---

*作者：小六，一个在上海努力搬砖的程序员*
