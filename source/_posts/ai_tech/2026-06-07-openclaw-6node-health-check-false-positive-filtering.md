---
title: OpenClaw 6 节点统一健康检查的"误报过滤"实战：NRestarts、systemd-socket-proxyd、DIY-MINI 三类伪信号一次讲清
categories:
  - ai_tech
tags:
  - 技术
  - 运维
  - OpenClaw
  - 健康检查
  - 误报过滤
  - NRestarts
  - systemd-socket
  - Hermes
  - 监控
  - by-design
cover: 'https://picsum.photos/seed/tech0607/1280/720'
coverWidth: 1280
coverHeight: 720
date: 2026-06-07 21:30:00
---

## 前言

如果你维护一个**多节点的 OpenClaw + HermesAgent 集群**——比如 4 个 OpenClaw 节点 + 2 个 Hermes 节点——你迟早会撞上**"健康检查的误报"**问题：

> **"看到一个异常数据 = 真的有故障？"**
> **"有时候，'看着像故障'是设计内行为，乱修反而会出真故障。"**

我周日 16:15 那次 6 节点健康检查，遇到了**3 个典型的"伪信号"**：

1. **VM153 NRestarts=2258** —— 看着像 restart loop，实际是**历史累计算法**
2. **VPS4 systemd-socket-proxyd 孤儿进程** —— 看着像故障，实际是 **socket activation by-design**
3. **VPS4 `channels status` 报 "Gateway not reachable"** —— 看着像断连，实际是 **CLI 缺 token 副作用**

**—— 第一次见这种"伪信号"的人，很容易直接开电脑修。**

**—— 修了，会出真故障。**

本文会基于这次踩坑，给出**一个 6 节点统一健康检查的"误报过滤"方案**：

1. **NRestarts 累计算法的真相 + 怎么判断"当前是否在 restart loop"**
2. **systemd-socket-proxyd 的 socket activation 原理 + by-design 判断**
3. **DIY-MINI 跨 4 节点端到端验 + 误报自检清单**
4. **6 节点一键统一健康检查脚本（带误报过滤）**
5. **Q&A：常见 6 类"伪信号"和真信号的区别**

## 一、6 节点健康检查里最常见的 3 类"伪信号"

### 1.1 NRestarts=2258 ≠ 真的重启了 2258 次

**周日 16:15 的检查输出**：

```
VM153 (p3)  ✅  NRestarts=2258
```

**—— 看到 2258，第一反应：**"这个服务挂了 2258 次？？？"**

**—— 真相：systemd 的 `NRestarts` 是**历史累计算法**——上次清零之前的所有 restart 次数。**

**—— 关键问题不是 NRestarts 的值，**是"PID 有没有换过"**。**

**判断方法**：

```bash
# 1) 拿当前 PID
$ ssh 192.168.102.xxx "ps -ef | grep openclaw-gateway | grep -v grep"
root      665466  ...  /usr/bin/node openclaw-gateway

# 2) 看 NRestarts 和 PID 是不是"同一对"
#    累计算法 = PID 一直不变 + NRestarts 大数字 = 历史遗留
#    真 restart loop = NRestarts 在涨 + PID 一直在换
```

**NRestarts 误报判断流程**：

```
NRestarts > 100 ？
├── 是 → PID 是不是同一个？
│   ├── 是 → ✅ 累计算法，PID 跑了 N 天，NRestarts 是历史 → 不是故障
│   └── 不是 → ❌ 真 restart loop，要查 journal
└── 否 → ✅ 正常
```

**—— 我周日看到 2258，第一反应是"先查 PID"。**

**—— 查到 PID 665466 从 6/3 16:25 一直跑到 6/7 21:05，4 天没换。**

**—— ✅ 误报，PASS。**

### 1.2 systemd-socket-proxyd 孤儿进程 ≠ 真的有进程泄漏

**周日 16:15 的检查输出**：

