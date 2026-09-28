"""Shared labels, colours and deterministic figure metadata.

Used by every rendering module and by ``scripts/render_horseshoe_sensitivity.py``."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import matplotlib

# The non-interactive backend lets figures render without a display.
matplotlib.use("Agg")


PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Display names for stored model keys; PH means proportional hazards.
MODEL_LABELS = {
    "cox_ph": "Cox PH",
    "random_survival_forest": "Random survival forest",
    "deepsurv": "DeepSurv",
    "bayesian_normal": "Bayesian Cox (normal)",
    "bayesian_horseshoe": "Bayesian Cox (horseshoe)",
    "bayesian_spike_slab": "Bayesian Cox (spike-and-slab)",
}

# The per-cell metrics that are tabulated and plotted, in display order. IPCW
# is inverse probability of censoring weighting; AUC is the area under the
# time-dependent receiver operating characteristic (ROC) curve.
METRIC_LABELS = {
    "ibs": "IPCW integrated Brier score",
    "uno_c_index": "Uno's C-index",
    "harrell_c_index": "Harrell's C-index",
    "mean_auc": "Mean time-dependent AUC",
}

# Okabe–Ito colour-blind-safe palette.
COLORS = (
    "#0072B2",
    "#D55E00",
    "#009E73",
    "#CC79A7",
    "#E69F00",
    "#56B4E9",
    "#000000",
)

# A fixed creation and modification date keeps PDF bytes identical between
# renders, so output hashes are reproducible.
FIXED_PDF_DATE = datetime(2000, 1, 1, tzinfo=UTC)

# Short prior names for contrast labels. Keys cover the model keys, the labels
# above and the labels written into inference.json by the confirmatory
# pipeline, which spell the last prior "spike_slab".
PRIOR_DISPLAY_LABELS = {
    "bayesian_normal": "Normal",
    "bayesian_horseshoe": "Horseshoe",
    "bayesian_spike_slab": "Spike/slab",
    "Bayesian Cox (normal)": "Normal",
    "Bayesian Cox (horseshoe)": "Horseshoe",
    "Bayesian Cox (spike_slab)": "Spike/slab",
    "Bayesian Cox (spike-and-slab)": "Spike/slab",
}
