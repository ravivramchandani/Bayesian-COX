"""Summarise descriptive uncertainty in frozen explanation agreement and group ranks.

The bootstrap resamples repeats, folds within each repeat and one seed within
each fold, preserving the frozen generator-consumption order. Its percentile
intervals describe stability rather than independent-sample inference.
SHAP denotes Shapley additive explanations.

The three-stage bootstrap follows the nesting of the design. Outer repeats
are separate random partitions of the cohort; the folds of one repeat share
training subjects; and each fold is explained with three seeds. One
replicate draws the repeats with replacement, then, within each drawn repeat,
its folds with replacement, then, within each drawn fold, one of its seed
values, and averages all drawn values. The 2.5th and 97.5th percentiles of
the replicate means form the interval. Because folds overlap in training data
and the target is agreement within fitted models, the interval summarises
variability across the design, not sampling uncertainty about a population.

Two claim gates use it, both at the largest budget:

- H3a (:func:`agreement_uncertainty`): positive agreement between the
  intrinsic ranking and SHAP on the same posterior-mean model.
- H3b (:func:`paired_cross_model_agreement_difference`): the paired
  difference, same-model agreement minus agreement with Cox SHAP, computed
  selection by selection before resampling.

:func:`group_stability` summarises each group's rank and top-five frequency.
All three are called by :mod:`src.explainability.result`."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.explainability.protocol import ExplanationProtocol, _stable_seed
from src.explainability.stability import model_convergence_status

AGREEMENT_METRICS = ("spearman_rho", "kendall_tau", "top_k_jaccard")

# (target label, comparison-row table key, score column) for each ranking
# whose group-level stability is summarised.
GROUP_STABILITY_TARGETS = (
    (
        "posterior_expected_absolute_contribution",
        "grouped_intrinsic",
        "expected_abs_contribution",
    ),
    ("exact_linear_shap", "grouped_shap", "mean_abs_shap"),
)

OuterCell = tuple[int, int]


def _values_by_cell(
    rows: list[dict[str, Any]], value_key: str
) -> tuple[dict[OuterCell, list[float]], dict[int, list[OuterCell]]]:
    """Group values by ``(repeat, fold)`` and list each repeat's folds in sorted order."""
    by_cell: dict[OuterCell, list[float]] = {}
    for row in rows:
        by_cell.setdefault((int(row["repeat"]), int(row["fold"])), []).append(float(row[value_key]))
    repeat_to_cells: dict[int, list[OuterCell]] = {}
    for cell_key in sorted(by_cell):
        repeat_to_cells.setdefault(cell_key[0], []).append(cell_key)
    return by_cell, repeat_to_cells


