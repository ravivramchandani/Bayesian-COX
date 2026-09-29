"""Mocked invocation and source-only AST boundary checks; no science launched."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

VERIFICATION = Path(__file__).resolve().parents[1] / "scripts/catalytic_correction/verification"
sys.path.insert(0, str(VERIFICATION))

from bound_lineage import BoundLineage  # noqa: E402
from capture_verification import capture  # noqa: E402
from frozen_backend import load_verification_definitions  # noqa: E402
from mixed_analysis import verify_runtime_metadata  # noqa: E402
from verification_gates import (  # noqa: E402 - byte-identical flat CLI imports
    CONTRACTS,
    PREFLIGHT_CORE,
    REUSE_CORE,
    complete_output_inventory,
    load_fit_gate_definitions,
    validate_source_surface,
)
from verification_io import (  # noqa: E402 - byte-identical flat CLI imports
    Pins,
    VerificationFailure,
    canonical,
    read,
    seal,
    sha,
    write_new,
)
from verify_mixed_extensions import actual_environment, prepare_output  # noqa: E402


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="fictional_verification_capture_")
        self.root = Path(self.temp.name).resolve()
        self.output, self.prefix = self.root / "verified", self.root / "capture"
        self.output.mkdir()
        self.status = "mixed_original_corrected_grid_deep_verified_and_frozen_analysis_recomputed"
        self.completion = {"status": self.status, "verified_logical_cells": 1625}
        write_new(self.output / "completion.json", seal(self.completion))
        self.stdout = (json.dumps({"status": self.status, "verified_logical_cells": 1625, "programme_complete": False}) + "\n").encode()

    def tearDown(self):
        self.temp.cleanup()

    def invocation(self, returncode=0, stdout=None):
        return lambda *args, **kwargs: SimpleNamespace(returncode=returncode, stdout=self.stdout if stdout is None else stdout, stderr=b"fictional diagnostic")

    def test_genuine_mock_rc0_capture_and_relocated_artifacts(self):
        receipt = capture(["fictional_verifier"], self.prefix, self.output, Pins(), self.invocation())
        self.assertEqual(receipt["status"], "mixed_verification_actual_rc0_captured")
        self.assertEqual(receipt["completion_sha256"], sha(self.output / "completion.json"))
        restored = self.root / "restored_capture"
        restored.mkdir()
        for name in receipt["artifacts"]:
            (restored / name).write_bytes((self.root / name).read_bytes())
        Pins().artifacts(restored, receipt["artifacts"])
        with self.assertRaisesRegex(VerificationFailure, "colliding"):
            capture(["fictional_verifier"], self.prefix, self.output, Pins(), self.invocation())

    def test_nonzero_real_rc_retained_even_with_leftover_positive_completion(self):
        with self.assertRaisesRegex(VerificationFailure, "failed"):
            capture(["fictional_verifier"], self.prefix, self.output, Pins(), self.invocation(7))
        attempt = read(self.root / "capture.attempt.json")
        self.assertEqual(attempt["exit_code"], 7)
        self.assertFalse((self.root / "capture.receipt.json").exists())
        self.assertEqual((self.root / "capture.stderr.log").read_bytes(), b"fictional diagnostic")

    def test_rc0_mismatched_stdout_refused(self):
        with self.assertRaisesRegex(VerificationFailure, "differs"):
            capture(["fictional_verifier"], self.prefix, self.output, Pins(), self.invocation(stdout=b'{"status":"wrong","verified_logical_cells":1625}\n'))
        self.assertFalse((self.root / "capture.receipt.json").exists())

    def test_launch_error_and_publication_error_never_become_success(self):
        def error(*args, **kwargs):
            raise OSError("fictional launch failure")
        with self.assertRaises(VerificationFailure):
            capture(["fictional_verifier"], self.prefix, self.output, Pins(), error)
        self.assertIsNone(read(self.root / "capture.attempt.json")["exit_code"])
        new_prefix = self.root / "other_capture"
        with patch("verification_io.os.link", side_effect=OSError("fictional exclusive-link failure")):
            with self.assertRaises(OSError):
                capture(["fictional_verifier"], new_prefix, self.output, Pins(), self.invocation())
        self.assertFalse((self.root / "other_capture.receipt.json").exists())
        self.assertTrue(list(self.root.glob(".verification-pending-*")))

    def test_committed_receipt_cleanup_failure_is_not_cli_success(self):
        original_unlink = Path.unlink
        def fail_receipt_cleanup(path, *args, **kwargs):
            if path.name.startswith(".verification-pending-capture.receipt.json-"):
                raise OSError("fictional cleanup failure")
            return original_unlink(path, *args, **kwargs)
        with patch.object(Path, "unlink", fail_receipt_cleanup):
            with self.assertRaisesRegex(OSError, "cleanup"):
                capture(["fictional_verifier"], self.prefix, self.output, Pins(), self.invocation())
        self.assertTrue((self.root / "capture.receipt.json").is_file())
        self.assertTrue(list(self.root.glob(".verification-pending-capture.*")))


class BoundaryTests(unittest.TestCase):
    def test_exact_source_surface_cannot_omit_ast_loaded_guard_source(self):
        freeze = {"dependency_source_sha256": {"contracts": CONTRACTS, "preflight_core": PREFLIGHT_CORE, "reuse_core": REUSE_CORE},
                  "implementation_source_sha256": {name: "x" * 64 for name in ("fit_common.py", "fit_child.py", "fit_controller.py")}}
        definition = {"contracts_sha256": CONTRACTS, "preflight_sources": {"preflight_core.py": PREFLIGHT_CORE, "run_preflight.py": "x" * 64},
                      "reuse_sources": {"reuse_core.py": REUSE_CORE, "run_reuse.py": "x" * 64, "normal_first_draw_child.py": "x" * 64}}
        validate_source_surface(freeze, definition)
        freeze["implementation_source_sha256"].pop("fit_common.py")
        with self.assertRaisesRegex(VerificationFailure, "source names"):
            validate_source_surface(freeze, definition)

    def test_historical_child_runtime_binds_paths_versions_and_numeric_environment(self):
        numeric = {name: "1" for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS")}
        original = {"python": "fictional version", "dependencies": {"fictional_dependency": "1"},
                    "dependency_set_sha256": canonical({"fictional_dependency": "1"})}
        runtime = {"locked_interpreter_samefile": True, "requested_locked_python": "/historic_mac/python",
                   "observed_executable": "/historic_mac/python", "numeric_thread_environment": numeric}
        interpreter = {"locked_interpreter_samefile": True, "observed_executable": "/historic_mac/python",
            "status": "exact_lock_versions_match", "observed_python": original["python"], "observed_dependencies": original["dependencies"],
            "observed_dependency_set_sha256": original["dependency_set_sha256"], "frozen_environment_sha256": canonical(original)}
        request, argv = {"locked_python": "/historic_mac/python"}, ["/historic_mac/python"]
        verify_runtime_metadata(runtime, interpreter, request, argv, original, numeric)
        runtime["locked_interpreter_samefile"] = False
        with self.assertRaisesRegex(VerificationFailure, "runtime"):
            verify_runtime_metadata(runtime, interpreter, request, argv, original, numeric)
        runtime["locked_interpreter_samefile"] = True
        numeric["OMP_NUM_THREADS"] = "2"
        with self.assertRaisesRegex(VerificationFailure, "runtime"):
            verify_runtime_metadata(runtime, interpreter, request, argv, original, numeric)

    def test_input_failure_replay_request_binds_all_actual_fields(self):
        with tempfile.TemporaryDirectory(prefix="fictional_replay_request_") as temporary:
            root = Path(temporary).resolve()
            preflight, witnesses = root / "preflight", root / "witnesses"
            preflight.mkdir()
            witnesses.mkdir()
            row = {"context_id": "toy::outer", "generation_seed": 47}
            source = seal({"status": "input_failure", "input_error": {"type": "builtins.ValueError", "message": "few events",
                "traceback": "original capture traceback retained"}, "artifacts": {}})
            write_new(preflight / "receipt.json", source)
            request = {"definition_content_sha256": "d" * 64, "context_id": row["context_id"],
                "context_row_sha256": canonical(row), "original_generation_seed": 47,
                "preflight_receipt_sha256": sha(preflight / "receipt.json"), "input_witness_sha256": None}
            def build_context(*args):
                raise ValueError("few events")
            bound = object.__new__(BoundLineage)
            bound.gates = SimpleNamespace(roots={"witness_root": witnesses, "preflight": preflight},
                documents={"definition": {"content_sha256": "d" * 64}})
            bound.science = SimpleNamespace(cohorts={"toy": {"fictional": True}})
            bound.backend = SimpleNamespace()
            bound.complete = SimpleNamespace(context=lambda item: (preflight, source),
                lookup={row["context_id"]: {"receipt_sha256": sha(preflight / "receipt.json")}})
            bound.pf = SimpleNamespace(build_context=build_context, InvalidCheckpoint=VerificationFailure,
                error_record=lambda error: {"type": "builtins.ValueError", "message": str(error), "traceback": "different relocated traceback"})
            bound.reuse = SimpleNamespace(compare_first_draw=lambda *args: {"synthetic": "same input failure"})
            def check(supplied):
                path = witnesses / "receipt.json"
                if path.exists():
                    path.unlink()
                replay = seal({"request": supplied, "context_id": row["context_id"], "status": "independent_original_first_draw_verified",
                    "original_replay": {"status": "input_failure"}, "assessment": {"synthetic": "same input failure"}, "artifacts": {}})
                write_new(path, replay)
                bound.pins = Pins()
                bound.replay = {row["context_id"]: {"receipt_path": "receipt.json", "receipt_sha256": sha(path),
                    "receipt_content_sha256": replay["content_sha256"]}}
                return bound.context(row, SimpleNamespace(dataset="toy"))
            self.assertEqual(check(request)["record"]["status"], "input_failure")
            for key in request:
                changed = {**request, key: "changed bound field"}
                with self.assertRaises(VerificationFailure, msg=key):
                    check(changed)

    def test_frozen_science_definitions_only_compiled_not_backend_instantiated(self):
        blob = subprocess.check_output(["git", "show", "8551d326b02bfe88915cfd9eb50c6ca8e5690e3a:src/pipelines/extensions/verification.py"],
                                       cwd=VERIFICATION.parents[2])
        temporary = tempfile.TemporaryDirectory(prefix="historical-verification-source-")
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name).resolve() / "historical_verification.py"
        path.write_bytes(blob)
        self.assertEqual(sha(path), json.loads((VERIFICATION / "source_pins.json").read_text())["files"]["analysis"]["src/pipelines/extensions/verification.py"])
        selected = load_verification_definitions(path, {})
        self.assertEqual(set(vars(selected)), {"SavedForecast", "assert_scientific_equal", "verify_trace_diagnostics", "verify_cell_identity"})
        self.assertNotIn("verify_extension_run", vars(selected))
        # Instantiation only stores a fictional mapping; it does not score it.
        self.assertEqual(selected.SavedForecast({"fictional": True}).p, {"fictional": True})

    def test_existing_pilot_definition_uses_dimensions_not_original_status(self):
        path = VERIFICATION.parent / "fit_common.py"
        definitions = load_fit_gate_definitions(path)
        rows = [{"original_cell_id": "large_pending", "model": "catalytic_fixed", "setting": "expression", "gene_budget": 512,
                 "n_train": 100, "p": 200},
                {"original_cell_id": "small_ready", "model": "catalytic_fixed", "setting": "expression", "gene_budget": 512,
                 "n_train": 100, "p": 20}]
        self.assertEqual(definitions["select_pilots"](rows), ["large_pending"])
        rows.append({**rows[0], "original_cell_id": "a_tie"})
        self.assertEqual(definitions["select_pilots"](rows), ["a_tie"])

    def test_output_preparation_rejects_overlap_and_replay_mutation(self):
        with tempfile.TemporaryDirectory(prefix="fictional_output_guard_") as temporary:
            root = Path(temporary).resolve()
            source = root / "source"
            source.mkdir()
            gates = SimpleNamespace(roots={"source": source}, files={})
            with self.assertRaisesRegex(VerificationFailure, "overlaps"):
                prepare_output(source / "inside", gates, {}, replay=False)
            output = root / "output"
            prepare_output(output, gates, {"synthetic_only": True}, replay=False)
            with self.assertRaisesRegex(VerificationFailure, "write-once"):
                prepare_output(output, gates, {}, replay=False)
            write_new(output / "completion.json", seal({"synthetic_only": True}))
            before = {str(path): sha(path) for path in output.rglob("*") if path.is_file()}
            prepare_output(output, gates, {}, replay=True)
            self.assertEqual(before, {str(path): sha(path) for path in output.rglob("*") if path.is_file()})

    def test_259_checker_is_mocked_and_nonzero_preserved(self):
        with tempfile.TemporaryDirectory(prefix="fictional_environment_guard_") as temporary:
            root = Path(temporary).resolve()
            source, output = root / "source", root / "output"
            (source / "scripts").mkdir(parents=True)
            output.mkdir()
            (source / "scripts/verify_environment.py").write_bytes(b"fictional checker not executed")
            (source / "conda-lock.yml").write_bytes(b"fictional lock")
            (source / "conda-lock.yml.sha256").write_text(sha(source / "conda-lock.yml") + "  conda-lock.yml\n")
            report = {"status": "ok", "package_count": 259}
            gates = SimpleNamespace(roots={"production": source}, pins=Pins(),
                original={"input_sha256": {name: sha(source / name) for name in ("scripts/verify_environment.py", "conda-lock.yml")}},
                preflight_manifest={"environment_verification": report}, documents={"definition": {"environment_verification": report}})
            def invoke(*args, **kwargs):
                return SimpleNamespace(returncode=5, stdout=b"", stderr=b"fictional environment rejection")
            with self.assertRaisesRegex(VerificationFailure, "checker failed"):
                actual_environment(gates, output, invoke=invoke)
            self.assertEqual(read(output / "environment_invocation.json")["exit_code"], 5)

    def test_inventory_does_not_admit_unbound_corrected_check(self):
        files, _directories = complete_output_inventory(Path("/unused"), ["a", "b"], ["a"])
        self.assertIn("checks/corrected/a.json", files)
        self.assertNotIn("checks/corrected/b.json", files)

    def test_no_top_level_scientific_backend_or_reducer_calls(self):
        own = VERIFICATION
        for name in ("frozen_backend.py", "bound_lineage.py", "science_verification.py", "mixed_analysis.py"):
            tree = ast.parse((own / name).read_text())
            for node in tree.body:
                if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                    self.fail("top-level function call in preparation " + name)


if __name__ == "__main__":
    unittest.main()
