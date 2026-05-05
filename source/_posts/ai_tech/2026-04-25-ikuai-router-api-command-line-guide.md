---
title: iKuai 路由器 API 完全指北：通过命令行自动获取网络状态、设备列表与端口映射
categories:
  - ai_tech
tags:
  - 技术
  - 运维
  - iKuai
  - API
  - 网络
  - 自动化
cover: 'https://picsum.photos/seed/tech0425/1280/720'
coverWidth: 1280
coverHeight: 720
date: 2026-04-25 21:30:00
---

## 前言

做运维工作的人，少不了要和路由器打交道。以前我管理路由器，要么登录 Web 管理界面点点点，要么查文档找 CLI 命令。但最近我发现了一个更高效的方式——直接调用路由器的 REST API。

本文以 iKuai 路由器为例，详细记录如何通过命令行调用其 API，包括认证机制、常用功能、返回值解析，以及一些实战经验。内容适用于需要自动化管理内网路由器、获取网络设备信息的运维人员。

## iKuai API 认证机制详解

iKuai 路由器的 Web 管理界面背后是一套 REST API。最有意思的是它的认证机制——既不是 Basic Auth，也不是 OAuth，而是一种基于 Cookie + Session Key 的简单认证。

### 认证流程

登录 API 地址：`http://<路由器IP>/Action/login`

请求体需要包含两个字段：

- `passwd`：原密码的 MD5 哈希值（32位，不加盐）
- `pass`：字符串 `salt_113` 拼接上原密码，然后做 Base64 编码

```bash
# 登录 iKuai 路由器并保存 session
PASS="你的路由器密码"
ROUTER_IP="192.168.x.x"

SESS_KEY=$(curl -s -c /tmp/ikuai_cookie.txt \
  "http://${ROUTER_IP}/Action/login" \
  -H 'Content-Type: application/json;charset=UTF-8' \
  -d "{\"username\":\"openclaw\",\"passwd\":\"$(echo -n $PASS | md5sum | cut -d' ' -f1)\",\"pass\":\"$(echo -n salt_113$PASS | base64)\"}" \
  --insecure | python3 -c "import sys,json; print(json.load(sys.stdin)['Result'])")

echo "Session Key: $SESS_KEY"
```

登录成功后，服务器会在响应中返回 `sess_key`，同时 Set-Cookie 中也会包含这个值。我习惯把 cookie 保存到文件里，方便后续请求复用。

### 认证字段生成逻辑

很多人第一次看到这个登录逻辑会觉得奇怪：为什么要同时传 MD5 和 Base64 两种格式？

根据实际测试推测，`passwd` 字段可能是给后端 PHP 验证用的（直接比较 MD5 值），而 `pass` 字段是给 JavaScript 验证用的（Base64 编码可以方便地在前端处理）。

这个双重验证机制可能是为了兼容不同版本的 iKuai 固件。

### 后续请求带上 Session Key

登录之后，每次请求 API 都需要在 Cookie 中带上 `sess_key`：

```bash
# 查询系统状态（带上 session cookie）
curl -s "http://${ROUTER_IP}/Action/call" \
  -H 'Content-Type: application/json;charset=UTF-8' \
  -b "username=root; sess_key=${SESS_KEY}" \
  -d '{"func_name":"sysstat","action":"show","param":{"TYPE":"verinfo,cpu,memory"}}' \
  --insecure
```

如果 sess_key 过期或无效，API 会返回错误信息。此时需要重新登录获取新的 sess_key。

## 常用 API 功能码

iKuai 的 API 通过 `func_name` 参数区分不同的功能模块。以下是我在日常运维中经常用到的几个：

### 1. 系统状态（sysstat）

获取路由器的 CPU、内存、系统版本等信息：

```bash
curl -s "http://${ROUTER_IP}/Action/call" \
  -H 'Content-Type: application/json;charset=UTF-8' \
  -b "username=root; sess_key=${SESS_KEY}" \
  -d '{"func_name":"sysstat","action":"show","param":{"TYPE":"verinfo,cpu,memory"}}' \
  --insecure | python3 -m json.tool
```

