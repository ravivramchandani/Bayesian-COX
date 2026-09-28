"""Read and write the stored mappings shared by pipeline stages.

``json_safe`` converts results into JavaScript Object Notation (JSON) types;
``write_json_atomic`` replaces a completed destination file, and
``read_mapping`` loads JSON or YAML (YAML Ain't Markup Language) configuration.
"""

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
    scalars become Python numbers, and non-finite floats (not-a-number or infinity)
    become ``None``. Anything else is stored as its ``str()`` form. Booleans
    are checked before integers because ``bool`` is a subclass of ``int``.

    Args:
        value: A scalar or nested dictionary, list, tuple or NumPy array.

    Returns:
        A corresponding value suitable for JSON encoding with non-finite
        numbers replaced by ``None``.
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
    """Write complete, indented, key-sorted JSON and replace the destination atomically.

    The content goes to ``<path>.tmp`` first and is then renamed over
    ``path``, so readers of the destination see either version in full.
    Callers must serialise writes to the same path: its temporary name is shared.

    Args:
        path: Destination file. Parent directories are created.
        value: Any value accepted by :func:`json_safe`.
        overwrite: When ``False``, check for an existing destination before
            writing; this is not an exclusive-create operation.

    Returns:
        None.

    Raises:
        FileExistsError: ``overwrite`` is false and the destination already exists.
        OSError: Creating, writing or replacing a file fails; the temporary
            file can remain after a failed operation.
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
    """Read a YAML or JSON file that must hold a mapping.

    Args:
        path: Input file; ``.yaml`` and ``.yml`` select safe YAML loading,
            while any other suffix selects JSON loading.

    Returns:
        The decoded dictionary, without changing its keys or nested values.

    Raises:
        OSError: The file cannot be opened or read.
        ValueError: The decoded value is not a mapping or JSON is malformed.
        yaml.YAMLError: YAML syntax is malformed.
    """
    with path.open(encoding="utf-8") as handle:
        value = yaml.safe_load(handle) if path.suffix in {".yaml", ".yml"} else json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a mapping")
    return value
