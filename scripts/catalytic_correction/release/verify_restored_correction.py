"""Actual read-only receiving replay with fresh captures outside immutable roots.

Transport mode delegates the pinned original verifier. Science mode invokes only
the sealed mixed --verify-existing CLI, a receiving-only reproduction reader and
a separately pinned read-only reporting replayer. Never execution/resume fits.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

if __name__ == "__main__":
    _parser = argparse.ArgumentParser(add_help=False)
    _parser.add_argument("--preparation-receipt", type=Path, required=True)
    _parser.add_argument("--preparation-receipt-sha256", required=True)
    _initial, _unknown = _parser.parse_known_args()
    if hashlib.sha256(_initial.preparation_receipt.read_bytes()).hexdigest() != _initial.preparation_receipt_sha256:
        raise RuntimeError("adapter preparation receipt differs")
    _preparation = json.loads(_initial.preparation_receipt.read_text())
    _own = Path(__file__).absolute().parent
    for _name, _digest in _preparation["implementation_source_sha256"].items():
        if Path(_name).name != _name or hashlib.sha256((_own / _name).read_bytes()).hexdigest() != _digest:
            raise RuntimeError("adapter implementation source differs")
    sys.path.insert(0, str(_own))

import release_core as core  # noqa: E402


def verify_payload(root: Path, manifest_sha: str, pins: core.Pins) -> dict[str, Any]:
    """Exact staged bytes, not a new claim of deep scientific readiness."""
    manifest_path = root / "corrected_release_stage.json"
    manifest = core.document(manifest_path, pins, manifest_sha)
    core.require(manifest["status"] == "corrected_private_payload_staged_with_separate_actual_source_gates"
                 and manifest["evidence_status"] == core.EVIDENCE and manifest["test_only"] is False
                 and manifest["remote_download_restore_or_publication_certified"] is False, "actual corrected staged payload required")
    expected = manifest["payload_inventory"]
    current = core.inventory_tree(root, pins)
    expected_files = {**expected["files"], "corrected_release_stage.json": {"sha256": manifest_sha, "bytes": manifest_path.stat().st_size}}
    core.require(current == {"files": expected_files, "directories": expected["directories"]}, "restored payload changed/missing/extra")
    return manifest


def validate_remapping(root: Path, manifest: dict[str, Any], bindings: dict[str, Any], pins: core.Pins) -> None:
    """Only exact explicit roles preserve their recorded source byte identities."""
    core.require(set(bindings["roots"]) == core.ROOTS and set(bindings["files"]) == core.FILES
                 and set(bindings["review_paths"]) == core.REVIEWS, "receiving mixed roles differ")
    for name in core.ROOTS - core.EXTERNAL:
        core.require(Path(bindings["roots"][name]) == root / core.LAYOUT[name], "automatic/foreign role remapping refused")
    for name, stored in manifest["verified_input_file_locations"].items():
        binding = bindings["files"][name]
        core.require(binding == {"path": str(root / stored["relative_path"]), "sha256": stored["sha256"]},
                     "receiving frozen file mapping/digest changed")
        pins.bind(Path(binding["path"]), binding["sha256"])
    for name, stored in manifest["verified_review_locations"].items():
        path = root / stored["relative_path"]
        core.require(bindings["review_paths"][name] == str(path), "actual review mapping changed")
        pins.bind(path, stored["sha256"])
    for name in ("resolution_review", "pilot_review"):
        stored = manifest["optional_review_locations"].get(name)
        if stored is None:
            core.require(bindings.get(name) is None, "foreign later review substituted")
        else:
            core.require(bindings.get(name) == {"path": str(root / stored["relative_path"]), "sha256": stored["sha256"]},
                         "reviewed pending/pilot mapping/digest changed")
    for name, item in manifest["required_external_baselines"].items():
        core.artifact_map(core.safe(Path(bindings["roots"][name])), item["files"], pins)
    for name, values in manifest["external_retained_file_bindings"].items():
        core.artifact_map(core.safe(Path(bindings["roots"][name])), values, pins)


def validate_reproduction_bindings(value: dict[str, Any], root: Path, manifest: dict[str, Any], request: dict[str, Any],
                                   pins: core.Pins) -> None:
    """Bind resolver inputs to this restored payload and actual external roles."""
    core.require(value["status"] == "corrected_selected_reproduction_receiving_bindings"
                 and value["selection_sha256"] == manifest["corrected_reproduction"]["selection_sha256"]
                 and value["completed_pass"]["sha256"] == manifest["corrected_reproduction"]["pass_sha256"],
                 "receiving reproduction uses foreign selection/pass")
    allowed = [root, *(core.safe(Path(path)) for path in request["external_roots"].values())]
    for item in value["immutable_roots"]:
        location = core.safe(Path(item["root"]))
        core.require(any(location == ancestor or location.is_relative_to(ancestor) for ancestor in allowed),
                     "reproduction trusted inventory lies outside explicitly restored roles")
        core.artifact_map(location, item["artifacts"], pins)
    for item in value["immutable_files"]:
        location = core.safe(Path(item["path"]))
        core.require(any(location == ancestor or location.is_relative_to(ancestor) for ancestor in allowed),
                     "reproduction trusted file lies outside explicitly restored roles")
        binding = item["binding"]
        pins.bind(location, binding["sha256"], size=binding["bytes"])
    for item in value["path_map"]:
        source, restored = Path(item["historical"]), core.safe(Path(item["restored"]))
        core.require(source.is_absolute() and ".." not in source.parts and item["kind"] in {"directory", "file"}
                     and any(restored == ancestor or restored.is_relative_to(ancestor) for ancestor in allowed),
                     "implicit/unsafe receiving reproduction mapping")
        allowed_pairs = {(row["historical_source"], str(root / row["payload_relative"]),
                          "file" if row["kind"] == "file" else "directory")
                         for row in manifest["historical_roots"].values()}
        allowed_pairs |= {(row["historical_source"], request["external_roots"][name], "directory")
                          for name, row in manifest["external_root_roles"].items()}
        allowed_pairs |= {(row["historical_source"], str(root / row["payload_relative"]), "file")
                          for row in manifest["retained_external_file_locations"]}
        core.require((str(source), str(restored), item["kind"]) in allowed_pairs, "reproduction mapping absent from explicit staged lineage")
    # The sibling reader independently checks full exact inventories, nested
    # mapping consistency and every source/producer/review identity. No rewrite.


def validate_reporting_bindings(value: dict[str, Any], root: Path, manifest: dict[str, Any], external: dict[str, str],
                                pins: core.Pins) -> None:
    """Fresh reporting reads exact restored roles, never a byte-identical old tree."""
    expected_roots = {name: str(root / core.LAYOUT[name]) for name in ("mixed_verified", "reproduction", "rendered", "qa")}
    expected_roots.update(sidecar=str(root / core.LAYOUT["reporting"]), payload=str(root))
    expected_roots.update({name: external[name] for name in ("primary", "sampler", "robustness")})
    core.require(value["roots"] == expected_roots, "reporting replay must use exact fresh restored evidence/baseline roles")
    core.require(set(value["files"]) == set(manifest["support_input_file_locations"]), "receiving reporting file scope differs")
    for name, location in manifest["support_input_file_locations"].items():
        if location["kind"] == "payload":
            path = core.child(root, location["relative_path"])
        else:
            core.require(location["kind"] == "external" and location["role"] in core.EXTERNAL, "unknown external reporting file role")
            path = core.child(Path(external[location["role"]]), location["relative_path"])
        core.require(value["files"][name] == {"path": str(path), "sha256": location["sha256"]},
                     "reporting replay file bypasses explicit fresh role: " + name)
        pins.bind(path, location["sha256"])
    support = root / core.LAYOUT["support"]
    core.require(value["preparation_receipt"] == {"path": str(support / "preparation_receipt.json"),
                 "sha256": manifest["reporting_qa_preparation_sha256"]}, "receiving reporting helper preparation role differs")


def validate_historical_mixed_capture(root: Path, manifest: dict[str, Any], pins: core.Pins) -> None:
    """Revalidate immutable genuine source metadata using explicit staged roles.

    Recorded original argv/path text is never rewritten or replaced by receiver
    interpreter identity. Only current file I/O resolves to trusted staged roles.
    This is preservation of original process proof, not a new rc or approval.
    """
    capture_path = core.child(root, manifest["source_verifier_capture_location"])
    core.require(capture_path.parent == root / core.LAYOUT["source_capture"], "source capture escaped its explicit retained role")
    value = core.capture_record(capture_path, manifest["source_verifier_capture_sha256"], pins,
        status="mixed_verification_actual_rc0_captured", summary_status=core.MIXED_STATUS,
        completion_sha=manifest["mixed_completion_sha256"])
    attempt_path = capture_path.with_name(capture_path.name.removesuffix(".receipt.json") + ".attempt.json")
    attempt = core.document(attempt_path, pins, value["invocation_attempt_sha256"])
    producer_root = root / core.LAYOUT["release_adapter_preparation"]
    prep = core.load_preparation(producer_root, manifest["release_adapter_preparation_sha256"], pins)
    verifier_root = root / core.LAYOUT["verification_preparation"]
    verifier = core.load_preparation(verifier_root, manifest["verification_preparation_receipt_sha256"], pins)
    historical = {name: Path(item["historical_source"]) for name, item in manifest["historical_roots"].items()}
    core.require(all(path.is_absolute() and ".." not in path.parts for path in historical.values()), "historical source path grammar differs")
    producer_history, verifier_history = historical["release_adapter_preparation"], historical["verification_preparation"]
    expected_producer = {
        "entrypoint": {"historical_path": str(producer_history / "capture_mixed_source.py"),
                       "sha256": prep["implementation_source_sha256"]["capture_mixed_source.py"]},
        "preparation_receipt": {"historical_path": str(producer_history / "preparation_receipt.json"),
                                "sha256": manifest["release_adapter_preparation_sha256"]},
        "implementation_source_sha256": {str(producer_history / name): digest
                                         for name, digest in prep["implementation_source_sha256"].items()},
    }
    expected_inputs = {str(verifier_history / name): digest for name, digest in verifier["implementation_source_sha256"].items()}
    expected_inputs[str(verifier_history / "preparation_receipt.json")] = manifest["verification_preparation_receipt_sha256"]
    expected_inputs[str(historical["source_verification_bindings"])] = manifest["source_verification_bindings_sha256"]
    pins.bind(root / core.LAYOUT["source_verification_bindings"], manifest["source_verification_bindings_sha256"])
    argv = attempt["argv"]
    runtime = attempt["runtime"]
    core.require(isinstance(argv, list) and all(isinstance(item, str) for item in argv) and len(argv) == 14
                 and Path(argv[0]).is_absolute() and ".." not in Path(argv[0]).parts
                 and argv == [runtime["python_executable"], "-I", "-B", str(verifier_history / "verify_mixed_extensions.py"),
                    "--preparation-receipt", str(verifier_history / "preparation_receipt.json"),
                    "--preparation-receipt-sha256", manifest["verification_preparation_receipt_sha256"],
                    "--input-bindings", str(historical["source_verification_bindings"]),
                    "--input-bindings-sha256", manifest["source_verification_bindings_sha256"],
                    "--output", str(historical["mixed_verified"])], "historical mixed source argv/input identities differ")
    core.require(attempt["operation"] == core.MIXED_CAPTURE_OPERATION
                 and attempt["entrypoint"] == {"historical_path": str(verifier_history / "verify_mixed_extensions.py"),
                     "sha256": verifier["implementation_source_sha256"]["verify_mixed_extensions.py"]}
                 and attempt.get("test_only_dependency_injection") is False
                 and value.get("test_only_dependency_injection") is False
                 and attempt["capture_producer"] == value["capture_producer"] == expected_producer
                 and attempt["implementation_source_sha256"] == expected_inputs
                 and attempt["runtime"] == value["runtime"] and runtime["locked_interpreter_samefile"] is True
                 and runtime["numeric_thread_environment"] == attempt["numeric_thread_environment"]
                 and attempt["numeric_thread_environment"] == value["numeric_thread_environment"]
                     == {name: "1" for name in core.NUMERIC}, "original genuine mixed producer proof missing/injected/foreign")
    pins.recheck()


def transport(request: dict[str, Any], output: Path, python: Path, source_pins: dict[str, Any], pins: core.Pins,
              dependencies: dict[str, Any]) -> dict[str, Any]:
    """Delegate unchanged safe archive verification; source/private download separate."""
    core.require(request["status"] == "corrected_transport_restore_request", "explicit transport request required")
    code, package, restored = (core.safe(Path(request[name])) for name in ("transport_code", "package", "restored"))
    for name, digest in source_pins["transport_sources"].items():
        pins.bind(code / name, digest)
    core.no_overlap(restored, [package, code, output])
    core.no_overlap(output, [package, code, restored])
    expected = request["trusted_inventory_canonical_sha256"]
    core.require(isinstance(expected, str) and len(expected) == 64 and all(letter in "0123456789abcdef" for letter in expected),
                 "trusted canonical transport digest required")
    output.mkdir()
    script = code / "verify.py"
    argv = [str(python), "-I", "-B", str(script), str(package), str(restored), "--expected-sha256", expected]
    # Original verify.py is a script with sibling archive_common import. -I
    # removes script-directory sys.path; execute its source via an isolated
    # explicit pinned-path bootstrap rather than weaken interpreter isolation.
    code_text = "import runpy,sys;sys.path.insert(0,sys.argv[1]);sys.argv=sys.argv[2:];runpy.run_path(sys.argv[0],run_name='__main__')"
    argv = [str(python), "-I", "-B", "-c", code_text, str(code), str(script), str(package), str(restored), "--expected-sha256", expected]
    def checked(summary: dict[str, Any]) -> None:
        core.require(summary["canonical_sha256"] == expected and summary["restored"] == str(restored)
                     and type(summary["shards"]) is int and summary["shards"] > 0
                     and type(summary["members"]) is int and summary["members"] > 0,
                     "actual transport stdout differs from trusted inventory/restore")
    result = core.capture_process(argv, output / "transport", pins, status="corrected_transport_restore_actual_rc0_captured",
        validate_summary=checked, entrypoint=script, entrypoint_sha=source_pins["transport_sources"]["verify.py"],
        invoke=dependencies.get("invoke", subprocess.run))
    core.require(restored.is_dir(), "actual verified restore absent")
    capture = core.document(Path(result["receipt_path"]), pins, result["receipt_sha256"])
    core.declared_output_tree(output, capture, pins, receipt_name="transport.receipt.json")
    return {"status": result["status"], "receipt_path": result["receipt_path"], "receipt_sha256": result["receipt_sha256"],
            "scientific_verification_completed": False, "programme_complete": False}


def science(request: dict[str, Any], output: Path, python: Path, source_pins: dict[str, Any], pins: core.Pins,
            dependencies: dict[str, Any], *, policy: core.Policy = core.PRODUCTION_POLICY) -> dict[str, Any]:
    """Actual fresh verification only; no cached receipt manufactures rc0 success."""
    core.require(request["status"] == "corrected_private_restore_verification_request" and request["test_only"] is False,
                 "actual corrected receiving request required")
    core.require(not dependencies or policy.test_only, "dependency injection is restricted to fictional test policies")
    restored = core.safe(Path(request["restored"]))
    payload_verifier = dependencies.get("verify_payload", verify_payload)
    manifest = payload_verifier(restored, request["stage_manifest_sha256"], pins)
    bindings_path, bindings = core.record(request["verification_bindings"], pins)
    validate_remapping(restored, manifest, bindings, pins)
    core.require(set(request["external_roots"]) == core.EXTERNAL
                 and all(request["external_roots"][name] == bindings["roots"][name] for name in core.EXTERNAL),
                 "exact external source/baseline receiving roles required")
    immutable = [restored, *(core.safe(Path(path)) for path in bindings["roots"].values()), bindings_path]
    core.no_overlap(output, immutable)
    transport_path, _ = core.record(request["transport_capture"], pins)
    transport_capture = core.capture_record(transport_path, request["transport_capture"]["sha256"], pins,
        status="corrected_transport_restore_actual_rc0_captured", summary_status=None)
    core.require(transport_capture["summary"]["canonical_sha256"] == request["trusted_inventory_canonical_sha256"]
                 and transport_capture["summary"]["restored"] == str(restored), "actual fresh trusted-download restore capture required")
    transport_attempt = core.document(transport_path.with_name(transport_path.name.removesuffix(".receipt.json") + ".attempt.json"), pins)
    transport_argv = transport_attempt["argv"]
    bootstrap = "import runpy,sys;sys.path.insert(0,sys.argv[1]);sys.argv=sys.argv[2:];runpy.run_path(sys.argv[0],run_name='__main__')"
    core.require(isinstance(transport_argv, list) and len(transport_argv) == 11
                 and transport_argv[:5] == [str(python), "-I", "-B", "-c", bootstrap]
                 and transport_argv[8:] == [str(restored), "--expected-sha256", request["trusted_inventory_canonical_sha256"]]
                 and Path(transport_argv[6]) == Path(transport_argv[5]) / "verify.py"
                 and transport_attempt["operation"] == "actual_corrected_transfer_child_capture"
                 and transport_attempt["entrypoint"] == {"historical_path": transport_argv[6], "sha256": source_pins["transport_sources"]["verify.py"]}
                 and transport_attempt["numeric_thread_environment"] == {name: "1" for name in core.NUMERIC},
                 "actual original safe-transport command/source proof differs")
    core.require(transport_attempt["test_only_dependency_injection"] is False or policy.test_only,
                 "injected transport proof cannot certify an actual restore")
    for name, digest in source_pins["transport_sources"].items():
        pins.bind(Path(transport_argv[5]) / name, digest)
    verified = restored / core.LAYOUT["mixed_verified"]
    validate_historical_mixed_capture(restored, manifest, pins)
    completion, _ = core.validate_mixed(verified, manifest["mixed_completion_sha256"], pins, policy)
    prep_root = restored / core.LAYOUT["verification_preparation"]
    preparation = core.load_preparation(prep_root, source_pins["mixed_verifier_preparation_sha256"], pins)
    reproduction_root = restored / core.LAYOUT["receiving_reproduction_preparation"]
    reproduction_prep = core.load_preparation(reproduction_root, manifest["receiving_reproduction_preparation_sha256"], pins)
    core.require(reproduction_prep["status"] == "corrected_reproduction_receiving_adapter_prepared"
                 and reproduction_prep["no_fit_or_generator_dispatch"] is True, "receiving-only reproduction helper required")
    reproduction_binding_path, reproduction_bindings = core.record(request["reproduction_bindings"], pins)
    validate_reproduction_bindings(reproduction_bindings, restored, manifest, request, pins)
    reporting_path, reporting_request = core.record(request["reporting_replay_request"], pins)
    core.require(reporting_request["status"] == "corrected_reporting_read_only_replay_request"
                 and reporting_request["mixed_completion_sha256"] == manifest["mixed_completion_sha256"]
                 and reporting_request["sidecar_receipt_sha256"] == manifest["corrected_reporting"]["sidecar_receipt_sha256"]
                 and reporting_request["selected_pass_sha256"] == manifest["corrected_reproduction"]["pass_sha256"]
                 and reporting_request["visual_qa_receipt_sha256"] == manifest["corrected_visual_transfer"]["receipt_sha256"],
                 "reporting replay inputs foreign or not read-only")
    validate_reporting_bindings(reporting_request, restored, manifest, request["external_roots"], pins)
    report_script = core.child(restored, manifest["support_source_locations"]["report_replay"])
    pins.bind(report_script, manifest["support_source_sha256"]["report_replay"])
    core.require(report_script.name != "run_reproduction.py", "execution controller is never a receiving entrypoint")
    for path in (reproduction_binding_path, reporting_path):
        core.require(not path.is_relative_to(restored), "new receiving bindings must stay outside immutable payload")
    pins.recheck()
    output.mkdir()
    invoke = dependencies.get("invoke", subprocess.run)
    captures = {}
    def mixed_checked(summary: dict[str, Any]) -> None:
        core.require(summary["status"] == core.MIXED_STATUS and summary["verify_existing"] is True
                     and summary["verified_logical_cells"] == policy.cells and summary["programme_complete"] is False,
                     "actual fresh deep replay summary differs")
    mixed_script = prep_root / "verify_mixed_extensions.py"
    argv = [str(python), "-I", "-B", str(mixed_script), "--preparation-receipt", str(prep_root / "preparation_receipt.json"),
            "--preparation-receipt-sha256", source_pins["mixed_verifier_preparation_sha256"],
            "--input-bindings", str(bindings_path), "--input-bindings-sha256", request["verification_bindings"]["sha256"],
            "--output", str(verified), "--verify-existing", "--replay-prefix", str(output / "mixed_replay")]
    captures["mixed"] = core.capture_process(argv, output / "mixed_process", pins,
        status="corrected_mixed_restored_replay_actual_rc0_captured", validate_summary=mixed_checked,
        entrypoint=mixed_script, entrypoint_sha=preparation["implementation_source_sha256"][mixed_script.name], invoke=invoke)
    replay = core.document(output / "mixed_replay.receipt.json", pins)
    core.require(replay["status"] == "actual_deep_restored_evidence_replay_completed"
                 and replay["existing_completion_sha256"] == manifest["mixed_completion_sha256"]
                 and replay["scientific_files_reproduced_exactly"] is True
                 and replay["argv"] == argv[3:] and replay["input_bindings_sha256"] == request["verification_bindings"]["sha256"]
                 and replay["preparation_receipt_sha256"] == source_pins["mixed_verifier_preparation_sha256"]
                 and replay["actual_numeric_thread_environment"] == {name: "1" for name in core.NUMERIC},
                 "actual fresh deep replay receipt absent or invocation foreign")
    env_prefix = output / "mixed_replay"
    env_invocation = core.document(env_prefix.with_name(env_prefix.name + ".environment_invocation.json"), pins)
    production = Path(bindings["roots"]["production"])
    env_stdout = env_prefix.with_name(env_prefix.name + ".environment.stdout.json")
    env_stderr = env_prefix.with_name(env_prefix.name + ".environment.stderr.log")
    core.require(env_invocation["operation"] == "fresh_original_259_package_environment_verification"
                 and env_invocation["exit_code"] == 0
                 and env_invocation["argv"] == [str(python), "-B", str(production / "scripts/verify_environment.py"),
                      "--lock-file", str(production / "conda-lock.yml"), "--hash-file", str(production / "conda-lock.yml.sha256")]
                 and env_invocation["checker_sha256"] == core.sha(production / "scripts/verify_environment.py")
                 and env_invocation["stdout_sha256"] == core.sha(env_stdout)
                 and env_invocation["stderr_sha256"] == core.sha(env_stderr), "fresh actual mixed checker rc0/log/source binding differs")
    env_report = core.document(env_stdout, pins, field=None)
    preflight_manifest = core.document(Path(bindings["roots"]["preflight"]) / "manifest.json", pins)
    core.require(env_report == preflight_manifest["environment_verification"] and env_report["status"] == "ok"
                 and env_report["package_count"] == 259, "actual fresh full259 report differs")
    def repro_checked(summary: dict[str, Any]) -> None:
        expected = manifest["corrected_reproduction"]
        core.require(summary["status"] == "corrected_selected_reproduction_restored_read_only_verified"
                     and summary["selection_sha256"] == expected["selection_sha256"]
                     and summary["selected_pass_sha256"] == expected["pass_sha256"]
                     and summary["scheduled_selected_cells"] == summary["accounted_selected_cells"] == len(expected["selected_cells"])
                     and summary["route_counts"] == expected["route_counts"] and summary["no_new_numerical_fit"] is True
                     and summary["no_new_generator_recipe"] is True, "actual restored selected reproduction proof differs")
    repro_script = reproduction_root / "verify_restored_reproduction.py"
    core.require(repro_script.name in reproduction_prep["implementation_source_sha256"], "read-only reproduction entrypoint omitted from tested pins")
    argv = [str(python), "-I", "-B", str(repro_script), "--bindings", str(reproduction_binding_path),
            "--bindings-sha256", request["reproduction_bindings"]["sha256"], "--output", str(output / "reproduction_review"), "--python", str(python)]
    captures["reproduction"] = core.capture_process(argv, output / "reproduction_process", pins,
        status="corrected_readonly_reproduction_actual_rc0_captured", validate_summary=repro_checked,
        entrypoint=repro_script, entrypoint_sha=reproduction_prep["implementation_source_sha256"][repro_script.name], invoke=invoke)
    repro_summary = captures["reproduction"]["summary"]
    repro_receipt = core.document(output / "reproduction_review/receipt.json", pins, repro_summary["receipt_sha256"])
    core.require(repro_summary["receipt_path"] == str(output / "reproduction_review/receipt.json")
                 and repro_receipt["status"] == "corrected_selected_reproduction_restored_read_only_verified"
                 and repro_receipt["test_only_dependency_injection"] is False
                 and repro_receipt["selection_sha256"] == manifest["corrected_reproduction"]["selection_sha256"]
                 and repro_receipt["completed_pass_sha256"] == manifest["corrected_reproduction"]["pass_sha256"],
                 "actual receiving reproduction receipt missing/foreign/synthetic")
    reproduction_inventory = core.declared_output_tree(output / "reproduction_review", repro_receipt, pins)
    def report_checked(summary: dict[str, Any]) -> None:
        core.require(summary["status"] == "corrected_reporting_source_replay_verified"
                     and summary["sidecar_receipt_sha256"] == manifest["corrected_reporting"]["sidecar_receipt_sha256"]
                     and summary["deterministic_bytes_reproduced_exactly"] is True
                     and summary["no_new_fit_generator_optimizer_or_inference"] is True, "actual corrected reporting replay absent")
    argv = [str(python), "-I", "-B", str(report_script), "--request", str(reporting_path),
            "--request-sha256", request["reporting_replay_request"]["sha256"], "--output", str(output / "reporting_review"), "--python", str(python)]
    captures["reporting"] = core.capture_process(argv, output / "reporting_process", pins,
        status="corrected_reporting_replay_actual_rc0_captured", validate_summary=report_checked,
        entrypoint=report_script, entrypoint_sha=manifest["support_source_sha256"]["report_replay"], invoke=invoke)
    report_summary = captures["reporting"]["summary"]
    report_receipt_path = output / "reporting_review/reporting_replay_receipt.json"
    report_receipt = core.document(report_receipt_path, pins, report_summary["receipt_sha256"])
    core.require(report_summary["receipt_path"] == str(report_receipt_path)
                 and report_receipt["status"] == "corrected_reporting_source_replay_verified"
                 and report_receipt["test_only"] is False, "actual receiving reporting receipt missing/foreign/synthetic")
    reporting_inventory = core.declared_output_tree(output / "reporting_review", report_receipt, pins,
                                                   receipt_name="reporting_replay_receipt.json")
    # Scientific process success does not replace exact immutable byte checks.
    payload_verifier(restored, request["stage_manifest_sha256"], pins)
    pins.recheck()
    expected_files = {}
    for value in captures.values():
        for name, binding in value["artifacts"].items():
            expected_files[name] = binding
        capture_path = Path(value["receipt_path"])
        expected_files[capture_path.name] = {"sha256": value["receipt_sha256"], "bytes": capture_path.stat().st_size}
    for suffix in (".receipt.json", ".environment.stdout.json", ".environment.stderr.log", ".environment_invocation.json"):
        path = output / ("mixed_replay" + suffix)
        expected_files[path.name] = {"sha256": core.sha(path), "bytes": path.stat().st_size}
    for name, inventory in (("reproduction_review", reproduction_inventory), ("reporting_review", reporting_inventory)):
        expected_files.update({str(Path(name) / relative): binding for relative, binding in inventory["files"].items()})
    actual_output = core.inventory_tree(output, pins)
    core.require(actual_output["files"] == expected_files, "fresh receiving output has missing/extra/residual files")
    receipt = core.seal({"schema_version": 1, "status": "corrected_private_restore_source_and_science_replay_verified",
        "stage_manifest_sha256": request["stage_manifest_sha256"], "mixed_completion_sha256": manifest["mixed_completion_sha256"],
        "trusted_transport_inventory_canonical_sha256": request["trusted_inventory_canonical_sha256"],
        "transport_capture_sha256": request["transport_capture"]["sha256"],
        "actual_child_captures": {name: {"receipt_path": value["receipt_path"], "receipt_sha256": value["receipt_sha256"]} for name, value in captures.items()},
        "fresh_mixed_replay_receipt_sha256": core.sha(output / "mixed_replay.receipt.json"),
        "selection_sha256": manifest["corrected_reproduction"]["selection_sha256"],
        "selected_pass_sha256": manifest["corrected_reproduction"]["pass_sha256"],
        "corrected_visual_qa_preserved_sha256": manifest["corrected_visual_transfer"]["receipt_sha256"],
        "original_negative_and_failed_evidence_preserved": True, "new_visual_approval_conferred": False,
        "actual_remote_release_identity_and_publication": "root must record separately",
        "programme_complete": False, "new_fit_generator_optimizer_or_inference_by_orchestrator": False,
        "fresh_receipt_is_external_to_sealed_payload": True, "test_only": policy.test_only})
    receipt["output_inventory"] = actual_output
    receipt = core.seal({key: value for key, value in receipt.items() if key != "content_sha256"})
    core.write_new(output / "receipt.json", receipt)
    pins.recheck()
    final_expected = {"files": {**expected_files, "receipt.json": {"sha256": core.sha(output / "receipt.json"),
                      "bytes": (output / "receipt.json").stat().st_size}}, "directories": actual_output["directories"]}
    core.require(core.inventory_tree(output, pins) == final_expected, "fresh replay publication inventory/residue differs")
    return {"status": receipt["status"], "receipt_path": str(output / "receipt.json"),
            "receipt_sha256": core.sha(output / "receipt.json"), "programme_complete": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("transport", "science"), required=True)
    for name in ("preparation-receipt", "request", "output", "python"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("preparation-receipt-sha256", "request-sha256"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    python = core.runtime(args.python)
    pins = core.Pins()
    own = Path(__file__).absolute().parent
    preparation = core.load_preparation(own, args.preparation_receipt_sha256, pins)
    core.require(args.preparation_receipt == own / "preparation_receipt.json", "explicit adapter receipt path differs")
    sources = core.document(own / "source_pins.json", pins, preparation["source_pins_sha256"], field=None)
    request = core.document(args.request, pins, args.request_sha256)
    core.no_overlap(args.output, [own, args.request])
    result = (transport if args.mode == "transport" else science)(request, args.output, python, sources, pins, {})
    pins.recheck()
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
