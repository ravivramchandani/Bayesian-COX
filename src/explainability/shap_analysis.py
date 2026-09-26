"""SHAP attribution utilities with no model fitting or eager SHAP import."""

from __future__ import annotations

import importlib
import warnings
from typing import Any

import numpy as np
import pandas as pd


def _matching_numeric_frames(
    background: pd.DataFrame, explained: pd.DataFrame
) -> tuple[np.ndarray, np.ndarray, list[str]]:
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
    """Aggregate encoded terms before taking mean absolute SHAP attribution."""
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
