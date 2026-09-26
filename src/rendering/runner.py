"""Assemble a publication package from verified frozen artefacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")


from .constants import PROJECT_ROOT
from .diagnostics import _render_ph, _render_predictive_checks, _render_trace_snapshots
from .holm_bounds import render_holm_bounds
from .metrics import (
    _render_calibration,
    _render_cohort_flow,
    _render_fold_metrics,
    _render_paired_ibs,
    _render_runtime,
)
from .outputs import OutputRegistry, _atomic_text, _configure_style
from .supplemental import _render_explanation, _render_robustness
from .verification import (
    _source,
    verify_explainability_artifact,
    verify_frozen_run,
    verify_robustness_run,
)


def render_run(
    run_dir: Path,
    output_dir: Path,
    *,
    explainability_artifact: Path | None = None,
    robustness_dir: Path | None = None,
) -> Path:
    """Validate a frozen run and render its permitted publication artifacts."""
    run = verify_frozen_run(run_dir)
    explanation_verified: tuple[dict[str, Any], dict[str, Any]] | None = None
    robustness_verified: tuple[dict[str, Any], dict[str, Any]] | None = None
    if run.mode == "rehearsal" and (
        explainability_artifact is not None or robustness_dir is not None
    ):
        raise ValueError(
            "rehearsal rendering accepts no performance, explanation or robustness artifact"
        )
    if explainability_artifact is not None:
        explanation_verified = verify_explainability_artifact(explainability_artifact, run)
    if robustness_dir is not None:
        robustness_verified = verify_robustness_run(robustness_dir, run)
    destination = output_dir.resolve()
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(
            f"render output directory is not empty: {destination}; use a new directory"
        )
    destination.mkdir(parents=True, exist_ok=True)
    _configure_style()
    registry = OutputRegistry(destination, run)
    optional_lineage: list[dict[str, Any]] = []

    if run.mode == "rehearsal":
        _render_runtime(run, registry, rehearsal=True)
        notice = (
            "REHEARSAL ONLY — NOT CONFIRMATORY EVIDENCE\n\n"
            "This package contains resource-use and failure diagnostics only. "
            "No prediction metric, calibration estimate, model contrast, explanation "
            "or scientific finding has been rendered from this rehearsal.\n"
        )
        notice_path = destination / "RUNTIME_ONLY_README.txt"
        _atomic_text(notice_path, notice)
        registry.add(
            notice_path,
            kind="evidence_notice",
            sources=[
                _source(run, "manifest.json", ["run_config.mode"]),
                _source(run, "completion.json", ["analysis_mode"]),
            ],
            note="Prominent rehearsal-only evidence boundary",
        )
    else:
        robustness: dict[str, Any] | None = None
        _render_cohort_flow(run, registry)
        _render_fold_metrics(run, registry)
        _render_paired_ibs(run, registry)
        render_holm_bounds(run, registry)
        _render_calibration(run, registry)
        _render_runtime(run, registry, rehearsal=False)
        _render_predictive_checks(run, registry)
        _render_trace_snapshots(run, registry)

        if explanation_verified is not None:
            explanation, source_ref = explanation_verified
            _render_explanation(explanation, source_ref, registry)
            optional_lineage.append(source_ref)
        if robustness_verified is not None:
            robustness, summary_ref = robustness_verified
            _render_robustness(robustness, summary_ref, registry)
            optional_lineage.append(summary_ref)
        _render_ph(run, registry, robustness=robustness)

    registry.write_lineage(
        optional_sources=optional_lineage,
        renderer_path=PROJECT_ROOT / "scripts/render_confirmatory.py",
    )
    return destination
