---
title: OpenClaw Subagent 通信机制详解：工作原理解析与 Session 管理最佳实践
categories:
  - ai_tech
tags:
  - 技术
  - OpenClaw
  - Subagent
  - Session
  - 通信机制
  - 运维
cover: 'https://picsum.photos/seed/tech0501/1280/720'
coverWidth: 1280
coverHeight: 720
date: 2026-04-05 21:30:00
---

# OpenClaw Subagent 通信机制详解：工作原理解析与 Session 管理最佳实践

## 前言

在 OpenClaw 的日常使用中，你是否遇到过这样的情况：明明 Subagent 已经启动，但消息发过去没有响应？或者 Subagent 的响应非常慢，不知道卡在了哪里？

今天这篇文章将从工作原理出发，深入解析 OpenClaw Subagent 的通信机制，介绍 Session 的生命周期管理，并提供常见问题的排查思路和解决方案。

## 什么是 Subagent

在 OpenClaw 的架构中，"Subagent"是一种**在独立 Session 中运行的子任务执行单元**。与主 Session（Main Session）不同，Subagent 运行在独立的上下文中，拥有自己的会话历史、工具调用权限和执行环境。

Subagent 的典型使用场景包括：

- **后台长时间运行的任务**：不需要阻塞主会话，让 Subagent 在后台执行
- **多任务并行处理**：同时运行多个 Subagent，每个处理一个独立任务
- **隔离性任务执行**：某些操作需要独立的执行环境，用 Subagent 可以避免对主会话的干扰
- **代码编写与评审**：Spawn 一个独立的 Coding Agent 处理 PR Review 或重构任务

Subagent 通过 `sessions_spawn` 工具启动，其生命周期由主 Session 管理，但实际执行是异步的。

## Subagent 的通信架构

### 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                    Main Session                         │
│  (Agent - 管理控制平面，发起 spawn 命令)                 │
└────────────────────────┬────────────────────────────────┘
                         │ sessions_spawn
                         ▼
┌─────────────────────────────────────────────────────────┐
│              OpenClaw Gateway                            │
│  - 负责 Subagent 的生命周期管理                          │
│  - 维护 Session 映射表                                     │
│  - 路由消息到对应的 Subagent Session                     │
└────────┬────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│           Subagent Session (isolated)                   │
│  - 独立的执行上下文                                       │
│  - 独立的消息历史                                         │
│  - 通过 sessions_send 与主 Session 通信                   │
└─────────────────────────────────────────────────────────┘
```

### 消息流向

Subagent 与主 Session 之间的消息流向如下：

1. **主 Session 发起 Spawn**：调用 `sessions_spawn`，指定 task（任务描述）、runtime（运行时类型）、mode（执行模式）
2. **Gateway 创建 Subagent Session**：Gateway 根据参数创建新的 Session，分配唯一标识 sessionKey
3. **Subagent 执行任务**：Subagent 在独立上下文中开始执行，可以通过工具调用完成各种操作
4. **Subagent 返回结果**：任务完成后，通过 `sessions_yield` 将结果推送回主 Session
5. **主 Session 接收结果**：主 Session 的下一次响应中会包含 Subagent 的返回内容

整个过程中，消息的传递是通过 Gateway 内部的消息队列完成的，不需要额外的网络通信（如果是本地节点）。

## Session 的生命周期

### Session 的状态

每个 Session（包括 Subagent Session）在其生命周期内会经历以下几种状态：

| 状态 | 含义 | 说明 |
|------|------|------|
| `pending` | 等待启动 | Session 已创建，等待第一次消息投递 |
| `active` | 运行中 | Subagent 正在执行任务 |
| `waiting` | 等待输入 | Subagent 在等待主 Session 的进一步指令 |
| `completed` | 已完成 | 任务正常结束 |
| `error` | 错误 | 执行过程中发生错误 |
| `killed` | 已终止 | 被主 Session 主动终止 |

### Session 的存储

Subagent Session 的消息历史和状态信息存储在 Gateway 的工作目录中：

```
~/.openclaw/agents/<agent-id>/sessions/<session-key>.jsonl
```

- **messages.jsonl**：Session 的完整消息历史（JSON Lines 格式）
- **状态信息**：存储在 sessions.json 索引文件中

当 Subagent 执行任务时，每一条消息都会被追加到对应的 .jsonl 文件中。这意味着：
- Session 历史是持久化的，重启 Gateway 不会丢失
- 但如果手动删除 .jsonl 文件，对应的 Session 历史就会丢失

### Session 的清理

Session 不会自动清理。随着使用时间增长，未终结的 Session 会积累，占用磁盘空间。可以通过以下方式管理：

```bash
# 查看所有 Session
openclaw sessions list

