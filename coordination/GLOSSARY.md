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
- Used in: `src/models/cox.py`; proportional-hazards comparator and theory.

## Bayesian piecewise-exponential proportional-hazards model
- Symbol: $Y_{im}, E_{im}, \lambda_m, \beta$
- Definition: The project's Bayesian model uses the full right-censored
  piecewise-exponential likelihood, represented as Poisson event counts over
  subject-interval exposures. It is a proportional-hazards model with an
  explicitly estimated piecewise-constant baseline, not a Cox partial-
  likelihood model.
- Formula: $Y_{im} \sim \operatorname{Poisson}\!\left(E_{im}\lambda_m
  \exp(x_i^\top\beta)\right)$
- Used in: `src/models/bayesian/model.py`, methodology and diagnostic appendix.

## Piecewise-exponential baseline hazard
- Symbol: $\lambda_0(t)$
- Definition: The baseline hazard held constant within each of a fixed number
  of intervals partitioning follow-up. Together with the subject-interval
  exposures and event counts, it defines the full likelihood through an exact
  Poisson representation of the piecewise-exponential survival model.
- Formula: $\lambda_0(t) = \lambda_m \text{ for } t \in (c_{m-1}, c_m]$
- Used in: `src/models/bayesian/model.py`.

## Regularised horseshoe prior
- Symbol: $\tau, \lambda_j, c$
- Definition: A global-local shrinkage prior in which a global scale pulls all
  coefficients toward zero while heavy-tailed local scales let genuinely
  non-zero coefficients escape. The slab term $c$ bounds the local-scale tails
  and can improve posterior geometry; only the recorded diagnostics determine
  whether a fitted cell passes the interpretation gate.
- Formula: $\tilde{\lambda}_j^2 = \frac{c^2 \lambda_j^2}{c^2 + \tau^2 \lambda_j^2}, \quad \beta_j \sim \mathcal{N}(0, \tau^2 \tilde{\lambda}_j^2)$
- Used in: `src/models/bayesian/model.py`.

## Continuous spike-and-slab prior
- Symbol: $\gamma_j$
- Definition: A two-component scale mixture in which each coefficient draws
  its variance from a narrow spike or a wide slab according to a continuous
  inclusion weight on $[0, 1]$. The discrete indicator of the classical
  formulation cannot be sampled by NUTS, so the weight is continuous and its
  posterior mean is a prior-specific auxiliary mixing signal, not the
  posterior probability of a discrete inclusion event.
- Formula: $\sigma_j^2=(1-\gamma_j)\sigma_0^2+\gamma_j\sigma_1^2$,
  $\beta_j\sim\mathcal{N}(0,\sigma_j^2)$, where the second Normal parameter is
  the variance.
- Used in: `src/models/bayesian/model.py`.

## Prior-specific auxiliary signal
- Symbol: $\mathbb{E}[\gamma_j]$, $\kappa^{\mathrm{proxy}}_j$
- Definition: For continuous spike-and-slab, the auxiliary signal is the
  posterior mean continuous mixing weight. For the regularised horseshoe,
  $1/(1+\lambda_j^2)$ is stored only as a local-scale shrinkage proxy: it omits
  the global scale and regularising slab and is neither the full shrinkage
  factor nor an inclusion probability. These signals are secondary; the
  primary intrinsic importance is the full-posterior expected absolute grouped
  contribution.
- Formula: $\kappa^{\mathrm{proxy}}_j=1/(1+\lambda_j^2)$
- Used in: `src/models/bayesian/model.py`, `src/explainability/frozen_cells.py`.

## R-hat
- Symbol: $\hat{R}$
- Definition: The Gelman-Rubin statistic comparing between-chain and
  within-chain variance. A maximum rank-normalised value below 1.01 passes this
  prespecified diagnostic component; it is not by itself proof of convergence.
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

## Exact interventional linear SHAP value
- Symbol: $\phi_j$
- Definition: The feature attribution for a frozen linear risk score relative
  to the mean of its supplied outer-training background. The confirmatory
  implementation uses `shap.LinearExplainer` and verifies its output against
  the analytic identity; it does not fit or refit a model. Encoded-term values
  are summed by source-variable group before mean absolute importance is
  computed. The same-Bayesian-model comparison is primary and frozen Cox is
  secondary; forest and DeepSurv explanations are not confirmatory targets.
- Formula: $\phi_j(x)=\beta_j\left(x_j-\mathbb{E}_{B}[X_j]\right)$
- Used in: `src/explainability/shap_analysis.py`,
  `src/explainability/frozen_cells.py`.
