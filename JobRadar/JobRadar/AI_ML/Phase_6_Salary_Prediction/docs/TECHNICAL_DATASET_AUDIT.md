# JobRadar Phase 6 — Technical Salary Dataset Audit (v2.0.0)

**Date:** November 2026  
**Cohort Scope:** Option A — Core Technical Careers Only  
**Source Dataset:** `cleaned_indian_job_market_2025.csv` (SHA256: `403017518B4CAFC016DB659AE1912CC9F4E9DF9B927A416605A6004F8AEDB1B8`)  
**Skills Dataset:** `job_skills.csv` (SHA256: `AED76C8B28A9A60F6C026EF368A68BCB46F6F6962128C77B8E47162EF590E881`)  
**Output Curated Dataset:** `curated_technical_salary_data.csv` (4,207 rows, 1,764 unique companies)  

---

## 1. Funnel and Filtering Decisions

| Step | Operation / Filter | Retained Rows | Excluded Rows | Rationale |
|---|---|---|---|---|
| **0** | Raw Dataset Ingestion | 97,682 | — | Raw scraped Indian job market listings. |
| **1** | Disclosed Valid Salaries (`salary_status == 'valid'`) | 33,138 | 64,544 | Excludes imputed or synthetic salaries. Zero synthetic target contamination. |
| **2** | Domestic Currency (`currency == 'INR'`) | 33,118 | 20 | Excludes ambiguous international USD records. |
| **3** | Reasonable Annual Salary Range ($0.60 \le \text{LPA} \le 100.0$) | 32,873 | 245 | Excludes sub-minimum daily wages and extreme C-suite outliers. |
| **4** | Attribute Deduplication (title, company, location, exp, salary) | 32,579 | 294 | Eliminates identical cross-split reposts. |
| **5** | Multi-Field Phase 4 Classification (Title $3\times$ + Skills $2\times$ + Tags + Desc 500c) | 32,579 | — | Evaluated against all 11 classes in `role-taxonomy-v1`. |
| **6** | Technical Domain Scope Filtering (Approved 8 Technical Families) | 4,293 | **28,286** | Excludes sales, BPO, HR, operations, and unclassified non-technical postings. |
| **7** | Phase 4 Confidence Cutoff ($\text{confidence} \ge 0.20$) | **4,207** | **86** | Consistent with Phase 5 benchmark extractor threshold; removes edge cases. |

---

## 2. Technical Career Distribution and Consolidation

In accordance with Option A, the 8 approved technical career families from `role_taxonomy.json` are retained:

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

Data Science ($N=35$) and Machine Learning / AI ($N=174$) are consolidated for primary regression under `data_science_ml_ai` ($N=209$) to ensure sufficient sample support, while original taxonomy tags are preserved.

### Consolidated Primary Modeling Families:
| Role Model Family | Valid Sample Count ($N$) | % of Technical Cohort | Median Salary (LPA) | Mean Salary (LPA) | Std Dev (LPA) | Mean Experience (Yrs) |
|---|---|---|---|---|---|---|
| `backend_core_software_engineering` | 1,440 | 34.23% | 14.00 | 14.93 | 9.48 | 6.7 |
| `frontend_full_stack_engineering` | 673 | 16.00% | 15.00 | 15.18 | 9.38 | 6.8 |
| `qa_automation_testing` | 618 | 14.69% | 6.50 | 9.17 | 7.34 | 6.2 |
| `data_analyst_business_intelligence` | 492 | 11.69% | 6.50 | 9.68 | 8.09 | 5.1 |
| `cloud_devops_sre` | 389 | 9.25% | 18.00 | 18.84 | 8.84 | 9.5 |
| `data_engineer_big_data_platform` | 386 | 9.17% | 20.00 | 18.99 | 7.92 | 7.8 |
| `data_science_ml_ai` | 209 | 4.97% | 19.50 | 20.50 | 12.33 | 7.6 |
| **Total Technical Cohort** | **4,207** | **100.0%** | **13.50** | **14.43** | **9.61** | **6.9** |

### Original 8-Role Breakdown (Data Science vs Machine Learning):
- **`machine_learning_ai_engineer`**: $N = 174$ (Median: 20.00 LPA, Mean: 20.84 LPA, Mean Exp: 7.6 yrs)
- **`data_scientist_advanced_analytics`**: $N = 35$ (Median: 15.75 LPA, Mean: 18.79 LPA, Mean Exp: 7.3 yrs)

*Statistical Note:* With $N = 35$, Data Science alone represents < 1% of the cohort. Independent model training on 35 rows leaves only ~7 rows in a 20% test fold, causing extreme variance in regression metrics. Consolidating into `data_science_ml_ai` ($N = 209$) provides sound statistical power while honoring identical mathematical skill foundations (Python, SQL, Linear Algebra, Optimization, Machine Learning).

---

## 3. Employer Grouping & Leakage Prevention Audit

Indian job market data on Naukri.com frequently exhibits recruitment agency clustering, where a single consultancy posts hundreds of listings with identical compensation templates.

- **Total Technical Rows:** 4,207
- **Unique Employers (`companyName_clean`):** 1,764
- **Missing Company Names:** 0 (100% complete)
- **Top 5 Employers by Volume in Technical Cohort:**
  1. *Purview India Consulting And Services Llp*: 237 postings
  2. *Talent21*: 183 postings
  3. *Purview Services*: 98 postings
  4. *Cloudxtreme*: 93 postings
  5. *HR Innovation Group*: 74 postings

### GroupKFold Validation & Entity Resolution Nuance:
- **Exact-String Separation:** 5-Fold `GroupKFold` split strictly on `companyName_clean` guarantees 0% exact string overlap between training and validation folds.
- **Entity Resolution Limitation:** GroupKFold prevents exact company-name overlap but does not fully solve parent-company or staffing-agency entity resolution. For instance, unnormalized corporate suffixes (*Purview India Consulting And Services Llp*, *Purview Services*, *Purview India Consulting And Services*) allow related entities of the same parent agency to be partitioned across different validation folds.
- **Future Improvement:** Company-name canonicalization and entity normalization are recorded as future improvements, not as implemented features in v2.0.0.
