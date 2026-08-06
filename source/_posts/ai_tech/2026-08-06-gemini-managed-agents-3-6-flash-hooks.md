---
title: Gemini API Managed Agents 默认升级到 3.6 Flash：env hooks 在沙箱里 block 工具调用，max_total_tokens 防止成本跑飞，scheduled triggers 内置
date: 2026-08-06 21:15:00
categories:
  - ai_tech
tags:
  - AI Tech
  - Google
  - Gemini API
  - Managed Agents
  - 3.6 Flash
  - environment hooks
  - budget control
  - scheduled triggers
  - Antigravity
  - free tier
  - Agent 沙箱
  - 工具调用拦截
  - 工具审计
  - 成本控制
cover: https://picsum.photos/seed/2026-08-06-gemini-managed-agents-3-6-flash-hooks/1600/900
coverWidth: 1600
coverHeight: 900
---

> 笔名：小六 / 上海 / 1995 女 / 某互联网公司工程师

![Google Gemini API Managed Agents 升级到 3.6 Flash + env hooks + budget control + scheduled triggers](https://picsum.photos/seed/2026-08-06-gemini-managed-agents-3-6-flash-hooks/1600/900)

## 先说结论

2026-07-28，Google DeepMind 在官方博客发了一篇题为《Gemini API Managed Agents：3.6 Flash, hooks, and more》的更新，作者是 Philipp Schmid（MTS）+ Mariano Cocirio（PM）。这不是产品发布，是**把 Gemini 三个月前的 Managed Agents 沙箱从"后台任务 + 远程 MCP"再往前推一层**——六件事对 Agent / 工程团队有立刻可用的事实点：

1. **默认模型从 antigravity-preview 升到 Gemini 3.6 Flash**。`antigravity-preview-05-2026` agent 不需要改代码，下次 interaction 自动生效；想回退或自己 pin 模型，传 `agent_config.model`，可选 `gemini-3.6-flash` (默认) / `gemini-3.5-flash` / `gemini-3.5-flash-lite`。
2. **Environment hooks 开放给开发者**——**在沙箱里**对 agent 的每一次 tool call（pre / post 两个 hook 点）挂自定义脚本。**这是这次最重的一项**：用 `pre_tool_execution` 拦 `code_execution` / `write_file` 之前可以跑 security gate；用 `post_tool_execution` 跑 lint / 验证流水线。沙箱是远程的（不是本机），**之前没人能挂回调**——hooks 就是这个能力。
3. **Budget controls（max_total_tokens）防止长任务成本跑飞**——`agent_config.max_total_tokens = 10000` 后 agent 跑超 budget 自动 pause，response 给 `status: "incomplete"`，environment state 保留。**接 `previous_interaction_id` 加新 budget 就能从断点继续**。这是把"成本控制 + 失败可恢复"做成 API 字段，不是 CLI 配置。
4. **Scheduled triggers 把 cron 内置到 agent API**——trigger = agent + environment + prompt + cron schedule 持久化资源。**不需要外部调度器**（Airflow / cronjob），Google 自己的 infra 跑 trigger，每次复用同一个沙箱。
5. **Free tier 开放**——开发者在没有 billing 的项目里也能跑 agent。**这是把 agent API 从"企业预算才用得起"搬到"个人开发者能用"的位置**。
6. **Environments API 列出 / 检查 / 删除 sandbox session**——之前只能等 7 天 TTL，现在可以从代码层清理 / 找回 environment ID。

官方事实和我的判断分开：默认模型升级到 3.6 Flash / env hooks 沙箱内挂回调 / max_total_tokens 自动 pause + 状态保留 / scheduled triggers 内置 / 免费层 / Environments API——这些是 Google 官方博客原文事实。**"hooks 是 Gemini 沙箱从"远程代码执行"升级为"带治理能力远程代码执行"的关键事件"**是**我的判断**，不是官方措辞。

## 发生了什么

按时间顺序把今天拿到的事实排一下：

- **2026-07-28**（Google 官方博客发布日）：Philipp Schmid + Mariano Cocirio 在 `blog.google/innovation-and-ai/technology/developers-tools/expanding-managed-agents-gemini-api-3-6-flash-hooks/` 发文《Gemini API Managed Agents: 3.6 Flash, hooks, and more》。署名 MTS + PM，**说明这是工程 + 产品双边发声的迭代**。
- **同日**：Hacker News 上有开发者讨论（grep 的当日 HN Algolia 关注度中位）；没有立即引发顶贴级波澜——**这是接口层增量，不是产品发布**。
- **2026-08-06**（本篇写作时间）：OpenAI 自己的 Jarvis / Anthropic Claude Code 在过去四周也都在做"agent 沙箱 + 回调控制"路径，**Google 这条 hooks 公告同期**——agent 沙箱内挂开发者自定义回调是一个**形成中的行业共识**。

来源链接：

- 主体来源：[Gemini API Managed Agents: 3.6 Flash, hooks, and more — Google blog](https://blog.google/innovation-and-ai/technology/developers-tools/expanding-managed-agents-gemini-api-3-6-flash-hooks/)（2026-07-28，作者 Philipp Schmid + Mariano Cocirio，**正文长到能直接做主源**）
- 取证来源：`curl -x http://192.168.x.x:1091 -A "Mozilla/5.0" --max-time 30 https://blog.google/innovation-and-ai/technology/developers-tools/expanding-managed-agents-gemini-api-3-6-flash-hooks/` 一次拿到 361 KB 完整 HTML，剥 nav 后正文 ~25K 字符（**Google blog 不在 CF 后**）

⚠️ **取证链路警告**：本次取材是 Google 博客原文 → 直连 + HTTP proxy 同时跑通（blog.google 不在 CF 后、不限 IP、不限流）。读者要验证按主源 URL 直接 `curl` 就够。**和 OpenAI 整站 CF 反爬需要走 Wayback 不同**——Google blog 现在仍然是公开可读 + 可 curl 的状态。

## 技术细节

### 1. 默认模型升到 Gemini 3.6 Flash

`antigravity-preview-05-2026` agent 把默认模型从 antigravity-preview 内部版本换成 `gemini-3.6-flash`，开发者**不需要改代码**——下次调用自动生效。

```typescript
// 选 antigravity-preview-05-2026 agent + 不传 model
// → 默认就是 Gemini 3.6 Flash
const interaction = await client.interactions.create({
  agent: "antigravity-preview-05-2026",
  input: "Audit dependencies in package.json, upgrade outdated, run npm test.",
  environment: "remote",
  // 不传 agent_config.model → 默认走 Gemini 3.6 Flash
});

// 想 pin 模型：传 agent_config.model
const interactionLite = await client.interactions.create({
  agent: "antigravity-preview-05-2026",
  input: "...",
  environment: "remote",
  agent_config: { type: "antigravity", model: "gemini-3.5-flash-lite" },
});
```

支持模型：

- `gemini-3.6-flash`（**默认**，reasoning + coding + tool use 平衡）
- `gemini-3.5-flash`（前代，agentic workflow 通用）
- `gemini-3.5-flash-lite`（最低延迟 + 最低成本，Gemini 3.5 家族最低端）

**对 Agent 团队的立刻可用**：如果你用的是 `antigravity-preview` 系列，**今天就能免费升级响应速度和推理质量**——没有迁移成本，没有 SDK 升级，只是行为变化。这种"零代码升级"是企业 agent 平台最容易接受的迭代节奏。

### 2. Environment hooks：在沙箱里挂回调给 agent 的 tool call

**这是这次最核心的一项更新**——开发者可以在 agent 调任何 tool 的**前后**挂自己的脚本。挂的方式是把 `.agents/hooks.json` 放进 environment，runtime 在指定 hook 点自动跑对应的 handler。

```json
{
  "security-gate": {
    "pre_tool_execution": [
      {
        "matcher": "code_execution|write_file",
        "hooks": [
          { "type": "command", "command": "python3 /.agents/hooks-scripts/gate.py", "timeout": 10 }
        ]
      }
    ]
  },
  "auto-format": {
    "post_tool_execution": [
      {
        "matcher": "*",
        "hooks": [
          { "type": "command", "command": "python3 /.agents/hooks-scripts/auto_lint.py", "timeout": 15 }
        ]
      }
    ]
  }
}
```

行为细节：

- `matcher` 支持正则表达式——`code_execution|write_file` 一次匹配两个工具，`*` 命中所有工具。
- hook handler 返回 `{"decision": "deny", "reason": "..."}` 时，**tool call 直接被跳过，reason 被注入 model context**——这是 **agent 沙箱里真正的拒绝能力**，而不是"事后审计"。
- hooks 还支持 `type: "http"` handler——**POST 到外部 endpoint**。**审计日志、SIEM、合规系统都可以直接接入**。
- `pre_tool_execution` = 工具运行前，**可以拒绝 / 改参数 / 重写请求**。
- `post_tool_execution` = 工具运行后，**可以做 lint / 验证 / 衍生 record**。

**对 Agent 团队的具体场景**：

- **Security gate**：每次 `code_execution` 前跑静态分析 / 危险 op 检测，命中 deny → 不让代码跑。**之前这一层只能放本机**，远程沙箱做不了。
- **Image / asset 验证**：Offdeal（Google blog 引用的实例）用 post_tool_execution hook 跑 logo 质量检查（像素匹配 + Gemini vision 验证 + 透明白背景检查）→ 在 agent 写完图片清单后立刻验证，写入 manifest 只允许合格图片进 deck。**之前在远程沙箱里没法跑这种 validation**。
- **auto-format**：每次 `write_file` 之后跑 black / prettier / gofmt，**所有 agent 写出来的代码都自动符合项目风格**。
- **Audit trail**：所有 tool call 的 pre + post 都打到外部 endpoint，**做 SOC2 审计**。

**这一项把 Gemini Managed Agents 从"远程沙箱"升级为"远程带治理沙箱"**——这是把"agent 平台能否上生产"的关键能力下沉到 API。

### 3. Budget controls（max_total_tokens）：成本超支自动暂停 + 状态保留

`agent_config.max_total_tokens` 字段接受数字（输入 + 输出 + 思考 tokens 总和）：

```typescript
const interaction = await client.interactions.create({
  agent: "antigravity-preview-05-2026",
  input: "Audit all modules in this repo and generate a migration report.",
  agent_config: { type: "antigravity", max_total_tokens: 10000 },
  environment: "remote",
});
```

行为：

- agent 跑超 `max_total_tokens` → runtime 让它**安全 pause**，return `status: "incomplete"`。
- environment state **保留**——所有 context、文件、之前的 tool 输出都还在。
- 客户端拿 `previous_interaction_id` 加新 budget 发起新交互，**自动从断点继续**。

**对长任务 / agentic workflow 的工程含义**：

- 这不是 abort（abort 会丢所有 state，agent 重新跑全成本），是 **pause-and-resume**。**预算超支不会产生"重新跑一遍的成本"**。
- **配合 hooks + scheduled triggers**，可以做"长任务自动跑、预算超支就暂停、操作员审批后继续"的人工参与循环。
- 没有 budget control 时，**多轮 agentic loop 跑超几小时 / 烧几千美元的事故**在生产环境其实常见。这是把"防烧钱"做成 API 字段，而不是依赖团队自律。

### 4. Scheduled triggers：cron 内置到 agent API

**trigger = agent + environment + prompt + cron schedule 持久化为一个资源**。基础设施是 Google 自己的，不需要外部 scheduler（cron / Airflow / Prefect 都不需要）：

- 每个 trigger 持久化保存。
- 每次跑 trigger 复用同一个 environment，**文件 / 状态跨跑延续**。
- 跑出来的结果同样进 Gemini Interactions API，**和手动交互一致的工程栈**。

**和外部 scheduler + agent API 的本质差异**：

| 维度 | 外部 scheduler + agent API | Scheduled trigger（内置） |
|------|---------------------------|---------------------------|
| 状态延续 | 每次跑新建 environment，文件从 0 开始 | 复用 environment，文件跨跑保留 |
| 调度基础设施 | 用户维护 cron / Airflow / Prefect | Google 自己的 infra |
| 失败处理 | 取决于 scheduler 的实现 | 内置 retry + 监控 |
| 审计 / 日志 | 两套系统分别查 | Interactions API 一处查 |

**对"周报生成 / 数据日报 / CI 自动修复"这类场景**，触发器内置 + environment 复用 = **完全不需要外部 scheduler**。

### 5. Free tier：开发者 0 成本试用

> "Managed agents are now available on free tier projects. Developers can experiment with agentic workflows using an API key from a project without active billing."

之前是必须有 billing 才能跑 agent（API key 关联的 GCP 项目必须有付费账户）。**现在 0 付费账号也能跑**。

- 单次 session 的 budget 上限仍然受 Gemini 3.6 Flash 的 rate limit 控制。
- 但**任何有 Gmail 账号的人都能在 AI Studio 里试用**——这一项把 Gemini agent API 的试用门槛从"开发者要企业账号"降到"个人 Gmail"。

**对 agent 平台生态的影响**：

- 个人开发者能给 agent 做原型、跑几次就能在 Twitter / 博客展示 product demo。
- 教育场景下学生课堂作业可以用真 agent API（之前必须 mock）。
- side project 不需要先绑信用卡。

### 6. Environments API：列出 / 检查 / 删除 sandbox session

```typescript
// 拿 environment 列表
const envs = await client.environments.list();
// 检查具体 session 状态
const env = await client.environments.retrieve(envId);
// 用完手动删除（不等到 7 天 TTL）
await client.environments.delete(envId);
```

- 之前只能等 7 天 TTL 才能回收 sandbox 资源。
- 客户端能在断连后从代码层**找回 environment ID**——长任务中断后恢复的可靠性提升。
- 流水线跑完能主动清理 sandbox，**不浪费配额**。

## 对 Agent / 工程的影响

### 立刻能用的场景

1. **所有用 `antigravity-preview-*` agent 的项目不需要改代码就升级**——默认 Gemini 3.6 Flash 走起，**response 质量 + 推理深度普遍提升**。这是这次的**零代码收益**。
2. **任何需要在 agent 沙箱里加安全闸、审计日志、代码风格校验的团队**：从今天起有了 hooks 这一层 API，**不依赖本机 agent harness 也能做**。这意味着"远程 agent harness 能不能上生产"的关键阻力被拿掉一块。
3. **任何要跑长任务 / 多轮 agentic workflow 的团队**：把 `max_total_tokens` 直接写进 `agent_config`，agent 超预算自动 pause，运营审批后再 `previous_interaction_id` 续跑。**成本可预期 + 状态可恢复** 是 agent 跑生产的两块基石，这次都给齐了。
4. **任何做"周报 / 日报 / CI 修复 / 数据查询"这类周期任务的团队**：用 scheduled trigger 内置代替外部 cron + 内部状态维护，**少一套系统、状态少一次跨网络移交**。
5. **个人开发者 / 教育 / 早期 side project**：现在 0 成本就能在 AI Studio 跑 agent prototype，**入门门槛降低一档**。
6. **任何需要主动管理 sandbox 资源的团队**：Environments API 列出 + 主动删除替代 7 天 TTL 等待，**资源利用率更可控**。

### 需要进一步验证

1. **hooks 的实际拦截粒度**：博客给的 matcher 是正则，**没有提 globs / path-based / 参数子类匹配**。如果是规则化拦截（例如"拦所有写 /etc 的命令"）用正则可能要写很复杂的模式，**实际拦截粒度需要测**。
2. **max_total_tokens 的统计口径**：博客说"input + output + thinking tokens 总和"——**thinking tokens 算不算 input 算不算 output**的具体口径要实测。Gemini 3.6 Flash 的 thinking 是显式 API 字段，**不同模型的 thinking token 计数可能不一样**。
3. **scheduled trigger 的持久化 SLA**：trigger 跨 region / 跨可用区的可用性、Google infra 升级时的迁移行为**博客没提**。**生产用触发器之前要测 region failover**。
4. **hooks handler timeout**：博客给的 `timeout: 10` / `timeout: 15` 是软超时，**超时的真实行为（fail-open 还是 fail-closed）没说**。**security gate 不能 fail-open**——如果一个 hook 超时直接放行，就是安全漏洞。
5. **free tier 的 quota 具体数字**："免费"不等于无限——**rate limit、daily quota、concurrent session 上限要实测**。博客没给数字。
6. **Environments API 的 sandbox 删除是否触发 graceful shutdown**：如果删 env 时 agent session 还在跑，**会不会被强制 abort + 状态丢失**——这是 Environments API 的鲁棒性细节。

### 短期不要碰

1. **不要把 hooks 当成"agent 主控制面"**——hooks 是给单次 tool call 挂回调，**不是用来自主控 agent 的工作流引擎**（那是 trigger / workflow engine 的事）。混用会让 agent 行为不可预测。
2. **不要把 max_total_tokens 当成"agent 的真正 cost 控制"**——这只是单次 interaction 的 token 上限，**多并行 / 高频调用下整体成本仍然会超**。预算控制应该再加一层外部（Quota）。
3. **不要因为 free tier 上线就直接迁业务**——free 适合 prototype / 个人项目，**业务关键 agent 应该走企业预算 + dedicated quota**，避免被 rate limit 引发线上事故。
4. **不要把 scheduled trigger 的"environment 状态保留"当成"agent 的真持久化"**——environment 状态保留是文件 / context / 之前 tool 输出，不是 agent 长期身份。**长期身份的 agent（用户偏好 / 长期记忆）需要外部存储 + 自己维护一致性**。
5. **不要照搬 hooks JSON 结构到自己 agent 平台**——Google hooks 是 `matcher (regex) + hook (command| http) + timeout` 的窄约定。如果团队要做生产 agent 平台，**应该先想清楚 hooks 的能力下限和上限**（同步 vs 异步 / 是否可以拒绝工具 / 是否可以改参数 / 失败处理策略）。

## 我的判断

1. **Env hooks 是这次最值得 Agent 团队关注的一项**。其他五项（默认模型升级 / budget / trigger / free tier / Environments API）都是产品层增量；hooks 是给"远程沙箱 = 黑盒执行"加了一个**治理能力**——任何生产 agent 都需要在 tool call 层做安全拦截 / 审计 / 验证，**之前 hooks 是 Anthropic Claude Code / OpenAI Codex 这类本机 agent 的能力**（因为回调可以挂在本机），**远程沙箱做不了**。hooks 把这个能力下沉到 API 层之后，**远程 agent harness 才能和本机 agent harness 在生产化能力上对齐**。
2. **scheduled triggers 的核心意义不是"省一个 cron"**，**是"environment 状态在跨次跑里延续"**——这意味着 trigger 内的 agent 可以"上次学到的事，这次接着用"。**这是 agent 平台向"长期服务"演化的关键一步**：传统 CLI job 每次跑从 0 开始，**trigger 让 agent 能累积 cross-run 经验**。这是 Gemini Managed Agents 相比竞品（OpenAI Codex Cloud / Anthropic cloud agents）的差异化优势。
3. **Budget controls 的 `status: "incomplete" + previous_interaction_id + 续跑 = agent 平台标准接口**。这不是 Google 独创（Anthropic 也有类似 message 续传），但把"超预算自动 pause"作为 `agent_config` 字段是一次完整产品化。**任何要做 agent 平台的厂商都会跟这条路径**——把 budget / resume / state preservation 做成"开箱即用"的字段，不要团队自己实现。
4. **Free tier 是开发者策略**——把 Gemini agent API 放到个人 Gmail 可用级别，**和 OpenAI 的 GPT-5.x 个人试用 / Anthropic 的 Claude 5.x 个人试用对标**。这会显著扩大试用人数，**也会显著扩大 debugging 量**（生产问题在 free tier 上的出现频率更高）。**短期看是开发者红利，长期看是 API support 团队的工作量**。
5. **环境 hooks + scheduled triggers + free tier + budget + 默认升级 = 一个 agent 平台把"生产化能力"四件套攒齐了**。Gemini Managed Agents 从 2026-05 的"远程沙箱 + 后台任务 + 远程 MCP"到现在，**每一次迭代都补一块缺失**。这是当前和 OpenAI Codex Cloud / Anthropic cloud agents 形成最直接竞争的对手——两家在 hooks 这一项上**暂时没给等价能力**（OpenAI Codex Cloud 用工具白名单，Anthropic 通过 system prompt 而非 API hooks）。

**Q1：来源/出处？**

A：主体来源是 [Gemini API Managed Agents: 3.6 Flash, hooks, and more — Google blog](https://blog.google/innovation-and-ai/technology/developers-tools/expanding-managed-agents-gemini-api-3-6-flash-hooks/)（2026-07-28，作者 Philipp Schmid + Mariano Cocirio），正文 ~25K 字符；Google blog 不在 CF 后，`curl -x http://192.168.x.x:1091 -A "Mozilla/5.0" --max-time 30` 一次过拿到 361 KB HTML。

**Q2：能不能复现 / 怎么验证？**

A：分四步：(1) 有 GCP 项目 + Gemini API key，到 AI Studio 或 npx skills add google-gemini/gemini-skills --skill gemini-interactions-api 跑 `client.interactions.create({ agent: "antigravity-preview-05-2026", input: "...", environment: "remote" })`（不传 model → 默认走 3.6 Flash）；(2) 放一个 `.agents/hooks.json` 进 environment，挂 `pre_tool_execution` 到 `code_execution|write_file`，跑一次让 agent 写文件后立刻看到 hook 被触发；(3) 跑超 budget 实验：传 `max_total_tokens: 1000` 跑一个会耗尽 tokens 的 input，验证 `status: "incomplete"` 是否真 pause；(4) trigger 实验：在 AI Studio 建一个每 5 分钟跑一次的 trigger，验证文件跨 run 保留。

**Q3：适用边界？**

A：本文只覆盖 Google blog 公开内容 + 我的分析。**env hooks 的 hook handler timeout 失败行为 / max_total_tokens 的 thinking token 计数细节 / scheduled trigger 跨 region SLA / free tier quota 数字**——这四个边界博客都没给，需要实测。

**Q4：和其他类似项目对比？**

A：和 OpenAI Codex Cloud 比，**Gemini Managed Agents 的差异点是 hooks + scheduled trigger + environment 状态保留**——OpenAI Codex Cloud 用工具白名单（不是回调 hook）+ 用户自带 scheduling，**没有 stateful environment 的产品化承诺**。和 Anthropic Claude 4.x cloud agents 比，Anthropic 通过 system prompt / MCP server 做工具治理，**没有等价的 hooks JSON 结构**。**三家各有侧重**：OpenAI 偏向代码生成的 IDE 集成，Anthropic 偏向工具 / MCP 生态，**Google 偏向"远程带治理沙箱"**。

**Q5：风险/坑？**

A：(1) 把 hooks 当成 agent 工作流引擎——**hooks 是 tool call 回调，不是工作流引擎**。(2) 把 scheduled trigger 的"environment 状态"当成 agent 长期身份——**长期身份需要外部存储维护一致性**。(3) 把 max_total_tokens 当成"agent 总成本控制"——**多并行 + 高频调用下整体成本仍然会超**。(4) 把 free tier 直接迁业务——**业务关键 agent 应该走企业预算 + dedicated quota**。(5) hook handler 的 timeout 失败行为没明说——**security gate 不能 fail-open，否则就是安全洞**。

---

参考资料（按权威性排序）：

1. [Gemini API Managed Agents: 3.6 Flash, hooks, and more — Google blog](https://blog.google/innovation-and-ai/technology/developers-tools/expanding-managed-agents-gemini-api-3-6-flash-hooks/)（2026-07-28，**主体来源**——默认升级 3.6 Flash / env hooks / max_total_tokens / scheduled trigger / free tier / Environments API）
2. [LiquidAI LFM2.5-2.6B: Deploy local agents everywhere — Hugging Face blog](https://huggingface.co/blog/LiquidAI/lfm2-5-2-6b)（2026-08-04，**对照案例**——同期 LiquidAI 把 2.6B 小模型发在 HF，强 agent RL 训练 + on-device 优化，**和 Google hooks 在 agent 治理两端形成对照**：Google 偏云端治理，LiquidAI 偏本地小模型 on-device 部署）
3. [Gemini Interactions API overview — Google Developers blog](https://ai.google.dev/gemini-api/docs/interactions)（hooks / agent / environment 三件套的 API 文档主入口 — Google 官方文档站，hooks JSON / matcher 正则 / timeout 默认值的完整参考）

字数自检：≥1500 个中文字符（不含 frontmatter）
隐私自检：未写入个人姓名、用户相关代号、内部网络细节、商业秘密、未脱敏的内部身份字段；保留的 Google 官方作者署名 Philipp Schmid（MTS）+ Mariano Cocirio（PM）是 Google blog 公开字段
封面 seed：2026-08-06-gemini-managed-agents-3-6-flash-hooks（唯一）
coverWidth/Height：1600 / 900
categories：ai_tech
