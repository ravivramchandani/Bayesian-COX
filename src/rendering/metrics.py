"""Tabulate and render cohort flow, prediction metrics and paired prior contrasts."""

from __future__ import annotations

import math
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .constants import COLORS, METRIC_LABELS, MODEL_LABELS, PRIOR_DISPLAY_LABELS
from .outputs import OutputRegistry, _cell_sources, _save_figure, _write_table
from .verification import FrozenRun, _finite, _source


def _runtime_rows(run: FrozenRun) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for relative, cell in run.cells:
        attempts = cell.get("fit_attempts")
        attempts = attempts if isinstance(attempts, list) else []
        last = attempts[-1] if attempts else {}
        diagnostics = last.get("diagnostics") if isinstance(last, dict) else None
        diagnostics = diagnostics if isinstance(diagnostics, dict) else {}
        rows.append(
            {
                "dataset": cell["dataset"],
                "model_key": cell["model_key"],
                "model": cell.get("model", MODEL_LABELS.get(cell["model_key"], cell["model_key"])),
                "repeat": cell["repeat"],
                "fold": cell["fold"],
                "status": cell["status"],
                "total_seconds": _finite(cell["total_seconds"], field="total_seconds"),
                "fit_attempts": len(attempts),
                "diagnostic_converged": diagnostics.get("converged"),
                "r_hat_max": diagnostics.get("r_hat_max"),
                "ess_bulk_min": diagnostics.get("ess_bulk_min"),
                "ess_tail_min": diagnostics.get("ess_tail_min"),
                "divergences": diagnostics.get("n_divergent"),
                "bfmi_min": diagnostics.get("bfmi_min"),
                "max_tree_depth_hits": diagnostics.get("n_max_tree_depth"),
                "failure_message": cell.get("message"),
                "source_cell": relative,
                "cell_content_sha256": cell["cell_content_sha256"],
            }
        )
    return pd.DataFrame(rows)


def _render_runtime(run: FrozenRun, registry: OutputRegistry, *, rehearsal: bool) -> None:
    table = _runtime_rows(run)
    sources = _cell_sources(
        run,
        run.cells,
        ["status", "total_seconds", "fit_attempts", "message"],
    )
    _write_table(
        table,
        registry.output_dir / "tables" / "runtime_diagnostic_failures",
        registry,
        sources=sources,
        note=(
            "REHEARSAL ONLY: resource and failure report; no performance evidence"
            if rehearsal
            else "Cell runtimes, fit attempts, diagnostic gates and failures"
        ),
    )

    figure, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    complete_times = table.loc[table["total_seconds"] > 0]
    models = sorted(complete_times["model_key"].unique())
    data = [
        complete_times.loc[complete_times["model_key"] == model, "total_seconds"].to_numpy()
        for model in models
    ]
    if data:
        axes[0].boxplot(data, tick_labels=[MODEL_LABELS.get(m, m) for m in models])
        axes[0].tick_params(axis="x", rotation=35)
        plt.setp(axes[0].get_xticklabels(), ha="right")
        axes[0].set_yscale("log")
        axes[0].set_ylabel("Total cell runtime (seconds, log scale)")
    else:
        axes[0].text(0.5, 0.5, "No runtime records", ha="center", va="center")
    status = (
        table.groupby(["model_key", "status"], sort=True)
        .size()
        .unstack(fill_value=0)
        .reindex(models, fill_value=0)
    )
    bottom = np.zeros(len(status), dtype=float)
    for index, state in enumerate(status.columns):
        values = status[state].to_numpy(float)
        axes[1].bar(
            np.arange(len(status)),
            values,
            bottom=bottom,
            label=state.replace("_", " "),
            color=COLORS[index % len(COLORS)],
        )
        bottom += values
    axes[1].set_xticks(
        np.arange(len(status)),
        [MODEL_LABELS.get(value, value) for value in status.index],
        rotation=35,
        ha="right",
    )
    axes[1].set_ylabel("Stored cells")
    axes[1].legend(frameon=False)
    prefix = "REHEARSAL ONLY — " if rehearsal else ""
    figure.suptitle(prefix + "Runtime and fit-status audit")
    _save_figure(
        figure,
        registry.output_dir / "figures" / "runtime_diagnostic_failures",
        registry,
        title=prefix + "Runtime and fit-status audit",
        sources=sources,
        note=(
            "Runtime planning artifact; rehearsal estimates are not scientific evidence"
            if rehearsal
            else "Runtime and prespecified fit/diagnostic status from frozen cells"
        ),
    )


