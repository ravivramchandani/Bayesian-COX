"""Cox proportional hazards baseline built on lifelines."""

import numpy as np
import pandas as pd
from lifelines import CoxPHFitter
from lifelines.statistics import proportional_hazard_test

from src.models.base import BaseSurvivalModel


class CoxPHModel(BaseSurvivalModel):
    """Cox PH baseline with hazard ratios and a Schoenfeld residual test."""

    def __init__(self, l2_reg: float = 0.0001, random_state: int = 42):
        self.l2_reg = l2_reg
        self.random_state = random_state
        self.fitter: CoxPHFitter | None = None
        self.feature_names: list[str] = []
        self._train_time: np.ndarray | None = None
        self._train_event: np.ndarray | None = None

    def fit(
        self, X: pd.DataFrame, y_time: np.ndarray, y_event: np.ndarray
    ) -> "CoxPHModel":
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
        """Linear predictor; higher means higher hazard."""
        self._check_fitted()
        return self.fitter.predict_partial_hazard(X[self.feature_names]).to_numpy()

    def predict_survival(self, X: pd.DataFrame, eval_times: np.ndarray) -> np.ndarray:
        """Survival probabilities of shape (n_samples, n_times)."""
        self._check_fitted()
        surv = self.fitter.predict_survival_function(
            X[self.feature_names], times=np.asarray(eval_times, dtype=float)
        )
        return surv.to_numpy().T

    def summary(self) -> pd.DataFrame:
        """Coefficients, hazard ratios, confidence intervals and p-values."""
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
        """Schoenfeld residual test per covariate."""
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
        if self.fitter is None:
            raise RuntimeError("Model is not fitted. Call fit() first.")
