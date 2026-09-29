"""Scope and evidence gates for actual selected correction reproduction.

The caller injects the byte-pinned stdlib fit support as
``_reproduction_bound_common``. Importing this module runs no scientific code.
"""

from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import _reproduction_bound_common as common

OWN_SOURCES = ("reproduction_core.py", "run_reproduction.py", "terminal_replay_child.py")
FIT_SOURCE_PINS = {
    "fit_common.py": "b17f378ba77ea3ae5ba25c836e963a1a0160556465b25745462f648e325d1f11",
    "fit_child.py": "8ec459f949d7edb18bb587b42eab5baa823fa606075b086c8a5b2475256b2935",
    "fit_controller.py": "1fdeecc9d437bae930414bc84094da01f21140e6db86e09193cf47a395f1a038",
}
COMPARISON_PINS = {
    "scripts/reproduce_extensions.py": "1c16387ecf8cafb01488840229f51f727dbe741614c9c91996c98a1a53781428",
    "src/pipelines/extensions/verification.py": "7594269be944d0da4647f741a6900c20a1db58a871c051a958f925ac2e969c10",
    "src/pipelines/extensions/planning.py": "99d2174d90aa7f50335fff510bae32da363c2dc2e54b08488e04bbc904006ee1",
    "tests/test_extensions.py": "53816fd42d733198f7a10013965e3549fe4b3a0327361749034a36f9f9cad938",
}
SCOPE_RULE = "sorted_unique(original_plan_repeat1_fold1_92_union_frozen_full_budget_pilots)"
FINAL_STATUSES = {
    "reused_verified_original_numerical_reproduction",
    "new_corrected_numerical_reproduction",
    "terminal_no_fit_recipe_replay",
}
TERMINAL = {"input_failure", "nonrank_failure", "exhausted_rank_cap"}
ACCEPTED = {"accepted_original_first_draw", "accepted_rank_conditioned_redraw"}
NUMERIC_KEYS = {"synthetic_design", "synthetic_time", "hazard", "time_scale"}
ORIGINAL_NUMERICAL_PRODUCER_COMMITS = {
    "119476fef55b1eeb690527f234c1423440720d45", "8551d326b02bfe88915cfd9eb50c6ca8e5690e3a"}
PRESTAGE_HELPER_SHA = "1b5e63aa380f707bed3e9497584070c32e2d2a1eff5b5e47272aa189b6a07b5f"


def original_selection(plan: list[dict[str, Any]], *, expected_count: int = 92) -> list[str]:
    """Derive the fixed original IDs from the exact frozen manifest grammar."""
    ids = [row["cell_id"] for row in plan]
    common.require(len(ids) == len(set(ids)), "duplicate original plan identities")
    chosen = []
    for identity in ids:
        match = re.fullmatch(r"[a-z0-9_.]+__[a-z0-9_.]+__r(\d{2})f(\d{2})__[a-z0-9_.]+__[a-z0-9_.]+", identity)
        common.require(match is not None, "original cell identity grammar differs")
        if tuple(map(int, match.groups())) == (1, 1):
            chosen.append(identity)
    common.require(len(chosen) == expected_count, "original selected reproduction count differs")
    return sorted(chosen)


def scope_definition(selection: dict[str, Any]) -> str:
    """Acyclic prospective scope, code and inputs digest, before score evidence."""
    keys = ("schema_version", "scope_rule", "original_selected_cells", "pilot_cells", "selected_cells",
            "original_manifest_sha256", "correction_freeze_sha256", "corrected_manifest_sha256",
            "definition_content_sha256", "input_inventory_sha256", "implementation_source_sha256",
            "fit_implementation_source_sha256", "comparison_source_sha256", "recipe_inventory_sha256",
            "original_numerical_evidence_sha256", "execution")
    return common.digest({key: selection[key] for key in keys})


