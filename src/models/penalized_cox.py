"""Training-tuned ridge, lasso and elastic-net Cox comparators."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sksurv.linear_model import CoxnetSurvivalAnalysis, CoxPHSurvivalAnalysis
from sksurv.util import Surv

from src.models.base import BaseSurvivalModel


class PenalizedCox(BaseSurvivalModel):
    """A penalty on the mean partial likelihood, with Breslow event ties."""

    def __init__(self, kind: str, penalty: float) -> None:
        if kind not in {"ridge", "lasso", "elastic_net"} or penalty <= 0:
            raise ValueError("invalid Cox penalty specification")
        self.kind, self.penalty = kind, float(penalty)

    def fit(self, X: pd.DataFrame, y_time: np.ndarray, y_event: np.ndarray) -> PenalizedCox:
        """Fit one fixed penalty; the pipeline performs nested selection."""
        if self.kind == "ridge":
            self.estimator = CoxPHSurvivalAnalysis(
                alpha=len(X) * self.penalty, ties="breslow", n_iter=1000, tol=1e-9,
            )
        else:
            self.estimator = CoxnetSurvivalAnalysis(
                alphas=[self.penalty], l1_ratio=1.0 if self.kind == "lasso" else 0.5,
                normalize=False, fit_baseline_model=True, max_iter=1000000, tol=1e-9,
            )
        self.estimator.fit(X, Surv.from_arrays(y_event.astype(bool), y_time))
        if not np.isfinite(self.estimator.coef_).all():
            raise RuntimeError("nonfinite penalized Cox coefficients")
        return self

    def predict_risk(self, X: pd.DataFrame) -> np.ndarray:
        """Return the fitted linear predictor."""
        return np.asarray(self.estimator.predict(X), dtype=float)

    def predict_survival(self, X: pd.DataFrame, eval_times: np.ndarray) -> np.ndarray:
        """Evaluate survival functions through the supported training follow-up."""
        functions = self.estimator.predict_survival_function(X)
        return np.vstack([function(eval_times) for function in functions])
