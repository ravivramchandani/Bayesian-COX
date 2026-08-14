# GLOSSARY

Single source of truth for formal terms. Code docstrings and thesis chapters
reference these entries; they do not redefine them.

Format:

```markdown
## <Term> [<acronym>]
- Symbol: <math or code symbol, or "—">
- Definition: <one or two sentences>
- Formula: <LaTeX, or "—">
- Used in: <files or chapters>
```

---

## Concordance index [C-index]
- Symbol: $C$
- Definition: The proportion of comparable subject pairs whose predicted risk
  ordering matches their observed survival ordering. A pair is comparable when
  the earlier time is an observed event. 0.5 is chance.
- Formula: $C = \frac{\sum_{i,j} \mathbb{1}[t_i < t_j] \cdot \mathbb{1}[r_i > r_j] \cdot \delta_i}{\sum_{i,j} \mathbb{1}[t_i < t_j] \cdot \delta_i}$
- Used in: `src/evaluation/metrics.py`, results chapter.

## Integrated Brier score [IBS]
- Symbol: $\mathrm{IBS}$
- Definition: The squared error between predicted survival probability and
  observed status, weighted for censoring and averaged over an evaluation
  window. Lower is better. It is a proper overall prediction-error measure
  affected by both calibration and discrimination, so it does not establish
  calibration by itself.
- Formula: $\mathrm{IBS} = \frac{1}{t_{\max}} \int_0^{t_{\max}} \mathrm{BS}(t)\,dt$
- Used in: `src/evaluation/metrics.py`, results chapter.

## Uno concordance index [Uno's C]
- Symbol: $C_{\mathrm{Uno}}$
- Definition: An inverse-probability-of-censoring-weighted concordance
  estimator evaluated up to a supported horizon. It is less sensitive than
  Harrell's concordance estimator to bias under heavy censoring.
- Formula: —
- Used in: confirmatory evaluation, results chapter.

## Calibration intercept and slope
- Symbol: $\alpha_{\mathrm{cal}}, \beta_{\mathrm{cal}}$
- Definition: Calibration-in-the-large/intercept measures systematic
  underprediction or overprediction at a horizon; calibration slope measures
  whether predictions are too extreme or too compressed. Their estimator and
  ideal values must be stated for the chosen survival-calibration model.
- Formula: —
- Used in: `src/evaluation/calibration.py`, confirmatory results chapter.

## Time-dependent AUC
- Symbol: $\mathrm{AUC}(t)$
- Definition: The area under the ROC curve for discriminating subjects who
  have experienced the event by time $t$ from those who have not, with
  inverse-probability-of-censoring weights.
- Formula: —
- Used in: `src/evaluation/metrics.py`, results chapter.

## Censoring
- Symbol: $\delta$
- Definition: A subject is censored when the event has not been observed by
  the end of follow-up. $\delta = 1$ marks an observed event and $\delta = 0$
  a censored observation.
- Formula: —
- Used in: all data and model modules.

## Cox proportional hazards model
- Symbol: $\lambda(t \mid x)$
- Definition: A semi-parametric model in which covariates act multiplicatively
  on an unspecified baseline hazard, so hazard ratios are constant over time.
- Formula: $\lambda(t \mid x) = \lambda_0(t) \exp(x^\top \beta)$
- Used in: `src/models/cox.py`, `src/models/bayesian/model.py`.

## Piecewise-exponential baseline hazard
- Symbol: $\lambda_0(t)$
- Definition: The baseline hazard held constant within each of a fixed number
  of intervals partitioning follow-up. It makes the Cox likelihood tractable
  as a Poisson regression over subject-interval exposures.
- Formula: $\lambda_0(t) = \lambda_m \text{ for } t \in (c_{m-1}, c_m]$
- Used in: `src/models/bayesian/model.py`.

## Regularised horseshoe prior
- Symbol: $\tau, \lambda_j, c$
- Definition: A global-local shrinkage prior in which a global scale pulls all
  coefficients toward zero while heavy-tailed local scales let genuinely
  non-zero coefficients escape. The slab term $c$ bounds the local scales and
  removes the funnel geometry that causes divergent transitions.
- Formula: $\tilde{\lambda}_j^2 = \frac{c^2 \lambda_j^2}{c^2 + \tau^2 \lambda_j^2}, \quad \beta_j \sim \mathcal{N}(0, \tau^2 \tilde{\lambda}_j^2)$
- Used in: `src/models/bayesian/model.py`.

## Continuous spike-and-slab prior
- Symbol: $\gamma_j$
- Definition: A two-component scale mixture in which each coefficient draws
  its variance from a narrow spike or a wide slab according to a continuous
  inclusion weight on $[0, 1]$. The discrete indicator of the classical
  formulation cannot be sampled by NUTS, so the weight is continuous and its
  posterior mean serves as the inclusion signal.
- Formula: $\beta_j \sim \mathcal{N}\!\left(0, (1-\gamma_j)\sigma_0^2 + \gamma_j \sigma_1^2\right)$
- Used in: `src/models/bayesian/model.py`.

## Inclusion signal
- Symbol: $\mathbb{E}[\gamma_j]$
- Definition: The built-in explainability output of a sparsity prior. For the
  spike-and-slab it is the posterior mean inclusion weight; for the horseshoe
  it is the shrinkage factor $1/(1+\lambda_j^2)$, where values near zero mark
  coefficients that escaped shrinkage.
- Formula: —
- Used in: `src/models/bayesian/model.py`, `src/explainability/`.

## R-hat
- Symbol: $\hat{R}$
- Definition: The Gelman-Rubin statistic comparing between-chain and
  within-chain variance. Values below 1.01 indicate chains have mixed.
- Formula: —
- Used in: `src/models/bayesian/diagnostics.py`.

## Effective sample size [ESS]
- Symbol: $S_{\mathrm{eff}}$
- Definition: The number of independent draws that would carry the same
  information as the autocorrelated posterior sample.
- Formula: —
- Used in: `src/models/bayesian/diagnostics.py`.

## Divergent transition
- Symbol: —
- Definition: A Hamiltonian trajectory in NUTS whose energy error exceeds
  tolerance, indicating the sampler failed to follow the posterior geometry.
  A sustained rate signals biased inference.
- Formula: —
- Used in: `src/models/bayesian/diagnostics.py`.

## SHAP value
- Symbol: $\phi_j$
- Definition: The Shapley attribution of a single prediction to feature $j$,
  averaged over feature orderings. Post-hoc and model-agnostic; here computed
  over each model's risk prediction so attributions are comparable across
  models.
- Formula: —
- Used in: `src/explainability/shap_analysis.py`.
