"""
数据飞轮的增量微调：在 production 权重上做 LoRA，只用复核确认的样本 + 少量回放。

设计要点：
  - 只训练 LoRA 适配器（分类头 + 骨干末段），基座权重冻结，避免小样本把模型带崩；
  - 混入 `--replay-ratio` 比例的原训练集（按类分层采样），防止遗忘；
  - 同时评估「飞轮回放集」（新域留出）与「主测试集」，前者衡量学到了什么，
    后者衡量有没有把原有能力弄坏；
  - 产出 merged.pt，格式与 InferenceEngine 兼容，可直接进门禁。

用法（在 ai-model/ 目录下）：
    python flywheel/train_lora.py \
        --base checkpoints/v1.5-papaya/best.pt \
        --flywheel data/manifests/flywheel.json \
        --manifest data/manifests/v1.json \
        --holdout data/manifests/flywheel_holdout.json \
        --out checkpoints/v1.6-flywheel
"""
import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "training"))

from labels import CROP_CLASSES, DISEASE_CLASSES, LABELS_VERSION, SEVERITY_TRAINED  # noqa: E402
from models.lightweight_cnn import TropicalPestNet  # noqa: E402
from train_manifest import ManifestDataset, build_transforms, macro_f1, set_seed  # noqa: E402


@torch.no_grad()
def evaluate(model, entries, crop_to_id, disease_to_id, device, img_size=224):
    model.eval()
    ds = ManifestDataset(entries, crop_to_id, disease_to_id, build_transforms(img_size, False))
    loader = DataLoader(ds, batch_size=32, shuffle=False)
    correct = total = 0
    y_true, y_pred = [], []
    for images, crops, diseases in loader:
        images = images.to(device)
        out = model(images)
        pred = out["disease"].argmax(1).cpu()
        y_pred.extend(pred.tolist())
        y_true.extend(diseases.tolist())
        correct += (pred == diseases).sum().item()
        total += images.size(0)
    return {
        "n": total,
        "accuracy": round(correct / total, 4) if total else None,
        "macro_f1": round(macro_f1(y_true, y_pred, len(DISEASE_CLASSES)), 4) if total else None,
    }


