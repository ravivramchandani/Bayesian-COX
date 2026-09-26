"""Load immutable cell records and rebuild the fold metrics and out-of-fold prediction tables."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.data.survival_folds import SurvivalFold
from src.utils.reproducibility import canonical_json_hash


def _cell_path(run_dir: Path, dataset: str, fold: SurvivalFold, model: str) -> Path:
    """Return the immutable checkpoint path for one model and outer fold."""
    return (
        run_dir
        / "cells"
        / dataset
        / f"repeat_{fold.repeat:02d}_fold_{fold.fold:02d}"
        / f"{model}.json"
    )


def _load_cells(run_dir: Path) -> list[dict[str, Any]]:
    """Read cells in path order and reject any invalid content hash."""
    cells = []
    for path in sorted((run_dir / "cells").glob("*/*/*.json")):
        with path.open(encoding="utf-8") as handle:
            cell = json.load(handle)
        claimed_hash = cell.get("cell_content_sha256")
        unhashed = dict(cell)
        unhashed.pop("cell_content_sha256", None)
        observed_hash = canonical_json_hash(unhashed)
        if claimed_hash != observed_hash:
            raise RuntimeError(f"cell content hash does not match: {path}")
        cells.append(cell)
    return cells


def _aggregate_tables(run_dir: Path, cells: list[dict[str, Any]]) -> None:
    """Write metric and subject-prediction tables using accepted cells only."""
    metrics_rows: list[dict[str, Any]] = []
    prediction_rows: list[dict[str, Any]] = []
    for cell in cells:
        if cell.get("status") != "complete":
            continue
        metrics = cell["metrics"]
        row = {
            "dataset": cell["dataset"],
            "model": cell["model"],
            "model_key": cell["model_key"],
            "repeat": cell["repeat"],
            "fold": cell["fold"],
            "n_train": cell["n_train"],
            "n_validation": cell["n_validation"],
            "events_train": cell["events_train"],
            "events_validation": cell["events_validation"],
            "harrell_c_index": metrics["harrell_c_index"],
            "uno_c_index": metrics["uno_c_index"],
            "ibs": metrics["ibs"],
            "mean_auc": metrics["mean_auc"],
            "total_seconds": cell["total_seconds"],
            "cell_content_sha256": cell["cell_content_sha256"],
        }
        for index, (horizon, auc) in enumerate(
            zip(metrics["horizons"], metrics["auc_at_horizons"], strict=True),
            start=1,
        ):
            row[f"horizon_{index}"] = horizon
            row[f"auc_{index}"] = auc
            summary = metrics["calibration"][index - 1]["summary"]
            row[f"calibration_intercept_{index}"] = summary["intercept"]["estimate"]
            row[f"calibration_slope_{index}"] = summary["slope"]["estimate"]
            row[f"calibration_large_{index}"] = summary["calibration_in_the_large"]["estimate"]
        metrics_rows.append(row)

        predictions = cell["predictions"]
        for index, subject_id in enumerate(predictions["subject_ids"]):
            prediction_rows.append(
                {
                    "dataset": cell["dataset"],
                    "model": cell["model"],
                    "model_key": cell["model_key"],
                    "repeat": cell["repeat"],
                    "fold": cell["fold"],
                    "subject_id": subject_id,
                    "observed_time": predictions["observed_time"][index],
                    "observed_event": predictions["observed_event"][index],
                    "risk": predictions["risk"][index],
                    "horizons_json": json.dumps(predictions["horizons"]),
                    "survival_at_horizons_json": json.dumps(
                        predictions["survival_at_horizons"][index]
                    ),
                    "ibs_grid_json": json.dumps(predictions["ibs_grid"]),
                    "survival_on_ibs_grid_json": json.dumps(
                        predictions["survival_on_ibs_grid"][index]
                    ),
                }
            )
    pd.DataFrame(metrics_rows).to_csv(run_dir / "fold_metrics.csv", index=False)
    pd.DataFrame(prediction_rows).to_csv(
        run_dir / "out_of_fold_predictions.csv.gz",
        index=False,
        compression={"method": "gzip", "compresslevel": 9, "mtime": 0},
    )
