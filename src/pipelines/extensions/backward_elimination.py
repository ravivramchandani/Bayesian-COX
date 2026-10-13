"""Nested, grouped backward elimination for a post-hoc Cox comparison.

Selection uses inner-fold IPCW integrated Brier scores on outer-training data.
The caller must run this selector separately inside each outer fold and retain
the returned selection record with that fold's result.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning

from src.data.fold_preprocessing import FoldFeaturePreprocessor
from src.data.survival_folds import repeated_survival_folds
from src.evaluation.metrics import integrated_brier
from src.models.cox import CoxPHModel
from src.pipelines.confirmatory.evaluation import (
    administratively_truncate_for_ipcw,
    evaluation_horizons_and_grid,
    validate_survival_prediction_matrix,
)


@dataclass(frozen=True)
class _InnerFoldData:
    """Training-only transforms and outcomes for one inner validation fold."""

    train_x: pd.DataFrame
    validation_x: pd.DataFrame
    feature_groups: dict[str, str]
    train_time: np.ndarray
    train_event: np.ndarray
    validation_time: np.ndarray
    validation_ipcw_time: np.ndarray
    validation_ipcw_event: np.ndarray
    evaluation_grid: np.ndarray


@dataclass(frozen=True)
class BackwardEliminationCoxFit:
    """Fitted outer-fold Cox model and its fold-local selection artefacts."""

    model: CoxPHModel
    preprocessor: FoldFeaturePreprocessor
    selection: dict[str, Any]
    training_features: pd.DataFrame
    validation_features: pd.DataFrame


def _declared_group_order(feature_spec: dict[str, Any]) -> list[str]:
    """Return the preprocessor's declared source-group order."""
    groups = list(feature_spec.get("numeric", []))
    groups.extend(
        " + ".join(declaration.get("source_features", []))
        or declaration["name"]
        for declaration in feature_spec.get("engineered", [])
    )
    groups.extend(feature_spec.get("ordinal", {}).keys())
    groups.extend(feature_spec.get("categorical", []))
    return list(dict.fromkeys(str(group) for group in groups))


