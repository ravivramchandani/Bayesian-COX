# Confirmatory study protocol

Version: 1.0-approved, 2026-08-15. The owner approved the design, ethics/data-
use position, licensing position and supervisor-decision track on 2026-08-15.
The protocol and five-repeat decision were fixed after a result-blind 18-cell
compute rehearsal completed on 2026-08-15. A second exact rehearsal under these
final inputs and the content-addressed write-once freeze remain required before
any comparative confirmatory result may be inspected.
The completed benchmark in
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

### Publication-enhancing scope decision

The optional Rotterdam transport analysis and ADEMP simulation were
permanently dropped before protocol freeze. The three-cohort confirmatory and
robustness programme already answers the approved master's-level questions;
adding either optional branch would weaken the six-month compute and writing
contingency. Neither omitted analysis is needed to support a claim retained in
this protocol. Simulation-based coefficient recovery and locked transport are
identified as future extensions, not incomplete thesis analyses.

### Explicit exclusions

- Competing risks, DeepHit and additional neural architectures.
- Gene-expression or mutation predictors.
- Causal treatment effects or treatment recommendations.
- Clinical deployment, decision-curve utility, fairness-effectiveness or
  transportability claims unsupported by the data.
- New priors during the confirmatory programme. The catalytic prior is future
  work unless a later, supervisor-approved project explicitly reopens it.
- Non-healthcare datasets and universal claims about Bayesian superiority.
- A fourth real-data cohort, a Rotterdam transport analysis, or an ADEMP
  simulation within the frozen six-month programme.

## Prediction targets and analysis populations

Prediction time must precede every primary predictor. A source-variable
availability table will be signed off before model fitting.

| Cohort | Time origin and endpoint | Primary analysis population | Primary predictor rule |
|---|---|---|---|
| GBSG2 | Source-defined recurrence-free survival in days. The pinned distribution and accessible trial metadata do not identify a more precise clinical clock anchor, which is retained as a limitation rather than inferred. | All 686 records with 299 events | Variables documented at the trial prognostic baseline; treatment assignment was recorded for the trial cohort |
| WHAS500 | Admission for acute myocardial infarction to all-cause death, in days | All 500 records with 215 deaths | Admission-time variables only; length of stay is excluded from the primary set |
| METABRIC | Overall survival in months since initial diagnosis, as defined by the pinned cBioPortal patient metadata | 1,980 positive-time records with 1,144 deaths rebuilt from the pinned cBioPortal snapshot | Diagnosis/pathology variables available before adjuvant treatment; surgery type and treatment-received variables are excluded from the primary set |

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
  secondary and estimation-led. The bounded roster contains each of the three
  Bayesian priors versus each of the three comparators within cohort (nine
  contrasts per cohort); comparator-versus-comparator pairs are not analysed
  and there is no unrestricted all-pairs testing or secondary multiplicity
  claim.
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
- The horseshoe local-scale shrinkage proxy and continuous spike-and-slab
  mixing weight are secondary prior-specific signals, not full posterior
  shrinkage factors or ground-truth inclusion probabilities.
- Estimands: between-resample Spearman and Kendall correlation, top-five
  Jaccard overlap, rank variability and selection frequency with uncertainty.
- Hypothesis H3a: intrinsic importance has stable positive agreement with SHAP
  computed on the same Bayesian posterior-mean risk model. Support requires
  every evaluable prespecified budget/seed stability comparison to pass and
  the three-stage-bootstrap Spearman interval to lie wholly above zero.
- Hypothesis H3b: same-model Bayesian agreement is stronger than the secondary
  agreement with Cox PH, whose linear proportional-hazards structure permits
  an exact no-refit comparison from frozen coefficients. The estimand is the
  paired same-model-minus-Cox difference in Spearman agreement at the largest
  frozen sampling budget. Its descriptive three-stage bootstrap resamples
  outer repeats, folds within repeat and explanation seeds within cell.
  Stronger-agreement wording is permitted only when the same-model and Cox
  stability gates both pass and the resulting 95% interval is wholly above
  zero.

### RQ4 — Design robustness

