"""Synthetic-only candidate checks; no cohort, fit, optimizer or evaluation data."""

from __future__ import annotations

import copy
import os
import pickle
import subprocess
import sys
import tempfile
import threading
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pandas as pd

from src.pipelines.extensions import correction_generator as candidate

SOURCE = (Path(os.environ["BAYES_COX_ORIGINAL_SOURCE"]).resolve()
          if os.environ.get("BAYES_COX_ORIGINAL_SOURCE") else None)
HERE = Path(__file__).absolute().parent


def tiny_proposal(seed: int, *, rejected: bool = False) -> candidate.DrawProposal:
    """Invent an in-memory proposal for wrapper control tests only."""
    design = np.zeros((2, 2)) if rejected else np.eye(2)
    data = candidate.SyntheticInputs(design, np.array([1.0, 2.0]), 1.0)
    return candidate.DrawProposal(data, None if rejected else {"seed": seed, "original": True},
                                  {"seed": seed, "synthetic_fixture": True})


def synthetic_fixture(*, singleton: bool = False) -> tuple[pd.DataFrame, dict, np.ndarray, np.ndarray]:
    """Create numeric/category training rows, times and events with no test rows."""
    levels = ["a"] * 999 + ["b"] if singleton else ["a"] * 500 + ["b"] * 300 + ["c"] * 200
    training = pd.DataFrame({"x": np.linspace(-1, 2, 1000), "category": levels})
    spec = {"numeric": ["x"], "categorical": ["category"]}
    return training, spec, np.linspace(1, 3, 1000), np.ones(1000, dtype=int)


def isolated_adapter(*, singleton: bool = False) -> candidate.IsolatedOriginalAdapter:
    """Bind only invented fixtures to the byte-pinned original-source child."""
    return candidate.IsolatedOriginalAdapter(SOURCE, *synthetic_fixture(singleton=singleton))


def direct_original_fixture(
    training: pd.DataFrame, spec: dict, time: np.ndarray, event: np.ndarray,
    *, seed: int, gene_budget: int,
) -> dict:
    """Run only the normal original generator in a private control process."""
    request = pickle.dumps({"training": training, "spec": spec, "time": time,
                            "event": event, "seed": seed, "gene_budget": gene_budget}, protocol=5)
    script = '''
import pickle,sys
from pathlib import Path
root=Path(sys.argv[1])
sys.path.insert(0,str(root))
import src.pipelines.extensions.preprocessing as original
for name,module in list(sys.modules.items()):
    if name=='src' or name.startswith('src.'):
        assert root in Path(module.__file__).resolve().parents
request=pickle.loads(sys.stdin.buffer.read())
processor=original.ExtensionPreprocessor(request['spec'],request['gene_budget']).fit(request['training'])
data,metadata=original.generate_catalytic_data(request['training'],processor,request['time'],request['event'],request['seed'])
sys.stdout.buffer.write(pickle.dumps({'design':data.design,'time':data.time,'hazard':data.hazard,
                                    'metadata':metadata,'processor':processor.metadata()},protocol=5))
'''
    candidate._source_bytes(SOURCE)
    with tempfile.TemporaryDirectory(prefix="generator-correction-control-") as temporary:
        cache = Path(temporary)
        environment = {**os.environ, "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1",
                       "MKL_NUM_THREADS": "1", "VECLIB_MAXIMUM_THREADS": "1", "NUMEXPR_NUM_THREADS": "1",
                       "PYTENSOR_FLAGS": "compiledir=" + str(cache / "pytensor"),
                       "MPLCONFIGDIR": str(cache / "matplotlib"), "XDG_CACHE_HOME": str(cache)}
        control = subprocess.run([sys.executable, "-I", "-B", "-c", script, str(SOURCE)],
                                 input=request, capture_output=True, check=False, env=environment)
        if control.returncode:
            raise RuntimeError(control.stderr.decode(errors="replace"))
        return pickle.loads(control.stdout)


