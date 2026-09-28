#!/usr/bin/env python3
"""Stage exactly 55 pinned audit/preparation artifacts, never production QA."""

from __future__ import annotations

import argparse
import ctypes
import errno
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

CLASSIFICATION = "audit_and_preparation_only; not production completion or visual QA"
MANIFEST_NAME = "audit_support_manifest.json"
COMMIT = "165bd77077b03038f9c2ee104959eb474770b2a9"
REPOSITORY = "https://github.com/cBioPortal/datahub"
REGISTRY = "coordination/extension_sources/catalytic_reference_hashes.json"
FREEZE = "coordination/extension_protocol_freeze.json"
VALIDATION = "coordination/extension_sources/implementation_validation.json"
SOURCE_REPORT = "coordination/extension_sources/metabric_source_report.json"
MATCHED_MANIFEST = "coordination/extension_sources/matched_metabric_manifest.json"
PROFILE = "coordination/extension_sources/training_compute_profile.json"
REFERENCE_FIXTURE = "tests/fixtures/extensions/catalytic_r_reference.json"
PAIR_FIXTURE = "tests/fixtures/extensions/metabric_known_accession_pairs.csv"
PROFILE_PURPOSE = "training-only computational profile; no outer-validation scores"
FROZEN_PATHS = frozenset({
    "config/extensions.yaml", "coordination/extension_sources/baseline_sources.json",
    MATCHED_MANIFEST, SOURCE_REPORT, PROFILE,
    "docs/protocol_addendum_extensions.md", REFERENCE_FIXTURE, PAIR_FIXTURE,
})

# The executed reference registry supplies these 24 hashes. Its captured byte hash
# is also checked below, so an edited registry cannot silently repin an artifact.
REFERENCE_PATHS = (
    "REFERENCE_REPORT.md", "fixture_inputs.json", "reference_fixtures.json",
    "execute_reference.R", "verify_reference.py", "R-execution.log",
    "R-sessionInfo.txt", "r-env-explicit.txt", "independent_validation.json",
    "sources/catalytic_0.1.0.tar.gz", "sources/survival_3.8-12.tar.gz",
    "sources/catalytic/R/cat_cox.R", "sources/catalytic/R/misc.R",
    "sources/catalytic/R/predict.R", "sources/catalytic/inst/stan/cox.stan",
    "sources/catalytic/inst/stan/cox_joint.stan",
    "sources/authors/point_estimation_cat.R", "sources/authors/bayesian_cox_cat.stan",
    "sources/arxiv_2312.01411v2.html", "sources/arxiv_2312.01411v2.pdf",
    "sources/survival/R/basehaz.R", "sources/survival/R/survfit.coxph.R",
    "sources/survival/man/basehaz.Rd", "sources/survival/man/coxph.Rd",
)

