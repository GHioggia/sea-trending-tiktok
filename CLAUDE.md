# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 环境配置

将 `.env.example` 复制为 `.env`，填入 `TIKHUB_API_TOKEN`；代理相关变量（`COVER_PROXY`、`ROBLOX_PROXY`、`GIT_PUSH_PROXY`）见 `.env.example` 注释。

安装依赖：
```
pip install -r requirements.txt
```

## 常用命令

```bash
# 查看今日 API 预算使用情况
python3 quick_fetch.py budget

# 每周全流程（定时任务入口）：脱离会话后台运行，日志在 logs/weekly_<时间>.log
bash run_weekly.sh

# 快速单次抓取
python3 quick_fetch.py category gaming ID    # 印尼游戏标签视频
python3 quick_fetch.py category horror TH    # 泰国恐怖标签视频

# 启动前端服务（必须用 HTTP 服务，不能直接打开 index.html）
python3 -m http.server 8090
```

**每周全流程约 2 小时**（抓取 + 封面 + 翻译），必须用 `run_weekly.sh` 或 `nohup setsid` 脱离会话运行；在 Claude 的 Bash 里前台跑会因 600s 超时转后台，会话结束即被杀。

## 架构说明

**核心文件：** `scraper.py` 是核心库（API 调用、解析、缓存、预算、Roblox/话题抓取）；`weekly_job.py` 是每周调度（抓取 → 翻译 → AI 洞察 → 部署 → 钉钉通知）；`translate_data.py` 负责标题翻译；`quick_fetch.py` 是手动 CLI。

**每周流程（`weekly_job.py weekly`）：**
1. **分类标签抓取**（`scrape_categories`）：6 分类（游戏/搞笑/娱乐/恐怖/萌宠/舞蹈）× ID/TH/PH/MY/SG/global 的本地化标签，约 140 次调用
2. **新话题发现**（`run_topics`）：各国近 7 天热门话题榜 → 大模型分类筛选 → 关键词搜索近 7 天代表视频，约 35–45 次调用
3. **Roblox 榜单**（`run_roblox`）：各国热门趋势/新晋上升榜 + 中文介绍，不消耗 TikHub 额度
4. 翻译、生成 `insights.json`、部署 gh-pages（`deploy_pages`）、bot 提交并推送 main（`sync_main`）、钉钉通知（每期只发一次，`.notified` 防重复）

**数据流：**
1. 通过 `TIKHUB_API_TOKEN` 调用 TikHub API（`https://api.tikhub.io`），`api_get` / `api_post` 统一处理缓存与预算
2. API 响应缓存到 `cache/resp_<md5>.json`，TTL 6 小时，避免重复消耗预算
3. 标签 ID 永久缓存在 `cache/tag_ids.json`；Roblox 中文介绍按 universeId 永久缓存在 `cache/roblox_intro.json`
4. 每日调用次数记录在 `cache/budget.json`；`DAILY_BUDGET = 500`（本地上限，与 TikHub 账户余额无关；余额不足时 API 返回 402，流程会中止并告警）
5. 抓取结果归档到 `data/<周一日期>/`（归档日期取本周一，周一当天运行即归档到当天），并更新 `data/dates.json`；`output/` 为旧版 CSV/JSON 输出，前端不使用

**前端：** `index.html` 是纯 HTML/JS/CSS 单文件应用，三个视图：TikTok 视频、本周新话题、Roblox 榜单。通过 `fetch()` 加载 `data/<date>/` 下的 JSON，**必须通过 HTTP 服务访问**，不能用 file:// 协议直接打开。线上地址：https://ghioggia.github.io/sea-trending-tiktok （gh-pages 分支）。

**标签配置原则：** 标签抓取接口不区分国家，同一标签放进多个地区会得到同一批视频。因此各国只放本地化标签，跨国通用标签（如 `#roblox`、`#analoghorror`）统一放 `global`。新增标签前先用 `fetch_tag_detail` 查视频量（每个 1 次调用）。

## 已知问题与注意事项

- **标签抓取有盲区**：只返回标签下历来较热门的视频（7 天内发布约占三分之一），抓不到预设列表外的新梗——由「新话题发现」补充；页面「起量速度」排序（播放 ÷ 发布天数）用于突出新视频。超大标签（如 `#dance`、`#pets`）接口返回 0 条。
- **热门话题榜**须用 POST 调 `/api/v1/tiktok/ads/get_trends_hashtag_list`（GET 返回 405）；旧的 `get_hashtag_list` 返回 404，`get_popular_trends` 最后记录为 `code 50004`。
- **视频搜索**：Web 端 `fetch_search_video` 返回 400；App 端 `/api/v1/tiktok/app/v3/fetch_video_search_result` 可用（支持 `region`、`publish_time=7`），关键词含下划线时可能 400。
- **封面 HEIC**：App 端接口的 `url_list[0]` 常为 HEIC（PIL 无法解码），需优先选 JPEG/WebP 变体。
- **Roblox**：explore-api 无官方文档；沙箱直连会被断开，需走代理（`ROBLOX_PROXY`，缺省 `CLAUDE_WEB_PROXY`），且必须用 `requests`（`httpx` 会被服务端断开）；图标在 rbxcdn，走 `COVER_PROXY`。
- **TikHub MCP 工具**当前报 session 无效，探测接口请直接用 `api_get` / `api_post`（会计入本地预算）。
- **video_id 是 19 位数字**——页面数据源必须用 JSON，不能用 CSV（CSV 会丢失大整数精度，导致 TikTok 链接失效）。
- **TikTok CDN 封面图**：需要在 `<img>` 标签加 `referrerpolicy="no-referrer"`，以及页面头部加 `<meta name="referrer" content="no-referrer">`，否则图片 403。
- **抖音、美食已停止采集**（2026-10-24）：历史周数据中仍有这些记录，前端加载时过滤（`isRetired`）。
- **日志可能含代理凭据**：`logs/` 已加入 `.gitignore`，不要提交或打印。
- **禁止用真实 API 调用做测试**——使用缓存响应或 `python3 quick_fetch.py budget` 确认状态；必须实测时先说明调用次数。

## 目录结构说明

```
data/
  dates.json              # 可用日期数组（最新在前），保留最近 5 周
  <date>/
    combined.json         # 当周分类标签视频（短字段，见 scraper.COLUMN_MAP）
    insights.json         # 地区 × 分类 AI 洞察
    topics.json           # 各国热门话题榜 + 分类结果（picked=入选）
    topic_videos.json     # 入选话题的代表视频（结构同 combined.json）
    roblox.json           # Roblox 各国榜单、游戏详情与中文介绍
    roblox/               # Roblox 游戏图标
    covers/               # 视频封面 WebP 缩略图
    .notified             # 钉钉通知已发送标记
cache/
  tag_ids.json            # 标签名 → challenge ID 永久缓存
  roblox_intro.json       # Roblox 中文名/介绍永久缓存
  budget.json             # 每日 API 调用计数 {date: count}
  resp_<md5>.json         # API 响应缓存（6h TTL）
logs/                     # 运行日志（不入库）
output/                   # 旧版抓取输出（CSV + JSON），前端不使用
```
