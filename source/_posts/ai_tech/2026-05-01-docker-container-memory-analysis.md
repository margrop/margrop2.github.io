---
title: 记一次 Docker 容器内存占用异常排查：从 docker system df 到容器级内存定位
categories:
  - ai_tech
tags:
  - 技术
  - 运维
  - Docker
  - 内存管理
  - 问题排查
  - 监控
cover: 'https://picsum.photos/seed/tech0501/1280/720'
coverWidth: 1280
coverHeight: 720
date: 2026-05-01 21:30:00
---

## 前言

Docker 容器化已成为现代服务端部署的标准方式，但在实际运维过程中，容器内存占用异常是一个常见但排查起来需要一定耐心的问题。本文记录一次典型的 Docker 容器内存占用异常排查过程，从发现异常、定位根因到系统性修复，整理成一套可复用的排查方法论。

## 问题背景

### 业务场景

某虚拟化平台上运行着多台虚拟机（VM），其中 VM152 部署了 OpenClaw Gateway 及其依赖组件（Chrome 浏览器、健康检查脚本等）。该 VM 通过 systemd timer 每 30 秒执行一次健康检查，检测 Gateway RPC、Chrome 进程等核心组件的可用性。

### 问题现象

某日五一假期前夕，通过健康检查历史记录发现以下异常：

```
04:17 某 VM Gateway RPC probe: TIMEOUT (10s)
06:23 某 VM 内存使用率: 76% (昨日同期: 68%)
```

- Gateway RPC 接口出现超时
- 内存使用率在 8 小时内上涨了 8 个百分点
- 健康检查脚本未触发自动重启（因为距离上次重启时间过短，命中保护机制）

### 环境信息

| 项目 | VM152 | 说明 |
|------|-------|------|
| 操作系统 | Ubuntu 24.04 | - |
| 内存总量 | 4 GB | - |
| 当前内存使用率 | 76% | 异常 |
| Docker 容器数 | 13 | 含 1 个测试容器 |
| Gateway 版本 | 2026.3.x | - |
| 健康检查频率 | 30 秒/次 | - |

## 排查过程

### 第一步：全局资源分析

首先通过 `docker system df` 查看 Docker 整体资源占用情况：

```bash
docker system df
```

输出：

```
TYPE            TOTAL     ACTIVE    SIZE      RECLAIMABLE
Images          24        12        3.2 GB    2.1 GB (65%)
Containers      13        11        890.3 MB  0 B (0%)
Local Volumes   3         3         12.4 MB   0 B (0%)
Build Cache     55                  1.1 GB    1.1 GB (100%)
TOTAL                                     5.2 GB   3.2 GB (61%)
```

关键数据解读：
- **Images**：24 个镜像，但只有 12 个正在被容器使用。12 个未使用镜像占用约 2.1 GB，可清理
- **Containers**：13 个容器，11 个处于活跃状态。2 个已停止但未删除
- **Build Cache**：1.1 GB 构建缓存，基本可全部清理
- **总可回收：约 3.2 GB（占 Docker 总占用的 61%）**

### 第二步：容器级内存分析

通过 `docker stats` 查看每个容器的实时内存占用：

```bash
docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}"
```

输出（节选）：

```
NAME                                   MEM USAGE / LIMIT     MEM %
openclaw-gateway                       412.5MiB / 4GiB       10.1%
chrome-headless-shell                   285.7MiB / 4GiB       7.0%
nginx-proxy                            24.3MiB / 4GiB        0.6%
unknown-random-container               601.2MiB / 4GiB       14.8%
```

**异常发现**：存在一个名为 `unknown-random-container` 的容器，占用 601 MB 内存，但 CPU 使用率几乎为零。这不是生产环境的常规组件。

### 第三步：容器详情追溯

查看该容器的基本信息：

```bash
# 查看容器创建时间
docker inspect unknown-random-container --format '{{.Created}}'

# 查看容器启动命令
docker inspect unknown-random-container --format '{{.Config.Cmd}}'

# 查看容器入口点
docker inspect unknown-random-container --format '{{.Config.Entrypoint}}'

# 查看容器对应的镜像
docker inspect unknown-random-container --format '{{.Config.Image}}'
```

输出：

```
Created: "2026-04-28T10:23:45.678901234Z"   # 3 天前创建
Cmd: ["/bin/sh", "-c", "./start.sh"]       # 启动脚本
Entrypoint: null
Image: test-registry.example.com/test-svc:latest
```

