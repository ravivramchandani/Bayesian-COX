# Ravi original-reference recovery audit

Original 95 references; 63 cited in original text; 32 uncited. At investigation start, 40 original entries plus 15 new entries made the 55-entry bibliography. Of the 55 removed originals, 25 had been cited and 30 had not.

The removal count alone does not establish which references belong in the revised thesis. This audit preserves all95 source records and original claim contexts; each receives a topic-specific placement. No source is excluded merely because a rewrite stopped citing it.

## Highest priority findings

- Restore ref52 BHCox as close prior literature: constrained spike-and-slab and regularised horseshoe proportional-hazards models already exist; M-spline baseline and interaction heredity distinguish it from this study.
- Restore ref68 BHAFT, ref94 Gaussian/diffused-gamma Cox, ref95 spatial Cox, and ref91/ref93 baseline sources in accurate modelling contexts.
- ref11 and ref48 predict binary horizon survival status; they should not be relabelled full survival-curve benchmarks.
- ref62 explains relative mortality-risk rankings and does not demonstrate RSF superiority over Cox in its data.
- ref66 supports the practical separation of discrimination, prediction error and calibration.
- Correct originally mismatched methods citations by relocating the scholarly source, not deleting it by default.

## Evidence coverage

Eleven removed-cited full articles are cached as publisher/JATS XML under paper_text, with SHA-256 identities in removed25_fulltext_access.json. PublisherHTML also exposes ref50 and part of ref94. Per-source levels distinguish sections actually examined from abstract-only evidence. No new PDF was downloaded or added to the central bank by this audit. The bank had no DOI/title-matched accepted mainPDF for any original95 at the initial check.

## Removed originally cited sources

### ref8: Data mining and machine learning in cancer survival research: An overview and future recommendations

DOI: 10.1016/j.jbi.2022.104026
Evidence examined: author_abstract. Anchor: Abstract.

The original generic prior/regularisation claims require a Bayesian methodological source. Preserve this review in the clinical landscape.

Reviews of cancer survival prediction describe a widening range of clinical data sources and statistical, machine-learning and deep-learning approaches. \cite{ref8}

### ref9: Machine learning and deep learning to improve overall survival prediction in cervical cancer patients

DOI: 10.21037/tcr-2024-2304
Evidence examined: fulltext_methods_and_results. Anchor: Methods: Patients and data collection; Constructing survival prognostic models; Key features extraction of the optimal model; Results: Construction of survival prediction models.

The source is a cervical-cancer application, not evidence for the exact cohorts or model settings used in this thesis.

Cervical-cancer studies have compared conventional learning algorithms with DeepSurv and used SHAP to examine the fitted predictions. \cite{ref9}

### ref10: Artificial neural networks for diagnosis and survival prediction in colon cancer

DOI: 10.1186/1476-4598-4-29
Evidence examined: publisher_fulltext_abstract_and_introduction. Anchor: Abstract; Section1 Introduction and Development of Artificial Neural Networks.

Use as historical clinical context; it cannot establish which cohorts, Bayesian priors or contemporary models this thesis implemented.

Early colon-cancer work explored artificial neural networks as nonlinear tools for diagnosis and survival prediction. \cite{ref10}

### ref11: Predicting the survival of patients with cancer from their initial oncology consultation document using natural language processing

DOI: 10.1001/jamanetworkopen.2023.0813
Evidence examined: fulltext_scientific_body. Anchor: Methods: Data Selection and Preparation; Natural Language Models; Statistical Analysis; Discussion; Conclusions.

The original general metrics/posterior-inference placement is mismatched. The paper uses binary6/36/60month labels, text inputs, integrated gradients and coefficient explanations, not our full likelihood or SHAP target.

Prognosis has also been estimated from initial oncology-consultation text through classification of survival at selected horizons, rather than estimation of a complete survival curve. \cite{ref11}

### ref12: Survival modelling using machine learning and Immune--Nutritional profiles in advanced gastric cancer on home parenteral nutrition

DOI: 10.3390/nu17152414
Evidence examined: fulltext_methods_results_discussion. Anchor: Sections2.1,2.3,2.4;3.5;4Discussion.

Valid clinical application. It does not substantiate this thesis diagnostic exclusions or confirmatory registry boundaries. Do not transplant its unusually high C-index into a common-model ranking.

