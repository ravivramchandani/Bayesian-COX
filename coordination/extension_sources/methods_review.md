# Methods choices for a frozen post-hoc addendum

Prepared 2026-09-28 from primary public sources only. No project repository was read or edited and no model was fitted. The formulas below distinguish published constructions from the proposed survival-model adaptations. Freeze these choices before new comparator results are inspected. Preserve the existing benchmark as the primary analysis and label this extension post-hoc.

## Regularized horseshoe

Primary source: Piironen and Vehtari (2017), *Sparsity information and regularization in the horseshoe and other shrinkage priors*, Electronic Journal of Statistics 11:5018-5051, DOI https://doi.org/10.1214/17-EJS1337SI. Authors' full text: https://arxiv.org/html/1707.01694 . Relevant pointers: Section 2.3 Eq. (2.8) for the finite slab; Section 3.3 Eqs. (3.7)-(3.12) for effective complexity and calibration; Section 3.5 Eqs. (3.14)-(3.15) and Table 1 for non-Gaussian likelihood curvature; Section 3.6 cautions against directly transplanting the Gaussian formula into more complex models.

Use the non-centered prior

    z_j ~ Normal(0,1), lambda_j ~ HalfCauchy(1), tau ~ HalfCauchy(tau0)
    v_j = tau^2 * c^2 * lambda_j^2 / (c^2 + tau^2 * lambda_j^2)
    beta_j = sqrt(v_j) * z_j.

Recommended frozen choices: c=2 on the log-hazard-ratio scale; p0=5 effective relevant coefficients when p>5, with the explicit low-dimensional rule p0=p/2 when p<=5. This is a sparsity assumption, not a clinical fact or a result selected by CV. Each dummy contrast counts as a coefficient; a factor with several contrasts is not counted as one grouped selection unit. With standardized numeric columns, c=2 describes a one-training-SD contrast; with unscaled 0/1 dummies it describes the category-versus-reference contrast. The limiting Gaussian slab has approximately 95% log-HR range +/-3.92, corresponding to HRs about 0.02 to 50.4: permissive but finite. This fixed slab is a transparent benchmark choice, not a universal recommendation from the paper. Do not shrink baseline log rates through the horseshoe.

### Training-only curvature calibration (proposed adaptation)

Use the actual training design after preprocessing, the actual interval exposure matrix, and the declared baseline Normal(-2,2) prior. Divide times, interval boundaries, and exposures by the same median training event time. A coefficient log-HR does not change under this time rescaling; baseline rates do.

For interval j let d_j be the training event count and a_j=sum_i E_ij the total exposure. At beta=0 choose the baseline-only MAP reference theta_hat_j by solving the monotone scalar equation

    d_j - a_j * exp(theta_hat_j) - (theta_hat_j + 2)/4 = 0.

This is a training-only reference calculation for calibration, not a horseshoe posterior fit. Define mu_ij=E_ij*exp(theta_hat_j), m_i=sum_j mu_ij, b_j=sum_i mu_ij, and q_j=sum_i mu_ij*x_i. The likelihood Hessian blocks plus baseline-prior precision give

    A = sum_i m_i * x_i*x_i'
    B = diag(b_j + 1/4)
    C[:,j] = q_j
    I_eff = A - C * B^{-1} * C'.

I_eff is the beta curvature after allowing baseline rates to adjust, under the local quadratic approximation. The +1/4 is the precision of the specified Normal(-2,2) prior; it is not a free ridge penalty. This handles unequal exposure/event information, correlations, and unscaled dummy prevalence. A conditional-beta approximation using A alone must be labeled as conditional on the baseline and can overstate information. Exact dependencies and zero-information columns should be reported, not repaired by an arbitrary Gaussian noise sigma.

For local draws lambda~HalfCauchy(1), let V_HS(tau)=tau^2*diag(lambda_j^2). Compute

    m_HS(tau,lambda) = tr[I_eff * (I_eff + V_HS(tau)^{-1})^{-1}]

