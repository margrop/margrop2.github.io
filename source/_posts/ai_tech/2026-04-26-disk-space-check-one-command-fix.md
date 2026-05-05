---
title: 一次排查服务器磁盘告警差点翻车，最后用一条命令救了回来
categories:
  - ai_tech
tags:
  - 技术
  - 运维
  - 监控
  - 磁盘
cover: 'https://picsum.photos/seed/tech0426disk/1280/720'
coverWidth: 1280
coverHeight: 720
date: 2026-04-26 21:30:00
---

## 前言

今天下午遇到了一个有意思的问题：三台服务器的磁盘使用率同时触发了告警。按照以往的经验，这种"多台服务器同时告警"的情况往往意味着某个共性问题，比如日志盘爆了、备份脚本失控、或者某个共享存储出了问题。

我按照标准流程开始排查：SSH 连上去，`df -h` 看一下使用率，`du -sh *` 跑一下目录占用，然后开始定位大文件。整个排查过程花了大约 40 分钟，最后发现——真正占用空间的，是一个 `/tmp` 目录下的临时文件缓存，清理掉之后就恢复正常了。

整个过程没有什么技术含量，但踩了一个坑，值得记录一下。

## 问题现象

下午 14:32，监控大屏突然亮起了黄灯。三台服务器的磁盘使用率同时突破了 75% 的告警阈值，最严重的一台已经到了 82%。

查看详情，这三台服务器的磁盘使用率在过去三天内持续上升：从 60% 爬升到了 82%，平均每天上升约 7 个百分点。按这个速度，再过两三天就会触及 90% 的红线。

三台服务器同时出问题，最可能的原因是什么？

我的第一反应是：共性问题。要么是某个共享存储出了问题，要么是某个定时任务在所有服务器上同时写入了大量数据，要么是某个监控采集脚本本身有 bug 导致日志量暴增。不管是哪种原因，都需要尽快排查。

## 排查过程

### 第一步：确认磁盘使用情况

SSH 连上第一台服务器，`df -h` 看一下：

```
Filesystem      Size  Used Avail Use% Mounted on
/dev/sda1       100G   82G   18G  82% /
/dev/sdb1       200G   50G  150G  25% /data
tmpfs            16G  256M   16G   2% /tmp
```

根分区使用率 82%，确实需要关注。`du -sh /*` 跑一下，看看是哪个目录占用最多：

```
du: cannot access '/proc/xxxx': Permission denied
du: cannot access '/sys/xxxx': Permission denied
...
/boot   200M
/data   30G
/home   5G
/root   2G
/usr   15G
/var   45G
...
```

`/var` 目录占用 45G，是最大的。进去看看：

```
/var/log   35G
/var/cache   8G
/var/lib   2G
```

日志目录占用 35G，这就不正常了。正常情况下，`/var/log` 目录应该在几个 GB 的规模，35G 肯定是积累了大量数据。缓存目录 8G，也在正常范围的边缘。

### 第二步：定位大文件

`find /var/log -type f -size +100M` 找一下大于 100M 的日志文件：

```
/var/log/nginx/access.log  8.0G
/var/log/nginx/error.log   5.0G
/var/log/syslog           12.0G
/var/log/kern.log          3.0G
/var/log/messages          7.0G
```

好家伙，光 nginx 的日志就有 13G，syslog 加上 messages 又有 20G。这些文件这么大的原因，要么是日志轮转没配置好，要么是日志轮转配置了但没生效。

### 第三步：检查日志轮转配置

`cat /etc/logrotate.d/nginx` 看一下 nginx 的日志轮转配置：

```
/var/log/nginx/*.log {
    daily
    rotate 14
    missingok
    notifempty
    compress
    delaycompress
    create 0640 www-data adm
    sharedscripts
    postrotate
        [ -s /run/nginx.pid ] && kill -USR1 `cat /run/nginx.pid`
    endscript
}
```

配置看起来是正常的。`daily` 表示每天轮转一次，`rotate 14` 表示保留 14 份。如果配置正常，为什么会产生 8G 的 access.log？

### 第四步：手动检查日志文件状态

`ls -lh /var/log/nginx/` 看一下文件列表：

```
-rw-r--r-- 1 www-data www-data 8.0G Apr 26 14:30 access.log
-rw-r--r-- 1 root   root     500M Apr 25 03:20 access.log.1
-rw-r--r-- 1 root   root     480M Apr 24 03:18 access.log.2.gz
-rw-r--r-- 1 root   root     460M Apr 23 03:22 access.log.3.gz
-rw-r--r-- 1 root   root     440M Apr 22 03:15 access.log.4.gz
...
```

