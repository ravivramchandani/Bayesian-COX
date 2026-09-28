"""Fail closed on broken child stages and altered completed output bundles.

Covers ``scripts/complete_results_programme.py``, the coordinator that runs
environment verification, the full refit reproduction, the post-hoc sampler
sensitivity and both renderers as logged child processes. The checks cover
child exit codes, the exclusive output lock, preservation of interrupted
renders, immutable final results, and verification of rendered bundles against
their recorded source and code hashes (INV-007). Stages are faked or replaced
by short inline programs; nothing is fitted.
"""

from __future__ import annotations

import importlib.util
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.utils.io import write_json_atomic
from src.utils.reproducibility import canonical_json_hash, sha256_file


@pytest.fixture
def programme():
    """Load the coordinator script from its file path as a fresh module."""
    path = Path(__file__).resolve().parents[1] / "scripts/complete_results_programme.py"
    spec = importlib.util.spec_from_file_location("results_programme_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_failed_child_stage_is_not_accepted(programme, tmp_path, monkeypatch):
    """A child stage with a non-zero exit code raises instead of counting as complete."""
    monkeypatch.setattr(
        programme.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=2)
    )
    with pytest.raises(RuntimeError, match="stage failed with exit 2"):
        programme.run_logged(["failed-stage.py"], tmp_path / "stage.log")


def test_duplicate_coordinator_cannot_reuse_an_active_output(programme, tmp_path):
    """A second coordinator cannot lock an output directory until the first releases it."""
    first = programme.acquire_programme_lock(tmp_path)
    try:
        with pytest.raises(RuntimeError, match="already owns this output"):
            programme.acquire_programme_lock(tmp_path)
    finally:
        first.close()
    resumed = programme.acquire_programme_lock(tmp_path)
    resumed.close()


def test_duplicate_coordinator_rejects_before_manifest_access(programme, tmp_path, monkeypatch):
    """A duplicate coordinator stops at the lock before writing a manifest or failure record."""
    code = tmp_path / "code"
    code.mkdir()
    output = tmp_path / "output"
    output.mkdir()
    first = programme.acquire_programme_lock(output)
    monkeypatch.setattr(programme, "PROJECT_ROOT", code)
    monkeypatch.setattr(
        programme.sys,
        "argv",
        [
            "complete_results_programme.py",
            "--source-dir",
            str(tmp_path / "source"),
            "--robustness-dir",
            str(tmp_path / "robustness"),
            "--explanation",
            str(tmp_path / "missing-explanation.json"),
            "--output-dir",
            str(output),
        ],
    )
    # Fake Git: ``symbolic-ref`` fails, as in a detached checkout, and
    # ``status`` reports no tracked changes, so ``main`` reaches the lock.
    monkeypatch.setattr(
        programme.subprocess,
        "run",
        lambda arguments, **kwargs: SimpleNamespace(
            returncode=1 if "symbolic-ref" in arguments else 0, stdout=""
        ),
    )
    try:
        with pytest.raises(RuntimeError, match="already owns this output"):
            programme.main()
    finally:
        first.close()
    assert not (output / "programme_manifest.json").exists()
    assert not (output / "programme_failure.json").exists()


def test_surviving_stage_holds_lock_after_coordinator_handle_closes(programme, tmp_path):
    """A child stage that inherited the lock keeps the output locked after the parent closes it."""
    first = programme.acquire_programme_lock(tmp_path)
    ready = tmp_path / "child-ready"
    release = tmp_path / "child-release"
    # The child checks that it inherited the lock descriptor, signals readiness
    # and then waits for the release file, so the lock can be probed while only
    # the child holds it.
    child = """
import os
import sys
import time
from pathlib import Path
os.fstat(int(sys.argv[1]))
Path(sys.argv[2]).write_text('ready')
deadline = time.monotonic() + 10
while not Path(sys.argv[3]).exists():
    if time.monotonic() >= deadline:
        raise RuntimeError('test stage release timed out')
    time.sleep(0.01)
"""
    with ThreadPoolExecutor(max_workers=1) as pool:
        stage = pool.submit(
            programme.run_logged,
            ["-c", child, str(first.fileno()), str(ready), str(release)],
            tmp_path / "stage.log",
            lock_fd=first.fileno(),
        )
        try:
            deadline = time.monotonic() + 5
            while not ready.exists():
                if stage.done():
                    stage.result()
                    pytest.fail("stage exited before reporting its inherited descriptor")
                if time.monotonic() >= deadline:
                    pytest.fail("stage did not report its inherited descriptor")
                time.sleep(0.01)
            # Only the child's inherited descriptor now holds the lock.
            first.close()
            with pytest.raises(RuntimeError, match="already owns this output"):
                programme.acquire_programme_lock(tmp_path)
        finally:
            first.close()
            release.write_text("exit")
            stage.result(timeout=5)
    resumed = programme.acquire_programme_lock(tmp_path)
    resumed.close()


