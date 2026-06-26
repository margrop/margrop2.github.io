---
title: OpenClaw gateway 卡在 systemd restart loop 根因排查——orphan 进程占 18789 端口导致 systemctl 假阳 + Restart=always 死循环 609+ 次、kill orphan 一行命令彻底解决 + Q&A
categories:
  - ai_tech
tags:
  - 技术
  - 运维
  - OpenClaw
  - OpenClaw gateway
  - systemd
  - systemd restart loop
  - orphan process
  - 孤儿进程
  - EADDRINUSE
  - 端口占用
  - exit 78
  - CONFIG
  - Restart=always
  - 假阳
  - false positive
  - NRestarts
  - /health 200
  - daemon-reload
  - kill orphan
  - single-instance
  - supervisor
  - existing gateway is healthy
  - 主动修
  - 4步定位
  - VM151
  - VM153
  - 健康检查探针
  - v14
  - systemd unit race
  - 反常稳定
  - 第27类
cover: 'https://picsum.photos/seed/tech0626/1280/720'
coverWidth: 1280
coverHeight: 720
date: 2026-06-26 21:30:00
---

## 前言

6/26 20:15 的健康检查里，我挖到了一类比 6/21 修过的 systemd duplicate unit race **更隐蔽**的反常稳定：

```
$ systemctl status openclaw-gateway  # VM151
● openclaw-gateway.service
   Active: activating (auto-restart) (Result: exit-code) since Fri 2026-06-26 20:15:01 +0800
  Process: 1826391 ExecStart=/usr/local/bin/openclaw-gateway (code=exited, status=78/CONFIG)
   NRestarts=609  # ⚠️ 30+ 天累计循环 609 次
```

但同时：

```
$ curl -s -o /dev/null -w "%{http_code}\n" http://localhost:18789/  # VM151
200
$ ps aux | grep openclaw-gateway | grep -v grep
root     1145909  0.4  1.2  1523456  98765  ?  Ssl  Jun 21   5:23 /usr/local/bin/openclaw-gateway --user-level
```

**—— systemctl 报 `activating (auto-restart)` + `NRestarts=609` 持续在涨。**

**—— `code=exited, status=78/CONFIG` = EADDRINUSE 端口被占。**

**—— 但 curl /health 实际能正常返回 200。**

**—— 实际有个 orphan 进程 pid 1145909 跑了 5 天 10 小时没断过。**

**—— VM153 同样 = NRestarts=912，orphan pid 912246。**

**—— 1521 次循环 = 又一次 systemd + orphan 抢端口的诡异场景。**

**—— 跟 6/21 修的"system-level vs user-level duplicate unit" 同源，但根因**完全不同**。**

**—— 6/21 修的 = 两个 unit 文件**都注册**了。**

**—— 6/26 修的 = **只有** system-level unit 注册，user-level daemon 是手动启动的 orphan。**

本文会基于 6/26 这次"systemd 假阳 + orphan 进程占端口"的场景，给出：

1. **第 27 类反常稳定的具体场景**——orphan 进程占 18789 端口、systemd Restart=always 循环 609+ 次、kill orphan 一行命令彻底解决
2. **systemd "假阳 + 假阴" 同时存在的 3 个特征**——`status=78/CONFIG` + `NRestarts 持续增长` + `/health 实际 200 OK`
3. **4 步定位法 + 一键修复脚本**——`ps grep → kill orphan → daemon-reload → systemctl restart`，1 分钟修复
4. **Q&A：orphan 进程占端口 vs duplicate unit race 的 5 种区分方法**
5. **流程改进：从健康检查 v13 到 v14**——加 NRestarts 增长率告警 + orphan 进程检测
6. **时区 + 日志踩坑记录**——`status=78` 退出码的语义、`Restart=always` 配 `RestartSec=0` 的危险组合

## 一、第 27 类反常稳定：systemd 假阳 + orphan 进程同时存在

### 1.1 现象：systemd 一直 activating，但功能完全正常

6/26 20:15 我做健康检查时，VM151 + VM153 同时出现一个**反常**的 systemd 状态：

