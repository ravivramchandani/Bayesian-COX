"""Fit and evaluate shallow trees that imitate a frozen RSF fold."""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import rankdata, spearmanr
from sklearn.model_selection import KFold
from sklearn.tree import DecisionTreeRegressor, export_text

from src.evaluation.metrics import harrell_c_index
from src.utils.reproducibility import canonical_json_hash, sha256_file

TREE_DEPTHS = (1, 2, 3, 4)
MIN_SAMPLES_LEAF_FRACTIONS = (0.05, 0.10, 0.20)
PROTOCOL_SHA256 = "291ad6843e96297717883e3d784503836e150b0e58e9a9314af14d4fef0c1bcf"
COHORTS = ("gbsg2", "whas500", "metabric")
PLANNED_FOLDS_PER_COHORT = 25


@dataclass(frozen=True)
class SurrogateFit:
    """Hold a fitted student tree and its training-only selection record."""

    estimator: DecisionTreeRegressor
    selection: dict[str, Any]


def fit_surrogate_tree(
    x_train: pd.DataFrame, teacher_train: np.ndarray, *, seed: int
) -> SurrogateFit:
    """Select and fit a shallow regression tree using outer-training data only.

    Args:
        x_train: Fold-preprocessed outer-training features.
        teacher_train: RSF risk scores for those same training subjects.
        seed: Explicit shuffle and tree seed for this outer fold.

    Returns:
        The final tree fitted on all outer-training rows and its inner-CV record.

    Raises:
        ValueError: Inputs are empty, misaligned, non-finite or have duplicate
            feature names.
        RuntimeError: No complexity candidate can be evaluated.
    """
    features = _feature_frame(x_train, name="outer-training features")
    target = _score_vector(teacher_train, len(features), name="training teacher scores")
    if len(features) < 3:
        raise ValueError("three inner folds require at least three training subjects")

    splitter = KFold(n_splits=3, shuffle=True, random_state=int(seed))
    candidates: list[dict[str, Any]] = []
    for depth in TREE_DEPTHS:
        for leaf_fraction in MIN_SAMPLES_LEAF_FRACTIONS:
            fold_errors: list[float] = []
            fold_leaves: list[int] = []
            for train_index, validation_index in splitter.split(features):
                model = DecisionTreeRegressor(
                    criterion="squared_error",
                    max_depth=depth,
                    min_samples_leaf=leaf_fraction,
                    max_features=None,
                    random_state=int(seed),
                )
                model.fit(features.iloc[train_index], target[train_index])
                residual = target[validation_index] - model.predict(
                    features.iloc[validation_index]
                )
                fold_errors.append(float(np.mean(np.square(residual))))
                fold_leaves.append(int(model.get_n_leaves()))
            mean_error = float(np.mean(fold_errors))
            standard_error = float(np.std(fold_errors, ddof=1) / np.sqrt(3.0))
            candidates.append(
                {
                    "max_depth": depth,
                    "min_samples_leaf": leaf_fraction,
                    "fold_mse": fold_errors,
                    "mean_mse": mean_error,
                    "standard_error": standard_error,
                    "mean_leaves": float(np.mean(fold_leaves)),
                }
            )

    if not candidates:
        raise RuntimeError("no surrogate-tree complexity candidates were evaluated")
    best = min(
        candidates,
        key=lambda row: (row["mean_mse"], row["max_depth"], -row["min_samples_leaf"]),
    )
    threshold = best["mean_mse"] + best["standard_error"]
    eligible = [row for row in candidates if row["mean_mse"] <= threshold]
    selected = min(
        eligible,
        key=lambda row: (row["max_depth"], -row["min_samples_leaf"], row["mean_mse"]),
    )
    estimator = DecisionTreeRegressor(
        criterion="squared_error",
        max_depth=int(selected["max_depth"]),
        min_samples_leaf=float(selected["min_samples_leaf"]),
        max_features=None,
        random_state=int(seed),
    )
    estimator.fit(features, target)
    return SurrogateFit(
        estimator=estimator,
        selection={
            "selection_metric": "three-fold mean squared error to RSF training risk",
            "minimum_mse_candidate": _selection_row(best),
            "one_standard_error_threshold": float(threshold),
            "selected_candidate": _selection_row(selected),
            "candidates": candidates,
            "seed": int(seed),
            "training_rows": int(len(features)),
        },
    )


