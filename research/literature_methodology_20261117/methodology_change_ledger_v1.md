# Methodology change ledger, version 1

Date: 17 November 2026. Chapter edited: `methodology.tex`; a subsequent parent-authorised caption-only clarification was made in `figures/diagnostic_decisions.tex`. Baseline: restored current manuscript `d1f6c0b`, cross-checked with Ravi's supplied manuscript at `69a7f046` and the implementation. The external research dossier was used as a discovery index; no dossier text was copied into the chapter.

## Scope and preservation

- All current section/subsection headings, labels, tables, original cohort definitions and research-question mapping were retained.
- Original literature context and citations were retained where they support the claim. Relevant original references `ref23`, `ref25`, `ref35` and `ref46` were brought into precise methodological contexts.
- The study's empirical results, acceptance outcomes, priors, refit controls, evaluation rules, cohort counts and sensitivity/explanation designs were not changed.
- Copyediting removes repeated definitions/settings and repairs awkward sentences. The first draft's whitespace word count changed from 7,826 to 7,176 while adding specific methodological explanations, followed by a bounded notation clarification for scaled time. This is not a new chapter structure or a replacement study design.

## Changes with evidence

| Change | Verified basis | Boundary |
|---|---|---|
| Specified the multi-cohort rationale and separated computational acceptance, model adequacy and held-out prediction | Original methodological structure; SurvBenchmark (`ref33`), Smith (`ref44`); Schad full-text discussion of distinct workflow questions | No claim that three cohorts establish general clinical validity |
| Replaced direct-loader wording with the cohorts distributed by scikit-survival | `project/scripts/download_datasets.py:212–253`; `project/src/data/cohorts.py:21–64` | Actual acquisition parses the distributed source files, then modelling reads the cohort table |
| Added METABRIC one-to-one patient/sample join and 2,509 minus 528 missing outcomes minus one zero-time eligibility derivation | `project/scripts/download_datasets.py:261–337` | Final counts remain 1,980 patients, 1,144 events, 836 censored |
| Corrected WHAS500 censored observations and explained the admission-time primary predictor set | `project/docs/datasets.md:38–60`; download script and frozen cohort configuration | No unverified clinical time origin added for GBSG2 |
| Clarified ordinal, numerical and one-hot transformations and source-variable grouping | `project/src/data/fold_preprocessing.py`; fixed dataset feature specifications | All fitting remains within training partitions |
| Clarified shared repeated outer folds and inner tuning of RSF/DeepSurv | `project/config/confirmatory.yaml`; `project/src/pipelines/confirmatory/fitting.py:124–205,321–430` | Does not imply all six models were hyperparameter-tuned |
| Added primary Cox/RSF/NUTS scholarly grounding and clarified which models retain PH | Cox1972 existing key; Ishwaran2008 verified publisher paper; Hoffman/Gelman2014 official JMLR; DeepSurv original full-text source | Comparator contrasts differ in baseline treatment as well as prior/inference |
| Defined interval exposure and event count, Poisson likelihood proportionality and continuous-time meaning | `project/src/models/bayesian/piecewise.py:1–83`; Laird/Olivier1981, Friedman1982; original `ref46` full-text Methods alternative approaches | No binary-hazard or whole generative event-time claim |
| Explained training-median time scaling, event-quantile cutpoints and baseline prior units | `project/src/models/bayesian/model.py:252–276,342–347` | Six intervals described as specified choice, not optimised choice |
| Made scaled-time notation explicit through u=t/s, scaled observed follow-up, scaled hazards, exposures and S(t) at original time | Same time-scaling and prediction code | Keeps original-time outcome definitions distinct from the likelihood's scaled units |
| Added draw-wise survival equation and posterior averaging target | `project/src/models/bayesian/model.py:490–562`; baseline cumulative hazard code in `predictive_checks.py:76–113` | Survival probabilities averaged over draws, not survival evaluated at mean parameters |
| Distinguished complete prior configurations and their strengths | `project/src/models/bayesian/model.py:292–340`; `project/config/confirmatory.yaml` primary/narrower/wider blocks | Does not claim strength-matched comparison of prior shapes |
| Clarified half-t2 regularised horseshoe variant, inverse-gamma shape/scale and slab's conditional-variance bound | Actual prior implementation; Carvalho2010 and Piironen/Vehtari2017 | Does not equate half-t2 scales with the original half-Cauchy horseshoe |
| Defined the Beta-weighted continuous variance interpolation | `project/src/models/bayesian/model.py:324–340` | Gamma describes variance allocation, not feature inclusion probability |
| Added exact prior predictive summaries and their training-derived conditioning | `project/src/models/bayesian/predictive_checks.py:1–23,115–194`; `model.py:349–356` | No claim of entirely data-independent checks or any new observed check result |
| Corrected BFMI to Hamiltonian energy exploration and tree-depth interpretation | `project/src/models/bayesian/diagnostics.py:1–25,124–232`; Betancourt2017 primary HMC review | Preserves the specified 0.30 and zero-hit thresholds |
| Distinguished predictive-check computation from first-passing-attempt selection | `project/src/models/bayesian/model.py:231–249`; `project/src/pipelines/confirmatory/fitting.py:259–318` | Failed-attempt computation does not imply eligibility for prediction/interpretation |
| Distinguished fixed-exposure replicated Poisson counts from fitted survival/Kaplan–Meier comparison | `project/src/models/bayesian/predictive_checks.py:196–330` | No claim of generating replicated patient survival/censoring histories |
| Clarified likelihood and marginal IPCW censoring assumptions, supported evaluation window and metric roles | `project/src/evaluation/metrics.py:128–295,405–462`; original metric papers | Training censoring estimation described as the chosen convention, not uniquely valid convention |
| Explained slope-one cloglog CITL as cumulative-hazard recalibration; specified calibration clipping and fixed-model bootstrap | `project/src/evaluation/calibration.py:246–430`; `calibration_model.py:1–114` | Exact code uses clipping at 1e-12; avoids attributing this particular estimator to a paper describing a different calibration estimator |
| Clarified corrected paired CV uncertainty, complete family/contrast requirements and superiority rule | `project/src/pipelines/confirmatory/inference.py:72–152,262–304,369–444`; Nadeau/Bengio2003; Holm1979 | Nominal intervals are not Holm-adjusted; posthoc bound remains separate |
| Distinguished posterior association uncertainty from contribution ranking and centred mean-coefficient SHAP | `project/src/models/bayesian/model.py:563–639`; existing exact linear SHAP implementation and checks | Same-model agreement is agreement between fitted-model summaries, not independent truth validation or survival-probability explanation |
| Restricted robustness wording to predictive/diagnostic sensitivity and kept explanation sampling stability separate | Frozen robustness configuration, `project/docs/study_protocol.md`; attribution seed/budget implementation | 825 outcomes/885 fits and all bootstrap budgets remain unchanged |
| Replaced repeated sampler paragraphs with useful software context | `project/docs/verified_resources.md:9–28`; `project/pyproject.toml:1–24` | No machine paths, hashes, setup instructions or unverified hardware specification |

