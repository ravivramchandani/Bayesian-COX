"""Source-bound corrected transfer gates; no scientific implementation imports.

The production CLI fixes all study counts. Tests inject tiny fictional policies
and dependency functions; no synthetic receipt represents actual science.
"""

from __future__ import annotations

import ast
import ctypes
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Any

_IO_SHA = "389c09c0b4f151adf754d20b3c21b2cdd0fa6809bcc4cd78dda470739d2ea3b8"
_IO = Path(__file__).absolute().with_name("verification_io.py")
if hashlib.sha256(_IO.read_bytes()).hexdigest() != _IO_SHA:
    raise RuntimeError("reviewed immutable IO source changed")

from verification_io import (  # noqa: E402
    Pins,
    canonical,
    child,
    require,
    safe,
    seal,
    sha,
    write_bytes_new,
    write_new,
)

EVIDENCE = "post_hoc_rank_conditioned_correction_after_original_failures_known"
MIXED_STATUS = "mixed_original_corrected_grid_deep_verified_and_frozen_analysis_recomputed"
FINAL_REPRO = {"reused_verified_original_numerical_reproduction", "new_corrected_numerical_reproduction",
               "terminal_no_fit_recipe_replay"}
NUMERIC = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS")
ROOTS = {"analysis", "candidate_module", "context_inventory", "contracts", "corrected_run", "correction_addendum",
         "correction_config", "fit_code", "matched", "original_run", "preflight", "preflight_code", "primary",
         "production", "reuse_code", "robustness", "sampler", "witness_root"}
FILES = {"arithmetic_accounting", "definition", "freeze", "inventory", "manifest"}
REVIEWS = {"arithmetic", "freeze", "implementation", "input_witness", "method"}
EXTERNAL = {"production", "analysis", "primary", "sampler", "robustness"}
REPORT_BINDINGS = {"mixed_completion_sha256", "selection_sha256", "selected_pass_sha256",
                   "visual_qa_receipt_sha256", "mixed_correction_lineage_sha256"}
LAYOUT = {
    "candidate_module": "code/correction/candidate/rank_conditioned_candidate.py",
    "context_inventory": "correction/context_inventory", "contracts": "code/correction/fit_contracts/correction_fit_contracts.py",
    "corrected_run": "evidence/corrected_run", "correction_addendum": "correction/protocol_addendum_catalytic_correction.md",
    "correction_config": "correction/catalytic_correction.yaml", "fit_code": "code/correction/fit_runner",
    "matched": "data/matched_metabric.parquet", "original_run": "evidence/original_run",
    "preflight": "correction/preflight", "preflight_code": "code/correction/preflight_runner",
    "reuse_code": "code/correction/reuse_runner", "witness_root": "correction/witness",
    "arithmetic": "correction/arithmetic", "mixed_verified": "evidence/mixed_verified",
    "reproduction": "evidence/corrected_reproduction", "original_reproduction": "evidence/original_reproduction",
    "rendered": "rendered/corrected", "qa": "visual_qa/corrected", "reporting": "reporting/corrected_sidecar",
    "verification_preparation": "code/correction/verification_v2", "reproduction_preparation": "code/correction/reproduction",
    "receiving_reproduction_preparation": "code/correction/receiving_reproduction",
    "release_adapter_preparation": "code/correction/release_adapter",
    "support": "code/correction/reporting_qa_support", "metabric_source": "data/metabric_source",
    "source_capture": "execution/source_verification", "reproduction_capture": "execution/source_reproduction_verification",
    "source_verification_bindings": "execution/source_verification_bindings.json",
    "source_reproduction_review": "execution/source_reproduction_review",
    "source_reporting_review": "reporting/source_replay_review",
    "source_reporting_capture": "reporting/source_replay", "claim_capture": "reporting/final_claims",
    "freeze": "correction/freeze.json", "matched_manifest": "data/matched_metabric_manifest.json",
    "source_report": "data/metabric_source_report.json",
    "review_method": "correction/reviews/method.json", "review_arithmetic": "correction/reviews/arithmetic.json",
    "review_input_witness": "correction/reviews/input_witness.json", "review_implementation": "correction/reviews/implementation.json",
    "review_freeze": "correction/reviews/freeze.json",
    "resolution_review": "correction/reviews/original_resolution.json", "pilot_review": "correction/reviews/pilot.json",
}
ATTESTATION = "I examined every rendered PDF page at full size and the indexed contact sheets."


@dataclass(frozen=True)
class Policy:
    """Fixed real programme policy; smaller policies exist only in injected tests."""

    cells: int = 1625
    contexts: int = 1650
    original_selected: int = 92
    figures: int = 32
    tables: int = 6
    comparisons: int = 123
    test_only: bool = False


PRODUCTION_POLICY = Policy()


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Reject ambiguous duplicate JSON keys rather than accept the last value."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def strict_json(data: bytes) -> Any:
    """Read finite JSON without importing a scientific dependency."""
    def invalid(value: str) -> None:
        raise ValueError("nonfinite JSON " + value)
    return json.loads(data, object_pairs_hook=unique_object, parse_constant=invalid)


