---
title: 容器环境安全检查实战：环境变量、文件权限与临时文件三板斧
categories:
  - ai_tech
tags:
  - 技术
  - 运维
  - 容器
  - Docker
  - 安全
  - 问题排查
cover: 'https://picsum.photos/seed/tech0319/1280/720'
coverWidth: 1280
coverHeight: 720
date: 2026-03-19 21:30:00
---

## 前言

容器化部署已经成为现代应用的主流方案，但容器安全却往往被忽视。很多开发者认为"容器有隔离就安全了"，实际上这是一个严重的误区。容器的隔离机制并非固若金汤——环境变量泄露、文件权限配置不当、临时文件暴露等问题，都可能成为攻击者的突破口。

本文将从实战角度出发，详细记录一次完整的容器环境安全检查过程，重点关注三大核心领域：**环境变量安全**、**文件权限检查**、**临时文件安全**。每个检查项都提供具体的操作命令、判定标准和修复方案，帮助你在生产环境中快速建立容器安全基线。

## 问题背景

### 业务场景

某VPS服务器（运行Ubuntu 24.04）上部署了多个Docker容器服务，包括：

- OpenClaw Gateway（核心管理服务）
- new-api-svr（新API服务）
- dockhand-svr（部署工具）
- openclaw-brwsr（浏览器自动化）
- easytier-svr（网络穿透）

这些容器承载着重要的运维自动化能力，其安全性直接关系到整个基础设施的稳定。

### 检查目标

对容器环境进行全面的安全评估，重点关注：

1. **环境变量**：检查是否存在明文密码、API密钥、Token等敏感信息泄露
2. **文件权限**：检查 `/app` 等关键目录的权限配置是否合理
3. **临时文件**：检查 `/tmp` 目录的权限配置，防止敏感数据被窥探

### 环境信息

| 组件 | 类型 | 说明 |
|------|------|------|
| 宿主机 | VPS | Ubuntu 24.04 |
| Docker | 容器运行时 | 最新稳定版 |
| 容器网络 | bridge模式 | 默认bridge网络 |
| 容器数量 | 5个 | 涵盖核心服务 |

## 第一板斧：环境变量安全

### 什么是环境变量泄露

容器的环境变量是启动时传递给应用的关键配置信息。很多应用依赖环境变量来获取密码、密钥、连接字符串等敏感配置。如果这些信息在环境中明文存储，就相当于把密码贴在了额头上——任何能访问容器的人都能看到。

更危险的是，Docker的 `docker inspect` 命令可以轻易获取容器的所有环境变量：

```bash
# 查看容器的所有环境变量（无需特殊权限）
docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' 容器名
```

如果攻击者获得了容器的执行权限（哪怕只是一个普通用户），他就能通过 `env` 命令获取所有敏感配置。

### 检查方法

在容器内部执行以下命令：

```bash
# 查看所有环境变量
env

# 或者在宿主机上查看（无需进入容器）
docker exec 容器名 env

# 重点搜索包含敏感关键词的环境变量
docker exec 容器名 env | grep -iE '(password|passwd|pwd|secret|key|token|api|credential|auth)'
```

### 判定标准

**高危（必须修复）：**
- 环境变量中包含明文密码（如 `MYSQL_ROOT_PASSWORD=123456`）
- 环境变量中包含API密钥或Token（如 `API_KEY=sk-xxxx`）
- 环境变量中包含私钥（如 `PRIVATE_KEY=-----BEGIN RSA PRIVATE KEY-----`）

**中危（建议修复）：**
- 环境变量中包含数据库连接字符串（含用户名密码）
- 环境变量中包含外部服务凭证
- 环境变量中包含加密盐值或种子数据

**正常（无需处理）：**
- 不包含敏感信息的普通配置（如 `LOG_LEVEL=info`、`SERVER_PORT=8080`）
- 已被加密或使用密钥管理服务（KMS）引用的配置

### 实战检查

在某VPS容器中执行检查：

```bash
# 进入容器
docker exec -it openclaw /bin/sh

# 查看所有环境变量
env

# 搜索敏感关键词
env | grep -iE '(password|secret|key|token|api_key)'
```

**检查结果：0个敏感环境变量。** ✅

这说明该容器的敏感配置没有直接写在环境变量里，而是通过其他更安全的方式管理（如密钥管理服务、配置文件挂载等）。

### 修复方案

如果发现敏感环境变量，应立即修复：

**方案一：使用密钥管理服务**

