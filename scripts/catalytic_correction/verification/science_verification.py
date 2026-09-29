"""Injected mixed-cell scientific verification; no scientific imports at load."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any, Protocol

from verification_io import Pins, canonical, child, require

BAYESIAN = {"bayesian_normal", "bayesian_horseshoe", "bayesian_spike_slab", "pv_horseshoe",
            "catalytic_fixed", "catalytic_adaptive"}
CATALYTIC = {"catalytic_fixed", "catalytic_adaptive", "catalytic_wme"}
STATUSES = {"complete", "failed", "failed_diagnostics"}
TRACE_PATTERN = re.compile(r"attempt_([1-3])_(posterior|prior)\.nc\Z")


class ScientificBackend(Protocol):
    """Actual source-pinned implementation is constructed only by root's CLI."""

    def identity(self, cell: dict[str, Any], job: Any) -> None: ...

    def real_inputs(self, job: Any) -> dict[str, Any]: ...

    def assert_equal(self, left: Any, right: Any, label: str) -> None: ...

    def trace_diagnostics(self, path: Path, label: str, expected: dict[str, Any] | None,
                          identity: str) -> dict[str, Any]: ...

    def rescore(self, cell: dict[str, Any], job: Any, real: dict[str, Any]) -> dict[str, Any]: ...


def verify_attempt_settings(cell: dict[str, Any], config: dict[str, Any]) -> None:
    """Check original full budget/remedy settings recorded by attempted fits.

    Execution failures can precede model construction and have no attempt;
    unavailable settings are not fabricated. Completed Bayesian attempt rows
    retain the unchanged target/tune/noncentered rules and acceptance gates.
    """
    attempts = cell.get("fit_attempts", [])
    bayesian = cell["model_key"] in BAYESIAN
    require(isinstance(attempts, list) and len(attempts) <= (3 if bayesian else 1),
            "attempt count exceeds original remedy rule")
    if cell["status"] == "failed_diagnostics":
        require(bayesian and len(attempts) == 3, "diagnostic-failed outcome did not exhaust the original three attempts")
        final = attempts[-1]
        require(not final.get("diagnostics", {}).get("converged", False)
                or bool(final.get("prior_diagnostics")) and not final["prior_diagnostics"].get("converged", False),
                "diagnostic-failed outcome has accepted final diagnostics")
    for index, row in enumerate(attempts):
        require(row["attempt"] == index + 1, "attempt ordering differs")
        if bayesian:
            expected = {"target_accept": config["sampling"]["target_accept"],
                        "tune": config["sampling"]["tune"] * (2 if index else 1),
                        "noncentered_baseline": index >= 2}
            present = [name for name in expected if name in row]
            # A recorded construction crash can legitimately omit model fields.
            require(len(present) == len(expected) or (not present and "error_type" in row),
                    "partly recorded Bayesian settings")
            for name in present:
                require(row[name] == expected[name], "original attempted sampler setting differs")
            diagnostics = row.get("diagnostics", {})
            if diagnostics and "n_draws" in diagnostics:
                require(diagnostics["method"] == "nuts", "recorded sampler method differs")
                if cell["status"] in {"complete", "failed_diagnostics"}:
                    require(diagnostics["n_draws"] == config["sampling"]["draws"]
                            and diagnostics["n_chains"] == config["sampling"]["chains"],
                            "completed sampler budget differs")
        if index < len(attempts) - 1:
            require(not row.get("error_type") and not row.get("trace_write_errors"),
                    "new attempt follows an original execution failure")
            require(not row.get("diagnostics", {}).get("converged", False)
                    or bool(row.get("prior_diagnostics")) and not row["prior_diagnostics"].get("converged", False),
                    "diagnostic remedy follows an accepted previous attempt")
    if cell["status"] == "complete" and bayesian:
        require(bool(attempts), "accepted Bayesian cell omits attempted fits")
        final = attempts[-1]
        require(final.get("diagnostics", {}).get("converged") is True,
                "accepted Bayesian posterior gate failed")
        if cell["model_key"].startswith("catalytic_"):
            require(final.get("prior_diagnostics", {}).get("converged") is True,
                    "accepted catalytic joint-prior gate failed")


