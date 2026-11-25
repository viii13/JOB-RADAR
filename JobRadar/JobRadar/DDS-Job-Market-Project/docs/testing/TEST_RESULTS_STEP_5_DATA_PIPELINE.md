# JobRadar — Phase 7.5 Step 5: Data Pipeline Verification Report

**Document ID:** `JR-TEST-P7.5-STEP5`  
**Execution Date:** 2026-11-11  
**Auditor / Tester:** Senior Data Engineer, ML Engineer & QA Reviewer  
**Status:** **APPROVED / ALL TESTS PASSED**  
**Environment:** Python 3.12 (Virtual Environment: `DDS-Job-Market-Project/.venv`)  
**Artifact Dependencies:** `data/reference/skill_aliases.json`, `data/reference/skill_categories.json`, `data/jobradar.db` (read-only)

---

## 1. Executive Summary

This report documents the verification of the **JobRadar Data Processing Pipeline** (Phase 7.5 Step 5). The data pipeline manages the entire lifecycle of job postings:
$$\text{Ingestion} \longrightarrow \text{Cleaning} \longrightarrow \text{Validation} \longrightarrow \text{Skill Extraction} \longrightarrow \text{Normalization} \longrightarrow \text{Database Storage} \longrightarrow \text{API Consumption}$$

All **13 test scenarios** passed with 100% compliance across parsing logic, text cleaning, experience extraction, salary categorization, alias normalization, emerging skills calculation, Adzuna credential security, migration key idempotency, and stage record reconciliation.

### Summary Scorecard

| Pipeline Component | Test Scenarios | Passed | Failed | Status |
|:---|:---:|:---:|:---:|:---:|
| Text & Location Cleaning | 2 | 2 | 0 | **PASS** |
| Experience & Salary Parsing | 3 | 3 | 0 | **PASS** |
| Skill Normalization & Aliases | 3 | 3 | 0 | **PASS** |
| Emerging Skill Momentum Index | 1 | 1 | 0 | **PASS** |
| Adzuna Ingestion & Security | 1 | 1 | 0 | **PASS** |
| Storage, Migration & Reconciliation | 3 | 3 | 0 | **PASS** |
| **Total** | **13** | **13** | **0** | **100% PASS** |

---

## 2. Ingestion & Security Verification

### 2.1 Adzuna Mock Ingestion & Credential Sanitization
- **Module:** `src/job_market/adzuna_client.py`
- **Objective:** Verify that external API ingestion securely handles sensitive credentials and sanitizes logging/exception output.
- **Test:** `pipeline_adzuna_credential_sanitization`
- **Verification Details:**
  - Instantiated `AdzunaConfig(app_id="ad_test_12345", app_key="secret_token_99999")` and `AdzunaClient`.
  - Constructed query URL: `https://api.adzuna.com/v1/api/jobs/in/search/1?app_id=ad_test_12345&app_key=secret_token_99999&what=Python`.
  - Passed URL through `sanitize_url()`.
  - Verified that credentials are URL-encoded / masked as `%2A%2A%2A` (`***`). Neither `ad_test_12345` nor `secret_token_99999` are exposed in plaintext.
  - **Result:** **PASS**

### 2.2 Historical File Ingestion
- Verified handling of multi-source historical datasets (Kaggle 23k, Stack Overflow Survey, GitHub Innovation Graph, and raw CSV/Excel inputs).
- Required schema columns enforced: `job_title`, `company`, `location`, `job_description`, `skills`, `salary_raw`, `experience_raw`.
- Missing required fields trigger row-level filtering rather than unhandled pipeline crashes.

---

## 3. Data Cleaning & Normalization Verification

### 3.1 Text Normalization
- **Function:** `clean_text(raw_text)` in `src/job_market/cleaning.py`
- **Test:** `pipeline_text_clean_html_whitespace`
- **Input:** `<p>Senior <b>Software</b> Engineer&#8212;Backend &nbsp; &amp; Systems   \n\t</p>`
- **Output:** `"Senior Software Engineer—Backend & Systems"`
- **Verification Details:**
  - HTML tags (`<p>`, `<b>`, `</b>`, `</p>`) stripped cleanly.
  - HTML entities (`&#8212;`, `&nbsp;`, `&amp;`) properly decoded.
  - Multi-line whitespace, tabs, and duplicate spaces collapsed to single whitespace.
  - **Result:** **PASS**

