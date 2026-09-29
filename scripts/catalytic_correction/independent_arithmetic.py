"""Independent finite-design arithmetic; no proposal generation, rank check or fit.

The reference loader executes only byte-pinned original function definitions.
It never imports the project package or constructs CatalyticData. Optimizer
access is disabled unless the separately named kappa stage explicitly enables it.
"""

from __future__ import annotations

import ast
import hashlib
import math
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np

ORIGINAL_COMMIT = "119476fef55b1eeb690527f234c1423440720d45"
ORIGINAL_CATALYTIC_SHA256 = "53b38e5d9314fefcfd37260ac95d1bd9400af44f564c2142f7e7d61986f20332"
SOURCE_RELATIVE = "src/models/catalytic.py"
KERNEL_ATOL = 1e-9
KERNEL_RTOL = 1e-11
COX_ATOL = 2e-8
COX_RTOL = 3e-11
KAPPA_SCORE_LIMIT = 1e-6
BETA_AMPLITUDE = 1e-3
TAU_MULTIPLIERS = (0.25, 1.0, 4.0)


class ArithmeticFailure(ValueError):
    """An input, reference or arithmetic comparison failed; never a retry signal."""


def require(condition: bool, message: str) -> None:
    """Refuse invalid arithmetic inputs without selecting a replacement proposal."""
    if not condition:
        raise ArithmeticFailure(message)


def sha256(data: bytes) -> str:
    """Hash bytes without interpreting them as scientific evidence."""
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class Inputs:
    """Bound accepted synthetic arrays and observed training arrays in their units.

    real_time is in original units; synthetic_time and hazard use the original
    generator's time_scale. Rank acceptance belongs to the input preflight.
    """

    synthetic_design: np.ndarray
    synthetic_time: np.ndarray
    hazard: float
    real_design: np.ndarray
    real_time: np.ndarray
    real_event: np.ndarray
    time_scale: float

    def validate(self) -> None:
        """Check finite arithmetic domains and dimensions without an SVD or fit."""
        sx, rx = self.synthetic_design, self.real_design
        require(sx.ndim == rx.ndim == 2 and sx.shape[1] == rx.shape[1] > 0,
                "synthetic and training design dimensions differ")
        require(sx.shape[0] > 0 and rx.shape[0] > 0, "empty arithmetic input")
        require(self.synthetic_time.ndim == self.real_time.ndim == self.real_event.ndim == 1,
                "time/event arrays must be vectors")
        require(len(self.synthetic_time) == len(sx)
                and len(self.real_time) == len(self.real_event) == len(rx), "array row counts differ")
        for name, array in (("synthetic_design", sx), ("real_design", rx),
                            ("synthetic_time", self.synthetic_time), ("real_time", self.real_time)):
            require(array.dtype == np.dtype("float64"), f"{name} must retain float64 arithmetic")
            require(bool(np.isfinite(array).all()), f"nonfinite {name}")
        require(bool(np.isfinite(self.real_event).all())
                and bool(np.isin(self.real_event, (0, 1)).all()), "invalid observed event indicator")
        require(bool(np.all(self.synthetic_time > 0)) and bool(np.all(self.real_time > 0)),
                "nonpositive times")
        require(math.isfinite(self.hazard) and self.hazard > 0
                and math.isfinite(self.time_scale) and self.time_scale > 0, "invalid rate/time scale")
        require(bool(np.any(self.real_event == 1)), "no observed training events")

    def reference_data(self) -> SimpleNamespace:
        """Expose the original functions' array interface without constructing a model."""
        return SimpleNamespace(design=self.synthetic_design, time=self.synthetic_time,
                               hazard=self.hazard)

    @property
    def p(self) -> int:
        """Actual encoded coefficient count, not synthetic rows or real patients."""
        return self.synthetic_design.shape[1]


