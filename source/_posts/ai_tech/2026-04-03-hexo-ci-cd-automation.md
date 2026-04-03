---
title: Hexo博客自动化发布的完整实践：从本地写作到一键部署的技术方案
categories:
  - ai_tech
tags:
  - 技术
  - Hexo
  - GitHub Actions
  - CI/CD
  - 自动化
  - 部署
cover: 'https://picsum.photos/seed/tech0403/1280/720'
coverWidth: 1280
coverHeight: 720
date: 2026-04-03 21:30:00
---

# Hexo博客自动化发布的完整实践：从本地写作到一键部署的技术方案

## 前言

Hexo 是一个很受欢迎的静态博客框架，配合 GitHub Pages 使用几乎零成本，是很多个人博主和技术写作者的首选。但"手动执行 hexo g -d"这件事，每次写完文章都要做一次，时间长了还是会觉得繁琐。

本文介绍一套完整的 Hexo 博客自动化发布方案，从本地写作、GitHub Actions 自动化构建，到服务器端验证，覆盖整个流程。文章末尾提供了常见问题的排查指南，适合想要把博客发布变成"push 即发布"的写作者参考。

## 问题背景

### 传统发布流程的痛点

手动发布的典型流程是这样的：

```
写文章（本地） → 上传到服务器 → 执行 hexo g -d → 验证发布结果
```

这个流程存在几个常见问题：

**第一，多设备写作不方便。** 如果在公司和家里分别用不同的电脑写作，每次换设备都需要重新配置 Hexo 环境、clone 仓库、上传文章，流程繁琐且容易出错。

**第二，发布操作无法自动化。** 每次写完都要手动执行发布命令，对于高频写作者来说，这个"机械操作"累积起来也是不小的时间成本。

**第三，发布结果无法自动验证。** 手动执行命令之后，还需要手动打开浏览器确认文章是否正常显示。这个验证步骤很容易被忽略。

**第四，脱敏检查容易被跳过。** 技术博客通常包含 IP 地址、域名、路径等信息，手动检查既繁琐又容易遗漏。

### 自动化发布的目标

自动化方案要解决的核心问题是：

```
写文章 → push 到 GitHub → 自动构建 → 自动部署 → 自动验证
```

整个过程不需要人工介入，作者只需要完成"push"这一个动作，剩下的全部由系统自动完成。

## 架构设计

### 整体流程

```
┌─────────────┐     push      ┌──────────────┐    hexo g    ┌────────────────┐
│   本地写作   │ ──────────► │  GitHub Repo  │ ──────────► │  GitHub Pages  │
└─────────────┘              └──────────────┘              └────────────────┘
                                    │
                                    ▼
                            ┌──────────────┐
                            │ GitHub Actions│
                            │  自动构建     │
                            └──────────────┘
                                    │
                                    ▼
                            ┌──────────────┐
                            │  自动化验证   │
                            │  (可选步骤)  │
                            └──────────────┘
```

### 仓库结构设计

推荐采用"源码和 Pages 在同一仓库"的架构：

```
blog repository (例: my-blog)
├── .github/
│   └── workflows/
│       └── deploy.yml       # CI/CD 配置
├── source/                  # Hexo 源码目录
│   └── _posts/              # 文章存放位置
│       ├── ai_diary/        # AI Diary 分类
│       └── ai_tech/         # AI Tech 分类
├── themes/                  # 主题目录（通常为 submodule）
├── public/                  # Hexo 生成的静态文件（gitignore）
├── _config.yml              # Hexo 主配置
├── package.json             # npm 依赖
└── .gitmodules              # submodule 配置
```

这样的结构有一个关键优点：**源码和生成的静态网站在同一个仓库中，通过不同分支管理**，无需维护两个独立的仓库。

## GitHub Actions 工作流配置

### 基础配置

在 `.github/workflows/deploy.yml` 中编写工作流：

