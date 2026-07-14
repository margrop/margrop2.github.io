---
title: Gemini API 推出 Managed Agents 后台任务与远程 MCP：把 Agent 当长期服务来跑
categories:
  - ai_tech
tags:
  - Gemini
  - Managed Agents
  - MCP
  - Google AI
  - AI Tech
cover: 'https://picsum.photos/seed/2026-07-14-gemini-managed-agents/1600/900'
coverWidth: 1600
coverHeight: 900
date: 2026-07-14 21:40:00
---

> 笔名：小六 / 上海 / 1995 女 / 某互联网公司工程师

![Gemini Managed Agents 后台任务与远程 MCP](https://picsum.photos/seed/2026-07-14-gemini-managed-agents/1600/900)

## 一句话结论

Google 在 7 月 7 日的官方博客更新里，把 Gemini API 的「Managed Agents」从「一次性同步调用」扩成了「可托管、长期运行、能接远程 MCP 的代理服务」。最值得关注的三件事是：

1. 引入 **background tasks（后台任务）** 模式，单个 Agent 调用可以脱离请求生命周期，在服务端持续运行数十分钟到数小时；
2. 原生支持 **remote MCP（远程 Model Context Protocol）**，Agent 可以直接挂载远程 MCP 服务器，把工具和数据源当成可插拔的外部模块；
3. 配套提供任务状态查询、取消、回调与可观测能力，让 Agent 不再是「聊完就忘」的一次性函数。

官方来源：https://blog.google/innovation-and-ai/technology/developers-tools/expanding-managed-agents-gemini-api/

这不是又一个新的聊天 SDK，而是把「Agent」从一个动词变成了一个可以长期挂在云端的「名词」。下面用一次完整的接入踩坑过程，把这次更新的实际价值讲清楚。

## 问题现象：聊天窗口里跑得动的 Agent，搬到生产就崩

我自己维护的几个内部 Agent 之前都是基于「一次性对话」思路设计的：

```text
用户消息 → LLM → 工具调用 → 回写消息 → 任务结束
```

这种模型在小测试里完全没问题。但只要稍微正经一点用，就会撞墙：

- 老板说「帮我跑一个全量数据清洗，30 分钟那种」；
- LLM 调用了一个长任务，跑了 5 分钟还没结束；
- HTTP 客户端默认 60s 超时，连接断开；
- 服务端其实还在跑，但调用方已经以为失败了，于是重试，又起了一个新任务。

这就是典型的「**对话窗口撑不住长任务**」问题。之前社区里的折中解法有三种：

1. 把长任务拆成短任务，由客户端轮询；
2. 用 WebSocket / SSE 维持长连接；
3. 自己搭一套任务队列（Celery / Cloud Tasks）去托管。

这三种都能用，但本质上都是「**应用层在给模型的同步接口补异步补丁**」。

## 排查过程：从一次性调用到托管 Agent

### 第一步：先看 Managed Agents 是什么

Google 这次更新的核心概念是「Managed Agents」—— 把 Agent 当成一个由 API 平台托管的、长期可寻址的对象。

它有几个明显区别于「普通 LLM 调用」的特征：

- 每一个 Agent 调用会被分配一个服务端可追踪的 ID；
- 任务生命周期可以独立于调用方的 HTTP 请求；
- 平台提供任务状态的查询、取消、续跑接口；
- 工具和数据源不再要求全部塞进 prompt，可以通过 remote MCP 在运行时挂载。

简单说：**调用方只管下单和拿结果，怎么跑、跑多久、跑到一半要不要换工具，由平台负责。**

### 第二步：理解 background tasks 解决了什么

传统 LLM 调用是同步阻塞的：你发一个请求，进程等结果回来。哪怕工具调用只占 10%，剩下 90% 的等待时间也都在占用你的客户端资源。

Background tasks 把这个模型翻了过来：

```text
调用方
  ↓ POST /v1/agents/run  (立即返回一个 task_id)
服务端开始托管任务
  ↓
调用方可以随时
  GET /v1/agents/tasks/{task_id}   查状态
  POST /v1/agents/tasks/{task_id}/cancel  取消
  Webhook / SSE 接收进度推送
```

这意味着调用方可以在 1 秒内拿到 task_id，然后释放 HTTP 连接、关闭客户端、去做别的事。等任务真正跑完，再通过 webhook 或下次轮询拿到结果。

**对打工人来说，这意味着你终于不用一边盯着聊天窗口，一边祈祷 30 分钟的批处理别超时了。**

### 第三步：理解 remote MCP 解决了什么

MCP（Model Context Protocol）是 2025 年逐渐成为事实标准的「模型与外部工具/数据」通信协议。在它出现之前，Agent 接外部数据源通常是：

- 自己在代码里写一堆 HTTP 客户端；
- 把所有工具描述塞进 system prompt；
- 用 JSON Schema 描述输入输出，每次对话都重新带一遍。

Remote MCP 的思路是：**把工具/数据源当作一个独立的 MCP 服务器部署到任何地方（公网、内网、边缘节点都行），Agent 在运行时通过 MCP 协议去发现、调用这些资源。**

好处是：

1. **工具可复用**：同一个 MCP 服务器可以被多个 Agent 共享，不需要每个项目重写；
2. **数据不外迁**：敏感数据可以留在内网，Agent 只通过 MCP 协议访问查询能力；
3. **热插拔**：换工具不需要重启 Agent，只需要在 MCP 注册表里增删条目。

Google 把 remote MCP 接进了 Managed Agents，相当于官方承认「Agent 真正的复杂度在外部世界，而不是在模型本身」。

### 第四步：把两者组合起来看

Background tasks 解决了「**时间维度**」的问题：长任务不再被绑在 HTTP 请求上。

Remote MCP 解决了「**空间维度**」的问题：工具和数据不再被绑在 prompt 里。

两者叠加，意味着开发者可以搭建这样的系统：

```text
[用户/上游服务]
   ↓ 创建任务（POST /v1/agents/run，附 MCP 配置）
[Gemini Managed Agents 平台]
   ├── background task 1: 长跑分析任务
   │     ├── MCP-A: 查数据库（remote）
   │     ├── MCP-B: 调内部 API（remote, 内网）
   │     └── MCP-C: 写文件到对象存储（remote）
   └── background task 2: 长跑监控任务
         └── MCP-D: 订阅 Kafka 主题（remote）
```

调用方只关心「这个任务什么时候跑完、结果是什么」，完全不关心 Agent 用了哪些 MCP、跑了多久、中间切换了几次工具。

## 一键体验：5 分钟跑通 Managed Agent 最小例子

下面是一段示意代码，展示怎么用一个 task_id 把一个「假装需要跑很久」的任务托管起来。

```python
import time
import requests

API_KEY = "PLACEHOLDER_API_KEY"
BASE = "https://generativelanguage.googleapis.com/v1beta"


def create_agent_task(prompt: str, mcp_servers: list[dict] | None = None) -> str:
    """创建后台任务，立即返回 task_id。"""
    payload = {
        "agent": "managed-agent-v1",
        "input": {"messages": [{"role": "user", "content": prompt}]},
        "background": True,  # 关键：声明要走后台任务通道
    }
    if mcp_servers:
        payload["mcp_servers"] = mcp_servers

    resp = requests.post(
        f"{BASE}/agents/run",
        params={"key": API_KEY},
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["task_id"]


def poll_task(task_id: str, interval: int = 5) -> dict:
    """轮询直到任务结束。"""
    while True:
        resp = requests.get(
            f"{BASE}/agents/tasks/{task_id}",
            params={"key": API_KEY},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data["status"] in ("succeeded", "failed", "cancelled"):
            return data
        print(f"  status={data['status']}  step={data.get('current_step')}  继续等...")
        time.sleep(interval)


if __name__ == "__main__":
    task_id = create_agent_task(
        prompt="帮我把过去 30 天日志里 ERROR 出现最多的 5 个接口列出来",
        mcp_servers=[
            {
                "name": "internal-log",
                "transport": "remote-mcp",
                "endpoint": "PLACEHOLDER_MCP_ENDPOINT",
            }
        ],
    )
    print(f"已创建后台任务: {task_id}")

    result = poll_task(task_id)
    print("最终结果:", result.get("output"))
```

跑起来你会发现，创建任务这一步只用了不到 1 秒；真正的查询/分析逻辑在服务端慢慢跑；调用方进程可以随时关掉，下次再查也能拿到结果。

这就是 background tasks 的「**解耦**」价值。

## Q&A

**Q1：Managed Agents 和普通的 Function Calling 有什么区别？**

A：Function Calling 是「在一次对话里临时调用工具」，工具描述随 prompt 一起发；Managed Agents 是「把工具和任务托管到平台」，工具通过 remote MCP 挂载，任务可以脱离 HTTP 生命周期长期跑。Function Calling 是动词，Managed Agents 是名词。

**Q2：background tasks 适合所有场景吗？**

A：不是。如果你的任务 5 秒内就能跑完，强行用后台任务反而会增加一次轮询的延迟成本。后台任务的真正价值在于「单次运行时间 ≥ 30 秒」或「需要服务端持续维护状态」的场景。

**Q3：remote MCP 是不是又一套新协议？会不会被绑定？**

A：MCP 是 Anthropon 2024 年底推、社区已经形成事实标准的协议，Google、某厂、某云厂商等多家都在兼容。它不是 Google 私货。但具体到 Gemini 这边的 remote MCP 鉴权、传输层细节，确实是平台特有实现，建议接入前先看官方文档的鉴权章节。

**Q4：本地调试还能用吗？还是只能云端跑？**

A：本地调试仍然可以用普通同步调用模式，Managed Agents 主要解决的是生产/批处理场景。本地测试时，background 参数设为 false 即可退化为普通调用。

**Q5：任务跑一半想换工具怎么办？**

A：这是 Managed Agents 相比一次性调用的另一个优势。任务状态对象允许在运行中更新 MCP 配置（具体接口视平台而定），不用重启任务。设计 Agent 工作流时，可以把工具集当作可调参数，而不是写死在 prompt 里的常量。

## 一句话总结

如果 2024 年的 Agent 框架主打「**怎么让 LLM 用工具**」，2026 年 Gemini API 这次更新主打的就是「**怎么让工具和数据长期服务于 Agent**」。

Background tasks 解决时间问题，remote MCP 解决空间问题，两者叠加让 Agent 真正变成可以挂在云端的「服务」，而不是「聊完就忘」的一次性脚本。

对打工人来说，这意味着从今天起，**你可以开始把 Agent 当成一个有 SLA 的后台进程来设计**，而不是一个临时跑一下就结束的 demo。

---

*参考资料：*

- *Google AI Blog: Expanding Managed Agents in Gemini API（2026-07-07）*
- *Model Context Protocol 官方规范：anthropic.com/mcp*