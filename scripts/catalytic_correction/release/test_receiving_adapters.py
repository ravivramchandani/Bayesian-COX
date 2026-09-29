"""Relocated tiny byte fixtures/injected child processes; no scientific execution."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import release_core as c
import verify_restored_correction as vr
from test_release_adapters import Fixture, binding, raw, save


def receiving(fixture: Fixture):
    """All status-shaped files below are fictional and stay in test temporary roots."""
    restored, _ = fixture.stage()
    manifest = c.document(restored / "corrected_release_stage.json", c.Pins())
    bindings = copy.deepcopy(fixture.bindings)
    for name in c.ROOTS - c.EXTERNAL:
        bindings["roots"][name] = str(restored / c.LAYOUT[name])
    for name, row in manifest["verified_input_file_locations"].items():
        bindings["files"][name] = {"path": str(restored / row["relative_path"]), "sha256": row["sha256"]}
    bindings["review_paths"] = {name: str(restored / row["relative_path"]) for name, row in manifest["verified_review_locations"].items()}
    verification_binding_path = fixture.base / "receiving_bindings.json"
    save(verification_binding_path, bindings)
    repro_path = fixture.base / "receiving_reproduction.json"
    save(repro_path, {"status": "corrected_selected_reproduction_receiving_bindings",
        "selection_sha256": manifest["corrected_reproduction"]["selection_sha256"],
        "completed_pass": {"path": "passes/fictional_complete.json", "sha256": manifest["corrected_reproduction"]["pass_sha256"]},
        "immutable_roots": [{"root": str(restored), "artifacts": c.inventory_tree(restored, c.Pins())["files"]}],
        "immutable_files": [], "path_map": [{"historical": row["historical_source"], "restored": str(restored / row["payload_relative"]),
            "kind": "file" if row["kind"] == "file" else "directory"} for row in manifest["historical_roots"].values()]})
    report_path = fixture.base / "receiving_reporting.json"
    report_files = {}
    for name, row in manifest["support_input_file_locations"].items():
        path = (restored / row["relative_path"] if row["kind"] == "payload"
                else Path(fixture.bindings["roots"][row["role"]]) / row["relative_path"])
        report_files[name] = {"path": str(path), "sha256": row["sha256"]}
    report_roots = {name: str(restored / c.LAYOUT[name]) for name in ("mixed_verified", "reproduction", "rendered", "qa")}
    report_roots.update(sidecar=str(restored / c.LAYOUT["reporting"]), payload=str(restored))
    report_roots.update({name: fixture.bindings["roots"][name] for name in ("primary", "sampler", "robustness")})
    save(report_path, {"status": "corrected_reporting_read_only_replay_request", "roots": report_roots, "files": report_files,
        "preparation_receipt": {"path": str(restored / c.LAYOUT["support"] / "preparation_receipt.json"),
                                "sha256": manifest["reporting_qa_preparation_sha256"]},
        "mixed_completion_sha256": manifest["mixed_completion_sha256"],
        "sidecar_receipt_sha256": manifest["corrected_reporting"]["sidecar_receipt_sha256"],
        "selected_pass_sha256": manifest["corrected_reproduction"]["pass_sha256"],
        "visual_qa_receipt_sha256": manifest["corrected_visual_transfer"]["receipt_sha256"]})
    code = fixture.source / "fictional_transport"
    prefix = fixture.base / "fictional_fresh_transport"
    prefix.mkdir()
    script = code / "verify.py"
    bootstrap = "import runpy,sys;sys.path.insert(0,sys.argv[1]);sys.argv=sys.argv[2:];runpy.run_path(sys.argv[0],run_name='__main__')"
    python = Path("/fictional/locked_python")
    argv = [str(python), "-I", "-B", "-c", bootstrap, str(code), str(script), str(fixture.base / "fictional_package"),
            str(restored), "--expected-sha256", "a" * 64]
    def transport_invoke(*_args, **_kwargs):
        return SimpleNamespace(returncode=0, stdout=(json.dumps({"canonical_sha256": "a" * 64, "restored": str(restored),
            "shards": 1, "members": 1, "fictional_no_transport_executed": True}) + "\n").encode(), stderr=b"")
    captured = c.capture_process(argv, prefix / "transport", c.Pins(), status="corrected_transport_restore_actual_rc0_captured",
        validate_summary=lambda _summary: None, entrypoint=script, entrypoint_sha=c.sha(script), invoke=transport_invoke)
    request = {"status": "corrected_private_restore_verification_request", "test_only": False, "restored": str(restored),
        "stage_manifest_sha256": c.sha(restored / "corrected_release_stage.json"),
        "verification_bindings": {"path": str(verification_binding_path), "sha256": c.sha(verification_binding_path)},
        "external_roots": {name: fixture.bindings["roots"][name] for name in c.EXTERNAL},
        "transport_capture": {"path": captured["receipt_path"], "sha256": captured["receipt_sha256"]},
        "trusted_inventory_canonical_sha256": "a" * 64,
        "reproduction_bindings": {"path": str(repro_path), "sha256": c.sha(repro_path)},
        "reporting_replay_request": {"path": str(report_path), "sha256": c.sha(report_path)}}
    output, calls = fixture.base / "fresh_receiving_proofs", []
    def child_invoke(argv, **_kwargs):
        calls.append(argv)
        def argument(name):
            return Path(argv[argv.index(name) + 1])
        if Path(argv[3]).name == "verify_mixed_extensions.py":
            pre = argument("--replay-prefix")
            env_stdout = pre.with_name(pre.name + ".environment.stdout.json")
            env_stderr = pre.with_name(pre.name + ".environment.stderr.log")
            save(env_stdout, fixture.environment, None)
            raw(env_stderr, b"fictional environment logs; checker never executed\n")
            production = Path(bindings["roots"]["production"])
            save(pre.with_name(pre.name + ".environment_invocation.json"), {
                "operation": "fresh_original_259_package_environment_verification", "exit_code": 0,
                "argv": [str(python), "-B", str(production / "scripts/verify_environment.py"),
                    "--lock-file", str(production / "conda-lock.yml"), "--hash-file", str(production / "conda-lock.yml.sha256")],
                "checker_sha256": c.sha(production / "scripts/verify_environment.py"),
                "stdout_sha256": c.sha(env_stdout), "stderr_sha256": c.sha(env_stderr), "fictional": True})
            summary = {"status": c.MIXED_STATUS, "verify_existing": True, "verified_logical_cells": 3, "programme_complete": False}
            save(pre.with_name(pre.name + ".receipt.json"), {"status": "actual_deep_restored_evidence_replay_completed",
                "existing_completion_sha256": manifest["mixed_completion_sha256"], "scientific_files_reproduced_exactly": True,
                "argv": argv[3:], "input_bindings_sha256": request["verification_bindings"]["sha256"],
                "preparation_receipt_sha256": fixture.pins["mixed_verifier_preparation_sha256"],
                "actual_numeric_thread_environment": {name: "1" for name in c.NUMERIC}, "fictional": True})
        elif Path(argv[3]).name == "verify_restored_reproduction.py":
            directory = argument("--output")
            directory.mkdir()
            path = directory / "receipt.json"
            save(path, {"status": "corrected_selected_reproduction_restored_read_only_verified", "test_only_dependency_injection": False,
                "selection_sha256": manifest["corrected_reproduction"]["selection_sha256"],
                "completed_pass_sha256": manifest["corrected_reproduction"]["pass_sha256"], "artifacts": {}, "fictional": True})
            summary = {"status": "corrected_selected_reproduction_restored_read_only_verified",
                "selection_sha256": manifest["corrected_reproduction"]["selection_sha256"],
                "selected_pass_sha256": manifest["corrected_reproduction"]["pass_sha256"], "route_counts": manifest["corrected_reproduction"]["route_counts"],
                "scheduled_selected_cells": 3, "accounted_selected_cells": 3, "no_new_numerical_fit": True, "no_new_generator_recipe": True,
                "receipt_path": str(path), "receipt_sha256": c.sha(path)}
        else:
            c.require(Path(argv[3]).name == "report_replay.py", "only fictional read-only report entrypoint expected")
            directory = argument("--output")
            directory.mkdir()
            parts = {}
            for name in ("claim_replay_summary.json", "preserved_visual_qa.json"):
                path = directory / name
                save(path, {"fictional": name})
                parts[name] = binding(path)
            path = directory / "reporting_replay_receipt.json"
            summary = {"status": "corrected_reporting_source_replay_verified", "sidecar_receipt_sha256": manifest["corrected_reporting"]["sidecar_receipt_sha256"],
                "deterministic_bytes_reproduced_exactly": True, "no_new_fit_generator_optimizer_or_inference": True}
            save(path, {**summary, "artifacts": parts, "test_only": False, "fictional": True})
            summary.update(receipt_path=str(path), receipt_sha256=c.sha(path))
        return SimpleNamespace(returncode=0, stdout=(json.dumps(summary) + "\n").encode(), stderr=b"fictional injected child\n")
    def test_payload(root, digest, pins):
        # Scope is an explicitly injected test policy. Production CLI has no seam.
        value = c.document(root / "corrected_release_stage.json", pins, digest)
        expected = value["payload_inventory"]
        c.require(c.inventory_tree(root, pins) == {"files": {**expected["files"], "corrected_release_stage.json": binding(root / "corrected_release_stage.json")},
                      "directories": expected["directories"]}, "fictional immutable payload changed")
        return value
    return request, output, python, {"invoke": child_invoke, "verify_payload": test_payload}, calls


class ReceivingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="fictional-correction-receiving-")
        self.base = Path(self.temporary.name).resolve(strict=True)

    def tearDown(self):
        self.temporary.cleanup()

    def test_three_read_only_replays_positive_and_exact_inventory(self):
        fixture = Fixture(self.base)
        request, output, python, deps, calls = receiving(fixture)
        result = vr.science(request, output, python, fixture.pins, c.Pins(), deps, policy=fixture.policy)
        receipt = c.document(Path(result["receipt_path"]), c.Pins())
        self.assertTrue(receipt["test_only"])
        self.assertFalse(receipt["programme_complete"])
        self.assertEqual(len(calls), 3)
        self.assertIn("--verify-existing", calls[0])
        self.assertEqual([Path(argv[3]).name for argv in calls],
                         ["verify_mixed_extensions.py", "verify_restored_reproduction.py", "report_replay.py"])
        self.assertEqual(len(receipt["output_inventory"]["files"]), 20)

    def test_production_policy_refuses_injected_replay(self):
        fixture = Fixture(self.base)
        request, output, python, deps, _calls = receiving(fixture)
        with self.assertRaisesRegex(ValueError, "injection"):
            vr.science(request, output, python, fixture.pins, c.Pins(), deps)
        self.assertFalse(output.exists())

    def test_each_actual_child_failure_retains_rc_and_stops(self):
        for target in ("verify_mixed_extensions.py", "verify_restored_reproduction.py", "report_replay.py"):
            with self.subTest(target=target), tempfile.TemporaryDirectory(dir=self.base) as folder:
                fixture = Fixture(Path(folder))
                request, output, python, deps, calls = receiving(fixture)
                successful = deps["invoke"]
                def invoke(argv, *, _target=target, _calls=calls, _successful=successful, **kwargs):
                    if Path(argv[3]).name == _target:
                        _calls.append(argv)
                        return SimpleNamespace(returncode=23, stdout=b"fictional retained failure\n", stderr=b"fixture stderr")
                    return _successful(argv, **kwargs)
                deps["invoke"] = invoke
                with self.assertRaisesRegex(ValueError, "child failed"):
                    vr.science(request, output, python, fixture.pins, c.Pins(), deps, policy=fixture.policy)
                self.assertFalse((output / "receipt.json").exists())
                prefix = {"verify_mixed_extensions.py": "mixed", "verify_restored_reproduction.py": "reproduction",
                          "report_replay.py": "reporting"}[target]
                self.assertEqual(c.document(output / (prefix + "_process.attempt.json"), c.Pins())["exit_code"], 23)

    def test_unknown_replay_file_refuses_final_receipt(self):
        fixture = Fixture(self.base)
        request, output, python, deps, _calls = receiving(fixture)
        original = deps["invoke"]
        def invoke(argv, **kwargs):
            result = original(argv, **kwargs)
            if Path(argv[3]).name == "report_replay.py":
                raw(output / "unknown_partial.bytes", b"injected unknown bytes")
            return result
        deps["invoke"] = invoke
        with self.assertRaisesRegex(ValueError, "extra/residual"):
            vr.science(request, output, python, fixture.pins, c.Pins(), deps, policy=fixture.policy)
        self.assertFalse((output / "receipt.json").exists())

    def test_changed_immutable_payload_stops_before_next_child(self):
        fixture = Fixture(self.base)
        request, output, python, deps, calls = receiving(fixture)
        original = deps["invoke"]
        def invoke(argv, **kwargs):
            result = original(argv, **kwargs)
            if Path(argv[3]).name == "verify_mixed_extensions.py":
                raw(Path(request["restored"]) / c.LAYOUT["matched"], b"changed fictional matched bytes")
            return result
        deps["invoke"] = invoke
        with self.assertRaises(ValueError):
            vr.science(request, output, python, fixture.pins, c.Pins(), deps, policy=fixture.policy)
        self.assertEqual(len(calls), 1)
        self.assertFalse((output / "receipt.json").exists())

    def test_reporting_old_tree_pointer_refuses_before_output(self):
        fixture = Fixture(self.base)
        request, output, python, deps, calls = receiving(fixture)
        path = Path(request["reporting_replay_request"]["path"])
        value = c.document(path, c.Pins())
        value["roots"]["mixed_verified"] = str(fixture.roots["mixed_verified"])
        request["reporting_replay_request"]["sha256"] = save(path, value)
        with self.assertRaisesRegex(ValueError, "fresh restored"):
            vr.science(request, output, python, fixture.pins, c.Pins(), deps, policy=fixture.policy)
        self.assertFalse(output.exists())
        self.assertFalse(calls)

    def test_reporting_original_claim_pointer_refuses_even_when_bytes_match(self):
        fixture = Fixture(self.base)
        request, output, python, deps, calls = receiving(fixture)
        path = Path(request["reporting_replay_request"]["path"])
        value = c.document(path, c.Pins())
        value["files"]["claim_stdout"]["path"] = str(fixture.roots["claim_capture"] / "claim.stdout.log")
        request["reporting_replay_request"]["sha256"] = save(path, value)
        with self.assertRaisesRegex(ValueError, "fresh role"):
            vr.science(request, output, python, fixture.pins, c.Pins(), deps, policy=fixture.policy)
        self.assertFalse(output.exists())
        self.assertFalse(calls)

    def test_synthetic_reproduction_proof_cannot_authorize_reporting(self):
        fixture = Fixture(self.base)
        request, output, python, deps, calls = receiving(fixture)
        original = deps["invoke"]
        def invoke(argv, **kwargs):
            result = original(argv, **kwargs)
            if Path(argv[3]).name == "verify_restored_reproduction.py":
                summary = json.loads(result.stdout)
                path = Path(summary["receipt_path"])
                value = c.document(path, c.Pins())
                value["test_only_dependency_injection"] = True
                summary["receipt_sha256"] = save(path, value)
                result.stdout = (json.dumps(summary) + "\n").encode()
            return result
        deps["invoke"] = invoke
        with self.assertRaisesRegex(ValueError, "synthetic"):
            vr.science(request, output, python, fixture.pins, c.Pins(), deps, policy=fixture.policy)
        self.assertEqual(len(calls), 2)
        self.assertFalse((output / "receipt.json").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
