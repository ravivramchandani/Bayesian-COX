"""Render verified explanation and robustness summaries without fitting models."""

from __future__ import annotations

from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .constants import COLORS, MODEL_LABELS
from .outputs import OutputRegistry, _atomic_text, _save_figure, _write_table


def _explanation_rows(result: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for hypothesis, records in (
        ("H3a_same_model_agreement", result.get("agreement_uncertainty", [])),
        (
            "H3b_same_model_minus_cox",
            result.get("secondary_cross_model_analysis", {})
            .get("cox_ph", {})
            .get("paired_same_model_minus_cox", []),
        ),
    ):
        if not isinstance(records, list):
            raise ValueError(f"explainability {hypothesis} record is not a list")
        for record in records:
            for metric in ("spearman_rho", "kendall_tau", "top_k_jaccard"):
                estimate = record.get(metric)
                if not isinstance(estimate, dict):
                    continue
                rows.append(
                    {
                        "hypothesis": hypothesis,
                        "dataset": record["dataset"],
                        "model_key": record["model_key"],
                        "metric": metric,
                        "estimate": estimate.get("estimate"),
                        "lower_95": estimate.get("lower_95"),
                        "upper_95": estimate.get("upper_95"),
                        "standard_deviation": estimate.get("standard_deviation"),
                        "n_outer_cells": record.get("n_outer_cells"),
                        "n_cell_seed_estimates_or_pairs": record.get(
                            "n_cell_seed_estimates", record.get("n_cell_seed_pairs")
                        ),
                        "sampling_stability_gate": record.get("sampling_stability_gate"),
                        "same_model_sampling_stability_gate": record.get(
                            "same_model_sampling_stability_gate"
                        ),
                        "cox_sampling_stability_gate": record.get("cox_sampling_stability_gate"),
                        "claim_supported": record.get(
                            "positive_same_model_agreement_supported",
                            record.get("stronger_same_model_agreement_supported"),
                        ),
                        "claim_rule": record.get("claim_rule"),
                    }
                )
    columns = [
        "hypothesis",
        "dataset",
        "model_key",
        "metric",
        "estimate",
        "lower_95",
        "upper_95",
        "standard_deviation",
        "n_outer_cells",
        "n_cell_seed_estimates_or_pairs",
        "sampling_stability_gate",
        "same_model_sampling_stability_gate",
        "cox_sampling_stability_gate",
        "claim_supported",
        "claim_rule",
    ]
    return pd.DataFrame(rows, columns=columns)


def _render_explanation(
    result: dict[str, Any], source_ref: dict[str, Any], registry: OutputRegistry
) -> None:
    convergence = result.get("convergence", {}).get("summary", {})
    convergence_failed = convergence.get("status") == "failed"
    if convergence_failed:
        notice = registry.output_dir / "EXPLANATION_GATE_NOTICE.txt"
        _atomic_text(
            notice,
            "The prespecified explanation convergence gate failed.\n"
            "The explanation tables and figures are descriptive diagnostics.\n"
            "No RQ3 explanation-stability claim is permitted from this package.\n",
        )
        registry.add(
            notice,
            kind="evidence_notice",
            sources=[source_ref],
            note="Explicit failed explanation-convergence gate and claim boundary",
        )
    table = _explanation_rows(result)
    stability = pd.DataFrame(result.get("group_stability", []))
    _write_table(
        table,
        registry.output_dir / "tables" / "explanation_agreement",
        registry,
        sources=[source_ref],
        note="Descriptive H3a and paired H3b estimates; interpret with the stored convergence and claim gates",
    )
    _write_table(
        stability,
        registry.output_dir / "tables" / "explanation_group_stability",
        registry,
        sources=[{**source_ref, "result_keys": ["group_stability"]}],
        note="Grouped importance rank and top-five stability summaries",
    )
    spearman = table[table["metric"] == "spearman_rho"].reset_index(drop=True)
    height = max(4.0, 0.42 * max(1, len(spearman)) + 2.0)
    figure, axes = plt.subplots(1, 2, figsize=(13, height))
    if spearman.empty:
        axes[0].text(0.5, 0.5, "No explanation agreement estimates", ha="center", va="center")
        axes[1].set_axis_off()
    else:
        for axis, hypothesis in zip(
            axes,
            ("H3a_same_model_agreement", "H3b_same_model_minus_cox"),
            strict=True,
        ):
            subset = spearman[spearman["hypothesis"] == hypothesis].reset_index(drop=True)
            if subset.empty:
                axis.text(0.5, 0.5, "Not estimable from frozen artifact", ha="center", va="center")
                axis.set_axis_off()
                continue
            y = np.arange(len(subset))
            estimate = subset["estimate"].to_numpy(float)
            lower = subset["lower_95"].to_numpy(float)
            upper = subset["upper_95"].to_numpy(float)
            axis.errorbar(
                estimate,
                y,
                xerr=np.vstack([estimate - lower, upper - estimate]),
                fmt="o",
                capsize=3,
                color=COLORS[0 if hypothesis.startswith("H3a") else 1],
            )
            axis.axvline(0.0, color="black", linestyle="--", linewidth=0.8)
            axis.set_yticks(
                y,
                [
                    f"{row.dataset.upper()} — {MODEL_LABELS.get(row.model_key, row.model_key)}"
                    for row in subset.itertuples(index=False)
                ],
            )
            axis.invert_yaxis()
            axis.set_xlabel("Spearman estimate (descriptive three-stage 95% interval)")
            axis.set_title(
                "H3a: same-model agreement"
                if hypothesis.startswith("H3a")
                else "H3b: same-model minus Cox agreement"
            )
    figure_title = (
        "Explanation diagnostics — convergence gate failed"
        if convergence_failed
        else "Explanation agreement and stability"
    )
    figure.suptitle(figure_title)
    _save_figure(
        figure,
        registry.output_dir / "figures" / "explanation_stability",
        registry,
        title=figure_title,
        sources=[source_ref],
        note="H3a and H3b estimates are read only from the verified explainability artifact",
    )


def _robustness_effect_rows(result: dict[str, Any]) -> pd.DataFrame:
    inference = result["paired_ibs_inference"]
    rows: list[dict[str, Any]] = []
    for kind, records in (
        ("contrast", inference.get("contrasts", [])),
        ("difference_in_differences", inference.get("difference_in_differences", [])),
    ):
        if not isinstance(records, list):
            raise ValueError(f"robustness {kind} record is not a list")
        for record in records:
            effect = record.get("effect")
            rows.append(
                {
                    "effect_type": kind,
                    "dataset": record.get("dataset"),
                    "component": record.get(
                        "component", "rq2" if kind == "difference_in_differences" else None
                    ),
                    "condition": record.get("condition"),
                    "reference_condition": record.get("reference_condition"),
                    "model_a": record.get("model_a"),
                    "model_b": record.get("model_b"),
                    "direction": record.get("direction"),
                    "n_paired_folds": len(record.get("paired_folds", [])),
                    "status": record.get("status"),
                    "observed": effect.get("observed") if isinstance(effect, dict) else None,
                    "bootstrap_standard_error": effect.get("bootstrap_standard_error")
                    if isinstance(effect, dict)
                    else None,
                    "confidence_lower": effect.get("confidence_lower")
                    if isinstance(effect, dict)
                    else None,
                    "confidence_upper": effect.get("confidence_upper")
                    if isinstance(effect, dict)
                    else None,
                    "n_bootstraps": effect.get("n_bootstraps")
                    if isinstance(effect, dict)
                    else None,
                    "n_successful": effect.get("n_successful")
                    if isinstance(effect, dict)
                    else None,
                }
            )
    return pd.DataFrame(rows)


def _render_robustness(
    result: dict[str, Any], summary_ref: dict[str, Any], registry: OutputRegistry
) -> None:
    table = _robustness_effect_rows(result)
    source_ref = result["source_refs"]["paired_ibs_inference.json"]
    _write_table(
        table,
        registry.output_dir / "tables" / "robustness_ibs_effects",
        registry,
        sources=[source_ref],
        note="Frozen robustness contrasts and RQ2 difference-in-differences effects",
    )
    complete = table[(table["status"] == "complete") & table["observed"].notna()].reset_index(
        drop=True
    )
    height = max(4.0, 0.32 * max(1, len(complete)) + 2.0)
    figure, axis = plt.subplots(figsize=(11, height))
    if complete.empty:
        axis.text(0.5, 0.5, "No complete robustness effects", ha="center", va="center")
        axis.set_axis_off()
    else:
        y = np.arange(len(complete))
        estimate = complete["observed"].to_numpy(float)
        lower = complete["confidence_lower"].to_numpy(float)
        upper = complete["confidence_upper"].to_numpy(float)
        axis.errorbar(
            estimate,
            y,
            xerr=np.vstack([estimate - lower, upper - estimate]),
            fmt="o",
            capsize=2,
            markersize=3,
            color=COLORS[0],
        )
        axis.axvline(0.0, color="black", linewidth=0.8)
        axis.set_yticks(
            y,
            [
                f"{row.dataset} | {row.component} | {row.condition} | {row.model_a}−{row.model_b}"
                for row in complete.itertuples(index=False)
            ],
            fontsize=6,
        )
        axis.invert_yaxis()
        axis.set_xlabel("Paired IBS effect (three-stage event-stratified bootstrap 95% interval)")
    axis.set_title("Frozen robustness and information-regime effects")
    _save_figure(
        figure,
        registry.output_dir / "figures" / "robustness_ibs_effects",
        registry,
        title="Frozen robustness and information-regime effects",
        sources=[source_ref],
        note="No condition is selected or omitted according to its effect estimate",
    )

    feasibility = result["feasibility_plan"]
    feasibility_rows = pd.json_normalize(feasibility, sep=".").drop(
        columns=["feasibility_content_sha256"], errors="ignore"
    )
    _write_table(
        feasibility_rows,
        registry.output_dir / "tables" / "robustness_feasibility_plan",
        registry,
        sources=[result["source_refs"]["feasibility_plan.json"]],
        note="Frozen result-blind robustness fit and runtime plan",
    )
    diagnostics_rows: list[dict[str, Any]] = []
    for cell in result["cells"]:
        attempts = cell.get("fit_attempts", [])
        diagnostics = attempts[-1].get("diagnostics", {}) if attempts else {}
        diagnostics_rows.append(
            {
                "dataset": cell.get("dataset"),
                "model_key": cell.get("model_key"),
                "repeat": cell.get("repeat"),
                "fold": cell.get("fold"),
                "condition_id": cell.get("condition", {}).get("condition_id"),
                "status": cell.get("status"),
                "total_seconds": cell.get("total_seconds"),
                "events_train": cell.get("events_train"),
                "processed_feature_degrees_of_freedom": cell.get(
                    "processed_feature_degrees_of_freedom"
                ),
                "effective_information_events_per_degree_of_freedom": cell.get(
                    "effective_information_events_per_degree_of_freedom"
                ),
                "diagnostic_converged": diagnostics.get("converged"),
            }
        )
    _write_table(
        pd.DataFrame(diagnostics_rows),
        registry.output_dir / "tables" / "robustness_cell_audit",
        registry,
        sources=list(result["source_refs"].values()),
        note="Robustness cell completion, compute and effective-information audit",
    )
