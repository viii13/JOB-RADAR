# Phase 6: Technical Salary Modeling Methodology & Architecture (v2.0.0)

## 1. Problem Formulation & Scope

Under **Option A: Core Technical Careers Only**, JobRadar's Salary Prediction Engine models market compensation exclusively for technical engineering and data roles in the Indian employment ecosystem:

$$\hat{y} = f(X)$$

Where $y$ is the annualized midpoint salary in LPA (Lakhs Per Annum INR) and $X$ represents observable job characteristics:
- Technical Career Role Track (7 primary modeling families consolidating 8 approved IC disciplines)
- Seniority Level (Intern, Junior, Mid, Senior, Lead, Principal/Architect, Executive)
- Years of Professional Experience (Linear & Quadratic Mincer terms, Experience tier brackets)
- Geographic Location Market Tier (Tier 1 Metro, Tier 2 City, Remote, Hybrid, Other)
- Technical Skill Competencies (36 high-demand technical indicators: Python, SQL, AWS, React, PyTorch, Docker, etc.)

---

## 2. Theoretical Grounding: The Mincer Earnings Function

In labor economics and human capital theory, Jacob Mincer's canonical earnings equation models the natural logarithm of compensation as a linear-quadratic function of experience:

$$\ln(Salary) = \beta_0 + \beta_1 \cdot \text{Experience} + \beta_2 \cdot \text{Experience}^2 + \sum_{k} \gamma_k \cdot \text{Skills}_k + \sum_{m} \delta_m \cdot \text{Location}_m + \epsilon$$

### Why Log-Target Transformation?
1. **Right-Skew Normalization**: Raw compensation in India exhibits severe positive skew (long right tail up to 90+ LPA). Log transformation produces near-normal residual errors.
2. **Homoscedastic Error**: Percentage error in salary estimation remains approximately constant across salary tiers.
3. **Guaranteed Positive Bounds**: Applying $\exp(\hat{y}) - 1$ mathematically guarantees non-negative predicted salary bounds.

---

## 3. Option A Technical Scope & Role Consolidation

### A. Identification via Phase 4 Classifier
Rather than relying on brittle title-only regex heuristics (which misclassify 82%+ of postings), JobRadar v2.0.0 uses the Phase 4 machine learning classifier bundle (`role_classifier_baseline_v0.1.0.joblib`) over boosted multi-field inputs:
- Cleaned Job Title (boosted $3\times$)
- Canonical Normalized Skills (boosted $2\times$)
- Source Tags & Attributes
- Cleaned Job Description (first 500 characters)

Postings with $\text{confidence} \ge 0.20$ matching the 8 approved technical career families are retained:
1. `backend_core_software_engineering` ($N = 1,440$)
2. `frontend_full_stack_engineering` ($N = 673$)
3. `qa_automation_testing` ($N = 618$)
4. `data_analyst_business_intelligence` ($N = 492$)
5. `cloud_devops_sre` ($N = 389$)
6. `data_engineer_big_data_platform` ($N = 386$)
7. `machine_learning_ai_engineer` ($N = 174$)
8. `data_scientist_advanced_analytics` ($N = 35$)

### B. Consolidation of Data Science & AI/ML
- **Data Science Alone:** $N = 35$ represents $< 1\%$ of the dataset, providing insufficient samples for independent cross-validated training without extreme variance.
- **Consolidation:** Combining `data_scientist_advanced_analytics` and `machine_learning_ai_engineer` into `data_science_ml_ai` yields $N = 209$ high-quality records.
- **Justification:** Both disciplines share identical foundational mathematical requirements (Python, SQL, Linear Algebra, Optimization, Machine Learning, Deep Learning) and aligned compensation curves (Median 19.50 LPA, Mean 20.50 LPA).

---

## 4. Employer Leakage Prevention Protocol (`GroupKFold`) & Entity Nuance

In the Indian tech market, recruitment agencies (e.g. *Purview India Consulting*, *Talent21*, *HR Innovation Group*) post dozens or hundreds of listings with identical boilerplate salary templates.

- **Vulnerability:** Standard random $K$-fold splits assign postings from the same agency across both train and test folds, causing data leakage and artificially optimistic test metrics.
- **Solution:** 5-Fold `GroupKFold` grouped strictly by `companyName_clean` across 1,764 unique employers.
- **Exact-Name Separation:** All listings with the exact same `companyName_clean` string appear exclusively in train or exclusively in test.
- **Entity Resolution Nuance:** While GroupKFold prevents exact company-name overlap, it does not fully solve parent-company or staffing-agency entity resolution. Unnormalized corporate suffixes (e.g. *Purview India Consulting And Services Llp* vs *Purview Services*) allow related entities of a single agency to appear across different validation folds.
- **Future Improvement:** Automated company-name canonicalization, legal suffix stripping, and parent-agency fuzzy clustering are recorded as future improvements, not as implemented features in v2.0.0.