def document(path: Path, pins: Pins, expected: str | None = None, *, field: str | None = "content_sha256") -> dict[str, Any]:
    """Read exact regular JSON bytes; legacy unsealed records need explicit None."""
    safe(path)
    before = sha(path)
    pins.bind(path, before if expected is None else expected)
    value = strict_json(path.read_bytes())
    require(isinstance(value, dict), "JSON object required")
    if field is not None:
        require(value.get(field) == canonical({k: v for k, v in value.items() if k != field}), "document content seal differs")
    require(sha(path) == before, "document changed while read")
    return value


def record(binding: dict[str, Any], pins: Pins, *, field: str | None = "content_sha256") -> tuple[Path, dict[str, Any]]:
    """An explicit path and byte digest are mandatory even for sealed JSON."""
    require(set(binding) == {"path", "sha256"}, "file binding needs exactly path/sha256")
    path = safe(Path(binding["path"]))
    return path, document(path, pins, binding["sha256"], field=field)


def exact_rows(rows: Any, key: str, expected: list[str], label: str) -> None:
    require(isinstance(rows, list) and len(set(expected)) == len(expected)
            and all(isinstance(row, dict) for row in rows) and [row[key] for row in rows] == expected,
            label + " missing/extra/duplicate/order differs")


def inventory_tree(root: Path, pins: Pins) -> dict[str, Any]:
    """Full unlinked tree inventory, including empty directories and failed bytes."""
    safe(root)
    require(root.is_dir(), "tree root absent")
    files, directories = {}, []
    for path in sorted(root.rglob("*")):
        safe(path)
        name = str(path.relative_to(root))
        if path.is_dir():
            directories.append(name)
        else:
            require(path.is_file(), "nonregular tree member")
            digest = sha(path)
            pins.bind(path, digest)
            files[name] = {"sha256": digest, "bytes": path.stat().st_size}
    return {"files": files, "directories": directories}


def verify_tree(root: Path, expected: dict[str, Any], pins: Pins) -> None:
    require(set(expected) == {"files", "directories"}, "exact tree inventory required")
    require(inventory_tree(root, pins) == expected, "tree changed/missing/extra/linked member")


def artifact_map(root: Path, values: dict[str, Any], pins: Pins) -> None:
    require(isinstance(values, dict), "artifact map required")
    for name, binding in values.items():
        require(set(binding) == {"sha256", "bytes"} and type(binding["bytes"]) is int and binding["bytes"] >= 0,
                "typed byte binding required")
        pins.bind(child(root, name), binding["sha256"], size=binding["bytes"])


def validate_assets(request: dict[str, Any], bindings: dict[str, Any], pins: Pins) -> dict[str, Any]:
    """Full explicit source inventories; no path search, aliases or silent omissions."""
    optional = {name for name in ("resolution_review", "pilot_review") if bindings.get(name) is not None}
    require(set(request["assets"]) == (set(LAYOUT) - {"resolution_review", "pilot_review"}) | optional,
            "exact required retained role surface absent")
    roots = {}
    targets = []
    for name, item in request["assets"].items():
        require(item["target"] == LAYOUT[name], "fixed logical release layout differs")
        root = safe(Path(item["source"]))
        roots[name] = root
        target = Path(item["target"])
        require(not target.is_absolute() and ".." not in target.parts, "unsafe target")
        targets.append(target)
        if item["kind"] == "tree":
            verify_tree(root, item["inventory"], pins)
        elif item["kind"] == "file":
            require(set(item["binding"]) == {"sha256", "bytes"}, "explicit single-file pin required")
            pins.bind(root, item["binding"]["sha256"], size=item["binding"]["bytes"])
        elif item["kind"] == "group":
            require(root.is_dir() and item["inventory"]["directories"] == [], "capture group must be flat")
            artifact_map(root, item["inventory"]["files"], pins)
        else:
            require(False, "unknown asset copy kind")
    for index, target in enumerate(targets):
        require(all(not target.is_relative_to(other) and not other.is_relative_to(target)
                    for other in targets[:index]), "overlapping logical assets")
    require(set(bindings["roots"]) == ROOTS and set(bindings["files"]) == FILES
            and set(bindings["review_paths"]) == REVIEWS, "mixed verification binding roles differ")
    for name in ROOTS - EXTERNAL:
        require(roots[name] == Path(bindings["roots"][name]), "copy root differs from verified role")
    require(roots["arithmetic"] == Path(bindings["files"]["arithmetic_accounting"]["path"]).parent,
            "complete arithmetic producer directory required")
    for _role, binding in bindings["files"].items():
        path, _ = record(binding, pins)
        require(any(path == root or path.is_relative_to(root) for name, root in roots.items()
                    if request["assets"][name]["kind"] != "group"), "frozen file is omitted from retained payload")
    for value in [*bindings["review_paths"].values(), *(bindings.get(name, {}).get("path") for name in ("resolution_review", "pilot_review"))]:
        if value is not None:
            path = safe(Path(value))
            require(any((request["assets"][name]["kind"] == "tree" and path.is_relative_to(root))
                        or (request["assets"][name]["kind"] == "file" and path == root) for name, root in roots.items()),
                    "actual review omitted from retained payload")
    return roots


