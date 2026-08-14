"""Frozen-grid, pairing, censoring and schema tests for robustness analyses."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from src.evaluation.metrics import integrated_brier
from src.pipelines.confirmatory import administratively_truncate_for_ipcw
from src.pipelines.robustness import (
    BAYESIAN_MODEL_KEYS,
    DESIGN_FEATURE_FOLD_NUMBERS_PER_REPEAT,
    aggregate_ph_tests,
    apply_administrative_censoring,
    build_condition_plan,
    build_design_conditions,
    build_rq2_conditions,
    effective_information_ratio,
    individual_integrated_brier_losses,
    multiple_imputed_fold_frames,
    paired_ibs_inference,
    planned_fit_counts,
    projected_runtime_from_confirmatory,
    stratified_training_subsets,
    summarize_imputation_predictions,
    validate_robustness_cell,
)
from src.utils.reproducibility import canonical_json_hash

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


@pytest.fixture
def configs() -> tuple[dict, dict]:
    return (
        _yaml(PROJECT_ROOT / "config" / "confirmatory.yaml"),
        _yaml(PROJECT_ROOT / "config" / "datasets.yaml"),
    )


def test_fractional_subsets_are_nested_deterministic_and_prior_independent():
    times = np.linspace(1.0, 120.0, 120)
    events = np.tile([0, 1], 60)
    fractions = [0.25, 0.50, 0.75, 1.0]
    first = stratified_training_subsets(times, events, fractions, seed=101, max_time_bins=4)
    second = stratified_training_subsets(times, events, fractions, seed=101, max_time_bins=4)
    for fraction in fractions:
        assert np.array_equal(first[fraction], second[fraction])
        selected_events = events[first[fraction]]
        assert set(selected_events) == {0, 1}
    assert set(first[0.25]) < set(first[0.50])
    assert set(first[0.50]) < set(first[0.75])
    assert set(first[0.75]) < set(first[1.0])


def test_administrative_censoring_truncates_train_and_validation_consistently():
    times = np.asarray([2.0, 5.0, 8.0, 12.0])
    events = np.asarray([1, 0, 1, 1])
    truncated_time, truncated_event = apply_administrative_censoring(times, events, 8.0)
    assert truncated_time.tolist() == [2.0, 5.0, 8.0, 8.0]
    assert truncated_event.tolist() == [1, 0, 1, 0]
    observed_time, observed_event = apply_administrative_censoring(times, events, None)
    assert np.array_equal(observed_time, times)
    assert np.array_equal(observed_event, events)


def test_individual_ibs_losses_average_to_reference_implementation():
    train_time = np.asarray([2.0, 3.0, 4.0, 6.0, 8.0, 10.0])
    train_event = np.asarray([1, 0, 1, 1, 0, 1])
    validation_time = np.asarray([2.5, 5.0, 7.0, 9.0])
    validation_event = np.asarray([1, 0, 1, 0])
    grid = np.asarray([3.0, 5.0, 7.0])
    survival = np.asarray(
        [
            [0.80, 0.60, 0.50],
            [0.90, 0.75, 0.65],
            [0.85, 0.65, 0.45],
            [0.95, 0.85, 0.75],
        ]
    )
    losses = individual_integrated_brier_losses(
        train_time,
        train_event,
        validation_time,
        validation_event,
        survival,
        grid,
    )
    reference = integrated_brier(
        train_time,
        train_event,
        validation_time,
        validation_event,
        survival,
        grid,
    )
    assert float(np.mean(losses)) == pytest.approx(reference)


def test_long_validation_followup_uses_same_ipcw_tau_for_losses_auc_and_uno():
    train_time = np.asarray([2.0, 3.0, 4.0, 6.0, 8.0, 10.0])
    train_event = np.asarray([1, 0, 1, 1, 0, 1])
    validation_time = np.asarray([2.5, 5.0, 7.0, 100.0])
    validation_event = np.asarray([1, 0, 1, 1])
    grid = np.asarray([3.0, 5.0, 7.0])
    survival = np.asarray(
        [
            [0.80, 0.60, 0.50],
            [0.90, 0.75, 0.65],
            [0.85, 0.65, 0.45],
            [0.95, 0.85, 0.75],
        ]
    )
    risk = np.asarray([0.8, 0.4, 0.7, 0.1])
    losses = individual_integrated_brier_losses(
        train_time,
        train_event,
        validation_time,
        validation_event,
        survival,
        grid,
    )
    ipcw_time, ipcw_event = administratively_truncate_for_ipcw(
        validation_time, validation_event, float(grid[-1])
    )
    reference = integrated_brier(
        train_time,
        train_event,
        ipcw_time,
        ipcw_event,
        survival,
        grid,
    )
    assert float(np.mean(losses)) == pytest.approx(reference)

    metrics = summarize_imputation_predictions(
        train_time,
        train_event,
        validation_time,
        validation_event,
        risk,
        survival,
        grid,
        grid,
    )
    assert metrics["ipcw_administrative_truncation_tau"] == 7.0
    assert metrics["ibs"] == pytest.approx(reference)
    assert np.isfinite(metrics["uno_c_index"])
    assert np.isfinite(metrics["auc_at_horizons"]).all()


def test_rq2_grid_is_nonfactorial_and_uses_only_folds_one_and_two(configs):
    config, _datasets = configs
    conditions = build_rq2_conditions(config)
    assert len(conditions) == 6
    assert sum(item.training_fraction < 1 for item in conditions) == 3
    censored = [item for item in conditions if item.censoring_quantile is not None]
    assert len(censored) == 2
    assert {item.censoring_quantile for item in censored} == {0.50, 0.75}
    assert all(item.training_fraction == 1.0 for item in censored)
    assert all(item.selected_fold_numbers == (1, 2) for item in conditions)


def test_design_grid_is_one_factor_at_a_time_and_feature_names_are_exact(configs):
    config, datasets = configs
    design = build_design_conditions(config)
    assert {(item.prior_scenario, item.n_intervals) for item in design} == {
        ("tighter", 6),
        ("primary", 6),
        ("wider", 6),
        ("primary", 4),
        ("primary", 10),
    }
    primary = next(
        item for item in design if item.prior_scenario == "primary" and item.n_intervals == 6
    )
    assert primary.selected_fold_numbers == (1, 2)
    assert all(
        item.selected_fold_numbers == DESIGN_FEATURE_FOLD_NUMBERS_PER_REPEAT
        for item in design
        if item is not primary
    )
    plan = build_condition_plan(config, datasets["metabric"], ("feature",))
    assert {item.feature_set for item in plan} == {
        "primary",
        *datasets["metabric"]["sensitivity_feature_sets"],
    }
    mi = [item for item in plan if item.imputation_method == "iterative_posterior_m5"]
    assert len(mi) == 1
    assert mi[0].feature_set == "npi_plus_stage"


def test_frozen_lean_plan_has_exact_cell_and_fit_count(configs):
    config, datasets = configs
    plans = {
        name: build_condition_plan(config, datasets[name], ("rq2", "design", "feature"))
        for name in config["datasets"]
    }
    counts = planned_fit_counts(
        plans,
        outer_repeats=config["validation"]["outer_repeats"],
        outer_splits=config["validation"]["outer_splits"],
    )
    assert counts["total_checkpoint_cells"] == 825
    assert counts["total_bayesian_fits"] == 885
    assert counts["calibration_bootstrap_replicates_per_cell"] == 0
    assert counts["rq2_fold_numbers_per_repeat"] == [1, 2]
    assert counts["design_feature_fold_numbers_per_repeat"] == [1]


def test_effective_information_is_events_over_transformed_columns():
    assert effective_information_ratio(40, 10) == 4.0
    with pytest.raises(ValueError, match="positive"):
        effective_information_ratio(40, 0)


def test_runtime_projection_scales_result_blind_mcmc_work(tmp_path: Path):
    manifest = {"run_config": {"bayes_draws": 100, "bayes_tune": 100, "bayes_chains": 2}}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    cell = {
        "dataset": "toy",
        "model_key": "bayesian_normal",
        "fit_attempts": [{"fit_seconds": 10.0}],
    }
    cell["cell_content_sha256"] = canonical_json_hash(cell)
    cell_path = tmp_path / "cells" / "toy" / "repeat_01_fold_01" / "bayesian_normal.json"
    cell_path.parent.mkdir(parents=True)
    cell_path.write_text(json.dumps(cell), encoding="utf-8")
    counts = {
        "grouped": [
            {
                "dataset": "toy",
                "model_key": "bayesian_normal",
                "checkpoint_cells": 2,
                "bayesian_fits": 2,
            }
        ]
    }
    projection = projected_runtime_from_confirmatory(
        tmp_path,
        counts,
        maximum_hours=1.0,
        target_draws=200,
        target_tune=200,
        target_chains=2,
    )
    assert projection["mcmc_work_multiplier"] == 2.0
    assert projection["projected_serial_hours"] == pytest.approx(52.0 / 3600.0)
    assert projection["feasible"] is True


def test_multiple_imputation_is_training_only_and_has_distinct_recorded_seeds(configs):
    _config, datasets = configs
    specification = datasets["metabric"]["sensitivity_feature_sets"]["npi_plus_stage"]
    training = {
        "age_at_diagnosis": [40.0, 50.0, 60.0, 70.0, 80.0, 55.0],
        "nottingham_prognostic_index": [2.0, 3.0, np.nan, 4.0, 5.0, 2.5],
        "tumor_stage": [1.0, np.nan, 2.0, 3.0, 4.0, 2.0],
        "cellularity": ["Low", "High", None, "High", "Low", "High"],
        "er_status": ["Positive"] * 6,
        "pr_status": ["Positive"] * 6,
        "her2_status": ["Negative"] * 6,
        "inferred_menopausal_state": ["Post"] * 6,
        "pam50_+_claudin-low_subtype": ["LumA"] * 6,
    }
    validation = {name: values[:2] for name, values in training.items()}
    validation_extreme = copy.deepcopy(validation)
    validation_extreme["tumor_stage"] = [1000.0, np.nan]
    seeds = [11, 12, 13, 14, 15]
    first = multiple_imputed_fold_frames(
        pd.DataFrame(training),
        pd.DataFrame(validation),
        specification,
        seeds=seeds,
    )
    second = multiple_imputed_fold_frames(
        pd.DataFrame(training),
        pd.DataFrame(validation_extreme),
        specification,
        seeds=seeds,
    )
    assert len(first) == 5
    assert [item[2]["seed"] for item in first] == seeds
    for left, right in zip(first, second, strict=True):
        assert np.allclose(
            left[0][specification["numeric"]].to_numpy(float),
            right[0][specification["numeric"]].to_numpy(float),
        )
        assert left[2]["validation_refit"] is False


def _fake_cell(
    model_key: str,
    condition: str,
    losses: list[float],
    *,
    repeat: int = 1,
    fold: int = 1,
) -> dict:
    cell = {
        "schema_version": "1.0.0",
        "analysis_id": "confirmatory_v1_robustness",
        "analysis_mode": "rehearsal",
        "dataset": "toy",
        "dataset_sha256": "d" * 64,
        "model_key": model_key,
        "prior": model_key.removeprefix("bayesian_"),
        "repeat": repeat,
        "fold": fold,
        "condition": {
            "condition_id": f"rq2_{condition}",
            "analyses": [{"component": "rq2", "condition": condition}],
            "feature_set": "primary",
            "training_fraction": 1.0,
            "censoring_name": "observed_followup",
            "censoring_quantile": None,
            "prior_scenario": "primary",
            "n_intervals": 6,
            "selected_fold_numbers": [1, 2],
            "imputation_method": "single_fold_local",
        },
        "training_subset_sha256": "a" * 64,
        "modified_outcomes_sha256": "b" * 64,
        "train_subject_ids": ["t1", "t2"],
        "validation_subject_ids": ["v1", "v2", "v3", "v4"],
        "n_train": 2,
        "n_validation": 4,
        "events_train": 1,
        "events_validation": 2,
        "processed_feature_degrees_of_freedom": 2,
        "effective_information_events_per_degree_of_freedom": 0.5,
        "original_events_validation": [0, 0, 1, 1],
        "status": "complete",
        "individual_ibs_loss": losses,
    }
    cell["cell_content_sha256"] = canonical_json_hash(cell)
    return cell


def test_result_schema_and_paired_difference_in_differences():
    cells = []
    for model_index, model in enumerate(BAYESIAN_MODEL_KEYS):
        full = [0.10 + model_index * 0.01] * 4
        reduced = [0.12 + model_index * 0.02] * 4
        cells.append(_fake_cell(model, "fraction_100_observed", full))
        cells.append(_fake_cell(model, "fraction_025_observed", reduced))
    for cell in cells:
        validate_robustness_cell(cell)

    result = paired_ibs_inference(
        cells,
        components=("rq2",),
        n_bootstraps=20,
        confidence_level=0.95,
        seed=11,
    )
    assert result["schema_version"] == "1.0.0"
    did = result["difference_in_differences"]
    assert len(did) == 3
    assert all(item["status"] == "complete" for item in did)
    assert did[0]["effect"]["n_successful"] == 20
    assert did[0]["effect"]["n_outer_repeats"] == 1
    assert "outer repeats" in did[0]["effect"]["resampling_unit"]


def test_cell_hash_tampering_is_rejected():
    cell = _fake_cell("bayesian_normal", "fraction_100_observed", [0.1] * 4)
    broken = copy.deepcopy(cell)
    broken["events_train"] = 99
    with pytest.raises(ValueError, match="content hash"):
        validate_robustness_cell(broken)


def test_ph_aggregation_recomputes_holm_without_fitting(tmp_path: Path):
    cell = {
        "dataset": "toy",
        "repeat": 1,
        "fold": 1,
        "status": "complete",
        "model_details": {
            "ph_test": [
                {"feature": "age", "test_statistic": 5.0, "p": 0.01},
                {"feature": "stage", "test_statistic": 1.0, "p": 0.20},
            ]
        },
    }
    cell["cell_content_sha256"] = canonical_json_hash(cell)
    path = tmp_path / "cells" / "toy" / "repeat_01_fold_01" / "cox_ph.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(cell), encoding="utf-8")

    result = aggregate_ph_tests(tmp_path)
    rows = result["covariate_tests"]
    assert [row["covariate"] for row in rows] == ["age", "stage"]
    assert rows[0]["holm_adjusted_p"] == pytest.approx(0.02)
    assert rows[0]["holm_reject_0_05"] is True
    assert "limitation" in result["frozen_response"]
