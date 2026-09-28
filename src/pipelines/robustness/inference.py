"""Compute paired Brier-score sensitivities and Cox proportional-hazards summaries.

This is the aggregation stage of a robustness run; :mod:`runner` calls both
entry points after every cell is stored and validated, then writes their
returned mappings to separate aggregate files.

- :func:`paired_ibs_inference` returns ``paired_ibs_inference.json`` content:
  for conditions represented by complete cells, the paired integrated Brier
  score (IBS) difference between priors, and for research question 2 (RQ2),
  difference-in-differences against the full-size, observed-follow-up
  condition. Intervals use a three-stage bootstrap, are descriptive and
  form no multiplicity-controlled family.
- :func:`aggregate_ph_tests` returns ``ph_assessment.json`` content: a summary
  of proportional-hazards (PH) tests stored in the confirmatory Cox cells.
  Nothing is refitted.
"""

from __future__ import annotations

from collections.abc import Iterable
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.pipelines.confirmatory import (
    deterministic_seed,
)
from src.statistics.hypothesis_tests import holm_adjust
from src.utils.io import read_mapping
from src.utils.reproducibility import (
    canonical_json_hash,
    sha256_file,
)

from .protocol import (
    BAYESIAN_MODEL_KEYS,
    DESIGN_FEATURE_FOLD_NUMBERS_PER_REPEAT,
)


def _cell_analysis_names(cell: dict[str, Any]) -> set[tuple[str, str]]:
    """Return the ``(component, condition)`` analyses a stored cell serves."""
    return {
        (str(item["component"]), str(item["condition"])) for item in cell["condition"]["analyses"]
    }


def _bootstrap_contributions(
    fold_contributions: list[np.ndarray],
    fold_events: list[np.ndarray],
    fold_ids: list[dict[str, int]],
    *,
    n_bootstraps: int,
    confidence_level: float,
    seed: int,
) -> dict[str, Any]:
    """Three-stage paired bootstrap of the mean per-subject IBS difference.

    Each replicate resamples, with replacement, (1) the outer repeats, (2) the
    folds within each sampled repeat, and (3) the validation subjects within
    each sampled fold and event stratum. It then averages the per-subject
    differences within each fold and the fold means across folds. Resampling
    repeats and folds as well as subjects represents split-to-split
    variation, not only subject-level variation. Because each value is
    already a paired difference, both priors always share the same resampled
    subjects.

    Args:
        fold_contributions: Per-subject IBS differences, or
            differences-in-differences, one array per fold.
        fold_events: Untruncated validation event indicators, one array per
            fold, defining the event strata.
        fold_ids: ``{"repeat", "fold"}`` identifiers, one per fold.
        n_bootstraps: Number of replicates; at least 20.
        confidence_level: Coverage of the percentile interval.
        seed: Seed of the single generator used for all replicates.

    Returns:
        The observed mean of fold means, the bootstrap mean, standard error
        and percentile interval, and the counts of repeats and folds.

    Raises:
        ValueError: Too few replicates, or misaligned inputs.
    """
    if n_bootstraps < 20:
        raise ValueError("sensitivity bootstrap requires at least 20 replicates")
    if (
        len(fold_contributions) == 0
        or len(fold_contributions) != len(fold_events)
        or len(fold_contributions) != len(fold_ids)
    ):
        raise ValueError("paired contributions, events and fold identifiers are required")
    repeat_to_indices: dict[int, list[int]] = {}
    for index, fold_id in enumerate(fold_ids):
        repeat = int(fold_id["repeat"])
        repeat_to_indices.setdefault(repeat, []).append(index)
    repeats = np.asarray(sorted(repeat_to_indices), dtype=int)
    if len(repeats) == 0:
        raise ValueError("at least one outer repeat is required")
    observed = float(np.mean([np.mean(values) for values in fold_contributions]))
    # One generator is consumed in a fixed order within each replicate:
    # repeats, then folds for each sampled repeat, then subjects for each
    # sampled fold, censored before events. Changing this order changes every
    # replicate and so the stored intervals.
    rng = np.random.default_rng(seed)
    samples = np.empty(n_bootstraps, dtype=float)
    for bootstrap in range(n_bootstraps):
        fold_means: list[float] = []
        sampled_repeats = rng.choice(repeats, size=len(repeats), replace=True)
        selected_fold_indices: list[int] = []
        for repeat in sampled_repeats:
            candidates = np.asarray(repeat_to_indices[int(repeat)], dtype=int)
            selected_fold_indices.extend(
                rng.choice(candidates, size=len(candidates), replace=True).tolist()
            )
        for fold_index in selected_fold_indices:
            values = fold_contributions[fold_index]
            events = fold_events[fold_index]
            sampled: list[np.ndarray] = []
            for status in (0, 1):
                indices = np.flatnonzero(events == status)
                if len(indices):
                    sampled.append(rng.choice(indices, size=len(indices), replace=True))
            selected = np.concatenate(sampled)
            fold_means.append(float(np.mean(values[selected])))
        samples[bootstrap] = float(np.mean(fold_means))
    alpha = 1.0 - confidence_level
    lower, upper = np.quantile(samples, [alpha / 2, 1 - alpha / 2])
    return {
        "observed": observed,
        "bootstrap_mean": float(np.mean(samples)),
        "bootstrap_standard_error": float(np.std(samples, ddof=1)),
        "confidence_lower": float(lower),
        "confidence_upper": float(upper),
        "confidence_level": confidence_level,
        "n_bootstraps": n_bootstraps,
        "n_successful": n_bootstraps,
        "resampling_unit": (
            "outer repeats, then folds within repeat, then validation subjects "
            "within fold and event stratum"
        ),
        "n_outer_repeats": len(repeats),
        "n_outer_folds": len(fold_contributions),
    }


