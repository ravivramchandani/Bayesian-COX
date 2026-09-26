"""Expand survival follow-up into the piecewise-Poisson likelihood rows.

The Bayesian fit creates these rows in subject-major order before adding the
likelihood to its PyMC model. Positive exposures, event counts and row order
match the stored confirmatory cells.
"""

from typing import NamedTuple

import numpy as np
import pymc as pm


class _PoissonRows(NamedTuple):
    """Subject-interval rows of the Poisson likelihood with positive exposure."""

    covariates: np.ndarray
    exposures: np.ndarray
    log_exposure: np.ndarray
    interval_index: np.ndarray
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
    observed event time. Rows with zero exposure are dropped. Rows are kept
    in subject-major order.
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
    """Add Poisson counts ``obs`` with log mean log(exposure) + log(lambda_m) + x beta."""
    linear_predictor = pm.math.dot(rows.covariates, beta)
    interval_log_hazard = log_lambda[rows.interval_index]
    poisson_mean = pm.math.exp(rows.log_exposure + interval_log_hazard + linear_predictor)
    pm.Poisson("obs", mu=poisson_mean, observed=rows.events)
