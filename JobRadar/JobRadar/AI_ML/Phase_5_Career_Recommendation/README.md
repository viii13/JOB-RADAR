# Phase 5: Student Career Recommendation Engine

## 1. Overview & Architecture

Phase 5 delivers an explainable, data-driven career recommendation, skill-gap analysis, and learning roadmap platform tailored specifically for university students and fresh graduates. It evaluates acquired competencies (from manual profiles or uploaded resumes) against empirical job-market skill benchmarks across 8 approved technical career families.

```text
Phase_5_Career_Recommendation/
├── benchmarks/         # Stage 5.1: Empirical role-skill benchmarks (N=26,766 eligible jobs)
│   ├── benchmark_extractor.py
│   ├── role_skill_benchmarks.json
│   └── __init__.py
├── resume/             # Stage 5.2: Text extraction (PDF, DOCX, TXT) and canonical skill parsing
│   ├── resume_extractor.py
│   └── __init__.py
├── recommendations/    # Stage 5.3: Explainable, deterministic career recommendation engine
│   ├── recommender.py
│   └── __init__.py
├── skill_gap/          # Stage 5.4: Differential gap analysis & readiness scoring
│   ├── analyzer.py
│   └── __init__.py
├── roadmap/            # Stage 5.5: Personalized learning roadmap & portfolio project generation
│   ├── generator.py
│   ├── resources.py
│   └── __init__.py
├── tests/              # Comprehensive unit and integration test suites (52 tests)
│   ├── test_benchmarks.py
│   ├── test_resume_extractor.py
│   ├── test_recommender.py
│   ├── test_skill_gap.py
│   ├── test_roadmap.py
│   └── test_phase5_integration.py
└── README.md
```

---

## 2. Stage Breakdown & Methodology

### 2.1 Stage 5.1: Empirical Role-Skill Benchmarks (`benchmarks/`)
- **Data Source:** Extracted from 97,679 deduplicated postings (`cleaned_indian_job_market_2025.csv`) and 210,029 deduplicated skill associations (`job_skills.csv`).
- **Eligible Universe:** 26,766 job postings classified into 8 technical roles with confidence $\ge 0.20$ using the Phase 4 model.
- **Dual Denominators:**
  1. *Primary Demand Percentage:* Distinct jobs requiring skill / Total eligible jobs in role $\times 100$.
  2. *Secondary Disclosed Percentage:* Distinct jobs requiring skill / Jobs with $\ge 1$ disclosed skill $\times 100$.
- **Support Tiers:**
  - `HIGH`: $\ge 2,500$ eligible postings (`Backend`, `Data Analyst`, `Frontend`, `QA`).
  - `MODERATE`: $1,000 - 2,499$ eligible postings (`Cloud/DevOps`, `Data Engineer`, `ML/AI`).
  - `LOW`: $< 1,000$ eligible postings (`Data Scientist`, $N=272$).

### 2.2 Stage 5.2: Resume Text Extraction & Skill Parsing (`resume/`)
- **Supported Formats:**
  - **PDF:** Extracted via pure-Python `pypdf`. Checks page count ($\le 10$ pages) and encryption status. Validates `%PDF-` signature within the first 1024 bytes before calling parser. If extracted text has $< 20$ characters, returns `status="scanned_pdf"` (OCR is deliberately excluded).
  - **DOCX:** Extracted via `python-docx` across paragraphs and table cells. Validates ZIP container signature (`PK`) prior to parsing.
  - **TXT:** Standard Python extraction with UTF-8 and Latin-1 fallback.
- **File Constraints:** Enforces 5 MB size limit, magic byte content verification, and rejects corrupt or unsupported extensions.
- **Skill Extraction:** Reuses `job_market.skills` regular expressions, alias mapping (`skill_aliases.json`), and categorization (`skill_categories.json`).
- **Ambiguity Guardrails:**
  - Context-bound matching for single-letter programming languages: `C` requires `C programming`/`C language`; `R` requires `R programming`/`R language`/`RStudio`.
  - Case-sensitive boundary matching for `AI` and `IT`.
  - Captures evidence context snippets (e.g. `"...building REST APIs with Python and FastAPI..."`).
- **Privacy & Security:** Uploaded resumes are processed in-memory and **never persisted** to disk or database. Full resume text and PII are never logged.

