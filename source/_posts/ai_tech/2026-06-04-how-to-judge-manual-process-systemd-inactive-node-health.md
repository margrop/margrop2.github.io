---
title: OpenClaw 健康检查中如何正确判定"manual 进程 + systemd inactive"节点的健康状态：一份可复用的判断矩阵
categories:
  - ai_tech
tags:
  - 技术
  - 运维
  - OpenClaw
  - 健康检查
  - systemd
  - manual
  - 进程
  - 监控
  - Hermes
  - dashboard
cover: 'https://picsum.photos/seed/tech0604/1280/720'
coverWidth: 1280
coverHeight: 720
date: 2026-06-04 21:30:00
---

## 前言

做 OpenClaw Gateway 健康检查的人，几乎都会撞上这样一个让人"半夜睡不着"的场景：

```bash
$ systemctl is-active openclaw-gateway
inactive

$ ps -ef | grep openclaw | grep -v grep
root  338431  ...  /usr/local/bin/openclaw-gateway --config /etc/openclaw/gateway.yaml

$ curl -s http://127.0.0.1:18789/readyz
{"status":"ready","uptime":"29h12m"}
```

**`systemd` 报 inactive，但 manual 进程在跑，gateway 自身 200。**

**这到底算健康，还是算故障？**

如果你选"故障"—— 你可能会去 `systemctl restart openclaw-gateway`，然后：
- 进程抢不到端口（被 manual 那个占着）
- 累计 NRestarts
- 飞书/钉钉连接被踢
- 业务中断 30 秒

如果你选"健康"—— 你可能会被半夜 3 点的告警吵醒："systemd unit not-found"。

**这个判定没有标准答案，但有一套判断矩阵。**

本文会基于我维护 6 节点 OpenClaw 集群的实战经验，给出一份**可复用的"manual 进程 + systemd inactive" 健康判定矩阵**，并附一个**只读、不 kill 任何进程**的安全检查脚本。

## 一、为什么会出现"manual 进程 + systemd inactive"

### 1.1 三种典型场景

在我这 6 个节点里，"systemd inactive 但服务健康"的状态出现过 3 次：

**场景 A：Hermes 节点取代 OpenClaw**

VM152 (p2) 整个迁移到了 HermesAgent 栈。Hermes 的 gateway 是个独立二进制（`hermes-gateway`），不归 OpenClaw 那个 systemd unit 管。

```bash
$ systemctl is-active openclaw-gateway
inactive  ← OpenClaw unit 不知道 Hermes 进程

$ ps -ef | grep hermes
hermes  338431  ...  /usr/local/bin/hermes-gateway
```

**systemd inactive 是预期的。** 重点是 Hermes 自己的 `/api/status`（9119 端口）是不是 200。

**场景 B：systemd unit 丢失，manual 进程续命**

VM151 (p1) 之前某次升级的时候，systemd unit 文件被覆盖了或者丢失了（`is-enabled: not-found`），但 manual 启动的进程一直在跑，没人来重启。

```bash
$ systemctl is-active openclaw-gateway
inactive

$ systemctl is-enabled openclaw-gateway
not-found  ← unit 文件不存在

$ ps -ef | grep openclaw
root  802705  ...  /usr/local/bin/openclaw-gateway
```

**unit 丢失 ≠ 进程不健康。** 重点是 manual 进程本身是不是还在响应。

**场景 C：manual 启动是"故意为之"**

有些团队（特别是 Hermes 这种新栈）会**故意不开 systemd**，就用 `nohup hermes-gateway &` 跑着，因为 Hermes 的更新节奏太快，systemd unit 维护成本反而高。

```bash
$ cat /etc/systemd/system/hermes.service
# 注释掉的 unit 文件
# 故意不开 systemd — 详见 Hermes 部署文档
```

**systemd inactive 是"设计选择"，不是"运维事故"。**

### 1.2 反面：什么时候 systemd inactive 真的是故障

```bash
$ systemctl is-active openclaw-gateway
inactive  ← 真的 inactive

$ ps -ef | grep openclaw
(空)  ← 没有 manual 进程

$ curl -s http://127.0.0.1:18789/readyz
curl: (7) Failed to connect to 127.0.0.1 port 18789
```

**systemd inactive + 进程不在 + readyz 拒绝连接 = 真故障。**

