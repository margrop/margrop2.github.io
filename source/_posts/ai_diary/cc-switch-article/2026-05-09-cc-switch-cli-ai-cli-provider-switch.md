---
title: '当五个AI编程助手同时"需要"换供应商：我是如何从配置地狱爬出来的'
categories:
  - ai_diary
tags:
  - 日记
  - 效率工具
  - AI编程助手
  - CLI工具
  - CC-Switch
  - Claude Code
  - Codex
  - OpenCode
  - OpenClaw
  - Gemini CLI
cover: 'https://picsum.photos/seed/ccswitch2026/1280/720'
coverWidth: 1280
coverHeight: 720
date: 2026-05-09 21:00:00
---

# 当五个AI编程助手同时"需要"换供应商：我是如何从配置地狱爬出来的

说出来你们可能不信，就在上周，我同时在用五款AI编程助手——Claude Code、Codex、OpenCode、OpenClaw，还有一个Gemini CLI。

为什么这么多？因为工作需要不同的工具嘛。有的做代码审查厉害，有的生成测试用例快，有的跟我的工作流集成得好。

但问题来了：某天，我常用的那个API代理商突然发了封邮件——"亲，我们的endpoint要更换啦，请更新配置"。我一看邮件，心凉了半截。

五款工具。五种配置格式。五个不同的配置文件路径。

**这就是我今天的故事：从"配置地狱"爬出来，然后遇见了CC Switch CLI。**

## 背景：五个工具，五种"方言"

先给你们看看我之前的配置文件有多乱：

**Claude Code** 用的是 `~/.claude/settings.json`，字段名是 `anthropicApiKey` 和 `apiUrl`。
**Codex** 用的是 `~/.codex/config.toml`，字段名是 `api_key` 和 `base_url`。
**Gemini CLI** 最特殊，用的是 `~/.gemini/.env` 环境变量格式。
**OpenCode** 用的是 `~/.config/opencode/opencode.json`，但格式跟Claude的还不完全一样。
**OpenClaw** 又有自己的 `~/.openclaw/openclaw.json` 配置体系。

每次换API供应商，我都得：
1. 打开一个配置文件
2. 查文档确认字段名
3. 修改
4. 保存
5. 重复上面步骤四次

这不是在写代码，这是在**填表**。

而且最烦的是，有些字段名还很像但不完全一样——比如`base_url` vs `apiUrl` vs `endpoint`，每次都要确认自己没改错。

![配置地狱对比图](/post-images/2026-05-11-cc-switch-cli-ai-cli-provider-switch/before-after.png)
*图1：没有CC Switch之前，我的配置文件管理状态——五湖四海，格式各异*

## 痛点：换一次供应商要多久？

给你们算个时间账：

假设我要把所有工具从"代理商A"切换到"代理商B"：

- **Claude Code**: 打开 `~/.claude/settings.json`，找到 `apiUrl` 字段，修改，保存 → 3分钟
- **Codex**: 打开 `~/.codex/config.toml`，找到 `base_url`，修改，保存 → 3分钟  
- **Gemini CLI**: 修改 `~/.gemini/.env` 里的环境变量 → 2分钟
- **OpenCode**: 打开 `~/.config/opencode/opencode.json`，找到对应字段 → 3分钟
- **OpenClaw**: 打开 `~/.openclaw/openclaw.json`，找到对应字段 → 3分钟

**加起来：14分钟。** 而且这还是"顺利"的情况。如果手滑改错了字段，排查又要额外花时间。

更可怕的是：如果你有多个环境（公司、家里、不同项目），每个环境都要改一遍。

**这不是在写代码，这是在跑腿。**

## 转折点：发现CC Switch CLI

忍无可忍之后，我开始搜索"AI编程助手配置管理工具"。然后我发现了两个项目：

1. **farion1231/cc-switch** — 原始的桌面GUI版本，用Rust + Tauri写的
2. **SaladDay/cc-switch-cli** — CLI版本，功能一样，但更适合我这种SSH党

最终我选择了cc-switch-cli。因为：
- 我大部分时间在远程服务器上工作
- 命令行操作可以写脚本自动化
- TUI界面跟我的工作流完美契合

安装只需要一行命令：

```bash
curl -fsSL https://github.com/SaladDay/cc-switch-cli/releases/latest/download/install.sh | bash
```

安装完成后，输入 `cc-switch` 就进入了交互式TUI界面。

## CC Switch CLI到底是什么？

CC Switch CLI是一个用Rust写的跨平台命令行工具，专门用来**统一管理多个AI编程助手的Provider配置**。

支持的应用：
- **Claude Code**（默认）
- **Codex**
- **Gemini CLI**
- **OpenCode**
- **OpenClaw**

核心功能有六大模块：

| 功能模块 | 能干啥 |
|---------|--------|
| 🔌 Provider管理 | 一键切换API供应商，支持速度测试 |
| 🛠️ MCP服务器管理 | 统一管理多个工具的MCP配置 |
| 💬 Prompts管理 | 备份和切换System Prompts |
| 🎯 Skills管理 | 安装和管理社区Skills扩展 |
| 🌉 代理管理 | 本地多应用代理路由控制 |
| ⚙️ 配置管理 | 备份、恢复、WebDAV同步 |

![功能总览图](/post-images/2026-05-11-cc-switch-cli-ai-cli-provider-switch/features-grid.png)
*图2：CC Switch CLI的六大核心功能模块*

## 核心功能详解

### 1. Provider管理 — 一键切换供应商

这是CC Switch的核心功能。假设我有多个API供应商配置：

```bash
# 列出所有已配置的供应商
cc-switch provider list

# 查看当前正在使用的供应商
cc-switch provider current

# 切换到指定供应商
cc-switch provider switch apiyi-proxy

# 测试供应商的API延迟
cc-switch provider speedtest apiyi-proxy
```

