# JobRadar — Developer Installation & Setup Guide

**Document ID:** `JR-GUIDE-INSTALL-P7.6`  
**Execution Date:** 2026-11-12  
**Auditor:** Senior DevOps Engineer & Software Architect  
**Target Environment:** Local Developer Workstation (Windows, macOS, or Linux)

---

## 1. Prerequisites

Before installing JobRadar, verify that your workstation has the following runtimes installed:

| Runtime / Tool | Minimum Version | Verified Working Version | Check Command |
|:---|:---:|:---:|:---|
| **Python** | $\ge 3.10.0$ | Python 3.12 / 3.14 | `python --version` |
| **Node.js** | $\ge 18.0.0$ | Node.js v24.22.0 | `node -v` |
| **npm** | $\ge 9.0.0$ | npm v10.x | `npm -v` |
| **SQLite** | $\ge 3.35.0$ | SQLite 3.x (Built-in) | `python -c "import sqlite3; print(sqlite3.sqlite_version)"` |

---

## 2. Repository Layout

Clone or navigate to the JobRadar project workspace:
```bash
cd "JobRadar/JobRadar"
```

The workspace contains two primary project directories:
- `DDS-Job-Market-Project/`: Python FastAPI backend, database, and machine learning models.
- `Frontend/`: React 19 + Vite 8 Single Page Application.

---

## 3. Backend Setup (`DDS-Job-Market-Project`)

### Step 3.1: Create & Activate Virtual Environment
```bash
cd DDS-Job-Market-Project

# Create virtual environment
python -m venv .venv

# Activate on Windows PowerShell:
.venv\Scripts\Activate.ps1

# Activate on Linux / macOS:
source .venv/bin/activate
```

### Step 3.2: Install Python Dependencies
```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Step 3.3: Configure Environment Variables
Copy the template configuration file:
```bash
# Windows
copy .env.example .env

# Linux / macOS
cp .env.example .env
```
Edit `.env` if you have Adzuna API credentials (optional; required only for live scraping):
```ini
ADZUNA_APP_ID=your_adzuna_app_id_here
ADZUNA_APP_KEY=your_adzuna_app_key_here
DATABASE_URL=sqlite:///data/jobradar.db
HOST=127.0.0.1
PORT=8000
```

### Step 3.4: Verify Data & Model Artifacts
Ensure the following files are present in `data/`:
- `data/jobradar.db` (266 MB SQLite database)
- `data/processed/cleaned_indian_job_market_2025.csv` (159 MB golden dataset)
- `data/processed/job_skills.csv` (11.5 MB relational mappings)
- `data/processed/emerging_skills.json` (42 kB hiring momentum data)
- `data/models/role_classifier_baseline_v0.1.0.joblib` (2.4 MB Phase 4 model)

### Step 3.5: Run Backend Automated Verification Tests
```bash
pytest tests/ -v
```
*(All 316 unit and integration tests should pass).*

### Step 3.6: Start the FastAPI Backend Server
```bash
# Using uvicorn directly
uvicorn job_market.api:app --host 127.0.0.1 --port 8000 --reload
```
Verify the server is running by opening `http://127.0.0.1:8000/api/health` in your browser. You should receive:
```json
{
  "status": "healthy",
  "service": "JobRadar API",
  "database": {
    "connected": true,
    "total_jobs": 98347
  },
  "models": {
    "salary_predictor_loaded": true,
    "career_recommendations_loaded": true,
    "emerging_skills_index_loaded": true
  }
}
```

---

## 4. Frontend Setup (`Frontend`)

### Step 4.1: Navigate to Frontend Directory
Open a separate terminal window and navigate to `Frontend`:
```bash
cd "JobRadar/JobRadar/Frontend"
```

### Step 4.2: Install npm Packages
```bash
npm install
```

### Step 4.3: Configure Frontend Environment (Optional)
```bash
# Windows
copy .env.example .env

# Linux / macOS
cp .env.example .env
```
Ensure `VITE_API_URL` points to your running FastAPI backend:
```ini
VITE_API_URL=http://127.0.0.1:8000
```

### Step 4.4: Start the Vite Development Server
```bash
npm run dev
```
Open your browser at `http://localhost:5173`. The JobRadar application dashboard will load and connect to your local FastAPI backend.

### Step 4.5: Compile Production Build (Optional)
To verify that the frontend bundles into optimized production assets:
```bash
npm run build
```
Assets will be generated in `dist/`.

---

## 5. Troubleshooting & FAQ

### Issue: "SyntaxWarning: invalid escape sequence"
- **Solution:** Handled in Phase 7.6. All regex and markdown strings in `emerging.py` use raw string literals (`r"..."`). Ensure you are using the updated repository files.

### Issue: "TypeError: Cannot read properties of undefined (reading 'VITE_API_URL')" in Node
- **Cause:** Running tests directly with Node ESM outside Vite.
- **Solution:** Use Vite's programmatic SSR server (`node test_frontend_step7.mjs`) which defines `import.meta.env`.

### Issue: "The starlette.testclient module requires httpx2"
- **Solution:** Run live integration tests using `scratch/run_step8_live_e2e.py` (which launches a real live Uvicorn server in a thread and uses Python's standard `urllib`) rather than Starlette TestClient.

---

## 6. Verification Checklist

- [ ] Python virtual environment created and activated.
- [ ] `pip install -r requirements.txt` completed with 0 errors.
- [ ] Backend starts on `http://127.0.0.1:8000/api/health` returning `healthy`.
- [ ] Frontend `npm install` and `npm run dev` starts on `http://localhost:5173`.
- [ ] Dashboard renders real market KPIs (97,682 jobs analyzed, ₹7.6 LPA avg salary).
