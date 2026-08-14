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
