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

## 2026-08-14 — Censoring weights require a bounded test horizon

Time-dependent AUC and the integrated Brier score estimate censoring weights
from the training follow-up, so every test event time must fall inside it.
METABRIC and WHAS500 both contain test observations past their training
horizon, which raised rather than returning a value. Test observations beyond
the horizon are now administratively censored at it before the weighted
metrics are computed; concordance still uses the untruncated data. GBSG2 and
WHAS500 results are unchanged by this, since it only affects the case that
previously failed.

## 2026-08-14 — Built-in and post-hoc explainability diverge by baseline

On GBSG2 the posterior ranking agrees closely with SHAP computed on Cox PH
(Spearman 0.60 to 0.97 depending on prior, top-5 overlap 3 to 4 of 5) and
shows almost no agreement with SHAP computed on the random survival forest
(Spearman -0.20 to +0.05). Both the Bayesian model and Cox PH are linear in
the log hazard, so the divergence is expected and separates attribution that
reflects the model family from attribution that reflects the data.
