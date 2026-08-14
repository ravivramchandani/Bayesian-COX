# DECISIONS

Architecture decision records. One entry per non-trivial choice, numbered
monotonically. Past decisions are never edited; a decision that changes is
superseded by a new record.

Format:

```markdown
## ADR-NNN — <short title>
- Status: PROPOSED | ACCEPTED | DEPRECATED | SUPERSEDED-BY-ADR-XXX
- Date: <YYYY-MM-DD>
- Context: <why the decision is needed; what alternatives were considered>
- Decision: <what was chosen>
- Consequences: <what becomes true and what becomes harder>
```

---

## ADR-001 — Coordination layer

- Status: ACCEPTED
- Date: 2026-08-14
- Context: The project runs across many sessions and machines. Without durable
  written state, sessions re-derive decisions and drift apart.
- Decision: Keep binding state in `coordination/`: this file, `INVARIANTS.md`,
  `GLOSSARY.md`, `OPEN_QUESTIONS.md`, `TODO.md`, `JOURNAL.md`, and
  `PROTOCOL.md`. Every session reads them on entry.
- Consequences: Decisions are discoverable and auditable. The cost is that
  every non-trivial choice must be written down.

## ADR-002 — Autonomous execution; administrative matters run in parallel

- Status: ACCEPTED
- Date: 2026-08-14
- Context: A sibling project stalled because administrative dependencies —
  approvals, access, ethics, permissions — were written into its coordination
  layer as hard gates. Engineering waited on items that were never the
  implementer's to resolve.
- Decision: Implementation proceeds autonomously. Work stops only when a
  required file is genuinely unavailable or an irreversible external action
  needs the owner's decision. Approvals, access, credentials, ethics, and
  permissions belong to an owner-managed track recorded in
  `OPEN_QUESTIONS.md` under "Owner track"; they are raised once and never
  used to pause engineering. An open question blocks only its exact final
  deliverable, not the preparatory work around it.
- Consequences: Progress does not depend on approval latency. Deliverables
  that genuinely need an external input are identified individually and
  everything else around them is built in advance.

## ADR-003 — Runtime and environment

- Status: ACCEPTED
- Date: 2026-08-14
- Context: Reproducibility requires a fixed runtime. PyMC, scikit-survival and
  lifelines constrain the usable Python version.
- Decision: Python 3.11 via conda, specified in `environment.yml` and
  mirrored in `pyproject.toml`. The environment is named `bayes-cox`.
- Consequences: A clean clone on a matching runtime reproduces the results.
  Changing the runtime requires a superseding record.

## ADR-004 — Benchmark cohorts

- Status: ACCEPTED
- Date: 2026-08-14
- Context: The proposal named METABRIC, a Kaggle heart-attack file, and a
  lung-cancer extract. Inspection confirms the heart-attack file has no
  time-to-event column and cannot support survival analysis, and the
  lung-cancer extract holds 80 rows.
- Decision: Use METABRIC (primary), WHAS500, and GBSG2, following the
  agreed methodology. WHAS500 supplies the cardiology cohort the
  heart-attack file was intended to cover; GBSG2 supplies a properly powered
  second cohort. All three have published baselines that make replication
  checkable.
- Consequences: Every cohort carries genuine time-to-event data with
  censoring. The proposal text differs; ADR-011 records how that is carried.

## ADR-005 — Real data only; no synthetic fallback

- Status: ACCEPTED
- Date: 2026-08-14
- Context: The dataset script previously generated synthetic data whenever
  scikit-survival failed to import, with outcomes drawn independently of the
  covariates. Every committed result was produced from that data, and the
  failure was silent.
- Decision: `scripts/download_datasets.py` loads GBSG2 and WHAS500 from
  scikit-survival and derives METABRIC from the clinical export. A missing
  source raises. No code path fabricates observations.
- Consequences: A broken environment fails loudly instead of producing
  plausible but meaningless results. INV-001 enforces this at test time.

## ADR-006 — Baselines use the established libraries

