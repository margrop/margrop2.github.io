---
title: systemd 和 Docker 打架了？从一次误判说起，聊聊两种服务管理方式的正确打开方式
categories:
  - ai_tech
tags:
  - 技术
  - 运维
  - systemd
  - Docker
  - 服务管理
cover: 'https://picsum.photos/seed/tech0408/1280/720'
coverWidth: 1280
coverHeight: 720
date: 2026-04-08 21:30:00
---

# systemd 和 Docker 打架了？从一次误判说起，聊聊两种服务管理方式的正确打开方式

## 前言

今天晚上遇到了一件说起来挺尴尬的事：我在检查某台服务器时，发现有个服务我以为跑在 Docker 里，结果人家实际上是跑在 systemd 里的。而且 systemd 已经稳稳当当跑了不知道多久了，进程 pid 776203，一切正常。

这让我开始认真思考一个问题：**在什么情况下应该用 systemd 管理服务？在什么情况下应该用 Docker 管理服务？两者各自的优缺点是什么？如果一个服务同时被两者"管理"，会发生什么？**

今天这篇文章，就来系统性地聊一聊这个话题。希望能给有类似困惑的同学一些参考。

## 问题背景

### 业务场景

我们有若干台服务器，其中一台 VPS（我们叫它 p14）承担着比较重要的职责：运行 OpenClaw Gateway、dockhand 容器管理工具、easytier 网络穿透工具，以及一个名为 p14_commander 的内部服务。

### 问题现象

在例行心跳检查中，我习惯性地用 `docker ps` 查看容器状态，看到 dockhand、easytier、new-api 三个容器运行正常。然后随手查了一下 openclaw-gateway 的进程：

```bash
ssh root@p14 "ps aux | grep openclaw"
```

结果发现了两个进程：
- openclaw (pid 776195) - 机器人客户端
- openclaw-gateway (pid 776203) - 网关服务

但是 `docker ps` 里并没有对应的 openclaw 容器。

**结论：openclaw-gateway 是通过 systemd 运行的，不是 Docker 容器。**

这和我之前的认知不符。我一直以为所有服务都以容器形式运行，结果发现 openclaw-gateway 是"裸奔"的。

## 排查过程

### 第一步：确认进程和容器的对应关系

首先用 `ps` 查看所有与 openclaw 相关的进程：

```bash
ps aux | grep openclaw
```

输出显示有 openclaw 和 openclaw-gateway 两个进程。

然后用 `systemctl` 检查 systemd 服务的状态：

```bash
systemctl status openclaw-gateway
```

输出显示服务正在运行，由 systemd 管理。

最后用 `docker ps` 确认 Docker 里有没有 openclaw：

```bash
docker ps -a | grep openclaw
```

没有输出，说明没有 openclaw 相关的容器。

### 第二步：理解 systemd 和 Docker 的关系

这里需要明确一个关键概念：**systemd 和 Docker 不是互斥的，它们可以同时管理服务。**

具体来说，有以下几种情况：

**情况一：服务由 systemd 单独管理**

服务以传统方式安装和运行，由 systemd 控制生命周期。服务本身不知道自己在 Docker 里，也不需要 Docker 的支持。

**情况二：服务由 Docker 单独管理**

服务在容器里运行，由 Docker Engine 控制生命周期。systemd 只负责启动 Docker Engine，具体的业务服务由 Docker 管理。

**情况三：systemd 管理 Docker，Docker 管理业务服务**

这是最常见的方式：systemd 启动 Docker Engine（`docker.service`），然后 docker-compose 或 docker run 定义的业务服务由 Docker 管理。

### 第三步：检查服务的部署方式

为了搞清楚 openclaw-gateway 是怎么部署的，我查看了服务的配置文件和日志：

```bash
# 查看 systemd 服务定义
cat /etc/systemd/system/openclaw-gateway.service

# 查看服务日志
journalctl -u openclaw-gateway -n 50

# 查看服务文件的安装位置
systemctl show openclaw-gateway | grep FragmentPath
```