# Fixed capture hashes for the 31 additional supporting artifacts. These are not
# inferred from host paths or accepted from an arbitrary caller-supplied manifest.
CAPTURE_SHA256 = {
    "catalytic/SHA256SUMS.json": "1e118f808a4e2344c94d4ab01b2b4d51e6868e468074ac9b8cfb1eacb9a14c4a",
    "catalytic/r-env-install.log": "44900cefe4d79bc175c9834c328e52fb21e2c6f1fadcb4dc8172afb553844b8b",
    "catalytic/rlang-install.log": "125a3a6fb9f4175c6a58629ba72524042a860d8c1b0228f0765b0bd6e13184ec",
    "catalytic/rlang-conda-install.log": "dd0d8ecd978c9dc52eacb133c125fd00a78339f090623d603970a93c5b1b4946",
    "preparation/implementation_environment_verification.json": "cc6fc42b01e2a273c31e4c85acff93c4090e289d1b8dd924438e5c7e211475e7",
    "preparation/implementation_full_tests.log": "5827b3e31735903c2f7e5170c5c1db7228e6cc77de81035d74ee76cf9af77665",
    "preparation/implementation_output_init_fix_tests.log": "1d1dbff8b907c8d96217c57c7167a382391d6a39dab9777436723a08f47727e7",
    "preparation/training_compute_profile.json": "5c7b18215e0a2e4c656b9f4e4ba7edc303176d817f8437ed92296137eb0a5b7d",
    "preparation/training_compute_profile.log": "e9ff858a4c30f16e47f8b719bf71108b09990a344b366be4f23b832ba1b43aea",
    "preparation/training_compute_profile_compact.json": "b3a42f1d2731a00f0d63cabb616a00231ef1f9b32e540afd5eedd448e04d65f1",
    "preparation/training_compute_profile_compact.log": "cc96c0af447f43e7f6f8cf7640ec8b8c57f915a44830bea5faa4a4403d267da4",
    "preparation/training_compute_profile_final.json": "2e4bb3e80815445889d8675e2525cb55688ea6843c29f8c1afed9d91843941c2",
    "preparation/training_compute_profile_final.log": "d7d87fdade4165a2cb3e4a0337709f302fd169d2cdd6d7550afdb92dedafcfda",
    "metabric/github_commit_metadata.json": "1d2a9b2ecf2b1b242dbac069fb7519b320515f563a5834c11d50cc78617591d7",
    "metabric/github_directory_manifest.json": "8490fd165f425d5093273240ed64a8632dd51d10b58882eacd1e21a5881b2695",
    "metabric/download_manifest.json": "1b0a0c19607026a9a5dcc57e0f287cfaf1a3d0e2c53753413ee2f52b3be3cae2",
    "metabric/schema_alignment_audit.json": "49eb961c0d6a8763657b305cda9ea19e80b64bdca953b6b0cdb337f2f8277487",
    "metabric/gene_identity_audit.json": "98e8c8890cde5cf176d0c157b47725a5aea6c8710aa6f546c9ef9c872e38213b",
    "metabric/known_biological_duplicate_audit.json": "29a4dd7178fe3aefa046538912b245a310a3986bdb53df06e89b4cd39fd1134e",
    "metabric/known_same_individual_accession_pairs.csv": "9293ec90899aa79afb5fb2162bca60ebc86a2f49bcf6e7a507acb793883810f9",
    "metabric/curtis_europepmc_metadata.json": "46b6b10a34bf3936906fcd6cea9f0229f0cd57155a42b225733f3cda047aab17",
    "metabric/curtis_2012_fulltext.xml": "fbc2574628d07789ef077d4148ae62c64b317d2c51c703ad8805ee0740d6dbd5",
    "metabric/curtis_2012_supplement_methods.pdf": "17ca72e029eadad4f08a392847fe92a024621839fde4b567bd6965b66bd6ae4e",
    "metabric/curtis_2012_supplement_methods.txt": "fee396433ce99c4f44749c5dca52420ba9acfd5af80133e4e71b2b5c2c963aed",
    "metabric/curtis_methods_page3.png": "c07a9e0713e93fa4cc36f4a5da01d31d4b7d2efbb7fd3ac8f5990691e65bc28f",
    "metabric/curtis_methods_page6.png": "c9e99ee5be2c370a251d2ea4d2f8a7f1be58e0ac2be5e3f6165dc90708c5712b",
    "metabric/pdf_render_warnings.log": "939d36ed42f8b890eb2837ecaf16e8e39ff43dc864a278ff7747739fd8dcdefd",
    "metabric/lfs_pointers/data_clinical_patient.txt": "b8603a6296432d7a52257583d71c0f85295a3dd2761e51276c99d8b2c3a38542",
    "metabric/lfs_pointers/data_clinical_sample.txt": "eda6f53f542e0220ef224b18afd50171ca6825b7ccf6fb662d0cd136321251f6",
    "metabric/lfs_pointers/data_mrna_illumina_microarray.txt": "33847ca28d168a9c5003c76cd3f7fa451331dfbf4ddd81503848e398370d8d2c",
    "metabric/lfs_pointers/data_mrna_illumina_microarray_zscores_ref_diploid_samples.txt": "baf8004fc53b3db27567a5eff59eb478042f8147e0d55e257840f7b7998dcb5a",
}
RAW_NAMES = frozenset({
    "LICENSE", "Readme.txt", "data_clinical_patient.txt", "data_clinical_sample.txt",
    "data_mrna_illumina_microarray.txt", "meta_clinical_patient.txt",
    "meta_clinical_sample.txt", "meta_mrna_illumina_microarray.txt",
    "meta_mrna_illumina_microarray_zscores_ref_diploid_samples.txt", "meta_study.txt",
})
LFS_NAMES = frozenset({
    "data_clinical_patient.txt", "data_clinical_sample.txt",
    "data_mrna_illumina_microarray.txt",
})
EXCLUDED_NAME = "data_mrna_illumina_microarray_zscores_ref_diploid_samples.txt"


