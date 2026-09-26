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

- Status: SUPERSEDED-BY-ADR-026
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
  heart-attack file was intended to cover; GBSG2 adds a second breast-cancer
  cohort with 686 records and 299 events. All three have documented public
  samples and published source descriptions, making provenance and benchmark
  comparisons auditable without asserting a power calculation.
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

- Status: SUPERSEDED-BY-ADR-027
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

- Status: SUPERSEDED-BY-ADR-028
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

- Status: SUPERSEDED-BY-ADR-015
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

- Status: SUPERSEDED-BY-ADR-024
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
  family would fragment the limited fold-level information into a large,
  difficult-to-interpret multiplicity family.
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

- Status: SUPERSEDED-BY-ADR-024
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

## ADR-020 — Owner approvals are recorded without invented identifiers

- Status: ACCEPTED
- Date: 2026-08-15
- Context: The owner approved the ethics/data-use, licensing and supervisor-
  decision tracks and directed that these matters not be raised again. No
  institutional ethics reference number or approval-letter identifier was
  supplied.
- Decision: Treat Q-002, Q-003 and Q-004 as answered. State the approved
  secondary, public/de-identified data-use position and conservative source-
  licence handling, but never invent an ethics number, letter, reviewer or
  signature. Exact source limitations remain reportable scientific facts.
- Consequences: Administrative work does not block engineering or writing.
  The thesis can accurately state owner-confirmed approval, but cannot cite a
  nonexistent institutional reference.

## ADR-021 — Parsimonious baseline feature sets are primary

- Status: ACCEPTED
- Date: 2026-08-15
- Context: Post-baseline predictors, NPI/component redundancy, raw/log copies
  and interactions could inflate apparent prediction and confound prior and
  feature-ranking comparisons.
- Decision: Use eight documented raw GBSG2 variables; nine admission-available
  WHAS500 variables excluding `los`, `afb`, `sho`, `chf` and `av3`; and a
  METABRIC baseline-pathology set containing age, NPI and six categorical
  pathology/receptor/subtype variables. No engineered feature is primary.
  Published-full, engineered, NPI-component, stage and treatment-augmented
  sets are named sensitivities. METABRIC confirmatory input is the pinned
  1,980-person/1,144-death cBioPortal derivation, never the pilot subset.
- Consequences: Primary prediction and explanation claims no longer depend on
  readily avoidable timing leakage or duplicate representations. Published-
  feature comparability moves to transparent sensitivity analyses.

## ADR-022 — Exact lock and content-addressed protocol freeze

- Status: ACCEPTED
- Date: 2026-08-15
- Context: A dirty working tree can still be made exactly reproducible when
  every executed input is content-addressed; requiring an unrequested git
  commit would mix implementation delivery with repository-history policy.
  The previous conda solve also paired h5py built for HDF5 2.1 with runtime
  HDF5 2.2.
- Decision: Pin every direct dependency, HDF5 2.1.0 and h5py 3.16.0; use the
  hashed osx-arm64 conda lock and a fresh verified environment. After the
  result-blind rehearsal, freeze hashes of every executed code, config,
  protocol, lock, manifest and data input in `config/protocol_freeze.json`.
  Confirmatory execution refuses any hash mismatch. Git commit/dirty state is
  still recorded but is not a substitute for the content check.
- Consequences: Confirmatory cells cannot silently combine different inputs,
  even before the owner chooses how to commit the work. Re-freezing after
  seeing comparative effects is prohibited.

## ADR-023 — Prespecified Bayesian remedies and lean information analysis

- Status: ACCEPTED
- Date: 2026-08-15
- Context: Full robustness over every fold, fraction and censoring factorial
  would exceed a master's-thesis compute budget, while vague remedies permit
  result-dependent sampler changes.
- Decision: A failed Bayesian cell receives at most two refits: target
  acceptance 0.99 with doubled tuning, then the same settings plus an
  equivalent non-centred baseline log-hazard parameterisation. RQ2 uses outer
  folds 1 and 2 from each repeat, paired 25/50/75/100-percent training subsets,
  and two training-derived administrative truncations at full size; sample-
  size and censoring conditions are not crossed. Prior scales use frozen
  half/default/double scenarios and baseline hazards use 4/6/10 intervals.
- Consequences: Failure handling and sensitivity scope are executable before
  results exist. The lean RQ2 estimates information-regime interaction with
  explicit uncertainty but is not presented as a universal asymptotic law.

## ADR-024 — Frozen-cell linear SHAP; forest SHAP dropped

- Status: ACCEPTED
- Date: 2026-08-15
- Context: The primary explanation target is a posterior-mean linear risk
  function, for which interventional linear SHAP is exact. Confirmatory cells
  retain Bayesian and Cox coefficients but deliberately do not pickle forest
  objects; refitting in a reporting script would break immutable lineage.
- Decision: Compare posterior expected absolute contribution with exact SHAP
  on the same Bayesian model using three paired random seeds and nested
  subject/background budgets. Retain exact Cox linear SHAP as a secondary
  no-refit comparison. Formally drop confirmatory forest SHAP and make no
  DeepSurv explanation claim. The earlier pilot forest Kernel-SHAP artefact
  remains exploratory only.
