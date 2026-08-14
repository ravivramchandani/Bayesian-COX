# OPEN QUESTIONS

Questions with no obvious defensible answer, where the choice would materially
change the work. Anything with an obvious answer is decided and recorded in
`DECISIONS.md` instead.

Format:

```markdown
## Q-NNN — <one-line question>
- Status: OPEN | ANSWERED | OBSOLETE
- Track: OWNER | ENGINEERING
- Blocks: <the single deliverable that cannot be finished without it, or none>
- Context: <what raised it>
- Answer: <when answered>
```

---

## Q-001 — Is the catalytic prior worth a fourth arm?

- Status: OPEN
- Track: ENGINEERING
- Blocks: nothing. The three-prior comparison is complete without it.
- Context: A catalytic prior stabilises the partial-likelihood estimator when
  the sample is small relative to the number of covariates. That is a
  different regime from the sparsity-as-explainability question this project
  answers, so it extends the prior sweep rather than belonging in the primary
  comparison. It becomes worth adding only if the small-sample robustness run
  in Phase 3 shows the existing priors degrading, which would give it
  something to be measured against.
- Answer: Deferred to Phase 3 on evidence, not opinion. Recorded as T-033.