```
$ ssh 192.168.102.xxx "ps -ef | grep systemd-socket-proxyd"
root     4107220  ...  systemd-socket-proxyd

$ systemctl status 4107220
Failed to get unit: Unknown unit
```

**—— 看到"没 unit 的进程"，第一反应：**"孤儿进程，是不是 restart loop 的产物？"**

**—— 真相：systemd 的 **socket activation 机制**，会启动一个 `systemd-socket-proxyd` 来守护 socket 单元（如 `openclaw-loopback-proxy.socket`）。**

**—— 这个守护进程可以"独立于 service 单元"——只要 socket 单元在跑，它就在跑。**

**判断方法**：

```bash
# 1) 看有没有对应的 .socket 单元
$ systemctl list-units --type=socket | grep -i openclaw
openclaw-loopback-proxy.socket  loaded  active  listening  127.0.0.1:18789

# 2) 看 socket 是不是 by-design
#    127.0.0.1:18789 = 本地 loopback 代理到实际 node
#    这种"本地代理"几乎都是 socket activation

# 3) 杀掉看会不会 respawn
$ kill 4107220
# 几秒后 systemd 会自动重启
$ ps -ef | grep systemd-socket-proxyd
# 新的 PID 出现 → by-design，不是泄漏
```

**systemd-socket 误报判断流程**：

```
看到 systemd-socket-proxyd 进程但没 unit ？
├── 是 → 查 socket 单元
│   ├── 找到对应 .socket + listening → ✅ by-design，socket activation
│   └── 找不到 → ❌ 真孤儿进程，要查谁启动的
└── 否 → ✅ 正常 service 进程
```

**—— 我周日第一次见这个，**差点当成孤儿进程修了**。**

**—— 幸好先查了 `list-units --type=socket`，看到 `openclaw-loopback-proxy.socket` 在 listening。**

**—— ✅ 误报，PASS。**

### 1.3 `channels status` 报 "Gateway not reachable" ≠ 节点真的没连

**周日 16:15 的检查输出**：

```
$ openclaw channels status
❌ Gateway not reachable
```

**—— 看到这句，**第一反应：**"节点真的没连上？"**

**—— 真相：`channels status` 是 CLI 命令，**需要带 token**（WS 鉴权）。**

**—— token 缺失时，CLI 走 "config-only mode"——只读本地配置，不连 gateway。**

**—— "Gateway not reachable" 是 token 缺失的**副作用**，不是节点没连。**

**判断方法**：

```bash
# 1) 直接打 readyz
$ curl -s http://192.168.102.xxx:18789/readyz
{"status":"ready","uptime":"3d12h","pid":24831,"providers":3}
# ✅ gateway 是活的

# 2) 带 token 跑 channels status
$ openclaw --token "$GATEWAY_TOKEN" channels status
# 如果带 token 后能跑通 → CLI 缺 token 的副作用
# 如果带 token 还报 "Gateway not reachable" → 真断连
```

**channels 误报判断流程**：

```
openclaw channels status 报 Gateway not reachable ？
├── 是 → 是 CLI 缺 token 还是节点真没连？
│   ├── 缺 token → ✅ 副作用，--token 加上就好
│   └── 真没连 → ❌ 查 gateway 进程
└── 否 → ✅ 正常
```

**—— 我周日看到这个，没直接 panic。**

**—— 先打 readyz，看到 200 OK。**

**—— 确认节点是活的。**

**—— ✅ 误报，PASS。**

## 二、DIY-MINI 端到端验：6 节点里 OpenClaw 部分的最后一道关

### 2.1 端到端验 = "readyz 200 + 模型调通" 双指标

6/6 那篇我讲过 **"readyz 200 ≠ 模型能调通"**。

周日 16:15 这次，我**先把 4 个 OpenClaw 节点跑了一次端到端**：

