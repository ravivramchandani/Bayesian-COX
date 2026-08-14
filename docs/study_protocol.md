# Confirmatory study protocol

Version: 0.1, 2026-08-14. This protocol is a design draft until the Week 2
scope gate. It must be frozen, assigned a version and archived before any
confirmatory result is inspected. The completed benchmark in
`reports/tables/benchmark.json` and the current explainability analysis are
exploratory development evidence only.

## Intended contribution

The thesis will be an auditable multi-cohort study of when coefficient-prior
choice changes predictive accuracy, uncertainty and global explanation
stability in Bayesian proportional-hazards prediction as effective
information and censoring vary.

Working title:

> Prior choice, calibration, and explanation stability in Bayesian
> proportional-hazards prediction: a multi-cohort survival benchmark

The work evaluates an implemented Bayesian piecewise-exponential
proportional-hazards model. It does not claim to invent Bayesian Cox
regression, the regularised horseshoe, continuous spike-and-slab, SHAP or
DeepSurv. Its contribution is the controlled, reproducible comparison and
the evidence about uncertainty and explanation stability.

The success target is an examiner-ready master's thesis and a manuscript of
Q1-journal quality within 26 weeks. Journal quartiles and editorial decisions
are external and cannot be guaranteed.

## Scope

### Thesis-essential scope

- Three public, right-censored clinical cohorts: GBSG2, WHAS500 and METABRIC.
- Cox PH, random survival forest, one validated DeepSurv implementation, and
  Bayesian proportional-hazards models with Normal, regularised-horseshoe and
  continuous spike-and-slab coefficient priors.
- Fold-local preprocessing and repeated nested cross-validation.
- Probabilistic performance, discrimination, explicit calibration,
  uncertainty, computational cost and explanation stability.
- Prespecified sensitivity analyses for predictor availability, missingness,
  censoring, sample size, proportional-hazards assumptions, baseline-hazard
  intervals and prior hyperparameters.
- A claim-to-evidence ledger, exact environment lock, immutable result
  manifests and TRIPOD+AI/PROBAST+AI review.

### Publication-enhancing scope

- A small ADEMP-structured simulation assessing coefficient recovery and
  predictive performance under sparse/dense and low/high-information
  regimes. It is admitted only at the Week 12 gate if the confirmatory real-
  data run is on schedule.
- A true locked transport evaluation from a Rotterdam breast-cancer model to
  GBSG2. It is admitted only at the Week 4 data gate after endpoint
  harmonisation, licence, predictor mapping and compute are verified. It is
  not a fourth independently retuned benchmark.

### Explicit exclusions

- Competing risks, DeepHit and additional neural architectures.
- Gene-expression or mutation predictors.
- Causal treatment effects or treatment recommendations.
- Clinical deployment, decision-curve utility, fairness-effectiveness or
  transportability claims unsupported by the data.
- New priors during the confirmatory programme. The catalytic prior is future
  work unless a later, supervisor-approved project explicitly reopens it.
- Non-healthcare datasets and universal claims about Bayesian superiority.

## Prediction targets and analysis populations

Prediction time must precede every primary predictor. A source-variable
availability table will be signed off before model fitting.

| Cohort | Time origin and endpoint | Primary analysis population | Primary predictor rule |
|---|---|---|---|
| GBSG2 | Trial-defined recurrence-free survival, in days; exact time origin to be verified from the primary trial report in T-112 | All 686 records with 299 events | Variables documented at the prognostic baseline; treatment assignment may be retained only if known at that baseline |
| WHAS500 | Admission for acute myocardial infarction to all-cause death, in days | All 500 records with 215 deaths | Admission-time variables only; length of stay is excluded from the primary set |
| METABRIC | Overall survival, in months; the exact source time origin is verified in T-112 before a diagnosis-time claim | Expected 1,980 positive-time records with 1,144 deaths after rebuilding from the pinned cBioPortal snapshot | Diagnosis/pathology variables available before adjuvant treatment; surgery type and treatment-received variables are excluded from the primary set |

