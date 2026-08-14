"""Verify that the active environment matches the committed macOS arm64 lock."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import json
import platform
import subprocess
import sys
import warnings
from pathlib import Path
from typing import Any

import yaml

EXPECTED_PLATFORM = "osx-arm64"
MINIMUM_MACOS = (14, 0)
DIRECT_IMPORTS = {
    "arviz": "arviz",
    "h5py": "h5py",
    "lifelines": "lifelines",
    "matplotlib": "matplotlib",
    "numpy": "numpy",
    "pandas": "pandas",
    "pycox": "pycox",
    "pymc": "pymc",
    "pytorch": "torch",
    "pyyaml": "yaml",
    "scikit-survival": "sksurv",
    "scipy": "scipy",
    "seaborn": "seaborn",
    "shap": "shap",
    "torchtuples": "torchtuples",
}


class VerificationError(RuntimeError):
    """Raised when the environment or lock fails a reproducibility check."""


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest of a file."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_lock(lock_path: Path) -> dict[str, Any]:
    """Load a conda-lock YAML document and validate its top-level type."""

    document = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise VerificationError(f"Lock is not a YAML mapping: {lock_path}")
    return document


def validate_lock_structure(lock_path: Path, hash_path: Path) -> dict[str, Any]:
    """Validate platform, source and package hashes in the committed lock."""

    lock = load_lock(lock_path)
    metadata = lock.get("metadata", {})
    platforms = metadata.get("platforms")
    if platforms != [EXPECTED_PLATFORM]:
        raise VerificationError(
            f"Lock platforms must be [{EXPECTED_PLATFORM!r}], found {platforms!r}"
        )

    actual_digest = sha256_file(lock_path)
    hash_parts = hash_path.read_text(encoding="utf-8").strip().split()
    if len(hash_parts) != 2 or hash_parts[1] != lock_path.name:
        raise VerificationError(f"Malformed lock digest file: {hash_path}")
    if hash_parts[0] != actual_digest:
        raise VerificationError(
            f"Lock SHA-256 mismatch: expected {hash_parts[0]}, calculated {actual_digest}"
        )

    source_metadata = metadata.get("inputs_metadata", {})
    for relative_name, source in source_metadata.items():
        source_path = lock_path.parent / relative_name
        expected = source.get("sha256") if isinstance(source, dict) else None
        if not source_path.is_file() or expected != sha256_file(source_path):
            raise VerificationError(f"Locked input hash mismatch: {source_path}")

    packages = lock.get("package")
    if not isinstance(packages, list) or not packages:
        raise VerificationError("Lock contains no packages")
    missing_hashes = [
        package.get("name", "<unnamed>")
        for package in packages
        if not package.get("url") or not package.get("hash", {}).get("sha256")
    ]
    if missing_hashes:
        raise VerificationError(f"Packages without URL/SHA-256: {missing_hashes}")

    keys = [(package["manager"], package["name"], package["platform"]) for package in packages]
    if len(keys) != len(set(keys)):
        raise VerificationError("Lock contains duplicate manager/name/platform package records")

    return {
        "document": lock,
        "lock_sha256": actual_digest,
        "package_count": len(packages),
        "conda_package_count": sum(package["manager"] == "conda" for package in packages),
        "pip_package_count": sum(package["manager"] == "pip" for package in packages),
    }


def _macos_version() -> tuple[int, ...]:
    value = platform.mac_ver()[0]
    try:
        return tuple(int(part) for part in value.split("."))
    except ValueError as error:
        raise VerificationError(f"Cannot parse macOS version {value!r}") from error


def _validate_host() -> dict[str, str]:
    machine = platform.machine().lower()
    if sys.platform != "darwin" or machine != "arm64":
        raise VerificationError(
            f"This lock supports macOS arm64 only; found {sys.platform}/{machine}"
        )
    macos = _macos_version()
    if macos < MINIMUM_MACOS:
        minimum = ".".join(map(str, MINIMUM_MACOS))
        raise VerificationError(f"macOS {minimum}+ is required; found {platform.mac_ver()[0]}")
    return {"system": platform.system(), "machine": machine, "macos": platform.mac_ver()[0]}


def _installed_conda_records() -> dict[str, dict[str, Any]]:
    metadata_dir = Path(sys.prefix) / "conda-meta"
    if not metadata_dir.is_dir():
        raise VerificationError(f"Active Python is not in a conda environment: {sys.prefix}")
    records: dict[str, dict[str, Any]] = {}
    for path in metadata_dir.glob("*.json"):
        record = json.loads(path.read_text(encoding="utf-8"))
        records[record["name"]] = record
    return records


def _verify_conda_packages(packages: list[dict[str, Any]]) -> int:
    expected = {package["name"]: package for package in packages if package["manager"] == "conda"}
    installed = _installed_conda_records()
    missing = sorted(set(expected) - set(installed))
    extra = sorted(set(installed) - set(expected))
    if missing or extra:
        raise VerificationError(
            f"Conda package set differs from lock; missing={missing}, extra={extra}"
        )

    mismatches: list[str] = []
    for name, locked in expected.items():
        current = installed[name]
        locked_hash = locked["hash"]["sha256"]
        if current.get("version") != str(locked["version"]):
            mismatches.append(f"{name}: version {current.get('version')} != {locked['version']}")
        if current.get("url") != locked["url"]:
            mismatches.append(f"{name}: package URL differs")
        if current.get("sha256") != locked_hash:
            mismatches.append(f"{name}: package SHA-256 differs")
    if mismatches:
        raise VerificationError("Conda package mismatch: " + "; ".join(mismatches))
    return len(expected)


def _verify_pip_packages(packages: list[dict[str, Any]]) -> int:
    expected = {
        package["name"]: str(package["version"])
        for package in packages
        if package["manager"] == "pip"
    }
    mismatches: list[str] = []
    for name, version in expected.items():
        try:
            current = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            mismatches.append(f"{name}: missing")
            continue
        if current != version:
            mismatches.append(f"{name}: version {current} != {version}")
    if mismatches:
        raise VerificationError("Pip package mismatch: " + "; ".join(mismatches))

    check = subprocess.run(
        [sys.executable, "-m", "pip", "check"],
        check=False,
        capture_output=True,
        text=True,
    )
    if check.returncode != 0:
        raise VerificationError("pip check failed: " + (check.stdout + check.stderr).strip())
    return len(expected)


def _verify_direct_imports(packages: list[dict[str, Any]]) -> dict[str, str]:
    locked_versions = {package["name"]: str(package["version"]) for package in packages}
    versions: dict[str, str] = {}
    for package_name, module_name in DIRECT_IMPORTS.items():
        module = importlib.import_module(module_name)
        version = getattr(module, "__version__", None)
        if not version:
            distribution_name = "torch" if package_name == "pytorch" else package_name
            version = importlib.metadata.version(distribution_name)
        version = str(version).split("+")[0]
        if version != locked_versions[package_name]:
            raise VerificationError(
                f"{module_name} import reports {version}; lock has {locked_versions[package_name]}"
            )
        versions[module_name] = version
    return versions


def _verify_hdf5() -> dict[str, str]:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        h5py = importlib.import_module("h5py")
    built = ".".join(map(str, h5py.version.hdf5_built_version_tuple))
    runtime = ".".join(map(str, h5py.version.hdf5_version_tuple))
    if built != runtime:
        raise VerificationError(
            f"h5py/HDF5 mismatch: built against {built}, running against {runtime}"
        )
    return {"h5py": h5py.__version__, "hdf5_built": built, "hdf5_runtime": runtime}


def verify_current_environment(lock_path: Path, hash_path: Path) -> dict[str, Any]:
    """Run all lock, platform, package, import and binary compatibility checks."""

    structure = validate_lock_structure(lock_path, hash_path)
    lock = structure.pop("document")
    packages = lock["package"]
    if platform.python_version() != "3.11.15":
        raise VerificationError(f"Python 3.11.15 is required; found {platform.python_version()}")

    return {
        "status": "ok",
        "platform": _validate_host(),
        "python": platform.python_version(),
        **structure,
        "verified_conda_packages": _verify_conda_packages(packages),
        "verified_pip_packages": _verify_pip_packages(packages),
        "direct_import_versions": _verify_direct_imports(packages),
        "hdf5": _verify_hdf5(),
    }


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock-file", type=Path, default=Path("conda-lock.yml"))
    parser.add_argument("--hash-file", type=Path, default=Path("conda-lock.yml.sha256"))
    return parser.parse_args()


def main() -> int:
    """Run verification and print a machine-readable summary."""

    args = parse_args()
    try:
        report = verify_current_environment(args.lock_file.resolve(), args.hash_file.resolve())
    except (OSError, KeyError, TypeError, VerificationError) as error:
        print(json.dumps({"status": "failed", "error": str(error)}, indent=2), file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
