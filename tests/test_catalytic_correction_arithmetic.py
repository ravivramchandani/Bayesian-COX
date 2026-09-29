"""Pure/synthetic arithmetic guards; no generator, SVD, optimizer or cohorts."""

from __future__ import annotations

import copy
import math
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from scripts.catalytic_correction.independent_arithmetic import (
    ORIGINAL_COMMIT,
    ArithmeticFailure,
    Inputs,
    beta_vectors,
    compare,
    independent_adaptive,
    independent_breslow,
    independent_catalytic,
    load_original_functions,
    merged_arrays,
    validate_arithmetic,
    validate_kappa,
    validate_training_units,
)


def original_source_fixture(destination: Path) -> Path:
    """Materialize three immutable Git blobs for AST-only reference tests."""
    root = Path(__file__).absolute().parents[1]
    for relative in ("src/models/catalytic.py", "src/models/bayesian/extensions.py",
                     "src/pipelines/extensions/preprocessing.py"):
        payload = subprocess.check_output(
            ["git", "-C", str(root), "show", f"{ORIGINAL_COMMIT}:{relative}"])
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    return destination.resolve()


def fixture() -> Inputs:
    """A finite two-coefficient fixture with ties and censored training cases."""
    return Inputs(
        np.array([[-1.0, 0.5], [0.5, -1.0], [1.0, 0.2], [-0.4, 1.0]]),
        np.array([0.5, 1.0, 1.0, 2.0]), 2.0 / 3.0,
        np.array([[0.3, 1.0], [-0.7, 0.2], [1.2, -0.5], [0.2, 0.4]]),
        np.array([1.0, 2.0, 2.0, 4.0]), np.array([1, 1, 0, 1]), 2.0,
    )


def balanced() -> Inputs:
    """Analytic q=-cosh(beta), kappa=-1 at beta=0; no optimizer needed."""
    return Inputs(np.array([[-1.0], [1.0]]), np.ones(2), 1.0,
                  np.array([[-0.5], [0.5]]), np.ones(2), np.ones(2, dtype=int), 1.0)


def enumerated_breslow(beta: np.ndarray, x: np.ndarray, time: np.ndarray,
                       event: np.ndarray, weight: np.ndarray) -> tuple[float, np.ndarray]:
    """Tiny direct per-event-time risk enumeration for synthetic tests only."""
    eta = x @ beta
    value, score = 0.0, np.zeros(x.shape[1])
    for t in sorted(set(time[event == 1])):
        case = (time == t) & (event == 1)
        risk = time >= t
        hazard_weight = weight[risk] * np.exp(eta[risk])
        denominator = math.fsum(hazard_weight)
        count = math.fsum(weight[case])
        value += math.fsum(weight[case] * eta[case]) - count * math.log(denominator)
        score += x[case].T @ weight[case] - count * (x[risk].T @ hazard_weight) / denominator
    return value, score


def finite_difference(function, beta: np.ndarray, epsilon: float = 1e-6) -> np.ndarray:
    """Central differences on tiny synthetic fixtures, never on real arrays."""
    answer = []
    for i in range(len(beta)):
        delta = np.zeros_like(beta)
        delta[i] = epsilon
        answer.append((function(beta + delta) - function(beta - delta)) / (2 * epsilon))
    return np.array(answer)