def paired_ibs_inference(
    cells: list[dict[str, Any]],
    *,
    components: Iterable[str],
    n_bootstraps: int,
    confidence_level: float,
    seed: int,
) -> dict[str, Any]:
    """Compute paired IBS contrasts and RQ2 difference-in-differences.

    Every contrast is IBS(model_a) minus IBS(model_b), computed per subject
    from the stored contributions and paired by cohort, component, condition,
    repeat and fold. Design and feature contrasts use only the folds in
    :data:`~.protocol.DESIGN_FEATURE_FOLD_NUMBERS_PER_REPEAT`, even for a
    condition that was also fitted on further folds for RQ2.

    The RQ2 difference-in-differences for condition c is, per subject,
    ``[IBS_a(c) - IBS_b(c)] - [IBS_a(full) - IBS_b(full)]`` with ``full`` the
    100-percent, observed-follow-up condition. It estimates how much the prior
    difference changes when training information falls or censoring rises,
    and uses the four cells of the same fold, which share validation
    subjects.

    Conditions with no complete cells produce no contrast rows. A contrast
    marked ``"complete"`` has an estimate from at least one usable fold pair;
    this status does not attest that all planned folds contributed. Its paired
    fold count and identifiers describe the actual coverage.

    Args:
        cells: Validated robustness cells; only complete cells are used.
        components: Components to summarise (``"rq2"``, ``"design"`` and/or
            ``"feature"``).
        n_bootstraps: Replicates per contrast.
        confidence_level: Interval coverage.
        seed: Base seed; each contrast derives its own.

    Returns:
        The content of ``paired_ibs_inference.json``.

    Raises:
        ValueError: Paired cells do not share validation subjects or strata.
    """
    complete = [cell for cell in cells if cell.get("status") == "complete"]
    datasets = sorted({str(cell["dataset"]) for cell in cells})
    requested = set(components)
    contrasts: list[dict[str, Any]] = []
    contribution_lookup: dict[
        tuple[str, str, str, str, int, int], tuple[np.ndarray, np.ndarray, list[str]]
    ] = {}

    for cell in complete:
        for component, condition in _cell_analysis_names(cell):
            if component not in requested:
                continue
            # Non-primary design and feature conditions exist only on fold 1,
            # so the primary anchor is restricted to the same folds.
            if (
                component in {"design", "feature"}
                and int(cell["fold"]) not in DESIGN_FEATURE_FOLD_NUMBERS_PER_REPEAT
            ):
                continue
            key = (
                str(cell["dataset"]),
                component,
                condition,
                str(cell["model_key"]),
                int(cell["repeat"]),
                int(cell["fold"]),
            )
            contribution_lookup[key] = (
                np.asarray(cell["individual_ibs_loss"], dtype=float),
                np.asarray(cell["original_events_validation"], dtype=int),
                [str(value) for value in cell["validation_subject_ids"]],
            )

    condition_names = sorted(
        {
            (dataset, component, condition)
            for dataset, component, condition, _model, _repeat, _fold in contribution_lookup
        }
    )
    for dataset, component, condition in condition_names:
        for model_a, model_b in combinations(BAYESIAN_MODEL_KEYS, 2):
            fold_values: list[np.ndarray] = []
            fold_events: list[np.ndarray] = []
            fold_ids: list[dict[str, int]] = []
            keys_a = sorted(
                key
                for key in contribution_lookup
                if key[:4] == (dataset, component, condition, model_a)
            )
            for key_a in keys_a:
                repeat, fold = key_a[-2:]
                key_b = (dataset, component, condition, model_b, repeat, fold)
                if key_b not in contribution_lookup:
                    continue
                loss_a, events_a, subjects_a = contribution_lookup[key_a]
                loss_b, events_b, subjects_b = contribution_lookup[key_b]
                if subjects_a != subjects_b or not np.array_equal(events_a, events_b):
                    raise ValueError("paired robustness cells do not share validation rows")
                fold_values.append(loss_a - loss_b)
                fold_events.append(events_a)
                fold_ids.append({"repeat": repeat, "fold": fold})
            record: dict[str, Any] = {
                "dataset": dataset,
                "component": component,
                "condition": condition,
                "model_a": model_a,
                "model_b": model_b,
                "direction": "IBS(model_a) minus IBS(model_b)",
                "paired_folds": fold_ids,
            }
            if fold_values:
                record["effect"] = _bootstrap_contributions(
                    fold_values,
                    fold_events,
                    fold_ids,
                    n_bootstraps=n_bootstraps,
                    confidence_level=confidence_level,
                    seed=deterministic_seed(seed, dataset, component, condition, model_a, model_b),
                )
                record["status"] = "complete"
            else:
                record["status"] = "incomplete_no_paired_cells"
            contrasts.append(record)

    # The RQ2 reference: full training size with observed follow-up. Each
    # other RQ2 condition is compared with it on the same fold and subjects.
    full_condition = "fraction_100_observed"
    differences_in_differences: list[dict[str, Any]] = []
    rq2_conditions = sorted(
        {
            condition
            for _dataset, component, condition in condition_names
            if component == "rq2" and condition != full_condition
        }
    )
    for dataset in datasets:
        for condition in rq2_conditions:
            for model_a, model_b in combinations(BAYESIAN_MODEL_KEYS, 2):
                fold_values = []
                fold_events = []
                fold_ids = []
                keys = sorted(
                    key
                    for key in contribution_lookup
                    if key[:4] == (dataset, "rq2", condition, model_a)
                )
                for key_a in keys:
                    repeat, fold = key_a[-2:]
                    keys_needed = (
                        (dataset, "rq2", condition, model_b, repeat, fold),
                        (dataset, "rq2", full_condition, model_a, repeat, fold),
                        (dataset, "rq2", full_condition, model_b, repeat, fold),
                    )
                    if any(key not in contribution_lookup for key in keys_needed):
                        continue
                    condition_a = contribution_lookup[key_a]
                    condition_b = contribution_lookup[keys_needed[0]]
                    full_a = contribution_lookup[keys_needed[1]]
                    full_b = contribution_lookup[keys_needed[2]]
                    subject_lists = [
                        condition_a[2],
                        condition_b[2],
                        full_a[2],
                        full_b[2],
                    ]
                    if any(subjects != subject_lists[0] for subjects in subject_lists[1:]):
                        raise ValueError("RQ2 difference-in-differences is not subject-paired")
                    if not all(
                        np.array_equal(events, condition_a[1])
                        for events in (condition_b[1], full_a[1], full_b[1])
                    ):
                        raise ValueError("RQ2 difference-in-differences strata disagree")
                    did = (condition_a[0] - condition_b[0]) - (full_a[0] - full_b[0])
                    fold_values.append(did)
                    fold_events.append(condition_a[1])
                    fold_ids.append({"repeat": repeat, "fold": fold})
                record = {
                    "dataset": dataset,
                    "condition": condition,
                    "reference_condition": full_condition,
                    "model_a": model_a,
                    "model_b": model_b,
                    "direction": ("[IBS(model_a)-IBS(model_b)] condition minus full observed"),
                    "paired_folds": fold_ids,
                }
                if fold_values:
                    record["effect"] = _bootstrap_contributions(
                        fold_values,
                        fold_events,
                        fold_ids,
                        n_bootstraps=n_bootstraps,
                        confidence_level=confidence_level,
                        seed=deterministic_seed(seed, "did", dataset, condition, model_a, model_b),
                    )
                    record["status"] = "complete"
                else:
                    record["status"] = "incomplete_no_paired_cells"
                differences_in_differences.append(record)
    return {
        "schema_version": "1.0.0",
        "metric": "IPCW integrated Brier score",
        "contrast_direction": "lower IBS is better",
        "uncertainty": (
            "three-stage bootstrap of outer repeats, folds within repeat, and "
            "paired event-stratified validation subjects within fold"
        ),
        "contrasts": contrasts,
        "difference_in_differences": differences_in_differences,
    }


