# Post-hoc extension addendum

Specification date: 2026-09-28. Status: freeze recorded separately in
`coordination/extension_protocol_freeze.json`. This addendum is an independent
multi-cohort post-hoc evaluation, not external preregistration. ADR-039
refines ADR-036–ADR-038. The original protocol, original failures, incomplete
primary Holm family and failed explanation gate remain unchanged.

## Chronology and purpose

The existing 450-cell primary record, 825-cell robustness programme, 450-cell
exact reproduction, ADR-033 Holm bound and 75-cell ADR-032 sampler sensitivity
were already known. ADR-032 has all 75 diagnostic passes, nine estimable
contrasts, adjusted p-values 1 and corrected intervals including zero. These
are earlier evidence, not result-blind new analyses. The current extensions
were authorised before their own outer-validation outcomes existed.

Executed authors/CRAN R fixtures, source alignment and a one-chain,
100-tune/100-draw training-only computational profile preceded this freeze.
No extension held-out score or decision curve informed these settings.
The profile supports feasibility, not production diagnostics or a total
runtime guarantee. Earlier interrupted and failed preparation probes are
retained outside the primary record. Full production uses clean committed
sealed code, exact locked Python, and a new external output directory.

The questions are whether penalised partial-likelihood comparators alter the
Bayesian comparison, whether prior specification affects estimation, whether
the catalytic prior remains usable across information regimes, and whether
measured expression changes matched predictive accuracy. Null hypotheses are
zero paired mean IBS differences within each defined family. Smaller IBS is
better. Calibration, discrimination, computational cost and diagnostic
coverage accompany estimates; no equivalence margin is introduced.

## Patients, folds and evaluation

Clinical extensions reuse exactly the frozen 5-repeat × 5-fold patients,
event/time stratification, base seed 260817 and training-event-quantile
evaluation rules. Three inner folds select mean IPCW IBS; exact ties follow
candidate order. Every transform and outcome-dependent prior generator is
fitted inside the relevant training set, including inner training.
Source reconciliation found one known same-individual accession pair in the
frozen clinical METABRIC CSV. Preserve its historical fold membership and
report inherited train/test exposure explicitly; do not claim biological
independence for that full clinical record. The matched expression cohort
contains no pair with both members and supplies the corresponding comparison
without known duplicate-pair overlap. Decision-curve bootstrap units group
known aliases as one biological cluster while retaining their records.

The expression cohort uses measured log2 Illumina HT-12 v3 intensities from
cBioPortal datahub commit `165bd77077b03038f9c2ee104959eb474770b2a9`.
Hashes, raw schemas and unique sample/patient mappings are recorded in
`coordination/extension_sources/metabric_source_report.json`. Within-sample
median aggregation by positive integer Entrez ID resolves probe/alias rows;
it learns nothing across patients. No additional log transform or all-sample
z-score matrix is used. Source OS times/events must agree with the clinical
CSV. Positive follow-up, primary samples, unique patient mapping and known
same-individual accession checks yield 1,979 patients and 1,143 events.
Both settings use these same patients, sorted IDs, outcomes and new common
25 folds. Published upstream cohort normalization is acknowledged; raw-assay
prospective normalization and exact pretreatment availability are unresolved.
This is a retrospective expression-augmented benchmark, not a deployment test.

Inside each training split, discard genes with >20% missing values, median
impute, rank by variance before scaling with lexical identifier tie-breaking,
retain exactly 512, then standardize with training means/population SDs.
Clinical preprocessing remains the declared diagnosis/pathology specification;
remove constant encoded training columns and record them. Numeric scaling,
categorical levels and selected genes never use validation observations.
Report actual encoded p, p/n and events/p. This is not a claim that p>=n.

Both matched settings include all original six arms, ridge/lasso/elastic-net,
the calibrated horseshoe, fixed/adaptive catalytic Bayes and catalytic WME:
13 models × 2 settings × 25 folds = 650 fits. New clinical arms contribute
7 × 3 cohorts × 25 = 525. Catalytic RQ2 adds 450 distinct fits: 25%, 50%, 75%
nested event/time-stratified training fractions and full-training administrative
75th/50th follow-up quantiles, on folds 1/2 in all five repeats. The 90 full
clinical anchors are reused, not refitted. No fraction × censoring crossing
is added. Subset seeds and memberships match frozen robustness; require at
least 20 training events and account for exclusions. Total distinct fits: 1625.

## Penalised Cox and Bayesian variants

