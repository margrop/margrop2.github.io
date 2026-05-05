---
title: GitHub Actions + Hexo：博客自动化部署与常见问题排查实战指南
categories:
  - ai_tech
tags:
  - 技术
  - GitHub Actions
  - Hexo
  - 自动化
  - 部署
  - CI/CD
cover: 'https://picsum.photos/seed/tech0329/1280/720'
coverWidth: 1280
coverHeight: 720
date: 2026-03-29 21:30:00
---

# GitHub Actions + Hexo：博客自动化部署与常见问题排查实战指南

## 前言

用 Hexo + GitHub Pages 搭建博客已经是很成熟的方案了，但"手动执行 hexo g -d"这件事，每次写完文章都要做一次，时间长了还是会觉得麻烦。特别是当你习惯了"写完就发布"的流程之后，多一步操作都觉得是负担。

今天就来介绍一套完整的 GitHub Actions 自动化部署方案：从仓库配置、Actions 编写，到常见问题的排查和解决，覆盖整个流程。配合实际案例讲解，保证看完就能上手。

## 为什么需要自动化部署

### 手动部署的痛点

手动部署的流程是这样的：

```
写文章 → 本地 hexo g → hexo d → 等上传完成 → 验证发布
```

每写完一篇文章，就要执行一次这个流程。如果是周更还好，要是日更，每天都要操作一遍，积少成多也挺烦的。

更麻烦的是，如果你在多台设备上写作（比如公司电脑和家里的电脑），每次换设备都要重新 clone 仓库、配置环境、才能发布。这对于使用体验来说是很大的障碍。

### 自动化部署的优势

使用 GitHub Actions 自动化部署之后，流程变成了：

```
写文章 → push 到 GitHub → GitHub Actions 自动构建部署 → 验证发布
```

你只需要把文章 push 上去，剩下的事情全部由 GitHub 自动完成。换设备也不需要重新配置，因为构建和部署都在 GitHub 的服务器上运行，你只需要一个能写文章的编辑器。

## 环境准备

### 必要条件

在开始之前，确保你满足以下条件：

1. **一个 GitHub 账号**：托管源代码和触发 Actions
2. **一个 GitHub Pages 仓库**：托管生成的静态网站，可以是同一个仓库的不同分支
3. **Node.js 环境**：用于本地测试（可选）
4. **Git 配置**：能够 push 代码到 GitHub

### 常见的部署架构

有两种主流的部署架构：

**方案一：源码和 Pages 在同一个仓库**

```
repository
├── source/  (Hexo 源码)
└── gh-pages/  (生成的静态文件，GitHub Pages 用这个分支)
```

- 优点：一个仓库搞定所有事情
- 缺点：需要配置 GitHub Actions 区分构建和部署步骤

**方案二：两个仓库**

```
repository-hexo/  (Hexo 源码)
└── repository-pages/  (静态文件，GitHub Pages)
```

- 优点：职责分离，配置简单
- 缺点：需要管理两个仓库

本文以方案一为例，因为大多数个人博客都采用这种架构。

## GitHub Actions 工作流配置

### 创建工作流文件

在仓库根目录创建 `.github/workflows/deploy.yml` 文件：

```yaml
name: Deploy Blog

on:
  push:
    branches:
      - main  # 触发条件：push 到 main 分支
  workflow_dispatch:  # 支持手动触发

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
          submodules: recursive  # 如果使用了 theme 作为 submodule
          fetch-depth: 0

      # 2. 设置 Node.js 环境
      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'  # 缓存 npm 依赖加速构建

      # 3. 安装依赖
      - name: Install Dependencies
        run: npm ci

      # 4. 生成静态文件
      - name: Generate Site
        run: npx hexo generate
        env:
          TZ: Asia/Shanghai  # 设置时区，避免文章时间错乱

      # 5. 配置 Git 用户信息
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

### 关键配置解释

**触发条件 (`on`)：**

```yaml
on:
  push:
    branches:
      - main  # 仅在 push 到 main 分支时触发
  workflow_dispatch:  # 允许在 GitHub Actions 页面手动触发
```

**缓存配置 (`cache: 'npm'`)：**

Hexo 博客的依赖通常不多（几十个包），但启用缓存可以节省大约 10-20 秒的安装时间，对于频繁触发的 Actions 来说很有价值。

**时区设置 (`TZ: Asia/Shanghai`)：**

Hexo 默认使用 UTC 时区，如果你用中文写作，文章的时间戳会显示为 UTC+0 的时间。在 Generate 步骤设置时区可以解决这个问题：

```yaml
env:
  TZ: Asia/Shanghai