def _cohort_rows(run: FrozenRun) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for dataset in sorted({str(cell["dataset"]) for _, cell in run.cells}):
        cohort_cells = [cell for _, cell in run.cells if cell["dataset"] == dataset]
        counts = {
            (
                int(cell["n_train"]) + int(cell["n_validation"]),
                int(cell["events_train"]) + int(cell["events_validation"]),
            )
            for cell in cohort_cells
        }
        if len(counts) != 1:
            raise RuntimeError(f"{dataset} cells disagree on cohort/event counts")
        n_subjects, n_events = counts.pop()
        status = pd.Series([cell["status"] for cell in cohort_cells]).value_counts()
        records.append(
            {
                "dataset": dataset,
                "eligible_subjects": n_subjects,
                "observed_events": n_events,
                "censored": n_subjects - n_events,
                "event_fraction": n_events / n_subjects,
                "planned_cells": len(cohort_cells),
                "complete_cells": int(status.get("complete", 0)),
                "failed_cells": int(status.get("failed", 0) + status.get("failed_diagnostics", 0)),
            }
        )
    return pd.DataFrame(records)


def _render_cohort_flow(run: FrozenRun, registry: OutputRegistry) -> None:
    table = _cohort_rows(run)
    sources = _cell_sources(
        run,
        run.cells,
        [
            "n_train",
            "n_validation",
            "events_train",
            "events_validation",
            "status",
        ],
    )
    _write_table(
        table,
        registry.output_dir / "tables" / "cohort_flow_counts",
        registry,
        sources=sources,
        note="Cohort inclusion, outcome and analysis-cell flow counts",
    )
    figure, axes = plt.subplots(1, 2, figsize=(10, 4.2))
    positions = np.arange(len(table))
    axes[0].bar(positions, table["observed_events"], label="Observed event", color=COLORS[1])
    axes[0].bar(
        positions,
        table["censored"],
        bottom=table["observed_events"],
        label="Censored",
        color=COLORS[0],
    )
    axes[0].set_xticks(positions, table["dataset"].str.upper())
    axes[0].set_ylabel("Eligible subjects")
    axes[0].legend(frameon=False)
    axes[1].bar(positions, table["complete_cells"], label="Complete", color=COLORS[2])
    axes[1].bar(
        positions,
        table["failed_cells"],
        bottom=table["complete_cells"],
        label="Failed/diagnostic failure",
        color=COLORS[1],
    )
    axes[1].set_xticks(positions, table["dataset"].str.upper())
    axes[1].set_ylabel("Frozen analysis cells")
    axes[1].legend(frameon=False)
    figure.suptitle("Cohort and analysis-cell flow")
    _save_figure(
        figure,
        registry.output_dir / "figures" / "cohort_flow_counts",
        registry,
        title="Cohort and analysis-cell flow",
        sources=sources,
        note="Counts reconstructed consistently from every frozen outer-fold cell",
    )


def _metric_rows(run: FrozenRun) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for relative, cell in run.cells:
        if cell["status"] != "complete":
            continue
        metrics = cell.get("metrics")
        if not isinstance(metrics, dict):
            raise ValueError(f"complete cell has no metrics mapping: {relative}")
        for key in METRIC_LABELS:
            rows.append(
                {
                    "dataset": cell["dataset"],
                    "model_key": cell["model_key"],
                    "model": cell.get(
                        "model", MODEL_LABELS.get(cell["model_key"], cell["model_key"])
                    ),
                    "repeat": cell["repeat"],
                    "fold": cell["fold"],
                    "metric": key,
                    "metric_label": METRIC_LABELS[key],
                    "value": _finite(metrics[key], field=f"metrics.{key}"),
                    "source_cell": relative,
                    "cell_content_sha256": cell["cell_content_sha256"],
                }
            )
    return pd.DataFrame(rows)


