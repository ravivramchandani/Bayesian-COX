"""Frozen-grid, pairing, censoring and schema tests for robustness analyses.

Covers ``src/pipelines/robustness``: the prespecified condition grids for RQ2
(information-regime robustness: training size and administrative censoring)
and for the design and feature sensitivities (ADR-023), paired training
subsets, per-subject inverse-probability-of-censoring-weighted (IPCW)
integrated Brier score (IBS) losses, fold-local multiple imputation (MI),
paired IBS inference, aggregation of the Cox proportional hazards (PH) tests,
fit counts and runtime projection, and the provenance checks that decide
whether a run directory may be created, resumed or accepted as complete.
Frozen evidence is verified at its checkpoint commit (ADR-030).
"""

from __future__ import annotations

import copy
import json
from dataclasses import replace
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
from src.utils.reproducibility import canonical_json_hash, sha256_file

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _yaml(path: Path) -> dict:
    """Parse one YAML file."""
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


@pytest.fixture
def configs() -> tuple[dict, dict]:
    """The frozen protocol (``confirmatory.yaml``) and cohort schemas (``datasets.yaml``)."""
    return (
        _yaml(PROJECT_ROOT / "config" / "confirmatory.yaml"),
        _yaml(PROJECT_ROOT / "config" / "datasets.yaml"),
    )


def test_fractional_subsets_are_nested_deterministic_and_prior_independent():
    """Seeded training fractions are reproducible, keep both event classes and are strictly nested."""
    # Evenly spaced times with alternating event status give eight equal
    # event/time strata of 15 subjects, so every fraction samples each stratum.
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
    """A cutoff keeps events at or before it, censors later follow-up there, and None changes nothing."""
    times = np.asarray([2.0, 5.0, 8.0, 12.0])
    events = np.asarray([1, 0, 1, 1])
    truncated_time, truncated_event = apply_administrative_censoring(times, events, 8.0)
    assert truncated_time.tolist() == [2.0, 5.0, 8.0, 8.0]
    assert truncated_event.tolist() == [1, 0, 1, 0]
    observed_time, observed_event = apply_administrative_censoring(times, events, None)
    assert np.array_equal(observed_time, times)
    assert np.array_equal(observed_event, events)


def test_individual_ibs_losses_average_to_reference_implementation():
    """Per-subject IPCW Brier losses average to the reference integrated Brier score."""
    # Each subject's loss is the trapezoidal average over the grid of
    # S(t)^2 / G(T) if the subject had an event by t, or (1 - S(t))^2 / G(t)
    # if still under follow-up after t, where G is the training censoring
    # survival; a subject censored by t contributes zero at t.
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
    """IBS, AUC and Uno's C-index share one truncation time, the last horizon (here tau = 7)."""
    # The last validation subject is followed to 100, far beyond the last
    # training time of 10. Untruncated, the reference IBS rejects that time;
    # after truncation at tau = 7 it is censored just after 7.
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
    """RQ2 has four training fractions and two full-size truncations, all on folds 1 and 2 (ADR-023)."""
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
    """Prior-scale and interval variants change one factor each; feature sets match the schema (ADR-023)."""
    # The primary anchor (primary priors, six intervals) runs on folds 1 and 2;
    # every other design condition runs on fold 1 only.
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
    # METABRIC also has the five-imputation stage sensitivity.
    plan = build_condition_plan(config, datasets["metabric"], ("feature",))
    assert {item.feature_set for item in plan} == {
        "primary",
        *datasets["metabric"]["sensitivity_feature_sets"],
    }
    mi = [item for item in plan if item.imputation_method == "iterative_posterior_m5"]
    assert len(mi) == 1
    assert mi[0].feature_set == "npi_plus_stage"


def test_frozen_lean_plan_has_exact_cell_and_fit_count(configs):
    """The frozen plan has 825 checkpoint cells and 885 Bayesian fits (ADR-023)."""
    # Fits exceed cells because each five-imputation cell needs five fits.
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
    """Effective information is training events per processed column; zero columns raise."""
    assert effective_information_ratio(40, 10) == 4.0
    with pytest.raises(ValueError, match="positive"):
        effective_information_ratio(40, 0)


