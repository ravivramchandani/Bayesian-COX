# HANDOFF

State needed to resume work in a new session or on another machine.

Updated: 2026-09-27

## Current checkpoint — resumed after reboot

The owner requested completion of all remaining code/results tasks. At
07:51:46 UTC (20:51 Auckland) on 2026-09-27, execution resumed on this Mac
after its reboot had stopped every earlier numerical process. The exact
259-package runtime, unchanged frozen checkout and all 90 sealed code hashes
were verified before restarting. No completed cell was rerun or removed.

- Robustness resumed from 551/825 stored cells: GBSG2 255, WHAS500 270,
  METABRIC 26. Six missing-cell claims were recorded and released; the 551
  claims for saved cells were retained.
- Full reproduction resumed from 154/450 saved cells: GBSG2 150 and
  METABRIC 4. The checkpoint verifies these refits before submitting only
  the remaining 296 cells. No mismatch had been reported at restart.
- Sampler sensitivity remains queued after robustness, with 0/75 cells.
- Six frozen workers are PIDs 3362–3367; supervisor PID 3372 owns the final
  official robustness resume. Coordinator PID 3374 runs the sealed programme;
  `caffeinate` PID 3376 prevents idle sleep during its lifetime.
- Fresh launcher logs are in
  `~/bayes-cox-runs/logs/resume_20260927T075146Z/`. Earlier logs and PID records
  were copied there and hash-checked before restart. Internal programme logs
  append to their existing files.

The restart receipt is preserved in
`coordination/recovery/2026-09-27-restart-checkpoint.json`; external recovery
tools are in the matching restart-tools archive and hash manifest. The current
monitor reads `~/bayes-cox-runs/logs/current_resume.json`, rather than historical
PIDs. Inspect actual command lines before any further restart. The cross-laptop
instructions remain available in
`coordination/reviews/2026-09-27-cross-laptop-continuation.md`; no evidence was
transferred and no second laptop run was launched.

Numerical completion, final rendering, actual final visual QA, claim review,
packaging, isolated restore and private release remain required. The older
checkpoint below records historical state, not current process ownership.

## Earlier session checkpoint — numerical jobs left running

The owner wrapped up the interactive session on 2026-09-27 and explicitly
requested that the detached numerical jobs keep running. This pauses
interactive work; it does not stop or restart any fit. The checkpoint at
03:18 UTC (16:18 Auckland) is preserved in
`coordination/recovery/2026-09-27-wrapup-checkpoint.json`.

- Robustness: 549/825 stored cells. GBSG2 has 255/255, WHAS500 has 270/270,
  and METABRIC has 24/300. These are file counts, not diagnostic pass counts;
  final aggregation and strict completion verification remain pending.
- Full reproduction: 149/450 saved refits, all currently in GBSG2. No
  mismatch is reported; the complete 450-cell equality report is pending.
- Post-hoc sensitivity: 0/75; queued after completed robustness verifies.
- All six robustness workers, both reproduction workers, supervisor PID
  40646, coordinator PID 57940 and its `caffeinate` PID 57941 were active.
  All 90 sealed source/script hashes still matched commit `11f86ce`.
- Integrated code, 270-test validation and the passed 426-PDF base review
  are complete. Final numerical evidence, rendering, visual QA, claim review,
  packaging, restore verification and private release remain unfinished.

Resume by reading this checkpoint and inspecting the actual live state:

```bash
/Users/macuser/miniconda3/envs/bayes-cox-lock-verify-20260815-b/bin/python -B \
  /Users/macuser/bayes-cox-runs/harness/monitor_programme_once.py
```

Do not launch another coordinator or manually finish robustness while the
existing processes remain active. The coordinator proceeds automatically
through the numerical stages and final rendering. Its final
`~/bayes-cox-runs/continuation-20260927/programme_analysis_verified.json`
means analysis/rendering verification is complete and actual final visual QA
is still required. If `programme_failure.json` exists instead, inspect its
stage log before deciding how to resume; retain all existing evidence.

The next interactive steps are:

1. Strictly verify completed 450/825/75 evidence using the coordinator gates
   and external `~/bayes-cox-runs/harness/summarize_programme_evidence.py`.
   The helper refuses incomplete evidence and preserves scientific failures.
2. Follow `~/bayes-cox-runs/final-pdf-qa-preparation-20260927/README.md`.
   `final_pdf_qa.py` compares both final bundles with the passed V3 inventory,
   checks their actual PDF hashes, boxes and fonts, and rasterizes every new
   or changed page. Reuse only exact passed PDF hashes; actually inspect all
   remaining pages before producing a passed record.
