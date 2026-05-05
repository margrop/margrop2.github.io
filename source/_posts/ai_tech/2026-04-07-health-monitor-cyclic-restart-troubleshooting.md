---
title: 记一次健康检查进程循环重启的完整排查：从日志分析到 systemd 配置修复
categories:
  - ai_tech
tags:
  - 技术
  - 运维
  - 健康检查
  - systemd
  - 问题排查
cover: 'https://picsum.photos/seed/tech0407/1280/720'
coverWidth: 1280
coverHeight: 720
date: 2026-04-07 21:30:00
---

# 记一次健康检查进程循环重启的完整排查：从日志分析到 systemd 配置修复

## 前言

在运维工作中，最让人头疼的问题之一就是进程循环重启——进程看起来在运行，但总是莫名其妙地不断重启，既不彻底挂掉给你重建的机会，也不完全正常地提供服务。这种"薛定谔的进程"排查起来往往让人抓狂。

今天要分享的是一次典型的健康检查进程循环重启问题：监控显示某 VM 每隔 10-15 分钟就会重启一次健康监控进程，但进程本身并没有彻底崩溃，服务也还在运行。本文将详细记录整个排查过程，从日志分析到根因定位再到完整修复方案，希望能给遇到类似问题的同学一些参考。

## 问题背景

### 业务场景

我们的 OpenClaw 系统中，每台服务器都部署了健康检查服务（health monitor），用于定时检测 Gateway、Chrome、WoClaw 等关键组件的运行状态。当发现问题时，监控系统会记录日志并尝试自动修复。

某日监控告警显示，VM152 和 VM153 两台服务器的健康检查进程出现了异常行为：每隔固定时间间隔就会重启一次。

### 问题现象

| 服务器 | 重启间隔 | 服务状态 | 告警级别 |
|--------|----------|----------|----------|
| VM152 | 约 10 分钟 | Gateway 正常运行 | 🟡 警告 |
| VM153 | 约 15 分钟 | Gateway 正常运行 | 🟡 警告 |

**关键现象**：虽然健康检查进程不断重启，但 Gateway 本身还在正常运行，RPC probe 正常，消息通道也连接正常。

这说明：健康检查进程的问题并没有影响到核心服务，但这个异常本身需要修复，否则会导致监控数据不准确、无法及时发现真正的异常。

### 环境信息

| 项目 | VM152 | VM153 |
|------|-------|-------|
| OS | Ubuntu 24.04 | Ubuntu 24.04 |
| Gateway 版本 | 2026.3.x | 2026.3.x |
| 健康检查方式 | systemd timer | systemd timer |
| 上次重启原因 | 未知 | 未知 |

## 排查过程

### 第一步：确认 systemd 服务状态

首先检查 systemd 中与健康检查相关的服务单元：

```bash
# 查看所有 openclaw 相关服务
systemctl --user list-units --type=service | grep openclaw
systemctl --user list-units --type=timer | grep openclaw

# 查看服务详细状态
systemctl --user status openclaw-health-monitor.service
systemctl --user status openclaw-health-monitor.timer

# 查看 timer 触发时间
systemctl --user list-timers | grep openclaw
```

**结果**：发现了健康检查相关的 systemd 服务和 timer，说明健康检查是通过 systemd 管理的定时任务。

### 第二步：查看服务日志

检查健康检查服务的日志，看看为什么进程会不断重启：

```bash
# 查看最近的服务日志
journalctl --user -u openclaw-health-monitor.service -n 50 --no-pager

# 查看特定时间段的日志
journalctl --user -u openclaw-health-monitor.service --since "1 hour ago" --no-pager

# 搜索错误关键词
journalctl --user -u openclaw-health-monitor.service --no-pager | grep -iE "error|fail|exit|kill"
```

**发现**：日志中出现了 "Process exited" 或 "Main process exited" 的字样，说明进程正常完成后退出了，而不是因为崩溃退出。

这就很关键了——**进程不是崩溃了，而是正常退出了**。

### 第三步：分析 systemd 服务配置

查看 systemd 服务单元文件的配置：

```bash
# 查看服务配置
cat ~/.config/systemd/user/openclaw-health-monitor.service

# 查看 timer 配置
cat ~/.config/systemd/user/openclaw-health-monitor.timer
```

典型的 systemd 服务配置可能是这样的：