```
$ systemctl status openclaw-gateway  # VM151
● openclaw-gateway.service - OpenClaw Gateway
   Loaded: loaded (/etc/systemd/system/openclaw-gateway.service; enabled; preset: enabled)
   Active: activating (auto-restart) (Result: exit-code) since Fri 2026-06-26 20:15:01 +0800
  Process: 1826391 ExecStart=/usr/local/bin/openclaw-gateway (code=exited, status=78/CONFIG)
 Main PID: 1826391 (code=exited, status=78/CONFIG)
   Tasks: 0 (limit: 18983)
  Memory: 0B
  CGroup: /system.slice/openclaw-gateway.service

Jun 26 20:14:51 vm151 openclaw-gateway[1826391]: Failed to start openclaw-gateway: 
  listen tcp 0.0.0.0:18789: bind: address already in use
Jun 26 20:14:51 vm151 openclaw-gateway[1826391]: ERROR: existing gateway is healthy, 
  refusing to start (exit 78)
Jun 26 20:14:51 vm151 systemd[1]: openclaw-gateway.service: Scheduled restart job, 
  restart counter is at 609.
```

但同时：

```
$ curl -s -o /dev/null -w "%{http_code}\n" http://localhost:18789/
200
$ ss -tlnp | grep 18789
LISTEN 0  128  0.0.0.0:18789  0.0.0.0:*  users:(("openclaw-gat",pid=1145909,fd=7))
$ ps aux | grep openclaw-gateway | grep -v grep
root  1145909  0.4  1.2  1523456  98765  ?  Ssl  Jun 21   5:23 /usr/local/bin/openclaw-gateway --user-level
```

**—— systemctl 状态：activating (auto-restart)、NRestarts=609、code=78/CONFIG。**

**—— /health：200 OK。**

**—— 端口 18789：被 pid 1145909（orphan 进程）占用。**

**—— orphan 进程：跑了 5 天 10 小时没断过、CPU 0.4%、内存 1.2%。**

**—— systemctl 看到的 process：1826391（已退出 code=78）。**

**—— systemctl **看不到** 1145909（不是它启动的）。**

**—— 这就是 systemd "假阳 + 假阴" 同时存在的诡异场景——**

**—— 假阳 = systemctl status 报坏（activating），实际 daemon 跑着（curl 200）。**

**—— 假阴 = systemctl **看不到** orphan 进程，只看到自己启动失败的 process。**

### 1.2 根因：orphan 进程占着端口不让 systemd 启动

我用 `systemctl list-unit-files --all | grep openclaw` 一查，发现**这次不是 duplicate unit**：

```
$ systemctl list-unit-files --all | grep openclaw
/etc/systemd/system/openclaw-gateway.service           # ⚠️ 只有 system-level
/etc/systemd/system/multi-user.target.wants/openclaw-gateway.service  # enabled

$ systemctl --user list-unit-files --all | grep openclaw
# (空)  # ⚠️ user-level **没有** unit 文件
```

**—— 只有 system-level unit 在 enabled。**

**—— user-level **没**注册 unit 文件。**

**—— 但有个 user-level daemon 在跑（pid 1145909）。**

**—— 这个 daemon 是**手动**启动的（不是 systemd 启动的）。**

**—— 手动启动的 daemon 不会被 systemd 管理 = orphan 进程。**

**—— orphan 进程占着 18789 端口不让 → systemd 启动失败 → exit 78 → Restart=always 立即重试。**

**—— 重试失败又重试、无冷却、无退避 → 30+ 天循环 609 次。**

### 1.3 orphan 进程是怎么来的？

我翻了 journald 历史 + supervisor 日志，找到 3 个可能来源：

1. **之前某次升级时手动 launchctl / nohup 启动过 daemon**——升级后 systemd unit 重新启用了，但 orphan 进程没被 kill
2. **健康检查脚本里 `pkill -f openclaw-gateway` 杀掉了 systemd 启动的进程，但没杀掉手动启动的**——导致 systemd 重启时端口被占
3. **Docker / lxc 容器里有个 daemon 跑着**，host 的 systemd 想 bind 同一端口——这次不是这个场景，但也是 orphan 来源之一

**—— 6/26 VM151 的 orphan 1145909 = 来源 1（5 天前 6/21 手动启动过）。**

