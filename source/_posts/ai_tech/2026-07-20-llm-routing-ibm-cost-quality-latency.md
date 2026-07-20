---
title: Model Routing 看似简单？IBM Research 在 417 个真实任务上，把“按价格选模型”这条路走崩了
categories:
  - ai_tech
tags:
  - Model Routing
  - LLM Router
  - Claude Sonnet
  - GPT-4.1
  - AppWorld
  - Cache Hit Rate
  - Agent 系统
  - IBM Research
  - AI Tech
cover: 'https://picsum.photos/seed/2026-07-20-llm-routing-ibm/1600/900'
coverWidth: 1600
coverHeight: 900
date: 2026-07-20 21:30:00
---

> 笔名：小六 / 上海 / 1995 女 / 某互联网公司工程师

![Model Routing 真实账单告诉你：选模型不是分类问题，是系统优化问题](https://picsum.photos/seed/2026-07-20-llm-routing-ibm/1600/900)

## 一句话结论

IBM Research 在 7 月 15 日的 Hugging Face 官方博客上，发了一篇题为 **"Model Routing Is Simple. Until It Isn't."** 的工程长文。他们在 417 个 AppWorld Test Challenge 任务上做了一次很残酷的对照实验：

> **同款 CodeAct agent、同样的任务集，"便宜的 GPT-4.1"反而比 Claude Sonnet 4.6 贵了将近一倍——GPT-4.1 花了 $155，Sonnet 只花了 $79。**

官方来源：https://huggingface.co/blog/ibm-research/model-routing-is-simple-until-it-isnt

这个反常识的结论来自三个常被"模型路由器"忽略的变量：**缓存命中率、任务真实复杂度、推理端到端时延**。文章把它们拆解后给出了排查思路和替代方案，最后给出一张 cost-accuracy frontier 图，告诉你怎么在企业 agent 系统里选路由策略。

对打工人的价值不在于记住 $79 和 $155 这两个数字，而在于**你的"省钱路由"也许正在偷偷烧钱**。

## 问题现象：路由表写得很美，账单回来时不好看

在 agent 系统里加 Model Router，是过去一年最常见的优化动作。直觉模型是这样：

```text
简单请求  -> 便宜小模型
困难请求  -> 贵但强的大模型
代码任务  -> Claude
多模态任务 -> Gemini
```

一张轻量分类器（heuristic 或小 LLM）就能选模型，配上不同账户、不同区域的 endpoint，再来几个 fallback 规则，部署上就能见到成本下降、性能持平的"漂亮曲线"。大多数团队走到这一步就停下了。

IBM Research 的工程师们也想停。但在 AppWorld Test Challenge 上，CodeAct agent 跑完 417 个真实业务任务后，账单上的两行数字把他们的默认假设砸出一个洞：

```text
Claude Sonnet 4.6 : $79 (0.19 / task)
GPT-4.1          : $155 (0.37 / task)
```

Sonnet 的 **"标价"明显更高**：输入单价、输出单价都比 GPT-4.1 贵；同一个任务的推理 step 数，Sonnet 还要多走大约 3 倍。按任何一张公开定价表推导，GPT-4.1 都应该便宜一大截。**结果是它贵了一倍**。

这就是文章想提醒工程团队的：**router 以为自己在优化成本，其实它一直在优化定价表。**

## 排查一：成本不只是"模型单价"

第一根隐形的成本轴是 cache。Agent 工作流的典型特征是大量上下文复用：

```text
工具调用结果  -> 多 step 复用
system prompt -> 几乎每 step 都重发
上下文前缀  -> 长对话里高度重复
```

当 cache hit 率高的时候，真实输入成本会显著下降。Sonnet 在 cache-read 上的折扣力度比 GPT-4.1 大得多，agent 工作流又恰好是 cache 命中率最高的形态。于是出现了一个"标价贵、账单便宜"的有意思现象。

换个方向也成立：**如果你设计的路由器只把 query 丢给一个没打开 prefix caching 的 endpoint，你看到的每次请求单价，会比生产账单真实数字贵几倍。** 一旦团队开始按"单价×长度"估成本，路由策略就会被这种估算带偏。

IBM Research 的第一条结论因此被写成一句话：

> Actual cost depends on the interaction between the model, the workload, and the serving infrastructure.

翻译成打工人语言：

> 模型不是孤立存在的，它和 workload、基础设施、缓存策略一起组成一个账单。路由器只看定价表，等于只看了账单的第一列。

## 排查二：复杂度不是"任务难度"

第二条常被工程团队高估的轴是"任务难度"。直觉模型是"难的请求送给强模型"，但现实里有两类反例：

第一类：**难度在路由时不可见**。

```text
请求："帮我总结这份合同"
   -> 看起来简单
   -> 实际触发：文档检索 + 合规检查 + 工具调用 + 多轮裁剪

请求："在 200 万条日志里找异常"
   -> 看起来困难
   -> 真实路由：一个小模型加一个聚类函数就能拿下
```

一个请求到底有多复杂，要等执行到一半才知道。路由器想做"难度感知"，就必须为执行后才知道的信号预先买单。

第二类：**难度只是众多变量中的一个**。

生产路由器要同时平衡：

```text
cost        -> 价格、缓存命中率、token 结构
latency     -> 端到端时延、queue、序列化
specialty   -> 多模态、长上下文、代码、推理
reliability -> 限流、可用区、fallback
governance  -> 合规、数据驻留、批准模型清单、隐私
```

**合规是一个常被低估的硬约束**。某条请求本该路由到模型 A，但 A 没在审批清单里，路由器只能把它改成 B，并接受随之而来的质量和成本差异。这条"治理通路"必须在路由设计里就占好位置，不能事后补丁。

所以 IBM Research 给出的第二条结论也很朴素：

> Routers aren't solving one problem. They're constantly juggling cost, quality, latency, compliance, and reliability all at once.

翻译成打工人语言：路由器不是分类器，是调度器。

## 排查三：时延不只是"模型大小"

第三条隐形轴是端到端时延。一般人会把时延和"模型参数量"挂钩，但用户实际感受到的时延，至少被以下几件事叠加：

```text
模型自身推理时间
硬件环境（GPU 类型、batch 大小、队列长度）
缓存命中率
路由开销
路由颗粒度（每 task 路由一次 vs. 每 step 路由一次）
```

其中最后两项是工程师自己引入的：

- **每 task 路由一次**，几乎零开销，但失去了运行期调度的灵活性。
- **每 step 路由一次**，可以动态调整模型，代价是每一次新决策都额外引入时延和运维复杂度。

文章专门点了一个反直觉案例：**理论上更快的模型，端到端实测可能更慢**。如果上游 cache 没命中、endpoint 拥堵、推理服务降级，那张"模型速度排行榜"就完全失真。路由器只看模型速度，等于在错误的坐标轴上优化。

把三条排查放在一起，IBM Research 的核心反驳就成型了：

```text
常见假设                              现实
─────────────────────────────────────────────────────
成本  = 模型单价                       成本 = 单价 × 调用模式 × 缓存命中率
难度  = 在请求阶段可估计                难度 = 执行阶段才逐渐显露
时延  = 模型越小越快                   时延 = 路由开销 + 端到端基础设施状态
```

## 替代方案：把路由器从"分类器"改造成"求解器"

文章没有停留在吐槽。它给出了一个明确的方法论迁移路径：

```text
旧视角：把模型选择当成"分类任务"
  -> 让分类器选最佳模型
  -> 等于在估算定价表

新视角：把模型选择当成"系统优化任务"
  -> 在 cost / quality / latency 之间同时搜索
  -> 算法足够轻，避免变成新的瓶颈
```

在 AppWorld Test Challenge 上，他们用优化式路由器对每个任务都找出 cost-accuracy frontier 的一组 Pareto 点。结果里有两个特别值得放到会议室大屏幕上的数字：

```text
Configuration 1（latency-optimized）
  accuracy : 84%
  cost     : $93
  latency  : 83 s
  对照（单独跑 Opus）：accuracy 几乎持平
  收益     : cost -21%，latency -9%，accuracy 仅掉 4%

Configuration 2（再省一点）
  更激进压成本，仍能保持 accuracy 在可接受范围
```

而那枚"传统的 difficulty-based 路由器"（teal diamond）落在同样 accuracy 区间，但 cost 明显更高——它根本没有去搜索 frontier，**只知道按难度抬模型**。

更值得工程团队注意的是，文章把优化算法本身的成本也摆在桌面：

```text
单任务路由器 overhead: ≈ 6 ms
路由器内存占用       : ≈ 2 KB
```

也就是说，这个"求解器"不会因为自身跑得太重，反而把端到端时延再拖一遍。这一点对生产系统非常关键：**路由器不能成为新的瓶颈**。

## 一键方案：把上面这套思路搬到你的环境

下面给一个脱敏后的最小骨架，用于在自家 agent 系统里把"分类式路由"迁移到"优化式路由"。它不是开箱即用，但把官方文章里的核心步骤压成了三段。

```python
#!/usr/bin/env python3
"""
optimization_based_router.py
按 IBM Research 的 cost-quality-latency frontier 思路实现的最小路由器。
"""

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional
import time


@dataclass
class ModelEndpoint:
    """每个候选模型的真实账单视图（非标价）。"""
    name: str
    input_price: float            # $/1M tokens（no cache）
    output_price: float           # $/1M tokens
    cache_read_price: float       # $/1M tokens
    avg_step_time_s: float        # 预估平均推理时延
    quality_score: float          # 在自家评测集上的 0~1 分数
    governance_ok: bool = True    # 是否在审批清单里


@dataclass
class RouterConstraints:
    """路由器搜索 frontier 时要满足的硬约束。"""
    max_cost_usd: float = 1.0
    max_latency_s: float = 30.0
    min_quality: float = 0.8
    force_governance: bool = True


def effective_cost_per_task(
    ep: ModelEndpoint,
    est_input_tokens: int,
    est_output_tokens: int,
    cache_hit_rate: float,
    avg_steps: int,
) -> float:
    """
    把定价表转成"对当前 workload 的预期单价"。
    注意：cache 命中部分按 cache_read_price 算。
    """
    in_cost  = est_input_tokens  * (
        cache_hit_rate * ep.cache_read_price + (1 - cache_hit_rate) * ep.input_price
    )
    out_cost = est_output_tokens * ep.output_price
    per_step = (in_cost + out_cost) / 1_000_000
    return per_step * avg_steps


def choose_endpoint(
    endpoints: List[ModelEndpoint],
    workload_signal: Dict[str, float],
    constraints: RouterConstraints,
) -> Optional[ModelEndpoint]:
    """在 frontier 上挑一个满足所有硬约束的端点。"""
    candidates = []
    for ep in endpoints:
        if constraints.force_governance and not ep.governance_ok:
            continue
        cost = effective_cost_per_task(
            ep,
            est_input_tokens=int(workload_signal["input_tok"]),
            est_output_tokens=int(workload_signal["output_tok"]),
            cache_hit_rate=float(workload_signal["cache_hit"]),
            avg_steps=int(workload_signal["steps"]),
        )
        latency = ep.avg_step_time_s * float(workload_signal["steps"])
        if cost <= constraints.max_cost_usd \
           and latency <= constraints.max_latency_s \
           and ep.quality_score >= constraints.min_quality:
            candidates.append((cost, latency, ep))

    if not candidates:
        return None
    # 默认按 cost 升序挑；想压 latency / 想抬 quality 自己改排序键。
    candidates.sort(key=lambda x: (x[0], x[1]))
    return candidates[0][2]


def main():
    endpoints = [
        ModelEndpoint(
            name="claude-sonnet-4.6",
            input_price=3.0, output_price=15.0,
            cache_read_price=0.30,
            avg_step_time_s=2.5,
            quality_score=0.86,
        ),
        ModelEndpoint(
            name="gpt-4.1",
            input_price=2.0, output_price=8.0,
            cache_read_price=1.0,    # 这条参数解释了 Sonnet 为何更便宜
            avg_step_time_s=1.4,
            quality_score=0.85,
        ),
    ]

    constraints = RouterConstraints(
        max_cost_usd=0.30,
        max_latency_s=20.0,
        min_quality=0.8,
    )

    workload = {
        "input_tok": 8000,
        "output_tok": 1200,
        "cache_hit": 0.85,   # agent 场景典型高命中率
        "steps": 3,
    }

    t0 = time.time()
    chosen = choose_endpoint(endpoints, workload, constraints)
    dt_ms = (time.time() - t0) * 1000

    print(f"router overhead: {dt_ms:.2f} ms")
    if chosen:
        print(f"picked: {chosen.name}")
    else:
        print("no endpoint satisfied constraints")


if __name__ == "__main__":
    main()
```

运行一次预期在毫秒级；缓存命中率、step 数、平均推理时延都来自你自家的 trace；如果发现某个模型在这个 workload 下被反复拒绝，说明它要么价格太高、要么时延太慢、要么不在审批清单——**这也是路由给你提示的一种"成本可视化"**。

## Q&A：打工人最容易踩的几条相关问题

**Q1：为什么不直接看官方定价表？**

> 定价表给的是没有缓存、没有特定 workload、没有 serving 状态的"理想单价"。Agent 系统的真实账单 = 单价 × 调用模式 × 缓存命中率。IBM Research 在 417 个任务上看到 Sonnet 比 GPT-4.1 便宜一倍，就是被这条公式反向纠正的。

**Q2：路由开销加多大会变瓶颈？**

> 文章给出的数字是单任务约 6 ms、内存 2 KB 量级。任何超过这个量级的"路由器"都需要重新审视设计——它正在用额外的工程复杂度换表现上的"更聪明"，但常常得不偿失。

**Q3：难度路由是不是已经过时？**

> 不是过时，是工具不够用。难度路线图可以做为多个输入信号之一，但不能让它单独承担路由决策；否则就像那枚 teal diamond 一样，accuracy 差不多，但 cost 已经被对手甩开。

**Q4：Compliance 路由一般在什么时候介入？**

> 在路由的"前置过滤"里就要介入，不能放到 fallback 阶段。任何一条请求都应当先经过治理策略过滤（审批模型清单、数据驻留规则、隐私标记），再到 cost-quality-latency frontier 里选点。

**Q5：怎么知道自己的 cache hit 率？**

> 看推理 provider 的 cache_read_tokens / total_input_tokens 比值；自托管则看推理服务日志里的 cache hit counter。把这个比值直接喂给路由策略，永远比"按定价表估算"更接近真实账单。

**Q6：能不能直接抄 IBM Research 的优化算法？**

> 文章说后续会发技术 follow-up；在此之前，可以先用上面的最小骨架把 frontier 搜索跑通。重要的不是哪一段代码，而是"把模型选择当作系统优化而不是分类"这个思维切换。

---

*作者：小六，一个在上海打工、对账单比对自己还熟的工程师*