def test_restarted_render_preserves_partial_files(programme, tmp_path):
    """An interrupted render without lineage is moved aside, not deleted, before a retry."""
    render = tmp_path / "render"
    render.mkdir()
    (render / "partial.png").write_bytes(b"partial artefact")
    programme.preserve_partial_render(render)
    assert not render.exists()
    assert (
        tmp_path / "interrupted_renders/render_001/partial.png"
    ).read_bytes() == b"partial artefact"


def test_verified_programme_result_can_resume_without_overwriting(programme, tmp_path):
    """An equal final result is not rewritten on resume, and a different one is refused."""
    path = tmp_path / "verified.json"
    record = {"status": "verified", "cells": 450}
    programme.write_or_verify_result(path, record)
    before = path.stat().st_mtime_ns
    programme.write_or_verify_result(path, record)
    assert path.stat().st_mtime_ns == before
    with pytest.raises(RuntimeError, match="existing verified programme result differs"):
        programme.write_or_verify_result(path, {"status": "verified", "cells": 449})


@pytest.mark.parametrize("corruption", [None, "omitted_supplement", "output_source"])
def test_confirmatory_bundle_requires_verified_supplement_lineage(
    programme, tmp_path, monkeypatch, corruption
):
    """A confirmatory bundle must cite the verified supplementary artefact and its hash (INV-007)."""
    source, root, output = tmp_path / "source", tmp_path / "code", tmp_path / "render"
    source.mkdir()
    root.mkdir()
    output.mkdir()
    # A minimal bundle: one output whose lineage cites one supplementary
    # artefact. "omitted_supplement" drops it from the bundle's optional
    # sources; "output_source" records a different hash for it on the output.
    records = {"manifest": "m" * 64, "completion": "c" * 64}
    for name, digest in records.items():
        write_json_atomic(source / f"{name}.json", {f"{name}_content_sha256": digest})
    (root / "renderer.py").write_text("original code\n")
    (output / "table.csv").write_text("original output\n")
    supplemental = {"artifact": "/verified/explanation.json", "sha256": "a" * 64}
    lineage = {
        "evidence_status": "confirmatory",
        "source_run": {f"{name}_content_sha256": digest for name, digest in records.items()},
        "optional_source_artifacts": [supplemental],
        "renderer": {
            "path": "renderer.py",
            "sha256": sha256_file(root / "renderer.py"),
            "module_sha256": {},
        },
        "outputs": [
            {
                "path": "table.csv",
                "sha256": sha256_file(output / "table.csv"),
                "sources": [dict(supplemental)],
            }
        ],
    }
    if corruption == "omitted_supplement":
        lineage["optional_source_artifacts"] = []
    elif corruption == "output_source":
        lineage["outputs"][0]["sources"][0]["sha256"] = "b" * 64
    lineage["lineage_content_sha256"] = canonical_json_hash(lineage)
    write_json_atomic(output / "lineage.json", lineage)
    # Renderer code hashes are checked under PROJECT_ROOT.
    monkeypatch.setattr(programme, "PROJECT_ROOT", root)
    kwargs = {
        "source_dir": source,
        "expected_optional_sources": [supplemental],
        "expected_source_hashes": {supplemental["artifact"]: supplemental["sha256"]},
    }
    if corruption:
        with pytest.raises(RuntimeError):
            programme.verify_rendered_bundle(output, **kwargs)
    else:
        assert programme.verify_rendered_bundle(output, **kwargs) == lineage


@pytest.mark.parametrize("corruption", [None, "output", "unexpected", "source", "code"])
def test_posthoc_bundle_validation_covers_files_and_lineage(
    programme, tmp_path, monkeypatch, corruption
):
    """Post-hoc bundle verification covers every output file, its sources and its code (INV-007)."""
    source, root, output = tmp_path / "source", tmp_path / "code", tmp_path / "render"
    source.mkdir()
    root.mkdir()
    output.mkdir()
    for name in ("manifest", "completion", "inference"):
        write_json_atomic(source / f"{name}.json", {"original": name})
    (root / "renderer.py").write_text("original code\n")
    (output / "table.csv").write_text("original output\n")
    lineage = {
        "evidence_status": "posthoc_sampler_sensitivity",
        **{
            f"source_{name}_sha256": sha256_file(source / f"{name}.json")
            for name in ("manifest", "completion", "inference")
        },
        "outputs": {"table.csv": sha256_file(output / "table.csv")},
        "renderer_input_sha256": {"renderer.py": sha256_file(root / "renderer.py")},
    }
    lineage["lineage_content_sha256"] = canonical_json_hash(lineage)
    write_json_atomic(output / "lineage.json", lineage)
    monkeypatch.setattr(programme, "PROJECT_ROOT", root)
    # Each corruption happens after the lineage was written and is absent from it.
    if corruption == "output":
        (output / "table.csv").write_text("changed\n")
    elif corruption == "unexpected":
        (output / "unexpected.csv").write_text("unregistered\n")
    elif corruption == "source":
        (source / "inference.json").write_text('{"changed":true}')
    elif corruption == "code":
        (root / "renderer.py").write_text("changed code\n")
    if corruption:
        with pytest.raises(RuntimeError):
            programme.verify_rendered_bundle(output, source_dir=source, posthoc=True)
    else:
        assert programme.verify_rendered_bundle(output, source_dir=source, posthoc=True) == lineage
