"""
基于 manifest 的训练脚本（D2）。

与旧的 `train.py` 的区别：
  - 数据来自 `data/manifests/*.json`，而不是目录结构；
  - **只训练 crop 与 disease 两个头**——公开数据没有严重度标注
    （labels.SEVERITY_TRAINED = False），训练它等于拟合噪声；
  - 输出指标 JSON，可直接喂给 `backend/flywheel/gate.py` 的门禁。

用法（在 ai-model/ 目录下）：
    # 冒烟测试
    python training/train_manifest.py --manifest data/manifests/v1.json \
        --epochs 1 --limit-train 200 --img-size 160

    # 正式训练
    python training/train_manifest.py --manifest data/manifests/v1.json \
        --epochs 10 --batch-size 32 --out checkpoints/v1.1
"""
import argparse
import io
import json
import os
import random
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms as T
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from labels import CROP_CLASSES, DISEASE_CLASSES, LABELS_VERSION, SEVERITY_TRAINED  # noqa: E402
from models.lightweight_cnn import TropicalPestNet  # noqa: E402

IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


class ManifestDataset(Dataset):
    def __init__(self, entries, crop_to_id, disease_to_id, transform):
        self.entries = entries
        self.crop_to_id = crop_to_id
        self.disease_to_id = disease_to_id
        self.transform = transform

    def __len__(self):
        return len(self.entries)

    def __getitem__(self, idx):
        e = self.entries[idx]
        img = Image.open(e["image_path"]).convert("RGB")
        return (
            self.transform(img),
            self.crop_to_id[e["crop"]],
            self.disease_to_id[e["label"]],
        )


class RandomJPEG:
    """模拟不同手机/相机的 JPEG 压缩质量。

    跨域失败的一大来源是采集设备差异（压缩率、噪点），
    而 torchvision 没有现成变换，这里用 PIL 重新编码实现。
    """

    def __init__(self, p: float = 0.25, quality=(30, 90)):
        self.p = p
        self.quality = quality

    def __call__(self, img):
        if random.random() > self.p:
            return img
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=random.randint(*self.quality))
        buf.seek(0)
        return Image.open(buf).convert("RGB")


