# JobRadar — Complete Repository Cleanup & Sharing Readiness Audit Report

**Document ID:** `JR-AUDIT-SHARING-2026-V1.0`  
**Date:** November 12, 2026  
**Auditor Roles:** Senior Software Engineer, Data Engineer, ML Engineer & Security Auditor  
**Audit Scope:** Entire JobRadar workspace (`c:\Users\aakas\OneDrive\Documents\Semester 3\Data Analysis using Python\Project Ds\JobRadar`)  
**Audit Status:** COMPLETE — READ-ONLY INSPECTION (0 repository files modified)  
**Sharing Verdict:** **BLOCKED / NOT READY FOR IMMEDIATE SHARING** (Requires Security & Large File Sanitization)

---

## 1. Executive Summary

A comprehensive, evidence-based architectural, data engineering, machine learning, and cybersecurity audit was conducted on the **JobRadar** repository to assess its readiness for sharing with external developers and version control distribution.

### 1.1 Platform Overview
JobRadar is an Indian technology job-market intelligence and career guidance platform consisting of:
1. **Backend Service (`JobRadar/DDS-Job-Market-Project`):** A high-performance FastAPI service providing REST endpoints for macroeconomic tech hiring trends, role classification, automated resume parsing, empirical skill gap calculation, milestone learning roadmaps, and regularized salary estimation with 90% calibrated conformal prediction intervals.
2. **AI/ML Engine (`JobRadar/AI_ML`):** Serialized pipelines and research assets across Phase 4 (Job Classification with TF-IDF and Logistic Regression), Phase 5 (Career Recommendation & Skill Gap Analysis with benchmark heuristics), and Phase 6 (Salary Prediction using Ridge Regression with log-transformed target variables and conformal uncertainty calibration).
3. **Frontend Application (`JobRadar/Frontend`):** A modern React 19 Single Page Application built with Vite 8 and Tailwind CSS, featuring interactive dashboards, career mindmaps, salary prediction widgets, and token-based authenticated profile workflows.

### 1.2 Verification Status
The existing codebase is structurally sound and functionally robust:
- **FastAPI Backend Suite:** 265 / 265 unit and integration tests passing (`OK` in 27.8s).
- **Phase 5 Career Recommendation Suite:** 57 / 57 tests passing (`OK` in 0.4s).
- **Phase 6 Salary Prediction Suite:** 9 / 9 tests passing (`OK` in 0.5s).
- **Frontend Authentication Test Suite:** 14 / 14 automated tests passing.
- **Frontend Component & Integration Suite:** 29 / 29 verification tests passing.
- **Total Passing Automated Tests:** **374 tests passing with zero failures**.

### 1.3 Key Audit Findings Summary

| Dimension | Finding Count | Criticality | Core Impact |
|:---|:---:|:---:|:---|
| **Security & Secrets** | 3 Confirmed | **CRITICAL** | Live Adzuna API credentials exposed in `.env`; live API key leaked in 36 Adzuna snapshot URLs; 42 active dev session tokens stored in `auth_users.db`. |
| **Git & Version Control** | 2 Confirmed | **HIGH** | No Git repository initialized; no `.gitignore` at workspace root; large files (>150 MB) unignored, which would immediately trigger GitHub push rejections. |
| **Repository Bloat** | 1.88 GB Footprint | **HIGH** | 481.2 MB of confirmed duplicate/obsolete data; 755.5 MB of regeneratable runtime virtual environments (`.venv`, `node_modules`). Clean sharing payload can be reduced from 1.88 GB to under 650 MB (or under 50 MB if excluding SQLite DB). |
| **Developer Onboarding** | 3 Confirmed | **HIGH** | `src/` not importable when running documented `uvicorn` command without `PYTHONPATH`; `pytest` and `matplotlib` omitted from `requirements.txt`; unpickling Phase 6 models outside engine fails due to namespace coupling. |
| **Documentation & Duplication** | 4 Confirmed | **MEDIUM** | Nested repository structure (`JobRadar/JobRadar`); duplicate READMEs; byte-for-byte duplicate authentication reports; 14 unlinked scratch scripts. |

---

## 2. Repository Structure Assessment

### 2.1 Physical Tree & Directory Layout Anomaly

The workspace directory is currently structured in a nested hierarchy:
```text
<WORKSPACE_ROOT>/ (JobRadar)
├── .pytest_cache/                                # Caches from root pytest invocation
├── scratch/                                      # 5 one-off inspection scripts
├── README.md                                     # Top-level workspace README (11.5 KB)
└── JobRadar/                                     # Inner project root
    ├── .gitignore                                # Inner ignore file (554 B)
    ├── README.md                                 # Inner project README (11.4 KB)
    ├── AUTHENTICATION_AUDIT.md                   # Duplicate markdown doc (12.5 KB)
    ├── AUTHENTICATION_IMPLEMENTATION_REPORT.md   # Duplicate markdown doc (13.3 KB)
    ├── AUTHENTICATION_SECURITY_REVIEW.md         # Duplicate markdown doc (14.7 KB)
    ├── scratch/                                  # 2 acceptance/audit scripts
    ├── AI_ML/                                    # Machine Learning modules & models
    ├── DDS-Job-Market-Project/                   # FastAPI backend, data, tests, docs
    └── Frontend/                                 # React 19 + Vite frontend
```

#### Structural Anomaly: Nested Project Folder
- **Evidence:** The active workspace is named `JobRadar`, but inside it sits another directory named `JobRadar`.
- **Impact:** Any developer receiving this folder structure will be confused about whether commands (`uvicorn`, `npm install`, `git init`) should be run from the root or from `JobRadar/`.
- **Path Divergence in Documentation:** The root `README.md` uses link targets prefixed with `JobRadar/DDS-Job-Market-Project/...`, whereas the inner `JobRadar/README.md` uses `DDS-Job-Market-Project/...`.

### 2.2 Subsystem Directory Breakdown

#### 1. Machine Learning Engine (`JobRadar/AI_ML/`)
- Contains two fully functional ML packages:
  - `Phase_5_Career_Recommendation/`: Resume parsing, skill gap analysis, and personalized roadmaps.
  - `Phase_6_Salary_Prediction/`: Data curation, preprocessing transformers, Ridge regression training pipeline, and calibrated prediction service.
