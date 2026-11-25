"""Independent API Test Runner for JobRadar Phase 7.5 Step 3.

Executes comprehensive positive, negative, boundary, and error handling tests
across all 21 verified backend API endpoints.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
import sys
import threading
import time
import urllib.error
import urllib.request
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
JOBRADAR_ROOT = PROJECT_ROOT.parent
if str(JOBRADAR_ROOT) not in sys.path:
    sys.path.insert(0, str(JOBRADAR_ROOT))

import uvicorn
from job_market.api import create_app

PORT = 8029
BASE_URL = f"http://127.0.0.1:{PORT}"

results: list[dict[str, Any]] = []


def record_result(
    endpoint: str,
    method: str,
    scenario: str,
    category: str,
    payload_or_params: Any,
    expected_status: int,
    actual_status: int,
    passed: bool,
    response_data: Any,
    notes: str = "",
    latency_ms: float = 0.0,
):
    results.append({
        "endpoint": endpoint,
        "method": method,
        "scenario": scenario,
        "category": category,
        "payload_or_params": payload_or_params,
        "expected_status": expected_status,
        "actual_status": actual_status,
        "status": "PASS" if passed else "FAIL",
        "response_summary": str(response_data)[:250] + ("..." if len(str(response_data)) > 250 else ""),
        "latency_ms": round(latency_ms, 2),
        "notes": notes,
    })


def http_get(path: str) -> tuple[int, Any, float]:
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url, headers={"User-Agent": "JobRadar-QA/1.0"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            dt = (time.time() - t0) * 1000
            data = json.loads(resp.read().decode("utf-8"))
            return resp.status, data, dt
    except urllib.error.HTTPError as err:
        dt = (time.time() - t0) * 1000
        try:
            body = json.loads(err.read().decode("utf-8"))
        except Exception:
            body = err.reason
        return err.code, body, dt
    except Exception as exc:
        dt = (time.time() - t0) * 1000
        return 0, str(exc), dt


def http_post_json(path: str, payload: Any) -> tuple[int, Any, float]:
    url = f"{BASE_URL}{path}"
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "JobRadar-QA/1.0"},
        method="POST",
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            dt = (time.time() - t0) * 1000
            data = json.loads(resp.read().decode("utf-8"))
            return resp.status, data, dt
    except urllib.error.HTTPError as err:
        dt = (time.time() - t0) * 1000
        try:
            body = json.loads(err.read().decode("utf-8"))
        except Exception:
            body = err.reason
        return err.code, body, dt
    except Exception as exc:
        dt = (time.time() - t0) * 1000
        return 0, str(exc), dt


def http_post_multipart(path: str, filename: str, content: bytes, content_type: str = "text/plain") -> tuple[int, Any, float]:
    url = f"{BASE_URL}{path}"
    boundary = "----JobRadarQABoundary987654321"
    
    parts = []
    parts.append(f"--{boundary}\r\n".encode("utf-8"))
    parts.append(f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode("utf-8"))
    parts.append(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
    parts.append(content)
    parts.append(f"\r\n--{boundary}--\r\n".encode("utf-8"))
    
    body = b"".join(parts)
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "JobRadar-QA/1.0",
        },
        method="POST",
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            dt = (time.time() - t0) * 1000
            data = json.loads(resp.read().decode("utf-8"))
            return resp.status, data, dt
    except urllib.error.HTTPError as err:
        dt = (time.time() - t0) * 1000
        try:
            body = json.loads(err.read().decode("utf-8"))
        except Exception:
            body = err.reason
        return err.code, body, dt
    except Exception as exc:
        dt = (time.time() - t0) * 1000
        return 0, str(exc), dt


def run_all_tests():
    print(f"[*] Starting background Uvicorn server on port {PORT}...")
    app = create_app()
    config = uvicorn.Config(app=app, host="127.0.0.1", port=PORT, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait for server startup
    started = False
    for _ in range(30):
        try:
            with urllib.request.urlopen(f"{BASE_URL}/api/health", timeout=1.0) as r:
                if r.status == 200:
                    started = True
                    break
        except Exception:
            time.sleep(0.2)

    if not started:
        print("[!] Server failed to start.")
        sys.exit(1)

    print("[*] Server is healthy. Commencing API verification...")

    # =========================================================================
    # 1. GET /api/health
    # =========================================================================
    st, d, lat = http_get("/api/health")
    passed = (
        st == 200
        and d.get("status") == "healthy"
        and d.get("database", {}).get("connected") is True
        and d.get("models", {}).get("salary_predictor_loaded") is True
    )
    record_result(
        "/api/health", "GET", "Health check & diagnostic telemetry", "Valid",
        None, 200, st, passed, d,
        "Verifies system health, DB connection, and model loading status", lat
    )

    # =========================================================================
    # 2. GET /api/analytics/overview
    # =========================================================================
    st, d, lat = http_get("/api/analytics/overview")
    passed = (
        st == 200
        and d.get("status") == "success"
        and d.get("summary", {}).get("totalJobsAnalyzed", 0) > 90000
        and len(d.get("locationDemand", [])) > 0
        and len(d.get("experienceDistribution", [])) > 0
        and len(d.get("roleDemand", [])) > 0
    )
    record_result(
        "/api/analytics/overview", "GET", "Consolidated real-time market overview", "Valid",
        None, 200, st, passed, d,
        "Validates precomputed market summary, location hubs, and distributions", lat
    )

    # =========================================================================
    # 3. GET /api/analytics/market-overview (Alias)
    # =========================================================================
    st, d, lat = http_get("/api/analytics/market-overview")
    passed = st == 200 and d.get("status") == "success" and "summary" in d
    record_result(
        "/api/analytics/market-overview", "GET", "Market overview alias endpoint", "Valid",
        None, 200, st, passed, d,
        "Ensures route alias compatibility", lat
    )

    # =========================================================================
    # 4. GET /api/analytics/salary
    # =========================================================================
    st, d, lat = http_get("/api/analytics/salary")
    passed = (
        st == 200
        and d.get("status") == "success"
        and d.get("average_salary_lpa", 0) > 0
        and len(d.get("distribution", [])) > 0
    )
    record_result(
        "/api/analytics/salary", "GET", "Disclosed salary distribution & analytics", "Valid",
        None, 200, st, passed, d,
        "Verifies statistics strictly computed from valid disclosed salaries", lat
    )

    # =========================================================================
    # 5. GET /api/skills/top
    # =========================================================================
    # Scenario A: Default
    st, d, lat = http_get("/api/skills/top")
    passed = st == 200 and isinstance(d, list) and len(d) == 20
    record_result(
        "/api/skills/top", "GET", "Default top skills (limit 20)", "Valid",
        None, 200, st, passed, d,
        "Returns top 20 skills ranked by demand count", lat
    )

    # Scenario B: Parameterized limit
    st, d, lat = http_get("/api/skills/top?limit=5")
    passed = st == 200 and len(d) == 5 and d[0]["demand_job_count"] >= d[1]["demand_job_count"]
    record_result(
        "/api/skills/top", "GET", "Custom limit filter (limit 5)", "Valid",
        {"limit": 5}, 200, st, passed, d,
        "Verifies descending demand ordering and exact count limit", lat
    )

    # Scenario C: Category filter
    st, d, lat = http_get("/api/skills/top?category=Programming%20Language")
    passed = st == 200 and len(d) > 0 and all(item["category"] == "Programming Language" for item in d)
    record_result(
        "/api/skills/top", "GET", "Valid category filter", "Valid",
        {"category": "Programming Language"}, 200, st, passed, d,
        "Ensures category subsetting works correctly", lat
    )

    # Scenario D: Non-existent category
    st, d, lat = http_get("/api/skills/top?category=UnknownCategory123")
    passed = st == 200 and len(d) == 0
    record_result(
        "/api/skills/top", "GET", "Non-existent category filter", "Boundary",
        {"category": "UnknownCategory123"}, 200, st, passed, d,
        "Returns empty array without error", lat
    )

    # Scenario E: Boundary limit violation (max 200)
    st, d, lat = http_get("/api/skills/top?limit=500")
    passed = st == 422
    record_result(
        "/api/skills/top", "GET", "Oversized limit boundary (>200)", "Invalid Input",
        {"limit": 500}, 422, st, passed, d,
        "Enforces Pydantic Query constraint le=200", lat
    )

    # =========================================================================
    # 6. GET /api/skills/categories
    # =========================================================================
    st, d, lat = http_get("/api/skills/categories")
    passed = st == 200 and isinstance(d, list) and len(d) > 0 and "category" in d[0] and "total_demand" in d[0]
    record_result(
        "/api/skills/categories", "GET", "Skill categories with aggregate demand", "Valid",
        None, 200, st, passed, d,
        "Verifies skill counts and total demand across domains", lat
    )

    # =========================================================================
    # 7. GET /api/skills/by-role
    # =========================================================================
    # Scenario A: Valid role name
    st, d, lat = http_get("/api/skills/by-role?role=Data%20Scientist")
    passed = st == 200 and d.get("success") is True and d.get("role_id") == "data_scientist_advanced_analytics" and len(d.get("skills", [])) > 0
    record_result(
        "/api/skills/by-role", "GET", "Valid target role name", "Valid",
        {"role": "Data Scientist"}, 200, st, passed, d,
        "Retrieves empirical benchmark skills for Data Scientist", lat
    )

    # Scenario B: Canonical role ID
    st, d, lat = http_get("/api/skills/by-role?role=backend_core_software_engineering")
    passed = st == 200 and d.get("success") is True and d.get("role_id") == "backend_core_software_engineering"
    record_result(
        "/api/skills/by-role", "GET", "Valid canonical role ID", "Valid",
        {"role": "backend_core_software_engineering"}, 200, st, passed, d,
        "Accepts exact canonical technical role ID", lat
    )

    # Scenario C: Unsupported/non-technical role rejection
    st, d, lat = http_get("/api/skills/by-role?role=Astronaut")
    passed = st == 400
    record_result(
        "/api/skills/by-role", "GET", "Unsupported non-technical role", "Invalid Input",
        {"role": "Astronaut"}, 400, st, passed, d,
        "Rejects unsupported role with 400 Bad Request", lat
    )

    # Scenario D: Missing role parameter (defaults to Data Scientist)
    st, d, lat = http_get("/api/skills/by-role")
    passed = st == 200 and d.get("role_id") == "data_scientist_advanced_analytics"
    record_result(
        "/api/skills/by-role", "GET", "Omitted role parameter", "Valid",
        None, 200, st, passed, d,
        "Applies default query value 'Data Scientist'", lat
    )

    # =========================================================================
    # 8. GET /api/skills/emerging
    # =========================================================================
    # Scenario A: Default
    st, d, lat = http_get("/api/skills/emerging")
    passed = st == 200 and isinstance(d, list) and len(d) > 0 and "momentum_tier" in d[0]
    record_result(
        "/api/skills/emerging", "GET", "Default emerging skills ranking", "Valid",
        None, 200, st, passed, d,
        "Ranks skills by Hiring Momentum & Salary Premium Index", lat
    )

    # Scenario B: Tier filter
    st, d, lat = http_get("/api/skills/emerging?tier=EXPONENTIAL_BREAKOUT")
    passed = st == 200 and isinstance(d, list)
    record_result(
        "/api/skills/emerging", "GET", "Tier filter (EXPONENTIAL_BREAKOUT)", "Valid",
        {"tier": "EXPONENTIAL_BREAKOUT"}, 200, st, passed, d,
        "Filters skills strictly in breakout momentum tier", lat
    )

    # Scenario C: Limit filter
    st, d, lat = http_get("/api/skills/emerging?limit=3")
    passed = st == 200 and len(d) <= 3
    record_result(
        "/api/skills/emerging", "GET", "Custom limit filter (limit 3)", "Valid",
        {"limit": 3}, 200, st, passed, d,
        "Respects maximum result count limit", lat
    )

    # =========================================================================
    # 9. GET /api/jobs
    # =========================================================================
    # Scenario A: Default search
    st, d, lat = http_get("/api/jobs")
    passed = (
        st == 200
        and d.get("total", 0) > 90000
        and d.get("page") == 1
        and len(d.get("jobs", [])) == 20
    )
    sample_valid_job_id = d["jobs"][0]["id"] if (d.get("jobs") and len(d["jobs"]) > 0) else "100125012854"
    record_result(
        "/api/jobs", "GET", "Default job search and pagination", "Valid",
        None, 200, st, passed, d,
        "Returns paginated job postings (page 1, limit 20)", lat
    )

    # Scenario B: Keyword search
    st, d, lat = http_get("/api/jobs?search=python&limit=10")
    passed = st == 200 and len(d.get("jobs", [])) <= 10 and d.get("total") > 0
    record_result(
        "/api/jobs", "GET", "Keyword search across postings ('python')", "Valid",
        {"search": "python", "limit": 10}, 200, st, passed, d,
        "Filters jobs matching title, company, or skills", lat
    )

    # Scenario C: Location filter
    st, d, lat = http_get("/api/jobs?location=Bengaluru&limit=5")
    passed = st == 200 and len(d.get("jobs", [])) == 5 and all("Bengaluru" in j["location"] or "Bangalore" in j["location"] for j in d["jobs"])
    record_result(
        "/api/jobs", "GET", "Metropolitan location filter ('Bengaluru')", "Valid",
        {"location": "Bengaluru", "limit": 5}, 200, st, passed, d,
        "Filters postings by metropolitan cluster", lat
    )

    # Scenario D: Minimum salary filter
    st, d, lat = http_get("/api/jobs?min_salary=15.0&limit=5")
    passed = st == 200 and all(j["salary_max"] is not None and j["salary_max"] >= 15.0 for j in d["jobs"])
    record_result(
        "/api/jobs", "GET", "Minimum disclosed salary filter (>= 15 LPA)", "Valid",
        {"min_salary": 15.0, "limit": 5}, 200, st, passed, d,
        "Filters only listings with disclosed compensation exceeding threshold", lat
    )

    # Scenario E: Work type filter
    st, d, lat = http_get("/api/jobs?work_type=Remote&limit=5")
    passed = st == 200 and all(j["work_type"] == "Remote" for j in d["jobs"])
    record_result(
        "/api/jobs", "GET", "Work type filter ('Remote')", "Valid",
        {"work_type": "Remote", "limit": 5}, 200, st, passed, d,
        "Filters remote working opportunities", lat
    )

    # Scenario F: Sorting order (salary_desc)
    st, d, lat = http_get("/api/jobs?sort_by=salary_desc&limit=5")
    sals = [j["salary_max"] for j in d.get("jobs", []) if j.get("salary_max") is not None]
    passed = st == 200 and sals == sorted(sals, reverse=True)
    record_result(
        "/api/jobs", "GET", "Sort by salary descending", "Valid",
        {"sort_by": "salary_desc", "limit": 5}, 200, st, passed, d,
        "Orders jobs highest disclosed salary first", lat
    )

    # Scenario G: Boundary pagination beyond total pages
    st, d, lat = http_get("/api/jobs?page=999999&limit=20")
    passed = st == 200 and d.get("page") == d.get("total_pages")
    record_result(
        "/api/jobs", "GET", "Page number exceeding max total pages", "Boundary",
        {"page": 999999}, 200, st, passed, d,
        "Clamps page index gracefully to total_pages", lat
    )

    # Scenario H: Oversized limit query parameter (>100)
    st, d, lat = http_get("/api/jobs?limit=500")
    passed = st == 422
    record_result(
        "/api/jobs", "GET", "Oversized page limit (>100)", "Invalid Input",
        {"limit": 500}, 422, st, passed, d,
        "Rejects limit > 100 with HTTP 422 Unprocessable Entity", lat
    )

    # =========================================================================
    # 10. GET /api/jobs/{job_id}
    # =========================================================================
    # First obtain a known valid job ID from default search
    valid_id = sample_valid_job_id
    st, d_single, lat = http_get(f"/api/jobs/{valid_id}")
    passed = st == 200 and d_single.get("id") == str(valid_id) and "title" in d_single
    record_result(
        "/api/jobs/{job_id}", "GET", "Valid single job record retrieval", "Valid",
        {"job_id": valid_id}, 200, st, passed, d_single,
        "Returns complete job details including skills and company initials", lat
    )

    # Non-existent job ID
    st, d_err, lat = http_get("/api/jobs/NON_EXISTENT_ID_99999999")
    passed = st == 404
    record_result(
        "/api/jobs/{job_id}", "GET", "Non-existent job record ID", "Error Handling",
        {"job_id": "NON_EXISTENT_ID_99999999"}, 404, st, passed, d_err,
        "Returns HTTP 404 Not Found", lat
    )

    # =========================================================================
    # 11. POST /api/classify/job
    # =========================================================================
    # Scenario A: Valid technical job
    p_job = {
        "title": "Staff Backend Engineer",
        "skills": ["Java", "Spring Boot", "Microservices", "Docker"],
        "description": "Design and architect highly scalable backend distributed systems.",
    }
    st, d, lat = http_post_json("/api/classify/job", p_job)
    passed = (
        st == 200
        and d.get("predicted_role") == "backend_core_software_engineering"
        and d.get("confidence", 0) > 0.4
        and d.get("method") in ("ml_logistic_regression", "rule_baseline_fallback")
    )
    record_result(
        "/api/classify/job", "POST", "Valid backend job classification", "Valid",
        p_job, 200, st, passed, d,
        "Accurately maps title and skills to backend career family", lat
    )

    # Scenario B: Data Scientist job
    p_ds = {
        "title": "Senior Data Scientist",
        "skills": ["Python", "Machine Learning", "PyTorch", "Statistics"],
        "description": "Develop and deploy deep neural network models in production.",
    }
    st, d, lat = http_post_json("/api/classify/job", p_ds)
    passed = st == 200 and d.get("predicted_role") == "data_scientist_advanced_analytics"
    record_result(
        "/api/classify/job", "POST", "Valid data scientist job classification", "Valid",
        p_ds, 200, st, passed, d,
        "Accurately classifies data science profile", lat
    )

    # Scenario C: Empty payload fallback
    st, d, lat = http_post_json("/api/classify/job", {})
    passed = st == 200 and "predicted_role" in d and d.get("predicted_role") in ("other_unclassified", "non_tech_corporate_operations")
    record_result(
        "/api/classify/job", "POST", "Empty job payload fallback", "Boundary",
        {}, 200, st, passed, d,
        "Safely handles empty payload and returns fallback role", lat
    )

    # Scenario D: Malformed payload types
    st, d, lat = http_post_json("/api/classify/job", {"skills": "NotAList"})
    passed = st == 422
    record_result(
        "/api/classify/job", "POST", "Malformed payload types (string instead of list)", "Invalid Input",
        {"skills": "NotAList"}, 422, st, passed, d,
        "Rejects invalid schema with HTTP 422", lat
    )

    # =========================================================================
    # 12. POST /api/classify/batch
    # =========================================================================
    # Scenario A: Valid batch
    batch_jobs = [
        {"id": "b1", "title": "DevOps Engineer", "skills": ["Kubernetes", "AWS"]},
        {"id": "b2", "title": "QA Automation Engineer", "skills": ["Selenium", "Java"]},
        {"id": "b3", "title": "Data Analyst", "skills": ["SQL", "Power BI", "Excel"]},
    ]
    st, d, lat = http_post_json("/api/classify/batch", {"jobs": batch_jobs})
    passed = (
        st == 200
        and d.get("total") == 3
        and len(d.get("predictions", [])) == 3
        and d["predictions"][0]["id"] == "b1"
        and d["predictions"][1]["id"] == "b2"
        and d["predictions"][2]["id"] == "b3"
    )
    record_result(
        "/api/classify/batch", "POST", "Valid batch classification (3 items)", "Valid",
        {"jobs": len(batch_jobs)}, 200, st, passed, d,
        "Preserves client IDs and returns batched role predictions", lat
    )

    # Scenario B: Empty batch rejection
    st, d, lat = http_post_json("/api/classify/batch", {"jobs": []})
    passed = st == 400
    record_result(
        "/api/classify/batch", "POST", "Empty batch rejection", "Error Handling",
        {"jobs": []}, 400, st, passed, d,
        "Rejects empty batch list with HTTP 400 Bad Request", lat
    )

    # Scenario C: Oversized batch (>100 jobs)
    oversized = [{"id": f"job_{i}", "title": "Engineer"} for i in range(101)]
    st, d, lat = http_post_json("/api/classify/batch", {"jobs": oversized})
    passed = st in (400, 422)
    record_result(
        "/api/classify/batch", "POST", "Oversized batch (>100 items)", "Boundary",
        {"jobs": 101}, 400, st, passed, d,
        "Enforces documented 100-job batch limit", lat
    )

    # =========================================================================
    # 13. GET /api/classify/taxonomy
    # =========================================================================
    st, d, lat = http_get("/api/classify/taxonomy")
    passed = (
        st == 200
        and "role_families" in d
        and len(d["role_families"]) == 11
        and "frontend_filter_mapping" in d
    )
    record_result(
        "/api/classify/taxonomy", "GET", "Role taxonomy definitions", "Valid",
        None, 200, st, passed, d,
        "Returns all 11 canonical taxonomy families and frontend mappings", lat
    )

    # =========================================================================
    # 14. GET /api/classify/info
    # =========================================================================
    st, d, lat = http_get("/api/classify/info")
    passed = (
        st == 200
        and d.get("status") in ("loaded", "fallback_rules")
        and "model_version" in d
        and "classes" in d
        and len(d["classes"]) == 11
    )
    record_result(
        "/api/classify/info", "GET", "Classifier model metadata & training card", "Valid",
        None, 200, st, passed, d,
        "Returns model version, vocabulary size, and class labels", lat
    )

    # =========================================================================
    # 15. POST /api/resume/extract-skills
    # =========================================================================
    # Scenario A: Valid Plain Text upload
    txt_content = b"Candidate Resume\nSkills: Python, SQL, Docker, AWS, Scikit-learn, React.\nExperience: 3 years building microservices."
    st, d, lat = http_post_multipart("/api/resume/extract-skills", "resume.txt", txt_content, "text/plain")
    passed = st == 200 and d.get("extracted_skill_count", 0) >= 4 and "Python" in d.get("skill_names", [])
    record_result(
        "/api/resume/extract-skills", "POST", "Valid Plain Text (.txt) resume upload", "Valid",
        {"filename": "resume.txt", "size": len(txt_content)}, 200, st, passed, d,
        "Parses hard skills with categorized evidence strictly in-memory", lat
    )

    # Scenario B: Empty file upload (0 bytes)
    st, d, lat = http_post_multipart("/api/resume/extract-skills", "empty.txt", b"", "text/plain")
    passed = st == 400
    record_result(
        "/api/resume/extract-skills", "POST", "Empty file upload (0 bytes)", "Error Handling",
        {"filename": "empty.txt", "size": 0}, 400, st, passed, d,
        "Rejects empty resume upload with HTTP 400 Bad Request", lat
    )

    # Scenario C: Unsupported extension (.exe)
    st, d, lat = http_post_multipart("/api/resume/extract-skills", "malicious.exe", b"MZDummyHeader", "application/octet-stream")
    passed = st == 400
    record_result(
        "/api/resume/extract-skills", "POST", "Unsupported file extension (.exe)", "Error Handling",
        {"filename": "malicious.exe"}, 400, st, passed, d,
        "Enforces allowed extensions (.pdf, .docx, .txt)", lat
    )

    # Scenario D: File exceeding size limit (>5 MB)
    large_payload = b"A" * (5 * 1024 * 1024 + 1024)
    st, d, lat = http_post_multipart("/api/resume/extract-skills", "huge.txt", large_payload, "text/plain")
    passed = st in (400, 413)
    record_result(
        "/api/resume/extract-skills", "POST", "Oversized file upload (>5 MB)", "Boundary",
        {"filename": "huge.txt", "size": len(large_payload)}, 413, st, passed, d,
        "Rejects file exceeding 5 MB limit with HTTP 413 Content Too Large", lat
    )

    # Scenario E: Corrupted PDF bytes
    st, d, lat = http_post_multipart("/api/resume/extract-skills", "corrupt.pdf", b"%PDF-1.4 Corrupted content without EOF", "application/pdf")
    passed = st in (200, 400) # Returns 400 or graceful empty extraction with warnings
    record_result(
        "/api/resume/extract-skills", "POST", "Corrupted PDF byte payload", "Error Handling",
        {"filename": "corrupt.pdf"}, 400, st, passed, d,
        "Safely handles PDF corruption without crashing server", lat
    )

    # =========================================================================
    # 16. POST /api/recommendations/career
    # =========================================================================
    # Scenario A: Valid skills + preferred role
    rec_p = {
        "skills": ["Java", "Spring Boot", "Microservices", "Docker", "SQL"],
        "preferred_role": "Backend Developer",
    }
    st, d, lat = http_post_json("/api/recommendations/career", rec_p)
    passed = (
        st == 200
        and d.get("status") == "success"
        and len(d.get("recommendations", [])) == 8
        and d["recommendations"][0]["role_id"] == "backend_core_software_engineering"
        and d["recommendations"][0]["match_score"] > 0
    )
    record_result(
        "/api/recommendations/career", "POST", "Valid career recommendations request", "Valid",
        rec_p, 200, st, passed, d,
        "Ranks 8 technical careers by demand-weighted cosine overlap", lat
    )

    # Scenario B: Incomplete profile (empty skills)
    st, d, lat = http_post_json("/api/recommendations/career", {"skills": []})
    passed = st == 200 and d.get("status") == "incomplete_profile" and len(d.get("recommendations", [])) == 8
    record_result(
        "/api/recommendations/career", "POST", "Empty student skills profile", "Boundary",
        {"skills": []}, 200, st, passed, d,
        "Returns unranked baseline profiles with incomplete_profile status", lat
    )

    # Scenario C: Unrecognized skills
    rec_unseen = {"skills": ["QuantumAlchemy", "CryptoTeleportation"]}
    st, d, lat = http_post_json("/api/recommendations/career", rec_unseen)
    passed = st == 200 and len(d.get("recommendations", [])) == 8
    record_result(
        "/api/recommendations/career", "POST", "Unrecognized skills handling", "Boundary",
        rec_unseen, 200, st, passed, d,
        "Gracefully handles unseen skills without KeyError", lat
    )

    # =========================================================================
    # 17. POST /api/skills/gap
    # =========================================================================
    # Scenario A: Valid role + partial skills
    gap_p = {
        "target_role": "Data Scientist",
        "skills": ["Python", "SQL"],
    }
    st, d, lat = http_post_json("/api/skills/gap", gap_p)
    passed = (
        st == 200
        and d.get("role_id") == "data_scientist_advanced_analytics"
        and 0.0 <= d.get("readiness_score", -1) <= 100.0
        and len(d.get("acquired_skills", [])) > 0
        and len(d.get("missing_critical_skills", [])) > 0
    )
    record_result(
        "/api/skills/gap", "POST", "Valid skill-gap diagnosis", "Valid",
        gap_p, 200, st, passed, d,
        "Calculates readiness score and partitions acquired vs missing skills", lat
    )

    # Scenario B: Unsupported target role
    st, d, lat = http_post_json("/api/skills/gap", {"target_role": "Astronaut", "skills": ["Python"]})
    passed = st == 400
    record_result(
        "/api/skills/gap", "POST", "Unsupported target role", "Invalid Input",
        {"target_role": "Astronaut"}, 400, st, passed, d,
        "Rejects unsupported target role with 400 Bad Request", lat
    )

    # Scenario C: Missing required target_role field
    st, d, lat = http_post_json("/api/skills/gap", {"skills": ["Python"]})
    passed = st == 422
    record_result(
        "/api/skills/gap", "POST", "Missing target_role field", "Missing Field",
        {"skills": ["Python"]}, 422, st, passed, d,
        "Enforces mandatory target_role with HTTP 422 Unprocessable Entity", lat
    )

    # Scenario D: All skills acquired
    gap_full = {
        "target_role": "Data Scientist",
        "skills": ["Data Science", "Machine Learning", "Python", "SQL", "Statistics", "Deep Learning"],
    }
    st, d, lat = http_post_json("/api/skills/gap", gap_full)
    passed = st == 200 and d.get("readiness_score", 0) >= 80.0
    record_result(
        "/api/skills/gap", "POST", "Full skill match diagnosis", "Boundary",
        gap_full, 200, st, passed, d,
        "Reflects high readiness score when core critical skills are acquired", lat
    )

    # =========================================================================
    # 18. POST /api/roadmap/generate
    # =========================================================================
    # Scenario A: Valid roadmap request
    road_p = {
        "target_role": "data_engineer_big_data_platform",
        "skills": ["SQL", "Python"],
    }
    st, d, lat = http_post_json("/api/roadmap/generate", road_p)
    passed = (
        st == 200
        and d.get("role_id") == "data_engineer_big_data_platform"
        and len(d.get("milestones", [])) > 0
        and d.get("total_estimated_weeks", 0) > 0
        and "completion_criteria" in d["milestones"][0]
    )
    record_result(
        "/api/roadmap/generate", "POST", "Valid milestone roadmap generation", "Valid",
        road_p, 200, st, passed, d,
        "Generates sequenced milestones with realistic timelines and resources", lat
    )

    # Scenario B: Invalid target role
    st, d, lat = http_post_json("/api/roadmap/generate", {"target_role": "Singer", "skills": []})
    passed = st == 400
    record_result(
        "/api/roadmap/generate", "POST", "Invalid target role for roadmap", "Invalid Input",
        {"target_role": "Singer"}, 400, st, passed, d,
        "Rejects unsupported role with 400 Bad Request", lat
    )

    # =========================================================================
    # 19. GET /api/recommendations/roles
    # =========================================================================
    st, d, lat = http_get("/api/recommendations/roles")
    passed = (
        st == 200
        and isinstance(d, list)
        and len(d) == 8
        and all("role_id" in r and "role_name" in r and "frontend_filter_key" in r for r in d)
    )
    record_result(
        "/api/recommendations/roles", "GET", "Supported technical career catalog", "Valid",
        None, 200, st, passed, d,
        "Returns 8 canonical technical roles with metadata and UI filter keys", lat
    )

    # =========================================================================
    # 20. POST /api/salary/predict
    # =========================================================================
    # Scenario A: Valid technical software engineering request
    sal_p = {
        "role": "Software Engineer",
        "experience_years": 3.0,
        "location": "Bengaluru",
        "skills": ["Java", "Spring Boot", "SQL"],
    }
    st, d, lat = http_post_json("/api/salary/predict", sal_p)
    passed = (
        st == 200
        and d.get("predicted_salary_lpa", 0) > 0
        and d.get("coverage_level_pct") == 90.0
        and "conformal_interval_lpa" in d
        and d["conformal_interval_lpa"]["max_lpa"] >= d["conformal_interval_lpa"]["min_lpa"]
    )
    record_result(
        "/api/salary/predict", "POST", "Valid software engineer compensation prediction", "Valid",
        sal_p, 200, st, passed, d,
        "Returns Ridge prediction with 90% calibrated conformal prediction interval", lat
    )

    # Scenario B: Valid Data Scientist request
    sal_ds = {
        "role": "Data Scientist",
        "experience_years": 5.0,
        "location": "Hyderabad",
        "skills": ["Python", "Machine Learning", "PyTorch"],
    }
    st, d, lat = http_post_json("/api/salary/predict", sal_ds)
    passed = st == 200 and d.get("resolved_role_family") in ("data_scientist_advanced_analytics", "data_science_ml_ai")
    record_result(
        "/api/salary/predict", "POST", "Valid data scientist compensation prediction", "Valid",
        sal_ds, 200, st, passed, d,
        "Correctly maps to data science track and calculates metro location index", lat
    )

    # Scenario C: Non-technical role rejection (HR Recruiter)
    sal_hr = {
        "role": "HR Executive / Recruiter",
        "experience_years": 4.0,
        "location": "Mumbai",
        "skills": ["Communication", "Payroll"],
    }
    st, d, lat = http_post_json("/api/salary/predict", sal_hr)
    passed = st == 400 and "calibrated exclusively for core technical" in str(d.get("detail", ""))
    record_result(
        "/api/salary/predict", "POST", "Non-technical role rejection ('HR Recruiter')", "Error Handling",
        sal_hr, 400, st, passed, d,
        "Rejects non-technical role with informative HTTP 400 explanation", lat
    )

    # Scenario D: Non-technical role rejection (Accountant / Finance)
    sal_acc = {
        "role": "Chartered Accountant / Finance Lead",
        "experience_years": 6.0,
        "location": "Delhi",
        "skills": ["Tally", "GST"],
    }
    st, d, lat = http_post_json("/api/salary/predict", sal_acc)
    passed = st == 400
    record_result(
        "/api/salary/predict", "POST", "Non-technical role rejection ('Accountant')", "Error Handling",
        sal_acc, 400, st, passed, d,
        "Safely rejects non-technical finance roles", lat
    )

    # Scenario E: Negative experience boundary (<0)
    st, d, lat = http_post_json("/api/salary/predict", {"role": "Software Engineer", "experience_years": -3.0})
    passed = st in (400, 422)
    record_result(
        "/api/salary/predict", "POST", "Negative experience boundary (<0)", "Boundary",
        {"experience_years": -3.0}, 400, st, passed, d,
        "Rejects negative experience value with HTTP 400/422", lat
    )

    # Scenario F: Extreme experience boundary (>40 yrs)
    st, d, lat = http_post_json("/api/salary/predict", {"role": "Software Engineer", "experience_years": 50.0})
    passed = st in (400, 422)
    record_result(
        "/api/salary/predict", "POST", "Extreme experience boundary (>40 yrs)", "Boundary",
        {"experience_years": 50.0}, 400, st, passed, d,
        "Rejects experience > 40.0 yrs", lat
    )

    # Scenario G: Empty role string
    st, d, lat = http_post_json("/api/salary/predict", {"role": "", "experience_years": 2.0})
    passed = st in (400, 422)
    record_result(
        "/api/salary/predict", "POST", "Empty role string", "Invalid Input",
        {"role": ""}, 400, st, passed, d,
        "Rejects empty string as target role", lat
    )

    # =========================================================================
    # 21. GET /api/salary/metadata
    # =========================================================================
    st, d, lat = http_get("/api/salary/metadata")
    passed = (
        st == 200
        and d.get("model_version") == "2.0.0"
        and "champion_model_name" in d
        and "champion_metrics" in d
        and "top_features" in d
    )
    record_result(
        "/api/salary/metadata", "GET", "Salary model card & validation metrics", "Valid",
        None, 200, st, passed, d,
        "Exposes Ridge champion validation metrics (GroupKFold MAE and R2)", lat
    )

    # Cleanup server
    print("[*] Completed all test scenarios. Stopping server...")
    server.should_exit = True
    thread.join(timeout=3.0)

    # Write output JSON
    out_file = PROJECT_ROOT / "docs" / "testing" / "step3_api_test_results.json"
    out_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"[*] Results persisted to {out_file}")

    total = len(results)
    passed_count = sum(1 for r in results if r["status"] == "PASS")
    failed_count = total - passed_count
    print(f"\n==========================================")
    print(f"API TEST SUMMARY: {passed_count}/{total} PASSED ({passed_count/total*100:.1f}%)")
    print(f"==========================================")


if __name__ == "__main__":
    run_all_tests()
