#!/usr/bin/env python3
"""Restore and verify the frozen confirmatory evidence from its private release."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import tarfile
import tempfile
from collections import Counter
from pathlib import Path, PurePosixPath

RELEASE_REPOSITORY = "ravivramchandani/Bayesian-COX"
RELEASE_TAG = "confirmatory-v1-44b6085"
ARCHIVE_NAME = "Bayesian-COX-confirmatory-v1-cdcdcee84651-44b6085.tar.gz"
CHECKSUM_NAME = f"{ARCHIVE_NAME}.sha256"
ARCHIVE_SHA256 = "0dbb745b82e5998b5aabc4bb3f05b28f87e00ba2851101a8accb83d447ddf34b"
RUN_RELATIVE_PATH = Path("reports/confirmatory/confirmatory_v1_confirmatory_cdcdcee84651")
RUN_ARCHIVE_PREFIX = PurePosixPath(RUN_RELATIVE_PATH.as_posix())
COMPLETION_CONTENT_SHA256 = "03870efdae3134305794ea977fd9cbe7913c0d693f1b009337546319aa03bee1"
MANIFEST_CONTENT_SHA256 = "9ec040841b4751ee3064c93d21d5069ed27bf3bfd6641f0dfffff76557bbf9f7"
MANIFEST_FILE_SHA256 = "2a1817365675aa179174b5edf5b3da67bbcb2be1b2eb4143347e4b295052ce02"
COMPLETION_FILE_SHA256 = "44d5d6e2c3cf4d0350c3bc8cb27291436c9934b219c4c895cb139525e6fa25f6"
EXPECTED_STATUSES = {"complete": 430, "failed_diagnostics": 20}


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_extract(archive_path: Path, extraction_root: Path) -> None:
    """Extract only regular files/directories beneath the frozen run prefix."""
    extraction_root.mkdir(parents=True, exist_ok=False)
    root = extraction_root.resolve()
    seen: set[PurePosixPath] = set()

    with tarfile.open(archive_path, mode="r:gz") as archive:
        members = archive.getmembers()
        if not members:
            raise RuntimeError("release archive is empty")
        for member in members:
            member_path = PurePosixPath(member.name)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise RuntimeError(f"unsafe archive path: {member.name}")
            if member_path != RUN_ARCHIVE_PREFIX and RUN_ARCHIVE_PREFIX not in member_path.parents:
                raise RuntimeError(f"unexpected archive path: {member.name}")
            if member_path in seen:
                raise RuntimeError(f"duplicate archive path: {member.name}")
            seen.add(member_path)
            if not (member.isfile() or member.isdir()):
                raise RuntimeError(f"unsupported archive member type: {member.name}")

            target = extraction_root.joinpath(*member_path.parts)
            resolved_target = target.resolve(strict=False)
            if not resolved_target.is_relative_to(root):
                raise RuntimeError(f"archive path escapes extraction root: {member.name}")
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue

            target.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                raise RuntimeError(f"archive file has no content: {member.name}")
            with source, target.open("xb") as destination:
                shutil.copyfileobj(source, destination)


def _prepare_destination(output_root: Path) -> tuple[Path, Path]:
    """Create and validate a non-symlinked destination below output_root."""
    parent = output_root
    for component in RUN_RELATIVE_PATH.parts[:-1]:
        parent = parent / component
        if parent.is_symlink():
            raise RuntimeError(f"destination ancestor is a symbolic link: {parent}")
        if parent.exists() and not parent.is_dir():
            raise RuntimeError(f"destination ancestor is not a directory: {parent}")

    parent.mkdir(parents=True, exist_ok=True)
    resolved_parent = parent.resolve(strict=True)
    if resolved_parent != parent or not resolved_parent.is_relative_to(output_root):
        raise RuntimeError("destination parent resolves outside the requested root")

    destination = resolved_parent / RUN_RELATIVE_PATH.name
    if destination.is_symlink():
        raise RuntimeError(f"destination is a symbolic link: {destination}")
    return resolved_parent, destination


def _verify_exact_inventory(run_path: Path, expected_files: set[str]) -> None:
    """Reject missing, extra or unsupported entries in a restored run."""
    if run_path.is_symlink():
        raise RuntimeError(f"run directory is a symbolic link: {run_path}")

    actual_files: set[str] = set()
    actual_directories: set[str] = set()
    unsupported: list[str] = []
    for path in run_path.rglob("*"):
        relative = path.relative_to(run_path).as_posix()
        if path.is_symlink():
            unsupported.append(relative)
        elif path.is_file():
            actual_files.add(relative)
        elif path.is_dir():
            actual_directories.add(relative)
        else:
            unsupported.append(relative)
    if unsupported:
        raise RuntimeError(f"run directory contains unsupported entries: {unsupported}")

    expected_directories: set[str] = set()
    for file_name in expected_files:
        file_path = PurePosixPath(file_name)
        if file_path.is_absolute() or ".." in file_path.parts:
            raise RuntimeError(f"released inventory contains unsafe path: {file_name}")
        expected_directories.update(
            parent.as_posix() for parent in file_path.parents if parent != PurePosixPath(".")
        )

    if actual_files != expected_files:
        differences = sorted(actual_files ^ expected_files)
        raise RuntimeError(f"run directory has missing or extra files: {differences}")
    if actual_directories != expected_directories:
        differences = sorted(actual_directories ^ expected_directories)
        raise RuntimeError(f"run directory has missing or extra directories: {differences}")


def _verify_run(project_root: Path, run_path: Path) -> None:
    """Verify exact release lineage and the clone's live frozen-input scope."""
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from scripts.render_confirmatory import verify_frozen_run
    from src.pipelines.confirmatory import (
        relevant_input_files,
        verify_protocol_freeze,
        verify_run_inputs_unchanged,
    )

    if sha256_file(run_path / "manifest.json") != MANIFEST_FILE_SHA256:
        raise RuntimeError("manifest file differs from the released checkpoint")
    if sha256_file(run_path / "completion.json") != COMPLETION_FILE_SHA256:
        raise RuntimeError("completion file differs from the released checkpoint")

    run = verify_frozen_run(run_path)
    if run.mode != "confirmatory":
        raise RuntimeError(f"expected confirmatory evidence, found {run.mode!r}")
    if run.manifest.get("manifest_content_sha256") != MANIFEST_CONTENT_SHA256:
        raise RuntimeError("manifest hash differs from the released checkpoint")
    if run.completion.get("completion_content_sha256") != COMPLETION_CONTENT_SHA256:
        raise RuntimeError("completion hash differs from the released checkpoint")
    if len(run.cells) != 450:
        raise RuntimeError(f"expected 450 cells, found {len(run.cells)}")
    statuses = Counter(cell["status"] for _, cell in run.cells)
    if dict(statuses) != EXPECTED_STATUSES:
        raise RuntimeError(f"unexpected cell status counts: {dict(statuses)}")
    if run.inference.get("status") != "incomplete":
        raise RuntimeError("inference status differs from the recorded close-out")
    if run.inference.get("holm_family_complete") is not False:
        raise RuntimeError("Holm-family status differs from the recorded close-out")

    expected_files = set(run.source_hashes)
    _verify_exact_inventory(run_path, expected_files)

    run_config = run.manifest.get("run_config")
    if not isinstance(run_config, dict):
        raise RuntimeError("released manifest has no run configuration")
    datasets = tuple(str(value) for value in run_config.get("datasets", []))
    live_inputs = relevant_input_files(project_root, datasets)
    manifest_inputs = run.manifest.get("input_sha256")
    if not isinstance(manifest_inputs, dict):
        raise RuntimeError("released manifest has no input hash map")
    if set(live_inputs) != set(manifest_inputs):
        differences = sorted(set(live_inputs) ^ set(manifest_inputs))
        raise RuntimeError(f"live frozen-input scope differs from release: {differences}")
    verify_run_inputs_unchanged(
        project_root,
        manifest_inputs,
        live_inputs,
        label="released run manifest",
    )
    freeze = verify_protocol_freeze(project_root, live_inputs)
    if freeze.get("frozen_input_sha256") != manifest_inputs:
        raise RuntimeError("released manifest inputs differ from protocol freeze")
    if run.manifest.get("protocol_freeze_sha256") != freeze.get("freeze_content_sha256"):
        raise RuntimeError("released run points to a different protocol freeze")

    print("Frozen confirmatory evidence verified.")
    print(f"run={run_path.resolve()}")
    print("cells=450 complete=430 failed_diagnostics=20")
    print(f"completion_content_sha256={COMPLETION_CONTENT_SHA256}")
    print(f"frozen_inputs={len(live_inputs)} unchanged")


