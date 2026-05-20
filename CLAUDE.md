# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 环境配置

将 `.env.example` 复制为 `.env`，填入 `TIKHUB_API_TOKEN`。

安装依赖：
```
pip install -r requirements.txt
```

## 常用命令

```bash
# 查看今日 API 预算使用情况
python3 quick_fetch.py budget

# 执行完整每日抓取（Part 1 趋势 + Part 2 分类）
python3 quick_fetch.py full

# 快速单次抓取
python3 quick_fetch.py trends ID vv          # 印尼按播放量排行
python3 quick_fetch.py trends TH like        # 泰国按点赞排行
python3 quick_fetch.py category gaming ID    # 印尼游戏标签视频
python3 quick_fetch.py category comedy TH    # 泰国搞笑标签视频

# 启动前端服务（必须用 HTTP 服务，不能直接打开 index.html）
python3 -m http.server 8090
```

## 架构说明

**两文件设计：** `scraper.py` 是核心库（API 调用、解析、缓存、预算逻辑）；`quick_fetch.py` 是 CLI 入口，直接从 `scraper.py` 导入使用。

**数据流：**
1. `scraper.py` 通过 `TIKHUB_API_TOKEN` 调用 TikHub API（`https://api.tikhub.io`）
2. API 响应缓存到 `cache/resp_<md5>.json`，TTL 6 小时，避免重复消耗预算
3. 标签 ID 永久缓存在 `cache/tag_ids.json`——TikTok hashtag ID 不会变化
4. 每日调用次数记录在 `cache/budget.json`；`DAILY_BUDGET = 250`
5. 抓取结果目前输出到 `output/`（CSV + JSON）——**TODO**：应自动归档到 `data/<date>/combined.json` 并更新 `data/dates.json`

**前端：** `index.html` 是纯 HTML/JS/CSS 单文件应用，通过 `fetch()` 加载 `data/<date>/combined.json` 和 `data/dates.json`，**必须通过 HTTP 服务访问**，不能用 file:// 协议直接打开。

**两种抓取模式：**
- **Part 1**（`scrape_trends`）：调用 TikHub Ads API（`get_popular_trends`）抓取 ID/TH/PH × 4 排序维度的热门视频。当前**不可用**——TikHub 返回 `code 50004 "no available es index"`（服务端 Elasticsearch 问题，非网络问题）。
- **Part 2**（`scrape_categories`）：调用 `fetch_tag_post` 按标签抓取，3 分类 × 3 地区 × 3 标签 = 27 个标签。当前**唯一可用数据源**。

## 已知问题与注意事项

- **`get_popular_trends` 和 `get_hashtag_list`** 返回 `code 50004`——TikHub 服务端问题，无法在本地修复，需定期检查是否恢复。
- **`fetch_search_video`** 始终返回 400，无法使用。
- **video_id 是 19 位数字**——页面数据源必须用 JSON，不能用 CSV（CSV 会丢失大整数精度，导致 TikTok 链接失效）。
- **TikTok CDN 封面图**：需要在 `<img>` 标签加 `referrerpolicy="no-referrer"`，以及页面头部加 `<meta name="referrer" content="no-referrer">`，否则图片 403。
- **禁止用真实 API 调用做测试**——使用缓存响应或 `python3 quick_fetch.py budget` 确认状态。

## 目录结构说明

```
data/
  dates.json              # 可用日期数组，如 ["2026-05-19"]
  <date>/
    combined.json         # 当日合并数据，供 index.html 加载
    categories.json       # 仅 Part 2 分类数据
    global.json           # 全球探索数据
cache/
  tag_ids.json            # 标签名 → challenge ID 永久缓存（45 个标签已缓存）
  budget.json             # 每日 API 调用计数 {date: count}
  resp_<md5>.json         # API 响应缓存（6h TTL）
output/                   # 旧版抓取输出（CSV + JSON），前端不使用
```
