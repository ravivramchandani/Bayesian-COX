"""Post-hoc SHAP attribution for the baseline models."""

from typing import Any

import numpy as np
import pandas as pd
import shap


def shap_importance(
    model: Any,
    X_background: pd.DataFrame,
    X_explain: pd.DataFrame,
    n_background: int = 100,
    random_state: int = 42,
) -> pd.DataFrame:
    """Global SHAP importance for a model's risk prediction.

    Uses a kernel explainer over `predict_risk`, which keeps the method
    identical across Cox PH and the random survival forest so their
    attributions are comparable.

    Returns:
        One row per feature with mean absolute SHAP value, sorted descending.
    """
    rng = np.random.default_rng(random_state)
    features = list(X_explain.columns)

    n_background = min(n_background, len(X_background))
    idx = rng.choice(len(X_background), size=n_background, replace=False)
    background = shap.kmeans(X_background.iloc[idx], min(25, n_background))

    def predict(data: np.ndarray) -> np.ndarray:
        frame = pd.DataFrame(data, columns=features)
        return np.asarray(model.predict_risk(frame), dtype=float)

    explainer = shap.KernelExplainer(predict, background)
    values = explainer.shap_values(X_explain, silent=True)

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
