"""
快速调用脚本 v2
用法:
    python3 quick_fetch.py trends ID vv         # 印尼按播放量排行
    python3 quick_fetch.py trends TH like       # 泰国按点赞排行
    python3 quick_fetch.py trends PH comment    # 菲律宾按评论排行
    python3 quick_fetch.py category gaming ID   # 印尼游戏标签视频
    python3 quick_fetch.py category comedy TH   # 泰国搞笑标签视频
    python3 quick_fetch.py category entertainment PH  # 菲律宾娱乐标签
    python3 quick_fetch.py budget               # 查看今日预算使用情况
    python3 quick_fetch.py full                 # 执行完整每日抓取
"""

import sys
from datetime import date

from scraper import (
    API_TOKEN,
    DAILY_BUDGET,
    REGIONS,
    TREND_ORDER_FIELDS,
    CATEGORY_TAGS,
    OUTPUT_DIR,
    get_today_usage,
    get_today_remaining,
    fetch_popular_trends,
    fetch_tag_posts,
    resolve_tag_ids,
    parse_trend_video,
    parse_tag_video,
    save_results,
    print_summary,
    check_budget,
    main as full_main,
)
import pandas as pd


def cmd_trends(region: str, order_by: str, limit: int = 50):
    if order_by not in TREND_ORDER_FIELDS:
        print(f"排序方式不支持: {order_by}, 可选: {list(TREND_ORDER_FIELDS.keys())}")
        return
    print(f"拉取 {REGIONS[region]} 7日内按{TREND_ORDER_FIELDS[order_by]}排行 (limit={limit})...")
    data = fetch_popular_trends(country_code=region, order_by=order_by, period=7, limit=limit)
    videos = data.get("data", {}).get("data", {}).get("videos", [])
    if not videos:
        videos = data.get("data", {}).get("videos", [])
    parsed = [parse_trend_video(v, region, order_by) for v in videos]
    df = pd.DataFrame(parsed)
    if not df.empty:
        df = df.drop_duplicates(subset=["video_id"], keep="first")
    print(f"获取到 {len(df)} 条视频")
    print_summary(df)
    save_results(df, prefix=f"quick_trends_{region}_{order_by}")


def cmd_category(category: str, region: str, count: int = 30):
    if category not in CATEGORY_TAGS:
        print(f"分类不支持: {category}, 可选: {list(CATEGORY_TAGS.keys())}")
        return
    if region not in REGIONS:
        print(f"地区不支持: {region}, 可选: {list(REGIONS.keys())}")
        return

    cat_info = CATEGORY_TAGS[category]
    tags = cat_info["tags"].get(region, [])
    print(f"拉取 {REGIONS[region]} / {cat_info['name']} (标签: {tags})...")

    tag_map = resolve_tag_ids(tags)
    all_videos = []
    for tag_name, tag_id in tag_map.items():
        if not check_budget():
            print(f"  预算不足，停止")
            break
        try:
            data = fetch_tag_posts(challenge_id=tag_id, count=count)
            items = data.get("data", {}).get("itemList", [])
            print(f"  #{tag_name}: {len(items)} 条")
            for item in items:
                all_videos.append(parse_tag_video(item, region, tag_name, category))
        except Exception as e:
            print(f"  #{tag_name}: 错误 {e}")

    df = pd.DataFrame(all_videos)
    if not df.empty:
        df = df.drop_duplicates(subset=["video_id"], keep="first")
    print(f"\n获取到 {len(df)} 条独立视频")
    print_summary(df)
    save_results(df, prefix=f"quick_{category}_{region}")


def cmd_budget():
    used = get_today_usage()
    remaining = get_today_remaining()
    print(f"日期: {date.today()}")
    print(f"每日预算: {DAILY_BUDGET} 次")
    print(f"今日已用: {used} 次")
    print(f"今日剩余: {remaining} 次")
    print()
    if remaining >= 39:
        print("状态: 可执行完整每日抓取 (39次)")
    elif remaining >= 12:
        print("状态: 可执行 Part 1 热门排行 (12次)")
    elif remaining > 0:
        print("状态: 余量较少, 建议单次快速查询")
    else:
        print("状态: 今日预算已用完, 明天再来")


def main():
    if not API_TOKEN or API_TOKEN == "your_token_here":
        print("错误: 请先在 .env 文件中设置 TIKHUB_API_TOKEN")
        return

    if len(sys.argv) < 2:
        print(__doc__)
        return

    action = sys.argv[1]

    if action == "trends":
        if len(sys.argv) < 4:
            print("用法: python3 quick_fetch.py trends <region> <order_by>")
            print(f"  region: {list(REGIONS.keys())}")
            print(f"  order_by: {list(TREND_ORDER_FIELDS.keys())}")
            return
        region = sys.argv[2].upper()
        order_by = sys.argv[3].lower()
        limit = int(sys.argv[4]) if len(sys.argv) > 4 else 50
        if region not in REGIONS:
            print(f"地区不支持: {region}")
            return
        cmd_trends(region, order_by, limit)

    elif action == "category":
        if len(sys.argv) < 4:
            print("用法: python3 quick_fetch.py category <category> <region>")
            print(f"  category: {list(CATEGORY_TAGS.keys())}")
            print(f"  region: {list(REGIONS.keys())}")
            return
        category = sys.argv[2].lower()
        region = sys.argv[3].upper()
        count = int(sys.argv[4]) if len(sys.argv) > 4 else 30
        cmd_category(category, region, count)

    elif action == "budget":
        cmd_budget()

    elif action == "full":
        full_main()

    else:
        print(f"不支持的操作: {action}")
        print(__doc__)


if __name__ == "__main__":
    main()
