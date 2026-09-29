"""Serial selective correction fits with real input, ownership and pilot gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Read the explicitly byte-pinned freeze before importing mutable support.
if __name__ == "__main__":
    _bootstrap = argparse.ArgumentParser(add_help=False)
    _bootstrap.add_argument("--freeze", type=Path, required=True)
    _bootstrap.add_argument("--freeze-sha256", required=True)
    _initial, _unknown = _bootstrap.parse_known_args()
    if hashlib.sha256(_initial.freeze.read_bytes()).hexdigest() != _initial.freeze_sha256:
        raise RuntimeError("correction freeze byte hash differs")
    _document = json.loads(_initial.freeze.read_text())
    _support = Path(__file__).absolute().with_name("fit_common.py")
    if hashlib.sha256(_support.read_bytes()).hexdigest() != _document["implementation_source_sha256"]["fit_common.py"]:
        raise RuntimeError("controller support byte pin differs")
    sys.path.insert(0, str(_support.parent))

import fit_common as common  # noqa: E402 - explicitly byte-verified support bootstrap

sys.dont_write_bytecode = True


def validate_snapshot(snapshot: dict[str, Any], entry: dict[str, Any], definition_sha: str) -> dict[str, Any] | None:
    """Accept only an exact immutable witness and independently checked source."""
    common.require(snapshot["input_witness_sha256"] == entry["input_witness_sha256"]
                   and snapshot["definition_content_sha256"] == definition_sha
                   and snapshot["original_cell_id"] == entry["original_cell_id"], "source snapshot binds different inputs")
    evidence = snapshot["source_evidence"]
    if snapshot["original_claim_active"] or evidence is None:
        return None
    return evidence


def read_resolution_review(path: Path | None, expected: str | None, freeze: dict[str, Any]) -> dict[str, Any]:
    """Bind append-only snapshots of original outcomes that were pending at freeze."""
    common.require((path is None) == (expected is None), "resolution review path and hash must be paired")
    if path is None:
        return {}
    review = common.read_json(path, expected)
    common.require(review["status"] == "original_finished_snapshots_reviewed"
                   and review["definition_content_sha256"] == freeze["definition_content_sha256"]
                   and review["input_inventory_sha256"] == freeze["input_inventory_sha256"],
                   "fresh original-resolution review required")
    return review["snapshots"]


def prepare_output(output: Path, manifest_source: Path, manifest_sha: str, forbidden: list[Path]) -> None:
    """Create a new run or accept only a matching immutable manifest on resume."""
    common.safe(output)
    manifest = common.read_json(manifest_source, manifest_sha)
    common.require(output.parent.is_dir() and all(not output.is_relative_to(root) and not root.is_relative_to(output)
                                                for root in forbidden), "output overlaps immutable source/input roots")
    if not output.exists():
        output.mkdir()
        for name in ("cells", "claims", "attempts", "passes"):
            (output / name).mkdir()
        common.copy_new(manifest_source, output / "manifest.json", manifest_sha)
    else:
        common.require(common.read_json(output / "manifest.json", manifest_sha) == manifest, "resume manifest differs")
    allowed = {"manifest.json", "cells", "claims", "attempts", "passes", "controller.claim.json"}
    common.require({path.name for path in output.iterdir()} <= allowed, "unrecognized run root artifacts")
    for path in output.rglob("*"):
        common.safe(path)
        common.require(path.is_file() or path.is_dir(), "unsafe run artifact")
    for name in ("cells", "claims", "attempts", "passes"):
        common.require((output / name).is_dir(), "missing run namespace")


def verify_record(path: Path, manifest_sha: str, identity: str) -> dict[str, Any]:
    """Recheck a recorded outcome, including failures and all child/orphan bytes."""
    value = common.read_json(path)
    common.require(value["original_cell_id"] == identity and value["corrected_manifest_sha256"] == manifest_sha
                   and value["operation"] in {"reuse_original_outcome", "fit_corrected_inputs", "retain_corrected_input_failure"},
                   "recorded correction outcome identity differs")
    common.verify_files(path.parent.parent, value["artifacts"])
    return value


def capture_child(argv: list[str], attempt: Path, environment: dict[str, str],
                  invoke: Any = subprocess.run) -> dict[str, Any]:
    """Retain actual rc/logs/timing; nonzero runs cannot become successful cells.

    ``invoke`` is injectable for synthetic tests only. Actual execution uses a
    list argv and no shell. All files are exclusive; failed logs remain in the
    owned attempt and prevent automatic refitting on resume.
    """
    started, monotonic = datetime.now(UTC).isoformat(), time.monotonic()
    rc, failure = None, None
    with (attempt / "stdout.log").open("xb") as stdout, (attempt / "stderr.log").open("xb") as stderr:
        try:
            rc = invoke(argv, stdout=stdout, stderr=stderr, env=environment, cwd=attempt, check=False).returncode
        except BaseException as error:
            failure = {"type": f"{type(error).__module__}.{type(error).__qualname__}", "message": str(error)}
        finally:
            for stream in (stdout, stderr):
                stream.flush()
                os.fsync(stream.fileno())
    receipt = common.seal({"operation": "isolated_original_cell_child", "argv": argv,
                           "started_at_utc": started, "finished_at_utc": datetime.now(UTC).isoformat(),
                           "wall_seconds": time.monotonic() - monotonic, "exit_code": rc, "launch_error": failure,
                           "stdout": common.file_binding(attempt / "stdout.log"),
                           "stderr": common.file_binding(attempt / "stderr.log"),
                           "numeric_thread_environment": {name: environment[name] for name in (
                               "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS")}})
    common.write_new(attempt / "invocation.json", receipt)
    common.require(rc == 0 and failure is None, "child did not exit zero; retained owned attempt requires explicit review")
    return receipt


def attempt_artifacts(attempt: Path, output: Path) -> dict[str, Any]:
    """Inventory every new fit log, cell, trace and orphan without gate claims."""
    result = {}
    for path in sorted(attempt.rglob("*")):
        common.safe(path)
        common.require(path.is_file() or path.is_dir(), "unsafe owned attempt artifact")
        if path.is_file():
            common.require(not path.name.startswith(".fit-pending-"), "residual publication prevents outcome seal")
            result[str(path.relative_to(output))] = common.file_binding(path)
    return result


def validate_pilot_review(review: dict[str, Any], manifest: dict[str, Any], manifest_sha: str,
                          output: Path) -> None:
    """Require an actual owner review of every retained full-budget pilot outcome."""
    common.require(review["status"] == "full_budget_pilot_reviewed"
                   and review["corrected_manifest_sha256"] == manifest_sha
                   and review["approve_remaining_selective_fits"] is True
                   and review["original_full_budget_retained"] is True
                   and review["all_failures_retained_and_reviewed"] is True
                   and set(review["pilot_outcomes"]) == set(manifest["pilot_cells"]),
                   "actual full-budget pilot review must authorize the remaining grid")
    for identity, binding in review["pilot_outcomes"].items():
        path = output / "cells" / f"{identity}.json"
        value = verify_record(path, manifest_sha, identity)
        common.require(common.file_binding(path) == binding and value["operation"] == "fit_corrected_inputs"
                       and value["fit_dispatched"] is True, "pilot review does not bind an actual changed-input fit")


class Controller:
    """Process a frozen whole-grid inventory serially without assumed reuse counts."""

    def __init__(self, args: argparse.Namespace, freeze: dict[str, Any], manifest: dict[str, Any],
                 inventory: dict[str, Any], completion: dict[str, Any], contracts: Any,
                 resolutions: dict[str, Any] | None = None, invoke: Any = subprocess.run) -> None:
        self.args, self.freeze, self.manifest, self.inventory, self.completion = args, freeze, manifest, inventory, completion
        self.contracts, self.resolutions, self.invoke = contracts, resolutions or {}, invoke
        self.paths = {key: Path(value) for key, value in freeze["paths"].items()}

    def current(self, entry: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None, Any]:
        """Recompute the pure decision, then impose a fresh original-owner barrier."""
        path = common.below(self.paths["witness_root"], entry["input_witness_path"])
        document = common.read_json(path, entry["input_witness_sha256"])
        common.require(document["definition_content_sha256"] == self.freeze["definition_content_sha256"], "input witness correction differs")
        common.verify_witness_proofs(path.parent, document, self.contracts)
        override = self.resolutions.get(entry["original_cell_id"])
        snapshot_path = common.below(self.paths["witness_root"], (entry if override is None else override)["snapshot_path"])
        snapshot_sha = (entry if override is None else override)["snapshot_sha256"]
        snapshot = common.read_json(snapshot_path, snapshot_sha)
        common.verify_files(path.parent, snapshot["artifacts"])
        evidence = validate_snapshot(snapshot, entry, self.freeze["definition_content_sha256"])
        if evidence is not None:
            common.require(evidence["verification_receipt_sha256"] in {binding["sha256"] for binding in snapshot["artifacts"].values()},
                           "standalone actual source-verification receipt is not bound")
        witness = common.witness_from_json(self.contracts, document, evidence)
        decision = self.contracts.classify(witness)
        common.require(decision["original_cell_id"] == entry["original_cell_id"] and witness.model == entry["model"], "decision cell/model differs")
        recorded = snapshot["decision"]
        common.require(recorded == decision, "snapshot decision is not the exact pinned classification")
        old = common.verify_original_outcome(self.paths["original_run"], entry["original_cell_id"], evidence)
        if decision["action"] in common.FIT_ACTIONS | {"reuse_original_outcome"} and old is None:
            decision = {**decision, "action": "await_original_owner_or_outcome", "fit_dispatched": False}
        return document, decision, old, witness

    def record(self, entry: dict[str, Any]) -> dict[str, Any]:
        """Reuse exact old success/failure, retain input failure or fit changed inputs."""
        identity, output = entry["original_cell_id"], self.args.output
        path = output / "cells" / f"{identity}.json"
        if path.exists():
            recorded = verify_record(path, self.args.manifest_sha256, identity)
            common.require(recorded["input_witness_sha256"] == entry["input_witness_sha256"], "resume input witness differs")
            witness_path = common.below(self.paths["witness_root"], entry["input_witness_path"])
            common.verify_witness_proofs(witness_path.parent, common.read_json(witness_path, entry["input_witness_sha256"]), self.contracts)
            if recorded["source_evidence"] is not None:
                common.require(common.verify_original_outcome(self.paths["original_run"], identity, recorded["source_evidence"]) is not None,
                               "recorded original owner or source bytes differ")
            return {"original_cell_id": identity, "status": "verified_existing_outcome", "record_sha256": common.sha(path)}
        with common.Claim(output / "claims" / f"{identity}.json", self.args.manifest_sha256):
            _, decision, old, witness = self.current(entry)
            action = decision["action"]
            if action in {"await_original_owner_or_outcome", "await_original_outcome", "unresolved"}:
                return {"original_cell_id": identity, "status": action, "fit_dispatched": False}
            record: dict[str, Any] = {"schema_version": 1, "original_cell_id": identity,
                       "evidence_status": "post_hoc_rank_conditioned_correction_after_original_failures_known",
                       "corrected_manifest_sha256": self.args.manifest_sha256, "correction_freeze_sha256": self.args.freeze_sha256,
                       "definition_content_sha256": self.freeze["definition_content_sha256"],
                       "input_witness_path": entry["input_witness_path"], "input_witness_sha256": entry["input_witness_sha256"],
                       "source_evidence": decision["source_evidence"], "decision": decision,
                       "generator_contexts": {name: list(row) for name, row in witness.generator_contexts.items()},
                       "original_seed_namespace": witness.corrected_seeds,
                       "fit_dispatched": False, "artifacts": {}, "programme_complete": False,
                       "reporting_certified": False, "release_certified": False}
            if action == "reuse_original_outcome":
                common.require(old is not None, "pending original outcome cannot be reusable")
                record.update(operation="reuse_original_outcome", scientific_status=old["status"],
                              original_reference={"logical_root": "original_extension_run", "path": f"cells/{identity}.json",
                                                  "sha256": witness.original_evidence.cell_byte_sha256,
                                                  "cell_content_sha256": witness.original_evidence.cell_content_sha256},
                              newly_executed_fit=False, fit_seconds=0.0)
            elif action == "retain_input_failure":
                record.update(operation="retain_corrected_input_failure", scientific_status="not_fit_input_failure",
                              original_reference=None, original_outcome_pending=old is None,
                              failure_contexts=decision["generator_failures"], newly_executed_fit=False, fit_seconds=0.0)
            elif action in common.FIT_ACTIONS:
                common.require(old is not None and witness.original_evidence is not None, "pending original cannot be corrected-fit-ready")
                if self.args.phase == "account" or self.args.phase == "pilot" and identity not in self.manifest["pilot_cells"]:
                    return {"original_cell_id": identity, "status": "changed_inputs_waiting_for_authorized_phase", "fit_dispatched": False}
                attempt = output / "attempts" / identity
                common.require(not attempt.exists(), "owned prior attempt exists; review rather than automatically refit")
                attempt.mkdir()
                request = common.seal({"original_cell_id": identity, "entry": entry,
                          "source_evidence": decision["source_evidence"], "action": action,
                          "freeze_path": str(self.args.freeze), "freeze_sha256": self.args.freeze_sha256,
                          "manifest_path": str(self.args.manifest), "manifest_sha256": self.args.manifest_sha256,
                          "attempt_path": str(attempt), "locked_python": str(self.args.python),
                          "implementation_source_sha256": self.freeze["implementation_source_sha256"]})
                common.write_new(attempt / "request.json", request)
                script = Path(__file__).absolute().with_name("fit_child.py")
                common.require(common.sha(script) == self.freeze["implementation_source_sha256"]["fit_child.py"], "child source differs before spawn")
                argv = [str(self.args.python), "-I", "-B", str(script), "--request", str(attempt / "request.json"),
                        "--request-sha256", common.sha(attempt / "request.json")]
                environment = dict(os.environ)
                for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
                    environment[name] = "1"
                environment["PYTHONDONTWRITEBYTECODE"] = "1"
                invocation = capture_child(argv, attempt, environment, self.invoke)
                child = common.read_json(attempt / "child_receipt.json")
                cell_path = attempt / "cells" / f"{identity}.json"
                cell = common.read_json(cell_path, child["cell"]["sha256"], field="cell_content_sha256")
                common.require(child["status"] == "original_cell_delegated_with_verified_corrected_inputs"
                               and child["original_cell_id"] == cell["cell_id"] == identity
                               and child["corrected_manifest_sha256"] == self.args.manifest_sha256
                               and child["scientific_status"] == cell["status"]
                               and child["action"] == action and child["input_witness_sha256"] == entry["input_witness_sha256"]
                               and child["original_seed_namespace"] == witness.corrected_seeds,
                               "successful child receipt does not bind the actual corrected cell")
                common.require(common.verify_original_outcome(self.paths["original_run"], identity, decision["source_evidence"]) is not None,
                               "original owner/source changed during child")
                record.update(operation="fit_corrected_inputs", scientific_status=cell["status"],
                              fit_dispatched=True, newly_executed_fit=True, fit_seconds=cell["seconds"],
                              child_wall_seconds=invocation["wall_seconds"], child_exit_code=0,
                              corrected_cell={"logical_root": "corrected_fit_run", "path": str(cell_path.relative_to(output)),
                                              "sha256": common.sha(cell_path), "cell_content_sha256": cell["cell_content_sha256"]},
                              child_receipt_path=str((attempt / "child_receipt.json").relative_to(output)),
                              invocation_path=str((attempt / "invocation.json").relative_to(output)),
                              observations_path=str((attempt / "observations.json").relative_to(output)),
                              artifacts=attempt_artifacts(attempt, output))
            else:
                common.require(False, f"unrecognized action: {action}")
            common.write_new(path, common.seal(record))
            verify_record(path, self.args.manifest_sha256, identity)
            return {"original_cell_id": identity, "status": "outcome_retained", "operation": record["operation"],
                    "scientific_status": record["scientific_status"], "record_sha256": common.sha(path),
                    "fit_dispatched": record["fit_dispatched"]}

    def run(self) -> dict[str, Any]:
        """Account an authorized pass; remaining fits require a real pilot review."""
        if self.args.phase == "remaining":
            common.require(self.args.pilot_review is not None and self.args.pilot_review_sha256 is not None,
                           "remaining fits require an actual explicit pilot review and byte hash")
            validate_pilot_review(common.read_json(self.args.pilot_review, self.args.pilot_review_sha256),
                                  self.manifest, self.args.manifest_sha256, self.args.output)
        rows = self.inventory["entries"]
        if self.args.phase == "pilot":
            rows = [entry for entry in rows if entry["original_cell_id"] in self.manifest["pilot_cells"]]
        results = []
        with common.Claim(self.args.output / "controller.claim.json", self.args.manifest_sha256):
            for entry in rows:
                results.append(self.record(entry))
                print(json.dumps(results[-1], sort_keys=True), flush=True)
                if self.args.limit is not None and len(results) >= self.args.limit:
                    break
            records = {path.stem: common.sha(path) for path in sorted((self.args.output / "cells").glob("*.json"))}
            expected = {row["original_cell_id"] for row in self.inventory["entries"]}
            common.require(set(records) <= expected, "unexpected logical output cell")
            value = common.seal({"schema_version": 1, "phase": self.args.phase,
                                 "corrected_manifest_sha256": self.args.manifest_sha256,
                                 "status": "all_logical_outcomes_accounted" if set(records) == expected else "partial_selective_fit_accounting",
                                 "scheduled_logical_cells": 1625, "retained_logical_outcomes": len(records),
                                 "current_pass": results, "record_sha256": records,
                                 "all_fits_numerically_verified": False, "programme_complete": False,
                                 "reporting_certified": False, "release_certified": False,
                                 "pending_gates": ["mixed_lineage_deep_verification", "analysis_reporting_qa", "selected_reproduction", "package_restore_replay"]})
            common.write_new(self.args.output / "passes" / f"{uuid.uuid4().hex}.json", value)
            return value


def main() -> None:
    """Read actual frozen inputs and launch at most the reviewed serial workload."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("freeze", "manifest", "output", "python"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    for name in ("freeze-sha256", "manifest-sha256"):
        parser.add_argument(f"--{name}", required=True)
    parser.add_argument("--phase", choices=("account", "pilot", "remaining"), required=True)
    parser.add_argument("--limit", type=int)
    for name in ("pilot-review", "resolution-review"):
        parser.add_argument(f"--{name}", type=Path)
        parser.add_argument(f"--{name}-sha256")
    args = parser.parse_args()
    common.require(args.limit is None or args.limit > 0, "positive pass limit required")
    for name in ("freeze", "manifest", "output", "pilot_review", "resolution_review"):
        if getattr(args, name) is not None:
            common.safe(getattr(args, name))
    supplied = args.python.absolute()
    common.require(supplied.is_file() and ".." not in supplied.parts, "explicit locked Python file required")
    args.python = common.safe(supplied.resolve(strict=True))
    common.validate_runtime(args.python)
    own = Path(__file__).absolute().parent
    freeze, manifest, inventory, completion = common.load_gates(args.freeze, args.freeze_sha256,
                                                               args.manifest, args.manifest_sha256, own)
    paths = {key: Path(value) for key, value in freeze["paths"].items()}
    common.verify_original_source(paths["source"], common.read_original_manifest(paths["original_run"]))
    common.require(common.sha(paths["matched"]) == common.read_original_manifest(paths["original_run"])["matched_sha256"],
                   "frozen matched bytes differ")
    contracts = common.module_from_pin(paths["contracts"], common.CONTRACTS_SHA, "_correction_fit_contracts_controller")
    resolutions = read_resolution_review(args.resolution_review, args.resolution_review_sha256, freeze)
    prepare_output(args.output, args.manifest, args.manifest_sha256,
                   [own, *paths.values(), Path(freeze["arithmetic_accounting"]["path"]).parent])
    value = Controller(args, freeze, manifest, inventory, completion, contracts, resolutions).run()
    common.load_gates(args.freeze, args.freeze_sha256, args.manifest, args.manifest_sha256, own)
    common.verify_original_source(paths["source"], common.read_original_manifest(paths["original_run"]))
    common.require(common.sha(paths["matched"]) == common.read_original_manifest(paths["original_run"])["matched_sha256"],
                   "original matched bytes changed during controller pass")
    print(json.dumps({"status": value["status"], "retained_logical_outcomes": value["retained_logical_outcomes"],
                      "programme_complete": False}, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