3. Create the actual visual-QA-backed release seal for all seven evidence
   roots, package it with `scripts/package_programme_release.py`, verify an
   isolated restore, and upload a new private supplementary release. Leave
   the original confirmatory release unchanged; download and hash-check the
   new assets before closing the programme.
4. Update the final factual claims and task status, run the required checks,
   and commit/push the close-out. Overleaf edits remain outside this scope.

The four external resume helpers are preserved in
`coordination/recovery/2026-09-27-resume-tools.tar.gz` with per-file hashes in
the matching manifest. If a helper is missing, extract it to an external
directory. Preserve the frozen checkout, sealed programme checkout, original
results, V3 render and full V3 QA records; they are required source evidence.

## Recovery checkpoint

The interrupted work was inspected and preserved on 2026-09-27. The five
existing main commits through `6c037a8` were pushed, and the unfinished model,
confirmatory and explanation changes were committed to three remote WIP
branches. Their completed modular implementations are now integrated; the
original checkpoints remain preserved. The initial branches, validation and
runtime snapshot are in
`coordination/reviews/2026-09-27-recovery-audit.md`.

An archive and per-file hashes under `coordination/recovery/` preserve the
external runtime harness, initial horseshoe investigation and six-cell
baseline reproduction report. Running production outputs remain in the
frozen worktree. The Overleaf repository is clean and matches its remote.

## Active programme — refactor, completion and reproduction

Owner instruction of 2026-09-27, which supersedes the "stop and wait" step
in the 2026-08-16 sequence below:

- make this repository the single script-based pipeline; the external
  notebook is not ported;
- simplify and document the code so a new reader can follow it, without
  losing any function;
- correct errors and inconsistencies, run the paused downstream stages, and
  update the coordination files;
- do not edit the Overleaf thesis in this programme; record thesis
  corrections in `TODO.md` for later;
- commit and push at the end, with no AI co-author trailer.

### Standing owner instructions (2026-09-27)

- The thesis must contain every experiment a Q1 journal paper needs
  (ADR-036), with the scientific design refined by ADR-037. The paper is
  drafted later; the thesis is its planned evidence base, not a guarantee
  of acceptance or of no further reviewer-requested analysis.
- Do not edit the Overleaf thesis until the owner instructs.
- Only one agent works on the repository at a time.
- **Current state: core programme running; planning updates authorised.**
  - The owner's latest instruction requests plan and coordination updates
    following the scientific review. ADR-037 and T-180–T-186 record them.
  - The existing coordinator continues frozen robustness, full 450-cell
    regeneration and the queued 75-cell ADR-032 sensitivity, then rendering.
    Final visual QA, claim review, packaging, restore and private code/evidence
    release remain in the existing authorised programme.
  - The four new ADR-035 analyses are planned, not launched or queued by
    this coordinator. T-180's actual addendum and freeze remain unfinished.
    This planning update does not start their experiments.
  - Do not run `finish_robustness.sh`, restart active workers or launch a
    duplicate coordinator/sensitivity. The supervisor owns robustness finish.

At 10:01 UTC on 2026-09-27, the read-only monitor reported 603/825 robustness
cells and 205/450 reproduction cells, no reported reproduction mismatch,
0/75 sampler cells and a live coordinator. These counts are a dated progress
snapshot, not completion or diagnostic acceptance. Read the current monitor
for live state; do not use this snapshot to decide whether to restart.

Findings behind each step are in
`coordination/reviews/2026-09-27-codebase-audit.md`.
Completed integration gates and their evidence locations are in
`coordination/reviews/2026-09-27-integrated-code-verification.md`.

### Established facts

- Commit `e824c1b` (2026-08-31) replaced the raw cohorts with output of the
  former synthetic fallback, restored pre-2026-08-14 files and wrote random
  cells into the frozen run directory. Revert `2e55c0b` restored the
  `4eeb1ac` tree. The frozen run verifies there and 170 tests pass in the
  lock environment.
- All 80 frozen inputs are stored byte-for-byte in commits `95af081`,
  `44b6085`, `4eeb1ac` and `2e55c0b`. This lets the frozen evidence be
  verified against a checkpoint commit instead of the working tree.
