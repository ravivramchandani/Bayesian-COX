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

## ADR-034 — Retire the pilot execution lane and preserve its evidence

- Status: ACCEPTED
- Date: 2026-09-27
- Context: The six pilot scripts and pre-generated processed splits form a
  second execution path. Default Make targets can overwrite tracked historical
  pilot results. Several model and integration tests still depend on those
  splits, although the active study uses paired, fold-local raw-cohort inputs.
  The code/results continuation programme explicitly includes pilot retirement.
- Decision:
  - Remove the pilot entry points and their exclusively used modules, unused
    pipeline/loss/likelihood stubs and unused utility shells from active code.
  - Preserve historical raw/processed data, reports and figures in place and
    preserve the retired source through Git history, including checkpoint
    `44b6085`. No historical number is recalculated or overwritten.
  - Migrate data, model and integration tests to authoritative raw cohorts,
    paired survival folds and training-fitted preprocessing. Retain functional
    statistical and metric utilities with real callers and meaningful tests.
  - Make the default workflow verify the environment, tests and lint. Dataset
    preparation only acquires/verifies the authoritative raw cohorts. Analysis
    and rendering require explicit current entry points and output locations.
- Consequences: There is one active study pipeline. Historical pilot evidence
  stays accessible but cannot accidentally be regenerated as current evidence.
  INV-002, INV-003, INV-006 and INV-007 are restated around active fold-local
  tests and hashed result lineage; their integrity requirements are retained.

## ADR-035 — Post-hoc extension for a Q1 journal paper

- Status: SUPERSEDED-BY-ADR-036
- Date: 2026-09-27
- Context: The owner's target is a Q1 journal paper. The frozen analysis
  detects no statistically significant IBS difference among the five
  estimable primary prior contrasts; four contrasts are unavailable. This
  does not establish equivalence or absence of a prior effect. The proposed
  extension addresses three scientific questions:
  - whether Bayesian shrinkage beats frequentist penalised Cox;
  - whether the result changes in the high-dimensional setting that
    shrinkage priors are designed for;
  - what clinical net benefit the predictions carry.

  The hard scope control in `TODO.md` forbids new model families, datasets or
  analyses after the freeze, so this record is needed before any addition.
- Decision:
  - Add four clearly labelled post-hoc analyses on the frozen outer folds:
    1. ridge, lasso and elastic-net Cox comparators with inner-CV penalties;
    2. a Piironen–Vehtari regularised horseshoe variant (half-Cauchy local
       scales, τ0 from the expected number of relevant predictors) as a
       prior-specification sensitivity;
    3. decision curve analysis at the three training-defined horizons, from
       stored out-of-fold predictions without refitting;
    4. a METABRIC clinical-plus-gene-expression setting from the pinned
       cBioPortal study.
  - Before any extension result is computed, specify every setting,
    hypothesis, metric and inference rule and freeze the addendum's hash.
    ADR-036 sets the current path to `docs/protocol_addendum_extensions.md`;
    ADR-037 refines its design and chronology.
  - This supersedes the first hard scope control for these four named
    analyses only. Rotterdam transport and the simulation study remain
    dropped under ADR-025.
- Consequences:
  - The confirmatory record stays the primary evidence and is never
    overwritten.
  - The extensions are reported as prespecified post-hoc analyses, frozen
    before their own results, and their outputs live in separate run
    directories.
  - Only a new ADR can add further analyses.

## ADR-036 — Extension experiments are thesis evidence; the paper is deferred

- Status: SUPERSEDED-BY-ADR-044
- Date: 2026-09-27
- Context: The owner wants the thesis itself to contain every experiment a
  Q1 journal paper would need. The paper is to be drafted after the thesis.
- Decision:
  - The four post-hoc analyses defined in ADR-035 are thesis experiments:
    1. the penalised Cox comparators;
    2. the Piironen–Vehtari horseshoe variant;
    3. decision curve analysis;
    4. the METABRIC clinical-plus-expression setting.
  - So are the ADR-032 horseshoe sampler sensitivity and the ADR-033 Holm
    bound.
  - The separation rules of ADR-035 still apply:
    - the four new analyses are specified in a frozen addendum before their
      own results exist (`docs/protocol_addendum_extensions.md`);
    - ADR-032 and ADR-033 retain their actual earlier specification and
      result chronology; the new addendum cannot retrospectively make
      existing probes or the computed Holm bound result-blind;
    - each is labelled post-hoc;
    - each is stored in its own run directory;
    - the frozen confirmatory record stays primary.
  - Journal drafting, submission and archival DOI minting (T-170–T-174,
    T-187, T-188) are deferred until after the thesis is submitted.
- Consequences:
  - The results chapter covers the confirmatory analysis, robustness,
    explanation and the extension experiments.
  - The thesis provides the planned evidence base for the later paper.
    Journal review may require further separately documented analyses;
    this plan does not guarantee Q1 acceptance.
  - Thesis text in the Overleaf repository is still edited only on the
    owner's instruction.

## ADR-037 — Refine the thesis extension design and preserve its chronology

- Status: ACCEPTED
- Date: 2026-09-27
- Context: The owner requested planning and coordination updates following
  the scientific review of ADR-036. The four new analyses are not running.
  The ADR-033 bound is already computed and rendered, and seven ADR-032
  sampler probes already exist. Their chronology must remain explicit.