def score_surrogate_fold(
    teacher_risk: np.ndarray,
    student_risk: np.ndarray,
    observed_time: np.ndarray,
    observed_event: np.ndarray,
) -> dict[str, Any]:
    """Measure fold-level teacher fidelity and survival performance separately.

    Args:
        teacher_risk: Replayed RSF risk scores on outer-validation subjects.
        student_risk: Student-tree risk estimates for those subjects.
        observed_time: Their observed follow-up times.
        observed_event: Their event indicators.

    Returns:
        Fidelity metrics, teacher/student Harrell concordance and their
        descriptive paired difference. Undefined metrics carry a reason.

    Raises:
        ValueError: Inputs are misaligned, empty, invalid or non-finite.
    """
    teacher = _score_vector(teacher_risk, None, name="validation teacher scores")
    student = _score_vector(student_risk, len(teacher), name="validation student scores")
    times = np.asarray(observed_time, dtype=float)
    events = np.asarray(observed_event, dtype=int)
    if times.ndim != 1 or len(times) != len(teacher) or not np.isfinite(times).all():
        raise ValueError("validation follow-up must be finite and aligned with scores")
    if events.ndim != 1 or len(events) != len(teacher) or not np.isin(events, (0, 1)).all():
        raise ValueError("validation events must be binary and aligned with scores")

    teacher_sd = float(np.std(teacher, ddof=0))
    rmse = float(np.sqrt(np.mean(np.square(student - teacher))))
    if teacher_sd > 0.0:
        normalized_rmse: dict[str, Any] = {"estimate": rmse / teacher_sd}
    else:
        normalized_rmse = {
            "estimate": None,
            "unavailable_reason": "teacher risk has zero variance on validation subjects",
        }
    fidelity = {
        "spearman": _spearman_metric(teacher, student),
        "normalized_rmse": normalized_rmse,
        "rmse": rmse,
    }
    teacher_c = _concordance_metric(times, events, teacher)
    student_c = _concordance_metric(times, events, student)
    difference = None
    if teacher_c["estimate"] is not None and student_c["estimate"] is not None:
        difference = student_c["estimate"] - teacher_c["estimate"]
    return {
        "fidelity": fidelity,
        "survival_performance": {
            "metric": "Harrell concordance index",
            "teacher": teacher_c,
            "student": student_c,
            "student_minus_teacher": difference,
        },
    }


def fit_and_evaluate_surrogate_fold(
    x_train: pd.DataFrame,
    teacher_train: np.ndarray,
    x_validation: pd.DataFrame,
    teacher_validation: np.ndarray,
    observed_time: np.ndarray,
    observed_event: np.ndarray,
    *,
    seed: int,
    feature_groups: dict[str, str],
    preprocessing: dict[str, Any],
) -> dict[str, Any]:
    """Fit the student on outer-training inputs, then score a separate held-out fold."""
    training = _feature_frame(x_train, name="outer-training features")
    validation = _feature_frame(x_validation, name="outer-validation features")
    if list(training.columns) != list(validation.columns):
        raise ValueError("outer-training and outer-validation feature columns differ")
    teacher = _score_vector(teacher_validation, len(validation), name="validation teacher scores")
    fitted = fit_surrogate_tree(training, teacher_train, seed=seed)
    student = fitted.estimator.predict(validation)
    metrics = score_surrogate_fold(teacher, student, observed_time, observed_event)
    diagnostics = tree_diagnostics(
        fitted.estimator,
        list(training.columns),
        feature_groups,
        preprocessing,
    )
    return {
        "fit": fitted,
        "student_risk": student,
        "metrics": metrics,
        "tree_diagnostics": diagnostics,
    }


def midrank_percentiles(scores: np.ndarray) -> np.ndarray:
    """Map finite scores to midrank percentiles in ``(0, 1)``."""
    values = _score_vector(scores, None, name="scores")
    return (rankdata(values, method="average") - 0.5) / len(values)


def surrogate_seed(cohort_index: int, repeat: int, fold: int) -> int:
    """Return the frozen inner-CV and tree seed for one planned outer cell."""
    if cohort_index not in range(len(COHORTS)) or repeat < 1 or fold < 1:
        raise ValueError("cohort, repeat and fold must identify a planned cell")
    return 47047 + 100000 * cohort_index + 1009 * (repeat - 1) + (fold - 1)


def bootstrap_seed(cohort_index: int) -> int:
    """Return the frozen subject-bootstrap seed for a cohort."""
    if cohort_index not in range(len(COHORTS)):
        raise ValueError("cohort_index must identify one of the three planned cohorts")
    return 147047 + cohort_index


