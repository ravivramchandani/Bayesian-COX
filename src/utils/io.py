"""Reading and writing the JSON and YAML files used by every pipeline stage."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any

import numpy as np
import yaml


def json_safe(value: Any) -> Any:
    """Convert a nested value into plain JSON types.

    Dictionary keys become strings, tuples and arrays become lists, NumPy
    scalars become Python numbers, and non-finite floats (NaN, infinity)
    become ``None``. Anything else is stored as its ``str()`` form. Booleans
    are checked before integers because ``bool`` is a subclass of ``int``.
    """
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, np.ndarray):
        return [json_safe(item) for item in value.tolist()]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, (np.integer, int)):
        return int(value)
    if value is None or isinstance(value, str):
        return value
    return str(value)


def write_json_atomic(path: Path, value: Any, *, overwrite: bool = True) -> None:
    """Write ``value`` as indented, key-sorted JSON without leaving partial files.

    The content goes to ``<path>.tmp`` first and is then renamed over
    ``path``, so a reader never sees a half-written file.

    Args:
        path: Destination file. Parent directories are created.
        value: Any value accepted by :func:`json_safe`.
        overwrite: When ``False``, refuse to replace an existing file.
    """
    if not overwrite and path.exists():
        raise FileExistsError(f"refusing to overwrite existing result: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(json_safe(value), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def read_mapping(path: Path) -> dict[str, Any]:
    """Read a YAML (``.yaml``/``.yml``) or JSON file that must hold a mapping."""
    with path.open(encoding="utf-8") as handle:
        value = yaml.safe_load(handle) if path.suffix in {".yaml", ".yml"} else json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a mapping")
    return value
