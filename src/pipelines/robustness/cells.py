"""Fit, evaluate and validate individual immutable robustness cells."""

from __future__ import annotations

import time
import traceback
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.data.fold_preprocessing import FoldFeaturePreprocessor
from src.data.survival_folds import (
    SurvivalFold,
)
from src.pipelines.confirmatory import (
    DiagnosticFailure,
    RunOptions,
    _fit_with_diagnostic_rule,
    administratively_truncate_for_ipcw,
    deterministic_seed,
)
from src.utils.io import json_safe as _json_safe
from src.utils.io import read_mapping
from src.utils.reproducibility import (
    canonical_json_hash,
)

from .conditions import (
    _condition_config,
    apply_administrative_censoring,
    effective_information_ratio,
)
from .evaluation import (
    evaluate_robustness_predictions,
    individual_integrated_brier_losses,
    summarize_imputation_predictions,
)
from .imputation import _MultipleImputationPredictionEnsemble, multiple_imputed_fold_frames
from .protocol import (
    BAYESIAN_MODEL_KEYS,
    MULTIPLE_IMPUTATIONS,
    RobustnessCondition,
    RobustnessOptions,
)


def run_robustness_cell(
    dataset_key: str,
    model_key: str,
    fold: SurvivalFold,
    condition: RobustnessCondition,
    raw: pd.DataFrame,
    times: np.ndarray,
    events: np.ndarray,
    subject_ids: np.ndarray,
    feature_spec: dict[str, Any],
    train_indices: np.ndarray,
    censoring_cutoff: float | None,
    *,
    config: dict[str, Any],
    options: RobustnessOptions,
    data_sha256: str,
) -> dict[str, Any]:
    """Fit and evaluate one content-addressed Bayesian robustness cell."""
    started = time.perf_counter()
    validation_indices = fold.validation_indices
    train_time, train_event = apply_administrative_censoring(
        times[train_indices], events[train_indices], censoring_cutoff
    )
    validation_time, validation_event = apply_administrative_censoring(
        times[validation_indices], events[validation_indices], censoring_cutoff
    )
    seed = deterministic_seed(
        int(config["validation"]["base_seed"]),
        "robustness",
        dataset_key,
        fold.repeat,
        fold.fold,
        condition.condition_id,
        model_key,
    )
    subset_hash = canonical_json_hash(subject_ids[train_indices].tolist())
    outcome_hash = canonical_json_hash(
        {
            "train_time": train_time.tolist(),
            "train_event": train_event.tolist(),
            "validation_time": validation_time.tolist(),
            "validation_event": validation_event.tolist(),
        }
    )
    base: dict[str, Any] = {
        "schema_version": "1.0.0",
        "analysis_id": f"{config['analysis_id']}_robustness",
        "analysis_mode": options.mode,
        "evidence_status": (
            "frozen_robustness" if options.mode == "robustness" else "rehearsal_only"
        ),
        "dataset": dataset_key,
        "dataset_sha256": data_sha256,
        "model_key": model_key,
        "prior": model_key.removeprefix("bayesian_"),
        "repeat": fold.repeat,
        "fold": fold.fold,
        "fold_seed": fold.seed,
        "cell_seed": seed,
        "condition": condition.to_dict(),
        "train_subject_ids": subject_ids[train_indices],
        "validation_subject_ids": subject_ids[validation_indices],
        "training_subset_sha256": subset_hash,
        "modified_outcomes_sha256": outcome_hash,
        "n_train": len(train_indices),
        "n_validation": len(validation_indices),
        "events_train": int(train_event.sum()),
        "events_validation": int(validation_event.sum()),
        "processed_feature_degrees_of_freedom": None,
        "effective_information_events_per_degree_of_freedom": None,
        "original_events_validation": events[validation_indices],
        "administrative_cutoff": censoring_cutoff,
    }
    minimum_events = int(config["robustness"]["minimum_training_events"])
    if int(train_event.sum()) < minimum_events:
        base.update(
            {
                "status": "unavailable_minimum_training_events",
                "minimum_training_events": minimum_events,
                "message": (
                    f"condition has {int(train_event.sum())} training events; "
                    f"at least {minimum_events} are required"
                ),
                "total_seconds": time.perf_counter() - started,
            }
        )
        base["cell_content_sha256"] = canonical_json_hash(_json_safe(base))
        return base

    try:
        fit_config = _condition_config(config, condition)
        confirmatory_options = RunOptions(
            mode="confirmatory" if options.mode == "robustness" else "rehearsal",
            datasets=(dataset_key,),
            models=(model_key,),
            outer_splits=options.outer_splits,
            outer_repeats=options.outer_repeats,
            fold_limit_per_dataset=None,
            bayes_draws=options.bayes_draws,
            bayes_tune=options.bayes_tune,
            bayes_chains=options.bayes_chains,
            calibration_bootstraps=0,
            resume=options.resume,
            output_root=options.output_root,
        )
        if condition.imputation_method == "iterative_posterior_m5":
            imputation_seeds = [
                deterministic_seed(seed, "imputation", number)
                for number in range(1, MULTIPLE_IMPUTATIONS + 1)
            ]
            imputed = multiple_imputed_fold_frames(
                raw.iloc[train_indices],
                raw.iloc[validation_indices],
                feature_spec,
                seeds=imputation_seeds,
            )
            models: list[Any] = []
            x_validations: list[pd.DataFrame] = []
            preprocessing_records: list[dict[str, Any]] = []
            fit_records: list[dict[str, Any]] = []
            for number, (
                imputed_train,
                imputed_validation,
                imputation_metadata,
            ) in enumerate(imputed, start=1):
                processor = FoldFeaturePreprocessor(feature_spec)
                x_train = processor.fit_transform(imputed_train)
                x_validation = processor.transform(imputed_validation)
                try:
                    model, attempts = _fit_with_diagnostic_rule(
                        model_key,
                        {},
                        x_train,
                        train_time,
                        train_event,
                        seed=deterministic_seed(seed, "imputed_fit", number),
                        config=fit_config,
                        options=confirmatory_options,
                    )
                except DiagnosticFailure as exc:
                    tagged = [{"imputation": number, **attempt} for attempt in exc.attempts]
                    raise DiagnosticFailure(tagged) from exc
                models.append(model)
                x_validations.append(x_validation)
                preprocessing_records.append(
                    {
                        "imputation": imputation_metadata,
                        "fold_preprocessor": processor.metadata(),
                    }
                )
                fit_records.append(
                    {
                        "imputation": number,
                        "imputation_seed": imputation_seeds[number - 1],
                        "attempts": attempts,
                    }
                )
            feature_schemas = [tuple(frame.columns) for frame in x_validations]
            if any(schema != feature_schemas[0] for schema in feature_schemas[1:]):
                raise RuntimeError("multiple-imputation transformed feature schemas do not match")
            transformed_columns = len(feature_schemas[0])
            ensemble = _MultipleImputationPredictionEnsemble(models, x_validations)
            metrics, predictions = evaluate_robustness_predictions(
                ensemble,
                x_validations[0],
                train_time,
                train_event,
                validation_time,
                validation_event,
                evaluation_config=config["evaluation"],
            )
            imputation_metrics: list[dict[str, Any]] = []
            for number, (model, x_validation) in enumerate(
                zip(models, x_validations, strict=True), start=1
            ):
                risk = np.asarray(model.predict_risk(x_validation), dtype=float)
                grid_survival = np.asarray(
                    model.predict_survival(x_validation, predictions["ibs_grid"]),
                    dtype=float,
                )
                imputation_metric = summarize_imputation_predictions(
                    train_time,
                    train_event,
                    validation_time,
                    validation_event,
                    risk,
                    grid_survival,
                    predictions["ibs_grid"],
                    predictions["horizons"],
                )
                imputation_metrics.append(
                    {
                        "imputation": number,
                        **imputation_metric,
                    }
                )
            preprocessing: dict[str, Any] = {
                "method": "five-fold-local-multiple-imputation prediction ensemble",
                "imputations": preprocessing_records,
            }
            attempts_output: list[dict[str, Any]] = fit_records
            model_details: dict[str, Any] = {
                "combination_rule": (
                    "arithmetic mean of imputation-specific risk and survival "
                    "predictions; pooled metrics are recomputed from those predictions"
                ),
                "per_imputation_metrics": imputation_metrics,
                "per_imputation_diagnostics": [
                    {
                        "imputation": number,
                        "diagnostics": model.diagnostics,
                        "prior_predictive": model.prior_predictive_summary,
                        "posterior_predictive": model.posterior_predictive_summary,
                        "time_scale": model.time_scale,
                    }
                    for number, model in enumerate(models, start=1)
                ],
                "posterior_uncertainty_statement": (
                    "The five posterior fits and prediction ensemble represent "
                    "imputation sensitivity; they do not form one Bayesian posterior "
                    "that propagates covariate-imputation uncertainty."
                ),
                "n_intervals": condition.n_intervals,
                "prior_parameters": fit_config["models"]["bayesian_cox"]["priors"][
                    model_key.removeprefix("bayesian_")
                ]["prior_params"],
            }
        else:
            processor = FoldFeaturePreprocessor(feature_spec)
            x_train = processor.fit_transform(raw.iloc[train_indices])
            x_validation = processor.transform(raw.iloc[validation_indices])
            model, attempts = _fit_with_diagnostic_rule(
                model_key,
                {},
                x_train,
                train_time,
                train_event,
                seed=seed,
                config=fit_config,
                options=confirmatory_options,
            )
            metrics, predictions = evaluate_robustness_predictions(
                model,
                x_validation,
                train_time,
                train_event,
                validation_time,
                validation_event,
                evaluation_config=config["evaluation"],
            )
            preprocessing = processor.metadata()
            attempts_output = attempts
            model_details = {
                "diagnostics": model.diagnostics,
                "prior_predictive": model.prior_predictive_summary,
                "posterior_predictive": model.posterior_predictive_summary,
                "time_scale": model.time_scale,
                "n_intervals": condition.n_intervals,
                "prior_parameters": fit_config["models"]["bayesian_cox"]["priors"][
                    model_key.removeprefix("bayesian_")
                ]["prior_params"],
            }
            transformed_columns = len(x_train.columns)
        losses = individual_integrated_brier_losses(
            train_time,
            train_event,
            validation_time,
            validation_event,
            predictions["survival_on_ibs_grid"],
            predictions["ibs_grid"],
        )
        if not np.isclose(float(np.mean(losses)), float(metrics["ibs"]), atol=1e-12):
            raise RuntimeError("individual IBS contributions do not match reference IBS")
        ipcw_time, ipcw_event = administratively_truncate_for_ipcw(
            validation_time,
            validation_event,
            float(predictions["horizons"][-1]),
        )
        base.update(
            {
                "status": "complete",
                "tuning": "none_prespecified_robustness_configuration",
                "processed_feature_degrees_of_freedom": transformed_columns,
                "effective_information_events_per_degree_of_freedom": (
                    effective_information_ratio(int(train_event.sum()), transformed_columns)
                ),
                "fit_attempts": attempts_output,
                "preprocessing": preprocessing,
                "metrics": metrics,
                "individual_ibs_loss": losses,
                "predictions": {
                    **predictions,
                    "subject_ids": subject_ids[validation_indices],
                    "observed_time": validation_time,
                    "observed_event": validation_event,
                    "ipcw_evaluation_time": ipcw_time,
                    "ipcw_evaluation_event": ipcw_event,
                },
                "model_details": model_details,
            }
        )
    except DiagnosticFailure as exc:
        base.update(
            {
                "status": "failed_diagnostics",
                "fit_attempts": exc.attempts,
                "error_type": type(exc).__name__,
                "message": str(exc),
            }
        )
    except Exception as exc:
        base.update(
            {
                "status": "failed",
                "error_type": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc(),
            }
        )
    base["total_seconds"] = time.perf_counter() - started
    base["cell_content_sha256"] = canonical_json_hash(_json_safe(base))
    return base