Do the headline contrasts retain their direction under plausible choices
about baseline predictors, missingness, censoring, proportional hazards,
baseline-hazard intervals and prior hyperparameters?

A finding is called robust only when the direction is unchanged and the
sensitivity estimate is compatible with the primary uncertainty interval.
Otherwise its design dependence is reported explicitly.

## Confirmatory validation design

1. Use five repeats of five-fold outer cross-validation. Within each event-
   status group, rank follow-up times deterministically (ties resolved by
   source-row order) and divide ranks into at most four equal-frequency bins.
   A time subdivision is used only if every resulting stratum contains at
   least five observations; otherwise that event group is stratified by event
   status alone. Outer repeat seed $r$ is $260817+1009(r-1)$. These folds and
   subject IDs are identical for all paired models.
2. Fit imputation, encoding, scaling, transformations, feature grouping,
   feature selection and evaluation-horizon selection inside each outer
   training fold. No validation/test record informs these operations.
3. Use inner three-fold cross-validation for compact, frozen random-forest and
   DeepSurv hyperparameter grids. Cox PH has no outcome-driven tuning.
   Bayesian prior definitions are fixed by prior-predictive checks, not tuned
   to validation performance.
4. Set the three reporting horizons to the 25th, 50th and 75th percentiles of
   observed event times in each outer-training fold. Evaluate IBS on 25
   equally spaced points from the first to third horizon. Every point must
   have training censoring survival strictly above 0.10; an unsupported fold
   fails explicitly rather than adapting a horizon from validation outcomes.
   For IPCW metrics only, validation follow-up beyond the final training-
   defined horizon is explicitly administratively censored immediately after
   that horizon; this preserves known event-free status through the window and
   prevents later validation times exceeding training censoring support.
   Harrell concordance and calibration retain the observed follow-up. Record
   every horizon, grid and truncation boundary.
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

Inner tuning uses three folds formed by the same event/time rule within each
outer-training fold. The frozen random-forest grid crosses minimum leaf size
5 or 15 with `sqrt` or all-feature candidate sampling, holding 300 trees and
minimum split size 10 fixed. The four DeepSurv candidates use one or two
hidden layers ([32] or [32,16]), dropout 0 or 0.2, and paired weight decay
$10^{-4}$ or $10^{-3}$; all use ReLU, batch normalisation, learning rate
$10^{-3}$, at most 100 epochs and training-only early stopping. Inner IPCW
IBS selects the candidate, with list order breaking exact ties.

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
  the estimator and uncertainty method. Each fold uses five equal-frequency
  calibration groups for the descriptive curve and 500 event-stratified
  percentile-bootstrap resamples for fixed-horizon complementary-log-log
  calibration parameter intervals; at least 80% of resamples must be
  estimable.
- Per-cell elapsed wall-clock time and convergence/fit failures are reported as
  practical outcomes. Peak memory is not instrumented and will not be claimed.

### Inference

- All model contrasts use identical outer folds and subject sets.
- Headline effects are paired metric differences with nominal 95%
  Nadeau–Bengio intervals.
- Repeated-CV uncertainty uses a prespecified Nadeau–Bengio corrected
  procedure; an event-stratified paired bootstrap of out-of-fold predictions
  is a sensitivity analysis. The latter uses 1,000 replicates, resampling
  validation subjects within event-status strata and applying identical
  indices to both models inside every paired fold before averaging fold IBS
  differences.
- Holm adjustment applies to p-values within the complete nine-test primary
  prior-comparison family. The accompanying 95% Nadeau–Bengio intervals are
  nominal, not multiplicity-adjusted. Primary superiority language requires
  both a Holm-adjusted p-value at most 0.05 and a nominal interval excluding
  zero. Secondary comparisons emphasise magnitude and compatibility intervals
  and are labelled exploratory.
- Paired calibration-in-the-large, intercept and slope differences at all
  three horizons are stored for the primary prior pairs and bounded secondary
  comparator roster, using the corrected repeated-CV interval. Their nominal
  p-values are not used to make secondary claims.
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