## Primary additions for bibliography integration

1. `hoffman2014`: Matthew D. Hoffman and Andrew Gelman, “The No-U-Turn Sampler: Adaptively Setting Path Lengths in Hamiltonian Monte Carlo,” Journal of Machine Learning Research 15(47), 1593–1623, 2014. Official abstract and paper verified: https://www.jmlr.org/papers/v15/hoffman14a.html and https://jmlr.csail.mit.edu/papers/volume15/hoffman14a/hoffman14a.pdf . Retained Thomas/Tu (`ref55`) as practical HMC context.
2. `ishwaran2008`: Hemant Ishwaran, Udaya B. Kogalur, Eugene H. Blackstone and Michael S. Lauer, “Random survival forests,” Annals of Applied Statistics 2(3), 841–860, 2008. Publisher verified: https://doi.org/10.1214/08-AOAS169 .
3. `betancourt2017`: Michael Betancourt, “A Conceptual Introduction to Hamiltonian Monte Carlo,” arXiv:1701.02434, 2017. Primary author report: https://arxiv.org/abs/1701.02434 . Energy/BFMI discussion verified in full-text primary paper (section 6.1).

Also requires restored bibliography items `ref35` and `ref46`; their source-claim suitability was independently checked by the original-reference recovery agent. Existing `ref23`/`ref25` are already in the current bibliography.

## Focused checks performed

- `git diff --check -- methodology.tex`: passed.
- Section/subsection heading sequence is identical before and after.
- LaTeX environment counts are balanced.
- No Unicode em dash or literal triple dash was introduced.
- Bibliography integration and final LaTeX build are owned by the parent agent, after the parallel chapter edits finish.
