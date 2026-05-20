"""
TikTok 东南亚热点短视频抓取工具 v2
每日 50 次 API 请求预算，覆盖印尼/泰国/菲律宾
- Part 1: 按播放/点赞/评论/转发排行拉取 7 日热门视频 (12次)
- Part 2: 按分类标签拉取游戏/搞笑/娱乐视频 (27次)
"""

import os
import json
import time
import hashlib
from datetime import datetime, date
from pathlib import Path

import httpx
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api.tikhub.io"
API_TOKEN = os.getenv("TIKHUB_API_TOKEN", "")
DAILY_BUDGET = 500

REGIONS = {
    "ID": "印尼 Indonesia",
    "TH": "泰国 Thailand",
    "PH": "菲律宾 Philippines",
}

TREND_ORDER_FIELDS = {
    "vv": "播放量",
    "like": "点赞",
    "comment": "评论",
    "repost": "转发",
}

CATEGORY_TAGS = {
    "gaming": {
        "name": "游戏",
        "tags": {
            "ID": ["mobilelegends", "freefire", "genshinimpact", "gaming", "gameandroid", "mlbb", "mobilegaming", "onlinegame"],
            "TH": ["rovthailand", "เกม", "gamingthailand", "rov", "gaming", "เกมมือถือ", "gameth"],
            "PH": ["mlbbph", "valorantph", "gamingph", "mlbb", "gaming", "genshinimpact", "freefire", "gamingphilippines"],
        },
    },
    "comedy": {
        "name": "沙雕搞笑",
        "tags": {
            "ID": ["komedi", "ngakak", "videolucu", "lucu", "kocak", "humor", "meme"],
            "TH": ["ตลก", "ตลกไทย", "comedythailand", "คลิปตลก", "ฮาๆ", "สายฮา"],
            "PH": ["pinoycomedy", "pinoyfunny", "hugot", "patama", "pinoytiktok", "realtalk"],
        },
    },
    "entertainment": {
        "name": "娱乐(明星/剧集/电影)",
        "tags": {
            "ID": ["drakor", "sinetron", "gosip", "kdrama", "gossip", "artis", "dramakorea"],
            "TH": ["ละคร", "ดารา", "thaidrama", "ละครไทย", "thaibl", "blseries", "บันเทิง"],
            "PH": ["kdramaph", "showbiz", "chismis", "kdrama", "chisme", "opm"],
        },
    },
    "horror": {
        "name": "恐怖/灵异",
        "tags": {
            "ID": ["horor", "pocong", "hororindonesia", "setan", "jumpscare", "kuntilanak", "misteri", "analoghorror"],
            "TH": ["หนังผี", "สยองขวัญ", "ผีไทย", "ผี", "เรื่องผี", "ความลึกลับ", "analoghorror"],
            "PH": ["pinoyhorror", "aswang", "multo", "engkanto", "mangkukulam", "analoghorror"],
        },
    },
    "cute": {
        "name": "萌娃/萌宠",
        "tags": {
            "ID": ["bayilucu", "anaklucu", "kucinglucu", "hewanlucu", "kucing", "bayi", "cute"],
            "TH": ["เด็กน่ารัก", "แมวน่ารัก", "น่ารัก", "สัตว์เลี้ยง", "ทารก", "หมาน่ารัก"],
            "PH": ["cutebaby", "cuteanimals", "pinoycat", "babies", "pinoypets", "cutepets"],
        },
    },
    "dance": {
        "name": "舞蹈/挑战",
        "tags": {
            "ID": ["dance", "challenge", "tiktokdance", "joget", "danceindonesia", "viral"],
            "TH": ["เต้น", "dancechallenge", "challenge", "เต้นออนไลน์", "tiktokthai"],
            "PH": ["dancechallenge", "pinoydance", "tiktokdance", "dance", "challenge"],
        },
    },
    "food": {
        "name": "美食",
        "tags": {
            "ID": ["masak", "kuliner", "foodindonesia", "masakanindo", "resepmasak", "makanan"],
            "TH": ["อาหาร", "อาหารไทย", "ทำอาหาร", "เมนูอร่อย", "อาหารอร่อย", "ของกิน"],
            "PH": ["foodph", "filipinofood", "pinoyrecipe", "lutongbahay", "kakainin"],
        },
    },
}

# ─── Paths ──────────────────────────────────────────────────────────────────

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)
CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)
TAG_CACHE_FILE = CACHE_DIR / "tag_ids.json"
BUDGET_FILE = CACHE_DIR / "budget.json"
VIDEO_CACHE_TTL = 6 * 3600