def _metric_summary(rows: pd.DataFrame) -> pd.DataFrame:
    if rows.empty:
        return pd.DataFrame(
            columns=[
                "dataset",
                "model_key",
                "model",
                "metric",
                "n_folds",
                "mean",
                "standard_deviation",
                "median",
                "quartile_25",
                "quartile_75",
            ]
        )
    grouped = rows.groupby(["dataset", "model_key", "model", "metric"], sort=True, observed=True)[
        "value"
    ]
    summary = grouped.agg(
        n_folds="count",
        mean="mean",
        standard_deviation="std",
        median="median",
        quartile_25=lambda values: values.quantile(0.25),
        quartile_75=lambda values: values.quantile(0.75),
    )
    return summary.reset_index()


def _render_fold_metrics(run: FrozenRun, registry: OutputRegistry) -> None:
    rows = _metric_rows(run)
    summary = _metric_summary(rows)
    selected = [(relative, cell) for relative, cell in run.cells if cell["status"] == "complete"]
    sources = _cell_sources(run, selected, ["metrics"])
    _write_table(
        rows,
        registry.output_dir / "tables" / "fold_metrics_long",
        registry,
        sources=sources,
        note="All complete-cell fold metrics; no pooling across cohorts",
    )
    _write_table(
        summary,
        registry.output_dir / "tables" / "fold_metric_summary",
        registry,
        sources=sources,
        note="Descriptive fold-metric summaries derived from the long table",
    )

    metrics = list(METRIC_LABELS)
    figure, axes = plt.subplots(2, 2, figsize=(13, 8.5))
    datasets = sorted(rows["dataset"].unique()) if not rows.empty else []
    models = sorted(rows["model_key"].unique()) if not rows.empty else []
    compact_model_labels = {
        "bayesian_normal": "Normal prior",
        "bayesian_horseshoe": "Horseshoe prior",
        "bayesian_spike_slab": "Spike/slab prior",
        "cox_ph": "Cox PH",
        "deepsurv": "DeepSurv",
        "random_survival_forest": "Survival forest",
    }
    for metric, axis in zip(metrics, axes.flat, strict=True):
        selected_metric = rows[rows["metric"] == metric]
        box_data: list[np.ndarray] = []
        labels: list[str] = []
        colors: list[str] = []
        for dataset_index, dataset in enumerate(datasets):
            for model in models:
                values = selected_metric.loc[
                    (selected_metric["dataset"] == dataset)
                    & (selected_metric["model_key"] == model),
                    "value",
                ].to_numpy()
                if len(values):
                    box_data.append(values)
                    labels.append(f"{dataset.upper()}\n{compact_model_labels.get(model, model)}")
                    colors.append(COLORS[dataset_index % len(COLORS)])
        if box_data:
            boxes = axis.boxplot(box_data, patch_artist=True, tick_labels=labels)
            for patch, color in zip(boxes["boxes"], colors, strict=True):
                patch.set_facecolor(color)
                patch.set_alpha(0.5)
            axis.tick_params(axis="x", rotation=90, labelsize=7)
        else:
            axis.text(0.5, 0.5, "No complete metric cells", ha="center", va="center")
        axis.set_title(METRIC_LABELS[metric])
        axis.set_ylabel("Outer-fold estimate")
    figure.suptitle("Outer-fold metric distributions")
    _save_figure(
        figure,
        registry.output_dir / "figures" / "fold_metric_distributions",
        registry,
        title="Outer-fold metric distributions",
        sources=sources,
        note="Distributions retain the repeated-CV fold as the displayed unit",
    )

    discrimination = rows[rows["metric"].isin(["uno_c_index", "harrell_c_index", "mean_auc"])]
    discrimination_summary = _metric_summary(discrimination)
    _write_table(
        discrimination_summary,
        registry.output_dir / "tables" / "discrimination_summary",
        registry,
        sources=sources,
        note="Descriptive discrimination summary by cohort and model",
    )
    figure, axes = plt.subplots(
        max(1, len(datasets)), 1, figsize=(10, max(3.6, 3.2 * len(datasets))), squeeze=False
    )
    for axis, dataset in zip(axes.flat, datasets, strict=False):
        subset = discrimination_summary[discrimination_summary["dataset"] == dataset]
        x = np.arange(len(models), dtype=float)
        width = 0.24
        for metric_index, metric in enumerate(("uno_c_index", "harrell_c_index", "mean_auc")):
            means = []
            errors = []
            for model in models:
                match = subset[(subset["model_key"] == model) & (subset["metric"] == metric)]
                means.append(float(match["mean"].iloc[0]) if len(match) else np.nan)
                sd = float(match["standard_deviation"].iloc[0]) if len(match) else np.nan
                errors.append(sd if math.isfinite(sd) else 0.0)
            axis.errorbar(
                x + (metric_index - 1) * width,
                means,
                yerr=errors,
                fmt="o",
                capsize=3,
                color=COLORS[metric_index],
                label=METRIC_LABELS[metric],
            )
        axis.set_xticks(
            x, [MODEL_LABELS.get(model, model) for model in models], rotation=30, ha="right"
        )
        axis.set_ylabel("Estimate (mean ± fold SD)")
        axis.set_title(dataset.upper())
        axis.legend(frameon=False, ncols=3)
    figure.suptitle("Discrimination across outer folds")
    _save_figure(
        figure,
        registry.output_dir / "figures" / "discrimination",
        registry,
        title="Discrimination across outer folds",
        sources=sources,
        note="Mean and fold standard deviation are descriptive, not independent-sample intervals",
    )