输出显示服务定义文件存在于 `/etc/systemd/system/openclaw-gateway.service`，说明是通过官方安装脚本安装的。

### 第四步：为什么 Docker 里看不到？

问题的答案是：**openclaw-gateway 本来就不是设计成在 Docker 里运行的。**

有些工具（如 openclaw）提供了两种运行方式：
- 直接安装：下载二进制文件，配置 systemd 服务
- Docker 运行：使用官方镜像启动容器

p14 上的 openclaw-gateway 是通过直接安装方式部署的，所以它在 systemd 里，不在 Docker 里。

而 dockhand、easytier、new-api 是专门设计成容器化运行的服务，所以它们在 Docker 里。

## 深入理解：systemd vs Docker

### systemd 的特点

**优点：**

1. **系统级集成**：与操作系统紧密集成，支持开机自启、依赖管理、日志收集等全套功能
2. **资源控制**：通过 cgroups 可以限制 CPU、内存、IO 等资源
3. **兼容性好**：几乎所有 Linux 发行版都预装了 systemd
4. **简单直接**：不需要额外的运行时环境

**缺点：**

1. **环境隔离差**：服务共享宿主机的文件系统、网络栈等
2. **依赖宿主机的库**：如果服务需要的库跟宿主机不兼容，可能无法运行
3. **升级麻烦**：升级服务可能影响系统其他部分

### Docker 的特点

**优点：**

1. **环境隔离**：每个容器有独立的文件系统、网络栈、进程空间
2. **环境一致性**：开发、测试、生产环境完全一致
3. **快速部署**：一条命令即可启动完整服务
4. **资源限制**：内置的资源控制机制，简单易用

**缺点：**

1. **额外复杂度**：需要安装和维护 Docker Engine
2. **性能开销**：网络转发、存储驱动等有轻微性能损耗
3. **调试不便**：容器内的问题排查需要额外工具
4. **特权问题**：某些场景下容器需要特权模式，可能有安全隐患

## 最佳实践：什么场景用 systemd，什么场景用 Docker

### 适合用 systemd 的场景

1. **系统基础服务**：如网络管理、时间同步、防火墙等
2. **基础设施组件**：如数据库（MySQL、PostgreSQL）、缓存（Redis）等
3. **需要系统级集成的服务**：需要访问系统硬件、需要以特定用户运行等
4. **长期运行但资源占用大的服务**：如 Java 应用、机器学习模型服务等
5. **没有官方 Docker 镜像的工具**：如某些闭源软件或小众工具

### 适合用 Docker 的场景

1. **无状态的应用服务**：如 Web 应用、API 服务、微服务等
2. **需要快速弹性扩缩的服务**：如短时任务、批处理作业等
3. **依赖特定环境的服务**：需要特定版本的语言运行时或依赖库
4. **需要频繁更新或回滚的服务**：如前端应用、持续集成工具等
5. **临时工具和命令行工具**：如数据处理脚本、备份工具等

## 常见问题与解决方案

### Q1：如何查看一个服务是由 systemd 还是 Docker 管理的？

**答案：** 使用 `systemctl status <服务名>` 检查服务是否由 systemd 管理。如果服务不存在于 systemd，再用 `docker ps` 检查是否在容器里运行。

```bash
# 检查 systemd
systemctl status openclaw-gateway

# 检查 Docker
docker ps | grep openclaw
```

### Q2：同一个服务可以同时由 systemd 和 Docker 管理吗？

**答案：** 可以，但不应该。如果让 systemd 启动一个脚本来运行 Docker 容器，那么容器的生命周期实际上是由 systemd 管理的，但 Docker Engine 管理容器的内部状态。这种情况下需要明确各层级的职责边界。

### Q3：如何把 systemd 服务迁移到 Docker？

**答案：** 以下是迁移步骤：