# ─── Budget Tracker ─────────────────────────────────────────────────────────

def _load_budget() -> dict:
    if BUDGET_FILE.exists():
        return json.loads(BUDGET_FILE.read_text(encoding="utf-8"))
    return {}


def _save_budget(data: dict):
    BUDGET_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_today_usage() -> int:
    budget = _load_budget()
    return budget.get(str(date.today()), 0)


def get_today_remaining() -> int:
    return DAILY_BUDGET - get_today_usage()


def _increment_budget():
    budget = _load_budget()
    today = str(date.today())
    budget[today] = budget.get(today, 0) + 1
    _save_budget(budget)


def check_budget(needed: int = 1) -> bool:
    remaining = get_today_remaining()
    if remaining < needed:
        print(f"  [!] 预算不足: 今日剩余 {remaining} 次, 需要 {needed} 次")
        return False
    return True


# ─── Cache ───────────────────────────────────────────────────────────────────

def _load_tag_cache() -> dict:
    if TAG_CACHE_FILE.exists():
        return json.loads(TAG_CACHE_FILE.read_text(encoding="utf-8"))
    return {}


def _save_tag_cache(cache: dict):
    TAG_CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def _response_cache_path(endpoint: str, params: dict) -> Path:
    key = f"{endpoint}|{json.dumps(params, sort_keys=True)}"
    h = hashlib.md5(key.encode()).hexdigest()
    return CACHE_DIR / f"resp_{h}.json"


def _get_cached_response(endpoint: str, params: dict) -> dict | None:
    path = _response_cache_path(endpoint, params)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    cached_at = data.get("_cached_at", 0)
    if time.time() - cached_at > VIDEO_CACHE_TTL:
        path.unlink(missing_ok=True)
        return None
    return data.get("response")


def _set_cached_response(endpoint: str, params: dict, response: dict):
    path = _response_cache_path(endpoint, params)
    payload = {"_cached_at": time.time(), "_endpoint": endpoint, "_params": params, "response": response}
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


# ─── API Core ────────────────────────────────────────────────────────────────

def get_headers():
    return {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json",
    }


def api_get(endpoint: str, params: dict = None, use_cache: bool = True) -> dict:
    params = params or {}

    if use_cache:
        cached = _get_cached_response(endpoint, params)
        if cached is not None:
            return cached

    if not check_budget():
        raise RuntimeError("今日 API 预算已用完")

    url = f"{BASE_URL}{endpoint}"
    with httpx.Client(timeout=30) as client:
        resp = client.get(url, headers=get_headers(), params=params)
        if resp.status_code == 402:
            print("  [!] API 余额不足 (402 Payment Required)，请充值后重试")
            raise httpx.HTTPStatusError("402 Payment Required", request=resp.request, response=resp)
        resp.raise_for_status()
        data = resp.json()

    _increment_budget()

    if use_cache:
        _set_cached_response(endpoint, params, data)
    return data


# ─── API Functions ───────────────────────────────────────────────────────────

def fetch_popular_trends(country_code: str, order_by: str = "vv",
                         period: int = 7, limit: int = 50, page: int = 1) -> dict:
    """获取指定国家指定时间段内按指标排序的热门视频"""
    return api_get("/api/v1/tiktok/ads/get_popular_trends", {
        "country_code": country_code,
        "order_by": order_by,
        "period": period,
        "limit": limit,
        "page": page,
    })


def fetch_hashtag_list(country_code: str, period: int = 7,
                       limit: int = 20, sort_by: str = "popular") -> dict:
    """获取热门标签排行榜"""
    return api_get("/api/v1/tiktok/ads/get_hashtag_list", {
        "country_code": country_code,
        "period": period,
        "limit": limit,
        "sort_by": sort_by,
    })


def fetch_tag_detail(tag_name: str) -> dict:
    """获取话题标签详情（含 challenge ID）"""
    return api_get("/api/v1/tiktok/web/fetch_tag_detail", {"tag_name": tag_name})


def fetch_tag_posts(challenge_id: str, count: int = 30, cursor: int = 0) -> dict:
    """获取话题标签下的视频"""
    return api_get("/api/v1/tiktok/web/fetch_tag_post", {
        "challengeID": challenge_id,
        "count": count,
        "cursor": cursor,
    })


# ─── Parsers ─────────────────────────────────────────────────────────────────

