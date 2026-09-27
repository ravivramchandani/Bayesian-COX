# Sharded package transfer

Requires Python 3.11 or newer; only the standard library is used. Arrange the complete private release as one source directory tree. Include every result cell, trace, QA artifact, measured-source license, matched Parquet file, and code file the receiving laptop needs. The scripts do not know or select project-specific files.

```sh
python3 package.py /path/to/release-tree /path/to/new-package-directory
# Record the printed canonical_sha256 somewhere separate from the copied package.
python3 verify.py /path/to/copied-package-directory /path/to/new-restored-directory --expected-sha256 YOUR_RECORDED_DIGEST
python3 selftest.py
```

Copy **inventory.json and every `part-*.tar.gz` file** together. The packer refuses an existing package destination; the verifier refuses an existing restore destination. Publication uses an atomic no-replace directory rename, and fails on platforms/filesystems without that operation. The verifier checks the canonical inventory hash, every compressed shard SHA256 and size, every ordered tar member name, exact type, zeroed identity/time metadata, length and SHA256, tar padding, and gzip trailer before accepting the restored tree. It copies each shard to private scratch space while hashing and extracts only the verified copy. It restores only regular files and directories through validated relative paths; links, duplicate names and unsafe cross-platform names fail.

Compressed shards are at most 500 MiB (500 × 1,048,576 bytes). A single file whose *standalone compressed tar.gz* exceeds the cap cannot be split and causes packaging to fail; split or externally transform that source file deliberately before packaging. The inventory's `canonical_sha256` is SHA256 of the inventory JSON object with that field omitted, serialized with sorted keys, compact separators and UTF-8. The digest stored inside inventory detects copy errors, not malicious rewriting of both assets and inventory. Passing an independently recorded digest via `--expected-sha256` provides a trusted comparison; it is optional only when authenticity is not required.

Source file contents are preserved byte-for-byte. File modes are normalized to 0644 and directory modes to 0755 in the archive; source mtimes, uid/gid and ownership are not preserved. No source/package absolute path, creation time, or random staging name enters the package bytes. Identical input generates identical bytes with the same Python/zlib implementation; cross-version or cross-platform DEFLATE byte identity is not guaranteed. macOS was exercised here; Linux and Windows no-replace publication paths were not exercised.

The workflow does not validate scientific correctness, Parquet schemas, software environments, or whether the source tree contains every intended result; check that upstream before packaging. Package and restore should run on stable local storage while no process edits the source. Changes observed during hashing or streaming fail the run.
