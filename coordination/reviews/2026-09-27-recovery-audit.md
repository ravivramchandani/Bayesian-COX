# Recovery audit — 2026-09-27

The code project is `ravivramchandani/Bayesian-COX`; the separate thesis
repository is Overleaf project `6a750f3e68075fe560b0c306`. Both remotes were
fetched. The thesis is clean at `a5f026a` and has no unpushed changes.

## Work preserved

Five existing main commits, `0a115b3` through `6c037a8`, were pushed. They
record the completion/refactor programme, code and thesis reviews, shared JSON
I/O, a cell-reproduction script, and decisions ADR-030 through ADR-033.
These are preparation and investigation; the planned refactor is not complete.

Thirteen unfinished source files were preserved in separate pushed branches:

| Branch | Commit | State |
|---|---|---|
| `wip/models-refactor-20260927` | `6b41431` | Four modified model files; 593 insertions and 433 deletions. Bayesian fitting and diagnostics were reorganised. Evaluation/statistics and other model families are not refactored. |
| `wip/confirmatory-refactor-20260927` | `d6bd723` | Three new files, 483 lines. Cohort loading, options and evaluation were extracted, but the original pipeline remains active. The new package lacks `__init__.py`; its two submodule imports fail. |
| `wip/explanation-refactor-20260927` | `089efc1` | Six new modules, 1,759 lines. They import successfully but are not wired into the active explanation entry point. |

The fourth worktree, intended for rendering, was clean at `6c037a8` and
contained no implementation changes. None of the three WIP branches is merged
into main or has established frozen-output equivalence.

`coordination/recovery/2026-09-27-supporting-work.tar.gz` preserves 22
unmodified files: the four external runtime harness files, horseshoe
investigation scripts and diagnostic summaries, and the baseline quick
reproduction report. The adjacent JSON manifest records each file's SHA-256;
archive contents were checked against those hashes. This supporting material
does not replace confirmatory evidence. Active production files were left in
their original directories.

## Validation

The locked environment passed `scripts/verify_environment.py`. Main passed
170 tests, Ruff, and coordination schema validation. All 13 unfinished files
passed syntax compilation and Ruff. The model worktree passed 44 focused
model, metric, calibration and statistics tests. These checks establish code
health, not refactor equivalence.

All 80 recorded input blobs in checkpoint `44b6085` match the frozen run's
SHA-256 values. In main, the frozen decision log changed and `src/utils/io.py`
was added outside the recorded source inventory; live-tree verification is
therefore not a valid continuation route.

The preserved baseline reproduction report records six of six original-code
cells identical, excluding timing and the timing-dependent cell hash. It is
not evidence for any unfinished refactor. The package-specific reproduction
gates remain those in `coordination/briefs/2026-09-27-readability-refactor.md`.

## Verified evidence and live jobs

Snapshot: 2026-09-27 12:23:48 Pacific/Auckland. Runtime files are under
`~/bayes-cox-runs/frozen/reports/`.

- Confirmatory: all 450 cell hashes and three aggregate hashes match the
  completion record. There are 430 complete cells and 20 failed horseshoe
  cells: 18 GBSG2 and two METABRIC.
- Primary inference: five of nine contrasts have all 25 paired folds. The
  family remains incomplete; the smallest available p is 0.4934248731.
  No superiority or equivalence finding is established. ADR-033's separate
  post-hoc Holm bound must retain that label.
- Explanation: 1,845 comparisons from 205 accepted Bayesian cells. Its
  SHA-256 is `120984c7edfac468f471b9f500470623689b2647e4bde56d271cc9623346ecd5`.
  Of 1,640 evaluable convergence comparisons, 102 fail; `claim_permitted`
  is false. Report the negative gate outcome without changing the threshold.
- Robustness: 75 of 825 planned cells recorded, comprising 63 complete and
  12 failed diagnostics. Six workers are alive; 750 cells are not yet recorded.
  Aggregates and completion do not exist. Counts will change as workers run.
- Initial horseshoe investigation: seven target-acceptance 0.999 probes
  produced six passing fits. The full 75-cell post-hoc sensitivity accepted
  in ADR-032 has no production runner or completed run yet.

The explanation artefact and robustness production remain local. Final
evidence packaging through the existing private release route is outstanding.

## Remaining sequence

1. Let the six robustness workers finish. Then run
   `~/bayes-cox-runs/harness/finish_robustness.sh` once and verify the complete
   inventory, hashes, diagnostic exclusions and aggregates. Current pending
   claims belong to live workers and require no intervention.
2. Implement ADR-030's checkpoint-bound verification. Recording the decision
   did not change the verifier: current main still checks live inputs and
   rejects its added source file and changed decision log. Restore and run frozen
   downstream work from an unchanged checkpoint worktree in the meantime.
3. Finish the three refactors, retain compatibility exports and monkeypatch
   behaviour, pass every package gate, and integrate only verified changes.
   Complete rendering, robustness refactoring and pilot retirement; update
   architecture, invariants and build instructions.
4. Reproduce all 450 cells with the integrated code in a separate output
   directory. Run the full 75-cell horseshoe sensitivity separately under
   ADR-032; retain all failures and keep confirmatory evidence unchanged.
5. Generate tables/figures, review permitted claims, report the explanation
   convergence failure and package final evidence. No frozen explanation
   threshold may be relaxed after observing the outcome.
6. Resume thesis work as its own programme: apply the 19 recorded corrections,
   write Results and Discussion, Conclusion and the final Abstract, update
   appendices and front matter, then complete supervisor and final audits.
   Introduction, Literature Review, Methodology and both appendices have
   substantive drafts. Results is a heading, Conclusion is a template
   sentence, and the Abstract retains a result placeholder. Overleaf edits
   are excluded from the current code programme. The existing delivery
   deadline remains 2026-11-30.
