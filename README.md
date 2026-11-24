# sea-trending-tiktok

东南亚 TikTok 热点内容 + Roblox 榜单的每周抓取与展示工具，面向微恐向休闲游戏团队做选题与买量参考。

每周一定时跑一轮：抓 5 个国家的分类标签视频、发现当周新话题、抓 Roblox 各国趋势榜，然后翻译标题、生成 AI 洞察、部署 GitHub Pages、推送钉钉周报。

**线上地址**：https://ghioggia.github.io/sea-trending-tiktok （gh-pages 分支，需自备网络环境）

---

## 抓取范围

| 维度 | 内容 |
|---|---|
| 国家 | 印尼 ID / 泰国 TH / 菲律宾 PH / 马来西亚 MY / 新加坡 SG |
| 分类 | 游戏、沙雕搞笑、娱乐、恐怖灵异、萌娃萌宠、舞蹈挑战（6 类） |
| 标签 | 各国本地化标签 + 跨国通用标签归入 `global`，去重后 140 个 |
| 补充 | 各国近 7 天热门话题榜（发现预设标签外的新梗）、Roblox 各国趋势/新晋榜 |

抖音、美食两个分类已于 2026-10-24 停止采集，历史周数据仍在，前端加载时过滤。

## 数据来源与额度

- **TikHub API**（`https://api.tikhub.io`）—— TikTok 侧全部数据，需 `TIKHUB_API_TOKEN`，按次计费
- **Roblox explore-api** —— 不消耗 TikHub 额度，无官方文档，需走代理
- **LLM 网关**（Anthropic 兼容）—— 洞察、翻译、话题分类、Roblox 介绍、钉钉文案

本地有每日调用上限 `DAILY_BUDGET = 500`（`cache/budget.json` 计数，与 TikHub 账户余额无关）。余额不足时 API 返回 402，流程中止并发钉钉告警。响应缓存 6 小时（`cache/resp_<md5>.json`），标签 ID 与 Roblox 介绍永久缓存。

## 每周流程

`bash run_weekly.sh` → 后台执行 `python3 weekly_job.py weekly`，日志写在 `logs/weekly_<时间>.log`。全程约 2 小时。

| # | 步骤 | 做什么 | TikHub 调用 |
|---|---|---|---|
| 1 | 分类标签抓取 | 6 分类 × 各国本地化标签，每标签取 30 条，归档到 `data/<周一日期>/combined.json`，下载封面 | ~140 |
| 2 | 新话题发现 | 热门话题榜 → LLM 分类筛选 → 同一事件变体归并（每组只搜一次）→ 关键词搜近 7 天代表视频 → 用代表视频标题复核类别与释义 → 按共现标签二次归并 | 35–45 |
| 3 | Roblox 榜单 | 各国热门趋势/新晋上升榜，榜单抓到即落盘，图标与中文介绍失败只降级不丢数据 | 0 |
| 4 | 标题翻译 | 批量中译，写入记录的 `zh` 字段 | 0 |
| 5 | AI 洞察 | 地区 × 分类 + 整体 + 摘要，写 `insights.json` | 0 |
| 6 | 部署与通知 | 部署 gh-pages → bot 提交并推送 main → 钉钉周报（`.notified` 防重复，每期只发一次） | 0 |

单周产出量级参考：2026-11-23 那期 3770 条视频。数据保留最近 5 周（`MAX_WEEKS`），更早的目录在部署前清理。

## 快速开始

```bash
pip install -r requirements.txt
cp .env.example .env      # 填入 TIKHUB_API_TOKEN
```

### 环境变量

| 变量 | 用途 | 必填 |
|---|---|---|
| `TIKHUB_API_TOKEN` | TikHub API 鉴权 | 是 |
| `ANTHROPIC_BASE_URL` / `ANTHROPIC_AUTH_TOKEN` | LLM 网关地址与 Bearer 凭据；留空则走官方 API + `ANTHROPIC_API_KEY` | 否 |
| `ANTHROPIC_MODEL` | 洞察/翻译/话题分类/Roblox 介绍用的模型（代码默认 `glm-5.2`） | 否 |
| `DINGTALK_MODEL` | 钉钉周报文案专用模型，默认 `qwen3.8-max` | 否 |
| `PAGES_URL` | 站点地址，用作钉钉消息里的传送门 | 否 |
| `GITHUB_REPO` / `GIT_PUSH_PROXY` | 部署推送目标与 push 代理 | 否 |
| `COVER_PROXY` | 封面（TikTok CDN）与 Roblox 图标（rbxcdn）下载代理 | 否 |
| `ROBLOX_PROXY` | Roblox explore-api 代理，留空则用 `CLAUDE_WEB_PROXY` | 否 |
| `SSL_CERT_FILE` | 企业网络中间人证书路径 | 否 |

### 钉钉机器人（可选）

不配这一步，流程照跑，只是不推送。在仓库根目录建 `dingtalk_bots.json`（已在 `.gitignore`，**不要提交**，里面是 webhook 凭据）：

```json
[
  {"name": "测试群", "webhook": "https://oapi.dingtalk.com/robot/send?access_token=<token>", "enabled": true, "alert": true},
  {"name": "正式群", "webhook": "https://oapi.dingtalk.com/robot/send?access_token=<token>", "enabled": true}
]
```

`enabled` 控制是否收周报，`alert` 控制是否收抓取异常告警。

### 本地看前端