- ADR-030 is integrated in release restoration, completed confirmatory
  resume, robustness provenance and evidence verification. Original code is
  verified against checkpoint `44b6085`; live protocol, raw data, manifest and
  lock files retain their frozen bytes. New runs record every current source
  and script file. Unfinished frozen robustness continues only in its
  unchanged original checkout and runtime; current code cannot mix into its
  cells.
- Primary results: the five estimable contrasts have maximum |ΔIBS| approximately 0.00034 and
  p ≥ 0.49. The smallest available p exceeds 0.05/5. Under Holm's
  step-down procedure, no estimable contrast can therefore be rejected,
  whatever the four missing p-values are.
- The external notebook (2026-09-26) builds Phase 2 on the synthetic CSVs.
  Phase 3 uses the real cohorts, but it evaluates one outer fold and 7 of 18
  model–cohort pairs, using metric values carried over in the session. The
  repository pipeline supersedes it.

### Plan and status

1. [ ] Run robustness (T-140–T-143) and explanation (T-144) production with
   the frozen code, from a detached worktree of `2e55c0b` outside iCloud
   (`~/bayes-cox-runs/frozen`), in the lock environment.
   - Explanation: done 2026-09-27. Output:
     `~/bayes-cox-runs/frozen/reports/explainability/confirmatory_v1_confirmatory_cdcdcee84651_explainability_v1.json`
     (SHA-256 `120984c7…6ecd5`). It made 1,845 comparisons; the convergence
     summary is `failed`, so no claim is permitted.
   - Robustness: started 2026-09-27 in
     `~/bayes-cox-runs/frozen/reports/robustness/confirmatory_v1_robustness_robustness_702d93af33bf/`.
     Six workers run `~/bayes-cox-runs/harness/shard_worker.py`, which runs
     the unmodified `run_robustness.py`. The worker claims each cell with a
     lock file in `~/bayes-cox-runs/robustness-claims/` and stops before
     aggregation. Logs and PIDs are in `~/bayes-cox-runs/logs/`.
   - Resumed supervisor PID 3372 runs `scripts/wait_for_robustness.py` and manages
     the final unsharded official `--resume` pass automatically after the
     workers finish. That pass verifies the original freeze, completes any
     missing cells and writes aggregates and `completion.json`. Do not launch
     a duplicate manual finish. Logs are in `~/bayes-cox-runs/logs/`.
2. [x] Build a reproduction harness that reruns one cell and compares it
   with the frozen record: `scripts/reproduce_confirmatory_cells.py`. The
   baseline on unchanged code reproduced the quick selection exactly.
   Robustness equivalent: `~/bayes-cox-runs/harness/check_robustness_cell.py`.
   A sharded production cell matched a fresh unsharded refit exactly.
3. [x] Integrate checkpoint-bound frozen-evidence verification (ADR-030).
   Release restoration and completed confirmatory resume verify the actual
   450-cell run read-only. Robustness has current-code manifests, safe resume
   separation and `verify_completed_robustness_run`, which checks the exact
   frozen 825-cell/885-fit blueprint, source inputs, cell identities and all
   recorded hashes without refitting.
4. [x] Refactor for readability, module by module. Tests and required
   equivalence gates passed. The rules and gates are in
   `coordination/briefs/2026-09-27-readability-refactor.md`.
   - Models: all six reference refits matched every non-timing field,
     including the horseshoe's three failed diagnostic attempts.
   - Explanation: the original SHA-256 `120984c7…6ecd5` reproduced exactly;
     its negative convergence finding remains unchanged.
   - Confirmatory: all 450 stored cells reproduced the three aggregate files
     byte for byte; the six quick-selection cells and four specified
     additional refits matched exactly.
   - Robustness: three stored production cells covering all three priors
     matched exactly. Rehashed wrong-cell identity, condition, raw-data hash
     and status checks reject corruption.
   - Rendering retains all nine primary contrasts, explicitly unavailable
     tests and the separate ADR-033 bound, and produces thesis-ready LaTeX.
5. [x] Retire the legacy pilot execution lane under ADR-034. Historical data
   and results remain in place, retired source remains in Git history, and
   active tests use real raw cohorts with fold-local preprocessing.
6. [ ] Regenerate the 450-cell run with the refactored code and compare it
   with the frozen artefacts (the ADR-026 reproduction claim). The full
   450-cell regeneration launched at 13:41 Auckland time on 2026-09-27 from
   sealed commit `11f86ced8735b32767debb58f3cbbefbb5a7b8e6` with two workers.
   Its complete 450/450 equality report remains pending; selected module
   gates and pure aggregate reproduction do not complete this task.
