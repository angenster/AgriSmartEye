"""
模拟一批用户上传样本，走完「入队 → 人工复核确认」流程，用于演示/测试飞轮闭环。

真实场景里这一步由前端上传 + 复核页完成；这里用脚本代替，便于复现实验。

用法（在 backend/ 目录下）：
    python -m flywheel.seed_demo \
        --dir "../ai-model/data/raw/dragonfruit_xdom/Cleaned/test/Good leaf" \
        --label 健康 --crop 火龙果 --count 150 --holdout 50 \
        --out-holdout ../ai-model/data/manifests/flywheel_holdout.json

脚本会：
  1. 确定性打乱后取前 count 张入队并确认，其余 holdout 张写成留出集清单；
  2. 入队走真实的 maybe_enqueue（manual 触发），确认走 review.confirm；
  3. 已入队过的图片按 hash 自动去重。
"""
import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import SessionLocal            # noqa: E402
from flywheel import review                  # noqa: E402
from flywheel.trigger import maybe_enqueue   # noqa: E402
from labels import DISEASE_CLASSES           # noqa: E402
from services.model_service import model_service  # noqa: E402

IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dir", required=True, help="图片目录")
    p.add_argument("--label", required=True, help="复核后的最终标签")
    p.add_argument("--crop", required=True, help="作物名（写入样本的 crop_type）")
    p.add_argument("--count", type=int, default=150, help="入队并确认的样本数")
    p.add_argument("--holdout", type=int, default=50, help="留出评测的样本数")
    p.add_argument("--out-holdout", required=True, help="留出集清单输出路径")
    args = p.parse_args()

    if args.label not in DISEASE_CLASSES:
        raise SystemExit(f"标签 {args.label!r} 不在模型标签空间内")

    files = [p for p in Path(args.dir).rglob("*")
             if p.is_file() and p.suffix.lower() in IMG_EXTS]
    files.sort()
    random.Random(0).shuffle(files)
    if len(files) < args.count + args.holdout:
        raise SystemExit(f"图片不足：{len(files)} < {args.count}+{args.holdout}")

    train_files = files[:args.count]
    holdout_files = files[args.count:args.count + args.holdout]

    out = Path(args.out_holdout)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(
        [{"image_path": str(p.resolve()), "label": args.label, "crop": args.crop}
         for p in holdout_files], ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"留出集 {len(holdout_files)} 张 -> {out}")

    # 模型只需就绪（用于生成入队时的预标注）
    model_service.load()
    db = SessionLocal()
    queued = confirmed = skipped = 0
    try:
        for path in train_files:
            pred = model_service.predict(str(path))
            cnn = {
                "crop": args.crop,          # 模拟复核人已知作物，覆盖模型可能错误的作物预测
                "disease": pred["disease"]["name"],
                "confidence": pred["disease"]["confidence"],
                "topk": pred["disease"]["topk"],
            }
            info = maybe_enqueue(db, str(path), cnn, None,
                                 source="simulated_upload", manual=True)
            if not info or not info.get("sample_id"):
                skipped += 1
                continue
            queued += 1
            review.confirm(db, info["sample_id"], "correct", final_label=args.label,
                           notes="simulated reviewer")
            confirmed += 1
    finally:
        db.close()

    print(f"入队 {queued}，确认 {confirmed}，跳过 {skipped}（重复或文件不存在）")


if __name__ == "__main__":
    main()