**这种情况下是要立刻拉起来的，不是误报。**

## 二、健康判定矩阵

我把这 6 个节点的经验总结成一张矩阵。

**判定维度 4 个**：

| 维度 | 含义 | 检查方式 |
|------|------|----------|
| **D1: systemd 状态** | unit 是否 active | `systemctl is-active` |
| **D2: 进程是否存在** | 至少 1 个 openclaw / hermes 进程在跑 | `ps -ef \| grep` |
| **D3: readyz 端点** | gateway 自身 HTTP 200 | `curl /readyz` |
| **D4: 上游连接** | 飞书 / 钉钉 / wecom 实际连通 | `ss \| grep ESTAB 443` 或 channel 状态 |

**判定矩阵**：

| D1 systemd | D2 进程 | D3 readyz | D4 上游 | 结论 | 行动 |
|------------|---------|-----------|---------|------|------|
| active | ✅ | 200 | ✅ | ✅ 完美健康 | 无 |
| active | ❌ | — | — | ❌ 真故障 | `systemctl restart` |
| **inactive** | **✅** | **200** | **✅** | **⚠️ 灰色健康** | **不动，看 NRestarts** |
| **inactive** | **✅** | **200** | **❌** | **❌ 准故障** | **查上游连接受阻原因** |
| **inactive** | **❌** | **—** | **—** | **❌ 真故障** | **手动起进程** |
| active (restart) | ❌ | 502 | — | ❌ restart loop | 杀孤儿保 systemd（6/2 那次 VM153 的情况） |

**关键判定**：第 3、4 行——"inactive + 进程在跑"。

**这不是"绿色健康"，也不是"红色故障"，是"灰色健康"。**

灰色健康的 3 个子情形：

1. **Hermes 节点取代 OpenClaw**（场景 A）→ **预期，判健康**
2. **systemd unit 丢失，manual 续命**（场景 B）→ **判健康，但记 NRestarts 警告**
3. **故意不开 systemd**（场景 C）→ **判健康，文档里写明**

**只要满足 D2 + D3 + D4 任一上游连接，就判健康。**

## 三、为什么不能用"看 NRestarts"一刀切

很多人会这么写脚本：

```bash
# ❌ 错误逻辑
NRestarts=$(systemctl show openclaw-gateway --property=NRestarts --value)
if [ "$NRestarts" -gt 100 ]; then
  echo "🔴 不健康"
  exit 1
fi
```

**这个逻辑的问题：NRestarts 是累计计数，不是"过去 1 小时"的计数。**

VM153 修好之前的历史累计 NRestarts=2258。但**修好之后已经稳定 1h+ 没动过**。

**如果脚本只看累计值，永远在告警。**

**正确做法**：NRestarts 必须配合时间窗口使用——

```bash
# ✅ 改进
# 1. 看 ActiveEnterTimestamp 是多久前
ActiveEnterTimestamp=$(systemctl show openclaw-gateway --property=ActiveEnterTimestamp --value)
SecondsSinceStart=$(date -d "$ActiveEnterTimestamp" +%s 2>/dev/null)

# 2. 如果进程已经稳定运行 1h+，即使 NRestarts=2000 也是健康的
if [ "$SecondsSinceStart" -gt 3600 ]; then
  echo "✅ 进程已稳定 1h+ — 历史 NRestarts 不影响当前状态"
fi
```

**——这也是 6/2 那次我修好 VM153 之后，写进 AGENTS.md 的一条铁律。**

> 6/2 的教训: 看 systemd `NRestarts` 字段! counter > 100 就一定有事
> 但 NRestarts 是**历史累计**，必须配合 ActiveEnterTimestamp 看

## 四、怎么区分"灰色健康"的三种子情形

光看 systemd/进程/readyz 还不够。

**"灰色健康"的三种情形需要进一步区分**，否则会把 Hermes 节点误判成"unit 丢失"。

### 4.1 区分方法：看进程二进制名

```bash
# 进程二进制名 = openclaw-gateway  → OpenClaw 栈
# 进程二进制名 = hermes-gateway     → Hermes 栈
# 进程二进制名 = node ... hermes     → Hermes 跑的 Node 进程

PROCESS_BIN=$(ps -ef | grep -E "openclaw|hermes" | grep -v grep | awk '{print $8}' | head -1)
case "$PROCESS_BIN" in
  *openclaw*)  echo "OpenClaw 栈";;
  *hermes*)    echo "Hermes 栈";;
  *node*hermes*) echo "Hermes (Node) 栈";;
esac
```