---

## 5. Candidate Model Benchmarks & Comparison

Evaluated on the 4,207 technical listings under 5-fold GroupKFold:

| Candidate Model | Out-of-Group CV MAE (LPA) | Out-of-Group CV MedAE (LPA) | Out-of-Group CV RMSE (LPA) | Out-of-Group CV $R^2$ | CV MAPE (%) |
|---|---|---|---|---|---|
| **DummyRegressor (Median Baseline)** | 7.511 | 6.750 | 9.662 | -0.0112 | 117.04% |
| **Linear Regression (OLS on log scale)** | 4.769 | 3.214 | 7.101 | 0.4537 | 56.52% |
| **Ridge Regression ($\alpha = 1.0$)** | 4.763 | 3.204 | 7.086 | 0.4561 | 56.38% |
| **Ridge Regression ($\alpha = 10.0$) [CHAMPION]** | **4.740** | **3.174** | **7.035** | **0.4639** | **55.84%** |
| **Random Forest Regressor ($n=100$)** | 4.776 | 3.158 | 7.016 | 0.4668 | 54.42% |

### Why Ridge ($\alpha=10.0$) is the Champion:
- **Lowest Generalization Error:** Achieves the lowest out-of-company CV MAE (4.740 LPA).
- **Overfitting Resistance:** Regularization prevents over-indexing on rare recruiter tags across sparse employer groups.
- **Interpretability:** Permutation importance and linear coefficients provide transparent economic valuation drivers.

---

## 6. Calibrated Conformal Prediction Intervals

Rather than reporting an uncalibrated heuristic margin ($\pm \text{MAE}$), JobRadar v2.0.0 implements distribution-free **conformal prediction calibration** based on out-of-group absolute residuals:

$$R_i = |y_i - \hat{y}_i|$$

Empirically calibrated 90% conformal prediction interval based on out-of-fold employer-grouped residuals. Independent held-out cross-conformal evaluation showed mean overall coverage of approximately 90.09%. Individual role-fold coverage varied from 76.7% to 96.9%. These results are empirical and do not establish guaranteed coverage for every role or future employer.

Calibration-set quantiles represent empirical thresholds computed over cross-validation residual arrays, and must not be described as independent test coverage guarantees.

### Role-Stratified Calibration:
Because variance differs significantly between roles (e.g. QA testing has narrower salary dispersion than senior AI engineering), conformal intervals are stratified by role:
- **QA Automation Testing ($N=618$):** $\pm 7.79$ LPA (Calibration-set sample coverage: 89.97%; Held-out mean: 90.43%, range: 83.1% – 95.0%)
- **Data Analyst & BI ($N=492$):** $\pm 8.34$ LPA (Calibration-set sample coverage: 89.84%; Held-out mean: 89.99%, range: 84.2% – 94.9%)
- **Data Engineering ($N=386$):** $\pm 10.14$ LPA (Calibration-set sample coverage: 89.90%; Held-out mean: 88.47%, range: 76.7% – 95.4%)
- **Frontend / Full Stack ($N=673$):** $\pm 10.26$ LPA (Calibration-set sample coverage: 89.90%; Held-out mean: 90.05%, range: 87.1% – 93.5%)
- **Backend / Core Software ($N=1,440$):** $\pm 11.01$ LPA (Calibration-set sample coverage: 90.00%; Held-out mean: 89.99%, range: 88.0% – 92.9%)
- **Cloud / DevOps / SRE ($N=389$):** $\pm 12.04$ LPA (Calibration-set sample coverage: 89.97%; Held-out mean: 91.01%, range: 78.0% – 96.9%)
- **Data Science, ML & AI ($N=209$):** $\pm 18.34$ LPA (Calibration-set sample coverage: 89.95%; Held-out mean: 90.32%, range: 84.1% – 95.6%)

---

## 7. Operational Limitations

Downstream users and applications should note:
1. The dataset contains 4,207 classifier-assigned technical job postings, not manually verified labels for every posting.
2. Company-name normalization is imperfect. Variations in employer names can allow related entities to appear across different validation folds.
3. Salary predictions have substantial error and should be treated as estimates, not exact compensation offers.
4. Data Science / ML / AI has fewer observations than larger career families.
5. Salary disclosure and dataset composition may introduce selection bias.
6. Results may not generalize to every employer, location, experience level, or future market condition.
