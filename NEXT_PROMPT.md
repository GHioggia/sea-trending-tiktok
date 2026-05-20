# NEXT_PROMPT

你现在接手一个已经进行中的项目。

请先阅读以下文件，恢复上下文：

1. HANDOFF.md
2. PROGRESS.md

读完后，请先输出：

1. 你理解的当前任务目标
2. 当前已经完成的内容
3. 当前未完成事项
4. 你认为下一步应该做什么
5. 你准备读取或检查哪些文件

在我确认前，不要直接做大规模代码修改。

当前优先级是：

1. 先确认项目当前状态
2. 再检查 HANDOFF.md / PROGRESS.md 中提到的关键文件
3. 然后继续推进最高优先级的未完成事项
4. 每完成一个小步骤，都要记录验证方式和结果
5. 如果发现 HANDOFF.md / PROGRESS.md 与真实代码不一致，以真实代码为准，并更新文档

禁止事项：

- 不要假设验证已经通过
- 不要伪造测试结果
- 不要一次性大范围重构
- 不要无视已有设计决策
- 不要重复读取大型文件全文，优先使用 grep / head / tail / offset / limit
- 不要把上下文扩展到与当前任务无关的模块

当前任务的继续目标是：

1. **[紧急] 修复 GLOBAL tab 数据**：`data/2026-05-19/combined.json` 中 60 条 global 数据字段名为长名（video_id/desc/...），需映射为短名（id/d/...），且 cat 字段从 None 改为 `global_trending`。参考 `scraper.py` 中的 `COLUMN_MAP`。
2. **[中] 补翻未翻译条目**：运行 `python3 translate_data.py` 翻译 combined.json 中缺少 zh 字段的条目。
3. **[中] 推送修复到 GitHub**：`git add -A && git commit && git push`
4. **[低] 确认 GitHub Pages 可访问**：页面地址 `https://ghioggia.github.io/sea-trending-tiktok/`

请开始。