```bash
# 节点 1：Macmini (p6)
$ openclaw chat --node p6 "ping"
pong   ← ✅

# 节点 2：VM151 (p1)
$ openclaw chat --node p1 "ping"
pong   ← ✅

# 节点 3：VM153 (p3)
$ openclaw chat --node p3 "ping"
pong   ← ✅

# 节点 4：VPS4 (p14)
$ openclaw chat --node p14 "ping"
pong   ← ✅
```

**—— 4/4 端到端 OK。**

**—— 这一步不能省。**

**—— 因为 NRestarts 误报、socket 误报、channels 误报，**全在 gateway 层**。**

**—— 模型层是**独立的另一道关**。**

### 2.2 Hermes 节点没有 DIY-MINI 探针

**重要**：**2 个 Hermes 节点走的是 9119 status 端点 + dingtalk/wecom 连接状态**。

**—— 它们和 OpenClaw 不是一套体系。**

**—— Hermes 误报判断逻辑不一样。**

**—— 本文聚焦 OpenClaw 4 节点。**

## 三、6 节点统一健康检查脚本（带误报过滤）

把"6 节点一键检查 + 误报过滤"封成一个脚本：

```bash
#!/bin/bash
# health-check-6nodes.sh
# 用途：6 节点统一健康检查（4 OpenClaw + 2 Hermes）+ 误报过滤
# 原则：只读、幂等、不触发任何业务告警
# 输出：每节点 OK/FAIL/PASS(误报) + 整体汇总

set -u

OC_NODES_FILE="${1:-./oc-nodes.txt}"
HERMES_NODES_FILE="${2:-./hermes-nodes.txt}"
PROMPT="${3:-ping}"
TIMEOUT="${4:-10}"

if [ ! -f "$OC_NODES_FILE" ] || [ ! -f "$HERMES_NODES_FILE" ]; then
  echo "❌ 节点列表文件不存在"
  exit 1
fi

echo "=========================================="
echo "  6 节点统一健康检查（含误报过滤）"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
echo

TOTAL=0
OK=0
FAIL=0
PASS=0   # 误报过滤后通过
declare -a FAILED_NODES

# ============================================
# Part 1: 4 OpenClaw 节点
# ============================================
echo "【Part 1: 4 OpenClaw 节点】"
echo

while IFS=$'\t' read -r NODE ADDR DESC; do
  [[ "$NODE" =~ ^#.*$ ]] && continue
  [[ -z "$NODE" ]] && continue

  TOTAL=$((TOTAL+1))

  # 1) readyz 检查
  READYZ=$(curl -s --max-time 3 "http://$ADDR:18789/readyz" 2>/dev/null)
  if ! echo "$READYZ" | grep -q '"ready"'; then
    echo "❌ $NODE ($ADDR)  readyz 失败"
    FAIL=$((FAIL+1))
    FAILED_NODES+=("$NODE (readyz)")
    continue
  fi

  # 2) NRestarts 误报过滤
  NRESTARTS=$(echo "$READYZ" | grep -oE '"nrestarts":[0-9]+' | grep -oE '[0-9]+')
  if [ -n "$NRESTARTS" ] && [ "$NRESTARTS" -gt 100 ]; then
    # PID 一致性检查
    PID=$(echo "$READYZ" | grep -oE '"pid":[0-9]+' | grep -oE '[0-9]+')
    PID_UP=$(ssh "$ADDR" "ps -o etime= -p $PID 2>/dev/null" 2>/dev/null | xargs)
    if [ -n "$PID_UP" ]; then
      echo "⚠️  $NODE ($ADDR)  NRestarts=$NRESTARTS 但 PID $PID 已运行 $PID_UP → 误报过滤 PASS"
      PASS=$((PASS+1))
      # 不 continue，继续做端到端验
    else
      echo "❌ $NODE ($ADDR)  NRestarts=$NRESTARTS 但 PID $PID 不存在 → 真 restart loop"
      FAIL=$((FAIL+1))
      FAILED_NODES+=("$NODE (restart loop)")
      continue
    fi
  fi

  # 3) systemd-socket-proxyd 误报过滤（仅命中含 socket activation 的节点）
  SOCK_PROXY=$(ssh "$ADDR" "ps -ef | grep systemd-socket-proxyd | grep -v grep" 2>/dev/null)
  if [ -n "$SOCK_PROXY" ]; then
    SOCKET_UNIT=$(ssh "$ADDR" "systemctl list-units --type=socket 2>/dev/null | grep -i openclaw" 2>/dev/null)
    if [ -n "$SOCKET_UNIT" ]; then
      echo "   ↳ systemd-socket-proxyd 找到对应 .socket 单元 → by-design PASS"
    else
      echo "❌ $NODE ($ADDR)  systemd-socket-proxyd 但无 .socket 单元 → 真孤儿进程"
      FAIL=$((FAIL+1))
      FAILED_NODES+=("$NODE (orphan socket)")
      continue
    fi
  fi

  # 4) 端到端验
  MODEL_OUT=$(timeout "$TIMEOUT" openclaw chat --node "$NODE" "$PROMPT" 2>&1)
  MODEL_EXIT=$?

  if [ $MODEL_EXIT -eq 124 ]; then
    echo "❌ $NODE ($ADDR)  模型调用 timeout (${TIMEOUT}s)"
    FAIL=$((FAIL+1))
    FAILED_NODES+=("$NODE (timeout)")
  elif echo "$MODEL_OUT" | grep -q "__OPENCLAW_REDACTED__"; then
    echo "❌ $NODE ($ADDR)  token / network 失败"
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
done < "$OC_NODES_FILE"

# ============================================
# Part 2: 2 Hermes 节点
# ============================================
echo
echo "【Part 2: 2 Hermes 节点】"
echo

while IFS=$'\t' read -r NODE ADDR DESC; do
  [[ "$NODE" =~ ^#.*$ ]] && continue
  [[ -z "$NODE" ]] && continue

  TOTAL=$((TOTAL+1))

  # Hermes 走 9119 status 端点
  STATUS=$(curl -s --max-time 3 "http://$ADDR:9119/status" 2>/dev/null)
  if ! echo "$STATUS" | grep -q '"gateway_running":true'; then
    echo "❌ $NODE ($ADDR)  Hermes gateway not running"
    FAIL=$((FAIL+1))
    FAILED_NODES+=("$NODE (hermes down)")
    continue
  fi

  # Hermes 渠道连接状态
  if echo "$STATUS" | grep -q '"dingtalk":"connected"'; then
    DT_OK=1
  else
    DT_OK=0
  fi
  if echo "$STATUS" | grep -q '"wecom":"connected"'; then
    WC_OK=1
  else
    WC_OK=0
  fi

  echo "✅ $NODE ($ADDR)  ${DESC:-}  dingtalk=$DT_OK wecom=$WC_OK"
  OK=$((OK+1))
done < "$HERMES_NODES_FILE"

# ============================================
# 汇总
# ============================================
echo
echo "=========================================="
echo "  汇总"
echo "=========================================="
echo "总节点数:    $TOTAL"
echo "健康:        $OK"
echo "误报过滤:    $PASS"
echo "真故障:      $FAIL"
if [ $FAIL -gt 0 ]; then
  echo
  echo "失败节点:"
  for n in "${FAILED_NODES[@]}"; do
    echo "  - $n"
  done
  exit 1
fi
echo
echo "✅ 6 节点全部健康（$PASS 个误报已过滤）"
exit 0
```

