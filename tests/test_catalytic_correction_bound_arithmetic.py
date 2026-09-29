"""Synthetic checkpoint/output guards; never invoke a generator or optimizer."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from scripts.catalytic_correction import bound_arithmetic as bound
from scripts.catalytic_correction.independent_arithmetic import (
    ArithmeticFailure,
    load_original_functions,
)
from tests.test_catalytic_correction_arithmetic import balanced, original_source_fixture


def write(path: Path, value: dict) -> str:
    """Only the synthetic fixture writer replaces its own fixture records."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bound.sealed(value), sort_keys=True, indent=2) + "\n")
    return bound.file_hash(path)


def artifact(path: Path) -> dict:
    return {"sha256": bound.file_hash(path), "bytes": path.stat().st_size}


def create_fixture(root: Path, *, adaptive: bool = False, bad_witness: bool = False,
                   fixed: bool = False, bad_seed: bool = False, bad_ids: bool = False,
                   nonfinite: bool = False, scalar_vector: bool = False) -> tuple[Path, str, str]:
    """Create two tiny fictional complete contexts; no cohort/guard/generator."""
    root.mkdir()
    data = balanced()
    if nonfinite:
        data.synthetic_design[0, 0] = np.nan
    identities = ["metabric__clinical__full__catalytic_adaptive__r01f01::outer" if adaptive else
                  "metabric__clinical__full__catalytic_fixed__r01f01::outer" if fixed else
                  "metabric__clinical__full__catalytic_wme__r01f01::outer",
                  "metabric__clinical__full__catalytic_wme__r01f01::inner_01"]
    outcomes, selected = [], []
    for ordinal, identity in enumerate(identities):
        cell, role = bound.context_parts(identity)
        folder = root / "contexts" / cell / role
        folder.mkdir(parents=True)
        input_witness = {
            "feature_names": ["x"], "ordered_training_subject_ids": ["p0"] if bad_ids else ["p0", "p1"],
            "n_train": 2, "processor_metadata": {"fixture": True},
            "processor_metadata_sha256": bound.canonical_hash({"fixture": True}),
            "real_design": bound.witness(data.real_design), "training_time": bound.witness(data.real_time),
            "training_event": bound.witness(data.real_event),
        }
        input_witness["training_membership_sha256"] = bound.canonical_hash(input_witness["ordered_training_subject_ids"])
        if bad_witness:
            input_witness["real_design"]["values_sha256"] = "0" * 64
        request = {"context_id": identity, "run_binding_sha256": "a" * 64, "candidate_cap": 256,
                   "original_generation_seed": 42, "input_witness_sha256": bound.canonical_hash(input_witness)}
        write(folder / "input.json", {"request": request, "input_witness": input_witness})
        np.savez_compressed(folder / "inputs.npz", real_design=data.real_design,
                            real_time=data.real_time, real_event=data.real_event)
        artifacts = {name: artifact(folder / name) for name in ("input.json", "inputs.npz")}
        attempts = []
        for index in range(ordinal + 1):
            attempt_dir = folder / f"attempt_{index:03d}"
            attempt_dir.mkdir()
            arrays = {"synthetic_design": data.synthetic_design if index == ordinal else np.zeros((2, 1)),
                      "synthetic_time": data.synthetic_time,
                      "hazard": np.asarray([data.hazard]) if scalar_vector else np.asarray(data.hazard),
                      "time_scale": np.asarray(data.time_scale)}
            np.savez_compressed(attempt_dir / "proposal.npz", **arrays)
            attempt = bound.sealed({"request": request, "attempt_index": index,
                                    "seed": bound.retry_seed(42, index) + int(bad_seed),
                                    "status": "accepted_original_constructor" if index == ordinal else "frozen_rank_rejected",
                                    "array_witnesses": {name: bound.witness(array) for name, array in arrays.items()},
                                    "artifacts": {"proposal.npz": artifact(attempt_dir / "proposal.npz")}})
            (attempt_dir / "receipt.json").write_text(json.dumps(attempt, sort_keys=True, indent=2) + "\n")
            attempts.append(attempt)
            for name in ("receipt.json", "proposal.npz"):
                artifacts[f"attempt_{index:03d}/{name}"] = artifact(attempt_dir / name)
        status = "accepted_original_first_draw" if ordinal == 0 else "accepted_rank_conditioned_redraw"
        content = {"schema_version": 1, "request": request, "attempts": attempts,
                   "accepted_attempt_index": ordinal, "status": status, "artifacts": artifacts}
        receipt_sha = write(folder / "receipt.json", content)
        outcomes.append({"context_id": identity, "status": status,
                         "receipt_path": str((folder / "receipt.json").relative_to(root)),
                         "receipt_sha256": receipt_sha,
                         "receipt_content_sha256": bound.read_sealed(folder / "receipt.json")["content_sha256"]})
        selected.append({"context_id": identity, "context_receipt_sha256": receipt_sha,
                         "adaptive_required": adaptive and ordinal == 0,
                         "kappa_required": (adaptive or fixed) and ordinal == 0})
    completion = {"schema_version": 1, "run_binding_sha256": "a" * 64,
                  "status": "all_scheduled_contexts_accounted", "scheduled_contexts": 2, "accounted_contexts": 2,
                  "outcomes": outcomes, "outcome_counts": dict(Counter(row["status"] for row in outcomes)),
                  "fit_reuse_certified": False, "model_fit_evaluation_identity_certified": False,
                  "scientific_method_approved": False, "new_freeze_created": False}
    completion_sha = write(root / "completion.json", completion)
    selection = root.parent / (root.name + "_selection.json")
    selection_sha = write(selection, {"schema_version": 1, "kind": "root_requested_arithmetic_contexts",
                                      "preflight_completion_sha256": completion_sha,
                                      "run_binding_sha256": "a" * 64, "contexts": selected})
    return selection, completion_sha, selection_sha


