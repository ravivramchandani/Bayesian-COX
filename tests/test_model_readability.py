"""Analytic survival checks and compatibility of the readable model modules."""

import arviz as az
import numpy as np
import pandas as pd

from src.models.bayesian.model import BayesianCoxModel
from src.models.bayesian.piecewise import _poisson_rows
from src.statistics.resampling import event_stratified_indices


def test_piecewise_rows_preserve_exposure_and_events_at_interval_boundaries():
    rows = _poisson_rows(
        np.asarray([[10.0], [20.0], [30.0]]),
        np.asarray([1.0, 2.0, 0.5]),
        np.asarray([1, 0, 1]),
        np.asarray([0.0, 1.0, 3.0]),
    )
    np.testing.assert_array_equal(rows.covariates[:, 0], [10.0, 20.0, 20.0, 30.0])
    np.testing.assert_array_equal(rows.exposures, [1.0, 1.0, 1.0, 0.5])
    np.testing.assert_array_equal(rows.interval_index, [0, 0, 1, 0])
    np.testing.assert_array_equal(rows.events, [1.0, 0.0, 0.0, 1.0])
    assert rows.exposures.sum() == 3.5
    assert rows.events.sum() == 2.0


def test_bayesian_predictions_average_survival_and_extend_last_interval():
    model = BayesianCoxModel()
    model.feature_names = ["age"]
    model.cutoffs = np.asarray([0.0, 1.0, 3.0])
    model.cutoffs_scaled = model.cutoffs.copy()
    model.beta_samples = np.asarray([[0.0], [0.0]])
    model.lambda_samples = np.asarray([[2.0, 2.0], [4.0, 4.0]])
    times = np.asarray([0.0, 0.5, 2.0, 4.0])
    predictions = model.predict_survival(pd.DataFrame({"age": [0.0]}), times)
    expected = np.clip((np.exp(-2.0 * times) + np.exp(-4.0 * times)) / 2.0, 1e-6, 1.0)
    np.testing.assert_allclose(predictions[0], expected, rtol=0.0, atol=1e-15)


def test_legacy_mcmc_table_retains_feature_names():
    model = BayesianCoxModel()
    assert model.get_mcmc_diagnostics().empty
    model.feature_names = ["age", "size"]
    model.idata = az.from_dict(
        posterior={"beta": np.random.default_rng(42).normal(size=(2, 200, 2))}
    )
    summary = model.get_mcmc_diagnostics()
    assert summary["parameter"].tolist() == ["beta[0]", "beta[1]"]
    assert summary["feature"].tolist() == ["age", "size"]
    assert {"r_hat", "ess_bulk", "ess_tail"} <= set(summary.columns)


def test_event_stratified_indices_preserve_counts_and_frozen_rng_stream():
    event = np.asarray([0, 1, 0, 1, 1, 0])
    integer_rng = np.random.default_rng(42)
    boolean_rng = np.random.default_rng(42)
    for _ in range(3):
        indices = event_stratified_indices(event, integer_rng)
        boolean_indices = event_stratified_indices(event.astype(bool), boolean_rng)
        np.testing.assert_array_equal(indices, boolean_indices)
        np.testing.assert_array_equal(np.bincount(event[indices]), [3, 3])
    assert integer_rng.bit_generator.state == boolean_rng.bit_generator.state