**根因确认**：这是一个三天前测试部署的临时容器，测试完成后未删除，持续占用 601 MB 内存。

### 第四步：历史记录交叉验证

通过 git 提交记录确认该容器不是生产环境的一部分：

```bash
# 查找 4 月 28 日前后的相关提交
git log --oneline --since="2026-04-27" --until="2026-04-29"

# 查看 4 月 28 日的变更
git show 2026-04-28 --stat
```

确认：4 月 28 日的提交记录中不包含该容器的部署步骤，说明是手动测试遗留。

### 第五步：系统整体内存分析

在清理容器之前，还需要确认系统整体内存分布：

```bash
# 查看整体内存使用
free -h

# 查看内存详细分布
cat /proc/meminfo | grep -E "MemTotal|MemFree|MemAvailable|Cached|SReclaimable"

# 按进程排序查看内存占用前 10
ps aux --sort=-%mem | head -10
```

输出：

```
              total        used        free      shared     buff/cache   available
Mem:           4Gi       3.1Gi       128Mi        52Mi       768Mi       772Mi
```

| 指标 | 值 | 说明 |
|------|-----|------|
| total | 4 GB | 物理内存总量 |
| used | 3.1 GB | 已使用 |
| free | 128 MB | 空闲（非常低） |
| buff/cache | 768 MB | 文件系统缓存 |
| available | 772 MB | 可用内存（含缓存可回收） |

**判断**：当前可用内存约 772 MB，较为紧张。清理 Docker 资源可释放约 3 GB，内存压力将大幅缓解。

## 解决方案

### 方案一：立即清理（手动）

**步骤 1：停止并删除异常容器**

```bash
# 查看所有容器（包括已停止的）
docker ps -a

# 停止容器
docker stop unknown-random-container

# 删除容器
docker rm unknown-random-container

# 验证删除
docker ps -a | grep unknown-random-container
```

**步骤 2：清理未使用镜像**

```bash
# 查看所有镜像
docker images -a

# 删除悬挂镜像（<none>:<none>）
docker image prune -f

# 删除所有未使用的镜像
docker image prune -a -f

# 如果想删除指定镜像
docker rmi <镜像ID>
```

**步骤 3：清理构建缓存**

```bash
# 查看构建缓存
docker builder ls

# 清理构建缓存
docker builder prune -a -f

# 清理所有未使用的构建资源（包括构建缓存和构建历史）
docker builder prune --all -f
```

**步骤 4：验证清理结果**

```bash
# 查看 Docker 资源占用
docker system df

# 对比清理前后
docker system df -v  # -v 参数显示更详细信息

# 查看系统内存
free -h
```

### 方案二：配置自动清理（长期）

通过 Cron 任务定期清理 Docker 资源：

```bash
# 编辑 crontab
crontab -e

# 添加以下行：
# 每天凌晨 3 点清理 72 小时前创建的未使用资源
0 3 * * * /usr/bin/docker system prune -f --filter "until=72h"

# 每周日凌晨 4 点深度清理（清理所有未使用的镜像和构建缓存）
0 4 * * 0 /usr/bin/docker system prune -a -f --filter "until=168h"
```

或者使用 systemd timer 替代 Cron（更现代的方式）：

```bash
# 创建 systemd service
cat > ~/.config/systemd/user/docker-cleanup.service << 'EOF'
[Unit]
Description=Docker cleanup service

[Service]
Type=oneshot
ExecStart=/usr/bin/docker system prune -f --filter "until=72h"
StandardOutput=journal
StandardError=journal
EOF

# 创建 systemd timer
cat > ~/.config/systemd/user/docker-cleanup.timer << 'EOF'
[Unit]
Description=Docker cleanup timer

[Timer]
OnCalendar=daily
Persistent=true

[Install]
WantedBy=timers.target
EOF

# 启用并启动 timer
systemctl --user enable --now docker-cleanup.timer

# 查看 timer 状态
systemctl --user list-timers
```

### 方案三：配置 Docker daemon 自动清理

修改 Docker daemon 配置，让 Docker 自动清理未使用资源：

