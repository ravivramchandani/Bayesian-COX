"""Reproducibility metadata and content hashing for frozen analysis runs."""

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
    """Return the SHA-256 digest of a file without loading it into memory."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json_hash(value: Any) -> str:
    """Hash a JSON-compatible value using a stable canonical encoding."""
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _git(project_root: Path, *args: str) -> str | None:
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
    """Return installed versions for the direct, analysis-critical packages."""
    versions: dict[str, str] = {}
    for name in names:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "NOT_INSTALLED"
    return versions


def file_hashes(project_root: str | Path, relative_paths: Iterable[str]) -> dict[str, str]:
    """Hash required run inputs, recording missing files explicitly."""
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
    """Build a complete, machine-readable manifest for one analysis run.

    Dates belong in the result directory name or an outer provenance record.
    The content below is deterministic for an unchanged checkout, command and
    configuration, which makes rerun comparisons meaningful.
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
