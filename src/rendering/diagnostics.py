"""Render posterior checks, proportional-hazards tests and archived trace snapshots.

Each ``_render_*`` function is called by :func:`src.rendering.runner.render_run`
for a confirmatory run and reads only verified stored content:

- ``_render_predictive_checks`` reads the prior and posterior predictive
  summaries of complete Bayesian cells and writes
  ``tables/prior_posterior_predictive_checks`` and
  ``figures/prior_posterior_predictive_checks``.
- ``_render_ph`` reads the proportional-hazards (PH) tests of complete Cox
  cells, or the robustness run's ``ph_assessment.json`` when one was verified,
  and writes ``tables/proportional_hazards_tests``,
  ``tables/proportional_hazards_summary`` and
  ``figures/proportional_hazards_assessment``.
- ``_render_trace_snapshots`` reads the thinned posterior trace snapshots of
  Bayesian cells and fit attempts and writes
  ``tables/posterior_trace_snapshot_inventory`` plus one figure per rendered
  variable under ``figures/traces/``.

The trace snapshots hold up to 250 evenly spaced draws per chain for visual
inspection only. Numerical Markov chain Monte Carlo (MCMC) diagnostics use every retained
draw when the cell was fitted and are not recomputed here."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

import matplotlib

# Select the non-interactive backend before pyplot is imported.
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .constants import COLORS, MODEL_LABELS
from .outputs import OutputRegistry, _cell_sources, _save_figure, _write_table
from .verification import FrozenRun, _slug, _source


def _predictive_check_rows(run: FrozenRun) -> pd.DataFrame:
    """Return the archived predictive checks of complete Bayesian cells as one long table.

    The ``check`` column takes four values:

    - ``prior_predictive_baseline_survival``: prior median baseline survival
      and its 95% interval at each stored time.
    - ``prior_predictive_covariate_population_survival``: the full-model prior
      survival over subjects and draws, with the share of draws near 0 or 1.
    - ``posterior_predictive_replicated_event_count``: observed event counts
      against replicated counts, in total and per baseline-hazard interval.
    - ``posterior_fitted_survival_comparison_not_replicated_data``: fitted
      posterior mean survival against the stored Kaplan–Meier estimate. This
      compares fitted curves, not replicated data, and is labelled so.

    Columns that do not apply to a check are NaN.

    Raises:
        ValueError: If a stored prior check lacks the covariate-population
            part, or a posterior check lacks the replicated-event or
            fitted-survival part.
    """
    rows: list[dict[str, Any]] = []
    for relative, cell in run.cells:
        if cell["status"] != "complete" or not str(cell["model_key"]).startswith("bayesian_"):
            continue
        details = cell.get("model_details", {})
        prior = details.get("prior_predictive")
        posterior = details.get("posterior_predictive")
        if isinstance(prior, dict):
            population = prior.get("covariate_population_survival")
            if not isinstance(population, list):
                raise ValueError(
                    f"confirmatory Bayesian cell lacks full-model prior predictive check: {relative}"
                )
            for item in prior.get("baseline_survival", []):
                rows.append(
                    {
                        "dataset": cell["dataset"],
                        "model_key": cell["model_key"],
                        "repeat": cell["repeat"],
                        "fold": cell["fold"],
                        "check": "prior_predictive_baseline_survival",
                        "time": item.get("time"),
                        "scaled_time": item.get("scaled_time"),
                        "interval": np.nan,
                        "observed": np.nan,
                        "predicted": item.get("median_survival"),
                        "lower_95": item.get("lower_95"),
                        "upper_95": item.get("upper_95"),
                        "observed_covered": np.nan,
                        "replicated_median": np.nan,
                        "posterior_predictive_tail_probability": np.nan,
                        "mean_survival_across_subjects_median": np.nan,
                        "proportion_subject_draws_below_0_01": np.nan,
                        "proportion_subject_draws_above_0_99": np.nan,
                        "source_cell": relative,
                    }
                )
            for item in population:
                rows.append(
                    {
                        "dataset": cell["dataset"],
                        "model_key": cell["model_key"],
                        "repeat": cell["repeat"],
                        "fold": cell["fold"],
                        "check": "prior_predictive_covariate_population_survival",
                        "time": item.get("time"),
                        "scaled_time": item.get("scaled_time"),
                        "interval": np.nan,
                        "observed": np.nan,
                        "predicted": item.get("subject_draw_median_survival"),
                        "lower_95": item.get("subject_draw_lower_95"),
                        "upper_95": item.get("subject_draw_upper_95"),
                        "observed_covered": np.nan,
                        "replicated_median": np.nan,
                        "posterior_predictive_tail_probability": np.nan,
                        "mean_survival_across_subjects_median": item.get(
                            "mean_survival_across_subjects_median"
                        ),
                        "proportion_subject_draws_below_0_01": item.get(
                            "proportion_subject_draws_below_0_01"
                        ),
                        "proportion_subject_draws_above_0_99": item.get(
                            "proportion_subject_draws_above_0_99"
                        ),
                        "source_cell": relative,
                    }
                )
        if isinstance(posterior, dict):
            replication = posterior.get("replicated_event_counts")
            fitted_survival = posterior.get("fitted_survival_check")
            if not isinstance(replication, dict) or not isinstance(fitted_survival, list):
                raise ValueError(
                    f"confirmatory Bayesian cell lacks replicated-event or fitted-survival checks: {relative}"
                )
            replication_records = [
                {"interval": "total", **replication["total"]},
                *replication.get("by_baseline_interval", []),
            ]
            for item in replication_records:
                rows.append(
                    {
                        "dataset": cell["dataset"],
                        "model_key": cell["model_key"],
                        "repeat": cell["repeat"],
                        "fold": cell["fold"],
                        "check": "posterior_predictive_replicated_event_count",
                        "time": np.nan,
                        "scaled_time": np.nan,
                        "interval": item.get("interval"),
                        "observed": item.get("observed"),
                        "predicted": item.get("replicated_mean"),
                        "lower_95": item.get("replicated_lower_95"),
                        "upper_95": item.get("replicated_upper_95"),
                        "observed_covered": item.get("observed_covered"),
                        "replicated_median": item.get("replicated_median"),
                        "posterior_predictive_tail_probability": item.get(
                            "posterior_predictive_tail_probability"
                        ),
                        "mean_survival_across_subjects_median": np.nan,
                        "proportion_subject_draws_below_0_01": np.nan,
                        "proportion_subject_draws_above_0_99": np.nan,
                        "source_cell": relative,
                    }
                )
            for item in fitted_survival:
                rows.append(
                    {
                        "dataset": cell["dataset"],
                        "model_key": cell["model_key"],
                        "repeat": cell["repeat"],
                        "fold": cell["fold"],
                        "check": "posterior_fitted_survival_comparison_not_replicated_data",
                        "time": item.get("time"),
                        "scaled_time": np.nan,
                        "interval": np.nan,
                        "observed": item.get("observed_km"),
                        "predicted": item.get("predicted_mean"),
                        "lower_95": item.get("lower_95"),
                        "upper_95": item.get("upper_95"),
                        "observed_covered": item.get("observed_covered"),
                        "replicated_median": np.nan,
                        "posterior_predictive_tail_probability": np.nan,
                        "mean_survival_across_subjects_median": np.nan,
                        "proportion_subject_draws_below_0_01": np.nan,
                        "proportion_subject_draws_above_0_99": np.nan,
                        "source_cell": relative,
                    }
                )
    return pd.DataFrame(rows)


def _render_predictive_checks(run: FrozenRun, registry: OutputRegistry) -> None:
    """Write the predictive-check table and a three-panel figure per dataset.

    Panels: prior subject-draw median survival over scaled time; replicated
    against observed total event counts; fitted against Kaplan–Meier
    survival.
    """
    table = _predictive_check_rows(run)
    selected = [
        (relative, cell)
        for relative, cell in run.cells
        if cell["status"] == "complete" and str(cell["model_key"]).startswith("bayesian_")
    ]
    sources = _cell_sources(
        run,
        selected,
        ["model_details.prior_predictive", "model_details.posterior_predictive"],
    )
    _write_table(
        table,
        registry.output_dir / "tables" / "prior_posterior_predictive_checks",
        registry,
        sources=sources,
        note=(
            "Archived full-model prior survival, replicated event counts and "
            "separately labelled fitted-survival summaries"
        ),
    )
    datasets = sorted(table["dataset"].unique()) if not table.empty else []
    figure, axes = plt.subplots(
        max(1, len(datasets)),
        3,
        figsize=(15, max(3.8, 3.5 * len(datasets))),
        squeeze=False,
    )
    if table.empty:
        axes[0, 0].text(0.5, 0.5, "No archived predictive checks", ha="center", va="center")
        axes[0, 1].set_axis_off()
        axes[0, 2].set_axis_off()
    for row_index, dataset in enumerate(datasets):
        prior = table[
            (table["dataset"] == dataset)
            & (table["check"] == "prior_predictive_covariate_population_survival")
        ]
        replication = table[
            (table["dataset"] == dataset)
            & (table["check"] == "posterior_predictive_replicated_event_count")
            & (table["interval"].astype(str) == "total")
        ]
        fitted = table[
            (table["dataset"] == dataset)
            & (table["check"] == "posterior_fitted_survival_comparison_not_replicated_data")
        ]
        for model_index, (model, group) in enumerate(prior.groupby("model_key", sort=True)):
            axes[row_index, 0].scatter(
                group["scaled_time"],
                group["predicted"],
                s=10,
                alpha=0.25,
                color=COLORS[model_index % len(COLORS)],
                label=MODEL_LABELS.get(model, model),
            )
        axes[row_index, 0].set_ylim(0, 1)
        axes[row_index, 0].set_xlabel("Training-time scale")
        axes[row_index, 0].set_ylabel("Prior subject-draw median survival")
        axes[row_index, 0].set_title(f"{dataset.upper()} — full-model prior predictive")
        if len(prior):
            axes[row_index, 0].legend(frameon=False, fontsize=6)
        for model_index, (model, group) in enumerate(replication.groupby("model_key", sort=True)):
            axes[row_index, 1].scatter(
                group["observed"],
                group["predicted"],
                s=12,
                alpha=0.35,
                color=COLORS[model_index % len(COLORS)],
                label=MODEL_LABELS.get(model, model),
            )
        maximum_count = max(
            1.0,
            float(replication[["observed", "predicted"]].max().max()) if len(replication) else 1.0,
        )
        axes[row_index, 1].plot(
            [0, maximum_count],
            [0, maximum_count],
            color="black",
            linestyle="--",
            linewidth=0.8,
        )
        axes[row_index, 1].set_xlim(0, maximum_count * 1.05)
        axes[row_index, 1].set_ylim(0, maximum_count * 1.05)
        axes[row_index, 1].set_xlabel("Observed total event count")
        axes[row_index, 1].set_ylabel("Replicated mean total event count")
        axes[row_index, 1].set_title(f"{dataset.upper()} — replicated likelihood-scale data")
        for model_index, (model, group) in enumerate(fitted.groupby("model_key", sort=True)):
            axes[row_index, 2].scatter(
                group["observed"],
                group["predicted"],
                s=12,
                alpha=0.35,
                color=COLORS[model_index % len(COLORS)],
                label=MODEL_LABELS.get(model, model),
            )
        axes[row_index, 2].plot([0, 1], [0, 1], color="black", linestyle="--", linewidth=0.8)
        axes[row_index, 2].set_xlim(0, 1)
        axes[row_index, 2].set_ylim(0, 1)
        axes[row_index, 2].set_xlabel("Observed training Kaplan–Meier survival")
        axes[row_index, 2].set_ylabel("Fitted posterior mean survival")
        axes[row_index, 2].set_title(f"{dataset.upper()} — fitted survival (not replicated data)")
    figure.suptitle("Prior predictive, replicated-event and fitted-survival checks")
    _save_figure(
        figure,
        registry.output_dir / "figures" / "prior_posterior_predictive_checks",
        registry,
        title="Prior predictive, replicated-event and fitted-survival checks",
        sources=sources,
        note=(
            "Full-model prior survival, replicated event counts and fitted-survival "
            "comparisons are separately identified from archived checks"
        ),
    )


def _ph_rows_from_cells(run: FrozenRun) -> pd.DataFrame:
    """Return the stored per-covariate PH test rows of every complete Cox cell.

    Each row keeps the test statistic, p-value and the Holm decision stored
    with the fit; nothing is recomputed.
    """
    rows: list[dict[str, Any]] = []
    for relative, cell in run.cells:
        if cell["status"] != "complete" or cell["model_key"] != "cox_ph":
            continue
        for item in cell.get("model_details", {}).get("ph_test", []):
            rows.append(
                {
                    "dataset": cell["dataset"],
                    "repeat": cell["repeat"],
                    "fold": cell["fold"],
                    "covariate": item.get("feature", item.get("covariate")),
                    "test_statistic": item.get("test_statistic"),
                    "p_value": item.get("p"),
                    "holm_adjusted_p": item.get("holm_adjusted_p"),
                    "holm_reject_0_05": item.get("holm_reject_0_05"),
                    "source_cell": relative,
                }
            )
    return pd.DataFrame(rows)


def _render_ph(
    run: FrozenRun,
    registry: OutputRegistry,
    *,
    robustness: dict[str, Any] | None,
) -> None:
    """Write the PH test table, a per-covariate summary and its figure.

    The summary gives, for each dataset and covariate, the number of outer
    Cox fits and the fraction whose stored within-fit Holm decision rejected
    proportional hazards. It is descriptive and is not used to select models.

    Args:
        run: The verified run.
        registry: Output registry.
        robustness: Verified robustness content; its ``ph_assessment`` is
            used instead of the cell-level tests when present.

    Raises:
        ValueError: If a non-empty test table lacks ``holm_reject_0_05``.
    """
    if robustness is not None and isinstance(robustness.get("ph_assessment"), dict):
        ph = robustness["ph_assessment"]
        table = pd.DataFrame(ph.get("covariate_tests", []))
        sources = [robustness["source_refs"]["ph_assessment.json"]]
    else:
        table = _ph_rows_from_cells(run)
        selected = [
            (relative, cell)
            for relative, cell in run.cells
            if cell["status"] == "complete" and cell["model_key"] == "cox_ph"
        ]
        sources = _cell_sources(run, selected, ["model_details.ph_test"])
    _write_table(
        table,
        registry.output_dir / "tables" / "proportional_hazards_tests",
        registry,
        sources=sources,
        note="Scaled Schoenfeld-residual PH tests with within-fit multiplicity decisions",
    )
    if table.empty:
        summary = pd.DataFrame(
            columns=["dataset", "covariate", "n_outer_fits", "holm_rejection_fraction"]
        )
    else:
        reject_column = "holm_reject_0_05"
        if reject_column not in table:
            raise ValueError("PH table lacks the stored Holm rejection decision")
        summary = (
            table.groupby(["dataset", "covariate"], sort=True)[reject_column]
            .agg(n_outer_fits="size", holm_rejection_fraction="mean")
            .reset_index()
        )
    _write_table(
        summary,
        registry.output_dir / "tables" / "proportional_hazards_summary",
        registry,
        sources=sources,
        note="Descriptive stability of within-fit PH departures across outer folds",
    )
    datasets = sorted(summary["dataset"].unique()) if not summary.empty else []
    panel_rows = [max(1, int((summary["dataset"] == dataset).sum())) for dataset in datasets]
    figure, axes = plt.subplots(
        max(1, len(datasets)),
        1,
        figsize=(9, max(3.5, 3.0 * len(datasets))),
        gridspec_kw={"height_ratios": panel_rows or [1]},
        squeeze=False,
    )
    if summary.empty:
        axes[0, 0].text(0.5, 0.5, "No available PH test records", ha="center", va="center")
    for axis, dataset in zip(axes.flat, datasets, strict=False):
        subset = summary[summary["dataset"] == dataset].sort_values(
            ["holm_rejection_fraction", "covariate"]
        )
        y = np.arange(len(subset))
        axis.barh(y, subset["holm_rejection_fraction"], color=COLORS[0], alpha=0.75)
        axis.set_yticks(y, subset["covariate"])
        axis.set_xlim(0, 1)
        axis.set_xlabel("Fraction of outer Cox fits rejecting PH after within-fit Holm control")
        axis.set_title(dataset.upper())
    figure.suptitle("Proportional-hazards assessment")
    _save_figure(
        figure,
        registry.output_dir / "figures" / "proportional_hazards_assessment",
        registry,
        title="Proportional-hazards assessment",
        sources=sources,
        note="Departure frequencies are limitations, not post-hoc model-selection rules",
    )


def _snapshot_records(run: FrozenRun) -> list[dict[str, Any]]:
    """List every archived trace snapshot of the Bayesian cells.

    A cell can hold a cell-level snapshot in ``model_details`` and one per fit
    attempt; each becomes a record with its source key, cell status and the
    diagnostics that belong to it. ``attempt`` is ``None`` for the cell-level
    snapshot and the 1-based attempt number otherwise.
    """
    records: list[dict[str, Any]] = []
    for relative, cell in run.cells:
        if not str(cell.get("model_key", "")).startswith("bayesian_"):
            continue
        details = cell.get("model_details", {})
        snapshot = details.get("posterior_trace_snapshot")
        diagnostics = details.get("diagnostics", {})
        if isinstance(snapshot, dict):
            records.append(
                {
                    "relative": relative,
                    "cell": cell,
                    "snapshot": snapshot,
                    "attempt": None,
                    "status": cell["status"],
                    "diagnostics": diagnostics,
                    "result_key": "model_details.posterior_trace_snapshot",
                }
            )
        for attempt_index, attempt in enumerate(cell.get("fit_attempts", []), start=1):
            attempt_snapshot = attempt.get("posterior_trace_snapshot")
            if isinstance(attempt_snapshot, dict):
                records.append(
                    {
                        "relative": relative,
                        "cell": cell,
                        "snapshot": attempt_snapshot,
                        "attempt": attempt_index,
                        "status": cell["status"],
                        "diagnostics": attempt.get("diagnostics", {}),
                        "result_key": f"fit_attempts.{attempt_index - 1}.posterior_trace_snapshot",
                    }
                )
    return records


def _trace_array(variable: dict[str, Any]) -> tuple[np.ndarray, list[str]]:
    """Return a stored variable as a ``(chain, draw, component)`` array.

    Dimensions other than chain and draw are flattened into the component
    axis.

    Returns:
        The array and the names of the flattened dimensions.

    Raises:
        ValueError: If chain or draw is not named, values are not finite, or
            the stored dimensions do not match the values.
    """
    dims = variable.get("dims")
    if not isinstance(dims, list) or "chain" not in dims or "draw" not in dims:
        raise ValueError("trace snapshot variable must identify chain and draw dimensions")
    values = np.asarray(variable.get("values"), dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("trace snapshot contains non-finite values")
    if values.ndim != len(dims):
        raise ValueError("trace snapshot dimensions do not match values")
    chain_axis = dims.index("chain")
    draw_axis = dims.index("draw")
    values = np.moveaxis(values, (chain_axis, draw_axis), (0, 1))
    remaining_dims = [name for name in dims if name not in {"chain", "draw"}]
    flattened = values.reshape(values.shape[0], values.shape[1], -1)
    return flattened, remaining_dims


def _component_labels(
    variable_name: str,
    n_components: int,
    cell: dict[str, Any],
) -> list[str]:
    """Return a display label for each component of a trace variable.

    Coefficients (``beta``) are named after their features, from the stored
    coefficient summary or else the preprocessing feature names, when the
    count matches. Otherwise a single component takes the variable name and
    several take ``name[index]``.
    """
    if variable_name == "beta":
        summary = cell.get("model_details", {}).get("coefficient_summary")
        if isinstance(summary, list):
            features = [str(row.get("feature")) for row in summary]
            if len(features) == n_components and all(value != "None" for value in features):
                return features
        metadata = cell.get("preprocessing", {})
        features = metadata.get("feature_names")
        if isinstance(features, list) and len(features) == n_components:
            return [str(value) for value in features]
    if n_components == 1:
        return [variable_name]
    return [f"{variable_name}[{index}]" for index in range(n_components)]


def _render_trace_variable(
    record: dict[str, Any],
    variable_name: str,
    registry: OutputRegistry,
) -> list[Path]:
    """Plot each component of a stored, thinned posterior variable.

    Args:
        record: Snapshot, cell and source-reference metadata from the verified run.
        variable_name: Key in the snapshot's variable mapping.
        registry: Output directory and exact source-lineage recorder.

    Returns:
        Written PDF and PNG paths. These plots do not recompute diagnostics.
    """
    snapshot = record["snapshot"]
    variables = snapshot.get("variables")
    if not isinstance(variables, dict) or variable_name not in variables:
        raise ValueError("trace snapshot variable inventory is malformed")
    values, _remaining_dims = _trace_array(variables[variable_name])
    draws = np.asarray(snapshot.get("draw_indices"), dtype=int)
    if draws.ndim != 1 or len(draws) != values.shape[1]:
        raise ValueError("trace draw-index inventory does not match stored values")
    labels = _component_labels(variable_name, values.shape[2], record["cell"])
    n_components = values.shape[2]
    horizontal_labels = any(len(label) > 24 for label in labels)
    figure, axes = plt.subplots(
        n_components,
        2,
        figsize=(12, max(3.0, 1.8 * n_components)),
        squeeze=False,
    )
    for component in range(n_components):
        trace_axis, marginal_axis = axes[component]
        for chain in range(values.shape[0]):
            trace_axis.plot(
                draws,
                values[chain, :, component],
                linewidth=0.65,
                alpha=0.8,
                color=COLORS[chain % len(COLORS)],
                label=f"chain {chain + 1}" if component == 0 else None,
            )
        marginal_axis.hist(
            values[:, :, component].reshape(-1),
            bins=min(30, max(10, int(np.sqrt(values.shape[0] * values.shape[1])))),
            density=True,
            color=COLORS[0],
            alpha=0.65,
        )
        if horizontal_labels:
            trace_axis.set_ylabel(
                textwrap.fill(
                    labels[component].replace("=", " = "), width=28, break_long_words=False
                ),
                rotation=0,
                ha="right",
                va="center",
                fontsize=8,
            )
        else:
            trace_axis.set_ylabel(labels[component])
        trace_axis.set_xlabel("Original retained draw index")
        marginal_axis.set_xlabel("Stored thinned value")
        marginal_axis.set_ylabel("Density")
    axes[0, 0].legend(frameon=False, ncols=min(4, values.shape[0]))
    cell = record["cell"]
    attempt = f" attempt {record['attempt']}" if record["attempt"] is not None else ""
    title = (
        "Visualization-only thinned posterior — "
        f"{cell['dataset'].upper()} {cell['model_key']} R{cell['repeat']} F{cell['fold']}"
        f"{attempt}: {variable_name}"
    )
    figure.suptitle(title, y=1.0)
    suffix = f"_attempt_{record['attempt']:02d}" if record["attempt"] is not None else ""
    base = (
        registry.output_dir
        / "figures"
        / "traces"
        / (
            f"trace_{_slug(cell['dataset'])}_{_slug(cell['model_key'])}_"
            f"r{int(cell['repeat']):02d}_f{int(cell['fold']):02d}{suffix}_{_slug(variable_name)}"
        )
    )
    source_ref = _source(
        registry.run,
        record["relative"],
        [f"{record['result_key']}.variables.{variable_name}"],
    )
    return _save_figure(
        figure,
        base,
        registry,
        title=title,
        sources=[source_ref],
        note=(
            "Thinned snapshot for visual diagnosis only; numerical diagnostics use all retained draws"
        ),
    )


def _render_trace_snapshots(run: FrozenRun, registry: OutputRegistry) -> None:
    """Inventory all snapshots and plot failed attempts plus one representative.

    A complete representative is selected for each cohort/model pair; every
    snapshot attached to a failed cell is rendered when its variables are valid.
    """
    records = _snapshot_records(run)
    representatives: set[tuple[str, str]] = set()
    inventory_rows: list[dict[str, Any]] = []
    rendered_output_lookup: dict[int, list[str]] = {}
    selected_indices: set[int] = set()
    for index, record in enumerate(records):
        cell = record["cell"]
        key = (str(cell["dataset"]), str(cell["model_key"]))
        failed_attempt = record["attempt"] is not None and cell["status"] != "complete"
        if failed_attempt or (record["attempt"] is None and key not in representatives):
            selected_indices.add(index)
            if record["attempt"] is None:
                representatives.add(key)

    for index, record in enumerate(records):
        snapshot = record["snapshot"]
        variables = snapshot.get("variables")
        if not isinstance(variables, dict):
            raise ValueError("trace snapshot lacks a variable mapping")
        paths: list[str] = []
        if index in selected_indices:
            diagnostics_checked = record.get("diagnostics", {}).get("variables_checked")
            requested = (
                [str(value) for value in diagnostics_checked]
                if isinstance(diagnostics_checked, list)
                else list(variables)
            )
            requested = [name for name in requested if name in variables]
            if not requested:
                requested = list(variables)
            for variable_name in sorted(set(requested)):
                written = _render_trace_variable(record, variable_name, registry)
                paths.extend(str(path.relative_to(registry.output_dir)) for path in written)
        rendered_output_lookup[index] = paths
        cell = record["cell"]
        for variable_name, variable in sorted(variables.items()):
            values, _dims = _trace_array(variable)
            inventory_rows.append(
                {
                    "dataset": cell["dataset"],
                    "model_key": cell["model_key"],
                    "repeat": cell["repeat"],
                    "fold": cell["fold"],
                    "cell_status": cell["status"],
                    "attempt": record["attempt"],
                    "variable": variable_name,
                    "stored_chains": values.shape[0],
                    "stored_draws_per_chain": values.shape[1],
                    "components": values.shape[2],
                    "purpose": snapshot.get("purpose"),
                    "rendered": index in selected_indices,
                    "rendered_outputs": ";".join(paths),
                    "source_cell": record["relative"],
                    "source_result_key": record["result_key"],
                }
            )
    table = pd.DataFrame(
        inventory_rows,
        columns=[
            "dataset",
            "model_key",
            "repeat",
            "fold",
            "cell_status",
            "attempt",
            "variable",
            "stored_chains",
            "stored_draws_per_chain",
            "components",
            "purpose",
            "rendered",
            "rendered_outputs",
            "source_cell",
            "source_result_key",
        ],
    )
    sources = [_source(run, record["relative"], [record["result_key"]]) for record in records]
    _write_table(
        table,
        registry.output_dir / "tables" / "posterior_trace_snapshot_inventory",
        registry,
        sources=sources,
        note=(
            "Inventory of all archived visualization-only trace snapshots; every failed-attempt "
            "snapshot and one complete representative per cohort/prior are rendered"
        ),
    )
