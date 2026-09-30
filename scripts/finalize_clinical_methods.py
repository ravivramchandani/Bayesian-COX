"""Finalize the frozen post-hoc clinical subset from independently verified cells."""

from __future__ import annotations

import argparse
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.pipelines.extensions.analysis import extension_families
from src.pipelines.extensions.runner import verified_cell
from src.rendering.verification import verify_frozen_run
from src.utils.io import read_mapping, write_json_atomic
from src.utils.posthoc_evidence import verify_posthoc_run
from src.utils.reproducibility import canonical_json_hash, sha256_file

COHORTS = ("gbsg2", "whas500", "metabric")
PENALISED = ("ridge", "lasso", "elastic_net")
REFERENCES = ("bayesian_normal", "bayesian_horseshoe", "bayesian_spike_slab")
STATUS = ("complete", "failed", "failed_diagnostics")
EVIDENCE = "post_hoc_clinical_methods_subset"


def selected_ids() -> set[str]:
    """Return the 225 identities fixed before focused performance inspection."""
    return {
        f"{cohort}__clinical__r{repeat:02d}f{fold:02d}__{model}__full"
        for cohort in COHORTS
        for model in PENALISED
        for repeat in range(1, 6)
        for fold in range(1, 6)
    }


def check_source_receipt(root: Path, run: Path, report_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Require a passing independent receipt and rebind every selected source byte."""
    report = read_mapping(report_path)
    scope_path = root / "coordination/clinical_methods_scope_freeze.json"
    scope = read_mapping(scope_path)
    roster_path = root / "coordination/clinical_methods_roster.json"
    if any(sha256_file(root / name) != digest for name, digest in scope["sha256"].items()):
        raise ValueError("focused study scope or roster changed after freeze")
    if sha256_file(root / scope["baseline_source_pins"]) != scope["baseline_source_pins_sha256"]:
        raise ValueError("baseline source pins changed after focused scope freeze")
    if (scope["source_extension_manifest_sha256"] != sha256_file(run / "manifest.json")
            or report.get("source_manifest_sha256") != scope["source_extension_manifest_sha256"]
            or report.get("scope_freeze_sha256") != sha256_file(scope_path)):
        raise ValueError("verification report does not bind the frozen source and scope")
    roster = read_mapping(roster_path)
    if (roster.get("source_cell_count") != 225 or roster.get("datasets") != list(COHORTS)
            or roster.get("penalised_models") != list(PENALISED)):
        raise ValueError("focused study roster differs from the selected clinical cells")
    manifest = read_mapping(run / "manifest.json")
    if (canonical_json_hash({k: v for k, v in manifest.items() if k != "manifest_content_sha256"})
            != manifest["manifest_content_sha256"]
            or manifest["code"]["git_commit"] != scope["source_fit_commit"]
            or report.get("production_code_commit") != scope["source_fit_commit"]
            or report.get("manifest_matched_sha256") != manifest.get("matched_sha256")
            or report.get("full_extension_grid_verified") is not False):
        raise ValueError("focused evidence cannot certify the full extension grid")
    if (report.get("evidence_status") != EVIDENCE or report.get("verification_status") != "passed"
            or report.get("verifier_committed") is not True
            or report.get("verified_cells") != 225
            or report.get("refits_compared") != 9
            or sha256_file(root / "scripts/verify_clinical_methods_subset.py") != report.get("verifier_sha256")):
        raise ValueError("independent subset verification is absent or not passed")
    entries = report.get("cells")
    if not isinstance(entries, dict) or set(entries) != selected_ids():
        raise ValueError("verified subset does not equal the frozen 225-cell roster")
    refits = report.get("selected_refits")
    selected_refits = {identity for identity in selected_ids() if "__r01f01__" in identity}
    if not isinstance(refits, dict) or set(refits) != selected_refits:
        raise ValueError("verification does not account for all nine selected refits")
    for identity, refit in refits.items():
        if (not isinstance(refit, dict)
                or refit.get("source_content_sha256") != entries[identity].get("cell_content_sha256")
                or not isinstance(refit.get("refit_content_sha256"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", refit["refit_content_sha256"])
                or refit.get("comparison") != "non-timing scientific content equal"
                or refit.get("original_receipt") not in {"verified", "missing_pending"}):
            raise ValueError(f"selected refit proof differs from bound source: {identity}")
    cells = []
    for identity in sorted(entries):
        path = run / "cells" / f"{identity}.json"
        entry = entries[identity]
        cell = verified_cell(path)
        if (not isinstance(entry, dict)
                or sha256_file(path) != entry.get("file_sha256")
                or cell["cell_content_sha256"] != entry.get("cell_content_sha256")
                or cell.get("status") != entry.get("status")
                or cell.get("cell_id") != identity
                or cell.get("status") not in STATUS):
            raise ValueError(f"verified source cell changed or has invalid status: {identity}")
        cells.append(cell)
    counts = dict(Counter(cell["status"] for cell in cells))
    if (counts != report.get("status_counts")
            or len(cells) != report.get("verified_cells")
            or counts.get("complete", 0) != report.get("rescored_cells")):
        raise ValueError("verification status/rescoring counts differ from bound cells")
    refit_receipts = Counter(entry["original_receipt"] for entry in refits.values())
    if (refit_receipts.get("verified", 0) != report.get("original_refit_receipts_verified")
            or refit_receipts.get("missing_pending", 0) != report.get("original_refit_receipts_pending")):
        raise ValueError("original refit receipt accounting differs from selected comparisons")
    return cells, report


def check_baseline_pins(root: Path, primary: Path, sampler: Path) -> tuple[Any, dict[str, Any], dict[str, str]]:
    """Verify immutable original and ADR-032 sources, then bind every reference cell."""
    pins = read_mapping(root / "coordination/extension_sources/baseline_sources.json")
    for label, folder in (("primary", primary), ("sampler_adr032", sampler)):
        for name in ("manifest", "completion"):
            if sha256_file(folder / f"{name}.json") != pins[label][f"{name}_sha256"]:
                raise ValueError(f"frozen baseline source changed: {label}/{name}")
    original = verify_frozen_run(primary)
    if original.mode != "confirmatory":
        raise ValueError("focused reference is not the frozen confirmatory study")
    posthoc = verify_posthoc_run(sampler, primary)
    original_refs = [(relative, cell) for relative, cell in original.cells
                     if cell["model_key"] in REFERENCES]
    sampler_refs = posthoc["cells"]
    if len(original_refs) != 225 or len(sampler_refs) != 75:
        raise ValueError("Bayesian reference inventory differs from the fixed study scope")
    hashes = {f"primary/{relative}": original.source_hashes[relative]
              for relative, _ in original_refs}
    for cell in sampler_refs:
        relative = (f"cells/{cell['dataset']}/repeat_{cell['repeat']:02d}_fold_{cell['fold']:02d}/"
                    "bayesian_horseshoe.json")
        hashes[f"adr032/{relative}"] = sha256_file(sampler / relative)
    if len(hashes) != 300:
        raise ValueError("reference hash inventory is incomplete")
    return original, posthoc, hashes


def check_programme_evidence(root: Path, sampler: Path) -> dict[str, Any]:
    """Bind the released exact-refit audit without claiming raw trace-array replay."""
    pin_path = root / "coordination/clinical_methods_baseline_evidence.json"
    pin = read_mapping(pin_path)
    expected_paths = {
        "reproduction_verification": "reproduction/verification.json",
        "programme_analysis_verified": "release_metadata/programme_analysis_verified.json",
        "programme_release_ready": "release_metadata/programme_release_ready.json",
    }
    if (pin.get("version") != 1
            or pin.get("reproduction_cells_checked") != 450
            or pin.get("reproduction_cells_identical") != 450
            or "raw posterior arrays unavailable" not in pin.get("verification_limit", "")):
        raise ValueError("baseline evidence pin has an unexpected scope or claim boundary")
    files = {}
    records = {}
    for name, relative in expected_paths.items():
        if pin.get(f"{name}_relative_path") != relative:
            raise ValueError(f"baseline evidence path differs: {name}")
        path = sampler.parent / relative
        digest = sha256_file(path)
        if digest != pin.get(f"{name}_sha256"):
            raise ValueError(f"restored baseline programme evidence changed: {name}")
        files[name] = digest
        records[name] = read_mapping(path)
    reproduction = records["reproduction_verification"]
    cells = reproduction.get("cells")
    if (reproduction.get("evidence_status") != "verification_only"
            or reproduction.get("analysis") != "confirmatory_refit_reproduction"
            or reproduction.get("selection") != "all"
            or reproduction.get("cells_checked") != 450
            or reproduction.get("cells_identical") != 450
            or not isinstance(cells, list) or len(cells) != 450
            or len({cell.get("cell") for cell in cells}) != 450
            or any(cell.get("identical") is not True or cell.get("n_differences") != 0
                   for cell in cells)
            or reproduction.get("report_content_sha256") != canonical_json_hash({
                k: v for k, v in reproduction.items() if k != "report_content_sha256"})):
        raise ValueError("baseline exact-refit verification does not cover 450 identical cells")
    analysis = records["programme_analysis_verified"]
    if (analysis.get("status") != "analysis_and_rendering_verified_pending_final_visual_qa"
            or analysis.get("reproduction_cells_identical") != 450
            or analysis.get("confirmatory_status_counts") != {"complete": 430, "failed_diagnostics": 20}
            or analysis.get("posthoc_sampler_status_counts") != {"complete": 75}
            or analysis.get("result_content_sha256") != canonical_json_hash({
                k: v for k, v in analysis.items() if k != "result_content_sha256"})):
        raise ValueError("baseline programme analysis does not retain diagnostic attrition")
    if records["programme_release_ready"].get("status") != "release_ready":
        raise ValueError("restored baseline programme release is not ready")
    return {"baseline_evidence_pin_sha256": sha256_file(pin_path),
            "released_programme_file_sha256": files,
            "original_refits_identical": 450,
            "verification_limit": pin["verification_limit"]}


def quantiles(values: list[Any]) -> dict[str, Any]:
    """Summarize finite observed numbers without imputing unavailable values."""
    finite = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    if not finite:
        return {"available": 0, "median": None, "q25": None, "q75": None}
    q25, median, q75 = np.quantile(finite, [0.25, 0.5, 0.75]).tolist()
    return {"available": len(finite), "median": median, "q25": q25, "q75": q75}


def cell_summary(cell: dict[str, Any], source: str) -> dict[str, Any]:
    """Retain all fit statuses and stored secondary metrics with clear lineage."""
    if source == "original_horseshoe_context":
        attempts = cell.get("fit_attempts", [])
        last = attempts[-1] if attempts else {}
        diagnostics = last.get("diagnostics") or {}
        return {"dataset": cell["dataset"], "model_key": cell["model_key"],
                "source": source, "repeat": cell["repeat"], "fold": cell["fold"],
                "status": cell["status"], "metrics": None, "calibration": None,
                "cell_seconds": cell.get("total_seconds"), "runtime_definition": "observed end-to-end cell elapsed time",
                "failure_type": cell.get("error_type"), "failure_message": cell.get("message"),
                "fit_attempts": len(attempts),
                "diagnostic_converged": diagnostics.get("converged"),
                "diagnostic_failures": diagnostics.get("failures"),
                "n_train": cell.get("n_train"), "events_train": cell.get("events_train"),
                "p": None, "p_over_n": None, "events_over_p": None}
    metric = cell.get("metrics") if cell["status"] == "complete" else None
    metrics = ({name: metric.get(name) for name in ("ibs", "harrell_c_index", "uno_c_index", "mean_auc")}
               if metric else None)
    calibration = []
    if metric:
        for index, item in enumerate(metric.get("calibration", []), start=1):
            summary = item["summary"]
            calibration.append({"horizon_index": index, "horizon": summary.get("horizon"),
                                "n_known": summary.get("n_known"),
                                "calibration_in_the_large": summary.get("calibration_in_the_large"),
                                "intercept": summary.get("intercept"), "slope": summary.get("slope")})
    attempts = cell.get("fit_attempts", [])
    last = attempts[-1] if attempts else {}
    diagnostics = last.get("diagnostics") or {}
    optimizer = last.get("optimizer")
    p, n, events = cell.get("p"), cell.get("n_train"), cell.get("events_train")
    p_over_n = float(p) / float(n) if p is not None and n is not None and n > 0 else None
    events_over_p = float(events) / float(p) if p is not None and events is not None and p > 0 else None
    return {"dataset": cell["dataset"], "model_key": cell["model_key"],
            "source": source, "repeat": cell["repeat"], "fold": cell["fold"],
            "status": cell["status"], "metrics": metrics,
            "calibration": calibration if metric else None,
            "cell_seconds": cell.get("seconds", cell.get("total_seconds")),
            "runtime_definition": "observed end-to-end cell elapsed time including evaluation",
            "fit_attempts": len(attempts), "diagnostic_converged": diagnostics.get("converged"),
            "diagnostic_failures": diagnostics.get("failures"),
            "optimizer": optimizer if optimizer else None,
            "optimizer_status": "recorded" if optimizer else "not_recorded",
            "optimizer_warnings": last.get("warnings"),
            "failure_type": cell.get("error_type"), "failure_message": cell.get("message"),
            "p": p, "n_train": n, "events_train": events,
            "p_over_n": p_over_n, "events_over_p": events_over_p}


def descriptive_summary(cells: list[dict[str, Any]], original: Any, sampler: dict[str, Any]) -> dict[str, Any]:
    """Summarize accepted-only scores beside full-denominator diagnostic coverage."""
    rows = [cell_summary(cell, "penalised_extension") for cell in cells]
    rows += [cell_summary(cell, "original_confirmatory") for _, cell in original.cells
             if cell["model_key"] in {"bayesian_normal", "bayesian_spike_slab"}]
    rows += [cell_summary(cell, "adr032_posthoc_sampler") for cell in sampler["cells"]]
    context = [cell_summary(cell, "original_horseshoe_context") for _, cell in original.cells
               if cell["model_key"] == "bayesian_horseshoe"]
    if len(rows) != 450 or len(context) != 75:
        raise ValueError("descriptive source roster differs from the focused study")
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows + context:
        groups[(row["dataset"], row["model_key"], row["source"])].append(row)
    group_rows = []
    for (dataset, model, source), records in sorted(groups.items()):
        statuses = dict(Counter(record["status"] for record in records))
        if len(records) != 25:
            raise ValueError(f"clinical source has fewer than 25 planned folds: {dataset}/{model}/{source}")
        metric_summaries = {name: quantiles([record["metrics"].get(name)
                           if record["metrics"] else None for record in records])
                            for name in ("ibs", "harrell_c_index", "uno_c_index", "mean_auc")}
        calibration_summaries = []
        for h in range(1, 4):
            calibration_summaries.append({"horizon_index": h,
                **{parameter: quantiles([
                    record["calibration"][h - 1][parameter]["estimate"]
                    if record["calibration"] and len(record["calibration"]) >= h
                    and isinstance(record["calibration"][h - 1].get(parameter), dict) else None
                    for record in records])
                   for parameter in ("calibration_in_the_large", "intercept", "slope")}})
        group_rows.append({"dataset": dataset, "model_key": model, "source": source,
                           "planned": 25, "status_counts": statuses,
                           "accepted": statuses.get("complete", 0),
                           "diagnostic_convergence_counts": dict(Counter(
                               "not_recorded" if record.get("diagnostic_converged") is None
                               else str(record["diagnostic_converged"]).lower() for record in records)),
                           "optimizer_status_counts": dict(Counter(
                               record.get("optimizer_status", "not_applicable") for record in records)),
                           "metrics_accepted_only": metric_summaries,
                           "calibration_accepted_only": calibration_summaries,
                           "information_regime_all_outcomes": {
                               name: quantiles([record[name] for record in records])
                               for name in ("n_train", "events_train", "p", "p_over_n", "events_over_p")},
                           "runtime_all_outcomes_seconds": quantiles([r["cell_seconds"] for r in records]),
                           "fit_attempts_all_outcomes": quantiles([r["fit_attempts"] for r in records])})
    return {"schema_version": 1, "evidence_status": EVIDENCE,
            "cell_rows": rows, "original_horseshoe_context": context,
            "group_rows": group_rows,
            "interpretation": {
                "metrics": "accepted-only descriptive summaries; planned and failed counts remain visible",
                "runtime": "observed end-to-end cell times across separate runs; not hardware-normalized fit-only cost",
                "no_equivalence_or_global_winner_claim": True,
                "no_prior_only_causal_attribution": True,
                "no_clinical_utility_or_external_validation_claim": True,
                "metabric_known_same_individual_pair": "One known accession pair in frozen clinical METABRIC may cross train and validation folds; biological independence is not claimed."}}


def fixed_family(cells: list[dict[str, Any]], original: Any, sampler: dict[str, Any]) -> dict[str, Any]:
    """Reuse the frozen paired analysis for only the pre-specified 27 contrasts."""
    refs = [cell for _, cell in original.cells if cell["model_key"] != "bayesian_horseshoe"]
    refs.extend(sampler["cells"])
    family = extension_families(cells, refs)["penalized_vs_original_priors"]
    if len(family["contrasts"]) != 27 or family["expected_contrasts"] != 27:
        raise ValueError("paired comparison does not match the fixed 27-contrast family")
    return family


def finalize(run: Path, verification: Path, primary: Path, sampler: Path, output: Path) -> dict[str, Any]:
    """Write focused aggregates in a fresh directory, leaving all source runs intact."""
    root = Path(__file__).resolve().parents[1]
    for source in (run, primary, sampler):
        if output.resolve().is_relative_to(source.resolve()):
            raise ValueError("focused aggregates must be outside every immutable source")
    if output.exists():
        raise FileExistsError("choose a new focused analysis output directory")
    cells, report = check_source_receipt(root, run, verification)
    original, posthoc, reference_hashes = check_baseline_pins(root, primary, sampler)
    programme_evidence = check_programme_evidence(root, sampler)
    family = fixed_family(cells, original, posthoc)
    comparisons = {"schema_version": 1, "evidence_status": EVIDENCE,
                   "family_name": "penalized_vs_original_priors", **family,
                   "direction": "penalised IBS minus Bayesian IBS; positive favours Bayesian",
                   "references": "original normal/spike-slab plus separately labelled ADR-032 horseshoe",
                   "claims": {"equivalence_permitted": False, "global_winner_permitted": False,
                              "causal_prior_effect_permitted": False}}
    descriptive = descriptive_summary(cells, original, posthoc)
    ledger = {"schema_version": 1, "evidence_status": EVIDENCE,
              "scope_freeze_sha256": report["scope_freeze_sha256"],
              "source_verification_sha256": sha256_file(verification),
              "source_manifest_sha256": sha256_file(run / "manifest.json"),
              "matched_sha256": report["manifest_matched_sha256"],
              "matched_source_file_verified": report.get("matched_source_file_verified"),
              "verifier_sha256": report["verifier_sha256"],
              "finalizer_sha256": sha256_file(Path(__file__)),
              "verification_analysis_code_commit": report.get("analysis_code_commit"),
              "source_cell_file_sha256": {identity: entry["file_sha256"]
                                          for identity, entry in sorted(report["cells"].items())},
              "reference_cell_file_sha256": reference_hashes,
              "baseline_source_sha256": {
                  "primary_manifest": sha256_file(primary / "manifest.json"),
                  "primary_completion": sha256_file(primary / "completion.json"),
                  "adr032_manifest": sha256_file(sampler / "manifest.json"),
                  "adr032_completion": sha256_file(sampler / "completion.json")},
              "baseline_programme_evidence": programme_evidence,
              "full_extension_grid_verified": False}
    output.mkdir(parents=True)
    for name, content in (("paired_families.json", comparisons), ("descriptive.json", descriptive),
                          ("source_ledger.json", ledger)):
        write_json_atomic(output / name, content, overwrite=False)
    completion = {"schema_version": 1, "evidence_status": EVIDENCE,
                  "status": "analysis_complete_release_pending",
                  "full_extension_grid_verified": False,
                  "source_verification_sha256": ledger["source_verification_sha256"],
                  "scope_freeze_sha256": ledger["scope_freeze_sha256"],
                  "source_manifest_sha256": ledger["source_manifest_sha256"],
                  "original_refit_receipts_verified": report.get("original_refit_receipts_verified"),
                  "original_refit_receipts_pending": report.get("original_refit_receipts_pending"),
                  "aggregate_sha256": {name: sha256_file(output / name) for name in
                                       ("paired_families.json", "descriptive.json", "source_ledger.json")},
                  "family_complete": family["family_complete"],
                  "verified_source_cells": len(cells), "reference_cells": 225,
                  "original_horseshoe_context_cells": 75}
    completion["completion_content_sha256"] = canonical_json_hash(completion)
    write_json_atomic(output / "completion.json", completion, overwrite=False)
    return completion


def main() -> None:
    """Read independently verified evidence and finalize only the focused subset."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("run", "verification", "primary", "sampler", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    completion = finalize(args.run.resolve(), args.verification.resolve(),
                          args.primary.resolve(), args.sampler.resolve(), args.output.absolute())
    print(f"focused 27-contrast analysis complete; family_complete={completion['family_complete']}; "
          f"release pending: {args.output}")


if __name__ == "__main__":
    main()
