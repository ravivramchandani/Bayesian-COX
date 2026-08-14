# HANDOFF

State needed to resume work in a new session or on another machine.

Updated: 2026-08-14

## Environment

Conda environment `bayes-cox`, Python 3.11, specified in `environment.yml`.

```bash
conda activate bayes-cox
make test
```

PyMC's parallel sampler is unreliable on this macOS setup; chains run
sequentially (`cores=1`). Each chain takes seconds at this model size, so the
parallel path is not worth restoring.

## Current state

Phase 0 is complete. The data path, metrics, baselines, Bayesian inference,
diagnostics and explainability were rebuilt and are under test. All 44 tests
pass and ruff is clean.

Phase 1 is running: the full benchmark and explainability comparison across
all three cohorts.

## Reproducing results

```bash
make data        # ~1 minute
make benchmark   # ~1 hour, Bayesian fits dominate
make explain     # ~30 minutes
make figures
make reports
```

Reduce `--draws`, `--tune` and `--cv-splits` for a faster pass. The Bayesian
cross-validation deliberately uses a shorter chain than the reported test-set
fit; see `build_models` in `scripts/run_benchmark.py`.

## What was invalidated

Every result, figure and report committed before 2026-08-14 was produced from
synthetic data and has been removed. See the JOURNAL entry for the evidence.
Nothing from the previous `reports/` should be cited.

## Not yet built

- Statistical comparison across CV folds with multiplicity control (Phase 2).
- Prior sensitivity sweep (Phase 2).
- Robustness runs: censoring rate, small sample, WHAS500 without `los`
  (Phase 3).
- DeepSurv is implemented but not in the benchmark; the deep-learning arm is
  pending Q-003.
