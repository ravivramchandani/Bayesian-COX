# Bayesian Survival Models for Explainable Prediction of Diseases

Codebase for a Master of Applied Technologies thesis at the School of
Computing, Unitec.

The completed exploratory benchmark covers three implemented model families
on three clinical cohorts. A DeepSurv comparator, explicit calibration and a
leakage-safe confirmatory analysis are planned and gated in
`coordination/TODO.md`. Current result files are pilot evidence, not final
inferential results.

## Models

| Family | Implementation |
| :--- | :--- |
| Cox proportional hazards | lifelines |
| Random survival forest | scikit-survival |
| Bayesian Cox, weakly-informative Normal prior | PyMC, NUTS |
| Bayesian Cox, regularised horseshoe prior | PyMC, NUTS |
| Bayesian Cox, continuous spike-and-slab prior | PyMC, NUTS |
| DeepSurv comparator | Local implementation awaiting reference validation and benchmark integration |

The Bayesian Cox model uses a piecewise-exponential baseline hazard expressed
as a Poisson regression over subject-interval exposures. The two sparsity
priors expose a per-feature inclusion signal that serves as built-in
explainability.

## Cohorts

| Cohort | Subjects | Events | Source |
| :--- | ---: | ---: | :--- |
| GBSG2 | 686 | 299 | scikit-survival |
| WHAS500 | 500 | 215 | scikit-survival |
| METABRIC pilot subset | 1903 | 1103 | `data/external/METABRIC_RNA_Mutation.csv` |

All three carry time-to-event data with right censoring. In the METABRIC
source `overall_survival` encodes *alive*, so the event indicator is its
complement. Confirmatory METABRIC will be rebuilt from a pinned cBioPortal
clinical snapshot and is expected to contain 1,980 positive-time records and
1,144 deaths; see `docs/datasets.md`.

## Setup

Requires conda and Python 3.11.

```bash
make env
conda activate bayes-cox
```

## Running

```bash
make data        # download cohorts and build train/val/test splits
make eda         # exploratory analysis, figures and tables
make benchmark   # fit every model on every cohort
make explain     # posterior versus SHAP comparison
make figures     # thesis figures
make reports     # markdown reports from the result files
make test        # test suite
```

The thesis document lives in a separate Overleaf-backed repository beside
this one:

```bash
make thesis      # compile ../thesis-overleaf/Main.tex
make jargon      # check no internal identifiers reached the chapters
```

Override the location with `THESIS_DIR=/path/to/thesis`.

`make all` runs data, eda, benchmark and explain in order. The benchmark takes
roughly an hour; the Bayesian fits dominate. Reduce `--draws`, `--tune` and
`--cv-splits` for a faster pass.

Results are written to `reports/tables/` as JSON. `python
scripts/make_reports.py` renders the markdown reports from those files.

## Layout

```
config/         dataset schemas and model hyperparameters
coordination/   decisions, invariants, glossary, protocol, task list
data/           raw, processed and external data
scripts/        entry points for each stage
src/            data, models, evaluation, explainability, statistics
tests/          test suite
reports/        generated reports, tables and figures
```

## Reproducibility status

Every stochastic step takes an explicit seed. Cohort sizes and event counts
are asserted against their published values, preprocessing is checked to
preserve prognostic signal, metrics are checked against scikit-survival, and
baselines are checked against their published concordance range. Sampler
diagnostics are computed from the posterior trace rather than asserted.

Exact clean-clone numerical reproducibility is not yet claimed: dependencies,
source manifests and result manifests still need publication locks, and the
confirmatory fold-local pipeline is not yet implemented. Those acceptance
gates are T-110, T-120, T-125 and T-129.

Run `make test` to verify all of the above.
