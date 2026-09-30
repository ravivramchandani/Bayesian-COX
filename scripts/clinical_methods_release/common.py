"""Strict file, hash and Git helpers shared by focused-study release tools."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tarfile
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    """Hash an existing regular file, rejecting links."""
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"missing or linked file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    """Read a JSON object without duplicate keys or non-finite literals."""
    sha256_file(path)

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {path}: {key}")
            result[key] = value
        return result

    def nonfinite(value: str) -> None:
        raise ValueError(f"non-finite JSON literal: {path}: {value}")

    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique,
                       parse_constant=nonfinite)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def write_json_new(path: Path, value: dict[str, Any]) -> None:
    """Write a human-readable record without replacing an existing file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def copy_regular(source: Path, destination: Path) -> str:
    """Copy an unlinked file to a new path and require byte identity."""
    expected = sha256_file(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as output, source.open("rb") as input_stream:
        shutil.copyfileobj(input_stream, output, length=1024 * 1024)
    if sha256_file(destination) != expected:
        raise ValueError(f"copied file differs: {source}")
    return expected


def copy_directory(source: Path, destination: Path) -> dict[str, str]:
    """Copy a link-free tree, returning exact relative file hashes."""
    if source.is_symlink() or not source.is_dir() or destination.exists():
        raise ValueError(f"invalid copy directory: {source} -> {destination}")
    destination.mkdir(parents=True)
    hashes: dict[str, str] = {}
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if path.is_symlink():
            raise ValueError(f"linked source member: {path}")
        if path.is_dir():
            (destination / relative).mkdir()
        elif path.is_file():
            hashes[relative.as_posix()] = copy_regular(path, destination / relative)
        else:
            raise ValueError(f"unsupported source member: {path}")
    return hashes


def inventory(root: Path, *, exclude: frozenset[str] = frozenset()) -> dict[str, str]:
    """Hash every regular file in a tree and reject links or special members."""
    if root.is_symlink() or not root.is_dir():
        raise ValueError(f"missing or linked tree: {root}")
    files: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise ValueError(f"linked tree member: {path}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError(f"unsupported tree member: {path}")
        if relative not in exclude:
            files[relative] = sha256_file(path)
    return files


def clean_commit(root: Path) -> str:
    """Return HEAD of an exactly clean Git checkout."""
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).strip():
        raise ValueError(f"code checkout is dirty: {root}")
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()


def archive_commit(root: Path, destination: Path, expected_commit: str) -> str:
    """Archive a committed Git tree and verify its embedded source commit."""
    if clean_commit(root) != expected_commit:
        raise ValueError(f"code checkout differs from expected commit: {root}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(destination)
    subprocess.run(["git", "archive", "--format=tar.gz", f"--output={destination}",
                    expected_commit], cwd=root, check=True)
    with tarfile.open(destination, "r:gz") as archive:
        observed = archive.pax_headers.get("comment")
    if observed != expected_commit:
        raise ValueError(f"archive commit marker differs: {destination}")
    return sha256_file(destination)
