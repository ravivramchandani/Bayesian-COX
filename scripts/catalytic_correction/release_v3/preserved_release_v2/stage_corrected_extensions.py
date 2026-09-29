"""Stage complete corrected evidence through original safe copy/publication IO.

No rendering, inference, numerical reproduction, fitting or publication occurs.
All declared actual source proofs must exist before the destination is created.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

if __name__ == "__main__":
    _parser = argparse.ArgumentParser(add_help=False)
    _parser.add_argument("--preparation-receipt", type=Path, required=True)
    _parser.add_argument("--preparation-receipt-sha256", required=True)
    _args, _unknown = _parser.parse_known_args()
    if hashlib.sha256(_args.preparation_receipt.read_bytes()).hexdigest() != _args.preparation_receipt_sha256:
        raise RuntimeError("adapter preparation receipt differs")
    _prep = json.loads(_args.preparation_receipt.read_text())
    _own = Path(__file__).absolute().parent
    for _name, _digest in _prep["implementation_source_sha256"].items():
        if Path(_name).name != _name or hashlib.sha256((_own / _name).read_bytes()).hexdigest() != _digest:
            raise RuntimeError("adapter implementation source differs")
    sys.path.insert(0, str(_own))

import release_core as core  # noqa: E402


def validate(request: dict[str, Any], pins: core.Pins, source_pins: dict[str, Any], policy: core.Policy,
             dependencies: dict[str, Any]) -> dict[str, Any]:
    """Structural/byte gates only; actual corrected science was independently run."""
    core.require(request["schema_version"] == 1 and request["status"] == "corrected_release_staging_inputs_bound"
                 and request["test_only"] is False, "bound production staging request required")
    core.require(not dependencies or policy.test_only, "dependency injection is restricted to fictional test policies")
    bindings_path, bindings = core.record(request["verification_bindings"], pins)
    roots = core.validate_assets(request, bindings, pins)
    release_preparation = core.load_preparation(roots["release_adapter_preparation"], request["release_adapter_preparation_sha256"], pins)
    if not policy.test_only:
        core.require(roots["release_adapter_preparation"] == Path(__file__).absolute().parent
                     and release_preparation["implementation_source_sha256"].get(Path(__file__).name) == core.sha(Path(__file__).absolute()),
                     "exact executing release adapter/preparation must be retained")
    core.validate_extra_retention(request, pins)
    core.require(set(request["external_retained_file_bindings"]) == core.EXTERNAL, "explicit receiving external file pins required")
    for name, values in request["external_retained_file_bindings"].items():
        core.require(all(".git" not in Path(relative).parts for relative in values), "Git metadata is historical review text, not scientific transfer bytes")
        core.artifact_map(Path(bindings["roots"][name]), values, pins)
    preparation = core.load_preparation(roots["verification_preparation"], source_pins["mixed_verifier_preparation_sha256"], pins)
    gates = dependencies.get("structural_gates", core.structural_gates)(bindings, roots["verification_preparation"], preparation, pins)
    completion, ids = core.validate_mixed(roots["mixed_verified"], request["mixed_completion_sha256"], pins, policy)
    core.require(gates.summary() == completion["source_bindings"], "mixed certificate uses different current freeze/input/review lineage")
    core.validate_retained(roots, bindings, completion, ids, pins, policy)
    capture_path, _ = core.record(request["source_capture"], pins)
    source_capture = core.capture_record(capture_path, request["source_capture"]["sha256"], pins,
        status="mixed_verification_actual_rc0_captured", summary_status=core.MIXED_STATUS,
        completion_sha=request["mixed_completion_sha256"])
    core.require(capture_path.parent == roots["source_capture"] and source_capture["summary"]["verified_logical_cells"] == policy.cells
                 and source_capture["summary"]["programme_complete"] is False, "actual deep source capture scope differs")
    core.require(roots["source_verification_bindings"] == bindings_path, "actual source verifier binding bytes omitted")
    verifier_script = roots["verification_preparation"] / "verify_mixed_extensions.py"
    source_attempt = core.captured_command(capture_path, source_capture, pins, entrypoint=verifier_script,
        entrypoint_sha=preparation["implementation_source_sha256"][verifier_script.name], original_mixed=True,
        options=["--preparation-receipt", str(roots["verification_preparation"] / "preparation_receipt.json"),
                 "--preparation-receipt-sha256", source_pins["mixed_verifier_preparation_sha256"],
                 "--input-bindings", str(bindings_path), "--input-bindings-sha256", request["verification_bindings"]["sha256"],
                 "--output", str(roots["mixed_verified"])])
    core.validate_mixed_capture_producer(source_attempt, roots["release_adapter_preparation"],
                                        request["release_adapter_preparation_sha256"], release_preparation, pins)
    for name, digest in preparation["implementation_source_sha256"].items():
        core.require(source_attempt["implementation_source_sha256"].get(str(roots["verification_preparation"] / name)) == digest,
                     "actual mixed capture omitted tested implementation bytes")
    expected_capture_inputs = {str(roots["verification_preparation"] / name): digest
                               for name, digest in preparation["implementation_source_sha256"].items()}
    expected_capture_inputs[str(roots["verification_preparation"] / "preparation_receipt.json")] = source_pins["mixed_verifier_preparation_sha256"]
    expected_capture_inputs[str(bindings_path)] = request["verification_bindings"]["sha256"]
    core.require(source_attempt["implementation_source_sha256"] == expected_capture_inputs,
                 "actual mixed capture source/input byte surface differs")
    initial_invocation = core.document(roots["mixed_verified"] / "invocation.json", pins)
    core.require(initial_invocation["operation"] == "mixed_extensions_deep_verification"
                 and initial_invocation["argv"] == source_attempt["argv"][3:]
                 and initial_invocation["input_bindings_sha256"] == request["verification_bindings"]["sha256"]
                 and initial_invocation["preparation_receipt_sha256"] == source_pins["mixed_verifier_preparation_sha256"]
                 and initial_invocation["actual_input_locations"] == bindings
                 and initial_invocation["verify_existing"] is False
                 and initial_invocation["actual_numeric_thread_environment"] == {name: "1" for name in core.NUMERIC},
                 "actual source verifier invocation differs from captured child")
    core.load_preparation(roots["reproduction_preparation"], source_pins["original_reproduction_preparation_sha256"], pins)
    receiving_prep = core.load_preparation(roots["receiving_reproduction_preparation"], request["receiving_reproduction_preparation_sha256"], pins)
    core.require(receiving_prep["status"] == "corrected_reproduction_receiving_adapter_prepared"
                 and receiving_prep["no_fit_or_generator_dispatch"] is True
                 and request["receiving_reproduction_preparation_sha256"] == source_pins["receiving_reproduction_preparation_sha256"],
                 "reviewed receiving-only reproduction adapter required")
    reproduction = core.validate_reproduction(roots, request, bindings, ids, pins, policy)
    for identity in reproduction["selected_cells"]:
        proof = core.document(roots["reproduction"] / "cells" / (identity + ".json"), pins)
        for source, binding in proof["external_artifacts"].items():
            path = core.safe(Path(source))
            pins.bind(path, binding["sha256"], size=binding["bytes"])
            core.require(core.explicit_retention(path, binding["sha256"], request, bindings),
                         "selected numerical producer/source/review/trace bytes omitted from payload/dependencies")
    reproduction_path, _ = core.record(request["reproduction_capture"], pins)
    actual_reproduction = core.capture_record(reproduction_path, request["reproduction_capture"]["sha256"], pins,
        status="corrected_readonly_reproduction_actual_rc0_captured",
        summary_status="corrected_selected_reproduction_restored_read_only_verified")
    summary = actual_reproduction["summary"]
    core.require(reproduction_path.parent == roots["reproduction_capture"]
                 and summary["selection_sha256"] == reproduction["selection_sha256"]
                 and summary["selected_pass_sha256"] == reproduction["pass_sha256"]
                 and summary["route_counts"] == reproduction["route_counts"]
                 and summary["scheduled_selected_cells"] == summary["accounted_selected_cells"] == len(reproduction["selected_cells"])
                 and summary["no_new_numerical_fit"] is True, "actual selected comparison capture is foreign/incomplete")
    reproduction_review = core.document(roots["source_reproduction_review"] / "receipt.json", pins, summary["receipt_sha256"])
    core.require(summary["receipt_path"] == str(roots["source_reproduction_review"] / "receipt.json")
                 and reproduction_review["status"] == "corrected_selected_reproduction_restored_read_only_verified"
                 and reproduction_review["test_only_dependency_injection"] is False,
                 "actual source selected receiving proof absent or synthetic")
    core.declared_output_tree(roots["source_reproduction_review"], reproduction_review, pins)
    repro_script = roots["receiving_reproduction_preparation"] / "verify_restored_reproduction.py"
    repro_request_path, _ = core.record(request["source_reproduction_bindings"], pins)
    core.require(core.explicit_retention(repro_request_path, request["source_reproduction_bindings"]["sha256"], request, bindings),
                 "actual source receiving bindings omitted")
    repro_attempt_path = reproduction_path.with_name(reproduction_path.name.removesuffix(".receipt.json") + ".attempt.json")
    repro_argv = core.document(repro_attempt_path, pins)["argv"]
    core.captured_command(reproduction_path, actual_reproduction, pins, entrypoint=repro_script,
        entrypoint_sha=receiving_prep["implementation_source_sha256"][repro_script.name],
        options=["--bindings", str(repro_request_path), "--bindings-sha256", request["source_reproduction_bindings"]["sha256"],
                 "--output", str(roots["source_reproduction_review"]), "--python", repro_argv[0]])
    support_fields = {"qa_helper", "reporting_helper", "claim_helper", "report_replay"}
    core.require(set(request["support_source_sha256"]) == support_fields
                 and set(request["support_paths"]) == support_fields, "exact corrected support implementations required")
    support_preparation = core.load_preparation(roots["support"], source_pins["reporting_qa_preparation_sha256"], pins)
    for name, digest in request["support_source_sha256"].items():
        path = core.safe(Path(request["support_paths"][name]))
        core.require(path.is_relative_to(roots["support"]), "corrected support source omitted from package")
        core.require(support_preparation["implementation_source_sha256"].get(str(path.relative_to(roots["support"]))) == digest,
                     "actual reporting/QA helper differs from reviewed preparation")
        pins.bind(path, digest)
    qa_roster = dependencies.get("qa_roster", core.frozen_qa_roster)
    names, tables = qa_roster(Path(request["transport_code"]) / "qa_transfer.py", source_pins["transport_sources"]["qa_transfer.py"], pins)
    visual = core.validate_visual(roots, request, request["mixed_completion_sha256"], request["source_capture"]["sha256"],
                                  names, tables, pins, policy)
    expected_reporting = {"mixed_completion_sha256": request["mixed_completion_sha256"],
        "selection_sha256": reproduction["selection_sha256"], "selected_pass_sha256": reproduction["pass_sha256"],
        "visual_qa_receipt_sha256": visual["receipt_sha256"],
        "mixed_correction_lineage_sha256": core.sha(roots["rendered"] / "mixed_correction_lineage.json")}
    reporting = core.validate_reporting(roots, request, expected_reporting, pins, policy)
    support_input_locations = {}
    for role, capture_role, expected_script in (("source_reporting_request", "source_reporting_capture", "report_replay"),
                                                ("source_claim_request", "claim_capture", "claim_helper")):
        request_path, support_request = core.record(request[role], pins)
        core.require(core.explicit_retention(request_path, request[role]["sha256"], request, bindings), "actual reporting/claim request omitted")
        captured_path, captured = core.record(request[capture_role], pins)
        attempt_path = captured_path.with_name(captured_path.name.removesuffix(".receipt.json") + ".attempt.json")
        argv = core.document(attempt_path, pins)["argv"]
        options = ["--request", str(request_path), "--request-sha256", request[role]["sha256"]]
        if expected_script == "report_replay":
            options += ["--output", str(roots["source_reporting_review"])]
        options += ["--python", argv[0]]
        core.captured_command(captured_path, captured, pins, entrypoint=Path(request["support_paths"][expected_script]),
                              entrypoint_sha=request["support_source_sha256"][expected_script], options=options)
        actual_files = {"mixed_completion": roots["mixed_verified"] / "completion.json",
            "source_capture": capture_path, "renderer": Path(bindings["roots"]["analysis"]) / "scripts/render_extensions.py",
            "renderer_adapter": roots["verification_preparation"] / "render_verified_mix.py",
            "selection": roots["reproduction"] / "selection.json",
            "selected_pass": core.child(roots["reproduction"], request["reproduction_pass"]["relative_path"]),
            "correction_manifest": Path(bindings["files"]["manifest"]["path"])}
        core.require(support_request["preparation_receipt"] == {"path": str(roots["support"] / "preparation_receipt.json"),
                     "sha256": source_pins["reporting_qa_preparation_sha256"]}, "source reporting uses foreign helper preparation")
        for name in ("mixed_verified", "reproduction", "rendered", "qa"):
            core.require(support_request["roots"][name] == str(roots[name]), "source reporting references foreign evidence tree")
        for name in ("primary", "sampler", "robustness"):
            core.require(support_request["roots"][name] == bindings["roots"][name], "source reporting uses foreign baseline role")
        for name, path in actual_files.items():
            core.require(support_request["files"][name] == {"path": str(path), "sha256": core.sha(path)},
                         "source reporting file role differs: " + name)
            support_input_locations[name] = support_file_location(path, core.sha(path), request, bindings)
        explanation_path, _ = core.record(support_request["files"]["explanation"], pins)
        explanation_location = support_file_location(explanation_path, support_request["files"]["explanation"]["sha256"], request, bindings)
        core.require("explanation" not in support_input_locations or support_input_locations["explanation"] == explanation_location,
                     "source reporting/claims use different explanation")
        support_input_locations["explanation"] = explanation_location
        actual_correction = core.document(roots["rendered"] / "mixed_correction_lineage.json", pins)
        core.require(actual_correction["original_renderer_sha256"] == core.sha(actual_files["renderer"])
                     and actual_correction["adapter_sha256"] == core.sha(actual_files["renderer_adapter"]),
                     "actual renderer source bytes differ from both lineages")
        if expected_script == "report_replay":
            proof = core.document(roots["source_reporting_review"] / "reporting_replay_receipt.json", pins, captured["summary"]["receipt_sha256"])
            core.require(captured["summary"]["receipt_path"] == str(roots["source_reporting_review"] / "reporting_replay_receipt.json")
                         and proof["source_bindings"] == expected_reporting
                         and proof["test_only"] is False, "actual source reporting proof absent or synthetic")
            core.declared_output_tree(roots["source_reporting_review"], proof, pins, receipt_name="reporting_replay_receipt.json")
    claim_stdout = Path(request["claim_capture"]["path"]).with_name(
        Path(request["claim_capture"]["path"]).name.removesuffix(".receipt.json") + ".stdout.log")
    support_input_locations["claim_stdout"] = support_file_location(claim_stdout, core.sha(claim_stdout), request, bindings)
    for name in ("source_reporting_capture", "claim_capture"):
        core.require(Path(request[name]["path"]).parent == roots[name], "required source reporting capture omitted")
    core.require(set(request["external_baselines"]) == {"primary", "sampler", "robustness"}, "required separately released baseline roles absent")
    for name, item in request["external_baselines"].items():
        root = core.safe(Path(bindings["roots"][name]))
        digest = item["trusted_release_inventory_canonical_sha256"]
        core.require(isinstance(digest, str) and len(digest) == 64 and all(letter in "0123456789abcdef" for letter in digest)
                     and set(item["files"]) == {"manifest.json", "completion.json"},
                     "explicit trusted baseline release/manifest/completion pins required")
        core.artifact_map(root, item["files"], pins)
    for name in ("production", "analysis"):
        root = core.safe(Path(bindings["roots"][name]))
        for relative, digest in core.document(roots["verification_preparation"] / "source_pins.json", pins, preparation["source_pins_sha256"], field=None)["files"][name].items():
            pins.bind(core.child(root, relative), digest)
        tracking_gate = dependencies.get("source_tracking_gate")
        if tracking_gate is None:
            result = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True, check=False)
            core.require(result.returncode == 0, "source archive tracked-file inventory unavailable")
            tracked = {value.decode() for value in result.stdout.split(b"\0") if value}
            core.require(set(request["external_retained_file_bindings"][name]) <= tracked,
                         "retained external source bytes are absent from Git archive; copy them explicitly")
        else:
            tracking_gate(root, request["external_retained_file_bindings"][name])
    source_gate = dependencies.get("source_gate")
    if source_gate is None:
        # This original gate reads frozen source/license bytes only. Extract
        # the exact function; no original stager/scientific CLI is invoked.
        import ast
        transport_source = Path(request["transport_code"]) / "stage_extensions.py"
        pins.bind(transport_source, source_pins["transport_sources"]["stage_extensions.py"])
        nodes = [node for node in ast.parse(transport_source.read_bytes()).body
                 if isinstance(node, ast.FunctionDef) and node.name == "verify_source_inputs"]
        core.require(len(nodes) == 1 and not any(name == "src" or name.startswith("src.") for name in sys.modules),
                     "fresh source-gate project namespace required")
        scope: dict[str, Any] = {"Path": Path}
        sys.path.insert(0, bindings["roots"]["production"])
        try:
            exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), str(transport_source), "exec"), scope)
            source_gate = scope["verify_source_inputs"]
            original_manifest = core.document(roots["original_run"] / "manifest.json", pins, field="manifest_content_sha256")
            source_gate(Path(bindings["roots"]["production"]), original_manifest, roots["matched"], roots["matched_manifest"],
                        roots["metabric_source"], roots["source_report"], analysis=Path(bindings["roots"]["analysis"]))
            for name, module in tuple(sys.modules.items()):
                if name == "src" or name.startswith("src."):
                    core.require(getattr(module, "__file__", None) is not None
                                 and Path(module.__file__).absolute().is_relative_to(Path(bindings["roots"]["production"])),
                                 "source-gate imported foreign project bytes")
        finally:
            sys.path.pop(0)
    else:
        source_gate(roots, bindings, pins)
    pins.recheck()
    return {"roots": roots, "bindings": bindings, "bindings_path": bindings_path, "completion": completion,
            "ids": ids, "gates": gates, "reproduction": reproduction, "visual": visual, "reporting": reporting,
            "support_input_locations": support_input_locations}


def archive_source(root: Path, target: Path, expected: str, api: dict[str, Any]) -> None:
    """Original clean commit check plus git's own archive; no project scripts run."""
    core.require(api["commit"](root) == expected, "archive source clean commit differs")
    with target.open("xb") as stream:
        result = subprocess.run(["git", "archive", "--format=tar.gz", "HEAD"], cwd=root, stdout=stream, stderr=subprocess.PIPE, check=False)
        stream.flush()
        os.fsync(stream.fileno())
    core.require(result.returncode == 0, "git archive failed; attempt bytes retained")
    core.require(api["commit"](root) == expected, "archive source changed during archive")