def validate_robustness_cell(cell: dict[str, Any]) -> None:
    """Validate the common schema and content hash of a stored cell."""
    required = {
        "schema_version",
        "analysis_id",
        "analysis_mode",
        "dataset",
        "dataset_sha256",
        "model_key",
        "prior",
        "repeat",
        "fold",
        "condition",
        "training_subset_sha256",
        "modified_outcomes_sha256",
        "n_train",
        "n_validation",
        "events_train",
        "processed_feature_degrees_of_freedom",
        "effective_information_events_per_degree_of_freedom",
        "status",
        "cell_content_sha256",
    }
    missing = sorted(required - set(cell))
    if missing:
        raise ValueError(f"robustness cell is missing required keys: {missing}")
    if cell["model_key"] not in BAYESIAN_MODEL_KEYS:
        raise ValueError("robustness cell has an unknown Bayesian model key")
    condition = cell["condition"]
    for key in (
        "condition_id",
        "analyses",
        "feature_set",
        "training_fraction",
        "censoring_name",
        "prior_scenario",
        "n_intervals",
        "imputation_method",
    ):
        if key not in condition:
            raise ValueError(f"robustness condition is missing {key!r}")
    unhashed = dict(cell)
    claimed = unhashed.pop("cell_content_sha256")
    if claimed != canonical_json_hash(unhashed):
        raise ValueError("robustness cell content hash does not match")
    if cell["status"] == "complete":
        degrees = int(cell["processed_feature_degrees_of_freedom"])
        observed = float(cell["effective_information_events_per_degree_of_freedom"])
        expected = effective_information_ratio(int(cell["events_train"]), degrees)
        if not np.isclose(observed, expected, atol=1e-12):
            raise ValueError("effective-information ratio does not match events/df")


def _cell_path(
    run_dir: Path,
    dataset: str,
    fold: SurvivalFold,
    condition: RobustnessCondition,
    model_key: str,
) -> Path:
    return (
        run_dir
        / "cells"
        / dataset
        / f"repeat_{fold.repeat:02d}_fold_{fold.fold:02d}"
        / condition.condition_id
        / f"{model_key}.json"
    )


def load_robustness_cells(run_dir: Path) -> list[dict[str, Any]]:
    """Load cells only after validating their declared content hashes."""
    cells: list[dict[str, Any]] = []
    for path in sorted((run_dir / "cells").glob("*/*/*/*.json")):
        cell = read_mapping(path)
        validate_robustness_cell(cell)
        cells.append(cell)
    return cells
