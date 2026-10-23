"""
数据集下载器。

能力边界（基于 2026-10-20 对两个平台公开 API 的实测）：

  Zenodo   完全自动：记录 API 给出文件列表、大小与 md5，可断点下载并解压。
  Mendeley 只能半自动：公开 API 返回的是扁平文件列表 + folder_id，**不含目录名**，
           无法还原「哪张图属于哪个类别」。必须在浏览器点 "Download All" 得到 ZIP，
           放到 data/raw/<dataset_key>.zip，本脚本负责解压与校验目录结构。
  Kaggle   需要 kaggle.json 凭据；无凭据时给出明确指引。

用法（在 ai-model/ 目录下）：
    python data/download_datasets.py --list
    python data/download_datasets.py --only pineapple_pldd --max-size-gb 5
    python data/download_datasets.py --all --dry-run
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dataset_registry import DATASETS, DOWNLOAD_SPECS  # noqa: E402

ZENODO_API = "https://zenodo.org/api/records/{record}"
RAW_ROOT = Path(__file__).resolve().parent / "raw"


def _fmt_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}PB"


def _md5(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def _download(url: str, dest: Path, expected_size: Optional[int] = None) -> None:
    """流式下载并显示进度。支持断点续传（存在 .part 时）。"""
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    already = part.stat().st_size if part.exists() else 0

    req = urllib.request.Request(url)
    if already:
        req.add_header("Range", f"bytes={already}-")

    with urllib.request.urlopen(req, timeout=60) as resp:
        total = expected_size or (already + int(resp.headers.get("Content-Length") or 0))
        mode = "ab" if already else "wb"
        with open(part, mode) as f:
            downloaded = already
            last = time.time()
            while True:
                block = resp.read(1 << 20)
                if not block:
                    break
                f.write(block)
                downloaded += len(block)
                if time.time() - last > 1:
                    pct = downloaded / total * 100 if total else 0
                    print(f"\r    {_fmt_size(downloaded)} / {_fmt_size(total)} ({pct:.1f}%)",
                          end="", flush=True)
                    last = time.time()
    print()
    part.replace(dest)


def _extract_zip(zip_path: Path, dest_dir: Path, class_name: Optional[str] = None) -> None:
    """解压。class_name 用于把类别名从 zip 文件名还原成 registry 里的类名。"""
    target = dest_dir / class_name if class_name else dest_dir
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(target)
    print(f"    解压 -> {target}")


# ---------------------------------------------------------------- Zenodo

def download_zenodo(spec: dict, dest: Path, max_size_gb: float, dry_run: bool) -> None:
    record = spec["record"]
    print(f"  Zenodo record {record}")
    with urllib.request.urlopen(ZENODO_API.format(record=record), timeout=60) as resp:
        meta = json.load(resp)

    files = meta.get("files") or []
    if not files:
        print("    ! API 未返回文件列表")
        return

    zip_class_map: Dict[str, str] = spec.get("zip_class_map") or {}
    for f in files:
        key = f.get("key") or f.get("filename")
        size = int(f.get("size") or 0)
        checksum = (f.get("checksum") or "").replace("md5:", "")
        if size > max_size_gb * (1 << 30):
            print(f"    跳过 {key}（{_fmt_size(size)} > {max_size_gb}GB）")
            continue

        url = (f.get("links") or {}).get("self") or \
              f"https://zenodo.org/records/{record}/files/{key}?download=1"
        target = dest / key
        if dry_run:
            print(f"    [dry-run] {key}  {_fmt_size(size)}  md5={checksum[:8]}...")
            continue

        if target.exists() and checksum and _md5(target) == checksum:
            print(f"    已存在且校验通过: {key}")
        else:
            print(f"    下载 {key}  {_fmt_size(size)}")
            _download(url, target, size)
            if checksum:
                actual = _md5(target)
                if actual != checksum:
                    print(f"    ! md5 不匹配（期望 {checksum[:8]}，实际 {actual[:8]}）")
                    target.unlink()
                    continue
                print("    md5 校验通过")

        if target.suffix.lower() == ".zip":
            stem = target.stem
            class_name = zip_class_map.get(stem)
            _extract_zip(target, dest, class_name)


# ---------------------------------------------------------------- Mendeley

def prepare_mendeley(spec: dict, key: str, raw_root: Path, dry_run: bool) -> None:
    zip_path = raw_root / f"{key}.zip"
    dest = raw_root / key

    if not zip_path.exists():
        print(f"    需要手动下载：{zip_path.name}")
        print(f"      1) 打开 https://data.mendeley.com/datasets/{spec['id']}")
        print(f"      2) 点 'Download All'")
        print(f"      3) 把得到的 ZIP 重命名为 {zip_path.name} 放到 {raw_root}")
        return

    if dry_run:
        print(f"    [dry-run] 将解压 {zip_path.name} -> {dest}")
        return

    dest.mkdir(parents=True, exist_ok=True)
    _extract_zip(zip_path, dest)
    # 解压后统计类别目录，便于确认结构正确
    classes = [p.name for p in dest.rglob("*") if p.is_dir() and any(
        f.suffix.lower() in {".jpg", ".jpeg", ".png"} for f in p.iterdir() if f.is_file()
    )]
    print(f"    识别到 {len(classes)} 个图片目录: {classes[:8]}{'...' if len(classes) > 8 else ''}")


# ---------------------------------------------------------------- Kaggle

def download_kaggle(spec: dict, key: str, raw_root: Path, dry_run: bool) -> None:
    """Kaggle 公开数据集的下载端点无需凭据（2026-10-20 实测 HTTP 200）。

    若某数据集要求接受规则或转为私有，端点会返回非 zip 内容，此时提示改用 CLI。
    """
    slug = spec.get("slug")
    url = f"https://www.kaggle.com/api/v1/datasets/download/{slug}"
    zip_path = raw_root / f"{key}.zip"
    dest = raw_root / key

    if dry_run:
        print(f"    [dry-run] GET {url} -> {zip_path.name} -> 解压到 {dest}")
        return

    if not zip_path.exists():
        print(f"    下载 {url}")
        _download(url, zip_path)
    else:
        print(f"    已存在: {zip_path.name}")

    if not zipfile.is_zipfile(zip_path):
        print("    ! 返回内容不是 ZIP。该数据集可能需要登录/接受规则，请改用 kaggle CLI 并配置凭据。")
        return

    _extract_zip(zip_path, dest)
    classes = [p.name for p in dest.rglob("*") if p.is_dir() and any(
        f.suffix.lower() in {".jpg", ".jpeg", ".png"} for f in p.iterdir() if f.is_file()
    )]
    print(f"    识别到 {len(classes)} 个图片目录: {classes[:8]}{'...' if len(classes) > 8 else ''}")


# ---------------------------------------------------------------- 主流程

def main() -> None:
    parser = argparse.ArgumentParser(description="下载公开数据集")
    parser.add_argument("--raw-root", default=str(RAW_ROOT))
    parser.add_argument("--only", default=None, help="逗号分隔的 dataset key")
    parser.add_argument("--all", action="store_true", help="处理所有数据集")
    parser.add_argument("--list", action="store_true", help="只列出数据集与下载方式")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-size-gb", type=float, default=6.0,
                        help="跳过超过该大小的单个文件（默认 6GB）")
    args = parser.parse_args()

    raw_root = Path(args.raw_root)
    registry = {d["key"]: d for d in DATASETS}
    specs = DOWNLOAD_SPECS

    if args.list:
        print(f"{'key':24s} {'方式':18s} 说明")
        print("-" * 90)
        for key, spec in specs.items():
            entry = registry.get(key, {})
            kind = spec["type"]
            extra = spec.get("slug") or spec.get("record") or spec.get("id") or spec.get("note", "")
            print(f"{key:24s} {kind:18s} {entry.get('name', '')} | {extra}")
        return

    keys = list(specs) if args.all else ([k.strip() for k in args.only.split(",")] if args.only else [])
    if not keys:
        parser.error("请指定 --only 或 --all（或 --list 查看）")

    raw_root.mkdir(parents=True, exist_ok=True)
    for key in keys:
        spec = specs.get(key)
        if spec is None:
            print(f"\n[{key}] 未登记下载规格，跳过")
            continue
        print(f"\n[{key}] {registry.get(key, {}).get('name', '')}")
        dest = raw_root / key
        kind = spec["type"]
        try:
            if kind == "zenodo":
                download_zenodo(spec, dest, args.max_size_gb, args.dry_run)
            elif kind == "mendeley":
                prepare_mendeley(spec, key, raw_root, args.dry_run)
            elif kind == "kaggle":
                download_kaggle(spec, key, raw_root, args.dry_run)
            else:
                print(f"    手动获取：{spec.get('note') or registry.get(key, {}).get('url', '')}")
        except Exception as e:  # noqa: BLE001
            print(f"    ! 失败：{type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
