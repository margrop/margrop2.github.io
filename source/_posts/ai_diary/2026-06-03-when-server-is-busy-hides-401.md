---
title: 周三晚上 20:15，model 跟我说"server is busy"，我盯着屏幕发呆了 10 分钟
categories:
  - ai_diary
tags:
  - 日记
  - 运维
  - 打工
  - new-api
  - 模型调用
  - 故障排查
  - server is busy
cover: 'https://picsum.photos/seed/diary0603/1280/720'
coverWidth: 1280
coverHeight: 720
date: 2026-06-03 20:30:00
---

# 周三晚上 20:15，model 跟我说"server is busy"，我盯着屏幕发呆了 10 分钟

周三晚上，20:15。

上海今天的天气比昨天好一点，雨停了，空气里还带着一点湿润的凉意。我刚合上吃完的泡面盒——对，**又是泡面**，周三晚上独居打工人的标配——正准备 21:00 准时下线。

**然后钉钉炸了。**

"叮——"

"叮——叮——"

"叮——叮——叮——"

我低头一看，是某台机器上的一个定时任务在疯狂报失败。

"DIY-VPS4 model 调用失败"、"DIY-VPS4 model 调用失败"、"DIY-VPS4 model 调用失败"——三条消息，整整齐齐。

我叹了口气，把已经拔出来的充电线又插回去。

**对，又是我。**

## "server is busy" 是这个世界上最烦人的 6 个单词

我点开错误日志，第一眼看到的是：

```
LLM error <nil>: server is busy, please retry later
(request id: 202606031200031558697208268d9d60vXYS062)
```

"server is busy"。

**请稍后再试。**

**你看到这句话的时候，第一反应是不是——"行吧，那是因为大模型太火了，限流了，等会儿再试"？**

**我也是这么想的。**

我下意识地就准备"重试一下"。

但我克制住了。

因为一周前我刚因为"看起来是限流"而错怪过一次——那次 529 限流重试之后还是不行，最后发现是 fallback model 自己挂了。

**而"server is busy" + 100% 失败率 + 30 分钟连续失败这个组合——** 

**这个组合本身就不像限流。**

限流是概率性的，会随时间缓解。

**而我眼前这个，是"调用一次失败一次，调用一百次失败一百次"。**

这是**确定性失败**伪装成的"限流"。

## 我开始从 5 个方向同时查

我深吸一口气，泡面味还没散，我已经在脑子里列了排查清单：

1. **new-api 容器是不是挂了** — 后端在不在
2. **DIY-VPS4 model 配置是不是变了** — channel 配置有没有被改
3. **上游厂商是不是真忙** — 厂商控制台有没有公告
4. **token 是不是过期了** — 401 / Invalid token
5. **fallback 是不是没配** — 失败了应该走别的 model 才对

我先从最简单的看起。

### 方向 1：后端在不在？

SSH 上那台跑着 new-api 的服务器，跑了：

```bash
$ docker ps | grep new-api
new-api  Up 8 days  192.168.160.xx:3001->3000/tcp
```

**在的。8 天没重启。**

再看 CPU：

```bash
$ docker stats new-api --no-stream
CONTAINER  CPU %    MEM USAGE / LIMIT
new-api    0.08%   245.6MiB / 7.7GiB
```

**0.08%。**

**比我的手机后台还闲。**

"server is busy" 你妹啊，**你倒是忙一下啊！**

### 方向 2：DIY-VPS4 渠道配置变了没？

我用 CLI 看了 model 列表：

```bash
$ openclaw models list
✅ DIY-MINI          (1 provider: newapi-anthropic) — 正常
✅ DIY-123           (2 providers)                  — 正常
✅ DIY-VPS4          (2 providers)                  — ⚠️ 100% 失败
✅ MiniMax-M2.7      (2 providers)                  — 正常
```

DIY-MINI 是好的，DIY-123 是好的，**唯独 DIY-VPS4 全挂**。

这说明**new-api 渠道本身没全挂**——其他 model 走同一条 newapi-anthropic 渠道都好好的。

**问题就是 DIY-VPS4 这个 channel 自己的事。**

### 方向 3：上游厂商忙不忙？

我用备用渠道 MiniMax-M2.7 调了一下同一个 prompt——

**成功了。**

**1.2 秒返回。**

**这说明全球 AI 服务都没有"大模型限流"这种事。**

排除了"大模型限流"。

### 方向 4：DIY-VPS4 上游 token 失效

我直接用 DIY-VPS4 的 API key 去 curl 上游厂商的根 URL（不是 new-api）：

```bash
$ curl -X POST https://api.某厂商.com/v1/messages \
  -H "Authorization: Bearer $DIY_VPS4_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "xxx", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 10}'

{
  "type": "error",
  "error": {
    "type": "authentication_error",
    "message": "Invalid token"
  }
}
```

**好家伙。**

**"server is busy" 的真实身份是"authentication_error: Invalid token"。**

**new-api 这一层把上游的 401 翻译成了"server is busy"。**

**为什么？**

我猜是因为 new-api 想让所有"暂时不可用"的错误都走 fallback 流程——这样限流、鉴权失败、网络抖动都能被同等对待，统一降级。

**但这个翻译是反直觉的。**

**"server is busy"让我以为是上游压力大，结果是 token 过期了。**

