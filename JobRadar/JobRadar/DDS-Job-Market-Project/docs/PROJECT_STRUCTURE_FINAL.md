# JobRadar — Final Project Structure & Architectural Inventory

**Document ID:** `JR-STRUCT-FINAL-P7.6`  
**Execution Date:** 2026-11-12  
**Auditor:** Senior Software Architect  
**Scope:** Complete repository directory layout, component roles, and data boundaries

---

## 1. High-Level Architectural Layout

```text
JobRadar/
├── AI_ML/                            # Core Machine Learning & Data Science Subsystems
│   ├── Phase_4_Job_Classification/   # TF-IDF + Logistic Regression Role Classifier
│   ├── Phase_5_Career_Recommendation/# Cosine Similarity Recommender, Skill Gap & Roadmap
│   ├── Phase_6_Salary_Prediction/    # Conformal Ridge Regression Salary Predictor
│   └── shared/                       # Shared ML evaluation utilities & schemas
│
├── DDS-Job-Market-Project/           # Backend Application, Data Pipeline & Testing
│   ├── .env.example                  # Template configuration for backend environment
│   ├── requirements.txt              # Reconciled Python production dependencies
│   ├── data/                         # SQLite databases, raw datasets, processed files
│   │   ├── jobradar.db               # Primary SQLite database (266 MB, 98,347 jobs)
│   │   ├── backups/                  # Historical pre-migration backups
│   │   ├── external/                 # External datasets (Kaggle 23k, Stack Overflow, GitHub)
│   │   ├── models/                   # Phase 4 classifier bundle artifact (2.4 MB)
│   │   ├── processed/                # Cleaned golden dataset (97,682 rows) & skills CSV
│   │   └── reference/                # Canonical skill aliases (115) & categories (30)
│   ├── docs/                         # Comprehensive engineering documentation
│   │   ├── data/                     # External dataset inventories & closure reports
│   │   ├── integration/              # Phase 7 integration documentation
│   │   └── testing/                  # All Phase 7.5 test reports & machine-readable JSON logs
│   ├── scratch/                      # Permanent verification test harnesses (Steps 3–8)
│   ├── src/job_market/               # FastAPI backend source modules (24 Python files)
│   │   ├── adzuna_client.py          # Adzuna API client with credential masking
│   │   ├── api.py                    # Main FastAPI app, DataStore, and 21 endpoints
│   │   ├── career_recommendations_api.py # Phase 5 recommendations & resume router
│   │   ├── classification.py         # Phase 4 classifier inference & rule fallback
│   │   ├── cleaning.py               # Text, location, experience, and salary parsing
│   │   ├── database.py               # SQLAlchemy engine & session factory
│   │   ├── emerging.py               # Hiring momentum index & tier calculation
│   │   ├── models.py                 # SQLAlchemy ORM models (Jobs, Skills, Sources)
│   │   ├── salary_prediction_api.py  # Phase 6 salary predictor router
│   │   └── skills.py                 # Skill normalization & alias extraction
│   └── tests/                        # 316 automated unit & integration test suites
│
└── Frontend/                         # React 19 + Vite 8 Single Page Application
    ├── .env.example                  # Template configuration for frontend API host
    ├── package.json                  # Frontend dependencies (React, Recharts, Tailwind)
    ├── vite.config.js                # Vite build & plugin configuration
    ├── dist/                         # Production compiled bundle (HTML, CSS, JS)
    └── src/                          # Application source code
        ├── api/                      # Centralized API client (`client.js`) & services
        ├── components/               # Domain-specific UI widgets (salary, jobs, mindmap)
        ├── context/                  # AuthContext and ToastContext state providers
        └── pages/                    # 10 route page views (Dashboard, Jobs, Skills, etc.)
```

---

## 2. Directory Breakdown & Subsystem Roles

