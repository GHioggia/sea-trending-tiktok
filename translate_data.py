"""
为 data/<date>/combined.json 中的视频描述生成中文翻译
使用 Claude API 批量翻译，无每日额度限制

用法:
    python3 translate_data.py              # 翻译所有日期
    python3 translate_data.py 2026-05-19  # 只翻译指定日期
"""

import json
import sys
import time
from pathlib import Path

import anthropic

BATCH_SIZE = 30   # 每次 API 调用翻译的条数
SAVE_INTERVAL = 3 # 每多少批次保存一次


def clean_desc(text: str) -> str:
    words = [w for w in text.split() if not w.startswith("#")]
    return " ".join(words).strip()


def translate_batch(items: list[dict], client: anthropic.Anthropic) -> list[str]:
    """批量翻译，返回与 items 等长的中文译文列表"""
    lines = []
    for i, item in enumerate(items, 1):
        clean = clean_desc(item.get("d", ""))
        lines.append(f"{i}. {clean}")

    prompt = (
        "以下是东南亚 TikTok 视频的标题（印尼语/泰语/菲律宾语/英语混合）。"
        "请将每条翻译成简洁的中文，保留游戏名/人名等专有名词的常用译法，"
        "去掉表情符号。按原编号逐行输出，每行格式为「编号. 译文」，不要解释。\n\n"
        + "\n".join(lines)
    )

    msg = client.messages.create(
        model="claude-haiku",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    result_text = msg.content[0].text.strip()
    results = [""] * len(items)
    for line in result_text.splitlines():
        line = line.strip()
        if not line:
            continue
        dot = line.find(".")
        if dot > 0 and line[:dot].isdigit():
            idx = int(line[:dot]) - 1
            if 0 <= idx < len(items):
                results[idx] = line[dot + 1:].strip()
    return results


def translate_file(json_path: Path):
    data = json.loads(json_path.read_text(encoding="utf-8"))

    pending_idx = [
        i for i, item in enumerate(data)
        if item.get("d") and not item.get("zh")
        and clean_desc(item.get("d", ""))
    ]

    print(f"\n{json_path.parent.name}/combined.json: {len(data)} 条, 待翻译 {len(pending_idx)} 条")
    if not pending_idx:
        print("  全部已翻译，跳过")
        return

    client = anthropic.Anthropic()
    total_done = 0

    for batch_num, start in enumerate(range(0, len(pending_idx), BATCH_SIZE), 1):
        batch_ids = pending_idx[start: start + BATCH_SIZE]
        batch_items = [data[i] for i in batch_ids]

        try:
            translations = translate_batch(batch_items, client)
        except Exception as e:
            print(f"  [批次 {batch_num}] 失败: {e}")
            time.sleep(2)
            continue

        for idx, zh in zip(batch_ids, translations):
            data[idx]["zh"] = zh

        total_done += len(batch_ids)
        print(f"  [批次 {batch_num}] {total_done}/{len(pending_idx)} 条完成  "
              f"示例: {translations[0][:30] if translations else ''}")

        if batch_num % SAVE_INTERVAL == 0:
            json_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        time.sleep(0.3)

    json_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    print(f"  完成，共翻译 {total_done} 条")


def main():
    data_dir = Path("data")
    if not data_dir.exists():
        print("错误: data/ 目录不存在")
        return

    if len(sys.argv) > 1:
        date_dirs = [data_dir / sys.argv[1]]
    else:
        date_dirs = sorted(
            d for d in data_dir.iterdir()
            if d.is_dir() and (d / "combined.json").exists()
        )

    for date_dir in date_dirs:
        combined = date_dir / "combined.json"
        if not combined.exists():
            print(f"跳过 {date_dir.name}: 无 combined.json")
            continue
        translate_file(combined)

    print("\n全部完成")


if __name__ == "__main__":
    main()