```ini
[Unit]
Description=OpenClaw Health Monitor
After=openclaw-gateway.service

[Service]
Type=oneshot
ExecStart=/usr/local/bin/openclaw-health-check.sh
WorkingDirectory=/root
Environment=HOME=/root

[Install]
WantedBy=openclaw-gateway.service
```

发现了问题！**`Type=oneshot`** 意味着服务执行完一次后就退出了，而不是持续运行。

### 第四步：理解 systemd Type 字段

systemd 的 Service Type 有多种模式，理解它们对于排查这类问题至关重要：

| Type | 说明 | 适用场景 |
|------|------|----------|
| simple | 默认类型，ExecStart 启动就算成功 | 持续运行的服务 |
| oneshot | ExecStart 执行完成后才视为成功 | 一次性任务 |
| exec | 与 simple 类似，但 ExecStart 进程作为主进程 | 替代 simple |
| forking | ExecStart 会 fork 一个子进程，主进程退出算完成 | 传统 daemon |
| notify | 服务启动后会发送 sd_notify | 需要等待通知 |
| dbus | 需要获取 D-Bus 总线名称 | D-Bus 服务 |

**根因定位**：`Type=oneshot` 是为"一次性任务"设计的，比如执行一次备份、清理一次日志等。对于需要持续运行或定时执行的健康检查，应该使用 `Type=simple` 或 `Type=exec`，并配合 `RemainAfterExit=no`（如果需要定时触发）。

但更关键的问题是：**为什么 timer 会重复触发服务？**

### 第五步：分析 timer 配置

查看 timer 的配置：

```ini
[Unit]
Description=OpenClaw Health Monitor Timer
Requires=openclaw-health-monitor.service

[Timer]
OnBootSec=5min
OnUnitActiveSec=10min
Unit=openclaw-health-monitor.service

[Install]
WantedBy=timers.target
```

timer 配置了 `OnUnitActiveSec=10min`，意味着**每 10 分钟触发一次服务**。所以进程不是"崩溃重启"，而是**被 timer 定时触发、执行完成后正常退出**。

### 第六步：判断这是不是问题

这里需要区分两种情况：

**情况 A（正常）**：健康检查服务设计为定时执行，每次检查完就退出，由 timer 再次触发。这其实是正确的设计。

**情况 B（问题）**：健康检查服务应该持续运行，但不知道为什么被 timer 触发后退出了。

查看日志，确认服务执行了什么：

```bash
# 查看服务执行的日志
journalctl --user -u openclaw-health-monitor.service -o verbose --no-pager | tail -50
```

日志显示服务正常执行了健康检查脚本，检查完成后正常退出。这说明**设计本身就是这样的**——定时检查，执行完就退出。

### 第七步：进一步分析——为什么 VM153 间隔是 15 分钟？

VM152 间隔是 10 分钟，VM153 间隔是 15 分钟。如果问题根因是 timer 配置不同，那两台机器的配置可能不一致。

检查 VM153 的 timer 配置：

```bash
ssh root@VM153 "cat ~/.config/systemd/user/openclaw-health-monitor.timer"
```

果然，VM153 的 `OnUnitActiveSec=15min`，而不是 10 分钟。

### 最终结论

经过完整排查，问题的"根因"其实是：**timer 正在正常工作**。

进程之所以"循环重启"，不是因为故障，而是因为 timer 在按配置的时间间隔定时触发服务。这是 systemd timer 的正常行为。

**问题在于**：我们最初以为健康检查是一个"持续运行的服务"，但实际上它是一个"定时执行的任务"。这种设计本身并没有问题，只是与我们的预期不符。

## 解决方案

### 方案一：确认设计意图

首先需要确认：健康检查进程应该持续运行，还是定时执行？

**如果设计意图是定时执行**（每次检查完就退出）：
- 当前配置是正确的
- timer 正常工作
- 只需要确保检查脚本本身没有问题

**如果设计意图是持续运行**（进程应该一直跑）：
- 需要修改 systemd 服务配置
- 不应该使用 timer + oneshot 的组合
- 应该使用 Type=simple/exec 并移除 timer

### 方案二：验证检查脚本是否正常工作

无论哪种设计意图，都需要验证健康检查脚本本身是否正常工作：

```bash
# 手动执行健康检查脚本
/usr/local/bin/openclaw-health-check.sh

# 查看脚本内容
cat /usr/local/bin/openclaw-health-check.sh

# 检查脚本的退出码
echo $?
```

### 方案三：修改 systemd 配置（如果需要持续运行）