- Consequences: RQ3 measures model-conditional rank agreement and stability
  with reproducible frozen state. It does not make a broader cross-model-
  explanation claim that the stored evidence cannot support.

## ADR-025 — Optional transport and simulation are permanently dropped

- Status: ACCEPTED
- Date: 2026-08-15
- Context: Rotterdam-to-GBSG2 transport and a lean ADEMP simulation were
  publication-enhancing options, not requirements for the approved research
  questions. The retained confirmatory analysis already includes three
  cohorts, 450 primary model-fold cells at five repeats, and a prespecified
  robustness plan of 825 checkpoint cells/885 Bayesian fits before any
  diagnostic refits. Either optional branch would consume the contingency
  needed for a six-month master's thesis without repairing a gap in a retained
  claim.
- Decision: Permanently exclude Rotterdam transport and the ADEMP simulation
  from this study before protocol freeze. Do not acquire, harmonise or analyse
  a fourth cohort and do not generate simulation results for the thesis or
  paper. This supersedes only the optional-branch provisions of ADR-016 and
  ADR-019; their three-cohort core and six-month controls remain binding.
  Treat transport validation and coefficient-recovery simulation as future
  work only; they cannot be reopened after comparative results are observed.
- Consequences: The study remains a three-cohort internal, repeated-CV
  methodological benchmark and makes no external-validation or coefficient-
  recovery claim. Compute and writing capacity remain available for required
  calibration, diagnostics, robustness, explanation, reproducibility and
  thesis review.

## ADR-026 — Exact locked runtime and result-reproduction boundary

- Status: ACCEPTED
- Date: 2026-08-15
- Context: ADR-003 named the mutable `bayes-cox` environment and claimed that
  a clean clone reproduced results. The named environment is not equivalent to
  the resolved lock because its PyTorch installation route differs, and no
  frozen confirmatory result yet exists to reproduce.
- Decision: Execute official verification and analysis with the environment
  created from the hashed osx-arm64 lock, currently
  `bayes-cox-lock-verify-20260815-b`, and verify all 259 locked records before
  use. A clean checkout plus pinned inputs establishes a reproducible workflow;
  a result-reproduction claim is permitted only after the frozen production
  artefacts have been independently regenerated and checksum-verified. This
  supersedes ADR-003 and complements the content-addressed freeze in ADR-022.
- Consequences: The mutable environment name is never treated as evidence of
  dependency identity. Current claims are limited to environment and workflow
  verification, not reproduction of confirmatory results that do not yet
  exist.

## ADR-027 — Zero-divergence confirmatory interpretation gate

- Status: ACCEPTED
- Date: 2026-08-15
- Context: ADR-007 allowed divergent transitions below 0.5% while calling a
  fit converged. That tolerance is inconsistent with the implemented
  confirmatory quality gate and would permit an avoidable sampler warning to
  enter interpreted evidence.
- Decision: Retain NUTS as the confirmatory sampler and compute diagnostics
  from every sampled variable with ArviZ. An interpreted Bayesian cell must
  have zero divergent transitions, maximum rank-normalised R-hat below 1.01,
  minimum bulk ESS above 400, BFMI at least 0.30 in every chain, and no maximum
  tree-depth hit. Apply only the two prespecified remedies in ADR-023; preserve
  a failed-cell record if the gate still fails. Historical pilot divergences
  remain historical observations, not acceptable confirmatory fits. This
  supersedes ADR-007.
- Consequences: “Converged” has a stricter executable meaning. A cell may be
  unavailable for interpretation even when its point prediction was produced,
  and no post-result sampler tuning is allowed.

## ADR-028 — No cross-domain generalisation claim

- Status: ACCEPTED
- Date: 2026-08-15
- Context: ADR-010 proposed one generalisation statement beyond healthcare
  even though every cohort, endpoint and empirical evaluation is clinical.
  Mathematical applicability alone is not evidence of predictive performance,
  robustness or transportability in another domain.
- Decision: Restrict all empirical and methodological claims to the evaluated
  healthcare survival-analysis setting and the three named cohorts. Do not
  claim cross-domain generalisability, performance or transportability. Work
  outside healthcare requires new data, validation and a separately frozen
  protocol. This supersedes ADR-010.
- Consequences: The thesis may describe the proportional-hazards equations,
  but it cannot convert their abstract form into evidence about another
  application domain.

## ADR-029 — Retain five outer repeats after the result-blind compute rehearsal

- Status: ACCEPTED
- Date: 2026-08-15
- Context: The approved design permits reducing five outer repeats to three
  only when the conservative planned-five serial-runtime projection exceeds
  72 hours. The fresh predecision rehearsal completed all 18 cohort/model cells
  with the exact 300/300/two-chain/30-bootstrap workload. Only console status
  and timing were inspected. The rounded cell times sum to 196.1 seconds; even
  assigning every value its maximum rounding error yields a planned-five
  projection below 22.81 hours.
