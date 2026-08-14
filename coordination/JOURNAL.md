# JOURNAL

Append-only record of findings and results. Facts and numbers, not process
narration.

---

## 2026-08-14 — Committed results were produced from synthetic data

`scripts/download_datasets.py` fell back to a synthetic generator whenever
scikit-survival failed to import, and the fallback was silent. In that
generator `time` and `cens` are drawn independently of every covariate, so the
data carries no signal by construction.

Confirmed from the scaler parameters in `data/processed/gbsg2/metadata.json`,
which match the generator rather than the real cohort: age 51.29/17.07 against
a real 53.05/10.11, tumour size 63.78/32.41 against 29.33/14.29, and
progesterone receptor standard deviation equal to its mean, the signature of
an exponential draw, against a real 202 versus 110.

Univariate concordance for `pnodes` was 0.645 in the real raw file and 0.499
after preprocessing. Every model sat between 0.427 and 0.576 across all three
cohorts because there was nothing to find. The pipeline crashed on the real
data at `src/data/preprocessing.py:281`, taking the mean of the non-numeric
`tgrade` column, so the real cohorts were never processed.

All figures, result tables and reports produced before this date are void.

## 2026-08-14 — Convergence diagnostics were fixed values

`MCMCDiagnostics.compute_rhat` returned `{"rhat_max": 1.01}` and
`compute_ess` returned `{"ess_bulk_min": 1500.0}` regardless of the fit.
`MCMCSampler.sample` returned `{"status": "ready"}` without sampling. Both
modules were removed and diagnostics are now computed from the trace with
arviz.

## 2026-08-14 — Baselines restored to the published range

After the data path was rebuilt, test-set concordance:

| Cohort | Cox PH | RSF | Previously reported |
|---|---|---|---|
| GBSG2 | 0.702 | 0.689 | 0.482 |
| WHAS500 | 0.722 | 0.743 | 0.469 |
| METABRIC | 0.665 | 0.675 | 0.513 |

Published Cox baselines for these cohorts are near 0.67, 0.75 and 0.63.

## 2026-08-14 — Plain horseshoe funnels under NUTS

The direct non-centred horseshoe produced 208 divergent transitions on GBSG2
across 8000 draws. Replacing it with the regularised horseshoe, where a slab
term bounds the local scales, reduced this to one divergence with R-hat
1.0000 and bulk effective sample size 1155. Concordance was unchanged at
0.702.

## 2026-08-14 — Full benchmark completed on real data

Fifteen model-cohort fits. Test-set concordance:

| Model | GBSG2 | WHAS500 | METABRIC |
|---|---|---|---|
| Cox PH | 0.7021 | 0.7215 | 0.6649 |
| Random survival forest | 0.6865 | 0.7504 | 0.6747 |
| Bayesian Cox, Normal | 0.6995 | 0.7310 | 0.6663 |
| Bayesian Cox, horseshoe | 0.7018 | 0.7454 | 0.6639 |
| Bayesian Cox, spike-and-slab | 0.6943 | 0.7293 | 0.6662 |

Every Bayesian fit converged: R-hat 1.0000 throughout, minimum bulk effective
sample size 1155, and one divergent transition in 8000 draws across the whole
run.

Two observations worth carrying into the analysis. The horseshoe is the
strongest Bayesian arm on the two smaller cohorts and gives the best
calibration on WHAS500 (IBS 0.1313 against 0.1445 for Cox PH), which is what
a shrinkage prior should do when the sample is small relative to the number
of covariates. On METABRIC, the largest cohort, the three priors are
indistinguishable — the likelihood dominates and the prior stops mattering.
That is the Bernstein-von Mises behaviour the panel asked to see addressed,
and it is now something the results demonstrate rather than assert.

Cost scales sharply with the horseshoe: 424 seconds on METABRIC against 88
for the Normal prior, from the smaller step sizes its geometry requires.

## 2026-08-14 — Kernel SHAP sampling capped after checking stability

Kernel SHAP's default coalition count scales with the feature count, which on
METABRIC against a 300-tree forest made the explainability run take hours.
Capping it at 256 coalitions per explained row brings one cohort-model pair to
31 seconds.

