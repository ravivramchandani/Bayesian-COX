# Methodology

This file describes the implemented exploratory models. The confirmatory
analysis replaces the current validation/evaluation path according to
`docs/study_protocol.md`; until those tasks pass, statements below are model
specifications rather than publication-quality validation claims.

## Cox proportional hazards

The hazard for subject $i$ at time $t$:

$$\lambda(t \mid X_i) = \lambda_0(t) \exp(\beta^\top X_i)$$

$\lambda_0(t)$ is the unspecified baseline hazard and $\beta$ the log hazard
ratios. The model is fitted with lifelines. Schoenfeld-residual checks are
specified but are not yet wired into the benchmark output; T-143 completes
and reports them under a frozen response rule.

## Random survival forest

An ensemble of survival trees split on the log-rank statistic, aggregating
cumulative hazard functions across trees. Fitted with scikit-survival.
Feature importance is measured by the drop in concordance when a feature is
permuted.

## Bayesian Cox

Follow-up is partitioned into $M$ intervals with a constant baseline hazard
in each. The Cox likelihood then becomes a Poisson regression over
subject-interval exposures:

$$y_{im} \sim \text{Poisson}(\mu_{im}), \qquad
\log \mu_{im} = \log e_{im} + \log \lambda_m + \beta^\top X_i$$

where $e_{im}$ is the exposure of subject $i$ in interval $m$ and $y_{im}$
indicates an event there. Baseline log-hazards take a
$\mathcal{N}(-2, 2^2)$ prior.

### Coefficient priors

**Weakly-informative Normal.** $\beta_j \sim \mathcal{N}(0, 1)$. The
reference case, carrying no sparsity assumption.

**Regularised horseshoe.** Global-local shrinkage in non-centred form, with a
slab bounding the local scales:

$$\tilde{\lambda}_j^2 = \frac{c^2\lambda_j^2}{c^2 + \tau^2\lambda_j^2},
\qquad \beta_j = z_j\,\tau\,\tilde{\lambda}_j$$

with $\tau \sim \text{HalfStudentT}(2, \tau_0)$,
$\lambda_j \sim \text{HalfStudentT}(2, 1)$,
$c^2 \sim \text{InvGamma}(\nu/2, \nu s^2/2)$ and
$z_j \sim \mathcal{N}(0,1)$. The unregularised form funnels badly under NUTS;
the slab removes the divergences.

**Continuous spike-and-slab.** A discrete inclusion indicator cannot be
sampled by NUTS, so the indicator is relaxed to a continuous weight
$\gamma_j \sim \text{Beta}(1,1)$ mixing a narrow spike with a wide slab:

$$\beta_j \sim \mathcal{N}\!\left(0,\;(1-\gamma_j)\sigma_0^2 + \gamma_j\sigma_1^2\right)$$

with $\sigma_0 = 0.05$ and $\sigma_1 = 2$. The posterior mean of $\gamma_j$
is the inclusion signal.

### Inference and diagnostics

NUTS, four chains, 2000 tuning and 2000 posterior draws, target acceptance
0.95 (0.99 for the horseshoe). The pilot reports R-hat, effective sample size
and divergent transitions computed from the trace with arviz, but its gate is
centred on `beta`. Confirmatory fits extend diagnostics to baseline hazards
and all prior hyperparameters, plus MCSE, BFMI, tree-depth and prior/posterior
predictive checks. The minimum gate is R-hat below 1.01 and bulk effective
sample size above 400; the confirmatory divergence target is zero.

## Confirmatory evaluation

- **IPCW integrated Brier score** — primary overall probabilistic prediction
  error over a supported follow-up window; it reflects both discrimination
  and calibration.
- **Uno's IPCW concordance index** — primary censoring-robust discrimination
  estimate. Harrell's concordance remains descriptive.
- **Cumulative/dynamic AUC** — discrimination as a function of time.
- **Calibration curves, intercept/calibration-in-the-large and slope** —
  explicit calibration at prespecified horizons.

Every evaluation window/horizon is chosen from the outer-training fold and
restricted to estimable censoring support; test outcomes never select it. The
pilot currently violates this rule and is exploratory. Reference metrics come
from scikit-survival, with calibration estimators independently tested.

## Confirmatory explainability

The common primary Bayesian importance is posterior expected absolute
contribution over validation subjects and posterior draws. Probability of
direction is a certainty measure; horseshoe shrinkage and the continuous
spike-and-slab mixing weight are secondary, prior-specific signals.

Primary agreement compares intrinsic importance with SHAP on the same
Bayesian posterior-mean risk model. Cox PH and random-survival-forest SHAP are
secondary cross-model comparisons. Subjects and backgrounds are sampled
within folds with recorded seeds, encoded/transformed terms are grouped by
source variable, and agreement/stability is reported with resampling
uncertainty. The analysis estimates model-conditional ranking agreement, not
causality, feature truth or clinical usefulness.