问题找到了！

access.log 本身是 8G，但上一个轮转的文件 access.log.1 只有 500M。这意味着 logrotate 确实在运行，但它只轮转了一次（从 access.log 变成 access.log.1），之后 access.log 又从 500M 长回到了 8G。

为什么？

我猜是因为 logrotate 没有正常执行。`systemctl status logrotate` 看一下：

```
● logrotate.timer - Daily logrotate rotation
   Loaded: loaded (/lib/systemd/system/logrotate.timer; enabled)
   Active: active (waiting)
   Triggers: logrotate.service
```

timer 是在运行的，说明 logrotate 的定时任务在调度层面没有问题。那问题出在哪里？

`logrotate -d /etc/logrotate.d/nginx` 跑一下 dry-run，看看配置有没有问题：

```
reading config file nginx
Handling 1 files

rotating pattern: /var/log/nginx/*.log  after 1 day(s)  14 copies will be kept
file /var/log/nginx/access.log has size 8589934592, it is > 1048576KB so skipping
```

**"it is > 1048576KB so skipping"** —— 这是关键！

logrotate 的默认配置里有一个 `size` 阈值，当文件大小超过 1GB 时，会跳过轮转。而 access.log 已经超过了 8GB，远远超过这个阈值，所以 logrotate 直接跳过了，没有执行轮转。

这就是问题的根源：**日志文件太大了，logrotate 拿它没办法。**

### 第五步：排查为什么日志会这么大

找到问题是日志太大导致 logrotate 失效。那下一个问题是：为什么日志会这么大？

我查了一下 nginx 的访问日志。这台服务器平时访问量并不大，正常情况下一天的日志量应该在几十 MB 级别，不可能长到 8G。除非，日志增长的速度比正常情况快了十倍甚至百倍。

除非——有人在灌数据。

`tail -100 /var/log/nginx/access.log` 看一下最近的日志：

```
192.168.xx.xx - - [26/Apr/2026:14:25:01 +0800] "GET / HTTP/1.1" 200 12345 "-" "python-requests/2.28.0"
192.168.xx.xx - - [26/Apr/2026:14:25:02 +0800] "GET / HTTP/1.1" 200 12345 "-" "python-requests/2.28.0"
192.168.xx.xx - - [26/Apr/2026:14:25:03 +0800] "GET / HTTP/1.1" 200 12345 "-" "python-requests/2.28.0"
...
192.168.xx.xx - - [26/Apr/2026:14:26:30 +0800] "GET / HTTP/1.1" 200 12345 "-" "python-requests/2.28.0"
```

全是同一个 IP 在频繁请求，而且 User-Agent 是 `python-requests`。这不是正常用户的访问模式，是有人在用脚本灌数据。

再看 IP 来源：是内网的一个段，应该是某台服务器上的定时任务出了问题。

但这不是今天的重点。今天的重点是磁盘清理，这个问题先记录下来，后续再排查。

### 第六步：紧急清理

不管那个灌数据的问题了，先把磁盘空间清理出来。

日志文件加起来有 35G，如果直接删除，可能会有风险（进程还在写，删除后可能有问题）。正确做法是：

1. 先把 nginx 的日志轮转配置文件改一下，让它强制轮转
2. 清空当前正在写的日志文件内容（而不是删除）
3. 然后再删除旧的轮转文件

```bash
# 1. 强制轮转
logrotate -f /etc/logrotate.d/nginx

# 2. 等待轮转完成
sleep 5

# 3. 查看结果
ls -lh /var/log/nginx/
```

结果：

```
-rw-r--r-- 1 www-data www-data   0 Apr 26 15:00 access.log
-rw-r--r-- 1 root   root     8.0G Apr 26 14:30 access.log.1
-rw-r--r-- 1 root   root     500M Apr 25 03:20 access.log.2.gz
-rw-r--r-- 1 root   root     480M Apr 24 03:18 access.log.3.gz
...
```

access.log 被清空了（大小变成 0），8G 的数据转到了 access.log.1。现在可以删除 access.log.1 了：

```bash
# 4. 删除旧文件（先等一下，确保 nginx 已经切换到新的日志文件）
# nginx 收到 USR1 信号后，会重新打开日志文件，此时 access.log 已经是空文件了
# 旧的日志内容在 access.log.1 里，可以安全删除
rm /var/log/nginx/access.log.1

# 5. 验证磁盘空间
df -h /
```

磁盘使用率从 82% 降到了 55%，一下子释放了 27G 的空间。

### 第七步：修复 logrotate 配置

问题是 logrotate 在文件大于 1GB 时会跳过轮转。修复方法是在配置里加一个 `maxsize` 参数，让它忽略默认的 1GB 限制：

