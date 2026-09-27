"""Complete the authorised refits, evidence checks and result bundles from pinned code."""

from __future__ import annotations

import argparse
import fcntl
import importlib.util
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TextIO

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.io import write_json_atomic
from src.utils.reproducibility import canonical_json_hash, sha256_file


def acquire_programme_lock(output: Path) -> TextIO:
    """Reject duplicates until the coordinator and its inherited child handles close."""
    handle = (output / "programme.lock").open("a+", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as error:
        handle.close()
        raise RuntimeError("another results coordinator already owns this output") from error
    handle.seek(0)
    handle.truncate()
    handle.write(f"pid={os.getpid()}\n")
    handle.flush()
    return handle


def run_logged(arguments: list[str], log_path: Path, *, lock_fd: int | None = None) -> None:
    """Require a child stage to succeed, preserving its log and any execution lock."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        completed = subprocess.run(
            [sys.executable, *arguments],
            cwd=PROJECT_ROOT,
            stdout=handle,
            stderr=subprocess.STDOUT,
            check=False,
            pass_fds=() if lock_fd is None else (lock_fd,),
        )
    if completed.returncode != 0:
        raise RuntimeError(
            f"stage failed with exit {completed.returncode}: {arguments[0]}; see {log_path}"
        )


def load_reproduction_driver():
    """Load the identical public comparison functions used during fitting."""
    path = PROJECT_ROOT / "scripts/reproduce_confirmatory_cells.py"
    spec = importlib.util.spec_from_file_location("programme_reproduction", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_reproduction(source_dir: Path, cells_dir: Path, report_path: Path) -> dict:
    """Verify all 450 saved refits and their code/source checkpoint independently."""
    driver = load_reproduction_driver()
    keys = driver.select_cells(source_dir, "all")
    checkpoint = driver.prepare_reproduction_checkpoint(source_dir, keys, cells_dir, resume=True)
    if len(keys) != 450:
        raise RuntimeError("full reproduction requires all 450 original cells")
    paths = {str(driver.saved_refit_path(cells_dir, *key).relative_to(cells_dir)) for key in keys}
    actual = {str(path.relative_to(cells_dir)) for path in cells_dir.glob("*/*/*.json")}
    if paths != actual:
        raise RuntimeError("full reproduction saved-refit inventory differs from the original grid")
    results = [
        driver.check_saved_refit(source_dir, driver.saved_refit_path(cells_dir, *key), key)
        for key in keys
    ]
    if not all(row["identical"] for row in results):
        raise RuntimeError("at least one regenerated cell differs beyond timing fields")
    report = json.loads(report_path.read_text())
    content = dict(report)
    claimed = content.pop("report_content_sha256", None)
    if canonical_json_hash(content) != claimed:
        raise RuntimeError("full reproduction report content hash differs")
    if (
        report.get("cells_checked") != 450
        or report.get("cells_identical") != 450
        or report.get("provenance") != checkpoint
    ):
        raise RuntimeError("full reproduction report does not verify the entire original grid")
    if report.get("evidence_status") != "verification_only":
        raise RuntimeError("full reproduction has an incorrect evidence label")
    driver.verify_reproduction_inputs(checkpoint, source_dir)
    return report


def refit_all(source_dir: Path, output: Path, workers: int, *, lock_fd: int | None = None) -> dict:
    """Run or verify the full 450-cell reproduction in its own output directory."""
    cells = output / "reproduction/cells"
    report = output / "reproduction/verification.json"
    if not report.exists():
        arguments = [
            "scripts/reproduce_confirmatory_cells.py",
            "--run-dir",
            str(source_dir),
            "--selection",
            "all",
            "--workers",
            str(workers),
            "--keep-cells",
            str(cells),
            "--report",
            str(report),
        ]
        if (cells / "reproduction_checkpoint.json").exists():
            arguments.append("--resume")
        run_logged(arguments, output / "logs/full_reproduction.log", lock_fd=lock_fd)
    return verify_reproduction(source_dir, cells, report)


def wait_for_robustness(
    robustness_dir: Path,
    source_dir: Path,
    output: Path,
    refits=None,
    supervisor_pid: int | None = None,
) -> None:
    """Wait for the existing frozen supervisor, then require its exact full grid."""
    from src.pipelines.robustness import verify_completed_robustness_run

    while not (robustness_dir / "completion.json").is_file():
        if supervisor_pid is not None:
            try:
                os.kill(supervisor_pid, 0)
            except ProcessLookupError as error:
                raise RuntimeError(
                    "frozen robustness supervisor exited before completing the plan"
                ) from error
        if refits is not None and refits.done() and refits.exception() is not None:
            raise refits.exception()
        count = len(list((robustness_dir / "cells").glob("*/*/*/*.json")))
        write_json_atomic(
            output / "robustness_progress.json",
            {
                "stage": "waiting_for_frozen_production",
                "stored_cells": count,
                "planned_cells": 825,
                "complete": False,
            },
        )
        print(f"waiting_for_robustness stored_cells={count}/825", flush=True)
        time.sleep(60)
    completion = verify_completed_robustness_run(
        robustness_dir, PROJECT_ROOT, confirmatory_run_dir=source_dir
    )
    if completion["stored_cells"] != 825:
        raise RuntimeError("frozen robustness completion must contain all 825 cells")
    write_json_atomic(
        output / "robustness_progress.json",
        {
            "stage": "frozen_production_verified",
            "stored_cells": 825,
            "planned_cells": 825,
            "complete": True,
        },
    )


def verify_rendered_bundle(
    directory: Path,
    *,
    source_dir: Path,
    posthoc: bool = False,
    expected_optional_sources: list | None = None,
    expected_source_hashes: dict | None = None,
) -> dict:
    """Verify a complete output inventory and its exact source/code lineage."""
    from src.rendering.verification import _safe_child

    lineage = json.loads((directory / "lineage.json").read_text())
    content = dict(lineage)
    digest = content.pop("lineage_content_sha256", None)
    if canonical_json_hash(content) != digest:
        raise RuntimeError("rendered bundle lineage content hash differs")
    if posthoc:
        if lineage.get("evidence_status") != "posthoc_sampler_sensitivity":
            raise RuntimeError("post-hoc bundle has an incorrect evidence label")
        for name in ("manifest", "completion", "inference"):
            if lineage[f"source_{name}_sha256"] != sha256_file(source_dir / f"{name}.json"):
                raise RuntimeError("post-hoc bundle source lineage differs")
        outputs = lineage["outputs"]
        code = lineage["renderer_input_sha256"]
    else:
        if lineage.get("evidence_status") != "confirmatory":
            raise RuntimeError("confirmatory bundle has an incorrect evidence label")
        if (
            expected_optional_sources is not None
            and lineage.get("optional_source_artifacts") != expected_optional_sources
        ):
            raise RuntimeError("rendered bundle optional evidence lineage differs")
        for name in ("manifest", "completion"):
            record = json.loads((source_dir / f"{name}.json").read_text())
            if lineage["source_run"][f"{name}_content_sha256"] != record[f"{name}_content_sha256"]:
                raise RuntimeError("confirmatory bundle source lineage differs")
        outputs = {row["path"]: row["sha256"] for row in lineage["outputs"]}
        if len(outputs) != len(lineage["outputs"]):
            raise RuntimeError("rendered bundle has duplicate output registrations")
        if expected_source_hashes is not None:
            for row in lineage["outputs"]:
                for reference in row["sources"]:
                    if expected_source_hashes.get(reference["artifact"]) != reference.get("sha256"):
                        raise RuntimeError("rendered output source differs from verified evidence")
        code = {
            lineage["renderer"]["path"]: lineage["renderer"]["sha256"],
            **lineage["renderer"]["module_sha256"],
        }
    actual = {
        str(path.relative_to(directory)) for path in directory.rglob("*") if path.is_file()
    } - {"lineage.json"}
    if actual != set(outputs):
        raise RuntimeError("rendered bundle output inventory differs")
    for relative, expected in outputs.items():
        if sha256_file(_safe_child(directory, relative)) != expected:
            raise RuntimeError(f"rendered output file hash differs: {relative}")
    for relative, expected in code.items():
        if sha256_file(_safe_child(PROJECT_ROOT, relative)) != expected:
            raise RuntimeError(f"rendered bundle uses different source code: {relative}")
    return lineage


def sampler_sensitivity(
    source_dir: Path, output: Path, workers: int, *, lock_fd: int | None = None
) -> Path:
    """Run all 75 post-hoc cells after the original six-worker production finishes."""
    root = output / "posthoc_sampler"
    arguments = [
        "scripts/run_horseshoe_sampler_sensitivity.py",
        "--run-dir",
        str(source_dir),
        "--output-root",
        str(root),
        "--workers",
        str(workers),
    ]
    if list(root.glob("*/manifest.json")):
        arguments.append("--resume")
    run_logged(arguments, output / "logs/posthoc_sampler.log", lock_fd=lock_fd)
    candidates = list(root.glob("*/completion.json"))
    if len(candidates) != 1:
        raise RuntimeError("sampler stage must produce exactly one completed sensitivity")
    return candidates[0].parent


def preserve_partial_render(directory: Path) -> None:
    """Keep an interrupted pure render and give its retry a fresh directory."""
    if not directory.exists() or (directory / "lineage.json").exists():
        return
    if not any(directory.iterdir()):
        return
    history = directory.parent / "interrupted_renders"
    history.mkdir(exist_ok=True)
    index = 1
    destination = history / f"{directory.name}_{index:03d}"
    while destination.exists():
        index += 1
        destination = history / f"{directory.name}_{index:03d}"
    directory.rename(destination)


def write_or_verify_result(path: Path, record: dict) -> None:
    """Keep a verified final result immutable when a completed programme resumes."""
    if path.exists():
        if json.loads(path.read_text()) != record:
            raise RuntimeError("existing verified programme result differs")
    else:
        write_json_atomic(path, record, overwrite=False)


def main() -> int:
    """Execute long stages from an immutable detached checkout and record readiness."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--robustness-dir", required=True, type=Path)
    parser.add_argument("--explanation", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--reproduction-workers", type=int, default=2)
    parser.add_argument("--sampler-workers", type=int, default=6)
    parser.add_argument("--robustness-supervisor-pid", type=int)
    args = parser.parse_args()
    if min(args.reproduction_workers, args.sampler_workers) < 1:
        raise ValueError("worker counts must be positive")
    head = subprocess.run(
        ["git", "symbolic-ref", "-q", "HEAD"], cwd=PROJECT_ROOT, capture_output=True
    )
    if head.returncode == 0:
        raise RuntimeError("run the results programme from a detached code checkout")
    tracked_changes = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    if tracked_changes.strip():
        raise RuntimeError("results programme requires unchanged committed source")
    source, robustness, explanation, output = (
        value.resolve()
        for value in (args.source_dir, args.robustness_dir, args.explanation, args.output_dir)
    )
    if any(
        output == protected or protected in output.parents for protected in (source, robustness)
    ):
        raise ValueError("programme output must be outside original evidence directories")
    output.mkdir(parents=True, exist_ok=True)
    execution_lock = acquire_programme_lock(output)
    code_commit: str | None = None
    try:
        lock_fd = execution_lock.fileno()
        initial_code = {
            str(path.relative_to(PROJECT_ROOT)): sha256_file(path)
            for folder in ("src", "scripts")
            for path in sorted((PROJECT_ROOT / folder).rglob("*.py"))
        }
        manifest_path = output / "programme_manifest.json"
        code_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        identity = {
            "code_commit": code_commit,
            "code_sha256": initial_code,
            "source_dir": str(source),
            "robustness_dir": str(robustness),
            "explanation_sha256": sha256_file(explanation),
        }
        if manifest_path.exists() and json.loads(manifest_path.read_text()) != identity:
            raise RuntimeError("programme checkpoint belongs to different source or code")
        if not manifest_path.exists():
            write_json_atomic(manifest_path, identity, overwrite=False)
        from src.rendering.verification import (
            verify_explainability_artifact,
            verify_frozen_run,
            verify_robustness_run,
        )
        from src.utils.frozen_evidence import verify_frozen_evidence
        from src.utils.posthoc_evidence import verify_posthoc_run

        run_logged(
            ["scripts/verify_environment.py"],
            output / "logs/environment_verification.log",
            lock_fd=lock_fd,
        )
        preflight = verify_frozen_run(source)
        verify_frozen_evidence(PROJECT_ROOT, preflight.manifest["input_sha256"])
        verify_explainability_artifact(explanation, preflight)
        del preflight
        with ThreadPoolExecutor(max_workers=1) as pool:
            full_refits = pool.submit(
                refit_all, source, output, args.reproduction_workers, lock_fd=lock_fd
            )
            wait_for_robustness(
                robustness, source, output, full_refits, args.robustness_supervisor_pid
            )
            run_logged(
                ["scripts/verify_environment.py"],
                output / "logs/environment_verification.log",
                lock_fd=lock_fd,
            )
            sampler = sampler_sensitivity(source, output, args.sampler_workers, lock_fd=lock_fd)
            reproduction = full_refits.result()
        from src.rendering.verification import (
            verify_explainability_artifact,
            verify_frozen_run,
        )
        from src.utils.frozen_evidence import verify_frozen_evidence

        frozen = verify_frozen_run(source)
        verify_frozen_evidence(PROJECT_ROOT, frozen.manifest["input_sha256"])
        explanation_record, explanation_ref = verify_explainability_artifact(explanation, frozen)
        robustness_record, robustness_ref = verify_robustness_run(robustness, frozen)
        sampler_record = verify_posthoc_run(sampler, source)
        rendered = output / "rendered_confirmatory"
        preserve_partial_render(rendered)
        if not (rendered / "lineage.json").exists():
            run_logged(
                [
                    "scripts/render_confirmatory.py",
                    "--run-dir",
                    str(source),
                    "--robustness-dir",
                    str(robustness),
                    "--explainability-artifact",
                    str(explanation),
                    "--output-dir",
                    str(rendered),
                ],
                output / "logs/render_confirmatory.log",
                lock_fd=lock_fd,
            )
        posthoc_rendered = output / "rendered_posthoc_sampler"
        preserve_partial_render(posthoc_rendered)
        if not (posthoc_rendered / "lineage.json").exists():
            run_logged(
                [
                    "scripts/render_horseshoe_sensitivity.py",
                    "--run-dir",
                    str(sampler),
                    "--source-dir",
                    str(source),
                    "--output-dir",
                    str(posthoc_rendered),
                ],
                output / "logs/render_posthoc_sampler.log",
                lock_fd=lock_fd,
            )
        source_hashes = {
            f"source_run/{name}": digest for name, digest in frozen.source_hashes.items()
        }
        source_hashes[explanation_ref["artifact"]] = explanation_ref["sha256"]
        source_hashes.update(
            {
                reference["artifact"]: reference["sha256"]
                for reference in robustness_record["source_refs"].values()
            }
        )
        verify_rendered_bundle(
            rendered,
            source_dir=source,
            expected_optional_sources=[explanation_ref, robustness_ref],
            expected_source_hashes=source_hashes,
        )
        verify_rendered_bundle(posthoc_rendered, source_dir=sampler, posthoc=True)
        current_code = {
            str(path.relative_to(PROJECT_ROOT)): sha256_file(path)
            for folder in ("src", "scripts")
            for path in sorted((PROJECT_ROOT / folder).rglob("*.py"))
        }
        if current_code != initial_code:
            raise RuntimeError("programme source changed during execution")
        result = {
            "status": "analysis_and_rendering_verified_pending_final_visual_qa",
            "code_commit": code_commit,
            "confirmatory_status_counts": frozen.completion["status_counts"],
            "confirmatory_holm_family_complete": frozen.inference["holm_family_complete"],
            "reproduction_cells_identical": reproduction["cells_identical"],
            "robustness_status_counts": robustness_record["completion"]["status_counts"],
            "posthoc_sampler_status_counts": sampler_record["completion"]["status_counts"],
            "posthoc_holm_family_complete": sampler_record["inference"]["holm_family_complete"],
            "explanation_claim_permitted": explanation_record["convergence"]["summary"].get(
                "claim_permitted", False
            ),
            "source_file_sha256": {
                str(path): sha256_file(path)
                for path in (
                    source / "manifest.json",
                    source / "completion.json",
                    robustness / "completion.json",
                    sampler / "completion.json",
                    output / "reproduction/verification.json",
                    rendered / "lineage.json",
                    posthoc_rendered / "lineage.json",
                )
            },
        }
        result["result_content_sha256"] = canonical_json_hash(result)
        write_or_verify_result(output / "programme_analysis_verified.json", result)
        print(
            f"programme_analysis_verified={output / 'programme_analysis_verified.json'}", flush=True
        )
        return 0
    except Exception as error:
        write_json_atomic(
            output / "programme_failure.json",
            {"status": "incomplete", "error": str(error), "code_commit": code_commit},
        )
        raise
    finally:
        execution_lock.close()


if __name__ == "__main__":
    raise SystemExit(main())
