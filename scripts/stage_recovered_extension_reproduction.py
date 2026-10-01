"""Stage 89 intact selected refits for a fully recovered extension source.

This adapter never fits a model or issues a reproduction receipt. Three selected
refits whose original traces are missing remain pending independent execution.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import uuid
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import assemble_recovered_extension as assembly
from scripts import recover_extension_run as recovery
from scripts.extension_release import recovery_lineage as lineage
from scripts.reproduce_extensions import compare_traces, scientific_content
from src.pipelines.extensions.runner import verified_cell
from src.pipelines.extensions.verification import assert_scientific_equal

PLANNED = 1625
SELECTED = 92
REUSED = 89
TRACES = 74
AFFECTED = frozenset({
    "metabric_matched__expression__r01f01__bayesian_horseshoe__full",
    "metabric_matched__expression__r01f01__bayesian_spike_slab__full",
    "metabric_matched__expression__r01f01__pv_horseshoe__full",
})
FROZEN_REPRODUCTION_SHA256 = "1c16387ecf8cafb01488840229f51f727dbe741614c9c91996c98a1a53781428"
IDENTITY = re.compile(r"[a-z0-9_.]+\Z")
TRACE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*\.nc\Z")


def require(condition: bool, message: str) -> None:
    """Fail before a partial copy can be mistaken for a complete stage."""
    if not condition:
        raise ValueError(message)


def checked_path(path: Path, *, exists: bool = True) -> Path:
    """Reject relative, traversing, or linked input and output paths."""
    require(path.is_absolute() and ".." not in path.parts, f"unsafe path: {path}")
    require(not any(item.is_symlink() for item in (path, *path.parents)), f"linked path: {path}")
    if exists:
        require(path.exists(), f"missing path: {path}")
    return path


def regular_file(path: Path) -> Path:
    """Require an ordinary file through ordinary parent directories."""
    checked_path(path)
    require(stat.S_ISREG(path.lstat().st_mode), f"non-regular file: {path}")
    return path


def digest(path: Path) -> str:
    """Hash a checked evidence file without loading NetCDF bytes into memory."""
    value = hashlib.sha256()
    with regular_file(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def function_ast(path: Path, name: str) -> str:
    """Compare only the frozen scientific comparator, not analysis-only edits."""
    tree = ast.parse(regular_file(path).read_text(encoding="utf-8"))
    matches = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name]
    require(len(matches) == 1, f"missing or duplicated comparator: {name}")
    return ast.dump(matches[0], include_attributes=False)


def require_frozen_comparison(code: Path, manifest: dict[str, Any]) -> None:
    """Bind every imported fit/selection function to the frozen source bytes."""
    current = Path(__file__).resolve().parents[1]
    for relative in ("scripts/reproduce_extensions.py", "src/pipelines/extensions/runner.py",
                     "src/pipelines/extensions/planning.py"):
        expected = manifest["input_sha256"][relative]
        require(digest(current / relative) == digest(code / relative) == expected,
                f"frozen reproduction source differs: {relative}")
    require(manifest["input_sha256"]["scripts/reproduce_extensions.py"] == FROZEN_REPRODUCTION_SHA256,
            "frozen reproduction script pin differs")
    relative = "src/pipelines/extensions/verification.py"
    require(digest(code / relative) == manifest["input_sha256"][relative],
            "frozen verification source differs")
    require(function_ast(current / relative, "assert_scientific_equal") ==
            function_ast(code / relative, "assert_scientific_equal"),
            "scientific comparator differs from frozen function")


def trace_paths(cell: dict[str, Any], identity: str) -> dict[str, str]:
    """Derive safe run-relative trace paths and their declared byte hashes."""
    require(cell.get("cell_id") == identity and IDENTITY.fullmatch(identity) is not None,
            f"invalid selected cell identity: {identity}")
    traces: dict[str, str] = {}
    for attempt in cell.get("fit_attempts", []):
        for trace in attempt.get("traces", {}).values():
            filename = trace["filename"]
            require(isinstance(filename, str) and TRACE_NAME.fullmatch(filename) is not None,
                    f"unsafe selected trace filename: {identity}")
            relative = f"traces/{identity}/{filename}"
            require(relative not in traces, f"duplicate selected trace: {relative}")
            traces[relative] = lineage.require_hash(trace["sha256"], relative)
    return traces


def verified_regular_cell(path: Path, identity: str) -> dict[str, Any]:
    """Reject linked trace paths before the frozen checkpoint verifier opens them."""
    raw = lineage.read(regular_file(path))
    for relative in trace_paths(raw, identity):
        regular_file(path.parent.parent / relative)
    return verified_cell(path)


def exact_tree(root: Path, files: set[str], *, empty_directories: set[str] | None = None) -> None:
    """Reject linked, unexpected, or missing files and directories."""
    checked_path(root)
    require(root.is_dir(), f"not a directory: {root}")
    expected_directories = {"."}
    for relative in files:
        expected_directories.update(str(parent) for parent in Path(relative).parents)
    expected_directories.update(empty_directories or set())
    actual_files: set[str] = set()
    actual_directories = {"."}
    for current, directories, names in os.walk(root, followlinks=False):
        for name in directories:
            path = Path(current) / name
            require(not path.is_symlink() and stat.S_ISDIR(path.lstat().st_mode),
                    f"linked or non-directory entry: {path}")
            actual_directories.add(path.relative_to(root).as_posix())
        for name in names:
            path = Path(current) / name
            regular_file(path)
            actual_files.add(path.relative_to(root).as_posix())
    require(actual_files == files and actual_directories == expected_directories,
            f"staging tree has missing or extra entries: {root}")


def copy_new(source: Path, destination: Path, expected: str) -> None:
    """Copy a verified source through an exclusive destination and rehash it."""
    require(digest(source) == expected, f"source changed before copy: {source}")
    checked_path(destination, exists=False)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as reader, destination.open("xb") as writer:
        for block in iter(lambda: reader.read(4 * 1024 * 1024), b""):
            writer.write(block)
        writer.flush()
        os.fsync(writer.fileno())
    require(digest(source) == digest(destination) == expected, f"copy bytes differ: {destination}")


def write_new_json(path: Path, value: dict[str, Any]) -> None:
    """Publish one external, canonically sealed, write-once staging receipt."""
    value = {**value, "content_sha256": lineage.canonical_hash(value)}
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def selected_roster(manifest: dict[str, Any], code: Path, matched: Path) -> list[str]:
    """Rebuild the complete frozen plan, then select its exact first-fold grid."""
    _, _, jobs = assembly.validated_jobs(manifest, code, matched)
    planned = [row["cell_id"] for row in manifest["plan"]]
    require(len(planned) == PLANNED and len(set(planned)) == PLANNED
            and set(jobs) == set(planned), "recovered plan differs from frozen jobs")
    selected = [identity for identity in planned if jobs[identity].repeat == jobs[identity].fold == 1]
    require(len(selected) == SELECTED and len(set(selected)) == SELECTED
            and len(AFFECTED) == SELECTED - REUSED and AFFECTED <= set(selected),
            "selected reproduction roster differs from frozen 89/3 partition")
    return selected


def require_deep_completion(run: Path, manifest_sha: str) -> str:
    """Bind a prior full-grid deep verification without repeating rescoring."""
    path = run / "completion.json"
    completion = lineage.read(path)
    seal = completion.get("completion_content_sha256")
    require(seal == lineage.canonical_hash({key: value for key, value in completion.items()
                                            if key != "completion_content_sha256"}),
            "deep completion content seal differs")
    require(completion.get("verification") == "deep"
            and completion.get("planned") == completion.get("stored") == PLANNED
            and completion.get("manifest_sha256") == manifest_sha
            and completion.get("production_code_commit") == recovery.SEALED_COMMIT,
            "full-grid deep completion is absent or source-unbound")
    expected_cells = {f"cells/{path.name}": digest(path)
                      for path in sorted((run / "cells").glob("*.json"))}
    require(len(expected_cells) == PLANNED and completion.get("cell_sha256") == expected_cells,
            "deep completion cell hashes differ from recovered source")
    aggregates = completion.get("aggregate_sha256")
    require(isinstance(aggregates, dict) and set(aggregates) == {
        "paired_families.json", "decision_curves.json", "rq2_effects.json"},
        "deep completion aggregate inventory differs")
    for relative, expected in aggregates.items():
        require(digest(run / relative) == expected, f"deep aggregate bytes differ: {relative}")
    verification = lineage.read(run / "verification.json")
    require(all(completion.get(key) == value for key, value in verification.items())
            and verification.get("verification") == "deep", "deep verification report differs")
    return digest(path)


def stage(args: argparse.Namespace) -> dict[str, Any]:
    """Check all 89 saved refits and publish only their cells and traces."""
    run = checked_path(args.recovered_run)
    original = checked_path(args.original_run)
    prestage = checked_path(args.prestage)
    matched = regular_file(checked_path(args.matched))
    code = checked_path(args.frozen_code)
    destination = checked_path(args.destination, exists=False)
    receipt = checked_path(args.receipt, exists=False)
    require(all(path.is_dir() for path in (run, original, prestage, code))
            and destination.parent.is_dir() and receipt.parent.is_dir()
            and not destination.exists() and not receipt.exists(),
            "existing evidence and fresh destination/receipt required")
    for source in (run, original, prestage, code):
        require(not destination.is_relative_to(source) and not source.is_relative_to(destination),
                "staging destination overlaps an input")
    require(destination != matched and receipt != matched, "staging path overlaps matched input")
    require(not receipt.is_relative_to(destination)
            and not any(receipt.is_relative_to(source) for source in (run, original, prestage, code)),
            "external receipt overlaps an input or destination")
    recovery.require_apfs(destination)
    recovery.require_free_space(destination, gib=1)

    proof = lineage.verify_recovered_lineage(run)
    require(proof["status"] == "recovered_lineage_verified"
            and proof["stored_cells"] == PLANNED
            and proof["manifest_sha256"] == lineage.INTERRUPTED_MANIFEST_SHA256,
            "complete recovered producer lineage required")
    manifest_sha = digest(run / "manifest.json")
    require(manifest_sha == digest(original / "manifest.json") == lineage.INTERRUPTED_MANIFEST_SHA256,
            "original and recovered frozen manifests differ")
    completion_sha = require_deep_completion(run, manifest_sha)
    manifest = lineage.read(run / "manifest.json")
    require(digest(matched) == manifest["matched_sha256"], "matched cohort bytes differ")
    git_dir = checked_path(args.production_git_dir) if args.production_git_dir else None
    production = assembly.require_production_root(manifest, code, git_dir)
    require_frozen_comparison(code, manifest)
    selected = selected_roster(manifest, code, matched)
    base = lineage.read(run / "recovery_lineage.json")
    final_sha = digest(run / "recovery_continuation.json")
    require(proof["base_lineage_sha256"] == digest(run / "recovery_lineage.json")
            and proof["final_lineage_sha256"] == final_sha,
            "recovered lineage anchors changed")
    producers = base["payload"]["producers"]
    require(all(producers[identity]["producer"] == ("new_refit" if identity in AFFECTED
                                                       else "intact_original") for identity in selected),
            "selected recovered producers differ from frozen 89/3 partition")

    old_cells = {path.stem for path in (prestage / "cells").glob("*.json")}
    require(old_cells == set(selected), "prestaged selected cell inventory differs")
    expected_old_files = {f"cells/{identity}.json" for identity in selected}
    copied: dict[str, str] = {}
    rows: dict[str, Any] = {}
    for identity in selected:
        if identity in AFFECTED:
            continue
        source_path = run / "cells" / f"{identity}.json"
        original_path = original / "cells" / f"{identity}.json"
        refit_path = prestage / "cells" / f"{identity}.json"
        source = verified_regular_cell(source_path, identity)
        before = verified_regular_cell(original_path, identity)
        refit = verified_regular_cell(refit_path, identity)
        require(digest(source_path) == digest(original_path)
                == producers[identity]["cell_file_sha256"],
                f"intact selected source bytes differ: {identity}")
        require(source == before and source["cell_id"] == refit["cell_id"] == identity,
                f"selected cell content/identity differs: {identity}")
        traces = trace_paths(source, identity)
        require(traces == trace_paths(before, identity)
                == producers[identity]["trace_sha256"],
                f"intact selected source traces differ: {identity}")
        for relative, expected in traces.items():
            require(digest(run / relative) == digest(original / relative) == expected,
                    f"intact selected trace bytes differ: {relative}")
        refit_traces = trace_paths(refit, identity)
        for relative, expected in refit_traces.items():
            require(digest(prestage / relative) == expected,
                    f"prestaged refit trace bytes differ: {relative}")
            require(relative not in copied, f"duplicate prestaged refit trace: {relative}")
            copied[relative] = expected
            expected_old_files.add(relative)
        assert_scientific_equal(scientific_content(source), scientific_content(refit), identity)
        compare_traces(run, prestage, source, refit)
        relative = f"cells/{identity}.json"
        copied[relative] = digest(refit_path)
        rows[identity] = {"origin": "previously_fitted_prestaged_refit",
                          "source_cell_file_sha256": digest(source_path),
                          "source_cell_content_sha256": source["cell_content_sha256"],
                          "refit_cell_file_sha256": copied[relative],
                          "refit_cell_content_sha256": refit["cell_content_sha256"],
                          "refit_trace_sha256": refit_traces,
                          "scientific_comparison": "frozen_fields_and_sampled_arrays_exact"}
    require(len(rows) == REUSED and sum(path.startswith("traces/") for path in copied) == TRACES,
            "89 prestaged cells or 74 traces differ")
    require(set(copied) | {f"cells/{identity}.json" for identity in AFFECTED} == expected_old_files,
            "prestaged selected refit paths differ")
    exact_tree(prestage, expected_old_files,
               empty_directories={f"traces/{identity}" for identity in AFFECTED})

    temporary = destination.with_name(f".{destination.name}.stage-{uuid.uuid4().hex}")
    checked_path(temporary, exists=False)
    temporary.mkdir()
    try:
        for relative, expected in sorted(copied.items()):
            copy_new(prestage / relative, temporary / relative, expected)
        exact_tree(temporary, set(copied))
        for identity in rows:
            verified_regular_cell(temporary / "cells" / f"{identity}.json", identity)
        require(all(digest(prestage / relative) == digest(temporary / relative) == expected
                    for relative, expected in copied.items()), "staged or source bytes changed")
        require(digest(run / "manifest.json") == digest(original / "manifest.json") == manifest_sha
                and digest(run / "recovery_continuation.json") == final_sha
                and digest(run / "recovery_lineage.json") == proof["base_lineage_sha256"]
                and digest(run / "completion.json") == completion_sha,
                "source anchors changed during staging")
        result = {"schema_version": 1, "status": "recovered_extension_89_refits_staged",
                  "destination": str(destination), "source_recovered_run": str(run),
                  "original_run": str(original), "prestage": str(prestage),
                  "frozen_code": str(code), "production_attestation": production,
                  "source_manifest_sha256": manifest_sha,
                  "source_deep_completion_sha256": completion_sha,
                  "recovery_lineage_sha256": proof["base_lineage_sha256"],
                  "recovery_continuation_sha256": final_sha,
                  "adapter_sha256": digest(Path(__file__)),
                  "reproduction_script_sha256": FROZEN_REPRODUCTION_SHA256,
                  "staged_cell_count": REUSED, "staged_trace_count": TRACES,
                  "staged_file_sha256": copied, "reused_refits": rows,
                  "pending_fresh_refit_ids": [identity for identity in selected if identity in AFFECTED],
                  "fresh_fits_executed": 0, "official_reproduction_receipts_issued": 0,
                  "adr041_original_numerical_producer_approved": False}
        write_new_json(temporary / "rebind_stage.json", result)
        exact_tree(temporary, set(copied) | {"rebind_stage.json"})
        require(not destination.exists(), "destination appeared during staging")
        temporary.rename(destination)
    except BaseException:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    external = {**result, "staged_provenance_sha256": digest(destination / "rebind_stage.json")}
    write_new_json(receipt, external)
    return external


def main() -> int:
    """Require explicit paths and perform a single write-once 89-cell stage."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("recovered-run", "original-run", "prestage", "matched", "frozen-code",
                 "destination", "receipt"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--production-git-dir", type=Path)
    args = parser.parse_args()
    result = stage(args)
    print(json.dumps({key: result[key] for key in
                      ("status", "destination", "staged_cell_count", "staged_trace_count",
                       "pending_fresh_refit_ids")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
