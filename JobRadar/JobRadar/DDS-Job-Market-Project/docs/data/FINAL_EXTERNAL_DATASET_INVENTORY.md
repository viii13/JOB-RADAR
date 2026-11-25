# JobRadar — Final External Dataset Inventory

> **Document Type:** Master Data Asset Inventory & Governance Register  
> **Status:** FORMALLY VERIFIED & LOCKED (POST-AUDIT REVIEW)  
> **Project:** JobRadar — Indian Tech Job Market Analysis and Career Intelligence Platform  
> **Repository Root:** `JobRadar/DDS-Job-Market-Project`  
> **External Directory:** `data/external/`  
> **Review Date:** 2026-11-11  

---

## 1. Inventory Summary & Counting Reconciliation

This inventory establishes the authoritative reconciliation of all external data assets across physical storage, distinct dataset entities, and data governance classifications.

### 1.1 Complete Reconciliation Matrix

To eliminate ambiguity, distinct acquired datasets are strictly decoupled from physical file counts, duplicate archives, raw upstream name aliases, and unacquired candidates:

| Asset Category | Distinct Datasets | Primary Content Files | Duplicate / Alias Files | Total Physical Files on Disk | Physical Disk Footprint | Governance & Usage Scope |
|---|---:|---:|---:|---:|---:|---|
| **Tier 1: Approved Datasets** | **7** | 8 | 2 | 10 | ~334.28 MB | Approved for Phase 5 recommendations, skill demand validation, and macroeconomic benchmarking. |
| **Tier 2: Conditionally Approved Datasets** | **2** | 2 | 0 | 2 | ~15.29 MB | Approved for Phase 4 classifier benchmarking and Phase 5 skill extraction; strictly quarantined from Phase 6 salary training. |
| **Tier 3: Reference Datasets** | **1** | 1 | 0 | 1 | ~9.46 MB | Legacy scraper snapshot (2,500 jobs) preserved strictly as an integration testing fixture. |
| **Tier 4: Quarantined / Rejected Datasets** | **1** | 1 | 0 | 1 | ~56.60 MB | Synthetic ITCI dataset permanently isolated to prevent ML parameter contamination. |
| **Tier 5: Duplicate Archives** | **0** | 0 | 1 | 1 | ~9.46 MB | Archival preservation of duplicate Role Radar file previously relocated from Tevos. |
| **Subtotal (Physical Workspace)** | **11** | **12** | **3** | **15** | **~415.90 MB** | **All physical files present in `data/external/`.** |
| **Tier 6: Skipped / Unavailable Candidates** | **1** | 0 | 0 | 0 | 0 MB | Headcount Labs: Formally evaluated in Step 2; skipped due to commercial paywall. |
| **Total Tracked Candidates** | **12** | **12** | **3** | **15** | **~415.90 MB** | Full collection lifecycle accounting. |

### 1.2 Counting Methodology Notes
1. **Physical Files on Disk (15 files, ~415.90 MB):** Exactly 15 physical files exist under `data/external/`.
2. **Duplicate Copies & Name Aliases (3 physical files):**
   - `data/external/duplicates_archive/role_radar_scraped_jobs_duplicate.json` (exact duplicate of `role_radar/raw/scraped_jobs.json`).
   - `data/external/stackoverflow/raw/results.csv` and `schema.csv` (exact upstream Git LFS name aliases of `survey_results_public.csv` and `survey_results_schema.csv` retained for tool compatibility).
   - *These 3 files are duplicates/aliases and are NOT counted as independent datasets.*
3. **Distinct Acquired Datasets on Disk (11 datasets):**
   - 7 Approved + 2 Conditionally Approved + 1 Reference + 1 Quarantined = **11 distinct datasets** (comprising 12 primary content files).
4. **Multi-File Dataset:** Stack Overflow Developer Survey 2024 is **1 distinct dataset** composed of 2 primary content files (`survey_results_public.csv` + `survey_results_schema.csv`).

---

## 2. Comprehensive External Dataset Catalog

### 2.1 Tier 1: Approved Datasets (7 Distinct Datasets, 8 Primary Files)

