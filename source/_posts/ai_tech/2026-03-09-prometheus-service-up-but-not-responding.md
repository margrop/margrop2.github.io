---
title: Prometheus 监控显示服务 UP 但实际不可用的排查与修复实践
categories:
  - ai_tech
tags:
  - 技术
  - 运维
  - Prometheus
  - 监控
  - 问题排查
cover: 'https://picsum.photos/seed/tech0309/1280/720'
coverWidth: 1280
coverHeight: 720
date: 2026-03-09 21:30:00
---

## 前言

在使用 Prometheus 进行服务监控时，你是否遇到过这种情况：监控面板显示服务状态为 "UP"，但实际调用时却返回错误？本文将详细记录一次典型的"监控与实际不符"问题的完整排查过程，并提供实用的修复方案。

## 问题现象

### 监控面板状态
在 Prometheus 监控面板中，目标服务的健康检查状态显示为 "UP"，服务响应时间也在正常范围内：
- app-gateway: UP
- bot-svr: UP  
- openapi-svr: UP
- robot-svr: UP
- robot-task: UP

### 实际服务状态
但当通过实际业务接口进行测试时，发现：
- 部分接口返回 503 Service Unavailable
- 某些环境的 API 调用超时
- 日志中存在大量错误信息

## 问题分析

### 1. 健康检查机制分析

Prometheus 的监控通常依赖于服务暴露的 `/actuator/prometheus` 端点。这种监控方式存在以下局限性：

| 监控指标 | 检查内容 | 局限性 |
|---------|---------|--------|
| 服务进程状态 | 进程是否存活 | 无法检测业务逻辑错误 |
| 端口监听状态 | 端口是否开放 | 无法检测服务是否真正响应 |
| 健康检查端点 | /health 是否返回 200 | 可能只是应用层健康，不代表业务健康 |

### 2. 根因定位

经过深入排查，发现以下问题：

**问题一：服务实例部分宕机**
在某个测试环境中，部分服务实例已经宕机，但负载均衡器的健康检查机制将请求路由到了仅存的其他实例。因为还有实例在响应，所以 Prometheus 的健康检查仍然显示 "UP"。

**问题二：HTTP 503 错误的监控盲区**
服务返回 503 错误时，HTTP 响应码仍然是 200（因为是健康检查端点返回的），所以监控系统认为服务正常。

**问题三：跨区域网络延迟**
部分欧洲（prod-xx）和美国（prod-yy）区域的服务存在间歇性超时问题，表现为 "context deadline exceeded"，这是典型的跨境网络延迟问题。

### 3. 影响范围

根据 Prometheus 监控数据，本次问题影响以下环境：

| 环境 | 受影响服务 | 状态 |
|-----|-----------|------|
| dev-aliyun | bot-svr, openapi-svr, robot-svr, robot-task-trcr | DOWN |
| prod-xx | bot-svr, openapi-svr, robot-svr, sch-tsk | DOWN |
| prod-yy | robot-rdr | DOWN |

## 解决方案

### 1. 修复服务实例

对于宕机的服务实例，执行以下操作：

```bash
# SSH 到目标服务器
ssh root@<target-server>

# 检查服务状态
systemctl status <service-name>

# 重启服务
systemctl restart <service-name>

# 验证服务是否正常
curl -f http://localhost:8080/health
```

### 2. 优化监控配置

**方案一：增加业务健康检查**

在服务的健康检查端点中添加更全面的检查：

```yaml
# application.yml
management:
  endpoints:
    web:
      exposure:
        include: health,info,prometheus
  endpoint:
    health:
      show-details: always
      probes:
        enabled: true
  health:
    livenessState:
      enabled: true
    readinessState:
      enabled: true
    db:
      enabled: true
    redis:
      enabled: true
    custom:
      enabled: true
```

**方案二：配置告警规则**

```yaml
# prometheus/rules/service-alerts.yml
groups:
  - name: service_health
    rules:
      - alert: ServiceDown
        expr: up == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "服务 {{ $labels.instance }} 已宕机"
          
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "服务 {{ $labels.instance }} 错误率过高"
```

### 3. 网络问题处理

对于跨境网络延迟问题，建议：

1. **增加超时时间**
```yaml
# Prometheus 抓取配置
scrape_configs:
  - job_name: '海外服务'
    scrape_timeout: 30s  # 增加超时时间
    scrape_interval: 2m  # 减少检查频率
```

2. **添加网络质量监控**
```yaml
- alert: HighLatency
  expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 5
  for: 10m
  labels:
    severity: warning
```

## 一键排查脚本

当遇到类似问题时，可以使用以下脚本进行快速排查：

```bash
#!/bin/bash

# 服务健康快速检查脚本

echo "========== 服务状态检查 =========="

# 检查 Prometheus targets
curl -s http://<prometheus-addr>:9090/api/v1/targets | \
  jq '.data.activeTargets[] | select(.health=="down") | {job: .labels.job, instance: .labels.instance, error: .lastError}'

echo ""
echo "========== 错误率检查 =========="

# 检查最近5分钟错误率
curl -s "http://<prometheus-addr>:9090/api/v1/query?query=rate(http_server_requests_seconds_count{status=~'5..'}[5m])" | \
  jq '.data.result[] | {instance: .metric.instance, error_rate: .value[1]}'

echo ""
echo "========== 响应时间检查 =========="

# 检查P99响应时间
curl -s "http://<prometheus-addr>:9090/api/v1/query?query=histogram_quantile(0.99, rate(http_server_requests_seconds_bucket[5m]))" | \
  jq '.data.result[] | {instance: .metric.instance, p99: .value[1]}'
```

## 常见问题解答

**Q：为什么监控显示 UP 但服务实际不可用？**

A：可能的原因包括：健康检查端点只检查进程存活而不检查业务逻辑；负载均衡将请求路由到了少数正常实例；服务返回了 HTTP 200 但业务处理失败。建议增加更全面的健康检查和业务指标监控。

**Q：如何快速定位是服务问题还是网络问题？**

A：先在服务端本地测试服务是否正常（curl localhost:端口），如果本地正常但远程不行，那基本是网络问题。如果本地也不正常，那就是服务本身的问题。

**Q：跨境服务响应慢应该如何优化？**

A：可以考虑以下方案：1）增加监控超时时间；2）使用 CDN 加速静态资源；3）在当地部署服务副本；4）实施多区域容灾策略。

**Q：Prometheus 告警阈值应该如何设置？**

A：建议根据业务的实际负载和历史数据进行调优。初始可以设置较宽松的阈值，观察一段时间后再逐步收紧。对于关键服务，优先设置"服务不可用"告警，其次再考虑性能告警。

**Q：如何避免监控"虚假绿色"的问题？**

A：1）增加业务层面的健康检查，不仅检查进程，还要检查核心业务逻辑；2）配置服务依赖检查，确保下游服务不可用时能及时发现；3）定期进行故障演练，验证监控的有效性。

## 经验总结

1. **监控需要分层次**：基础设施监控、应用监控、业务监控，每一层都很重要
2. **健康检查要全面**：不能只看进程是否在跑，还要看业务是否正常
3. **告警要有策略**：区分关键告警和次要告警，避免告警疲劳
4. **网络问题要耐心**：跨境网络问题很多时候只能等待，别急着半夜起来改配置

## 参考资料

- [Prometheus 官方文档](https://prometheus.io/docs/)
- [Spring Boot Actuator 配置](https://docs.spring.io/spring-boot/docs/current/actuator/html/)
- [Prometheus 告警规则最佳实践](https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/)

---

*作者：小六，一个在上海努力搬砖的程序员*
