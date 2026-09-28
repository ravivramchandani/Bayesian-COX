#!/usr/bin/env python3
"""Build deterministic, integrity-checked tar.gz shards from a directory."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import shutil
import stat
import sys
import tarfile
import tempfile
from pathlib import Path

from archive_common import (
    MAX_SHARD_BYTES,
    ArchiveError,
    assert_source_unchanged,
    atomic_new_directory,
    canonical_bytes,
    checked_file,
    public_member,
    sha256_file,
    source_snapshot,
    stat_signature,
)

BUFFER_SIZE = 1024 * 1024


class HashingReader:
    """File-like wrapper that hashes and counts every byte read through it."""
    def __init__(self, stream):
        """Wrap ``stream`` with an empty SHA-256 digest and a zero byte count."""
        self.stream = stream
        self.digest = hashlib.sha256()
        self.count = 0

    def read(self, length: int = -1) -> bytes:
        """Read up to ``length`` bytes, updating the digest and count."""
        chunk = self.stream.read(length)
        self.digest.update(chunk)
        self.count += len(chunk)
        return chunk


def tar_info(member: dict) -> tarfile.TarInfo:
    """Build a tar header with fixed metadata so identical content gives identical archives.

    Modification time, owner and group are zeroed and permissions fixed (0o755
    for directories, 0o644 for files), which makes the shards byte-reproducible.
    """
    info = tarfile.TarInfo(member["path"])
    info.type = tarfile.DIRTYPE if member["type"] == "dir" else tarfile.REGTYPE
    info.size = member["size"]
    info.mode = 0o755 if member["type"] == "dir" else 0o644
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.pax_headers = {}
    return info


def write_archive(root: Path, members: list[dict], path: Path) -> None:
    """Write ``members`` of ``root`` to one gzip-compressed PAX tar at ``path``.

    Each source entry is re-checked against the signature recorded when it was
    listed, and each file's streamed bytes are hashed, so a file that changes
    during packaging is rejected instead of being archived silently.

    Raises:
        ArchiveError: A source entry changed or its bytes do not match the listing.
    """
    with path.open("wb") as output:
        with gzip.GzipFile(
            filename="", mode="wb", fileobj=output, mtime=0, compresslevel=6
        ) as zipped:
            with tarfile.open(
                fileobj=zipped, mode="w|", format=tarfile.PAX_FORMAT
            ) as archive:
                for member in members:
                    info = tar_info(member)
                    if member["type"] == "dir":
                        source_info = (root / member["path"]).lstat()
                        if not stat.S_ISDIR(source_info.st_mode) or (
                            stat_signature(source_info) != member["_signature"]
                        ):
                            raise ArchiveError(
                                f"Source directory changed: {member['path']}"
                            )
                        archive.addfile(info)
                        continue
                    source = root / member["path"]
                    fd = checked_file(source, member["_signature"])
                    with os.fdopen(fd, "rb") as stream:
                        reader = HashingReader(stream)
                        archive.addfile(info, fileobj=reader)
                        if (
                            reader.count != member["size"]
                            or reader.digest.hexdigest() != member["sha256"]
                            or stat_signature(os.fstat(stream.fileno()))
                            != member["_signature"]
                            or stat_signature(source.lstat()) != member["_signature"]
                        ):
                            raise ArchiveError(
                                f"Source changed during streaming: {member['path']}"
                            )


def initial_groups(members: list[dict], max_bytes: int) -> list[list[dict]]:
    """Keep normal groups well below the cap; oversized files stand alone."""
    budget = int(max_bytes * 0.90)
    groups: list[list[dict]] = []
    current: list[dict] = []
    estimate = 10240
    for member in members:
        # PAX path overhead is accommodated by generous 8 KiB/member allowance.
        cost = ((member["size"] + 511) // 512) * 512 + 8192
        if current and estimate + cost > budget:
            groups.append(current)
            current = []
            estimate = 10240
        current.append(member)
        estimate += cost
    if current:
        groups.append(current)
    return groups


def package_tree(source: Path, destination: Path, max_bytes: int) -> dict:
    """Package ``source`` into deterministic, size-capped shards in a new ``destination``.

    Steps: snapshot and hash the source tree; group members into shards, halving
    any group whose compressed size exceeds ``max_bytes``; confirm the source did
    not change; write ``inventory.json`` (members, shards and a canonical hash);
    then publish the staging directory atomically.

    Args:
        source: Directory to package; must be a real directory, not a link.
        destination: New package directory; must not exist or lie inside ``source``.
        max_bytes: Largest allowed compressed shard size (1 KiB to 500 MiB).

    Returns:
        The inventory dictionary that was written.

    Raises:
        ArchiveError: Invalid arguments, a changing source, or a single member
            too large for one shard.
    """
    if max_bytes < 1024 or max_bytes > MAX_SHARD_BYTES:
        raise ArchiveError("Shard cap must be 1 KiB to 500 MiB")
    source = source.absolute()
    destination = destination.absolute()
    if destination.exists() or destination.is_symlink():
        raise ArchiveError(f"Refusing to overwrite destination: {destination}")
    if source.is_symlink() or not source.is_dir():
        raise ArchiveError(f"Source is not a real directory: {source}")
    if os.path.commonpath((source.resolve(), destination.resolve())) == str(source.resolve()):
        raise ArchiveError("Destination cannot be inside source tree")
    destination.parent.mkdir(parents=True, exist_ok=True)
    members = source_snapshot(source)
    stage = Path(tempfile.mkdtemp(prefix=".package-stage-", dir=destination.parent))
    shards: list[dict] = []
    assignments: dict[str, str] = {}
    try:
        def place(group: list[dict]) -> None:
            """Write ``group`` as the next shard, or split it in half and retry if it is too large."""
            candidate = stage / "candidate.tar.gz"
            write_archive(source, group, candidate)
            byte_count = candidate.stat().st_size
            if byte_count > max_bytes:
                candidate.unlink()
                if len(group) == 1:
                    raise ArchiveError(
                        f"Single member exceeds compressed shard cap: "
                        f"{group[0]['path']} ({byte_count} bytes compressed)"
                    )
                midpoint = len(group) // 2
                place(group[:midpoint])
                place(group[midpoint:])
                return
            name = f"part-{len(shards) + 1:06d}.tar.gz"
            asset = stage / name
            candidate.rename(asset)
            shards.append({
                "name": name, "bytes": byte_count, "sha256": sha256_file(asset),
                "member_count": len(group),
            })
            for member in group:
                assignments[member["path"]] = name

        for group in initial_groups(members, max_bytes):
            place(group)
        assert_source_unchanged(members, source_snapshot(source))
        base = {
            "version": 1,
            "format": "deterministic-tar-gzip-shards",
            "max_shard_bytes": max_bytes,
            "members": [public_member(m, assignments[m["path"]]) for m in members],
            "shards": shards,
        }
        inventory = {**base, "canonical_sha256": hashlib.sha256(canonical_bytes(base)).hexdigest()}
        (stage / "inventory.json").write_text(
            json.dumps(inventory, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        atomic_new_directory(stage, destination)
        return inventory
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def main() -> int:
    """Command-line entry point: package a directory and print a JSON summary; return 0 on success, 1 on failure."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Directory tree to package")
    parser.add_argument("destination", type=Path, help="New package directory")
    parser.add_argument(
        "--max-mib", type=int, default=500,
        help="Maximum compressed shard size in MiB (default 500; maximum 500)",
    )
    args = parser.parse_args()
    try:
        result = package_tree(
            args.source, args.destination, args.max_mib * 1024 * 1024
        )
        print(json.dumps({
            "inventory": str(args.destination.absolute() / "inventory.json"),
            "canonical_sha256": result["canonical_sha256"],
            "shards": len(result["shards"]),
            "members": len(result["members"]),
        }, sort_keys=True))
        return 0
    except (ArchiveError, OSError, tarfile.TarError) as error:
        print(f"package failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
