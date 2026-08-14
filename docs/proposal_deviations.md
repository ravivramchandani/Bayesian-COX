# Deviations from the proposal

The implemented work differs from the original proposal in the following
ways. Each is a technical decision recorded in `coordination/DECISIONS.md`,
and each is justified in the methodology chapter where a reader meets it.

## Cohorts

**Proposal:** METABRIC, a heart-attack dataset, and a lung-cancer extract.

**Implemented:** METABRIC, WHAS500, GBSG2.

The heart-attack file contains `age, sex, cp, trtbps, chol, fbs, restecg,
thalachh, exng, oldpeak, slp, caa, thall, output`. `output` is a binary label
and there is no event time, so the file cannot support survival analysis. The
lung-cancer extract holds 80 rows, with a duration only derivable as the gap
between diagnosis and end-of-treatment dates.

WHAS500 supplies the cardiology cohort with genuine time-to-event data, and
GBSG2 a properly powered second cohort. Both ship with scikit-survival and
carry published baselines, which lets the pipeline be checked against
external reference points — the check that catches a broken pipeline before
any result is interpreted.

## Priors

**Proposal:** a Bayesian Cox model, priors unspecified.

**Implemented:** weakly-informative Normal, regularised horseshoe, and a
continuous relaxation of spike-and-slab.

The posterior of a sparsity prior is the explainability signal this work
measures, so a baseline prior plus two sparsity priors is the minimum that
makes the comparison meaningful. A discrete spike-and-slab indicator cannot
be sampled by NUTS, so the indicator is relaxed to a continuous inclusion
weight whose posterior mean is reported.

## Inference

**Proposal:** MCMC, sampler unnamed, no diagnostics stated.

**Implemented:** PyMC with NUTS, reporting R-hat, bulk and tail effective
sample size, and divergent transitions for every fit.

## Metrics

**Proposal:** C-index, Brier score, integrated Brier score, time-dependent
AUC, calibration curves.

**Implemented:** all except calibration curves, which exist in
`src/evaluation/calibration.py` but are not yet in the benchmark output.

## Deep learning

**Proposal:** DeepHit in the literature review.

**Implemented:** DeepSurv is the deep-learning arm. All three cohorts record
a single event type, so there are no competing risks for DeepHit to model,
and DeepSurv shares the proportional-hazards structure of the other arms.

## Explainability

**Proposal:** explainability asserted but not operationalised.

**Implemented:** the built-in posterior signal is compared against post-hoc
SHAP on both baselines, with agreement measured by rank correlation and
top-k overlap.