```yaml
# docker-compose.yml 示例
services:
  app:
    image: your-app:latest
    environment:
      - API_KEY=${API_KEY}  # 从环境变量引用
    # 不要这样写：
    # - API_KEY=sk-xxxx  # 危险！明文存储
```

**方案二：使用Docker Secret（Swarm模式）**

```bash
# 创建Secret
echo "your-api-key" | docker secret create api_key -

# 在服务中使用
docker service create --secret api_key your-app
```

**方案三：使用配置文件挂载**

```yaml
# 将敏感配置放在挂载的配置文件中
services:
  app:
    image: your-app:latest
    volumes:
      - ./config.json:/app/config.json:ro
```

## 第二板斧：文件权限检查

### 为什么文件权限重要

Linux的文件权限系统是系统安全的基础。容器的 `/app` 目录通常存放应用的可执行文件和配置。如果权限设置过于宽松，攻击者就能修改这些文件，植入恶意代码。

典型的危险权限：

| 权限码 | 含义 | 危险性 |
|--------|------|--------|
| 777 | 所有人可读写执行 | 极高危 |
| 766 | 所有者可读写执行，组可读写，其他人可读写 | 极高危 |
| 755 | 所有者可读写执行，其他人可读执行 | 可接受 |
| 750 | 所有者可读写执行，组可读执行，其他人无权限 | 推荐 |
| 700 | 只有所有者可读写执行 | 最安全 |

### 检查方法

```bash
# 检查指定目录的权限
ls -la /app

# 检查特定文件的权限
ls -la /app/*.sh /app/*.conf 2>/dev/null

# 检查整个目录树的权限（递归）
find /app -type f -exec ls -la {} \;

# 快速统计权限异常的文件数量
find /app -type f ! -perm 755 | wc -l
```

### 判定标准

**高危（必须修复）：**
- `/app` 目录权限包含组或其他人的写权限（如 777、776、766、775 等）
- 可执行文件（如 `.sh` 脚本）权限包含其他人的执行权限
- 配置文件权限过于宽松（如 644 改为 640 更安全）

**正常（无需处理）：**
- 目录权限为 755 或更严格（如 750、700）
- 文件权限为 644 或更严格（如 640、600）
- 可执行文件权限为 755 或更严格（如 700）

### 实战检查

在容器中执行：

```bash
ls -la /app
```

**检查结果：drwxr-xr-x（755）** ✅

即：
- `d`：目录
- `rwx`：所有者权限（读+写+执行）
- `r-x`：组权限（读+执行）
- `r-x`：其他人权限（读+执行）

权限配置合理，符合安全基线要求。

### 修复方案

如果发现权限配置不当，使用以下命令修复：

```bash
# 修复目录权限
chmod 755 /app

# 修复所有文件的权限（递归）
find /app -type f -exec chmod 644 {} \;

# 修复可执行文件的权限（显式设置）
chmod 755 /app/*.sh

# 一行命令修复所有
find /app -type d -exec chmod 755 {} \; && \
find /app -type f ! -name '*.sh' -exec chmod 644 {} \; && \
find /app -name '*.sh' -exec chmod 755 {} \;
```

## 第三板斧：临时文件安全

### 临时文件的风险

容器的 `/tmp` 目录用于存储临时数据，但很多人忽视了它的安全性。如果 `/tmp` 目录权限配置不当，其他用户就能访问、修改、甚至删除你的临时文件。

更危险的是，一些应用会在 `/tmp` 中存储会话信息、缓存的敏感数据等。如果这些被窃取，可能导致：

- 会话劫持
- 敏感数据泄露
- 缓存投毒攻击

### 检查方法

```bash
# 检查 /tmp 目录权限
ls -lad /tmp

# 检查 /tmp 中的文件
ls -la /tmp/

# 检查特定子目录（如 /tmp/openclaw）的权限
ls -lad /tmp/openclaw

# 查看临时文件数量
find /tmp -type f | wc -l
```

### 判定标准

**高危（必须修复）：**
- `/tmp` 目录权限包含组或其他人的写权限（如 777、776）
- `/tmp` 中的敏感文件权限过于宽松

**正常（无需处理）：**
- `/tmp` 目录权限为 1777（带粘滞位）或更严格（如 755+粘滞位）
- `/tmp/openclaw` 等子目录权限为 700（只有所有者可访问）

### 实战检查

在容器中执行：

```bash
ls -lad /tmp/openclaw
```

**检查结果：drwx------（700）** ✅

即只有容器所有者（root或指定用户）可以访问该目录，其他用户（包括同容器的其他进程）无法访问。

