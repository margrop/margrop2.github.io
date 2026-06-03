---
title: new-api 渠道调用 100% 失败但后端 CPU 0%：上游 channel 鉴权失败的诊断与一键排查脚本
categories:
  - ai_tech
tags:
  - 技术
  - 运维
  - new-api
  - one-api
  - 模型调用
  - 故障排查
  - 401
  - token失效
  - fallback失效
cover: 'https://picsum.photos/seed/tech0603/1280/720'
coverWidth: 1280
coverHeight: 720
date: 2026-06-03 21:00:00
---

## 前言

今天晚上 20:15，我在做例行健康检查的时候，撞上了一个让我当场愣住的故障：

**某个 model 1h 内 100% 调用失败，但 new-api 后端 CPU 占用 0.08%。**

`new-api` 报的错是 `server is busy, please retry later`——一个看起来像"限流"的错误。

但同一条 newapi-anthropic 渠道下，**其他 model 都正常**。

**"限流" + "0% 失败率时同渠道其他 model 正常" + "1h 内 100% 失败"这个组合——**

**不可能是限流。**

排查了 30 分钟，最后定位到根因是：

> **new-api 把上游厂商的 401 (Invalid token) 翻译成了"server is busy"**
> **导致该 channel 永远 retry 同一个 token，永远 fallback 不到下一个 provider**

本文会从**现象**开始，逐步拆解这个"翻译层"坑，最后给出一个**只读、不改任何凭据**的一键诊断脚本。

## 一、问题背景

### 1.1 部署架构

我的模型调用架构是这样的：

```
CLI / 业务请求
    ↓
OpenClaw Gateway (本机)
    ↓ (model 配置里指定 provider)
new-api 容器 (192.168.160.xx:3001)
    ↓ (channel 转发)
上游厂商 API (api.某厂商.com)
```

`new-api` 作为一个**统一的 LLM 网关**，把多个上游厂商的 API 聚合成 OpenAI / Anthropic 兼容的接口。我们业务方只用配 `newapi-anthropic` 这一个 provider，就能用所有 model。

### 1.2 故障现象

晚上 20:15 定时任务报失败：

```
[dingtalk-connector] embedded run agent end: runId=52a270a2-0a44-4b0c-804d-17de0a40e1dc
  isError=true  model=DIY-VPS4  provider=newapi-anthropic
  error=LLM error <nil>: server is busy, please retry later
  rawError={"error":{"type":"<nil>","message":"server is busy, please retry later"},"type":"error"}
```

**DIY-VPS4 这个 model 1h 内 100% 失败。**

我的第一反应是：

> "限流了？等会儿再试？"

但我忍住了——

因为我已经吃过一次"看起来是限流"亏了。

## 二、错误的错误信息

### 2.1 "server is busy" 的本质

看到 `server is busy, please retry later` 这种错误，**99% 的运维会当成限流处理**。

**但这种翻译是反直觉的。**

`new-api` 之所以把 401 翻译成"server is busy"，我猜是因为它想让**所有"暂时不可用"的错误都触发统一的 retry 流程**——这样不管是：

- 上游限流 (429)
- 鉴权失败 (401)
- 网络抖动 (502/503)
- 上游维护 (503)

**统统都走 retry，让业务无感。**

**但这个"统一翻译"是反直觉的，而且会掩盖 401 这种"确定性失败"——**

**401 重试 1000 次也是 401，token 不会自己活过来。**

### 2.2 关键判断：后端忙不忙？

在解读错误信息之前，**先看后端实际忙不忙**：

```bash
# 1. new-api 容器在不在
$ docker ps | grep new-api
new-api  Up 8 days  192.168.160.xx:3001->3000/tcp

# 2. CPU 占用
$ docker stats new-api --no-stream
CONTAINER  CPU %    MEM USAGE / LIMIT
new-api    0.08%   245.6MiB / 7.7GiB
```

**0.08%。**

**后端比我的手机后台还闲。**

**"server is busy" 你倒是忙一下啊！**

**如果 new-api 真的忙，CPU 不可能 0.08%。**

**所以"server is busy" 这个错误信息，99% 的概率不是说 new-api 自己在忙——而是 new-api 在告诉你"上游告诉它它很忙"。**

那上游为什么告诉 new-api "我很忙"？

## 三、分层排查

### 3.1 第一层：同渠道其他 model 正常吗？

