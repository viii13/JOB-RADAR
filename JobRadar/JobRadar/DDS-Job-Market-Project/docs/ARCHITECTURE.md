# JobRadar — Full-Stack System Architecture Documentation

**Document ID:** `JR-ARCH-SYSTEM-P7.6`  
**Execution Date:** 2026-11-12  
**Architect:** Senior Software Architect & ML Systems Engineer  
**System Architecture:** Decoupled React Frontend + FastAPI Backend + SQLite Storage + MLOps Pipelines

---

## 1. High-Level System Architecture

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        REACT FRONTEND (Vite 8)                         │
│  DashboardPage │ JobsPage │ SkillsPage │ SkillGapPage │ SalaryWidget   │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │ JSON / HTTP REST
                                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│                    CENTRALIZED CLIENT (client.js)                      │
│      Timeout Abort (15s) │ Error Unrolling │ FormData Headers          │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │ Network Boundary
                                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        FASTAPI BACKEND (Python)                        │
│   CORS Middleware │ Global Exception Handler │ Pydantic Schemas        │
│                                                                        │
│   ┌───────────────────────────┐    ┌───────────────────────────────┐   │
│   │    IN-MEMORY DATASTORE    │    │        API ROUTERS            │   │
│   │ 97,682 Cleaned Postings   │◄───┤ • Analytics & Overview        │   │
│   │ Fast In-Memory Filtering  │    │ • Jobs Search & Filters       │   │
│   │ Precomputed Top Skills    │    │ • Skills & Emerging Momentum  │   │
│   └───────────────────────────┘    │ • ML Role Classification      │   │
│                                    │ • Career Recommendations      │   │
│                                    │ • Salary Prediction           │   │
│                                    └──────────────┬────────────────┘   │
└───────────────────────────────────────────────────┼────────────────────┘
                                                    │
            ┌───────────────────────────────────────┼──────────────────────────────────────┐
            │                                       │                                      │
            ▼                                       ▼                                      ▼
┌────────────────────────┐              ┌────────────────────────┐             ┌────────────────────────┐
│     SQLITE STORAGE     │              │    MACHINE LEARNING    │             │   IN-MEMORY RESUME     │
│   data/jobradar.db     │              │   • Phase 4 Classifier │             │        PARSER          │
│ • jobs (98,347 rows)   │              │   • Phase 5 Knowledge  │             │ • pypdf (PDF stream)   │
│ • skills (120 rows)    │              │   • Phase 6 Conformal  │             │ • python-docx (DOCX)   │
│ • job_skills (216,977) │              │     Salary Predictor   │             │ • 0 disk persistence   │
└────────────────────────┘              └────────────────────────┘             └────────────────────────┘
```

---

## 2. Frontend Architecture (React 19 + Vite 8)

### 2.1 Component & View Hierarchy
The presentation layer is built as a Single Page Application (SPA) using React 19, Vite 8, and Tailwind CSS:
- **Routing:** Handled client-side by `react-router-dom` v7 with 10 primary pages:
  - `/` $\to$ `DashboardPage`: Macro KPIs, salary distribution, role demand share, and hiring trends.
  - `/jobs` $\to$ `JobsPage`: Searchable, filterable catalog of 97,679 jobs with pagination and modal views.
  - `/skills` $\to$ `SkillsPage`: In-demand technical skills and emerging momentum rankings.
  - `/skill-gap` $\to$ `SkillGapPage`: Role-specific differential skill coverage and readiness scoring.
  - `/mindmap` $\to$ `MindMapPage`: Interactive skill ontology and branching learning mind maps.
  - `/onboarding` $\to$ `OnboardingPage`: Step-by-step career path questionnaire and profile setup.
  - `/profile` $\to$ `ProfilePage`: User technical competency profile and saved bookmarks.
- **Charts:** Powered by `recharts` v3 using responsive SVG wrappers (`ResponsiveContainer`, `BarChart`, `AreaChart`, `PieChart`).

### 2.2 Centralized API Client Architecture ([`src/api/client.js`](file:///c:/Users/aakas/OneDrive/Documents/Semester%203/Data%20Analysis%20using%20Python/Project%20Ds/JobRadar/JobRadar/Frontend/src/api/client.js))
All network communications pass through a unified client:
- **Environment Targeting:** Automatically reads `import.meta.env.VITE_API_URL` or defaults to `http://127.0.0.1:8000`.
- **Request Lifecycle:**
  1. Instantiates `AbortController` with a 15-second timer.
  2. Dynamically applies `Content-Type: application/json` for plain objects, while omitting it for `FormData` to allow native browser multipart boundary generation.
  3. Evaluates HTTP response status; if non-OK, parses error JSON and throws an `ApiError` instance containing numeric status and unrolled detail strings.
  4. Clears timer upon resolution.

