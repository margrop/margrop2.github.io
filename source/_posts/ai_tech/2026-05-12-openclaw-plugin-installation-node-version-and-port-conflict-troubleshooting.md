---
title: 记一次 OpenClaw 飞书插件安装：Node版本不匹配与端口占用问题排查全记录
categories:
  - ai_tech
tags:
  - 技术
  - 运维
  - OpenClaw
  - 飞书
  - Node.js
  - 问题排查
  - 端口冲突
cover: 'https://picsum.photos/seed/tech0512/1280/720'
coverWidth: 1280
coverHeight: 720
date: 2026-05-12 21:30:00
---

## 前言

今天在给三台 OpenClaw Gateway 服务器批量安装飞书插件时，遇到了两个经典问题：**Node.js 版本不匹配**和**端口被旧进程占用**。本文将详细记录整个排查和解决过程，希望能给遇到类似问题的同学一些参考。

## 问题背景

### 任务描述

需要在 VM151、VM152、VM153 三台服务器上安装 `@openclaw/feishu` 插件，并通过 WebSocket 模式连接飞书开放平台。

### 环境信息

- **操作系统**：Ubuntu 24.04
- **OpenClaw Gateway**：运行在 18789 端口
- **Node.js**：系统默认 v18，部分插件需要 v22

### 问题现象

**VM151**：安装过程顺利，重启后飞书 WebSocket 直接连接成功。

**VM152**：安装时报错 `Error: The module './dist/index.js' does not exist`。重启服务时提示 `Port 18789 is already in use`。

**VM153**：安装顺利，连接成功，但存在一个无关的钉钉插件 TypeScript 编译警告。

## 问题一：Node.js 版本不匹配

### 错误信息

```
Error: The module './dist/index.js' does not exist
```

### 排查过程

#### 第一步：确认错误发生的位置

插件安装时出现这个错误，说明插件的构建产物（`dist/index.js`）没有被正确生成或者不被识别。

但仔细看错误提示，发现问题可能不是插件本身，而是 Node.js 环境。`./dist/index.js` 这个路径是一个相对路径，Node.js 在解析这个路径时出了问题，很可能是版本兼容性问题。

#### 第二步：检查 Node.js 版本

```bash
# 检查当前 Node.js 版本
node --version

# 输出
v18.17.0
```

系统默认的 Node.js 是 18.17.0。而某些新的 OpenClaw 插件需要 Node.js 22 才能运行。

#### 第三步：检查是否有 nvm

```bash
# 检查是否有 nvm
command -v nvm

# 或者
ls -la ~/.nvm/nvm.sh
```

如果系统里有 nvm，可以用它来切换 Node.js 版本。如果没有，则需要安装。

### 解决方案

#### 方案一：使用 nvm 切换 Node.js 版本

如果系统已经安装了 nvm：

```bash
# 加载 nvm
source ~/.nvm/nvm.sh

# 安装 Node.js 22
nvm install 22

# 切换到 Node.js 22
nvm use 22

# 确认版本
node --version
# 应该输出 v22.x.x
```

#### 方案二：安装 nvm（如果没有）

```bash
# 下载并安装 nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.0/install.sh | bash

# 重新加载 shell 配置
exec $SHELL

# 安装 Node.js 22
nvm install 22

# 设置默认版本
nvm alias default 22
```

#### 方案三：直接下载 Node.js 22

如果不习惯用 nvm，也可以直接下载 Node.js 22：

```bash
# 下载 Node.js 22
cd /tmp
wget https://nodejs.org/dist/v22.14.0/node-v22.14.0-linux-x64.tar.xz

# 解压到 /usr/local
sudo tar -xf node-v22.14.0-linux-x64.tar.xz -C /usr/local --strip-components=1

# 确认版本
node --version
```

### 验证步骤

```bash
# 在 Node.js 22 环境下重新安装插件
source ~/.nvm/nvm.sh && nvm use 22
openclaw plugin add @openclaw/feishu

# 如果安装成功，重启 Gateway
systemctl restart openclaw-gateway

# 检查日志
journalctl -u openclaw-gateway -n 50
```

## 问题二：端口被旧进程占用

### 错误信息

```
Error: Port 18789 is already in use
```

### 排查过程

#### 第一步：确认端口占用情况

```bash
# 检查端口 18789 是否被占用
ss -tlnp | grep 18789

# 输出示例
tcp  0  0  0.0.0.0:18789  0.0.0.0:*  LISTEN  123456/openclaw-ga
```

有进程在监听端口 18789，PID 是 123456。

#### 第二步：检查进程详情

```bash
# 查看进程详细信息
ps -p 123456 -o pid,ppid,etime,cmd,user

# 示例输出
PID   PPID  ELAPSED   CMD                          USER
123456  1    15-00:00:00  /opt/openclaw/openclaw-gateway  root
```

关键信息：
- 进程已经运行了 15 天
- PPID 是 1（说明是通过 systemd 或直接 init 启动的）
- 进程名是 `openclaw-gateway`，不是 `openclaw-gateway.service`