```yaml
name: Deploy Hexo Blog

on:
  push:
    branches:
      - main
  workflow_dispatch:

permissions:
  contents: read

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    timeout-minutes: 15

    steps:
      # 1. 检出代码
      - name: Checkout
        uses: actions/checkout@v4
        with:
          submodules: recursive
          fetch-depth: 0

      # 2. 设置 Node.js 环境（带缓存）
      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'

      # 3. 安装依赖
      - name: Install Dependencies
        run: npm ci

      # 4. 生成静态文件
      - name: Generate Site
        run: npx hexo generate
        env:
          TZ: Asia/Shanghai

      # 5. 配置 Git 用户
      - name: Configure Git
        run: |
          git config --global user.name "github-actions[bot]"
          git config --global user.email "github-actions[bot]@users.noreply.github.com"

      # 6. 部署到 GitHub Pages
      - name: Deploy
        uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./public
          publish_branch: gh-pages
```

### 关键配置项详解

**submodules: recursive**

如果主题通过 Git submodule 引入（如 `git submodule add https://github.com/hexojs/hexo-theme-landscape themes/landscape`），必须在 checkout 步骤加上 `submodules: recursive`，否则主题文件不会被克隆，导致构建失败。

**fetch-depth: 0**

Hexo 的某些插件依赖 Git 历史信息（如 `hexo-generator-sitemap`），设置为 0 可以获取完整的 Git 历史，确保插件正常工作。

**cache: 'npm'**

GitHub Actions 的 Node.js Setup Action 内置了 npm 缓存支持。启用后，第二次及之后的构建会复用缓存的 node_modules，显著缩短构建时间。对于 Hexo 这样依赖不算多的项目，开启缓存可以将依赖安装时间从约 60 秒缩短到 10 秒以内。

**TZ: Asia/Shanghai**

这是最容易遗漏但又非常重要的配置。Hexo 默认使用 UTC 时区，如果没有设置 `TZ: Asia/Shanghai`，文章的 `date` 字段会被解析为 UTC 时间，在中国时区（UTC+8）访问时会显示为"未来时间"，导致文章排序错乱或显示异常。

## 进阶配置

### 添加构建通知

Hexo 博客通常在阿里云等国内服务器上托管，GitHub Actions 的通知邮件在 国内网络环境下经常收不到。推荐配置钉钉或企业微信群通知：

```yaml
      - name: Notify on Failure
        if: failure()
        run: |
          curl -X POST "https://oapi.dingtalk.com/robot/send?access_token=YOUR_TOKEN" \
            -H "Content-Type: application/json" \
            -d '{
              "msgtype": "text",
              "text": {
                "content": "[Blog Deploy] 构建失败，请检查日志"
              }
            }'
```

### 添加隐私扫描步骤

技术博客中经常包含 IP 地址、域名、内部路径等敏感信息。在工作流中添加隐私扫描步骤，可以在构建阶段发现泄露风险：

```yaml
      - name: Privacy Scan
        run: |
          # 扫描敏感 IP 模式（如 192.168.x.x, 10.x.x.x 等内网IP）
          if grep -rE '192\.168\.[0-9]+\.[0-9]+|10\.[0-9]+\.[0-9]+\.[0-9]+|172\.(1[6-9]|2[0-9]|3[0-1])\.[0-9]+\.[0-9]+' source/_posts/; then
            echo "警告：检测到内网 IP 地址，请确认已脱敏"
            exit 1
          fi
          echo "隐私扫描通过"
```

### 多环境分支策略

对于有"草稿"和"发布"分离需求的写作者，可以配置分支策略：

```yaml
on:
  push:
    branches:
      - main        # push 到 main → 自动发布
  pull_request:
    branches:
      - main        # PR 到 main → 仅构建验证，不发布
```

## 服务器端自动化验证

如果博客托管在自有服务器（如阿里云 ECS）而非 GitHub Pages，还可以在服务器端添加自动化验证步骤，确保构建结果正确上传并正常渲染。

### 方案一：Webhooks 触发验证

GitHub Actions 在每次构建完成后可以发送 Webhook 请求：

```yaml
      - name: Trigger Server Verification
        if: success()
        run: |
          curl -X POST "https://your-server.com/api/verify" \
            -H "Content-Type: application/json" \
            -d '{"branch": "gh-pages", "commit": "${{ github.sha }}"}'
```

服务器端接收 Webhook 请求后，执行以下验证：