---

## 3. Backend Architecture (FastAPI + ASGI)

### 3.1 Application Lifecycle & DataStore
At startup, FastAPI initializes `DataStore` in process memory:
- **Dataset Pre-Loading:** Reads `cleaned_indian_job_market_2025.csv` (97,682 rows) and `job_skills.csv` (216,977 mappings).
- **Indexing:** Builds hash maps for $O(1)$ skill lookups:
  - `job_skills_map`: Maps `jobId` $\to$ list of normalized skills.
  - `skill_to_jobs_map`: Maps lowercase normalized skill $\to$ set of matching `jobId` strings.
- **Search Masking:** Applies vectorized boolean pandas masks for multi-parameter filtering (keyword, location, salary, experience, work type) with sub-10ms response times.

### 3.2 Database Layer (SQLAlchemy 2.x + SQLite)
- **Primary Database:** `data/jobradar.db` (266 MB).
- **Concurrency & Protection:** Accessed strictly in read-only mode (`?mode=ro`) during analytical and API queries, preventing write locks and database mutation.
- **Session Lifecycle:** Managed via dependency injection (`get_db()`) utilizing context-managed generator yields with guaranteed cleanup in `finally:` blocks.

---

## 4. Machine Learning System Architecture

```text
[Incoming Job / Candidate Profile]
               │
   ┌───────────┴───────────┐
   ▼                       ▼
[Job Posting]        [Candidate Profile]
   │                       │
   ▼                       ▼
Phase 4: ML Classifier     Phase 5: Career Recommender
 • TF-IDF (18,458 feats)   • Cosine Similarity vs 8 Benchmark Roles
 • Multinomial Logistic    • Readiness Score: [0.0, 100.0]
 • Confidence Tiering      • Phased Milestone Roadmap
 • Rule-based Fallback     • In-Memory Multi-Format Resume Parser
                           │
                           ▼
                     Phase 6: Salary Predictor
                      • Ridge Regression (alpha=10.0)
                      • Non-Tech Role Gating (HTTP 400)
                      • 90% Conformal Prediction Intervals
```

### 4.1 Phase 4: Job Role Classification
- **Artifact:** `data/models/role_classifier_baseline_v0.1.0.joblib`
- **Inference Flow:** Input text $\to$ Feature Synthesis (`JobTextFeatures`) $\to$ TF-IDF Vectorization $\to$ Logistic Regression $\to$ Class Probabilities $\to$ Confidence Tiering (`HIGH`, `MEDIUM`, `UNCERTAIN`).
- **Resilience:** If ML confidence falls below threshold or the model is unavailable, automatically falls back to `classify_job_by_rules()` keyword scoring.

### 4.2 Phase 5: Technical Career Recommendations
- **Artifact:** `AI_ML/Phase_5_Career_Recommendation/benchmarks/role_skill_benchmarks.json`
- **Scoring:** Calculates normalized dot-product cosine similarity between candidate skills and role benchmark vectors across 8 technical career tracks.
- **Diagnostic Engine:** Differential gap analysis identifies acquired vs missing critical skills and outputs a readiness score strictly bounded within $[0.0, 100.0]$.

### 4.3 Phase 6: Conformal Salary Prediction
- **Artifact:** `AI_ML/Phase_6_Salary_Prediction/models/artifacts/salary_predictor_v2.0.0_tech_only.joblib`
- **Mathematical Formulation:**
  $$\ln(1 + \hat{y}) = \mathbf{w}^T \mathbf{x} + b \quad\implies\quad \hat{y} = \exp(\mathbf{w}^T \mathbf{x} + b) - 1$$
- **Uncertainty Calibration:** Employs inductive conformal prediction based on calibration non-conformity scores, providing a verified **90.09% empirical market coverage interval**.

---

## 5. Security & Data Governance Architecture

1. **Credential Isolation:** External API credentials (Adzuna) are loaded from `.env` via `pydantic-settings` / `os.getenv`. Credential masking regex ensures tokens never appear in plain text.
2. **Zero Disk Storage for User Files:** Resume uploads are streamed into memory as raw byte arrays, extracted via `pypdf` / `python-docx`, and discarded immediately after skill token extraction.
3. **Strict Domain Gating:** Non-technical corporate roles are rejected with HTTP 400, preventing non-engineering roles from skewing technical compensation statistics.

---

## 6. Certification

This architecture balances high query performance via in-memory caching with strict data immutability and mathematically sound machine learning inference.
