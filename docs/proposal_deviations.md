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
GBSG2 supplies a second time-to-event cohort with 686 records and 299 observed
events. No prospective power claim is made. Both ship with scikit-survival and
carry published baselines, which lets the pipeline be checked against external
reference points — the check that catches a broken pipeline before any result
is interpreted.

## Priors

**Proposal:** a Bayesian Cox model, priors unspecified.

**Implemented:** a piecewise-exponential proportional-hazards full-likelihood
model, rather than an exact Bayesian Cox partial-likelihood model, with
weakly-informative Normal, regularised horseshoe, and continuous
spike-and-slab coefficient priors.

The common explanation quantity is the posterior expected absolute grouped
linear-predictor contribution. Prior-specific posterior quantities are
secondary: the spike-and-slab relaxation supplies a continuous mixture weight,
and the horseshoe supplies an explicitly labelled local-scale proxy. Neither is
presented as a ground-truth inclusion probability or as the common comparison
measure. A discrete spike-and-slab indicator is not used because the frozen
sampler is NUTS; the implemented continuous weight mixes the spike and slab
variances.

## Inference

**Proposal:** MCMC, sampler unnamed, no diagnostics stated.

**Implemented:** PyMC with NUTS. The admissibility gate covers every sampled
variable and checks rank-normalised R-hat, bulk and tail effective sample size,
Monte Carlo standard error, divergent transitions, energy/BFMI, tree depth,
and prior/posterior predictive records. A failed fit remains in the result
inventory and cannot contribute predictions or coefficient interpretations.

## Metrics

**Proposal:** C-index, Brier score, integrated Brier score, time-dependent
AUC, calibration curves.

**Implemented for the frozen confirmatory pipeline:** IPCW integrated Brier
score, Harrell and Uno concordance, cumulative/dynamic AUC, and explicit
calibration curves plus calibration-in-the-large/intercept and slope at
training-derived horizons. The historical benchmark remains exploratory; no
confirmatory numerical result is claimed until the production run completes.

## Deep learning

**Proposal:** DeepHit in the literature review.

**Implemented:** DeepSurv is the deep-learning arm. All three cohorts record
a single event type, so there are no competing risks for DeepHit to model,
and DeepSurv shares the proportional-hazards structure of the other arms.

## Explainability

**Proposal:** explainability asserted but not operationalised.

**Implemented for frozen-cell analysis:** full-posterior grouped contribution
is compared with exact interventional linear SHAP on the same Bayesian
posterior-mean risk score, using identical validation subjects and recorded
training backgrounds. Exact Cox linear SHAP is the sole secondary cross-model
comparison. Random-survival-forest SHAP was formally dropped because the
confirmatory cell does not retain forest state; DeepSurv attribution is outside
scope. Agreement and sampling stability use prespecified rank, overlap, budget,
seed, completeness, and uncertainty gates. These are model-agreement measures,
not causal or clinical-utility evidence.