```bash
#!/bin/bash
# verify.sh - 服务器端验证脚本

WEBHOOK_SECRET="your-secret"

# 验证请求来源
SIGNATURE=$(echo -n "$WEBHOOK_SECRET" | openssl dgst -sha256 -hmac "$BODY" | cut -d' ' -f2)
if [ "$SIGNATURE" != "$EXPECTED_SIGNATURE" ]; then
    echo "Unauthorized request"
    exit 1
fi

# 验证文章文件存在
ARTICLE_COUNT=$(find /var/www/blog/source/_posts -name "*.md" | wc -l)
if [ "$ARTICLE_COUNT" -eq 0 ]; then
    echo "错误：未检测到文章文件"
    exit 1
fi

# 验证 Git 提交记录
LATEST_COMMIT=$(cd /var/www/blog && git log --oneline -1)
echo "最新提交: $LATEST_COMMIT"

# 验证构建产物
if [ ! -d "/var/www/blog/public" ]; then
    echo "错误：构建产物目录不存在"
    exit 1
fi

echo "验证通过"
```

### 方案二：定时拉取验证

如果 Webhook 方式不稳定，可以使用定时任务方式：

```bash
#!/bin/bash
# pull-and-verify.sh - 定时拉取并验证

BLOG_DIR="/var/www/blog"
REMOTE="origin"
BRANCH="gh-pages"

cd $BLOG_DIR

# 拉取最新内容
git fetch $REMOTE $BRANCH
LOCAL_COMMIT=$(git rev-parse HEAD)
REMOTE_COMMIT=$(git rev-parse FETCH_HEAD)

if [ "$LOCAL_COMMIT" != "$REMOTE_COMMIT" ]; then
    echo "检测到新提交，正在拉取..."
    git checkout $BRANCH
    git pull $REMOTE $BRANCH

    # 验证
    ARTICLE_COUNT=$(find $BLOG_DIR/source/_posts -name "*.md" | wc -l)
    echo "文章总数: $ARTICLE_COUNT"

    # 重新构建（确保最新）
    hexo clean && hexo g
    echo "构建完成"
else
    echo "已是最新，无需更新"
fi
```

加入 Crontab：

```bash
# 每5分钟检查一次
*/5 * * * * /opt/scripts/pull-and-verify.sh >> /var/log/blog-sync.log 2>&1
```

## GitHub Pages 配置

Actions 部署完成后，还需要在 GitHub 仓库设置中正确配置 GitHub Pages：

1. 进入仓库 **Settings** → **Pages**
2. **Source** 选择 **Deploy from a branch**
3. **Branch** 选择 **gh-pages** 分支，目录选择 **/ (root)**
4. 如果使用自定义域名，在 **Custom domain** 中填写域名并勾选 **Enforce HTTPS**

通常配置完成后 2-5 分钟内网站即可访问。如果长时间无法访问，先检查 GitHub Actions 的构建日志，确认是否有错误信息。

## 常见问题排查

### 问题一：Git submodule 未正确克隆

**错误信息：**

```
fatal: not a git repository: /path/to/theme/.git
```

**原因：** 主题通过 submodule 引入，但 checkout 时没有加上 `submodules: recursive` 参数。

**解决方案：** 修改工作流配置：

```yaml
- name: Checkout
  uses: actions/checkout@v4
  with:
    submodules: recursive
    fetch-depth: 0
```

### 问题二：Hexo 命令找不到

**错误信息：**

```
Error: Cannot find module 'hexo'
Error: npx: command not found
```

**原因：** `package.json` 中没有包含 `hexo` 依赖。常见于从别人那里 fork 的仓库，依赖不完整。

**排查步骤：**

```bash
# 检查 package.json
cat package.json | jq '.dependencies'

# 确认是否包含 hexo
cat package.json | grep hexo
```

**解决方案：** 执行 `npm install hexo --save`，确保 hexo 在 dependencies 中，然后 push 触发重新构建。

### 问题三：构建超时

**错误信息：**

```
Error: The job running you has run out of time
```

**原因：** npm 安装过慢或网络不稳定，导致超时。

**解决方案：** 
1. 启用 npm 缓存（`cache: 'npm'`）
2. 或使用国内镜像，在工作流中添加 `.npmrc` 配置：

```yaml
- name: Setup Node.js
  uses: actions/setup-node@v4
  with:
    node-version: '20'
    cache: 'npm'
    registry: 'https://registry.npmmirror.com'
```

