# JobRadar — Indian Tech Job Market Intelligence & Career Intelligence Platform

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI: 0.115+](https://img.shields.io/badge/FastAPI-0.115%2B-green.svg)](https://fastapi.tiangolo.com/)
[![React: 19+](https://img.shields.io/badge/React-19-61dafb.svg)](https://react.dev/)
[![Vite: 8+](https://img.shields.io/badge/Vite-8-646cff.svg)](https://vite.dev/)
[![Tests: 514 Passing](https://img.shields.io/badge/Tests-514%20Passing-brightgreen.svg)](JobRadar/DDS-Job-Market-Project/docs/testing/PHASE_7_5_FINAL_TEST_SUMMARY.md)

JobRadar is an end-to-end Indian technology job-market intelligence and career intelligence platform. It processes over **97,600+ verified Indian tech job postings** to deliver macro-market analytics, emerging skill momentum tracking, AI job classification, personalized career path recommendations, skill-gap analysis, and regularized salary estimation with 90% calibrated conformal prediction intervals.

---

## 1. Key Platform Features

- **Empirical Market Intelligence Dashboard:** Real-time visibility into hiring volumes, location demand across Indian IT hubs (Bengaluru, Hyderabad, Pune, Gurugram), role distribution, and salary disclosure benchmarks.
- **Skill Demand & Hiring Momentum Index:** Ranks 100+ technical competencies combining hiring growth velocity, salary premiums, and temporal recency into actionable momentum tiers (`High Momentum`, `Moderate Momentum`).
- **AI Job Role Classification (Phase 4):** TF-IDF Vectorizer + Multinomial Logistic Regression classifying raw postings across 11 canonical role families with confidence scoring and keyword rule-based fallback.
- **Technical Career Recommendations & Skill-Gap Analysis (Phase 5):** Knowledge-graph vector matching across 8 core technical career tracks. Diagnostic engine computes candidate readiness scores bounded within $[0.0, 100.0]$ and generates personalized multi-week learning roadmaps.
- **In-Memory Resume Parsing:** Extracts technical competencies directly from PDF, DOCX, and TXT resume byte buffers with **zero temporary file persistence on disk**.
- **Conformal Salary Prediction (Phase 6):** Ridge Regression model ($\alpha=10.0$) trained on log-transformed salaries from verified tech postings, outputting point predictions accompanied by **90% calibrated conformal prediction intervals** ($\pm 8$ to $10$ LPA empirical uncertainty).

---

## 2. Technology Stack

| Layer | Technology | Primary Purpose |
|:---|:---|:---|
| **Frontend** | React 19, Vite 8, Tailwind CSS 3.4 | Modern, responsive Single Page Application (SPA) |
| **Data Visualization** | Recharts 3.10, Lucide Icons | Responsive interactive bar, area, and pie charts |
| **API Client** | Centralized `client.js` with `AbortController` | 15s timeout management, error unrolling, multipart uploads |
| **Backend API** | Python 3.12, FastAPI 0.115+, Uvicorn 0.54 | Asynchronous REST API serving 21 endpoints |
| **Data Layer** | SQLite 3.x, SQLAlchemy 2.1, Pandas 3.0 | Read-only SQLite storage (98,347 jobs) & in-memory caching |
| **Machine Learning** | Scikit-learn 1.9, Joblib 1.6, NumPy 2.5 | Classification, conformal regression, vector similarity |
| **Document Parsers** | `pypdf` 7.0, `python-docx` 1.2 | Pure in-memory resume parsing without disk I/O |

---

## 3. Architecture Overview

```text
┌────────────────────────────────────────────────────────┐
│               REACT 19 FRONTEND (Vite 8)               │
│  Dashboard │ Jobs Search │ Skills │ Skill Gap │ Salary │
└───────────────────────────┬────────────────────────────┘
                            │ HTTP REST / JSON
                            ▼
┌────────────────────────────────────────────────────────┐
│                    FASTAPI BACKEND                     │
│   ┌────────────────────────┐  ┌────────────────────┐   │
│   │  IN-MEMORY DATASTORE   │  │   API ROUTERS      │   │
│   │ 97,682 Cleaned Postings│◄─┤ • Analytics        │   │
│   │ Sub-millisecond Search │  │ • Jobs Search      │   │
│   └────────────────────────┘  │ • Skills & Trends  │   │
│                               │ • ML Classify      │   │
│                               │ • Recommendations  │   │
│                               │ • Salary Predictor │   │
│                               └─────────┬──────────┘   │
└─────────────────────────────────────────┼──────────────┘
                                          │
       ┌──────────────────────────────────┼─────────────────────────────────┐
       ▼                                  ▼                                 ▼
┌──────────────┐                 ┌─────────────────┐               ┌─────────────────┐
│ SQLITE DB    │                 │   ML MODELS     │               │ IN-MEMORY PARSER│
│ jobradar.db  │                 │ Phase 4, 5 & 6  │               │ PDF, DOCX, TXT  │
│ (Read-Only)  │                 │ (.joblib / JSON)│               │ (0 Disk Writes) │
└──────────────┘                 └─────────────────┘               └─────────────────┘
```

---

## 4. Prerequisites

- **Python:** $\ge 3.10$ (Tested on Python 3.12 and 3.14)
- **Node.js:** $\ge 18.0.0$ (Tested on Node.js v24.22.0)
- **npm:** $\ge 9.0.0$

---

## 5. Quickstart Guide

### 5.1 Backend Setup
```bash
# Navigate to backend directory
cd "JobRadar/DDS-Job-Market-Project"

# Create and activate virtual environment
python -m venv .venv

# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Linux / macOS:
# source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create environment file from template
copy .env.example .env

# Run automated tests
pytest tests/ -v

# Start FastAPI server
uvicorn job_market.api:app --host 127.0.0.1 --port 8000 --reload
```
*Backend health check:* Open `http://127.0.0.1:8000/api/health` in your browser.

### 5.2 Frontend Setup
```bash
# In a new terminal, navigate to frontend directory
cd "JobRadar/Frontend"

# Install npm packages
npm install

# Start development server
npm run dev
```
*Frontend Application:* Open `http://localhost:5173` in your browser.

---

## 6. Project Directory Layout

```text
JobRadar/
├── AI_ML/                            # Core ML Subsystems (Phase 4, Phase 5, Phase 6)
│   ├── Phase_4_Job_Classification/   # TF-IDF + Logistic Regression Classifier
│   ├── Phase_5_Career_Recommendation/# Recommendation Engine & Skill-Gap Roadmap
│   └── Phase_6_Salary_Prediction/    # Conformal Ridge Regression Salary Model
│
├── DDS-Job-Market-Project/           # Backend Application, Storage & Docs
│   ├── requirements.txt              # Production Python dependencies
│   ├── data/                         # SQLite DB (jobradar.db), golden CSVs, models
│   ├── docs/                         # Architecture, API & model documentation
│   │   ├── ARCHITECTURE.md           # Full-stack architectural design
│   │   ├── API_DOCUMENTATION.md      # Complete REST API reference (21 endpoints)
│   │   ├── MODEL_DOCUMENTATION.md    # Machine learning specifications & metrics
│   │   ├── INSTALLATION_GUIDE.md     # Detailed installation & developer setup
│   │   └── testing/                  # All Phase 7.5 test reports & JSON logs
│   ├── src/job_market/               # FastAPI backend source modules (24 files)
│   └── tests/                        # 316 automated unit & integration test suites
│
└── Frontend/                         # React 19 + Vite 8 SPA
    ├── package.json                  # Dependencies (React, Recharts, Tailwind)
    ├── dist/                         # Production compiled bundle
    └── src/                          # Pages, Components, and centralized API client
```

---

## 7. Comprehensive Documentation Links

- [**System Architecture (`ARCHITECTURE.md`)**](JobRadar/DDS-Job-Market-Project/docs/ARCHITECTURE.md)
- [**Installation & Developer Guide (`INSTALLATION_GUIDE.md`)**](JobRadar/DDS-Job-Market-Project/docs/INSTALLATION_GUIDE.md)
- [**REST API Documentation (`API_DOCUMENTATION.md`)**](JobRadar/DDS-Job-Market-Project/docs/API_DOCUMENTATION.md)
- [**Machine Learning Model Documentation (`MODEL_DOCUMENTATION.md`)**](JobRadar/DDS-Job-Market-Project/docs/MODEL_DOCUMENTATION.md)
- [**Final Integration Audit Report (`PHASE_7_6_FINAL_AUDIT_REPORT.md`)**](JobRadar/DDS-Job-Market-Project/docs/PHASE_7_6_FINAL_AUDIT_REPORT.md)
- [**Deployment Readiness Checklist (`DEPLOYMENT_READINESS_CHECKLIST.md`)**](JobRadar/DDS-Job-Market-Project/docs/DEPLOYMENT_READINESS_CHECKLIST.md)

---

## 8. Verification & Test Evidence

In Phase 7.5, JobRadar achieved a **100% test pass rate across 514 test scenarios**:
- **Automated Pytest Suites:** 316 / 316 passed.
- **Backend API Matrix:** 59 / 59 passed.
- **Database Integration:** 38 / 38 passed.
- **Data Pipeline:** 13 / 13 passed.
- **Machine Learning Modules:** 21 / 21 passed.
- **Frontend Component Verification:** 29 / 29 passed.
- **Live End-to-End System Testing:** 35 / 35 passed.
- **Cross-Module Interoperability:** 3 / 3 passed.

Full test evidence and JSON logs are preserved in [`JobRadar/DDS-Job-Market-Project/docs/testing/`](JobRadar/DDS-Job-Market-Project/docs/testing/).

---

## 9. Status & Known Limitations

**Current Phase Status:** **PASSED WITH LIMITATIONS (Ready for Phase 8 Deployment)**
1. **Phase 4 Provisional Labels:** The classifier model is trained on automated silver-standard rule labels (`is_provisional = True`, 85.71% benchmark accuracy). A double-blind human annotation campaign is pending to establish a gold-standard baseline.
2. **Technical Scope Restriction:** Salary prediction and career recommendations are calibrated exclusively for 8 core technical and data families. Corporate non-technical roles are rejected by design (HTTP 400).
3. **Single-Worker In-Memory State:** `DataStore` loads the 97,682-row dataset into process memory. Horizontal scaling across multi-worker clusters will require transition to Redis or direct SQLite queries.

---

## 10. License & Attribution

Distributed under the MIT License. Developed for the Indian Tech Job Market Analysis and Career Intelligence Platform Project.