def explicit_retention(path: Path, digest: str, request: dict[str, Any], bindings: dict[str, Any]) -> bool:
    """A source file is shipped by an exact manifest entry or trusted external role.

    Aliases are caller-supplied identities, not a content-deduplication search.
    Git source trees and separately released baselines are independently pinned
    by the scientific certificate and receiving replay.
    """
    for item in request["assets"].values():
        root = Path(item["source"])
        if item["kind"] == "file" and path == root:
            return item["binding"]["sha256"] == digest
        if item["kind"] in {"tree", "group"} and path.is_relative_to(root):
            row = item["inventory"]["files"].get(str(path.relative_to(root)))
            if row is not None:
                return row["sha256"] == digest
    for item in request["retained_files"]:
        if Path(item["source"]) == path:
            return item["binding"]["sha256"] == digest
    for role in EXTERNAL:
        root = Path(bindings["roots"][role])
        if path.is_relative_to(root):
            row = request["external_retained_file_bindings"][role].get(str(path.relative_to(root)))
            return row is not None and row["sha256"] == digest
    return False


def validate_extra_retention(request: dict[str, Any], pins: Pins) -> None:
    """No unreviewed target overlap or alias with changed bytes is permitted."""
    require(not request.get("historical_file_aliases"),
            "sealed receiving v1 refuses file aliases; retain distinct explicit files")
    destinations: dict[str, dict[str, Any]] = {}
    for item in request["assets"].values():
        if item["kind"] == "file":
            destinations[item["target"]] = item["binding"]
        else:
            for name, binding in item["inventory"]["files"].items():
                destinations[str(Path(item["target"]) / name)] = binding
    source_files = set()
    for item in request["retained_files"]:
        source = safe(Path(item["source"]))
        target = Path(item["target"])
        require(not target.is_absolute() and ".." not in target.parts and target.is_relative_to("execution/retained_external")
                and str(target) not in destinations and source not in source_files, "extra retention target/source conflicts")
        for previous in destinations:
            old = Path(previous)
            require(not target.is_relative_to(old) and not old.is_relative_to(target), "extra retention parent conflicts")
        binding = item["binding"]
        pins.bind(source, binding["sha256"], size=binding["bytes"])
        destinations[str(target)] = binding
        source_files.add(source)


def load_preparation(root: Path, expected: str, pins: Pins, *, expected_status: str | None = None) -> dict[str, Any]:
    value = document(root / "preparation_receipt.json", pins, expected)
    if expected_status is not None:
        require(value["status"] == expected_status, "preparation status differs")
    artifact_map(root, value["artifacts"], pins)
    for name, digest in value["implementation_source_sha256"].items():
        pins.bind(child(root, name), digest)
    return value


def load_module(path: Path, digest: str, name: str, pins: Pins) -> Any:
    """Only already byte-pinned stdlib source adapters are imported by staging."""
    pins.bind(path, digest)
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None and name not in sys.modules, "unsafe occupied adapter namespace")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
        return module
    except BaseException:
        sys.modules.pop(name, None)
        raise


def structural_gates(bindings: dict[str, Any], root: Path, preparation: dict[str, Any], pins: Pins) -> Any:
    module = load_module(root / "verification_gates.py", preparation["implementation_source_sha256"]["verification_gates.py"],
                         "_corrected_stage_frozen_gates", pins)
    return module.Gates(bindings, pins)


def capture_record(path: Path, expected: str, pins: Pins, *, status: str, summary_status: str | None,
                   completion_sha: str | None = None) -> dict[str, Any]:
    """Verify actual captured exit/log/attempt bytes; never reconstruct an rc proof."""
    value = document(path, pins, expected)
    require(value["status"] == status and type(value["exit_code"]) is int and value["exit_code"] == 0,
            "genuine completed process capture absent")
    require(path.name.endswith(".receipt.json"), "capture prefix receipt required")
    prefix = path.name.removesuffix(".receipt.json")
    expected_names = {prefix + suffix for suffix in (".stdout.log", ".stderr.log", ".attempt.json", ".receipt.json")}
    require({p.name for p in path.parent.glob(prefix + ".*")} == expected_names
            and not any(path.parent.glob(".verification-pending-" + prefix + ".*")), "capture residue/collision/missing member")
    artifact_map(path.parent, value["artifacts"], pins)
    attempt = document(path.with_name(prefix + ".attempt.json"), pins, value["invocation_attempt_sha256"])
    require(type(attempt["exit_code"]) is int and attempt["exit_code"] == 0 and attempt["launch_error"] is None,
            "actual invocation failed or return code untyped")
    for kind in ("stdout", "stderr"):
        actual = path.with_name(prefix + "." + kind + ".log")
        require(value[kind + "_sha256"] == attempt[kind + "_sha256"] == sha(actual)
                and Path(value[kind + "_path"]).name == actual.name
                and Path(attempt[kind + "_path"]).name == actual.name, "raw capture binding differs")
    lines = path.with_name(prefix + ".stdout.log").read_bytes().splitlines()
    require(bool(lines), "successful process emitted no factual summary")
    summary = strict_json(lines[-1])
    require(summary == value["summary"] and (summary_status is None or summary["status"] == summary_status), "captured summary differs")
    if completion_sha is not None:
        require(value["completion_sha256"] == completion_sha, "capture completion bytes differ")
    return value


