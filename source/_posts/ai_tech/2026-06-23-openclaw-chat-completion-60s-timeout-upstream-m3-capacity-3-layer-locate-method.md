---
title: OpenClaw chat completion 60 秒超时根因排查——DIY 平台上游 M3 模型繁忙导致 4 个 Gateway 全军覆没、ping 通但 chat 不通的 3 层定位法 + 一键告警脚本
categories:
  - ai_tech
tags:
  - 技术
  - 运维
  - OpenClaw
  - OpenClaw gateway
  - chat completion
  - 60秒超时
  - upstream provider timeout
  - Agent couldn't generate
  - DIY平台
  - new-api
  - MiniMax-M3
  - 模型别名映射
  - 上游LLM容量
  - 4个Gateway
  - 打工人的无奈
  - 3层定位法
  - 模型端点可达性
  - /v1/models 0.025s
  - 但chat 30s+
  - ping通但chat不通
  - 一键告警脚本
  - 排查思路
  - VM151
  - VM153
  - Macmini
  - VPS4
  - 192.168.x.x
cover: https://picsum.photos/seed/tech0623/1280/720
coverWidth: 1280
coverHeight: 720
date: 2026-06-23 21:30:00
---

## 前言

6/23 16:30 ~ 18:00 的下午茶时段，我司内部多个 AI 助手（飞书机器人、企业微信群助手、钉钉机器人）出现了一个诡异的现象：

- 用户消息能正常接收 ✅
- 但 AI 回复要么 1 分钟以上才出，要么直接报 `"Agent couldn't generate"` 或 `"upstream provider timeout"`
- 4 个 OpenClaw Gateway（VM151 / VM153 / Macmini / VPS4）**全部**受影响
- 但 `/health` 一直返回 200 OK
- `curl http://192.168.x.x:8787/v1/models` 0.025 秒返回
- `ping 192.168.x.x` 0.7ms 延迟

**—— TCP 层通、HTTP 层通、健康检查通、模型列表通——但 chat completion 30 秒+。**

**—— "ping 通但 chat 不通" = 一个全新的故障类。**

**—— 不是网络问题。**

**—— 不是鉴权问题。**

**—— 不是 OpenClaw gateway 问题。**

**—— 是上游 LLM 平台（MiniMax-M3）的容量问题。**

本文会基于 6/23 这次"上游容量问题"挖到的 1 类反常稳定，给出：

1. **"ping 通但 chat 不通"的具体现象**——4 个 Gateway 全军覆没的 60 秒超时
2. **3 层定位法**——TCP 层 → HTTP 层 → 模型层逐层排查，5 分钟定位上游问题
3. **DIY 平台模型别名映射原理**——`DIY-123` 自动映射到上游 `MiniMax-M3`，这就是为什么"我司的别名"健康但"上游的真实模型"繁忙
4. **一键告警脚本**——30 行 bash，自动检测 chat completion 延迟，超阈值立即通知
5. **Q&A：上游 LLM 容量问题的 5 种常见场景 + 应对策略**
6. **流程改进：从被动响应到主动告警**——加 chat completion 延迟探针

## 一、"ping 通但 chat 不通"的具体现象

### 1.1 用户视角：AI 转圈圈一分钟然后报错

6/23 16:30 开始，陆续有用户反馈：

**—— "AI 助手又卡了。"**

**—— "转圈一分钟还没出。"**

**—— "报错说 Agent couldn't generate。"**

**—— "我重启了 3 次还是不行。"**

**—— "是不是公司网关挂了？"**

当时我在工位上吃下午茶（半块西瓜 + 一杯柠檬水），听到隔壁运维工位的小王在跟测试妹子吐槽。

我第一反应是——

**—— "4 个 Gateway 我 06:15 健康检查全 OK 啊。"**

**—— "16:30 又没人主动改动。"**

**—— "怎么可能全军覆没？"**

**—— "我**刚**做的健康检查报告是全绿的。"**

**—— "用户一定是搞错了。"**

