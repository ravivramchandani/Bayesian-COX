"""Historical evidence must survive code changes and reject altered study inputs.

Covers ``verify_frozen_evidence`` in ``src/utils/frozen_evidence.py`` against a
throwaway Git repository whose single commit stands in for the evidence
checkpoint. Frozen inputs are read from that commit, so source files may change
in the working tree, while the protocol, raw-data, lock and freeze files must
keep their frozen bytes (INV-008, ADR-030).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from src.utils.frozen_evidence import verify_frozen_evidence
from src.utils.reproducibility import canonical_json_hash, sha256_file


@pytest.fixture
def frozen_checkout(tmp_path: Path) -> tuple[Path, str, dict[str, str]]:
    """Commit a minimal frozen study to a new Git repository.

    Returns:
        The repository root, the commit hash and the recorded input hashes.
    """
    # One source module, which may later change, and one protocol, raw-data and
    # lock file, which must keep their bytes in the live tree.
    contents = {
        "src/original.py": "VALUE = 1\n",
        "config/confirmatory.yaml": "analysis: original\n",
        "data/raw/cohort.csv": "time,event\n1,1\n",
        "conda-lock.yml": "locked: true\n",
    }
    for relative, text in contents.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
    hashes = {relative: sha256_file(tmp_path / relative) for relative in contents}
    # The verifier accepts a freeze only with a valid self-hash and the
    # result-blind attestation.
    freeze = {"frozen_input_sha256": hashes, "no_comparative_effects_inspected_before_freeze": True}
    freeze["freeze_content_sha256"] = canonical_json_hash(freeze)
    (tmp_path / "config/protocol_freeze.json").write_text(json.dumps(freeze))
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.test",
            "commit",
            "-qm",
            "freeze",
        ],
        cwd=tmp_path,
        check=True,
    )
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, check=True, capture_output=True, text=True
    ).stdout.strip()
    return tmp_path, commit, hashes


def test_historical_evidence_survives_deleted_and_added_source(frozen_checkout) -> None:
    """Deleted or added source files leave checkpoint-verified evidence valid (INV-008, ADR-030)."""
    root, commit, hashes = frozen_checkout
    (root / "src/original.py").unlink()
    (root / "src/refactored.py").write_text("VALUE = 1\n")
    assert verify_frozen_evidence(root, hashes, checkpoint=commit)["frozen_input_sha256"] == hashes


@pytest.mark.parametrize(
    "relative",
    [
        "config/confirmatory.yaml",
        "data/raw/cohort.csv",
        "conda-lock.yml",
        "config/protocol_freeze.json",
    ],
)
def test_changed_live_study_input_is_rejected(frozen_checkout, relative: str) -> None:
    """Changed live protocol, raw-data, lock or freeze bytes are rejected (INV-008, ADR-030)."""
    root, commit, hashes = frozen_checkout
    (root / relative).write_text("changed\n")
    with pytest.raises(RuntimeError, match="live"):
        verify_frozen_evidence(root, hashes, checkpoint=commit)


def test_crlf_worktree_text_inputs_match_the_frozen_git_content(frozen_checkout) -> None:
    """Windows checkout line endings do not change frozen text input identity."""
    root, commit, hashes = frozen_checkout
    for relative in ("config/confirmatory.yaml", "conda-lock.yml", "config/protocol_freeze.json"):
        path = root / relative
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    assert verify_frozen_evidence(root, hashes, checkpoint=commit)["frozen_input_sha256"] == hashes


def test_forged_manifest_input_map_is_rejected(frozen_checkout) -> None:
    """A run's recorded input map must equal the checkpoint freeze's map exactly (INV-008)."""
    root, commit, hashes = frozen_checkout
    forged = {**hashes, "src/original.py": "0" * 64}
    with pytest.raises(RuntimeError, match="manifest inputs differ"):
        verify_frozen_evidence(root, forged, checkpoint=commit)


def test_missing_checkpoint_is_rejected(frozen_checkout) -> None:
    """A checkpoint commit absent from the repository fails verification (INV-008)."""
    root, _, hashes = frozen_checkout
    # A well-formed 40-hex commit name that does not exist in the repository.
    with pytest.raises(RuntimeError, match="checkpoint input unavailable"):
        verify_frozen_evidence(root, hashes, checkpoint="0" * 40)
