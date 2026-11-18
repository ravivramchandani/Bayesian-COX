"""Keep primary-metric selection and immutable-input checking explicit."""

import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "examiner_presentation", Path(__file__).parents[1] / "scripts/render_examiner_presentation.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_changed_input_is_rejected(tmp_path):
    """A valid manifest cannot silently bless a subsequently modified CSV."""
    source = tmp_path / "metrics.csv"
    source.write_text("value\n0.5\n")
    manifest = {"outputs": {"metrics.csv": {"sha256": MODULE.sha256(source)}}}
    (tmp_path / "provenance.json").write_text(json.dumps(manifest))
    assert MODULE.load_verified(tmp_path, "metrics.csv")[0]["value"] == "0.5"
    source.write_text("value\n0.6\n")
    with pytest.raises(ValueError, match="hash mismatch"):
        MODULE.load_verified(tmp_path, "metrics.csv")


def test_duplicate_or_missing_model_is_rejected():
    """Partial accepted-fold counts are allowed, omitted model arms are not."""
    rows = [{"dataset": "gbsg2", "model_key": key} for key in MODULE.MODELS]
    assert len(MODULE.select_rows(list(reversed(rows)), "gbsg2")) == 6
    with pytest.raises(ValueError, match="Incomplete or duplicate"):
        MODULE.select_rows(rows[:-1], "gbsg2")
    with pytest.raises(ValueError, match="Incomplete or duplicate"):
        MODULE.select_rows(rows + [rows[0]], "gbsg2")