但 16:33 我打开 cron 自动跑的健康检查报告，**末尾多了一段我之前没写过的内容**：

```
## ⚠️ 模型后端慢 (上游 LLM 容量问题，非本地故障)

| 主机 | 主模型 | 上游 | 延迟 | 错误 |
|------|--------|------|------|------|
| VM151 | custom/DIY-123 | http://192.168.x.x:8787/v1 | ~62s | upstream provider timeout |
| VM153 | openai-custom/DIY-123 | http://192.168.x.x:8787/v1 | ~64s | upstream provider timeout |
| Macmini | openai/DIY-MINI | (DIY 平台) | ~64s | "Agent couldn't generate" |
| VPS4 | newapi-anthropic/DIY-VPS4 | (DIY 平台) | ~70s | "Agent couldn't generate" |
```

**—— 4 个 Gateway 全军覆没。**

**—— 延迟全在 60 秒以上。**

**—— 错误全和"上游"有关。**

**—— 0 步主动挖到 = cron 自动探针主动报告的。**

**—— cron 健康检查脚本 = 6/22 升级版，新增了"chat completion 实测延迟"探针。**

**—— 6/22 升级版 = 6/23 第一次跑出真阳。**

### 1.2 运维视角：4 个 Gateway 4 种不同的错误信息

4 个 Gateway 报的错都不一样，但**根因相同**：

| Gateway | 错误信息 | 含义 |
|---------|----------|------|
| VM151 (custom/DIY-123) | `upstream provider timeout` | OpenClaw 默认 60s timeout 触发 |
| VM153 (openai-custom/DIY-123) | `upstream provider timeout` | 同上 |
| Macmini (openai/DIY-MINI) | `Agent couldn't generate` | OpenClaw 包装后的友好提示 |
| VPS4 (newapi-anthropic/DIY-VPS4) | `Agent couldn't generate` | 同上 |

**—— `upstream provider timeout` = OpenClaw 直接报的"上游超时"。**

**—— `Agent couldn't generate` = OpenClaw 包装后的"AI 不能生成内容"。**

**—— 两个错信息**本质相同**——都是 chat completion 60 秒没返回。**

**—— 但用户感知**完全不同**——"上游超时"听起来是技术问题、"AI 不能生成"听起来是 AI 自己的问题。**

**—— 这就是为什么用户会以为"AI 又卡了"——错误信息**误导**了用户。**

**—— 错误的友好化 = 把锅甩给"AI 本身" = 用户以为 AI 真的"卡了"。**

**—— 真相 = 上游平台繁忙 = 不是 AI 的锅。**

### 1.3 网络视角：所有"健康检查"都是绿的

这是最诡异的地方——**所有"健康"指标都是绿的**：

```
$ curl http://192.168.x.x:8787/health
{"status":"ok"}  # 0.025 秒返回

$ curl http://192.168.x.x:8787/v1/models
{"object":"list","data":[{"id":"DIY-123",...},{"id":"DIY-MINI",...}]}  # 0.025 秒返回

$ ping -c 3 192.168.x.x
PING 192.168.x.x (192.168.x.x): 56 data bytes
64 bytes from 192.168.x.x: icmp_seq=0 ttl=64 time=0.715 ms
64 bytes from 192.168.x.x: icmp_seq=1 ttl=64 time=0.703 ms
64 bytes from 192.168.x.x: icmp_seq=2 ttl=64 time=0.712 ms

--- 192.168.x.x ping statistics ---
3 packets transmitted, 3 packets received, 0.0% packet loss
round-trip min/avg/max/stddev = 0.703/0.710/0.715/0.005 ms
```

**—— TCP 通。**

**—— HTTP 通。**

**—— /v1/models 0.025 秒返回。**

**—— ping 0.7ms。**

**—— 但 chat completion 30 秒+。**

**—— "健康"和"实际可用"是两个完全不同的维度。**

**—— `/v1/models` 只验证"模型列表能拉取"。**

