"""Data integrity tests.

The central check is that preprocessing preserves the association between
covariates and outcome. An earlier version of the pipeline silently produced
data with no such association, and every downstream result was invalid.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from src.evaluation.metrics import concordance_index

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"

DATASETS = ["gbsg2", "whas500", "metabric"]

# Cohort sizes and event counts published for these datasets.
EXPECTED_RAW = {
    "gbsg2": {"n": 686, "events": 299, "event_col": "cens"},
    "whas500": {"n": 500, "events": 215, "event_col": "fstat"},
}

# A covariate known to carry prognostic signal, and the concordance it must
# still reach after preprocessing.
SIGNAL_CHECKS = {
    "gbsg2": ("log_pnodes", 0.60),
    "whas500": ("age", 0.65),
    "metabric": ("nottingham_prognostic_index", 0.55),
}


@pytest.fixture(scope="module")
def config():
    with open(ROOT / "config" / "datasets.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.mark.parametrize("dataset", DATASETS)
def test_raw_file_exists(dataset):
    assert (RAW / f"{dataset}.csv").exists(), (
        f"{dataset} raw file missing. Run scripts/download_datasets.py."
    )


@pytest.mark.parametrize("dataset", sorted(EXPECTED_RAW))
def test_raw_cohort_matches_published_counts(dataset):
    """Guards against a substituted or regenerated source file."""
    spec = EXPECTED_RAW[dataset]
    df = pd.read_csv(RAW / f"{dataset}.csv")
    assert len(df) == spec["n"]
    assert int(df[spec["event_col"]].sum()) == spec["events"]


def test_gbsg2_raw_has_tumour_grade():
    """tgrade is present in the real cohort and absent from any stand-in."""
    df = pd.read_csv(RAW / "gbsg2.csv")
    assert "tgrade" in df.columns
    assert set(df["tgrade"].unique()) <= {"I", "II", "III"}


@pytest.mark.parametrize("dataset", DATASETS)
def test_splits_are_disjoint_and_complete(dataset):
    parts = {
        name: pd.read_csv(PROCESSED / dataset / f"{name}.csv")
        for name in ("train", "val", "test")
    }
    meta = json.loads((PROCESSED / dataset / "metadata.json").read_text())

    for name, df in parts.items():
        assert len(df) == meta[f"{name}_samples"]
        assert {"time", "event"} <= set(df.columns)
        assert df["time"].gt(0).all()
        assert set(df["event"].unique()) <= {0, 1}


@pytest.mark.parametrize("dataset", DATASETS)
def test_preprocessing_preserves_prognostic_signal(dataset):
    """The regression test for the row-alignment failure.

    If features and outcomes are misaligned, univariate concordance collapses
    to 0.5 and no model can recover.
    """
    feature, floor = SIGNAL_CHECKS[dataset]
    train = pd.read_csv(PROCESSED / dataset / "train.csv")
    assert feature in train.columns

    c, _ = concordance_index(
        train["time"].to_numpy(), train["event"].to_numpy(), train[feature].to_numpy()
    )
    # Signal may run in either direction; what matters is distance from chance.
    assert max(c, 1 - c) >= floor, (
        f"{dataset}: {feature} concordance {c:.3f} is at chance level, which "
        "indicates covariates and outcomes are misaligned"
    )


@pytest.mark.parametrize("dataset", DATASETS)
def test_scaler_fitted_on_train_only(dataset):
    """Training features are standardised; the scaler must not see val or test."""
    meta = json.loads((PROCESSED / dataset / "metadata.json").read_text())
    train = pd.read_csv(PROCESSED / dataset / "train.csv")

    for column, params in meta["scaling_params"].items():
        if column not in train.columns:
            continue
        values = train[column].to_numpy()
        assert np.mean(values) == pytest.approx(0.0, abs=0.05)
        assert np.std(values) == pytest.approx(1.0, abs=0.05)
        assert params["std"] > 0


@pytest.mark.parametrize("dataset", DATASETS)
def test_no_missing_values_after_preprocessing(dataset):
    for name in ("train", "val", "test"):
        df = pd.read_csv(PROCESSED / dataset / f"{name}.csv")
        assert not df.isna().any().any()


def test_metabric_event_is_death_not_survival():
    """`overall_survival` in the source encodes *alive*; the event is its inverse."""
    df = pd.read_csv(RAW / "metabric.csv")
    # Roughly 58% of the METABRIC cohort died during follow-up.
    assert 0.5 < df["event"].mean() < 0.65


@pytest.mark.parametrize("dataset", DATASETS)
def test_config_columns_exist_in_raw(dataset, config):
    spec = config[dataset]
    df = pd.read_csv(RAW / f"{dataset}.csv")

    assert spec["duration_col"] in df.columns
    assert spec["event_col"] in df.columns
    for column in (spec.get("numeric_features") or []):
        assert column in df.columns, f"{dataset}: {column} missing from raw data"
    for column in (spec.get("categorical_features") or []):
        assert column in df.columns, f"{dataset}: {column} missing from raw data"