def _verify_checksum(checksum_path: Path, archive_path: Path) -> None:
    """Verify both the released checksum record and the pinned digest."""
    lines = checksum_path.read_text(encoding="utf-8").splitlines()
    if len(lines) != 1:
        raise RuntimeError("checksum asset must contain exactly one record")
    fields = lines[0].split()
    if len(fields) != 2 or fields[1].lstrip("*") != ARCHIVE_NAME:
        raise RuntimeError("checksum asset names an unexpected archive")
    observed = sha256_file(archive_path)
    if fields[0] != observed or observed != ARCHIVE_SHA256:
        raise RuntimeError("archive SHA-256 differs from the released checkpoint")
    print(f"{ARCHIVE_NAME}: OK")


def restore(project_root: Path, output_root: Path) -> Path:
    """Restore the release below output_root, or verify an existing copy."""
    project_root = project_root.resolve(strict=True)
    output_root = output_root.resolve(strict=True)
    destination_parent, destination = _prepare_destination(output_root)

    if destination.is_dir():
        print("Existing result directory found; verifying without overwriting it.")
        _verify_run(project_root, destination)
        return destination
    if destination.exists():
        raise RuntimeError(f"destination exists but is not a directory: {destination}")
    if shutil.which("gh") is None:
        raise RuntimeError("GitHub CLI is required to restore the private release")
    subprocess.run(
        ["gh", "auth", "status", "--hostname", "github.com"],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    with tempfile.TemporaryDirectory(
        prefix=".confirmatory-restore-", dir=destination_parent
    ) as temporary_name:
        temporary_dir = Path(temporary_name)
        print(f"Downloading private release {RELEASE_TAG}...")
        subprocess.run(
            [
                "gh",
                "release",
                "download",
                RELEASE_TAG,
                "--repo",
                RELEASE_REPOSITORY,
                "--dir",
                str(temporary_dir),
                "--pattern",
                f"{ARCHIVE_NAME}*",
            ],
            check=True,
        )
        archive_path = temporary_dir / ARCHIVE_NAME
        checksum_path = temporary_dir / CHECKSUM_NAME
        downloaded = {path.name for path in temporary_dir.iterdir() if path.is_file()}
        if downloaded != {ARCHIVE_NAME, CHECKSUM_NAME}:
            raise RuntimeError(f"release supplied unexpected assets: {sorted(downloaded)}")
        _verify_checksum(checksum_path, archive_path)

        extraction_root = temporary_dir / "extracted"
        _safe_extract(archive_path, extraction_root)
        staged_run = extraction_root / RUN_RELATIVE_PATH
        _verify_run(project_root, staged_run)
        checked_parent, checked_destination = _prepare_destination(output_root)
        if checked_parent != destination_parent or checked_destination != destination:
            raise RuntimeError("destination changed during restoration")
        if checked_destination.exists():
            raise RuntimeError("destination appeared during restoration")
        staged_run.replace(checked_destination)

    _verify_run(project_root, destination)
    print(f"Restoration complete: {destination}")
    return destination


def parse_args() -> argparse.Namespace:
    """Parse command-line options."""
    parser = argparse.ArgumentParser(
        description=(
            "Download, checksum, safely extract and verify the frozen "
            "confirmatory release. Existing runs are verified, never overwritten."
        )
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        help="existing root beneath which reports/confirmatory will be restored",
    )
    return parser.parse_args()


def main() -> int:
    """Run the fail-closed restore workflow."""
    args = parse_args()
    project_root = Path(__file__).resolve().parents[1]
    output_root = args.output_root or project_root
    try:
        restore(project_root, output_root)
    except (OSError, RuntimeError, subprocess.CalledProcessError, tarfile.TarError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