def captured_command(path: Path, value: dict[str, Any], pins: Pins, *, entrypoint: Path,
                     entrypoint_sha: str, options: list[str], original_mixed: bool = False) -> dict[str, Any]:
    """Bind historical actual rc0 to the exact pinned child and ordered arguments.

    Historical interpreter text is preserved; the independent scientific reader
    binds its recorded runtime/environment. This function never invents an rc.
    """
    prefix = path.name.removesuffix(".receipt.json")
    attempt = document(path.with_name(prefix + ".attempt.json"), pins, value["invocation_attempt_sha256"])
    argv = attempt["argv"]
    require(isinstance(argv, list) and len(argv) >= 4 and all(isinstance(item, str) for item in argv)
            and Path(argv[0]).is_absolute() and ".." not in Path(argv[0]).parts
            and argv[1:] == ["-I", "-B", str(entrypoint), *options],
            "actual captured child entrypoint/arguments differ")
    pins.bind(entrypoint, entrypoint_sha)
    if original_mixed:
        require(attempt["operation"] == "actual_mixed_verifier_child_capture"
                and attempt["implementation_source_sha256"].get(str(entrypoint)) == entrypoint_sha,
                "actual original mixed capture source provenance differs")
    else:
        require(attempt["operation"] == "actual_corrected_transfer_child_capture"
                and attempt["entrypoint"] == {"historical_path": str(entrypoint), "sha256": entrypoint_sha}
                and attempt["numeric_thread_environment"] == {name: "1" for name in NUMERIC}
                and attempt["test_only_dependency_injection"] is False,
                "actual read-only capture source/runtime provenance differs")
    return attempt


def declared_output_tree(root: Path, receipt: dict[str, Any], pins: Pins, *, receipt_name: str = "receipt.json") -> dict[str, Any]:
    """Exact new evidence files, including child diagnostics; never repair residue."""
    artifacts = receipt["artifacts"]
    artifact_map(root, artifacts, pins)
    actual = inventory_tree(root, pins)
    expected = {**artifacts, receipt_name: {"sha256": sha(root / receipt_name), "bytes": (root / receipt_name).stat().st_size}}
    require(actual["files"] == expected
            and not any(Path(name).name.startswith(".verification-pending-") or Path(name).name.endswith(".claim.json")
                        for name in actual["files"]), "fresh evidence output missing/extra/partial/owned")
    return actual


def validate_mixed(root: Path, digest: str, pins: Pins, policy: Policy) -> tuple[dict[str, Any], list[str]]:
    completion = document(root / "completion.json", pins, digest)
    require(completion["status"] == MIXED_STATUS and completion["evidence_status"] == EVIDENCE
            and completion["planned_logical_cells"] == completion["verified_logical_cells"] == policy.cells
            and completion["programme_complete"] is False and completion["original855_certificate_inherited"] is False
            and completion["stored_diagnostics_recomputed_and_complete_forecasts_rescored"] is True
            and completion["original_and_primary_negative_findings_preserved"] is True, "complete own mixed deep record absent")
    manifest = document(root / "manifest.json", pins, completion["manifest_sha256"])
    ids = [row["cell_id"] for row in manifest["plan"]]
    require(len(ids) == len(set(ids)) == policy.cells, "mixed exact planned grid differs")
    require(set(completion["cell_sha256"]) == {f"cells/{identity}.json" for identity in ids}
            and set(completion["lineage_sha256"]) == {f"lineage/{identity}.json" for identity in ids}, "mixed cell/lineage scope differs")
    require(set(completion["aggregate_sha256"]) == {"aggregates/" + name for name in
            ("paired_families.json", "rq2_effects.json", "decision_curves.json")}, "frozen reducers absent")
    original_checks = {f"checks/original/{identity}.json" for identity in ids}
    require(original_checks <= set(completion["check_sha256"]), "original failures/deep checks omitted")
    require(all(name in original_checks or (name.startswith("checks/corrected/") and Path(name).stem in ids)
                for name in completion["check_sha256"]), "unplanned deep check")
    for field in ("cell_sha256", "lineage_sha256", "aggregate_sha256", "check_sha256", "initial_invocation_metadata_sha256"):
        for name, digest in completion[field].items():
            pins.bind(child(root, name), digest)
    for name, field in (("reference_verification.json", "reference_verification_sha256"),
                        ("comparison_accounting.json", "comparison_accounting_sha256"), ("render_input.json", "render_input_sha256")):
        pins.bind(root / name, completion[field])
    return completion, ids


