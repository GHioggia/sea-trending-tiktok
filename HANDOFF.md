# HANDOFF

## 1. 当前任务一句话总结

使用 TikHub API 抓取 TikTok 东南亚（印尼/泰国/菲律宾）热点短视频，按分类标签（游戏/搞笑/娱乐）和全球热门组织数据，通过 index.html 前端页面展示。核心抓取和展示功能已完成，正在优化前端页面交互。

## 2. 项目与环境

- 当前目录：`/home/admin/workspace/tt_scraper`
- 当前分支：**不是 git 仓库**
- Git 状态：无 git
- 主要技术栈：Python 3.12 + httpx + pandas + dotenv；前端纯 HTML/CSS/JS
- 关键入口文件：`scraper.py`（主抓取）、`quick_fetch.py`（CLI 快捷工具）、`index.html`（展示页面）
- 关键配置/文档路径：
  - `.env` — TikHub API Token
  - `cache/tag_ids.json` — 45 个标签 ID 缓存（永久）
  - `cache/budget.json` — 每日 API 请求计数
  - `data/dates.json` — 可用数据日期索引
  - `data/<date>/combined.json` — 每日合并数据（供 index.html 加载）

## 3. 当前目标

- 完善 index.html 前端展示页面的交互体验
- 后续需要将 scraper.py 的输出自动归档到 `data/<date>/` 目录结构
- 不应修改核心抓取逻辑，不应消耗 API 额度做测试

## 4. 已完成工作

| # | 做了什么 | 文件 | 验证 |
|---|---|---|---|
| 1 | 搭建 TikHub API 抓取框架（v2），支持 Part1 趋势排行 + Part2 分类标签 | `scraper.py` | ✅ 已运行，Part2 拉取 1515 条 |
| 2 | 快捷 CLI 工具（trends/category/budget 命令） | `quick_fetch.py` | ✅ budget 命令验证通过 |
| 3 | 本地缓存机制：tag ID 永久缓存 + API 响应 6h TTL + 每日预算追踪 | `scraper.py`, `cache/` | ✅ 全部验证通过 |
| 4 | 全量数据拉取：1515 条分类 + 60 条全球 = 1575 条 | `data/2026-05-19/` | ✅ |
| 5 | index.html 前端页面（dark theme, tabs, category filters, sort） | `index.html` | ✅ 可通过 HTTP 访问 |
| 6 | 数据按日期归档目录结构 | `data/` | ✅ 2 天数据已归档 |

## 5. 关键设计决策

| 决策 | 原因 | 影响范围 | 注意事项 |
|---|---|---|---|
| 使用 `fetch_tag_post` 作为核心数据源（非 ads 排行接口） | TikHub Ads 接口 `get_popular_trends` 服务端 ES 索引异常（code 50004），所有国家均返回空 | 全局 | Ads 接口恢复后可重新启用 Part1 |
| Tag ID 永久缓存不过期 | TikTok hashtag ID 是固定标识，不会变化 | `cache/tag_ids.json` | 标签被下架时会返回空数据但不报错 |
| 每日预算追踪（DAILY_BUDGET） | 用户套餐有限，需严格控制 | `scraper.py` | 当前设为 250（用户已充值），原始套餐为 50 |
| index.html 通过 fetch 加载 `data/<date>/combined.json` | 支持多日期切换，页面本身不内嵌数据 | `index.html`, `data/` | 需要 HTTP 服务器，不能直接双击打开 |
| 代理 `http://mgproxy.ejoy.com:23488` 可用但对 Ads 接口无帮助 | 已验证代理不影响 50004 错误 | 无 | 用户提供的代理地址 |

## 6. 当前文件变更清单

| 文件 | 类型 | 摘要 | 风险 | 继续处理 |
|---|---|---|---|---|
| `scraper.py` | 新增 | v2 抓取框架，Part1+Part2，预算追踪 | 低 | 需要把输出自动写入 `data/<date>/` |
| `quick_fetch.py` | 新增 | CLI 工具 | 低 | 无 |
| `index.html` | 新增 | 前端展示页面 | 低 | 用户正在调整 UI |
| `data/dates.json` | 新增 | 日期索引 | 低 | scraper 需自动更新此文件 |
| `data/2026-05-19/combined.json` | 新增 | 当日数据 | 低 | 无 |
| `cache/tag_ids.json` | 修改 | 45 个标签 ID | 低 | 无 |
| `.env` | 存在 | 含用户 API Token | 高 | 不要提交到版本控制 |

## 7. 验证记录

| 命令 | 目的 | 结果 | 备注 |
|---|---|---|---|
| `python3 quick_fetch.py budget` | 验证预算追踪 | 正常显示 50/50 used | - |
| `python3 scraper.py` (full run) | 完整抓取测试 | Part1 返回 0（Ads 接口异常），Part2 成功 345 条 | 首次运行消耗了标签解析 |
| 手动完整拉取脚本 | 1515+60 条视频 | 成功，56 次 API 调用 | - |
| `curl http://localhost:8090/index.html` | 验证页面服务 | 200 OK | HTTP server on port 8090 |
| 代理测试 get_popular_trends | 排除网络问题 | 同样 50004 错误 | TikHub 服务端问题 |

## 8. 未完成事项

1. **[高] scraper.py 输出自动归档** — main() 运行后应自动将数据写入 `data/<today>/combined.json` 并更新 `data/dates.json`
2. **[中] Part1 趋势排行** — `get_popular_trends` 接口恢复后重新接入
3. **[中] index.html 细节打磨** — 用户可能还有 UI 调整需求
4. **[低] DAILY_BUDGET 恢复** — 当前设为 250（调试用），日常应该设回 50 或用户实际套餐额度
5. **[低] output/ 目录清理** — 旧的 CSV/JSON 文件仍在 output/ 中

## 9. 已知风险与坑点

- **TikHub Ads 接口不可用**：`get_popular_trends` 和 `get_hashtag_list` 均返回 `code: 50004, "no available es index"`。这不是用户网络/套餐问题，是 TikHub 服务端维护。代理测试已确认。
- **CSV 大数字精度丢失**：video_id 是 19 位数字，CSV 会截断末位变 0。页面数据源必须用 JSON，不能用 CSV。
- **TikTok CDN 封面图**：需要 `referrerpolicy="no-referrer"` 才能加载，否则 403。
- **fetch_search_video 接口**：一直返回 400，无法使用搜索功能。
- **index.html 需要 HTTP 服务器**：使用 fetch() 加载 JSON，不能 file:// 协议打开。

## 10. 下轮建议读取的文件

| 文件 | 原因 |
|---|---|
| `index.html` | 用户正在迭代 UI，需了解当前结构 |
| `scraper.py` 的 `main()` 函数 | 需要改造输出路径到 `data/<date>/` |
| `data/dates.json` | 了解日期索引格式 |
| `cache/tag_ids.json` | 确认 45 个标签都已缓存 |
| `.env` | 确认 Token 存在 |
