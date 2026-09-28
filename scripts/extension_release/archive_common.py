"""Common format and safety rules for deterministic sharded archives."""
from __future__ import annotations

import ctypes
import errno
import hashlib
import json
import os
import stat
import sys
from pathlib import Path
from typing import Any

MAX_SHARD_BYTES = 500 * 1024 * 1024
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
BUFFER_SIZE = 1024 * 1024
WINDOWS_DEVICES = {"CON", "PRN", "AUX", "NUL"} | {
    f"{prefix}{number}" for prefix in ("COM", "LPT") for number in range(1, 10)
}
WINDOWS_FORBIDDEN = set('<>:"|?*')


class ArchiveError(Exception):
    """A package or source violates the archive contract."""


def canonical_bytes(value: Any) -> bytes:
    """Encode a value as compact, key-sorted UTF-8 JSON for stable hashing."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_file(path: Path) -> str:
    """Return the SHA-256 hex digest of a file, read in 1 MiB chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(BUFFER_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def validate_relative_path(name: str) -> tuple[str, ...]:
    """Check that an archive member path is safe to extract on macOS, Linux and Windows.

    Rejects absolute paths, backslashes, NUL bytes, empty, ``.`` and ``..``
    components, trailing dots or spaces, control and Windows-forbidden
    characters, and reserved Windows device names such as ``CON`` or ``COM1``.

    Returns:
        The path split into its ``/``-separated components.

    Raises:
        ArchiveError: The path is unsafe or not valid UTF-8.
    """
    if not isinstance(name, str) or not name or name.startswith("/"):
        raise ArchiveError(f"Unsafe archive path: {name!r}")
    if "\\" in name or "\x00" in name:
        raise ArchiveError(f"Unsafe archive path: {name!r}")
    try:
        name.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ArchiveError(f"Non-UTF-8 archive path: {name!r}") from error
    pieces = tuple(name.split("/"))
    for piece in pieces:
        if (
            piece in {"", ".", ".."} or piece.endswith((".", " "))
            or any(char in WINDOWS_FORBIDDEN or ord(char) < 32 for char in piece)
            or piece.split(".", 1)[0].rstrip(" ").upper() in WINDOWS_DEVICES
        ):
            raise ArchiveError(f"Unsafe archive path: {name!r}")
    return pieces


def stat_signature(info: os.stat_result) -> tuple[int, int, int, int, int]:
    """Return the fields (device, inode, size, modification and change times) used to detect that a file changed or was replaced."""
    return (
        info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns,
        info.st_ctime_ns,
    )


def checked_file(path: Path, expected_signature: tuple[int, ...]) -> int:
    """Open a regular file without following links, and confirm it is still the file that was listed.

    Returns:
        An open read-only file descriptor; the caller must close it.

    Raises:
        ArchiveError: The entry is not a regular file, or its signature changed
            since it was listed.
    """
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise ArchiveError(f"Non-regular source file: {path}")
        if stat_signature(info) != expected_signature:
            raise ArchiveError(f"Source changed before streaming: {path}")
        if stat_signature(path.lstat()) != expected_signature:
            raise ArchiveError(f"Source path replaced: {path}")
        return fd
    except Exception:
        os.close(fd)
        raise


def source_snapshot(root: Path) -> list[dict[str, Any]]:
    """List and hash a source without following links. Includes empty dirs."""
    if root.is_symlink() or not stat.S_ISDIR(root.lstat().st_mode):
        raise ArchiveError(f"Source is not a real directory: {root}")
    members: list[dict[str, Any]] = []
    seen: set[str] = set()

    def walk(directory: Path) -> None:
        """Recursively record every entry under ``directory`` in name order, hashing regular files."""
        with os.scandir(directory) as scanner:
            entries = sorted(scanner, key=lambda entry: entry.name)
        for entry in entries:
            path = Path(entry.path)
            rel = path.relative_to(root).as_posix()
            validate_relative_path(rel)
            if rel in seen:
                raise ArchiveError(f"Duplicate source path: {rel}")
            seen.add(rel)
            info = path.lstat()
            signature = stat_signature(info)
            if stat.S_ISLNK(info.st_mode):
                raise ArchiveError(f"Symlink in source: {rel}")
            if stat.S_ISDIR(info.st_mode):
                members.append({
                    "path": rel, "type": "dir", "size": 0,
                    "sha256": EMPTY_SHA256, "_signature": signature,
                })
                walk(path)
                if stat_signature(path.lstat()) != signature:
                    raise ArchiveError(f"Source directory changed: {rel}")
            elif stat.S_ISREG(info.st_mode):
                fd = checked_file(path, signature)
                digest = hashlib.sha256()
                size = 0
                with os.fdopen(fd, "rb") as stream:
                    while chunk := stream.read(BUFFER_SIZE):
                        digest.update(chunk)
                        size += len(chunk)
                    if stat_signature(os.fstat(stream.fileno())) != signature:
                        raise ArchiveError(f"Source changed during hashing: {rel}")
                if size != info.st_size or stat_signature(path.lstat()) != signature:
                    raise ArchiveError(f"Source changed during hashing: {rel}")
                members.append({
                    "path": rel, "type": "file", "size": size,
                    "sha256": digest.hexdigest(), "_signature": signature,
                })
            else:
                raise ArchiveError(f"Unsupported source entry: {rel}")

    walk(root)
    members.sort(key=lambda m: m["path"])
    return members


def public_member(member: dict[str, Any], shard: str) -> dict[str, Any]:
    """Return the member fields written to the package inventory, dropping the private stat signature."""
    return {
        "path": member["path"], "type": member["type"],
        "size": member["size"], "sha256": member["sha256"],
        "shard": shard,
    }


def assert_source_unchanged(
    original: list[dict[str, Any]], current: list[dict[str, Any]],
) -> None:
    """Raise ``ArchiveError`` if a second snapshot of the source differs from the first."""
    if original != current:
        raise ArchiveError("Source tree changed during packaging")


def atomic_new_directory(stage: Path, destination: Path) -> None:
    """Publish a verified directory atomically without replacing any target."""
    if destination.exists() or destination.is_symlink():
        raise ArchiveError(f"Refusing to overwrite destination: {destination}")
    if sys.platform == "darwin":
        # sys/stdio.h: RENAME_EXCL = 0x00000004.
        libc = ctypes.CDLL(None, use_errno=True)
        rename = libc.renamex_np
        rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        status = rename(os.fsencode(stage), os.fsencode(destination), 0x4)
    elif sys.platform.startswith("linux"):
        # linux/fs.h: RENAME_NOREPLACE = 1; AT_FDCWD = -100.
        libc = ctypes.CDLL(None, use_errno=True)
        try:
            rename = libc.renameat2
        except AttributeError as error:
            raise ArchiveError("Atomic no-replace rename unavailable on Linux") from error
        rename.argtypes = [
            ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p,
            ctypes.c_uint,
        ]
        rename.restype = ctypes.c_int
        status = rename(-100, os.fsencode(stage), -100, os.fsencode(destination), 1)
    elif os.name == "nt":
        # Windows os.rename raises FileExistsError for an existing destination.
        os.rename(stage, destination)
        return
    else:
        raise ArchiveError(f"Atomic no-replace rename unsupported on {sys.platform}")
    if status != 0:
        error_code = ctypes.get_errno()
        if error_code == errno.EEXIST:
            raise ArchiveError(f"Refusing to overwrite destination: {destination}")
        raise OSError(error_code, os.strerror(error_code), str(destination))