典型返回：

```json
{
  "verinfo": {
    "core_version": "iKuai8_2_7",
    "build_date": "2024-11-20",
    "main_ver": "8.50.10"
  },
  "cpu": {
    "cpu_usage": 15
  },
  "memory": {
    "total": 512,
    "used": 287,
    "free": 225,
    "usage": 56
  }
}
```

### 2. 线路监控（monitor_iface）

获取 WAN/LAN 接口的流量和状态：

```bash
curl -s "http://${ROUTER_IP}/Action/call" \
  -H 'Content-Type: application/json;charset=UTF-8' \
  -b "username=root; sess_key=${SESS_KEY}" \
  -d '{"func_name":"monitor_iface","action":"show","param":{"TYPE":"iface_check,iface_stream"}}' \
  --insecure | python3 -m json.tool
```

返回内容包括各 WAN 线路的上传/下载速率、连接数、是否在线等信息。如果有负载均衡或双线路配置，这个接口可以直观地看到各线路的负载情况。

### 3. DHCP 终端列表（dhcp_lease）

获取当前分配了 IP 的设备列表——这是我最常用的接口之一：

```bash
curl -s "http://${ROUTER_IP}/Action/call" \
  -H 'Content-Type: application/json;charset=UTF-8' \
  -b "username=root; sess_key=${SESS_KEY}" \
  -d '{"func_name":"dhcp_lease","action":"show","param":{"TYPE":"total,data","limit":"0,100"}}' \
  --insecure | python3 -m json.tool
```

返回示例（已脱敏）：

```json
{
  "result": [
    {
      "ip": "192.168.103.XX",
      "mac": "00:11:22:33:44:55",
      "hostname": "NAS",
      " lease_time": "2026-04-25 18:30:00",
      "online": 1
    },
    {
      "ip": "192.168.103.1XX",
      "mac": "aa:bb:cc:dd:ee:ff",
      "hostname": "VM151",
      " lease_time": "2026-04-25 20:15:00",
      "online": 1
    }
  ],
  "total": 74
}
```

这个接口对于资产盘点和网络设备发现非常有用。通过对比不同时间点的数据，可以发现新增或消失的设备。

### 4. DHCP 静态分配（dhcp_static）

查看 MAC 地址和 IP 的静态绑定关系：

```bash
curl -s "http://${ROUTER_IP}/Action/call" \
  -H 'Content-Type: application/json;charset=UTF-8' \
  -b "username=root; sess_key=${SESS_KEY}" \
  -d '{"func_name":"dhcp_static","action":"show","param":{"TYPE":"data","limit":"0,50"}}' \
  --insecure | python3 -m json.tool
```

如果某些服务器需要固定 IP，但不想手动在每台机器上配置，可以统一在路由器 DHCP 静态分配里管理。

### 5. 端口映射（dnat）

查看当前的端口转发规则：

```bash
curl -s "http://${ROUTER_IP}/Action/call" \
  -H 'Content-Type: application/json;charset=UTF-8' \
  -b "username=root; sess_key=${SESS_KEY}" \
  -d '{"func_name":"dnat","action":"show","param":{"TYPE":"total,data","limit":"0,50"}}' \
  --insecure | python3 -m json.tool
```

返回内容包括端口映射规则的目的 IP、端口、协议、是否启用等。对于需要远程访问内网服务的场景，这个接口可以帮助快速确认映射规则是否正确。

### 6. ARP 表（arp）

查看 ARP 缓存，了解 IP 和 MAC 的对应关系：

```bash
curl -s "http://${ROUTER_IP}/Action/call" \
  -H 'Content-Type: application/json;charset=UTF-8' \
  -b "username=root; sess_key=${SESS_KEY}" \
  -d '{"func_name":"arp","action":"show","param":{}}' \
  --insecure | python3 -m json.tool
```

ARP 表对于排查 IP 冲突或定位未知设备非常有用。

## 实用脚本：自动化巡检

