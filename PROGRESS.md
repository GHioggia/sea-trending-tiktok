# PROGRESS

## 当前阶段

**实现中** — 核心抓取+翻译+展示全链路已打通。有一个 GLOBAL 数据字段 BUG 需修复。已推送 GitHub。

## 本轮进展

1. 为视频标题添加中文翻译功能：先尝试 MyMemory（有日限额），后改用 Claude API（claude-haiku）批量翻译
2. 前端 index.html 新增 `.card-zh` 行展示中文说明，含 HASH_ZH 关键词映射兜底
3. 分类标签从 3 个扩展到 7 个：新增恐怖/萌宠/舞蹈/美食
4. 每个分类的 hashtag 从 3 个扩展到 5-8 个（数据驱动选择）
5. 前端 hashtag 提示区重新设计为标签卡片式排版，显示中文名 + 条目计数
6. 修复 `archive_to_data()` 从覆盖模式改为合并模式
7. 修复切换地区时分类筛选被重置的问题
8. 初始化 git 仓库，推送到 GitHub（GHioggia/sea-trending-tiktok）
9. 完整抓取一轮新数据（3355 条 + 翻译 2940 条）

## 任务状态表

| 任务 | 状态 | 说明 | 下一步 |
|---|---|---|---|
| TikHub API 调研 | DONE | 明确可用/不可用接口 | - |
| 抓取框架 v2（7分类） | DONE | 121 个标签已缓存 | 每日运行 full |
| 中文翻译集成 | DONE | Claude API 批量翻译 | 补翻 652 条 |
| index.html 前端 | DONE | 7分类+排序+翻译+卡片tag | 无 |
| scraper 输出自动归档 | DONE | archive_to_data 合并模式 | - |
| GitHub 推送 | DONE | 4 commits on main | - |
| GitHub Pages | NEED_VERIFY | 用户需手动启用 | 用户操作 |
| **GLOBAL tab 数据修复** | **TODO** | global.json 字段名不匹配 | 重新映射+合并 |
| Part1 趋势排行接入 | BLOCKED | TikHub Ads 接口 ES 异常 | 等待服务端修复 |

## 问题与修复记录

### 问题 1：Google Translate 不可达

- 现象：`httpx.ConnectError: [Errno 99] Cannot assign requested address`
- 原因：环境网络白名单限制，只有 tikhub.io 和 mymemory 可达
- 修复：改用 Claude API（claude-haiku）通过本地 proxy 翻译
- 结果：无日限额，翻译质量更好
- 后续注意：模型名只能用 `claude-haiku`/`claude-sonnet`/`claude-opus`

### 问题 2：archive_to_data 覆盖导致 GLOBAL 数据丢失

- 现象：第二次运行 `full` 后 GLOBAL tab 为空
- 原因：`archive_to_data()` 直接覆写 combined.json，60 条 global 数据被覆盖
- 修复：改为合并模式（新数据按 id 覆盖，保留旧条目）+ 手动恢复 global.json
- 结果：数据量恢复到 3415 条，但 global 条目字段名仍为长名
- 后续注意：**global.json 字段名映射尚未完成，GLOBAL tab 仍不可用**

### 问题 3：MyMemory 每日额度限制

- 现象：翻译 889 条后停止，报 quotaFinished
- 原因：免费每日 5000 字符限制
- 修复：切换到 Claude API 无限额翻译
- 结果：完全解决

## 验证状态

- 已验证：scraper 抓取流程、缓存机制、预算追踪、翻译流程、git push
- 未验证：GitHub Pages 部署是否成功（用户需启用）
- 需要人工验证：GLOBAL tab 修复后在浏览器查看
- 需要后续自动化验证：每日定时抓取是否正常

## 下一阶段目标

1. 修复 GLOBAL 数据字段映射（将 global.json 的长字段名转为短字段名 + cat=global_trending）
2. 补翻 652 条未翻译条目
3. 确认 GitHub Pages 可正常访问
4. 推送修复后的数据到 GitHub