class ArithmeticTests(unittest.TestCase):
    """Independent arithmetic and explicit failure boundaries."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.source_temporary = tempfile.TemporaryDirectory(prefix="original_arithmetic_blobs_")
        cls.original = original_source_fixture(Path(cls.source_temporary.name).resolve())
        cls.reference = load_original_functions(cls.original)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.source_temporary.cleanup()

    def test_catalytic_analytic_gradient(self) -> None:
        data = fixture()
        beta = np.array([0.04, -0.03])
        value, gradient = independent_catalytic(beta, data)
        self.assertTrue(math.isfinite(value))
        numerical = finite_difference(lambda b: independent_catalytic(b, data)[0], beta)
        np.testing.assert_allclose(gradient, numerical, atol=2e-10, rtol=1e-8)

    def test_weighted_breslow_ties_and_fractional_weights(self) -> None:
        data = fixture()
        for tau in (0.5, 2.0, 8.0):
            arrays = merged_arrays(data, tau)
            beta = np.array([0.04, -0.03])
            value, score = independent_breslow(beta, *arrays)
            direct_value, direct_score = enumerated_breslow(beta, *arrays)
            self.assertAlmostEqual(value, direct_value, places=12)
            np.testing.assert_allclose(score, direct_score, atol=1e-12, rtol=1e-12)
            numerical = finite_difference(lambda b, arrays=arrays: independent_breslow(b, *arrays)[0], beta)
            np.testing.assert_allclose(score, numerical, atol=2e-9, rtol=2e-8)

    def test_tied_censored_row_enters_risk_set(self) -> None:
        x = np.array([[0.0], [1.0], [2.0]])
        time = np.array([1.0, 1.0, 2.0])
        event, weight = np.array([1, 0, 1]), np.array([1.0, 0.5, 2.0])
        value, score = independent_breslow(np.zeros(1), x, time, event, weight)
        self.assertAlmostEqual(value, -math.log(3.5) - 2 * math.log(2.0), places=12)
        self.assertAlmostEqual(float(score[0]), -(0.5 + 4.0) / 3.5, places=12)

    def test_original_function_comparisons_partial_adaptive_explicit(self) -> None:
        result = validate_arithmetic(fixture(), self.reference)
        self.assertEqual(result["status"], "arithmetic_passed")
        self.assertEqual(result["adaptive_status"], "pending_kappa_evidence")
        self.assertEqual(result["check_count"], 56)
        self.assertFalse(result["optimizer_invoked"])
        self.assertFalse(result["rank_check_invoked"])
        self.assertFalse(result["fit_reuse_certified"])

    def test_analytic_supplied_kappa_full_adaptive(self) -> None:
        result = validate_arithmetic(balanced(), self.reference, kappa=-1.0, beta_hat=np.zeros(1))
        self.assertEqual(result["status"], "arithmetic_passed")
        self.assertEqual(result["adaptive_status"], "checked_supplied_kappa")
        self.assertEqual(result["check_count"], 83)

    def test_kappa_value_and_score_witness_failures(self) -> None:
        checks = validate_kappa(balanced(), self.reference, -0.9, np.zeros(1))
        self.assertFalse(checks[0]["passed"])
        with self.assertRaisesRegex(ArithmeticFailure, "score threshold"):
            validate_kappa(balanced(), self.reference, -1.0, np.array([0.1]))
        with self.assertRaisesRegex(ArithmeticFailure, "supplied together"):
            validate_arithmetic(balanced(), self.reference, kappa=-1.0)

    def test_constant_cancellation_and_adaptive_derivatives(self) -> None:
        data = balanced()
        beta = np.array([0.02])
        q, gradient = independent_catalytic(beta, data)
        q0, _ = independent_catalytic(np.zeros(1), data)
        constant = math.log(data.hazard) + 0.731
        for tau in (0.25, 1.0, 4.0):
            self.assertAlmostEqual(tau * (q - q0), tau * ((q + constant) - (q0 + constant)), places=12)
            joint = independent_adaptive(q, tau, data.p, -1.0)
            shifted = independent_adaptive(q + constant, tau, data.p, -1.0 + constant)
            self.assertAlmostEqual(joint, shifted, places=12)
            numerical = finite_difference(
                lambda b, tau=tau: independent_adaptive(independent_catalytic(b, data)[0], tau, data.p, -1.0), beta)
            np.testing.assert_allclose(numerical, tau * gradient, atol=3e-10, rtol=1e-8)

    def test_no_rank_constructor_optimizer_call(self) -> None:
        with patch.object(np.linalg, "matrix_rank", side_effect=AssertionError("SVD forbidden")):
            result = validate_arithmetic(balanced(), self.reference, kappa=-1.0, beta_hat=np.zeros(1))
        self.assertEqual(result["status"], "arithmetic_passed")
        with self.assertRaisesRegex(ArithmeticFailure, "optimizer disabled"):
            self.reference.catalytic_kappa(balanced().reference_data())

    def test_kernel_overflow_is_not_clipped(self) -> None:
        with self.assertRaisesRegex(ArithmeticFailure, "overflow"):
            independent_catalytic(np.array([1000.0]), balanced())

    def test_weighted_underflow_is_not_retried(self) -> None:
        with self.assertRaisesRegex(ArithmeticFailure, "underflow"):
            independent_breslow(np.array([1000.0]), np.array([[1.0], [-1.0]]),
                                np.array([1.0, 2.0]), np.array([0, 1]), np.ones(2))

    def test_invalid_domains_and_nonfinite_comparison(self) -> None:
        data = fixture()
        for name, value in (("hazard", math.inf), ("time_scale", 0.0),
                            ("real_event", np.array([1, 2, 0, 1])),
                            ("real_time", np.array([1.0, math.nan, 2.0, 4.0]))):
            invalid = copy.copy(data)
            object.__setattr__(invalid, name, value)
            with self.assertRaises(ArithmeticFailure):
                invalid.validate()
        with self.assertRaises(ArithmeticFailure):
            compare("nonfinite", math.inf, 0.0, atol=1e-9, rtol=1e-11)
        with self.assertRaisesRegex(ArithmeticFailure, "comparison error"):
            compare("finite subtraction overflow", 1e308, -1e308, atol=1e-9, rtol=1e-11)
        with self.assertRaises(ArithmeticFailure):
            independent_adaptive(0.0, -1.0, 1, -1.0)

    def test_source_pin_and_fixed_vectors(self) -> None:
        self.assertEqual(self.reference.source_sha256,
                         "53b38e5d9314fefcfd37260ac95d1bd9400af44f564c2142f7e7d61986f20332")
        self.assertEqual([name for name, _ in beta_vectors(3)],
                         ["zero", "alternating", "negative_alternating", "sine"])
        self.assertTrue(all(np.max(np.abs(vector)) <= 0.001 for _, vector in beta_vectors(3)))

    def test_training_median_and_hazard_units(self) -> None:
        self.assertTrue(all(row["passed"] for row in validate_training_units(fixture())))
        wrong = copy.copy(fixture())
        object.__setattr__(wrong, "hazard", 0.75)
        self.assertFalse(validate_training_units(wrong)[1]["passed"])


if __name__ == "__main__":
    unittest.main()
