# Review template

Used by the Reviewer subagent. Save at
`coordination/reviews/<task-or-phase-id>.md`.

---

# Review of <T-NNN or phase-N>

- Reviewed-by: <session id>
- Reviewed-at: <ISO-8601 UTC>
- Scope: <commit SHA range, files, or "phase N end-of-phase sweep">
- Brief consulted: `coordination/briefs/<id>.md` (if applicable)

## Tests run

| Command | Result | Notes |
|---------|--------|-------|
| `make test` | pass / fail | <details> |
| `<phase-specific test>` | pass / fail | <details> |

## Invariants checked

| Invariant | Status | How verified |
|-----------|--------|--------------|
| INV-NNN | holds / violated | <command or quote> |
| INV-MMM | holds / violated | <command or quote> |

## ADRs referenced

| ADR | Implementation status | Drift detected? |
|-----|----------------------|-----------------|
| ADR-NNN | matches | no |
| ADR-MMM | matches | yes, see notes |

## Findings

### Must-fix (blocks landing)
- <item>

### Should-fix (does not block)
- <item>

### Suggestions (nice to have)
- <item>

## Verdict

`APPROVE` | `APPROVE-WITH-CAVEATS` | `REVISE-MINOR` | `REVISE-MAJOR` | `REJECT`

## Notes

<Anything else worth recording: context for the verdict, edge cases
considered, areas not reviewed.>
