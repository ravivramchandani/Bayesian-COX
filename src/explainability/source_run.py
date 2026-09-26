"""Verification and loading of the frozen run that the explanation stage reads.

This is the first step of the confirmatory explanation stage. It checks the
run's manifest, completion record and every stored cell against their recorded
hashes, sorts the cells into interpretable Bayesian cells, exclusions and Cox
partners, reloads each cohort from its raw file, checks that cells from the
same outer fold share subjects and preprocessing, and reads the frozen Cox
coefficients used by the secondary comparison. No model is fitted or refitted.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.data.fold_preprocessing import FoldFeaturePreprocessor
from src.utils.io import read_mapping
from src.utils.reproducibility import canonical_json_hash, sha256_file

FoldKey = tuple[str, int, int]
StoredCell = tuple[Path, dict[str, Any]]

FROZEN_CONFIG_FILES = ("config/datasets.yaml", "config/confirmatory.yaml")


@dataclass(frozen=True)
class SourceRun:
    """A frozen run whose manifest, completion record and cells passed every hash check.

    Attributes:
        run_dir: The run directory.
        project_root: Repository root that holds ``config/`` and ``data/``.
        manifest: Parsed ``manifest.json``.
        completion: Parsed ``completion.json``.
        input_hashes: The manifest's ``input_sha256`` mapping, keyed by
            project-relative path.
        cells: Every stored cell as ``(path, parsed cell)``, in sorted path order.
        dataset_configs: Parsed ``config/datasets.yaml``.
        feature_set: Feature-set name the run was fitted with.
    """

    run_dir: Path
    project_root: Path
    manifest: dict[str, Any]
    completion: dict[str, Any]
    input_hashes: dict[str, Any]
    cells: list[StoredCell]
    dataset_configs: dict[str, Any]
    feature_set: str

    def relative(self, path: Path) -> str:
        """Return a cell path relative to the run directory."""
        return str(path.relative_to(self.run_dir))


@dataclass(frozen=True)
class CellInventory:
    """The stored cells sorted by the role they play in the explanation stage.

    Attributes:
        bayesian_cells: Complete Bayesian cells that may be interpreted.
        exclusions: One record per Bayesian cell that may not be interpreted.
        cox_cells: Every Cox PH cell, keyed by ``(dataset, repeat, fold)``.
        secondary_models: Sorted model keys of every non-Bayesian cell.
    """

    bayesian_cells: list[StoredCell]
    exclusions: list[dict[str, Any]]
    cox_cells: dict[FoldKey, StoredCell]
    secondary_models: list[Any]


@dataclass(frozen=True)
class Cohort:
    """One raw cohort file with its subject identifiers.

    Attributes:
        raw: The raw file as read from disk.
        subject_ids: One identifier per raw row, in file order.
        positions: Row position of each identifier.
    """

    raw: pd.DataFrame
    subject_ids: np.ndarray
    positions: dict[str, int]


@dataclass(frozen=True)
class CellLineage:
    """The subjects and preprocessing state that a Bayesian cell was fitted on.

    Attributes:
        fold_key: ``(dataset, repeat, fold)`` of the outer fold.
        train_ids: Outer-training subject identifiers, in cell order.
        validation_ids: Outer-validation subject identifiers, in cell order.
        record: The subject lists and preprocessing hash that every cell of
            the same outer fold must share.
    """

    fold_key: FoldKey
    train_ids: list[str]
    validation_ids: list[str]
    record: dict[str, Any]


@dataclass(frozen=True)
class PairedCox:
    """The frozen Cox PH cell from the same outer fold as a Bayesian cell.

    Attributes:
        relative_path: Cell path relative to the run directory.
        cell: The parsed Cox cell.
        coefficients: Cox coefficients in the Bayesian cell's feature order.
    """

    relative_path: str
    cell: dict[str, Any]
    coefficients: np.ndarray


def _verify_content_hash(record: dict[str, Any], hash_field: str, path: Path) -> str:
    """Check that a record's stored content hash matches the rest of the record."""
    expected = record.get(hash_field)
    if not isinstance(expected, str):
        raise ValueError(f"{path} is missing {hash_field}")
    unhashed = dict(record)
    unhashed.pop(hash_field, None)
    observed = canonical_json_hash(unhashed)
    if observed != expected:
        raise RuntimeError(f"content hash does not match: {path}")
    return observed


def _verify_frozen_configs(project_root: Path, input_hashes: dict[str, Any]) -> None:
    """Check that the current dataset and run configuration match the frozen run."""
    for relative in FROZEN_CONFIG_FILES:
        if relative in input_hashes:
            path = project_root / relative
            if sha256_file(path) != input_hashes[relative]:
                raise RuntimeError(f"current {relative} does not match the frozen run manifest")


