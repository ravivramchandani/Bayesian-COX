"""Observe the original kappa call without changing its solver or predicates."""

from __future__ import annotations

import math
from types import SimpleNamespace
from typing import Any

import numpy as np

if __package__:
    from .independent_arithmetic import Inputs, require
else:
    from independent_arithmetic import Inputs, require


def finite_scalar(value: Any) -> float | None:
    """Preserve finite scalar values; record nonfinite status separately."""
    if value is None:
        return None
    numeric = float(value)
    return numeric if math.isfinite(numeric) else None


def observed_kappa(reference: SimpleNamespace, inputs: Inputs,
                   telemetry: dict[str, Any]) -> tuple[float, np.ndarray]:
    """Delegate one exact AST-loaded original call, restoring aliases finally.

    The optimizer's returned jacobian is recorded separately from the original
    post-optimization kernel score. No extra objective or solver call is made.
    The caller must load the byte-pinned original definitions in an exclusively
    owned process. Exceptions retain their original traceback and identity.
    """
    require(reference.optimizer_enabled, "kappa observation requires the explicit optimizer stage")
    function = reference.catalytic_kappa
    namespace = function.__globals__
    require(namespace.get("np") is np and callable(namespace.get("minimize"))
            and callable(namespace.get("catalytic_kernel")), "original AST namespace differs")
    optimizer, kernel = namespace["minimize"], namespace["catalytic_kernel"]
    telemetry.update(optimizer_calls=0, optimizer_returned=False,
                     post_optimization_kernel_observed=False, original_gate_rejected=None,
                     additional_optimizer_or_kernel_calls=False)
    awaiting_post_kernel = False

    def observe_optimizer(*args: Any, **kwargs: Any) -> Any:
        nonlocal awaiting_post_kernel
        telemetry["optimizer_calls"] += 1
        require(telemetry["optimizer_calls"] == 1, "unexpected extra original kappa optimizer call")
        telemetry.update(method=kwargs.get("method"), options=dict(kwargs.get("options", {})),
                         jacobian_argument=kwargs.get("jac"))
        try:
            result = optimizer(*args, **kwargs)
        except Exception as error:
            telemetry["optimizer_exception"] = {"type": type(error).__name__, "message": str(error)}
            raise
        coefficients = np.asarray(result.x)
        jacobian = None if getattr(result, "jac", None) is None else np.asarray(result.jac)
        maximum = None if jacobian is None else float(np.max(np.abs(jacobian)))
        telemetry.update(optimizer_returned=True, success=bool(result.success),
                         x_finite=bool(np.isfinite(coefficients).all()),
                         jac_finite=None if jacobian is None else bool(np.isfinite(jacobian).all()),
                         maximum_absolute_returned_jacobian=finite_scalar(maximum),
                         objective=finite_scalar(getattr(result, "fun", None)),
                         objective_finite=None if getattr(result, "fun", None) is None else
                         math.isfinite(float(result.fun)),
                         iterations=None if getattr(result, "nit", None) is None else int(result.nit),
                         message=str(result.message))
        awaiting_post_kernel = True
        return result

    def observe_kernel(*args: Any, **kwargs: Any) -> Any:
        nonlocal awaiting_post_kernel
        value, gradient = kernel(*args, **kwargs)
        if awaiting_post_kernel:
            maximum = float(np.max(np.abs(gradient)))
            finite_value = bool(np.isfinite(value))
            rejected_score = bool(maximum > 1e-6)
            telemetry.update(post_optimization_kernel_observed=True,
                             post_kernel_value=finite_scalar(value), post_kernel_value_finite=finite_value,
                             post_score_finite=bool(np.isfinite(gradient).all()),
                             maximum_absolute_post_score=finite_scalar(maximum),
                             post_score_threshold=1e-6, post_score_threshold_rejected=rejected_score,
                             original_gate_rejected=not telemetry["success"] or not finite_value or rejected_score)
            awaiting_post_kernel = False
        return value, gradient

    namespace["minimize"], namespace["catalytic_kernel"] = observe_optimizer, observe_kernel
    try:
        return function(inputs.reference_data())
    finally:
        namespace["minimize"], namespace["catalytic_kernel"] = optimizer, kernel


def is_original_kappa_gate_failure(error: Exception, reference: SimpleNamespace,
                                   telemetry: dict[str, Any]) -> bool:
    """Require the actual original guard frame and its observed failed predicate."""
    if (type(error) is not RuntimeError or
            not str(error).startswith("catalytic kappa optimizer failed: ") or
            telemetry.get("optimizer_calls") != 1 or
            telemetry.get("post_optimization_kernel_observed") is not True or
            telemetry.get("original_gate_rejected") is not True):
        return False
    traceback = error.__traceback__
    while traceback is not None:
        if traceback.tb_frame.f_code is reference.catalytic_kappa.__code__:
            return True
        traceback = traceback.tb_next
    return False
