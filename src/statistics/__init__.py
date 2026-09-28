"""Statistical inference for paired model comparisons.

The confirmatory analysis uses ``repeated_cv`` for the Nadeau-Bengio (NB)
corrected paired intervals and tests, ``hypothesis_tests.holm_adjust`` for
Holm's multiplicity adjustment, and ``resampling`` for the event-stratified
subject resampling shared with calibration. ``bootstrap``,
``confidence_intervals``, ``permutation`` and the rank tests in
``hypothesis_tests`` are general or legacy tools.
"""

from .bootstrap import (
    BootstrapResampler,
    PairedBootstrapResult,
    paired_event_stratified_bootstrap,
)
from .confidence_intervals import ConfidenceIntervalCalculator
from .hypothesis_tests import SurvivalHypothesisTests, holm_adjust
from .permutation import PermutationTest
from .repeated_cv import NadeauBengioResult, nadeau_bengio_paired_effect

__all__ = [
    "BootstrapResampler",
    "ConfidenceIntervalCalculator",
    "NadeauBengioResult",
    "PairedBootstrapResult",
    "PermutationTest",
    "SurvivalHypothesisTests",
    "holm_adjust",
    "nadeau_bengio_paired_effect",
    "paired_event_stratified_bootstrap",
]
