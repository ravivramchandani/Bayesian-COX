"""Portable invented-byte guards for the sealed corrected release adapter.

The original preparation tests are loaded under private, scoped import aliases.
They dispatch only injected children and cannot certify scientific evidence.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import pytest

HERE = Path(__file__).resolve().parents[1] / "scripts/catalytic_correction/release"


def load_fixture_module(name: str, aliases: dict):
    """Keep the retained test/runtime bytes and isolate their import aliases."""
    spec = importlib.util.spec_from_file_location("_release_integration_" + name, HERE / (name + ".py"))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    with patch.dict(sys.modules, aliases):
        spec.loader.exec_module(module)
    return module


_aliases = {}
for _name in (
    "verification_io",
    "release_core",
    "stage_corrected_extensions",
    "verify_restored_correction",
    "capture_corrected_source",
    "capture_mixed_source",
    "test_release_adapters",
    "test_receiving_adapters",
    "test_source_capture",
    "test_transport_delegate",
    "test_v2_provenance",
):
    _module = load_fixture_module(_name, _aliases)
    _aliases[_name] = _module
    if _name.startswith("test_"):
        for _class_name, _candidate in vars(_module).items():
            if (
                isinstance(_candidate, type)
                and issubclass(_candidate, unittest.TestCase)
                and _candidate.__module__ == _module.__name__
            ):
                globals()["Test" + _name + "_" + _class_name] = _candidate

del _name, _module, _class_name, _candidate


@pytest.fixture(autouse=True)
def scoped_runtime_aliases():
    """Resolve the retained string-based mock target only during its test."""
    with patch.dict(sys.modules, _aliases):
        yield


def test_retained_preparation_has_its_complete_executable_file_surface():
    """The real entrypoint's preparation check needs every bound local member."""
    core = _aliases["release_core"]
    preparation = core.load_preparation(
        HERE,
        "9e567639359328d958e73c476a2d16ec8b0ab408e17c1fb016c37c3234713c1d",
        core.Pins(),
    )
    assert len(preparation["artifacts"]) == 99
    assert set(preparation["implementation_source_sha256"]) == _aliases["capture_mixed_source"].OWN
