"""Apply sampling-stability gates to grouped Shapley additive explanations (SHAP).

Successive budgets and successive seeds must meet the frozen Spearman and
top-five overlap thresholds; failed comparisons block agreement claims.

A grouped SHAP ranking depends on which subjects and background rows were
drawn. The gate checks that this sampling no longer changes the ranking in
two ways, for every cell:

- *Budget*: with the same seed, each budget (25/50, 50/100, 100/200
  validation subjects / background rows, capped by fold size) is compared
  with the next larger one.
- *Seed*: at the largest budget, each of the three seeds is compared with
  the next one.

A comparison passes when the two rankings have Spearman correlation at least
0.95 and share at least four of their top-five groups. It is not evaluable
when there are fewer than four groups, when a ranking is constant, or when
fold-size caps make two budgets explain identical samples. A model's gate
passes only when every evaluable comparison passes; the H3a and H3b claim
rules in :mod:`src.explainability.uncertainty` require that.

:func:`convergence_records` is called by :mod:`src.explainability.result`,
once for the Bayesian rows and once for the Cox rows."""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.explainability.posterior_analysis import compare_group_rankings
from src.explainability.protocol import ExplanationProtocol

# Only these statuses count towards a gate; "not_evaluable" and
# "not_evaluable_identical_effective_budget" are reported but ignored.
EVALUABLE_STATUSES = frozenset({"passed", "failed"})

# (dataset, model_key, repeat, fold, seed, budget_index)
ComparisonKey = tuple[Any, ...]


def _ranking_stability(
    left: list[dict[str, Any]],
    right: list[dict[str, Any]],
    *,
    score: str,
    protocol: ExplanationProtocol,
) -> dict[str, Any]:
    """Compare two grouped rankings of the same kind and apply the convergence rule.

    Args:
        left: Records of the first ranking, each with ``group`` and ``score``.
        right: Records of the second ranking, in the same form.
        score: Name of the score field in both.
        protocol: Thresholds and top-five size.

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
    """Detect equal selection hashes or equal effective nested-sampling budgets."""
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
    """Compare successive seeds at the largest budget for one cell.

    Unlike the budget comparisons, these are not screened for identical
    effective samples.
    """
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

    For Cox comparison rows ``grouped_shap`` holds the Cox SHAP ranking, so
    the same rule then measures the stability of Cox SHAP. Those rows carry
    the Bayesian cell's ``model_key``, so the Cox gate is reported per prior
    and covers only the folds in which that prior's cell was interpretable.

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
    """Return the convergence record used when no Cox comparison exists.

    Returns:
        Empty comparison records and a non-evaluable gate that permits no claim.
    """
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

    Args:
        convergence: Budget and successive-seed comparison records.
        dataset: Cohort key to select.
        model_key: Stored model key to select.

    Returns:
        Passed, failed or not_evaluable for the selected model and cohort.
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
