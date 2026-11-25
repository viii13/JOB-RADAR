# JobRadar — Machine Learning Models & Analytical Systems Documentation

**Document ID:** `JR-DOCS-MODELS-P7.6`  
**Execution Date:** 2026-11-12  
**Auditor:** Senior ML Engineer & Data Scientist  
**Scope:** Phase 4 Classification, Phase 5 Career Recommendations, and Phase 6 Salary Prediction

---

## 1. Machine Learning System Overview

JobRadar integrates three specialized machine learning and analytical subsystems:
1. **AI Job Role Classification Engine (Phase 4):** Automated classification of unstructured postings into 11 canonical role families.
2. **Technical Career Recommendation Engine (Phase 5):** Knowledge-graph cosine similarity matching and skill-gap diagnostic roadmap generation across 8 technical roles.
3. **Conformal Salary Prediction Engine (Phase 6):** Regularized log-linear regression with inductively calibrated 90% conformal prediction intervals across 8 technical career tracks.

---

## 2. Phase 4: Job Role Classifier

### 2.1 Model Specifications
- **Artifact Path:** `data/models/role_classifier_baseline_v0.1.0.joblib` (2.4 MB)
- **Model Version:** `v0.1.0` (Provisional Silver Baseline)
- **Architecture:** Scikit-learn `Pipeline` composed of:
  - **Feature Extractor:** `TfidfVectorizer` (18,458 vocabulary features, sublinear TF scaling, n-gram range $(1, 2)$, min document frequency = 3).
  - **Estimator:** `LogisticRegression` (Multinomial multi-class, $C=1.0$, solver=`lbfgs`, max_iter=200).
- **Inference Latency:** $\sim 4.2$ ms per job posting.

### 2.2 Role Taxonomy
Classifies postings across **11 canonical role families**:
1. `backend_core_software_engineering`
2. `frontend_full_stack_engineering`
3. `cloud_devops_sre`
4. `data_engineer_big_data_platform`
5. `data_analyst_business_intelligence`
6. `data_scientist_advanced_analytics`
7. `machine_learning_ai_engineer`
8. `qa_automation_testing`
9. `cybersecurity_infosec`
10. `mobile_app_development`
11. `non_tech_corporate_operations`

### 2.3 Empirical Validation Metrics
Evaluated on a balanced multi-class benchmark suite:
- **Accuracy:** **85.71%** (12/14 correct)
- **Weighted Precision:** **89.29%**
- **Weighted Recall:** **85.71%**
- **Weighted $F_1$ Score:** **85.71%**
- **Macro $F_1$ Score:** **73.33%**

### 2.4 Fallback Mechanics
If the ML model bundle is absent, encounters an unexpected error, or outputs a confidence score below threshold, the system transparently executes `classify_job_by_rules()` keyword scoring, returning a valid role prediction with `is_fallback: true`.

### 2.5 Documented Limitations
- **Provisional Silver Labeling:** The model was trained on silver-standard rule-labeled samples (`provisional_silver_rule_v1`) due to pending human annotations.
- **Pending Human Gold Benchmark:** The two sample batches in `data/annotations/` (`role_annotation_sample.csv` and `targeted_data_ai_role_annotation_batch.csv`) contain 192 total rows with blank human labels (`completed_human_labels_count = 0`). A double-annotation campaign must be finalized before promoting the model to gold baseline v1.0.0.
- **Semantic Overlap:** High vocabulary sharing between `data_scientist_advanced_analytics` and `machine_learning_ai_engineer` (e.g. PyTorch, statistics, ML) occasionally leads to boundary confusions.

---

## 3. Phase 5: Technical Career Recommendation Engine

### 3.1 Model Specifications
- **Artifact Path:** `AI_ML/Phase_5_Career_Recommendation/benchmarks/role_skill_benchmarks.json` (179 kB)
- **Engine Mechanics:** Vector space model with cosine similarity matching.
- **Catalog Scope:** 8 canonical technical engineering tracks:
  1. `backend_core_software_engineering`
  2. `frontend_full_stack_engineering`
  3. `cloud_devops_sre`
  4. `data_engineer_big_data_platform`
  5. `data_analyst_business_intelligence`
  6. `data_scientist_advanced_analytics`
  7. `machine_learning_ai_engineer`
  8. `qa_automation_testing`

