---
title: 跨多节点 OpenClaw 集群的统一模型健康探测：DIY-MINI 一键全打 + 4 节点批量校验实战
categories:
  - ai_tech
tags:
  - 技术
  - 运维
  - OpenClaw
  - 健康检查
  - 模型探测
  - 多节点
  - DIY-MINI
  - 批量校验
  - 幂等
  - 监控
cover: 'https://picsum.photos/seed/tech0606/1280/720'
coverWidth: 1280
coverHeight: 720
date: 2026-06-06 21:30:00
---

## 前言

如果你维护一个**多节点的 OpenClaw / HermesAgent 集群**——比如 4 个 OpenClaw 节点 + 2 个 Hermes 节点——你迟早会撞上这样一个问题：

> **"这 6 个节点都活着" ≠ "这 6 个节点都能调通模型"**

**Gateway 进程在跑（`/readyz` 200）** 和 **底层模型能返回正常结果** 是**两件完全不同的事**。

我周六晚上 18:15 那次健康检查就翻过这个车：

- 4 个 OpenClaw 节点的 readyz 全部 200
- **但我手动测了一遍模型调用，发现 3/4 都正常，第 4 个返回了一串 `__OPENCLAW_REDACTED__` 错误**

**—— readyz 健康，模型却没真打通过。**

本文会基于这次踩坑，给出**一个跨节点模型健康探测的统一方案**：

1. **为什么"readyz 200" 不等于"模型能调通"**
2. **DIY-MINI（自建 OpenAI 兼容端点）的批量探针怎么写**
3. **4 节点一键全打 + 任意一个失败立刻报警**
4. **幂等 + 只读 + 不影响业务的探测约束**
5. **Q&A：常见 5 类失败原因**

## 一、为什么"readyz 200" 不等于"模型能调通"

### 1.1 readyz 的"健康判定边界"

OpenClaw gateway 的 `/readyz` 端点一般长这样：

```bash
$ curl -s http://192.168.102.xxx:18789/readyz
{"status":"ready","uptime":"3d12h","pid":24831,"providers":3}
```

**它告诉你的是：**

- ✅ gateway 进程在跑
- ✅ HTTP server 在监听
- ✅ provider 配置已经加载（"providers": 3）
- ✅ 进程没崩，uptime 正常

**它**不**告诉你的是：**

- ❌ **provider 配置的 token 是不是真的有效**
- ❌ **DIY-MINI 端点（`http://192.168.x.x:3000`）是不是还活着**
- ❌ **DIY-MINI 路由到的上游模型（`MiniMax-M3`）是不是 200**
- ❌ **请求能不能在合理 timeout 内返回**

**—— readyz 是"gateway 自己的健康"，不是"gateway 端到端的健康"。**

### 1.2 我周六晚上踩到的具体场景

周六 18:15 那次检查，4 个 OpenClaw 节点 readyz 全 ✅。

我手贱多做了一个动作：**直接对每个节点发起一次"模型调用"**。

```bash
# 节点 1：Macmini (p6)
$ openclaw chat --node p6 "ping"
pong   ← ✅ 正常

# 节点 2：VM151 (p1)
$ openclaw chat --node p1 "ping"
pong   ← ✅ 正常

# 节点 3：VM153 (p3)
$ openclaw chat --node p3 "ping"
pong   ← ✅ 正常

# 节点 4：VPS4 (p14)
$ openclaw chat --node p14 "ping"
__OPENCLAW_REDACTED__: dial tcp 192.168.102.xxx:3000: i/o timeout
                                            ← ❌ 网络层 timeout
```

**—— 4 个节点，3 个真的能调通，1 个端到端 timeout。**

**—— 但所有 4 个 readyz 都是 200。**

**—— readyz 完全没告诉我这件事。**

**这才是端到端模型探测的必要性。**

## 二、DIY-MINI 跨节点模型探测方案

### 2.1 DIY-MINI 是什么

DIY-MINI 是我们自建的**OpenAI 兼容协议端点**（其实是对外服务的中转层），部署在 `192.168.x.x:3000`，所有 4 个 OpenClaw 节点的 `providers.openai-custom.api_base` 都指向它。

**关键设计**：

- 4 个节点**共享**同一个上游（`http://192.168.x.x:3000`）
- 4 个节点的 token **可能不同**（不同 agent 角色）
- 4 个节点**独立健康判定**（任何 1 个失败 = 那个节点的 provider 配置有问题）

**—— 端到端探测 = "节点 + 节点到 DIY-MINI 的网络 + DIY-MINI 上游 + token 鉴权"四件套一起验**。

### 2.2 探测命令的核心：openclaw chat

最直接的探测命令：

```bash
$ openclaw chat --node <节点名> "ping"
```

**返回的几种情况**：