def validate_review_receipt(receipt: dict[str, Any]) -> None:
    """Require a named, independent acceptance tied to the frozen protocol."""
    required = (
        "reviewer_name",
        "reviewer_affiliation",
        "reviewer_role",
        "reviewed_at_utc",
        "decision",
        "protocol_sha256",
    )
    missing = [field for field in required if not str(receipt.get(field, "")).strip()]
    if missing:
        raise ValueError(f"review receipt is missing required fields: {missing}")
    role = str(receipt["reviewer_role"]).casefold()
    if "independent" not in role:
        raise ValueError("reviewer_role must identify an independent scientific reviewer")
    if receipt["decision"] != "accepted":
        raise ValueError("RSF surrogate production requires an accepted protocol review")
    if receipt["protocol_sha256"] != PROTOCOL_SHA256:
        raise ValueError("review receipt does not accept the frozen protocol hash")


def validate_owner_waiver_receipt(receipt: dict[str, Any]) -> None:
    """Validate an explicit owner waiver without representing it as review."""
    required = (
        "receipt_type",
        "owner_role",
        "instruction_date",
        "receipt_recorded_at_utc",
        "decision",
        "protocol_sha256",
        "authorization_context",
        "scope",
        "independent_review_obtained",
    )
    missing = [field for field in required if field not in receipt]
    if missing:
        raise ValueError(f"owner waiver receipt is missing required fields: {missing}")
    if receipt["receipt_type"] != "owner_gate_waiver":
        raise ValueError("receipt_type must identify an owner gate waiver")
    if receipt["owner_role"] != "project owner":
        raise ValueError("owner waiver must be authorized by the project owner")
    if receipt["instruction_date"] != "2026-10-07":
        raise ValueError("owner waiver instruction date is unexpected")
    if receipt["decision"] != "proceed_under_owner_waiver":
        raise ValueError("owner waiver decision is not an authorization to proceed")
    if receipt["protocol_sha256"] != PROTOCOL_SHA256:
        raise ValueError("owner waiver does not identify the frozen protocol hash")
    if receipt["scope"] != ["T-193", "T-194 Windows pilot and budget-qualified production"]:
        raise ValueError("owner waiver scope differs from the authorized execution")
    if receipt["independent_review_obtained"] is not False:
        raise ValueError("owner waiver must not claim independent review was obtained")
    if not str(receipt["authorization_context"]).strip():
        raise ValueError("owner waiver must preserve its authorization context")


def verify_teacher_replay(
    expected_risk: Sequence[float],
    replayed_risk: Sequence[float],
    expected_subject_ids: Sequence[str],
    replayed_subject_ids: Sequence[str],
) -> dict[str, Any]:
    """Check the frozen validation prediction vector and its exact row order."""
    expected = _score_vector(np.asarray(expected_risk), None, name="stored teacher scores")
    replayed = _score_vector(np.asarray(replayed_risk), len(expected), name="replayed teacher scores")
    expected_ids = [str(value) for value in expected_subject_ids]
    replayed_ids = [str(value) for value in replayed_subject_ids]
    if len(expected_ids) != len(expected) or replayed_ids != expected_ids:
        raise ValueError("replayed teacher subject order differs from the frozen source cell")
    if not np.allclose(replayed, expected, rtol=1e-10, atol=1e-12):
        max_error = float(np.max(np.abs(replayed - expected)))
        raise ValueError(f"replayed teacher risk differs from source (max_abs_error={max_error:.17g})")
    return {
        "subject_order_match": True,
        "rtol": 1e-10,
        "atol": 1e-12,
        "max_absolute_error": float(np.max(np.abs(replayed - expected))),
        "n_validation": int(len(expected)),
    }