Ridge minimises negative mean Breslow partial log likelihood plus
lambda*||beta||²/2: scikit-survival CoxPH alpha=n_training*lambda.
Lasso/elastic-net use Coxnet alpha=lambda; elastic-net L1 fraction is 0.5.
The 13 fixed lambdas are 10^(-4), 10^(-3.5), ..., 10^2, as listed in
`config/extensions.yaml`. Coxnet fits the baseline. Every candidate must
complete all three inner folds; convergence warnings invalidate a candidate.
All-zero solutions are valid if predictions/evaluation remain valid.

The P-V comparator has z~N(0,1), local half-Cauchy(1), global
half-Cauchy(tau0), fixed slab c=2, beta=z*sqrt(tau²*c²*lambda²/(c²+tau²*lambda²)).
Set p0=5 when p>5 and p0=p/2 otherwise. This expresses an assumed sparsity
level, not an estimated count. At beta=0 compute the baseline-only PWE MAP
under logbaseline~N(-2,2). With exposure E and mu=E*exp(theta), profile the
baseline by the Schur complement of total information, including precision
1/4. Use its diagonal h_j and solve
sum_j tau0*sqrt(h_j)/(1+tau0*sqrt(h_j))=p0.
This explicitly omits predictor correlations. It is a survival-curvature
adaptation, not the Gaussian sigma/sqrt(n) rule or an exact survival theorem.
Zero/invalid information raises. Record h, tau0 and finite-slab expected
complexity at fixed tau0, which is smaller than underlying horseshoe p0.

All new/matched Bayesian fits keep six PWE intervals, the same time scale,
baseline prior and likelihood. A compact subject-wise design product is
algebraically equivalent to the interval-expanded implementation; likelihood
and gradient parity are checked. Original frozen code remains unchanged.
Use four sequential chains, 2000 draws/tune, target acceptance .999. At most
two refits double tune to 4000; the last uses the equivalent noncentred
baseline. The ADR-027 all-parameter R-hat/ESS/divergence/BFMI/tree-depth gate
is unchanged. Failure is an analysis outcome. Store each actual trace,
diagnostics, prior and posterior predictive checks and attempted configuration.

## Catalytic construction and reference boundary

Resample independent numeric source-variable marginals and whole categorical
levels, then apply the training encoder and recompute derived features.
With actual encoded p set M=max(1000,4p). Fit the censored-exponential
reference rate h+=sum(events)/sum(observed scaled time); draw positive,
uncensored synthetic times. Record seed, rate, time scale, source variables,
synthetic hash and full-column-rank check. Synthetic rows are prior data,
never real patients, test observations or evaluation outcomes.

Define q(beta)=mean(x*beta-h+*y*exp(x*beta)); omit log(h+) consistently.
Fixed prior log kernel is p*q(beta). For adaptive tau, alpha=2 and gamma=1:
log pi(beta,tau)=(p+alpha-1)log(tau)+tau*(q(beta)-kappa-1/gamma),
where kappa=sup_beta q(beta). Optimize the concave kernel with checked
maximum absolute score <=1e-6. The conditional tau shape is p+alpha and
rate kappa-q(beta)+1/gamma. It is not Gamma(2,1) times a weighted prior.

Likelihood-free NUTS samples the actual fixed/joint prior for predictive
checks, with the same gate/remedies as posterior sampling. Forward PyMC
prior sampling ignores Potentials and is prohibited for these variants.
This preserves the project's PWE likelihood/baseline and therefore adapts
the authors' coefficient prior; it does not replicate their grouped-baseline
posterior. Numerical parity concerns the prior and WME only.

WME maximises weighted merged-data Breslow partial likelihood, with case
weights 1 and tau/M in event terms AND risk denominators. Select tau from
{p/4,p,4p} by inner IBS, with a fresh training-only generator in each inner
split and the same synthetic rows across its candidates. Outer synthetic
rows are generated afresh from outer training. Actual optimizer success,
finite coefficients, maximum absolute score <=1e-4 and valid survival are
required. Absolute survival uses the weighted merged-data Breslow baseline
on the common model time scale; this is an explicit extension beyond the
package's X*beta prediction. MCMC gates do not apply to this point estimator.

The frozen fixture contains censoring, tied events and treatment-coded
three-level categories. Exact authors' R WME, official CRAN source WME,
factor encoding and R prior arithmetic were executed. Fixtures and source
hashes are committed. Stan compilation was not performed; formula/source
checks used the authors' arXiv v2 and CRAN source. Published journal metadata
was verified, but its full text returned 403. No broader parity is claimed.

