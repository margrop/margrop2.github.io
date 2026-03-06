---
title: 记一次VPS8无法访问的排查：Caddy配置缺失导致的域名解析问题
categories:
  - ai_tech
tags:
  - 技术
  - 运维
  - VPS
  - Caddy
  - 问题排查
cover: 'https://picsum.photos/seed/tech0303/1280/720'
coverWidth: 1280
coverHeight: 720
date: 2026-03-03 21:30:00
---

## 前言

在运维工作中经常会遇到这样的问题：服务器明明运行正常，服务也能访问，但通过域名访问就是不行。这种"玄学"问题排查起来往往让人抓狂——你知道服务器没问题，但就是找不到问题在哪。

本文将记录一次关于 VPS8 无法通过域名访问的完整排查过程，最终发现是 Caddy 配置文件中缺少域名配置导致的。希望能给遇到类似问题的同学一些参考。

## 问题背景

### 业务场景

我们有多台美国 VPS 用于代理和内网穿透服务。其中一台 VPS8（IP: 64.69.***.***）配置了 Caddy 作为反向代理和 HTTPS 终结器。

### 问题现象

- VPS8 可以通过 IP 地址直接访问
- 其他 VPS 可以通过代理访问外网（速度测试 1.47s，最快的一台）
- 但通过域名 ***.***.xyz 无法访问
- Caddy 服务正常运行，未报错

### 环境信息

- **服务器**：VPS8 (64.69.***.***)
- **操作系统**：Alpine 容器
- **内存**：256MB
- **Web 服务器**：Caddy 2.x
- **域名**：***.***.xyz

## 排查过程

### 第一步：确认服务器状态

首先确认 VPS8 本身是否正常工作：

```bash
# SSH 登录到 VPS8
ssh root@64.69.***.***

# 检查 Caddy 进程状态
ps aux | grep caddy

# 检查端口监听
netstat -tlnp | grep 80
# 或者
ss -tlnp | grep -E ':(80|443)'
```

结果：Caddy 进程正常运行，80 和 443 端口都在监听。

### 第二步：测试本地访问

在 VPS8 本地测试服务是否正常：

```bash
# 测试本地回环访问
curl -I http://localhost

# 或者
wget -O- http://localhost
```

结果：本地访问正常，服务本身没有问题。

### 第三步：测试 IP 直接访问

从本地电脑或其他服务器测试 IP 直接访问：

```bash
# 使用 IP 访问
curl -I http://64.69.***.***
```

结果：IP 直接访问正常。说明服务器和网络都没有问题。

### 第四步：检查域名解析

确认域名是否正确解析到服务器 IP：

```bash
# 使用 nslookup 检查域名解析
nslookup ***.***.xyz

# 或者使用 dig
dig ***.***.xyz

# 或者使用 ping
ping -c 3 ***.***.xyz
```

结果：域名正确解析到了 64.69.***.***。DNS 没有问题。

### 第五步：检查 Caddy 配置

这是关键的一步。检查 Caddy 的配置文件：

```bash
# 查看 Caddy 配置文件
cat /etc/caddy/Caddyfile

# 或者查看 sites-enabled 目录
ls -la /etc/caddy/sites-enabled/

# 查看 Caddy 日志
tail -f /var/log/caddy.log
```

结果：发现问题！

Caddy 配置文件中只有其他几个 VPS 的配置，唯独缺少 ***.***.xyz 的配置：

```
# 现有的配置大概是这样
***.***.xyz {
    reverse_proxy localhost:xxxx
}

***.***.xyz {
    reverse_proxy localhost:xxxx
}

# ... 其他 VPS

# 缺少 ***.***.xyz
```

这就解释了为什么域名无法访问——Caddy 根本不知道要把 ***.***.xyz 的请求代理到哪里去！

### 第六步：添加域名配置

找到问题后，解决方法就很简单了。在 Caddy 配置文件中添加 ***.***.xyz 的配置：