def validate_retained(roots: dict[str, Path], bindings: dict[str, Any], completion: dict[str, Any], ids: list[str],
                      pins: Pins, policy: Policy) -> None:
    """Bind every original/new input/outcome/failed trace already deep-verified."""
    inventory = document(Path(bindings["files"]["inventory"]["path"]), pins, bindings["files"]["inventory"]["sha256"])
    exact_rows(inventory["entries"], "original_cell_id", ids, "whole correction inventory")
    pf = document(roots["preflight"] / "completion.json", pins)
    replay = document(roots["witness_root"] / "replay/completion.json", pins, inventory["replay_completion_sha256"])
    require(pf["status"] == "all_scheduled_contexts_accounted" and pf["scheduled_contexts"] == pf["accounted_contexts"] == policy.contexts
            and replay["status"] == "all1650_independent_first_draw_contexts_accounted"
            and replay["scheduled_contexts"] == replay["accounted_contexts"] == policy.contexts, "whole context/firstdraw accounting absent")
    contexts = [row["context_id"] for row in pf["outcomes"]]
    require(len(contexts) == len(set(contexts)) == policy.contexts, "preflight exact context scope differs")
    exact_rows(replay["outcomes"], "context_id", contexts, "independent context replay")
    for namespace, rows in ((roots["preflight"], pf["outcomes"]), (roots["witness_root"], replay["outcomes"])):
        for row in rows:
            path = child(namespace, row["receipt_path"])
            receipt = document(path, pins, row["receipt_sha256"])
            artifact_map(path.parent, receipt["artifacts"], pins)
    for entry in inventory["entries"]:
        path = child(roots["witness_root"], entry["input_witness_path"])
        witness = document(path, pins, entry["input_witness_sha256"])
        artifact_map(path.parent, witness["proof_artifacts"], pins)
        artifact_map(path.parent, witness["artifacts"], pins)
        snapshot = document(child(roots["witness_root"], entry["snapshot_path"]), pins, entry["snapshot_sha256"])
        artifact_map(path.parent, snapshot["artifacts"], pins)
    for root in (roots["original_run"], roots["corrected_run"]):
        require({p.stem for p in (root / "cells").glob("*.json")} == set(ids), "full raw original/corrected envelope grid absent")
        require((root / "claims").is_dir() and not any((root / "claims").iterdir()), "active original/corrected fit owner")
    require(not (roots["corrected_run"] / "controller.claim.json").exists(), "corrected controller active")
    for identity in ids:
        lineage = document(roots["mixed_verified"] / "lineage" / f"{identity}.json", pins,
                           completion["lineage_sha256"][f"lineage/{identity}.json"])
        raw = lineage["raw_bindings"]
        old = document(roots["original_run"] / "cells" / f"{identity}.json", pins, raw["original_cell_sha256"], field="cell_content_sha256")
        envelope = document(roots["corrected_run"] / "cells" / f"{identity}.json", pins, raw["corrected_envelope_sha256"])
        require(envelope["original_cell_id"] == lineage["original_cell_id"] == identity
                and envelope["operation"] == lineage["operation"] and lineage["original_record_preserved"] is True,
                "raw correction/analysis lineage mismatch")
        original = lineage["input_verification"]["original_source_evidence"]
        require(original["cell_byte_sha256"] == raw["original_cell_sha256"], "original source evidence mismatch")
        for field in ("referenced_trace_sha256", "unreferenced_trace_sha256"):
            for name, digest in original[field].items():
                pins.bind(child(roots["original_run"], name), digest)
        for attempt in old.get("fit_attempts", []):
            for trace in attempt.get("traces", {}).values():
                require(Path(trace["filename"]).name == trace["filename"], "unsafe trace basename")
                pins.bind(roots["original_run"] / "traces" / identity / trace["filename"], trace["sha256"])
        artifact_map(roots["corrected_run"], envelope["artifacts"], pins)
        if envelope["operation"] == "fit_corrected_inputs":
            reference = envelope["corrected_cell"]
            require(reference["sha256"] == raw["corrected_raw_cell_sha256"], "corrected raw cell binding differs")
            cell = document(child(roots["corrected_run"], reference["path"]), pins, reference["sha256"], field="cell_content_sha256")
            attempt_root = roots["corrected_run"] / "attempts" / identity
            for attempt in cell.get("fit_attempts", []):
                for trace in attempt.get("traces", {}).values():
                    require(Path(trace["filename"]).name == trace["filename"], "unsafe corrected trace basename")
                    pins.bind(attempt_root / "traces" / identity / trace["filename"], trace["sha256"])
        else:
            require(envelope["operation"] in {"reuse_original_outcome", "retain_corrected_input_failure"}, "unknown outcome operation")
    arithmetic = document(Path(bindings["files"]["arithmetic_accounting"]["path"]), pins,
                          bindings["files"]["arithmetic_accounting"]["sha256"])
    artifact_map(roots["arithmetic"], arithmetic["artifacts"], pins)


def frozen_qa_roster(path: Path, digest: str, pins: Pins) -> tuple[list[str], list[tuple[str, list[str]]]]:
    """Reuse original fixed names/table sources; never invoke QA or a renderer."""
    pins.bind(path, digest)
    tree = ast.parse(path.read_bytes())
    names = {"COHORT_SETTINGS", "FAMILIES", "TABLE_SOURCES"}
    values = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id in names:
            values[node.targets[0].id] = ast.literal_eval(node.value)
    require(set(values) == names, "fixed roster definitions changed")
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "expected_names"]
    require(len(functions) == 1, "fixed roster function absent")
    scope = dict(values)
    exec(compile(ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[])), str(path), "exec"), scope)
    return scope["expected_names"](), list(values["TABLE_SOURCES"])


