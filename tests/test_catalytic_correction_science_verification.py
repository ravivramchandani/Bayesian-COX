"""Injected tiny science fixtures; no imports of datasets, traces or scorers."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

VERIFICATION = Path(__file__).resolve().parents[1] / "scripts/catalytic_correction/verification"
sys.path.insert(0, str(VERIFICATION))

from science_verification import (  # noqa: E402 - byte-identical flat CLI imports
    comparison_counts,
    original_comparison,
    verify_attempt_settings,
    verify_science_cell,
)
from verification_io import (  # noqa: E402 - byte-identical flat CLI imports
    Pins,
    VerificationFailure,
    canonical,
    inventory,
    read,
    seal,
    sha,
    write_new,
)


class Backend:
    """Explicit fictional reconstruction/diagnostics/scoring callbacks."""

    def __init__(self) -> None:
        self.scored = 0
        self.diagnosed = []
        self.real = {"events_train": 3, "preprocessing_status": "reconstructed", "p": 2,
                     "preprocessing": {"feature_names": ["a", "b"]},
                     "training_time": [1.0, 2.0, 3.0], "training_event": [1, 1, 1],
                     "observed_time": [1.0, 2.0], "observed_event": [1, 0],
                     "encoded_training": {"shape": [3, 2], "dtype": "<f8", "values_sha256": "a" * 64},
                     "encoded_validation": {"shape": [2, 2], "dtype": "<f8", "values_sha256": "b" * 64}}

    def identity(self, cell, job):
        if cell["cell_id"] != job.cell_id:
            raise VerificationFailure("fake identity mismatch")

    def real_inputs(self, job):
        return self.real

    def assert_equal(self, left, right, label):
        if left != right:
            raise VerificationFailure("fake scientific mismatch at " + label)

    def trace_diagnostics(self, path, label, expected, identity):
        self.diagnosed.append((path.name, label, expected is not None))
        if path.read_bytes() == b"fake unreadable":
            raise ValueError("fake unreadable orphan")
        if expected and not expected.get("matches_fixture", True):
            raise VerificationFailure("fake trace diagnostic mismatch")
        return {"status": "synthetic_callback_recomputed", "observed_diagnostics": {"converged": True}}

    def rescore(self, cell, job, real):
        self.scored += 1
        return {"ibs": 0.125}


def cell(model="ridge", status="complete"):
    value = {"cell_id": "fixture__" + model + "__full", "model_key": model,
             "status": status, "events_train": 3, "p": 2, "events_per_coefficient": 1.5,
             "preprocessing": {"feature_names": ["a", "b"]}, "validation_subject_ids": ["p0", "p1"]}
    if status == "complete":
        value.update(metrics={"ibs": 0.125}, predictions={
            "subject_ids": ["p0", "p1"], "training_time": [1.0, 2.0, 3.0], "training_event": [1, 1, 1],
            "observed_time": [1.0, 2.0], "observed_event": [1, 0]})
    value["cell_content_sha256"] = canonical(value)
    return value


class ScienceTests(unittest.TestCase):
    """Truthful complete/failed/partial trace and rescoring accounting."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="mixed_verification_fixture_")
        self.root = Path(self.temp.name).resolve()
        self.backend, self.pins = Backend(), Pins()
        self.config = {"sampling": {"draws": 2000, "tune": 2000, "chains": 4, "target_accept": 0.999}}

    def tearDown(self):
        self.temp.cleanup()

    def verify(self, value, referenced=None, orphaned=None):
        return verify_science_cell(value, SimpleNamespace(cell_id=value["cell_id"]), trace_root=self.root,
                                   referenced=referenced or {}, orphaned=orphaned or {}, config=self.config,
                                   backend=self.backend, pins=self.pins)

    def trace(self, value, name, data=b"fictional trace bytes"):
        path = self.root / "traces" / value["cell_id"] / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return str(path.relative_to(self.root)), sha(path)

    def test_accepted_forecast_rescored_and_feature_state_checked(self):
        result = self.verify(cell())
        self.assertTrue(result["rescored"])
        self.assertEqual(self.backend.scored, 1)
        self.assertEqual(result["real_input_bindings"]["encoded_training"], self.backend.real["encoded_training"])
        wrong = cell()
        wrong["preprocessing"]["feature_names"] = ["b", "a"]
        with self.assertRaisesRegex(VerificationFailure, "preprocessing"):
            self.verify(wrong)

    def test_failed_terminal_cell_has_no_fake_forecast_or_diagnostics(self):
        value = cell(status="failed")
        result = self.verify(value)
        self.assertFalse(result["rescored"])
        self.assertEqual(result["stored_diagnostic_traces_checked"], 0)
        self.assertEqual(self.backend.scored, 0)
        value["predictions"] = {}
        with self.assertRaisesRegex(VerificationFailure, "fabricated"):
            self.verify(value)

    def test_ordered_outcomes_and_metrics_mismatches(self):
        for field, replacement in (("subject_ids", ["p1", "p0"]), ("observed_time", [2.0, 1.0])):
            value = cell()
            value["predictions"][field] = replacement
            with self.assertRaises(VerificationFailure):
                self.verify(value)
        value = cell()
        value["metrics"]["ibs"] = 0.2
        with self.assertRaisesRegex(VerificationFailure, "metrics"):
            self.verify(value)

    def test_actual_posterior_and_joint_prior_gates(self):
        value = cell("catalytic_fixed")
        posterior_name, posterior_sha = self.trace(value, "attempt_1_posterior.nc")
        prior_name, prior_sha = self.trace(value, "attempt_1_prior.nc")
        value["fit_attempts"] = [{"attempt": 1, "target_accept": 0.999, "tune": 2000,
                                  "noncentered_baseline": False,
                                  "diagnostics": {"method": "nuts", "n_chains": 4, "n_draws": 2000, "converged": True},
                                  "prior_diagnostics": {"converged": True}, "traces": {
                                      "posterior": {"filename": "attempt_1_posterior.nc", "sha256": posterior_sha},
                                      "prior": {"filename": "attempt_1_prior.nc", "sha256": prior_sha}}}]
        traces = {posterior_name: posterior_sha, prior_name: prior_sha}
        result = self.verify(value, traces)
        self.assertEqual(result["stored_diagnostic_traces_checked"], 2)
        value["fit_attempts"][0]["prior_diagnostics"]["converged"] = False
        with self.assertRaisesRegex(VerificationFailure, "joint-prior"):
            self.verify(value, traces)

    def test_diagnostic_failure_requires_existing_remedy_exhaustion(self):
        value = cell("bayesian_normal", "failed_diagnostics")
        value["fit_attempts"] = []
        with self.assertRaisesRegex(VerificationFailure, "exhaust"):
            verify_attempt_settings(value, self.config)
        value["fit_attempts"] = [{"attempt": index + 1, "target_accept": 0.999, "tune": 2000 if index == 0 else 4000,
            "noncentered_baseline": index >= 2, "diagnostics": {"method": "nuts", "n_draws": 2000, "n_chains": 4,
            "converged": False}} for index in range(3)]
        verify_attempt_settings(value, self.config)
        value["fit_attempts"][-1]["diagnostics"]["converged"] = True
        with self.assertRaisesRegex(VerificationFailure, "accepted final"):
            verify_attempt_settings(value, self.config)

    def test_failed_partial_draws_and_unstored_orphan_not_promoted(self):
        value = cell("catalytic_adaptive", "failed")
        name, digest = self.trace(value, "attempt_1_posterior.nc")
        orphan, orphan_sha = self.trace(value, "attempt_1_prior.nc", b"fake unreadable")
        value["fit_attempts"] = [{"attempt": 1, "target_accept": 0.999, "tune": 2000,
                                  "noncentered_baseline": False, "error_type": "RuntimeError",
                                  "diagnostics": {"method": "nuts", "n_chains": 2, "n_draws": 15, "converged": False},
                                  "prior_diagnostics": {}, "traces": {
                                      "posterior": {"filename": "attempt_1_posterior.nc", "sha256": digest}}}]
        result = self.verify(value, {name: digest}, {orphan: orphan_sha})
        self.assertFalse(result["rescored"])
        self.assertEqual(result["orphan_traces_audited"], 1)
        self.assertEqual(result["trace_checks"][orphan]["status"], "orphan_diagnostics_unavailable")
        self.assertFalse(result["trace_checks"][orphan]["stored_diagnostics_present"])

    def test_no_execution_failure_or_accepted_fit_gains_remedy(self):
        value = cell("bayesian_normal", "failed")
        value["fit_attempts"] = [{"attempt": 1, "error_type": "RuntimeError"},
                                  {"attempt": 2, "error_type": "RuntimeError"}]
        with self.assertRaisesRegex(VerificationFailure, "execution failure"):
            self.verify(value)
        value["fit_attempts"] = [{"attempt": 1, "target_accept": 0.999, "tune": 2000,
                                  "noncentered_baseline": False, "diagnostics": {"converged": True}},
                                 {"attempt": 2, "target_accept": 0.999, "tune": 4000,
                                  "noncentered_baseline": False, "diagnostics": {"converged": False}}]
        with self.assertRaisesRegex(VerificationFailure, "accepted previous"):
            self.verify(value)

    def test_changed_trace_bytes_missing_trace_extra_orphan_rejected(self):
        value = cell(status="failed")
        name, digest = self.trace(value, "attempt_1_posterior.nc")
        with self.assertRaisesRegex(VerificationFailure, "inventory differs"):
            self.verify(value)
        with (self.root / name).open("ab") as stream:
            stream.write(b"changed")
        with self.assertRaisesRegex(VerificationFailure, "byte binding"):
            self.verify(value, orphaned={name: digest})

    def test_original_failure_and_reuse_accounting_stays_separate(self):
        old = cell(status="failed")
        new = cell()
        row = original_comparison(old, new, "fit_corrected_inputs", ["outer.synthetic_constructor"])
        summary = comparison_counts([row])
        self.assertEqual(summary["original_status_counts"], {"failed": 1})
        self.assertEqual(summary["corrected_status_counts"], {"complete": 1})
        self.assertFalse(summary["inferential_promotion"])


