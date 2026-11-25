# JobRadar — Comprehensive Backend REST API Documentation

**Document ID:** `JR-DOCS-API-P7.6`  
**Execution Date:** 2026-11-12  
**API Version:** v1.0.0 (FastAPI 0.115.x / OpenAPI 3.1)  
**Base URL:** `http://127.0.0.1:8000`  
**Total Registered Routes:** 21 Endpoints  
**Interactive Swagger UI:** Available at `/docs` when server is running

---

## 1. System & Health Endpoints

### 1.1 Service Health Check
- **Route:** `GET /api/health`
- **Associated Service:** Core System Diagnostics
- **Description:** Verifies database connectivity, in-memory dataset records, and ML model initialization.
- **Request Parameters:** None.
- **Success Response (HTTP 200):**
  ```json
  {
    "status": "healthy",
    "service": "JobRadar API",
    "database": {
      "connected": true,
      "total_jobs": 98347
    },
    "dataset": {
      "total_jobs_processed": 97682,
      "total_skill_mentions": 216977,
      "unique_skills": 120,
      "jobs_with_skills": 97111
    },
    "models": {
      "salary_predictor_loaded": true,
      "salary_predictor_version": "2.0.0",
      "career_recommendations_loaded": true,
      "emerging_skills_index_loaded": true,
      "role_classifier_loaded": true,
      "role_classifier_version": "0.1.0"
    }
  }
  ```

---

## 2. Market Analytics Endpoints

### 2.1 Market Intelligence Overview Bundle
- **Route:** `GET /api/analytics/overview` (Alias: `GET /api/analytics/market-overview`)
- **Associated Service:** `DataStore` Caching Layer
- **Description:** Returns macro market KPIs, salary distribution, role demand share, and posting trends.
- **Success Response (HTTP 200):**
  ```json
  {
    "status": "success",
    "summary": {
      "totalJobsAnalyzed": 97682,
      "averageSalaryLPA": 7.6,
      "medianSalaryLPA": 6.0,
      "topSkill": "Python",
      "topSkillDemandPct": 21.6,
      "activeHiringCompanies": 18617,
      "topHiringCity": "Bengaluru",
      "momGrowthPct": "+14.2%",
      "salaryDisclosedJobs": 11268,
      "salaryDisclosureRatePct": 11.5,
      "salaryScopeNote": "Valid disclosed salaries only"
    },
    "roleDemand": [...],
    "locationDemand": [...],
    "salaryDistribution": [...],
    "postingVolumeTrend": [...]
  }
  ```

### 2.2 Disclosed Salary Distribution & Statistics
- **Route:** `GET /api/analytics/salary`
- **Associated Service:** Salary Aggregator
- **Description:** Statistical summary of valid disclosed compensation figures in LPA.
- **Success Response (HTTP 200):**
  ```json
  {
    "average_salary_lpa": 7.6,
    "median_salary_lpa": 6.0,
    "min_salary_lpa": 0.6,
    "max_salary_lpa": 85.0,
    "disclosed_jobs_count": 11268,
    "disclosure_rate_pct": 11.5,
    "distribution": [
      { "bracket": "0-3 LPA", "count": 2150 },
      { "bracket": "3-6 LPA", "count": 4820 }
    ]
  }
  ```

---

## 3. Job Search & Filtering Endpoints

### 3.1 Search & Filter Jobs Catalog
- **Route:** `GET /api/jobs`
- **Associated Service:** `DataStore.search_jobs()`
- **Query Parameters:**
  - `search` (string, optional): Keyword search across title, company, description, and skills.
  - `role` (string, optional): Role title filter (e.g. `"Data Scientist"`).
  - `location` (string, optional): City or state filter (e.g. `"Bengaluru"`).
  - `experience` (string, optional): Experience bracket (`"Entry"`, `"Mid"`, `"Senior"`).
  - `min_salary` (float, optional, $\ge 0$): Minimum disclosed salary in LPA.
  - `skill` (string, optional): Exact normalized skill name.
  - `work_type` (string, optional): `"Remote"`, `"Hybrid"`, `"On-site"`.
  - `sort_by` (string, optional, default `"relevance"`): `"relevance"`, `"salary_desc"`, `"date_desc"`.
  - `page` (int, default 1, $\ge 1$): Page number.
  - `limit` (int, default 20, $1 \le \text{limit} \le 100$): Results per page.
