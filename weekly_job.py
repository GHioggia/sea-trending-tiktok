"""
每周自动化调度脚本
用法:
    python3 weekly_job.py saturday   # 周六：萌宠 + 舞蹈 + 美食
    python3 weekly_job.py sunday     # 周日：搞笑 + 娱乐
    python3 weekly_job.py monday     # 周一：游戏 + 恐怖 → 合并 → 部署 → 通知
"""

import os
import sys
import json
import shutil
import subprocess
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv
import httpx

load_dotenv()

from scraper import (
    API_TOKEN,
    scrape_categories,
    archive_to_data,
    get_today_remaining,
    get_today_usage,
    DAILY_BUDGET,
    DATA_DIR,
)

SCHEDULE = {
    "friday": {"categories": None, "regions": ["global"]},
    "saturday": {"categories": ["cute", "dance", "food"]},
    "sunday": {"categories": ["comedy", "entertainment"]},
    "monday": {"categories": ["gaming", "horror"]},
}

DINGTALK_BOTS_FILE = Path("dingtalk_bots.json")
PAGES_URL = os.getenv("PAGES_URL", "https://ghioggia.github.io/sea-trending-tiktok")
SITE_DIR = Path("_site")
LOG_DIR = Path("logs")


def get_monday_date(today: date | None = None) -> date:
    today = today or date.today()
    weekday = today.weekday()  # Mon=0, Sat=5, Sun=6
    if weekday == 5:
        return today + timedelta(days=2)
    elif weekday == 6:
        return today + timedelta(days=1)
    elif weekday == 0:
        return today
    return today + timedelta(days=(7 - weekday))


def run_scrape(day: str):
    config = SCHEDULE[day]
    cats = config.get("categories")
    regions = config.get("regions")
    monday = get_monday_date()
    label_parts = []
    if cats:
        label_parts.append(f"分类: {', '.join(cats)}")
    if regions:
        label_parts.append(f"地区: {', '.join(regions)}")
    print(f"[{day}] 抓取 {' / '.join(label_parts) or '全部'}")
    print(f"  目标归档日期: {monday}")
    print(f"  今日预算剩余: {get_today_remaining()}/{DAILY_BUDGET}")

    df = scrape_categories(videos_per_tag=30, categories=cats, regions=regions)
    if df.empty:
        print("  未获取到数据")
        return None

    combined_path = archive_to_data(df, target_date=str(monday))
    print(f"  已归档 → {combined_path}")
    print(f"  今日已用: {get_today_usage()}/{DAILY_BUDGET}")
    return combined_path


def deploy_pages():
    print("\n[部署] 构建 GitHub Pages...")
    if SITE_DIR.exists():
        shutil.rmtree(SITE_DIR)
    SITE_DIR.mkdir()

    shutil.copy2("index.html", SITE_DIR / "index.html")
    shutil.copytree("data", SITE_DIR / "data")

    cmd = ["ghp-import", "-n", "-p", "-f", str(SITE_DIR)]
    print(f"  执行: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  部署失败: {result.stderr}")
        raise RuntimeError(f"ghp-import failed: {result.stderr}")
    print("  部署成功")

    shutil.rmtree(SITE_DIR, ignore_errors=True)


CAT_NAMES = {
    "gaming": "游戏", "comedy": "搞笑", "entertainment": "娱乐",
    "horror": "恐怖", "cute": "萌宠", "dance": "舞蹈", "food": "美食",
}
REGION_NAMES = {"ID": "印尼", "TH": "泰国", "PH": "菲律宾"}
FIELDS_TO_KEEP = ["d", "zh", "cat", "r", "p", "l", "cm", "sh", "h"]

