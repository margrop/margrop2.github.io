---
title: "七个 AI Coding Plan 的用量散落在各处，我造了一个局域网看板把它们统一起来"
categories: ai_tech
tags:
  - AI Infrastructure
  - Self-hosting
  - DevOps
  - Coding Plan
  - Dashboard
  - Docker
  - 开源项目
cover: https://picsum.photos/seed/coding-plan-dashboard/1600/900
coverWidth: 1600
coverHeight: 900
date: 2026-07-25 20:00:00
---

一句话结论：如果你同时订阅了 Codex、Kimi Code、MiniMax、火山方舟、LongCat、千问 AI、Google AI 中的两个以上，那你大概率也和我一样——每天打开四五个网页查配额，然后发现某个平台的 5 小时窗口早就打满了，而你直到报错才知道。

我开源了一个叫 **Coding Plan Dashboard** 的项目，一个 Docker 容器跑在局域网里，把所有平台的配额数据拉到一个页面上。不依赖任何第三方 SaaS，数据不出你的内网。

项目地址：<https://github.com/margrop/coding-plan-dashboard>

<!-- more -->

## 为什么需要这个东西

先说背景。2026 年上半年，各大模型厂商几乎都推出了面向开发者的 Coding Plan——按周或按月的订阅制，给你一定的请求配额用来跑 AI 编程助手。我手头同时在用的就有七家：

| 平台 | 配额周期 | 查询方式 |
|------|---------|---------|
| Codex (OpenAI) | 5h 窗口 + 周限额 | 网页 Dashboard |
| Kimi Code | 5h 窗口 + 周限额 | 网页 Dashboard |
| MiniMax | 周限额 | 网页控制台 |
| 火山方舟 (Volcano Engine) | 5h 窗口 + 周限额 | API 查询 |
| LongCat (美团) | 周限额 | 网页控制台 |
| 千问 AI (通义灵码) | 周限额 | 网页控制台 |
| Google AI (Gemini CLI) | 日限额 + 周限额 | API 查询 |

问题很明显：**每个平台的配额模型都不一样，查询入口也都不一样。**

有的给你一个网页 Dashboard，你得登录进去看；有的只有 API，你得自己 curl 再解析 JSON；有的连 API 都没有，只能看网页上那行小字。

我试过写 shell 脚本轮询，也试过用 n8n 做定时任务，但都卡在同一个问题上：**这些平台的认证方式千差万别。** 有的用 Bearer Token，有的用 AK/SK 签名，有的用 OAuth Cookie，有的用 API Key。你没法用一个统一的 HTTP 客户端搞定所有平台。

更麻烦的是，配额是"窗口制"的。比如 Codex 的 5 小时窗口，你在窗口 A 里用掉的额度，要到窗口 B 才释放。如果你不知道当前窗口还剩多少，就会在关键时刻被限流——而限流提示往往只是一句冷冰冰的 `rate_limit_exceeded`。

所以我决定自己造一个。

## 设计思路：不造轮子，造胶水

这个项目的第一原则是：**不做任何平台的 SDK 封装，不做任何中间件代理。** 它只是一个"胶水层"——把各平台已有的查询能力粘到一起。

具体来说，数据采集走的是这条路：

1. 你在浏览器里打开某个平台的用量页面
2. F12 → Network → 找到那个返回配额 JSON 的请求
3. 右键 → Copy as cURL
4. 粘贴到 Dashboard 的导入框里

Dashboard 后端拿到这段 cURL 命令后，做的事情很简单：**解析出 URL、Headers、Body，然后用 Python 的 `httpx` 原样重放这个 HTTPS 请求。**

这里有一个关键设计决策：**我没有用 `subprocess` 去执行 curl 命令。** 原因很直接——如果我把用户粘贴的 cURL 字符串直接丢给 shell 执行，那就是一个现成的命令注入漏洞。cURL 命令里可以藏 `$(...)` 、反引号、管道符，任何一种都能让我在服务器上执行任意命令。

所以我选择了更笨但更安全的方案：用正则和 shlex 把 cURL 命令拆成结构化的请求参数，再用 Python HTTP 客户端发出去。整个过程不经过 shell。

![数据流：从 cURL 到看板](/post-images/coding-plan-dashboard/dataflow.png)

## 技术架构

整个项目由三部分组成：

**前端**：一个纯静态的 `index.html`，没有任何构建步骤。Vue 3 和 Tailwind CSS 都通过 CDN 加载，所有逻辑写在一个文件里。是的，我知道这听起来很"不工程化"，但这个项目的前端逻辑并不复杂——渲染卡片、展示表格、处理导入——用一个文件反而更容易维护。

