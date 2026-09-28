#!/usr/bin/env python3
"""Verify a sharded package and restore its tree into a new directory."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tarfile
import tempfile
from pathlib import Path

from archive_common import (
    BUFFER_SIZE,
    EMPTY_SHA256,
    MAX_SHARD_BYTES,
    ArchiveError,
    atomic_new_directory,
    canonical_bytes,
    validate_relative_path,
)

HEX_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
SHARD_NAME = re.compile(r"part-[0-9]{6}\.tar\.gz\Z")


class LimitedReader:
    """Cap inflated tar bytes before tarfile can parse oversized PAX records."""

    def __init__(self, stream, maximum: int):
        """Wrap ``stream`` and allow at most ``maximum`` bytes to be read from it."""
        self.stream = stream
        self.maximum = maximum
        self.count = 0

    def read(self, length: int = -1) -> bytes:
        """Read from the stream, raising ``ArchiveError`` once the byte allowance is exceeded."""
        remaining = self.maximum - self.count
        if length < 0 or length > remaining + 1:
            length = remaining + 1
        if length <= 0:
            raise ArchiveError("Expanded tar exceeds declared member budget")
        chunk = self.stream.read(length)
        self.count += len(chunk)
        if self.count > self.maximum:
            raise ArchiveError("Expanded tar exceeds declared member budget")
        return chunk


def expanded_tar_budget(members: list[dict]) -> int:
    # Size is declared and checked per member. The allowance covers tar/PAX
    # headers, even for long UTF-8 path names, plus the final 10 KiB record.
    """Return the largest plausible uncompressed tar size for these members.

    This caps decompression, so a corrupted or malicious shard cannot expand
    without limit: file data rounded up to 512-byte tar blocks, a generous
    allowance for headers and long path names, and the final 10 KiB tar record.
    """
    return 10240 + sum(
        ((member["size"] + 511) // 512) * 512
        + 8192 + 2 * len(member["path"].encode("utf-8"))
        for member in members
    )


def unique_object(pairs):
    """JSON object hook that rejects duplicate keys instead of silently keeping the last one."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ArchiveError(f"Duplicate inventory JSON key: {key}")
        result[key] = value
    return result


def expect_keys(value, keys, label):
    """Raise ``ArchiveError`` unless ``value`` is a dict with exactly the keys ``keys``."""
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ArchiveError(f"Invalid {label} fields")


def valid_hash(value):
    """Return True if ``value`` is a 64-character lowercase hexadecimal SHA-256 string."""
    return isinstance(value, str) and HEX_SHA256.fullmatch(value) is not None


