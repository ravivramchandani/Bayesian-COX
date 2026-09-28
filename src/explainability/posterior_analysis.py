"""Posterior contribution and ranking-agreement utilities.

:func:`compare_group_rankings` is the agreement measure used throughout the
explanation stage: it compares two grouped importance tables by Spearman and
Kendall rank correlation and by overlap of their top-ranked groups. Neither
table is treated as the truth; agreement is between two summaries of one
fitted model (or, for the Cox comparison, of two fitted models).
SHAP denotes Shapley additive explanations.

:func:`recover_posterior_mean_abs_beta` and
:func:`grouped_posterior_contribution` rebuild a term-wise intrinsic score for
rehearsal cells that predate stored group contributions. Confirmatory cells
store the exact grouped score, which
:func:`src.explainability.cell_explanation.stored_grouped_posterior_contribution`
reads instead. :func:`posterior_importance` and :func:`compare_rankings` are
older feature-level entry points kept for compatibility."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import kendalltau, spearmanr


def recover_posterior_mean_abs_beta(
    full_validation: pd.DataFrame,
    stored_importance: list[dict[str, Any]],
) -> tuple[pd.Series, list[str]]:
    """Recover ``E(|beta_j|)`` from an immutable cell's full-fold scores.

    A confirmatory cell stores ``E_i E_s |x_ij beta_sj|``. Because the
    covariates are fixed, that equals ``mean_i(|x_ij|) * E_s(|beta_sj|)``.
    This factorisation permits exact recomputation for a random validation
    subset without retaining or reconstructing posterior draws.

    If a transformed feature is numerically zero across the validation fold
    (mean absolute value at most ``1e-15``), its
    contribution is necessarily zero for every subset but ``E(|beta_j|)`` is
    not identifiable. Such features receive a zero multiplier and are
    returned in the second result for explicit reporting.

    Args:
        full_validation: Transformed features of every outer-validation
            subject of the cell, one column per model term.
        stored_importance: The cell's ``posterior_expected_absolute_contribution``
            records, each with ``feature`` and ``expected_abs_contribution``.

    Returns:
        ``E(|beta_j|)`` indexed like ``full_validation.columns``, and the
        names of the unidentified all-zero terms.

    Raises:
        ValueError: If the stored table has another schema, duplicate or
            mismatched features, negative or non-finite values, or a non-zero
            value for an all-zero term.
        RuntimeError: If the recovered multipliers do not reproduce the
            stored values.
    """
    required = {str(name) for name in full_validation.columns}
    table = pd.DataFrame(stored_importance)
    if set(table.columns) != {"feature", "expected_abs_contribution"}:
        raise ValueError("stored posterior importance has an unexpected schema")
    if table["feature"].duplicated().any():
        raise ValueError("stored posterior importance contains duplicate features")
    observed = set(table["feature"].astype(str))
    if observed != required:
        raise ValueError(
            "stored posterior importance features do not match preprocessing metadata"
        )
    stored = table.set_index("feature")["expected_abs_contribution"].astype(float)
    stored = stored.reindex(full_validation.columns)
    if not np.isfinite(stored.to_numpy()).all() or bool((stored < 0).any()):
        raise ValueError("stored posterior importance must be finite and non-negative")

    x_abs_mean = full_validation.abs().mean(axis=0).astype(float)
    beta_abs = pd.Series(index=full_validation.columns, dtype=float)
    unidentified: list[str] = []
    for feature in full_validation.columns:
        denominator = float(x_abs_mean[feature])
        importance = float(stored[feature])
        if denominator <= 1e-15:
            if importance > 1e-12:
                raise ValueError(
                    f"stored importance for zero-valued feature {feature!r} is non-zero"
                )
            beta_abs[feature] = 0.0
            unidentified.append(str(feature))
        else:
            beta_abs[feature] = importance / denominator

    reconstructed = x_abs_mean * beta_abs
    if not np.allclose(
        reconstructed.to_numpy(), stored.to_numpy(), rtol=1e-10, atol=1e-12
    ):
        raise RuntimeError("could not reconstruct the frozen posterior importance")
    return beta_abs, unidentified


def grouped_posterior_contribution(
    validation: pd.DataFrame,
    posterior_mean_abs_beta: pd.Series,
    feature_groups: Mapping[str, str],
) -> pd.DataFrame:
    """Sum term-wise posterior absolute contributions within each source group.

    Each term scores ``mean_i(|x_ij|) * E(|beta_j|)`` over the rows of
    ``validation``, and a group's score is the sum over its terms. This is
    the absolute value taken term by term, not the confirmatory group score
    ``E_s|sum_{j in g} x_ij beta_j^(s)|``, in which signed terms are summed
    first; for a group with several terms it is never smaller than that
    score. It is used only for rehearsal cells without stored group
    contributions, and results computed with it are labelled
    ``legacy_termwise_reconstruction_rehearsal_only``.

    Args:
        validation: Transformed features of the explained subjects.
        posterior_mean_abs_beta: ``E(|beta_j|)`` in ``validation`` column order,
            as returned by :func:`recover_posterior_mean_abs_beta`.
        feature_groups: Source-variable group of every transformed term.

    Returns:
        ``group`` and ``expected_abs_contribution``, largest first with ties
        broken by group name.

    Raises:
        ValueError: If the multiplier order differs from the columns or a
            term has no group.
    """
    if list(validation.columns) != list(posterior_mean_abs_beta.index):
        raise ValueError("posterior multiplier order must match validation columns")
    missing = [name for name in validation if name not in feature_groups]
    if missing:
        raise ValueError(f"feature-group metadata is missing posterior terms: {missing}")
    term_scores = validation.abs().mean(axis=0) * posterior_mean_abs_beta
    rows: dict[str, float] = {}
    for feature, score in term_scores.items():
        group = str(feature_groups[str(feature)])
        rows[group] = rows.get(group, 0.0) + float(score)
    return (
        pd.DataFrame(
            {
                "group": list(rows),
                "expected_abs_contribution": list(rows.values()),
            }
        )
        .sort_values(
            ["expected_abs_contribution", "group"], ascending=[False, True]
        )
        .reset_index(drop=True)
    )


def compare_group_rankings(
    intrinsic: pd.DataFrame,
    shap_importance: pd.DataFrame,
    *,
    intrinsic_score: str = "expected_abs_contribution",
    shap_score: str = "mean_abs_shap",
    top_k: int = 5,
) -> dict[str, Any]:
    """Compare two grouped rankings without treating either as ground truth.

    The correlations are computed on the two score columns over the shared
    groups: Spearman's rho and Kendall's tau-b (the SciPy default). Spearman
    assigns average ranks to tied scores; Kendall's tau-b adjusts its pair-count
    normalisation for ties. The top-k sets take the ``top_k``
    highest scores of each table, breaking ties by group name; their overlap
    is the number of shared groups and their Jaccard index is overlap divided
    by the size of their union.

    Args:
        intrinsic: Table with ``group`` and ``intrinsic_score`` columns.
        shap_importance: Table with ``group`` and ``shap_score`` columns.
        intrinsic_score: Score column of ``intrinsic``.
        shap_score: Score column of ``shap_importance``.
        top_k: Requested top-set size, reduced to the number of groups when
            there are fewer.

    Returns:
        ``n_groups``; ``spearman_rho``, ``kendall_tau`` and their p-values,
        each ``None`` when not finite, as happens when one score column is
        constant;
        ``top_k``, ``top_k_overlap`` and ``top_k_jaccard``; the two top-k group
        lists; and a fixed ``interpretation`` note.

    Raises:
        ValueError: If a table repeats a group, the two tables do not hold
            the same groups, or there are fewer than three groups.
    """
    left = intrinsic[["group", intrinsic_score]].copy()
    right = shap_importance[["group", shap_score]].copy()
    if left["group"].duplicated().any() or right["group"].duplicated().any():
        raise ValueError("rankings must contain one row per source-variable group")
    merged = left.merge(right, on="group", how="inner", validate="one_to_one")
    if len(merged) < 3 or len(merged) != len(left) or len(merged) != len(right):
        raise ValueError("rankings require at least three identical source groups")

    rho, rho_p = spearmanr(merged[intrinsic_score], merged[shap_score])
    tau, tau_p = kendalltau(merged[intrinsic_score], merged[shap_score])
    effective_k = min(int(top_k), len(merged))
    top_left = set(
        left.sort_values([intrinsic_score, "group"], ascending=[False, True])
        .head(effective_k)["group"]
    )
    top_right = set(
        right.sort_values([shap_score, "group"], ascending=[False, True])
        .head(effective_k)["group"]
    )
    overlap = len(top_left & top_right)
    union = len(top_left | top_right)
    return {
        "n_groups": int(len(merged)),
        "spearman_rho": float(rho) if np.isfinite(rho) else None,
        "spearman_p": float(rho_p) if np.isfinite(rho_p) else None,
        "kendall_tau": float(tau) if np.isfinite(tau) else None,
        "kendall_p": float(tau_p) if np.isfinite(tau_p) else None,
        "top_k": effective_k,
        "top_k_overlap": overlap,
        "top_k_jaccard": float(overlap / union),
        "intrinsic_top_k": sorted(top_left),
        "shap_top_k": sorted(top_right),
        "interpretation": "model-conditional agreement; neither ranking is ground truth",
    }


def posterior_importance(model: Any, X: pd.DataFrame | None = None) -> pd.DataFrame:
    """Return posterior expected absolute contribution from a fitted model.

    This compatibility entry point deliberately does not expose probability of
    direction as a magnitude ranking. Confirmatory work reads frozen cell
    artifacts instead of calling this function or refitting a model.

    Args:
        model: A fitted model with ``posterior_expected_absolute_contribution``,
            such as ``BayesianCoxModel``.
        X: Transformed features of the subjects to average over.

    Returns:
        The model's per-term ``mean_i(|x_ij|) * E(|beta_j|)`` table.

    Raises:
        ValueError: If ``X`` is omitted.
    """
    if X is None:
        raise ValueError("X is required for posterior expected contribution")
    return model.posterior_expected_absolute_contribution(X)


def compare_rankings(
    built_in: pd.DataFrame,
    post_hoc: pd.DataFrame,
    built_in_score: str,
    post_hoc_score: str = "mean_abs_shap",
    top_k: int = 5,
) -> dict[str, Any]:
    """Compatibility wrapper for feature-level exploratory comparisons.

    Renames each table's ``feature`` column to ``group`` and delegates to
    :func:`compare_group_rankings`, so each transformed term is treated as its
    own group.

    Args:
        built_in: Intrinsic table with ``feature`` and ``built_in_score``.
        post_hoc: Post-hoc table with ``feature`` and ``post_hoc_score``.
        built_in_score: Score column of ``built_in``.
        post_hoc_score: Score column of ``post_hoc``.
        top_k: Requested top-set size.

    Returns:
        The agreement record of :func:`compare_group_rankings`.
    """
    left = built_in.rename(columns={"feature": "group"})
    right = post_hoc.rename(columns={"feature": "group"})
    return compare_group_rankings(
        left,
        right,
        intrinsic_score=built_in_score,
        shap_score=post_hoc_score,
        top_k=top_k,
    )