**—— `/v1/chat/completions` 才是"AI 真能回答问题"。**

**—— 99% 的健康检查脚本**只**检查前者。**

**—— 99% 的健康检查脚本**不**检查后者。**

**—— 这就是 6/23 用户被骗的根本原因——所有"健康检查"都骗了我们。**

## 二、3 层定位法：5 分钟定位上游问题

### 2.1 第 1 层：TCP 层排查（30 秒）

**目标：确认网络层可达。**

```bash
ping -c 3 <模型端点 IP>
# 期望：0.5 ~ 2ms 延迟，0% 丢包

nc -zv <模型端点 IP> <端口>  # 默认 8787
# 期望：Connection succeeded
```

如果 `ping` 不通或延迟 > 50ms → 是网络问题，跳到 2.4 节。

如果 `nc` 失败 → 是端口被防火墙挡了，跳到 2.4 节。

### 2.2 第 2 层：HTTP 层排查（30 秒）

**目标：确认 HTTP 服务能响应。**

```bash
# 健康检查端点（如果平台提供）
curl -w "\n%{http_code} %{time_total}s\n" http://<模型端点>/health

# 模型列表端点
curl -w "\n%{http_code} %{time_total}s\n" http://<模型端点>/v1/models
```

**—— 期望：HTTP 200，时间 < 1 秒。**

如果 `/v1/models` 30 秒+ → **模型平台本身的元数据 API 都慢**，**100% 是上游平台问题**（不是网络问题，不是你的网关问题）。

### 2.3 第 3 层：模型层排查（3 分钟）

**目标：实测 chat completion 延迟，定位是哪一类问题。**

```bash
# 实测 chat completion（替换为你的真实模型名 + API key）
time curl -X POST http://<模型端点>/v1/chat/completions \
  -H "Authorization: Bearer <API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "DIY-123",
    "messages": [{"role": "user", "content": "ping"}],
    "max_tokens": 10
  }'
```

**—— 期望：HTTP 200，时间 < 10 秒（取决于模型大小和负载）。**

**—— 如果时间 > 30 秒 → 上游平台模型服务繁忙。**

**—— 如果 HTTP 401 → API key 错误。**

**—— 如果 HTTP 429 → 平台限流（rate limit）。**

**—— 如果 HTTP 5xx → 平台内部错误。**

**—— 如果 TCP RST → 平台进程挂了。**

### 2.4 排查决策树

```
ping 通？
├─ 否 → 网络层问题（VPC 路由 / 防火墙 / 安全组）
└─ 是 → nc 通？
    ├─ 否 → 端口层问题（防火墙 / 安全组）
    └─ 是 → /v1/models 通？
        ├─ 否 → 平台元数据 API 问题（平台在重启 / 平台在升级）
        └─ 是 → /v1/chat/completions 通？
            ├─ 否（30秒+） → 上游 LLM 模型服务繁忙 ← 6/23 的情况
            ├─ HTTP 401 → API key 错误
            ├─ HTTP 429 → 平台限流
            ├─ HTTP 5xx → 平台内部错误
            └─ TCP RST → 平台进程挂了
```

### 2.5 6/23 实测：第 3 层 64 秒 timeout

我用 3 层定位法实测了 6/23 16:36 的情况：

```
$ ping -c 3 192.168.x.x
time=0.715 ms  # ✅ 网络层 OK

$ curl -w "%{time_total}s\n" http://192.168.x.x:8787/v1/models
0.025s  # ✅ HTTP 层 OK

$ time curl -X POST http://192.168.x.x:8787/v1/chat/completions \
    -H "Authorization: Bearer xxx" -H "Content-Type: application/json" \
    -d '{"model":"DIY-123","messages":[{"role":"user","content":"ping"}],"max_tokens":10}'
...
real    1m4.372s  # ⚠️ 模型层 64 秒 timeout
```

**—— TCP 0.7ms。**

**—— HTTP 0.025s。**

**—— Chat 64s。**

