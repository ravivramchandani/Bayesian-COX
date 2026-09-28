"""Data integrity tests for the raw cohorts, their manifest and fold preprocessing.

The central check is that preprocessing preserves the association between
covariates and outcome. An earlier version of the pipeline silently produced
data with no such association, and every downstream result was invalid.

Covers the files retrieved by ``scripts/download_datasets.py`` (``data/raw/``
and ``data/manifest.yaml``), the schemas in ``config/datasets.yaml``, and
``src/data/cohorts.py``, ``survival_folds.py`` and ``fold_preprocessing.py``.
Verifies INV-001 (published counts, tumour grade) and INV-002 (prognostic
signal survives preprocessing).
"""

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from src.data.fold_preprocessing import FoldFeaturePreprocessor
from src.evaluation.metrics import concordance_index
from tests.cohort_fixtures import prepare_real_fold

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
MANIFEST_PATH = ROOT / "data" / "manifest.yaml"

DATASETS = ["gbsg2", "whas500", "metabric"]

# Cohort sizes and event counts published for these datasets.
EXPECTED_RAW = {
    "gbsg2": {"n": 686, "events": 299, "event_col": "cens"},
    "whas500": {"n": 500, "events": 215, "event_col": "fstat"},
    "metabric": {"n": 1980, "events": 1144, "event_col": "event"},
}

# A covariate known to carry prognostic signal, and the concordance it must
# still reach after preprocessing (the INV-002 floors).
SIGNAL_CHECKS = {
    "gbsg2": ("pnodes", 0.60),
    "whas500": ("age", 0.65),
    "metabric": ("nottingham_prognostic_index", 0.55),
}


def primary_feature_columns(dataset_config):
    """Read the primary declaration in the same column order as its preprocessor."""
    return FoldFeaturePreprocessor(dataset_config["primary_features"]).required_source_columns