```bash
python3 -m http.server 8090     # 然后访问 http://localhost:8090
```

必须走 HTTP 服务：页面用 `fetch()` 读 `data/<date>/*.json`，`file://` 直接打开会被浏览器拦掉。

## 常用命令

```bash
python3 quick_fetch.py budget              # 查看今日 API 预算使用情况
bash run_weekly.sh                         # 每周全流程（脱离会话后台运行）
python3 weekly_job.py weekly               # 同上，前台运行（会被会话超时杀掉，仅用于调试）
python3 quick_fetch.py category gaming ID  # 单次抓取：印尼游戏标签视频
python3 quick_fetch.py category horror TH  # 单次抓取：泰国恐怖标签视频
python3 quick_fetch.py trends ID vv        # 单次抓取：印尼按播放量排行
```

**不要前台跑每周全流程**：约 2 小时，在受超时限制的会话里会被转后台、会话结束即被杀。`run_weekly.sh` 用 `nohup setsid` 脱离会话，并带重复启动保护。

## 目录结构

```
scraper.py            核心库：API 调用、解析、缓存、预算、Roblox/话题抓取
weekly_job.py         每周调度：抓取 → 翻译 → 洞察 → 部署 → 钉钉通知
translate_data.py     标题翻译
quick_fetch.py        手动 CLI
index.html            前端单文件应用（纯 HTML/CSS/JS，无构建步骤）
run_weekly.sh         定时任务入口

data/
  dates.json              可用周期数组（最新在前，保留 5 周）
  <date>/
    combined.json         当周分类标签视频（短字段，映射见 scraper.COLUMN_MAP）
    insights.json         地区 × 分类 AI 洞察
    topics.json           各国热门话题榜 + 分类结果（picked=入选）
    topic_videos.json     入选话题的代表视频（结构同 combined.json）
    roblox.json           Roblox 各国榜单、游戏详情与中文介绍
    covers/               视频封面 WebP 缩略图
    roblox/               Roblox 游戏图标
    .notified             钉钉通知已发送标记
cache/                  API 响应缓存、标签 ID、预算计数（不入库，可重建）
logs/                   运行日志（不入库，可能含代理凭据）
output/                 旧版 CSV/JSON 输出，前端不使用
```

### combined.json 字段

短字段是为了压缩体积：`id` 视频 ID、`d` 原标题、`zh` 中文翻译、`t` 发布时间、`an`/`au` 作者昵称/账号、`p`/`l`/`cm`/`sh` 播放/点赞/评论/分享、`dur` 时长、`cov` 封面相对路径、`h` 标签、`r` 地区、`cat` 分类、`url` 视频链接、`qr`/`qt` 命中的查询地区与标签、`srcs`/`cats`/`qrs`/`qts` 多来源合并后的溯源信息。

`id` 是 **19 位数字**，页面数据源必须用 JSON——CSV 会丢大整数精度，导致 TikTok 链接失效。

## 前端

`index.html` 三个视图：**TIKTOK 视频**（一级 Tab 按地区：东南亚/泰国/印尼/菲律宾/马来西亚/新加坡/全球，二级按分类筛选，另有多种排序，其中「起量速度」= 播放 ÷ 发布天数，用于突出新视频）、**本周新话题**、**ROBLOX 榜单**。

TikTok CDN 的封面图需要 `<img referrerpolicy="no-referrer">` 且页面头部带 `<meta name="referrer" content="no-referrer">`，否则 403。

## 钉钉周报

消息为 markdown 格式：标题 + 本周监测条数与地区分布 → 「恐怖内容灵感」与「传播策略参考」两个板块、共 4 个要点 → 本周行动建议 → 站点传送门。

每个要点后附 1–2 条**该要点引用的视频链接**。实现上不让模型直接写 URL（19 位视频 ID 会被改位数）：代码按与洞察取样同口径挑出候选视频并编号，模型只输出 `LINKS: 编号`，由 `_render_links()` 查表替换成真实链接，无效编号静默丢弃。

## 已知限制

- **标签抓取有盲区**：接口只返回标签下历来较热门的视频（7 天内发布约占三分之一），抓不到预设列表外的新梗——由「新话题发现」补充
- 超大标签（如 `#dance`、`#pets`）接口可能返回 0 条
- 热门话题榜须用 POST 调 `/api/v1/tiktok/ads/get_trends_hashtag_list`（GET 返回 405）
- 视频搜索用 App 端 `/api/v1/tiktok/app/v3/fetch_video_search_result`（Web 端 `fetch_search_video` 返回 400），关键词含下划线时可能 400
- App 端接口的封面 `url_list[0]` 常为 HEIC（PIL 无法解码），需优先选 JPEG/WebP 变体
- Roblox explore-api 沙箱直连会被断开，需代理，且必须用 `requests`（`httpx` 会被服务端断开）
- 新增标签前先用 `fetch_tag_detail` 查视频量（每个 1 次调用）；标签接口不区分国家，同一标签放进多个地区只会得到同一批视频，跨国通用标签统一放 `global`

## 文档

- `CLAUDE.md` —— 面向 Claude Code 的项目说明（架构、命令、注意事项），与本文件同源，改动请一并更新
- `HANDOFF.md` / `PROGRESS.md` / `NEXT_PROMPT.md` —— 2026-05 的阶段性交接记录，**已过时**（当时是 3 地区 7 分类、每日抓取），现状以本文件为准