def test_runtime_projection_scales_result_blind_mcmc_work(tmp_path: Path):
    """Runtime projection scales stored fit times by the ratio of Markov chain Monte Carlo work."""
    # Source work is (100 + 100) x 2 and target work (200 + 200) x 2, a factor
    # of 2. One 10-second cell projects to 20 s per fit; two fits with the
    # 1.30 overhead give 52 s.
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
    """MI is fitted on training rows only, records the five supplied seeds and marks no validation refit."""
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
    # The two runs differ only in one validation tumour stage, set to 1000;
    # identical training imputations show that validation rows do not affect the fit.
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
    """Return a minimal, correctly hashed, complete Bayesian cell for one RQ2 condition.

    Args:
        model_key: One of ``BAYESIAN_MODEL_KEYS``.
        condition: RQ2 condition name, for example ``"fraction_100_observed"``.
        losses: Individual IBS losses, one per validation subject.
        repeat: Outer repeat number.
        fold: Outer fold number.
    """
    # Four validation subjects in two event strata; the stored information
    # ratio equals events_train / degrees of freedom, 1 / 2, so schema
    # validation passes. Apart from its ID and analysis name, the condition
    # record is the same for every RQ2 condition.
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
    """Valid cells yield one complete RQ2 difference-in-differences per prior pair."""
    # Constant losses per model, reduced and full, for the three Bayesian
    # priors; the three prior pairs give three difference-in-differences.
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
    """Editing a cell without recomputing its content hash fails validation."""
    cell = _fake_cell("bayesian_normal", "fraction_100_observed", [0.1] * 4)
    broken = copy.deepcopy(cell)
    broken["events_train"] = 99
    with pytest.raises(ValueError, match="content hash"):
        validate_robustness_cell(broken)


def test_ph_aggregation_recomputes_holm_without_fitting(tmp_path: Path):
    """Stored Cox PH tests are Holm-adjusted per fit without refitting and framed as a limitation."""
    # With p-values 0.01 and 0.20, Holm multiplies the smaller by 2 (0.02),
    # which rejects at 0.05.
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


def _rehearsal_options(output_root: Path):
    """Rehearsal options for one WHAS500 RQ2 fold, writing under ``output_root``."""
    from src.pipelines.robustness import RobustnessOptions

    return RobustnessOptions(
        mode="rehearsal",
        datasets=("whas500",),
        components=("rq2",),
        outer_splits=5,
        outer_repeats=1,
        fold_limit_per_dataset=1,
        bayes_draws=300,
        bayes_tune=300,
        bayes_chains=2,
        sensitivity_bootstraps=30,
        resume=False,
        output_root=output_root,
    )


def test_execution_manifest_records_all_current_modules(configs, tmp_path):
    """The run manifest hashes every current src module, not the retired single-file module."""
    from src.pipelines.robustness.provenance import build_execution_manifest

    config, _datasets = configs
    manifest = build_execution_manifest(
        PROJECT_ROOT, {"protocol": config}, _rehearsal_options(tmp_path)
    )
    current_sources = {
        str(path.relative_to(PROJECT_ROOT)) for path in PROJECT_ROOT.glob("src/**/*.py")
    }
    assert current_sources <= set(manifest["input_sha256"])
    assert "src/pipelines/robustness.py" not in manifest["input_sha256"]
    assert "src/pipelines/robustness/__init__.py" in manifest["input_sha256"]
    assert "MISSING" not in manifest["input_sha256"].values()


def test_code_identity_separates_runs_and_changed_runtime_cannot_resume(tmp_path, monkeypatch):
    """A changed runtime blocks resume, and changed code gets a separate run directory."""
    from src.pipelines.robustness import provenance

    actual_config = {"protocol": {"analysis_id": "toy"}}
    manifest = {
        "run_config": actual_config,
        "config_sha256": canonical_json_hash(actual_config),
        "input_sha256": {"src/example.py": "a" * 64},
        "execution_code_sha256": "b" * 64,
        "environment": {"python": "3.11.15"},
    }

    def current_manifest(*_args):
        """Return the test's current manifest, hashed as the real builder would."""
        current = copy.deepcopy(manifest)
        current["manifest_content_sha256"] = canonical_json_hash(current)
        return current

    monkeypatch.setattr(provenance, "build_execution_manifest", current_manifest)
    options = _rehearsal_options(tmp_path)
    first, complete = provenance.initialise_run_directory(
        PROJECT_ROOT, actual_config, options, {}, {}
    )
    assert complete is False
    manifest["environment"] = {"python": "different"}
    with pytest.raises(RuntimeError, match="runtime changed"):
        provenance.initialise_run_directory(
            PROJECT_ROOT, actual_config, replace(options, resume=True), {}, {}
        )
    manifest["execution_code_sha256"] = "c" * 64
    manifest["input_sha256"]["src/example.py"] = "d" * 64
    second, complete = provenance.initialise_run_directory(
        PROJECT_ROOT, actual_config, options, {}, {}
    )
    assert first != second
    assert complete is False