7. [x] Render the frozen results tables and figures, including the Holm
   family-completion bound. The full old/new comparison retained 874 identical
   files, seven intended changes and five additions, with no missing output.
   See `coordination/reviews/2026-09-27-rendering-refactor-verification.md`.
   The subsequent full 426-page review found 30 legacy layout defects.
   The complete replacement bundle passed all 426 PDF pages, recorded in
   `coordination/reviews/2026-09-27-full-pdf-review.md`.
   A final bundle incorporating completed robustness remains required.
8. [ ] Complete the labelled post-hoc horseshoe sensitivity under ADR-032.
   Initial investigation and seven target-acceptance probes are complete;
   `scripts/run_horseshoe_sampler_sensitivity.py` implements the separate
   75-cell refit and nine-contrast analysis. Production has not started; the
   coordinator queues six workers after frozen robustness is complete.
9. [ ] Finalise documentation and evidence packaging. Engineering status,
   architecture, decisions, invariants and recorded thesis corrections are
   updated. Final run identifiers, claims, rendered bundles and visual QA
   remain to be recorded after production verification.
10. [ ] Commit and push all verified continuation work. Recovery and completed
    code checkpoints have been pushed; final production close-out remains open.

11. [ ] Thesis extension experiments under ADR-036/ADR-037; T-180–T-186 in
    `TODO.md`. The four new analyses are not part of the running coordinator.
    Dependencies:
    - freeze the actual new-analysis addendum (T-180) before their own results;
      reference existing ADR-032/ADR-033 evidence with its actual chronology;
    - T-181 is the same sensitivity as step 8, already queued after robustness
      and independent of T-180; do not run it twice;
    - after T-180, run fair inner-CV penalised-Cox comparators (T-182) and
      censoring-aware decision curves from stored predictions (T-184);
    - after T-180/T-181, run the precisely specified Piironen–Vehtari clinical
      variant (T-183), with comparable sampler settings and unchanged gates;
    - after T-180/T-182/T-183, run matched METABRIC clinical-only and clinical-
      plus-expression arms (T-185), explicitly including the new variant;
    - render and actually review the separate extension bundle (T-186).

    Paper drafting and submission are deferred until after the thesis.

Tick each box when its step is complete, and record where its outputs are.

`scripts/complete_results_programme.py` is the automatic continuation entry
point. Launch it once from a clean detached checkout of the final integrated
commit, with external original-evidence paths and a separate output directory.
It records the sealed code/source identity, runs the full 450-cell reproduction
with two workers alongside the six frozen robustness workers, and waits for
supervisor PID 3372 to finish robustness. It then verifies the exact 825-cell
completion, runs all 75 post-hoc sampler cells with six workers, verifies the
separate inference and renders both final bundles. Its verified-analysis
record still requires final visual QA and evidence packaging; it does not
complete thesis writing. The README records the machine-specific invocation.

The resumed coordinator is PID 3374; `caffeinate` PID 3376 prevents idle sleep
for its lifetime. The immutable checkout is
`~/bayes-cox-runs/refactored-programme-20260927/`, and outputs are in
`~/bayes-cox-runs/continuation-20260927/`. Its manifest pins all 90 current
source/script files and the exact original explanation hash. Preflight
verified the frozen run, unchanged study inputs and locked runtime before
starting the reproduction stage. The log is
`~/bayes-cox-runs/logs/resume_20260927T075146Z/programme.log` and its PID file
is alongside it. Do not edit that checkout or launch a second coordinator.
Full reproduction, robustness aggregation, sampler results, final visual QA
and packaging remain pending until their actual completed evidence verifies.

Administrative deadline: the live programme in `TODO.md` runs from 2026-08-17
to 2026-11-30. This 15-week schedule supersedes the earlier 26-week dates for
project management without changing any frozen analytical method or claim
gate.

## Exact runtime

On the original machine, use the verified locked environment directly. The
absolute path below is machine-specific; on another machine, install
`conda-lock.yml` as `bayes-cox-clean` using the README instructions. The older
environment named `bayes-cox` is not lock-equivalent because its PyTorch
package route differs.

```bash
EXACT_PY=/Users/macuser/miniconda3/envs/bayes-cox-lock-verify-20260815-b/bin/python
$EXACT_PY scripts/verify_environment.py
$EXACT_PY -m pytest -q
$EXACT_PY -m ruff check .
```