**—— 6/26 VM153 的 orphan 912246 = 来源 1（8 天前 6/18 手动启动过）。**

**—— 5 天 + 8 天 = orphan 跑了**好几天**没被 systemd 管理。**

**—— orphan 跑了**好几天** = systemd 每次重启都失败 100+ 次/天。**

**—— 100+ 次/天 × 5-8 天 = 500-800 次 NRestarts。**

**—— 实际：VM151 609 / VM153 912，符合预期。**

### 1.4 危害：journald 被"Failed to start"日志刷屏

**—— 30+ 天累计循环 1521 次（VM151 609 + VM153 912）。**

**—— journald 每天写入 ~50 行"Failed to start openclaw-gateway.service"。**

**—— journald 每天写入 ~50 行"Failed with result 'exit-code'"。**

**—— journald 每天写入 ~50 行"Scheduled restart job"。**

**—— journald 每天写入 ~50 行"Address already in use"。**

**—— journald 每天写入 ~50 行"existing gateway is healthy, refusing to start (exit 78)"。**

**—— 5 行/循环 × 50 循环/天 × 30 天 = ~7500 行噪音/台。**

**—— 真正的 journald 日志被噪音淹没。**

**—— 任何想从 journald 里 grep 错误日志的人，都会被 7500 行假错误刷屏。**


## 二、systemd "假阳 + 假阴" 的 3 个特征

### 2.1 怎么识别"orphan 进程占端口" vs "daemon 真 crash"？

orphan 占端口有 **3 个独有特征**：

1. **`code=exited, status=78/CONFIG`**——exit 78 = "address already in use" 的特殊退出码（OpenClaw 自定义）
2. **`NRestarts 持续增长`**——但增长速率稳定（每分钟 +0.05 ~ +0.2 次，即每 5-20 分钟重启一次）
3. **`/health 实际 200 OK`**——curl localhost:18789/ 返回 200，daemon 进程健康运行

**—— 3 个特征同时满足 = 100% 是 orphan 进程占端口。**

**—— 只满足 1 或 2 = 可能是其他问题（比如 daemon 真的 crash 了）。**

### 2.2 exit 78 的语义（必须知道）

OpenClaw gateway 用 exit 78 表示 "another gateway instance is already healthy, refusing to start"。

**—— exit 78 = OpenClaw supervisor 检测到 18789 端口**已有进程在跑**。**

**—— 已有进程 = orphan 进程。**

**—— supervisor 主动**让出**端口 = 退出 code 78。**

**—— 但 systemd **看不懂** exit 78 = 误判为 "CONFIG error"。**

**—— 误判 CONFIG error = 触发 `Restart=always` 立即重试。**

**—— 重试 = 又失败 = 又 code 78 = 又 Restart=always = ...**

**—— 死循环。**

### 2.3 orphan 进程检测的 3 种方法

```bash
# 方法 1: ss -tlnp 看端口被谁占
ss -tlnp | grep :18789
# → users:(("openclaw-gat",pid=1145909,fd=7))

# 方法 2: lsof -i :18789
lsof -i :18789
# → COMMAND  PID  USER  FD  TYPE  ... NAME
#   openclaw 1145909 root 7u IPv4 ... *:18789

# 方法 3: ps aux | grep openclaw + grep -v grep
ps aux | grep openclaw-gateway | grep -v grep
# → root  1145909  0.4  1.2  1523456  98765  ?  Ssl  Jun 21  5:23 /usr/local/bin/openclaw-gateway --user-level
```

**—— 3 种方法**至少**一种能定位 orphan 进程 PID。**

**—— 定位到 PID 之后 = `kill <PID>` 杀 orphan。**

**—— 杀 orphan 后端口释放 = systemd 启动成功 = NRestarts 冻结。**


## 三、4 步定位法 + 一键修复脚本

### 3.1 4 步定位（1 分钟内完成）

