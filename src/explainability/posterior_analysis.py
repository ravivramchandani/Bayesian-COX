"""Posterior contribution and ranking-agreement utilities."""

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

    If a transformed feature is zero for every validation subject, its
    contribution is necessarily zero for every subset but ``E(|beta_j|)`` is
    not identifiable. Such features receive a zero multiplier and are
    returned in the second result for explicit reporting.
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
    """Compute grouped posterior expected absolute contribution for subjects."""
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
    """Compare two grouped rankings without treating either as ground truth."""
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
    """Compatibility wrapper for feature-level exploratory comparisons."""
    left = built_in.rename(columns={"feature": "group"})
    right = post_hoc.rename(columns={"feature": "group"})
    return compare_group_rankings(
        left,
        right,
        intrinsic_score=built_in_score,
        shap_score=post_hoc_score,
        top_k=top_k,
    )
