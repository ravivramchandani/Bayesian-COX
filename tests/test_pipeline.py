"""Package imports and the active fold-local pipeline on a real cohort.

The whole file verifies INV-006. Every package under ``src/`` must import, and
a Cox proportional hazards (PH) model on GBSG2, with training-fitted
preprocessing, must run through ``evaluate_model`` and
``training_event_time_horizons`` (``src/evaluation/metrics.py``),
``time_dependent_auc_at`` (``src/evaluation/ranking.py``), the confirmatory
truncation rule for inverse probability of censoring weighting (IPCW) and the
legacy ``BootstrapResampler`` (``src/statistics/bootstrap.py``). The metrics
are Harrell's and Uno's concordance indices (C-indices), the integrated Brier
score (IBS) and the time-dependent area under the receiver operating
characteristic curve (AUC).
"""

import importlib
from pathlib import Path

import numpy as np
import pytest

from src.data.fold_preprocessing import FoldFeaturePreprocessor
from src.evaluation.metrics import evaluate_model, training_event_time_horizons
from src.evaluation.ranking import time_dependent_auc_at
from src.models.cox import CoxPHModel
from src.pipelines.confirmatory import administratively_truncate_for_ipcw
from src.statistics.bootstrap import BootstrapResampler
from tests.cohort_fixtures import prepare_real_fold

ROOT = Path(__file__).resolve().parents[1]
# Dotted names of every directory under src/ that has an __init__.py.
PACKAGES = sorted(
    ".".join(path.parent.relative_to(ROOT).parts) for path in (ROOT / "src").rglob("__init__.py")
)


@pytest.fixture(scope="module")
def fitted():
    """Cox PH fitted on the GBSG2 first-fold training rows, with the prepared fold."""
    prepared = prepare_real_fold("gbsg2")
    indices = prepared.fold.train_indices
    model = CoxPHModel().fit(prepared.train, prepared.time[indices], prepared.event[indices])
    return model, prepared


@pytest.mark.parametrize("package", PACKAGES)
def test_package_imports(package):
    """Every package under src/ imports without error (INV-006)."""
    importlib.import_module(package)


def _evaluate_fold(model, validation, train_time, train_event, validation_time, validation_event):
    """Evaluate one outer fold with training-derived horizons and training censoring.

    Args:
        model: Fitted model with ``predict_risk`` and ``predict_survival``.
        validation: Preprocessed validation features.
        train_time: Training follow-up times; with ``train_event`` they set the
            horizons and the censoring weights.
        train_event: Training event indicators.
        validation_time: Validation follow-up times before truncation.
        validation_event: Validation event indicators before truncation.

    Returns:
        The metric dictionary from ``evaluate_model``.
    """
    horizons = training_event_time_horizons(train_time, train_event)
    # Censor validation follow-up just after the last horizon, as the
    # confirmatory pipeline does; later follow-up could need censoring weights
    # that the training data cannot supply.
    truncated_time, truncated_event = administratively_truncate_for_ipcw(
        validation_time, validation_event, float(horizons[-1])
    )
    return evaluate_model(
        train_time=train_time,
        train_event=train_event,
        test_time=truncated_time,
        test_event=truncated_event,
        risk_scores=model.predict_risk(validation),
        survival_probs=model.predict_survival(validation, horizons),
        eval_times=horizons,
    )


def test_outer_fold_evaluation_uses_training_censoring(fitted):
    """Outer-fold evaluation with training censoring gives bounded C-indices and IBS (INV-006)."""
    model, prepared = fitted
    training = prepared.fold.train_indices
    validation = prepared.fold.validation_indices
    result = _evaluate_fold(
        model,
        prepared.validation,
        prepared.time[training],
        prepared.event[training],
        prepared.time[validation],
        prepared.event[validation],
    )
    assert 0 <= result["c_index"] <= 1
    assert 0 <= result["uno_c_index"] <= 1
    assert 0 <= result["ibs"] <= 1
    assert np.isfinite(result["mean_auc"])


def test_time_dependent_auc_at_single_time(fitted):
    """Single-time AUC at the second training horizon is finite and within [0, 1] (INV-006)."""
    model, prepared = fitted
    training = prepared.fold.train_indices
    validation = prepared.fold.validation_indices
    horizon = float(
        training_event_time_horizons(prepared.time[training], prepared.event[training])[1]
    )
    validation_time, validation_event = administratively_truncate_for_ipcw(
        prepared.time[validation], prepared.event[validation], horizon
    )
    auc = time_dependent_auc_at(
        validation_time,
        validation_event,
        model.predict_risk(prepared.validation),
        horizon,
        train_time=prepared.time[training],
        train_event=prepared.event[training],
    )
    assert np.isfinite(auc)
    assert 0 <= auc <= 1


def test_bootstrap_resampler_runs(fitted):
    """The legacy bootstrap gives C-index replicates in [0, 1] on training-fold predictions (INV-006)."""
    model, prepared = fitted
    training = prepared.fold.train_indices
    # BootstrapResampler draws unstratified subject resamples of the training
    # rows; the event-stratified sampler lives in src.statistics.resampling.
    result = BootstrapResampler(n_bootstraps=20, random_state=42).bootstrap_metrics(
        y_time=prepared.time[training],
        y_event=prepared.event[training],
        risk_scores=model.predict_risk(prepared.train),
    )
    assert result["c_index"]
    assert all(0 <= score <= 1 for score in result["c_index"])


def test_fold_local_cross_validation_runs():
    """Fold-local refits validate every GBSG2 subject exactly once within a repeat (INV-006)."""
    prepared = prepare_real_fold("gbsg2")
    validation_ids = []
    for fold in prepared.folds:
        processor = FoldFeaturePreprocessor(prepared.dataset_config["primary_features"])
        processor.fit(prepared.raw.iloc[fold.train_indices])
        train = processor.transform(prepared.raw.iloc[fold.train_indices])
        validation = processor.transform(prepared.raw.iloc[fold.validation_indices])
        model = CoxPHModel().fit(
            train, prepared.time[fold.train_indices], prepared.event[fold.train_indices]
        )
        result = _evaluate_fold(
            model,
            validation,
            prepared.time[fold.train_indices],
            prepared.event[fold.train_indices],
            prepared.time[fold.validation_indices],
            prepared.event[fold.validation_indices],
        )
        assert 0 <= result["ibs"] <= 1
        assert np.isfinite(result["uno_c_index"])
        validation_ids.extend(prepared.subject_ids[fold.validation_indices])
    assert len(validation_ids) == len(prepared.raw)
    assert len(set(validation_ids)) == len(prepared.raw)