## Decision curves

Use saved absolute event risk 1-S at the 25th/50th/75th training-event
quantile, retaining each record's original-unit fold horizon. Threshold
before averaging repeats. Thresholds .01 through .50 in .01 steps represent
exploratory escalation of clinical assessment at a specified action-cost
ratio; no specific effective treatment or clinical threshold is established.
GBSG2 uses its recurrence endpoint, WHAS500/METABRIC overall survival.

Training reverse KM supplies G. Event weight U=delta*1(Y<=h)/G(Y-);
event-free weight V=1(Y>h)/G(h). Utility is action*(U-u/(1-u)*V), averaged
over all patients including early-censored zero contributors. Treat-all
uses action=1 and treat-none zero. Require h within training support,
G(h)>=.10, at least 10 training patients at risk, and supported event
weights. No epsilon substitution or weight truncation. Marginal IPCW
assumes censoring independence; predictor-dependent censoring is unresolved.

Curves describe the adaptive training-horizon procedure, not common-year
clinical utility. Report original-unit horizon ranges, known events/free,
early censoring, weight ESS and support failures. A model curve requires
all 25 folds and complete matched patient/repeat records; unavailable
models/horizons are explicit. Original horseshoe curves and ADR-032 curves
retain separate identities. Bootstrap 1000 paired patient IDs with all
repeats retained, after averaging patient-specific utility across repeats.
Known same-individual accessions are sampled as one cluster; each sampled
cluster retains all its accessions/repeats, and the record denominator follows
the sampled cluster sizes. Pointwise percentile intervals and model-minus-all/none intervals are
conditional on saved forecasts/horizons/G, not refit-procedure uncertainty
or simultaneous threshold-grid coverage. No clinical-impact claim.

## Paired inference and verification

Use mean paired IBS differences with Nadeau–Bengio repeated-CV correction
and 95% intervals. Require all 25 planned pairs and identical patients,
outcomes, training memberships and evaluation grids; matched feature-arm
contrasts also use common eligible patients. Four separate post-hoc Holm
families are fixed: 27 penalised-versus-inherited-prior contrasts; 3
calibrated-versus-ADR032-horseshoe contrasts; 27 catalytic-versus-inherited-
prior contrasts; 13 matched expression-minus-clinical contrasts. The first
and third use frozen normal/spike-slab and separately labelled ADR-032
horseshoe; the original failed horseshoe primary record is not replaced.
Only a complete family permits Holm rejection language, and any claim also
requires a corrected interval excluding zero. Missing contrasts remain
missing. Other comparator effects, discrimination/calibration and RQ2
differences/differences-in-differences are descriptive, without additional
significance claims. For RQ2, report complete/partial paired coverage and
compare actual identical condition memberships, never pool cohorts.

Independently verify every cell hash, trace hash/diagnostics, patient/fold
identity, valid predictions and recomputed metrics. Seeded exact refits cover
the first clinical fold for every new model/cohort, the first matched fold
for all 13 models/settings, and the first-repeat first-fold five nonfull
RQ2 conditions for each catalytic model/cohort: 21+26+45=92 cells, including
planned failure outcomes. Compare all non-timing scientific content; timing
and environment path strings are separately recorded. Hash verification
covers all 1625 cells; selected refits are not an all-cell reproduction claim.
Render from stored evidence only, actually inspect every new figure/table
layout, review claims and package all data/provenance/code/traces/results
in a private remote release. Download and restore independently before
completion is reported. No Overleaf edit, paper submission or DOI minting
is included.

## Primary references

- [Li and Huang, author preprint v2](https://arxiv.org/html/2312.01411v2);
  [published journal record](https://doi.org/10.1093/biomtc/ujag004);
  [official CRAN catalytic package](https://cran.r-project.org/package=catalytic).
- [Piironen and Vehtari (2017)](https://arxiv.org/html/1707.01694).
- [Vickers et al. (2008)](https://doi.org/10.1186/1472-6947-8-53),
  [IPCW event/free weights](https://www.jmlr.org/papers/volume24/19-1030/19-1030.pdf).
- [scikit-survival CoxPH source](https://github.com/sebp/scikit-survival/blob/v0.28.0/sksurv/linear_model/coxph.py)
  and [Coxnet source](https://github.com/sebp/scikit-survival/blob/v0.28.0/sksurv/linear_model/src/coxnet/coxnet.h).
- [Curtis et al. (2012)](https://doi.org/10.1038/nature10983);
  pinned source/audit references are in the METABRIC source report.