结合上面的 API，可以写一个简单的巡检脚本，自动收集路由器的关键信息：

```bash
#!/bin/bash

# iKuai 路由器巡检脚本
# 用法: ./router_inspect.sh <路由器IP> <密码>

ROUTER_IP="$1"
PASS="$2"
COOKIE_FILE="/tmp/ikuai_${ROUTER_IP//./_}.cookie"

if [ -z "$ROUTER_IP" ] || [ -z "$PASS" ]; then
  echo "用法: $0 <路由器IP> <密码>"
  exit 1
fi

# 登录
SESS_KEY=$(curl -s -c "$COOKIE_FILE" \
  "http://${ROUTER_IP}/Action/login" \
  -H 'Content-Type: application/json;charset=UTF-8' \
  -d "{\"username\":\"openclaw\",\"passwd\":\"$(echo -n $PASS | md5sum | cut -d' ' -f1)\",\"pass\":\"$(echo -n salt_113$PASS | base64)\"}" \
  --insecure | python3 -c "import sys,json; print(json.load(sys.stdin)['Result'])" 2>/dev/null)

if [ -z "$SESS_KEY" ]; then
  echo "登录失败"
  exit 1
fi

API_CALL() {
  curl -s "http://${ROUTER_IP}/Action/call" \
    -H 'Content-Type: application/json;charset=UTF-8' \
    -b "username=root; sess_key=${SESS_KEY}" \
    -d "$(printf '{"func_name":"%s","action":"show","param":%s}' "$1" "$2")" \
    --insecure
}

echo "=== 路由器巡检报告 ==="
echo "时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# 系统状态
echo "【系统状态】"
API_CALL "sysstat" '{"TYPE":"verinfo,cpu,memory"}' | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"版本: {d.get('verinfo',{}).get('main_ver','N/A')}\"); print(f\"CPU: {d.get('cpu',{}).get('cpu_usage','N/A')}%\"); print(f\"内存: {d.get('memory',{}).get('used','N/A')}MB / {d.get('memory',{}).get('total','N/A')}MB ({d.get('memory',{}).get('usage','N/A')}%)\")"
echo ""

# 线路监控
echo "【线路状态】"
API_CALL "monitor_iface" '{"TYPE":"iface_check"}' | \
  python3 -c "import sys,json; d=json.load(sys.stdin); [print(f\"线路 {i+1}: {'在线' if x.get('enable') else '离线'} | 连接数 {x.get('num','N/A')}\") for i,x in enumerate(d.get('result',[]))]"
echo ""

# DHCP 设备
echo "【DHCP 设备统计】"
API_CALL "dhcp_lease" '{"TYPE":"total"}' | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"在线设备: {d.get('result',{}).get('total','N/A')} 台\")"
echo ""

# 端口映射
echo "【端口映射统计】"
API_CALL "dnat" '{"TYPE":"total"}' | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"端口映射: {d.get('result',{}).get('total','N/A')} 条\")"

rm -f "$COOKIE_FILE"
```

这个脚本收集了路由器最关键的几个指标，每次巡检跑一遍，大约 3-5 秒就能拿到完整的报告。

## 数据差异的排查经验

在使用的过程中，我发现了一个值得注意的现象：**不同路由器的 API 返回结构可能不一样。**

例如，出口路由器（主网关）的 DHCP 列表返回 74 台设备，而另一台 DHCP 服务器只返回 17 台设备。两边的数据结构和字段名称也有细微差异。

这种情况通常有以下几种可能：

**1. 不同的 DHCP 作用域**
两台路由器分别服务于不同的网段或 VLAN。出口路由器作为网关，能看到所有经过它的 DHCP 流量；而独立的 DHCP 服务器只服务本地网段。

**2. 不同的固件版本**
不同版本的 iKuai 固件可能使用了不同的 API 字段名。较新的版本可能返回更丰富的字段，而老版本则可能缺少某些信息。

**3. 权限配置不同**
某些 API 接口可能需要管理员权限才能访问完整数据。如果 session 对应的用户权限不足，返回的数据可能被截断。