### 2.3 Stage 5.3: Career Recommendation Engine (`recommendations/`)
- **Eligible Roles:** Strictly limited to the 8 technical role families. Excludes non-tech corporate operations, hybrid product management, and unclassified fallbacks.
- **Objective Scoring Formula (0.0 to 100.0%):**
  $$\text{MatchScore} = \min\left(100.0, \text{BaseScore}\right)$$
  Where:
  - **For roles with critical skills** (e.g. Frontend, Machine Learning):
    $$\text{BaseScore} = 0.50 \times S_{\text{crit}} + 0.40 \times S_{\text{core}} + S_{\text{breadth}}$$
  - **For roles without critical skills** (e.g. Backend, where top skills are $< 50\%$):
    $$\text{BaseScore} = 0.90 \times S_{\text{core}} + S_{\text{breadth}}$$
    *(Allocates the combined 0.90 weight directly to demand-weighted core coverage, preventing recommended skills from being counted twice).*
  - $S_{\text{crit}}$: Coverage percentage of role Critical skills ($\text{DemandPct} \ge 50\%$).
  - $S_{\text{core}}$: Demand-weighted coverage of role core requirements (Critical + Recommended):
    $$S_{\text{core}} = \frac{\sum_{s \in M_R \cap \text{Core}_R} \text{DemandPct}(s, R)}{\sum_{s \in \text{Core}_R} \text{DemandPct}(s, R)} \times 100$$
  - $S_{\text{breadth}}$: Bounded bonus for matching elective competencies ($\max 10.0$ points).
- **Preference as a Deterministic Tie-Breaker:**
  - `match_score` strictly reflects objective skill fit (no additive bonus points are added).
  - Career preferences (`is_preferred`) are preserved as a separate property and act strictly as a tie-breaker when objective scores are equal.
- **Ranking Order:**
  Sorted by `match_score` DESC, then `is_preferred` DESC, then `support_tier` rank DESC (`HIGH` > `MODERATE` > `LOW`), then `role_name` ASC.

### 2.4 Stage 5.4: Skill-Gap Analysis (`skill_gap/`)
- **Partitions:**
  - **Acquired Competencies:** Skills present in student profile and benchmarked for target role.
  - **Missing Critical Competencies:** High-impact skills with benchmark demand $\ge 50\%$.
  - **Missing Recommended Competencies:** High-value skills with benchmark demand $20\% - 49.9\%$.
  - **Missing Elective Competencies:** Specialized skills with benchmark demand $< 20\%$.
  - **Transferable Competencies:** User skills that demonstrate technical ability outside the role's core.
- **Readiness Score:**
  $$\text{ReadinessScore} = \frac{\sum_{s \in \text{Acquired} \cap \text{Core}} w_s \cdot \text{DemandPct}(s, R)}{\sum_{s \in \text{Core}} w_s \cdot \text{DemandPct}(s, R)} \times 100$$
  where $w_{\text{CRITICAL}} = 2.0$, $w_{\text{RECOMMENDED}} = 1.0$.
  *Measures empirical alignment with benchmarked postings in JobRadar; does NOT guarantee hiring.*

### 2.5 Stage 5.5: Personalized Learning Roadmap (`roadmap/`)
- **Milestone Sequencing:**
  - **Sequential Phase Numbering:**
    - If missing critical skills exist: starts with `Phase 1: Critical Foundations`, followed by `Phase 2: High-Demand Tools`, and `Phase 3: Applied Electives`.
    - If no critical skills are missing: starts with `Phase 1: Core Technologies`, followed by `Phase 2: Applied Electives`.
  - **Capstone Portfolio Integration Project:** Synthesizes acquired and newly learned skills into an end-to-end, production-grade portfolio project with concrete deliverables (GitHub repository, unit tests, deployment, documentation).
- **Verified Resources (`resources.py`):**
  - Reuses verified entries from `mockLearning.js` (`Machine Learning`, `Scikit-learn`, `NLP`, `Statistics`, `Deep Learning`, `AWS`, `Docker`).
  - Supplements with official documentation (Python.org, React.dev, PostgreSQL.org, Spring.io, Kubernetes.io, Spark.apache.org).
  - **Strictly avoids fabricating course links or fictional prices.** If no verified course link exists, provides a concrete implementation activity and project specification.

---

## 3. Methodological Distinctions

| Aspect | Observed Facts (Data) | Heuristics (Project Design) | Implementation Assumptions |
| :--- | :--- | :--- | :--- |
| **Skill Demand** | Primary and disclosed percentages computed from 26,766 classified Indian job postings. | Priority thresholds (`CRITICAL` $\ge 50\%$, `RECOMMENDED` $20\% - 49.9\%$, `ELECTIVE` $< 20\%$). | Postings with confidence $\ge 0.20$ reflect representative role demand. |
| **Confidence Cutoff** | Heuristic score from Phase 4 silver classifier ($\ge 2.2\times$ uniform chance). | $0.20$ threshold used to discard unclassified noise. | Softmax outputs are uncalibrated decision scores, not frequentist probabilities. |
| **Readiness Score** | Counts of acquired vs missing skills from the benchmark. | Weights: Critical ($2.0$), Recommended ($1.0$). Bounded in $[0, 100]\%$. | Readiness represents portfolio alignment, not interview outcomes or job offer probabilities. |
| **Roadmap Estimates** | Real curated courses and official documentation links. | Estimated study effort of 2–4 weeks per skill assuming 10–15 hours/week. | Independent self-study pacing varies by student prior background. |

---

## 4. How to Run Tests

From the project root:

```powershell
# Run all Phase 5 unit and integration tests (55 tests)
.\JobRadar\DDS-Job-Market-Project\.venv\Scripts\python.exe -m unittest discover -s JobRadar/AI_ML/Phase_5_Career_Recommendation/tests -v

# Run the complete backend regression test suite (206 tests)
.\JobRadar\DDS-Job-Market-Project\.venv\Scripts\python.exe -c "import sys, unittest; sys.path.insert(0, r'JobRadar\DDS-Job-Market-Project\src'); test_suite = unittest.defaultTestLoader.discover(r'JobRadar\DDS-Job-Market-Project\tests'); runner = unittest.TextTestRunner(verbosity=1); res = runner.run(test_suite); sys.exit(0 if res.wasSuccessful() else 1)"
```

---

## 5. Stage 5.6: FastAPI & React Integration (Completed)

Stage 5.6 connects the verified Phase 5 backend engine directly to the JobRadar FastAPI backend and React frontend application.

### 5.1 Endpoints Implemented

| Endpoint | Method | Input | Output | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `/api/resume/extract-skills` | `POST` | `multipart/form-data` (`file`) | `ResumeSkillExtractionResponse` | Strictly in-memory text extraction and canonical skill extraction. Validates file extension (.pdf, .docx, .txt), magic bytes, and enforces 5 MB limit. Rejects empty (400) or oversized (413) files. Detects scanned PDFs safely. Never writes to disk or SQLite. |
| `/api/recommendations/career` | `POST` | `CareerRecommendationRequest` (JSON) | `CareerRecommendationResponse` | Objective skill fit evaluation for 8 supported technical roles with explainability, match scores, matching/missing skills, and preference tie-breaking. |
| `/api/skills/gap` | `POST` | `SkillGapRequest` (JSON) | `SkillGapResponse` | Evaluates student skills against empirical benchmarks for target role across acquired, transferable, missing critical, missing recommended, and missing elective partitions with weighted readiness score ($0.0 - 100.0\%$). |
| `/api/roadmap/generate` | `POST` | `RoadmapRequest` (JSON) | `RoadmapResponse` | Personalized milestone learning roadmap with official references, courses, practice platforms, and practical portfolio projects. |
| `/api/recommendations/roles` | `GET` | None | `list[dict]` | Returns catalog of 8 supported technical roles with descriptions and frontend filter mappings. |

### 5.2 How to Run the Applications

#### Running the FastAPI Backend:
```powershell
cd JobRadar\DDS-Job-Market-Project
.\.venv\Scripts\uvicorn.exe job_market.api:app --reload --host 127.0.0.1 --port 8000
```
Swagger UI documentation is automatically accessible at `http://127.0.0.1:8000/docs`.

#### Running the React Frontend:
```powershell
cd JobRadar\Frontend
npm.cmd run dev
```
Development server will be accessible at `http://localhost:5173`.

### 5.3 Privacy & Security Guarantees
- **Pure In-Memory Processing:** Resumes are parsed directly from memory buffers. No files are saved to temporary directories, disk storage, or databases.
- **Zero PII Logging:** Resume text, names, emails, and phone numbers are never printed to console logs or log files.
- **Strict Content & Size Validation:** File sizes $> 5$ MB are rejected with HTTP 413. Extension and magic byte checks prevent arbitrary execution.
- **Client Transparency:** Extracted skills are returned for student review and confirmation before being used in recommendations or gap calculations.

---

## 6. Verification & Test Execution

```powershell
# 1. Run all Phase 5 business logic unit & integration tests (57 tests)
.\JobRadar\DDS-Job-Market-Project\.venv\Scripts\python.exe -m unittest discover -s JobRadar/AI_ML/Phase_5_Career_Recommendation/tests -v

# 2. Run new Phase 5.6 API test suite (21 tests)
.\JobRadar\DDS-Job-Market-Project\.venv\Scripts\python.exe -m unittest JobRadar/DDS-Job-Market-Project/tests/test_career_recommendations_api.py -v

# 3. Run complete backend regression test suite (206 tests)
.\JobRadar\DDS-Job-Market-Project\.venv\Scripts\python.exe -c "import sys, unittest; sys.path.insert(0, r'JobRadar\DDS-Job-Market-Project\src'); test_suite = unittest.defaultTestLoader.discover(r'JobRadar\DDS-Job-Market-Project\tests'); runner = unittest.TextTestRunner(verbosity=1); res = runner.run(test_suite); sys.exit(0 if res.wasSuccessful() else 1)"

# 4. Run Frontend Production Build & Linter
cd JobRadar\Frontend
npm.cmd run build
npm.cmd run lint
```

### Phase 5 Completion Status
```text
[x] Stage 5.1 — Empirical Role-Skill Benchmarks
[x] Stage 5.2 — Resume Extraction and Skill Parsing
[x] Stage 5.3 — Career Recommendation Engine
[x] Stage 5.4 — Skill-Gap Analysis
[x] Stage 5.5 — Personalized Learning Roadmap
[x] Stage 5.6 — FastAPI and React Integration
[x] Full End-to-End Verification
```
