---
title: ImmortalWRT软件源分享
categories:
  - ai_tech
tags:
  - OpenWrt
  - 旁路由
  - 路由器
date: '2026-05-09 16:00:00'
---
原文地址：[https://deeprouter.org/article/immoralwrt-opkg-replace-edu-mirror](https://deeprouter.org/article/immoralwrt-opkg-replace-edu-mirror)

> 作者：Deep Router
> 分类：资源分享
> 更新日期：2025-03-03

---

ImmortalWrt 是 OpenWrt 的一个第三方分支，主要针对国内用户开发，在不对系统进行过度修改的情况下，不仅继承了 OpenWRT 的灵活性和强大功能，还提供更多的本地化软件包和设备支持，对 [IPv6](https://www.dolingou.com/article/bypass-the-routing-proxy-to-proxy-IPV6-with-clash) 的支持也很稳定，应该是国内目前最为纯净的 OpenWRT 系统。ImmortalWrt 也是支持使用 Dae 的 OpenWRT 分支。

本文章适用于 [ImmortalWRT](https://github.com/immortalwrt/immortalwrt) 用户，与 OpenWRT 官方源仓库不一定兼容，如需使用 OpenWRT 官方源仓库，可参考：[🖥️OpenWRT 软件源整理](https://deeprouter.org/article/Compilation-of-OpenWRT-Software-Sources)

<!-- more -->

## ImmortalWRT软件源

### ImmortalWRT软件仓库地址

ImmortalWRT 在国内有镜像加速，目前 ImmortalWRT 路由系统在安装完成之后默认使用的 OPKG 软件仓库为下面这个：

```
https://mirrors.vsean.net/openwrt/releases/
```

软件仓库提供版本及架构选择，请根据自身设备所使用的 OpenWRT 版本及系统架构进行选择。

### Opkg配置ImmortalWRT软件源

以下内容以 **ImmortalWRT-23.05.3，X86-64架构** 的软件源为例，其他版本及架构可通过仓库选择之后复制地址替换到下面的代码中。

#### 命令行方式

1. 编辑 `/etc/opkg/customfeeds.conf`

```shell
vim /etc/opkg/customfeeds.conf
```

2. 复制以下软件源配置信息至文件中并进行保存

```plain
src/gz immortalwrt_core https://mirrors.vsean.net/openwrt/releases/23.05.3/targets/x86/64/packages
src/gz immortalwrt_base https://mirrors.vsean.net/openwrt/releases/23.05.3/packages/x86_64/base
src/gz immortalwrt_luci https://mirrors.vsean.net/openwrt/releases/23.05.3/packages/x86_64/luci
src/gz immortalwrt_packages https://mirrors.vsean.net/openwrt/releases/23.05.3/packages/x86_64/packages
src/gz immortalwrt_routing https://mirrors.vsean.net/openwrt/releases/23.05.3/packages/x86_64/routing
src/gz immortalwrt_telephony https://mirrors.vsean.net/openwrt/releases/23.05.3/packages/x86_64/telephony
```

3. 更新软件源

```shell
opkg update
```

#### Luci界面操作方式

1. 登入 OpenWRT 管理页面
2. 打开 `系统 - 软件包`，点击 `配置 opkg`
3. 在 `/etc/opkg/customfeeds.conf` 粘贴以下内容并保存

```plain
src/gz immortalwrt_core https://mirrors.vsean.net/openwrt/releases/23.05.3/targets/x86/64/packages
src/gz immortalwrt_base https://mirrors.vsean.net/openwrt/releases/23.05.3/packages/x86_64/base
src/gz immortalwrt_luci https://mirrors.vsean.net/openwrt/releases/23.05.3/packages/x86_64/luci
src/gz immortalwrt_packages https://mirrors.vsean.net/openwrt/releases/23.05.3/packages/x86_64/packages
src/gz immortalwrt_routing https://mirrors.vsean.net/openwrt/releases/23.05.3/packages/x86_64/routing
src/gz immortalwrt_telephony https://mirrors.vsean.net/openwrt/releases/23.05.3/packages/x86_64/telephony
```

4. 点击 `更新列表` 进行软件源更新

### 镜像地址

如果默认的镜像地址在你的网络下速度并不理想，可以替换使用其他镜像地址：

#### CERNET（校园网联合镜像站）

```plain
https://mirrors.cernet.edu.cn/immortalwrt
```

#### 南开大学开源镜像站

```plain
https://mirror.nju.edu.cn/immortalwrt
```

#### 北京大学开源镜像站

```plain
https://mirrors.pku.edu.cn/immortalwrt
```

#### 上海科技大学 Geek Pie 开源镜像站

```plain
https://mirrors.ustc.edu.cn/immortalwrt
```

#### 中国科学技术大学开源镜像站

```plain
https://mirrors.ustc.edu.cn/immortalwrt
```

#### 上海交通大学开源镜像站

```shell
https://mirror.sjtu.edu.cn/immortalwrt
```

#### 南京大学开源镜像站

```plain
https://mirror.nju.edu.cn/immortalwrt
```

#### Cloudflare 镜像站

```shell
https://immortalwrt.kyarucloud.moe/
```

### 替换方法

修改 `/etc/opkg/customfeeds.conf` 文件，将源地址 `https://downloads.immortalwrt.org` 或 `https://mirrors.vsean.net/openwrt` 更改上面的镜像站地址。

或者通过命令行方式进行修改，格式为 `s,[原来的软件源地址],[替换的软件源地址],g`

```shell
sed -e 's,https://downloads.immortalwrt.org,https://mirrors.jlu.edu.cn/immortalwrt,g' \
-e 's,https://mirrors.vsean.net/openwrt,https://mirrors.jlu.edu.cn/immortalwrt,g' \
-i.bak /etc/opkg/customfeeds.conf
```

替换完成后通过 `opkg update` 进行更新。

### ImmortalWRT固件下载

推荐使用官方提供的 Firmware 固件下载服务。如具备动手能力可自行编译固件。

**ImmortalWrt Firmware Selector**: https://firmware-selector.immortalwrt.org/

---

## 📎 参考文章

- [ImmortalWrt 软件仓库镜像使用帮助](https://help.mirrors.cernet.edu.cn/immortalwrt/)