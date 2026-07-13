---
title: PyTorch 注意力性能分析：为什么 SDPA Math 比朴素实现慢 3.7 倍
categories:
  - ai_tech
tags:
  - PyTorch
  - Attention
  - GPU 性能分析
  - FlashAttention
  - AI Tech
cover: 'https://picsum.photos/seed/2026-07-13-pytorch-attention-profiler/1600/900'
coverWidth: 1600
coverHeight: 900
date: 2026-07-13 21:40:00
---

> 笔名：小六 / 上海 / 1995 女 / 某互联网公司工程师

![PyTorch 注意力性能分析](https://picsum.photos/seed/2026-07-13-pytorch-attention-profiler/1600/900)

## 一句话结论

Hugging Face 官方在 7 月 10 日发布了 PyTorch Profiler 系列第三篇文章《Profiling in PyTorch (Part 3): Attention is all you profile》，用同一组注意力计算对比了朴素实现、原地掩码、SDPA Math、Efficient、Flash 和 cuDNN 后端。

官方来源：https://huggingface.co/blog/torch-attention-profile

最反直觉的结果是：**代码更短的 SDPA Math 后端，单次前向 CUDA 平均时间为 7.239 ms，反而比 1.955 ms 的朴素原地实现慢约 3.7 倍。** 原因不是 SDPA 这个接口慢，而是 Math 后端为了兼容性和数值安全，做了 FP32 上转换、每次重建因果掩码、安全 softmax，并启动了 20 个 GPU kernel。

而 Efficient、Flash 和 cuDNN 后端都把一整套注意力操作融合为一个 kernel。官方测试形状下，Flash 的 GPU 平均时间约为 146.8 μs，是几种融合后端中最快的。

这条新闻原始发布日期略超周末 72 小时窗口，因此按无新官方技术稿时的降级规则纳入七日窗口。它值得写，不是因为又出现了一个性能数字，而是因为它提醒我们：**不要凭 API 名字猜性能，要看 profiler trace。**

## 问题现象：换成一行 SDPA，为什么反而慢了

注意力的朴素计算流程并不神秘：

```text
Q × Kᵀ
  ↓
缩放
  ↓
应用因果掩码
  ↓
softmax
  ↓
注意力权重 × V
```

手写 PyTorch 时，它通常对应两个矩阵乘、一次缩放、一次掩码和一次 softmax。看到 `torch.nn.functional.scaled_dot_product_attention()` 可以把这些步骤压成一行，很多人的直觉是：代码少了，kernel 也应该少，速度自然更快。

官方 trace 却给出了相反结果：

| 实现 | 每次前向 kernel 数 | 关键现象 |
|---|---:|---|
| 朴素注意力 | 6 | 掩码操作额外触发一次内存复制 |
| 原地掩码 | 5 | 一行改动消掉 `Memcpy` |
| SDPA Math | 20 | FP32、重建掩码、安全 softmax |
| SDPA Efficient | 1 | 融合 kernel，保持 bf16 |
| SDPA Flash | 1 | FlashAttention-2，不落完整分数矩阵 |
| SDPA cuDNN | 1 | 针对问题形状生成并调优 kernel |

这就像你去办一张证。手写实现是自己跑五个窗口；SDPA 接口像把材料交给综合柜台。综合柜台背后可能直接一站办结，也可能为了确保任何人、任何材料都能处理，又复印、核验、盖章、备案了二十次。**柜台名字一样，后台路线完全不同。**

## 排查过程一：先找出隐藏的内存复制

朴素实现里，官方 trace 除了预期的五类运算，还多出一个 `Memcpy`。根因是普通的 `masked_fill()` 会返回新张量，需要额外复制；改成带下划线的原地版本 `masked_fill_()` 后，这个复制 kernel 就消失了。

```python
# 普通写法：会创建新张量
scores = scores.masked_fill(mask, float("-inf"))

# 仅推理、无反向传播时可考虑原地写法
scores.masked_fill_(mask, float("-inf"))
```

这是一行代码换掉一个 kernel，但不能机械照抄。原地操作会覆盖前向值，而自动求导可能需要这些值计算梯度。官方实验运行在 `torch.no_grad()` 下，没有反向传播，所以使用原地操作是安全的；训练阶段则必须先确认 autograd 依赖关系。

这个案例说明 profiler 的第一个价值：它能把“我没写复制”变成“运行时确实发生了复制”。如果只盯 Python 源码，根本看不到这一层。

## 排查过程二：SDPA Math 的 20 个 kernel 从哪里来

SDPA Math 是参考实现，它的第一目标是“尽可能都能运行”，而不是“在某一块 GPU 上最快”。官方 trace 里有三个主要成本。

### 1. bf16 被上转换为 FP32

测试输入是 bf16。朴素矩阵乘走了 Tensor Core 快速路径，而 Math 后端为了数值精度把数据上转换到 FP32，最终使用普通 CUDA Core 上的单精度矩阵乘。

这不只是计算单元变了，数据搬运量也增加了。模型推理里，算力和显存带宽都很贵；把 16 位数据扩大成 32 位，相当于搬家时把每个箱子都换成双倍体积，再抱怨电梯太慢。

### 2. 因果掩码每次重新构造

传入 `is_causal=True` 很方便，但 Math 后端会在每次前向过程中创建下三角矩阵、填充负无穷并转换成加性偏置。调用者不用手写掩码，不代表掩码不需要计算，只是工作被移到更深的一层。

如果相同序列长度被重复调用，这部分成本会不断出现。融合后端则可以把因果关系直接编码进 kernel，避免完整掩码矩阵在显存里来回落地。

### 3. 使用更安全的 softmax

普通 softmax 遇到整行都被掩码的情况，可能形成 `0/0` 并产生 NaN。Math 后端使用安全版本处理这个边界条件，因此又增加了检查和 kernel。

所以，Math 后端慢并不代表它“写坏了”。它是在用速度购买兼容性、精度和边界安全，适合作为可靠基线。真正需要高吞吐时，应让 PyTorch 自动选择融合后端，或在测试时明确比较各后端。

## 排查过程三：为什么 Flash 只有约 13% 占用率却最快

Profiler 里另一个容易误判的数字，是 Flash kernel 的估算 occupancy 只有约 13%。很多人会马上得出结论：GPU 没吃满，性能肯定不好。

官方解释恰好相反。

FlashAttention 会大量使用寄存器和共享内存，把注意力分块保留在芯片内部。以文中的示例计算，一个 block 有 128 个线程，每个线程使用 255 个寄存器，共需要 32640 个寄存器；一块 Ampere SM 总共 65536 个寄存器，因此同时只能容纳两个这样的 block，大约就是 13% 的理论 occupancy。

低占用率是因为每个 block “带的行李很多”，不是因为它没干活。这些寄存器和共享内存避免了完整的 `[seq, seq]` 注意力分数矩阵写入 HBM。序列长度为 4096 时，单个 head 的分数矩阵就有大约 1600 万个数；如果反复写入、读取、掩码再读取，显存流量会非常可观。

Flash 的做法像厨师把常用食材都放在手边的小操作台，一小块一小块完成计算，而不是每切一颗菜都跑一次仓库。操作台看起来被占得很满，能同时站的人少了，但整道菜反而出得更快。

因此，**occupancy 不能脱离 kernel 的资源使用、显存流量和最终耗时单独解读。**

## 一键排查方案：同时比较四种 SDPA 后端

下面的最小脚本会在支持 CUDA 的环境中分别尝试 Math、Efficient、Flash 和 cuDNN 后端，并输出 profiler 表。不同 PyTorch 版本、GPU 架构、dtype、head dimension 与序列长度可能导致某些后端不可用，脚本会记录跳过原因，而不是把失败误报成性能结果。

```python
import torch
import torch.nn.functional as F
from torch.nn.attention import SDPBackend, sdpa_kernel

if not torch.cuda.is_available():
    raise SystemExit("需要 CUDA GPU 才能比较 SDPA GPU 后端")

# 固定形状，便于不同后端公平比较
q = torch.randn(2, 16, 2048, 64, device="cuda", dtype=torch.bfloat16)
k = torch.randn_like(q)
v = torch.randn_like(q)

backends = {
    "math": SDPBackend.MATH,
    "efficient": SDPBackend.EFFICIENT_ATTENTION,
    "flash": SDPBackend.FLASH_ATTENTION,
    "cudnn": SDPBackend.CUDNN_ATTENTION,
}

for name, backend in backends.items():
    try:
        # 先预热，避免把首次初始化成本混入结果
        with torch.no_grad(), sdpa_kernel(backend):
            for _ in range(10):
                F.scaled_dot_product_attention(q, k, v, is_causal=True)
        torch.cuda.synchronize()

        with torch.no_grad(), sdpa_kernel(backend), torch.profiler.profile(
            activities=[
                torch.profiler.ProfilerActivity.CPU,
                torch.profiler.ProfilerActivity.CUDA,
            ],
            record_shapes=True,
        ) as prof:
            for _ in range(20):
                F.scaled_dot_product_attention(q, k, v, is_causal=True)
        torch.cuda.synchronize()

        print(f"\n===== {name} =====")
        print(prof.key_averages().table(
            sort_by="self_cuda_time_total",
            row_limit=15,
        ))
    except Exception as exc:
        print(f"\n===== {name}: 当前环境不可用 =====")
        print(type(exc).__name__, exc)
```

运行时重点看四件事：

1. `self_cuda_time_total` 与每次调用平均 CUDA 时间；
2. 每次前向实际启动了多少 kernel；
3. 是否出现额外的 `Memcpy`、dtype 转换或掩码构造；
4. CPU 时间是否异常偏高，工作可能只是从 GPU trace 移到了库内部。

不要直接复制官方 A100 上的数字作为自己机器的结论。正确姿势是固定业务真实的 batch、序列长度、head dimension 和 dtype，然后在自己的 GPU 上比较。

## cuDNN 的 0% 占用率，为什么也不能直接相信

官方 trace 中，cuDNN 后端甚至显示 0% achieved occupancy，但这并不表示 GPU 没工作，而是测量缺口。它通过 `cuLaunchKernelEx` 启动，CUPTI 无法像普通 `cudaLaunchKernel` 那样正确归因占用率。

资源足迹仍然能说明真实情况：文中示例每个线程使用 240 个寄存器，一个 block 有 256 个线程，总计 61440 个寄存器，接近单个 SM 的 65536 个上限。因此一次只能放入一个 block，实际行为和 Flash 的重资源 kernel 很接近。

同时，cuDNN 的 GPU 时间约 186.3 μs，位于 Flash 的 146.8 μs 与 Efficient 的 277.9 μs 之间；但 CPU 平均时间约 214 μs，高于 Flash 的 138 μs 和 Efficient 的 117 μs。原因是 cuDNN 会针对具体形状选择并准备执行计划，trace 表面更干净，工作却被移进了库内部的一条粗柱子。

**Profiler 不是判决书，它是线索。** 某项指标出现 0、某条轨迹突然变短，都应该继续问一句：工作是真的消失了，还是换了一个看不见的地方？

## Q&A

### Q1：生产环境应该强制指定 Flash 后端吗？

不一定。让 PyTorch 自动分派通常更稳，因为 Flash 对 dtype、形状、掩码和硬件有约束。可以在基准测试中强制后端做对比，但生产代码应准备回退路径，并监控版本升级后的性能变化。

### Q2：SDPA Math 慢，是不是就完全没用？

不是。它兼容性好、数值处理谨慎，适合作为正确性基线。当融合后端不可用，或需要排查数值差异时，Math 后端很有价值。

### Q3：原地 `masked_fill_()` 能用于训练吗？

不能一概而论。原地写入可能破坏 autograd 保存的中间值。纯推理且处于 `torch.no_grad()` 时风险较低；训练代码必须实际跑反向传播与梯度一致性测试。

### Q4：GPU 利用率和 occupancy 是一回事吗？

不是。GPU 利用率描述一段时间里设备是否忙碌，occupancy 描述一个 SM 上驻留 warp 与理论上限的比例。低 occupancy 的 kernel 仍可能因为减少显存访问而非常快。

### Q5：换后端后只测一次延迟可以吗？

不可以。首次运行可能包含上下文初始化、kernel 加载和执行计划选择。应先预热，再同步 GPU，重复多轮，并同时报告平均值、分位数和吞吐量。

## 总结

这篇官方性能分析最值得带走的，不是“Flash 一定最快”，而是一个排查习惯：**先猜 trace 应该长什么样，再打开 profiler，重点研究与预期不一致的部分。**

隐藏的 `Memcpy`、Math 后端的 20 个 kernel、Flash 看似不健康的 13% occupancy、cuDNN 的 0% 指标与偏高 CPU 时间，都是因为实际轨迹没有符合直觉，才暴露出真正的优化线索。

优化注意力性能时，可以按这个顺序行动：

```text
固定真实输入形状
  ↓
预热并重复测量
  ↓
比较 CPU / CUDA 时间
  ↓
查看 kernel 数、复制与 dtype 转换
  ↓
确认后端回退和数值正确性
  ↓
最后才决定是否强制某个后端
```

代码少不等于计算少，指标低不等于性能差，trace 干净也不等于没有隐藏成本。对 GPU 优化来说，最可靠的答案仍然是：在自己的工作负载上跑一次，然后认真看那条和预期不一样的线。

---

*参考资料：Hugging Face 官方《Profiling in PyTorch (Part 3): Attention is all you profile》— https://huggingface.co/blog/torch-attention-profile*