class PureWrapperTests(unittest.TestCase):
    """Check retry policy and accounting independently of scientific imports."""

    def test_first_data_and_legacy_metadata_unchanged(self) -> None:
        """An accepted first proposal is returned without metadata mutation."""
        proposal = tiny_proposal(260817)
        before = copy.deepcopy(proposal.legacy_metadata)
        draw = Mock(return_value=proposal)
        result = candidate.generate_rank_conditioned(draw, 260817)
        draw.assert_called_once_with(260817)
        self.assertIs(result.proposal, proposal)
        self.assertEqual(result.proposal.legacy_metadata, before)
        self.assertTrue(result.proposal_metadata["first_draw_accepted"])
        self.assertEqual(result.proposal_metadata["accepted_attempt_index"], 0)
        self.assertFalse(result.proposal_metadata["fit_reuse_certified"])

    def test_retry_seed_order_then_acceptance(self) -> None:
        """Only tagged rejections consume retry indices one and two."""
        seeds = []

        def draw(seed: int) -> candidate.DrawProposal:
            seeds.append(seed)
            if len(seeds) <= 2:
                raise candidate.FrozenRankRejection(tiny_proposal(seed, rejected=True))
            return tiny_proposal(seed)

        result = candidate.generate_rank_conditioned(draw, 4, cap=3)
        self.assertEqual(seeds, [4, candidate.deterministic_seed(4, "rank_conditioned_retry", 1),
                                 candidate.deterministic_seed(4, "rank_conditioned_retry", 2)])
        self.assertEqual(result.proposal_metadata["attempts_generated"], 3)
        self.assertEqual(result.proposal_metadata["accepted_attempt_index"], 2)
        self.assertEqual([r["legacy_metadata_returned"] for r in result.proposal_metadata["attempts"]],
                         [False, False, True])

    def test_exhausted_cap_one_and_256(self) -> None:
        """Both candidate bounds include the unchanged first draw exactly once."""
        for cap in (1, 256):
            seeds = []

            def draw(seed: int, *, recorded: list[int] = seeds) -> candidate.DrawProposal:
                recorded.append(seed)
                raise candidate.FrozenRankRejection(tiny_proposal(seed, rejected=True))

            with self.subTest(cap=cap), self.assertRaises(candidate.RankConditionedExhausted) as caught:
                candidate.generate_rank_conditioned(draw, 4, cap=cap)
            metadata = caught.exception.proposal_metadata
            self.assertEqual(len(seeds), cap)
            self.assertEqual(seeds[0], 4)
            if cap > 1:
                self.assertEqual(seeds[-1], candidate.deterministic_seed(4, "rank_conditioned_retry", 255))
            self.assertTrue(metadata["exhausted"])
            self.assertIsNone(metadata["accepted_attempt_index"])
            self.assertEqual(metadata["attempts_generated"], cap)
            self.assertEqual(metadata["proposal_metadata_sha256"], candidate._canonical(
                {k: v for k, v in metadata.items() if k != "proposal_metadata_sha256"}))

    def test_invalid_cap_refuses_before_drawing(self) -> None:
        """Zero, invalid types and a cap beyond this bounded candidate are refused."""
        for cap in (0, -1, True, 1.5, "2", None, 257):
            draw = Mock()
            with self.subTest(cap=cap), self.assertRaises(ValueError):
                candidate.generate_rank_conditioned(draw, 4, cap=cap)
            draw.assert_not_called()

    def test_nonrank_errors_escape_without_retry(self) -> None:
        """Even an untagged same-message ValueError is never retryable."""
        errors = [ValueError(candidate.RANK_MESSAGE), ValueError("nonfinite synthetic times"),
                  RuntimeError("optimizer failure"), RuntimeError("MCMC failure")]
        for error in errors:
            draw = Mock(side_effect=error)
            with self.subTest(error=error), self.assertRaises(type(error)) as caught:
                candidate.generate_rank_conditioned(draw, 4)
            self.assertIs(caught.exception, error)
            draw.assert_called_once_with(4)

    @unittest.skipUnless(SOURCE, "set BAYES_COX_ORIGINAL_SOURCE to the sealed production checkout")
    def test_seed_matches_exact_original_function(self) -> None:
        """Check all 255 retry indices against verified original seed bytes."""
        source = candidate._source_bytes(SOURCE)["src/pipelines/confirmatory/options.py"]
        name = "_synthetic_test_original_options"
        module = types.ModuleType(name)
        sys.modules[name] = module
        try:
            exec(compile(source, str(SOURCE / "src/pipelines/confirmatory/options.py"), "exec"), module.__dict__)
            for index in range(1, 256):
                self.assertEqual(candidate.deterministic_seed(4, candidate.RETRY_LABEL, index),
                                 module.deterministic_seed(4, candidate.RETRY_LABEL, index))
        finally:
            del sys.modules[name]