def parse_trend_video(item: dict, country_code: str, order_by: str) -> dict:
    """解析 get_popular_trends 返回的视频对象"""
    return {
        "video_id": str(item.get("id", item.get("item_id", ""))),
        "desc": item.get("title", ""),
        "create_time": "",
        "author_nickname": "",
        "author_unique_id": "",
        "play_count": 0,
        "like_count": 0,
        "comment_count": 0,
        "share_count": 0,
        "duration": item.get("duration", 0),
        "cover_url": item.get("cover", ""),
        "play_url": item.get("item_url", ""),
        "music_title": "",
        "hashtags": "",
        "region": country_code,
        "source": f"trends:{order_by}",
        "category": "trending",
        "tiktok_url": item.get("item_url", ""),
    }


def parse_tag_video(item: dict, region: str, tag_name: str, category: str) -> dict:
    """解析 fetch_tag_post 返回的视频对象"""
    video = item.get("video", {})
    author = item.get("author", {})
    stats = item.get("stats", item.get("statistics", {}))
    music = item.get("music", {})
    challenges = item.get("challenges", [])

    cover_url = ""
    if isinstance(video.get("cover"), str):
        cover_url = video["cover"]
    elif isinstance(video.get("origin_cover"), dict):
        urls = video["origin_cover"].get("url_list", [])
        cover_url = urls[0] if urls else ""

    create_time = item.get("createTime", item.get("create_time", 0))
    if isinstance(create_time, int) and create_time > 0:
        create_time_str = datetime.fromtimestamp(create_time).strftime("%Y-%m-%d %H:%M:%S")
    else:
        create_time_str = str(create_time)

    vid = str(item.get("id", item.get("aweme_id", "")))
    author_uid = author.get("uniqueId", author.get("unique_id", ""))
    tiktok_url = f"https://www.tiktok.com/@{author_uid}/video/{vid}" if author_uid and vid else ""

    return {
        "video_id": vid,
        "desc": item.get("desc", ""),
        "create_time": create_time_str,
        "author_nickname": author.get("nickname", ""),
        "author_unique_id": author_uid,
        "play_count": stats.get("playCount", stats.get("play_count", 0)),
        "like_count": stats.get("diggCount", stats.get("digg_count", 0)),
        "comment_count": stats.get("commentCount", stats.get("comment_count", 0)),
        "share_count": stats.get("shareCount", stats.get("share_count", 0)),
        "duration": video.get("duration", 0),
        "cover_url": cover_url,
        "play_url": "",
        "music_title": music.get("title", ""),
        "hashtags": ", ".join(c.get("title", "") for c in challenges),
        "region": region,
        "source": f"tag:{tag_name}",
        "category": category,
        "tiktok_url": tiktok_url,
    }


# ─── Tag ID Resolver ─────────────────────────────────────────────────────────

def resolve_tag_ids(tags: list[str]) -> dict[str, str]:
    """批量解析话题标签名称到 challenge ID（优先读本地缓存）"""
    tag_cache = _load_tag_cache()
    tag_map = {}
    tags_to_fetch = []

    for tag in tags:
        if tag in tag_cache:
            tag_map[tag] = tag_cache[tag]
            print(f"    #{tag} -> ID: {tag_cache[tag]} [cached]")
        else:
            tags_to_fetch.append(tag)

    for tag in tags_to_fetch:
        if not check_budget():
            print(f"    #{tag} -> 跳过 (预算不足)")
            continue
        try:
            data = fetch_tag_detail(tag)
            challenge_info = data.get("data", {}).get("challengeInfo", {}).get("challenge", {})
            cid = challenge_info.get("id", "")
            if cid:
                tag_map[tag] = str(cid)
                tag_cache[tag] = str(cid)
                print(f"    #{tag} -> ID: {cid} [fetched]")
        except Exception as e:
            print(f"    #{tag} -> 错误: {e}")
        time.sleep(0.5)

    _save_tag_cache(tag_cache)
    return tag_map


# ─── Scrape Part 1: Trends ───────────────────────────────────────────────────

