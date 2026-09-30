"""Render only the verified, fixed 27-contrast clinical methods subset."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
import tempfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.clinical_methods_release.common import read_json, sha256_file, write_json_new
from scripts.extension_release.archive_common import atomic_new_directory
from src.utils.reproducibility import canonical_json_hash

COHORTS = ("gbsg2", "whas500", "metabric")
PENALISED = ("ridge", "lasso", "elastic_net")
REFERENCES = ("bayesian_normal", "bayesian_horseshoe", "bayesian_spike_slab")
FIGURES = tuple(f"paired_{name}" for name in COHORTS) + ("diagnostic_coverage",)
MODEL_LABELS = {"ridge": "Ridge Cox", "lasso": "Lasso Cox", "elastic_net": "Elastic-net Cox",
                "bayesian_normal": "Bayesian normal", "bayesian_horseshoe": "ADR-032 horseshoe",
                "bayesian_spike_slab": "Bayesian spike/slab"}


def checked_analysis(analysis: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Require the complete bounded aggregate inventory and its fixed contrast set."""
    completion = read_json(analysis / "completion.json")
    content = {k: v for k, v in completion.items() if k != "completion_content_sha256"}
    if (completion.get("schema_version") != 1
            or completion.get("evidence_status") != "post_hoc_clinical_methods_subset"
            or completion.get("status") != "analysis_complete_release_pending"
            or completion.get("full_extension_grid_verified") is not False
            or completion.get("verified_source_cells") != 225
            or completion.get("reference_cells") != 225
            or completion.get("original_horseshoe_context_cells") != 75
            or completion.get("completion_content_sha256") != canonical_json_hash(content)):
        raise ValueError("focused analysis completion is absent or invalid")
    expected = {"paired_families.json", "descriptive.json", "source_ledger.json"}
    if set(completion.get("aggregate_sha256", {})) != expected:
        raise ValueError("focused analysis aggregate roster differs")
    for name, digest in completion["aggregate_sha256"].items():
        if sha256_file(analysis / name) != digest:
            raise ValueError(f"focused analysis aggregate changed: {name}")
    family = read_json(analysis / "paired_families.json")
    descriptive = read_json(analysis / "descriptive.json")
    ledger = read_json(analysis / "source_ledger.json")
    if (family.get("family_name") != "penalized_vs_original_priors"
            or family.get("evidence_status") != "post_hoc_clinical_methods_subset"
            or family.get("expected_contrasts") != 27
            or len(family.get("contrasts", [])) != 27
            or family.get("family_complete") != completion.get("family_complete")
            or descriptive.get("evidence_status") != "post_hoc_clinical_methods_subset"
            or len(descriptive.get("cell_rows", [])) != 450
            or len(descriptive.get("original_horseshoe_context", [])) != 75
            or ledger.get("full_extension_grid_verified") is not False):
        raise ValueError("focused comparison/descriptive content differs from its scope")
    rows = family["contrasts"]
    keys = [(r.get("dataset"), r.get("left"), r.get("right")) for r in rows]
    expected_keys = {(cohort, method, reference) for cohort in COHORTS
                     for method in PENALISED for reference in REFERENCES}
    if set(keys) != expected_keys or len(set(keys)) != 27:
        raise ValueError("focused comparison roster contains missing or extra contrasts")
    complete = all(r.get("status") == "estimable" and r.get("n_pairs") == 25 for r in rows)
    if family["family_complete"] != complete:
        raise ValueError("focused Holm family completion marker differs")
    if complete:
        if any("holm_adjusted_p" not in r or "holm_reject" not in r for r in rows):
            raise ValueError("complete Holm family lacks corrected inference")
    elif any("holm_reject" in r or "holm_adjusted_p" in r for r in rows):
        raise ValueError("incomplete Holm family must not have rejection claims")
    return completion, family, descriptive


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    """Write a stable table with explicit columns and no implicit index."""
    with path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def _estimate(value: Any) -> Any:
    """Use a stored calibration estimate only when that value is available."""
    return value.get("estimate") if isinstance(value, dict) else None


