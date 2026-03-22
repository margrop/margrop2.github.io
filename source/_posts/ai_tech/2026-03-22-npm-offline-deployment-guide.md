---
title: 当 npm install 遇到网络隔离：离线部署 Node.js 包实战指南
categories:
  - ai_tech
tags:
  - npm
  - 网络
  - 部署
  - Node.js
date: 2026-03-22 21:50:00
---

# 当 npm install 遇到网络隔离：离线部署 Node.js 包实战指南

企业内网、生产环境、防火墙策略严格的服务器——这些场景下 `npm install` 经常遇到网络不通的问题。今天记录一次真实的离线部署案例，目标是 OpenClaw，但方法适用于任何 npm 包。

<!-- more -->

## 问题场景

目标服务器：内网 VM，Ubuntu 24.04，Node.js 24 已安装。

执行 `npm install -g openclaw@latest` 时报错：

```
npm error code 128
npm error An unknown git error occurred
npm error command git --no-replace-objects ls-remote ssh://git@github.com/whiskeysockets/libsignal-node.git
npm error fatal: Could not read from remote repository.
```

网络诊断结果：

| 目标 | 状态 |
|------|------|
| `api.github.com` | ✅ 可访问 |
| `github.com` (HTTPS) | ❌ TCP 443 超时 |
| `github.com` (SSH) | ❌ TCP 22 超时 |

API 可通但 TCP 握手失败——这说明防火墙放行了部分 GitHub 流量，但不是全部。

## 常规解法逐一尝试

### 方法 1：Git URL 重写

```bash
git config --global url.'https://github.com/'.insteadOf ssh://git@github.com/
```

**结果**：HTTPS 本身就在 TCP 层被拦截，此路不通。

### 方法 2：代理

内网有 SOCKS5/HTTP 代理，但配置繁琐且不稳定。

### 方法 3：Gitee 镜像

`libsignal-node` 不在 Gitee 上，镜像方案不适用。

## 最终方案：npm pack + SCP 离线安装

核心思路：**在网络正常的机器上下载完整包，传到目标机器本地安装**。

### Step 1：本地打包

在任意一台能访问 npm registry 的机器上（不需要是 Linux）：

```bash
npm pack openclaw@latest
```

这会下载一个 tarball，而不是安装。如果包有 native 依赖需要编译，可能还需要连同 node_modules 一起打包：

```bash
# 在本地创建完整安装目录
mkdir openclaw-install && cd openclaw-install
npm install openclaw@latest --registry https://registry.npmjs.org/

# 打包
tar -czf openclaw-node_modules.tar.gz node_modules/
```

`--ignore-scripts` 适用于跳过 postinstall，但需要确保 node_modules 完整。

### Step 2：传到目标机器

```bash
scp openclaw-*.tgz root@目标服务器:/tmp/
scp openclaw-node_modules.tar.gz root@目标服务器:/tmp/
```

内网 SCP 不受互联网防火墙影响，速度也很快。

### Step 3：目标机器本地安装

```bash
# 先安装主包
npm install -g /tmp/openclaw-2026.3.13.tgz

# 如果遇到 dist/entry.(m)js missing 错误，说明 node_modules 不完整
# 解压完整的 node_modules
tar -xzf /tmp/openclaw-node_modules.tar.gz -C /usr/lib/node_modules/
```

### 验证

```bash
openclaw --version
# OpenClaw 2026.3.13 (61d171a)
```

## 常见坑

### 坑 1：postinstall 脚本被跳过导致缺少构建产物

```
Error: missing dist/entry.(m)js (build output)
```

原因：`npm install --ignore-scripts` 跳过了部分构建步骤。解决：完整打包 node_modules 后再传。

### 坑 2：native 模块版本不匹配

如果目标机器 Node.js 版本与打包机器不同，native 模块（如 `sharp`、`libsignal`）可能无法运行。需要：

- 确保 Node.js 大版本一致（建议使用 nodesource 安装相同版本）
- 或在目标机器上单独编译 native 依赖

### 坑 3：可选依赖被跳过

`npm install --ignore-scripts` 也会跳过可选依赖。如果业务需要这些依赖，需要手动安装：

```bash
npm install -g /tmp/openclaw-*.tgz
npm install --prefix=/usr/lib/node_modules/openclaw <缺失的包>
```

## 总结

| 步骤 | 命令 |
|------|------|
| 本地打包 | `npm pack openclaw@latest` |
| 传文件 | `scp *.tgz root@target:/tmp/` |
| 安装 | `npm install -g /tmp/openclaw-*.tggz` |
| 补全 node_modules | `tar -xzf node_modules.tar.gz -C /usr/lib/node_modules/` |
| 验证 | `openclaw --version` |

这个方法比 `npm ci --offline` 更可靠，因为是完整的 tarball 而非 lockfile 驱动。