The cap was checked rather than assumed: two runs at different seeds on the
METABRIC forest agree at Spearman 0.989 with an identical top-five set, the
fourth and fifth features merely swapping places. That is well inside what a
rank comparison needs, which is all the built-in-versus-post-hoc analysis
uses the SHAP values for.

## 2026-08-14 — Censoring weights require a bounded test horizon

Time-dependent AUC and the integrated Brier score estimate censoring weights
from the training follow-up, so every test event time must fall inside it.
METABRIC and WHAS500 both contain test observations past their training
horizon, which raised rather than returning a value. Test observations beyond
the horizon are now administratively censored at it before the weighted
metrics are computed; concordance still uses the untruncated data. GBSG2 and
WHAS500 results are unchanged by this, since it only affects the case that
previously failed.

## 2026-08-14 — Built-in explainability tracks the model family, not the data

Eighteen comparisons across three cohorts. Spearman correlation between the
posterior ranking and SHAP:

| Cohort | vs Cox PH | vs random survival forest |
|---|---|---|
| GBSG2 | +0.57 to +0.95 | -0.19 to +0.13 |
| WHAS500 | +0.46 to +0.68 | +0.17 to +0.40 |
| METABRIC | +0.90 to +0.92 | +0.39 to +0.52 |

The posterior signal agrees strongly with attribution computed on Cox PH and
much less with attribution computed on the forest. Both the Bayesian model
and Cox PH are linear in the log hazard, so what the agreement measures is
shared model structure rather than a shared reading of the data. Any claim
that a built-in signal and a post-hoc one "agree" therefore has to name which
model the post-hoc signal was computed on.

The horseshoe is the exception worth noting: it is the only prior whose
ranking moves toward the forest on every cohort, which fits a prior that lets
a few coefficients escape shrinkage rather than spreading weight evenly.

The features the sparsity priors retain are the clinically expected ones —
positive lymph nodes on GBSG2, cardiogenic shock and age on WHAS500, age and
nodal status on METABRIC — so the signal is recovering known prognostic
structure rather than arbitrary directions.

## 2026-08-14 — Current benchmark is exploratory, not confirmatory

The benchmark holdout has been inspected and used in model interpretation.
Cross-validation receives a matrix whose imputation, encoding and scaling were
fitted on the full development training split, so each validation fold
informed its preprocessing. Evaluation horizons are selected from test event
times, and the result JSON retains only fold mean/standard deviation rather
than paired fold predictions. `src/statistics/permutation.py` also returns the
constant value `0.05` for every input and is not valid evidence.

The 15 fits and 18 explanation comparisons remain useful pipeline and
hypothesis-generating evidence. They cannot support confirmatory superiority,
equivalence, calibration or multiplicity-controlled claims. ADR-014 defines a
fold-local repeated nested-CV replacement.

## 2026-08-14 — Active METABRIC source omits eligible survival records

The active source is the 1,904-row, 693-column Kaggle version-1 combined
clinical/omics export, SHA-256
`d4802594827667a71a75b5ae5c3cad1eb4346222052fcc792361c64abc7e43bc`.
It produces 1,903 positive-time records and 1,103 deaths. The single excluded
record has zero follow-up, not missing follow-up.

The 2,509-row clinical export stored with the proposal matches the pinned
cBioPortal DataHub patient/sample files on patient IDs, outcome status,
outcome missingness and clinical values. Requiring complete overall-survival
outcomes and positive time produces 1,980 records and 1,144 deaths. The active
pilot therefore omits 77 otherwise eligible records and 41 deaths. ADR-016
requires the pinned cBioPortal source for confirmatory METABRIC.

## 2026-08-14 — Thesis source fails a clean publication build

The Overleaf source fails `latexmk -halt-on-error` at the malformed
Kaplan–Meier equation in `literature_review.tex`. A nonstop diagnostic build
reported hundreds of LaTeX errors and 349 undefined-citation warnings. Static
bibliography inspection found 62 entries, 56 cited keys, missing key `ref8`,
seven unused entries, 38 entries without a stable identifier and malformed
BibTeX entry `ref23`.

The literature review is about 25,700 words, while the introduction,
methodology, results, conclusion, abstract and appendices are template or
effectively empty. Writing and bibliography repair therefore start in Week 1
in parallel with confirmatory engineering.