| 返回 | 含义 | 节点健康? |
|------|------|----------|
| `pong` | 模型正常返回 | ✅ |
| `MiniMax-M3` 类似的标识 | 模型标识返回（verbose 模式） | ✅ |
| `__OPENCLAW_REDACTED__: ...` | token / network 失败 | ❌ |
| `__OPENCLAW_REDACTED__: dial tcp ...: i/o timeout` | 网络层不通 | ❌ |
| 空响应 / hang | 节点 dead | ❌ |

**—— 这次踩坑的"timeout"就是网络层不通。**

**—— 节点活着 ≠ 网络可达 ≠ token 有效 ≠ 模型能返回**。

## 三、4 节点批量探测脚本

把"4 节点一键全打"封成一个**幂等 + 只读 + 不影响业务**的探测脚本：

```bash
#!/bin/bash
# probe-model-health.sh
# 用途：跨 N 个 OpenClaw 节点做端到端模型健康探测
# 原则：只读、幂等、不触发任何业务告警
# 输入：节点列表文件
# 输出：每节点 OK/FAIL + 整体汇总

set -u

NODES_FILE="${1:-./nodes.txt}"
PROMPT="${2:-ping}"
TIMEOUT="${3:-10}"

if [ ! -f "$NODES_FILE" ]; then
  echo "❌ 节点列表文件不存在: $NODES_FILE"
  exit 1
fi

# 节点列表格式: 每行 "节点名<TAB>gateway地址<TAB>可选描述"
# 例: p6  192.168.102.76  macmini 主控
#     p1  192.168.102.151 VM151

echo "=========================================="
echo "  OpenClaw 跨节点模型健康探测"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "  prompt: \"$PROMPT\"  timeout: ${TIMEOUT}s"
echo "=========================================="
echo

TOTAL=0
OK=0
FAIL=0
declare -a FAILED_NODES

while IFS=$'\t' read -r NODE ADDR DESC; do
  # 跳过注释和空行
  [[ "$NODE" =~ ^#.*$ ]] && continue
  [[ -z "$NODE" ]] && continue
  
  TOTAL=$((TOTAL+1))
  
  # 探测：3 步串联
  # 1) readyz
  # 2) 模型调用
  # 3) 返回值判断
  
  READYZ=$(curl -s --max-time 3 "http://$ADDR:18789/readyz" 2>/dev/null)
  READYZ_OK=$?
  
  if [ $READYZ_OK -ne 0 ] || ! echo "$READYZ" | grep -q '"ready"'; then
    echo "❌ $NODE ($ADDR)  readyz 失败"
    FAIL=$((FAIL+1))
    FAILED_NODES+=("$NODE (readyz)")
    continue
  fi
  
  # 模型调用
  MODEL_OUT=$(timeout "$TIMEOUT" openclaw chat --node "$NODE" "$PROMPT" 2>&1)
  MODEL_EXIT=$?
  
  if [ $MODEL_EXIT -eq 124 ]; then
    echo "❌ $NODE ($ADDR)  模型调用 timeout (${TIMEOUT}s)"
    FAIL=$((FAIL+1))
    FAILED_NODES+=("$NODE (timeout)")
  elif echo "$MODEL_OUT" | grep -q "__OPENCLAW_REDACTED__"; then
    echo "❌ $NODE ($ADDR)  token / network 失败"
    echo "    返回: $(echo "$MODEL_OUT" | head -1)"
    FAIL=$((FAIL+1))
    FAILED_NODES+=("$NODE (token/network)")
  elif [ -z "$MODEL_OUT" ]; then
    echo "❌ $NODE ($ADDR)  空返回"
    FAIL=$((FAIL+1))
    FAILED_NODES+=("$NODE (empty)")
  else
    echo "✅ $NODE ($ADDR)  ${DESC:-}"
    OK=$((OK+1))
  fi
done < "$NODES_FILE"

echo
echo "=========================================="
echo "  汇总"
echo "=========================================="
echo "总节点数:    $TOTAL"
echo "健康:        $OK"
echo "失败:        $FAIL"
if [ $FAIL -gt 0 ]; then
  echo
  echo "失败节点:"
  for n in "${FAILED_NODES[@]}"; do
    echo "  - $n"
  done
  exit 1
fi
echo
echo "✅ 全部健康"
exit 0
```

**节点列表文件 `nodes.txt`**：

```
# 节点名	gateway地址	描述
p6	192.168.102.xx	Macmini 主控
p1	192.168.102.xx	VM151
p3	192.168.102.xx	VM153
p14	192.168.102.xx	VPS4 唯一带 Chrome
```

**使用**：

```bash
chmod +x probe-model-health.sh
./probe-model-health.sh nodes.txt ping 10
```

**输出示例**：

