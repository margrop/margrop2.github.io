---
title: Docker容器网络互通排障全流程：从Bridge到iptables的深度排查
categories:
  - ai_tech
tags:
  - 技术
  - 运维
  - Docker
  - 网络
  - 容器
cover: 'https://picsum.photos/seed/tech0323/1280/720'
coverWidth: 1280
coverHeight: 720
date: 2026-03-23 21:30:00
---

## 前言

容器网络互通是Docker部署中最容易出问题的环节之一。相比传统VM网络，容器网络多了好几层抽象——Bridge、iptables、veth pair、overlay……任何一个环节出问题，都会导致容器之间无法通信。

本文记录一次典型的跨宿主机容器网络互通问题排查全过程，从现象到根因到解决，提供可复用的排障思路和一键脚本。

## 问题背景

### 业务场景

在多台服务器上使用Docker Compose部署了一套微服务架构，各容器之间需要通过内部网络互通：

- `web` 服务（前端Nginx）
- `api` 服务（Python/Go后端）
- `db` 服务（MySQL数据库）

三台服务器各运行部分容器，部分请求需要跨服务器访问。例如p14（某VPS）上的web容器需要访问VM152上的api容器。

### 问题现象

部署完成后，同一宿主机上的容器之间通信正常，但跨宿主机通信全部失败：

```
# 从p14的web容器访问同宿主机的api容器
curl http://api:8000/health  ✅ 正常

# 从p14的web容器访问VM152的api容器
curl http://api-host:8000/health  ❌ 连接超时
```

错误信息：`Connection timed out` 或 `No route to host`

### 环境信息

| 节点 | IP | 容器网络 | 说明 |
|------|-----|---------|------|
| p14（某VPS） | 某VPS_IP | 172.18.0.0/16 | Docker Bridge: docker0 |
| VM152 | 某内网IP | 172.19.0.0/16 | Docker Bridge: docker0 |
| VM151 | 某内网IP | 172.20.0.0/16 | Docker Bridge: docker0 |

三个网络地址完全不同，网段也不在同一大段——这为互通埋下了隐患。

## 排查过程

### 第一步：确认Docker网络配置

先检查各宿主机的Docker网络配置：

```bash
# 在各节点执行
docker network ls
docker network inspect bridge
docker network inspect <自定义网络名>
```

发现各节点使用的是默认的 `bridge` 网络，且网段配置如下：

```
p14:  172.17.0.0/16
VM152: 172.18.0.0/16  
VM151: 172.19.0.0/16
```

问题初步定位：**三个节点的Docker Bridge网段完全不同，且互不重叠**。

Docker默认的Bridge模式下，不同宿主机的容器处于完全隔离的网络中，无法直接互通。这是正常行为，不是bug。

### 第二步：理解Docker网络模式

Docker提供多种网络模式：

| 模式 | 说明 | 跨主机互通 |
|------|------|-----------|
| bridge | 默认模式，使用docker0网桥 | ❌ 不能直接互通 |
| host | 容器共享宿主机网络 | ✅ 可以，但易端口冲突 |
| overlay | Docker Swarm模式，自带VXLAN隧道 | ✅ 可以 |
| macvlan | 给容器分配真实MAC，挂在物理网络上 | ✅ 可以 |

要实现跨主机互通，有三种常用方案：

1. **Docker Compose + external networks**：使用自定义bridge网络配合 `--net=host`
2. **Docker overlay**：需要Docker Swarm，比较重
3. **macvlan + 物理网络打通**：最接近物理网络的方案

考虑到生产环境的简洁性，我们选择 **macvlan** 方案。

### 第三步：检查宿主机网络是否支持macvlan

macvlan需要物理网卡支持"混杂模式"。检查方法：

```bash
# 检查网卡是否支持混杂模式
ip link show eth0
# 查看是否有 PROMISC 标志

# 或者用ethtool检查
ethtool eth0 | grep -i promis
# 如果显示 "Promiscuous mode: on" 则支持
```

如果网卡不支持macvlan，需要改用overlay或自定义bridge方案。

### 第四步：创建macvlan网络

在各宿主机上执行以下命令（注意：需要先删除旧的bridge容器）：

```bash
# 在p14上执行
docker network create \
  --driver macvlan \
  --subnet=172.18.0.0/16 \
  --gateway=172.18.0.1 \
  -o parent=eth0 \
  macvlan_net

# 在VM152上执行
docker network create \
  --driver macvlan \
  --subnet=172.19.0.0/16 \
  --gateway=172.19.0.1 \
  -o parent=eth0 \
  macvlan_net
```

### 第五步：发现新问题——网关不通

创建macvlan网络后，发现容器仍然无法跨宿主机通信。

用 `ping` 测试：

```bash
# 从p14的容器ping VM152的网关
ping 172.19.0.1
# 结果：Destination Host Unreachable
```

问题定位：**宿主机之间的路由不通**。

检查网络架构：

```
p14所在网络:  192.168.160.0/24 (假设)
VM152所在网络: 192.168.102.0/24 (假设)
```

两个内网不在同一网段，需要通过路由器/三层交换转发。

