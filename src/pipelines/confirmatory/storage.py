"""Shared JSON writing and the legacy YAML-mapping error contract."""

from pathlib import Path
from typing import Any

from src.utils.io import read_mapping


def _load_yaml(path: Path) -> dict[str, Any]:
    """Read a YAML mapping while preserving the pipeline's original error text."""
    try:
        return read_mapping(path)
    except ValueError as error:
        if str(error) == f"{path} must contain a mapping":
            raise ValueError(f"{path} must contain a YAML mapping") from error
        raise
