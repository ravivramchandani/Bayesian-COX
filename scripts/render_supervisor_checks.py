"""Report frozen predictive checks and calibration intervals without fitting models."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import platform
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from src.rendering.diagnostics import _predictive_check_rows
from src.rendering.metrics import _calibration_rows
from src.rendering.verification import sha256_file, verify_frozen_run

DATASETS = ("gbsg2", "metabric", "whas500")
PRIORS = ("bayesian_normal", "bayesian_horseshoe", "bayesian_spike_slab")
COHORT_LABELS = {"gbsg2": "GBSG2", "metabric": "METABRIC", "whas500": "WHAS500"}
PRIOR_LABELS = {
    "bayesian_normal": "Normal",
    "bayesian_horseshoe": "Horseshoe",
    "bayesian_spike_slab": "Spike-and-Slab",
}
COUNT_CHECK = "posterior_predictive_replicated_event_count"
SURVIVAL_CHECK = "posterior_fitted_survival_comparison_not_replicated_data"


def summarise_predictive_checks(rows: pd.DataFrame) -> pd.DataFrame:
    """Summarise saved checks by cohort/prior, retaining their distinct denominators.

    Args:
        rows: The existing renderer's long predictive-check table, restricted
            there to complete Bayesian cells.

    Returns:
        Counts of observed quantities within their stored central intervals,
        plus mean and maximum absolute fitted-survival/Kaplan-Meier differences.

    Raises:
        ValueError: If a group lacks one total, six interval-count checks or
            three fitted-survival checks per accepted fit, or a saved interval
            flag disagrees with its numerical bounds.
    """
    summaries: list[dict[str, Any]] = []
    for (dataset, model), group in rows.groupby(["dataset", "model_key"], sort=True):
        count_rows = group[group["check"] == COUNT_CHECK]
        totals = count_rows[count_rows["interval"].astype(str) == "total"]
        intervals = count_rows[count_rows["interval"].astype(str) != "total"]
        survival = group[group["check"] == SURVIVAL_CHECK]
        n_fits = len(totals)
        if n_fits == 0 or len(intervals) != 6 * n_fits or len(survival) != 3 * n_fits:
            raise ValueError(f"incomplete stored predictive checks: {dataset}/{model}")
        for checked in (count_rows, survival):
            observed_covered = (checked["lower_95"] <= checked["observed"]) & (
                checked["observed"] <= checked["upper_95"]
            )
            if not (observed_covered == checked["observed_covered"].astype(bool)).all():
                raise ValueError(f"stored interval flag disagrees: {dataset}/{model}")
        absolute_difference = (survival["predicted"] - survival["observed"]).abs()
        summaries.append(
            {
                "dataset": dataset,
                "model_key": model,
                "accepted_fits": n_fits,
                "total_count_checks": len(totals),
                "total_counts_within_interval": int(totals["observed_covered"].sum()),
                "interval_count_checks": len(intervals),
                "interval_counts_within_interval": int(intervals["observed_covered"].sum()),
                "fitted_survival_checks": len(survival),
                "km_within_fitted_survival_interval": int(survival["observed_covered"].sum()),
                "mean_absolute_survival_difference": float(absolute_difference.mean()),
                "max_absolute_survival_difference": float(absolute_difference.max()),
            }
        )
    return pd.DataFrame(summaries)


def _predictive_table(summary: pd.DataFrame) -> str:
    lines = [
        r"\begin{table}[htbp]",
        r"\centering\footnotesize",
        r"\setlength{\tabcolsep}{4pt}",
        r"\caption{Training-data predictive checks for accepted Bayesian fits.}",
        r"\label{tab:sup-predictive-checks}",
        r"\begin{tabular}{@{}llrrrrr@{}}\toprule",
        r"Cohort & Prior & \shortstack{Accepted\\fits} & \shortstack{Total count\\within interval} & \shortstack{Interval counts\\within interval} & \shortstack{KM within\\fitted interval} & \shortstack{Mean absolute\\survival difference}\\\midrule",
    ]
    for dataset in DATASETS:
        for prior in PRIORS:
            row = summary[(summary["dataset"] == dataset) & (summary["model_key"] == prior)].iloc[0]
            lines.append(
                f"{COHORT_LABELS[dataset]} & {PRIOR_LABELS[prior]} & {int(row.accepted_fits)} & "
                f"{int(row.total_counts_within_interval)}/{int(row.total_count_checks)} & "
                f"{int(row.interval_counts_within_interval)}/{int(row.interval_count_checks)} & "
                f"{int(row.km_within_fitted_survival_interval)}/{int(row.fitted_survival_checks)} & "
                f"{row.mean_absolute_survival_difference:.4f} \\\\"
            )
    lines.extend(
        [
            r"\bottomrule\end{tabular}",
            r"\par\smallskip\begin{minipage}{\linewidth}\footnotesize Counts use the stored central 95\% intervals. Poisson replication conditions on observed exposures. The fitted-survival check compares training Kaplan--Meier estimates with posterior intervals for mean fitted survival at three training-event quartiles. The final column averages $|\overline S(t)-\widehat S_{\mathrm{KM}}(t)|$ over those checks. Frequencies are descriptive across overlapping training fits.\end{minipage}",
            r"\end{table}",
        ]
    )
    return "\n".join(lines) + "\n"


def _calibration_table(selected: pd.DataFrame) -> str:
    lines = [
        r"\begin{table}[htbp]",
        r"\centering\small",
        r"\caption{Fold-specific calibration estimates and bootstrap intervals for the first outer Normal-prior fit.}",
        r"\label{tab:sup-calibration-bootstrap}",
        r"\begin{tabular}{@{}llrrr@{}}\toprule",
        r"Cohort & Parameter & Estimate & Lower 95\% & Upper 95\%\\\midrule",
    ]
    parameter_labels = {
        "calibration_in_the_large": "Calibration-in-the-large",
        "intercept": "Joint intercept",
        "slope": "Joint slope",
    }
    for dataset in DATASETS:
        block = selected[selected["dataset"] == dataset]
        for parameter in parameter_labels:
            row = block[block["parameter"] == parameter].iloc[0]
            lines.append(
                f"{COHORT_LABELS[dataset]} & {parameter_labels[parameter]} & "
                f"{row.estimate:+.3f} & {row.confidence_lower:+.3f} & {row.confidence_upper:+.3f} \\\\"
            )
    horizons = []
    for dataset in DATASETS:
        block = selected[selected["dataset"] == dataset]
        row = block.iloc[0]
        unit = "months" if dataset == "metabric" else "days"
        horizons.append(f"{COHORT_LABELS[dataset]} {row.horizon:g} {unit}")
    lines.extend(
        [
            r"\bottomrule\end{tabular}",
            r"\par\smallskip\begin{minipage}{\linewidth}\footnotesize Repeat 1, fold 1; middle training-event horizon: "
            + "; ".join(horizons)
            + r". Each estimate had 500 successful bootstrap replicates. Models were held fixed; training observations were resampled to re-estimate censoring and validation observations were resampled with their predictions. These are within-fold bootstrap intervals, distinct from the between-fold standard deviations in Figure~\ref{fig:ravi-calibration}.\end{minipage}",
            r"\end{table}",
        ]
    )
    return "\n".join(lines) + "\n"


def _calibration_figure(curves: pd.DataFrame, output: Path) -> None:
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "pdf.fonttype": 42})
    figure, axes = plt.subplots(1, 3, figsize=(7.2, 2.8), sharex=True, sharey=True)
    for axis, dataset in zip(axes, DATASETS, strict=True):
        block = curves[curves["dataset"] == dataset].sort_values("bin")
        predicted = block["mean_predicted_survival"].to_numpy()
        observed = block["observed_survival"].to_numpy()
        lower = block["observed_lower"].to_numpy()
        upper = block["observed_upper"].to_numpy()
        axis.plot([0, 1], [0, 1], color="#777777", linestyle="--", linewidth=1)
        axis.errorbar(
            predicted,
            observed,
            yerr=[observed - lower, upper - observed],
            color="#23628A",
            ecolor="#8CAFC4",
            marker="o",
            markersize=4,
            capsize=3,
            linewidth=1.2,
        )
        horizon = float(block.iloc[0]["horizon"])
        unit = "months" if dataset == "metabric" else "days"
        axis.set_title(f"{COHORT_LABELS[dataset]}: {horizon:g} {unit}")
        axis.set_xlim(0, 1)
        axis.set_ylim(0, 1)
        axis.set_xlabel("Mean predicted survival")
        axis.grid(alpha=0.18)
        axis.set_aspect("equal", adjustable="box")
    axes[0].set_ylabel("Observed Kaplan-Meier survival")
    figure.tight_layout()
    fixed_date = dt.datetime(2026, 11, 19, tzinfo=dt.UTC)
    figure.savefig(output, metadata={"CreationDate": fixed_date, "ModDate": fixed_date})
    plt.close(figure)


def render_saved_checks(run_dir: Path, output_dir: Path) -> dict[str, Any]:
    """Verify the original cells and export their stored checks to a new directory.

    Args:
        run_dir: Original confirmatory run with manifest and completion records.
        output_dir: New or empty directory receiving only derived report files.

    Returns:
        Descriptive summary and provenance of the generated outputs.

    Raises:
        ValueError: If the output directory is nonempty or accepted check counts
            differ from the complete original analysis.
    """
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("output directory must be new or empty")
    run = verify_frozen_run(run_dir)
    if run.mode != "confirmatory" or len(run.cells) != 450:
        raise ValueError("expected the 450-cell original confirmatory run")
    predictive = _predictive_check_rows(run)
    parameters, curves = _calibration_rows(run)
    summary = summarise_predictive_checks(predictive)
    expected = {
        (dataset, prior): (7 if dataset == "gbsg2" else 23 if dataset == "metabric" else 25)
        if prior == "bayesian_horseshoe" else 25
        for dataset in DATASETS for prior in PRIORS
    }
    actual = {(r.dataset, r.model_key): int(r.accepted_fits) for r in summary.itertuples()}
    if actual != expected or len(parameters) != 430 * 3 * 3 or len(curves) != 430 * 3 * 5:
        raise ValueError("saved check coverage differs from the original accepted grid")
    selected = parameters[
        (parameters["model_key"] == "bayesian_normal")
        & (parameters["repeat"] == 1)
        & (parameters["fold"] == 1)
        & (parameters["horizon_index"] == 2)
    ].copy()
    selected_curves = curves[
        (curves["model_key"] == "bayesian_normal")
        & (curves["repeat"] == 1)
        & (curves["fold"] == 1)
        & (curves["horizon_index"] == 2)
    ].copy()
    if len(selected) != 9 or len(selected_curves) != 15:
        raise ValueError("first-fold calibration examples are incomplete")
    if set(selected["n_bootstrap_successful"]) != {500}:
        raise ValueError("representative calibration intervals lack 500 bootstrap replicates")
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, table in {
        "predictive_checks_all.csv": predictive,
        "predictive_check_summary.csv": summary,
        "calibration_parameters_all.csv": parameters,
        "calibration_curves_all.csv": curves,
        "calibration_bootstrap_examples.csv": selected,
        "calibration_curve_examples.csv": selected_curves,
    }.items():
        table.to_csv(output_dir / name, index=False, float_format="%.17g")
    (output_dir / "table_predictive_checks.tex").write_text(_predictive_table(summary))
    (output_dir / "table_calibration_bootstrap.tex").write_text(_calibration_table(selected))
    _calibration_figure(selected_curves, output_dir / "figure_calibration_examples.pdf")
    result = {
        "schema_version": "1.0.0",
        "fitting_performed": False,
        "simulation_performed": False,
        "runtime": {
            "python": platform.python_version(),
            "matplotlib": matplotlib.__version__,
            "pandas": pd.__version__,
        },
        "verified_original_cells": len(run.cells),
        "accepted_bayesian_fits": int(summary["accepted_fits"].sum()),
        "accepted_calibration_cells": int(len(parameters) / 9),
        "predictive_summary": summary.to_dict(orient="records"),
        "calibration_examples": selected.to_dict(orient="records"),
        "source_sha256": run.source_hashes,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "definitions": {
            "count_intervals": "Stored central 95% replicated-Poisson intervals at observed exposures; descriptive checks, not calibrated hypothesis tests.",
            "fitted_survival_intervals": "Central 95% posterior interval of training-average fitted survival; compared with training Kaplan-Meier at three event-time quartiles.",
            "calibration_parameter_intervals": "Stored within-cell bootstrap intervals; independent training/validation resampling with fitted model held fixed.",
            "calibration_curve_bars": "Stored 95% within-bin Kaplan-Meier intervals, not calibration-parameter bootstrap intervals.",
        },
        "outputs": {
            path.name: {"sha256": sha256_file(path), "bytes": path.stat().st_size}
            for path in sorted(output_dir.iterdir()) if path.is_file()
        },
    }
    (output_dir / "provenance.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return result


def main() -> None:
    """Parse the input/output locations and render the stored checks."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    result = render_saved_checks(args.run_dir, args.output_dir)
    print(json.dumps({key: result[key] for key in ("verified_original_cells", "accepted_bayesian_fits", "accepted_calibration_cells")}))


if __name__ == "__main__":
    main()