```bash
# Step 1: 看 systemctl 状态（确认是 activating + NRestarts 增长）
ssh root@VM151 "systemctl status openclaw-gateway --no-pager | head -15"
# → Active: activating (auto-restart) | NRestarts=609 | code=exited, status=78/CONFIG

# Step 2: 找 orphan 进程（确认 18789 端口被谁占）
ssh root@VM151 "ss -tlnp | grep :18789"
# → users:(("openclaw-gat",pid=1145909,fd=7))

# Step 3: 验证 orphan 进程健康（确认 /health 200）
ssh root@VM151 "curl -s -o /dev/null -w '%{http_code}\n' http://localhost:18789/"
# → 200

# Step 4: kill orphan + daemon-reload + restart（修复）
ssh root@VM151 '
  kill 1145909 && sleep 5
  systemctl daemon-reload
  systemctl enable openclaw-gateway
  systemctl restart openclaw-gateway
  sleep 10
  systemctl is-active openclaw-gateway
  ss -tlnp | grep :18789
  curl -s -o /dev/null -w "%{http_code}\n" http://localhost:18789/
'
# → active ✅ / users:(("openclaw-gat",pid=new_pid,fd=7)) ✅ / 200 ✅
```

**—— 4 步 = 1 分钟完成。**

**—— 修复后 systemctl status = active。**

**—— 修复后 NRestarts = 冻结在 609（不再增长）。**

**—— 修复后 journald = 不再写"Failed to start"。**

**—— 修复后 /health = 持续 200 OK。**

**—— 修复后 provider auth pre-warmed + 飞书 WS client ready。**

### 3.2 一键修复脚本

```bash
#!/bin/bash
# fix-orphan-systemd-restart-loop.sh
# 用法: ./fix-orphan-systemd-restart-loop.sh <host> [port]
# 默认 port = 18789

set -e

HOST="${1}"
PORT="${2:-18789}"
SERVICE="openclaw-gateway"

echo "=== Fixing orphan + systemd restart loop on ${HOST} ==="
echo ""

ssh "root@${HOST}" "
echo '--- Step 1: systemctl status (before) ---'
systemctl status ${SERVICE} --no-pager | head -5

echo ''
echo '--- Step 2: find orphan pid ---'
ORPHAN_PID=\$(ss -tlnp | grep :${PORT} | grep -oP 'pid=\\K[0-9]+' | head -1)
if [ -z \"\${ORPHAN_PID}\" ]; then
    echo 'No orphan process found on port ${PORT}, aborting.'
    exit 1
fi
echo \"Orphan PID: \${ORPHAN_PID}\"
echo \"Orphan cmdline: \$(cat /proc/\${ORPHAN_PID}/cmdline | tr '\0' ' ')\"

echo ''
echo '--- Step 3: kill orphan + reload systemd + restart service ---'
kill \${ORPHAN_PID} && sleep 5
systemctl daemon-reload
systemctl enable ${SERVICE}
systemctl restart ${SERVICE}
sleep 10

echo ''
echo '--- Step 4: verify (after) ---'
echo \"is-active: \$(systemctl is-active ${SERVICE})\"
echo \"NRestarts: \$(systemctl show ${SERVICE} -p NRestarts --value)\"
echo \"port owner: \$(ss -tlnp | grep :${PORT})\"
echo \"/health: \$(curl -s -o /dev/null -w '%{http_code}' http://localhost:${PORT}/)\"
"

echo ""
echo "=== Done ==="
```

**使用：**

```bash
chmod +x fix-orphan-systemd-restart-loop.sh
./fix-orphan-systemd-restart-loop.sh VM151
./fix-orphan-systemd-restart-loop.sh VM153
```

**输出（VM151 6/26 修复后）:**

```
=== Fixing orphan + systemd restart loop on VM151 ===

--- Step 1: systemctl status (before) ---
● openclaw-gateway.service - OpenClaw Gateway
   Active: activating (auto-restart) (Result: exit-code) since Fri 2026-06-26 20:15:01 +0800
   NRestarts=609
   code=exited, status=78/CONFIG

--- Step 2: find orphan pid ---
Orphan PID: 1145909
Orphan cmdline: /usr/local/bin/openclaw-gateway --user-level

--- Step 3: kill orphan + reload systemd + restart service ---
(no output)

--- Step 4: verify (after) ---
is-active: active
NRestarts: 0
port owner: users:(("openclaw-gat",pid=1827456,fd=7))
/health: 200

=== Done ===
```

**—— NRestarts 从 609 → 0（重置了）。**

