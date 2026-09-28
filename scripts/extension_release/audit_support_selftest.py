#!/usr/bin/env python3
"""Focused artificial fixtures for the bounded audit-support staging helper."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import audit_support as support


def sha(data: bytes) -> str:
    """Return the SHA-256 hex digest of ``data``."""
    return hashlib.sha256(data).hexdigest()


def write(path: Path, data: bytes) -> None:
    """Write bytes to ``path``, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def write_json(path: Path, data: object) -> None:
    """Write indented, key-sorted JSON to ``path``."""
    write(path, (json.dumps(data, sort_keys=True, indent=2) + "\n").encode())


def git_blob(data: bytes) -> str:
    """Return the Git blob SHA-1 of ``data``, as Git computes it for a committed file."""
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


class Fixture:
    """Tiny coherent synthetic source documents, never measured patient data."""

    def __init__(self, root: Path):
        """Create the synthetic production, reference and preparation trees, and record the hash of each captured file."""
        self.production = root / "production-code"
        self.reference = root / "reference"
        self.preparation = root / "preparation"
        self.target = root / "release/audit"
        for folder in (self.production, self.reference, self.preparation):
            folder.mkdir()
        for name in support.REFERENCE_PATHS:
            write(self.reference / "catalytic" / name, f"artificial reference: {name}\n".encode())
        self.registry = {name: sha((self.reference / "catalytic" / name).read_bytes())
                         for name in support.REFERENCE_PATHS}
        write_json(self.production / support.REGISTRY, self.registry)
        write(self.reference / "catalytic/SHA256SUMS.json",
              (self.production / support.REGISTRY).read_bytes())
        for name in support.CAPTURE_SHA256:
            if name == "catalytic/SHA256SUMS.json":
                continue
            write(self.source(name), f"artificial supporting artifact: {name}\n".encode())
        # Unselected files must remain unselected, even if they look evidential.
        write(self.reference / "catalytic/r-env/unselected.txt", b"installed environment excluded\n")
        write(self.reference / "metabric/raw/unselected.txt", b"measured raw data excluded\n")
        write(self.preparation / "synthetic_preflight_verdict.json", b"{}\n")
        lock = b"artificial Apple Silicon dependency lock\n"
        write(self.production / "conda-lock.yml", lock)
        write_json(self.preparation / "implementation_environment_verification.json",
                   {"status": "ok", "platform": {"machine": "arm64"}, "lock_sha256": sha(lock)})
        matched_sha = sha(b"artificial matched data identity, no dataset created")
        for name in ("training_compute_profile.json", "training_compute_profile_compact.json",
                     "training_compute_profile_final.json"):
            write_json(self.preparation / name, {"purpose": support.PROFILE_PURPOSE,
                                                "matched_sha256": matched_sha, "variant": name})
        pair_data = b"accession_1,accession_2\nARTIFICIAL_A,ARTIFICIAL_B\n"
        pair_path = self.reference / "metabric/known_same_individual_accession_pairs.csv"
        write(pair_path, pair_data)
        supplement = self.reference / "metabric/curtis_2012_supplement_methods.pdf"
        write(supplement, b"artificial supplement bytes; not a real PDF\n")
        schema = {"artificial_alignment": {"n_samples": 2}}
        gene = {"artificial_gene_identity": 3}
        duplicate = {"known_2012_same_individual_pairs": 1}
        for name, value in (("schema_alignment_audit.json", schema),
                            ("gene_identity_audit.json", gene),
                            ("known_biological_duplicate_audit.json", duplicate)):
            write_json(self.reference / "metabric" / name, value)
        api = "https://api.github.com/repos/cBioPortal/datahub"
        raw = f"https://raw.githubusercontent.com/cBioPortal/datahub/{support.COMMIT}/public/brca_metabric/"
        media = f"https://media.githubusercontent.com/media/cBioPortal/datahub/{support.COMMIT}/public/brca_metabric/"
        rows = []
        listing = []
        lfs_payloads = {}
        for name in sorted(support.RAW_NAMES | {support.EXCLUDED_NAME}):
            payload = f"artificial measured payload identity: {name}\n".encode()
            lfs = name in support.LFS_NAMES or name == support.EXCLUDED_NAME
            pointer = (f"version https://git-lfs.github.com/spec/v1\noid sha256:{sha(payload)}\n"
                       f"size {len(payload)}\n").encode()
            git_sha = git_blob(pointer if lfs else payload)
            listing.append({"name": name, "sha": git_sha, "path": f"public/brca_metabric/{name}",
                            "type": "file", "download_url": raw + name})
            if lfs:
                write(self.reference / "metabric/lfs_pointers" / name, pointer)
                lfs_payloads[name] = {"git_blob_sha1": git_sha, "lfs_sha256": sha(payload),
                                      "lfs_size": len(payload)}
            if name == support.EXCLUDED_NAME:
                continue
            row = {"name": name, "git_blob_sha1": git_sha, "raw_url": raw + name,
                   "git_blob_verified": True, "payload_url": (media if lfs else raw) + name,
                   "downloaded_sha256": sha(payload), "downloaded_size": len(payload),
                   "local_path": f"/historical/host/metabric/raw/{name}",
                   "lfs_verified": True if lfs else None}
            if lfs:
                row.update({"lfs_sha256": sha(payload), "lfs_size": len(payload)})
            rows.append(row)
        tree = hashlib.sha1(b"artificial git tree").hexdigest()
        write_json(self.reference / "metabric/github_commit_metadata.json",
                   {"sha": support.COMMIT, "tree": {"sha": tree},
                    "url": f"{api}/git/commits/{support.COMMIT}"})
        write_json(self.reference / "metabric/github_directory_manifest.json", listing)
        write_json(self.reference / "metabric/download_manifest.json", rows)
        report = {
            "study_id": "brca_metabric", "repository": support.REPOSITORY,
            "commit": support.COMMIT, "commit_verified": True, "commit_tree_sha1": tree,
            "directory_manifest_url": f"{api}/contents/public/brca_metabric?ref={support.COMMIT}",
            "model_fits_performed": False, "outcome_performance_analysis_performed": False,
            "data_files": rows,
            "excluded_zscore_profile": {"data_name": support.EXCLUDED_NAME,
                                         "payload_downloaded": False,
                                         "raw_pointer_url": raw + support.EXCLUDED_NAME,
                                         **lfs_payloads[support.EXCLUDED_NAME]},
            "audits": {"schema_alignment": schema, "gene_identity": gene,
                       "known_biological_duplicates": {**duplicate,
                           "source_pair_mapping_path": "/historical/host/pairs.csv",
                           "source_pair_mapping_sha256": sha(pair_data)}},
            "platform_and_processing": {"supplement_sha256": sha(supplement.read_bytes())},
        }
        write_json(self.reference / "metabric/metabric_source_report.json", report)
        write_json(self.production / support.SOURCE_REPORT, report)
        matched = {"matched_sha256": matched_sha, "known_pairs_sha256": sha(pair_data),
                   "source_sha256": {row["name"]: row["downloaded_sha256"] for row in rows
                                     if row["name"] in support.LFS_NAMES}}
        write_json(self.production / support.MATCHED_MANIFEST, matched)
        write(self.production / support.PROFILE,
              (self.preparation / "training_compute_profile_final.json").read_bytes())
        write(self.production / support.REFERENCE_FIXTURE,
              (self.reference / "catalytic/reference_fixtures.json").read_bytes())
        write(self.production / support.PAIR_FIXTURE, pair_data)
        for name in support.FROZEN_PATHS:
            path = self.production / name
            if not path.exists():
                write(path, f"artificial frozen metadata: {name}\n".encode())
        self.freeze = {"classification": "post_hoc_extension", "version": 1,
                       "sha256": {name: sha((self.production / name).read_bytes())
                                  for name in sorted(support.FROZEN_PATHS)}}
        self.freeze["content_sha256"] = support._canonical_hash(self.freeze)
        write_json(self.production / support.FREEZE, self.freeze)
        write_json(self.production / support.VALIDATION,
                   {"environment_verification_sha256": sha((self.preparation / "implementation_environment_verification.json").read_bytes()),
                    "tests": {"full_log_sha256": sha((self.preparation / "implementation_full_tests.log").read_bytes()), "passed": 1},
                    "extension_freeze_content_sha256": self.freeze["content_sha256"],
                    "frozen_primary_changed": False})
        self.pins = {name: sha(self.source(name).read_bytes()) for name in support.CAPTURE_SHA256}

    def source(self, name: str) -> Path:
        """Return the fixture path of a captured artefact name."""
        prefix, rest = name.split("/", 1)
        return (self.preparation / rest if prefix == "preparation"
                else self.reference / prefix / rest)

    def refresh_pin(self, name: str) -> None:
        """Re-record a captured file's hash after a test deliberately edits it."""
        self.pins[name] = sha(self.source(name).read_bytes())

    def stage(self) -> dict:
        # Only the artificial-test runtime changes the internal capture pins.
        # The public API/CLI exposes no expected-hash override.
        """Run the staging helper with this fixture's hashes in place of the real capture hashes."""
        with patch.object(support, "CAPTURE_SHA256", self.pins):
            return support.stage_audit_support(self.production, self.reference,
                                               self.preparation, self.target)