CC Switch会把所有供应商信息存在SQLite数据库里（`~/.cc-switch/cc-switch.db`），然后根据不同的应用生成对应的配置文件。

比如切到Claude Code时，它会更新 `~/.claude/settings.json`；切到Codex时，它会更新 `~/.codex/config.toml`。**你不需要知道每个工具的配置文件长什么样，CC Switch帮你搞定一切。**

![Provider切换流程图](/post-images/2026-05-11-cc-switch-cli-ai-cli-provider-switch/provider-switch-workflow.png)
*图3：CC Switch执行Provider切换的完整工作流程*

### 2. 跨应用统一管理

这是CC Switch最让我惊喜的功能——一个 `--app` 参数搞定所有工具。

```bash
# 列出Claude的供应商
cc-switch --app claude provider list

# 列出Codex的供应商
cc-switch --app codex provider list

# 查看OpenClaw的供应商
cc-switch --app openclaw provider list

# 同步MCP服务器到Codex
cc-switch --app codex mcp sync

# 查看Gemini的提示词
cc-switch --app gemini prompts list
```

这意味着：**不管你用多少个AI编程工具，都可以用同一套命令操作它们。**

### 3. Prompts管理 — 不再丢失的提示词

你们有没有过这种经历：花了半天写了一个完美的System Prompt，结果换了个环境就找不到了？

CC Switch的Prompts管理功能可以：
- 备份所有应用的System Prompt（CLAUDE.md、AGENTS.md、GEMINI.md等）
- 创建多个提示词预设，随时切换
- 通过WebDAV同步到云端，换机器也不怕

```bash
# 列出所有提示词预设
cc-switch prompts list

# 创建新预设
cc-switch prompts create "代码审查模式"

# 激活预设
cc-switch prompts activate 代码审查模式

# 导出到文件
cc-switch config export ~/cc-switch-backup.json
```

### 4. Skills管理 — 社区技能一键安装

CC Switch还支持Skills扩展管理。从GitHub上发现好的Skills？一键安装并启用：

```bash
# 搜索可用的Skills
cc-switch skills discover "testing"

# 安装
cc-switch skills install superpower-tdd

# 启用Skills
cc-switch skills enable superpower-tdd --app claude

# 同步到应用目录
cc-switch skills sync
```

这比之前手动clone仓库、复制到正确目录方便多了。

### 5. 配置备份与WebDAV同步

CC Switch会在 `~/.cc-switch/backups/` 目录自动备份配置，保留最近10个版本。

```bash
# 创建备份
cc-switch config backup --name "换供应商前"

# 恢复备份
cc-switch config restore

# 配置WebDAV同步（支持坚果云等）
cc-switch config webdav set \
  --base-url https://dav.example.com \
  --username user \
  --password pass \
  --enable
```

有了WebDAV同步，我在公司配置的供应商信息，回家打开电脑就自动同步过来了。

### 6. 环境检查

```bash
# 检查本地安装了哪些AI CLI工具
cc-switch env tools

# 检查环境变量冲突
cc-switch env check
```

这个功能帮我发现过好几次 `ANTHROPIC_API_KEY` 环境变量冲突的问题——有些工具在环境变量里设置了API Key，导致配置文件里的设置被忽略了。

## 实际使用体验

用了一个星期，说说我的感受：

**优点：**

1. **大幅减少重复操作**：以前换供应商要14分钟，现在一个命令搞定
2. **配置集中管理**：所有供应商信息存在一个SQLite数据库里，一目了然
3. **自动化程度高**：备份、恢复、同步都可以脚本化
4. **交互TUI很友好**：不记得命令？直接输入 `cc-switch`，菜单导航
5. **支持多语言**：可以切换中英文界面

**缺点：**

1. **学习曲线**：刚接触时要理解 `--app` 参数的作用
2. **文档部分内容过时**：GitHub上的README更新了，但部分第三方文档没跟上
3. **没有GUI**：习惯桌面应用的同学可能觉得不方便（但我喜欢CLI）

## 现在的日常

用了CC Switch之后，我的工作流变成了这样：

**早上到公司：**
```bash
# 检查今天要用哪个供应商
cc-switch provider list
```

**切换供应商：**
```bash
# 一键切换
cc-switch provider switch rightcode

# 验证是否成功
cc-switch --app claude provider current
cc-switch --app codex provider current
```

**备份配置：**
```bash
# 自动备份
cc-switch config backup
```

整个过程不超过1分钟，而且**不会改错文件**。

## 总结：配置管理是门学问

用AI编程助手越多，越觉得**配置管理是门学问**。

工具多了，每个工具的配置文件格式都不一样——这是历史包袱，也是现实。但现实归现实，我们不能被它牵着鼻子走。

CC Switch CLI解决的问题很明确：**让你不用再记每个工具的配置文件长什么样，一套命令走天下。**

它不完美，但它是目前我找到的最接近"统一管理"这个目标的工具。如果你也在同时用多个AI编程助手，不妨试试。

**毕竟，我们花钱买的是AI的能力，不是花时间填表的快乐。**

---

*作者：一位从配置地狱爬出来的工程师*

**文中配图说明：**

![CC Switch中心枢纽图](/post-images/2026-05-11-cc-switch-cli-ai-cli-provider-switch/hub-diagram.png)
*配图1：CC Switch作为中心枢纽，统一管理多个AI编程助手的配置*

![TUI界面截图](/post-images/2026-05-11-cc-switch-cli-ai-cli-provider-switch/tui-screenshot.png)
*配图2：CC Switch交互式TUI界面，支持菜单导航和实时状态查看*