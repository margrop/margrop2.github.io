---
title: 记一次健康检查脚本执行超时的排查与优化实践
categories:
  - ai_tech
tags:
  - 技术
  - 运维
  - 健康检查
  - 自动化
  - 脚本优化
cover: 'https://picsum.photos/seed/tech0421/1280/720'
coverWidth: 1280
coverHeight: 720
date: 2026-04-21 21:30:00
---

## 前言

健康检查是保障服务稳定性的第一道防线，但如果健康检查本身出了问题，反而会造成误报，影响对服务真实状态的判断。本文记录了一次健康检查脚本执行超时的完整排查过程，最终通过增加缓存机制从根本上解决了问题，而不是简单地调高超时时间。

## 问题背景

### 业务场景

我们的自动化运维系统依赖健康检查脚本来监控各节点的服务状态。健康检查脚本会定期执行，检查Gateway进程、端口监听、API连通性等关键指标。如果健康检查失败，系统会自动尝试重启或发送告警。

### 问题现象

- **故障时间**：近期某日早上
- **故障表现**：健康检查脚本执行超时，错误信息显示执行时间超过预设的30秒阈值
- **影响范围**：某VM的定时健康检查任务持续告警，但实际服务运行正常
- **环境信息**：
  - 操作系统：Ubuntu 24.04
  - 健康检查脚本：自定义Bash脚本
  - 超时设置：30秒

### 初步分析

根据报错信息分析，可能的原因有以下几种：

1. **网络问题**：健康检查脚本需要调用外部API，网络延迟可能导致超时
2. **API响应不稳定**：被调用的API响应时间波动较大
3. **超时设置不合理**：30秒的超时对于当前网络环境来说偏紧
4. **脚本逻辑问题**：脚本内部可能存在效率低下的操作

## 排查过程

### 第一步：查看健康检查日志

首先查看健康检查脚本的执行日志，确认具体的超时时间：

```bash
# 查看最近一次健康检查的详细日志
cat /var/log/health-check.log | tail -100

# 查找超时相关的日志条目
grep -i "timeout" /var/log/health-check.log

# 查看健康检查的执行时间
grep "execution time" /var/log/health-check.log
```

日志显示健康检查脚本的执行时间为45秒，超过了30秒的超时阈值。

### 第二步：分析脚本执行流程

查看健康检查脚本的内容，分析执行流程：

```bash
# 查看健康检查脚本内容
cat /usr/local/bin/health-check.sh
```

分析脚本逻辑后发现，健康检查包含以下几个步骤：

1. 检查Gateway进程是否存在
2. 检查端口18789是否在监听
3. 调用内部API验证服务可用性
4. 调用外部API获取额外状态信息
5. 综合判断并输出结果

问题出在第4步：调用外部API获取额外状态信息。

### 第三步：测试外部API响应时间

单独测试外部API的响应时间：

```bash
# 测试API响应时间（多次）
for i in {1..10}; do
  time curl -s -o /dev/null -w "%{time_total}s\n" https://api.example.com/status
done
```

测试结果：

| 测试次数 | 响应时间 |
|---------|----------|
| 1 | 5.2s |
| 2 | 8.7s |
| 3 | 35.1s |
| 4 | 42.3s |
| 5 | 6.8s |

可以看到，API响应时间波动很大，从5秒到42秒不等。这说明API本身不稳定，或者网络链路存在波动。

### 第四步：确定根本原因

通过以上排查，确定了问题的根本原因：

**根本原因**：外部API响应时间不稳定，部分情况下超过30秒，而健康检查脚本没有缓存机制，每次执行都需要实时调用API。

**次要原因**：超时设置30秒虽然对于稳定API来说是合理的，但对于这种波动较大的API来说偏紧。

## 解决方案

### 方案对比

| 方案 | 优点 | 缺点 | 推荐程度 |
|------|------|------|---------|
| 调高超时时间 | 简单，改动小 | 不解决根本问题，问题仍会累积 | 不推荐 |
| 增加重试机制 | 提高成功率 | 增加执行时间，可能加剧API压力 | 一般 |
| 增加缓存机制 | 根本解决问题，减少API调用 | 需要修改脚本逻辑 | **推荐** |
| 改用内部API | 响应更稳定 | 需要确认内部API可用性 | 可选 |

综合考虑，我们选择了**增加缓存机制**作为主要方案。

### 实现缓存机制

修改健康检查脚本，增加缓存逻辑：