def validate_visual(roots: dict[str, Path], request: dict[str, Any], completion_sha: str, source_capture_sha: str,
                    names: list[str], tables: list[tuple[str, list[str]]], pins: Pins, policy: Policy) -> dict[str, Any]:
    """Correction-aware source binding with unchanged actual visual obligations."""
    rendered, qa = roots["rendered"], roots["qa"]
    lineage = document(rendered / "lineage.json", pins, field=None)
    correction = document(rendered / "mixed_correction_lineage.json", pins)
    require(correction["evidence_status"] == EVIDENCE and correction["mixed_completion_sha256"] == completion_sha
            and correction["actual_verifier_capture_sha256"] == source_capture_sha
            and correction["original_renderer_lineage_sha256"] == sha(rendered / "lineage.json")
            and correction["actual_visual_review"] == "pending; rendering is not QA", "corrected renderer lineage/capture absent")
    inventory = document(qa / "qa_inventory.json", pins)
    review = document(qa / "review.json", pins)
    receipt = document(qa / "visual_qa_receipt.json", pins)
    required = {"mixed_completion_sha256": completion_sha, "original_renderer_lineage_sha256": sha(rendered / "lineage.json"),
                "mixed_correction_lineage_sha256": sha(rendered / "mixed_correction_lineage.json"),
                "renderer_sha256": correction["original_renderer_sha256"], "renderer_adapter_sha256": correction["adapter_sha256"],
                "actual_verifier_capture_sha256": source_capture_sha, "qa_helper_sha256": request["support_source_sha256"]["qa_helper"]}
    require(inventory["source_bindings"] == receipt["source_bindings"] == required
            and inventory["status"] == "corrected_automated_checks_passed_visual_review_pending"
            and receipt["visual_qa_status"] == "passed" and receipt["test_only"] is False
            and receipt["inventory_sha256"] == review["inventory_sha256"] == sha(qa / "qa_inventory.json")
            and receipt["review_sha256"] == sha(qa / "review.json"), "actual corrected production QA binding absent")
    require(receipt["reviewer_name"] == review["reviewer_name"].strip() != ""
            and receipt["attestation"] == review["attestation"] == ATTESTATION
            and receipt["reviewer_role"] == review["reviewer_role"] == "root", "named actual root visual attestation absent")
    timestamp = datetime.fromisoformat(review["reviewed_at_utc"].replace("Z", "+00:00"))
    require(timestamp.tzinfo is not None and timestamp.utcoffset() is not None
            and receipt["reviewed_at_utc"] == timestamp.isoformat(), "visual timestamp missing/unbound")
    require(len(names) == policy.figures and len(tables) == policy.tables, "frozen visual roster differs")
    exact_rows(lineage["figures"], "name", names, "renderer figures")
    exact_rows(inventory["figures"], "name", names, "QA figures")
    exact_rows(review["figures"], "name", names, "actual figure verdicts")
    require(receipt["figures"] == review["figures"] and all(row["verdict"] == "pass" for row in review["figures"])
            and receipt["figure_count"] == inventory["figure_count"] == policy.figures, "all actual visual pass verdicts required")
    pages = []
    for index, (figure, check) in enumerate(zip(lineage["figures"], inventory["figures"], strict=True), 1):
        require(check["source_files"] == figure["source_files"] and bool(figure["source_files"])
                and figure["visual_review"] == "pending", "source figure files/visual history changed")
        for extension in ("pdf", "png"):
            path = rendered / (figure["name"] + "." + extension)
            require(check[extension + "_sha256"] == figure[extension + "_sha256"], "QA figure digest differs")
            pins.bind(path, figure[extension + "_sha256"])
        relative = f"page_renders/{index:02d}_{figure['name']}.png"
        require(check["page_render"] == relative, "actual page proof absent")
        pins.bind(child(qa, relative), check["page_render_sha256"])
        pages.append(Path(relative).name)
    require({p.name for p in (qa / "page_renders").iterdir()} == set(pages), "page review inventory differs")
    for extension in ("pdf", "png"):
        require({p.stem for p in rendered.glob("*." + extension)} == set(names), "figure file inventory differs")
    table_names = [name for name, _ in tables]
    exact_rows(lineage["tables"], "name", table_names, "rendered tables")
    exact_rows(inventory["tables"], "name", table_names, "QA tables")
    require(inventory["tables"] == lineage["tables"] and receipt["table_count"] == inventory["table_count"] == policy.tables
            and receipt["tables"] == [{"name": row["name"], "csv_sha256": row["csv_sha256"]} for row in inventory["tables"]],
            "reviewed table lineage/count differs")
    for row, (_, sources) in zip(inventory["tables"], tables, strict=True):
        require(row["source_files"] == sources, "frozen table sources differ")
        pins.bind(rendered / (row["name"] + ".csv"), row["csv_sha256"])
    require({p.stem for p in rendered.glob("*.csv")} == set(table_names), "table file inventory differs")
    sheets = [f"contact_sheets/sheet_{index:02d}.png" for index in range(1, 5)]
    exact_rows(inventory["contact_sheets"], "file", sheets, "indexed contact sheets")
    for row in inventory["contact_sheets"]:
        pins.bind(child(qa, row["file"]), row["sha256"])
    require({p.name for p in (qa / "contact_sheets").iterdir()} == {Path(name).name for name in sheets}, "contact sheet inventory differs")
    return {"receipt_sha256": sha(qa / "visual_qa_receipt.json"), "both_render_lineages_bound": True,
            "actual_visual_review_preserved": True, "new_visual_approval_conferred": False}


