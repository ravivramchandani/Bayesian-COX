"""Sampling-stability gates for the grouped SHAP ranking.

A SHAP ranking computed from a random sample of subjects is worth interpreting
only if a larger or different sample gives nearly the same ranking of
source-variable groups. For every fold and model, this module compares the
grouped SHAP ranking

- at each budget with the next larger budget, under the same seed; and
- at the largest budget between successive seeds (first with second, second
  with third).

A comparison passes when the two rankings have a Spearman correlation of at
least 0.95 and share at least four of their top-five groups. Failures are
reported, not hidden, and they block the agreement claims built on them in
:mod:`src.explainability.uncertainty`.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.explainability.posterior_analysis import compare_group_rankings
from src.explainability.protocol import ExplanationProtocol

EVALUABLE_STATUSES = frozenset({"passed", "failed"})

ComparisonKey = tuple[Any, ...]


def _ranking_stability(
    left: list[dict[str, Any]],
    right: list[dict[str, Any]],
    *,
    score: str,
    protocol: ExplanationProtocol,
) -> dict[str, Any]:
    """Compare two grouped rankings of the same kind and apply the convergence rule.

    Returns:
        The agreement statistics of :func:`compare_group_rankings` plus the
        thresholds and a ``status`` of ``passed``, ``failed`` or
        ``not_evaluable``.
    """
    # compare_group_rankings expects an intrinsic and a SHAP column name; both
    # tables here hold the same score, so the left one is renamed to fit.
    left_frame = pd.DataFrame(left).rename(columns={score: "expected_abs_contribution"})
    right_frame = pd.DataFrame(right).rename(columns={score: "mean_abs_shap"})
    comparison = compare_group_rankings(left_frame, right_frame, top_k=protocol.top_k)
    rho = comparison["spearman_rho"]
    overlap = comparison["top_k_overlap"]
    # With fewer groups than the required overlap the rule cannot be met, and a
    # constant ranking has no defined Spearman correlation.
    evaluable = comparison["n_groups"] >= protocol.convergence_top_overlap and rho is not None
    if not evaluable:
        status = "not_evaluable"
    elif rho >= protocol.convergence_spearman and overlap >= protocol.convergence_top_overlap:
        status = "passed"
    else:
        status = "failed"
    return {
        **comparison,
        "required_spearman": protocol.convergence_spearman,
        "required_top_five_overlap": protocol.convergence_top_overlap,
        "status": status,
    }


def _comparison_lookup(comparisons: list[dict[str, Any]]) -> dict[ComparisonKey, dict[str, Any]]:
    """Index comparison rows by dataset, model, repeat, fold, seed and budget."""
    return {
        (
            row["dataset"],
            row["model_key"],
            row["repeat"],
            row["fold"],
            row["seed"],
            row["budget_index"],
        ): row
        for row in comparisons
    }


def _same_effective_sample(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """Return whether two budgets ended up explaining the same subjects."""
    return left["selection_sha256"] == right["selection_sha256"] or (
        left["effective_validation_subjects"] == right["effective_validation_subjects"]
        and left["effective_training_background"] == right["effective_training_background"]
    )


def _successive_budget_records(
    lookup: dict[ComparisonKey, dict[str, Any]],
    cell: tuple[Any, ...],
    protocol: ExplanationProtocol,
) -> list[dict[str, Any]]:
    """Compare each budget with the next larger one, for every seed of one cell."""
    dataset, model_key, repeat, fold = cell
    records: list[dict[str, Any]] = []
    for seed in protocol.seeds:
        for lower, upper in zip(
            range(1, len(protocol.budgets)),
            range(2, len(protocol.budgets) + 1),
            strict=True,
        ):
            left = lookup[(dataset, model_key, repeat, fold, seed, lower)]
            right = lookup[(dataset, model_key, repeat, fold, seed, upper)]
            # When a small fold caps both budgets at the same size, both
            # selections hold the same subjects and the rankings are identical,
            # so the comparison says nothing about stability.
            if _same_effective_sample(left, right):
                agreement: dict[str, Any] = {"status": "not_evaluable_identical_effective_budget"}
            else:
                agreement = _ranking_stability(
                    left["grouped_shap"],
                    right["grouped_shap"],
                    score="mean_abs_shap",
                    protocol=protocol,
                )
            records.append(
                {
                    "dataset": dataset,
                    "model_key": model_key,
                    "repeat": repeat,
                    "fold": fold,
                    "seed": seed,
                    "lower_budget_index": lower,
                    "upper_budget_index": upper,
                    "agreement": agreement,
                }
            )
    return records


def _successive_seed_records(
    lookup: dict[ComparisonKey, dict[str, Any]],
    cell: tuple[Any, ...],
    protocol: ExplanationProtocol,
) -> list[dict[str, Any]]:
    """Compare successive seeds at the largest budget for one cell."""
    dataset, model_key, repeat, fold = cell
    maximum_budget = len(protocol.budgets)
    records: list[dict[str, Any]] = []
    for left_seed, right_seed in zip(protocol.seeds[:-1], protocol.seeds[1:], strict=True):
        left = lookup[(dataset, model_key, repeat, fold, left_seed, maximum_budget)]
        right = lookup[(dataset, model_key, repeat, fold, right_seed, maximum_budget)]
        records.append(
            {
                "dataset": dataset,
                "model_key": model_key,
                "repeat": repeat,
                "fold": fold,
                "left_seed": left_seed,
                "right_seed": right_seed,
                "budget_index": maximum_budget,
                "agreement": _ranking_stability(
                    left["grouped_shap"],
                    right["grouped_shap"],
                    score="mean_abs_shap",
                    protocol=protocol,
                ),
            }
        )
    return records


def _convergence_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarise gate results; the run passes only if every evaluable comparison passes."""
    evaluable = [
        row["agreement"]["status"]
        for row in records
        if row["agreement"]["status"] in EVALUABLE_STATUSES
    ]
    if not evaluable:
        overall = "not_evaluable"
    elif all(status == "passed" for status in evaluable):
        overall = "passed"
    else:
        overall = "failed"
    return {
        "status": overall,
        "n_evaluable": len(evaluable),
        "n_passed": evaluable.count("passed"),
        "n_failed": evaluable.count("failed"),
        "claim_permitted": overall == "passed",
    }