def _require(condition: bool, message: str) -> None:
    """Raise ``ValueError(message)`` when ``condition`` is false."""
    if not condition:
        raise ValueError(message)


def _canonical_hash(value: Any) -> str:
    """Return the SHA-256 of a value's compact, key-sorted JSON encoding."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode("utf-8")).hexdigest()


def _relative(value: str) -> str:
    """Return ``value`` if it is a safe, normalised, relative POSIX path; raise otherwise."""
    path = PurePosixPath(value)
    _require(isinstance(value, str) and value and not path.is_absolute()
             and value == path.as_posix() and all(p not in {"", ".", ".."} for p in path.parts)
             and "\\" not in value and "\x00" not in value, f"unsafe relative path: {value!r}")
    return value


def _regular_path(path: Path, *, directory: bool = False) -> Path:
    """Return the absolute path after checking that no component is a link and the target is a regular file (or a directory when ``directory`` is true)."""
    path = path.absolute()
    _require(".." not in path.parts, f"parent traversal refused: {path}")
    chain = list(reversed(path.parents)) + [path]
    for item in chain:
        mode = item.lstat().st_mode
        _require(not stat.S_ISLNK(mode), f"linked path refused: {item}")
        if item != path or directory:
            _require(stat.S_ISDIR(mode), f"non-directory path component: {item}")
        else:
            _require(stat.S_ISREG(mode), f"non-regular file refused: {item}")
    return path


def _fresh_target(path: Path) -> Path:
    """Return the absolute path after checking that it does not exist yet and that its existing ancestors are real directories."""
    path = path.absolute()
    _require(".." not in path.parts, f"parent traversal refused: {path}")
    for item in reversed(path.parents):
        try:
            mode = item.lstat().st_mode
        except FileNotFoundError:
            continue
        _require(not stat.S_ISLNK(mode) and stat.S_ISDIR(mode),
                 f"linked or non-directory target ancestor refused: {item}")
    _require(not path.exists() and not path.is_symlink(), f"fresh target required: {path}")
    return path


def _signature(info: os.stat_result) -> tuple[int, int, int, int, int]:
    """Return the stat fields (device, inode, size, modification and change times) used to detect a changed or replaced file."""
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


@dataclass(frozen=True)
class Snapshot:
    """A file's path, size, SHA-256 and stat signature, recorded when it was validated."""
    path: Path
    size: int
    sha256: str
    signature: tuple[int, int, int, int, int]


def _open_snapshot(path: Path, expected: Snapshot | None = None) -> tuple[int, tuple[int, int, int, int, int]]:
    """Open a regular file read-only without following links; if ``expected`` is given, require that the file is unchanged since that snapshot."""
    path = _regular_path(path)
    before = _signature(path.stat())
    if expected is not None:
        _require(before == expected.signature, f"source changed since validation: {path}")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        _require(stat.S_ISREG(os.fstat(fd).st_mode) and _signature(os.fstat(fd)) == before,
                 f"source changed while opening: {path}")
    except BaseException:
        os.close(fd)
        raise
    return fd, before


def _check_unchanged(path: Path, fd: int, before: tuple[int, int, int, int, int]) -> None:
    """Raise ``ValueError`` if the file changed while it was being read."""
    _regular_path(path)
    _require(_signature(os.fstat(fd)) == before and _signature(path.stat()) == before,
             f"source changed during streaming: {path}")


