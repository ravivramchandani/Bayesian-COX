"""Validate frozen cell, aggregate and supplemental evidence before rendering.

Rendering starts here. :func:`verify_frozen_run` checks a confirmatory or
rehearsal run directory; :func:`verify_explainability_artifact` and
:func:`verify_robustness_run` check the optional supplements and their link
to that run. Each returns only after every hash, count and identity check
has passed, and raises otherwise, so the renderers downstream read verified
content only. :func:`_source` turns a verified file into the lineage record
attached to each output.

Every stored record carries a content hash: the SHA-256 of the canonical JSON
encoding of the record without its hash field. Files are also checked by the
SHA-256 of their bytes against the inventory that lists them. Other modules
(the confirmatory and post-hoc pipelines, ``src/utils/posthoc_evidence.py``
and several scripts) import these checks for the same purpose."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib

# Select the non-interactive backend before any rendering module imports pyplot.
matplotlib.use("Agg")

import pandas as pd


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest of one file.

    Args:
        path: File whose bytes are hashed.

    Returns:
        The 64-character hexadecimal digest of the file bytes.
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json_hash(value: Any) -> str:
    """Hash a JSON-compatible object using the analysis canonical encoding.

    Keys are sorted, separators carry no spaces, text is UTF-8 and NaN or
    infinite numbers are rejected. This matches
    ``src.utils.reproducibility.canonical_json_hash``, which sealed the
    records being checked.

    Args:
        value: JSON-compatible object with finite numeric values.

    Returns:
        The hexadecimal SHA-256 of the canonical UTF-8 JSON bytes.
    """
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _load_mapping(path: Path) -> dict[str, Any]:
    """Read a JSON file that must contain a mapping.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the top-level value is not a mapping.
    """
    if not path.is_file():
        raise FileNotFoundError(f"required frozen artifact is missing: {path}")
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON mapping")
    return value


def _verify_content_hash(record: dict[str, Any], hash_field: str, path: Path) -> str:
    """Check that a record's stored content hash matches the rest of the record.

    Args:
        record: Parsed record.
        hash_field: Name of the field that holds the claimed hash.
        path: Source file, used in error messages.

    Returns:
        The recomputed hash.

    Raises:
        ValueError: If the hash field is missing or not a string.
        RuntimeError: If the recomputed hash differs.
    """
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
    """Resolve an inventory path and require it to stay inside ``root``.

    Resolution follows ``..`` and symbolic links, so an inventory entry
    cannot point at a file outside the run directory.

    Raises:
        ValueError: If the resolved path lies outside ``root``.
    """
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"artifact inventory escapes its run directory: {relative}") from exc
    return candidate


def _slug(value: object) -> str:
    """Return a lower-case file-name fragment of letters, digits and underscores.

    Returns ``unnamed`` when nothing remains.
    """
    text = re.sub(r"[^a-zA-Z0-9]+", "_", str(value)).strip("_").lower()
    return text or "unnamed"


def _finite(value: Any, *, field: str) -> float:
    """Convert a stored value to a float and reject NaN or infinity.

    Raises:
        ValueError: If the value is not finite; ``field`` names it.
    """
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field} must be finite")
    return number


@dataclass(frozen=True)
class FrozenRun:
    """A run whose manifests, aggregates and cell inventory have been verified.

    Attributes:
        run_dir: Resolved run directory.
        manifest: Parsed ``manifest.json``.
        completion: Parsed ``completion.json``.
        inference: Parsed ``inference.json``, the paired-contrast aggregate.
        cells: ``(path relative to run_dir, parsed cell)`` for every stored
            cell, in sorted path order.
        source_hashes: File SHA-256 of every verified source, keyed by path
            relative to ``run_dir``; lineage may cite only these files.
    """

    run_dir: Path
    manifest: dict[str, Any]
    completion: dict[str, Any]
    inference: dict[str, Any]
    cells: tuple[tuple[str, dict[str, Any]], ...]
    source_hashes: dict[str, str]

    @property
    def mode(self) -> str:
        """Return the analysis mode, ``confirmatory`` or ``rehearsal``."""
        return str(self.completion["analysis_mode"])

    @property
    def evidence_status(self) -> str:
        """Return ``confirmatory`` for a confirmatory run and ``rehearsal_only`` otherwise."""
        return "confirmatory" if self.mode == "confirmatory" else "rehearsal_only"


def verify_frozen_run(run_dir: Path) -> FrozenRun:
    """Load a confirmatory/rehearsal run only after exhaustive hash checks.

    The checks, in order:

    - ``manifest.json`` and ``completion.json`` match their content hashes,
      and the manifest's configuration and dependency-set hashes match.
    - The mode is ``rehearsal`` or ``confirmatory`` in both files; a
      confirmatory manifest declares a frozen design and a protocol-freeze
      hash.
    - Every aggregate in the completion inventory, including
      ``fold_metrics.csv``, ``out_of_fold_predictions.csv.gz`` and
      ``inference.json``, lies inside the run and matches its file hash.
    - The cell files match the completion inventory exactly; each matches
      its file and content hashes, the run's mode and evidence status, and
      has a unique key and a known status; the status counts match.
    - The cell count equals the planned grid (datasets x models x repeats x
      folds, with any rehearsal fold limit); a confirmatory run forms that
      grid exactly.
    - ``fold_metrics.csv`` has exactly one row per complete cell, matched by
      key and cell content hash.

    Args:
        run_dir: Run directory containing the manifest, completion record,
            aggregates and ``cells/``.

    Returns:
        The verified run.

    Raises:
        FileNotFoundError: If a required JSON file is missing.
        ValueError: If a record is malformed or a required entry is missing.
        RuntimeError: If any hash, count, mode or key check fails.
    """
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
    """Return the lineage record citing one verified file of the run.

    Args:
        run: The verified run.
        relative: Path of the source file relative to the run directory.
        result_keys: Fields of that file the output was derived from.

    Returns:
        ``artifact`` (the path prefixed with ``source_run/``), the verified
        file ``sha256`` and the sorted, de-duplicated ``result_keys``.

    Raises:
        KeyError: If the file was not verified by :func:`verify_frozen_run`.
    """
    if relative not in run.source_hashes:
        raise KeyError(f"unverified source requested for lineage: {relative}")
    return {
        "artifact": f"source_run/{relative}",
        "sha256": run.source_hashes[relative],
        "result_keys": sorted(set(result_keys)),
    }


def verify_explainability_artifact(
    path: Path, run: FrozenRun
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Verify an optional explainability result and its link to this source run.

    The result must match its content hash, be a frozen-cell explanation
    result with the run's mode and evidence status, name the run's directory,
    manifest and completion content hashes, and cite for every cell it used
    the content hash that cell has in the run.

    Args:
        path: Explainability result written by
            :func:`src.explainability.frozen_cells.write_explainability_result`.
        run: The verified source run.

    Returns:
        The parsed result and its lineage record: path, file hash, content
        hash and the result keys the renderer reads.

    Raises:
        FileNotFoundError: If the file is missing.
        ValueError: If the result is malformed or of another analysis type.
        RuntimeError: If a hash or any link to the source run does not match.
    """
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


def verify_robustness_run(
    robustness_dir: Path, run: FrozenRun
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Verify a frozen robustness directory and every declared artifact hash.

    The manifest and completion record must match their content and
    configuration hashes, be in ``robustness`` mode and name this
    confirmatory run. Every cell file must match the completion inventory,
    its file and content hashes and the robustness mode, with matching status
    and planned counts. Every aggregate must lie inside the directory and
    match its file hash (and its content hash where it has one), and the three
    required aggregates must be present. Finally the robustness manifest must
    record exactly one input hash for each of this run's ``manifest.json`` and
    ``completion.json``, equal to the current file hashes.

    Args:
        robustness_dir: Completed robustness run directory.
        run: The verified confirmatory run it supplements.

    Returns:
        The parsed manifest, completion, cells and aggregates with a
        ``source_refs`` lineage record per file, and a summary lineage record
        for the directory.

    Raises:
        FileNotFoundError: If a required JSON file is missing.
        ValueError: If a record or inventory is malformed or incomplete.
        RuntimeError: If any hash, mode, count or link check fails.
    """
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