def _load_verified_cells(run_dir: Path, completion: dict[str, Any]) -> list[StoredCell]:
    """Load every stored cell after checking it against the completion inventory."""
    recorded_files = completion.get("all_stored_cell_hashes")
    if not isinstance(recorded_files, dict):
        raise ValueError("completion artifact has no stored-cell hash mapping")
    actual_paths = sorted((run_dir / "cells").glob("*/*/*.json"))
    actual_relative = {str(path.relative_to(run_dir)) for path in actual_paths}
    if actual_relative != set(recorded_files):
        raise RuntimeError("stored cell files do not match the completion inventory")
    if int(completion.get("stored_cells", -1)) != len(actual_paths):
        raise RuntimeError("stored cell count does not match the completion artifact")

    cells: list[StoredCell] = []
    for path in actual_paths:
        relative = str(path.relative_to(run_dir))
        if sha256_file(path) != recorded_files[relative]:
            raise RuntimeError(f"stored cell file hash does not match: {path}")
        cell = read_mapping(path)
        _verify_content_hash(cell, "cell_content_sha256", path)
        cells.append((path, cell))
    return cells


def verify_source_run(run_dir: Path, project_root: Path) -> SourceRun:
    """Verify a frozen run and load its cells.

    The manifest and completion record must match their own content hashes;
    the current ``config/datasets.yaml`` and ``config/confirmatory.yaml`` must
    match the hashes the manifest recorded; the set of cell files must match
    the completion inventory exactly; and each cell file must match both its
    recorded file hash and its internal content hash.

    Args:
        run_dir: Resolved run directory.
        project_root: Resolved repository root.

    Returns:
        The verified run.
    """
    manifest_path = run_dir / "manifest.json"
    completion_path = run_dir / "completion.json"
    manifest = read_mapping(manifest_path)
    completion = read_mapping(completion_path)
    _verify_content_hash(manifest, "manifest_content_sha256", manifest_path)
    _verify_content_hash(completion, "completion_content_sha256", completion_path)

    input_hashes = manifest.get("input_sha256")
    if not isinstance(input_hashes, dict):
        raise ValueError("run manifest has no input hash mapping")
    _verify_frozen_configs(project_root, input_hashes)
    cells = _load_verified_cells(run_dir, completion)

    dataset_configs = read_mapping(project_root / "config" / "datasets.yaml")
    feature_set = manifest.get("run_config", {}).get("protocol", {}).get("feature_set")
    if not isinstance(feature_set, str):
        raise ValueError("run manifest does not identify its feature set")
    return SourceRun(
        run_dir=run_dir,
        project_root=project_root,
        manifest=manifest,
        completion=completion,
        input_hashes=input_hashes,
        cells=cells,
        dataset_configs=dataset_configs,
        feature_set=feature_set,
    )


def _is_bayesian(cell: dict[str, Any]) -> bool:
    """Return whether a cell holds one of the Bayesian Cox models."""
    return str(cell.get("model_key", "")).startswith("bayesian_")


def fold_key(cell: dict[str, Any]) -> FoldKey:
    """Return the ``(dataset, repeat, fold)`` key of a cell's outer fold."""
    return (str(cell["dataset"]), int(cell["repeat"]), int(cell["fold"]))


def _exclusion_record(cell: dict[str, Any], relative_path: str) -> dict[str, Any] | None:
    """Return why a Bayesian cell may not be interpreted, or ``None`` if it may."""
    if cell.get("status") != "complete":
        return {
            "cell": relative_path,
            "status": cell.get("status"),
            "reason": "only complete Bayesian cells may be interpreted",
        }
    if cell.get("analysis_mode") == "confirmatory" and not cell.get("model_details", {}).get(
        "diagnostics", {}
    ).get("converged", False):
        return {
            "cell": relative_path,
            "status": "failed_diagnostic_recheck",
            "reason": "confirmatory Bayesian diagnostics are not converged",
        }
    return None


