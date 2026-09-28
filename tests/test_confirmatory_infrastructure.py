"""Leakage, pairing and lineage checks for the confirmatory infrastructure.

Protects ``src/data/fold_preprocessing.py``, ``src/data/survival_folds.py``,
the canonical hash in ``src/utils/reproducibility.py`` and the
``src.pipelines.confirmatory`` package: the survival-prediction gate, the
Bayesian refit rule, IPCW (inverse probability of censoring weighting)
truncation, the paired OOF (out-of-fold) bootstrap and the repeated-CV
(cross-validation) inference roster. Inputs are small synthetic arrays.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import src.pipelines.confirmatory as confirmatory_pipeline
from src.data.fold_preprocessing import FoldFeaturePreprocessor
from src.data.survival_folds import event_time_strata, repeated_survival_folds
from src.pipelines.confirmatory import (
    MODEL_KEYS,
    DiagnosticFailure,
    RunOptions,
    _fit_with_diagnostic_rule,
    _paired_oof_ibs_bootstrap,
    _repeated_cv_inference,
    administratively_truncate_for_ipcw,
    validate_survival_prediction_matrix,
)
from src.utils.reproducibility import canonical_json_hash


def _feature_spec():
    """Return a feature specification with numeric, categorical, ordinal and engineered terms."""
    return {
        "numeric": ["age", "biomarker"],
        "categorical": ["sex"],
        "ordinal": {"grade": ["I", "II", "III"]},
        "engineered": [
            {
                "name": "log_biomarker",
                "expression": "log1p(biomarker)",
                "source_features": ["biomarker"],
            }
        ],
    }


def test_fold_preprocessing_ignores_validation_distribution():
    """Preprocessing state comes from training rows only and survives restore (ADR-014)."""
    # Training includes a missing biomarker and a missing sex, so imputation and
    # the missing category are learned from training data.
    training = pd.DataFrame(
        {
            "age": [40.0, 50.0, 60.0, 70.0],
            "biomarker": [0.0, 2.0, np.nan, 8.0],
            "sex": ["F", "M", "F", None],
            "grade": ["I", "II", "III", "II"],
        }
    )
    # Validation has out-of-range values and categories never seen in training.
    validation = pd.DataFrame(
        {
            "age": [45.0, 90.0],
            "biomarker": [1.0, 1000.0],
            "sex": ["F", "unseen"],
            "grade": ["II", "unseen"],
        }
    )

    first = FoldFeaturePreprocessor(_feature_spec()).fit(training)
    state_before = first.metadata()
    transformed = first.transform(validation)

    # Transforming extreme validation values must not change the fitted state.
    altered = validation.copy()
    altered.loc[:, "age"] = [-1e9, 1e9]
    altered.loc[:, "biomarker"] = [0.0, 1e12]
    first.transform(altered)

    assert first.metadata() == state_before
    assert list(transformed.columns) == state_before["feature_names"]
    sex_columns = [name for name in transformed if name.startswith("sex=")]
    # An unseen category sets every indicator to zero, as for the reference level.
    assert transformed.loc[1, sex_columns].sum() == 0.0
    # The unseen ordinal grade is coded -1 before scaling, so values stay finite.
    assert np.isfinite(transformed.to_numpy()).all()

    # Refitting gives the same state hash, and state restored from metadata
    # transforms identically.
    second = FoldFeaturePreprocessor(_feature_spec()).fit(training)
    assert second.metadata()["training_state_sha256"] == state_before[
        "training_state_sha256"
    ]
    restored = FoldFeaturePreprocessor.from_metadata(_feature_spec(), state_before)
    pd.testing.assert_frame_equal(restored.transform(validation), transformed)


def test_repeated_folds_are_deterministic_paired_and_complete():
    """Repeated folds are reproducible and validate every subject once per repeat (ADR-014)."""
    # 100 distinct times with alternating events: 50 subjects per event status.
    times = np.arange(1, 101, dtype=float)
    events = np.tile([0, 1], 50)
    first = repeated_survival_folds(
        times, events, n_splits=5, n_repeats=3, base_seed=742
    )
    second = repeated_survival_folds(
        times, events, n_splits=5, n_repeats=3, base_seed=742
    )

    # Identical folds from a repeated call are what lets every model family be
    # evaluated on the same paired splits.
    assert len(first) == 15
    for left, right in zip(first, second, strict=True):
        assert left.repeat == right.repeat
        assert left.fold == right.fold
        assert np.array_equal(left.train_indices, right.train_indices)
        assert np.array_equal(left.validation_indices, right.validation_indices)

    for repeat in range(1, 4):
        held_out = np.concatenate(
            [fold.validation_indices for fold in first if fold.repeat == repeat]
        )
        assert np.array_equal(np.sort(held_out), np.arange(len(times)))

    # Each event status has 50 subjects, enough for the maximum of four time bins
    # with at least one subject per fold in each, giving 2 x 4 = 8 strata.
    strata = event_time_strata(times, events, n_splits=5)
    assert len(np.unique(strata)) == 8


def test_canonical_hash_is_key_order_independent():
    """The canonical JSON hash does not depend on mapping key order."""
    assert canonical_json_hash({"a": 1, "b": [2, 3]}) == canonical_json_hash(
        {"b": [2, 3], "a": 1}
    )


def test_survival_prediction_gate_rejects_increasing_curve():
    """A predicted survival curve that rises over time is rejected; flat steps are accepted."""
    valid = np.asarray([[0.9, 0.8, 0.6], [1.0, 0.7, 0.7]])
    validate_survival_prediction_matrix(valid, n_samples=2, n_times=3)

    # Survival rising from 0.8 to 0.85 between the last two times is impossible.
    invalid = valid.copy()
    invalid[0, 2] = 0.85
    with np.testing.assert_raises_regex(ValueError, "non-increasing"):
        validate_survival_prediction_matrix(invalid, n_samples=2, n_times=3)


def test_failed_bayesian_attempt_retains_trace_and_model_checks(monkeypatch):
    """A fit that fails the diagnostic gate keeps its trace snapshot and model checks (ADR-027)."""
    class FailedModel:
        """Stand-in Bayesian model whose diagnostics always report non-convergence."""

        target_accept = 0.95
        tune = 10
        noncentered_baseline = False
        diagnostics = {"converged": False, "failures": ["synthetic"]}
        prior_predictive_summary = {"finite": True}
        posterior_predictive_summary = {"replicated_event_counts": {}}

        def fit(self, *_args):
            """Skip sampling; the fixed diagnostics already describe the outcome."""
            return self

    # The refit rule resolves these hooks from the package at call time, so
    # patching the package replaces the model factory and trace collector.
    monkeypatch.setattr(
        confirmatory_pipeline,
        "_model_from_parameters",
        lambda *_args, **_kwargs: FailedModel(),
    )
    monkeypatch.setattr(
        confirmatory_pipeline,
        "_posterior_trace_snapshot",
        lambda _model: {"purpose": "test-snapshot"},
    )
    options = RunOptions(
        mode="confirmatory",
        datasets=("demo",),
        models=("bayesian_normal",),
        outer_splits=5,
        outer_repeats=1,
        fold_limit_per_dataset=None,
        bayes_draws=10,
        bayes_tune=10,
        bayes_chains=2,
        calibration_bootstraps=20,
        resume=False,
        output_root=Path("unused"),
    )
    # No refits allowed, so the single failed attempt raises DiagnosticFailure.
    config = {
        "models": {
            "bayesian_cox": {
                "failed_fit_rule": {
                    "maximum_refits": 0,
                    "refit_target_accept": 0.99,
                    "refit_tune_multiplier": 2,
                }
            }
        }
    }

    with pytest.raises(DiagnosticFailure) as error:
        _fit_with_diagnostic_rule(
            "bayesian_normal",
            {},
            pd.DataFrame({"x": [0.0, 1.0]}),
            np.asarray([1.0, 2.0]),
            np.asarray([0, 1]),
            seed=7,
            config=config,
            options=options,
        )

    attempt = error.value.attempts[0]
    assert attempt["posterior_trace_snapshot"] == {"purpose": "test-snapshot"}
    assert attempt["model_checks"]["prior_predictive"] == {"finite": True}
    assert "replicated_event_counts" in attempt["model_checks"][
        "posterior_predictive"
    ]


def test_ipcw_truncation_uses_only_frozen_tau_and_preserves_known_status():
    """Follow-up beyond tau is censored just above tau; earlier times and events are kept."""
    # Two subjects end before tau = 10 and two after it, one with an event.
    time = np.asarray([2.0, 8.0, 12.0, 20.0])
    event = np.asarray([1, 0, 1, 1])
    truncated_time, truncated_event = administratively_truncate_for_ipcw(
        time, event, 10.0
    )

    np.testing.assert_array_equal(truncated_time[:2], time[:2])
    np.testing.assert_array_equal(truncated_event[:2], event[:2])
    # Censoring at the next float above tau keeps these subjects known to be
    # event-free up to and including tau.
    assert np.all(truncated_time[2:] > 10.0)
    assert np.all(truncated_time[2:] == np.nextafter(10.0, np.inf))
    np.testing.assert_array_equal(truncated_event[2:], [0, 0])


def test_paired_oof_bootstrap_uses_aligned_subject_predictions():
    """The paired OOF bootstrap succeeds on aligned cells with a finite standard error (ADR-017)."""
    # Exponential survival curves with subject-specific hazards on a four-point IBS
    # (integrated Brier score) grid; the second model adds 0.01 to every survival
    # probability, so the two models' predictions differ.
    training_time = np.arange(1.0, 151.0)
    training_event = np.tile([0, 1], 75)
    observed_time = np.arange(1.0, 101.0)
    observed_event = np.tile([0, 1], 50)
    grid = np.asarray([10.0, 20.0, 30.0, 40.0])
    base = np.exp(-np.outer(np.linspace(0.02, 0.08, len(observed_time)), grid))

    def cell(survival):
        """Return a cell with the shared subjects, outcomes and grid and the given ``survival``."""
        return {
            "metrics": {"ibs": 0.2},
            "predictions": {
                "subject_ids": [f"s{index}" for index in range(len(observed_time))],
                "training_time": training_time.tolist(),
                "training_event": training_event.tolist(),
                "observed_time": observed_time.tolist(),
                "observed_event": observed_event.tolist(),
                "ibs_grid": grid.tolist(),
                "survival_on_ibs_grid": survival.tolist(),
            },
        }

    # 20 replicates is the minimum the bootstrap accepts; all must be estimable.
    result = _paired_oof_ibs_bootstrap(
        [(cell(base), cell(np.clip(base + 0.01, 0.0, 1.0)))],
        n_bootstraps=20,
        seed=19,
    )
    assert result["n_successful"] == 20
    assert np.isfinite(result["bootstrap_standard_error"])


def test_inference_emits_bounded_benchmark_and_calibration_roster():
    """Inference gives three prior contrasts and nine prior-versus-comparator records (ADR-017)."""
    # One cohort, one repeat of two folds, all six models. Survival, calibration and
    # metric values shift slightly with the model index, so paired differences
    # between models are non-zero.
    training_time = np.arange(1.0, 151.0)
    training_event = np.tile([0, 1], 75)
    observed_time = np.arange(1.0, 101.0)
    observed_event = np.tile([0, 1], 50)
    grid = np.asarray([10.0, 20.0, 30.0, 40.0])
    cells = []
    for fold in (1, 2):
        subject_ids = [f"f{fold}-s{index}" for index in range(len(observed_time))]
        for model_index, model_key in enumerate(MODEL_KEYS):
            survival = np.exp(
                -np.outer(
                    np.linspace(0.02, 0.08, len(observed_time))
                    + model_index * 0.0002,
                    grid,
                )
            )
            calibration = []
            for horizon_index in range(3):
                calibration.append(
                    {
                        "summary": {
                            parameter: {
                                "estimate": float(
                                    model_index * 0.01 + horizon_index * 0.001
                                )
                            }
                            for parameter in (
                                "calibration_in_the_large",
                                "intercept",
                                "slope",
                            )
                        }
                    }
                )
            cells.append(
                {
                    "status": "complete",
                    "dataset": "demo",
                    "model_key": model_key,
                    "repeat": 1,
                    "fold": fold,
                    "total_seconds": float(model_index + 1),
                    "metrics": {
                        "ibs": 0.15 + model_index * 0.002 + fold * 0.0001,
                        "uno_c_index": 0.7 - model_index * 0.001,
                        "harrell_c_index": 0.69 - model_index * 0.001,
                        "mean_auc": 0.72 - model_index * 0.001,
                        "calibration": calibration,
                    },
                    "predictions": {
                        "subject_ids": subject_ids,
                        "training_time": training_time.tolist(),
                        "training_event": training_event.tolist(),
                        "observed_time": observed_time.tolist(),
                        "observed_event": observed_event.tolist(),
                        "ibs_grid": grid.tolist(),
                        "survival_on_ibs_grid": survival.tolist(),
                    },
                }
            )

    options = RunOptions(
        mode="confirmatory",
        datasets=("demo",),
        models=MODEL_KEYS,
        outer_splits=2,
        outer_repeats=1,
        fold_limit_per_dataset=None,
        bayes_draws=10,
        bayes_tune=10,
        bayes_chains=2,
        calibration_bootstraps=20,
        resume=False,
        output_root=Path("unused"),
    )
    result = _repeated_cv_inference(
        cells,
        options,
        {
            "validation": {"base_seed": 42},
            "inference": {"paired_oof_bootstraps": 20},
        },
    )

    # Three prior pairs in one cohort; 3 horizons x 3 calibration parameters = 9
    # calibration effects per contrast; 3 priors x 3 comparators = 9 secondary records.
    assert len(result["primary"]) == 3
    assert all(len(row["calibration_secondary_effects"]) == 9 for row in result["primary"])
    assert all("paired_oof_bootstrap" in row for row in result["primary"])
    assert len(result["secondary_benchmark_estimation"]) == 9
    assert all(
        len(row["calibration_effects"]) == 9
        for row in result["secondary_benchmark_estimation"]
    )
