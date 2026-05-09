---
title: immortalwrt（OpenWrt）软件包中英文对照表
categories:
  - ai_tech
tags:
  - OpenWrt
  - 路由器
  - immortalwrt
date: 2026-05-09 12:00:00
---

> 本文转载自 [alili.website](https://alili.website/posts/2025/immortalwrtopenwrt%E8%BD%AF%E4%BB%B6%E5%8C%85%E4%B8%AD%E8%8B%B1%E6%96%87%E5%AF%B9%E7%85%A7%E8%A1%A8/)，采用 CC BY-NC-SA 4.0 许可。

[immortalwrt 软件包合集](https://mirror.nju.edu.cn/immortalwrt/releases/24.10.1/packages/x86_64/luci/?sort=size&order=desc) | [ImmortalWrt Downloads (nju.edu.cn)](https://mirror.nju.edu.cn/immortalwrt/)

## 软件对照表

| 序号 | 包名称 | 中文解释 | 详细解释 |
|------|--------|----------|----------|
| 1 | csstidy | CSSTidy 优化器 | 命令行 CSS 压缩/清理工具，可减小网页样式表体积 |
| 2 | liblucihttp-lua | LuciHTTP-Lua 库 | LuCI 框架的 Lua 语言 HTTP 解析/生成库 |
| 3 | liblucihttp-ucode | LuciHTTP-ucode 库 | 同上，但面向 ucode 脚本环境 |
| 4 | liblucihttp0 | LuciHTTP 主库 | LuCI 的底层 C 语言 HTTP 库（运行时） |
| 5 | luci-app-3cat | 3CAT 应用界面 | 加泰罗尼亚电视台 3CAT 的 IPTV/流媒体配置前端 |
| 6 | luci-app-3ginfo-lite | 3G/LTE 信息轻量版 | 在 LuCI 中显示 3G/4G 模块信号强度、运营商等实时信息 |
| 7 | luci-app-acl | ACL 访问控制 | LuCI 页面级权限与访问控制列表管理 |
| 8 | luci-app-acme | ACME 自动证书 | 通过 ACME 协议（Let's Encrypt 等）自动申请/续期 HTTPS 证书 |
| 9 | luci-app-adblock-fast | AdBlock 快速版 | 轻量级广告屏蔽，支持快速规则更新 |
| 10 | luci-app-adblock | AdBlock 完整版 | 功能最全的广告/跟踪器屏蔽，支持 DNS/Hosts 多种方式 |
| 11 | luci-app-advanced-reboot | 高级重启 | 双分区路由器切换固件并重启的图形化向导 |
| 12 | luci-app-airplay2 | AirPlay 2 服务 | 把 OpenWrt 变成 AirPlay 2 音频接收端 |
| 13 | luci-app-airwhu | AirWHU 校园网助手 | 武汉高校校园网一键认证/登录界面 |
| 14 | luci-app-amule | aMule 电驴 | P2P 下载工具 aMule 的 Web 管理界面 |
| 15 | luci-app-antiblock | 防封锁代理 | 针对域名污染/封锁的智能代理切换 |
| 16 | luci-app-apinger | Apinger 监测 | 网关/链路延迟/丢包实时监测与告警 |
| 17 | luci-app-appfilter | 应用层过滤 | DPI 识别并阻断 QQ、BT、游戏等具体应用 |
| 18 | luci-app-argon-config | Argon 主题配置 | 为 Argon 主题提供颜色、背景、Logo 等自定义界面 |
| 19 | luci-app-aria2 | Aria2 下载器 | 轻量级多协议下载器 Aria2 的 Web 前端 |
| 20 | luci-app-arpbind | ARP 绑定 | 静态 ARP 绑定管理，防止 ARP 欺骗 |
| 21 | luci-app-attendedsysupgrade | 在线升级助手 | 一键在线升级固件并保留配置 |
| 22 | luci-app-autoreboot | 定时重启 | 按周期或特定时间自动重启路由器 |
| 23 | luci-app-babeld | Babel 路由 | 支持 Babel 无环距离向量路由协议的可视化配置 |
| 24 | luci-app-banip | IP 黑名单 | 基于 IPSet 的国家、恶意 IP 地址实时封禁 |
| 25 | luci-app-bcp38 | BCP38 防伪造 | 实施 BCP38 入口过滤，防止伪造源地址攻击 |
| 26 | luci-app-bitsrunlogin-go | 深澜认证助手 | 高校深澜计费系统一键登录（Go 版） |
| 27 | luci-app-bmx7 | BMX7 路由 | 无线社区网络 BMX7 协议的 Web 配置 |
| 28 | luci-app-cd8021x | 802.1X 校园网 | 针对高校 802.1X 认证客户端的 LuCI 配置界面 |
| 29 | luci-app-chrony | Chrony NTP | 精确时钟同步服务 Chrony 的 Web 管理 |
| 30 | luci-app-cifs-mount | CIFS/SMB 挂载 | 把 Windows/Samba 共享目录挂载到路由器 |
| 31 | luci-app-clamav | ClamAV 杀毒 | 邮件/文件病毒扫描器 ClamAV 的 Web 前端 |
| 32 | luci-app-cloudflared | Cloudflared 隧道 | 一键创建 Cloudflare Argo Tunnel 反向代理 |
| 33 | luci-app-commands | 自定义命令 | 在 LuCI 里添加/执行自定义 Shell 命令 |
| 34 | luci-app-coovachilli | CoovaChilli | 热点门户/计费系统 CoovaChilli 的 Web 配置 |
| 35 | luci-app-cpulimit | CPU 限速 | 限制某个进程最大 CPU 使用率 |
| 36 | luci-app-crowdsec-firewall-bouncer | CrowdSec 防火墙 | 基于 CrowdSec 威胁情报自动封锁恶意 IP |
| 37 | luci-app-cshark | CShark 抓包 | 在线网络数据包捕获与简易分析工具 |
| 38 | luci-app-dae | DAE 代理 | 新一代 DAE（Dynamic Any-socket Engine）透明代理配置界面 |
| 39 | luci-app-daed | Daed 代理 | DAE 的衍生版本 daed Web 前端 |
| 40 | luci-app-dawn | DAWN 无线优化 | 分布式 AP 信道/负载自动优化 |
| 41 | luci-app-dcwapd | DCWAPD 多拨 | 多条 WAN 带宽叠加/负载均衡 |
| 42 | luci-app-ddns-go | DDNS-Go | 轻量级动态域名客户端（Go 实现） |
| 43 | luci-app-ddns | 动态 DNS | 支持 20+ 服务商的 DDNS 客户端 |
| 44 | luci-app-diskman | 磁盘管理 | 查看/挂载/格式化/分区 硬盘 & U 盘 |
| 45 | luci-app-docker | Docker 引擎 | 在路由器上部署容器化应用（仅引擎） |
| 46 | luci-app-dockerman | Docker 管理 | Docker 容器/镜像/网络的 Web 管理面板 |
| 47 | luci-app-dufs | DUFS 文件服务 | 轻量级 HTTP/WebDAV 文件服务器配置 |
| 48 | luci-app-dump1090 | Dump1090 航班雷达 | 接收并显示 1090 MHz ADS-B 航班信息 |
| 49 | luci-app-dynapoint | DynaPoint 热点 | 动态热点门户，访客认证/计费 |
| 50 | luci-app-email | 邮件告警 | 系统事件通过 SMTP 发送邮件通知 |
| 51 | luci-app-eoip | EOIP 隧道 | 建立 MikroTik 兼容的 Ethernet-over-IP 二层隧道 |
| 52 | luci-app-eqos | 智能 QoS | 一键按设备/应用限速，保障游戏/视频体验 |
| 53 | luci-app-example | 示例应用 | LuCI 开发者示例插件，演示如何写前端 |
| 54 | luci-app-filebrowser-go | FileBrowser-Go | Go 写的网盘式文件管理器 |
| 55 | luci-app-filebrowser | FileBrowser 原版 | 简易 HTTP 文件浏览/上传/下载 |
| 56 | luci-app-filemanager | 文件管理器 | 集成版文件管理，支持压缩/解压/编辑 |
| 57 | luci-app-firewall | 防火墙 | OpenWrt 防火墙规则图形化管理 |
| 58 | luci-app-frpc | FRP 客户端 | 内网穿透 FRP Client 的 Web 配置 |
| 59 | luci-app-frps | FRP 服务端 | FRP Server 的 LuCI 管理界面 |
| 60 | luci-app-fwknopd | fwknop SPA | 单包授权 (SPA) 端口敲门安全网关 |
| 61 | luci-app-gost | GOST 代理 | 多功能隧道/代理 GOST 的 Web 前端 |
| 62 | luci-app-haproxy-tcp | HAProxy TCP | 高性能 TCP/HTTP 负载均衡器 HAProxy 配置 |
| 63 | luci-app-hd-idle | 硬盘休眠 | 空闲时自动停转外置硬盘节能 |
| 64 | luci-app-homeproxy | HomeProxy | 家庭网络透明代理/分流（Xray/V2Ray） |
| 65 | luci-app-https-dns-proxy | DoH 代理 | 通过 HTTPS 的 DNS（DoH）客户端 |
| 66 | luci-app-ipsec-vpnd | IPSec VPN 服务端 | 站点到站点/远程拨入 IPSec VPN |
| 67 | luci-app-irqbalance | IRQ 负载均衡 | 多核 CPU 网络中断自动分配 |
| 68 | luci-app-kcptun | Kcptun 加速 | KCP 隧道加速 TCP 的 Web 配置 |
| 69 | luci-app-keepalived | Keepalived | VRRP 高可用/负载均衡器配置 |
| 70 | luci-app-ksmbd | KSMBD 文件共享 | 轻量级 SMB3 文件服务器 |
| 71 | luci-app-ledtrig-rssi | RSSI LED 触发 | 用 LED 指示 Wi-Fi 信号强度 |
| 72 | luci-app-ledtrig-switch | 交换机 LED 触发 | 端口状态灯自定义 |
| 73 | luci-app-ledtrig-usbport | USB LED 触发 | USB 设备插拔灯控制 |
| 74 | luci-app-libreswan | Libreswan VPN | Libreswan IPSec VPN 管理 |
| 75 | luci-app-lldpd | LLDP 邻居发现 | 显示链路层邻居设备信息 |
| 76 | luci-app-lorawan-basicstation | LoRaWAN 基站 | Semtech Basic Station LoRa 网关配置 |
| 77 | luci-app-lxc | LXC 容器 | 轻量级 Linux 容器管理 |
| 78 | luci-app-mentohust | MentoHUST 认证 | 锐捷/深澜 802.1x 校园网认证客户端 |
| 79 | luci-app-microsocks | MicroSocks | 小巧 SOCKS5 服务器配置 |
| 80 | luci-app-minidlna | MiniDLNA 媒体 | DLNA/UPnP 媒体服务器 |
| 81 | luci-app-mjpg-streamer | MJPG-Streamer | 摄像头实时 MJPEG 视频流 |
| 82 | luci-app-modemband | 调制解调器锁频 | 手动锁定 4G/5G 频段提升稳定性 |
| 83 | luci-app-mosquitto | Mosquitto MQTT | MQTT 代理服务器配置 |
| 84 | luci-app-msd_lite | MSD Lite 多播 | 轻量级 IGMP/UDP 多播代理 |
| 85 | luci-app-music-remote-center | 音乐远控中心 | 网络音频播放器遥控界面 |
| 86 | luci-app-mwan3 | MWAN3 多拨 | 多 WAN 口负载均衡/策略路由 |
| 87 | luci-app-n2n | N2N VPN | 点对点/组播二层 VPN |
| 88 | luci-app-natmap | NATMap | 查看当前 NAT 会话与端口 |
| 89 | luci-app-netdata | Netdata 监控 | 实时性能/网络/应用监控图表 |
| 90 | luci-app-nextdns | NextDNS | 广告/跟踪防护 DNS 服务配置 |
| 91 | luci-app-nfs | NFS 共享 | 网络文件系统 (NFS) 服务器/客户端 |
| 92 | luci-app-nft-qos | nft QoS | 基于 nftables 的带宽/优先级控制 |
| 93 | luci-app-ngrokc | Ngrok 客户端 | 内网穿透 Ngrok 配置 |
| 94 | luci-app-njitclient | NJIT 客户端 | 南京理工校园网 802.1x 认证 |
| 95 | luci-app-nlbwmon | 网络带宽监控 | 按 IP/域名统计流量并图形化 |
| 96 | luci-app-nps | NPS 内网穿透 | NPS 客户端/服务端 Web 管理 |
| 97 | luci-app-nut | NUT UPS | UPS 不间断电源监控 |
| 98 | luci-app-ocserv | OpenConnect VPN | SSL VPN AnyConnect 兼容服务端 |
| 99 | luci-app-oled | OLED 状态屏 | 外接 I2C OLED 显示系统信息 |
| 100 | luci-app-olsr-services | OLSR 服务发现 | 在 OLSR 网络中广播/发现本地服务 |
| 101 | luci-app-olsr-viz | OLSR 拓扑可视化 | 用 D3.js 实时绘制 OLSR 网络拓扑图 |
| 102 | luci-app-olsr | OLSR 路由协议 | 无线社区网络 OLSR 配置与监控 |
| 103 | luci-app-omcproxy | OMCProxy 组播 | IGMP/MLD 代理，跨网段 IPTV 必备 |
| 104 | luci-app-openclash | OpenClash | 基于 Clash 的全局透明代理/规则分流 |
| 105 | luci-app-openlist | OpenList Web界面 | OpenList 是一个支持多种存储的文件列表程序 |
| 106 | luci-app-openvpn-server | OpenVPN 服务端 | 一键部署 OpenVPN 服务器 |
| 107 | luci-app-openvpn | OpenVPN 客户端 | OpenVPN 隧道/策略路由配置 |
| 108 | luci-app-openwisp | OpenWISP | 远程集中管理路由器（OpenWISP Agent） |
| 109 | luci-app-oscam | OSCam 服务器 | 软解电视卡共享服务器 |
| 110 | luci-app-p910nd | p910nd 打印 | 把 USB 打印机变成网络打印机 |
| 111 | luci-app-package-manager | 软件包管理器 | 图形化 OPKG 安装/升级/卸载 |
| 112 | luci-app-pagekitec | PageKitec | PageKite 反向 HTTP 隧道客户端 |
| 113 | luci-app-passwall | PassWall | 基于 Xray/Trojan/SSR 的可视化代理分流 |
| 114 | luci-app-pbr | 策略路由 PBR | Policy-Based Routing，按域名/IP/端口分流 |
| 115 | luci-app-pppoe-relay | PPPoE 中继 | 在局域网内中继远端 PPPoE 服务器 |
| 116 | luci-app-pppoe-server | PPPoE 服务器 | 自建拨号认证服务器，支持 Radius |
| 117 | luci-app-privoxy | Privoxy 代理 | HTTP/HTTPS 广告过滤代理服务 |
| 118 | luci-app-ps3netsrv | PS3 网服 | 给 PS3 提供无线 ISO 游戏网络共享 |
| 119 | luci-app-qbittorrent | qBittorrent | WebUI 版 qBittorrent 下载器 |
| 120 | luci-app-qos | 传统 QoS | 基于 tc 的带宽/优先级管理 |
| 121 | luci-app-radicale2 | Radicale2 日历 | CalDAV/CardDAV 通讯录/日历服务器 |
| 122 | luci-app-radicale | Radicale 日历 | 旧版本 Radicale 前端 |
| 123 | luci-app-ramfree | 内存释放 | 一键清理缓存/释放内存 |
| 124 | luci-app-rclone | Rclone 云盘 | 把路由器变成云盘同步器 |
| 125 | luci-app-rp-pppoe-server | RP-PPPoE 服务端 | 轻量级 PPPoE 服务器（Roaring Penguin 版） |
| 126 | luci-app-rustdesk-server | RustDesk 服务器 | 自建 RustDesk 远程桌面中继/ID 服务器 |
| 127 | luci-app-samba4 | Samba4 文件共享 | SMB/CIFS 3.x 文件/打印服务器 |
| 128 | luci-app-scutclient | SCUT 客户端 | 华南理工校园网 802.1x 认证 |
| 129 | luci-app-ser2net | Ser2net 串口 | 把串口转成 TCP Socket 服务器 |
| 130 | luci-app-siitwizard | SIIT 向导 | IPv4/IPv6 无状态转换快速配置 |
| 131 | luci-app-smartdns | SmartDNS | 智能 DNS 解析加速/分流 |
| 132 | luci-app-sms-tool-js | SMS 工具箱 JS | 收发短信/ USSD / AT 指令调试界面 |
| 133 | luci-app-snmpd | SNMP 守护 | SNMP v1/v2c/v3 网络管理 |
| 134 | luci-app-softether | SoftEther VPN | 多协议 VPN（SSL-VPN/L2TP/OpenVPN） |
| 135 | luci-app-softethervpn | SoftEther VPN 前端 | 图形化 SoftEther VPN Server |
| 136 | luci-app-speederv2 | SpeederV2 | KCP/UDP 加速隧道 |
| 137 | luci-app-splash | 热点门户 | 访客 Wi-Fi 认证/广告页面 |
| 138 | luci-app-spotifyd | Spotifyd 播放器 | 路由器变身 Spotify Connect 播放器 |
| 139 | luci-app-sqm | SQM 队列管理 | 智能队列 Cake/FQ-CoDel 降低延迟 |
| 140 | luci-app-squid | Squid 代理 | Web 缓存/访问控制代理 |
| 141 | luci-app-sshtunnel | SSH 隧道 | 一键建立 SSH 本地/远程端口转发 |
| 142 | luci-app-statistics | 系统统计 | 长期 CPU/内存/带宽/温度图表 |
| 143 | luci-app-strongswan-swanctl | StrongSwan IKEv2 | IPSec IKEv2 VPN 服务端/客户端 |
| 144 | luci-app-syncdial | 同步拨号 | 多条 PPPoE 同时拨号叠加带宽 |
| 145 | luci-app-syncthing | Syncthing | 点对点文件同步 |
| 146 | luci-app-sysuh3c | SYSU H3C 认证 | 中山大学 H3C 校园网一键登录 |
| 147 | luci-app-timewol | 定时唤醒 | 基于时间/日历的网络唤醒（WoL） |
| 148 | luci-app-tinyproxy | TinyProxy | 轻量 HTTP/HTTPS 代理 |
| 149 | luci-app-tor | Tor 透明代理 | 把流量匿名路由到 Tor 网络 |
| 150 | luci-app-transmission | Transmission | BT/PT 下载器 Web 前端 |
| 151 | luci-app-travelmate | TravelMate 旅行伴侣 | 自动连接/切换公共 Wi-Fi 并维护 VPN 安全隧道 |
| 152 | luci-app-ttyd | TTYD Web 终端 | 在浏览器里使用路由器 Shell |
| 153 | luci-app-ua2f | UA2F 用户代理转换 | 透明修改 HTTP User-Agent 以绕过运营商/校园网检测 |
| 154 | luci-app-udp2raw | UDP2Raw 隧道 | 把 UDP 伪装成 TCP 流量，突破 QoS/防火墙 |
| 155 | luci-app-udpxy | UDPXY 组播转 HTTP | 把 IPTV 组播流转成 HTTP 单播，跨网段播放 |
| 156 | luci-app-uhttpd | uHTTPd 管理 | LuCI 自带 Web 服务器高级配置 |
| 157 | luci-app-unblockneteasemusic | 解锁网易云音乐 | 解锁灰色版权歌曲，支持 VIP/高音质 |
| 158 | luci-app-unbound | Unbound DNS | 递归 DNS 缓存/验证/DoT/DoH |
| 159 | luci-app-upnp | MiniUPnP | UPnP/NAT-PMP 自动端口映射 |
| 160 | luci-app-usb-printer | USB 打印机共享 | 把 USB 打印机变成网络打印机（p910nd 前端） |
| 161 | luci-app-usteer | uSteer 智能漫游 | 802.11k/v/r 漫游决策守护进程前端 |
| 162 | luci-app-v2raya | V2RayA | 一键 V2Ray/Xray 可视化代理与规则管理 |
| 163 | luci-app-vlmcsd | KMS 服务器 | 自建 KMS 激活 Windows/Office |
| 164 | luci-app-vnstat2 | VnStat2 流量图 | 长期按接口统计流量并绘图 |
| 165 | luci-app-vsftpd | vsftpd 服务器 | FTP/SFTP/FTPS 文件服务器配置 |
| 166 | luci-app-watchcat | WatchCat 看门狗 | 断网/宕机自动重启或执行脚本 |
| 167 | luci-app-wechatpush | 微信推送 | 路由器事件实时推送到微信/企业微信/钉钉 |
| 168 | luci-app-wifischedule | Wi-Fi 定时开关 | 按日历/时段自动开关无线 |
| 169 | luci-app-wol | 网络唤醒 | 局域网/广域网一键 WoL 唤醒设备 |
| 170 | luci-app-xfrpc | Xfrp 客户端 | 轻量级 FRP 替代，支持 TCP/UDP/HTTP |
| 171 | luci-app-xinetd | xinetd 超级守护 | 按需启动 Telnet/FTP/SWAT 等服务 |
| 172 | luci-app-xlnetacc | 迅雷快鸟提速 | 电信迅雷快鸟宽带提速客户端 |
| 173 | luci-app-zerotier | ZeroTier | 全球虚拟局域网 SD-WAN 配置 |
| 174 | luci-base | LuCI 基础框架 | LuCI Web 界面核心库与 MVC 框架 |
| 175 | luci-compat | LuCI 兼容层 | 旧版 LuCI 应用兼容支持 |
| 176 | luci-lib-base | LuCI 基础库 | LuCI 框架的核心 Lua 工具库，所有 LuCI 模块依赖 |
| 177 | luci-lib-chartjs | Chart.js 图表库 | 封装 Chart.js，用于在 LuCI 页面绘制流量/统计图表 |
| 178 | luci-lib-docker | Docker Lua 库 | 提供 Lua 接口，供 LuCI 与 Docker Engine 交互 |
| 179 | luci-lib-httpclient | HTTP 客户端库 | Lua 级 HTTP/HTTPS 客户端，供 LuCI 调用外部 API |
| 180 | luci-lib-httpprotoutils | HTTP 协议工具 | HTTP 协议解析与 URL/Header 处理辅助函数 |
| 181 | luci-lib-ip | IP 地址库 | Lua 封装 iproute2，解析与操作 IPv4/IPv6 地址、路由、邻居 |
| 182 | luci-lib-ipkg | OPKG 库 | 封装 opkg 命令，用于 LuCI 内部查询/安装/卸载软件包 |
| 183 | luci-lib-iptparser | iptables 解析器 | 把 iptables-save 输出解析成 Lua 表，便于防火墙前端展示 |
| 184 | luci-lib-json | JSON 编解码 | 纯 Lua JSON 解析/生成，兼容老旧系统 |
| 185 | luci-lib-jsonc | JSON-C 绑定 | 基于 libjson-c 的高性能 JSON 解析/生成库 |
| 186 | luci-lib-nixio | Nixio I/O 库 | 跨平台 Socket/文件/进程/SSL 操作封装，LuCI 网络核心 |
| 187 | luci-lib-px5g | PX5G 工具库 | 调用 px5g 生成 RSA/ECC X.509 证书，用于 uHTTPd/Lighttpd |
| 188 | luci-lib-uqr | uQR 二维码库 | 纯 Lua 二维码生成器，用于在页面展示 Wi-Fi/URL 二维码 |
| 189 | luci-light | 轻量 LuCI | 最小化 LuCI 安装包，仅含核心框架与必要模块 |
| 190 | luci-lua-runtime | Lua 运行时 | 包含 Lua 解释器与 LuCI 所需的 Lua 模块 |
| 191 | luci-mod-admin-full | 全功能管理模块 | 传统"系统-管理-网络"完整菜单（旧管理界面） |
| 192 | luci-mod-battstatus | 电池状态模块 | 在 LuCI 页面显示 UPS/笔记本电池电量 |
| 193 | luci-mod-dashboard | 仪表盘模块 | 路由器概览首页：系统、网络、资源一览 |
| 194 | luci-mod-dsl | DSL 状态模块 | 展示 xDSL 线路速率、SNR、误码等详细信息 |
| 195 | luci-mod-network | 网络配置模块 | 网络接口、无线、DHCP、防火墙图形化配置 |
| 196 | luci-mod-rpc | RPC 接口模块 | 提供 JSON-RPC/UBUS API，供外部程序调用 LuCI 功能 |
| 197 | luci-mod-status | 状态模块 | 实时状态：路由表、连接、日志、负载、温度 |
| 198 | luci-mod-system | 系统模块 | 管理固件升级、软件包、启动项、计划任务、备份/恢复 |
| 199 | luci-nginx | Nginx LuCI 集成 | 用 Nginx 取代 uhttpd 作为 LuCI 的 Web 服务器 |
| 200 | luci-proto-3g | 3G/UMTS 协议支持 | 将 3G 调制解调器作为 WAN 接口的配置前端 |
| 201 | luci-proto-autoip | AutoIP 协议支持 | 169.254.x.x 自分配地址（Zeroconf）配置 |
| 202 | luci-proto-batman-adv | B.A.T.M.A.N. 协议 | 无线 Mesh 网络 batman-adv 接口配置 |
| 203 | luci-proto-external | 外部脚本协议 | 通过自定义脚本建立/拆除任意隧道接口 |
| 204 | luci-proto-gre | GRE 隧道协议 | IPv4/IPv6 GRE 隧道配置界面 |
| 205 | luci-proto-hnet | Homenet (HNET) 协议 | 家庭网络自组织路由（RFC 7788）配置 |
| 206 | luci-proto-ipip | IPIP 隧道 | IPv4 over IPv4 隧道（RFC 1853） |
| 207 | luci-proto-ipv6 | IPv6 通用协议 | RA、DHCPv6-PD、6in4、6to4、6rd 等配置 |
| 208 | luci-proto-mbim | MBIM 协议 | 4G/5G 模块 MBIM 拨号接口配置 |
| 209 | luci-proto-minieap | MiniEAP 协议 | 校园网/企业 802.1x EAP 认证客户端配置 |
| 210 | luci-proto-modemmanager | ModemManager 协议 | 使用 ModemManager 管理蜂窝调制解调器 |
| 211 | luci-proto-ncm | NCM 协议 | 基于 CDC-NCM 的 4G 网卡拨号配置 |
| 212 | luci-proto-nebula | Nebula 协议 | Slack 开源 Nebula 覆盖网络配置 |
| 213 | luci-proto-openconnect | OpenConnect VPN | Cisco AnyConnect 兼容 SSL VPN 配置 |
| 214 | luci-proto-openfortivpn | FortiVPN 协议 | Fortinet SSL-VPN 客户端配置 |
| 215 | luci-proto-ppp | PPP/PPPoE 协议 | 传统拨号、PPPoE、PPPoA 配置 |
| 216 | luci-proto-pppossh | PPP over SSH | 通过 SSH 隧道建立 PPP 链接 |
| 217 | luci-proto-qmi | QMI 协议 | 4G/5G 模块 QMI 拨号接口配置 |
| 218 | luci-proto-quectel | Quectel AT 协议 | Quectel 模块专有 AT 命令拨号配置 |
| 219 | luci-proto-relay | Relay 中继 | 伪网桥/relayd 透明二层中继配置 |
| 220 | luci-proto-sstp | SSTP 协议 | Microsoft SSTP VPN 客户端配置 |
| 221 | luci-proto-unet | UNet 协议 | 用于某些 USB-Ethernet 芯片的 UNET 拨号 |
| 222 | luci-proto-vpnc | Cisco VPNC | IPSec Cisco 兼容客户端（vpnc）配置 |
| 223 | luci-proto-vti | VTI 协议 | IPsec VTI 虚拟隧道接口配置 |
| 224 | luci-proto-vxlan | VXLAN 协议 | 以太网 over UDP 隧道（RFC 7348） |
| 225 | luci-proto-wireguard | WireGuard 协议 | 现代高性能 VPN 一键配置 |
| 226 | luci-proto-xfrm | XFRM 接口 | IPsec xfrm 状态/策略可视化 |
| 227 | luci-proto-yggdrasil | Yggdrasil | 去中心化 IPv6 Mesh 路由配置 |
| 228 | luci-ssl-openssl | OpenSSL SSL 支持 | 用 OpenSSL 为 LuCI 提供 HTTPS（与 uhttpd/openssl 组合） |
| 229 | luci-ssl | 通用 SSL 支持 | 元包，拉取默认 SSL 库（通常是 mbedtls） |
| 230 | luci-theme-argon | Argon 主题 | 现代扁平化主题，支持暗色/自定义壁纸 |
| 231 | luci-theme-bootstrap | Bootstrap 主题 | 基于 Bootstrap 3 的响应式官方主题 |
| 232 | luci-theme-material | Material 主题 | Google Material Design 风格主题 |
| 233 | luci-theme-openwrt-2020 | 2020 主题 | OpenWrt 官方新主题（浅色现代风） |
| 234 | luci-theme-openwrt | 经典主题 | 传统 OpenWrt 绿色经典界面 |
| 235 | luci | LuCI 元包 | 安装完整 LuCI Web 界面（含 uhttpd、luci-base、常用模块） |
| 236 | rpcd-mod-luci | RPCD LuCI 模块 | 为 rpcd 提供 LuCI 专用 API（权限、文件操作等） |
| 237 | rpcd-mod-rad2-enc | RPCD Radius 加密 | 支持 Radius 加密的 rpcd 插件（极少用） |
| 238 | rpcd-mod-rrdns | RPCD 反向 DNS | 提供 rrdns 反向查询接口，供状态页解析主机名 |
| 239 | ucode-mod-html | ucode HTML 模块 | ucode 脚本可直接生成 HTML，减少模板依赖 |
| 240 | ucode-mod-lua | ucode Lua 模块 | 让 ucode 脚本内嵌/调用 Lua 代码，提升扩展性 |

## 语言包

软件包名称如 `luci-i18n-xxx.ipk` 的都是对应软件的语言包，关键字如下：

| 序号 | 关键字 | 中文解释 |
|------|--------|----------|
| 1 | zh-cn | 中文语言包 |
| 2 | de | 德语包 |
| 3 | it | 意大利语包 |
| 4 | pl | 波兰语包 |
| 5 | ru | 俄语包 |
| 6 | cn | 中文包 |
| 7 | ar | 阿拉伯语包 |
| 8 | bg | 保加利亚语包 |
| 9 | bn | 孟加拉语包 |
| 10 | ca | 加泰罗尼亚语包 |
| 11 | cs | 捷克语包 |
| 12 | da | 丹麦语包 |
| 13 | el | 希腊语包 |
| 14 | es | 西班牙语包 |
| 15 | fa | 波斯语包 |
| 16 | fi | 芬兰语包 |
| 17 | fr | 法语包 |
| 18 | he | 希伯来语包 |
| 19 | hi | 印地语包 |
| 20 | hu | 匈牙利语包 |
| 21 | ja | 日语包 |
| 22 | ko | 韩语包 |
| 23 | lt | 立陶宛语包 |
| 24 | mr | 马拉地语包 |
| 25 | ms | 马来语包 |
| 26 | nl | 荷兰语包 |
| 27 | no | 挪威语包 |
| 28 | br | 巴西葡萄牙语包 |
| 29 | pt | 葡萄牙语包 |
| 30 | ro | 罗马尼亚语包 |
| 31 | sk | 斯洛伐克语包 |
| 32 | sv | 瑞典语包 |
| 33 | tr | 土耳其语包 |
| 34 | uk | 乌克兰语包 |
| 35 | vi | 越南语包 |
| 36 | yua | 尤卡坦玛雅语包 |
| 37 | zh-tw | 繁体中文包 |
| 38 | tw | 繁体中文包 |

---

> 作者：coocolight  
> 原文链接：https://alili.website/posts/2025/immortalwrtopenwrt%E8%BD%AF%E4%BB%B6%E5%8C%85%E4%B8%AD%E8%8B%B1%E6%96%87%E5%AF%B9%E7%85%A7%E8%A1%A8/  
> 许可：[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/deed.zh)