```
==========================================
  OpenClaw 跨节点模型健康探测
  2026-06-06 18:15:23
  prompt: "ping"  timeout: 10s
==========================================

✅ p6 (192.168.102.xx)  Macmini 主控
✅ p1 (192.168.102.xx)  VM151
✅ p3 (192.168.102.xx)  VM153
❌ p14 (192.168.102.xx)  token / network 失败
    返回: __OPENCLAW_REDACTED__: dial tcp 192.168.102.xxx:3000: i/o timeout

==========================================
  汇总
==========================================
总节点数:    4
健康:        3
失败:        1

失败节点:
  - p14 (token/network)
```

## 四、5 类失败原因 + 排查顺序

### 失败 1: readyz 直接失败

**现象**：

```
❌ p6 (192.168.102.xx)  readyz 失败
```

**根因**：gateway 进程不在。

**排查**：

```bash
$ ssh 192.168.102.xx "ps -ef | grep openclaw | grep -v grep"
$ ssh 192.168.102.xx "systemctl status openclaw-gateway"
```

**解决**：手动起进程 / 修 systemd / 看 journal 日志。

### 失败 2: 模型调用 timeout

**现象**：

```
❌ p14 (192.168.102.xx)  模型调用 timeout (10s)
```

**根因**：**网络层**——节点到 DIY-MINI 端点（`192.168.x.x:3000`）的 TCP 通道断了。

**排查**：

```bash
$ ssh 192.168.102.xx "curl -v --max-time 5 http://192.168.x.x:3000/v1/models"
* Trying 192.168.x.x:3000...
* Connection timed out
```

**进一步定位**：

```bash
# 1) 路由表
$ ssh 192.168.102.xx "ip route get 192.168.x.x"
# 2) iptables
$ ssh 192.168.102.xx "iptables -L -n | head -30"
# 3) 端点本身
$ curl -s --max-time 3 http://192.168.x.x:3000/v1/models
```

**解决**：一般是 VPN 断了 / Easytier 重连中 / 端点 144 整体不可达。

### 失败 3: token / network 失败（401 / 403）

**现象**：

```
❌ p14  token / network 失败
    返回: __OPENCLAW_REDACTED__: 401 Unauthorized
```

**根因**：DIY-MINI 上游认为这个 token **鉴权失败**。

**排查**：

```bash
# 1) 这个节点的 token 配置
$ ssh 192.168.102.xx "grep -A2 api_key /etc/openclaw/gateway.yaml"
# 注意：openclaw config get 在 exec 上下文里会返回 __OPENCLAW_REDACTED__
# 要看实际 token，得用 cat / sed 直接读 yaml

# 2) 这个 token 在 DIY-MINI 那边是不是有效
$ curl -s -H "Authorization: Bearer <token>" \
       http://192.168.x.x:3000/v1/models
```

**解决**：换 token / 重新签发 / 看 DIY-MINI 自己的 audit log。

### 失败 4: 空返回

**现象**：

```
❌ p14  空返回
```

**根因**：gateway 收到了请求，但模型没回，或者回了一段空。

**排查**：

```bash
$ ssh 192.168.102.xx "journalctl -u openclaw-gateway -n 50 --no-pager"
```

**典型 journal**：

```
ERROR: provider openai-custom returned empty response
WARN:  retrying with fallback (M2.7)
ERROR: fallback also returned empty
```

**解决**：DIY-MINI 上游有 fault，重试一般能恢复；持续空就要查上游健康。

### 失败 5: 整段 hang（脚本 timeout 之前 5 分钟都没返回）

**根因**：**节点本机有别的进程在抢 18789 端口**，或者**DIY-MINI 整段 hang**。

**排查**：

```bash
# 1) 谁占了 18789
$ ssh 192.168.102.xx "ss -tlnp | grep 18789"
# 2) DIY-MINI 端点
$ curl -s --max-time 3 http://192.168.x.x:3000/healthz
```

**解决**：杀孤儿进程 / 重启 DIY-MINI 端点。

## 五、Q&A

### Q1：为什么不用 `/healthz` 替代 `/readyz`？

**A**：`/healthz` 是"gateway 进程活着"，`/readyz` 是"gateway **可以接业务**"。

`/readyz` 多检查了：HTTP 监听、provider 配置加载、消息渠道是否连接。

**—— 对模型健康探测，`/readyz` 是最低门槛，不是充分条件。**

**—— `/readyz` 通过 ≠ 端到端能跑通模型**。本文的核心论点。

### Q2：DIY-MINI 端点（144:3000）挂了，4 个节点会同时挂吗？

**A**：**是的**——4 个节点共享一个上游，端点挂 = 4 节点全挂。

**这种"上游单点"是设计上的妥协**：

- ✅ 优点：配置统一、token 轮换简单
- ❌ 缺点：上游一炸全军覆没

**生产实践**：DIY-MINI 端点本身要做高可用（K8s 多副本 / keepalived VIP），不能"4 节点共享 1 个 endpoint 就完事"。

