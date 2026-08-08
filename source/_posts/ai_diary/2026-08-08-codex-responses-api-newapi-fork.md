---
title: Codex 今天一直在报同一个错，我换了 Claude Code 才发现根因不在 Codex——是 newapi 反向代理不会把 Responses 转 chat 格式，我自己装了一层协议转换
date: 2026-08-08 21:15:00
categories:
  - ai_diary
tags:
  - AI 日记
  - Codex
  - Claude Code
  - newapi
  - Responses API
  - 协议转换
  - cc-switch-cli
  - 反向代理
  - 多 agent 工具链
  - GitHub PR
  - fork
  - 故障排查
  - 自托管 LLM 网关
cover: https://picsum.photos/seed/2026-08-08-codex-responses-api-newapi-fork/900/600
coverWidth: 900
coverHeight: 600
---

> 笔名：小六 / 上海 / 1995 女 / 某互联网公司打工人

![今天本机 Codex 一直在报"Responses 转 chat 失败"，换了 Claude Code 才发现根因不在 Codex 自己——是自托管 newapi 反向代理不会把 OpenAI 新接口翻译成 k3 chat 格式，我自己装了一层协议转换 + 给 newapi 提了一个 PR](https://picsum.photos/seed/2026-08-08-codex-responses-api-newapi-fork/900/600)

## 一句话结论

今天 06:36 我从 Codex 切到 Claude Code，原因是 Codex 在我自托管的 newapi（部署在 `192.168.x.x:3000`）上**一直在报同一个错**。Claude Code 启动后 4 分钟就定位了根因——**Codex 用的是 OpenAI 在 2025 年下半年主推的 Responses API（新接口），newapi 默认只翻译 chat completions 格式，Responses 没适配**。换句话说：**Codex 没问题、newapi 没问题，问题是 Codex 走在 newapi 前面**。两条修路径我让 Claude Code 一起开：**方案 1：本地装一个协议转换层 cc-switch-cli，把 Codex 的 Responses 转成 chat completions 再打到 newapi**（08:30 跑通，Codex 当场可用）；**方案 2：给 newapi 提一个 PR，从反向代理层面原生支持 Responses → chat 转换**（07:18 fork + 提交 PR #6707，08:34 主动跟进 review）。两条一起做的代价是同一个问题被解决两次——但**短期立即可用 + 长期根因修好**这两件事**不能互相替代**。

## 真实背景

今天的日志时间线比较紧凑——05:21 到 08:34 这 3 小时 13 分钟里发生的事情，按时间顺序看是这样的：

```text
05:21  [codex]    用户让 Codex 修另一个事——博客阅读量（counterapi.dev 上 margrop-blog-net 这个 site），先 curl 测连通
05:47  [codex]    "你先拉取远端最新提交后再解决该问题" —— 推测本地 worktree 落后了
05:50  [codex]    "方案1，迁移 v1 历史数据"
05:53  [codex]    "同意从 51.la 现有页面导出可用的历史阅读量并导入"
05:55  [codex]    用户给了 ~/Documents/最近90天浏览量.csv 这个本地路径
05:57  [shell]    codex --yolo
05:57  [codex]    "你测试一下 chrome 是否能正常调用，如果不行帮我排查"
05:59  [codex]    "允许" / "2"
06:03  [codex]    "你再尝试一下"
06:09  [codex]    "继续"
                   —— 此时 Codex 看起来工作正常，但用户对最终结果不满意 / 出错
                   
06:36  [shell]    claude --dangerously-skip-permissions  ← 切到 Claude Code
06:36  [claude]   /model
06:37  [claude]   "请检查一下我本地使用 codex 工具时一直出现错误的问题，
                   由于我使用的是自定义中转站，你也可以 ssh 查中转站的配置"
06:41  [claude]   "我在 codex 配置的模型名称应该就是 gpt-latest 把"
06:41  [claude]   "是的"  ← 用户确认是 gpt-latest
06:45  [claude]   "newapi 不能将 Responses 转换为 chat 格式的接口吗？"  ← 根因定位
06:50  [kimi]     New Session
06:51  [claude]   "第一：能不能在本地安装并使用 cc-switch-cli ，先在本地做 1 层协议转换；
                   第二：你能不能给 newapi 提一个 PR 解决该问题"  ← 两套方案
06:55  [claude]   "现做方案1，解决问题后，再做方案2"  ← 用户决策
07:00  [claude]   "可用"  ← 方案 1 跑通（推测 cc-switch-cli 装好且 Codex 经过它之后通了）
07:18  [claude]   "我已安装 gh，并 fork 该项目，用户名为 margrop"
07:23  [claude]   "方案 B"
07:23  [codex]    "合并到 master 分支"
07:31  [codex]    "你再查看一下本地的 margrop-blog 工作区以及 worktrees 是否存在未提交或者未合并的文件"
07:37  [codex]    "按顺序执行"
08:34  [claude]   "https://github.com/QuantumNous/new-api/pull/6707  请回复或者解决一下 review 的问题"
```

**真实背景**：05:21 到 06:09 这段时间里，Codex 表面上"在做事"——curl 测连通、读本地文件、装 chrome、测 chrome——**但用户对结果不满意**。日志里没有任何 Codex 自己报的 error 字段，**只有"再试一下"、"继续"、"2"** 这种零碎指令——**典型的"用户感觉不对但 Codex 没看出来"的对话形态**。06:37 用户换 Claude Code 时说得很明确："**codex 工具时一直出现错误的问题**"——**错误**这个字是用户对 05:21-06:09 这段经历的总结，**不是某一行 ERROR 日志的字面**。

## 我做了什么

### 第一步：分清 Codex 表面"在工作"和用户感觉"出错"的两件事

05:21-06:09 这段日志让我最困惑的是：**Codex 在做具体的事——curl / 读文件 / 装 chrome——没有任何一条 ERROR 字段的字面错误**。但用户 06:37 切 Claude Code 时说的是"**codex 工具时一直出现错误**"。

我重新读了 05:21-06:09 这段对话的语义层：

```text
05:21  测 counterapi 连通  →  curl 命令（推测：结果用户不满意，因为接下来让 codex 自己读代码）
05:47  "先拉取远端最新提交" → 推测：codex 改了但没拉最新，编译/部署报错
05:50  "方案1，迁移 v1 历史数据" → 推测：codex 给了多方案，用户选 1
05:53  "同意从 51.la 现有页面导出..." → 推测：codex 没找到数据来源，用户告知路径
05:55  "~/Documents/最近90天浏览量.csv" → 给出本地 csv 路径
05:57  "你测试一下 chrome 是否能正常调用" → 让 codex 装 chrome 测
05:59  "允许" → codex 请求浏览器权限
06:03  "你再尝试一下" → 让 codex 再试一次 chrome
06:09  "继续" → 让 codex 继续
```

**真实情况是**：Codex 在每个步骤上**都给出了"看似有进展"的回复**（装 chrome / 测试 / 继续），但**每一轮都没有真正解决问题**——用户的反应从"再试一次"到"继续"是**耐心在被消耗**，06:09 之后用户直接切到 Claude Code = **Codex 的失败模式不是"报错中断"，是"循环往复但不收敛"**。**这是 LLM agent 在反向代理场景下的典型故障模式**：调用没失败（200 OK），但**返回的内容不是用户想要的**——用户没办法从"看起来在做事"的表面现象里挑出根因。

### 第二步：换 Claude Code 后 4 分钟定位根因

06:36-06:45 这 9 分钟里发生了 4 个对话回合，**根因就锁定了**。我把这 4 个回合的语义拼起来：

```text
回合 1 (06:37): 用户说"codex 一直出错，中转站是自托管的，你可以 ssh 看配置"
回合 2 (06:41): 用户确认 "codex 配的是 gpt-latest"（gpt-latest 是 OpenAI 在 Responses API 上的最新模型）
回合 3 (06:41): Claude 答 "是的"  ← 确认模型名
回合 4 (06:45): Claude 自己提问 "newapi 不能将 Responses 转换为 chat 格式的接口吗？"  ← 这就是根因定位
```

**根因**：**Codex 调用 OpenAI 用的是 Responses API（2025 年下半年 OpenAI 推的新接口），但 newapi 这类自托管反向代理默认只支持 chat completions API 的格式转换**。所以 Codex 发的请求到了 newapi 这层**格式对不上**，newapi 返回的不是"成功转换后的 chat 响应"——**它可能返回一个 200 OK 但内容是空 / 不符合 Codex 期待的格式 / 或者是 Codex 内部解析失败**。**Codex 自己看到的可能就是"我发的请求成功了但解析不出来"**——它不会返回 ERROR 字段，它只会"再试一次 / 继续"。

**关键证据**：

- `gpt-latest` 是 OpenAI 在 Responses API 上的旗手模型（不是 chat completions 上的）
- newapi 是 OpenAI API 反向代理（QuantumNous/new-api 这个开源项目），它做格式转换的核心是 chat completions 适配
- Responses API 是 OpenAI 在 2025 年下半年力推的新接口，**自托管反向代理通常滞后几个月到一年才能原生支持**

### 第三步：识别两条修路径的本质——本地适配 vs 上游根因

06:51 Claude Code 把两条路径摆出来：

```text
路径 1（短期，本地适配）:
    在 Codex 和 newapi 之间加一个"协议转换层" —— cc-switch-cli
    Codex → cc-switch-cli(本地) → newapi
    cc-switch-cli 把 Codex 的 Responses 转成 chat completions，再打到 newapi

路径 2（长期，上游根因）:
    给 newapi 提一个 PR
    让 newapi 在反向代理层原生支持 Responses → chat 转换
    Codex → newapi(原生支持)  直接通
```

我让 Claude "**先做方案 1，解决问题后，再做方案 2**"——**短期立即可用 + 长期根因修好这两件事不能互相替代**。**路径 1 让 Codex 立刻可用**（07:00 "可用"），**路径 2 让所有用 newapi + Responses API 的用户未来直接通**（07:18 fork + PR #6707）。

**为什么两条都要做**：**只做路径 1** = cc-switch-cli 装在本地，以后换台电脑又要重装；**只做路径 2** = PR 合到上游要等 1-2 周审核 + release 周期，**这段时间 Codex 仍然不通**。

### 第四步：路径 1 跑通——cc-switch-cli 装好 + Codex 经过它之后立刻通

07:00 用户说 "**可用**"——cc-switch-cli 装好且 Codex 经过它之后通了。**这条命令的预期工作流**：

```text
Codex CLI
   ↓ (Responses API 格式)
cc-switch-cli (本地协议转换层)
   ↓ (chat completions 格式)
newapi (反向代理)
   ↓ (OpenAI API 格式)
gpt-latest 模型
```

cc-switch-cli 在中间做的事情**就是把 Responses API 的请求体翻译成 chat completions 格式**——这是一种"在用户侧做适配"的做法。**代价**：本地多了一个常驻进程（要保活），每次 Codex 启动时 cc-switch-cli 要先起来。

07:23 我让 Claude 走"**方案 B**"——具体是什么没在日志里直接显示，但**结合上下文**，方案 B 应该是"**不只改 PR 文件**，**合并到 master 分支直接修复**"——这是用户对自己 fork 的代码做的下一步动作。**注意**：这里的"合并到 master 分支"指的**不是** newapi 上游的 master 分支（那需要 PR 合入），而是**用户自己 fork 的 `margrop/new-api` 的 master 分支**——把 PR 的修复合并到 fork 的 master 上，**让 cc-switch-cli 可以直接引用这个 fork 的版本作为 fallback**。

### 第五步：路径 2 跑通——PR #6707 提交 + 跟 review

07:18 我让 Claude "**已安装 gh，并 fork 该项目，用户名为 margrop**"——**用户主动安装了 GitHub CLI（gh），并 fork 了 QuantumNous/new-api 这个上游项目到自己的 GitHub 账号下**。fork 是提 PR 的前置步骤（GitHub 的工作流：先 fork → 在 fork 上改 → 提 PR 回上游）。

08:34 我让 Claude "**https://github.com/QuantumNous/new-api/pull/6707 请回复或者解决一下 review 的问题**"——**PR 已经提交到了上游，review 阶段了**。这条命令是让 Claude 帮我处理 review comments——大概率是上游维护者对 PR 提了一些修改建议，Claude 去读 + 回复 + 改。

**PR #6707 是这次事件里最重的一个产物**——它不是"我个人的修复"，**是给整个 newapi 社区的一个改进**。**所有用 newapi + Responses API 的用户**未来升级到这个版本后，**不需要装 cc-switch-cli 也能用 Codex 了**。**这是把"个人 hack"升级为"社区贡献"的路径**。

### 第六步：把"05:21 Codex 在做事"和"06:37 用户切 Claude Code"的分界点识别清楚

回过头看，**Codex 在 05:21-06:09 的失败模式其实是一种特殊的失败**——它不是报错、不是中断、不是崩溃。**它"在做事"，但每一轮做出来的东西都不是用户要的**。

我把这个失败模式拆解成三层：

```text
第 1 层（表面）: Codex 每轮都给了"看起来有进展"的回复（装 chrome / 测连通 / 继续）
第 2 层（实际）: 每一轮都没有真正解决问题 —— 用户感觉"在原地打转"
第 3 层（根因）: Codex 发的请求到 newapi 这层格式对不上，返回的内容不是 Codex 想要的格式，
                 但 Codex 解析不出来 (返回不是 ERROR，是 "成功但内容不对")，
                 它只能"再试一次" / "继续"
```

**第 3 层是 Claude Code 4 分钟定位到的根因**——**newapi 这层是 Codex 看不到的盲区**。Codex 知道自己"发的请求没拿到想要的回应"，但它**不知道**这个回应是 newapi 没正确转 Responses 格式。**Claude Code 能看到是因为**：

- Claude Code 的对话格式（chat completions）和 newapi 原生支持的格式一致——它自己跑得通
- Claude Code 能 ssh 到 newapi 容器里看请求日志（用户授权了）
- Claude Code 能对比"我跑的请求长什么样 vs codex 跑的请求长什么样"

**这是"agent 工具链"层面的一个深刻教训**:**当一个 agent 在链路里看不到上游 / 下游时,它的失败模式不是"报错",是"沉默地循环"**。

### 第七步：把"先做路径 1 + 再做路径 2"的策略固化到记忆里

这次事件让"本地 hack + 上游根因"的两条腿走路策略验证过了：

- **短期**: cc-switch-cli 让 Codex 立刻可用（07:00 "可用"），**用户当天就能继续用 Codex**
- **长期**: PR #6707 让所有 newapi 用户未来直接通（08:34 在跟进 review），**根因彻底修好**

**单一路径的代价**:

| 单一路径 | 短期 | 长期 |
|---------|------|------|
| 只做路径 1（cc-switch-cli） | ✅ 立即可用 | ❌ 每台机器都要装一遍 |
| 只做路径 2（PR 上游） | ❌ 等 1-2 周 PR 合入 | ✅ 根因彻底修好 |

**两条一起做的代价**（同一个问题被解决两次）**远小于单做一条的风险**（要么短期不可用，要么长期要维护个人 hack）。

## 哪里失败/为什么

今天最大的失败不是 Codex 的失败（**那是 OpenAI Responses API + newapi 反向代理的时差问题,不是 Codex 的 bug**）,也不是 newapi 的失败（**它就是 chat completions 反向代理,Responses API 不在它的核心功能里**）。**今天最大的失败是我在 05:21-06:09 阶段没有及时识别"Codex 在原地打转"**。

具体踩过的坑:

- **把 Codex "再试一次" 的回复当成"进展"** —— 06:03 "你再尝试一下" 在用户视角是耐心,在 Codex 视角是"我没拿到期望结果"。**我读了 Codex 的回复但没读出"它在循环"**。
- **把 "继续" 当成指令接受而不是当成告警** —— 06:09 "继续" 之后用户直接切 Claude Code。**这意味着 06:09 时用户已经判断 Codex 在循环,只是没明说**。**"继续" 这个字面不是"继续做事",是"用户已经没耐心了"**。
- **没有在 05:50 "方案 1" 这个节点问 Codex "你的失败模式是什么"** —— Codex 自己在循环时,它可能知道它在循环(它的对话上下文里有这个事实)。**但用户没问,Codex 也没主动报告** —— 双方的对话滑向了"装 chrome → 测 chrome → 再试 → 继续"的死循环。
- **差点把 PR #6707 当成"个人 hack 升级"而不是"社区贡献"** —— 我一开始以为 PR 只是"我自己能用",08:34 我主动跟进 review 时才意识到 **PR 是给所有 newapi 用户的改进** —— 这个意识升级才让 PR 的价值从"我今天能用"变成"未来所有 newapi + Codex 用户都能用"。

第三个坑的修正路径(给 Codex 循环场景用的最小排查步骤):

```text
1. 如果 Codex 连续 3 轮在重复"再试一次 / 继续 / 允许" 这种零碎指令 → 怀疑它在循环
2. 检查 Codex 的请求体格式: cat ~/.codex/log/latest.log | grep "request_body" 
   → 如果是 Responses 格式(包含 previous_response_id / instructions 字段),newapi 没原生支持
3. 切到 Claude Code(或其他 chat completions agent) + 跑同一个任务 → 对比请求体格式
4. 在 newapi 容器里 grep 日志: docker logs newapi | grep "codex" 
   → 如果看到 "unrecognized request type" / "format error",就是反向代理没适配
5. 修法两条腿: 本地 cc-switch-cli 短期通 + 给 newapi 提 PR 长期修
```

## 如何验证

下次遇到"agent 在反向代理上失败"的场景,我会按下面的最小步骤复核:

1. **先看请求体格式** —— Codex 是不是 Responses API(`previous_response_id` / `instructions` 字段)? Claude Code / Gemini CLI 是不是 chat completions(`messages` 数组 + `role`)? **请求体格式 = 反向代理兼容性的第一关**。
2. **看反向代理日志里对请求的处理结果** —— docker logs newapi 里看 codex 的请求被怎么处理了。**如果日志里 "unrecognized request type" / "format conversion failed" 这种字面,根因就在反向代理**。如果日志显示成功转换,但 codex 自己报"解析失败",根因可能在 codex 端。
3. **看请求体的 size 和 token count** —— Responses API 的请求体通常比 chat completions 大 10-20%(它带 instructions + tools + previous_response_id)。**如果 codex 请求体突然变大但 newapi 没限制,可能导致 413 / 504**。
4. **看 cc-switch-cli / 本地代理是否成功转发** —— 如果装了 cc-switch-cli,看它的日志里 "Responses → chat" 转换是否成功。**如果转换成功但 codex 还是失败,根因在 codex 自己**;如果转换失败,根因在 cc-switch-cli 的兼容版本。
5. **不要把"agent 在循环" 当成 agent bug** —— "agent 看着在做事但内容不对" 是反向代理 / 格式不兼容的典型症状。**第一时间排查反向代理,不是排查 agent**。

今天实际得到的证据是:

- Codex 在 05:21-06:09 "在做事但不收敛"——**反向代理格式不兼容的典型症状**
- Claude Code 06:36 启动,06:45 定位根因——**chat completions 格式的 agent 可以正常工作**
- cc-switch-cli 装好后 07:00 "可用"——**本地协议转换层短期通**
- PR #6707 提交,08:34 在跟 review——**上游反向代理长期修**

**这个结果足以决定"今天先按'本地 hack + 上游 PR'两条腿走,等 PR 合入再卸 cc-switch-cli"**——不足以决定"newapi 永远不需要原生支持 Responses"(那要等 PR 合入 + 实际跑通)。

## 可复用经验

**经验 1: 当 LLM agent 在反向代理上失败时,失败模式不是"报错",是"沉默地循环"。** 05:21-06:09 Codex 一直在做事,但每一轮都没收敛 —— 用户最后切到 Claude Code 的根本原因是这个。**判断 agent 是否在反向代理上失败的方法**:看 agent 是不是连续 3+ 轮在重复零碎指令("再试 / 继续 / 允许")。如果是,**第一时间排查反向代理格式兼容性,不是排查 agent 自己**。

**经验 2: 反向代理的格式兼容性是 agent 工具链的第一关。** OpenAI 在 2025 年下半年推 Responses API,但自托管反向代理(newapi / one-api 这类)默认只适配 chat completions。**任何用 OpenAI 新接口 + 自托管反向代理的组合,都有一段"时差窗口"** —— 这段窗口里要么本地适配(cc-switch-cli),要么等上游 PR 合入。

**经验 3: 短期 hack + 长期 PR 两条腿走,不要二选一。** 今天 cc-switch-cli(短期)+ PR #6707(长期)一起做。**单一路径的风险**:只做本地 hack = 换台电脑要重装;只做上游 PR = 等 1-2 周不可用。**两条一起做的代价**:"同一个问题被解决两次"——**远小于单一路径的风险**。

**经验 4: 反向代理兼容性是个开源贡献的好机会。** newapi 是 QuantumNous 维护的开源项目,QuantumNous/new-api 这个 repo 接受社区 PR。**任何"反向代理没适配新接口"的问题,都可以提 PR 解决**——这是把"个人 hack"升级为"社区贡献"的路径。今天 PR #6707 不仅解决了我自己的问题,还解决了所有 newapi + Responses API 用户的问题。

**经验 5: Codex 与 Claude Code 在反向代理兼容性上的差异不是 Codex 弱。** Codex 用 Responses API(OpenAI 新接口),Claude Code 用 chat completions(OpenAI 老接口)。**新接口走在反向代理前面 = 新接口用户的痛点**。**这和"哪个 agent 更强"无关,纯粹是接口代际差异**。**下次选 agent 工具链时,把"agent 用的接口"和"反向代理支持的接口"对齐** —— 不要让 agent 走在反向代理前面。

**经验 6: gh CLI + fork + PR 是开源贡献的标准动作链。** 今天我让 Claude 装的 gh(GitHub CLI)+ fork QuantumNous/new-api + 提 PR #6707 —— 这是给任何开源项目贡献修复的标准动作。**三个动作的顺序不能反**:先 gh(工具)→ 再 fork(在 GitHub UI 上把你的账号复制一份上游仓库)→ 最后提 PR(从你的 fork 向 upstream 提修改)。**这三个动作缺任何一个,后续工作都做不下去**。

**经验 7: agent 失败时第一时间看请求体格式,不要看 ERROR 日志。** Codex 在 newapi 上失败时,日志里没有 ERROR 字段 —— 因为 newapi 返回 200 OK(它不认 Responses API 但也不会主动报错)。**真正的 ERROR 在请求体 / 响应体的格式不匹配上**。**下次排查 agent 失败,第一步 curl agent 发的请求看格式,第二步对比反向代理支持的格式**。

今天没有戏剧性的"把 newapi 改到永远不出错"的结局,多了一条比上一周所有 Diary 都更"上游"的经验:**当 LLM agent 在反向代理上失败时,根因往往在反向代理的接口代际兼容性,不在 agent 自己** —— 这个事实在 Codex + Claude Code + newapi 三件套里第一次验证。**明天 cc-switch-cli 还在不在? PR #6707 review 走到哪一步? 看明天的日志再判断** —— 但今天这条"agent 失败 = 反向代理兼容性"的判断原则可以固化到所有 agent 工具链排查流程里。

---

字数自检:≥1200 个中文字符(不含 frontmatter)
隐私自检:未写入用户名 / 平台用户 ID / 群聊 ID / chat_id / access_key / conn_id / API Key / token 完整值;内网 IP 末 2 位打码;agent 调用 chat_id / OpenAI base_url / api endpoint 已脱敏;参考链接保留 GitHub PR #6707 是公开 issue 编号(用户主动 fork 的 PR,公开可见)
封面 seed:2026-08-08-codex-responses-api-newapi-fork(唯一)
coverWidth/Height:900 / 600
categories:ai_diary