def _table_rows(family: dict, descriptive: dict) -> dict[str, tuple[list[dict], list[str]]]:
    contrast_rows = []
    for row in family["contrasts"]:
        effect = row.get("effect") or {}
        contrast_rows.append({
            "dataset": row["dataset"], "penalised_model": row["left"],
            "bayesian_reference": row["right"], "reference_label": row.get("horseshoe_reference") or "original",
            "status": row["status"], "accepted_pairs": row["n_pairs"],
            "planned_pairs": row["expected_pairs"],
            "mean_ibs_difference": effect.get("mean_difference"),
            "corrected_ci_lower": effect.get("confidence_lower"),
            "corrected_ci_upper": effect.get("confidence_upper"),
            "unadjusted_p": effect.get("p_value"),
            "holm_adjusted_p": row.get("holm_adjusted_p"),
            "holm_reject": row.get("holm_reject"),
            "superiority_language_permitted": row.get("superiority_language_permitted"),
        })
    contrast_columns = list(contrast_rows[0])
    cell_rows = []
    for row in descriptive["cell_rows"]:
        metrics = row.get("metrics") or {}
        flattened = {"dataset": row["dataset"], "model_key": row["model_key"],
                     "source": row["source"], "repeat": row["repeat"], "fold": row["fold"],
                     "status": row["status"], "n_train": row.get("n_train"),
                     "events_train": row.get("events_train"), "p": row.get("p"),
                     "cell_seconds": row.get("cell_seconds"), "fit_attempts": row.get("fit_attempts"),
                     "failure_type": row.get("failure_type")}
        flattened.update({name: metrics.get(name) for name in
                          ("ibs", "harrell_c_index", "uno_c_index", "mean_auc")})
        for index in range(3):
            horizon = (row.get("calibration") or [])[index] if len(row.get("calibration") or []) > index else {}
            flattened[f"h{index+1}_horizon"] = horizon.get("horizon")
            flattened[f"h{index+1}_n_known"] = horizon.get("n_known")
            for parameter in ("calibration_in_the_large", "intercept", "slope"):
                flattened[f"h{index+1}_{parameter}"] = _estimate(horizon.get(parameter))
        cell_rows.append(flattened)
    group_rows = []
    for row in descriptive["group_rows"]:
        statuses = row.get("status_counts", {})
        metrics = row.get("metrics_accepted_only", {})
        runtime = row.get("runtime_all_outcomes_seconds", {})
        group_rows.append({"dataset": row["dataset"], "model_key": row["model_key"],
                           "source": row["source"], "planned": row["planned"],
                           "accepted": row["accepted"], "failed": statuses.get("failed", 0),
                           "failed_diagnostics": statuses.get("failed_diagnostics", 0),
                           "accepted_ibs_median": metrics.get("ibs", {}).get("median"),
                           "accepted_ibs_q25": metrics.get("ibs", {}).get("q25"),
                           "accepted_ibs_q75": metrics.get("ibs", {}).get("q75"),
                           "observed_cell_seconds_median": runtime.get("median"),
                           "observed_cell_seconds_available": runtime.get("available")})
    context_rows = [{"dataset": row["dataset"], "model_key": row["model_key"],
                     "repeat": row["repeat"], "fold": row["fold"], "status": row["status"],
                     "failure_type": row.get("failure_type")}
                    for row in descriptive["original_horseshoe_context"]]
    return {
        "paired_contrasts": (contrast_rows, contrast_columns),
        "cell_metrics": (cell_rows, list(cell_rows[0])),
        "diagnostic_coverage": (group_rows, list(group_rows[0])),
        "original_horseshoe_context": (context_rows, list(context_rows[0])),
    }


def _save_figure(fig: plt.Figure, stage: Path, name: str, sources: list[str]) -> dict:
    fig.text(0.01, 0.01, "Post-hoc outcome-aware subset | three distinct internal-validation cohorts", fontsize=8)
    fixed_date = datetime(2000, 1, 1, tzinfo=UTC)
    fig.savefig(stage / f"{name}.pdf", bbox_inches="tight",
                metadata={"Title": name, "CreationDate": fixed_date, "ModDate": fixed_date})
    fig.savefig(stage / f"{name}.png", bbox_inches="tight", dpi=160)
    plt.close(fig)
    return {"name": name, "source_files": sources,
            "pdf_sha256": sha256_file(stage / f"{name}.pdf"),
            "png_sha256": sha256_file(stage / f"{name}.png")}


def _paired_plot(stage: Path, cohort: str, family: dict) -> dict:
    rows = [r for r in family["contrasts"] if r["dataset"] == cohort]
    if len(rows) != 9:
        raise ValueError(f"missing paired rows for {cohort}")
    fig, ax = plt.subplots(figsize=(11.5, 6.2))
    labels = []
    for index, row in enumerate(rows):
        labels.append(f"{MODEL_LABELS[row['left']]} - {MODEL_LABELS[row['right']]}")
        effect = row.get("effect")
        if row["status"] == "estimable" and effect:
            mid = effect["mean_difference"]
            lo, hi = effect["confidence_lower"], effect["confidence_upper"]
            ax.errorbar(mid, index, xerr=[[mid - lo], [hi - mid]], fmt="o", capsize=3, color="navy")
        else:
            ax.text(0.99, index, f"{row.get('n_pairs', 0)}/25 pairs; inference unavailable",
                    transform=ax.get_yaxis_transform(), ha="right", va="center", fontsize=8)
    ax.set_yticks(range(len(rows)), labels, fontsize=8)
    ax.invert_yaxis()
    ax.axvline(0, color="grey", linewidth=1, linestyle="--")
    ax.set_xlabel("Mean paired IBS difference (penalised minus Bayesian); repeated-CV 95% interval")
    family_status = "complete" if family["family_complete"] else "incomplete"
    ax.set_title(f"{cohort.upper()} | nine fixed contrasts; 27-test Holm family {family_status}")
    if cohort == "metabric":
        fig.text(0.01, 0.045, "Known same-individual METABRIC accession pair may cross folds.", fontsize=8)
    fig.tight_layout(rect=[0, 0.075, 1, 1])
    return _save_figure(fig, stage, f"paired_{cohort}", ["paired_families.json"])


