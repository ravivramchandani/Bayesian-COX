"""Pure explainability analysis over immutable confirmatory cell artifacts."""

from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from src.data.fold_preprocessing import FoldFeaturePreprocessor
from src.explainability.posterior_analysis import (
    compare_group_rankings,
    grouped_posterior_contribution,
    recover_posterior_mean_abs_beta,
)
from src.explainability.shap_analysis import (
    exact_linear_shap_values,
    grouped_shap_importance,
)
from src.utils.reproducibility import canonical_json_hash, sha256_file


@dataclass(frozen=True)
class SamplingBudget:
    """Nested random-sampling budget for one explanation estimate."""

    validation_subjects: int
    training_background: int


@dataclass(frozen=True)
class ExplanationProtocol:
    """Frozen controls for exact linear-SHAP stability analysis."""

    seeds: tuple[int, ...] = (104729, 130363, 155921)
    budgets: tuple[SamplingBudget, ...] = (
        SamplingBudget(25, 50),
        SamplingBudget(50, 100),
        SamplingBudget(100, 200),
    )
    top_k: int = 5
    convergence_spearman: float = 0.95
    convergence_top_overlap: int = 4
    uncertainty_bootstraps: int = 2000
    uncertainty_seed: int = 196613

    def __post_init__(self) -> None:
        if len(self.seeds) != 3 or len(set(self.seeds)) != 3:
            raise ValueError("the confirmatory explanation protocol requires three seeds")
        if any(seed < 0 for seed in self.seeds):
            raise ValueError("explanation seeds must be non-negative")
        if len(self.budgets) < 2:
            raise ValueError("at least two successive sampling budgets are required")
        validation_sizes = [budget.validation_subjects for budget in self.budgets]
        background_sizes = [budget.training_background for budget in self.budgets]
        if any(value <= 0 for value in validation_sizes + background_sizes):
            raise ValueError("sampling budgets must be positive")
        if validation_sizes != sorted(set(validation_sizes)):
            raise ValueError("validation-subject budgets must increase strictly")
        if background_sizes != sorted(set(background_sizes)):
            raise ValueError("training-background budgets must increase strictly")
        if self.top_k != 5 or self.convergence_top_overlap != 4:
            raise ValueError("the frozen convergence rule is top-five overlap of at least four")
        if not 0.0 <= self.convergence_spearman <= 1.0:
            raise ValueError("the convergence Spearman threshold must be in [0, 1]")
        if self.uncertainty_bootstraps < 100:
            raise ValueError("uncertainty requires at least 100 bootstrap resamples")


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.ndarray):
        return [_json_safe(item) for item in value.tolist()]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    if value is None or isinstance(value, str):
        return value
    return str(value)


