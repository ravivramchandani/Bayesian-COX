"""Read dataset YAML declarations for the pipeline's input inventory.

:mod:`provenance` uses :func:`_load_yaml` to read ``config/datasets.yaml``
when it lists the run inputs.
"""

from pathlib import Path
from typing import Any

from src.utils.io import read_mapping


def _load_yaml(path: Path) -> dict[str, Any]:
    """Read a YAML mapping while preserving the pipeline's original error text.

    Raises:
        ValueError: The file does not contain a mapping; the message reads
            ``"<path> must contain a YAML mapping"``. Other reader errors are
            re-raised unchanged.
    """
    try:
        return read_mapping(path)
    except ValueError as error:
        if str(error) == f"{path} must contain a mapping":
            raise ValueError(f"{path} must contain a YAML mapping") from error
        raise