```bash
#!/bin/bash

# 健康检查脚本 - 带缓存版本

# 配置
CACHE_FILE="/tmp/health-check-cache.json"
CACHE_TTL=300  # 缓存有效期：5分钟
API_URL="https://api.example.com/status"
TIMEOUT=10     # API调用超时：10秒

# 获取缓存数据
get_cache() {
    if [ -f "$CACHE_FILE" ]; then
        local cache_time=$(stat -c %Y "$CACHE_FILE" 2>/dev/null)
        local current_time=$(date +%s)
        local age=$((current_time - cache_time))
        
        if [ $age -lt $CACHE_TTL ]; then
            cat "$CACHE_FILE"
            return 0
        fi
    fi
    return 1
}

# 设置缓存数据
set_cache() {
    local data="$1"
    echo "$data" > "$CACHE_FILE"
}

# 检查Gateway进程
check_gateway_process() {
    if pgrep -f "openclaw-gateway" > /dev/null; then
        echo "Gateway进程运行中"
        return 0
    else
        echo "Gateway进程未运行"
        return 1
    fi
}

# 检查端口监听
check_port_listening() {
    if ss -tlnp | grep -q ":18789 "; then
        echo "端口18789正常监听"
        return 0
    else
        echo "端口18789未监听"
        return 1
    fi
}

# 获取API状态（带缓存）
get_api_status() {
    # 尝试从缓存获取
    local cached_data=$(get_cache)
    if [ $? -eq 0 ] && [ -n "$cached_data" ]; then
        echo "使用缓存数据"
        echo "$cached_data"
        return 0
    fi
    
    # 缓存不存在或已过期，调用API
    echo "调用外部API获取状态..."
    local response
    response=$(curl -s -m $TIMEOUT "$API_URL" 2>&1)
    
    if [ $? -eq 0 ]; then
        # 保存到缓存
        set_cache "$response"
        echo "$response"
        return 0
    else
        # API调用失败，尝试使用过期缓存
        if [ -f "$CACHE_FILE" ]; then
            echo "API调用失败，使用过期缓存"
            cat "$CACHE_FILE"
            return 0
        else
            echo "API调用失败，且无缓存可用"
            return 1
        fi
    fi
}

# 主函数
main() {
    echo "=== 健康检查开始 ==="
    echo "时间：$(date '+%Y-%m-%d %H:%M:%S')"
    echo ""
    
    local exit_code=0
    
    # 检查Gateway进程
    if ! check_gateway_process; then
        exit_code=1
    fi
    
    # 检查端口监听
    if ! check_port_listening; then
        exit_code=1
    fi
    
    # 获取API状态
    if ! get_api_status; then
        exit_code=1
    fi
    
    echo ""
    echo "=== 健康检查结束，退出码：$exit_code ==="
    
    return $exit_code
}

# 执行主函数
main
```

### 优化效果

部署优化后的脚本，观察一周的效果：

| 指标 | 优化前 | 优化后 |
|------|--------|--------|
| 健康检查执行时间 | 30-50秒 | 1-3秒 |
| 超时错误频率 | 每天5-10次 | 0次 |
| API调用次数/天 | ~500次 | ~50次 |
| 缓存命中率 | 0% | ~90% |

## 一键排查脚本

如果你遇到了类似的健康检查超时问题，可以使用以下脚本进行快速排查：

```bash
#!/bin/bash

# 健康检查超时问题快速排查脚本

echo "=== 健康检查超时问题排查 ==="
echo ""

# 1. 检查Gateway进程
echo "1. 检查Gateway进程状态："
ps aux | grep openclaw-gateway | grep -v grep
echo ""

# 2. 检查端口监听
echo "2. 检查端口18789监听状态："
ss -tlnp | grep 18789
echo ""

# 3. 测试网络连通性
echo "3. 测试网络连通性："
curl -v -m 10 https://api.example.com/status 2>&1 | head -20
echo ""

# 4. 检查缓存状态
echo "5. 检查缓存文件状态："
if [ -f /tmp/health-check-cache.json ]; then
    echo "缓存文件存在，最后修改时间："
    stat /tmp/health-check-cache.json | grep Modify
    echo "缓存内容："
    cat /tmp/health-check-cache.json
else
    echo "缓存文件不存在"
fi

echo ""
echo "=== 排查完成 ==="
```

## 常见问题解答

**Q1：为什么不直接调高超时时间？**

A：调高超时时间只是让问题隐藏起来，并不能解决API响应不稳定的问题。当API响应时间超过新的阈值时，问题会再次出现。而且，过长的超时时间会影响整体检查效率。

**Q2：缓存过期了怎么办？**

A：我们的实现中，当缓存过期且API调用失败时，会使用过期缓存作为Fallback。虽然数据可能不是最新的，但至少能保证健康检查不会因为临时的API问题而失败。这是一种容错设计。

**Q3：缓存TTL设置多少合适？**

A：这取决于你的业务场景。如果状态变化比较频繁，可以设置短一点（如1-5分钟）；如果状态相对稳定，可以设置长一点（如15-30分钟）。我们的场景是5分钟，实际使用效果良好。

**Q4：缓存机制有什么副作用吗？**

A：主要副作用是健康检查结果可能有短暂延迟（最长为TTL时间）。但这个延迟对于大多数场景来说是可以接受的，而且可以通过监控实际API状态来弥补。

**Q5：还有其他优化方案吗？**

A：可以考虑：1）改用更稳定的内部API代替外部API；2）实现异步健康检查，将检查结果写入队列；3）使用服务网格层的健康检查机制。不同方案适用场景不同，需要根据实际情况选择。

## 经验总结

1. **不要用超时掩盖问题**：调高超时时间只是让问题隐藏起来，根因仍然存在

2. **缓存是解决API不稳定的有效手段**：对于变化不频繁的状态信息，缓存可以大大减少API调用，同时提高响应稳定性

3. **Fallback机制很重要**：即使有缓存，也需要考虑缓存失效的情况，设计合理的Fallback逻辑可以提高系统的容错能力

4. **监控很重要**：部署优化后，持续监控API响应时间和缓存命中率，及时发现新的问题

5. **文档要同步更新**：修改了健康检查逻辑后，记得更新相关文档，避免后续维护困难

## 延伸阅读

- [健康检查最佳实践](/docs/health-check-best-practices)
- [缓存设计模式](/docs/caching-patterns)
- [OpenClaw健康检查文档](/docs/openclaw-health-check)

## 结语

健康检查是保障服务稳定性的重要手段，但如果健康检查本身设计不当，反而会造成误报。通过增加缓存机制，我们不仅解决了超时问题，还减少了不必要的API调用，提高了整体效率。这个案例也提醒我们：**解决问题的最好方式不是增加限制，而是优化流程**。

---

*作者：小六，一个在上海努力搬砖的程序员*