遇到 API 返回格式不一致的情况，建议直接调用 `{"func_name":"","action":"show","param":{}}` 这种通用接口，查看实际返回的内容，再逐个字段排查。

## API 安全的思考

调用 iKuai API 的过程中，我对安全性有了一些思考：

**admin 密码是唯一的防线。**iKuai API 不提供独立的 API Key 或 OAuth Token，认证完全依赖 admin 密码。这意味着只要拿到 admin 密码，就可以通过 API 操作路由器的所有功能。

**sess_key 存在服务器本地。**登录后获得的 sess_key 通常保存在服务器的 cookie 文件中。如果攻击者拿到了服务器的访问权限，理论上可以从中提取 sess_key，从而操作路由器。

**API 调用缺乏细粒度权限控制。**目前的 API 不区分只读和读写操作。所有功能码都可以自由调用，没有类似于"只允许读取，禁止修改"的配置选项。

基于以上几点，我建议：

1. **强密码策略**：路由器 admin 密码必须足够复杂，定期更换。
2. **访问控制**：尽量在可信的内网环境中调用路由器 API，不要将路由器管理端口暴露到不安全的网络。
3. **会话管理**：定期检查 sess_key 是否异常使用，及时清理无用的 cookie 文件。
4. **监控告警**：如果条件允许，监控路由器的 API 调用日志，发现异常调用及时告警。

## 常见问题解答

**Q1：登录成功但 API 返回空结果？**

A：可能的原因有几种。首先检查 sess_key 是否过期，如果长期不操作，iKuai 会自动清理过期的 session，建议每次使用前重新登录。其次确认 func_name 和 param 格式是否正确，字段名称必须是字符串类型。最后，某些接口可能需要特定权限，尝试用 admin 账号登录。

**Q2：API 返回的字符编码是乱码？**

A：iKuai API 默认使用 UTF-8 编码。如果出现乱码，可能是设备名称或主机名中包含了非 ASCII 字符。可以用 `python3 -c "import sys; print(sys.stdin.read().encode('utf-8').decode('utf-8'))"` 的方式强制使用 UTF-8 解码，或者在 curl 命令后加上 `-H 'Accept-Charset: utf-8'`。

**Q3：如何判断某个设备是不是"正常"在线？**

A：DHCP 列表中的 `online` 字段表示设备当前是否在线。但需要注意的是，iKuai 的 DHCP lease 有一定的过期时间，如果设备进入休眠或断开网络，可能在 lease 过期前仍显示"在线"。建议配合 ARP 表交叉验证，ARP 表中有记录的设备通常是真实在线的。

**Q4：API 请求频率有限制吗？**

A：iKuai 路由器本身没有明确的 API 调用频率限制，但作为嵌入式设备，它的并发处理能力有限。过于频繁的请求（如每秒几十次）可能导致路由器负载过高。建议将调用频率控制在每秒 1-2 次以内，对于需要批量查询的场景，可以加一个小的人为延迟。

**Q5：如何获取路由器的负载趋势数据？**

A：iKuai 的 `monitor_iface` 接口返回的是实时流量数据。如果需要负载趋势，可以配合 Prometheus 或 Zabbix 定时采集，将数据存储到时序数据库中绘图。建议采集间隔设置为 1 分钟，这个频率既能反映趋势变化，又不会对路由器造成过大压力。

## 总结

iKuai 路由器的 REST API 为运维工作提供了一种高效的管理方式。通过命令行调用 API，可以自动化收集网络状态、监控设备列表、管理端口映射——这些工作以前需要登录 Web 管理界面手动操作，现在几行脚本就能搞定。

但同时，API 的便利性也带来了一些安全隐患。admin 密码是唯一的认证凭证，API 调用缺乏细粒度权限控制，这些都需要在实际使用中加以注意。

如果你也在管理 iKuai 路由器，不妨试试这套 API。用得好，它是运维利器；用不好，它也可能成为安全的短板。

---

*作者：小六，一个用命令行把路由器玩出花的打工人*
