"""Check matching, scale preservation and exact use of archived diagnostics."""

from __future__ import annotations

import copy
import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "examiner_summaries", ROOT / "scripts/render_examiner_summaries.py"
)
assert SPEC is not None and SPEC.loader is not None
REPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REPORT)
RUN = ROOT / "reports/confirmatory" / REPORT.RUN_NAME
ASSETS = ROOT.parent / "thesis-overleaf/build/examiner-polish-20261119/source_assets"


def _cells() -> list[tuple[str, dict]]:
    cells = []
    for cohort in REPORT.COHORTS:
        for fold in (1, 2):
            for index, model in enumerate(REPORT.PRIORS):
                features = ("age", "stage=B")
                preprocessing = {
                    "feature_names": list(features),
                    "feature_groups": {"age": "age", "stage=B": "stage"},
                    "category_levels": {"stage": ["A", "B"]},
                    "ordinal_maps": {},
                    "scaling": {"age": {"mean": 50, "scale": 5 * fold}},
                    "training_state_sha256": str(fold) * 64,
                }
                details = {
                    "coefficient_summary": [
                        {
                            "feature": feature,
                            "coef (beta_mean)": fold + 0.1 * index,
                            "95% Credible Lower": 0.5 if fold == 1 else 1.2,
                            "95% Credible Upper": 1.5 if fold == 1 else 1.8,
                            "Prob(HR > 1)": 0.7 + 0.1 * index,
                        }
                        for feature in features
                    ],
                    "inclusion_signal": [
                        {"feature": feature, "continuous_inclusion_weight": 0.3 + 0.1 * fold}
                        for feature in features
                    ]
                    if model == "bayesian_spike_slab"
                    else None,
                }
                cell = {
                    "dataset": cohort,
                    "repeat": 1,
                    "fold": fold,
                    "model_key": model,
                    "status": "complete",
                    "train_subject_ids": [1, 2],
                    "validation_subject_ids": [3],
                    "preprocessing": preprocessing,
                    "model_details": details,
                    "cell_content_sha256": str(index) * 64,
                }
                cells.append((f"{cohort}/{fold}/{model}", cell))
    return cells