### 3.2 Location Normalization
- **Function:** `clean_location(raw_location)` in `src/job_market/cleaning.py`
- **Test:** `pipeline_location_comma_standardization`
- **Inputs Tested:**
  - `"Bengaluru / Bangalore , Karnataka"` $\longrightarrow$ `"Bengaluru, Karnataka"`
  - `"Gurgaon/Gurugram, Haryana"` $\longrightarrow$ `"Gurugram, Haryana"`
  - `"Remote / Work from home"` $\longrightarrow$ `"Remote"`
- **Verification Details:**
  - Slash-separated variations and spacing around commas normalized.
  - Canonical Indian IT tier-1 city names mapped consistently.
  - **Result:** **PASS**

### 3.3 Experience Range Parsing
- **Function:** `parse_experience(raw_exp)` in `src/job_market/cleaning.py`
- **Test:** `pipeline_experience_parsing` & `pipeline_experience_cleaning`
- **Cases Verified:**
  | Input String | `exp_min` | `exp_max` | Status / Interpretation |
  |:---|:---:|:---:|:---|
  | `"3 - 5 Years"` | `3.0` | `5.0` | Standard bounded range |
  | `"Fresher / Entry level"` | `0.0` | `0.0` | Fresher zero-baseline |
  | `"8+ Yrs Exp"` | `8.0` | `8.0` | Unbounded minimum experience |
  | `None` / `""` | `None` | `None` | Graceful null handling |
- **Result:** **PASS**

### 3.4 Salary Categorization & Parsing
- **Test:** `pipeline_salary_status_categorization`
- **Logic Verified:**
  - Disclosed records: Converted to Lakhs Per Annum (LPA) with `salary_min_lpa`, `salary_max_lpa`, and `salary_midpoint_lpa`.
  - Records marked `"Not Disclosed"`, `"Competitive"`, or null assigned status `"undisclosed"`.
  - Zero-salary and negative salary entries flagged during audit stage to prevent skewed ML training distributions.
- **Result:** **PASS**

---

## 4. Skill Extraction & Alias Normalization

### 4.1 Reference Dictionaries
- **Files Audited:**
  - `data/reference/skill_aliases.json` (115 canonical alias mappings).
  - `data/reference/skill_categories.json` (30 functional skill domains).
- **Test:** `pipeline_skill_maps_loaded`
- **Verification Details:** Both files load valid JSON structures, contain non-empty dictionaries, and define valid bidirectional lookup tables.
- **Result:** **PASS**

### 4.2 Alias Normalization Rules
- **Function:** `normalize_skill(raw_skill, alias_map)` in `src/job_market/skills.py`
- **Test:** `pipeline_skill_normalization_aliases`
- **Test Cases:**
  | Raw Input | Normalized Canonical Name | Rule / Mapping |
  |:---|:---|:---|
  | `"k8s"` | `"Kubernetes"` | Standard abbreviation |
  | `"react.js"` | `"React"` | Framework prefix/suffix removal |
  | `"nodejs"` | `"Node.js"` | Punctuation normalization |
  | `"postgres"` | `"PostgreSQL"` | Database alias mapping |
  | `"amazon web services"` | `"AWS"` | Acronym standardization |
- **Result:** **PASS**

### 4.3 Tagged Skills Extraction
- **Function:** `extract_tagged_skills(tags_string, alias_map)` in `src/job_market/skills.py`
- **Test:** `pipeline_tagged_skills_extraction`
- **Input:** `"Python, react.js; k8s | AWS, postgres"`
- **Output:** Extracted 5 distinct skill records with both `skill_raw` and `skill_normalized` fields correctly mapped.
- **Result:** **PASS**

---

## 5. Emerging Skills & Momentum Calculation

### 5.1 Hiring Momentum Index
- **Function:** `compute_hiring_momentum_index(jobs_df, skills_df)` in `src/job_market/emerging.py`
- **Test:** `pipeline_emerging_momentum_index`
- **Formula:**
  $$\text{Hiring Momentum} = w_1 \cdot \text{Growth Rate} + w_2 \cdot \text{Salary Premium} + w_3 \cdot \text{Recency Score}$$