def _paired_ibs_rows(run: FrozenRun) -> pd.DataFrame:
    primary = run.inference.get("primary")
    if not isinstance(primary, list):
        raise ValueError("inference artifact has no primary contrast list")
    rows: list[dict[str, Any]] = []
    for contrast in primary:
        effect = contrast.get("ibs")
        effect = effect if isinstance(effect, dict) else {}
        rows.append(
            {
                "dataset": contrast["dataset"],
                "model_a": contrast["model_a"],
                "model_b": contrast["model_b"],
                "direction": contrast["contrast_direction"],
                "n_paired_folds": contrast["n_paired_folds"],
                "status": contrast.get("status", "complete" if effect else "unavailable"),
                "mean_ibs_difference": effect.get("mean_difference"),
                "corrected_standard_error": effect.get("corrected_standard_error"),
                "confidence_lower": effect.get("confidence_lower"),
                "confidence_upper": effect.get("confidence_upper"),
                "p_value": effect.get("p_value"),
                "holm_adjusted_p": contrast.get("holm_adjusted_p"),
                "holm_reject_0_05": contrast.get("holm_reject_0_05"),
                "superiority_language_permitted": contrast.get(
                    "superiority_language_permitted", False
                ),
            }
        )
    columns = [
        "dataset",
        "model_a",
        "model_b",
        "direction",
        "n_paired_folds",
        "status",
        "mean_ibs_difference",
        "corrected_standard_error",
        "confidence_lower",
        "confidence_upper",
        "p_value",
        "holm_adjusted_p",
        "holm_reject_0_05",
        "superiority_language_permitted",
    ]
    return pd.DataFrame(rows, columns=columns)