def validate_scope(selection: dict[str, Any], original: dict[str, Any], manifest: dict[str, Any],
                   *, expected_count: int = 92) -> None:
    """Require the original fixed selection union the input-selected pilots."""
    original_ids = original_selection(original["plan"], expected_count=expected_count)
    pilots = manifest["pilot_cells"]
    common.require(pilots == sorted(set(pilots)), "pilot list must be sorted and unique")
    all_ids = {row["cell_id"] for row in original["plan"]}
    common.require(set(pilots) <= all_ids, "foreign pilot identity")
    expected = sorted(set(original_ids) | set(pilots))
    common.require(selection["scope_rule"] == SCOPE_RULE
                   and selection["original_selected_cells"] == original_ids
                   and selection["pilot_cells"] == pilots and selection["selected_cells"] == expected,
                   "frozen selected reproduction scope differs")


def load_selection(path: Path, expected: str, own: Path) -> tuple[dict[str, Any], Any, Any, Any, Any]:
    """Verify actual external approvals; this function cannot create approval."""
    selection = common.read_json(path, expected)
    common.require(selection["status"] == "reviewed_corrected_reproduction_selection"
                   and selection["schema_version"] == 1, "actual reviewed selection required")
    common.require(selection["implementation_source_sha256"] == {name: common.sha(own / name) for name in OWN_SOURCES}
                   and selection["fit_implementation_source_sha256"] == FIT_SOURCE_PINS
                   and selection["comparison_source_sha256"] == COMPARISON_PINS,
                   "reproduction, fit or original comparison sources differ")
    paths = {key: common.safe(Path(value)) for key, value in selection["paths"].items()}
    common.require(set(paths) == {"freeze", "manifest", "fit_code", "corrected_run", "original_reproduction",
                                 "original_numerical_evidence", "recipe_inventory", "scope_review"},
                   "reproduction path roles differ")
    for name, pin in FIT_SOURCE_PINS.items():
        common.require(common.sha(paths["fit_code"] / name) == pin, "sealed fit source differs")
    freeze, manifest, inventory, completion = common.load_gates(
        paths["freeze"], selection["correction_freeze_sha256"], paths["manifest"],
        selection["corrected_manifest_sha256"], paths["fit_code"])
    common.require(selection["original_manifest_sha256"] == freeze["original_manifest_sha256"]
                   and selection["definition_content_sha256"] == freeze["definition_content_sha256"]
                   and selection["input_inventory_sha256"] == freeze["input_inventory_sha256"],
                   "selected reproduction scientific inputs differ")
    original = common.read_original_manifest(Path(freeze["paths"]["original_run"]))
    validate_scope(selection, original, manifest)
    for name, pin in COMPARISON_PINS.items():
        common.require(common.sha(common.below(Path(freeze["paths"]["source"]), name)) == pin,
                       "frozen original comparison/test bytes differ")
    common.require(selection["execution"] == {
        "workers": 1, "numeric_threads": 1, "original_full_budget": True,
        "terminal_recipe": "normal_full_raw_preprocessing_original_generator_rank_only_cap256",
        "comparison": "original_scientific_content_tolerance1e-10_and_exact_posterior_sample_stats",
        "pending_original_policy": "await_reviewed_original_numerical_evidence_and_finished_owner"},
        "selected reproduction policy differs")
    review = common.read_json(paths["scope_review"], selection["scope_review_sha256"])
    common.require(review["status"] == "reproduction_scope_frozen_before_corrected_score"
                   and review["scope_definition_sha256"] == scope_definition(selection)
                   and review["corrected_manifest_sha256"] == selection["corrected_manifest_sha256"]
                   and review["frozen_before_any_corrected_score"] is True,
                   "independent prospective root scope review required")
    evidence = common.read_json(paths["original_numerical_evidence"], selection["original_numerical_evidence_sha256"])
    common.require(evidence["status"] == "reviewed_original_92_numerical_reproduction_evidence"
                   and evidence["original_manifest_sha256"] == common.ORIGINAL_MANIFEST_SHA
                   and evidence["comparison_source_sha256"] == COMPARISON_PINS
                   and sorted(evidence["entries"]) == selection["original_selected_cells"],
                   "explicit original92 evidence inventory required, including pending members")
    rows = recipe_rows(paths["recipe_inventory"], selection["recipe_inventory_sha256"], completion)
    preflight_manifest = common.read_json(Path(freeze["paths"]["preflight"]) / "manifest.json", freeze["preflight_manifest_sha256"])
    common.require(preflight_manifest["contexts_jsonl_sha256"] == selection["recipe_inventory_sha256"],
                   "selected recipe is not the exact preflight recipe")
    return selection, freeze, manifest, inventory, (completion, rows, evidence)


