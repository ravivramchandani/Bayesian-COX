#!/usr/bin/env python3
"""Verify or safely restore private supplementary programme assets.

The original 450-cell private Release must already be restored separately.
No download, publication, fitting or modification of that source is performed.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from scripts.package_programme_release import (
    ARCHIVE_GROUPS,
    directory_inventory,
    load_mapping,
    publish_staged_directory,
    safe_relative,
    sha256_file,
    validate_inventory,
    verify_content_hash,
    verify_inventory,
)


def inspect_archive(path: Path, expected: dict[str, str], destination: Path | None = None) -> None:
    """Verify every regular archive member, optionally extracting into a new directory."""
    expected = validate_inventory(expected)
    seen = set()
    with tarfile.open(path, "r:gz") as archive:
        for member in archive:
            name = safe_relative(member.name)
            if not member.isfile() or name in seen or name not in expected:
                raise ValueError(f"unsafe, duplicate or undeclared archive member: {name}")
            seen.add(name)
            handle = archive.extractfile(member)
            if handle is None:
                raise ValueError(f"archive member cannot be read: {name}")
            target = None
            if destination is not None:
                target_path = destination / name
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target = target_path.open("xb")
            digest = hashlib.sha256()
            length = 0
            try:
                with handle:
                    for chunk in iter(lambda handle=handle: handle.read(1024 * 1024), b""):
                        length += len(chunk)
                        digest.update(chunk)
                        if target is not None:
                            target.write(chunk)
            finally:
                if target is not None:
                    target.close()
            if length != member.size or digest.hexdigest() != expected[name]:
                raise ValueError(f"archive member hash or size mismatch: {name}")
    if seen != set(expected):
        raise ValueError(f"archive is missing declared members: {path}")


def _verify_seal_copy(release: Path, manifest: dict[str, Any]) -> None:
    seal = load_mapping(release / "programme_release_ready.json")
    if seal.get("status") != "release_ready":
        raise ValueError("release has no final release_ready seal")
    if seal.get("code_commit") != manifest["code_commit"]:
        raise ValueError("release code revision differs from its final seal")
    if seal["artifacts"]["original450"] != manifest["original_confirmatory_release"]:
        raise ValueError("original confirmatory reference differs from the final seal")
    if (manifest["seal_sha256"] != sha256_file(release / "programme_release_ready.json")
            or seal["verified_report"]["sha256"] != sha256_file(release / "programme_analysis_verified.json")
            or seal["visual_qa"]["sha256"] != sha256_file(release / "programme_visual_qa.json")
            or seal["visual_qa"].get("status") != "passed"
            or load_mapping(release / "programme_visual_qa.json").get("status") != "passed"):
        raise ValueError("final seal, verified report or visual QA bytes changed")
    for archive_name, names in ARCHIVE_GROUPS.items():
        expected = {
            f"{name}/{relative}": digest
            for name in names for relative, digest in seal["artifacts"][name]["files"].items()
        }
        if manifest["assets"][archive_name]["files"] != expected:
            raise ValueError(f"release archive differs from final artifact seal: {archive_name}")
    code_files = manifest["assets"]["programme-committed-code.tar.gz"]["files"]
    if any(not name.startswith("code/") for name in code_files):
        raise ValueError("committed-code archive contains files outside its code prefix")
    for name, digest in validate_inventory(seal["code_files"]).items():
        if code_files.get(f"code/{name}") != digest:
            raise ValueError(f"code archive differs from the sealed actual source: {name}")


def verify_release(release: Path, original_run: Path) -> dict[str, Any]:
    """Verify all asset hashes, safe member inventories, metadata and original source."""
    manifest = load_mapping(release / "programme_release_manifest.json")
    verify_content_hash(manifest, "manifest_content_sha256")
    if manifest.get("status") != "private_supplementary_release":
        raise ValueError("unexpected release status")
    required_assets = set(ARCHIVE_GROUPS) | {"programme-committed-code.tar.gz"}
    if set(manifest.get("assets", {})) != required_assets:
        raise ValueError("release must contain all five supplementary archives")
    expected = dict(validate_inventory(manifest["metadata_sha256"]))
    if set(expected) != {
        "programme_release_ready.json", "programme_analysis_verified.json", "programme_visual_qa.json",
    }:
        raise ValueError("release metadata inventory is incomplete")
    for name, record in manifest["assets"].items():
        safe_relative(name)
        expected[name] = record["sha256"]
    expected["programme_release_manifest.json"] = sha256_file(release / "programme_release_manifest.json")
    checksums = {}
    for line in (release / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split("  ", 1)
        safe_relative(name)
        if name in checksums:
            raise ValueError("checksum listing contains duplicate files")
        checksums[name] = digest
    if checksums != expected:
        raise ValueError("checksum listing differs from the release inventory")
    actual = directory_inventory(release)
    actual.pop("SHA256SUMS", None)
    if actual != validate_inventory(expected):
        raise ValueError("release has missing, changed or undeclared files")
    _verify_seal_copy(release, manifest)
    verify_inventory(original_run, manifest["original_confirmatory_release"]["files"])
    member_names = set()
    for name, record in manifest["assets"].items():
        inventory = validate_inventory(record["files"])
        if member_names.intersection(inventory):
            raise ValueError("archives contain colliding destination files")
        member_names.update(inventory)
        inspect_archive(release / name, inventory)
    return manifest


def restored_inventory(release: Path, manifest: dict[str, Any]) -> dict[str, str]:
    """Describe the exact restored tree, including a copy of its release metadata."""
    expected = {
        relative: digest for record in manifest["assets"].values()
        for relative, digest in record["files"].items()
    }
    for name in set(manifest["metadata_sha256"]) | {"programme_release_manifest.json", "SHA256SUMS"}:
        expected[f"release_metadata/{name}"] = sha256_file(release / name)
    return expected


def restore_release(release: Path, original_run: Path, destination: Path) -> Path:
    """Restore verified assets into a new directory; an existing directory is verify-only."""
    manifest = verify_release(release, original_run)
    destination = destination.resolve()
    if (destination == original_run.resolve() or original_run.resolve() in destination.parents
            or destination == release.resolve() or release.resolve() in destination.parents):
        raise ValueError("restore output must be outside the release and original evidence")
    expected = restored_inventory(release, manifest)
    if destination.exists():
        verify_inventory(destination, expected)
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".programme-restore-", dir=destination.parent))
    try:
        for name, record in manifest["assets"].items():
            inspect_archive(release / name, record["files"], stage)
        metadata = stage / "release_metadata"
        metadata.mkdir()
        for name in set(manifest["metadata_sha256"]) | {"programme_release_manifest.json", "SHA256SUMS"}:
            shutil.copyfile(release / name, metadata / name)
        verify_inventory(stage, expected)
        verify_release(release, original_run)
        publish_staged_directory(stage, destination)
        return destination
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def main() -> int:
    """Verify local assets or restore them without contacting any external service."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-dir", required=True, type=Path)
    parser.add_argument("--original-run", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    release, source = args.release_dir.resolve(), args.original_run.resolve()
    if args.output_dir is None:
        verify_release(release, source)
        print(f"verified_private_programme_release={release}")
    else:
        print(restore_release(release, source, args.output_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
