---
title: 使用 OpenResty + 签名 Cookie 实现"登录一次，1 小时免重复认证"的反代安全网关
categories:
  - ai_tech
tags:
  - OpenResty
  - 反向代理
  - 安全
  - Nginx
  - Cookie 认证
date: 2026-02-28 18:30:00
---

> 背景：某些 Web 面板/管理后台近期安全风险频出，公网暴露端口容易被扫描与爆破。本文记录一种轻量加固方案：**不改原应用容器**，仅用 OpenResty 做反向代理与认证网关，实现**首次 BasicAuth、之后 1 小时免验证**。

## 1. 目标与约束

### 目标

- 原应用端口不直接暴露公网
- 增加认证拦截
- 登录一次后，**最近 1 小时同客户端无需再次认证**
- 网关可控过期时间（严格 3600 秒）
- 支持 WebSocket
- 容器重启不影响（无状态认证）

### 约束

- 不修改原应用容器
- 尽量不引入额外依赖（Redis/DB/认证中心）

## 2. 架构概览

```
公网: 外网端口
↓
OpenResty（反代网关）
├── /__login：BasicAuth（只在这里弹一次）
├── Cookie 校验：签名 + 过期校验（1 小时）
└── 反代到内部应用
↓
内部应用：仅监听 127.0.0.1:内部端口
```

## 3. 完整 docker-compose.yml

```yaml
services:
  app:
    image: your-app-image:tag
    container_name: app
    hostname: app
    restart: always
    environment:
      APP_ENV_1: "..."
      APP_ENV_2: "..."
    volumes:
      - /path/to/app/data:/app/data
    ports:
      - "127.0.0.1:内部端口:内部端口"
    networks:
      - ql_net

  openresty:
    image: openresty/openresty:alpine
    container_name: secure-gateway
    restart: always
    depends_on:
      - app
    ports:
      - "外网端口:80"
    environment:
      COOKIE_SECRET: "REPLACE_WITH_A_LONG_RANDOM_SECRET"
      COOKIE_NAME: "ql_auth"
      COOKIE_TTL: "3600"
    volumes:
      - /path/to/openresty/nginx.conf:/usr/local/openresty/nginx/conf/nginx.conf:ro
      - /path/to/openresty/.htpasswd:/etc/openresty/.htpasswd:ro
    networks:
      - ql_net

networks:
  ql_net:
    driver: bridge
```

## 4. 完整 nginx.conf

> 特点：
> - `map` 放在 `http {}` 级别
> - 不依赖 `resty.hmac`，使用内置 `ngx.hmac_sha1()`
> - `/__login` 触发 BasicAuth
> - `/__logout` 可清 Cookie（可选）

```nginx
worker_processes 1;
events {
    worker_connections 1024;
}
http {
    include mime.types;
    default_type application/octet-stream;
    sendfile on;
    keepalive_timeout 65;
    
    resolver 127.0.0.11 ipv6=off valid=30s;
    
    map $http_upgrade $connection_upgrade {
        default upgrade;
        '' close;
    }
    
    server {
        listen 80;
        server_name _;
        
        # 1) 登录入口：只在这里做 BasicAuth
        location = /__login {
            auth_basic "Restricted";
            auth_basic_user_file /etc/openresty/.htpasswd;
            
            content_by_lua_block {
                local secret = os.getenv("COOKIE_SECRET") or "change_me"
                local cookie_name = os.getenv("COOKIE_NAME") or "ql_auth"
                local ttl = tonumber(os.getenv("COOKIE_TTL") or "3600") or 3600
                
                local function to_hex(s)
                    return (s:gsub(".", function(c) return string.format("%02x", string.byte(c)) end))
                end
                
                local function sign(payload)
                    return to_hex(ngx.hmac_sha1(secret, payload))
                end
                
                local exp = ngx.time() + ttl
                local payload = tostring(exp)
                local token = payload .. "." .. sign(payload)
                
                local secure = ""
                if ngx.var.scheme == "https" then
                    secure = "; Secure"
                end
                
                ngx.header["Set-Cookie"] = cookie_name .. "=" .. token .. "; Path=/; Max-Age=" .. ttl .. "; HttpOnly; SameSite=Lax" .. secure
                
                local next_url = ngx.var.arg_next
                if not next_url or next_url == "" then
                    next_url = "/"
                end
                return ngx.redirect(next_url, 302)
            }
        }
        
        # 2) 退出入口
        location = /__logout {
            content_by_lua_block {
                local cookie_name = os.getenv("COOKIE_NAME") or "ql_auth"
                ngx.header["Set-Cookie"] = cookie_name .. "=deleted; Path=/; Max-Age=0; HttpOnly; SameSite=Lax"
                return ngx.redirect("/", 302)
            }
        }
        
        # 3) 主入口：校验 Cookie
        location / {
            access_by_lua_block {
                local secret = os.getenv("COOKIE_SECRET") or "change_me"
                local cookie_name = os.getenv("COOKIE_NAME") or "ql_auth"
                
                local function to_hex(s)
                    return (s:gsub(".", function(c) return string.format("%02x", string.byte(c)) end))
                end
                
                local function sign(payload)
                    return to_hex(ngx.hmac_sha1(secret, payload))
                end
                
                if ngx.var.uri == "/__login" or ngx.var.uri == "/__logout" then
                    return
                end
                
                local token = ngx.var["cookie_" .. cookie_name]
                local ok = false
                
                if token and token ~= "" then
                    local dot = token:find("%.")
                    if dot then
                        local payload = token:sub(1, dot - 1)
                        local sig = token:sub(dot + 1)
                        
                        if sig == sign(payload) then
                            local exp = tonumber(payload)
                            if exp and exp > ngx.time() then
                                ok = true
                            end
                        end
                    end
                end
                
                if not ok then
                    local next_url = ngx.escape_uri(ngx.var.request_uri)
                    return ngx.redirect("/__login?next=" .. next_url, 302)
                end
            }
            
            proxy_pass http://app:内部端口;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection $connection_upgrade;
        }
    }
}
```

## 5. 操作步骤

### Step 1：准备目录

```bash
mkdir -p /docker/qinglong/openresty
mkdir -p /docker/qinglong/data
```

### Step 2：生成 BasicAuth 账号密码

```bash
docker run --rm httpd:2.4-alpine \
  htpasswd -nbB username 'strong_password' \
  > /docker/qinglong/openresty/.htpasswd
```

### Step 3：生成 Cookie 签名密钥

```bash
python3 - <<'PY'
import os, base64
print(base64.b64encode(os.urandom(48)).decode())
PY
```

### Step 4-6：启动服务

```bash
cd /docker/qinglong
docker compose up -d
```

### Step 7：验证效果

1. 首次访问自动跳转 `/__login?next=...`
2. 弹 BasicAuth 输入一次
3. 登录后跳回原页面
4. 1 小时内无需再次验证
5. 访问 `/__logout` 可立即退出

## 6. 常见错误

**错误 1：`map directive is not allowed here`**
- 原因：`map` 写在了 `server {}` 内
- 修复：确保 `map` 位于 `http {}` 级别

**错误 2：`module 'resty.hmac' not found`**
- 原因：镜像没有 `lua-resty-hmac`
- 修复：改用 `ngx.hmac_sha1()`

## 7. 总结

这套方案的价值在于：

- **不改原应用容器**，通过网关实现可控认证
- BasicAuth 仅首次触发，之后靠签名 Cookie **严格 1 小时免验证**
- 无状态、不依赖外部存储，容器重启也不丢

适合个人/小团队把敏感面板从"裸奔公网"快速提升到"可控暴露"。
