"""
把复核队列中已确认的样本导出为训练清单。

只导出满足以下条件的样本：
  - status=confirmed，final_label 非空；
  - final_label 在当前模型的标签空间内（42 类知识空间里的旧标签会被丢弃）；
  - 能确定作物：优先用 sample_queue.crop_type（复核时写入），
    否则从病害标签的作物前缀推断；"健康"且无 crop_type 的样本跳过。

用法（在 ai-model/ 目录下）：
    python flywheel/export_confirmed.py --out data/manifests/flywheel.json
"""
import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from labels import CROP_CLASSES, DISEASE_CLASSES, HEALTHY_LABEL, crop_of_label  # noqa: E402

DEFAULT_DB = Path(__file__).resolve().parents[2] / "backend" / "zhinong.db"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--db", default=str(DEFAULT_DB))
    p.add_argument("--out", default="data/manifests/flywheel.json")
    args = p.parse_args()

    if not os.path.exists(args.db):
        raise SystemExit(f"数据库不存在: {args.db}")

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT q.id AS sample_id, q.image_path, q.crop_type,
               c.final_label, c.confirm_source, c.created_at
        FROM sample_queue q
        JOIN sample_confirmations c ON c.sample_id = q.id
        WHERE q.status = 'confirmed' AND c.final_label IS NOT NULL
        ORDER BY c.created_at DESC
        """
    ).fetchall()
    conn.close()

    entries, skipped = [], {"not_model_label": 0, "unknown_crop": 0, "missing_file": 0}
    seen = set()
    for r in rows:
        label = r["final_label"]
        if label not in DISEASE_CLASSES:
            skipped["not_model_label"] += 1
            continue
        if not os.path.exists(r["image_path"]):
            skipped["missing_file"] += 1
            continue

        crop = r["crop_type"]
        if not crop:
            crop = crop_of_label(label)
        if crop not in CROP_CLASSES:
            if label == HEALTHY_LABEL:
                skipped["unknown_crop"] += 1
                continue
            skipped["unknown_crop"] += 1
            continue

        key = (r["image_path"], label)
        if key in seen:
            continue
        seen.add(key)
        entries.append({
            "image_path": r["image_path"],
            "label": label,
            "crop": crop,
            "source": "flywheel",
            "sample_id": r["sample_id"],
            "confirm_source": r["confirm_source"],
        })

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")

    from collections import Counter
    print(f"导出 {len(entries)} 条 -> {out}")
    print("按标签:", dict(Counter(e["label"] for e in entries)))
    print("按作物:", dict(Counter(e["crop"] for e in entries)))
    print("跳过:", skipped)


if __name__ == "__main__":
    main()
