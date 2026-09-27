# Penalized Cox normalization and diagonal horseshoe calibration

External methods audit, 2026-09-28. No shared repository access or changes; no model fits or empirical results. This note supplements `frozen_addendum_methods.md`.

## Version verified

The supplied interpreter `/Users/macuser/miniconda3/envs/bayes-cox-lock-verify-20260815-b/bin/python` reports both distribution metadata and `sksurv.__version__` as **0.28.0**, not 0.27.0. Its installed `coxph.py` and `coxnet.py` are byte-identical to the official v0.28.0 files. Public v0.27.0 and v0.28.0 `src/coxnet/coxnet.h` files are byte-identical. No environment was modified. Freeze the actual verified version or explicitly restore/reverify the intended lock before computing results.

The public-source v0.27.0 files retained in `scikit_survival_v027_sources/` have SHA256:

- `coxph.py`: `285cd50cfd53acdafd1efd3c6c21ac69c4d7d30fda1368f0b203290877b747c0`
- `coxnet.py`: `4602289844bdec171a33e4569b19ab3fa004def903681b32e287fbdbb56c55f4`
- `coxnet.h`: `f01469a3157c52cd282cd0e4e0c2360f567f90db5d4144d0b69a314d4ffbf19c`

## Objective and conversion

Let n be the number of subjects in the **current fit**, and let ell_B(beta) be the total Breslow log partial likelihood. Define the common ridge target as

`-ell_B(beta)/n + lambda * sum(beta_j^2)/2`.

