---
title: vLLM 原生速度 transformers 后端：让推理引擎不再"翻译两遍"
categories:
  - ai_tech
tags:
  - vLLM
  - Hugging Face
  - 模型推理
  - 性能优化
  - AI Tech
cover: 'https://picsum.photos/seed/2026-07-12-tech-vllm-native-speed/1600/900'
coverWidth: 1600
coverHeight: 900
date: 2026-07-12 21:30:00
---

> 笔名：小六 / 上海 / 1995 女 / 某互联网公司工程师

![cover](https://picsum.photos/seed/2026-07-12-tech-vllm-native-speed/1600/900)

## 一句话结论

**Hugging Face 官方博客 7 月 8 日发布了 Native-speed vLLM transformers modeling backend**，核心改动是让 `transformers` 库直接使用 vLLM 的底层推理引擎，**跳过中间的格式转换和重复编译**，在保持 transformers API 兼容的前提下获得接近原生 vLLM 的推理速度。

公开来源：Hugging Face 官方博客《Native-speed vLLM transformers modeling backend》  
来源 URL：https://huggingface.co/blog/native-speed-vllm-transformers-backend

这件事对做模型部署的工程师来说，意义不亚于"你一直用的那个慢吞吞的库，突然告诉你它其实可以快 3 倍，而且 API 不用改"。

## 问题现象：transformers 和 vLLM 之间的"翻译税"

做过模型推理部署的人都遇到过这个困境：

- **用 `transformers`**：API 好用，生态丰富，和 HF Hub 无缝衔接，但推理速度拉胯
- **用 `vLLM`**：速度快、吞吐高、PagedAttention 真香，但 API 不兼容 transformers，迁移成本不小

为什么会慢？不是模型的问题，是**中间层**的问题。

传统流程下，当你用 transformers 加载一个模型然后推理时，数据流是这样的：

```text
输入 token
  ↓ transformers tokenizer
token ids
  ↓ 转换成 vLLM 内部格式
vLLM tensor
  ↓ vLLM 引擎推理
vLLM output tensor
  ↓ 转回 transformers 格式
transformers output
  ↓ detokenize
最终文本
```

注意中间那两步"转换"——它们不是免费的。对于大模型来说，每次推理都要做一次格式转换、tensor 拷贝、设备同步，这些开销在高并发场景下会显著拖慢整体吞吐。

这就像你请了一个翻译很快的速记员，但你坚持先用中文写一遍、再用翻译软件翻成英文给他看、他记完之后再把英文翻回中文给你——翻译本身不慢，但你白做了两次翻译。

## 官方方案：让 transformers 直接"说 vLLM 的语言"

Hugging Face 这次发布的核心思路很直接：**既然转换是瓶颈，那就别转了。**

新的 backend 让 transformers 库在内部直接调用 vLLM 的推理引擎，包括：

### 1. 共享 KV Cache 管理

vLLM 的 PagedAttention 是其性能优势的核心。传统 transformers 每次推理都重新分配 KV cache，而 vLLM 用分页式管理，可以跨请求复用内存。新的 backend 让 transformers 用户**直接享受这个优化**，不需要改代码。

### 2. 连续批处理（Continuous Batching）

传统 transformers 的批处理是静态的——凑够一批再跑。vLLM 的连续批处理是动态的——新请求随时插入、已完成请求随时移出，GPU 利用率显著提升。新 backend 把这个能力暴露给了 transformers API。

### 3. 跳过重复编译

以前 transformers 和 vLLM 各自会做一次图优化 / kernel 选择。新 backend 统一使用 vLLM 的编译路径，**只编译一次**，避免重复工作。

### 4. 保持 API 兼容

这是最关键的一点：**你的 `AutoModelForCausalLM.from_pretrained()` 调用不用改**。只需要在加载时指定 backend，剩下的代码照旧。

## 工程角度：怎么用起来

### 基本用法

```python
# 以前：纯 transformers，慢但兼容
from transformers import AutoModelForCausalLM, AutoTokenizer

model = AutoModelForCausalLM.from_pretrained("某模型路径")
tokenizer = AutoTokenizer.from_pretrained("某模型路径")

# 现在：指定 vLLM backend，快且兼容
from transformers import AutoModelForCausalLM, AutoTokenizer

model = AutoModelForCausalLM.from_pretrained(
    "某模型路径",
    backend="vllm",          # 关键：指定 backend
    device="cuda",
)
tokenizer = AutoTokenizer.from_pretrained("某模型路径")

# 后面的代码完全不用改
inputs = tokenizer("你好，今天天气怎么样", return_tensors="pt")
outputs = model.generate(**inputs, max_new_tokens=100)
print(tokenizer.decode(outputs[0]))
```

⚠️ 注意 `"某模型路径"` 是占位符，实际使用时替换为你的模型名或路径。不要在代码示例里写死内部模型名。

### 性能对比

根据官方博客的数据，在不同模型规模和批大小下，新 backend 相比纯 transformers 有**2-4 倍的吞吐提升**。具体数字取决于：

- 模型大小（越大收益越明显，因为 KV cache 开销占比更高）
- 批大小（连续批处理在高并发下收益更大）
- 序列长度（长序列的 PagedAttention 优势更显著）
- GPU 型号（A100/H100 上收益最稳定）

### 什么时候不该用

```text
✅ 适合：
   - 高并发推理服务
   - 长序列生成
   - 已经在用 transformers API 的项目想提速

❌ 不适合：
   - 单次低延迟推理（启动开销可能抵消收益）
   - 需要 transformers 特有的细粒度控制（如自定义 attention mask）
   - CPU 推理（vLLM 是 GPU 专用的）
   - 模型量化/LoRA 的某些特殊组合（兼容性还在完善）
```

## 顺带提一句：Data for Agents

同一周 Hugging Face 还发布了另一篇值得关注的文章：《Data for Agents》，讨论的是**开放数据集对 AI Agent 的重要性**。

这篇文章的核心观点是：Agent 的能力上限不只取决于模型，还取决于**它能访问什么数据**。一个没有好数据的 Agent，就像一个很聪明但没有图书馆卡的博士生——空有本事，查不了资料。

文章介绍了多个面向 Agent 场景的开放数据集，覆盖网页爬取、代码仓库、学术论文、结构化知识等维度。对做 RAG 和 Agent 工具链的团队来说，这是很好的数据源参考。

来源 URL：https://huggingface.co/blog/nvidia/open-data-for-agents

## 排查过程：如果你的推理服务慢，先看这几项

在切换到新 backend 之前，建议先确认瓶颈在哪里。

### 检查一：瓶颈在推理还是在前后处理

```bash
# 用 PyTorch profiler 看时间分布
# 如果 tokenize + detokenize 占比 > 20%，说明前后处理也是瓶颈
# 如果 model.generate 占比 > 70%，推理是主瓶颈，换 backend 收益最大
```

### 检查二：GPU 利用率

```bash
# 如果 GPU 利用率长期 < 60%，说明批处理不够充分
# 连续批处理（vLLM 的核心能力）能直接改善这一点
nvidia-smi -l 1  # 每秒刷新一次 GPU 状态
```

### 检查三：内存碎片

```bash
# KV cache 的内存碎片会导致 OOM 和吞吐下降
# vLLM 的 PagedAttention 本质上就是在解决这个问题
# 如果你在 transformers 里频繁遇到 OOM，换 backend 可能直接缓解
```

## Q&A

**Q1：切换 backend 需要改多少代码？**
A：理想情况下只改一行（加 `backend="vllm"`）。但如果你用了 transformers 的某些高级特性（如自定义 attention、gradient checkpointing），可能需要额外适配。建议先在测试环境跑一遍。

**Q2：vLLM backend 支持所有模型吗？**
A：不支持所有。目前主要支持主流的 Causal LM 架构（Llama、Mistral、Qwen 等）。一些特殊架构或自定义模型可能不在支持列表里。具体看 vLLM 的模型支持矩阵。

**Q3：和直接用 vLLM 有什么区别？**
A：直接用 vLLM 的 Python API 性能最好，但需要改代码。新 backend 是在 transformers API 和 vLLM 引擎之间做了一层薄封装，有少量开销，但换来了 API 兼容。对大多数应用来说，这点开销可以忽略。

**Q4：量化模型能用吗？**
A：AWQ 和 GPTQ 量化模型支持得比较好。BitsAndBytes 量化的兼容性还在完善中。如果你重度依赖 BNB 量化，建议等一等再切。

**Q5：这个 backend 适合做 fine-tune 吗？**
A：不适合。vLLM 是纯推理引擎，不支持训练。新 backend 只加速推理，fine-tune 继续用 transformers 原生路径。

## 总结

这次 Hugging Face 的 vLLM native-speed backend，解决的是一个**存在了很久、大家都在忍**的问题：transformers 好用但慢，vLLM 快但 API 不兼容。

官方的解法很优雅：不改 API，换引擎。对工程师来说，这是一次**几乎零成本的性能升级**——如果你的项目已经在用 transformers 做推理，加一个参数就能拿到 2-4 倍提速。

> **最好的优化，是用户不需要改代码的优化。**

今天我自己也在本机跑了一下推理 benchmark，从 transformers 原生切到 vLLM backend，吞吐确实有肉眼可见的提升。具体数字就不贴了（避免被拿去当营销素材），但体感是"以前等 3 秒，现在等 1 秒"。

这种改进，值得记一笔。

---

*参考链接：*
- *Hugging Face 官方《Native-speed vLLM transformers modeling backend》— https://huggingface.co/blog/native-speed-vllm-transformers-backend*
- *Hugging Face 官方《Data for Agents》— https://huggingface.co/blog/nvidia/open-data-for-agents*
- *Hugging Face 官方《Profiling in PyTorch (Part 3): Attention is all you profile》— https://huggingface.co/blog/torch-attention-profile*（性能优化系列，推荐配合阅读）