def checked_beta(beta: np.ndarray, p: int) -> np.ndarray:
    """Require a finite coefficient vector without clipping its linear predictors."""
    values = np.asarray(beta, dtype=np.float64)
    require(values.ndim == 1 and len(values) == p and bool(np.isfinite(values).all()),
            "invalid arithmetic coefficient vector")
    return values


def beta_vectors(p: int) -> tuple[tuple[str, np.ndarray], ...]:
    """Return the fixed small vectors specified before any real arithmetic result."""
    indices = np.arange(p)
    alternating = BETA_AMPLITUDE * np.where(indices % 2 == 0, 1.0, -1.0)
    return (("zero", np.zeros(p)), ("alternating", alternating),
            ("negative_alternating", -alternating),
            ("sine", BETA_AMPLITUDE * np.sin(indices + 1.0)))


def independent_catalytic(beta: np.ndarray, inputs: Inputs) -> tuple[float, np.ndarray]:
    """Evaluate q and its analytic gradient using independent scalar reductions.

    math.fsum replaces the original NumPy mean/GEMV reductions. No clipping,
    optimization, synthetic resampling or matrix-rank computation occurs.
    """
    beta = checked_beta(beta, inputs.p)
    x, t = inputs.synthetic_design, inputs.synthetic_time
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            eta = x @ beta
            cumulative = inputs.hazard * t * np.exp(eta)
            residual = 1.0 - cumulative
        require(bool(np.isfinite(eta).all()) and bool(np.isfinite(cumulative).all()),
                "nonfinite catalytic linear predictor/cumulative hazard")
        value = math.fsum(float(v) for v in eta - cumulative) / len(x)
        gradient = np.array([math.fsum(float(v) for v in x[:, j] * residual) / len(x)
                             for j in range(inputs.p)], dtype=np.float64)
    except (FloatingPointError, OverflowError) as error:
        raise ArithmeticFailure("catalytic overflow/nonfinite arithmetic") from error
    require(math.isfinite(value) and bool(np.isfinite(gradient).all()), "nonfinite catalytic result")
    return value, gradient


def independent_adaptive(q: float, tau: float, p: int, kappa: float,
                         *, alpha: float = 2.0, gamma: float = 1.0) -> float:
    """Evaluate the normalized joint expression from independently computed q."""
    require(all(math.isfinite(v) for v in (q, tau, kappa, alpha, gamma))
            and tau > 0 and alpha > 0 and gamma > 0 and p > 0, "invalid adaptive domain")
    value = (p + alpha - 1.0) * math.log(tau) + tau * (q - kappa - 1.0 / gamma)
    require(math.isfinite(value), "nonfinite adaptive expression")
    return value


