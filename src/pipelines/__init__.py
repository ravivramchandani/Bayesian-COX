"""Analysis pipelines that fit models and write the study's stored evidence.

- :mod:`src.pipelines.confirmatory`: the frozen repeated nested cross-validation
  of six models on three cohorts, from fold-local fitting to paired inference.
  Entry point ``execute_confirmatory_run``, called by
  ``scripts/run_confirmatory.py``.
- :mod:`src.pipelines.robustness`: the prespecified Bayesian sensitivity
  analyses (training size, censoring, prior scale, baseline resolution,
  feature sets, imputation) and the proportional-hazards summary. Entry point
  ``execute_robustness_run``, called by ``scripts/run_robustness.py``.
- :mod:`src.pipelines.posthoc_sampler`: the post-hoc horseshoe sampler
  sensitivity of ADR-032. Entry point ``execute_sampler_sensitivity``, called
  by ``scripts/run_horseshoe_sampler_sensitivity.py``.
"""
