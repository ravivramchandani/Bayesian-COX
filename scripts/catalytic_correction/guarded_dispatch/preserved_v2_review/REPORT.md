# Independent guarded-dispatch V2 delta review

The three demonstrated V1 counterexamples are closed in V2. One related material GD-R2 consistency gap remains: a sealed account-only original reuse can carry a decision that the pinned original classifier could never emit. This review is preparation evidence only; it does not adopt a dispatcher or approve any scientific run, freeze, scope, release, or retry.

The reviewed carrier is `/Users/macuser/bayes-cox-runs/extensions-20260928/generator_correction_guarded_dispatch_v2`. Its preparation receipt byte SHA-256 is `46a95785348e9f54379178caaf728fd863cccef3d133b2f5a3c8116aa5d9e9cc`, with 78 bound members, 79 files including the receipt, and exactly the two declared preserved directories. The capture, core, and read-only CLI pins are respectively `f82a7b8d2c65e829a7178c8fb230751bef193356e8589c22512ac229de944611`, `ee80c8e610f81b1cf7059c87d7cc4df80b964e6d76cd6c3144205f09add8bdc9`, and `7b19d4c7efa945d22e03cc779e1a1e64a06425f59a7d6b7d862097708ec501a9`.

## Material residual: GD-R2a, contradictory no-fit decision metadata

`guard_fit_dispatch.py:416–444` checks the exact decision keys, its content seal, identity, source/status, seed binding, and the reuse action/reference. It does not require the reuse branch's `missing_roles`, `changed_roles`, and `generator_failures` to be empty or its `tuning_record_reused_sha256` to be null.

In four independent mutations of an otherwise-valid fictional `failed_diagnostics` reused account envelope, I changed just one of these fields and recomputed the decision and cell seals. `account_only` accepted all four:

| Decision field | Injected contradiction | Actual result |
|---|---|---|
| `changed_roles` | `["model_sources"]` | Accepted |
| `missing_roles` | `["model_sources"]` | Accepted |
| `generator_failures` | `{"outer": "input_failure"}` with an accepted outer generator context | Accepted |
| `tuning_record_reused_sha256` | A non-null 64-character digest | Accepted |

These are impossible original reuse decisions under pinned `correction_fit_contracts.py:238–255`: failures choose retained input failure, missing roles choose unresolved, and changed roles choose a fit action; the tuning-reuse marker is populated only for `fit_changed_inputs_reuse_tuning`. The evidence is the genuine `reuse_probe.invocation.json`, raw stdout/stderr, and `probe_reuse_consistency.py`. Its actual subprocess return code is zero because the observation completed successfully; that return code does not mean the four candidates were rejected. No original or injected controller was called in this probe.

A bounded correction should reject these four contradictions before introduction and during semantic revalidation, preserving original success, failure, and diagnostic-failure reuse. Source inspection also shows that the terminal-input branch needs a null tuning-reuse marker (`guard_fit_dispatch.py:431–438`, original classifier `248–249`). This latter point is source-only, not an additional executed counterexample. Do not require terminal `missing_roles` or `changed_roles` to be empty: generator failures have priority in the original classifier and may legitimately coexist with those lists. Preserve the exact original retained-input-failure grammar, including the independent Boolean `original_outcome_pending`.

## Verified V2 corrections and preservation

- GD-R1: `immutable_output_roles` and `protect_output` cover all classified request, freeze, selection, arithmetic, source-code, preparation-tree, and review files. The launcher calls protection before `prepare_output` (`capture_guarded_dispatch.py:74–75`); the child calls it before owner/capture writes (`guard_fit_dispatch.py:1031`); the semantic reader protects both historical and physically resolved receiving roles plus actual map/authority files before creating its output (`1003–1008`). Only the intentional dispatch selection role `corrected_run` is exempt; read-only proof output protects it. Exact file siblings remain available. The three corresponding new fictional regression methods pass.
- GD-R2: the account envelope now has exact top-level fields and false numerical/completion flags, so the actual six corrected-fit-only fields and arbitrary score fields are rejected. Exact original references and statuses `complete`, `failed`, and `failed_diagnostics`, plus terminal-input accounts, remain accepted. The residual above concerns dependent decision consistency, not those top-level corrections.
- GD-R3: exact old account-pass fields, counts, flags, hashes, unique known inventory-prefix rows, retained/existing rows, and all four legitimate pending statuses are enforced. The historical cumulative record maps remain nested partial subsets rather than being forced equal to the final map. This preserves pending-then-terminal history and accounts resumed with `changed_inputs_waiting_for_authorized_phase`.

I independently ran all 34 fictional unit methods with a genuinely captured subprocess: actual return code zero, `Ran 34 tests`, `OK`. The original 23 test method ASTs remain exactly identical to V1 and to the preparation receipt; the additional 11 methods are separate. The producer's final unit, Ruff, and AST/compile captures were independently checked against their retained raw streams and final six Python source pins. Their actual return codes are zero; earlier producer failure captures remain present.

The complete V2 carrier, all 20 bound original sources, the original V1's complete 41-file carrier, the previous independent review's complete 11 files, the original classifier, and the two independent capture/probe sources were checked before and after both independent subprocesses: all 154 files are unchanged. Both preserved copies are exact byte matches. The six original imported source pins remain unchanged. Of the original core function/class ASTs, only `dispatch`, `validate_account_snapshot`, and `verify_guarded_dispatch_proof` changed; the four new helpers are separate. Only `launch` changed in the old capture functions; the read-only CLI is byte-identical. The already reviewed history, actual-return-code chain, remaining-pilot predicate, and no-fallback source/receiving mapping code retain their original ASTs.

## Scope and limits

I read V2's README, delta JSON, all changed runtime and fixture code, all 11 new regression methods, final producer captures, and the relevant pinned original predicates. The V1 full-source review supplies the unchanged-code baseline. Target runtime imports occurred only inside disposable fictional fixture tests; they did not run original controller/scientific/environment-checker code, read datasets/arrays/traces, query process owners, or write resident/source/real-run trees. I did not simulate a real receiving restore or certify a numerical result, release, retry, scope, or adoption.

Two exploratory read commands used nonexistent document/test names and returned code one; they were followed by reads of the actual `V2_DELTA.json` and `test_guarded_dispatch_regressions.py`. Expected `diff -u` return code one denoted source differences. These are read-attempt outcomes, not scientific or runtime failures, and are recorded in the final verification metadata.