def load_inventory(package_dir: Path) -> dict:
    """Read ``inventory.json`` and check its structure and canonical hash.

    Rejects duplicate keys, non-finite numbers, unexpected fields, an
    unsupported format version, unsafe member paths and a canonical SHA-256
    that does not match the content.

    Raises:
        ArchiveError: The inventory is missing, malformed or inconsistent.
    """
    path = package_dir / "inventory.json"
    if path.is_symlink() or not path.is_file():
        raise ArchiveError("Missing or symlinked inventory.json")
    with path.open("r", encoding="utf-8") as stream:
        inventory = json.load(
            stream, object_pairs_hook=unique_object,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ArchiveError(f"Non-finite JSON value: {value}")
            ),
        )
    expect_keys(
        inventory,
        {"version", "format", "max_shard_bytes", "members", "shards", "canonical_sha256"},
        "inventory",
    )
    claimed = inventory["canonical_sha256"]
    base = {k: v for k, v in inventory.items() if k != "canonical_sha256"}
    try:
        actual_canonical = hashlib.sha256(canonical_bytes(base)).hexdigest()
    except (TypeError, ValueError, UnicodeError) as error:
        raise ArchiveError("Invalid inventory JSON values") from error
    if not valid_hash(claimed) or actual_canonical != claimed:
        raise ArchiveError("Inventory canonical SHA256 mismatch")
    if type(inventory["version"]) is not int or inventory["version"] != 1 or inventory["format"] != "deterministic-tar-gzip-shards":
        raise ArchiveError("Unsupported inventory version/format")
    cap = inventory["max_shard_bytes"]
    if type(cap) is not int or not 1024 <= cap <= MAX_SHARD_BYTES:
        raise ArchiveError("Invalid compressed shard cap")
    shards = inventory["shards"]
    members = inventory["members"]
    if not isinstance(shards, list) or not isinstance(members, list):
        raise ArchiveError("Invalid inventory arrays")
    names = []
    for index, shard in enumerate(shards, 1):
        expect_keys(shard, {"name", "bytes", "sha256", "member_count"}, "shard")
        name = shard["name"]
        if (
            not isinstance(name, str) or not SHARD_NAME.fullmatch(name)
            or name != f"part-{index:06d}.tar.gz"
        ):
            raise ArchiveError("Unsorted or unsafe shard names")
        if type(shard["bytes"]) is not int or not 0 < shard["bytes"] <= cap:
            raise ArchiveError(f"Invalid shard byte count: {name}")
        if type(shard["member_count"]) is not int or shard["member_count"] < 1:
            raise ArchiveError(f"Invalid shard member count: {name}")
        if not valid_hash(shard["sha256"]):
            raise ArchiveError(f"Invalid shard hash: {name}")
        names.append(name)
    if len(names) != len(set(names)):
        raise ArchiveError("Duplicate shard name")
    if members and not shards:
        raise ArchiveError("Members without shards")
    prior = None
    seen = set()
    counts = {name: 0 for name in names}
    dir_paths = set()
    for member in members:
        expect_keys(member, {"path", "type", "size", "sha256", "shard"}, "member")
        path = member["path"]
        validate_relative_path(path)
        if path in seen or (prior is not None and path <= prior):
            raise ArchiveError(f"Duplicate or unsorted member: {path}")
        seen.add(path)
        prior = path
        kind = member["type"]
        if not isinstance(kind, str) or kind not in {"file", "dir"}:
            raise ArchiveError(f"Invalid member type: {path}")
        if type(member["size"]) is not int or member["size"] < 0:
            raise ArchiveError(f"Invalid member size: {path}")
        if not valid_hash(member["sha256"]):
            raise ArchiveError(f"Invalid member hash: {path}")
        if kind == "dir":
            if member["size"] != 0 or member["sha256"] != EMPTY_SHA256:
                raise ArchiveError(f"Invalid directory metadata: {path}")
            dir_paths.add(path)
        assigned = member["shard"]
        if not isinstance(assigned, str) or assigned not in counts:
            raise ArchiveError(f"Unknown shard assignment: {path}")
        counts[assigned] += 1
    for member in members:
        pieces = validate_relative_path(member["path"])
        for end in range(1, len(pieces)):
            parent = "/".join(pieces[:end])
            if parent not in dir_paths:
                raise ArchiveError(f"Missing parent directory: {member['path']}")
    if any(shard["member_count"] != counts[shard["name"]] for shard in shards):
        raise ArchiveError("Shard member counts do not match inventory")
    package_names = {entry.name for entry in package_dir.iterdir()}
    if package_names != set(names) | {"inventory.json"}:
        raise ArchiveError("Unexpected or missing files in package directory")
    return inventory


