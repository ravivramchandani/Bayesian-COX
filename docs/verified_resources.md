# Verified resource ledger

Checked: 2026-08-15. This ledger records resources that were actually
inspected. It distinguishes availability and implementation from completed
scientific results. External journal policies, fees and rankings can change
and must be rechecked at manuscript freeze and submission.

## Exact compute environment

The official confirmatory runtime is the fresh environment
`bayes-cox-lock-verify-20260815-b`, installed from `conda-lock.yml`. The
content-addressed lock has SHA-256
`1921895d4a404fc99e848d69ccd4a3f6639a3d1610315c82ecd463ed4bcdfb57`.
The older `bayes-cox` environment is not lock-equivalent because it resolves
PyTorch through a different package route.

| Resource | Independently verified status |
|---|---|
| Platform | macOS 26.6, arm64; lock target macOS arm64 |
| Python | 3.11.15 |
| Locked packages | 259 total: 237 conda and 22 PyPI records |
| NumPy / pandas / SciPy | 2.4.6 / 2.3.3 / 1.17.1 |
| PyMC / ArviZ | 5.28.5 / 0.23.4 |
| scikit-survival / lifelines | 0.28.0 / 0.30.3 |
| PyTorch / pycox / torchtuples | 2.13.0 / 0.3.0 / 0.2.2 |
| SHAP | 0.51.0 |
| h5py / HDF5 build / HDF5 runtime | 3.16.0 / 2.1.0 / 2.1.0 |
| Project suite | 150 tests passed without warnings in the exact environment on 2026-08-15 |
| Ruff | Clean in the exact environment on 2026-08-15 |
| LaTeX toolchain | Clean LaTeX/BibTeX build produced a 70-page A4 PDF; no undefined item, LaTeX warning or box warning on 2026-08-15 |

The environment verifier checks the lock digest, all locked records, direct
imports and HDF5 build/runtime compatibility. A different operating system or
architecture needs a separately generated and verified lock; portability is
not inferred from this Apple Silicon build.

## Core data

All required real data are local and independently retrievable. The three
confirmatory cohorts contain 3,166 subjects and 1,658 observed events in
total. No synthetic fallback exists.

| Cohort | Verified analysis records/events | Pinned source | Verified derived SHA-256 |
|---|---:|---|---|
| GBSG2 | 686 / 299 | scikit-survival v0.24.1 repository commit `3e887ed7307a60c08f3fafec8b00d57f7a2d4982` | `2158b777d27ecfb69b187d3cbcad13fd1eb92d626935c528a4465fea6490ae5f` |
| WHAS500 | 500 / 215 | scikit-survival v0.24.1 repository commit `3e887ed7307a60c08f3fafec8b00d57f7a2d4982` | `4bb01775c04eca11d7f06d6e5dfebd0a5cce75aa7e73fe4261732385be106fcc` |
| METABRIC | 1,980 / 1,144 | cBioPortal DataHub commit `165bd77077b03038f9c2ee104959eb474770b2a9` | `731ea80ce0240cb6aa96ffb0f4a3bb379615202966c954512664bef02b29545c` |

The GBSG2 and WHAS500 ARFF checksums, source citations, endpoint coding and
package data notice are stored in `data/manifest.yaml`. The package
distribution is GPL-3.0-or-later, but no separate original-dataset licence was
identified in its pinned data directory; the project therefore does not infer
broader patient-level redistribution rights.

METABRIC was rebuilt from the pinned cBioPortal patient and sample files. All
2,509 patient identifiers, survival status/missingness and mapped clinical
values matched the independently held proposal export; the eligibility rule
retains 1,980 complete positive-time records. The pinned metadata defines
overall survival in months since initial diagnosis. The study database is
ODbL-1.0 and requires attribution and share-alike handling of an adapted
database.

The earlier 1,904-row Kaggle/cBioPortal-derived METABRIC file remains pilot
input only. It yields 1,903 positive-time records and 1,103 deaths and cannot
represent the confirmatory cohort.

The Rotterdam resource is publicly documented, but transport harmonisation
was never admitted or run. It and the optional ADEMP simulation were
permanently removed from this six-month study before freeze. This is a scope
decision, not unavailable evidence; neither is needed to answer the retained
research questions.

## Method and reporting resources

The following authoritative or primary sources are available and have been
mapped to tested implementation controls:

- Varma and Simon on nested validation and tuning bias:
  <https://doi.org/10.1186/1471-2105-7-91>.
- Uno and colleagues' censoring-robust concordance estimator:
  <https://doi.org/10.1002/sim.4154>.
- Survival calibration assessment:
  <https://doi.org/10.1186/s12916-019-1466-7>.
- The scikit-survival
  [metrics API](https://scikit-survival.readthedocs.io/en/stable/api/metrics.html)
  for Harrell and Uno concordance, cumulative/dynamic AUC, Brier score and
  integrated Brier score.
- Nadeau and Bengio's
  [corrected resampled inference paper](https://papers.neurips.cc/paper/1661-inference-for-the-generalization-error.pdf).
- The pinned pycox [CoxPH implementation](https://github.com/havakv/pycox)
  used for DeepSurv.
- Bayesian Analysis Reporting Guidelines, including all-parameter convergence
  and predictive checking:
  <https://pmc.ncbi.nlm.nih.gov/articles/PMC8526359/>.
- [TRIPOD+AI](https://www.bmj.com/content/385/bmj-2023-078378) for reporting
  prediction-model studies and
  [PROBAST+AI](https://www.bmj.com/content/388/bmj-2024-082505) for structured
  quality/risk-of-bias assessment.

The code now implements fold-local transformations, deterministic paired
repeated folds, training-defined horizons, IPCW metrics, calibration
parameters and curves, corrected paired inference, full Bayesian diagnostics,
predictive checks, frozen-cell explanation analysis and prespecified
robustness. This establishes implementation availability, not a completed
confirmatory result. Production effects remain unavailable until the frozen
runs finish.

## Publication resources

The owner-approved primary target is
[BMC Medical Research Methodology](https://link.springer.com/journal/12874/aims-and-scope).
Its official page, checked 2026-08-15, explicitly includes healthcare research
methodology, data analysis/statistical modelling and empirical studies of how
methodological choices affect outcomes. Its current official
[submission guidelines](https://link.springer.com/journal/12874/submission-guidelines)
accept TeX/LaTeX, require a data-availability statement and list a fully open-
access APC of GBP 2,290, USD 3,090 or EUR 2,690, subject to change and taxes.
The owner-approved alternative is
[Computer Methods and Programs in Biomedicine](https://www.sciencedirect.com/journal/computer-methods-and-programs-in-biomedicine),
whose scope is biomedical computing methods and software. Its current journal
page and publication route must be rechecked when the paper package is
formatted.

A public
[SCImago check](https://www.scimagojr.com/journalvalue.php?category=2713&country=OECD&ord=asc&order=publisher)
dated 2026-08-15 indicates BMC Medical Research Methodology is Q1 in a
relevant 2024 Scopus-derived category. This is not an institutional ranking
determination and is not permanent. The applicable database, category, year,
fees and instructions are reverified at manuscript freeze and immediately
before submission. The project may claim a Q1 target or quality ambition,
never guaranteed ranking, acceptance or publication.

## Availability conclusion

The retained master's-thesis programme is resource-feasible: the three
cohorts, exact runtime, reference libraries, statistical methods, reporting
standards and LaTeX toolchain are available. Remaining work is execution and
evidence review, not acquisition. No new core dataset, model family, prior,
simulation or transport branch is justified within the frozen six-month
scope.
