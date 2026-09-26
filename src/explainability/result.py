"""Assemble the frozen explanation result and its descriptive claim gates."""

from __future__ import annotations

from typing import Any

from src.explainability.cell_explanation import ExplanationRecords
from src.explainability.protocol import ExplanationProtocol, protocol_record
from src.explainability.source_run import CellInventory, SourceRun
from src.explainability.stability import convergence_records, unavailable_convergence
from src.explainability.uncertainty import (
    agreement_uncertainty,
    group_stability,
    paired_cross_model_agreement_difference,
)
from src.utils.io import json_safe
from src.utils.reproducibility import canonical_json_hash


def _expected_outer_cells(source: SourceRun, comparisons: list[dict[str, Any]]) -> int:
    """Read the planned outer grid, allowing a fold limit only for rehearsal evidence."""
    run_config = source.manifest.get("run_config", {})
    repeats = run_config.get("outer_repeats")
    splits = run_config.get("outer_splits")
    fold_limit = run_config.get("fold_limit_per_dataset")
    if run_config.get("mode") == "confirmatory":
        if not isinstance(repeats, int) or not isinstance(splits, int):
            raise ValueError("confirmatory run does not declare its outer grid")
        if fold_limit is not None:
            raise ValueError("confirmatory explanation source cannot limit outer folds")
        return repeats * splits
    if isinstance(repeats, int) and isinstance(splits, int):
        expected = repeats * splits
        return min(expected, int(fold_limit)) if fold_limit is not None else expected
    return max(1, len({(row["repeat"], row["fold"]) for row in comparisons}))


def _source_record(source: SourceRun, records: ExplanationRecords) -> dict[str, Any]:
    """Record the source manifest, cells and raw inputs used by the explanation."""
    input_hashes = source.input_hashes
    return {
        "directory_name": source.run_dir.name,
        "manifest_content_sha256": source.manifest["manifest_content_sha256"],
        "completion_content_sha256": source.completion["completion_content_sha256"],
        "cell_content_hashes_used": records.cell_hashes_used,
        "verified_input_hashes": {
            "config/datasets.yaml": input_hashes.get("config/datasets.yaml"),
            **(
                {"config/confirmatory.yaml": input_hashes["config/confirmatory.yaml"]}
                if "config/confirmatory.yaml" in input_hashes
                else {}
            ),
            **{
                str(source.dataset_configs[key]["raw_file"]): input_hashes.get(
                    str(source.dataset_configs[key]["raw_file"])
                )
                for key in sorted(records.cohorts)
            },
        },
        "feature_set": source.feature_set,
    }


def _cox_analysis(
    records: ExplanationRecords,
    protocol: ExplanationProtocol,
    convergence: dict[str, Any],
    cox_convergence: dict[str, Any],
    inference_options: dict[str, Any],
) -> dict[str, Any]:
    """Assemble the secondary paired Cox agreement summaries."""
    cox = records.cox_comparisons
    return {
        "status": (
            "complete"
            if len(cox) == len(records.comparisons)
            else "partial"
            if cox
            else "unavailable"
        ),
        "estimand": (
            "grouped Bayesian posterior expected absolute contribution versus "
            "grouped exact SHAP from the paired frozen Cox PH linear risk score"
        ),
        "claim_role": "secondary; never the primary agreement claim basis",
        "comparisons": cox,
        "convergence": cox_convergence,
        "agreement_uncertainty": (
            agreement_uncertainty(cox, protocol, cox_convergence, **inference_options)
            if cox
            else []
        ),
        "paired_same_model_minus_cox": (
            paired_cross_model_agreement_difference(
                records.comparisons,
                cox,
                protocol,
                convergence,
                cox_convergence,
                **inference_options,
            )
            if cox
            else []
        ),
        "unavailable_folds": sorted(
            records.cox_unavailable.values(),
            key=lambda row: (row["dataset"], row["repeat"], row["fold"]),
        ),
    }


def _secondary_analysis(inventory: CellInventory, cox_analysis: dict[str, Any]) -> dict[str, Any]:
    """Record the Cox comparison and the explicitly unavailable forest explanation."""
    return {
        "available_cell_model_keys": inventory.secondary_models,
        "cox_ph": cox_analysis,
        "random_survival_forest": {
            "status": "formally_dropped_unavailable",
            "frozen_cells_present": "random_survival_forest" in inventory.secondary_models,
            "reason": (
                "frozen RSF cells do not serialize reproducible fitted-tree state; "
                "the immutable-cell protocol prohibits refitting"
            ),
        },
    }


def build_result(
    source: SourceRun,
    inventory: CellInventory,
    records: ExplanationRecords,
    protocol: ExplanationProtocol,
) -> dict[str, Any]:
    """Summarise comparison rows and preserve the result schema and content hash.

    Args:
        source: Verified frozen run.
        inventory: Interpretable cells, exclusions and comparator availability.
        records: Paired explanation rows and their lineage.
        protocol: Frozen sampling and descriptive-bootstrap controls.

    Returns:
        The complete result mapping, including all failed claim gates.
    """
    convergence = convergence_records(records.comparisons, protocol)
    cox_convergence = (
        convergence_records(records.cox_comparisons, protocol)
        if records.cox_comparisons
        else unavailable_convergence()
    )
    analysis_mode = source.manifest.get("run_config", {}).get("mode")
    inference_options = {
        "expected_outer_cells": _expected_outer_cells(source, records.comparisons),
        "confirmatory_evidence": analysis_mode == "confirmatory",
    }
    cox_analysis = _cox_analysis(records, protocol, convergence, cox_convergence, inference_options)
    result: dict[str, Any] = {
        "schema_version": "1.0.0",
        "analysis": "confirmatory_explainability_from_frozen_cells",
        "analysis_mode": analysis_mode,
        "evidence_status": "confirmatory" if analysis_mode == "confirmatory" else "rehearsal_only",
        "source_run": _source_record(source, records),
        "protocol": protocol_record(protocol),
        "selection_registry": sorted(
            records.selection_registry.values(),
            key=lambda row: (
                row["dataset"],
                row["repeat"],
                row["fold"],
                row["seed"],
                row["budget_index"],
            ),
        ),
        "comparisons": records.comparisons,
        "convergence": convergence,
        "agreement_uncertainty": agreement_uncertainty(
            records.comparisons, protocol, convergence, **inference_options
        ),
        "group_stability": group_stability(records.comparisons, protocol),
        "excluded_bayesian_cells": inventory.exclusions,
        "secondary_cross_model_analysis": _secondary_analysis(inventory, cox_analysis),
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
    result["result_content_sha256"] = canonical_json_hash(json_safe(result))
    return result