def test_unfinished_historical_run_is_not_resumed_by_current_code(tmp_path, monkeypatch):
    """Resume refuses an unfinished run in the historical config-only directory and leaves it intact."""
    from src.pipelines.robustness import provenance

    # Historical runs were named by the configuration hash alone; a manifest
    # without completion.json marks one as unfinished.
    actual_config = {"protocol": {"analysis_id": "toy"}}
    digest = canonical_json_hash(actual_config)
    monkeypatch.setattr(
        provenance,
        "build_execution_manifest",
        lambda *_args: {
            "config_sha256": digest,
            "execution_code_sha256": "c" * 64,
        },
    )
    legacy = tmp_path / f"toy_robustness_rehearsal_{digest[:12]}"
    legacy.mkdir()
    (legacy / "manifest.json").write_text("{}", encoding="utf-8")
    with pytest.raises(RuntimeError, match="unchanged original code and runtime"):
        provenance.initialise_run_directory(
            PROJECT_ROOT,
            actual_config,
            replace(_rehearsal_options(tmp_path), resume=True),
            {},
            {},
        )
    assert sorted(path.name for path in legacy.iterdir()) == ["manifest.json"]


@pytest.mark.parametrize(
    ("wrong_body", "message"),
    [
        ({"dataset": "other"}, "identity differs"),
        ({"repeat": 2}, "identity differs"),
        ({"fold": 2}, "identity differs"),
        ({"model_key": "bayesian_horseshoe"}, "identity differs"),
        ({"condition": {"feature_set": "wrong"}}, "condition differs"),
        ({"dataset_sha256": "e" * 64}, "raw-data hash differs"),
        ({"status": "unavailable_minimum_training_events"}, "completed-run status"),
    ],
)
def test_completed_historical_verification_is_read_only_and_rejects_rehashed_wrong_cells(
    tmp_path, monkeypatch, wrong_body, message
):
    """Completed-run checks write nothing and reject cells re-hashed with a wrong identity (ADR-030)."""
    from src.pipelines.robustness import provenance

    # Build a minimal completed production run: three RQ2 cells, empty
    # aggregates and a consistent completion record. The frozen-evidence check
    # is replaced by a stub whose frozen inputs equal the manifest's study
    # inputs, so those inputs (including src/retired.py, absent from the
    # project) count as historical and are not re-hashed from the project.
    project = tmp_path / "project"
    run_dir = tmp_path / "robustness"
    source = tmp_path / "frozen_confirmatory"
    source.mkdir()
    (project / "config").mkdir(parents=True)
    (project / "config/datasets.yaml").write_text(
        "toy:\n  raw_file: data/raw/toy.csv\n", encoding="utf-8"
    )
    (source / "manifest.json").write_text("{}", encoding="utf-8")
    inputs = {
        "src/retired.py": "a" * 64,
        "config/confirmatory.yaml": "b" * 64,
        "data/raw/toy.csv": "d" * 64,
    }
    freeze = {"freeze_content_sha256": "f" * 64, "frozen_input_sha256": inputs}
    checked = []

    def verify_checkpoint(_project_root, expected=None):
        """Record the requested checkpoint and return the stub freeze."""
        checked.append(expected)
        return freeze

    monkeypatch.setattr(provenance, "verify_frozen_evidence", verify_checkpoint)
    monkeypatch.setattr(provenance, "_verify_frozen_plan", lambda *_args: None)
    run_config = {
        "mode": "robustness",
        "components": ["rq2"],
        "confirmatory_run": source.name,
        "datasets": ["toy"],
        "outer_repeats": 1,
        "outer_splits": 1,
        "condition_plan": {
            "toy": [_fake_cell("bayesian_normal", "fraction_100_observed", [])['condition']]
        },
    }
    manifest = {
        "run_config": run_config,
        "config_sha256": canonical_json_hash(run_config),
        "protocol_freeze_sha256": freeze["freeze_content_sha256"],
        "input_sha256": {
            **inputs,
            f"reports/confirmatory/{source.name}/manifest.json": sha256_file(
                source / "manifest.json"
            ),
        },
    }
    manifest["manifest_content_sha256"] = canonical_json_hash(manifest)
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    cell_hashes = {}
    for model_key in BAYESIAN_MODEL_KEYS:
        cell = _fake_cell(model_key, "fraction_100_observed", [0.1] * 4)
        cell["analysis_mode"] = "robustness"
        cell.pop("cell_content_sha256")
        cell["cell_content_sha256"] = canonical_json_hash(cell)
        path = run_dir / f"cells/toy/repeat_01_fold_01/rq2_fraction_100_observed/{model_key}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cell), encoding="utf-8")
        cell_hashes[str(path.relative_to(run_dir))] = sha256_file(path)
    cell_path = (
        run_dir / "cells/toy/repeat_01_fold_01/rq2_fraction_100_observed/bayesian_normal.json"
    )
    aggregates = {}
    for name in (
        "paired_ibs_inference.json",
        "analysis_availability.json",
        "feasibility_plan.json",
    ):
        (run_dir / name).write_text("{}", encoding="utf-8")
        aggregates[name] = sha256_file(run_dir / name)
    completion = {
        "stored_cells": 3,
        "planned_cells_in_this_invocation": 3,
        "status_counts": {"complete": 3},
        "cell_sha256": cell_hashes,
        "aggregate_sha256": aggregates,
    }
    completion["completion_content_sha256"] = canonical_json_hash(completion)
    (run_dir / "completion.json").write_text(json.dumps(completion), encoding="utf-8")
    before = {
        path: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in run_dir.rglob("*")
        if path.is_file()
    }
    assert (
        provenance.verify_completed_robustness_run(run_dir, project, confirmatory_run_dir=source)
        == completion
    )
    assert checked == [None]
    assert before == {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in before}
    cell_path.write_text(cell_path.read_text() + " ", encoding="utf-8")
    with pytest.raises(RuntimeError, match="stored cell file hash"):
        provenance.verify_completed_robustness_run(run_dir, project, confirmatory_run_dir=source)
    wrong_cell = json.loads(before[cell_path][0])
    for key, value in wrong_body.items():
        if key == "condition":
            wrong_cell[key].update(value)
        else:
            wrong_cell[key] = value
    wrong_cell.pop("cell_content_sha256")
    wrong_cell["cell_content_sha256"] = canonical_json_hash(wrong_cell)
    cell_path.write_text(json.dumps(wrong_cell), encoding="utf-8")
    completion["cell_sha256"][str(cell_path.relative_to(run_dir))] = sha256_file(cell_path)
    completion.pop("completion_content_sha256")
    completion["completion_content_sha256"] = canonical_json_hash(completion)
    (run_dir / "completion.json").write_text(json.dumps(completion), encoding="utf-8")
    with pytest.raises(RuntimeError, match=message):
        provenance.verify_completed_robustness_run(run_dir, project, confirmatory_run_dir=source)


