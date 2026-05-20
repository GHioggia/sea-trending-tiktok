# NEXT_PROMPT

你现在接手一个已经进行中的项目。

请先阅读以下文件，恢复上下文：

1. `HANDOFF.md`
2. `PROGRESS.md`

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
- 不要消耗 TikHub API 额度做无意义测试（每日限 50 次，当前设为 250 是调试临时值）

当前任务的继续目标是：

1. **改造 scraper.py 的 main() 输出**：运行后自动将 combined.json 写入 `data/<today>/`，并更新 `data/dates.json`，这样 index.html 页面切换日期时能自动看到新数据
2. **DAILY_BUDGET 恢复为用户实际额度**（确认后设回 50 或其他值）
3. **根据用户反馈继续调整 index.html**（如有）

技术要点提醒：
- TikHub Ads 接口 (`get_popular_trends`) 目前不可用（服务端 50004 错误），不是 bug
- Tag ID 缓存永久有效，无需刷新
- index.html 通过 fetch() 加载 `data/<date>/combined.json`，需要 HTTP 服务器
- 启动预览：`python3 -m http.server 8090 --directory /home/admin/workspace/tt_scraper`
- 获取公网 URL：`curl -s "http://localhost:58596/api/port-mapping?port=8090" | jq -r .url`

请开始。
