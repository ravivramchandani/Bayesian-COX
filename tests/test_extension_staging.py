"""Reject mismatched measured-source evidence before assembling a transfer."""

from __future__ import annotations

import json
import runpy
import shutil
import sys
from pathlib import Path

import pytest

from src.utils.reproducibility import canonical_json_hash, sha256_file


def source_fixture(tmp_path: Path, broken_field: str | None = None) -> tuple:
    """Create a small coherent freeze with independent measured files."""
    root = tmp_path / "production"
    records = root / "coordination/extension_sources"
    records.mkdir(parents=True)
    known = root / "tests/fixtures/extensions/metabric_known_accession_pairs.csv"
    known.parent.mkdir(parents=True)
    known.write_text("first,second\n")
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "LICENSE").write_text("fixture license\n")
    (raw / "data_clinical_patient.txt").write_text("fixture patients\n")
    matched = tmp_path / "matched.parquet"
    matched.write_bytes(b"fixture matched bytes")
    report = {"data_files": [{"name": p.name, "downloaded_sha256": sha256_file(p)}
                             for p in sorted(raw.iterdir())]}
    preparation = {"matched_sha256": sha256_file(matched), "clinical_sha256": "a" * 64,
                   "known_pairs_sha256": sha256_file(known),
                   "source_sha256": {"data_clinical_patient.txt": sha256_file(raw / "data_clinical_patient.txt")}}
    if broken_field:
        preparation[broken_field] = ({"data_clinical_patient.txt": "b" * 64}
                                     if broken_field == "source_sha256" else "b" * 64)
    report_path = records / "metabric_source_report.json"
    prep_path = records / "matched_metabric_manifest.json"
    report_path.write_text(json.dumps(report))
    prep_path.write_text(json.dumps(preparation))
    freeze = {"sha256": {str(p.relative_to(root)): sha256_file(p)
                         for p in (known, report_path, prep_path)}}
    freeze["content_sha256"] = canonical_json_hash(freeze)
    (root / "coordination/extension_protocol_freeze.json").write_text(json.dumps(freeze))
    manifest = {"freeze_sha256": freeze["content_sha256"], "matched_sha256": sha256_file(matched),
                "input_sha256": {"data/raw/metabric.csv": "a" * 64}}
    supplied_report, supplied_prep = tmp_path / "report.json", tmp_path / "prep.json"
    supplied_report.write_bytes(report_path.read_bytes())
    supplied_prep.write_bytes(prep_path.read_bytes())
    return root, manifest, matched, supplied_prep, raw, supplied_report


@pytest.fixture
def staging_module(monkeypatch):
    directory = Path(__file__).resolve().parents[1] / "scripts/extension_release"
    monkeypatch.syspath_prepend(str(directory))
    return runpy.run_path(str(directory / "stage_extensions.py"))


@pytest.fixture
def source_verifier(staging_module):
    return staging_module["verify_source_inputs"]


def test_frozen_source_inventory_is_bound(source_verifier, tmp_path):
    args = source_fixture(tmp_path)
    hashes = source_verifier(*args)
    assert hashes["data/matched_metabric.parquet"] == sha256_file(args[2])
    assert hashes["data/metabric_raw/LICENSE"] == sha256_file(args[4] / "LICENSE")
    assert len(hashes) == 5


@pytest.mark.parametrize("target", ["matched", "preparation", "report", "raw", "analysis"])
def test_altered_transfer_source_is_rejected(source_verifier, tmp_path, target):
    args = source_fixture(tmp_path)
    root, _, matched, prep, raw, report = args
    analysis = tmp_path / "analysis"
    shutil.copytree(root, analysis)
    changed = {"matched": matched, "preparation": prep, "report": report,
               "raw": raw / "LICENSE", "analysis": analysis / "tests/fixtures/extensions/metabric_known_accession_pairs.csv"}[target]
    changed.write_bytes(changed.read_bytes() + b" ")
    with pytest.raises(ValueError):
        source_verifier(*args, analysis=analysis)


@pytest.mark.parametrize("field", ["matched_sha256", "clinical_sha256", "known_pairs_sha256", "source_sha256"])
def test_inconsistent_frozen_preparation_is_rejected(source_verifier, tmp_path, field):
    with pytest.raises(ValueError):
        source_verifier(*source_fixture(tmp_path, field))


@pytest.mark.skipif(sys.platform != "darwin", reason="native clonefile is macOS-specific")
def test_native_clone_is_independent_and_refuses_overwrite(staging_module, tmp_path):
    source, target = tmp_path / "original", tmp_path / "clone"
    source.write_bytes(b"immutable input" * 1024)
    staging_module["copy_file"](source, target, clone=True)
    assert source.stat().st_ino != target.stat().st_ino
    assert source.read_bytes() == target.read_bytes()
    target.write_bytes(b"changed clone")
    assert source.read_bytes() == b"immutable input" * 1024
    with pytest.raises(OSError):
        staging_module["copy_file"](source, target, clone=True)
    assert target.read_bytes() == b"changed clone"


@pytest.mark.skipif(sys.platform != "darwin", reason="native clonefile is macOS-specific")
def test_native_clone_tree_preserves_separate_files(staging_module, tmp_path):
    source, target = tmp_path / "original_tree", tmp_path / "cloned_tree"
    (source / "nested").mkdir(parents=True)
    (source / "nested/a").write_bytes(b"a")
    (source / "b").write_bytes(b"b")
    staging_module["copy_tree"](source, target, clone=True)
    (target / "nested/a").write_bytes(b"changed")
    assert (source / "nested/a").read_bytes() == b"a"
    assert (target / "b").read_bytes() == b"b"