def classify_cells(source: SourceRun) -> CellInventory:
    """Sort the stored cells into interpretable Bayesian cells, exclusions and Cox cells.

    A Bayesian cell is interpreted only when it completed and, in a
    confirmatory run, its MCMC convergence diagnostics passed. Every other
    Bayesian cell is recorded as an exclusion with its reason, so no failed
    cell disappears silently.
    """
    secondary_models = sorted(
        {cell.get("model_key") for _, cell in source.cells if not _is_bayesian(cell)}
    )
    exclusions: list[dict[str, Any]] = []
    bayesian_cells: list[StoredCell] = []
    cox_cells: dict[FoldKey, StoredCell] = {}
    for path, cell in source.cells:
        if cell.get("model_key") == "cox_ph":
            key = fold_key(cell)
            if key in cox_cells:
                raise RuntimeError(f"duplicate Cox cell for {key}")
            cox_cells[key] = (path, cell)
        if not _is_bayesian(cell):
            continue
        exclusion = _exclusion_record(cell, source.relative(path))
        if exclusion is not None:
            exclusions.append(exclusion)
            continue
        bayesian_cells.append((path, cell))
    if not bayesian_cells:
        raise RuntimeError("the frozen run has no complete, interpretable Bayesian cells")
    return CellInventory(
        bayesian_cells=bayesian_cells,
        exclusions=exclusions,
        cox_cells=cox_cells,
        secondary_models=secondary_models,
    )


def verify_raw_data(source: SourceRun, cell: dict[str, Any]) -> str:
    """Check a cell's raw data file against the cell and the manifest.

    Returns:
        The SHA-256 of the raw file.
    """
    dataset = str(cell["dataset"])
    if dataset not in source.dataset_configs:
        raise ValueError(f"cell references unknown dataset {dataset!r}")
    dataset_config = source.dataset_configs[dataset]
    raw_hash = sha256_file(source.project_root / dataset_config["raw_file"])
    if raw_hash != cell.get("dataset_sha256"):
        raise RuntimeError(f"{dataset} raw data do not match the cell hash")
    relative_raw = str(Path(dataset_config["raw_file"]))
    if source.input_hashes.get(relative_raw) != raw_hash:
        raise RuntimeError(f"{dataset} raw data do not match the run manifest")
    return raw_hash


def feature_specification(dataset_config: dict[str, Any], feature_set: str) -> dict[str, Any]:
    """Return the feature specification that a run's feature set names for a dataset."""
    if feature_set == "primary":
        return dict(dataset_config["primary_features"])
    sensitivities = dataset_config.get("sensitivity_feature_sets", {})
    if feature_set not in sensitivities:
        raise ValueError(f"dataset has no feature set {feature_set!r}")
    return dict(sensitivities[feature_set])


def _load_raw_cohort(
    project_root: Path,
    dataset_key: str,
    dataset_config: dict[str, Any],
) -> tuple[pd.DataFrame, np.ndarray]:
    """Read a raw cohort file, check its outcome columns and build subject identifiers.

    When the dataset has no identifier column, subjects are named
    ``<dataset>-<row number>`` with zero padding, which is the rule the
    confirmatory pipeline used when it stored the cells.
    """
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


def load_cohort(source: SourceRun, dataset: str, cache: dict[str, Cohort]) -> Cohort:
    """Return a dataset's cohort, reading the raw file only on first use."""
    if dataset not in cache:
        raw, subject_ids = _load_raw_cohort(
            source.project_root, dataset, source.dataset_configs[dataset]
        )
        cache[dataset] = Cohort(
            raw=raw,
            subject_ids=subject_ids,
            positions={str(subject_id): index for index, subject_id in enumerate(subject_ids)},
        )
    return cache[dataset]


