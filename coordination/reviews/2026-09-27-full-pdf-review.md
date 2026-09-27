# Full rendered-PDF review — 2026-09-27

All 426 PDFs in the first extracted-renderer bundle were rasterized at 150 dpi
and visually reviewed against their file hashes. All PDF fonts were embedded
and page boxes passed structural checks. The complete review found 396 clean
pages and 30 with layout defects, extending the earlier representative-only
check in `2026-09-27-rendering-refactor-verification.md`.
The per-file review record is
`../recovery/2026-09-27-baseline-pdf-qa.json` (SHA-256
`c1d5d81e81070bcbf822ad82ab3d102f3db3182a544f2cbe2bea27528d2473b8`).
The baseline record correctly retains a failed layout status.

Three overview figures had crowded fold-metric model labels, runtime labels
or proportional-hazards covariate labels. Twenty-five tall METABRIC trace
pages placed their heading in the first plot row, and two WHAS500 trace
headings touched histogram ticks. Three METABRIC coefficient-trace pages
also had overlapping long covariate labels.

The renderer now uses compact vertical fold-metric labels, aligns rotated
runtime labels to the right, and allocates proportional-hazards panel heights
by covariate count. Trace headings sit above the axes; long covariate labels
wrap horizontally without splitting categorical names. These changes affect
presentation only. Source evidence, numeric values, failed diagnostic outcomes
and claim gates remain unchanged.

The three corrected overview figures and the corrected METABRIC normal-prior
coefficient trace passed native-size visual inspection. The complete public-CLI
render is in `~/bayes-cox-runs/render-equivalence-20260927/refactored_v3/`.
The exhaustive comparison is `../recovery/2026-09-27-final-layout-equivalence.json`
(SHA-256 `1cf4a96041a293340dd140971b0e830ddd78c979bf9e8e1a5ac249005549c186`).
It retains all 881 original paths and adds the same five documented outputs.
Thirty-six original files remain byte-identical. The 845 changed files include
the seven previously documented changes and 838 presentation-only changes:
832 trace PDF/PNG files and six corrected overview PDF/PNG files. No unexpected
change or missing output exists. Every numerical CSV/LaTeX table retains its
original bytes except the previously documented primary-contrast tables.
The bundle verifier accepted all 885 registered outputs, their exact original
source hashes, explanation reference and unchanged current renderer code.
The full replacement review passed all 426 single-page PDFs. All 419 changed
pages (416 traces and three overviews) were actually visually reviewed;
seven unchanged overview pages reused their exact previously passed hashes.
All 30 baseline layout defects are resolved, with no observed clipping,
overlap, truncated feature labels or broken glyphs. All 850 font records are
embedded with Unicode mappings, and all page boxes pass. Conservative
font-metric bounds warnings remain separate from actual visual defects;
the visible glyphs were reviewed. The final per-file record is
`../recovery/2026-09-27-final-pdf-qa.json` (SHA-256
`d1ee0d502d26a28c2ee3e3681a779aafd251cdcb8d2a1e7004b28e2e68cd6dd5`).
The final programme bundle will additionally include completed robustness and separate
post-hoc sampler evidence, and will require its own hash-bound visual QA.
