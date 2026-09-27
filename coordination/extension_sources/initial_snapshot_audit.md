# Bounded audit of copied extension code

Reviewed the external snapshot at `/Users/macuser/bayes-cox-runs/extension-code-review-20260928`, without reading or editing the shared project repository. The snapshot hashes are recorded in `snapshot_numeric_audit.json`. No new real scientific fit was run. Numerical tests used only the frozen synthetic R reference fixture; PyMC sampling was mocked to inspect construction and context isolation.

## Scientific checks passed

- `catalytic.py:35-69`: fixed and adaptive kernels, gradients, p+alpha-1 exponent, gamma scale/rate, kappa, and consistent omitted log(h0) match the executed reference probes.
- `catalytic.py:72-150`: weighted event terms and combined weighted risk denominators implement Breslow WME; tied/censored/multi-level encoded fixture coefficients and explicit merged-data absolute survival agree with actual authors/CRAN R results.
- `preprocessing.py:85-90`, `fitting.py:57-58`, `catalytic.py:117,147`: median-event-axis rate/time construction is dimensionally consistent; jointly rescaling times and inverse-rescaling the rate preserves prior kernels, WME estimates, and original-unit survival predictions in the fixture.
- `bayesian_extensions.py:138-148`: actual copied PyMC coefficient-prior log densities have the correct fixed/adaptive kernels. Gamma adds only a beta/tau-independent normalization constant; all probe density differences agree. The approximately 2.55e-8 discrepancy in the absolute adaptive constant is constant across probes and has no inference effect.
- `bayesian_extensions.py:160-172`: exact copied `pm.Model(model=None)` construction is parent-free and likelihood-free in PyMC 5.28.5. It creates no observed RVs, restores the outer context, and does not contaminate the posterior model. The actual `pm.sample` call was mocked; convergence was not tested or claimed.
- `fitting.py:96-103`, `runner.py:83-96`, `preprocessing.py:27-58`: visible preprocessing, reference-rate estimation, and synthetic generation use the relevant inner/outer training rows. No new evaluation-data leakage was found in these paths.
- `protocol_addendum_extensions.md:124-153`: scope correctly separates exact coefficient-prior/WME parity from the common-PWE posterior adaptation, LP-only package prediction from the merged baseline extension, and executed R parity from uncompiled Stan. This avoids claiming authors' grouped-baseline posterior reproduction.

## Corrections identified in the reviewed snapshot

These block the snapshot's declared exhaustive diagnostic/pairing verification claim, rather than revealing an incorrect prior density or WME estimator.

1. `fitting.py:142-147` can throw during a later attempt and discard metadata for earlier completed attempts. `runner.py:116-118` writes a generic failed cell without those attempts, leaving earlier saved trace files unreferenced. Preserve prior attempt records and runtime-failed attempt configuration through exceptions.
2. `verification.py:98-111` iterates whichever traces exist but does not require a posterior trace, or both posterior/prior traces and populated prior diagnostics for catalytic Bayesian acceptance. An absent trace set can bypass independent convergence reconstruction. Require the appropriate trace schema and diagnostics explicitly.
3. `rq2.py:47-57` omits condition-pair training-time/event checks and full-anchor pairing checks before difference-in-differences. Require exact modified training outcomes, paired full-anchor memberships/outcomes/grids, and shared validation-fold identities.

The repository owner reports that all three have subsequently been corrected and regression tests are being added. Those edits are not present in this reviewed snapshot, so this report does not independently certify the revised repository state.

## Nonblocker limitations

- The inherited Bayesian base, diagnostics implementation, clinical encoder, and compact-PWE row generator were not supplied in the snapshot. Their exact behavior cannot be independently certified from this copy. The numerical audit stubs only absent inherited helpers to isolate the copied coefficient and context code; it does not claim complete model, PPO, or diagnostic-gate reproduction.
- No four-chain convergence, production run, new patient fit, held-out metric, or outer-test comparison was executed by this audit.
- Independent source-marginal synthetic resampling is an author-consistent construction; it is an empirical prior-data choice, rather than a realistic joint generator of measured biological features.
- The inherited clinical duplicate-pair train/test exposure and retrospective upstream expression normalization remain acknowledged scientific limitations. The declared matched expression cohort and post-hoc comparison labeling are appropriate boundaries; no deployment or biological-independence claim follows.

Machine-readable numerical evidence: `snapshot_numeric_audit.json`. Reproduction command:

```sh
/Users/macuser/miniconda3/envs/bayes-cox-lock-verify-20260815-b/bin/python /Users/macuser/bayes-cox-runs/extension-reference-20260928/catalytic/audit_snapshot.py
```
