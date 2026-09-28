"""Random survival forest (RSF) comparator built on scikit-survival.

Each tree is grown on a bootstrap sample of the training fold with log-rank
splitting. Each leaf stores a Nelson-Aalen cumulative hazard and a
Kaplan-Meier survival curve, and the forest averages each over trees. The
confirmatory pipeline tunes
``min_samples_leaf`` and ``max_features`` by inner cross-validation and
holds 300 trees and ``min_samples_split`` = 10 fixed.
"""

import numpy as np
import pandas as pd
from sksurv.ensemble import RandomSurvivalForest
from sksurv.util import Surv

from src.models.base import BaseSurvivalModel


class RandomSurvivalForestModel(BaseSurvivalModel):
    """Random survival forest with permutation feature importance.

    Arguments are passed unchanged to scikit-survival's forest. The
    confirmatory configuration uses ``n_jobs=1``.

    Args:
        n_estimators: Number of bootstrap-grown survival trees.
        min_samples_split: Minimum subjects required to split a node.
        min_samples_leaf: Minimum subjects in each resulting leaf.
        max_depth: Maximum tree depth; ``None`` leaves it unrestricted.
        max_features: Features considered per split. ``"sqrt"`` uses
            the square root of the feature count; ``"log2"`` uses its
            logarithm; a float in (0, 1] selects a fraction, a positive
            integer sets a count, and ``None`` uses every feature.
        random_state: Seed for tree sampling and permutation importance.
        n_jobs: Parallel workers; -1 uses all available processors.
    """

    def __init__(
        self,
        n_estimators: int = 300,
        min_samples_split: int = 10,
        min_samples_leaf: int = 15,
        max_depth: int | None = None,
        max_features: str = "sqrt",
        random_state: int = 42,
        n_jobs: int = -1,
    ) -> None:
        """Store forest settings and initialise the unfitted model."""
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
        """Fit log-rank survival trees on the supplied training fold.

        Args:
            X: Preprocessed covariates of shape (n_subjects, n_features).
            y_time: Follow-up times of shape (n_subjects,), in the cohort's
                own unit (days or months).
            y_event: Indicators of shape (n_subjects,), 1 for an observed
                event and 0 for censoring.

        Returns:
            The fitted forest.
        """
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
        """Return cumulative hazard summed over distinct training event times.

        scikit-survival's risk score is ``sum_j H(T_j | x)``. It is
        non-negative and not on a log scale; larger values mean greater risk.

        Args:
            X: Preprocessed covariates containing every fitted feature column.

        Returns:
            Risk scores of shape (n_subjects,).

        Raises:
            RuntimeError: The model has not been fitted.
        """
        self._check_fitted()
        return self.model.predict(X[self.feature_names])

    def predict_survival(self, X: pd.DataFrame, eval_times: np.ndarray) -> np.ndarray:
        """Evaluate ensemble survival step functions at requested times.

        Args:
            X: Preprocessed covariates containing every fitted feature column.
            eval_times: Times of shape (n_times,) in the cohort's own unit,
                within [0, largest training follow-up time].

        Returns:
            Survival probabilities of shape (n_subjects, n_times).

        Raises:
            RuntimeError: The model has not been fitted.
            ValueError: A requested time lies outside the fitted step
                functions' domain or is non-finite.
        """
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
        """Measure drops in Harrell's concordance index after feature shuffling.

        Each feature is shuffled ``n_repeats`` times using ``random_state``.
        Features are processed in fitted-column order, fixing the random
        stream. A negative drop means that shuffling improved the score.

        Args:
            X: Covariates to score, containing every fitted feature column.
            y_time: Matching follow-up times in the cohort's own unit.
            y_event: Matching event indicators (0/1).
            n_repeats: Positive number of independent shuffles per feature.

        Returns:
            A frame with ``feature``, ``importance_mean`` and
            ``importance_std`` (population standard deviation, denominator
            n_repeats), sorted by mean drop in descending order.

        Raises:
            RuntimeError: The model has not been fitted.
            ValueError: The outcomes are invalid for concordance evaluation.
        """
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
                score, _ = concordance_index(y_time, y_event, self.predict_risk(permuted))
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
        """Raise ``RuntimeError`` if :meth:`fit` has not been called."""
        if self.model is None:
            raise RuntimeError("Model is not fitted. Call fit() first.")