- Decision:
  - Frame the extension around when Bayesian shrinkage improves survival
    prediction or decision value beyond tuned penalised Cox, and how this
    depends on dimensionality, prior specification and sampling reliability.
    The contribution is the systematic comparison, not a claim of a new
    shrinkage algorithm or a universal Q1 experiment checklist.
  - Freeze settings, comparison families, multiplicity, dependency-aware
    inference, exclusions and claim rules for the four new analyses in
    T-180 before producing their own results. Reference ADR-032/ADR-033 and
    existing evidence with their actual dates. The current core programme
    and its ADR-032 sensitivity do not depend on this new addendum.
  - Compare penalised Cox and Bayesian models on the same eligible patients,
    frozen outer folds and evaluation rules. Tune penalties by inner CV;
    fit imputation, scaling and feature selection inside the relevant
    training split, including inner CV. Freeze the comparison family and
    report effects, uncertainty, diagnostic attrition and paired coverage.
    Outer-test performance cannot select a favourable configuration.
  - Specify the Piironen–Vehtari variant precisely. The existing model uses
    half-Student-t scales with two degrees of freedom and fixed global
    scale 0.1, rather than canonical half-Cauchy scales. The new variant is
    a joint prior-specification sensitivity: fix local/global/slab priors,
    expected relevant predictors and a scale calibration justified for the
    survival likelihood. Do not import the Gaussian regression scale rule
    without justification. Use comparable ADR-032 sampler settings and
    unchanged diagnostic gates to separate prior and sampler effects.
  - In the METABRIC extension, compare clinical-only and clinical-plus-
    expression models on the same expression-eligible patients and outer
    folds, with common endpoint and evaluation times. Refit matched clinical
    controls when eligibility differs from the original primary cohort.
    Audit pinned expression provenance, patient/sample alignment, duplicate
    handling and predictor timing; freeze the gene-filter/selection rule and
    feature budget. Selection and preprocessing stay inside training splits.
    Include penalised Cox, the three original priors and the new variant in
    both matched settings; report predictors and events as well as results.
  - Specify survival decision curves with a clinical action, threshold range,
    censoring estimator and support/exclusion rules. Preserve the actual
    training-defined horizons; do not present varying fold horizons as a
    fixed clinical time point. Handle repeated predictions from the same
    patient in the uncertainty procedure. Use stored out-of-fold predictions
    without refitting and report all specified available curves and coverage.
    Net benefit under these assumptions is not a clinical impact finding.
  - Preserve the incomplete original primary family and the failed original
    explanation-convergence gate. Neither a non-significant contrast nor a
    new extension permits equivalence, superiority or stable-explanation
    claims beyond its evidence. Runtime estimates require measured evidence;
    blind computational profiling must not select on outer-test performance.