- **Success Response (HTTP 200):**
  ```json
  {
    "total": 97679,
    "page": 1,
    "limit": 20,
    "total_pages": 4884,
    "jobs": [
      {
        "id": "1001",
        "title": "Senior Backend Engineer",
        "company": "Infosys",
        "companyLogoText": "IN",
        "location": "Bengaluru, Karnataka",
        "salary_min": 12.0,
        "salary_max": 18.0,
        "salary_display": "₹12-18 LPA",
        "experience_min": 4.0,
        "experience_max": 7.0,
        "experience_display": "4-7 yrs",
        "work_type": "Hybrid",
        "skills": ["Java", "Spring Boot", "Microservices", "Docker"],
        "description": "Architect scalable backend services...",
        "posted_date": "2025-02-10",
        "days_ago": 2
      }
    ]
  }
  ```

### 3.2 Single Job Detail Lookup
- **Route:** `GET /api/jobs/{job_id}`
- **Description:** Retrieves full posting details for a specific unique identifier.
- **Error Codes:** `404 Not Found` if `job_id` does not exist.

---

## 4. Skill Intelligence Endpoints

### 4.1 In-Demand Skills Ranking
- **Route:** `GET /api/skills/top`
- **Query Parameters:** `limit` (int, default 10), `category` (string, optional).
- **Success Response (HTTP 200):** Array of objects: `[{"skill": "Python", "category": "Programming Language", "demand_job_count": 21085}, ...]`

### 4.2 Functional Skill Categories Breakdown
- **Route:** `GET /api/skills/categories`
- **Success Response (HTTP 200):** Array of 10 categories with `skill_count` and `total_demand`.

### 4.3 Skill Demand Breakdown by Target Role
- **Route:** `GET /api/skills/by-role`
- **Query Parameters:** `role` (string, required, e.g. `"Data Scientist"`).
- **Success Response (HTTP 200):**
  ```json
  {
    "success": true,
    "role_name": "Data Scientist",
    "role_id": "data_scientist_advanced_analytics",
    "skills": [
      { "skill": "Python", "demand_count": 1420, "demand_pct": 68.5 }
    ]
  }
  ```

### 4.4 Emerging Skills & Hiring Momentum Index
- **Route:** `GET /api/skills/emerging`
- **Query Parameters:** `limit` (int, default 20), `tier` (string, optional).
- **Success Response (HTTP 200):** Array of emerging skills with `momentum_index` and `momentum_tier` (`"High Momentum"`, `"Moderate Momentum"`).

---

## 5. Machine Learning Classification Endpoints (Phase 4)

### 5.1 Single Job Role Classification
- **Route:** `POST /api/classify/job`
- **Associated Service:** Phase 4 Classifier (`role_classifier_baseline_v0.1.0.joblib`)
- **Request Body (JSON):**
  ```json
  {
    "title": "Senior Cloud DevOps Engineer",
    "skills": ["AWS", "Kubernetes", "Docker", "Terraform"],
    "description": "Manage Kubernetes clusters and automate infrastructure as code.",
    "min_confidence": 0.0
  }
  ```
- **Success Response (HTTP 200):**
  ```json
  {
    "predicted_role": "cloud_devops_sre",
    "predicted_role_name": "Cloud Infrastructure, DevOps & SRE",
    "confidence": 0.8351,
    "confidence_tier": "HIGH",
    "is_fallback": false,
    "confidence_margin": 0.65,
    "runner_up_role": "backend_core_software_engineering",
    "runner_up_confidence": 0.12,
    "class_probabilities": {...},
    "model_version": "0.1.0",
    "label_source": "provisional_silver_rule_v1",
    "is_provisional": true,
    "method": "ml_logistic_regression"
  }
  ```

### 5.2 Batch Job Role Classification
- **Route:** `POST /api/classify/batch`
- **Request Body (JSON):** `{"jobs": [{"id": "1", "title": "..."}, ...]}` (Maximum 100 jobs per batch).
- **Error Codes:** `400 Bad Request` if batch is empty or exceeds 100 jobs.

---

## 6. Technical Career Recommendations Endpoints (Phase 5)

### 6.1 Career Recommendation Ranking
- **Route:** `POST /api/recommendations/career`
- **Request Body (JSON):**
  ```json
  {
    "skills": ["Python", "SQL", "Pandas", "Scikit-learn"],
    "preferred_role": "Data Scientist"
  }
  ```
- **Success Response (HTTP 200):**
  ```json
  {
    "status": "success",
    "recommendations": [
      {
        "role_id": "data_scientist_advanced_analytics",
        "role_name": "Data Scientist & Advanced Analytics",
        "match_score": 53.7,
        "matching_skills": ["Python", "SQL", "Scikit-learn", "Pandas"],
        "gap_skills": ["Statistics", "Machine Learning"]
      }
    ]
  }
  ```