In advanced gastric cancer receiving home parenteral nutrition, Cox analysis has been used to identify immune-nutritional predictors before fitting a random survival forest. \cite{ref12}

### ref29: SHAP-integrated machine learning framework for interpretable survival modeling in a synthetic COVID-19 cohort

DOI: 10.1016/j.insi.2025.100136
Evidence examined: publisher_supplied_abstract_in_DOAJ_only. Anchor: DOAJ indexed author abstract; publisher fulltext route403.

Explicitly synthetic, so it is not real-patient clinical validation. Original metrics-review and general Cox-versus-RSF simulation claims require other methodological sources. Detailed results were not verified from the full paper.

SHAP has also been paired with survival modelling in synthetic COVID-19 data. \cite{ref29}

### ref35: Reporting of prognostic clinical prediction models based on machine learning methods in oncology needs to be improved

DOI: 10.1016/j.jclinepi.2021.06.024
Evidence examined: fulltext_discussion_and_author_abstract. Anchor: Discussion: Summary of findings; Literature; Future research; Conclusions; author Abstract.

Preserve for reporting rationale. It does not derive a piecewise baseline, censoring likelihood, MCMC ESS or sampler convergence rule.

Reporting reviews emphasise that prediction studies should make their model specification, preprocessing, validation and performance assessment explicit. \cite{ref35}

### ref36: Comparison of time-to-event machine learning models in predicting oral cavity cancer prognosis

DOI: 10.1016/j.ijmedinf.2021.104635
Evidence examined: author_abstract. Anchor: Abstract: Materials and methods; Results.

A relevant clinical comparison, with different models favoured by discrimination and overall prediction-error measures. It is not an HMC or rank-normalised convergence-diagnostic source.

An oral-cavity study compared DeepSurv, DeepHit, Cox-Time and random survival forests using both concordance and integrated Brier scores. \cite{ref36}

### ref41: Machine learning-based prediction of 1-year mortality for acute coronary syndrome\ensuremath{\star}

DOI: 10.1016/j.jjcc.2021.11.006
Evidence examined: author_abstract. Anchor: Abstract: Methods; Results.

Restore cardiovascular/external-validation context. Original prior-predictive and posterior-diagnostic uses, or proof that our SHAP results were unavailable, are mismatched.

Acute-coronary-syndrome survival comparisons have assessed Cox, DeepSurv and random survival forests in an external cohort as well as an internal split. \cite{ref41}

### ref46: Survival prediction models: an introduction to discrete-time modeling

DOI: 10.1186/s12874-022-01679-6
Evidence examined: fulltext_methods_and_discussion. Anchor: Methods: Discrete-time survival models; Alternative approaches; Building discrete-time survival prediction models; Discussion.

Restore the alternative time-formulation discussion. The article also explicitly contrasts this binomial formulation with a Poisson piecewise-exponential model using interval exposure. It is not primary evidence on Bayesian prior sensitivity.

Discrete-time survival models express interval hazards as conditional probabilities in person-period data, allowing binary learning algorithms to produce survival predictions. \cite{ref46}

### ref48: A multimodal affinity fusion network for predicting the survival of breast cancer patients

DOI: 10.3389/fgene.2021.709027
Evidence examined: fulltext_methods_results_discussion. Anchor: Section2.1Materials;2.3Methods;2.4Optimization;3.4Comparison With Other Methods.

The supervised target is binary five-year status with cross-entropy. It does not supply full censoring-aware survival curves, SHAP methodology or Kaplan-Meier foundations.

Multimodal affinity-fusion networks have combined gene expression, copy-number alteration and clinical data to classify five-year breast-cancer survival. \cite{ref48}

### ref49: Scaling survival analysis in healthcare with federated survival forests: A comparative study on heart failure and breast cancer genomics

DOI: 10.1016/j.future.2023.07.036
Evidence examined: institutional_author_abstract. Anchor: Politecnico institutional repository abstract; accepted-manuscript PDF route403 in browser.

Restore federated-learning context; not a foundation for Kaplan-Meier curves or this study specific METABRIC feature table. Abstract confirms heterogeneous federations and FedSurF++.

Federated survival forests address a different setting in which patient data remain distributed across institutions. \cite{ref49}

