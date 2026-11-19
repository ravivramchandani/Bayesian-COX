"""Protect complete coefficient coverage and paired event/parameter denominators."""

from __future__ import annotations

import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "completion", ROOT / "scripts/render_prior_comparison_completion.py"
)
assert SPEC is not None and SPEC.loader is not None
REPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REPORT)
THESIS = ROOT.parent / "thesis-overleaf"
EVIDENCE = ROOT / "reports/tables/thesis_reporting_completion"


def read(name: Path) -> list[dict[str, str]]:
    with name.open(newline="") as stream:
        return list(csv.DictReader(stream))


class PriorComparisonCompletionTests(unittest.TestCase):
    def test_full_coefficient_coverage_and_mismatched_scale_rejection(self) -> None:
        rows = read(THESIS / "report_summaries/examiner_polish/posterior_matched_all_features.csv")
        rows = REPORT.add_absolute_means(rows, read(
            THESIS / "report_summaries/examiner_polish/posterior_matched_by_fold.csv"))
        for cohort, (features, _) in REPORT.COUNTS.items():
            table = REPORT.posterior_table(rows, cohort)
            self.assertEqual(sum(table.count(f" & {p} & ") for p in "NHS"), features * 3)
        reduced = [r for r in rows if not (r["dataset"] == "gbsg2"
                   and r["feature"] == "menostat=Pre")]
        with self.assertRaisesRegex(ValueError, "coefficient coverage"):
            REPORT.posterior_table(reduced, "gbsg2")
        changed = [dict(r) for r in rows]
        changed[0]["reference"] = "unmatched"
        with self.assertRaisesRegex(ValueError, "coefficient coding"):
            REPORT.posterior_table(changed, changed[0]["dataset"])

    def test_absolute_means_do_not_cancel_opposite_fold_signs(self) -> None:
        common = {"dataset": "cohort", "feature": "x", "model_key": "normal"}
        rows = [{**common, "n_matched_folds": "2", "mean_beta": "-0.5"}]
        folds = [{**common, "repeat": "1", "fold": str(i), "beta_mean": str(beta)}
                 for i, beta in ((1, -2), (2, 1))]
        enriched = REPORT.add_absolute_means(rows, folds)
        self.assertEqual(float(enriched[0]["mean_absolute_beta"]), 1.5)
        with self.assertRaisesRegex(ValueError, "repeated posterior folds"):
            REPORT.add_absolute_means(rows, [folds[0], folds[0]])

    def test_exact_ratios_and_shared_subset_validation(self) -> None:
        primary = read(EVIDENCE / "outer_training_epc.csv")
        quarter = read(EVIDENCE / "quarter_training_cells_epc.csv")
        rows = REPORT.information_rows(primary, quarter)
        self.assertEqual([(r["minimum_exact"], r["maximum_exact"]) for r in rows],
                         [("239/8", "30"), ("172/9", "172/9"), ("914/19", "916/15"),
                          ("59/8", "59/8"), ("40/9", "40/9"), ("12", "114/7")])
        changed = [dict(r) for r in quarter]
        changed[0]["events_train"] = str(int(changed[0]["events_train"]) + 1)
        with self.assertRaisesRegex(ValueError, "Unmatched training subset"):
            REPORT.information_rows(primary, changed)

    def test_changed_source_rejected_and_render_matches_saved_tables(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "changed.csv"
            path.write_text("value\n1\n")
            with self.assertRaisesRegex(ValueError, "Source hash mismatch"):
                REPORT.read_verified(path, "0" * 64)
            output = Path(directory) / "rendered"
            REPORT.render(THESIS, EVIDENCE, output)
            for table in output.glob("*.tex"):
                self.assertEqual(table.read_bytes(), (THESIS /
                                 "report_summaries/prior_comparison_completion" / table.name).read_bytes())


if __name__ == "__main__":
    unittest.main()
