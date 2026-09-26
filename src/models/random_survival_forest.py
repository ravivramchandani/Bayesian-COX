"""Random survival forest baseline built on scikit-survival."""

import numpy as np
import pandas as pd
from sksurv.ensemble import RandomSurvivalForest
from sksurv.util import Surv

from src.models.base import BaseSurvivalModel


class RandomSurvivalForestModel(BaseSurvivalModel):
    """Random survival forest with permutation feature importance."""

    def __init__(
        self,
        n_estimators: int = 300,
        min_samples_split: int = 10,
        min_samples_leaf: int = 15,
        max_depth: int | None = None,
        max_features: str = "sqrt",
        random_state: int = 42,
        n_jobs: int = -1,
    ):
        self.n_estimators = n_estimators
        self.min_samples_split = min_samples_split
        self.min_samples_leaf = min_samples_leaf
        self.max_depth = max_depth
        self.max_features = max_features
        self.random_state = random_state
        self.n_jobs = n_jobs

        self.model: RandomSurvivalForest | None = None
        self.feature_names: list[str] = []

    def fit(
        self, X: pd.DataFrame, y_time: np.ndarray, y_event: np.ndarray
    ) -> "RandomSurvivalForestModel":
        self.feature_names = list(X.columns)
        y = Surv.from_arrays(
            event=np.asarray(y_event).astype(bool),
            time=np.asarray(y_time, dtype=float),
        )

        self.model = RandomSurvivalForest(
            n_estimators=self.n_estimators,
            min_samples_split=self.min_samples_split,
            min_samples_leaf=self.min_samples_leaf,
            max_depth=self.max_depth,
            max_features=self.max_features,
            random_state=self.random_state,
            n_jobs=self.n_jobs,
        )
        self.model.fit(X[self.feature_names], y)
        return self

    def predict_risk(self, X: pd.DataFrame) -> np.ndarray:
        """Ensemble cumulative hazard; higher means higher risk."""
        self._check_fitted()
        return self.model.predict(X[self.feature_names])

    def predict_survival(self, X: pd.DataFrame, eval_times: np.ndarray) -> np.ndarray:
        """Survival probabilities of shape (n_samples, n_times)."""
        self._check_fitted()
        funcs = self.model.predict_survival_function(X[self.feature_names])
        eval_times = np.asarray(eval_times, dtype=float)
        return np.vstack([fn(eval_times) for fn in funcs])

    def permutation_importance(
        self,
        X: pd.DataFrame,
        y_time: np.ndarray,
        y_event: np.ndarray,
        n_repeats: int = 10,
    ) -> pd.DataFrame:
        """Drop in C-index when each feature is permuted."""
        from src.evaluation.metrics import concordance_index

        self._check_fitted()
        rng = np.random.default_rng(self.random_state)

        baseline, _ = concordance_index(y_time, y_event, self.predict_risk(X))

        rows = []
        for feature in self.feature_names:
            drops = []
            for _ in range(n_repeats):
                permuted = X.copy()
                permuted[feature] = rng.permutation(permuted[feature].to_numpy())
                score, _ = concordance_index(
                    y_time, y_event, self.predict_risk(permuted)
                )
                drops.append(baseline - score)
            rows.append(
                {
                    "feature": feature,
                    "importance_mean": float(np.mean(drops)),
                    "importance_std": float(np.std(drops)),
                }
            )

        return (
            pd.DataFrame(rows)
            .sort_values("importance_mean", ascending=False)
            .reset_index(drop=True)
        )

    def _check_fitted(self) -> None:
        if self.model is None:
            raise RuntimeError("Model is not fitted. Call fit() first.")
