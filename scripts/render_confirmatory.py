"""Render publication artifacts from a completed, content-addressed run.

The renderer is intentionally independent of every model and evaluation
module.  It validates the frozen files, performs only descriptive tabulation,
and writes figures/tables whose lineage points to exact source keys and hashes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_LABELS = {
    "cox_ph": "Cox PH",
    "random_survival_forest": "Random survival forest",
    "deepsurv": "DeepSurv",
    "bayesian_normal": "Bayesian Cox (normal)",
    "bayesian_horseshoe": "Bayesian Cox (horseshoe)",
    "bayesian_spike_slab": "Bayesian Cox (spike-and-slab)",
}
METRIC_LABELS = {
    "ibs": "IPCW integrated Brier score",
    "uno_c_index": "Uno's C-index",
    "harrell_c_index": "Harrell's C-index",
    "mean_auc": "Mean time-dependent AUC",
}
COLORS = (
    "#0072B2",
    "#D55E00",
    "#009E73",
    "#CC79A7",
    "#E69F00",
    "#56B4E9",
    "#000000",
)
FIXED_PDF_DATE = datetime(2000, 1, 1, tzinfo=UTC)


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest of one file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json_hash(value: Any) -> str:
    """Hash a JSON-compatible object using the analysis canonical encoding."""
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _load_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"required frozen artifact is missing: {path}")
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON mapping")
    return value


def _verify_content_hash(record: dict[str, Any], hash_field: str, path: Path) -> str:
    claimed = record.get(hash_field)
    if not isinstance(claimed, str):
        raise ValueError(f"{path} is missing {hash_field}")
    unhashed = dict(record)
    unhashed.pop(hash_field, None)
    observed = canonical_json_hash(unhashed)
    if claimed != observed:
        raise RuntimeError(f"content hash does not match: {path}")
    return observed


def _safe_child(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"artifact inventory escapes its run directory: {relative}") from exc
    return candidate


def _slug(value: object) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "_", str(value)).strip("_").lower()
    return text or "unnamed"


def _finite(value: Any, *, field: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field} must be finite")
    return number


@dataclass(frozen=True)
class FrozenRun:
    """A run whose manifests, aggregates and cell inventory have been verified."""

    run_dir: Path
    manifest: dict[str, Any]
    completion: dict[str, Any]
    inference: dict[str, Any]
    cells: tuple[tuple[str, dict[str, Any]], ...]
    source_hashes: dict[str, str]

    @property
    def mode(self) -> str:
        return str(self.completion["analysis_mode"])

    @property
    def evidence_status(self) -> str:
        return "confirmatory" if self.mode == "confirmatory" else "rehearsal_only"


def verify_frozen_run(run_dir: Path) -> FrozenRun:
    """Load a confirmatory/rehearsal run only after exhaustive hash checks."""
    root = run_dir.resolve()
    manifest_path = root / "manifest.json"
    completion_path = root / "completion.json"
    manifest = _load_mapping(manifest_path)
    completion = _load_mapping(completion_path)
    _verify_content_hash(manifest, "manifest_content_sha256", manifest_path)
    _verify_content_hash(completion, "completion_content_sha256", completion_path)

    run_config = manifest.get("run_config")
    if not isinstance(run_config, dict):
        raise ValueError("run manifest has no run_config mapping")
    if manifest.get("config_sha256") != canonical_json_hash(run_config):
        raise RuntimeError("manifest config hash does not match run_config")
    dependencies = manifest.get("environment", {}).get("dependencies")
    dependency_hash = manifest.get("environment", {}).get("dependency_set_sha256")
    if not isinstance(dependencies, dict) or dependency_hash != canonical_json_hash(dependencies):
        raise RuntimeError("manifest dependency-set hash is invalid")

    mode = run_config.get("mode")
    if mode not in {"rehearsal", "confirmatory"}:
        raise ValueError(f"unsupported source analysis mode: {mode!r}")
    if completion.get("analysis_mode") != mode:
        raise RuntimeError("manifest and completion analysis modes disagree")
    if mode == "confirmatory":
        protocol = run_config.get("protocol", {})
        if protocol.get("design_status") != "frozen_after_rehearsal":
            raise RuntimeError("confirmatory source does not identify a frozen design")
        freeze_hash = manifest.get("protocol_freeze_sha256")
        if not isinstance(freeze_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", freeze_hash):
            raise RuntimeError("confirmatory manifest lacks a valid protocol-freeze hash")

    aggregate_hashes = completion.get("aggregate_sha256")
    if not isinstance(aggregate_hashes, dict):
        raise ValueError("completion artifact has no aggregate hash inventory")
    required_aggregates = {
        "fold_metrics.csv",
        "out_of_fold_predictions.csv.gz",
        "inference.json",
    }
    if not required_aggregates.issubset(aggregate_hashes):
        missing = sorted(required_aggregates - set(aggregate_hashes))
        raise ValueError(f"completion artifact omits required aggregates: {missing}")
    source_hashes = {
        "manifest.json": sha256_file(manifest_path),
        "completion.json": sha256_file(completion_path),
    }
    for relative, claimed in sorted(aggregate_hashes.items()):
        path = _safe_child(root, str(relative))
        if not path.is_file() or sha256_file(path) != claimed:
            raise RuntimeError(f"aggregate file hash does not match: {path}")
        source_hashes[str(relative)] = str(claimed)

    inventory = completion.get("all_stored_cell_hashes")
    if not isinstance(inventory, dict):
        raise ValueError("completion artifact has no stored-cell hash inventory")
    actual_paths = sorted((root / "cells").glob("*/*/*.json"))
    actual_relative = {str(path.relative_to(root)) for path in actual_paths}
    if actual_relative != set(inventory):
        raise RuntimeError("stored cell files do not match the completion inventory")
    if int(completion.get("stored_cells", -1)) != len(actual_paths):
        raise RuntimeError("stored cell count does not match the completion inventory")

    cells: list[tuple[str, dict[str, Any]]] = []
    keys: set[tuple[str, str, int, int]] = set()
    observed_status: dict[str, int] = {}
    for path in actual_paths:
        relative = str(path.relative_to(root))
        observed_file_hash = sha256_file(path)
        if inventory[relative] != observed_file_hash:
            raise RuntimeError(f"stored cell file hash does not match: {path}")
        cell = _load_mapping(path)
        _verify_content_hash(cell, "cell_content_sha256", path)
        if cell.get("analysis_mode") != mode:
            raise RuntimeError(f"cell analysis mode differs from its run: {path}")
        expected_evidence = "confirmatory" if mode == "confirmatory" else "rehearsal_only"
        if cell.get("evidence_status") != expected_evidence:
            raise RuntimeError(f"cell evidence status differs from its run: {path}")
        key = (
            str(cell.get("dataset")),
            str(cell.get("model_key")),
            int(cell.get("repeat", -1)),
            int(cell.get("fold", -1)),
        )
        if key in keys:
            raise RuntimeError(f"duplicate stored cell key: {key}")
        keys.add(key)
        status = str(cell.get("status"))
        if status not in {"complete", "failed", "failed_diagnostics"}:
            raise ValueError(f"unknown cell status {status!r}: {path}")
        observed_status[status] = observed_status.get(status, 0) + 1
        source_hashes[relative] = observed_file_hash
        cells.append((relative, cell))
    if observed_status != completion.get("status_counts"):
        raise RuntimeError("completion status counts do not match stored cells")

    datasets = tuple(str(value) for value in run_config.get("datasets", []))
    models = tuple(str(value) for value in run_config.get("models", []))
    repeats = int(run_config.get("outer_repeats", 0))
    splits = int(run_config.get("outer_splits", 0))
    fold_limit = run_config.get("fold_limit_per_dataset")
    folds_per_dataset = repeats * splits
    if fold_limit is not None:
        folds_per_dataset = min(folds_per_dataset, int(fold_limit))
    expected_count = len(datasets) * len(models) * folds_per_dataset
    if expected_count <= 0:
        raise ValueError("run configuration defines no planned cells")
    if int(completion.get("planned_cells_in_this_invocation", -1)) != expected_count:
        raise RuntimeError("completion planned-cell count does not match run_config")
    if len(cells) != expected_count:
        raise RuntimeError("run is incomplete: not every planned cell is stored")
    if mode == "confirmatory":
        if fold_limit is not None:
            raise RuntimeError("confirmatory source unexpectedly limits outer folds")
        expected_keys = {
            (dataset, model, repeat, fold)
            for dataset in datasets
            for model in models
            for repeat in range(1, repeats + 1)
            for fold in range(1, splits + 1)
        }
        if keys != expected_keys:
            raise RuntimeError("confirmatory cells do not form the exact planned grid")

    metrics_path = root / "fold_metrics.csv"
    metrics_table = pd.read_csv(metrics_path)
    complete_cells = [cell for _, cell in cells if cell["status"] == "complete"]
    if len(metrics_table) != len(complete_cells):
        raise RuntimeError("fold_metrics row count differs from complete-cell count")
    required_metric_columns = {
        "dataset",
        "model_key",
        "repeat",
        "fold",
        "cell_content_sha256",
    }
    if complete_cells and not required_metric_columns.issubset(metrics_table.columns):
        raise ValueError("fold_metrics is missing cell-lineage columns")
    metric_keys = {
        (
            str(row.dataset),
            str(row.model_key),
            int(row.repeat),
            int(row.fold),
            str(row.cell_content_sha256),
        )
        for row in metrics_table.itertuples(index=False)
    }
    complete_keys = {
        (
            str(cell["dataset"]),
            str(cell["model_key"]),
            int(cell["repeat"]),
            int(cell["fold"]),
            str(cell["cell_content_sha256"]),
        )
        for cell in complete_cells
    }
    if metric_keys != complete_keys:
        raise RuntimeError("fold_metrics rows do not map exactly to complete cells")

    inference_path = root / "inference.json"
    inference = _load_mapping(inference_path)
    return FrozenRun(
        run_dir=root,
        manifest=manifest,
        completion=completion,
        inference=inference,
        cells=tuple(cells),
        source_hashes=source_hashes,
    )


def _source(run: FrozenRun, relative: str, result_keys: Iterable[str]) -> dict[str, Any]:
    if relative not in run.source_hashes:
        raise KeyError(f"unverified source requested for lineage: {relative}")
    return {
        "artifact": f"source_run/{relative}",
        "sha256": run.source_hashes[relative],
        "result_keys": sorted(set(result_keys)),
    }


class OutputRegistry:
    """Write-only registry that records exact sources for every output file."""

    def __init__(self, output_dir: Path, run: FrozenRun) -> None:
        self.output_dir = output_dir
        self.run = run
        self.outputs: list[dict[str, Any]] = []

    def add(
        self,
        path: Path,
        *,
        kind: str,
        sources: Iterable[dict[str, Any]],
        note: str,
    ) -> None:
        relative = str(path.relative_to(self.output_dir))
        if any(row["path"] == relative for row in self.outputs):
            raise RuntimeError(f"duplicate rendered output registration: {relative}")
        self.outputs.append(
            {
                "path": relative,
                "sha256": sha256_file(path),
                "kind": kind,
                "sources": list(sources),
                "note": note,
            }
        )

    def write_lineage(
        self,
        *,
        optional_sources: list[dict[str, Any]],
        renderer_path: Path,
    ) -> Path:
        lineage = {
            "schema_version": "1.0.0",
            "evidence_status": self.run.evidence_status,
            "source_run": {
                "directory_name": self.run.run_dir.name,
                "analysis_mode": self.run.mode,
                "manifest_content_sha256": self.run.manifest["manifest_content_sha256"],
                "completion_content_sha256": self.run.completion["completion_content_sha256"],
            },
            "renderer": {
                "path": "scripts/render_confirmatory.py",
                "sha256": sha256_file(renderer_path),
                "policy": "pure frozen-artifact renderer; no model reconstruction or fitting",
            },
            "optional_source_artifacts": optional_sources,
            "outputs": sorted(self.outputs, key=lambda row: row["path"]),
        }
        lineage["lineage_content_sha256"] = canonical_json_hash(lineage)
        path = self.output_dir / "lineage.json"
        _atomic_text(
            path,
            json.dumps(lineage, indent=2, sort_keys=True, allow_nan=False) + "\n",
        )
        return path


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def _configure_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.labelsize": 9,
            "legend.fontsize": 7,
            "figure.dpi": 120,
            "savefig.dpi": 240,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.alpha": 0.18,
        }
    )


def _save_figure(
    figure: plt.Figure,
    base_path: Path,
    registry: OutputRegistry,
    *,
    title: str,
    sources: Iterable[dict[str, Any]],
    note: str,
) -> list[Path]:
    source_list = list(sources)
    written: list[Path] = []
    figure.tight_layout()
    for suffix in (".pdf", ".png"):
        path = base_path.with_suffix(suffix)
        path.parent.mkdir(parents=True, exist_ok=True)
        if suffix == ".pdf":
            metadata = {
                "Title": title,
                "Author": "Ravi Thesis Project",
                "Subject": note,
                "Keywords": "frozen artifact; reproducible rendering",
                "Creator": "scripts/render_confirmatory.py",
                "Producer": "Matplotlib",
                "CreationDate": FIXED_PDF_DATE,
                "ModDate": FIXED_PDF_DATE,
            }
        else:
            metadata = {
                "Title": title,
                "Author": "Ravi Thesis Project",
                "Description": note,
                "Software": "scripts/render_confirmatory.py",
            }
        figure.savefig(path, bbox_inches="tight", metadata=metadata)
        registry.add(path, kind=f"figure_{suffix[1:]}", sources=source_list, note=note)
        written.append(path)
    plt.close(figure)
    return written


def _write_table(
    frame: pd.DataFrame,
    base_path: Path,
    registry: OutputRegistry,
    *,
    sources: Iterable[dict[str, Any]],
    note: str,
) -> list[Path]:
    source_list = list(sources)
    base_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path = base_path.with_suffix(".csv")
    tex_path = base_path.with_suffix(".tex")
    _atomic_text(csv_path, frame.to_csv(index=False, lineterminator="\n"))
    latex = frame.to_latex(
        index=False,
        escape=True,
        na_rep="--",
        float_format=lambda value: f"{value:.4f}",
    )
    _atomic_text(tex_path, latex)
    registry.add(csv_path, kind="table_csv", sources=source_list, note=note)
    registry.add(tex_path, kind="table_latex", sources=source_list, note=note)
    return [csv_path, tex_path]


def _cell_sources(
    run: FrozenRun,
    selected: Iterable[tuple[str, dict[str, Any]]],
    result_keys: Iterable[str],
) -> list[dict[str, Any]]:
    keys = list(result_keys)
    return [_source(run, relative, keys) for relative, _ in selected]


def _runtime_rows(run: FrozenRun) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for relative, cell in run.cells:
        attempts = cell.get("fit_attempts")
        attempts = attempts if isinstance(attempts, list) else []
        last = attempts[-1] if attempts else {}
        diagnostics = last.get("diagnostics") if isinstance(last, dict) else None
        diagnostics = diagnostics if isinstance(diagnostics, dict) else {}
        rows.append(
            {
                "dataset": cell["dataset"],
                "model_key": cell["model_key"],
                "model": cell.get("model", MODEL_LABELS.get(cell["model_key"], cell["model_key"])),
                "repeat": cell["repeat"],
                "fold": cell["fold"],
                "status": cell["status"],
                "total_seconds": _finite(cell["total_seconds"], field="total_seconds"),
                "fit_attempts": len(attempts),
                "diagnostic_converged": diagnostics.get("converged"),
                "r_hat_max": diagnostics.get("r_hat_max"),
                "ess_bulk_min": diagnostics.get("ess_bulk_min"),
                "ess_tail_min": diagnostics.get("ess_tail_min"),
                "divergences": diagnostics.get("n_divergent"),
                "bfmi_min": diagnostics.get("bfmi_min"),
                "max_tree_depth_hits": diagnostics.get("n_max_tree_depth"),
                "failure_message": cell.get("message"),
                "source_cell": relative,
                "cell_content_sha256": cell["cell_content_sha256"],
            }
        )
    return pd.DataFrame(rows)


def _render_runtime(run: FrozenRun, registry: OutputRegistry, *, rehearsal: bool) -> None:
    table = _runtime_rows(run)
    sources = _cell_sources(
        run,
        run.cells,
        ["status", "total_seconds", "fit_attempts", "message"],
    )
    _write_table(
        table,
        registry.output_dir / "tables" / "runtime_diagnostic_failures",
        registry,
        sources=sources,
        note=(
            "REHEARSAL ONLY: resource and failure report; no performance evidence"
            if rehearsal
            else "Cell runtimes, fit attempts, diagnostic gates and failures"
        ),
    )

    figure, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    complete_times = table.loc[table["total_seconds"] > 0]
    models = sorted(complete_times["model_key"].unique())
    data = [
        complete_times.loc[complete_times["model_key"] == model, "total_seconds"].to_numpy()
        for model in models
    ]
    if data:
        axes[0].boxplot(data, tick_labels=[MODEL_LABELS.get(m, m) for m in models])
        axes[0].tick_params(axis="x", rotation=35)
        axes[0].set_yscale("log")
        axes[0].set_ylabel("Total cell runtime (seconds, log scale)")
    else:
        axes[0].text(0.5, 0.5, "No runtime records", ha="center", va="center")
    status = (
        table.groupby(["model_key", "status"], sort=True)
        .size()
        .unstack(fill_value=0)
        .reindex(models, fill_value=0)
    )
    bottom = np.zeros(len(status), dtype=float)
    for index, state in enumerate(status.columns):
        values = status[state].to_numpy(float)
        axes[1].bar(
            np.arange(len(status)),
            values,
            bottom=bottom,
            label=state.replace("_", " "),
            color=COLORS[index % len(COLORS)],
        )
        bottom += values
    axes[1].set_xticks(
        np.arange(len(status)),
        [MODEL_LABELS.get(value, value) for value in status.index],
        rotation=35,
        ha="right",
    )
    axes[1].set_ylabel("Stored cells")
    axes[1].legend(frameon=False)
    prefix = "REHEARSAL ONLY — " if rehearsal else ""
    figure.suptitle(prefix + "Runtime and fit-status audit")
    _save_figure(
        figure,
        registry.output_dir / "figures" / "runtime_diagnostic_failures",
        registry,
        title=prefix + "Runtime and fit-status audit",
        sources=sources,
        note=(
            "Runtime planning artifact; rehearsal estimates are not scientific evidence"
            if rehearsal
            else "Runtime and prespecified fit/diagnostic status from frozen cells"
        ),
    )


def _cohort_rows(run: FrozenRun) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for dataset in sorted({str(cell["dataset"]) for _, cell in run.cells}):
        cohort_cells = [cell for _, cell in run.cells if cell["dataset"] == dataset]
        counts = {
            (
                int(cell["n_train"]) + int(cell["n_validation"]),
                int(cell["events_train"]) + int(cell["events_validation"]),
            )
            for cell in cohort_cells
        }
        if len(counts) != 1:
            raise RuntimeError(f"{dataset} cells disagree on cohort/event counts")
        n_subjects, n_events = counts.pop()
        status = pd.Series([cell["status"] for cell in cohort_cells]).value_counts()
        records.append(
            {
                "dataset": dataset,
                "eligible_subjects": n_subjects,
                "observed_events": n_events,
                "censored": n_subjects - n_events,
                "event_fraction": n_events / n_subjects,
                "planned_cells": len(cohort_cells),
                "complete_cells": int(status.get("complete", 0)),
                "failed_cells": int(status.get("failed", 0) + status.get("failed_diagnostics", 0)),
            }
        )
    return pd.DataFrame(records)


def _render_cohort_flow(run: FrozenRun, registry: OutputRegistry) -> None:
    table = _cohort_rows(run)
    sources = _cell_sources(
        run,
        run.cells,
        [
            "n_train",
            "n_validation",
            "events_train",
            "events_validation",
            "status",
        ],
    )
    _write_table(
        table,
        registry.output_dir / "tables" / "cohort_flow_counts",
        registry,
        sources=sources,
        note="Cohort inclusion, outcome and analysis-cell flow counts",
    )
    figure, axes = plt.subplots(1, 2, figsize=(10, 4.2))
    positions = np.arange(len(table))
    axes[0].bar(positions, table["observed_events"], label="Observed event", color=COLORS[1])
    axes[0].bar(
        positions,
        table["censored"],
        bottom=table["observed_events"],
        label="Censored",
        color=COLORS[0],
    )
    axes[0].set_xticks(positions, table["dataset"].str.upper())
    axes[0].set_ylabel("Eligible subjects")
    axes[0].legend(frameon=False)
    axes[1].bar(positions, table["complete_cells"], label="Complete", color=COLORS[2])
    axes[1].bar(
        positions,
        table["failed_cells"],
        bottom=table["complete_cells"],
        label="Failed/diagnostic failure",
        color=COLORS[1],
    )
    axes[1].set_xticks(positions, table["dataset"].str.upper())
    axes[1].set_ylabel("Frozen analysis cells")
    axes[1].legend(frameon=False)
    figure.suptitle("Cohort and analysis-cell flow")
    _save_figure(
        figure,
        registry.output_dir / "figures" / "cohort_flow_counts",
        registry,
        title="Cohort and analysis-cell flow",
        sources=sources,
        note="Counts reconstructed consistently from every frozen outer-fold cell",
    )


def _metric_rows(run: FrozenRun) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for relative, cell in run.cells:
        if cell["status"] != "complete":
            continue
        metrics = cell.get("metrics")
        if not isinstance(metrics, dict):
            raise ValueError(f"complete cell has no metrics mapping: {relative}")
        for key in METRIC_LABELS:
            rows.append(
                {
                    "dataset": cell["dataset"],
                    "model_key": cell["model_key"],
                    "model": cell.get(
                        "model", MODEL_LABELS.get(cell["model_key"], cell["model_key"])
                    ),
                    "repeat": cell["repeat"],
                    "fold": cell["fold"],
                    "metric": key,
                    "metric_label": METRIC_LABELS[key],
                    "value": _finite(metrics[key], field=f"metrics.{key}"),
                    "source_cell": relative,
                    "cell_content_sha256": cell["cell_content_sha256"],
                }
            )
    return pd.DataFrame(rows)


def _metric_summary(rows: pd.DataFrame) -> pd.DataFrame:
    if rows.empty:
        return pd.DataFrame(
            columns=[
                "dataset",
                "model_key",
                "model",
                "metric",
                "n_folds",
                "mean",
                "standard_deviation",
                "median",
                "quartile_25",
                "quartile_75",
            ]
        )
    grouped = rows.groupby(["dataset", "model_key", "model", "metric"], sort=True, observed=True)[
        "value"
    ]
    summary = grouped.agg(
        n_folds="count",
        mean="mean",
        standard_deviation="std",
        median="median",
        quartile_25=lambda values: values.quantile(0.25),
        quartile_75=lambda values: values.quantile(0.75),
    )
    return summary.reset_index()


def _render_fold_metrics(run: FrozenRun, registry: OutputRegistry) -> None:
    rows = _metric_rows(run)
    summary = _metric_summary(rows)
    selected = [(relative, cell) for relative, cell in run.cells if cell["status"] == "complete"]
    sources = _cell_sources(run, selected, ["metrics"])
    _write_table(
        rows,
        registry.output_dir / "tables" / "fold_metrics_long",
        registry,
        sources=sources,
        note="All complete-cell fold metrics; no pooling across cohorts",
    )
    _write_table(
        summary,
        registry.output_dir / "tables" / "fold_metric_summary",
        registry,
        sources=sources,
        note="Descriptive fold-metric summaries derived from the long table",
    )

    metrics = list(METRIC_LABELS)
    figure, axes = plt.subplots(2, 2, figsize=(13, 8.5))
    datasets = sorted(rows["dataset"].unique()) if not rows.empty else []
    models = sorted(rows["model_key"].unique()) if not rows.empty else []
    for metric, axis in zip(metrics, axes.flat, strict=True):
        selected_metric = rows[rows["metric"] == metric]
        box_data: list[np.ndarray] = []
        labels: list[str] = []
        colors: list[str] = []
        for dataset_index, dataset in enumerate(datasets):
            for model in models:
                values = selected_metric.loc[
                    (selected_metric["dataset"] == dataset)
                    & (selected_metric["model_key"] == model),
                    "value",
                ].to_numpy()
                if len(values):
                    box_data.append(values)
                    labels.append(f"{dataset.upper()}\n{MODEL_LABELS.get(model, model)}")
                    colors.append(COLORS[dataset_index % len(COLORS)])
        if box_data:
            boxes = axis.boxplot(box_data, patch_artist=True, tick_labels=labels)
            for patch, color in zip(boxes["boxes"], colors, strict=True):
                patch.set_facecolor(color)
                patch.set_alpha(0.5)
            axis.tick_params(axis="x", rotation=65, labelsize=6)
        else:
            axis.text(0.5, 0.5, "No complete metric cells", ha="center", va="center")
        axis.set_title(METRIC_LABELS[metric])
        axis.set_ylabel("Outer-fold estimate")
    figure.suptitle("Outer-fold metric distributions")
    _save_figure(
        figure,
        registry.output_dir / "figures" / "fold_metric_distributions",
        registry,
        title="Outer-fold metric distributions",
        sources=sources,
        note="Distributions retain the repeated-CV fold as the displayed unit",
    )

    discrimination = rows[rows["metric"].isin(["uno_c_index", "harrell_c_index", "mean_auc"])]
    discrimination_summary = _metric_summary(discrimination)
    _write_table(
        discrimination_summary,
        registry.output_dir / "tables" / "discrimination_summary",
        registry,
        sources=sources,
        note="Descriptive discrimination summary by cohort and model",
    )
    figure, axes = plt.subplots(
        max(1, len(datasets)), 1, figsize=(10, max(3.6, 3.2 * len(datasets))), squeeze=False
    )
    for axis, dataset in zip(axes.flat, datasets, strict=False):
        subset = discrimination_summary[discrimination_summary["dataset"] == dataset]
        x = np.arange(len(models), dtype=float)
        width = 0.24
        for metric_index, metric in enumerate(("uno_c_index", "harrell_c_index", "mean_auc")):
            means = []
            errors = []
            for model in models:
                match = subset[(subset["model_key"] == model) & (subset["metric"] == metric)]
                means.append(float(match["mean"].iloc[0]) if len(match) else np.nan)
                sd = float(match["standard_deviation"].iloc[0]) if len(match) else np.nan
                errors.append(sd if math.isfinite(sd) else 0.0)
            axis.errorbar(
                x + (metric_index - 1) * width,
                means,
                yerr=errors,
                fmt="o",
                capsize=3,
                color=COLORS[metric_index],
                label=METRIC_LABELS[metric],
            )
        axis.set_xticks(
            x, [MODEL_LABELS.get(model, model) for model in models], rotation=30, ha="right"
        )
        axis.set_ylabel("Estimate (mean ± fold SD)")
        axis.set_title(dataset.upper())
        axis.legend(frameon=False, ncols=3)
    figure.suptitle("Discrimination across outer folds")
    _save_figure(
        figure,
        registry.output_dir / "figures" / "discrimination",
        registry,
        title="Discrimination across outer folds",
        sources=sources,
        note="Mean and fold standard deviation are descriptive, not independent-sample intervals",
    )


def _paired_ibs_rows(run: FrozenRun) -> pd.DataFrame:
    primary = run.inference.get("primary")
    if not isinstance(primary, list):
        raise ValueError("inference artifact has no primary contrast list")
    rows: list[dict[str, Any]] = []
    for contrast in primary:
        effect = contrast.get("ibs")
        if not isinstance(effect, dict):
            continue
        rows.append(
            {
                "dataset": contrast["dataset"],
                "model_a": contrast["model_a"],
                "model_b": contrast["model_b"],
                "direction": contrast["contrast_direction"],
                "n_paired_folds": contrast["n_paired_folds"],
                "mean_ibs_difference": effect["mean_difference"],
                "corrected_standard_error": effect["corrected_standard_error"],
                "confidence_lower": effect["confidence_lower"],
                "confidence_upper": effect["confidence_upper"],
                "p_value": effect["p_value"],
                "holm_adjusted_p": contrast.get("holm_adjusted_p"),
                "holm_reject_0_05": contrast.get("holm_reject_0_05"),
                "superiority_language_permitted": contrast.get(
                    "superiority_language_permitted", False
                ),
            }
        )
    columns = [
        "dataset",
        "model_a",
        "model_b",
        "direction",
        "n_paired_folds",
        "mean_ibs_difference",
        "corrected_standard_error",
        "confidence_lower",
        "confidence_upper",
        "p_value",
        "holm_adjusted_p",
        "holm_reject_0_05",
        "superiority_language_permitted",
    ]
    return pd.DataFrame(rows, columns=columns)


def _render_paired_ibs(run: FrozenRun, registry: OutputRegistry) -> None:
    table = _paired_ibs_rows(run)
    sources = [_source(run, "inference.json", ["primary", "holm_family_complete"])]
    _write_table(
        table,
        registry.output_dir / "tables" / "paired_ibs_effects",
        registry,
        sources=sources,
        note="Nadeau–Bengio corrected paired Bayesian-prior IBS effects",
    )
    height = max(3.5, 0.45 * max(1, len(table)) + 1.8)
    figure, axis = plt.subplots(figsize=(9, height))
    if table.empty:
        axis.text(
            0.5,
            0.5,
            "No complete paired IBS inference in the frozen artifact",
            ha="center",
            va="center",
        )
        axis.set_axis_off()
    else:
        ordered = table.reset_index(drop=True)
        y = np.arange(len(ordered))
        estimates = ordered["mean_ibs_difference"].to_numpy(float)
        lower = ordered["confidence_lower"].to_numpy(float)
        upper = ordered["confidence_upper"].to_numpy(float)
        axis.errorbar(
            estimates,
            y,
            xerr=np.vstack([estimates - lower, upper - estimates]),
            fmt="o",
            capsize=3,
            color=COLORS[0],
        )
        axis.axvline(0.0, color="black", linewidth=0.8)
        labels = [
            f"{row.dataset.upper()}: {row.model_a} − {row.model_b}"
            for row in ordered.itertuples(index=False)
        ]
        axis.set_yticks(y, labels)
        axis.invert_yaxis()
        axis.set_xlabel("Corrected mean IBS difference (95% CI; lower favours model A)")
    axis.set_title("Primary paired IBS effects")
    _save_figure(
        figure,
        registry.output_dir / "figures" / "paired_ibs_effects",
        registry,
        title="Primary paired IBS effects",
        sources=sources,
        note="Effect direction and confidence intervals are read from inference.json",
    )


def _calibration_rows(run: FrozenRun) -> tuple[pd.DataFrame, pd.DataFrame]:
    parameters: list[dict[str, Any]] = []
    curves: list[dict[str, Any]] = []
    for relative, cell in run.cells:
        if cell["status"] != "complete":
            continue
        calibration = cell.get("metrics", {}).get("calibration")
        if not isinstance(calibration, list):
            raise ValueError(f"complete cell has no calibration list: {relative}")
        for horizon_index, item in enumerate(calibration, start=1):
            summary = item.get("summary")
            curve = item.get("curve")
            if not isinstance(summary, dict) or not isinstance(curve, dict):
                raise ValueError(f"malformed calibration record: {relative}")
            base = {
                "dataset": cell["dataset"],
                "model_key": cell["model_key"],
                "model": cell.get("model", MODEL_LABELS.get(cell["model_key"], cell["model_key"])),
                "repeat": cell["repeat"],
                "fold": cell["fold"],
                "horizon_index": horizon_index,
                "horizon": summary["horizon"],
                "source_cell": relative,
                "cell_content_sha256": cell["cell_content_sha256"],
            }
            for parameter in ("calibration_in_the_large", "intercept", "slope"):
                estimate = summary[parameter]
                parameters.append(
                    {
                        **base,
                        "parameter": parameter,
                        "estimate": estimate["estimate"],
                        "confidence_lower": estimate["lower"],
                        "confidence_upper": estimate["upper"],
                        "n_bootstrap_successful": summary.get("n_bootstrap_successful"),
                    }
                )
            for bin_record in curve.get("bins", []):
                curves.append(
                    {
                        **base,
                        "bin": bin_record["bin"],
                        "n": bin_record["n"],
                        "mean_predicted_survival": bin_record["mean_predicted_survival"],
                        "observed_survival": bin_record["observed_survival"],
                        "observed_lower": bin_record["observed_lower"],
                        "observed_upper": bin_record["observed_upper"],
                    }
                )
    return pd.DataFrame(parameters), pd.DataFrame(curves)


def _render_calibration(run: FrozenRun, registry: OutputRegistry) -> None:
    parameters, curves = _calibration_rows(run)
    selected = [(relative, cell) for relative, cell in run.cells if cell["status"] == "complete"]
    sources = _cell_sources(run, selected, ["metrics.calibration"])
    _write_table(
        parameters,
        registry.output_dir / "tables" / "calibration_parameters",
        registry,
        sources=sources,
        note="Calibration-in-the-large, intercept and slope with cell-level intervals",
    )
    _write_table(
        curves,
        registry.output_dir / "tables" / "calibration_curves",
        registry,
        sources=sources,
        note="All frozen calibration-bin estimates and Kaplan–Meier intervals",
    )

    datasets = sorted(curves["dataset"].unique()) if not curves.empty else []
    horizons = sorted(curves["horizon_index"].unique()) if not curves.empty else []
    figure, axes = plt.subplots(
        max(1, len(datasets)),
        max(1, len(horizons)),
        figsize=(4 * max(1, len(horizons)), 3.6 * max(1, len(datasets))),
        squeeze=False,
        sharex=True,
        sharey=True,
    )
    if curves.empty:
        axes[0, 0].text(0.5, 0.5, "No complete calibration curves", ha="center", va="center")
    for row_index, dataset in enumerate(datasets):
        for column_index, horizon_index in enumerate(horizons):
            axis = axes[row_index, column_index]
            subset = curves[
                (curves["dataset"] == dataset) & (curves["horizon_index"] == horizon_index)
            ]
            for model_index, (model, group) in enumerate(subset.groupby("model_key", sort=True)):
                averaged = (
                    group.groupby("bin", sort=True)[
                        ["mean_predicted_survival", "observed_survival"]
                    ]
                    .mean()
                    .reset_index()
                )
                axis.plot(
                    averaged["mean_predicted_survival"],
                    averaged["observed_survival"],
                    marker="o",
                    linewidth=1.2,
                    markersize=3,
                    label=MODEL_LABELS.get(model, model),
                    color=COLORS[model_index % len(COLORS)],
                )
            axis.plot([0, 1], [0, 1], linestyle="--", color="black", linewidth=0.8)
            axis.set_xlim(0, 1)
            axis.set_ylim(0, 1)
            axis.set_title(f"{dataset.upper()} — horizon quantile {horizon_index}")
            axis.set_xlabel("Mean predicted survival")
            axis.set_ylabel("Observed survival")
            if row_index == 0 and column_index == 0:
                axis.legend(frameon=False, fontsize=6)
    figure.suptitle("Calibration curves across outer folds")
    _save_figure(
        figure,
        registry.output_dir / "figures" / "calibration_curves",
        registry,
        title="Calibration curves across outer folds",
        sources=sources,
        note="Lines average corresponding calibration bins descriptively across outer folds",
    )

    figure, axes = plt.subplots(
        max(1, len(datasets)), 2, figsize=(11, max(3.6, 3.4 * len(datasets))), squeeze=False
    )
    models = sorted(parameters["model_key"].unique()) if not parameters.empty else []
    for row_index, dataset in enumerate(datasets):
        for column_index, parameter in enumerate(("intercept", "slope")):
            axis = axes[row_index, column_index]
            subset = parameters[
                (parameters["dataset"] == dataset) & (parameters["parameter"] == parameter)
            ]
            for model_index, model in enumerate(models):
                model_rows = subset[subset["model_key"] == model]
                x = (
                    model_index
                    + (
                        model_rows["horizon_index"].to_numpy(float)
                        - model_rows["horizon_index"].mean()
                    )
                    * 0.035
                )
                axis.scatter(
                    x,
                    model_rows["estimate"],
                    s=12,
                    alpha=0.35,
                    color=COLORS[model_index % len(COLORS)],
                )
                if len(model_rows):
                    axis.plot(
                        model_index,
                        model_rows["estimate"].mean(),
                        marker="D",
                        color="black",
                        markersize=4,
                    )
            axis.axhline(
                0.0 if parameter == "intercept" else 1.0,
                color="black",
                linestyle="--",
                linewidth=0.8,
            )
            axis.set_xticks(
                np.arange(len(models)),
                [MODEL_LABELS.get(model, model) for model in models],
                rotation=30,
                ha="right",
            )
            axis.set_ylabel(parameter.capitalize())
            axis.set_title(f"{dataset.upper()} — calibration {parameter}")
    figure.suptitle("Calibration intercepts and slopes")
    _save_figure(
        figure,
        registry.output_dir / "figures" / "calibration_parameters",
        registry,
        title="Calibration intercepts and slopes",
        sources=sources,
        note="Points are cell/horizon estimates; diamonds are descriptive means",
    )


def _predictive_check_rows(run: FrozenRun) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for relative, cell in run.cells:
        if cell["status"] != "complete" or not str(cell["model_key"]).startswith("bayesian_"):
            continue
        details = cell.get("model_details", {})
        prior = details.get("prior_predictive")
        posterior = details.get("posterior_predictive")
        if isinstance(prior, dict):
            population = prior.get("covariate_population_survival")
            if not isinstance(population, list):
                raise ValueError(
                    f"confirmatory Bayesian cell lacks full-model prior predictive check: {relative}"
                )
            for item in prior.get("baseline_survival", []):
                rows.append(
                    {
                        "dataset": cell["dataset"],
                        "model_key": cell["model_key"],
                        "repeat": cell["repeat"],
                        "fold": cell["fold"],
                        "check": "prior_predictive_baseline_survival",
                        "time": item.get("time"),
                        "scaled_time": item.get("scaled_time"),
                        "interval": np.nan,
                        "observed": np.nan,
                        "predicted": item.get("median_survival"),
                        "lower_95": item.get("lower_95"),
                        "upper_95": item.get("upper_95"),
                        "observed_covered": np.nan,
                        "replicated_median": np.nan,
                        "posterior_predictive_tail_probability": np.nan,
                        "mean_survival_across_subjects_median": np.nan,
                        "proportion_subject_draws_below_0_01": np.nan,
                        "proportion_subject_draws_above_0_99": np.nan,
                        "source_cell": relative,
                    }
                )
            for item in population:
                rows.append(
                    {
                        "dataset": cell["dataset"],
                        "model_key": cell["model_key"],
                        "repeat": cell["repeat"],
                        "fold": cell["fold"],
                        "check": "prior_predictive_covariate_population_survival",
                        "time": item.get("time"),
                        "scaled_time": item.get("scaled_time"),
                        "interval": np.nan,
                        "observed": np.nan,
                        "predicted": item.get("subject_draw_median_survival"),
                        "lower_95": item.get("subject_draw_lower_95"),
                        "upper_95": item.get("subject_draw_upper_95"),
                        "observed_covered": np.nan,
                        "replicated_median": np.nan,
                        "posterior_predictive_tail_probability": np.nan,
                        "mean_survival_across_subjects_median": item.get(
                            "mean_survival_across_subjects_median"
                        ),
                        "proportion_subject_draws_below_0_01": item.get(
                            "proportion_subject_draws_below_0_01"
                        ),
                        "proportion_subject_draws_above_0_99": item.get(
                            "proportion_subject_draws_above_0_99"
                        ),
                        "source_cell": relative,
                    }
                )
        if isinstance(posterior, dict):
            replication = posterior.get("replicated_event_counts")
            fitted_survival = posterior.get("fitted_survival_check")
            if not isinstance(replication, dict) or not isinstance(fitted_survival, list):
                raise ValueError(
                    f"confirmatory Bayesian cell lacks replicated-event or fitted-survival checks: {relative}"
                )
            replication_records = [
                {"interval": "total", **replication["total"]},
                *replication.get("by_baseline_interval", []),
            ]
            for item in replication_records:
                rows.append(
                    {
                        "dataset": cell["dataset"],
                        "model_key": cell["model_key"],
                        "repeat": cell["repeat"],
                        "fold": cell["fold"],
                        "check": "posterior_predictive_replicated_event_count",
                        "time": np.nan,
                        "scaled_time": np.nan,
                        "interval": item.get("interval"),
                        "observed": item.get("observed"),
                        "predicted": item.get("replicated_mean"),
                        "lower_95": item.get("replicated_lower_95"),
                        "upper_95": item.get("replicated_upper_95"),
                        "observed_covered": item.get("observed_covered"),
                        "replicated_median": item.get("replicated_median"),
                        "posterior_predictive_tail_probability": item.get(
                            "posterior_predictive_tail_probability"
                        ),
                        "mean_survival_across_subjects_median": np.nan,
                        "proportion_subject_draws_below_0_01": np.nan,
                        "proportion_subject_draws_above_0_99": np.nan,
                        "source_cell": relative,
                    }
                )
            for item in fitted_survival:
                rows.append(
                    {
                        "dataset": cell["dataset"],
                        "model_key": cell["model_key"],
                        "repeat": cell["repeat"],
                        "fold": cell["fold"],
                        "check": "posterior_fitted_survival_comparison_not_replicated_data",
                        "time": item.get("time"),
                        "scaled_time": np.nan,
                        "interval": np.nan,
                        "observed": item.get("observed_km"),
                        "predicted": item.get("predicted_mean"),
                        "lower_95": item.get("lower_95"),
                        "upper_95": item.get("upper_95"),
                        "observed_covered": item.get("observed_covered"),
                        "replicated_median": np.nan,
                        "posterior_predictive_tail_probability": np.nan,
                        "mean_survival_across_subjects_median": np.nan,
                        "proportion_subject_draws_below_0_01": np.nan,
                        "proportion_subject_draws_above_0_99": np.nan,
                        "source_cell": relative,
                    }
                )
    return pd.DataFrame(rows)


def _render_predictive_checks(run: FrozenRun, registry: OutputRegistry) -> None:
    table = _predictive_check_rows(run)
    selected = [
        (relative, cell)
        for relative, cell in run.cells
        if cell["status"] == "complete" and str(cell["model_key"]).startswith("bayesian_")
    ]
    sources = _cell_sources(
        run,
        selected,
        ["model_details.prior_predictive", "model_details.posterior_predictive"],
    )
    _write_table(
        table,
        registry.output_dir / "tables" / "prior_posterior_predictive_checks",
        registry,
        sources=sources,
        note=(
            "Archived full-model prior survival, replicated event counts and "
            "separately labelled fitted-survival summaries"
        ),
    )
    datasets = sorted(table["dataset"].unique()) if not table.empty else []
    figure, axes = plt.subplots(
        max(1, len(datasets)),
        3,
        figsize=(15, max(3.8, 3.5 * len(datasets))),
        squeeze=False,
    )
    if table.empty:
        axes[0, 0].text(0.5, 0.5, "No archived predictive checks", ha="center", va="center")
        axes[0, 1].set_axis_off()
        axes[0, 2].set_axis_off()
    for row_index, dataset in enumerate(datasets):
        prior = table[
            (table["dataset"] == dataset)
            & (table["check"] == "prior_predictive_covariate_population_survival")
        ]
        replication = table[
            (table["dataset"] == dataset)
            & (table["check"] == "posterior_predictive_replicated_event_count")
            & (table["interval"].astype(str) == "total")
        ]
        fitted = table[
            (table["dataset"] == dataset)
            & (table["check"] == "posterior_fitted_survival_comparison_not_replicated_data")
        ]
        for model_index, (model, group) in enumerate(prior.groupby("model_key", sort=True)):
            axes[row_index, 0].scatter(
                group["scaled_time"],
                group["predicted"],
                s=10,
                alpha=0.25,
                color=COLORS[model_index % len(COLORS)],
                label=MODEL_LABELS.get(model, model),
            )
        axes[row_index, 0].set_ylim(0, 1)
        axes[row_index, 0].set_xlabel("Training-time scale")
        axes[row_index, 0].set_ylabel("Prior subject-draw median survival")
        axes[row_index, 0].set_title(f"{dataset.upper()} — full-model prior predictive")
        if len(prior):
            axes[row_index, 0].legend(frameon=False, fontsize=6)
        for model_index, (model, group) in enumerate(replication.groupby("model_key", sort=True)):
            axes[row_index, 1].scatter(
                group["observed"],
                group["predicted"],
                s=12,
                alpha=0.35,
                color=COLORS[model_index % len(COLORS)],
                label=MODEL_LABELS.get(model, model),
            )
        maximum_count = max(
            1.0,
            float(replication[["observed", "predicted"]].max().max()) if len(replication) else 1.0,
        )
        axes[row_index, 1].plot(
            [0, maximum_count],
            [0, maximum_count],
            color="black",
            linestyle="--",
            linewidth=0.8,
        )
        axes[row_index, 1].set_xlim(0, maximum_count * 1.05)
        axes[row_index, 1].set_ylim(0, maximum_count * 1.05)
        axes[row_index, 1].set_xlabel("Observed total event count")
        axes[row_index, 1].set_ylabel("Replicated mean total event count")
        axes[row_index, 1].set_title(f"{dataset.upper()} — replicated likelihood-scale data")
        for model_index, (model, group) in enumerate(fitted.groupby("model_key", sort=True)):
            axes[row_index, 2].scatter(
                group["observed"],
                group["predicted"],
                s=12,
                alpha=0.35,
                color=COLORS[model_index % len(COLORS)],
                label=MODEL_LABELS.get(model, model),
            )
        axes[row_index, 2].plot([0, 1], [0, 1], color="black", linestyle="--", linewidth=0.8)
        axes[row_index, 2].set_xlim(0, 1)
        axes[row_index, 2].set_ylim(0, 1)
        axes[row_index, 2].set_xlabel("Observed training Kaplan–Meier survival")
        axes[row_index, 2].set_ylabel("Fitted posterior mean survival")
        axes[row_index, 2].set_title(f"{dataset.upper()} — fitted survival (not replicated data)")
    figure.suptitle("Prior predictive, replicated-event and fitted-survival checks")
    _save_figure(
        figure,
        registry.output_dir / "figures" / "prior_posterior_predictive_checks",
        registry,
        title="Prior predictive, replicated-event and fitted-survival checks",
        sources=sources,
        note=(
            "Full-model prior survival, replicated event counts and fitted-survival "
            "comparisons are separately identified from archived checks"
        ),
    )


def _ph_rows_from_cells(run: FrozenRun) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for relative, cell in run.cells:
        if cell["status"] != "complete" or cell["model_key"] != "cox_ph":
            continue
        for item in cell.get("model_details", {}).get("ph_test", []):
            rows.append(
                {
                    "dataset": cell["dataset"],
                    "repeat": cell["repeat"],
                    "fold": cell["fold"],
                    "covariate": item.get("feature", item.get("covariate")),
                    "test_statistic": item.get("test_statistic"),
                    "p_value": item.get("p"),
                    "holm_adjusted_p": item.get("holm_adjusted_p"),
                    "holm_reject_0_05": item.get("holm_reject_0_05"),
                    "source_cell": relative,
                }
            )
    return pd.DataFrame(rows)


def _render_ph(
    run: FrozenRun,
    registry: OutputRegistry,
    *,
    robustness: dict[str, Any] | None,
) -> None:
    if robustness is not None and isinstance(robustness.get("ph_assessment"), dict):
        ph = robustness["ph_assessment"]
        table = pd.DataFrame(ph.get("covariate_tests", []))
        sources = [robustness["source_refs"]["ph_assessment.json"]]
    else:
        table = _ph_rows_from_cells(run)
        selected = [
            (relative, cell)
            for relative, cell in run.cells
            if cell["status"] == "complete" and cell["model_key"] == "cox_ph"
        ]
        sources = _cell_sources(run, selected, ["model_details.ph_test"])
    _write_table(
        table,
        registry.output_dir / "tables" / "proportional_hazards_tests",
        registry,
        sources=sources,
        note="Scaled Schoenfeld-residual PH tests with within-fit multiplicity decisions",
    )
    if table.empty:
        summary = pd.DataFrame(
            columns=["dataset", "covariate", "n_outer_fits", "holm_rejection_fraction"]
        )
    else:
        reject_column = "holm_reject_0_05"
        if reject_column not in table:
            raise ValueError("PH table lacks the stored Holm rejection decision")
        summary = (
            table.groupby(["dataset", "covariate"], sort=True)[reject_column]
            .agg(n_outer_fits="size", holm_rejection_fraction="mean")
            .reset_index()
        )
    _write_table(
        summary,
        registry.output_dir / "tables" / "proportional_hazards_summary",
        registry,
        sources=sources,
        note="Descriptive stability of within-fit PH departures across outer folds",
    )
    datasets = sorted(summary["dataset"].unique()) if not summary.empty else []
    figure, axes = plt.subplots(
        max(1, len(datasets)), 1, figsize=(9, max(3.5, 3.0 * len(datasets))), squeeze=False
    )
    if summary.empty:
        axes[0, 0].text(0.5, 0.5, "No available PH test records", ha="center", va="center")
    for axis, dataset in zip(axes.flat, datasets, strict=False):
        subset = summary[summary["dataset"] == dataset].sort_values(
            ["holm_rejection_fraction", "covariate"]
        )
        y = np.arange(len(subset))
        axis.barh(y, subset["holm_rejection_fraction"], color=COLORS[0], alpha=0.75)
        axis.set_yticks(y, subset["covariate"])
        axis.set_xlim(0, 1)
        axis.set_xlabel("Fraction of outer Cox fits rejecting PH after within-fit Holm control")
        axis.set_title(dataset.upper())
    figure.suptitle("Proportional-hazards assessment")
    _save_figure(
        figure,
        registry.output_dir / "figures" / "proportional_hazards_assessment",
        registry,
        title="Proportional-hazards assessment",
        sources=sources,
        note="Departure frequencies are limitations, not post-hoc model-selection rules",
    )


def verify_explainability_artifact(
    path: Path, run: FrozenRun
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Verify an optional explainability result and its link to this source run."""
    artifact_path = path.resolve()
    result = _load_mapping(artifact_path)
    _verify_content_hash(result, "result_content_sha256", artifact_path)
    if result.get("analysis") != "confirmatory_explainability_from_frozen_cells":
        raise ValueError("optional explainability file has an unknown analysis type")
    if result.get("analysis_mode") != run.mode:
        raise RuntimeError("explainability and source-run analysis modes disagree")
    if result.get("evidence_status") != run.evidence_status:
        raise RuntimeError("explainability and source-run evidence statuses disagree")
    source_run = result.get("source_run")
    if not isinstance(source_run, dict):
        raise ValueError("explainability result has no source_run mapping")
    if source_run.get("directory_name") != run.run_dir.name:
        raise RuntimeError("explainability result references a different source run")
    if source_run.get("manifest_content_sha256") != run.manifest.get("manifest_content_sha256"):
        raise RuntimeError("explainability manifest lineage does not match")
    if source_run.get("completion_content_sha256") != run.completion.get(
        "completion_content_sha256"
    ):
        raise RuntimeError("explainability completion lineage does not match")
    used = source_run.get("cell_content_hashes_used")
    if not isinstance(used, dict):
        raise ValueError("explainability source_run lacks cell hashes")
    cell_content = {relative: cell["cell_content_sha256"] for relative, cell in run.cells}
    for relative, claimed in used.items():
        if cell_content.get(relative) != claimed:
            raise RuntimeError(f"explainability cell-content lineage does not match: {relative}")
    source_ref = {
        "artifact": str(artifact_path),
        "sha256": sha256_file(artifact_path),
        "content_sha256": result["result_content_sha256"],
        "result_keys": [
            "agreement_uncertainty",
            "group_stability",
            "convergence",
            "secondary_cross_model_analysis.cox_ph.paired_same_model_minus_cox",
        ],
    }
    return result, source_ref


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
    table = _explanation_rows(result)
    stability = pd.DataFrame(result.get("group_stability", []))
    _write_table(
        table,
        registry.output_dir / "tables" / "explanation_agreement",
        registry,
        sources=[source_ref],
        note="Verified H3a and paired H3b explanation-agreement estimates",
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
    figure.suptitle("Explanation agreement and stability")
    _save_figure(
        figure,
        registry.output_dir / "figures" / "explanation_stability",
        registry,
        title="Explanation agreement and stability",
        sources=[source_ref],
        note="H3a and H3b estimates are read only from the verified explainability artifact",
    )


def verify_robustness_run(
    robustness_dir: Path, run: FrozenRun
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Verify a frozen robustness directory and every declared artifact hash."""
    root = robustness_dir.resolve()
    manifest_path = root / "manifest.json"
    completion_path = root / "completion.json"
    manifest = _load_mapping(manifest_path)
    completion = _load_mapping(completion_path)
    _verify_content_hash(manifest, "manifest_content_sha256", manifest_path)
    _verify_content_hash(completion, "completion_content_sha256", completion_path)
    run_config = manifest.get("run_config")
    if not isinstance(run_config, dict) or manifest.get("config_sha256") != canonical_json_hash(
        run_config
    ):
        raise RuntimeError("robustness manifest configuration hash is invalid")
    mode = run_config.get("mode")
    if completion.get("analysis_mode") != mode:
        raise RuntimeError("robustness manifest and completion modes disagree")
    if mode != "robustness":
        raise RuntimeError("only a production robustness run may supplement confirmatory evidence")
    if run_config.get("confirmatory_run") != run.run_dir.name:
        raise RuntimeError("robustness artifact references a different confirmatory run")

    inventory = completion.get("cell_sha256")
    if not isinstance(inventory, dict):
        raise ValueError("robustness completion has no cell inventory")
    actual_paths = sorted((root / "cells").glob("*/*/*/*.json"))
    actual_relative = {str(path.relative_to(root)) for path in actual_paths}
    if actual_relative != set(inventory):
        raise RuntimeError("robustness cells do not match their completion inventory")
    if int(completion.get("stored_cells", -1)) != len(actual_paths):
        raise RuntimeError("robustness stored-cell count is invalid")
    status_counts: dict[str, int] = {}
    source_refs: dict[str, dict[str, Any]] = {}
    cells: list[dict[str, Any]] = []
    for path in actual_paths:
        relative = str(path.relative_to(root))
        observed = sha256_file(path)
        if inventory[relative] != observed:
            raise RuntimeError(f"robustness cell file hash does not match: {path}")
        cell = _load_mapping(path)
        _verify_content_hash(cell, "cell_content_sha256", path)
        if cell.get("analysis_mode") != "robustness":
            raise RuntimeError(f"robustness cell has incorrect analysis mode: {path}")
        status = str(cell.get("status"))
        status_counts[status] = status_counts.get(status, 0) + 1
        cells.append(cell)
        source_refs[relative] = {
            "artifact": str(path),
            "sha256": observed,
            "result_keys": ["status", "condition", "metrics", "fit_attempts"],
        }
    if status_counts != completion.get("status_counts"):
        raise RuntimeError("robustness status counts do not match stored cells")
    if int(completion.get("planned_cells_in_this_invocation", -1)) != len(cells):
        raise RuntimeError("robustness run is incomplete")

    aggregates = completion.get("aggregate_sha256")
    if not isinstance(aggregates, dict):
        raise ValueError("robustness completion has no aggregate inventory")
    required = {
        "paired_ibs_inference.json",
        "analysis_availability.json",
        "feasibility_plan.json",
    }
    if not required.issubset(aggregates):
        raise ValueError(
            "robustness completion omits aggregates: "
            + ", ".join(sorted(required - set(aggregates)))
        )
    loaded: dict[str, Any] = {}
    for name, claimed in sorted(aggregates.items()):
        path = _safe_child(root, str(name))
        if not path.is_file() or sha256_file(path) != claimed:
            raise RuntimeError(f"robustness aggregate hash does not match: {path}")
        value = _load_mapping(path)
        if "result_content_sha256" in value:
            _verify_content_hash(value, "result_content_sha256", path)
        elif "feasibility_content_sha256" in value:
            _verify_content_hash(value, "feasibility_content_sha256", path)
        loaded[path.name] = value
        source_refs[path.name] = {
            "artifact": str(path),
            "sha256": str(claimed),
            "result_keys": sorted(value),
        }

    confirmatory_inputs = manifest.get("input_sha256", {})
    if not isinstance(confirmatory_inputs, dict):
        raise ValueError("robustness manifest has no input hashes")
    for source_name, observed_hash in (
        ("manifest.json", sha256_file(run.run_dir / "manifest.json")),
        ("completion.json", sha256_file(run.run_dir / "completion.json")),
    ):
        matches = [
            value
            for key, value in confirmatory_inputs.items()
            if key.endswith(f"/{run.run_dir.name}/{source_name}")
        ]
        if len(matches) != 1 or matches[0] != observed_hash:
            raise RuntimeError(
                f"robustness manifest does not hash-link the confirmatory {source_name}"
            )

    result = {
        "manifest": manifest,
        "completion": completion,
        "cells": cells,
        "paired_ibs_inference": loaded["paired_ibs_inference.json"],
        "analysis_availability": loaded["analysis_availability.json"],
        "feasibility_plan": loaded["feasibility_plan.json"],
        "ph_assessment": loaded.get("ph_assessment.json"),
        "source_refs": source_refs,
    }
    summary_ref = {
        "artifact": str(root),
        "manifest_sha256": sha256_file(manifest_path),
        "completion_sha256": sha256_file(completion_path),
        "manifest_content_sha256": manifest["manifest_content_sha256"],
        "completion_content_sha256": completion["completion_content_sha256"],
    }
    return result, summary_ref


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


def _snapshot_records(run: FrozenRun) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for relative, cell in run.cells:
        if not str(cell.get("model_key", "")).startswith("bayesian_"):
            continue
        details = cell.get("model_details", {})
        snapshot = details.get("posterior_trace_snapshot")
        diagnostics = details.get("diagnostics", {})
        if isinstance(snapshot, dict):
            records.append(
                {
                    "relative": relative,
                    "cell": cell,
                    "snapshot": snapshot,
                    "attempt": None,
                    "status": cell["status"],
                    "diagnostics": diagnostics,
                    "result_key": "model_details.posterior_trace_snapshot",
                }
            )
        for attempt_index, attempt in enumerate(cell.get("fit_attempts", []), start=1):
            attempt_snapshot = attempt.get("posterior_trace_snapshot")
            if isinstance(attempt_snapshot, dict):
                records.append(
                    {
                        "relative": relative,
                        "cell": cell,
                        "snapshot": attempt_snapshot,
                        "attempt": attempt_index,
                        "status": cell["status"],
                        "diagnostics": attempt.get("diagnostics", {}),
                        "result_key": f"fit_attempts.{attempt_index - 1}.posterior_trace_snapshot",
                    }
                )
    return records


def _trace_array(variable: dict[str, Any]) -> tuple[np.ndarray, list[str]]:
    dims = variable.get("dims")
    if not isinstance(dims, list) or "chain" not in dims or "draw" not in dims:
        raise ValueError("trace snapshot variable must identify chain and draw dimensions")
    values = np.asarray(variable.get("values"), dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("trace snapshot contains non-finite values")
    if values.ndim != len(dims):
        raise ValueError("trace snapshot dimensions do not match values")
    chain_axis = dims.index("chain")
    draw_axis = dims.index("draw")
    values = np.moveaxis(values, (chain_axis, draw_axis), (0, 1))
    remaining_dims = [name for name in dims if name not in {"chain", "draw"}]
    flattened = values.reshape(values.shape[0], values.shape[1], -1)
    return flattened, remaining_dims


def _component_labels(
    variable_name: str,
    n_components: int,
    cell: dict[str, Any],
) -> list[str]:
    if variable_name == "beta":
        summary = cell.get("model_details", {}).get("coefficient_summary")
        if isinstance(summary, list):
            features = [str(row.get("feature")) for row in summary]
            if len(features) == n_components and all(value != "None" for value in features):
                return features
        metadata = cell.get("preprocessing", {})
        features = metadata.get("feature_names")
        if isinstance(features, list) and len(features) == n_components:
            return [str(value) for value in features]
    if n_components == 1:
        return [variable_name]
    return [f"{variable_name}[{index}]" for index in range(n_components)]


def _render_trace_variable(
    record: dict[str, Any],
    variable_name: str,
    registry: OutputRegistry,
) -> list[Path]:
    snapshot = record["snapshot"]
    variables = snapshot.get("variables")
    if not isinstance(variables, dict) or variable_name not in variables:
        raise ValueError("trace snapshot variable inventory is malformed")
    values, _remaining_dims = _trace_array(variables[variable_name])
    draws = np.asarray(snapshot.get("draw_indices"), dtype=int)
    if draws.ndim != 1 or len(draws) != values.shape[1]:
        raise ValueError("trace draw-index inventory does not match stored values")
    labels = _component_labels(variable_name, values.shape[2], record["cell"])
    n_components = values.shape[2]
    figure, axes = plt.subplots(
        n_components,
        2,
        figsize=(12, max(3.0, 1.8 * n_components)),
        squeeze=False,
    )
    for component in range(n_components):
        trace_axis, marginal_axis = axes[component]
        for chain in range(values.shape[0]):
            trace_axis.plot(
                draws,
                values[chain, :, component],
                linewidth=0.65,
                alpha=0.8,
                color=COLORS[chain % len(COLORS)],
                label=f"chain {chain + 1}" if component == 0 else None,
            )
        marginal_axis.hist(
            values[:, :, component].reshape(-1),
            bins=min(30, max(10, int(np.sqrt(values.shape[0] * values.shape[1])))),
            density=True,
            color=COLORS[0],
            alpha=0.65,
        )
        trace_axis.set_ylabel(labels[component])
        trace_axis.set_xlabel("Original retained draw index")
        marginal_axis.set_xlabel("Stored thinned value")
        marginal_axis.set_ylabel("Density")
    axes[0, 0].legend(frameon=False, ncols=min(4, values.shape[0]))
    cell = record["cell"]
    attempt = f" attempt {record['attempt']}" if record["attempt"] is not None else ""
    title = (
        "Visualization-only thinned posterior — "
        f"{cell['dataset'].upper()} {cell['model_key']} R{cell['repeat']} F{cell['fold']}"
        f"{attempt}: {variable_name}"
    )
    figure.suptitle(title)
    suffix = f"_attempt_{record['attempt']:02d}" if record["attempt"] is not None else ""
    base = (
        registry.output_dir
        / "figures"
        / "traces"
        / (
            f"trace_{_slug(cell['dataset'])}_{_slug(cell['model_key'])}_"
            f"r{int(cell['repeat']):02d}_f{int(cell['fold']):02d}{suffix}_{_slug(variable_name)}"
        )
    )
    source_ref = _source(
        registry.run,
        record["relative"],
        [f"{record['result_key']}.variables.{variable_name}"],
    )
    return _save_figure(
        figure,
        base,
        registry,
        title=title,
        sources=[source_ref],
        note=(
            "Thinned snapshot for visual diagnosis only; numerical diagnostics use all retained draws"
        ),
    )


def _render_trace_snapshots(run: FrozenRun, registry: OutputRegistry) -> None:
    records = _snapshot_records(run)
    representatives: set[tuple[str, str]] = set()
    inventory_rows: list[dict[str, Any]] = []
    rendered_output_lookup: dict[int, list[str]] = {}
    selected_indices: set[int] = set()
    for index, record in enumerate(records):
        cell = record["cell"]
        key = (str(cell["dataset"]), str(cell["model_key"]))
        failed_attempt = record["attempt"] is not None and cell["status"] != "complete"
        if failed_attempt or (record["attempt"] is None and key not in representatives):
            selected_indices.add(index)
            if record["attempt"] is None:
                representatives.add(key)

    for index, record in enumerate(records):
        snapshot = record["snapshot"]
        variables = snapshot.get("variables")
        if not isinstance(variables, dict):
            raise ValueError("trace snapshot lacks a variable mapping")
        paths: list[str] = []
        if index in selected_indices:
            diagnostics_checked = record.get("diagnostics", {}).get("variables_checked")
            requested = (
                [str(value) for value in diagnostics_checked]
                if isinstance(diagnostics_checked, list)
                else list(variables)
            )
            requested = [name for name in requested if name in variables]
            if not requested:
                requested = list(variables)
            for variable_name in sorted(set(requested)):
                written = _render_trace_variable(record, variable_name, registry)
                paths.extend(str(path.relative_to(registry.output_dir)) for path in written)
        rendered_output_lookup[index] = paths
        cell = record["cell"]
        for variable_name, variable in sorted(variables.items()):
            values, _dims = _trace_array(variable)
            inventory_rows.append(
                {
                    "dataset": cell["dataset"],
                    "model_key": cell["model_key"],
                    "repeat": cell["repeat"],
                    "fold": cell["fold"],
                    "cell_status": cell["status"],
                    "attempt": record["attempt"],
                    "variable": variable_name,
                    "stored_chains": values.shape[0],
                    "stored_draws_per_chain": values.shape[1],
                    "components": values.shape[2],
                    "purpose": snapshot.get("purpose"),
                    "rendered": index in selected_indices,
                    "rendered_outputs": ";".join(paths),
                    "source_cell": record["relative"],
                    "source_result_key": record["result_key"],
                }
            )
    table = pd.DataFrame(
        inventory_rows,
        columns=[
            "dataset",
            "model_key",
            "repeat",
            "fold",
            "cell_status",
            "attempt",
            "variable",
            "stored_chains",
            "stored_draws_per_chain",
            "components",
            "purpose",
            "rendered",
            "rendered_outputs",
            "source_cell",
            "source_result_key",
        ],
    )
    sources = [_source(run, record["relative"], [record["result_key"]]) for record in records]
    _write_table(
        table,
        registry.output_dir / "tables" / "posterior_trace_snapshot_inventory",
        registry,
        sources=sources,
        note=(
            "Inventory of all archived visualization-only trace snapshots; every failed-attempt "
            "snapshot and one complete representative per cohort/prior are rendered"
        ),
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
        renderer_path=Path(__file__).resolve(),
    )
    return destination


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Pure renderer for a completed frozen confirmatory run. Rehearsals "
            "produce a labelled runtime-only package."
        )
    )
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--explainability-artifact", type=Path, default=None)
    parser.add_argument("--robustness-dir", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    output_dir = (
        args.output_dir.resolve()
        if args.output_dir is not None
        else PROJECT_ROOT / "reports" / "rendered" / run_dir.name
    )
    rendered = render_run(
        run_dir,
        output_dir,
        explainability_artifact=(
            args.explainability_artifact.resolve()
            if args.explainability_artifact is not None
            else None
        ),
        robustness_dir=(args.robustness_dir.resolve() if args.robustness_dir is not None else None),
    )
    print(f"rendered_artifact={rendered}", flush=True)
    print(f"evidence_lineage={rendered / 'lineage.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