def average_repeated_fold_percentiles(
    fold_records: Sequence[dict[str, Any]],
    expected_subject_ids: Sequence[str],
    *,
    n_repeats: int = 5,
    n_folds: int = 5,
) -> dict[str, Any]:
    """Average within-fold ranks only when every subject has one score per repeat."""
    expected = [str(value) for value in expected_subject_ids]
    if len(set(expected)) != len(expected) or n_repeats < 1 or n_folds < 1:
        raise ValueError("expected subjects must be unique and repeat/fold counts positive")
    teacher_rows: dict[str, list[float]] = {subject: [] for subject in expected}
    student_rows: dict[str, list[float]] = {subject: [] for subject in expected}
    outcomes: dict[str, tuple[float, int]] = {}
    repeats: dict[int, dict[str, int]] = {}
    seen_cells: set[tuple[int, int]] = set()
    for record in fold_records:
        repeat = int(record["repeat"])
        fold = int(record["fold"])
        if repeat not in range(1, n_repeats + 1) or fold not in range(1, n_folds + 1):
            raise ValueError("fold record has an invalid repeat or fold identity")
        if (repeat, fold) in seen_cells:
            raise ValueError("duplicate outer-fold record")
        seen_cells.add((repeat, fold))
        prediction = record["predictions"]
        ids = [str(value) for value in prediction["subject_ids"]]
        teacher = _score_vector(prediction["teacher_risk"], len(ids), name="teacher fold scores")
        student = _score_vector(prediction["student_risk"], len(ids), name="student fold scores")
        times = np.asarray(prediction["observed_time"], dtype=float)
        events = np.asarray(prediction["observed_event"], dtype=int)
        if len(times) != len(ids) or not np.isfinite(times).all():
            raise ValueError("fold follow-up does not align with subject identities")
        if len(events) != len(ids) or not np.isin(events, (0, 1)).all():
            raise ValueError("fold events do not align with subject identities")
        if len(set(ids)) != len(ids) or not set(ids).issubset(teacher_rows):
            raise ValueError("fold has duplicate or unexpected subject identities")
        repeat_counts = repeats.setdefault(repeat, {})
        teacher_percentiles = midrank_percentiles(teacher)
        student_percentiles = midrank_percentiles(student)
        for index, subject in enumerate(ids):
            if subject in repeat_counts:
                raise ValueError(f"subject {subject!r} appears in multiple folds in repeat {repeat}")
            repeat_counts[subject] = fold
            outcome = (float(times[index]), int(events[index]))
            if subject in outcomes and outcomes[subject] != outcome:
                raise ValueError(f"outcomes disagree across folds for subject {subject!r}")
            outcomes[subject] = outcome
            teacher_rows[subject].append(float(teacher_percentiles[index]))
            student_rows[subject].append(float(student_percentiles[index]))
    expected_cells = {(repeat, fold) for repeat in range(1, n_repeats + 1) for fold in range(1, n_folds + 1)}
    if seen_cells != expected_cells:
        raise ValueError("fold records do not cover the complete repeated outer-fold grid")
    incomplete = {
        subject: len(values)
        for subject, values in teacher_rows.items()
        if len(values) != n_repeats
    }
    if incomplete:
        raise ValueError(
            "cannot form the frozen repeated-fold cohort summary; subjects do not have "
            f"exactly {n_repeats} held-out predictions: {len(incomplete)} incomplete"
        )
    if len(outcomes) != len(expected):
        raise ValueError("not every expected subject has observed outcomes")
    return {
        "subject_ids": expected,
        "teacher_percentiles": np.asarray(
            [np.mean(teacher_rows[subject]) for subject in expected], dtype=float
        ),
        "student_percentiles": np.asarray(
            [np.mean(student_rows[subject]) for subject in expected], dtype=float
        ),
        "observed_time": np.asarray([outcomes[s][0] for s in expected], dtype=float),
        "observed_event": np.asarray([outcomes[s][1] for s in expected], dtype=int),
        "n_repeats": n_repeats,
    }


def feature_group_stability(
    cell_records: Sequence[dict[str, Any]],
    *,
    planned_cells: int = PLANNED_FOLDS_PER_COHORT,
    candidate_groups: Sequence[str] = (),
) -> dict[str, Any]:
    """Count split-group use against the full planned denominator, retaining failures."""
    if planned_cells < 1 or len(cell_records) > planned_cells:
        raise ValueError("planned_cells must cover every supplied fold record")
    counts: dict[str, int] = {str(group): 0 for group in candidate_groups}
    split_counts: dict[str, int] = {}
    complete = 0
    for record in cell_records:
        if record.get("status") != "complete":
            continue
        complete += 1
        diagnostics = record.get("tree_diagnostics", {})
        groups = set(str(value) for value in diagnostics.get("feature_groups_used", []))
        for group in groups:
            counts[group] = counts.get(group, 0) + 1
        for split in diagnostics.get("split_records", []):
            group = str(split["feature_group"])
            split_counts[group] = split_counts.get(group, 0) + 1
    return {
        "planned_cell_denominator": int(planned_cells),
        "successful_tree_cells": complete,
        "feature_groups": {
            group: {
                "fold_use_count": count,
                "planned_fold_proportion": count / planned_cells,
                "split_count": split_counts.get(group, 0),
            }
            for group, count in sorted(counts.items())
        },
    }