#### 第三步：检查 systemd 服务状态

```bash
# 检查 Gateway 服务状态
systemctl status openclaw-gateway

# 示例输出
● openclaw-gateway.service - OpenClaw Gateway
   Loaded: loaded (/etc/systemd/system/openclaw-gateway.service; enabled; vendor preset: enabled)
   Active: inactive (dead) since Mon 10:30:00 2026; 2h ago
```

服务状态显示 `inactive (dead)`，但端口却被占用。说明**占用端口的进程不是通过 systemd 启动的**。

### 问题根因

这种情况下，通常是因为：

1. **手动启动了进程**：有人直接运行了 `./openclaw-gateway`，没有通过 systemd
2. **升级时的遗留**：旧版本进程没有被正确退出
3. **脚本残留**：启动脚本里既有 systemd 启动又有直接运行

对于 VM152 的情况，最可能的原因是：**之前有人手动启动了一个 Gateway，后来用 systemd 重启服务时，旧的进程没有被清理**。

### 解决方案

#### 步骤一：杀掉旧进程

```bash
# 先确认这个进程是否可以安全杀掉
ps -p 123456 -o pid,etime,cmd

# 如果确认是旧进程，杀掉它
kill 123456

# 等待几秒，确认进程已退出
sleep 2
ss -tlnp | grep 18789
```

#### 步骤二：确保 systemd 能正确管理服务

```bash
# 检查服务是否 enabled
systemctl is-enabled openclaw-gateway

# 如果不是 enabled，启用它
systemctl enable openclaw-gateway

# 重启服务
systemctl restart openclaw-gateway

# 检查服务状态
systemctl status openclaw-gateway
```

#### 步骤三：验证端口监听

```bash
# 验证端口现在由 systemd 服务监听
ss -tlnp | grep 18789

# 确认是 systemd 启动的进程
ps aux | grep openclaw-gateway | grep -v grep
```

### 一键解决方案脚本

如果你经常遇到这个问题，可以使用以下脚本：

```bash
#!/bin/bash
# openclaw-gateway-port-fix.sh
# 用于清理占用 18789 端口的旧进程并重启服务

PORT=${1:-18789}
SERVICE_NAME="openclaw-gateway"

echo "=== OpenClaw Gateway 端口冲突修复脚本 ==="
echo ""

# 1. 检查端口占用
echo "1. 检查端口 ${PORT} 占用情况..."
 ss -tlnp | grep ":${PORT} " || echo "端口未被占用"
echo ""

# 2. 找到占用进程
echo "2. 分析占用进程..."
PID=$(ss -tlnp | grep ":${PORT} " | grep -oP 'pid=\K\d+' | head -1)
if [ -n "$PID" ]; then
    ps -p $PID -o pid,ppid,etime,user,cmd
    echo ""
    
    # 3. 检查是否是 systemd 管理的进程
    echo "3. 检查进程来源..."
    SYSTEMD_PID=$(systemctl show --property=MainPID --value ${SERVICE_NAME} 2>/dev/null)
    if [ "$PID" = "$SYSTEMD_PID" ]; then
        echo "进程由 systemd 管理 (PID=$PID)，可能是服务启动失败"
        echo "检查日志：journalctl -u ${SERVICE_NAME} -n 50"
        systemctl status ${SERVICE_NAME}
    else
        echo "进程 $PID 不是由 systemd 管理（systemd 认为 MainPID=$SYSTEMD_PID）"
        echo "这是旧进程残留，正在清理..."
        
        # 4. 清理旧进程
        echo "4. 清理旧进程..."
        kill $PID
        sleep 2
        
        # 5. 确认清理成功
        if ss -tlnp | grep -q ":${PORT} "; then
            echo "警告：端口仍被占用，尝试强制杀掉"
            kill -9 $PID
            sleep 1
        fi
    fi
else
    echo "端口未被占用"
fi
echo ""

# 6. 重启服务
echo "5. 重启 ${SERVICE_NAME} 服务..."
systemctl restart ${SERVICE_NAME}
sleep 2

# 7. 验证结果
echo "6. 验证结果..."
if systemctl is-active ${SERVICE_NAME}; then
    echo "✅ 服务运行正常"
    ss -tlnp | grep ":${PORT} "
else
    echo "❌ 服务启动失败，检查日志："
    systemctl status ${SERVICE_NAME} --no-pager
    journalctl -u ${SERVICE_NAME} -n 20 --no-pager
fi
```

使用方法：

```bash
# 保存脚本
sudo tee /usr/local/bin/openclaw-gateway-port-fix.sh << 'EOF'
# (粘贴上面的脚本内容)
EOF

# 添加执行权限
sudo chmod +x /usr/local/bin/openclaw-gateway-port-fix.sh

# 执行脚本
sudo /usr/local/bin/openclaw-gateway-port-fix.sh
```

## 问题三：插件加载但有 TypeScript 错误

### 问题描述

VM153 上的钉钉连接器（dingtalk-connector）有一个 TypeScript 编译错误：