### ref50: Survival Analysis as Imprecise Classification with Trainable Kernels

DOI: 10.3390/math13183040
Evidence examined: publisher_fulltext_abstract_introduction_and_method_formulation. Anchor: Abstract; Sections1Introduction,3Preliminaries,4Survival Analysis as an Imprecise Multi-Label Classification Problem.

This is a distinct censoring/kernel model, not a Kaplan-Meier or causal-effect source. No general superiority claim is needed for restoration.

Imprecise survival approaches represent censored observations through interval-valued event-time probabilities and combine them using trainable kernel weights. \cite{ref50}

### ref52: BHCox: Bayesian heredity-constrained Cox proportional hazards models for detecting gene-environment interactions

DOI: 10.1186/s12859-025-06077-5
Evidence examined: fulltext_methods_simulations_realdata_discussion. Anchor: Methods: Heredity-constrained Cox proportional hazard model; Prior distribution; MCMC sampling; Simulation study; Real data analysis; Discussion.

Essential close related work, not a disposable application citation. Distinguish its heredity-constrained high-dimensional interaction target and M-spline baseline from the common piecewise-exponential main-effects comparison here. Do not claim the thesis first compares these prior families.

BHCox incorporates effect heredity into Bayesian proportional-hazards models with spike-and-slab and regularised horseshoe priors, using an M-spline baseline for gene-environment interaction analysis. \cite{ref52}

### ref58: Bayesian inference using Hamiltonian Monte\textendash{}Carlo algorithm for nonlinear joint modeling in the context of cancer immunotherapy

DOI: 10.1002/sim.8756
Evidence examined: author_abstract. Anchor: Abstract.

Preserve Bayesian computation/joint-model context. It is not an empirical Cox-versus-RSF benchmark or a universal performance-ranking source.

Hamiltonian Monte Carlo has also been used for Bayesian nonlinear joint models that connect tumour dynamics with survival during cancer immunotherapy. \cite{ref58}

### ref62: Explainable machine learning can outperform Cox regression predictions and provide insights in breast cancer survival

DOI: 10.1038/s41598-021-86327-7
Evidence examined: fulltext_methods_results_discussion. Anchor: Methods: Models; Evaluation; Results; Discussion; Outlook and conclusion.

Original RSF-improvement claim is inaccurate for this paper: Cox,RSF,SVM were similar and XGBoost had higher concordance. Its SHAP output is log relative mortality risk, distinct from fixed-horizon survival probability.

In breast-cancer risk-ranking comparisons, SHAP has been used to explain the relative-risk predictions of Cox and gradient-boosting models. \cite{ref62}

### ref66: Machine Learning Support for Decision-Making in Kidney Transplantation: Step-by-step development of a technological solution

DOI: 10.2196/34554
Evidence examined: fulltext_results_and_discussion. Anchor: Results: Model Performance; Discussion: Evaluation of ML Models; Conclusions.

This is a direct multi-metric comparison: different models lead concordance,IBS and ICI. Preserve as a use-case-specific comparison rather than asserting an ordering across all datasets.

Kidney-graft comparisons show that the model with stronger discrimination need not give the best-calibrated survival probabilities. \cite{ref66}

### ref68: BHAFT\,: Bayesian heredity\textendash{}constrained accelerated failure time models for detecting gene\textendash{}environment interactions in survival analysis

DOI: 10.1002/sim.10145
Evidence examined: publisher_and_indexed_author_abstract. Anchor: Abstract.

Genuinely relevant prior literature. Explicitly distinguish AFT from proportional hazards; no detailed performance generalisation beyond the tested interaction setting.

Related heredity-constrained accelerated-failure-time models use spike-and-slab or regularised horseshoe priors to study gene-environment interactions. \cite{ref68}

### ref77: Deep learning-based survival prediction of oral cancer patients

DOI: 10.1038/s41598-019-43372-7
Evidence examined: fulltext_results_discussion_and_modelling_methods. Anchor: Results: Comparing the performance of deep-learning based survival prediction with RSF and CPH; Discussion; Methods: Modelling process.

Preserve the disease-specific comparative result. Do not generalise one study to universal rankings, or describe it as colon-cancer evidence.