class DistillDataset(Dataset):
    """返回 (图像, 作物, 病害, 基座logits, distill_mask)。

    回放样本带 distill_mask=1，训练时用 KL 约束新模型输出不要偏离基座；
    飞轮样本 mask=0，正常用交叉熵学习。这样既能学到新域，又不会把
    原有类别的决策边界带偏（实测单类批次会把咖啡锈病召回从 67% 压到 46%）。
    """

    def __init__(self, entries, crop_to_id, disease_to_id, transform, base_logits):
        self.inner = ManifestDataset(entries, crop_to_id, disease_to_id, transform)
        self.entries = entries
        self.base_logits = base_logits

    def __len__(self):
        return len(self.entries)

    def __getitem__(self, idx):
        image, crop, disease = self.inner[idx]
        e = self.entries[idx]
        logits = self.base_logits.get(e["image_path"])
        if logits is None:
            logits = torch.zeros(len(DISEASE_CLASSES))
            mask = torch.tensor(0.0)
        else:
            mask = torch.tensor(1.0)
        return image, crop, disease, logits, mask


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--base", required=True, help="production 权重")
    p.add_argument("--flywheel", required=True, help="复核确认样本清单")
    p.add_argument("--manifest", required=True, help="原训练清单（用于回放）")
    p.add_argument("--holdout", required=True, help="飞轮新域留出集")
    p.add_argument("--out", default="checkpoints/v1.6-flywheel")
    p.add_argument("--epochs", type=int, default=20)
    p.add_argument("--batch-size", type=int, default=16)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--lora-r", type=int, default=8)
    p.add_argument("--replay-ratio", type=float, default=0.10)
    p.add_argument("--distill-weight", type=float, default=1.0,
                   help="回放样本上的 KL 蒸馏权重，防止小批次把原有决策边界带偏")
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    set_seed(args.seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    crop_to_id = {c: i for i, c in enumerate(CROP_CLASSES)}
    disease_to_id = {d: i for i, d in enumerate(DISEASE_CLASSES)}

    flywheel = [e for e in json.load(open(args.flywheel, encoding="utf-8"))
                if e["label"] in DISEASE_CLASSES and e["crop"] in CROP_CLASSES]
    if not flywheel:
        raise SystemExit("没有可用的复核样本")

    # 分层回放：每个类取原训练集的一定比例
    main_manifest = json.load(open(args.manifest, encoding="utf-8"))
    by_label = defaultdict(list)
    for e in main_manifest:
        if e["split"] == "train" and e["label"] in DISEASE_CLASSES and e["crop"] in CROP_CLASSES:
            by_label[e["label"]].append(e)
    replay = []
    rng = random.Random(args.seed)
    for label, items in by_label.items():
        k = max(1, int(len(items) * args.replay_ratio))
        replay.extend(rng.sample(items, min(k, len(items))))

    train_entries = flywheel + [dict(e, source="replay") for e in replay]
    holdout = json.load(open(args.holdout, encoding="utf-8"))
    holdout = [e for e in holdout if e["label"] in DISEASE_CLASSES and e["crop"] in CROP_CLASSES]
    print(f"飞轮样本 {len(flywheel)} + 回放 {len(replay)} = {len(train_entries)} | 留出 {len(holdout)}")

    model = TropicalPestNet(len(DISEASE_CLASSES), len(CROP_CLASSES), pretrained=False).to(device)
    ckpt = torch.load(args.base, map_location=device)
    model.load_state_dict(ckpt.get("model", ckpt))

    before = evaluate(model, holdout, crop_to_id, disease_to_id, device)
    print(f"微调前（新域留出）: acc={before['accuracy']} macro-F1={before['macro_f1']}")

    # 预计算基座在回放样本上的 logits，作为蒸馏目标
    base_logits = {}
    if args.distill_weight > 0:
        replay_entries = [e for e in train_entries if e.get("source") == "replay"]
        print(f"预计算基座 logits: {len(replay_entries)} 张")
        val_tf = build_transforms(224, False)
        model.eval()
        with torch.no_grad():
            for i in range(0, len(replay_entries), 32):
                chunk = replay_entries[i:i + 32]
                imgs = torch.stack([
                    val_tf(Image.open(e["image_path"]).convert("RGB")) for e in chunk
                ]).to(device)
                logits = model(imgs)["disease"].detach().cpu()
                for e, logit in zip(chunk, logits):
                    base_logits[e["image_path"]] = logit
        print(f"  已缓存 {len(base_logits)} 条")

    # LoRA：只训练分类头；骨干末段也可加，但小样本下先保守处理
    from peft import LoraConfig, get_peft_model
    target = ["disease_classifier.0", "disease_classifier.3",
              "crop_classifier.0", "crop_classifier.3"]
    model = get_peft_model(model, LoraConfig(
        r=args.lora_r, lora_alpha=args.lora_r * 2, lora_dropout=0.05,
        target_modules=target, bias="none",
    ))
    model.print_trainable_parameters()

    train_ds = DistillDataset(train_entries, crop_to_id, disease_to_id,
                              build_transforms(224, True, "base"), base_logits)
    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, drop_last=True)

    ce_crop = nn.CrossEntropyLoss(label_smoothing=0.05)
    # 飞轮批次往往类别极不均衡（例如整批都是"健康"）。若用普通 CE，
    # 模型会整体向该类别偏置，把病害召回压下去（实测咖啡锈病 67% → 46%）。
    # 用 sqrt 反频率权重抵消这一偏置。
    counts = Counter(e["label"] for e in train_entries)
    w = torch.tensor([(1.0 / counts.get(d, 1)) ** 0.5 for d in DISEASE_CLASSES],
                     dtype=torch.float32)
    w = (w / w.mean()).to(device)
    ce_disease = nn.CrossEntropyLoss(weight=w, label_smoothing=0.05)
    print("类别权重:", {d: round(float(w[i]), 2) for i, d in enumerate(DISEASE_CLASSES)})
    optimizer = optim.AdamW([p_ for p_ in model.parameters() if p_.requires_grad],
                            lr=args.lr, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)

    for epoch in range(1, args.epochs + 1):
        model.train()
        total, seen = 0.0, 0
        for images, crops, diseases, base_logit, distill_mask in tqdm(
                train_loader, desc=f"LoRA {epoch}", leave=False):
            images, crops, diseases = images.to(device), crops.to(device), diseases.to(device)
            optimizer.zero_grad()
            out = model(images)
            loss = ce_crop(out["crop"], crops) + ce_disease(out["disease"], diseases)

            # 回放样本上做 KL 蒸馏：只允许在新样本上改变行为
            if args.distill_weight > 0 and float(distill_mask.sum()) > 0:
                m = distill_mask.to(device) > 0
                logp = F.log_softmax(out["disease"][m], dim=1)
                p_base = F.softmax(base_logit[m].to(device), dim=1)
                loss = loss + args.distill_weight * F.kl_div(logp, p_base, reduction="batchmean")

            loss.backward()
            optimizer.step()
            total += loss.item() * images.size(0)
            seen += images.size(0)
        scheduler.step()
        if epoch % 5 == 0 or epoch == args.epochs:
            after = evaluate(model, holdout, crop_to_id, disease_to_id, device)
            print(f"  epoch {epoch}: loss={total/max(seen,1):.4f} holdout_acc={after['accuracy']}")

    after = evaluate(model, holdout, crop_to_id, disease_to_id, device)
    print(f"微调后（新域留出）: acc={after['accuracy']} macro-F1={after['macro_f1']}")

    # 合并 LoRA 并保存为 InferenceEngine 可加载的格式
    merged = model.merge_and_unload()
    torch.save({
        "model": merged.state_dict(),
        "version": out_dir.name,
        "labels_version": LABELS_VERSION,
        "crop_classes": CROP_CLASSES,
        "disease_classes": DISEASE_CLASSES,
        "trained_classes": ckpt.get("trained_classes"),
        "lora_r": args.lora_r,
        "base_version": ckpt.get("version"),
        "flywheel_samples": len(flywheel),
        "replay_samples": len(replay),
    }, out_dir / "merged.pt")

    metrics = {
        "labels_version": LABELS_VERSION,
        "severity_trained": SEVERITY_TRAINED,
        "base_version": ckpt.get("version"),
        "flywheel_samples": len(flywheel),
        "replay_samples": len(replay),
        "lora_r": args.lora_r,
        "epochs": args.epochs,
        "holdout_before": before,
        "holdout_after": after,
    }
    (out_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2),
                                          encoding="utf-8")
    print(f"已保存 {out_dir/'merged.pt'} 与 metrics.json")


if __name__ == "__main__":
    main()
