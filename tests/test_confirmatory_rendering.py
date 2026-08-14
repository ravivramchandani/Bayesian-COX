"""Pure-renderer provenance, evidence-boundary and determinism tests."""

from __future__ import annotations

import ast
import gzip
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RENDERER_PATH = PROJECT_ROOT / "scripts" / "render_confirmatory.py"


def _renderer() -> ModuleType:
    spec = importlib.util.spec_from_file_location("confirmatory_renderer", RENDERER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load confirmatory renderer")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _canonical(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()
    import hashlib

    return hashlib.sha256(payload).hexdigest()


def _file_hash(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _calibration(offset: float) -> list[dict[str, Any]]:
    return [
        {
            "summary": {
                "horizon": 5.0,
                "n_bootstrap_successful": 30,
                "calibration_in_the_large": {
                    "estimate": 0.02 + offset,
                    "lower": -0.08 + offset,
                    "upper": 0.12 + offset,
                },
                "intercept": {
                    "estimate": 0.05 + offset,
                    "lower": -0.15 + offset,
                    "upper": 0.25 + offset,
                },
                "slope": {
                    "estimate": 1.0 + offset,
                    "lower": 0.8 + offset,
                    "upper": 1.2 + offset,
                },
            },
            "curve": {
                "horizon": 5.0,
                "bins": [
                    {
                        "bin": 1,
                        "n": 1,
                        "mean_predicted_survival": 0.45 + offset,
                        "observed_survival": 0.5,
                        "observed_lower": 0.2,
                        "observed_upper": 0.8,
                    },
                    {
                        "bin": 2,
                        "n": 1,
                        "mean_predicted_survival": 0.8 + offset,
                        "observed_survival": 1.0,
                        "observed_lower": 1.0,
                        "observed_upper": 1.0,
                    },
                ],
            },
        }
    ]


def _cell(model_key: str, *, mode: str) -> dict[str, Any]:
    bayesian = model_key.startswith("bayesian_")
    offset = 0.01 if bayesian else 0.0
    cell: dict[str, Any] = {
        "schema_version": "1.0.0",
        "dataset": "toy",
        "dataset_sha256": "a" * 64,
        "model_key": model_key,
        "model": "Bayesian Cox (normal)" if bayesian else "Cox PH",
        "repeat": 1,
        "fold": 1,
        "fold_seed": 10,
        "cell_seed": 11 if bayesian else 12,
        "analysis_mode": mode,
        "evidence_status": "confirmatory" if mode == "confirmatory" else "rehearsal_only",
        "train_subject_ids": [f"s{index}" for index in range(8)],
        "validation_subject_ids": ["s8", "s9"],
        "n_train": 8,
        "n_validation": 2,
        "events_train": 4,
        "events_validation": 1,
        "status": "complete",
        "selected_hyperparameters": {},
        "inner_tuning": {"tuned": False, "candidates": []},
        "preprocessing": {"feature_names": ["age"]},
        "metrics": {
            "harrell_c_index": 0.65 + offset,
            "uno_c_index": 0.64 + offset,
            "ibs": 0.18 - offset,
            "mean_auc": 0.66 + offset,
            "horizons": [5.0],
            "auc_at_horizons": [0.66 + offset],
            "calibration": _calibration(offset),
        },
        "predictions": {"subject_ids": ["s8", "s9"]},
        "total_seconds": 0.4 if bayesian else 0.1,
    }
    if bayesian:
        diagnostics = {
            "converged": True,
            "r_hat_max": 1.0,
            "ess_bulk_min": 800,
            "ess_tail_min": 700,
            "n_divergent": 0,
            "bfmi_min": 0.9,
            "n_max_tree_depth": 0,
            "variables_checked": ["beta", "log_lambda"],
        }
        cell["fit_attempts"] = [{"attempt": 1, "fit_seconds": 0.3, "diagnostics": diagnostics}]
        cell["model_details"] = {
            "diagnostics": diagnostics,
            "coefficient_summary": [{"feature": "age", "coef (beta_mean)": 0.1}],
            "prior_predictive": {
                "baseline_survival": [
                    {
                        "time": 5.0,
                        "scaled_time": 1.0,
                        "median_survival": 0.6,
                        "lower_95": 0.2,
                        "upper_95": 0.9,
                    }
                ],
                "covariate_population_survival": [
                    {
                        "time": 5.0,
                        "scaled_time": 1.0,
                        "subject_draw_median_survival": 0.58,
                        "subject_draw_lower_95": 0.15,
                        "subject_draw_upper_95": 0.92,
                        "mean_survival_across_subjects_median": 0.59,
                        "proportion_subject_draws_below_0_01": 0.01,
                        "proportion_subject_draws_above_0_99": 0.02,
                    }
                ],
            },
            "posterior_predictive": {
                "replicated_event_counts": {
                    "likelihood": "expanded piecewise-Poisson event counts",
                    "n_posterior_draws": 100,
                    "total": {
                        "observed": 4.0,
                        "replicated_mean": 4.2,
                        "replicated_median": 4.0,
                        "replicated_lower_95": 1.0,
                        "replicated_upper_95": 8.0,
                        "posterior_predictive_tail_probability": 0.6,
                        "observed_covered": True,
                    },
                    "by_baseline_interval": [
                        {
                            "interval": 1,
                            "observed": 4.0,
                            "replicated_mean": 4.2,
                            "replicated_median": 4.0,
                            "replicated_lower_95": 1.0,
                            "replicated_upper_95": 8.0,
                            "posterior_predictive_tail_probability": 0.6,
                            "observed_covered": True,
                        }
                    ],
                },
                "fitted_survival_check": [
                    {
                        "time": 5.0,
                        "observed_km": 0.5,
                        "predicted_mean": 0.55,
                        "lower_95": 0.4,
                        "upper_95": 0.7,
                        "observed_covered": True,
                    }
                ],
            },
            "posterior_trace_snapshot": {
                "purpose": "visualisation_only_full_trace_used_for_numeric_diagnostics",
                "draw_indices": [0, 2, 4],
                "variables": {
                    "beta": {
                        "dims": ["chain", "draw", "beta_dim_0"],
                        "values": [
                            [[0.0], [0.1], [0.2]],
                            [[0.05], [0.15], [0.25]],
                        ],
                    },
                    "log_lambda": {
                        "dims": ["chain", "draw", "log_lambda_dim_0"],
                        "values": [
                            [[-1.0], [-0.9], [-0.8]],
                            [[-1.1], [-1.0], [-0.9]],
                        ],
                    },
                },
            },
        }
    else:
        cell["fit_attempts"] = [{"attempt": 1, "fit_seconds": 0.08}]
        cell["model_details"] = {
            "ph_test": [
                {
                    "feature": "age",
                    "test_statistic": 0.5,
                    "p": 0.48,
                    "holm_adjusted_p": 0.48,
                    "holm_reject_0_05": False,
                }
            ]
        }
    cell["cell_content_sha256"] = _canonical(cell)
    return cell


def _make_run(root: Path, *, mode: str = "confirmatory") -> Path:
    run_dir = root / f"toy_{mode}"
    models = ["cox_ph", "bayesian_normal"]
    run_config = {
        "mode": mode,
        "datasets": ["toy"],
        "models": models,
        "outer_repeats": 1,
        "outer_splits": 1,
        "fold_limit_per_dataset": None if mode == "confirmatory" else 1,
        "protocol": {"design_status": "frozen_after_rehearsal"},
    }
    dependencies: dict[str, str] = {}
    manifest: dict[str, Any] = {
        "schema_version": "1.0.0",
        "run_config": run_config,
        "config_sha256": _canonical(run_config),
        "input_sha256": {},
        "environment": {
            "dependencies": dependencies,
            "dependency_set_sha256": _canonical(dependencies),
        },
    }
    if mode == "confirmatory":
        manifest["protocol_freeze_sha256"] = "f" * 64
    manifest["manifest_content_sha256"] = _canonical(manifest)
    _write_json(run_dir / "manifest.json", manifest)

    cells = [_cell(model, mode=mode) for model in models]
    inventory: dict[str, str] = {}
    metric_rows = []
    for cell in cells:
        relative = f"cells/toy/repeat_01_fold_01/{cell['model_key']}.json"
        path = run_dir / relative
        _write_json(path, cell)
        inventory[relative] = _file_hash(path)
        metric_rows.append(
            {
                "dataset": "toy",
                "model_key": cell["model_key"],
                "repeat": 1,
                "fold": 1,
                "cell_content_sha256": cell["cell_content_sha256"],
            }
        )
    pd.DataFrame(metric_rows).to_csv(run_dir / "fold_metrics.csv", index=False)
    with gzip.GzipFile(
        filename=str(run_dir / "out_of_fold_predictions.csv.gz"),
        mode="wb",
        mtime=0,
    ) as handle:
        handle.write(b"dataset,subject_id\ntoy,s8\n")
    inference = {
        "status": "incomplete",
        "holm_family_complete": False,
        "primary": [],
        "secondary_estimation": [],
    }
    _write_json(run_dir / "inference.json", inference)
    aggregate = {
        name: _file_hash(run_dir / name)
        for name in (
            "fold_metrics.csv",
            "out_of_fold_predictions.csv.gz",
            "inference.json",
        )
    }
    completion: dict[str, Any] = {
        "schema_version": "1.0.0",
        "analysis_mode": mode,
        "planned_cells_in_this_invocation": 2,
        "stored_cells": 2,
        "status_counts": {"complete": 2},
        "all_stored_cell_hashes": inventory,
        "aggregate_sha256": aggregate,
    }
    completion["completion_content_sha256"] = _canonical(completion)
    _write_json(run_dir / "completion.json", completion)
    return run_dir


def test_renderer_has_no_model_import_or_fit_call() -> None:
    tree = ast.parse(RENDERER_PATH.read_text(encoding="utf-8"))
    imported = []
    fitted = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "fit"
        ):
            fitted.append(node.lineno)
    assert not [name for name in imported if name.startswith("src.models")]
    assert not [name for name in imported if name.startswith("src.pipelines")]
    assert not fitted


def test_confirmatory_render_is_complete_lineaged_and_deterministic(
    tmp_path: Path,
) -> None:
    module = _renderer()
    run_dir = _make_run(tmp_path / "source")
    first = module.render_run(run_dir, tmp_path / "render_a")
    second = module.render_run(run_dir, tmp_path / "render_b")

    first_files = {
        str(path.relative_to(first)): _file_hash(path)
        for path in first.rglob("*")
        if path.is_file()
    }
    second_files = {
        str(path.relative_to(second)): _file_hash(path)
        for path in second.rglob("*")
        if path.is_file()
    }
    assert first_files == second_files
    lineage = json.loads((first / "lineage.json").read_text(encoding="utf-8"))
    mapped = {row["path"] for row in lineage["outputs"]}
    assert mapped == set(first_files) - {"lineage.json"}
    assert lineage["evidence_status"] == "confirmatory"
    assert (first / "figures" / "calibration_curves.pdf").is_file()
    assert (first / "figures" / "paired_ibs_effects.png").is_file()
    assert (first / "tables" / "posterior_trace_snapshot_inventory.csv").is_file()


def test_tampered_cell_is_rejected_before_output(tmp_path: Path) -> None:
    module = _renderer()
    run_dir = _make_run(tmp_path / "source")
    cell_path = run_dir / "cells" / "toy" / "repeat_01_fold_01" / "cox_ph.json"
    cell_path.write_text(cell_path.read_text(encoding="utf-8") + " ", encoding="utf-8")
    output = tmp_path / "render"
    with pytest.raises(RuntimeError, match="file hash"):
        module.render_run(run_dir, output)
    assert not output.exists()


def test_verified_optional_explanation_is_rendered_and_tamper_is_rejected(
    tmp_path: Path,
) -> None:
    module = _renderer()
    run_dir = _make_run(tmp_path / "source")
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    completion = json.loads((run_dir / "completion.json").read_text(encoding="utf-8"))
    artifact: dict[str, Any] = {
        "schema_version": "1.0.0",
        "analysis": "confirmatory_explainability_from_frozen_cells",
        "analysis_mode": "confirmatory",
        "evidence_status": "confirmatory",
        "source_run": {
            "directory_name": run_dir.name,
            "manifest_content_sha256": manifest["manifest_content_sha256"],
            "completion_content_sha256": completion["completion_content_sha256"],
            "cell_content_hashes_used": {},
        },
        "agreement_uncertainty": [],
        "group_stability": [],
        "convergence": {"summary": {"status": "not_evaluable"}},
        "secondary_cross_model_analysis": {"cox_ph": {"paired_same_model_minus_cox": []}},
    }
    artifact["result_content_sha256"] = _canonical(artifact)
    artifact_path = tmp_path / "explanation.json"
    _write_json(artifact_path, artifact)

    output = module.render_run(
        run_dir,
        tmp_path / "render",
        explainability_artifact=artifact_path,
    )
    assert (output / "tables" / "explanation_agreement.csv").is_file()
    assert (output / "figures" / "explanation_stability.pdf").is_file()

    artifact_path.write_text(
        artifact_path.read_text(encoding="utf-8").replace("not_evaluable", "passed"),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="content hash|does not match"):
        module.render_run(
            run_dir,
            tmp_path / "tampered_render",
            explainability_artifact=artifact_path,
        )
    assert not (tmp_path / "tampered_render").exists()


def test_rehearsal_renders_runtime_only_and_optional_inputs_are_not_required(
    tmp_path: Path,
) -> None:
    module = _renderer()
    run_dir = _make_run(tmp_path / "source", mode="rehearsal")
    output = module.render_run(run_dir, tmp_path / "render")
    files = {str(path.relative_to(output)) for path in output.rglob("*") if path.is_file()}
    assert "RUNTIME_ONLY_README.txt" in files
    assert "figures/runtime_diagnostic_failures.pdf" in files
    assert not any("calibration" in name or "fold_metric" in name for name in files)
    notice = (output / "RUNTIME_ONLY_README.txt").read_text(encoding="utf-8")
    assert "NOT CONFIRMATORY EVIDENCE" in notice


def test_rehearsal_refuses_explanation_artifact(tmp_path: Path) -> None:
    module = _renderer()
    run_dir = _make_run(tmp_path / "source", mode="rehearsal")
    with pytest.raises(ValueError, match="rehearsal rendering"):
        module.render_run(
            run_dir,
            tmp_path / "render",
            explainability_artifact=tmp_path / "missing.json",
        )
    assert not (tmp_path / "render").exists()