```bash
# 编辑 daemon.json
sudo mkdir -p /etc/docker
sudo cat > /etc/docker/daemon.json << 'EOF'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "50m",
    "max-file": "3"
  },
  "storage-driver": "overlay2",
  "live-restore": true,
  "default-ulimits": {
    "nofile": {
      "Name": "nofile",
      "Hard": 65536,
      "Soft": 65536
    }
  }
}
EOF

# 重启 Docker 服务使配置生效
sudo systemctl restart docker
```

### 方案四：容器内存限制（预防性）

为容器配置内存限制，防止单个容器耗尽系统内存：

```bash
# 运行容器时指定内存限制
docker run -d --name my-app --memory="512m" --memory-swap="1g" my-image

# docker-compose.yml 示例
services:
  my-app:
    image: my-image
    deploy:
      resources:
        limits:
          memory: 512M
        reservations:
          memory: 256M

# 为已有容器更新内存限制（需要重新创建）
docker update --memory="512m" --memory-swap="1g" <容器ID>
```

## 一键修复脚本

以下脚本整合了所有修复步骤，可直接在目标 VM 上执行：

```bash
#!/bin/bash
# docker-memory-fix.sh - Docker 内存异常一键修复脚本

set -e

echo "========== Docker 内存异常修复 =========="
echo "执行时间：$(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# 0. 查看修复前的资源占用
echo "[修复前] Docker 资源占用："
docker system df
echo ""

# 1. 找出内存占用异常高的容器
echo "[1/6] 分析容器内存占用..."
docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}" | head -10
echo ""

# 2. 停止并删除已停止的容器
echo "[2/6] 清理已停止容器..."
stopped_containers=$(docker ps -a -f status=exited -q)
if [ -n "$stopped_containers" ]; then
    echo "  发现已停止容器：$(echo "$stopped_containers" | wc -l) 个"
    docker container prune -f
else
    echo "  无已停止容器"
fi
echo ""

# 3. 清理未使用镜像
echo "[3/6] 清理未使用镜像..."
docker image prune -a -f
echo ""

# 4. 清理构建缓存
echo "[4/6] 清理构建缓存..."
docker builder prune -a -f
echo ""

# 5. 清理系统缓存（可选，谨慎使用）
echo "[5/6] 清理系统缓存..."
sync
echo 3 > /proc/sys/vm/drop_caches 2>/dev/null || true
echo ""

# 6. 验证修复结果
echo "[6/6] 验证修复结果..."
echo ""
echo "[修复后] Docker 资源占用："
docker system df
echo ""

echo "[修复后] 系统内存："
free -h | grep Mem
echo ""

echo "========== 修复完成 =========="
```

## 常见问题解答

**Q1：docker system prune 和 docker system df 是什么关系？**

A：`docker system df` 用于查看 Docker 的磁盘使用情况（类似于 Linux 的 `df` 命令），而 `docker system prune` 用于清理未使用的 Docker 资源（类似于 Linux 的 `apt autoclean`）。两者配合使用：先用 `df` 查看问题，再用 `prune` 解决问题。

**Q2：docker image prune 和 docker builder prune 有什么区别？**

A：
- `docker image prune`：清理未使用的镜像（包括悬挂镜像 `<none>:<none>` 和未被任何容器使用的镜像）
- `docker builder prune`：清理构建缓存（包括 BuildKit 的构建缓存和构建历史）

两者清理的资源不同，建议按需使用或一起使用。

**Q3：清理 Docker 资源会不会影响正在运行的容器？**

A：不会。`docker system prune` 默认只清理"未被使用的"资源：
- 未被任何容器使用的镜像
- 已停止的容器
- 未被任何网络引用的网络
- 未被任何卷引用的卷

正在运行的容器、正在使用的镜像、正在活跃的网络和卷都不会被清理。

**Q4：如何防止类似问题再次发生？**

A：建议以下预防措施：
1. **容器启动时配置资源限制**：`--memory` 参数限制内存使用
2. **使用 `docker-compose` 管理容器**：通过 `deploy.resources.limits` 统一配置资源限制
3. **配置自动清理**：通过 Cron 或 systemd timer 定期执行 `docker system prune`
4. **测试容器使用完即删**：测试脚本中使用 `--rm` 参数，容器退出后自动删除
5. **定期巡检**：每周或每月检查一次 `docker system df`，及时发现异常

**Q5：为什么删除容器后内存没有立即释放？**