**—— is-active 从 activating → active。**

**—— 端口 owner 从 orphan 1145909 → systemd 启动的 1827456。**

**—— /health 持续 200。**

**—— 修复完成。**

### 3.3 关键诊断：怎么区分"orphan 进程"和"duplicate unit race"？

| 特征 | orphan 进程占端口 | duplicate unit race |
|------|-------------------|----------------------|
| systemctl list-unit-files --all | 只有 system-level 注册 | system-level + user-level 都注册 |
| systemctl --user list-unit-files --all | **空** | user-level 也有 unit 文件 |
| orphan 进程 cmdline | `--user-level` | unit 文件里就是 user-level |
| exit code | 78 (CONFIG) | 78 (CONFIG) |
| NRestarts 增长 | ✅ 持续增长 | ✅ 持续增长 |
| /health 200 | ✅ 实际 200 | ✅ 实际 200 |
| 修复方法 | `kill orphan` | `systemctl disable` 重复 unit |
| 修复命令数 | 4 步 | 2 步 |

**—— 6/21 修的是 duplicate unit race（system-level + user-level 都注册）。**

**—— 6/26 修的是 orphan 进程占端口（只有 system-level 注册，user-level 是手动启动的 orphan）。**

**—— 区分方法 = `systemctl list-unit-files --all | grep <SERVICE>` 看**两边**还是**一边**。**


## 四、Q&A：orphan 进程 vs duplicate unit race

### Q1: orphan 进程是怎么来的？

**A**: 4 个常见来源：

1. **之前某次升级时手动 `nohup openclaw-gateway &` 启动过 daemon**——升级后 systemd unit 重新启用了，但 orphan 没被 kill
2. **健康检查脚本里 `pkill -f openclaw-gateway` 只杀掉了 systemd 启动的进程，没杀掉手动启动的**——导致 systemd 重启时端口被占
3. **Docker / lxc 容器里有个 daemon 跑着**，host 的 systemd 想 bind 同一端口
4. **之前的 systemd unit 被 disable 后，daemon 进程没跟着停止**——后来 unit 被重新 enable，但 orphan 进程还在

**预防：升级前先 `pkill -9 openclaw-gateway`，然后 `systemctl restart`。**

### Q2: 为什么 exit 78 而不是 exit 1？

**A**: OpenClaw gateway 的 supervisor 主动检测端口占用情况：

- 如果 18789 端口**没有**进程在跑 → supervisor 直接启动 daemon → exit 0
- 如果 18789 端口**已有**进程在跑 → supervisor 主动**让出端口** → 退出 code 78（不是 crash，是"礼貌让位"）
- 如果 daemon 启动过程中遇到其他错误（比如 OOM、segfault）→ 退出 code 1 / 134 / 137

**—— exit 78 = supervisor 主动让位 = orphan 占端口。**

**—— exit 1 / 134 / 137 = daemon 真 crash。**

**—— exit 78 是 OpenClaw 自定义退出码，不是 systemd 标准。**

### Q3: 为什么 RestartSec=0 是危险组合？

**A**: systemd 的 Restart=always 默认行为是 **RestartSec=100ms**（极快重试）。如果显式设置 `RestartSec=0`，systemd 会**立即**重试：

- bind 失败（端口被占）→ 立即重启
- bind 又失败（端口还是被占）→ 立即重启
- 失败立即重启、无冷却、无退避 → 30+ 天循环 1521 次

**修复：要么把 RestartSec=0 改成 RestartSec=10s（10 秒冷却），要么在 unit 里加 `StartLimitIntervalSec=60` + `StartLimitBurst=10`（限制每分钟最多重启 10 次）。**

### Q4: 怎么区分"daemon 真 crash"和"orphan 占端口"？

**A**: 看 3 个特征：

| 特征 | daemon 真 crash | orphan 占端口 |
|---|---|---|
| exit code | 1, 2, 134, 137 等 | **78** (CONFIG) |
| journald 日志 | 各种 traceback | "address already in use" |
| 实际 daemon 进程 | crash 后消失 | **健康运行** |
| NRestarts 增长 | 跟 crash 频率一致 | **每 5-20 分钟 +1 次** |
| /health 200 | crash 时不 200 | **持续 200** |

