---
title: "I Built a LAN Dashboard to Track All My AI Coding Plan Quotas in One Place"
categories: ai_tech
tags:
  - AI Infrastructure
  - Self-hosting
  - DevOps
  - Coding Plan
  - Dashboard
  - Docker
  - Open Source
cover: https://picsum.photos/seed/coding-plan-dashboard-en/1600/900
coverWidth: 1600
coverHeight: 900
date: 2026-07-26 08:00:00
---

One-line summary: if you subscribe to two or more AI coding assistants — Codex, Kimi Code, MiniMax, Volcano Engine, LongCat, Qwen AI, Google AI — you probably also open four or five browser tabs every day just to check how much quota you have left. I got tired of that, so I built a self-hosted dashboard that pulls all of it into a single page. One Docker container, LAN-only, no third-party SaaS.

The project is open source: <https://github.com/margrop/coding-plan-dashboard>

<!-- more -->

## The Problem: Quota Sprawl

In the first half of 2026, nearly every major model provider launched a "Coding Plan" — a monthly or weekly subscription that gives you a request quota for AI-powered coding assistants. I ended up using seven of them simultaneously:

| Platform | Quota Model | How to Check |
|----------|-------------|--------------|
| Codex (OpenAI) | 5h window + weekly cap | Web dashboard |
| Kimi Code | 5h window + weekly cap | Web dashboard |
| MiniMax | Weekly cap | Web console |
| Volcano Engine | 5h window + weekly cap | API query |
| LongCat (Meituan) | Weekly cap | Web console |
| Qwen AI (Lingma) | Weekly cap | Web console |
| Google AI (Gemini CLI) | Daily + weekly cap | API query |

The core problem: **every platform has a different quota model and a different way to query it.**

Some give you a web dashboard you have to log into. Some only expose an API you have to curl and parse. Some don't even have an API — you just squint at a tiny line of text on a settings page.

I tried shell scripts with cron. I tried n8n workflows. Both hit the same wall: **authentication is wildly different across platforms.** Bearer tokens, AK/SK HMAC signatures, OAuth cookies, plain API keys — there's no single HTTP client pattern that covers them all.

And the quota windows make things worse. Codex, for example, uses rolling 5-hour windows. Quota you burn in window A doesn't free up until window B starts. If you don't know where you stand in the current window, you hit `rate_limit_exceeded` at the worst possible moment.

So I built my own aggregator.

## Design Principle: Glue, Not Another SDK

The first rule of this project: **don't wrap any platform's SDK, don't build a proxy.** It's a glue layer that sticks together the query capabilities each platform already provides.

The data collection workflow looks like this:

1. Open a platform's usage page in your browser
2. F12 → Network → find the request that returns quota JSON
3. Right-click → Copy as cURL
4. Paste it into the Dashboard's import box

The backend receives that cURL command and does something deliberately simple: **parse the URL, headers, and body, then replay the HTTPS request using Python's `httpx`.**

Here's a critical design decision: **I don't execute the cURL command via `subprocess`.** If I passed user-pasted cURL strings to a shell, that's a ready-made command injection vulnerability. A cURL command can hide `$(...)`, backticks, or pipe operators — any of which would give an attacker arbitrary command execution on my server.

So I chose the boring-but-safe path: use regex and `shlex` to decompose the cURL command into structured request parameters, then issue the HTTP request from Python. No shell involved.

![Data flow: from cURL paste to dashboard card](/post-images/coding-plan-dashboard/dataflow.png)

## Architecture

Three components, nothing more:

**Frontend**: a single static `index.html`. No build step. Vue 3 and Tailwind CSS load from CDN. All logic lives in one file. Yes, I know that sounds "un-engineered," but the frontend logic here is genuinely simple — render cards, show a table, handle imports. One file is easier to maintain than a webpack config.

**Backend**: a Python FastAPI app, roughly 1,200 lines. Three core jobs: parse cURL commands, replay HTTPS requests, normalize quota data. Plus a SQLite database for account configs and response caching.