def verify_surrogate_run(run_dir: Path) -> dict[str, Any]:
    """Verify a sealed post-hoc run's hashes, exact 75-cell grid and inventory."""
    root = run_dir.resolve(strict=True)
    manifest = _load_json_mapping(root / "manifest.json")
    completion = _load_json_mapping(root / "completion.json")
    _verify_embedded_hash(manifest, "manifest_content_sha256", "run manifest")
    _verify_embedded_hash(completion, "completion_content_sha256", "run completion")
    if manifest.get("analysis") != "posthoc_rsf_surrogate_v1":
        raise RuntimeError("run manifest identifies a different analysis")
    if manifest.get("run_type") != "production":
        raise RuntimeError("run manifest is not a full production run")
    if manifest.get("protocol_sha256") != PROTOCOL_SHA256:
        raise RuntimeError("run manifest points to a different frozen protocol")
    if completion.get("protocol_sha256") != PROTOCOL_SHA256:
        raise RuntimeError("run completion points to a different frozen protocol")
    source_release = manifest.get("source_release")
    if not isinstance(source_release, dict):
        raise RuntimeError("run manifest has no frozen source release identity")
    source_manifest = source_release.get("manifest_sha256")
    if not isinstance(source_manifest, str) or not re.fullmatch(r"[0-9a-f]{64}", source_manifest):
        raise RuntimeError("run manifest has no valid source manifest hash")
    source_completion = source_release.get("completion_sha256")
    if not isinstance(source_completion, str) or not re.fullmatch(r"[0-9a-f]{64}", source_completion):
        raise RuntimeError("run manifest has no valid source completion hash")
    if completion.get("source_completion_sha256") != source_completion:
        raise RuntimeError("run completion points to a different source completion")
    run_identity = manifest.get("run_identity_sha256")
    if not isinstance(run_identity, str) or not re.fullmatch(r"[0-9a-f]{64}", run_identity):
        raise RuntimeError("run manifest has no identity hash")
    pilot_hash = manifest.get("pilot_completion_sha256")
    if not isinstance(pilot_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", pilot_hash):
        raise RuntimeError("production manifest has no verified pilot completion hash")

    expected = {
        f"cells/{cohort}/r{repeat:02d}f{fold:02d}.json"
        for cohort in COHORTS
        for repeat in range(1, 6)
        for fold in range(1, 6)
    }
    inventory = completion.get("cell_sha256")
    if not isinstance(inventory, dict) or set(inventory) != expected:
        raise RuntimeError("run cell inventory does not equal the frozen 75-cell grid")
    actual = {
        path.relative_to(root).as_posix()
        for path in (root / "cells").glob("*/*.json")
    }
    if actual != expected:
        raise RuntimeError("stored cell files differ from the completion inventory")
    observed_statuses: Counter[str] = Counter()
    for relative in sorted(expected):
        path = root / Path(relative)
        if sha256_file(path) != inventory[relative]:
            raise RuntimeError(f"cell file SHA-256 mismatch: {relative}")
        record = _load_json_mapping(path)
        _verify_embedded_hash(record, "cell_content_sha256", relative)
        if record.get("run_identity_sha256") != manifest.get("run_identity_sha256"):
            raise RuntimeError(f"cell is bound to a different run identity: {relative}")
        path_parts = Path(relative).parts
        if (
            record.get("dataset") != path_parts[1]
            or int(record.get("repeat", -1)) != int(path_parts[2][1:3])
            or int(record.get("fold", -1)) != int(path_parts[2][4:6])
        ):
            raise RuntimeError(f"cell identity differs from its inventory path: {relative}")
        status = record.get("status")
        if status not in {
            "complete",
            "source_cell_absent",
            "source_cell_failed",
            "source_integrity_failed",
            "rsf_replay_failed",
            "replay_mismatch",
            "student_fit_failed",
            "analysis_failed",
        }:
            raise RuntimeError(f"cell has an invalid or unfinished status: {relative}")
        source_cell_hash = record.get("source_cell_sha256")
        if status == "source_cell_absent":
            if source_cell_hash is not None or record.get("source_cell_content_sha256") is not None:
                raise RuntimeError(f"absent source cell has a source hash: {relative}")
        else:
            source_content_hash = record.get("source_cell_content_sha256")
            if not isinstance(source_cell_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", source_cell_hash):
                raise RuntimeError(f"source cell hash is missing or invalid: {relative}")
            if not isinstance(source_content_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", source_content_hash):
                raise RuntimeError(f"source cell content hash is missing or invalid: {relative}")
        observed_statuses[str(status)] += 1
    if observed_statuses != Counter(completion.get("status_counts", {})):
        raise RuntimeError("completion status counts differ from the stored cells")
    if int(completion.get("planned_cells", -1)) != len(expected):
        raise RuntimeError("completion planned-cell count differs from the frozen grid")
    if int(completion.get("stored_cells", -1)) != len(expected):
        raise RuntimeError("completion stored-cell count differs from the frozen grid")

    expected_aggregates = {"cohort_summaries.json", "report.md"}
    aggregate_inventory = completion.get("aggregate_sha256")
    if not isinstance(aggregate_inventory, dict) or set(aggregate_inventory) != expected_aggregates:
        raise RuntimeError("aggregate inventory is incomplete")
    for relative, digest in aggregate_inventory.items():
        path = root / relative
        if not path.is_file() or sha256_file(path) != digest:
            raise RuntimeError(f"aggregate SHA-256 mismatch: {relative}")
    summaries = _load_json_mapping(root / "cohort_summaries.json")
    if set(summaries) != set(COHORTS):
        raise RuntimeError("cohort summary inventory differs from the frozen design")
    for cohort in COHORTS:
        summary = summaries[cohort]
        if int(summary.get("planned_cells", -1)) != PLANNED_FOLDS_PER_COHORT:
            raise RuntimeError(f"{cohort} summary has a different planned denominator")
        if sum(int(value) for value in summary.get("status_counts", {}).values()) != PLANNED_FOLDS_PER_COHORT:
            raise RuntimeError(f"{cohort} summary does not account for every planned cell")
    return {
        "status": "verified",
        "planned_cells": len(expected),
        "status_counts": dict(sorted(observed_statuses.items())),
        "manifest_sha256": sha256_file(root / "manifest.json"),
        "completion_sha256": sha256_file(root / "completion.json"),
    }


def summarize_subject_predictions(
    teacher_percentiles: np.ndarray,
    student_percentiles: np.ndarray,
    observed_time: np.ndarray,
    observed_event: np.ndarray,
    *,
    seed: int,
    bootstrap_replicates: int = 2000,
) -> dict[str, Any]:
    """Summarize repeated-fold percentile predictions with patient bootstrap CIs.

    Each input row represents a distinct subject whose five held-out
    predictions have already been averaged. Resampling is stratified by the
    observed event indicator and conditions on the fitted repeated-fold models.

    Args:
        teacher_percentiles: Subject-level averaged teacher midrank percentiles.
        student_percentiles: Subject-level averaged student midrank percentiles.
        observed_time: One outcome time per subject.
        observed_event: One 0/1 event indicator per subject.
        seed: Explicit bootstrap random seed.
        bootstrap_replicates: Positive number of event-stratified resamples.

    Returns:
        Point estimates, percentile confidence intervals and bootstrap counts.

    Raises:
        ValueError: Inputs are misaligned, invalid or empty.
    """
    teacher = _score_vector(teacher_percentiles, None, name="subject teacher percentiles")
    student = _score_vector(student_percentiles, len(teacher), name="subject student percentiles")
    times = np.asarray(observed_time, dtype=float)
    events = np.asarray(observed_event, dtype=int)
    if len(times) != len(teacher) or not np.isfinite(times).all():
        raise ValueError("subject follow-up must be finite and aligned")
    if len(events) != len(teacher) or not np.isin(events, (0, 1)).all():
        raise ValueError("subject events must be binary and aligned")
    if bootstrap_replicates < 1:
        raise ValueError("bootstrap_replicates must be positive")

    point = _population_metrics(teacher, student, times, events)
    rng = np.random.default_rng(int(seed))
    event_indices = np.flatnonzero(events == 1)
    censored_indices = np.flatnonzero(events == 0)
    draws: dict[str, list[float]] = {
        "fidelity_spearman": [],
        "fidelity_rmse": [],
        "fidelity_normalized_rmse": [],
        "teacher_harrell_c": [],
        "student_harrell_c": [],
        "student_minus_teacher_harrell_c": [],
    }
    for _ in range(bootstrap_replicates):
        sampled = np.concatenate(
            (
                rng.choice(event_indices, size=len(event_indices), replace=True),
                rng.choice(censored_indices, size=len(censored_indices), replace=True),
            )
        )
        replicate = _population_metrics(
            teacher[sampled], student[sampled], times[sampled], events[sampled]
        )
        _append_estimate(draws["fidelity_spearman"], replicate["fidelity"]["spearman"])
        _append_estimate(draws["fidelity_rmse"], replicate["fidelity"]["rmse"])
        _append_estimate(
            draws["fidelity_normalized_rmse"], replicate["fidelity"]["normalized_rmse"]
        )
        outcome = replicate["survival_performance"]
        _append_estimate(draws["teacher_harrell_c"], outcome["teacher"])
        _append_estimate(draws["student_harrell_c"], outcome["student"])
        difference = outcome["student_minus_teacher"]
        if difference is not None:
            draws["student_minus_teacher_harrell_c"].append(float(difference))

    intervals = {
        metric: _percentile_interval(values)
        for metric, values in draws.items()
    }
    return {
        **point,
        "uncertainty": {
            "method": "event-stratified subject bootstrap of repeated-fold averages",
            "confidence_level": 0.95,
            "requested_replicates": int(bootstrap_replicates),
            "seed": int(seed),
            "intervals": intervals,
            "interpretation": (
                "Conditional on the fitted repeated-fold models; does not quantify "
                "model-refitting or external-population uncertainty."
            ),
        },
        "n_subjects": int(len(teacher)),
        "n_events": int(events.sum()),
    }


def tree_diagnostics(
    estimator: DecisionTreeRegressor,
    feature_names: list[str],
    feature_groups: dict[str, str],
    preprocessing: dict[str, Any],
) -> dict[str, Any]:
    """Return tree complexity, mapped split records and readable fold rules."""
    if estimator.tree_ is None:
        raise ValueError("surrogate tree is not fitted")
    if len(feature_names) != estimator.n_features_in_:
        raise ValueError("feature names do not match the fitted tree")
    tree = estimator.tree_
    group_importance: dict[str, float] = {}
    feature_importance: dict[str, float] = {}
    group_split_counts: dict[str, int] = {}
    split_records: list[dict[str, Any]] = []
    engineered = {
        str(declaration["name"]): declaration
        for declaration in preprocessing.get("feature_spec", {}).get("engineered", [])
    }
    for node in range(tree.node_count):
        feature_index = int(tree.feature[node])
        if feature_index < 0:
            continue
        name = feature_names[feature_index]
        group = feature_groups.get(name, name)
        feature_importance[name] = float(estimator.feature_importances_[feature_index])
        group_split_counts[group] = group_split_counts.get(group, 0) + 1
        threshold = float(tree.threshold[node])
        scaling = preprocessing.get("scaling", {}).get(name)
        raw_threshold = None
        if isinstance(scaling, dict):
            raw_threshold = threshold * float(scaling["scale"]) + float(scaling["mean"])
        split_records.append(
            {
                "node": node,
                "feature": name,
                "feature_group": group,
                "engineered_definition": engineered.get(name),
                "threshold_preprocessed": threshold,
                "threshold_feature_scale": raw_threshold,
                "samples": int(tree.n_node_samples[node]),
            }
        )
    for name, importance in feature_importance.items():
        group = feature_groups.get(name, name)
        group_importance[group] = group_importance.get(group, 0.0) + importance
    return {
        "depth": int(tree.max_depth),
        "node_count": int(tree.node_count),
        "leaf_count": int(estimator.get_n_leaves()),
        "feature_groups_used": sorted(group_importance),
        "candidate_feature_groups": sorted(set(str(value) for value in feature_groups.values())),
        "feature_group_importance": dict(sorted(group_importance.items())),
        "feature_group_split_counts": dict(sorted(group_split_counts.items())),
        "split_records": split_records,
        "rules_text": export_text(estimator, feature_names=feature_names, decimals=4),
    }


def _feature_frame(value: pd.DataFrame, *, name: str) -> pd.DataFrame:
    """Validate one finite, uniquely named preprocessed feature frame."""
    if not isinstance(value, pd.DataFrame) or value.empty:
        raise ValueError(f"{name} must be a non-empty DataFrame")
    if not value.columns.is_unique:
        raise ValueError(f"{name} contains duplicate feature names")
    array = value.to_numpy(dtype=float)
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain only finite values")
    return value


def _score_vector(value: np.ndarray, length: int | None, *, name: str) -> np.ndarray:
    """Validate a non-empty finite one-dimensional prediction vector."""
    scores = np.asarray(value, dtype=float)
    if scores.ndim != 1 or len(scores) == 0 or (length is not None and len(scores) != length):
        raise ValueError(f"{name} must be a non-empty vector of the expected length")
    if not np.isfinite(scores).all():
        raise ValueError(f"{name} must contain only finite values")
    return scores


def _load_json_mapping(path: Path) -> dict[str, Any]:
    """Load one JSON object used by the run verifier."""
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object in {path}")
    return value


def _verify_embedded_hash(record: dict[str, Any], field: str, name: str) -> None:
    """Compare a record's claimed canonical hash with its unhashed content."""
    unhashed = dict(record)
    claimed = unhashed.pop(field, None)
    if claimed != canonical_json_hash(unhashed):
        raise RuntimeError(f"{name} content hash is invalid")


def _selection_row(candidate: dict[str, Any]) -> dict[str, Any]:
    """Return the protocol-relevant selection fields without mutating a candidate."""
    return {
        "max_depth": int(candidate["max_depth"]),
        "min_samples_leaf": float(candidate["min_samples_leaf"]),
        "mean_mse": float(candidate["mean_mse"]),
        "standard_error": float(candidate["standard_error"]),
    }


def _spearman_metric(left: np.ndarray, right: np.ndarray) -> dict[str, Any]:
    """Return a finite Spearman statistic or a reason it is undefined."""
    if np.ptp(left) == 0.0 or np.ptp(right) == 0.0:
        return {"estimate": None, "unavailable_reason": "one score vector is constant"}
    result = spearmanr(left, right)
    estimate = float(result.statistic)
    if not np.isfinite(estimate):
        return {"estimate": None, "unavailable_reason": "Spearman statistic is non-finite"}
    return {"estimate": estimate}


def _concordance_metric(
    times: np.ndarray, events: np.ndarray, scores: np.ndarray
) -> dict[str, Any]:
    """Return Harrell concordance or retain its undefined-comparison reason."""
    try:
        return {"estimate": harrell_c_index(times, events, scores)}
    except ValueError as exc:
        return {"estimate": None, "unavailable_reason": str(exc)}


def _population_metrics(
    teacher: np.ndarray, student: np.ndarray, times: np.ndarray, events: np.ndarray
) -> dict[str, Any]:
    """Return cohort-level fidelity and outcome metrics for paired subjects."""
    rmse = float(np.sqrt(np.mean(np.square(student - teacher))))
    teacher_sd = float(np.std(teacher, ddof=0))
    normalized_rmse: dict[str, Any]
    if teacher_sd > 0.0:
        normalized_rmse = {"estimate": rmse / teacher_sd}
    else:
        normalized_rmse = {
            "estimate": None,
            "unavailable_reason": "teacher percentiles have zero variance",
        }
    teacher_c = _concordance_metric(times, events, teacher)
    student_c = _concordance_metric(times, events, student)
    difference = None
    if teacher_c["estimate"] is not None and student_c["estimate"] is not None:
        difference = student_c["estimate"] - teacher_c["estimate"]
    return {
        "fidelity": {
            "spearman": _spearman_metric(teacher, student),
            "rmse": rmse,
            "normalized_rmse": normalized_rmse,
        },
        "survival_performance": {
            "metric": "Harrell concordance index on repeated-fold average percentiles",
            "teacher": teacher_c,
            "student": student_c,
            "student_minus_teacher": difference,
        },
    }


def _append_estimate(target: list[float], metric: float | dict[str, Any]) -> None:
    """Add one defined estimate to a bootstrap distribution."""
    value = metric.get("estimate") if isinstance(metric, dict) else metric
    if value is not None and np.isfinite(float(value)):
        target.append(float(value))


def _percentile_interval(values: list[float]) -> dict[str, Any]:
    """Return a 95% percentile interval and retain empty bootstrap support."""
    if not values:
        return {"lower": None, "upper": None, "successful_replicates": 0}
    lower, upper = np.quantile(np.asarray(values, dtype=float), [0.025, 0.975])
    return {
        "lower": float(lower),
        "upper": float(upper),
        "successful_replicates": len(values),
    }