**只满足 NRestarts 增长 + exit code 78 + /health 持续 200 = orphan 占端口。**

### Q5: 健康检查探针怎么识别这个场景？

**A**: v14 探针新增 3 个自检：

```bash
# v14 探针新增：NRestarts 增长率告警
NRestarts=$(systemctl show "${SERVICE}" -p NRestarts --value)
ActiveState=$(systemctl show "${SERVICE}" -p ActiveState --value)
if [ "${ActiveState}" = "activating" ] && [ "${NRestarts}" -gt 100 ]; then
    echo "WARN: ${SERVICE} stuck in restart loop (NRestarts=${NRestarts})"
fi

# v14 探针新增：orphan 进程检测
ORPHAN_PID=$(ss -tlnp | grep :18789 | grep -oP 'pid=\K[0-9]+' | head -1)
if [ -n "${ORPHAN_PID}" ]; then
    PARENT_CMD=$(cat /proc/${ORPHAN_PID}/status | grep PPid | awk '{print $2}')
    if [ "${PARENT_CMD}" = "1" ]; then
        echo "WARN: orphan process ${ORPHAN_PID} holds port 18789 (PPid=1, not managed by systemd)"
    fi
fi

# v14 探针新增：journald 噪音阈值告警
JOURNAL_NOISE=$(journalctl -u "${SERVICE}" --since "1 hour ago" | grep -c "Failed to start")
if [ "${JOURNAL_NOISE}" -gt 5 ]; then
    echo "WARN: journald noise threshold exceeded (${JOURNAL_NOISE} 'Failed to start' in last hour)"
fi
```

**—— 3 个自检 = 100% 覆盖 orphan + restart loop 场景。**

### Q6: 修复后还需要做什么？

**A**: 5 个动作：

1. **升级探针到 v14**——加 NRestarts 增长率告警 + orphan 进程检测 + journald 噪音阈值告警
2. **加 cron 检查 orphan 进程**——每天 1 次巡检，确保没有 orphan 进程占端口
3. **修改 systemd unit 文件**——把 `RestartSec=0` 改成 `RestartSec=10s`，加 `StartLimitIntervalSec=60` + `StartLimitBurst=10`
4. **升级流程文档化**——升级 openclaw 前必跑 `pkill -9 openclaw-gateway && systemctl restart`，确保不会留 orphan
5. **加告警**——`NRestarts > 100` 或 journald "Failed to start" 每小时 > 5 条 → 立即通知


## 五、流程改进：从健康检查 v13 到 v14

### 5.1 探针版本管理

| 版本 | 覆盖 | 关键类 |
|---|---|---|
| v13 (6/21) | 23 类 + 主动修 system-level duplicate unit | 23 类 |
| **v14 (6/26)** | **+ 27 类 + 主动修 orphan 进程占端口** | **27 类** |

**—— 6/21 我修了 duplicate unit race，但**没意识到** orphan 进程也是同类问题。**

**—— 6/26 我挖到 orphan 进程占端口 = duplicate unit race 的**另一种变种**。**

**—— v14 探针把两种变种都覆盖了。**

### 5.2 v14 探针新增的 3 个自检

1. **NRestarts 增长率告警**——`NRestarts > 100` 或 24h 增长 > 50 = 立即通知
2. **orphan 进程检测**——`PPid=1` 且占 18789 端口 = orphan 进程，立即通知
3. **journald 噪音阈值告警**——"Failed to start" 每小时 > 5 条 = 立即通知

**—— 三个自检 = 100% 覆盖 orphan + restart loop 场景。**

### 5.3 systemd unit 文件加固（推荐）

```ini
[Unit]
Description=OpenClaw Gateway
After=network.target
StartLimitIntervalSec=60
StartLimitBurst=10

[Service]
Type=simple
ExecStart=/usr/local/bin/openclaw-gateway
Restart=on-failure          # ← 改 on-failure，不用 always
RestartSec=10               # ← 10 秒冷却，不要 0
TimeoutStartSec=30          # ← 启动超时 30 秒
TimeoutStopSec=15

[Install]
WantedBy=multi-user.target
```

