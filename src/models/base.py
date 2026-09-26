"""Common interface for the four survival model families in the study.

Cox proportional hazards, random survival forest, DeepSurv and the Bayesian
piecewise-exponential model all implement :class:`BaseSurvivalModel`, so the
confirmatory pipeline can fit, score and evaluate them the same way.
"""

from abc import ABC, abstractmethod

import numpy as np
import pandas as pd


class BaseSurvivalModel(ABC):
    """Abstract base class for survival models with risk and survival predictions."""

    @abstractmethod
    def fit(
        self, X: pd.DataFrame, y_time: np.ndarray, y_event: np.ndarray
    ) -> "BaseSurvivalModel":
        """Fit the model on training covariates, follow-up times and event indicators."""

    @abstractmethod
    def predict_risk(self, X: pd.DataFrame) -> np.ndarray:
        """Return one risk score per row; higher scores mean shorter expected survival.

        Only the ranking is comparable across models, because the scale
        differs: Cox returns the partial hazard ``exp(x beta)``, the random
        survival forest the ensemble cumulative hazard, DeepSurv the network
        log-risk, and the Bayesian model the posterior-mean linear predictor.
        """

    @abstractmethod
    def predict_survival(self, X: pd.DataFrame, eval_times: np.ndarray) -> np.ndarray:
        """Return survival probabilities ``S(t | x)`` of shape (n_samples, n_times)."""

    def get_summary(self) -> pd.DataFrame:
        """Return a summary of fitted parameters, or an empty frame if none applies."""
        return pd.DataFrame()


# Alias for backwards compatibility
BaseModel = BaseSurvivalModel
