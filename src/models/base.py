"""Common interface for the four survival model families in the study.

Cox proportional hazards (PH), random survival forest (RSF), DeepSurv and the
Bayesian piecewise-exponential model all implement
:class:`BaseSurvivalModel`, so the confirmatory pipeline can fit, score and
evaluate them the same way: ``fit`` on the preprocessed outer-training fold,
then ``predict_risk`` and ``predict_survival`` on the validation fold.
"""

from abc import ABC, abstractmethod

import numpy as np
import pandas as pd


class BaseSurvivalModel(ABC):
    """Abstract base class for survival models with risk and survival predictions."""

    @abstractmethod
    def fit(self, X: pd.DataFrame, y_time: np.ndarray, y_event: np.ndarray) -> "BaseSurvivalModel":
        """Fit training covariates, follow-up times and event indicators.

        Args:
            X: Preprocessed covariates of shape (n_subjects, n_features).
            y_time: Follow-up times of shape (n_subjects,), in the cohort's
                own unit (days or months).
            y_event: Indicators of shape (n_subjects,), 1 for an observed
                event and 0 for censoring.

        Returns:
            The fitted model.
        """

    @abstractmethod
    def predict_risk(self, X: pd.DataFrame) -> np.ndarray:
        """Return one risk score per row; higher scores mean greater event risk.

        Only ranks can be compared across models, because their scales differ:

        - Cox: partial hazard ``exp((x - x_mean) beta)``, centred at the
          training-fold covariate means by lifelines.
        - Random survival forest: ensemble cumulative hazard summed over
          the distinct training event times.
        - DeepSurv: network output ``g(x)``, a log partial hazard.
        - Bayesian model: posterior-mean linear predictor ``x E[beta]``,
          a log hazard ratio.

        Args:
            X: Preprocessed covariates containing the fitted feature columns.

        Returns:
            Risk scores of shape (n_subjects,).
        """

    @abstractmethod
    def predict_survival(self, X: pd.DataFrame, eval_times: np.ndarray) -> np.ndarray:
        """Return survival probabilities ``S(t | x)`` at requested times.

        Args:
            X: Preprocessed covariates of shape (n_subjects, n_features).
            eval_times: Times of shape (n_times,) in the cohort's own unit.

        Returns:
            Probabilities of shape (n_subjects, n_times), with columns in
            evaluation-time order.
        """

    def get_summary(self) -> pd.DataFrame:
        """Return a parameter summary when a subclass supplies one.

        Returns:
            An empty data frame in this base implementation.
        """
        return pd.DataFrame()


# Older name kept so existing imports still work.
BaseModel = BaseSurvivalModel
