# Exact macOS arm64 environment

The confirmatory environment is locked for Apple Silicon on macOS 14 or
newer. `conda-lock.yml` contains the exact URLs and SHA-256 checksums for 237
conda packages and 22 PyPI packages. Its committed SHA-256 is recorded in
`conda-lock.yml.sha256`.

The conda package is named `pytorch`, while its Python import and PyPI
distribution are named `torch`. The conda specification therefore pins
`pytorch=2.13.0`; `pyproject.toml` retains `torch==2.13.0` for pip-only use.
`pyproject.toml` can pin `h5py`, but it cannot pin the native HDF5 library, so
the confirmatory build uses the conda lock.

## Create and verify a fresh environment

Use conda-lock 4.0.2 from a separate tool environment. The target environment
name must be new so the verification is a clean-build test.

```bash
conda create -n bayes-cox-conda-lock-4-0-2 \
  --override-channels -c conda-forge conda-lock=4.0.2
conda run -n bayes-cox-conda-lock-4-0-2 \
  conda-lock install -n bayes-cox-clean conda-lock.yml
conda run -n bayes-cox-clean python scripts/verify_environment.py
conda run -n bayes-cox-clean python -m pytest tests -q
conda run -n bayes-cox-clean python -m ruff check --no-cache .
```

The equivalent Make workflow is:

```bash
make clean-build \
  CONDA_LOCK="conda run -n bayes-cox-conda-lock-4-0-2 conda-lock" \
  LOCK_ENV=bayes-cox-clean
```

Regenerate the lock only after an intentional dependency change:

```bash
make lock \
  CONDA_LOCK="conda run -n bayes-cox-conda-lock-4-0-2 conda-lock"
```

The lock-generation virtual-package specification sets macOS 14.0 and arm64.
This matches the minimum platform of the pinned PyTorch arm64 build and makes
the platform assumption explicit. A lock for another operating system or CPU
architecture must be generated and independently verified; this lock is not
portable to those platforms.

## Separate Windows lock for the RSF surrogate study

`conda-lock-win-64.yml` is a platform-specific lock generated from the same
`environment.yml` dependency specification. Its SHA-256 is recorded in
`conda-lock-win-64.yml.sha256`. It does not replace the macOS lock or authorize
confirmatory production on Windows. The Windows lock is reserved for the
separate post-hoc RSF surrogate study; its run manifest records this lock and
the platform separately from the frozen source release's macOS lock.

Create and verify the Windows environment with:

```powershell
conda run -n bayes-cox-conda-lock-4-0-2 conda-lock install `
  --name bayes-cox-rsf-win-64 conda-lock-win-64.yml
conda run -n bayes-cox-rsf-win-64 python scripts/verify_environment.py `
  --platform win-64 --lock-file conda-lock-win-64.yml `
  --hash-file conda-lock-win-64.yml.sha256
```

The environment lock establishes package provenance; it does not establish
numerical equivalence to the frozen source forest. The first Windows pilot
failed the strict source-prediction replay check in all three cohorts, before
any student-tree fit. Its sealed records are in
`reports/posthoc/rsf_surrogate_v1_pilot_windows_20261007_r1/`.

## Windows source-version parity lock

`environment-rsf-surrogate-win.yml` is based on the project environment and
pins scikit-learn 1.9.0, joblib 1.5.3 and threadpoolctl 3.6.0 to the versions
in the macOS source lock. `conda-lock-rsf-surrogate-win-64.yml` records the
Windows x64 package builds and checksums; its digest is in the companion
`.sha256` file. It was verified in
`bayes-cox-rsf-win-sklearn190-20261007` with Python 3.11.15 and 249 package
records. Verify it with:

```powershell
conda run -n bayes-cox-rsf-win-sklearn190-20261007 `
  python scripts/verify_environment.py --platform win-64 `
  --lock-file conda-lock-rsf-surrogate-win-64.yml `
  --hash-file conda-lock-rsf-surrogate-win-64.yml.sha256
```

The second pilot at
`reports/posthoc/rsf_surrogate_v1_pilot_windows_sklearn190_20261007_r1/`
reproduced the same three maximum replay errors as the first pilot. Matching
these core package versions did not resolve the cross-platform mismatch; its
cause remains undiagnosed. Both pilots are incomplete, no surrogate tree was
fitted, and the 75-cell study was not run. The frozen tolerance remains
unchanged.

## HDF5 compatibility finding

The previous active environment combined h5py 3.16.0, compiled against HDF5
2.1.0, with the HDF5 2.2.0 runtime. Importing h5py with warnings treated as
errors reproduced its binary-version warning. The conda package metadata
allowed HDF5 versions from 2.1 up to, but not including, 3.0, which permitted
that incompatible solve. The source specification and lock now pin h5py
3.16.0 with HDF5 2.1.0. The verifier imports h5py with warnings treated as
errors and requires its compile-time and runtime HDF5 versions to be equal.

## Verified clean build

On 2026-08-15, a fresh environment named
`bayes-cox-lock-verify-20260815-b` was installed from the committed lock on
macOS 26.6 arm64. Verification established Python 3.11.15, all 259 locked
package records, all direct imports, and matching HDF5 2.1.0 build/runtime
versions. The complete test suite passed (150 tests, with no warnings), and
Ruff reported no violations.
