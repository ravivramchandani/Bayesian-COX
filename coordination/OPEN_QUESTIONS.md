# OPEN QUESTIONS

Questions that need an answer from the owner or an external source. Answered
entries stay as the audit trail.

Owner-track items are administrative. They are recorded once, held by the
owner, and never used to pause engineering. Each names the one deliverable it
actually blocks; everything around that deliverable is built regardless.

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

## Owner track

## Q-001 — Does the approved proposal document need a formal update?

- Status: OPEN
- Track: OWNER
- Blocks: Final proposal document only.
- Context: The cohorts changed from the proposal's METABRIC, heart-attack and
  lung-cancer set to METABRIC, WHAS500 and GBSG2 (ADR-004), and the model
  roster and priors were extended after the proposal was approved. Whether
  the proposal itself is revised or the change is carried in the thesis is
  the supervisors' call.
- Answer: —

## Q-002 — Is the catalytic prior in scope as a fourth prior variant?

- Status: OPEN
- Track: OWNER
- Blocks: A fourth prior arm in the comparison. The three-prior comparison is
  complete without it.
- Context: A 2024 catalytic-prior paper for Cox regression was raised as a
  possible novelty anchor. It addresses the small-n/large-p regime rather
  than explainability, so it extends the prior comparison rather than
  replacing its spine.
- Answer: —

## Q-003 — DeepSurv or DeepHit as the deep-learning arm?

- Status: OPEN
- Track: OWNER
- Blocks: The deep-learning row of the benchmark table only. The four other
  arms are complete.
- Context: DeepSurv shares the proportional-hazards assumption and sits closer
  to the Cox comparison. DeepHit earns its place only if competing risks are
  in scope, which the panel noted was missing.
- Answer: —

## Q-004 — Confirm the thesis domain scope

- Status: OPEN
- Track: OWNER
- Blocks: Final framing of the introduction chapter.
- Context: The current draft broadened the title beyond healthcare while the
  panel asked for a sharper focus. All implemented work is healthcare.
- Answer: —

---

## Engineering track

## Q-005 — Should `los` remain a WHAS500 covariate?

- Status: OPEN
- Track: ENGINEERING
- Blocks: nothing; the current benchmark includes it.
- Context: Length of hospital stay is recorded at the index admission and is
  part of the standard scikit-survival feature set, but it is measured after
  admission and may carry outcome information. A sensitivity run without it
  would settle the question.
- Answer: —
