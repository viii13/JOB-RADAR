# Model Card: JobRadar Salary Prediction Engine v2.0.0 (Technical-Only)

## Model Details
- **Developer**: JobRadar Data Science & Engineering Team
- **Model Version**: 2.0.0 (`salary_predictor_v2.0.0_tech_only.joblib`)
- **Scope**: Option A — Core Technical Careers Only (8 approved Phase 4 engineering & data families)
- **Champion Architecture**: Ridge Regression ($\alpha = 10.0$) wrapped in `TransformedTargetRegressor` fitting on $\ln(1 + \text{salary\_lpa})$ and predicting via $\exp(\hat{y}) - 1$.
- **Validation Methodology**: 5-Fold `GroupKFold` grouped by employer (`companyName_clean`) across 1,764 unique hiring organizations.
- **Uncertainty Quantification**: Calibrated Group-Aware Conformal Prediction Intervals (90% nominal coverage).
- **Release Date**: November 2026
- **License**: Proprietary / Educational

---

## Intended Use
- **Primary Use Case**: Predict market compensation brackets (in LPA and annual INR) for technical job listings and candidate profiles across 8 approved technical career families:
  1. Backend / Core Software Engineering
  2. Frontend / Full Stack Engineering
  3. QA Automation & Quality Engineering
  4. Cloud, DevOps & SRE
  5. Data Engineering & Big Data
  6. Data Analyst & Business Intelligence
  7. Data Science & Advanced Analytics (consolidated with AI/ML)
  8. Machine Learning & AI Engineering (consolidated with Data Science)
- **Out-of-Scope / Prohibited Use Cases**: Non-technical roles (HR, sales, operations, finance) are explicitly rejected by the prediction engine. Not intended for legally binding contractual offers or executive equity negotiation.

---

## Training Data & Provenance
- **Source Dataset**: `cleaned_indian_job_market_2025.csv` (domestic Indian job postings)
- **Skills Source**: `job_skills.csv` (canonical normalized technical skills)
- **Role Classifier**: Phase 4 TF-IDF + Logistic Regression Bundle (`role_classifier_baseline_v0.1.0.joblib`)
- **Confidence Threshold**: $\text{confidence} \ge 0.20$
- **Curated Technical Cohort**: **4,207 verified technical listings**
- **Unique Employers**: **1,764 companies**
- **Target Variable**: Disclosed annual midpoint salary in Lakhs Per Annum (LPA)

### Verified Technical Role Distribution (4,207 Records):

| Technical Career Family | Records | Share |
|---|---:|---:|
| Backend / Core Software Engineering | 1,440 | 34.2% |
| Frontend / Full-stack Engineering | 673 | 16.0% |
| QA Automation / Testing | 618 | 14.7% |
| Data Analyst / Business Intelligence | 492 | 11.7% |
| Cloud / DevOps / SRE | 389 | 9.2% |
| Data Engineering / Big Data | 386 | 9.2% |
| Machine Learning / AI Engineering | 174 | 4.1% |
| Data Science / Advanced Analytics | 35 | 0.8% |
| **Total** | **4,207** | **100%** |

---

## 5-Fold GroupKFold Cross-Validation Comparison

All candidate estimators were evaluated on the identical 4,207 technical listings under employer-grouped validation:

| Candidate Model | 5-Fold Group CV MAE (LPA) | 5-Fold Group CV MedAE (LPA) | 5-Fold Group CV RMSE (LPA) | 5-Fold Group CV $R^2$ | CV MAPE (%) |
|---|---|---|---|---|---|
| **DummyRegressor (Median Baseline)** | 7.511 | 6.750 | 9.662 | -0.0112 | 117.04% |
| **Linear Regression (OLS)** | 4.769 | 3.214 | 7.101 | 0.4537 | 56.52% |
| **Ridge Regression ($\alpha = 1.0$)** | 4.763 | 3.204 | 7.086 | 0.4561 | 56.38% |
| **Ridge Regression ($\alpha = 10.0$) [CHAMPION]** | **4.740** | **3.174** | **7.035** | **0.4639** | **55.84%** |
| **Random Forest Regressor ($n=100$)** | 4.776 | 3.158 | 7.016 | 0.4668 | 54.42% |

