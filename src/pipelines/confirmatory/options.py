"""Model roster, run controls and seed derivation for the confirmatory study.

Every other module in this package uses these definitions: the six model keys
and their display labels, the options one run executes with, the exception
raised when a Bayesian fit fails its diagnostic gate, and the hash-based seed
that makes each cell reproducible on its own.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MODEL_KEYS = (
    "cox_ph",
    "random_survival_forest",
    "deepsurv",
    "bayesian_normal",
    "bayesian_horseshoe",
    "bayesian_spike_slab",
)

MODEL_LABELS = {
    "cox_ph": "Cox PH",
    "random_survival_forest": "Random Survival Forest",
    "deepsurv": "DeepSurv",
    "bayesian_normal": "Bayesian Cox (normal)",
    "bayesian_horseshoe": "Bayesian Cox (horseshoe)",
    "bayesian_spike_slab": "Bayesian Cox (spike_slab)",
}


class DiagnosticFailure(RuntimeError):
    """A Bayesian cell failed the frozen all-parameter diagnostic gate.

    ``attempts`` holds one record per fit attempt, including the diagnostics
    and posterior trace snapshot that explain each failure.
    """

    def __init__(self, attempts: list[dict[str, Any]]) -> None:
        super().__init__("Bayesian fit did not pass the confirmatory diagnostic gate")
        self.attempts = attempts


@dataclass(frozen=True)
class RunOptions:
    """Controls for one run, after any rehearsal-only reductions are applied.

    ``mode`` is ``"rehearsal"`` or ``"confirmatory"``. Only confirmatory mode
    verifies the protocol freeze, applies the Bayesian diagnostic gate and its
    refits, and labels cells as evidence. ``fold_limit_per_dataset`` keeps
    only the first outer folds of each cohort (``None`` keeps all of them).
    """

    mode: str
    datasets: tuple[str, ...]
    models: tuple[str, ...]
    outer_splits: int
    outer_repeats: int
    fold_limit_per_dataset: int | None
    bayes_draws: int
    bayes_tune: int
    bayes_chains: int
    calibration_bootstraps: int
    resume: bool
    output_root: Path


def deterministic_seed(base_seed: int, *parts: object) -> int:
    """Derive a stable seed in ``[0, 2**31 - 1)`` from a base seed and labels.

    The parts are joined as ``"base|part1|part2|..."`` and hashed with
    SHA-256, so the seed does not depend on Python's per-process string
    hashing. Every stochastic step of a cell gets its own labelled seed.
    """
    payload = "|".join([str(base_seed), *(str(part) for part in parts)])
    digest = hashlib.sha256(payload.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % (2**31 - 1)
