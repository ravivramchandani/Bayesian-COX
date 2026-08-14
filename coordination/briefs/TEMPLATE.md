# Brief template — dispatch a subagent

The Coordinator writes one of these before invoking a subagent (Implementer,
Researcher, Reviewer, or Writer). The brief is the subagent's prompt; it
contains everything the subagent needs to act without further context.

Save the brief at `coordination/briefs/<task-id>.md` and pass its
contents to the subagent.

---

# Brief: <T-NNN or Q-NNN> — <one-line goal>

## Role
<implementer | researcher | reviewer | writer>

## Goal
<One sentence describing the outcome. Specific and falsifiable.>

## Exit gate
<The single test, command, or grep that proves the work is done. The
subagent must run this before reporting back.>

```bash
<exact command>
```

Expected outcome: <pass / specific value / specific output shape>.

## Files to read on entry
- `coordination/DECISIONS.md` — note ADR-NNN, ADR-MMM if relevant.
- `coordination/INVARIANTS.md` — note INV-NNN, INV-MMM if relevant.
- `coordination/GLOSSARY.md` — terms in scope: <list>.
- `coordination/OPEN_QUESTIONS.md` — relevant: <list>.
- <other paths>

## Constraints
- <Invariants the change must preserve.>
- <ADRs that constrain the choice.>
- <Glossary terms that govern the definition.>
- <Style or convention rules from AGENTS.md.>

## Expected output
- <File path 1>: <what to put there>.
- <File path 2>: <what to put there>.
- (For Implementer) Commit on `main` with message `phase-N: T-NNN <title>`.
- (For Researcher) Verification note at `coordination/research/<id>.md`.
- (For Reviewer) Structured review at `coordination/reviews/<id>.md`.
- (For Writer) LaTeX section in `thesis/chapters/<file>.tex`; `make thesis`
  must pass.

## Word count / scope budget (Writer only)
<e.g., 1,200–1,500 words; one figure reference; cites at most five papers.>

## Notes / context
<Anything else the subagent should know but that does not fit above.>
