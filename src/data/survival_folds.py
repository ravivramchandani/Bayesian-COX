"""Construct deterministic, event/time-stratified survival validation folds.

``event_time_strata`` builds the labels used by ``repeated_survival_folds``.
The nested-validation pipelines reuse the resulting indices across model
families so comparisons use the same subjects in each training/validation pair.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold


@dataclass(frozen=True)
class SurvivalFold:
    """Describe one training/validation split by its row positions and seed.

    Args:
        repeat: One-based repeat number.
        fold: One-based fold number within the repeat.
        seed: Seed used to shuffle that repeat's stratified splits.
        train_indices: One-dimensional integer positions in the input arrays.
        validation_indices: Held-out positions in the same input arrays.
    """

    repeat: int
    fold: int
    seed: int
    train_indices: np.ndarray
    validation_indices: np.ndarray


def event_time_strata(
    times: np.ndarray,
    events: np.ndarray,
    *,
    n_splits: int,
    max_time_bins: int = 4,
) -> np.ndarray:
    """Combine event status with coarse within-status follow-up quantiles.

    Ranking with ``method='first'`` makes the rule deterministic when times
    are tied. A time subdivision is used only when every resulting stratum can
    contribute at least one observation to every fold; otherwise the affected
    event group is stratified by event status alone.

    Args:
        times: Positive finite follow-up times, shape ``(n_subjects,)``, in
            the cohort's own unit.
        events: Aligned binary event indicators: 1 for event, 0 for censoring.
        n_splits: Number of folds each stratum must support.
        max_time_bins: Maximum quantile subdivisions within each event group.

    Returns:
        String labels of shape ``(n_subjects,)`` in the input row order.

    Raises:
        ValueError: Arrays are not aligned and one-dimensional, times are
            invalid, converted event indicators are not binary, or either
            event group contains fewer subjects than ``n_splits``.
    """
    time = np.asarray(times, dtype=float)
    event = np.asarray(events, dtype=int)
    if time.ndim != 1 or event.ndim != 1 or len(time) != len(event):
        raise ValueError("times and events must be one-dimensional and aligned")
    if len(time) < n_splits:
        raise ValueError("n_splits cannot exceed the number of observations")
    if np.any(~np.isfinite(time)) or np.any(time <= 0):
        raise ValueError("survival times must be finite and strictly positive")
    if not set(np.unique(event)).issubset({0, 1}):
        raise ValueError("events must contain only 0 and 1")

    strata = np.empty(len(time), dtype=object)
    for status in (0, 1):
        indices = np.flatnonzero(event == status)
        if len(indices) < n_splits:
            raise ValueError(
                f"event group {status} has {len(indices)} observations, fewer "
                f"than n_splits={n_splits}"
            )
        n_bins = min(max_time_bins, len(indices) // n_splits)
        if n_bins < 2:
            strata[indices] = f"event_{status}"
            continue

        ranked = pd.Series(time[indices]).rank(method="first")
        bins = pd.qcut(ranked, q=n_bins, labels=False).to_numpy(dtype=int)
        counts = np.bincount(bins, minlength=n_bins)
        if np.min(counts) < n_splits:
            strata[indices] = f"event_{status}"
        else:
            strata[indices] = [f"event_{status}_time_{value}" for value in bins]
    return strata.astype(str)


def repeated_survival_folds(
    times: np.ndarray,
    events: np.ndarray,
    *,
    n_splits: int = 5,
    n_repeats: int = 5,
    base_seed: int = 42,
    max_time_bins: int = 4,
) -> list[SurvivalFold]:
    """Return paired, deterministic repeated folds for all model families.

    Each repeat shuffles the same event/time strata with seed
    ``base_seed + 1009 * repeat_index``. Reusing this list across models
    preserves the pairing required by the corrected comparison statistics.

    Args:
        times: Follow-up times of shape ``(n_subjects,)``, in cohort time units.
        events: Aligned binary indicators, 1 for event and 0 for censoring.
        n_splits: Number of validation folds per repeat; must be at least two.
        n_repeats: Number of repeated partitions to construct.
        base_seed: Seed for the first repeat; later seeds follow the rule above.
        max_time_bins: Maximum time subdivisions passed to ``event_time_strata``.

    Returns:
        A repeat-major list of ``SurvivalFold`` records containing positions
        relative to the supplied arrays, with one-based repeat/fold numbers.

    Raises:
        ValueError: Stratification inputs or the split count are invalid.
    """
    strata = event_time_strata(
        times,
        events,
        n_splits=n_splits,
        max_time_bins=max_time_bins,
    )
    dummy = np.zeros(len(strata), dtype=np.int8)
    folds: list[SurvivalFold] = []
    for repeat in range(n_repeats):
        seed = int(base_seed + 1009 * repeat)
        splitter = StratifiedKFold(
            n_splits=n_splits,
            shuffle=True,
            random_state=seed,
        )
        for fold, (train, validation) in enumerate(
            splitter.split(dummy, strata), start=1
        ):
            folds.append(
                SurvivalFold(
                    repeat=repeat + 1,
                    fold=fold,
                    seed=seed,
                    train_indices=train.astype(int),
                    validation_indices=validation.astype(int),
                )
            )
    return folds