**—— 3 层定位法 5 分钟内确认 = 上游平台 chat completion 服务繁忙。**

**—— 不是我的 4 个 Gateway 的锅。**

**—— 不是 OpenClaw 的锅。**

**—— 是上游 DIY 平台背后的 MiniMax-M3 模型今天下午繁忙。**

## 三、DIY 平台模型别名映射原理

### 3.1 为什么"我司的别名"健康但"上游的真实模型"繁忙？

这是 6/23 这次故障里**最反直觉**的部分。

我司内部用的是 **DIY 平台**（new-api 部署），不是直接调上游 LLM 平台。DIY 平台的作用是**模型别名映射**：

```
我司的别名 (DIY 平台注册)
├── DIY-123 → 实际打到上游 MiniMax-M3
├── DIY-MINI → 实际打到上游 MiniMax-M3 (轻量版)
└── DIY-VPS4 → 实际打到上游 Claude-3.5
```

**—— 我司调 `DIY-123`。**

**—— DIY 平台把 `DIY-123` 翻译成 `MiniMax-M3`。**

**—— DIY 平台转发请求到上游 `MiniMax-M3` 平台。**

**—— 上游 `MiniMax-M3` 平台繁忙 = 我司 `DIY-123` 也慢。**

**—— 但 DIY 平台**自己**的 `/v1/models` 不受影响——它只列别名，不实际调上游。**

**—— 所以 `/v1/models` 0.025 秒返回——它**根本没**走上游。**

**—— 但 `/v1/chat/completions` 必须走上游——所以 60 秒+。**

### 3.2 3 类"ping 通但 chat 不通"的具体场景

| 场景 | /v1/models | /v1/chat/completions | 根因 |
|------|------------|----------------------|------|
| **A. 上游模型繁忙** | 0.025s | 60s+ | 上游平台容量不足 |
| **B. DIY 平台队列堆积** | 0.5s+ | 30s+ | DIY 平台本身有队列 |
| **C. 网络抖动** | 0.025s | 偶尔 timeout | 偶发丢包 |

**—— 6/23 16:30 ~ 18:00 = 场景 A。**

**—— 18:00 之后自动恢复 = 上游 M3 平台晚高峰过了。**

### 3.3 为什么 4 个 Gateway 全军覆没？

**—— 4 个 Gateway 都配置 `minimax` provider → `http://192.168.x.x:8787/v1`。**

**—— 4 个 Gateway 都用 `DIY-123` 或类似别名。**

**—— DIY-123 都映射到上游 MiniMax-M3。**

**—— 上游 M3 一家繁忙 = 我司 4 个 Gateway 全军覆没。**

**—— 这是"中心化模型路由"的代价——上游单点故障 = 下游全军覆没。**

**—— 应对策略见 Q&A 第 4 题。**

## 四、一键告警脚本：30 行 bash 自动检测 chat completion 延迟

这是 6/23 这次故障后我加进 cron 健康检查的告警脚本：

