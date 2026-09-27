"""Fail closed on broken child stages and altered completed output bundles."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.utils.io import write_json_atomic
from src.utils.reproducibility import canonical_json_hash, sha256_file


@pytest.fixture
def programme():
    path = Path(__file__).resolve().parents[1] / "scripts/complete_results_programme.py"
    spec = importlib.util.spec_from_file_location("results_programme_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_failed_child_stage_is_not_accepted(programme, tmp_path, monkeypatch):
    monkeypatch.setattr(
        programme.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=2)
    )
    with pytest.raises(RuntimeError, match="stage failed with exit 2"):
        programme.run_logged(["failed-stage.py"], tmp_path / "stage.log")


def test_restarted_render_preserves_partial_files(programme, tmp_path):
    render = tmp_path / "render"
    render.mkdir()
    (render / "partial.png").write_bytes(b"partial artefact")
    programme.preserve_partial_render(render)
    assert not render.exists()
    assert (
        tmp_path / "interrupted_renders/render_001/partial.png"
    ).read_bytes() == b"partial artefact"


def test_verified_programme_result_can_resume_without_overwriting(programme, tmp_path):
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
    source, root, output = tmp_path / "source", tmp_path / "code", tmp_path / "render"
    source.mkdir()
    root.mkdir()
    output.mkdir()
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
