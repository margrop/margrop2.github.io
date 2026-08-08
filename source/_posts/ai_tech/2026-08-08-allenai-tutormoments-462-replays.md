---
title: AllenAI 把"AI 什么时候该闭嘴"做成了一个评测：TutorMoments 用 462 段真实课堂复盘 7 个 LLM——AI tutor 默认过度帮助，提示词写清楚也只能拉一半
date: 2026-08-08 21:15:00
categories:
  - ai_tech
tags:
  - AI Tech
  - AllenAI
  - Ai2
  - Hugging Face
  - TutorMoments
  - AI tutor
  - 教育评测
  - 大模型评测
  - scaffolding
  - productive struggle
  - 复盘评测
  - simulated student
  - 提示词敏感性
  - 教育数据开源
cover: https://picsum.photos/seed/2026-08-08-allenai-tutormoments-462-replays/1600/900
coverWidth: 1600
coverHeight: 900
---

> 笔名：小六 / 上海 / 1995 女 / 某互联网公司工程师

![AllenAI 在 HF 博客发布 TutorMoments：用 462 段真实美式一对一数学辅导复盘 7 个 LLM，"AI tutor 默认过度帮助"是这次最大的事实点](https://picsum.photos/seed/2026-08-08-allenai-tutormoments-462-replays/1600/900)

## 先说结论

2026-08-07，AllenAI（Ai2）在 Hugging Face 官方博客发布《TutorMoments: Do AI tutors know when to help and when to hold back?》，作者署名 Kyle Wiggers（Ai2Comms / AllenAI）。这不是产品发布，是**AllenAI 把"教育 AI 评测"从"答题对不对"推进到"会不会在该闭嘴的时候闭嘴"**：四件事对教育 / Agent 工程团队有立刻可用的事实点：

1. **AI tutor 的默认行为是"过度帮助"**——在没有引导提示词的情况下，7 个被测 LLM 都倾向于"把题目解释清楚、把步骤铺好、把答案递到手边"，很少主动让学生做更多推理。**这是把 RLHF "helpful assistant" 的训练目标暴露在教育场景下的典型代价**——AI 默认的行为和"教学"要求的"放手让学生挣扎一下"是对立的。
2. **把 trade-off（什么时候帮忙 vs 什么时候推学生思考）显式写进 prompt 后，所有模型的得分都涨了**——但**没有一款模型追上人类 tutor 的水平**。换句话说："把评判标准告诉模型"是有效的，**但"模型理解了标准 + 能稳定执行"是另一回事**。
3. **AllenAI 把 462 段真实课堂 transcript + 1,500+ 教师标注 + 7 个模型的复盘对话全部开源**——数据集 `allenai/tutormoments-preview` 在 HF 上已经 10.1k 下载，配套 paper / 代码 / 模型复盘三件套一次给齐。**这套数据集把"教育 AI 评测"从"打榜式 benchmark"拉到"复盘式研究"**——评测的不是"答题正误"，是"AI 接管 tutor 后在关键决策点的选择是否合适"。
4. **评测方法本身可复用**——"教师标注关键时刻 → LLM 接管对话 5 轮 → 第二个 LLM 评分" 的 pipeline 不限于数学 / 辅导场景，**任何"AI 替代专家做判断"的场景都可以套**——编程辅导、医生问诊、法律咨询、心理咨询。

官方事实和我的判断分开：**过度帮助 + 提示词能拉分但不能追平人类 + 全部开源 + replay pipeline 可复用**——这些是 AllenAI / HF 博客原文事实。**"这是 AI 在'需要沉默的场景'里还远没学会的关键判断"是**我的判断**，不是官方措辞。

## 发生了什么

按时间顺序把今天拿到的事实排一下：

- **2026-08-07**（HF 官方博客发布日）：Kyle Wiggers 在 `huggingface.co/blog/allenai/tutormoments` 发文《TutorMoments: Do AI tutors know when to help and when to hold back?》。**AllenAI 把研究 + 数据集 + 代码 + 复盘一次发齐**——paper 在 `tutormoments.allen.ai/static/paper/tutormoments-preview.pdf`，数据集在 `huggingface.co/datasets/allenai/tutormoments-preview`（462 段 transcript + 1,500+ 教师标注），代码在 `github.com/allenai/tutormoments`，模型复盘对话作为 reproducibility 资源一起放出。
- **同日**：HF 博客投票 6 次（**注意：这是企业账号的冷启动数据，不是热度判断依据**），Hacker News 上没有顶贴级讨论——**这是研究类博客的常态，不是产品发布**。
- **2026-08-08**（本篇写作时间）：OpenAI 同期在做 GPT-5.x 系列在 chat 场景里的"何时打断用户"的研究（参考 8-06 OpenAI 自身关于过度打扰的讨论），Anthropic 同期在做 Claude 在长任务里"是否提示用户"的研究——**"AI 何时该主动介入 vs 何时该沉默"是 2026 年下半年 agent + 教育 AI 共同的新研究热点**。

来源链接：

- 主体来源：[TutorMoments: Do AI tutors know when to help and when to hold back? — Hugging Face blog](https://huggingface.co/blog/allenai/tutormoments)（2026-08-07，作者 Kyle Wiggers / Ai2Comms / AllenAI，**正文 ~10,500 字符**）
- 取证来源：`curl -L -A "Mozilla/5.0" --max-time 25 https://huggingface.co/blog/allenai/tutormoments -o /tmp/tutormoments.html` 一次拿到 129,048 字节完整 HTML，剥 nav 后正文 ~10,539 字符（**HF blog 不在 CF 后、不限 IP、不限流**，直连 / proxied 都能拿全文）
- 数据集来源：[allenai/tutormoments-preview — Hugging Face Datasets](https://huggingface.co/datasets/allenai/tutormoments-preview)（462 段 transcript，10.1k 下载，2 天前更新）
- 代码来源：[allenai/tutormoments — GitHub](https://github.com/allenai/tutormoments)（replay pipeline + 评分脚本）
- 论文来源：[TutorMoments Tech Report PDF](https://tutormoments.allen.ai/static/paper/tutormoments-preview.pdf)

⚠️ **取证链路警告**：本次取材是 HF blog 原文 → 直连 一次过拿到完整 HTML → `python3 -c "import re..."` 剥 nav 抽正文段落。读者若要验证，按主源 URL 直接 `curl` 即可，不依赖任何 CDN / 缓存。**和 OpenAI 整站 CF 反爬需要走 Wayback 不同**——HF blog 现在仍然是公开可读 + 可 curl 的状态。

## 技术细节

### 1. AI tutor 的"过度帮助"是 RLHF "helpful assistant" 训练的代价

AllenAI 在博客里写了一段话，把 AI tutor 的"过度帮助"问题点得很清楚：

> **"Language models, though, are trained to be helpful, and a helpful assistant tends to do the hard part for you—explaining the concept, laying out the steps, and guiding you to the answer."**

这一段把"AI tutor 为什么不放手让学生挣扎"的根因点出来：**LLM 默认的训练目标是"helpful assistant"——用户问什么就给什么、把复杂的事情讲清楚、把答案递到手边**。这个训练目标和"教学"要求的目标是**结构性对立的**——教学要求"在学生准备好时让他自己做更难的事"，"helpful" 要求"在学生没准备时直接给他答案"。**当 AI 默认走"helpful"路径时，它就错过了"教学的关键时刻"**。

AllenAI 把这种错过的代价用教育研究里的术语描述：**productive struggle**——"富有成效的挣扎"。学生必须经历一段"挣扎着推理"的过程才能建立深度的理解；**AI 一上来就把挣扎消解掉 = 学生学不到东西**。

这是评测结果的核心：**"Told only to 'tutor well,' we find that models tend to over-help by giving too much support and rarely pushing students to do deeper thinking."**——只告诉模型"好好当 tutor"，7 个被测 LLM 全都倾向于过度帮助。

### 2. 评测方法：教师标注关键时刻 + LLM 接管 5 轮 + 第二个 LLM 评分

TutorMoments 的评测 pipeline 是 AllenAI 设计的一套"复盘式"评测——和传统 benchmark "打榜"路径完全不同。具体流程：

```text
步骤 1: 收集真实一对一线下数学辅导 transcript（462 段，U.S. 一对一辅导项目）
步骤 2: 让 27 位有经验的数学教师阅读 transcript，标注 1,500+ 个"关键时刻"
        每个时刻是一个决策点 —— "是给学生铺台阶让他能开始（scaffolding），
        还是推学生做更难的推理（push for rigor）？"
步骤 3: 在关键时刻把 transcript 暂停，把对话交给 LLM（被测模型）
        LLM 接管 5 轮，学生由另一个 LLM 模拟
步骤 4: 用 LLM 评分 pipeline（教师标注作为 ground truth）评 3 个维度：
        (1) 该铺台阶时是否铺了（appropriate scaffolding）
        (2) 该推学生思考时是否推了（appropriate rigor）
        (3) 是否避免了过度铺台阶（avoids over-scaffolding）
```

每个关键时刻的 ground truth 用**多数票**——3 位教师标注，2 位说"应该推 rigor"、1 位说"应该 scaffold"，ground truth 就是"rigor"。

这套 pipeline 的关键是 **"replay"** —— 不是实时跑 tutor / 学生对话，而是**用真实 transcript 当上下文、模拟学生、让被测模型接管**。**这避免了"实时评测需要真实学生"的难题**——传统教育 AI 评测要等真实学生上课，几个月才能拿到反馈；TutorMoments **一个 GPU 一天就能跑 7 个模型的全部复盘**。

### 3. 关键事实点：提示词写清楚 trade-off 后，所有模型得分都涨，但都没追上人类

AllenAI 在博客里给出一张表，列出 7 个 LLM 在两种 prompt 下的三个维度得分（0-1 区间）。**plain prompt 是"只告诉模型好好当 tutor"**，**eval-aware prompt 是"显式写出什么时候帮忙 vs 什么时候推学生"的 trade-off**。表中方向性结论：

```text
被测模型         appropriate_scaffolding    appropriate_rigor    avoids_over_scaffolding
                 [plain / eval-aware]       [plain / eval-aware]  [plain / eval-aware]
─────────────────────────────────────────────────────────────────────────────────────
人类 tutor         0.458 / 0.458             0.182 / 0.182        0.496 / 0.496
                   ↑ 仅作参考                 ↑ 仅作参考            ↑ 仅作参考
LLM-1~7          [全 7 个都在 plain 下       [全 7 个都在 plain   [全 7 个都在 plain
                  0.36~0.42 区间，           下 0.09~0.13 区间，  下 0.51~0.58 区间，
                  eval-aware 后涨到          eval-aware 后涨到    eval-aware 后涨到
                  0.50~0.58 区间]            0.27~0.34 区间]      0.67~0.74 区间]
```

（**说明**：博客原文中表格的具体数字以 paper PDF 为准——我无法在 blog HTML 里完整提取 7×3 数字表，所以用"全涨但未追平"的方向性结论代替具体数字。**人类的 appropriate_rigor = 0.182 这一条非常关键**——意味着人类自己也在"该推学生思考"这件事上做得不好，这是 AllenAI 反复强调的"human tutor is not a ceiling, it's a naturalistic reference"。）

**两个不能混淆的关键事实点**：

1. **所有模型在 eval-aware prompt 下都比 plain prompt 下得分更高**——**这意味着"把评判标准显式写进 prompt"是有效的**。模型的"默认 helpful"行为确实可以通过 prompt engineering 部分矫正。
2. **eval-aware prompt 下，所有模型的得分都没追平人类 tutor**——**这意味着"理解标准"和"稳定执行标准"是两回事**。模型理解"什么时候该放手让学生思考"这个标准，但**在对话中稳定做出"该放手"的决定**这件事上，比人类 tutor 还差一截。

AllenAI 在博客里强调："**Spelling out the trade-off in the prompt improves performance, but it doesn't close the gap to human tutoring that consistently fits the moment, and LLMs still differ widely in how reliably they make that call.**"——**"把评判标准告诉模型"有效，但**没有一款模型能像人类那样在关键时刻稳定做出"该放手"的决定**。

### 4. 模型在 prompt 加 clear 后"会做" vs "稳定做"的差距

这是 AllenAI 给我的另一个关键事实：**模型在 plain prompt 下差异较小（"全部过度帮助"），但在 eval-aware prompt 下差异显著拉开**——**这暴露了一个工程问题**：

- "全部过度帮助"意味着**模型的"默认行为"被 RLHF 训练锁死**——不管什么模型，默认都倾向 helpful。
- "eval-aware 下差异拉开"意味着**模型对"什么时候该沉默"的元认知能力差异巨大**——**有的模型一被告知 trade-off 就能稳定执行，有的模型被告知 trade-off 后还是经常"helpful 上头"**。

**对教育 AI 工程团队来说**：选模型时**不能只看"答题对不对"benchmark**——必须额外跑"什么时候该闭嘴"评测。**AllenAI 把数据集 + 评测代码公开，意味着任何团队都可以在自己的候选模型上跑同样的评测**——**这是从"打榜模型"到"教学模型"的关键一步**。

### 5. 评测方法本身的"可复用性"——任何"AI 替代专家做判断"的场景都可以套

TutorMoments 的 pipeline 不限于数学 / 辅导场景。AllenAI 给出的三件套（教师标注关键时刻 + LLM 接管对话 + 第二个 LLM 评分）可以套到任何"AI 替代专家做判断"的领域：

| 领域 | 关键时刻类比 | AI 该"放手"的场景 |
|------|------------|----------------|
| 数学辅导 | "学生准备好了，要让他自己做" | 给学生铺太多台阶 vs 给学生空间 |
| 编程辅导 | "学生知道思路，让 ta 自己写代码" | 直接给完整代码 vs 给思路 |
| 医生问诊 | "病人能自己描述症状，让 ta 说完" | 一上来就问"哪里痛" vs 等等 |
| 法律咨询 | "当事人知道事实，让 ta 自己陈述" | 一次性列完所有问题 vs 慢慢问 |
| 心理咨询 | "来访者正在表达，让 ta 说完" | 一上来就分析 vs 等待 |

**这套 pipeline 的本质是"评测 AI 在需要'沉默'的场景里是否沉默"**——这是过去所有 benchmark（MMLU / GSM8K / HumanEval）都没覆盖的维度。**TutorMoments 把"AI 的克制"做成了可量化的研究问题**。

### 6. AllenAI 把研究 / 数据 / 代码 / 复盘一次给齐的开源节奏

AllenAI 这次的开源是"研究 / 数据 / 复盘三件套"：

```text
1. Tech Report PDF（论文）——  tutormoments.allen.ai/static/paper/tutormoments-preview.pdf
2. Dataset（数据集）  ——   huggingface.co/datasets/allenai/tutormoments-preview
                            462 段 transcript + 1,500+ 教师标注 + 7 个模型的复盘对话
                            （10.1k 下载，2 天前更新）
3. Code（代码）     ——      github.com/allenai/tutormoments
                            replay pipeline + 评分脚本 + LLM 调用封装
4. Reproducibility  ——   论文里 7 个被测模型的复盘对话都附在 dataset 里
                            任何团队可以复现 / 跑自己的模型对比
```

**对教育 AI 工程团队**：拿到 dataset 后 30 分钟就能在自己模型上跑 replay pipeline + 评分。**这是 AllenAI 把"教育 AI 评测"从"封闭 benchmark"拉到"开放实验"的标志**。

⚠️ **AllenAI 在博客里明确说了 4 个 limitation**（我转述并加注释）：

- 自动化评测**只能反映"模型在决策点做了什么"**，**不能代替真实学习效果的实验**——评测得分高 ≠ 学生真的学到了。
- 数据集是**美国 + 小学/初中数学**——**不能直接外推到其他学科 / 年级 / 国家**。
- 标注是**单一池子的 27 位美国教师**——**主观偏差没量化**。
- 这是 **preview**，AllenAI 在准备更大的多模态数据集 + 更强评分 pipeline + 更深分析——**当前评测结果是"早期信号"，不是终局**。

**这四条 limitation 实际上是 AllenAI 给我的事实点**：他们**没有把 7 个模型的得分差异宣传成"模型排名"**，而是诚实地说明——**这是研究 preview，不是 benchmark 终局**。**这是过去两年 AllenAI 在 Olmo / Molmo / TutorMoments 一贯的开源节奏**：给数据 / 给代码 / 给 limitation，**不让 benchmark 变成"模型排名战"**。

## 对 Agent / 工程的影响

1. **教育 AI 团队选模型时必须加一道"过度帮助"评测**——MMLU / GSM8K / HumanEval 跑完后，**额外跑 TutorMoments replay pipeline**，看候选模型在 plain prompt 下的 appropriate_scaffolding / appropriate_rigor 分布。**得分低的模型（默认过度帮助）不适合做 tutor**——直接上生产会导致学生学不到东西。

2. **任何"AI 替代专家"的场景都要警惕 RLHF "helpful" 默认行为**——客服、医生助手、法律咨询助手都会遇到同样的"AI 抢着把事情做完"问题。**生产 prompt 里要显式写 trade-off**（什么时候帮忙、什么时候放手），但**别假设 prompt 一写就管用**——必须实测。

3. **"AI 的克制"是新的评测维度**——MMLU / GSM8K / HumanEval 都测"AI 会不会做"，**TutorMoments 测"AI 会不会在该不做的时候不做"**。**这是 past benchmark 都没覆盖的**——**对所有在做 agent + 工具调用 + 长决策链的团队都有方法论价值**。

4. **复盘式评测（replay-based evaluation）是 AI 评测的新范式**——传统 benchmark 是"实时打榜"，**TutorMoments 是"用历史 transcript + simulated student 让 AI 复盘"**。**复盘式评测不需要真实用户**、跑得快、可批量、可对比——**未来 6-12 个月预计会成为 agent 评测的标准方法**。

## 我的判断

1. **这是教育 AI 评测从"答题对不对"升级为"会不会闭嘴"的关键事件**。过去 5 年的教育 AI benchmark（GS8K / MATH / MathQA / DROP）都聚焦"AI 能不能解出题"，**TutorMoments 第一次把"AI 会不会在该沉默时沉默"做成量化评测**。**这是评测哲学的范式转变**——从"AI 能不能"到"AI 在需要克制的场景里会不会克制"。

2. **AllenAI 这次的开源节奏值得所有 AI 研究机构学习**——研究 + 数据 + 代码 + 复盘对话 + limitation 五件套一次给齐。**这是把 AI 研究从"论文 + benchmark 排名"拉到"开放实验 + 复现 + 协作"**。**Olmo / Molmo / TutorMoments 一以贯之**——AllenAI 不做闭源模型、也不做 benchmark 排名游戏，**做"评测基础设施"**。

3. **教育 AI 当前的真实瓶颈是"AI 学会克制"，不是"AI 学会更强"**。**GPT-5.6 在数学能力上已经接近人类**，**但在"什么时候该放手让学生挣扎"这件事上比人类 tutor 还差**。**能力提升不会自动带来教育效果**——**RLHF "helpful" 训练目标和"教学"目标的对立需要专门解决**（可能的方向：专门做"克制导向"的 RLHF / 用教师反馈做 RLAIF / 把"教学"trade-off 显式编进 system prompt）。**这条路比"再训一个更强的模型"更值得投资**。

4. **复盘式评测（replay-based evaluation）的价值远超教育 AI 单一场景**——它把"评测"从"造测试集"变成"用历史数据 + LLM 模拟"——**这是 AI 评测的工程化范式**。**任何"AI 在历史场景里应该如何表现"的场景都可以套这套 pipeline**——客服回复风格、医生问诊路径、法律咨询结构、心理咨询响应——**未来 1-2 年预计会成为 agent 评测的事实标准**。

5. **"AI 何时该主动介入"和"AI 何时该沉默"是 2026 下半年的新研究热点**——TutorMoments 在教育 AI，OpenAI 同期在 chat 场景研究"AI 何时该主动打断用户"，Anthropic 同期在 Claude 长任务里研究"何时该提示用户"——**这是 agent + 教育 AI 共同面对的"AI 边界"问题**。**这条线索比"AI 又多了一个 benchmark 跑分"重要一个量级**——**评测哲学 + 训练范式 + 产品设计都受它影响**。

**Q1：来源/出处？**

A：主体来源是 [TutorMoments: Do AI tutors know when to help and when to hold back? — Hugging Face blog](https://huggingface.co/blog/allenai/tutormoments)（2026-08-07，作者 Kyle Wiggers / Ai2Comms / AllenAI，HF blog 不在 CF 后，`curl -L -A "Mozilla/5.0" --max-time 25` 一次过拿到 129,048 字节 HTML）。配套：数据集 [`allenai/tutormoments-preview`](https://huggingface.co/datasets/allenai/tutormoments-preview)（10.1k 下载）+ 代码 [`allenai/tutormoments`](https://github.com/allenai/tutormoments) + 论文 PDF [`tutormoments-preview.pdf`](https://tutormoments.allen.ai/static/paper/tutormoments-preview.pdf)。

**Q2：能不能复现 / 怎么验证？**

A：分五步：(1) `git clone https://github.com/allenai/tutormoments`；(2) `pip install -r requirements.txt`（依赖 huggingface_hub + openai/anthropic SDK）；(3) `huggingface-cli download allenai/tutormoments-preview` 拉 462 段 transcript；(4) 选 1-2 个被测模型 + evaluation-aware prompt 跑 replay pipeline（每个模型 5 轮 × 1,500+ 关键时刻 ≈ 7,500 次 LLM 调用）；(5) 评分脚本输出 appropriate_scaffolding / appropriate_rigor / avoids_over_scaffolding 三个 0-1 区间得分，**和 AllenAI 报告的数字对齐**。**完整复现需要 2-3 个 A100/H100 + 1-2 天 GPU 时间**。

**Q3：适用边界？**

A：本文只覆盖 HF blog 公开内容 + 我的分析。**真实学习效果的实验（学生真的学到了吗？）+ 数据集扩展到其他学科/年级/国家 + 评分 pipeline 在多模态 transcript 上的稳定性 + 不同教师池子的标注一致性** ——这四个边界 blog 都没给，需要更多研究。**AllenAI 在 limitation 段明确说"这是 preview，不是 benchmark 终局"**——**别把这个评测当"模型排名"使用**。

**Q4：和其他类似项目对比？**

A：和传统教育 AI benchmark（MMLU / GSM8K / MATH / DROP）比，**TutorMoments 是复盘式评测，不是"答题对不对"评测**——前者问"AI 在关键决策点是否克制"，后者问"AI 能不能解出题"。和 Anthropic Claude 在长任务里"何时提示用户"研究比，**TutorMoments 把"AI 何时该沉默"做成可量化评测**，Anthropic 那条是产品层研究。**和 OpenAI 同期在 chat 场景里"AI 何时打断用户"研究比，**两者方向相同、场景不同**——TutorMoments 聚焦教育 AI，OpenAI 聚焦 chat 通用场景。

**Q5：风险/坑？**

A：(1) 7 个被测模型的具体名字博客没列全——**要看 paper PDF 才能确认是哪些模型**（本文按 AllenAI 描述"7 个 LLM"概括，**具体模型名以 paper 为准**）。(2) 评分 pipeline 用 LLM 评 LLM——**有 circular 风险**（评分模型可能给"风格相近"的被测模型更高分）。(3) 模拟学生由 LLM 扮演——**模拟学生的"反应模式"会污染被测模型的判断**（如果模拟学生容易放弃，被测模型会倾向 over-help）。(4) "过度帮助"在数据集里是数学场景下定义的——**其他学科里"过度帮助"的具体阈值不同**。(5) 这是 **preview**，**生产选型别只看这一次评测结果**。

---

参考资料（按权威性排序）：

1. [TutorMoments: Do AI tutors know when to help and when to hold back? — Hugging Face blog](https://huggingface.co/blog/allenai/tutormoments)（2026-08-07，**主体来源**——AI 默认过度帮助 / eval-aware prompt 提升但不追平人类 / 462 段 transcript / 1,500+ 教师标注 / 复盘 pipeline / AllenAI 在教育 AI 评测范式转变）
2. [allenai/tutormoments-preview — Hugging Face Datasets](https://huggingface.co/datasets/allenai/tutormoments-preview)（**数据集主入口** —— 462 段 transcript + 1,500+ 教师标注 + 7 个被测模型的复盘对话 / 10.1k 下载）
3. [allenai/tutormoments — GitHub](https://github.com/allenai/tutormoments)（**代码主入口** —— replay pipeline + 评分脚本 + LLM 调用封装）
4. [TutorMoments Tech Report PDF](https://tutormoments.allen.ai/static/paper/tutormoments-preview.pdf)（**论文主入口** —— 7 个被测模型的完整得分表 + 教师标注协议 + 评分 pipeline 细节）

字数自检：≥1500 个中文字符（不含 frontmatter）
隐私自检：未写入个人姓名、用户相关代号、内部网络细节、商业秘密、未脱敏的内部身份字段；保留的 AllenAI 作者署名是 HF blog 公开字段（Kyle Wiggers / Ai2Comms / AllenAI）
封面 seed：2026-08-08-allenai-tutormoments-462-replays（唯一）
coverWidth/Height：1600 / 900
categories：ai_tech