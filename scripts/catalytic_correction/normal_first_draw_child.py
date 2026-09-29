"""Owned clean normal-source attempt0 replay; no candidate adapter imports."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import json
import os
import pickle
import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True


def owned_main(directory: Path, request_sha: str) -> None:
    """Consume only one locally owned hashed transport and emit numeric proof."""
    directory = directory.absolute()
    if any(item.is_symlink() for item in (directory, *directory.parents)):
        raise ValueError("linked owned child directory")
    request_path = directory / "request.json"
    if hashlib.sha256(request_path.read_bytes()).hexdigest() != request_sha:
        raise ValueError("owned request bytes differ")
    request = json.loads(request_path.read_text())
    core_path = Path(request["preflight_core"])
    if hashlib.sha256(core_path.read_bytes()).hexdigest() != request["preflight_core_sha256"]:
        raise ValueError("owned child core bytes differ")
    spec = importlib.util.spec_from_file_location("_independent_first_core", core_path)
    if spec is None or spec.loader is None:
        raise ValueError("cannot load independent hash helpers")
    pf = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = pf
    spec.loader.exec_module(pf)
    if pf.read_sealed(request_path) != request or pf.sha256_file(Path(__file__)) != request["child_source_sha256"]:
        raise pf.InvalidCheckpoint("owned child request/source differs")
    if any(name == "src" or name.startswith("src.") for name in sys.modules):
        raise pf.InvalidCheckpoint("child has foreign scientific namespace")
    for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
        if os.environ.get(name) != "1":
            raise pf.InvalidCheckpoint("child numeric threads must be1")
    with pf.Claim(directory / "normal_child.claim.json", request_sha):
        execute_owned(directory, request, pf)


def execute_owned(directory: Path, request: dict[str, Any], pf: Any) -> None:
    """Hold exclusive ownership across the normal import and untouched call."""
    source = Path(request["source"])
    sys.pycache_prefix = str(directory / "cache" / "python")
    os.environ.update(MPLCONFIGDIR=str(directory / "cache" / "matplotlib"),
                      NUMBA_CACHE_DIR=str(directory / "cache" / "numba"),
                      PYTENSOR_FLAGS=f"compiledir={directory / 'cache' / 'pytensor'}")
    sys.path.insert(0, str(source))
    module = importlib.import_module("src.pipelines.extensions.preprocessing")
    for name, loaded in list(sys.modules.items()):
        if name == "src" or name.startswith("src."):
            path = Path(loaded.__file__).absolute()
            if not path.is_relative_to(source):
                raise pf.InvalidCheckpoint("child normal scientific module came from another checkout")
            relative = str(path.relative_to(source))
            if request["original_input_sha256"].get(relative) != pf.sha256_file(path):
                raise pf.InvalidCheckpoint("child normal original source bytes differ")
    payload_path = directory / "owned_training_transport.pkl"
    if pf.artifact_binding(payload_path) != request["payload_artifact"] or payload_path.is_symlink():
        raise pf.InvalidCheckpoint("owned training transport bytes differ")
    # Allowed only for this newly owned, sealed/hash-bound local temporary file.
    with payload_path.open("rb") as stream:
        payload = pickle.load(stream)  # noqa: S301 - locally owned and byte-bound transport, never external evidence
    training, time, event = payload["training"], payload["time"], payload["event"]
    expected = request["expected_input_witness"]
    import numpy as np
    if pf.source_frame_witness(training, list(training.columns)) != request["full_raw_training_witness"]:
        raise pf.InvalidCheckpoint("independent full raw training frame differs")
    processor = module.ExtensionPreprocessor(payload["feature_spec"], payload["gene_budget"]).fit(training)
    sources = list(dict.fromkeys(processor.clinical.required_source_columns + processor.genes))
    actual_input = {"ordered_training_subject_ids": training.subject_id.tolist(),
                    "processor_metadata": processor.metadata(), "source_values": pf.source_frame_witness(training, sources),
                    "real_design": pf.array_witness(processor.transform(training).to_numpy(float)),
                    "training_time": pf.array_witness(time), "training_event": pf.array_witness(event)}
    if any(actual_input[key] != expected[key] for key in actual_input):
        raise pf.InvalidCheckpoint("independent normal original training/processor inputs differ")
    original = module.CatalyticData
    captured: dict[str, Any] = {}

    def capture(design: Any, synthetic_time: Any, hazard: Any) -> Any:
        if captured:
            raise pf.InvalidCheckpoint("original generator called constructor more than once")
        captured.update(synthetic_design=np.asarray(design).copy(), synthetic_time=np.asarray(synthetic_time).copy(),
                        hazard=np.asarray(hazard, dtype=float),
                        time_scale=np.asarray(float(np.median(time[event == 1])), dtype=float))
        try:
            return original(design, synthetic_time, hazard)
        except ValueError as error:
            trace = error.__traceback__
            while trace is not None and trace.tb_next is not None:
                trace = trace.tb_next
            guard = getattr(original, "__post_init__", None)
            if (type(error) is ValueError and error.args == ("synthetic design is not full column rank",)
                    and trace is not None and guard is not None and trace.tb_frame.f_code is guard.__code__):
                captured["rank_error"] = error
            raise

    error, legacy = None, None
    module.CatalyticData = capture
    try:
        try:
            _, legacy = module.generate_catalytic_data(training, processor, time, event,
                                                      request["request"]["original_generation_seed"])
        except Exception as caught:
            error = caught
    finally:
        module.CatalyticData = original
    if module.CatalyticData is not original:
        raise pf.InvalidCheckpoint("original constructor alias not restored")
    for name, loaded in list(sys.modules.items()):
        if name == "src" or name.startswith("src."):
            path = Path(loaded.__file__).absolute()
            if not path.is_relative_to(source) or request["original_input_sha256"].get(
                    str(path.relative_to(source))) != pf.sha256_file(path):
                raise pf.InvalidCheckpoint("child final original import origin/source bytes differ")
    if pf.sha256_file(Path(__file__)) != request["child_source_sha256"]:
        raise pf.InvalidCheckpoint("independent child source changed during execution")
    status = ("accepted_original_constructor" if error is None else "frozen_rank_rejected"
              if error is captured.get("rank_error") else "nonrank_error")
    arrays = {key: captured[key] for key in ("synthetic_design", "synthetic_time", "hazard", "time_scale")} if "synthetic_design" in captured else None
    artifacts, witnesses = {"request.json": pf.artifact_binding(directory / "request.json")}, None
    if arrays is not None:
        pf.save_arrays(directory / "proposal.npz", arrays)
        witnesses = {key: pf.array_witness(value) for key, value in arrays.items()}
        artifacts["proposal.npz"] = pf.artifact_binding(directory / "proposal.npz")
    result = pf.seal({"schema_version": 1, "request": request["request"], "status": status,
        "seed": request["request"]["original_generation_seed"], "processor_metadata": processor.metadata(),
        "array_witnesses": witnesses, "legacy_metadata": legacy,
        "error": None if error is None else pf.error_record(error), "artifacts": artifacts,
        "normal_import_source_path": str(source), "original_source_input_hashes": request["original_input_sha256"],
        "owned_transport_sha256": request["payload_artifact"]["sha256"],
        "owned_process": {"pid": os.getpid(), "parent_pid": os.getppid(), "interpreter": sys.executable,
                          "isolated": bool(sys.flags.isolated), "dont_write_bytecode": sys.dont_write_bytecode},
        "constructor_alias_restored": True, "candidate_adapter_or_helpers_imported": False,
        "input_scope": "full_raw_training_local_preprocessor_fit; no_heldout_rows_received",
        "no_optimizer_mcmc_model_prediction_or_score_run": True})
    pf.write_json_new(directory / "receipt.json", result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owned-directory", type=Path, required=True)
    parser.add_argument("--request-sha256", required=True)
    args = parser.parse_args()
    owned_main(args.owned_directory, args.request_sha256)