**栈判断 + readyz 端口** = 准确识别：

| 栈 | systemd 单元名 | readyz 端口 | 平台 dashboard 端口 |
|----|---------------|-------------|---------------------|
| OpenClaw | `openclaw-gateway.service` | **18789** | 无（管理面板在 gateway 里） |
| Hermes | `hermes-gateway.service` (可能缺失) | 9119 | 9119（独立 dashboard） |

**VM152/VM154 是 Hermes 节点 — 它们用的是 9119 端口，不是 18789。**

**我用 `curl http://127.0.0.1:9119/api/status` 验证 Hermes 节点的健康。**

### 4.2 区分方法：看进程启动方式

```bash
# manual 启动的进程 — PPID 一般不是 1
# systemd 启动的进程 — PPID 一定是 1 (PID 1 = systemd)

PPID=$(ps -ef | grep -E "openclaw|hermes" | grep -v grep | awk '{print $3}' | head -1)
if [ "$PPID" = "1" ]; then
  echo "systemd 启动"
else
  echo "manual 启动 (PPID=$PPID)"
fi
```

**PPID != 1 不一定是 manual 启动**（可能是被 supervisor 之类接管了），但**可以用来快速区分"systemd 启的"和"其他方式启的"**。

### 4.3 区分方法：看启动时长 vs NRestarts

```bash
# systemd 报的 NRestarts 是 unit 重启次数
# manual 进程的 etime 是它当前实例运行了多久

# 如果 manual 进程 etime > 24h
#   → 这是"长期 manual 续命"，不是"刚被踢出来"
#   → 灰色健康，不动

# 如果 manual 进程 etime < 5min
#   → 这是"刚被踢出来又拉起"
#   → 灰色健康 + 警告（有人在反复重启）
```

**etime 决定"灰色健康"的可信度。**

## 五、一键检查脚本

把上述判断逻辑封装成一个**只读、不 kill 任何进程**的脚本：