- Consequences: T-180–T-186 implement these refinements without changing the
  frozen protocol, data, code or original results. Planning updates do not
  launch the four new experiments. Overleaf remains outside the authorised
  scope; journal drafting, submission and DOI minting remain deferred.
  Method references: [Piironen and Vehtari (2017)](https://arxiv.org/abs/1707.01694)
  for the regularised horseshoe and non-Gaussian calibration, and
  [Vickers et al. (2008)](https://link.springer.com/article/10.1186/1472-6947-8-53)
  for survival decision curves and uncertainty.

## ADR-038 — Cox catalytic prior as a post-hoc extension arm

- Status: ACCEPTED; methodological details refined by ADR-039
- Date: 2026-09-28
- Context:
  - Q-001 deferred the catalytic prior, to be reopened if the small-sample
    robustness analysis showed the existing priors degrading.
    `docs/study_protocol.md` (lines 69–70) excludes it unless a later,
    supervisor-approved decision reopens it.
  - The Cox catalytic prior is now published: Li and Huang (2026),
    Biometrics 82(1), ujag004, doi:10.1093/biomtc/ujag004. It extends the
    original catalytic prior of Huang et al. (2020, PNAS 117(22),
    doi:10.1073/pnas.1920913117).
  - The Cox version adds a down-weighted likelihood of synthetic data drawn
    from a simple model. Its evaluation covers simulations and one small
    cohort; no independent multi-cohort benchmark with IBS, calibration or
    repeated cross-validation exists.
  - It stabilises estimation where data are scarce relative to the number of
    predictors, the regime that RQ2 and the METABRIC expression setting
    test.
  - The supervisor approved adding it on 2026-09-28, before any RQ2
    robustness result had been inspected.
- Decision:
  - Add the Cox catalytic prior (Li and Huang, Eq. 7) as a prior on β,
    combined with the existing piecewise-exponential likelihood and sampled
    with NUTS under the unchanged ADR-027 gate. There are two Bayesian
    variants:
    - fixed total weight τ = p, the authors' small-sample recommendation;
    - the adaptive catalytic prior on (τ, β), with (α, γ) = (2, 1), the
      authors' default.
  - Also add the authors' weighted mixture estimator, with cross-validated
    τ, as a point-estimate comparator.
  - Generate synthetic data inside each outer training fold:
    - covariates resampled from each preprocessed training column's
      empirical marginal;
    - uncensored times from an exponential model fitted to the training fold
      on the model's time scale;
    - the fitted rate as the surrogate baseline hazard;
    - M = max(1,000, 4p);
    - seeds derived from the cell seed.
  - Before production, the prior log-density and the weighted mixture
    estimate must match the authors' reference implementation (R package
    `catalytic` or their published code) on a fixed test case.
  - Evaluate the arm wherever the other priors are evaluated: the 25 outer
    folds of each cohort, the RQ2 information-regime conditions and the
    METABRIC expression setting.
  - The exact settings are fixed in `docs/protocol_addendum_extensions.md`
    (T-180) before any catalytic result exists. Every result is labelled
    post-hoc.
  - Every ADR-037 refinement applies to this arm too:
    - same eligible patients, frozen outer folds and evaluation rules;
    - the weighted mixture estimator's τ tuned by inner CV only;
    - inclusion in both matched METABRIC settings;
    - no equivalence or superiority claim beyond its evidence.
  - This reopens Q-001 and supersedes the protocol's catalytic exclusion for
    this arm only; `docs/study_protocol.md` remains the unchanged historical
    plan.
- Consequences:
  - The thesis becomes the first independent, preregistered evaluation of
    the Cox catalytic prior across real cohorts and clinical metrics, next
    to parameter-space priors, penalised Cox and machine-learning
    comparators.
  - The prior is log-concave, so its compute cost is expected to be close
    to the normal prior's. It must be measured, not assumed.
  - The RQ2 conditions need new catalytic cells, because the frozen
    robustness run has no catalytic arm.

## ADR-039 — Verified implementation of the post-hoc extension programme

- Status: ACCEPTED
- Date: 2026-09-28
- Context: The owner requested a full, complete and verified implementation
  after review of ADR-036–ADR-038. Reference inspection identified invalid
  independent dummy resampling, adaptive-prior normalization and
  prior-predictive sampling hazards, an incomplete matched-model roster, and
  an unsupported novelty/preregistration claim.
- Decision:
  - Continue all authorised code/results extensions under one repository
    integration owner. External reference research may run independently;
    it does not edit the repository. Overleaf and paper/DOI work stay deferred.
  - The extension is an independent multi-cohort post-hoc evaluation. Neither
    a first-evaluation claim nor external preregistration is established.
    The earlier ADR-038 novelty/preregistration sentence is superseded.
  - Freeze the exact addendum and machine-readable settings before any new
    outer-validation result is computed. Training-only computational
    profiling, source alignment and executed reference fixtures are
    preparation, not extension outcome evidence. Record their chronology.
  - Generate categorical source levels before encoding, recompute derived
    features, and resample numeric source marginals. Learn the censored
    exponential generator within each relevant inner or outer training set.
    Require positive synthetic times and full column rank; M=max(1000,4p).
  - Fixed log prior is tau*q(beta). Adaptive joint log prior is
    (p+alpha-1)*log(tau)+tau*(q(beta)-kappa-1/gamma), alpha=2, gamma=1,
    kappa=sup q. Omit beta-independent constants consistently.
    Preserve the common PWE likelihood and baseline: this is an adaptation
    of the authors' prior, not reproduction of their grouped-baseline posterior.
    Potentials require likelihood-free prior MCMC for valid prior checks.
  - The weighted-mixture comparator uses weighted Breslow partial likelihood
    with weights 1 and tau/M, including weighted risk denominators. Its
    absolute survival uses the weighted merged-data Breslow baseline.
    Check optimizer status, finite coefficients/score and survival validity.
    Bayesian variants retain the unchanged all-parameter MCMC gate.
  - Use measured log2 METABRIC expression, within-sample median collapse by
    Entrez ID, audited unique sample/patient mapping and identical eligible
    patients and folds in both feature settings. Training-only gene filtering,
    imputation and scaling also run inside inner CV. Report published
    cohort-normalization and unresolved exact pretreatment availability.
  - Split T-185 data preparation from fitting. Both matched settings include
    the original six arms, three penalised Cox models, the calibrated
    horseshoe and all three catalytic variants. T-189 depends on prepared
    matched data, avoiding a circular fit dependency.
  - One known same-individual pair exists in the frozen clinical METABRIC
    CSV. Preserve historical folds and report possible inherited train/test
    overlap. The matched expression cohort has no such pair overlap; cluster
    known aliases together in decision-curve uncertainty.
  - Fold-quantile decision curves estimate an adaptive training-horizon
    procedure. Use training censoring weights and paired patient-cluster
    resampling, with conditional exploratory uncertainty and no deployment
    claim. Multiplicity and diagnostic attrition stay explicit.
  - Measure compute before giving runtime predictions. Log-concavity does
    not imply normal-prior sampling cost or an attainable posterior gate.
- Consequences: ADR-038's post-encoding generator, unsupported novelty claim,
  and common diagnostic language for point/Bayesian estimators are replaced
  by these rules. Original frozen failures, incomplete inference, negative
  explanation results and existing released evidence remain immutable. New
  code, manifests, attempted cells, verification and rendered outputs have
  their own lineage and private remote release.

## ADR-040 — Prepare a separately verified catalytic generator correction

- Status: ACCEPTED for corrective engineering; corrected numerical production
  remains subject to the gates below
- Date: 2026-09-29
- Context: The owner requested complete verified code/results and asked how to
  recover from the observed extension failures. At the 2026-09-28 19:01 UTC
  checkpoint, 160 cells rejected a rank-deficient synthetic design, six failed
  optimization/tuning and 19 failed sampling diagnostics. All 73 earlier
  reconstructed rank failures were explained by zero synthetic columns after
  rare-category omission. The pre-production generator fixture used balanced
  categories; supplied full-rank reference inputs and one short expression
  profile did not establish feasibility across the real training splits.
- Decision:
  - Prepare a distinct post-hoc generator correction within the existing
    three catalytic variants. Preserve the original T-180 specification,
    sealed production, all successes/failures and current worker ownership.
    The original programme continues; no full benchmark restart is required.
  - First validate generation using training inputs across all 825 planned
    catalytic outer jobs and every WME inner split, including splits not
    reached after a failure. Record memberships, preprocessing/gene selection,
    actual p/M, times/rate, seeds, rank, category omissions and proposal hashes.
    No held-out scores or sampling success may select a proposal.
  - Evaluate a bounded rank-conditioned candidate that preserves the original
    first proposal exactly. Specify retry seeds, joint covariate/time proposal
    order, rank tolerance, attempt cap and terminal failure. These details are
    candidate settings until the actual preflight and implementation review;
    this decision creates no new numerical freeze.
  - Full-rank accepted designs satisfy the finite-design properness condition
    in Li and Huang (2026), Section 5.1. Conditioning on rank changes the
    generator distribution and couples rows; it does not inherit the original
    iid stability or asymptotic claims. This is a methodological sensitivity
    proposed after failures were known, not externally preregistered evidence.
  - Determine scope and required fits from a reviewed input inventory. The
    METABRIC block has 375 outer positions; the global catalytic block has
    825. These are assessment scopes, not established rerun counts. Preserve
    an outcome, including a failure, only with exact synthetic/real input,
    model, fitting seed/configuration and evaluation compatibility. WME reuse
    additionally requires all inner-generation and tuning inputs to match.
    Keep separate reuse provenance; never relabel original cells as new fits.
  - Revalidate prior/WME arithmetic on changed accepted inputs. Freeze a new
    explicit addendum, reviewed implementation and input manifest before any
    corrected outer-validation score. Run a specified full-budget pilot after
    that freeze to measure compute and test execution. Keep every pilot
    outcome under the new specification; never relax acceptance gates or
    select a generator from performance. A pilot failure triggers review, not
    a silent protocol alteration or a selectively discarded result.
  - Refresh affected scores, paired effects, RQ2 anchors, decision curves,
    reporting, actual visual QA, reproduction/verification and private
    restore/replay evidence. Keep original and corrected versions distinct.
    The frozen-version transfer helpers certify only their original scope;
    corrected/reused provenance needs explicit verification support.
- Consequences: T-190 is required corrective work. Generator feasibility and
  input-equivalence checking begin before further corrected fitting. A rank
  repair does not remedy optimizer or MCMC failures automatically. Their
  separate causes and retained outcomes still require assessment. Compute
  estimates come from full-budget execution, not the previous short profile.
  Overleaf and paper/DOI scope remain as instructed. The original preparation
  proposal is retained byte-for-byte in
  `coordination/recovery/2026-09-29-generator-correction-proposal/`; its pending
  flags describe that historical proposal, not completed corrective gates.
  The prospective cap, seed namespace, complete-proposal retry rule and
  training-input pilot selection are now specified in
  `config/catalytic_correction.yaml` and
  `docs/protocol_addendum_catalytic_correction.md`. Tested generator/preflight
  implementation does not replace the complete-input, arithmetic and distinct
  corrected numerical-freeze gates.
  Method source: [Li and Huang (2026), Section 5.1](https://academic.oup.com/biometrics/article/82/1/ujag004/8455879).

## ADR-041 — Freeze selected correction reproduction before corrected scores

- Status: ACCEPTED for the prospective scope; actual reproduction remains pending
- Date: 2026-09-29
- Context: ADR-040 requires independently verified correction reproduction.
  The original extension plan specifies 92 repeat-one/fold-one cells. The
  correction also selects full-budget pilots from training-input dimensions.
  No corrected fitting or outer-validation score has yet been executed.
- Decision:
  - Select the sorted unique union of the original plan's fixed 92 identities
    and every input-selected corrected pilot identity. Supply a separate
    sealed scope review, code/input bindings and immutable selection before
    any corrected score. Neither fit success nor model performance changes
    the selection. Original ownership delays execution, not selection.
  - For changed accepted inputs, execute a fresh refit with the same corrected
    freeze, input witnesses, seeds, full sampling budget, remedies and gates.
    Compare scientific cell contents and actual posterior/sample-statistic
    arrays using the pinned original reproduction rules. Retain every failed
    attempt, trace, log and comparison failure.
  - For unchanged reused outcomes, require the actual original numerical
    reproduction and reviewed producer/source/environment/input evidence.
    Reapply scientific-content and sampled-array comparisons to those actual
    source/refit files. Report inherited original numerical reproduction;
    byte agreement alone does not establish that a refit occurred.
  - For terminal corrected input outcomes, independently replay the complete
    applicable outer/inner generator recipe under normal full-raw training
    preprocessing, the exact rank-only retry rule and cap. Report no-fit
    recipe reproduction separately from numerical model reproduction.
    Retain historically unavailable constructor evidence as unavailable.
  - Missing original numerical evidence may remain explicitly pending in the
    prospective selection. Resolve it only through separately reviewed,
    append-only evidence without changing identities or known bindings.
    No tool generates its own scope or scientific approval.
- Consequences: This check covers the declared selected union, not an
  all-grid numerical rerun. Deep input, diagnostic, metric and lineage
  verification still covers the complete 1,625-cell mixed grid. Actual
  selected reproduction, visual QA and fresh private release restoration
  remain separate completion gates. ADR-040's generation, pilot and
  acceptance rules are unchanged; no running specification is rewritten.

## ADR-042 — Preserve distinct locations for any missing inherited refit proof

- Status: ACCEPTED for the engineering design; actual identities and execution remain pending
- Date: 2026-09-29
- Context: The sealed selected-reproduction adapters use one original refit
  root. A genuinely missing inherited producer proof may require fresh
  original-law execution. Its new output cannot be copied into that old root
  and presented as historical execution. No corrected score has been produced.
- Decision:
  - Determine any missing subset from the completed reuse inventory and actual
    producer gates. Do not rerun all 92 identities automatically or infer a
    producer's return code from a stored cell, marker or cached comparison.
  - Permit a separately reviewed I/O adapter and prospective, root-reviewed
    per-entry location plan. Only genuinely unproven inherited original-92
    identities with exact current reuse witnesses may enter that plan.
    Each entry has distinct fresh numerical and capture directories, the
    original plan-order index and the unchanged workers=92 selection rule.
  - Bind the same historical root through capture, controller ownership and
    scientific comparisons, producer validation and receiving resolution.
    Receiving locations use explicit complete inventories. Historical JSON
    paths stay immutable; aliases, global-root repointing and file-copy
    equivalence do not establish numerical execution.
  - Keep the original sealed modules and preparation pins unchanged. New
    wrappers have their own reviewed implementation pins. Actual execution,
    exact source/input/environment/thread/interpreter evidence, typed return
    codes, raw logs, official comparisons and lineage reviews remain required.
    A later owner observation is not an original launch receipt or proof of
    an unavailable past exit code.
  - Acquire completed evidence through append-only reviewed resolution.
    Existing pending-only resolution rules remain in force. A valid proved
    entry is unchanged; any factual reclassification requires explicit root
    review and retained history. Freeze and selected identities are unchanged.
  - Review release and receiving wiring separately before adopting a new
    adapter. A wrapper or additional evidence tree cannot silently satisfy
    an older entrypoint or preparation binding.
- Consequences: This decision changes file I/O only. It creates no actual
  missing subset, location plan, scientific approval, corrected freeze or
  numerical result. ADR-040/ADR-041's scope, seeds, budgets, acceptance gates,
  full mixed verification and fresh-restore requirements remain unchanged.

## ADR-043 — Recover the interrupted extension in a separate result lineage

- Status: ACCEPTED for the prospective recovery scope; execution and release
  remain pending
- Date: 2026-10-01 (New Zealand)
- Context: The unpublished 1,625-cell post-hoc extension run stopped with
  1,214 stored cell JSONs and 411 positions without a cell. Twenty-one of the
  stored records reference 34 missing posterior NetCDF files; the other
  1,193 cells passed strict cell/trace hash verification. The exact 21-cell,
  34-trace inventory was committed at `c5ac205` before the isolated one-cell
  recovery pilot returned. That pilot's source/refit non-timing scientific
  JSON matches under the frozen reproduction comparison, but its NetCDF SHA
  differs. A surviving trace demonstrates time-dependent container metadata;
  the missing original posterior arrays cannot be compared. This pilot is a
  recovery-method probe, not an accepted replacement cell. The six interrupted
  claims and two partial traces are preserved in a verified local archive.
- Decision:
  - Preserve the interrupted original run, including every success, failure,
    cell JSON, surviving trace and missing-trace reference. The six dead-owner
    claims and two partial traces were archived and their claim paths cleared
    before this decision; retain that forensic receipt and make no further
    change to the original result root.
    Never write reconstructed files into its missing trace paths, rewrite its
    21 cell JSONs or label a new NetCDF as the original byte-bound artifact.
  - Freeze the 21 recovery identities from
    `coordination/recovery/2026-09-30-host-interruption-trace-inventory.json`.
    Freeze the 411 absent identities from the same original manifest and cell
    directory in
    `coordination/recovery/2026-09-30-original-extension-absent-roster.json`
    before any new numerical dispatch; prohibit another producer of the
    recovered root while this roster is assembled. The 21 were selected
    by missing trace evidence, not results. In fresh write-once roots,
    dispatch all 21 once under sealed production commit
    `119476f`, the original manifest, exact locked environment and matched
    data hash, seeds, budgets and diagnostic rules. The isolated pilot is not
    counted as one of these 21. Preserve actual starts, child return codes,
    raw logs, attempts, failed outcomes, cells and trace hashes. A process
    interruption requires a separate captured retry, not overwrite.
  - Compare each new cell against its preserved original JSON using the
    frozen reproduction rule that excludes only timing, trace-container
    hashes and traceback. Record status, seed, parameters, predictions,
    metrics, diagnostics and every difference. Original posterior-array
    equality is unavailable and must never be claimed. A difference or an
    interrupted or unresolved attempt stops automatic run assembly for
    explicit scientific review; it does not select a favourable repeat or
    erase an old failure. A recorded `failed` or `failed_diagnostics` result
    is a terminal scientific outcome and remains eligible if its official
    scientific record matches.
  - After the 21 refits and comparisons pass, assemble a distinct recovered
    extension root from the 1,193 fully verified original cells/traces and
    the 21 new cells/traces. Bind each producer, file hash and reason for
    replacement in a write-once lineage manifest; require the frozen run
    manifest to match exactly. Resume only the 411 frozen absent positions in
    that recovered root using the sealed six-shard runner and unchanged
    settings. After the documented dead-claim archival and clearance, the old
    run remains separately readable and unchanged.
  - Recheck all 1,625 recovered cells and trace hashes, independent full-grid
    metrics/diagnostics, the fixed 92-cell selected reproduction (including
    the three affected repeat-one/fold-one identities), rendered figures and
    actual PDF QA. Rebind each selected reproduction to the recovered source
    map and compare sampled arrays against the actual source trace. Existing
    prestaged refits and receipts do not automatically certify this recovered
    run, particularly its three replaced selected cells. Report the recovery
    lineage and any old/new outcome differences in the thesis evidence. Final
    release requires a fresh
    receiving restoration and source/receiving comparison; a local assembled
    grid is not a published result.
  - Keep V3's sealed 1,650 first-draw replay as distinct evidence. Its partial
    1,536-cell reuse inventory binds the interrupted source and cannot certify
    the recovered run. Review whether replay inputs can be independently
    rebound to the actual recovered source map; otherwise repeat them. Build a
    new complete input/reuse inventory and arithmetic against the actual
    recovered producer map before any
    ADR-040 corrected numerical freeze or fit. Retain ADR-041/ADR-042's
    original-law producer and reproduction gates with explicit new locations.
- Consequences: This is a post-incident recovery of an unpublished post-hoc
  extension, not a retrospective repair of the released confirmatory or
  robustness evidence. It supersedes ADR-040's assumption that the intact
  original extension shards can simply continue. The catalytic correction
  remains a separate post-hoc version with its existing scientific gates.

## ADR-044 — Submit from verified baseline evidence; continue extensions separately

- Status: ACCEPTED
- Date: 2026-10-01
- Context: The owner chose a submission-first thesis scope after the full
  extension/recovery workload proved incompatible with a near-term writing
  schedule. The owner still wants to finish the extension experiment quickly.
  The approved original study protocol states that the three-cohort
  confirmatory and robustness programme answers the master's questions. Its
  evidence is released and freshly restorable. The later ADR-036 made all
  Q1-oriented extensions thesis-essential, but the interrupted extension is
  still incomplete and the corrected fits have not started. The thesis
  results and conclusion chapters remain unwritten.
- Decision:
  - Supersede ADR-036 only where it requires completion of T-182–T-186 and
    T-189–T-191 before the thesis can be submitted. The thesis evidence base
    is the verified confirmatory, robustness and explanation record, the
    separately labelled ADR-032 sampler sensitivity and ADR-033 Holm bound.
    The original 20 diagnostic failures, five-of-nine estimable primary
    contrast family, and failed explanation-convergence gate must be reported
    without a superiority, equivalence or explanation-stability claim.
  - Keep the frozen extension addendum, original run, recovery plan, results
    and all scientific acceptance gates unchanged. The extension and its
    catalytic correction may continue in parallel as separate post-hoc
    research; they are not thesis-submission prerequisites. The active
    single-cell refit is allowed to reach its recorded terminal return.
    A partial 1,625-cell grid is not a completed experiment and cannot be
    cherry-picked into thesis conclusions.
  - If the entire extension evidence bundle, including the separate catalytic
    correction and T-186 verification/release gates, is available before the
    thesis results lock, the owner and supervisors may include it as clearly
    separated supplementary evidence. Otherwise, document the unfinished
    programme as future work without numerical claims from its partial grid.
    ADR-043's recovery lineage and any original/recovered outcome differences are
    reported in the extension evidence; the thesis reports them only if that
    verified extension is actually included. Paper drafting and DOI work
    remain after thesis submission.
  - Prioritize the thesis evidence freeze, results and conclusion chapters,
    claim review, supervisor review and clean rendered thesis. Continue to
    require an owner instruction before editing the separate Overleaf
    repository. The owner's couple-of-days experiment target is a planning
    aim, not permission to shorten the frozen grid or bypass verification.
- Consequences: T-182–T-186 and T-189–T-191 remain open, active post-hoc
  research tasks with their existing acceptance criteria, but no longer block
  T-147 or T-150–T-161. The study protocol and result-blind extension addendum
  remain preserved. No result changes its original scientific status.

## ADR-045 — Extract a focused post-hoc clinical methods study

- Status: ACCEPTED
- Date: 2026-10-01
- Context: The owner approved a smaller, separate clinical methods study while
  Ravi completes the submission-first thesis. All penalised-Cox clinical
  source cells are stored, whereas the full 1,625-fit extension and its
  correction cannot finish on the desired short schedule. This scope choice
  follows partial extension execution and is therefore outcome-aware even
  though the original 27-comparison family was frozen before its results.
- Decision:
  - Freeze the separate scope and exact roster in
    `docs/protocol_addendum_clinical_methods.md` and
    `coordination/clinical_methods_roster.json` before focused performance
    analysis. Preserve the original addendum and full-grid tasks.
  - Use all 225 clinical penalised-Cox cells, 150 original normal/spike-slab
    references and 75 separately labelled ADR-032 horseshoe references.
    Report all statuses and original horseshoe attrition; no favourable
    model, fold or cohort exclusion is allowed.
  - Keep the original 27-member Holm family and its complete-family,
    25-pair and corrected-interval claim gates. Show calibration,
    discrimination, coverage and runtime descriptively. Do not infer a
    prior-only causal effect or cross-cohort external validation.
  - Build a new verifier, analysis, renderer and private-release path that
    certify only this subset. The full-extension finalizer/release gates
    remain unsatisfied and cannot be reused as a certificate for this study.
  - No decision curve, genomic comparison, catalytic correction, Overleaf
    edit, paper drafting or DOI is required for this focused evidence package.
- Consequences: T-192 tracks this separate study. A complete focused release
  does not close T-182–T-186 or T-189–T-191, nor change the thesis scope in
  ADR-044. Scientific claims depend on the resulting verified evidence.

## ADR-046 — State the baseline verification level available to the focused study

- Status: ACCEPTED
- Date: 2026-10-01
- Context: The frozen focused addendum asks to verify Bayesian traces and
  diagnostics with existing frozen evidence helpers. Independent review found
  that the restored confirmatory and ADR-032 releases used for this study
  contain hash-verified cell records and a 450-cell exact-refit report, but
  not the raw posterior arrays needed to recompute MCMC diagnostics from
  traces. The existing helpers explicitly verify stored status, hashes and
  lineage without recalculating diagnostics or prediction scores. This
  distinction was identified before focused comparative results were read.
- Decision:
  - Keep the focused addendum and its freeze hash unchanged. Supersede only
    its overbroad trace-verification sentence: for the Bayesian references,
    verify every stored cell and source hash, frozen manifests/completions,
    ADR-032 lineage, the existing release receipts and all 450 exact-refit
    scientific-content matches. Pin the prior release files in
    `coordination/clinical_methods_baseline_evidence.json`.
  - Report the verification limit explicitly. The focused study must not
    claim that raw posterior arrays were re-inspected or that diagnostics
    were recomputed from those arrays. Stored diagnostic statuses and all
    original failures remain visible. The new 225 penalised-Cox cells still
    receive independent forecast/metric rescoring and nine saved-refit
    comparisons under ADR-045.
  - No change to the 27 contrasts, paired-patient requirement, Holm gate,
    model roster, clinical cohorts, or original full-extension programme.
- Consequences: T-192 can be judged only at this stated evidence level;
  manuscript and handoff text must carry the same limit. This correction
  does not turn a stored result into a recomputed raw-trace finding.

## ADR-047 — Plan a separate post-hoc RSF surrogate-tree analysis

- Status: ACCEPTED
- Date: 2026-10-07
- Context: The frozen random survival forest (RSF) cells retain selected
  settings and validation predictions but not fitted forest objects. ADR-024
  dropped confirmatory forest SHAP from the immutable explanation stage. A
  shallow tree that imitates RSF predictions could add a distinct, useful
  interpretation of the comparator, but it would not measure the existing
  Bayesian/Cox explanation estimand. The owner asked to add this analysis to
  the task register and plan; all baseline findings and explanation gates are
  already known, so this work is explicitly post-hoc.
- Decision:
  - Plan a separately versioned RSF surrogate-tree analysis under T-193–T-195.
    It is non-blocking for thesis submission under ADR-044 and cannot alter,
    replace or repair any frozen confirmatory, robustness or explanation
    result.
  - Preserve the existing cohorts, outer folds, fold-local preprocessing,
    selected RSF settings and seeds. Refit each source forest in a new run and
    compare its outer-validation predictions with the stored cell before
    treating it as the same teacher. A mismatch must be resolved or reported
    before proceeding; it cannot be silently accepted as an exact replay.
  - Fit each student tree using outer-training data and RSF-generated targets
    only. Tree-complexity selection must use training-only data; outer-
    validation subjects and outcomes remain reserved for fidelity and
    survival-performance evaluation.
  - Freeze the exact teacher target, tree type and complexity selection,
    teacher-replay tolerance, fidelity and outcome metrics, feature grouping,
    uncertainty/stability summaries, failure handling, seeds and claim limits
    in a separate protocol addendum before inspecting surrogate results.
  - Report teacher-student fidelity separately from outcome prediction
    performance. Describe the tree as an approximation of the RSF, not as a
    causal, biological or independently validated clinical explanation. Keep
    all outputs in new files and label the analysis post-hoc.
- Consequences: T-193 must freeze the detailed protocol before production.
  The study does not revive confirmatory RSF SHAP, close the original failed
  explanation-convergence gate, create a new primary model comparison or
  change the thesis evidence base. Inclusion in the thesis remains subject to
  completion before its results lock and the existing claim-review process.


## ADR-048 - Owner override for submission evidence lock reviews

- Status: ACCEPTED
- Date: 2026-10-07
- Context: T-106, T-108 and T-147 were prepared against the verified ADR-044
  baseline, but statistical, clinical/domain and principal-supervisor review
  decisions were unavailable. The owner explicitly instructed that the
  evidence-lock work continue and be completed without reviewer decisions.
- Decision:
  - For these three project tasks, waive the external reviewer-decision gates
    and lock the source-bounded claims in
    docs/claim_evidence_register.md under the prepared evidence manifest.
    Record the internal evidence check and this owner override. Do not describe
    the wording as approved by a statistical supervisor, principal supervisor
    or clinical reviewer.
  - Accept the proposed thesis architecture and 21,000-word main-text target
    as the owner-approved planning baseline in docs/thesis_architecture.md.
    The supervisor decision is waived for T-108 project tracking. Do not imply
    that the programme or institution has approved this target; verify any
    formal programme limit before final submission.
  - Preserve the original diagnostic failures, incomplete primary family,
    failed explanation gate, post-hoc labels, source limits and prohibited
    causal, clinical-utility, deployment, external-validation and superiority
    claims. No new analysis, result or Overleaf edit is authorized by this
    override.
  - Close T-106, T-108 and T-147 on this basis. The waiver applies to this
    evidence-lock milestone only and does not represent external reviewer
    approval or waive any later institution-required thesis review.
- Consequences: The submission baseline is locked for repository planning and
  writing under owner authority. The record distinguishes internal evidence
  review from external approval. Q-007 is answered; the three tasks may be
  checked complete without claiming that reviewers approved the wording.

## ADR-049 - Freeze the RSF surrogate-tree protocol

- Status: FROZEN; independent scientific review pending
- Date: 2026-10-07
- Context: The owner asked to implement and run the separate RSF surrogate
  analysis planned under ADR-047. The protocol choices must be fixed before
  stored RSF prediction values or surrogate results are inspected. The
  checkout's uncommitted evidence-lock work is preserved.
- Decision:
  - Freeze `docs/protocol_addendum_rsf_surrogate.md` before opening stored
    RSF prediction values. Its SHA-256 is
    `291ad6843e96297717883e3d784503836e150b0e58e9a9314af14d4fef0c1bcf`.
    `coordination/rsf_surrogate_protocol_freeze.json` records the hash,
    timestamp and baseline commit.
  - Use the source RSF risk score as the teacher, strict source replay matching,
    fold-local decision-tree regression, training-only complexity selection,
    prespecified fidelity/outcome metrics, patient-level repeated-fold
    summaries, explicit seeds and descriptive feature-group stability.
  - Keep the study post-hoc and write only to a new run directory. The frozen
    baseline and original explanation result remain unchanged.
  - Do not start RSF replay or surrogate production until an independent
    scientific reviewer records acceptance of the frozen protocol. Code,
    focused tests and no-result preflight may proceed while review is pending.
- Consequences: The protocol content is frozen for T-193, but T-193 remains
  open until independent review is recorded. T-194 production is gated on
  that review; T-195 also requires independent scientific and claim review.

## ADR-050 - Prepare a Windows x64 environment for the RSF surrogate study

- Status: ACCEPTED; cross-platform replay qualification pending
- Date: 2026-10-07
- Context: The owner directed that the separate post-hoc RSF surrogate study
  continue on Windows if any platform effects are shown to be immaterial.
  The confirmatory source release is bound to the macOS arm64 lock, so a
  Windows execution environment must be independently locked and recorded.
- Decision:
  - Keep `conda-lock.yml` as the immutable macOS arm64 source-release and
    confirmatory environment. Add `conda-lock-win-64.yml` as a separate lock
    generated from the same `environment.yml` version constraints and record
    its SHA-256 in the companion file.
  - Permit the Windows lock only for the separate post-hoc RSF surrogate
    execution. Its lock identity is recorded separately in each run manifest;
    it does not alter or replace the frozen source release environment.
  - Do not presume platform differences are negligible. Before any student
    fit, the independent protocol-acceptance gate in ADR-049 must pass and the
    Windows RSF replay must preserve subject order and meet the frozen
    `allclose(rtol=1e-10, atol=1e-12)` tolerance for each eligible source cell.
    A mismatch blocks use of that cell as a teacher under the frozen protocol.
  - Keep the three-cohort timing pilot and 60-minute projected runtime ceiling
    unchanged. Write all pilot and production outputs to new post-hoc paths.
- Consequences: A Windows environment can be prepared and verified without
  touching confirmatory outputs. Its installed dependency versions and HDF5
  compatibility are verified, but no RSF replay has run and cross-platform
  scientific equivalence is not yet established. Q-008 and ADR-049 remain
  unchanged; production is still held pending their independent review gate.

## ADR-051 - Owner waiver to execute the RSF surrogate study

- Status: ACCEPTED; independent scientific review not obtained
- Date: 2026-10-07
- Context: After being told that Q-008 remained open and no independent
  protocol acceptance was recorded, the owner instructed execution of the
  Windows RSF surrogate study. This explicitly waives the ADR-049 reviewer
  prerequisite for T-193/T-194 execution; it does not supply or imply
  independent scientific review.
- Decision:
  - Proceed with the frozen protocol v1.0 methods and the separately locked
    Windows x64 environment. Do not alter the protocol hash or describe this
    owner instruction as reviewer acceptance.
  - Preserve the strict subject-order and
    `allclose(rtol=1e-10, atol=1e-12)` teacher replay check. Run one
    representative fold per cohort first; proceed to the 75-cell grid only
    when replay passes and the measured runtime projection is at most
    60 minutes. If either condition fails, stop before full production.
  - Bind the owner waiver receipt and its hash in every run manifest. The
    waiver applies only to T-193/T-194 execution on Windows. T-195 still
    requires independent scientific and claim review before reporting or
    adopting any result as thesis evidence.
- Consequences: Q-008 is answered for the T-193/T-194 production prerequisite
  by the owner's waiver; no independent acceptance was obtained. Any results
  remain explicitly owner-waived post-hoc evidence and cannot be described as
  independently reviewed.
- Execution update (2026-10-07): Two three-cohort Windows r01f01 pilots were
  sealed under separate Windows locks. All six cell attempts failed the frozen
  replay tolerance with the same cohort-specific maximum absolute errors
  (11.6091, 14.2223 and 87.9071). No student tree was fitted and the 75-cell
  production run was not started. The second lock pinned scikit-learn, joblib
  and threadpoolctl to the macOS source-lock versions but did not resolve the
  mismatch. Its cause remains undiagnosed; do not claim platform equivalence
  or alter protocol v1.0 based on these observed results.

## ADR-052 — Add a separate backward-elimination Cox analysis

- Status: ACCEPTED
- Date: 2026-10-13
- Context: The frozen baseline uses declared clinical predictor sets and must
  remain unchanged. A fold-local backward-elimination comparison can assess
  whether a smaller Cox feature set retains predictive performance, provided
  selection is isolated from outer validation and from the original claims.
- Decision:
  - Add grouped backward elimination as a distinct post-hoc Cox analysis. Do
    not apply it to the frozen Bayesian, Cox, forest, or DeepSurv cells and do
    not overwrite any released evidence.
  - At each greedy step, remove the source-feature group whose removal gives
    the lowest complete three-fold inner-CV IPCW IBS. Refit preprocessing
    inside every inner-training split and use the fixed Cox penalty from the
    confirmatory specification.
  - Select the smallest model on the greedy path within one fold standard
    error of the lowest inner mean IBS. The one-standard-error quantity is a
    selection heuristic, not an inferential interval. Use deterministic
    preprocessor group order to resolve exact ties and retain every candidate
    score and failure.
  - Freeze the protocol and implementation hashes in
    `coordination/backward_elimination_protocol_freeze.json`; run only in a
    new post-hoc results directory, using the existing outer-fold identities.
    Report selection stability descriptively and make no causal, confirmatory,
    superiority, equivalence, or clinical-utility claims.
- Consequences: The original feature sets and evidence remain authoritative.
  The new implementation is available for the separately tracked study, but
  no model has been fitted and no experiment result is produced by this
  decision. Production and result verification remain outstanding.


## ADR-053 — Finalise the standalone thesis from completed evidence

- Status: ACCEPTED
- Date: 2026-11-17
- Context: The owner supplied Ravi's new Overleaf project and requested a complete, coherent report of the study that exists now. The report should foreground its scientific contribution, with clear natural prose and no planning history, internal metadata or repetitive caveats.
- Decision:
  - Use the new project `6af91395a2e68e546f56fbc0` as the manuscript target. Preserve the previous source checkpoints.
  - Finalise all five chapters and scientific appendices using the existing prediction, calibration, posterior, explanation, robustness and separately identified post-hoc results. No new model fitting is required.
  - Present precise scientific findings and interpretation-essential coverage and uncertainty. Remove proposal-versus-completion narration, recovery records, machine paths, hashes and administrative material from the manuscript. Maintain the owner's existing manuscript-content exclusions.
  - Replace outdated result screenshots with verified vector figures and source-derived tables. Preserve the original numerical evidence; presentation changes may improve labels and notes without changing values.
  - Treat T-150 through T-157, T-159 and T-160 as manuscript-production tasks under the current acceptance criteria below. Author feedback and actual university submission remain separate activities, not prerequisites for producing the completed files.
- Consequences: The completed source and PDF are published on GitHub branch `thesis/final-report-20261117`. The prepared source ZIP is independently build-verified. Overleaf rejected the direct Git push as forbidden; its live replacement is not claimed. The editor-upload procedure is recorded in `docs/ravi_thesis_next_steps.md`. Original experiments and code remain unchanged.


## ADR-054 — Apply the examiner review and consolidate the report

- Status: ACCEPTED
- Date: 2026-11-17
- Context: The owner requested use of `Master_thesis_review_prompt_2.md`, a stronger scholarly argument and removal of redundant or repeated report content.
- Decision:
  - Assess all nine supplied criteria and save versioned assessments outside the thesis. Preserve previous review versions.
  - Express the four research questions through the analyses actually performed. Remove the separate hypothesis labels from the manuscript rather than attributing an unestimated information trend to ordinary within-cohort comparisons. Preserve the original scientific protocol and result records.
  - Position the contribution against named closest studies. Add the exact algebraic relationship between posterior absolute contributions and centred posterior-mean SHAP as an interpretation of their definitions, with a checked prior-variance identity. Do not present these as new model fits or an invented empirical result.
  - Consolidate the cohort information, methods and concluding synthesis. Retain complete scientific details in their primary location and supporting estimates in the appendices.
  - Preserve all original numerical evidence and the separation of original and post-hoc analyses. Commit the revised PDF, source, assessment and independently build-verified upload ZIP to GitHub.
- Consequences: The revised report is 92 pages, eight fewer than the preceding version, with 2,221 fewer main-chapter source tokens. The current assessment is Codex v2 and recommends A under the supplied rubric. The actual institutional grade and journal decisions are not represented as obtained. The existing Overleaf write-access restriction remains separate from the completed report and review.