def verify_science_cell(cell: dict[str, Any], job: Any, *, trace_root: Path,
                        referenced: dict[str, str], orphaned: dict[str, str],
                        config: dict[str, Any], backend: ScientificBackend,
                        pins: Pins) -> dict[str, Any]:
    """Independently diagnose and rescore an exact resolved outcome.

    Referenced traces with stored diagnostics must match them exactly under
    the frozen855 routine. Unstored orphan diagnostics are audit observations,
    never invented original diagnostics or accepted-fit proof. A failed cell
    may have no forecasts or traces. It never becomes an accepted observation.
    """
    require(cell["status"] in STATUSES, "unknown scientific outcome status")
    backend.identity(cell, job)
    verify_attempt_settings(cell, config)
    identity = cell["cell_id"]
    require(not set(referenced) & set(orphaned), "trace ownership conflicts")
    actual_references = {}
    diagnostic_targets = {}
    for row in cell.get("fit_attempts", []):
        for label, trace in row.get("traces", {}).items():
            require(label in {"posterior", "prior"} and Path(trace["filename"]).name == trace["filename"],
                    "unknown or traversing referenced trace")
            name = f"traces/{identity}/{trace['filename']}"
            require(name not in actual_references, "one trace has multiple attempt owners")
            actual_references[name] = trace["sha256"]
            expected = row.get("diagnostics" if label == "posterior" else "prior_diagnostics")
            if expected:
                diagnostic_targets[name] = (label, expected)
            else:
                require(cell["status"] == "failed", "accepted/diagnostic-failed trace lacks actual recorded diagnostics")
                diagnostic_targets[name] = (label, None)
        if cell["model_key"] in BAYESIAN and cell["status"] in {"complete", "failed_diagnostics"}:
            required = {"posterior", "prior"} if cell["model_key"].startswith("catalytic_") else {"posterior"}
            require(set(row.get("traces", {})) == required, "completed Bayesian attempt lacks required actual traces")
    require(actual_references == referenced, "resolved referenced trace inventory differs from raw cell")
    trace_prefix = f"traces/{identity}/"
    all_traces = {**referenced, **orphaned}
    for name, digest in all_traces.items():
        require(name.startswith(trace_prefix), "trace belongs to a different cell")
        pins.bind(child(trace_root, name), digest)
    trace_directory = child(trace_root, f"traces/{identity}")
    found = set()
    if trace_directory.exists():
        for path in trace_directory.rglob("*"):
            require(not path.is_symlink(), "linked trace inventory node")
            if path.is_file():
                found.add(str(path.relative_to(trace_root)))
    require(found == set(all_traces), "available referenced/orphan trace inventory differs")
    trace_results = {}
    for name, (label, expected) in diagnostic_targets.items():
        try:
            result = backend.trace_diagnostics(child(trace_root, name), label, expected, identity)
        except Exception as error:
            if expected is not None:
                raise
            result = {"status": "unstored_failed_trace_diagnostics_unavailable",
                      "exception_type": type(error).__name__,
                      "message": str(error).replace(str(trace_root), "<logical_trace_source>")}
        trace_results[name] = {"source_sha256": all_traces[name], "stored_diagnostics_present": expected is not None,
                               "scope": "recomputed_and_compared_stored_diagnostics" if expected is not None
                               else "recomputed_unstored_trace_audit_only", **result}
    for name in orphaned:
        match = TRACE_PATTERN.fullmatch(Path(name).name)
        label = match.group(2) if match is not None else "unknown"
        try:
            result = backend.trace_diagnostics(child(trace_root, name), label, None, identity)
        except Exception as error:
            result = {"status": "orphan_diagnostics_unavailable", "exception_type": type(error).__name__,
                      "message": str(error).replace(str(trace_root), "<logical_trace_source>")}
        trace_results[name] = {"source_sha256": orphaned[name], "stored_diagnostics_present": False,
                               "scope": "orphan_audit_not_an_invented_original_diagnostic", **result}
    real = backend.real_inputs(job)
    require(cell["events_train"] == real["events_train"], "censored training-event count differs")
    if "preprocessing" in cell:
        require(real.get("preprocessing_status") == "reconstructed", "stored preprocessing cannot be reconstructed")
        backend.assert_equal(cell["preprocessing"], real["preprocessing"], identity + "/preprocessing")
        require(cell.get("p") == real["p"], "actual encoded coefficient count differs")
        backend.assert_equal(cell["events_per_coefficient"], real["events_train"] / real["p"],
                             identity + "/events_per_coefficient")
    rescored = False
    if cell["status"] == "complete":
        require(real.get("preprocessing_status") == "reconstructed", "accepted cell lacks reconstructed feature/design inputs")
        predictions = cell["predictions"]
        require(predictions["subject_ids"] == cell["validation_subject_ids"], "forecast patient order differs")
        for name in ("training_time", "training_event", "observed_time", "observed_event"):
            backend.assert_equal(predictions[name], real[name], identity + "/predictions/" + name)
        metrics = backend.rescore(cell, job, real)
        backend.assert_equal(cell["metrics"], metrics, identity + "/metrics")
        rescored = True
    require(cell["status"] == "complete" or "metrics" not in cell and "predictions" not in cell,
            "failed outcome carries fabricated accepted forecasts/metrics")
    return {"original_cell_id": identity, "status": cell["status"], "deep_science_checked": True,
            "rescored": rescored, "trace_checks": trace_results,
            "stored_diagnostic_traces_checked": len(diagnostic_targets), "orphan_traces_audited": len(orphaned),
            "real_input_bindings": {key: real[key] for key in ("training_membership_sha256",
                "validation_membership_sha256", "training_outcomes_sha256", "validation_outcomes_sha256",
                "preprocessing_status", "encoded_training", "encoded_validation") if key in real},
            "raw_cell_content_sha256": cell["cell_content_sha256"], "raw_cell_status_unchanged": True,
            "new_fit_refit_or_generator_invoked": False}


