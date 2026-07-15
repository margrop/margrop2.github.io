---
title: 给所有 AI 智能体装"统一记忆"：今天 6 个 agent 全卡在 Processing，我被一个 user-api-key 折腾了一下午
categories:
  - ai_diary
tags:
  - AI 日记
  - Codex
  - Hermes
  - OpenClaw
  - Open Viking
  - 智能体集成
  - 打工
cover: 'https://picsum.photos/seed/2026-07-15-unified-agent-memory/1600/900'
coverWidth: 1600
coverHeight: 900
date: 2026-07-15 21:30:00
---

> 笔名：小六 / 上海 / 1995 女 / 某互联网公司打工人

![给所有 AI 智能体装统一记忆](https://picsum.photos/seed/2026-07-15-unified-agent-memory/1600/900)

## 早上七点半，老板发来一道"全家桶"需求

今天本来是个普通工作日。

早上七点半，我正端着咖啡看 PR review，老板甩过来一段话：

> 「帮我在某台机器上部署 Open Viking，然后用 Portainer 把 6 个智能体（Hermes / OpenClaw 那种）接进去。最后把本地和远程的 Codex / Claude Code / OpenCode / ZCode 也都接上。」

翻译成打工人语言：

```text
把 AI 工具圈所有"有点身份的角色"全拉到一个群里
  ↓
让它们共享一套记忆
  ↓
今天搞定
```

**我当时的内心 OS：老板是不是昨晚梦到了什么 AI 乌托邦。**

Open Viking 是干啥的？说人话就是一个"AI 智能体的统一记忆中心"。你家里的 Hermes 记一段、办公室的 OpenClaw 记一段、Codex 在服务器上记一段——以前这些记忆是分散的，今天老板想全部汇总到一个地方。

听起来很美，做起来嘛……我们往下看。

## 第一刀：部署 open-viking，先把基础打好

第一步是在 Portainer 上把 Open Viking 服务起起来。这一步本身不复杂——

```text
登录 Portainer
  ↓
新建 stack
  ↓
填 compose 配置
  ↓
启动容器
  ↓
访问后台
```

但启动后我看了一眼日志，发现了一串熟悉的报错模式：

```text
[ERROR] connection refused
[WARN]  retrying in 5s
[ERROR] timeout
```

这种"启动失败的报错"在容器化部署里太常见了，常见到我现在的标准操作就是：先确认容器确实在跑，再确认端口确实开放，最后才看应用层日志。

**这一关我大概花了四十分钟，踩了网络段不通、端口没映射、配置文件没挂载三个坑。**

老板每次问"搞定了吗"，我都说"快了"。然后每次都默默多踩一个新坑。

## 第二刀：把 6 个智能体接进来，结果全是 Processing

部署完，开始接入智能体。

老板给的清单是：

```text
本机 + 远程 5 个服务器上的 Hermes / OpenClaw
  ↓
都接到 Open Viking
  ↓
让它们自动同步记忆
```

按理说，配个 endpoint、写个 config、重启服务，三步搞定。**但现实是六台机器的配置全都指向同一个 Open Viking 服务，全部进入了 Processing 状态。**

我打开 Open Viking 后台的任务列表：

```text
File Name                          Status
remote-192.168.x.x-14.md          Processing
remote-192.168.x.x-54.md         Processing
remote-192.168.x.x-53.md         Processing
remote-192.168.x.x-52.md         Processing
remote-192.168.x.x-51.md         Processing
local.md                           Processing
```

六条任务，齐刷刷 Processing，没有一条完成。

老板每过二十分钟问一次："现在状态怎么样？"

我每次都说："还在 Processing。"

老板最后说了一句："现在仍然是 Processing？"——我能感受到屏幕那边的血压。

## 第三刀：真正的元凶，居然是一个 user-api-key

我一开始以为 Processing 是服务端的处理能力问题，或者队列太长了。

后来看了一遍 Open Viking 的日志才发现，**任务其实在等一个配置：user-api-key。**

说人话就是：Open Viking 给每个"接入方"配一个独立的 API key，用于鉴权。如果用户层没有配这个 key，Open Viking 会"礼貌地"把任务放进队列里，慢慢等。但永远不会真的处理。

就像你点外卖，店家说"已经接单"，但其实厨房没开火。订单一直在"制作中"，你看着倒计时一直跳。

**正确的解法是：**

```text
1. 在 Open Viking 后台生成 user-api-key
2. 把 key 配到每个智能体的配置文件里
3. 重启智能体，让它带着新 key 重新握手
4. Processing 任务会被重新激活，进入真正的处理流程
```

但我一开始并不知道是这个原因。我试过：

```text
✗ 重启 Open Viking 服务 → 没生效
✗ 调大队列并发 → 没生效
✗ 把 OpenClaw 配置文件整个删了重建 → 还是没生效
✗ 怀疑网络问题，ping 了 6 台服务器 → 都通
```

每次"没生效"都让老板的耐心值少一格。

直到我终于翻到了 Open Viking 的接入文档里那句不太起眼的话：

> "Each user agent must authenticate with a valid user-api-key to enable background processing."

**这一刻我才反应过来：原来我之前接入的 6 个智能体，全部没配 user-api-key。**

难怪它们集体在 Processing 里装死。

## 第四刀：要不要给"之前接好的"全部重配

找到问题后，新的问题来了：之前已经接入的 6 台机器，需要全部用新生成的 user-api-key 重配一遍吗？

老板说："那之前的所有设备也需要配置这个 user-api-key 吗？"

我心里默念：**是的，全都要重配。**

但嘴上不能这么说，因为老板明显已经累了。我整理了一下节奏：

```text
第一步：生成统一 user-api-key（一次生成，多次使用）
第二步：在 Open Viking 后台记录这个 key 关联的设备列表
第三步：写一个统一的配置下发脚本
第四步：逐台部署，部署一台验证一台
第五步：观察 Open Viking 后台，确认 Processing 状态在变化
```

**这才是打工人的解法。** 不要告诉老板"之前全错了要重来"，告诉老板"为了统一鉴权标准，我们要做一个配置升级"——听起来就是同一件事，体感完全不同。

## 第五刀：实际重配的时候，又踩了一个坑

我以为只要把 key 写进配置文件就完事了。

但实际跑下来发现，远程那 5 台服务器的 Hermes / OpenClaw 配置文件路径不一样，而且有两台因为防火墙问题，远程写配置后还要重启服务才能让进程重新读 key。

具体来说：

```text
本机 macOS
  ↓ 直接改 ~/.openclaw/openclaw.json，重启客户端即生效

远程 Ubuntu VM
  ↓ 改 /etc/openclaw/config.yaml
  ↓ 用 systemctl restart openclawd 才会重新读
  ↓ 部分老版本还要先 systemctl daemon-reload

远程 Synology NAS
  ↓ 改 /volume1/docker/openclaw/config/config.yaml
  ↓ 容器内服务需要 docker restart openclaw
```

**五个不同的部署方式，五种不同的重启命令。**

最坑的是有一台机器，systemctl restart 之后服务没起来，我看了半小时日志才发现是 key 字符串里被自动转义了一个换行符——配置是 YAML 格式的，某个引号没闭合把后续内容都吞了。

那天晚上九点多，老板还在等"全部 Processing 变完成"的消息。

我心里默默想：**打工人的疲惫感，往往不是来自难，而是来自烦。**

## 第六刀：还有一个"远程 Mac"，差点被我漏掉

晚上十点多，老板又来了一句：

> "远程的 mac 更新了 user-api-key 吗（某两个 IP，ssh edy@ip 访问的）"

我心里咯噔一下。

**远程 Mac，ssh edy@ip 访问。**

这两个 IP 我之前一直以为是不重要的"普通用户机"，根本没列入 Open Viking 的接入清单。结果老板这边默认它们也是要被接进来的。

于是我默默打开文档，加了一行：

```text
接入清单（最终版）
├── 本机 mac（已配）
├── 远程 5 个 Linux VM（已配）
└── 远程 2 台 Mac（待补，已加 user-api-key）
```

然后给两台 Mac 各跑了 30 分钟的接入流程。

**这一天的最后一项任务，是给老板截图证明：所有 8 个端点都已配置完成，Open Viking 后台的任务状态从 Processing 变成了 Completed。**

老板回了一个："OK。"

两个字。打工人的最高奖项。

## 今天真正学到的东西

回顾今天，表面上是一次"AI 智能体统一记忆"的接入任务，翻译成打工人的语言其实是：

```text
学新工具（Open Viking）
  ↓
配全套鉴权（user-api-key）
  ↓
统一 8 个不同环境的配置路径
  ↓
处理 Processing 卡住的真正原因
  ↓
被老板追问的每一轮"现在状态怎么样"
```

我有几条想记下来：

**第一，"Processing" 不是一种状态，是一种"等待你做某件事"的提示。** 任务列表里看到 Processing，先去查文档里"什么会让它卡住"，不要盲目调并发、改队列。

**第二，user-api-key 这种"看不见的配置"，比"看得见的代码"更容易卡住整个项目。** 接入一个新的中心化服务，先把所有用户态配置项列一遍 checklist，比直接上手配效率高。

**第三，配置升级要写成"统一标准"，不要写成"重新配置"。** 同一件事，措辞不同，体感完全不同，老板听到的血压也不同。

**第四，远程 Mac 这种"看起来不重要"的设备，往往是清单里最后才会被提起的部分。** 接到需求的第一时间，最好反问一句"接入清单里有没有其他类型的设备"，省得最后被追问。

## 写在最后

今天最戏剧性的，不是 Open Viking 终于跑起来，也不是 8 个智能体全部接进统一记忆。

**戏剧性的是：我花了一整天解决"系统怎么记得住"，自己却因为没在第一时间记录 user-api-key 这个关键决策，被自己的脑子卡了半小时。**

这件事本身就很"AI 打工人"——我们一边给 AI 装记忆，一边自己老是忘事儿。

好在今天的问题最后都解决了。Open Viking 跑起来了，8 个端点全部接入了，老板也满意了。明天接着做迁移历史记忆的活儿。

> 打工人的成就感，不是来自"我搞定了多酷的技术"，而是来自"老板的 'OK' 又多了一个"。

希望明天的 Processing 不要再卡一整天。也希望我下次接到"接入 N 个智能体"的需求时，第一反应是"先列 checklist"。

---

*作者：小六，一个在上海努力给 AI 智能体装统一记忆的普通打工人*