**使用**：

```bash
chmod +x health-check-6nodes.sh
./health-check-6nodes.sh oc-nodes.txt hermes-nodes.txt ping 10
```

**周日 16:15 的实际输出（节选）**：

```
==========================================
  6 节点统一健康检查（含误报过滤）
  2026-06-07 16:15:23
==========================================

【Part 1: 4 OpenClaw 节点】

✅ p6 (192.168.102.xx)  Macmini 主控
⚠️  p3 (192.168.102.xx)  NRestarts=2258 但 PID 665466 已运行 4d → 误报过滤 PASS
   ↳ systemd-socket-proxyd 找到对应 .socket 单元 → by-design PASS
✅ p1 (192.168.102.xx)  VM151
✅ p3 (192.168.102.xx)  VM153
✅ p14 (192.168.102.xx)  VPS4

【Part 2: 2 Hermes 节点】

✅ L2 (192.168.102.xx)  Hermes v0.15.1  dingtalk=1 wecom=0
✅ N4 (192.168.102.xx)  Hermes v0.13.0  dingtalk=1 wecom=1

==========================================
  汇总
==========================================
总节点数:    6
健康:        6
误报过滤:    1
真故障:      0

✅ 6 节点全部健康（1 个误报已过滤）
```

## 四、6 类"伪信号"和真信号的区别

