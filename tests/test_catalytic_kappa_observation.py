"""Original AST control with injected solvers; no actual optimizer or cohorts."""

from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest

from scripts.catalytic_correction.independent_arithmetic import load_original_functions
from scripts.catalytic_correction.kappa_observation import (
    is_original_kappa_gate_failure,
    observed_kappa,
)
from tests.test_catalytic_correction_arithmetic import balanced, original_source_fixture


@pytest.fixture
def reference():
    with tempfile.TemporaryDirectory(prefix="kappa_ast_fixture_") as directory:
        source = original_source_fixture(Path(directory).resolve())
        value = load_original_functions(source, optimizer_enabled=True)
        yield value


def solver_result(*, success: bool = True, coefficient: float = 0.0,
                  returned_jacobian: float = 0.0) -> SimpleNamespace:
    """Expose the real solver result interface on one analytic fixture."""
    return SimpleNamespace(success=success, x=np.array([coefficient]),
                           jac=np.array([returned_jacobian]), fun=1.0, nit=3,
                           message="CONVERGENCE")


def test_success_observation_preserves_aliases_and_single_delegation(reference):
    namespace = reference.catalytic_kappa.__globals__
    original_kernel = namespace["catalytic_kernel"]
    calls = []

    def injected(function, initial, **kwargs):
        calls.append((initial.copy(), kwargs))
        function(initial)
        return solver_result()

    with patch.dict(namespace, minimize=injected):
        telemetry = {}
        value, coefficients = observed_kappa(reference, balanced(), telemetry)
        assert namespace["minimize"] is injected
        assert namespace["catalytic_kernel"] is original_kernel
    assert value == -1.0 and np.array_equal(coefficients, [0.0])
    assert len(calls) == telemetry["optimizer_calls"] == 1
    assert telemetry["post_optimization_kernel_observed"] is True
    assert telemetry["original_gate_rejected"] is False
    assert telemetry["options"] == {"gtol": 1e-8, "ftol": 1e-14, "maxiter": 5000, "maxls": 50}


@pytest.mark.parametrize("result", [solver_result(success=False), solver_result(coefficient=0.2)])
def test_convergence_message_does_not_hide_original_failed_predicate(reference, result):
    namespace = reference.catalytic_kappa.__globals__
    original_kernel = namespace["catalytic_kernel"]
    def injected(*_args, **_kwargs):
        return result
    with patch.dict(namespace, minimize=injected):
        telemetry = {}
        with pytest.raises(RuntimeError) as caught:
            observed_kappa(reference, balanced(), telemetry)
        assert is_original_kappa_gate_failure(caught.value, reference, telemetry)
        assert namespace["minimize"] is injected
        assert namespace["catalytic_kernel"] is original_kernel
    assert telemetry["message"] == "CONVERGENCE"
    assert not telemetry["success"] or telemetry["post_score_threshold_rejected"]


def test_returned_jacobian_does_not_replace_original_post_kernel_score(reference):
    namespace = reference.catalytic_kappa.__globals__
    with patch.dict(namespace, minimize=lambda *_args, **_kwargs: solver_result(returned_jacobian=0.3)):
        telemetry = {}
        observed_kappa(reference, balanced(), telemetry)
    assert telemetry["maximum_absolute_returned_jacobian"] == 0.3
    assert telemetry["maximum_absolute_post_score"] == 0.0
    assert telemetry["original_gate_rejected"] is False


def test_solver_exception_with_same_text_is_not_original_guard_failure(reference):
    namespace = reference.catalytic_kappa.__globals__

    def injected(*_args, **_kwargs):
        raise RuntimeError("catalytic kappa optimizer failed: CONVERGENCE")

    with patch.dict(namespace, minimize=injected):
        telemetry = {}
        with pytest.raises(RuntimeError) as caught:
            observed_kappa(reference, balanced(), telemetry)
        assert namespace["minimize"] is injected
    assert not is_original_kappa_gate_failure(caught.value, reference, telemetry)
    assert telemetry["optimizer_returned"] is False
    assert telemetry["post_optimization_kernel_observed"] is False


def test_nonfinite_post_value_retains_original_failure_without_json_nan(reference):
    namespace = reference.catalytic_kappa.__globals__
    with patch.dict(namespace, minimize=lambda *_args, **_kwargs: solver_result(coefficient=1000.0)):
        telemetry = {}
        with pytest.raises(RuntimeError) as caught:
            observed_kappa(reference, balanced(), telemetry)
    assert is_original_kappa_gate_failure(caught.value, reference, telemetry)
    assert telemetry["post_kernel_value"] is None
    assert telemetry["post_kernel_value_finite"] is False
