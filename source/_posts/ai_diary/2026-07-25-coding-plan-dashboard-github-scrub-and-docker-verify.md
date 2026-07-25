---
title: 把 coding-plan-dashboard 整成 GitHub-ready 的今天：IP 脱敏、rebase 压成 1 个 commit，最后让 Codex 上 192.168.x.x-45 验了一遍 Docker
categories:
  - ai_diary
tags:
  - AI 日记
  - Coding Plan Dashboard
  - 开源项目
  - GitHub
  - Docker
  - Codex
  - 打工人
  - 周六
cover: 'https://picsum.photos/seed/2026-07-25-coding-plan-dashboard-github-scrub/900/600'
coverWidth: 900
coverHeight: 600
date: 2026-07-25 21:30:00
---

> 笔名：小六 / 上海 / 1995 女 / 某互联网公司打工人

![周六整天都在 GitHub 化的 coding-plan-dashboard：脱敏、压 commit、验部署](https://picsum.photos/seed/2026-07-25-coding-plan-dashboard-github-scrub/900/600)

## 一句话结论

今天我把 [Coding Plan Dashboard](https://github.com/margrop/coding-plan-dashboard) 这个项目从「局域网自用脚本」一路折腾成「能丢上 GitHub 公开仓库」的版本：先全仓脱敏（删硬编码 IP、删代理配置、把默认目标改成 URL 特征识别），再把所有本地 commit rebase 成 1 个压扁提交强推 gitea，最后让 Codex 上 192.168.x.x-45 这台装了 Docker 的内网机器跑了一遍 `docker compose up -d`，确认 `http://127.0.0.1:8080/` 还能 200。**真正卡我的不是 GitHub 上传，是"自己的历史里埋了一颗硬编码 IP"。**

## 真实背景

这个项目我大概一周前就在用了——把 Codex、Kimi Code、MiniMax、火山方舟 CodingPlan / AgentPlan、LongCat、千问 AI、Google AI (Gemini 3.5 Flash) 这七家 Coding Plan 的配额攒到一个看板里，每天早上打开就知道今天哪个平台窗口要满了。AI Tech 那篇《七个 AI Coding Plan 的用量散落在各处》就是介绍它的。

写完那篇 Tech 之后，我开始想：这个东西既然我天天用、又有 README、有 `AGENTS.md`、有 `LICENSE`、有测试，**为什么不顺手丢到 GitHub 公开**？本来就是 MIT 协议下我自己写的代码，没用公司任何内部模块。

但丢之前必须做一件事：**把 git 历史里所有"内网指纹"清掉**。

这个项目最初是从我个人用的脚本一路改过来的，最早的 commit 里写死了 NewAPI 服务的 IP（`192.168.x.x-44`，就是我自己 NewAPI 容器那台机的局域网地址），README 还引用了一个走 HTTP 代理才能访问的地址（`192.168.x.x:1081`，这是我以前科学上网留的）。这两样东西如果跟着 commit 一起推到 GitHub，任何一个搜引擎都能搜到，等于把我的内网拓扑扬了。

所以今天的工作量是：

1. 把 server.py 里所有硬编码的 NewAPI 主机改成"根据 URL 特征自动识别"——只要你的 curl 里有 `/api/channel/{channelId}/codex/usage` 和 `/api/channel/{channelId}/codex/usage/reset-credits` 这两个 path，就判定是 NewAPI 的 Codex 渠道，不再依赖具体主机。
2. 把 README 和 server.py 里所有 `http://192.168.x.x:1081` 代理相关的引用清掉，让用户通过环境变量自己配。
3. git 历史里有 7-8 个旧 commit 引用过 IP，**必须 rebase 压成 1 个 commit 再强推**——否则光改 working tree 不够，git log 里仍然能看到老 IP。
4. 最后让 Codex 在一台 Docker 测试机上跑一遍 `docker compose up -d`，确认改完之后还能正常启动。

## 我做了什么（按时间线）

### 上午 09:13 — 决定把 commit 全部 rebase 压扁

第一件事我想得很清楚：改 working tree 没用，得改 git 历史。

我跟 Codex 说：

> 帮我将当前项目的 git 所有提交全部 rebase 压缩成 1 次提交

理由很简单——一个公开仓库，git log 是透明的，攻击者拿到一个早期 commit 的 IP 就能拼出我的内网拓扑。rebase 之后只剩一个干净的 "feat: coding plan quota dashboard with GitHub-ready metadata"，没有 IP 残留。

这一步 Codex 走得比较顺利，用 `git rebase -i HEAD~N` 把 7-8 个 commit 全压成 1 个，最后强推 `gitea master`。

### 上午 09:32 — 让 NewAPI 主机不再是硬编码

紧接着我让 Codex 改一个老 bug：

> 请更新并重新部署该项目，我希望该项目不要直接将 192.168.x.x-44 定死为 NewAPI 的自动识别，而是根据 url 特征【/api/channel/{channelId}/codex/usage 和 /api/channel/{channelId}/codex/usage/reset-credits】自动识别为 NewAPI 的 Codex 渠道，且项目中也不要再出现 192.168.x.x-44 等字样

这一步是**最有工程价值的一改**。原本 server.py 里有个 `if 'newapi' in url` 之类的硬编码判断，改成基于 URL path 的白名单：

```python
NEWAPI_PATH_PATTERNS = (
    "/api/channel/{channel_id}/codex/usage",
    "/api/channel/{channel_id}/codex/usage/reset-credits",
)
```

这样任何人在自己的局域网里跑 NewAPI，只要把 curl 粘进看板，**服务器自己就能识别是 NewAPI 的 Codex 渠道**，不再依赖任何具体主机名/IP。

### 上午 10:04 — 删掉代理相关的旧配置

第三步是删代理：

> http://192.168.x.x:1081 这个代理的相关代码需要全部从 git 仓库中移除，请移除后重新 amend 提交到 gitea

这一步 Codex 走得有点磕绊——第一次 amend 之后我发现 git log 里还有一两条 commit 提到了代理词（不是 IP，是描述文字里写了"通过代理"），所以又让它跑了一遍 `git rebase -i` 手动清理 commit message。

教训：**"已脱敏"的判断不能只看 working tree，必须看 `git log --all --oneline` 的每一行 commit message**。我差点漏过。

### 下午 13:29 — 准备 GitHub 上传的"四件套"

中午吃完饭回来，我开始准备 GitHub 上传：

> 1. AGENTS.md 随仓库发布，2. LICENSE 选择 MIT，3. 帮我进行修改并压缩为 1 个 Commit，4. 搭建 CI

这个清单其实是**公开仓库的"四件套"**：
- `AGENTS.md` → 给未来的 AI coding agent 看（这个项目自己的 AGENTS.md 里写了"credentials out of source code、部署走 Portainer Stack、验证 http://<host>:8080 返回 200"）
- `LICENSE = MIT` → 商用友好
- rebase 压成 1 commit → 历史干净
- `.github/workflows/test.yml` → CI 跑 `node --test tests/parser.test.js` + `python3 -m unittest`

CI 这一步 Codex 帮我写了完整的 GitHub Actions workflow，用 `ubuntu-latest`，先 checkout、再 `actions/setup-python@v5` (3.13)、再 `actions/setup-node@v4`、再装依赖、再跑测试。最后我让它把 Gitea 和 GitHub 同步推——先用 SSH 推 Gitea master，再用 HTTPS 推 GitHub main。

### 下午 18:37 — 拿 GitHub Personal Access Token

到下午六点多，Codex 跟我说 GitHub 端需要 Personal Access Token。我去 Settings → Developer settings → Personal access tokens → Tokens (classic)，生成了一个 classic token（不是 fine-grained），把相应权限勾上——`repo` 全部 + `workflow`（因为要触发 CI）。Codex 拿到 token 之后就能 `git push https://ghp_xxx@github.com/margrop/coding-plan-dashboard.git main` 了。

这一步我学到一件事：**公开仓库的 GitHub Actions 用 classic PAT 就够了**。fine-grained token 反而需要勾一堆 resource owner 和 permission，对个人项目 overkill。

### 晚上 20:33 — 验部署

git 那边搞定之后，剩下的最后一道关卡是——**改完之后还能不能正常跑？**

> 我为了将 coding-plan-dashboard 发布到 github ，将该项目修整了一下，你看看该项目是否还能正常的部署？

这句话听起来很轻飘，其实是今天最关键的一步。**改完一堆东西之后不复跑一遍，谁也不知道 deploy 是不是真的能起来。**

### 晚上 20:59 — 验 Docker 部署教程

紧接着我又问：

> 检查一下当前项目的 docker 部署教程，即根据该教程是否能正确的在 docker 容器中部署？

这一步是**把 README 当 checklist 走一遍**——从 "1. Prepare the host directory" 一直到 "4. Verify with curl"，每一步能不能真的复现。如果 README 写的是"sudo mkdir -p /docker/coding_plan_quota_dashboard/data"但脚本里 `docker-compose.yml` 引用的是别的路径，就是文档和代码不一致，公开出去会被人骂。

### 晚上 21:01 — 上 Docker 测试机

最后一步：

> 你可以在 192.168.x.x-45（你可以 ssh root@ip）做测试，该机器上安装了 docker

192.168.x.x-45 是我专门留出来跑"一次性部署测试"的机器，跟生产环境隔离。Codex ssh 上去之后跑了：

```bash
sudo mkdir -p /docker/coding_plan_quota_dashboard/data
sudo chmod 700 /docker/coding_plan_quota_dashboard/data
sudo cp index.html server.py docker-compose.yml /docker/coding_plan_quota_dashboard/
cd /docker/coding_plan_quota_dashboard
sudo docker compose up -d
sudo docker compose ps
sudo docker logs --tail=100 coding-plan-quota-dashboard
curl -fsS -o /dev/null -w 'HTTP %{http_code}\n' http://127.0.0.1:8080/
```

`HTTP 200`。部署成功。

## 哪里失败/为什么

今天踩的最深的一个坑是 **"git rebase 压扁之后，commit message 里仍然残留 IP"**。

我第一遍让 Codex 把所有 commit rebase 成 1 个之后，自己 `git log --all --pretty=full` 看了一遍，发现 squash 后的 commit message 里有一行写的是"为内网 NewAPI 192.168.x.x-44 增加自动识别"——这个 IP 是我之前 commit 时手动写进去的，squash 会把多个 commit 的 message 合并到一起，**老 message 里的 IP 不会自动清掉**。

处理办法是用 `git rebase -i HEAD~1` → `reword` → 手动把 IP 删掉，再 `--amend` 一次。Codex 第一遍没做这步，是我看到 `git log` 里有 IP 之后才让它补的。

另一个小坑是 GitHub 端第一次 push 失败，报 `ghp_lZ...OOIO token has insufficient scope`——classic token 默认没勾 `workflow` scope，跑 GitHub Actions 触发不了。补勾之后重试通过。

## 如何验证

今天的关键验证是 **"192.168.x.x-45 这台 Docker 测试机上 `docker compose up -d` 之后，`curl http://127.0.0.1:8080/` 返回 200"**。

具体步骤：

```bash
# 1. 在 192.168.x.x-45 上确认 docker 装好
docker --version && docker compose version

# 2. 按 README 准备目录
sudo mkdir -p /docker/coding_plan_quota_dashboard/data
sudo chmod 700 /docker/coding_plan_quota_dashboard/data
sudo cp index.html server.py docker-compose.yml /docker/coding_plan_quota_dashboard/

# 3. 启动 stack
cd /docker/coding_plan_quota_dashboard
sudo docker compose up -d

# 4. 看 container 状态 + logs
sudo docker compose ps
sudo docker logs --tail=100 coding-plan-quota-dashboard

# 5. 验证 HTTP
curl -fsS -o /dev/null -w 'HTTP %{http_code}\n' http://127.0.0.1:8080/
# 期望: HTTP 200

# 6. 验证 git 历史干净
cd /path/to/coding-plan-dashboard
git log --all --pretty=format:'%h %s' | grep -E '192\.168|10\.[0-9]+|172\.(1[6-9]|2[0-9]|3[01])' || echo 'clean'
# 期望: clean
```

第 6 步是今天额外加的——**部署能跑 ≠ git 历史干净**。两个都要过才算"开源 ready"。

## 可复用经验

1. **"已脱敏"的判断要包括 git 历史**：只改 working tree 不够，老 commit message 里的 IP 仍然能被搜索引擎索引。`git log --all --pretty=full` + `grep` 是 audit 的最低标准。
2. **公开仓库的"四件套"**：AGENTS.md + LICENSE + rebase 1 commit + CI workflow。今天我意识到这四样是个人项目开源的最低标配，少一样就别谈"开源"。
3. **GitHub PAT 用 classic 就够**：fine-grained 对个人项目是 overkill，反而要勾一堆 resource owner 和 permission，容易出错。
4. **公开前的部署验证必须有一台独立的 Docker 测试机**：今天用 192.168.x.x-45 隔离跑了一遍 README 的步骤，README 是真的能走通还是"看起来能走通"立刻就能分出来。如果只在生产机上验，**一旦 README 写错，生产机也跟着错**。
5. **`docker compose up -d` 之后一定要 `curl http://127.0.0.1:<port>/` 验证**：container `Up` 不等于业务可用。我见过太多次"docker compose ps 显示 Up 但 curl 返回 connection refused"——是因为 `network_mode: host` 但 app 启动失败。

---

> 今天还看到这条新闻：OpenAI 推出 Health in ChatGPT（个人健康对话产品，2026-07-24 发布）、Google 把 Managed Agents 扩到 Gemini API（带 background tasks 和 remote MCP）——和今天 Coding Plan Dashboard "把多个 Coding Plan 统一到一个看板" 是同一个心智：**与其每个服务都打开一个 tab，不如攒到一个面板里**。只不过 OpenAI / Google 攒的是产品形态，我攒的是 API 配额。