class AuditSupportTests(unittest.TestCase):
    """Behaviour of the audit-support staging helper on coherent and deliberately altered fixtures."""
    def setUp(self) -> None:
        """Build a fresh fixture in a temporary directory."""
        self.temporary = tempfile.TemporaryDirectory(prefix="audit-support-selftest-")
        # macOS exposes /var as an OS symlink; resolve this trusted test base,
        # while source/target symlinks within fixtures remain explicitly refused.
        self.fixture = Fixture(Path(self.temporary.name).resolve())

    def tearDown(self) -> None:
        """Remove the temporary directory."""
        self.temporary.cleanup()

    def assert_failed_cleanly(self, text: str) -> None:
        """Staging must fail with ``text`` and leave neither a target nor staging leftovers."""
        with self.assertRaisesRegex(ValueError, text):
            self.fixture.stage()
        self.assertFalse(self.fixture.target.exists())
        self.assertEqual(list(self.fixture.target.parent.glob(".audit-support-*")), [])

    def test_coherent_success_exact_inventory_and_hashes(self) -> None:
        """A coherent fixture stages exactly the expected files with matching hashes."""
        result = self.fixture.stage()
        self.assertEqual(result["file_count"], 55)
        self.assertEqual(sorted(result["category_counts"].values()), [9, 18, 28])
        path = self.fixture.target / support.MANIFEST_NAME
        manifest = json.loads(path.read_text())
        self.assertEqual(sha(path.read_bytes()), result["manifest_sha256"])
        self.assertEqual(support._canonical_hash({k: v for k, v in manifest.items()
                                                 if k != "content_sha256"}),
                         result["manifest_content_sha256"])
        actual = {p.relative_to(self.fixture.target).as_posix()
                  for p in self.fixture.target.rglob("*") if p.is_file()}
        self.assertEqual(actual, {row["path"] for row in manifest["files"]} | {support.MANIFEST_NAME})
        self.assertFalse(manifest["production_completion_or_visual_qa_evidence"])
        self.assertEqual(manifest["classification"], support.CLASSIFICATION)
        self.assertEqual(manifest["total_bytes"], sum(row["bytes"] for row in manifest["files"]))
        for row in manifest["files"]:
            data = (self.fixture.target / row["path"]).read_bytes()
            self.assertEqual(row["bytes"], len(data))
            self.assertEqual(row["sha256"], sha(data))
        self.assertFalse(any("r-env/" in p or "raw/" in p or "preflight" in p for p in actual))

    def test_altered_registry_pinned_artifact_rejected(self) -> None:
        """A changed hash-pinned artefact is rejected."""
        write(self.fixture.reference / "catalytic/execute_reference.R", b"altered\n")
        self.assert_failed_cleanly("pinned audit artifact changed: catalytic/execute_reference.R")

    def test_altered_fixed_capture_rejected(self) -> None:
        """A changed fixed capture file is rejected."""
        write(self.fixture.preparation / "implementation_full_tests.log", b"altered\n")
        self.assert_failed_cleanly("pinned audit artifact changed: preparation/implementation_full_tests.log")

    def test_altered_frozen_metadata_rejected(self) -> None:
        """Changed frozen metadata is rejected."""
        write(self.fixture.production / "config/extensions.yaml", b"altered\n")
        self.assert_failed_cleanly("frozen production metadata changed")

    def test_altered_receipt_environment_binding_rejected(self) -> None:
        """A receipt bound to a different environment is rejected."""
        path = self.fixture.production / support.VALIDATION
        receipt = json.loads(path.read_text())
        receipt["environment_verification_sha256"] = "0" * 64
        write_json(path, receipt)
        self.assert_failed_cleanly("implementation environment/tests receipt differs")

    def test_altered_domain_download_link_rejected_after_pin_passes(self) -> None:
        """A wrong source download link is rejected even when the file hashes match."""
        name = "metabric/download_manifest.json"
        data = json.loads(self.fixture.source(name).read_text())
        data[0]["downloaded_size"] += 1
        write_json(self.fixture.source(name), data)
        self.fixture.refresh_pin(name)
        self.assert_failed_cleanly("download manifest differs")

    def test_altered_domain_audit_rejected_after_pin_passes(self) -> None:
        """An altered domain audit is rejected even when the file hashes match."""
        name = "metabric/schema_alignment_audit.json"
        write_json(self.fixture.source(name), {"artificial_alignment": {"n_samples": 999}})
        self.fixture.refresh_pin(name)
        self.assert_failed_cleanly("source report and audit disagree")

    def test_altered_domain_lfs_binding_rejected_after_pin_passes(self) -> None:
        """A wrong Git LFS binding is rejected even when the file hashes match."""
        name = "metabric/lfs_pointers/data_mrna_illumina_microarray.txt"
        path = self.fixture.source(name)
        data = path.read_bytes()
        data = data.replace(b"oid sha256:", b"oid sha256:0", 1)
        # Keep the syntax valid but alter the OID/Git pointer identity.
        start = data.index(b"oid sha256:") + len(b"oid sha256:")
        data = data[:start + 64] + data[start + 65:]
        write(path, data)
        self.fixture.refresh_pin(name)
        self.assert_failed_cleanly("LFS pointer Git/OID/size binding differs")

    def test_altered_copied_artifact_rejected_before_publication(self) -> None:
        """A copy that differs from its source is caught before anything is published."""
        original = support._copy_snapshot

        def corrupt(source: support.Snapshot, target: Path) -> None:
            """Copy normally, then corrupt one copied file."""
            original(source, target)
            if target.name == "execute_reference.R":
                target.write_bytes(target.read_bytes() + b"corruption\n")

        with patch.object(support, "_copy_snapshot", corrupt):
            self.assert_failed_cleanly("copied audit artifact differs: catalytic/execute_reference.R")

    def test_source_changed_after_validation_rejected(self) -> None:
        """A source file edited after validation is rejected."""
        original = support._copy_snapshot

        def mutate(source: support.Snapshot, target: Path) -> None:
            """Edit one source file just before it is copied."""
            if source.path.name == "execute_reference.R":
                source.path.write_bytes(source.path.read_bytes() + b"changed\n")
            original(source, target)

        with patch.object(support, "_copy_snapshot", mutate):
            self.assert_failed_cleanly("source changed since validation")

    def test_linked_source_rejected(self) -> None:
        """A source that is a symbolic link is rejected."""
        path = self.fixture.source("catalytic/r-env-install.log")
        original = path.with_name("saved-install.log")
        path.rename(original)
        path.symlink_to(original.name)
        self.assert_failed_cleanly("linked path refused")

    def test_existing_target_refused_without_overwrite(self) -> None:
        """An existing target is refused and left unchanged."""
        self.fixture.target.mkdir(parents=True)
        sentinel = self.fixture.target / "existing.txt"
        sentinel.write_bytes(b"preserve\n")
        with self.assertRaisesRegex(ValueError, "fresh target required"):
            self.fixture.stage()
        self.assertEqual(sentinel.read_bytes(), b"preserve\n")

    def test_target_created_during_publish_refused_without_overwrite(self) -> None:
        """A target that appears during publication is refused and not overwritten."""
        original = support._atomic_new_directory

        def race(source: Path, target: Path) -> None:
            """Create the target just before the atomic rename, simulating a race."""
            target.mkdir()
            (target / "existing.txt").write_bytes(b"preserve\n")
            original(source, target)

        with patch.object(support, "_atomic_new_directory", race):
            with self.assertRaises(FileExistsError):
                self.fixture.stage()
        self.assertEqual((self.fixture.target / "existing.txt").read_bytes(), b"preserve\n")
        self.assertEqual(list(self.fixture.target.parent.glob(".audit-support-*")), [])

    def test_target_parent_traversal_cannot_bypass_overlap_check(self) -> None:
        """A target path using ``..`` cannot escape the source/target overlap check."""
        self.fixture.target = self.fixture.production.parent / "missing/../production-code/audit"
        self.assert_failed_cleanly("parent traversal refused")
        self.assertFalse((self.fixture.production / "audit").exists())

    def test_linked_target_ancestor_rejected_before_creation(self) -> None:
        """A target whose ancestor is a link is rejected before anything is created."""
        alias = self.fixture.production.parent / "linked-output"
        alias.symlink_to(self.fixture.production, target_is_directory=True)
        self.fixture.target = alias / "new/audit"
        self.assert_failed_cleanly("target ancestor refused")
        self.assertFalse((self.fixture.production / "new").exists())

    def test_case_alias_cannot_bypass_overlap_check(self) -> None:
        """On a case-insensitive volume, an upper-case alias of a source root cannot bypass the overlap check."""
        alias = self.fixture.production.with_name(self.fixture.production.name.upper())
        if not alias.is_dir() or not alias.samefile(self.fixture.production):
            self.skipTest("case-insensitive volume required")
        self.fixture.target = alias / "audit"
        self.assert_failed_cleanly("target overlaps a source root by directory identity")
        self.assertFalse((self.fixture.production / "audit").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