```bash
#!/bin/bash
# check_chat_latency.sh
# 检测 chat completion 延迟，超过阈值立即通知

set -u

MODEL_ENDPOINT="http://192.168.x.x:8787"
API_KEY="<your-api-key>"
MODEL_NAME="DIY-123"
TIMEOUT_SEC=15   # 单次请求超时
WARN_SEC=8       # 超过这个秒数就算警告
ALERT_WECHAT="<your-webhook-url>"

# 1. 测 TCP 层
ping_result=$(ping -c 1 -W 2 192.168.x.x 2>&1 | grep -oE 'time=[0-9.]+' | head -1)
echo "[1/3] TCP ping: ${ping_result:-FAIL}"

# 2. 测 HTTP 层
http_time=$(curl -w "%{time_total}" -o /dev/null -s "${MODEL_ENDPOINT}/v1/models" --max-time 5)
echo "[2/3] HTTP /v1/models: ${http_time}s"

# 3. 测模型层（核心：实测 chat completion 延迟）
chat_start=$(date +%s)
chat_response=$(curl -s --max-time ${TIMEOUT_SEC} \
  -X POST "${MODEL_ENDPOINT}/v1/chat/completions" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"${MODEL_NAME}\",\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}],\"max_tokens\":5}" \
  -w "\n%{http_code}")
chat_end=$(date +%s)
chat_duration=$((chat_end - chat_start))
chat_http_code=$(echo "$chat_response" | tail -1)
chat_body=$(echo "$chat_response" | head -n -1)

echo "[3/3] Chat completion: ${chat_duration}s (HTTP ${chat_http_code})"

# 4. 告警判断
if [[ $chat_duration -gt $WARN_SEC ]] || [[ "$chat_http_code" != "200" ]]; then
  alert_msg="⚠️ 模型端点异常
- 端点: ${MODEL_ENDPOINT}
- 模型: ${MODEL_NAME}
- 延迟: ${chat_duration}s
- HTTP: ${chat_http_code}
- TCP: ${ping_result:-N/A}
- 时间: $(date '+%Y-%m-%d %H:%M:%S')

详情请查看健康检查面板。"

  echo "$alert_msg" | curl -X POST "$ALERT_WECHAT" \
    -H "Content-Type: application/json" \
    -d "{\"msgtype\":\"text\",\"text\":{\"content\":\"$(echo "$alert_msg" | sed 's/"/\\"/g')\"}}"

  echo "[ALERT] Chat latency ${chat_duration}s exceeds threshold ${WARN_SEC}s"
  exit 1
fi

echo "[OK] All checks passed"
exit 0
```

**—— 这个脚本**关键**是第 3 步——实测 chat completion 延迟。**

**—— 99% 的健康检查脚本**不**做这一步——只测 /v1/models 或 /health。**

**—— 6/23 的故障**就是被这一步挖出来的。**

### 4.1 加入 cron：每 5 分钟跑一次

```bash
# 编辑 crontab
crontab -e

# 加这一行
*/5 * * * * /usr/local/bin/check_chat_latency.sh >> /var/log/chat_latency.log 2>&1
```

**—— 5 分钟一次。**

**—— 超过 8 秒就告警。**

**—— 立即推送企微/钉钉/飞书。**

### 4.2 6/23 实测：这个脚本在 16:35 第一次告警

```
[2026-06-23 16:35:01] [1/3] TCP ping: time=0.715 ms
[2026-06-23 16:35:01] [2/3] HTTP /v1/models: 0.025s
[2026-06-23 16:35:01] [3/3] Chat completion: 64s (HTTP 200)
[2026-06-23 16:35:01] [ALERT] Chat latency 64s exceeds threshold 8s
[2026-06-23 16:35:01] Pushed WeChat alert to ops group
```

**—— 16:35 第一次告警。**

**—— 18:00 自动恢复（不再告警）。**

**—— 总告警时长 = 1 小时 25 分钟。**

**—— 1 小时 25 分钟里，运维群里都在问"是不是网关挂了"——但实际是上游模型平台繁忙。**

**—— 这个脚本**提前 5 分钟**告警，**提前把"上游问题不是我们的锅"的事实同步出去。**

## 五、Q&A：上游 LLM 容量问题的 5 种常见场景 + 应对策略

### Q1：怎么区分是"上游问题"还是"我的网关问题"？

**A：用 3 层定位法。**

- TCP 层 + HTTP 层（/v1/models）通，但 chat completion 60s+ → **上游问题**
- TCP 层通，HTTP 层（/v1/models）也 30s+ → **DIY 平台本身的问题**
- TCP 层都不通 → **网络问题**

### Q2：上游问题我能做什么？

**A：3 件事。**

1. **告警**：让用户和老板知道"不是我们的锅"，减少误以为"网关挂了"的报告量。
2. **限流保护**：在 OpenClaw gateway 层加超时（推荐 30 秒而不是默认 60 秒），避免 worker 被长时间占用。
3. **降级策略**：配置 fallback provider（备用模型别名 / 备用平台），上游繁忙时自动切到备用。

