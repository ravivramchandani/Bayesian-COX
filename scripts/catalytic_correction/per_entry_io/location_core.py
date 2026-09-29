"""Explicit per-entry ORIGINAL reproduction I/O, without scientific promotion.

Only externally supplied root reviews can authorise a location. This module
does not select identities, make reviews, dispatch work, import science, or
compare numerical arrays. Its immutable legacy pins are distinct from the
new adapter pins. Historical paths are resolved for I/O, never rewritten.
"""

from __future__ import annotations

import hashlib
import importlib.util
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True
OWN = (
    "location_core.py", "capture_at_location.py", "capture_original_at_location.py",
    "selected_at_locations.py", "run_selected_at_locations.py", "receiving_at_locations.py",
    "verify_restored_at_locations.py", "verification_io.py",
)
IO_SHA = "389c09c0b4f151adf754d20b3c21b2cdd0fa6809bcc4cd78dda470739d2ea3b8"
LEGACY = {
    "selected": {
        "reproduction_core.py": "fa43d4c75f231a59f12adb73b312627744b6c40dd0a97c002016ed4cba597cb5",
        "run_reproduction.py": "86eed8bd3af2f5ddab9b1bf354e7251518cfb64932da778d05d63a937209829c",
        "terminal_replay_child.py": "830e866d38eb65f9742cb9e7e48212f532ee1d1bfd9eeb7791ca89dbe3dacc61",
    },
    "receiving": {
        "receiving_core.py": "9da62601b7f482be97f62de30566fe52eb916fa59d09995fe13654f700e20f3f",
        "verify_restored_reproduction.py": "9387aae83e348515999843963ace0acba0cacef2501fbdacbb0cef85bd5ad33e",
    },
    "capture": {
        "producer_capture.py": "c8c10daace6f44ebcfd0305cbd48954d1db4afedae442103b69d736053ffb95e",
        "capture_original_producer.py": "71ce704199512379024a53b5de3add15ca74be5ea73dc093e2ae4685d5af35e3",
        "verification_io.py": IO_SHA,
    },
}
LEGACY_RECEIPTS = {
    "selected": "43f2dba209a4d068df7122a3be956d295f7810601272b271fa996ad5a27aa95b",
    "receiving": "fe0662adacbf29bc356d7c19f7abd40b2b6304cb9f683673fce1e7ae39f1e1ba",
    "capture": "2a8530662d20936ac9f84a93db83b558abf6c1651a4df5039925cc616df72ea1",
}
PLAN_STATUS = "root_reviewed_original_numerical_output_locations"
AUDIT_STATUS = "original_numerical_producer_availability_reviewed"
SCOPE_RULE = "sorted_unique(original_plan_repeat1_fold1_92_union_frozen_full_budget_pilots)"
CAPTURE_STATUS = "original_missing_producer_execution_captured_root_review_pending"

_path = Path(__file__).absolute().with_name("verification_io.py")
if hashlib.sha256(_path.read_bytes()).hexdigest() != IO_SHA:
    raise RuntimeError("unchanged I/O bytes differ")
_spec = importlib.util.spec_from_file_location("_per_entry_location_io", _path)
if _spec is None or _spec.loader is None:
    raise RuntimeError("I/O loader unavailable")
io = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(io)