- Contains placeholder scaffolding directories with explanatory `README.md` files:
  - `AI_ML/docs/README.md` (architecture records index)
  - `AI_ML/experiments/README.md` (experimental laboratory guidelines)
  - `AI_ML/models/README.md` (central model registry conventions)
  - `AI_ML/shared/README.md` (shared utility specifications)
  - `AI_ML/Phase_4_Job_Classification/README.md` (Phase 4 architecture description; actual Phase 4 code resides in `DDS-Job-Market-Project/src/job_market/classification.py`).

#### 2. Backend & Data Pipeline (`JobRadar/DDS-Job-Market-Project/`)
- Total file count: 24,453 files (24,211 files reside inside `.venv/`).
- `src/job_market/`: Clean modular Python package implementing database access, ingestion, cleaning, role classification, semantic matching, authentication, and REST API routing.
- `data/`: 1.11 GB total storage across raw datasets, processed CSVs, SQLite databases, external datasets, and snapshots.
- `docs/`: 43 markdown files covering architectural decisions, testing logs, and external dataset governance.
- `tests/`: 59 test files and fixture folders.

#### 3. Frontend Single Page Application (`JobRadar/Frontend/`)
- React 19 + Vite 8 + Tailwind CSS.
- `src/`: 33 JavaScript/JSX source files organized into `api/`, `components/`, `context/`, `data/`, and `pages/`.
- `node_modules/`: 144.7 MB across 13,468 files.
- `dist/`: 0.86 MB production bundle from prior build.

#### 4. Scratch & Temporary Directories (Antigravity Artifacts)
- **Root `scratch/`:** 5 scripts (`check_source.py`, `inspect_mock_learning.py`, `investigate_technical_scope.py`, `recalculate.py`, `test_hypotheses.py`).
- **Inner `JobRadar/scratch/`:** 2 scripts (`acceptance_test_runner.py`, `audit_stage_6_0.py`).
- **Backend `JobRadar/DDS-Job-Market-Project/scratch/`:** 7 scripts (`inspect_db_counts.py`, `inspect_routes.py`, `run_step3_api_test.py`, `run_step4_database_test.py`, `run_step8_live_e2e.py`, `run_steps_5_6_comprehensive.py`, `test_imports_steps5_6.py`).
- **Evidence:** None of these 14 scripts are imported by production code. They were created during development and validation stages as recorded in `PROJECT_CLEANUP_LOG.md`.

---

## 3. Duplicate and Unnecessary File Findings

A rigorous SHA-256 byte-level hash comparison was executed across the entire repository. The following confirmed duplicate, obsolete, and redundant files were identified:

### 3.1 Exact Byte-for-Byte Duplicate Files

| File 1 Relative Path | File 2 Relative Path | File Size | Hash / Evidence | Disposition |
|:---|:---|:---:|:---:|:---:|
| `JobRadar\AUTHENTICATION_AUDIT.md` | `JobRadar\DDS-Job-Market-Project\docs\AUTHENTICATION_AUDIT.md` | 12.5 KB | SHA-256 identical | Redundant copy in `JobRadar/`. Keep doc in `docs/`. |
| `JobRadar\AUTHENTICATION_IMPLEMENTATION_REPORT.md` | `JobRadar\DDS-Job-Market-Project\docs\AUTHENTICATION_IMPLEMENTATION_REPORT.md` | 13.3 KB | SHA-256 identical | Redundant copy in `JobRadar/`. Keep doc in `docs/`. |
| `JobRadar\AUTHENTICATION_SECURITY_REVIEW.md` | `JobRadar\DDS-Job-Market-Project\docs\AUTHENTICATION_SECURITY_REVIEW.md` | 14.7 KB | SHA-256 identical | Redundant copy in `JobRadar/`. Keep doc in `docs/`. |
| `JobRadar\DDS-Job-Market-Project\data\external\stackoverflow\raw\results.csv` | `JobRadar\DDS-Job-Market-Project\data\external\stackoverflow\raw\survey_results_public.csv` | **152.14 MB** | SHA-256 identical | **Critical Bloat:** 152 MB exact duplicate of StackOverflow survey. |
| `JobRadar\DDS-Job-Market-Project\data\external\stackoverflow\raw\schema.csv` | `JobRadar\DDS-Job-Market-Project\data\external\stackoverflow\raw\survey_results_schema.csv` | 12.5 KB | SHA-256 identical | Duplicate schema file. |
| `JobRadar\DDS-Job-Market-Project\data\external\duplicates_archive\role_radar_scraped_jobs_duplicate.json` | `JobRadar\DDS-Job-Market-Project\data\external\role_radar\raw\scraped_jobs.json` | 9.46 MB | SHA-256 identical | Duplicate archival copy. |
| `JobRadar\DDS-Job-Market-Project\tests\_role_annotation_output\first.csv` | `JobRadar\DDS-Job-Market-Project\tests\_role_annotation_output\second.csv` | 727 B | SHA-256 identical | Ephemeral test runner output left on disk. |
| `JobRadar\Frontend\dist\favicon.svg` | `JobRadar\Frontend\public\favicon.svg` | 9.5 KB | SHA-256 identical | Dist build asset vs public source asset. |

### 3.2 Near-Duplicate Files

| File 1 | File 2 | Size Difference | Content Comparison |
|:---|:---|:---:|:---|
| `README.md` (root) | `JobRadar/README.md` | 104 bytes | Content is 99% identical. The only difference is relative link paths (`JobRadar/DDS-Job-Market-Project/...` in root vs `DDS-Job-Market-Project/...` in inner). |

### 3.3 Obsolete and Quarantined Large Artifacts

1. **Obsolete Pre-Migration Database Backup:**
   - **Path:** `JobRadar\DDS-Job-Market-Project\data\backups\jobradar_pre_m4_pilot_20261110.db`
   - **Size:** **251.78 MB**
   - **Evidence:** This database was created on 2026-11-10 as a pre-pilot migration safety backup. It has 0 references in any code or tests (only mentioned once in `DEPLOYMENT_READINESS_CHECKLIST.md`).