- Status: ACCEPTED
- Date: 2026-08-14
- Context: Cox PH, the random survival forest, and the concordance index were
  each reimplemented by hand and never validated against a reference. The
  hand-written concordance index disagreed with scikit-survival by up to
  0.003 through differing tie handling.
- Decision: Cox PH uses lifelines, the random survival forest uses
  scikit-survival, and all metrics delegate to scikit-survival, as the
  proposal specified. The Bayesian Cox model remains the project's own
  implementation because it is the contribution.
- Consequences: Baseline numbers are comparable with published work and the
  reimplementation risk is confined to the contribution.

## ADR-007 — Bayesian inference: NUTS with reported diagnostics

- Status: ACCEPTED
- Date: 2026-08-14
- Context: The model defaulted to variational inference, and the convergence
  diagnostics were stubs returning fixed passing values regardless of the
  fit. The agreed methodology requires PyMC with NUTS and reported R-hat,
  effective sample size, divergent transitions, and trace plots.
- Decision: NUTS is the default. Diagnostics are computed from the trace with
  arviz. A fit is reported as converged only when R-hat < 1.01, bulk
  effective sample size > 400, and divergent transitions are under 0.5% of
  draws. Variational inference remains available for exploration and reports
  no sampler diagnostics.
- Consequences: Convergence claims are verifiable. Poorly behaved posteriors
  surface rather than being hidden.

## ADR-008 — Coefficient priors

- Status: ACCEPTED
- Date: 2026-08-14
- Context: The model implemented Normal, Student-t and Laplace priors. The
  agreed methodology calls for a weakly-informative baseline plus two
  sparsity-inducing priors whose posteriors serve as the explainability
  signal.
- Decision: Support three priors — weakly-informative Normal, regularised
  horseshoe, and a continuous relaxation of spike-and-slab. A discrete
  inclusion indicator cannot be sampled by NUTS, so the spike-and-slab uses a
  continuous inclusion weight mixing a narrow spike with a wide slab
  variance, and the posterior mean of that weight is the inclusion signal.
- Consequences: The priors match the methodology. The plain horseshoe
  produced 208 divergent transitions on GBSG2; the regularised form reduced
  that to one.

## ADR-009 — Deep-learning arm is DeepSurv

- Status: ACCEPTED
- Date: 2026-08-14
- Context: The deep-learning comparator could be DeepSurv or DeepHit. DeepHit
  models competing risks with a discrete-time likelihood; DeepSurv optimises
  the Cox partial likelihood with a neural risk function.
- Decision: DeepSurv. All three cohorts record a single event type with right
  censoring, so there are no competing risks for DeepHit to model. DeepSurv
  also shares the proportional-hazards structure of the Cox and Bayesian Cox
  arms, which keeps the comparison about the risk function rather than about
  differing likelihoods.
- Consequences: The benchmark isolates what the neural model adds over a
  linear risk function. Competing risks are out of scope; adding them later
  would require a cohort that records cause of failure.

## ADR-010 — Scope is healthcare survival analysis

- Status: ACCEPTED
- Date: 2026-08-14
- Context: A broader framing spanning other domains was considered. All
  implemented work, every cohort, and every evaluation choice is clinical.
- Decision: Scope the work to healthcare survival analysis. The methods
  generalise to any right-censored time-to-event problem, which is stated
  once as a generalisation claim rather than pursued with additional data.
- Consequences: A single coherent evaluation story. Claims about other
  domains are not made, so none need supporting evidence.

## ADR-011 — Proposal deviations are carried in the thesis

- Status: ACCEPTED
- Date: 2026-08-14
- Context: The cohorts, priors, sampler, and model roster differ from the
  approved proposal, for the technical reasons recorded in ADR-004, ADR-007
  and ADR-008. The alternative was maintaining a separately revised proposal
  document.
- Decision: The thesis carries the deviations, with the rationale in the
  methodology chapter and the full comparison in
  `docs/proposal_deviations.md`. No parallel proposal revision is maintained.
