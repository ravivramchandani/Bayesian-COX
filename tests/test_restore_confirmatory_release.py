"""Adversarial tests for the confirmatory-release restoration boundary.

Covers the private helpers of ``scripts/restore_confirmatory_release.py``, which
restores the frozen 450-cell confirmatory run from its pinned private release
archive. Small hand-built archives and directories check that extraction admits
only regular files and directories under the exact run prefix, that the
destination has no symbolic-link ancestor, that the restored inventory is exact,
and that the checksum record matches the pinned digest.
"""

from __future__ import annotations

import hashlib
import io
import tarfile
from pathlib import Path

import pytest

from scripts import restore_confirmatory_release as restore


def _write_archive(
    path: Path,
    members: list[tuple[str, bytes, bytes | None]],
) -> None:
    """Write a small gzip-compressed tar fixture.

    Each tuple contains the member name, tar type, and optional regular-file
    payload. Link and device metadata are populated when their types require it.
    """
    with tarfile.open(path, mode="w:gz") as archive:
        for name, member_type, payload in members:
            member = tarfile.TarInfo(name)
            member.type = member_type
            if member_type in {tarfile.SYMTYPE, tarfile.LNKTYPE}:
                member.linkname = "target"
            if member_type in {tarfile.CHRTYPE, tarfile.BLKTYPE}:
                member.devmajor = 1
                member.devminor = 3
            if member_type == tarfile.REGTYPE:
                content = payload or b""
                member.size = len(content)
                archive.addfile(member, io.BytesIO(content))
            else:
                archive.addfile(member)


def test_safe_extract_accepts_exact_prefix_directories_and_regular_files(
    tmp_path: Path,
) -> None:
    """Directories and regular files under the exact run prefix are extracted intact."""
    prefix = restore.RUN_ARCHIVE_PREFIX.as_posix()
    archive_path = tmp_path / "release.tar.gz"
    _write_archive(
        archive_path,
        [
            (prefix, tarfile.DIRTYPE, None),
            (f"{prefix}/nested", tarfile.DIRTYPE, None),
            (f"{prefix}/nested/result.json", tarfile.REGTYPE, b'{"ok": true}\n'),
        ],
    )

    extraction_root = tmp_path / "extracted"
    restore._safe_extract(archive_path, extraction_root)

    assert (
        extraction_root / Path(prefix) / "nested" / "result.json"
    ).read_bytes() == b'{"ok": true}\n'


@pytest.mark.parametrize(
    ("member_name", "message"),
    [
        (
            f"/{restore.RUN_ARCHIVE_PREFIX.as_posix()}/result.json",
            "unsafe archive path",
        ),
        (
            f"{restore.RUN_ARCHIVE_PREFIX.as_posix()}/../escape.json",
            "unsafe archive path",
        ),
        (
            "reports/confirmatory/a-different-run/result.json",
            "unexpected archive path",
        ),
    ],
    ids=["absolute", "traversal", "unexpected-prefix"],
)
def test_safe_extract_rejects_paths_outside_exact_prefix(
    tmp_path: Path,
    member_name: str,
    message: str,
) -> None:
    """Absolute, traversing or differently prefixed member paths are rejected."""
    archive_path = tmp_path / "unsafe-path.tar.gz"
    _write_archive(
        archive_path,
        [(member_name, tarfile.REGTYPE, b"untrusted")],
    )

    with pytest.raises(RuntimeError, match=message):
        restore._safe_extract(archive_path, tmp_path / "extracted")


def test_safe_extract_rejects_duplicate_member_names(tmp_path: Path) -> None:
    """An archive that repeats a member name is rejected."""
    member_name = f"{restore.RUN_ARCHIVE_PREFIX.as_posix()}/result.json"
    archive_path = tmp_path / "duplicate.tar.gz"
    _write_archive(
        archive_path,
        [
            (member_name, tarfile.REGTYPE, b"first"),
            (member_name, tarfile.REGTYPE, b"second"),
        ],
    )

    with pytest.raises(RuntimeError, match="duplicate archive path"):
        restore._safe_extract(archive_path, tmp_path / "extracted")


@pytest.mark.parametrize(
    "member_type",
    [
        tarfile.SYMTYPE,
        tarfile.LNKTYPE,
        tarfile.FIFOTYPE,
        tarfile.CHRTYPE,
        tarfile.BLKTYPE,
    ],
    ids=["symlink", "hardlink", "fifo", "character-device", "block-device"],
)
def test_safe_extract_rejects_non_regular_member_types(
    tmp_path: Path,
    member_type: bytes,
) -> None:
    """Symbolic links, hard links, named pipes (FIFOs) and device members are rejected."""
    member_name = f"{restore.RUN_ARCHIVE_PREFIX.as_posix()}/untrusted"
    archive_path = tmp_path / "unsupported-type.tar.gz"
    _write_archive(archive_path, [(member_name, member_type, None)])

    with pytest.raises(RuntimeError, match="unsupported archive member type"):
        restore._safe_extract(archive_path, tmp_path / "extracted")


