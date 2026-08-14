# Working protocol

How work proceeds on this project. Binding for every session.

## Execution

Implementation proceeds autonomously. Resolve ordinary engineering choices,
build the next usable component, and keep momentum. Do not convert unknowns
into requests for permission.

Stop only when:

- a required file is genuinely unavailable, or
- an irreversible external action needs the owner's decision.

Everything else continues.

## Two tracks

Work is separated into what can be done now and what depends on an input that
only one later deliverable needs.

**Engineering track.** Data, models, metrics, tests, analysis, figures, and
writing. Runs continuously and is never gated on an administrative item.

**Owner track.** Approvals, access, credentials, authentication, ethics,
permissions, licensing, data-use determinations, and supervisor sign-off. The
owner holds these. They are recorded once in `OPEN_QUESTIONS.md` under
"Owner track", carried forward without restating, and never used to pause
engineering.

An open question blocks only its exact final deliverable. If a result needs an
input that has not arrived, build the pipeline that produces it, test it on
the data available, and leave the single dependent number pending. Missing
optional evidence narrows the affected analysis; it does not stop the thesis.

## Quality bar

Publishable master's-thesis quality. A limitation is acceptable only when it
is out of scope per a written record, the data is unavailable with evidence,
or an external constraint binds. Anything fixable within scope gets fixed.

No invented results, citations, or numbers. Every quantitative claim traces to
a file in `reports/tables/`.

## Determinism

Every stochastic step takes an explicit seed. Sampling configuration is
recorded alongside the result it produced. Reruns from a clean clone reproduce
committed results.

## Writing

Repository content stays clear, simple, and professional. No decorative
headers, no comments restating the code, no process narration, no status
chatter. A docstring says what a function does and what its arguments mean. A
journal entry records a fact or a result. A report states the method and the
numbers.

Internal identifiers, file paths, and process language do not appear in
compiled thesis chapters, except the reproducibility appendix.

## Commits

Trunk-based on `main`. Commit messages state what changed. Commit when the
work is complete and the tests pass.
