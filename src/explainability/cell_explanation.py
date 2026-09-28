"""Compute exact linear SHAP and read grouped posterior contributions for frozen cells.

SHAP means Shapley additive explanations. Features come from raw cohorts and
stored preprocessing. Selected subjects share
a training background across Bayesian and Cox scores; signed contributions are
grouped before their absolute magnitude is averaged.

For one selection of a Bayesian cell, :func:`explain_selection` builds two
grouped importance tables and compares them:

- *Intrinsic*: the posterior expected absolute group contribution
  ``E_s|sum_{j in g} x_ij beta_j^(s)|``, the average over posterior draws
  ``s`` of the size of the group's contribution to subject ``i``'s log
  relative hazard, then averaged over the selected subjects. It uses the
  whole posterior and measures each contribution from ``x = 0`` on the
  transformed feature scale. The confirmatory cell stored these values for
  every validation subject when it was fitted, so this module only averages
  the stored rows.
- *Post-hoc*: grouped mean absolute SHAP on the posterior-mean risk score
  ``x . E(beta)``, measured from the background mean. It summarises one
  point estimate of the model, not the posterior.

The two therefore describe the same fitted model in different ways, and their
agreement is model-conditional. The Cox comparison keeps the intrinsic table
and replaces the post-hoc one with SHAP on the paired Cox coefficients.

:func:`prepare_cell_features` is called once per cell and
:func:`explain_selection` once per selection, both from
:mod:`src.explainability.frozen_cells`."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from src.data.fold_preprocessing import FoldFeaturePreprocessor
from src.explainability.posterior_analysis import (
    compare_group_rankings,
    grouped_posterior_contribution,
    recover_posterior_mean_abs_beta,
)
from src.explainability.shap_analysis import exact_linear_shap_values, grouped_shap_importance
from src.explainability.source_run import (
    CellLineage,
    Cohort,
    FoldKey,
    PairedCox,
    SourceRun,
    feature_specification,
)

# Key under a Bayesian cell's model_details that holds the stored per-subject
# group contributions, and the two labels recorded in each comparison row to
# say where its intrinsic table came from.
STORED_GROUP_CONTRIBUTION_KEY = "posterior_expected_absolute_group_contribution_by_subject"
STORED_SOURCE = "stored_exact_full_posterior_group_contribution"
LEGACY_SOURCE = "legacy_termwise_reconstruction_rehearsal_only"


@dataclass
class ExplanationRecords:
    """Everything collected while the Bayesian cells are explained one by one.

    Attributes:
        cohorts: Raw cohorts loaded so far, keyed by dataset.
        fold_lineage: Subjects and preprocessing hash of each outer fold.
        selection_registry: Every selection, keyed by its hash.
        comparisons: Bayesian intrinsic-versus-own-SHAP rows.
        cox_comparisons: Bayesian intrinsic-versus-Cox-SHAP rows.
        cox_unavailable: Why a fold has no usable Cox partner.
        cell_hashes_used: Content hash of every cell that was read.
    """

    cohorts: dict[str, Cohort] = field(default_factory=dict)
    fold_lineage: dict[FoldKey, dict[str, Any]] = field(default_factory=dict)
    selection_registry: dict[str, dict[str, Any]] = field(default_factory=dict)
    comparisons: list[dict[str, Any]] = field(default_factory=list)
    cox_comparisons: list[dict[str, Any]] = field(default_factory=list)
    cox_unavailable: dict[FoldKey, dict[str, Any]] = field(default_factory=dict)
    cell_hashes_used: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CellFeatures:
    """A Bayesian cell's transformed features and posterior summaries.

    Attributes:
        feature_spec: Feature specification the preprocessor was restored with.
        processor: The cell's restored fold preprocessor.
        x_train: Transformed outer-training rows, in cell order.
        x_validation: Transformed outer-validation rows, in cell order.
        posterior_mean_beta: Posterior-mean coefficients in feature order.
        legacy_beta_abs: ``E(|beta_j|)`` recovered for rehearsal cells without
            stored group contributions; ``None`` otherwise.
        unidentified_terms: Terms whose ``E(|beta_j|)`` could not be recovered
            because they are zero for every validation subject.
    """

    feature_spec: dict[str, Any]
    processor: FoldFeaturePreprocessor
    x_train: pd.DataFrame
    x_validation: pd.DataFrame
    posterior_mean_beta: np.ndarray
    legacy_beta_abs: pd.Series | None
    unidentified_terms: list[str]


def _posterior_mean_beta(cell: dict[str, Any], feature_names: list[str]) -> np.ndarray:
    """Read the stored posterior-mean coefficients in feature order.

    Raises:
        ValueError: If the coefficients do not match the features or are not
            finite.
    """
    beta_mapping = cell["model_details"].get("posterior_mean_beta")
    if not isinstance(beta_mapping, dict) or set(beta_mapping) != set(feature_names):
        raise ValueError("cell posterior-mean coefficients do not match its features")
    beta_mean = np.asarray([beta_mapping[name] for name in feature_names], float)
    if not np.isfinite(beta_mean).all():
        raise ValueError("cell posterior-mean coefficients are not finite")
    return beta_mean


def _legacy_beta_abs(
    source: SourceRun, cell: dict[str, Any], x_validation: pd.DataFrame
) -> tuple[pd.Series | None, list[str]]:
    """Recover ``E(|beta_j|)`` only for a rehearsal cell without stored group contributions.

    A confirmatory cell must store its exact group contributions, so this
    raises instead of falling back.

    Returns:
        ``(None, [])`` when the cell stores group contributions; otherwise the
        result of :func:`~src.explainability.posterior_analysis.recover_posterior_mean_abs_beta`.

    Raises:
        ValueError: If a confirmatory run's cell lacks stored group
            contributions.
    """
    exact_group_record = cell["model_details"].get(STORED_GROUP_CONTRIBUTION_KEY)
    if (
        source.manifest.get("run_config", {}).get("mode") == "confirmatory"
        and exact_group_record is None
    ):
        raise ValueError("confirmatory Bayesian cell lacks exact posterior group contributions")
    if exact_group_record is not None:
        return None, []
    return recover_posterior_mean_abs_beta(
        x_validation,
        cell["model_details"]["posterior_expected_absolute_contribution"],
    )


def prepare_cell_features(
    source: SourceRun, cell: dict[str, Any], cohort: Cohort, lineage: CellLineage
) -> CellFeatures:
    """Rebuild a Bayesian cell's features from raw data and its frozen preprocessing.

    Restoring the preprocessor checks its state hash, so the current feature
    specification must be the one the cell was fitted with.

    Args:
        source: The verified run.
        cell: The Bayesian cell.
        cohort: The cell's raw cohort.
        lineage: The cell's verified subject lists.

    Returns:
        The transformed training and validation rows in cell order, the
        posterior-mean coefficients and, for rehearsal cells only, the
        recovered ``E(|beta_j|)``.

    Raises:
        ValueError: If the preprocessing state hash or the coefficients fail
            their checks, or a confirmatory cell lacks stored group
            contributions.
        RuntimeError: If a rehearsal cell's term-wise contributions cannot be
            reconstructed.
    """
    dataset_config = source.dataset_configs[str(cell["dataset"])]
    specification = feature_specification(dataset_config, source.feature_set)
    processor = FoldFeaturePreprocessor.from_metadata(specification, cell["preprocessing"])
    train_positions = [cohort.positions[value] for value in lineage.train_ids]
    validation_positions = [cohort.positions[value] for value in lineage.validation_ids]
    x_train = processor.transform(cohort.raw.iloc[train_positions]).reset_index(drop=True)
    x_validation = processor.transform(cohort.raw.iloc[validation_positions]).reset_index(drop=True)
    beta_mean = _posterior_mean_beta(cell, list(processor.feature_names))
    beta_abs, unidentified = _legacy_beta_abs(source, cell, x_validation)
    return CellFeatures(
        feature_spec=specification,
        processor=processor,
        x_train=x_train,
        x_validation=x_validation,
        posterior_mean_beta=beta_mean,
        legacy_beta_abs=beta_abs,
        unidentified_terms=unidentified,
    )


def stored_grouped_posterior_contribution(
    model_details: dict[str, Any],
    selected_positions: list[int],
    feature_groups: dict[str, str],
    n_validation: int,
) -> pd.DataFrame | None:
    """Average the stored per-subject group contributions over the selected subjects.

    The cell stores ``E_s|sum_{j in g} x_ij beta_j^(s)|`` for every
    validation subject ``i`` and group ``g``, computed from the full
    posterior when the model was fitted. Its rows follow the cell's
    validation order, which is why selection positions index them directly.

    Args:
        model_details: The cell's ``model_details``.
        selected_positions: Positions of the selected validation subjects.
        feature_groups: Map from transformed term to source-variable group.
        n_validation: Number of validation subjects in the cell.

    Returns:
        ``group`` and ``expected_abs_contribution``, largest first with ties
        broken by group name, or ``None`` when the cell stores no group
        contributions.

    Raises:
        ValueError: If the stored record is not a mapping, its groups differ
            from the preprocessing groups, or its values have the wrong shape,
            are negative or are not finite.
    """
    record = model_details.get(STORED_GROUP_CONTRIBUTION_KEY)
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
        pd.DataFrame({"group": group_names, "expected_abs_contribution": means})
        .sort_values(["expected_abs_contribution", "group"], ascending=[False, True])
        .reset_index(drop=True)
    )


def _grouped_intrinsic(
    cell: dict[str, Any],
    features: CellFeatures,
    selection: dict[str, Any],
    x_explain: pd.DataFrame,
) -> tuple[pd.DataFrame, str]:
    """Return the grouped posterior contribution of a selection and where it came from.

    Stored full-posterior values are used when present; otherwise the
    term-wise rehearsal reconstruction is used and labelled as such.
    """
    grouped = stored_grouped_posterior_contribution(
        cell["model_details"],
        selection["validation_positions"],
        features.processor.feature_groups,
        len(features.x_validation),
    )
    if grouped is not None:
        return grouped, STORED_SOURCE
    if features.legacy_beta_abs is None:
        raise RuntimeError("posterior contribution fallback is unavailable")
    grouped = grouped_posterior_contribution(
        x_explain, features.legacy_beta_abs, features.processor.feature_groups
    )
    return grouped, LEGACY_SOURCE


def _selection_fields(
    cell: dict[str, Any],
    features: CellFeatures,
    selection: dict[str, Any],
    intrinsic_source: str,
) -> dict[str, Any]:
    """Return the identifying fields shared by the Bayesian and Cox comparison rows."""
    return {
        "dataset": str(cell["dataset"]),
        "model_key": cell["model_key"],
        "prior": str(cell["model_key"]).removeprefix("bayesian_"),
        "repeat": int(cell["repeat"]),
        "fold": int(cell["fold"]),
        "preprocessing_state_sha256": features.processor.training_state_sha256,
        "seed": selection["seed"],
        "budget_index": selection["budget_index"],
        "effective_validation_subjects": selection["effective_validation_subjects"],
        "effective_training_background": selection["effective_training_background"],
        "selection_sha256": selection["selection_sha256"],
        "grouped_intrinsic_source": intrinsic_source,
    }


def explain_selection(
    cell: dict[str, Any],
    features: CellFeatures,
    selection: dict[str, Any],
    protocol_top_k: int,
    paired_cox: PairedCox | None,
    *,
    linear_shap: Callable[[np.ndarray, pd.DataFrame, pd.DataFrame], pd.DataFrame] = (
        exact_linear_shap_values
    ),
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Explain one selection with the posterior mean and, if available, with Cox.

    The Bayesian row compares the intrinsic table with SHAP on the
    posterior-mean coefficients. The Cox row compares the same intrinsic
    table with SHAP on the paired Cox coefficients, using the same subjects
    and background, so the two rows differ only in the post-hoc model.

    Args:
        cell: The Bayesian cell.
        features: The cell's rebuilt features.
        selection: One record from :func:`~src.explainability.sampling.paired_selections`.
        protocol_top_k: Size of the top-ranked group set.
        paired_cox: The fold's Cox cell, or ``None`` when it has none.
        linear_shap: Exact linear-attribution function used for both models.

    Returns:
        The Bayesian comparison row and the Cox comparison row, which is
        ``None`` without a Cox partner.
    """
    x_explain = features.x_validation.iloc[selection["validation_positions"]]
    x_background = features.x_train.iloc[selection["background_positions"]]
    feature_groups = features.processor.feature_groups
    shap_values = linear_shap(features.posterior_mean_beta, x_background, x_explain)
    grouped_intrinsic, intrinsic_source = _grouped_intrinsic(cell, features, selection, x_explain)
    grouped_shap = grouped_shap_importance(shap_values, feature_groups)
    agreement = compare_group_rankings(grouped_intrinsic, grouped_shap, top_k=protocol_top_k)
    shared = _selection_fields(cell, features, selection, intrinsic_source)
    comparison = {
        **shared,
        "cell_content_sha256": cell["cell_content_sha256"],
        "zero_validation_terms_with_unidentified_beta_abs": features.unidentified_terms,
        "grouped_intrinsic": grouped_intrinsic.to_dict("records"),
        "grouped_shap": grouped_shap.to_dict("records"),
        "agreement": agreement,
    }
    if paired_cox is None:
        return comparison, None

    cox_shap_values = linear_shap(paired_cox.coefficients, x_background, x_explain)
    grouped_cox_shap = grouped_shap_importance(cox_shap_values, feature_groups)
    cox_comparison = {
        **shared,
        "comparison_target": "Cox PH exact linear SHAP",
        "bayesian_cell_content_sha256": cell["cell_content_sha256"],
        "cox_cell_content_sha256": paired_cox.cell["cell_content_sha256"],
        "grouped_intrinsic": grouped_intrinsic.to_dict("records"),
        "grouped_shap": grouped_cox_shap.to_dict("records"),
        "agreement": compare_group_rankings(
            grouped_intrinsic, grouped_cox_shap, top_k=protocol_top_k
        ),
    }
    return comparison, cox_comparison
