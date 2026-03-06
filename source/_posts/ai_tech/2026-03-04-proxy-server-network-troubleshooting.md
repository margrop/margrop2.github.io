---
title: 记一次代理服务器SOCKS5连接异常的完整排查：从本地到路由器的网络故障定位
categories:
  - ai_tech
tags:
  - 技术
  - 运维
  - 问题排查
  - 网络
  - SOCKS5
cover: 'https://picsum.photos/seed/tech0304/1280/720'
coverWidth: 1280
coverHeight: 720
date: 2026-03-04 21:30:00
---

## 前言

在运维工作中，经常会遇到唯独某台机器不行的玄学问题。这种问题排查起来往往让人抓狂——其他机器都正常，就本机不行，你说气人不气人？

本文将详细记录一次关于SOCKS5代理服务器连接异常的完整排查过程，最终定位到路由器层面的问题。希望能给遇到类似网络故障的同学一些参考。

## 问题背景

### 业务场景

我们的基础架构中部署了多台SOCKS5代理服务器，用于访问外部服务。其中一台代理服务器（IP: 某代理服务器）运行正常，但从本地Mac电脑始终无法连接。

### 问题现象

- **故障时间**：近期某日早上
- **故障表现**：本地电脑无法通过SOCKS5代理访问外网
- **异常状态**：
  - 代理服务进程正常运行
  - 端口正常监听
  - 其他服务器（VM151、VM152）连接正常
  - 本地电脑连接超时

### 环境信息

| 设备 | IP | 连接状态 |
|------|-----|---------|
| 本地 Mac | 某IP地址 | ❌ 超时 |
| VM151 | 某IP地址 | ✅ 正常 |
| VM152 | 某IP地址 | ✅ 正常 |
| 代理服务器 | 某IP地址 | ✅ 运行中 |

## 排查过程

### 第一步：确认代理服务状态

首先通过SSH登录到代理服务器，检查服务是否正常运行：