def verify_and_restore(
    package_dir: Path, destination: Path, expected_sha256: str | None = None,
) -> dict:
    """Verify every shard of a package and restore its tree into a new ``destination``.

    Each shard is copied to scratch space while its size and SHA-256 are checked
    against the inventory. It is then read member by member in the recorded
    order: every path is checked for safety, every header for the fixed metadata
    written by ``package.py``, and every extracted file's size and SHA-256
    against the inventory. The accepted tree is published atomically after
    verification. The final cleanup removes temporary extraction and scratch
    directories.

    Args:
        package_dir: Directory holding ``inventory.json`` and the shards.
        destination: New directory to create; must not exist.
        expected_sha256: Optional inventory hash received through a separate
            trusted channel; it must match.

    Returns:
        The verified inventory.

    Raises:
        ArchiveError: Any integrity, safety or consistency check fails.
    """
    package_dir = package_dir.absolute()
    destination = destination.absolute()
    if package_dir.is_symlink() or not package_dir.is_dir():
        raise ArchiveError("Package source is not a real directory")
    if destination.exists() or destination.is_symlink():
        raise ArchiveError(f"Refusing to overwrite destination: {destination}")
    if os.path.commonpath((package_dir.resolve(), destination.resolve())) == str(package_dir.resolve()):
        raise ArchiveError("Restore destination cannot be inside package directory")
    inventory = load_inventory(package_dir)
    if expected_sha256 is not None and (
        not valid_hash(expected_sha256)
        or inventory["canonical_sha256"] != expected_sha256
    ):
        raise ArchiveError("Trusted expected inventory SHA256 mismatch")
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".restore-stage-", dir=destination.parent))
    scratch = Path(tempfile.mkdtemp(prefix=".verified-shards-", dir=destination.parent))
    try:
        expected_by_shard = {
            shard["name"]: [
                member for member in inventory["members"]
                if member["shard"] == shard["name"]
            ] for shard in inventory["shards"]
        }
        for shard in inventory["shards"]:
            asset = package_dir / shard["name"]
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
            fd = os.open(asset, flags)
            copied = scratch / shard["name"]
            digest = hashlib.sha256()
            copied_bytes = 0
            with os.fdopen(fd, "rb") as source, copied.open("wb") as copy:
                if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                    raise ArchiveError(f"Non-regular shard: {shard['name']}")
                while chunk := source.read(BUFFER_SIZE):
                    copied_bytes += len(chunk)
                    if copied_bytes > shard["bytes"]:
                        raise ArchiveError(f"Shard size mismatch: {shard['name']}")
                    digest.update(chunk)
                    copy.write(chunk)
            if copied_bytes != shard["bytes"] or digest.hexdigest() != shard["sha256"]:
                raise ArchiveError(f"Shard SHA256 or size mismatch: {shard['name']}")
            expected = expected_by_shard[shard["name"]]
            with copied.open("rb") as encoded, gzip.GzipFile(fileobj=encoded, mode="rb") as expanded, tarfile.open(
                fileobj=LimitedReader(expanded, expanded_tar_budget(expected)), mode="r|"
            ) as archive:
                for member in expected:
                    info = archive.next()
                    if info is None:
                        raise ArchiveError(f"Missing tar member: {shard['name']}")
                    raw_name = info.name
                    if raw_name.endswith("//"):
                        raise ArchiveError(f"Unsafe tar path: {raw_name}")
                    name = raw_name[:-1] if raw_name.endswith("/") else raw_name
                    validate_relative_path(name)
                    if name != member["path"]:
                        raise ArchiveError(f"Tar member order/name mismatch: {shard['name']}")
                    if info.uid != 0 or info.gid != 0 or info.mtime != 0 or (
                        info.uname or info.gname
                    ):
                        raise ArchiveError(f"Nonzero tar identity/time: {name}")
                    kind = member["type"]
                    if kind == "file" and raw_name != name:
                        raise ArchiveError(f"Noncanonical tar file name: {raw_name}")
                    if kind == "dir":
                        if info.type != tarfile.DIRTYPE or info.size != 0 or info.mode != 0o755:
                            raise ArchiveError(f"Invalid tar directory: {name}")
                    elif info.type != tarfile.REGTYPE or info.size != member["size"] or info.mode != 0o644:
                        raise ArchiveError(f"Invalid tar file: {name}")
                    target = stage.joinpath(*validate_relative_path(name))
                    if kind == "dir":
                        if target.exists() or target.is_symlink():
                            raise ArchiveError(f"Duplicate extraction target: {name}")
                        target.mkdir()
                        target.chmod(0o755)
                        continue
                    parent = target.parent
                    if not parent.is_dir() or parent.is_symlink():
                        raise ArchiveError(f"Unsafe extraction parent: {name}")
                    source_stream = archive.extractfile(info)
                    if source_stream is None:
                        raise ArchiveError(f"Unreadable tar member: {name}")
                    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
                    fd = os.open(target, flags, 0o600)
                    digest = hashlib.sha256()
                    count = 0
                    with source_stream, os.fdopen(fd, "wb") as output:
                        while chunk := source_stream.read(BUFFER_SIZE):
                            count += len(chunk)
                            if count > member["size"]:
                                raise ArchiveError(f"Expanded member too large: {name}")
                            digest.update(chunk)
                            output.write(chunk)
                    if count != member["size"] or digest.hexdigest() != member["sha256"]:
                        raise ArchiveError(f"Extracted member SHA256 mismatch: {name}")
                    target.chmod(0o644)
                if archive.next() is not None:
                    raise ArchiveError(f"Extra tar member: {shard['name']}")
                # Tar EOF can precede the gzip trailer. The writer leaves only
                # zero padding to the 10 KiB tar record; drain to verify CRC/ISIZE.
                tail_bytes = 0
                while chunk := archive.fileobj.read(10241 - tail_bytes):
                    tail_bytes += len(chunk)
                    if tail_bytes > 10240 or any(chunk):
                        raise ArchiveError(f"Invalid tar tail: {shard['name']}")
            copied.unlink()
        atomic_new_directory(stage, destination)
        return inventory
    finally:
        shutil.rmtree(stage, ignore_errors=True)
        shutil.rmtree(scratch, ignore_errors=True)


def main() -> int:
    """Command-line entry point: verify and restore a package and print a JSON summary; return 0 on success, 1 on failure."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path, help="Directory containing inventory and shards")
    parser.add_argument("destination", type=Path, help="New restore directory")
    parser.add_argument(
        "--expected-sha256", help="Inventory digest copied via a separate trusted channel",
    )
    args = parser.parse_args()
    try:
        inventory = verify_and_restore(
            args.package, args.destination, args.expected_sha256
        )
        print(json.dumps({
            "restored": str(args.destination.absolute()),
            "canonical_sha256": inventory["canonical_sha256"],
            "shards": len(inventory["shards"]),
            "members": len(inventory["members"]),
        }, sort_keys=True))
        return 0
    except (ArchiveError, OSError, tarfile.TarError, json.JSONDecodeError) as error:
        print(f"verify failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