def scrape_trends(period: int = 7, limit: int = 50) -> pd.DataFrame:
    """Part 1: 拉取3国×4维度的热门趋势视频排行"""
    all_videos = []
    regions = list(REGIONS.keys())
    order_fields = list(TREND_ORDER_FIELDS.keys())

    total_calls = len(regions) * len(order_fields)
    print(f"\n[Part 1] 热门趋势排行 (预计 {total_calls} 次请求)")
    print(f"  地区: {', '.join(REGIONS.values())}")
    print(f"  排序: {', '.join(TREND_ORDER_FIELDS.values())}")
    print(f"  时间范围: {period} 天, 每次取 {limit} 条")

    for region in regions:
        for order_by in order_fields:
            if not check_budget():
                break
            try:
                data = fetch_popular_trends(
                    country_code=region, order_by=order_by,
                    period=period, limit=limit,
                )
                videos = data.get("data", {}).get("data", {}).get("videos", [])
                if not videos:
                    videos = data.get("data", {}).get("videos", [])
                print(f"  {REGIONS[region][:4]} / {TREND_ORDER_FIELDS[order_by]}: {len(videos)} 条")
                for item in videos:
                    all_videos.append(parse_trend_video(item, region, order_by))
            except RuntimeError:
                print("  预算已用完，停止拉取")
                break
            except Exception as e:
                print(f"  {REGIONS[region][:4]} / {TREND_ORDER_FIELDS[order_by]}: 错误 {e}")
            time.sleep(0.8)

    df = pd.DataFrame(all_videos)
    if not df.empty:
        df = df.drop_duplicates(subset=["video_id"], keep="first")
        print(f"  合计: {len(df)} 条独立视频 (去重后)")
    return df


# ─── Scrape Part 2: Category Tags ────────────────────────────────────────────

def scrape_categories(videos_per_tag: int = 30) -> pd.DataFrame:
    """Part 2: 按分类标签拉取游戏/搞笑/娱乐视频"""
    all_tags = []
    for cat_id, cat_info in CATEGORY_TAGS.items():
        for region, tags in cat_info["tags"].items():
            all_tags.extend(tags)

    unique_tags = list(dict.fromkeys(all_tags))
    total_calls = len(unique_tags)
    print(f"\n[Part 2] 分类标签视频 (预计 {total_calls} 次请求, 不含标签解析)")
    print(f"  分类: {', '.join(c['name'] for c in CATEGORY_TAGS.values())}")

    # Resolve all tag IDs first
    print(f"\n  解析标签 ID...")
    tag_map = resolve_tag_ids(unique_tags)

    all_videos = []
    for cat_id, cat_info in CATEGORY_TAGS.items():
        cat_name = cat_info["name"]
        print(f"\n  ── {cat_name} ──")
        for region, tags in cat_info["tags"].items():
            for tag_name in tags:
                tag_id = tag_map.get(tag_name)
                if not tag_id:
                    print(f"    #{tag_name} [{region}]: 无 ID, 跳过")
                    continue
                if not check_budget():
                    print(f"    预算不足，停止")
                    break
                try:
                    data = fetch_tag_posts(challenge_id=tag_id, count=videos_per_tag)
                    items = data.get("data", {}).get("itemList", [])
                    print(f"    #{tag_name} [{region}]: {len(items)} 条")
                    for item in items:
                        all_videos.append(parse_tag_video(item, region, tag_name, cat_id))
                except RuntimeError:
                    print("    预算已用完")
                    break
                except Exception as e:
                    print(f"    #{tag_name} [{region}]: 错误 {e}")
                time.sleep(0.8)

    df = pd.DataFrame(all_videos)
    if not df.empty:
        df = df.drop_duplicates(subset=["video_id"], keep="first")
        print(f"\n  合计: {len(df)} 条独立视频 (去重后)")
    return df


# ─── Archive to data/<date>/ ──────────────────────────────────────────────────

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

# 列名映射：DataFrame 长列名 → combined.json 短字段名
COLUMN_MAP = {
    "video_id": "id", "desc": "d", "create_time": "t",
    "author_nickname": "an", "author_unique_id": "au",
    "play_count": "p", "like_count": "l", "comment_count": "cm",
    "share_count": "sh", "duration": "dur", "cover_url": "cov",
    "tiktok_url": "url", "hashtags": "h", "region": "r", "category": "cat",
}
DROP_COLS = {"play_url", "music_title", "source"}


