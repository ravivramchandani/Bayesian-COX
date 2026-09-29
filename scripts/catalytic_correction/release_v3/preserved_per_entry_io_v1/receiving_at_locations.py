"""Read-only relocated I/O adapter over the unchanged receiving-v1 verifier.

No numerical controller, fit or generator is invoked. Recorded historical
paths and source maps stay intact. Distinct entry trees resolve through the
unchanged trusted resolver. Default dependency loading may run only the
already required fresh environment check during a later real invocation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import location_core as loc


def verifier_class(legacy: Any, locations: Any) -> type:
    """Delegate every science predicate with an explicit historical I/O view."""

    class LocationReceivingVerifier(legacy.ReceivingVerifier):
        def inherited(self, identity: str, record: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
            proof = loc.acquired(locations, identity, self.numerical[identity])
            locations.verify_envelope(record["location_extension"], identity)
            loc.io.require(record["reproduction_location"] == locations.metadata(identity), "source I/O lineage differs")
            if proof:
                loc.io.require(record["retained_per_entry_trees"] == proof, "restored alternate trees omit/change retained bytes/directories")
            locations.owner_clear(identity)
            before_root, before_selection = self.repro_paths["original_reproduction"], self.selection
            self.repro_paths["original_reproduction"] = locations.actual(identity)
            # A local path-only view provides the exact historical producer root
            # to the unchanged method. No file, parsed original dict or scientific
            # selection/scope field is changed; restore both members in finally.
            self.selection = {**before_selection, "paths": {**before_selection["paths"],
                "original_reproduction": str(locations.historical(identity))}}
            try:
                result = super().inherited(identity, record, baseline)
                locations.recheck()
                locations.owner_clear(identity)
                return {**result, "reproduction_location": locations.metadata(identity)}
            finally:
                self.repro_paths["original_reproduction"] = before_root
                self.selection = before_selection

        def run(self, pass_value: dict[str, Any], output: Path) -> list[dict[str, Any]]:
            loc.io.require(pass_value["location_extension"] == locations.envelope(), "completed pass belongs to another location/source plan")
            for outcome in pass_value["outcomes"]:
                identity = outcome["original_cell_id"]
                path = self.root / "cells" / (identity + ".json")
                record = self.common.read_json(path, outcome["record_sha256"])
                locations.verify_envelope(record["location_extension"], identity)
                loc.io.require(record["reproduction_location"] == locations.metadata(identity), "completed record I/O provenance differs")
                if locations.metadata(identity) is not None:
                    loc.io.require(record["status"] == "reused_verified_original_numerical_reproduction", "alternate roots cannot replace changed/terminal routes")
            results = super().run(pass_value, output)
            locations.recheck()
            return results

    return LocationReceivingVerifier


def verify(bindings_path: Path, bindings_sha: str, location_path: Path, location_sha: str,
           output: Path, python: Path, prepared: dict[str, Any], *, dependencies: Any = None,
           test_only: bool = False) -> dict[str, Any]:
    """Fresh immutable receiving proof; injection can emit only synthetic proof."""
    io = loc.io
    io.require(dependencies is None or test_only, "injection requires explicit fictional mode")
    value = io.read(bindings_path, bindings_sha)
    plan = io.read(location_path, location_sha)
    io.require(value["receiving_source_sha256"] == loc.LEGACY["receiving"]
               and value["reproduction_source_sha256"] == loc.LEGACY["selected"]
               and value["location_extension"] == {"location_plan": {"historical_path": plan["historical_plan_path"], "sha256": location_sha},
                   "io_adapter_source_sha256": prepared["implementation_source_sha256"]}, "honest separate original/new source binding required")
    own = Path(__file__).absolute().parent
    loc.disjoint(io.safe(output), [own, bindings_path, location_path])
    legacy_root = Path(plan["legacy_code_roots"]["receiving"])
    # Resolve before import with the original resolver from its pinned source.
    # The receiving implementation itself is located by explicit binding,
    # separate from the immutable historical root text in the location plan.
    supplied_root = io.safe(Path(value["location_receiving_code"]))
    for name, pin in loc.LEGACY["receiving"].items():
        io.require(io.sha(supplied_root / name) == pin, "unchanged receiving source differs")
    io.require(io.sha(supplied_root / "preparation_receipt.json") == loc.LEGACY_RECEIPTS["receiving"], "unchanged receiving preparation differs")
    legacy = (dependencies.get("legacy") if dependencies is not None else None)
    if legacy is None:
        legacy = loc.import_pin(supplied_root / "receiving_core.py", loc.LEGACY["receiving"]["receiving_core.py"],
                                "_location_original_receiving")
    actual_runtime = legacy.runtime(python)
    legacy.require(value["schema_version"] == 1 and value["status"] == "corrected_selected_reproduction_receiving_bindings"
                   and set(value["reviews"]) <= {"original_resolution", "original_numerical_resolution", "pilot"}, "receiving scope differs")
    resolver = legacy.Resolver(value, output)
    io.require(resolver.resolve(str(legacy_root)) == supplied_root
               and resolver.resolve(plan["historical_plan_path"]) == location_path, "receiving role locations differ")
    for row in plan["entry_locations"].values():
        for key in ("historical_reproduction_root", "capture_root"):
            historical = Path(row[key])
            io.require((historical, resolver.resolve(row[key]), "directory") in resolver.maps,
                       "every alternate output/capture requires its exact explicit directory mapping")
    before = resolver.verify()
    io.require(output.parent.is_dir() and not output.exists(), "new external receiving output required; never resume")
    output.mkdir()
    (output / "cells").mkdir()
    io.write_new(output / "bindings_capture.json", io.seal({"bindings_path": str(bindings_path), "bindings_sha256": bindings_sha,
        "location_plan_sha256": location_sha, "actual_runtime": actual_runtime,
        "immutable_inventory": before, "no_controller_execute_or_resume": True, "test_only_dependency_injection": test_only}))
    try:
        loader = legacy.load_receiving_dependencies if dependencies is None else dependencies.get("load", legacy.load_receiving_dependencies)
        pack = loader(value, resolver, output, python)
        environment = pack.pop("environment")
        io.require(environment["report"]["status"] == "ok" and environment["report"]["package_count"] == 259
                   and type(environment["invocation"]["exit_code"]) is int and environment["invocation"]["exit_code"] == 0,
                   "actual fresh environment rc0 required")
        selection, common, rc = pack["selection"], pack["common"], pack["rc"]
        locations = loc.Locations(location_path, location_sha, prepared, selection=selection, selection_sha=value["selection_sha256"],
            scope_sha=rc.scope_definition(selection), original=common.read_original_manifest(resolver.resolve(pack["freeze"]["paths"]["original_run"])),
            inventory=pack["inventory"], base=pack["numerical"], freeze=pack["freeze"], resolve=resolver.resolve)
        verifier = verifier_class(legacy, locations)(value=value, resolver=resolver, **pack)
        root = verifier.root
        io.require(resolver.resolve(value["selection"]) == root / "selection.json" and not (root / "controller.claim.json").exists(),
                   "receiving selection/root owner differs")
        item = value["completed_pass"]
        io.require(set(item) == {"path", "sha256"} and legacy.relative(item["path"]).parent == Path("passes"), "completed pass namespace differs")
        pass_value = legacy.document(root / legacy.relative(item["path"]), item["sha256"])
        results = verifier.run(pass_value, output)
        after = resolver.verify()
        io.require(before == after and io.sha(bindings_path) == bindings_sha and io.sha(location_path) == location_sha,
                   "immutable evidence/bindings changed during receiving")
        locations.recheck()
        routes = {status: sum(result["route"] == status for result in results) for status in sorted(legacy.FINAL_STATUSES)}
        artifacts = {str(path.relative_to(output)): legacy.binding(path) for path in sorted(output.rglob("*")) if path.is_file()}
        receipt = io.seal({"schema_version": 1,
            "status": "synthetic_receiving_verification_fixture_passed" if test_only else "corrected_selected_reproduction_restored_read_only_verified",
            "bindings_sha256": bindings_sha, "selection_sha256": value["selection_sha256"], "completed_pass_sha256": item["sha256"],
            "scope_definition_sha256": rc.scope_definition(selection), "original_fixed_selected_cells": 92,
            "selected_union_cells": len(selection["selected_cells"]), "accounted_selected_cells": len(results), "selected_route_counts": routes,
            "receiving_source_sha256": loc.LEGACY["receiving"], "reproduction_source_sha256": loc.LEGACY["selected"],
            "io_adapter_source_sha256": prepared["implementation_source_sha256"], "location_extension": locations.envelope(),
            "v1_preparation_receipt_sha256": legacy.V1_RECEIPT_SHA, "v1_test_source_sha256": legacy.V1_TEST_SHA,
            "immutable_inventory_before": before, "immutable_inventory_after": after, "current_receiving_runtime": actual_runtime,
            "environment": environment, "artifacts": artifacts,
            "cells": {result["original_cell_id"]: legacy.binding(output / "cells" / (result["original_cell_id"] + ".json")) for result in results},
            "historical_absolute_paths_rewritten": False, "restored_evidence_modified": False, "new_numerical_fit_executed": False,
            "new_generator_recipe_executed": False, "test_only_dependency_injection": test_only,
            "verification_kind": "fresh_stored_scientific_sample_array_and_terminal_recipe_evidence_comparison",
            "actual_cli_exit_code_capture": "caller_must_capture_real_process_rc0_separately",
            "whole_1625_grid_numerically_reproduced": False, "programme_complete": False,
            "reporting_certified": False, "release_certified": False, "scientific_approval_created": False})
        io.write_new(output / "receipt.json", receipt)
        io.require(artifacts == {str(path.relative_to(output)): legacy.binding(path) for path in sorted(output.rglob("*"))
                                if path.is_file() and path != output / "receipt.json"}, "fresh output changed before publication")
        locations.recheck()
        io.require(before == resolver.verify(), "immutable evidence changed before receipt closeout")
        return receipt
    except BaseException as error:
        io.write_new(output / "failure.json", io.seal({"status": "receiving_verification_failed_retained", "bindings_sha256": bindings_sha,
            "location_plan_sha256": location_sha, "type": f"{type(error).__module__}.{type(error).__qualname__}", "message": str(error),
            "scientific_verification_certified": False, "no_resume_or_numerical_repair_attempted": True,
            "test_only_dependency_injection": test_only}))
        raise
