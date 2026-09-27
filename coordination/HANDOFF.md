# HANDOFF

State needed to resume work in a new session or on another machine.

Updated: 2026-09-27

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
   - Supervisor PID 40646 runs `scripts/wait_for_robustness.py` and manages
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
   450-cell regeneration has not launched; selected module gates and pure
   aggregate reproduction do not complete this task.
7. [x] Render the frozen results tables and figures, including the Holm
   family-completion bound. The full old/new comparison retained 874 identical
   files, seven intended changes and five additions, with no missing output.
   See `coordination/reviews/2026-09-27-rendering-refactor-verification.md`.
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

Tick each box when its step is complete, and record where its outputs are.

`scripts/complete_results_programme.py` is the automatic continuation entry
point. Launch it once from a clean detached checkout of the final integrated
commit, with external original-evidence paths and a separate output directory.
It records the sealed code/source identity, runs the full 450-cell reproduction
with two workers alongside the six frozen robustness workers, and waits for
supervisor PID 40646 to finish robustness. It then verifies the exact 825-cell
completion, runs all 75 post-hoc sampler cells with six workers, verifies the
separate inference and renders both final bundles. Its verified-analysis
record still requires final visual QA and evidence packaging; it does not
complete thesis writing. The README records the machine-specific invocation.

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