**后端**：一个 Python FastAPI 应用，大约 1200 行代码。核心功能就三个：解析 cURL 命令、重放 HTTPS 请求、归一化配额数据。外加一个 SQLite 数据库存账号配置和缓存。

**部署**：一个 Docker 容器，暴露 8080 端口。没有 Nginx，没有 Redis，没有消息队列。LAN-only 访问，不需要 HTTPS 证书。

![系统架构](/post-images/coding-plan-dashboard/architecture.png)

这个架构的选择背后有一个判断：**配额监控是一个低频、低并发、高价值的场景。** 我不需要每秒处理上千个请求，我只需要每隔几分钟拉一次各平台的配额数据，然后展示在一个页面上。在这种场景下，任何额外的基础设施都是负担。

## 数据归一化：七种 JSON 格式，一种展示

七个平台返回的 JSON 结构完全不同。有的给你 `used_tokens` 和 `total_tokens`，有的给你 `percentage`，有的只给你 `remaining`，还有的把配额拆成 `five_hour_window` 和 `weekly_limit` 两个维度。

我定义了一个统一的内部模型：

```python
@dataclass
class QuotaSnapshot:
    platform: str          # 平台标识
    account_label: str     # 账号备注名
    window_type: str       # "5h" | "weekly" | "daily"
    used: float            # 已用量（归一化为百分比）
    total: float           # 总量
    used_pct: float        # 使用百分比
    window_start: datetime # 窗口起始时间
    window_end: datetime   # 窗口结束时间
    raw: dict              # 原始响应，用于调试
```

每个平台的解析器负责把自己的 JSON 映射到这个模型。新增一个平台，就是写一个新的解析器——大约 50-80 行代码。

这里有一个我踩过的坑：**火山方舟的 AK/SK 签名。** 它不像其他平台那样给你一个 Bearer Token 就完事了，它需要你按特定规则对请求做 HMAC-SHA256 签名，签名里包含时间戳、region、service name 等一堆参数。我第一版直接用 cURL 导入去调，结果签名校验永远不过。后来才发现，cURL 里的 `Authorization` header 是请求时生成的，过期就失效了。

所以火山方舟走的是另一条路：用户在导入时填 AK 和 SK，后端自己实现签名逻辑，每次查询时动态生成。这也是项目里唯一一个不走"cURL 重放"模式的平台。

![Dashboard 主界面——每个平台一张卡片，显示当前窗口的用量](/post-images/coding-plan-dashboard/dashboard-cards.png)

## 实际运行效果

我在局域网的一台小主机上跑了这个 Dashboard，Docker Compose 启动，30 秒搞定：

```yaml
# docker-compose.yml
services:
  dashboard:
    image: ghcr.io/margrop/coding-plan-dashboard:latest
    ports:
      - "8080:8080"
    volumes:
      - ./data:/app/data
    restart: unless-stopped
```

`./data` 目录挂载出来，里面是 SQLite 数据库和缓存文件。容器重建后配置不丢。

启动后打开 `http://<SERVER_IP>:8080`，第一屏是这样的：

![Dashboard 顶部概览区域](/post-images/coding-plan-dashboard/dashboard-hero.png)

顶部是全局概览：总账号数、当前窗口平均使用率、即将打满的账号预警。下面是每个平台的卡片，卡片里显示当前窗口的用量百分比、窗口剩余时间、以及一个简单的进度条。

往下滚是导入区域。你把 cURL 命令粘贴进去，后端会自动识别是哪个平台，然后解析出账号信息：

![导入面板：粘贴 cURL 后自动识别平台](/post-images/coding-plan-dashboard/dashboard-import.png)

最下面是账号管理表格，可以编辑备注名、调整刷新间隔、手动触发刷新：

![账号管理表格](/post-images/coding-plan-dashboard/dashboard-accounts.png)

移动端也做了适配。虽然我主要是在电脑上看，但偶尔在手机上查一下配额也很方便：

![移动端视图](/post-images/coding-plan-dashboard/dashboard-mobile.png)

## 安全设计：这个项目的底线

因为要处理各平台的认证凭据，安全是这个项目的底线。几个关键设计：

**1. 不执行 shell 命令。** 前面说了，cURL 命令只做解析，不做执行。所有 HTTP 请求通过 Python httpx 发出。

**2. 域名白名单。** 后端只允许向已知的平台域名发请求。如果你粘贴的 cURL 指向一个不在白名单里的域名，直接拒绝。这防止了 SSRF 攻击——比如有人构造一个指向 `http://169.254.169.254/latest/meta-data/` 的 cURL 来窃取云主机的元数据。

