"""
语料人工校对登记工具。

语料正文在 seed_corpus.py，本工具只维护同目录的 corpus_reviews.json：
  --export <csv>   导出 42 条供植保人员逐条校对
  --apply <csv>    回填校对结论；"通过"的条目入库时 source 变为 manual_reviewed
  --status         查看已校对数量与未校对清单

校对结论回填后需要重建索引才会生效：
  python -m rag.indexer
"""
import argparse
import csv
import json
from datetime import date
from pathlib import Path
from typing import Dict, List

from rag import seed_corpus

FIELDS = [
    "name", "crop", "category", "symptoms", "causes", "prevention", "treatment",
    "sources", "reviewed", "reviewer", "reviewed_at", "verdict", "notes",
]

APPROVE = {"通过", "approved", "pass", "ok"}
REJECT = {"需修改", "reject", "fail"}


def _row(item: Dict, review: Dict) -> Dict:
    return {
        "name": item["name"],
        "crop": item["crop"],
        "category": item["category"],
        "symptoms": item["symptoms"],
        "causes": item["causes"],
        "prevention": "；".join(item["prevention"]),
        "treatment": "；".join(item["treatment"]),
        "sources": " | ".join(item.get("sources") or []),
        "reviewed": "是" if review.get("reviewed") else "否",
        "reviewer": review.get("reviewer") or "",
        "reviewed_at": review.get("reviewed_at") or "",
        "verdict": "",
        "notes": review.get("notes") or "",
    }


def export_csv(path: str | Path) -> None:
    reviews = seed_corpus.load_reviews()
    rows = [_row(item, reviews.get(item["name"]) or {}) for item in seed_corpus.CORPUS]
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"已导出 {len(rows)} 条到 {path}")
    print("校对时填写 reviewer / reviewed_at / verdict（通过|需修改）/ notes，"
          "然后执行 --apply 回填。")


def apply_csv(path: str | Path) -> None:
    path = Path(path)
    if not path.exists():
        raise SystemExit(f"文件不存在: {path}")

    with path.open(encoding="utf-8-sig", newline="") as f:
        rows: List[Dict] = list(csv.DictReader(f))

    known = {item["name"] for item in seed_corpus.CORPUS}
    reviews = seed_corpus.load_reviews()
    approved = rejected = skipped = 0
    problems: List[str] = []

    for i, row in enumerate(rows, 2):
        name = (row.get("name") or "").strip()
        if name not in known:
            problems.append(f"第 {i} 行: 未知条目 {name!r}，已忽略")
            continue

        verdict = (row.get("verdict") or "").strip()
        reviewer = (row.get("reviewer") or "").strip()
        notes = (row.get("notes") or "").strip()

        if verdict in APPROVE:
            if not reviewer:
                problems.append(f"第 {i} 行「{name}」: 判定通过但未填 reviewer，未采纳")
                skipped += 1
                continue
            reviews[name] = {
                "reviewed": True,
                "reviewer": reviewer,
                "reviewed_at": (row.get("reviewed_at") or "").strip() or date.today().isoformat(),
                "notes": notes or None,
            }
            approved += 1
        elif verdict in REJECT:
            # 明确判为需修改 → 撤销已通过状态，保留修改意见
            reviews[name] = {
                "reviewed": False,
                "reviewer": reviewer or None,
                "reviewed_at": (row.get("reviewed_at") or "").strip() or date.today().isoformat(),
                "notes": notes or None,
            }
            rejected += 1
        else:
            # 空或待定：保持原状态，避免误撤销已有签字
            skipped += 1

    records = {
        name: record for name, record in sorted(reviews.items())
        if record.get("reviewed") or record.get("notes")
    }
    seed_corpus.REVIEWS_PATH.write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    total = len(seed_corpus.CORPUS)
    reviewed = sum(1 for r in records.values() if r.get("reviewed"))
    print(f"回填完成: 通过 {approved} / 需修改 {rejected} / 未表态 {skipped}")
    print(f"当前已校对 {reviewed}/{total} 条 → {seed_corpus.REVIEWS_PATH}")
    for p in problems:
        print(f"  [注意] {p}")
    if approved:
        print("记得重建索引：python -m rag.indexer")


def status() -> None:
    reviews = seed_corpus.load_reviews()
    total = len(seed_corpus.CORPUS)
    pending = [item["name"] for item in seed_corpus.CORPUS if item["name"] not in reviews]
    print(f"已校对 {len(reviews)}/{total} 条")
    if pending:
        print("未校对:")
        for name in pending:
            print(f"  - {name}")


def main() -> None:
    ap = argparse.ArgumentParser(description="语料人工校对登记")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--export", metavar="CSV", help="导出待校对清单")
    group.add_argument("--apply", metavar="CSV", help="回填校对结论")
    group.add_argument("--status", action="store_true", help="查看校对进度")
    args = ap.parse_args()

    if args.export:
        export_csv(args.export)
    elif args.apply:
        apply_csv(args.apply)
    else:
        status()


if __name__ == "__main__":
    main()