def _subject_id_lists(cell: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Return a cell's training and validation subject identifiers as strings."""
    train_ids = [str(value) for value in cell["train_subject_ids"]]
    validation_ids = [str(value) for value in cell["validation_subject_ids"]]
    return train_ids, validation_ids


def _prediction_ids(cell: dict[str, Any]) -> list[str]:
    """Return the subject order of a cell's stored predictions."""
    return [str(value) for value in cell["predictions"]["subject_ids"]]


def _lineage_record(
    cell: dict[str, Any], train_ids: list[str], validation_ids: list[str]
) -> dict[str, Any]:
    """Return the subject lists and preprocessing hash shared by cells of one fold."""
    return {
        "train_subject_ids": train_ids,
        "validation_subject_ids": validation_ids,
        "training_state_sha256": cell["preprocessing"]["training_state_sha256"],
    }


def verify_cell_lineage(
    cell: dict[str, Any],
    cohort: Cohort,
    fold_lineage: dict[FoldKey, dict[str, Any]],
) -> CellLineage:
    """Check a Bayesian cell's subjects and that it matches other cells of its fold.

    The training and validation subjects must be disjoint and together cover
    the whole cohort, and the stored predictions must follow the validation
    order. The first Bayesian cell seen for an outer fold sets the fold's
    lineage in ``fold_lineage``; every later prior for that fold must match
    it, so all priors are explained on the same subjects and features.
    """
    train_ids, validation_ids = _subject_id_lists(cell)
    if len(train_ids) != int(cell["n_train"]) or len(validation_ids) != int(cell["n_validation"]):
        raise RuntimeError("cell subject counts do not match its ID lists")
    if len(set(train_ids)) != len(train_ids) or len(set(validation_ids)) != len(validation_ids):
        raise RuntimeError("cell contains duplicate subject identifiers")
    if set(train_ids) & set(validation_ids):
        raise RuntimeError("cell training and validation subjects overlap")
    if set(train_ids) | set(validation_ids) != set(cohort.subject_ids):
        raise RuntimeError("cell subject IDs do not partition the frozen cohort")
    if _prediction_ids(cell) != validation_ids:
        raise RuntimeError("cell prediction order differs from validation ID order")

    key = fold_key(cell)
    record = _lineage_record(cell, train_ids, validation_ids)
    prior_record = fold_lineage.setdefault(key, record)
    if prior_record != record:
        raise RuntimeError("paired Bayesian cells do not share subjects and preprocessing state")
    return CellLineage(
        fold_key=key, train_ids=train_ids, validation_ids=validation_ids, record=record
    )


def cox_unavailable_reason(cox_entry: StoredCell | None) -> str | None:
    """Return why a fold has no usable Cox partner, or ``None`` if it has one."""
    if cox_entry is None:
        return "no frozen Cox cell exists for the paired outer fold"
    status = cox_entry[1].get("status")
    if status != "complete":
        return f"paired frozen Cox cell is not complete: {status}"
    return None


def _coefficient_vector(coefficient_summary: Any, feature_names: list[str]) -> np.ndarray:
    """Read Cox coefficients from a stored summary table in the given feature order."""
    if not isinstance(coefficient_summary, list):
        raise ValueError("Cox cell has no coefficient-summary table")
    table = pd.DataFrame(coefficient_summary)
    if not {"feature", "coef"}.issubset(table.columns):
        raise ValueError("Cox coefficient summary is missing feature or coef")
    if table["feature"].duplicated().any() or set(table["feature"]) != set(feature_names):
        raise ValueError("Cox coefficients do not match preprocessing features")
    coefficients = (
        table.set_index("feature")["coef"].astype(float).reindex(feature_names).to_numpy()
    )
    if not np.isfinite(coefficients).all():
        raise ValueError("Cox coefficients must be finite")
    return coefficients


def pair_cox_cell(
    source: SourceRun,
    cox_entry: StoredCell,
    *,
    raw_hash: str,
    lineage: CellLineage,
    feature_spec: dict[str, Any],
    processor: FoldFeaturePreprocessor,
) -> PairedCox:
    """Check that a complete Cox cell matches a Bayesian cell and read its coefficients.

    The Cox cell must use the same raw data, subjects, prediction order and
    preprocessing state as the Bayesian cell, so that both linear risk scores
    are explained on identical inputs.

    Args:
        source: The verified run.
        cox_entry: The complete Cox cell of the same outer fold.
        raw_hash: SHA-256 of the dataset's raw file.
        lineage: The Bayesian cell's lineage.
        feature_spec: Feature specification used to restore preprocessing.
        processor: The Bayesian cell's restored preprocessor.

    Returns:
        The Cox cell with its coefficients in the Bayesian feature order.
    """
    cox_path, cox_cell = cox_entry
    if cox_cell.get("dataset_sha256") != raw_hash:
        raise RuntimeError("paired Cox cell has a different dataset hash")
    cox_train_ids, cox_validation_ids = _subject_id_lists(cox_cell)
    if _lineage_record(cox_cell, cox_train_ids, cox_validation_ids) != lineage.record:
        raise RuntimeError("paired Cox and Bayesian cells do not share subjects and preprocessing")
    if _prediction_ids(cox_cell) != lineage.validation_ids:
        raise RuntimeError("Cox prediction order differs from paired validation IDs")
    cox_processor = FoldFeaturePreprocessor.from_metadata(feature_spec, cox_cell["preprocessing"])
    if cox_processor.training_state_sha256 != processor.training_state_sha256:
        raise RuntimeError("Cox and Bayesian preprocessing hashes differ")
    coefficients = _coefficient_vector(
        cox_cell["model_details"].get("coefficient_summary"), list(processor.feature_names)
    )
    return PairedCox(
        relative_path=source.relative(cox_path), cell=cox_cell, coefficients=coefficients
    )