or, more stably, sum zeta/(1+zeta) over eigenvalues zeta of V_HS^(1/2)*I_eff*V_HS^(1/2). Use fixed, seeded local-scale draws and root-find tau0 so E_lambda[m_HS(tau0,lambda)]=p0. Reuse exactly the same draws during root-finding. This is the information-matrix analogue of PV's reference calibration at tau=tau0. It does not mean the full HalfCauchy hyperprior has marginal expected complexity exactly p0.

After calibration, calculate the same trace with the regularized v_j and record its mean and quantiles; finite slab regularization reduces effective complexity. The paper similarly permits calibration of the underlying horseshoe followed by slab regularization (Section 3.4). Also record the full hyperprior-induced complexity distribution from prior draws. If rank(I_eff)<=p0, the requested calibration is unattainable: report it rather than silently changing p0 or treating tau0=1 as calibrated. Tiny negative eigenvalues from floating-point error can be clipped under a recorded tolerance; meaningful negative eigenvalues indicate an implementation error.

A less expensive diagonal approximation replaces I_eff by diag(I_eff); then the exact horseshoe local-scale expectation is sum_j tau0*sqrt(I_eff[j,j])/(1+tau0*sqrt(I_eff[j,j])). It retains exposure and categorical scaling but drops correlation. Prefer the full trace when feasible; label the diagonal route explicitly. Neither version is the paper's exact survival theorem: both are local-curvature adaptations and require recorded reference values and prior-draw checks.

Freeze c, p0 rule, seed, root tolerance, reference baseline, preprocessing and diagnostic criteria. Construct tau0 separately from each outer training fold; if any comparator tuning is introduced, repeat calibration inside the inner-training split. Never select these choices from held-out predictive performance.

## Survival decision curves from saved repeated-CV predictions

Primary DCA source: Vickers, Cronin, Elkin and Gonen (2008), *Extensions to decision curve analysis*, https://doi.org/10.1186/1472-6947-8-53 ; full text https://link.springer.com/article/10.1186/1472-6947-8-53 . Relevant sections: correction for overfit by repeated CV; confidence intervals for net benefits; application to censored data. Their survival estimator uses Kaplan-Meier survival among selected patients. The IPCW version below is an explicitly derived extension, not a verbatim reproduction of that estimator.

Primary IPCW sources: Gerds and Schumacher (2006), https://doi.org/10.1002/bimj.200610301 (conditional versus marginal censoring assumptions); Kvamme and Borgan (2023), *The Brier Score under Administrative Censoring*, https://www.jmlr.org/papers/volume24/19-1030/19-1030.pdf , Section 3.2 Eq. (4) gives the event and event-free IPCW terms and left-limit convention. These same terms identify binary event-state expectations and can therefore weight DCA utility.

For patient i's saved out-of-fold prediction in repeat r, retain the outer fold f(i,r), its training-derived horizon h_ir in original time units, and predicted event risk q_ir=1-S_hat_ir(h_ir). Use posterior mean event risk if that was the frozen prediction rule; do not use a risk score as if it were an absolute probability. Define action A_ir(u)=1[q_ir>=u], with threshold odds w(u)=u/(1-u), for 0<u<1.

Fit reverse Kaplan-Meier censoring survival G_f using only the relevant outer-training patients (censoring event indicator 1-delta), assuming censoring is independent of event time and model predictors. If only conditional independence is defensible, use a declared training-only conditional G_f(t|x); marginal KM does not correct predictor-dependent censoring. The addendum should state this limitation rather than claim that IPCW automatically solves informative censoring.

For observed time Y_i=min(T_i,C_i) and event indicator delta_i, define

    U_ir = delta_i * 1[Y_i<=h_ir] / G_f(Y_i- | x_i)
    V_ir = 1[Y_i>h_ir] / G_f(h_ir | x_i)
    NB_model,r(u) = (1/n) * sum_i A_ir(u) * [U_ir - w(u)*V_ir]
    NB_all,r(u) = (1/n) * sum_i [U_ir - w(u)*V_ir]
    NB_none,r(u) = 0
    NB_model(u) = (1/R) * sum_r NB_model,r(u).

