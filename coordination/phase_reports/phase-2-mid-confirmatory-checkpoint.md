# Phase 2 checkpoint — Frozen confirmatory run in progress

Date: 2026-08-15

Status: procedural gates complete; confirmatory computation active; no final
scientific result accepted

## Completed gates

- The exact locked environment contains 259 packages; its lock SHA-256 is
  `1921895d4a404fc99e848d69ccd4a3f6639a3d1610315c82ecd463ed4bcdfb57`.
- The final-input result-blind rehearsal stored all 18 planned cells. Review
  was limited to status, controls, hashes and elapsed time; no comparative
  effect was inspected.
- The prespecified runtime rule retained five outer repeats.
- The write-once protocol freeze records 80 inputs. Independent rehashing found
  zero mismatches. Its content SHA-256 is
  `3b5e1042d592ebb6fade0a4a76c1f0d31ce9c0c1cfc08357be46f163f037d2ca`.
- Before production, the exact environment passed 150 tests and Ruff reported
  no violations.

## Live-run boundary

The production run is writing to
`reports/confirmatory/confirmatory_v1_confirmatory_cdcdcee84651/`. At the
checkpoint, all 150 GBSG2 cells and all 150 WHAS500 cells were stored, while
METABRIC remained active. Cell completion is operational progress, not a
completed performance or inferential result.

No final aggregate, inference table, calibration comparison, robustness result
or confirmatory explanation result is accepted by this checkpoint. Live and
rehearsal artefact directories are intentionally excluded from the source
checkpoint commit because they are generated, content-addressed and, for the
active run, still changing.

## Required close-out

1. Allow the frozen confirmatory process to finish or resume only under the
   same exact environment and unchanged frozen inputs.
2. Verify 450 stored cells, completion and manifest hashes, end-of-run freeze
   checks, diagnostic failures and analysis-specific completeness gates.
3. Update the tracker with verified final status and create the agreed local
   confirmatory checkpoint commit.
4. Stop for owner review. Do not begin robustness, confirmatory explanation or
   post-confirmatory thesis results writing without a new instruction.
