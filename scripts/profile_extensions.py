"""Profile training-only extension computation without outer-test scoring."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.survival_folds import repeated_survival_folds
from src.models.bayesian.extensions import ExtensionBayesianCox
from src.pipelines.extensions.preprocessing import ExtensionPreprocessor, generate_catalytic_data
from src.utils.io import read_mapping, write_json_atomic
from src.utils.reproducibility import sha256_file


def main() -> None:
    """Write measured training-only timing, never held-out model performance."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matched", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--genes", type=int, default=512)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    data = pd.read_parquet(args.matched)
    t, e = data.duration.to_numpy(float), data.event.to_numpy(int)
    fold = repeated_survival_folds(t, e, n_splits=5, n_repeats=5, base_seed=260817, max_time_bins=4)[0]
    training = data.iloc[fold.train_indices]
    tt, ee = t[fold.train_indices], e[fold.train_indices]
    started = time.perf_counter()
    processor = ExtensionPreprocessor(read_mapping(root / "config/datasets.yaml")["metabric"]["primary_features"], args.genes).fit(training)
    x = processor.transform(training)
    synthetic, prior_meta = generate_catalytic_data(training, processor, tt, ee, 280928)
    result = {"purpose": "training-only computational profile; no outer-validation scores",
              "matched_sha256": sha256_file(args.matched), "genes": args.genes,
              "n_training": len(tt), "events": int(ee.sum()), "p": x.shape[1],
              "preparation_seconds": time.perf_counter() - started, "prior_data": prior_meta,
              "draws": 100, "tune": 100, "chains": 1, "target_accept": 0.999, "models": {}}
    write_json_atomic(args.output, result)
    for key in ("pv_horseshoe", "catalytic_fixed", "catalytic_adaptive"):
        started = time.perf_counter()
        model = ExtensionBayesianCox(key, synthetic=synthetic if key.startswith("catalytic") else None,
                                     draws=100, tune=100, chains=1, cores=1, target_accept=0.999,
                                     random_state=280928)
        model.fit(x, tt, ee)
        result["models"][key] = {"seconds": time.perf_counter() - started,
                                  "details": model.details,
                                  "diagnostics_role": "one-chain profile; no evidence gate or predictive result"}
        write_json_atomic(args.output, result, overwrite=True)
        print(key, result["models"][key]["seconds"], flush=True)


if __name__ == "__main__":
    main()