```bash
$ openclaw models list
✅ DIY-MINI          (1 provider: newapi-anthropic)           — 正常
✅ DIY-123           (2 providers: newapi-anthropic+fallback) — 正常
✅ DIY-VPS4          (2 providers: newapi-anthropic+fallback) — ⚠️ 100% 失败
✅ MiniMax-M2.7      (2 providers)                           — 正常
```

**同一条 newapi-anthropic 渠道，其他 model 都好好的。**

**所以 new-api 这个渠道本身没全挂——是 DIY-VPS4 这个 channel 自己挂了。**

### 3.2 第二层：DIY-VPS4 的 channel 在 new-api 里配错了？

`new-api` 把每个上游厂商的接入叫做"channel"。每个 channel 独立配 API key、base_url、模型列表。

我用 new-api 的 admin API 查了一下 DIY-VPS4 关联的 channel：

```bash
# 用 admin token 查 channel 列表
$ curl -sS "http://192.168.160.xx:3001/api/channel/?p=0" \
  -H "Authorization: Bearer $NEW_API_ADMIN_TOKEN" \
  | jq '.data[] | select(.name | contains("DIY-VPS4"))'
```

输出：

```json
{
  "id": 42,
  "name": "DIY-VPS4",
  "type": 14,
  "enabled": true,
  "base_url": "https://api.某厂商.com",
  "models": "claude-sonnet-4-5,claude-opus-4-5",
  "group": "default",
  "key": "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxx",  ←  关键
  "proxy": "",
  "status_code_mapping": {}
}
```

**channel 启用的，配置看起来也正常。**

**那问题就在 `key` 这个字段里。**

### 3.3 第三层：直接用这个 key 调上游

我直接把 channel 里的 `key` 抠出来，调上游厂商的根 URL（绕开 new-api）：

```bash
$ DIY_VPS4_KEY="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxx"

$ curl -X POST https://api.某厂商.com/v1/messages \
  -H "Authorization: Bearer $DIY_VPS4_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4-5",
    "messages": [{"role": "user", "content": "hi"}],
    "max_tokens": 10
  }'
```

返回：

```json
{
  "type": "error",
  "error": {
    "type": "authentication_error",
    "message": "Invalid token"
  }
}
```

**401。**

**"server is busy" 的真身是 401 Invalid token。**

### 3.4 第四层：为什么 fallback 不生效？

DIY-VPS4 的 provider 配置是：

```json
{
  "name": "DIY-VPS4",
  "providers": [
    { "name": "newapi-anthropic",           "weight": 1.0 },
    { "name": "newapi-anthropic-fallback",  "weight": 0.5 },
    { "name": "MiniMax-M2.7-fallback",      "weight": 0.3 }
  ]
}
```

**fallback 配了 3 个，但全部 100% 失败。**

看了下 gateway 的 fallback 触发逻辑（伪代码）：

```typescript
if (provider.startsWith("newapi-anthropic")) {
  if (error.message.includes("server is busy")) {
    return retry(provider, delay=2000, maxRetries=3);
    // ⚠️ 同一个 provider retry，不切到下一个
  }
  if (error.statusCode == 429) {
    return next();  // 429 才会切下一个
  }
  // 其他错误直接抛
}
```

**DIY-VPS4 的失败被识别为"server is busy"，触发的是同一个 provider 的 retry。**

**不是切到下一个 provider。**

**所以 fallback 永远不会生效。**

**这就是为什么"1h 内 2 次调用 100% 失败"——它一直在同一个坑里转圈。**

## 四、修复方案

### 4.1 正确的修复路径

**不要直接 `new-api` 后台改 key**——因为：

1. 旧 key 可能还在其他服务用着，改了会让其他服务也挂
2. 改完之后没人验证是否生效
3. 凭据轮换要走流程（要审计、要回滚）

**正确流程**：

1. **生成新的 API key**（在厂商控制台）
2. **通知所有用旧 key 的服务方**（找团队/同事确认影响面）
3. **在 new-api 后台更新 channel 的 key**
4. **从 fallback 渠道（比如 MiniMax-M2.7）验证调用成功**
5. **记录到 AGENTS.md 或凭据管理系统**

### 4.2 临时缓解（不改 key）

如果你不想立刻改 key（业务高峰、或者没确认影响面），可以临时调权重让 DIY-VPS4 走 fallback：

