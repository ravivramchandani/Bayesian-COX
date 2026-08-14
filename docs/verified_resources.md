# Verified resource ledger

Checked: 2026-08-14. This ledger records availability, not task status. URLs,
versions, licences and journal rankings are rechecked at protocol freeze and
submission because external resources can change.

## Local compute and software

The `bayes-cox` conda environment is available and is the only verified
runtime. On 2026-08-14 it contained:

| Resource | Verified version/status |
|---|---|
| Python | 3.11.15 |
| NumPy | 2.4.6 |
| pandas | 2.3.3 |
| PyMC | 5.28.5 |
| ArviZ | 0.23.4 |
| scikit-survival | 0.28.0 |
| lifelines | 0.30.3 |
| SHAP | 0.51.0 |
| Project tests | 60 passed |
| Ruff | clean |
| LaTeX toolchain | available, but the current thesis source fails to compile cleanly |
| PyTorch / pycox / torchtuples | not installed in the named environment |

The environment specifications currently use lower bounds. T-129 must create
and verify an exact lock before reproducibility claims. DeepSurv reference
validation requires adding a pinned, Python-3.11-compatible PyTorch/pycox
stack or proving the local implementation against it.

## Data

| Resource | Availability | Verification |
|---|---|---|
| GBSG2 | Local and retrievable through [scikit-survival](https://scikit-survival.readthedocs.io/en/stable/api/generated/sksurv.datasets.load_gbsg2.html) | 686 records/299 events; local values match the package data |
| WHAS500 | Local and retrievable through [scikit-survival](https://scikit-survival.readthedocs.io/en/stable/api/generated/sksurv.datasets.load_whas500.html) | 500 records/215 deaths; local values match the package data |
| METABRIC pilot subset | Local Kaggle version-1 file | SHA-256 `d4802594827667a71a75b5ae5c3cad1eb4346222052fcc792361c64abc7e43bc`; pilot only |
| METABRIC confirmatory source | Local 2,509-row clinical export and [pinned cBioPortal DataHub snapshot](https://github.com/cBioPortal/datahub/tree/165bd77077b03038f9c2ee104959eb474770b2a9/public/brca_metabric) | Patient IDs, OS fields and clinical values agree; expected 1,980 positive-time records/1,144 deaths; rebuild pending |
| METABRIC licence | Available in the study directory | [ODbL attribution/share-alike terms](https://github.com/cBioPortal/datahub/blob/master/public/brca_metabric/LICENSE); public-release interpretation remains owner-pending |
| Optional Rotterdam transport cohort | Official [`survival::rotterdam` documentation](https://stat.ethz.ch/R-manual/R-devel/library/survival/html/rotterdam.html) and [CRAN package page](https://stat.ethz.ch/CRAN/web/packages/survival/index.html) available | Not admitted, downloaded or harmonised; governed by the Week 4 gate |

No new real dataset is needed for the core thesis. The three confirmatory
cohorts total 3,166 patients and 1,658 events after the planned METABRIC
repair.

## Method and evaluation references

- Nested validation and preprocessing/tuning leakage: Varma and Simon,
  <https://doi.org/10.1186/1471-2105-7-91>.
- Uno's censoring-robust concordance estimator:
  <https://doi.org/10.1002/sim.4154>.
- Calibration assessment for survival models:
  <https://doi.org/10.1186/s12916-019-1466-7>.
- scikit-survival's current
  [metrics API](https://scikit-survival.readthedocs.io/en/stable/api/metrics.html)
  exposes Harrell/Uno concordance, cumulative dynamic AUC, Brier score and IBS.
- Corrected resampled inference: Nadeau and Bengio,
  [primary paper](https://papers.neurips.cc/paper/1661-inference-for-the-generalization-error.pdf).
- DeepSurv reference implementation route: pycox
  [CoxPH/DeepSurv repository](https://github.com/havakv/pycox); not yet locally
  installed or validated.
- Simulation design and Monte Carlo uncertainty: Morris, White and Crowther,
  ADEMP, <https://doi.org/10.1002/sim.8086>.
- Bayesian reporting expectations, including all-parameter convergence and
  posterior predictive checks:
  [Bayesian Analysis Reporting Guidelines](https://pmc.ncbi.nlm.nih.gov/articles/PMC8526359/).

These sources establish available methods and good practice; they do not
pre-verify the project's future implementation. T-120 through T-129 require
reference and leakage tests.

## Reporting and risk-of-bias standards

- [TRIPOD+AI](https://www.bmj.com/content/385/bmj-2023-078378) is the current
  27-item reporting framework covering regression and machine-learning
  prediction-model development/evaluation.
- [PROBAST+AI](https://www.bmj.com/content/388/bmj-2024-082505) separates
  development quality from evaluation risk of bias and supplies four domains
  with signalling questions.

Both are available without credentials and are mandatory audit inputs, not
badges that can be claimed before completing the page-referenced checklists.

## Publication candidates

- [BMC Medical Research Methodology scope](https://bmcmedresmethodol.biomedcentral.com/submission-guidelines/aims-and-scope):
  primary candidate because it accepts empirical studies about methodological
  choices.
- [Computer Methods and Programs in Biomedicine](https://www.sciencedirect.com/journal/computer-methods-and-programs-in-biomedicine):
  main alternative for a validated biomedical methods/computing paper.
- *Journal of Biomedical Informatics* and *Artificial Intelligence in
  Medicine* are stretch candidates only if novelty and clinical-domain review
  become materially stronger.

“Q1” is not permanently attached to a journal: database, category and year
matter. T-105 must verify the institution-accepted quartile source and T-172
must repeat that check immediately before submission.

## Availability conclusion

The core project is resource-feasible now: all required real data, Python
runtime, survival libraries, Bayesian engine, tests and reporting standards
are available. The unresolved resources are governance decisions, an exact
dependency lock, validated DeepSurv dependencies and optional external-
transport harmonisation. Each has a dated task and a drop/fallback rule, so
none justifies acquiring a new core dataset.
