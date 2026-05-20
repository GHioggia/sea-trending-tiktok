# HANDOFF

## 1. 当前任务一句话总结

使用 TikHub API 抓取 TikTok 东南亚（印尼/泰国/菲律宾）热点短视频，按 7 个分类标签（游戏/搞笑/娱乐/恐怖/萌宠/舞蹈/美食）+ 全球热门组织数据，通过 index.html 前端页面展示，带中文翻译。项目已推送到 GitHub 并配置 Pages。**当前有一个 BUG 需修复：GLOBAL tab 数据丢失（字段名不匹配）**。

## 2. 项目与环境

- 当前目录：`/home/admin/workspace/tt_scraper`
- 当前分支：**main**
- Git 状态：干净（已全部提交+推送）
- 远程仓库：`https://github.com/GHioggia/sea-trending-tiktok.git`
- GitHub Pages：用户需在 Settings → Pages 启用（main / root）
- 主要技术栈：Python 3.12 + httpx + pandas + dotenv + anthropic；前端纯 HTML/CSS/JS
- 关键入口文件：`scraper.py`（主抓取+归档）、`quick_fetch.py`（CLI）、`index.html`（展示）、`translate_data.py`（翻译）
- 关键配置/文档路径：
  - `.env` — TikHub API Token
  - `cache/tag_ids.json` — 121 个标签 ID 缓存（永久）
  - `cache/budget.json` — 每日 API 请求计数
  - `data/dates.json` — 可用数据日期索引
  - `data/<date>/combined.json` — 每日合并数据（供 index.html 加载）

## 3. 当前目标

- **[紧急] 修复 GLOBAL tab 数据缺失**：`data/2026-05-19/global.json` 用的是长字段名（video_id/desc/...），合并到 combined.json 时没有做列名映射，且 `category` 字段为 None（应为 `global_trending`）
- 确认 GitHub Pages 已成功部署
- 每日运行 `python3 quick_fetch.py full` 即可自动抓取+归档+翻译

## 4. 已完成工作

| # | 做了什么 | 文件 | 验证 |
|---|---|---|---|
| 1 | 搭建 TikHub API 抓取框架 v2，7 个分类 × 3 地区，每类 5-8 个 hashtag | `scraper.py` | ✅ 已抓取 3355 条 |
| 2 | 快捷 CLI 工具（trends/category/budget/full） | `quick_fetch.py` | ✅ |
| 3 | 本地缓存机制：tag ID 永久缓存 + API 响应 6h TTL + 每日预算追踪 | `scraper.py`, `cache/` | ✅ |
| 4 | 自动归档到 `data/<date>/combined.json` + 更新 dates.json（合并模式不覆盖） | `scraper.py` archive_to_data() | ✅ |
| 5 | Claude API 批量翻译（claude-haiku），自动集成在 full 流程中 | `translate_data.py` | ✅ 2763/3415 条已翻译 |
| 6 | index.html 前端（dark theme, 7个分类Tab, 地区筛选, 排序, 中文翻译展示, hashtag 标签卡片） | `index.html` | ✅ |
| 7 | 切换地区时保持分类筛选状态 | `index.html` | ✅ |
| 8 | 推送到 GitHub | git remote | ✅ aa60075 |
| 9 | DAILY_BUDGET 从 250 调至 500 | `scraper.py` | ✅ |

## 5. 关键设计决策

| 决策 | 原因 | 影响范围 | 注意事项 |
|---|---|---|---|
| 使用 `fetch_tag_post` 作为核心数据源 | TikHub Ads 接口 `get_popular_trends` 返回 50004 | 全局 | Ads 接口恢复后可重新启用 Part1 |
| Tag ID 永久缓存不过期 | TikTok hashtag ID 是固定标识 | `cache/tag_ids.json` | 当前已缓存 121 个标签 |
| combined.json 使用短字段名（id/d/t/p/l/...） | 减小 JSON 体积，前端已适配 | 前端+归档 | global.json 仍用长字段名，需修复 |
| archive_to_data 合并模式 | 避免覆盖 global 等之前抓取的数据 | `scraper.py` | 新数据按 id 去重覆盖旧条目 |
| 翻译用 Claude API（claude-haiku） | 环境网络限制 Google Translate 不可达，MyMemory 有日限额 | `translate_data.py` | 本地 proxy `127.0.0.1:58597` 转发，模型名用 `claude-haiku` |
| GitHub Pages 从 main 分支根目录部署 | index.html 在根目录，data/ 也在根目录 | 部署 | 用户需手动启用 Pages |