def recipe_rows(path: Path, expected: str, completion: dict[str, Any], *, expected_count: int = 1650) -> list[dict[str, Any]]:
    """Require the complete ordered historical generator recipe, no arrays read."""
    common.require(common.sha(path) == expected, "recipe bytes differ")
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    common.require(len(rows) == expected_count and len({row["context_id"] for row in rows}) == expected_count
                   and [row["context_id"] for row in rows] == [row["context_id"] for row in completion["outcomes"]],
                   "full generator recipe accounting differs")
    common.require(common.sha(path) == expected, "recipe changed during read")
    return rows


def selected_contexts(rows: list[dict[str, Any]], identity: str, model: str) -> list[dict[str, Any]]:
    """Cover outer and all WME inner recipes, including unreached contexts."""
    found = [row for row in rows if row["outer_cell_id"] == identity]
    expected = {"outer", "inner_01", "inner_02", "inner_03"} if model == "catalytic_wme" else {"outer"}
    common.require(len(found) == len(expected) and {row["context_id"].split("::")[-1] for row in found} == expected,
                   "selected catalytic context coverage differs")
    return found


def extract_functions(path: Path, expected: str, names: tuple[str, ...], namespace: dict[str, Any]) -> dict[str, Any]:
    """Load exact original function ASTs without module top-level science/main."""
    common.require(common.sha(path) == expected, "original comparison function source differs")
    tree = ast.parse(path.read_text())
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    common.require({node.name for node in nodes} == set(names) and len(nodes) == len(names),
                   "original comparison function set differs")
    module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), *nodes], type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(path), "exec"), namespace)  # noqa: S102 - exact byte-pinned original function AST only
    common.require(common.sha(path) == expected, "original comparison source changed while loading")
    return {name: namespace[name] for name in names}


def original_comparators(source: Path, np: Any, az: Any) -> dict[str, Any]:
    """Original tolerance, field exclusions and exact sampled-array comparison."""
    namespace = {"np": np, "az": az, "Path": Path}
    result = extract_functions(source / "scripts/reproduce_extensions.py", COMPARISON_PINS["scripts/reproduce_extensions.py"],
                               ("scientific_content", "compare_traces"), namespace)
    result.update(extract_functions(source / "src/pipelines/extensions/verification.py",
                                  COMPARISON_PINS["src/pipelines/extensions/verification.py"],
                                  ("assert_scientific_equal",), namespace))
    return result


def trace_inventory(root: Path, cell: dict[str, Any]) -> dict[str, Any]:
    """Bind every referenced and orphan trace before/after a numeric comparison."""
    identity = cell["cell_id"]
    common.require(re.fullmatch(r"[a-z0-9_.]+", identity) is not None, "unsafe cell identity")
    referenced = {}
    for attempt in cell.get("fit_attempts", []):
        for record in attempt.get("traces", {}).values():
            name = record["filename"]
            common.require(Path(name).name == name, "unsafe trace filename")
            path = common.below(root, f"traces/{identity}/{name}")
            common.require(common.sha(path) == record["sha256"], "referenced trace bytes differ")
            referenced[str(path.relative_to(root))] = common.file_binding(path)
    all_files = {}
    directory = common.safe(root / "traces" / identity)
    if directory.exists():
        for path in sorted(directory.rglob("*")):
            common.safe(path)
            common.require(path.is_file() or path.is_dir(), "unsafe trace artifact")
            if path.is_file():
                all_files[str(path.relative_to(root))] = common.file_binding(path)
    common.require(set(referenced) <= set(all_files), "missing referenced trace")
    return {"referenced": referenced, "unreferenced": {name: value for name, value in all_files.items() if name not in referenced}}


