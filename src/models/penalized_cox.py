"""Penalised Cox comparators: ridge, lasso and elastic net (ADR-035 extension).

Penalised Cox regression is the frequentist counterpart of Bayesian
shrinkage. A penalty on the size of the coefficients stabilises the fit:

- ridge shrinks all coefficients smoothly;
- lasso can set some coefficients exactly to zero;
- elastic net mixes the two (here half-and-half, ``l1_ratio = 0.5``).

This class fits one fixed penalty. The extension pipeline chooses the
penalty by inner cross-validation inside each training fold.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sksurv.linear_model import CoxnetSurvivalAnalysis, CoxPHSurvivalAnalysis
from sksurv.util import Surv

from src.models.base import BaseSurvivalModel


class PenalizedCox(BaseSurvivalModel):
    """One penalised Cox model with a fixed penalty strength.

    The penalty is on the per-subject (mean) scale of the log partial
    likelihood. Lasso and elastic net use scikit-survival's
    ``CoxnetSurvivalAnalysis``, which works on that scale. Ridge uses
    ``CoxPHSurvivalAnalysis``, whose objective sums over subjects, so the
    penalty is multiplied by the number of training subjects to match. Tied
    event times use the Breslow approximation.
    """

    def __init__(self, kind: str, penalty: float) -> None:
        """Store the penalty type and strength.

        Args:
            kind: ``"ridge"``, ``"lasso"`` or ``"elastic_net"``.
            penalty: Positive penalty strength on the mean scale.

        Raises:
            ValueError: Unknown ``kind`` or a non-positive penalty.
        """
        if kind not in {"ridge", "lasso", "elastic_net"} or penalty <= 0:
            raise ValueError("invalid Cox penalty specification")
        self.kind, self.penalty = kind, float(penalty)

    def fit(self, X: pd.DataFrame, y_time: np.ndarray, y_event: np.ndarray) -> PenalizedCox:
        """Fit the model with this penalty; the penalty itself is chosen elsewhere.

        Raises:
            RuntimeError: The fitted coefficients are not finite.
        """
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
        """Return the linear predictor ``x beta`` (log relative hazard); higher is riskier."""
        return np.asarray(self.estimator.predict(X), dtype=float)

    def predict_survival(self, X: pd.DataFrame, eval_times: np.ndarray) -> np.ndarray:
        """Return survival probabilities, shape (n_subjects, len(eval_times)).

        scikit-survival's Breslow baseline covers only the training
        follow-up; ``eval_times`` must lie within it.
        """
        functions = self.estimator.predict_survival_function(X)
        return np.vstack([function(eval_times) for function in functions])
