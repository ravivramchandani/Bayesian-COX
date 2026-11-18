"""Protect the distinction between count checks and fitted-survival checks."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/render_supervisor_checks.py"
SPEC = importlib.util.spec_from_file_location("supervisor_checks", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _rows() -> pd.DataFrame:
    base = {"dataset": "gbsg2", "model_key": "bayesian_normal", "repeat": 1, "fold": 1}
    records = []
    for interval in ["total", 1, 2, 3, 4, 5, 6]:
        records.append({**base, "check": MODULE.COUNT_CHECK, "interval": interval,
                        "observed": 10.0, "predicted": 10.1, "lower_95": 8.0,
                        "upper_95": 12.0, "observed_covered": True})
    for observed, predicted in [(0.8, 0.82), (0.6, 0.64), (0.4, 0.5)]:
        records.append({**base, "check": MODULE.SURVIVAL_CHECK, "interval": None,
                        "observed": observed, "predicted": predicted,
                        "lower_95": predicted - 0.05, "upper_95": predicted + 0.05,
                        "observed_covered": abs(predicted - observed) <= 0.05})
    return pd.DataFrame(records)


def test_distinct_denominators_and_survival_discrepancy() -> None:
    """One total, six interval counts and three horizons remain separate units."""
    summary = MODULE.summarise_predictive_checks(_rows()).iloc[0]
    assert summary.accepted_fits == 1
    assert summary.total_count_checks == 1
    assert summary.interval_count_checks == 6
    assert summary.fitted_survival_checks == 3
    assert summary.km_within_fitted_survival_interval == 2
    assert summary.mean_absolute_survival_difference == pytest.approx((0.02 + 0.04 + 0.10) / 3)


def test_missing_interval_is_not_silently_accepted() -> None:
    """Incomplete scientific output must fail before reporting coverage."""
    with pytest.raises(ValueError, match="incomplete stored predictive checks"):
        MODULE.summarise_predictive_checks(_rows().drop(index=3))


def test_inconsistent_saved_interval_flag_is_rejected() -> None:
    """A stale coverage flag cannot override the actual saved interval bounds."""
    rows = _rows()
    rows.loc[0, "observed_covered"] = False
    with pytest.raises(ValueError, match="stored interval flag disagrees"):
        MODULE.summarise_predictive_checks(rows)
