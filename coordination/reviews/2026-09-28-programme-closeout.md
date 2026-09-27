# Code/results programme close-out — 2026-09-28

Scope: the interrupted refactor, exact reproduction, frozen robustness,
separate ADR-032 sampler sensitivity, final reports, evidence preservation
and Ravi's remote continuation. The new thesis extensions are future tasks.
Overleaf, supervisor sign-off, paper submission and DOI minting are excluded.

## Verified evidence

The numerical programme used sealed code
`11f86ced8735b32767debb58f3cbbefbb5a7b8e6` in the exact 259-package macOS
arm64 lock. All 90 source/script hashes remained unchanged. The coordinator
and all numerical stages exited successfully. Strict final analysis and
rendered-lineage verification passed.

| Evidence | Verified outcome |
| --- | --- |
| Original confirmatory | 450 recorded cells: 430 complete, 20 diagnostic failures; unchanged |
| Exact reproduction | 450/450 cells match every non-timing field; own content hashes also validate |
| Frozen robustness | 825 recorded cells: 770 diagnostic passes, 55 failures |
| Separate sampler sensitivity | 75/75 diagnostic passes; nine estimable contrasts |
| Final PDF review | 428 PDFs/pages passed; 426 exact passed V3 hashes reused, two new PDFs actually inspected |
| Remote result restoration | All ten assets and 2,498 archive members verified; 2,503 restored files including metadata |
| Remote audit archive | All three assets and 899 members verified; archive is 496,134,676 bytes |

The original primary family remains incomplete: five of nine contrasts are
estimable. The separate sampler sensitivity has Holm-adjusted p-values of
1.0 for all nine contrasts and every corrected interval includes zero.
It cannot replace the original failed cells or complete their primary family.
No superiority or equivalence conclusion follows.

The explanation artifact is unchanged at SHA-256
`120984c7edfac468f471b9f500470623689b2647e4bde56d271cc9623346ecd5`.
It has 1,845 comparisons, including 102 failed convergence comparisons among
1,640 evaluable comparisons. Its global stability claim remains prohibited.

## Robustness interpretation review

Every direct and difference-in-differences row was reviewed for the actual
accepted/planned pair counts, available estimate, effect direction and interval.

| Analysis | Rows | Estimates available | Full planned pairing |
| --- | ---: | ---: | ---: |
| Design/hyperparameter direct effects | 45 | 39 | 31 |
| Feature/missingness direct effects | 30 | 28 | 22 |
| RQ2 direct effects | 54 | 54 | 42 |
| All direct effects | 129 | 121 | 95 |
| Difference-in-differences | 45 | 45 | 33 |

Eight direct rows remain unavailable; 26 direct and 12 difference-in-differences
estimates use partial pairing. Of the direct rows, 115 intervals include zero,
four are wholly positive, two wholly negative and eight are unavailable.
Of the difference-in-differences rows, 39 intervals include zero and three
are wholly positive and three wholly negative. These are descriptive stored
intervals. No robustness p-values are stored or inferred, and no uniform
H2 support or general robustness claim is asserted.

The METABRIC five-imputation sensitivity averages predictions before computing
metrics. Numeric imputations use distinct seeded training-fold posterior
sampling and categorical values use training-fold mode. This does not form
one Bayesian posterior propagating covariate-imputation uncertainty.

PH assessment retains within-fit Holm adjustment. METABRIC age and NPI reject
in 25/25 outer fits, ER-positive in 13/25, LumA in 11/25 and claudin-low in
21/25. WHAS500 systolic blood pressure rejects in 2/25; no GBSG2 covariate
rejects after adjustment. Frequencies across dependent outer fits are
descriptive; rare dummy levels have their actual denominators recorded.
Supported violations constrain PH interpretation. No time-varying replacement
model was introduced.

## Visual review and packaging

The final QA rechecked actual lineages, PDF identities, page boxes and embedded
Unicode fonts. Two new PDFs received full-page inspection; the tall robustness
overview additionally received native label and axis-region inspection. Its
effect types are identified in the separate direct and difference-in-differences
tables. No clipping or overlapping labels was observed. All earlier V3 layout
repairs were reused only for identical PDF hashes.

The first packaging attempt stopped before creating assets: an identical
copied explanation file had a different absolute path from the rendered
optional-source lineage. The revised seal uses the original unchanged
single-file explanation directory. The first seal and correction record are
preserved in the [close-out support archive](../recovery/2026-09-28-closeout-support/programme-audit-evidence.tar.gz);
no scientific code, source data, output, rendered lineage or QA
bytes were changed to bypass verification.

## Remote availability and student restoration

- [Original source](https://github.com/ravivramchandani/Bayesian-COX/releases/tag/confirmatory-v1-44b6085)
- [Verified programme](https://github.com/ravivramchandani/Bayesian-COX/releases/tag/results-programme-20260927-11f86ce)
- [Supporting visual QA, probes, helpers and logs](https://github.com/ravivramchandani/Bayesian-COX/releases/tag/results-programme-audit-20260928)

The repository remained private. New assets were uploaded as drafts, downloaded
into fresh directories, compared with local SHA-256 inventories, fully verified
and then published. Published inventories retain the same asset identities,
names and sizes. Both new Git tags independently resolve to the sealed full
commit. The original release was not modified.

A fresh GitHub clone downloaded and restored the original 455-file source
through `restore_confirmatory_release.py`. Its own supplementary restore helper
then restored the downloaded programme to a new directory and verified every
member and original-source inventory. No source results were copied from the
original working folders, and no models were fitted. The exact environment
verifier and Ruff passed in the fresh clone. This tests relocation on the
current Apple Silicon Mac with the existing lock environment; it is not a
second-physical-laptop or new-environment installation test.

[Ravi's guide](../../docs/ravi_handoff.md) records the exact install, download,
restore, checks, paths and next tasks. Large evidence stays in private releases;
compact counts, content hashes, asset identities and verification receipts are
in [the close-out record](../recovery/2026-09-28-programme-closeout.json) and
[the numerical summary](../recovery/2026-09-28-numerical-evidence-summary.json).
The earlier checkpoints, probe chronology and historical failures are retained.

T-140–T-144 and T-181 computation/review are complete with these outcomes.
T-134's original complete-family gate remains unmet. T-135 includes later
thesis wording/sign-off; T-147 includes later extension evidence and approval.
The next scientific step is T-180's actual frozen extension addendum, followed
by T-182–T-185/T-189 and separate rendering/review T-186. The independent
comment/docstring documentation pass is still tracked in HANDOFF step 12.

## Repository checks

`make test` passed all 270 tests in 48.44 seconds. Separate coordination
schema validation, Ruff, local guide links and `git diff --check` passed.
The compact validation receipt is `coordination/recovery/2026-09-28-closeout-validation.json`.
No Overleaf file was edited.