class ConstructorCaptureTests(unittest.TestCase):
    """Use fake module callbacks to check restoration without parent src imports."""

    def setUp(self) -> None:
        """Create a private fake module and training-only metadata stub."""
        self.module = types.ModuleType("_synthetic_capture_module")
        self.processor = SimpleNamespace(clinical=SimpleNamespace(required_source_columns=["x"]),
                                         genes=[], feature_names=["x"], metadata=lambda: {"fixture": True})
        self.training = pd.DataFrame({"x": [1.0, 2.0]})
        self.time = np.array([1.0, 2.0])
        self.event = np.ones(2, dtype=int)

    def capture(self) -> candidate.DrawProposal:
        """Call private interception with the fake module only."""
        return candidate._capture_original(self.module, self.training, self.processor, self.time, self.event, 4)

    def test_original_constructor_restored_for_other_exceptions(self) -> None:
        """ValueError, runtime error and BaseException all release the alias/lock."""
        for error in (ValueError("finite time guard"), RuntimeError("other failure"), KeyboardInterrupt()):
            original = Mock(side_effect=error)
            self.module.CatalyticData = original
            self.module.generate_catalytic_data = lambda *_a: self.module.CatalyticData(np.eye(2), self.time, 1.0)
            with self.subTest(error=type(error)), self.assertRaises(type(error)) as caught:
                self.capture()
            self.assertIs(caught.exception, error)
            self.assertIs(self.module.CatalyticData, original)
            self.assertFalse(candidate._INTERCEPTION_LOCK.locked())

    def test_same_message_outside_original_rank_guard_not_tagged(self) -> None:
        """A processor or unverified constructor message cannot spoof the tag."""
        error = ValueError(candidate.RANK_MESSAGE)
        self.module.CatalyticData = Mock()
        original = self.module.CatalyticData
        self.module.generate_catalytic_data = Mock(side_effect=error)
        with self.assertRaises(ValueError) as caught:
            self.capture()
        self.assertIs(caught.exception, error)
        self.assertIs(self.module.CatalyticData, original)
        original.assert_not_called()
        self.module.CatalyticData = Mock(side_effect=error)
        original = self.module.CatalyticData
        self.module.generate_catalytic_data = lambda *_a: self.module.CatalyticData(np.eye(2), self.time, 1.0)
        with self.assertRaises(ValueError) as caught:
            self.capture()
        self.assertIs(caught.exception, error)
        self.assertIs(self.module.CatalyticData, original)

    def test_serial_collision_and_foreign_thread_refused(self) -> None:
        """Concurrent interception is refused before changing any module alias."""
        original = Mock()
        self.module.CatalyticData = original
        candidate._INTERCEPTION_LOCK.acquire()
        try:
            with self.assertRaisesRegex(ValueError, "already active"):
                self.capture()
        finally:
            candidate._INTERCEPTION_LOCK.release()
        errors = []

        def attempt() -> None:
            try:
                self.capture()
            except ValueError as error:
                errors.append(error)

        thread = threading.Thread(target=attempt)
        thread.start()
        thread.join()
        self.assertEqual(len(errors), 1)
        self.assertIn("serial main thread", str(errors[0]))
        self.assertIs(self.module.CatalyticData, original)