### 2.1 Backend Source Modules (`DDS-Job-Market-Project/src/job_market/`)
| Module Name | File Size | Primary Responsibilities |
|:---|:---:|:---|
| `api.py` | 36 kB | Central FastAPI entrypoint. Implements `DataStore` in-memory caching for 97,682 jobs, registers CORS middleware, handles global exceptions, and serves core analytics and search routes. |
| `database.py` | 12 kB | SQLAlchemy engine creation, database initialization, session factory dependency, and deterministic migration key generator (`build_migration_key`). |
| `models.py` | 14 kB | Declarative ORM models: `Job`, `Skill`, `JobSkill`, `Source`, `IngestionRun`, `RawSnapshot`, `JobVersion`, `ExternalSkillBenchmark`. |
| `cleaning.py` | 15 kB | Text normalization (HTML stripping, entity decoding), location standardization, experience bracket parsing, and salary status categorization. |
| `skills.py` | 18 kB | Bidirectional skill alias lookup (115 rules), skill normalization, regex pattern extraction from job descriptions, and category mapping. |
| `emerging.py` | 11 kB | Computes cross-sectional Hiring Momentum Index combining hiring growth, wage premiums, and upload recency into three canonical tiers. |
| `adzuna_client.py` | 9 kB | External API crawler client with automatic credential masking (`%2A%2A%2A`) in logging and request URLs. |
| `classification.py`| 19 kB | Phase 4 ML classifier loader (`role_classifier_baseline_v0.1.0.joblib`), text feature synthesis (`JobTextFeatures`), confidence tiering, and keyword rule fallback. |
| `career_recommendations_api.py` | 18 kB | FastAPI router mounting `/api/recommendations/career`, `/api/skills/gap`, `/api/roadmap/generate`, `/api/recommendations/roles`, and `/api/resume/extract-skills`. |
| `salary_prediction_api.py` | 9 kB | FastAPI router mounting `/api/salary/predict` and `/api/salary/metadata`, enforcing non-technical role rejection and conformal interval formatting. |

### 2.2 Machine Learning Packages (`AI_ML/`)
| Directory | Target Domain | Key Artifacts & Responsibilities |
|:---|:---|:---|
| `Phase_4_Job_Classification/` | Automated Job Classification | Trains and evaluates multi-class TF-IDF + Logistic Regression models across 11 canonical role families. Contains provisional training pipelines. |
| `Phase_5_Career_Recommendation/`| Career Intelligence | Contains `benchmarks/role_skill_benchmarks.json` (8 canonical roles), cosine similarity matching engine, skill-gap diagnostic algorithms, and in-memory resume parsers. |
| `Phase_6_Salary_Prediction/` | Conformal Salary Prediction | Contains champion artifact `salary_predictor_v2.0.0_tech_only.joblib` (Ridge Regression $\alpha=10.0$), 90% conformal uncertainty calibrator, and GroupKFold evaluation suites. |

### 2.3 Frontend Application (`Frontend/src/`)
| Subdirectory | Component Role | Key Files |
|:---|:---|:---|
| `api/` | Centralized Network Layer | `client.js` (universal fetch wrapper with 15s timeout), `analytics.js`, `jobs.js`, `skills.js`, `salary.js`, `recommendations.js`, `auth.js`. |
| `components/` | Reusable UI Modules | `salary/SalaryPredictorWidget.jsx`, `jobs/JobCard.jsx`, `jobs/JobFilterBar.jsx`, `mindmap/InteractiveMindMap.jsx`, `common/ChartCard.jsx`, `common/KpiCard.jsx`. |
| `pages/` | Primary Views | `DashboardPage.jsx`, `JobsPage.jsx`, `SkillsPage.jsx`, `SkillGapPage.jsx`, `MindMapPage.jsx`, `OnboardingPage.jsx`, `ProfilePage.jsx`. |
| `context/` | Global State | `AuthContext.jsx` (session persistence), `ToastContext.jsx` (user notification alerts). |

---

## 3. Data & Artifact Storage Boundaries

### 3.1 Primary Datasets
- **`data/jobradar.db` (266 MB):** Permanent SQLite database containing 98,347 physical job postings, 216,977 relational skill mappings, and multi-run ingestion snapshot records. Accessed strictly in read-only mode (`?mode=ro`).
- **`data/processed/cleaned_indian_job_market_2025.csv` (159 MB):** The golden deduplicated dataset containing exactly **97,682 rows** and 34 standardized columns.
- **`data/processed/job_skills.csv` (11.5 MB):** Pre-computed normalized skill-to-jobId relational mapping.
- **`data/processed/emerging_skills.json` (42 kB):** 104 pre-calculated emerging skills ranked by hiring momentum.

### 3.2 Reference Data
- **`data/reference/skill_aliases.json` (6.2 kB):** 115 standardized technical alias rules (`k8s` $\to$ `Kubernetes`, `react.js` $\to$ `React`, `aws` $\to$ `AWS`).
- **`data/reference/skill_categories.json` (2.4 kB):** 30 functional skill domains mapped to top-level UI presentation groups.

---

## 4. Verification

This structural inventory reflects the verified layout of the JobRadar repository at the conclusion of Phase 7.6.