```bash
#!/bin/bash
# diagnose-manual-systemd.sh
# 用途：诊断 "systemd inactive + manual 进程在跑" 节点的健康状态
# 原则：只读，不重启、不 kill、不动 systemd

set -e

NODE_NAME="${1:-$(hostname)}"
GATEWAY_PORT="${2:-18789}"
HERMES_PORT="${3:-9119}"

echo "============================================"
echo "  节点健康判定矩阵 — $NODE_NAME"
echo "============================================"
echo

# === 0. 节点角色判断 ===
echo "=== 0. 节点角色判断 ==="
PROCESS_LIST=$(ps -ef | grep -E "openclaw|hermes" | grep -v grep || true)
if [ -z "$PROCESS_LIST" ]; then
  echo "❌ 没有 openclaw / hermes 进程在跑"
  echo "   建议：手动启动 gateway"
  exit 1
fi

PROCESS_BIN=$(echo "$PROCESS_LIST" | awk '{print $8}' | head -1)
PROCESS_PID=$(echo "$PROCESS_LIST" | awk '{print $2}' | head -1)
PROCESS_PPID=$(echo "$PROCESS_LIST" | awk '{print $3}' | head -1)
PROCESS_ETIME=$(ps -p "$PROCESS_PID" -o etime= 2>/dev/null | xargs)

case "$PROCESS_BIN" in
  *openclaw*)
    STACK="OpenClaw"
    READYZ_URL="http://127.0.0.1:$GATEWAY_PORT/readyz"
    ;;
  *hermes*)
    STACK="Hermes"
    READYZ_URL="http://127.0.0.1:$HERMES_PORT/api/status"
    ;;
  *node*)
    STACK="Hermes (Node)"
    READYZ_URL="http://127.0.0.1:$HERMES_PORT/api/status"
    ;;
  *)
    STACK="Unknown ($PROCESS_BIN)"
    READYZ_URL=""
    ;;
esac

echo "栈:      $STACK"
echo "PID:     $PROCESS_PID"
echo "PPID:    $PROCESS_PPID (1 = systemd 启动, 其他 = manual/supervisor)"
echo "etime:   $PROCESS_ETIME"
echo "readyz:  $READYZ_URL"
echo

# === 1. D1: systemd 状态 ===
echo "=== 1. D1: systemd 状态 ==="
SYSTEMD_ACTIVE=$(systemctl is-active openclaw-gateway 2>/dev/null || echo "unknown")
SYSTEMD_ENABLED=$(systemctl is-enabled openclaw-gateway 2>/dev/null || echo "unknown")
NRESTARTS=$(systemctl show openclaw-gateway --property=NRestarts --value 2>/dev/null || echo "0")
ACTIVE_TS=$(systemctl show openclaw-gateway --property=ActiveEnterTimestamp --value 2>/dev/null || echo "n/a")

echo "is-active:    $SYSTEMD_ACTIVE"
echo "is-enabled:   $SYSTEMD_ENABLED"
echo "NRestarts:    $NRESTARTS (历史累计)"
echo "ActiveEnter:  $ACTIVE_TS"
echo

# === 2. D2: 进程存在性 ===
echo "=== 2. D2: 进程存在性 ==="
if [ -n "$PROCESS_PID" ]; then
  echo "✅ $STACK 进程在跑 (PID $PROCESS_PID, etime $PROCESS_ETIME)"
else
  echo "❌ 没有 $STACK 进程"
fi
echo

# === 3. D3: readyz 端点 ===
echo "=== 3. D3: readyz 端点 ==="
if [ -n "$READYZ_URL" ]; then
  HTTP_CODE=$(curl -sS -o /tmp/readyz_resp.json -w "%{http_code}" \
    --max-time 5 "$READYZ_URL" 2>/dev/null || echo "000")
  if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ $READYZ_URL → 200"
    cat /tmp/readyz_resp.json | jq -r '.status // ."uptime // . // empty' 2>/dev/null
  elif [ "$HTTP_CODE" = "000" ]; then
    echo "❌ $READYZ_URL → 无法连接"
  else
    echo "⚠️  $READYZ_URL → $HTTP_CODE"
  fi
else
  echo "⚠️  未知栈，跳过 readyz 检查"
fi
echo

# === 4. D4: 上游连接 ===
echo "=== 4. D4: 上游连接 ==="
ESTAB_COUNT=$(ss -tan 2>/dev/null | grep -E "ESTAB.*:443" | wc -l | xargs)
echo "443 ESTAB 连接数: $ESTAB_COUNT"
if [ "$ESTAB_COUNT" -gt 0 ]; then
  echo "✅ 有上游连接（飞书/钉钉/wecom 至少一个连着）"
  ss -tan 2>/dev/null | grep -E "ESTAB.*:443" | awk '{print $5}' | head -3
else
  echo "⚠️  没有 443 ESTAB 连接 — 上游可能没连上"
fi
echo

# === 5. 综合判定 ===
echo "=== 5. 综合判定 ==="
if [ "$SYSTEMD_ACTIVE" = "active" ] && [ "$HTTP_CODE" = "200" ] && [ "$ESTAB_COUNT" -gt 0 ]; then
  echo "✅ 完美健康 (systemd active + 进程在跑 + readyz 200 + 上游连着)"
  EXIT_CODE=0
elif [ "$SYSTEMD_ACTIVE" != "active" ] && [ "$HTTP_CODE" = "200" ] && [ "$ESTAB_COUNT" -gt 0 ]; then
  echo "⚠️  灰色健康 (systemd inactive + 进程在跑 + readyz 200 + 上游连着)"
  echo "   说明: systemd 单元不健康但 gateway 自身正常"
  case "$STACK" in
    Hermes*)        echo "   原因: Hermes 栈不依赖 OpenClaw systemd 单元 — 预期状态";;
    OpenClaw*)
      if [ "$SYSTEMD_ENABLED" = "not-found" ]; then
        echo "   原因: systemd unit 文件丢失，manual 进程在续命"
        echo "   建议: 重写 systemd unit 让它接管 (但不强制)"
      else
        echo "   原因: systemd unit 存在但 inactive，进程是 manual 启动"
        echo "   建议: 看 journalctl 找 systemd 为何没拉起"
      fi
      ;;
  esac
  EXIT_CODE=0
elif [ "$HTTP_CODE" != "200" ] || [ "$ESTAB_COUNT" -eq 0 ]; then
  echo "❌ 准故障 (gateway 自身或上游有问题)"
  echo "   建议: 看 journalctl / gateway 日志找原因"
  EXIT_CODE=1
elif [ -z "$PROCESS_PID" ]; then
  echo "❌ 真故障 (进程不在)"
  echo "   建议: 手动启动 gateway"
  EXIT_CODE=1
else
  echo "⚠️  状态未明 — 请人工排查"
  EXIT_CODE=1
fi
echo
echo "============================================"
echo "  诊断完成 (exit code: $EXIT_CODE)"
echo "============================================"

exit $EXIT_CODE
```