```

**GitHub Pages 部署 (`peaceiris/actions-gh-pages@v3`)：**

这是最流行的 GitHub Pages 部署 Action，它会：
1. 将 `publish_dir`（即 `public` 目录）的内容推送到 `publish_branch`（即 `gh-pages` 分支）
2. 自动配置 GitHub Pages 的设置

### 配置 GitHub Pages

部署 Action 运行成功后，需要在 GitHub 仓库设置中启用 GitHub Pages：

1. 进入仓库 **Settings** → **Pages**
2. **Source** 选择 **Deploy from a branch**
3. **Branch** 选择 **gh-pages** 分支，**/ (root)** 目录
4. 点击 **Save**

通常几分钟后网站就可以访问了，地址是 `https://<username>.github.io/<repository>/`

## 常见问题排查

### 问题一：Hexo 命令找不到

**错误信息：**

```
Error: Cannot find module 'hexo'
Error: npx: command not found
```

**原因分析：**

Hexo 没有被正确安装。这通常是因为 `package.json` 中的依赖没有包含 `hexo` 本身。

**排查步骤：**

```bash
# 检查 package.json 是否包含 hexo
cat package.json | grep hexo

# 正确的 dependencies 应该包含：
# "dependencies": {
#   "hexo": "^7.0.0",
#   "hexo-generator-sitemap": "^3.1.0",
#   ...
# }
```

**解决方案：**

确保 `package.json` 中包含了 `hexo` 依赖：

```bash
npm install hexo --save
git add package.json package-lock.json
git commit -m "chore: add hexo dependency"
git push
```

### 问题二：Theme submodule 没有被正确克隆

**错误信息：**

```
fatal: not a git repository: /path/to/theme/.git
```

**原因分析：**

如果你的主题是通过 Git submodule 的方式引入的，Actions 的 checkout 默认不会克隆 submodule。

**排查步骤：**

检查 `.gitmodules` 文件是否存在：

```bash
cat .gitmodules
# 应该看到类似：
# [submodule "themes/landscape"]
#   path = themes/landscape
#   url = https://github.com/hexojs/hexo-theme-landscape.git
```

**解决方案：**

在 checkout 步骤添加 `submodules: recursive`：

```yaml
- name: Checkout
  uses: actions/checkout@v4
  with:
    submodules: recursive
    fetch-depth: 0
```

### 问题三：构建时间过长导致超时

**错误信息：**

```
Error: The job running you has run out of time
```

**原因分析：**

GitHub Actions 有超时限制（默认 360 分钟，免费版对公开仓库是 6 小时/月的总运行时间）。对于 Hexo 博客来说，正常构建时间在 30 秒到 2 分钟之间。如果超时，可能是依赖安装过慢或者网络问题。

**排查步骤：**

```bash
# 本地测试一下构建时间
time npx hexo generate
```

**解决方案：**

启用 npm 缓存可以显著加速依赖安装：

```yaml
- name: Setup Node
  uses: actions/setup-node@v4
  with:
    node-version: '20'
    cache: 'npm'
```

如果问题仍然存在，可以考虑：
1. 使用国内镜像源（通过 `.npmrc` 配置）
2. 减少不必要的主题插件

### 问题四：部署后页面显示 404

**错误信息：**

部署成功，但访问网站显示 `404 Page not found`。

**原因分析：**

这种情况通常有两个原因：
1. GitHub Pages 的源分支设置不正确
2. 仓库名称与 GitHub Pages 路径不匹配

GitHub Pages 的访问规则是：
- 如果仓库名是 `<username>.github.io`，则网站根目录就是 `https://<username>.github.io/`
- 如果仓库名是其他名字如 `blog`，则网站路径是 `https://<username>.github.io/blog/`

**排查步骤：**

```bash
# 检查生成的 public 目录
ls public/

# 确认 index.html 存在
cat public/index.html | head -5
```

**解决方案：**

1. 确认 GitHub Pages 设置中选择了正确的分支（`gh-pages`）

2. 如果使用的是自定义域名，需要在 `public` 目录放置 `CNAME` 文件。在 Hexo 博客中，可以创建 `source/CNAME` 文件（注意是 `source` 目录，不是 `public` 目录），内容写入你的域名：

