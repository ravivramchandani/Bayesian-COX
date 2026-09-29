"""Portable structural prerequisites; no cohorts or scientific imports."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from verification_io import Pins, canonical, child, require, safe

ORIGINAL_COMMIT = "119476fef55b1eeb690527f234c1423440720d45"
ORIGINAL_MANIFEST = "83b9049fb6aaaadab576b34de0741e4f510344dcefba9f96198d15b5ab4f49b9"
CONTRACTS = "83cb84002cd9dc447f70d9346baaba16197fa04d5a43e8b2fb500c2ce38f7fef"
PREFLIGHT_CORE = "6b03c18a7dc55f896d7c999e0cca676cffb9822132914ce86a90867986a4798c"
REUSE_CORE = "db558bee7973677305cc9f6e6062bb753e3dbe7daba3f5e08b80b657f115ac84"
ROOT_ROLES = {"production", "analysis", "original_run", "corrected_run", "preflight", "witness_root",
              "context_inventory", "fit_code", "contracts", "preflight_code", "reuse_code", "candidate_module",
              "correction_config", "correction_addendum", "matched", "primary", "sampler", "robustness"}
FILE_ROLES = {"freeze", "definition", "inventory", "manifest", "arithmetic_accounting"}
REVIEWS = {"method", "arithmetic", "input_witness", "implementation", "freeze"}


def unique_ids(rows: list[dict[str, Any]], key: str, expected: list[str], label: str) -> None:
    """Require exact scope and order, never infer completeness from a count."""
    require([row[key] for row in rows] == expected and len(set(expected)) == len(expected),
            label + " scope/order/duplicates differ")


def validate_source_surface(freeze: dict[str, Any], definition: dict[str, Any]) -> None:
    """Never AST-load a source omitted from the exact reviewed byte-pin surface."""
    require(set(freeze["dependency_source_sha256"]) == {"contracts", "preflight_core", "reuse_core"}
            and freeze["dependency_source_sha256"]["contracts"] == definition["contracts_sha256"] == CONTRACTS
            and freeze["dependency_source_sha256"]["preflight_core"] == definition["preflight_sources"]["preflight_core.py"] == PREFLIGHT_CORE
            and freeze["dependency_source_sha256"]["reuse_core"] == definition["reuse_sources"]["reuse_core.py"] == REUSE_CORE,
            "reviewed dependency identities differ")
    require(set(freeze["implementation_source_sha256"]) == {"fit_common.py", "fit_child.py", "fit_controller.py"},
            "exact reviewed correction runner source names required")
    require(set(definition["preflight_sources"]) == {"preflight_core.py", "run_preflight.py"}
            and set(definition["reuse_sources"]) == {"reuse_core.py", "run_reuse.py", "normal_first_draw_child.py"},
            "exact reviewed preflight/reuse source names required")


def validate_documents(freeze: dict[str, Any], definition: dict[str, Any], inventory: dict[str, Any],
                       manifest: dict[str, Any], freeze_sha: str, inventory_sha: str,
                       *, expected_count: int = 1625) -> None:
    """Pure schema/scope checks; supplying a record does not confer approval."""
    require(freeze["status"] == "reviewed_corrected_fit_freeze"
            and manifest["status"] == "corrected_fit_manifest_frozen"
            and manifest["freeze_sha256"] == freeze_sha
            and freeze["original_production_commit"] == ORIGINAL_COMMIT
            and freeze["original_manifest_sha256"] == ORIGINAL_MANIFEST,
            "reviewed new freeze and original source identity required")
    require(freeze["definition_content_sha256"] == definition["content_sha256"]
            == manifest["definition_content_sha256"] == inventory["definition_content_sha256"]
            and freeze["input_inventory_sha256"] == manifest["input_inventory_sha256"] == inventory_sha,
            "immutable correction definition/inventory differs")
    require(inventory["status"] == "complete_input_witness_and_original_acquisition_inventory"
            and inventory["scheduled_cells"] == len(inventory["entries"]) == expected_count
            and len({row["original_cell_id"] for row in inventory["entries"]}) == expected_count,
            "whole corrective input inventory required")
    require(definition["original_production_commit"] == ORIGINAL_COMMIT
            and definition["original_manifest_sha256"] == ORIGINAL_MANIFEST
            and definition["attempt_cap"] == 256
            and definition["retry_seed_rule"] == "originalseed; deterministic_seed(originalseed,'rank_conditioned_retry',index1..255)"
            and definition["numerical_thread_policy"] == 1,
            "original proposal law/seed/cap differs")
    require(set(freeze["review_bindings"]) == REVIEWS, "all actual existing review roles required")
    require(freeze["execution"] == {"fit_workers": 1, "numeric_threads": 1, "original_full_budget": True,
        "pilot_rule": "each(model,setting,gene_budget):max(n_train*p),then_lexicographic_original_cell_id",
        "pilot_eligibility": "changed_accepted_training_inputs_complete_role_and_arithmetic_accounting;original_owner_is_launch_barrier_only",
        "original_resolution_policy": "fresh_reviewed_finished_source_snapshot"},
        "original serial/pilot/ownership policy differs")


def verify_arithmetic_provenance(pins: Pins, witness_root: Path, arithmetic: dict[str, Any],
                                 inventory: dict[str, Any], definition: dict[str, Any], inventory_sha: str,
                                 completion: dict[str, Any], completion_sha: str,
                                 replay: dict[str, Any]) -> dict[str, Any]:
    """Bind actual arithmetic accounting to this exact input inventory/selector.

    The sealed selector is produced before the inventory and therefore has no
    inventory digest of its own. Its definition, preflight and independent
    replay provenance must match this inventory. No formula, acceptance or
    inferential rule is introduced here; the existing arithmetic gate remains
    responsible for the original numerical predicates and failure accounting.
    """
    selector_sha = inventory.get("arithmetic_selector_sha256")
    require(isinstance(selector_sha, str) and len(selector_sha) == 64
            and all(value in "0123456789abcdef" for value in selector_sha),
            "current inventory must bind the actual arithmetic selector bytes")
    selector = pins.json(child(witness_root, "arithmetic_selector.json"), selector_sha)
    require(arithmetic.get("input_inventory_sha256") == inventory_sha,
            "arithmetic accounting belongs to a different input inventory")
    require(arithmetic.get("definition_content_sha256") == definition["content_sha256"]
            == inventory["definition_content_sha256"] == selector.get("definition_content_sha256")
            == replay["definition_content_sha256"],
            "arithmetic accounting/selector scientific definition differs")
    require(arithmetic.get("selector_sha256") == selector_sha,
            "arithmetic accounting belongs to a different selector")
    require(type(arithmetic.get("scheduled_contexts")) is int
            and type(selector.get("scheduled_contexts")) is int
            and arithmetic["scheduled_contexts"] == selector["scheduled_contexts"] == 1650
            and len(arithmetic["context_outcomes"]) == len(selector["entries"]) == 1650,
            "whole1650 arithmetic/selector accounting required")
    require(selector.get("status") == "all1650_context_arithmetic_requirements_accounted"
            and selector.get("arithmetic_validation_executed") is False
            and selector.get("scientific_method_approved") is False,
            "actual input-only arithmetic selector required")
    require(selector.get("preflight_completion_sha256") == arithmetic["preflight_completion_sha256"]
            == inventory["preflight_completion_sha256"] == completion_sha
            and selector.get("replay_completion_sha256") == inventory["replay_completion_sha256"],
            "arithmetic selector preflight/independent replay provenance differs")
    expected = [row["context_id"] for row in completion["outcomes"]]
    unique_ids(selector["entries"], "context_id", expected, "arithmetic selector")
    unique_ids(replay["outcomes"], "context_id", expected, "arithmetic selector independent replay")
    require(len(expected) == 1650, "whole1650 arithmetic selector context scope required")
    for row, original, independent in zip(selector["entries"], completion["outcomes"], replay["outcomes"], strict=True):
        require(row["preflight_receipt_path"] == original["receipt_path"]
                and row["preflight_receipt_sha256"] == original["receipt_sha256"]
                and row["replay_receipt_path"] == independent["receipt_path"]
                and row["replay_receipt_sha256"] == independent["receipt_sha256"]
                and row.get("arithmetic_executed_or_certified_by_selector") is False,
                "arithmetic selector current context receipt/scope binding differs")
    return selector


class Gates:
    """Resolve explicit restored locations by bytes, preserving frozen path text."""

    def __init__(self, bindings: dict[str, Any], pins: Pins, *, expected_count: int = 1625) -> None:
        require(bindings["schema_version"] == 1 and set(bindings["roots"]) == ROOT_ROLES
                and set(bindings["files"]) == FILE_ROLES and set(bindings["review_paths"]) == REVIEWS,
                "explicit verification path roles differ")
        self.bindings, self.pins = bindings, pins
        self.roots = {key: safe(Path(value)) for key, value in bindings["roots"].items()}
        self.files = {key: safe(Path(value["path"])) for key, value in bindings["files"].items()}
        self.hashes = {key: value["sha256"] for key, value in bindings["files"].items()}
        self.documents = {key: pins.json(self.files[key], self.hashes[key]) for key in FILE_ROLES}
        freeze, definition, inventory, manifest = (self.documents[key] for key in
                                                   ("freeze", "definition", "inventory", "manifest"))
        validate_documents(freeze, definition, inventory, manifest, self.hashes["freeze"], self.hashes["inventory"],
                           expected_count=expected_count)
        require(self.files["definition"] == self.roots["witness_root"] / "definition.json", "definition root differs")
        self.original = pins.json(self.roots["original_run"] / "manifest.json", ORIGINAL_MANIFEST,
                                  field="manifest_content_sha256")
        require(definition["original_input_sha256"] == self.original["input_sha256"]
                and definition["original_configuration"] == self.original["run_config"]
                and definition["matched_sha256"] == self.original["matched_sha256"], "scientific definition input bytes differ")
        pins.bind(self.roots["matched"], self.original["matched_sha256"])
        pins.bind(self.roots["contracts"], CONTRACTS)
        pins.bind(self.roots["preflight_code"] / "preflight_core.py", PREFLIGHT_CORE)
        validate_source_surface(freeze, definition)
        for name, digest in freeze["implementation_source_sha256"].items():
            pins.bind(child(self.roots["fit_code"], name), digest)
        self.fit_gates = load_fit_gate_definitions(self.roots["fit_code"] / "fit_common.py")
        self.fit_gates["validate_budget"](self.original["run_config"])
        require(manifest["pilot_cells"] == self.fit_gates["select_pilots"](inventory["selection_scope"]),
                "frozen pilot dimensions/rule differ")
        for role, field in (("preflight_code", "preflight_sources"), ("reuse_code", "reuse_sources")):
            for name, digest in definition[field].items():
                pins.bind(child(self.roots[role], name), digest)
        for role, field in (("candidate_module", "candidate_source_sha256"), ("correction_config", "correction_config_sha256"),
                            ("correction_addendum", "correction_addendum_sha256")):
            pins.bind(self.roots[role], definition[field])
        for role, bound in freeze["review_bindings"].items():
            review = pins.json(safe(Path(bindings["review_paths"][role])), bound["sha256"])
            require(review["status"] == "reviewed_for_corrected_fit_execution" and review["role"] == role
                    and review["definition_content_sha256"] == definition["content_sha256"]
                    and review["input_inventory_sha256"] == self.hashes["inventory"]
                    and review["execution_definition_sha256"] == self.fit_gates["execution_definition"](freeze), "review scope differs")
        preflight = self.roots["preflight"]
        self.preflight_manifest = pins.json(preflight / "manifest.json", freeze["preflight_manifest_sha256"])
        self.preflight_completion = pins.json(preflight / "completion.json", freeze["preflight_completion_sha256"])
        complete = self.preflight_completion
        require(complete["status"] == "all_scheduled_contexts_accounted"
                and complete["scheduled_contexts"] == complete["accounted_contexts"] == 1650
                and len(complete["outcomes"]) == len({row["context_id"] for row in complete["outcomes"]}) == 1650
                and complete["run_binding_sha256"] == self.preflight_manifest["content_sha256"]
                and inventory["preflight_completion_sha256"] == freeze["preflight_completion_sha256"],
                "full 825 outer and 825 WME inner accounting required")
        for field in ("original_input_sha256", "matched_sha256", "candidate_source_sha256", "correction_config_sha256", "correction_addendum_sha256"):
            require(self.preflight_manifest[field] == definition[field], "preflight definition differs: " + field)
        require(self.preflight_manifest["runner_source_sha256"] == definition["preflight_sources"], "preflight source identity differs")
        require(self.hashes["arithmetic_accounting"] == freeze["arithmetic_accounting"]["sha256"], "frozen arithmetic evidence differs")
        arithmetic = self.documents["arithmetic_accounting"]
        pins.artifacts(self.files["arithmetic_accounting"].parent, arithmetic["artifacts"])
        self.fit_gates["validate_arithmetic"](arithmetic, complete, freeze["preflight_completion_sha256"])
        pins.bind(self.roots["context_inventory"] / "contexts.jsonl", self.preflight_manifest["contexts_jsonl_sha256"])
        pins.bind(self.roots["context_inventory"] / "preparation_receipt.json", self.preflight_manifest["inventory_receipt_sha256"])
        self.replay_completion = pins.json(self.roots["witness_root"] / "replay/completion.json", inventory["replay_completion_sha256"])
        require(self.replay_completion["status"] == "all1650_independent_first_draw_contexts_accounted"
                and self.replay_completion["definition_content_sha256"] == definition["content_sha256"]
                and self.replay_completion["scheduled_contexts"] == self.replay_completion["accounted_contexts"] == 1650,
                "independent original first draw coverage required")
        self.arithmetic_selector = verify_arithmetic_provenance(pins, self.roots["witness_root"], arithmetic,
            inventory, definition, self.hashes["inventory"], complete, freeze["preflight_completion_sha256"],
            self.replay_completion)
        pins.json(self.roots["corrected_run"] / "manifest.json", self.hashes["manifest"])
        ids = [row["cell_id"] for row in self.original["plan"]]
        unique_ids(inventory["entries"], "original_cell_id", ids, "corrective cell inventory")
        for root in (self.roots["original_run"], self.roots["corrected_run"]):
            require({path.stem for path in (root / "cells").glob("*.json")} == set(ids), "actual whole grid is incomplete/extra")
            require(not any((root / "claims").iterdir()), "a cell owner is still active")
        require(not (self.roots["corrected_run"] / "controller.claim.json").exists(), "correction controller still active")
        self.resolutions = {}
        if bindings.get("resolution_review") is not None:
            binding = bindings["resolution_review"]
            review = pins.json(safe(Path(binding["path"])), binding["sha256"])
            require(review["status"] == "original_finished_snapshots_reviewed"
                    and review["definition_content_sha256"] == definition["content_sha256"]
                    and review["input_inventory_sha256"] == self.hashes["inventory"], "later original-resolution review differs")
            self.resolutions = review["snapshots"]
        self.pilot_review = None
        if bindings.get("pilot_review") is not None:
            binding = bindings["pilot_review"]
            review = pins.json(safe(Path(binding["path"])), binding["sha256"])
            require(review["status"] == "full_budget_pilot_reviewed"
                    and review["corrected_manifest_sha256"] == self.hashes["manifest"]
                    and review["approve_remaining_selective_fits"] is True
                    and review["original_full_budget_retained"] is True
                    and review["all_failures_retained_and_reviewed"] is True
                    and set(review["pilot_outcomes"]) == set(manifest["pilot_cells"]), "existing scale-up pilot review required")
            for identity, binding in review["pilot_outcomes"].items():
                pins.bind(self.roots["corrected_run"] / "cells" / f"{identity}.json", binding["sha256"], size=binding["bytes"])
            self.pilot_review = review

    def summary(self) -> dict[str, Any]:
        """Stable logical source bindings, with host paths in separate invocation."""
        return {"freeze_sha256": self.hashes["freeze"], "definition_sha256": self.hashes["definition"],
                "definition_content_sha256": self.documents["definition"]["content_sha256"],
                "input_inventory_sha256": self.hashes["inventory"], "corrected_manifest_sha256": self.hashes["manifest"],
                "original_manifest_sha256": ORIGINAL_MANIFEST,
                "preflight_completion_sha256": self.documents["freeze"]["preflight_completion_sha256"],
                "replay_completion_sha256": self.documents["inventory"]["replay_completion_sha256"],
                "later_original_resolution_review_sha256": (self.bindings.get("resolution_review") or {}).get("sha256"),
                "actual_scale_up_pilot_review_sha256": (self.bindings.get("pilot_review") or {}).get("sha256"),
                "arithmetic_accounting_sha256": self.hashes["arithmetic_accounting"],
                "arithmetic_selector_sha256": self.documents["inventory"]["arithmetic_selector_sha256"],
                "relocation_policy": "explicit_path_roles_match_unchanged_byte_pins; frozen_paths_not_rewritten"}


def load_fit_gate_definitions(path: Path) -> dict[str, Any]:
    """Delegate byte-pinned pure existing freeze/arithmetic/pilot guards only.

    The caller has already pinned this source to the reviewed freeze. AST
    selection cannot import a controller or launch children/scientific work.
    """
    selected = {"validate_budget", "select_pilots", "validate_arithmetic", "execution_definition"}
    nodes = [node for node in ast.parse(path.read_bytes()).body if isinstance(node, ast.FunctionDef) and node.name in selected]
    require({node.name for node in nodes} == selected, "existing reviewed pure fit gate definitions missing")
    scope = {"require": require, "digest": canonical}
    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    code = ast.fix_missing_locations(ast.Module(body=[future, *nodes], type_ignores=[]))
    exec(compile(code, str(path), "exec"), scope)
    return {name: scope[name] for name in selected}


def complete_output_inventory(root: Path, ids: list[str], corrected_checks: list[str]) -> tuple[set[str], set[str]]:
    """Enumerate only the verified adapter output namespaces, including failure views."""
    files = {"invocation.json", "environment.stdout.json", "environment.stderr.log", "environment_invocation.json",
             "manifest.json", "completion.json", "reference_verification.json", "comparison_accounting.json",
             "aggregates/paired_families.json", "aggregates/rq2_effects.json", "aggregates/decision_curves.json",
             "render_input.json"}
    for identity in ids:
        files |= {f"cells/{identity}.json", f"lineage/{identity}.json", f"checks/original/{identity}.json"}
    files |= {f"checks/corrected/{identity}.json" for identity in corrected_checks}
    return files, {"cells", "lineage", "checks", "checks/original", "checks/corrected", "aggregates"}