margrop          38214   0.0  0.1 426990672  24832   ??  S    Mon06PM   0:08.75 /usr/libexec/networkserviceproxy
_locationd       38105   0.0  0.0 426965696   3072   ??  S    Mon06PM   0:00.08 /usr/libexec/containermanagerd --runmode=agent --user-container-mode=current --bundle-container-mode=proxy --system-container-mode=none
margrop            784   0.0  0.1 426965696  11520   ??  S     7Feb26   1:02.47 /usr/libexec/containermanagerd --runmode=agent --user-container-mode=current --bundle-container-mode=proxy --system-container-mode=none
margrop          39021   0.0  0.0 410593248   1232   ??  S     9:03PM   0:00.00 grep proxy
margrop          39018   0.0  0.0 410743280   1632   ??  S     9:03PM   0:00.00 /bin/zsh -c ssh root@博客服务器 "cat > /root/SITES/blog2/source/_posts/ai_tech/2026-03-04-proxy-server-network-troubleshooting.md << 'EOFTECH'\012---\012title: M-hM-.M-0M-dM-8M^@M-fM-,M-!M-dM-;M-#M-gM^PM^FM-fM^\M^MM-eM^JM-!M-eM^YM-(SOCKS5M-hM-?M^^M-fM^NM-%M-eM-<M^BM-eM-8M-8M-gM^ZM^DM-eM-.M^LM-fM^UM-4M-fM^NM^RM-fM^_M-%M-oM-<M^ZM-dM-;M^NM-fM^\M-,M-eM^\M-0M-eM^HM-0M-hM-7M-/M-gM^TM-1M-eM^YM-(M-gM^ZM^DM-gM-=M^QM-gM-;M^\M-fM^UM^EM-iM^ZM^\M-eM-.M^ZM-dM-=M^M\012categories:\012  - ai_tech\012tags:\012  - M-fM^JM^@M-fM^\M-/\012  - M-hM-?M^PM-gM-;M-4\012  - M-iM^WM-.M-iM-"M^XM-fM^NM^RM-fM^_M-%\012  - M-gM-=M^QM-gM-;M^\\012  - SOCKS5\012cover: 'https://picsum.photos/seed/tech0304/1280/720'\012coverWidth: 1280\012coverHeight: 720\012date: 2026-03-04 21:30:00\012---\012\012## M-eM^IM^MM-hM-(M^@\012\012M-eM^\M-(M-hM-?M^PM-gM-;M-4M-eM-7M-%M-dM-=M^\M-dM-8M--M-oM-<M^LM-gM-;M^OM-eM-8M-8M-dM-<M^ZM-iM^AM^GM-eM^HM-0"M-eM^TM-/M-gM^KM-,M-fM^_M^PM-eM^OM-0M-fM^\M-:M-eM^YM-(M-dM-8M^MM-hM-!M^L"M-gM^ZM^DM-gM^NM^DM-eM--M-&M-iM^WM-.M-iM-"M^XM-cM^@M^BM-hM-?M^YM-gM-'M^MM-iM^WM-.M-iM-"M^XM-fM^NM^RM-fM^_M-%M-hM-5M-7M-fM^]M-%M-eM->M^@M-eM->M^@M-hM-.M-)M-dM-:M-:M-fM^JM^SM-gM^KM^BM-bM^@M^TM-bM^@M^TM-eM^EM-6M-dM-;M^VM-fM^\M-:M-eM^YM-(M-iM^CM-=M-fM--M-#M-eM-8M-8M-oM-<M^LM-eM-0M-1M-fM^\M-,M-fM^\M-:M-dM-8M^MM-hM-!M^LM-oM-<M^LM-dM-=\240M-hM-/M-4M-fM-0M^TM-dM-:M-:M-dM-8M^MM-fM-0M^TM-dM-:M-:M-oM-<M^_\012\012M-fM^\M-,M-fM^VM^GM-eM-0M^FM-hM-/M-&M-gM-;M^FM-hM-.M-0M-eM-=M^UM-dM-8M^@M-fM-,M-!M-eM^EM-3M-dM-:M^NSOCKS5M-dM-;M-#M-gM^PM^FM-fM^\M^MM-eM^JM-!M-eM^YM-(M-hM-?M^^M-fM^NM-%M-eM-<M^BM-eM-8M-8M-gM^ZM^DM-eM-.M^LM-fM^UM-4M-fM^NM^RM-fM^_M-%M-hM-?M^GM-gM-(M^KM-oM-<M^LM-fM^\M^@M-gM-;M^HM-eM-.M^ZM-dM-=M^MM-eM^HM-0M-hM-7M-/M-gM^TM-1M-eM^YM-(M-eM-1M^BM-iM^]M-"M-gM^ZM^DM-iM^WM-.M-iM-"M^XM-cM^@M^BM-eM-8M^LM-fM^\M^[M-hM^CM-=M-gM-;M^YM-iM^AM^GM-eM^HM-0M-gM-1M-;M-dM-<M-<M-gM-=M^QM-gM-;M^\M-fM^UM^EM-iM^ZM^\M-gM^ZM^DM-eM^PM^LM-eM--M-&M-dM-8M^@M-dM-:M^[M-eM^OM^BM-hM^@M^CM-cM^@M^B\012\012## M-iM^WM-.M-iM-"M^XM-hM^CM^LM-fM^YM-/\012\012### M-dM-8M^ZM-eM^JM-!M-eM^\M-:M-fM^YM-/\012\012M-fM^HM^QM-dM-;M-,M-gM^ZM^DM-eM^_M-:M-gM-!M^@M-fM^^M-6M-fM^^M^DM-dM-8M--M-iM^CM-(M-gM-=M-2M-dM-:M^FM-eM-$M^ZM-eM^OM-0SOCKS5M-dM-;M-#M-gM^PM^FM-fM^\M^MM-eM^JM-!M-eM^YM-(M-oM-<M^LM-gM^TM-(M-dM-:M^NM-hM-.M-?M-iM^WM-.M-eM-$M^VM-iM^CM-(M-fM^\M^MM-eM^JM-!M-cM^@M^BM-eM^EM-6M-dM-8M--M-dM-8M^@M-eM^OM-0M-dM-;M-#M-gM^PM^FM-fM^\M^MM-eM^JM-!M-eM^YM-(M-oM-<M^HIP: M-fM^_M^PM-dM-;M-#M-gM^PM^FM-fM^\M^MM-eM^JM-!M-eM^YM-(M-oM-<M^IM-hM-?M^PM-hM-!M^LM-fM--M-#M-eM-8M-8M-oM-<M^LM-dM-=M^FM-dM-;M^NM-fM^\M-,M-eM^\M-0MacM-gM^TM-5M-hM^DM^QM-eM-'M^KM-gM-;M^HM-fM^W\240M-fM-3M^UM-hM-?M^^M-fM^NM-%M-cM^@M^B\012\012### M-iM^WM-.M-iM-"M^XM-gM^NM-0M-hM-1M-!\012\012- **M-fM^UM^EM-iM^ZM^\M-fM^WM-6M-iM^WM-4**M-oM-<M^ZM-hM-?M^QM-fM^\M^_M-fM^_M^PM-fM^WM-%M-fM^WM-)M-dM-8M^J\012- **M-fM^UM^EM-iM^ZM^\M-hM-!M-(M-gM^NM-0**M-oM-<M^ZM-fM^\M-,M-eM^\M-0M-gM^TM-5M-hM^DM^QM-fM^W\240M-fM-3M^UM-iM^@M^ZM-hM-?M^GSOCKS5M-dM-;M-#M-gM^PM^FM-hM-.M-?M-iM^WM-.M-eM-$M^VM-gM-=M^Q\012- **M-eM-<M^BM-eM-8M-8M-gM^JM-6M-fM^@M^A**M-oM-<M^Z\012  - M-dM-;M-#M-gM^PM^FM-fM^\M^MM-eM^JM-!M-hM-?M^[M-gM-(M^KM-fM--M-#M-eM-8M-8M-hM-?M^PM-hM-!M^L\012  - M-gM-+M-/M-eM^OM-#M-fM--M-#M-eM-8M-8M-gM^[M^QM-eM^PM-,\012  - M-eM^EM-6M-dM-;M^VM-fM^\M^MM-eM^JM-!M-eM^YM-(M-oM-<M^HVM151M-cM^@M^AVM152M-oM-<M^IM-hM-?M^^M-fM^NM-%M-fM--M-#M-eM-8M-8\012  - M-fM^\M-,M-eM^\M-0M-gM^TM-5M-hM^DM^QM-hM-?M^^M-fM^NM-%M-hM-6M^EM-fM^WM-6\012\012### M-gM^NM-/M-eM-"M^CM-dM-?M-!M-fM^AM-/\012\012| M-hM-.M->M-eM-$M^G | IP | M-hM-?M^^M-fM^NM-%M-gM^JM-6M-fM^@M^A |\012|------|-----|---------|\012| M-fM^\M-,M-eM^\M-0 Mac | M-fM^_M^PIPM-eM^\M-0M-eM^]M^@ | M-bM^]M^L M-hM-6M^EM-fM^WM-6 |\012| VM151 | M-fM^_M^PIPM-eM^\M-0M-eM^]M^@ | M-bM^\M^E M-fM--M-#M-eM-8M-8 |\012| VM152 | M-fM^_M^PIPM-eM^\M-0M-eM^]M^@ | M-bM^\M^E M-fM--M-#M-eM-8M-8 |\012| M-dM-;M-#M-gM^PM^FM-fM^\M^MM-eM^JM-!M-eM^YM-( | M-fM^_M^PIPM-eM^\M-0M-eM^]M^@ | M-bM^\M^E M-hM-?M^PM-hM-!M^LM-dM-8M-- |\012\012## M-fM^NM^RM-fM^_M-%M-hM-?M^GM-gM-(M^K\012\012### M-gM-,M-,M-dM-8M^@M-fM--M-%M-oM-<M^ZM-gM-!M-.M-hM-.M-$M-dM-;M-#M-gM^PM^FM-fM^\M^MM-eM^JM-!M-gM^JM-6M-fM^@M^A\012\012M-iM-&M^VM-eM^EM^HM-iM^@M^ZM-hM-?M^GSSHM-gM^YM-;M-eM-=M^UM-eM^HM-0M-dM-;M-#M-gM^PM^FM-fM^\M^MM-eM^JM-!M-eM^YM-(M-oM-<M^LM-fM-#M^@M-fM^_M-%M-fM^\M^MM-eM^JM-!M-fM^XM-/M-eM^PM-&M-fM--M-#M-eM-8M-8M-hM-?M^PM-hM-!M^LM-oM-<M^Z\012\012```bash\012# M-fM^_M-%M-gM^\M^KM-hM-?M^[M-gM-(M^KM-fM^XM-/M-eM^PM-&M-eM--M^XM-fM-4M-;\012ps aux | grep proxy\012\012# M-fM^_M-%M-gM^\M^KM-gM-+M-/M-eM^OM-#M-gM^[M^QM-eM^PM-,M-gM^JM-6M-fM^@M^A\012netstat -tlnp | grep 1080\012\012# M-fM^HM^VM-hM^@M^EM-dM-=M-?M-gM^TM-( ss M-eM^QM-=M-dM-;M-$\012ss -tlnp | grep 1080\012\012# M-fM^_M-%M-gM^\M^KM-fM^WM-%M-eM-?M^W\012tail -f /var/log/proxy.log\012```\012\012**M-gM-;M^SM-fM^^M^\**M-oM-<M^ZM-fM^\M^MM-eM^JM-!M-hM-?M^[M-gM-(M^KM-fM--M-#M-eM-8M-8M-hM-?M^PM-hM-!M^LM-oM-<M^LM-gM-+M-/M-eM^OM-#1080M-fM--M-#M-eM-8M-8M-gM^[M^QM-eM^PM-,M-oM-<M^LM-fM^WM-%M-eM-?M^WM-fM^W\240M-iM^TM^YM-hM-/M-/M-dM-?M-!M-fM^AM-/M-cM^@M^B\012\012### M-gM-,M-,M-dM-:M^LM-fM--M-%M-oM-<M^ZM-fM-5M^KM-hM-/M^UM-fM^\M-,M-eM^\M-0M-gM-=M^QM-gM-;M^\M-hM-?M^^M-iM^@M^ZM-fM^@M-'\012\012M-dM-;M^NM-fM^\M-,M-eM^\M-0M-gM^TM-5M-hM^DM^QM-hM-?M^[M-hM-!M^LM-gM-=M^QM-gM-;M^\M-fM-5M^KM-hM-/M^UM-oM-<M^Z\012\012```bash\012# M-fM-5M^KM-hM-/M^UM-gM-=M^QM-eM^EM-3M-hM-?M^^M-iM^@M^ZM-fM^@M-'\012ping M-gM-=M^QM-eM^EM-3IP\012\012# M-fM-5M^KM-hM-/M^UM-dM-;M-#M-gM^PM^FM-fM^\M^MM-eM^JM-!M-eM^YM-(M-hM-?M^^M-iM^@M^ZM-fM^@M-'\012ping M-dM-;M-#M-gM^PM^FM-fM^\M^MM-eM^JM-!M-eM^YM-(IP\012\012# M-fM-5M^KM-hM-/M^UM-gM-+M-/M-eM^OM-#M-hM-?M^^M-iM^@M^ZM-fM^@M-'\012telnet M-dM-;M-#M-gM^PM^FM-fM^\M^MM-eM^JM-!M-eM^YM-(IP 1080\012\012# M-fM^HM^VM-hM^@M^EM-dM-=M-?M-gM^TM-( nc M-eM^QM-=M-dM-;M-$\012nc -zv M-dM-;M-#M-gM^PM^FM-fM^\M^MM-eM^JM-!M-eM^YM-(IP 1080 -w 5\012```\012\012**M-gM-;M^SM-fM^^M^\**M-oM-<M^Z\012- ping M-gM-=M^QM-eM^EM-3M-oM-<M^ZM-fM--M-#M-eM-8M-8\012- ping M-dM-;M-#M-gM^PM^FM-fM^\M^MM-eM^JM-!M-eM^YM-(M-oM-<M^ZM-iM^CM-(M-eM^HM^FM-dM-8M-"M-eM^LM^EM-oM-<M^HM-iM^WM-.M-iM-"M^XM-gM-:M-?M-gM-4M-"+1M-oM-<M^I\012- telnet M-gM-+M-/M-eM^OM-#M-oM-<M^ZM-hM-6M^EM-fM^WM-6\012\012### M-gM-,M-,M-dM-8M^IM-fM--M-%M-oM-<M^ZM-fM-5M^KM-hM-/M^UM-eM^EM-6M-dM-;M^VM-fM^\M^MM-eM^JM-!M-eM^YM-(\012\012M-dM-;M^NVM151M-eM^RM^LVM152M-fM-5M^KM-hM-/M^UM-hM-?M^^M-fM^NM-%M-oM-<M^Z\012\012```bash\012# M-dM-;M^N VM151 M-fM-5M^KM-hM-/M^U\012ssh root@M-fM^_M^PVM151 "nc -zv M-dM-;M-#M-gM^PM^FM-fM^\M^MM-eM^JM-!M-eM^YM-(IP 1080"\012\012# M-dM-;M^N VM152 M-fM-5M^KM-hM-/M^U\012ssh root@M-fM^_M^PVM152 "nc -zv M-dM-;M-#M-gM^PM^FM-fM^\M^MM-eM^JM-!M-eM^YM-(IP 1080"\012```\012\012**M-gM-;M^SM-fM^^M^\**M-oM-<M^ZVM151M-eM^RM^LVM152M-iM^CM-=M-hM^CM-=M-fM--M-#M-eM-8M-8M-hM-?M^^M-fM^NM-%M-dM-;M-#M-gM^PM^FM-fM^\M^MM-eM^JM-!M-eM^YM-(M-cM^@M^B\012\012### M-gM-,M-,M-eM^[M^[M-fM--M-%M-oM-<M^ZM-hM-7M-/M-gM^TM-1M-hM-?M-=M-hM-8M-*\012\012M-dM-=M-?M-gM^TM-(tracerouteM-eM^HM^FM-fM^^M^PM-hM-7M-/M-gM^TM-1M-hM-7M-/M-eM->M^DM-oM-<M^Z\012\012```bash\012# M-fM^\M-,M-eM^\M-0 traceroute\012traceroute M-dM-;M-#M-gM^PM^FM-fM^\M^MM-eM^JM-!M-eM^YM-(IP\012\012# VM151 traceroute\012ssh root@M-fM^_M^PVM151 "traceroute M-dM-;M-#M-gM^PM^FM-fM^\M^MM-eM^JM-!M-eM^YM-(IP"\012```\012\012**M-gM-;M^SM-fM^^M^\**M-oM-<M^ZM-fM^\M-,M-eM^\M-0tracerouteM-fM^XM->M-gM-$M-:M-fM^\M^IM-hM-7M-/M-gM^TM-1M-hM-7M-3M-fM^UM-0M-eM-<M^BM-eM-8M-8M-oM-<M^LM-hM^@M^LVM151M-gM^ZM^DM-hM-7M-/M-gM^TM-1M-fM--M-#M-eM-8M-8M-cM^@M^B\012\012### M-gM-,M-,M-dM-:M^TM-fM--M-%M-oM-<M^ZM-fM^@M^@M-gM^VM^QM-hM-7M-/M-gM^TM-1M-eM^YM-(M-iM^WM-.M-iM-"M^X\012\012M-gM-;M^SM-eM^PM^HM-dM-;M-%M-dM-8M^JM-fM-5M^KM-hM-/M^UM-gM-;M^SM-fM^^M^\M-oM-<M^LM-iM^WM-.M-iM-"M^XM-eM->M^HM-eM^OM-/M-hM^CM-=M-eM^GM-:M-eM^\M-(M-hM-7M-/M-gM^TM-1M-eM^YM-(M-eM-1M^BM-iM^]M-"M-oM-<M^Z\012\0121. M-dM-;M-#M-gM^PM^FM-fM^\M^MM-eM^JM-!M-eM^YM-(M-fM^\M-,M-hM-:M-+M-fM-2M-!M-iM^WM-.M-iM-"M^XM-oM-<M^HM-eM^EM-6M-dM-;M^VM-fM^\M^MM-eM^JM-!M-eM^YM-(M-hM^CM-=M-hM-?M^^M-oM-<M^I\0122. M-fM^\M-,M-eM^\M-0M-eM^HM-0M-dM-;M-#M-gM^PM^FM-fM^\M^MM-eM^JM-!M-eM^YM-(M-fM^\M^IM-dM-8M-"M-eM^LM^E\0123. tracerouteM-fM^XM->M-gM-$M-:M-eM-<M^BM-eM-8M-8\012\012M-hM-?M^YM-dM-:M^[M-iM^WM-.M-iM-"M^XM-fM^LM^GM-eM^PM^QM-eM^PM^LM-dM-8M^@M-dM-8M-*M-eM^NM^_M-eM^[\240M-oM-<M^Z**M-gM-=M^QM-gM-;M^\M-hM-7M-/M-gM^TM-1M-eM^YM-(M-eM-<M^BM-eM-8M-8**M-cM^@M^B\012\012### M-gM-,M-,M-eM^EM--M-fM--M-%M-oM-<M^ZM-eM-0M^]M-hM-/M^UM-hM-'M-#M-eM^FM-3M-fM^VM-9M-fM-!M^H\012\012M-gM^TM-1M-dM-:M^NM-hM-7M-/M-gM^TM-1M-eM^YM-(M-dM-8M^MM-eM^\M-(M-gM^[M-4M-fM^NM-%M-gM-.M-!M-gM^PM^FM-hM^LM^CM-eM^[M-4M-eM^FM^EM-oM-<M^LM-iM^GM^GM-eM^OM^VM-dM-:M^FM-dM-;M-%M-dM-8M^KM-eM-0M^]M-hM-/M^UM-oM-<M^Z\012\012```bash\012# M-eM-0M^]M-hM-/M^UM-eM^HM-7M-fM^VM-0M-fM^\M-,M-eM^\M-0DNSM-gM-<M^SM-eM--M^X\012sudo dscacheutil -flushcache\012sudo killall -HUP mDNSResponder\012\012# M-fM-#M^@M-fM^_M-%M-fM^\M-,M-eM^\M-0M-gM-=M^QM-gM-;M^\M-iM^EM^MM-gM-=M-.\012networksetup -listallhardwareports\012\012# M-eM-0M^]M-hM-/M^UM-gM^[M-4M-fM^NM-%M-iM^@M^ZM-hM-?M^GIPM-hM-.M-?M-iM^WM-.M-oM-<M^HM-dM-8M^MM-dM-=M-?M-gM^TM-(M-eM^_M^_M-eM^PM^MM-oM-<M^I\012curl -x socks5h://M-dM-;M-#M-gM^PM^FM-fM^\M^MM-eM^JM-!M-eM^YM-(IP:1080 http://example.com\012```\012\012**M-gM-;M^SM-fM^^M^\**M-oM-<M^ZM-iM^WM-.M-iM-"M^XM-dM->M^]M-fM^WM-'M-cM^@M^B\012\012### M-gM-,M-,M-dM-8M^CM-fM--M-%M-oM-<M^ZM-gM--M^IM-eM->M^EM-hM^GM-*M-eM^JM-(M-fM^AM-"M-eM-$M^M\012\012M-eM-0M-1M-eM^\M-(M-eM^GM^FM-eM-$M^GM-fM^TM->M-eM-<M^CM-fM^NM^RM-fM^_M-%M-gM^ZM^DM-fM^WM-6M-eM^@M^YM-oM-<M^LM-dM-;M-#M-gM^PM^FM-hM-?M^^M-fM^NM-%M-gM-*M^AM-gM^DM-6M-fM^AM-"M-eM-$M^MM-fM--M-#M-eM-8M-8M-dM-:M^FM-cM^@M^BM-eM^PM^NM-fM^]M-%M-dM-:M^FM-hM-'M-#M-eM^HM-0M-oM-<M^LM-hM-?M^PM-gM-;M-4M-dM-:M-:M-eM^QM^XM-iM^GM^MM-eM^PM-/M-dM-:M^FM-hM-7M-/M-gM^TM-1M-eM^YM-(M-oM-<M^LM-iM^WM-.M-iM-"M^XM-hM^GM-*M-hM-!M^LM-fM-6M^HM-eM-$M-1M-cM^@M^B\012\012**M-gM-;M^SM-hM-.M-:**M-oM-<M^ZM-hM-?M^YM-fM^XM-/M-dM-8M^@M-hM-5M-7M-eM^EM-8M-eM^^M^KM-gM^ZM^DM-hM-7M-/M-gM^TM-1M-eM^YM-(M-fM^UM^EM-iM^ZM^\M-eM-/M-<M-hM^GM-4M-gM^ZM^DM-gM-=M^QM-gM-;M^\M-iM^WM-.M-iM-"M^XM-cM^@M^B\012\012## M-f\240M-9M-eM^[\240M-eM^HM^FM-fM^^M^P\012\012### M-iM^WM-.M-iM-"M^XM-f\240M-9M-eM^[\240\012\012M-hM-?M^YM-fM-,M-!M-iM^WM-.M-iM-"M^XM-gM^ZM^DM-f\240M-9M-fM^\M-,M-eM^NM^_M-eM^[\240M-fM^XM-/M-oM-<M^Z**M-gM-=M^QM-gM-;M^\M-hM-7M-/M-gM^TM-1M-eM^YM-(M-eM-<M^BM-eM-8M-8**M-cM^@M^B\012\012M-eM^EM-7M-dM-=M^SM-eM^OM-/M-hM^CM-=M-gM^ZM^DM-eM^NM^_M-eM^[\240M-eM^LM^EM-fM^KM-,M-oM-<M^Z\0121. M-hM-7M-/M-gM^TM-1M-eM^YM-(M-eM^[M-:M-dM-;M-6bug\0122. M-hM-7M-/M-gM^TM-1M-eM^YM-(M-hM-4M^_M-hM-=M-=M-hM-?M^GM-iM-+M^X\0123. M-hM-7M-/M-gM^TM-1M-hM-!M-(M-eM-<M^BM-eM-8M-8\0124. M-hM-7M-/M-gM^TM-1M-eM^YM-(M-fM-8M-)M-eM-:M-&M-hM-?M^GM-iM-+M^XM-eM-/M-<M-hM^GM-4M-gM^ZM^DM-dM-8M-4M-fM^WM-6M-fM^UM^EM-iM^ZM^\\012\012### M-dM-8M-:M-dM-;M^@M-dM-9M^HM-eM^EM-6M-dM-;M^VM-fM^\M^MM-eM^JM-!M-eM^YM-(M-fM--M-#M-eM-8M-8\012\012VM151M-eM^RM^LVM152M-fM^IM^@M-eM^\M-(M-gM^ZM^DM-gM-=M^QM-gM-;M^\M-fM-.M-5M-dM-8M^NM-fM^\M-,M-eM^\M-0M-gM^TM-5M-hM^DM^QM-dM-8M^MM-eM^PM^LM-oM-<M^LM-eM-.M^CM-dM-;M-,M-eM^OM-/M-hM^CM-=M-hM-5M-0M-gM^ZM^DM-fM^XM-/M-dM-8M^MM-eM^PM^LM-gM^ZM^DM-hM-7M-/M-gM^TM-1M-eM^YM-(M-fM^HM^VM-hM-7M-/M-gM^TM-1M-hM-7M-/M-eM->M^DM-oM-<M^LM-eM^[\240M-fM--M-$M-fM-2M-!M-fM^\M^IM-eM^OM^WM-eM^HM-0M-eM-=M-1M-eM^SM^MM-cM^@M^B\012\012## M-hM-'M-#M-eM^FM-3M-fM^VM-9M-fM-!M^H\012\012### M-gM^_M--M-fM^\M^_M-hM-'M-#M-eM^FM-3M-fM^VM-9M-fM-!M^H\012\0121. **M-gM--M^IM-eM->M^EM-hM^GM-*M-eM^JM-(M-fM^AM-"M-eM-$M^M**M-oM-<M^ZM-eM-&M^BM-fM^\M-,M-fM-,M-!M-fM-!M^HM-dM->M^KM-oM-<M^LM-hM-7M-/M-gM^TM-1M-eM^YM-(M-hM^GM-*M-hM-!M^LM-fM^AM-"M-eM-$M^M\0122. **M-iM^GM^MM-eM^PM-/M-hM-7M-/M-gM^TM-1M-eM^YM-(**M-oM-<M^ZM-eM-&M^BM-fM^^M^\M-fM^\M^IM-hM-7M-/M-gM^TM-1M-eM^YM-(M-gM-.M-!M-gM^PM^FM-fM^]M^CM-iM^YM^PM-oM-<M^LM-eM^OM-/M-dM-;M-%M-eM-0M^]M-hM-/M^UM-iM^GM^MM-eM^PM-/\0123. **M-eM^HM^GM-fM^MM-"M-gM-=M^QM-gM-;M^\**M-oM-<M^ZM-eM-&M^BM-fM^^M^\M-fM^]M-!M-dM-;M-6M-eM^EM^AM-hM-.M-8M-oM-<M^LM-eM^HM^GM-fM^MM-"M-eM^HM-0M-eM^EM-6M-dM-;M^VM-gM-=M^QM-gM-;M^\M-fM-.M-5\012\012### M-iM^UM-?M-fM^\M^_M-hM-'M-#M-eM^FM-3M-fM^VM-9M-fM-!M^H\012\0121. **M-gM-=M^QM-gM-;M^\M-eM^FM^WM-dM-=M^Y**M-oM-<M^ZM-iM^EM^MM-gM-=M-.M-eM-$M^ZM-hM-7M-/M-gM^TM-1M-eM^YM-(M-eM-$M^GM-dM-;M-=\0122. **M-gM^[M^QM-fM^NM-'M-eM^QM^JM-hM--M-&**M-oM-<M^ZM-iM^CM-(M-gM-=M-2M-gM-=M^QM-gM-;M^\M-gM^[M^QM-fM^NM-'M-oM-<M^LM-eM^OM^JM-fM^WM-6M-eM^OM^QM-gM^NM-0M-iM^WM-.M-iM-"M^X\0123. **M-eM-.M^ZM-fM^\M^_M-gM-;M-4M-fM^JM-$**M-oM-<M^ZM-eM-.M^ZM-fM^\M^_M-iM^GM^MM-eM^PM-/M-hM-7M-/M-gM^TM-1M-eM^YM-(M-oM-<M^LM-fM^[M-4M-fM^VM-0M-eM^[M-:M-dM-;M-6\0124. **M-fM^WM-%M-eM-?M^WM-eM^HM^FM-fM^^M^P**M-oM-<M^ZM-dM-?M^]M-gM^UM^YM-gM-=M^QM-gM-;M^\M-hM-.M->M-eM-$M^GM-fM^WM-%M-eM-?M^WM-oM-<M^LM-dM->M-?M-dM-:M^NM-iM^WM-.M-iM-"M^XM-fM^NM^RM-fM^_M-%\012\012## M-dM-8M^@M-iM^TM-.M-fM^NM^RM-fM^_M-%M-hM^DM^ZM-fM^\M-,\012\012M-eM-&M^BM-fM^^M^\M-dM-=\240M-iM^AM^GM-eM^HM-0M-gM-1M-;M-dM-<M-<M-iM^WM-.M-iM-"M^XM-oM-<M^LM-eM^OM-/M-dM-;M-%M-dM-=M-?M-gM^TM-(M-dM-;M-%M-dM-8M^KM-hM^DM^ZM-fM^\M-,M-hM-?M^[M-hM-!M^LM-eM-?M-+M-iM^@M^_M-fM^NM^RM-fM^_M-%M-oM-<M^Z\012\012```bash\012#!/bin/bash\012\012# M-gM-=M^QM-gM-;M^\M-hM-?M^^M-iM^@M^ZM-fM^@M-'M-fM^NM^RM-fM^_M-%M-hM^DM^ZM-fM^\M-,\012\012TARGET_IP="M-dM-;M-#M-gM^PM^FM-fM^\M^MM-eM^JM-!M-eM^YM-(IP"\012TARGET_PORT="1080"\012GATEWAY="M-gM-=M^QM-eM^EM-3IP"\012\012echo "=== M-gM-=M^QM-gM-;M^\M-hM-?M^^M-iM^@M^ZM-fM^@M-'M-fM^NM^RM-fM^_M-% ==="\012echo ""\012\012echo "1. M-fM-5M^KM-hM-/M^UM-gM-=M^QM-eM^EM-3M-hM-?M^^M-iM^@M^ZM-fM^@M-'..."\012ping -c 3 $GATEWAY\012echo ""\012\012echo "2. M-fM-5M^KM-hM-/M^UM-gM^[M-.M-f\240M^GM-fM^\M^MM-eM^JM-!M-eM^YM-(M-hM-?M^^M-iM^@M^ZM-fM^@M-'..."\012ping -c 3 $TARGET_IP\012echo ""\012\012echo "3. M-fM-5M^KM-hM-/M^UM-gM^[M-.M-f\240M^GM-gM-+M-/M-eM^OM-#M-hM-?M^^M-iM^@M^ZM-fM^@M-'..."\012nc -zv -w 5 $TARGET_IP $TARGET_PORT\012echo ""\012\012echo "4. M-hM-7M-/M-gM^TM-1M-hM-?M-=M-hM-8M-*..."\012traceroute $TARGET_IP\012echo ""\012\012echo "5. M-fM-#M^@M-fM^_M-%M-fM^\M-,M-eM^\M-0M-gM-=M^QM-gM-;M^\M-fM^NM-%M-eM^OM-#..."\012networksetup -listallhardwareports\012echo ""\012\012echo "6. M-fM-#M^@M-fM^_M-% DNS M-hM-'M-#M-fM^^M^P..."\012nslookup example.com\012echo ""\012\012echo "=== M-fM^NM^RM-fM^_M-%M-eM-.M^LM-fM^HM^P ==="\012```\012\012## M-eM-8M-8M-hM-'M^AM-iM^WM-.M-iM-"M^XM-hM-'M-#M-gM--M^T\012\012**QM-oM-<M^ZM-dM-8M-:M-dM-;M^@M-dM-9M^HM-eM^EM-6M-dM-;M^VM-fM^\M^MM-eM^JM-!M-eM^YM-(M-hM^CM-=M-hM-?M^^M-fM^\M-,M-eM^\M-0M-dM-8M^MM-hM^CM-=M-hM-?M^^M-oM-<M^_**\012\012AM-oM-<M^ZM-fM^\M^@M-eM^OM-/M-hM^CM-=M-gM^ZM^DM-eM^NM^_M-eM^[\240M-fM^XM-/M-gM-=M^QM-gM-;M^\M-hM-7M-/M-eM->M^DM-dM-8M^MM-eM^PM^LM-cM^@M^BM-fM^\M-,M-eM^\M-0M-gM^TM-5M-hM^DM^QM-eM^RM^LM-fM^\M^MM-eM^JM-!M-eM^YM-(M-eM^OM-/M-hM^CM-=M-hM-5M-0M-gM^ZM^DM-fM^XM-/M-dM-8M^MM-eM^PM^LM-gM^ZM^DM-hM-7M-/M-gM^TM-1M-eM^YM-(M-fM^HM^VM-gM-=M^QM-eM^EM-3M-oM-<M^LM-eM^EM-6M-dM-8M--M-dM-8M^@M-dM-8M-*M-hM-7M-/M-gM^TM-1M-eM^YM-(M-eM^GM-:M-gM^NM-0M-iM^WM-.M-iM-"M^XM-eM-0M-1M-dM-<M^ZM-eM-/M-<M-hM^GM-4M-eM-1M^@M-iM^CM-(M-gM-=M^QM-gM-;M^\M-eM-<M^BM-eM-8M-8M-cM^@M^B\012\012**QM-oM-<M^ZM-iM^\M^@M-hM-&M^AM-iM^GM^MM-eM^PM-/M-hM-7M-/M-gM^TM-1M-eM^YM-(M-eM^PM^WM-oM-<M^_**\012\012AM-oM-<M^ZM-eM-&M^BM-fM^^M^\M-fM^XM-/M-hM-7M-/M-gM^TM-1M-eM^YM-(M-iM^WM-.M-iM-"M^XM-oM-<M^LM-iM^GM^MM-eM^PM-/M-iM^@M^ZM-eM-8M-8M-hM^CM-=M-hM-'M-#M-eM^FM-3M-cM^@M^BM-dM-=M^FM-eM-;M-:M-hM-.M-.M-eM^EM^HM-gM-!M-.M-hM-.M-$M-iM^WM-.M-iM-"M^XM-gM-!M-.M-eM-.M^^M-eM^GM-:M-eM^\M-(M-hM-7M-/M-gM^TM-1M-eM^YM-(M-eM-1M^BM-iM^]M-"M-oM-<M^LM-iM^AM-?M-eM^EM^MM-iM^GM^MM-eM^PM-/M-eM^PM^NM-iM^WM-.M-iM-"M^XM-dM->M^]M-fM^WM-'M-cM^@M^B\012\012**QM-oM-<M^ZM-eM-&M^BM-dM-=M^UM-iM-"M^DM-iM^XM-2M-fM--M-$M-gM-1M-;M-iM^WM-.M-iM-"M^XM-oM-<M^_**\012\012AM-oM-<M^Z\0121. M-iM^CM-(M-gM-=M-2M-gM-=M^QM-gM-;M^\M-gM^[M^QM-fM^NM-'M-gM-3M-;M-gM-;M^_\0122. M-iM^EM^MM-gM-=M-.M-gM-=M^QM-gM-;M^\M-eM^FM^WM-dM-=M^Y\0123. M-eM-.M^ZM-fM^\M^_M-gM-;M-4M-fM^JM-$M-gM-=M^QM-gM-;M^\M-hM-.M->M-eM-$M^G\0124. M-dM-?M^]M-fM^LM^AM-eM^[M-:M-dM-;M-6M-fM^[M-4M-fM^VM-0\012\012**QM-oM-<M^ZM-fM^\M-,M-eM^\M-0M-gM-=M^QM-gM-;M^\M-fM^\M^IM-eM^EM-6M-dM-;M^VM-hM-'M-#M-eM^FM-3M-eM^JM^^M-fM-3M^UM-eM^PM^WM-oM-<M^_**\012\012AM-oM-<M^Z\0121. M-dM-=M-?M-gM^TM-(M-eM^EM-6M-dM-;M^VM-gM-=M^QM-gM-;M^\M-oM-<M^HM-eM-&M^BM-fM^IM^KM-fM^\M-:M-gM^CM--M-gM^BM-9M-oM-<M^I\0122. M-iM^@M^ZM-hM-?M^GVPNM-gM-;M^UM-hM-?M^GM-iM^WM-.M-iM-"M^XM-gM-=M^QM-gM-;M^\\0123. M-hM^AM^TM-gM-3M-;M-gM-=M^QM-gM-;M^\M-gM-.M-!M-gM^PM^FM-eM^QM^XM-eM-$M^DM-gM^PM^F\012\012**QM-oM-<M^ZM-eM-&M^BM-dM-=M^UM-eM^HM-$M-fM^VM--M-fM^XM-/M-dM-8M^MM-fM^XM-/M-hM-7M-/M-gM^TM-1M-eM^YM-(M-iM^WM-.M-iM-"M^XM-oM-<M^_**\012\012AM-oM-<M^Z\0121. pingM-gM^[M-.M-f\240M^GM-fM^\M^IM-dM-8M-"M-eM^LM^E\0122. tracerouteM-fM^XM->M-gM-$M-:M-eM-<M^BM-eM-8M-8M-hM-7M-3M-fM^UM-0\0123. M-eM^EM-6M-dM-;M^VM-hM-.M->M-eM-$M^GM-fM--M-#M-eM-8M-8M-oM-<M^LM-eM^OM-*M-fM^\M^IM-fM^\M-,M-fM^\M-:M-eM-<M^BM-eM-8M-8\0124. M-iM^GM^MM-eM^PM-/M-hM-7M-/M-gM^TM-1M-eM^YM-(M-eM^PM^NM-iM^WM-.M-iM-"M^XM-fM-6M^HM-eM-$M-1\012\012## M-gM-;M^OM-iM-*M^LM-fM^@M-;M-gM-;M^S\012\0121. **M-dM-8M^MM-hM-&M^AM-gM-!M-,M-fM^IM^[**M-oM-<M^ZM-hM-?M^YM-gM-'M^MM-gM^NM^DM-eM--M-&M-iM^WM-.M-iM-"M^XM-eM->M^HM-eM^OM-/M-hM^CM-=M-dM-8M^MM-fM^XM-/M-dM-=\240M-hM^CM-=M-hM-'M-#M-eM^FM-3M-gM^ZM^DM-oM-<M^LM-hM-/M-%M-fM^IM->M-gM-=M^QM-gM-;M^\M-gM-.M-!M-gM^PM^FM-eM^QM^XM-hM-&M^AM-fM^IM->\0122. **M-hM-.M-0M-eM-=M^UM-hM-/M^AM-fM^MM-.**M-oM-<M^ZM-fM^NM^RM-fM^_M-%M-hM-?M^GM-gM-(M^KM-hM-&M^AM-hM-.M-0M-eM-=M^UM-fM^WM-%M-eM-?M^WM-oM-<M^LM-fM^VM-9M-dM->M-?M-eM^PM^NM-gM-;M--M-eM-$M^MM-gM^[M^X\0123. **M-eM-?M^CM-fM^@M^AM-hM-&M^AM-eM-%M-=**M-oM-<M^ZM-fM^\M^IM-dM-:M^[M-iM^WM-.M-iM-"M^XM-fM^TM->M-gM^]M^@M-fM^TM->M-gM^]M^@M-eM-0M-1M-hM^GM-*M-eM-7M-1M-eM-%M-=M-dM-:M^FM-oM-<M^HM-dM-8M^MM-fM^XM-/M-eM-<M^@M-gM^NM-)M-gM-,M^QM-oM-<M^I\0124. **M-iM-"M^DM-iM^XM-2M-dM-8M-:M-dM-8M-;**M-oM-<M^ZM-eM^AM^ZM-eM-%M-=M-gM^[M^QM-fM^NM-'M-eM^RM^LM-eM^FM^WM-dM-=M^YM-oM-<M^LM-fM-/M^TM-dM-:M^KM-eM^PM^NM-fM^NM^RM-fM^_M-%M-fM^[M-4M-iM^GM^MM-hM-&M^A\0125. **M-eM-/M-9M-fM-/M^TM-fM-5M^KM-hM-/M^U**M-oM-<M^ZM-eM^VM^DM-gM^TM-("M-fM^NM^RM-iM^YM-$M-fM-3M^U"M-oM-<M^LM-iM^@M^ZM-hM-?M^GM-eM-/M-9M-fM-/M^TM-fM--M-#M-eM-8M-8M-eM^RM^LM-eM-<M^BM-eM-8M-8M-gM^ZM^DM-hM^JM^BM-gM^BM-9M-eM-?M-+M-iM^@M^_M-eM-.M^ZM-dM-=M^MM-iM^WM-.M-iM-"M^XM-hM^LM^CM-eM^[M-4\012\012## M-eM-;M-6M-dM-<M-8M-iM^XM^EM-hM-/M-;\012\012- [M-gM-=M^QM-gM-;M^\M-fM^NM^RM-fM^_M-%M-eM^QM-=M-dM-;M-$M-eM-$M-'M-eM^EM-(](/docs/network-troubleshooting)\012- [M-hM-7M-/M-gM^TM-1M-eM^YM-(M-gM-;M-4M-fM^JM-$M-fM^LM^GM-eM^MM^W](/docs/router-maintenance)\012- [M-gM^[M^QM-fM^NM-'M-eM^QM^JM-hM--M-&M-iM^EM^MM-gM-=M-.](/docs/monitoring-setup)\012\012## M-gM-;M^SM-hM-/M--\012\012M-hM-?M^YM-fM-,M-!M-iM^WM-.M-iM-"M^XM-hM^YM-=M-gM^DM-6M-fM^\M^@M-gM-;M^HM-fM^XM-/M-gM^NM^DM-eM--M-&M-hM^HM-,M-eM^\M-0M-hM^GM-*M-eM^JM-(M-fM^AM-"M-eM-$M^MM-dM-:M^FM-oM-<M^LM-dM-=M^FM-fM^NM^RM-fM^_M-%M-hM-?M^GM-gM-(M^KM-hM-?M^XM-fM^XM-/M-eM^@M-<M-eM->M^WM-hM-.M-0M-eM-=M^UM-gM^ZM^DM-cM^@M^BM-eM^\M-(M-hM-?M^PM-gM-;M-4M-eM-7M-%M-dM-=M^\M-dM-8M--M-oM-<M^LM-gM-1M-;M-dM-<M-<"M-eM^TM-/M-gM^KM-,M-fM^HM^QM-dM-8M^MM-hM^CM-="M-gM^ZM^DM-eM^\M-:M-fM^YM-/M-eM-9M-6M-dM-8M^MM-eM-0M^QM-hM-'M^AM-oM-<M^LM-eM-8M^LM-fM^\M^[M-hM-?M^YM-gM-/M^GM-fM^VM^GM-gM-+\240M-hM^CM-=M-eM-8M-.M-eM^HM-0M-dM-=\240M-cM^@M^B\012\012M-eM-&M^BM-fM^^M^\M-fM^\M^IM-iM^WM-.M-iM-"M^XM-oM-<M^LM-fM-,M-"M-hM-?M^NM-eM^\M-(M-hM-/M^DM-hM-.M-:M-eM^LM-:M-hM-.M-(M-hM-.M-:M-cM^@M^B\012\012---\012\012*M-dM-=M^\M-hM^@M^EM-oM-<M^ZM-eM-0M^OM-eM^EM--M-oM-<M^LM-dM-8M^@M-dM-8M-*M-eM^\M-(M-dM-8M^JM-fM-5M-7M-eM^JM-*M-eM^JM^[M-fM^PM-,M-g\240M^VM-gM^ZM^DM-gM-(M^KM-eM-:M^OM-eM^QM^X*\012EOFTECH"
margrop          39010   0.0  0.0 410735344   2608   ??  Ss    9:03PM   0:00.01 /bin/zsh -c ssh root@博客服务器 "cat > /root/SITES/blog2/source/_posts/ai_tech/2026-03-04-proxy-server-network-troubleshooting.md << 'EOFTECH'\012---\012title: M-hM-.M-0M-dM-8M^@M-fM-,M-!M-dM-;M-#M-gM^PM^FM-fM^\M^MM-eM^JM-!M-eM^YM-(SOCKS5M-hM-?M^^M-fM^NM-%M-eM-<M^BM-eM-8M-8M-gM^ZM^DM-eM-.M^LM-fM^UM-4M-fM^NM^RM-fM^_M-%M-oM-<M^ZM-dM-;M^NM-fM^\M-,M-eM^\M-0M-eM^HM-0M-hM-7M-/M-gM^TM-1M-eM^YM-(M-gM^ZM^DM-gM-=M^QM-gM-;M^\M-fM^UM^EM-iM^ZM^\M-eM-.M^ZM-dM-=M^M\012categories:\012  - ai_tech\012tags:\012  - M-fM^JM^@M-fM^\M-/\012  - M-hM-?M^PM-gM-;M-4\012  - M-iM^WM-.M-iM-"M^XM-fM^NM^RM-fM^_M-%\012  - M-gM-=M^QM-gM-;M^\\012  - SOCKS5\012cover: 'https://picsum.photos/seed/tech0304/1280/720'\012coverWidth: 1280\012coverHeight: 720\012date: 2026-03-04 21:30:00\012---\012\012## M-eM^IM^MM-hM-(M^@\012\012M-eM^\M-(M-hM-?M^PM-gM-;M-4M-eM-7M-%M-dM-=M^\M-dM-8M--M-oM-<M^LM-gM-;M^OM-eM-8M-8M-dM-<M^ZM-iM^AM^GM-eM^HM-0"M-eM^TM-/M-gM^KM-,M-fM^_M^PM-eM^OM-0M-fM^\M-:M-eM^YM-(M-dM-8M^MM-hM-!M^L"M-gM^ZM^DM-gM^NM^DM-eM--M-&M-iM^WM-.M-iM-"M^XM-cM^@M^BM-hM-?M^YM-gM-'M^MM-iM^WM-.M-iM-"M^XM-fM^NM^RM-fM^_M-%M-hM-5M-7M-fM^]M-%M-eM->M^@M-eM->M^@M-hM-.M-)M-dM-:M-:M-fM^JM^SM-gM^KM^BM-bM^@M^TM-bM^@M^TM-eM^EM-6M-dM-;M^VM-fM^\M-:M-eM^YM-(M-iM^CM-=M-fM--M-#M-eM-8M-8M-oM-<M^LM-eM-0M-1M-fM^\M-,M-fM^\M-:M-dM-8M^MM-hM-!M^LM-oM-<M^LM-dM-=\240M-hM-/M-4M-fM-0M^TM-dM-:M-:M-dM-8M^MM-fM-0M^TM-dM-:M-:M-oM-<M^_\012\012M-fM^\M-,M-fM^VM^GM-eM-0M^FM-hM-/M-&M-gM-;M^FM-hM-.M-0M-eM-=M^UM-dM-8M^@M-fM-,M-!M-eM^EM-3M-dM-:M^NSOCKS5M-dM-;M-#M-gM^PM^FM-fM^\M^MM-eM^JM-!M-eM^YM-(M-hM-?M^^M-fM^NM-%M-eM-<M^BM-eM-8M-8M-gM^ZM^DM-eM-.M^LM-fM^UM-4M-fM^NM^RM-fM^_M-%M-hM-?M^GM-gM-(M^KM-oM-<M^LM-fM^\M^@M-gM-;M^HM-eM-.M^ZM-dM-=M^MM-eM^HM-0M-hM-7M-/M-gM^TM-1M-eM^YM-(M-eM-1M^BM-iM^]M-"M-gM^ZM^DM-iM^WM-.M-iM-"M^XM-cM^@M^BM-eM-8M^LM-fM^\M^[M-hM^CM-=M-gM-;M^YM-iM^AM^GM-eM^HM-0M-gM-1M-;M-dM-<M-<M-gM-=M^QM-gM-;M^\M-fM^UM^EM-iM^ZM^\M-gM^ZM^DM-eM^PM^LM-eM--M-&M-dM-8M^@M-dM-:M^[M-eM^OM^BM-hM^@M^CM-cM^@M^B\012\012## M-iM^WM-.M-iM-"M^XM-hM^CM^LM-fM^YM-/\012\012### M-dM-8M^ZM-eM^JM-!M-eM^\M-:M-fM^YM-/\012\012M-fM^HM^QM-dM-;M-,M-gM^ZM^DM-eM^_M-:M-gM-!M^@M-fM^^M-6M-fM^^M^DM-dM-8M--M-iM^CM-(M-gM-=M-2M-dM-:M^FM-eM-$M^ZM-eM^OM-0SOCKS5M-dM-;M-#M-gM^PM^FM-fM^\M^MM-eM^JM-!M-eM^YM-(M-oM-<M^LM-gM^TM-(M-dM-:M^NM-hM-.M-?M-iM^WM-.M-eM-$M^VM-iM^CM-(M-fM^\M^MM-eM^JM-!M-cM^@M^BM-eM^EM-6M-dM-8M--M-dM-8M^@M-eM^OM-0M-dM-;M-#M-gM^PM^FM-fM^\M^MM-eM^JM-!M-eM^YM-(M-oM-<M^HIP: M-fM^_M^PM-dM-;M-#M-gM^PM^FM-fM^\M^MM-eM^JM-!M-eM^YM-(M-oM-<M^IM-hM-?M^PM-hM-!M^LM-fM--M-#M-eM-8M-8M-oM-<M^LM-dM-=M^FM-dM-;M^NM-fM^\M-,M-eM^\M-0MacM-gM^TM-5M-hM^DM^QM-eM-'M^KM-gM-;M^HM-fM^W\240M-fM-3M^UM-hM-?M^^M-fM^NM-%M-cM^@M^B\012\012### M-iM^WM-.M-iM-"M^XM-gM^NM-0M-hM-1M-!\012\012- **M-fM^UM^EM-iM^ZM^\M-fM^WM-6M-iM^WM-4**M-oM-<M^ZM-hM-?M^QM-fM^\M^_M-fM^_M^PM-fM^WM-%M-fM^WM-)M-dM-8M^J\012- **M-fM^UM^EM-iM^ZM^\M-hM-!M-(M-gM^NM-0**M-oM-<M^ZM-fM^\M-,M-eM^\M-0M-gM^TM-5M-hM^DM^QM-fM^W\240M-fM-3M^UM-iM^@M^ZM-hM-?M^GSOCKS5M-dM-;M-#M-gM^PM^FM-hM-.M-?M-iM^WM-.M-eM-$M^VM-gM-=M^Q\012- **M-eM-<M^BM-eM-8M-8M-gM^JM-6M-fM^@M^A**M-oM-<M^Z\012  - M-dM-;M-#M-gM^PM^FM-fM^\M^MM-eM^JM-!M-hM-?M^[M-gM-(M^KM-fM--M-#M-eM-8M-8M-hM-?M^PM-hM-!M^L\012  - M-gM-+M-/M-eM^OM-#M-fM--M-#M-eM-8M-8M-gM^[M^QM-eM^PM-,\012  - M-eM^EM-6M-dM-;M^VM-fM^\M^MM-eM^JM-!M-eM^YM-(M-oM-<M^HVM151M-cM^@M^AVM152M-oM-<M^IM-hM-?M^^M-fM^NM-%M-fM--M-#M-eM-8M-8\012  - M-fM^\M-,M-eM^\M-0M-gM^TM-5M-hM^DM^QM-hM-?M^^M-fM^NM-%M-hM-6M^EM-fM^WM-6\012\012### M-gM^NM-/M-eM-"M^CM-dM-?M-!M-fM^AM-/\012\012| M-hM-.M->M-eM-$M^G | IP | M-hM-?M^^M-fM^NM-%M-gM^JM-6M-fM^@M^A |\012|------|-----|---------|\012| M-fM^\M-,M-eM^\M-0 Mac | M-fM^_M^PIPM-eM^\M-0M-eM^]M^@ | M-bM^]M^L M-hM-6M^EM-fM^WM-6 |\012| VM151 | M-fM^_M^PIPM-eM^\M-0M-eM^]M^@ | M-bM^\M^E M-fM--M-#M-eM-8M-8 |\012| VM152 | M-fM^_M^PIPM-eM^\M-0M-eM^]M^@ | M-bM^\M^E M-fM--M-#M-eM-8M-8 |\012| M-dM-;M-#M-gM^PM^FM-fM^\M^MM-eM^JM-!M-eM^YM-( | M-fM^_M^PIPM-eM^\M-0M-eM^]M^@ | M-bM^\M^E M-hM-?M^PM-hM-!M^LM-dM-8M-- |\012\012## M-fM^NM^RM-fM^_M-%M-hM-?M^GM-gM-(M^K\012\012### M-gM-,M-,M-dM-8M^@M-fM--M-%M-oM-<M^ZM-gM-!M-.M-hM-.M-$M-dM-;M-#M-gM^PM^FM-fM^\M^MM-eM^JM-!M-gM^JM-6M-fM^@M^A\012\012M-iM-&M^VM-eM^EM^HM-iM^@M^ZM-hM-?M^GSSHM-gM^YM-;M-eM-=M^UM-eM^HM-0M-dM-;M-#M-gM^PM^FM-fM^\M^MM-eM^JM-!M-eM^YM-(M-oM-<M^LM-fM-#M^@M-fM^_M-%M-fM^\M^MM-eM^JM-!M-fM^XM-/M-eM^PM-&M-fM--M-#M-eM-8M-8M-hM-?M^PM-hM-!M^LM-oM-<M^Z\012\012```bash\012# M-fM^_M-%M-gM^\M^KM-hM-?M^[M-gM-(M^KM-fM^XM-/M-eM^PM-&M-eM--M^XM-fM-4M-;\012ps aux | grep proxy\012\012# M-fM^_M-%M-gM^\M^KM-gM-+M-/M-eM^OM-#M-gM^[M^QM-eM^PM-,M-gM^JM-6M-fM^@M^A\012netstat -tlnp | grep 1080\012\012# M-fM^HM^VM-hM^@M^EM-dM-=M-?M-gM^TM-( ss M-eM^QM-=M-dM-;M-$\012ss -tlnp | grep 1080\012\012# M-fM^_M-%M-gM^\M^KM-fM^WM-%M-eM-?M^W\012tail -f /var/log/proxy.log\012```\012\012**M-gM-;M^SM-fM^^M^\**M-oM-<M^ZM-fM^\M^MM-eM^JM-!M-hM-?M^[M-gM-(M^KM-fM--M-#M-eM-8M-8M-hM-?M^PM-hM-!M^LM-oM-<M^LM-gM-+M-/M-eM^OM-#1080M-fM--M-#M-eM-8M-8M-gM^[M^QM-eM^PM-,M-oM-<M^LM-fM^WM-%M-eM-?M^WM-fM^W\240M-iM^TM^YM-hM-/M-/M-dM-?M-!M-fM^AM-/M-cM^@M^B\012\012### M-gM-,M-,M-dM-:M^LM-fM--M-%M-oM-<M^ZM-fM-5M^KM-hM-/M^UM-fM^\M-,M-eM^\M-0M-gM-=M^QM-gM-;M^\M-hM-?M^^M-iM^@M^ZM-fM^@M-'\012\012M-dM-;M^NM-fM^\M-,M-eM^\M-0M-gM^TM-5M-hM^DM^QM-hM-?M^[M-hM-!M^LM-gM-=M^QM-gM-;M^\M-fM-5M^KM-hM-/M^UM-oM-<M^Z\012\012```bash\012# M-fM-5M^KM-hM-/M^UM-gM-=M^QM-eM^EM-3M-hM-?M^^M-iM^@M^ZM-fM^@M-'\012ping M-gM-=M^QM-eM^EM-3IP\012\012# M-fM-5M^KM-hM-/M^UM-dM-;M-#M-gM^PM^FM-fM^\M^MM-eM^JM-!M-eM^YM-(M-hM-?M^^M-iM^@M^ZM-fM^@M-'\012ping M-dM-;M-#M-gM^PM^FM-fM^\M^MM-eM^JM-!M-eM^YM-(IP\012\012# M-fM-5M^KM-hM-/M^UM-gM-+M-/M-eM^OM-#M-hM-?M^^M-iM^@M^ZM-fM^@M-'\012telnet M-dM-;M-#M-gM^PM^FM-fM^\M^MM-eM^JM-!M-eM^YM-(IP 1080\012\012# M-fM^HM^VM-hM^@M^EM-dM-=M-?M-gM^TM-( nc M-eM^QM-=M-dM-;M-$\012nc -zv M-dM-;M-#M-gM^PM^FM-fM^\M^MM-eM^JM-!M-eM^YM-(IP 1080 -w 5\012```\012\012**M-gM-;M^SM-fM^^M^\**M-oM-<M^Z\012- ping M-gM-=M^QM-eM^EM-3M-oM-<M^ZM-fM--M-#M-eM-8M-8\012- ping M-dM-;M-#M-gM^PM^FM-fM^\M^MM-eM^JM-!M-eM^YM-(M-oM-<M^ZM-iM^CM-(M-eM^HM^FM-dM-8M-"M-eM^LM^EM-oM-<M^HM-iM^WM-.M-iM-"M^XM-gM-:M-?M-gM-4M-"+1M-oM-<M^I\012- telnet M-gM-+M-/M-eM^OM-#M-oM-<M^ZM-hM-6M^EM-fM^WM-6\012\012### M-gM-,M-,M-dM-8M^IM-fM--M-%M-oM-<M^ZM-fM-5M^KM-hM-/M^UM-eM^EM-6M-dM-;M^VM-fM^\M^MM-eM^JM-!M-eM^YM-(\012\012M-dM-;M^NVM151M-eM^RM^LVM152M-fM-5M^KM-hM-/M^UM-hM-?M^^M-fM^NM-%M-oM-<M^Z\012\012```bash\012# M-dM-;M^N VM151 M-fM-5M^KM-hM-/M^U\012ssh root@M-fM^_M^PVM151 "nc -zv M-dM-;M-#M-gM^PM^FM-fM^\M^MM-eM^JM-!M-eM^YM-(IP 1080"\012\012# M-dM-;M^N VM152 M-fM-5M^KM-hM-/M^U\012ssh root@M-fM^_M^PVM152 "nc -zv M-dM-;M-#M-gM^PM^FM-fM^\M^MM-eM^JM-!M-eM^YM-(IP 1080"\012```\012\012**M-gM-;M^SM-fM^^M^\**M-oM-<M^ZVM151M-eM^RM^LVM152M-iM^CM-=M-hM^CM-=M-fM--M-#M-eM-8M-8M-hM-?M^^M-fM^NM-%M-dM-;M-#M-gM^PM^FM-fM^\M^MM-eM^JM-!M-eM^YM-(M-cM^@M^B\012\012### M-gM-,M-,M-eM^[M^[M-fM--M-%M-oM-<M^ZM-hM-7M-/M-gM^TM-1M-hM-?M-=M-hM-8M-*\012\012M-dM-=M-?M-gM^TM-(tracerouteM-eM^HM^FM-fM^^M^PM-hM-7M-/M-gM^TM-1M-hM-7M-/M-eM->M^DM-oM-<M^Z\012\012```bash\012# M-fM^\M-,M-eM^\M-0 traceroute\012traceroute M-dM-;M-#M-gM^PM^FM-fM^\M^MM-eM^JM-!M-eM^YM-(IP\012\012# VM151 traceroute\012ssh root@M-fM^_M^PVM151 "traceroute M-dM-;M-#M-gM^PM^FM-fM^\M^MM-eM^JM-!M-eM^YM-(IP"\012```\012\012**M-gM-;M^SM-fM^^M^\**M-oM-<M^ZM-fM^\M-,M-eM^\M-0tracerouteM-fM^XM->M-gM-$M-:M-fM^\M^IM-hM-7M-/M-gM^TM-1M-hM-7M-3M-fM^UM-0M-eM-<M^BM-eM-8M-8M-oM-<M^LM-hM^@M^LVM151M-gM^ZM^DM-hM-7M-/M-gM^TM-1M-fM--M-#M-eM-8M-8M-cM^@M^B\012\012### M-gM-,M-,M-dM-:M^TM-fM--M-%M-oM-<M^ZM-fM^@M^@M-gM^VM^QM-hM-7M-/M-gM^TM-1M-eM^YM-(M-iM^WM-.M-iM-"M^X\012\012M-gM-;M^SM-eM^PM^HM-dM-;M-%M-dM-8M^JM-fM-5M^KM-hM-/M^UM-gM-;M^SM-fM^^M^\M-oM-<M^LM-iM^WM-.M-iM-"M^XM-eM->M^HM-eM^OM-/M-hM^CM-=M-eM^GM-:M-eM^\M-(M-hM-7M-/M-gM^TM-1M-eM^YM-(M-eM-1M^BM-iM^]M-"M-oM-<M^Z\012\0121. M-dM-;M-#M-gM^PM^FM-fM^\M^MM-eM^JM-!M-eM^YM-(M-fM^\M-,M-hM-:M-+M-fM-2M-!M-iM^WM-.M-iM-"M^XM-oM-<M^HM-eM^EM-6M-dM-;M^VM-fM^\M^MM-eM^JM-!M-eM^YM-(M-hM^CM-=M-hM-?M^^M-oM-<M^I\0122. M-fM^\M-,M-eM^\M-0M-eM^HM-0M-dM-;M-#M-gM^PM^FM-fM^\M^MM-eM^JM-!M-eM^YM-(M-fM^\M^IM-dM-8M-"M-eM^LM^E\0123. tracerouteM-fM^XM->M-gM-$M-:M-eM-<M^BM-eM-8M-8\012\012M-hM-?M^YM-dM-:M^[M-iM^WM-.M-iM-"M^XM-fM^LM^GM-eM^PM^QM-eM^PM^LM-dM-8M^@M-dM-8M-*M-eM^NM^_M-eM^[\240M-oM-<M^Z**M-gM-=M^QM-gM-;M^\M-hM-7M-/M-gM^TM-1M-eM^YM-(M-eM-<M^BM-eM-8M-8**M-cM^@M^B\012\012### M-gM-,M-,M-eM^EM--M-fM--M-%M-oM-<M^ZM-eM-0M^]M-hM-/M^UM-hM-'M-#M-eM^FM-3M-fM^VM-9M-fM-!M^H\012\012M-gM^TM-1M-dM-:M^NM-hM-7M-/M-gM^TM-1M-eM^YM-(M-dM-8M^MM-eM^\M-(M-gM^[M-4M-fM^NM-%M-gM-.M-!M-gM^PM^FM-hM^LM^CM-eM^[M-4M-eM^FM^EM-oM-<M^LM-iM^GM^GM-eM^OM^VM-dM-:M^FM-dM-;M-%M-dM-8M^KM-eM-0M^]M-hM-/M^UM-oM-<M^Z\012\012```bash\012# M-eM-0M^]M-hM-/M^UM-eM^HM-7M-fM^VM-0M-fM^\M-,M-eM^\M-0DNSM-gM-<M^SM-eM--M^X\012sudo dscacheutil -flushcache\012sudo killall -HUP mDNSResponder\012\012# M-fM-#M^@M-fM^_M-%M-fM^\M-,M-eM^\M-0M-gM-=M^QM-gM-;M^\M-iM^EM^MM-gM-=M-.\012networksetup -listallhardwareports\012\012# M-eM-0M^]M-hM-/M^UM-gM^[M-4M-fM^NM-%M-iM^@M^ZM-hM-?M^GIPM-hM-.M-?M-iM^WM-.M-oM-<M^HM-dM-8M^MM-dM-=M-?M-gM^TM-(M-eM^_M^_M-eM^PM^MM-oM-<M^I\012curl -x socks5h://M-dM-;M-#M-gM^PM^FM-fM^\M^MM-eM^JM-!M-eM^YM-(IP:1080 http://example.com\012```\012\012**M-gM-;M^SM-fM^^M^\**M-oM-<M^ZM-iM^WM-.M-iM-"M^XM-dM->M^]M-fM^WM-'M-cM^@M^B\012\012### M-gM-,M-,M-dM-8M^CM-fM--M-%M-oM-<M^ZM-gM--M^IM-eM->M^EM-hM^GM-*M-eM^JM-(M-fM^AM-"M-eM-$M^M\012\012M-eM-0M-1M-eM^\M-(M-eM^GM^FM-eM-$M^GM-fM^TM->M-eM-<M^CM-fM^NM^RM-fM^_M-%M-gM^ZM^DM-fM^WM-6M-eM^@M^YM-oM-<M^LM-dM-;M-#M-gM^PM^FM-hM-?M^^M-fM^NM-%M-gM-*M^AM-gM^DM-6M-fM^AM-"M-eM-$M^MM-fM--M-#M-eM-8M-8M-dM-:M^FM-cM^@M^BM-eM^PM^NM-fM^]M-%M-dM-:M^FM-hM-'M-#M-eM^HM-0M-oM-<M^LM-hM-?M^PM-gM-;M-4M-dM-:M-:M-eM^QM^XM-iM^GM^MM-eM^PM-/M-dM-:M^FM-hM-7M-/M-gM^TM-1M-eM^YM-(M-oM-<M^LM-iM^WM-.M-iM-"M^XM-hM^GM-*M-hM-!M^LM-fM-6M^HM-eM-$M-1M-cM^@M^B\012\012**M-gM-;M^SM-hM-.M-:**M-oM-<M^ZM-hM-?M^YM-fM^XM-/M-dM-8M^@M-hM-5M-7M-eM^EM-8M-eM^^M^KM-gM^ZM^DM-hM-7M-/M-gM^TM-1M-eM^YM-(M-fM^UM^EM-iM^ZM^\M-eM-/M-<M-hM^GM-4M-gM^ZM^DM-gM-=M^QM-gM-;M^\M-iM^WM-.M-iM-"M^XM-cM^@M^B\012\012## M-f\240M-9M-eM^[\240M-eM^HM^FM-fM^^M^P\012\012### M-iM^WM-.M-iM-"M^XM-f\240M-9M-eM^[\240\012\012M-hM-?M^YM-fM-,M-!M-iM^WM-.M-iM-"M^XM-gM^ZM^DM-f\240M-9M-fM^\M-,M-eM^NM^_M-eM^[\240M-fM^XM-/M-oM-<M^Z**M-gM-=M^QM-gM-;M^\M-hM-7M-/M-gM^TM-1M-eM^YM-(M-eM-<M^BM-eM-8M-8**M-cM^@M^B\012\012M-eM^EM-7M-dM-=M^SM-eM^OM-/M-hM^CM-=M-gM^ZM^DM-eM^NM^_M-eM^[\240M-eM^LM^EM-fM^KM-,M-oM-<M^Z\0121. M-hM-7M-/M-gM^TM-1M-eM^YM-(M-eM^[M-:M-dM-;M-6bug\0122. M-hM-7M-/M-gM^TM-1M-eM^YM-(M-hM-4M^_M-hM-=M-=M-hM-?M^GM-iM-+M^X\0123. M-hM-7M-/M-gM^TM-1M-hM-!M-(M-eM-<M^BM-eM-8M-8\0124. M-hM-7M-/M-gM^TM-1M-eM^YM-(M-fM-8M-)M-eM-:M-&M-hM-?M^GM-iM-+M^XM-eM-/M-<M-hM^GM-4M-gM^ZM^DM-dM-8M-4M-fM^WM-6M-fM^UM^EM-iM^ZM^\\012\012### M-dM-8M-:M-dM-;M^@M-dM-9M^HM-eM^EM-6M-dM-;M^VM-fM^\M^MM-eM^JM-!M-eM^YM-(M-fM--M-#M-eM-8M-8\012\012VM151M-eM^RM^LVM152M-fM^IM^@M-eM^\M-(M-gM^ZM^DM-gM-=M^QM-gM-;M^\M-fM-.M-5M-dM-8M^NM-fM^\M-,M-eM^\M-0M-gM^TM-5M-hM^DM^QM-dM-8M^MM-eM^PM^LM-oM-<M^LM-eM-.M^CM-dM-;M-,M-eM^OM-/M-hM^CM-=M-hM-5M-0M-gM^ZM^DM-fM^XM-/M-dM-8M^MM-eM^PM^LM-gM^ZM^DM-hM-7M-/M-gM^TM-1M-eM^YM-(M-fM^HM^VM-hM-7M-/M-gM^TM-1M-hM-7M-/M-eM->M^DM-oM-<M^LM-eM^[\240M-fM--M-$M-fM-2M-!M-fM^\M^IM-eM^OM^WM-eM^HM-0M-eM-=M-1M-eM^SM^MM-cM^@M^B\012\012## M-hM-'M-#M-eM^FM-3M-fM^VM-9M-fM-!M^H\012\012### M-gM^_M--M-fM^\M^_M-hM-'M-#M-eM^FM-3M-fM^VM-9M-fM-!M^H\012\0121. **M-gM--M^IM-eM->M^EM-hM^GM-*M-eM^JM-(M-fM^AM-"M-eM-$M^M**M-oM-<M^ZM-eM-&M^BM-fM^\M-,M-fM-,M-!M-fM-!M^HM-dM->M^KM-oM-<M^LM-hM-7M-/M-gM^TM-1M-eM^YM-(M-hM^GM-*M-hM-!M^LM-fM^AM-"M-eM-$M^M\0122. **M-iM^GM^MM-eM^PM-/M-hM-7M-/M-gM^TM-1M-eM^YM-(**M-oM-<M^ZM-eM-&M^BM-fM^^M^\M-fM^\M^IM-hM-7M-/M-gM^TM-1M-eM^YM-(M-gM-.M-!M-gM^PM^FM-fM^]M^CM-iM^YM^PM-oM-<M^LM-eM^OM-/M-dM-;M-%M-eM-0M^]M-hM-/M^UM-iM^GM^MM-eM^PM-/\0123. **M-eM^HM^GM-fM^MM-"M-gM-=M^QM-gM-;M^\**M-oM-<M^ZM-eM-&M^BM-fM^^M^\M-fM^]M-!M-dM-;M-6M-eM^EM^AM-hM-.M-8M-oM-<M^LM-eM^HM^GM-fM^MM-"M-eM^HM-0M-eM^EM-6M-dM-;M^VM-gM-=M^QM-gM-;M^\M-fM-.M-5\012\012### M-iM^UM-?M-fM^\M^_M-hM-'M-#M-eM^FM-3M-fM^VM-9M-fM-!M^H\012\0121. **M-gM-=M^QM-gM-;M^\M-eM^FM^WM-dM-=M^Y**M-oM-<M^ZM-iM^EM^MM-gM-=M-.M-eM-$M^ZM-hM-7M-/M-gM^TM-1M-eM^YM-(M-eM-$M^GM-dM-;M-=\0122. **M-gM^[M^QM-fM^NM-'M-eM^QM^JM-hM--M-&**M-oM-<M^ZM-iM^CM-(M-gM-=M-2M-gM-=M^QM-gM-;M^\M-gM^[M^QM-fM^NM-'M-oM-<M^LM-eM^OM^JM-fM^WM-6M-eM^OM^QM-gM^NM-0M-iM^WM-.M-iM-"M^X\0123. **M-eM-.M^ZM-fM^\M^_M-gM-;M-4M-fM^JM-$**M-oM-<M^ZM-eM-.M^ZM-fM^\M^_M-iM^GM^MM-eM^PM-/M-hM-7M-/M-gM^TM-1M-eM^YM-(M-oM-<M^LM-fM^[M-4M-fM^VM-0M-eM^[M-:M-dM-;M-6\0124. **M-fM^WM-%M-eM-?M^WM-eM^HM^FM-fM^^M^P**M-oM-<M^ZM-dM-?M^]M-gM^UM^YM-gM-=M^QM-gM-;M^\M-hM-.M->M-eM-$M^GM-fM^WM-%M-eM-?M^WM-oM-<M^LM-dM->M-?M-dM-:M^NM-iM^WM-.M-iM-"M^XM-fM^NM^RM-fM^_M-%\012\012## M-dM-8M^@M-iM^TM-.M-fM^NM^RM-fM^_M-%M-hM^DM^ZM-fM^\M-,\012\012M-eM-&M^BM-fM^^M^\M-dM-=\240M-iM^AM^GM-eM^HM-0M-gM-1M-;M-dM-<M-<M-iM^WM-.M-iM-"M^XM-oM-<M^LM-eM^OM-/M-dM-;M-%M-dM-=M-?M-gM^TM-(M-dM-;M-%M-dM-8M^KM-hM^DM^ZM-fM^\M-,M-hM-?M^[M-hM-!M^LM-eM-?M-+M-iM^@M^_M-fM^NM^RM-fM^_M-%M-oM-<M^Z\012\012```bash\012#!/bin/bash\012\012# M-gM-=M^QM-gM-;M^\M-hM-?M^^M-iM^@M^ZM-fM^@M-'M-fM^NM^RM-fM^_M-%M-hM^DM^ZM-fM^\M-,\012\012TARGET_IP="M-dM-;M-#M-gM^PM^FM-fM^\M^MM-eM^JM-!M-eM^YM-(IP"\012TARGET_PORT="1080"\012GATEWAY="M-gM-=M^QM-eM^EM-3IP"\012\012echo "=== M-gM-=M^QM-gM-;M^\M-hM-?M^^M-iM^@M^ZM-fM^@M-'M-fM^NM^RM-fM^_M-% ==="\012echo ""\012\012echo "1. M-fM-5M^KM-hM-/M^UM-gM-=M^QM-eM^EM-3M-hM-?M^^M-iM^@M^ZM-fM^@M-'..."\012ping -c 3 $GATEWAY\012echo ""\012\012echo "2. M-fM-5M^KM-hM-/M^UM-gM^[M-.M-f\240M^GM-fM^\M^MM-eM^JM-!M-eM^YM-(M-hM-?M^^M-iM^@M^ZM-fM^@M-'..."\012ping -c 3 $TARGET_IP\012echo ""\012\012echo "3. M-fM-5M^KM-hM-/M^UM-gM^[M-.M-f\240M^GM-gM-+M-/M-eM^OM-#M-hM-?M^^M-iM^@M^ZM-fM^@M-'..."\012nc -zv -w 5 $TARGET_IP $TARGET_PORT\012echo ""\012\012echo "4. M-hM-7M-/M-gM^TM-1M-hM-?M-=M-hM-8M-*..."\012traceroute $TARGET_IP\012echo ""\012\012echo "5. M-fM-#M^@M-fM^_M-%M-fM^\M-,M-eM^\M-0M-gM-=M^QM-gM-;M^\M-fM^NM-%M-eM^OM-#..."\012networksetup -listallhardwareports\012echo ""\012\012echo "6. M-fM-#M^@M-fM^_M-% DNS M-hM-'M-#M-fM^^M^P..."\012nslookup example.com\012echo ""\012\012echo "=== M-fM^NM^RM-fM^_M-%M-eM-.M^LM-fM^HM^P ==="\012```\012\012## M-eM-8M-8M-hM-'M^AM-iM^WM-.M-iM-"M^XM-hM-'M-#M-gM--M^T\012\012**QM-oM-<M^ZM-dM-8M-:M-dM-;M^@M-dM-9M^HM-eM^EM-6M-dM-;M^VM-fM^\M^MM-eM^JM-!M-eM^YM-(M-hM^CM-=M-hM-?M^^M-fM^\M-,M-eM^\M-0M-dM-8M^MM-hM^CM-=M-hM-?M^^M-oM-<M^_**\012\012AM-oM-<M^ZM-fM^\M^@M-eM^OM-/M-hM^CM-=M-gM^ZM^DM-eM^NM^_M-eM^[\240M-fM^XM-/M-gM-=M^QM-gM-;M^\M-hM-7M-/M-eM->M^DM-dM-8M^MM-eM^PM^LM-cM^@M^BM-fM^\M-,M-eM^\M-0M-gM^TM-5M-hM^DM^QM-eM^RM^LM-fM^\M^MM-eM^JM-!M-eM^YM-(M-eM^OM-/M-hM^CM-=M-hM-5M-0M-gM^ZM^DM-fM^XM-/M-dM-8M^MM-eM^PM^LM-gM^ZM^DM-hM-7M-/M-gM^TM-1M-eM^YM-(M-fM^HM^VM-gM-=M^QM-eM^EM-3M-oM-<M^LM-eM^EM-6M-dM-8M--M-dM-8M^@M-dM-8M-*M-hM-7M-/M-gM^TM-1M-eM^YM-(M-eM^GM-:M-gM^NM-0M-iM^WM-.M-iM-"M^XM-eM-0M-1M-dM-<M^ZM-eM-/M-<M-hM^GM-4M-eM-1M^@M-iM^CM-(M-gM-=M^QM-gM-;M^\M-eM-<M^BM-eM-8M-8M-cM^@M^B\012\012**QM-oM-<M^ZM-iM^\M^@M-hM-&M^AM-iM^GM^MM-eM^PM-/M-hM-7M-/M-gM^TM-1M-eM^YM-(M-eM^PM^WM-oM-<M^_**\012\012AM-oM-<M^ZM-eM-&M^BM-fM^^M^\M-fM^XM-/M-hM-7M-/M-gM^TM-1M-eM^YM-(M-iM^WM-.M-iM-"M^XM-oM-<M^LM-iM^GM^MM-eM^PM-/M-iM^@M^ZM-eM-8M-8M-hM^CM-=M-hM-'M-#M-eM^FM-3M-cM^@M^BM-dM-=M^FM-eM-;M-:M-hM-.M-.M-eM^EM^HM-gM-!M-.M-hM-.M-$M-iM^WM-.M-iM-"M^XM-gM-!M-.M-eM-.M^^M-eM^GM-:M-eM^\M-(M-hM-7M-/M-gM^TM-1M-eM^YM-(M-eM-1M^BM-iM^]M-"M-oM-<M^LM-iM^AM-?M-eM^EM^MM-iM^GM^MM-eM^PM-/M-eM^PM^NM-iM^WM-.M-iM-"M^XM-dM->M^]M-fM^WM-'M-cM^@M^B\012\012**QM-oM-<M^ZM-eM-&M^BM-dM-=M^UM-iM-"M^DM-iM^XM-2M-fM--M-$M-gM-1M-;M-iM^WM-.M-iM-"M^XM-oM-<M^_**\012\012AM-oM-<M^Z\0121. M-iM^CM-(M-gM-=M-2M-gM-=M^QM-gM-;M^\M-gM^[M^QM-fM^NM-'M-gM-3M-;M-gM-;M^_\0122. M-iM^EM^MM-gM-=M-.M-gM-=M^QM-gM-;M^\M-eM^FM^WM-dM-=M^Y\0123. M-eM-.M^ZM-fM^\M^_M-gM-;M-4M-fM^JM-$M-gM-=M^QM-gM-;M^\M-hM-.M->M-eM-$M^G\0124. M-dM-?M^]M-fM^LM^AM-eM^[M-:M-dM-;M-6M-fM^[M-4M-fM^VM-0\012\012**QM-oM-<M^ZM-fM^\M-,M-eM^\M-0M-gM-=M^QM-gM-;M^\M-fM^\M^IM-eM^EM-6M-dM-;M^VM-hM-'M-#M-eM^FM-3M-eM^JM^^M-fM-3M^UM-eM^PM^WM-oM-<M^_**\012\012AM-oM-<M^Z\0121. M-dM-=M-?M-gM^TM-(M-eM^EM-6M-dM-;M^VM-gM-=M^QM-gM-;M^\M-oM-<M^HM-eM-&M^BM-fM^IM^KM-fM^\M-:M-gM^CM--M-gM^BM-9M-oM-<M^I\0122. M-iM^@M^ZM-hM-?M^GVPNM-gM-;M^UM-hM-?M^GM-iM^WM-.M-iM-"M^XM-gM-=M^QM-gM-;M^\\0123. M-hM^AM^TM-gM-3M-;M-gM-=M^QM-gM-;M^\M-gM-.M-!M-gM^PM^FM-eM^QM^XM-eM-$M^DM-gM^PM^F\012\012**QM-oM-<M^ZM-eM-&M^BM-dM-=M^UM-eM^HM-$M-fM^VM--M-fM^XM-/M-dM-8M^MM-fM^XM-/M-hM-7M-/M-gM^TM-1M-eM^YM-(M-iM^WM-.M-iM-"M^XM-oM-<M^_**\012\012AM-oM-<M^Z\0121. pingM-gM^[M-.M-f\240M^GM-fM^\M^IM-dM-8M-"M-eM^LM^E\0122. tracerouteM-fM^XM->M-gM-$M-:M-eM-<M^BM-eM-8M-8M-hM-7M-3M-fM^UM-0\0123. M-eM^EM-6M-dM-;M^VM-hM-.M->M-eM-$M^GM-fM--M-#M-eM-8M-8M-oM-<M^LM-eM^OM-*M-fM^\M^IM-fM^\M-,M-fM^\M-:M-eM-<M^BM-eM-8M-8\0124. M-iM^GM^MM-eM^PM-/M-hM-7M-/M-gM^TM-1M-eM^YM-(M-eM^PM^NM-iM^WM-.M-iM-"M^XM-fM-6M^HM-eM-$M-1\012\012## M-gM-;M^OM-iM-*M^LM-fM^@M-;M-gM-;M^S\012\0121. **M-dM-8M^MM-hM-&M^AM-gM-!M-,M-fM^IM^[**M-oM-<M^ZM-hM-?M^YM-gM-'M^MM-gM^NM^DM-eM--M-&M-iM^WM-.M-iM-"M^XM-eM->M^HM-eM^OM-/M-hM^CM-=M-dM-8M^MM-fM^XM-/M-dM-=\240M-hM^CM-=M-hM-'M-#M-eM^FM-3M-gM^ZM^DM-oM-<M^LM-hM-/M-%M-fM^IM->M-gM-=M^QM-gM-;M^\M-gM-.M-!M-gM^PM^FM-eM^QM^XM-hM-&M^AM-fM^IM->\0122. **M-hM-.M-0M-eM-=M^UM-hM-/M^AM-fM^MM-.**M-oM-<M^ZM-fM^NM^RM-fM^_M-%M-hM-?M^GM-gM-(M^KM-hM-&M^AM-hM-.M-0M-eM-=M^UM-fM^WM-%M-eM-?M^WM-oM-<M^LM-fM^VM-9M-dM->M-?M-eM^PM^NM-gM-;M--M-eM-$M^MM-gM^[M^X\0123. **M-eM-?M^CM-fM^@M^AM-hM-&M^AM-eM-%M-=**M-oM-<M^ZM-fM^\M^IM-dM-:M^[M-iM^WM-.M-iM-"M^XM-fM^TM->M-gM^]M^@M-fM^TM->M-gM^]M^@M-eM-0M-1M-hM^GM-*M-eM-7M-1M-eM-%M-=M-dM-:M^FM-oM-<M^HM-dM-8M^MM-fM^XM-/M-eM-<M^@M-gM^NM-)M-gM-,M^QM-oM-<M^I\0124. **M-iM-"M^DM-iM^XM-2M-dM-8M-:M-dM-8M-;**M-oM-<M^ZM-eM^AM^ZM-eM-%M-=M-gM^[M^QM-fM^NM-'M-eM^RM^LM-eM^FM^WM-dM-=M^YM-oM-<M^LM-fM-/M^TM-dM-:M^KM-eM^PM^NM-fM^NM^RM-fM^_M-%M-fM^[M-4M-iM^GM^MM-hM-&M^A\0125. **M-eM-/M-9M-fM-/M^TM-fM-5M^KM-hM-/M^U**M-oM-<M^ZM-eM^VM^DM-gM^TM-("M-fM^NM^RM-iM^YM-$M-fM-3M^U"M-oM-<M^LM-iM^@M^ZM-hM-?M^GM-eM-/M-9M-fM-/M^TM-fM--M-#M-eM-8M-8M-eM^RM^LM-eM-<M^BM-eM-8M-8M-gM^ZM^DM-hM^JM^BM-gM^BM-9M-eM-?M-+M-iM^@M^_M-eM-.M^ZM-dM-=M^MM-iM^WM-.M-iM-"M^XM-hM^LM^CM-eM^[M-4\012\012## M-eM-;M-6M-dM-<M-8M-iM^XM^EM-hM-/M-;\012\012- [M-gM-=M^QM-gM-;M^\M-fM^NM^RM-fM^_M-%M-eM^QM-=M-dM-;M-$M-eM-$M-'M-eM^EM-(](/docs/network-troubleshooting)\012- [M-hM-7M-/M-gM^TM-1M-eM^YM-(M-gM-;M-4M-fM^JM-$M-fM^LM^GM-eM^MM^W](/docs/router-maintenance)\012- [M-gM^[M^QM-fM^NM-'M-eM^QM^JM-hM--M-&M-iM^EM^MM-gM-=M-.](/docs/monitoring-setup)\012\012## M-gM-;M^SM-hM-/M--\012\012M-hM-?M^YM-fM-,M-!M-iM^WM-.M-iM-"M^XM-hM^YM-=M-gM^DM-6M-fM^\M^@M-gM-;M^HM-fM^XM-/M-gM^NM^DM-eM--M-&M-hM^HM-,M-eM^\M-0M-hM^GM-*M-eM^JM-(M-fM^AM-"M-eM-$M^MM-dM-:M^FM-oM-<M^LM-dM-=M^FM-fM^NM^RM-fM^_M-%M-hM-?M^GM-gM-(M^KM-hM-?M^XM-fM^XM-/M-eM^@M-<M-eM->M^WM-hM-.M-0M-eM-=M^UM-gM^ZM^DM-cM^@M^BM-eM^\M-(M-hM-?M^PM-gM-;M-4M-eM-7M-%M-dM-=M^\M-dM-8M--M-oM-<M^LM-gM-1M-;M-dM-<M-<"M-eM^TM-/M-gM^KM-,M-fM^HM^QM-dM-8M^MM-hM^CM-="M-gM^ZM^DM-eM^\M-:M-fM^YM-/M-eM-9M-6M-dM-8M^MM-eM-0M^QM-hM-'M^AM-oM-<M^LM-eM-8M^LM-fM^\M^[M-hM-?M^YM-gM-/M^GM-fM^VM^GM-gM-+\240M-hM^CM-=M-eM-8M-.M-eM^HM-0M-dM-=\240M-cM^@M^B\012\012M-eM-&M^BM-fM^^M^\M-fM^\M^IM-iM^WM-.M-iM-"M^XM-oM-<M^LM-fM-,M-"M-hM-?M^NM-eM^\M-(M-hM-/M^DM-hM-.M-:M-eM^LM-:M-hM-.M-(M-hM-.M-:M-cM^@M^B\012\012---\012\012*M-dM-=M^\M-hM^@M^EM-oM-<M^ZM-eM-0M^OM-eM^EM--M-oM-<M^LM-dM-8M^@M-dM-8M-*M-eM^\M-(M-dM-8M^JM-fM-5M-7M-eM^JM-*M-eM^JM^[M-fM^PM-,M-g\240M^VM-gM^ZM^DM-gM-(M^KM-eM-:M^OM-eM^QM^X*\012EOFTECH"
margrop          49830   0.0  0.4 1865214944  59536   ??  S     2:00AM   0:04.02 /Applications/Google Chrome.app/Contents/Frameworks/Google Chrome Framework.framework/Versions/144.0.7559.133/Helpers/Google Chrome Helper.app/Contents/MacOS/Google Chrome Helper --type=utility --utility-sub-type=proxy_resolver.mojom.ProxyResolverFactory --lang=en-US --service-sandbox-type=service --shared-files --metrics-shmem-handle=1752395122,r,18218910699058371625,7356684326383652774,524288 --field-trial-handle=1718379636,r,14143067006290247523,14241204018161969264,262144 --variations-seed-version --trace-process-track-uuid=3190780176192265571 --seatbelt-client=250