**3. LAN-only。** 默认监听 `0.0.0.0:8080`，但文档里明确建议只在局域网内使用。不建议暴露到公网。如果你非要公网访问，请自己加反向代理和认证。

**4. 凭据存储。** AK/SK 和 Token 存在 SQLite 里，没有加密。这是一个已知的取舍——对于一个 LAN-only 的工具，我认为本地存储的风险是可接受的。如果你需要更高的安全级别，可以挂载一个加密卷。

## 和现有方案的对比

在造这个轮子之前，我调研过几个现有方案：

| 方案 | 优点 | 缺点 |
|------|------|------|
| 各平台原生 Dashboard | 数据最准确 | 要开 N 个网页，无法聚合 |
| Grafana + 自定义插件 | 灵活，可定制 | 重，每个平台要写数据源插件 |
| n8n / Home Assistant | 自动化能力强 | 配置复杂，展示层弱 |
| 自己写脚本 + cron | 简单 | 没有 UI，不支持多账号 |

Coding Plan Dashboard 的定位很明确：**它不是 Grafana 的竞品，它是一个"够用就好"的聚合看板。** 如果你需要时序图、告警规则、多租户，那 Grafana 是更好的选择。如果你只是想知道"我的七个 Coding Plan 现在还剩多少配额"，那这个项目就是为你准备的。

## 一些取舍和遗憾

**没有做告警。** 最初想做"配额超过 80% 就发通知"，但后来发现通知渠道是个无底洞——邮件、钉钉、飞书、Telegram、Bark……每个都要适配。所以目前只在页面上做颜色预警（黄色 >70%，红色 >90%）。后续可能会加一个 Webhook 接口，让外部系统来消费。

**没有做历史趋势。** SQLite 里其实存了每次查询的快照，理论上可以画时序图。但前端展示历史数据需要额外的图表库和交互设计，目前还没做。

**cURL 导入不是万能的。** 有些平台的用量页面是前端渲染的，配额数据嵌在 HTML 里而不是 API 返回的 JSON 里。这种情况下 cURL 导入拿不到有用的数据。对于这类平台，目前只能等官方出 API。

## 开源和贡献

项目已经在 GitHub 上开源：<https://github.com/margrop/coding-plan-dashboard>

![GitHub 仓库页面](/post-images/coding-plan-dashboard/github-repo.png)

![项目 README](/post-images/coding-plan-dashboard/github-readme.png)

欢迎提 Issue 和 PR。最需要的贡献是：

- **新平台的解析器。** 如果你在用其他平台的 Coding Plan（比如 Cursor、Windsurf、Claude Pro），欢迎贡献解析逻辑。
- **告警集成。** Webhook、钉钉、飞书、Telegram，任何一个都行。
- **历史趋势图。** 前端加一个时间维度的展示。

## 总结

这个项目解决的是一个很具体的问题：**多平台 AI Coding Plan 的配额聚合监控。** 它不复杂，一个 Docker 容器、一个 SQLite 文件、一个 HTML 页面。但它确实解决了我每天要开四五个网页查配额的痛点。

如果你也在同时使用多个 AI 编程助手的订阅服务，可以试试。部署成本很低，一个能跑 Docker 的设备就行——NAS、树莓派、旧笔记本、云主机都可以。

最后说一句关于"自建"的看法：不是所有东西都值得自建。这个项目的价值不在于技术多先进，而在于它把分散的信息聚合到了一个视线上可达的地方。有时候，"少开四个网页"就是最大的生产力提升。

---

*相关阅读*

- [自建服务的反代与认证：Caddy 实战](/post/2026-03-03-vps8-caddy-domain-configuration/)
- [Docker Compose 编排最佳实践](/post/2026-03-22-docker-container-security-best-practices/)
- [HomeLab 网络架构：从单台 NAS 到全屋智能](/post/2026-07-14-coding-plan-dashboard-seven-versions/)

*参考资料*

- [Coding Plan Dashboard GitHub 仓库](https://github.com/margrop/coding-plan-dashboard)
- [OpenAI Codex 配额说明](https://platform.openai.com/docs/guides/rate-limits)
- [火山方舟 API 签名文档](https://www.volcengine.com/docs/82379/1263482)
- [Google AI Studio API 文档](https://ai.google.dev/docs)

*免责声明：本文涉及的平台名称和配额模型以各平台官方文档为准，文中数据仅为示例。项目为个人开源作品，与上述平台无官方关联。*

*[English Version](/post/2026-07-25-coding-plan-dashboard-unified-quota-monitor-en/)*