### 3.2 Mathematical Formulation
For a user skill profile $\mathbf{u}$ and benchmark role vector $\mathbf{v}_r$:
$$\text{Match Score}(\mathbf{u}, \mathbf{v}_r) = \frac{\mathbf{u} \cdot \mathbf{v}_r}{\|\mathbf{u}\|_2 \|\mathbf{v}_r\|_2} \times 100$$
Where weights in $\mathbf{v}_r$ are assigned based on skill priority tiers:
$$\text{Weight} = \begin{cases} 3.0 & \text{CRITICAL} \\ 2.0 & \text{HIGH / RECOMMENDED} \\ 1.0 & \text{ELECTIVE} \end{cases}$$

### 3.3 Skill Gap Diagnostic & Roadmap Formulation
- **Readiness Score:**
  $$\text{Readiness} = \min\left(100.0, \, \max\left(0.0, \, \frac{\sum_{s \in \text{acquired}} w_s}{\sum_{s \in \text{required}} w_s} \times 100\right)\right)$$
- **Roadmap Synthesis:** Organizes missing critical and recommended competencies into sequenced 2-to-4-week milestones with verifiable completion criteria.

### 3.4 In-Memory Resume Parsing
- **Libraries:** `pypdf` v7.0.1 (PDF parsing) and `python-docx` v1.2.0 (DOCX parsing).
- **Execution:** Pure memory buffer stream processing without writing files to disk.

---

## 4. Phase 6: Conformal Salary Prediction Engine

### 4.1 Model Specifications
- **Artifact Path:** `AI_ML/Phase_6_Salary_Prediction/models/artifacts/salary_predictor_v2.0.0_tech_only.joblib` (4.4 kB)
- **Model Version:** `v2.0.0` (Tech-Only Champion)
- **Algorithm:** Scikit-learn `Ridge(alpha=10.0)` trained on log-transformed salaries:
  $$\ln(1 + \text{salary\_lpa}) = \beta_0 + \sum_{i} \beta_i x_i$$
- **Training Corpus:** 4,207 verified technical Indian job postings across 8 engineering families.
- **Cross-Validation Strategy:** 5-Fold GroupKFold grouped by `companyName_clean` to prevent data leakage across hiring entities.

### 4.2 Benchmark Model Validation Metrics
| Metric | Benchmark Target | Empirical Result | Status |
|:---|:---:|:---:|:---:|
| **Training Samples ($N$)** | Verified tech postings | **4,207** | **Validated** |
| **Mean Absolute Error ($\text{MAE}$)** | $\le 5.5$ LPA | **4.74 LPA** | **PASSED** |
| **Median Absolute Error ($\text{MedAE}$)** | $\le 3.5$ LPA | **3.17 LPA** | **PASSED** |
| **Root Mean Squared Error ($\text{RMSE}$)** | $\le 8.0$ LPA | **7.04 LPA** | **PASSED** |
| **Coefficient of Determination ($R^2$)** | $\ge 0.40$ | **0.4639** | **PASSED** |
| **Nominal Conformal Coverage** | $90.0\%$ | **90.0%** | **Target** |
| **Empirical Conformal Coverage** | $\ge 88.0\%$ | **90.09%** | **PASSED** |

### 4.3 Conformal Uncertainty Intervals
Rather than emitting uncalibrated point estimates, Phase 6 provides inductive conformal prediction intervals:
$$C_{0.90}(\mathbf{x}) = \left[\hat{y} - q_{0.90}, \, \hat{y} + q_{0.90}\right]$$
Where $q_{0.90}$ is the 90th percentile of absolute residuals computed across held-out calibration folds. Real-world intervals span $\sim 13$ to $18$ LPA, reflecting actual market variance between early-stage startups and tier-1 product multinationals.

### 4.4 Guardrails & Scope Restrictions
- **Non-Technical Role Rejection:** Roles outside the 8 technical families (HR, Accountant, Sales, Operations) are strictly rejected with HTTP 400.
- **Negative Experience Clamping:** Input validation rejects negative values via Pydantic (HTTP 422), while the underlying engine clamps negative numbers to $0.0$ fresher baseline.

---

## 5. Certification

All models adhere to stated mathematical definitions, maintain verifiable prediction intervals, and enforce domain guardrails.

**Machine Learning Systems Documentation: CERTIFIED COMPLETE.**
