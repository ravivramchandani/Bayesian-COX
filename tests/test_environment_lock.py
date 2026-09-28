"""Tests for the exact macOS arm64 environment lock.

Reads the committed ``conda-lock.yml``, its ``.sha256`` record and
``conda-lock-virtual-packages.yml`` through ``scripts/verify_environment.py``.
The checks are static: they inspect the lock files, not the running
environment. They protect the exact, hashed lock of ADR-022 and the 259-record
count that ADR-026 requires to be verified before use.
"""

from pathlib import Path

import yaml

from scripts.verify_environment import load_lock, sha256_file, validate_lock_structure

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "conda-lock.yml"
LOCK_HASH = ROOT / "conda-lock.yml.sha256"


def test_lock_is_hashed_and_complete() -> None:
    """The lock passes its hash checks and holds 237 conda and 22 pip records (ADR-026)."""
    report = validate_lock_structure(LOCK, LOCK_HASH)
    assert report["package_count"] == 259
    assert report["conda_package_count"] == 237
    assert report["pip_package_count"] == 22


def test_lock_contains_binary_compatible_hdf5_and_reference_pytorch() -> None:
    """The lock pins HDF5 2.1.0, h5py 3.16.0 and fixed PyTorch, pycox and torchtuples (ADR-022)."""
    lock = load_lock(LOCK)
    records = {(item["manager"], item["name"]): item for item in lock["package"]}

    assert records[("conda", "hdf5")]["version"] == "2.1.0"
    assert records[("conda", "h5py")]["version"] == "3.16.0"
    assert records[("conda", "pytorch")]["version"] == "2.13.0"
    assert records[("pip", "pycox")]["version"] == "0.3.0"
    assert records[("pip", "torchtuples")]["version"] == "0.2.2"


def test_lock_inputs_and_target_platform_are_immutable() -> None:
    """The lock matches environment.yml and targets only osx-arm64 with macOS 14.0 (ADR-022)."""
    lock = load_lock(LOCK)
    input_digest = lock["metadata"]["inputs_metadata"]["environment.yml"]["sha256"]
    virtual = yaml.safe_load((ROOT / "conda-lock-virtual-packages.yml").read_text())

    assert input_digest == sha256_file(ROOT / "environment.yml")
    assert lock["metadata"]["platforms"] == ["osx-arm64"]
    assert virtual["subdirs"]["osx-arm64"]["packages"]["__archspec"] == "1 arm64"
    assert virtual["subdirs"]["osx-arm64"]["packages"]["__osx"] == "14.0"
