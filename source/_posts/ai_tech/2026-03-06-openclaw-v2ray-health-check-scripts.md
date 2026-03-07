---
title: OpenClaw Gateway 与 V2Ray 代理自动化健康检查脚本实战
categories:
  - ai_tech
tags:
  - 技术
  - 运维
  - 自动化
  - 健康检查
  - OpenClaw
cover: 'https://picsum.photos/seed/tech0306/1280/720'
coverWidth: 1280
coverHeight: 720
date: 2026-03-06 21:30:00
---

## 前言

在运维工作中，健康检查是保障服务稳定性的重要一环。本文将详细介绍如何为 OpenClaw Gateway 和 V2Ray 代理服务编写自动化健康检查脚本，实现问题的早发现、早处理。

## 背景

我们的自动化运维系统依赖于两个核心服务：

1. **OpenClaw Gateway**：负责接收和处理用户请求，是整个系统的入口
2. **V2Ray 代理**：负责转发外网请求，确保系统能够访问外部 API

这两个服务一旦出问题，整个自动化运维系统就会瘫痪。因此，建立完善健康检查机制至关重要。

## 环境信息

| 服务 | 检查内容 | 位置 |
|------|---------|------|
| OpenClaw Gateway | 进程状态、Web UI 可用性 | VM151、VM152 |
| V2Ray 代理 | 进程状态、代理连通性 | ***.***.***.182 |

## 脚本设计

### 1. OpenClaw Gateway 健康检查脚本

```bash
#!/bin/bash

# OpenClaw Gateway 健康检查脚本
# 路径：/usr/local/bin/codex-health-check.sh

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================="
echo "OpenClaw Gateway 健康检查"
echo "检查时间: $(date)"
echo "========================================="

# 检查 Gateway 进程是否在运行
echo -n "[1/2] 检查进程状态... "
if pgrep -f "openclaw-gateway" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ 运行中${NC}"
    PROCESS_STATUS=0
else
    echo -e "${RED}✗ 未运行${NC}"
    PROCESS_STATUS=1
fi

# 检查 Web UI 是否可访问
echo -n "[2/2] 检查 Web UI... "
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:18789/api/status 2>/dev/null)
if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ 正常 (HTTP $HTTP_CODE)${NC}"
    UI_STATUS=0
else
    echo -e "${RED}✗ 异常 (HTTP $HTTP_CODE)${NC}"
    UI_STATUS=1
fi

# 总结
echo "========================================="
if [ $PROCESS_STATUS -eq 0 ] && [ $UI_STATUS -eq 0 ]; then
    echo -e "${GREEN}总体状态: 正常${NC}"
    exit 0
else
    echo -e "${RED}总体状态: 异常${NC}"
    exit 1
fi
```

### 2. V2Ray 代理健康检查脚本

```bash
#!/bin/bash

# V2Ray 代理健康检查脚本
# 路径：/usr/local/bin/proxy-health-check.sh

# 配置
PROXY_IP="***.***.***.182"
PROXY_PORT="1080"
TEST_URL="https://www.google.com"

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================="
echo "V2Ray 代理健康检查"
echo "检查时间: $(date)"
echo "========================================="

# 检查 V2Ray 进程是否在运行
echo -n "[1/2] 检查进程状态... "
if pgrep -f "v2ray" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ 运行中${NC}"
    PROCESS_STATUS=0
else
    echo -e "${RED}✗ 未运行${NC}"
    PROCESS_STATUS=1
fi

# 测试代理连通性
echo -n "[2/2] 检查代理连通性... "
HTTP_CODE=$(curl -x socks5://${PROXY_IP}:${PROXY_PORT} -s -o /dev/null -w "%{http_code}" ${TEST_URL} 2>/dev/null)
if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "301" ] || [ "$HTTP_CODE" = "302" ]; then
    echo -e "${GREEN}✓ 正常 (HTTP $HTTP_CODE)${NC}"
    PROXY_STATUS=0
else
    echo -e "${RED}✗ 异常 (HTTP $HTTP_CODE)${NC}"
    PROXY_STATUS=1
fi

# 总结
echo "========================================="
if [ $PROCESS_STATUS -eq 0 ] && [ $PROXY_STATUS -eq 0 ]; then
    echo -e "${GREEN}总体状态: 正常${NC}"
    exit 0
else
    echo -e "${RED}总体状态: 异常${NC}"
    exit 1
fi
```

## 使用方法

### 1. 安装脚本

```bash
# 创建脚本目录
sudo mkdir -p /usr/local/bin

# 保存脚本
sudo cp codex-health-check.sh /usr/local/bin/codex-health-check.sh
sudo cp proxy-health-check.sh /usr/local/bin/proxy-health-check.sh

# 添加执行权限
sudo chmod +x /usr/local/bin/codex-health-check.sh
sudo chmod +x /usr/local/bin/proxy-health-check.sh
```

