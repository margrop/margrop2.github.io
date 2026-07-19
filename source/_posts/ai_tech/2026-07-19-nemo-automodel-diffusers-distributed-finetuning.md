---
title: NeMo Automodel 接入 Diffusers：不转换权重，如何把图像与视频微调从单卡扩展到多机多卡
categories:
  - ai_tech
tags:
  - NeMo Automodel
  - Diffusers
  - 扩散模型
  - LoRA
  - FSDP2
  - 分布式训练
  - AI Tech
cover: 'https://picsum.photos/seed/2026-07-19-nemo-diffusers-scale/1600/900'
coverWidth: 1600
coverHeight: 900
date: 2026-07-19 21:45:00
---

> 笔名：小六 / 上海 / 1995 女 / 某互联网公司工程师

![NeMo Automodel 与 Diffusers 的分布式微调工作流](https://picsum.photos/seed/2026-07-19-nemo-diffusers-scale/1600/900)

## 一句话结论

NVIDIA 与 Hugging Face 在 7 月 17 日发布了一套新的开源集成：**NeMo Automodel 可以直接读取 Hugging Face Hub 上符合 Diffusers 格式的图像和视频模型，在不转换 checkpoint、不重写模型的前提下，使用 FSDP2、张量并行、上下文并行和流水线并行做分布式微调。**

官方来源：https://huggingface.co/blog/nvidia/scale-diffusers-finetuning-nemo-automodel

这件事对工程团队的价值，不是“又多了一个训练框架”，而是把过去彼此割裂的两端接起来了：

```text
Diffusers：模型多、接口统一、生态成熟
  ↓
NeMo Automodel：训练分片、并行策略、多机编排、检查点管理
  ↓
同一份 Diffusers 权重直接训练
  ↓
训练结果仍可回到 Diffusers 推理与分享
```

工程师最值得记住三点：

1. **模型格式不再成为训练和推理之间的墙**：Hub 上的预训练权重可以直接进入训练，微调后的 checkpoint 也能直接给 `DiffusionPipeline` 使用；
2. **扩容主要变成配置选择，而不是模型代码重写**：从单卡 LoRA 到多机全量微调，核心差异集中在 YAML 和启动参数；
3. **预编码数据是吞吐量的关键**：先缓存 VAE latent 与文本 embedding，避免每个训练 step 重复做相同编码。

## 问题现象：Diffusers 推理很顺，训练一扩容就开始“换框架”

Diffusers 已经是开源扩散模型事实上的统一入口。图像模型、视频模型、LoRA、量化、采样器和 pipeline 基本都能用一套相近的 API 组织起来。

但到了微调阶段，团队经常遇到这种场面：

```text
阶段 1：单卡实验
  ↓ Diffusers 自带训练脚本可以跑
  ↓
阶段 2：模型变大、数据变多
  ↓ 显存不够，开始加梯度累积和 checkpointing
  ↓
阶段 3：需要 8 卡或多机
  ↓ 原脚本没有完整的分片、并行和容错能力
  ↓
阶段 4：切到另一个训练框架
  ↓ checkpoint 格式不一致
  ↓ 模型类要重写，推理端还要再转换回来
```

最终训练代码和推理代码像两套互不认识的亲戚：都说自己用的是同一个模型，见面却要先交换一轮证件。

官方文章给出的解决思路是：**保留 Diffusers 作为模型和 pipeline 的公共语言，把 NeMo Automodel 放在训练执行层。** Automodel 本身是一个基于 PyTorch DTensor 的开源训练库，当前集成支持 flow-matching 类模型，能够直接调用 Diffusers 模型类加载权重，并使用 Diffusers pipeline 生成结果。

它目前给出的现成 recipe 覆盖多种图像与视频模型，包括 12B 级图像模型、32B 级图像模型、1.3B 与 14B 视频模型，以及 27B 总参数的 MoE 视频模型。官方明确给出：某款 1.3B 视频模型可以放进单张 40GB A100，而更大模型则可以通过分片和并行策略扩展。

## 排查过程一：为什么“不转换 checkpoint”比看起来重要

传统跨框架训练经常多出一条转换链：

```text
Hub 权重
  ↓ 转成训练框架私有格式
  ↓ 分布式训练
  ↓ 再转成推理框架格式
  ↓ 才能给 pipeline、LoRA 工具或量化工具使用
```

转换不仅浪费时间，还会引入三个风险：

- 参数命名映射错误，某些层没有被正确加载；
- 精度、分片或权重绑定方式变化，转换前后结果不完全一致；
- 新模型上线后，团队必须先维护一套新的转换脚本，才能开始训练。

NeMo Automodel 这次集成的核心承诺是：预训练权重按 Diffusers 模型 ID 直接加载，训练结果可以直接回到 Diffusers 生态。下游已有的量化、编译、LoRA adapter 和自定义 sampler 仍能继续工作。

对新模型支持也更轻：通常只需要补一个数据预处理 handler 和模型 adapter，其余 FSDP2、分桶数据加载、checkpoint 和生成流程都复用现有栈。**新模型的接入成本从“重写训练脚本”缩小为“补齐薄适配层”。**

## 排查过程二：扩容为何能从改代码变成改配置

Automodel 提供的并行选项包括：

```text
FSDP2              → 参数、梯度与优化器状态分片
Tensor Parallel    → 单层计算拆到多张卡
Context Parallel   → 长序列 / 大时空 token 的上下文拆分
Pipeline Parallel  → 不同层分配到不同设备阶段
Expert Parallel    → MoE 专家分布到不同设备
```

单个项目不需要一次把它们全开。选择策略的原则仍然是先找瓶颈：

- 权重和优化器状态放不下，优先 FSDP2；
- 单层矩阵计算已经超过单卡能力，再考虑张量并行；
- 视频序列或高分辨率图像让上下文过长，考虑上下文并行；
- 层数很多且多机通信可控，才考虑流水线并行。

官方示例里，FLUX.1-dev 的全量微调使用八路 FSDP2，有效 batch size 为 32；同一套 recipe 可以通过命令行覆盖数据路径、分辨率、学习率计划、最大步数和 checkpoint 周期。模型结构不用因为“从一张卡变八张卡”重新写一遍。

这并不意味着分布式训练从此没有复杂度，而是复杂度被移动到了更适合管理的位置：**配置、拓扑和数据路径。** 这些内容可审计、可版本化，也更容易在不同环境里复现。

## 排查过程三：为什么训练前要先做 VAE latent 与文本向量缓存

扩散模型微调的一大隐形浪费，是每个 epoch 都重复做同样的编码：原图通过 VAE 得到 latent，caption 通过文本编码器得到 embedding，然后主模型才开始计算训练目标。

如果数据集不变，这些结果其实可以先算一次：

```text
原始图片 / 视频 + caption
  ↓ 多 GPU 并行预处理
VAE latent + 文本 embedding
  ↓ 写入缓存并生成分片元数据
训练阶段只读取缓存
  ↓ 不再每个 step 重复编码
```

官方用一个 78 张公共领域塔罗牌图像的数据集演示完整流程。预处理后，样本进入匹配纵横比的分辨率 bucket；训练直接读取缓存，并在 200 个 optimizer step 中每 50 步保存一次 checkpoint。生成时只需把现有 generation YAML 指向训练产物。

这套设计有两个直接收益：

1. **吞吐更稳定**：训练 step 不再被 VAE 或文本编码器的波动拖慢；
2. **多分辨率更可控**：通过 bucket 把尺寸接近的样本放在一起，减少 padding 和无效计算。

但要注意：缓存不是免费的。数据增强如果依赖每轮随机裁剪、随机 caption 或在线变换，预编码会把随机性提前固定。工程上需要在“训练吞吐”和“数据增强多样性”之间做选择。

## 性能数据怎么看：不要只盯每秒样本数

官方性能测试使用一台配备 8 张 H100 80GB、通过 NVLink 互联的服务器，数据来自三个稳定的 10-step 窗口，给出了 step time、吞吐量和每卡峰值显存。

几个有代表性的数字：

| 任务 | 训练方式 | Step time | 吞吐 | 每卡峰值显存 |
|---|---|---:|---:|---:|
| FLUX.1-dev 图像全量微调 | FSDP2 | 约 0.902 秒 | 35.51 images/s | 63.88 GiB |
| FLUX.1-dev LoRA r64 | DDP | 约 0.894 秒 | 53.73 images/s | 67.43 GiB |
| Wan 2.1 1.3B 视频全量微调 | 单步 49 帧样本 | 约 0.942 秒 | 8.50 clips/s | 6.09 GiB |
| Wan 2.1 14B 视频全量微调 | 激活检查点开启 | 约 3.798 秒 | 2.107 clips/s | 33.35 GiB |

这些数字不能直接当作采购结论，因为它们来自高端互联硬件和特定缓存数据集。但它们说明了两件事：

- 统一框架并没有把分布式能力换成明显的执行开销；
- LoRA 的优势不能只看显存，吞吐、全局 batch、通信方式和可训练参数量要一起看。

尤其是官方表中，某些 LoRA 配置的峰值显存未必低于全量 FSDP2，因为 DDP 会复制更多状态，而 FSDP2 会做分片。**“LoRA 一定最省显存”只在并行策略相同或单卡比较时才成立。**

## 一键方案：最小化跑通“预编码 → 微调 → 生成”

下面给出一个脱敏后的执行骨架。它不是通吃所有模型的一键魔法，但能把官方流程压缩为三个清晰阶段：

```bash
#!/usr/bin/env bash
set -euo pipefail

MODEL_ID="black-forest-labs/FLUX.1-dev"
DATASET_ID="multimodalart/1920-raider-waite-tarot-public-domain"
CACHE_DIR="/cache/flux_demo"
OUT_DIR="/tmp/flux_demo"

# 1. 预编码：缓存 VAE latent 与文本 embedding
uv run --locked --no-default-groups \
  --extra diffusion --extra diffusion-media \
  python -m tools.diffusion.preprocessing_multiprocess image \
  --dataset_name "$DATASET_ID" \
  --dataset_media_column image \
  --dataset_caption_column caption \
  --dataset_streaming \
  --max_images 78 \
  --output_dir "$CACHE_DIR" \
  --processor flux \
  --model_name "$MODEL_ID" \
  --max_pixels 245760

# 2. 八卡微调：直接复用已有 YAML，只覆盖本次运行参数
torchrun --nproc-per-node=8 \
  examples/diffusion/finetune/finetune.py \
  -c examples/diffusion/finetune/flux_t2i_flow.yaml \
  --data.dataloader.cache_dir "$CACHE_DIR" \
  --data.dataloader.base_resolution '[384,640]' \
  --step_scheduler.max_steps 200 \
  --step_scheduler.ckpt_every_steps 50 \
  --checkpoint.checkpoint_dir "$OUT_DIR/checkpoints"

# 3. 生成：checkpoint 直接交给 Diffusers 风格生成 recipe
python examples/diffusion/generate/generate.py \
  -c examples/diffusion/generate/configs/generate_flux.yaml \
  --model.checkpoint "$OUT_DIR/checkpoints/full/epoch_66_step_199" \
  --inference.height 640 \
  --inference.width 384 \
  --inference.prompts '["a vintage card of an astronaut tending a rose garden on Mars"]' \
  --output.output_dir "$OUT_DIR/generations" \
  --seed 2026
```

正式使用前需要确认对应模型 license、显存预算、容器或 CUDA 依赖，以及数据集字段名。对于算力较小的团队，先把全量微调 recipe 换成 LoRA，再从单机开始验证，是更实际的路径。

## Q&A

### Q1：这是否意味着 Diffusers 自带训练脚本没用了？

不是。单卡实验、小模型 LoRA、快速验证仍然适合直接使用 Diffusers 脚本。NeMo Automodel 的优势主要在大模型、多机多卡、并行策略和生产级 checkpoint 管理。没有扩容需求时，不必为了“框架更高级”增加复杂度。

### Q2：所有 Diffusers 模型都能直接训练吗？

目前不能。官方明确说明当前主要支持 flow-matching 模型，并为一批图像、视频模型提供现成 recipe。新的 Diffusers 模型通常还需要数据预处理 handler 和模型 adapter。正确说法是“不需要转换权重与重写整套训练”，不是“任何模型零适配”。

### Q3：全量微调和 LoRA 怎么选？

先看目标。少量风格学习、角色一致性或快速迭代，LoRA 成本低、部署方便；需要更深的领域适配，且有足够数据和算力，再考虑全量微调。还要结合并行策略看显存，不能只凭“LoRA 参数少”判断整体占用。

### Q4：预编码会不会影响训练效果？

固定 VAE 和文本编码器时，预编码通常不会改变主模型训练目标；但它会限制依赖在线随机变换的数据增强。若训练需要随机裁剪、动态 caption 或多种编码器状态，就要重新设计缓存粒度，或者接受部分在线编码成本。

### Q5：单张 24GB 显卡能不能用？

能否运行取决于模型规模。1B 级模型配合 LoRA、低分辨率、梯度检查点和较小 batch 有机会；12B 以上模型通常需要更大显存、CPU offload 或多卡。Automodel 提供扩展能力，但不能消除模型本身的内存需求。

### Q6：为什么官方更推荐容器？

分布式扩散训练依赖 PyTorch、CUDA、通信库和已编译扩展的版本组合。官方容器把这些依赖预先对齐，可减少“代码没错，环境先炸”的时间。需要自定义环境时再用 pip 或源码安装，并把完整版本锁进镜像或 lockfile。

## 总结

NeMo Automodel 接入 Diffusers 的真正意义，是把开源扩散模型的“模型生态”和分布式训练的“工程能力”接成同一条链。

过去的流程是：

```text
Diffusers 找模型
  ↓ 转格式
另一个框架做训练
  ↓ 再转格式
Diffusers 做推理
```

现在可以变成：

```text
Diffusers 模型 ID
  ↓ NeMo Automodel 直接加载
配置 FSDP2 / 张量并行 / 上下文并行
  ↓ 训练与保存
Diffusers pipeline 直接使用
```

对工程团队来说，最有价值的变化不是少写一次转换命令，而是**训练产物不再脱离原有生态，新模型接入也不必重建整套基础设施。**

但这套方案仍然有边界：当前以 flow-matching 模型为主，分布式拓扑仍需工程经验，预编码会影响动态数据增强，官方性能数字也不能直接照搬到普通 PCIe 服务器。

我的建议是：先选一个小数据集做 50 到 200 步的闭环测试，核对三件事——checkpoint 能否直接生成、单卡到多卡的 loss 是否一致、缓存与在线编码的样本是否等价。三件都过，再谈多机扩容。

**框架集成最怕“能启动”，训练系统真正要证明的是“能复现、能扩容、能回到推理端”。** 这次 NeMo Automodel 与 Diffusers 的合作，至少把这三件事放进了同一条公开、可检查的工作流里。

---

*参考资料：*
- *Hugging Face Blog《Fine-tune video and image models at scale with NVIDIA NeMo Automodel and Diffusers》(2026-07-17) — https://huggingface.co/blog/nvidia/scale-diffusers-finetuning-nemo-automodel*
- *NVIDIA NeMo Automodel 开源仓库 — https://github.com/NVIDIA-NeMo/Automodel*
- *Hugging Face Diffusers 文档 — https://huggingface.co/docs/diffusers/*