#### 1. Stack Overflow Developer Survey 2024
* **Dataset Identifier:** `ds-ext-so-2024`
* **Publisher / Source:** Stack Exchange, Inc. | [survey.stackoverflow.co/2024](https://survey.stackoverflow.co/2024)
* **Primary Content Files:**
  - `data/external/stackoverflow/raw/survey_results_public.csv` (159,525,875 bytes, 65,437 rows × 114 cols)
  - `data/external/stackoverflow/raw/survey_results_schema.csv` (12,503 bytes, 87 rows × 6 cols)
* **Repository Aliases (Duplicates):**
  - `data/external/stackoverflow/raw/results.csv` (SHA-256 matches public CSV)
  - `data/external/stackoverflow/raw/schema.csv` (SHA-256 matches schema CSV)
* **SHA-256 Checksums:**
  - `survey_results_public.csv`: `7f2c2dbf6989d00b80a7351de4bb3af4b52b21cc52d5c947891bbc4f4e5cbe49`
  - `survey_results_schema.csv`: `d9c03fd43949dd9b0fea4847894c4011a6fe3c4390d5d8c48e078a8bfe623833`
* **Licence & Evidence:** **Open Database License (ODbL) v1.0 (VERIFIED)**. Attribution and Share-Alike obligations apply to publicly redistributed derived databases.
* **Audit Status:** **AUDITED & APPROVED (Step 4B)**
* **Recommended Phase:** **Phase 5 (Career Recommendation Engine)**
* **Approved Use:** Developer career paths (`YearsCode` vs `YearsCodePro`), cross-stack technology co-occurrence, and macro salary reality check.
* **Strict Governance Boundary:** **Must never be pooled into employer-posted job salary training sets.** Measures self-reported 2024 total comp (including equity/bonuses) of tenured engineers, distinct from employer base CTC bids.

---

#### 2. GitHub Innovation Graph — Programming Languages
* **Dataset Identifier:** `ds-ext-github-languages-2026`
* **Publisher / Source:** GitHub, Inc. | [github.com/github/innovationgraph](https://github.com/github/innovationgraph)
* **Relative File Path:** `data/external/github_innovation_graph/raw/languages.csv`
* **File Format & Size:** CSV (UTF-8) | 6,154,689 bytes (5.87 MB)
* **Dimensions:** **190,246 rows × 6 columns** (5,009 quarterly observations for India across 300 languages)
* **SHA-256 Checksum:** `72932bc0f65f469f2f53a1b020d07bbd27cd1df6917809143ae6171e1b3aecaa`
* **Temporal Span:** 2020 Q1 through 2026 Q2 (26 consecutive quarters).
* **Licence & Evidence:** **CC0 1.0 Universal Public Domain Dedication (VERIFIED)** via official repository `LICENSE`.
* **Audit Status:** **AUDITED & APPROVED (Step 4B)**
* **Recommended Phase:** **Phase 5 (Career Recommendation & Skill Gap Analysis)**
* **Approved Use:** Longitudinal technology momentum weighting, emerging language tracking in India.
* **Strict Governance Boundary:** Reflects public repository git pushers only (omits private enterprise codebases). Activity volume does **not** equal commercial job vacancies or wage levels.

---

#### 3. Jobspiq — Skills Demand India
* **Dataset Identifier:** `ds-ext-jobspiq-skills`
* **Publisher / Source:** Jobspiq India Benchmark Division
* **Relative File Path:** `data/external/jobspiq/benchmarks/skills-demand-india.csv`
* **File Format & Size:** CSV (UTF-8) | 9,008 bytes (8.80 KB)
* **Dimensions:** **76 rows × 8 columns**
* **SHA-256 Checksum:** `41e3f8797f82f623d8dec8b35ba51d3d88628b1fb0091ee610e3378472cffdba`
* **Licence & Evidence:** **Unknown / Unverified**. No formal license file accompanied this dataset in the repository.
* **Permitted Usage:** **Internal Academic & Research Benchmark Use Only.** Non-commercial research reference.
* **Audit Status:** **AUDITED & APPROVED (Step 1)**
* **Recommended Phase:** **Phase 5 (Skill Prioritization & Benchmarking)**

---

#### 4. Jobspiq — Tech Salaries Stated India
* **Dataset Identifier:** `ds-ext-jobspiq-salaries`
* **Publisher / Source:** Jobspiq India Benchmark Division
* **Relative File Path:** `data/external/jobspiq/benchmarks/tech-salaries-stated-india.csv`
* **File Format & Size:** CSV (UTF-8) | 2,593 bytes (2.53 KB)
* **Dimensions:** **25 rows × 9 columns**
* **SHA-256 Checksum:** `b332fd324f3ba37f5274bde39eb3cc2f19062c7ccc19044cf391b7073ebc4b5c`
* **Licence & Evidence:** **Unknown / Unverified**. No formal license file present.
* **Permitted Usage:** **Internal Academic & Research Benchmark Use Only.** Non-commercial research reference.
* **Audit Status:** **AUDITED & APPROVED (Step 1)**
* **Recommended Phase:** **Phase 6 (Salary Prediction Benchmarking)**

---

#### 5. JobTether — Experience Bar Distribution
* **Dataset Identifier:** `ds-ext-jobtether-exp`
* **Publisher / Source:** JobTether Analytics
* **Relative File Path:** `data/external/jobtether/benchmarks/experience-bar-distribution.csv`
* **File Format & Size:** CSV (UTF-8) | 292 bytes
* **Dimensions:** **10 rows × 4 columns**
* **SHA-256 Checksum:** `31ea99ef3d35d98657c82da1a43fee662b27ff863293fc8ae5cf2d7ffa7de3d2`
* **Licence & Evidence:** **Unknown / Unverified**. No formal license file present.
* **Permitted Usage:** **Internal Academic & Research Benchmark Use Only.**
* **Audit Status:** **AUDITED & APPROVED (Step 1)**
* **Recommended Phase:** **Phase 5 & Phase 6 (Experience Tier Binning Reference)**

---

#### 6. JobTether — Salary Disclosure by Company
* **Dataset Identifier:** `ds-ext-jobtether-disclosure`
* **Publisher / Source:** JobTether Analytics
* **Relative File Path:** `data/external/jobtether/benchmarks/salary-disclosure-by-company.csv`
* **File Format & Size:** CSV (UTF-8) | 17,243 bytes (16.84 KB)
* **Dimensions:** **549 rows × 6 columns**
* **SHA-256 Checksum:** `d282e73a35ef29d3b1c8d9e1892c007710f06a00314cfc80a99bf4e448b0b133`
* **Licence & Evidence:** **Unknown / Unverified**. No formal license file present.
* **Permitted Usage:** **Internal Academic & Research Benchmark Use Only.**
* **Audit Status:** **AUDITED & APPROVED (Step 1)**
* **Recommended Phase:** **Phase 6 (Salary Transparency EDA Reference)**

---

#### 7. Tevos — Top Skills Benchmark
* **Dataset Identifier:** `ds-ext-tevos-skills`
* **Publisher / Source:** Tevos Workforce Analytics
* **Relative File Path:** `data/external/tevos/benchmarks/top-skills.json`
* **File Format & Size:** JSON | 4,839 bytes (4.73 KB)
* **Dimensions:** **10 role families, structured skill priority hierarchies**
* **SHA-256 Checksum:** `74407ad74278486547d11c4987aa65858935343946f85611e52008bc4d4d6637`
* **Licence & Evidence:** **Unknown / Unverified**. No formal license file present.
* **Permitted Usage:** **Internal Reference Taxonomy Only.**
* **Audit Status:** **AUDITED & APPROVED (Step 1)**
* **Recommended Phase:** **Phase 5 (Skill Recommendation Taxonomy Reference)**

---

### 2.2 Tier 2: Conditionally Approved Datasets (2 Distinct Datasets, 2 Primary Files)

#### 8. Kaggle Indian Tech Jobs 2026 (Shreyash Gade)
* **Dataset Identifier:** `ds-ext-kaggle-tech-23k`
* **Publisher / Source:** Shreyash Gade | [kaggle.com/datasets/shree0910/india-tech-job-market-2026-23k-records](https://www.kaggle.com/datasets/shree0910/india-tech-job-market-2026-23k-records)
* **Relative File Path:** `data/external/kaggle_tech_23k/raw/indian_tech_jobs_2026.csv`
* **File Format & Size:** CSV (UTF-8) | 14,006,736 bytes (13.36 MB)
* **Dimensions:** **23,201 rows × 32 columns**
* **SHA-256 Checksum:** `f220404b0b6d3fde9471a3758f887e2f103ec772dda3ab2d20cafef9d0b53fb1`
* **Licence & Evidence:**
  - **Publisher Declared Licence:** Community Data License Agreement (CDLA-Permissive) on Kaggle.
  - **Source-Platform Content Rights:** **Unknown / Unverified & Restricted**. Scraped from Naukri.com without documented platform permission. The publisher's CDLA declaration does **not** grant third-party commercial redistribution rights over underlying Naukri job postings. Restricted strictly to non-commercial academic research.
* **Audit Status:** **AUDITED & CONDITIONALLY APPROVED (Step 4 & 4B)**
* **Recommended Phase Allocation:**
  - **Phase 4 (AI Classifier Testing):** Approved as an out-of-sample test benchmark (23,201 jobs).
  - **Phase 5 (Skill Extraction):** Approved for skill co-occurrence graph generation.
  - **Phase 6 (Salary Prediction):** **STRICTLY QUARANTINED.**
* **Salary Disclosed Partition & Integrity Clarification (2,768 records total):**
  - **Group 1: Synthetic Imputed Unpaid Records (306 records, 11.05%):** `salary_raw == "Unpaid"` imputed with synthetic range 10–18 LPA (midpoint 14.0 LPA). **Zero overlap with sub-1.0 LPA records.**
  - **Group 2: Sub-1.0 LPA Records (105 records, 3.79%):**
    * *2 zero-salary invalid records* (`"0 PA"`, midpoint = 0.0 LPA).
    * *40 unannualized monthly stipends* (e.g. `"20,000/month"` parsed as 0.20 LPA).
    * *36 corrupted mixed-range regex inversions* (e.g. `"50,000-15 Lacs PA"` parsed as 0.25 LPA).
    * *27 genuine low annual salaries/ranges* (18 flat e.g. `"50,000 PA"` = 0.5 LPA, 9 ranges e.g. `"50,000-80,000 PA"` = 0.65 LPA).
  - **Group 3: Standard Clean $\ge 1.0$ LPA Records (2,357 records, 85.15%):** Genuine stated ranges/flat values in Lacs PA.
  - *Mathematical Check:* $306 + 105 + 2,357 = 2,768 \text{ records}$ (100% mutually exclusive).
* **Non-Independence Constraint:** Shares Naukri.com provenance with JobRadar (76 exact Naukri IDs, 2,064 common employers). Governed as a vertical/temporal expansion set, not an independent population.

---

#### 9. Fliar — India Salary Benchmarks 2026 Sample
* **Dataset Identifier:** `ds-ext-fliar-sample`
* **Publisher / Source:** Fliar Analytics / Hugging Face Hub
* **Relative File Path:** `data/external/fliar/raw/india_salary_benchmarks_2026_sample.csv`
* **File Format & Size:** CSV (UTF-8) | 2,024,308 bytes (1.93 MB)
* **Dimensions:** **12,958 rows × 14 columns**
* **SHA-256 Checksum:** `e63de7a3036643a3e6ba1abf84f73d0ca1edcf9060f1a810ffc72982834b0a81`
* **Licence & Evidence:** **Unknown / Unverified**. Open community upload on Hugging Face without formal open-source license text.
* **Permitted Usage:** Non-commercial exploratory research only.
* **Audit Status:** **AUDITED & CONDITIONALLY APPROVED (Step 1 & 2C)**
* **Recommended Phase:** **Phase 6 (Salary Band Cross-Verification)**
* **Governance Limitations:** Contains 12,958 sample rows (not 49k). Pre-binned percentiles only; exploratory reference, not for continuous regression training.

---

### 2.3 Tier 3: Reference Datasets (1 Distinct Dataset, 1 Primary File)

#### 10. Role Radar — Scraped Jobs Sample
* **Dataset Identifier:** `ds-ext-role-radar-raw`
* **Publisher / Source:** Role Radar Open Ingestion Stream
* **Relative File Path:** `data/external/role_radar/raw/scraped_jobs.json`
* **File Format & Size:** JSON | 9,917,593 bytes (9.46 MB)
* **Dimensions:** **2,500 rows × 16 attributes**
* **SHA-256 Checksum:** `78d32995b4a770f4bf19f8052e984cee617a5935f15820045fc6b16785384bef`
* **Licence & Evidence:** **Unverified / Scraped Content**. Scraped job postings without explicit platform licensing.
* **Permitted Usage:** Internal testing fixture only.
* **Audit Status:** **AUDITED & APPROVED AS REFERENCE (Step 1)**
* **Recommended Phase:** **Integration Pipeline Regression Testing**

---

### 2.4 Tier 4: Quarantined / Rejected Datasets (1 Distinct Dataset, 1 Physical File)

#### 11. Indian Tech Career Intelligence 2026 (Synthetic ITCI)
* **Dataset Identifier:** `ds-ext-rejected-itci-synthetic`
* **Publisher / Source:** Unknown Third-Party / Open Kaggle Mirror
* **Relative File Path:** `data/external/rejected/synthetic_itci_2026/indian_tech_career_intelligence_2026.csv`
* **File Format & Size:** CSV (UTF-8) | 59,347,309 bytes (56.60 MB)
* **Dimensions:** **100,000 rows × 33 columns**
* **SHA-256 Checksum:** `f69a8de12e0d379419e7f9767c74a366366fabab864d20eb6f414bba21ad403c`
* **Licence & Evidence:** **Unknown / Unverified (REJECTED)**.
* **Permitted Usage:** **STRICTLY PROHIBITED FROM ALL PIPELINES, DATABASES, AND MODELS.**
* **Audit Status:** **AUDITED & REJECTED (Step 1 & 1B)**
* **Rejection Reason:** 100% synthetic uniform random generation. Preserved strictly for audit reproducibility in quarantined directory.

---

### 2.5 Tier 5: Duplicate Archives & Aliases (0 Distinct Datasets, 3 Physical Files)

* **`data/external/duplicates_archive/role_radar_scraped_jobs_duplicate.json`** (9.46 MB | SHA-256: `78d32995...`): Exact bit-for-bit duplicate of Role Radar `scraped_jobs.json` previously archived from Tevos.
* **`data/external/stackoverflow/raw/results.csv`** (152.14 MB | SHA-256: `7f2c2dbf...`): Exact Git LFS alias copy of `survey_results_public.csv`.
* **`data/external/stackoverflow/raw/schema.csv`** (12.21 KB | SHA-256: `d9c03fd4...`): Exact Git LFS alias copy of `survey_results_schema.csv`.

---

### 2.6 Tier 6: Skipped / Unavailable Candidates (1 Candidate, 0 Files on Disk)

* **Headcount Labs Tech Compensation Benchmark:** Formally evaluated during Step 2 discovery; skipped during Step 3 due to commercial sales-gating and paywalls. 0 bytes downloaded.

---

## 3. Catalog Cross-Reference Master Table

| Dataset Identifier | Canonical File Name | Folder Path | Physical Size | Cryptographic SHA-256 Checksum | Rows | Cols | Formal Licence Status | Governance Tier | Approved Phase |
|---|---|---|---:|---|---:|---:|---|---|---|
| `ds-ext-so-2024` | `survey_results_public.csv` | `data/external/stackoverflow/raw/` | 152.14 MB | `7f2c2dbf6989d00b80a7351de4bb3af4b52b21cc52d5c947891bbc4f4e5cbe49` | 65,437 | 114 | ODbL v1.0 (Verified) | Approved | Phase 5 |
| `ds-ext-so-schema-2024` | `survey_results_schema.csv` | `data/external/stackoverflow/raw/` | 12.21 KB | `d9c03fd43949dd9b0fea4847894c4011a6fe3c4390d5d8c48e078a8bfe623833` | 87 | 6 | ODbL v1.0 (Verified) | Approved | Phase 5 |
| `ds-ext-github-languages-2026` | `languages.csv` | `data/external/github_innovation_graph/raw/` | 5.87 MB | `72932bc0f65f469f2f53a1b020d07bbd27cd1df6917809143ae6171e1b3aecaa` | 190,246 | 6 | CC0-1.0 (Verified) | Approved | Phase 5 |
| `ds-ext-jobspiq-skills` | `skills-demand-india.csv` | `data/external/jobspiq/benchmarks/` | 8.80 KB | `41e3f8797f82f623d8dec8b35ba51d3d88628b1fb0091ee610e3378472cffdba` | 76 | 8 | Unknown / Unverified | Approved | Phase 5 |
| `ds-ext-jobspiq-salaries` | `tech-salaries-stated-india.csv` | `data/external/jobspiq/benchmarks/` | 2.53 KB | `b332fd324f3ba37f5274bde39eb3cc2f19062c7ccc19044cf391b7073ebc4b5c` | 25 | 9 | Unknown / Unverified | Approved | Phase 6 |
| `ds-ext-jobtether-exp` | `experience-bar-distribution.csv` | `data/external/jobtether/benchmarks/` | 292 B | `31ea99ef3d35d98657c82da1a43fee662b27ff863293fc8ae5cf2d7ffa7de3d2` | 10 | 4 | Unknown / Unverified | Approved | Phase 5/6 |
| `ds-ext-jobtether-disclosure` | `salary-disclosure-by-company.csv` | `data/external/jobtether/benchmarks/` | 16.84 KB | `d282e73a35ef29d3b1c8d9e1892c007710f06a00314cfc80a99bf4e448b0b133` | 549 | 6 | Unknown / Unverified | Approved | Phase 6 |
| `ds-ext-tevos-skills` | `top-skills.json` | `data/external/tevos/benchmarks/` | 4.73 KB | `74407ad74278486547d11c4987aa65858935343946f85611e52008bc4d4d6637` | 10 | 1 | Unknown / Unverified | Approved | Phase 5 |
| `ds-ext-kaggle-tech-23k` | `indian_tech_jobs_2026.csv` | `data/external/kaggle_tech_23k/raw/` | 13.36 MB | `f220404b0b6d3fde9471a3758f887e2f103ec772dda3ab2d20cafef9d0b53fb1` | 23,201 | 32 | CDLA on Kaggle / Scraped Rights Unverified | Conditional | Phase 4/5 |
| `ds-ext-fliar-sample` | `india_salary_benchmarks_2026_sample.csv` | `data/external/fliar/raw/` | 1.93 MB | `e63de7a3036643a3e6ba1abf84f73d0ca1edcf9060f1a810ffc72982834b0a81` | 12,958 | 14 | Unknown / Unverified | Conditional | Phase 6 |
| `ds-ext-role-radar-raw` | `scraped_jobs.json` | `data/external/role_radar/raw/` | 9.46 MB | `78d32995b4a770f4bf19f8052e984cee617a5935f15820045fc6b16785384bef` | 2,500 | 16 | Unverified Scraped Data | Reference | Testing |
| `ds-ext-rejected-itci-synthetic` | `indian_tech_career_intelligence_2026.csv` | `data/external/rejected/synthetic_itci_2026/` | 56.60 MB | `f69a8de12e0d379419e7f9767c74a366366fabab864d20eb6f414bba21ad403c` | 100,000 | 33 | Unknown / Unverified | Rejected | None |
| *(Alias) so-alias-results* | `results.csv` | `data/external/stackoverflow/raw/` | 152.14 MB | `7f2c2dbf6989d00b80a7351de4bb3af4b52b21cc52d5c947891bbc4f4e5cbe49` | 65,437 | 114 | ODbL v1.0 (Alias) | Duplicate | None |
| *(Alias) so-alias-schema* | `schema.csv` | `data/external/stackoverflow/raw/` | 12.21 KB | `d9c03fd43949dd9b0fea4847894c4011a6fe3c4390d5d8c48e078a8bfe623833` | 87 | 6 | ODbL v1.0 (Alias) | Duplicate | None |
| *(Archive) role-radar-dup* | `role_radar_scraped_jobs_duplicate.json` | `data/external/duplicates_archive/` | 9.46 MB | `78d32995b4a770f4bf19f8052e984cee617a5935f15820045fc6b16785384bef` | 2,500 | 16 | Duplicate Archive | Duplicate | None |

---

## 4. Governance Sign-Off

* **Lead Reviewer:** Independent Senior Data Scientist, Data Engineer, and Data Governance Reviewer
* **Integrity Audit:** 100% of physical files verified with SHA-256 cryptographic hashes.
* **Status:** LOCKED FOR INTEGRATION.