`CoxPHSurvivalAnalysis` minimizes `-ell(beta)/n + alpha * sum(beta_j^2)/(2*n)`. Consequently set **`alpha = n_fit * lambda`**, including each inner-training fit. n counts subjects, not events. Source: [v0.27.0 CoxPHOptimizer.nlog_likelihood, lines 168–214](https://github.com/sebp/scikit-survival/blob/v0.27.0/sksurv/linear_model/coxph.py#L168), with the penalty gradient/Hessian at lines 289–293. The installed v0.28.0 implementation retains this expression: [official v0.28.0 source](https://github.com/sebp/scikit-survival/blob/v0.28.0/sksurv/linear_model/coxph.py#L168).

With default equal penalty factors, `CoxnetSurvivalAnalysis` minimizes

`-ell_B(beta)/n + alpha * [rho * sum(abs(beta_j)) + (1-rho) * sum(beta_j^2)/2]`.

Therefore set **`alphas=[lambda]`**, with `l1_ratio=rho`; rho=1 is lasso. Coxnet disallows rho=0, so use CoxPH for pure ridge. This normalization follows the C++ likelihood/residual factor `1/n`, penalties `alpha*rho` and `alpha*(1-rho)`, and coordinate soft threshold/denominator: [v0.27.0 Coxnet source, lines 93–109, 125–175, 236–237, 305–307](https://github.com/sebp/scikit-survival/blob/v0.27.0/sksurv/linear_model/src/coxnet/coxnet.h#L93). Dividing risk-set sums by n only adds a beta-independent likelihood constant. Custom `penalty_factor` changes this objective and is rescaled to sum p by the Python wrapper; freeze default ones for the stated mapping.

This source normalization is more precise than interpreting the user-guide symbolic `log PL` formulas as the same unnormalized likelihood in both estimators. The original Coxnet paper explicitly explains the 1/n weighting and Breslow ties in [Simon et al. (2011), section 2.5, equation 8](https://pmc.ncbi.nlm.nih.gov/articles/PMC4824408/#S8).

Set `ties="breslow"` for CoxPH to align its coefficient objective with Coxnet, which exposes no Efron option. CoxPH also permits Efron, which produces a different tied-event objective. Coxnet internally centers columns; set `normalize=False` with training-standardized numeric columns and unscaled categorical dummies. Centering does not change partial-likelihood coefficients; the wrapper stores an offset used by prediction. `fit_baseline_model=True` enables its Breslow absolute survival predictions. See [v0.27.0 CoxPH documentation/source](https://github.com/sebp/scikit-survival/blob/v0.27.0/sksurv/linear_model/coxph.py#L339) and [Coxnet preprocessing and prediction setup](https://github.com/sebp/scikit-survival/blob/v0.27.0/sksurv/linear_model/coxnet.py#L202).

One-element `alphas` is supported: the [official v0.27.0 guide, Choosing penalty strength](https://scikit-survival.readthedocs.io/en/v0.27.0/user_guide/coxnet.html#choosing-penalty-strength-alpha) passes `[[v] ...]` to GridSearchCV and refits one selected alpha. It does not inherently cause a convergence warning. A single alpha starts without the preceding path's warm-start solutions. Capture actual `ConvergenceWarning` messages: Coxnet emits one when `n_iter >= max_iter` yet returns coefficients; CoxPH similarly returns coefficients after its iteration-limit warning. Such candidates require the frozen retry/failure policy and must not silently count as converged. An all-zero-coefficient Coxnet `UserWarning` is separate and can represent a legitimate null model. [Coxnet fit warning logic, lines 300–310](https://github.com/sebp/scikit-survival/blob/v0.27.0/sksurv/linear_model/coxnet.py#L300); [CoxPH iteration-limit logic, lines 480–489](https://github.com/sebp/scikit-survival/blob/v0.27.0/sksurv/linear_model/coxph.py#L480).

## Diagonal profiled PWE curvature: valid computational approximation

This is a training-only adaptation of Piironen–Vehtari local quadratic calibration, not a published survival-specific formula. Their [regularized horseshoe paper](https://arxiv.org/html/1707.01694) gives the slab in section 2.3/equation 2.8, effective-dimension calibration in section 3.3/equations 3.7–3.12, and non-Gaussian curvature discussion in sections 3.5–3.6/equations 3.14–3.15. Section 3.4 explains the finite slab's effect on complexity.

Use median-training-event-time-scaled PWE exposures E_ik, standardized numeric columns and unscaled 0/1 dummy columns x_i, without a beta intercept. At beta=0, the baseline-only posterior mode for independent theta_k ~ Normal(-2,2) satisfies

`d_k - a_k * exp(theta_k) - (theta_k+2)/4 = 0`, where `a_k=sum_i E_ik`.

Define `mu_ik=E_ik*exp(theta_k)`, `m_i=sum_k mu_ik`, `b_k=sum_i mu_ik`, and `q_kj=sum_i mu_ik*x_ij`. The joint negative-log-posterior Hessian's baseline block has diagonal `b_k+1/4`; profiling nuisance baselines gives

`I_eff = A - C * diag(1/(b_k+1/4)) * C^T`,

where `A=sum_i m_i*x_i*x_i^T` and `C[:,k]=q_k`.

Its diagonal can be computed without constructing the p-by-p A matrix:

`h_j = sum_i m_i*x_ij^2 - sum_k q_kj^2/(b_k+1/4)`.

The +1/4 is the actual baseline-prior precision; call this **prior-adjusted profiled local information**, not pure likelihood information. Use the **total** log likelihood Hessian; dividing it by n would change the prior scale. It is positive semidefinite mathematically. Only roundoff-sized negative h_j may be clipped; meaningful negatives indicate an implementation error. Zero-information columns contribute zero. Training-only zero/duplicate design handling and p must be recorded.

For original horseshoe local scales `lambda_j ~ HalfCauchy(1)`, at fixed tau,

`kappa_j = 1/(1+h_j*tau^2*lambda_j^2)`

and direct half-Cauchy integration gives exactly, **under the diagonal quadratic approximation**,

`E_lambda[1-kappa_j] = tau*sqrt(h_j)/(1+tau*sqrt(h_j))`.

Calibrate tau0 by a monotone scalar root:

`sum_j tau0*sqrt(h_j)/(1+tau0*sqrt(h_j)) = p0`,

with frozen `p0=5` for p>5, otherwise `p0=p/2`, and p=0 handled as a baseline-only model. These p0 values express a post-hoc sparsity assumption; they are not estimated relevance counts or defaults established by the cited paper. Use a log-tau root with a deterministic bracket. A finite root exists only if `0 < p0 < count(h_j>0)`; flag unattainable calibration rather than substitute an undocumented scale.

Dropping off-diagonal curvature can overcount information in correlated or duplicate predictors. This diagonal result is an explicitly declared computational approximation to the full eigenvalue/trace calculation in the companion note. Positive diagonal entries do not establish full rank or p independent estimable directions.

Freeze slab `c=2` on the log-hazard-ratio coefficient scale and hyperprior `tau ~ HalfCauchy(tau0)`. c=2 is a broad finite slab (a limiting N(0,4) has a central 95% HR interval about 0.02–50.4), selected as a regularization bound, not a clinical effect prior. Numeric coefficients apply per training SD, while dummy coefficients apply to the category contrast. The root calibrates the **underlying unregularized horseshoe at fixed tau=tau0**, not the hyperprior-marginal or regularized effective dimension.

For the slab variance `v_j=tau^2*c^2*lambda_j^2/(c^2+tau^2*lambda_j^2)`, the diagonal regularized complexity also has an analytic expectation:

`E_lambda[h_j*v_j/(1+h_j*v_j)] = [h_j/(h_j+c^(-2))] * [tau*sqrt(h_j+c^(-2))/(1+tau*sqrt(h_j+c^(-2)))]`.

This follows by writing the integrand as `[h_j/(h_j+c^(-2))] * [a^2*lambda_j^2/(1+a^2*lambda_j^2)]`, with `a=tau*sqrt(h_j+c^(-2))`. Report its sum at tau0 as the finite-slab reduction; do not claim the actual regularized prior has expected dimension exactly p0. Neither these curvature summaries nor log-density checks replace valid prior draws for prior-predictive checks.