class ExaminerSummaryTests(unittest.TestCase):
    def test_equal_fold_weighting_and_stored_hr_limits(self) -> None:
        with patch.dict(REPORT.MATCHED_COUNTS, {x: 2 for x in REPORT.COHORTS}, clear=True):
            rows, folds, excluded, selected = REPORT._posterior_rows(_cells())
        row = next(
            r
            for r in rows
            if r["dataset"] == "gbsg2"
            and r["feature"] == "age"
            and r["model_key"] == "bayesian_spike_slab"
        )
        self.assertAlmostEqual(row["mean_beta"], 1.7)
        self.assertAlmostEqual(row["mean_hr_interval_width"], 0.8)
        self.assertAlmostEqual(row["fraction_hr_intervals_excluding_one"], 0.5)
        self.assertAlmostEqual(row["mean_absolute_beta_difference_from_normal"], 0.2)
        self.assertAlmostEqual(row["mean_continuous_mixture_variance_weight"], 0.45)
        self.assertEqual(selected["gbsg2"], [[1, 1], [1, 2]])
        self.assertEqual(excluded, [])
        scales = {r["training_scale"] for r in folds if r["feature"] == "age"}
        self.assertEqual(scales, {5, 10})

    def test_reference_drift_is_excluded_and_within_fold_mismatch_rejected(self) -> None:
        cells = _cells()
        for _, cell in cells:
            if cell["dataset"] == "gbsg2" and cell["fold"] == 2:
                cell["preprocessing"]["category_levels"]["stage"] = ["B", "A"]
        with patch.dict(REPORT.MATCHED_COUNTS, {x: 2 for x in REPORT.COHORTS}, clear=True):
            rows, _, excluded, _ = REPORT._posterior_rows(cells)
            self.assertEqual(
                excluded,
                [
                    {
                        "dataset": "gbsg2",
                        "feature": "stage=B",
                        "reason": "coding or reference differs across folds",
                    }
                ],
            )
            self.assertFalse(
                any(r["dataset"] == "gbsg2" and r["feature"] == "stage=B" for r in rows)
            )
            bad = copy.deepcopy(cells)
            bad[0][1]["preprocessing"]["scaling"]["age"]["scale"] = 99
            with self.assertRaisesRegex(ValueError, "Unmatched preprocessing"):
                REPORT._posterior_rows(bad)

    def test_rejection_cause_comes_from_stored_flags(self) -> None:
        cell = {
            "path": "example",
            "dataset": "gbsg2",
            "model_key": "bayesian_horseshoe",
            "repeat": 1,
            "fold": 1,
            "status": "failed_diagnostics",
            "cell_content_sha256": "0" * 64,
            "fit_attempts": [
                {
                    "diagnostics": {
                        "converged": False,
                        "failures": ["3 divergent transitions (0.04% of draws)"],
                        "n_divergent": 3,
                        "n_max_tree_depth": 0,
                        "max_tree_depth": 8,
                        "r_hat_max": 1.0,
                        "ess_bulk_min": 2000,
                        "ess_tail_min": 2100,
                        "bfmi_min": 0.8,
                    }
                }
            ],
        }
        summary, rows = REPORT._diagnostic_rows([cell], "Original")
        self.assertEqual(rows[0]["failure_categories"], "divergences")
        self.assertEqual(summary[0]["divergence_only_failures"], 1)
        self.assertEqual(summary[0]["failures_involving_tree_depth"], 0)
        self.assertEqual(summary[0]["failures_involving_rhat"], 0)
        cell["fit_attempts"][0]["diagnostics"]["failures"] = ["unknown rejection"]
        with self.assertRaisesRegex(ValueError, "Unknown recorded"):
            REPORT._diagnostic_rows([cell], "Original")

    def test_quarter_training_uses_identical_matched_validation_folds(self) -> None:
        full, reduced = [], []
        for index, model in enumerate(REPORT.PRIORS):
            for fold in (1, 2):
                cell = {
                    "path": f"{model}/{fold}",
                    "dataset": "whas500",
                    "model_key": model,
                    "repeat": 1,
                    "fold": fold,
                    "status": "complete",
                    "condition": {},
                    "validation_subject_ids": [fold],
                    "metrics": {"ibs": 0.1 + index * 0.01 + fold * 0.001},
                    "cell_content_sha256": "0" * 64,
                }
                full.append(cell)
                altered = copy.deepcopy(cell)
                altered["condition"] = {"condition_id": "rq2_fraction_025_observed"}
                altered["metrics"]["ibs"] += 0.02
                reduced.append(altered)
        summary, raw = REPORT._reduced_training_rows(reduced, full)
        self.assertEqual(len(raw), 12)
        normal_full = next(
            r
            for r in summary
            if r["model_key"] == "bayesian_normal" and r["training_fraction"] == 1
        )
        normal_reduced = next(
            r
            for r in summary
            if r["model_key"] == "bayesian_normal" and r["training_fraction"] == 0.25
        )
        self.assertAlmostEqual(normal_reduced["mean_ibs"] - normal_full["mean_ibs"], 0.02)
        self.assertEqual(normal_reduced["n_matched_folds"], 2)
        reduced[0]["validation_subject_ids"] = [99]
        with self.assertRaisesRegex(ValueError, "evaluation subjects differ"):
            REPORT._reduced_training_rows(reduced, full)

    @unittest.skipUnless(
        (RUN / "completion.json").is_file()
        and all((ASSETS / name).is_file() for name in REPORT.ARCHIVES),
        "Frozen programme archives not restored",
    )
    def test_frozen_sources_to_portable_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            provenance = REPORT.build_report(RUN, ASSETS, output)
            self.assertFalse(provenance["fitting_performed"])
            self.assertFalse(provenance["simulation_performed"])
            self.assertEqual(
                provenance["matched_fold_counts"], {"gbsg2": 7, "whas500": 25, "metabric": 23}
            )
            self.assertEqual(provenance["attribution_failure_count"], 102)
            self.assertEqual(provenance["supplementary_sources"]["verified_robustness_cells"], 825)
            with (output / "diagnostic_failures_by_outcome.csv").open() as stream:
                failures = list(csv.DictReader(stream))
            self.assertEqual(len(failures), 75)
            self.assertEqual(sum(r["programme"] == "Original" for r in failures), 20)
            self.assertEqual(
                {r["failure_categories"] for r in failures if r["programme"] == "Original"},
                {"divergences"},
            )
            self.assertEqual(len(provenance["outputs"]), 16)
            self.assertIn(
                "not a pooled credible interval",
                (output / "table_posterior_summary.tex").read_text(),
            )


if __name__ == "__main__":
    unittest.main()