### 问题四：部署后页面 404

**原因分析：**
1. GitHub Pages 源分支设置错误
2. 仓库名称与访问路径不匹配

**排查步骤：**

```bash
# 检查 public 目录是否有内容
ls public/

# 确认 index.html 存在
test -f public/index.html && echo "index.html 存在"
```

**解决方案：**
1. 在 Settings → Pages 中确认选择了 `gh-pages` 分支
2. 如果仓库名不是 `username.github.io`，访问路径需要加上仓库名（如 `https://username.github.io/blog/`）

### 问题五：文章时间显示错误

**原因：** Hexo 默认使用 UTC 时区，中国用户看到的文章时间会比实际晚 8 小时。

**解决方案：** 在 generate 步骤设置时区环境变量：

```yaml
- name: Generate Site
  run: npx hexo generate
  env:
    TZ: Asia/Shanghai
```

### 问题六：Actions 触发但没有任何变化

**原因：** Hexo generate 只在检测到源文件变化时才会重新生成内容。如果通过 API 修改文件但没有 flush 文件系统，Actions 可能检测不到变化。

**解决方案：** 确认每次修改后都执行了 `git add` 和 `git commit`，而不是直接用 API 写文件。

## 一键部署脚本

以下是一个完整的初始化脚本，可以快速配置 Hexo 自动化发布：

```bash
#!/bin/bash
# init-hexo-actions.sh - Hexo 博客 GitHub Actions 部署初始化

set -e

echo "开始初始化 Hexo + GitHub Actions 自动化部署..."

# 1. 检查必要文件
if [ ! -f "package.json" ]; then
    echo "错误: 未找到 package.json，请在 Hexo 博客根目录执行此脚本"
    exit 1
fi

# 2. 创建 GitHub Actions 配置目录
mkdir -p .github/workflows

# 3. 创建工作流文件
cat > .github/workflows/deploy.yml << 'EOF'
name: Deploy Hexo Blog

on:
  push:
    branches:
      - main
  workflow_dispatch:

permissions:
  contents: read

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    timeout-minutes: 15

    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          submodules: recursive
          fetch-depth: 0

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'

      - name: Install Dependencies
        run: npm ci

      - name: Generate Site
        run: npx hexo generate
        env:
          TZ: Asia/Shanghai

      - name: Configure Git
        run: |
          git config --global user.name "github-actions[bot]"
          git config --global user.email "github-actions[bot]@users.noreply.github.com"

      - name: Deploy
        uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./public
          publish_branch: gh-pages
EOF

echo "✅ GitHub Actions 配置已创建: .github/workflows/deploy.yml"

# 4. 创建 CNAME 文件（可选）
read -p "是否配置自定义域名？(y/N): " use_domain
if [ "$use_domain" = "y" ]; then
    read -p "请输入你的域名: " domain_name
    echo "$domain_name" > source/CNAME
    echo "✅ 已创建 source/CNAME"
fi

# 5. 提交并推送
git add .
git commit -m "chore: add GitHub Actions deployment workflow"
git push

echo ""
echo "✅ 初始化完成！"
echo "请在 GitHub 仓库 Settings → Pages 中启用 GitHub Pages"
echo "选择分支: gh-pages，目录: / (root)"
echo ""
echo "后续写作流程: 写文章 → git push → 自动发布"
```

使用方法：

```bash
chmod +x init-hexo-actions.sh
./init-hexo-actions.sh
```

## 总结

本文介绍了 Hexo 博客自动化发布的完整技术方案，核心要点包括：

1. **架构设计**：采用同一仓库多分支管理，源码在 main，构建产物在 gh-pages
2. **GitHub Actions 工作流**：监听 push 事件 → npm ci → hexo generate → actions-gh-pages 自动部署
3. **关键配置**：submodules 递归克隆、npm 缓存加速、时区设置
4. **进阶功能**：构建失败通知、隐私扫描、服务器端验证
5. **常见问题排查**：submodule 克隆失败、构建超时、404 错误等

这套方案可以将博客发布从"每次手动操作"变成"push 即发布"，显著降低写作的心理成本，让人更专注于内容本身而非发布流程。

---

*作者：小六，一个在上海努力搬砖的程序员*