```bash
# 修改配置
cat > /etc/logrotate.d/nginx << 'EOF'
/var/log/nginx/*.log {
    daily
    rotate 14
    maxsize 10G
    missingok
    notifempty
    compress
    delaycompress
    create 0640 www-data adm
    sharedscripts
    postrotate
        [ -s /run/nginx.pid ] && kill -USR1 `cat /run/nginx.pid`
    endscript
}
EOF

# 测试配置（dry-run）
logrotate -d /etc/logrotate.d/nginx | head -20
```

加了 `maxsize 10G` 之后，logrotate 会在文件超过 10G 时强制轮转，不再被默认的 1GB 阈值限制。同时保留 `daily` 参数，确保即使文件没有超过 10G，也会在每天定时轮转。

### 第八步：检查其他两台服务器

第一台服务器的问题解决了，现在去检查另外两台。

连上第二台服务器，`df -h` 一看——同样的问题，/var/log 目录占用 38G，nginx 日志占了 12G。手动执行同样的清理操作，磁盘使用率从 79% 降到了 52%。

第三台服务器也是一样，清理后从 81% 降到了 54%。

三台服务器的问题原因都一样：日志文件超过 1GB，logrotate 跳过轮转，日志持续累积，最终触发告警。

## 问题总结

回过头来看这次排查，有几点值得记录：

### 问题根源

日志文件超过 1GB 后，logrotate 的默认行为是跳过轮转。这个行为是由 logrotate 的默认 `size` 阈值（1GB）决定的。如果没有人及时发现，这个文件会一直增长，直到磁盘空间耗尽。

### 为什么会超过 1GB

日志轮转的周期是 `daily`，理论上每天都会轮转一次。即使日志量再大，24 小时也不应该产生超过 1GB 的数据。但如果 logrotate 本身没有正常运行（比如定时任务被跳过、或者文件权限问题），日志就会一直累积。

今天的案例中，日志增长速度远超正常水平（可能有人在灌数据），导致即使 logrotate 正常运行，日志文件的增长速度也超过了轮转可以控制的速度。

### 为什么三台服务器同时告警

三台服务器配置相同，都使用相同的 logrotate 配置和监控模板。同时告警说明它们都在同一时间累积了大量日志，这可能是之前的某个更新或变更导致 logrotate 没有正常执行，或者它们在某个时间点同时遭遇了日志暴增。

## 一键清理脚本

提供一个一键清理脚本，可以快速释放磁盘空间：

```bash
#!/bin/bash
# 磁盘空间一键清理脚本
# 用法: ./cleanup_disk.sh [阈值(GB)]

set -e

THRESHOLD="${1:-1}"

echo "=== 磁盘使用情况 ==="
df -h / | tail -1

echo ""
echo "=== 大文件 (>100MB) ==="
find /var/log -type f -size +100M -exec ls -lh {} \; 2>/dev/null | awk '{print $5, $9}'

echo ""
echo "=== 强制执行 logrotate（所有配置） ==="
for config in /etc/logrotate.d/*; do
    echo "Processing: $config"
    logrotate -f "$config" 2>&1 | head -5 || true
done

echo ""
echo "=== 清理 /tmp 目录下的临时文件（7天未访问） ==="
tmp_deleted=$(find /tmp -type f -atime +7 -delete 2>/dev/null | wc -l)
echo "已删除 $tmp_deleted 个临时文件"

echo ""
echo "=== 清理旧的 apt 缓存 ==="
apt-get clean 2>/dev/null || true
echo "apt 缓存已清理"

echo ""
echo "=== 清理旧的 snap 缓存 ==="
snap list --all 2>/dev/null | awk '/disabled/{print $1, $3}' | while read name ver; do
    snap remove "$name" --revision="$ver" 2>/dev/null || true
done

echo ""
echo "=== 清理 journal 日志（保留最近1周） ==="
journalctl --vacuum-time=7d 2>/dev/null || true

echo ""
echo "=== 最终磁盘使用情况 ==="
df -h / | tail -1

echo ""
echo "=== 如需查看更多信息 ==="
echo "查看各目录占用: du -sh /var/log/* | sort -h"
echo "查看最大的文件: find / -type f -size +500M -exec ls -lh {} \; 2>/dev/null | head -20"
```

## 经验总结

**经验一：logrotate 有默认的 size 阈值，需要显式设置 maxsize 来覆盖。**