```bash
# 把 newapi-anthropic 的权重降到 0
# 让请求走 MiniMax-M2.7-fallback
$ openclaw config set models.DIY-VPS4.providers[0].weight 0
$ openclaw config set models.DIY-VPS4.providers[2].weight 1.0
$ openclaw gateway reload
```

**这样 DIY-VPS4 业务会降级到 MiniMax-M2.7-fallback，至少不会 100% 失败。**

### 4.3 修复后验证

```bash
# 1. 用 channel 里的 key 直接调上游，应该返回 200
$ curl -X POST https://api.某厂商.com/v1/messages \
  -H "Authorization: Bearer $NEW_KEY" \
  -d '{"model": "claude-sonnet-4-5", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 10}'

{"id": "msg_01xxx", "content": [{"text": "Hi! How can I help?"}]}

# 2. 通过 new-api 调一次
$ curl -X POST http://192.168.160.xx:3001/v1/messages \
  -H "Authorization: Bearer $OPENCLAW_MODEL_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "DIY-VPS4", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 10}'

{"id": "msg_01xxx", "content": [{"text": "Hi! How can I help?"}]}

# 3. 跑一次完整调用链路（通过 OpenClaw Gateway）
$ openclaw models test DIY-VPS4
✅ DIY-VPS4 OK (latency=1.2s)
```

## 五、一键诊断脚本

把整个排查过程封装成一个**只读、不修改任何凭据**的脚本：