### 第六步：检查iptables和路由表

在VM152上检查iptables规则：

```bash
# 查看NAT规则
iptables -t nat -L -n
# 重点关注 POSTROUTING 和 FORWARD 链

# 查看转发是否开启
cat /proc/sys/net/ipv4/ip_forward
# 如果是0，需要开启：echo 1 > /proc/sys/net/ipv4/ip_forward
```

发现 `ip_forward` 是关闭的。开启后再次测试：

```bash
# 开启IP转发（临时，重启失效）
echo 1 > /proc/sys/net/ipv4/ip_forward

# 永久开启
sysctl -w net.ipv4.ip_forward=1
```

但问题依然存在。

深入检查iptables的FORWARD链：

```bash
# 查看filter表的FORWARD链
iptables -L FORWARD -n -v

# 临时放行所有转发流量测试
iptables -P FORWARD ACCEPT
```

测试发现：iptables的FORWARD策略默认是DROP的，阻止了跨宿主机流量。

### 第七步：配置正确的iptables规则

```bash
# 允许Docker网络之间的流量转发
# 注意：需要根据实际网段修改

# 允许p14网络访问VM152网络（示例网段）
iptables -A FORWARD -s 172.18.0.0/16 -d 172.19.0.0/16 -j ACCEPT
iptables -A FORWARD -s 172.19.0.0/16 -d 172.18.0.0/16 -j ACCEPT

# 允许已知Docker网段的流量
iptables -A FORWARD -s 172.0.0.0/8 -d 172.0.0.0/8 -j ACCEPT
```

但这种逐条配置的方式太繁琐，且不够安全。

更好的方案是：**在Docker服务启动时自动配置正确的iptables规则**：

```bash
# 编辑Docker服务配置
vim /etc/systemd/system/docker.service.d/10-macvlan.conf

# 添加以下内容
[Service]
ExecStart=
ExecStart=/usr/bin/dockerd -H fd:// -H tcp://0.0.0.0:2375 \
  --ip-masq=true \
  --ip-forward=true \
  --iptables=true
```

### 第八步：重新测试连通性

```bash
# 重启Docker服务
systemctl daemon-reload
systemctl restart docker

# 再次测试
docker run --rm --net=macvlan_net alpine ping -c 3 172.19.0.x
# 如果能ping通，说明macvlan配置成功
```

## 根因分析

### 为什么默认bridge网络不能跨主机互通？

Docker默认的bridge网络是"单主机"的。`docker0` 网桥只在本机生效，不同宿主机的docker0网桥完全隔离。

当你执行 `docker network inspect bridge` 时，会发现：

```json
{
    "Name": "bridge",
    "Driver": "bridge",
    "Subnet": "172.17.0.0/16",
    "Gateway": "172.17.0.1"
}
```

这个172.17.0.0/16网段只在当前宿主机内有效。另一台宿主机的容器即使也用了172.17.0.0/16，也不会和第一台冲突——因为它们根本不在同一个二层网络中。

### 为什么需要macvlan或overlay？

要让容器跨主机通信，需要在"容器网络"和"物理网络"之间架设桥梁：

- **macvlan**：让容器直接"挂"在物理网络上，容器有自己的MAC和IP，就像真实的物理机一样
- **overlay**：在物理网络之上建立VXLAN隧道，容器在overlay网络中互通，物理网络只负责传输VXLAN数据包

两种方案各有优劣：

| 方案 | 优点 | 缺点 |
|------|------|------|
| macvlan | 性能最好，接近物理网络 | 需要网卡支持混杂模式，配置复杂 |
| overlay | Docker原生支持，易配置 | 性能略有损耗，需要额外存储 |

## 完整解决方案

### 方案一：macvlan方案（推荐用于生产环境）

**前置条件**：
- 网卡支持混杂模式
- 宿主机网络允许macvlan流量

**步骤**：

```bash
# 1. 创建macvlan网络（各宿主机执行，使用不同subnet）
docker network create \
  --driver macvlan \
  --subnet=<各节点独立子网> \
  --gateway=<各节点网关> \
  -o parent=<物理网卡名> \
  --internal \
  macvlan_internal

# 2. 使用网络启动容器
docker run --rm --net=macvlan_internal --ip=<固定IP> -it alpine sh

# 3. 配置iptables允许转发
iptables -A FORWARD -s <各节点子网> -j ACCEPT
iptables -A FORWARD -d <各节点子网> -j ACCEPT
```

### 方案二：overlay方案（推荐用于Docker Swarm环境）

```bash
# 初始化Swarm（Manager节点）
docker swarm init

# 创建overlay网络
docker network create -d overlay --attachable my_overlay_net

# 在任意节点启动容器并加入该网络
docker run --rm --net=my_overlay_net -it alpine sh
```

### 一键排障脚本

以下脚本可快速排查容器网络问题：

