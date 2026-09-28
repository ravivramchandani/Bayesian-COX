"""Expand survival follow-up into the piecewise-Poisson likelihood rows.

With a hazard that is constant within each baseline interval, the
right-censored survival likelihood equals, up to a factor that does not
depend on the parameters, the likelihood of independent Poisson counts: one
count per subject and interval, equal to 1 if the subject's event falls in
that interval and 0 otherwise, with mean ``exposure * lambda_m * exp(x beta)``.
The exposure is the time the subject was at risk inside the interval.

``BayesianCoxModel.fit`` creates these rows in subject-major order, on the
scaled time axis, before adding the likelihood to its PyMC model. Only positive
exposures are retained, with covariates and event counts in matching order.
"""

from typing import NamedTuple

import numpy as np
import pymc as pm


class _PoissonRows(NamedTuple):
    """Subject-interval rows of the Poisson likelihood with positive exposure."""

    # Covariates of each row's subject, shape (n_rows, n_features).
    covariates: np.ndarray
    # Time at risk inside the interval, in scaled time units, shape (n_rows,).
    exposures: np.ndarray
    # log(exposures), the Poisson offset.
    log_exposure: np.ndarray
    # Zero-based baseline interval of each row.
    interval_index: np.ndarray
    # 1.0 when the subject's observed event falls in this interval, else 0.0.
    events: np.ndarray


def _poisson_rows(
    X_mat: np.ndarray,
    y_time_scaled: np.ndarray,
    y_event: np.ndarray,
    cutoffs_scaled: np.ndarray,
) -> _PoissonRows:
    """Expand subjects into subject-interval exposures and event counts.

    Subject i's exposure in interval m is ``max(0, min(t_i, end_m) -
    start_m)``, and its count is 1 only in the interval that contains an
    observed event time. Intervals are open on the left and closed on the
    right, so an event exactly at a cut point belongs to the interval that
    ends there. Rows with zero exposure are dropped: they add nothing to the
    likelihood and their log exposure is undefined. Rows are kept in
    subject-major order.

    Args:
        X_mat: Covariates, shape (n_subjects, n_features).
        y_time_scaled: Follow-up times divided by the model's time scale.
        y_event: Event indicators, 1 for an event and 0 for censoring.
        cutoffs_scaled: Increasing cut points on the scaled axis, starting at 0.

    Returns:
        Aligned covariates, exposures, log exposures, interval indices
        and event counts for the retained subject-interval rows.
    """
    starts = cutoffs_scaled[:-1]
    ends = cutoffs_scaled[1:]
    times = y_time_scaled[:, None]
    events = y_event[:, None]

    exposures = np.clip(np.minimum(times, ends) - starts, 0, None)
    events_matrix = ((events == 1) & (times > starts) & (times <= ends)).astype(float)

    has_exposure = exposures > 0
    subject_index, interval_index = np.where(has_exposure)
    row_exposures = exposures[has_exposure]
    return _PoissonRows(
        covariates=X_mat[subject_index],
        exposures=row_exposures,
        log_exposure=np.log(row_exposures),
        interval_index=interval_index,
        events=events_matrix[has_exposure],
    )


def _add_poisson_likelihood(rows: _PoissonRows, beta, log_lambda) -> None:
    """Add Poisson counts ``obs`` with log mean log(exposure) + log(lambda_m) + x beta.

    Args:
        rows: Likelihood rows from :func:`_poisson_rows`.
        beta: PyMC coefficient vector, shape (n_features,).
        log_lambda: PyMC baseline log hazards, shape (n_intervals,).
    """
    linear_predictor = pm.math.dot(rows.covariates, beta)
    interval_log_hazard = log_lambda[rows.interval_index]
    poisson_mean = pm.math.exp(rows.log_exposure + interval_log_hazard + linear_predictor)
    pm.Poisson("obs", mu=poisson_mean, observed=rows.events)
