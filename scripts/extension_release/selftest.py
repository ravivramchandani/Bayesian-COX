#!/usr/bin/env python3
"""Focused round-trip and rejection tests using only synthetic files."""
from __future__ import annotations

import gzip
import hashlib
import json
import shutil
import tarfile
import tempfile
from pathlib import Path

import package as packer
from archive_common import ArchiveError, canonical_bytes, source_snapshot, validate_relative_path
from package import package_tree, write_archive
from verify import verify_and_restore


def must_fail(action, label: str) -> None:
    try:
        action()
    except (ArchiveError, OSError, tarfile.TarError):
        return
    raise AssertionError(f"Expected failure: {label}")


def resign(package_dir: Path, asset_bytes: bytes | None = None) -> None:
    inventory_path = package_dir / "inventory.json"
    inventory = json.loads(inventory_path.read_text())
    shard = inventory["shards"][0]
    asset = package_dir / shard["name"]
    if asset_bytes is not None:
        asset.write_bytes(asset_bytes)
    shard["bytes"] = asset.stat().st_size
    shard["sha256"] = hashlib.sha256(asset.read_bytes()).hexdigest()
    base = {key: value for key, value in inventory.items() if key != "canonical_sha256"}
    inventory["canonical_sha256"] = hashlib.sha256(canonical_bytes(base)).hexdigest()
    inventory_path.write_text(json.dumps(inventory))