**结果**：服务进程正常运行，端口1080正常监听，日志无错误信息。

### 第二步：测试本地网络连通性

从本地电脑进行网络测试：



**结果**：
- ping 网关：正常
- ping 代理服务器：部分丢包（问题线索+1）
- telnet 端口：超时

### 第三步：测试其他服务器

从VM151和VM152测试连接：



**结果**：VM151和VM152都能正常连接代理服务器。

### 第四步：路由追踪

使用traceroute分析路由路径：



**结果**：本地traceroute显示有路由跳数异常，而VM151的路由正常。

### 第五步：怀疑路由器问题

结合以上测试结果，问题很可能出在路由器层面：

1. 代理服务器本身没问题（其他服务器能连）
2. 本地到代理服务器有丢包
3. traceroute显示异常

这些问题指向同一个原因：**网络路由器异常**。

### 第六步：尝试解决方案

由于路由器不在直接管理范围内，采取了以下尝试：



**结果**：问题依旧。

### 第七步：等待自动恢复

就在准备放弃排查的时候，代理连接突然恢复正常了。后来了解到，运维人员重启了路由器，问题自行消失。

**结论**：这是一起典型的路由器故障导致的网络问题。

## 根因分析

### 问题根因

这次问题的根本原因是：**网络路由器异常**。