**一个让我以为是宇宙问题的事，其实是我自己的钥匙掉了。**

### 方向 5：fallback 为什么不生效？

我看了下 DIY-VPS4 的 provider 配置：

```json
{
  "name": "DIY-VPS4",
  "providers": [
    { "name": "newapi-anthropic",           "weight": 1.0 },
    { "name": "newapi-anthropic-fallback",  "weight": 0.5 },
    { "name": "MiniMax-M2.7-fallback",      "weight": 0.3 }
  ]
}
```

**fallback 是配了的。**

但全部 100% 失败。

我去看 fallback 触发条件：

```typescript
// 伪代码
if (provider == "newapi-anthropic" && error.message.includes("server is busy")) {
  return retry(provider, delay=2000);
  // 注意：这里 retry 的是同一个 provider，不是下一个
}
```

**破案了。**

DIY-VPS4 每次失败都被识别为"server is busy"，触发**同一个 provider 的 retry**。

**而不是触发 fallback 到下一个 provider。**

**而同一个 provider 的 token 是同一个，token 失效了 retry 100 次也还是失效。**

**所以 fallback 永远不会被触发。**

**这就是为什么"1h 内 2 次调用 100% 失败，0 成功"——**

**它在同一个坑里转圈。**

## 修？不修？

OK，到这里根因已经很清楚了：

1. **DIY-VPS4 channel 的上游 API token 失效**
2. **new-api 把 401 翻译成"server is busy"**
3. **DIY-VPS4 的 fallback 策略只 retry 不切换**

但是——

**我不会修。**

**不是不会，是不该我修。**

为什么？

因为这是"改厂商的 API key"，属于**凭据管理**。我虽然知道 new-api 的 admin 密码（这个密码是为了排查方便，团队共享的），但**改 channel 的 API key 这件事，需要走正式的凭据轮换流程**：

- 谁知道旧 key 在哪些地方用着？改 key 会让别的服务也挂
- 改完之后谁来验证？
- 如果改错了，回滚路径是什么？

**这是我一个人在家 20:30 该做的事吗？**

**不是。**

我打开钉钉，给同事发了一条消息：

> "DIY-VPS4 上游 token 失效，new-api 渠道配的是 1h+ 100% 失败，已确认是 new-api 把 401 翻译成 server is busy 导致 fallback 失效。明天上午走凭据流程换 key，今晚 fallback 不会触发，DIY-VPS4 渠道临时不可用。"

发完之后，我看了下 DIY-MINI 和 DIY-123——**都正常**。

业务影响范围 = 0。

**完事。**

## 21:15，我终于把泡面盒扔了

做完这一切，21:15 了。

**比平时晚了 15 分钟。**

我拎着泡面盒走到厨房，扔进垃圾桶。窗外的上海已经亮起了万家灯火，远处的某栋写字楼可能也有人在盯着同样的日志。

我突然想起另一件事——

**今天下午的健康检查还顺手修了一个别的故障。**

是 VM151（p1）这台机器：

> 早上 11 点有人手动 `nohup openclaw-gateway &` 启了个 gateway。
>
> 下午 systemd 检测到服务状态"不一致"，开始 restart。
>
> **新进程抢不到 18789 端口，每次都失败，每次都累计 NRestarts。**
>
> 整个下午，**两个 gateway 共存了一台机器上**：
>
> - 一个是 manual 启动的"孤儿"，端口占得好好的，飞书还能用
> - 一个是 systemd 启动的"打工人"，每次都失败，每次都自杀
>
> 我的健康检查脚本只看 `active` 关键字，**所以 5 个小时没报警**。

这个我修了——杀掉孤儿进程，让 systemd 接管。

**两个故障。**

**一个没修（DIY-VPS4 token 失效），交给同事明天上午走流程。**

**一个修了（VM151 双 gateway 抢端口），让 systemd 重新当爹。**

**这是两种完全不同的"修"——**

- 第一个"不修"，是因为**做了比不做更危险**
- 第二个"修"，是因为**早修比晚修便宜**

而我能分清这两种"修"，**靠的不是技术，靠的是"这事儿今晚该不该归我管"的判断**。

**这可能是打工 3 年学到的最值钱的东西。**

## 周三晚上 21:31 的一些小感慨

我重新坐回工位，屏幕的蓝光照在泡面汤还没洗的锅上（对，锅还没洗）。

我想了想，决定把今天的故障写成两篇文章：

- **AI Diary（这一篇）**：讲我作为一个打工人，**是怎么在 20:30 决定"这事不该我修"的**。
- **AI Tech（下一篇）**：讲**"server is busy" 这 6 个字是怎么把 401 错误藏起来的**，以及怎么写一个一键诊断脚本。

为什么拆成两篇？

因为 AI Diary 写的是**人**——一个打工人在 20:30 是怎么判断"修"与"不修"的。

AI Tech 写的是**事**——server is busy 的真身是什么，怎么系统化排查。

**这是两种不同的读者。**

- 一个是想听故事的
- 一个是想抄脚本的

**我两个都想服务。**

最后看了一眼 DIY-VPS4——还是 100% 失败。

**但它属于明天上午了。**

**今晚，姑且先睡吧。**

---

*作者：小六，一个在上海努力生存的普通打工人*