def aggregate_ph_tests(confirmatory_run_dir: Path) -> dict[str, Any]:
    """Purely aggregate stored Cox PH test details with within-fit Holm control.

    Each complete confirmatory Cox cell stores one scaled Schoenfeld residual
    test per covariate (rank-transformed time). Holm's adjustment is applied
    across the covariates of each fit, a fit is flagged as a departure when
    any adjusted p-value is at most 0.05, and rejection rates are summarised
    per cohort and covariate over the outer fits. The frozen response to a
    departure is to report it as a design limitation; no model is changed.

    Args:
        confirmatory_run_dir: Completed confirmatory run directory.

    Returns:
        The content of ``ph_assessment.json``, including the hash of every
        source cell and its own content hash.

    Raises:
        FileNotFoundError: No Cox cells were found.
        ValueError: A Cox cell fails its content hash.
    """
    cell_paths = sorted((confirmatory_run_dir / "cells").glob("*/*/cox_ph.json"))
    if not cell_paths:
        raise FileNotFoundError(
            f"no confirmatory Cox cells were found under {confirmatory_run_dir}"
        )
    rows: list[dict[str, Any]] = []
    fit_decisions: list[dict[str, Any]] = []
    source_hashes: dict[str, str] = {}
    for path in cell_paths:
        cell = read_mapping(path)
        claimed = cell.get("cell_content_sha256")
        unhashed = dict(cell)
        unhashed.pop("cell_content_sha256", None)
        if claimed != canonical_json_hash(unhashed):
            raise ValueError(f"confirmatory cell hash does not match: {path}")
        source_hashes[str(path.relative_to(confirmatory_run_dir))] = sha256_file(path)
        if cell.get("status") != "complete":
            fit_decisions.append(
                {
                    "dataset": cell.get("dataset"),
                    "repeat": cell.get("repeat"),
                    "fold": cell.get("fold"),
                    "status": "unavailable_incomplete_cox_cell",
                }
            )
            continue
        tests = cell.get("model_details", {}).get("ph_test", [])
        if not tests:
            fit_decisions.append(
                {
                    "dataset": cell["dataset"],
                    "repeat": cell["repeat"],
                    "fold": cell["fold"],
                    "status": "unavailable_no_ph_details",
                }
            )
            continue
        adjusted, rejected = holm_adjust([float(row["p"]) for row in tests])
        for test, adjusted_p, reject in zip(tests, adjusted, rejected, strict=True):
            rows.append(
                {
                    "dataset": cell["dataset"],
                    "repeat": cell["repeat"],
                    "fold": cell["fold"],
                    "covariate": test.get("feature", test.get("covariate")),
                    "test_statistic": test.get("test_statistic"),
                    "p_value": float(test["p"]),
                    "holm_adjusted_p": float(adjusted_p),
                    "holm_reject_0_05": bool(reject),
                }
            )
        fit_decisions.append(
            {
                "dataset": cell["dataset"],
                "repeat": cell["repeat"],
                "fold": cell["fold"],
                "status": "complete",
                "global_family_decision": (
                    "departure_detected" if any(rejected) else "no_departure_detected"
                ),
                "n_covariates": len(tests),
                "n_holm_rejections": int(sum(rejected)),
            }
        )

    summary: list[dict[str, Any]] = []
    if rows:
        table = pd.DataFrame(rows)
        for (dataset, covariate), group in table.groupby(
            ["dataset", "covariate"], dropna=False, sort=True
        ):
            summary.append(
                {
                    "dataset": dataset,
                    "covariate": covariate,
                    "n_outer_fits": len(group),
                    "n_holm_rejections": int(group["holm_reject_0_05"].sum()),
                    "proportion_holm_rejections": float(group["holm_reject_0_05"].mean()),
                    "median_raw_p": float(group["p_value"].median()),
                    "minimum_raw_p": float(group["p_value"].min()),
                }
            )
    result = {
        "schema_version": "1.0.0",
        "source_run": confirmatory_run_dir.name,
        "source_cell_sha256": source_hashes,
        "method": (
            "scaled Schoenfeld residual tests with Holm adjustment within each outer Cox fit"
        ),
        "scope_note": (
            "These Cox diagnostics warn about the shared proportional-hazards "
            "structure; they are not residual tests of DeepSurv or Bayesian fits."
        ),
        "frozen_response": (
            "Any supported departure is reported as a limitation. This pure "
            "aggregation neither adds nor tunes time interactions after results."
        ),
        "covariate_tests": rows,
        "fit_level_family_decisions": fit_decisions,
        "covariate_stability_summary": summary,
    }
    result["result_content_sha256"] = canonical_json_hash(result)
    return result
