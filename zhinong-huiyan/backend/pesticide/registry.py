"""
农药登记库 —— 导入与查询。

红线 #3：药品名称与剂量只能来自检索，禁止模型生成。因此本模块只做
"把结构化登记数据入库 / 按病害查出来"，不做任何补全或推断：
缺剂量就是缺，缺登记证号就是缺，绝不猜。
"""
import argparse
import csv
import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from models import PesticideEntry
from labels import CROP_CLASSES, DISEASE_CLASSES

REQUIRED_FIELDS = ("disease_name", "product_name", "source")

# 允许导入的字段白名单；多余字段直接忽略，避免把来源文件的其他列带进库
ALLOWED_FIELDS = (
    "crop_type", "disease_name", "product_name", "active_ingredient",
    "formulation", "dosage", "safe_interval_days", "registration_no",
    "manufacturer", "source", "source_url", "verified", "notes",
)

_TRUTHY = {"1", "true", "yes", "y", "是", "已校审", "已校对"}


def _to_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in _TRUTHY


def _clean(record: Dict) -> Dict:
    """校验并规整一条记录。缺必填字段或类型不对时抛 ValueError。"""
    row = {k: record.get(k) for k in ALLOWED_FIELDS}
    for key in REQUIRED_FIELDS:
        if not str(row.get(key) or "").strip():
            raise ValueError(f"缺少必填字段 {key}")
    for key in ("crop_type", "disease_name", "product_name", "active_ingredient",
                "formulation", "dosage", "registration_no", "manufacturer",
                "source", "source_url", "notes"):
        if row.get(key) is not None:
            row[key] = str(row[key]).strip() or None

    row["verified"] = _to_bool(row.get("verified"))

    # 标签空间校验：模型只会用 DISEASE_CLASSES 里的名称查询，
    # 写错的条目导入后永远查不到，必须在入库前拦住。
    if row["disease_name"] not in DISEASE_CLASSES:
        raise ValueError(
            f"disease_name {row['disease_name']!r} 不在模型标签空间内，"
            f"可用值: {'、'.join(DISEASE_CLASSES)}"
        )
    if row.get("crop_type") and row["crop_type"] not in CROP_CLASSES:
        raise ValueError(
            f"crop_type {row['crop_type']!r} 不在作物清单内，"
            f"可用值: {'、'.join(CROP_CLASSES)}"
        )

    if row.get("safe_interval_days") in ("", None):
        row["safe_interval_days"] = None
    else:
        try:
            row["safe_interval_days"] = int(row["safe_interval_days"])
        except (TypeError, ValueError):
            raise ValueError("safe_interval_days 必须是整数") from None

    # 已校审却没有剂量 = 数据本身不完整，拒绝入库。
    # 否则查询端会把它当成"有登记数据可用"，反而更危险。
    if row["verified"] and not row.get("dosage"):
        raise ValueError("verified=true 的条目必须提供 dosage")
    return row


def load_file(path: str | Path) -> List[Dict]:
    """读取 JSON 数组或 CSV（UTF-8，首行为表头）。"""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as f:
            return [dict(r) for r in csv.DictReader(f)]
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("JSON 顶层必须是数组")
    return data


def import_entries(db: Session, records: Iterable[Dict], replace: bool = False) -> Dict:
    """按 (作物, 病害, 药品, 剂型) 去重写入。

    replace=False 时已存在的行保持不变（默认，避免导入样例覆盖人工校对结果）；
    replace=True 时更新已有行。
    """
    stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": []}
    for i, record in enumerate(records):
        try:
            row = _clean(record)
        except ValueError as e:
            stats["errors"].append(f"第 {i + 1} 条: {e}")
            continue

        existing = (
            db.query(PesticideEntry)
            .filter_by(
                crop_type=row["crop_type"],
                disease_name=row["disease_name"],
                product_name=row["product_name"],
                formulation=row["formulation"],
            )
            .first()
        )
        if existing:
            if replace:
                for key, value in row.items():
                    setattr(existing, key, value)
                stats["updated"] += 1
            else:
                stats["skipped"] += 1
            continue

        db.add(PesticideEntry(**row))
        stats["inserted"] += 1

    db.commit()
    return stats


def query_entries(db: Session, disease_name: str, crop_type: Optional[str] = None) -> List[PesticideEntry]:
    """按病害查登记条目；作物只用于收窄，不匹配时退回全部同病害条目。

    排序把已校审的放前面——调用方据此决定能否下发剂量。
    """
    name = (disease_name or "").strip()
    if not name:
        return []

    rows = db.query(PesticideEntry).filter(PesticideEntry.disease_name == name).all()
    if not rows:
        rows = (
            db.query(PesticideEntry)
            .filter(PesticideEntry.disease_name.like(f"%{name}%"))
            .all()
        )
    if crop_type and rows:
        narrowed = [r for r in rows if not r.crop_type or r.crop_type == crop_type]
        if narrowed:
            rows = narrowed

    return sorted(rows, key=lambda r: (not r.verified, r.id))


def validate_file(path: str | Path) -> Dict:
    """只校验不写库：用于人工收集数据后的自检。"""
    records = load_file(path)
    errors = []
    valid = 0
    for i, record in enumerate(records, 1):
        try:
            _clean(record)
            valid += 1
        except ValueError as e:
            errors.append(f"第 {i} 条: {e}")
    return {"total": len(records), "valid": valid, "errors": errors}


def write_template(path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        csv.DictWriter(f, fieldnames=ALLOWED_FIELDS).writeheader()
    print(f"已生成空模板: {path}")
    print("字段说明见 docs/pesticide_data.md；verified=true 时必须填 dosage。")


def _main() -> None:
    from database import Base, SessionLocal, engine

    Base.metadata.create_all(bind=engine)  # 允许在服务未启动时单独导入

    ap = argparse.ArgumentParser(description="农药登记库导入工具")
    ap.add_argument("--file", help="JSON 数组或 CSV 文件")
    ap.add_argument("--seed", action="store_true", help="导入内置样例（全部标记未校审）")
    ap.add_argument("--replace", action="store_true", help="更新已存在的同键条目")
    ap.add_argument("--list", action="store_true", help="列出库中条目")
    ap.add_argument("--template", metavar="CSV", help="生成空白 CSV 模板")
    ap.add_argument("--check", metavar="CSV", help="只校验文件，不写库")
    args = ap.parse_args()

    if args.template:
        write_template(args.template)
        return

    if args.check:
        result = validate_file(args.check)
        print(f"共 {result['total']} 条，通过校验 {result['valid']} 条")
        for err in result["errors"]:
            print(f"  [错误] {err}")
        return

    db = SessionLocal()
    try:
        if args.list:
            rows = db.query(PesticideEntry).order_by(PesticideEntry.disease_name).all()
            print(f"共 {len(rows)} 条")
            for r in rows:
                flag = "已校审" if r.verified else "未校审"
                print(f"  [{flag}] {r.crop_type or '-'} / {r.disease_name} / "
                      f"{r.product_name} {r.formulation or ''} / 剂量={r.dosage or '-'}")
            return

        path = args.file or (Path(__file__).with_name("seed.json") if args.seed else None)
        if not path:
            ap.error("需要 --file / --seed / --list / --template / --check 之一")
        stats = import_entries(db, load_file(path), replace=args.replace)
        print(f"导入完成: 新增 {stats['inserted']} / 更新 {stats['updated']} / "
              f"跳过 {stats['skipped']}")
        for err in stats["errors"]:
            print(f"  [跳过] {err}")
    finally:
        db.close()


if __name__ == "__main__":
    _main()
