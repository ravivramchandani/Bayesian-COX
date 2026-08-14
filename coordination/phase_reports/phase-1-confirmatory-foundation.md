# Phase 1 — Confirmatory foundation and evidence boundary

Date: 2026-08-15
Status: engineering foundation complete; scientific production runs pending

## Exit evidence achieved

| Area | Verified state |
|---|---|
| GBSG2 | 686 records/299 events; derived SHA-256 `2158b777d27ecfb69b187d3cbcad13fd1eb92d626935c528a4465fea6490ae5f` |
| WHAS500 | 500 records/215 events; derived SHA-256 `4bb01775c04eca11d7f06d6e5dfebd0a5cce75aa7e73fe4261732385be106fcc` |
| METABRIC | Pinned cBioPortal rebuild; 1,980 positive-time records/1,144 deaths; derived SHA-256 `731ea80ce0240cb6aa96ffb0f4a3bb379615202966c954512664bef02b29545c` |
| Feature integrity | Primary baseline/admission/pathology sets and named sensitivities are explicit and tested; WHAS500 excludes `los`, `afb`, `sho`, `chf` and `av3` from the nine-predictor primary set; post-baseline or unverified-timing variables are excluded from primary models |
| Validation | Deterministic paired repeated outer folds, fold-local preprocessing, training-only horizons and compact inner tuning are implemented and tested |
| Evaluation | IPCW IBS, Uno and Harrell concordance, cumulative/dynamic AUC, calibration curves/parameters and unsupported-support failures are reference-tested |
| Inference | Nadeau–Bengio paired intervals, Holm adjustment and event-stratified paired out-of-fold bootstrap are implemented and tested |
| Bayesian quality | All-parameter diagnostics, zero-divergence gate, BFMI/tree-depth checks, prespecified refits, trace snapshots and genuine replicated-event posterior-predictive checks are implemented |
| Comparators | lifelines Cox, scikit-survival forest and pinned pycox DeepSurv are integrated with deterministic training and prediction gates |
| Explanation | Exact no-refit Bayesian/Cox linear SHAP, full-posterior grouped intrinsic contributions, nested budgets, three seeds and three-stage uncertainty are implemented; confirmatory forest SHAP and DeepSurv explanation are dropped |
| Robustness | Lean frozen plan, RQ2 pairing, feature/design/missingness sensitivities, PH aggregation, checkpoint hashes and result-blind runtime refusal are implemented |
| Rendering | Confirmatory tables/figures are pure artefact renderers with hash/key lineage; the legacy pilot renderer is separated |
| Environment | Fresh macOS arm64 lock verified; lock SHA-256 `1921895d4a404fc99e848d69ccd4a3f6639a3d1610315c82ecd463ed4bcdfb57` |
| Automated verification | 150 tests passed and Ruff reported no violations in the exact locked environment on 2026-08-15 |

## Pilot evidence retained with limits

The earlier 15 model/cohort fits and 18 explanation comparisons remain only
as development and hypothesis-generating artefacts. Their inspected holdout,
global preprocessing, test-derived horizons and absent paired predictions
exclude confirmatory superiority, equivalence, calibration and multiplicity-
controlled claims. The earlier narrative descriptions of Bernstein–von Mises
behaviour, clinically established feature recovery and prior benefit are not
admissible thesis findings.

The current result-blind rehearsal stored all 18 planned cohort/model cells,
but only 14 completed. The WHAS500 and METABRIC forest/DeepSurv cells failed
under the earlier IPCW support handling. Focused post-fix smoke tests exist,
but that rehearsal predates the final code, renderer and freeze inputs and
cannot satisfy the compute gate. No comparative rehearsal effect was admitted
as evidence.

## Scope decision

The three core cohorts total 3,166 subjects and 1,658 events. Rotterdam
transport and the ADEMP simulation were permanently dropped before protocol
freeze under ADR-025. The thesis therefore remains a three-cohort repeated-CV
methodological benchmark and makes neither external-validation nor simulated
coefficient-recovery claims. It also makes no empirical generalisation or
transportability claim beyond the evaluated healthcare setting.

## Work that is not complete

- Run a new exact 18-cell result-blind rehearsal and inspect only completion,
  diagnostics and runtime.
- Apply the prespecified 72-hour repeat rule, record the final repeat count and
  create the content-addressed protocol freeze.
- Execute the frozen confirmatory grid; no confirmatory performance or
  calibration result exists yet.
- Execute robustness and confirmatory explanation from the completed frozen
  run; no robustness or explanation-stability result exists yet.
- Render immutable outputs, write results/conclusion/abstract from those
  outputs, and complete statistical, citation, reporting and reproducibility
  reviews.

No completed scientific result is inferred from the availability of its
pipeline or from a passing unit/reference test.