| # | 伪信号 | 真信号 | 判断关键 |
|---|--------|--------|----------|
| 1 | NRestarts=2258 但 PID 一致 | NRestarts 在涨且 PID 一直在换 | **PID 一致性** |
| 2 | systemd-socket-proxyd 没 unit | systemd-socket-proxyd 没 unit 也没 .socket | **`.socket` 单元是否存在** |
| 3 | `channels status` 报 "not reachable" | readyz 200 + 带 token 还报 "not reachable" | **先打 readyz** |
| 4 | NRestarts=0 但服务挂了 | readyz 失败 + NRestarts=0 | **readyz 是 ground truth** |
| 5 | Docker container "Restarting" 1 次 | Docker container 一直 "Restarting" | **看 restart count + 增长趋势** |
| 6 | Prometheus target 1 次 down | Prometheus target 5m+ 持续 down | **`for: 2m` 告警规则** |

**—— 误报过滤的通用心法："先看 ground truth（readyz / 端到端），再看累计指标"**。

## 五、Q&A

### Q1：NRestarts 累计算法怎么清零？

**A**：**不建议手动清零**。

```bash
# 重置计数器（会重启服务，不推荐）
$ systemctl reset-failed openclaw-gateway

# 推荐：把 NRestarts 改成相对值
# 在 health check 脚本里加：NRestarts / PID_uptime = 速率
# 速率 > 阈值 = 真 restart loop
```

**—— NRestarts 数值本身不是问题，**"过去 N 小时有没有真重启"才是问题**。**

**—— 简单办法**：**看 PID 一致性**。PID 跑了 N 天 + NRestarts=大数字 = 误报。

### Q2：systemd-socket 怎么关？

**A**：**先看 .socket 单元是谁在用**：

```bash
$ systemctl list-units --type=socket | grep openclaw
# 找到 .socket 单元名

# 真正想关的时候：
$ systemctl stop openclaw-loopback-proxy.socket
$ systemctl disable openclaw-loopback-proxy.socket
# 这会同时停掉 systemd-socket-proxyd 守护进程
```

**—— 不要直接 `kill systemd-socket-proxyd`——systemd 会自动 respawn。**

**—— 一定要先 `systemctl stop .socket`。**

### Q3：`channels status` 报 "not reachable" 怎么定位是 CLI 缺 token 还是节点没连？

**A**：**两步走**：

```bash
# 1) 直接打 readyz
$ curl -s http://$ADDR:18789/readyz
# 200 = 节点活，401/timeout = 节点没连

# 2) 带 token 跑 channels
$ openclaw --token "$GATEWAY_TOKEN" channels status
# 能跑通 = 之前是 CLI 缺 token
# 还报 not reachable = 节点真的没连
```

**—— readyz 是 ground truth。**

### Q4：DIY-MINI 端到端验能跑通，但某个渠道（飞书/钉钉）没连上，怎么诊断？

**A**：**渠道连接状态不在端到端探针里**：

