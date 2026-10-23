"""
构建固定演示集（方案 §10.1 的 E2）。

从同域测试清单里按类别确定性抽样，并额外挑出若干“低 margin 难例”，
让演示每次使用同一批图片、结果可复现。

不复制原图：清单只记录相对 `ai-model/` 的路径，原图仍留在 data/raw/ 下，
避免把受数据集许可约束的图片重新分发进仓库。

用法（在 ai-model/ 目录下）：
    python data/build_demo_set.py --per-class 2 --hard 4
"""
import argparse
import json
import random
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List

AI_MODEL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_MODEL_DIR))

IMG_SIZE = 224


def _load_trained() -> List[str]:
    import torch

    ckpt = torch.load(AI_MODEL_DIR / "checkpoints/best.pt", map_location="cpu")
    return list(ckpt.get("trained_classes") or [])


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(AI_MODEL_DIR).as_posix()
    except ValueError:
        return path.as_posix()


def _candidates(manifest: Path, trained: List[str], crops: set) -> List[Dict]:
    data = json.loads(manifest.read_text(encoding="utf-8"))
    out = []
    for row in data:
        label = row.get("label") or row.get("disease")
        crop = row.get("crop")
        raw = row.get("image_path")
        if not label or not raw or label not in trained:
            continue
        if crop and crop not in crops:
            continue
        path = Path(raw) if Path(raw).is_absolute() else AI_MODEL_DIR / raw
        if not path.exists():
            continue
        out.append({**row, "_path": path, "label": label})
    return out


def _hard_examples(items: List[Dict], count: int) -> List[Dict]:
    """按 top1-top2 间距挑最不确定的样本，用于演示双引擎仲裁。"""
    if count <= 0:
        return []
    from inference.inference import InferenceEngine

    engine = InferenceEngine(str(AI_MODEL_DIR / "checkpoints/best.pt"), device="cpu")
    scored = []
    for row in items:
        result = engine.predict(str(row["_path"]))
        topk = result["disease"].get("topk") or []
        margin = 0.0
        if len(topk) >= 2:
            margin = float(topk[0]["confidence"]) - float(topk[1]["confidence"])
        scored.append((margin, row, result))
    scored.sort(key=lambda x: x[0])
    return [
        {**row, "_hard": True, "_margin": round(margin, 4),
         "_cnn_top1": (pred.get("disease") or {}).get("name")}
        for margin, row, pred in scored[:count]
    ]


def main() -> None:
    ap = argparse.ArgumentParser(description="构建固定演示集")
    ap.add_argument("--manifest", default=str(AI_MODEL_DIR / "data/manifests/v1_test.json"))
    ap.add_argument("--per-class", type=int, default=2)
    ap.add_argument("--hard", type=int, default=4, help="额外挑选的难例数量")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default=str(AI_MODEL_DIR / "data/demo/e2.json"))
    args = ap.parse_args()

    trained = _load_trained()
    from labels import crop_of_label

    crops = {crop_of_label(label) for label in trained if crop_of_label(label)}
    items = _candidates(Path(args.manifest), trained, crops)
    if not items:
        raise SystemExit("没有可用样本，请先重建 manifest")

    by_label: Dict[str, List[Dict]] = defaultdict(list)
    for row in sorted(items, key=lambda r: r["_path"].as_posix()):
        by_label[row["label"]].append(row)

    rnd = random.Random(args.seed)
    picked: List[Dict] = []
    for label in sorted(by_label):
        pool = by_label[label][:]
        rnd.shuffle(pool)
        picked.extend(pool[: args.per_class])

    hard = _hard_examples(items, args.hard)
    hard_paths = {r["_path"] for r in hard}
    picked = [r for r in picked if r["_path"] not in hard_paths] + hard
    rnd.shuffle(picked)

    out_items = []
    for row in picked:
        entry = {
            "image_path": _rel(row["_path"]),
            "label": row["label"],
            "crop": row.get("crop"),
            "source": row.get("source"),
            "difficulty": "hard" if row.get("_hard") else "normal",
        }
        if row.get("_hard"):
            entry["note"] = (f"CNN top1-top2 margin={row['_margin']}，"
                             f"top1={row.get('_cnn_top1')}")
        out_items.append(entry)

    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "source_manifest": _rel(Path(args.manifest)),
        "per_class": args.per_class,
        "hard_count": len(hard),
        "items": out_items,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"已写入 {out}：{len(out_items)} 张"
          f"（正常 {len(out_items) - len(hard)}，难例 {len(hard)}）")
    for item in out_items:
        if item["difficulty"] == "hard":
            print(f"  [难例] {item['label']} | {item['note']}")


if __name__ == "__main__":
    main()
