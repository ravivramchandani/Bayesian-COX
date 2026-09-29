"""Immutable byte bindings and atomic checkpoints for mixed verification."""

from __future__ import annotations

import hashlib
import json
import os
import socket
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class VerificationFailure(ValueError):
    """An exact source/input/outcome/scientific verification failed."""


def require(condition: bool, message: str) -> None:
    """Reject changed or incomplete evidence without fitting or repairing it."""
    if not condition:
        raise VerificationFailure(message)


def canonical(value: Any) -> str:
    """Use finite original canonical JSON; hashes alone do not prove science."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def safe(path: Path) -> Path:
    """Require explicit unlinked absolute paths, including every ancestor."""
    require(path.is_absolute() and ".." not in path.parts
            and not any(item.is_symlink() for item in (path, *path.parents)), "unsafe or linked path")
    return path


def child(root: Path, name: str) -> Path:
    """Resolve only a nonempty ordinary relative artifact below its bound root."""
    relative = Path(name)
    require(bool(name) and not relative.is_absolute() and ".." not in relative.parts,
            "unsafe relative artifact")
    path = safe(root / relative)
    require(path != root, "artifact must name a child")
    return path


def sha(path: Path) -> str:
    """Stream file bytes with bounded memory; used only during actual invocation."""
    safe(path)
    require(path.is_file(), "bound file missing")
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def seal(value: dict[str, Any]) -> dict[str, Any]:
    """Seal a new documentary record without changing its evidence scope."""
    require("content_sha256" not in value, "record already sealed")
    return {**value, "content_sha256": canonical(value)}


def read(path: Path, expected: str | None = None, *, field: str = "content_sha256") -> dict[str, Any]:
    """Bind complete JSON bytes and strict internal content before use."""
    before = sha(path)
    require(expected is None or before == expected, "record byte binding differs")

    def nonfinite(value: str) -> None:
        raise VerificationFailure("nonfinite JSON " + value)

    try:
        record = json.loads(path.read_text(encoding="utf-8"), parse_constant=nonfinite)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise VerificationFailure("invalid or partial JSON record") from error
    require(isinstance(record, dict) and record.get(field) == canonical(
        {key: value for key, value in record.items() if key != field}), "record content binding differs")
    require(sha(path) == before, "record changed during read")
    return record


def write_new(path: Path, value: dict[str, Any]) -> None:
    """Publish closed/fsynced JSON through a no-replace atomic hard link."""
    data = (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()
    write_bytes_new(path, data)


def write_bytes_new(path: Path, data: bytes) -> None:
    """Publish closed/fsynced bytes exclusively; preserve failed-publication residue."""
    safe(path)
    require(path.parent.is_dir() and not path.exists(), "new output with existing parent required")
    descriptor, name = tempfile.mkstemp(prefix=".verification-pending-" + path.name + "-", dir=path.parent)
    temporary = Path(name)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.link(temporary, path)
    temporary.unlink()
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    # Publication/cleanup/fsync errors propagate; residual evidence is retained.


class Pins:
    """Cache verified byte digests, and recheck all of them before certification."""

    def __init__(self) -> None:
        self.files: dict[Path, str] = {}

    def bind(self, path: Path, expected: str, *, size: int | None = None) -> Path:
        safe(path)
        require(size is None or path.stat().st_size == size, "artifact length binding differs")
        previous = self.files.get(path)
        require(previous is None or previous == expected, "one path has conflicting byte bindings")
        require(sha(path) == expected, "artifact byte binding differs")
        self.files[path] = expected
        return path

    def json(self, path: Path, expected: str, *, field: str = "content_sha256") -> dict[str, Any]:
        self.bind(path, expected)
        return read(path, expected, field=field)

    def artifacts(self, root: Path, records: dict[str, Any]) -> None:
        for name, binding in records.items():
            self.bind(child(root, name), binding["sha256"], size=binding["bytes"])

    def recheck(self) -> None:
        for path, expected in self.files.items():
            require(sha(path) == expected, "bound source/input/outcome changed during verification")


class Claim:
    """One exclusive actual verifier owner; stale claims require root recovery."""

    def __init__(self, path: Path, binding: str) -> None:
        self.path, self.binding, self.nonce = path, binding, uuid.uuid4().hex

    def __enter__(self) -> Claim:
        write_new(self.path, seal({"nonce": self.nonce, "binding_sha256": self.binding,
                                   "pid": os.getpid(), "host": socket.gethostname(),
                                   "started_at_utc": datetime.now(UTC).isoformat()}))
        return self

    def __exit__(self, *_arguments: Any) -> None:
        require(read(self.path)["nonce"] == self.nonce, "verifier claim ownership changed")
        self.path.unlink()


def checkpoint(path: Path, value: dict[str, Any]) -> None:
    """Resume only byte/content-equivalent finished scientific checkpoints."""
    record = seal(value)
    if path.exists():
        require(read(path) == record, "existing verified checkpoint differs")
    else:
        write_new(path, record)


def inventory(root: Path, expected: set[str], directories: set[str]) -> None:
    """Refuse residual/temp/linked files and unexpected empty output directories."""
    found_files, found_dirs = set(), set()
    for path in root.rglob("*"):
        safe(path)
        relative = str(path.relative_to(root))
        if path.is_file():
            found_files.add(relative)
        elif path.is_dir():
            found_dirs.add(relative)
        else:
            require(False, "unrecognized output node")
    require(found_files == expected and found_dirs == directories, "output inventory differs or is partial")