Numeric diagnostics use every retained draw. For deterministic supplemental
trace and marginal figures, each accepted or failed Bayesian cell additionally
archives up to 250 evenly spaced post-warm-up draws per chain for every
posterior variable. The thinned visualization snapshot is never used to
compute or override a diagnostic gate.

The existing minimum gate is R-hat below 1.01 and bulk ESS above 400. The
confirmatory target is zero divergences. A failed fit receives at most two
prespecified refits. The first raises `target_accept` to 0.99 and doubles
tuning iterations. The second retains those settings and expresses the
identical $\log\lambda_m\sim\mathcal{N}(-2,2^2)$ baseline-hazard prior in
non-centred form, $\log\lambda_m=-2+2z_m$,
$z_m\sim\mathcal{N}(0,1)$. A cell that still fails is reported as failed and
its posterior coefficients are not interpreted. This remedy changes
parameterisation, not the statistical model.

## Missing data

Every missingness table is derived before model fitting and reproduced per
outer fold. Imputation is fit only on training data. A nominal value absent
from a training fold creates no new coefficient and maps to that factor's
all-zero reference block at validation. Its frequency is reported as a
preprocessing limitation rather than treated as an estimated effect for an
unseen level.

METABRIC tumour stage is missing for 514 of 1,980 subjects (26.0%). The primary
core feature set therefore excludes stage. The stage sensitivity uses five
fold-local numeric imputations: an iterative posterior-sampling imputer is fit
only to training-fold age, NPI and stage, then applied to validation rows with
five recorded seeds. Imputation-specific risk scores and survival
probabilities are combined by their arithmetic mean, after which pooled
metrics are recomputed from the averaged predictions. Metrics and diagnostics
for each imputation-specific fit are archived separately. This sensitivity
does not integrate imputation uncertainty inside one Bayesian posterior, and
the manuscript explicitly says so.

## Explainability protocol

- Select validation subjects with a recorded random seed and use the same
  subjects for every model in a paired comparison; never use the first rows
  of a file.
- Draw each SHAP background from the corresponding training fold.
- Compute exact interventional linear SHAP for the Bayesian posterior-mean
  risk model for the primary within-model comparison. Compute Cox PH linear
  SHAP from its frozen coefficient vector as a secondary comparison on the
  identical subjects/backgrounds. Forest SHAP is formally dropped before
  freeze because the immutable cells do not retain reproducible tree state and
  the explanation stage is forbidden to refit models.
- Use three SHAP seeds and nested validation/background budgets of 25/50,
  50/100 and 100/200 (capped by fold size). Successive grouped rankings must
  have Spearman correlation at least 0.95 and at least four common top-five
  groups; failure is reported rather than hidden.
- Aggregate encoded, raw/log and interaction terms into prespecified clinical
  source-variable groups before global ranking. For each validation subject,
  the intrinsic group score is the posterior mean absolute value of the signed
  sum of group-term contributions, $E_s|\sum_{j\in g}x_{ij}\beta_j^{(s)}|$;
  these exact full-posterior values are stored in each cell before any random
  explanation subset is selected. SHAP terms are likewise summed with their
  signs within subject and group before taking the mean absolute attribution.
- Estimate ranking uncertainty across folds/resamples.
- Never infer causality, feature truth, treatment benefit or clinical utility
  from posterior/SHAP agreement.

## Prespecified robustness analyses

- WHAS500 baseline-only primary versus the full published set including
  length of stay.
- METABRIC baseline-only primary versus treatment-augmented predictors.
- METABRIC stage-excluding primary versus the five-imputation fold-local stage
  sensitivity described above.
- NPI alone versus its tumour-size/grade/node components.
- Parsimonious predictors versus the currently engineered predictor set.
- Piecewise baseline hazards with 4, 6 and 10 intervals.
- Proportional-hazards tests use rank-transformed Schoenfeld residuals with
  Holm control within cohort/fold. The frozen response is to report supported
  violations as design limitations; no outcome-driven time interaction is
  added to the confirmatory models.