def validate_reproduction(roots: dict[str, Path], request: dict[str, Any], bindings: dict[str, Any], ids: list[str],
                          pins: Pins, policy: Policy) -> dict[str, Any]:
    selection = document(roots["reproduction"] / "selection.json", pins, request["selection_sha256"])
    manifest = document(Path(bindings["files"]["manifest"]["path"]), pins, bindings["files"]["manifest"]["sha256"])
    original = sorted(identity for identity in ids if "__r01f01__" in identity)
    require(len(original) == policy.original_selected and selection["original_selected_cells"] == original
            and selection["pilot_cells"] == manifest["pilot_cells"]
            and selection["selected_cells"] == sorted(set(original) | set(manifest["pilot_cells"]))
            and selection["status"] == "reviewed_corrected_reproduction_selection"
            and selection["correction_freeze_sha256"] == bindings["files"]["freeze"]["sha256"]
            and selection["corrected_manifest_sha256"] == bindings["files"]["manifest"]["sha256"]
            and selection["input_inventory_sha256"] == bindings["files"]["inventory"]["sha256"], "exact prospectively frozen reproduction union absent")
    pass_path = child(roots["reproduction"], request["reproduction_pass"]["relative_path"])
    require(pass_path.parent == roots["reproduction"] / "passes", "explicit selected pass path required")
    receipt = document(pass_path, pins, request["reproduction_pass"]["sha256"])
    selected = selection["selected_cells"]
    require(receipt["status"] == "all_selected_reproduction_outcomes_accounted"
            and receipt["selection_sha256"] == request["selection_sha256"]
            and receipt["scheduled_selected_cells"] == receipt["accounted_selected_cells"] == len(selected)
            and receipt["whole_1625_grid_numerically_reproduced"] is False, "actual completed selected reproduction absent")
    exact_rows(receipt["outcomes"], "original_cell_id", selected, "selected reproduction")
    require({p.stem for p in (roots["reproduction"] / "cells").glob("*.json")} == set(selected), "reproduction record scope differs")
    require(not (roots["reproduction"] / "controller.claim.json").exists()
            and not any((roots["reproduction"] / "claims").iterdir()), "selected reproduction still owned")
    counts = dict.fromkeys(sorted(FINAL_REPRO), 0)
    for row in receipt["outcomes"]:
        require(row["status"] in FINAL_REPRO, "pending or failed reproduction cannot complete handoff")
        value = document(roots["reproduction"] / "cells" / (row["original_cell_id"] + ".json"), pins, row["record_sha256"])
        require(value["status"] == row["status"] and value["selection_sha256"] == request["selection_sha256"], "reproduction record/pass mismatch")
        artifact_map(roots["reproduction"], value["artifacts"], pins)
        counts[row["status"]] += 1
    return {"selection_sha256": request["selection_sha256"], "pass_sha256": sha(pass_path),
            "selected_cells": selected, "route_counts": counts, "whole_grid_numerically_reproduced": False}


def validate_reporting(roots: dict[str, Path], request: dict[str, Any], expected: dict[str, str], pins: Pins,
                       policy: Policy) -> dict[str, Any]:
    """Require actual corrected five-file facts and source replay, not old gates."""
    root = roots["reporting"]
    require({p.name for p in root.iterdir()} == {"dimension_ratios.csv", "descriptive_catalytic_pairs.csv", "report.json", "lineage.json", "receipt.json"},
            "exact corrected reporting sidecar absent")
    receipt = document(root / "receipt.json", pins)
    require(receipt["status"] == "corrected_reporting_sidecar_generated"
            and receipt["source_bindings"] == expected and receipt["scientific_completion_certified"] is False,
            "actual source-bound corrected sidecar absent")
    artifact_map(root, receipt["artifacts"], pins)
    require(set(receipt["artifacts"]) == {"dimension_ratios.csv", "descriptive_catalytic_pairs.csv", "report.json", "lineage.json"},
            "reporting artifact inventory differs")
    report = document(root / "report.json", pins, field=None)
    require(len(report["dimension_ratios"]) == policy.cells and len({row["cell_id"] for row in report["dimension_ratios"]}) == policy.cells
            and len(report["descriptive_catalytic_pairs"]) == policy.comparisons, "frozen reporting row roster missing")
    require(receipt["helper_sha256"] == request["support_source_sha256"]["reporting_helper"], "corrected reporter implementation differs")
    replay_path, replay = record(request["source_reporting_capture"], pins)
    capture_record(replay_path, request["source_reporting_capture"]["sha256"], pins,
                   status="corrected_reporting_replay_actual_rc0_captured", summary_status="corrected_reporting_source_replay_verified")
    require(replay["summary"]["source_bindings"] == expected
            and replay["summary"]["sidecar_receipt_sha256"] == sha(root / "receipt.json")
            and replay["summary"]["deterministic_bytes_reproduced_exactly"] is True, "actual source report replay missing")
    claim_path, claim = record(request["claim_capture"], pins)
    capture_record(claim_path, request["claim_capture"]["sha256"], pins,
                   status="corrected_claim_review_actual_rc0_captured", summary_status="corrected_factual_claim_inputs_verified")
    require(claim["summary"]["source_bindings"] == expected
            and claim["summary"]["original_primary_negative_findings_preserved"] is True
            and claim["summary"]["new_inferential_promotion"] is False, "actual corrected factual closeout missing")
    return {"sidecar_receipt_sha256": sha(root / "receipt.json"), "source_replay_capture_sha256": sha(replay_path),
            "claim_capture_sha256": sha(claim_path)}