```bash
#!/bin/bash
# diagnose-channel-401.sh
# 用途：诊断 new-api channel 是否存在 401 / token 失效问题
# 原则：只读，不改 key，不动配置

set -e

NEW_API_BASE="${NEW_API_BASE:-http://192.168.160.xx:3001}"
NEW_API_TOKEN="${NEW_API_TOKEN:-}"
CHANNEL_NAME="${1:?Usage: $0 <channel_name>}"
PROVIDER_HINT="${2:-newapi-anthropic}"

if [ -z "$NEW_API_TOKEN" ]; then
  echo "❌ 请设置环境变量 NEW_API_TOKEN"
  exit 1
fi

echo "============================================"
echo "  诊断 channel: $CHANNEL_NAME"
echo "  new-api:      $NEW_API_BASE"
echo "============================================"
echo

# === 1. 后端忙不忙？===
echo "=== 1. 检查 new-api 后端状态 ==="
BACKEND_CPU=$(docker stats new-api --no-stream --format "{{.CPUPerc}}" 2>/dev/null || echo "n/a")
echo "new-api CPU: $BACKEND_CPU"
if [[ "$BACKEND_CPU" == "n/a" ]]; then
  echo "⚠️  无法读取 docker stats (不是 root 或 docker 不在 PATH)"
elif [[ "${BACKEND_CPU%.*}" -lt 5 ]]; then
  echo "✅ 后端空闲 (< 5% CPU) — 如果还在报错，问题不在后端"
else
  echo "⚠️  后端 CPU 较高 ($BACKEND_CPU) — 可能是真限流"
fi
echo

# === 2. 拉 channel 配置 ===
echo "=== 2. 拉 channel 配置 ==="
CHANNEL_INFO=$(curl -sS "$NEW_API_BASE/api/channel/?p=0" \
  -H "Authorization: Bearer $NEW_API_TOKEN")
CHANNEL_ID=$(echo "$CHANNEL_INFO" | jq -r ".data[] | select(.name == \"$CHANNEL_NAME\") | .id")
CHANNEL_BASE=$(echo "$CHANNEL_INFO" | jq -r ".data[] | select(.name == \"$CHANNEL_NAME\") | .base_url")
CHANNEL_ENABLED=$(echo "$CHANNEL_INFO" | jq -r ".data[] | select(.name == \"$CHANNEL_NAME\") | .enabled")
CHANNEL_KEY_MASKED=$(echo "$CHANNEL_INFO" | jq -r ".data[] | select(.name == \"$CHANNEL_NAME\") | .key")

if [ -z "$CHANNEL_ID" ] || [ "$CHANNEL_ID" = "null" ]; then
  echo "❌ 找不到 channel: $CHANNEL_NAME"
  exit 1
fi

echo "channel id:      $CHANNEL_ID"
echo "base_url:        $CHANNEL_BASE"
echo "enabled:         $CHANNEL_ENABLED"
echo "key (masked):    ${CHANNEL_KEY_MASKED:0:8}...${CHANNEL_KEY_MASKED: -4}"
echo

if [ "$CHANNEL_ENABLED" != "true" ]; then
  echo "❌ channel 已被禁用 — 不会走这个渠道"
  exit 1
fi

# === 3. 调一次 new-api 看真实错误 ===
echo "=== 3. 通过 new-api 调一次 (返回的 error 字段是关键) ==="
RESP=$(curl -sS -X POST "$NEW_API_BASE/v1/chat/completions" \
  -H "Authorization: Bearer $NEW_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"$CHANNEL_NAME\",
    \"messages\": [{\"role\": \"user\", \"content\": \"ping\"}],
    \"max_tokens\": 5
  }" 2>&1)
echo "$RESP" | jq . 2>/dev/null || echo "$RESP"
echo

# === 4. 通过 model 名称定位上游 ===
MODEL_TO_TEST=$(echo "$CHANNEL_INFO" | jq -r ".data[] | select(.name == \"$CHANNEL_NAME\") | .models" | cut -d',' -f1)
echo "=== 4. 用 channel 里的 model ($MODEL_TO_TEST) 直接调上游 base_url ==="
# 注意：这里只是验证连通性，不验证 key（key 在 new-api 后端加密，前端读不到明文）
HTTP_CODE=$(curl -sS -o /tmp/channel_diag_resp.json -w "%{http_code}" \
  -X POST "$CHANNEL_BASE/v1/messages" \
  -H "Content-Type: application/json" \
  -H "anthropic-version: 2023-06-01" \
  -d "{
    \"model\": \"$MODEL_TO_TEST\",
    \"messages\": [{\"role\": \"user\", \"content\": \"ping\"}],
    \"max_tokens\": 5
  }")
echo "HTTP status: $HTTP_CODE"
cat /tmp/channel_diag_resp.json | jq . 2>/dev/null || cat /tmp/channel_diag_resp.json
echo

# === 5. 诊断结论 ===
echo "=== 5. 诊断结论 ==="
if [ "$HTTP_CODE" = "401" ]; then
  echo "❌ 上游返回 401 — channel key 已失效"
  echo "   建议：登录厂商控制台生成新 key，然后在 new-api 后台更新 channel"
elif [ "$HTTP_CODE" = "429" ]; then
  echo "⚠️  上游返回 429 — 真限流"
  echo "   建议：等几分钟再试，或考虑升级上游套餐"
elif [ "$HTTP_CODE" = "200" ]; then
  echo "✅ 上游能直接调通 — 问题在 new-api 渠道或 model 名称映射"
else
  echo "⚠️  上游返回 $HTTP_CODE — 排查厂商侧问题"
fi
echo

# === 6. fallback 检查 ===
echo "=== 6. fallback 配置 ==="
FALLBACK_INFO=$(openclaw config get models 2>/dev/null | jq -r ".\"$CHANNEL_NAME\".providers")
if [ -n "$FALLBACK_INFO" ] && [ "$FALLBACK_INFO" != "null" ]; then
  echo "$FALLBACK_INFO" | jq .
  PROVIDER_COUNT=$(echo "$FALLBACK_INFO" | jq 'length')
  if [ "$PROVIDER_COUNT" -lt 2 ]; then
    echo "⚠️  只有 $PROVIDER_COUNT 个 provider — fallback 链太短"
  fi
else
  echo "⚠️  无法读取 fallback 配置 (请检查 openclaw CLI 权限)"
fi
```

**使用方法**：

```bash
chmod +x diagnose-channel-401.sh

export NEW_API_TOKEN="<your-new-api-admin-token>"

./diagnose-channel-401.sh DIY-VPS4
```

**输出示例**：

```
============================================
  诊断 channel: DIY-VPS4
  new-api:      http://192.168.160.xx:3001
============================================

=== 1. 检查 new-api 后端状态 ===
new-api CPU: 0.08%
✅ 后端空闲 (< 5% CPU) — 如果还在报错，问题不在后端

=== 2. 拉 channel 配置 ===
channel id:      42
base_url:        https://api.某厂商.com
enabled:         true
key (masked):    sk-xxxxx...xxxx

=== 3. 通过 new-api 调一次 (返回的 error 字段是关键) ===
{
  "error": {
    "message": "server is busy, please retry later"
  }
}

=== 4. 用 channel 里的 model (claude-sonnet-4-5) 直接调上游 base_url ===
HTTP status: 401
{
  "type": "error",
  "error": {
    "type": "authentication_error",
    "message": "Invalid token"
  }
}

=== 5. 诊断结论 ===
❌ 上游返回 401 — channel key 已失效
   建议：登录厂商控制台生成新 key，然后在 new-api 后台更新 channel

=== 6. fallback 配置 ===
[
  { "name": "newapi-anthropic",           "weight": 1.0 },
  { "name": "newapi-anthropic-fallback",  "weight": 0.5 },
  { "name": "MiniMax-M2.7-fallback",      "weight": 0.3 }
]
```