def build_transforms(img_size: int, train: bool, aug: str = "base"):
    if not train:
        return T.Compose([
            T.Resize(int(img_size * 1.14)),
            T.CenterCrop(img_size),
            T.ToTensor(),
            T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

    if aug == "dr":
        # 域随机化：模拟不同设备、距离、角度、光照与压缩质量。
        # 注意色相抖动保持很小（0.05）——病害的颜色（锈斑橙、白粉白）
        # 本身就是判别信号，过度改色会抹掉标签信息。
        return T.Compose([
            T.RandomResizedCrop(img_size, scale=(0.5, 1.0), ratio=(0.75, 1.33)),
            T.RandomHorizontalFlip(),
            T.RandomApply([T.RandomAffine(degrees=20, translate=(0.08, 0.08), shear=8)], p=0.5),
            T.RandomPerspective(distortion_scale=0.15, p=0.3),
            T.ColorJitter(brightness=0.4, contrast=0.4, saturation=0.3, hue=0.05),
            T.RandomGrayscale(p=0.05),
            T.RandomApply([T.GaussianBlur(3, sigma=(0.1, 2.0))], p=0.2),
            RandomJPEG(p=0.25, quality=(30, 90)),
            T.ToTensor(),
            T.RandomErasing(p=0.1, scale=(0.02, 0.1)),
            T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

    return T.Compose([
        T.RandomResizedCrop(img_size, scale=(0.7, 1.0)),
        T.RandomHorizontalFlip(),
        T.RandomRotation(15),
        T.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
        T.ToTensor(),
        T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])
    return T.Compose([
        T.Resize(int(img_size * 1.14)),
        T.CenterCrop(img_size),
        T.ToTensor(),
        T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])


def load_manifest(path: str, limit_train: int = 0):
    entries = json.load(open(path, encoding="utf-8"))
    by_split = defaultdict(list)
    skipped = Counter()
    for e in entries:
        if not os.path.exists(e["image_path"]):
            skipped["missing_file"] += 1
            continue
        if e["crop"] not in CROP_CLASSES:
            skipped["unknown_crop"] += 1
            continue
        if e["label"] not in DISEASE_CLASSES:
            skipped["unknown_label"] += 1
            continue
        by_split[e["split"]].append(e)

    if limit_train:
        random.Random(0).shuffle(by_split["train"])
        by_split["train"] = by_split["train"][:limit_train]
    return by_split, skipped


def macro_f1(y_true, y_pred, num_classes):
    """多分类宏平均 F1；只统计真实出现过的类别，避免未出现的类稀释指标。"""
    scores = []
    for c in range(num_classes):
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == c and p == c)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != c and p == c)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == c and p != c)
        if tp + fn == 0:
            continue
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        scores.append(2 * precision * recall / (precision + recall) if (precision + recall) else 0.0)
    return sum(scores) / len(scores) if scores else 0.0


@torch.no_grad()
def evaluate(model, loader, device, criterion_crop, criterion_disease):
    model.eval()
    total_loss, n = 0.0, 0
    crop_true, crop_pred, dis_true, dis_pred = [], [], [], []
    for images, crops, diseases in loader:
        images, crops, diseases = images.to(device), crops.to(device), diseases.to(device)
        out = model(images)
        loss = criterion_crop(out["crop"], crops) + criterion_disease(out["disease"], diseases)
        total_loss += loss.item() * images.size(0)
        n += images.size(0)
        crop_true += crops.cpu().tolist()
        crop_pred += out["crop"].argmax(1).cpu().tolist()
        dis_true += diseases.cpu().tolist()
        dis_pred += out["disease"].argmax(1).cpu().tolist()

    return {
        "loss": round(total_loss / max(n, 1), 4),
        "n": n,
        "crop_accuracy": round(sum(a == b for a, b in zip(crop_true, crop_pred)) / max(n, 1), 4),
        "disease_accuracy": round(sum(a == b for a, b in zip(dis_true, dis_pred)) / max(n, 1), 4),
        "disease_macro_f1": round(macro_f1(dis_true, dis_pred, len(DISEASE_CLASSES)), 4),
        "per_class": {
            DISEASE_CLASSES[c]: {
                "support": sum(1 for t in dis_true if t == c),
                "recall": round(sum(1 for t, p in zip(dis_true, dis_pred) if t == c and p == c)
                                / max(sum(1 for t in dis_true if t == c), 1), 4),
            }
            for c in sorted(set(dis_true))
        },
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", required=True)
    p.add_argument("--epochs", type=int, default=10)
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--lr", type=float, default=3e-4)
    p.add_argument("--img-size", type=int, default=224)
    p.add_argument("--device", default="auto")
    p.add_argument("--workers", type=int, default=0, help="Windows 上建议 0")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--freeze-epochs", type=int, default=1,
                   help="前 N 轮冻结骨干，只训分类头")
    p.add_argument("--limit-train", type=int, default=0, help="仅用于冒烟测试")
    p.add_argument("--out", default="checkpoints/v1.1")
    p.add_argument("--aug", choices=["base", "dr"], default="base",
                   help="base=原增强；dr=域随机化增强（跨域实验用）")
    args = p.parse_args()

    set_seed(args.seed)
    device = ("cuda" if torch.cuda.is_available() else "cpu") if args.device == "auto" else args.device
    threads = os.cpu_count() or 4
    torch.set_num_threads(threads)
    print(f"device={device} threads={threads} labels={LABELS_VERSION} "
          f"severity_trained={SEVERITY_TRAINED}")

    crop_to_id = {c: i for i, c in enumerate(CROP_CLASSES)}
    disease_to_id = {d: i for i, d in enumerate(DISEASE_CLASSES)}

    by_split, skipped = load_manifest(args.manifest, args.limit_train)
    print(f"数据: train={len(by_split['train'])} val={len(by_split['val'])} "
          f"test={len(by_split['test'])} | 跳过: {dict(skipped)}")
    if not by_split["train"]:
        raise SystemExit("训练集为空")

    loaders = {
        "train": DataLoader(
            ManifestDataset(by_split["train"], crop_to_id, disease_to_id,
                            build_transforms(args.img_size, True, args.aug)),
            batch_size=args.batch_size, shuffle=True,
            num_workers=args.workers, drop_last=True,
        ),
        "val": DataLoader(
            ManifestDataset(by_split["val"], crop_to_id, disease_to_id,
                            build_transforms(args.img_size, False)),
            batch_size=args.batch_size, shuffle=False, num_workers=args.workers,
        ),
        "test": DataLoader(
            ManifestDataset(by_split["test"], crop_to_id, disease_to_id,
                            build_transforms(args.img_size, False)),
            batch_size=args.batch_size, shuffle=False, num_workers=args.workers,
        ),
    }

    model = TropicalPestNet(
        num_classes=len(DISEASE_CLASSES), num_crops=len(CROP_CLASSES), pretrained=True
    ).to(device)
    print("模型:", model.get_model_size())

    # 类别不平衡：健康类有 1877 张，香蕉小类只有 23 张。
    # 用 sqrt 反频率作权重，避免极少数类把梯度带偏。
    counts = Counter(e["label"] for e in by_split["train"])
    weights = torch.tensor(
        [(1.0 / counts.get(d, 1)) ** 0.5 for d in DISEASE_CLASSES], dtype=torch.float32
    ).to(device)
    weights = weights / weights.mean()
    criterion_crop = nn.CrossEntropyLoss(label_smoothing=0.1)
    criterion_disease = nn.CrossEntropyLoss(weight=weights, label_smoothing=0.1)

    optimizer = optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    best_f1, best_epoch = -1.0, 0
    history = []

    for epoch in range(1, args.epochs + 1):
        # 冻结/解冻骨干
        frozen = epoch <= args.freeze_epochs
        for name, param in model.named_parameters():
            if name.startswith("features."):
                param.requires_grad = not frozen
        if epoch == 1:
            print(f"[epoch 1] 骨干冻结={frozen}（只训分类头）")

        model.train()
        started = time.time()
        running, seen = 0.0, 0
        pbar = tqdm(loaders["train"], desc=f"Epoch {epoch}/{args.epochs}", leave=False)
        for images, crops, diseases in pbar:
            images, crops, diseases = images.to(device), crops.to(device), diseases.to(device)
            optimizer.zero_grad()
            out = model(images)
            # 只计算两个头；severity 头不参与（无标注）
            loss = criterion_crop(out["crop"], crops) + criterion_disease(out["disease"], diseases)
            loss.backward()
            optimizer.step()
            running += loss.item() * images.size(0)
            seen += images.size(0)
            pbar.set_postfix(loss=f"{running/max(seen,1):.4f}")

        scheduler.step()
        val = evaluate(model, loaders["val"], device, criterion_crop, criterion_disease)
        elapsed = time.time() - started
        print(f"epoch {epoch}: train_loss={running/max(seen,1):.4f} "
              f"val_loss={val['loss']} val_acc={val['disease_accuracy']:.4f} "
              f"val_f1={val['disease_macro_f1']:.4f} ({elapsed:.1f}s)")

        history.append({"epoch": epoch, "val": val, "train_loss": round(running / max(seen, 1), 4)})

        if val["disease_macro_f1"] > best_f1:
            best_f1 = val["disease_macro_f1"]
            best_epoch = epoch
            torch.save({
                "model": model.state_dict(),
                "version": out_dir.name,
                "labels_version": LABELS_VERSION,
                "crop_classes": CROP_CLASSES,
                "disease_classes": DISEASE_CLASSES,
                # 记录训练集里真实出现过的类别：推理时要屏蔽其余类，
                # 否则零样本类别的随机分类头会吸收低置信预测（实测：
                # 健康叶片被误判为"木瓜花叶病"）。
                "trained_classes": sorted({e["label"] for e in by_split["train"]}),
                "epoch": epoch,
                "val_metrics": val,
            }, out_dir / "best.pt")
            print(f"  ✓ 保存最佳模型 (val macro-F1={best_f1:.4f})")

    # 用最佳权重在测试集上评一次
    ckpt = torch.load(out_dir / "best.pt", map_location=device)
    model.load_state_dict(ckpt["model"])
    test = evaluate(model, loaders["test"], device, criterion_crop, criterion_disease)

    metrics = {
        "labels_version": LABELS_VERSION,
        "severity_trained": SEVERITY_TRAINED,
        "aug": args.aug,
        "manifest": args.manifest,
        "epochs": args.epochs,
        "img_size": args.img_size,
        "best_epoch": best_epoch,
        "val": history[best_epoch - 1]["val"] if 0 < best_epoch <= len(history) else None,
        "test": test,
        "history": history,
        "n_train": len(by_split["train"]),
        "n_val": len(by_split["val"]),
        "n_test": len(by_split["test"]),
        "skipped": dict(skipped),
    }
    (out_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2),
                                          encoding="utf-8")
    print(f"\n测试集: acc={test['disease_accuracy']:.4f} macro-F1={test['disease_macro_f1']:.4f}")
    print(f"指标已写入 {out_dir/'metrics.json'}")


if __name__ == "__main__":
    main()