def _render_paired_ibs(run: FrozenRun, registry: OutputRegistry) -> None:
    table = _paired_ibs_rows(run)
    sources = [_source(run, "inference.json", ["primary", "holm_family_complete"])]
    _write_table(
        table,
        registry.output_dir / "tables" / "paired_ibs_effects",
        registry,
        sources=sources,
        note="Nadeau–Bengio corrected paired Bayesian-prior IBS effects",
    )
    height = max(3.5, 0.45 * max(1, len(table)) + 1.8)
    figure, axis = plt.subplots(figsize=(9, height))
    if table.empty:
        axis.text(
            0.5,
            0.5,
            "No complete paired IBS inference in the frozen artifact",
            ha="center",
            va="center",
        )
        axis.set_axis_off()
    else:
        ordered = table.reset_index(drop=True)
        available = ordered["mean_ibs_difference"].notna()
        y = np.flatnonzero(available.to_numpy())
        estimates = ordered.loc[available, "mean_ibs_difference"].to_numpy(float)
        lower = ordered.loc[available, "confidence_lower"].to_numpy(float)
        upper = ordered.loc[available, "confidence_upper"].to_numpy(float)
        axis.errorbar(
            estimates,
            y,
            xerr=np.vstack([estimates - lower, upper - estimates]),
            fmt="o",
            capsize=3,
            color=COLORS[0],
        )
        axis.axvline(0.0, color="black", linewidth=0.8)
        labels = [
            f"{row.dataset.upper()}: {PRIOR_DISPLAY_LABELS.get(row.model_a, row.model_a)} − {PRIOR_DISPLAY_LABELS.get(row.model_b, row.model_b)}"
            for row in ordered.itertuples(index=False)
        ]
        axis.set_yticks(np.arange(len(ordered)), labels)
        for row_index in np.flatnonzero(~available.to_numpy()):
            axis.text(
                0.02,
                row_index,
                f"Not estimable ({int(ordered.iloc[row_index]['n_paired_folds'])}/25 paired folds)",
                transform=axis.get_yaxis_transform(),
                color="dimgray",
                fontsize=8,
            )
        axis.set_ylim(len(ordered) - 0.5, -0.5)
        axis.set_xlabel("Corrected mean IBS difference (95% CI; lower favours model A)")
    axis.set_title("Primary paired IBS effects")
    _save_figure(
        figure,
        registry.output_dir / "figures" / "paired_ibs_effects",
        registry,
        title="Primary paired IBS effects",
        sources=sources,
        note="All primary contrasts are shown; missing inference is labelled without a fabricated estimate",
    )


def _calibration_rows(run: FrozenRun) -> tuple[pd.DataFrame, pd.DataFrame]:
    parameters: list[dict[str, Any]] = []
    curves: list[dict[str, Any]] = []
    for relative, cell in run.cells:
        if cell["status"] != "complete":
            continue
        calibration = cell.get("metrics", {}).get("calibration")
        if not isinstance(calibration, list):
            raise ValueError(f"complete cell has no calibration list: {relative}")
        for horizon_index, item in enumerate(calibration, start=1):
            summary = item.get("summary")
            curve = item.get("curve")
            if not isinstance(summary, dict) or not isinstance(curve, dict):
                raise ValueError(f"malformed calibration record: {relative}")
            base = {
                "dataset": cell["dataset"],
                "model_key": cell["model_key"],
                "model": cell.get("model", MODEL_LABELS.get(cell["model_key"], cell["model_key"])),
                "repeat": cell["repeat"],
                "fold": cell["fold"],
                "horizon_index": horizon_index,
                "horizon": summary["horizon"],
                "source_cell": relative,
                "cell_content_sha256": cell["cell_content_sha256"],
            }
            for parameter in ("calibration_in_the_large", "intercept", "slope"):
                estimate = summary[parameter]
                parameters.append(
                    {
                        **base,
                        "parameter": parameter,
                        "estimate": estimate["estimate"],
                        "confidence_lower": estimate["lower"],
                        "confidence_upper": estimate["upper"],
                        "n_bootstrap_successful": summary.get("n_bootstrap_successful"),
                    }
                )
            for bin_record in curve.get("bins", []):
                curves.append(
                    {
                        **base,
                        "bin": bin_record["bin"],
                        "n": bin_record["n"],
                        "mean_predicted_survival": bin_record["mean_predicted_survival"],
                        "observed_survival": bin_record["observed_survival"],
                        "observed_lower": bin_record["observed_lower"],
                        "observed_upper": bin_record["observed_upper"],
                    }
                )
    return pd.DataFrame(parameters), pd.DataFrame(curves)