def convergence_records(
    comparisons: list[dict[str, Any]], protocol: ExplanationProtocol
) -> dict[str, Any]:
    """Run every successive-budget and successive-seed gate on the grouped SHAP rankings.

    Args:
        comparisons: One row per cell, seed and budget, each holding a
            ``grouped_shap`` table.
        protocol: Budgets, seeds and thresholds.

    Returns:
        The individual budget and seed comparisons and an overall summary.
    """
    lookup = _comparison_lookup(comparisons)
    cells = sorted(
        {(row["dataset"], row["model_key"], row["repeat"], row["fold"]) for row in comparisons}
    )
    budget_records: list[dict[str, Any]] = []
    seed_records: list[dict[str, Any]] = []
    for cell in cells:
        budget_records.extend(_successive_budget_records(lookup, cell, protocol))
        seed_records.extend(_successive_seed_records(lookup, cell, protocol))
    return {
        "primary_gate_target": "grouped exact-SHAP global ranking",
        "budget_comparisons": budget_records,
        "successive_seed_comparisons": seed_records,
        "summary": _convergence_summary(budget_records + seed_records),
    }


def unavailable_convergence() -> dict[str, Any]:
    """Return the convergence record used when no Cox comparison exists."""
    return {
        "primary_gate_target": "not applicable to unavailable Cox comparison",
        "budget_comparisons": [],
        "successive_seed_comparisons": [],
        "summary": {
            "status": "not_evaluable",
            "n_evaluable": 0,
            "n_passed": 0,
            "n_failed": 0,
            "claim_permitted": False,
        },
    }


def model_convergence_status(convergence: dict[str, Any], dataset: str, model_key: str) -> str:
    """Return the combined gate status of one model on one dataset.

    Only ``passed`` and ``failed`` comparisons count. The status is
    ``passed`` when all of them passed, ``failed`` when any failed, and
    ``not_evaluable`` when there are none.
    """
    records = [
        row
        for section in ("budget_comparisons", "successive_seed_comparisons")
        for row in convergence.get(section, [])
        if row.get("dataset") == dataset
        and row.get("model_key") == model_key
        and row.get("agreement", {}).get("status") in EVALUABLE_STATUSES
    ]
    if not records:
        return "not_evaluable"
    if all(row["agreement"]["status"] == "passed" for row in records):
        return "passed"
    return "failed"
