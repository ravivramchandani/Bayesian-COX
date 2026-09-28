"""Create the content-addressed confirmatory protocol freeze after rehearsal.

The freeze is the step between the result-blind rehearsal and the
confirmatory run (ADR-022, ADR-029). It records the SHA-256 digest of every
code, configuration, protocol, lock, manifest and data input the confirmatory
run executes. The confirmatory runner then refuses to fit if any input differs
from its frozen digest.

Before writing, the script checks that the rehearsal is exactly the 18-cell
result-blind workload (three cohorts by six models, one outer fold, the
rehearsal sampler settings), that every cell completed, that every file matches
the rehearsal's own hash records, and that no input has changed since the
rehearsal. It then applies the compute gate: the approved five repeats may be
reduced to three only when a deliberately conservative five-repeat runtime
projection exceeds ``maximum_projected_hours`` in ``config/confirmatory.yaml``.
The ``--repeat-decision`` flag must equal both the gate's answer and
``validation.outer_repeats``. Only cell status and runtime are read; no
prediction result is used.

Reads:
    ``config/confirmatory.yaml``, the rehearsal run directory and every frozen
    input.

Writes:
    ``config/protocol_freeze.json``, created once. The file already exists in
    this repository, so a rerun fails rather than overwrite it.

Example:
    python scripts/freeze_protocol.py \
        --rehearsal-dir reports/confirmatory/<rehearsal run> --repeat-decision 5 \
        --acknowledge-no-effects-inspected
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.pipelines.confirmatory import MODEL_KEYS, relevant_input_files
from src.utils.reproducibility import canonical_json_hash, sha256_file


def _verify_content_hash(record: dict, field: str, *, label: str) -> None:
    """Check that ``record[field]`` is the canonical hash of the rest of ``record``.

    Raises:
        ValueError: If the stored hash does not match, naming ``label``.
    """
    claimed = record.get(field)
    unhashed = dict(record)
    unhashed.pop(field, None)
    if claimed != canonical_json_hash(unhashed):
        raise ValueError(f"{label} content hash is invalid")


def required_repeat_decision(
    *,
    planned_five_repeat_hours: float,
    maximum_hours: float,
    planned_repeats: int = 5,
    reduced_repeats: int = 3,
) -> int:
    """Apply the result-blind compute gate to the planned five-repeat design.

    The projection is deliberately independent of the requested repeat count.
    This prevents the circular case where choosing three repeats changes the
    projection used to decide whether three repeats are permitted.

    Args:
        planned_five_repeat_hours: Conservative projected runtime of the full
            planned design, in hours.
        maximum_hours: Largest acceptable projected runtime, in hours.
        planned_repeats: Approved number of outer repeats.
        reduced_repeats: Number of repeats permitted when the gate fails.

    Returns:
        ``reduced_repeats`` if the projection exceeds ``maximum_hours``,
        otherwise ``planned_repeats``.

    Raises:
        ValueError: If a repeat count is not positive, the reduction is not
            smaller than the plan, the projection is negative or the cap is not
            positive.
    """
    if planned_repeats <= 0 or reduced_repeats <= 0:
        raise ValueError("repeat counts must be positive")
    if reduced_repeats >= planned_repeats:
        raise ValueError("the permitted reduction must be smaller than the plan")
    if planned_five_repeat_hours < 0 or maximum_hours <= 0:
        raise ValueError("runtime projections must be non-negative and the cap positive")
    return (
        reduced_repeats
        if planned_five_repeat_hours > maximum_hours
        else planned_repeats
    )


def write_protocol_freeze_once(output: Path, freeze: dict) -> None:
    """Create the protocol freeze exactly once and refuse any overwrite.

    The file is opened in exclusive-creation mode, so an existing freeze is
    never replaced, even by a concurrent writer.

    Args:
        output: New freeze file path; its parent must already exist.
        freeze: Verified freeze record to write as finite JSON.

    Raises:
        FileExistsError: If ``output`` already exists.
    """
    try:
        with output.open("x", encoding="utf-8") as handle:
            json.dump(freeze, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
    except FileExistsError as exc:
        raise FileExistsError(
            f"protocol freeze already exists and is immutable: {output}"
        ) from exc


def expected_rehearsal_controls(config: dict) -> dict[str, object]:
    """Return the exact result-blind workload accepted by the runtime gate.

    These are the settings ``scripts/run_confirmatory.py`` applies in rehearsal
    mode when no override flag is given; the rehearsal manifest's
    ``run_config`` must match them key by key.

    Args:
        config: Confirmatory configuration supplying cohorts and outer-fold settings.

    Returns:
        The exact default rehearsal workload to compare with its manifest.
    """
    return {
        "mode": "rehearsal",
        "datasets": list(config["datasets"]),
        "models": list(MODEL_KEYS),
        "outer_splits": int(config["validation"]["outer_splits"]),
        "outer_repeats": 1,
        "fold_limit_per_dataset": 1,
        "bayes_draws": 300,
        "bayes_tune": 300,
        "bayes_chains": 2,
        "calibration_bootstraps": 30,
    }


def parse_args() -> argparse.Namespace:
    """Parse the command line.

    Returns:
        Parsed command-line option namespace.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--rehearsal-dir", required=True, type=Path)
    parser.add_argument("--repeat-decision", required=True, type=int, choices=(3, 5))
    parser.add_argument(
        "--acknowledge-no-effects-inspected",
        action="store_true",
        help="Required attestation that only status and runtime were read.",
    )
    return parser.parse_args()