def original_comparison(original: dict[str, Any], resolved: dict[str, Any], operation: str,
                        changed_roles: list[str]) -> dict[str, Any]:
    """Record statuses/input scope only; never promote performance or rescue claims."""
    return {"original_cell_id": resolved["cell_id"], "operation": operation,
            "dataset": resolved.get("dataset"), "setting": resolved.get("setting"),
            "model": resolved.get("model_key"), "condition": resolved.get("condition"),
            "original_status": original["status"], "corrected_view_status": resolved["status"],
            "original_failure_class": "execution" if original["status"] == "failed" else
                "diagnostic" if original["status"] == "failed_diagnostics" else None,
            "corrected_failure_class": "terminal_corrective_input" if resolved.get("derived_corrective_input_failure_view") else
                "execution" if resolved["status"] == "failed" else "diagnostic" if resolved["status"] == "failed_diagnostics" else None,
            "original_error_type": original.get("error_type"), "corrected_error_type": resolved.get("error_type"),
            "original_message": original.get("message"), "corrected_message": resolved.get("message"),
            "changed_input_roles": changed_roles,
            "original_raw_record_preserved": True, "no_significance_or_quality_claim_added": True}


def comparison_counts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Account for original failures separately from the resolved correction view."""
    return {"operation_counts": dict(Counter(row["operation"] for row in rows)),
            "original_status_counts": dict(Counter(row["original_status"] for row in rows)),
            "corrected_status_counts": dict(Counter(row["corrected_view_status"] for row in rows)),
            "changed_input_cells": sum(bool(row["changed_input_roles"]) for row in rows),
            "comparison_rows_sha256": canonical(rows), "inferential_promotion": False}