def compare_cells(left_path: Path, right_path: Path, left_root: Path, right_root: Path,
                  comparators: dict[str, Any]) -> dict[str, Any]:
    """Compare actual science and sampled arrays; hashes are lineage only."""
    left_byte, right_byte = common.sha(left_path), common.sha(right_path)
    left = common.read_json(left_path, left_byte, field="cell_content_sha256")
    right = common.read_json(right_path, right_byte, field="cell_content_sha256")
    common.require(left["cell_id"] == right["cell_id"] and left["status"] in common.OUTCOMES
                   and right["status"] in common.OUTCOMES, "numerical reproduction cell identity/status differs")
    before = [trace_inventory(left_root, left), trace_inventory(right_root, right)]
    comparators["assert_scientific_equal"](comparators["scientific_content"](left),
                                           comparators["scientific_content"](right), left["cell_id"])
    comparators["compare_traces"](left_root, right_root, left, right)
    common.require(before == [trace_inventory(left_root, left), trace_inventory(right_root, right)]
                   and common.sha(left_path) == left_byte and common.sha(right_path) == right_byte,
                   "compared cells/traces changed during numerical comparison")
    return {"status": "original_scientific_and_sample_array_semantics_match", "left": common.file_binding(left_path),
            "right": common.file_binding(right_path), "left_content_sha256": left["cell_content_sha256"],
            "right_content_sha256": right["cell_content_sha256"], "trace_inventory": before,
            "scientific_comparison": "original_tolerance1e-10_after_original_field_exclusions",
            "trace_comparison": "actual_posterior_and_sample_stats_exact_equal_nan_except_original_three_clock_variables",
            "actual_returned_trace_pairs_compared": sum(len(item.get("traces", {})) for item in left.get("fit_attempts", [])),
            "sample_array_comparison_scope": "actual_returned_trace_pairs" if any(item.get("traces") for item in left.get("fit_attempts", [])) else "no_returned_sample_arrays",
            "new_numerical_fit_executed_by_comparison": False}