*Champion Selection Justification:* Ridge Regression with $\alpha=10.0$ achieved the lowest out-of-company generalization error (MAE 4.740 LPA) with consistent stability across sparse employer profiles, avoiding tree-depth overfitting on recruiter boilerplate.

---

## Role-Stratified Evaluation Benchmarks

Evaluated on out-of-group predictions across 1,764 employer clusters:

### Consolidated Modeling Families:
| Role Model Family | Sample Count ($N$) | Mean Actual (LPA) | Median Actual (LPA) | CV MAE (LPA) | CV RMSE (LPA) | CV $R^2$ Score |
|---|---|---|---|---|---|---|
| `backend_core_software_engineering` | 1,440 | 14.93 | 14.00 | 4.990 | 7.325 | 0.4010 |
| `frontend_full_stack_engineering` | 673 | 15.18 | 15.00 | 5.135 | 7.353 | 0.3850 |
| `qa_automation_testing` | 618 | 9.17 | 6.50 | 3.438 | 5.426 | 0.4528 |
| `data_analyst_business_intelligence` | 492 | 9.68 | 6.50 | 3.376 | 5.157 | 0.5777 |
| `cloud_devops_sre` | 389 | 18.84 | 18.00 | 4.928 | 7.061 | 0.3642 |
| `data_engineer_big_data_platform` | 386 | 18.99 | 20.00 | 5.146 | 7.235 | 0.1621 |
| `data_science_ml_ai` | 209 | 20.50 | 19.50 | 7.709 | 10.647 | 0.2383 |

### Original 8-Role Breakdown (Data Science vs ML Engineer):
| Original Role Family | Sample Count ($N$) | Mean Actual (LPA) | Median Actual (LPA) | CV MAE (LPA) | CV RMSE (LPA) | CV $R^2$ Score |
|---|---|---|---|---|---|---|
| `machine_learning_ai_engineer` | 174 | 20.84 | 20.00 | 8.015 | 10.856 | 0.2275 |
| `data_scientist_advanced_analytics` | 35 | 18.79 | 15.75 | 6.188 | 9.540 | 0.2368 |

*Role-Specific Sample Size Limitation:* `data_scientist_advanced_analytics` has only 35 observations in the entire Indian job dataset, representing < 1% of the cohort. While the model predicts Data Science accurately via the consolidated `data_science_ml_ai` family, standalone role claims for Data Science must acknowledge high sampling variance.

---

## Calibrated Conformal Prediction Intervals (Group-Aware)

Empirically calibrated 90% conformal prediction interval based on out-of-fold employer-grouped residuals. Independent held-out cross-conformal evaluation showed mean overall coverage of approximately 90.09%. Individual role-fold coverage varied from 76.7% to 96.9%. These results are empirical and do not establish guaranteed coverage for every role or future employer.

Calibration-set quantiles represent empirical thresholds computed over cross-validation residual arrays, and must not be described as independent test coverage guarantees.

- **Global 90% Conformal Quantile:** $\pm 10.60$ LPA (Calibration-Set In-Sample Quantile: 89.99%)
- **Global 80% Conformal Quantile:** $\pm 7.41$ LPA (Calibration-Set In-Sample Quantile: 79.99%)
- **Independent Held-Out 5-Fold Evaluation:** Mean Global Out-of-Sample Coverage: **90.09%** (Fold range: 87.41% to 91.91%)

