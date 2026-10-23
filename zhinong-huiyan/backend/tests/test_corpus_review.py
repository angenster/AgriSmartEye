"""语料校对：导出、回填、通过与撤销，以及 reviewed 状态切换。"""
import csv
import tempfile
import unittest
from pathlib import Path

from rag import review_corpus, seed_corpus


class CorpusReviewTest(unittest.TestCase):
    def setUp(self):
        self._orig_path = seed_corpus.REVIEWS_PATH
        self.tmp = Path(tempfile.mkdtemp())
        seed_corpus.REVIEWS_PATH = self.tmp / "corpus_reviews.json"
        self.csv_path = self.tmp / "review.csv"

    def tearDown(self):
        seed_corpus.REVIEWS_PATH = self._orig_path

    def _export(self):
        review_corpus.export_csv(self.csv_path)
        with self.csv_path.open(encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))

    def _rewrite(self, rows):
        with self.csv_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=review_corpus.FIELDS)
            writer.writeheader()
            writer.writerows(rows)

    def _chunk(self, name):
        return next(c for c in seed_corpus.to_chunks() if c["ref_id"] == name)

    def test_export_covers_all_and_has_sources_column(self):
        rows = self._export()
        self.assertEqual(len(rows), 42)
        self.assertIn("sources", rows[0])
        # 12 个可触达条目中至少芒果白粉病有出处
        target = next(r for r in rows if r["name"] == "芒果白粉病")
        self.assertTrue(target["sources"])

    def test_approve_switches_to_manual_reviewed(self):
        rows = self._export()
        name = rows[0]["name"]
        rows[0].update(verdict="通过", reviewer="测试老师", notes="单元测试")
        self._rewrite(rows)

        review_corpus.apply_csv(self.csv_path)
        self.assertTrue(seed_corpus.REVIEWS_PATH.exists())
        chunk = self._chunk(name)
        self.assertEqual(chunk["source"], seed_corpus.REVIEWED_SOURCE_TAG)
        self.assertTrue(chunk["metadata"]["reviewed"])
        self.assertEqual(chunk["metadata"]["reviewer"], "测试老师")

    def test_approve_without_reviewer_is_ignored(self):
        rows = self._export()
        name = rows[0]["name"]
        rows[0].update(verdict="通过", reviewer="")
        self._rewrite(rows)

        review_corpus.apply_csv(self.csv_path)
        chunk = self._chunk(name)
        self.assertEqual(chunk["source"], seed_corpus.SOURCE_TAG)
        self.assertFalse(chunk["metadata"]["reviewed"])

    def test_reject_revokes_previous_approval(self):
        rows = self._export()
        name = rows[0]["name"]
        rows[0].update(verdict="通过", reviewer="测试老师")
        self._rewrite(rows)
        review_corpus.apply_csv(self.csv_path)
        self.assertTrue(self._chunk(name)["metadata"]["reviewed"])

        rows = self._export()
        rows[0].update(verdict="需修改", reviewer="测试老师", notes="病原名有误")
        self._rewrite(rows)
        review_corpus.apply_csv(self.csv_path)

        chunk = self._chunk(name)
        self.assertEqual(chunk["source"], seed_corpus.SOURCE_TAG)
        self.assertFalse(chunk["metadata"]["reviewed"])

    def test_unknown_entry_is_ignored(self):
        rows = self._export()
        rows.append({k: "" for k in review_corpus.FIELDS})
        rows[-1].update(name="不存在的病害", verdict="通过", reviewer="测试老师")
        self._rewrite(rows)
        review_corpus.apply_csv(self.csv_path)  # 不抛错，且不影响 42 条
        self.assertEqual(len(seed_corpus.to_chunks()), 42)


if __name__ == "__main__":
    unittest.main()