def _render_calibration(run: FrozenRun, registry: OutputRegistry) -> None:
    parameters, curves = _calibration_rows(run)
    selected = [(relative, cell) for relative, cell in run.cells if cell["status"] == "complete"]
    sources = _cell_sources(run, selected, ["metrics.calibration"])
    _write_table(
        parameters,
        registry.output_dir / "tables" / "calibration_parameters",
        registry,
        sources=sources,
        note="Calibration-in-the-large, intercept and slope with cell-level intervals",
    )
    _write_table(
        curves,
        registry.output_dir / "tables" / "calibration_curves",
        registry,
        sources=sources,
        note="All frozen calibration-bin estimates and Kaplan–Meier intervals",
    )

    datasets = sorted(curves["dataset"].unique()) if not curves.empty else []
    horizons = sorted(curves["horizon_index"].unique()) if not curves.empty else []
    figure, axes = plt.subplots(
        max(1, len(datasets)),
        max(1, len(horizons)),
        figsize=(4 * max(1, len(horizons)), 3.6 * max(1, len(datasets))),
        squeeze=False,
        sharex=True,
        sharey=True,
    )
    if curves.empty:
        axes[0, 0].text(0.5, 0.5, "No complete calibration curves", ha="center", va="center")
    for row_index, dataset in enumerate(datasets):
        for column_index, horizon_index in enumerate(horizons):
            axis = axes[row_index, column_index]
            subset = curves[
                (curves["dataset"] == dataset) & (curves["horizon_index"] == horizon_index)
            ]
            for model_index, (model, group) in enumerate(subset.groupby("model_key", sort=True)):
                averaged = (
                    group.groupby("bin", sort=True)[
                        ["mean_predicted_survival", "observed_survival"]
                    ]
                    .mean()
                    .reset_index()
                )
                axis.plot(
                    averaged["mean_predicted_survival"],
                    averaged["observed_survival"],
                    marker="o",
                    linewidth=1.2,
                    markersize=3,
                    label=MODEL_LABELS.get(model, model),
                    color=COLORS[model_index % len(COLORS)],
                )
            axis.plot([0, 1], [0, 1], linestyle="--", color="black", linewidth=0.8)
            axis.set_xlim(0, 1)
            axis.set_ylim(0, 1)
            axis.set_title(f"{dataset.upper()} — horizon quantile {horizon_index}")
            axis.set_xlabel("Mean predicted survival")
            axis.set_ylabel("Observed survival")
            if row_index == 0 and column_index == 0:
                axis.legend(frameon=False, fontsize=6)
    figure.suptitle("Calibration curves across outer folds")
    _save_figure(
        figure,
        registry.output_dir / "figures" / "calibration_curves",
        registry,
        title="Calibration curves across outer folds",
        sources=sources,
        note="Lines average corresponding calibration bins descriptively across outer folds",
    )

    figure, axes = plt.subplots(
        max(1, len(datasets)), 2, figsize=(11, max(3.6, 3.4 * len(datasets))), squeeze=False
    )
    models = sorted(parameters["model_key"].unique()) if not parameters.empty else []
    for row_index, dataset in enumerate(datasets):
        for column_index, parameter in enumerate(("intercept", "slope")):
            axis = axes[row_index, column_index]
            subset = parameters[
                (parameters["dataset"] == dataset) & (parameters["parameter"] == parameter)
            ]
            for model_index, model in enumerate(models):
                model_rows = subset[subset["model_key"] == model]
                x = (
                    model_index
                    + (
                        model_rows["horizon_index"].to_numpy(float)
                        - model_rows["horizon_index"].mean()
                    )
                    * 0.035
                )
                axis.scatter(
                    x,
                    model_rows["estimate"],
                    s=12,
                    alpha=0.35,
                    color=COLORS[model_index % len(COLORS)],
                )
                if len(model_rows):
                    axis.plot(
                        model_index,
                        model_rows["estimate"].mean(),
                        marker="D",
                        color="black",
                        markersize=4,
                    )
            axis.axhline(
                0.0 if parameter == "intercept" else 1.0,
                color="black",
                linestyle="--",
                linewidth=0.8,
            )
            axis.set_xticks(
                np.arange(len(models)),
                [MODEL_LABELS.get(model, model) for model in models],
                rotation=30,
                ha="right",
            )
            axis.set_ylabel(parameter.capitalize())
            axis.set_title(f"{dataset.upper()} — calibration {parameter}")
    figure.suptitle("Calibration intercepts and slopes")
    _save_figure(
        figure,
        registry.output_dir / "figures" / "calibration_parameters",
        registry,
        title="Calibration intercepts and slopes",
        sources=sources,
        note="Points are cell/horizon estimates; diamonds are descriptive means",
    )