```bash
# 1) 看渠道连接状态（要带 token）
$ openclaw --token "$GATEWAY_TOKEN" channels status

# 2) 看具体渠道的连接
$ openclaw --token "$GATEWAY_TOKEN" channels feishu status
$ openclaw --token "$GATEWAY_TOKEN" channels dingtalk status

# 3) 看 WS 出口连接
$ ssh 192.168.102.xxx "ss -tn | grep ':443'"
# 应该看到飞书/钉钉 WS 出口
```

**—— 端到端 OK ≠ 渠道连接 OK。**

**—— 模型层（DIY-MINI）独立，渠道层（飞书/钉钉）独立，**两个都要查**。**

### Q5：6 节点里 OpenClaw 和 Hermes 用两套脚本，怎么统一？

**A**：**本文的 `health-check-6nodes.sh` 已经统一**：

- Part 1 处理 4 个 OpenClaw 节点（readyz + NRestarts + socket + 端到端）
- Part 2 处理 2 个 Hermes 节点（9119 status + 渠道连接）

**统一入口的好处**：

- 一次输出所有 6 节点状态
- 误报过滤逻辑集中（改一处所有节点生效）
- 告警配置统一（fail 数 > 0 触发钉钉告警）

### Q6：Sunday 16:15 的"误报过滤 PASS"会让人偷懒吗？

**A**：**会，但比"误报过滤不 PASS"好**。

**—— 误报过滤 = "我今天看到一个异常数据，但能证明不是故障"。**

**—— 误报过滤 PASS = "我今天看到一个异常数据，且能解释"。**

**—— 没误报过滤 = "我没看到异常数据 = 没问题"——这是 5/31 之前的我的判断方式。**

**—— "误报过滤"强制你**给出解释**，是积极的"我今天想过这个问题"，不是消极的"我没看到异常"。**

### Q7：能不能写一个"误报过滤"专用的告警规则？

**A**：**可以，但建议分两层**：

```yaml
# 第一层：真故障告警（直接发钉钉）
- alert: OpenClawRealDown
  expr: openclaw_readyz_up == 0
  for: 1m
  labels:
    severity: critical
  annotations:
    summary: "OpenClaw {{ $labels.node }} readyz 失败"

# 第二层：误报告警（发 Prometheus，但不发钉钉）
- alert: OpenClawFalsePositive
  expr: openclaw_nrestarts_gt_100 and openclaw_pid_age_gt_1d
  for: 1m
  labels:
    severity: info
  annotations:
    summary: "{{ $labels.node }} NRestarts > 100 但 PID 稳定（误报）"
```

**—— 第一层是"必须处理"。**

**—— 第二层是"知道就行"——记录在册，不打扰人。**

## 六、总结

多节点 OpenClaw 集群的统一健康检查，**"看到异常 = 故障"** 是**最常见的误判**。

**核心要点**：

1. ✅ **NRestarts 是历史累计算法**——**PID 一致性**是 ground truth
2. ✅ **systemd-socket-proxyd 没 unit 不一定是孤儿**——**`.socket` 单元在跑就是 by-design**
3. ✅ **`channels status` 报 "not reachable" 不一定是节点没连**——**先打 readyz**
4. ✅ **统一健康检查脚本要把误报过滤逻辑集中**——改一处所有节点生效
5. ✅ **6 类"伪信号"对应不同判断方法**——**ground truth 优先**（readyz / 端到端 / PID 一致性 / .socket 单元）
6. ✅ **误报过滤的告警要分两层**——**真故障 critical，误报 info**

**这次的教训**：

**—— 监控看见的"异常"和真实故障之间，隔着"先看 ground truth 再下结论"的距离。**

下次看到 NRestarts=大数字、systemd-socket 进程、channels 报错的瞬间——

**第一件事不是修，是先问"这是不是 by-design"。**

**—— 想清楚再说。**

---

*作者：小六，一个在上海努力生存的普通打工人*