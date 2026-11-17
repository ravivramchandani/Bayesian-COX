# Investigate and provide an evidence-grounded research dossier to improve BOTH th

**Question:** Investigate and provide an evidence-grounded research dossier to improve BOTH the literature review and methodology of Ravi Ramchandani's existing master's thesis, Explainable Bayesian Survival Models. This is a comprehensive investigation, not a request for new experiments. Preserve the author's existing chapter structure and valid original scholarship. The current editorial task must repair earlier over-aggressive citation deletion: original bibliography had 95 entries, 63 cited; an edited version kept 40 original sources and added 15 methods sources. Twenty-five originally cited entries were omitted after citation corrections or paragraph edits. We need recover relevant original scholarship with accurate supporting claims, not merely pad a bibliography.

Study: three right-censored clinical cohorts GBSG2 n686/events299/8 source predictors, WHAS500 n500/events215/9 predictors, METABRIC n1980/events1144/8 primary clinical/pathology predictors. Six arms: CoxPH, RSF, DeepSurv, and a common full-likelihood Bayesian piecewise-exponential PH model with Normal, regularised horseshoe, continuous variance-mixture priors. Five repeats x five outer folds, shared partitions, training-only imputation/scaling/encoding; three-fold inner IBS tuning only RSF/DeepSurv. Six event-quantile intervals; time scaled by outer-training median event time; independent log baseline rates Normal(-2,2^2). Normal beta~N(0,1). Horseshoe global HalfStudent-t(df2,scale0.1), local HalfStudent-t(df2,scale1), c^2~InvGamma(2,8), regularised local scale. Continuous beta=z*sigma; z~N(0,1); gamma~Beta(1,1); sigma^2=(1-gamma)*0.05^2+gamma*2^2. No discrete inclusion event. NUTS four chains initial2000warmup+2000retained; targets0.95/0.99; diagnostic gates rounded rank-Rhat<1.01, bulkESS>400, zero divergences/treedepth, BFMI>=.30; at most two specified refits, second noncentred baseline. Priors/likelihood/folds remain fixed. Original450 model-fold outcomes430accepted, horseshoe55/75 (GBSG7/25,METABRIC23/25,WHAS25/25); Normal and continuous mixture75/75. Separate post-hoc target0.999 horseshoe sensitivity75/75. Five of nine primary IBS contrasts fully estimable; all intervals include0; no equivalence claim. 825-condition robustness programme and exact linear risk-score SHAP completed. Do not require larger excluded studies.

Whole task: (1) critically position this controlled low-dimensional clinical-prior comparison against broad benchmarks, Bayesian survival prior/variable-selection studies, piecewise baseline work and survival-XAI; identify precise defensible contribution without claiming new model components. Include seminal literature and relevant recent work through2026 as available; do not claim exhaustive novelty proof. (2) audit methodology justification and assumptions: full likelihood versus Cox partial likelihood; interval/time scaling; prior shape versus regularisation-strength confounding; half-t regularised-horseshoe variant versus canonical PV; continuous variance mixture versus genuine spike-and-slab selection; prior/PPC/model adequacy versus sampling diagnostics; Schoenfeld PH checks; nested/repeated CV; training censoring survival and IPCW; IBS,UnoC,HarrellC,time-dependentAUC; complementary-log-log calibration intercept/slope and fixed-slope CITL; corrected repeatedCV paired intervals and multiplicity; explanation posterior uncertainty versus deterministic SHAP, grouped categories/centred training background and sampling stability. (3) identify claims needing correction or qualification and give precise source-supported replacement reasoning, without changing frozen scientific design or inventing calculations/results. (4) return an organised critical synthesis with exact titles, authors/year/DOI, primary-source support and full-text passages where feasible, paper-to-claim mappings and clear distinctions from this study.

Existing central sources: SurvBenchmark10.1093/gigascience/giac071; Tang spike-and-slab lasso Cox10.1093/bioinformatics/btx300; Nikooienejad inverse-moment priors10.1214/20-AOAS1325; Samorodnitsky pan-cancer spike/slab10.1186/s12859-022-04770-3; Wu Cox variable selection10.1080/02664763.2021.1893285; Alvares BUGS10.1002/sim.8933; Alvares INLA10.1002/sim.10160; Lazaro flexible baseline10.1002/bimj.201900211; PiironenVehtari10.1214/17-EJS1337SI; Carvalho10.1093/biomet/asq017; Park survival metrics10.3348/kjr.2021.0223 (earlier draft wrongly said it ignored censoring, correct this); Austin calibration10.1002/sim.8570; McLernon10.7326/M22-0844; DeepSurv10.1186/s12874-018-0482-1; SurvSHAP(t)10.1016/j.knosys.2022.110234; Suresh model-agnostic survival explanations10.1002/sim.10057; Song Gaussian/diffused-gamma Cox priors10.1007/s12561-023-09395-5; Wiesenfarth prior impact10.1111/biom.13124; Vehtari Rhat10.1214/20-BA1221; NadeauBengio10.1023/A:1024068626366. Prioritise original research and official methods; broader clinical application papers can support relevant context but cannot stand in for MCMC or calibration theory. No administrative/funding/ethics material and no grade/journal-acceptance promises.

# Research Dossier for **Explainable Bayesian Survival Models**

Ravi Ramchandani’s *Explainable Bayesian Survival Models* can be strengthened by restoring claim-relevant scholarship, sharpening its controlled-comparison contribution, and qualifying methodological claims without changing the frozen design. The dossier below supplies insertion-ready reasoning for the existing chapters; it does not propose new experiments or replace valid original scholarship.

**Boundary:** neither thesis version, the original bibliography, nor the list of 25 omitted citations is supplied. Consequently, the mappings below identify defensible restoration candidates—not verified identities of the omitted entries. Study specifications and numerical outcomes are treated as author-supplied facts, not independently verified results.

## Defensible Contribution