Use the same matched patient/horizon/censoring weights for all compared models and both default strategies. Patients censored before the horizon contribute zero to both IPCW event-state terms but remain in denominator n. Do not drop them and renormalize over observed outcomes. This specifies an ordinary Horvitz-Thompson IPCW estimator; any self-normalized version is a separately labeled sensitivity analysis.

The formulas follow directly from NB=Pr(action,event)-u/(1-u)*Pr(action,no event) and IPCW identification. Verify no-censoring reduction to the usual TP/n-odds*FP/n formula, and verify setting every A=1 or A=0 exactly reproduces the default strategies.

### Horizons, support, and interpretation

Freeze horizon rules and threshold grid before drawing the new curves. If horizons vary by fold because they are training event-time quantiles, the average curve estimates performance of that training-horizon procedure, not net benefit at a single calendar horizon. Give the original-unit horizon median/range by dataset and rule. Do not average risks across repeat-specific horizons before thresholding; average net-benefit contributions after applying each correct horizon. A clinically interpretable fixed-year DCA requires a common fixed original-unit horizon supported in every relevant training fold.

As an operational guard, require each training horizon to lie within training follow-up support, G_f(h)>=0.10, and at least 10 training patients still at risk. These are frozen stability choices, not literature-derived universal constants. Report event counts, horizon-specific known event-free counts, early-censoring counts, G(h), maximum weight, selected-patient count, and weight ESS. Do not replace zero G by epsilon or silently truncate weights. Unsupported dataset/horizon results should be unavailable, or use an explicitly reported common support subset across models with its evaluated fraction; do not present it as full-cohort utility.

Use threshold odds consistently; endpoints u=0 and u=1 require separate limiting treatment and should not be included in the ordinary formula. Without an identified clinical intervention and threshold rationale, label curves exploratory threshold scenarios. A higher curve means better estimated net benefit for the specified action-cost ratio; it is not proof that the action improves outcomes.

### Dependence-aware uncertainty

The independent resampling unit is patient ID, not the n*R prediction rows, folds, or posterior draws. For a frozen forecast analysis, use a paired patient-cluster bootstrap: resample patient IDs and retain all repeats and all model predictions for each sampled ID. Average each sampled patient's repeat-specific utility contributions before constructing the bootstrap average. Use the same sampled IDs for all model/default contrasts. Freeze at least 1000 bootstrap replicates and report pointwise percentile intervals for NB differences at a small frozen set of thresholds, rather than implying simultaneous coverage across the entire grid.

With saved models, horizons and G held fixed, these intervals are conditional descriptive uncertainty. They account for repeated rows of the same patient but do not include model refitting, threshold selection, horizon selection, or all dependence induced by overlapping training fits. Do not label them unconditional confidence intervals for the complete learning procedure. A fuller bootstrap would resample patients, refit all training and censoring procedures, and repeat the entire CV pipeline; that is a different, more expensive analysis. Refitting only G in a patient bootstrap can include some censoring-estimation uncertainty while remaining conditional on saved outcome forecasts and horizons, but must be declared separately.

Primary CV variance source: Bengio and Grandvalet (2004), *No Unbiased Estimator of the Variance of K-Fold Cross-Validation*, https://jmlr.org/papers/v5/grandvalet04a.html . This supports avoiding independent-fold standard errors; the patient-cluster recommendation and its conditional scope above are design-specific statistical judgments.

## Minimum frozen audit record

Record model version, exact fold manifest/patient IDs, each training time scale, encoded column names, p/p0/c, tau0 and reference curvature diagnostics, actual prior complexity summaries, horizon rule and original-unit values, censoring assumption/estimator, support policy, threshold grid, bootstrap seed/count, interval scope and failed/unsupported cells. Pair all comparisons on the same supported records. Describe results as a post-hoc addendum and avoid changing the frozen primary benchmark or presenting these choices as prespecified before earlier results existed.