Verified 2026-08-16: 170 tests pass and Ruff is clean. The exact macOS arm64
lock contains 259 packages and has SHA-256
`1921895d4a404fc99e848d69ccd4a3f6639a3d1610315c82ecd463ed4bcdfb57`.
Python is 3.11.15; h5py 3.16.0 uses matching HDF5 2.1.0 build/runtime
libraries. PyMC chains run sequentially (`cores=1`) on this machine.

## Authoritative status

The design, statistical analysis plan, ethics/data-use position, licensing
position, journal targets and supervisor-decision track are owner-approved.
Q-001 through Q-006 are answered and must not be asked again. No institutional
ethics reference or named clinical reviewer was supplied, so neither may be
invented. Clinical interpretation without an authoritative source is omitted.

The confirmatory engineering foundation is implemented and reference-tested:
fold-local preprocessing, paired repeated outer folds, compact inner tuning,
training-only horizons, IPCW metrics, explicit calibration, corrected paired
inference, immutable cell/prediction schemas, DeepSurv, full Bayesian quality
gates, frozen-cell explanation, lean robustness and pure rendering.

Implementation is not scientific evidence. The final-input result-blind
rehearsal completed all 18 cells using only status/timing inspection, and the
deterministic resource rule retained five repeats. The write-once protocol
freeze exists unchanged at `config/protocol_freeze.json`; all 80 recorded
inputs verify against the original checkpoint, while live methodological
inputs retain their frozen bytes. The freeze content SHA-256 is
`3b5e1042d592ebb6fade0a4a76c1f0d31ce9c0c1cfc08357be46f163f037d2ca`.

The frozen confirmatory execution is complete at
`reports/confirmatory/confirmatory_v1_confirmatory_cdcdcee84651/`. The frozen-
run verifier accepted the exact 450-cell grid, content hashes, aggregate
hashes, complete-cell metric and prediction lineages and unchanged protocol
freeze. Of the 450 cells, 430 completed and 20 exhausted the prespecified
diagnostic remedies.
All failures are horseshoe fits: 18 in GBSG2 and two in METABRIC. WHAS500 and
every non-horseshoe arm completed all 25 folds.

The inferential evidence is deliberately incomplete. `inference.json` records
`status: incomplete` and `holm_family_complete: false`: five of nine primary
contrasts have all 25 paired folds, while the two GBSG2 and two METABRIC
horseshoe contrasts have no confirmatory inference. No complete-family
superiority, equivalence or multiplicity-controlled claim is accepted.
Robustness production is running from the unchanged frozen worktree.
Confirmatory explanation production completed, but its convergence gate
failed and it permits no RQ3 claim. See the recovery checkpoint above.

## Data state

The three confirmatory raw files and their exact counts/hashes are complete:

| Cohort | Records/events | Derived SHA-256 |
|---|---:|---|
| GBSG2 | 686 / 299 | `2158b777d27ecfb69b187d3cbcad13fd1eb92d626935c528a4465fea6490ae5f` |
| WHAS500 | 500 / 215 | `4bb01775c04eca11d7f06d6e5dfebd0a5cce75aa7e73fe4261732385be106fcc` |
| METABRIC | 1,980 / 1,144 | `731ea80ce0240cb6aa96ffb0f4a3bb379615202966c954512664bef02b29545c` |

The manifest pins upstream files, hashes, citations, endpoint coding and
licence limits. Public release defaults to metadata, hashes and retrieval
scripts; the project MIT licence does not relicense patient data. METABRIC
database material is ODbL. The earlier 1,904-row METABRIC file remains pilot
input only.

Primary features are the eight raw GBSG2 predictors, nine documented
admission-time WHAS500 predictors and the baseline/pathology METABRIC set with
age, NPI and six categorical variables. Published-full, engineered,
NPI-component/stage and treatment-augmented representations are sensitivities.

## Evidence boundary and frozen-run state

The 15 legacy model/cohort fits and 18 legacy explanation comparisons are
exploratory pilot evidence only. They cannot support confirmatory superiority,
equivalence, calibration, prior-asymptotic or clinical-feature claims.

The legacy rehearsal stored all 18 planned cohort/model cells but only 14
completed and remains unusable. The fresh predecision rehearsal at
`reports/confirmatory_rehearsal_predecision_20260815/` completed 18/18 under
the exact reduced workload. Only console completion and runtime were inspected;
the rounded timing bound mandates five repeats. Its input hashes precede the
resulting status/decision update, so it cannot itself create the final freeze.
The subsequent final-input rehearsal at
`reports/confirmatory_rehearsal_final_20260815/confirmatory_v1_rehearsal_df0135acdf99/`
also completed 18/18 and is the timing evidence named by the write-once freeze.
No comparative rehearsal effect was inspected or admitted. Do not inspect or
report any rehearsal performance effect.

