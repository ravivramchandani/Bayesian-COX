# Methodology

## Cox proportional hazards

The hazard for subject $i$ at time $t$:

$$\lambda(t \mid X_i) = \lambda_0(t) \exp(\beta^\top X_i)$$

$\lambda_0(t)$ is the unspecified baseline hazard and $\beta$ the log hazard
ratios. Fitted with lifelines; the proportional-hazards assumption is checked
with Schoenfeld residuals.

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
0.95 (0.99 for the horseshoe). Every fit reports R-hat, bulk and tail
effective sample size, and divergent transitions, computed from the trace
with arviz. A fit counts as converged when R-hat is below 1.01, bulk
effective sample size exceeds 400, and divergences are under 0.5% of draws.

## Evaluation

- **Concordance index** — discrimination.
- **Integrated Brier score** — calibration over the follow-up window, with
  inverse-probability-of-censoring weights.
- **Time-dependent AUC** — discrimination as a function of time.

Evaluation times are quantiles of the observed event times, clipped inside
both the training and test follow-up so censoring weights remain estimable.
All three metrics come from scikit-survival.

## Explainability

The Bayesian posterior supplies a built-in signal: the probability that a
coefficient's effect has a consistent direction, plus the inclusion signal
from each sparsity prior. This is compared against post-hoc SHAP computed on
Cox PH and the random survival forest, using a kernel explainer over each
model's risk prediction so the attribution method is constant across models.
Agreement is reported as Spearman and Kendall rank correlation and top-k
overlap.
