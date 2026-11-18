"""Render matched-fold summaries and saved IBS bootstrap sensitivity estimates."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUN_NAME = "confirmatory_v1_confirmatory_cdcdcee84651"
COHORTS = {"gbsg2": "GBSG2", "whas500": "WHAS500", "metabric": "METABRIC"}
MODELS = {
    "bayesian_normal": "Normal",
    "bayesian_horseshoe": "Horseshoe",
    "bayesian_spike_slab": "Continuous Spike-and-Slab",
    "cox_ph": "CoxPH",
    "random_survival_forest": "RSF",
    "deepsurv": "DeepSurv",
}
MODEL_NAMES = {
    "Bayesian Cox (normal)": "Normal",
    "Bayesian Cox (horseshoe)": "Horseshoe",
    "Bayesian Cox (spike_slab)": "Spike-and-Slab",
}
EXPECTED_COUNTS = {"gbsg2": 7, "whas500": 25, "metabric": 23}
EXPECTED_SEALS = {
    "manifest.json": ("manifest_content_sha256", "9ec040841b4751ee3064c93d21d5069ed27bf3bfd6641f0dfffff76557bbf9f7"),
    "completion.json": ("completion_content_sha256", "03870efdae3134305794ea977fd9cbe7913c0d693f1b009337546319aa03bee1"),
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _load_inputs(run: Path) -> tuple[list[dict[str, str]], dict[str, Any], dict[str, Any]]:
    metadata = {}
    for name, (field, expected) in EXPECTED_SEALS.items():
        record = json.loads((run / name).read_text())
        claimed = record[field]
        actual = _canonical({key: value for key, value in record.items() if key != field})
        if actual != claimed or claimed != expected:
            raise ValueError(f"Frozen input seal mismatch: {name}")
        metadata[name] = record
    manifest = metadata["manifest.json"]
    completion = metadata["completion.json"]
    if manifest["run_config"]["mode"] != "confirmatory":
        raise ValueError("Expected the original confirmatory analysis")
    if completion["status_counts"] != {"complete": 430, "failed_diagnostics": 20}:
        raise ValueError("Changed original outcome coverage")
    for name in ("fold_metrics.csv", "inference.json"):
        if _sha(run / name) != completion["aggregate_sha256"][name]:
            raise ValueError(f"Frozen aggregate hash mismatch: {name}")
    with (run / "fold_metrics.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    inference = json.loads((run / "inference.json").read_text())
    return rows, inference, metadata


def _matched_rows(rows: list[dict[str, str]]) -> tuple[list[dict[str, Any]], dict[str, list[list[int]]]]:
    indexed = {}
    fold_design = {}
    design_fields = ("n_train", "n_validation", "events_train", "events_validation", "horizon_1", "horizon_2", "horizon_3")
    for row in rows:
        dataset, model = row["dataset"], row["model_key"]
        repeat, fold = int(row["repeat"]), int(row["fold"])
        identity = (dataset, model, repeat, fold)
        if dataset not in COHORTS or model not in MODELS or repeat not in range(1, 6) or fold not in range(1, 6):
            raise ValueError(f"Unexpected fold identity: {identity}")
        if identity in indexed:
            raise ValueError(f"Duplicate outcome: {identity}")
        for metric in ("ibs", "mean_auc"):
            value = float(row[metric])
            if not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"Invalid {metric} in {identity}")
        if len(row["cell_content_sha256"]) != 64:
            raise ValueError(f"Missing source-cell content hash: {identity}")
        design_key = (dataset, repeat, fold)
        design = tuple(float(row[field]) for field in design_fields)
        if design_key in fold_design and fold_design[design_key] != design:
            raise ValueError(f"Mismatched cohort/fold evaluation design: {design_key}")
        fold_design[design_key] = design
        indexed[identity] = row
    if len(indexed) != 430:
        raise ValueError("Expected all 430 accepted original outcomes")
    results, selected = [], {}
    for dataset in COHORTS:
        folds = sorted((repeat, fold) for cohort, model, repeat, fold in indexed if cohort == dataset and model == "bayesian_horseshoe")
        if len(folds) != EXPECTED_COUNTS[dataset]:
            raise ValueError(f"Changed Horseshoe fold coverage: {dataset}")
        selected[dataset] = [list(pair) for pair in folds]
        for model in MODELS:
            coverage = sum(cohort == dataset and candidate == model for cohort, candidate, _, _ in indexed)
            expected = EXPECTED_COUNTS[dataset] if model == "bayesian_horseshoe" else 25
            if coverage != expected:
                raise ValueError(f"Changed model coverage: {dataset}/{model}")
            subset = [indexed[(dataset, model, repeat, fold)] for repeat, fold in folds]
            ibs = [float(row["ibs"]) for row in subset]
            auc = [float(row["mean_auc"]) for row in subset]
            results.append({"dataset": dataset, "model_key": model, "n_matched_folds": len(folds),
                            "mean_ibs": statistics.mean(ibs), "sd_ibs": statistics.stdev(ibs),
                            "mean_auc": statistics.mean(auc), "sd_auc": statistics.stdev(auc)})
    return results, selected


def _bootstrap_rows(inference: dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    for row in inference["primary"]:
        if "paired_oof_bootstrap" not in row:
            if row["n_paired_folds"] == 25:
                raise ValueError("Complete primary contrast has no saved bootstrap result")
            continue
        effect, bootstrap = row["ibs"], row["paired_oof_bootstrap"]
        if row["n_paired_folds"] != 25 or bootstrap["n_bootstraps"] != 1000:
            raise ValueError("Unexpected paired bootstrap specification")
        if not math.isclose(effect["mean_difference"], bootstrap["estimate"], rel_tol=0, abs_tol=1e-15):
            raise ValueError("Primary and bootstrap point estimates differ")
        values = {"estimate": effect["mean_difference"], "corrected_lower": effect["confidence_lower"],
                  "corrected_upper": effect["confidence_upper"], "bootstrap_lower": bootstrap["confidence_lower"],
                  "bootstrap_upper": bootstrap["confidence_upper"]}
        if not all(math.isfinite(value) for value in values.values()):
            raise ValueError("Non-finite saved paired estimate")
        results.append({"dataset": row["dataset"], "model_a": MODEL_NAMES[row["model_a"]],
                        "model_b": MODEL_NAMES[row["model_b"]], "n_pairs": 25, **values,
                        "n_bootstraps": bootstrap["n_bootstraps"], "n_successful": bootstrap["n_successful"],
                        "resampling_unit": bootstrap["resampling_unit"]})
    if len(results) != 5:
        raise ValueError("Expected the five complete original primary contrasts")
    return results


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _render_matched(rows: list[dict[str, Any]]) -> str:
    lines = [r"\begingroup\singlespacing\footnotesize", r"\setlength{\tabcolsep}{4pt}", r"\begin{longtable}{@{}llrrr@{}}",
             r"\caption{Predictive performance on the folds accepted by the original Horseshoe model.}\label{tab:matched-horseshoe-folds}\\",
             r"\toprule Cohort & Model & Folds & IBS, mean (SD) & Mean AUC, mean (SD)\\\midrule\endfirsthead",
             r"\multicolumn{5}{l}{\tablename\ \thetable\ (continued)}\\",
             r"\toprule Cohort & Model & Folds & IBS, mean (SD) & Mean AUC, mean (SD)\\\midrule\endhead",
             r"\midrule\multicolumn{5}{r}{Continued on next page}\\\endfoot", r"\bottomrule\endlastfoot"]
    for row in rows:
        lines.append(f"{COHORTS[row['dataset']]} & {MODELS[row['model_key']]} & {row['n_matched_folds']} & "
                     f"{row['mean_ibs']:.4f} ({row['sd_ibs']:.4f}) & {row['mean_auc']:.4f} ({row['sd_auc']:.4f})" + r" \\")
    lines += [r"\end{longtable}", r"\noindent Each cohort uses one shared set of repeat--fold pairs for all six models: 7 in GBSG2, 25 in WHAS500 and 23 in METABRIC. Entries are equally weighted fold means (sample SD); each fold's mean AUC is the survival-weighted summary across its evaluation horizons. Selection is conditional on original Horseshoe diagnostic acceptance. These descriptive summaries do not replace the complete-fold primary contrasts.\par\endgroup"]
    return "\n".join(lines) + "\n"


def _render_bootstrap(rows: list[dict[str, Any]]) -> str:
    names = {"Normal": "N", "Horseshoe": "H", "Spike-and-Slab": "S"}
    lines = [r"\begingroup\singlespacing\footnotesize", r"\begin{longtable}{@{}llrrrr@{}}",
             r"\caption{Corrected primary and paired-bootstrap IBS intervals for the five complete prior contrasts.}\label{tab:ibs-bootstrap-sensitivity}\\",
             r"\toprule Cohort & Contrast & $\Delta$IBS & Corrected 95\% interval & Bootstrap 95\% interval & Valid draws\\\midrule\endfirsthead",
             r"\multicolumn{6}{l}{\tablename\ \thetable\ (continued)}\\",
             r"\toprule Cohort & Contrast & $\Delta$IBS & Corrected 95\% interval & Bootstrap 95\% interval & Valid draws\\\midrule\endhead",
             r"\midrule\multicolumn{6}{r}{Continued on next page}\\\endfoot", r"\bottomrule\endlastfoot"]
    for row in rows:
        corrected = f"[{row['corrected_lower'] * 1e4:+.3f}, {row['corrected_upper'] * 1e4:+.3f}]"
        bootstrap = f"[{row['bootstrap_lower'] * 1e4:+.3f}, {row['bootstrap_upper'] * 1e4:+.3f}]"
        lines.append(f"{COHORTS[row['dataset']]} & {names[row['model_a']]}--{names[row['model_b']]} & "
                     f"{row['estimate'] * 1e4:+.3f} & {corrected} & {bootstrap} & {row['n_successful']}/1000" + r" \\")
    lines += [r"\end{longtable}", r"\noindent All effects and interval endpoints are expressed in units of $10^{-4}$ IBS. N = Normal, H = Horseshoe, S = continuous Spike-and-Slab; differences are first prior minus second. Every contrast has 25 paired folds. Bootstrap intervals are the saved percentile intervals from event-stratified validation-subject resampling within paired folds, with fitted predictions held fixed. Corrected intervals account approximately for overlapping training sets. Both interval sets are nominal 95\% intervals; neither supplies a new complete-family superiority test.\par\endgroup"]
    return "\n".join(lines) + "\n"


def _robustness_table(thesis: Path, kind: str) -> tuple[str, dict[str, Any]]:
    variants = {
        "coverage": (
            "9fd8cf61b69dfc1d22f3e6a4c7d033003e6892abe47aa2282219a700f837713b",
            "The 825-condition analysis contains 770 accepted fits.",
            "Of 825 model--condition--fold outcomes, 770 were accepted. The analysis involved 885 underlying Bayesian fits.",
        ),
        "diagnostics": (
            "2527f842cf9430a2da014515e768834ea6fc012c4f22742a85691e6e2e2149c4",
            "Counts describe all 825 robustness conditions. Paired effects use diagnostically accepted fits.",
            "Counts describe all 825 model--condition--fold outcomes. Paired effects use accepted outcomes.",
        ),
    }
    expected_presentation, old, new = variants[kind]
    name = f"table_robustness_{kind}.tex"
    path = thesis / "tables" / name
    source = path.read_text()
    generated_path = thesis / "generated" / name
    manifest_path = thesis / "generated/provenance.json"
    manifest = json.loads(manifest_path.read_text())
    expected = manifest["outputs"][name]["sha256"]
    if _sha(generated_path) != expected:
        raise ValueError("Changed frozen generated robustness coverage table")
    if _sha(path) != expected_presentation:
        raise ValueError("Changed original presentation robustness coverage table")
    generated_rows = [line for line in generated_path.read_text().splitlines() if " & " in line and any(char.isdigit() for char in line)]
    presentation_rows = [line for line in source.splitlines() if " & " in line and any(char.isdigit() for char in line)]
    if generated_rows != presentation_rows:
        raise ValueError("Presentation robustness counts differ from the frozen generated counts")
    if source.count(old) != 1:
        raise ValueError("Expected the original robustness outcome-unit note exactly once")
    revised = source.replace(old, new)
    source_rows = [line for line in source.splitlines() if " & " in line]
    revised_rows = [line for line in revised.splitlines() if " & " in line]
    if revised_rows != source_rows:
        raise ValueError("The robustness table's numerical rows changed")
    return revised, {"table_sha256": _sha(path), "frozen_generated_table_sha256": _sha(generated_path), "generated_provenance_sha256": _sha(manifest_path),
                     "numerical_rows_unchanged": True, "caption_and_label_unchanged": True}


def build_report(run: Path, output: Path) -> dict[str, Any]:
    """Verify frozen aggregates and write descriptive summaries without refitting.

    Args:
        run: Original confirmatory run containing its sealed metadata and aggregates.
        output: New supplementary-output directory, separate from frozen reports.

    Returns:
        Input/output hashes, selected fold identities and reporting scope.
    """
    raw_rows, inference, metadata = _load_inputs(run)
    matched, selected = _matched_rows(raw_rows)
    bootstrap = _bootstrap_rows(inference)
    robustness, robustness_source = _robustness_table(ROOT.parent / "thesis-overleaf", "coverage")
    diagnostics, diagnostics_source = _robustness_table(ROOT.parent / "thesis-overleaf", "diagnostics")
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "matched_fold_metrics.csv", matched)
    _write_csv(output / "paired_ibs_bootstrap.csv", bootstrap)
    (output / "table_matched_folds.tex").write_text(_render_matched(matched))
    (output / "table_paired_bootstrap.tex").write_text(_render_bootstrap(bootstrap))
    (output / "table_robustness_coverage.tex").write_text(robustness)
    (output / "table_robustness_diagnostics.tex").write_text(diagnostics)
    report = {"schema_version": "1.0.0", "analysis": "Descriptive matched-fold reaggregation and extraction of saved bootstrap results",
              "new_fitting": False, "new_bootstrap_sampling": False, "source_run": run.name,
              "inputs": {name: _sha(run / name) for name in ("manifest.json", "completion.json", "fold_metrics.csv", "inference.json")},
              "source_embedded_seals": {name: record[EXPECTED_SEALS[name][0]] for name, record in metadata.items()},
              "script_sha256": _sha(Path(__file__)), "source_accepted_rows": len(raw_rows),
              "matched_summary_rows": len(matched), "saved_bootstrap_contrasts": len(bootstrap),
              "matched_folds": selected, "frozen_primary_inference_changed": False,
              "robustness_coverage_source": robustness_source,
              "robustness_diagnostics_source": diagnostics_source,
              "outputs": {name: {"sha256": _sha(output / name), "bytes": (output / name).stat().st_size} for name in (
                  "matched_fold_metrics.csv", "paired_ibs_bootstrap.csv", "table_matched_folds.tex", "table_paired_bootstrap.tex", "table_robustness_coverage.tex", "table_robustness_diagnostics.tex")}}
    (output / "provenance.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=ROOT / "reports/confirmatory" / RUN_NAME)
    parser.add_argument("--output-dir", type=Path, default=ROOT.parent / "thesis-overleaf/report_summaries/supervisor_comparisons")
    args = parser.parse_args()
    report = build_report(args.run_dir, args.output_dir)
    print(json.dumps({key: report[key] for key in ("source_accepted_rows", "matched_summary_rows", "saved_bootstrap_contrasts")}))


if __name__ == "__main__":
    _main()
