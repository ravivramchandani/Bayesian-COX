"""Cox proportional hazards (PH) comparator built on lifelines.

The confirmatory pipeline fits :class:`CoxPHModel` on each outer-training
fold, with no outcome-driven tuning. lifelines maximises the Cox partial
likelihood using Efron's method for tied event times, with a ridge penalty
``0.5 * n_subjects * l2_reg * ||beta_standardised||^2``. The confirmatory
configuration uses ``l2_reg = 1e-4``. It estimates the baseline hazard by
Breslow's method. The penalty acts on internally standardised covariates;
reported coefficients are returned to the supplied covariate scale.
"""

import numpy as np
import pandas as pd
from lifelines import CoxPHFitter
from lifelines.statistics import proportional_hazard_test

from src.models.base import BaseSurvivalModel


class CoxPHModel(BaseSurvivalModel):
    """Cox PH comparator with hazard ratios and a Schoenfeld residual test.

    Args:
        l2_reg: lifelines ``penalizer`` (pure ridge penalty).
        random_state: Stored for interface consistency; the fit is
            deterministic and does not use it.
    """

    def __init__(self, l2_reg: float = 0.0001, random_state: int = 42) -> None:
        """Store the ridge penalty and initialise the unfitted model."""
        self.l2_reg = l2_reg
        self.random_state = random_state
        self.fitter: CoxPHFitter | None = None
        self.feature_names: list[str] = []
        self._train_time: np.ndarray | None = None
        self._train_event: np.ndarray | None = None

    def fit(self, X: pd.DataFrame, y_time: np.ndarray, y_event: np.ndarray) -> "CoxPHModel":
        """Fit penalised Cox partial likelihood on the supplied training fold.

        Args:
            X: Preprocessed covariates of shape (n_subjects, n_features),
                with feature names distinct from ``time`` and ``event``.
            y_time: Follow-up times of shape (n_subjects,), in the cohort's
                own unit (days or months).
            y_event: Indicators of shape (n_subjects,), 1 for an observed
                event and 0 for censoring.

        Returns:
            The fitted model.
        """
        self.feature_names = list(X.columns)
        self._train_time = np.asarray(y_time, dtype=float)
        self._train_event = np.asarray(y_event, dtype=int)

        df = X.copy()
        df["time"] = self._train_time
        df["event"] = self._train_event

        self.fitter = CoxPHFitter(penalizer=self.l2_reg)
        self.fitter.fit(df, duration_col="time", event_col="event")
        return self

    def predict_risk(self, X: pd.DataFrame) -> np.ndarray:
        """Return partial hazard ``exp((x - x_mean) beta)`` for each subject.

        lifelines centres covariates at their training-fold means, so these
        hazard ratios compare subjects with one whose covariates are average.
        The score is exponentiated; larger values mean greater hazard.

        Args:
            X: Preprocessed covariates containing every fitted feature column.

        Returns:
            Partial hazards of shape (n_subjects,).

        Raises:
            RuntimeError: The model has not been fitted.
        """
        self._check_fitted()
        return self.fitter.predict_partial_hazard(X[self.feature_names]).to_numpy()

    def predict_survival(self, X: pd.DataFrame, eval_times: np.ndarray) -> np.ndarray:
        """Return survival probabilities from the fitted Breslow baseline.

        Args:
            X: Preprocessed covariates containing every fitted feature column.
            eval_times: Times of shape (n_times,) in the cohort's own unit.

        Returns:
            Survival probabilities of shape (n_subjects, n_times).

        Raises:
            RuntimeError: The model has not been fitted.
        """
        self._check_fitted()
        surv = self.fitter.predict_survival_function(
            X[self.feature_names], times=np.asarray(eval_times, dtype=float)
        )
        return surv.to_numpy().T

    def summary(self) -> pd.DataFrame:
        """Return coefficient, hazard-ratio and Wald-test summaries.

        Returns:
            One row per feature with ``coef`` and ``se`` on the log
            hazard-ratio scale, ``hazard_ratio`` and its 95% confidence
            bounds ``ci_lower``/``ci_upper``, plus ``z`` and ``p``.

        Raises:
            RuntimeError: The model has not been fitted.
        """
        self._check_fitted()
        s = self.fitter.summary
        return pd.DataFrame(
            {
                "feature": s.index,
                "coef": s["coef"].to_numpy(),
                "hazard_ratio": s["exp(coef)"].to_numpy(),
                "se": s["se(coef)"].to_numpy(),
                "ci_lower": s["exp(coef) lower 95%"].to_numpy(),
                "ci_upper": s["exp(coef) upper 95%"].to_numpy(),
                "z": s["z"].to_numpy(),
                "p": s["p"].to_numpy(),
            }
        ).reset_index(drop=True)

    def proportional_hazards_test(
        self, X: pd.DataFrame, y_time: np.ndarray, y_event: np.ndarray
    ) -> pd.DataFrame:
        """Test the proportional-hazards assumption for each covariate.

        lifelines tests scaled Schoenfeld residuals against rank-transformed
        time. Small p-values indicate evidence against a constant coefficient.
        ``ph_satisfied`` is the unadjusted rule ``p > 0.05``; it does not
        establish that the assumption holds. The confirmatory pipeline applies
        Holm's correction separately.

        Args:
            X: The preprocessed training covariates used for this fit.
            y_time: Matching training follow-up times in the cohort's own unit.
            y_event: Matching training event indicators (0/1).

        Returns:
            Columns ``feature``, ``test_statistic``, ``p`` and ``ph_satisfied``.

        Raises:
            RuntimeError: The model has not been fitted.
        """
        self._check_fitted()
        df = X[self.feature_names].copy()
        df["time"] = np.asarray(y_time, dtype=float)
        df["event"] = np.asarray(y_event, dtype=int)

        result = proportional_hazard_test(self.fitter, df, time_transform="rank")
        table = result.summary.reset_index()
        table.columns = ["feature", *list(table.columns[1:])]
        table["ph_satisfied"] = table["p"] > 0.05
        return table[["feature", "test_statistic", "p", "ph_satisfied"]]

    def _check_fitted(self) -> None:
        """Raise ``RuntimeError`` if :meth:`fit` has not been called."""
        if self.fitter is None:
            raise RuntimeError("Model is not fitted. Call fit() first.")
