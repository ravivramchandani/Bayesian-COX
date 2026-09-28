"""Subject resampling shared by paired inference and survival calibration.

The calibration bootstrap (``src.evaluation.calibration``) and the paired
bootstrap (``src.statistics.bootstrap``) both draw their replicates here.
Resampling within event-status strata keeps each replicate's numbers of
events and censored subjects equal to the original sample's, while predictions and outcomes remain paired. This preserves event
counts but does not guarantee censoring support or estimable calibration fits.
"""

import numpy as np


def event_stratified_indices(event: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Sample subjects with replacement while preserving event-status counts.

    Args:
        event: Non-empty binary event indicators of shape (n_subjects,).
            Callers validate this array; the helper samples only labels 0 and 1.
        rng: The caller's seeded generator; each sample advances its state.

    Returns:
        Shuffled integer row indices of shape (n_subjects,), with the
        original number of subjects in each event/censoring stratum.
    """
    groups = []
    # Keep censored subjects before events, then shuffle the combined sample.
    # Both this order and the final shuffle determine the frozen random stream.
    for value in (0, 1):
        indices = np.flatnonzero(event == value)
        if len(indices):
            groups.append(rng.choice(indices, size=len(indices), replace=True))
    sampled = np.concatenate(groups)
    rng.shuffle(sampled)
    return sampled