def mapped_file(source: Path, request: dict[str, Any]) -> str:
    """Resolve only an explicitly inventoried source file, never prefix guessing."""
    matches = []
    for item in request["assets"].values():
        root = Path(item["source"])
        if item["kind"] == "file" and source == root:
            matches.append(item["target"])
        elif item["kind"] in {"tree", "group"} and source.is_relative_to(root):
            relative = str(source.relative_to(root))
            if relative in item["inventory"]["files"]:
                matches.append(str(Path(item["target"]) / relative))
    matches.extend(item["target"] for item in request["retained_files"] if Path(item["source"]) == source)
    core.require(len(matches) == 1, "frozen file has absent/ambiguous explicit payload mapping")
    return matches[0]


def support_file_location(path: Path, digest: str, request: dict[str, Any], bindings: dict[str, Any]) -> dict[str, str]:
    """A file resolves to one shipped entry or one explicit unchanged external role."""
    core.require(core.explicit_retention(path, digest, request, bindings), "reporting input omitted from retained file roles")
    external = [(name, Path(bindings["roots"][name])) for name in core.EXTERNAL if path.is_relative_to(Path(bindings["roots"][name]))]
    if external:
        core.require(len(external) == 1, "ambiguous external reporting input")
        role, root = external[0]
        return {"kind": "external", "role": role, "relative_path": str(path.relative_to(root)), "sha256": digest}
    return {"kind": "payload", "relative_path": mapped_file(path, request), "sha256": digest}