如果确认需要健康检查进程持续运行，修改配置如下：

**修改服务文件**：

```ini
[Unit]
Description=OpenClaw Health Monitor
After=openclaw-gateway.service

[Service]
Type=exec
ExecStart=/usr/local/bin/openclaw-health-check.sh
WorkingDirectory=/root
Restart=always
RestartSec=5

[Install]
WantedBy=openclaw-gateway.service
```

关键配置说明：
- `Type=exec`：替代 simple，作为主进程运行
- `Restart=always`：进程退出后自动重启
- `RestartSec=5`：退出后 5 秒再启动

**禁用并移除 timer**：

```bash
# 停止 timer
systemctl --user stop openclaw-health-monitor.timer

# 禁用 timer
systemctl --user disable openclaw-health-monitor.timer

# 启用服务（开机自启）
systemctl --user enable openclaw-health-monitor.service

# 立即启动服务
systemctl --user start openclaw-health-monitor.service
```

### 方案四：如果定时执行是正确的设计

如果定时执行本就是设计意图，那只需要：

1. **确认 timer 正常工作**：

```bash
# 查看 timer 下次触发时间
systemctl --user list-timers | grep openclaw

# 查看 timer 触发历史
journalctl --user -u openclaw-health-monitor.timer --no-pager | tail -20
```

2. **确认检查脚本没有问题**：

```bash
# 手动执行并查看输出
/usr/local/bin/openclaw-health-check.sh --verbose
```

3. **调整触发间隔**（如果需要）：

```bash
# 修改 timer 配置
sed -i 's/OnUnitActiveSec=10min/OnUnitActiveSec=5min/' ~/.config/systemd/user/openclaw-health-monitor.timer

# 重新加载配置
systemctl --user daemon-reload

# 重启 timer
systemctl --user restart openclaw-health-monitor.timer
```

## 一键排查脚本

```bash
#!/bin/bash
# 健康检查进程循环重启排查脚本
# 保存到 /opt/scripts/health-monitor-debug.sh

echo "========== 健康检查进程排查 =========="
echo "时间：$(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# 1. 检查 systemd 服务状态
echo "[1/6] systemd 服务状态："
systemctl --user list-units --type=service,timer --all | grep openclaw-health || echo "  未找到相关服务"
echo ""

# 2. 查看最近服务日志
echo "[2/6] 最近服务日志（最后20行）："
journalctl --user -u openclaw-health-monitor.service -n 20 --no-pager --quiet 2>/dev/null || echo "  无法获取日志"
echo ""

# 3. 查看 timer 配置
echo "[3/6] timer 配置："
if [ -f ~/.config/systemd/user/openclaw-health-monitor.timer ]; then
    cat ~/.config/systemd/user/openclaw-health-monitor.timer | grep -E "^On|Unit="
else
    echo "  timer 配置文件不存在"
fi
echo ""

# 4. 查看服务配置
echo "[4/6] 服务配置："
if [ -f ~/.config/systemd/user/openclaw-health-monitor.service ]; then
    cat ~/.config/systemd/user/openclaw-health-monitor.service | grep -E "^Type=|^ExecStart|^Restart="
else
    echo "  service 配置文件不存在"
fi
echo ""

# 5. 手动执行检查脚本
echo "[5/6] 手动执行检查脚本："
if [ -x /usr/local/bin/openclaw-health-check.sh ]; then
    /usr/local/bin/openclaw-health-check.sh 2>&1 | head -10
    echo "  退出码: $?"
else
    echo "  脚本不存在或无执行权限"
fi
echo ""

# 6. 检查进程运行状态
echo "[6/6] 进程运行状态："
ps aux | grep -E "[o]penclaw-health|[h]ealth-monitor" | grep -v grep || echo "  无运行中的健康检查进程"
echo ""

echo "========== 排查完成 =========="
echo ""
echo "判断依据："
echo "- 如果 '最近服务日志' 显示 'Main process exited'，说明进程正常退出"
echo "- 如果 'Type=oneshot'，说明服务设计为一次性执行"
echo "- 如果 'OnUnitActiveSec=10min'，说明每10分钟触发一次"
echo "- 以上都是正常行为，不是故障"
echo ""
echo "如果需要进程持续运行，参考以下命令："
echo "  1. 修改 Type=exec 并添加 Restart=always"
echo "  2. systemctl --user disable openclaw-health-monitor.timer"
echo "  3. systemctl --user enable openclaw-health-monitor.service"
echo "  4. systemctl --user start openclaw-health-monitor.service"
```

