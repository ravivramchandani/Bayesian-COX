"""SHAP attribution utilities with no model fitting or eager SHAP import.

SHAP (SHapley Additive exPlanations) splits one subject's risk score into
additive per-feature attributions relative to a reference population, the
*background*. "Interventional" means that a feature left out of a coalition
is replaced by background values drawn independently of the subject's other
features, rather than conditionally on them. For a linear risk score
``f(x) = sum_j beta_j x_j`` this has the closed form

    phi_j(x) = beta_j * (x_j - mean of x_j over the background),

so the attributions are exact: no coalitions are sampled and no Monte Carlo
budget applies. Sampling variability in this exact attribution calculation
comes from the selected subjects and background rows. The scores explained
here, the Bayesian posterior-mean linear predictor and the frozen Cox proportional-hazards (PH) linear
predictor, are log relative hazards, so attributions share that scale.

:func:`exact_linear_shap_values` computes these values with
``shap.LinearExplainer`` and checks them against the closed form;
:func:`grouped_shap_importance` sums signed attributions within each source
variable and then averages their absolute value over subjects.

There is no random survival forest SHAP. A forest is not linear, so its SHAP
values would need the fitted trees, and the frozen forest cells record only
the implementation name and feature count. Recreating the trees would mean
refitting, which the explanation stage does not do (ADR-024).
:func:`shap_importance` is an older model-agnostic Kernel SHAP helper that
the confirmatory analysis does not call."""

from __future__ import annotations

import importlib
import warnings
from typing import Any

import numpy as np
import pandas as pd