def _snapshot(path: Path) -> Snapshot:
    """Stream a file once, returning its size, hash and signature, and reject it if it changes during the read."""
    path = path.absolute()
    fd, before = _open_snapshot(path)
    digest = hashlib.sha256()
    size = 0
    try:
        while chunk := os.read(fd, 1024 * 1024):
            size += len(chunk)
            _require(size <= before[2], f"source grew during streaming: {path}")
            digest.update(chunk)
        _check_unchanged(path, fd, before)
    finally:
        os.close(fd)
    _require(size == before[2], f"streamed size differs: {path}")
    return Snapshot(path, size, digest.hexdigest(), before)


def _read_bytes(source: Snapshot, limit: int = 4 * 1024 * 1024) -> bytes:
    """Return a small file's bytes after confirming they still match its validated snapshot."""
    _require(source.size <= limit, f"metadata exceeds bounded size: {source.path}")
    fd, before = _open_snapshot(source.path, source)
    try:
        chunks = []
        size = 0
        while chunk := os.read(fd, 65536):
            size += len(chunk)
            _require(size <= source.size, f"metadata grew during streaming: {source.path}")
            chunks.append(chunk)
        data = b"".join(chunks)
        _check_unchanged(source.path, fd, before)
    finally:
        os.close(fd)
    _require(len(data) == source.size and hashlib.sha256(data).hexdigest() == source.sha256,
             f"metadata changed since validation: {source.path}")
    return data


def _json(source: Snapshot) -> Any:
    """Parse a validated snapshot as JSON, rejecting duplicate keys and non-finite numbers."""
    def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        """JSON object hook that rejects duplicate keys."""
        obj: dict[str, Any] = {}
        for name, value in pairs:
            _require(name not in obj, f"duplicate JSON key: {source.path}: {name}")
            obj[name] = value
        return obj

    def no_nonfinite(token: str) -> None:
        """Reject ``NaN`` and ``Infinity`` literals."""
        raise ValueError(f"nonfinite JSON value: {source.path}: {token}")

    return json.loads(_read_bytes(source), object_pairs_hook=no_duplicates,
                      parse_constant=no_nonfinite)


def _hash_value(value: Any, digits: int = 64) -> bool:
    """Return True if ``value`` is a lowercase hexadecimal digest with ``digits`` characters."""
    return isinstance(value, str) and re.fullmatch(rf"[0-9a-f]{{{digits}}}", value) is not None


def _copy_snapshot(source: Snapshot, target: Path) -> None:
    """Copy a validated file to a new ``target`` (never overwriting), checking the copied bytes against the snapshot hash."""
    target.parent.mkdir(parents=True, exist_ok=True)
    source_fd, before = _open_snapshot(source.path, source)
    target_fd: int | None = None
    digest = hashlib.sha256()
    size = 0
    try:
        target_fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                            | getattr(os, "O_NOFOLLOW", 0), 0o644)
        while chunk := os.read(source_fd, 1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
            _require(size <= source.size, f"source grew during copy: {source.path}")
            view = memoryview(chunk)
            while view:
                written = os.write(target_fd, view)
                _require(written > 0, f"short write: {target}")
                view = view[written:]
        os.fsync(target_fd)
        _check_unchanged(source.path, source_fd, before)
    finally:
        os.close(source_fd)
        if target_fd is not None:
            os.close(target_fd)
    _require(size == source.size and digest.hexdigest() == source.sha256,
             f"copied stream differs from validated source: {source.path}")


def _atomic_new_directory(source: Path, target: Path) -> None:
    """Publish without overwriting even if a target appears after validation."""
    if sys.platform == "darwin":
        libc = ctypes.CDLL(None, use_errno=True)
        rename = libc.renamex_np
        rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        result = rename(os.fsencode(source), os.fsencode(target), 0x4)  # RENAME_EXCL
    elif sys.platform.startswith("linux"):
        libc = ctypes.CDLL(None, use_errno=True)
        rename = getattr(libc, "renameat2", None)
        _require(rename is not None, "atomic no-replace directory rename unavailable")
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p,
                           ctypes.c_uint]
        rename.restype = ctypes.c_int
        result = rename(-100, os.fsencode(source), -100, os.fsencode(target), 1)
    elif sys.platform == "win32":
        os.rename(source, target)  # Windows refuses an existing destination.
        return
    else:
        raise ValueError("atomic no-replace directory publication unsupported on this OS")
    if result:
        code = ctypes.get_errno()
        if code in {errno.EEXIST, errno.ENOTEMPTY}:
            raise FileExistsError(target)
        raise OSError(code, os.strerror(code), str(target))