**Deployment**: one Docker container exposing port 8080. No Nginx, no Redis, no message queue. LAN-only access, no TLS certificate needed.

![System architecture](/post-images/coding-plan-dashboard/architecture.png)

The reasoning behind this: **quota monitoring is low-frequency, low-concurrency, high-value.** I don't need to handle a thousand requests per second. I need to poll each platform every few minutes and show the results on a page. In that scenario, any extra infrastructure is a liability.

## Data Normalization: Seven JSON Shapes, One Model

The seven platforms return completely different JSON structures. Some give you `used_tokens` and `total_tokens`. Some give a `percentage`. Some only give `remaining`. Others split quota into `five_hour_window` and `weekly_limit` dimensions.

I defined a unified internal model:

```python
@dataclass
class QuotaSnapshot:
    platform: str          # platform identifier
    account_label: str     # user-assigned account name
    window_type: str       # "5h" | "weekly" | "daily"
    used: float            # usage (normalized to percentage)
    total: float           # total quota
    used_pct: float        # usage percentage
    window_start: datetime # window start time
    window_end: datetime   # window end time
    raw: dict              # original response, for debugging
```

Each platform gets a parser that maps its JSON onto this model. Adding a new platform means writing a new parser — typically 50-80 lines.

One gotcha I hit: **Volcano Engine's AK/SK signing.** Unlike every other platform that hands you a Bearer token and calls it a day, Volcano requires HMAC-SHA256 request signing with timestamp, region, and service name baked into the signature. My first attempt used cURL import directly, but the `Authorization` header in a captured cURL is time-bound — it expires. So Volcano Engine is the one platform that doesn't use the "cURL replay" path. Instead, users provide their AK and SK at import time, and the backend generates a fresh signature on every query.

![Dashboard main view — one card per platform showing current window usage](/post-images/coding-plan-dashboard/dashboard-cards.png)

## Running It

I run this on a small box on my LAN. Docker Compose, up in 30 seconds:

```yaml
# docker-compose.yml
services:
  dashboard:
    image: ghcr.io/margrop/coding-plan-dashboard:latest
    ports:
      - "8080:8080"
    volumes:
      - ./data:/app/data
    restart: unless-stopped
```

The `./data` directory holds the SQLite database and cache files. Config survives container rebuilds.

Open `http://<SERVER_IP>:8080` and the first screen looks like this:

![Dashboard hero section with global overview](/post-images/coding-plan-dashboard/dashboard-hero.png)

Top section: global overview — total accounts, average usage across current windows, and warnings for accounts about to hit their cap. Below that, one card per platform showing current window usage percentage, time remaining in the window, and a progress bar.

Scroll down and you hit the import panel. Paste a cURL command and the backend auto-detects which platform it belongs to:

![Import panel: paste cURL, auto-detect platform](/post-images/coding-plan-dashboard/dashboard-import.png)

Further down, the account management table — edit labels, adjust refresh intervals, trigger manual refreshes:

![Account management table](/post-images/coding-plan-dashboard/dashboard-accounts.png)

Mobile works too. I mostly check from my desktop, but it's handy on a phone:

![Mobile view](/post-images/coding-plan-dashboard/dashboard-mobile.png)

## Security: The Non-Negotiables

Since this tool handles platform credentials, security is the floor, not the ceiling:

**1. No shell execution.** cURL commands are parsed, never executed. All HTTP requests go through Python httpx.

**2. Domain allowlist.** The backend only sends requests to known platform domains. A cURL pointing at anything not on the list is rejected outright. This blocks SSRF — e.g., someone crafting a cURL aimed at `http://169.254.169.254/latest/meta-data/` to steal cloud instance metadata.

**3. LAN-only by design.** It listens on `0.0.0.0:8080`, but the docs explicitly recommend LAN use only. Don't expose it to the public internet. If you must, put a reverse proxy with auth in front.

