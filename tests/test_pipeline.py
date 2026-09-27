"""Package imports and the active fold-local pipeline on a real cohort."""

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
PACKAGES = sorted(
    ".".join(path.parent.relative_to(ROOT).parts) for path in (ROOT / "src").rglob("__init__.py")
)


@pytest.fixture(scope="module")
def fitted():
    prepared = prepare_real_fold("gbsg2")
    indices = prepared.fold.train_indices
    model = CoxPHModel().fit(prepared.train, prepared.time[indices], prepared.event[indices])
    return model, prepared


@pytest.mark.parametrize("package", PACKAGES)
def test_package_imports(package):
    importlib.import_module(package)


def _evaluate_fold(model, validation, train_time, train_event, validation_time, validation_event):
    horizons = training_event_time_horizons(train_time, train_event)
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
    model, prepared = fitted
    training = prepared.fold.train_indices
    result = BootstrapResampler(n_bootstraps=20, random_state=42).bootstrap_metrics(
        y_time=prepared.time[training],
        y_event=prepared.event[training],
        risk_scores=model.predict_risk(prepared.train),
    )
    assert result["c_index"]
    assert all(0 <= score <= 1 for score in result["c_index"])


def test_fold_local_cross_validation_runs():
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