def backward_elimination(
    raw_training: pd.DataFrame,
    time: np.ndarray,
    event: np.ndarray,
    feature_spec: dict[str, Any],
    evaluation_config: dict[str, Any],
    *,
    seed: int,
    l2_reg: float = 1e-4,
    n_splits: int = 3,
) -> dict[str, Any]:
    """Select a nested, greedy backward path of Cox feature groups.

    At each step, score removing each remaining source-feature group by mean
    IPCW integrated Brier score over deterministic inner survival folds. Stop
    at one group, then select the smallest path model within one fold standard
    error of the best mean score. All preprocessing and selection use only
    ``raw_training``; callers must not pass outer-validation rows.

    Args:
        raw_training: Raw rows from one outer-training fold only.
        time: Follow-up times aligned to ``raw_training``.
        event: Binary event indicators aligned to ``raw_training``.
        feature_spec: The cohort's declared feature set.
        evaluation_config: Frozen training-derived horizon and IPCW settings.
        seed: Explicit cell-specific seed for deterministic inner-fold
            construction, derived from the outer-fold identity.
        l2_reg: Fixed Cox ridge penalty used for every path candidate.
        n_splits: Number of inner folds; must be the protocol's three folds.

    Returns:
        A JSON-compatible selection record with the complete greedy path,
        candidate scores/failures at every step, and the selected groups.

    Raises:
        ValueError: Inputs/settings are invalid or no source group can be evaluated.
        RuntimeError: No path model completes all inner-fold scores.
    """
    times = np.asarray(time, dtype=float)
    try:
        raw_events = np.asarray(event, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError("event must contain binary 0/1 values") from exc
    if times.ndim != 1 or raw_events.ndim != 1 or len(raw_training) != len(times):
        raise ValueError("raw rows, time and event must be aligned one-dimensional data")
    if len(times) != len(raw_events):
        raise ValueError("time and event must have equal lengths")
    if not np.isfinite(raw_events).all() or not np.isin(raw_events, (0, 1)).all():
        raise ValueError("event must contain only binary 0/1 values")
    events = raw_events.astype(int)
    if not np.isfinite(l2_reg) or l2_reg < 0:
        raise ValueError("l2_reg must be finite and non-negative")
    if float(l2_reg) != 1e-4:
        raise ValueError("the frozen analysis fixes the Cox penalty at 1e-4")
    if n_splits != 3:
        raise ValueError("the frozen analysis fixes three inner folds")

    folds = repeated_survival_folds(
        times,
        events,
        n_splits=n_splits,
        n_repeats=1,
        base_seed=int(seed),
        max_time_bins=4,
    )
    inner_data: list[_InnerFoldData] = []
    observed_groups: set[str] = set()
    for fold in folds:
        train_rows = raw_training.iloc[fold.train_indices]
        validation_rows = raw_training.iloc[fold.validation_indices]
        processor = FoldFeaturePreprocessor(feature_spec)
        train_x = processor.fit_transform(train_rows)
        validation_x = processor.transform(validation_rows)
        missing_groups = set(train_x.columns).difference(processor.feature_groups)
        if missing_groups:
            raise ValueError(
                "preprocessor omitted feature-group metadata: "
                f"{sorted(missing_groups)}"
            )
        observed_groups.update(
            processor.feature_groups[column]
            for column in train_x.columns
            if float(np.std(train_x[column].to_numpy(dtype=float))) > 1e-12
        )

        train_time = times[fold.train_indices]
        train_event = events[fold.train_indices]
        validation_time = times[fold.validation_indices]
        validation_event = events[fold.validation_indices]
        _, grid = evaluation_horizons_and_grid(
            train_time, train_event, evaluation_config
        )
        validation_ipcw_time, validation_ipcw_event = (
            administratively_truncate_for_ipcw(
                validation_time, validation_event, float(grid[-1])
            )
        )
        inner_data.append(
            _InnerFoldData(
                train_x=train_x,
                validation_x=validation_x,
                feature_groups=dict(processor.feature_groups),
                train_time=train_time,
                train_event=train_event,
                validation_time=validation_time,
                validation_ipcw_time=validation_ipcw_time,
                validation_ipcw_event=validation_ipcw_event,
                evaluation_grid=grid,
            )
        )

    group_order = [
        group for group in _declared_group_order(feature_spec) if group in observed_groups
    ]
    if not group_order:
        raise ValueError("no varying feature groups are available for selection")

    def score_groups(groups: Sequence[str]) -> dict[str, Any]:
        scores: list[float] = []
        failures: list[dict[str, Any]] = []
        fold_warnings: list[dict[str, Any]] = []
        for fold_index, fold_data in enumerate(inner_data, start=1):
            warning_messages: list[str] = []
            columns = [
                column
                for column in fold_data.train_x.columns
                if fold_data.feature_groups[column] in groups
                and float(
                    np.std(fold_data.train_x[column].to_numpy(dtype=float))
                )
                > 1e-12
            ]
            if not columns:
                failures.append(
                    {
                        "fold": fold_index,
                        "type": "NoVaryingFeatures",
                        "message": "candidate has no varying columns in this inner training fold",
                    }
                )
                continue
            try:
                model = CoxPHModel(l2_reg=l2_reg, random_state=int(seed))
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    try:
                        model.fit(
                            fold_data.train_x[columns],
                            fold_data.train_time,
                            fold_data.train_event,
                        )
                    finally:
                        warning_messages = [str(warning.message) for warning in caught]
                convergence = [
                    message
                    for message, warning in zip(warning_messages, caught, strict=True)
                    if issubclass(warning.category, ConvergenceWarning)
                    or "converg" in warning.category.__name__.lower()
                ]
                if convergence:
                    raise RuntimeError("; ".join(convergence))
                survival = model.predict_survival(
                    fold_data.validation_x[columns], fold_data.evaluation_grid
                )
                validate_survival_prediction_matrix(
                    survival,
                    n_samples=len(fold_data.validation_time),
                    n_times=len(fold_data.evaluation_grid),
                )
                scores.append(
                    integrated_brier(
                        fold_data.train_time,
                        fold_data.train_event,
                        fold_data.validation_ipcw_time,
                        fold_data.validation_ipcw_event,
                        survival,
                        fold_data.evaluation_grid,
                    )
                )
                fold_warnings.append(
                    {"fold": fold_index, "warnings": warning_messages}
                )
            except Exception as exc:
                failures.append(
                    {
                        "fold": fold_index,
                        "type": type(exc).__name__,
                        "message": str(exc),
                        "warnings": warning_messages,
                    }
                )

        complete = len(scores) == n_splits and not failures
        mean_score = float(np.mean(scores)) if complete else None
        standard_error = (
            float(np.std(scores, ddof=1) / np.sqrt(len(scores)))
            if complete and len(scores) > 1
            else None
        )
        return {
            "groups": list(groups),
            "n_groups": len(groups),
            "fold_scores": scores,
            "fold_warnings": fold_warnings,
            "mean_ipcw_ibs": mean_score,
            "fold_standard_error": standard_error,
            "failures": failures,
        }

    path: list[dict[str, Any]] = []
    elimination_steps: list[dict[str, Any]] = []
    active = tuple(group_order)
    initial = score_groups(active)
    path.append({"step": 0, "removed_group": None, **initial})

    while len(active) > 1:
        candidates: list[dict[str, Any]] = []
        for removed_group in active:
            remaining = tuple(group for group in active if group != removed_group)
            candidates.append(
                {"removed_group": removed_group, **score_groups(remaining)}
            )
        eligible = [
            candidate
            for candidate in candidates
            if candidate["mean_ipcw_ibs"] is not None
        ]
        if not eligible:
            elimination_steps.append(
                {
                    "groups_before": list(active),
                    "candidates": candidates,
                    "selected_candidate": None,
                }
            )
            break
        chosen = min(
            eligible,
            key=lambda candidate: (
                float(candidate["mean_ipcw_ibs"]),
                tuple(group_order.index(group) for group in candidate["groups"]),
            ),
        )
        active = tuple(chosen["groups"])
        path.append(
            {
                "step": len(path),
                "removed_group": chosen["removed_group"],
                **{key: value for key, value in chosen.items() if key != "removed_group"},
            }
        )
        elimination_steps.append(
            {
                "groups_before": list(path[-2]["groups"]),
                "candidates": candidates,
                "selected_candidate": chosen["removed_group"],
            }
        )

    scored_path = [state for state in path if state["mean_ipcw_ibs"] is not None]
    if not scored_path:
        raise RuntimeError("no backward-elimination path model passed all inner folds")
    best = min(scored_path, key=lambda state: (state["mean_ipcw_ibs"], state["step"]))
    threshold = float(best["mean_ipcw_ibs"]) + float(best["fold_standard_error"])
    within_one_se = [
        state for state in scored_path if float(state["mean_ipcw_ibs"]) <= threshold
    ]
    selected = min(
        within_one_se,
        key=lambda state: (state["n_groups"], state["mean_ipcw_ibs"], state["step"]),
    )
    return {
        "method": "greedy_grouped_backward_elimination",
        "selection_metric": "mean inner-fold IPCW integrated Brier score",
        "selection_rule": (
            "smallest path model within one fold standard error of the minimum"
        ),
        "cox_l2_reg": float(l2_reg),
        "seed": int(seed),
        "n_splits": int(n_splits),
        "initial_groups": group_order,
        "path": path,
        "elimination_steps": elimination_steps,
        "best_path_step": int(best["step"]),
        "one_se_threshold": threshold,
        "selected_step": int(selected["step"]),
        "selected_groups": list(selected["groups"]),
        "selected_inner_mean_ipcw_ibs": float(selected["mean_ipcw_ibs"]),
    }


def select_feature_columns(
    features: pd.DataFrame,
    feature_groups: Mapping[str, str],
    selected_groups: Sequence[str],
) -> pd.DataFrame:
    """Keep all encoded columns belonging to selected source-feature groups.

    Args:
        features: A matrix transformed by the outer-training preprocessor.
        feature_groups: Its column-to-source-group mapping.
        selected_groups: Groups returned by :func:`backward_elimination`.

    Returns:
        A copy containing selected columns in their original feature order.

    Raises:
        ValueError: A selected group is absent or no columns remain.
    """
    selected = set(selected_groups)
    if not selected:
        raise ValueError("selected_groups must not be empty")
    missing_metadata = set(features.columns).difference(feature_groups)
    if missing_metadata:
        raise ValueError(
            f"feature-group metadata is missing columns: {sorted(missing_metadata)}"
        )
    columns = [
        column for column in features.columns if feature_groups[column] in selected
    ]
    present = {feature_groups[column] for column in columns}
    missing_groups = selected.difference(present)
    if missing_groups or not columns:
        raise ValueError(
            f"selected groups are absent from transformed features: {sorted(missing_groups)}"
        )
    return features.loc[:, columns].copy()


def fit_backward_elimination_cox(
    raw_training: pd.DataFrame,
    raw_validation: pd.DataFrame,
    train_time: np.ndarray,
    train_event: np.ndarray,
    feature_spec: dict[str, Any],
    evaluation_config: dict[str, Any],
    *,
    seed: int,
    l2_reg: float = 1e-4,
    n_splits: int = 3,
) -> BackwardEliminationCoxFit:
    """Select features inside an outer-training fold and fit its Cox model.

    Validation outcomes are intentionally not accepted by this function.

    Args:
        raw_training: Raw rows from the outer-training fold.
        raw_validation: Raw predictors from its held-out fold.
        train_time: Follow-up times aligned to ``raw_training``.
        train_event: Event indicators aligned to ``raw_training``.
        feature_spec: The cohort's declared feature set.
        evaluation_config: Frozen training-derived horizon and IPCW settings.
        seed: Explicit cell-specific seed derived from the outer-fold identity.
        l2_reg: Fixed Cox ridge penalty used for selection and final fit.
        n_splits: Number of inner folds; must be the protocol's three folds.

    Returns:
        The fitted Cox model, outer-training preprocessor, full selection
        record, and selected training/validation matrices.
    """
    selection = backward_elimination(
        raw_training,
        train_time,
        train_event,
        feature_spec,
        evaluation_config,
        seed=seed,
        l2_reg=l2_reg,
        n_splits=n_splits,
    )
    preprocessor = FoldFeaturePreprocessor(feature_spec).fit(raw_training)
    training_features = select_feature_columns(
        preprocessor.transform(raw_training),
        preprocessor.feature_groups,
        selection["selected_groups"],
    )
    validation_features = select_feature_columns(
        preprocessor.transform(raw_validation),
        preprocessor.feature_groups,
        selection["selected_groups"],
    )
    model = CoxPHModel(l2_reg=l2_reg, random_state=int(seed))
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            model.fit(training_features, train_time, train_event)
        finally:
            fit_warnings = [str(warning.message) for warning in caught]
    convergence = [
        message
        for message, warning in zip(fit_warnings, caught, strict=True)
        if issubclass(warning.category, ConvergenceWarning)
        or "converg" in warning.category.__name__.lower()
    ]
    selection["outer_fit_warnings"] = fit_warnings
    if convergence:
        raise RuntimeError("; ".join(convergence))
    return BackwardEliminationCoxFit(
        model=model,
        preprocessor=preprocessor,
        selection=selection,
        training_features=training_features,
        validation_features=validation_features,
    )
