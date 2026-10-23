"""
把下载到本地的公开数据集整理成统一清单（manifest）。

目录约定（每个数据集一个目录）：
    ai-model/data/raw/<dataset_key>/<类别目录>/*.jpg
或（数据集自带划分时）：
    ai-model/data/raw/<dataset_key>/{train,val,test}/<类别目录>/*.jpg

输出：
    ai-model/data/manifests/<name>.json   统一清单
        [{"image_path", "label", "crop", "source", "split", "source_class"}]
    ai-model/data/manifests/<name>_coverage.md   覆盖率与问题报告

用法（在 ai-model/ 目录下）：
    python data/build_manifest.py --audit                # 只看登记表，不扫文件
    python data/build_manifest.py --raw-root data/raw --out data/manifests/v1.json
    python data/build_manifest.py ... --include-approx --allow-nc
"""
import argparse
import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dataset_registry import DATASETS  # noqa: E402

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
SPLIT_DIRS = {"train", "val", "valid", "validation", "test"}

# 数据集中自带的增强图后缀，例如 Anthracnose_104_crop_196.jpg
_AUG_RE = re.compile(r"_(crop|rotate|blur|bright|flip|noise|scale|shift|zoom|contrast)_\d+$", re.I)


def _base_id(stem: str) -> str:
    """去掉增强后缀，得到原图 ID。

    同一张原图的多个增强版本必须落在同一个 split，否则测试集里会出现
    训练图的变体，指标虚高——这是数据划分里最常见也最隐蔽的泄漏。
    """
    return _AUG_RE.sub("", stem)


def _is_augmented(stem: str) -> bool:
    return bool(_AUG_RE.search(stem))


def _norm(name: str) -> str:
    return name.strip().lower().replace("-", "_").replace(" ", "_")


def _lookup_mapping(entry: dict, class_dir: str) -> Optional[Tuple[str, str]]:
    """按类别目录名查映射；先精确，再忽略大小写/空格/连字符。"""
    mapping = entry.get("mapping") or {}
    if class_dir in mapping:
        return mapping[class_dir]
    target = _norm(class_dir)
    for key, value in mapping.items():
        if _norm(key) == target:
            return value
    return None


def _iter_dataset_files(dataset_dir: Path):
    """产出 (image_path, class_dir_name, split_hint)。"""
    for root, _dirs, files in os.walk(dataset_dir):
        for fname in files:
            if Path(fname).suffix.lower() not in IMAGE_EXTS:
                continue
            path = Path(root) / fname
            parent = path.parent.name
            if parent.lower() in SPLIT_DIRS:
                class_dir = path.parent.parent.name
                split_hint = parent.lower()
            else:
                class_dir = parent
                split_hint = None
            yield path, class_dir, split_hint


def _split_of(rel_path: str) -> str:
    """按路径哈希做确定性划分，保证每次重建清单得到同一划分。"""
    h = hashlib.sha256(rel_path.encode("utf-8")).hexdigest()[:8]
    bucket = int(h, 16) % 100
    if bucket < 80:
        return "train"
    if bucket < 90:
        return "val"
    return "test"


def build(args) -> Dict:
    raw_root = Path(args.raw_root) if args.raw_root else None
    manifest: List[Dict] = []
    per_dataset: Dict[str, Dict] = {}
    label_counts: Dict[str, int] = defaultdict(int)
    label_sources: Dict[str, set] = defaultdict(set)

    for entry in DATASETS:
        key = entry["key"]
        stats = {
            "name": entry["name"],
            "license": entry["license"],
            "commercial_ok": entry["commercial_ok"],
            "found": 0,
            "mapped": 0,
            "skipped_unmapped": 0,
            "skipped_approx": 0,
            "skipped_license": 0,
            "skipped_unverified": 0,
            "skipped_augmented": 0,
            "skipped_eval_only": 0,
            "local_dir": None,
            "note": entry.get("notes", ""),
        }

        if entry.get("eval_only"):
            stats["skipped_eval_only"] = -1   # -1 表示整体仅用于评测
            per_dataset[key] = stats
            continue

        if not entry["verified"]:
            stats["skipped_unverified"] = -1   # -1 表示整条未核实
            per_dataset[key] = stats
            continue

        if entry["commercial_ok"] is False and not args.allow_nc:
            stats["skipped_license"] = -1      # -1 表示因许可整条排除
            per_dataset[key] = stats
            continue

        dataset_dir = (raw_root / key) if raw_root else None
        if dataset_dir is None or not dataset_dir.exists():
            per_dataset[key] = stats
            continue

        stats["local_dir"] = str(dataset_dir)
        pending = []
        for path, class_dir, split_hint in _iter_dataset_files(dataset_dir):
            stats["found"] += 1

            # 某些数据集的增强图放在独立目录且编号与原图不对应，无法防泄漏，整体丢弃
            if entry.get("drop_augmented") and class_dir.lower().startswith("augmented"):
                stats["skipped_augmented"] += 1
                continue

            mapped = _lookup_mapping(entry, class_dir)
            if mapped is None:
                stats["skipped_unmapped"] += 1
                continue
            label, kind = mapped
            if kind == "approx" and not args.include_approx:
                stats["skipped_approx"] += 1
                continue

            pending.append((path, class_dir, label, kind, split_hint))

        # 可选：限制每个类别的入库数量。新来源若在数量上占主导，
        # 会把共享特征空间拉向自己（实测菠萝 5,115 张让芒果跨域掉 8.5pt）。
        cap = entry.get("max_per_class")
        if cap:
            by_label = defaultdict(list)
            for item in pending:
                by_label[item[2]].append(item)
            trimmed = []
            for label, items in by_label.items():
                items.sort(key=lambda x: str(x[0]))
                trimmed.extend(items[:cap])
            stats["capped_from"] = len(pending)
            pending = trimmed

        for path, class_dir, label, kind, split_hint in pending:
            # 划分依据 = 数据集/类别/原图ID，增强图与原图同组
            group_key = f"{key}/{class_dir}/{_base_id(path.stem)}"
            manifest.append({
                # 存绝对路径：清单会被训练脚本与 backend 门禁从不同工作目录读取
                "image_path": str(path.resolve()),
                "label": label,
                "crop": entry["crop"],
                "source": key,
                "source_class": class_dir,
                "mapping_kind": kind,
                "augmented": _is_augmented(path.stem),
                "split": split_hint or _split_of(group_key),
            })
            stats["mapped"] += 1
            label_counts[label] += 1
            label_sources[label].add(entry["crop"])

        per_dataset[key] = stats

    return {
        "manifest": manifest,
        "per_dataset": per_dataset,
        "label_counts": dict(sorted(label_counts.items(), key=lambda kv: -kv[1])),
        "label_sources": {k: sorted(v) for k, v in label_sources.items()},
    }