The strongest contribution is **a controlled empirical comparison of three specified prior configurations within one full-likelihood survival model**, accompanied by predictive evaluation, computational feasibility reporting, robustness analyses, and exact explanations of a linear risk score. It is not the invention of Bayesian survival modelling, regularised horseshoes, continuous shrinkage, piecewise baselines, or survival explanations: these components have substantial precedents [[1.1]](https://consensus.app/papers/alvares-lázaro-bayesian-survival-analysis-with-bugs/w:5ddd5c71-9bad-40ed-8d54-6b5696f7dbf6/) [[2.1]](https://consensus.app/papers/piironen-vehtari-sparsity-information-and-regularization-in-the/w:03640a15-f6c5-4062-bed8-5f477b090a4b/) [[3.1]](https://consensus.app/papers/lázaro-armero-bayesian-regularization-for-flexible-baseline/w:705beec8-2a0a-4d41-9f34-dc8e20d4c4f7/) [[4.1]](https://consensus.app/papers/krzyziński-spytek-survshapt-timedependent-explanations-of-machine/w:24a437ce-f550-4dbc-84d4-652092196cfb/).

### Benchmark Positioning

| Literature | Relevant Finding | Distinction From This Thesis | Citations |
|---|---|---|---|
| Zhang et al., *SurvBenchmark* | Twenty methods, sixteen datasets; rankings vary by metric | Broader benchmarking, not a common-likelihood prior comparison | [[5.1]](https://consensus.app/papers/zhang-wong-survbenchmark-comprehensive-benchmarking-study-of/w:0ec6dcdf-f686-437e-aa1a-2b9bd76f8a6d/) |
| Burk et al., low-dimensional benchmark | Twenty-one models, thirty-four datasets; no statistically significant improvement over CoxPH | Strong contemporary comparator, but excludes DeepSurv from its evaluated suite | [[6.1]](https://consensus.app/papers/burk-zobolas-a-largescale-neutral-comparison-study-of-survival/w:435c2c95-6414-4377-b5f5-a79cfccb977c/) [[6.2]](https://consensus.app/papers/burk-zobolas-a-largescale-neutral-comparison-study-of-survival/w:435c2c95-6414-4377-b5f5-a79cfccb977c/) [[6.3]](https://consensus.app/papers/burk-zobolas-a-largescale-neutral-comparison-study-of-survival/w:435c2c95-6414-4377-b5f5-a79cfccb977c/) |
| Herrmann et al., multi-omics benchmark | Only block forest slightly outperformed clinical Cox on average | High-dimensional molecular setting differs from eight or nine source predictors | [[7.1]](https://consensus.app/papers/herrmann-probst-largescale-benchmark-study-of-survival-prediction/w:7d964efb-53b7-41ed-956c-7c1aa91a4823/) [[7.2]](https://consensus.app/papers/herrmann-probst-largescale-benchmark-study-of-survival-prediction/w:7d964efb-53b7-41ed-956c-7c1aa91a4823/) |
| Baralou et al., simulation comparison | RSF benefits from interactions as event information increases | Supports conditional, not universal, model-performance expectations | [[8.1]](https://consensus.app/papers/baralou-kalpourtzi-individual-risk-prediction-comparing-random/w:a4f7d820-3e90-434b-a3ed-c8b8cff0656a/) [[8.2]](https://consensus.app/papers/baralou-kalpourtzi-individual-risk-prediction-comparing-random/w:a4f7d820-3e90-434b-a3ed-c8b8cff0656a/) |
| Katzman et al., DeepSurv | Neural-network Cox proportional-hazards model | Nonlinear predictor does not itself remove proportional hazards | [[9.1]](https://consensus.app/papers/katzman-shaham-deepsurv-personalized-treatment-recommender-system/w:a2d858a1-18fd-4e6a-8c22-fafbfe8faa68/) |

**Figure 1:** Benchmark findings and their boundaries for this thesis

Recent overlap should narrow—not erase—the contribution. Yılmaz compares six survival models under explicitly low-events-per-variable regimes, but its reported range is 0.6–7.6, unlike a study described primarily by eight or nine clinical source predictors [[10.1]](https://consensus.app/papers/yılmaz-regularized-cox-models-versus-deep-survival/w:e7069eee-e0e9-4485-8063-6a9af1342b32/) [[10.2]](https://consensus.app/papers/yılmaz-regularized-cox-models-versus-deep-survival/w:e7069eee-e0e9-4485-8063-6a9af1342b32/). Knaus et al. use piecewise-exponential models with shrinkage of time-varying effects, while Jacobs et al. shrink survival-tree step heights; neither is the same static-coefficient prior comparison [[11.1]](https://consensus.app/papers/knaus-winkler-flexible-yet-sparse-bayesian-survival-models-with/w:0e73de1d-0f4c-4d22-bb73-a6c1f5a9e076/) [[12.1]](https://consensus.app/papers/jacobs-wieringen-horseshoe-forests-for-highdimensional-causal/w:3936d947-1180-4a0b-98e6-3a730ac97d0d/). Jung and Gerstung instead target scalable partial-likelihood inference through stochastic variational approximation [[13.1]](https://consensus.app/papers/jung-gerstung-bayesian-cox-regression-for-largescale-inference/w:03521094-caec-4de7-8218-e35fb8047222/) [[13.2]](https://consensus.app/papers/jung-gerstung-bayesian-cox-regression-for-largescale-inference/w:03521094-caec-4de7-8218-e35fb8047222/).

**Suggested contribution wording:**

> This thesis evaluates predictive performance, computational reliability, and risk-score explanations for three prespecified Bayesian prior configurations under a shared piecewise-exponential proportional-hazards likelihood on three low-dimensional clinical cohorts. Its contribution is the controlled comparison and transparent accounting of its results, rather than new model components or an exhaustive novelty claim.

## Scholarship Restoration Map

Restore references where their substantive claims belong. Do not restore every original entry automatically, and do not treat newly added methods references as substitutes for relevant original scholarship.

### Bayesian Survival and Priors

Exact titles and DOI strings below follow the supplied records. Author lists are abbreviated where necessary.

| Source | Exact Title | Appropriate Supporting Claim and Boundary | Citations |
|---|---|---|---|
| Carvalho, Polson & Scott, 2010. DOI: `10.1093/biomet/asq017` | The horseshoe estimator for sparse signals | Seminal normal-scale-mixture shrinkage; sparse-signal theory does not establish superiority here | [[14.1]](https://consensus.app/papers/carvalho-polson-the-horseshoe-estimator-for-sparse-signals/w:e4d95810-f885-4ba6-bd15-fb006c9a7588/) [[14.2]](https://consensus.app/papers/carvalho-polson-the-horseshoe-estimator-for-sparse-signals/w:e4d95810-f885-4ba6-bd15-fb006c9a7588/) |
| Piironen & Vehtari, 2017. DOI: `10.1214/17-ejs1337si` | Sparsity information and regularization in the horseshoe and other shrinkage priors | Separates sparsity assumptions from regularisation of large coefficients | [[2.2]](https://consensus.app/papers/piironen-vehtari-sparsity-information-and-regularization-in-the/w:03640a15-f6c5-4062-bed8-5f477b090a4b/) [[2.3]](https://consensus.app/papers/piironen-vehtari-sparsity-information-and-regularization-in-the/w:03640a15-f6c5-4062-bed8-5f477b090a4b/) |
| Tang et al., 2017. DOI: `10.1093/bioinformatics/btx300` | The spike-and-slab lasso Cox model for survival prediction and associated genes detection | Hierarchical Cox methodology for thousands of molecular features; different fitting algorithm | [[15.1]](https://consensus.app/papers/tang-shen-the-spikeandslab-lasso-cox-model-for-survival/w:cece8a71-7532-43e6-b15d-ab4d6ce2b72f/) [[15.2]](https://consensus.app/papers/tang-shen-the-spikeandslab-lasso-cox-model-for-survival/w:cece8a71-7532-43e6-b15d-ab4d6ce2b72f/) [[15.3]](https://consensus.app/papers/tang-shen-the-spikeandslab-lasso-cox-model-for-survival/w:cece8a71-7532-43e6-b15d-ab4d6ce2b72f/) |
| Nikooie, Wang & Johnson, 2020. DOI: `10.1214/20-aoas1325` | Bayesian variable selection for survival data using inverse moment priors | Explicit point mass at zero, Cox partial likelihood, model-averaged prediction | [[16.1]](https://consensus.app/papers/nikooie-wang-bayesian-variable-selection-for-survival-data/w:5e75dfa7-5637-4d1a-a9ce-1a4664a1c3fd/) [[16.2]](https://consensus.app/papers/nikooie-wang-bayesian-variable-selection-for-survival-data/w:5e75dfa7-5637-4d1a-a9ce-1a4664a1c3fd/) |
| Samorodnitsky, Hoadley & Lock, 2022. DOI: `10.1186/s12859-022-04770-3` | A hierarchical spike-and-slab model for pan-cancer survival using pan-omic data | Information borrowing across cancers and omics sources, not independent clinical-cohort fitting | [[17.1]](https://consensus.app/papers/samorodnitsky-hoadley-a-hierarchical-spikeandslab-model-for-pancancer/w:73606f86-d109-48bf-90fe-ad47b76870e4/) [[17.2]](https://consensus.app/papers/samorodnitsky-hoadley-a-hierarchical-spikeandslab-model-for-pancancer/w:73606f86-d109-48bf-90fe-ad47b76870e4/) |
| Wu, Ahn & Yang, 2021. DOI: `10.1080/02664763.2021.1893285` | Spike-and-slab type variable selection in the Cox proportional hazards model for high-dimensional features | Transformed partial-likelihood framework with stochastic variable search | [[18.1]](https://consensus.app/papers/wu-ahn-spikeandslab-type-variable-selection-in-the-cox/w:2a7b1ea3-3842-4fcf-8972-0870f24ca080/) [[18.2]](https://consensus.app/papers/wu-ahn-spikeandslab-type-variable-selection-in-the-cox/w:2a7b1ea3-3842-4fcf-8972-0870f24ca080/) |
| Song, Guha & Li, 2023. DOI: `10.1007/s12561-023-09395-5` | Bayesian Inference for High Dimensional Cox Models with Gaussian and Diffused-Gamma Priors: A Case Study of Mortality in COVID-19 Patients Admitted to the ICU | Distinct continuous prior construction using Cox partial likelihood | [[19.1]](https://consensus.app/papers/song-guha-bayesian-inference-for-high-dimensional-cox-models/w:a28e54b7-569c-4af1-a047-b5303b0ff908/) [[19.2]](https://consensus.app/papers/song-guha-bayesian-inference-for-high-dimensional-cox-models/w:a28e54b7-569c-4af1-a047-b5303b0ff908/) |
| Tang et al., 2019. DOI: `10.1186/s12859-019-2656-1` | Gsslasso Cox: a Bayesian hierarchical model for predicting survival and detecting associated genes by incorporating pathway information | Group-aware shrinkage incorporating biological pathways | [[20.1]](https://consensus.app/papers/tang-lei-gsslasso-cox-a-bayesian-hierarchical-model-for/w:2418ac79-12f3-4bbc-ac1f-85368dac1516/) [[20.2]](https://consensus.app/papers/tang-lei-gsslasso-cox-a-bayesian-hierarchical-model-for/w:2418ac79-12f3-4bbc-ac1f-85368dac1516/) |

**Figure 2:** Prior scholarship mapped to defensible restoration claims

The inverse-moment record lists **“Amir Nikooie”**; verify the publisher’s author spelling before replacing the thesis’s “Nikooienejad.” Tang’s earlier *The Spike-and-Slab Lasso Generalized Linear Models for Prediction and Associated Genes Detection* supplies methodological ancestry, but its GLM results should not replace the survival-specific Cox reference [[21.1]](https://consensus.app/papers/tang-shen-the-spikeandslab-lasso-generalized-linear-models/w:f97d18b4-dccb-4166-a5fd-9dd066f4ff28/).

### Baselines, Evaluation, and Explanations

| Source | Exact Title | Restoration Role | Citations |
|---|---|---|---|
| Alvares et al., 2021. DOI: `10.1002/sim.8933` | Bayesian survival analysis with BUGS | Bayesian survival implementation and posterior-derived quantities | [[1.2]](https://consensus.app/papers/alvares-lázaro-bayesian-survival-analysis-with-bugs/w:5ddd5c71-9bad-40ed-8d54-6b5696f7dbf6/) [[1.3]](https://consensus.app/papers/alvares-lázaro-bayesian-survival-analysis-with-bugs/w:5ddd5c71-9bad-40ed-8d54-6b5696f7dbf6/) |
| Alvares et al., 2024. DOI: `10.1002/sim.10160` | Bayesian survival analysis with INLA | Alternative approximation, model checks, and prior sensitivity | [[22.1]](https://consensus.app/papers/alvares-niekerk-bayesian-survival-analysis-with-inla/w:4b166508-8282-4389-8315-dacd71401330/) [[22.2]](https://consensus.app/papers/alvares-niekerk-bayesian-survival-analysis-with-inla/w:4b166508-8282-4389-8315-dacd71401330/) |
| Lázaro, Armero & Alvares, 2020. DOI: `10.1002/bimj.201900211` | Bayesian regularization for flexible baseline hazard functions in Cox survival models | Partition and baseline-regularisation choices affect flexibility | [[3.2]](https://consensus.app/papers/lázaro-armero-bayesian-regularization-for-flexible-baseline/w:705beec8-2a0a-4d41-9f34-dc8e20d4c4f7/) |
| Park et al., 2021. DOI: `10.3348/kjr.2021.0223` | Review of Statistical Methods for Evaluating the Performance of Survival or Other Time-to-Event Prediction Models (from Conventional to Deep Learning Approaches) | C-indices, time-dependent ROC, calibration, and Brier score | [[23.1]](https://consensus.app/papers/park-park-review-of-statistical-methods-for-evaluating-the/w:777061af-a150-4546-8a1d-81e67551b0c8/) |
| Austin, Harrell & Van Klaveren, 2020. DOI: `10.1002/sim.8570` | Graphical calibration curves and the integrated calibration index (ICI) for survival models | Smoothed survival calibration and absolute calibration-error summaries | [[24.1]](https://consensus.app/papers/austin-harrell-graphical-calibration-curves-and-the-integrated/w:e21e59a8-60e0-421b-8967-d46fa638c62d/) [[24.2]](https://consensus.app/papers/austin-harrell-graphical-calibration-curves-and-the-integrated/w:e21e59a8-60e0-421b-8967-d46fa638c62d/) |
| McLernon et al., 2022 online record. DOI: `10.7326/m22-0844` | Assessing Performance and Clinical Usefulness in Prediction Models With Survival Outcomes: Practical Guidance for Cox Proportional Hazards Models | Fixed-horizon versus follow-up-wide assessment | [[25.1]](https://consensus.app/papers/mclernon-giardiello-assessing-performance-and-clinical-usefulness-in/w:2a1ef30f-b48e-4b8a-81bf-b60f09725cea/) [[25.2]](https://consensus.app/papers/mclernon-giardiello-assessing-performance-and-clinical-usefulness-in/w:2a1ef30f-b48e-4b8a-81bf-b60f09725cea/) |
| Krzyziński et al., 2022 online record. DOI: `10.1016/j.knosys.2022.110234` | SurvSHAP(t): Time-dependent explanations of machine learning survival models | Explains functional survival predictions over time | [[4.2]](https://consensus.app/papers/krzyziński-spytek-survshapt-timedependent-explanations-of-machine/w:24a437ce-f550-4dbc-84d4-652092196cfb/) [[4.1]](https://consensus.app/papers/krzyziński-spytek-survshapt-timedependent-explanations-of-machine/w:24a437ce-f550-4dbc-84d4-652092196cfb/) |
| Suresh, Görg & Ghosh, 2024. DOI: `10.1002/sim.10057` | Model‐agnostic explanations for survival prediction models | Local explanations of fixed-time predictions and entire curves | [[26.1]](https://consensus.app/papers/suresh-görg-model‐agnostic-explanations-for-survival/w:409da791-8b32-48f0-a039-3a01b36a43b7/) [[26.2]](https://consensus.app/papers/suresh-görg-model‐agnostic-explanations-for-survival/w:409da791-8b32-48f0-a039-3a01b36a43b7/) [[26.3]](https://consensus.app/papers/suresh-görg-model‐agnostic-explanations-for-survival/w:409da791-8b32-48f0-a039-3a01b36a43b7/) |

**Figure 3:** Baseline evaluation and explanation sources for restoration

Seminal Cox scholarship belongs in the foundations, but the supplied identifiable *Regression Models and Life-Tables* record is a **1992 reprint**, not verified metadata for the original publication [[27.1]](https://consensus.app/papers/cox-regression-models-and-lifetables/w:1ffd80cf-e70d-4d25-a48b-c677a1be0836/). Similarly, the supplied *Bayesian Survival Analysis* record attributed to Margaret May is a book review, not the underlying methods book [[28.1]](https://consensus.app/papers/may-bayesian-survival-analysis/w:e776f990-d4dd-4237-8987-5be4424dbaf6/).

## Frozen-Design Methodology Audit

### Likelihood and Prior Specification

The full likelihood estimates baseline hazards and coefficients jointly; Cox’s conditional likelihood supplies inference for coefficients without specifying the same baseline model [[3.3]](https://consensus.app/papers/lázaro-armero-bayesian-regularization-for-flexible-baseline/w:705beec8-2a0a-4d41-9f34-dc8e20d4c4f7/) [[29.1]](https://consensus.app/papers/regression-models-and-lifetables/w:7d23f983-7783-4c68-8e65-0d32f6e45f2e/). Accordingly, **only the three Bayesian arms isolate prior configuration**; Bayesian-versus-CoxPH contrasts also differ in baseline treatment and likelihood.

Six event-quantile intervals are a prespecified modelling choice, not a literature-established optimum. Piecewise models show partition sensitivity, and adaptive-partition research explicitly questions a universal optimal partition [[3.4]](https://consensus.app/papers/lázaro-armero-bayesian-regularization-for-flexible-baseline/w:705beec8-2a0a-4d41-9f34-dc8e20d4c4f7/) [[30.1]](https://consensus.app/papers/li-seo-bayesian-survival-analysis-using-gamma-processes/w:070b37c6-c524-415e-8f11-988c2459369c/). Li, Seo and Lee estimate cutpoint number and position, whereas this thesis intentionally freezes them [[30.2]](https://consensus.app/papers/li-seo-bayesian-survival-analysis-using-gamma-processes/w:070b37c6-c524-415e-8f11-988c2459369c/). Chellai and Boudrissa also report sensitivity of likelihood and information criteria to grid construction [[31.1]](https://consensus.app/papers/chellai-boudrissa-bayesian-estimation-of-cox-proporional-hazard/w:d996d0bf-b854-4508-895e-38af6e78f8ac/).

The following are **specification consequences**, not additional empirical results:

| Audit Point | Precise Editorial Treatment | Supporting Context | Citations |
|---|---|---|---|
| Time scaling | State training-median scaling and its induced baseline-rate units | Baseline modelling is part of fully Bayesian specification | [[3.3]](https://consensus.app/papers/lázaro-armero-bayesian-regularization-for-flexible-baseline/w:705beec8-2a0a-4d41-9f34-dc8e20d4c4f7/) |
| Normal versus shrinkage priors | Compare complete prior configurations, not shape alone | Global shrinkage encodes assumptions about sparsity | [[2.3]](https://consensus.app/papers/piironen-vehtari-sparsity-information-and-regularization-in-the/w:03640a15-f6c5-4062-bed8-5f477b090a4b/) |
| Half-t horseshoe variant | Name the supplied half-t, df=2 regularised-horseshoe variant explicitly | Regularised horseshoe controls the largest coefficients separately | [[2.1]](https://consensus.app/papers/piironen-vehtari-sparsity-information-and-regularization-in-the/w:03640a15-f6c5-4062-bed8-5f477b090a4b/) |
| Continuous variance mixture | Call gamma a continuous variance-position parameter, not inclusion probability | Genuine point-mass selection has an explicit zero component | [[16.1]](https://consensus.app/papers/nikooie-wang-bayesian-variable-selection-for-survival-data/w:5e75dfa7-5637-4d1a-a9ce-1a4664a1c3fd/) |
| Prior-impact interpretation | Do not use ECSS as an established cross-prior strength-matching result | Wiesenfarth and Calderazzo develop application-specific prior impact | [[32.1]](https://consensus.app/papers/wiesenfarth-calderazzo-quantification-of-prior-impact-in-terms-of/w:a213249b-feba-426d-8790-92206075e0ce/) [[32.2]](https://consensus.app/papers/wiesenfarth-calderazzo-quantification-of-prior-impact-in-terms-of/w:a213249b-feba-426d-8790-92206075e0ce/) |

**Figure 4:** Specification distinctions requiring precise methodological language

With the stated mixture, \(\sigma^2=0.0025+3.9975\gamma\): there is no discrete inclusion event. Likewise, holding the likelihood fixed does not match regularisation strength across priors. Piironen and Vehtari explicitly distinguish sparsity from large-effect regularisation and recommend checking whether slab width is overly restrictive [[2.2]](https://consensus.app/papers/piironen-vehtari-sparsity-information-and-regularization-in-the/w:03640a15-f6c5-4062-bed8-5f477b090a4b/) [[2.4]](https://consensus.app/papers/piironen-vehtari-sparsity-information-and-regularization-in-the/w:03640a15-f6c5-4062-bed8-5f477b090a4b/).

### Diagnostics and Model Adequacy

Keep the prespecified gates, but describe passing them as **computational acceptance**, not proof of model adequacy. Rank-based diagnostics address failures of traditional \(\widehat R\), while quantile-based efficiency and Monte Carlo error concern posterior-summary precision [[33.1]](https://consensus.app/papers/vehtari-gelman-ranknormalization-folding-and-localization-an/w:7a585f5c-57c0-4039-8442-c46ececfb5e3/) [[33.2]](https://consensus.app/papers/vehtari-gelman-ranknormalization-folding-and-localization-an/w:7a585f5c-57c0-4039-8442-c46ececfb5e3/). The exact BFMI, treedepth, and refit thresholds supplied by the author lack direct official-method documentation in this corpus; do not imply that Vehtari’s article establishes every gate.

A useful full-text passage warns that divergences can produce inference with “a bias with an unknown magnitude” [[2.5]](https://consensus.app/papers/piironen-vehtari-sparsity-information-and-regularization-in-the/w:03640a15-f6c5-4062-bed8-5f477b090a4b/). Prior checks, posterior predictive checks, and sampling checks therefore require separate reporting; Bayesian workflow explicitly separates model checking, validation, and computational troubleshooting [[34.1]](https://consensus.app/papers/gelman-vehtari-bayesian-workflow/w:415619af-ca99-484b-8e1b-9301b198c979/).

Schoenfeld-based checks address proportional hazards through residual patterns and weighted score tests [[35.1]](https://consensus.app/papers/grambsch-therneau-proportional-hazards-tests-and-diagnostics-based/w:1ca25b0c-1d8e-40c7-83e9-3c3c879ab7e6/) [[35.2]](https://consensus.app/papers/grambsch-therneau-proportional-hazards-tests-and-diagnostics-based/w:1ca25b0c-1d8e-40c7-83e9-3c3c879ab7e6/). A flexible baseline alone does not make the supplied static-coefficient model non-PH. Record the time transformation used, because residual-test conclusions can depend on it [[36.1]](https://consensus.app/papers/park-hendry-reassessing-schoenfeld-residual-tests-of/w:c8a22e98-9d9e-4a97-9dc8-3b90fa1e3839/). Case-cohort extensions are relevant background, not the appropriate primary justification for these ordinary cohorts [[37.1]](https://consensus.app/papers/xue-xie-testing-the-proportional-hazards-assumption-in/w:6f7c41d5-ddc5-4b16-9b84-2098a5edd5e7/).

## Prediction and Inference Corrections

### Validation and Censoring

Retain shared repeated outer partitions and inner IBS tuning for RSF/DeepSurv. Describe this as nested tuning for those learners—not identical tuning of all six arms. Repeated nested validation separates tuning from assessment, but repetitions remain dependent [[38.1]](https://consensus.app/papers/krstajić-buturović-crossvalidation-pitfalls-when-selecting-and/w:c441b0e7-f04c-4d8c-afcd-3d2d0a39da27/) [[39.1]](https://consensus.app/papers/wong-yeh-reliable-accuracy-estimates-from-kfold-cross/w:d090d879-82d1-407b-96bb-11bb8699ac3e/).

The cleanest full-text-compatible correction is:

> Training-estimated censoring weights were used consistently as a prespecified evaluation convention; they are not the uniquely valid IPCW implementation.

Prince et al. report “no standard” for selecting the censoring-model dataset and find that test-set estimation can be advisable under some covariate-dependent or small-sample settings [[40.1]](https://consensus.app/papers/prince-bommert-on-the-estimation-of-inverseprobabilityofcensoring/w:a61d6b5a-048a-4f65-aa48-326fa3c6c75e/) [[40.2]](https://consensus.app/papers/prince-bommert-on-the-estimation-of-inverseprobabilityofcensoring/w:a61d6b5a-048a-4f65-aa48-326fa3c6c75e/). Marginal versus conditional censoring assumptions must also be distinguished: Uno’s original proposal assumes censoring independent of covariates and discusses stratified extensions [[41.1]](https://consensus.app/papers/uno-cai-on-the-c‐statistics-for-evaluating-overall/w:37db2388-ad0d-4f6d-9cac-31b7fbc3869f/) [[41.2]](https://consensus.app/papers/uno-cai-on-the-c‐statistics-for-evaluating-overall/w:37db2388-ad0d-4f6d-9cac-31b7fbc3869f/).

### Metric and Calibration Claims

| Claim Needing Repair | Replacement Reasoning | Source Boundary | Citations |
|---|---|---|---|
| “Park ignores censoring” | Park reviews survival-specific discrimination, calibration, and prediction-error measures | Correct the mischaracterisation, retain the reference | [[23.2]](https://consensus.app/papers/park-park-review-of-statistical-methods-for-evaluating-the/w:777061af-a150-4546-8a1d-81e67551b0c8/) [[23.1]](https://consensus.app/papers/park-park-review-of-statistical-methods-for-evaluating-the/w:777061af-a150-4546-8a1d-81e67551b0c8/) |
| “IBS measures calibration” | IBS assesses probability-prediction error; report calibration separately | Graf develops inaccuracy measures for survival probabilities | [[42.1]](https://consensus.app/papers/graf-schmoor-assessment-and-comparison-of-prognostic/w:84fea422-9bfb-4868-aaad-ae87ad787fb9/) [[24.3]](https://consensus.app/papers/austin-harrell-graphical-calibration-curves-and-the-integrated/w:e21e59a8-60e0-421b-8967-d46fa638c62d/) |
| “Concordance validates probabilities” | Concordance evaluates ordering, not probability agreement | Calibration is agreement between predicted probabilities and observed rates | [[41.3]](https://consensus.app/papers/uno-cai-on-the-c‐statistics-for-evaluating-overall/w:37db2388-ad0d-4f6d-9cac-31b7fbc3869f/) [[24.4]](https://consensus.app/papers/austin-harrell-graphical-calibration-curves-and-the-integrated/w:e21e59a8-60e0-421b-8967-d46fa638c62d/) |
| “UnoC eliminates censoring concerns” | Its censoring-robust target still requires estimation assumptions | Original marginal censoring assumption remains material | [[41.4]](https://consensus.app/papers/uno-cai-on-the-c‐statistics-for-evaluating-overall/w:37db2388-ad0d-4f6d-9cac-31b7fbc3869f/) [[41.1]](https://consensus.app/papers/uno-cai-on-the-c‐statistics-for-evaluating-overall/w:37db2388-ad0d-4f6d-9cac-31b7fbc3869f/) |
| “One metric establishes superiority” | Discrimination, calibration, and overall accuracy answer different questions | Benchmark performance varies across metrics | [[5.2]](https://consensus.app/papers/zhang-wong-survbenchmark-comprehensive-benchmarking-study-of/w:0ec6dcdf-f686-437e-aa1a-2b9bd76f8a6d/) [[6.4]](https://consensus.app/papers/burk-zobolas-a-largescale-neutral-comparison-study-of-survival/w:435c2c95-6414-4377-b5f5-a79cfccb977c/) |

**Figure 5:** Metric interpretations and source-supported replacement reasoning

For the implemented fixed-horizon calibration, explicitly define \(q_i=\log[-\log\widehat S_i(t)]\). A free-intercept/free-slope complementary-log-log regression and fixed-slope CITL are different specifications: CITL fixes the coefficient on \(q_i\) to one. **The supplied excerpts do not directly establish this exact IPCW-weighted formulation.** Crowson supports related Poisson calibration, its erratum corrects implementation code, and Riley supports calibration slopes on the log cumulative-hazard scale—not this exact formula [[43.1]](https://consensus.app/papers/crowson-atkinson-assessing-calibration-of-prognostic-risk-scores/w:45b4127f-b74b-406f-94c1-506b120435b2/) [[44.1]](https://consensus.app/papers/erratum-–-assessing-calibration-of-prognostic-risk/w:dd644ec2-6a24-4e79-89a2-4e499df03564/) [[45.1]](https://consensus.app/papers/riley-collins-minimum-sample-size-calculations-for-external/w:d9b3a74a-a87d-48ea-b532-27a2236526e9/).

Report horizon support, censoring weights, outcome coding, prediction clipping, and whether the slope was fixed or estimated. Calibration-curve estimators themselves differ under misspecification, and pseudo-observation methods carry censoring assumptions [[24.5]](https://consensus.app/papers/austin-harrell-graphical-calibration-curves-and-the-integrated/w:e21e59a8-60e0-421b-8967-d46fa638c62d/) [[45.2]](https://consensus.app/papers/riley-collins-minimum-sample-size-calculations-for-external/w:d9b3a74a-a87d-48ea-b532-27a2236526e9/). Distributional calibration objectives such as X-CAL or S-cal are related but different estimands, not direct validation of CITL [[46.1]](https://consensus.app/papers/mark-han-xcal-explicit-calibration-for-survival-analysis/w:7e026513-285f-4709-b72c-76e28ed0d1ce/) [[47.1]](https://consensus.app/papers/park-kang-stochastic-explicit-calibration-algorithm-for/w:54757650-02f2-4851-b1d4-2205408f276d/).

### Estimability and Statistical Conclusions

Use the supplied results unchanged: **430/450 accepted primary model-fold outcomes**, horseshoe **55/75**, and a separately labelled post-hoc target-0.999 sensitivity with **75/75**. Do not substitute sensitivity outcomes into the primary comparison. Computational failures constrain estimability; they do not themselves establish inferior predictive accuracy.

Ordinary fold-independent intervals underestimate uncertainty because observations recur across training and testing [[48.1]](https://consensus.app/papers/bates-hastie-crossvalidation-what-does-it-estimate-and-how-well/w:a7ac3fea-f290-43b0-ad90-0a832eacc304/). Nadeau–Bengio-style corrections address training-set variability, but the retrieved record has incomplete publication metadata; verify the published reference before finalising it [[49.1]](https://consensus.app/papers/série-scientifique-scientific-series-inference-for/w:59cee8c4-e52a-4cec-9bf7-42d1f1e5684c/) [[49.2]](https://consensus.app/papers/série-scientifique-scientific-series-inference-for/w:59cee8c4-e52a-4cec-9bf7-42d1f1e5684c/). Modern alternatives also require stability assumptions rather than guaranteeing universal coverage [[50.1]](https://consensus.app/papers/bayle-alexandre-crossvalidation-confidence-intervals-for-test/w:4622303c-b81c-46f1-8f56-e57e29739761/) [[51.1]](https://consensus.app/papers/austern-zhou-asymptotics-of-crossvalidation/w:28ced397-bd79-49ca-9f94-96b7b3a4652f/).

State that five of nine primary IBS contrasts were fully estimable and all their intervals included zero. This is **inconclusive evidence of differences**, not equivalence; equivalence requires justified bounds [[52.1]](https://consensus.app/papers/lakens-equivalence-tests-a-practical-primer-for-t-tests/w:5c1ce7c6-9baf-44e4-9b80-a3f0a940c703/) [[52.2]](https://consensus.app/papers/lakens-equivalence-tests-a-practical-primer-for-t-tests/w:5c1ce7c6-9baf-44e4-9b80-a3f0a940c703/). Identify the multiplicity family and distinguish pointwise intervals from any adjusted inferential claims.

## Explanation Scope and Reporting

Exact SHAP for the fixed linear risk score is a legitimate, narrower contribution than explaining posterior survival uncertainty. SurvSHAP(t) explains functional outputs, while Suresh et al. address both individual horizons and entire survival curves [[4.1]](https://consensus.app/papers/krzyziński-spytek-survshapt-timedependent-explanations-of-machine/w:24a437ce-f550-4dbc-84d4-652092196cfb/) [[26.2]](https://consensus.app/papers/suresh-görg-model‐agnostic-explanations-for-survival/w:409da791-8b32-48f0-a039-3a01b36a43b7/).

For the stated fixed-background interventional linear explanation, document
\[
\phi_j(x)=\widehat\beta_j(x_j-\bar x_{j,\mathrm{train}}).
\]
This identifies the explained scale and background; it does not establish conditional or causal attribution. Interventional and observational games answer application-dependent questions, and dependence can materially change even linear-model explanations [[53.1]](https://consensus.app/papers/chen-janizek-true-to-the-model-or-true-to-the-data/w:999dbeef-ee17-426c-87ae-4777bfd556f6/) [[53.2]](https://consensus.app/papers/chen-janizek-true-to-the-model-or-true-to-the-data/w:999dbeef-ee17-426c-87ae-4777bfd556f6/) [[54.1]](https://consensus.app/papers/aas-jullum-explaining-individual-predictions-when-features/w:218d9af4-87de-4e1d-bd7f-890a41ffb382/).

| Reporting Requirement | Interpretation | Citations |
|---|---|---|
| Group encoded categories | Declare grouping and aggregate signed contributions before absolute importance | [[54.2]](https://consensus.app/papers/aas-jullum-explaining-individual-predictions-when-features/w:218d9af4-87de-4e1d-bd7f-890a41ffb382/) |
| Fix the training background | Attribution depends on the explanation context and reference distribution | [[55.1]](https://consensus.app/papers/sundararajan-najmi-the-many-shapley-values-for-model-explanation/w:35a72d2c-79bb-4ec8-80c7-77ee8c8e3761/) [[56.1]](https://consensus.app/papers/chen-covert-algorithms-to-estimate-shapley-value-feature/w:320be533-b54f-451a-b134-c3132334e60d/) |
| Separate uncertainty sources | Posterior attribution variation differs from numerical Shapley-estimation error | [[57.1]](https://consensus.app/papers/chau-muandet-explaining-the-uncertain-stochastic-shapley-values/w:2aed198f-427d-4d79-baf2-3eb717f0f4e4/) [[58.1]](https://consensus.app/papers/covert-lee-improving-kernelshap-practical-shapley-value/w:745158b7-52ea-42e6-88d3-61483b0c6f95/) |
| Label cross-model stability | Importance across good models is not one fixed-model explanation | [[59.1]](https://consensus.app/papers/ning-ong-shapley-variable-importance-cloud-for/w:4316342c-e28c-4242-b860-8a9f7eb52059/) |
| Avoid causal language | Causal Shapley methods require additional causal structure | [[60.1]](https://consensus.app/papers/heskes-sijben-causal-shapley-values-exploiting-causal-knowledge/w:986fea69-dfe1-4f64-aa53-8d03aaffba19/) |

**Figure 6:** Explanation targets backgrounds grouping and uncertainty boundaries

Conditional Shapley estimation requires nontrivial conditional expectations; exact interventional linear SHAP does not solve that separate problem [[61.1]](https://consensus.app/papers/olsen-glad-a-comparative-study-of-methods-for-estimating/w:f4bbfed7-5a7a-413d-be2d-19371bde2921/). Explaining predictive entropy is also a distinct target from attaching posterior intervals to feature contributions [[62.1]](https://consensus.app/papers/watson-ohara-explaining-predictive-uncertainty-with-information/w:f1b0a2c6-e8cb-42b6-8fb1-ac7230e604d0/). Retain the completed robustness programme, but describe precisely which sensitivity each condition addresses rather than treating its size as proof of adequacy.

## Editorial Disposition

Preserve the existing chapters and valid scholarship. Restore omitted sources only beside accurate supporting claims, retain the frozen primary/sensitivity distinction, and make unavailable diagnostics or source verification explicit rather than inventing them.

The defensible thesis is a transparent, controlled comparison of specified priors—with computational limitations and explanation scope reported as carefully as predictive results—not a new survival-model family or a demonstration of equivalence.
 
_These search results were found and analyzed using Consensus, an AI-powered search engine for research. Try it at https://consensus.app. © 2026 Consensus NLP, Inc. Personal, non-commercial use only; redistribution requires copyright holders’ consent._
 
## References
 
`1.` Alvares D, Lázaro E, Gómez‐Rubio V, Armero C. Bayesian survival analysis with BUGS. *Statistics in Medicine.* 2021;40:2975-3020. doi:10.1002/sim.8933 · [Access through your institution](https://libkey.io/libraries/4025/articles/450254379/full-text-file?utm_source=api_3508&allow_speedbump=true)
 
> [1.1] We have discussed all the implementation details of the following Bayesian survival models: AFT, PH, mixture cure, competing risks, multi-state, frailty, and joint models of longitudinal and survival data. (Conclusion)
 
> [1.2] Then, the survival dataset used (available in an R-package) is described and each survival modeling is exemplified using Markov chain Monte Carlo (MCMC) methods 28 implemented in BUGS syntax 29 with the support of JAGS 30 and the rjags 31 package (version 4-10) for the R language (version 4.0.2). (Body)
 
> [1.3] Moreover, the computation of quantities of interest derived from posterior samples has been provided as well as some graphs that assist in the interpretation of results and decision making. (Conclusion)
 
`2.` Piironen J, Vehtari A. Sparsity information and regularization in the horseshoe and other shrinkage priors. *Electronic Journal of Statistics.* 2017;11:5018-5051. doi:10.1214/17-ejs1337si · [Access through your institution](https://libkey.io/libraries/4025/articles/168154425/full-text-file?utm_source=api_3508&allow_speedbump=true)
 
> [2.1] Moreover, we introduce a generalization to the horseshoe prior, called the regularized horseshoe, that allows us to specify a minimum level of regularization to the largest values. (Abstract)
 
> [2.2] Second, the horseshoe prior has the undesired property that there is no possibility of specifying separately information about sparsity and the amount of regularization for the largest coefficients, which can be problematic with weakly identified parameters, such as the logistic regression coefficients in the case of data separation. (Abstract)
 
> [2.3] We introduce a concept of effective number of nonzero parameters, show an intuitive way of formulating the prior for the global hyperparameter based on the sparsity assumptions, and argue that the previous default choices are dubious based on their tendency to favor solutions with more unshrunk parameters than we typically expect a priori. (Abstract)
 
> [2.4] Still, it is worthwhile to compare the results to a model with a relatively loose prior on c using standard model assessment techniques (Vehtari and Ojanen, 2012; Vehtari, Gelman and Gabry, 2017) to get an indication if the slab width was chosen to be too restrictive. (Conclusion)
 
> [2.5] However, even if a very large value for c yields better predictive fit, if it produces a large number of divergent transitions, it cannot be recommended because in such cases the inference is likely to have a bias with an unknown magnitude (Betancourt, 2017a). (Conclusion)
 
`3.` Lázaro E, Armero C, Alvares D. Bayesian regularization for flexible baseline hazard functions in Cox survival models. *Biometrical Journal.* 2020;63:7-26. doi:10.1002/bimj.201900211 · [Access through your institution](https://libkey.io/libraries/4025/articles/408285292/full-text-file?utm_source=api_3508&allow_speedbump=true)
 
> [3.1] We discuss Bayesian regularization for Cox survival models defined via flexible baseline hazards specified by a mixture of piecewise constant functions and by a cubic B-spline function. (Abstract)
 
> [3.2] Flexibility and overfitting were discussed within both semiparametric options with regard to different regularization schemes expressed in terms of prior distributions and time axis partition configurations. (Conclusion)
 
> [3.3] Fully Bayesian methods for Cox models specify a model for the baseline hazard function. (Abstract)
 
> [3.4] However, PC models show a certain sensitivity to axis partition in estimating covariate effects. (Conclusion)
 
`4.` Krzyziński M, Spytek M, Baniecki H, Biecek P. SurvSHAP(t): Time-dependent explanations of machine learning survival models. *Knowledge-Based Systems.* 2022;262:110234-110234. doi:10.1016/j.knosys.2022.110234 · [Access through your institution](https://libkey.io/libraries/4025/articles/542093807/full-text-file?utm_source=api_3508&allow_speedbump=true)
 
> [4.1] SurvSHAP(t) is model-agnostic and can be applied to all models with functional output. (Abstract)
 
> [4.2] In this paper, we introduce SurvSHAP(t), the first time-dependent explanation that allows for interpreting survival black-box models. (Abstract)
 
`5.` Zhang Y, Wong G, Mann GJ, Müller S, Yang JYH. SurvBenchmark: comprehensive benchmarking study of survival analysis methods using both omics data and clinical data. *GigaScience.* 2022;11. doi:10.1093/gigascience/giac071 · [Access through your institution](https://libkey.io/libraries/4025/articles/531881282/full-text-file?utm_source=api_3508&allow_speedbump=true)
 
> [5.1] Our systematic comparison design with 320 comparisons (20 methods over 16 data sets) shows that the performances of survival models vary in practice over real-world data sets and over the choice of the evaluation metric. (Abstract)
 
> [5.2] In particular, we highlight that using multiple performance metrics is critical in providing a balanced assessment of various models. (Abstract)
 
`6.` Burk L, Zobolas J, Bischl B, Bender A, Wright MN, Sonabend R. A large-scale neutral comparison study of survival models on low-dimensional data. *Bioinformatics.* 2026;42. doi:10.1093/bioinformatics/btag186 · [Access through your institution](https://libkey.io/libraries/4025/articles/704552372/full-text-file?utm_source=api_3508&allow_speedbump=true)
 
> [6.1] Results: We benchmark 21 models, ranging from classical statistical approaches to many common machine learning methods, on 34 publicly available datasets. (Abstract)
 
> [6.2] Despite superior average ranks in overall predictive performance from individual learners like oblique random survival forests and likelihood-based boosting, and better discrimination rankings from multiple boosting- and tree-based methods as well as parametric survival models, no method statistically significantly outperforms the commonly used Cox proportional hazards model for either tuning measure. (Abstract)
 
> [6.3] This excludes some recently proposed DL based methods like DeepSurv (Katzman 2016) and DeepHit (Lee et al. 2019), which have higher computational complexity, require intensive tuning, and in initial experiments could not be evaluated reliably within our benchmark suite due to a lack of stable implementations. (Body)
 
> [6.4] Generally speaking, multiple measures should be considered for performance evaluation, as they may highlight aspects of performance relevant in different contexts. (Body)
 
`7.` Herrmann M, Probst P, Hornung R, Jurinović V, Boulesteix A. Large-scale benchmark study of survival prediction methods using multi-omics data. *Briefings in Bioinformatics.* 2020;22. doi:10.1093/bib/bbaa167 · [Access through your institution](https://libkey.io/libraries/4025/articles/400322817/full-text-file?utm_source=api_3508&allow_speedbump=true)
 
> [7.1] Different prediction methods from machine learning and statistics were applied on 18 multi-omics cancer datasets (35 to 1000 observations, up to 100 000 variables) from the database 'The Cancer Genome Atlas' (TCGA). (Abstract)
 
> [7.2] Moreover, only the block forest method outperformed the Cox model on average, and only slightly. (Abstract)
 
`8.` Baralou V, Kalpourtzi N, Touloumi G. Individual risk prediction: Comparing random forests with Cox proportional‐hazards model by a simulation study. *Biometrical Journal.* 2022;65:e2100380-e2100380. doi:10.1002/bimj.202100380 · [Access through your institution](https://libkey.io/libraries/4025/articles/535587698/full-text-file?utm_source=api_3508&allow_speedbump=true)
 
> [8.1] Under the presence of interactions, RSF performed better than Cox-PH as the number of events increased whereas Cox-S reached at least similar performance with RSF under nonlinear effects. (Abstract)
 
> [8.2] Although RSF algorithms are a promising alternative to conventional Cox-PH as data complexity increases, they require a higher number of events for training. (Abstract)
 
`9.` Katzman J, Shaham U, Cloninger A, Bates J, Jiang T, Kluger Y. DeepSurv: personalized treatment recommender system using a Cox proportional hazards deep neural network. *BMC Medical Research Methodology.* 2018;18:24-24. doi:10.1186/s12874-018-0482-1 · [Access through your institution](https://libkey.io/libraries/4025/articles/189676161/full-text-file?utm_source=api_3508&allow_speedbump=true)
 
> [9.1] Methods: We introduce DeepSurv, a Cox proportional hazards deep neural network and state-of-the-art survival method for modeling interactions between a patient's covariates and treatment effectiveness in order to provide personalized treatment recommendations. (Abstract)
 
`10.` Yılmaz E. Regularized Cox Models Versus Deep Survival Networks in Low Events-per-Variable Regimes: A Benchmark Across Censoring Levels. *IEEE Access.* 2026;14:83652-83668. doi:10.1109/access.2026.3698751 · [Access through your institution](https://libkey.io/libraries/4025/articles/711403968/full-text-file?utm_source=api_3508&allow_speedbump=true)
 
> [10.1] This paper presents a systematic benchmark of six survival models—the classical Cox model, lasso-penalized Cox, the Bayesian elastic net Cox model (BEN-Cox), random survival forests, DeepSurv, and Cox-Time—across three publicly available datasets (METABRIC, SUPPORT, and TCGA-BRCA) under controlled censoring regimes. (Abstract)
 
> [10.2] The experimental grid scans events-per-variable (EPV) ratios from 0.6 to 7.6 and censoring rates from 33% to 86%. (Abstract)
 
`11.` Knaus P, Winkler D, Schoppmann SF, Jomrich G. Flexible yet Sparse Bayesian Survival Models With Time‐Varying Coefficients and Unobserved Heterogeneity. *Statistics in Medicine.* 2026;45:e70458-e70458. doi:10.1002/sim.70458 · [Access through your institution](https://libkey.io/libraries/4025/articles/703262978/full-text-file?utm_source=api_3508&allow_speedbump=true)
 
> [11.1] Building on these advances, we propose a piecewise exponential hazard model using state of the art continuous shrinkage priors to regularize the amount of time variation we allow in the effects of the covariates. (Introduction)
 
`12.` Jacobs T, Van Wieringen WN, Van Der Pas S. Horseshoe Forests for High-Dimensional Causal Survival Analysis. *Bayesian Analysis.* 2026;-1:1-30. doi:10.1214/26-ba1603 · [Access through your institution](https://auckland.primo.exlibrisgroup.com/openurl/64UAUCK_INST/64UAUCK_INST:NEWUI?genre=article&aulast=Jacobs&issn=1931-6690&title=Bayesian+analysis&atitle=Horseshoe+Forests+for+High-Dimensional+Causal+Survival+Analysis&volume=-1&issue=-1&spage=1&epage=30&date=2026-01-01&rft_id=info%3Adoi%2F10.1214%2F26-BA1603&rft_id=info%3Apmid%2F&sid=LibKey&utm_source=consensus)
 
> [12.1] This work introduces a novel regularisation strategy for Bayesian regression tree ensembles by applying shrinkage directly to the step heights via the horseshoe prior. (Discussion)
 
`13.` Jung AW, Gerstung M. Bayesian Cox regression for large-scale inference with applications to electronic health records. *The Annals of Applied Statistics.* 2023;17:1064-1085. doi:10.1214/22-aoas1658 · [Access through your institution](https://auckland.primo.exlibrisgroup.com/openurl/64UAUCK_INST/64UAUCK_INST:NEWUI?genre=article&aulast=Jung&issn=1941-7330&title=Annals+of+applied+statistics&atitle=Bayesian+Cox+regression+for+large-scale+inference+with+applications+to+electronic+health+records&volume=17&issue=2&spage=1064&epage=1085&date=2023-06-01&rft_id=info%3Adoi%2F10.1214%2F22-AOAS1658&rft_id=info%3Apmid%2F&sid=LibKey&utm_source=consensus)
 
> [13.1] Here, we propose a Bayesian version for the counting process representation of Cox’s partial likelihood for efficient inference on large-scale datasets with millions of data points and thousands of time-dependent covariates. (Abstract)
 
> [13.2] Through the combination of stochastic variational inference and a reweighting of the log-likelihood, we obtain an approximation for the posterior distribution that factorizes over subsamples of the data, enabling the analysis in big data settings. (Abstract)
 
`14.` Carvalho CM, Polson N, Scott JG. The horseshoe estimator for sparse signals. *Biometrika.* 2010;97:465-480. doi:10.1093/biomet/asq017 · [Access through your institution](https://libkey.io/libraries/4025/articles/28414496/full-text-file?utm_source=api_3508&allow_speedbump=true)
 
> [14.1] This paper proposes a new approach to sparsity, called the horseshoe estimator, which arises from a prior based on multivariate-normal scale mixtures. (Abstract)
 
> [14.2] We prove two theorems: one that characterizes the horseshoe estimator's tail robustness and the other that demonstrates a super-efficient rate of convergence to the correct estimate of the sampling density in sparse situations. (Abstract)
 
`15.` Tang Z, Shen Y, Zhang X, Yi N. The spike-and-slab lasso Cox model for survival prediction and associated genes detection. *Bioinformatics.* 2017;33:2799-2807. doi:10.1093/bioinformatics/btx300 · [Access through your institution](https://libkey.io/libraries/4025/articles/99972832/full-text-file?utm_source=api_3508&allow_speedbump=true)
 
> [15.1] Results: We propose new Bayesian hierarchical Cox proportional hazards models, called the spike-and-slab lasso Cox, for predicting survival outcomes and detecting associated genes. (Abstract)
 
> [15.2] We also develop an efficient algorithm to fit the proposed models by incorporating Expectation-Maximization steps into the extremely fast cyclic coordinate descent algorithm. (Abstract)
 
> [15.3] We demonstrate the proposed procedure on two cancer datasets with censored survival outcomes and thousands of molecular features. (Abstract)
 
`16.` Nikooie A, Wang W, Johnson VE. Bayesian variable selection for survival data using inverse moment priors. *The Annals of Applied Statistics.* 2020;14:809-828. doi:10.1214/20-aoas1325 · [Access through your institution](https://auckland.primo.exlibrisgroup.com/openurl/64UAUCK_INST/64UAUCK_INST:NEWUI?genre=article&aulast=Nikooienejad&issn=1941-7330&title=Annals+of+applied+statistics&atitle=Bayesian+variable+selection+for+survival+data+using+inverse+moment+priors&volume=14&issue=2&spage=809&epage=828&date=2020-06-01&rft_id=info%3Adoi%2F10.1214%2F20-AOAS1325&rft_id=info%3Apmid%2F33456641&sid=LibKey&utm_source=consensus)
 
> [16.1] In this article we introduce a Bayesian variable selection procedure that uses a mixture prior composed of a point mass at zero and an inverse moment prior in conjunction with the partial likelihood defined by the Cox proportional hazard model. (Abstract)
 
> [16.2] Bayesian model averaging is used for prediction. (Abstract)
 
`17.` Samorodnitsky S, Hoadley KA, Lock EF. A hierarchical spike-and-slab model for pan-cancer survival using pan-omic data. *BMC Bioinformatics.* 2022;23:235-235. doi:10.1186/s12859-022-04770-3 · [Access through your institution](https://libkey.io/libraries/4025/articles/528313844/full-text-file?utm_source=api_3508&allow_speedbump=true)
 
> [17.1] Our model performs variable selection through spike-and-slab priors that borrow information across clustered data. (Abstract)
 
> [17.2] We use this model to predict overall patient survival from the Cancer Genome Atlas with data from 29 cancer types and 4 omics sources and use simulations to characterize the performance of the hierarchical spike-and-slab prior. (Abstract)
 
`18.` Wu R, Ahn M, Yang H. Spike-and-slab type variable selection in the Cox proportional hazards model for high-dimensional features. *Journal of Applied Statistics.* 2021;49:2189-2207. doi:10.1080/02664763.2021.1893285 · [Access through your institution](https://libkey.io/libraries/4025/articles/448633169/full-text-file?utm_source=api_3508&allow_speedbump=true)
 
> [18.1] Specifically, we consider the transformation of the score and information functions for the partial likelihood function evaluated at the given data from the parameter space into the space generated by the logarithm of the hazard ratio. (Abstract)
 
> [18.2] Then, we use a stochastic variable search Gibbs sampling approach via the spike-and-slab prior distribution to obtain the sparsity structure of the covariates associated with the survival outcome. (Abstract)
 
`19.` Song J, Guha S, Li Y. Bayesian Inference for High Dimensional Cox Models with Gaussian and Diffused-Gamma Priors: A Case Study of Mortality in COVID-19 Patients Admitted to the ICU. *Statistics in Biosciences.* 2023;16:221-249. doi:10.1007/s12561-023-09395-5 · [Access through your institution](https://libkey.io/libraries/4025/articles/593313916/full-text-file?utm_source=api_3508&allow_speedbump=true)
 
> [19.1] The Gaussian and diffused-gamma (GD) prior has emerged as a promising alternative due to its continuous-and-differentiable ℓ0-norm approximation and computational efficiency in generalized linear models. (Abstract)
 
> [19.2] In this paper, we extend the GD prior to semi-parametric Cox models by proposing a rank-based Bayesian inference procedure with the Cox partial likelihood. (Abstract)
 
`20.` Tang Z, Lei S, Zhang X, et al. Gsslasso Cox: a Bayesian hierarchical model for predicting survival and detecting associated genes by incorporating pathway information. *BMC Bioinformatics.* 2019;20:94-94. doi:10.1186/s12859-019-2656-1 · [Access through your institution](https://libkey.io/libraries/4025/articles/282933275/full-text-file?utm_source=api_3508&allow_speedbump=true)
 
> [20.1] Results: We here propose a Bayesian hierarchical Cox survival model, called the group spike-and-slab lasso Cox (gsslasso Cox), for predicting disease survival outcomes and detecting associated genes by incorporating group structures of biological pathways. (Abstract)
 
> [20.2] Conclusions: Both the theoretical and empirical studies show that the proposed method can induce weaker shrinkage on predictors in an active pathway, thereby incorporating the biological similarity of genes within a same pathway into the hierarchical modeling. (Abstract)
 
`21.` Tang Z, Shen Y, Zhang X, Yi N. The Spike-and-Slab Lasso Generalized Linear Models for Prediction and Associated Genes Detection. *Genetics.* 2016;205:77-88. doi:10.1534/genetics.116.192195 · [Access through your institution](https://libkey.io/libraries/4025/articles/67931544/full-text-file?utm_source=api_3508&allow_speedbump=true)
 
> [21.1] We propose new Bayesian hierarchical generalized linear models, called spike-and-slab lasso GLMs, for prognostic prediction and detection of associated genes using large-scale molecular data. (Abstract)
 
`22.` Alvares D, Van Niekerk J, Krainski ET, Rue H, Rustand D. Bayesian survival analysis with INLA. *Statistics in Medicine.* 2024;43:3975-4010. doi:10.1002/sim.10160 · [Access through your institution](https://libkey.io/libraries/4025/articles/620878386/full-text-file?utm_source=api_3508&allow_speedbump=true)
 
> [22.1] Section 11 gives some insights on model check and illustrates how to perform prior sensitivity analysis. (Body)
 
> [22.2] Our proposal aims to provide the reader with syntax examples for implementing survival models using a fast and accurate approximate Bayesian inferential approach. (Abstract)
 
`23.` Park SY, Park JE, Kim H, Park SH. Review of Statistical Methods for Evaluating the Performance of Survival or Other Time-to-Event Prediction Models (from Conventional to Deep Learning Approaches). *Korean Journal of Radiology.* 2021;22:1697-1697. doi:10.3348/kjr.2021.0223 · [Access through your institution](http://libkey.io/libraries/4025/articles/491973806/full-text-file?utm_source=api_3508&allow_speedbump=true)
 
> [23.1] This review article includes straightforward explanations of C indices (Harrell's C index, etc.), time-dependent receiver operating characteristic curve analysis, calibration plot, other methods for evaluating the calibration performance, and Brier score. (Abstract)
 
> [23.2] The recent introduction of various high-dimensional modeling methods, such as radiomics and deep learning, has created a much greater diversity in modeling approaches for survival prediction (or, more generally, time-to-event prediction). (Abstract)
 
`24.` Austin PC, Harrell FE, Klaveren DV. Graphical calibration curves and the integrated calibration index (ICI) for survival models. *Statistics in Medicine.* 2020;39:2714-2742. doi:10.1002/sim.8570 · [Access through your institution](https://libkey.io/libraries/4025/articles/394032686/full-text-file?utm_source=api_3508&allow_speedbump=true)
 
> [24.1] We focus on hazard regression models and restricted cubic splines in conjunction with a Cox proportional hazards model. (Abstract)
 
> [24.2] In this context, this is the average (respectively, median or 90th percentile) absolute difference between predicted survival probabilities and smoothed survival frequencies. (Abstract)
 
> [24.3] The use of calibration curves and of these numeric calibration metrics permits for a comprehensive comparison of the calibration of competing survival models. (Abstract)
 
> [24.4] In the context of survival analysis, calibration refers to the agreement between predicted probabilities and observed event rates or frequencies of the outcome within a given duration of time. (Abstract)
 
> [24.5] In contrast, under a mis-specified model, the smoothed calibration curved constructed using hazard regression tended to be closer to the true calibration curve. (Abstract)
 
`25.` McLernon DJ, Giardiello D, Van Calster B, et al. Assessing Performance and Clinical Usefulness in Prediction Models With Survival Outcomes: Practical Guidance for Cox Proportional Hazards Models. *Annals of Internal Medicine.* 2022;176:105-114. doi:10.7326/m22-0844 · [Access through your institution](https://libkey.io/libraries/4025/articles/541781132/full-text-file?utm_source=api_3508&allow_speedbump=true)
 
> [25.1] We distinguished measures to assess model performance at speci fi c time points (such as 5-year survival) and over the range of follow-up times. (Body)
 
> [25.2] In conclusion, the guidance in this article may assist readers and applied researchers to know how to assess, report, and interpret discrimination, calibration, and overall performance for survival prediction models. (Conclusion)
 
`26.` Suresh K, Görg C, Ghosh D. Model‐agnostic explanations for survival prediction models. *Statistics in Medicine.* 2024;43:2161-2182. doi:10.1002/sim.10057 · [Access through your institution](https://libkey.io/libraries/4025/articles/610159176/full-text-file?utm_source=api_3508&allow_speedbump=true)
 
> [26.1] (i) survival predictions at particular follow-up times, and (Abstract)
 
> [26.2] (ii) a patient's overall predicted survival curve. (Abstract)
 
> [26.3] We extend the local interpretable model-agnostic explainer framework for classification outcomes to survival prediction models. (Abstract)
 
`27.` Cox DR. Regression Models and Life-Tables. *Springer series in statistics.* 1992;34:527-541. doi:10.1007/978-1-4612-4380-9_37
 
> [27.1] The hazard function (age-specific failure rate) is taken to be a function of the explanatory variables and unknown regression coefficients multiplied by an arbitrary and unknown function of time. (Abstract)
 
`28.` May M. Bayesian Survival Analysis.. *International Journal of Epidemiology.* 2002;31:505-505. doi:10.1093/intjepid/31.2.505 · [Access through your institution](https://libkey.io/libraries/4025/articles/75842664/full-text-file?utm_source=api_3508&allow_speedbump=true)
 
> [28.1] The book is about Bayesian survival analysis which is illustrated with examples that mostly use the BUGS software package. (Body)
 
`29.` Regression Models and Life-Tables.
 
> [29.1] A conditional likelihood is obtained, leading to inferences about the unknown regression coefficients. (Abstract)
 
`30.` Li Y, Seo S, Lee KH. Bayesian survival analysis using gamma processes with adaptive time partition. *Journal of Statistical Computation and Simulation.* 2021;91:2937-2952. doi:10.1080/00949655.2021.1912752 · [Access through your institution](https://libkey.io/libraries/4025/articles/459145625/full-text-file?utm_source=api_3508&allow_speedbump=true)
 
> [30.1] However, it would be controversial to suggest a general guideline to construct an optimal time partition. (Abstract)
 
> [30.2] A key feature of the proposed framework is that the number and position of interval cutpoints are treated as random and estimated based on their posterior distributions. (Abstract)
 
`31.` Chellai F, Boudrissa N. Bayesian Estimation of Cox Proporional Hazard model under A Piecewise Constant model for Baseline Hazard and the problem of Survival Time Axis Grid. *African Journal of Applied Statistics.* 2019;6:551-563. doi:10.16929/ajas/2019.551.230 · [Access through your institution](https://auckland.primo.exlibrisgroup.com/openurl/64UAUCK_INST/64UAUCK_INST:NEWUI?genre=article&aulast=Fatih&issn=2316-0861&title=African+Journal+of+Applied+Statistics&atitle=Bayesian+Estimation+of+Cox+Proporional+Hazard+model+under+A+Piecewise+Constant+model+for+Baseline+Hazard+and+the+problem+of+Survival+Time+Axis+Grid&volume=6&issue=1&spage=551&epage=563&date=2019-01-01&rft_id=info%3Adoi%2F10.16929%2Fajas%2F2019.551.230&rft_id=info%3Apmid%2F&sid=LibKey&utm_source=consensus)
 
> [31.1] The determination of the number and the lengths of intervals of the baseline risk function λ 0 (t), is an important issue in Piecewise constant Exponential Models (PEM) and Proportional Hazard Models (PH), especially, when using Bayesian inference.In this context, we propose a simple method to estimate that number and thoses lenghts of interval for constructing Bayesian PH Cox model.Based on real data, the obtained results that the estimated parameters are not affected, but the log-likelihood and information criterion are very sensitive.On this, the problem of model selection is considered to assess the influence on decision making. (Abstract)
 
`32.` Wiesenfarth M, Calderazzo S. Quantification of prior impact in terms of effective current sample size. *Biometrics.* 2019;76:326-336. doi:10.1111/biom.13124 · [Access through your institution](https://libkey.io/libraries/4025/articles/332469268/full-text-file?utm_source=api_3508&allow_speedbump=true)
 
> [32.1] We build on a recent work to relate prior impact to the number of (virtual) samples from the current data model and introduce the effective current sample size (ECSS) of a prior, tailored to the application in Bayesian clinical trial designs. (Abstract)
 
> [32.2] Furthermore, the ECSS can help overcome lack of consensus in the ESS assessment of mixture priors and can, more broadly, provide further insights into the impact of priors. (Abstract)
 
`33.` Vehtari A, Gelman A, Simpson D, Carpenter B, Bürkner P. Rank-Normalization, Folding, and Localization: An Improved Rˆ for Assessing Convergence of MCMC (with Discussion). *Bayesian Analysis.* 2020;16:667-718. doi:10.1214/20-ba1221 · [Access through your institution](https://libkey.io/libraries/4025/articles/399758772/full-text-file?utm_source=api_3508&allow_speedbump=true)
 
> [33.1] Traditional Rˆ will fail to correctly diagnose convergence failures when the chain has a heavy tail or when the variance varies across the chains. (Abstract)
 
> [33.2] We also introduce a collection of quantile-based local efficiency measures, along with a practical approach for computing Monte Carlo error estimates for quantiles. (Abstract)
 
`34.` Gelman A, Vehtari A, McElreath R, et al. Bayesian Workflow. *Chapman & Hall/CRC eBooks.* 2026. doi:10.1201/9781003044024
 
> [34.1] Beyond inference, the workflow also includes iterative model building, model checking, validation and troubleshooting of computational problems, model understanding, and model comparison. (Abstract)
 
`35.` Grambsch PM, Therneau TM. Proportional Hazards Tests and Diagnostics Based on Weighted Residuals. *Biometrika.* 1994;81:515-515. doi:10.1093/biomet/81.3.515 · [Access through your institution](https://libkey.io/libraries/4025/articles/28412699/full-text-file?utm_source=api_3508&allow_speedbump=true)
 
> [35.1] We show that the function /3(t) can be directly visualized by smoothing an appropriate residual plot. (Abstract)
 
> [35.2] Also, many tests of proportional hazards, including those of Cox (1972), Gill & Schumacher (1987), Harrell (1986), Lin (1991), Moreau, O'Quigley & Mesbah (1985), Nagelkerke, Oosting & Hart (1984), O'Quigley & Pessione (1989), Schoenfeld (1980) and Wei (1984) are related to time-weighted score tests of the proportional hazards hypothesis, and can be visualized as a weighted least-squares line fitted to the residual plot. (Abstract)
 
`36.` Park S, Hendry DJ. Reassessing Schoenfeld Residual Tests of Proportional Hazards in Political Science Event History Analyses. *American Journal of Political Science.* 2015;59:1072-1087. doi:10.1111/ajps.12176 · [Access through your institution](https://libkey.io/libraries/4025/articles/54012046/full-text-file?utm_source=api_3508&allow_speedbump=true)
 
> [36.1] Using replications and simulations, we demonstrate that the decision about time transformations can have profound implications for the conclusions reached. (Abstract)
 
`37.` Xue X, Xie X, Gunter MJ, et al. Testing the proportional hazards assumption in case-cohort analysis. *BMC Medical Research Methodology.* 2013;13:88-88. doi:10.1186/1471-2288-13-88 · [Access through your institution](https://libkey.io/libraries/4025/articles/45789731/full-text-file?utm_source=api_3508&allow_speedbump=true)
 
> [37.1] Methods: We extended the correlation test based on Schoenfeld residuals, an approach used to evaluate the proportionality of hazards in standard Cox models. (Abstract)
 
`38.` Krstajić D, Buturović LJ, Leahy DE, Thomas S. Cross-validation pitfalls when selecting and assessing regression and classification models. *Journal of Cheminformatics.* 2014;6:10-10. doi:10.1186/1758-2946-6-10 · [Access through your institution](https://libkey.io/libraries/4025/articles/49940107/full-text-file?utm_source=api_3508&allow_speedbump=true)
 
> [38.1] Methods: We describe in detail an algorithm for repeated grid-search V-fold cross-validation for parameter tuning in classification and regression, and we define a repeated nested cross-validation algorithm for model assessment. (Abstract)
 
`39.` Wong T, Yeh P. Reliable Accuracy Estimates from k-Fold Cross Validation. *IEEE Transactions on Knowledge and Data Engineering.* 2019;32:1586-1594. doi:10.1109/tkde.2019.2912815 · [Access through your institution](https://libkey.io/libraries/4025/articles/302771603/full-text-file?utm_source=api_3508&allow_speedbump=true)
 
> [39.1] Most of them did not consider the correlation among the replications of <italic>k</italic>-fold cross validation, and hence the variance could be underestimated. (Abstract)
 
`40.` Prince T, Bommert A, Rahnenführer J, Schmid MC. On the estimation of inverse-probability-of-censoring weights for the evaluation of survival prediction error. *PLoS ONE.* 2025;20:e0318349-e0318349. doi:10.1371/journal.pone.0318349 · [Access through your institution](https://libkey.io/libraries/4025/articles/650462487/full-text-file?utm_source=api_3508&allow_speedbump=true)
 
> [40.1] There seems to be considerable disagreement between authors with regards to this issue, and no standard has been established so far. (Abstract)
 
> [40.2] However, in some circumstances, such as in the case of a covariate-dependent censoring process, a small sample size, or when dealing with noisy data, it may be advisable to use the test set instead of the training set to model the censoring distribution. (Abstract)
 
`41.` Uno H, Cai T, Pencina MJ, D’Agostino RB, Wei LJ. On the C‐statistics for evaluating overall adequacy of risk prediction procedures with censored survival data. *Statistics in Medicine.* 2011;30:1105-1117. doi:10.1002/sim.4154 · [Access through your institution](https://libkey.io/libraries/4025/articles/26700961/full-text-file?utm_source=api_3508&allow_speedbump=true)
 
> [41.1] For the new proposal, we assume that the censoring distribution is independent of the covariates. (Discussion)
 
> [41.2] When the covariate vector can be discretized, our new procedure can be modified easily using stratified Kaplan-Meier estimates for the censoring. (Discussion)
 
> [41.3] To evaluate the adequacy of such a system, C-statistics are routinely used in the medical literature to quantify the capacity of the estimated risk score in discriminating among subjects with different event times. (Abstract)
 
> [41.4] The new procedure consistently estimates a conventional concordance measure which is free of censoring. (Abstract)
 
`42.` Graf E, Schmoor C, Sauerbrei W, Schumacher M. Assessment and comparison of prognostic classification schemes for survival data. *Statistics in Medicine.* 1999;18:2529-2545. doi:10.1002/(sici)1097-0258(19990915/30)18:17/18<2529::aid-sim274>3.0.co;2-5 · [Access through your institution](https://libkey.io/libraries/4025/articles/25379599/full-text-file?utm_source=api_3508&allow_speedbump=true)
 
> [42.1] We review these methods and develop measures of inaccuracy which may be calculated in a validation study in order to assess the usefulness of estimated patient-specific survival probabilities associated with a prognostic classification scheme. (Abstract)
 
`43.` Crowson CS, Atkinson EJ, Therneau TM. Assessing calibration of prognostic risk scores. *Statistical Methods in Medical Research.* 2013;25:1692-1706. doi:10.1177/0962280213497434 · [Access through your institution](https://libkey.io/libraries/4025/articles/47399492/full-text-file?utm_source=api_3508&allow_speedbump=true)
 
> [43.1] We show that Poisson regression models can be used to easily assess calibration in prognostic models. (Abstract)
 
`44.` Erratum – Assessing calibration of prognostic risk scores. *Statistical Methods in Medical Research.* 2017;26:1992-1993. doi:10.1177/0962280217719818 · [Access through your institution](https://libkey.io/libraries/4025/articles/147800994/full-text-file?utm_source=api_3508&allow_speedbump=true)
 
> [44.1] fit0 <coxph(Surv(futime, status) x1þ x2þ x3, data1⁄4 data0) p <log(predict(fit0, newdata1⁄4 data1, type1⁄4 "expected")) lp <predict(fit0, newdata1⁄4 data1, type1⁄4 "lp") logbase <p lp fit1 <glm(y offset(p), family1⁄4 poisson, data1⁄4 data1) fit2 <glm(y lpþ offset(logbase), family1⁄4 poisson, data1⁄4 data1) group <cut(lp, c(-Inf, quantile(lp,(1:9)/10), Inf) fit3 <glm(y -1þ groupþ offset(p), family1⁄4 poisson, data1⁄4 data1) (Abstract)
 
`45.` Riley RD, Collins PGS, Ensor J, et al. Minimum sample size calculations for external validation of a clinical prediction model with a time‐to‐event outcome. *Statistics in Medicine.* 2021;41:1280-1295. doi:10.1002/sim.9275 · [Access through your institution](https://libkey.io/libraries/4025/articles/511564111/full-text-file?utm_source=api_3508&allow_speedbump=true)
 
> [45.1] A simulation-based framework is proposed, which calculates the sample size required to target a particular confidence interval width for the calibration slope measuring the agreement between predicted risks (from the model) and observed risks (derived using pseudo-observations to account for censoring) on the log cumulative hazard scale. (Abstract)
 
> [45.2] In particular, pseudo-observations assume non-informative censoring, and so to help mitigate against this, we suggest deriving them separately within each of, say, 10 or 20 groups defined by tenths or twentieths of predicted risk. (Discussion)
 
`46.` Mark G, Han X, Puli A, Perotte A, Ranganath R. X-CAL: Explicit Calibration for Survival Analysis.. *Advances in neural information processing systems.* 2021;33:18296-18307. doi:10.48550/arxiv.2101.05346
 
> [46.1] We develop explicit calibration (X-CAL), which turns D-CALIBRATION into a differentiable objective that can be used in survival modeling alongside maximum likelihood estimation and other objectives. (Abstract)
 
`47.` Park J, Kang S, Kim G. Stochastic Explicit Calibration Algorithm for Survival Models. *IEEE Access.* 2025;13:78679-78706. doi:10.1109/access.2025.3566156 · [Access through your institution](https://libkey.io/libraries/4025/articles/663177647/full-text-file?utm_source=api_3508&allow_speedbump=true)
 
> [47.1] In this study, we introduce Stochastic Explicit Calibration (S-cal), an algorithm that employs random intervals instead of fixed bins, thereby advancing the calibration methods used in deep networks. (Abstract)
 
`48.` Bates S, Hastie TJ, Tibshirani RJ. Cross-Validation: What Does It Estimate and How Well Does It Do It?. *Journal of the American Statistical Association.* 2023;119:1434-1445. doi:10.1080/01621459.2023.2197686 · [Access through your institution](https://libkey.io/libraries/4025/articles/565145455/full-text-file?utm_source=api_3508&allow_speedbump=true)
 
> [48.1] Because each data point is used for both training and testing, there are correlations among the measured accuracies for each fold, and so the usual estimate of variance is too small. (Abstract)
 
`49.` Série Scientifique Scientific Series Inference for the Generalization Error.
 
> [49.1] Such tests should take into account the variability due to the choice of training set and not only that due to the test examples, as is often the case. (Abstract)
 
> [49.2] Our analysis shows that all the variance estimators that are based only on the results of the cross-validation experiment must be biased. (Abstract)
 
`50.` Bayle P, Alexandre B, Janson L, Mackey LW. Cross-validation Confidence Intervals for Test Error. *arXiv (Cornell University).* 2020;33:16339-16350. doi:10.48550/arxiv.2007.12671
 
> [50.1] This work develops central limit theorems for cross-validation and consistent estimators of its asymptotic variance under weak stability conditions on the learning algorithm. (Abstract)
 
`51.` Austern M, Zhou W. Asymptotics of cross-validation. *Annales de l Institut Henri Poincaré Probabilités et Statistiques.* 2025;61:2804-2865. doi:10.1214/24-aihp1488 · [Access through your institution](https://auckland.primo.exlibrisgroup.com/openurl/64UAUCK_INST/64UAUCK_INST:NEWUI?genre=article&aulast=Austern&issn=0246-0203&title=Annales+de+l%27Institut+Henri+Poincare+%28B%29+Probability+and+Statistics&atitle=Asymptotics+of+cross-validation&volume=61&issue=4&spage=2804&epage=2865&date=2025-11-01&rft_id=info%3Adoi%2F10.1214%2F24-AIHP1488&rft_id=info%3Apmid%2F&sid=LibKey&utm_source=consensus)
 
> [51.1] Sous des conditions sur la stabilité des estimateurs considérés, nous établissons un théorème limite central et une inégalité de type Berry–Esseen, qui nous permettent de calculer des intervalles de confiance asymptotiquement corrects. (Abstract)
 
`52.` Lakens D. Equivalence Tests: A Practical Primer for t Tests, Correlations, and Meta-Analyses. *Social Psychological and Personality Science.* 2017;8:355-362. doi:10.1177/1948550617697177 · [Access through your institution](https://libkey.io/libraries/4025/articles/100208339/full-text-file?utm_source=api_3508&allow_speedbump=true)
 
> [52.1] Currently, researchers often incorrectly conclude an effect is absent based a nonsignificant result. (Abstract)
 
> [52.2] In equivalence tests, such as the two one-sided tests (TOST) procedure discussed in this article, an upper and lower equivalence bound is specified based on the smallest effect size of interest. (Abstract)
 
`53.` Chen H, Janizek JD, Lundberg S, Lee S. True to the Model or True to the Data?. *arXiv (Cornell University).* 2020;abs/2006.16234. doi:10.48550/arxiv.2006.16234
 
> [53.1] The two main approaches that have been proposed differ in the way that they condition on known features, using either (1) an interventional or (2) an observational conditional expectation. (Abstract)
 
> [53.2] While previous work has argued that one of the two approaches is preferable in general, we argue that the choice is application dependent. (Abstract)
 
`54.` Aas K, Jullum M, Løland A. Explaining individual predictions when features are dependent: More accurate approximations to Shapley values. *Artificial Intelligence.* 2021;298:103502-103502. doi:10.1016/j.artint.2021.103502
 
> [54.1] This is the case even if a simple linear model is used for predictions. (Abstract)
 
> [54.2] We also propose a method for aggregating individual Shapley values, such that the prediction can be explained by groups of dependent variables. (Abstract)
 
`55.` Sundararajan M, Najmi A. The many Shapley values for model explanation. *RePEc: Research Papers in Economics.* 2019;1:9269-9278. doi:10.48550/arxiv.1908.08474
 
> [55.1] These differ in how they reference the model, the training data, and the explanation context. (Abstract)
 
`56.` Chen H, Covert I, Lundberg S, Lee S. Algorithms to estimate Shapley value feature attributions. *Nature Machine Intelligence.* 2023;5:590-601. doi:10.1038/s42256-023-00657-x
 
> [56.1] We disentangle this complexity into two main factors: the approach to removing feature information and the tractable estimation strategy. (Abstract)
 
`57.` Chau SL, Muandet K, Sejdinović D. Explaining the Uncertain: Stochastic Shapley Values for Gaussian Process Models. *arXiv (Cornell University).* 2023;abs/2305.15167. doi:10.48550/arxiv.2305.15167
 
> [57.1] This covariance allows for quantifying explanation uncertainties and studying the statistical dependencies between explanations. (Abstract)
 
`58.` Covert I, Lee S. Improving KernelSHAP: Practical Shapley Value Estimation via Linear Regression. *arXiv (Cornell University).* 2020;abs/2012.01536. doi:10.48550/arxiv.2012.01536
 
> [58.1] By analyzing the original KernelSHAP alongside a newly proposed unbiased version, we develop techniques to detect its convergence and calculate uncertainty estimates. (Abstract)
 
`59.` Ning Y, Ong MEH, Chakraborty B, et al. Shapley variable importance cloud for interpretable machine learning. *Patterns.* 2022;3:100452-100452. doi:10.1016/j.patter.2022.100452
 
> [59.1] The resulting Shapley variable importance cloud consists of Shapley-based importance measures from each good model and pools information across models to provide an overall importance measure, with uncertainty explicitly quantified to support formal statistical inference. (Abstract)
 
`60.` Heskes T, Sijben E, Bucur IG, Claassen T. Causal Shapley Values: Exploiting Causal Knowledge to Explain Individual Predictions of Complex Models. *arXiv (Cornell University).* 2020;33:4778-4789. doi:10.48550/arxiv.2011.01625
 
> [60.1] By employing Pearl's do-calculus, we show how these 'causal' Shapley values can be derived for general causal graphs without sacrificing any of their desirable properties. (Abstract)
 
`61.` Olsen LHB, Glad IK, Jullum M, Aas K. A comparative study of methods for estimating model-agnostic Shapley value explanations. *Data Mining and Knowledge Discovery.* 2024;38:1782-1829. doi:10.1007/s10618-024-01016-z
 
> [61.1] Estimating precise conditional Shapley values is difficult as they require the estimation of non-trivial conditional expectations. (Abstract)
 
`62.` Watson D, O'Hara J, Tax N, Mudd R, Guy I. Explaining Predictive Uncertainty with Information Theoretic Shapley Values. *neural information processing systems.* 2023;abs/2306.05724:7330-7350. doi:10.52202/075280-0320
 
> [62.1] We adapt the popular Shapley value framework to explain various types of predictive uncertainty, quantifying each feature's contribution to the conditional entropy of individual model outputs. (Abstract)

