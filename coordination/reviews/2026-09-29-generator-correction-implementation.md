# Generator correction implementation review

ADR-040/T-190 remains open. This update implements the candidate generator
and actual training-input preflight runner. It specifies cap 256, exact
original first seed and complete rank-only redraws before the real preflight.
It does not claim corrected fits, fit reuse, arithmetic approval or a new
numerical freeze.

The candidate runs each proposal in a fresh isolated child using byte-pinned
original leaf source. It captures the original constructor inputs and retries
only the exact original rank guard. Default preprocessing rebuild remains
available. Optional restoration uses the original clinical metadata guard,
complete outer-state hash and exact metadata/feature-order roundtrip. The
controller independently fits the full original training frame before passing
selected source columns and complete state. Integrity alone is not training
provenance.

Seventeen integrated generator tests cover rare/singleton categories,
structural dependence, exact first proposals, whole redraws, terminal cap,
nonrank errors, constructor restoration and unchanged parent module state.
Clinical and selected-gene restoration matches original rebuild exactly;
the selected-gene fixture additionally matches a direct normal-import
original-source control. Tampered outer/clinical state and budget mismatch
stop before drawing. These fixtures do not certify real whole-grid reuse.

The preflight normally imports the clean original production checkout,
checks all imported source origins and 118 frozen inputs, verifies the exact
lock and independently reconstructs all 1,625 original jobs. It accounts for
825 outer and 825 WME inner training contexts. It saves actual real/proposal
arrays, memberships, processor state, source support, rank measurements,
seeds and terminal outcomes without fitting or evaluating a model. Source
comparisons certify saved generator/preprocessing metadata only. Independent
original replay and complete fit/evaluation witnesses remain required.

Twenty-five invented/injected runner tests cover censoring-before-inner
splitting, training-only processing, held-out perturbation, restoration
transport, rank-only retries, interruption/resume, corrupted/extra checkpoints,
scalar archive shapes, retained errors, claims and no-replace publication.
Independent static reviews found no material defect in the runner or optional
restoration. The scalar witness shape was corrected before sealing and has
a focused roundtrip test. Repository integration changes only sibling/package
imports, the reviewed default candidate digest and portable test fixture paths.
The integrated core remains byte-identical to its sealed preparation.

Five sealed preparation bundles are archived with every original member
verified byte-for-byte:

| Archive suffix | Members | SHA-256 |
| --- | ---: | --- |
| `candidate.tar.gz` | 20 | `6202bcae30ebed4101a05507dff6f16f72dabac607a4caf8dba949a9b37924fb` |
| `inventory.tar.gz` | 7 | `99872973c168d16962712ba7ec6109fecdec27464348fab0c08b7a2afccb8a4a` |
| `fit-contracts.tar.gz` | 20 | `8dc3c2180ef672474578c016242fd949ef0671c82b44970217215ed60a847c2c` |
| `preflight-runner.tar.gz` | 27 | `60ebfe10637f9116b802a799a28ce97dbdadf042e68cae0ebd3de60627064f4c` |
| `arithmetic.tar.gz` | 27 | `08fd9e7d3f97341cc9ef41b6a3ad90227318c969cfdf124c057b2bed04566b22` |

Each lives under
`coordination/recovery/2026-09-29-generator-correction-<suffix>`.
Their original pending flags remain unchanged. The contract prototype's
14 synthetic tests/review passed; actual scientific witness construction and
dispatch adapters remain separate implementation work.
The independent arithmetic preparation passed 29 synthetic tests and peer
review, including the corrected optimizer-invocation byte binding. Both
fixed/adaptive Bayesian outer contexts require separately checked kappa
witnesses. Its actual changed-input coverage and numerical execution remain
pending; it is not an arithmetic approval or a method freeze.

The exact 259-package environment passed again, with Python 3.11.15 and
matching HDF5 2.1.0 build/runtime. All 157 existing source/build/lock files
still match the earlier v5 tested-source inventory. Repository-wide Ruff
passed. Full integrated `make test` passed all 391 tests and 21 subtests in
319.82 seconds; coordination schemas and `git diff --check` also passed.
The compact verification receipt is
`coordination/recovery/2026-09-29-generator-correction-integration.json`;
full logs are retained in the external integration-validation directory.

Original workers, source, inputs, outcomes and postfit support remain unchanged.
The next real stage is the serial low-priority training preflight on external
APFS storage. Its inputs/code/addendum/config will be pinned separately from
later repository edits. Numerical correction still requires complete input
review, independent arithmetic and a distinct freeze before any corrected
validation score.
