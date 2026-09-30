# Focused clinical methods claim review

This release is a post-hoc, outcome-aware subset of the unfinished extension.
The 27 comparisons were defined in the earlier frozen extension addendum;
the narrower study was selected after some extension outcomes existed. Do not
call it prospective preregistration or completion of the 1,625-cell programme.

Before approving figures or claims, check each item against the saved tables:

1. GBSG2, WHAS500 and clinical METABRIC have distinct endpoints. Each is an
   internal-validation setting, not an external validation of one transported
   model. Do not pool the cohort effects.
2. Penalised Cox and the Bayesian comparators use different survival
   likelihood/baseline-hazard implementations. An observed difference is not
   a causal effect of the coefficient prior alone.
3. All 25 planned folds per arm remain in the denominator; report failed
   fitting and diagnostic outcomes alongside accepted-only scores. Keep the
   original horseshoe's 20 failed diagnostics separate from the ADR-032
   post-hoc sampler result.
4. Each formal contrast needs 25 aligned accepted pairs. Holm rejection
   language requires all 27 contrasts in the fixed family to be estimable;
   the corrected interval must also exclude zero in the claimed direction.
   Missing comparisons do not establish equivalence or a global winner.
5. The frozen clinical METABRIC source has a known same-individual accession
   pair that may occur across training and validation folds. Biological
   independence is not established for that cohort.
6. Decision curves, a validated clinical action threshold and clinical
   utility are outside this focused study. Observed runtimes come from
   separate runs and are descriptive, not a controlled hardware benchmark.
7. Q1 publication quality is a goal, not an acceptance claim. TRIPOD+AI and
   PROBAST+AI can guide later item-level reporting and bias appraisal;
   neither compliance nor a completed appraisal is claimed by this package.
8. The baseline release hashes and 450/450 exact refit comparisons corroborate
   the saved Bayesian diagnostic records. The restored baseline releases do
   not contain raw posterior arrays, so this study does not recalculate
   diagnostics from those arrays or claim fresh trace-array verification.

The visual-QA review form requires an explicit pass for each boundary above.
Its pass records that this release's wording and graphics respect the limits;
it is not a substitute for an item-level manuscript review.
