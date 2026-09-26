# Methodology

This file is a compact implementation synopsis. The prespecified design and
claim rules live in `docs/study_protocol.md`; the thesis gives the complete
mathematical account. Infrastructure described here is implemented and tested,
but numerical findings remain unavailable until the content-addressed
confirmatory, robustness, and frozen-cell explanation runs complete.

## Cox proportional hazards

The hazard for subject $i$ at time $t$:

$$\lambda(t \mid X_i) = \lambda_0(t) \exp(\beta^\top X_i)$$

$\lambda_0(t)$ is the unspecified baseline hazard and $\beta$ the log hazard
ratios. The model is fitted with lifelines. Each frozen Cox cell stores
Schoenfeld-residual tests with Holm adjustment within that fit. Supported
violations are reported as design limitations; they do not trigger an
outcome-driven time interaction or change the primary model.

## Random survival forest

An ensemble of survival trees split on the log-rank statistic, aggregating
cumulative hazard functions across trees. It is fitted with scikit-survival,
with its compact grid selected by inner-fold IPCW integrated Brier score.
Random-forest feature attribution is not part of the confirmatory explanation
claim because the immutable prediction cells do not retain forest state.

## Bayesian piecewise-exponential proportional hazards

Follow-up is partitioned into $M$ intervals with a constant baseline hazard
in each. This specifies a full event-time likelihood with a
proportional-hazards linear predictor; it is not the Cox partial likelihood.
After splitting each subject's follow-up into interval-specific exposures, the
piecewise-exponential likelihood has the following Poisson representation:

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
$z_j \sim \mathcal{N}(0,1)$. The slab bounds the local-scale tails and can
improve NUTS geometry; only the prespecified fit diagnostics determine whether
a particular posterior sample is admissible.

**Continuous spike-and-slab.** A discrete inclusion indicator cannot be
sampled by NUTS, so the indicator is relaxed to a continuous weight
$\gamma_j \sim \text{Beta}(1,1)$ mixing a narrow spike with a wide slab:

$$\sigma_j^2=(1-\gamma_j)\sigma_0^2 + \gamma_j\sigma_1^2,
\qquad \beta_j \sim \mathcal{N}(0,\sigma_j^2)$$

with $\sigma_0 = 0.05$ and $\sigma_1 = 2$. The posterior mean of $\gamma_j$
is the inclusion signal.

### Inference and diagnostics

The frozen production specification uses NUTS, four chains, 2,000 tuning and
2,000 retained draws, and target acceptance 0.95 (0.99 for the horseshoe). The
gate covers coefficients, baseline hazards, and every prior hyperparameter,
plus rank-normalised R-hat, bulk/tail ESS, MCSE, BFMI, tree depth, zero
divergences, and prior/posterior predictive records. The minimum common gates
include R-hat below 1.01 and bulk ESS above 400. At most two prespecified
remedies change sampler geometry but not the inferential model; a final failure
is retained and excluded from complete-case inference.

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

Primary Bayesian-prior IBS contrasts use paired Nadeau–Bengio estimates with
nominal 95% intervals. Holm adjustment is applied to the nine primary
p-values, not to those intervals; superiority wording requires both a
Holm-adjusted p-value at most 0.05 and a nominal interval excluding zero.

The METABRIC stage sensitivity fits five fold-local imputation-specific
models. It averages their risk scores and survival probabilities and then
recomputes pooled metrics from those averaged predictions; per-imputation
metrics and diagnostics are archived separately. This prediction ensemble is
not one Bayesian posterior and does not propagate covariate-imputation
uncertainty as posterior uncertainty.

RQ2 uses outer folds 1 and 2 in every repeat retained after the result-blind
compute gate. Non-primary design and feature conditions, including the
five-imputation condition, use outer fold 1 in every retained repeat and are
paired with the corresponding fold-1 primary condition.

## Confirmatory explainability

The common primary Bayesian importance is posterior expected absolute
contribution over validation subjects and posterior draws. Probability of
direction is a certainty measure; horseshoe shrinkage and the continuous
spike-and-slab mixing weight are secondary, prior-specific signals.

Primary agreement compares intrinsic importance with exact interventional
linear SHAP on the same Bayesian posterior-mean risk model. Exact Cox linear
SHAP is the only secondary cross-model comparison; forest state is not retained
and DeepSurv attribution is outside scope. Subjects and training backgrounds
are sampled in paired, nested budgets within outer folds using recorded seeds,
and encoded terms are grouped by source variable. H3 claims require complete
planned-cell inventories, sampling-stability gates, and three-stage
repeat/fold/seed uncertainty intervals. The analysis estimates
model-conditional ranking agreement, not causality, feature truth, or clinical
usefulness.
