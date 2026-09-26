"""Subject resampling shared by paired inference and survival calibration."""

import numpy as np


def event_stratified_indices(event: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Sample subjects with replacement while preserving the event/censoring counts.

    Args:
        event: Binary event indicators, one per subject.
        rng: The caller's seeded generator; its state advances with each sample.

    Returns:
        Shuffled row indices, with the original number of subjects in each stratum.
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