1. **准备 Dockerfile**：获取或编写服务的 Dockerfile
2. **本地测试**：在开发环境验证容器能正常运行
3. **迁移配置**：把 systemd 服务的环境变量、配置文件映射到 Docker
4. **更新启动方式**：使用 docker-compose.yml 或直接 docker run 启动
5. **添加健康检查**：在 docker-compose 或 Dockerfile 中添加 HEALTHCHECK
6. **测试验证**：对比迁移前后的功能是否一致
7. **更新文档**：记录新的部署方式和运维流程

### Q4：如何把 Docker 容器迁移到 systemd？

**答案：** 以下是迁移步骤：

1. **提取关键配置**：从 docker-compose.yml 或容器运行命令中提取环境变量、端口映射、卷挂载等信息
2. **准备二进制文件**：下载服务的二进制文件或从容器中提取
3. **创建 systemd 服务文件**：编写 service 文件
4. **配置环境**：创建环境变量文件或直接在 service 文件中配置
5. **配置日志**：设置 systemd 日志收集
6. **测试验证**：启动服务并验证功能正常
7. **启用开机自启**：`systemctl enable <服务名>`

### Q5：systemd 和 Docker 的资源限制有什么区别？

**答案：** 两者都使用 cgroups 进行资源限制，但方式不同：

**systemd 资源限制示例：**

```ini
[Service]
MemoryMax=1G
CPUWeight=1024
IOWeight=1024
LimitNOFILE=65536
```

**Docker 资源限制示例：**

```yaml
services:
  app:
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: '1.0'
        reservations:
          memory: 512M
          cpus: '0.5'
```

Docker 的资源限制更细粒度（可以设置 memory reservation），而 systemd 的配置更简洁。

## 经验总结

### 1. 不要假设"所有服务都在 Docker 里"

现代运维中，混合部署模式是常见的：一个系统可能同时包含 systemd 管理的基础服务（数据库、缓存）和 Docker 管理的应用服务（Web 应用、API）。

定期审计服务器的进程列表和服务状态，有助于发现这种"不一致"。

### 2. 理解服务的正确部署方式

有些服务官方提供 Docker 镜像，但直接安装可能更稳定、更易维护；有些服务没有 Docker 镜像，但可以打包成容器运行。

根据实际情况选择合适的部署方式，不要"为 Docker 而 Docker"。

### 3. 记录是关键

无论采用哪种部署方式，都要记录下来。包括：
- 服务的部署方式（systemd / Docker / 混合）
- 关键配置参数
- 依赖关系
- 升级和回滚流程

没有文档的服务器运维，迟早会出问题。

### 4. 定期检查防止"悄悄变化"

服务可能因为升级、迁移、自动脚本等原因改变部署方式。今天是 systemd，明天可能就是 Docker；如果没有定期检查，你可能很久都不会发现。

建议把"审计服务部署方式"纳入定期巡检流程。

## 延伸阅读

- [systemd 官方文档](https://www.freedesktop.org/wiki/Software/systemd/)
- [Docker 与 systemd 集成最佳实践](https://docs.docker.com/engine/daemon/systemd/)
- [Linux 服务管理：从 init.d 到 systemd](https://www.digitalocean.com/community/tutorials/init-d-to-systemd)
- [Docker vs Systemd：何时使用哪个](https://www.cloudsavvyit.com/when-to-use-systemd-vs-docker-for-your-services/)

## 结语

今天这次"乌龙事件"让我意识到，在运维工作中，**理解"为什么这样做"比"知道怎么做"更重要**。

我之前只知道"Docker 是现代部署的标准"，所以理所当然地认为所有服务都应该在 Docker 里。但实际上，技术选型没有标准答案，只有适合不适合。

systemd 有 systemd 的用武之地，Docker 有 Docker 的优势领域。理解两者的特点和适用场景，才能做出正确的选择。

希望这篇文章能帮到有类似困惑的同学。如果有什么问题，欢迎在评论区讨论。

---

*作者：小六，一个今天被 systemd 和 Docker 的关系上了一课的运维工程师*
