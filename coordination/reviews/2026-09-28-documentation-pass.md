# Baseline documentation review — 2026-09-28

The documentation pass is complete across 115 baseline Python files: 23 in
`src/pipelines`, 31 in `src/models`, `evaluation`, `statistics`, `data` and
`utils`, 20 in `src/explainability` and `rendering`, and 41 in `scripts` and
`tests`. All 858 module/class/function definitions in this scope now have
docstrings. Public contracts describe inputs, outputs, relevant errors, array
axes, units and scales; tests identify the behaviour they protect. The newer
extension modules retain their separately verified documentation and source
identities.

Corrections follow the actual bodies and callees. These include Cox's scaled
ridge penalty; training-derived prior predictive checks; tie-adjusted ranking;
conditional censoring weights; finite-sample statistical assumptions; SHAP's
attribution scale and sampling variation; partial-pair inference; actual
prediction calls, attempt retention, atomic writes and source-data consumers.
Each package's report and before/after ledger enumerate the reviewed changes.

All 230 stripped-AST comparisons pass against original base `f0cce64` and
integration base `0ba4c3d`. The independent repository gate also reports
`115 changed Python files; 115 documentation-only`. All 349 tests pass in
85.44 s; normal repository Ruff, coordination schemas and diff checks pass.
Hashes of all 157 tested source/build/lock files stayed unchanged during
verification. Imports and executable statements are unchanged.

The brief requires existing bugs to be reported without changing code.
Recorded boundary limitations include event coercion; some unchecked prediction
times; nonfinite values potentially skipped by aggregate diagnostic reductions;
permutation-count validation; NumPy scalar serialization; concurrent writes;
discarded earlier attempts after execution errors; and a robustness availability
status that the completed-run verifier rejects. These descriptions do not
establish affected study results. The separate numerical verification retains
its original gates.

The 103 original worktree drafts remain unchanged. The
[compact receipt](../recovery/2026-09-28-documentation-pass-verification.json)
pins the 269-member, byte-verified
[evidence archive](../recovery/2026-09-28-documentation-gates.tar.gz), containing
original drafts, candidate sources, package reports, correction ledgers,
two-base proofs and full integration logs. The existing reading guide remains
at `docs/code_guide.md`. No numerical worker or sealed scientific source changed.
