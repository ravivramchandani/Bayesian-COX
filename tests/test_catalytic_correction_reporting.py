"""Invented/injected fixtures only; no cohorts, traces, renderer or actual review."""

from __future__ import annotations

import importlib.util
import json
import math
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
HERE = REPO / "scripts/catalytic_correction/reporting"


def load_support(name: str, aliases: dict):
    """Load the pinned module while keeping fixture import aliases local."""
    spec = importlib.util.spec_from_file_location("_reporting_test_" + name, HERE / (name + ".py"))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    with patch.dict(sys.modules, aliases):
        spec.loader.exec_module(module)
    return module


core = load_support("support_core", {})
visual = load_support("corrected_pdf_qa", {"support_core": core})
reporting = load_support("reporting", {"support_core": core, "corrected_pdf_qa": visual})


def frozen(name: str):
    """Load only the exact copied support dependency for synthetic fixtures."""
    path = HERE / name
    spec = importlib.util.spec_from_file_location("_reporting_fixture_" + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


FROZEN = frozen("frozen_reporting.py")
ROSTER = frozen("frozen_qa_transfer.py")


def record(model: str, repeat: int, fold: int, *, failed: bool = False, p=2):
    """A fictional two-subject/three-training patient record, never cohort data."""
    cell = {
        "cell_id": FROZEN.cell_id("gbsg2", "clinical", repeat, fold, model, "full"),
        "dataset": "gbsg2",
        "setting": "clinical",
        "repeat": repeat,
        "fold": fold,
        "model_key": model,
        "condition": "full",
        "evidence_status": "post_hoc_extension",
        "status": "failed" if failed else "complete",
        "n_train": 3,
        "n_validation": 2,
        "events_train": 2,
        "p": p,
        "train_subject_ids": [1, 2, 3],
        "validation_subject_ids": [4, 5],
    }
    if not failed:
        cell["metrics"] = {"ibs": 0.12 if model.startswith("catalytic") else 0.13}
        cell["predictions"] = {
            "subject_ids": [4, 5],
            "training_time": [1, 2, 3],
            "training_event": [1, 1, 0],
            "observed_time": [2, 3],
            "observed_event": [1, 0],
            "horizons": [1, 2, 3],
            "ibs_grid": [1, 2, 3],
        }
    cell["cell_content_sha256"] = core.canonical(cell)
    return cell


def pair_refs(*, failures=0):
    """Return25 invented paired records for an existing frozen descriptive row."""
    left, right = {}, {}
    for repeat in range(1, 6):
        for fold in range(1, 6):
            index = (repeat - 1) * 5 + fold - 1
            a = record("catalytic_fixed", repeat, fold, failed=index < failures)
            b = record("cox_ph", repeat, fold)
            left[a["cell_id"]] = FROZEN.CellRef("mixed", "cells/" + a["cell_id"] + ".json", a)
            right[("gbsg2", "cox_ph", repeat, fold)] = FROZEN.CellRef(
                "primary", "fictional.json", b
            )
    return left, right


class Guards(unittest.TestCase):
    """Small metadata, portability, IO and frozen-scope guards."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="synthetic-reporting-qa-")
        self.root = Path(self.temp.name).resolve()
        self.science_before = {
            name for name in sys.modules if name == "src" or name.startswith("src.")
        }

    def tearDown(self):
        self.temp.cleanup()
        self.assertEqual(
            self.science_before,
            {name for name in sys.modules if name == "src" or name.startswith("src.")},
        )

    def test_duplicate_json_rejected(self):
        with self.assertRaises(ValueError):
            core.strict_json(b'{"x":1,"x":2}')

    def test_fresh_metadata_import_does_not_load_scientific_modules(self):
        code = """
import sys
sys.path.insert(0, sys.argv[1])
import corrected_pdf_qa
import reporting
import support_core
for root in ('src', 'numpy', 'pandas', 'pymc', 'arviz', 'pytensor', 'torch'):
    assert not any(name == root or name.startswith(root + '.') for name in sys.modules), root
"""
        process = subprocess.run(
            [sys.executable, "-I", "-B", "-c", code, str(HERE)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(process.returncode, 0, process.stderr)

    def test_nonfinite_json_rejected(self):
        for raw in (b'{"x":NaN}', b'{"x":Infinity}', b'{"x":1e999}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                core.strict_json(raw)

    def test_content_mismatch_rejected(self):
        value = core.seal({"x": 1})
        value["x"] = 2
        with self.assertRaises(ValueError):
            core.content(value)

    def test_seal_does_not_mutate(self):
        original = {"x": 1}
        value = core.seal(original)
        core.content(value)
        self.assertEqual(original, {"x": 1})

    def test_reseal_rejected(self):
        with self.assertRaises(ValueError):
            core.seal(core.seal({"x": 1}))

    def test_path_traversal_rejected(self):
        with self.assertRaises(ValueError):
            core.child(self.root, "../escape")

    def test_link_ancestor_rejected(self):
        target = self.root / "target"
        target.mkdir()
        alias = self.root / "alias"
        alias.symlink_to(target, target_is_directory=True)
        with self.assertRaises(ValueError):
            core.safe(alias / "missing")

    def test_snapshot_mutation_rejected(self):
        path = self.root / "data.json"
        path.write_text("{}")
        snapshot = core.Snapshot()
        snapshot.read("logical", path)
        path.write_text('{"x":1}')
        with self.assertRaises(ValueError):
            snapshot.recheck()

    def test_snapshot_duplicate_role_rejected(self):
        path = self.root / "data.json"
        path.write_text("{}")
        snapshot = core.Snapshot()
        snapshot.read("logical", path)
        with self.assertRaises(ValueError):
            snapshot.read("logical", path)

    def test_relocation_request_excluded_from_deterministic_lineage(self):
        snapshots = []
        for index in range(2):
            path = self.root / f"request{index}.json"
            path.write_text(json.dumps({"path": f"/different-host-{index}"}))
            fixed = self.root / f"fixed{index}.json"
            fixed.write_text('{"value":2}')
            snapshot = core.Snapshot()
            snapshot.read("invocation/request.json", path)
            snapshot.read("source/logical.json", fixed)
            snapshots.append(snapshot)
        self.assertEqual(snapshots[0].portable(), snapshots[1].portable())

    def test_write_collision_does_not_overwrite(self):
        path = self.root / "output.json"
        core.write_bytes_new(path, b"first")
        with self.assertRaises(FileExistsError):
            core.write_bytes_new(path, b"second")
        self.assertEqual(path.read_bytes(), b"first")
        self.assertFalse(list(self.root.glob(".support-pending-*")))

    def test_new_output_overlap_refused_before_creation(self):
        source = self.root / "source"
        source.mkdir()
        output = source / "output"
        with self.assertRaises(ValueError):
            core.new_directory(output, [source])
        self.assertFalse(output.exists())

    def test_frozen_scope_exact(self):
        scope = core.strict_json((HERE / "scope.json").read_bytes())
        FROZEN.check_scope(scope)
        self.assertEqual(len(FROZEN.expected_extension()), 1625)
        self.assertEqual(len(scope["rows"]), 123)

    def test_scope_change_refused(self):
        scope = core.strict_json((HERE / "scope.json").read_bytes())
        scope["rows"].pop()
        with self.assertRaises(ValueError):
            FROZEN.check_scope(scope)

    def test_missing_p_is_explicit(self):
        value = record("catalytic_fixed", 1, 1, failed=True, p=None)
        FROZEN.validate_record(value, "fictional")
        rows = FROZEN.dimension_rows(
            {value["cell_id"]: FROZEN.CellRef("mixed", "fictional.json", value)}
        )
        self.assertIsNone(rows[0]["p_over_n_train"])
        self.assertIsNone(rows[0]["events_over_p"])
        self.assertFalse(rows[0]["p_available"])

    def test_ratio_uses_actual_encoded_p(self):
        value = record("catalytic_fixed", 1, 1, p=527)
        FROZEN.validate_record(value, "fictional")
        row = FROZEN.dimension_rows(
            {value["cell_id"]: FROZEN.CellRef("mixed", "fictional.json", value)}
        )[0]
        self.assertEqual(row["p_over_n_train"], 527 / 3)
        self.assertEqual(row["events_over_p"], 2 / 527)

    def test_zero_p_refused(self):
        with self.assertRaises(ValueError):
            FROZEN.validate_record(record("catalytic_fixed", 1, 1, p=0), "fictional")

    def test_partial_pairs_never_call_interval(self):
        left, right = pair_refs(failures=1)

        def forbidden(*args, **kwargs):
            raise AssertionError("partial coverage must not calculate an interval")

        row = FROZEN.descriptive_row(FROZEN.expected_scope_rows()[0], left, right, forbidden)
        self.assertEqual(row["n_pairs"], 24)
        self.assertEqual(row["interval_status"], "partial_observed_pairs_no_interval")
        self.assertIsNone(row["confidence_lower"])
        self.assertEqual(row["paired_records"][0]["exclusions"], ["left_failed"])

    def test_zero_pairs_no_mean_or_interval(self):
        left, right = pair_refs(failures=25)
        row = FROZEN.descriptive_row(
            FROZEN.expected_scope_rows()[0], left, right, lambda *a, **k: None
        )
        self.assertEqual(row["n_pairs"], 0)
        self.assertIsNone(row["mean_difference"])
        self.assertEqual(row["interval_status"], "zero_pairs_no_interval")

    def test_complete_pairs_exact_frozen_interval_math(self):
        interval = frozen("frozen_repeated_cv.py")
        left, right = pair_refs()
        for index, ref in enumerate(left.values()):
            ref.record["metrics"]["ibs"] = 0.13 + index / 1000
        row = FROZEN.descriptive_row(
            FROZEN.expected_scope_rows()[0], left, right, interval.nadeau_bengio_paired_effect
        )
        expected = interval.nadeau_bengio_paired_effect(
            [0.13 + i / 1000 for i in range(25)],
            [0.13] * 25,
            n_repeats=5,
            n_folds=5,
            test_train_ratio=1 / 4,
            confidence_level=0.95,
        ).to_dict()
        for field in (
            "mean_difference",
            "standard_deviation",
            "corrected_standard_error",
            "confidence_lower",
            "confidence_upper",
        ):
            self.assertEqual(row[field], expected[field])
        self.assertAlmostEqual(
            row["corrected_standard_error"],
            math.sqrt((1 / 25 + 1 / 4) * (54.166666666666664 / 1000000)),
        )
        self.assertEqual(row["confidence_level"], 0.95)
        self.assertNotIn("p_value", row)
        self.assertNotIn("t_statistic", row)

    def test_patient_pair_mismatch_refused(self):
        a, b = record("catalytic_fixed", 1, 1), record("cox_ph", 1, 1)
        b["validation_subject_ids"] = [5, 4]
        with self.assertRaises(ValueError):
            FROZEN.assert_pair_alignment(
                FROZEN.CellRef("mixed", "a", a), FROZEN.CellRef("primary", "b", b)
            )

    def test_prediction_grid_mismatch_refused(self):
        a, b = record("catalytic_fixed", 1, 1), record("cox_ph", 1, 1)
        b["predictions"]["ibs_grid"] = [1, 2, 4]
        with self.assertRaises(ValueError):
            FROZEN.assert_pair_alignment(
                FROZEN.CellRef("mixed", "a", a), FROZEN.CellRef("primary", "b", b)
            )

    def test_frozen_visual_roster(self):
        self.assertEqual(len(ROSTER.expected_names()), 32)
        self.assertEqual(len(ROSTER.TABLE_SOURCES), 6)

    def test_formal27_links_keep_adr032_distinct(self):
        name = "catalytic_vs_original_priors"
        rows = [
            {
                "dataset": dataset,
                "left": model,
                "right": prior,
                "n_pairs": 24,
                "expected_pairs": 25,
                "status": "missing_fold_pairs",
                "horseshoe_reference": "ADR-032 post-hoc sampler"
                if prior == "bayesian_horseshoe"
                else None,
            }
            for dataset in FROZEN.DATASETS
            for model in FROZEN.CATALYTIC
            for prior in FROZEN.ORIGINAL[3:]
        ]
        summary = {name: {"estimable_contrasts": 0, "missing_fold_pairs": 27}}
        value = FROZEN.formal_links({name: {"contrasts": rows}}, summary)
        self.assertEqual(len(value["contrasts"]), 27)
        self.assertEqual(
            sum(row["right_identity"] == "ADR032_post_hoc_sampler" for row in value["contrasts"]), 9
        )
        self.assertTrue(all("p_value" not in row for row in value["contrasts"]))
        rows.pop()
        with self.assertRaises(ValueError):
            FROZEN.formal_links({name: {"contrasts": rows}}, summary)

    def render_fixture(self):
        """Build fictional renderer metadata/bytes without rendering any figure."""
        rendered, mixed_root = self.root / "render_fixture", self.root / "mixed_fixture"
        rendered.mkdir()
        mixed_root.mkdir()
        (mixed_root / "cells").mkdir()
        (mixed_root / "aggregates").mkdir()
        cells = {}
        for dataset, setting in ROSTER.COHORT_SETTINGS:
            relative = f"cells/{dataset}__{setting}__r01f01__catalytic_fixed__full.json"
            (mixed_root / relative).write_bytes(b"fictional cell metadata")
            cells[relative] = core.sha_bytes(b"fictional cell metadata")
        aggregate_map = {
            name: "aggregates/" + name
            for name in ("paired_families.json", "rq2_effects.json", "decision_curves.json")
        }
        aggregates = {}
        for relative in aggregate_map.values():
            (mixed_root / relative).write_bytes(b"fictional aggregate metadata")
            aggregates[relative] = core.sha_bytes(b"fictional aggregate metadata")
        figures = []
        digest = core.sha_bytes(b"fictional render bytes")
        for name in ROSTER.expected_names():
            if name.startswith("decision_"):
                sources = ["decision_curves.json"]
            elif name.startswith("paired_"):
                sources = ["paired_families.json"]
            elif name.startswith("rq2_"):
                sources = ["rq2_effects.json"]
            else:
                dataset, setting = next(
                    (d, s)
                    for d, s in ROSTER.COHORT_SETTINGS
                    if name in (f"{d}_{s}_ibs", f"{d}_{s}_calibration")
                )
                sources = sorted(
                    path
                    for path in cells
                    if Path(path).stem.startswith(dataset + "__" + setting + "__")
                )
            for suffix in ("pdf", "png"):
                (rendered / (name + "." + suffix)).write_bytes(b"fictional render bytes")
            figures.append(
                {
                    "name": name,
                    "source_files": sources,
                    "pdf_sha256": digest,
                    "png_sha256": digest,
                    "visual_review": "pending",
                }
            )
        tables = []
        for name, sources in ROSTER.TABLE_SOURCES:
            (rendered / (name + ".csv")).write_bytes(b"fictional table bytes")
            tables.append(
                {
                    "name": name,
                    "source_files": sources,
                    "csv_sha256": core.sha_bytes(b"fictional table bytes"),
                }
            )
        renderer, adapter = self.root / "renderer.py", self.root / "adapter.py"
        renderer.write_bytes(b"fictional renderer source")
        adapter.write_bytes(b"fictional adapter source")
        render_sha, adapter_sha = (
            core.sha_bytes(renderer.read_bytes()),
            core.sha_bytes(adapter.read_bytes()),
        )
        lineage = {
            "source_completion_sha256": "fictional_completion",
            "source_manifest_sha256": "fictional_manifest",
            "renderer_sha256": render_sha,
            "evidence_status": "post_hoc_extension",
            "actual_visual_review": "pending; creation does not constitute QA",
            "figures": figures,
            "tables": tables,
        }
        core.write_new(rendered / "lineage.json", lineage)
        correction = {
            "evidence_status": core.EVIDENCE,
            "mixed_completion_sha256": "fictional_completion",
            "actual_verifier_capture_sha256": "fictional_capture",
            "original_renderer_sha256": render_sha,
            "adapter_sha256": adapter_sha,
            "original_renderer_lineage_sha256": core.sha_bytes(
                (rendered / "lineage.json").read_bytes()
            ),
            "actual_visual_review": "pending; rendering is not QA",
            "programme_complete": False,
            "aggregate_source_mapping": aggregate_map,
        }
        core.write_new(rendered / "mixed_correction_lineage.json", core.seal(correction))
        request = {
            "roots": {"rendered": str(rendered)},
            "files": {
                "renderer": {"path": str(renderer), "sha256": render_sha},
                "renderer_adapter": {"path": str(adapter), "sha256": adapter_sha},
                "source_capture": {"sha256": "fictional_capture"},
            },
        }
        mixed = {
            "root": mixed_root,
            "completion_sha256": "fictional_completion",
            "completion": {
                "manifest_sha256": "fictional_manifest",
                "cell_sha256": cells,
                "aggregate_sha256": aggregates,
            },
        }
        return request, mixed, {"reporting": FROZEN, "roster": ROSTER}, render_sha, adapter_sha

    def test_both_renderer_lineages_and_exact72_files_bound(self):
        request, mixed, deps, render_sha, adapter_sha = self.render_fixture()
        with (
            patch.object(core, "RENDERER_SHA", render_sha),
            patch.object(core, "RENDER_ADAPTER_SHA", adapter_sha),
        ):
            snapshot = core.Snapshot()
            result = visual.render_state(request, mixed, deps, snapshot)
            self.assertEqual(len(result["names"]), 32)
            self.assertEqual(len(result["tables"]), 6)
            self.assertEqual(
                result["source_bindings"]["mixed_correction_lineage_sha256"],
                snapshot.bindings["rendered/mixed_correction_lineage.json"]["sha256"],
            )
            snapshot.recheck()

    def test_renderer_lineage_disagreement_refused(self):
        request, mixed, deps, render_sha, adapter_sha = self.render_fixture()
        path = Path(request["roots"]["rendered"]) / "mixed_correction_lineage.json"
        value = core.strict_json(path.read_bytes())
        value.pop("content_sha256")
        value["original_renderer_lineage_sha256"] = "different"
        path.write_bytes(core.json_bytes(core.seal(value)))
        with (
            patch.object(core, "RENDERER_SHA", render_sha),
            patch.object(core, "RENDER_ADAPTER_SHA", adapter_sha),
            self.assertRaises(ValueError),
        ):
            visual.render_state(request, mixed, deps, core.Snapshot())

    def test_renderer_foreign_extra_file_refused(self):
        request, mixed, deps, render_sha, adapter_sha = self.render_fixture()
        (Path(request["roots"]["rendered"]) / "foreign.txt").write_text("fictional extra")
        with (
            patch.object(core, "RENDERER_SHA", render_sha),
            patch.object(core, "RENDER_ADAPTER_SHA", adapter_sha),
            self.assertRaises(ValueError),
        ):
            visual.render_state(request, mixed, deps, core.Snapshot())

    def test_visual_pending_cannot_attest(self):
        review = {
            "inventory_sha256": "fixture",
            "reviewer_role": "root",
            "reviewer_name": "",
            "attestation": "",
            "reviewed_at_utc": "",
            "figures": [],
        }
        with self.assertRaises(ValueError):
            visual.review_rows(review, ROSTER.expected_names(), "fixture")

    def test_named_root_required(self):
        review = self.complete_review()
        review["reviewer_role"] = "automation"
        with self.assertRaises(ValueError):
            visual.review_rows(review, ROSTER.expected_names(), "fixture")

    def complete_review(self):
        return {
            "inventory_sha256": "fixture",
            "reviewer_role": "root",
            "reviewer_name": "Synthetic fixture only",
            "attestation": ROSTER.ATTESTATION,
            "reviewed_at_utc": "2026-01-01T00:00:00+00:00",
            "figures": [
                {"name": name, "verdict": "pass", "issue": ""} for name in ROSTER.expected_names()
            ],
        }

    def test_all32_explicit_verdicts_required(self):
        review = self.complete_review()
        review["figures"].pop()
        with self.assertRaises(ValueError):
            visual.review_rows(review, ROSTER.expected_names(), "fixture")

    def test_review_order_bound(self):
        review = self.complete_review()
        review["figures"].reverse()
        with self.assertRaises(ValueError):
            visual.review_rows(review, ROSTER.expected_names(), "fixture")

    def test_failure_needs_issue(self):
        review = self.complete_review()
        review["figures"][0]["verdict"] = "fail"
        with self.assertRaises(ValueError):
            visual.review_rows(review, ROSTER.expected_names(), "fixture")

    def test_timezone_required(self):
        review = self.complete_review()
        review["reviewed_at_utc"] = "2026-01-01T00:00:00"
        with self.assertRaises(ValueError):
            visual.review_rows(review, ROSTER.expected_names(), "fixture")

    def test_partial_mixed_grid_refused_without_destination(self):
        mixed = self.root / "mixed"
        mixed.mkdir()
        document = core.seal(
            {
                "status": core.MIXED_STATUS,
                "evidence_status": core.EVIDENCE,
                "planned_logical_cells": 1625,
                "verified_logical_cells": 1624,
            }
        )
        path = mixed / "completion.json"
        path.write_bytes(core.json_bytes(document))
        request = {
            "roots": {"mixed_verified": str(mixed)},
            "files": {
                "mixed_completion": {"path": str(path), "sha256": core.sha_bytes(path.read_bytes())}
            },
        }
        with self.assertRaises(ValueError):
            core.load_mixed(request, core.Snapshot(), FROZEN)
        self.assertEqual({p.name for p in mixed.iterdir()}, {"completion.json"})

    def test_actual_interpreter_samefile_required(self):
        fake = self.root / "python"
        fake.write_text("fictional")
        with self.assertRaises(ValueError):
            core.runtime(fake)

    def test_numeric_thread_guard(self):
        with patch.dict(os.environ, {name: "1" for name in core.NUMERIC}):
            core.runtime(Path(sys.executable))
            with patch.dict(os.environ, {core.NUMERIC[0]: "2"}), self.assertRaises(ValueError):
                core.runtime(Path(sys.executable))

    def test_source_capture_rc_nonzero_refused(self):
        path = self.root / "capture.receipt.json"
        document = core.seal({"status": "mixed_verification_actual_rc0_captured", "exit_code": 1})
        path.write_bytes(core.json_bytes(document))
        request = {
            "files": {
                "source_capture": {"path": str(path), "sha256": core.sha_bytes(path.read_bytes())}
            }
        }
        with self.assertRaises(ValueError):
            core.validate_capture(request, "fictional", core.Snapshot())

    def capture_fixture(self):
        """Create small invented raw process evidence, never a verifier invocation."""
        prefix = "fixture"
        summary = {
            "status": core.MIXED_STATUS,
            "verified_logical_cells": 1625,
            "programme_complete": False,
        }
        stdout, stderr = (
            (json.dumps(summary, sort_keys=True) + "\n").encode(),
            b"fictional stderr retained\n",
        )
        for suffix, raw in (("stdout.log", stdout), ("stderr.log", stderr)):
            (self.root / (prefix + "." + suffix)).write_bytes(raw)
        attempt = core.seal(
            {
                "exit_code": 0,
                "launch_error": None,
                "stdout_sha256": core.sha_bytes(stdout),
                "stderr_sha256": core.sha_bytes(stderr),
            }
        )
        core.write_new(self.root / (prefix + ".attempt.json"), attempt)
        artifacts = {
            prefix + suffix: {
                "sha256": core.sha_bytes((self.root / (prefix + suffix)).read_bytes()),
                "bytes": (self.root / (prefix + suffix)).stat().st_size,
            }
            for suffix in (".stdout.log", ".stderr.log", ".attempt.json")
        }
        receipt = core.seal(
            {
                "status": "mixed_verification_actual_rc0_captured",
                "exit_code": 0,
                "completion_sha256": "fictional",
                "summary": summary,
                "artifacts": artifacts,
                "invocation_attempt_sha256": artifacts[prefix + ".attempt.json"]["sha256"],
                "stdout_path": "/historical-host/fixture.stdout.log",
                "stderr_path": "/historical-host/fixture.stderr.log",
                "stdout_sha256": core.sha_bytes(stdout),
                "stderr_sha256": core.sha_bytes(stderr),
            }
        )
        path = self.root / (prefix + ".receipt.json")
        core.write_new(path, receipt)
        return {
            "files": {
                "source_capture": {"path": str(path), "sha256": core.sha_bytes(path.read_bytes())}
            }
        }

    def test_actual_capture_checks_raw_siblings_after_relocation(self):
        request = self.capture_fixture()
        snapshot = core.Snapshot()
        result = core.validate_capture(request, "fictional", snapshot)
        self.assertEqual(result["exit_code"], 0)
        snapshot.recheck()

    def test_capture_changed_raw_stdout_refused(self):
        request = self.capture_fixture()
        (self.root / "fixture.stdout.log").write_bytes(b"changed")
        with self.assertRaises(ValueError):
            core.validate_capture(request, "fictional", core.Snapshot())

    def test_capture_residual_file_refused(self):
        request = self.capture_fixture()
        (self.root / "fixture.other").write_bytes(b"foreign")
        with self.assertRaises(ValueError):
            core.validate_capture(request, "fictional", core.Snapshot())

    def test_old_original_certificate_not_a_mixed_certificate(self):
        mixed = self.root / "mixed"
        mixed.mkdir()
        value = core.seal(
            {"status": "original_grid_complete", "evidence_status": "post_hoc_extension"}
        )
        path = mixed / "completion.json"
        core.write_new(path, value)
        request = {
            "roots": {"mixed_verified": str(mixed)},
            "files": {
                "mixed_completion": {"path": str(path), "sha256": core.sha_bytes(path.read_bytes())}
            },
        }
        with self.assertRaises(ValueError):
            core.load_mixed(request, core.Snapshot(), FROZEN)

    def test_incomplete_preparation_source_scope_refused(self):
        path = self.root / "fixture_preparation.json"
        core.write_new(
            path,
            core.seal(
                {
                    "status": "corrected_reporting_qa_adapters_prepared",
                    "actual_scientific_or_visual_execution": False,
                    "implementation_source_sha256": {},
                    "dependency_source_sha256": core.DEPENDENCY_PINS,
                }
            ),
        )
        request = {
            "preparation_receipt": {"path": str(path), "sha256": core.sha_bytes(path.read_bytes())}
        }
        with self.assertRaises(ValueError):
            core.bind_preparation(request, core.Snapshot())

    def test_sidecar_exact_inventory(self):
        root = self.root / "sidecar"
        root.mkdir()
        (root / "extra").mkdir()
        with self.assertRaises(ValueError):
            reporting.verify_existing(root, {}, {}, "fictional", core.Snapshot())

    def test_artifact_scope_cannot_expand(self):
        with self.assertRaises(ValueError):
            reporting.artifact_bindings({"made_up.csv": b"x"})

    def test_write_once_and_relocation_replay(self):
        artifacts = {name: ("fictional " + name).encode() for name in core.ARTIFACTS}
        bindings = {"mixed_completion_sha256": "fictional"}
        snapshot = core.Snapshot()
        receipt = core.seal(
            {
                "status": "corrected_reporting_sidecar_generated",
                "operation": "generate",
                "source_bindings": bindings,
                "artifacts": reporting.artifact_bindings(artifacts),
                "source_binding_sha256": core.canonical(snapshot.portable()),
                "helper_sha256": "helper",
                "scientific_completion_certified": False,
                "test_only": False,
            }
        )
        root = self.root / "synthetic-sidecar"
        reporting.publish(root, artifacts, receipt, [])
        before = {p.name: p.read_bytes() for p in root.iterdir()}
        result = reporting.verify_existing(
            root, artifacts, {"source_bindings": bindings}, "helper", snapshot
        )
        self.assertEqual(result["deterministic_artifacts_compared"], 4)
        self.assertEqual(before, {p.name: p.read_bytes() for p in root.iterdir()})
        self.assertFalse(result["programme_complete"])

    def test_sidecar_mutation_before_return_refused(self):
        artifacts = {name: ("fictional " + name).encode() for name in core.ARTIFACTS}
        snapshot = core.Snapshot()
        receipt = core.seal(
            {
                "status": "corrected_reporting_sidecar_generated",
                "operation": "generate",
                "source_bindings": {},
                "artifacts": reporting.artifact_bindings(artifacts),
                "source_binding_sha256": core.canonical({}),
                "helper_sha256": "helper",
                "scientific_completion_certified": False,
                "test_only": False,
            }
        )
        root = self.root / "synthetic-sidecar"
        reporting.publish(root, artifacts, receipt, [])
        reporting.verify_existing(root, artifacts, {"source_bindings": {}}, "helper", snapshot)
        (root / "report.json").write_text("changed")
        with self.assertRaises(ValueError):
            snapshot.recheck()

    def qa_fixture(self, *, test_only=True):
        """Build invented byte/metadata fixtures without running an image tool."""
        qa = self.root / "qa_fixture"
        qa.mkdir()
        (qa / "page_renders").mkdir()
        (qa / "contact_sheets").mkdir()
        names = ROSTER.expected_names()
        figures, checks = [], []
        for index, name in enumerate(names, 1):
            figure = {
                "name": name,
                "source_files": ["fictional"],
                "pdf_sha256": "fictional",
                "png_sha256": "fictional",
            }
            relative = f"page_renders/{index:02d}_{name}.png"
            (qa / relative).write_bytes(b"fictional page bytes")
            figures.append(figure)
            checks.append(
                {
                    **figure,
                    "page_render": relative,
                    "page_render_sha256": core.sha_bytes(b"fictional page bytes"),
                }
            )
        sheets = []
        for index in range(1, 5):
            relative = f"contact_sheets/sheet_{index:02d}.png"
            (qa / relative).write_bytes(b"fictional contact bytes")
            sheets.append({"file": relative, "sha256": core.sha_bytes(b"fictional contact bytes")})
        tables = [
            {"name": name, "source_files": sources, "csv_sha256": "fictional"}
            for name, sources in ROSTER.TABLE_SOURCES
        ]
        state = {
            "names": names,
            "source_bindings": {"fictional": "fixture"},
            "lineage": {"figures": figures, "tables": tables},
        }
        inventory = core.seal(
            {
                "status": "corrected_automated_checks_passed_visual_review_pending",
                "source_bindings": state["source_bindings"],
                "figure_count": 32,
                "table_count": 6,
                "figures": checks,
                "tables": tables,
                "contact_sheets": sheets,
                "test_only": test_only,
            }
        )
        core.write_new(qa / "qa_inventory.json", inventory)
        core.write_new(qa / "review_template.json", core.seal({"actual_fixture_only": True}))
        review = self.complete_review()
        review["inventory_sha256"] = core.sha_bytes((qa / "qa_inventory.json").read_bytes())
        review_path = self.root / "external_review_fixture.json"
        core.write_new(review_path, core.seal(review))
        request = {
            "roots": {"qa": str(qa)},
            "files": {
                "review": {
                    "path": str(review_path),
                    "sha256": core.sha_bytes(review_path.read_bytes()),
                }
            },
        }
        return qa, state, request

    def test_fixture_receipt_remains_test_only_and_cannot_promote(self):
        qa, state, request = self.qa_fixture()
        with patch.object(visual, "render_state", return_value=state):
            receipt = visual.issue_receipt(request, {}, {}, core.Snapshot())
            self.assertEqual(receipt["visual_qa_status"], "synthetic_test_only_passed")
            self.assertTrue(receipt["test_only"])
            before = {p.name: p.read_bytes() for p in qa.iterdir() if p.is_file()}
            with self.assertRaises(ValueError):
                visual.verify_visual(request, {}, {}, core.Snapshot())
            self.assertEqual(before, {p.name: p.read_bytes() for p in qa.iterdir() if p.is_file()})

    def test_received_named_review_preservation_never_confers_new_approval(self):
        qa, state, request = self.qa_fixture(test_only=False)
        with patch.object(visual, "render_state", return_value=state):
            visual.issue_receipt(request, {}, {}, core.Snapshot())
            before = {p.name: p.read_bytes() for p in qa.iterdir() if p.is_file()}
            result = visual.verify_visual(request, {}, {}, core.Snapshot())
            self.assertTrue(result["actual_visual_review_preserved"])
            self.assertFalse(result["new_visual_approval_conferred"])
            self.assertEqual(result["page_render_count"], 32)
            self.assertEqual(result["contact_sheet_count"], 4)
            self.assertEqual(before, {p.name: p.read_bytes() for p in qa.iterdir() if p.is_file()})

    def test_failed_named_review_cannot_be_preserved_as_passed(self):
        _, state, request = self.qa_fixture(test_only=False)
        path = Path(request["files"]["review"]["path"])
        review = core.strict_json(path.read_bytes())
        review.pop("content_sha256")
        review["figures"][0].update(verdict="fail", issue="Synthetic fixture defect only")
        path.write_bytes(core.json_bytes(core.seal(review)))
        request["files"]["review"]["sha256"] = core.sha_bytes(path.read_bytes())
        with patch.object(visual, "render_state", return_value=state):
            receipt = visual.issue_receipt(request, {}, {}, core.Snapshot())
            self.assertEqual(receipt["visual_qa_status"], "failed")
            with self.assertRaises(ValueError):
                visual.verify_visual(request, {}, {}, core.Snapshot())

    def test_injected_prepare_only_creates_pending_review(self):
        output, source = self.root / "qa", self.root / "rendered"
        source.mkdir()
        names = ROSTER.expected_names()
        figures = []
        for name in names:
            for extension in ("pdf", "png"):
                (source / (name + "." + extension)).write_bytes(b"fictional image fixture")
            figures.append(
                {
                    "name": name,
                    "source_files": ["fictional"],
                    "pdf_sha256": core.sha_bytes(b"fictional image fixture"),
                    "png_sha256": core.sha_bytes(b"fictional image fixture"),
                }
            )

        def invoke(argv, **kwargs):
            Path(argv[-1] + ".png").write_bytes(b"fictional full-page fixture")
            return SimpleNamespace(returncode=0)

        def contacts(root, checks):
            (root / "contact_sheets").mkdir()
            rows = []
            for index in range(1, 5):
                relative = f"contact_sheets/sheet_{index:02d}.png"
                (root / relative).write_bytes(b"fictional contact fixture")
                rows.append(
                    {"file": relative, "sha256": core.sha_bytes(b"fictional contact fixture")}
                )
            return rows

        qa = SimpleNamespace(
            poppler_metadata=lambda p: {"boxes_pt": {"CropBox": [0, 0, 10, 10]}},
            png_metadata=lambda *a: {"width_px": 1000, "height_px": 1000},
            contact_sheets=contacts,
        )
        tables = [
            {"name": name, "source_files": sources, "csv_sha256": "fixture"}
            for name, sources in ROSTER.TABLE_SOURCES
        ]
        state = {
            "root": source,
            "lineage": {"figures": figures, "tables": tables},
            "source_bindings": {"fixture_only": True},
            "names": names,
        }
        request = {"roots": {"qa": str(output), "rendered": str(source)}, "test_only": True}
        with patch.object(visual, "render_state", return_value=state):
            result = visual.prepare(request, output, {}, {"qa": qa}, core.Snapshot(), invoke=invoke)
        self.assertFalse(result["visual_qa_passed"])
        self.assertEqual(len(list((output / "page_renders").iterdir())), 32)
        self.assertEqual(len(list((output / "contact_sheets").iterdir())), 4)
        self.assertFalse((output / "visual_qa_receipt.json").exists())
        inventory = core.strict_json((output / "qa_inventory.json").read_bytes())
        self.assertTrue(inventory["test_only"])
        template = core.strict_json((output / "review_template.json").read_bytes())
        self.assertEqual(template["reviewer_name"], "")
        self.assertTrue(all(row["verdict"] == "pending" for row in template["figures"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
