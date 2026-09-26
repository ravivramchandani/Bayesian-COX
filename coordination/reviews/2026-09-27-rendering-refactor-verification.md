# Rendering refactor verification

The original renderer at `6c037a8` and the extracted renderer consumed the
same verified 450-cell run and original explanation artefact. The old source
copy matches its Git blob exactly. Outputs were written to separate scratch
directories under `~/bayes-cox-runs/render-equivalence-20260927/`.

The exhaustive SHA-256 inventory is
`coordination/recovery/2026-09-27-render-equivalence.json`. Of 881 original
files, 874 remain byte-identical and seven differ intentionally. The new
bundle contains 886 files. No original output is missing.

| Changed output | Reason |
|---|---|
| `paired_ibs_effects.csv` and `.tex` | Retain all nine primary contrasts, their status and paired-fold counts; four estimates remain unavailable. |
| `paired_ibs_effects.pdf` and `.png` | Show the four unavailable rows, readable prior labels and all nine rows without clipping. |
| `explanation_stability.pdf` and `.png` | The title identifies the failed convergence gate; numerical estimates remain unchanged and descriptive. |
| `lineage.json` | Record extracted renderer-module hashes, the changed outputs and five new artefacts. |

Five additions are intentional: `EXPLANATION_GATE_NOTICE.txt`, the CSV/LaTeX
ADR-033 bound, and the CSV/LaTeX compact primary-contrast table. The bound
reports no possible or guaranteed rejection for any of the five available
contrasts; it supplies no missing p-values and leaves confirmatory Holm
inference incomplete.

The paired-effects and explanation PDFs were rendered through Poppler and
visually inspected: labels and intervals are legible, all rows are present,
and nothing is clipped or overlapping. PDF fonts are embedded. The remaining
874 outputs, including posterior traces, calibration, discrimination,
predictive checks, runtime and proportional-hazards summaries, match the
original bytes.

The extracted package separates verification, outputs/lineage, metrics,
diagnostics, supplements and orchestration. The entry point preserves its
previous import names. Tests recursively reject model/pipeline imports or
fitting calls, verify deterministic rendering, reject corrupted evidence,
and reject edits to renderer source during execution. Rendering and bound
tests passed 15 cases; the integrated suite subsequently passed 204 tests
before the separate sampler-reporting additions.

No frozen source record, cell, aggregate or explanation value was changed.
