# Explainability comparison

Generated 2026-08-14 from `reports/tables/explainability.json`.

**Evidence status: exploratory pilot.** Rankings use a limited test-row
sample and do not yet quantify fold, subject or SHAP-seed stability.

The Bayesian posterior provides a built-in feature signal: the
posterior probability that a coefficient's effect has a consistent
direction. This is compared against post-hoc SHAP attributions
computed on the Cox PH and random survival forest baselines. Both
use a kernel explainer over the model's risk prediction, so the
attribution method is held constant across models.

Agreement is reported as Spearman and Kendall rank correlation over
all features, and as the overlap of the five highest-ranked features.

## GBSG2 (German Breast Cancer Study Group 2)

| Posterior prior | Compared with | Spearman | Kendall | Top-5 overlap |
| :--- | :--- | ---: | ---: | ---: |
| normal | Cox PH | +0.951 | +0.848 | 4 of 5 |
| normal | Random Survival Forest | -0.182 | -0.121 | 1 of 5 |
| horseshoe | Cox PH | +0.573 | +0.455 | 3 of 5 |
| horseshoe | Random Survival Forest | +0.126 | +0.091 | 3 of 5 |
| spike_slab | Cox PH | +0.944 | +0.818 | 4 of 5 |
| spike_slab | Random Survival Forest | -0.189 | -0.152 | 1 of 5 |

Leading horseshoe sparsity signal: log_pnodes (0.182), log_progrec (0.353), horTh_yes (0.409), progrec (0.477), menostat_Pre (0.541).

Leading spike_slab sparsity signal: horTh_yes (0.661), age_x_horTh (0.505), log_pnodes (0.439), menostat_Pre (0.418), progrec (0.387).

## WHAS500 (Worcester Heart Attack Study)

| Posterior prior | Compared with | Spearman | Kendall | Top-5 overlap |
| :--- | :--- | ---: | ---: | ---: |
| normal | Cox PH | +0.462 | +0.360 | 2 of 5 |
| normal | Random Survival Forest | +0.166 | +0.118 | 2 of 5 |
| horseshoe | Cox PH | +0.682 | +0.517 | 3 of 5 |
| horseshoe | Random Survival Forest | +0.403 | +0.276 | 3 of 5 |
| spike_slab | Cox PH | +0.506 | +0.383 | 2 of 5 |
| spike_slab | Random Survival Forest | +0.205 | +0.142 | 2 of 5 |

Leading horseshoe sparsity signal: sho_1 (0.139), age (0.226), mitype_1 (0.437), age_x_chf (0.493), hr (0.513).

Leading spike_slab sparsity signal: sho_1 (0.587), age (0.457), chf_1 (0.454), mitype_1 (0.436), bmi_low (0.426).

## METABRIC

| Posterior prior | Compared with | Spearman | Kendall | Top-5 overlap |
| :--- | :--- | ---: | ---: | ---: |
| normal | Cox PH | +0.918 | +0.783 | 4 of 5 |
| normal | Random Survival Forest | +0.408 | +0.310 | 2 of 5 |
| horseshoe | Cox PH | +0.902 | +0.769 | 4 of 5 |
| horseshoe | Random Survival Forest | +0.518 | +0.419 | 2 of 5 |
| spike_slab | Cox PH | +0.924 | +0.812 | 4 of 5 |
| spike_slab | Random Survival Forest | +0.387 | +0.288 | 2 of 5 |

Leading horseshoe sparsity signal: age_at_diagnosis (0.139), inferred_menopausal_state_Pre (0.289), log_lymph_nodes (0.291), pam50_+_claudin-low_subtype_LumA (0.315), her2_status_Positive (0.456).

Leading spike_slab sparsity signal: age_at_diagnosis (0.436), inferred_menopausal_state_Pre (0.413), pam50_+_claudin-low_subtype_NC (0.411), log_lymph_nodes (0.395), her2_status_Positive (0.390).
