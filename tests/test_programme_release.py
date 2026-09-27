"""Archive-format and fail-closed tests; fixtures contain no clinical results."""

import hashlib
import io
import json
import subprocess
import tarfile

import pytest

from scripts import package_programme_release as package
from scripts import restore_programme_release as restore


def write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True))
    return package.sha256_file(path)


@pytest.mark.parametrize("name", ["../x", "/x", "a/../x", "a//x", "a/./x", "a\\x", "C:x", "x\ny", "x\x00y", ""])
def test_relative_paths_reject_traversal_and_nonportable_names(name):
    with pytest.raises(ValueError):
        package.safe_relative(name)


def test_archives_are_byte_identical_despite_source_metadata(tmp_path):
    source = tmp_path / "source"
    source.write_bytes(b"archive format test")
    first, second = tmp_path / "first.tar.gz", tmp_path / "second.tar.gz"
    expected = package.write_archive(first, {"nested/file": source})
    source.chmod(0o600)
    assert package.write_archive(second, {"nested/file": source}) == expected
    assert first.read_bytes() == second.read_bytes()
    restore.inspect_archive(first, expected)


@pytest.mark.parametrize("kind", ["traversal", "symlink", "hardlink", "duplicate", "extra"])
def test_restore_rejects_unsafe_archive_members(tmp_path, kind):
    path = tmp_path / "unsafe.tar.gz"
    with tarfile.open(path, "w:gz") as archive:
        member = tarfile.TarInfo("../escape" if kind == "traversal" else "allowed")
        member.size = 1
        if kind in {"symlink", "hardlink"}:
            member.type = tarfile.SYMTYPE if kind == "symlink" else tarfile.LNKTYPE
            member.linkname = "../escape"
            member.size = 0
        archive.addfile(member, io.BytesIO(b"x"))
        if kind in {"duplicate", "extra"}:
            member = tarfile.TarInfo("allowed" if kind == "duplicate" else "extra")
            member.size = 1
            archive.addfile(member, io.BytesIO(b"x"))
    expected = {"allowed": hashlib.sha256(b"x").hexdigest()}
    with pytest.raises(ValueError):
        restore.inspect_archive(path, expected)
    assert not (tmp_path / "escape").exists()


def test_inventory_rejects_added_files_changed_bytes_and_links(tmp_path):
    root = tmp_path / "artifact"
    root.mkdir()
    (root / "first").write_bytes(b"first")
    expected = package.directory_inventory(root)
    package.verify_inventory(root, expected)
    (root / "first").write_bytes(b"changed")
    with pytest.raises(ValueError):
        package.verify_inventory(root, expected)
    (root / "link").symlink_to(root / "first")
    with pytest.raises(ValueError):
        package.directory_inventory(root)


def test_pending_analysis_report_cannot_be_packaged(tmp_path):
    path = tmp_path / "analysis.json"
    write_json(path, {"status": "analysis_and_rendering_verified_pending_final_visual_qa"})
    with pytest.raises(ValueError, match="release_ready"):
        package.package_release(path, tmp_path, tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_committed_code_must_match_sealed_actual_bytes(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "source.py").write_bytes(b"print('format fixture')\n")
    subprocess.run(["git", "add", "source.py"], cwd=tmp_path, check=True)
    subprocess.run([
        "git", "-c", "user.name=Unit test", "-c", "user.email=unit@example.invalid",
        "commit", "-qm", "Archive fixture",
    ], cwd=tmp_path, check=True)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=tmp_path).decode().strip()
    seal = {"code_commit": commit, "code_files": {"source.py": package.sha256_file(tmp_path / "source.py")}}
    assert package.committed_code(tmp_path, seal)["source.py"] == (tmp_path / "source.py").read_bytes()
    (tmp_path / "source.py").write_bytes(b"changed")
    with pytest.raises(ValueError, match="actual programme code"):
        package.committed_code(tmp_path, seal)


def test_directory_claim_never_replaces_an_existing_empty_directory(tmp_path):
    stage, destination = tmp_path / "stage", tmp_path / "destination"
    stage.mkdir()
    (stage / "file").write_bytes(b"archive fixture")
    destination.mkdir()
    with pytest.raises(FileExistsError):
        package.publish_staged_directory(stage, destination)
    assert list(destination.iterdir()) == []


