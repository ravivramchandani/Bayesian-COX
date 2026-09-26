"""Shared labels, colours and deterministic figure metadata."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")


PROJECT_ROOT = Path(__file__).resolve().parents[2]

MODEL_LABELS = {
    "cox_ph": "Cox PH",
    "random_survival_forest": "Random survival forest",
    "deepsurv": "DeepSurv",
    "bayesian_normal": "Bayesian Cox (normal)",
    "bayesian_horseshoe": "Bayesian Cox (horseshoe)",
    "bayesian_spike_slab": "Bayesian Cox (spike-and-slab)",
}

METRIC_LABELS = {
    "ibs": "IPCW integrated Brier score",
    "uno_c_index": "Uno's C-index",
    "harrell_c_index": "Harrell's C-index",
    "mean_auc": "Mean time-dependent AUC",
}

COLORS = (
    "#0072B2",
    "#D55E00",
    "#009E73",
    "#CC79A7",
    "#E69F00",
    "#56B4E9",
    "#000000",
)

FIXED_PDF_DATE = datetime(2000, 1, 1, tzinfo=UTC)

PRIOR_DISPLAY_LABELS = {
    "bayesian_normal": "Normal",
    "bayesian_horseshoe": "Horseshoe",
    "bayesian_spike_slab": "Spike/slab",
    "Bayesian Cox (normal)": "Normal",
    "Bayesian Cox (horseshoe)": "Horseshoe",
    "Bayesian Cox (spike_slab)": "Spike/slab",
    "Bayesian Cox (spike-and-slab)": "Spike/slab",
}