The WHAS500 full published feature set, including length of stay, and the
METABRIC treatment-augmented feature set are comparability sensitivities.
They are not the basis of a prospective-at-baseline prediction claim.

For METABRIC, the primary specification must avoid including Nottingham
prognostic index together with all of its component variables. One
prespecified representation is primary and the other is a sensitivity.
Raw/log-transformed copies and dummy variables are aggregated into clinical
source-variable groups for explanation analyses.

## Data sources and availability

No new real dataset is required. All three core cohorts are locally available
and independently retrievable.

| Cohort | Authoritative source | Availability and licence action |
|---|---|---|
| GBSG2 | [`sksurv.datasets.load_gbsg2`](https://scikit-survival.readthedocs.io/en/stable/api/generated/sksurv.datasets.load_gbsg2.html) | Pin the scikit-survival release and upstream ARFF checksum; preserve the original-trial DOI and package data notice in the manifest |
| WHAS500 | [`sksurv.datasets.load_whas500`](https://scikit-survival.readthedocs.io/en/stable/api/generated/sksurv.datasets.load_whas500.html) | Pin the scikit-survival release and upstream ARFF checksum; preserve the source-book DOI and package data notice in the manifest |
| METABRIC | [cBioPortal DataHub snapshot `165bd770...`](https://github.com/cBioPortal/datahub/tree/165bd77077b03038f9c2ee104959eb474770b2a9/public/brca_metabric) | Rebuild from the pinned patient/sample files; the study-specific [ODbL licence](https://github.com/cBioPortal/datahub/blob/master/public/brca_metabric/LICENSE) requires attribution and share-alike handling of adapted databases |

The current 1,904-row Kaggle file remains available only to reproduce the
exploratory pilot. It omits 77 otherwise eligible positive-time survival
records and 41 deaths relative to the pinned 2,509-row clinical export. It
must not supply confirmatory METABRIC results.

Before release, a data manifest records source URL and immutable version,
retrieval date, upstream and derived hashes, licence, citation, eligibility
rules, endpoint/event coding and redistribution decision. The project MIT
licence applies to software, not automatically to upstream data.

## Research questions and hypotheses

### RQ1 — Prediction under different coefficient priors

How do Normal, regularised-horseshoe and continuous spike-and-slab priors
affect out-of-sample survival prediction relative to Cox PH, random survival
forest and DeepSurv?

- Primary estimand: within-cohort paired difference in IPCW integrated Brier
  score (IBS) over a training-defined evaluation window.
- Primary inferential family: the three pairwise contrasts among Bayesian
  priors, evaluated in each of the three cohorts (nine tests).
- Secondary estimands: paired differences in Uno's C-index, cumulative/
  dynamic AUC, calibration intercept and calibration slope at three
  training-defined horizons.
- Benchmark contrasts against Cox PH, random survival forest and DeepSurv are
  secondary and estimation-led; there is no unrestricted all-pairs testing.
- Hypothesis H1: shrinkage-prior benefit relative to the Normal prior grows
  as observed events per effective predictor degree of freedom falls.

### RQ2 — Information-regime robustness

Does the prior effect change as training information falls or censoring
increases?

- Information measure: observed training events divided by predictor degrees
  of freedom.
- Training fractions: 25%, 50%, 75% and 100%, with identical event/time-
  stratified subsamples for all models in a contrast.
- Censoring conditions: observed follow-up plus two prespecified
  administrative-truncation conditions derived only from training data.
- Primary estimand: the difference-in-differences in IBS contrast between a
  low-information condition and the full-information condition.
- Hypothesis H2: shrinkage relative to the Normal prior is more beneficial at
  lower effective information.

### RQ3 — Explanation agreement and stability

How stable are Bayesian global feature rankings, and what does their
agreement with SHAP measure?

- Common primary Bayesian importance: posterior expected absolute
  contribution, averaged over validation subjects and posterior draws,
  $E(|x_j\beta_j|)$.
- Probability of direction is a certainty measure, not magnitude importance.
- Horseshoe shrinkage and the continuous spike-and-slab mixing weight are
  secondary prior-specific signals, not ground-truth inclusion probabilities.
- Estimands: between-resample Spearman and Kendall correlation, top-five
  Jaccard overlap, rank variability and selection frequency with uncertainty.
- Hypothesis H3a: intrinsic importance agrees more strongly with SHAP
  computed on the same Bayesian posterior-mean risk model than with SHAP from
  another model family.
- Hypothesis H3b: cross-model agreement is stronger with Cox PH than with the
  forest because Cox PH shares the linear proportional-hazards structure.

### RQ4 — Design robustness

Do the headline contrasts retain their direction under plausible choices
about baseline predictors, missingness, censoring, proportional hazards,
baseline-hazard intervals and prior hyperparameters?

A finding is called robust only when the direction is unchanged and the
sensitivity estimate is compatible with the primary uncertainty interval.
Otherwise its design dependence is reported explicitly.

## Confirmatory validation design

1. Use five repeats of five-fold outer cross-validation, stratified jointly
   by event status and coarse follow-up-time bins. The exact bin rule and fold
   seeds are frozen in the protocol.
2. Fit imputation, encoding, scaling, transformations, feature grouping,
   feature selection and evaluation-horizon selection inside each outer
   training fold. No validation/test record informs these operations.
3. Use inner three-fold cross-validation for compact, frozen random-forest and
   DeepSurv hyperparameter grids. Cox PH has no outcome-driven tuning.
   Bayesian prior definitions are fixed by prior-predictive checks, not tuned
   to validation performance.
4. Choose the IBS integration window and three reporting horizons from each
   outer training fold only, then constrain them to support with estimable
   censoring weights. Record every resulting horizon.
5. Generate out-of-fold risks and survival probabilities for every subject.
   Store subject ID, cohort, repeat/fold, model, feature specification,
   hyperparameters, metrics, predictions, seed, runtime and diagnostics.
6. Keep endpoint-specific estimates separate. The three cohorts are
   replication settings, not independent external validations of one model
   and not interchangeable samples from one clinical population.

The five-repeat design is subject to a result-blind compute gate after a
single-fold rehearsal. If projected wall time exceeds 72 hours on available
hardware, repeats may be reduced to three before any confirmatory performance
is inspected; the decision and benchmark timing must be recorded.

## Models and implementation controls

- Cox PH uses lifelines.
- Random survival forest uses scikit-survival.
- DeepSurv must be either a pinned pycox CoxPH reference implementation or a
  local implementation that passes numerical/reference parity, gradient,
  prediction and overfit-a-tiny-dataset tests. Dropout, normalisation,
  optimiser and early stopping settings must actually be wired and recorded.
- The Bayesian model is described accurately as a piecewise-exponential full
  likelihood with a proportional-hazards linear predictor; it is not an
  exact Bayesian partial-likelihood Cox model.
- Time scale and baseline-hazard priors must be harmonised across day/month
  cohorts, either by training-fold time rescaling or justified cohort-specific
  priors.

## Metrics and statistical analysis

### Primary and secondary metrics

- IPCW IBS is the primary probabilistic prediction-error metric. It reflects
  both discrimination and calibration and is never used alone to claim
  calibration.
- Uno's IPCW C-index is the primary discrimination metric because it is less
  sensitive than Harrell's C-index to censoring. Harrell's C-index remains a
  familiar descriptive secondary metric.
- Cumulative/dynamic AUC is reported at the three training-defined horizons.
- Calibration is assessed with curves plus calibration-in-the-large/intercept
  and calibration slope at the same horizons. Calibration estimates state
  the estimator and uncertainty method.
- Runtime, convergence failure and memory are reported as practical outcomes.

### Inference

- All model contrasts use identical outer folds and subject sets.
- Headline effects are paired metric differences with 95% intervals.
- Repeated-CV uncertainty uses a prespecified Nadeau–Bengio corrected
  procedure; an event-stratified paired bootstrap of out-of-fold predictions
  is a sensitivity analysis.
- Holm adjustment applies within the nine-test primary prior-comparison
  family. Secondary comparisons emphasise magnitude and compatibility
  intervals and are labelled exploratory.
- A model is not called equivalent or non-inferior without a separately
  justified, frozen margin. An interval containing zero means “no clear
  evidence of a difference,” not “the models are the same.”
- The current comparable-pair standard-error approximation and any stubbed
  test result are excluded from inference.

## Bayesian quality protocol

Prior-predictive survival checks are performed before the confirmatory
freeze. Posterior predictive checks are archived for every final model/cohort
fit.

Diagnostics cover coefficients, baseline log-hazards, global and local
scales, slab parameters and continuous mixing weights—not only `beta`. The
record includes rank-normalised R-hat, bulk and tail ESS, Monte Carlo standard
error, divergences, BFMI and maximum-tree-depth hits.

The existing minimum gate is R-hat below 1.01 and bulk ESS above 400. The
confirmatory target is zero divergences. A failed fit receives at most two
prespecified remedies: higher target acceptance, then an approved
reparameterisation. A cell that still fails is reported as failed and its
posterior coefficients are not interpreted.

## Missing data

Every missingness table is derived before model fitting and reproduced per
outer fold. Imputation is fit only on training data.

METABRIC tumour stage is about 26% missing in the proposed confirmatory
cohort. The primary core feature set therefore excludes stage or uses a
prespecified missingness representation. Fold-wise multiple imputation is a
sensitivity analysis. The manuscript must not claim that posterior
uncertainty integrates covariate-imputation uncertainty unless the
implementation actually propagates it.

## Explainability protocol

- Select validation subjects with a recorded random seed and use the same
  subjects for every model in a paired comparison; never use the first rows
  of a file.
- Draw each SHAP background from the corresponding training fold.
- Compute SHAP for the Bayesian posterior-mean risk model for the primary
  within-model comparison, then compare with Cox PH and random survival
  forest as secondary cross-model analyses.
- Use three SHAP seeds. Start with 256 coalitions and increase until successive
  rankings have Spearman correlation at least 0.95 and at least four common
  top-five feature groups.
- Aggregate encoded, raw/log and interaction terms into prespecified clinical
  source-variable groups before global ranking.
- Estimate ranking uncertainty across folds/resamples.
- Never infer causality, feature truth, treatment benefit or clinical utility
  from posterior/SHAP agreement.

## Prespecified robustness analyses

- WHAS500 baseline-only primary versus the full published set including
  length of stay.
- METABRIC baseline-only primary versus treatment-augmented predictors.
- METABRIC core/missing-indicator primary versus fold-wise multiple
  imputation.
- NPI alone versus its tumour-size/grade/node components.
- Parsimonious predictors versus the currently engineered predictor set.
- Piecewise baseline hazards with 4, 6 and 10 intervals.
- Proportional-hazards tests with multiplicity control; add time interactions
  only under the frozen response rule when violations are supported.
- Prior hyperparameter grid fixed before the confirmatory run.
- Training-size and administrative-censoring conditions from RQ2.

## Optional simulation

If admitted at the Week 12 gate, the simulation is reported separately from
the real cohorts and follows the ADEMP structure: aims, data-generating
mechanisms, estimands, methods and performance measures. A lean design uses
two sample sizes, sparse versus dense coefficients, and ordinary versus high
censoring, with at least 25 reproducible replicates per cell. It compares the
three Bayesian priors and Cox PH, not the full machine-learning roster.

Outcomes include IBS/Uno C, coefficient error, interval coverage and ranking
recovery, each with Monte Carlo uncertainty. No simulated row enters a real-
data result file or is described as clinical evidence.

## Claim and reporting gates

The binding wording rules are in `docs/claim_evidence_register.md`.
Quantitative manuscript claims must name an immutable machine-readable result
and key. Factual claims must have a verified primary or authoritative source.

Reporting follows:

- [TRIPOD+AI](https://www.bmj.com/content/385/bmj-2023-078378) for complete
  reporting of regression and machine-learning prediction studies;
- [PROBAST+AI](https://www.bmj.com/content/388/bmj-2024-082505) as the design
  and risk-of-bias audit;
- Bayesian analysis reporting guidance, including diagnostics for all
  parameters and predictive checks; and
- [ADEMP](https://doi.org/10.1002/sim.8086) if the optional simulation is run.

## Publication strategy

The primary journal candidate is *BMC Medical Research Methodology*, whose
scope includes empirical studies of methodological choices. *Computer
Methods and Programs in Biomedicine* is the main alternative. *Journal of
Biomedical Informatics* or *Artificial Intelligence in Medicine* is a stretch
target only if the completed study demonstrates sufficient methodological
novelty and receives clinical-domain review.

The journal, applicable category and current quartile must be re-verified in
the institution's accepted ranking source at Week 2 and again immediately
before submission. Manuscript quality is the controlled outcome; a Q1 label
or acceptance is not.

## Calendar and gates

The 26-week window runs from 2026-08-17 to 2027-02-14. `TODO.md` is the live
task register; this table defines the non-negotiable gates.

| Gate | Date | Required evidence |
|---|---:|---|
| G0 integrity | 2026-08-23 | Coordination reconciled; current results labelled exploratory; tests/lint pass; LaTeX failure inventory captured |
| G1 scope | 2026-08-30 | Prediction times, RQs, estimands, analysis plan, ethics/licensing questions and journal shortlist approved |
| G2 data | 2026-09-13 | Pinned manifests/hashes/licences, rebuilt METABRIC and baseline-predictor audit pass; optional external dataset accepted or permanently dropped |
| G3 design complete | 2026-09-27 | Fold-local pipeline, metrics/calibration, paired artefact schema, DeepSurv decision, full diagnostics and clean tests pass |
| G4 protocol freeze | 2026-10-11 | One-fold-per-cohort rehearsal passes; runtime decision made without inspecting confirmatory effects; protocol/config tagged |
| G5 confirmatory complete | 2026-11-08 | Repeated nested-CV predictions and primary analyses complete with no unresolved invalid fit |
| G6 robustness/evidence freeze | 2026-12-06 | Sensitivities and explainability complete; optional simulation admitted/completed or dropped; result manifest tagged |
| G7 full thesis draft | 2026-12-20 | Every chapter substantive; tables generated; no thesis-critical unverified claim |
| G8 examiner ready | 2027-01-17 | Statistical, citation, ethics, TRIPOD+AI/PROBAST+AI, reproducibility and clean-build reviews pass |
| G9 thesis delivered | 2027-01-24 | University-format thesis/source/archive submitted, leaving three weeks of contingency |
| G10 paper package | 2027-02-14 | Journal manuscript, supplement, checklist, declarations, cover letter and permissible reproducibility archive ready |

No unprespecified model family, prior, dataset or analysis may enter after G4.
The already specified optional simulation may be activated at the Week 12
scheduling review only if its design was frozen at G4; it is completed or
dropped by G6.

## Drop rules and definition of done

If a gate slips by more than one week, drop work in this order: external
transport evaluation, optional simulation, additional SHAP case studies,
then non-primary sensitivity grid points. Never drop fold-local preprocessing,
data provenance, calibration, full Bayesian diagnostics, claim verification,
the baseline-predictor audit, the primary robustness analyses or thesis build
quality.

The thesis is done only when all research questions are answered with either
supported findings or explicit negative/uncertain results, every submitted
claim is verified, all headline values trace to immutable artefacts, the
named environment reproduces the analysis, and a clean LaTeX build has zero
undefined references or citations.