CAT_PROMPTS = {
    "horror": (
        "聚焦恐怖内容设计灵感：哪些恐怖元素/题材正在爆发（jumpscare、灵异、都市传说、analog horror 等），"
        "有哪些值得微恐游戏借鉴的创意手法。"
    ),
    "gaming": (
        "聚焦游戏社区传播趋势：哪些游戏话题正在火爆，玩家在关注什么，"
        "有哪些可借鉴的游戏传播套路，微恐游戏可以如何切入这些游戏社区做推广。"
    ),
    "comedy": (
        "聚焦整活与玩梗：当前流行什么梗和搞笑套路，"
        "微恐游戏可以如何用幽默和创意的方式蹭这些梗做内容营销。"
    ),
    "entertainment": (
        "聚焦娱乐热点蹭流量：当前有什么热门影视/明星/综艺话题，"
        "微恐游戏可以如何蹭这些娱乐热点做内容营销。"
    ),
    "cute": (
        "聚焦反差营销：萌系内容中有什么爆款套路，"
        "微恐游戏可以如何用蹭这些内容手法制造传播。"
    ),
    "dance": (
        "聚焦挑战赛传播：当前流行什么舞蹈挑战和 viral 趋势。"
    ),
    "food": (
        "聚焦美食领域跨界：当前什么美食内容最火，"
        "微恐游戏可以如何跨界美食领域做创意传播。"
    ),
}

CATEGORY_PROMPT_TPL = """\
你是东南亚 TikTok 趋势分析师，服务对象是微恐向休闲游戏开发团队。
以下是本周{region_desc}「{cat_name}」分类的 top 视频数据。
字段：d=描述, zh=中文翻译, r=地区, p=播放, l=点赞, cm=评论, sh=分享, h=标签

{focus}

要求：
- 用 2-3 个要点总结，区分短期爆发趋势和持续流行内容
- 每个要点引用具体视频数据（播放/分享数）佐证
- 直接输出要点内容，不要写开头总结句（如"三个核心趋势："之类）
- 控制在 150 字以内，中文输出，不要用 markdown 标题

数据：
{data}"""

ALL_PROMPT_TPL = """\
你是东南亚 TikTok 趋势分析师，服务对象是微恐向休闲游戏开发团队。
以下是本周{region_desc} TikTok 各分类的 top 视频数据。
字段：d=描述, zh=中文翻译, cat=分类, r=地区, p=播放, l=点赞, cm=评论, sh=分享, h=标签

综合所有分类，提炼本周最值得微恐游戏团队关注的 2-3 个跨分类趋势。
重点关注：可用于游戏内容设计的恐怖元素 + 可用于游戏传播的热门梗/挑战。
区分短期爆发和持续流行。每个要点引用具体视频数据佐证。
直接输出要点内容，不要写开头总结句（如"三个核心趋势："之类）。
控制在 200 字以内，中文输出，不要用 markdown 标题。

数据：
{data}"""

SUMMARY_PROMPT_TPL = """\
以下是本周东南亚 TikTok 各分类的洞察摘要。请用 2 句话概括最值得关注的发现，面向微恐游戏开发团队。
控制在 80 字以内，中文，不要用 markdown。

{insights}"""


def _top_by_region(records: list[dict], n_per_region: int) -> list[dict]:
    by_region = {}
    for r in records:
        by_region.setdefault(r.get("r", "??"), []).append(r)
    result = []
    for region in ["ID", "TH", "PH"]:
        region_items = by_region.get(region, [])
        top = sorted(region_items, key=lambda x: (x.get("sh", 0) or 0), reverse=True)[:n_per_region]
        result.extend(top)
    return result


def _slim(records: list[dict]) -> str:
    slim = [{k: r.get(k) for k in FIELDS_TO_KEEP if r.get(k)} for r in records]
    return json.dumps(slim, ensure_ascii=False, indent=1)


def _llm_call(prompt: str, max_tokens: int = 512) -> str:
    import anthropic
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model="claude-haiku",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()


MIN_VIDEOS_FOR_INSIGHT = 5
REGIONS_WITH_ALL = {"all": "全东南亚（印尼/泰国/菲律宾）", "ID": "印尼", "TH": "泰国", "PH": "菲律宾", "global": "全球"}


def _top_sorted(records: list[dict], n: int) -> list[dict]:
    return sorted(records, key=lambda x: (x.get("sh", 0) or 0), reverse=True)[:n]


