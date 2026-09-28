"""Model roster, run controls and seed derivation for the confirmatory study.

``scripts/run_confirmatory.py`` builds a :class:`RunOptions`. The fitting,
cell and runner stages use the definitions here: the six model keys and
their display labels, including Cox proportional hazards (PH), the diagnostic-
failure exception, and the hash-based seed derivation. Reusing labelled seeds
is one part of reproducing a cell in its recorded environment.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Internal model keys; also the default fitting order within each outer fold.
MODEL_KEYS = (
    "cox_ph",
    "random_survival_forest",
    "deepsurv",
    "bayesian_normal",
    "bayesian_horseshoe",
    "bayesian_spike_slab",
)

# Display labels stored in cells, tables and inference records.
MODEL_LABELS = {
    "cox_ph": "Cox PH",
    "random_survival_forest": "Random Survival Forest",
    "deepsurv": "DeepSurv",
    "bayesian_normal": "Bayesian Cox (normal)",
    "bayesian_horseshoe": "Bayesian Cox (horseshoe)",
    "bayesian_spike_slab": "Bayesian Cox (spike_slab)",
}


class DiagnosticFailure(RuntimeError):
    """Carry a Bayesian diagnostic-gate failure and the caller's attempt records.

    The confirmatory fitter raises this after its permitted diagnostic remedies
    have failed, and sensitivity pipelines reuse it. The exception itself stores
    ``attempts`` unchanged; their contents depend on the caller. A cell wrapper
    can retain these records with status ``"failed_diagnostics"``.

    Args:
        attempts: Completed fit-attempt records supplied by the caller.
    """

    def __init__(self, attempts: list[dict[str, Any]]) -> None:
        """Store the supplied attempts with the fixed diagnostic-failure message."""
        super().__init__("Bayesian fit did not pass the confirmatory diagnostic gate")
        self.attempts = attempts


@dataclass(frozen=True)
class RunOptions:
    """Controls for one run, after any rehearsal-only reductions are applied.

    ``mode`` is ``"rehearsal"`` or ``"confirmatory"``. Only confirmatory mode
    verifies the protocol freeze, applies the Bayesian diagnostic gate and its
    refits, and labels cells as evidence. Every field except ``resume`` and
    ``output_root`` enters the run-configuration hash that names the run
    directory.

    Args:
        mode: ``"rehearsal"`` or ``"confirmatory"``.
        datasets: Cohort keys from ``config/datasets.yaml``, in run order.
        models: Keys from :data:`MODEL_KEYS`, in fitting order.
        outer_splits: Outer folds per repeat.
        outer_repeats: Outer cross-validation repeats.
        fold_limit_per_dataset: Keep only the first this-many outer folds of
            each cohort, in repeat-then-fold order; ``None`` keeps all.
        bayes_draws: Posterior draws per chain after tuning.
        bayes_tune: NUTS (No-U-Turn Sampler) tuning steps per chain before
            any refit multiplier.
        bayes_chains: Independent Markov chains per Bayesian fit.
        calibration_bootstraps: Bootstrap replicates for each calibration
            interval.
        resume: Continue or verify an existing run directory instead of
            refusing to reuse it.
        output_root: Parent directory of the run directory.
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
    hashing. Every stochastic step of a cell gets its own labelled seed, so a
    cell can reuse its seeds when fitted alone or in another order. Reproducing
    the numerical draws also requires the same implementation and runtime.

    Args:
        base_seed: The protocol's ``validation.base_seed`` or a seed already
            derived from it.
        *parts: Labels that identify the step, such as cohort, repeat, fold
            and model; each is converted with ``str``.

    Returns:
        The first four bytes of the digest, big-endian, modulo ``2**31 - 1``.
    """
    payload = "|".join([str(base_seed), *(str(part) for part in parts)])
    digest = hashlib.sha256(payload.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % (2**31 - 1)
