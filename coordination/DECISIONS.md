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
  supervisor's May 2026 guidance. WHAS500 supplies the cardiology cohort the
  heart-attack file was intended to cover; GBSG2 supplies a properly powered
  second cohort. All three have published baselines that make replication
  checkable.
- Consequences: Every cohort carries genuine time-to-event data with
  censoring. The proposal text needs updating to match; that is recorded as
  an owner-track item, not a blocker.

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
  fit. Supervisor guidance from May 2026 required PyMC with NUTS and reported
  R-hat, effective sample size, divergent transitions, and trace plots.
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

## ADR-009 — Explainability comparison

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