def import_pin(path: Path, expected: str, name: str) -> Any:
    """Load one explicitly pinned stdlib helper, never a scientific package."""
    io.safe(path)
    io.require(io.sha(path) == expected and name not in sys.modules, "helper pin/namespace differs")
    spec = importlib.util.spec_from_file_location(name, path)
    io.require(spec is not None and spec.loader is not None, "helper loader unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    io.require(io.sha(path) == expected, "helper changed during import")
    return module


def preparation(path: Path, expected: str) -> dict[str, Any]:
    """Pin this separately named adapter; never claim the old source map."""
    value = io.read(path, expected)
    io.require(value["status"] == "original_reproduction_per_entry_io_adapter_prepared"
               and value["actual_science_executed"] is False
               and value["actual_subset_or_reviews_created"] is False
               and set(value["implementation_source_sha256"]) == set(OWN), "adapter preparation differs")
    root = Path(__file__).absolute().parent
    for name, pin in value["implementation_source_sha256"].items():
        io.require(io.sha(io.safe(root / name)) == pin, "new adapter source bytes differ")
    io.require(io.sha(path) == expected, "adapter preparation changed")
    return value


def original_order(original: dict[str, Any]) -> list[str]:
    """Use frozen manifest order for the unchanged --workers92 shard."""
    plan = original["plan"]
    io.require(isinstance(plan, list) and len(plan) == 1625, "full original plan required")
    ids = [row["cell_id"] for row in plan]
    io.require(len(ids) == len(set(ids)), "duplicate original identity")
    selected = []
    for identity in ids:
        match = re.fullmatch(r"[a-z0-9_.]+__[a-z0-9_.]+__r(\d{2})f(\d{2})__[a-z0-9_.]+__[a-z0-9_.]+", identity)
        io.require(match is not None, "original cell grammar differs")
        if tuple(map(int, match.groups())) == (1, 1):
            selected.append(identity)
    io.require(len(selected) == 92, "fixed original92 differs")
    return selected


def disjoint(path: Path, others: list[Path]) -> None:
    io.safe(path)
    io.require(all(not path.is_relative_to(other) and not other.is_relative_to(path) for other in others),
               "location overlaps immutable evidence or another entry/attempt")


def validate_plan(value: dict[str, Any], *, selection: dict[str, Any], selection_sha: str,
                  scope_sha: str, original: dict[str, Any], inventory: dict[str, Any],
                  base: dict[str, Any], choice: dict[str, Any], audit: dict[str, Any],
                  adapter_pins: dict[str, str], previous: dict[str, Any] | None = None) -> None:
    """Pure documentary/input checks; no approval or numerical proof is made."""
    order = original_order(original)
    io.require(selection["status"] == "reviewed_corrected_reproduction_selection"
               and selection["scope_rule"] == SCOPE_RULE
               and selection["original_selected_cells"] == sorted(order)
               and selection["selected_cells"] == sorted(set(order) | set(selection["pilot_cells"])),
               "frozen selected union differs")
    io.require(value["schema_version"] == 1 and value["status"] == PLAN_STATUS
               and value["reviewer_role"] == "root"
               and value["selection_sha256"] == selection_sha
               and value["scope_definition_sha256"] == scope_sha
               and value["original_manifest_sha256"] == selection["original_manifest_sha256"]
               and value["input_inventory_sha256"] == selection["input_inventory_sha256"]
               and value["definition_content_sha256"] == selection["definition_content_sha256"]
               and value["original_numerical_evidence_sha256"] == selection["original_numerical_evidence_sha256"]
               and value["io_adapter_source_sha256"] == adapter_pins
               and value["legacy_source_sha256"] == LEGACY, "location scope/source bindings differ")
    entries, chosen = value["entry_locations"], choice["selected_missing_producer_cell_ids"]
    io.require(choice["status"] == "root_selected_missing_original_producer_proofs"
               and choice["selection_sha256"] == selection_sha
               and choice["original_manifest_sha256"] == selection["original_manifest_sha256"]
               and choice["reason"] == "existing_actual_numerical_producer_proof_genuinely_unavailable"
               and choice["source_score_selection"] is False and choice["automatic_all92_rerun"] is False
               and isinstance(chosen, list) and chosen == sorted(set(chosen)) and chosen
               and isinstance(entries, dict) and set(entries) == set(chosen) <= set(order),
               "only the exact root-chosen unproven inherited subset may move")
    io.require(audit["status"] == AUDIT_STATUS and audit["reviewer_role"] == "root"
               and audit["selection_sha256"] == selection_sha
               and audit["original_numerical_evidence_sha256"] == selection["original_numerical_evidence_sha256"]
               and set(audit["entries"]) == set(entries), "actual missing-producer review differs")
    lookup = {entry["original_cell_id"]: entry for entry in inventory["entries"]}
    io.require(len(lookup) == len(inventory["entries"]) == 1625
               and sorted(base["entries"]) == sorted(order), "complete frozen input/base inventory required")
    paths: list[Path] = []
    for identity, row in entries.items():
        pending = base["entries"][identity]
        entry = lookup[identity]
        io.require(pending["status"] == "pending_original_numerical_reproduction"
                   and row["pending_base_entry_sha256"] == io.canonical(pending)
                   and row["original_cell_id"] == identity
                   and row["current_input_witness_sha256"] == entry["input_witness_sha256"]
                   and entry["decision"]["action"] == "reuse_original_outcome"
                   and entry["action"] == "reuse_original_outcome", "known evidence or noninherited input cannot move")
        report = audit["entries"][identity]
        io.require(report == {"status": "existing_actual_numerical_producer_proof_genuinely_unavailable",
            "pending_base_entry_sha256": row["pending_base_entry_sha256"],
            "current_input_witness_sha256": row["current_input_witness_sha256"],
            "default_original_reproduction_owner_finished": True}, "root missing-proof/default-owner facts required")
        io.require(row["producer_route"] == "official_fresh_refit"
                   and type(row["workers"]) is int and row["workers"] == 92
                   and type(row["original_plan_selected_index"]) is int
                   and row["original_plan_selected_index"] == order.index(identity), "original plan-order shard differs")
        for name in ("historical_reproduction_root", "capture_root"):
            path = io.safe(Path(row[name]))
            disjoint(path, paths)
            paths.append(path)
    if previous is None:
        io.require(value["previous_plan"] is None, "prior plan binding absent")
    else:
        io.require(previous["status"] == PLAN_STATUS and previous["reviewer_role"] == "root", "prior root review differs")
        for key in ("selection_sha256", "scope_definition_sha256", "original_manifest_sha256", "input_inventory_sha256",
                    "definition_content_sha256", "original_numerical_evidence_sha256", "io_adapter_source_sha256", "legacy_source_sha256"):
            io.require(previous[key] == value[key], "append-only plan changes its scientific/source scope")
        io.require(set(previous["entry_locations"]) <= set(entries)
                   and all(entries[key] == row for key, row in previous["entry_locations"].items()),
                   "append-only plan cannot replace an earlier identity/root/attempt")


class Locations:
    """One pinned plan shared by source capture, source controller and restore."""

    def __init__(self, path: Path, expected: str, prepared: dict[str, Any], *, selection: dict[str, Any],
                 selection_sha: str, scope_sha: str, original: dict[str, Any], inventory: dict[str, Any],
                 base: dict[str, Any], freeze: dict[str, Any], resolve: Callable[[str], Path] | None = None) -> None:
        self.resolve = resolve or (lambda text: io.safe(Path(text)))
        self.pins, self.path, self.sha = io.Pins(), io.safe(path), expected
        self.trees: dict[Path, dict[str, Any]] = {}
        self.value = self.pins.json(self.path, expected)
        io.require(self.resolve(self.value["historical_plan_path"]) == self.path, "plan file is not its explicit historical/resolved role")
        self.prepared, self.selection, self.freeze = prepared, selection, freeze
        self.adapter_pins = prepared["implementation_source_sha256"]
        io.require(self.bound(self.value["io_adapter_preparation"]) == prepared, "location plan pins another adapter preparation")
        own = Path(__file__).absolute().parent
        for name, pin in self.adapter_pins.items():
            self.pins.bind(own / name, pin)
        self.choice = self.bound(self.value["root_missing_producer_choice"])
        self.audit = self.bound(self.value["actual_producer_audit"])
        self.history: dict[str, dict[str, Any]] = {}
        self.introducing: dict[str, str] = {}
        node, node_sha = self.value, expected
        while True:
            io.require(node_sha not in self.history, "cyclic/duplicate prior location plan")
            self.history[node_sha] = node
            for identity in node["entry_locations"]:
                self.introducing[identity] = node_sha
            prior = node["previous_plan"]
            previous = None if prior is None else self.bound(prior)
            if prior is not None:
                io.require(previous["historical_plan_path"] == prior["path"],
                           "prior plan file is not its explicit historical role")
            validate_plan(node, selection=selection, selection_sha=selection_sha, scope_sha=scope_sha,
                          original=original, inventory=inventory, base=base,
                          choice=self.bound(node["root_missing_producer_choice"]),
                          audit=self.bound(node["actual_producer_audit"]), adapter_pins=self.adapter_pins, previous=previous)
            io.require(self.bound(node["io_adapter_preparation"]) == prepared, "prior location plan pins another adapter")
            if prior is None:
                break
            node, node_sha = previous, prior["sha256"]
        self.lookup = {entry["original_cell_id"]: entry for entry in inventory["entries"]}
        self.roots = self.value["legacy_code_roots"]
        io.require(set(self.roots) == set(LEGACY), "legacy helper roots differ")
        for role, mapping in LEGACY.items():
            root = self.resolve(self.roots[role])
            for name, pin in mapping.items():
                self.pins.bind(root / name, pin)
            self.pins.bind(root / "preparation_receipt.json", LEGACY_RECEIPTS[role])
        self.default = Path(selection["paths"]["original_reproduction"])
        immutable = [self.resolve(text) for text in {*freeze["paths"].values(), *selection["paths"].values(), *self.roots.values()}]
        immutable += [self.path, *self.pins.files, Path(__file__).absolute().parent]
        for identity, row in self.value["entry_locations"].items():
            witness = self.lookup[identity]
            self.pins.json(self.resolve(str(Path(freeze["paths"]["witness_root"]) / witness["input_witness_path"])),
                           row["current_input_witness_sha256"])
            for key in ("historical_reproduction_root", "capture_root"):
                actual = self.resolve(row[key])
                disjoint(actual, immutable)
        self.pins.recheck()

    def bound(self, item: dict[str, Any]) -> dict[str, Any]:
        io.require(set(item) == {"path", "sha256"}, "explicit reviewed path/SHA required")
        return self.pins.json(self.resolve(item["path"]), item["sha256"])

    def historical(self, identity: str) -> Path:
        row = self.value["entry_locations"].get(identity)
        return self.default if row is None else Path(row["historical_reproduction_root"])

    def actual(self, identity: str) -> Path:
        return self.resolve(str(self.historical(identity)))

    def metadata(self, identity: str) -> dict[str, Any] | None:
        row = self.value["entry_locations"].get(identity)
        if row is None:
            return None
        return {"original_cell_id": identity, "location_plan_sha256": self.introducing[identity],
                "historical_reproduction_root": row["historical_reproduction_root"],
                "capture_root": row["capture_root"], "original_plan_selected_index": row["original_plan_selected_index"],
                "pending_base_entry_sha256": row["pending_base_entry_sha256"],
                "current_input_witness_sha256": row["current_input_witness_sha256"],
                "io_adapter_source_sha256": self.adapter_pins}

    def owner_clear(self, identity: str) -> None:
        """An alternate path cannot hide a source/default/alternate cell owner."""
        for root in {self.resolve(str(self.default)), self.actual(identity), self.resolve(self.freeze["paths"]["original_run"])}:
            io.require(not io.safe(root / "claims" / (identity + ".json")).exists(), "original/default/alternate owner still active")

    def fresh(self, identity: str, output: Path, capture: Path) -> None:
        row = self.value["entry_locations"].get(identity)
        io.require(row is not None and output == self.actual(identity)
                   and capture == self.resolve(row["capture_root"]), "capture outputs are not the same declared entry roots")
        self.owner_clear(identity)
        for path in (output, capture):
            io.require(path.parent.is_dir() and not path.exists(), "fresh absent entry outputs required; no retry/resume")
        self.pins.recheck()

    def resolution(self, identity: str, evidence: dict[str, Any]) -> None:
        """Bind acquisition location; legacy gates still verify its real science."""
        meta = self.metadata(identity)
        if meta is None:
            io.require("reproduction_location" not in evidence, "undeclared alternate numerical acquisition")
            return
        io.require(evidence["status"] == "verified_original_numerical_reproduction_evidence"
                   and evidence["reproduction_location"] == meta, "append-only acquisition location differs")
        self.owner_clear(identity)

    def external(self) -> dict[str, Any]:
        """Byte bindings for the plan/reviews/legacy code actually read."""
        return {str(path): {"sha256": digest, "bytes": path.stat().st_size} for path, digest in self.pins.files.items()}

    def envelope(self) -> dict[str, Any]:
        return {"location_plan_path": self.value["historical_plan_path"], "location_plan_sha256": self.sha,
                "io_adapter_source_sha256": self.adapter_pins,
                "legacy_source_sha256": LEGACY, "selection_bytes_rewritten": False}

    def verify_envelope(self, value: dict[str, Any], identity: str) -> None:
        """Accept an exact retained earlier plan without rewriting its record."""
        node_sha = value.get("location_plan_sha256")
        io.require(node_sha in self.history, "record plan is not in retained append-only history")
        node = self.history[node_sha]
        io.require(value == {"location_plan_path": node["historical_plan_path"], "location_plan_sha256": node_sha,
            "io_adapter_source_sha256": self.adapter_pins, "legacy_source_sha256": LEGACY,
            "selection_bytes_rewritten": False}, "record I/O envelope differs from its actual retained plan")
        io.require(node["entry_locations"].get(identity) == self.value["entry_locations"].get(identity),
                   "record did not declare the same per-entry root")

    def recheck(self) -> None:
        self.pins.recheck()
        for root, expected in self.trees.items():
            io.safe(root)
            io.require(root.is_dir(), "retained tree root missing")
            files, directories = set(), []
            for path in sorted(root.rglob("*")):
                io.safe(path)
                if path.is_file():
                    files.add(str(path.relative_to(root)))
                elif path.is_dir():
                    directories.append(str(path.relative_to(root)))
                else:
                    io.require(False, "unsafe retained tree node")
            io.require(files == set(expected["artifacts"]) and directories == expected["directories"],
                       "retained tree inventory/empty directories changed")

    def retain_tree(self, root: Path) -> dict[str, Any]:
        found = full_tree(root)
        previous = self.trees.get(root)
        io.require(previous is None or previous == found, "retained tree changed during acquisition")
        for name, expected in found["artifacts"].items():
            self.pins.bind(root / name, expected["sha256"], size=expected["bytes"])
        self.trees[root] = found
        return found


def full_tree(root: Path) -> dict[str, Any]:
    """Retain all actual files and empty directories; never filter failed bytes."""
    io.safe(root)
    io.require(root.is_dir(), "retained full tree missing")
    artifacts, directories = {}, []
    for path in sorted(root.rglob("*")):
        io.safe(path)
        name = str(path.relative_to(root))
        if path.is_dir():
            directories.append(name)
        elif path.is_file():
            artifacts[name] = {"sha256": io.sha(path), "bytes": path.stat().st_size}
        else:
            io.require(False, "unsafe retained tree node")
    return {"artifacts": artifacts, "directories": directories}


def acquired(locations: Locations, identity: str, evidence: dict[str, Any]) -> dict[str, Any]:
    """Additional I/O/provenance checks; never replace the original verifier."""
    locations.resolution(identity, evidence)
    row = locations.value["entry_locations"].get(identity)
    if row is None:
        return {}
    capture = locations.resolve(row["capture_root"])
    receipt = locations.pins.json(capture / "capture_receipt.json", io.sha(capture / "capture_receipt.json"))
    meta = locations.metadata(identity)
    io.require(receipt["status"] == CAPTURE_STATUS and receipt["test_only_dependency_injection"] is False
               and receipt["original_cell_id"] == identity and receipt["reproduction_location"] == meta,
               "genuine completed per-entry capture required; root reviews still required separately")
    plan_used = receipt["actual_location_plan"]
    io.require(set(plan_used) == {"path", "sha256"} and plan_used["sha256"] in locations.history
               and locations.history[plan_used["sha256"]]["historical_plan_path"] == plan_used["path"]
               and locations.history[plan_used["sha256"]]["entry_locations"][identity] == row,
               "actual capture does not use an exact retained root-reviewed plan")
    io.inventory(capture, set(receipt["artifacts"]) | {"capture_receipt.json"}, set())
    for name, expected in receipt["artifacts"].items():
        locations.pins.bind(capture / name, expected["sha256"], size=expected["bytes"])
    request = locations.pins.json(capture / "request_capture.json", receipt["request_sha256"])
    io.require(request["location_plan"] == plan_used and request["original_cell_id"] == identity
               and request["reproduction_output"] == row["historical_reproduction_root"]
               and request["capture_output"] == row["capture_root"]
               and request["workers"] == 92 and request["worker"] == row["original_plan_selected_index"]
               and request["selected_reproduction_selection"]["sha256"] == receipt["selection_sha256"],
               "retained actual capture request uses another location/input/shard")
    invocation = locations.pins.json(capture / "invocation_record.json", receipt["artifacts"]["invocation_record.json"]["sha256"])
    official = locations.pins.json(capture / "official_comparison_record.json", receipt["artifacts"]["official_comparison_record.json"]["sha256"])
    attempt = locations.pins.json(capture / "numerical.attempt.json", receipt["artifacts"]["numerical.attempt.json"]["sha256"])
    argv = invocation["argv"]
    io.require(type(attempt["exit_code"]) is int and attempt["exit_code"] == 0 and attempt["launch_error"] is None
               and attempt["status"] == "actual_process_attempt_recorded"
               and attempt["operation"] == "unchanged119_original_official_fresh_refit_and_comparison"
               and attempt["test_only_dependency_injection"] is False
               and attempt["argv"] == argv and attempt["cwd"] == invocation["cwd"]
               and attempt["numeric_thread_environment"] == invocation["numeric_thread_environment"], "actual raw numerical attempt differs")
    for key, name in (("stdout", "numerical.stdout.txt"), ("stderr", "numerical.stderr.log")):
        io.require(attempt[key] == {"path": str(Path(row["capture_root"]) / name), "binding": receipt["artifacts"][name]}
                   and invocation[key] == official[key] == attempt[key], "actual raw numerical stream binding differs")
    for value in (invocation, official):
        io.require(type(value["exit_code"]) is int and value["exit_code"] == 0
                   and value["test_only_dependency_injection"] is False
                   and value["cached_comparison_only"] is False
                   and value["reproduction_output"] == row["historical_reproduction_root"]
                   and value["reproduction_location"] == meta and value["argv"] == argv
                   and value["actual_location_plan"] == plan_used
                   and value["workers"] == 92 and value["worker"] == row["original_plan_selected_index"]
                   and value["actual_attempt_record_sha256"] == receipt["artifacts"]["numerical.attempt.json"]["sha256"]
                   and value["fresh_output_reserved_empty_before_numerical_dispatch"] is True,
                   "actual producer/official location/index/attempt differs")
    io.require(argv.count("--output") == 1 and argv[argv.index("--output") + 1] == row["historical_reproduction_root"]
               and argv.count("--workers") == 1 and argv[argv.index("--workers") + 1] == "92"
               and argv.count("--worker") == 1 and argv[argv.index("--worker") + 1] == str(row["original_plan_selected_index"]),
               "recorded original worker output/index differs")
    review = locations.pins.json(locations.resolve(evidence["execution_review"]["path"]), evidence["execution_review"]["sha256"])
    producer = review["producer"]
    io.require(producer["route"] == "official_fresh_refit", "per-entry acquisition uses the unchanged official route")
    for role, name in (("invocation_record", "invocation_record.json"), ("official_comparison_record", "official_comparison_record.json")):
        io.require(producer[role]["path"] == str(Path(row["capture_root"]) / name)
                   and producer[role]["binding"] == receipt["artifacts"][name], "review points to another numerical capture")
    locations.recheck()
    return {"reproduction_location": meta,
            "retained_original_reproduction_tree": locations.retain_tree(locations.actual(identity)),
            "retained_original_capture_tree": locations.retain_tree(capture)}