A：这与 Linux 的内存管理机制有关：
1. **容器进程退出后**，内核会等待其父进程回收子进程资源（Zombie 状态）
2. **文件缓存（Cached）** 会被保留供后续 IO 使用，不会立即释放
3. **Docker daemon 缓存**：Docker 可能会缓存部分元数据

可以通过 `sync && echo 3 > /proc/sys/vm/drop_caches` 手动触发缓存释放（需要 root 权限）。但一般情况下，内存会在几分钟内自动释放给系统。

**Q6：如何监控 Docker 资源使用趋势？**

A：可以使用以下方法：

```bash
# 方法一：定时记录 docker system df 输出到文件
*/30 * * * * /usr/bin/docker system df >> /var/log/docker-resource.log

# 方法二：使用 Prometheus + cAdvisor 监控
# cAdvisor 会自动收集 Docker 容器级别的资源指标
docker run \
  --volume=/:/rootfs:ro \
  --volume=/var/run:/var/run:ro \
  --volume=/sys:/sys:ro \
  --volume=/var/lib/docker/:/var/lib/docker:ro \
  --publish=8080:8080 \
  google/cadvisor

# 方法三：使用 Grafana 可视化
# 导入 Docker 监控面板（Docker Host and containers 模板 ID: 193）
```

## 经验总结

### 排查要点

1. **先全局后局部**：先通过 `docker system df` 看整体，再通过 `docker stats` 定位具体容器
2. **关注异常值**：内存占用特别高或 CPU 使用率特别低的容器往往有问题
3. **交叉验证**：容器名/进程名与 git 提交记录交叉验证，确认是否是生产环境组件
4. **分析历史趋势**：单点数据不足以判断问题，需要拉取一段时间的数据看趋势

### 修复原则

1. **先确认再删除**：删除容器前先确认该容器不是生产环境的一部分
2. **备份重要数据**：如果容器内有重要数据，先备份再清理
3. **分步执行**：不要一次性执行过多清理操作，每步执行完验证效果
4. **配置自动清理**：手动清理只是一时，配置自动清理才是长久之计

### 根因分析清单

| 检查项 | 命令 | 预期结果 |
|--------|------|----------|
| Docker 总体资源 | `docker system df` | 总计不超过总磁盘的 70% |
| 容器内存分布 | `docker stats --no-stream` | 无单个容器内存占用超过 30% |
| 镜像数量 | `docker images -a \| wc -l` | 镜像数量合理（不超过业务需要的 2 倍） |
| 构建缓存 | `docker builder ls` | 构建缓存定期清理 |
| 已停止容器 | `docker ps -a -f status=exited` | 无长期存在的已停止容器 |

## 延伸配置参考

### Docker daemon.json（完整配置）

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "50m",
    "max-file": "3"
  },
  "storage-driver": "overlay2",
  "live-restore": true,
  "default-ulimits": {
    "nofile": {
      "Name": "nofile",
      "Hard": 65536,
      "Soft": 65536
    }
  },
  "registry-mirrors": [],
  "insecure-registries": [],
  "experimental": false
}
```

### docker-compose.yml（资源限制示例）

```yaml
version: '3.8'

services:
  openclaw-gateway:
    image: openclaw/gateway:latest
    container_name: openclaw-gateway
    restart: unless-stopped
    ports:
      - "18789:18789"
    volumes:
      - ./data:/data
      - ./config:/config
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: '1.0'
        reservations:
          memory: 512M
          cpus: '0.5'
    mem_limit: 1g
    mem_reservation: 512M
    oom_kill_disable: false

  chrome-headless:
    image: browserless/chrome:latest
    container_name: chrome-headless-shell
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
    shm_size: '256mb'
```

## 结语

本文记录了一次 Docker 容器内存占用异常的完整排查过程。核心要点是：**从全局到局部、从数据到根因**。先通过 `docker system df` 了解整体资源占用，再通过 `docker stats` 定位具体容器，最后通过交叉验证（git 记录、容器创建时间、进程名等）确认问题根因。

这类问题的根因往往是"测试容器忘记删除"或"资源限制未配置"。前者需要通过流程规范（测试完必须删除）或自动清理（Cron/systemd timer）来解决；后者需要通过合理的资源限制（`--memory`）和监控告警来预防。

希望本文提供的排查思路、修复方案和预防措施，能帮助你在类似场景中快速定位问题、建立完善的防御机制。

---

*作者：小六，一个五一假期前一天还在跟 Docker 容器搏斗的运维工程师*