def merged_arrays(inputs: Inputs, tau: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Build one merged context; synthetic events are prior data with tau/M weight."""
    require(math.isfinite(tau) and tau > 0, "invalid weighted-mixture tau")
    x = np.concatenate((inputs.real_design, inputs.synthetic_design), axis=0)
    t = np.concatenate((inputs.real_time / inputs.time_scale, inputs.synthetic_time))
    event = np.concatenate((inputs.real_event, np.ones(len(inputs.synthetic_time), dtype=int)))
    weight = np.concatenate((np.ones(len(inputs.real_time)),
                             np.full(len(inputs.synthetic_time), tau / len(inputs.synthetic_time))))
    return x, t, event, weight


def validate_training_units(inputs: Inputs) -> list[dict[str, Any]]:
    """Recompute the original training-only median scale and exponential MLE.

    This arithmetic check uses supplied training arrays, not patient records,
    generator draws or rank checks. math.fsum gives an independent denominator.
    """
    inputs.validate()
    observed = sorted(float(t) for t, event in zip(inputs.real_time, inputs.real_event, strict=True)
                      if event == 1)
    middle = len(observed) // 2
    scale = observed[middle] if len(observed) % 2 else (observed[middle - 1] + observed[middle]) / 2
    hazard = math.fsum(float(d) for d in inputs.real_event) / math.fsum(
        float(t) / scale for t in inputs.real_time)
    require(math.isfinite(scale) and scale > 0 and math.isfinite(hazard) and hazard > 0,
            "nonfinite independently recomputed training units")
    return [compare("training_time_scale", scale, inputs.time_scale, atol=0.0, rtol=KERNEL_RTOL),
            compare("training_reference_hazard", hazard, inputs.hazard, atol=0.0, rtol=KERNEL_RTOL)]


def independent_breslow(beta: np.ndarray, design: np.ndarray, time: np.ndarray,
                       event: np.ndarray, weight: np.ndarray) -> tuple[float, np.ndarray]:
    """Evaluate weighted Breslow terms by descending tied-time groups.

    Keep only O(p) running risk/score vectors and O(n) scalar arrays. This does
    not construct an n-by-n risk matrix or the original n-by-p cumulative
    numerator matrix. Event case weights and risk denominator weights both apply.
    """
    x = design
    require(x.ndim == 2 and len(x) > 0 and x.shape[1] > 0, "invalid merged design")
    beta = checked_beta(beta, x.shape[1])
    require(all(a.ndim == 1 and len(a) == len(x) for a in (time, event, weight)),
            "invalid merged vector dimensions")
    require(all(bool(np.isfinite(a).all()) for a in (x, time, event, weight))
            and bool(np.all(time > 0)) and bool(np.all(weight > 0))
            and bool(np.isin(event, (0, 1)).all()), "invalid merged arithmetic domain")
    eta = x @ beta
    require(bool(np.isfinite(eta).all()), "nonfinite weighted linear predictor")
    shift = float(np.max(eta))
    with np.errstate(over="raise", invalid="raise"):
        risk = weight * np.exp(eta - shift)
    order = np.argsort(-time, kind="stable")
    numerator = np.zeros(x.shape[1])
    numerator_correction = np.zeros(x.shape[1])
    score = np.zeros(x.shape[1])
    score_correction = np.zeros(x.shape[1])
    denominator = 0.0
    denominator_correction = 0.0
    terms: list[float] = []
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and time[order[end]] == time[order[start]]:
            end += 1
        group = order[start:end]
        for row in group:
            adjusted = float(risk[row]) - denominator_correction
            updated = denominator + adjusted
            denominator_correction = (updated - denominator) - adjusted
            denominator = updated
            vector = risk[row] * x[row] - numerator_correction
            updated_vector = numerator + vector
            numerator_correction = (updated_vector - numerator) - vector
            numerator = updated_vector
        event_weight = math.fsum(float(weight[row] * event[row]) for row in group)
        if event_weight > 0:
            require(math.isfinite(denominator) and denominator > 0,
                    "weighted risk denominator underflow/nonfinite")
            for row in group:
                case = float(weight[row] * event[row])
                if case:
                    terms.append(case * float(eta[row]))
                    contribution = case * x[row] - score_correction
                    updated_vector = score + contribution
                    score_correction = (updated_vector - score) - contribution
                    score = updated_vector
            terms.append(-event_weight * (math.log(denominator) + shift))
            contribution = -event_weight * numerator / denominator - score_correction
            updated_vector = score + contribution
            score_correction = (updated_vector - score) - contribution
            score = updated_vector
        start = end
    value = math.fsum(terms)
    require(math.isfinite(value) and bool(np.isfinite(score).all()), "nonfinite weighted Breslow result")
    return value, score


def compare(name: str, actual: Any, reference: Any, *, atol: float,
            rtol: float) -> dict[str, Any]:
    """Record elementwise absolute/relative errors and refuse nonfinite values."""
    a, b = np.asarray(actual, dtype=float), np.asarray(reference, dtype=float)
    require(a.shape == b.shape, f"shape mismatch in {name}")
    require(bool(np.isfinite(a).all()) and bool(np.isfinite(b).all()), f"nonfinite reference/check in {name}")
    try:
        with np.errstate(over="raise", invalid="raise"):
            error = np.abs(a - b)
    except FloatingPointError as exception:
        raise ArithmeticFailure(f"nonfinite comparison error in {name}") from exception
    scale = np.maximum(np.abs(a), np.abs(b))
    allowed = atol + rtol * scale
    relative = error / np.maximum(scale, np.finfo(float).tiny)
    passed = bool(np.all(error <= allowed))
    return {"check": name, "passed": passed, "absolute_tolerance": atol,
            "relative_tolerance": rtol, "maximum_absolute_error": float(np.max(error)),
            "maximum_relative_error": float(np.max(relative)),
            "maximum_tolerance_ratio": float(np.max(error / allowed)),
            "elements": int(a.size)}


def load_original_functions(source_checkout: Path, *, optimizer_enabled: bool = False) -> SimpleNamespace:
    """Compile exact pinned original definitions without package imports or SVD.

    The named optional kappa stage may enable only the original kappa optimizer.
    Default arithmetic execution cannot call it successfully.
    """
    root = source_checkout
    require(root.is_absolute() and root.is_dir() and ".." not in root.parts
            and not any(p.is_symlink() for p in (root, *root.parents)), "unsafe original checkout")
    path = root / SOURCE_RELATIVE
    require(path.is_file() and not any(p.is_symlink() for p in (path, *path.parents)), "unsafe original source")
    data = path.read_bytes()
    require(sha256(data) == ORIGINAL_CATALYTIC_SHA256, "original catalytic function source changed")
    selected = {"catalytic_kernel", "adaptive_log_kernel", "weighted_breslow_objective", "catalytic_kappa"}
    tree = ast.parse(data, filename=str(path))
    definitions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in selected]
    require({node.name for node in definitions} == selected, "original arithmetic definitions unavailable")

    def forbidden_optimizer(*_args: Any, **_kwargs: Any) -> Any:
        raise ArithmeticFailure("optimizer disabled; use separately named compute-kappa stage")

    optimizer = forbidden_optimizer
    if optimizer_enabled:
        from scipy.optimize import minimize
        optimizer = minimize
    namespace = {"np": np, "minimize": optimizer}
    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    module = ast.fix_missing_locations(ast.Module(body=[future, *definitions], type_ignores=[]))
    exec(compile(module, str(path), "exec"), namespace)
    return SimpleNamespace(**{name: namespace[name] for name in selected},
                           source_sha256=ORIGINAL_CATALYTIC_SHA256,
                           source_relative=SOURCE_RELATIVE, optimizer_enabled=optimizer_enabled)


def validate_kappa(inputs: Inputs, reference: SimpleNamespace, kappa: float,
                   beta_hat: np.ndarray) -> list[dict[str, Any]]:
    """Check a supplied finite optimum witness, without running an optimizer.

    Check q(beta_hat), the independent and original scores, and the unchanged
    original 1e-6 maximum-absolute-score criterion. This is not an independent
    optimization or a proof of all-grid properness.
    """
    require(math.isfinite(kappa), "nonfinite supplied kappa")
    beta_hat = checked_beta(beta_hat, inputs.p)
    independent_q, independent_gradient = independent_catalytic(beta_hat, inputs)
    original_q, original_gradient = reference.catalytic_kernel(beta_hat, inputs.reference_data())
    checks = [compare("kappa_value", independent_q, kappa, atol=KERNEL_ATOL, rtol=KERNEL_RTOL),
              compare("kappa_reference_value", original_q, kappa, atol=KERNEL_ATOL, rtol=KERNEL_RTOL),
              compare("kappa_gradient", independent_gradient, original_gradient,
                      atol=KERNEL_ATOL, rtol=KERNEL_RTOL)]
    require(float(np.max(np.abs(independent_gradient))) <= KAPPA_SCORE_LIMIT
            and float(np.max(np.abs(original_gradient))) <= KAPPA_SCORE_LIMIT,
            "supplied kappa witness fails unchanged score threshold")
    return checks


def validate_arithmetic(inputs: Inputs, reference: SimpleNamespace,
                        *, kappa: float | None = None, beta_hat: np.ndarray | None = None) -> dict[str, Any]:
    """Compare finite-design arithmetic only; never a fit/freeze/reuse certificate.

    Adaptive checks are explicitly pending without a supplied checked kappa.
    Callers requiring a complete arithmetic stage must refuse that partial status.
    """
    inputs.validate()
    require(not reference.optimizer_enabled, "validation requires optimizer-disabled reference")
    require((kappa is None) == (beta_hat is None), "kappa and optimum witness must be supplied together")
    checks: list[dict[str, Any]] = []
    if kappa is not None:
        checks.extend(validate_kappa(inputs, reference, kappa, beta_hat))
    zero = np.zeros(inputs.p)
    q0, _ = independent_catalytic(zero, inputs)
    oq0, _ = reference.catalytic_kernel(zero, inputs.reference_data())
    for label, beta in beta_vectors(inputs.p):
        q, gradient = independent_catalytic(beta, inputs)
        original_q, original_gradient = reference.catalytic_kernel(beta, inputs.reference_data())
        checks.append(compare(f"{label}:q", q, original_q, atol=KERNEL_ATOL, rtol=KERNEL_RTOL))
        checks.append(compare(f"{label}:q_gradient", gradient, original_gradient,
                              atol=KERNEL_ATOL, rtol=KERNEL_RTOL))
        for multiplier in TAU_MULTIPLIERS:
            tau = inputs.p * multiplier
            prefix = f"{label}:tau_{multiplier:g}"
            checks.append(compare(prefix + ":fixed_difference", tau * (q - q0), tau * (original_q - oq0),
                                  atol=COX_ATOL, rtol=COX_RTOL))
            checks.append(compare(prefix + ":fixed_gradient", tau * gradient, tau * original_gradient,
                                  atol=COX_ATOL, rtol=COX_RTOL))
            if kappa is not None:
                independent_joint = independent_adaptive(q, tau, inputs.p, kappa)
                original_joint = reference.adaptive_log_kernel(beta, tau, inputs.reference_data(), kappa)
                checks.append(compare(prefix + ":adaptive_joint", independent_joint, original_joint,
                                      atol=COX_ATOL, rtol=COX_RTOL))
                checks.append(compare(prefix + ":adaptive_beta_gradient", tau * gradient,
                                      tau * original_gradient, atol=COX_ATOL, rtol=COX_RTOL))
            merged = merged_arrays(inputs, tau)
            value, score = independent_breslow(beta, *merged)
            original_value, original_score = reference.weighted_breslow_objective(beta, *merged)
            checks.append(compare(prefix + ":weighted_breslow", value, original_value, atol=COX_ATOL, rtol=COX_RTOL))
            checks.append(compare(prefix + ":weighted_score", score, original_score, atol=COX_ATOL, rtol=COX_RTOL))
            del merged
    passed = all(row["passed"] for row in checks)
    return {"schema_version": 1, "status": "arithmetic_passed" if passed else "arithmetic_failed",
            "adaptive_status": "checked_supplied_kappa" if kappa is not None else "pending_kappa_evidence",
            "checks": checks, "check_count": len(checks), "p": inputs.p,
            "synthetic_rows": len(inputs.synthetic_time), "training_rows": len(inputs.real_time),
            "beta_rule": "zero, alternating +/-, sine; component amplitude 0.001",
            "tau_multipliers": list(TAU_MULTIPLIERS), "optimizer_invoked": False,
            "rank_check_invoked": False, "new_proposals_generated": False,
            "predictive_metrics_computed": False, "fit_reuse_certified": False,
            "method_freeze_certified": False, "programme_completion_certified": False}