def format_release(tmp_path):
    """Construct only an archive-format fixture, without claiming scientific gates."""
    release, original = tmp_path / "release", tmp_path / "original"
    release.mkdir()
    original.mkdir()
    (original / "source").write_bytes(b"immutable source fixture")
    descriptor = {"root": str(original), "files": package.directory_inventory(original)}
    seal = {
        "status": "release_ready", "code_commit": "1" * 40,
        "artifacts": {"original450": descriptor}, "code_files": {"script.py": hashlib.sha256(b"code fixture").hexdigest()},
    }
    assets = {}
    code_name = "programme-committed-code.tar.gz"
    inventory = package.write_archive(release / code_name, {"code/script.py": b"code fixture"})
    assets[code_name] = {"sha256": package.sha256_file(release / code_name), "files": inventory}
    for archive_name, names in package.ARCHIVE_GROUPS.items():
        members = {f"{name}/format_fixture": name.encode() for name in names}
        inventory = package.write_archive(release / archive_name, members)
        assets[archive_name] = {"sha256": package.sha256_file(release / archive_name), "files": inventory}
        for name in names:
            seal["artifacts"][name] = {"root": "/unit-format-fixture", "files": {"format_fixture": hashlib.sha256(name.encode()).hexdigest()}}
    metadata = {}
    metadata["programme_analysis_verified.json"] = write_json(release / "programme_analysis_verified.json", {"fixture": "archive-format-only"})
    metadata["programme_visual_qa.json"] = write_json(release / "programme_visual_qa.json", {"status": "passed", "fixture": "archive-format-only"})
    seal["verified_report"] = {"path": "/unit-format-fixture", "sha256": metadata["programme_analysis_verified.json"]}
    seal["visual_qa"] = {"status": "passed", "path": "/unit-format-fixture", "sha256": metadata["programme_visual_qa.json"]}
    metadata["programme_release_ready.json"] = write_json(release / "programme_release_ready.json", seal)
    manifest = {
        "status": "private_supplementary_release", "code_commit": seal["code_commit"],
        "seal_sha256": metadata["programme_release_ready.json"],
        "original_confirmatory_release": descriptor, "assets": assets, "metadata_sha256": metadata,
    }
    manifest["manifest_content_sha256"] = package.canonical_hash(manifest)
    write_json(release / "programme_release_manifest.json", manifest)
    inventory = package.directory_inventory(release)
    (release / "SHA256SUMS").write_text("".join(f"{digest}  {name}\n" for name, digest in inventory.items()))
    return release, original


def test_restore_roundtrip_is_exact_write_once_and_original_is_unchanged(tmp_path):
    release, original = format_release(tmp_path)
    before = package.directory_inventory(original)
    manifest = restore.verify_release(release, original)
    destination = tmp_path / "restored"
    assert restore.restore_release(release, original, destination) == destination
    assert package.directory_inventory(destination) == restore.restored_inventory(release, manifest)
    assert restore.restore_release(release, original, destination) == destination
    assert package.directory_inventory(original) == before
    (destination / "reproduction/format_fixture").write_bytes(b"edited")
    with pytest.raises(ValueError):
        restore.restore_release(release, original, destination)
    assert (destination / "reproduction/format_fixture").read_bytes() == b"edited"


def test_verify_release_rejects_changed_asset_and_original(tmp_path):
    release, original = format_release(tmp_path)
    (original / "source").write_bytes(b"changed")
    with pytest.raises(ValueError, match="inventory"):
        restore.verify_release(release, original)
    (original / "source").write_bytes(b"immutable source fixture")
    archive = release / "programme-reproduction.tar.gz"
    archive.write_bytes(archive.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="changed"):
        restore.verify_release(release, original)


def test_reproduction_uses_model_key_with_human_readable_model_label(tmp_path, monkeypatch):
    from types import SimpleNamespace

    source = SimpleNamespace(cells=[("cell", {
        "dataset": "gbsg2", "model": "Bayesian Cox (normal)", "model_key": "bayesian_normal",
        "repeat": 0, "fold": 0,
    })])
    report = {
        "analysis": "confirmatory_refit_reproduction", "selection": "all",
        "cells_checked": 450, "cells_identical": 450, "evidence_status": "verification_only",
        "cells": [{"cell": "gbsg2:bayesian_normal:0:0", "identical": True, "n_differences": 0}] * 450,
    }
    report["report_content_sha256"] = package.canonical_hash(report)
    path = tmp_path / "report.json"
    write_json(path, report)
    # Pass the identity check and stop at provenance, before any result verification.
    with pytest.raises(KeyError, match="provenance"):
        package._verify_reproduction(
            {"artifacts": {"reproduction": {"files": {"report.json": package.sha256_file(path)}}}},
            {"reproduction": tmp_path}, source,
        )