## 6. 当前文件变更清单

| 文件 | 类型 | 摘要 | 风险 | 继续处理 |
|---|---|---|---|---|
| `scraper.py` | 修改 | 7分类扩展+archive_to_data合并模式+DAILY_BUDGET=500 | 低 | 需修复 global 数据合并逻辑 |
| `index.html` | 修改 | 7分类按钮+tag卡片排版+中文翻译+地区切换保持tab | 低 | 无 |
| `translate_data.py` | 修改 | 改用 Claude API 批量翻译 | 低 | 无 |
| `data/2026-05-19/combined.json` | 修改 | 3415条（但global 60条字段名错误） | **中** | **需修复** |
| `.gitignore` | 新增 | 排除 .env/cache/output/__pycache__ | 低 | 无 |

## 7. 验证记录

| 命令 | 目的 | 结果 | 备注 |
|---|---|---|---|
| `python3 quick_fetch.py budget` | 确认预算 | 今日 0/500 剩余 | 日期已翻到 2026-05-20 |
| `python3 quick_fetch.py full` | 完整抓取 | 3355 条分类数据 + 翻译 2940 条 | 预算用了 292 次 |
| `git push` | 推送到 GitHub | ✅ 成功 | 4 个 commit |
| `python3 -c "import scraper"` | 语法检查 | ✅ OK | - |
| 检查 combined.json global 数据 | 验证 GLOBAL tab | ❌ cat=None，字段名为长名 | **需修复** |

## 8. 未完成事项

1. **[高] 修复 GLOBAL 数据字段**：`data/2026-05-19/combined.json` 中 60 条 global 数据的字段名是长名（video_id 而非 id），且 cat 为 None（应为 global_trending）。需要重新处理 global.json → 映射列名 + 设置 cat=global_trending → 合并回 combined.json
2. **[中] 未翻译条目**：3415 条中有 652 条无 zh 字段（主要是新增的 dance/food 分类和 global）
3. **[低] DAILY_BUDGET 恢复**：当前为 500（调试用），日常应根据用户实际套餐设定
4. **[低] GitHub Pages 启用**：用户需手动到 Settings → Pages 启用
5. **[低] `get_popular_trends` 接口**：仍返回 50004，定期检查恢复

## 9. 已知风险与坑点

- **global.json 用长字段名**：历史遗留文件，和 combined.json 的短字段名不一致。合并时必须做 COLUMN_MAP 映射 + 设置 `cat: "global_trending"`
- **Claude API 模型名**：本环境 proxy 只认 `claude-haiku`/`claude-sonnet`/`claude-opus`（无版本号），不支持 `claude-3-5-haiku-20241022` 等完整名称
- **TikTok CDN 封面图**：需要 `referrerpolicy="no-referrer"`，否则 403
- **video_id 是 19 位数字**：必须用 JSON 不能用 CSV
- **网络限制**：环境只能访问 api.tikhub.io 和 api.mymemory.translated.net，Google/DeepL 等均不可达
- **`fetch_search_video`** 始终返回 400，无法使用

## 10. 下轮建议读取的文件

| 文件 | 原因 |
|---|---|
| `data/2026-05-19/global.json` | 需修复字段名映射，head 看前几条即可 |
| `scraper.py` 的 `archive_to_data()` 函数 | 需要在合并 global 数据时做字段映射 |
| `index.html` 的 `doFilter()` | 确认 global_trending 过滤逻辑 |
| `data/2026-05-19/combined.json` | 验证修复后 global 数据正确 |
