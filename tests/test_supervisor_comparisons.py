"""Check frozen-source integrity and the scope of the additional reporting."""

from __future__ import annotations

import csv
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "supervisor_comparisons", ROOT / "scripts/render_supervisor_comparisons.py"
)
assert SPEC is not None and SPEC.loader is not None
REPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REPORT)
RUN = ROOT / "reports/confirmatory" / REPORT.RUN_NAME
SOURCE_AVAILABLE = all((RUN / name).is_file() for name in ("manifest.json", "completion.json", "fold_metrics.csv", "inference.json")) and (ROOT.parent / "thesis-overleaf/tables/table_robustness_coverage.tex").is_file()


def _fictional_rows() -> list[dict[str, str]]:
    rows = []
    pairs = [(repeat, fold) for repeat in range(1, 6) for fold in range(1, 6)]
    for cohort in REPORT.COHORTS:
        for model in REPORT.MODELS:
            selected = pairs[:REPORT.EXPECTED_COUNTS[cohort]] if model == "bayesian_horseshoe" else pairs
            for repeat, fold in selected:
                rows.append({"dataset": cohort, "model_key": model, "repeat": str(repeat), "fold": str(fold),
                             "ibs": str(0.1 + 0.001 * fold), "mean_auc": str(0.6 + 0.001 * fold),
                             "cell_content_sha256": "a" * 64,
                             "n_train": "80", "n_validation": "20", "events_train": "40", "events_validation": "10",
                             "horizon_1": "1", "horizon_2": "2", "horizon_3": "3"})
    return rows


class SupervisorComparisonsTests(unittest.TestCase):
    @unittest.skipUnless(SOURCE_AVAILABLE, "Original confirmatory release is not restored")
    def test_matching_and_bootstrap_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            provenance = REPORT.build_report(RUN, output)
            with (output / "matched_fold_metrics.csv").open(newline="") as stream:
                matched = list(csv.DictReader(stream))
            with (output / "paired_ibs_bootstrap.csv").open(newline="") as stream:
                bootstrap = list(csv.DictReader(stream))
            self.assertEqual(provenance["source_accepted_rows"], 430)
            self.assertEqual(len(matched), 18)
            self.assertEqual(len(bootstrap), 5)
            for cohort, count in {"gbsg2": 7, "whas500": 25, "metabric": 23}.items():
                self.assertEqual({int(row["n_matched_folds"]) for row in matched if row["dataset"] == cohort}, {count})
            gbsg = {row["model_key"]: row for row in matched if row["dataset"] == "gbsg2"}
            self.assertEqual(f"{float(gbsg['bayesian_horseshoe']['mean_auc']):.6f}", "0.753046")
            self.assertEqual(f"{float(gbsg['random_survival_forest']['mean_auc']):.6f}", "0.768334")
            whas = next(row for row in bootstrap if row["dataset"] == "whas500" and row["model_a"] == "Normal" and row["model_b"] == "Spike-and-Slab")
            self.assertLess(float(whas["corrected_lower"]), 0)
            self.assertGreater(float(whas["bootstrap_lower"]), 0)
            self.assertEqual(int(whas["n_successful"]), 1000)
            self.assertFalse(json.loads((output / "provenance.json").read_text())["new_fitting"])
            for kind in ("coverage", "diagnostics"):
                name = f"table_robustness_{kind}.tex"
                original = (ROOT.parent / "thesis-overleaf/tables" / name).read_text()
                revised = (output / name).read_text()
                self.assertEqual([line for line in original.splitlines() if " & " in line],
                                 [line for line in revised.splitlines() if " & " in line])
                self.assertIn("825 model--condition--fold outcomes", revised)
            self.assertIn("885 underlying Bayesian fits", (output / "table_robustness_coverage.tex").read_text())

    def test_duplicate_fold_cannot_change_subset_mean(self) -> None:
        rows = _fictional_rows()
        with self.assertRaisesRegex(ValueError, "Duplicate outcome"):
            REPORT._matched_rows(rows + [rows[0]])

    def test_missing_comparator_fold_is_rejected(self) -> None:
        rows = _fictional_rows()
        with self.assertRaises(ValueError):
            REPORT._matched_rows(rows[1:])

    @unittest.skipUnless(SOURCE_AVAILABLE, "Original confirmatory release is not restored")
    def test_changed_aggregate_is_rejected_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "source"
            copied.mkdir()
            for name in ("manifest.json", "completion.json", "fold_metrics.csv", "inference.json"):
                shutil.copyfile(RUN / name, copied / name)
            with (copied / "fold_metrics.csv").open("a") as stream:
                stream.write("\n")
            output = Path(temporary) / "output"
            with self.assertRaisesRegex(ValueError, "Frozen aggregate hash mismatch"):
                REPORT.build_report(copied, output)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