def _validate_domain(sources: dict[str, Snapshot], production: dict[str, Snapshot],
                     external_report: Snapshot, freeze: dict[str, Any],
                     receipt: dict[str, Any]) -> dict[str, Any]:
    """Check that the audit artefacts describe the pinned official METABRIC source.

    Confirms the source report names the official cBioPortal study and pinned
    commit, performed no model fits or outcome analysis, and agrees with the
    recorded Git commit, directory listing and file hashes, and with the
    production matched-cohort manifest.

    Returns:
        A summary of the validated source facts for the staging record.
    """
    report = _json(external_report)
    matched = _json(production[MATCHED_MANIFEST])
    _require(report["study_id"] == "brca_metabric" and report["repository"] == REPOSITORY
             and report["commit"] == COMMIT and report["commit_verified"] is True,
             "source report does not identify the pinned official study/commit")
    _require(report["model_fits_performed"] is False
             and report["outcome_performance_analysis_performed"] is False,
             "source report is not a source-only audit")
    api = "https://api.github.com/repos/cBioPortal/datahub"
    raw = f"https://raw.githubusercontent.com/cBioPortal/datahub/{COMMIT}/public/brca_metabric/"
    media = f"https://media.githubusercontent.com/media/cBioPortal/datahub/{COMMIT}/public/brca_metabric/"
    _require(report["directory_manifest_url"] == f"{api}/contents/public/brca_metabric?ref={COMMIT}",
             "source report directory URL differs from the pinned official commit")
    commit = _json(sources["metabric/github_commit_metadata.json"])
    _require(commit["sha"] == COMMIT and commit["tree"]["sha"] == report["commit_tree_sha1"]
             and _hash_value(report["commit_tree_sha1"], 40)
             and commit["url"] == f"{api}/git/commits/{COMMIT}",
             "Git commit/tree evidence differs from source report")
    listing = _json(sources["metabric/github_directory_manifest.json"])
    entries = {row["name"]: row for row in listing}
    _require(len(entries) == len(listing), "duplicate Git directory entry")
    files = report["data_files"]
    rows = {row["name"]: row for row in files}
    _require(len(rows) == len(files) and set(rows) == RAW_NAMES,
             "source report measured/license inventory differs")
    _require(_json(sources["metabric/download_manifest.json"]) == files,
             "download manifest differs from frozen source report")
    for name, row in rows.items():
        entry = entries[name]
        _require(entry["sha"] == row["git_blob_sha1"] and _hash_value(row["git_blob_sha1"], 40)
                 and entry["path"] == f"public/brca_metabric/{name}"
                 and entry["type"] == "file" and entry["download_url"] == raw + name
                 and row["raw_url"] == raw + name and row["git_blob_verified"] is True
                 and _hash_value(row["downloaded_sha256"])
                 and isinstance(row["downloaded_size"], int) and row["downloaded_size"] > 0,
                 f"Git/download lineage differs: {name}")
        if name in LFS_NAMES:
            _require(row["payload_url"] == media + name and row["lfs_verified"] is True
                     and row["lfs_sha256"] == row["downloaded_sha256"]
                     and row["lfs_size"] == row["downloaded_size"], f"LFS payload lineage differs: {name}")
        else:
            _require(row["payload_url"] == raw + name, f"ordinary payload URL differs: {name}")
    audits = report["audits"]
    for name, field in (("schema_alignment_audit.json", "schema_alignment"),
                        ("gene_identity_audit.json", "gene_identity")):
        _require(_json(sources[f"metabric/{name}"]) == audits[field],
                 f"source report and audit disagree: {name}")
    duplicate = audits["known_biological_duplicates"]
    duplicate_fields = {k: v for k, v in duplicate.items()
                        if k not in {"source_pair_mapping_path", "source_pair_mapping_sha256"}}
    _require(_json(sources["metabric/known_biological_duplicate_audit.json"]) == duplicate_fields,
             "source report and known-pair audit disagree")
    pair_sha = sources["metabric/known_same_individual_accession_pairs.csv"].sha256
    _require(pair_sha == duplicate["source_pair_mapping_sha256"]
             == matched["known_pairs_sha256"] == freeze["sha256"][PAIR_FIXTURE],
             "known-pair CSV is not bound to report/preparation/freeze")
    _require(sources["metabric/curtis_2012_supplement_methods.pdf"].sha256
             == report["platform_and_processing"]["supplement_sha256"],
             "supplement PDF differs from source report")
    _require(set(matched["source_sha256"]) == LFS_NAMES,
             "matched preparation measured-source set differs")
    for name, expected in matched["source_sha256"].items():
        _require(rows[name]["downloaded_sha256"] == expected,
                 f"matched preparation and source report disagree: {name}")
    excluded = report["excluded_zscore_profile"]
    _require(excluded["data_name"] == EXCLUDED_NAME and excluded["payload_downloaded"] is False
             and excluded["raw_pointer_url"] == raw + EXCLUDED_NAME,
             "excluded z-score profile lineage differs")
    for name in sorted(LFS_NAMES | {EXCLUDED_NAME}):
        data = _read_bytes(sources[f"metabric/lfs_pointers/{name}"], 1024)
        pointer = re.fullmatch(rb"version https://git-lfs.github.com/spec/v1\noid sha256:([0-9a-f]{64})\nsize ([0-9]+)\n", data)
        _require(pointer is not None, f"invalid LFS pointer: {name}")
        oid, size = pointer.group(1).decode("ascii"), int(pointer.group(2))
        row = excluded if name == EXCLUDED_NAME else rows[name]
        git_sha = hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()
        _require(git_sha == row["git_blob_sha1"] == entries[name]["sha"]
                 and oid == row["lfs_sha256"] and size == row["lfs_size"],
                 f"LFS pointer Git/OID/size binding differs: {name}")
    environment = sources["preparation/implementation_environment_verification.json"]
    tests = sources["preparation/implementation_full_tests.log"]
    profile = sources["preparation/training_compute_profile_final.json"]
    _require(environment.sha256 == receipt["environment_verification_sha256"]
             and tests.sha256 == receipt["tests"]["full_log_sha256"]
             and receipt["extension_freeze_content_sha256"] == freeze["content_sha256"]
             and receipt["frozen_primary_changed"] is False,
             "implementation environment/tests receipt differs from frozen preparation")
    env = _json(environment)
    _require(env["status"] == "ok" and env["platform"]["machine"] == "arm64"
             and env["lock_sha256"] == production["conda-lock.yml"].sha256,
             "environment verification differs from production Apple Silicon lock")
    _require(profile.sha256 == freeze["sha256"][PROFILE],
             "final training-only profile differs from extension freeze")
    for name in ("training_compute_profile.json", "training_compute_profile_compact.json",
                 "training_compute_profile_final.json"):
        data = _json(sources[f"preparation/{name}"])
        _require(data["purpose"] == PROFILE_PURPOSE and data["matched_sha256"] == matched["matched_sha256"],
                 f"profile is not the matched training-only preparation: {name}")
    return {"study_id": "brca_metabric", "datahub_commit": COMMIT,
            "git_tree_sha1": report["commit_tree_sha1"],
            "matched_sha256": matched["matched_sha256"], "known_pairs_sha256": pair_sha,
            "source_report_sha256": external_report.sha256,
            "source_report_domain_links": ["downloads", "schema_alignment", "gene_identity",
                                           "known_pairs", "supplement_pdf", "git_commit_tree", "git_lfs"],
            "excluded_zscore_payload_copied": False}


