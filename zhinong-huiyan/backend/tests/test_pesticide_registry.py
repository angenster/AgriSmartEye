"""农药登记库：导入校验、去重、查询排序与工具层剂量隐藏。"""
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
from models import PesticideEntry
from pesticide import registry


def _row(**over):
    base = {
        "crop_type": "芒果",
        "disease_name": "芒果炭疽病",
        "product_name": "测试药剂",
        "formulation": "水乳剂",
        "dosage": "稀释1500倍",
        "source": "unit-test",
        "verified": True,
    }
    base.update(over)
    return base


class PesticideRegistryTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    # ---------- 校验 ----------
    def test_verified_requires_dosage(self):
        with self.assertRaises(ValueError):
            registry._clean(_row(dosage=None))

    def test_unknown_disease_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            registry._clean(_row(disease_name="芒果炭疽"))
        self.assertIn("标签空间", str(ctx.exception))

    def test_unknown_crop_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            registry._clean(_row(crop_type="荔枝"))
        self.assertIn("作物清单", str(ctx.exception))

    def test_missing_required_field_rejected(self):
        with self.assertRaises(ValueError):
            registry._clean({"disease_name": "芒果炭疽病", "source": "x"})

    # ---------- 导入 ----------
    def test_import_dedupes_same_key(self):
        records = [_row(), _row()]
        stats = registry.import_entries(self.db, records)
        self.assertEqual(stats["inserted"], 1)
        self.assertEqual(stats["skipped"], 1)
        self.assertEqual(self.db.query(PesticideEntry).count(), 1)

    def test_import_replace_updates_existing(self):
        registry.import_entries(self.db, [_row()])
        stats = registry.import_entries(
            self.db, [_row(dosage="稀释2000倍")], replace=True
        )
        self.assertEqual(stats["updated"], 1)
        entry = self.db.query(PesticideEntry).one()
        self.assertEqual(entry.dosage, "稀释2000倍")

    def test_invalid_record_is_skipped_with_error(self):
        stats = registry.import_entries(self.db, [_row(verified=True, dosage=None)])
        self.assertEqual(stats["inserted"], 0)
        self.assertEqual(len(stats["errors"]), 1)

    # ---------- 查询 ----------
    def test_query_prefers_verified_and_narrows_crop(self):
        registry.import_entries(self.db, [
            _row(verified=False, dosage=None, product_name="未校审药剂"),
            _row(verified=True, product_name="已校审药剂"),
            _row(crop_type="香蕉", disease_name="芒果炭疽病",
                 product_name="错作物药剂", verified=True),
        ])
        rows = registry.query_entries(self.db, "芒果炭疽病", "芒果")
        self.assertEqual([r.product_name for r in rows],
                         ["已校审药剂", "未校审药剂"])

    def test_query_returns_empty_for_unknown(self):
        self.assertEqual(registry.query_entries(self.db, "香蕉枯萎病"), [])


if __name__ == "__main__":
    unittest.main()