### Role-Stratified 90% Calibrated Conformal Intervals:
| Role Family | Sample Count ($N$) | Calibrated 90% Conformal Margin ($q_{90}$) | Calibration Set Sample Coverage | Held-Out Fold Coverage Mean (Range) |
|---|---|---|---|---|
| `qa_automation_testing` | 618 | **$\pm 7.79$ LPA** | 89.97% | 90.43% (83.1% – 95.0%) |
| `data_analyst_business_intelligence` | 492 | **$\pm 8.34$ LPA** | 89.84% | 89.99% (84.2% – 94.9%) |
| `data_engineer_big_data_platform` | 386 | **$\pm 10.14$ LPA** | 89.90% | 88.47% (76.7% – 95.4%) |
| `frontend_full_stack_engineering` | 673 | **$\pm 10.26$ LPA** | 89.90% | 90.05% (87.1% – 93.5%) |
| `backend_core_software_engineering` | 1,440 | **$\pm 11.01$ LPA** | 90.00% | 89.99% (88.0% – 92.9%) |
| `cloud_devops_sre` | 389 | **$\pm 12.04$ LPA** | 89.97% | 91.01% (78.0% – 96.9%) |
| `data_science_ml_ai` | 209 | **$\pm 18.34$ LPA** | 89.95% | 90.32% (84.1% – 95.6%) |

---

## Validation Strategy & Employer Grouping Nuance

- **GroupKFold Separation:** 5-Fold `GroupKFold` on `companyName_clean` guarantees that no exact company-name string appears in both training and validation folds within any fold.
- **Entity Resolution Limitation:** While `GroupKFold` prevents exact literal company-name overlap, it does not fully solve parent-company or staffing-agency entity resolution. Differences in corporate suffixes (e.g. *Purview India Consulting And Services Llp* vs *Purview Services*) can allow related entities of the same parent agency to be partitioned across different validation folds.
- **Planned Future Work:** Automated company-name canonicalization, legal suffix stripping, and parent-agency fuzzy clustering are recorded as future improvements, not as implemented features in v2.0.0.

---

## Model Limitations & Operational Governance

Users and downstream systems must account for the following explicit limitations:

1. **Classifier-Assigned Role Labels:** The dataset contains 4,207 classifier-assigned technical job postings (via the Phase 4 model at $\text{confidence} \ge 0.20$), not manually verified labels for every posting. Edge-case misclassifications may exist.
2. **Imperfect Company-Name Normalization:** Company-name normalization is imperfect. Variations in employer names can allow related entities to appear across different validation folds.
3. **Substantial Prediction Error:** Salary predictions have substantial error (Overall CV MAE: 4.740 LPA; Role MAE up to 8.015 LPA for AI/ML) and should be treated as estimates, not exact compensation offers.
4. **Sample Size Disparity:** Data Science / ML / AI has fewer observations ($N=35$ for Data Science, $N=174$ for ML Engineer) than larger career families (e.g. Backend with $N=1,440$). Estimates for smaller disciplines carry higher variance.
5. **Selection & Disclosure Bias:** Salary disclosure and dataset composition may introduce selection bias. Organizations that publicly disclose salary bands on hiring platforms may differ systematically from those that negotiate privately.
6. **Generalization Scope:** Results may not generalize to every employer, location, experience level, or future market condition. Macroeconomic hiring shifts and inflation post-2025 are outside model horizon.

---

## Permutation Feature Importance

Permutation importance computed over 5 repeats on the full technical cohort (MAE penalty when feature values are permuted):

1. `exp_mid_years_scaled` (+8.1369 LPA)
2. `exp_mid_years_sq_scaled` (+2.9730 LPA)
3. `role_model_qa_automation_testing` (+0.3258 LPA)
4. `loc_hybrid` (+0.1531 LPA)
5. `role_model_data_science_ml_ai` (+0.0723 LPA)
6. `skill_excel` (+0.0688 LPA)
7. `exp_5-8_years` (+0.0604 LPA)
8. `skill_spark` (+0.0448 LPA)
9. `skill_python` (+0.0444 LPA)
10. `skill_automation_testing` (+0.0427 LPA)
11. `sen_mid` (+0.0418 LPA)
12. `loc_tier_3_other` (+0.0365 LPA)
13. `skill_aws` (+0.0341 LPA)
14. `sen_senior` (+0.0339 LPA)
15. `skill_git` (+0.0330 LPA)

---

## Rollback & Backward Compatibility
- **Model Version 1.0.0 Artifacts Intact:** `salary_predictor_v1.0.0.joblib` and `salary_model_metadata.json` remain preserved in `models/artifacts/`.
- **API Version Negotiation:** The API and service layer default to v2.0.0, with optional parameter `model_version="1.0.0"` available for backward compatibility.