def archive_to_data(df: pd.DataFrame) -> Path:
    """将 DataFrame 归档到 data/<today>/combined.json 并更新 dates.json，合并已有数据"""
    today = str(date.today())
    date_dir = DATA_DIR / today
    date_dir.mkdir(exist_ok=True)

    # 重命名列、去掉不需要的列
    df2 = df.drop(columns=[c for c in DROP_COLS if c in df.columns], errors="ignore")
    df2 = df2.rename(columns={k: v for k, v in COLUMN_MAP.items() if k in df2.columns})

    new_records = json.loads(df2.to_json(orient="records", force_ascii=False))

    # 合并已有数据（保留 global 等之前抓取的数据）
    combined_path = date_dir / "combined.json"
    if combined_path.exists():
        existing = json.loads(combined_path.read_text(encoding="utf-8"))
        new_ids = {r.get("id") for r in new_records}
        kept = [r for r in existing if r.get("id") not in new_ids]
        new_records = new_records + kept
        print(f"\n  合并已有数据: 保留 {len(kept)} 条旧条目")

    combined_path.write_text(json.dumps(new_records, ensure_ascii=False), encoding="utf-8")
    print(f"  已归档 {len(new_records)} 条 → {combined_path}")

    # 更新 dates.json
    dates_path = DATA_DIR / "dates.json"
    dates = json.loads(dates_path.read_text(encoding="utf-8")) if dates_path.exists() else []
    if today not in dates:
        dates = [today] + dates
        dates_path.write_text(json.dumps(dates, ensure_ascii=False), encoding="utf-8")
        print(f"  dates.json 已更新: {dates}")

    return combined_path


def save_results(df: pd.DataFrame, prefix: str = "data"):
    if df.empty:
        print("  没有数据可保存")
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = OUTPUT_DIR / f"{prefix}_{timestamp}.json"
    csv_path = OUTPUT_DIR / f"{prefix}_{timestamp}.csv"

    df.to_json(json_path, orient="records", force_ascii=False, indent=2)
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    print(f"  已保存 {len(df)} 条: {json_path}")
    return json_path


def print_summary(df: pd.DataFrame):
    if df.empty:
        return

    print(f"\n{'='*60}")
    print(f"数据摘要 (共 {len(df)} 条视频)")
    print(f"{'='*60}")

    if "region" in df.columns:
        print(f"\n  按地区:")
        for region, count in df["region"].value_counts().items():
            print(f"    {REGIONS.get(region, region)}: {count} 条")

    if "category" in df.columns:
        print(f"\n  按分类:")
        cat_names = {"trending": "热门排行", "gaming": "游戏", "comedy": "沙雕搞笑",
                     "entertainment": "娱乐", "horror": "恐怖/灵异",
                     "cute": "萌娃/萌宠", "dance": "舞蹈/挑战", "food": "美食"}
        for cat, count in df["category"].value_counts().items():
            print(f"    {cat_names.get(cat, cat)}: {count} 条")

    if "play_count" in df.columns:
        numeric = df[pd.to_numeric(df["play_count"], errors="coerce") > 0].copy()
        if not numeric.empty:
            numeric["play_count"] = pd.to_numeric(numeric["play_count"])
            top = numeric.nlargest(5, "play_count")
            print(f"\n  Top 5 播放量:")
            for _, row in top.iterrows():
                desc = str(row["desc"])[:45] + "..." if len(str(row["desc"])) > 45 else str(row["desc"])
                print(f"    [{row['region']}] {desc}")
                print(f"         播放: {int(row['play_count']):,}")


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    if not API_TOKEN or API_TOKEN == "your_token_here":
        print("错误: 请先在 .env 文件中设置 TIKHUB_API_TOKEN")
        return

    print("=" * 60)
    print("TikTok SEA 每日热点抓取 v2")
    print(f"目标: {', '.join(REGIONS.values())}")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"今日预算: {get_today_remaining()}/{DAILY_BUDGET} 剩余")
    print("=" * 60)

    if get_today_remaining() < 10:
        print("\n[!] 今日预算不足 10 次，建议明天再运行")
        return

    # Part 1: 热门趋势排行
    df_trends = scrape_trends(period=7, limit=50)
    if not df_trends.empty:
        save_results(df_trends, prefix="part1_trends")

    # Part 2: 分类标签
    df_cats = scrape_categories(videos_per_tag=30)
    if not df_cats.empty:
        save_results(df_cats, prefix="part2_categories")

    # 合并
    frames = [df for df in [df_trends, df_cats] if not df.empty]
    if frames:
        df_all = pd.concat(frames, ignore_index=True)
        df_all = df_all.drop_duplicates(subset=["video_id"], keep="first")
        save_results(df_all, prefix="daily_combined")
        print_summary(df_all)

        # 归档到 data/<date>/combined.json
        combined_path = archive_to_data(df_all)

        # 自动翻译
        print("\n[翻译] 开始对新数据生成中文说明...")
        try:
            from translate_data import translate_file
            translate_file(combined_path)
        except Exception as e:
            print(f"  [!] 翻译失败（不影响数据）: {e}")

    print(f"\n今日已用: {get_today_usage()}/{DAILY_BUDGET} 次请求")


if __name__ == "__main__":
    main()
