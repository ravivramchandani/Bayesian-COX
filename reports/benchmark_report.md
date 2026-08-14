# Benchmark results

Generated 2026-08-14 from `reports/tables/benchmark.json`.

**Evidence status: exploratory pilot.** The inspected holdout, current
cross-validation preprocessing and test-derived horizons prevent
confirmatory model-comparison claims; see ADR-014.

Three model families are compared on three clinical cohorts: the Cox
proportional hazards baseline, a random survival forest, and the
Bayesian Cox model fitted under each of three coefficient priors.
Discrimination is measured by Harrell's concordance index and
time-dependent AUC. Integrated Brier score is an overall probabilistic
prediction-error measure affected by discrimination and calibration;
lower is better. It does not establish calibration by itself.

Cross-validated concordance uses a shorter sampling chain than the
reported test-set fit, so it is comparable across models but not
directly against the test-set column.

## GBSG2 (German Breast Cancer Study Group 2)

479 training and 105 test subjects, 12 features, 43.6% event rate in training.

| Model | C-index | IBS | Mean AUC | CV C-index | Fit (s) |
| :--- | ---: | ---: | ---: | ---: | ---: |
| Cox PH | 0.7021 | 0.1584 | 0.7369 | 0.6714 ± 0.048 | 0.0 |
| Random Survival Forest | 0.6865 | 0.1652 | 0.7135 | 0.6817 ± 0.051 | 0.1 |
| Bayesian Cox (normal) | 0.6995 | 0.1592 | 0.7315 | 0.6726 ± 0.047 | 54.4 |
| Bayesian Cox (horseshoe) | 0.7018 | 0.1586 | 0.7355 | 0.6763 ± 0.044 | 167.9 |
| Bayesian Cox (spike_slab) | 0.6943 | 0.1599 | 0.7293 | 0.6717 ± 0.051 | 120.4 |

Sampler diagnostics:

| Model | R-hat max | Bulk ESS min | Divergences | Converged |
| :--- | ---: | ---: | ---: | :---: |
| Bayesian Cox (normal) | 1.0000 | 2291 | 0 (0.00%) | yes |
| Bayesian Cox (horseshoe) | 1.0000 | 1155 | 1 (0.01%) | yes |
| Bayesian Cox (spike_slab) | 1.0000 | 2092 | 0 (0.00%) | yes |

The Cox baseline reaches 0.702 against a published reference of approximately 0.67, which places the pipeline within the expected range for this cohort.

## WHAS500 (Worcester Heart Attack Study)

349 training and 77 test subjects, 16 features, 43.0% event rate in training.

| Model | C-index | IBS | Mean AUC | CV C-index | Fit (s) |
| :--- | ---: | ---: | ---: | ---: | ---: |
| Cox PH | 0.7215 | 0.1445 | 0.7445 | 0.7879 ± 0.053 | 0.0 |
| Random Survival Forest | 0.7504 | 0.1332 | 0.7900 | 0.7904 ± 0.032 | 0.1 |
| Bayesian Cox (normal) | 0.7310 | 0.1375 | 0.7722 | 0.7879 ± 0.042 | 29.1 |
| Bayesian Cox (horseshoe) | 0.7454 | 0.1313 | 0.7920 | 0.7923 ± 0.038 | 116.2 |
| Bayesian Cox (spike_slab) | 0.7293 | 0.1380 | 0.7696 | 0.7882 ± 0.043 | 63.5 |

Sampler diagnostics:

| Model | R-hat max | Bulk ESS min | Divergences | Converged |
| :--- | ---: | ---: | ---: | :---: |
| Bayesian Cox (normal) | 1.0000 | 2166 | 0 (0.00%) | yes |
| Bayesian Cox (horseshoe) | 1.0000 | 3489 | 0 (0.00%) | yes |
| Bayesian Cox (spike_slab) | 1.0000 | 2821 | 0 (0.00%) | yes |

The Cox baseline reaches 0.722 against a published reference of approximately 0.75, which places the pipeline within the expected range for this cohort.

## METABRIC

1332 training and 286 test subjects, 24 features, 58.0% event rate in training.

| Model | C-index | IBS | Mean AUC | CV C-index | Fit (s) |
| :--- | ---: | ---: | ---: | ---: | ---: |
| Cox PH | 0.6649 | 0.1696 | 0.7077 | 0.6670 ± 0.024 | 0.1 |
| Random Survival Forest | 0.6747 | 0.1677 | 0.7175 | 0.6806 ± 0.013 | 0.4 |
| Bayesian Cox (normal) | 0.6663 | 0.1701 | 0.7069 | 0.6670 ± 0.022 | 87.9 |
| Bayesian Cox (horseshoe) | 0.6639 | 0.1696 | 0.7070 | 0.6677 ± 0.021 | 423.8 |
| Bayesian Cox (spike_slab) | 0.6662 | 0.1700 | 0.7071 | 0.6674 ± 0.022 | 302.1 |

Sampler diagnostics:

| Model | R-hat max | Bulk ESS min | Divergences | Converged |
| :--- | ---: | ---: | ---: | :---: |
| Bayesian Cox (normal) | 1.0000 | 3621 | 0 (0.00%) | yes |
| Bayesian Cox (horseshoe) | 1.0000 | 2407 | 0 (0.00%) | yes |
| Bayesian Cox (spike_slab) | 1.0000 | 5378 | 0 (0.00%) | yes |

The Cox baseline reaches 0.665 against a published reference of approximately 0.63, which places the pipeline within the expected range for this cohort.