class BindingTests(unittest.TestCase):
    """Byte pins, accounting and atomic output semantics on tiny fake archives."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.source_temporary = tempfile.TemporaryDirectory(prefix="original_arithmetic_blobs_")
        cls.original = original_source_fixture(Path(cls.source_temporary.name).resolve())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.source_temporary.cleanup()

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="synthetic_arithmetic_")
        self.base = Path(self.temporary.name).resolve()
        self.root = self.base / "preflight"
        self.selection, self.completion_sha, self.selection_sha = create_fixture(self.root)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def snapshot(self) -> bound.Snapshot:
        return bound.Snapshot(self.root, self.completion_sha, self.selection, self.selection_sha,
                              expected_contexts=2)

    def args(self, command: str = "validate") -> argparse.Namespace:
        return argparse.Namespace(command=command, preflight_root=self.root, completion_sha256=self.completion_sha,
                                  selection=self.selection, selection_sha256=self.selection_sha,
                                  source_checkout=self.original, destination=self.base / "output", kappa_root=None,
                                  kappa_receipt_sha256=None)

    def small_snapshot(self):
        original = bound.Snapshot

        def fixture_snapshot(*args, **kwargs):
            return original(*args, **kwargs, expected_contexts=2)

        return patch.object(bound, "Snapshot", side_effect=fixture_snapshot)

    def test_bound_inputs_and_portable_lineage(self) -> None:
        snapshot = self.snapshot()
        inputs, lineage = snapshot.load(snapshot.selected[1])
        self.assertEqual(lineage["accepted_attempt_index"], 1)
        self.assertEqual(inputs.p, 1)
        relocated = self.base / "relocated"
        shutil.copytree(self.root, relocated)
        replay = bound.Snapshot(relocated, self.completion_sha, self.selection, self.selection_sha, expected_contexts=2)
        _, replay_lineage = replay.load(replay.selected[1])
        self.assertEqual(lineage, replay_lineage)
        snapshot.recheck()

    def test_production_cli_refuses_partial_before_output(self) -> None:
        with self.assertRaisesRegex(ArithmeticFailure, "full scheduled"):
            bound.run(self.args())
        self.assertFalse(self.args().destination.exists())

    def test_changed_bytes_and_recheck(self) -> None:
        snapshot = self.snapshot()
        snapshot.load(snapshot.selected[0])
        path = snapshot.selected[0][2] / "inputs.npz"
        with path.open("ab") as stream:
            stream.write(b"changed")
        with self.assertRaisesRegex(ArithmeticFailure, "changed during"):
            snapshot.recheck()
        with self.assertRaisesRegex(ArithmeticFailure, "artifact bytes"):
            snapshot.load(snapshot.selected[0])

    def test_missing_and_symlink_artifacts(self) -> None:
        snapshot = self.snapshot()
        path = snapshot.selected[0][2] / "inputs.npz"
        saved = self.base / "saved.npz"
        path.rename(saved)
        with self.assertRaises(ArithmeticFailure):
            snapshot.load(snapshot.selected[0])
        path.symlink_to(saved)
        with self.assertRaisesRegex(ArithmeticFailure, "linked"):
            snapshot.load(snapshot.selected[0])

    def test_resealed_bad_witness_seed_and_ids(self) -> None:
        for key in ("bad_witness", "bad_seed", "bad_ids", "nonfinite", "scalar_vector"):
            root = self.base / key
            selection, completion_sha, selection_sha = create_fixture(root, **{key: True})
            snapshot = bound.Snapshot(root, completion_sha, selection, selection_sha, expected_contexts=2)
            with self.assertRaises(ArithmeticFailure):
                snapshot.load(snapshot.selected[0])

    def test_duplicate_selection_and_adaptive_omission(self) -> None:
        value = bound.read_sealed(self.selection)
        value.pop("content_sha256")
        value["contexts"].append(value["contexts"][0])
        self.selection_sha = write(self.selection, value)
        with self.assertRaisesRegex(ArithmeticFailure, "duplicate"):
            self.snapshot()
        root = self.base / "adaptive"
        selection, completion_sha, selection_sha = create_fixture(root, adaptive=True)
        value = bound.read_sealed(selection)
        value.pop("content_sha256")
        value["contexts"][0]["adaptive_required"] = False
        selection_sha = write(selection, value)
        with self.assertRaisesRegex(ArithmeticFailure, "cannot omit"):
            bound.Snapshot(root, completion_sha, selection, selection_sha, expected_contexts=2)

    def test_validate_success_no_optimizer_and_overwrite_refusal(self) -> None:
        with self.small_snapshot(), patch.object(np.linalg, "matrix_rank", side_effect=AssertionError("no SVD")):
            receipt = bound.run(self.args())
        self.assertEqual(receipt["status"], "requested_context_arithmetic_passed")
        self.assertEqual(receipt["reported_context_count"], 2)
        self.assertFalse(receipt["optimizer_invoked"])
        files = list(self.args().destination.rglob("*.json"))
        self.assertEqual(len(files), 4)
        before = bound.file_hash(self.args().destination / "receipt.json")
        with self.small_snapshot(), self.assertRaises(FileExistsError):
            bound.run(self.args())
        self.assertEqual(before, bound.file_hash(self.args().destination / "receipt.json"))

    def test_bad_arithmetic_retained_without_success_receipt(self) -> None:
        original = load_original_functions(self.original)
        fake = SimpleNamespace(**vars(original))

        def wrong(beta, data):
            value, gradient = original.catalytic_kernel(beta, data)
            return value, gradient + 0.01

        fake.catalytic_kernel = wrong
        with self.small_snapshot(), patch.object(bound, "load_original_functions", return_value=fake):
            with self.assertRaisesRegex(ArithmeticFailure, "comparison failed"):
                bound.run(self.args())
        output = self.args().destination
        self.assertFalse((output / "receipt.json").exists())
        self.assertTrue((output / "failure.json").exists())
        row = bound.read_sealed(next((output / "contexts").iterdir()))
        self.assertEqual(row["result"]["status"], "arithmetic_failed")

    def test_adaptive_missing_kappa_before_destination(self) -> None:
        root = self.base / "adaptive"
        self.selection, self.completion_sha, self.selection_sha = create_fixture(root, adaptive=True)
        self.root = root
        with self.small_snapshot(), self.assertRaisesRegex(ArithmeticFailure, "kappa witnesses"):
            bound.run(self.args())
        self.assertFalse(self.args().destination.exists())

    def test_fixed_also_requires_kappa_initialization_witness(self) -> None:
        root = self.base / "fixed"
        self.selection, self.completion_sha, self.selection_sha = create_fixture(root, fixed=True)
        self.root = root
        with self.small_snapshot(), self.assertRaisesRegex(ArithmeticFailure, "kappa witnesses"):
            bound.run(self.args())
        self.assertFalse(self.args().destination.exists())
        value = bound.read_sealed(self.selection)
        value.pop("content_sha256")
        value["contexts"][0]["kappa_required"] = False
        self.selection_sha = write(self.selection, value)
        with self.assertRaisesRegex(ArithmeticFailure, "both Bayesian"):
            self.snapshot()

    def test_mocked_explicit_kappa_stage_and_validate_bindings(self) -> None:
        root = self.base / "adaptive"
        self.selection, self.completion_sha, self.selection_sha = create_fixture(root, adaptive=True)
        self.root = root
        original = load_original_functions(self.original)
        fake = SimpleNamespace(**vars(original))
        fake.optimizer_enabled = True
        fake.catalytic_kappa = lambda data: (-1.0, np.zeros(data.design.shape[1]))
        with self.small_snapshot(), patch.object(bound, "load_original_functions", return_value=fake):
            receipt = bound.run(self.args("compute-kappa"))
        self.assertTrue(receipt["optimizer_invoked"])
        self.assertEqual(receipt["reported_context_count"], 1)
        args = self.args()
        args.kappa_root = args.destination
        args.kappa_receipt_sha256 = bound.file_hash(args.kappa_root / "receipt.json")
        args.destination = self.base / "validated"
        with self.small_snapshot():
            validated = bound.run(args)
        self.assertEqual(validated["reported_context_count"], 2)
        self.assertFalse(validated["optimizer_invoked"])
        item = bound.read_sealed(next((args.kappa_root / "contexts").iterdir()))
        item.pop("content_sha256")
        item["lineage"]["accepted_proposal_sha256"] = "f" * 64
        path = next((args.kappa_root / "contexts").iterdir())
        write(path, item)
        args.destination = self.base / "changed_kappa"
        with self.small_snapshot(), self.assertRaisesRegex(ArithmeticFailure, "artifact bytes"):
            bound.run(args)

    def test_atomic_link_failure_and_existing_receipt_untouched(self) -> None:
        path = self.base / "receipt.json"
        with patch.object(bound.os, "link", side_effect=OSError("synthetic link error")):
            with self.assertRaisesRegex(OSError, "link error"):
                bound.publish_new(path, {"fake": True})
        self.assertFalse(path.exists())
        self.assertTrue(list(self.base.glob(".arithmetic-*")))
        bound.publish_new(path, {"fake": True})
        before = path.read_bytes()
        with self.assertRaisesRegex(ArithmeticFailure, "overwrite"):
            bound.publish_new(path, {"fake": False})
        self.assertEqual(before, path.read_bytes())

    def test_kappa_invocation_missing_changed_and_residual_refused(self) -> None:
        root = self.base / "fixed"
        self.selection, self.completion_sha, self.selection_sha = create_fixture(root, fixed=True)
        self.root = root
        original = load_original_functions(self.original)
        fake = SimpleNamespace(**vars(original))
        fake.optimizer_enabled = True
        fake.catalytic_kappa = lambda data: (-1.0, np.zeros(data.design.shape[1]))
        args = self.args("compute-kappa")
        with self.small_snapshot(), patch.object(bound, "load_original_functions", return_value=fake):
            bound.run(args)
        receipt_sha = bound.file_hash(args.destination / "receipt.json")
        invocation = args.destination / "invocation.json"
        before = invocation.read_bytes()
        invocation.write_bytes(before + b"changed")
        with self.assertRaisesRegex(ArithmeticFailure, "byte binding"):
            bound.read_kappa(args.destination, receipt_sha, self.snapshot())
        invocation.unlink()
        with self.assertRaisesRegex(ArithmeticFailure, "missing"):
            bound.read_kappa(args.destination, receipt_sha, self.snapshot())
        invocation.write_bytes(before)
        residual = args.destination / ".arithmetic-residual"
        residual.write_text("retained partial")
        with self.assertRaisesRegex(ArithmeticFailure, "residual"):
            bound.read_kappa(args.destination, receipt_sha, self.snapshot())
        residual.unlink()
        witness = bound.read_kappa(args.destination, receipt_sha, self.snapshot())
        self.assertEqual(len(witness), 1)
        invocation_record = bound.read_sealed(invocation)
        invocation_record.pop("content_sha256")
        next(iter(invocation_record["optimizer_context_stages"].values()))["status"] = "started"
        invocation_sha = write(invocation, invocation_record)
        receipt_record = bound.read_sealed(args.destination / "receipt.json")
        receipt_record.pop("content_sha256")
        receipt_record["invocation_sha256"] = invocation_sha
        receipt_sha = write(args.destination / "receipt.json", receipt_record)
        with self.assertRaisesRegex(ArithmeticFailure, "invocation/stage/source"):
            bound.read_kappa(args.destination, receipt_sha, self.snapshot())

    def test_mocked_optimizer_failure_terminal_no_retry(self) -> None:
        root = self.base / "adaptive"
        self.selection, self.completion_sha, self.selection_sha = create_fixture(root, adaptive=True)
        self.root = root
        original = load_original_functions(self.original)
        fake = SimpleNamespace(**vars(original))
        fake.optimizer_enabled = True
        calls = []

        def failed(data):
            calls.append(data)
            raise RuntimeError("synthetic optimizer failure")

        fake.catalytic_kappa = failed
        args = self.args("compute-kappa")
        with self.small_snapshot(), patch.object(bound, "load_original_functions", return_value=fake):
            with self.assertRaisesRegex(RuntimeError, "optimizer failure"):
                bound.run(args)
        self.assertEqual(len(calls), 1)
        self.assertFalse((args.destination / "receipt.json").exists())
        failure = bound.read_sealed(args.destination / "failure.json")
        self.assertEqual(failure["status"], "failed_arithmetic_attempt")
        self.assertFalse(failure["retry_or_replacement_proposal_generated"])
        stage = next(iter(failure["optimizer_context_stages"].values()))
        self.assertEqual(stage["status"], "failed_no_retry")
        self.assertIn("finished_at_utc", stage)

    def test_atomic_cleanup_failure_propagates_after_link(self) -> None:
        path = self.base / "receipt.json"
        original = Path.unlink

        def fail_cleanup(item, *args, **kwargs):
            if item.name.startswith(".arithmetic-"):
                raise OSError("synthetic cleanup error")
            return original(item, *args, **kwargs)

        with patch.object(Path, "unlink", fail_cleanup):
            with self.assertRaisesRegex(OSError, "cleanup error"):
                bound.publish_new(path, {"fake": True})
        self.assertTrue(path.exists())
        self.assertTrue(list(self.base.glob(".arithmetic-*")))

    def test_exact_inventory_rejects_residuals_and_links(self) -> None:
        output = self.base / "inventory"
        output.mkdir()
        (output / "contexts").mkdir()
        path = output / "row.json"
        path.write_text("{}")
        bound.verify_output_inventory(output, {"row.json"})
        residual = output / ".arithmetic-residual"
        residual.write_text("partial")
        with self.assertRaisesRegex(ArithmeticFailure, "residual"):
            bound.verify_output_inventory(output, {"row.json"})
        residual.unlink()
        (output / "unknown_empty_directory").mkdir()
        with self.assertRaisesRegex(ArithmeticFailure, "residual"):
            bound.verify_output_inventory(output, {"row.json"})
        (output / "unknown_empty_directory").rmdir()
        (output / "broken_link").symlink_to(self.base / "absent")
        with self.assertRaisesRegex(ArithmeticFailure, "linked"):
            bound.verify_output_inventory(output, {"row.json"})


if __name__ == "__main__":
    unittest.main()