def _matching_numeric_frames(
    background: pd.DataFrame, explained: pd.DataFrame
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Return both frames as finite float arrays and their shared column names.

    Raises:
        ValueError: If the columns differ, either frame is empty or any value
            is not finite.
    """
    if list(background.columns) != list(explained.columns):
        raise ValueError("background and explained frames must have identical columns")
    if background.empty or explained.empty:
        raise ValueError("background and explained frames must both contain rows")
    names = [str(name) for name in background.columns]
    background_array = background.to_numpy(dtype=float, copy=True)
    explained_array = explained.to_numpy(dtype=float, copy=True)
    if not np.isfinite(background_array).all() or not np.isfinite(
        explained_array
    ).all():
        raise ValueError("SHAP inputs must be finite")
    return background_array, explained_array, names


def exact_linear_shap_values(
    coefficients: np.ndarray,
    background: pd.DataFrame,
    explained: pd.DataFrame,
) -> pd.DataFrame:
    """Return exact interventional SHAP values for one linear risk model.

    ``shap.LinearExplainer`` is instantiated with the entire supplied outer-
    training background. For a linear risk score this has the exact solution
    ``beta_j * (x_j - mean_background_j)``. The implementation verifies the
    library output against that identity so a masker or API change cannot
    silently alter the estimand.

    Args:
        coefficients: One coefficient per column of the frames, in the same
            order, shape ``(n_terms,)``.
        background: Transformed outer-training rows that define the reference
            mean.
        explained: Transformed outer-validation rows to attribute.

    Returns:
        Attributions on the linear-predictor (log relative hazard) scale, with
        the index of ``explained`` and one column per term.

    Raises:
        ValueError: If the frames do not match, contain non-finite values, or
            the coefficients have the wrong shape or are not finite.
        RuntimeError: If the pinned ``shap`` package is missing, or its
            output has the wrong shape or departs from the closed form.
    """
    background_array, explained_array, names = _matching_numeric_frames(
        background, explained
    )
    beta = np.asarray(coefficients, dtype=float)
    if beta.shape != (len(names),) or not np.isfinite(beta).all():
        raise ValueError("coefficients must be one finite value per frame column")

    try:
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                category=PendingDeprecationWarning,
                module=r"shap\.plots\.colors\._colors",
            )
            shap = importlib.import_module("shap")
    except ImportError as exc:  # pragma: no cover - exercised only in broken envs
        raise RuntimeError(
            "Exact linear SHAP requires the pinned 'shap' dependency"
        ) from exc

    # max_samples equal to the background size stops the masker from
    # subsampling, so the reference mean uses every selected background row.
    # The intercept is zero because an additive constant cancels in x - mean.
    masker = shap.maskers.Independent(
        background_array, max_samples=len(background_array)
    )
    explainer = shap.LinearExplainer((beta, 0.0), masker)
    values = np.asarray(explainer(explained_array).values, dtype=float)
    if values.shape != explained_array.shape:
        raise RuntimeError(
            "shap.LinearExplainer returned an unexpected attribution shape"
        )

    analytic = (explained_array - background_array.mean(axis=0)) * beta
    if not np.allclose(values, analytic, rtol=1e-10, atol=1e-12):
        maximum_error = float(np.max(np.abs(values - analytic)))
        raise RuntimeError(
            "LinearExplainer output failed the exact linear-risk identity; "
            f"maximum absolute error={maximum_error:.3g}"
        )
    return pd.DataFrame(values, columns=names, index=explained.index)


def grouped_shap_importance(
    shap_values: pd.DataFrame, feature_groups: dict[str, str]
) -> pd.DataFrame:
    """Aggregate encoded terms before taking mean absolute SHAP attribution.

    For each subject the signed attributions of a group's terms (for example
    the indicator columns of one categorical variable) are added, and the
    group's importance is the mean absolute value of that sum over subjects.
    Summing before the absolute value lets opposite-signed terms of one
    variable offset each other, as they do in the risk score.

    Args:
        shap_values: Attributions, one row per subject and one column per term.
        feature_groups: Source-variable group of every term.

    Returns:
        ``group`` and ``mean_abs_shap``, largest first with ties broken by
        group name.

    Raises:
        ValueError: If a term has no group.
    """
    missing = [name for name in shap_values if name not in feature_groups]
    if missing:
        raise ValueError(f"feature-group metadata is missing SHAP terms: {missing}")
    grouped: dict[str, np.ndarray] = {}
    for feature in shap_values:
        group = str(feature_groups[feature])
        values = shap_values[feature].to_numpy(dtype=float)
        grouped[group] = grouped.get(group, np.zeros(len(values), dtype=float)) + values
    rows = [
        {
            "group": group,
            "mean_abs_shap": float(np.mean(np.abs(values))),
        }
        for group, values in grouped.items()
    ]
    return (
        pd.DataFrame(rows)
        .sort_values(["mean_abs_shap", "group"], ascending=[False, True])
        .reset_index(drop=True)
    )


def shap_importance(
    model: Any,
    X_background: pd.DataFrame,
    X_explain: pd.DataFrame,
    n_background: int = 100,
    n_clusters: int = 15,
    nsamples: int = 256,
    random_state: int = 42,
) -> pd.DataFrame:
    """Legacy model-agnostic Kernel SHAP importance for exploratory outputs.

    The confirmatory protocol uses :func:`exact_linear_shap_values`. SHAP is
    imported only when this legacy function is called so importing the project
    does not emit third-party warnings or load the expensive dependency.

    Args:
        model: Fitted model with ``predict_risk(frame)``.
        X_background: Candidate background rows.
        X_explain: Rows to attribute.
        n_background: Background rows drawn without replacement, capped at
            the number available.
        n_clusters: k-means centres that summarise the drawn background.
        nsamples: Coalition evaluations per explained row.
        random_state: Seed for the background draw only.

    Returns:
        ``feature`` and ``mean_abs_shap`` per term, largest first, without
        grouping.
    """
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            category=PendingDeprecationWarning,
            module=r"shap\.plots\.colors\._colors",
        )
        shap = importlib.import_module("shap")
    rng = np.random.default_rng(random_state)
    features = list(X_explain.columns)

    n_background = min(n_background, len(X_background))
    idx = rng.choice(len(X_background), size=n_background, replace=False)
    background = shap.kmeans(X_background.iloc[idx], min(n_clusters, n_background))

    def predict(data: np.ndarray) -> np.ndarray:
        """Score the arrays Kernel SHAP passes with the model's risk prediction."""
        frame = pd.DataFrame(data, columns=features)
        return np.asarray(model.predict_risk(frame), dtype=float)

    explainer = shap.KernelExplainer(predict, background)
    values = explainer.shap_values(X_explain, nsamples=nsamples, silent=True)
    return (
        pd.DataFrame(
            {
                "feature": features,
                "mean_abs_shap": np.abs(np.asarray(values)).mean(axis=0),
            }
        )
        .sort_values("mean_abs_shap", ascending=False)
        .reset_index(drop=True)
    )