class IOTests(unittest.TestCase):
    """Write-once checkpoint and residue/source-byte guards."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="verification_io_fixture_")
        self.root = Path(self.temp.name).resolve()

    def tearDown(self):
        self.temp.cleanup()

    def test_atomic_closed_receipt_and_overwrite_refusal(self):
        path = self.root / "receipt.json"
        record = seal({"fictional": True})
        write_new(path, record)
        self.assertEqual(read(path), record)
        with self.assertRaises(VerificationFailure):
            write_new(path, record)
        before = path.read_bytes()
        path.write_bytes(before + b"changed")
        with self.assertRaises(VerificationFailure):
            read(path)

    def test_publish_link_failure_retains_partial_attempt(self):
        path = self.root / "receipt.json"
        with patch("verification_io.os.link", side_effect=OSError("fake link failure")):
            with self.assertRaises(OSError):
                write_new(path, seal({"fake": True}))
        self.assertFalse(path.exists())
        self.assertTrue(list(self.root.glob(".verification-pending-*")))

    def test_exact_inventory_unknown_directory_link_and_temp(self):
        folder = self.root / "facts"
        folder.mkdir()
        write_new(folder / "row.json", seal({"fake": True}))
        inventory(folder, {"row.json"}, set())
        (folder / "unknown").mkdir()
        with self.assertRaises(VerificationFailure):
            inventory(folder, {"row.json"}, set())
        (folder / "unknown").rmdir()
        (folder / "linked").symlink_to(self.root / "missing")
        with self.assertRaises(VerificationFailure):
            inventory(folder, {"row.json"}, set())


if __name__ == "__main__":
    unittest.main()