def test_prepare_destination_creates_exact_parent_below_output_root(
    tmp_path: Path,
) -> None:
    """The destination's parent is created at reports/confirmatory under the output root."""
    parent, destination = restore._prepare_destination(tmp_path)

    assert parent == tmp_path / "reports" / "confirmatory"
    assert parent.is_dir()
    assert destination == tmp_path / restore.RUN_RELATIVE_PATH


def test_prepare_destination_rejects_symlinked_ancestor(tmp_path: Path) -> None:
    """A symbolic link among the destination's ancestors is rejected."""
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "reports").symlink_to(outside, target_is_directory=True)

    with pytest.raises(RuntimeError, match="ancestor is a symbolic link"):
        restore._prepare_destination(tmp_path)


def test_prepare_destination_rejects_symlinked_run_directory(
    tmp_path: Path,
) -> None:
    """A symbolic link in place of the run directory itself is rejected."""
    parent = tmp_path / "reports" / "confirmatory"
    parent.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (parent / restore.RUN_RELATIVE_PATH.name).symlink_to(
        outside,
        target_is_directory=True,
    )

    with pytest.raises(RuntimeError, match="destination is a symbolic link"):
        restore._prepare_destination(tmp_path)


def test_verify_exact_inventory_accepts_only_implied_directories(
    tmp_path: Path,
) -> None:
    """An inventory passes when its only directories are parents of expected files."""
    run_path = tmp_path / "run"
    (run_path / "cells").mkdir(parents=True)
    (run_path / "manifest.json").write_text("{}\n", encoding="utf-8")
    (run_path / "cells" / "cell.json").write_text("{}\n", encoding="utf-8")

    restore._verify_exact_inventory(
        run_path,
        {"manifest.json", "cells/cell.json"},
    )


def test_verify_exact_inventory_rejects_extra_empty_directory(
    tmp_path: Path,
) -> None:
    """An empty directory that no expected file implies makes the inventory fail."""
    run_path = tmp_path / "run"
    run_path.mkdir()
    (run_path / "manifest.json").write_text("{}\n", encoding="utf-8")
    (run_path / "unexpected").mkdir()

    with pytest.raises(RuntimeError, match="missing or extra directories"):
        restore._verify_exact_inventory(run_path, {"manifest.json"})


def _checksum_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, Path, str]:
    """Write a stand-in archive and pin the module's expected name and digest to it.

    Returns:
        The checksum-record path (not yet written), the archive path and the
        archive's SHA-256 digest.
    """
    archive_name = "release.tar.gz"
    archive_path = tmp_path / archive_name
    archive_path.write_bytes(b"immutable release bytes")
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    monkeypatch.setattr(restore, "ARCHIVE_NAME", archive_name)
    monkeypatch.setattr(restore, "ARCHIVE_SHA256", digest)
    return tmp_path / "release.tar.gz.sha256", archive_path, digest


def test_verify_checksum_accepts_matching_record_and_pinned_digest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One record naming the archive with its pinned digest is accepted."""
    checksum_path, archive_path, digest = _checksum_fixture(tmp_path, monkeypatch)
    checksum_path.write_text(f"{digest}  {archive_path.name}\n", encoding="utf-8")

    restore._verify_checksum(checksum_path, archive_path)


@pytest.mark.parametrize(
    "record",
    [
        "{digest}  release.tar.gz\n{digest}  release-copy.tar.gz\n",
        "{digest}  unexpected.tar.gz\n",
        "{wrong_digest}  release.tar.gz\n",
    ],
    ids=["multiple-records", "unexpected-name", "record-digest-mismatch"],
)
def test_verify_checksum_rejects_invalid_checksum_records(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    record: str,
) -> None:
    """Multiple records, a wrong archive name or a wrong recorded digest are rejected."""
    checksum_path, archive_path, digest = _checksum_fixture(tmp_path, monkeypatch)
    checksum_path.write_text(
        record.format(digest=digest, wrong_digest="0" * 64),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError):
        restore._verify_checksum(checksum_path, archive_path)


def test_verify_checksum_rejects_digest_that_differs_from_pinned_release(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A self-consistent record is still rejected when the pinned release digest differs."""
    checksum_path, archive_path, digest = _checksum_fixture(tmp_path, monkeypatch)
    checksum_path.write_text(f"{digest}  {archive_path.name}\n", encoding="utf-8")
    monkeypatch.setattr(restore, "ARCHIVE_SHA256", "f" * 64)

    with pytest.raises(RuntimeError, match="differs from the released checkpoint"):
        restore._verify_checksum(checksum_path, archive_path)