Oral-cancer studies have compared DeepSurv with Cox regression and random survival forests under a shared clinical prediction task. \cite{ref77}

### ref79: Comparison of nomogram with random survival forest for prediction of survival in patients with spindle cell carcinoma

DOI: 10.4103/jcrt.jcrt_2375_21
Evidence examined: author_abstract. Anchor: Abstract: Methods; Results; Conclusions.

Useful applied counterpoint to assuming more flexible models always dominate. It is not a general calibration-estimator reference.

A spindle-cell-carcinoma study compared a Cox-based nomogram with a random survival forest and found comparable predictive performance. \cite{ref79}

### ref88: The preoperative machine learning algorithm for extremity metastatic disease can predict 90\textendash{}day and 1\textendash{}year survival: An external validation study

DOI: 10.1002/jso.26708
Evidence examined: author_abstract. Anchor: Abstract: Methods; Results.

Restore external-validation and clinical evaluation context. It cannot substantiate the thesis number of accepted Bayesian fits or its HMC diagnostic ledger.

External validation of a metastatic long-bone survival algorithm assessed discrimination, calibration, overall prediction performance and clinical net benefit. \cite{ref88}

### ref91: A novel Bayesian continuous piecewise linear log\textendash{}hazard model, with estimation and inference via reversible jump Markov chain Monte Carlo

DOI: 10.1002/sim.8511
Evidence examined: author_abstract_and_institutional_record. Anchor: Abstract.

Preserve baseline flexibility and computation contrast. It is not a principled-Bayesian-workflow reference or a Cox-versus-RSF comparison.

Bayesian reversible-jump methods have extended piecewise-exponential survival models to continuous piecewise-linear log hazards. \cite{ref91}

### ref93: Extending beyond Bagust and Beale: Fully parametric piecewise exponential models for extrapolation of survival outcomes in health technology assessment

DOI: 10.1016/j.jval.2023.06.007
Evidence examined: author_abstract. Anchor: Abstract: Objectives; Methods; Conclusions.

This paper concerns change-point estimation and health-technology-assessment extrapolation, not horseshoe shrinkage. Appropriate baseline/tail context, with extrapolation distinguished from within-follow-up prediction.

Piecewise-exponential models have also been used for long-term survival extrapolation, where the final hazard segment determines the tail assumption. \cite{ref93}

### ref94: Bayesian Inference for High Dimensional Cox Models with Gaussian and Diffused-Gamma Priors: A Case Study of Mortality in COVID-19 Patients Admitted to the ICU

DOI: 10.1007/s12561-023-09395-5
Evidence examined: full_supplied_article_text_read_via_Consensus. Anchor: Author manuscript Sections1Introduction,2Formulation of the Problem,3GD Prior Adapted to Cox Models; publisher Abstract.

Relevant close prior study. Its rank/partial-likelihood procedure avoids specifying a baseline prior, unlike the common full likelihood used here. Complete supplied primary text was read through Consensus; no equation symbols missing from the export were reconstructed.

Song and colleagues use Gaussian and diffused-gamma priors for high-dimensional Cox inference based on the partial likelihood. \cite{ref94}

### ref95: Bayesian variable selection for the Cox regression model with spatially varying coefficients with applications to Louisiana respiratory cancer data

DOI: 10.1002/bimj.202000047
Evidence examined: author_abstract. Anchor: Abstract.

Restore structured Bayesian prior context. This is Louisiana respiratory-cancer spatial modelling, not the original conclusion claim about deep learning versus Cox in colon cancer; two-stage sitewise partial-likelihood/MCMC differs from our joint full-likelihood model.

Spatial Cox variable-selection models have combined horseshoe sparsity with a point-mass mixture to distinguish constant and spatially varying covariate effects. \cite{ref95}


## Song full-text follow-up

Complete supplied primary text was read through Consensus; a Song-only copy is paper_text/ref94_Consensus_fulltext.txt. Sections 1 and 2.2 explicitly remove the baseline hazard by using rank-based/Cox partial likelihood under independent censoring. This differs from jointly estimating interval baseline rates and coefficients in the thesis full piecewise-exponential likelihood. Sections 3–4 describe Gaussian/gamma,MAP/ICM and Metropolis-Hastings inference, not HMC. Numerical source-export maths gaps were not reconstructed.