def generate_insights(records: list[dict], target_date: str) -> dict:
    print("\n[洞察] 生成 地区×分类 洞察...")
    insights = {"date": target_date}
    call_count = 0

    for region_id, region_desc in REGIONS_WITH_ALL.items():
        region_data = {}
        if region_id == "all":
            pool = [r for r in records if r.get("cat") != "global_trending"]
        else:
            pool = [r for r in records if r.get("r") == region_id]

        if not pool:
            print(f"  [{region_desc}] 无数据，跳过")
            continue

        # 各分类洞察
        for cat_id, cat_name in CAT_NAMES.items():
            cat_records = [r for r in pool if r.get("cat") == cat_id]
            if len(cat_records) < MIN_VIDEOS_FOR_INSIGHT:
                continue
            if region_id == "all":
                sample = _top_by_region(cat_records, 7)
            else:
                sample = _top_sorted(cat_records, 20)
            prompt = CATEGORY_PROMPT_TPL.format(
                region_desc=region_desc,
                cat_name=cat_name,
                focus=CAT_PROMPTS.get(cat_id, ""),
                data=_slim(sample),
            )
            try:
                region_data[cat_id] = _llm_call(prompt)
                call_count += 1
                print(f"  [{region_desc}] {cat_name}: 完成")
            except Exception as e:
                print(f"  [{region_desc}] {cat_name}: 失败 {e}")

        # All Tags 整体洞察
        if region_id == "all":
            sample = _top_by_region(pool, 10)
        else:
            sample = _top_sorted(pool, 30)
        try:
            region_data["all"] = _llm_call(ALL_PROMPT_TPL.format(
                region_desc=region_desc,
                data=_slim(sample),
            ))
            call_count += 1
            print(f"  [{region_desc}] 整体: 完成")
        except Exception as e:
            print(f"  [{region_desc}] 整体: 失败 {e}")

        insights[region_id] = region_data

    # 钉钉摘要（基于 all 维度的各分类洞察）
    print("  钉钉摘要...")
    all_insights = insights.get("all", {})
    cat_text = "\n".join(f"[{CAT_NAMES.get(k,k)}] {v}" for k, v in all_insights.items() if k != "all" and v)
    try:
        insights["summary"] = _llm_call(SUMMARY_PROMPT_TPL.format(insights=cat_text))
        call_count += 1
        print("  摘要: 完成")
    except Exception as e:
        print(f"  摘要: 失败 {e}")
        insights["summary"] = ""

    out_path = DATA_DIR / target_date / "insights.json"
    out_path.write_text(json.dumps(insights, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  已保存 → {out_path} (共 {call_count} 次 LLM 调用)")
    return insights


DINGTALK_PROMPT_TPL = """\
你是微恐游戏团队的东南亚 TikTok 趋势分析师，需要撰写钉钉群周报推送的正文部分。

注意：标题、日期、视频总数已由系统自动生成，你只需要写洞察内容。
绝对不要在开头重复写标题、日期、数据概览等信息，直接从洞察内容开始。

严格要求：
- 总字数 500-600 字，绝对不能超过 600 字，钉钉会截断
- 每个要点的第一句是总结性结论，用 <font color="#FF6600">**总结句**</font> 高亮，后面的数据佐证用普通文字
- 分「恐怖内容灵感」和「传播策略参考」两个板块，用 ### 【板块名】 作为标题（如 ### 【恐怖内容灵感】）
- 每个板块各写 2 个要点，共 4 个要点
- 每个要点开头用不同的 emoji 做视觉分隔（如 👻 🎮 🔥 💡）
- 每个要点 1-2 句话，必须附具体数据（播放/分享数）
- 最后一行写行动建议，只输出建议内容本身，不要加前缀标题，系统会自动加格式

以下是各分类的洞察数据供你参考：

各分类洞察：
{cat_insights}

整体洞察：
{all_insight}"""


def _load_dingtalk_bots() -> list[dict]:
    if not DINGTALK_BOTS_FILE.exists():
        return []
    bots = json.loads(DINGTALK_BOTS_FILE.read_text(encoding="utf-8"))
    return [b for b in bots if b.get("enabled", True)]


def notify_dingtalk(monday_date: str, records: list[dict], insights: dict):
    bots = _load_dingtalk_bots()
    if not bots:
        print("\n[通知] 跳过：dingtalk_bots.json 中无已启用的机器人")
        return

    total = len(records)

    cat_counts = {}
    region_counts = {}
    for r in records:
        cat = r.get("cat", "unknown")
        region = r.get("r", "??")
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
        region_counts[region] = region_counts.get(region, 0) + 1

    cat_stats = " / ".join(f"{CAT_NAMES.get(c, c)} {n}条" for c, n in sorted(cat_counts.items(), key=lambda x: -x[1]))
    region_stats = " / ".join(f"{REGION_NAMES.get(r, r)} {n}" for r, n in sorted(region_counts.items(), key=lambda x: -x[1]))

    # 钉钉推送基于 all 维度的洞察
    all_insights = insights.get("all", {})
    cat_insights = "\n\n".join(
        f"【{CAT_NAMES.get(k, k)}】\n{v}"
        for k, v in all_insights.items()
        if k != "all" and v
    )

    print("\n[通知] 调用 LLM 生成钉钉推送文案...")
    try:
        body = _llm_call(DINGTALK_PROMPT_TPL.format(
            cat_insights=cat_insights,
            all_insight=all_insights.get("all", ""),
        ), max_tokens=1024)
    except Exception as e:
        print(f"  文案生成失败: {e}")
        body = insights.get("summary", "本周洞察已生成，请查看完整报告。")

    # 拆分正文和行动建议（LLM 输出的最后一行）
    lines = body.strip().split("\n")
    action_line = lines[-1].strip() if lines else ""
    for prefix in ["💡", "行动建议：", "行动建议:", "**行动建议**：", "**行动建议**:"]:
        action_line = action_line.lstrip(prefix).strip()
    main_body = "\n".join(lines[:-1]).strip() if len(lines) > 1 else body
    while main_body.endswith("---"):
        main_body = main_body[:-3].strip()

    text = (
        f"## 📊 东南亚 TikTok 周报 · {monday_date}\n\n"
        f"本周监测：**{total}** 条视频 | {region_stats}\n\n"
        f"---\n\n"
        f"{main_body}\n\n"
        f"---\n\n"
        f"📌 **本周行动建议**：{action_line}\n\n"
        f"---\n\n"
        f"📊 [【传送门】本周TikTok热点视频>>>]({PAGES_URL})"
    )
    payload = {
        "msgtype": "markdown",
        "markdown": {"title": f"🔥 TikTok 东南亚周报 {monday_date}", "text": text},
    }

    print(f"\n[通知] 发送钉钉消息到 {len(bots)} 个机器人...")
    for bot in bots:
        name = bot.get("name", "未命名")
        webhook = bot.get("webhook", "")
        if not webhook:
            print(f"  [{name}] 跳过：无 webhook")
            continue
        try:
            resp = httpx.post(webhook, json=payload, timeout=10)
            data = resp.json()
            if data.get("errcode") == 0:
                print(f"  [{name}] 发送成功")
            else:
                print(f"  [{name}] 失败: {data}")
        except Exception as e:
            print(f"  [{name}] 异常: {e}")


def run_monday():
    combined_path = run_scrape("monday")

    monday = str(get_monday_date())
    data_file = DATA_DIR / monday / "combined.json"

    if data_file.exists():
        print(f"\n[翻译] 开始翻译 {data_file}...")
        try:
            from translate_data import translate_file
            translate_file(data_file)
        except Exception as e:
            print(f"  翻译失败（不影响数据）: {e}")

        records = json.loads(data_file.read_text(encoding="utf-8"))
        insights = generate_insights(records, monday)

        deploy_pages()
        notify_dingtalk(monday, records, insights)
    else:
        print(f"\n[!] 未找到 {data_file}，跳过部署和通知")


def main():
    if not API_TOKEN or API_TOKEN == "your_token_here":
        print("错误: 请先在 .env 文件中设置 TIKHUB_API_TOKEN")
        return

    LOG_DIR.mkdir(exist_ok=True)

    if len(sys.argv) < 2:
        print(__doc__)
        return

    day = sys.argv[1].lower()
    if day not in SCHEDULE:
        print(f"不支持的参数: {day}")
        print(f"可选: {list(SCHEDULE.keys())}")
        return

    if day == "monday":
        run_monday()
    else:
        run_scrape(day)

    print("\n完成。")


if __name__ == "__main__":
    main()