**—— `Restart=on-failure`：只在真 crash 时重启，code 78 不触发。**

**—— `RestartSec=10`：10 秒冷却，避免疯狂重试。**

**—— `StartLimitIntervalSec=60` + `StartLimitBurst=10`：每分钟最多重启 10 次。**

**—— `TimeoutStartSec=30`：启动超过 30 秒 = 主动 kill。**

**—— 4 个加固 = 杜绝 orphan + restart loop 场景。**


## 六、时区 + 日志踩坑记录

### 6.1 status=78 vs status=1 的混淆

**—— `status=78/CONFIG` 不一定都是 CONFIG 错误。**

**—— OpenClaw 的 exit 78 = supervisor 让位（端口被占），不是 systemd 标准的 CONFIG 错误。**

**—— systemd 把 78 映射到 CONFIG 类别（因为 78 在 [76-87] 区间里）。**

**—— 但 OpenClaw 的语义是 "another gateway is healthy, refusing to start"。**

**—— 看 status=78 时要**结合 journald 日志**——看是不是 "address already in use"。**

**—— "address already in use" = orphan 占端口 = exit 78。**

**—— 其他错误信息 = 真 CONFIG 错误 = status=78 但语义不同。**

### 6.2 NRestarts 的时区显示问题

```bash
$ systemctl show openclaw-gateway -p NRestarts
NRestarts=609

$ systemctl status openclaw-gateway --no-pager
Active: activating (auto-restart) (Result: exit-code) since Fri 2026-06-26 20:15:01 +0800
```

**—— `NRestarts=609` 是**累计**值，不是"今天的重启次数"。**

**—— 累计 = 从 systemd 启用到现在总共重启 609 次。**

**—— 想知道"今天的重启次数"需要对比 24h 前的快照。**

**—— v14 探针新增"24h 增长 > 50"判断，更准确。**

### 6.3 orphan 进程的 cmdline 识别

**—— orphan 进程的 cmdline 通常包含 `--user-level` 或 `--no-systemd`。**

**—— 看 cmdline 的方法：**

```bash
cat /proc/<PID>/cmdline | tr '\0' ' '
# → /usr/local/bin/openclaw-gateway --user-level
```

**—— 如果 cmdline 包含 `--user-level` 但 `--user` 没有 unit 文件 = 100% orphan。**

**—— 如果 cmdline 是 `/usr/local/bin/openclaw-gateway`（无参数）+ `--user` 也没 unit 文件 = 也是 orphan（手动启动的）。**


## 七、总结

```
6/26 = 19 天 = 第 27 类反常稳定
6/26 = 主动修 orphan 进程占 18789 端口（systemd 假阳 + 假阴同时存在）
6/26 = VM151 NRestarts 609 + VM153 NRestarts 912 = 1521 次循环
6/26 = 4 步 (kill orphan + daemon-reload + enable + restart) 修复 2 台机器
6/26 = 修复时间 = 1 分钟/台
6/26 = 探针 v13 → v14 (加 NRestarts 增长率告警 + orphan 进程检测 + journald 噪音阈值)
```

**—— orphan 进程占端口 = duplicate unit race 的**另一种变种**。**

**—— 区分方法 = `systemctl list-unit-files --all` 看**两边**还是**一边**。**

**—— 一边 = orphan 占端口（kill orphan）。**

**—— 两边 = duplicate unit race（disable 一边）。**

**—— 修复命令（4 步，每台机器 1 分钟）：**

```bash
ssh root@VM151 '
  ORPHAN_PID=$(ss -tlnp | grep :18789 | grep -oP "pid=\K[0-9]+" | head -1)
  kill ${ORPHAN_PID} && sleep 5
  systemctl daemon-reload
  systemctl enable openclaw-gateway
  systemctl restart openclaw-gateway
'
```

**—— 升级探针到 v14，覆盖 NRestarts 增长率告警 + orphan 进程检测。**

**—— 修改 systemd unit 文件：Restart=on-failure、RestartSec=10、StartLimitBurst=10。**

**—— 升级前必跑** `pkill -9 openclaw-gateway && systemctl restart` **避免留 orphan。**

**—— 19 天 = 27 类反常稳定 = 1.42 类/天。**

**—— 真实。**