```bash
#!/bin/bash
# Docker容器网络排障脚本
# 保存到 /opt/scripts/docker-network-check.sh

set -e

echo "========== Docker 容器网络排障 =========="
echo "时间：$(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# 1. 检查Docker网络列表
echo "[1/7] Docker网络列表："
docker network ls
echo ""

# 2. 检查docker0网桥状态
echo "[2/7] docker0网桥状态："
ip addr show docker0 2>/dev/null || echo "  docker0不存在（可能使用其他网络）"
echo ""

# 3. 检查IP转发
echo "[3/7] IP转发状态："
IP_FORWARD=$(cat /proc/sys/net/ipv4/ip_forward)
echo "  ip_forward = $IP_FORWARD"
if [ "$IP_FORWARD" != "1" ]; then
    echo "  ⚠️  IP转发未开启，可能导致跨宿主机通信失败"
fi
echo ""

# 4. 检查iptables FORWARD策略
echo "[4/7] iptables FORWARD策略："
FORWARD_POLICY=$(iptables -L FORWARD -n | grep "^Chain FORWARD" | awk '{print $4}')
echo "  默认策略: $FORWARD_POLICY"
if [ "$FORWARD_POLICY" = "DROP" ]; then
    echo "  ⚠️  FORWARD策略为DROP，可能阻止容器通信"
fi
echo ""

# 5. 检查Docker网络详情
echo "[5/7] 各Docker网络详情："
for net in $(docker network ls --format '{{.Name}}' | grep -v -E '^(none|host)$'); do
    echo "  --- $net ---"
    docker network inspect $net --format '{{range .IPAM.Config}}Subnet: {{.Subnet}}  Gateway: {{.Gateway}}{{end}}' 2>/dev/null
    echo ""
done

# 6. 检查容器网络连接（需要指定网络名）
echo "[6/7] 跨宿主机连通性测试："
echo "  说明：以下为示例测试，请根据实际环境修改目标IP"
# ping -c 1 -W 1 目标IP 2>/dev/null && echo "  ✅ 到目标IP可达" || echo "  ❌ 到目标IP不可达"
echo ""

# 7. 检查DNS解析（容器间通信通常依赖DNS）
echo "[7/7] 容器DNS配置："
docker run --rm --net=bridge alpine cat /etc/resolv.conf 2>/dev/null || echo "  无法获取DNS配置"
echo ""

echo "========== 排障完成 =========="
echo ""
echo "常见问题处理建议："
echo "1. IP转发未开：sysctl -w net.ipv4.ip_forward=1"
echo "2. FORWARD被DROP：iptables -P FORWARD ACCEPT"
echo "3. 跨主机不通：检查物理网络路由或使用overlay/macvlan"
echo "4. DNS解析失败：检查自定义网络的DNS配置"
```

使用方法：

```bash
chmod +x /opt/scripts/docker-network-check.sh
/opt/scripts/docker-network-check.sh
```

## 常见问题解答

**Q1：为什么容器能ping通宿主机，但ping不通其他宿主机上的容器？**

A：这通常意味着：
1. 宿主机之间的路由不通（检查网络设备和路由表）
2. iptables的FORWARD策略阻止了流量（检查iptables -L FORWARD）
3. IP转发未开启（检查/proc/sys/net/ipv4/ip_forward）

**Q2：macvlan容器无法获取IP怎么办？**

A：可能的原因：
1. 物理网卡不支持混杂模式（用 `ip link show eth0` 检查）
2. 父网络（parent）配置错误
3. 子网与物理网络冲突

**Q3：overlay网络创建失败怎么排查？**

A：overlay需要Docker Swarm环境。先检查是否已初始化Swarm：
```bash
docker info | grep Swarm
# 如果显示 "Swarm: inactive"，需要先初始化
docker swarm init
```

**Q4：容器内无法解析其他容器的名字怎么办？**

A：Docker的嵌入式DNS（Embedded DNS）只对用户自定义网络（如docker network create创建的网络）生效。默认bridge网络不支持容器间DNS解析。

解决方案：
```bash
# 创建自定义网络
docker network create my_net

# 启动容器时使用该网络
docker run --net=my_net --name=container_a -d image_a
docker run --net=my_net --name=container_b -d image_b

# 现在container_b可以通过container_a的名字访问它
docker exec container_b ping container_a
```

**Q5：如何在不停容器的情况下修复网络问题？**

A：Docker允许动态创建网络并让运行中的容器连接：
```bash
# 创建新网络
docker network create -d bridge --subnet=172.20.0.0/16 my_new_net

# 将运行中的容器连接到新网络（不影响原网络连接）
docker network connect my_new_net <运行中的容器ID>

# 断开旧网络（如需要）
docker network disconnect bridge <容器ID>
```

## 总结

Docker容器网络互通问题排查的核心思路：

1. **先确认是单主机问题还是跨主机问题**：同主机通、跨主机不通，通常是网络层问题
2. **理解Docker网络模式**：bridge/host/overlay/macvlan各有特点，选对方案是关键
3. **逐层排查**：物理网卡 → 网桥 → iptables → 路由表 → 应用层
4. **善用工具**：`ip`、`iptables`、`docker network inspect`、`tcpdump`都是排查利器

希望这篇文章能帮到你。如果有问题，欢迎在评论区讨论。

---

*作者：小六，一个在上海努力搬砖的程序员*
