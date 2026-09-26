"""Analyse immutable confirmatory cells through verification, sampling and explanation stages."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.data.fold_preprocessing import FoldFeaturePreprocessor
from src.explainability.cell_explanation import (
    ExplanationRecords,
    explain_selection,
    prepare_cell_features,
)
from src.explainability.cell_explanation import (
    stored_grouped_posterior_contribution as _exact_grouped_intrinsic_from_cell,
)
from src.explainability.posterior_analysis import (
    compare_group_rankings,
    grouped_posterior_contribution,
    recover_posterior_mean_abs_beta,
)
from src.explainability.protocol import (
    ExplanationProtocol,
    SamplingBudget,
    _stable_seed,
)
from src.explainability.protocol import (
    protocol_record as _protocol_record,
)
from src.explainability.result import build_result
from src.explainability.sampling import paired_selections as _paired_selections
from src.explainability.sampling import register_selection
from src.explainability.shap_analysis import exact_linear_shap_values, grouped_shap_importance
from src.explainability.source_run import (
    CellInventory,
    SourceRun,
    _coefficient_vector,
    _load_raw_cohort,
    _verify_content_hash,
    classify_cells,
    cox_unavailable_reason,
    load_cohort,
    pair_cox_cell,
    verify_cell_lineage,
    verify_raw_data,
    verify_source_run,
)
from src.explainability.source_run import (
    feature_specification as _feature_spec,
)
from src.explainability.stability import (
    _ranking_stability,
)
from src.explainability.stability import (
    convergence_records as _convergence_records,
)
from src.explainability.stability import (
    model_convergence_status as _group_convergence_status,
)
from src.explainability.uncertainty import (
    agreement_uncertainty as _agreement_uncertainty,
)
from src.explainability.uncertainty import (
    group_stability as _group_stability,
)
from src.explainability.uncertainty import (
    paired_cross_model_agreement_difference as _paired_cross_model_agreement_difference,
)
from src.explainability.uncertainty import (
    three_stage_bootstrap as _three_stage_bootstrap,
)
from src.utils.io import json_safe as _json_safe
from src.utils.io import read_mapping as _load_mapping
from src.utils.io import write_json_atomic
from src.utils.reproducibility import canonical_json_hash, sha256_file

__all__ = [
    "ExplanationProtocol",
    "FoldFeaturePreprocessor",
    "SamplingBudget",
    "analyze_frozen_run",
    "canonical_json_hash",
    "compare_group_rankings",
    "exact_linear_shap_values",
    "grouped_posterior_contribution",
    "grouped_shap_importance",
    "recover_posterior_mean_abs_beta",
    "sha256_file",
    "write_explainability_result",
    "_agreement_uncertainty",
    "_coefficient_vector",
    "_convergence_records",
    "_exact_grouped_intrinsic_from_cell",
    "_feature_spec",
    "_group_convergence_status",
    "_group_stability",
    "_json_safe",
    "_load_mapping",
    "_load_raw_cohort",
    "_paired_cross_model_agreement_difference",
    "_paired_selections",
    "_protocol_record",
    "_ranking_stability",
    "_stable_seed",
    "_three_stage_bootstrap",
    "_verify_content_hash",
]


def write_explainability_result(path: Path, result: dict[str, Any]) -> None:
    """Atomically write a new result without overwriting prior evidence.

    Args:
        path: New result file outside the immutable source run.
        result: Explanation result mapping.
    """
    if path.exists():
        raise FileExistsError(f"explainability result already exists: {path}")
    write_json_atomic(path, result, overwrite=False)


def _explain_cell(
    source: SourceRun,
    inventory: CellInventory,
    path: Path,
    cell: dict[str, Any],
    records: ExplanationRecords,
    protocol: ExplanationProtocol,
) -> None:
    """Verify one Bayesian cell and append its paired explanation records."""
    raw_hash = verify_raw_data(source, cell)
    cohort = load_cohort(source, str(cell["dataset"]), records.cohorts, loader=_load_raw_cohort)
    lineage = verify_cell_lineage(cell, cohort, records.fold_lineage)
    features = prepare_cell_features(source, cell, cohort, lineage)
    cox_entry = inventory.cox_cells.get(lineage.fold_key)
    unavailable_reason = cox_unavailable_reason(cox_entry)
    paired_cox = None
    if unavailable_reason is not None:
        records.cox_unavailable.setdefault(
            lineage.fold_key,
            {
                "dataset": str(cell["dataset"]),
                "repeat": int(cell["repeat"]),
                "fold": int(cell["fold"]),
                "reason": unavailable_reason,
            },
        )
    else:
        assert cox_entry is not None
        paired_cox = pair_cox_cell(
            source,
            cox_entry,
            raw_hash=raw_hash,
            lineage=lineage,
            feature_spec=features.feature_spec,
            processor=features.processor,
        )
        records.cell_hashes_used[paired_cox.relative_path] = paired_cox.cell["cell_content_sha256"]
    selections = _paired_selections(
        lineage.train_ids,
        lineage.validation_ids,
        dataset=str(cell["dataset"]),
        repeat=int(cell["repeat"]),
        fold=int(cell["fold"]),
        protocol=protocol,
    )
    for selection in selections:
        register_selection(records.selection_registry, selection)
        comparison, cox_comparison = explain_selection(
            cell,
            features,
            selection,
            protocol.top_k,
            paired_cox,
            linear_shap=exact_linear_shap_values,
        )
        records.comparisons.append(comparison)
        if cox_comparison is not None:
            records.cox_comparisons.append(cox_comparison)
    records.cell_hashes_used[source.relative(path)] = cell["cell_content_sha256"]


def analyze_frozen_run(
    run_dir: Path,
    project_root: Path,
    *,
    protocol: ExplanationProtocol | None = None,
) -> dict[str, Any]:
    """Analyse complete Bayesian cells without fitting or reconstructing a model.

    Source hashes, subject pairing and stored preprocessing are checked before
    any explanation is interpreted. Failed diagnostic cells and failed
    sampling-stability gates remain explicit in the result.

    Args:
        run_dir: Immutable run containing manifest, completion and stored cells.
        project_root: Repository containing the frozen configuration and raw data.
        protocol: Frozen explanation settings; use defaults when omitted.

    Returns:
        Explanation comparisons, descriptive uncertainty, lineage and claim gates.
    """
    protocol = protocol or ExplanationProtocol()
    source = verify_source_run(run_dir.resolve(), project_root.resolve())
    inventory = classify_cells(source)
    records = ExplanationRecords()
    for path, cell in inventory.bayesian_cells:
        _explain_cell(source, inventory, path, cell, records, protocol)
    return build_result(source, inventory, records, protocol)
