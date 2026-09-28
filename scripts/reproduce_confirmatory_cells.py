"""Refit stored confirmatory cells with the current code and compare them.

A cell is one (dataset, model, repeat, fold) fit from the frozen confirmatory
run. This script refits the selected cells with the code in the working tree,
using the protocol and data recorded in the run's manifest, and checks that
every stored field is reproduced exactly.

Only wall-clock fields differ between two executions of the same cell:
``total_seconds``, each attempt's ``fit_seconds`` and ``cell_content_sha256``
(which is computed over those timings). They are excluded from the check.

This is the behaviour-preservation check of ADR-030: a code change is
accepted only if it regenerates the frozen cells, and the full 450-cell run is
also the result reproduction required by ADR-026. It is a verification
output, not a new analysis, and it never writes into the source run (INV-008).

Before any fit, the script verifies the source run and the frozen study inputs,
requires the live protocol and the installed dependency versions to match the
run's manifest, and records the hashes of every ``src`` module and of this
script. It checks those hashes and the source evidence again after the last
fit, so an edit made during a long reproduction is detected.

Reads:
    The completed confirmatory run (``--run-dir``, by default the frozen
    ``confirmatory_v1_confirmatory_cdcdcee84651``) and the raw cohorts.

Writes:
    A JSON report, by default ``reports/reproduction/cells_<timestamp>.json``.
    With ``--keep-cells DIR``, also each refitted cell and a
    ``reproduction_checkpoint.json`` recording the code, environment, source
    evidence and selection. ``--resume`` reuses the refits saved in ``DIR``
    only when that checkpoint matches exactly and each saved cell passes its
    own content hash.

The exit status is 0 when every selected cell is identical and 1 otherwise.
Make target: ``reproduce-confirmatory`` (needs ``CONFIRMATORY_RUN``).

Examples::

    # Six quick cells: every model on GBSG2 repeat 1 fold 1.
    python scripts/reproduce_confirmatory_cells.py --selection quick

    # Every stored cell, four processes, with the refitted cells kept.
    python scripts/reproduce_confirmatory_cells.py --selection all --workers 4 \
        --keep-cells reports/reproduction/cells
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_RUN = PROJECT_ROOT / "reports/confirmatory/confirmatory_v1_confirmatory_cdcdcee84651"
CHECKPOINT_COMMIT = "44b6085"
# Keys skipped wherever they occur in a cell when comparing refit and original.
TIMING_FIELDS = {"total_seconds", "fit_seconds", "cell_content_sha256"}


def parse_args() -> argparse.Namespace:
    """Parse the command line.

    Returns:
        Parsed command-line option namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    parser.add_argument(
        "--selection",
        default="quick",
        help="'quick', 'all', or comma-separated dataset:model:repeat:fold keys",
    )
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument(
        "--resume", action="store_true", help="reuse verified refits from --keep-cells"
    )
    parser.add_argument(
        "--keep-cells",
        type=Path,
        default=None,
        help="directory in which to save each refitted cell as JSON",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="JSON report path; defaults to reports/reproduction/<timestamp>.json",
    )
    return parser.parse_args()


