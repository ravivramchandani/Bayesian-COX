# Phase 0 — Repair and verification

Date: 2026-08-14
Exit gate: `make test`, `make lint`, and the coordination schema validator all
pass, and both baselines reach their published concordance range on all three
cohorts.

## What was wrong

Every committed result had been produced from synthetic data. The dataset
script fell back to a generator whenever scikit-survival failed to import,
and the fallback was silent. In that generator the outcome is drawn
independently of every covariate, so no signal existed to find. The
preprocessing pipeline crashed on the real cohorts, so they were never
processed.

Convergence diagnostics were stub functions returning fixed passing values.
The concordance index, random survival forest and DeepSurv were each written
by hand and never checked against a reference. The explainability module was
empty although a report describing its findings existed. Four of seven test
files were empty, as were the Makefile, `environment.yml`, `requirements.txt`
and `LICENSE`.

## What was done

Data path rebuilt with no fallback; a missing source now raises. METABRIC is
derived from the clinical export, with the event indicator taken as the
complement of `overall_survival`. Preprocessing detects categorical columns
by dtype rather than trusting configuration, which was the specific defect
that crashed on GBSG2's `tgrade`.

Metrics delegate to scikit-survival, adding the time-dependent AUC the
methodology requires. Cox PH moved to lifelines and the random survival
forest to scikit-survival. The Bayesian Cox model kept its PyMC
implementation and gained the three specified priors, NUTS by default, and
diagnostics computed from the trace.

Explainability implemented as posterior signal against post-hoc SHAP.
Coordination layer added. Dead modules, superseded scripts and invalidated
artefacts removed.

## Verification

| Check | Result |
| :--- | :--- |
| Test suite | 44 passed |
| Ruff | clean |
| Coordination schemas | passed |
| GBSG2 Cox PH | 0.702 against a published 0.67 |
| WHAS500 Cox PH | 0.722 against a published 0.75 |
| METABRIC Cox PH | 0.665 against a published 0.63 |
| Signal preserved through preprocessing | GBSG2 `pnodes` 0.650, previously 0.499 |
| All three priors converge | R-hat 1.0000, divergences under 0.02% |

## Follow-on

The regularised horseshoe replaced the plain horseshoe after the latter
produced 208 divergent transitions on GBSG2. Phase 2 should sweep the global
scale to confirm the choice is not sensitive to `tau0`.