2. **Quarantined Rejected Synthetic Dataset:**
   - **Path:** `JobRadar\DDS-Job-Market-Project\data\external\rejected\synthetic_itci_2026\indian_tech_career_intelligence_2026.csv`
   - **Size:** **56.60 MB**
   - **Evidence:** Documented in `EXTERNAL_DATASET_RISK_REGISTER.md` as permanently quarantined due to synthetic noise to prevent ML contamination. 0 code references.
3. **Orphaned Experimental Evaluation Dataset:**
   - **Path:** `JobRadar\DDS-Job-Market-Project\data\processed\expanded_skills_evaluation\job_skills.csv` (11.23 MB), `skill_extraction_audit.json` (1.2 KB), `skill_extraction_audit.md` (2.2 KB)
   - **Size:** 11.23 MB
   - **Evidence:** 0 references in production code or tests. The active production file is `JobRadar\DDS-Job-Market-Project\data\processed\job_skills.csv`.
4. **Test Output Directory Left on Disk:**
   - **Path:** `JobRadar\DDS-Job-Market-Project\tests\_role_annotation_output\` (9 files, ~4.5 KB)
   - **Evidence:** Created during execution of `tests/test_role_annotation.py` because the test does not use `tempfile.TemporaryDirectory()`.

---

## 4. Dependency Audit

### 4.1 Python Dependencies (`requirements.txt`)

Inspected file: `JobRadar/DDS-Job-Market-Project/requirements.txt` (12 declared dependencies).

| Declared Package | Specification | Codebase Usage Status | Referencing Modules |
|:---|:---:|:---:|:---|
| `pandas` | `>=2.2.0,<4.0.0` | **CONFIRMED USED** | `api.py`, `cleaning.py`, `historical_migration.py`, `curator.py`, `benchmark_extractor.py` |
| `openpyxl` | `>=3.1.5,<4.0.0` | **CONFIRMED USED** | Reads `indian-job-market-dataset-2025.xlsx` in `historical_migration.py` and `run_cleaning.py` |
| `fastapi` | `>=0.115.0,<1.0.0` | **CONFIRMED USED** | `api.py`, `auth_api.py`, `career_recommendations_api.py`, `salary_prediction_api.py` |
| `uvicorn` | `>=0.30.0,<1.0.0` | **CONFIRMED USED** | Production ASGI server runner |
| `SQLAlchemy` | `>=2.0.0,<3.0.0` | **CONFIRMED USED** | `database.py`, `models.py`, `historical_migration.py` |
| `scikit-learn` | `>=1.5.0,<2.0.0` | **CONFIRMED USED** | `classification.py`, `pipeline.py`, `trainer.py`, `metrics.py` |
| `joblib` | `>=1.3.0,<2.0.0` | **CONFIRMED USED** | Model serialization/deserialization across Phase 4 and Phase 6 |
| `numpy` | `>=1.26.0,<3.0.0` | **CONFIRMED USED** | `semantic_matching.py`, `pipeline.py`, `metrics.py` |
| `pydantic` | `>=2.7.0,<3.0.0` | **CONFIRMED USED** | Request/response validation schemas across all API endpoints |
| `python-multipart` | `>=0.0.9,<1.0.0` | **CONFIRMED USED** | Required by FastAPI for `UploadFile` resume uploads in `career_recommendations_api.py` |
| `pypdf` | `>=5.0.0,<8.0.0` | **CONFIRMED USED** | PDF resume parsing in `resume_extractor.py` |
| `python-docx` | `>=1.1.0,<2.0.0` | **CONFIRMED USED** | Word document resume parsing in `resume_extractor.py` |

#### Missing Python Dependencies in `requirements.txt`
1. **`matplotlib` (Missing Runtime Dependency):**
   - **Evidence:** `JobRadar/AI_ML/Phase_6_Salary_Prediction/visualizers/eda_plots.py` directly imports `matplotlib.pyplot` and `matplotlib`. It is installed in the local `.venv` (v3.11.2) but **omitted from `requirements.txt`**. Any developer attempting to run Phase 6 visualizations will encounter `ModuleNotFoundError: No module named 'matplotlib'`.
2. **`pytest` (Missing Development/Testing Dependency):**
   - **Evidence:** `INSTALLATION_GUIDE.md` explicitly instructs the developer to execute `pytest tests/ -v`. However, `pytest` is **not declared in `requirements.txt`**. A developer following the guide after a fresh `pip install -r requirements.txt` will receive `pytest: command not found`.
3. **`sentence-transformers` (Optional Fallback):**
   - **Evidence:** `semantic_matching.py` checks `importlib.util.find_spec("sentence_transformers")`. If absent, it gracefully falls back to TF-IDF cosine matching. Not required, but should be documented as optional.

#### Version Risk: Scikit-Learn Serialization Compatibility
- The serialized model `salary_predictor_v2.0.0_tech_only.joblib` was trained and pickled using `scikit-learn 1.9.1` in the author's virtual environment.
- When unpickled with `scikit-learn 1.9.0`, scikit-learn emits multiple `InconsistentVersionWarning` warnings.
- **Recommendation:** Pin or lock dependencies using `pip-tools` or `uv.lock` to ensure identical runtime environments.

---

### 4.2 JavaScript / Frontend Dependencies (`package.json`)

Inspected file: `JobRadar/Frontend/package.json`.

| Package | Version | Type | Usage Evidence in `Frontend/src` | Finding |
|:---|:---:|:---:|:---|:---:|
| `react` | `^19.2.8` | dependency | 30 source files | Essential |
| `react-dom` | `^19.2.8` | dependency | `main.jsx` | Essential |
| `react-router-dom` | `^7.18.4` | dependency | 16 source files | Essential |
| `lucide-react` | `^1.53.0` | dependency | 23 source files | Essential |
| `recharts` | `^3.10.1` | dependency | `DashboardPage.jsx`, `SkillsPage.jsx` | Essential |
| `canvas-confetti` | `^1.9.4` | dependency | `OnboardingPage.jsx`, `MindMapPage.jsx` | Essential |
| `clsx` | `^2.1.1` | dependency | **0 files in entire codebase** | **Unused Dependency** |
| `tailwind-merge` | `^3.7.0` | dependency | **0 files in entire codebase** | **Unused Dependency** |
| `vite` | `^8.3.0` | devDependency | Build tool | Essential |
| `@vitejs/plugin-react` | `^6.1.1` | devDependency | Vite React plugin | Essential |
| `tailwindcss` | `^3.4.19` | devDependency | Styling engine | Essential |
| `postcss` | `^8.5.29` | devDependency | CSS processing | Essential |
| `autoprefixer` | `^10.6.1` | devDependency | Vendor prefixes | Essential |
| `oxlint` | `^1.81.0` | devDependency | Fast JS linter | Essential |

- **Finding:** `clsx` and `tailwind-merge` are declared in `dependencies` but are never imported in any file in `Frontend/`. They are typical shadcn boilerplate artifacts that can be safely pruned.

---

## 5. Dataset and ML Artifact Inventory

Below is the complete inventory of all data assets, database files, and trained ML artifacts in the repository:

| Asset Relative Path | Size | Type | Provenance | Code References | Sharing Assessment |
|:---|:---:|:---:|:---|:---:|:---:|
| `DDS-Job-Market-Project/data/jobradar.db` | **254.0 MB** | SQLite DB | Aggregated production database (98,347 jobs, 216,977 skill links) | `database.py`, `independent_evaluation.py` | **KEEP** (Required for instant execution; requires Git LFS or external link due to 254 MB size) |
| `DDS-Job-Market-Project/data/processed/cleaned_indian_job_market_2025.csv` | **151.7 MB** | Golden CSV | 97,682 cleaned job records | 8 production modules | **KEEP** (Can be shared via LFS or regenerated from raw xlsx) |
| `DDS-Job-Market-Project/data/processed/job_skills.csv` | 10.95 MB | Processed CSV | Normalized job-to-skill relational table | 7 production modules | **KEEP** |
| `DDS-Job-Market-Project/data/processed/emerging_skills.json` | 42.5 KB | Processed JSON | Momentum analysis of rising technologies | `api.py` | **KEEP** |
| `DDS-Job-Market-Project/data/processed/emerging_skills.csv` | 10.0 KB | Processed CSV | Tabular emerging skills export | Diagnostic/doc | **KEEP BUT REVIEW** |
| `DDS-Job-Market-Project/data/raw/indian-job-market-dataset-2025.xlsx` | 30.24 MB | Raw Excel | Primary historical source dataset | `run_ingestion.py`, `historical_migration.py` | **KEEP** (Source of truth) |
| `DDS-Job-Market-Project/data/reference/role_taxonomy.json` | 3.97 KB | Config JSON | 11 canonical role families and keywords | `classification.py`, `semantic_matching.py` | **KEEP** (Essential) |
| `DDS-Job-Market-Project/data/models/role_classifier_baseline_v0.1.0.joblib` | 2.29 MB | ML Bundle | Phase 4 TF-IDF + Logistic Regression | `classification.py`, `api.py` | **KEEP** (Active classifier) |
| `AI_ML/Phase_5_Career_Recommendation/benchmarks/role_skill_benchmarks.json` | 179 KB | Config JSON | Empirical role skill frequencies & weights | `recommender.py`, `generator.py`, `analyzer.py` | **KEEP** (Essential for Phase 5) |
| `AI_ML/Phase_6_Salary_Prediction/models/artifacts/salary_predictor_v2.0.0_tech_only.joblib` | 4.47 KB | ML Pipeline | Phase 6 Ridge Regressor (Champion model) | `prediction_service.py`, `trainer.py` | **KEEP** (Active salary model) |
| `AI_ML/Phase_6_Salary_Prediction/models/artifacts/salary_model_metadata_v2.json` | 17.5 KB | Metadata JSON | Performance metrics, conformal intervals ($R^2=0.4608$) | `prediction_service.py` | **KEEP** |
| `AI_ML/Phase_6_Salary_Prediction/models/artifacts/salary_predictor_v1.0.0.joblib` | 4.05 MB | ML Pipeline | Phase 6 v1.0.0 Random Forest baseline | Fallback / comparison | **KEEP BUT REVIEW** |
| `AI_ML/Phase_6_Salary_Prediction/models/artifacts/model_comparison_v2.json` | 1.47 KB | Benchmark JSON | Algorithm comparison metrics | Docs / evaluation | **KEEP** |
| `AI_ML/Phase_6_Salary_Prediction/data/curated_technical_salary_data.csv` | 7.51 MB | Curated CSV | Filtered technical training records (16,043 rows) | `curator.py` | **REGENERATABLE** (Generated by curator) |
| `DDS-Job-Market-Project/data/backups/jobradar_pre_m4_pilot_20261110.db` | **251.8 MB** | Backup DB | Obsolete Nov 10 pre-pilot migration backup | 0 code references | **REMOVE CANDIDATE** |
| `DDS-Job-Market-Project/data/external/stackoverflow/raw/results.csv` | **152.1 MB** | Raw CSV | Duplicate of `survey_results_public.csv` | 0 code references | **REMOVE CANDIDATE** |
| `DDS-Job-Market-Project/data/external/stackoverflow/raw/survey_results_public.csv` | **152.1 MB** | Raw CSV | External Stack Overflow 2024 Developer Survey | Reference / evaluation | **KEEP BUT REVIEW** (Too large for git without LFS) |
| `DDS-Job-Market-Project/data/external/rejected/synthetic_itci_2026/...` | **56.6 MB** | Raw CSV | Synthetic ITCI dataset (quarantined) | 0 code references | **REMOVE CANDIDATE** |
| `DDS-Job-Market-Project/data/external/kaggle_tech_23k/raw/indian_tech_jobs_2026.csv` | 13.36 MB | Raw CSV | Kaggle 23k tech jobs dataset | Reference | **KEEP BUT REVIEW** |
| `DDS-Job-Market-Project/data/external/duplicates_archive/role_radar_scraped_jobs_duplicate.json` | 9.46 MB | Raw JSON | Duplicate of `role_radar/raw/scraped_jobs.json` | 0 code references | **REMOVE CANDIDATE** |
| `DDS-Job-Market-Project/data/external/role_radar/raw/scraped_jobs.json` | 9.46 MB | Raw JSON | Scraped jobs integration fixture | Reference | **KEEP BUT REVIEW** |
| `DDS-Job-Market-Project/data/external/github_innovation_graph/raw/languages.csv` | 5.87 MB | Raw CSV | GitHub language frequency trends | Reference | **KEEP BUT REVIEW** |
| `DDS-Job-Market-Project/data/external/fliar/raw/india_salary_benchmarks_2026_sample.csv` | 1.93 MB | Raw CSV | FLIAR Indian salary benchmarks | Reference | **KEEP BUT REVIEW** |
| `DDS-Job-Market-Project/data/external/jobspiq/benchmarks/skills-demand-india.csv` | 9.0 KB | Raw CSV | External skill demand benchmark | `benchmark_import.py` | **KEEP** |
| `DDS-Job-Market-Project/data/external/jobspiq/benchmarks/tech-salaries-stated-india.csv` | 2.6 KB | Raw CSV | External salary benchmark | `benchmark_import.py` | **KEEP** |
| `DDS-Job-Market-Project/data/processed/expanded_skills_evaluation/job_skills.csv` | 11.23 MB | Eval CSV | Orphaned evaluation experiment file | 0 code references | **REMOVE CANDIDATE** |
| `DDS-Job-Market-Project/data/auth_users.db` | 49.1 KB | SQLite DB | Local auth database with active dev/test sessions | `auth_api.py` | **SENSITIVE / REGENERATABLE** |
| `DDS-Job-Market-Project/data/snapshots/adzuna/*.json` (36 files) | 840 KB | JSON Cache | Cached Adzuna search API responses | Leaks `ADZUNA_APP_ID` | **SENSITIVE** |

### 5.1 Machine Learning Serialization Coupling Note
- **Technical Issue:** When `salary_predictor_v2.0.0_tech_only.joblib` is loaded via `joblib.load()`, it raises `ModuleNotFoundError: No module named 'features'`.
- **Root Cause:** The pipeline was pickled from within `JobRadar/AI_ML/Phase_6_Salary_Prediction/` where `features/` was on `sys.path` as a top-level package.
- **Current Workaround:** `prediction_service.py` monkey-patches `sys.modules["features"] = features` before unpickling.
- **Sharing Recommendation:** A recipient developer attempting to load the `.joblib` model independently in a standalone notebook or script will fail unless instructed to configure `sys.modules` or until the model is re-serialized with canonical absolute package paths (`Phase_6_Salary_Prediction.features.transformers`).

---

## 6. Security Findings

```
========================================================================================
CRITICAL SECURITY NOTICE: CREDENTIALS & PRIVACY LEAKAGE AUDIT
========================================================================================
```

### 6.1 Finding SEC-01: Live API Credentials in Plaintext `.env`
- **Severity:** **CRITICAL**
- **Location:** `JobRadar/DDS-Job-Market-Project/.env`
- **Evidence:** The file exists on disk and contains live, functional third-party API credentials:
  - `ADZUNA_APP_ID`: 8-character active application identifier (`a3***85`)
  - `ADZUNA_APP_KEY`: 32-character active secret key (`48***b9`)
- **Risk:** If this repository is zipped, copied, or pushed to GitHub, the developer's live Adzuna account and query quota will be compromised.
- **Action Required:** Remove this file from any sharing bundle. Ensure `.env.example` is used exclusively.

### 6.2 Finding SEC-02: Live API Key Leaked Across 36 Snapshot Files
- **Severity:** **HIGH**
- **Location:** `JobRadar/DDS-Job-Market-Project/data/snapshots/adzuna/*.json` (36 files)
- **Evidence:** Inspection of the Adzuna API response cache revealed that Adzuna embeds the client's App ID in its job redirect URLs:
  ```text
  "redirect_url": "https://www.adzuna.in/details/3821301570?utm_medium=api&utm_source=a3ae5385"
  ```
  Every single JSON snapshot contains `utm_source=<ADZUNA_APP_ID>`, exposing the App ID even if `.env` is deleted! Additionally, each job record contains an internal HMAC JWT token in `adref`.
- **Risk:** Silent credential leak via cached test fixture data.
- **Action Required:** Exclude `data/snapshots/adzuna/` from distribution, or sanitize the redirect URLs using a regex replacement script.

### 6.3 Finding SEC-03: Local Authentication Sessions in `auth_users.db`
- **Severity:** **MEDIUM**
- **Location:** `JobRadar/DDS-Job-Market-Project/data/auth_users.db`
- **Evidence:** The database contains 9 registered user accounts (including demo user `aarav_ds` and test accounts like `tester_1794485695880`) and **42 active session tokens** in the `sessions` table.
- **Risk:** Distributing active session tokens and user records created during test runs.
- **Action Required:** Do not include `auth_users.db`. `auth_api.py` automatically initializes a clean database and seeds the default demo account on first startup.

### 6.4 Finding SEC-04: Git Ignore Configuration Blind Spots
- **Severity:** **HIGH**
- **Evidence:**
  1. There is **no `.git` repository** currently initialized anywhere in the project.
  2. There is **no `.gitignore` file at the workspace root**.
  3. The existing inner `JobRadar/.gitignore` contains rules for `.env`, `Frontend/node_modules/`, and `DDS-Job-Market-Project/data/raw/`, but:
     - It does **NOT** ignore `.db` files (`jobradar.db`, `jobradar_pre_m4_pilot_20261110.db`, `auth_users.db`).
     - It does **NOT** ignore `data/snapshots/`.
     - It does **NOT** ignore large external datasets (`results.csv`, `survey_results_public.csv`, `synthetic_itci_2026`).
- **Risk:** The moment another developer runs `git init` and `git add .`, over 850 MB of binary databases and CSVs (including multiple files exceeding GitHub's 100 MB hard limit) plus live API credentials in snapshots will be staged.

---

## 7. Application Readiness & Reproducibility Assessment

### 7.1 Backend Readiness (`DDS-Job-Market-Project`)
- **FastAPI Endpoint Coverage:** Complete. All endpoints respond correctly to HTTP queries (health, classification, taxonomy, skills, jobs, auth, career recommendations, and salary prediction).
- **Database Connection:** Resilient. `DEFAULT_DATABASE_URL` uses dynamic path resolution relative to `PROJECT_ROOT`, meaning SQLite connects seamlessly regardless of absolute machine path.
- **Test Suite Status:** 265 / 265 unit tests pass via `unittest`.

#### Developer Onboarding Friction Points (Backend):
1. **Import Error on Documented Start Command:**
   - `INSTALLATION_GUIDE.md` instructs:
     ```bash
     cd DDS-Job-Market-Project
     uvicorn job_market.api:app --host 127.0.0.1 --port 8000 --reload
     ```
   - **Tested Result:** Fails immediately with:
     ```text
     ModuleNotFoundError: No module named 'job_market'
     ```
   - **Cause:** `src/` is not on `sys.path` by default unless `PYTHONPATH=src` is defined, or a `pyproject.toml` installs the package in editable mode (`pip install -e .`).
2. **Missing `pytest` and `matplotlib` in `requirements.txt`:**
   - Fresh installation following the guide will fail when running tests or visualization scripts.

---

### 7.2 Frontend Readiness (`Frontend`)
- **Vite 8 + React 19:** Compiles with 0 build errors.
- **API Client:** `src/api/client.js` has robust fallback logic: connects to `import.meta.env.VITE_API_URL` or defaults to `http://127.0.0.1:8000`.
- **Mock Fallback Resilience:** If the backend is offline, the frontend falls back gracefully to `mockJobs.js`, `mockAnalytics.js`, and `mockLearning.js`.
- **Test Suite Status:** Both `test_authentication_suite.mjs` (14 tests) and `test_frontend_step7.mjs` (29 tests) pass with 100% success.
- **Production Asset Build:** `dist/` builds cleanly into 854 KB JS and 40 KB CSS.

---

## 8. Master File & Folder Sharing Assessment

Every relevant directory and file group in the workspace is classified below into one of six standard sharing categories:

```
[KEEP]             Essential production code, documentation, configuration, or required models.
[KEEP BUT REVIEW]  Non-critical reference files, evaluation docs, or comparison baselines.
[REMOVE CANDIDATE] Confirmed redundant, duplicate, obsolete, or rejected files.
[REGENERATABLE]    Build outputs, caches, or environments recreated with standard commands.
[SENSITIVE]        Contains credentials, tokens, or private data; MUST NOT BE SHARED.
[MISSING]          Required configuration or packaging files that are currently absent.
```

| Path | Size / Count | Category | Audit Evidence & Rationale |
|:---|:---:|:---:|:---|
| **Root Workspace Items** | | | |
| `JobRadar/` (Inner directory) | Full project | **KEEP** | Core project source code and assets. |
| `README.md` (Root) | 11.5 KB | **KEEP BUT REVIEW** | Reconcile with inner `JobRadar/README.md` to avoid duplicate maintenance. |
| `.pytest_cache/` | 4 files | **REGENERATABLE** | Ephemeral pytest cache. Exclude from sharing. |
| `scratch/` (Root) | 5 files (12 KB) | **KEEP BUT REVIEW** | Non-production scratch scripts. Move to an archive or exclude. |
| Root `.gitignore` | Absent | **MISSING** | **Must be added** to prevent committing `.venv`, `.env`, and large DB files. |
| **Inner Root (`JobRadar/`)** | | | |
| `JobRadar/.gitignore` | 554 B | **KEEP BUT REVIEW** | Needs expansion to cover large DBs and snapshots. |
| `JobRadar/README.md` | 11.4 KB | **KEEP** | Primary project documentation. |
| `JobRadar/AUTHENTICATION_*.md` (3 files) | 40.5 KB | **REMOVE CANDIDATE** | Byte-for-byte duplicates of files in `DDS-Job-Market-Project/docs/`. |
| `JobRadar/scratch/` (2 files) | 20 KB | **KEEP BUT REVIEW** | One-off audit scripts (`acceptance_test_runner.py`). |
| **Backend Source & Config** | | | |
| `DDS-Job-Market-Project/src/` | 50 files (0.87 MB) | **KEEP** | Essential backend source code. |
| `DDS-Job-Market-Project/requirements.txt` | 328 B | **KEEP BUT REVIEW** | Essential; needs addition of `pytest` and `matplotlib`. |
| `DDS-Job-Market-Project/pyproject.toml` | Absent | **MISSING** | **Must be added** to solve `job_market` import path resolution. |
| `DDS-Job-Market-Project/.env` | 71 B | **SENSITIVE** | **CRITICAL:** Contains live Adzuna API keys. Must be excluded. |
| `DDS-Job-Market-Project/.env.example` | 391 B | **KEEP** | Safe configuration template. |
| `DDS-Job-Market-Project/.venv/` | 24,211 files (610.8 MB) | **REGENERATABLE** | Local Python virtual environment. Exclude from sharing. |
| `DDS-Job-Market-Project/docs/` | 43 files (0.46 MB) | **KEEP** | Comprehensive architecture, testing, and governance documentation. |
| `DDS-Job-Market-Project/tests/` | 50 test files | **KEEP** | Core unit and integration test suite. |
| `DDS-Job-Market-Project/tests/_role_annotation_output/` | 9 files | **REGENERATABLE** | Test artifacts left on disk by `test_role_annotation.py`. |
| `DDS-Job-Market-Project/scratch/` | 7 files (133 KB) | **KEEP BUT REVIEW** | Permanent verification test harnesses (e.g. `run_step8_live_e2e.py`). |
| **Data & Artifacts** | | | |
| `.../data/jobradar.db` | 254.0 MB | **KEEP** | Core production SQLite database. Share via Git LFS or external link. |
| `.../data/auth_users.db` | 49.1 KB | **SENSITIVE / REGENERATABLE** | Contains test sessions. Exclude; auto-created on startup. |
| `.../data/snapshots/adzuna/` | 36 files (840 KB) | **SENSITIVE** | Leaks `ADZUNA_APP_ID` in redirect URLs. Exclude or sanitize. |
| `.../data/raw/indian-job-market-dataset-2025.xlsx` | 30.24 MB | **KEEP** | Source of truth dataset. |
| `.../data/processed/cleaned_indian_job_market_2025.csv` | 151.72 MB | **KEEP** | Cleaned dataset. Share via LFS or regenerate. |
| `.../data/processed/job_skills.csv` | 10.95 MB | **KEEP** | Processed skills dataset. |
| `.../data/processed/emerging_skills.json` | 42.5 KB | **KEEP** | Emerging skills momentum data. |
| `.../data/reference/role_taxonomy.json` | 3.97 KB | **KEEP** | Role taxonomy configuration. |
| `.../data/models/role_classifier_baseline_v0.1.0.joblib` | 2.29 MB | **KEEP** | Phase 4 trained classifier bundle. |
| `.../data/backups/jobradar_pre_m4_pilot_20261110.db` | **251.78 MB** | **REMOVE CANDIDATE** | Obsolete pre-migration backup database. |
| `.../data/external/stackoverflow/raw/results.csv` | **152.14 MB** | **REMOVE CANDIDATE** | Exact duplicate of `survey_results_public.csv`. |
| `.../data/external/stackoverflow/raw/survey_results_public.csv` | 152.14 MB | **KEEP BUT REVIEW** | External reference survey. Exclude or LFS. |
| `.../data/external/rejected/synthetic_itci_2026/...` | **56.60 MB** | **REMOVE CANDIDATE** | Quarantined rejected synthetic dataset. |
| `.../data/external/duplicates_archive/...` | **9.46 MB** | **REMOVE CANDIDATE** | Duplicate copy of `role_radar/raw/scraped_jobs.json`. |
| `.../data/processed/expanded_skills_evaluation/...` | **11.23 MB** | **REMOVE CANDIDATE** | Unreferenced experimental evaluation artifacts. |
| `.../data/external/kaggle_tech_23k/...` | 13.36 MB | **KEEP BUT REVIEW** | Reference benchmarking dataset. |
| `.../data/external/github_innovation_graph/...` | 5.87 MB | **KEEP BUT REVIEW** | Reference benchmarking dataset. |
| `.../data/external/fliar/...` | 1.93 MB | **KEEP BUT REVIEW** | Reference benchmarking dataset. |
| `.../data/external/jobspiq/...` | 11.6 KB | **KEEP** | Benchmarks imported by `benchmark_import.py`. |
| **AI / ML Engine (`JobRadar/AI_ML`)** | | | |
| `AI_ML/Phase_5_Career_Recommendation/` | Full package | **KEEP** | Essential career recommendation and resume parsing engine. |
| `AI_ML/Phase_6_Salary_Prediction/` | Full package | **KEEP** | Essential salary prediction engine and pipelines. |
| `AI_ML/Phase_6_Salary_Prediction/.../salary_predictor_v2.0.0_tech_only.joblib` | 4.47 KB | **KEEP** | Active champion salary prediction model. |
| `AI_ML/Phase_6_Salary_Prediction/.../salary_predictor_v1.0.0.joblib` | 4.05 MB | **KEEP BUT REVIEW** | Baseline model; can be retained for comparison. |
| `AI_ML/Phase_6_Salary_Prediction/data/curated_technical_salary_data.csv` | 7.51 MB | **REGENERATABLE** | Curated training data generated by `curator.py`. |
| `AI_ML/Phase_6_Salary_Prediction/visualizers/output/*.png` | 6 plots (1.5 MB) | **KEEP BUT REVIEW** | Visual EDA and residual plots. |
| `AI_ML/docs/`, `experiments/`, `models/`, `shared/` | 5 READMEs | **KEEP** | Architectural specifications and future roadmap docs. |
| **Frontend Application (`JobRadar/Frontend`)** | | | |
| `Frontend/src/` | 33 source files | **KEEP** | Essential React frontend source code. |
| `Frontend/package.json` | 863 B | **KEEP BUT REVIEW** | Essential; remove unused `clsx` and `tailwind-merge`. |
| `Frontend/package-lock.json` | 94.4 KB | **KEEP** | npm lockfile ensuring deterministic package installs. |
| `Frontend/node_modules/` | 13,468 files (144.7 MB) | **REGENERATABLE** | npm dependencies. Exclude from sharing. |
| `Frontend/dist/` | 4 files (0.86 MB) | **REGENERATABLE** | Vite production build output. Exclude from sharing. |
| `Frontend/.env.example` | 175 B | **KEEP** | Frontend environment template (`VITE_API_URL`). |
| `Frontend/test_*.mjs` (2 files) | 22.6 KB | **KEEP** | Frontend automated verification test suites. |

---

## 9. Sharing-Readiness Checklist

| Dimension | Item | Current Status | Remediation Required Before Sharing |
|:---:|:---|:---:|:---|
| 🔐 **Security** | Omit live `.env` file | ❌ **FAIL** | Delete or quarantine `.env` from the sharing bundle. |
| 🔐 **Security** | Scrub Adzuna snapshots | ❌ **FAIL** | Exclude `data/snapshots/adzuna/` (leaks App ID in redirect URLs). |
| 🔐 **Security** | Reset local auth database | ⚠️ **WARN** | Exclude `auth_users.db` (backend regenerates it automatically on start). |
| 📦 **Storage** | Exclude virtual environments | ⚠️ **WARN** | Ensure `.venv` (610 MB) and `node_modules` (145 MB) are not zipped. |
| 📦 **Storage** | Prune confirmed duplicate files | ⚠️ **WARN** | Remove `results.csv` (152 MB duplicate) and duplicate archives (~10 MB). |
| 📦 **Storage** | Remove obsolete backup DB | ⚠️ **WARN** | Delete `jobradar_pre_m4_pilot_20261110.db` (252 MB obsolete backup). |
| 📦 **Storage** | Isolate rejected datasets | ⚠️ **WARN** | Exclude `synthetic_itci_2026` (57 MB quarantined synthetic data). |
| ⚙️ **Config** | Root `.gitignore` | ❌ **FAIL** | Create a root `.gitignore` covering `.venv`, `.env`, `.db`, and `node_modules`. |
| ⚙️ **Packaging** | Python package installation | ❌ **FAIL** | Add `pyproject.toml` or update instructions to set `PYTHONPATH=src`. |
| ⚙️ **Packaging** | Complete `requirements.txt` | ❌ **FAIL** | Add `pytest` and `matplotlib` to `requirements.txt`. |
| ⚙️ **Frontend** | Clean `package.json` | ⚠️ **WARN** | Remove unused dependencies (`clsx`, `tailwind-merge`). |
| 📖 **Docs** | Fix onboarding setup guide | ❌ **FAIL** | Update `INSTALLATION_GUIDE.md` commands so `uvicorn` and `pytest` work out of the box. |
| 📖 **Docs** | Remove duplicate root docs | ⚠️ **WARN** | Delete redundant `JobRadar/AUTHENTICATION_*.md` files. |

---

## 10. Prioritized Cleanup Recommendations

To prepare JobRadar for clean, secure, and reproducible sharing, execute the cleanup in the following order:

### Phase 1: Immediate Security & Privacy Quarantine (CRITICAL — DO FIRST)
1. **Quarantine `.env`:** Ensure `JobRadar/DDS-Job-Market-Project/.env` is never committed to Git or bundled into a zip archive.
2. **Exclude or Sanitize Adzuna Snapshots:** Delete or exclude `JobRadar/DDS-Job-Market-Project/data/snapshots/adzuna/` from the distribution bundle to prevent leakage of the Adzuna App ID.
3. **Exclude `auth_users.db`:** Do not share `data/auth_users.db`. The application automatically re-creates the database schema and seeds the default demo account on first run.

### Phase 2: High-Yield Storage De-bloating (Reclaims ~480 MB)
Execute the following safe deletions (confirmed 0 production code impact):
1. **Delete Obsolete Backup Database:**
   - Remove `JobRadar/DDS-Job-Market-Project/data/backups/jobradar_pre_m4_pilot_20261110.db` (**Reclaims 251.78 MB**).
2. **Delete Exact Duplicate StackOverflow CSV:**
   - Remove `JobRadar/DDS-Job-Market-Project/data/external/stackoverflow/raw/results.csv` (**Reclaims 152.14 MB**; identical to `survey_results_public.csv`).
   - Remove `...data/external/stackoverflow/raw/schema.csv` (identical to `survey_results_schema.csv`).
3. **Delete Quarantined Synthetic Dataset:**
   - Remove `JobRadar/DDS-Job-Market-Project/data/external/rejected/synthetic_itci_2026/` (**Reclaims 56.60 MB**).
4. **Delete Duplicate Scraped Jobs Archive:**
   - Remove `JobRadar/DDS-Job-Market-Project/data/external/duplicates_archive/` (**Reclaims 9.46 MB**).
5. **Delete Orphaned Evaluation Artifact:**
   - Remove `JobRadar/DDS-Job-Market-Project/data/processed/expanded_skills_evaluation/` (**Reclaims 11.23 MB**).
6. **Clean Test Runner Output:**
   - Remove generated test CSVs in `JobRadar/DDS-Job-Market-Project/tests/_role_annotation_output/`.

*Total physical data reclaimed:* **~481.2 MB**.

### Phase 3: Developer Experience & Packaging Fixes
1. **Resolve Python Import Resolution:**
   - Add a minimal `pyproject.toml` to `JobRadar/DDS-Job-Market-Project/` so developers can run `pip install -e .`, allowing `uvicorn job_market.api:app` and `pytest` to resolve `job_market` without manual `PYTHONPATH` exports.
2. **Update `requirements.txt`:**
   - Add `matplotlib>=3.8.0` and `pytest>=8.0.0` to `JobRadar/DDS-Job-Market-Project/requirements.txt`.
3. **Prune Unused Frontend Dependencies:**
   - Remove `clsx` and `tailwind-merge` from `JobRadar/Frontend/package.json`.
4. **Remove Duplicate Documentation:**
   - Delete the 3 redundant authentication reports from the inner `JobRadar/` root (`AUTHENTICATION_AUDIT.md`, `AUTHENTICATION_IMPLEMENTATION_REPORT.md`, `AUTHENTICATION_SECURITY_REVIEW.md`), leaving the canonical copies in `DDS-Job-Market-Project/docs/`.
5. **Consolidate Workspace Layout:**
   - Provide clear instructions in the root `README.md` clarifying the workspace folder hierarchy, or hoist the inner `JobRadar/` contents to the root workspace if restructuring is desired.

### Phase 4: Git Setup & Version Control Strategy
1. **Create Root `.gitignore`:**
   - Establish a comprehensive `.gitignore` at the workspace root covering `.venv/`, `node_modules/`, `dist/`, `.env`, `*.db`, `__pycache__/`, `.pytest_cache/`, and large datasets.
2. **Handling Large Production Datasets (`jobradar.db`, `cleaned_indian_job_market_2025.csv`):**
   - Because `jobradar.db` (254 MB) and `cleaned_indian_job_market_2025.csv` (151 MB) exceed GitHub's 100 MB hard limit, configure **Git LFS** (`git lfs track "*.db" "*.csv"`) or provide an automated download script / cloud storage link in `INSTALLATION_GUIDE.md`.

---

## 11. Final Readiness Verdict

```text
========================================================================================
FINAL SHARING VERDICT: NOT READY FOR IMMEDIATE SHARING (BLOCKED)
========================================================================================
REASONS:
  1. [SECURITY BLOCKER] Live Adzuna API credentials exposed in .env and 36 snapshot files.
  2. [SECURITY BLOCKER] Local auth database contains active developer session tokens.
  3. [ONBOARDING BLOCKER] uvicorn start command fails out of the box without PYTHONPATH.
  4. [ONBOARDING BLOCKER] pytest and matplotlib missing from requirements.txt.
  5. [STORAGE BLOCKER] Over 480 MB of unneeded duplicate/obsolete data; 4 files exceed 100 MB GitHub limit.

READINESS AFTER RECOMMENDED SANITIZATION:
  Once Phase 1 (Security Quarantine) and Phase 2 (De-bloating) are executed and 
  packaging fixes (Phase 3) are applied, JobRadar will achieve 100% PRODUCTION READY 
  and SHARING READY status.
========================================================================================
```

---
*Report completed in read-only audit mode. No repository modifications have been made. Awaiting user approval before proceeding with cleanup actions.*
