# Phase 2 — Frozen confirmatory execution close-out

Date: 2026-08-15

Status: frozen execution complete and verified; primary inferential family
incomplete; no complete-family claim accepted

## Verified production artefact

The production run is
`reports/confirmatory/confirmatory_v1_confirmatory_cdcdcee84651/`. Verification
accepted the manifest and completion content hashes, every aggregate and
stored-cell file hash, the exact planned cell grid, the complete-cell metric
and prediction lineages and the unchanged 80-input protocol freeze.

| Control | Verified value |
|---|---|
| Planned/stored cells | 450 / 450 |
| Cell status | 430 complete; 20 `failed_diagnostics` |
| Out-of-fold predictions | 91,718 rows across the 430 complete cell keys; no duplicate subject key |
| Manifest content SHA-256 | `9ec040841b4751ee3064c93d21d5069ed27bf3bfd6641f0dfffff76557bbf9f7` |
| Completion content SHA-256 | `03870efdae3134305794ea977fd9cbe7913c0d693f1b009337546319aa03bee1` |
| Protocol-freeze SHA-256 | `3b5e1042d592ebb6fade0a4a76c1f0d31ce9c0c1cfc08357be46f163f037d2ca` |
| Fold-metric aggregate SHA-256 | `e27aca1fffa74719ada0999ae5a200a44a5ac49dd11711457185ac33c7b5f86e` |
| Prediction aggregate SHA-256 | `6e1b03fd60759ef7e6c22e0a64dd5d08f040abd12e9250de566211fbd7fe3c42` |
| Inference aggregate SHA-256 | `54f53ff0e2e23be2e52e9365716693d9f6b35a11e0d5750644640b38e26edf0e` |

## Prespecified diagnostic outcome

All 20 failed cells are Bayesian horseshoe fits. Each records three attempts:
the initial fit and both permitted remedies. The failures are distributed as
follows:

| Cohort | Horseshoe complete | Horseshoe failed | Other model cells |
|---|---:|---:|---:|
| GBSG2 | 7 | 18 | 125 complete |
| WHAS500 | 25 | 0 | 125 complete |
| METABRIC | 23 | 2 | 125 complete |

No failed-diagnostic fit enters `fold_metrics.csv` or an inferential estimate.
The failures are the recorded outcome of the frozen quality gate, not a reason
to add a sampler remedy or select a favourable rerun.

## Inferential completeness gate

The generated inference artefact reports `status: incomplete` and
`holm_family_complete: false`. Five of the nine primary within-cohort prior
contrasts have all 25 paired folds. Four do not:

- normal versus horseshoe and horseshoe versus spike-and-slab in GBSG2;
- normal versus horseshoe and horseshoe versus spike-and-slab in METABRIC.

Those four entries are recorded as `incomplete_no_confirmatory_inference`.
They have no corrected effect, confidence interval, test or Holm-adjusted
result. Available complete contrasts and descriptive aggregates remain frozen
production evidence, but they cannot be presented as a complete nine-contrast
primary family. No complete-family superiority, equivalence or multiplicity-
controlled claim is accepted by this phase.

## Handoff boundary

The live 15-week programme still ends on 2026-11-30. The owner has paused
robustness, confirmatory explanation, primary claim review and
post-confirmatory thesis result writing. This checkpoint ends after the local
source commit; no downstream production stage starts without a new
instruction. The 80 frozen methodological inputs remain unchanged.
