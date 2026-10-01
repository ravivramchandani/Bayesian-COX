# Focused clinical methods evidence and private transfer

This is the operator guide for producing, transferring and scientifically
replaying the focused evidence. Those steps are already complete on the
original Mac. Ravi can read the [results note](clinical_methods_results.md)
and use the [beginner thesis guide](ravi_start_here.md) on any operating
system; he does not need this macOS arm64 procedure to write the thesis.

The completed private checkpoint is
[`clinical-methods-posthoc-20261001-eaebcd7`](https://github.com/ravivramchandani/Bayesian-COX/releases/tag/clinical-methods-posthoc-20261001-eaebcd7)
at analysis commit `eaebcd7b422e63cc7b0792cc8ac481f83a0080ba`.
Download its `inventory.json` and `part-000001.tar.gz` into a fresh directory
and use canonical inventory SHA-256
`3497558581a4fefb67eabcf8a2b215cec6f48e3654fe681679a2572f54378953`
with the restore command below. A fresh clone and download on the current Mac
passed the full scientific replay; a second physical laptop has not been
tested. The exact evidence is in the
[release receipt](../coordination/recovery/2026-10-01-clinical-methods-release.json).

This is the separate ADR-045 post-hoc clinical subset. It is not completion
of the frozen 1,625-fit extension or a change to Ravi's submission-first
thesis. The exact scope and 225-cell roster were committed before this
focused performance analysis. The narrower scope is outcome-aware and must
be labelled that way. No new fit, Overleaf edit, paper submission or DOI is
part of this procedure.

Use the exact Apple Silicon lock described in [Ravi's handoff](ravi_handoff.md)
and a clean analysis checkout containing these scripts. The original fitting
checkout must be clean at commit `119476fef55b1eeb690527f234c1423440720d45`.
The existing private confirmatory and supplementary-programme releases
provide the original primary and ADR-032 sampler reference runs; restore them
as in Ravi's handoff. Keep the original extension source run and its separate
reproduction directory unchanged. The verifier reads only the fixed 225
clinical penalised-Cox cells and nine selected saved refits. It does not need
the expression-matched Parquet for a clinical-only replay.
ADR-046 and `coordination/clinical_methods_baseline_evidence.json` bind the
earlier 450-cell exact-refit report and release receipts. The restored
baseline references do not provide raw posterior arrays for rederiving MCMC
diagnostics, so this study checks their stored diagnostic records and exact
refit agreement without claiming new raw-trace analysis.

Choose fresh paths on the mounted, case-sensitive APFS SSD for all new
evidence and transfer files. On this Mac, the current mount is
`/Volumes/BayesCoxRecovery20261001`; verify it is mounted and has space
before using it. The variables below are examples to fill from actual
restored/source locations. Do not run a second producer against the partial
extension run.

```bash
clinical_python=/path/to/exact-locked-env/bin/python
clinical_analysis="$PWD"                 # clean current project checkout
clinical_production=/path/to/clean-detached-119476f-checkout
clinical_source_run=/path/to/original-extension-run
clinical_reproduction=/path/to/original-extension-reproduction
clinical_primary=/path/to/restored-original-confirmatory-run
clinical_sampler=/path/to/restored-programme/sampler_run
clinical_home=/Volumes/BayesCoxRecovery20261001/clinical-methods-v1
mkdir -p "$clinical_home"

"$clinical_python" scripts/verify_environment.py \
  --lock-file conda-lock.yml --hash-file conda-lock.yml.sha256
"$clinical_python" scripts/verify_clinical_methods_subset.py \
  --production-code "$clinical_production" --run "$clinical_source_run" \
  --reproduction "$clinical_reproduction" \
  --report "$clinical_home/verification.json"
"$clinical_python" scripts/finalize_clinical_methods.py \
  --run "$clinical_source_run" --verification "$clinical_home/verification.json" \
  --primary "$clinical_primary" --sampler "$clinical_sampler" \
  --output "$clinical_home/analysis"
"$clinical_python" scripts/clinical_methods_release/render.py \
  --analysis "$clinical_home/analysis" --output "$clinical_home/rendered"
"$clinical_python" scripts/clinical_methods_release/qa.py prepare \
  --analysis "$clinical_home/analysis" --rendered "$clinical_home/rendered" \
  --qa-dir "$clinical_home/visual_qa"
```

Open each `visual_qa/page_renders/*.png` at full size and the contact sheet.
Check legibility, clipping, labels, interval direction, missing-pair markers
and the METABRIC limitation. Copy `review_template.json` to `review.json`
and enter a truthful named, timezone-aware inspection, four explicit figure
passes and the nine claim-boundary passes. A script cannot perform or infer
this inspection. The required claim wording is in
[`CLAIM_REVIEW.md`](../scripts/clinical_methods_release/CLAIM_REVIEW.md).
If an item fails, retain that evidence and render a new output directory
after correcting the source; do not overwrite the reviewed tree.

After the review is genuinely complete, seal and stage the evidence. These
commands require a committed, clean analysis checkout. Stage reruns the
scientific verification and final analysis before copying exactly 225 source
cells and nine refits; it does not certify the remaining extension grid.

```bash
"$clinical_python" scripts/clinical_methods_release/qa.py seal \
  --analysis "$clinical_home/analysis" --rendered "$clinical_home/rendered" \
  --qa-dir "$clinical_home/visual_qa"
"$clinical_python" scripts/clinical_methods_release/stage.py \
  --production-code "$clinical_production" --analysis-code "$clinical_analysis" \
  --run "$clinical_source_run" --reproduction "$clinical_reproduction" \
  --primary "$clinical_primary" --sampler "$clinical_sampler" \
  --verification "$clinical_home/verification.json" \
  --analysed "$clinical_home/analysis" --rendered "$clinical_home/rendered" \
  --qa-dir "$clinical_home/visual_qa" --output "$clinical_home/staged"
"$clinical_python" scripts/extension_release/package.py \
  "$clinical_home/staged" "$clinical_home/assets"
```

The generic package tool creates `inventory.json` and size-capped
`part-*.tar.gz` files. Record its printed canonical inventory SHA-256 in a
separate committed release receipt. Publish these files only to a **private**
GitHub release after the scientific and visual checks pass. Download from
that release into a fresh directory, supplying the independently recorded
digest to the verifier. The `verify.py` input directory must contain only
`inventory.json` and its numbered shards.

```bash
mkdir -p /path/to/fresh-downloaded-assets
gh release download clinical-methods-posthoc-20261001-eaebcd7 \
  --repo ravivramchandani/Bayesian-COX \
  --dir /path/to/fresh-downloaded-assets
"$clinical_python" scripts/extension_release/verify.py \
  /path/to/fresh-downloaded-assets /path/to/new-restored-focused-tree \
  --expected-sha256 3497558581a4fefb67eabcf8a2b215cec6f48e3654fe681679a2572f54378953
```

On the receiving Mac, use a fresh clone of the private code repository and
clean detached checkouts of both `production_code_commit` and
`analysis_code_commit` recorded in the restored `release_stage.json`. Restore
the two existing baseline releases independently as in Ravi's handoff. The
scientific replay works from the 225-cell restored subset and its nine
refits; it needs no other extension cells or matched expression data. Write
the new replay receipt outside the immutable restored evidence tree:

```bash
"$clinical_python" scripts/clinical_methods_release/verify_restored.py \
  --restored /path/to/new-restored-focused-tree \
  --production-code /path/to/clean-production-checkout \
  --analysis-code /path/to/clean-analysis-checkout \
  --primary /path/to/restored-original-confirmatory-run \
  --sampler /path/to/restored-programme/sampler_run \
  --report /path/to/new-external-restored-science-receipt.json
```

The sharded archive verifier checks transfer bytes and paths. The later
scientific replay rechecks every selected cell and refit, recomputes the
27-row family and descriptions against the restored baseline sources, and
verifies the preserved original visual-review receipt. A passed package or
local stage alone is not a completed remote handoff. TRIPOD+AI and PROBAST+AI
remain item-level manuscript review aids, not automatic compliance claims.
