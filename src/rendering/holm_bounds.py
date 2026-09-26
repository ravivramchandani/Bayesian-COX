"""Render ADR-033's post-hoc bounds without supplying missing hypothesis tests."""

from __future__ import annotations

from typing import Any

import pandas as pd

from .constants import PRIOR_DISPLAY_LABELS
from .metrics import _paired_ibs_rows
from .outputs import OutputRegistry, _write_table
from .verification import FrozenRun, _source


def incomplete_holm_bounds(primary: list[dict[str, Any]], *, alpha: float = 0.05) -> pd.DataFrame:
    """Bound available Holm rejections over every possible missing p-value.

    The best case places all missing hypotheses first with p-values zero;
    the worst case places them last with p-values one. These are hypothetical
    mathematical bounds, not observed or imputed tests.
    """
    family_size = len(primary)
    available = sorted(
        (row for row in primary if isinstance(row.get("ibs"), dict)),
        key=lambda row: float(row["ibs"]["p_value"]),
    )
    missing = family_size - len(available)
    rows = []
    best_previous = worst_previous = 0.0
    for rank, contrast in enumerate(available):
        p_value = float(contrast["ibs"]["p_value"])
        if not 0 <= p_value <= 1:
            raise ValueError("Holm bound requires p-values in [0, 1]")
        best_previous = min(1.0, max(best_previous, (len(available) - rank) * p_value))
        worst_previous = min(1.0, max(worst_previous, (family_size - rank) * p_value))
        rows.append(
            {
                "dataset": contrast["dataset"],
                "model_a": contrast["model_a"],
                "model_b": contrast["model_b"],
                "p_value": p_value,
                "family_size": family_size,
                "missing_hypotheses": missing,
                "best_case_adjusted_p_bound": best_previous,
                "worst_case_adjusted_p_bound": worst_previous,
                "rejection_possible": best_previous <= alpha,
                "rejection_guaranteed": worst_previous <= alpha,
                "evidence_status": "posthoc_bound_on_incomplete_family",
            }
        )
    return pd.DataFrame(rows)


def render_holm_bounds(run: FrozenRun, registry: OutputRegistry) -> None:
    """Write the separately labelled bound and a compact thesis results table."""
    sources = [_source(run, "inference.json", ["primary", "holm_family_complete"])]
    if not run.inference.get("holm_family_complete", False):
        bounds = incomplete_holm_bounds(run.inference["primary"])
        _write_table(
            bounds,
            registry.output_dir / "tables/posthoc_incomplete_holm_bounds",
            registry,
            sources=sources,
            note="ADR-033 post-hoc mathematical bound; missing p-values are not estimated and confirmatory Holm results remain incomplete",
        )
    aliases = PRIOR_DISPLAY_LABELS
    table = _paired_ibs_rows(run)
    compact = []
    for row in table.itertuples(index=False):
        available = pd.notna(row.mean_ibs_difference)
        compact.append(
            {
                "Cohort": row.dataset.upper(),
                "Contrast": aliases.get(row.model_a, row.model_a)
                + " - "
                + aliases.get(row.model_b, row.model_b),
                "Paired folds": row.n_paired_folds,
                "Delta IBS": f"{row.mean_ibs_difference:+.6f}" if available else "Unavailable",
                "95% interval": f"[{row.confidence_lower:+.6f}, {row.confidence_upper:+.6f}]"
                if available
                else "--",
                "p": f"{row.p_value:.3f}" if available else "--",
            }
        )
    _write_table(
        pd.DataFrame(compact),
        registry.output_dir / "tables/primary_contrasts_thesis",
        registry,
        sources=sources,
        note="All primary contrasts, with unavailable estimates retained; delta IBS is model A minus model B; no complete-family superiority or equivalence claim",
    )