## 常见问题解答

**Q1：进程不断重启但服务还在，这是故障吗？**

A：不一定。如果是 timer + oneshot 的组合，进程按配置间隔被触发、执行完成后正常退出，这是正常设计。关键是确认这是否是预期的设计意图。如果本应持续运行，那才需要修复。

**Q2：Type=oneshot 和 Type=simple 有什么区别？**

A：
- `oneshot`：服务执行一次就完成，视为"成功"，适用于一次性任务
- `simple`：服务持续运行，主进程退出则服务停止，适用于守护进程

oneshot 服务配合 timer 可以实现"定时任务"；simple 服务单独使用则是"持续运行服务"。

**Q3：timer 触发间隔是怎么配置的？**

A：主要通过以下字段配置：
- `OnBootSec=5min`：系统启动 5 分钟后第一次触发
- `OnUnitActiveSec=10min`：距离上次触发 10 分钟后再次触发
- `OnCalendar=*:0/10`：每 10 分钟触发（另一种写法）

**Q4：如何判断是 timer 触发还是进程自己重启？**

A：查看日志中的时间戳。如果每次退出的时间间隔正好是 timer 配置的间隔，那就是 timer 触发的。如果间隔不规律，可能是进程自己崩溃后被 Restart 策略重启。

**Q5：如何临时禁用 timer 让服务只运行一次？**

```bash
# 停止 timer
systemctl --user stop openclaw-health-monitor.timer

# 临时启动服务（不会自动重启）
systemctl --user start openclaw-health-monitor.service

# 恢复 timer
systemctl --user start openclaw-health-monitor.timer
```

**Q6：进程退出了但 timer 没触发下次执行怎么办？**

A：检查 timer 是否正常运行：
```bash
# 查看 timer 状态
systemctl --user status openclaw-health-monitor.timer

# 查看 timer 下次触发时间
systemctl --user list-timers | grep openclaw

# 如果 timer 有问题，重启 timer
systemctl --user restart openclaw-health-monitor.timer
```

## 经验总结

这次排查经历让我总结出以下几点经验：

**第一，理解 systemd 的设计理念很重要。**

systemd 的 service 和 timer 是两个独立的单元，通过 `Unit=service_name.service` 关联。timer 负责"何时触发"，service 负责"触发后执行什么"。理解这一点，很多看似奇怪的行为都能得到合理解释。

**第二，"进程不断重启"不一定是故障。**

在 systemd 的设计里，timer 触发 service、service 完成后退出、timer 再触发——这是一个正常的循环。如果这个循环是你预期的设计，那它就不是问题。

**第三，日志是排查的第一手资料。**

`journalctl` 可以查看 systemd 服务的详细日志，包括进程退出原因、执行时间等。通过日志可以快速判断是"正常退出"还是"异常崩溃"。

**第四，确认设计意图是解决问题的前提。**

在动手修复之前，先确认一下：这个行为是预期的吗？如果是预期的设计，那不需要修复，只需要解释给相关人员听。如果不是预期的设计，再动手修改。

**第五，修改配置后要验证效果。**

修改 systemd 配置后，记得：
1. `systemctl --user daemon-reload` 重新加载配置
2. `systemctl --user restart xxx` 重启服务
3. 观察日志确认行为符合预期

## 延伸阅读

- [systemd.service 文档](https://www.freedesktop.org/software/systemd/man/systemd.service.html)
- [systemd.timer 文档](https://www.freedesktop.org/software/systemd/man/systemd.timer.html)
- [systemd.unit 文档](https://www.freedesktop.org/software/systemd/man/systemd.unit.html)
- [Linux 定时任务：systemd timer vs cron](https://opensource.com/article/21/7/systemd-timers)

## 结语

这次排查的核心教训是：**在动手修 bug 之前，先确认这到底是不是 bug**。

健康检查进程"不断重启"的现象看起来确实有点吓人，但当我们理解了 systemd 的设计理念后，才发现这其实是正常行为。问题的"根因"不是故障，而是我们最初对设计意图的理解有偏差。

所以啊，运维工作不仅仅是"处理问题"，更重要的是"理解系统"。只有真正理解了系统的设计逻辑，才能判断什么是问题，什么是正常。

希望这篇文章能帮到你。如果有问题，欢迎在评论区讨论。

---

*作者：小六，一个在上海努力搬砖的程序员*