def stage(request_path: Path, request_sha: str, output: Path, source_pins: dict[str, Any], *,
          dependencies: dict[str, Any] | None = None, policy: core.Policy = core.PRODUCTION_POLICY) -> dict[str, Any]:
    """Atomic no-replace stage; failed attempts/residue stay external and intact."""
    dependencies = {} if dependencies is None else dependencies
    pins = core.Pins()
    request = core.document(request_path, pins, request_sha)
    validated = validate(request, pins, source_pins, policy, dependencies)
    roots, bindings = validated["roots"], validated["bindings"]
    immutable = [*roots.values(), *(core.safe(Path(value)) for value in bindings["roots"].values()), request_path]
    core.no_overlap(output, immutable)
    api = dependencies.get("copy_api") or core.transport_api(core.safe(Path(request["transport_code"])), source_pins, pins)
    pending = Path(tempfile.mkdtemp(prefix=".corrected-stage-pending-" + output.name + "-", dir=output.parent))
    # No cleanup on failure: preserve evidence, refuse to certify any partial tree.
    historical_roots = {}
    for name, item in request["assets"].items():
        source, target = core.safe(Path(item["source"])), core.child(pending, item["target"])
        target.parent.mkdir(parents=True, exist_ok=True)
        if item["kind"] == "tree":
            api["copy_tree"](source, target, clone=request["strict_native_clone"])
            core.verify_tree(target, item["inventory"], core.Pins())
        elif item["kind"] == "file":
            api["copy_file"](source, target, clone=request["strict_native_clone"])
            core.Pins().bind(target, item["binding"]["sha256"], size=item["binding"]["bytes"])
        else:
            target.mkdir()
            for relative, binding in item["inventory"]["files"].items():
                destination = core.child(target, relative)
                destination.parent.mkdir(parents=True, exist_ok=True)
                api["copy_file"](core.child(source, relative), destination, clone=request["strict_native_clone"])
                core.Pins().bind(destination, binding["sha256"], size=binding["bytes"])
        historical_roots[name] = {"historical_source": str(source), "payload_relative": item["target"], "kind": item["kind"]}
    retained_locations = []
    for item in request["retained_files"]:
        target = core.child(pending, item["target"])
        target.parent.mkdir(parents=True, exist_ok=True)
        api["copy_file"](Path(item["source"]), target, clone=request["strict_native_clone"])
        core.Pins().bind(target, item["binding"]["sha256"], size=item["binding"]["bytes"])
        retained_locations.append({"historical_source": item["source"], "payload_relative": item["target"], "binding": item["binding"]})
    for name, commit in (("production", "119476fef55b1eeb690527f234c1423440720d45"), ("analysis", "8551d326b02bfe88915cfd9eb50c6ca8e5690e3a")):
        target = pending / "code" / (name + ".tar.gz")
        dependencies.get("archive_source", archive_source)(Path(bindings["roots"][name]), target, commit, api)
    files = {name: {"relative_path": mapped_file(Path(item["path"]), request), "sha256": item["sha256"]}
             for name, item in bindings["files"].items()}
    reviews = {name: {"relative_path": mapped_file(Path(path), request), "sha256": core.sha(Path(path))}
               for name, path in bindings["review_paths"].items()}
    optional_reviews = {name: {"relative_path": mapped_file(Path(bindings[name]["path"]), request), "sha256": bindings[name]["sha256"]}
                        for name in ("resolution_review", "pilot_review") if bindings.get(name) is not None}
    pins.recheck()
    # Original constructor rechecks clear ownership, source/review/freeze law.
    dependencies.get("recheck_gates", lambda state: type(state["gates"])(state["bindings"], pins))(validated)
    for name, item in request["assets"].items():
        if item["kind"] == "tree":
            core.verify_tree(roots[name], item["inventory"], pins)
    payload = core.inventory_tree(pending, core.Pins())
    manifest = core.seal({"schema_version": 1, "status": "corrected_private_payload_staged_with_separate_actual_source_gates",
        "evidence_status": core.EVIDENCE, "source_staging_request_sha256": request_sha,
        "payload_inventory": payload, "historical_roots": historical_roots,
        "retained_external_file_locations": retained_locations,
        "verified_input_file_locations": files, "verified_review_locations": reviews, "optional_review_locations": optional_reviews,
        "external_root_roles": {name: {"historical_source": bindings["roots"][name]} for name in core.EXTERNAL},
        "required_external_baselines": request["external_baselines"], "mixed_completion_sha256": request["mixed_completion_sha256"],
        "external_retained_file_bindings": request["external_retained_file_bindings"],
        "source_verifier_capture_sha256": request["source_capture"]["sha256"],
        "source_verifier_capture_location": mapped_file(Path(request["source_capture"]["path"]), request),
        "source_verification_bindings_sha256": request["verification_bindings"]["sha256"],
        "source_reproduction_capture_sha256": request["reproduction_capture"]["sha256"],
        "corrected_reproduction": validated["reproduction"], "corrected_visual_transfer": validated["visual"],
        "corrected_reporting": validated["reporting"], "support_source_sha256": request["support_source_sha256"],
        "support_input_file_locations": validated["support_input_locations"],
        "support_source_locations": {name: mapped_file(Path(path), request) for name, path in request["support_paths"].items()},
        "receiving_reproduction_preparation_sha256": request["receiving_reproduction_preparation_sha256"],
        "verification_preparation_receipt_sha256": source_pins["mixed_verifier_preparation_sha256"],
        "reporting_qa_preparation_sha256": source_pins["reporting_qa_preparation_sha256"],
        "release_adapter_preparation_sha256": request["release_adapter_preparation_sha256"],
        "selected_numerical_reproduction_is_not_whole_grid": True,
        "transport_tool_sha256": source_pins["transport_sources"],
        "remote_download_restore_or_publication_certified": False, "programme_complete": False,
        "new_scientific_approval_conferred": False, "test_only": policy.test_only})
    core.write_new(pending / "corrected_release_stage.json", manifest)
    pins.recheck()
    api["publish"](pending, output)
    descriptor = os.open(output.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    # A committed manifest followed by any inventory/recheck failure is not rc0.
    actual = core.inventory_tree(output, core.Pins())
    expected_files = {**payload["files"], "corrected_release_stage.json": {"sha256": core.sha(output / "corrected_release_stage.json"),
                                                                         "bytes": (output / "corrected_release_stage.json").stat().st_size}}
    core.require(actual == {"files": expected_files, "directories": payload["directories"]}, "published exact payload inventory differs")
    pins.recheck()
    for name, item in request["assets"].items():
        if item["kind"] == "tree":
            core.verify_tree(roots[name], item["inventory"], pins)
    dependencies.get("recheck_gates", lambda state: type(state["gates"])(state["bindings"], pins))(validated)
    return {"status": manifest["status"], "stage_manifest_sha256": core.sha(output / "corrected_release_stage.json"),
            "selected_cells": len(validated["reproduction"]["selected_cells"]), "programme_complete": False, "test_only": policy.test_only}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("preparation-receipt", "request", "output", "python"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("preparation-receipt-sha256", "request-sha256"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    core.runtime(args.python)
    pins = core.Pins()
    own = Path(__file__).absolute().parent
    preparation = core.load_preparation(own, args.preparation_receipt_sha256, pins)
    core.require(args.preparation_receipt == own / "preparation_receipt.json", "explicit adapter receipt path differs")
    sources = core.document(own / "source_pins.json", pins, preparation["source_pins_sha256"], field=None)
    core.no_overlap(args.output, [own])
    result = stage(args.request, args.request_sha256, args.output, sources)
    pins.recheck()
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