```bash
# 编辑 Caddyfile
vi /etc/caddy/Caddyfile

# 添加以下配置
***.***.xyz {
    reverse_proxy localhost:xxxx
    encode gzip
    log {
        output file /var/log/caddy/vps8.log
    }
}
```

### 第七步：重载 Caddy 配置

修改配置后，需要让 Caddy 重新加载配置：

```bash
# 检查配置语法
caddy validate --config /etc/caddy/Caddyfile

# 重载配置
caddy reload

# 或者重启服务
systemctl restart caddy
```

### 第八步：验证修复

配置重载后，测试域名是否可以访问：

```bash
# 测试 HTTPS 访问
curl -I https://***.***.xyz

# 测试 HTTP 访问（应该会自动重定向到 HTTPS）
curl -I http://***.***.xyz
```

结果：域名访问恢复正常！

## 根因分析

### 问题根因

这次问题的根本原因是：**Caddy 配置文件不完整**。

在配置多个域名时，可能因为以下原因导致遗漏：

1. **手动添加域名时漏掉**：配置 VPS1-VPS7 时都加了，但配置 VPS8 时漏掉了
2. **批量配置脚本不完整**：使用脚本批量生成配置时，VPS8 的配置没有被正确生成
3. **配置文件版本不同步**：多人维护时，有人添加了新域名但没有同步给其他人

### 预防措施

为了避免类似问题再次发生，建议：

1. **配置清单**：维护一份所有域名的配置清单，每次添加新域名时更新
2. **自动化配置**：使用 Ansible、Terraform 等工具自动化管理配置
3. **监控告警**：添加 HTTPS 证书过期监控和域名访问监控
4. **配置审计**：定期审计配置文件，确保所有域名都已配置

## 一键解决方案

如果你遇到了类似的"域名无法访问但IP可以"的问题，可以尝试以下排查步骤：

```bash
# 1. 确认域名解析正确
nslookup your-domain.com

# 2. 确认服务器可达
ping -c 3 your-domain.com

# 3. 确认 Web 服务运行
curl -I http://localhost

# 4. 确认 Web 服务监听端口
netstat -tlnp | grep -E ':(80|443)'

# 5. 检查 Web 服务器配置
# Nginx
cat /etc/nginx/sites-enabled/*
# Apache
cat /etc/apache2/sites-enabled/*
# Caddy
cat /etc/caddy/Caddyfile

# 6. 检查防火墙
iptables -L -n
ufw status

# 7. 检查 SSL 证书
curl -I https://your-domain.com -v
```

## 常见问题解答

**Q：域名解析正确但无法访问怎么办？**

A：首先确认服务器端的 Web 服务是否正常运行，然后检查防火墙是否阻止了 80/443 端口，最后检查 Web 服务器配置是否包含该域名。

**Q：Caddy 配置修改后需要重启吗？**

A：Caddy 支持热重载，使用 `caddy reload` 即可。但如果是配置语法错误，需要先修复再重载。

**Q：如何批量管理多个域名的 Caddy 配置？**

A：可以使用 Caddy 的 import 功能，将公共配置抽离，然后用 import 引入。也可以使用 JSON 格式的配置进行编程式管理。

**Q：配置正确但还是无法访问怎么办？**

A：检查是否有多个 Web 服务同时监听 80/443 端口（端口冲突），检查本地 DNS 缓存（使用 `ipconfig /flushdns` 或 `systemd-resolve --flush-caches`），检查是否被 CDN 或防火墙拦截。

**Q：如何避免配置遗漏？**

A：建议使用配置管理工具（如 Ansible）进行标准化管理，或者编写脚本自动生成配置并进行校验。

## 总结

这次问题的排查过程虽然不复杂，但很有代表性：

1. **先确认基本功能正常**（IP 能访问）
2. **再检查网络层**（DNS 解析）
3. **最后检查应用层**（Web 服务器配置）

很多时候，看似"玄学"的问题，实际上都是配置遗漏或者不同步导致的。建议建立配置管理流程，避免手动维护配置文件。

希望这篇文章能帮到你。如果有问题，欢迎在评论区讨论。

---

*作者：小六，一个在上海努力搬砖的程序员*