def _coverage_plot(stage: Path, descriptive: dict) -> dict:
    fig, axes = plt.subplots(1, 3, figsize=(15, 6.4), sharex=True)
    for ax, cohort in zip(axes, COHORTS, strict=True):
        rows = [r for r in descriptive["group_rows"] if r["dataset"] == cohort]
        rows.sort(key=lambda row: (row["source"], row["model_key"]))
        if len(rows) != 7:
            raise ValueError(f"diagnostic coverage roster differs: {cohort}")
        labels = []
        for index, row in enumerate(rows):
            counts = Counter(row["status_counts"])
            if sum(counts.values()) != 25 or row["accepted"] != counts["complete"]:
                raise ValueError(f"diagnostic coverage denominator differs: {cohort}")
            ax.barh(index, counts["complete"], color="#277da1")
            ax.barh(index, counts["failed_diagnostics"], left=counts["complete"], color="#e9a03b")
            ax.barh(index, counts["failed"], left=counts["complete"] + counts["failed_diagnostics"],
                    color="#c44536")
            labels.append("Original horseshoe" if row["source"] == "original_horseshoe_context"
                          else MODEL_LABELS[row["model_key"]])
            ax.text(25.3, index, f"{counts['complete']}/25", va="center", fontsize=7)
        ax.set_yticks(range(len(rows)), labels, fontsize=7)
        ax.invert_yaxis()
        ax.set_xlim(0, 29)
        ax.set_title(cohort.upper())
        ax.set_xlabel("Planned outer folds")
    fig.suptitle("Outer-fold outcomes by model; denominator 25 per cohort")
    fig.legend(handles=[Patch(color="#277da1", label="Accepted"),
                        Patch(color="#e9a03b", label="Failed diagnostics"),
                        Patch(color="#c44536", label="Execution failure")],
               loc="lower center", bbox_to_anchor=(0.5, 0.04), ncol=3,
               frameon=False, fontsize=8)
    fig.tight_layout(rect=[0, 0.11, 1, 0.94])
    return _save_figure(fig, stage, "diagnostic_coverage", ["descriptive.json"])


def render(analysis: Path, output: Path) -> dict:
    """Produce fixed tables and PDF/PNG figures in a fresh immutable directory."""
    completion, family, descriptive = checked_analysis(analysis)
    if output.exists() or output.is_symlink():
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".clinical-render-", dir=output.parent))
    try:
        tables = []
        for name, (rows, columns) in _table_rows(family, descriptive).items():
            write_csv(stage / f"{name}.csv", rows, columns)
            tables.append({"name": name, "source_files":
                           ["paired_families.json"] if name == "paired_contrasts" else ["descriptive.json"],
                           "csv_sha256": sha256_file(stage / f"{name}.csv")})
        figures = [_paired_plot(stage, cohort, family) for cohort in COHORTS]
        figures.append(_coverage_plot(stage, descriptive))
        if [item["name"] for item in figures] != list(FIGURES):
            raise ValueError("focused figure roster differs")
        lineage = {"schema_version": 1, "evidence_status": "post_hoc_clinical_methods_subset",
                   "source_completion_sha256": sha256_file(analysis / "completion.json"),
                   "source_aggregates_sha256": completion["aggregate_sha256"],
                   "renderer_sha256": sha256_file(Path(__file__)),
                   "figures": figures, "tables": tables, "visual_review": "pending",
                   "limitations": ["outcome-aware post-hoc subset", "distinct internal-validation cohorts",
                                   "Bayesian PWE versus penalised Cox architecture confounding",
                                   "clinical METABRIC known same-individual accession pair exposure",
                                   "no decision-curve or clinical-utility claim"],
                   "full_extension_grid_verified": False}
        write_json_new(stage / "lineage.json", lineage)
        atomic_new_directory(stage, output)
        return lineage
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def main() -> None:
    """Read completed analysis evidence and render the bounded study only."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = render(args.analysis.resolve(), args.output.absolute())
    print(json.dumps({"figures": len(result["figures"]), "tables": len(result["tables"]),
                      "output": str(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
