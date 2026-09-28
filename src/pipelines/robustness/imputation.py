"""Create fold-local multiple imputations and average their fitted predictions.

Used only by the METABRIC ``npi_plus_stage`` feature condition with
``imputation_method="iterative_posterior_m5"``. :mod:`cells` calls
:func:`multiple_imputed_fold_frames`, fits one Bayesian model per imputed
training frame and scores the average of their predictions through
:class:`_MultipleImputationPredictionEnsemble`. This is an imputation
sensitivity: the five posteriors are not combined into one posterior that
propagates imputation uncertainty.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import numpy as np
import pandas as pd
from sklearn.experimental import enable_iterative_imputer  # noqa: F401
from sklearn.impute import IterativeImputer

from .protocol import (
    ITERATIVE_IMPUTER_MAX_ITER,
    MULTIPLE_IMPUTATIONS,
)


def multiple_imputed_fold_frames(
    raw_training: pd.DataFrame,
    raw_validation: pd.DataFrame,
    feature_spec: dict[str, Any],
    *,
    seeds: Iterable[int],
) -> list[tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]]:
    """Fit five stochastic numeric imputers on training data only.

    Numeric variables use posterior draws from an iterative Bayesian-ridge
    imputer. Categorical and ordinal missing values use a mode learned from
    the same outer-training fold. Each returned validation frame is transformed
    by its corresponding fitted imputer without refitting.

    ``sample_posterior=True`` makes each imputer draw imputed values from its
    predictive distribution rather than use the conditional mean. The five
    seeds allow completed data sets to differ where numeric values are missing.

    Args:
        raw_training: Unprocessed outer-training rows.
        raw_validation: Unprocessed outer-validation rows.
        feature_spec: The ``npi_plus_stage`` feature declaration.
        seeds: Five distinct imputer seeds.

    Returns:
        Five ``(training frame, validation frame, metadata)`` triples, in
        seed order.

    Raises:
        ValueError: The numeric features are not METABRIC age, Nottingham
            prognostic index (NPI) and tumour stage, the seeds are not five
            distinct values, or a categorical feature has no observed
            training value.
    """
    numeric = [str(name) for name in feature_spec.get("numeric", [])]
    categorical = [str(name) for name in feature_spec.get("categorical", [])]
    ordinal = [str(name) for name in feature_spec.get("ordinal", {})]
    if set(numeric) != {
        "age_at_diagnosis",
        "nottingham_prognostic_index",
        "tumor_stage",
    }:
        raise ValueError(
            "the frozen multiple-imputation sensitivity is defined only for "
            "METABRIC age, NPI and tumour stage"
        )
    seed_values = [int(seed) for seed in seeds]
    if len(seed_values) != MULTIPLE_IMPUTATIONS or len(set(seed_values)) != len(seed_values):
        raise ValueError("multiple imputation requires five distinct seeds")

    train_base = raw_training.copy()
    validation_base = raw_validation.copy()
    modes: dict[str, Any] = {}
    for name in [*categorical, *ordinal]:
        observed = train_base[name].dropna()
        if observed.empty:
            raise ValueError(f"categorical feature {name!r} has no training mode")
        mode_values = observed.mode(dropna=True)
        mode = mode_values.iloc[0]
        modes[name] = mode
        train_base[name] = train_base[name].fillna(mode)
        validation_base[name] = validation_base[name].fillna(mode)

    train_numeric = train_base[numeric].apply(pd.to_numeric, errors="coerce")
    validation_numeric = validation_base[numeric].apply(pd.to_numeric, errors="coerce")
    results: list[tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]] = []
    for imputation, seed in enumerate(seed_values, start=1):
        imputer = IterativeImputer(
            max_iter=ITERATIVE_IMPUTER_MAX_ITER,
            sample_posterior=True,
            random_state=seed,
            skip_complete=False,
        )
        imputed_training = imputer.fit_transform(train_numeric)
        imputed_validation = imputer.transform(validation_numeric)
        train_frame = train_base.copy()
        validation_frame = validation_base.copy()
        train_frame.loc[:, numeric] = imputed_training
        validation_frame.loc[:, numeric] = imputed_validation
        metadata = {
            "imputation": imputation,
            "seed": seed,
            "implementation": "sklearn.impute.IterativeImputer",
            "estimator": "BayesianRidge (IterativeImputer default)",
            "sample_posterior": True,
            "max_iter": ITERATIVE_IMPUTER_MAX_ITER,
            "numeric_columns": numeric,
            "categorical_mode_columns": [*categorical, *ordinal],
            "categorical_modes": {name: str(value) for name, value in modes.items()},
            "fit_scope": "outer training fold only",
            "validation_refit": False,
        }
        results.append((train_frame, validation_frame, metadata))
    return results


class _MultipleImputationPredictionEnsemble:
    """Average predictions from independently fitted imputation-specific models.

    The ensemble is bound to one outer-validation fold: model ``m`` predicts
    on its own imputed validation frame ``m``. The ``frame`` argument of the
    prediction methods is used only to check the number of rows, so the
    ensemble can be passed wherever a fitted model is expected.

    Args:
        models: Five fitted Bayesian models in imputation order.
        validation_frames: Their corresponding processed validation frames;
            rows must represent the same subjects in the same order.

    Raises:
        ValueError: The numbers of models and frames are not both five.
    """

    def __init__(self, models: list[Any], validation_frames: list[pd.DataFrame]) -> None:
        """Bind exactly five fitted models to their corresponding validation frames."""
        if len(models) != MULTIPLE_IMPUTATIONS or len(models) != len(validation_frames):
            raise ValueError("prediction ensemble requires all five imputations")
        self.models = models
        self.validation_frames = validation_frames

    def predict_risk(self, frame: pd.DataFrame) -> np.ndarray:
        """Average imputation-specific posterior-mean linear-predictor scores.

        Args:
            frame: Frame with the bound fold's row count; its values are not used.

        Returns:
            An array of shape (validation subjects,) in the bound subject order.

        Raises:
            ValueError: ``frame`` has a different row count from the bound fold.
        """
        if len(frame) != len(self.validation_frames[0]):
            raise ValueError("ensemble is bound to its outer-validation fold")
        values = [
            np.asarray(model.predict_risk(validation), dtype=float)
            for model, validation in zip(self.models, self.validation_frames, strict=True)
        ]
        return np.mean(values, axis=0)

    def predict_survival(self, frame: pd.DataFrame, evaluation_times: np.ndarray) -> np.ndarray:
        """Average survival probabilities across the bound imputations.

        Args:
            frame: Frame with the bound fold's row count; its values are not used.
            evaluation_times: One-dimensional array of times in the cohort's unit,
                passed unchanged to each fitted model.

        Returns:
            Survival probabilities of shape (validation subjects, evaluation times).

        Raises:
            ValueError: ``frame`` has a different row count from the bound fold.
        """
        if len(frame) != len(self.validation_frames[0]):
            raise ValueError("ensemble is bound to its outer-validation fold")
        values = [
            np.asarray(model.predict_survival(validation, evaluation_times), dtype=float)
            for model, validation in zip(self.models, self.validation_frames, strict=True)
        ]
        return np.mean(values, axis=0)
