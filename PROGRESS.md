# PROGRESS

## 当前阶段

**实现中** — 核心抓取逻辑和前端展示已完成，正在打磨 UI 交互和完善数据归档流程。

## 本轮进展

1. 调研 TikHub API，发现可用端点：`fetch_tag_post`、`fetch_explore_post`、`fetch_tag_detail`
2. 发现 `fetch_search_video` 始终 400、`get_popular_trends` 返回 50004
3. 搭建 scraper v1（基于 SEA_HASHTAGS 硬编码标签），成功拉取印尼 260 条 + 泰国 145 条
4. 添加 tag ID 本地缓存 + API 响应缓存（6h TTL）
5. 用户提出 50 次/天预算限制，重新设计为 Part1 (趋势排行 12 次) + Part2 (分类标签 27 次) = 39 次/天
6. 重写 scraper v2：CATEGORY_TAGS 按游戏/搞笑/娱乐分类，每类每国 3 标签
7. 用户充值后全量拉取：1515 条分类 + 60 条全球 = 1575 条
8. 前端 index.html 多次迭代：暗色主题 → 加分类筛选 → 改 Tab 结构 → 数据按日期归档加载
9. 最后一次 UI 调整：GLOBAL 移到最后、GLOBAL 也有 Sort、Sort 统一靠右

## 任务状态表

| 任务 | 状态 | 说明 | 下一步 |
|---|---|---|---|
| TikHub API 调研 | DONE | 明确可用/不可用接口 | - |
| 抓取框架 v2 | DONE | Part1+Part2, 预算追踪 | 输出自动归档到 data/ |
| Tag ID 缓存 | DONE | 45 个标签已缓存 | 无需刷新 |
| 全量数据拉取 | DONE | 1575 条 | 每日可重复运行 |
| index.html 前端 | DOING | Tab/筛选/排序基本完成 | 用户可能还有微调 |
| scraper 输出归档 | TODO | 当前 main() 输出到 output/ | 改为自动写入 data/<date>/ |
| Part1 趋势排行接入 | BLOCKED | TikHub Ads 接口 ES 异常 | 等待服务端修复 |
| output/ 目录清理 | DEFERRED | 旧文件仍存在 | 低优先级 |

## 问题与修复记录

### 问题 1：CSV 导致 video_id 精度丢失

- 现象：18-19 位数字的 video_id 在 CSV 中末几位变为 0，导致 TikTok 链接无法打开
- 原因：Excel/pandas CSV 将大整数当作浮点数处理
- 修复：数据源改用 JSON，video_id 始终以字符串存储
- 结果：链接全部可正确跳转
- 后续注意：不要用 CSV 作为页面数据源

### 问题 2：TikHub Ads 接口不可用

- 现象：`get_popular_trends` 和 `get_hashtag_list` 返回 `code: 50004, "no available es index"`
- 原因：TikHub 服务端 Elasticsearch 索引未就绪
- 修复：无法修复（服务端问题），通过代理测试排除了网络原因
- 结果：Part1 暂时无数据，仅 Part2 标签方案工作
- 后续注意：定期检测是否恢复

### 问题 3：TikTok CDN 封面图 403

- 现象：卡片封面图无法加载
- 原因：TikTok CDN 检查 Referer
- 修复：添加 `<meta name="referrer" content="no-referrer">` + img 标签 `referrerpolicy="no-referrer"`
- 结果：封面正常显示

## 验证状态

- 已验证：scraper 抓取流程、缓存机制、预算追踪、index.html 页面加载和筛选
- 未验证：scraper 输出自动归档到 data/（尚未实现）
- 需要人工验证：TikHub Ads 接口是否恢复
- 需要后续自动化验证：每日定时抓取是否正常

## 下一阶段目标

1. 改造 `scraper.py` 的 `main()` 使其输出自动归档到 `data/<date>/combined.json` 并更新 `dates.json`
2. 根据用户反馈继续微调 index.html
3. 监控 TikHub Ads 接口恢复情况
