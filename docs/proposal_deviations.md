# Deviations from the approved proposal

The proposal was approved with suggestions in May 2026. The implemented work
differs from it in the following ways. Each is recorded as a decision in
`coordination/DECISIONS.md`; whether the proposal document itself is revised
is an open question for the supervisors.

## Cohorts

**Proposal:** METABRIC, a Kaggle heart-attack dataset, and a lung-cancer
extract.

**Implemented:** METABRIC, WHAS500, GBSG2.

The heart-attack file contains `age, sex, cp, trtbps, chol, fbs, restecg,
thalachh, exng, oldpeak, slp, caa, thall, output`. `output` is a binary
label and there is no event time, so the file cannot support survival
analysis at all. The lung-cancer extract holds 80 rows, with a duration only
derivable as the gap between diagnosis and end-of-treatment dates.

WHAS500 supplies the cardiology cohort the heart-attack file was meant to
cover, with genuine time-to-event data. GBSG2 supplies a properly powered
second cohort. Both ship with scikit-survival and have published baselines,
which makes the pipeline checkable against external reference points. This
follows the co-supervisor's May 2026 guidance and addresses the panel's
concern that the datasets were not verified to contain survival data.

## Priors

**Proposal:** a Bayesian Cox model, priors unspecified.

**Implemented:** three coefficient priors — weakly-informative Normal,
regularised horseshoe, and a continuous relaxation of spike-and-slab.

The panel noted that prior distributions were unspecified. The three-prior
scheme comes from the co-supervisor's May 2026 guidance, where the posterior
of a sparsity prior serves as the explainability signal. A discrete
spike-and-slab indicator cannot be sampled by NUTS, so the continuous
relaxation is used and the posterior mean of the inclusion weight is
reported.

## Inference

**Proposal:** MCMC, sampler unnamed, no diagnostics stated.

**Implemented:** PyMC with NUTS, reporting R-hat, bulk and tail effective
sample size, and divergent transitions for every fit.

This addresses the panel's observation that the sampler was unnamed and
convergence diagnostics absent.

## Metrics

**Proposal:** C-index, Brier score, integrated Brier score, time-dependent
AUC, calibration curves.

**Implemented:** all of the above except calibration curves, which are
implemented in `src/evaluation/calibration.py` but not yet in the benchmark
output.

## Deep learning

**Proposal:** DeepHit discussed in the literature review; DeepSurv added
later as the deep-learning arm.

**Implemented:** DeepSurv exists in `src/models/deepsurv.py` but is not in
the benchmark. Whether the deep-learning arm is DeepSurv or DeepHit depends
on whether competing risks are in scope, which is unresolved.

## Explainability

**Proposal:** explainability asserted but not operationalised, which the
panel flagged.

**Implemented:** the built-in posterior signal is compared against post-hoc
SHAP on both baselines, with agreement measured by rank correlation and
top-k overlap.