def _verify_copies(root: Path, expected: dict[str, Snapshot], *, manifest: Snapshot | None = None) -> None:
    """Check that a staged directory holds exactly the expected files, each identical to its source snapshot."""
    names = set(expected)
    if manifest is not None:
        names.add(MANIFEST_NAME)
    actual = set()
    for path in root.rglob("*"):
        _require(not path.is_symlink(), f"linked staged path refused: {path}")
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
        else:
            _require(path.is_dir(), f"non-regular staged member: {path}")
    _require(actual == names, "staged audit file inventory differs")
    for name, source in expected.items():
        copied = _snapshot(root / name)
        _require(copied.size == source.size and copied.sha256 == source.sha256,
                 f"copied audit artifact differs: {name}")
    if manifest is not None:
        copied = _snapshot(root / MANIFEST_NAME)
        _require(copied.size == manifest.size and copied.sha256 == manifest.sha256,
                 "copied audit manifest differs")


def stage_audit_support(production: Path, reference_root: Path, preparation: Path,
                        target: Path) -> dict[str, Any]:
    """Validate, copy, and rehash exactly 55 files into a fresh audit directory.

    ``production`` is the production *code root* containing coordination/, not
    the live results directory. No measured matrices or production cells are read.
    ``target`` is the new audit tree itself (typically release_stage / "audit").
    """
    production = _regular_path(Path(production), directory=True)
    reference_root = _regular_path(Path(reference_root), directory=True)
    preparation = _regular_path(Path(preparation), directory=True)
    target = _fresh_target(Path(target))
    for root in (production, reference_root, preparation):
        _require(target != root and root not in target.parents and target not in root.parents,
                 f"target overlaps a source root: {target}")
        # macOS realpath can retain a different spelling on a case-insensitive
        # volume; compare filesystem identities as well as lexical containment.
        _require(not any(parent.exists() and parent.samefile(root) for parent in target.parents),
                 f"target overlaps a source root by directory identity: {target}")
    prod: dict[str, Snapshot] = {}
    for name in sorted(FROZEN_PATHS | {REGISTRY, FREEZE, VALIDATION, "conda-lock.yml"}):
        prod[name] = _snapshot(production / _relative(name))
    freeze = _json(prod[FREEZE])
    _require(_hash_value(freeze["content_sha256"])
             and _canonical_hash({k: v for k, v in freeze.items() if k != "content_sha256"})
             == freeze["content_sha256"], "extension freeze canonical content hash differs")
    _require(set(freeze["sha256"]) == FROZEN_PATHS, "frozen metadata inventory differs")
    for name, expected in freeze["sha256"].items():
        _require(_hash_value(expected) and prod[name].sha256 == expected,
                 f"frozen production metadata changed: {name}")
    registry = _json(prod[REGISTRY])
    _require(set(registry) == set(REFERENCE_PATHS) and len(registry) == 24,
             "executed reference registry must contain the exact 24-artifact allowlist")
    _require(prod[REGISTRY].sha256 == CAPTURE_SHA256["catalytic/SHA256SUMS.json"],
             "production reference registry differs from captured registry")
    _require(registry["reference_fixtures.json"] == freeze["sha256"][REFERENCE_FIXTURE],
             "executed reference fixture is not bound to the extension freeze")
    expected = {f"catalytic/{name}": sha for name, sha in registry.items()}
    _require(not set(expected).intersection(CAPTURE_SHA256), "duplicate audit allowlist entry")
    expected.update(CAPTURE_SHA256)
    _require(len(expected) == 55, "audit allowlist must contain exactly 55 files")
    sources: dict[str, Snapshot] = {}
    for name, digest in sorted(expected.items()):
        _relative(name)
        _require(_hash_value(digest), f"invalid pinned artifact hash: {name}")
        prefix, rest = name.split("/", 1)
        root = preparation if prefix == "preparation" else reference_root / prefix
        source = _snapshot(root / rest)
        _require(source.sha256 == digest, f"pinned audit artifact changed: {name}")
        sources[name] = source
    _require(sources["catalytic/SHA256SUMS.json"].sha256 == prod[REGISTRY].sha256,
             "external and production executed-reference registries differ")
    external_report = _snapshot(reference_root / "metabric/metabric_source_report.json")
    _require(external_report.sha256 == freeze["sha256"][SOURCE_REPORT],
             "external METABRIC source report differs from frozen source report")
    domain = _validate_domain(sources, prod, external_report, freeze, _json(prod[VALIDATION]))
    categories = {"catalytic": "executed_reference_arithmetic_audit",
                  "preparation": "training_and_implementation_preparation_audit",
                  "metabric": "measured_source_provenance_audit"}
    entries = []
    for name, source in sorted(sources.items()):
        prefix = name.split("/", 1)[0]
        binding = "captured_sha256"
        if prefix == "catalytic" and name.removeprefix("catalytic/") in registry:
            binding = f"production:{REGISTRY}"
        elif name == "catalytic/SHA256SUMS.json":
            binding = f"production:{REGISTRY}; captured_sha256"
        elif name in {"preparation/implementation_environment_verification.json",
                      "preparation/implementation_full_tests.log"}:
            binding = f"production:{VALIDATION}; extension_freeze; captured_sha256"
        elif name == "preparation/training_compute_profile_final.json":
            binding = f"production:{FREEZE}:{PROFILE}; captured_sha256"
        entries.append({"path": name, "category": categories[prefix], "bytes": source.size,
                        "sha256": source.sha256, "binding": binding})
    counts = {category: sum(row["category"] == category for row in entries)
              for category in categories.values()}
    manifest = {
        "schema_version": 1, "classification": CLASSIFICATION,
        "production_completion_or_visual_qa_evidence": False,
        "reference_fixture_role": "synthetic arithmetic fixtures for executed R reference audit only; not production outcomes",
        "file_count": 55, "total_bytes": sum(s.size for s in sources.values()),
        "category_counts": counts, "files": entries,
        "bindings": {"production_metadata_sha256": {name: snap.sha256 for name, snap in sorted(prod.items())},
                     "extension_freeze_content_sha256": freeze["content_sha256"], **domain},
        "not_copied_by_this_helper": ["installed R environment", "measured raw data and LICENSE",
                                      "matched parquet", "METABRIC source report",
                                      "production results/completion", "reproduction receipts", "visual QA",
                                      "synthetic/preflight release verdicts", "later optional validation logs"],
    }
    manifest["content_sha256"] = _canonical_hash(manifest)
    # Validate every source before creating any target tree. The temporary tree is
    # private and published only after every copied payload has been rehashed.
    target.parent.mkdir(parents=True, exist_ok=True)
    _regular_path(target.parent, directory=True)
    stage = Path(tempfile.mkdtemp(prefix=".audit-support-", dir=target.parent))
    try:
        for name, source in sources.items():
            _copy_snapshot(source, stage / name)
        _verify_copies(stage, sources)
        payload = (json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
        with (stage / MANIFEST_NAME).open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        manifest_snapshot = _snapshot(stage / MANIFEST_NAME)
        _verify_copies(stage, sources, manifest=manifest_snapshot)
        for source in [*sources.values(), *prod.values(), external_report]:
            _regular_path(source.path)
            _require(_signature(source.path.stat()) == source.signature,
                     f"source changed before publication: {source.path}")
        _atomic_new_directory(stage, target)
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return {"classification": CLASSIFICATION, "manifest": MANIFEST_NAME,
            "manifest_sha256": manifest_snapshot.sha256,
            "manifest_content_sha256": manifest["content_sha256"], "file_count": 55,
            "category_counts": counts, "total_bytes": manifest["total_bytes"]}


def main() -> None:
    """Command-line entry point: stage the audit and preparation artefacts and print the JSON result."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("production", "reference-root", "preparation", "target"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    result = stage_audit_support(args.production, args.reference_root, args.preparation, args.target)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
