"""Protect the complete-pair sensitivity synthesis and unchanged numerical displays."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
THESIS = ROOT.parent / "thesis-overleaf"
SPEC = importlib.util.spec_from_file_location("v3", ROOT / "scripts/render_examiner_v3_completion.py")
assert SPEC is not None and SPEC.loader is not None
REPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REPORT)


class ExaminerV3CompletionTests(unittest.TestCase):
    def test_complete_pair_synthesis_excludes_anchors_and_partial_comparisons(self) -> None:
        with (THESIS / "generated/robustness_effects.csv").open(newline="") as stream:
            rows = list(csv.DictReader(stream))
        summary = REPORT.sensitivity_summary(rows)
        self.assertEqual((summary["eligible_contrasts"], summary["complete_contrasts"]), (38, 29))
        h = summary["priors"]["Horseshoe"]
        s = summary["priors"]["Spike-and-slab"]
        self.assertEqual(h["complete_contrasts"], 10)
        self.assertEqual(h["nominal_intervals_excluding_zero"], [])
        self.assertEqual(s["complete_contrasts"], 19)
        self.assertEqual([r["condition"] for r in s["nominal_intervals_excluding_zero"]],
                         ["baseline_intervals_10"])
        self.assertEqual(len(summary["single_pair_nonzero_intervals"]), 2)
        self.assertTrue(all(r["dataset"] == "gbsg2"
                           for r in summary["single_pair_nonzero_intervals"]))
        with self.assertRaisesRegex(ValueError, "Repeated sensitivity contrast"):
            REPORT.sensitivity_summary(rows + [rows[0]])

    def test_changed_source_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "input.csv"
            p.write_text("observed\n1\n")
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
            self.assertEqual(REPORT.verified(p, digest), p.read_bytes())
            p.write_text("observed\n2\n")
            with self.assertRaisesRegex(ValueError, "Source hash mismatch"):
                REPORT.verified(p, digest)

    def test_all_174_robustness_numerical_rows_are_preserved(self) -> None:
        def values(path: Path) -> list[list[str]]:
            return [[x.strip() for x in line.split(" & ")[-3:]]
                    for line in path.read_text().splitlines()
                    if line.startswith(("GBSG2 &", "METABRIC &", "WHAS500 &"))]

        old = values(THESIS / "tables/table_robustness_effects.tex")
        new = values(THESIS / "report_summaries/examiner_v3_presentation/table_robustness_effects.tex")
        self.assertEqual(len(old), 174)
        self.assertEqual(old, new)

    def test_replot_keeps_original_sources_and_summary(self) -> None:
        pins = ROOT / "reports/tables/examiner_v3_completion/source_hashes.json"
        with tempfile.TemporaryDirectory(dir=THESIS / "build") as directory:
            output = Path(directory)
            REPORT.render(THESIS, pins, output)
            self.assertGreater((output / "figure_calibration_examples.pdf").stat().st_size, 1000)
            summary = json.loads((output / "sensitivity_summary.json").read_text())
            self.assertEqual(summary["complete_contrasts"], 29)
            provenance = json.loads((output / "provenance.json").read_text())
            for name, expected in provenance["source_sha256"].items():
                self.assertEqual(hashlib.sha256((THESIS / name).read_bytes()).hexdigest(), expected)


if __name__ == "__main__":
    unittest.main()