```
www.example.com
```

然后在 `_config.yml` 中配置：

```yaml
url: https://www.example.com
root: /
```

### 问题五：CI/CD 触发但没有任何变化

**错误信息：**

workflow 运行了，但是没有任何变化。

**原因分析：**

Hexo 的 generate 命令只有在检测到源文件变化时才会重新生成内容。如果你是通过 API 或者脚本修改文章，而没有正确 flush 文件系统，GitHub Actions 可能检测不到变化。

**排查步骤：**

```bash
# 检查最近一次 commit 的变更
git log --oneline -3
git diff HEAD~1 --stat
```

**解决方案：**

在 `_config.yml` 中可以禁用 `skip_render` 匹配，确保所有文件都被处理：

```yaml
skip_render: []  # 不要跳过任何文件
```

或者确认修改文件后正确执行了 `git add` 和 `git commit`。

## 进阶配置

### 配置自定义域名 + HTTPS

在 `source` 目录下创建 `CNAME` 文件（注意是 `source/CNAME`，Hexo 会自动将其复制到 `public` 目录）：

```
yourdomain.com
```

然后在 `_config.yml` 中配置 URL：

```yaml
url: https://yourdomain.com
root: /
```

GitHub Actions 部署完成后，在仓库 Settings → Pages 中：
1. 填入自定义域名
2. 勾选 **Enforce HTTPS**

### 配置 URL 路径

如果你的博客不在仓库根目录（比如仓库叫 `blog`，网站是 `https://username.github.io/blog/`），需要修改 `_config.yml`：

```yaml
url: https://username.github.io/blog
root: /blog/
```

### 配置构建通知

你可以在工作流中添加钉钉、企业微信或者邮件通知，在构建失败时及时收到提醒：

```yaml
- name: Notify on Failure
  if: failure()
  run: |
    curl -X POST "https://your-webhook-url" \
      -H "Content-Type: application/json" \
      -d '{"msg": "Blog CI/CD failed"}'
```

## 一键部署脚本

以下是一个本地部署辅助脚本，帮助你快速完成初始配置：

```bash
#!/bin/bash
# Hexo 博客 GitHub Actions 部署初始化脚本

set -e

echo "开始初始化 Hexo + GitHub Actions 自动化部署..."

# 1. 检查必要的文件
if [ ! -f "package.json" ]; then
    echo "错误: 未找到 package.json，请确保在 Hexo 博客根目录执行此脚本"
    exit 1
fi

# 2. 创建 GitHub Actions 目录
mkdir -p .github/workflows

# 3. 创建 deploy.yml
cat > .github/workflows/deploy.yml << 'EOF'
name: Deploy Blog

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

      - name: Setup Node
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

# 4. 创建 .gitmodules（如果没有的话）
if [ ! -f ".gitmodules" ]; then
    echo "ℹ️  未检测到 Git submodule，略过相关配置"
fi

# 5. 创建 CNAME 文件（可选）
read -p "是否配置自定义域名？(y/N): " use_domain
if [ "$use_domain" = "y" ]; then
    read -p "请输入你的域名: " domain_name
    echo "$domain_name" > source/CNAME
    echo "✅ 已创建 source/CNAME"
fi

# 6. 提交并推送
git add .
git commit -m "chore: add GitHub Actions deployment workflow"
git push

echo ""
echo "✅ 初始化完成！"
echo "请在 GitHub 仓库 Settings → Pages 中启用 GitHub Pages"
echo "选择分支: gh-pages，目录: / (root)"
```

使用方法：

```bash
chmod +x init-actions.sh
./init-actions.sh
```

## 总结

本文详细介绍了 GitHub Actions + Hexo 自动化部署的完整方案，核心要点包括：

1. **工作流配置**：通过 `.github/workflows/deploy.yml` 定义构建和部署流程
2. **关键步骤**：checkout → setup-node → npm ci → hexo generate → deploy
3. **常见问题**：Hexo 命令找不到、submodule 未克隆、构建超时、404 错误等
4. **进阶配置**：自定义域名、HTTPS、构建通知等

自动化部署的意义不只是省事，而是让写作和发布变成一个"提交代码"的动作，从而降低写作的心理门槛。当发布变得足够简单，你才能更专注于内容本身。

---

*作者：小六，一个致力于让技术简单一点点的程序员*
