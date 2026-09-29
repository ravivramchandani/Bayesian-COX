"""Probe only disposable fictional reuse metadata, with no controller execution."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

CARRIER = Path("/Users/macuser/bayes-cox-runs/extensions-20260928/generator_correction_guarded_dispatch_v2")
sys.path.insert(0, str(CARRIER))
spec = importlib.util.spec_from_file_location("_independent_v2_regressions", CARRIER / "test_guarded_dispatch_regressions.py")
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
test = module.GuardV2Regressions()
test.setUp()
try:
    test.make_reuse("failed_diagnostics")
    f = test.fixture
    g = module.g
    path = f.output / "cells/a.json"
    original = g.document(path)
    results = []
    for key, value in (("changed_roles", ["model_sources"]), ("missing_roles", ["model_sources"]),
                       ("generator_failures", {"outer": "input_failure"}), ("tuning_record_reused_sha256", "1" * 64)):
        candidate = json.loads(json.dumps(original))
        decision = {name: item for name, item in candidate["decision"].items() if name != "decision_content_sha256"}
        decision[key] = value
        decision["decision_content_sha256"] = g.digest(decision)
        candidate["decision"] = decision
        test.rewrite(path, candidate)
        try:
            g.account_only(f.output, f.request, f.gates())
        except g.InvalidProof as error:
            results.append({"field": key, "rejected": True, "error": str(error)})
        else:
            results.append({"field": key, "rejected": False, "unexpectedly_accepted": True})
    assert f.controller_calls == 0
    assert not any(name == "src" or name.startswith("src.") for name in sys.modules)
    print(json.dumps({"status": "bounded_reuse_decision_consistency_observed", "results": results,
                      "actual_controller_scientific_or_checker_calls": 0, "fictional_only": True}, sort_keys=True))
finally:
    test.tearDown()