**4. Credential storage.** AK/SK and tokens live in SQLite, unencrypted. This is a deliberate trade-off — for a LAN-only tool, local plaintext storage is an acceptable risk. If you need more, mount an encrypted volume.

## How It Compares

Before building this, I looked at existing options:

| Option | Pros | Cons |
|--------|------|------|
| Native platform dashboards | Most accurate data | N browser tabs, no aggregation |
| Grafana + custom plugins | Flexible, customizable | Heavy; need a data source plugin per platform |
| n8n / Home Assistant | Strong automation | Complex setup, weak display layer |
| Custom scripts + cron | Simple | No UI, poor multi-account support |

Coding Plan Dashboard is not a Grafana competitor. It's a "good enough" aggregation board. If you need time-series charts, alert rules, and multi-tenancy, use Grafana. If you just want to know "how much quota do I have left across my seven coding plans," this is for you.

## Trade-offs and Known Gaps

**No alerting.** I originally planned "notify when usage > 80%," but notification channels are a rabbit hole — email, DingTalk, Feishu, Telegram, Bark… For now, the UI does color-coded warnings (yellow > 70%, red > 90%). A webhook endpoint is on the roadmap so external systems can consume the data.

**No historical trends.** SQLite stores every query snapshot, so time-series charts are theoretically possible. But the frontend work for that — chart library, date pickers, interaction design — hasn't happened yet.

**cURL import isn't universal.** Some platforms render usage data client-side, embedding quota info in HTML rather than returning it via API JSON. For those, cURL import captures nothing useful. Until those platforms ship a proper API, they're out of scope.

## Open Source

The project is on GitHub: <https://github.com/margrop/coding-plan-dashboard>

![GitHub repository page](/post-images/coding-plan-dashboard/github-repo.png)

![Project README](/post-images/coding-plan-dashboard/github-readme.png)

Issues and PRs are welcome. The most needed contributions:

- **New platform parsers.** If you use Cursor, Windsurf, Claude Pro, or another coding plan — contribute a parser.
- **Alert integrations.** Webhook, DingTalk, Feishu, Telegram — any of them.
- **Historical trend charts.** A time dimension on the frontend.

## Bottom Line

This project solves one specific problem: **aggregated quota monitoring across multiple AI coding plan subscriptions.** It's not complex — one Docker container, one SQLite file, one HTML page. But it genuinely eliminates the daily ritual of opening four or five browser tabs to check quota.

If you're juggling multiple AI coding assistant subscriptions, give it a try. The deployment cost is minimal — anything that runs Docker works: a NAS, a Raspberry Pi, an old laptop, a cloud VM.

One last thought on self-hosting: not everything is worth building yourself. The value here isn't technical sophistication — it's putting scattered information in one place where your eyes can reach it. Sometimes "opening four fewer browser tabs" is the biggest productivity win.

---

*Related reading*

- [Reverse Proxy and Auth for Self-Hosted Services: Caddy in Practice](/post/2026-03-03-vps8-caddy-domain-configuration/)
- [Docker Compose Orchestration Best Practices](/post/2026-03-22-docker-container-security-best-practices/)
- [HomeLab Network Architecture: From a Single NAS to a Smart Home](/post/2026-07-14-coding-plan-dashboard-seven-versions/)

*References*

- [Coding Plan Dashboard on GitHub](https://github.com/margrop/coding-plan-dashboard)
- [OpenAI Codex Rate Limits](https://platform.openai.com/docs/guides/rate-limits)
- [Volcano Engine API Signing Docs](https://www.volcengine.com/docs/82379/1263482)
- [Google AI Studio API Docs](https://ai.google.dev/docs)

*Disclaimer: Platform names and quota models described here are subject to each provider's official documentation. Data shown is illustrative. This is a personal open-source project with no official affiliation with any listed platform.*

*[中文版本](/post/2026-07-25-coding-plan-dashboard-unified-quota-monitor/)*
