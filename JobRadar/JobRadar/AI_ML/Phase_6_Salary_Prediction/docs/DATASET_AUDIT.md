# Phase 6: Salary Dataset Audit Report

## 1. Executive Summary

This audit evaluated all candidate salary datasets in the JobRadar workspace to identify reliable ground-truth observations for training the Indian Tech Salary Prediction Engine without synthetic bias or target leakage.

---

## 2. Dataset Evaluations

### 2.1 Primary Source: `cleaned_indian_job_market_2025.csv`
- **Total Records**: 97,682
- **Unique `jobId`s**: 97,679 (only 3 duplicate keys)
- **Salary Status Distribution**:
  - `not_disclosed`: 63,920 (65.44%)
  - `valid`: 33,138 (33.92%)
  - `missing_bounds`: 571 (0.58%)
  - `zero_unknown`: 45 (0.05%)
  - `incomplete_range`: 8 (0.01%)
- **Currency**: 97,553 INR, 129 USD (among valid disclosed salaries: 33,118 INR, 20 USD).
- **Salary Bounds Quality**:
  - `min_salary <= max_salary`: 100% compliant for valid subset (0 inverted bounds).
  - Flat salaries (`min == max`): 156 listings.
  - Salary ranges (`min < max`): 32,982 listings.
- **Experience Completeness**: `minimumExperience_clean` and `maximumExperience_clean` are 100% non-null (0 missing) in the valid salary subset.

### 2.2 External Raw Source: `tech-salaries-stated-india.csv`
- **Rows**: 25 aggregated summary records from Jobspiq benchmark reports (CC BY 4.0).
- **Structure**: Grouped statistics (`median_lpa`, `lower_quartile_lpa`, `upper_quartile_lpa`) across experience levels and skill groups.
- **Suitability**: **Unsuitable for supervised training** because it lacks job-level rows; retained as an independent external macro-benchmark.

### 2.3 External Raw Source: `indian_tech_career_intelligence_2026.csv`
- **Rows**: 100,000
- **Structure**: Exactly 20,000 rows per platform (Naukri, Glassdoor, LinkedIn, AmbitionBox, Indeed).
- **Audit Finding**: Uniformly distributed random salaries (`salary_minimum` ~ Uniform(3L, 6L), `salary_maximum` ~ Uniform(7L, 18L)) showing synthetic characteristics (e.g. Interns paired with 2-4 years experience and 12+ LPA).
- **Suitability**: **Strictly excluded from training** to maintain academic and scientific integrity.

---

## 3. Curation & Exclusion Decisions

| Decision | Condition | Rows Excluded | Rationale |
| :--- | :--- | :--- | :--- |
| **Non-INR Currency** | `currency != 'INR'` | 20 | Avoids unit contamination and exchange-rate distortion. |
| **Sub-Minimum Wage / Misparsed Hourly** | `salary_mid_lpa < 0.60` | 128 | Daily/monthly stipends misclassified as annual figures (e.g. 1k-2k PA). |
| **Extreme C-Suite Outliers** | `salary_mid_lpa > 100.0` | 18 | Executive C-suite (e.g. 2-3 Crore) distorting standard student/developer regression. |
| **Exact Content Duplicates** | Duplicated on title, company, location, exp, salary | 393 | Eliminates web scraping repeats and prevents cross-split data leakage. |
| **Final Curated Modeling Cohort** | Compliant with all filters | **32,579** | High-integrity, verified domestic compensation dataset. |

---

## 4. Curated Cohort Summary Statistics

- **Sample Size**: 32,579 records
- **Median Midpoint Salary**: ₹4.25 LPA
- **Mean Midpoint Salary**: ₹7.528 LPA
- **Standard Deviation**: ₹8.645 LPA
- **Interquartile Range**: ₹2.875 LPA (25th) to ₹8.25 LPA (75th)
- **Technical Career Subset**: Median ₹8.00 LPA, Mean ₹11.44 LPA