def render_report(result: Dict, args) -> str:
    lines = ["# 数据集覆盖率报告", ""]
    lines.append(f"- 清单条目：**{len(result['manifest'])}**")
    lines.append(f"- 覆盖标签数：**{len(result['label_counts'])}**")
    lines.append(f"- 包含近似映射：{'是' if args.include_approx else '否'}")
    lines.append(f"- 允许非商用（NC）数据集：{'是' if args.allow_nc else '否'}")
    lines.append("")

    lines.append("## 各数据集状态")
    lines.append("")
    lines.append("| 数据集 | 许可 | 商用 | 本地 | 找到 | 入库 | 未映射 | 近似跳过 | 增强丢弃 | 状态 |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for key, s in result["per_dataset"].items():
        if s["skipped_unverified"] == -1:
            status = "未核实，跳过"
        elif s["skipped_eval_only"] == -1:
            status = "仅评测，不入训练"
        elif s["skipped_license"] == -1:
            status = "许可禁止商用，跳过"
        elif s["local_dir"] is None:
            status = "未下载"
        elif s["mapped"] == 0:
            status = "已下载但零可用类别"
        else:
            status = "可用"
        commercial = {True: "可", False: "否", None: "未知"}[s["commercial_ok"]]
        lines.append(
            f"| {s['name']} | {s['license']} | {commercial} | "
            f"{'是' if s['local_dir'] else '否'} | {s['found']} | {s['mapped']} | "
            f"{s['skipped_unmapped']} | {s['skipped_approx']} | {s['skipped_augmented']} | {status} |"
        )
    lines.append("")

    lines.append("## 标签覆盖")
    lines.append("")
    if not result["label_counts"]:
        lines.append("_当前没有任何已入库样本。请先下载数据集到 `data/raw/<dataset_key>/`。_")
    else:
        lines.append("| 标签 | 样本数 | 来源作物 | 是否达到建议下限 |")
        lines.append("|---|---|---|---|")
        for label, count in result["label_counts"].items():
            ok = "是" if count >= args.min_per_class else f"否（<{args.min_per_class}）"
            lines.append(f"| {label} | {count} | {'、'.join(result['label_sources'][label])} | {ok} |")
    lines.append("")

    lines.append("## 已知问题")
    lines.append("")
    lines.append("1. **严重度标签缺失**：除咖啡锈病严重度集外，所有公开集都只有图像级病害分类，"
                 "第三个分类头（轻/中/重）没有训练数据。")
    lines.append("2. **分类体系不匹配**：多个数据集用症状名（Black Spot / Burned Leaf）"
                 "而非病原名，与我们的标签空间无法精确对应。")
    lines.append("3. **非商用许可**：MangoLeafBD 为 CC BY-NC，商用项目不可用。")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="构建统一训练/评测清单")
    parser.add_argument("--raw-root", default=None, help="包含各数据集目录的根目录")
    parser.add_argument("--out", default=None, help="manifest 输出路径")
    parser.add_argument("--include-approx", action="store_true", help="纳入近似映射类别")
    parser.add_argument("--allow-nc", action="store_true", help="允许使用禁止商用的数据集")
    parser.add_argument("--min-per-class", type=int, default=20)
    parser.add_argument("--audit", action="store_true", help="只输出登记表审计，不扫文件")
    args = parser.parse_args()

    result = build(args)
    report = render_report(result, args)

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result["manifest"], ensure_ascii=False, indent=2), encoding="utf-8")
        report_path = out.with_name(out.stem + "_coverage.md")
        report_path.write_text(report, encoding="utf-8")
        print(f"清单已写入 {out}（{len(result['manifest'])} 条）")
        print(f"报告已写入 {report_path}")

    print(report)


if __name__ == "__main__":
    main()