def synthetic_tar(
    name: str, payload: bytes, *, duplicate=False, symlink=False, huge_pax=False,
) -> bytes:
    from io import BytesIO
    output = BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=0) as zipped:
        with tarfile.open(fileobj=zipped, mode="w|", format=tarfile.PAX_FORMAT) as archive:
            for _ in range(2 if duplicate else 1):
                info = tarfile.TarInfo(name)
                info.uid = info.gid = info.mtime = 0
                info.uname = info.gname = ""
                info.mode = 0o644
                if huge_pax:
                    info.pax_headers = {"oversized": "x" * 50_000}
                if symlink:
                    info.type = tarfile.SYMTYPE
                    info.linkname = "../outside"
                    archive.addfile(info)
                else:
                    from io import BytesIO as Reader
                    info.type = tarfile.REGTYPE
                    info.size = len(payload)
                    archive.addfile(info, Reader(payload))
    return output.getvalue()


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="shard-selftest-") as temporary:
        root = Path(temporary)
        source = root / "source"
        source.mkdir()
        (source / "empty").mkdir()
        (source / "nested").mkdir()
        (source / "nested" / "alpha.txt").write_bytes(b"alpha\n")
        (source / "nested" / "zero.bin").write_bytes(b"")
        (source / "unicode-β.txt").write_text("βeta\n", encoding="utf-8")
        for number in range(3):
            # Fixed pseudo-random data keep test artifacts small and incompressible.
            (source / f"noise-{number}.bin").write_bytes(
                hashlib.shake_256(f"noise:{number}".encode()).digest(50_000)
            )
        first = root / "first"
        second = root / "second"
        one = package_tree(source, first, 80 * 1024)
        two = package_tree(source, second, 80 * 1024)
        assert len(one["shards"]) >= 2
        assert one == two, "Identical input must produce identical inventory"
        for shard in one["shards"]:
            assert (first / shard["name"]).read_bytes() == (second / shard["name"]).read_bytes()
            assert shard["bytes"] <= 80 * 1024
        restored = root / "restored"
        verified = verify_and_restore(first, restored, one["canonical_sha256"])
        assert verified == one
        for entry in source.rglob("*"):
            counterpart = restored / entry.relative_to(source)
            assert counterpart.exists()
            if entry.is_dir():
                assert counterpart.is_dir()
            else:
                assert counterpart.read_bytes() == entry.read_bytes()
        must_fail(lambda: verify_and_restore(first, restored), "restore overwrite")
        must_fail(
            lambda: verify_and_restore(first, root / "wrong-hash", "0" * 64),
            "trusted inventory digest mismatch",
        )

        altered = root / "altered"
        shutil.copytree(first, altered)
        shard_file = altered / one["shards"][0]["name"]
        with shard_file.open("r+b") as stream:
            stream.seek(-1, 2)
            byte = stream.read(1)
            stream.seek(-1, 2)
            stream.write(bytes([byte[0] ^ 1]))
        must_fail(lambda: verify_and_restore(altered, root / "bad-restore"), "asset tamper")
        assert not (root / "bad-restore").exists()

        forged = root / "forged"
        shutil.copytree(first, forged)
        inventory = json.loads((forged / "inventory.json").read_text())
        inventory["members"][0]["path"] = "../outside"
        base = {key: value for key, value in inventory.items() if key != "canonical_sha256"}
        inventory["canonical_sha256"] = hashlib.sha256(canonical_bytes(base)).hexdigest()
        (forged / "inventory.json").write_text(json.dumps(inventory))
        must_fail(lambda: verify_and_restore(forged, root / "unsafe-restore"), "path traversal")
        assert not (root / "outside").exists()

        duplicated = root / "duplicated"
        shutil.copytree(first, duplicated)
        inventory = json.loads((duplicated / "inventory.json").read_text())
        inventory["members"].insert(1, dict(inventory["members"][0]))
        base = {key: value for key, value in inventory.items() if key != "canonical_sha256"}
        inventory["canonical_sha256"] = hashlib.sha256(canonical_bytes(base)).hexdigest()
        (duplicated / "inventory.json").write_text(json.dumps(inventory))
        must_fail(lambda: verify_and_restore(duplicated, root / "duplicate-restore"), "duplicate inventory member")

        single_source = root / "single-source"
        single_source.mkdir()
        (single_source / "file.txt").write_bytes(b"payload\n")
        clean = root / "single-package"
        package_tree(single_source, clean, 80 * 1024)
        clean_bytes = (clean / "part-000001.tar.gz").read_bytes()
        from io import BytesIO
        with gzip.GzipFile(fileobj=BytesIO(clean_bytes), mode="rb") as expanded:
            tar_bytes = expanded.read()
        tail_buffer = BytesIO()
        with gzip.GzipFile(filename="", fileobj=tail_buffer, mode="wb", mtime=0) as zipped:
            zipped.write(tar_bytes + b"\0" * 20_000)
        for label, archive_bytes in [
            ("symlink-tar", synthetic_tar("file.txt", b"payload\n", symlink=True)),
            ("duplicate-tar", synthetic_tar("file.txt", b"payload\n", duplicate=True)),
            ("corrupt-gzip-trailer", clean_bytes[:-1] + bytes([clean_bytes[-1] ^ 1])),
            ("oversized-tar-tail", tail_buffer.getvalue()),
            ("oversized-pax-header", synthetic_tar("file.txt", b"payload\n", huge_pax=True)),
        ]:
            malicious = root / label
            shutil.copytree(clean, malicious)
            resign(malicious, archive_bytes)
            must_fail(
                lambda package_dir=malicious, output=root / f"{label}-out":
                    verify_and_restore(package_dir, output),
                label,
            )

        malformed = root / "malformed"
        shutil.copytree(clean, malformed)
        inventory = json.loads((malformed / "inventory.json").read_text())
        inventory["members"][0]["type"] = []
        base = {key: value for key, value in inventory.items() if key != "canonical_sha256"}
        inventory["canonical_sha256"] = hashlib.sha256(canonical_bytes(base)).hexdigest()
        (malformed / "inventory.json").write_text(json.dumps(inventory))
        must_fail(lambda: verify_and_restore(malformed, root / "malformed-out"), "malformed type")

        must_fail(lambda: validate_relative_path("CON.txt"), "portable reserved name")
        must_fail(lambda: validate_relative_path("trailing. "), "portable trailing dot/space")
        linked = source / "linked"
        linked.symlink_to(source / "nested")
        must_fail(lambda: package_tree(source, root / "linked-package", 80 * 1024), "source symlink")
        linked.unlink()
        snapshot = source_snapshot(source)
        (source / "nested" / "alpha.txt").write_bytes(b"changed\n")
        must_fail(
            lambda: write_archive(source, snapshot, root / "changed.tar.gz"),
            "source changed after snapshot",
        )
        current = source_snapshot(source)
        alpha = next(item for item in current if item["path"] == "nested/alpha.txt")
        original_read = packer.HashingReader.read
        mutated = False
        def mutate_during_read(self, length=-1):
            nonlocal mutated
            data = original_read(self, length)
            if data and not mutated:
                mutated = True
                (source / "nested" / "alpha.txt").write_bytes(b"edited during read\n")
            return data
        packer.HashingReader.read = mutate_during_read
        try:
            must_fail(
                lambda: write_archive(source, [alpha], root / "changed-midstream.tar.gz"),
                "source changed during streaming",
            )
        finally:
            packer.HashingReader.read = original_read

        large_source = root / "large-source"
        large_source.mkdir()
        (large_source / "too-large.bin").write_bytes(
            hashlib.shake_256(b"too-large").digest(1_200_000)
        )
        must_fail(
            lambda: package_tree(large_source, root / "too-large-package", 1024 * 1024),
            "single compressed file over shard cap",
        )
        assert not (root / "too-large-package").exists()
    print("selftest passed: deterministic round-trip, shard cap, trusted digest, corrupt assets and gzip, unsafe/duplicate entries, symlinks, overwrite, source changes")


if __name__ == "__main__":
    main()
