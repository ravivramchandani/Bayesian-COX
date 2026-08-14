"""Frozen-cell explainability, pairing, exactness and lineage tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from src.data.fold_preprocessing import FoldFeaturePreprocessor
from src.explainability.frozen_cells import (
    ExplanationProtocol,
    SamplingBudget,
    analyze_frozen_run,
    write_explainability_result,
)
from src.explainability.posterior_analysis import (
    grouped_posterior_contribution,
    recover_posterior_mean_abs_beta,
)
from src.explainability.shap_analysis import (
    exact_linear_shap_values,
    grouped_shap_importance,
)
from src.utils.reproducibility import canonical_json_hash, sha256_file


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _hashed(value: dict, field: str) -> dict:
    result = dict(value)
    result[field] = canonical_json_hash(result)
    return result


def _frozen_fixture(tmp_path: Path) -> tuple[Path, Path, list[str]]:
    project_root = tmp_path / "project"
    raw_path = project_root / "data" / "raw" / "toy.csv"
    raw_path.parent.mkdir(parents=True)
    values = np.arange(15, dtype=float)
    raw = pd.DataFrame(
        {
            "a": np.sin(values) + values / 5,
            "b": np.cos(values) - values / 7,
            "c": (values % 4) - 1.5,
            "d": np.sqrt(values + 1),
            "e": ((values * 3) % 7).astype(float),
            "time": values + 1,
            "event": (values.astype(int) % 2).astype(int),
        }
    )
    raw.to_csv(raw_path, index=False)
    feature_spec = {
        "numeric": ["a", "b", "c", "d", "e"],
        "categorical": [],
        "ordinal": {},
        "engineered": [],
    }
    dataset_config = {
        "toy": {
            "name": "Toy",
            "raw_file": "data/raw/toy.csv",
            "duration_col": "time",
            "event_col": "event",
            "primary_features": feature_spec,
        }
    }
    config_path = project_root / "config" / "datasets.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(yaml.safe_dump(dataset_config), encoding="utf-8")

    subject_ids = [f"toy-{index:02d}" for index in range(len(raw))]
    train_ids = subject_ids[:10]
    validation_ids = subject_ids[10:]
    processor = FoldFeaturePreprocessor(feature_spec)
    processor.fit(raw.iloc[:10])
    x_validation = processor.transform(raw.iloc[10:]).reset_index(drop=True)

    run_dir = project_root / "reports" / "confirmatory" / "toy_rehearsal"
    relative_cells: dict[str, str] = {}
    for model_key, beta_mean, beta_abs in (
        (
            "bayesian_normal",
            np.asarray([0.7, -0.5, 0.3, 0.2, -0.8]),
            np.asarray([0.8, 0.6, 0.4, 0.3, 0.9]),
        ),
        (
            "bayesian_horseshoe",
            np.asarray([0.6, -0.4, 0.2, 0.1, -0.7]),
            np.asarray([0.7, 0.5, 0.3, 0.2, 0.8]),
        ),
    ):
        stored = x_validation.abs().mean(axis=0).to_numpy() * beta_abs
        cell = {
            "schema_version": "1.0.0",
            "dataset": "toy",
            "dataset_sha256": sha256_file(raw_path),
            "model_key": model_key,
            "model": model_key,
            "repeat": 1,
            "fold": 1,
            "analysis_mode": "rehearsal",
            "evidence_status": "rehearsal_only",
            "status": "complete",
            "n_train": len(train_ids),
            "n_validation": len(validation_ids),
            "train_subject_ids": train_ids,
            "validation_subject_ids": validation_ids,
            "preprocessing": processor.metadata(),
            "predictions": {"subject_ids": validation_ids},
            "model_details": {
                "diagnostics": {"converged": False},
                "posterior_mean_beta": dict(
                    zip(processor.feature_names, beta_mean.tolist(), strict=True)
                ),
                "posterior_expected_absolute_contribution": [
                    {
                        "feature": feature,
                        "expected_abs_contribution": float(score),
                    }
                    for feature, score in zip(
                        processor.feature_names, stored, strict=True
                    )
                ],
                "posterior_expected_absolute_group_contribution_by_subject": {
                    "definition": "test exact posterior group contribution",
                    "group_names": processor.feature_names,
                    "values": (
                        x_validation.abs().to_numpy()
                        * beta_abs[None, :]
                    ).tolist(),
                },
            },
        }
        cell = _hashed(cell, "cell_content_sha256")
        cell_path = (
            run_dir
            / "cells"
            / "toy"
            / "repeat_01_fold_01"
            / f"{model_key}.json"
        )
        _write_json(cell_path, cell)
        relative_cells[str(cell_path.relative_to(run_dir))] = sha256_file(cell_path)

    cox_beta = np.asarray([0.5, -0.2, 0.4, 0.1, -0.6])
    cox_cell = _hashed(
        {
            "schema_version": "1.0.0",
            "dataset": "toy",
            "dataset_sha256": sha256_file(raw_path),
            "model_key": "cox_ph",
            "model": "Cox PH",
            "repeat": 1,
            "fold": 1,
            "analysis_mode": "rehearsal",
            "evidence_status": "rehearsal_only",
            "status": "complete",
            "n_train": len(train_ids),
            "n_validation": len(validation_ids),
            "train_subject_ids": train_ids,
            "validation_subject_ids": validation_ids,
            "preprocessing": processor.metadata(),
            "predictions": {"subject_ids": validation_ids},
            "model_details": {
                "coefficient_summary": [
                    {"feature": feature, "coef": float(coefficient)}
                    for feature, coefficient in zip(
                        processor.feature_names, cox_beta, strict=True
                    )
                ]
            },
        },
        "cell_content_sha256",
    )
    cox_path = (
        run_dir
        / "cells"
        / "toy"
        / "repeat_01_fold_01"
        / "cox_ph.json"
    )
    _write_json(cox_path, cox_cell)
    relative_cells[str(cox_path.relative_to(run_dir))] = sha256_file(cox_path)

    manifest = _hashed(
        {
            "schema_version": "1.0.0",
            "run_config": {
                "mode": "rehearsal",
                "protocol": {"feature_set": "primary"},
            },
            "input_sha256": {
                "config/datasets.yaml": sha256_file(config_path),
                "data/raw/toy.csv": sha256_file(raw_path),
            },
        },
        "manifest_content_sha256",
    )
    _write_json(run_dir / "manifest.json", manifest)
    completion = _hashed(
        {
            "schema_version": "1.0.0",
            "stored_cells": len(relative_cells),
            "all_stored_cell_hashes": relative_cells,
        },
        "completion_content_sha256",
    )
    _write_json(run_dir / "completion.json", completion)
    return project_root, run_dir, validation_ids


def _small_protocol() -> ExplanationProtocol:
    return ExplanationProtocol(
        seeds=(11, 13, 17),
        budgets=(
            SamplingBudget(2, 3),
            SamplingBudget(3, 5),
            SamplingBudget(4, 8),
        ),
        uncertainty_bootstraps=100,
    )


def test_importing_explainability_does_not_import_shap():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import src.explainability; assert 'shap' not in sys.modules",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_linear_explainer_is_exact_and_grouped_before_absolute_value():
    background = pd.DataFrame(
        {"x=a": [0.0, 1.0, 2.0], "x=b": [1.0, 0.0, 1.0], "z": [2.0, 4.0, 6.0]}
    )
    explained = pd.DataFrame(
        {"x=a": [3.0, 4.0], "x=b": [0.0, 1.0], "z": [1.0, 3.0]}
    )
    beta = np.asarray([2.0, -1.0, -0.5])
    values = exact_linear_shap_values(beta, background, explained)
    expected = (explained - background.mean(axis=0)) * beta
    np.testing.assert_allclose(values, expected, rtol=0, atol=1e-12)

    grouped = grouped_shap_importance(
        values, {"x=a": "x", "x=b": "x", "z": "z"}
    ).set_index("group")
    expected_x = np.abs(expected["x=a"] + expected["x=b"]).mean()
    assert grouped.loc["x", "mean_abs_shap"] == pytest.approx(expected_x)


def test_frozen_posterior_contribution_is_recovered_for_random_subsets():
    validation = pd.DataFrame(
        {"a": [-2.0, 0.0, 4.0], "b=one": [0.0, 1.0, 1.0], "b=two": [1.0, 0.0, 0.0]}
    )
    beta_abs = pd.Series([0.5, 0.8, 0.3], index=validation.columns)
    full = validation.abs().mean(axis=0) * beta_abs
    stored = [
        {"feature": feature, "expected_abs_contribution": float(score)}
        for feature, score in full.items()
    ]
    recovered, unidentified = recover_posterior_mean_abs_beta(validation, stored)
    pd.testing.assert_series_equal(recovered, beta_abs)
    assert unidentified == []

    grouped = grouped_posterior_contribution(
        validation.iloc[[0, 2]],
        recovered,
        {"a": "a", "b=one": "b", "b=two": "b"},
    ).set_index("group")
    assert grouped.loc["a", "expected_abs_contribution"] == pytest.approx(1.5)
    assert grouped.loc["b", "expected_abs_contribution"] == pytest.approx(0.55)


def test_frozen_run_uses_paired_random_samples_and_records_uncertainty(tmp_path):
    project_root, run_dir, validation_ids = _frozen_fixture(tmp_path)
    result = analyze_frozen_run(
        run_dir, project_root, protocol=_small_protocol()
    )

    assert result["evidence_status"] == "rehearsal_only"
    assert len(result["comparisons"]) == 18
    assert len(result["selection_registry"]) == 9
    assert len(result["agreement_uncertainty"]) == 2
    assert all(
        row["sampling_stability_gate"] in {"passed", "failed", "not_evaluable"}
        for row in result["agreement_uncertainty"]
    )
    secondary = result["secondary_cross_model_analysis"]
    assert secondary["cox_ph"]["status"] == "complete"
    assert len(secondary["cox_ph"]["comparisons"]) == 18
    paired_differences = secondary["cox_ph"]["paired_same_model_minus_cox"]
    assert len(paired_differences) == 2
    assert all(row["n_cell_seed_pairs"] == 3 for row in paired_differences)
    assert all("confidence_lower" not in row for row in paired_differences)
    assert all(row["spearman_rho"]["lower_95"] is not None for row in paired_differences)
    assert all(
        isinstance(row["stronger_same_model_agreement_supported"], bool)
        for row in paired_differences
    )
    assert all("same_model_sampling_stability_gate" in row for row in paired_differences)
    assert all("cox_sampling_stability_gate" in row for row in paired_differences)
    assert secondary["random_survival_forest"]["status"] == (
        "formally_dropped_unavailable"
    )
    assert secondary["random_survival_forest"]["frozen_cells_present"] is False
    assert "prob_direction" not in json.dumps(result)
    assert {
        row["grouped_intrinsic_source"] for row in result["comparisons"]
    } == {"stored_exact_full_posterior_group_contribution"}

    first_budget = [
        row for row in result["selection_registry"] if row["budget_index"] == 1
    ]
    assert all(row["validation_subject_ids"] != validation_ids[:2] for row in first_budget)
    for row in first_budget:
        assert set(row["validation_subject_ids"]).issubset(validation_ids)
        paired = [
            item
            for item in result["comparisons"]
            if item["selection_sha256"] == row["selection_sha256"]
        ]
        assert {item["model_key"] for item in paired} == {
            "bayesian_normal",
            "bayesian_horseshoe",
        }

    assert result["convergence"]["summary"]["n_evaluable"] > 0
    assert result["group_stability"]
    result_hash = result.pop("result_content_sha256")
    assert canonical_json_hash(result) == result_hash


def test_frozen_run_rejects_tampered_cell_file(tmp_path):
    project_root, run_dir, _validation_ids = _frozen_fixture(tmp_path)
    cell_path = next((run_dir / "cells").glob("*/*/*.json"))
    cell_path.write_text(cell_path.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(RuntimeError, match="stored cell file hash"):
        analyze_frozen_run(run_dir, project_root, protocol=_small_protocol())


def test_frozen_run_rejects_changed_raw_data(tmp_path):
    project_root, run_dir, _validation_ids = _frozen_fixture(tmp_path)
    raw_path = project_root / "data" / "raw" / "toy.csv"
    raw_path.write_text(raw_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="raw data do not match the cell hash"):
        analyze_frozen_run(run_dir, project_root, protocol=_small_protocol())


def test_result_writer_never_overwrites(tmp_path):
    output = tmp_path / "result.json"
    write_explainability_result(output, {"status": "first"})
    with pytest.raises(FileExistsError, match="already exists"):
        write_explainability_result(output, {"status": "second"})