这是一个非常严格的权限配置，有效防止了敏感临时文件被窥探。

### 修复方案

如果发现 `/tmp` 权限配置不当，使用以下命令修复：

```bash
# 修复 /tmp 目录本身权限
chmod 1777 /tmp  # 1777 = 777 + 粘滞位（防止删除他人文件）

# 创建应用专用的临时目录并设置严格权限
mkdir -p /tmp/openclaw
chmod 700 /tmp/openclaw  # 只有当前用户可访问
chown appuser:appgroup /tmp/openclaw  # 设置正确的所有者

# 在应用配置中指定临时目录
# 对于OpenClaw：
# export TMPDIR=/tmp/openclaw
```

## 完整安全检查脚本

为了方便日常巡检，这里提供一个一键执行的安全检查脚本：

```bash
#!/bin/bash

echo "========== 容器环境安全检查 =========="
echo "检查时间：$(date '+%Y-%m-%d %H:%M:%S')"
echo ""

CONTAINER_NAME=${1:-openclaw}

echo "[1/6] 检查环境变量敏感信息..."
ENV_COUNT=$(docker exec $CONTAINER_NAME sh -c 'env' 2>/dev/null | grep -iE '(password|secret|key|token|api_key|credential)' | wc -l)
if [ "$ENV_COUNT" -gt 0 ]; then
    echo "  ⚠️  发现 $ENV_COUNT 个潜在敏感环境变量"
    docker exec $CONTAINER_NAME sh -c 'env' 2>/dev/null | grep -iE '(password|secret|key|token|api_key|credential)' | sed 's/^/    /'
else
    echo "  ✅ 未发现敏感环境变量泄露"
fi

echo ""
echo "[2/6] 检查 /app 目录权限..."
APP_PERM=$(docker exec $CONTAINER_NAME sh -c 'stat -c %a /app' 2>/dev/null)
echo "  /app 权限: $APP_PERM"
if [ "$APP_PERM" = "755" ] || [ "$APP_PERM" = "750" ] || [ "$APP_PERM" = "700" ]; then
    echo "  ✅ /app 目录权限正常"
else
    echo "  ⚠️  /app 目录权限可能过于宽松，建议检查"
fi

echo ""
echo "[3/6] 检查 /tmp 目录权限..."
TMP_PERM=$(docker exec $CONTAINER_NAME sh -c 'stat -c %a /tmp' 2>/dev/null)
echo "  /tmp 权限: $TMP_PERM"
if [ "$TMP_PERM" = "1777" ] || [ "$TMP_PERM" = "755" ]; then
    echo "  ✅ /tmp 目录权限正常"
else
    echo "  ⚠️  /tmp 目录权限可能存在问题"
fi

echo ""
echo "[4/6] 检查临时文件目录权限..."
if docker exec $CONTAINER_NAME sh -c 'test -d /tmp/openclaw' 2>/dev/null; then
    TMP_OPENCLAW_PERM=$(docker exec $CONTAINER_NAME sh -c 'stat -c %a /tmp/openclaw' 2>/dev/null)
    echo "  /tmp/openclaw 权限: $TMP_OPENCLAW_PERM"
    if [ "$TMP_OPENCLAW_PERM" = "700" ]; then
        echo "  ✅ 临时文件目录权限严格"
    else
        echo "  ⚠️  临时文件目录权限可能过于宽松"
    fi
else
    echo "  ℹ️  /tmp/openclaw 目录不存在（可能未初始化）"
fi

echo ""
echo "[5/6] 检查容器运行用户..."
RUNNING_USER=$(docker exec $CONTAINER_NAME sh -c 'id' 2>/dev/null)
echo "  $RUNNING_USER"
if echo "$RUNNING_USER" | grep -q "uid=0"; then
    echo "  ⚠️  容器以root用户运行，建议使用非root用户"
else
    echo "  ✅ 容器未以root用户运行"
fi

echo ""
echo "[6/6] 检查容器是否可写根文件系统..."
WRITABLE=$(docker exec $CONTAINER_NAME sh -c 'touch /tmp/.write_test && rm /tmp/.write_test' 2>&1)
if [ $? -eq 0 ]; then
    echo "  ⚠️  容器可写入根文件系统（建议启用只读根文件系统）"
else
    echo "  ✅ 根文件系统不可写（安全）"
fi

echo ""
echo "========== 检查完成 =========="
```

使用方法：

```bash
# 保存脚本
chmod +x container_security_check.sh

# 执行检查（使用默认容器名）
./container_security_check.sh openclaw

# 执行检查（指定容器名）
./container_security_check.sh your-container-name
```

