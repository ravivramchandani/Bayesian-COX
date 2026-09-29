"""Serial selected numerical reproduction with retained failures and pending evidence."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time
import uuid
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True
FIT_COMMON_SHA = "b17f378ba77ea3ae5ba25c836e963a1a0160556465b25745462f648e325d1f11"


def bootstrap(selection_path: Path, selection_sha: str) -> tuple[Any, Any]:
    """Pin helpers before loading them and before any scientific imports."""
    if hashlib.sha256(selection_path.read_bytes()).hexdigest() != selection_sha:
        raise ValueError("reproduction selection bytes differ")
    selection = json.loads(selection_path.read_text())
    common_path = Path(selection["paths"]["fit_code"]) / "fit_common.py"
    if not hashlib.sha256(common_path.read_bytes()).hexdigest() == selection["fit_implementation_source_sha256"]["fit_common.py"] == FIT_COMMON_SHA:
        raise ValueError("reproduction common source differs")
    if any(name == "src" or name.startswith("src.") for name in sys.modules):
        raise ValueError("controller has foreign scientific namespace")
    spec = importlib.util.spec_from_file_location("_reproduction_bound_common", common_path)
    if spec is None or spec.loader is None or spec.name in sys.modules:
        raise ValueError("reproduction support namespace occupied")
    common = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = common
    spec.loader.exec_module(common)
    own = Path(__file__).absolute().parent
    rc = common.module_from_pin(own / "reproduction_core.py", selection["implementation_source_sha256"]["reproduction_core.py"],
                                "_selected_reproduction_core")
    return common, rc


def artifact_inventory(common: Any, attempt: Path, output: Path) -> dict[str, Any]:
    """Retain every owned request/log/array/trace/cache/orphan, including failures."""
    found = {}
    for path in sorted(attempt.rglob("*")):
        common.safe(path)
        common.require(path.is_file() or path.is_dir(), "unsafe reproduction artifact")
        if path.is_file():
            common.require(not path.name.startswith(".fit-pending-"), "partial publication requires review")
            found[str(path.relative_to(output))] = common.file_binding(path)
    return found


def capture_child(common: Any, argv: list[str], attempt: Path, invoke: Any = subprocess.run) -> dict[str, Any]:
    """Retain nonzero launches/logs without converting them into numerical proof."""
    environment = dict(os.environ)
    environment.update({name: "1" for name in common.NUMERIC_THREAD_VARIABLES})
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    started, monotonic = datetime.now(UTC).isoformat(), time.monotonic()
    code, failure = None, None
    with (attempt / "stdout.log").open("xb") as stdout, (attempt / "stderr.log").open("xb") as stderr:
        try:
            code = invoke(argv, stdout=stdout, stderr=stderr, env=environment, cwd=attempt, check=False).returncode
        except BaseException as error:
            failure = {"type": f"{type(error).__module__}.{type(error).__qualname__}", "message": str(error)}
        finally:
            for stream in (stdout, stderr):
                stream.flush()
                os.fsync(stream.fileno())
    receipt = common.seal({"operation": "isolated_selected_reproduction_child", "argv": argv,
        "started_at_utc": started, "finished_at_utc": datetime.now(UTC).isoformat(), "wall_seconds": time.monotonic() - monotonic,
        "exit_code": code, "launch_error": failure, "stdout": common.file_binding(attempt / "stdout.log"),
        "stderr": common.file_binding(attempt / "stderr.log"), "numeric_thread_environment": {name: environment[name] for name in common.NUMERIC_THREAD_VARIABLES}})
    common.write_new(attempt / "invocation.json", receipt)
    common.require(code == 0 and failure is None, "child nonzero/launch failure retained; explicit review required")
    return receipt


def prepare_output(common: Any, output: Path, selection_path: Path, selection_sha: str, forbidden: list[Path]) -> None:
    """A separate write-once run; reject overlap, foreign files and partial attempts."""
    common.safe(output)
    common.require(output.parent.is_dir() and all(not output.is_relative_to(root) and not root.is_relative_to(output) for root in forbidden),
                   "reproduction output overlaps existing immutable/source/run evidence")
    if not output.exists():
        output.mkdir()
        for name in ("cells", "claims", "attempts", "passes"):
            (output / name).mkdir()
        common.copy_new(selection_path, output / "selection.json", selection_sha)
    else:
        common.read_json(output / "selection.json", selection_sha)
    common.require({path.name for path in output.iterdir()} <= {"selection.json", "cells", "claims", "attempts", "passes", "controller.claim.json"},
                   "unknown reproduction root artifact")
    for name in ("cells", "claims", "attempts", "passes"):
        common.require((output / name).is_dir(), "missing reproduction namespace")
    for path in output.rglob("*"):
        common.safe(path)
        common.require(path.is_file() or path.is_dir(), "unsafe reproduction checkpoint")


def verify_record(common: Any, path: Path, selection_sha: str, identity: str, output: Path) -> dict[str, Any]:
    """Verify existing actual proof or retained failure without rerunning it."""
    record = common.read_json(path)
    common.require(record["original_cell_id"] == identity and record["selection_sha256"] == selection_sha
                   and record["status"] in {"reused_verified_original_numerical_reproduction", "new_corrected_numerical_reproduction",
                                             "terminal_no_fit_recipe_replay", "retained_reproduction_failure"},
                   "recorded reproduction identity/status differs")
    common.verify_files(output, record["artifacts"])
    for name, binding in record["external_artifacts"].items():
        common.require(common.file_binding(common.safe(Path(name))) == binding, "external reproduction lineage changed")
    return record


def numerical_inventory(common: Any, rc: Any, selection: dict[str, Any], base: dict[str, Any],
                        path: Path | None, expected: str | None) -> dict[str, Any]:
    """Allow a later reviewed append-only acquisition for originally pending92."""
    common.require((path is None) == (expected is None), "numerical resolution path/hash must be paired")
    if path is None:
        return base["entries"]
    review = common.read_json(path, expected)
    common.require(review["status"] == "reviewed_original_numerical_evidence_resolution"
                   and review["scope_definition_sha256"] == rc.scope_definition(selection)
                   and review["original_manifest_sha256"] == common.ORIGINAL_MANIFEST_SHA
                   and set(review["entries"]) <= set(selection["original_selected_cells"]), "foreign numerical evidence resolution")
    for identity, value in review["entries"].items():
        common.require(base["entries"][identity]["status"] == "pending_original_numerical_reproduction"
                       and value["status"] == "verified_original_numerical_reproduction_evidence", "resolution cannot replace frozen evidence")
    return {**base["entries"], **review["entries"]}


class Controller:
    """Rerun changed selected fits; inherit only genuinely proved unchanged refits."""

    def __init__(self, args: Any, common: Any, rc: Any, selection: Any, freeze: Any, manifest: Any,
                 inventory: Any, completion: Any, rows: Any, numerical: Any, fit_controller: Any,
                 contracts: Any, comparators: Any, resolutions: Any, invoke: Any = subprocess.run,
                 final_gates: Any | None = None) -> None:
        self.args, self.common, self.rc, self.selection, self.freeze = args, common, rc, selection, freeze
        self.manifest, self.inventory, self.completion, self.rows, self.numerical = manifest, inventory, completion, rows, numerical
        self.fit_controller, self.contracts, self.comparators, self.invoke = fit_controller, contracts, comparators, invoke
        self.final_gates = final_gates
        self.paths = {key: Path(value) for key, value in freeze["paths"].items()}
        self.repro_paths = {key: Path(value) for key, value in selection["paths"].items()}
        fit_args = argparse.Namespace(freeze_sha256=selection["correction_freeze_sha256"],
            manifest_sha256=selection["corrected_manifest_sha256"], output=self.repro_paths["corrected_run"])
        self.input_controller = fit_controller.Controller(fit_args, freeze, manifest, inventory, completion, contracts, resolutions)

    def acquisition_binding(self, entry: dict[str, Any], decision: Any) -> dict[str, Any]:
        """Bind a later reviewed source snapshot without rewriting terminal proof."""
        c, identity = self.common, entry["original_cell_id"]
        override = self.input_controller.resolutions.get(identity)
        c.require(override is not None, "terminal later source acquisition requires explicit reviewed resolution")
        snapshot_path = c.below(self.paths["witness_root"], override["snapshot_path"])
        snapshot = c.read_json(snapshot_path, override["snapshot_sha256"])
        c.require(snapshot["source_evidence"] == decision["source_evidence"]
                  and snapshot["decision"] == decision
                  and snapshot["input_witness_sha256"] == entry["input_witness_sha256"]
                  and snapshot["definition_content_sha256"] == self.freeze["definition_content_sha256"],
                  "terminal finished-source acquisition binds a different immutable input")
        return {"snapshot_path": override["snapshot_path"], "snapshot_sha256": override["snapshot_sha256"],
                "current_reviewed_acquisition_decision": decision}

    def baseline(self, entry: dict[str, Any], decision: Any, witness: Any) -> tuple[Path, dict[str, Any]] | None:
        """Require a bound actual corrected outcome before a reproduction attempt."""
        c, identity = self.common, entry["original_cell_id"]
        root = self.repro_paths["corrected_run"]
        c.require(c.sha(root / "manifest.json") == self.selection["corrected_manifest_sha256"], "corrected run manifest differs")
        if c.safe(root / "claims" / f"{identity}.json").exists():
            return None
        path = c.safe(root / "cells" / f"{identity}.json")
        if not path.exists():
            return None
        envelope = self.fit_controller.verify_record(path, self.selection["corrected_manifest_sha256"], identity)
        c.require(envelope["correction_freeze_sha256"] == self.selection["correction_freeze_sha256"]
                  and envelope["definition_content_sha256"] == self.freeze["definition_content_sha256"]
                  and envelope["input_witness_sha256"] == entry["input_witness_sha256"]
                  and envelope["original_seed_namespace"] == witness.corrected_seeds,
                  "actual corrected outcome does not bind identical current inputs/seeds/source")
        if envelope["decision"] != decision or envelope["source_evidence"] != decision["source_evidence"]:
            c.require(envelope["operation"] == "retain_corrected_input_failure"
                      and envelope["original_outcome_pending"] is True
                      and envelope["source_evidence"] is None and decision["action"] == "retain_input_failure"
                      and decision["source_evidence"] is not None,
                      "only an immutable pending-origin terminal may use later original acquisition")
            pending_witness = replace(witness, original_evidence=None)
            c.require(envelope["decision"] == self.contracts.classify(pending_witness),
                      "pending-origin terminal envelope is not the exact original pinned classification")
            self.acquisition_binding(entry, decision)
        c.require(not (root / "claims" / f"{identity}.json").exists(), "corrected owner changed during read")
        return path, envelope

    def inherited(self, identity: str, baseline: dict[str, Any], evidence: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        """Recheck official old numerical proof and actual sample arrays, no new fit."""
        c, root = self.common, self.repro_paths["original_reproduction"]
        c.require(evidence["status"] == "verified_original_numerical_reproduction_evidence"
                  and evidence["original_cell_id"] == identity and evidence["owner_finished"] is True,
                  "actual original numerical reproduction owner evidence required")
        c.require(not c.safe(root / "claims" / f"{identity}.json").exists(), "original reproduction owner active")
        official_path = c.below(root, evidence["official_receipt_path"])
        c.require(str(official_path.relative_to(root)) == f"receipts/{identity}.json"
                  and c.file_binding(official_path) == evidence["official_receipt"], "official original reproduction receipt differs")
        official = json.loads(official_path.read_text())
        source_path = self.paths["original_run"] / "cells" / f"{identity}.json"
        refit_path = root / "cells" / f"{identity}.json"
        c.require(c.file_binding(source_path) == evidence["source_cell"] and c.file_binding(refit_path) == evidence["refit_cell"],
                  "official source/refit lineage differs")
        review_path = c.safe(Path(evidence["execution_review"]["path"]))
        review = c.read_json(review_path, evidence["execution_review"]["sha256"])
        c.require(review["status"] == "original_numerical_refit_and_trace_comparison_execution_reviewed"
                  and review["original_cell_id"] == identity and review["original_manifest_sha256"] == c.ORIGINAL_MANIFEST_SHA
                  and review["comparison_source_sha256"] == self.rc.COMPARISON_PINS
                  and review["source_cell"] == evidence["source_cell"] and review["refit_cell"] == evidence["refit_cell"]
                  and review["official_receipt"] == evidence["official_receipt"]
                  and review["original_full_budget"] is True and review["numerical_refit_executed"] is True
                  and review["owner_finished"] is True, "root-reviewed actual original numerical execution lineage required")
        original = c.read_original_manifest(self.paths["original_run"])
        preflight_manifest = c.read_json(self.paths["preflight"] / "manifest.json", self.freeze["preflight_manifest_sha256"])
        producer_external = self.rc.verify_old_numerical_producer(review["producer"], original,
            preflight_manifest["environment_verification"], self.paths["original_run"], root, original_cell_id=identity)
        result = self.rc.compare_cells(source_path, refit_path, self.paths["original_run"], root, self.comparators)
        c.require(official == {"cell_id": identity, "status": "scientific_match",
            "source_content_sha256": result["left_content_sha256"], "refit_content_sha256": result["right_content_sha256"],
            "trace_sample_arrays": "exact; timing/NetCDF metadata excluded"}, "official numerical receipt schema/identity differs")
        c.require(result["trace_inventory"] == evidence["trace_inventory"] == review["trace_inventory"],
                  "original numeric comparison trace/orphan inventory differs")
        c.require(baseline["operation"] == "reuse_original_outcome"
                  and baseline["original_reference"]["sha256"] == evidence["source_cell"]["sha256"], "inherited proof source is not exactly reused")
        c.require(c.file_binding(official_path) == evidence["official_receipt"]
                  and not (root / "claims" / f"{identity}.json").exists(), "original numerical owner/evidence changed")
        external = {**producer_external, **{str(path): c.file_binding(path) for path in (official_path, source_path, refit_path, review_path)}}
        for trace_root, inventory in zip((self.paths["original_run"], root), result["trace_inventory"], strict=True):
            external.update({str(c.below(trace_root, name)): binding for name, binding in {**inventory["referenced"], **inventory["unreferenced"]}.items()})
        return result, external

    def execute_changed(self, entry: Any, decision: Any, witness: Any, baseline: Any, attempt: Path) -> dict[str, Any]:
        """Use unchanged sealed fit_child, identical freeze and full original law."""
        c, identity = self.common, entry["original_cell_id"]
        if identity not in self.manifest["pilot_cells"]:
            c.require(self.args.pilot_review is not None and self.args.pilot_review_sha256 is not None,
                      "nonpilot corrected selected reproduction requires actual full-budget pilot review")
            self.fit_controller.validate_pilot_review(c.read_json(self.args.pilot_review, self.args.pilot_review_sha256),
                self.manifest, self.selection["corrected_manifest_sha256"], self.repro_paths["corrected_run"])
        request = c.seal({"original_cell_id": identity, "entry": entry, "source_evidence": decision["source_evidence"],
            "action": decision["action"], "freeze_path": str(self.repro_paths["freeze"]),
            "freeze_sha256": self.selection["correction_freeze_sha256"], "manifest_path": str(self.repro_paths["manifest"]),
            "manifest_sha256": self.selection["corrected_manifest_sha256"], "attempt_path": str(attempt),
            "locked_python": str(self.args.python), "implementation_source_sha256": self.rc.FIT_SOURCE_PINS})
        c.write_new(attempt / "request.json", request)
        script = self.repro_paths["fit_code"] / "fit_child.py"
        c.require(c.sha(script) == self.rc.FIT_SOURCE_PINS[script.name], "sealed reproduction fit child differs")
        capture_child(c, [str(self.args.python), "-I", "-B", str(script), "--request", str(attempt / "request.json"),
                         "--request-sha256", c.sha(attempt / "request.json")], attempt, self.invoke)
        child = c.read_json(attempt / "child_receipt.json")
        path = attempt / "cells" / f"{identity}.json"
        c.require(child["status"] == "original_cell_delegated_with_verified_corrected_inputs"
                  and child["original_cell_id"] == identity and child["corrected_manifest_sha256"] == self.selection["corrected_manifest_sha256"]
                  and child["input_witness_sha256"] == entry["input_witness_sha256"] and child["action"] == decision["action"]
                  and child["original_seed_namespace"] == witness.corrected_seeds and c.file_binding(path) == child["cell"],
                  "new numerical refit child receipt differs")
        old_path = c.below(self.repro_paths["corrected_run"], baseline["corrected_cell"]["path"])
        c.require(c.sha(old_path) == baseline["corrected_cell"]["sha256"], "corrected comparison source differs")
        comparison = self.rc.compare_cells(old_path, path, old_path.parent.parent, attempt, self.comparators)
        c.write_new(attempt / "comparison.json", c.seal(comparison))
        return {"status": "new_corrected_numerical_reproduction", "new_numerical_fit_executed": True,
                "scientific_status": child["scientific_status"], "comparison": comparison,
                "child_receipt_path": str((attempt / "child_receipt.json").relative_to(self.args.output))}

    def execute_terminal(self, entry: Any, baseline: Any, attempt: Path) -> dict[str, Any]:
        """A fresh no-fit child independently replays every applicable recipe."""
        c = self.common
        c.require(baseline["operation"] == "retain_corrected_input_failure", "terminal replay baseline is not input failure")
        request = c.seal({"original_cell_id": entry["original_cell_id"], "entry": entry, "attempt_path": str(attempt),
            "selection_path": str(self.args.selection), "selection_sha256": self.args.selection_sha256,
            "fit_code": str(self.repro_paths["fit_code"]), "locked_python": str(self.args.python),
            "fit_implementation_source_sha256": self.rc.FIT_SOURCE_PINS,
            "implementation_source_sha256": self.selection["implementation_source_sha256"]})
        c.write_new(attempt / "request.json", request)
        script = Path(__file__).absolute().with_name("terminal_replay_child.py")
        c.require(c.sha(script) == self.selection["implementation_source_sha256"][script.name], "terminal child source differs")
        capture_child(c, [str(self.args.python), "-I", "-B", str(script), "--request", str(attempt / "request.json"),
                         "--request-sha256", c.sha(attempt / "request.json")], attempt, self.invoke)
        result = c.read_json(attempt / "receipt.json")
        c.verify_files(attempt, result["artifacts"])
        chosen = self.rc.selected_contexts(self.rows, entry["original_cell_id"], entry["model"])
        c.require(result["status"] == "selected_terminal_full_recipe_independently_replayed_without_fit"
                  and result["selection_sha256"] == self.args.selection_sha256
                  and result["original_cell_id"] == entry["original_cell_id"]
                  and result["input_witness_sha256"] == entry["input_witness_sha256"]
                  and [row["context_id"] for row in result["contexts"]] == [row["context_id"] for row in chosen]
                  and result["no_model_optimizer_mcmc_prediction_or_score_executed"] is True
                  and result["new_numerical_fitted_cell_reproduction"] is False,
                  "actual scoped terminal replay receipt differs")
        return {"status": "terminal_no_fit_recipe_replay", "new_numerical_fit_executed": False,
                "scientific_status": "not_fit_input_failure", "terminal_receipt_path": str((attempt / "receipt.json").relative_to(self.args.output)),
                "scoped_generator_contexts": [row["context_id"] for row in chosen]}

    def record(self, entry: dict[str, Any]) -> dict[str, Any]:
        """No evidence-only audit can manufacture a completed numerical outcome."""
        c, identity, output = self.common, entry["original_cell_id"], self.args.output
        path = output / "cells" / f"{identity}.json"
        document, decision, old, witness = self.input_controller.current(entry)
        if decision["action"] in {"await_original_owner_or_outcome", "await_original_outcome", "unresolved"}:
            return {"original_cell_id": identity, "status": "pending_original_owner_or_input_proof"}
        if decision["action"] == "retain_input_failure" and decision["source_evidence"] is not None and old is None:
            return {"original_cell_id": identity, "status": "pending_original_owner_or_input_proof"}
        current = self.baseline(entry, decision, witness)
        if path.exists():
            record = verify_record(c, path, self.args.selection_sha256, identity, output)
            c.require(current is not None and c.sha(current[0]) == record["corrected_outcome_sha256"]
                      and record["input_witness_sha256"] == entry["input_witness_sha256"], "resumed reproduction source/input bytes changed")
            result = {"original_cell_id": identity, "status": record["status"], "record_sha256": c.sha(path)}
            if decision != record["current_input_decision"]:
                c.require(record["status"] == "terminal_no_fit_recipe_replay"
                          and decision["action"] == "retain_input_failure" and decision["source_evidence"] is not None
                          and record["current_input_decision"] == self.contracts.classify(replace(witness, original_evidence=None)),
                          "resumed reproduction decision differs outside reviewed terminal acquisition")
                result["later_reviewed_original_acquisition"] = self.acquisition_binding(entry, decision)
            return result
        with c.Claim(output / "claims" / f"{identity}.json", self.args.selection_sha256):
            if current is None:
                return {"original_cell_id": identity, "status": "pending_corrected_outcome_or_owner"}
            action = decision["action"]
            if action == "reuse_original_outcome":
                proof = self.numerical.get(identity)
                if proof is None or proof["status"] == "pending_original_numerical_reproduction":
                    return {"original_cell_id": identity, "status": "pending_original_numerical_reproduction"}
                if c.safe(self.repro_paths["original_reproduction"] / "claims" / f"{identity}.json").exists():
                    return {"original_cell_id": identity, "status": "pending_original_numerical_owner"}
            else:
                proof = None
            if action in c.FIT_ACTIONS and identity not in self.manifest["pilot_cells"]:
                if self.args.pilot_review is None or self.args.pilot_review_sha256 is None:
                    return {"original_cell_id": identity, "status": "pending_full_budget_pilot_review"}
                self.fit_controller.validate_pilot_review(c.read_json(self.args.pilot_review, self.args.pilot_review_sha256),
                    self.manifest, self.selection["corrected_manifest_sha256"], self.repro_paths["corrected_run"])
            leftovers = list((output / "attempts").glob(f"{identity}.*"))
            c.require(not leftovers, "unrecorded reproduction attempt/orphan requires explicit review, never automatic retry")
            attempt = output / "attempts" / f"{identity}.{uuid.uuid4().hex}"
            attempt.mkdir()
            record: dict[str, Any] = {"schema_version": 1, "original_cell_id": identity,
                "selection_sha256": self.args.selection_sha256, "scope_definition_sha256": self.rc.scope_definition(self.selection),
                "corrected_manifest_sha256": self.selection["corrected_manifest_sha256"],
                "correction_freeze_sha256": self.selection["correction_freeze_sha256"],
                "definition_content_sha256": self.freeze["definition_content_sha256"],
                "input_witness_sha256": entry["input_witness_sha256"], "current_input_decision": decision,
                "corrected_outcome_path": str(current[0]), "corrected_outcome_sha256": c.sha(current[0]),
                "artifacts": {}, "external_artifacts": {}, "selected_scope_only": True,
                "programme_complete": False, "reporting_certified": False, "release_certified": False}
            if current[1]["decision"] != decision:
                acquisition = self.acquisition_binding(entry, decision)
                record["pending_origin_terminal_resolution"] = {
                    "status": "finished_original_acquisition_verified_for_pending_origin_terminal",
                    "retained_original_terminal_decision": current[1]["decision"],
                    **acquisition}
                acquisition_path = c.below(self.paths["witness_root"], acquisition["snapshot_path"])
                record["external_artifacts"][str(acquisition_path)] = c.file_binding(acquisition_path)
                if getattr(self.args, "resolution_review", None) is not None:
                    record["external_artifacts"][str(self.args.resolution_review)] = c.file_binding(self.args.resolution_review)
            try:
                if action == "reuse_original_outcome":
                    c.require(old is not None and current[1]["operation"] == "reuse_original_outcome", "unchanged reuse lineage missing")
                    comparison, external = self.inherited(identity, current[1], proof)
                    c.write_new(attempt / "inherited_original_comparison.json", c.seal(comparison))
                    record.update(status="reused_verified_original_numerical_reproduction", comparison=comparison,
                                  external_artifacts=external, new_numerical_fit_executed=False,
                                  inherited_actual_original_numerical_refit_evidence=True, scientific_status=old["status"])
                elif action in c.FIT_ACTIONS:
                    c.require(current[1]["operation"] == "fit_corrected_inputs" and old is not None,
                              "changed reproduction requires actual original ownership and corrected numerical source")
                    record.update(self.execute_changed(entry, decision, witness, current[1], attempt))
                elif action == "retain_input_failure":
                    record.update(self.execute_terminal(entry, current[1], attempt))
                else:
                    c.require(False, "unrecognized selected reproduction action")
                after = self.baseline(entry, decision, witness)
                c.require(after is not None and c.sha(after[0]) == record["corrected_outcome_sha256"], "corrected source changed during reproduction")
                if decision["source_evidence"] is not None:
                    c.require(c.verify_original_outcome(self.paths["original_run"], identity, decision["source_evidence"]) is not None,
                              "original owner/source changed during reproduction")
                _, refreshed, _, _ = self.input_controller.current(entry)
                c.require(refreshed == decision, "input proofs/decision changed during reproduction")
            except Exception as error:
                failure = c.seal({"type": f"{type(error).__module__}.{type(error).__qualname__}", "message": str(error),
                                  "status": "retained_reproduction_failure", "scientific_success_claimed": False})
                c.write_new(attempt / "failure.json", failure)
                record.update(status="retained_reproduction_failure", error=failure,
                              new_numerical_fit_executed=None,
                              numerical_execution_status="not_certified_see_retained_invocation_and_child_artifacts",
                              reproduction_certified=False)
            record["artifacts"] = artifact_inventory(c, attempt, output)
            record["external_artifacts"][str(current[0])] = c.file_binding(current[0])
            c.write_new(path, c.seal(record))
            verify_record(c, path, self.args.selection_sha256, identity, output)
            return {"original_cell_id": identity, "status": record["status"], "record_sha256": c.sha(path)}

    def run(self) -> dict[str, Any]:
        """Append a selected pass; no incomplete pass can become final proof."""
        c, results = self.common, []
        lookup = {row["original_cell_id"]: row for row in self.inventory["entries"]}
        with c.Claim(self.args.output / "controller.claim.json", self.args.selection_sha256):
            for identity in self.selection["selected_cells"]:
                result = self.record(lookup[identity])
                results.append(result)
                print(json.dumps(result, sort_keys=True), flush=True)
            if self.final_gates is not None:
                self.final_gates()
            value = self.rc.publication_status(results, self.selection["selected_cells"])
            value.update(schema_version=1, selection_sha256=self.args.selection_sha256,
                         scope_definition_sha256=self.rc.scope_definition(self.selection),
                         original_fixed_selected_cells=92, pilot_union_selected_cells=len(self.selection["selected_cells"]),
                         correction_freeze_sha256=self.selection["correction_freeze_sha256"],
                         corrected_manifest_sha256=self.selection["corrected_manifest_sha256"],
                         original_comparison_source_sha256=self.rc.COMPARISON_PINS)
            if hasattr(self.args, "environment_artifacts"):
                value["controller_environment_artifacts"] = self.args.environment_artifacts
                c.verify_files(self.args.output, self.args.environment_artifacts)
            if getattr(self.args, "resolution_review", None) is not None:
                value["actual_original_resolution_review"] = {"path": str(self.args.resolution_review),
                    "sha256": self.args.resolution_review_sha256}
                c.require(c.sha(self.args.resolution_review) == self.args.resolution_review_sha256,
                          "actual original acquisition review changed before selected pass")
            path = self.args.output / "passes" / f"{uuid.uuid4().hex}.json"
            c.write_new(path, c.seal(value))
            return {**value, "pass_receipt_path": str(path), "pass_receipt_sha256": c.sha(path)}


def main() -> None:
    """No real execution is possible without independently supplied real freezes."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("selection", "output", "python"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--selection-sha256", required=True)
    for name in ("pilot-review", "resolution-review", "original-numerical-resolution"):
        parser.add_argument(f"--{name}", type=Path)
        parser.add_argument(f"--{name}-sha256")
    args = parser.parse_args()
    c, rc = bootstrap(args.selection, args.selection_sha256)
    supplied = args.python.absolute()
    c.require(supplied.is_file() and ".." not in supplied.parts, "explicit locked Python required")
    args.python = c.safe(supplied.resolve(strict=True))
    c.validate_runtime(args.python)
    own = Path(__file__).absolute().parent
    selection, freeze, manifest, inventory, (completion, rows, evidence) = rc.load_selection(args.selection, args.selection_sha256, own)
    fit_directory = Path(selection["paths"]["fit_code"])
    c.require("fit_common" not in sys.modules, "fit support namespace already occupied")
    sys.modules["fit_common"] = c
    fit_controller = c.module_from_pin(fit_directory / "fit_controller.py", rc.FIT_SOURCE_PINS["fit_controller.py"], "_reproduction_fit_controller")
    contracts = c.module_from_pin(Path(freeze["paths"]["contracts"]), c.CONTRACTS_SHA, "_reproduction_contracts")
    resolutions = fit_controller.read_resolution_review(args.resolution_review, args.resolution_review_sha256, freeze)
    numerical = numerical_inventory(c, rc, selection, evidence, args.original_numerical_resolution, args.original_numerical_resolution_sha256)
    forbidden = [Path(value) for value in freeze["paths"].values()] + [Path(value) for value in selection["paths"].values()]
    prepare_output(c, args.output, args.selection, args.selection_sha256, forbidden)
    original = c.read_original_manifest(Path(freeze["paths"]["original_run"]))
    c.verify_original_source(Path(freeze["paths"]["source"]), original)
    c.require(c.sha(Path(freeze["paths"]["matched"])) == original["matched_sha256"], "matched input bytes differ")
    environment_dir = args.output / "passes" / f"environment.{uuid.uuid4().hex}"
    environment_dir.mkdir()
    preflight_manifest = c.read_json(Path(freeze["paths"]["preflight"]) / "manifest.json", freeze["preflight_manifest_sha256"])
    c.verify_environment(Path(freeze["paths"]["source"]), original, args.python, preflight_manifest, environment_dir)
    args.environment_artifacts = artifact_inventory(c, environment_dir, args.output)
    import arviz as az
    import numpy as np
    comparators = rc.original_comparators(Path(freeze["paths"]["source"]), np, az)
    def final_gates() -> None:
        rc.load_selection(args.selection, args.selection_sha256, own)
        c.verify_original_source(Path(freeze["paths"]["source"]), original)
        c.require(c.sha(Path(freeze["paths"]["matched"])) == original["matched_sha256"], "matched input changed before reproduction seal")
    controller = Controller(args, c, rc, selection, freeze, manifest, inventory, completion, rows,
                            numerical, fit_controller, contracts, comparators, resolutions, final_gates=final_gates)
    result = controller.run()
    rc.load_selection(args.selection, args.selection_sha256, own)
    c.verify_original_source(Path(freeze["paths"]["source"]), original)
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