def _bootstrap_means(
    by_cell: dict[OuterCell, list[float]],
    repeat_to_cells: dict[int, list[OuterCell]],
    n_bootstraps: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Return the mean of each three-stage bootstrap resample."""
    repeats = np.asarray(sorted(repeat_to_cells), dtype=int)
    estimates = np.empty(n_bootstraps, dtype=float)
    # The frozen intervals depend on drawing from the generator in exactly this
    # order: repeats, then folds within each repeat, then one value per fold.
    for index in range(n_bootstraps):
        sampled_repeats = rng.choice(repeats, size=len(repeats), replace=True)
        values: list[float] = []
        for repeat in sampled_repeats:
            candidates = repeat_to_cells[int(repeat)]
            sampled_cells = rng.choice(len(candidates), size=len(candidates), replace=True)
            values.extend(
                float(rng.choice(by_cell[candidates[cell_index]])) for cell_index in sampled_cells
            )
        estimates[index] = np.mean(values)
    return estimates


def three_stage_bootstrap(
    records: list[dict[str, Any]],
    value_key: str,
    *,
    n_bootstraps: int,
    seed: int,
) -> dict[str, Any]:
    """Summarise one value across outer cells with a three-stage bootstrap interval.

    Rows whose value is ``None`` are left out. The point estimate is the plain
    mean of the remaining rows, and the interval is the 2.5th and 97.5th
    percentiles of the resampled means. ``standard_deviation`` is the sample
    standard deviation of the rows, not a bootstrap standard error.

    Args:
        records: Rows with ``repeat``, ``fold`` and ``value_key``.
        value_key: Name of the value to summarise.
        n_bootstraps: Number of resamples.
        seed: Seed of the bootstrap generator.

    Returns:
        ``estimate``, ``lower_95`` and ``upper_95``, which are all ``None``
        when no row has a value; otherwise also ``standard_deviation``,
        ``n_outer_repeats`` and ``n_outer_cells``.
    """
    available = [row for row in records if row.get(value_key) is not None]
    if not available:
        return {"estimate": None, "lower_95": None, "upper_95": None}
    by_cell, repeat_to_cells = _values_by_cell(available, value_key)
    rng = np.random.default_rng(seed)
    estimates = _bootstrap_means(by_cell, repeat_to_cells, n_bootstraps, rng)
    observed = np.asarray([float(row[value_key]) for row in available])
    return {
        "estimate": float(np.mean(observed)),
        "lower_95": float(np.percentile(estimates, 2.5)),
        "upper_95": float(np.percentile(estimates, 97.5)),
        "standard_deviation": float(np.std(observed, ddof=1)) if len(observed) > 1 else None,
        "n_outer_repeats": len(repeat_to_cells),
        "n_outer_cells": len(by_cell),
    }


def _final_budget_rows(
    comparisons: list[dict[str, Any]], protocol: ExplanationProtocol
) -> list[dict[str, Any]]:
    """Keep the comparison rows computed at the largest sampling budget."""
    final_budget = len(protocol.budgets)
    return [row for row in comparisons if row["budget_index"] == final_budget]


def _dataset_models(rows: list[dict[str, Any]]) -> list[tuple[Any, Any]]:
    """Return the sorted ``(dataset, model_key)`` pairs present in the rows."""
    return sorted({(row["dataset"], row["model_key"]) for row in rows})


def _rows_for_model(
    rows: list[dict[str, Any]], dataset: str, model_key: str
) -> list[dict[str, Any]]:
    """Keep the rows of one model on one dataset."""
    return [row for row in rows if row["dataset"] == dataset and row["model_key"] == model_key]


def _interval_above_zero(summary: dict[str, Any]) -> bool:
    """Return whether a bootstrap summary's 95% interval lies wholly above zero."""
    return summary["lower_95"] is not None and summary["lower_95"] > 0.0


def _model_agreement_uncertainty(
    selected: list[dict[str, Any]],
    dataset: str,
    model_key: str,
    protocol: ExplanationProtocol,
    convergence: dict[str, Any],
    *,
    expected_outer_cells: int,
    confirmatory_evidence: bool,
) -> dict[str, Any]:
    """Summarise one model's agreement and decide whether H3a support is permitted.

    Each metric gets its own bootstrap generator, seeded from the dataset,
    model and metric. A model with any excluded cell has fewer outer cells
    than planned and so cannot meet the complete-outer-cell gate.
    """
    metric_rows = [
        {
            "repeat": row["repeat"],
            "fold": row["fold"],
            "seed": row["seed"],
            **{key: row["agreement"][key] for key in AGREEMENT_METRICS},
        }
        for row in selected
    ]
    cells = {(row["repeat"], row["fold"]) for row in metric_rows}
    result: dict[str, Any] = {
        "dataset": dataset,
        "model_key": model_key,
        "n_outer_cells": len(cells),
        "n_cell_seed_estimates": len(metric_rows),
        "method": (
            "descriptive three-stage bootstrap: resample outer repeats, "
            "folds within repeat, then one of the three seed estimates "
            "within each sampled cell"
        ),
        "bootstrap_replicates": protocol.uncertainty_bootstraps,
    }
    for metric in AGREEMENT_METRICS:
        result[metric] = three_stage_bootstrap(
            metric_rows,
            metric,
            n_bootstraps=protocol.uncertainty_bootstraps,
            seed=_stable_seed(protocol.uncertainty_seed, dataset, model_key, metric),
        )
    stability_status = model_convergence_status(convergence, dataset, model_key)
    complete_cell_gate = len(cells) == expected_outer_cells
    result["sampling_stability_gate"] = stability_status
    result["expected_outer_cells"] = expected_outer_cells
    result["complete_outer_cell_gate"] = complete_cell_gate
    result["confirmatory_evidence_gate"] = confirmatory_evidence
    result["positive_same_model_agreement_supported"] = bool(
        confirmatory_evidence
        and complete_cell_gate
        and stability_status == "passed"
        and _interval_above_zero(result["spearman_rho"])
    )
    result["claim_rule"] = (
        "Positive same-model agreement is supported only for a confirmatory "
        "artifact with every planned outer cell, when every evaluable "
        "budget/seed stability comparison passes and the Spearman 95% "
        "interval is wholly above zero."
    )
    return result


def agreement_uncertainty(
    comparisons: list[dict[str, Any]],
    protocol: ExplanationProtocol,
    convergence: dict[str, Any],
    *,
    expected_outer_cells: int,
    confirmatory_evidence: bool,
) -> list[dict[str, Any]]:
    """Summarise each model's intrinsic-versus-SHAP agreement at the largest budget.

    Positive agreement (hypothesis H3a) is supported only when all four gates
    hold: the source run is confirmatory, every planned outer cell is present,
    the model's sampling-stability gate passed, and the Spearman 95% interval
    lies wholly above zero.

    Args:
        comparisons: Comparison rows, each with an ``agreement`` record.
        protocol: Budgets, bootstrap size and seed.
        convergence: Output of :func:`~src.explainability.stability.convergence_records`
            for the same rows.
        expected_outer_cells: Number of outer cells the run planned.
        confirmatory_evidence: Whether the source run is a confirmatory run.

    Returns:
        One summary per ``(dataset, model_key)``, in sorted order.
    """
    final_rows = _final_budget_rows(comparisons, protocol)
    return [
        _model_agreement_uncertainty(
            _rows_for_model(final_rows, dataset, model_key),
            dataset,
            model_key,
            protocol,
            convergence,
            expected_outer_cells=expected_outer_cells,
            confirmatory_evidence=confirmatory_evidence,
        )
        for dataset, model_key in _dataset_models(final_rows)
    ]


def _final_budget_lookup(
    rows: list[dict[str, Any]], final_budget: int
) -> dict[tuple[Any, ...], dict[str, Any]]:
    """Index final-budget rows by dataset, model, repeat, fold, seed and budget."""
    return {
        (
            row["dataset"],
            row["model_key"],
            row["repeat"],
            row["fold"],
            row["seed"],
            row["budget_index"],
        ): row
        for row in rows
        if row["budget_index"] == final_budget
    }


def _paired_difference_rows(
    keys: list[tuple[Any, ...]],
    same_lookup: dict[tuple[Any, ...], dict[str, Any]],
    cox_lookup: dict[tuple[Any, ...], dict[str, Any]],
) -> list[dict[str, Any]]:
    """Subtract Cox agreement from same-model agreement for each paired selection."""
    rows: list[dict[str, Any]] = []
    for key in keys:
        same = same_lookup[key]
        cox = cox_lookup[key]
        if same["selection_sha256"] != cox["selection_sha256"]:
            raise RuntimeError("same-model and Cox agreement records are not paired selections")
        row: dict[str, Any] = {
            "repeat": same["repeat"],
            "fold": same["fold"],
            "seed": same["seed"],
        }
        for metric in AGREEMENT_METRICS:
            left = same["agreement"].get(metric)
            right = cox["agreement"].get(metric)
            row[metric] = None if left is None or right is None else float(left) - float(right)
        rows.append(row)
    return rows


def paired_cross_model_agreement_difference(
    same_model: list[dict[str, Any]],
    cox_model: list[dict[str, Any]],
    protocol: ExplanationProtocol,
    same_convergence: dict[str, Any],
    cox_convergence: dict[str, Any],
    *,
    expected_outer_cells: int,
    confirmatory_evidence: bool,
) -> list[dict[str, Any]]:
    """Estimate the H3b paired difference: same-model agreement minus Cox agreement.

    Both agreements compare the same grouped posterior contribution, once
    with SHAP on the Bayesian posterior-mean model and once with SHAP on the
    paired Cox model, on the same subjects and background. Only selections
    present in both sets at the largest budget are used. Stronger same-model
    agreement is supported only when the run is confirmatory, every planned
    outer cell is paired, both sampling-stability gates passed, and the
    Spearman-difference 95% interval lies wholly above zero.

    Args:
        same_model: Bayesian intrinsic-versus-own-SHAP comparison rows.
        cox_model: Bayesian intrinsic-versus-Cox-SHAP comparison rows.
        protocol: Budgets, bootstrap size and seed.
        same_convergence: Convergence records of ``same_model``.
        cox_convergence: Convergence records of ``cox_model``.
        expected_outer_cells: Number of outer cells the run planned.
        confirmatory_evidence: Whether the source run is a confirmatory run.

    Returns:
        One summary per ``(dataset, model_key)``, in sorted order.

    Raises:
        RuntimeError: If two rows with the same key were computed on
            different selections.
    """
    final_budget = len(protocol.budgets)
    same_lookup = _final_budget_lookup(same_model, final_budget)
    cox_lookup = _final_budget_lookup(cox_model, final_budget)
    paired_keys = sorted(set(same_lookup) & set(cox_lookup))
    results: list[dict[str, Any]] = []
    for dataset, model_key in sorted({key[:2] for key in paired_keys}):
        keys = [key for key in paired_keys if key[0] == dataset and key[1] == model_key]
        difference_rows = _paired_difference_rows(keys, same_lookup, cox_lookup)
        result: dict[str, Any] = {
            "dataset": dataset,
            "model_key": model_key,
            "direction": "same-Bayesian-model agreement minus paired Cox agreement",
            "n_outer_cells": len({(row["repeat"], row["fold"]) for row in difference_rows}),
            "n_cell_seed_pairs": len(difference_rows),
            "method": (
                "paired descriptive three-stage bootstrap over outer repeats, "
                "folds within repeat and identical explanation seeds"
            ),
            "bootstrap_replicates": protocol.uncertainty_bootstraps,
        }
        for metric in AGREEMENT_METRICS:
            result[metric] = three_stage_bootstrap(
                difference_rows,
                metric,
                n_bootstraps=protocol.uncertainty_bootstraps,
                seed=_stable_seed(
                    protocol.uncertainty_seed, "same_minus_cox", dataset, model_key, metric
                ),
            )
        same_stability = model_convergence_status(same_convergence, dataset, model_key)
        cox_stability = model_convergence_status(cox_convergence, dataset, model_key)
        complete_cell_gate = result["n_outer_cells"] == expected_outer_cells
        result["same_model_sampling_stability_gate"] = same_stability
        result["cox_sampling_stability_gate"] = cox_stability
        result["expected_outer_cells"] = expected_outer_cells
        result["complete_outer_cell_gate"] = complete_cell_gate
        result["confirmatory_evidence_gate"] = confirmatory_evidence
        result["stronger_same_model_agreement_supported"] = bool(
            confirmatory_evidence
            and complete_cell_gate
            and same_stability == "passed"
            and cox_stability == "passed"
            and _interval_above_zero(result["spearman_rho"])
        )
        result["claim_rule"] = (
            "The secondary stronger-agreement claim is permitted only for a "
            "confirmatory artifact with every planned paired outer cell, when "
            "same-model and Cox sampling-stability gates pass and the paired "
            "Spearman-difference 95% interval is wholly above zero."
        )
        results.append(result)
    return results


def _rank_observations(
    selected: list[dict[str, Any]],
    table_key: str,
    score_key: str,
    protocol: ExplanationProtocol,
) -> list[dict[str, Any]]:
    """Rank the groups of every comparison row, largest score first.

    Ties are broken by group name. ``top_five`` is 1.0 when the group ranks
    within the top ``protocol.top_k`` and 0.0 otherwise, so its mean is a
    selection frequency.
    """
    observations: list[dict[str, Any]] = []
    for row in selected:
        table = pd.DataFrame(row[table_key]).sort_values(
            [score_key, "group"], ascending=[False, True]
        )
        for rank, item in enumerate(table.to_dict("records"), start=1):
            observations.append(
                {
                    "repeat": row["repeat"],
                    "fold": row["fold"],
                    "seed": row["seed"],
                    "group": item["group"],
                    "importance": item[score_key],
                    "rank": rank,
                    "top_five": float(rank <= protocol.top_k),
                }
            )
    return observations


def _group_rank_summary(
    group_rows: list[dict[str, Any]],
    *,
    dataset: str,
    model_key: str,
    target: str,
    group: str,
    protocol: ExplanationProtocol,
) -> dict[str, Any]:
    """Summarise one group's importance, rank and top-five frequency.

    ``mean_importance`` is a plain mean over cell-seed rows; the rank and the
    top-five frequency each get a three-stage bootstrap interval.
    """
    return {
        "dataset": dataset,
        "model_key": model_key,
        "target": target,
        "group": group,
        "n_cell_seed_estimates": len(group_rows),
        "mean_importance": float(np.mean([row["importance"] for row in group_rows])),
        "rank": three_stage_bootstrap(
            group_rows,
            "rank",
            n_bootstraps=protocol.uncertainty_bootstraps,
            seed=_stable_seed(protocol.uncertainty_seed, dataset, model_key, target, group, "rank"),
        ),
        "top_five_selection_frequency": three_stage_bootstrap(
            group_rows,
            "top_five",
            n_bootstraps=protocol.uncertainty_bootstraps,
            seed=_stable_seed(
                protocol.uncertainty_seed, dataset, model_key, target, group, "top_five"
            ),
        ),
    }


def group_stability(
    comparisons: list[dict[str, Any]], protocol: ExplanationProtocol
) -> list[dict[str, Any]]:
    """Summarise how stable each group's rank is at the largest budget.

    This is done separately for the grouped posterior contribution and the
    grouped SHAP ranking of every model.

    Args:
        comparisons: Bayesian comparison rows with ``grouped_intrinsic`` and
            ``grouped_shap`` tables.
        protocol: Budgets, top-five size, bootstrap size and seed.

    Returns:
        One summary per ``(dataset, model_key, target, group)``.
    """
    final_rows = _final_budget_rows(comparisons, protocol)
    results: list[dict[str, Any]] = []
    for dataset, model_key in _dataset_models(final_rows):
        selected = _rows_for_model(final_rows, dataset, model_key)
        for target, table_key, score_key in GROUP_STABILITY_TARGETS:
            observations = _rank_observations(selected, table_key, score_key, protocol)
            for group in sorted({row["group"] for row in observations}):
                group_rows = [row for row in observations if row["group"] == group]
                results.append(
                    _group_rank_summary(
                        group_rows,
                        dataset=dataset,
                        model_key=model_key,
                        target=target,
                        group=group,
                        protocol=protocol,
                    )
                )
    return results