def write_explainability_result(path: Path, result: dict[str, Any]) -> None:
    """Atomically write a new result without overwriting prior evidence."""
    if path.exists():
        raise FileExistsError(f"explainability result already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(_json_safe(result), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _load_mapping(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        if path.suffix in {".yaml", ".yml"}:
            value = yaml.safe_load(handle)
        else:
            value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a mapping")
    return value


def _verify_content_hash(
    record: dict[str, Any], hash_field: str, path: Path
) -> str:
    expected = record.get(hash_field)
    if not isinstance(expected, str):
        raise ValueError(f"{path} is missing {hash_field}")
    unhashed = dict(record)
    unhashed.pop(hash_field, None)
    observed = canonical_json_hash(unhashed)
    if observed != expected:
        raise RuntimeError(f"content hash does not match: {path}")
    return observed


def _stable_seed(base_seed: int, *parts: object) -> int:
    payload = "|".join([str(base_seed), *(str(part) for part in parts)])
    digest = hashlib.sha256(payload.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % (2**32 - 1)


def _feature_spec(dataset_config: dict[str, Any], feature_set: str) -> dict[str, Any]:
    if feature_set == "primary":
        return dict(dataset_config["primary_features"])
    sensitivities = dataset_config.get("sensitivity_feature_sets", {})
    if feature_set not in sensitivities:
        raise ValueError(f"dataset has no feature set {feature_set!r}")
    return dict(sensitivities[feature_set])


def _coefficient_vector(
    coefficient_summary: Any, feature_names: list[str]
) -> np.ndarray:
    if not isinstance(coefficient_summary, list):
        raise ValueError("Cox cell has no coefficient-summary table")
    table = pd.DataFrame(coefficient_summary)
    if not {"feature", "coef"}.issubset(table.columns):
        raise ValueError("Cox coefficient summary is missing feature or coef")
    if table["feature"].duplicated().any() or set(table["feature"]) != set(
        feature_names
    ):
        raise ValueError("Cox coefficients do not match preprocessing features")
    coefficients = (
        table.set_index("feature")["coef"].astype(float).reindex(feature_names).to_numpy()
    )
    if not np.isfinite(coefficients).all():
        raise ValueError("Cox coefficients must be finite")
    return coefficients


def _exact_grouped_intrinsic_from_cell(
    model_details: dict[str, Any],
    selected_positions: list[int],
    feature_groups: dict[str, str],
    n_validation: int,
) -> pd.DataFrame | None:
    record = model_details.get(
        "posterior_expected_absolute_group_contribution_by_subject"
    )
    if record is None:
        return None
    if not isinstance(record, dict):
        raise ValueError("stored posterior group contribution has invalid schema")
    group_names = [str(value) for value in record.get("group_names", [])]
    expected_groups = set(str(value) for value in feature_groups.values())
    if len(group_names) != len(set(group_names)) or set(group_names) != expected_groups:
        raise ValueError("stored posterior group names do not match preprocessing")
    values = np.asarray(record.get("values"), dtype=float)
    if values.shape != (n_validation, len(group_names)):
        raise ValueError("stored posterior group contribution has invalid shape")
    if not np.isfinite(values).all() or np.any(values < 0):
        raise ValueError("stored posterior group contributions must be finite and non-negative")
    selected = values[np.asarray(selected_positions, dtype=int)]
    means = selected.mean(axis=0)
    return (
        pd.DataFrame(
            {"group": group_names, "expected_abs_contribution": means}
        )
        .sort_values(
            ["expected_abs_contribution", "group"], ascending=[False, True]
        )
        .reset_index(drop=True)
    )


def _load_raw_cohort(
    project_root: Path,
    dataset_key: str,
    dataset_config: dict[str, Any],
) -> tuple[pd.DataFrame, np.ndarray]:
    path = project_root / dataset_config["raw_file"]
    frame = pd.read_csv(path)
    duration_col = dataset_config["duration_col"]
    event_col = dataset_config["event_col"]
    if duration_col not in frame or event_col not in frame:
        raise ValueError(f"{dataset_key} raw data are missing outcome columns")
    times = pd.to_numeric(frame[duration_col], errors="coerce").to_numpy(float)
    events = pd.to_numeric(frame[event_col], errors="coerce").to_numpy(float)
    if not np.isfinite(times).all() or np.any(times <= 0):
        raise ValueError(f"{dataset_key} has invalid survival times")
    if not np.isin(events, [0.0, 1.0]).all():
        raise ValueError(f"{dataset_key} has a non-binary event indicator")

    id_col = dataset_config.get("id_col")
    if id_col:
        if id_col not in frame:
            raise ValueError(f"{dataset_key} is missing ID column {id_col!r}")
        subject_ids = frame[id_col].astype(str).to_numpy()
    else:
        width = len(str(len(frame)))
        subject_ids = np.asarray(
            [f"{dataset_key}-{index:0{width}d}" for index in range(len(frame))]
        )
    if len(set(subject_ids)) != len(subject_ids):
        raise ValueError(f"{dataset_key} subject identifiers are not unique")
    return frame, subject_ids


def _paired_selections(
    train_ids: list[str],
    validation_ids: list[str],
    *,
    dataset: str,
    repeat: int,
    fold: int,
    protocol: ExplanationProtocol,
) -> list[dict[str, Any]]:
    selections: list[dict[str, Any]] = []
    for seed in protocol.seeds:
        subject_seed = _stable_seed(seed, dataset, repeat, fold, "subjects")
        background_seed = _stable_seed(seed, dataset, repeat, fold, "background")
        subject_order = np.random.default_rng(subject_seed).permutation(
            len(validation_ids)
        )
        background_order = np.random.default_rng(background_seed).permutation(
            len(train_ids)
        )
        for budget_index, budget in enumerate(protocol.budgets, start=1):
            n_subjects = min(budget.validation_subjects, len(validation_ids))
            n_background = min(budget.training_background, len(train_ids))
            subject_positions = subject_order[:n_subjects]
            background_positions = background_order[:n_background]
            selected_ids = [validation_ids[index] for index in subject_positions]
            background_ids = [train_ids[index] for index in background_positions]
            selection_state = {
                "dataset": dataset,
                "repeat": repeat,
                "fold": fold,
                "seed": seed,
                "derived_subject_seed": subject_seed,
                "derived_background_seed": background_seed,
                "budget_index": budget_index,
                "requested_validation_subjects": budget.validation_subjects,
                "requested_training_background": budget.training_background,
                "validation_subject_ids": selected_ids,
                "training_background_subject_ids": background_ids,
            }
            selections.append(
                {
                    **selection_state,
                    "effective_validation_subjects": n_subjects,
                    "effective_training_background": n_background,
                    "validation_positions": subject_positions.tolist(),
                    "background_positions": background_positions.tolist(),
                    "selection_sha256": canonical_json_hash(selection_state),
                }
            )
    return selections


def _ranking_stability(
    left: list[dict[str, Any]],
    right: list[dict[str, Any]],
    *,
    score: str,
    protocol: ExplanationProtocol,
) -> dict[str, Any]:
    left_frame = pd.DataFrame(left).rename(columns={score: "expected_abs_contribution"})
    right_frame = pd.DataFrame(right).rename(columns={score: "mean_abs_shap"})
    comparison = compare_group_rankings(
        left_frame,
        right_frame,
        top_k=protocol.top_k,
    )
    rho = comparison["spearman_rho"]
    overlap = comparison["top_k_overlap"]
    evaluable = comparison["n_groups"] >= protocol.convergence_top_overlap and rho is not None
    return {
        **comparison,
        "required_spearman": protocol.convergence_spearman,
        "required_top_five_overlap": protocol.convergence_top_overlap,
        "status": (
            "not_evaluable"
            if not evaluable
            else "passed"
            if rho >= protocol.convergence_spearman
            and overlap >= protocol.convergence_top_overlap
            else "failed"
        ),
    }


def _convergence_records(
    comparisons: list[dict[str, Any]], protocol: ExplanationProtocol
) -> dict[str, Any]:
    lookup = {
        (
            row["dataset"],
            row["model_key"],
            row["repeat"],
            row["fold"],
            row["seed"],
            row["budget_index"],
        ): row
        for row in comparisons
    }
    cells = sorted(
        {
            (row["dataset"], row["model_key"], row["repeat"], row["fold"])
            for row in comparisons
        }
    )
    budget_records: list[dict[str, Any]] = []
    seed_records: list[dict[str, Any]] = []
    for dataset, model_key, repeat, fold in cells:
        for seed in protocol.seeds:
            for lower, upper in zip(
                range(1, len(protocol.budgets)),
                range(2, len(protocol.budgets) + 1),
                strict=True,
            ):
                left = lookup[(dataset, model_key, repeat, fold, seed, lower)]
                right = lookup[(dataset, model_key, repeat, fold, seed, upper)]
                same_sample = (
                    left["selection_sha256"] == right["selection_sha256"]
                    or (
                        left["effective_validation_subjects"]
                        == right["effective_validation_subjects"]
                        and left["effective_training_background"]
                        == right["effective_training_background"]
                    )
                )
                if same_sample:
                    agreement: dict[str, Any] = {
                        "status": "not_evaluable_identical_effective_budget"
                    }
                else:
                    agreement = _ranking_stability(
                        left["grouped_shap"],
                        right["grouped_shap"],
                        score="mean_abs_shap",
                        protocol=protocol,
                    )
                budget_records.append(
                    {
                        "dataset": dataset,
                        "model_key": model_key,
                        "repeat": repeat,
                        "fold": fold,
                        "seed": seed,
                        "lower_budget_index": lower,
                        "upper_budget_index": upper,
                        "agreement": agreement,
                    }
                )

        maximum_budget = len(protocol.budgets)
        for left_seed, right_seed in zip(
            protocol.seeds[:-1], protocol.seeds[1:], strict=True
        ):
            left = lookup[
                (dataset, model_key, repeat, fold, left_seed, maximum_budget)
            ]
            right = lookup[
                (dataset, model_key, repeat, fold, right_seed, maximum_budget)
            ]
            seed_records.append(
                {
                    "dataset": dataset,
                    "model_key": model_key,
                    "repeat": repeat,
                    "fold": fold,
                    "left_seed": left_seed,
                    "right_seed": right_seed,
                    "budget_index": maximum_budget,
                    "agreement": _ranking_stability(
                        left["grouped_shap"],
                        right["grouped_shap"],
                        score="mean_abs_shap",
                        protocol=protocol,
                    ),
                }
            )

    evaluable = [
        row["agreement"]["status"]
        for row in budget_records + seed_records
        if row["agreement"]["status"] in {"passed", "failed"}
    ]
    overall = (
        "not_evaluable"
        if not evaluable
        else "passed"
        if all(status == "passed" for status in evaluable)
        else "failed"
    )
    return {
        "primary_gate_target": "grouped exact-SHAP global ranking",
        "budget_comparisons": budget_records,
        "successive_seed_comparisons": seed_records,
        "summary": {
            "status": overall,
            "n_evaluable": len(evaluable),
            "n_passed": evaluable.count("passed"),
            "n_failed": evaluable.count("failed"),
            "claim_permitted": overall == "passed",
        },
    }


def _three_stage_bootstrap(
    records: list[dict[str, Any]],
    value_key: str,
    *,
    n_bootstraps: int,
    seed: int,
) -> dict[str, Any]:
    finite = [row for row in records if row.get(value_key) is not None]
    if not finite:
        return {"estimate": None, "lower_95": None, "upper_95": None}
    by_cell: dict[tuple[int, int], list[float]] = {}
    for row in finite:
        by_cell.setdefault((int(row["repeat"]), int(row["fold"])), []).append(
            float(row[value_key])
        )
    cell_keys = sorted(by_cell)
    repeat_to_cells: dict[int, list[tuple[int, int]]] = {}
    for cell_key in cell_keys:
        repeat_to_cells.setdefault(cell_key[0], []).append(cell_key)
    repeats = np.asarray(sorted(repeat_to_cells), dtype=int)
    rng = np.random.default_rng(seed)
    estimates = np.empty(n_bootstraps, dtype=float)
    for index in range(n_bootstraps):
        sampled_repeats = rng.choice(repeats, size=len(repeats), replace=True)
        values: list[float] = []
        for repeat in sampled_repeats:
            candidates = repeat_to_cells[int(repeat)]
            sampled_cells = rng.choice(
                len(candidates), size=len(candidates), replace=True
            )
            values.extend(
                float(rng.choice(by_cell[candidates[cell_index]]))
                for cell_index in sampled_cells
            )
        estimates[index] = np.mean(values)
    observed = np.asarray([float(row[value_key]) for row in finite])
    return {
        "estimate": float(np.mean(observed)),
        "lower_95": float(np.percentile(estimates, 2.5)),
        "upper_95": float(np.percentile(estimates, 97.5)),
        "standard_deviation": float(np.std(observed, ddof=1))
        if len(observed) > 1
        else None,
        "n_outer_repeats": int(len(repeats)),
        "n_outer_cells": int(len(cell_keys)),
    }


def _group_convergence_status(
    convergence: dict[str, Any], dataset: str, model_key: str
) -> str:
    records = [
        row
        for section in ("budget_comparisons", "successive_seed_comparisons")
        for row in convergence.get(section, [])
        if row.get("dataset") == dataset and row.get("model_key") == model_key
        and row.get("agreement", {}).get("status") in {"passed", "failed"}
    ]
    if not records:
        return "not_evaluable"
    return (
        "passed"
        if all(row["agreement"]["status"] == "passed" for row in records)
        else "failed"
    )


def _agreement_uncertainty(
    comparisons: list[dict[str, Any]],
    protocol: ExplanationProtocol,
    convergence: dict[str, Any],
    *,
    expected_outer_cells: int,
    confirmatory_evidence: bool,
) -> list[dict[str, Any]]:
    final_budget = len(protocol.budgets)
    final_rows = [row for row in comparisons if row["budget_index"] == final_budget]
    groups = sorted({(row["dataset"], row["model_key"]) for row in final_rows})
    results: list[dict[str, Any]] = []
    for dataset, model_key in groups:
        selected = [
            row
            for row in final_rows
            if row["dataset"] == dataset and row["model_key"] == model_key
        ]
        metric_rows = [
            {
                "repeat": row["repeat"],
                "fold": row["fold"],
                "seed": row["seed"],
                **{
                    key: row["agreement"][key]
                    for key in ("spearman_rho", "kendall_tau", "top_k_jaccard")
                },
            }
            for row in selected
        ]
        cells = {(row["repeat"], row["fold"]) for row in metric_rows}
        result: dict[str, Any] = {
            "dataset": dataset,
            "model_key": model_key,
            "n_outer_cells": len(cells),
            "n_cell_seed_estimates": len(metric_rows),
            "method": (
                "descriptive three-stage bootstrap: resample outer repeats, "
                "folds within repeat, then one of the three seed estimates "
                "within each sampled cell"
            ),
            "bootstrap_replicates": protocol.uncertainty_bootstraps,
        }
        for metric in ("spearman_rho", "kendall_tau", "top_k_jaccard"):
            result[metric] = _three_stage_bootstrap(
                metric_rows,
                metric,
                n_bootstraps=protocol.uncertainty_bootstraps,
                seed=_stable_seed(
                    protocol.uncertainty_seed, dataset, model_key, metric
                ),
            )
        spearman = result["spearman_rho"]
        stability_status = _group_convergence_status(
            convergence, dataset, model_key
        )
        complete_cell_gate = len(cells) == expected_outer_cells
        result["sampling_stability_gate"] = stability_status
        result["expected_outer_cells"] = expected_outer_cells
        result["complete_outer_cell_gate"] = complete_cell_gate
        result["confirmatory_evidence_gate"] = confirmatory_evidence
        result["positive_same_model_agreement_supported"] = bool(
            confirmatory_evidence
            and complete_cell_gate
            and stability_status == "passed"
            and spearman["lower_95"] is not None
            and spearman["lower_95"] > 0.0
        )
        result["claim_rule"] = (
            "Positive same-model agreement is supported only for a confirmatory "
            "artifact with every planned outer cell, when every evaluable "
            "budget/seed stability comparison passes and the Spearman 95% "
            "interval is wholly above zero."
        )
        results.append(result)
    return results


def _paired_cross_model_agreement_difference(
    same_model: list[dict[str, Any]],
    cox_model: list[dict[str, Any]],
    protocol: ExplanationProtocol,
    same_convergence: dict[str, Any],
    cox_convergence: dict[str, Any],
    *,
    expected_outer_cells: int,
    confirmatory_evidence: bool,
) -> list[dict[str, Any]]:
    """Estimate paired same-Bayesian minus Cox agreement at the final budget."""
    final_budget = len(protocol.budgets)

    def keyed(rows: list[dict[str, Any]]) -> dict[tuple[Any, ...], dict[str, Any]]:
        return {
            (
                row["dataset"],
                row["model_key"],
                row["repeat"],
                row["fold"],
                row["seed"],
                row["budget_index"],
            ): row
            for row in rows
            if row["budget_index"] == final_budget
        }

    same_lookup = keyed(same_model)
    cox_lookup = keyed(cox_model)
    paired_keys = sorted(set(same_lookup) & set(cox_lookup))
    results: list[dict[str, Any]] = []
    for dataset, model_key in sorted({key[:2] for key in paired_keys}):
        keys = [
            key
            for key in paired_keys
            if key[0] == dataset and key[1] == model_key
        ]
        difference_rows: list[dict[str, Any]] = []
        for key in keys:
            same = same_lookup[key]
            cox = cox_lookup[key]
            if same["selection_sha256"] != cox["selection_sha256"]:
                raise RuntimeError(
                    "same-model and Cox agreement records are not paired selections"
                )
            row: dict[str, Any] = {
                "repeat": same["repeat"],
                "fold": same["fold"],
                "seed": same["seed"],
            }
            for metric in ("spearman_rho", "kendall_tau", "top_k_jaccard"):
                left = same["agreement"].get(metric)
                right = cox["agreement"].get(metric)
                row[metric] = (
                    None if left is None or right is None else float(left) - float(right)
                )
            difference_rows.append(row)

        result: dict[str, Any] = {
            "dataset": dataset,
            "model_key": model_key,
            "direction": "same-Bayesian-model agreement minus paired Cox agreement",
            "n_outer_cells": len(
                {(row["repeat"], row["fold"]) for row in difference_rows}
            ),
            "n_cell_seed_pairs": len(difference_rows),
            "method": (
                "paired descriptive three-stage bootstrap over outer repeats, "
                "folds within repeat and identical explanation seeds"
            ),
            "bootstrap_replicates": protocol.uncertainty_bootstraps,
        }
        for metric in ("spearman_rho", "kendall_tau", "top_k_jaccard"):
            result[metric] = _three_stage_bootstrap(
                difference_rows,
                metric,
                n_bootstraps=protocol.uncertainty_bootstraps,
                seed=_stable_seed(
                    protocol.uncertainty_seed,
                    "same_minus_cox",
                    dataset,
                    model_key,
                    metric,
                ),
            )
        spearman = result["spearman_rho"]
        same_stability = _group_convergence_status(
            same_convergence, dataset, model_key
        )
        cox_stability = _group_convergence_status(
            cox_convergence, dataset, model_key
        )
        result["same_model_sampling_stability_gate"] = same_stability
        result["cox_sampling_stability_gate"] = cox_stability
        complete_cell_gate = result["n_outer_cells"] == expected_outer_cells
        result["expected_outer_cells"] = expected_outer_cells
        result["complete_outer_cell_gate"] = complete_cell_gate
        result["confirmatory_evidence_gate"] = confirmatory_evidence
        result["stronger_same_model_agreement_supported"] = bool(
            confirmatory_evidence
            and complete_cell_gate
            and same_stability == "passed"
            and cox_stability == "passed"
            and spearman["lower_95"] is not None
            and spearman["lower_95"] > 0.0
        )
        result["claim_rule"] = (
            "The secondary stronger-agreement claim is permitted only for a "
            "confirmatory artifact with every planned paired outer cell, when "
            "same-model and Cox sampling-stability gates pass and the paired "
            "Spearman-difference 95% interval is wholly above zero."
        )
        results.append(result)
    return results


def _group_stability(
    comparisons: list[dict[str, Any]], protocol: ExplanationProtocol
) -> list[dict[str, Any]]:
    final_budget = len(protocol.budgets)
    final_rows = [row for row in comparisons if row["budget_index"] == final_budget]
    results: list[dict[str, Any]] = []
    for dataset, model_key in sorted(
        {(row["dataset"], row["model_key"]) for row in final_rows}
    ):
        selected = [
            row
            for row in final_rows
            if row["dataset"] == dataset and row["model_key"] == model_key
        ]
        for target, table_key, score_key in (
            (
                "posterior_expected_absolute_contribution",
                "grouped_intrinsic",
                "expected_abs_contribution",
            ),
            ("exact_linear_shap", "grouped_shap", "mean_abs_shap"),
        ):
            observations: list[dict[str, Any]] = []
            for row in selected:
                table = pd.DataFrame(row[table_key]).sort_values(
                    [score_key, "group"], ascending=[False, True]
                )
                for rank, item in enumerate(table.to_dict("records"), start=1):
                    observations.append(
                        {
                            "repeat": row["repeat"],
                            "fold": row["fold"],
                            "seed": row["seed"],
                            "group": item["group"],
                            "importance": item[score_key],
                            "rank": rank,
                            "top_five": float(rank <= protocol.top_k),
                        }
                    )
            for group in sorted({row["group"] for row in observations}):
                group_rows = [row for row in observations if row["group"] == group]
                results.append(
                    {
                        "dataset": dataset,
                        "model_key": model_key,
                        "target": target,
                        "group": group,
                        "n_cell_seed_estimates": len(group_rows),
                        "mean_importance": float(
                            np.mean([row["importance"] for row in group_rows])
                        ),
                        "rank": _three_stage_bootstrap(
                            group_rows,
                            "rank",
                            n_bootstraps=protocol.uncertainty_bootstraps,
                            seed=_stable_seed(
                                protocol.uncertainty_seed,
                                dataset,
                                model_key,
                                target,
                                group,
                                "rank",
                            ),
                        ),
                        "top_five_selection_frequency": _three_stage_bootstrap(
                            group_rows,
                            "top_five",
                            n_bootstraps=protocol.uncertainty_bootstraps,
                            seed=_stable_seed(
                                protocol.uncertainty_seed,
                                dataset,
                                model_key,
                                target,
                                group,
                                "top_five",
                            ),
                        ),
                    }
                )
    return results


def _protocol_record(protocol: ExplanationProtocol) -> dict[str, Any]:
    return {
        **asdict(protocol),
        "primary_intrinsic_estimand": (
            "posterior expected absolute contribution E(|x_j beta_j|)"
        ),
        "primary_post_hoc_estimand": (
            "mean absolute exact interventional SHAP attribution from "
            "shap.LinearExplainer on the same posterior-mean linear risk score"
        ),
        "sampling": (
            "separate seeded permutations without replacement for validation "
            "subjects and outer-training backgrounds; selections are nested "
            "across successive budgets and paired across Bayesian priors"
        ),
        "grouping": (
            "cell preprocessing feature_groups metadata; signed transformed terms "
            "are summed within subject and source group before absolute magnitude"
        ),
        "coalition_budget": (
            "not applicable: LinearExplainer is exact for the frozen linear risk model"
        ),
        "convergence_rule": (
            "successive grouped SHAP rankings require Spearman >= 0.95 and "
            "at least four common top-five groups"
        ),
    }


def analyze_frozen_run(
    run_dir: Path,
    project_root: Path,
    *,
    protocol: ExplanationProtocol | None = None,
) -> dict[str, Any]:
    """Analyze complete Bayesian cells without fitting or reconstructing a model."""
    protocol = protocol or ExplanationProtocol()
    run_dir = run_dir.resolve()
    project_root = project_root.resolve()
    manifest_path = run_dir / "manifest.json"
    completion_path = run_dir / "completion.json"
    manifest = _load_mapping(manifest_path)
    completion = _load_mapping(completion_path)
    _verify_content_hash(manifest, "manifest_content_sha256", manifest_path)
    _verify_content_hash(completion, "completion_content_sha256", completion_path)

    input_hashes = manifest.get("input_sha256")
    if not isinstance(input_hashes, dict):
        raise ValueError("run manifest has no input hash mapping")
    for relative in ("config/datasets.yaml", "config/confirmatory.yaml"):
        if relative in input_hashes:
            path = project_root / relative
            if sha256_file(path) != input_hashes[relative]:
                raise RuntimeError(
                    f"current {relative} does not match the frozen run manifest"
                )

    recorded_files = completion.get("all_stored_cell_hashes")
    if not isinstance(recorded_files, dict):
        raise ValueError("completion artifact has no stored-cell hash mapping")
    actual_paths = sorted((run_dir / "cells").glob("*/*/*.json"))
    actual_relative = {str(path.relative_to(run_dir)) for path in actual_paths}
    if actual_relative != set(recorded_files):
        raise RuntimeError("stored cell files do not match the completion inventory")
    if int(completion.get("stored_cells", -1)) != len(actual_paths):
        raise RuntimeError("stored cell count does not match the completion artifact")

    cells: list[tuple[Path, dict[str, Any]]] = []
    for path in actual_paths:
        relative = str(path.relative_to(run_dir))
        if sha256_file(path) != recorded_files[relative]:
            raise RuntimeError(f"stored cell file hash does not match: {path}")
        cell = _load_mapping(path)
        _verify_content_hash(cell, "cell_content_sha256", path)
        cells.append((path, cell))

    dataset_configs = _load_mapping(project_root / "config" / "datasets.yaml")
    run_protocol = manifest.get("run_config", {}).get("protocol", {})
    feature_set = run_protocol.get("feature_set")
    if not isinstance(feature_set, str):
        raise ValueError("run manifest does not identify its feature set")

    exclusions: list[dict[str, Any]] = []
    bayesian_cells: list[tuple[Path, dict[str, Any]]] = []
    secondary_models = sorted(
        {
            cell.get("model_key")
            for _, cell in cells
            if not str(cell.get("model_key", "")).startswith("bayesian_")
        }
    )
    cox_cells: dict[tuple[str, int, int], tuple[Path, dict[str, Any]]] = {}
    for path, cell in cells:
        if cell.get("model_key") == "cox_ph":
            key = (str(cell["dataset"]), int(cell["repeat"]), int(cell["fold"]))
            if key in cox_cells:
                raise RuntimeError(f"duplicate Cox cell for {key}")
            cox_cells[key] = (path, cell)
        if not str(cell.get("model_key", "")).startswith("bayesian_"):
            continue
        if cell.get("status") != "complete":
            exclusions.append(
                {
                    "cell": str(path.relative_to(run_dir)),
                    "status": cell.get("status"),
                    "reason": "only complete Bayesian cells may be interpreted",
                }
            )
            continue
        if cell.get("analysis_mode") == "confirmatory" and not cell.get(
            "model_details", {}
        ).get("diagnostics", {}).get("converged", False):
            exclusions.append(
                {
                    "cell": str(path.relative_to(run_dir)),
                    "status": "failed_diagnostic_recheck",
                    "reason": "confirmatory Bayesian diagnostics are not converged",
                }
            )
            continue
        bayesian_cells.append((path, cell))
    if not bayesian_cells:
        raise RuntimeError("the frozen run has no complete, interpretable Bayesian cells")

    cohort_cache: dict[str, tuple[pd.DataFrame, np.ndarray, dict[str, int]]] = {}
    fold_lineage: dict[tuple[str, int, int], dict[str, Any]] = {}
    selection_registry: dict[str, dict[str, Any]] = {}
    comparisons: list[dict[str, Any]] = []
    cox_comparisons: list[dict[str, Any]] = []
    cox_unavailable: dict[tuple[str, int, int], dict[str, Any]] = {}
    cell_hashes_used: dict[str, str] = {}

    for path, cell in bayesian_cells:
        dataset = str(cell["dataset"])
        if dataset not in dataset_configs:
            raise ValueError(f"cell references unknown dataset {dataset!r}")
        dataset_config = dataset_configs[dataset]
        raw_path = project_root / dataset_config["raw_file"]
        raw_hash = sha256_file(raw_path)
        if raw_hash != cell.get("dataset_sha256"):
            raise RuntimeError(f"{dataset} raw data do not match the cell hash")
        relative_raw = str(Path(dataset_config["raw_file"]))
        if input_hashes.get(relative_raw) != raw_hash:
            raise RuntimeError(f"{dataset} raw data do not match the run manifest")

        if dataset not in cohort_cache:
            raw, subject_ids = _load_raw_cohort(
                project_root, dataset, dataset_config
            )
            cohort_cache[dataset] = (
                raw,
                subject_ids,
                {str(subject_id): index for index, subject_id in enumerate(subject_ids)},
            )
        raw, all_subject_ids, id_to_position = cohort_cache[dataset]

        train_ids = [str(value) for value in cell["train_subject_ids"]]
        validation_ids = [str(value) for value in cell["validation_subject_ids"]]
        if len(train_ids) != int(cell["n_train"]) or len(validation_ids) != int(
            cell["n_validation"]
        ):
            raise RuntimeError("cell subject counts do not match its ID lists")
        if len(set(train_ids)) != len(train_ids) or len(set(validation_ids)) != len(
            validation_ids
        ):
            raise RuntimeError("cell contains duplicate subject identifiers")
        if set(train_ids) & set(validation_ids):
            raise RuntimeError("cell training and validation subjects overlap")
        if set(train_ids) | set(validation_ids) != set(all_subject_ids):
            raise RuntimeError("cell subject IDs do not partition the frozen cohort")
        prediction_ids = [str(value) for value in cell["predictions"]["subject_ids"]]
        if prediction_ids != validation_ids:
            raise RuntimeError("cell prediction order differs from validation ID order")

        fold_key = (dataset, int(cell["repeat"]), int(cell["fold"]))
        lineage = {
            "train_subject_ids": train_ids,
            "validation_subject_ids": validation_ids,
            "training_state_sha256": cell["preprocessing"][
                "training_state_sha256"
            ],
        }
        prior_lineage = fold_lineage.setdefault(fold_key, lineage)
        if prior_lineage != lineage:
            raise RuntimeError(
                "paired Bayesian cells do not share subjects and preprocessing state"
            )

        specification = _feature_spec(dataset_config, feature_set)
        processor = FoldFeaturePreprocessor.from_metadata(
            specification, cell["preprocessing"]
        )
        train_positions = [id_to_position[value] for value in train_ids]
        validation_positions = [id_to_position[value] for value in validation_ids]
        x_train = processor.transform(raw.iloc[train_positions]).reset_index(drop=True)
        x_validation = processor.transform(raw.iloc[validation_positions]).reset_index(
            drop=True
        )

        feature_names = list(processor.feature_names)
        beta_mapping = cell["model_details"].get("posterior_mean_beta")
        if not isinstance(beta_mapping, dict) or set(beta_mapping) != set(feature_names):
            raise ValueError("cell posterior-mean coefficients do not match its features")
        beta_mean = np.asarray([beta_mapping[name] for name in feature_names], float)
        if not np.isfinite(beta_mean).all():
            raise ValueError("cell posterior-mean coefficients are not finite")
        exact_group_record = cell["model_details"].get(
            "posterior_expected_absolute_group_contribution_by_subject"
        )
        if (
            manifest.get("run_config", {}).get("mode") == "confirmatory"
            and exact_group_record is None
        ):
            raise ValueError(
                "confirmatory Bayesian cell lacks exact posterior group contributions"
            )
        beta_abs: pd.Series | None = None
        unidentified: list[str] = []
        if exact_group_record is None:
            beta_abs, unidentified = recover_posterior_mean_abs_beta(
                x_validation,
                cell["model_details"]["posterior_expected_absolute_contribution"],
            )

        cox_beta: np.ndarray | None = None
        cox_path: Path | None = None
        cox_cell: dict[str, Any] | None = None
        cox_entry = cox_cells.get(fold_key)
        if cox_entry is None:
            cox_unavailable.setdefault(
                fold_key,
                {
                    "dataset": dataset,
                    "repeat": int(cell["repeat"]),
                    "fold": int(cell["fold"]),
                    "reason": "no frozen Cox cell exists for the paired outer fold",
                },
            )
        elif cox_entry[1].get("status") != "complete":
            cox_unavailable.setdefault(
                fold_key,
                {
                    "dataset": dataset,
                    "repeat": int(cell["repeat"]),
                    "fold": int(cell["fold"]),
                    "reason": (
                        "paired frozen Cox cell is not complete: "
                        f"{cox_entry[1].get('status')}"
                    ),
                },
            )
        else:
            cox_path, cox_cell = cox_entry
            if cox_cell.get("dataset_sha256") != raw_hash:
                raise RuntimeError("paired Cox cell has a different dataset hash")
            cox_train_ids = [str(value) for value in cox_cell["train_subject_ids"]]
            cox_validation_ids = [
                str(value) for value in cox_cell["validation_subject_ids"]
            ]
            cox_lineage = {
                "train_subject_ids": cox_train_ids,
                "validation_subject_ids": cox_validation_ids,
                "training_state_sha256": cox_cell["preprocessing"][
                    "training_state_sha256"
                ],
            }
            if cox_lineage != lineage:
                raise RuntimeError(
                    "paired Cox and Bayesian cells do not share subjects and preprocessing"
                )
            cox_prediction_ids = [
                str(value) for value in cox_cell["predictions"]["subject_ids"]
            ]
            if cox_prediction_ids != validation_ids:
                raise RuntimeError("Cox prediction order differs from paired validation IDs")
            cox_processor = FoldFeaturePreprocessor.from_metadata(
                specification, cox_cell["preprocessing"]
            )
            if cox_processor.training_state_sha256 != processor.training_state_sha256:
                raise RuntimeError("Cox and Bayesian preprocessing hashes differ")
            cox_beta = _coefficient_vector(
                cox_cell["model_details"].get("coefficient_summary"), feature_names
            )
            cell_hashes_used[
                str(cox_path.relative_to(run_dir))
            ] = cox_cell["cell_content_sha256"]

        selections = _paired_selections(
            train_ids,
            validation_ids,
            dataset=dataset,
            repeat=int(cell["repeat"]),
            fold=int(cell["fold"]),
            protocol=protocol,
        )
        for selection in selections:
            registry_record = {
                key: value
                for key, value in selection.items()
                if key not in {"validation_positions", "background_positions"}
            }
            prior_selection = selection_registry.setdefault(
                selection["selection_sha256"], registry_record
            )
            if prior_selection != registry_record:
                raise RuntimeError("selection hash collision detected")

            x_explain = x_validation.iloc[selection["validation_positions"]]
            x_background = x_train.iloc[selection["background_positions"]]
            shap_values = exact_linear_shap_values(
                beta_mean, x_background, x_explain
            )
            grouped_intrinsic = _exact_grouped_intrinsic_from_cell(
                cell["model_details"],
                selection["validation_positions"],
                processor.feature_groups,
                len(x_validation),
            )
            intrinsic_source = "stored_exact_full_posterior_group_contribution"
            if grouped_intrinsic is None:
                if beta_abs is None:
                    raise RuntimeError("posterior contribution fallback is unavailable")
                grouped_intrinsic = grouped_posterior_contribution(
                    x_explain, beta_abs, processor.feature_groups
                )
                intrinsic_source = "legacy_termwise_reconstruction_rehearsal_only"
            grouped_shap = grouped_shap_importance(
                shap_values, processor.feature_groups
            )
            agreement = compare_group_rankings(
                grouped_intrinsic,
                grouped_shap,
                top_k=protocol.top_k,
            )
            comparisons.append(
                {
                    "dataset": dataset,
                    "model_key": cell["model_key"],
                    "prior": str(cell["model_key"]).removeprefix("bayesian_"),
                    "repeat": int(cell["repeat"]),
                    "fold": int(cell["fold"]),
                    "cell_content_sha256": cell["cell_content_sha256"],
                    "preprocessing_state_sha256": processor.training_state_sha256,
                    "seed": selection["seed"],
                    "budget_index": selection["budget_index"],
                    "effective_validation_subjects": selection[
                        "effective_validation_subjects"
                    ],
                    "effective_training_background": selection[
                        "effective_training_background"
                    ],
                    "selection_sha256": selection["selection_sha256"],
                    "zero_validation_terms_with_unidentified_beta_abs": unidentified,
                    "grouped_intrinsic_source": intrinsic_source,
                    "grouped_intrinsic": grouped_intrinsic.to_dict("records"),
                    "grouped_shap": grouped_shap.to_dict("records"),
                    "agreement": agreement,
                }
            )
            if cox_beta is not None and cox_cell is not None and cox_path is not None:
                cox_shap_values = exact_linear_shap_values(
                    cox_beta, x_background, x_explain
                )
                grouped_cox_shap = grouped_shap_importance(
                    cox_shap_values, processor.feature_groups
                )
                cox_comparisons.append(
                    {
                        "dataset": dataset,
                        "model_key": cell["model_key"],
                        "prior": str(cell["model_key"]).removeprefix("bayesian_"),
                        "comparison_target": "Cox PH exact linear SHAP",
                        "repeat": int(cell["repeat"]),
                        "fold": int(cell["fold"]),
                        "bayesian_cell_content_sha256": cell[
                            "cell_content_sha256"
                        ],
                        "cox_cell_content_sha256": cox_cell[
                            "cell_content_sha256"
                        ],
                        "preprocessing_state_sha256": processor.training_state_sha256,
                        "seed": selection["seed"],
                        "budget_index": selection["budget_index"],
                        "effective_validation_subjects": selection[
                            "effective_validation_subjects"
                        ],
                        "effective_training_background": selection[
                            "effective_training_background"
                        ],
                        "selection_sha256": selection["selection_sha256"],
                        "grouped_intrinsic_source": intrinsic_source,
                        "grouped_intrinsic": grouped_intrinsic.to_dict("records"),
                        "grouped_shap": grouped_cox_shap.to_dict("records"),
                        "agreement": compare_group_rankings(
                            grouped_intrinsic,
                            grouped_cox_shap,
                            top_k=protocol.top_k,
                        ),
                    }
                )
        cell_hashes_used[str(path.relative_to(run_dir))] = cell["cell_content_sha256"]

    convergence = _convergence_records(comparisons, protocol)
    cox_status = (
        "complete"
        if len(cox_comparisons) == len(comparisons)
        else "partial"
        if cox_comparisons
        else "unavailable"
    )
    cox_convergence = (
        _convergence_records(cox_comparisons, protocol)
        if cox_comparisons
        else {
            "primary_gate_target": "not applicable to unavailable Cox comparison",
            "budget_comparisons": [],
            "successive_seed_comparisons": [],
            "summary": {
                "status": "not_evaluable",
                "n_evaluable": 0,
                "n_passed": 0,
                "n_failed": 0,
                "claim_permitted": False,
            },
        }
    )
    run_config = manifest.get("run_config", {})
    analysis_mode = run_config.get("mode")
    confirmatory_evidence = analysis_mode == "confirmatory"
    repeats = run_config.get("outer_repeats")
    splits = run_config.get("outer_splits")
    fold_limit = run_config.get("fold_limit_per_dataset")
    if confirmatory_evidence:
        if not isinstance(repeats, int) or not isinstance(splits, int):
            raise ValueError("confirmatory run does not declare its outer grid")
        expected_outer_cells = repeats * splits
        if fold_limit is not None:
            raise ValueError("confirmatory explanation source cannot limit outer folds")
    elif isinstance(repeats, int) and isinstance(splits, int):
        expected_outer_cells = repeats * splits
        if fold_limit is not None:
            expected_outer_cells = min(expected_outer_cells, int(fold_limit))
    else:
        expected_outer_cells = max(
            1,
            len(
                {
                    (row["repeat"], row["fold"])
                    for row in comparisons
                }
            ),
        )
    agreement_uncertainty = _agreement_uncertainty(
        comparisons,
        protocol,
        convergence,
        expected_outer_cells=expected_outer_cells,
        confirmatory_evidence=confirmatory_evidence,
    )
    cox_agreement_uncertainty = (
        _agreement_uncertainty(
            cox_comparisons,
            protocol,
            cox_convergence,
            expected_outer_cells=expected_outer_cells,
            confirmatory_evidence=confirmatory_evidence,
        )
        if cox_comparisons
        else []
    )
    paired_same_minus_cox = (
        _paired_cross_model_agreement_difference(
            comparisons,
            cox_comparisons,
            protocol,
            convergence,
            cox_convergence,
            expected_outer_cells=expected_outer_cells,
            confirmatory_evidence=confirmatory_evidence,
        )
        if cox_comparisons
        else []
    )
    result: dict[str, Any] = {
        "schema_version": "1.0.0",
        "analysis": "confirmatory_explainability_from_frozen_cells",
        "analysis_mode": manifest.get("run_config", {}).get("mode"),
        "evidence_status": (
            "confirmatory"
            if manifest.get("run_config", {}).get("mode") == "confirmatory"
            else "rehearsal_only"
        ),
        "source_run": {
            "directory_name": run_dir.name,
            "manifest_content_sha256": manifest["manifest_content_sha256"],
            "completion_content_sha256": completion["completion_content_sha256"],
            "cell_content_hashes_used": cell_hashes_used,
            "verified_input_hashes": {
                "config/datasets.yaml": input_hashes.get("config/datasets.yaml"),
                **(
                    {
                        "config/confirmatory.yaml": input_hashes[
                            "config/confirmatory.yaml"
                        ]
                    }
                    if "config/confirmatory.yaml" in input_hashes
                    else {}
                ),
                **{
                    str(dataset_configs[key]["raw_file"]): input_hashes.get(
                        str(dataset_configs[key]["raw_file"])
                    )
                    for key in sorted(cohort_cache)
                },
            },
            "feature_set": feature_set,
        },
        "protocol": _protocol_record(protocol),
        "selection_registry": sorted(
            selection_registry.values(),
            key=lambda row: (
                row["dataset"],
                row["repeat"],
                row["fold"],
                row["seed"],
                row["budget_index"],
            ),
        ),
        "comparisons": comparisons,
        "convergence": convergence,
        "agreement_uncertainty": agreement_uncertainty,
        "group_stability": _group_stability(comparisons, protocol),
        "excluded_bayesian_cells": exclusions,
        "secondary_cross_model_analysis": {
            "available_cell_model_keys": secondary_models,
            "cox_ph": {
                "status": cox_status,
                "estimand": (
                    "grouped Bayesian posterior expected absolute contribution versus "
                    "grouped exact SHAP from the paired frozen Cox PH linear risk score"
                ),
                "claim_role": "secondary; never the primary agreement claim basis",
                "comparisons": cox_comparisons,
                "convergence": cox_convergence,
                "agreement_uncertainty": cox_agreement_uncertainty,
                "paired_same_model_minus_cox": paired_same_minus_cox,
                "unavailable_folds": sorted(
                    cox_unavailable.values(),
                    key=lambda row: (row["dataset"], row["repeat"], row["fold"]),
                ),
            },
            "random_survival_forest": {
                "status": "formally_dropped_unavailable",
                "frozen_cells_present": "random_survival_forest" in secondary_models,
                "reason": (
                    "frozen RSF cells do not serialize reproducible fitted-tree state; "
                    "the immutable-cell protocol prohibits refitting"
                ),
            },
        },
        "interpretation_limits": [
            "Agreement is model-conditional ranking agreement, not causal truth.",
            "No treatment benefit, feature truth, clinical utility or deployment claim is supported.",
            "Grouped posterior scores use stored full-posterior signed group sums before taking absolute values; they remain model-conditional importance, not feature truth.",
            "Across-fold/seed intervals are descriptive stability summaries, not independent-sample confidence intervals.",
            "Exact LinearExplainer has no coalition Monte Carlo budget; randomness enters only through recorded subject and background samples.",
            "Cox agreement is a secondary cross-model comparison between different fitted risk models.",
            "RSF SHAP is unavailable from the frozen artifacts and was not approximated or refitted.",
        ],
    }
    result["result_content_sha256"] = canonical_json_hash(_json_safe(result))
    return result
