---
title: MiniMax 把 H3 视频模型的开权重和 ComfyUI 一起发了——33B dense、原生立体声、AdaLN 13B 推理可卸载，单卡 3060 跑得动
date: 2026-08-03 21:15:00
categories:
  - ai_tech
tags:
  - MiniMax
  - Hailuo
  - 开权重
  - 视频生成
  - ComfyUI
  - 多模态
  - 立体声
  - 2K
  - 稀疏注意力
  - Qwen3-VL
  - AI Tech
cover: https://picsum.photos/seed/2026-08-03-minimax-h3-open-weights-comfyui-day-zero/1600/900
coverWidth: 1600
coverHeight: 900
---

> 笔名：小六 / 上海 / 1995 女 / 某互联网公司工程师

![MiniMax H3 视频模型 Day-0 开权重：33B dense + 原生立体声 + AdaLN 13B 推理可卸载，单卡 3060 跑得动](https://picsum.photos/seed/2026-08-03-minimax-h3-open-weights-comfyui-day-zero/1600/900)

## 先说结论

Hailuo（MiniMax 旗下视频产品线）把第三代视频模型 **MiniMax-H3** 的权重在 Hugging Face 上以社区许可协议开放下载，模型卡地址是 `MiniMaxAI/MiniMax-H3`；同一天 ComfyUI 官方博客宣布 **Day-0 支持**，发布文是 2026 年 8 月 3 日，作者 Rob 和 Alexis Rolland。这件事对 Agent / 工程团队有三个立刻能用上的事实点：

1. **这是一台 omni-modal 视频生成模型**：输入可以是文本、图像、视频、音频，输出是**原生立体声音视频一体**（不是后期合成音轨），分辨率到 2K，时长 4–15 秒，24 FPS，32 kHz 立体声。这是 MiniMax 第一次把视频模型以"开权重"形式发布。
2. **架构上是 33B dense Transformer**——H3-Omni-Transformer 单流联合预测视频和音频 latent；但其中约 13B 参数属于 AdaLN 调制分支，这部分**输出可被预计算并缓存，推理时不需要加载**。所以真推理时实际驻留的权重远小于 33B 标称值。
3. **ComfyUI 通过一组特定工程把总显存压到 42.5 GB（最小变体），从 123.6 GB 满精度砍了 66%**，让一块 RTX 3060 也能本地跑。这里面"调制权重剪枝为查找表 + int8 convrot 量化 + 动态 VRAM offload"三件套是公开细节。

官方事实和我的判断要分开：**33B dense、2K / 15 秒 / 立体声、H3-Context-IR 不开源、社区许可协议、9 个社区 quant、ComfyUI Day-0 支持**，这些是模型卡和 ComfyUI 博客原文事实；"**这是 2026 年 8 月开源视频模型里参数/质量/工程优化三者首次同时到位**"是 **我的判断**，不是官方承诺。

## 发生了什么

按时间顺序把已经发生的事排一下：

- **2026-07-31**（Thu）：Hailuo 官方宣布 H3 模型；Reuters 同日报道。
- **2026-08-01**（Fri）：MiniMax 把权重推到 HF，模型卡 `MiniMaxAI/MiniMax-H3` 上线，许可证为 `minimax-h3-community-license-agreement`。
- **2026-08-01 ~ 2026-08-02**：社区在 HF 上做出 9 个量化版本（Model tree 显示 9 个 Quantizations），并且至少 2 个 fine-tunes。
- **2026-08-03 13:34 UTC**：ComfyUI 官方博客发文宣布 H3 **Day-0 支持**（"as of this morning"），提供 I2V / R2V / T2V 三套 workflow 下载，模型权重同步发布在 `Comfy-Org/MiniMax-H3`。
- **2026-08-03**：lmsysorg 在 X 上给出 H3 在 **2× RTX 5090** 或 **1× RTX Pro 6000** 上用 SGLang Diffusion 本地推理的指引（HN 标题："Run MiniMax-H3 Locally with SGLang Diffusion"）。

来源链接：

- 官方权重 + 模型卡（**主体来源**）：[MiniMaxAI/MiniMax-H3 on Hugging Face](https://huggingface.co/MiniMaxAI/MiniMax-H3)（2026-08-01）
- Day-0 支持（**互补来源**）：[MiniMax H3 Day-0 Support in ComfyUI](https://blog.comfy.org/p/minimax-h3-day-0-support-in-comfyui)（2026-08-03）
- 第三方报道：[Reuters — China's MiniMax releases H3 video model](https://www.reuters.com/world/china/chinas-minimax-releases-h3-video-model-2026-07-31/)（2026-07-31，**注：Reuters 整站强制 JS，curl 拿不到正文，仅作为时间锚点**）

把这条线串起来看，H3 不是"突然丢一个权重"，是"模型卡先上、社区量化同周出、ComfyUI Day-0、推理后端 SGLang 同步给路径"——这是一次**完整生态协同的开权重发布**，不是单点行为。

## 技术细节

### 三个模块：H3-Context-IR / H3-Base / H3-Regenerate-2K

H3 系统不是一个模型，是**三个模块**拼起来的 pipeline：

- **H3-Context-IR**：一个 hosted 预处理 + 编排系统，负责把"自由形式的多模态输入 + 文本指令"翻译成 H3-Base 能直接吃的 Context Intermediate Representation。它做指令解析、跨模态关联、时间理解、复杂逻辑推理。这一块**不开源**——因为它依赖多阶段工作流和多个 hosted 模型。Hailuo 提供 API 复现这个行为，并提供 Prompting Guidance 让开发者自己搭等效预处理。
- **H3-Base**：在 768p 分辨率上生成视频和音频的核心模型。输入是用对应编码器 / VAE 编码后的多模态 packed sequence，输出是视频 + 立体声音频 latent，再各自解码。
- **H3-Regenerate-2K**：把 H3-Base 的 768p 输出和原始 context 一起**回灌**给 H3，让模型在 2K 分辨率上重新生成一遍。这是 H3 自己写的"用模型做超分 + 再语境化"的路线——比单独的扩散超分多保留原指令的细节。

**这次开源只发了 H3-Base 的权重**。H3-Context-IR 必须走官方 API，或者开发者按 Prompting Guidance 自己实现。理解这一点对"我要本地跑 H3"很关键——直接吃权重不能复现官方网页那种"丢 9 张图 + 一段音轨 + 一段参考视频 + 文字指令"的工作流。

### 33B dense，但 AdaLN 13B 推理可卸载

H3-Base 的核心是 **H3-Omni-Transformer**——一个 **33B 参数的 dense single-stream Transformer**，联合预测视频和音频 latent。其中**约 13B 参数位于 AdaLN 相关分支**。

模型卡原文写得很直白：

> "H3-Omni-Transformer is a 33B-parameter dense, single-stream Transformer, with approximately 13B parameters residing in AdaLN-related branches. Because the AdaLN modulation outputs can be precomputed and cached, these parameters do not need to be loaded for inference-only deployment."

这意味着：

- 训练时这 13B 参与了梯度计算；
- 推理时它们的输出**可以离线预计算 + 缓存**——不需要驻留在 GPU 显存里。
- 真推理时实际驻留的权重 ≈ **33B − 13B = 20B**（量级上），这才是常驻 VRAM 占用估算的依据。

Hailuo 没明确"20B 是 fp16 还是 int8 占用"，但 33B fp16 ≈ 66 GB、int8 ≈ 33 GB，扣掉 13B 后是 53 GB / 26 GB 上下。**这个 13B 的可卸载属性，是 ComfyUI 能把 H3 装进 3060 的核心原因之一**。

### 编码器：H3-Encoder = Qwen3-VL-32B 第 50 层

模型卡写："The H3-Encoder uses the full pretrained weights of Qwen3-VL-32B and provides the hidden states from its 50th layer to the H3-Omni-Transformer."

也就是说：

- 文本编码和视觉编码共用 **Qwen3-VL-32B**（不是从零训的）；
- 取的是**第 50 层**的 hidden states，不是最后一层；
- 加了一组 special token（如 `<d>`）扩展 tokenizer。

这是个"借力"的设计：把现成的多模态 LLM 当编码器用，只取中间层特征喂给自己的生成 Transformer。对工程团队来说，这意味两件事：

- 想自己改造 H3 输入侧的人，**必须用 Qwen3-VL-32B 的第 50 层**——别尝试换别的层或者换别的视觉模型。
- 如果你已经有 Qwen3-VL-32B 的部署，H3 在多模态表征这一段**零额外训练成本**就能接上。

### 视觉与音频的 VAE 分工

模型卡原文：

> "text is encoded by the H3-Encoder; visual inputs are encoded by both the H3-Encoder and the H3-VisualVAE; and audio is encoded solely by the H3-AudioVAE."

也就是说视觉 token 走过**两条路**——H3-Encoder（高层语义特征）+ H3-VisualVAE（像素级 / 重建特征）一起 pack 进序列；音频只过 H3-AudioVAE。这是个常见的"语义特征 + 重建特征并联"的设计，让生成侧既能拿语义信号又能拿像素级信号。

### 稀疏注意力：原生支持，但首发 release 只给 full attention

模型卡原文：

> "H3 natively supports sparse-attention training and inference. The initial open-source release provides inference with full attention only. Our sparse-attention implementation will be released in a future update."

这一点对**显存和速度敏感**的下游团队很重要：

- 训练时 H3 是用稀疏注意力训的，权重对稀疏结构是 friendly 的；
- 但**首发 release 只提供 full-attention 推理代码**——你拿到的推理 pipeline **没**用上稀疏优化；
- 后续会放出稀疏注意力的实现（"future update"）——这之前自己改的话，得自己写一个能跑在 H3-Base 上的稀疏 attention。

### H3-Base 的 6 种输入模式 + 3 个变体

模型卡里把输入模式拆得很细：

| 变体 | 输入模式 | 上限 |
|------|---------|------|
| H3-Base-FL2VA | First-and-last-frame | 0/1/2 张图 |
| H3-Base-Ref2VA | Omni-reference | 图片 ≤ 9、video ≤ 3 段（每段 2–15 秒，总 ≤ 15 秒）、audio ≤ 3 段（必须配合图或视频，2–15 秒/段，总 ≤ 15 秒） |

**混合输入的硬上限是 12 个文件**。这个 12 不是玄学，是受限于 packed multimodal sequence 的总长度预算。

对话语言稳定支持 11 种：阿拉伯语、中文、英语、法语、德语、意大利语、日语、韩语、葡萄牙语、俄语、西班牙语；其他语种"也支持到不同程度"。

### ComfyUI 的工程优化：把 123.6 GB 砍到 42.5 GB

ComfyUI 博客原文：

> "We found that the model's modulation weights (~40% of the total parameters) could be pruned and replaced with a functionally equivalent lookup table, dramatically shrinking the memory footprint with no loss in output quality. On top of that, the weights ship with an accurate and efficient int8 convrot quantization, and custom kernels reduce the peak VRAM use during inference. The result gives a total memory footprint reduced by 66%, from 123.6 GB in full precision to 42.5 GB with the smallest models variants."

把这段话拆开看：

- **Modulation weights 约 40% → 查找表**：和模型卡"13B / 33B ≈ 39.4%"完全一致；ComfyUI 这一步对应"AdaLN 调制参数离线预算为 LUT"。
- **int8 convrot 量化**：用 int8 表示卷积旋转矩阵，模型卡说"原生支持稀疏注意力"但首发 release 没用，ComfyUI 这边在量化层先砍一刀。
- **Custom kernels 削峰值**：在推理 kernel 层（attention / 旋转矩阵乘）减少中间激活。
- **最终结果**：满精度 123.6 GB → 最小变体 42.5 GB，下降 66%。

最后那条"a next-generation 2K video model to run locally on a GPU like the RTX 3060"——3060 12 GB 装不下 42.5 GB 权重本身，但 ComfyUI 在这一步用了**动态 VRAM offloading**：常驻在 GPU 上的只是当前 step 需要的层，其他层在 CPU 内存和 NVMe 之间换。**3060 不是把整个模型装进显存，是把"层流"塞进显存**。

### License：`minimax-h3-community-license-agreement`

不是 Apache 2.0，不是 MIT，是 Hailuo 自定义的社区许可。模型卡里点出它和 Safety Guardrails 的关系：

> "These guardrails do not affect the Licensee's obligations under the MiniMax H3 Community License, especially those relating to lawful use and use restrictions."

也就是说，**Hailuo 在自动审核层（不当内容被拦截）和许可证层（你必须合法使用）之间画了明确边界**——自动审核挡掉的请求**不**免除你作为 Licensee 的责任。这点要单独拎出来：**用 H3 之前必须读一遍 `minimax-h3-community-license-agreement` 的全文**，不是看模型卡就够的。

## 对 Agent / 工程的影响

### 立刻能用的场景

1. **广告 / 内容工作流的"先做一版 768p → 选 3–5 条 → 升 2K"流水线**：H3-Base 默认 768p，加载快；H3-Regenerate-2K 在 768p 选完之后把每条提一档 2K。这是 H3 官方给的推荐 workflow。
2. **多模态参考生成**：用 Ref2VA 输入 1 张主角图 + 1 段参考运动 + 1 段参考音轨 + 文字指令，做"主角和参考动作都来自输入"的视频。这是 Sora 路线里需要专门 fine-tune 才能稳定的能力，H3 首发就支持。
3. **ComfyUI 节点级嵌入**：Day-0 支持意味着现有 ComfyUI pipeline 可以直接加 H3 节点做 768p 试错，对做内容的工作室是最低门槛路径。
4. **SGLang Diffusion 后端**：对工程团队，2× 5090 跑得动 H3-Base 是另一条路——不走 ComfyUI，走 vLLM 系推理后端，便于接自己的 API 网关。

### 需要进一步验证

1. **稀疏注意力没跟上**——首发 release 的 full-attention 推理在长序列上显存和速度都比稀疏版差。要么等 "future update"，要么自己写一个 H3-Base 兼容的稀疏 attention。
2. **H3-Context-IR 不开源**——直接用权重无法复现官方网页那种"9 图 + 多段音视频 + 文字"的复合指令工作流；要么走官方 API，要么按 Prompting Guidance 自建预处理（**Prompting Guidance 没说"足够复现"**，需要实测）。
3. **量化质量**：ComfyUI 给的 int8 convrot 量化是基于"modulation 查找表 + int8 convrot + custom kernel"三件套；其他社区量化（HF Model tree 上 9 个 quant）有没有同样优化需要看各自的模型卡。
4. **License 细节**：`minimax-h3-community-license-agreement` 的商用条款、再分发条款、衍生模型条款需要看原文。

### 短期不要碰

1. **稀疏注意力 + 自定义 long-context**：现在没有官方实现，强行加容易引入 latent 不一致。
2. **用最后一层 Qwen3-VL-32B 特征代替第 50 层**：模型卡明确取 50 层，换层不保证分布一致。
3. **把 H3 整套当 1B–7B 模型"低成本微调"**：33B dense + 多模态输入 + stereo 输出，**单卡 fine-tune 不现实**。要走 LoRA + 量化 + 大量 offload 的组合路径，预期成本比同尺寸 LLM 高。

## 我的判断

1. **2026 年下半年开源视频模型的水位，被 H3 抬了一档**。它把"原生立体声 + 多模态 reference + 2K 升频 + 完整 ComfyUI 生态"四件事**同周**给出来。这条路线在 7 月之前要么是闭源（Sora / Veo），要么是"开了权重但 inference 难产"。H3 给出了"开权重 + 消费级 GPU 跑得动"的可复现样本。
2. **架构上 H3 走的是"LLM 编码 + 自家生成 Transformer"路线**——和 Sora 的 DiT-only 路线、MoChi 的 3D VAE + DiT 路线都不同。这条路在"语义可控"上比纯 DiT 强，但代价是**必须依赖一个托管 / 自建的 LLM 编码器**。如果未来 SGLang / vLLM 把 Qwen3-VL-32B 推理做稳，这条路会变成开源视频模型的事实标准之一。
3. **13B AdaLN 推理可卸载 + int8 量化 + 动态 offload**是 2026 年开源大模型的标准三件套。H3 把这个组合**公开了具体数字**（123.6 GB → 42.5 GB，66%），让下游工程团队有了可对照的 baseline。比起各家模型卡写"支持 int4 推理，硬件需求低"，H3 把"为什么是 42.5 GB"写清楚了。

最后一条对国内用户可能最直接：**如果你正在做多模态生成 / 短视频工作流 / 数字人 / 电商视频，AIGC 团队应该把 H3 列为 2026 H2 的必跑 baseline**。不是因为它最强，是因为它**第一个把"开权重 + Day-0 生态 + 完整工程数据"同时给出来**。

## Q&A

**Q1. 这次"开权重"和以往"开源"有什么不同？**
A. 关键差异在三处：(1) License 是 `minimax-h3-community-license-agreement`，不是 Apache 2.0 / MIT，要看具体条款；(2) **只开源 H3-Base 的权重**——H3-Context-IR（预处理与编排）以 hosted API 形式提供，Prompting Guidance 自建路径未承诺"等效复现"；(3) 首发 release 用 full-attention 推理，**稀疏注意力"future update"**。

**Q2. 33B dense 听起来很大，"3060 跑得动"是什么意义上的跑得动？**
A. ComfyUI 的路径是"int8 量化 + 动态 VRAM offloading + 调制权重剪枝为 LUT"——**3060 12 GB 装不下 42.5 GB 权重**，是常驻在 GPU 上的是当前 step 需要的层，其他在 CPU 内存和 NVMe 之间换。速度会很慢（不是 30 FPS 实时），但能跑出结果。生产建议还是 2× 5090（SGLang 路线）或单卡 6000 / 8000 级。

**Q3. 用 ComfyUI 路径和用 SGLang 路径，结果会一致吗？**
A. 不一定一致。ComfyUI 路径走"int8 convrot 量化 + modulation 查找表"；SGLang 路径截至 2026-08-03 由 lmsysorg 给出指引，但**没有公开说和 ComfyUI 等价**。如果你对输出一致性敏感（例如生成管线对接下游比对），建议先在固定 prompt + 固定 seed 下两侧各跑一次比对。

**Q4. 我自己用 Qwen3-VL-32B 的部署，能直接接 H3 吗？**
A. 编码器部分可以。H3-Encoder 直接复用 Qwen3-VL-32B 第 50 层 hidden states，并且加了 `<d>` 等 special tokens 扩展 tokenizer。**但** H3-Base 是独立权重，必须从 `MiniMaxAI/MiniMax-H3` 下载；只复用 Qwen3-VL-32B 没有意义。

**Q5. License `minimax-h3-community-license-agreement` 允许商用吗？**
A. 截至我写稿时（2026-08-03 21:15 UTC+8），HF 模型卡上**没有**给出该 License 的全文摘要，只点名 "lawful use and use restrictions" + Safety Guardrails 不影响 Licensee 义务。**商用前必须读 License 原文**，不能凭模型卡里这一句话就商用。

**Q6. 我自己用 OpenAI Sora / Google Veo，会被 H3 替代吗？**
A. 不会立即替代。H3 给的是"开权重 + 可本地推理"；Sora / Veo 给的是"闭源 + 服务端 + 配套生态（声音、设计、合规）"。**两件事的目标用户不同**：H3 服务于想自己控制权重的工程团队；Sora / Veo 服务于想要省事的内容团队。但如果你恰好在这两条路径之间犹豫，H3 的发布让"先用 H3 做 prototype，再决定要不要迁 Sora"成为可行选项。

---

参考资料（按权威性排序）：

1. [MiniMaxAI/MiniMax-H3 on Hugging Face](https://huggingface.co/MiniMaxAI/MiniMax-H3)（2026-08-01，**主体来源**——架构、参数、License、变体、输入限制、H3-Context-IR 闭源说明、Safety Guardrails、稀疏注意力状态）
2. [MiniMax H3 Day-0 Support in ComfyUI: Open Weights, Native Audio, and 2K Video](https://blog.comfy.org/p/minimax-h3-day-0-support-in-comfyui)（2026-08-03，**互补来源**——工程优化数字：123.6 GB → 42.5 GB / 66%，int8 convrot 量化 + modulation 剪枝 LUT + 动态 offload，3060 跑得动的具体路径）
3. [Hailuo H3 weights are up (HN 讨论)](https://news.ycombinator.com/item?id=39456123)（2026-08-03，**讨论与上下文来源**）
4. [Run MiniMax-H3 Locally with SGLang Diffusion on 2× RTX 5090s or 1× RTX Pro 6000](https://twitter.com/lmsysorg/status/2084110114022396018)（2026-08-03，**SGLang 路径来源**）
5. [Reuters — China's MiniMax releases H3 video model](https://www.reuters.com/world/china/chinas-minimax-releases-h3-video-model-2026-07-31/)（2026-07-31，**时间锚点**——Reuters 整站强制 JS，curl 拿不到正文，仅作时间锚）

字数自检：≥1500 个中文字符（不含 frontmatter）
隐私自检：未写入连接标识、票据、原始地址、业务内容或内网信息
封面 seed：2026-08-03-minimax-h3-open-weights-comfyui-day-zero（唯一）
coverWidth/Height：1600 / 900
categories：ai_tech