- Consequences: One authoritative document. Each deviation is justified where
  a reader encounters it rather than in a separate file they may not read.

## ADR-012 — Length of stay retained in the WHAS500 covariates

- Status: ACCEPTED
- Date: 2026-08-14
- Context: `los` is recorded at the index admission but resolves after
  follow-up begins, so it could carry outcome information. It is part of the
  standard scikit-survival feature set that published baselines use.
- Decision: Retain it in the primary model so the results stay comparable
  with published WHAS500 baselines, and run a sensitivity fit without it in
  Phase 3 (T-032). If removing it changes concordance materially, the
  sensitivity result becomes the headline and this record is superseded.
- Consequences: Comparability now, with the leakage question settled by
  measurement rather than assumption.

## ADR-013 — Explainability comparison

- Status: ACCEPTED
- Date: 2026-08-14
- Context: The explainability module was empty although a report describing
  its findings existed.
- Decision: Compare the built-in posterior signal against post-hoc SHAP
  computed on the Cox PH and random survival forest baselines. SHAP uses a
  kernel explainer over each model's risk prediction so the method is
  identical across models. Agreement is reported as Spearman and Kendall rank
  correlation plus top-k overlap.
- Consequences: The explainability claim is measured rather than asserted.

## ADR-014 — Existing results are exploratory; repeated nested CV is confirmatory

- Status: ACCEPTED
- Date: 2026-08-14
- Context: The current holdout has been inspected and used to interpret model
  behaviour. Cross-validation uses data preprocessed on the full training
  split, selects evaluation horizons from test outcomes, and stores only
  aggregate mean and standard deviation. It cannot support the planned paired
  confirmatory inference.
- Decision: Preserve the current 15 fits and 18 explanation comparisons as
  exploratory pilot evidence. The primary analysis is five repeats of
  five-fold outer cross-validation with all preprocessing and horizon choice
  fitted inside each outer-training fold. Compact random-forest and DeepSurv
  tuning occurs in three inner folds. Per-subject out-of-fold predictions and
  per-fold metrics are retained. A result-blind compute rehearsal may reduce
  the repeats to three before confirmatory effects are inspected.
- Consequences: No untouched holdout claim is made. The confirmatory analysis
  is paired and reproducible but materially more expensive. Pilot values can
  motivate hypotheses and check code, not establish superiority.

## ADR-015 — Prediction times and baseline-only primary predictors

- Status: ACCEPTED
- Date: 2026-08-14
- Context: Prediction time was not defined. WHAS500 length of stay resolves
  after admission, while METABRIC surgery and treatment-received variables
  occur after diagnosis. Including them in a baseline clinical-prediction
  model risks post-baseline information leakage. ADR-012 retained length of
  stay as primary for published comparability.
- Decision: The primary WHAS500 target is admission-time mortality prediction
  and excludes length of stay plus any complication not verified as available
  at admission. The intended primary METABRIC target uses diagnosis/pathology
  variables available before adjuvant treatment and excludes surgery type and
  treatment received unless a defensible timing audit establishes otherwise;
  its exact survival time origin must be verified before that label is used.
  Full published/augmented feature sets are comparability sensitivities. This
  decision supersedes ADR-012.
- Consequences: The primary claims have a clear intended prediction time and
  avoid readily fixable leakage. Some performance may fall and direct
  comparison with published full-feature baselines moves to sensitivity
  analysis. The historical T-032 referenced by ADR-012 is replaced by T-142.

## ADR-016 — Confirmatory data sources; no fourth core cohort

- Status: ACCEPTED
- Date: 2026-08-14
- Context: GBSG2 and WHAS500 are reproducible from scikit-survival. The active
  1,904-row Kaggle METABRIC source omits 77 otherwise eligible positive-time
  survival records and 41 deaths relative to the 2,509-row cBioPortal clinical
  export already stored with the proposal. A new dataset would add work while
  calibration, robustness, governance and thesis writing remain unfinished.
