# Phase 6: Salary Estimation & Compensation Analytics

## 1. Overview & Purpose
Phase 6 implements a robust, reproducible, and explainable **Salary Prediction Engine** for the Indian technical job market. Grounded in labor economics and empirical compensation data, the engine estimates expected market compensation (in LPA and annual INR) with statistically defensible confidence bands for students and developers based on role, experience, location, and technical skill sets.

---

## 2. Directory Architecture & Modules

```text
Phase_6_Salary_Prediction/
├── data/
│   └── curator.py           # Dataset audit, cleaning, outlier handling & deduplication
├── features/
│   ├── transformers.py      # Mincer experience, LocationTier, Seniority, SkillIndicators
│   └── pipeline.py          # Unified scikit-learn feature union preprocessor
├── models/
│   ├── trainer.py           # Multi-model training, 5-fold CV, tuning & persistence
│   └── artifacts/
│       ├── salary_predictor_v2.0.0_tech_only.joblib # Production champion Ridge pipeline (v2.0.0)
│       ├── salary_model_metadata_v2.json           # v2.0.0 metrics, conformal calibration & metadata
│       ├── model_comparison_v2.json                # v2.0.0 GroupKFold comparison summary
│       ├── salary_predictor_v1.0.0.joblib          # Persisted legacy Random Forest pipeline
│       └── salary_model_metadata.json              # Legacy v1.0.0 metadata
├── evaluation/
│   └── metrics.py           # MAE, MedAE, RMSE, R², MAPE & stratified evaluators
├── visualizers/
│   ├── eda_plots.py         # Visual generation suite (matplotlib)
│   └── output/              # 6 publication-quality PNG charts
├── api/
│   └── prediction_service.py # Clean Python inference engine with explainability
├── tests/
│   └── test_salary_engine.py # Automated unit test suite
└── docs/
    ├── DATASET_AUDIT.md     # Audit of raw & processed sources, exclusion rules
    ├── METHODOLOGY.md       # Econometric grounding, Mincer curve & regression benchmarks
    └── MODEL_CARD.md        # Official model card, validation metrics & limitations
```

---

## 3. Key Scientific Findings & Benchmark Results

### 3.1 Curated Cohort Characteristics
- **Total Valid Disclosed Records**: 32,579 (after dropping 20 USD listings, 146 extreme bounds, and 393 exact duplicates)
- **Train / Test Split**: 26,063 train (80%), 6,516 test (20%) stratified by role family
- **Market Medians**:
  - Full Market: Median **₹4.25 LPA**, Mean **₹7.53 LPA**
  - Technical Careers: Median **₹8.00 LPA**, Mean **₹11.44 LPA**

### 3.2 Regression Model Comparison

| Model | Test MAE | Test MedAE | Test RMSE | Test R² | 5-Fold CV MAE |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **DummyRegressor (Median Baseline)** | 4.706 LPA | 1.750 LPA | 9.442 LPA | -0.1409 | 4.688 LPA |
| **Linear Regression (Log Scale)** | 3.028 LPA | 1.161 LPA | 6.843 LPA | 0.4007 | 3.018 LPA |
| **Ridge Regression ($\alpha=10.0$)** | 3.024 LPA | 1.159 LPA | 6.833 LPA | 0.4025 | 3.014 LPA |
| **Random Forest Regressor ($n=100$)** | **2.884 LPA** | **1.094 LPA** | **6.593 LPA** | **0.4436** | **2.921 LPA** |

### 3.3 Experience Stratification
- **Fresher (0-1 yrs)**: Test MAE **0.992 LPA** | MedAE **0.603 LPA**
- **Early Career (2-4 yrs)**: Test MAE **1.884 LPA** | MedAE **0.793 LPA**
- **Mid-Level (5-8 yrs)**: Test MAE **3.175 LPA** | MedAE **1.816 LPA**
- **Senior (9-12 yrs)**: Test MAE **5.155 LPA** | MedAE **3.860 LPA**

### 3.4 Production Model: Technical-Only Engine v2.0.0 (Option A)

Under Option A, JobRadar v2.0.0 focuses strictly on 8 approved technical engineering and data career families ($N=4,207$ postings across 1,764 unique employers):

#### Verified Technical Role Distribution:
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

#### 5-Fold GroupKFold Cross-Validation (companyName_clean):
- **Champion Architecture**: Ridge Regression ($\alpha=10.0$) with log-target transformation.
- **Out-of-Company Validation Metrics**: MAE **4.740 LPA**, MedAE **3.174 LPA**, RMSE **7.035 LPA**, $R^2 = \mathbf{0.4639}$, MAPE **55.84%**.

#### Calibrated Conformal Prediction Intervals:
Empirically calibrated 90% conformal prediction interval based on out-of-fold employer-grouped residuals. Independent held-out cross-conformal evaluation showed mean overall coverage of approximately 90.09%. Individual role-fold coverage varied from 76.7% to 96.9%. These results are empirical and do not establish guaranteed coverage for every role or future employer.

#### Operational Limitations:
1. The dataset contains 4,207 classifier-assigned technical job postings, not manually verified labels for every posting.
2. Company-name normalization is imperfect. Variations in employer names can allow related entities to appear across different validation folds. GroupKFold prevents exact company-name overlap but does not fully solve parent-company or staffing-agency entity resolution (canonicalization recorded as a future improvement).
3. Salary predictions have substantial error and should be treated as estimates, not exact compensation offers.
4. Data Science / ML / AI has fewer observations than larger career families.
5. Salary disclosure and dataset composition may introduce selection bias.
6. Results may not generalize to every employer, location, experience level, or future market condition.

---

## 4. API Endpoints

### `POST /api/salary/predict`
Request:
```json
{
  "role": "Data Scientist",
  "experience_years": 2.5,
  "location": "Bengaluru",
  "skills": ["Python", "SQL", "Pandas", "Machine Learning"]
}
```
Response:
```json
{
  "target_role": "Data Scientist",
  "experience_years": 2.5,
  "location": "Bengaluru",
  "predicted_salary_lpa": 6.85,
  "predicted_salary_annual_inr": 685000,
  "salary_range_lpa": {
    "min_lpa": 3.97,
    "max_lpa": 9.73
  },
  "salary_range_annual_inr": {
    "min_inr": 397000,
    "max_inr": 973000
  },
  "role_median_lpa": 8.0,
  "market_tier": "tier_1_metro",
  "model_name": "Random Forest Regressor (n=100)",
  "model_version": "1.0.0",
  "mae_uncertainty_lpa": 2.88,
  "contributing_factors": [
    "Core career progression curve applied for 2.5 years experience.",
    "Tier-1 tech metro compensation premium applied for Bengaluru.",
    "Valued technical competencies detected: Python, SQL."
  ],
  "disclaimers": [...]
}
```

### `GET /api/salary/metadata`
Returns model card details, validation metrics, feature importances, and role breakdowns.

---

## 5. Verification Commands

1. **Train Models & Regenerate Artifacts**:
   ```bash
   python -m Phase_6_Salary_Prediction.models.trainer
   ```
2. **Generate EDA Charts**:
   ```bash
   python -m Phase_6_Salary_Prediction.visualizers.eda_plots
   ```
3. **Run Unit Tests**:
   ```bash
   python -m unittest discover -s AI_ML/Phase_6_Salary_Prediction/tests
   ```
4. **Run API Tests**:
   ```bash
   python -m unittest DDS-Job-Market-Project/tests/test_salary_prediction_api.py
   ```
