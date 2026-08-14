# HANDOFF

State needed to resume work in a new session or on another machine.

Updated: 2026-08-14

## Environment

Use the named environment explicitly; the default shell Python does not carry
the survival stack.

```bash
conda activate bayes-cox
make test
make lint
```

Verified on 2026-08-14: 60 tests pass and ruff is clean. Dependencies are not
yet exactly locked, so do not claim clean-clone numerical reproducibility
until T-129 passes. PyMC chains run sequentially (`cores=1`) on this macOS
setup.

## Authoritative status

Phase 0 is complete. The exploratory Phase 1 core is also complete: 15
model-cohort fits, 18 explainability comparisons and 21 figures are present.
Calibration and DeepSurv were not integrated, so Phase 1 has not passed a
publication-quality exit gate.

The existing benchmark and explanation files are pilot evidence only. The
inspected holdout, fold-level preprocessing leakage, test-derived evaluation
horizons and missing paired fold predictions prevent confirmatory inference.
ADR-014 defines the replacement repeated nested-CV analysis.

The six-month programme is now defined in:

- `coordination/TODO.md` — live tasks, owners, weeks, dependencies and
  acceptance evidence;
- `docs/study_protocol.md` — RQs, estimands, design, gates and scope;
- `docs/claim_evidence_register.md` — permitted claim strength;
- ADR-014 through ADR-019 — binding methodology and scope choices; and
- Q-002 through Q-006 — owner-track ethics, release, approval, journal and
  clinical-review inputs.

## Data state

GBSG2 and WHAS500 match their scikit-survival sources. The active pilot uses a
1,904-row Kaggle/cBioPortal-derived METABRIC file and produces 1,903
positive-time records with 1,103 deaths. It is not the confirmatory source.

The proposal directory already contains the 2,509-row clinical export that
matches the pinned cBioPortal DataHub patient/sample files. Rebuilding it is
expected to yield 1,980 positive-time records and 1,144 deaths, adding 77
eligible records and 41 deaths. T-111 must complete before any confirmatory
METABRIC run.

Primary predictors require a timing audit. WHAS500 length of stay is excluded
from the admission-time primary model; METABRIC surgery/treatment-received
variables are excluded from the diagnosis-time primary model unless their
availability is defensible. Full feature sets are sensitivities under
ADR-015.

## Thesis state

The Overleaf repository is not submission-ready. A clean halt-on-error build
fails in `literature_review.tex`; a diagnostic nonstop build produced hundreds
of LaTeX errors and 349 undefined-citation warnings. Introduction,
methodology, results, conclusion, abstract and appendices are template/empty,
while the literature review is about 25,700 words and requires replacement by
a focused critical synthesis.

Writing begins in Week 1 in parallel with engineering. T-107 repairs the
build foundation; T-150 through T-160 govern substantive writing and review.

## Reproducing pilot results

```bash
make data
make benchmark
make explain
make figures
make reports
```

These commands reproduce development artefacts, not the future confirmatory
release. `make_figures.py` currently refits Bayesian models despite the old
architecture claim that it is a pure renderer; T-126 corrects the lineage.

## Next action

Start T-100/T-101/T-107 in parallel. Do not run new headline comparisons
until T-131 freezes the data, feature sets, protocol, environment and analysis
code. Continue engineering while owner questions are pending, consistent with
ADR-002.