def transport_api(root: Path, source_pins: dict[str, Any], pins: Pins) -> dict[str, Any]:
    """Reuse original no-replace publisher/copy definitions, not archive machinery."""
    for name, digest in source_pins["transport_sources"].items():
        pins.bind(root / name, digest)
    common = load_module(root / "archive_common.py", source_pins["transport_sources"]["archive_common.py"],
                         "_corrected_release_original_archive_common", pins)
    tree = ast.parse((root / "stage_extensions.py").read_bytes())
    names = {"copy_file", "copy_tree", "commit"}
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    require({node.name for node in nodes} == names, "original safe copy definitions absent")
    scope = {"Path": Path, "sys": sys, "ctypes": ctypes, "os": os, "shutil": shutil,
             "subprocess": subprocess, "partial": partial}
    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[future, *nodes], type_ignores=[])), str(root / "stage_extensions.py"), "exec"), scope)
    return {**{name: scope[name] for name in names}, "publish": common.atomic_new_directory}


def no_overlap(destination: Path, immutable: list[Path]) -> None:
    safe(destination)
    require(destination.parent.is_dir() and not destination.exists()
            and all(not destination.is_relative_to(root) and not root.is_relative_to(destination) for root in immutable),
            "new output overlaps immutable evidence/source or already exists")


def runtime(python: Path) -> Path:
    """Real children use this same frozen interpreter and five single-thread vars."""
    supplied = python.absolute()
    require(supplied.is_file() and ".." not in supplied.parts and os.path.samefile(supplied, sys.executable), "samefile locked interpreter required")
    actual = safe(supplied.resolve(strict=True))
    require(all(os.environ.get(name) == "1" for name in NUMERIC), "all five numeric thread variables must equal one")
    return actual


def capture_process(argv: list[str], prefix: Path, pins: Pins, *, status: str,
                    validate_summary: Any, entrypoint: Path, entrypoint_sha: str,
                    invoke: Any = subprocess.run) -> dict[str, Any]:
    """Capture an actual return code; injected synthetic calls are explicitly tests.

    A failed command, malformed final summary, source change, publication residue
    or cleanup failure leaves diagnostic bytes and no reported CLI success.
    """
    safe(prefix)
    require(prefix.parent.is_dir() and not prefix.exists() and not any(prefix.parent.glob(prefix.name + ".*")),
            "exclusive capture prefix required")
    pins.bind(entrypoint, entrypoint_sha)
    started, tick = datetime.now(UTC).isoformat(), time.monotonic()
    rc, error, stdout, stderr = None, None, b"", b""
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    for name in NUMERIC:
        environment[name] = "1"
    try:
        result = invoke(argv, capture_output=True, check=False, env=environment)
        rc, stdout, stderr = result.returncode, result.stdout, result.stderr
    except BaseException as caught:
        error = {"type": f"{type(caught).__module__}.{type(caught).__qualname__}", "message": str(caught)}
    require(isinstance(stdout, bytes) and isinstance(stderr, bytes), "raw child bytes required")
    paths = {kind: prefix.with_name(prefix.name + suffix) for kind, suffix in
             (("stdout", ".stdout.log"), ("stderr", ".stderr.log"), ("attempt", ".attempt.json"), ("receipt", ".receipt.json"))}
    write_bytes_new(paths["stdout"], stdout)
    write_bytes_new(paths["stderr"], stderr)
    attempt = seal({"operation": "actual_corrected_transfer_child_capture", "argv": argv,
        "entrypoint": {"historical_path": str(entrypoint), "sha256": entrypoint_sha},
        "exit_code": rc, "launch_error": error, "started_at_utc": started, "finished_at_utc": datetime.now(UTC).isoformat(),
        "wall_seconds": time.monotonic() - tick, "numeric_thread_environment": {name: environment[name] for name in NUMERIC},
        "stdout_path": str(paths["stdout"]), "stderr_path": str(paths["stderr"]),
        "stdout_sha256": sha(paths["stdout"]), "stderr_sha256": sha(paths["stderr"]),
        "no_success_inferred_from_self_written_receipts": True, "test_only_dependency_injection": invoke is not subprocess.run})
    write_new(paths["attempt"], attempt)
    require(type(rc) is int and rc == 0 and error is None, "child failed; exact actual logs/rc retained")
    lines = stdout.splitlines()
    require(bool(lines), "actual child final summary absent")
    summary = strict_json(lines[-1])
    validate_summary(summary)
    pins.recheck()
    receipt = seal({"schema_version": 1, "status": status, "exit_code": rc,
        "summary": summary, "stdout_path": str(paths["stdout"]), "stderr_path": str(paths["stderr"]),
        "stdout_sha256": sha(paths["stdout"]), "stderr_sha256": sha(paths["stderr"]),
        "invocation_attempt_sha256": sha(paths["attempt"]),
        "test_only_dependency_injection": invoke is not subprocess.run,
        "artifacts": {path.name: {"sha256": sha(path), "bytes": path.stat().st_size}
                      for kind, path in paths.items() if kind != "receipt"},
        "programme_complete": False, "scientific_method_or_visual_approval_conferred": False})
    write_new(paths["receipt"], receipt)
    require({path.name for path in prefix.parent.glob(prefix.name + ".*")} == {path.name for path in paths.values()}
            and not any(prefix.parent.glob(".verification-pending-" + prefix.name + ".*")), "capture residual/missing files")
    pins.recheck()
    return {**receipt, "receipt_path": str(paths["receipt"]), "receipt_sha256": sha(paths["receipt"])}