- Decision: Retain the approved five repeats and set
  `design_status: frozen_after_rehearsal`. Run a second exact rehearsal under
  the final inputs and require the freezer to recompute the decision from the
  unrounded archived timings before creating the write-once content freeze.
  No performance, calibration, inference, prediction, or explanation value is
  inspected before that freeze.
- Consequences: Three repeats are not permitted on the observed timing
  evidence. If the final exact rehearsal unexpectedly changes the gate result,
  no freeze is created until the configuration and a fresh final rehearsal
  agree with the deterministic rule.

## ADR-030 — Frozen evidence is verified against its checkpoint commit

- Status: ACCEPTED
- Date: 2026-09-27
- Context: `verify_run_inputs_unchanged` compares the 80 frozen inputs with
  the live working tree. The inputs include every `src/**/*.py`, the Makefile
  and this decision log. Under that rule the code can never be simplified or
  documented, and no decision can be recorded, without making the completed
  evidence unverifiable. The student could not follow the code in its frozen
  form. All 80 inputs are stored byte-for-byte in commits `95af081` and
  `44b6085`; the evidence Release is attached to `44b6085`.
- Decision:
  - Verify frozen confirmatory and robustness evidence against the input
    blobs stored in checkpoint commit `44b6085`, not the working tree.
  - The protocol-defining inputs keep their frozen content in the live tree:
    `config/confirmatory.yaml`, `config/datasets.yaml`,
    `config/protocol_freeze.json`, `data/raw/*`, `data/manifest.yaml` and
    the lock files.
  - Code and documentation may change. Code changes must preserve behaviour,
    demonstrated by regenerating frozen cells with
    `scripts/reproduce_confirmatory_cells.py` and matching every stored field
    except wall-clock timings.
- Consequences:
  - The evidence stays verifiable after the code changes.
  - Confirmatory execution itself is closed. New analyses are post-hoc,
    carry their own manifests and are labelled as such.
  - A full regeneration of the 450 cells with the refactored code is also
    the reproduction required by ADR-026.

## ADR-031 — Sharded execution of the frozen robustness plan

- Status: ACCEPTED
- Date: 2026-09-27
- Context: The frozen robustness runner is serial. Its plan (825 cells, 885
  Bayesian fits) was projected at 69.6 hours, just under the 72-hour limit.
  Each cell depends only on its own deterministic seeds, and the runner skips
  cells whose files already exist.
- Decision:
  - Run the unmodified frozen runner in six worker processes
    (`~/bayes-cox-runs/harness/shard_worker.py`). Each worker claims a cell
    with an atomic lock file outside the run directory before fitting it, and
    stops before aggregation.
  - A final unsharded `--resume` invocation verifies the freeze, fits any
    missing cell, and writes the aggregates and completion record.
- Consequences:
  - Wall time falls to roughly a sixth of the serial time.
  - Cell content does not depend on which process fitted the cell: a sharded
    cell refitted in a fresh process matched in every field except timings.
  - The run manifest records the runner command. The worker harness is kept
    beside the run and described here.

## ADR-032 — Post-hoc horseshoe sampler sensitivity

- Status: ACCEPTED
- Date: 2026-09-27
- Context:
  - 20 of 75 confirmatory horseshoe cells failed the zero-divergence gate:
    18 in GBSG2 and 2 in METABRIC, each with 1–11 divergences per 8,000 draws
    and every other diagnostic passing. As a result, four of the nine primary
    contrasts have no inference.
  - The ADR-023 remedies do not alter the horseshoe's sampling: it already
    used target acceptance 0.99, and the second remedy changes only the
    baseline parameterisation.
  - On the frozen seeds, target acceptance 0.999 cleared 6 of 7 failed GBSG2
    cells.
- Decision:
  - Refit all 75 horseshoe cells with the frozen folds, seeds, model, priors
    and gate, changing only target acceptance to 0.999 for every attempt.
    Keep the same remedy ladder.
  - Store the refits in a separate post-hoc run directory, and estimate all
    nine prior contrasts against the unchanged frozen normal and
    spike-and-slab cells.
  - Label every result a post-hoc sampler sensitivity. It never replaces the
    confirmatory outcome, which remains "five of nine contrasts estimable".
- Consequences:
  - The sensitivity shows whether the incomplete family hides a prior
    effect, without selecting cells: all 75 are refitted, not only the
    failures.
  - Remaining failures are reported, not remedied further.

## ADR-033 — Post-hoc bound on the incomplete Holm family

- Status: ACCEPTED
- Date: 2026-09-27
- Context: The frozen inference applies Holm only when all nine primary
  contrasts are estimable, so the confirmatory record gives no multiplicity
  statement at all.
- Decision:
  - Report, for each estimable contrast, whether Holm rejection at
    family-wise level 0.05 is possible in the most favourable case (every
    missing hypothesis rejected first) and guaranteed in the least favourable
    case (every missing p-value equal to 1).
  - Label this a post-hoc bound on the incomplete family, not a Holm-adjusted
    confirmatory result.
- Consequences: With the observed p-values (smallest 0.493 against a best-case
  threshold of 0.01), no estimable contrast can be rejected under any value of
  the four missing p-values.