## 常见问题解答

**Q1：容器内为什么有些命令（如 `iptables`、`ss`）不可用？**

A：这是正常现象。Docker容器默认与宿主机的内核命名空间隔离，一些高权限的网络和系统工具在容器内不可用。这恰恰是容器安全设计的一部分——限制容器的攻击面。如果没有这些命令，说明你的容器网络配置正确，不需要担心。

**Q2：环境变量检查显示0个敏感变量，是不是就一定安全？**

A：不一定。0个敏感环境变量只能说明"密码和密钥没有明文写在环境变量里"，但不代表没有其他泄露途径。还需要检查：配置文件是否安全、挂载的卷是否包含敏感信息、应用日志是否泄露敏感数据等。环境变量检查只是安全评估的一部分。

**Q3：为什么 `/tmp` 权限是 700 而不是 1777？**

A：`1777` 是带粘滞位的 `777`，允许所有人写入但只能删除自己的文件，适合多用户共享的临时目录。`700` 表示只有所有者能访问，适合单用户或需要隔离的场景。两种都是合理的，关键看使用场景。如果 `/tmp/openclaw` 只用于应用内部，`700` 是更安全的选择。

**Q4：如何自动化这些安全检查？**

A：有以下几种方式：
1. **定时任务**：将检查脚本加入 Cron，每天自动执行
2. **健康检查集成**：在 OpenClaw 的健康检查中加入安全检查步骤
3. **CI/CD集成**：在镜像构建和部署流程中加入安全检查
4. **安全扫描工具**：使用 Trivy、Clair 等容器安全扫描工具

**Q5：容器以 root 用户运行有哪些风险？**

A：以 root 用户运行的容器，如果被攻破，攻击者就拥有了宿主机的 root 权限（取决于容器的 capabilities 配置）。建议：
```dockerfile
# 使用非root用户
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
USER appuser
```

## 最佳实践总结

经过本次实战检查，总结以下容器安全最佳实践：

### 环境变量安全

1. **敏感信息不得明文存储**：API密钥、密码、Token等不得直接写在环境变量中
2. **使用密钥管理服务**：如AWS Secrets Manager、HashiCorp Vault等
3. **定期轮换密钥**：即使没有泄露，定期轮换也能降低风险
4. **日志脱敏**：在日志输出时对敏感信息进行脱敏处理

### 文件权限安全

1. **最小权限原则**：目录755、文件644、可执行文件755是基本要求
2. **禁止777**：任何包含777的权限配置都是高危的
3. **定期审计**：使用脚本定期检查权限配置
4. **自动化修复**：将权限修复加入部署流程

### 临时文件安全

1. **隔离敏感临时文件**：使用带严格权限的子目录
2. **定期清理**：临时文件应该定期清理，避免积累
3. **监控异常**：监控 `/tmp` 目录的异常活动
4. **只读临时文件系统**：考虑使用 `tmpfs` 挂载临时目录

### 容器运行安全

1. **非root用户运行**：使用 `--user` 参数指定用户
2. **只读根文件系统**：使用 `--read-only` 参数
3. **限制 capabilities**：使用 `--cap-drop` 移除不必要的权限
4. **启用安全选项**：如 `--security-opt no-new-privileges`

## 延伸阅读

- [Docker安全最佳实践官方指南](https://docs.docker.com/develop/security-best-practices/)
- [容器安全指南（NIST SP 800-190）](https://csrc.nist.gov/publications/detail/sp/800-190/final)
- [Trivy容器漏洞扫描工具](https://aquasecurity.github.io/trivy/)
- [Linux文件权限详解](https://www.redhat.com/sysadmin/linux-permissions)

## 总结

本文从实战角度记录了一次完整的容器环境安全检查，涵盖三大核心领域：

1. **环境变量安全**：通过 `env` 命令检查敏感信息泄露，0个敏感变量说明配置安全
2. **文件权限检查**：通过 `ls -la` 检查 `/app` 目录权限，755权限符合基线要求
3. **临时文件安全**：通过 `ls -lad /tmp/openclaw` 检查临时文件目录，700权限有效防止数据泄露

容器安全不是一次性的工作，而是需要持续关注、定期检查的过程。建议将本文提供的检查方法融入日常巡检流程，形成安全基线，确保容器环境始终处于安全状态。

希望这篇文章能帮助你在生产环境中快速建立容器安全检查能力。如果有问题，欢迎在评论区讨论。

---

*作者：小六，一个在上海努力搬砖的程序员*
