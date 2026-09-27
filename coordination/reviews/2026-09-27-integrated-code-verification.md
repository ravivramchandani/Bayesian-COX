# Integrated code verification — 2026-09-27

The interrupted changes are integrated into the active script pipeline. The
frozen study inputs, original evidence and adjacent Overleaf repository are
unchanged. New reproduction and post-hoc outputs have separate directories.

## Numerical and rendering gates

| Change | Acceptance evidence | Outcome |
| --- | --- | --- |
| Models, evaluation and statistics | Six original GBSG2 model cells refitted, including the horseshoe remedy ladder | 6/6 identical except timing fields |
| Confirmatory package | All 450 stored cells re-aggregated | All three aggregate files byte-identical |
| Confirmatory fitting | Six GBSG2 cells and four specified WHAS500/METABRIC cells refitted | 10/10 identical except timing fields |
| Explanation package | Original production artifact recreated through the public CLI | Original SHA-256 reproduced exactly |
| Robustness package | Normal sample-fraction, spike-and-slab administrative-censoring and horseshoe tighter-prior cells refitted | 3/3 identical except timing fields |
| Renderer | Exhaustive original/refactored file comparison | 874 identical, seven documented changes, five additions, no missing files |

The render comparison and visual inspection are documented in
`2026-09-27-rendering-refactor-verification.md`; its exhaustive inventory is
`../recovery/2026-09-27-render-equivalence.json`. The final render incorporating
completed robustness and the separate sampler sensitivity remains pending.

The original explanation SHA-256 is
`120984c7edfac468f471b9f500470623689b2647e4bde56d271cc9623346ecd5`.
Its failed convergence gate is preserved. Exact reproduction does not permit
an explanation-stability claim.

## Integration checks

Checkpoint-bound verification accepts all 80 original input blobs at
`44b608572a5e1006a05ed5e3c4985471b2ba594d` and requires unchanged live study
inputs. The actual completed 450-cell resume was checked read-only: all 455
original files retained their hashes, and no fit or aggregation was invoked.
The locked runtime verifies all 259 packages.

The integrated suite passed 270 tests after packaging and presentation fixes,
including final result idempotence and supplemental-render lineage.
Coordination schemas, Ruff and the exact runtime verification passed.
Coordinator crash/restart checks also passed: duplicate launches are rejected
before manifest access, and a surviving child stage retains the output lock.
Retired pilot executables, duplicate loaders and placeholder pipelines no
longer form an active path; historical data and results remain preserved.

The independent review found two integration errors before production launch:
saved reproduction paths differed between writing and resume, and sampler
validation initially used a display label for spike-and-slab instead of its
analytical label. Both are corrected and covered by regression checks.
Validation also rejects rehashed wrong-body robustness cells, undeclared
sampler changes, stale environments, incomplete paired-fold inference and
rendered outputs tied to different supplemental evidence.

## Production boundary

`scripts/complete_results_programme.py` runs from unchanged committed code in
a detached checkout. It verifies the frozen source and runtime before fitting,
uses two workers to refit all 450 cells, waits for the existing six frozen
robustness workers and their finishing supervisor, then runs all 75 ADR-032
sampler refits with six workers. It independently verifies saved results and
renders both evidence bundles. Its analysis-complete record explicitly
requires final visual QA before release readiness.

The 450-cell regeneration is verification-only. The 75-cell sensitivity is
post-hoc and never replaces original diagnostic failures. The original Holm
family remains incomplete, irrespective of sensitivity results. Original
scientific failures are reported as observed outcomes rather than repaired by
relaxing a gate.

## Local evidence locations

The seven small reports/logs below are also preserved in
`../recovery/2026-09-27-refactor-gates.tar.gz`, with per-file hashes in its
adjacent manifest. The archive does not contain fitted-cell outputs.

- `~/bayes-cox-runs/refactor-verification/models-20260927-v1/quick6.json`
  (SHA-256 `020e360ad62dcbbb24a85819c88fa296e4bcf5104d323112ed58cb06ed870e95`).
- `~/bayes-cox-runs/refactor-verification/confirmatory-20260927-v1/quick6.json`
  (SHA-256 `dd0953b933f925c280a0ea823bab1dea862de06cba948defc59b28682a8bde41`).
- `~/bayes-cox-runs/refactor-verification/confirmatory-20260927-v1/specified4.json`
  (SHA-256 `c903b5769f327c071c27ae4e16e80b3dfc50042d363aacc7cdeedc893500be69`).
- `~/bayes-cox-runs/agent-scratch/confirmatory/rebuild_refactored_20260927.log`.
- `~/bayes-cox-runs/checks/robustness-refactor-gate-{1,2,3}.log`.

These limited refit gates establish safe integration. They do not stand in
for the separately required full 450-cell regeneration.
