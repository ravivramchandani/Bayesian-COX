"""Thin source controller adapter over the unchanged selected-v1 implementation.

New I/O/provenance fields have their own source pins. The frozen selection and
the scientific producer, comparator, changed-fit and terminal methods remain
the original implementations. No scientific helper is called on import.
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from pathlib import Path
from typing import Any

import location_core as loc


def load_context(plan: dict[str, Any], selection_path: Path, selection_sha: str,
                 prepared: dict[str, Any]) -> dict[str, Any]:
    """Load the unchanged v1 selection/gates from genuinely pinned old sources."""
    io = loc.io
    roots = plan["legacy_code_roots"]
    io.require(set(roots) == set(loc.LEGACY) and plan["legacy_source_sha256"] == loc.LEGACY,
               "honest original implementation pins required")
    for role, mapping in loc.LEGACY.items():
        directory = io.safe(Path(roots[role]))
        for name, pin in mapping.items():
            io.require(io.sha(directory / name) == pin, "legacy source changed")
        io.require(io.sha(directory / "preparation_receipt.json") == loc.LEGACY_RECEIPTS[role], "legacy preparation differs")
    old_directory = Path(roots["selected"])
    legacy = loc.import_pin(old_directory / "run_reproduction.py", loc.LEGACY["selected"]["run_reproduction.py"],
                            "_location_original_selected_controller")
    common, rc = legacy.bootstrap(selection_path, selection_sha)
    selection, freeze, manifest, inventory, (completion, rows, evidence) = rc.load_selection(selection_path, selection_sha, old_directory)
    fit_directory = Path(selection["paths"]["fit_code"])
    io.require("fit_common" not in sys.modules, "fit support namespace already occupied")
    sys.modules["fit_common"] = common
    fit_controller = common.module_from_pin(fit_directory / "fit_controller.py", rc.FIT_SOURCE_PINS["fit_controller.py"],
                                            "_location_original_fit_controller")
    contracts = common.module_from_pin(Path(freeze["paths"]["contracts"]), common.CONTRACTS_SHA, "_location_original_contracts")
    args = argparse.Namespace(manifest_sha256=selection["corrected_manifest_sha256"])
    inputs = fit_controller.Controller(args, freeze, manifest, inventory, completion, contracts)
    lookup = {entry["original_cell_id"]: entry for entry in inventory["entries"]}

    def verify_input(identity: str) -> None:
        _, decision, old, _ = inputs.current(lookup[identity])
        common.require(decision["action"] == "reuse_original_outcome" and old is not None,
                       "alternate original refit requires current complete inherited input proof and finished source")

    return {"legacy": legacy, "common": common, "rc": rc, "selection": selection,
            "freeze": freeze, "manifest": manifest, "inventory": inventory, "completion": completion,
            "rows": rows, "evidence": evidence, "fit_controller": fit_controller, "contracts": contracts,
            "original": common.read_original_manifest(Path(freeze["paths"]["original_run"])),
            "verify_inherited_input": verify_input, "original_code": old_directory}


class PublishingCommon:
    """Add separately pinned I/O lineage before the original exclusive write.

    This proxy does not change a scientific field or the original seal/write
    implementation. Only owned cell and completed-pass publications gain I/O
    metadata; earlier immutable checkpoints are never rewritten.
    """

    def __init__(self, common: Any, output: Path, locations: Any) -> None:
        self.common, self.output, self.locations = common, output, locations
        self.acquisitions: dict[str, Any] = {}

    def __getattr__(self, name: str) -> Any:
        return getattr(self.common, name)

    def write_new(self, path: Path, value: dict[str, Any]) -> None:
        if path.suffix == ".json" and path.parent in {self.output / "cells", self.output / "passes"}:
            self.locations.recheck()
            value = {key: item for key, item in value.items() if key != "content_sha256"}
            value["location_extension"] = self.locations.envelope()
            if path.parent == self.output / "cells":
                identity = value["original_cell_id"]
                value["reproduction_location"] = self.locations.metadata(identity)
                value["external_artifacts"].update(self.locations.external())
                proof = self.acquisitions.get(identity)
                if proof is not None:
                    value["retained_per_entry_trees"] = proof
                    row = self.locations.value["entry_locations"][identity]
                    for role, key in (("retained_original_reproduction_tree", "historical_reproduction_root"),
                                      ("retained_original_capture_tree", "capture_root")):
                        root = self.locations.resolve(row[key])
                        value["external_artifacts"].update({str(root / name): binding for name, binding in proof[role]["artifacts"].items()})
                elif self.locations.metadata(identity) is not None:
                    self.common.require(value["status"] == "retained_reproduction_failure", "missing completed acquisition proof")
            value = self.common.seal(value)
        self.common.write_new(path, value)


def controller_class(legacy: Any, locations: Any) -> type:
    """Route original v1 methods with a local root change restored in finally."""

    class LocationController(legacy.Controller):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self.raw_common = self.common
            self.common = PublishingCommon(self.raw_common, self.args.output, locations)

        def inherited(self, identity: str, baseline: dict[str, Any], evidence: dict[str, Any]) -> tuple[Any, Any]:
            proof = loc.acquired(locations, identity, evidence)
            before = self.repro_paths["original_reproduction"]
            self.repro_paths["original_reproduction"] = locations.actual(identity)
            try:
                result, external = super().inherited(identity, baseline, evidence)
                if proof:
                    self.common.acquisitions[identity] = proof
                locations.recheck()
                return result, external
            finally:
                self.repro_paths["original_reproduction"] = before

        def record(self, entry: dict[str, Any]) -> dict[str, Any]:
            identity = entry["original_cell_id"]
            meta = locations.metadata(identity)
            path = self.args.output / "cells" / (identity + ".json")
            if meta is not None:
                _, decision, old, _ = self.input_controller.current(entry)
                self.raw_common.require(decision["action"] == "reuse_original_outcome" and old is not None,
                                        "per-entry root applies only to independently verified inherited inputs")
                if any((root / "claims" / (identity + ".json")).exists() for root in {
                    locations.resolve(str(locations.default)), locations.actual(identity)}):
                    return {"original_cell_id": identity, "status": "pending_original_numerical_owner"}
                proof = self.numerical.get(identity)
                if proof is not None and proof["status"] != "pending_original_numerical_reproduction":
                    locations.resolution(identity, proof)
            if path.exists():
                value = self.raw_common.read_json(path)
                locations.verify_envelope(value["location_extension"], identity)
                self.raw_common.require(value["reproduction_location"] == meta,
                                        "immutable checkpoint belongs to another per-entry I/O root")
                if meta is not None and value["status"] == "reused_verified_original_numerical_reproduction":
                    now = loc.acquired(locations, identity, self.numerical[identity])
                    self.raw_common.require(value["retained_per_entry_trees"] == now, "retained alternate capture/refit tree changed")
            before = self.repro_paths["original_reproduction"]
            self.repro_paths["original_reproduction"] = locations.actual(identity)
            try:
                result = super().record(entry)
                locations.recheck()
                return result
            finally:
                self.repro_paths["original_reproduction"] = before

    return LocationController


def run(args: argparse.Namespace, prepared: dict[str, Any]) -> dict[str, Any]:
    """Execute only the unchanged selected scope, after actual reviewed gates."""
    io = loc.io
    io.require(args.python.is_absolute() and args.python.is_file() and args.python.samefile(Path(sys.executable)), "locked actual interpreter differs")
    io.require(all(os.environ.get(name) == "1" for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS")), "all five numeric thread variables must already equal one")
    args.python = io.safe(args.python.resolve(strict=True))
    plan = io.read(args.location_plan, args.location_plan_sha256)
    context = load_context(plan, args.selection, args.selection_sha256, prepared)
    c, rc, legacy = context["common"], context["rc"], context["legacy"]
    selection, freeze, manifest, inventory = (context[name] for name in ("selection", "freeze", "manifest", "inventory"))
    completion, rows, evidence = (context[name] for name in ("completion", "rows", "evidence"))
    locations = loc.Locations(args.location_plan, args.location_plan_sha256, prepared, selection=selection,
        selection_sha=args.selection_sha256, scope_sha=rc.scope_definition(selection), original=context["original"],
        inventory=inventory, base=evidence, freeze=freeze)
    fit_controller, contracts = context["fit_controller"], context["contracts"]
    resolutions = fit_controller.read_resolution_review(args.resolution_review, args.resolution_review_sha256, freeze)
    numerical = legacy.numerical_inventory(c, rc, selection, evidence, args.original_numerical_resolution, args.original_numerical_resolution_sha256)
    for identity in plan["entry_locations"]:
        proof = numerical[identity]
        if proof["status"] != "pending_original_numerical_reproduction":
            locations.resolution(identity, proof)
    forbidden = [Path(text) for text in {*freeze["paths"].values(), *selection["paths"].values(), *plan["legacy_code_roots"].values()}]
    forbidden += [args.location_plan, args.preparation_receipt, Path(__file__).absolute().parent, *locations.pins.files]
    for row in plan["entry_locations"].values():
        forbidden += [Path(row["historical_reproduction_root"]), Path(row["capture_root"])]
    legacy.prepare_output(c, args.output, args.selection, args.selection_sha256, forbidden)
    original = context["original"]
    c.verify_original_source(Path(freeze["paths"]["source"]), original)
    c.require(c.sha(Path(freeze["paths"]["matched"])) == original["matched_sha256"], "matched input bytes differ")
    environment_dir = args.output / "passes" / ("environment." + uuid.uuid4().hex)
    environment_dir.mkdir()
    preflight = c.read_json(Path(freeze["paths"]["preflight"]) / "manifest.json", freeze["preflight_manifest_sha256"])
    c.verify_environment(Path(freeze["paths"]["source"]), original, args.python, preflight, environment_dir)
    args.environment_artifacts = legacy.artifact_inventory(c, environment_dir, args.output)
    import arviz as az
    import numpy as np
    comparators = rc.original_comparators(Path(freeze["paths"]["source"]), np, az)

    def final_gates() -> None:
        locations.recheck()
        rc.load_selection(args.selection, args.selection_sha256, context["original_code"])
        c.verify_original_source(Path(freeze["paths"]["source"]), original)
        c.require(c.sha(Path(freeze["paths"]["matched"])) == original["matched_sha256"], "matched input changed before seal")

    controller = controller_class(legacy, locations)(args, c, rc, selection, freeze, manifest, inventory, completion, rows,
        numerical, fit_controller, contracts, comparators, resolutions, final_gates=final_gates)
    result = controller.run()
    final_gates()
    return result
