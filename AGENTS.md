# AGENTS.md — shared guide for AI coding assistants

Codebase for the MAT thesis *Bayesian Survival Models for Explainable
Prediction of Diseases*. The thesis document lives in a separate
Overleaf-backed repository; this repository holds data, models, experiments,
and results.

## Start here

Read in order:

1. `coordination/PROTOCOL.md` — how work proceeds.
2. `coordination/TODO.md` — current tasks.
3. `coordination/DECISIONS.md` — binding choices.
4. `coordination/INVARIANTS.md` — contracts that must not be weakened.
5. `coordination/GLOSSARY.md` — formal terms.
6. `coordination/OPEN_QUESTIONS.md` — what is genuinely unresolved.

These files are the source of truth. Do not duplicate them elsewhere.

## Execution

Proceed autonomously. Resolve ordinary engineering choices and build the next
usable component. Stop only when a required file is genuinely unavailable or
an irreversible external action needs the owner's decision.

Approvals, access, credentials, ethics, and permissions
are owner-managed. They live in `OPEN_QUESTIONS.md` under "Owner track", are
raised once, and never pause implementation. An open question blocks only its
exact final deliverable, not the preparatory engineering around it.

## Build

```bash
make env        # install the exact lock into LOCK_ENV
make data       # retrieve and verify the three raw cohorts
make all        # verify the environment, run tests and lint
make test       # test suite plus coordination schema validation
make lint       # ruff
make thesis     # compile ../thesis-overleaf/Main.tex
make jargon     # check no internal identifiers reached the chapters
```

Run inside the exact lock environment recorded in `coordination/HANDOFF.md`,
and set `PYTHON` to that environment's interpreter. The thesis document is a
separate Overleaf-backed repository beside this one; `THESIS_DIR` overrides
its path.

The active data path is `src/data/cohorts.py`, `survival_folds.py` and
`fold_preprocessing.py`. Preprocessing is fitted inside each training fold;
no active script consumes the historical `data/processed` splits. The six
legacy pilot scripts, duplicate loaders and placeholder pipelines are retired.
Their original source remains available from checkpoint commits. Historical
data and results remain unchanged in the checkout.

Use `make reproduce-confirmatory CONFIRMATORY_RUN=<directory>` for a frozen-
cell reproduction check. Rendering targets `make reports`, `make figures`
and `make render-confirmatory` require that same run directory and read its
stored evidence. They never refit models. Confirmatory production is closed;
the current authorised downstream programme is recorded in `HANDOFF.md`.

## Code rules

- Baselines use lifelines and scikit-survival; metrics delegate to
  scikit-survival. The Bayesian Cox model is the project's own implementation.
- Every stochastic step takes an explicit seed.
- Public functions carry type hints and at least one focused test.
- Definitions live in `GLOSSARY.md`; code references them rather than
  redefining.
- Non-trivial methodology choices get a record in `DECISIONS.md`.
- Results already referenced by the thesis are immutable; new results write to
  a new filename.
- No code path may fabricate observations. A missing data source raises.

## Writing

Repository content stays clear, simple, and professional. No decorative
headers, no comments restating the code, no process narration. Write the
minimum a competent reader needs.

## Before committing

```bash
make test
python tests/test_coordination_schemas.py
```
