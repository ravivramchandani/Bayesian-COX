# Cox catalytic reference fixtures

Actual R execution passed. The fixture is synthetic numerical test data only; it contains no project fit, clinical result, or test-fold measurement. All work is external to the shared project repository.

## Artifacts and execution scope

- `fixture_inputs.json`: frozen 10-row observed dataset, 12-row uncensored synthetic dataset, encoded designs, hyperparameters, probe coefficients, and prediction grid.
- `reference_fixtures.json`: machine-readable inputs plus actual R WME coefficients, objectives, score vectors, prior formula probes, gradients, and two explicitly labeled baseline choices.
- `execute_reference.R`: reproducible execution script, using unmodified functions from downloaded official sources.
- `R-execution.log`, `R-sessionInfo.txt`, `r-env-explicit.txt`: execution and isolated runtime evidence.
- `verify_reference.py`, `independent_validation.json`: independent Python standard-library arithmetic validation. No scientific Python environment or lock was changed.
- `SHA256SUMS.json`: hashes of fixture artifacts and the precise source files used.

R 4.4.3, survival 3.8-12, jsonlite 2.0.0, and rlang 1.3.0 ran in `r-env/`. The full catalytic package was not installed: CRAN `cat_cox`, `misc.R`, and `predict.cat_cox` source functions were sourced directly. The exact `betahat_mix_estimation` assignment was parsed from the authors' untouched R file and evaluated; unused `library(dplyr)` was not executed. This is executed R estimator parity. The Stan prior expressions were evaluated using R arithmetic; Stan was not compiled and no posterior sampling parity is claimed.

The fixed dataset is injected through a frozen initialization list with the expected `cat_initialization` class and fields. `cat_cox_initialization` stochastic resampling was deliberately not run. The numerical fixture tests the estimator conditional on explicit synthetic data, rather than synthetic RNG parity.

## Sources and pins

1. Authors' primary preprint: [arXiv 2312.01411 v2](https://arxiv.org/html/2312.01411v2), 14 December 2024; frozen HTML and PDF in `sources/`. Eq. 7 gives the fixed prior; Eq. 10/11 give the adaptive joint prior; Eq. 15 gives the weighted partial likelihood.
2. Final journal identity: [Biometrics DOI 10.1093/biomtc/ujag004](https://doi.org/10.1093/biomtc/ujag004), journal article published 3 February 2026. The publisher full text fetch failed and curl returned HTTP 403. The equations were verified against the authors' preprint and official package source, not independently against inaccessible final journal text.
3. [Official CRAN catalytic 0.1.0](https://cran.r-project.org/package=catalytic), source downloaded from `https://cran.r-project.org/src/contrib/catalytic_0.1.0.tar.gz`. Relevant files: `R/cat_cox.R:148`, `R/misc.R:964`, `R/misc.R:1144`, `R/predict.R:50`, `inst/stan/cox_joint.stan:17` and `:104`.
4. [Authors' implementation](https://github.com/liweihaoPaul/Catalytic-Cox-Regrerssion), commit `9b27334f3bf5bb7f6e8d0d6a1700cba4f7ba75c7`. Relevant function: `point_estimation_cat.R:289`.
5. [Official survival package](https://cran.r-project.org/package=survival), source `survival_3.8-12.tar.gz`. `man/coxph.Rd:158` documents case weights; `man/basehaz.Rd:41` documents baseline centering and offset recentering. `R/basehaz.R` and `R/survfit.coxph.R:157` verify the exact executed baseline behavior.

## Numerical contracts

The design columns are `z`, `group_B`, `group_C`; group A is the reference. There is no intercept or full dummy block. The synthetic and combined designs both have rank 3. Actual R `model.matrix` for a three-level factor equals the explicit encoded matrix exactly. Observed data include censored rows, simultaneous events, and events tied with censoring; synthetic times are strictly positive and include ties with observed and synthetic rows.

Define `q(beta) = mean(X_star beta - h0 * T_star * exp(X_star beta))`, with uncensored synthetic rows. The fixed log-prior kernel is `tau*q(beta)`; beta-independent constants are dropped. The adaptive kernel is

```
tau * (q(beta) - kappa - 1/gamma) + (p + alpha - 1) * log(tau)
kappa = sup_beta q(beta)
```

CRAN's Stan and `get_cox_kappa` both omit `log(h0)`. Including this term in both q and kappa produces the same adaptive joint density. Omitting it in only one place changes the tau posterior. Gamma is a scale: conditional tau shape is `p+alpha`, and rate is `kappa-q(beta)+1/gamma`. The six probes include fixed/adaptive densities and beta/tau gradients. Here `p=3`, `M=12`, `h0=0.23`, `alpha=2`, `gamma=1.4`, and `kappa=-0.375915003296517`.

WME uses one combined risk set, case weight 1 for observed rows and `tau/M` for synthetic rows, with Breslow ties. Its objective is

```
sum_{event i} w_i * [X_i beta - log(sum_{j: T_j >= T_i} w_j exp(X_j beta))]
```

The hazard constant does not enter WME. At `tau=3.5`, all three executed R routes (authors function, CRAN `cat_cox`, and factor-coded `coxph`) agree within `1e-12`:

```
beta = [-0.948414067917538, 0.112041790794521, -1.21601205872214]
log objective = -17.4688470407106
maximum absolute score = 2.71371813909127e-12
```

The package's `predict.cat_cox` returns raw `X beta`. It does not specify an absolute survival prediction API. The fixture therefore supplies both choices explicitly:

- Weighted merged baseline: `survival::basehaz(fit, centered=FALSE)` from the actual WME fit; numerator is total weighted events at a time, denominator is weighted merged risk.
- Observed-training baseline at fixed WME beta: observed rows only, using an offset-only `coxph` fit. Offsets are recentered even with `centered=FALSE`, so the mean offset is removed from the returned cumulative hazard by multiplying by `exp(-mean_offset)`.

Both choices are independently checked against event-time Breslow increments and frozen absolute survival curves `exp(-H0(t)*exp(X beta))`. Downstream code must name its chosen baseline; neither labeled absolute-survival fixture should be represented as output of catalytic's LP-only `predict` method.

## Commands and validation

Executed from this artifact directory:

```sh
/Users/macuser/miniconda3/bin/conda create --prefix "$PWD/r-env" -c conda-forge --override-channels r-base=4.4 r-survival r-jsonlite -y
/Users/macuser/miniconda3/bin/conda install --prefix "$PWD/r-env" -c conda-forge --override-channels r-rlang -y
/Users/macuser/miniconda3/bin/conda list --prefix "$PWD/r-env" --explicit > r-env-explicit.txt
./r-env/bin/Rscript execute_reference.R ./fixture_inputs.json > R-execution.log 2>&1
python3 verify_reference.py
```

The R script asserts exact author/CRAN/factor estimator agreement, objective agreement with `coxph$loglik`, stationary score, kappa agreement with a separate optimizer, consistent adaptive centering, and both baseline calculations. Independent standard-library validation passed; maximum absolute discrepancy including finite differences was `3.7759040338869454e-10`.

One initial attempt to install rlang through `install.packages` returned a nonzero installation status; the subsequent isolated conda install succeeded. The retained logs record both attempts. No project repository was read or edited.
