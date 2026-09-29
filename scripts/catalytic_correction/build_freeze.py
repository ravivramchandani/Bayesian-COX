"""Prospective proposal/freeze assembly from existing reviewed evidence only.

This stdlib module imports no scientific package and performs no generator,
decomposition, checker, optimizer, model, prediction or score operation.
Actual CLI execution reads and hashes existing evidence. Only root supplies
approval receipts; this helper never creates them or launches numerical work.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

COMMON_SHA = "b17f378ba77ea3ae5ba25c836e963a1a0160556465b25745462f648e325d1f11"
FIT_SOURCES = {"fit_common.py": COMMON_SHA,
               "fit_child.py": "8ec459f949d7edb18bb587b42eab5baa823fa606075b086c8a5b2475256b2935",
               "fit_controller.py": "1fdeecc9d437bae930414bc84094da01f21140e6db86e09193cf47a395f1a038"}
PATH_ROLES = {"source", "original_run", "matched", "preflight", "contracts", "preflight_core",
              "reuse_core", "witness_root", "inventory"}
REVIEW_ROLES = {"method", "arithmetic", "input_witness", "implementation", "freeze"}
PRODUCTION_CELLS, PRODUCTION_CONTEXTS = 1625, 1650


def load_common(directory: Path) -> Any:
    """Load the exact sealed stdlib fit support in a fresh private namespace."""
    path = directory / "fit_common.py"
    if (not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents))
            or hashlib.sha256(path.read_bytes()).hexdigest() != COMMON_SHA):
        raise ValueError("sealed fit_common bytes/path required")
    name = "_freeze_builder_bound_common"
    if name in sys.modules:
        raise ValueError("private helper namespace already occupied")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError("cannot load pinned support")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
        if module.sha(path) != COMMON_SHA:
            raise ValueError("support changed during import")
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


class Evidence:
    """Keep actual byte bindings and recheck them before/after publication."""

    def __init__(self, common: Any) -> None:
        self.common, self.observed = common, {}

    def bind(self, path: Path, expected: str) -> None:
        """Bind a regular unlinked file to one consistent expected byte digest."""
        self.common.require(path not in self.observed or self.observed[path] == expected,
                            "conflicting input byte pin")
        self.common.require(self.common.sha(path) == expected, f"input bytes differ: {path}")
        self.observed[path] = expected

    def read(self, path: Path, expected: str) -> dict[str, Any]:
        """Read finite content-sealed JSON only after checking its actual bytes."""
        self.bind(path, expected)
        return self.common.read_json(path, expected)

    def artifacts(self, root: Path, artifacts: dict[str, Any]) -> None:
        """Bind exact declared artifact bytes without opening numerical arrays."""
        self.common.verify_files(root, artifacts)
        for name, row in artifacts.items():
            self.bind(self.common.below(root, name), row["sha256"])

    def recheck(self) -> None:
        """Refuse a source race; no changed bytes can yield successful stdout."""
        for path, expected in self.observed.items():
            self.common.require(self.common.sha(path) == expected, "input changed during assembly")


def expected_context_ids(entries: list[dict[str, Any]]) -> set[str]:
    """Derive the original825 catalytic outer plus825 WME inner identity set."""
    return {f"{row['original_cell_id']}::{name}" for row in entries
            if row["model"] in {"catalytic_fixed", "catalytic_adaptive", "catalytic_wme"}
            for name in (["outer", "inner_01", "inner_02", "inner_03"]
                         if row["model"] == "catalytic_wme" else ["outer"])}


def validate_scope(common: Any, original: dict[str, Any], definition: dict[str, Any],
                   inventory: dict[str, Any], preflight_manifest: dict[str, Any],
                   completion: dict[str, Any], replay: dict[str, Any], binding: dict[str, Any]) -> None:
    """Require fixed full coverage and exact original policy, allowing old owners.

    These are structural gates on existing evidence. They do not infer actual
    reuse, select by outcomes or confer scientific approval.
    """
    require = common.require
    require(definition["original_production_commit"] == common.ORIGINAL_COMMIT
            and definition["original_manifest_sha256"] == common.ORIGINAL_MANIFEST_SHA
            and definition["original_input_sha256"] == original["input_sha256"]
            and definition["original_configuration"] == original["run_config"]
            and definition["matched_sha256"] == original["matched_sha256"]
            and definition["attempt_cap"] == 256
            and definition["retry_seed_rule"] == "originalseed; deterministic_seed(originalseed,'rank_conditioned_retry',index1..255)"
            and definition["numerical_thread_policy"] == 1, "scientific correction definition differs")
    common.validate_budget(original["run_config"])
    require(inventory["status"] == "complete_input_witness_and_original_acquisition_inventory"
            and inventory["scheduled_cells"] == len(inventory["entries"]) == PRODUCTION_CELLS
            and [row["original_cell_id"] for row in inventory["entries"]] == [row["cell_id"] for row in original["plan"]]
            and len({row["original_cell_id"] for row in inventory["entries"]}) == PRODUCTION_CELLS
            and inventory["definition_content_sha256"] == definition["content_sha256"], "complete exact1625 inventory required")
    require(all(f"__{row['model']}__" in row["original_cell_id"] for row in inventory["entries"]),
            "cell model label does not match original identity")
    ids = expected_context_ids(inventory["entries"])
    require(len(ids) == PRODUCTION_CONTEXTS
            and completion["status"] == "all_scheduled_contexts_accounted"
            and completion["scheduled_contexts"] == completion["accounted_contexts"] == len(completion["outcomes"]) == PRODUCTION_CONTEXTS
            and {row["context_id"] for row in completion["outcomes"]} == ids
            and completion["run_binding_sha256"] == preflight_manifest["content_sha256"]
            and inventory["preflight_completion_sha256"] == binding["preflight_completion_sha256"], "complete exact1650 preflight required")
    require(replay["status"] == "all1650_independent_first_draw_contexts_accounted"
            and replay["scheduled_contexts"] == replay["accounted_contexts"] == len(replay["outcomes"]) == PRODUCTION_CONTEXTS
            and [row["context_id"] for row in replay["outcomes"]] == [row["context_id"] for row in completion["outcomes"]]
            and replay["definition_content_sha256"] == definition["content_sha256"]
            and inventory["replay_completion_sha256"] == binding["replay_completion_sha256"], "complete ordered independent1650 replay required")
    require(preflight_manifest["original_manifest_sha256"] == common.ORIGINAL_MANIFEST_SHA
            and preflight_manifest["environment_verification"] == definition["environment_verification"]
            and definition["environment_verification"]["status"] == "ok"
            and definition["environment_verification"]["package_count"] == 259
            and definition["environment_verification"]["lock_sha256"] == original["input_sha256"]["conda-lock.yml"],
            "existing full locked preflight environment differs")
    for field in ("original_input_sha256", "matched_sha256", "candidate_source_sha256",
                  "correction_config_sha256", "correction_addendum_sha256"):
        require(preflight_manifest[field] == definition[field], "preflight scientific input differs: " + field)
    require(preflight_manifest["runner_source_sha256"] == definition["preflight_sources"]
            and definition["contracts_sha256"] == common.CONTRACTS_SHA
            and definition["preflight_sources"]["preflight_core.py"] == common.PREFLIGHT_CORE_SHA
            and definition["reuse_sources"]["reuse_core.py"] == common.REUSE_CORE_SHA, "sealed dependency identity differs")


def validate_arithmetic_links(common: Any, arithmetic: dict[str, Any], selector: dict[str, Any],
                              inventory: dict[str, Any], definition: dict[str, Any],
                              completion: dict[str, Any], replay: dict[str, Any],
                              binding: dict[str, Any]) -> None:
    """Bind existing arithmetic to the current exact inventory and selector.

    The caller must read selector bytes using inventory.arithmetic_selector_sha256
    through Evidence before calling. The selector precedes the inventory, so it
    intentionally carries no inventory hash. This validates existing provenance;
    it neither performs arithmetic nor approves any scientific method.
    """
    require = common.require
    require(selector["schema_version"] == 1
            and selector["status"] == "all1650_context_arithmetic_requirements_accounted"
            and selector["definition_content_sha256"] == definition["content_sha256"]
            and selector["preflight_completion_sha256"] == binding["preflight_completion_sha256"]
            and selector["replay_completion_sha256"] == binding["replay_completion_sha256"]
            and selector["scheduled_contexts"] == len(selector["entries"]) == PRODUCTION_CONTEXTS
            and [row["context_id"] for row in selector["entries"]] ==
                [row["context_id"] for row in completion["outcomes"]] ==
                [row["context_id"] for row in replay["outcomes"]]
            and selector["arithmetic_validation_executed"] is False
            and selector["scientific_method_approved"] is False,
            "actual selector scope/provenance differs")
    for row, preflight_row, replay_row in zip(selector["entries"], completion["outcomes"], replay["outcomes"], strict=True):
        require(row["preflight_receipt_path"] == preflight_row["receipt_path"]
                and row["preflight_receipt_sha256"] == preflight_row["receipt_sha256"]
                and row["replay_receipt_path"] == replay_row["receipt_path"]
                and row["replay_receipt_sha256"] == replay_row["receipt_sha256"]
                and row["arithmetic_executed_or_certified_by_selector"] is False,
                "actual selector context receipt binding differs")
    require(arithmetic["input_inventory_sha256"] == binding["input_inventory_sha256"]
            and arithmetic["definition_content_sha256"] == definition["content_sha256"]
            and arithmetic["selector_sha256"] == inventory["arithmetic_selector_sha256"]
            and arithmetic["scheduled_contexts"] == PRODUCTION_CONTEXTS,
            "arithmetic account current inventory/definition/selector/coverage differs")


def read_inputs(binding_path: Path, binding_sha: str, fit_code: Path, common: Any) -> dict[str, Any]:
    """Bind full existing evidence, without invoking any scientific operation.

    No original-owner availability check filters prospective pilots. Current
    owner/status/trace checks remain launch and full-closeout responsibilities.
    """
    evidence = Evidence(common)
    binding = evidence.read(binding_path, binding_sha)
    common.require(binding["schema_version"] == 1 and binding["status"] == "prospective_corrective_freeze_input_bindings"
                   and set(binding["paths"]) == PATH_ROLES and binding["fit_code"] == str(fit_code), "explicit input path schema differs")
    paths = {key: common.safe(Path(value)) for key, value in binding["paths"].items()}
    for name, expected in FIT_SOURCES.items():
        evidence.bind(fit_code / name, expected)
    for role, expected in (("contracts", common.CONTRACTS_SHA), ("preflight_core", common.PREFLIGHT_CORE_SHA), ("reuse_core", common.REUSE_CORE_SHA)):
        evidence.bind(paths[role], expected)
    original = common.read_original_manifest(paths["original_run"])
    evidence.bind(paths["original_run"] / "manifest.json", common.ORIGINAL_MANIFEST_SHA)
    evidence.bind(paths["matched"], original["matched_sha256"])
    definition = evidence.read(paths["witness_root"] / "definition.json", binding["definition_sha256"])
    inventory = evidence.read(paths["inventory"], binding["input_inventory_sha256"])
    preflight_manifest = evidence.read(paths["preflight"] / "manifest.json", binding["preflight_manifest_sha256"])
    completion = evidence.read(paths["preflight"] / "completion.json", binding["preflight_completion_sha256"])
    replay_path = paths["witness_root"] / "replay/completion.json"
    replay = evidence.read(replay_path, binding["replay_completion_sha256"])
    validate_scope(common, original, definition, inventory, preflight_manifest, completion, replay, binding)
    selector = evidence.read(paths["witness_root"] / "arithmetic_selector.json", inventory["arithmetic_selector_sha256"])
    for row in completion["outcomes"]:
        path = common.below(paths["preflight"], row["receipt_path"])
        receipt = evidence.read(path, row["receipt_sha256"])
        common.require(receipt["content_sha256"] == row["receipt_content_sha256"]
                       and receipt["status"] == row["status"]
                       and receipt["request"]["context_id"] == row["context_id"]
                       and receipt["request"]["run_binding_sha256"] == completion["run_binding_sha256"], "preflight context receipt differs")
        evidence.artifacts(path.parent, receipt["artifacts"])
    evidence.artifacts(replay_path.parent, replay["artifacts"])
    for row in replay["outcomes"]:
        path = common.below(paths["witness_root"], row["receipt_path"])
        receipt = evidence.read(path, row["receipt_sha256"])
        common.require(receipt["content_sha256"] == row["receipt_content_sha256"]
                       and receipt["status"] == "independent_original_first_draw_verified"
                       and receipt["context_id"] == row["context_id"]
                       and receipt["request"]["definition_content_sha256"] == definition["content_sha256"], "independent replay context differs")
        evidence.artifacts(path.parent, receipt["artifacts"])
    contracts = common.module_from_pin(paths["contracts"], common.CONTRACTS_SHA, "_freeze_builder_bound_contracts")
    context_lookup = {row["context_id"]: row for row in completion["outcomes"]}
    actual_entries = []
    for row in inventory["entries"]:
        path = common.below(paths["witness_root"], row["input_witness_path"])
        witness = evidence.read(path, row["input_witness_sha256"])
        evidence.artifacts(path.parent, witness["proof_artifacts"])
        common.verify_witness_proofs(path.parent, witness, contracts)
        decoded = common.witness_from_json(contracts, witness)
        common.require(witness["definition_content_sha256"] == definition["content_sha256"]
                       and decoded.original_cell_id == row["original_cell_id"] and decoded.model == row["model"]
                       and set(decoded.roles) == set(contracts.required_roles(decoded.model))
                       and all(value.complete() for value in decoded.roles.values()), "complete exact cell roles required")
        common.require(decoded.original_seeds == decoded.corrected_seeds == contracts.seed_ledger(decoded.original_cell_id)
                       and witness["selection_scope"] == row["selection_scope"], "original seed or selection metadata differs")
        required_contexts = {key.rsplit("::", 1)[1] for key in context_lookup if key.startswith(decoded.original_cell_id + "::")}
        common.require(set(decoded.generator_contexts) == required_contexts, "complete cell generator dependencies required")
        for name, (status, context_sha) in decoded.generator_contexts.items():
            actual = context_lookup[f"{decoded.original_cell_id}::{name}"]
            abstract = "accepted" if actual["status"] in {"accepted_original_first_draw", "accepted_rank_conditioned_redraw"} else actual["status"]
            common.require(status == abstract and context_sha == actual["receipt_sha256"], "cell generator receipt/status differs")
        snapshot_path = common.below(paths["witness_root"], row["snapshot_path"])
        snapshot = evidence.read(snapshot_path, row["snapshot_sha256"])
        evidence.artifacts(path.parent, snapshot["artifacts"])
        common.require(snapshot["original_cell_id"] == row["original_cell_id"]
                       and snapshot["input_witness_sha256"] == row["input_witness_sha256"]
                       and snapshot["definition_content_sha256"] == definition["content_sha256"], "historical original acquisition differs")
        decision = contracts.classify(decoded)
        actual_entries.append({"decision": decision, "selection_scope": witness["selection_scope"],
                               "generator_contexts": {key: list(value) for key, value in decoded.generator_contexts.items()}})
    tree = ast.parse(paths["reuse_core"].read_bytes())
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "pilot_input_scope"]
    common.require(len(nodes) == 1, "sealed pure pilot eligibility function missing")
    scope = {"require": common.require, "Any": Any}
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), str(paths["reuse_core"]), "exec"), scope)
    common.require(scope["pilot_input_scope"](actual_entries) == inventory["selection_scope"], "full changed-input eligible pilot scope differs")
    arithmetic_path = common.safe(Path(binding["arithmetic_accounting"]["path"]))
    arithmetic = evidence.read(arithmetic_path, binding["arithmetic_accounting"]["sha256"])
    evidence.artifacts(arithmetic_path.parent, arithmetic["artifacts"])
    validate_arithmetic_links(common, arithmetic, selector, inventory, definition, completion, replay, binding)
    common.validate_arithmetic(arithmetic, completion, binding["preflight_completion_sha256"])
    evidence.recheck()
    return {"binding": binding, "evidence": evidence, "definition": definition,
            "inventory": inventory, "completion": completion}


def proposal(common: Any, inputs: dict[str, Any], binding_sha: str) -> dict[str, Any]:
    """Create only an unapproved acyclic proposal; never synthesize reviews."""
    binding, definition = inputs["binding"], inputs["definition"]
    template = {"original_production_commit": common.ORIGINAL_COMMIT,
        "original_manifest_sha256": common.ORIGINAL_MANIFEST_SHA,
        "definition_content_sha256": definition["content_sha256"],
        "input_inventory_sha256": binding["input_inventory_sha256"],
        "preflight_completion_sha256": binding["preflight_completion_sha256"],
        "preflight_manifest_sha256": binding["preflight_manifest_sha256"],
        "implementation_source_sha256": FIT_SOURCES,
        "dependency_source_sha256": {"contracts": common.CONTRACTS_SHA, "preflight_core": common.PREFLIGHT_CORE_SHA, "reuse_core": common.REUSE_CORE_SHA},
        "paths": binding["paths"], "arithmetic_accounting": binding["arithmetic_accounting"],
        "execution": {"fit_workers": 1, "numeric_threads": 1, "original_full_budget": True,
            "pilot_rule": common.PILOT_RULE, "pilot_eligibility": common.PILOT_ELIGIBILITY,
            "original_resolution_policy": "fresh_reviewed_finished_source_snapshot"}}
    return common.seal({"schema_version": 1, "status": "unapproved_execution_definition_proposal",
        "input_bindings_sha256": binding_sha, "freeze_template": template,
        "execution_definition_sha256": common.execution_definition(template),
        "pilot_cells": common.select_pilots(inputs["inventory"]["selection_scope"]),
        "scientific_method_approved": False, "root_reviews_created": False,
        "actual_fit_or_scientific_operation_launched": False})


def approved_freeze(common: Any, proposed: dict[str, Any], reviews: dict[str, Any],
                    read_review: Any) -> dict[str, Any]:
    """Consume all five actual existing reviewed files; confer no approval.

    Args:
        read_review: Byte/content-verifying read function supplied by Evidence.
        reviews: Sealed binding carrier with exactly the five existing roles.
    Returns:
        The final exact fit_common freeze mapping, after every review matches
        the unchanged proposal's definition, inventory and acyclic digest.
    Raises:
        InvalidBinding: A role, byte binding or actual approval status differs.
    """
    common.require(reviews["status"] == "root_supplied_corrective_execution_review_bindings"
                   and set(reviews["review_bindings"]) == REVIEW_ROLES, "five existing root review roles required")
    template = proposed["freeze_template"]
    for role, row in reviews["review_bindings"].items():
        common.require(set(row) == {"path", "sha256"}, "review carrier fields differ")
        value = read_review(common.safe(Path(row["path"])), row["sha256"])
        common.require(value["status"] == "reviewed_for_corrected_fit_execution" and value["role"] == role
                       and value["definition_content_sha256"] == template["definition_content_sha256"]
                       and value["input_inventory_sha256"] == template["input_inventory_sha256"]
                       and value["execution_definition_sha256"] == proposed["execution_definition_sha256"], "actual approved review binds different execution inputs")
    return common.seal({"status": "reviewed_corrected_fit_freeze", **template,
                        "review_bindings": reviews["review_bindings"]})


def prepare_destination(common: Any, output: Path, inputs: dict[str, Any], fit_code: Path) -> None:
    """Refuse collisions/overlaps before creating any prospective output."""
    common.safe(output)
    protected = [fit_code, Path(inputs["binding"]["fit_code"]), *[Path(value) for value in inputs["binding"]["paths"].values()],
                 Path(inputs["binding"]["arithmetic_accounting"]["path"]).parent]
    common.require(not output.exists() and output.parent.is_dir()
                   and all(not output.is_relative_to(path) and not path.is_relative_to(output) for path in protected),
                   "exclusive disjoint new output with existing parent required")


def main() -> None:
    """Assemble a prospective proposal or approved freeze; never run science."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operation", choices=("proposal", "finalize"), required=True)
    for name in ("fit-code", "input-bindings", "preparation-receipt", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("input-bindings-sha256", "preparation-receipt-sha256"):
        parser.add_argument("--" + name, required=True)
    for name in ("proposal", "review-bindings"):
        parser.add_argument("--" + name, type=Path)
        parser.add_argument("--" + name + "-sha256")
    args = parser.parse_args()
    common = load_common(args.fit_code)
    preparation = common.read_json(common.safe(args.preparation_receipt), args.preparation_receipt_sha256)
    own = Path(__file__).absolute().parent
    common.require(preparation["status"] == "prospective_correction_freeze_builder_preparation_sealed"
                   and preparation["source_sha256"]["build_freeze.py"] == common.sha(own / "build_freeze.py"), "tested builder source differs")
    inputs = read_inputs(common.safe(args.input_bindings), args.input_bindings_sha256, common.safe(args.fit_code), common)
    inputs["evidence"].bind(args.preparation_receipt, args.preparation_receipt_sha256)
    inputs["evidence"].bind(own / "build_freeze.py", preparation["source_sha256"]["build_freeze.py"])
    prepare_destination(common, args.output, inputs, own)
    proposed = proposal(common, inputs, args.input_bindings_sha256)
    freeze = None
    if args.operation == "proposal":
        common.require(args.proposal is None and args.proposal_sha256 is None
                       and args.review_bindings is None and args.review_bindings_sha256 is None, "proposal does not accept approval inputs")
    else:
        common.require(all(value is not None for value in (args.proposal, args.proposal_sha256, args.review_bindings, args.review_bindings_sha256)), "finalization requires existing proposal and review carrier with byte pins")
        old = inputs["evidence"].read(common.safe(args.proposal), args.proposal_sha256)
        common.require(old == proposed, "approved proposal inputs changed; create a new unapproved proposal")
        reviews = inputs["evidence"].read(common.safe(args.review_bindings), args.review_bindings_sha256)
        freeze = approved_freeze(common, proposed, reviews, inputs["evidence"].read)
    inputs["evidence"].recheck()
    args.output.mkdir()
    started = datetime.now(UTC).isoformat()
    if freeze is None:
        common.write_new(args.output / "proposal.json", proposed)
        status, names = "unapproved_proposal_assembled", ["proposal.json"]
    else:
        common.write_new(args.output / "freeze.json", freeze)
        manifest = common.seal({"status": "corrected_fit_manifest_frozen", "freeze_sha256": common.sha(args.output / "freeze.json"),
            "definition_content_sha256": freeze["definition_content_sha256"], "input_inventory_sha256": freeze["input_inventory_sha256"],
            "pilot_cells": proposed["pilot_cells"]})
        common.write_new(args.output / "manifest.json", manifest)
        common.load_gates(args.output / "freeze.json", common.sha(args.output / "freeze.json"),
                          args.output / "manifest.json", common.sha(args.output / "manifest.json"), args.fit_code)
        status, names = "existing_review_approved_correction_freeze_assembled", ["freeze.json", "manifest.json"]
    inputs["evidence"].recheck()
    common.write_new(args.output / "assembly_receipt.json", common.seal({"status": status, "operation": args.operation,
        "argv": sys.argv, "started_at_utc": started, "finished_at_utc": datetime.now(UTC).isoformat(),
        "source_sha256": common.sha(own / "build_freeze.py"), "input_bindings_sha256": args.input_bindings_sha256,
        "preparation_receipt_sha256": args.preparation_receipt_sha256, "proposal_sha256": args.proposal_sha256,
        "review_bindings_sha256": args.review_bindings_sha256, "execution_definition_sha256": proposed["execution_definition_sha256"],
        "artifacts": {name: common.file_binding(args.output / name) for name in names},
        "existing_input_file_count": len(inputs["evidence"].observed), "root_reviews_created": False,
        "scientific_method_approval_conferred": False, "actual_scientific_operations_launched": False,
        "programme_complete": False, "numerical_results_certified": False}))
    inputs["evidence"].recheck()
    print(json.dumps({"status": status, "assembly_receipt_sha256": common.sha(args.output / "assembly_receipt.json"),
                      "programme_complete": False}, sort_keys=True), flush=True)


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    main()