具体可能的原因包括：
1. 路由器固件bug
2. 路由器负载过高
3. 路由表异常
4. 路由器温度过高导致的临时故障

### 为什么其他服务器正常

VM151和VM152所在的网络段与本地电脑不同，它们可能走的是不同的路由器或路由路径，因此没有受到影响。

## 解决方案

### 短期解决方案

1. **等待自动恢复**：如本次案例，路由器自行恢复
2. **重启路由器**：如果有路由器管理权限，可以尝试重启
3. **切换网络**：如果条件允许，切换到其他网络段

### 长期解决方案

1. **网络冗余**：配置多路由器备份
2. **监控告警**：部署网络监控，及时发现问题
3. **定期维护**：定期重启路由器，更新固件
4. **日志分析**：保留网络设备日志，便于问题排查

## 一键排查脚本

如果你遇到类似问题，可以使用以下脚本进行快速排查：

=== 网络连通性排查 ===

1. 测试网关连通性...

2. 测试目标服务器连通性...

3. 测试目标端口连通性...

4. 路由追踪...

5. 检查本地网络接口...

6. 检查 DNS 解析...
Server:		内网DNS
Address:	内网DNS#53

Non-authoritative answer:
Name:	example.com
Address: 104.18.27.120
Name:	example.com
Address: 104.18.26.120