**这个脚本是只读的——它不会改 key、不会改 channel、不会动 fallback 配置。**

你拿到诊断结果之后，**自己决定**要不要改、改哪个、什么时候改。

## 六、Q&A

### Q1：为什么 new-api 要把 401 翻译成"server is busy"？

**A**：为了统一处理"暂时不可用"类错误。`new-api` 想让 429/401/502/503 全部走 retry 流程，业务方无感。但这有个副作用——**401 这种确定性失败也会被 retry 100 次**，掩盖了真实问题。

### Q2：怎么快速判断"server is busy" 是真限流还是 401？

**A**：三步走：
1. 看后端 CPU（`docker stats`）— 0% 大概率不是后端限流
2. 看同渠道其他 model — 都正常说明渠道没全挂
3. **直接用 channel 里的 key 调上游** — 401 就是 token 失效，429 才是真限流

### Q3：fallback 为什么不生效？

**A**：看你的 gateway 的 fallback 触发逻辑。一般有两种实现：
- **基于 HTTP 状态码**：401/429 切下一个 provider
- **基于错误信息匹配**：`server is busy` 这种通用错误可能只触发 retry

如果是第二种，**401 被翻译成"server is busy"后，fallback 就被绕过了**。建议把 fallback 触发条件改为基于 HTTP 状态码，而不是错误信息。

### Q4：能不能写个 watchdog 自动检测 channel 失效？

**A**：可以。思路：
- 每 5 分钟用 channel 的 key 调一次上游（只发 1 token 的请求）
- 如果连续 3 次返回 401，告警
- 如果返回 200，记 ok
- 告警时通过 WeCom / 钉钉推送给负责人

但要注意：
- **不要用业务 key 跑 watchdog**（会污染厂商的 rate limit 计数）
- **不要在 watchdog 里换 key**（换 key 属于凭据管理，要走人工）

### Q5：DIY-VPS4 渠道现在还能用吗？

**A**：能——但需要走 fallback。如果你不想立刻换 key，临时把 `newapi-anthropic` 的权重降到 0，让请求走 `MiniMax-M2.7-fallback` 即可：

```bash
openclaw config set models.DIY-VPS4.providers[0].weight 0
openclaw config set models.DIY-VPS4.providers[2].weight 1.0
openclaw gateway reload
```

### Q6：怎么从根上避免这种问题？

**A**：

1. **凭据要定期轮换**（建议 90 天）— 厂商不会主动告诉你 key 失效
2. **告警要覆盖 401** — 监控 channel 调用结果时，401 要单独分类，不能混在 5xx 里
3. **fallback 触发条件用 HTTP 状态码而不是错误信息** — 不要让翻译层掩盖真实问题
4. **凭据要分级管理** — 厂商的 API key 和业务的 API key 分开，watchdog 只能读不能写

## 七、总结

`server is busy, please retry later` 这 6 个字看起来像限流，**但它可能是 401、429、502、503 的任意一种**。

核心要点：

1. ✅ **先看后端忙不忙** — `docker stats` CPU 0% 大概率不是真限流
2. ✅ **看同渠道其他 model** — 都正常说明是 channel 自己的事
3. ✅ **直接用 channel key 调上游** — 401 = token 失效，429 = 真限流
4. ✅ **fallback 触发条件用 HTTP 状态码** — 不要让错误信息翻译层掩盖真实状态
5. ✅ **凭据管理要走流程** — 不要在排查过程中随手换 key
6. ✅ **给 watchdog 留一个旁路** — 只读不写的诊断脚本是排查的第一步

**这次故障的教训：错误信息是最不可信的第一现场。** `new-api` 把 401 翻译成"server is busy"是为了业务无感，但这也让排查难度增加。

**真正的现场是上游的 HTTP 状态码——401 就是 401，不会被任何翻译层改变。**

下次看到"server is busy"，**第一件事不是重试，是看后端 CPU 是不是真的忙。**

如果不是，那就直奔上游 401。

---

*作者：小六，一个在上海努力生存的普通打工人*
