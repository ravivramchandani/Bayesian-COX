"""Verify historical evidence against its Git checkpoint and live study inputs.

The frozen analysis records its original code, including retired modules.
``checkpoint_blob`` reads historical file bytes without changing the checkout;
``verify_checkpoint_inputs`` checks their SHA-256 (256-bit Secure Hash
Algorithm) digests. ``verify_frozen_evidence`` also checks the live freeze and
protected study inputs. Git-tracked text inputs may use either LF or CRLF
working-tree line endings; their normalized content must match the checkpoint.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from src.utils.reproducibility import canonical_json_hash, sha256_file

CHECKPOINT_COMMIT = "44b608572a5e1006a05ed5e3c4985471b2ba594d"
LIVE_STUDY_INPUTS = frozenset(
    {
        "config/confirmatory.yaml",
        "config/datasets.yaml",
        "data/manifest.yaml",
        "conda-lock.yml",
        "conda-lock.yml.sha256",
        "conda-lock-virtual-packages.yml",
    }
)


def checkpoint_blob(
    project_root: Path, relative: str, *, checkpoint: str = CHECKPOINT_COMMIT
) -> bytes:
    """Read required file bytes from Git without checking out historical code.

    Args:
        project_root: Checkout containing the requested Git history.
        relative: Non-empty repository-relative path without parent traversal.
        checkpoint: Commit or other Git revision containing that file.

    Returns:
        The exact bytes stored at the checkpoint path.

    Raises:
        ValueError: The path is absolute, empty or contains ``..`` components.
        RuntimeError: Git cannot read the required checkpoint input.
    """
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"invalid checkpoint input path: {relative!r}")
    try:
        result = subprocess.run(
            ["git", "show", f"{checkpoint}:{relative}"],
            cwd=project_root,
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(
            f"required checkpoint input unavailable: {checkpoint}:{relative}"
        ) from exc
    return result.stdout


def _text_sha256(path: Path) -> str:
    """Hash UTF-8 text after normalizing Windows CRLF to Git's LF bytes."""
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def verify_checkpoint_inputs(
    project_root: Path,
    expected: Mapping[str, str],
    *,
    checkpoint: str = CHECKPOINT_COMMIT,
) -> None:
    """Reject missing or altered checkpoint blobs in a recorded input map.

    Args:
        project_root: Checkout containing the checkpoint history.
        expected: Repository-relative paths mapped to expected SHA-256 digests.
        checkpoint: Git revision against which every file is verified.

    Returns:
        None when every recorded blob matches.

    Raises:
        ValueError: A recorded path is invalid.
        RuntimeError: The map is empty, a blob is unavailable, or a digest differs.
    """
    if not expected:
        raise RuntimeError("frozen evidence has no recorded inputs")
    changed = []
    for relative, digest in sorted(expected.items()):
        data = checkpoint_blob(project_root, relative, checkpoint=checkpoint)
        if hashlib.sha256(data).hexdigest() != digest:
            changed.append(relative)
    if changed:
        raise RuntimeError("frozen checkpoint inputs differ: " + ", ".join(changed))


def verify_frozen_evidence(
    project_root: Path,
    expected: Mapping[str, str] | None = None,
    *,
    checkpoint: str = CHECKPOINT_COMMIT,
) -> dict[str, Any]:
    """Verify the historical freeze and the live protocol, raw data and lock.

    Args:
        project_root: Checkout containing both the checkpoint history and live inputs.
        expected: A source run's recorded input map, when checking that run.
        checkpoint: Historical Git commit; production uses the pinned release commit.

    Returns:
        The original freeze record, whose content hash remains unchanged.

    Raises:
        ValueError: A checkpoint input path is invalid or freeze JSON is malformed.
        RuntimeError: The freeze lacks a valid hash, result-blind attestation
            or input map, expected inputs differ, or any protected bytes differ.
    """
    freeze_bytes = checkpoint_blob(
        project_root, "config/protocol_freeze.json", checkpoint=checkpoint
    )
    freeze = json.loads(freeze_bytes)
    unhashed = dict(freeze)
    claimed = unhashed.pop("freeze_content_sha256", None)
    if claimed != canonical_json_hash(unhashed):
        raise RuntimeError("checkpoint protocol freeze content hash is invalid")
    if not freeze.get("no_comparative_effects_inspected_before_freeze", False):
        raise RuntimeError("checkpoint freeze lacks the result-blind rehearsal attestation")
    recorded = freeze.get("frozen_input_sha256")
    if not isinstance(recorded, dict) or not recorded:
        raise RuntimeError("checkpoint freeze has no recorded input map")
    if expected is not None and dict(expected) != recorded:
        raise RuntimeError("run manifest inputs differ from checkpoint protocol freeze")
    verify_checkpoint_inputs(project_root, recorded, checkpoint=checkpoint)

    live_freeze = project_root / "config/protocol_freeze.json"
    if (
        not live_freeze.is_file()
        or live_freeze.read_bytes().replace(b"\r\n", b"\n") != freeze_bytes
    ):
        raise RuntimeError("live config/protocol_freeze.json differs from checkpoint")
    protected = {
        name for name in recorded if name in LIVE_STUDY_INPUTS or name.startswith("data/raw/")
    }
    changed = []
    for name in sorted(protected):
        path = project_root / name
        if not path.is_file():
            changed.append(name)
        elif name.startswith("data/raw/"):
            if sha256_file(path) != recorded[name]:
                changed.append(name)
        elif _text_sha256(path) != recorded[name]:
            changed.append(name)
    if changed:
        raise RuntimeError("live frozen study inputs differ: " + ", ".join(changed))
    return freeze