- Prior hyperparameter grid fixed before the confirmatory run.
- Training-size and administrative-censoring conditions from RQ2. RQ2 uses
  outer folds 1 and 2 in every repeat retained by the result-blind compute
  gate. Within each selected outer-training fold, event/time-stratified 25%,
  50%, 75% and 100% subsets are identical across priors. Administrative
  truncation is evaluated at the training-fold 75th and 50th follow-up
  quantiles at 100% training size, alongside observed follow-up; sample-size
  and censoring conditions are not crossed. A condition with fewer than 20
  training events fails explicitly. Each non-primary design condition, each
  non-primary feature condition and the five-imputation condition uses outer
  fold 1 in every retained repeat and is paired with the matching fold-1
  primary condition; the primary anchor is also retained on fold 2 for RQ2.

Uncertainty for RQ2 and the one-factor-at-a-time design/feature sensitivities
uses a paired three-stage bootstrap: outer repeats are resampled first, folds
are resampled within each selected repeat, and validation subjects are then
resampled within event-status strata using identical indices for both priors.
This preserves pairing while representing split-to-split as well as
subject-level variation. These sensitivity intervals remain descriptive and
do not create a second multiplicity-controlled confirmatory family.

Prior-scale sensitivity uses three prespecified joint scenarios. Relative to
the primary priors, the tighter scenario halves the Normal standard deviation,
horseshoe global/slab scales and spike/slab standard deviations; the wider
scenario doubles them. Shape parameters remain fixed. Baseline-hazard
resolution is evaluated with 4, 6 and 10 intervals. These grids estimate
design dependence and are never tuned to obtain a favourable result.

## Simulation and transport boundary

No simulation or cross-cohort transport result enters the thesis evidence.
This is a deliberate pre-freeze scope decision, not a failed analysis. The
real-data study estimates predictive and explanation behaviour in three
separate replication settings; it does not estimate coefficient-recovery
truth and does not externally validate one locked clinical model.

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
- [ADEMP](https://doi.org/10.1002/sim.8086) is retained only as reporting
  guidance for future simulation work; no simulation is part of this study.

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
| G2 data | 2026-09-13 | Pinned manifests/hashes/licences, rebuilt METABRIC and baseline-predictor audit pass; optional transport permanently dropped |
| G3 design complete | 2026-09-27 | Fold-local pipeline, metrics/calibration, paired artefact schema, DeepSurv decision, full diagnostics and clean tests pass |
| G4 protocol freeze | 2026-10-11 | One-fold-per-cohort rehearsal passes; runtime decision made without inspecting confirmatory effects; protocol/config tagged |
| G5 confirmatory complete | 2026-11-08 | Every planned cell is accounted for; no diagnostically invalid fit is interpreted, and any retained failure is excluded and reflected in the completeness gates |
| G6 robustness/evidence freeze | 2026-12-06 | Sensitivities and explainability complete; result manifest tagged; optional simulation remains permanently dropped |
| G7 full thesis draft | 2026-12-20 | Every chapter substantive; tables generated; no thesis-critical unverified claim |
| G8 examiner ready | 2027-01-17 | Statistical, citation, ethics, TRIPOD+AI/PROBAST+AI, reproducibility and clean-build reviews pass |
| G9 thesis delivered | 2027-01-24 | University-format thesis/source/archive submitted, leaving three weeks of contingency |
| G10 paper package | 2027-02-14 | Journal manuscript, supplement, checklist, declarations, cover letter and permissible reproducibility archive ready |

No unprespecified model family, prior, dataset or analysis may enter after G4.
The pre-freeze decisions dropping transport and simulation are irreversible
within this study and cannot be reopened after comparative results are seen.

## Drop rules and definition of done

If a gate slips by more than one week, the already-dropped transport and
simulation branches stay out; then drop additional SHAP case studies and
non-primary sensitivity grid points. Never drop fold-local preprocessing,
data provenance, calibration, full Bayesian diagnostics, claim verification,
the baseline-predictor audit, the primary robustness analyses or thesis build
quality.

The thesis is done only when all research questions are answered with either
supported findings or explicit negative/uncertain results, every submitted
claim is verified, all headline values trace to immutable artefacts, the
named environment reproduces the analysis, and a clean LaTeX build has zero
undefined references or citations.