def main() -> int:
    """Verify the rehearsal, apply the compute gate and write the freeze once.

    Returns:
        Exit status 0 once the freeze is written.

    Raises:
        RuntimeError: If the attestation flag is missing, the configuration is
            not marked ``frozen_after_rehearsal``, the repeat decision disagrees
            with the configuration or the gate, or an input changed after the
            rehearsal.
        FileNotFoundError: If the rehearsal manifest or completion is missing.
        ValueError: If the rehearsal's content, cells or settings do not match
            the expected result-blind workload.
        FileExistsError: If the freeze already exists.
    """
    args = parse_args()
    if not args.acknowledge_no_effects_inspected:
        raise RuntimeError("result-blind rehearsal attestation is required")

    config_path = PROJECT_ROOT / "config" / "confirmatory.yaml"
    with config_path.open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if config["design_status"] != "frozen_after_rehearsal":
        raise RuntimeError(
            "set design_status to frozen_after_rehearsal only after the rehearsal passes"
        )
    if int(config["validation"]["outer_repeats"]) != args.repeat_decision:
        raise RuntimeError("repeat decision does not match confirmatory.yaml")

    rehearsal_dir = args.rehearsal_dir.resolve()
    completion_path = rehearsal_dir / "completion.json"
    manifest_path = rehearsal_dir / "manifest.json"
    if not completion_path.is_file() or not manifest_path.is_file():
        raise FileNotFoundError("rehearsal directory lacks manifest/completion evidence")
    completion = json.loads(completion_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _verify_content_hash(
        completion, "completion_content_sha256", label="rehearsal completion"
    )
    _verify_content_hash(
        manifest, "manifest_content_sha256", label="rehearsal manifest"
    )
    expected_cells = len(config["datasets"]) * len(MODEL_KEYS)
    if completion.get("analysis_mode") != "rehearsal":
        raise ValueError("the supplied run is not labelled rehearsal")
    if completion.get("stored_cells") != expected_cells:
        raise ValueError(
            f"rehearsal must contain {expected_cells} cells, found "
            f"{completion.get('stored_cells')}"
        )
    if completion.get("planned_cells_in_this_invocation") != expected_cells:
        raise ValueError(
            "rehearsal completion does not record the exact planned 18-cell grid"
        )
    if completion.get("status_counts") != {"complete": expected_cells}:
        raise ValueError("every rehearsal cell must complete before protocol freeze")

    actual = manifest.get("run_config", {})
    expected_controls = expected_rehearsal_controls(config)
    mismatched_controls = [
        key
        for key, expected in expected_controls.items()
        if actual.get(key) != expected
    ]
    if mismatched_controls:
        raise ValueError(
            "rehearsal controls do not match the result-blind gate: "
            + ", ".join(mismatched_controls)
        )

    cell_hashes = {
        str(path.relative_to(rehearsal_dir)): sha256_file(path)
        for path in sorted((rehearsal_dir / "cells").glob("*/*/*.json"))
    }
    if cell_hashes != completion.get("all_stored_cell_hashes"):
        raise ValueError("rehearsal cell files differ from the completion manifest")
    expected_cell_paths = {
        f"cells/{dataset}/repeat_01_fold_01/{model}.json"
        for dataset in config["datasets"]
        for model in MODEL_KEYS
    }
    if set(cell_hashes) != expected_cell_paths:
        raise ValueError("rehearsal cell paths do not match the exact cohort/model grid")

    # Each cell must carry the dataset and model its path names, so that a
    # renamed or copied file cannot stand in for a missing cell.
    cell_records: list[dict[str, object]] = []
    seen_keys: set[tuple[str, str]] = set()
    for relative in sorted(cell_hashes):
        cell_path = rehearsal_dir / relative
        cell = json.loads(cell_path.read_text(encoding="utf-8"))
        _verify_content_hash(cell, "cell_content_sha256", label=relative)
        key = (str(cell.get("dataset")), str(cell.get("model_key")))
        if key in seen_keys:
            raise ValueError(f"duplicate rehearsal cell key: {key}")
        seen_keys.add(key)
        expected_relative = (
            f"cells/{key[0]}/repeat_01_fold_01/{key[1]}.json"
        )
        if relative != expected_relative:
            raise ValueError(f"rehearsal cell identity disagrees with its path: {relative}")
        if (
            cell.get("analysis_mode") != "rehearsal"
            or cell.get("evidence_status") != "rehearsal_only"
            or cell.get("status") != "complete"
            or cell.get("repeat") != 1
            or cell.get("fold") != 1
        ):
            raise ValueError(f"invalid rehearsal cell state: {relative}")
        total_seconds = float(cell.get("total_seconds", float("nan")))
        if not math.isfinite(total_seconds) or total_seconds < 0:
            raise ValueError(f"invalid rehearsal runtime: {relative}")
        cell_records.append(cell)
    aggregate_hashes = {
        name: sha256_file(rehearsal_dir / name)
        for name in ("fold_metrics.csv", "out_of_fold_predictions.csv.gz", "inference.json")
    }
    if aggregate_hashes != completion.get("aggregate_sha256"):
        raise ValueError("rehearsal aggregate files differ from the completion manifest")

    # The freeze records the live inputs, so they must be byte-identical to the
    # inputs the rehearsal ran with.
    inputs = relevant_input_files(PROJECT_ROOT, tuple(config["datasets"]))
    current_input_hashes = {
        relative: sha256_file(PROJECT_ROOT / relative)
        if (PROJECT_ROOT / relative).is_file()
        else "MISSING"
        for relative in inputs
    }
    if manifest.get("input_sha256") != current_input_hashes:
        changed = sorted(
            name
            for name in set(manifest.get("input_sha256", {})) | set(current_input_hashes)
            if manifest.get("input_sha256", {}).get(name)
            != current_input_hashes.get(name)
        )
        raise RuntimeError(
            "methodological inputs changed after the rehearsal: " + ", ".join(changed)
        )

    timings: list[dict[str, object]] = [
        {
            "dataset": cell["dataset"],
            "model_key": cell["model_key"],
            "status": cell["status"],
            "total_seconds": cell["total_seconds"],
        }
        for cell in cell_records
    ]
    observed_seconds = float(sum(float(row["total_seconds"]) for row in timings))
    # This intentionally overestimates: it scales every operation by the
    # larger of the MCMC-iteration and calibration-bootstrap ratios, then by
    # the number of outer folds. It uses no comparative prediction result.
    mcmc_ratio = (
        (int(config["models"]["bayesian_cox"]["draws"]) + int(config["models"]["bayesian_cox"]["tune"]))
        * int(config["models"]["bayesian_cox"]["chains"])
        / (
            (int(actual["bayes_draws"]) + int(actual["bayes_tune"]))
            * int(actual["bayes_chains"])
        )
    )
    bootstrap_ratio = int(config["evaluation"]["calibration_bootstraps"]) / int(
        actual["calibration_bootstraps"]
    )
    conservative_scale = max(1.0, mcmc_ratio, bootstrap_ratio)
    projected_seconds_per_repeat = (
        observed_seconds
        * conservative_scale
        * int(config["validation"]["outer_splits"])
    )
    planned_repeats = 5
    planned_projected_hours = (
        projected_seconds_per_repeat * planned_repeats / 3600.0
    )
    selected_projected_hours = (
        projected_seconds_per_repeat * args.repeat_decision / 3600.0
    )
    maximum_hours = float(config["validation"]["maximum_projected_hours"])
    reduced_repeats = int(config["validation"]["permitted_reduction_repeats"])
    required_repeats = required_repeat_decision(
        planned_five_repeat_hours=planned_projected_hours,
        maximum_hours=maximum_hours,
        planned_repeats=planned_repeats,
        reduced_repeats=reduced_repeats,
    )
    if args.repeat_decision != required_repeats:
        if planned_projected_hours > maximum_hours:
            raise RuntimeError(
                "conservative projection exceeds the compute gate; use the permitted "
                f"{reduced_repeats}-repeat reduction before freezing"
            )
        raise RuntimeError(
            "conservative projection is within the compute gate; the approved "
            f"{planned_repeats}-repeat design must be retained"
        )

    frozen_hashes = current_input_hashes
    freeze = {
        "schema_version": "1.0.0",
        "analysis_id": config["analysis_id"],
        "frozen_at_utc": datetime.now(UTC).isoformat(),
        "outer_repeats": args.repeat_decision,
        "result_blind_runtime_gate": {
            "rehearsal_manifest_sha256": sha256_file(manifest_path),
            "rehearsal_completion_sha256": sha256_file(completion_path),
            "observed_rehearsal_seconds": observed_seconds,
            "conservative_scale": conservative_scale,
            "planned_five_repeat_projected_hours": planned_projected_hours,
            "selected_projected_hours": selected_projected_hours,
            "maximum_hours": maximum_hours,
            "cell_timings": timings,
        },
        "no_comparative_effects_inspected_before_freeze": True,
        "frozen_input_sha256": frozen_hashes,
    }
    freeze["freeze_content_sha256"] = canonical_json_hash(freeze)
    output = PROJECT_ROOT / "config" / "protocol_freeze.json"
    write_protocol_freeze_once(output, freeze)
    print(f"wrote {output}")
    print(f"planned_five_repeat_projected_hours={planned_projected_hours:.2f}")
    print(f"selected_projected_hours={selected_projected_hours:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
