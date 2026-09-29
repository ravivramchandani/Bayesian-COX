"""Constrained source-capture guards with fictional bytes/injected child only."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import capture_corrected_source as source
import release_core as c
from test_release_adapters import binding, raw, save


class SourceCaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="fictional-correction-source-capture-")
        self.base = Path(self.temp.name).resolve(strict=True)
        self.evidence, self.helpers, self.captures = (self.base / name for name in ("evidence", "helpers", "captures"))
        for path in (self.evidence, self.helpers, self.captures):
            path.mkdir()
        raw(self.evidence / "fictional_failed_trace.bytes", b"ordinary bytes; no trace parser")
        for name, _, _ in source.MODES.values():
            raw(self.helpers / name, b"# fictional read-only helper; never executed\n")
        names = [value[0] for value in source.MODES.values()]
        self.preparation = self.helpers / "preparation_receipt.json"
        prep_sha = save(self.preparation, {"status": "corrected_reproduction_receiving_adapter_prepared",
            "no_fit_or_generator_dispatch": True, "artifacts": {name: binding(self.helpers / name) for name in names},
            "implementation_source_sha256": {name: c.sha(self.helpers / name) for name in names}})
        self.pins = {"receiving_reproduction_preparation_sha256": prep_sha, "reporting_qa_preparation_sha256": prep_sha}
        self.python = Path("/fictional/locked_python")

    def tearDown(self):
        self.temp.cleanup()

    def fixture(self, mode):
        input_path = self.base / (mode + "_bindings.json")
        bindings = {name: "a" * 64 for name in c.REPORT_BINDINGS}
        value = {"immutable_roots": [{"root": str(self.evidence)}], "immutable_files": [],
            "roots": {"fictional": str(self.evidence)}, "files": {}, "selection_sha256": "a" * 64,
            "completed_pass": {"sha256": "b" * 64}, "sidecar_receipt_sha256": "c" * 64, **bindings}
        save(input_path, value)
        output = self.base / (mode + "_proof")
        request = {"schema_version": 1, "status": "corrected_read_only_source_capture_request", "mode": mode, "test_only": False,
            "helper_preparation": {"path": str(self.preparation), "sha256": c.sha(self.preparation)},
            "input_request": {"path": str(input_path), "sha256": c.sha(input_path)},
            "immutable_roots": [str(self.evidence)], "immutable_files": [],
            "capture_prefix": str(self.captures / mode), "evidence_output": None if mode == "claims" else str(output)}
        calls = []
        def invoke(argv, **kwargs):
            calls.append(argv)
            self.assertEqual(kwargs["env"]["PYTHONDONTWRITEBYTECODE"], "1")
            self.assertTrue(all(kwargs["env"][name] == "1" for name in c.NUMERIC))
            summary = {"status": source.MODES[mode][2]}
            if mode == "reproduction":
                summary.update(selection_sha256="a" * 64, selected_pass_sha256="b" * 64, scheduled_selected_cells=3,
                    accounted_selected_cells=3, no_new_numerical_fit=True, no_new_generator_recipe=True)
            elif mode == "reporting":
                summary.update(source_bindings=bindings, sidecar_receipt_sha256="c" * 64,
                    deterministic_bytes_reproduced_exactly=True, no_new_fit_generator_optimizer_or_inference=True)
            else:
                summary.update(original_primary_negative_findings_preserved=True, new_inferential_promotion=False)
            if mode != "claims":
                output.mkdir()
                name = "receipt.json" if mode == "reproduction" else "reporting_replay_receipt.json"
                path = output / name
                save(path, {**summary, "test_only": False, "test_only_dependency_injection": False, "artifacts": {},
                            "fictional_injected_no_actual_helper_invoked": True})
                summary.update(receipt_path=str(path), receipt_sha256=c.sha(path))
            return SimpleNamespace(returncode=0, stdout=(json.dumps(summary) + "\n").encode(), stderr=b"fictional injected process\n")
        return request, {"invoke": invoke}, calls

    def test_all_three_fixed_read_only_entrypoints(self):
        for mode in source.MODES:
            with self.subTest(mode=mode):
                request, deps, calls = self.fixture(mode)
                result = source.capture_source(request, self.python, c.Pins(), self.pins, dependencies=deps, test_only=True)
                self.assertTrue(result["test_only"])
                self.assertEqual(len(calls), 1)
                self.assertEqual(Path(calls[0][3]).name, source.MODES[mode][0])
                receipt = c.document(Path(result["receipt_path"]), c.Pins())
                self.assertTrue(receipt["test_only_dependency_injection"])
                self.assertFalse(receipt["programme_complete"])

    def test_nonzero_retains_logs_without_success_receipt(self):
        request, _deps, _calls = self.fixture("claims")
        def failed(*_args, **_kwargs):
            return SimpleNamespace(returncode=31, stdout=b"fictional failed stdout\n", stderr=b"retained stderr")
        with self.assertRaisesRegex(ValueError, "child failed"):
            source.capture_source(request, self.python, c.Pins(), self.pins, dependencies={"invoke": failed}, test_only=True)
        self.assertEqual(c.document(self.captures / "claims.attempt.json", c.Pins())["exit_code"], 31)
        self.assertFalse((self.captures / "claims.receipt.json").exists())

    def test_production_api_rejects_injection(self):
        request, deps, calls = self.fixture("claims")
        with self.assertRaisesRegex(ValueError, "fictional tests"):
            source.capture_source(request, self.python, c.Pins(), self.pins, dependencies=deps)
        self.assertFalse(calls)

    def test_arbitrary_execution_mode_refused(self):
        request, deps, calls = self.fixture("claims")
        request["mode"] = "run_reproduction"
        with self.assertRaisesRegex(ValueError, "read-only"):
            source.capture_source(request, self.python, c.Pins(), self.pins, dependencies=deps, test_only=True)
        self.assertFalse(calls)

    def test_unreviewed_helper_receipt_refused_before_invocation(self):
        request, deps, calls = self.fixture("claims")
        self.pins["reporting_qa_preparation_sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "reviewed helper"):
            source.capture_source(request, self.python, c.Pins(), self.pins, dependencies=deps, test_only=True)
        self.assertFalse(calls)

    def test_output_overlap_missing_roles_and_overwrite(self):
        request, deps, calls = self.fixture("reproduction")
        request["evidence_output"] = str(self.evidence / "forbidden")
        with self.assertRaises(ValueError):
            source.capture_source(request, self.python, c.Pins(), self.pins, dependencies=deps, test_only=True)
        self.assertFalse(calls)
        request["evidence_output"] = str(self.base / "existing")
        (self.base / "existing").mkdir()
        with self.assertRaises(ValueError):
            source.capture_source(request, self.python, c.Pins(), self.pins, dependencies=deps, test_only=True)
        request["immutable_roots"] = [str(self.helpers)]
        with self.assertRaisesRegex(ValueError, "roles omitted"):
            source.capture_source(request, self.python, c.Pins(), self.pins, dependencies=deps, test_only=True)

    def test_claim_changed_primary_findings_refused(self):
        request, _deps, _calls = self.fixture("claims")
        def fabricated(*_args, **_kwargs):
            return SimpleNamespace(returncode=0, stdout=(json.dumps({"status": source.MODES["claims"][2],
                "original_primary_negative_findings_preserved": False, "new_inferential_promotion": True}) + "\n").encode(), stderr=b"")
        with self.assertRaisesRegex(ValueError, "frozen findings"):
            source.capture_source(request, self.python, c.Pins(), self.pins, dependencies={"invoke": fabricated}, test_only=True)
        self.assertFalse((self.captures / "claims.receipt.json").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