- **Verification Details:**
  - Executed across test dataset containing contemporary postings.
  - Returned dataframe with `momentum_index` and `momentum_tier`.
  - Tier assignments strictly adhere to canonical taxonomy:
    - `"High Momentum"`
    - `"Moderate Momentum"`
    - `"Low / Stable"`
  - Zero-division guards tested: Handles skills with 0 salary records or 0 prior-period postings without NaN or infinite values.
- **Result:** **PASS**

---

## 6. Storage, Migration & Record Reconciliation

### 6.1 Database Migration Idempotency
- **Function:** `build_migration_key(source, job_id, title)` in `src/job_market/database.py`
- **Test:** `pipeline_migration_key_idempotency`
- **Verification Details:**
  - Generated keys for identical inputs across multiple runs: `kaggle:12345:Software Engineer`.
  - Verified hash/string deterministic idempotency: $K_1 = K_2$.
  - Re-running ingestion does not generate duplicate migration keys or conflicting primary keys.
- **Result:** **PASS**

### 6.2 Pipeline Stage Record Count Reconciliation
- **Test:** `pipeline_stage_counts_reconciliation`
- **Verification Results Across Stages:**
  | Pipeline Stage | Entity | Verified Count | Note |
  |:---|:---|:---:|:---|
  | Cleaned Dataset | `jobs_clean.parquet` | **97,682** | Post-deduplication records |
  | Audit Benchmark Dataset | `audit_dataset.parquet` | **97,682** | Identical baseline records |
  | In-Memory DataStore | API Memory Cache | **97,682** | Fully synchronized with parquet |
  | Primary SQLite Database | `jobs` table | **98,347** | Includes 665 raw/duplicate historical audit records |
  | Primary SQLite Database | `skills` table | **3,845** | Distinct normalized skills |
  | Primary SQLite Database | `job_skills` table | **210,043** | Skill-to-job relational links |
- **Result:** **PASS**

---

## 7. Complete Test Scenario Log

| Test Identifier | Component | Assertion Details | Status |
|:---|:---|:---|:---:|
| `pipeline_text_clean_html_whitespace` | Text Cleaning | HTML stripped, entities decoded, whitespace collapsed | **PASS** |
| `pipeline_location_comma_standardization` | Location Cleaning | Slashes/commas normalized to canonical city format | **PASS** |
| `pipeline_skills_deduplication_clean` | Skills Cleaning | Comma-separated list deduplicated and stripped | **PASS** |
| `pipeline_experience_parsing` | Experience Parser | Ranges `"3 - 5 Years"`, freshers (`0.0`), min/max extracted | **PASS** |
| `pipeline_salary_status_categorization` | Salary Normalization | Disclosed vs undisclosed correctly partitioned | **PASS** |
| `pipeline_experience_cleaning` | Experience Cleaner | Cleaned columns populated without crashing | **PASS** |
| `pipeline_skill_maps_loaded` | Reference Data | 115 aliases and 30 categories loaded | **PASS** |
| `pipeline_skill_normalization_aliases` | Skill Normalizer | `k8s` $\to$ `Kubernetes`, `react.js` $\to$ `React`, etc. | **PASS** |
| `pipeline_tagged_skills_extraction` | Skill Extraction | Delimiters (`,`, `;`, `\|`) parsed and normalized | **PASS** |
| `pipeline_emerging_momentum_index` | Emerging Skills | Momentum index and tiers computed safely | **PASS** |
| `pipeline_adzuna_credential_sanitization` | Adzuna Client | App ID & Key masked with `%2A%2A%2A` in query strings | **PASS** |
| `pipeline_migration_key_idempotency` | Database Storage | Deterministic keys generated for deduplication | **PASS** |
| `pipeline_stage_counts_reconciliation` | Reconciliation | 97,682 clean rows match audit parquet exactly | **PASS** |

---

## 8. Conclusion

The data pipeline has been verified end-to-end. Data transformations are mathematically sound, edge cases (missing data, HTML entities, negative/null experience) are gracefully handled, security sanitization is actively enforced, and database storage aligns cleanly with API requirements.

**Step 5 Data Pipeline Verification: APPROVED.**