# 查看特定 Session 的消息历史
openclaw sessions history <session-key>

# 终止一个 Session
openclaw sessions kill <session-key>

# 清理孤立的 Session 文件（需要手动确认）
ls ~/.openclaw/agents/main/sessions/*.jsonl | xargs -I {} echo {}
```

## Subagent 的启动参数详解

`sessions_spawn` 是启动 Subagent 的核心工具，其参数含义如下：

### runtime

指定 Subagent 的运行时类型：

| 值 | 含义 |
|----|------|
| `subagent` | OpenClaw 内置 Subagent 运行时 |
| `acp` | ACP 编码任务运行时（需要 agentId） |

```json
{
  "runtime": "subagent",
  "task": "帮我写一个 Python 脚本处理 CSV 文件",
  "mode": "run"
}
```

### mode

指定 Subagent 的执行模式：

| 值 | 含义 |
|----|------|
| `run` | 单次执行模式，任务完成后自动退出 |
| `session` | 会话模式，Subagent 会持续运行直到被终止 |

```json
{
  "runtime": "subagent",
  "mode": "session",
  "task": "持续监控某个目录的变化并报告"
}
```

### thread

仅在 `runtime="acp"` 时有效。设置为 `true` 时，Subagent 在 Discord 等支持线程的平台上会创建独立线程。

### cleanup

指定 Subagent 结束后是否清理 Session 历史：

| 值 | 含义 |
|----|------|
| `delete` | 任务完成后删除 Session 文件（默认） |
| `keep` | 保留 Session 文件以供后续查询 |

```json
{
  "runtime": "subagent",
  "task": "生成一份代码审查报告",
  "cleanup": "keep"
}
```

## Subagent 与主 Session 的通信机制

### sessions_send：向 Subagent 发送消息

启动 Subagent 之后，主 Session 可以随时通过 `sessions_send` 向其发送消息：

```json
{
  "sessionKey": "<subagent-session-key>",
  "message": "任务有变化，请停止当前操作并重新评估"
}
```

Subagent 收到消息后，会在自己的上下文中处理这条消息，并返回响应。

### sessions_yield：Subagent 返回结果

Subagent 完成主要工作后，需要调用 `sessions_yield` 将结果返回给主 Session：

```json
{
  "message": "任务已完成，结果如下：\n- 处理文件数：42\n- 成功率：97.6%"
}
```

`sessions_yield` 会将消息发送到主 Session，主 Session 在下一轮响应中接收这个结果。

### sessions_list：查看 Subagent 状态

主 Session 可以随时查看当前所有 Subagent 的状态：

```json
{
  "kinds": ["subagent"],
  "limit": 10,
  "activeMinutes": 60
}
```

这个查询返回过去 60 分钟内活跃的所有 Subagent Session 及其最新消息。

## 常见问题与解决方案

### 问题一：Subagent 启动后没有任何响应

**现象**：调用 `sessions_spawn` 后，Subagent Session 被创建，但没有执行任何操作，也没有返回结果。

**排查步骤**：

第一步：检查 Subagent Session 是否被正确创建
```bash
openclaw sessions list
```
查找刚创建的 Session，确认其状态不是 `pending`（如果是，说明消息没有被投递）。

第二步：检查 Gateway 日志
```bash
tail -f /tmp/openclaw-gateway.log | grep -i "subagent\|spawn\|session"
```
查找与 Subagent 相关的日志条目，特别关注是否有错误信息。

第三步：检查 Subagent 的消息历史
```bash
openclaw sessions history <session-key>
```
看看是否有任何消息被记录，如果完全是空的，说明 Subagent 根本没有收到任务。

**常见原因**：

1. **Session Key 错误**：发送消息时使用了错误的 sessionKey，导致消息无法投递
2. **Gateway 负载过高**：Gateway 在高负载情况下可能延迟处理 Subagent 的初始化
3. **任务描述不明确**：task 参数过于模糊，导致 Subagent 无法开始执行

**解决方案**：

1. 确认使用的 sessionKey 正确（`sessions_spawn` 的返回值中会包含 sessionKey）
2. 重启 Gateway 释放负载
3. 在 task 参数中提供更清晰的任务描述

### 问题二：Subagent 返回结果不完整

**现象**：Subagent 明明执行了很长的任务，但返回的结果只有最后几行。

**原因**：Subagent 的返回是通过 `sessions_yield` 实现的，如果任务输出很长，可能超出单次消息的大小限制。

**解决方案**：

1. 在 Subagent 内部将长输出写入文件，然后在 `sessions_yield` 中只返回文件路径
2. 将输出切分为多个小块，通过多次 `sessions_send` 分批返回
3. 增大 Gateway 的消息大小限制（如果支持）

### 问题三：Subagent Session 无法终止

**现象**：调用 `sessions_kill` 或者在主 Session 中发送终止信号，Subagent 仍然在运行。

**排查步骤**：

```bash
# 查看 Session 当前状态
openclaw sessions list | grep <session-key>

# 查看 Gateway 进程
ps aux | grep openclaw

# 查看 Subagent 的子进程
ps aux | grep -i "subagent\|child" | grep -v grep
```

**常见原因**：

1. **Subagent 创建了后台进程**：`sessions_spawn` 启动的 Subagent 内部可能通过 `exec` 或 `subprocess` 创建了后台进程，这些进程不受 Session 生命周期管理
2. **Gateway 无法访问 Subagent 的进程树**：某些情况下 Subagent 的进程脱离了 Gateway 的控制范围

**解决方案**：

1. 在 Subagent 的任务描述中明确**不要创建后台进程**，所有操作都应在 Subagent 的主进程中完成
2. 如果 Subagent 创建了后台进程，需要手动通过 `kill` 命令终止相关进程
3. 使用 `exec` 的 `background: true` 参数配合 `process` 工具来管理后台进程，而不是在 Subagent 内部创建

### 问题四：多个 Subagent 之间无法共享状态

**现象**：启动了多个 Subagent 处理不同任务，但它们之间无法共享数据或状态。

**原因**：Subagent 运行在完全隔离的 Session 上下文中，彼此之间不共享内存或文件系统。

**解决方案**：

1. **通过主 Session 中转**：所有需要共享的数据都通过主 Session 汇总和分发
2. **写入共享存储**：如果 Subagent 需要共享文件，可以写入共享存储（如 NAS、云存储），其他 Subagent 从中读取
3. **使用数据库**：通过数据库（如 SQLite、MySQL）作为 Subagent 之间的数据共享媒介

### 问题五：Subagent 日志占用大量磁盘空间

**现象**：随着使用时间增长，Gateway 的磁盘空间不断减少，排查发现是 Session 历史文件占用过大。

**原因**：每个 Subagent Session 的消息历史都会被持久化到 .jsonl 文件中，长时间不清理会积累大量数据。

**解决方案**：

1. **定期清理 Session 文件**：
```bash
# 查找超过 7 天的 Session 文件
find ~/.openclaw/agents -name "*.jsonl" -mtime +7

# 删除超过 7 天的 Session 文件
find ~/.openclaw/agents -name "*.jsonl" -mtime +7 -delete
```

2. **设置自动清理**：在 crontab 中添加定时清理任务：
```bash
# 每天凌晨 3 点清理 7 天前的 Session 文件
0 3 * * * find ~/.openclaw/agents -name "*.jsonl" -mtime +7 -delete
```

3. **设置 Session 保留策略**：在 `sessions_spawn` 时设置 `cleanup: "delete"`，任务完成后自动删除 Session 文件

## Subagent 的最佳实践

### 1. 任务描述要清晰

Subagent 的 task 参数是它唯一的输入来源。模糊的任务描述会导致 Subagent 无法正确执行。推荐的结构：

```
角色：你是一个 [具体角色]
目标：完成 [具体任务]
约束：
- 必须 [约束条件1]
- 禁止 [约束条件2]
- 输出格式：[期望的输出格式]
```

### 2. 设置合理的超时时间

对于可能耗时较长的任务，设置 `timeoutSeconds` 参数：

```json
{
  "runtime": "subagent",
  "task": "完整重构 /path/to/project 目录下的所有 Python 文件",
  "timeoutSeconds": 3600
}
```

超时后主 Session 会收到一个超时错误，可以选择重试或手动介入。

### 3. 使用独立的 Workspace

Subagent 有自己独立的工作目录，但可以通过 `cwd` 参数指定其工作路径：

```json
{
  "runtime": "subagent",
  "task": "在 /tmp/build 目录下编译项目",
  "cwd": "/tmp/build"
}
```

这样可以让 Subagent 的操作更加可控，避免对主 Session 的工作目录造成影响。

### 4. 善用 session 模式做持续性任务

对于需要长时间保持运行、随时等待指令的 Subagent，使用 `mode: "session"` 而不是 `mode: "run"`：

```json
{
  "runtime": "subagent",
  "task": "监控 /var/log 目录，发现新日志立即报告",
  "mode": "session"
}
```

这样 Subagent 会持续运行，直到主 Session 主动终止它。

### 5. Subagent 内部禁止再 Spawn Subagent

这是一个重要的架构约束：**不要在 Subagent 内部再启动另一个 Subagent**。这会导致 Session 层级混乱，难以管理。如果确实需要并行处理多个子任务，应该在主 Session 层面 Spawn 多个 Subagent，然后由主 Session 汇总结果。

## 进阶用法：Subagent 的编排模式

### 模式一：并行执行 + 结果汇总

```json
// 主 Session 中同时 Spawn 三个 Subagent
sessions_spawn("任务1：分析代码质量", runtime="subagent", mode="run")
sessions_spawn("任务2：检查安全漏洞", runtime="subagent", mode="run")
sessions_spawn("任务3：生成测试用例", runtime="subagent", mode="run")

// 等待所有 Subagent 返回结果后，汇总输出
```

适用场景：三个任务相互独立，可以同时执行。

### 模式二：流水线执行

```json
// 第一阶段：数据收集
spawn("收集数据", runtime="subagent", mode="run")

// 在接收到第一阶段结果后，启动第二阶段
// 第二阶段：数据分析
spawn("分析数据", runtime="subagent", mode="run")

// 第三阶段：生成报告
spawn("生成报告", runtime="subagent", mode="run")
```

适用场景：各阶段存在依赖，必须按顺序执行。

### 模式三：Supervisor 模式

```json
// 主 Session 作为 Supervisor，启动多个 Worker Subagent
spawn("Worker-1：持续处理任务A", runtime="subagent", mode="session")
spawn("Worker-2：持续处理任务B", runtime="subagent", mode="session")
spawn("Worker-3：持续处理任务C", runtime="subagent", mode="session")

// 主 Session 负责任务分发和结果收集
while True:
    new_task = get_new_task()
    worker = select_idle_worker()
    sessions_send(worker, new_task)
```

适用场景：有大量短任务需要处理，Worker 持续运行等待任务分发。

## 总结

Subagent 是 OpenClaw 中一个强大的功能，它让任务执行从主 Session 中解耦出来，实现了真正的并行处理和后台运行。但要正确使用它，需要理解几个关键点：

1. **Subagent 是异步的**：Spawn 之后不会阻塞主 Session，主 Session 继续执行，Subagent 在后台运行
2. **Session 是隔离的**：每个 Subagent 有自己独立的上下文，Session 之间不共享内存
3. **通信是双向的**：主 Session 可以通过 `sessions_send` 向 Subagent 发消息，Subagent 通过 `sessions_yield` 向主 Session 返回结果
4. **Session 需要管理**：长期运行会产生大量 Session 文件，需要定期清理

理解这些机制后，Subagent 就能成为日常工作中提升效率的利器——把那些不需要实时监控的后台任务交给 Subagent，主 Session 专注于需要即时交互的工作。

---

*作者：小六，一个在上海努力搬砖的程序员*