=== 排查完成 ===

## 常见问题解答

**Q：为什么其他服务器能连本地不能连？**

A：最可能的原因是网络路径不同。本地电脑和服务器可能走的是不同的路由器或网关，其中一个路由器出现问题就会导致局部网络异常。

**Q：需要重启路由器吗？**

A：如果是路由器问题，重启通常能解决。但建议先确认问题确实出在路由器层面，避免重启后问题依旧。

**Q：如何预防此类问题？**

A：
1. 部署网络监控系统
2. 配置网络冗余
3. 定期维护网络设备
4. 保持固件更新

**Q：本地网络有其他解决办法吗？**

A：
1. 使用其他网络（如手机热点）
2. 通过VPN绕过问题网络
3. 联系网络管理员处理

**Q：如何判断是不是路由器问题？**

A：
1. ping目标有丢包
2. traceroute显示异常跳数
3. 其他设备正常，只有本机异常
4. 重启路由器后问题消失

## 经验总结

1. **不要硬扛**：这种玄学问题很可能不是你能解决的，该找网络管理员要找
2. **记录证据**：排查过程要记录日志，方便后续复盘
3. **心态要好**：有些问题放着放着就自己好了（不是开玩笑）
4. **预防为主**：做好监控和冗余，比事后排查更重要
5. **对比测试**：善用排除法，通过对比正常和异常的节点快速定位问题范围

## 延伸阅读

- [网络排查命令大全](/docs/network-troubleshooting)
- [路由器维护指南](/docs/router-maintenance)
- [监控告警配置](/docs/monitoring-setup)

## 结语

这次问题虽然最终是玄学般地自动恢复了，但排查过程还是值得记录的。在运维工作中，类似唯独我不能的场景并不少见，希望这篇文章能帮到你。

如果有问题，欢迎在评论区讨论。

---

*作者：小六，一个在上海努力搬砖的程序员*