The production completion record has content SHA-256
`03870efdae3134305794ea977fd9cbe7913c0d693f1b009337546319aa03bee1`;
the manifest content SHA-256 is
`9ec040841b4751ee3064c93d21d5069ed27bf3bfd6641f0dfffff76557bbf9f7`.
The aggregate artefacts and all 450 cell files are covered by the completion
inventory. The 20 failed-diagnostic cells each contain all three frozen fit
attempts and are excluded from `fold_metrics.csv` and inference. Preserve this
failure outcome; do not add a remedy or selectively rerun a cell within the
current freeze.

The complete 552 MB evidence directory is available to authorised repository
collaborators as the private GitHub Release `confirmatory-v1-44b6085`:
<https://github.com/ravivramchandani/Bayesian-COX/releases/tag/confirmatory-v1-44b6085>.
Its archive SHA-256 is
`0dbb745b82e5998b5aabc4bb3f05b28f87e00ba2851101a8accb83d447ddf34b`.
From the root of a clone with the exact environment installed, run:

```bash
conda run -n bayes-cox-clean python scripts/restore_confirmatory_release.py
```

The helper downloads both assets, checks the supplied SHA-256, rejects unsafe
archive paths, verifies every frozen artefact and confirms all 80 checkpoint
input blobs plus unchanged live study inputs before installing the run beneath
`reports/confirmatory/`. It never overwrites an existing run and instead
verifies it in place.

The available complete contrasts and descriptive aggregates are frozen
production evidence, but the primary family is not complete. They may be used
only with wording that makes the diagnostic attrition and incomplete family
explicit. They must not be presented as though all nine primary contrasts or
their Holm adjustment were available.

The robustness runner is intentionally large even after scope control: at
five repeats it plans 825 checkpoint cells and 885 Bayesian fits, with RQ2 on
outer folds 1–2 and design/feature sensitivities on fold 1. It performs no
calibration bootstrap in IBS-only sensitivity cells and refuses production if
a timing-only projection from completed confirmatory cells exceeds 72 hours.

Rotterdam transport and the ADEMP simulation are permanently dropped under
ADR-025. They are not delayed tasks and cannot be reintroduced after results.
The evidence supports no external-validation or cross-domain generalisation
claim.

## Thesis state

The adjacent Overleaf repository now has a focused introduction and
literature review plus a substantial pre-freeze methodology and reproducibility/
diagnostic appendices. Its bibliography has 36 retained, cited entries: 30
with DOI records and six authoritative web records. The results, conclusion
and abstract remain intentionally unwritten. Frozen production evidence now
exists, but the primary inferential family is incomplete and the owner has
paused post-confirmatory thesis writing. Do not populate these chapters from
pilot or rehearsal effects, or start the production-results rewrite without a
new instruction.

After the methods package was added, a LaTeX/BibTeX build produced a 70-page
A4 PDF with no undefined citations/references, LaTeX warnings, or overfull/
underfull boxes; fonts are embedded and `make jargon` passes. Methodology and
appendix pages were visually inspected. Later results, conclusion and final
abstract writing must use renderer outputs and frozen result keys, not manually
transcribed values.

## Historical close-out sequence — superseded by the active programme

1. On a new machine, use the README restoration command and require the
   reported 450-cell, completion-hash and 80-input checks to pass. The source
   checkpoint and private evidence Release are already published; do not rerun
   or selectively reconstruct the confirmatory analysis.
2. The prospective `docs/study_protocol.md` is an immutable pre-execution
   record. Read it as the frozen analysis plan together with this close-out,
   which records the observed diagnostic attrition and inferential boundary.
3. The former downstream pause is superseded for code/results work by the
   2026-09-27 instruction above. Continue robustness, reproduction, sensitivity
   and evidence rendering. Overleaf chapter writing remains excluded.
4. On resumption, retain the prespecified failed-fit outcome and incomplete
   primary-family status in every downstream table and claim. A methodological
   change requires a new result-blind rehearsal and freeze; it cannot be folded
   into this run.

Do not edit live frozen methodological inputs. ADR-030 permits code and
ordinary-documentation changes while their original checkpoint blobs remain
verifiable. A methodological change cannot enter the completed confirmatory
analysis; the acceptance-only sensitivity is separate under ADR-032.