### 6.2 Skill Gap Diagnostic
- **Route:** `POST /api/skills/gap`
- **Request Body (JSON):** `{"skills": ["Python", "SQL"], "target_role": "Data Scientist"}`
- **Success Response (HTTP 200):**
  ```json
  {
    "role_id": "data_scientist_advanced_analytics",
    "readiness_score": 42.5,
    "acquired_skills": ["Python", "SQL"],
    "missing_critical_skills": ["Machine Learning", "Statistics"],
    "missing_recommended_skills": ["PyTorch", "Deep Learning"]
  }
  ```

### 6.3 Phased Milestone Roadmap Generation
- **Route:** `POST /api/roadmap/generate`
- **Request Body (JSON):** `{"skills": ["Python"], "target_role": "Data Scientist"}`
- **Success Response (HTTP 200):** Milestones array with sequenced weekly commitments and completion criteria.

### 6.4 Supported Technical Roles Catalog
- **Route:** `GET /api/recommendations/roles`
- **Success Response (HTTP 200):** List of 8 supported technical career tracks.

### 6.5 In-Memory Resume Skill Parsing
- **Route:** `POST /api/resume/extract-skills`
- **Content-Type:** `multipart/form-data`
- **Form Field:** `file` (Binary payload: PDF, DOCX, or TXT).
- **Success Response (HTTP 200):**
  ```json
  {
    "success": true,
    "file_name": "resume.pdf",
    "extracted_skill_count": 6,
    "skills": [
      { "canonical_name": "Python", "category": "Programming Language" }
    ]
  }
  ```
- **Error Codes:** `400 Bad Request` for empty payloads, unsupported file types (`.exe`), or files exceeding 10 MB.

---

## 7. Conformal Salary Prediction Endpoints (Phase 6)

### 7.1 Predict Salary with Conformal Uncertainty
- **Route:** `POST /api/salary/predict`
- **Request Body (JSON):**
  ```json
  {
    "role": "Software Engineer",
    "experience_years": 3.0,
    "location": "Bengaluru",
    "skills": ["Java", "Spring Boot", "SQL"]
  }
  ```
- **Success Response (HTTP 200):**
  ```json
  {
    "target_role": "Software Engineer",
    "resolved_role_family": "backend_core_software_engineering",
    "is_technical": true,
    "experience_years": 3.0,
    "location": "Bengaluru",
    "predicted_salary_lpa": 7.12,
    "predicted_salary_annual_inr": 712000,
    "conformal_interval_lpa": {
      "min_lpa": 1.20,
      "max_lpa": 17.58
    },
    "conformal_uncertainty_lpa": 8.19,
    "coverage_level_pct": 90.0,
    "market_tier": "tier_1_metro",
    "model_name": "Ridge Regression (alpha=10.0)",
    "model_version": "2.0.0"
  }
  ```
- **Domain Rejection (HTTP 400):**
  ```json
  {
    "detail": "Salary prediction is currently calibrated exclusively for core technical engineering and data roles... The requested role 'HR Executive' is not within technical scope."
  }
  ```
- **Input Boundary Rejection (HTTP 422):** Raised if `experience_years < 0.0`.

### 7.2 Salary Model Metadata
- **Route:** `GET /api/salary/metadata`
- **Success Response (HTTP 200):** Returns champion model metrics (MAE 4.74 LPA, $R^2 = 0.4639$, 4,207 training samples, 5-fold GroupKFold validation strategy).

---

## 8. Global Error Responses

| HTTP Status | Meaning | Typical Trigger | JSON Payload Example |
|:---|:---|:---|:---|
| **400 Bad Request** | Domain Scope / Business Rule Violation | Non-technical role submitted to salary prediction; batch size > 100 | `{"detail": "Error description..."}` |
| **404 Not Found** | Resource Missing | Non-existent `job_id` or unregistered route | `{"detail": "Job ID 'XYZ' not found."}` |
| **408 Request Timeout** | Client Abort | Request took longer than client timeout (15s) | `{"detail": "Request timeout after 15s"}` |
| **422 Unprocessable Entity** | Pydantic Schema Validation Error | Negative experience, missing required field, non-numeric type | `{"detail": [{"loc": ["body", "exp"], "msg": "..."}]}` |
| **500 Internal Server Error** | Unhandled Exception | Internal backend failure | `{"detail": "Internal server error: ...", "path": "/api/..."}` |