def load_run_inputs(run_dir: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Return the run manifest, frozen protocol and dataset configuration.

    The protocol is read from the manifest, so later edits to
    ``config/confirmatory.yaml`` cannot change what is reproduced. The
    dataset configuration is read from the working tree when its hash matches
    the manifest, otherwise from the checkpoint commit.

    Args:
        run_dir: Stored run whose manifest supplies the protocol and dataset hash.

    Returns:
        Manifest, recorded protocol and hash-matched dataset configuration.
    """
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    protocol = manifest["run_config"]["protocol"]
    recorded = manifest["input_sha256"]["config/datasets.yaml"]
    live = PROJECT_ROOT / "config/datasets.yaml"
    text = live.read_bytes()
    if hashlib.sha256(text).hexdigest() != recorded:
        text = subprocess.run(
            ["git", "show", f"{CHECKPOINT_COMMIT}:config/datasets.yaml"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
        ).stdout
        if hashlib.sha256(text).hexdigest() != recorded:
            raise RuntimeError("no copy of config/datasets.yaml matches the run manifest")
    return manifest, protocol, yaml.safe_load(text)


def select_cells(run_dir: Path, selection: str) -> list[tuple[str, str, int, int]]:
    """Translate a selection string into (dataset, model, repeat, fold) keys.

    Args:
        run_dir: Source run whose manifest and stored cells define the choices.
        selection: ``"quick"`` for every model of the run on GBSG2 repeat 1
            fold 1; ``"all"`` for every stored cell; otherwise comma-separated
            ``dataset:model:repeat:fold`` keys.

    Returns:
        The selected keys; repeat and fold numbers start at 1.
    """
    if selection == "quick":
        models = json.loads((run_dir / "manifest.json").read_text())["run_config"]["models"]
        return [("gbsg2", model, 1, 1) for model in models]
    if selection == "all":
        keys = []
        for path in sorted((run_dir / "cells").glob("*/repeat_*_fold_*/*.json")):
            repeat, fold = path.parent.name.split("_")[1::2]
            keys.append((path.parent.parent.name, path.stem, int(repeat), int(fold)))
        return keys
    keys = []
    for item in selection.split(","):
        dataset, model, repeat, fold = item.split(":")
        keys.append((dataset, model, int(repeat), int(fold)))
    return keys


def stored_cell_path(run_dir: Path, dataset: str, model: str, repeat: int, fold: int) -> Path:
    """Locate an original cell inside the source run.

    Args:
        run_dir: Original confirmatory run directory.
        dataset: Cohort key.
        model: Stored model key.
        repeat: Outer repeat number, starting at one.
        fold: Outer fold number, starting at one.

    Returns:
        Expected cell path; existence is checked by the caller.
    """
    return run_dir / "cells" / dataset / f"repeat_{repeat:02d}_fold_{fold:02d}" / f"{model}.json"


def saved_refit_path(keep: Path, dataset: str, model: str, repeat: int, fold: int) -> Path:
    """Locate a refit under the directory passed as --keep-cells.

    Args:
        keep: External refit directory passed as --keep-cells.
        dataset: Cohort key.
        model: Stored model key.
        repeat: Outer repeat number, starting at one.
        fold: Outer fold number, starting at one.

    Returns:
        Expected regenerated-cell path; no file is created here.
    """
    return keep / dataset / f"repeat_{repeat:02d}_fold_{fold:02d}" / f"{model}.json"


def differences(new: Any, old: Any, path: str = "") -> list[str]:
    """List every leaf where two JSON values differ, ignoring timing fields.

    Args:
        new: The refitted value.
        old: The stored value.
        path: Location of the values within the cell, used in messages.

    Returns:
        One message per differing leaf, key present on only one side, or list
        length mismatch. An empty list means the values agree.
    """
    if isinstance(new, dict) and isinstance(old, dict):
        found = []
        for key in sorted(set(new) | set(old)):
            if key in TIMING_FIELDS:
                continue
            if key not in new or key not in old:
                found.append(f"{path}.{key}: present in only one cell")
            else:
                found += differences(new[key], old[key], f"{path}.{key}")
        return found
    if isinstance(new, list) and isinstance(old, list):
        if len(new) != len(old):
            return [f"{path}: length {len(new)} != {len(old)}"]
        found = []
        for index, (left, right) in enumerate(zip(new, old, strict=True)):
            found += differences(left, right, f"{path}[{index}]")
        return found
    return [] if new == old else [f"{path}: {str(new)[:80]} != {str(old)[:80]}"]


def refit_cell(run_dir: Path, key: tuple[str, str, int, int]) -> dict[str, Any]:
    """Refit one cell with the current code and return it as stored JSON.

    The run settings, protocol and dataset configuration come from the run's
    manifest, and the outer fold is regenerated from the frozen base seed, so
    only the code can differ from the original fit.

    Args:
        run_dir: Immutable confirmatory source run.
        key: Dataset, model, outer repeat and outer fold to regenerate.

    Raises:
        RuntimeError: If the cohort's raw file differs from the manifest.

    Returns:
        Regenerated cell with the same JSON-compatible value types as stored evidence.
    """
    import src.pipelines.confirmatory as confirmatory
    from src.data.survival_folds import repeated_survival_folds
    from src.utils.reproducibility import sha256_file

    dataset, model, repeat, fold_number = key
    manifest, protocol, dataset_config = load_run_inputs(run_dir)
    settings = manifest["run_config"]
    options = confirmatory.RunOptions(
        mode=settings["mode"],
        datasets=tuple(settings["datasets"]),
        models=tuple(settings["models"]),
        outer_splits=settings["outer_splits"],
        outer_repeats=settings["outer_repeats"],
        fold_limit_per_dataset=settings["fold_limit_per_dataset"],
        bayes_draws=settings["bayes_draws"],
        bayes_tune=settings["bayes_tune"],
        bayes_chains=settings["bayes_chains"],
        calibration_bootstraps=settings["calibration_bootstraps"],
        resume=True,
        output_root=run_dir.parent,
    )
    cohort = dataset_config[dataset]
    data_path = PROJECT_ROOT / cohort["raw_file"]
    if sha256_file(data_path) != manifest["input_sha256"][cohort["raw_file"]]:
        raise RuntimeError(f"{cohort['raw_file']} differs from the run manifest")
    raw, times, events, subject_ids = confirmatory.load_analysis_dataset(
        PROJECT_ROOT, dataset, cohort
    )
    folds = repeated_survival_folds(
        times,
        events,
        n_splits=options.outer_splits,
        n_repeats=options.outer_repeats,
        base_seed=int(protocol["validation"]["base_seed"]),
        max_time_bins=int(protocol["validation"]["followup_time_bins"]),
    )
    fold = next(item for item in folds if item.repeat == repeat and item.fold == fold_number)
    cell = confirmatory.run_cell(
        dataset,
        model,
        fold,
        raw,
        times,
        events,
        subject_ids,
        confirmatory._feature_spec(cohort, protocol["feature_set"]),
        config=protocol,
        options=options,
        data_sha256=sha256_file(data_path),
    )
    # Round-trip through JSON so that the refit has exactly the types and key
    # order of a cell read back from disk.
    return json.loads(json.dumps(confirmatory._json_safe(cell), sort_keys=True))


def check_cell(run_dir: Path, key: tuple[str, str, int, int], keep: Path | None) -> dict[str, Any]:
    """Refit one cell, compare it with the stored cell and summarise.

    Args:
        run_dir: Source run.
        key: The cell's (dataset, model, repeat, fold).
        keep: Directory in which to save the refit, or ``None``.

    Returns:
        A summary with the cell key, its status, whether it is identical, the
        number of differences, the first ten differences and the refit time
        in seconds.
    """
    started = time.perf_counter()
    new = refit_cell(run_dir, key)
    old = json.loads(stored_cell_path(run_dir, *key).read_text(encoding="utf-8"))
    found = differences(new, old)
    if keep is not None:
        from src.utils.io import write_json_atomic

        target = saved_refit_path(keep, *key)
        write_json_atomic(target, new, overwrite=False)
    return {
        "cell": ":".join(map(str, key)),
        "status": new["status"],
        "identical": not found,
        "n_differences": len(found),
        "first_differences": found[:10],
        "seconds": round(time.perf_counter() - started, 1),
    }


def main() -> int:
    """Refit and compare the selected cells, then write the report.

    Returns:
        0 if every selected cell is identical, otherwise 1.

    Raises:
        ValueError: If ``--workers`` is below 1, ``--resume`` lacks
            ``--keep-cells``, or an output path lies inside the source run.
    """
    args = parse_args()
    run_dir = args.run_dir.resolve()
    keys = select_cells(run_dir, args.selection)
    keep = args.keep_cells.resolve() if args.keep_cells else None
    report_path = args.report.resolve() if args.report else None
    if args.workers < 1:
        raise ValueError("workers must be positive")
    if args.resume and keep is None:
        raise ValueError("--resume requires --keep-cells")
    if keep is not None and (keep == run_dir or run_dir in keep.parents):
        raise ValueError("reproduction output must be outside the immutable source run")
    if report_path is not None and (report_path == run_dir or run_dir in report_path.parents):
        raise ValueError("reproduction report must be outside the immutable source run")
    checkpoint = prepare_reproduction_checkpoint(run_dir, keys, keep, resume=args.resume)
    results = []
    pending = []
    for key in keys:
        target = saved_refit_path(keep, *key) if keep is not None else None
        if args.resume and target is not None and target.exists():
            results.append(check_saved_refit(run_dir, target, key))
        else:
            pending.append(key)
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(check_cell, run_dir, key, keep): key for key in pending}
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(
                f"{result['cell']:<40} identical={result['identical']} "
                f"status={result['status']} seconds={result['seconds']}",
                flush=True,
            )
    verify_reproduction_inputs(checkpoint, run_dir)
    results.sort(key=lambda item: item["cell"])
    report = {
        "analysis": "confirmatory_refit_reproduction",
        "evidence_status": "verification_only",
        "run": run_dir.name,
        "selection": args.selection,
        "cells_checked": len(results),
        "cells_identical": sum(item["identical"] for item in results),
        "ignored_fields": sorted(TIMING_FIELDS),
        "cells": results,
        "provenance": checkpoint,
    }
    path = report_path or (
        PROJECT_ROOT / "reports/reproduction" / f"cells_{time.strftime('%Y%m%dT%H%M%S')}.json"
    )
    from src.utils.io import write_json_atomic
    from src.utils.reproducibility import canonical_json_hash

    report["report_content_sha256"] = canonical_json_hash(report)
    write_json_atomic(path, report, overwrite=False)
    print(f"{report['cells_identical']}/{report['cells_checked']} cells identical; report={path}")
    return 0 if report["cells_identical"] == report["cells_checked"] else 1


def prepare_reproduction_checkpoint(
    run_dir: Path,
    keys: list[tuple[str, str, int, int]],
    keep: Path | None,
    *,
    resume: bool,
) -> dict[str, Any]:
    """Record actual code identity before fitting and validate resumable outputs.

    Args:
        run_dir: Completed confirmatory source run.
        keys: Selected cell keys; they must be unique and all stored in the run.
        keep: Refit directory, or ``None`` when refits are not saved.
        resume: Whether saved refits in ``keep`` may be reused.

    Returns:
        The checkpoint record: environment, source manifest and completion
        hashes, the run's source-file hashes, the planned keys and the hash of
        every ``src`` module and this script.

    Raises:
        ValueError: If the source is not a completed confirmatory run or the
            selection is empty, repeated or outside the run.
        RuntimeError: If the protocol, dependency versions or Python version
            differ from the source run, or a resumed checkpoint differs from
            the current record.
        FileExistsError: If a checkpoint exists without ``resume``, or a new
            ``keep`` directory is not empty.
    """
    from src.rendering.verification import verify_frozen_run
    from src.utils.frozen_evidence import verify_frozen_evidence
    from src.utils.reproducibility import dependency_versions, sha256_file

    source = verify_frozen_run(run_dir)
    if source.mode != "confirmatory":
        raise ValueError("reproduction requires a completed confirmatory source")
    if not keys or len(keys) != len(set(keys)):
        raise ValueError("reproduction selection must contain unique cell keys")
    if any(not stored_cell_path(run_dir, *key).is_file() for key in keys):
        raise ValueError("reproduction selection includes a cell outside the source inventory")
    manifest = source.manifest
    verify_frozen_evidence(PROJECT_ROOT, manifest["input_sha256"])
    from src.utils.io import read_mapping

    if manifest["run_config"]["protocol"] != read_mapping(
        PROJECT_ROOT / "config/confirmatory.yaml"
    ):
        raise RuntimeError("reproduction source protocol differs from the frozen study")
    environment = {"python": platform.python_version(), "dependencies": dependency_versions()}
    original_environment = manifest["environment"]
    if environment["dependencies"] != original_environment["dependencies"] or (
        original_environment.get("python") is not None
        and environment["python"] != original_environment["python"]
    ):
        raise RuntimeError("reproduction runtime differs from the frozen source environment")
    files = sorted(PROJECT_ROOT.glob("src/**/*.py")) + [Path(__file__).resolve()]
    record = {
        "environment": environment,
        "source_manifest_sha256": sha256_file(run_dir / "manifest.json"),
        "source_completion_sha256": sha256_file(run_dir / "completion.json"),
        "source_file_sha256": source.source_hashes,
        "planned_keys": [list(key) for key in keys],
        "actual_code_sha256": {
            str(path.relative_to(PROJECT_ROOT)): sha256_file(path) for path in files
        },
    }
    if keep is not None:
        checkpoint_path = keep / "reproduction_checkpoint.json"
        if checkpoint_path.exists():
            if not resume:
                raise FileExistsError(f"reproduction checkpoint exists: {keep}; use --resume")
            if json.loads(checkpoint_path.read_text()) != record:
                raise RuntimeError("reproduction code, source evidence or selection changed")
        else:
            if resume:
                raise RuntimeError("reproduction resume requires its original checkpoint manifest")
            if keep.exists() and any(keep.iterdir()):
                raise FileExistsError("new reproduction output directory must be empty")
            keep.mkdir(parents=True, exist_ok=True)
            from src.utils.io import write_json_atomic

            write_json_atomic(checkpoint_path, record, overwrite=False)
    return record


def verify_reproduction_inputs(checkpoint: dict[str, Any], run_dir: Path) -> None:
    """Reject source edits made while an otherwise valid refit was running.

    Args:
        checkpoint: Code and source hashes captured before refitting.
        run_dir: Immutable original run whose recorded file hashes are checked again.
    """
    from src.utils.frozen_evidence import verify_frozen_evidence
    from src.utils.reproducibility import sha256_file

    actual_paths = sorted(PROJECT_ROOT.glob("src/**/*.py")) + [Path(__file__).resolve()]
    current = {str(path.relative_to(PROJECT_ROOT)): sha256_file(path) for path in actual_paths}
    if current != checkpoint["actual_code_sha256"]:
        raise RuntimeError("reproduction source code changed during execution")
    for relative, digest in checkpoint["source_file_sha256"].items():
        if sha256_file(run_dir / relative) != digest:
            raise RuntimeError(f"original evidence changed during reproduction: {relative}")
    manifest = json.loads((run_dir / "manifest.json").read_text())
    verify_frozen_evidence(PROJECT_ROOT, manifest["input_sha256"])


def check_saved_refit(run_dir: Path, path: Path, key: tuple[str, str, int, int]) -> dict[str, Any]:
    """Verify a resumed cell's own hash and compare it with the original cell.

    Args:
        run_dir: Original confirmatory source run.
        path: Saved regenerated cell to verify.
        key: Dataset, model, repeat and fold identifying its original cell.

    Returns:
        A summary in the format of :func:`check_cell`, with zero seconds and
        ``resumed_verified_refit`` set.

    Raises:
        RuntimeError: If the saved cell's content hash is invalid.
    """
    from src.utils.reproducibility import canonical_json_hash

    new = json.loads(path.read_text())
    content = dict(new)
    claimed = content.pop("cell_content_sha256", None)
    if claimed != canonical_json_hash(content):
        raise RuntimeError(f"saved reproduction cell hash is invalid: {path}")
    old = json.loads(stored_cell_path(run_dir, *key).read_text())
    found = differences(new, old)
    return {
        "cell": ":".join(map(str, key)),
        "status": new["status"],
        "identical": not found,
        "n_differences": len(found),
        "first_differences": found[:10],
        "seconds": 0.0,
        "resumed_verified_refit": True,
    }


if __name__ == "__main__":
    raise SystemExit(main())