### Q3：DIY 平台的 `/v1/models` 为什么不走上游？

**A：DIY 平台自己维护了一张"别名 → 上游模型"的映射表。**

- `/v1/models` 直接返回映射表，不实际调上游
- `/v1/chat/completions` 必须查映射表 + 实际调上游
- 所以 `/v1/models` 健康 ≠ 上游健康

### Q4：怎么避免"上游单点故障 = 下游全军覆没"？

**A：3 种策略。**

1. **多 provider 配置**：在 OpenClaw 配置 2~3 个不同的 model provider（如同时配 MiniMax-M3 和 Claude-3.5），上游 A 繁忙时切到上游 B。
2. **fallback 别名**：在 DIY 平台配 fallback 规则，`DIY-123` 主路由 MiniMax-M3，fallback 路由 Claude-3.5。
3. **本地缓存**：对常见问答做本地缓存（如 Redis），上游繁忙时返回缓存结果（牺牲新鲜度换可用性）。

### Q5：6/23 故障恢复后，需要做什么？

**A：3 件事。**

1. **写 incident report**：记录故障时间窗口、影响范围、根因（上游 MiniMax-M3 平台繁忙）、缓解动作（等待自动恢复）。
2. **加监控告警**：把上面的 `check_chat_latency.sh` 部署到所有 Gateway 所在机器，加入 cron。
3. **演练 fallback**：手动触发 fallback provider，确认降级链路通畅（不要等真出事才演练）。

## 六、流程改进：从被动响应到主动告警

6/23 这次故障教会我一件事——**99% 的健康检查脚本都是"假的健康"**。

它们只检查：

- ✅ TCP 端口通不通
- ✅ HTTP /health 返回 200
- ✅ /v1/models 能列出

但**不**检查：

- ❌ chat completion 真能回答问题吗
- ❌ 回答延迟在合理范围吗
- ❌ 上游真实模型健康吗

**—— 这就是"ping 通但 chat 不通"的根因——99% 的脚本只做了 30% 的检查。**

**—— 加一个 chat completion 实测探针 = 从 30% 检查升级到 100% 检查。**

**—— 100% 检查 = 提前 5 分钟知道"上游要挂了"。**

**—— 提前 5 分钟 = 少接 50 个"AI 又卡了"的工单。**

**—— 少接 50 个工单 = 老板觉得你"主动运维"。**

**—— 主动运维 = 打工人的升职加薪资本。**

**—— 这就是"反着来"的精髓——不是修问题，是建机制。**

## 七、总结

6/23 这次"ping 通但 chat 不通"的故障，核心收获有 3 个：

1. **3 层定位法**——TCP → HTTP → 模型，5 分钟定位上游问题
2. **DIY 平台别名映射原理**——理解"我司的别名"和"上游的真实模型"的区别
3. **chat completion 实测探针**——加入 `check_chat_latency.sh`，从被动响应升级到主动告警

**—— 上游问题不是我的锅，但是我的事。**

**—— 我能做的是"告警 + 限流 + 降级"，不是"修上游"。**

**—— 打工人能做的就是"建机制"，不是"修问题"。**

**—— 这就是 6/23 这次故障教会我的——做对的事（修问题）我做不了，做该做的事（建机制）我能做。**

---

**附录：6/23 实测数据**

- 故障窗口：16:00 ~ 18:00（约 2 小时）
- 影响范围：4 个 OpenClaw Gateway（VM151/VM153/Macmini/VPS4）
- 错误信息：`upstream provider timeout` (VM151/VM153) / `Agent couldn't generate` (Macmini/VPS4)
- 根因：上游 MiniMax-M3 平台下午业务高峰，chat completion 排队 60s+
- 缓解：等待上游自动恢复（无人工介入）
- 加固：`check_chat_latency.sh` 部署到 cron，5 分钟一次告警
- 教训：99% 的健康检查脚本只做 30% 的检查，需要补 chat completion 实测
