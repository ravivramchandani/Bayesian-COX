"""Record reproducible run inputs and host metadata for analysis pipelines.

``build_run_manifest`` combines configuration, seeds, Git state, dependency
versions, hardware and input digests. ``sha256_file`` hashes file bytes and
``canonical_json_hash`` hashes a stable JSON (JavaScript Object Notation)
encoding using SHA-256 (the 256-bit Secure Hash Algorithm).
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

DIRECT_DEPENDENCIES = (
    "numpy",
    "scipy",
    "pandas",
    "pyyaml",
    "pymc",
    "arviz",
    "scikit-survival",
    "lifelines",
    "shap",
    "matplotlib",
    "seaborn",
    "torch",
    "pycox",
    "torchtuples",
)


def sha256_file(path: str | Path) -> str:
    """Return a file's SHA-256 digest by reading one-megabyte blocks.

    Args:
        path: File whose exact bytes are hashed.

    Returns:
        A 64-character hexadecimal digest.

    Raises:
        OSError: The file cannot be opened or read.
    """
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json_hash(value: Any) -> str:
    """Hash JSON-compatible data with sorted keys and a compact Unicode encoding.

    Args:
        value: JSON-compatible data, containing no non-finite numbers.

    Returns:
        A hexadecimal SHA-256 digest of the encoded value.

    Raises:
        TypeError: A value cannot be encoded as JSON.
        ValueError: A value is non-finite or has a circular reference.
    """
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _git(project_root: Path, *args: str) -> str | None:
    """Run Git in the project root, returning stripped stdout or None on failure."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip()


def dependency_versions(names: Iterable[str] = DIRECT_DEPENDENCIES) -> dict[str, str]:
    """Read installed distribution versions without importing those packages.

    Args:
        names: Distribution names; defaults to the direct analysis dependencies.

    Returns:
        A name-to-version mapping, with ``"NOT_INSTALLED"`` for missing packages.
    """
    versions: dict[str, str] = {}
    for name in names:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "NOT_INSTALLED"
    return versions


def file_hashes(project_root: str | Path, relative_paths: Iterable[str]) -> dict[str, str]:
    """Hash a sorted, deduplicated collection of paths relative to a project root.

    Args:
        project_root: Base directory for the named files.
        relative_paths: Input names expected to be relative to that directory.

    Returns:
        A path-to-digest mapping, with ``"MISSING"`` for paths that are not files.

    Raises:
        OSError: An existing file cannot be read.
    """
    root = Path(project_root).resolve()
    hashes: dict[str, str] = {}
    for relative in sorted(set(relative_paths)):
        path = root / relative
        hashes[relative] = sha256_file(path) if path.is_file() else "MISSING"
    return hashes


def build_run_manifest(
    project_root: str | Path,
    *,
    command: list[str],
    seeds: dict[str, int | list[int]],
    input_files: Iterable[str],
    run_config: dict[str, Any],
) -> dict[str, Any]:
    """Build a machine-readable identity record for one analysis run.

    Dates belong in the result directory name or an outer provenance record.
    The content is deterministic when all recorded inputs, Git state, command,
    seeds, configuration, software and host metadata remain unchanged. Missing
    files or dependencies are recorded rather than rejected here.

    Args:
        project_root: Checkout whose history and relative input files are recorded.
        command: Command arguments to store; this function does not run them.
        seeds: Named integer seeds or lists of integer seeds used by the run.
        input_files: Relative input paths to hash.
        run_config: JSON-compatible configuration to record and hash.

    Returns:
        A manifest containing input/configuration/dependency hashes, Git state,
        software and hardware metadata, and a hash of the manifest itself.

    Raises:
        OSError: An existing input cannot be read.
        TypeError: Configuration cannot be encoded as JSON.
        ValueError: Configuration contains non-finite numbers or circular references.
    """
    root = Path(project_root).resolve()
    status = _git(root, "status", "--porcelain")
    inputs = file_hashes(root, input_files)
    dependencies = dependency_versions()
    config_hash = canonical_json_hash(run_config)
    environment_hash = canonical_json_hash(dependencies)

    manifest: dict[str, Any] = {
        "schema_version": "1.0.0",
        "project_root_name": root.name,
        "command": command,
        "seeds": seeds,
        "run_config": run_config,
        "config_sha256": config_hash,
        "input_sha256": inputs,
        "code": {
            "git_commit": _git(root, "rev-parse", "HEAD"),
            "git_dirty": bool(status),
            "git_changed_paths": status.splitlines() if status else [],
        },
        "environment": {
            "python": platform.python_version(),
            "executable_name": Path(sys.executable).name,
            "dependencies": dependencies,
            "dependency_set_sha256": environment_hash,
        },
        "hardware": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "logical_cpu_count": os.cpu_count(),
        },
    }
    manifest["manifest_content_sha256"] = canonical_json_hash(manifest)
    return manifest