```
Error: Cannot find entry module for TypeScript: './dist/index.js'
```

### 分析

这个错误不影响飞书插件，因为钉钉插件和飞书插件是独立的。如果钉钉插件加载失败，飞书插件仍然可以正常工作。

VM153 的情况验证了这一点——钉钉插件有错误，但飞书 WebSocket 连接正常。

### 处理建议

如果需要修复钉钉插件的错误，可以：

1. **更新插件版本**：
```bash
openclaw plugin update @openclaw/dingtalk
```

2. **重新编译 TypeScript**：
```bash
cd ~/.openclaw/plugins/dingtalk-connector
npm run build
```

3. **如果不需要钉钉功能，可以禁用插件**：
```bash
# 在配置文件中禁用
openclaw config set plugins.dingtalk.enabled false
systemctl restart openclaw-gateway
```

## 预防措施

### 1. Node.js 版本统一

为了避免 Node.js 版本问题，建议在所有服务器上使用相同版本：

```bash
# 在配置管理工具中添加 Node.js 版本检查
# 或者使用 Docker 容器来隔离 Node.js 环境
```

### 2. 禁止手动启动 Gateway

建议通过 systemd 来管理所有 Gateway 服务，禁止手动运行：

```bash
# 在 /etc/openclaw/config.yml 中添加限制
gateway:
  # 只允许通过 systemd 启动
  allow_manual_start: false
```

### 3. 升级脚本中加入进程检查

在升级脚本中，先检查并清理旧进程：

```bash
#!/bin/bash
# openclaw-upgrade.sh

# 1. 检查并停止旧服务
echo "停止旧服务..."
systemctl stop openclaw-gateway || true

# 2. 等待端口释放
echo "等待端口释放..."
sleep 3

# 3. 检查是否有残留进程
PID=$(ss -tlnp | grep ":18789 " | grep -oP 'pid=\K\d+' | head -1)
if [ -n "$PID" ]; then
    echo "发现残留进程 PID=$PID，正在清理..."
    kill $PID || true
    sleep 2
fi

# 4. 执行升级
echo "执行升级..."
npm install -g openclaw-gateway

# 5. 启动新服务
echo "启动新服务..."
systemctl start openclaw-gateway
```

### 4. 配置端口检查告警

添加一个监控任务，定期检查端口占用情况：

```bash
# 添加到 crontab
*/5 * * * * /usr/local/bin/check-gateway-port.sh
```

## 常见问题解答

**Q：为什么 Node.js 18 不能运行某些插件？**

A：某些新的 OpenClaw 插件使用了较新的 Node.js API（如 `fetch` 内置支持、`crypto` 模块更新等），这些 API 在 Node.js 18 中不可用或行为不同。建议使用 Node.js 22 或更高版本。

**Q：端口被占用但找不到进程怎么办？**

A：可能是僵尸进程或内核级别的占用。可以尝试：
1. `ps aux | grep -v grep | grep 18789` 确认进程
2. 检查是否有 socket 文件残留：`ls -la /var/run/openclaw-gateway.*`
3. 如果是 Docker 环境，检查容器网络配置

**Q：如何避免端口冲突再次发生？**

A：核心是确保所有 Gateway 服务都通过 systemd 管理：
1. 禁止手动 `./openclaw-gateway` 启动
2. 升级前先停止旧服务
3. 升级脚本中加入进程清理逻辑
4. 配置端口监控告警

**Q：systemctl 显示服务 active，但端口没监听怎么办？**

A：可能是服务启动后又崩溃了。检查方法：
```bash
# 查看服务状态和最新日志
systemctl status openclaw-gateway
journalctl -u openclaw-gateway -n 50

# 检查是否有崩溃
journalctl --system --priority=3 -n 20
```

**Q：钉钉插件报错但飞书正常，需要处理吗？**

A：如果只使用飞书通道，钉钉插件的报错可以忽略。如果需要同时使用钉钉和飞书，则需要修复钉钉插件的错误。建议检查插件版本和 Node.js 兼容性。

## 总结

今天遇到的三个问题，本质上都是**"环境一致性"和"历史遗留"**问题：

1. **Node.js 版本不匹配**：不同服务器的环境不一致，有些用 v18，有些用 v22
2. **端口被旧进程占用**：之前手动启动的进程没有被清理
3. **插件错误不影响主流程**：钉钉插件报错，但飞书功能正常

解决方案：
1. 使用 nvm 统一管理 Node.js 版本
2. 通过脚本自动化处理端口冲突
3. 理清插件之间的依赖关系，独立处理

核心经验是：**运维工作不仅仅是"把服务跑起来"，还要确保"环境可重复、问题可追溯"**。只有这样，才能避免同样的问题反复出现。

希望这篇文章对正在经历类似问题的同学有所帮助。如果有更好的实践方法，欢迎交流。

---

*作者：小六，一个今天装了三个插件查了三个问题的运维工程师*
*本文使用 picsum.photos 题图，授权可商用*
---