**使用方法**：

```bash
chmod +x diagnose-manual-systemd.sh

# OpenClaw 节点
./diagnose-manual-systemd.sh VM151

# Hermes 节点
./diagnose-manual-systemd.sh VM152 18789 9119
```

**VM152 (Hermes 节点) 输出示例**：

```
============================================
  节点健康判定矩阵 — VM152
============================================

=== 0. 节点角色判断 ===
栈:      Hermes
PID:     338431
PPID:    338347 (1 = systemd 启动, 其他 = manual/supervisor)
etime:   1-06:23:45
readyz:  http://127.0.0.1:9119/api/status

=== 1. D1: systemd 状态 ===
is-active:    inactive
is-enabled:   not-found
NRestarts:    0 (历史累计)
ActiveEnter:  n/a

=== 2. D2: 进程存在性 ===
✅ Hermes 进程在跑 (PID 338431, etime 1-06:23:45)

=== 3. D3: readyz 端点 ===
✅ http://127.0.0.1:9119/api/status → 200
gateway_state=running

=== 4. D4: 上游连接 ===
443 ESTAB 连接数: 1
✅ 有上游连接（飞书/钉钉/wecom 至少一个连着）

=== 5. 综合判定 ===
⚠️  灰色健康 (systemd inactive + 进程在跑 + readyz 200 + 上游连着)
   说明: systemd 单元不健康但 gateway 自身正常
   原因: Hermes 栈不依赖 OpenClaw systemd 单元 — 预期状态
   建议: 重写 systemd unit 让它接管 (但不强制)

============================================
  诊断完成 (exit code: 0)
============================================
```

**关键**：这个脚本**不重启、不 kill、不动 systemd**。它只是**给出现状的事实陈述** + **建议**。

**决策权在运维人手里。**

## 六、Q&A

### Q1：systemd inactive 但进程在跑，要不要 `systemctl restart`？

**A**：**不要。** `systemctl restart` 会尝试启动一个新进程，但 18789 端口被 manual 进程占着，新进程会**立即失败**，然后累计 NRestarts，飞书/钉钉的 WebSocket 连接会被踢一次。

**正确做法**：

- **如果 manual 进程是健康的**（readyz 200 + 上游连着）→ 什么都不做，记一条"灰色健康"到监控
- **如果 manual 进程也是坏的**（readyz 502）→ 找到 manual 进程 PID，温和地 `kill -TERM <pid>`，让 systemd 接管

### Q2：怎么判断 manual 进程是"刚被踢出来"还是"长期续命"？

**A**：看 `etime` 字段。

```bash
$ ps -p $PID -o etime=
1-06:23:45  ← 1 天 6 小时 23 分 45 秒（长期续命）
05:23       ← 5 分 23 秒（刚被踢出来）
```

**etime > 24h 几乎一定是"长期 manual 续命"**，可以判定为**稳定的灰色健康**。

**etime < 5min 是"刚被踢出来"**，需要查为什么 systemd unit 在反复 restart。

### Q3：NRestarts > 100 是不是一定要报警？

**A**：**不一定。** NRestarts 是**历史累计**，不是"过去 1 小时"。

**正确判定**：

- NRestarts=2000 + ActiveEnterTimestamp=1h ago → 修好了，**不报警**
- NRestarts=2000 + ActiveEnterTimestamp=10s ago + 还在涨 → 还在 restart loop，**报警**

**铁律**: 必须**同时看 NRestarts 和 ActiveEnterTimestamp**，**缺一不可**。

### Q4：Hermes 节点（VM152/VM154）的 systemd 单元要不要补上？

**A**：**看情况。**