- Decision: Pin GBSG2 and WHAS500 to an exact scikit-survival source release.
  Rebuild confirmatory METABRIC from cBioPortal DataHub commit
  `165bd77077b03038f9c2ee104959eb474770b2a9`, expecting 1,980 positive-time
  records and 1,144 deaths. Keep the Kaggle subset only for pilot
  reproducibility. Add no fourth independently refitted core cohort. A locked
  Rotterdam-to-GBSG2 transport evaluation is optional only if the Week 4 gate
  verifies licence, endpoint/predictor compatibility and schedule.
- Consequences: The core is feasible with locally and publicly available data
  and METABRIC selection becomes auditable. All existing METABRIC performance
  numbers remain exploratory and must be rerun. Multi-cohort fitting is called
  benchmarking, not external validation.

## ADR-017 — Primary estimands, calibration and inference

- Status: ACCEPTED
- Date: 2026-08-14
- Context: Harrell's C-index is optimistic under heavy censoring, IBS is
  incorrectly labelled calibration, actual calibration is unwired, and a
  statistics stub returns a constant p-value. An unrestricted all-pairs test
  family would be underpowered and difficult to interpret.
- Decision: IPCW IBS is the primary probabilistic-error estimand and Uno's
  IPCW C-index the primary discrimination estimand. Calibration requires
  curves plus calibration intercept/calibration-in-the-large and slope at
  training-defined horizons. The primary inferential family is the three
  pairwise Bayesian-prior contrasts within three cohorts, with Holm control.
  Repeated-CV effects use a prespecified corrected paired procedure and a
  paired out-of-fold bootstrap sensitivity. Cox, forest and DeepSurv contrasts
  are secondary and estimation-led.
- Consequences: “Calibration,” “superior,” “equivalent” and “robust” have
  explicit evidence gates. Existing mean/standard-deviation summaries and the
  comparable-pair standard error are descriptive only. The stubbed
  permutation result cannot enter any report.

## ADR-018 — Explanation target is model-conditional stability

- Status: ACCEPTED
- Date: 2026-08-14
- Context: Current agreement compares posterior probability-of-direction
  rankings with SHAP from other model families on the first 40 test rows.
  Probability of direction, coefficient magnitude, prior-specific shrinkage
  and SHAP attribution are different constructs, while raw/log duplicates and
  encoded levels fragment one clinical concept.
- Decision: Use posterior expected absolute contribution as the common primary
  Bayesian importance, compute SHAP on the same posterior-mean Bayesian risk
  model for the primary comparison, and retain Cox/forest SHAP as secondary
  cross-model comparisons. Subjects and backgrounds are sampled within folds
  with recorded seeds. Importance is grouped by source variable and stability
  is estimated across folds, subjects and SHAP seeds. Prior-specific
  shrinkage/mixing weights remain secondary signals.
- Consequences: The thesis can claim measured rank agreement and stability,
  not explanatory truth, causality or clinical usefulness. The continuous
  mixing weight is never called a discrete posterior inclusion probability.

## ADR-019 — Six-month scope and publication target

- Status: ACCEPTED
- Date: 2026-08-14
- Context: A high-quality paper benefits from robustness, transparent
  reporting and reproducibility, but a master's thesis has a fixed six-month
  window. Adding datasets, priors and models can delay the evidence and the
  largely unwritten thesis.
- Decision: Run the 26-week programme in `TODO.md`, targeting an examiner-ready
  thesis by Week 22, thesis delivery in Week 23 and a journal package by Week
  26. Thesis-essential work takes priority. Optional external transport and a
  lean ADEMP simulation are admitted only at their written gates. No new model
  family, prior, real dataset or analysis enters after the Week 8 protocol
  freeze. Reporting follows TRIPOD+AI and is audited with PROBAST+AI.
- Consequences: The work targets Q1-journal quality but does not promise a Q1
  ranking or acceptance. When a gate slips, optional transport, simulation and
  non-primary explanation work are dropped before any integrity, thesis or
  reproducibility requirement.