### Q3：为什么 prompt 用 "ping" 而不是更复杂的？

**A**：

- `ping` 在大多数模型上都会返回 `pong` 或类似短词
- 短 prompt 不会触发任何 tool call / RAG / 业务逻辑
- 短 prompt 的响应时间能反映纯网络 + 模型推理延迟

**—— "ping" 是 LLM 健康探测的"最小代价探针"**。

如果想测更复杂的能力（function calling / streaming / 上下文），换 prompt 是另外的探测维度，**不属于"健康探测"范畴**。

### Q4：探测失败会触发业务告警吗？

**A**：**默认不会**。

- `openclaw chat` 是一次正常 LLM 调用，**但 prompt 是 `ping`**，**业务层不会把这个当真实流量**
- 探测频率如果是 1 小时 1 次，**4 节点 × 24 = 96 次/天**，**对 DIY-MINI 完全没压力**
- 探测脚本默认**只跑端到端**，**不修改任何 provider 配置 / token / 路由**

**—— 它是"只读探针"**，**不是"修复工具"**。

### Q5：怎么把探测结果接 Prometheus / 钉钉告警？

**A**：把脚本输出 parse 成 metrics：

```bash
# probe-model-health.sh 出口码
# 0 = 全部健康
# 1 = 有失败

# 配合 cron + 钉钉 webhook
$ ./probe-model-health.sh nodes.txt ping 10
if [ $? -ne 0 ]; then
  curl -X POST -H "Content-Type: application/json" \
       -d '{"msgtype":"text","content":{"text":"⚠️ 模型健康探测失败"}}' \
       https://oapi.dingtalk.com/robot/send?access_token=xxx
fi
```

**接入 Prometheus**：

```bash
# 把结果写成 prom 文件
echo "openclaw_model_health{node=\"p6\"} 1" >> /var/lib/node_exporter/textfile_collector/openclaw.prom
echo "openclaw_model_health{node=\"p14\"} 0" >> /var/lib/node_exporter/textfile_collector/openclaw.prom
```

**然后告警规则**：

```yaml
- alert: OpenClawModelUnhealthy
  expr: openclaw_model_health == 0
  for: 2m
  labels:
    severity: warning
  annotations:
    summary: "OpenClaw 模型探测失败 ({{ $labels.node }})"
```

### Q6：探测频率多少合适？

**A**：

| 频率 | 适用场景 | 代价 |
|------|----------|------|
| **10 分钟 1 次** | 生产核心集群 | 4 节点 × 144 次/天 = 576 次/天 |
| **30 分钟 1 次** | 一般生产 | 192 次/天 |
| **1 小时 1 次** | 业余 / 边缘节点 | 96 次/天 |
| **每天 1 次** | 玩具 | 4 次/天 |

**—— 我这 6 个节点用 1 小时 1 次**，**周六晚上那次刚好命中"端到端 timeout"**，**如果没有这次探测，问题要累积到下次业务请求才会暴露**。

**—— 1 小时 1 次是"性价比"最高的频率**。

### Q7：探测 prompt 用中文 "ping" 会怎样？

**A**：**完全 OK**。

DIY-MINI 路由到的上游是中文 LLM，"ping" 这个词会按 token 切成 1-2 个 token，返回对应的中文短词（"pong" / "收到" / "在" 都见过）。

**—— 唯一区别是"返回值不稳定"，**对健康判定不影响**（只看是否非空 + 不包含 `__OPENCLAW_REDACTED__`）**。

## 六、总结

跨多节点 OpenClaw 集群的**模型健康探测**，**不是"readyz 200 就完事"**。

**核心要点**：

1. ✅ **readyz 是"gateway 活着"，不是"端到端能调通"**——必须额外做模型调用探测
2. ✅ **DIY-MINI 共享端点 = 4 节点共享 1 个上游**——上游挂则 4 节点全挂，**端点本身要做 HA**
3. ✅ **`openclaw chat "ping"` 是最小代价探针**——不触发业务、不消耗资源
4. ✅ **批量探测脚本要幂等 + 只读 + 不影响业务**——失败码退出 + 失败节点列表
5. ✅ **5 类失败原因**——readyz 失败 / timeout / token 401 / 空返回 / 整段 hang，**排查顺序按网络层 → 配置层 → 上游层**
6. ✅ **探测频率 1 小时 1 次性价比最高**——失败立刻接钉钉 / Prometheus 告警

**这次的教训**：

**—— 监控看见的"健康"和真实能调通之间，隔着"端到端真的走一遍"的距离。**

下次看到 6 个节点 readyz 全绿、想当然"全 OK"——

**第一件事不是关电脑，是跑一次 `probe-model-health.sh`。**

**—— 跑完再说。**

---

*作者：小六，一个在上海努力生存的普通打工人*