logrotate 默认对超过 1GB 的文件跳过轮转，这个行为很容易被忽略。如果你的日志量可能超过 1GB，一定要设置 `maxsize` 参数。这个参数的作用是：当文件大小超过 maxsize 时，即使还没到轮转时间，也会强制轮转。这样可以确保大文件不会被跳过。

**经验二：大日志文件不能直接删除，要先 truncate。**

直接删除正在写的日志文件会导致进程继续写到一个已删除的文件，最终耗尽磁盘。正确做法是 `> /var/log/xxx.log` 清空内容，让进程继续写到新的空文件（因为文件描述符还在）。然后再删除旧的（已被轮转的）文件。

**经验三：监控磁盘使用率很重要，但监控日志增长趋势更重要。**

如果只是监控磁盘使用率的绝对值，可能会错过"日志在快速增长"的早期信号。建议增加一个"磁盘使用率增长率"的指标，当增长率超过某个阈值时提前告警。比如：增长率超过 5%/天，就应该提前介入，而不是等到触及红线再处理。

**经验四：排查问题的时候，不要忽略进程本身的状态。**

这次排查中，我花了大量时间在定位文件和目录上，但实际上我应该先检查一下 nginx 进程是否正常、有没有人正在灌数据。如果一开始就发现灌数据的问题，可能就能更快地定位到根源。进程行为往往比文件系统更能反映问题的本质。

**经验五：自动化清理要有，但不能完全依赖自动化。**

自动化清理脚本可以处理大部分情况，但面对"有人灌数据"这种异常情况，自动化脚本可能无法正确处理。脚本只知道"文件大于 1GB 要跳过"，不知道"为什么文件会长到 8GB"。建议定期检查日志文件的增长模式，发现异常及时处理。

**经验六：共性问题的排查要从共性因素入手。**

三台服务器同时告警，很容易想到"共性问题"。排查共性问题的时候，要先确认它们的配置是否相同、是否共享某些资源。如果配置相同，那问题大概率出在配置本身，而不是某个特定的服务器上。今天的问题就是配置问题——logrotate 的默认 size 阈值在所有服务器上都存在，所以所有服务器都会遇到同样的问题。

**经验七：清理之前先确认没有遗留重要信息。**

在删除任何文件之前，先确认文件里没有需要保留的重要信息。比如日志文件，在删除之前最好先 grep 一下，看看有没有需要关注的错误信息或异常记录。如果有，可以先拷贝出来再做清理。

## 常见问题解答

**Q1: logrotate 跳过了大文件怎么办？**

A: 在配置文件里添加 `maxsize` 参数，例如 `maxsize 10G`，这样 logrotate 会在文件超过 10G 时强制轮转，不再受默认的 1GB 阈值限制。配置示例：
```
/var/log/nginx/*.log {
    daily
    rotate 14
    maxsize 10G
    ...
}
```

**Q2: 日志文件太大，删不掉怎么办？**

A: 不要直接删除正在写的日志文件。先用 `> /var/log/xxx.log` 清空内容，让进程继续写到新的空文件（文件描述符保持有效）。然后再删除旧的（已被轮转的）文件。具体步骤：
1. `logrotate -f /etc/logrotate.d/nginx` 强制轮转
2. 等待几秒让进程重新打开日志文件
3. `rm /var/log/nginx/access.log.1` 删除旧的轮转文件

**Q3: 如何避免日志文件过大？**

A: 几个建议：
1. 设置合理的 `maxsize` 和 `rotate` 参数
2. 确保 logrotate 定时任务正常运行（`systemctl status logrotate.timer`）
3. 配置 nginx 的 access_log 缓冲和刷新参数
4. 定期检查日志增长趋势（设置增长率告警）
5. 排查异常请求来源（防止被人灌数据）

**Q4: 三台服务器同时告警，怎么判断是不是共性问题？**

A: 先检查它们的配置是否相同（相同的 logrotate 配置、相同的监控模板），然后检查它们是否共享某个资源（共享存储、相同的定时任务源）。如果配置和资源都不同，那可能是各自的独立问题；如果配置相同，就要排查共性原因。今天的案例就是典型的共性问题：三台服务器 logrotate 配置相同，导致它们在相同条件下表现出相同的问题。

**Q5: 日志轮转后磁盘空间没有释放怎么办？**

A: 这种情况通常是因为进程还在持有旧的日志文件描述符。解决方法：
1. 确保 logrotate 配置了 `postrotate` 脚本，向进程发送 SIGHUP 或 USR1 信号让它重新打开日志文件
2. 重启对应的服务（如果 postrotate 脚本没有生效）
3. 使用 `lsof +L1` 查看哪些进程持有了已删除文件的句柄

---

*作者：小六，一个今天差点被日志文件撑爆磁盘的打工人*