@pytest.fixture(scope="module")
def config():
    """Parsed ``config/datasets.yaml``, shared by the module's tests."""
    with open(ROOT / "config" / "datasets.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def manifest():
    """Parsed ``data/manifest.yaml``, shared by the module's tests."""
    with MANIFEST_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.mark.parametrize("dataset", DATASETS)
def test_raw_file_exists(dataset):
    """Each cohort's raw CSV is present in ``data/raw``."""
    assert (RAW / f"{dataset}.csv").exists(), (
        f"{dataset} raw file missing. Run scripts/download_datasets.py."
    )


@pytest.mark.parametrize("dataset", DATASETS)
def test_raw_cohort_matches_published_counts(dataset):
    """Each raw cohort has its published row and event counts, so it is not a substitute (INV-001)."""
    spec = EXPECTED_RAW[dataset]
    df = pd.read_csv(RAW / f"{dataset}.csv")
    assert len(df) == spec["n"]
    assert int(df[spec["event_col"]].sum()) == spec["events"]


def test_gbsg2_raw_has_tumour_grade():
    """The GBSG2 raw file has a tgrade column whose levels are only I, II and III (INV-001)."""
    df = pd.read_csv(RAW / "gbsg2.csv")
    assert "tgrade" in df.columns
    assert set(df["tgrade"].unique()) <= {"I", "II", "III"}


def test_metabric_ids_and_positive_follow_up_are_exact():
    """METABRIC has 1,980 unique patient IDs, positive durations and a 0/1 event indicator."""
    df = pd.read_csv(RAW / "metabric.csv")
    assert df["patient_id"].is_unique
    assert df["patient_id"].nunique() == 1980
    assert df["duration"].gt(0).all()
    assert set(df["event"].unique()) == {0, 1}


@pytest.mark.parametrize("dataset", DATASETS)
def test_splits_are_disjoint_and_complete(dataset):
    """Within one repeat each fold splits all subjects, and each subject is validated once."""
    prepared = prepare_real_fold(dataset)
    all_ids = set(prepared.subject_ids)
    held_out = []
    for fold in prepared.folds:
        train_ids = set(prepared.subject_ids[fold.train_indices])
        validation_ids = set(prepared.subject_ids[fold.validation_indices])
        assert train_ids.isdisjoint(validation_ids)
        assert train_ids | validation_ids == all_ids
        held_out.extend(prepared.subject_ids[fold.validation_indices])
    assert len(held_out) == len(all_ids)
    assert set(held_out) == all_ids


@pytest.mark.parametrize("dataset", DATASETS)
def test_fold_preprocessing_preserves_every_eligible_subject(dataset):
    """Preprocessing drops no subject and keeps each fold's source row index and order."""
    prepared = prepare_real_fold(dataset)
    assert len(prepared.train) + len(prepared.validation) == EXPECTED_RAW[dataset]["n"]
    np.testing.assert_array_equal(
        prepared.train.index, prepared.raw.iloc[prepared.fold.train_indices].index
    )
    np.testing.assert_array_equal(
        prepared.validation.index, prepared.raw.iloc[prepared.fold.validation_indices].index
    )


def test_absent_validation_category_is_encoded_as_indexed_zeros():
    """A training level missing from validation still yields an all-zero indicator column."""
    # Level "a" sorts first and becomes the reference, so "group=b" is the only
    # indicator; the validation rows contain no "b" and carry a non-default index.
    processor = FoldFeaturePreprocessor({"numeric": ["value"], "categorical": ["group"]})
    train = pd.DataFrame({"value": [1.0, 2.0, 3.0], "group": ["a", "b", "a"]})
    validation = pd.DataFrame({"value": [4.0, 5.0], "group": ["a", "a"]}, index=[10, 11])
    processor.fit(train)
    transformed = processor.transform(validation)
    assert "group=b" in processor.feature_names
    assert transformed["group=b"].eq(0.0).all()
    assert transformed.index.equals(validation.index)


@pytest.mark.parametrize("dataset", DATASETS)
def test_preprocessing_preserves_prognostic_signal(dataset):
    """Preprocessing keeps a primary covariate's concordance unchanged and not below its floor (INV-002)."""
    prepared = prepare_real_fold(dataset)
    feature, floor = SIGNAL_CHECKS[dataset]
    indices = prepared.fold.train_indices
    # The reference applies the same training-median imputation to the raw
    # values; standardisation is a positive affine map, so ranks and hence the
    # concordance must be identical.
    raw_values = pd.to_numeric(prepared.raw.iloc[indices][feature])
    imputed = raw_values.fillna(raw_values.median()).to_numpy()
    before, _ = concordance_index(prepared.time[indices], prepared.event[indices], imputed)
    after, _ = concordance_index(
        prepared.time[indices], prepared.event[indices], prepared.train[feature].to_numpy()
    )
    assert after == before
    # The covariate is used directly as a risk score, so a protective covariate
    # gives a concordance below 0.5; the floor applies to either direction.
    assert max(after, 1 - after) >= floor


@pytest.mark.parametrize("dataset", DATASETS)
def test_scaler_fitted_on_train_only(dataset):
    """Transforming validation rows leaves the fitted state unchanged; scaled training columns are standardised."""
    prepared = prepare_real_fold(dataset)
    state_before = prepared.processor.metadata()
    altered = prepared.raw.iloc[prepared.fold.validation_indices].copy()
    for column in prepared.processor.numeric:
        altered[column] = 1e12
    prepared.processor.transform(altered)
    assert prepared.processor.metadata() == state_before
    for column in prepared.processor.scaling:
        values = prepared.train[column].to_numpy()
        assert np.mean(values) == pytest.approx(0.0, abs=1e-12)
        # A constant training column keeps scale 1 and so has standard
        # deviation 0 after centring; every other column has standard deviation 1.
        assert min(abs(np.std(values)), abs(np.std(values) - 1.0)) < 1e-12


@pytest.mark.parametrize("dataset", DATASETS)
def test_no_missing_values_after_preprocessing(dataset):
    """Preprocessed training and validation features are all finite."""
    prepared = prepare_real_fold(dataset)
    for frame in (prepared.train, prepared.validation):
        assert np.isfinite(frame.to_numpy()).all()


def test_metabric_event_is_death_not_survival():
    """The cBioPortal DECEASED status is encoded as the event."""
    df = pd.read_csv(RAW / "metabric.csv")
    assert int(df["event"].sum()) == 1144


@pytest.mark.parametrize("dataset", DATASETS)
def test_config_columns_exist_in_raw(dataset, config):
    """Outcome and feature-set columns exist in the raw file; engineered features use declared sources."""
    spec = config[dataset]
    df = pd.read_csv(RAW / f"{dataset}.csv")

    assert spec["duration_col"] in df.columns
    assert spec["event_col"] in df.columns
    feature_sets = [spec["primary_features"], *spec["sensitivity_feature_sets"].values()]
    for feature_set in feature_sets:
        columns = [
            *(feature_set.get("numeric") or []),
            *(feature_set.get("categorical") or []),
            *(feature_set.get("ordinal") or {}).keys(),
        ]
        for column in columns:
            assert column in df.columns, f"{dataset}: {column} missing from raw data"
        for engineered in feature_set.get("engineered") or []:
            assert set(engineered["source_features"]) <= set(columns)


@pytest.mark.parametrize("dataset", DATASETS)
def test_primary_selection_excludes_every_undeclared_column(dataset, config):
    """The primary preprocessor reads only declared columns, never outcomes or subject IDs."""
    prepared = prepare_real_fold(dataset)
    spec = config[dataset]
    declared = set(primary_feature_columns(spec))
    assert set(prepared.processor.required_source_columns) == declared
    assert set(prepared.processor.feature_groups.values()) <= declared
    assert {spec["duration_col"], spec["event_col"]}.isdisjoint(declared)
    if spec.get("id_col"):
        assert spec["id_col"] not in declared
        np.testing.assert_array_equal(
            prepared.subject_ids, prepared.raw[spec["id_col"]].astype(str)
        )


@pytest.mark.parametrize("dataset", DATASETS)
def test_fold_outputs_contain_only_primary_declarations(dataset, config):
    """Primary outputs omit excluded columns and sensitivity-only engineered features (ADR-015, ADR-021)."""
    prepared = prepare_real_fold(dataset)
    spec = config[dataset]
    features = set(prepared.train)
    groups = set(prepared.processor.feature_groups.values())
    for exclusion in spec["primary_exclusions"]:
        column = exclusion["column"]
        assert column not in groups
        assert column not in features
        # Categorical columns appear only as "<column>=<level>" indicators.
        assert not any(name.startswith(f"{column}=") for name in features)
    primary_engineered = {item["name"] for item in spec["primary_features"].get("engineered") or []}
    sensitivity_engineered = {
        item["name"]
        for feature_set in spec["sensitivity_feature_sets"].values()
        for item in feature_set.get("engineered") or []
    }
    assert not (sensitivity_engineered - primary_engineered) & features


def test_feature_sets_resolve_composite_and_timing_conflicts(config):
    """Primary sets exclude timing-uncertain WHAS500 fields and prognostic-index parts (ADR-015, ADR-021)."""
    # WHAS500: length of stay and complications of uncertain onset are only in
    # the published_full sensitivity. METABRIC: the Nottingham prognostic index
    # (NPI) is primary, and its components, stage and treatments are not.
    whas_primary = set(primary_feature_columns(config["whas500"]))
    assert {"los", "afb", "sho", "chf", "av3"}.isdisjoint(whas_primary)
    whas_full = config["whas500"]["sensitivity_feature_sets"]["published_full"]
    whas_full_columns = set(whas_full["numeric"] + whas_full["categorical"])
    assert {"los", "afb", "sho", "chf", "av3"} <= whas_full_columns

    metabric_primary = set(primary_feature_columns(config["metabric"]))
    assert "nottingham_prognostic_index" in metabric_primary
    assert {
        "tumor_size",
        "lymph_nodes_examined_positive",
        "neoplasm_histologic_grade",
        "tumor_stage",
        "type_of_breast_surgery",
        "chemotherapy",
        "hormone_therapy",
        "radio_therapy",
    }.isdisjoint(metabric_primary)

    components = config["metabric"]["sensitivity_feature_sets"]["npi_components"]
    assert "nottingham_prognostic_index" not in components["numeric"]
    assert {
        "tumor_size",
        "lymph_nodes_examined_positive",
        "neoplasm_histologic_grade",
    } <= set(components["numeric"])


@pytest.mark.parametrize("dataset", DATASETS)
def test_config_backed_loaders_match_primary_schema(dataset, config):
    """The loader returns aligned rows with published counts and the primary column order."""
    prepared = prepare_real_fold(dataset)
    assert (
        len(prepared.raw) == len(prepared.time) == len(prepared.event) == EXPECTED_RAW[dataset]["n"]
    )
    assert prepared.event.sum() == EXPECTED_RAW[dataset]["events"]
    assert prepared.processor.required_source_columns == primary_feature_columns(config[dataset])


@pytest.mark.parametrize("dataset", DATASETS)
def test_manifest_matches_derived_files(dataset, manifest):
    """Each raw file matches the SHA-256 hash, record count and event count in the manifest."""
    entry = manifest["datasets"][dataset]
    path = ROOT / entry["derivation"]["raw_file"]
    observed = hashlib.sha256(path.read_bytes()).hexdigest()
    assert observed == entry["derivation"]["sha256"]
    assert entry["cohort"]["analysis_records"] == EXPECTED_RAW[dataset]["n"]
    assert entry["cohort"]["events"] == EXPECTED_RAW[dataset]["events"]


def test_metabric_manifest_missingness_is_exact(manifest):
    """The manifest's METABRIC missing-value counts and proportions match the raw file."""
    df = pd.read_csv(RAW / "metabric.csv")
    recorded = manifest["datasets"]["metabric"]["missingness"]
    assert recorded["denominator"] == len(df)
    for column, values in recorded["columns"].items():
        assert int(df[column].isna().sum()) == values["count"]
        assert df[column].isna().mean() == pytest.approx(values["proportion"], abs=1e-10)


def test_pilot_metabric_provenance_is_separate_and_unchanged(manifest):
    """The Kaggle pilot source and its derived table match the manifest and are non-confirmatory (ADR-016)."""
    pilot = manifest["exploratory_sources"]["metabric_kaggle_v1"]
    source = ROOT / pilot["source_file"]
    assert hashlib.sha256(source.read_bytes()).hexdigest() == pilot["source_sha256"]

    # Re-derive the historical pilot table: the event is the complement of the
    # Kaggle overall_survival flag, and a row needs a complete outcome and a
    # positive duration.
    feature_columns = pilot["historical_derived_feature_columns"]
    pilot_source = pd.read_csv(
        source,
        usecols=[*feature_columns, "overall_survival_months", "overall_survival"],
        low_memory=False,
    )
    historical = pilot_source[feature_columns].copy()
    historical["duration"] = pd.to_numeric(pilot_source["overall_survival_months"], errors="coerce")
    historical["event"] = 1 - pd.to_numeric(pilot_source["overall_survival"], errors="coerce")
    historical = historical.dropna(subset=["duration", "event"])
    historical = historical.loc[historical["duration"] > 0].reset_index(drop=True)
    historical["event"] = historical["event"].astype(int)
    historical_hash = hashlib.sha256(historical.to_csv(index=False).encode()).hexdigest()

    assert historical_hash == pilot["historical_derived_raw_sha256"]
    assert len(historical) == pilot["historical_eligibility"]["analysis_records"]
    assert int(historical["event"].sum()) == pilot["historical_eligibility"]["events"]
    assert pilot["historical_eligibility"] == {
        "rule": "Complete outcome and positive overall_survival_months.",
        "analysis_records": 1903,
        "events": 1103,
        "exclusions_non_positive_time": 1,
    }
    assert "prohibited as confirmatory input" in pilot["role"]