def compare_context_history(saved: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
    """Require a new normal-source recipe execution with the exact frozen law."""
    common.require(actual["status"] == saved["status"]
                   and actual["accepted_attempt_index"] == saved["accepted_attempt_index"], "terminal replay final outcome differs")
    if saved["status"] == "input_failure":
        common.require(not actual["attempts"] and not saved["attempts"]
                       and actual["input_error"]["type"] == saved["input_error"]["type"]
                       and actual["input_error"]["message"] == saved["input_error"]["message"],
                       "normal input failure replay differs")
        return {"status": "independent_input_failure_replayed", "attempts_compared": 0, "generator_called": False}
    common.require(actual["input_witness_sha256"] == saved["request"]["input_witness_sha256"]
                   and len(actual["attempts"]) == len(saved["attempts"]), "normal replay input/history count differs")
    for index, (before, after) in enumerate(zip(saved["attempts"], actual["attempts"], strict=True)):
        common.require(before["attempt_index"] == after["attempt_index"] == index
                       and before["seed"] == after["seed"] and before["status"] == after["status"],
                       "normal replay attempt index/seed/outcome differs")
        if before["status"] == "nonrank_error":
            common.require(after["error"]["type"] == before["error"]["type"]
                           and after["error"]["message"] == before["error"]["message"], "normal nonrank error differs")
            # An old nonrank transport did not retain constructors. New captured
            # values remain evidence, but their historical identity is unresolved.
            continue
        common.require(before["array_witnesses"] == after["array_witnesses"]
                       and before["constructor_inputs"] == after["constructor_inputs"]
                       and before["legacy_metadata"] == after["legacy_metadata"], "normal constructor values/legacy metadata differ")
        common.require({key: value for key, value in before["actual_metadata"].items() if key != "processor_origin"}
                       == {key: value for key, value in after["actual_metadata"].items() if key != "processor_origin"},
                       "normal constructor learned state/scientific metadata differ")
    return {"status": "independent_full_rank_only_recipe_history_replayed", "attempts_compared": len(actual["attempts"]),
            "generator_called": True, "processor_origin_labels_retained_separately": True,
            "nonrank_constructor_identity": "historically_unavailable" if saved["status"] == "nonrank_failure" else "exact"}


def verify_old_numerical_producer(producer: dict[str, Any], original: dict[str, Any], environment: dict[str, Any],
                                  original_run: Path, reproduction: Path, *, original_cell_id: str,
                                  invoke: Any = subprocess.run) -> dict[str, Any]:
    """Verify actual recorded original refit provenance, never infer an old run.

    The119/855 comparison script is identical. A distinct independent review
    must bind the actual producer's complete source/input set and its original
    scientific equivalence; current byte checks cannot establish past refits.
    """
    source = common.safe(Path(producer["source_path"]))
    common.require(producer["git_commit"] in ORIGINAL_NUMERICAL_PRODUCER_COMMITS
                   and set(producer["input_sha256"]) == set(original["input_sha256"]),
                   "original numerical producer checkout/input coverage differs")
    executable = shutil.which("git")
    common.require(executable is not None, "Git required to verify original numerical producer")
    def current_git() -> None:
        commit = invoke([executable, "rev-parse", "HEAD"], cwd=source, capture_output=True, text=True, check=True).stdout.strip()
        status = invoke([executable, "status", "--porcelain"], cwd=source, capture_output=True, text=True, check=True).stdout
        common.require(commit == producer["git_commit"] and not status, "original numerical producer checkout is not clean/bound")
    current_git()
    external = {}
    for name, expected in producer["input_sha256"].items():
        path = common.below(source, name)
        common.require(common.sha(path) == expected, "original numerical producer source/input bytes differ")
        external[str(path)] = common.file_binding(path)
    common.require(producer["input_sha256"]["scripts/reproduce_extensions.py"] == COMPARISON_PINS["scripts/reproduce_extensions.py"],
                   "actual original numerical producer reproduction script differs")
    documents = {}
    for role in ("environment_report", "invocation_record", "scientific_lineage_review", "official_comparison_record"):
        path = common.safe(Path(producer[role]["path"]))
        common.require(common.file_binding(path) == producer[role]["binding"], "original numerical producer evidence bytes differ")
        documents[role] = (json.loads(path.read_text()) if role == "environment_report" else common.read_json(path))
        external[str(path)] = common.file_binding(path)
    common.require(documents["environment_report"] == environment and environment["status"] == "ok"
                   and environment["package_count"] == 259, "actual original numerical environment report differs")
    invocation = documents["invocation_record"]
    common.require(invocation["status"] == "actual_original_numerical_worker_invocation_recorded"
                   and invocation["source_path"] == str(source) and invocation["git_commit"] == producer["git_commit"]
                   and invocation["original_manifest_sha256"] == common.ORIGINAL_MANIFEST_SHA
                   and invocation["original_run"] == str(original_run) and invocation["reproduction_output"] == str(reproduction)
                   and invocation["source_input_sha256"] == producer["input_sha256"]
                   and invocation["environment_report_sha256"] == producer["environment_report"]["binding"]["sha256"]
                   and invocation["original_full_budget"] is True and invocation["actual_numerical_refit_execution"] is True
                   and invocation["exit_code"] == 0 and invocation["owner_finished"] is True
                   and invocation["cached_comparison_only"] is False
                   and original_cell_id in invocation["numerically_refitted_cell_ids"]
                   and invocation["numeric_thread_environment"] == {name: "1" for name in common.NUMERIC_THREAD_VARIABLES},
                   "actual original numerical worker invocation/input/runtime proof required")
    python = Path(invocation["python_executable"])
    common.require(python.is_absolute() and python.is_file() and python.samefile(Path(sys.executable)),
                   "original numerical producer interpreter identity differs")
    matched = common.safe(Path(producer["matched_input"]["path"]))
    common.require(common.file_binding(matched) == producer["matched_input"]["binding"]
                   and producer["matched_input"]["binding"]["sha256"] == original["matched_sha256"],
                   "original numerical matched input bytes differ")
    external[str(matched)] = common.file_binding(matched)
    def verify_argv(record: dict[str, Any], script: Path, options: tuple[tuple[str, str], ...]) -> None:
        values = record["argv"]
        common.require(isinstance(values, list) and all(isinstance(value, str) for value in values),
                       "actual numerical argv must be a recorded argument list")
        cwd = common.safe(Path(record["cwd"]))
        index = record["script_index"]
        common.require(type(index) is int and 0 <= index < len(values), "recorded numerical script index differs")
        declared = Path(values[index])
        declared = declared if declared.is_absolute() else cwd / declared
        common.require(common.safe(declared) == script, "actual numerical argv/script evidence differs")
        for option, value in options:
            common.require(values.count(option) == 1 and values.index(option) + 1 < len(values)
                           and values[values.index(option) + 1] == value, "actual numerical argv input path differs")
    shared_options = (("--source", str(original_run)), ("--output", str(reproduction)), ("--matched", str(matched)))
    route = producer["route"]
    if route == "official_fresh_refit":
        verify_argv(invocation, source / "scripts/reproduce_extensions.py", shared_options)
    elif route == "reviewed_external_prestage":
        common.require(producer["git_commit"] == common.ORIGINAL_COMMIT
                       and producer["input_sha256"] == original["input_sha256"], "prestage must delegate the exact sealed119 source")
        helper = common.safe(Path(producer["helper"]["path"]))
        common.require(common.file_binding(helper) == producer["helper"]["binding"]
                       and producer["helper"]["binding"]["sha256"] == PRESTAGE_HELPER_SHA,
                       "actual reviewed external prestage helper bytes differ")
        worker, workers = invocation["worker"], invocation["workers"]
        common.require(type(worker) is int and type(workers) is int and 0 <= worker < workers,
                       "actual prestage worker shard differs")
        verify_argv(invocation, helper, shared_options + (("--production-code", str(source)),
                    ("--worker", str(worker)), ("--workers", str(workers))))
        selected = [row["cell_id"] for row in original["plan"] if "__r01f01__" in row["cell_id"]]
        common.require(len(selected) == 92 and original_cell_id in selected
                       and selected.index(original_cell_id) % workers == worker, "actual prestage selected shard does not own this cell")
        review_path = common.safe(Path(producer["helper_scientific_delegation_review"]["path"]))
        common.require(common.file_binding(review_path) == producer["helper_scientific_delegation_review"]["binding"],
                       "actual helper delegation review bytes differ")
        helper_review = common.read_json(review_path)
        common.require(helper_review["status"] == "actual_prestage_helper_scientific_delegation_reviewed"
                       and helper_review["helper_sha256"] == PRESTAGE_HELPER_SHA
                       and helper_review["original_manifest_sha256"] == common.ORIGINAL_MANIFEST_SHA
                       and helper_review["production_source_commit"] == common.ORIGINAL_COMMIT
                       and helper_review["unchanged_run_extension_cell_inputs_seeds_budget_and_guards"] is True
                       and helper_review["issues_official_final_receipts"] is False,
                       "actual prestage scientific delegation review required")
        stdout = common.safe(Path(invocation["stdout"]["path"]))
        common.require(common.file_binding(stdout) == invocation["stdout"]["binding"]
                       and f"{original_cell_id} prestaged_exact" in stdout.read_text().splitlines(),
                       "actual prestage log does not witness a newly executed exact refit")
        external.update({str(helper): common.file_binding(helper), str(review_path): common.file_binding(review_path),
                         str(stdout): common.file_binding(stdout)})
    else:
        common.require(False, "unknown actual original numerical producer route")
    # The official comparator can operate on cached pre-stage cells. That is
    # a separate actual comparison proof and never supplies numerical refit
    # execution provenance by itself.
    official = documents["official_comparison_record"]
    common.require(official["status"] == "actual_official_original_92_comparison_recorded"
                   and official["source_path"] == str(source) and official["git_commit"] == producer["git_commit"]
                   and official["original_manifest_sha256"] == common.ORIGINAL_MANIFEST_SHA
                   and official["source_input_sha256"] == producer["input_sha256"]
                   and official["environment_report_sha256"] == producer["environment_report"]["binding"]["sha256"]
                   and official["exit_code"] == 0 and official["owner_finished"] is True
                   and original_cell_id in official["scientifically_compared_cell_ids"]
                   and official["numeric_thread_environment"] == {name: "1" for name in common.NUMERIC_THREAD_VARIABLES}
                   and Path(official["python_executable"]).is_absolute()
                   and Path(official["python_executable"]).is_file()
                   and Path(official["python_executable"]).samefile(Path(sys.executable)),
                   "separate actual official original comparison execution proof required")
    verify_argv(official, source / "scripts/reproduce_extensions.py", shared_options)
    if route == "reviewed_external_prestage":
        common.require(official["cached_comparison_only"] is True, "prestage official comparison must be distinguished from fresh refit")
    else:
        common.require(official["cached_comparison_only"] is False, "cached official compare alone cannot certify original numerical refit")
    lineage = documents["scientific_lineage_review"]
    common.require(lineage["status"] == "original_numerical_execution_input_and_algorithm_lineage_reviewed"
                   and lineage["original_manifest_sha256"] == common.ORIGINAL_MANIFEST_SHA
                   and lineage["producer_git_commit"] == producer["git_commit"]
                   and lineage["producer_input_sha256"] == producer["input_sha256"]
                   and lineage["original_input_sha256"] == original["input_sha256"]
                   and lineage["invocation_record_sha256"] == producer["invocation_record"]["binding"]["sha256"]
                   and lineage["official_comparison_record_sha256"] == producer["official_comparison_record"]["binding"]["sha256"]
                   and lineage["producer_route"] == route
                   and lineage["frozen_primary_scientific_inputs_algorithms_seeds_budgets_and_gates_identical"] is True,
                   "independent actual producer input/algorithm lineage review required")
    current_git()
    for path, binding in external.items():
        common.require(common.file_binding(Path(path)) == binding, "original numerical producer evidence changed")
    return external


def publication_status(outcomes: list[dict[str, Any]], selected: list[str]) -> dict[str, Any]:
    """Selected coverage only; no whole-grid numerical rerun or release claim."""
    common.require([row["original_cell_id"] for row in outcomes] == selected, "selected accounting order differs")
    complete = all(row["status"] in FINAL_STATUSES for row in outcomes)
    return {"status": "all_selected_reproduction_outcomes_accounted" if complete else "selected_reproduction_pending",
            "scheduled_selected_cells": len(selected), "accounted_selected_cells": sum(row["status"] in FINAL_STATUSES for row in outcomes),
            "outcomes": outcomes, "selected_scope_only": True, "whole_1625_grid_numerically_reproduced": False,
            "programme_complete": False, "reporting_certified": False, "release_certified": False}
