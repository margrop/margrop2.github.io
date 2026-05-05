---
title: OpenClaw 多智能体协作方案完全指南：五种架构详解
categories:
  - ai_tech
tags:
  - OpenClaw
  - Multi-Agent
  - ACP
  - 架构
cover: 'https://picsum.photos/seed/tech0330/1280/720'
date: 2026-03-30 21:00:00
---

# OpenClaw 多智能体协作方案完全指南：五种架构详解

今天深入研究了 OpenClaw 的多智能体协作体系，发现它的设计比想象中完善得多。本文从实战角度详细介绍五种协作方案，帮助你根据场景选择最适合的架构。

> 本文内容基于 OpenClaw v2026.3.x 官方文档整理，附完整配置示例。

## 一、多智能体路由（Multi-Agent Routing）

**适用场景**：同一 Gateway 下多个隔离智能体，每个服务不同用户或不同渠道。

**核心概念**：
- 每个 `agentId` 有独立的 workspace、auth、session store
- 通过 `bindings` 将不同渠道/账号路由到不同智能体
- 首次匹配生效，支持精确到 peer 级别的路由

**最小配置示例**：

```json5
{
  agents: {
    list: [
      { id: "main", workspace: "~/.openclaw/workspace-main" },
      { id: "ops", workspace: "~/.openclaw/workspace-ops" },
      { id: "dev", workspace: "~/.openclaw/workspace-dev" }
    ]
  },
  bindings: [
    { agentId: "ops", match: { channel: "telegram", accountId: "ops-bot" } },
    { agentId: "dev", match: { channel: "discord", guildId: "123456789" } },
    // 默认路由到 main
    { agentId: "main", match: { channel: "telegram", accountId: "default" } }
  ]
}
```

**路由优先级**（最具体优先）：
1. `peer` 匹配（精确 DM/群组/频道 ID）
2. `parentPeer` 匹配（线程继承）
3. `guildId + roles`（Discord 角色路由）
4. `accountId` 匹配
5. 通道级别默认

---

## 二、子智能体树型编排（Subagent Orchestration）

**适用场景**：复杂任务分解为多个并行子任务，结果汇总。

**关键配置**：

```json5
{
  agents: {
    defaults: {
      subagents: {
        maxSpawnDepth: 2,        // 允许两层嵌套（编排者+执行者）
        maxChildrenPerAgent: 5,   // 每个节点最多5个子节点
        maxConcurrent: 8,        // 全局并发上限
        runTimeoutSeconds: 900    // 默认超时15分钟
      }
    }
  }
}
```

**深度与角色**：

| 深度 | Session Key 格式 | 角色 | 可派生子任务 |
|------|-----------------|------|------------|
| 0 | `agent:<id>:main` | 主智能体 | ✅ 始终可以 |
| 1 | `agent:<id>:subagent:<uuid>` | 编排者/叶子 | 仅 maxSpawnDepth≥2 |
| 2 | `agent:<id>:subagent:<uuid>:subagent:<uuid>` | 执行者 | ❌ 永远不可以 |

**工具权限**：
- 叶子节点：默认无 session 工具
- 编排者（depth=1 when maxSpawnDepth≥2）：额外获得 `sessions_spawn`、`subagents`、`sessions_list`、`sessions_history`

**结果汇报链**：Depth-2 → 汇报给父编排者 → 汇总后 → 汇报给主智能体

---

## 三、ACP 对等会话（Agent Client Protocol）

**适用场景**：连接外部编码引擎（Codex、Claude Code、Cursor、Gemini CLI），实现持久化编码会话。

**核心配置**：

```json5
{
  acp: {
    enabled: true,
    backend: "acpx",
    allowedAgents: ["codex", "claude", "cursor", "openclaw"],
    maxConcurrentSessions: 8,
    runtime: { ttlMinutes: 120 }
  }
}
```

**会话类型**：

| 类型 | 命令 | 特点 |
|------|------|------|
| 持久会话 | `/acp spawn codex --mode persistent --thread auto` | 绑定线程，持续响应 |
| 单次会话 | `/acp spawn codex --mode oneshot` | 一次任务，自动关闭 |
| 绑定当前对话 | `/acp spawn codex --bind here` | 不创建新线程，绑定当前 chat |

**权限配置**：

```bash
# 无 TTY 交互时的权限策略
openclaw config set plugins.entries.acpx.config.permissionMode approve-all
openclaw config set plugins.entries.acpx.config.nonInteractivePermissions fail
```

⚠️ 默认 `permissionMode=approve-reads` + `nonInteractivePermissions=fail`，写操作会直接崩溃。

---

## 四、代理架构（Delegate Architecture）

**适用场景**：AI 具有独立组织身份，代表组织行动（发邮件、建日程），而非代表某个人。

**能力层级**：

| 层级 | 能力 | 权限要求 |
|------|------|---------|
| Tier 1 | 只读+草稿 | 只读权限 |
| Tier 2 | 代发消息/建日程 | Send-on-Behalf 权限 |
| Tier 3 | 自主定时执行 | Tier 2 + Cron + Standing Orders |

**安全加固必须项**：
1. 工具限制：`tools: { allow: ["read","exec","message","cron"], deny: ["write","browser","canvas"] }`
2. 沙箱隔离：`sandbox: { mode: "all", scope: "agent" }`
3. 硬阻断规则（写入 SOUL.md）：不修改身份提供商设置、不导出联系人等

---

## 五、agentToAgent 对等通信

**适用场景**：同一 Gateway 下的多个 agent 直接互相发送消息。

```json5
{
  tools: {
    agentToAgent: {
      enabled: true,
      allow: ["main", "p1", "p2", "p3", "p14"]
    }
  }
}
```

⚠️ **默认关闭**。启用前务必确认 allowlist，谨慎开放。

---

## 实战建议：如何选择

```
任务复杂度
    ↑
    │                    ┌─────────────────┐
    │   简单              │  多智能体路由    │  场景：多用户/多渠道隔离
    │                    └─────────────────┘
    │
    │                    ┌─────────────────┐
    │   中等              │  子智能体树型编排 │  场景：任务分解+并行执行
    │                    └─────────────────┘
    │
    │                    ┌─────────────────┐
    │   复杂              │  ACP + 子智能体 │  场景：编码任务+外部引擎
    │                    └─────────────────┘
    │
    │                    ┌─────────────────┐
    │   组织级             │  代理架构        │  场景：AI有独立组织身份
    │                    └─────────────────┘
    └──────────────────────────────────────────→
                                            协作紧密度
```

---

## 常见问题排查

| 问题 | 原因 | 解决 |
|------|------|------|
| ACP runtime not configured | acpx 插件未安装 | `openclaw plugins install acpx` |
| ACP disabled by policy | `acp.enabled=false` | 设置 `acp.enabled=true` |
| Subagent 超时 | 默认无超时但耗尽 token | 设置 `runTimeoutSeconds` |
| 消息路由到错误 agent | bindings 顺序问题 | 最具体规则放前面 |
| agentToAgent 不可用 | 默认关闭 | 启用 `tools.agentToAgent.enabled` |

---

## 总结

OpenClaw 的多智能体协作体系相当完整，从简单的多租户隔离到复杂的树型编排，再到 ACP 外部引擎集成，都有对应的官方支持。选择哪种方案，取决于你的任务复杂度、协作紧密度和安全性要求。

下一篇我会详细介绍如何在自己的环境中落地这套体系。

---

*本文由 AI 辅助整理，参考 OpenClaw 官方文档 v2026.3.x*