### 2. 手动执行

```bash
# 检查 Gateway
/usr/local/bin/codex-health-check.sh

# 检查代理
/usr/local/bin/proxy-health-check.sh
```

### 3. 配置定时任务

```bash
# 编辑 crontab
crontab -e

# 添加定时任务（每5分钟检查一次）
*/5 * * * * /usr/local/bin/codex-health-check.sh >> /var/log/health-check/gateway.log 2>&1
*/5 * * * * /usr/local/bin/proxy-health-check.sh >> /var/log/health-check/proxy.log 2>&1
```

### 4. 配置告警通知（可选）

如果需要自动告警，可以在脚本中添加邮件或钉钉通知：

```bash
# 添加告警逻辑
if [ $PROCESS_STATUS -ne 0 ]; then
    # 发送告警通知
    curl -X POST "https://example.com/notify" -d "message=Gateway进程异常"
fi
```

## 进阶功能：自动修复

如果希望脚本具备自动修复能力，可以添加以下逻辑：

```bash
# 自动修复 Gateway
if [ $PROCESS_STATUS -ne 0 ]; then
    echo "尝试重启 Gateway..."
    sudo systemctl restart openclaw-gateway
    sleep 5
    # 再次检查
    if pgrep -f "openclaw-gateway" > /dev/null 2>&1; then
        echo "✓ 自动重启成功"
    else
        echo "✗ 自动重启失败，请人工介入"
    fi
fi
```

⚠️ **注意**：自动修复有一定风险，建议在测试环境验证后再启用。

## 常见问题排查

### 问题1：进程存在但服务无响应

可能原因：
- 进程卡死
- 端口被占用
- 资源耗尽

排查方法：
```bash
# 查看进程详情
ps aux | grep openclaw-gateway

# 查看端口占用
netstat -tlnp | grep 18789

# 查看系统资源
top -bn1 | head -20
```

### 问题2：代理连通性测试失败

可能原因：
- V2Ray 进程异常
- 网络策略变化
- 代理规则变更

排查方法：
```bash
# 查看 V2Ray 日志
tail -f /var/log/v2ray/access.log

# 测试直连
curl -I https://www.google.com

# 检查代理配置
cat /etc/v2ray/config.json
```

### 问题3：脚本执行权限不足

解决方法：
```bash
# 添加执行权限
chmod +x /usr/local/bin/codex-health-check.sh
chmod +x /usr/local/bin/proxy-health-check.sh
```

## 监控集成

可以将健康检查脚本接入现有监控系统：

### 1. Prometheus 监控

```yaml
- job_name: 'health-check'
  static_configs:
    - targets: ['localhost:9100']
  metrics_path: /metrics
```

### 2. Grafana 面板

创建自定义面板，展示：
- 服务 uptime
- 检查成功率
- 平均响应时间

### 3. 告警规则

```yaml
groups:
- name: health-check
  rules:
  - alert: ServiceDown
    expr: up{job="health-check"} == 0
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "服务宕机"
```

## 一键部署脚本

为了方便部署，我们提供了一键部署脚本：

```bash
#!/bin/bash

# 一键部署健康检查脚本

set -e

echo "开始部署健康检查脚本..."

# 创建目录
mkdir -p /usr/local/bin
mkdir -p /var/log/health-check

# 部署 Gateway 检查脚本
cat > /usr/local/bin/codex-health-check.sh << 'SCRIPT'
#!/bin/bash
# 内容见上文
SCRIPT

# 部署代理检查脚本
cat > /usr/local/bin/proxy-health-check.sh << 'SCRIPT'
#!/bin/bash
# 内容见上文
SCRIPT

# 设置权限
chmod +x /usr/local/bin/codex-health-check.sh
chmod +x /usr/local/bin/proxy-health-check.sh

# 配置定时任务
(crontab -l 2>/dev/null | grep -v health-check; echo "*/5 * * * * /usr/local/bin/codex-health-check.sh >> /var/log/health-check/gateway.log 2>&1"; echo "*/5 * * * * /usr/local/bin/proxy-health-check.sh >> /var/log/health-check/proxy.log 2>&1") | crontab -

echo "部署完成！"
echo "手动执行: /usr/local/bin/codex-health-check.sh"
echo "手动执行: /usr/local/bin/proxy-health-check.sh"
```

## 总结

通过部署自动化健康检查脚本，我们可以：

1. **早发现**：及时发现服务异常，避免问题扩大
2. **自动化**：减少人工检查工作量，提高效率
3. **可追溯**：记录检查日志，便于问题排查
4. **可告警**：集成告警通知，第一时间响应

建议将健康检查作为运维自动化的基础组件，配合监控告警使用，效果更佳。

---

*作者：小六，一个在上海努力搬砖的程序员*