def test_completed_production_plan_must_match_all_825_frozen_cells(configs, tmp_path):
    """Require the frozen robustness plan to contain all 825 cell identities."""
    from src.pipelines.robustness import provenance
    from src.utils.io import json_safe

    config, datasets = configs
    validation = config["validation"]
    bayesian = config["models"]["bayesian_cox"]
    plans = {
        name: build_condition_plan(config, datasets[name], ("rq2", "design", "feature"))
        for name in config["datasets"]
    }
    fit_plan = planned_fit_counts(
        plans, outer_repeats=validation["outer_repeats"], outer_splits=validation["outer_splits"]
    )
    run_config = {
        "mode": "robustness",
        "protocol": config,
        "datasets": config["datasets"],
        "components": ["rq2", "design", "feature", "ph"],
        "outer_splits": validation["outer_splits"],
        "outer_repeats": validation["outer_repeats"],
        "fold_limit_per_dataset": None,
        "bayes_draws": bayesian["draws"],
        "bayes_tune": bayesian["tune"],
        "bayes_chains": bayesian["chains"],
        "sensitivity_bootstraps": 2000,
        "frozen_production_fit_plan": fit_plan,
        "condition_plan": json_safe(
            {name: [condition.to_dict() for condition in plan] for name, plan in plans.items()}
        ),
        "runtime_projection": {"feasible": True},
    }
    feasibility = {"fit_plan": fit_plan, "runtime_projection": run_config["runtime_projection"]}
    feasibility["feasibility_content_sha256"] = canonical_json_hash(feasibility)
    (tmp_path / "feasibility_plan.json").write_text(json.dumps(feasibility), encoding="utf-8")
    provenance._verify_frozen_plan(PROJECT_ROOT, tmp_path, run_config)
    assert len(provenance._planned_cell_paths(run_config)) == 825
    incomplete = copy.deepcopy(run_config)
    incomplete["condition_plan"]["gbsg2"].pop()
    with pytest.raises(RuntimeError, match="condition grid differs"):
        provenance._verify_frozen_plan(PROJECT_ROOT, tmp_path, incomplete)
