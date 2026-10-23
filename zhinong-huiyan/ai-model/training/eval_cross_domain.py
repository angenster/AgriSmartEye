"""
跨域评测 —— 用与训练集不同来源的数据测现有模型，衡量泛化能力。

与门禁（gate.py）的区别：门禁用的是固定同域测试集，衡量"在已知分布上是否退步"；
这里用的是**不同国家/不同采集条件**的数据，衡量"换个环境会掉多少"。

三个评测集：
  1. mango_xdom    孟加拉来源的芒果叶片（8 类，疑似 MangoLeafBD 系列）
                   训练用的是越南 VN-MangoLeaf，两者独立采集。
  2. coffee_bracol 巴西 BRACoL 咖啡叶（YOLO 检测标注，按主类别的图像级标签推导）
                   训练用的是 RoCoLe，来源不同。
  3. banana_xdom   乌干达香蕉叶（sigatoka / pestalotiopsis / cordana / healthy）
                   训练用的是孟加拉 Kaggle 香蕉集。

用法（在 ai-model/ 目录下）：
    python training/eval_cross_domain.py --weights checkpoints/best.pt
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from inference.inference import InferenceEngine  # noqa: E402
from labels import DISEASE_CLASSES, HEALTHY_LABEL  # noqa: E402

IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

# 数据集 → {源类别目录名: 本项目标签}
MANGO_MAP = {
    "Anthracnose": "芒果炭疽病",
    "Powdery Mildew": "芒果白粉病",
    "Healthy Leaf": HEALTHY_LABEL,
}
BANANA_MAP = {
    "healthy": HEALTHY_LABEL,
    # sigatoka 只写"叶斑病"，未区分 Black/Yellow Sigatoka，故作为近似类单独统计
    "sigatoka": "香蕉叶斑病",
}
# 埃塞俄比亚咖啡集：只用其官方 test 划分，两个模型都未训练过
ETHIOPIA_MAP = {
    "Leaf rust": "咖啡锈病",
    "Healthy": HEALTHY_LABEL,
}
BRACOL_CLASSES = ["Cercospora", "Miner", "Phoma", "Rust"]


def _images(d: Path):
    return [p for p in d.rglob("*") if p.is_file() and p.suffix.lower() in IMG_EXTS]


def build_mango(root: Path):
    base = root / "Dataset"
    out = []
    skipped = Counter()
    for p in _images(base):
        cls = p.parent.name
        if cls in MANGO_MAP:
            out.append((p, MANGO_MAP[cls], cls))
        else:
            skipped[cls] += 1
    return out, skipped


def build_banana(root: Path):
    base = root / "OriginalSet"
    out, skipped = [], Counter()
    for p in _images(base):
        cls = p.parent.name
        if cls in BANANA_MAP:
            out.append((p, BANANA_MAP[cls], cls))
        else:
            skipped[cls] += 1
    return out, skipped


def build_ethiopia(root: Path):
    """只用官方 test 划分（未增强、未参与训练）。"""
    base = root / "ethiopian cofee leaf dataset" / "test"
    out, skipped = [], Counter()
    if not base.exists():
        # 目录名可能随版本变化，退化为找任意 test 目录
        cands = [p for p in root.rglob("test") if p.is_dir()]
        base = cands[0] if cands else base
    for p in _images(base):
        cls = p.parent.name
        if cls in ETHIOPIA_MAP:
            out.append((p, ETHIOPIA_MAP[cls], cls))
        else:
            skipped[cls] += 1
    return out, skipped


def _yolo_image_label(label_file: Path):
    """从 YOLO 标注推导图像级标签：取框数最多的类别；无框视为健康。"""
    if not label_file.exists():
        return None
    lines = [ln.strip() for ln in label_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not lines:
        return HEALTHY_LABEL
    counts = Counter()
    for ln in lines:
        parts = ln.split()
        try:
            counts[int(parts[0])] += 1
        except (ValueError, IndexError):
            continue
    if not counts:
        return HEALTHY_LABEL
    major = counts.most_common(1)[0][0]
    name = BRACOL_CLASSES[major] if 0 <= major < len(BRACOL_CLASSES) else None
    # 只保留能对应到本项目标签的：Rust → 咖啡锈病；健康由空标注处理
    return "咖啡锈病" if name == "Rust" else None


def build_coffee(root: Path):
    base = root / "BRACOL_REVIEWED_ANNOTATIONS" / "BRACOL_REVIEWED"
    out, skipped = [], Counter()
    for split in ("train", "valid", "test"):
        img_dir = base / split / "images"
        lbl_dir = base / split / "labels"
        for p in _images(img_dir):
            label = _yolo_image_label(lbl_dir / (p.stem + ".txt"))
            if label:
                out.append((p, label, split))
            else:
                skipped["非锈病/混合"] += 1
    return out, skipped


def evaluate(engine, items, name):
    correct = 0
    preds = Counter()
    per_label = defaultdict(lambda: {"n": 0, "correct": 0, "pred": Counter()})
    for path, truth, origin in items:
        r = engine.predict(str(path))
        pred = r["disease"]["name"]
        ok = pred == truth
        correct += ok
        preds[pred] += 1
        per_label[truth]["n"] += 1
        per_label[truth]["correct"] += ok
        per_label[truth]["pred"][pred] += 1

    n = len(items)
    # macro-F1（只在真实出现的类上平均）
    f1s = []
    for label, st in per_label.items():
        tp = st["pred"].get(label, 0)
        fp = sum(v for k, v in st["pred"].items() if k != label)
        fn = st["n"] - tp
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1s.append(2 * precision * recall / (precision + recall) if (precision + recall) else 0.0)

    return {
        "dataset": name,
        "n": n,
        "accuracy": round(correct / n, 4) if n else None,
        "macro_f1": round(sum(f1s) / len(f1s), 4) if f1s else None,
        "per_label": {
            label: {
                "n": st["n"],
                "recall": round(st["correct"] / st["n"], 4),
                "top_wrong": dict(st["pred"].most_common(3)),
            }
            for label, st in sorted(per_label.items(), key=lambda kv: -kv[1]["n"])
        },
        "predicted_distribution": dict(preds.most_common()),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--weights", default="checkpoints/best.pt")
    p.add_argument("--raw-root", default="data/raw")
    p.add_argument("--manifest", default="data/manifests/v1.json",
                   help="混训后必须用 manifest 的 test 划分评测，避免训练集泄漏")
    p.add_argument("--out", default="reports/cross_domain_eval.json")
    args = p.parse_args()

    root = Path(args.raw_root)
    engine = InferenceEngine(args.weights, device="cpu")
    print(f"权重: {args.weights} | version={engine.version} | demo={engine.is_demo}")
    print(f"屏蔽的零样本类别: {len(DISEASE_CLASSES) - len(engine.trained_indices or range(len(DISEASE_CLASSES)))}")

    manifest = []
    mp = Path(args.manifest)
    if mp.exists():
        manifest = json.loads(mp.read_text(encoding="utf-8"))
        print(f"manifest: {mp}（{len(manifest)} 条）")

    def from_manifest(source: str):
        """只取留出的 test 划分；这些来源已参与训练，用全量会泄漏。"""
        return [
            (Path(e["image_path"]), e["label"], e.get("source_class") or source)
            for e in manifest
            if e["source"] == source and e["split"] == "test"
        ]

    results = []
    specs = []

    # 芒果跨域：eval_only，从未参与训练，可用全量
    mango_dir = root / "mango_xdom"
    if mango_dir.exists():
        specs.append(("mango_xdom", lambda: build_mango(mango_dir)))

    # 埃塞俄比亚咖啡：两个版本都未训练过，用官方 test 划分，是真跨域
    eth_dir = root / "coffee_ethiopia"
    if eth_dir.exists():
        specs.append(("coffee_ethiopia", lambda: build_ethiopia(eth_dir)))

    # 混合来源训练用过的数据：只用 manifest 的 test 划分
    for source, label in (("coffee_bracol_cls", "coffee_bracol"), ("banana_xdom", "banana_xdom")):
        items = from_manifest(source)
        if items:
            specs.append((label, lambda items=items: (items, {"manifest_test_split": len(items)})))
        else:
            print(f"\n[{label}] manifest 中没有该来源的 test 划分，跳过（避免泄漏）")

    for name, builder in specs:
        items, skipped = builder()
        if not items:
            print(f"\n[{name}] 无可评测样本，跳过")
            continue
        print(f"\n[{name}] {len(items)} 张，跳过 {dict(skipped)}")
        result = evaluate(engine, items, name)
        results.append(result)
        print(f"  准确率 {result['accuracy']:.4f} | macro-F1 {result['macro_f1']:.4f}")
        for label, st in result["per_label"].items():
            print(f"    {label:10s} n={st['n']:4d} recall={st['recall']:.3f} "
                  f"主要误判={list(st['top_wrong'].items())[:3]}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果已写入 {out}")


if __name__ == "__main__":
    main()