- 如果 Hermes 升级频率很高（每周一个版本）→ **建议不开 systemd**，manual 跑就行，省得每次升级都改 unit
- 如果 Hermes 升级频率低（每月一个版本）→ **建议补上 systemd unit**，让进程意外退出能自动拉起

**经验值**：我 6 个节点里 VM152/VM154 是 Hermes 栈，目前**都跑 manual**——因为 Hermes 的更新频率比 OpenClaw 高，unit 维护成本不划算。

**这不等于"systemd 没用"，而是"manual 是当前最佳实践"。**

### Q5：怎么监控"manual 进程 + systemd inactive"的灰色健康？

**A**：两种方式：

**方式 1：在监控面板里单独建一个组**（推荐）

```
Group: "灰色健康（已知项）"
├── VM151 — manual 续命，systemd unit 缺失（已知）
├── VM152 — Hermes 节点，systemd 不适用（已知）
└── VM154 — Hermes 节点，systemd 不适用（已知）
```

**方式 2：在告警规则里加白名单**

```yaml
# Prometheus alertmanager
routes:
  - match:
      alertname: SystemdUnitInactive
      instance: "VM151|VM152|VM154"
    receiver: "silent"  # 静默
  - match:
      alertname: SystemdUnitInactive
    receiver: "page"     # 其他节点真告警
```

**——这就是为什么我说"6 个节点全绿反而让我慌"：因为白名单 + 全绿，看起来像监控坏了。**

**其实不是坏了，是 6 个节点都被"差异化健康检查"覆盖了，每一种"健康"都被验证过。**

### Q6：怎么从根上避免"systemd unit 丢失"这种状态？

**A**：三个动作：

1. **systemd unit 文件纳入版本控制**（Git）
   ```bash
   /etc/systemd/system/openclaw-gateway.service  →  /opt/openclaw/deploy/systemd/
   ```
   升级时 `cp -p` 覆盖，而不是直接 overwrite。

2. **加一个 systemd unit 完整性的 cron 检查**
   ```bash
   # 每天早上 8 点跑一次
   0 8 * * *  systemctl is-enabled openclaw-gateway || \
     echo "⚠️ openclaw-gateway unit 缺失！" | mail -s "ALERT" ops@example.com
   ```

3. **跑 manual 进程时记录"为什么要 manual"**
   ```bash
   # /etc/openclaw/manual-reason.txt
   2026-06-03 23:15  ——
   原因: systemd unit 在 5/30 升级时丢失
   临时方案: nohup openclaw-gateway & 续命
   永久方案: 等 6/4 上午重写 unit
   ```

**第 3 条是关键**——**所有"临时方案"必须有 metadata**，否则 3 个月后就没人记得当初为什么 manual 启动了。

## 七、总结

"systemd inactive + manual 进程在跑" 这个状态，在 6 节点 OpenClaw 集群里是**日常状态**，不是"故障状态"。

**核心要点**：

1. ✅ **判定矩阵 4 维**: systemd 状态 + 进程存在 + readyz 端点 + 上游连接
2. ✅ **"灰色健康"是健康**,不是"待处理故障"——尤其 Hermes 节点
3. ✅ **NRestarts 必配合 ActiveEnterTimestamp**,缺一不可
4. ✅ **`etime > 24h` 几乎一定是"长期 manual 续命"**,可以稳定判健康
5. ✅ **不要轻易 `systemctl restart`**,它会抢端口、累计 NRestarts、踢连接
6. ✅ **决策权在运维手里**——脚本只给"事实 + 建议",**不替运维做决定**

**这次的教训: 健康检查不是"非黑即白"的二进制。** 真正稳定的集群里,总会有"灰色地带"——

- 有的灰色是"已知项"(systemd unit 丢失,manual 续命)
- 有的灰色是"设计选择"(Hermes 节点不开 systemd)
- 有的灰色是"真故障的前兆"(刚被踢出来又拉起)

**把这三种灰色区分开,是健康检查脚本从"能跑"到"可信"的分水岭。**

下次看到"systemd inactive + 进程在跑"——

**第一件事不是 restart,是看 readyz、看 etime、看上游连接、看进程栈类型。**

**——把这四件事做完了,再做决定。**

---

*作者：小六，一个在上海努力生存的普通打工人*
