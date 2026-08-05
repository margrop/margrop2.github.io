---
title: OpenAI 把 GPT-Live 实时语音架构写在了一篇博客里：去掉 turn detector、Go 重写前端、WARP 把 6 次握手压到 1 次
date: 2026-08-05 21:15:00
categories:
  - ai_tech
tags:
  - AI Tech
  - OpenAI
  - GPT-Live
  - 实时语音
  - full-duplex
  - WebRTC
  - WARP
  - SPED
  - SNAP
  - KV cache
  - 流式推理
  - 异步委派
  - 上下文压缩
  - silent test
  - 工程笔记
cover: https://picsum.photos/seed/2026-08-05-openai-gpt-live-realtime-voice-six-months/1600/900
coverWidth: 1600
coverHeight: 900
---

> 笔名：小六 / 上海 / 1995 女 / 某互联网公司工程师

![OpenAI GPT-Live 实时语音架构：从 turn detector 去掉到 WebRTC WARP 6→1 RTT 握手](https://picsum.photos/seed/2026-08-05-openai-gpt-live-realtime-voice-six-months/1600/900)

## 先说结论

2026-08-03，OpenAI 在官方博客发了一篇题为《How we built a realtime system for responsive voice AI in six months》的工程笔记，作者是 Justin Uberti 和 Zahan Malkani（MTS）。这篇不是产品发布，是**把第三代语音系统 GPT-Live 从 turn-based 改造成 full-duplex 的整套架构公开写下来**——五件事对 Agent / 工程团队有立刻能用的事实点：

1. **去掉 turn detector，让语音模型自己决定何时说话**——以前的 cascaded 系统靠一个独立的小模型先判断"用户说完了"，再让大模型响应；现在 GPT-Live 是 full-duplex 模型，**边听边说**，turn detector 从音频路径里被移除。需要深度推理 / 工具调用时，**异步**委派给 GPT-5.5 等 frontier 模型，不打断对话流。
2. **媒体路径和应用逻辑物理隔离**——音频走专用 fast path，工具调用 / 业务逻辑走异步 RPC 边界。**慢工具调用只能延迟自己的结果，不能 stall 媒体流**。这条规则同时是性能规则和工程边界——应用可以换工具、改策略、改 backend，**不影响**负责音频流动的媒体前端。
3. **Go 重写前端，p95 = 旧系统 p50**——媒体前端和推理逻辑用 Go 重写，替代之前的 Python asyncio 实现。**新系统的 p95 等于旧系统的 p50**——单这一条就说明 Python 异步调度在长连接、流式音频上的抖动太大。
4. **WARP 把 WebRTC 6 次握手压到 1 次**——WebRTC 的 DTLS / ICE / SCTP / DCEP 子协议各自带 anti-DoS 机制叠在一起浪费往返，OpenAI 提了 WARP（WebRTC Abridged Roundtrip Protocol），用 SPED 把 DTLS piggyback 到 ICE，用 DTLS 1.3 加快握手，用 SNAP 预协商 SCTP，用预协商 data channel 跳过 DCEP。**媒体握手从 6 个 RTT 压到 1 个 RTT**。WARP 已经是 libwebrtc + Pion 都有实现的开放协议，提案走 IETF TSVWG。
5. **Silent test：流量比例 ramp-up，capacity 不能再用 GPU throughput 衡量**——生产环境影子跑 GPT-Live，初始只切一小部分 ChatGPT Voice 流量比例逐步放大。**长连接语音的 capacity 瓶颈不是 GPU 吞吐**，而是 CPU 侧流式 handler + 队列 + 网络路径——这意味着做语音推理的服务端，监控面板要加"并发 session 数 × 每帧守时率"维度，不只是 GPU 利用率。

官方事实和我的判断要分开：**去掉 turn detector / Go 重写前端 / p95 = 旧 p50 / WARP 6→1 RTT / silent test 流量比例 / capacity 不再是 GPU throughput / KV cache 失效 + 上下文 compaction = 一次 managed transition**，这些是 OpenAI 官方博客原文事实；**"GPT-Live 是 2026 年公开过的、最完整的实时语音架构笔记，它的工程取舍能直接喂给任何要做 voice agent 的团队"**是 **我的判断**，不是官方承诺。

## 发生了什么

按时间顺序把今天拿到的事实排一下：

- **2026-08-03**（OpenAI 官方博客发布日）：Justin Uberti 和 Zahan Malkani 在 `openai.com/index/continuous-voice-interaction-with-gpt-live` 发文《How we built a realtime system for responsive voice AI in six months》。文章署名 MTS（Members of Technical Staff），不是 PR 团队——这一点直接说明这是工程笔记，不是 marketing。
- **同日**：Hacker News 上有讨论但不在头版（今天头版是 OpenAI 反诉苹果、IBM 模型路由）。
- **2026-08-03 ~ 2026-08-05**：Hacker News 后续讨论和 sibling 媒体（如 The Verge / Ars Technica）跟进；本文取正文做主源。

来源链接：

- 主体来源：[How we built a realtime system for responsive voice AI in six months — OpenAI 官方博客](https://openai.com/index/continuous-voice-interaction-with-gpt-live)（2026-08-03，作者 Justin Uberti + Zahan Malkani）
- 取证来源：[Wayback Machine — openai.com/index/continuous-voice-interaction-with-gpt-live](https://web.archive.org/web/2026/openai.com/index/continuous-voice-interaction-with-gpt-live)（OpenAI 整站 Cloudflare 反爬，原始 URL `curl` / 浏览器直访均返回 CF challenge；归档缓存一次拿到 523 KB 完整正文）

⚠️ **取证链路警告**：本次取材是 OpenAI 原文 → 403 / CF challenge → Wayback 缓存拿到完整正文 → 用 `python3 -c` 剥 HTML 抽正文段落（剥离 script/style 后约 20,370 字符正文）。读者若要验证，按 Wayback URL 取，不依赖 OpenAI 当前 anti-bot 防御层。这条链路在 2026-08-04 那篇 OpenAI 反诉苹果博客也用过，**OpenAI 整站 CF 反爬是当前稳定的取证痛点**。

## 技术细节

### 1. 从 turn-based 到 full-duplex：turn detector 被从音频路径里移除

老 cascaded 系统的结构是 **speech-to-text → LLM → text-to-speech** 三段串行——每段都是 turn-based，每一段都会丢信息（语气、节奏、停顿）。speech-to-speech 模型把音频直接处理掉，但**还是靠 turn detector 决定何时开始推理**。turn detector 是个独立小模型，猜早了用户被截断，猜晚了响应迟钝。

GPT-Live 的关键决定是 **voice model 进入 full-duplex**：它边听边说，不依赖 turn detector 决定"是否轮到我了"。需要深度推理 / 工具调用时，**异步**把请求委派给 GPT-5.5 等 frontier 模型——委派在另一条路径上跑，结果流回 voice 模型。

架构原话：

> "GPT‑Live puts the voice model in control of the audio loop —— audio flows in and out of the model, while deeper reasoning and tool use happen asynchronously. The system’s primary job is to sustain an uninterrupted media loop."

**对做 Agent 的人来说这不是 voice 专属的事**：把"主对话流"和"异步委派"做物理隔离，是所有需要低延迟响应的交互系统通用模式。GPT-Live 把这件事写在 voice 上下文里，但同样的取舍适用于 **real-time chat / 实时游戏 NPC / 实时客服 / 实时陪伴 agent**——主响应永远先回，慢思考异步跑。

### 2. 媒体路径和应用逻辑物理隔离

架构里有两条独立的路径：

- **媒体 fast path**：客户端 ↔ voice model 之间的音频帧传输。**专用路径**，和业务逻辑完全隔离。
- **异步 RPC path**：工具调用、深度推理、对话持久化。**和媒体并行**，慢工具只能延迟自己的结果，**不能 stall 音频**。

原文：

> "An early decision we made was to specifically separate media flow from application and business logic. Audio moves between the client and the voice model on a dedicated fast path. Delegation, tool use, and other application work happen behind an asynchronous RPC boundary. A slow tool call or backend service can delay its own result, but cannot stall the flow of media."

这条规则的延伸含义：**媒体前端可以独立替换**——OpenAI 把前端从 Python asyncio 改成 Go 重写，p95 等于旧系统 p50。应用层换工具、改策略、改 backend，**不会影响负责"让音频动起来"的媒体前端**。这是工程边界，不是性能技巧——它让"实时性能"和"业务功能"成为两个独立可改的轴。

### 3. Go 重写前端 + WebRTC 作为传输基础

媒体前端用 Go 重写，替代之前的 Python asyncio。原文给的对比是**新系统的 p95 = 旧系统的 p50**——单这一条就说明 Python 异步调度在长连接、流式音频上有不可忽视的抖动。

传输层用 WebRTC：

- WebRTC 是低延迟媒体设计的；
- 能扛 packet loss、clock drift、client connection changes；
- 包晚到时 WebRTC 可以微拉伸音频防 gap，再短暂加速追回实时；
- 全链路最小化 buffer + block，给出亚秒级的对话响应。

原文：

> "We wrote the media frontend and inference logic in Go, replacing a previous Python asyncio implementation. This significantly improved the smoothness of frame delivery, with the new system’s p95 matching the previous system’s p50."

**对 Python 团队的工程含义**：长连接流式 + 每帧守时这类 workload，Python asyncio 不是不能做，但它的 GC / event loop 抖动会让 p95 显著高于 p50。**OpenAI 用 Go 重写前端不是因为 Go 性能"更快"，是因为 Go 的 p95/p50 比例更接近 1——这才是流式媒体的真正需求**。Python 团队要做同类系统，前端这层可能也得 Go 化。

### 4. Stateful inference：长连接 + 模型实例动态切换

长语音会话可能持续几分钟到几小时，context 持续增长，模型实例按需启动 / 关闭。OpenAI 的解法是 **seamless handoff**：要切换实例时，**新实例和旧实例并行 prefill**，新实例 ready 后一次 cut over，对音频流完全无感。

这个机制同时用来解决**上下文超长的问题**：当 context 增长接近模型上限时，OpenAI 把"上下文压缩"也当成一次 managed transition——旧实例继续对话，新实例带着压缩后的 context prefill，切换无感。

原文：

> "When a transition is needed, we can warm a replacement model instance alongside the existing one, prefill it with the current session context, run inference against both in parallel, and cut over when the new instance is fully ready. The same basic mechanism also supports dynamic context compaction."

**对做 KV cache + 长上下文的工程团队来说**，这是当前公开的最干净的方案——把"模型实例切换"和"上下文压缩"统一成同一种 managed transition，避免两套机制各管一段。**代价是同时跑两份实例的算力浪费**，但对长语音会话来说这个浪费远小于切流过程中产生的卡顿。

### 5. 异步委派：把"talking"和"thinking"解耦

GPT-Live 委派给 frontier 模型时**优化的是"直到 frontier 模型产出对对话有用的结果"的总耗时**。原话：

> "We therefore treated the full delegation loop—routing, prompt processing, inference, and tool calls—as part of the responsiveness budget."

具体做的优化：

- 语音会话启动时，**提前给 frontier 模型建 inference session + prefill 初始 context**——不是用户说话时才开始建。
- 整段语音会话期间 frontier inference session 保持存活，**用 session affinity 让请求稳定路由**。
- 配合 prompt caching，进一步压低 latency。
- 调整 reasoning effort / output limits / tool schemas / model-tool round trips 这些杠杆，让 frontier 模型更快产出可用结果。

**这套取舍的本质**：主对话流和异步委派共享**同一份延迟预算**。**voice 模型可以用"嗯" "让我想想"撑几十秒，但不能撑几分钟**——所以 frontier 模型委派的端到端延迟必须压在人类对话可以接受的范围内。

### 6. 把连续语音拆成离散 turns：speculative view + authoritative view

voice 模型连续 streaming，但**周边系统（ChatGPT UI / analytics / 安全过滤）仍是 turn-based**。原话：

> "Even though the voice model operates on continuous streams of speech, many of the systems around it still operate on user and assistant turns, including ChatGPT’s conversation UI and parts of our analytics and safety infrastructure."

解法是 **两层对话视图**：

- **speculative view（推测视图）**：实时滚动，最新一条消息是 provisional 的，文本 / 时间 / 说话人都可能变。UI 渲染这个。
- **authoritative view（权威视图）**：speaking floor 持续足够久后才 finalize 写入。analytics / 日志 / 安全过滤读这个。

**关键取舍**：

> "Every segmentation policy trades freshness for certainty. Committing too early produces fragmented history and unstable ordering; waiting too long delays transcripts and the features that depend on them."

**这是任何流式 + turn-based 双轨系统的通用解法**——不只是 voice。AI 助手 agent 的实时流式输出 + 后台审计日志 / 数据库写入也是同样问题。**speculative view + authoritative view + finalize 阈值** 是当前最稳的两层架构。

### 7. WARP：WebRTC 6 RTT → 1 RTT

WebRTC 是个分层协议——DTLS（传输层安全）、ICE（连通性）、SCTP（数据通道）、DCEP（数据通道建立）。每层都自带 anti-DoS 机制，但**叠在一起时 anti-DoS 是冗余的**。WARP 做四件事：

- **SPED**：把 DTLS 握手 piggyback 到 ICE 握手里（**省一个 RTT**）；
- **DTLS 1.3**：DTLS 1.3 比 1.2 快；
- **SNAP**：预协商 SCTP 握手（**省一个 RTT**）；
- **预协商 data channel**：跳过 DCEP（**省一个 RTT**）。

加上 Instant Connect（预协商 SDP 参数，**SDP 交换不再走 critical path**），客户端可以用**单个 UDP 包**启动 session，服务器立刻响应。

原文：

> "With the SDP exchange off the critical path and WARP collapsing the transport handshake, the client can now start a session with a single UDP packet."

WARP 是 OpenAI 联合 WebRTC 社区设计的开放规范——**libwebrtc 和 Pion 都已实现**，其他实现跟进中；提案走 IETF TSVWG。**这不是 OpenAI 私有协议，是 IETF 路径上的开放提案**。

### 8. Silent test：capacity 不再是 GPU throughput

GPT-Live 上线前跑了 silent test——把一小部分 ChatGPT Voice 流量比例逐步放大到 GPT-Live，**老 Advanced Voice Mode 仍服务用户**（双轨影子）。第一个教训：

> "Voice sessions stay open and send frames continuously, so CPU-side stream handlers, queues, and network paths must scale alongside inference."

capacity 问题**从"GPU 能跑多少请求"变成"系统能 sustain 多少并发 session 同时让每帧守时"**。具体踩坑：

- 一个 supporting component（推测是 CPU 侧的流式 handler）比 load test 预期更早饱和，导致推理请求堆积、latency 复合放大。
- 地域变成 first-order 关注——跨地域路由在 startup 和 streaming 多个点加延迟。
- 长 session 才暴露的问题：内存压力、持久化压力、重连的 compaction + 状态恢复、客户端断开时的 shutdown handshake race。
- observability：latency 指标被不同来源混合、聚合看板隐藏了单个不健康 engine、配置漂移。

修复路径：

- 加更细粒度的 telemetry；
- 已知好配置做 validation；
- 分阶段 ramp；
- **单独隔离 / disable 任一路径的能力**。

**对做语音 / 视频 / 长连接服务的工程团队**，这套 silent test + 流量比例 ramp-up 的方法论是当前公开过的最完整的版本。**"capacity 不能只看 GPU throughput"** 是这一段最重的一句话——语音服务的容量规划必须加 CPU / 队列 / 网络 / 帧守时率四个维度。

## 对 Agent / 工程的影响

### 立刻能用的场景

1. **任何做 voice agent 的团队，把"主对话流"和"异步委派"做物理隔离**——慢工具调用 / 慢推理只能延迟自己的结果，不能 stall 音频。GPT-Live 的规则是通用的：实时客服、实时游戏 NPC、实时陪伴 agent 同样适用。
2. **Python 团队做长连接流式，前端这层可能得 Go 化**——不是因为 Go 更快，是因为 Go 的 p95/p50 比例接近 1。**流式媒体的真正需求不是平均延迟低，是延迟抖动小**。
3. **做实时交互系统的团队，把"模型实例切换"和"上下文压缩"统一成同一种 managed transition**——并行 prefill + 切流。代价是双份算力浪费，但切流卡顿比双份算力更贵。
4. **任何要做 WebRTC 实时系统的团队，关注 WARP / SPED / SNAP**——IETF TSVWG 路径上的开放提案，libwebrtc 和 Pion 已有实现。**WebRTC 6 RTT → 1 RTT 是当前公开可拿的最显著握手优化**。
5. **长连接服务的 capacity 规划**：监控面板必须加"并发 session 数 × 每帧守时率"维度，**不只是 GPU 利用率**。silent test + 流量比例 ramp-up 是当前公开过的最完整的方法论。
6. **流式 + turn-based 双轨系统（AI 助手实时输出 + 后台审计 / 数据库）**：**speculative view + authoritative view + finalize 阈值** 是最稳的两层架构。

### 需要进一步验证

1. **WARP 在生产环境的实际收益**：OpenAI 论文级描述但没有给"6 RTT 减到 1 RTT 在用户感知上的延迟差异"。**任何要做 voice agent 的团队，自己 A/B 测一下 WARP 启用 / 不启用下的首字节延迟和首帧延迟**，别只看握手时间。
2. **silent test 流量比例 ramp-up 的具体阈值**：OpenAI 没给"切 1% → 5% → 20% → 100%"的阶梯具体数字。**这是每个团队要按自己的 service tier SLO 单独调**的。
3. **GPT-Live 是否会单独发 API**：原文末段说 "the upcoming GPT‑Live API"——意味着 API 还没发，但会发。**等 API 发了再做产品集成，不要现在基于博客内容做架构决策**。
4. **OpenAI 是否会公开 WARP 实现细节**：博客只描述了协议改进的"做什么"，没给"怎么做"。**libwebrtc / Pion 实现可以拉代码看**，但 OpenAI 自己的实现细节（具体握手时序、超时设置）还没公开。

### 短期不要碰

1. **不要在 GPT-Live API 还没发布时基于博客内容做架构决策**——这是工程笔记，不是 API 文档。**等 API 发布 + 官方 SDK 发布** 再做产品集成。
2. **不要照搬 WARP 协议到自己系统**——WARP 是 IETF 提案路径上的开放规范，但**还在演进**。如果团队要做生产 WebRTC 系统，先用 libwebrtc / Pion 的现有实现，别自己手写。
3. **不要把 Go 重写当成"Python 不行"的普适结论**——GPT-Live 的 workload 是**每帧守时的长连接流式音频**。如果是普通 HTTP request-response 异步服务，Python 完全可以；**只有 workload 是"延迟抖动敏感"时才需要重新评估**。
4. **不要忽略 KV cache 失效的代价**——OpenAI 把上下文压缩当 managed transition 是为了"压缩期间不卡顿"，**但 KV cache 重建 + 新实例 prefill 的算力开销是真实存在的**。小模型 / 低延迟场景下这个开销可以忽略，长上下文 / 大模型场景下要认真评估。

## 我的判断

1. **GPT-Live 是 2026 年公开过的最完整的实时语音架构笔记。** 8 个工程决策（去掉 turn detector / 媒体路径与应用逻辑分离 / Go 重写前端 / Stateful inference 切换 / 异步委派延迟预算 / speculative vs authoritative view / WARP 6→1 RTT / silent test 流量比例）每一项都有清晰的取舍和代价。**对任何要做 voice agent 的团队，这篇博客等于一份"必读清单"**——可以不同意 OpenAI 的取舍（用 Go / 用 WARP / silent test 模式），但**不能不知道**这些取舍被公开讨论过。
2. **去掉 turn detector 是 voice agent 行业的"分水岭"。** 老 cascaded 系统"猜早被截断 / 猜晚被嫌慢"的问题，本质是**用一个小模型去预测"何时可以说话"这个高难度决策**。GPT-Live 直接让 voice 模型自己 full-duplex，把这个决策下放给大模型——**这是把"小模型做辅助决策"模式改成"大模型端到端做决策"模式的典型案例**。同样的取舍未来会扩展到实时客服 / 实时游戏 NPC / 实时陪伴 agent——任何需要"何时说话 / 何时行动"的实时交互系统，都会跟着 GPT-Live 走。
3. **WARP 是 IETF 路径上的开放提案，不是 OpenAI 私有协议**——这一点非常关键。**WebRTC 6 RTT 减到 1 RTT 的改进如果被 IETF 接受，是整个 WebRTC 生态受益**——视频会议、远程协作、低延迟直播都会跟着升级。OpenAI 把这个改进交给 IETF 而不是闭源，意味着**实时语音 / 实时视频的下一代握手协议是公有的**，任何想跟进的实现方都可以拉 libwebrtc / Pion 代码。
4. **silent test + 流量比例 ramp-up 是 OpenAI 反复用过的方法论**——它在 GPT-5.5 / GPT-5.6 / GPT-Live 都用过。**任何要做大模型上线发布的工程团队，应该把"silent test 流量比例 ramp-up"当成默认方法**——不要从 0% 直接切到 100%，不要在没有 shadow 流量的情况下做灰度。
5. **GPT-Live 的架构不是"AI 新东西"，是分布式系统的旧原理应用到新 workload**——主路径和异步路径分离、媒体路径和应用逻辑分离、并行 prefill + 切流、speculative view + authoritative view、流量比例 ramp-up——**这些都是分布式系统的老技巧**，但 OpenAI 把它们在 voice 上下文里重新讲了一遍。**做 AI Agent 的工程团队应该把这些原理背熟，不是只背 AI 那部分**。

**Q1：来源/出处？**
A：[How we built a realtime system for responsive voice AI in six months — OpenAI 官方博客](https://openai.com/index/continuous-voice-interaction-with-gpt-live)，2026-08-03 发布，作者 Justin Uberti + Zahan Malkani（MTS）；[Wayback Machine 完整正文](https://web.archive.org/web/2026/openai.com/index/continuous-voice-interaction-with-gpt-live)（OpenAI 整站 CF 反爬，原始 URL `curl` / 浏览器直访均失败，归档缓存拿到 523 KB 完整正文）。

**Q2：能不能复现 / 怎么验证？**
A：分四步：(1) 取 Wayback URL 拿到正文；(2) WARP 协议改进部分去 IETF TSVWG 邮件列表 / 草案仓库查当前状态；(3) libwebrtc / Pion 拉代码看 SPED / SNAP 实现；(4) 等 GPT-Live API 发布后做实测 A/B（首帧延迟 / 每帧守时率 / WARP 启用前后对比）。

**Q3：适用边界？**
A：本文只覆盖 OpenAI 官方公开的工程笔记 + 我的分析。**GPT-Live 还没发布 API**——任何"我们要立刻集成 GPT-Live"的决策都是过早的。**等 API 发布 + 官方 SDK 发布 + WARP 被 IETF 接受**再做产品集成。

**Q4：和其他类似项目对比？**
A：和 OpenAI 之前的 Realtime API、ChatGPT Voice（Advanced Voice Mode）比，**GPT-Live 是第三代**——核心差异是 turn detector 被移除、Go 重写前端、WARP 协议改进。**第三代比第二代显著**——第二代还是 turn-based；第三代是 full-duplex。和 Google Gemini Live 比，**两家的取舍方向接近**（full-duplex voice model + WebRTC + 异步委派），但 OpenAI 把工程笔记公开讲了一遍，Google 的 Live API 文档还在产品层；做架构参考 OpenAI 更详尽。

**Q5：风险/坑？**
A：(1) 把"OpenAI 公开了"当成"OpenAI 邀请集成"——这是工程笔记不是 API 文档。(2) 把"去掉 turn detector"当成"所有 voice system 都该这么设计"——小模型端到端决策的代价是模型体积 / 推理成本，**不是每个 voice system 都扛得起**。(3) 把"Go 重写前端"当成"Python 不行"——Python 异步在普通 HTTP workload 下完全可以，**只有延迟抖动敏感时才需要重新评估**。(4) 把"WARP 6→1 RTT"当成"WebRTC 协议层 bug"——WARP 是改进不是 bug，**现有 WebRTC 在多数场景下仍然够用**。

---

参考资料（按权威性排序）：

1. [How we built a realtime system for responsive voice AI in six months — OpenAI 官方博客](https://openai.com/index/continuous-voice-interaction-with-gpt-live)（2026-08-03，**主体来源**——去掉 turn detector / Go 重写前端 / WARP 6→1 RTT / silent test 流量比例 ramp-up / capacity 不再是 GPU throughput / KV cache + 上下文压缩 = 一次 managed transition / speculative view + authoritative view）
2. [Wayback Machine 完整正文](https://web.archive.org/web/2026/openai.com/index/continuous-voice-interaction-with-gpt-live)（2026-08-03，**取证来源**——OpenAI 整站 CF 反爬，原始 URL `curl` / 浏览器直访均 403 / CF challenge，归档缓存拿到 523 KB 完整正文）
3. [Gemini API Managed Agents: 3.6 Flash, hooks, and more — Google blog](https://blog.google/innovation-and-ai/technology/developers-tools/expanding-managed-agents-gemini-api-3-6-flash-hooks/)（2026-07-28，**同期动态**——同周 Google 把 Managed Agents 的 hooks / 模型选择 / 免费层上线，env hooks 是另一个"异步委派"的工程化变体，但方向不同：GPT-Live 是 voice 实时路径，Gemini Managed Agents 是 code execution / tool use 异步路径）
4. WARP 协议改进（OpenAI 联合作者提交给 IETF TSVWG 的开放提案——SPED / SNAP / DTLS 1.3 / Instant Connect；libwebrtc / Pion 已有实现；详细提案文本本文未直接引用，仅作为方向参考）

字数自检：≥1500 个中文字符（不含 frontmatter）
隐私自检：未写入个人姓名、内部代号、商业秘密、内网 IP、真实机器名（仅保留 OpenAI 官方博客公开署名作者 Justin Uberti + Zahan Malkani）
封面 seed：2026-08-05-openai-gpt-live-realtime-voice-six-months（唯一）
coverWidth/Height：1600 / 900
categories：ai_tech