@unittest.skipUnless(SOURCE, "set BAYES_COX_ORIGINAL_SOURCE to the sealed production checkout")
class IsolatedOriginalFixtureTests(unittest.TestCase):
    """Exercise only invented training fixtures through real original code."""

    def test_common_fixture_matches_direct_normal_original_import(self) -> None:
        """Normal package initialization and thin adapter produce identical values."""
        parent_src_modules = {n: id(v) for n, v in sys.modules.items() if n == "src" or n.startswith("src.")}
        training, spec, time, event = synthetic_fixture()
        request = pickle.dumps({"training": training, "spec": spec, "time": time, "event": event}, protocol=5)
        script = '''
import pickle,sys
from pathlib import Path
root=Path(sys.argv[1])
sys.path.insert(0,str(root))
import src.pipelines.extensions.preprocessing as original
for name,module in list(sys.modules.items()):
    if name=='src' or name.startswith('src.'):
        assert root in Path(module.__file__).resolve().parents
request=pickle.loads(sys.stdin.buffer.read())
processor=original.ExtensionPreprocessor(request['spec']).fit(request['training'])
data,metadata=original.generate_catalytic_data(request['training'],processor,request['time'],request['event'],260817)
sys.stdout.buffer.write(pickle.dumps({'design':data.design,'time':data.time,'hazard':data.hazard,'metadata':metadata},protocol=5))
'''
        candidate._source_bytes(SOURCE)
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=SOURCE, check=True, capture_output=True, text=True)
        self.assertEqual(commit.stdout.strip(), "119476fef55b1eeb690527f234c1423440720d45")
        temporary = tempfile.TemporaryDirectory(prefix="generator-correction-import-")
        self.addCleanup(temporary.cleanup)
        cache = Path(temporary.name)
        environment = {**os.environ, "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1",
                       "MKL_NUM_THREADS": "1", "VECLIB_MAXIMUM_THREADS": "1", "NUMEXPR_NUM_THREADS": "1",
                       "PYTENSOR_FLAGS": "compiledir=" + str(cache / "pytensor"),
                       "MPLCONFIGDIR": str(cache / "matplotlib"), "XDG_CACHE_HOME": str(cache)}
        control = subprocess.run([sys.executable, "-I", "-B", "-c", script, str(SOURCE)],
                                 input=request, capture_output=True, check=False, env=environment)
        self.assertEqual(control.returncode, 0, control.stderr.decode(errors="replace"))
        baseline = pickle.loads(control.stdout)
        result = candidate.generate_rank_conditioned(isolated_adapter(), 260817, cap=2)
        np.testing.assert_array_equal(result.proposal.data.design, baseline["design"])
        np.testing.assert_array_equal(result.proposal.data.time, baseline["time"])
        self.assertEqual(result.proposal.data.hazard, baseline["hazard"])
        self.assertEqual(result.proposal.legacy_metadata, baseline["metadata"])
        self.assertEqual(result.proposal_metadata["attempts_generated"], 1)
        self.assertTrue(result.proposal.actual_metadata["constructor_restored"])
        self.assertEqual(result.proposal.actual_metadata["original_retry_seed_1"],
                         candidate.deterministic_seed(260817, candidate.RETRY_LABEL, 1))
        self.assertEqual(parent_src_modules, {n: id(v) for n, v in sys.modules.items()
                                              if n == "src" or n.startswith("src.")})

    def test_singleton_omission_deterministically_recovers(self) -> None:
        """Seed4 rejects the omitted singleton; its first declared retry succeeds."""
        result = candidate.generate_rank_conditioned(isolated_adapter(singleton=True), 4, cap=2)
        self.assertEqual(result.proposal_metadata["accepted_attempt_index"], 1)
        rows = result.proposal_metadata["attempts"]
        self.assertEqual([row["seed"] for row in rows], [4, 341562260])
        self.assertEqual([row["status"] for row in rows], ["frozen_rank_rejected", "accepted_original_constructor"])
        self.assertFalse(rows[0]["legacy_metadata_returned"])
        self.assertTrue(rows[0]["actual_proposal_metadata"]["constructor_restored"])
        self.assertEqual(result.proposal.legacy_metadata["seed"], 341562260)
        self.assertGreater(np.sum(result.proposal.data.design[:, 1]), 0)

    def test_singleton_cap_one_exhausts_without_new_draw(self) -> None:
        """The actual rejected first constructor remains an explicit execution outcome."""
        with self.assertRaises(candidate.RankConditionedExhausted) as caught:
            candidate.generate_rank_conditioned(isolated_adapter(singleton=True), 4, cap=1)
        self.assertEqual(caught.exception.proposal_metadata["attempts_generated"], 1)
        self.assertFalse(caught.exception.proposal_metadata["attempts"][0]["legacy_metadata_returned"])

    def test_actual_structural_dependency_exhausts_cap(self) -> None:
        """An original derived-column dependency remains rank deficient at every draw."""
        training = pd.DataFrame({"x": np.linspace(1, 3, 32), "one": np.ones(32)})
        spec = {"numeric": ["x"], "categorical": [], "engineered": [
            {"name": "x_copy", "expression": "x * one", "source_features": ["x", "one"]}]}
        adapter = candidate.IsolatedOriginalAdapter(SOURCE, training, spec,
                       np.linspace(1, 2, 32), np.ones(32, dtype=int))
        actual = []

        def observed(seed: int) -> candidate.DrawProposal:
            try:
                return adapter(seed)
            except candidate.FrozenRankRejection as error:
                actual.append(error.proposal)
                raise

        with self.assertRaises(candidate.RankConditionedExhausted) as caught:
            candidate.generate_rank_conditioned(observed, 4, cap=2)
        metadata = caught.exception.proposal_metadata
        self.assertTrue(metadata["exhausted"])
        self.assertIsNone(metadata["accepted_attempt_index"])
        self.assertEqual(len(actual), 2)
        self.assertEqual(metadata["attempts_generated"], 2)
        for proposal, record in zip(actual, metadata["attempts"], strict=True):
            np.testing.assert_array_equal(proposal.data.design[:, 0], proposal.data.design[:, 1])
            self.assertEqual(record["constructor_inputs"], proposal.data.hashes())
            self.assertTrue(proposal.actual_metadata["constructor_restored"])
            self.assertIsNone(proposal.legacy_metadata)
            self.assertEqual(record["status"], "frozen_rank_rejected")

    def test_hazard_and_preprocessing_errors_are_not_retried(self) -> None:
        """Real original training guards retain their types/messages and stop once."""
        training, spec, time, event = synthetic_fixture()
        adapter = candidate.IsolatedOriginalAdapter(SOURCE, training, spec, time, event * 0)
        draw = Mock(side_effect=adapter)
        with self.assertRaisesRegex(ValueError, "cannot fit the training exponential reference"):
            candidate.generate_rank_conditioned(draw, 4, cap=2)
        draw.assert_called_once_with(4)
        bad_spec = {"numeric": ["missing"], "categorical": []}
        draw = Mock(side_effect=candidate.IsolatedOriginalAdapter(SOURCE, training, bad_spec, time, event))
        with self.assertRaisesRegex(ValueError, "requires missing source columns"):
            candidate.generate_rank_conditioned(draw, 4, cap=2)
        draw.assert_called_once_with(4)

    def test_restored_state_preserves_clinical_and_singleton_proposals(self) -> None:
        """Restoring learned state preserves both accepted and rejected first draws."""
        for singleton, seed, cap in ((False, 260817, 2), (True, 4, 2)):
            with self.subTest(singleton=singleton):
                training, spec, time, event = synthetic_fixture(singleton=singleton)
                baseline = candidate.generate_rank_conditioned(isolated_adapter(singleton=singleton), seed, cap=cap)
                state = baseline.proposal.actual_metadata["processor_metadata"]
                sources = baseline.proposal.actual_metadata["source_variables"]
                adapter = candidate.IsolatedOriginalAdapter(
                    SOURCE, training[sources], spec, time, event, processor_metadata=state)
                result = candidate.generate_rank_conditioned(adapter, seed, cap=cap)
                np.testing.assert_array_equal(result.proposal.data.design, baseline.proposal.data.design)
                np.testing.assert_array_equal(result.proposal.data.time, baseline.proposal.data.time)
                self.assertEqual(result.proposal.data.hazard, baseline.proposal.data.hazard)
                self.assertEqual(result.proposal.legacy_metadata, baseline.proposal.legacy_metadata)
                self.assertEqual(result.proposal.actual_metadata["processor_metadata"], state)
                self.assertEqual([r["constructor_inputs"] for r in result.proposal_metadata["attempts"]],
                                 [r["constructor_inputs"] for r in baseline.proposal_metadata["attempts"]])

    def test_restored_selected_genes_match_direct_original_control(self) -> None:
        """Removing unselected gene columns leaves the exact original prior inputs."""
        training, spec, time, event = synthetic_fixture()
        training["gene:1"] = 10 * np.sin(np.arange(len(training)) * 0.37)
        training["gene:2"] = 2 * np.cos(np.arange(len(training)) * 0.23)
        training["gene:3"] = np.linspace(0, 1, len(training))
        control = direct_original_fixture(training, spec, time, event, seed=260817, gene_budget=2)
        baseline = candidate.generate_rank_conditioned(
            candidate.IsolatedOriginalAdapter(SOURCE, training, spec, time, event, gene_budget=2), 260817)
        state = baseline.proposal.actual_metadata["processor_metadata"]
        self.assertEqual(state, control["processor"])
        narrow = training[baseline.proposal.actual_metadata["source_variables"]]
        self.assertNotIn("gene:3", narrow)
        restored = candidate.generate_rank_conditioned(candidate.IsolatedOriginalAdapter(
            SOURCE, narrow, spec, time, event, gene_budget=2, processor_metadata=state), 260817)
        for proposal in (baseline.proposal, restored.proposal):
            np.testing.assert_array_equal(proposal.data.design, control["design"])
            np.testing.assert_array_equal(proposal.data.time, control["time"])
            self.assertEqual(proposal.data.hazard, control["hazard"])
            self.assertEqual(proposal.legacy_metadata, control["metadata"])
        self.assertEqual(restored.proposal.actual_metadata["processor_metadata"], state)

    def test_restored_state_tampering_is_not_retried(self) -> None:
        """Invalid outer/clinical hashes and requested budgets stop before drawing."""
        training, spec, time, event = synthetic_fixture()
        baseline = candidate.generate_rank_conditioned(isolated_adapter(), 260817)
        state = baseline.proposal.actual_metadata["processor_metadata"]
        outer_bad = copy.deepcopy(state)
        outer_bad["keep_clinical"] = []
        clinical_bad = copy.deepcopy(state)
        clinical_bad["clinical"]["scaling"]["x"]["mean"] += 1
        clinical_bad["state_sha256"] = candidate._canonical(
            {k: v for k, v in clinical_bad.items() if k != "state_sha256"})
        for metadata, budget in ((outer_bad, 0), (clinical_bad, 0), (state, 1)):
            with self.subTest(budget=budget):
                draw = Mock(side_effect=candidate.IsolatedOriginalAdapter(
                    SOURCE, training, spec, time, event, gene_budget=budget, processor_metadata=metadata))
                with self.assertRaises(ValueError):
                    candidate.generate_rank_conditioned(draw, 260817, cap=2)
                draw.assert_called_once_with(260817)


if __name__ == "__main__":
    unittest.main(verbosity=2)
