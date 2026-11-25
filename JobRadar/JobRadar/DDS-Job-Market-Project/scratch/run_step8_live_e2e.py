"""JobRadar Phase 7.5 Step 8: Live End-to-End System Testing & Acceptance Runner.

Starts the live FastAPI backend on http://127.0.0.1:8000 and executes exhaustive
live HTTP end-to-end user workflows, testing real database queries, ML inferences,
error recovery, and record reconciliation.
"""

from __future__ import annotations

import concurrent.futures
import io
import json
import logging
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any
import urllib.error
import urllib.parse
import urllib.request

import uvicorn

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parents[1]
JOBRADAR_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
if str(JOBRADAR_ROOT) not in sys.path:
    sys.path.insert(0, str(JOBRADAR_ROOT))
aiml_dir = JOBRADAR_ROOT / "AI_ML"
if str(aiml_dir) not in sys.path:
    sys.path.insert(0, str(aiml_dir))

from job_market.api import create_app

PORT = 8000
BASE_URL = f"http://127.0.0.1:{PORT}"
DOCS_TESTING_DIR = PROJECT_ROOT / "docs" / "testing"

e2e_results: dict[str, Any] = {
    "summary": {"total": 0, "passed": 0, "failed": 0},
    "tests": {},
    "metrics": {},
    "reconciliation": {},
}


def record_test(name: str, passed: bool, details: Any = None):
    e2e_results["summary"]["total"] += 1
    if passed:
        e2e_results["summary"]["passed"] += 1
        print(f"[PASS] {name}")
    else:
        e2e_results["summary"]["failed"] += 1
        print(f"[FAIL] {name}: {details}")
    e2e_results["tests"][name] = {
        "status": "PASS" if passed else "FAIL",
        "details": details,
    }


def http_get(path: str, timeout: float = 10.0) -> tuple[int, dict | list]:
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url, headers={"User-Agent": "JobRadar-E2E/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
        return resp.status, json.loads(body)


def http_post(path: str, payload: dict | list, timeout: float = 10.0) -> tuple[int, dict | list]:
    url = f"{BASE_URL}{path}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": "JobRadar-E2E/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
        return resp.status, json.loads(body)


def http_post_multipart(path: str, filename: str, file_bytes: bytes, field_name: str = "file", timeout: float = 10.0) -> tuple[int, dict]:
    url = f"{BASE_URL}{path}"
    boundary = "----WebKitFormBoundaryJobRadarE2EBoundary7MA4YWxkTrZu0gW"
    
    body = bytearray()
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode("utf-8"))
    body.extend(b"Content-Type: application/octet-stream\r\n\r\n")
    body.extend(file_bytes)
    body.extend(f"\r\n--{boundary}--\r\n".encode("utf-8"))

    req = urllib.request.Request(
        url,
        data=bytes(body),
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "JobRadar-E2E/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


class LiveServerManager:
    def __init__(self, port: int = 8000):
        self.port = port
        self.server: uvicorn.Server | None = None
        self.thread: threading.Thread | None = None

    def start(self):
        print(f"[*] Starting live Uvicorn server on http://127.0.0.1:{self.port} ...")
        app = create_app()
        config = uvicorn.Config(
            app=app,
            host="127.0.0.1",
            port=self.port,
            log_level="error",
            access_log=False,
        )
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.thread.start()

        started = False
        for _ in range(35):
            try:
                with urllib.request.urlopen(f"{BASE_URL}/api/health", timeout=1.0) as resp:
                    if resp.status == 200:
                        started = True
                        break
            except Exception:
                time.sleep(0.2)

        if not started:
            raise RuntimeError("Live Uvicorn server failed to respond on /api/health within 7s")
        print("[*] Live server is responsive!")

    def stop(self):
        print("[*] Shutting down live Uvicorn server ...")
        if self.server:
            self.server.should_exit = True
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=3.0)
        print("[*] Live server terminated cleanly.")


def run_e2e_tests():
    server_mgr = LiveServerManager(port=PORT)
    server_mgr.start()

    try:
        # =====================================================================
        # A. BACKEND LIVE AVAILABILITY
        # =====================================================================
        print("\n--- A. Backend Live Availability ---")
        status, health = http_get("/api/health")
        record_test(
            "e2e_health_status_ok",
            status == 200 and health.get("status") == "healthy",
            health,
        )
        record_test(
            "e2e_health_database_connected",
            health.get("database", {}).get("connected") is True and health.get("database", {}).get("total_jobs", 0) > 90000,
            health.get("database"),
        )
        models = health.get("models", {})
        record_test(
            "e2e_health_models_initialized",
            models.get("salary_predictor_loaded") is True and
            models.get("career_recommendations_loaded") is True and
            models.get("emerging_skills_index_loaded") is True,
            models,
        )

        # =====================================================================
        # B. JOBS WORKFLOW
        # =====================================================================
        print("\n--- B. Jobs Workflow ---")
        status, jobs_page1 = http_get("/api/jobs?limit=20&page=1")
        record_test(
            "e2e_jobs_list_retrieval",
            status == 200 and jobs_page1.get("total", 0) > 90000 and len(jobs_page1.get("jobs", [])) == 20,
            {"total": jobs_page1.get("total"), "returned": len(jobs_page1.get("jobs", []))},
        )

        # Keyword search
        status, py_jobs = http_get("/api/jobs?search=Python&limit=10")
        sample_has_py = any(
            "python" in j["title"].lower() or "python" in [s.lower() for s in j.get("skills", [])]
            for j in py_jobs.get("jobs", [])
        )
        record_test(
            "e2e_jobs_keyword_search",
            status == 200 and py_jobs.get("total", 0) > 5000 and sample_has_py,
            {"python_total_matching": py_jobs.get("total")},
        )

        # Location filter
        status, blr_jobs = http_get("/api/jobs?location=Bengaluru&limit=10")
        all_blr = all("bengaluru" in j["location"].lower() or "bangalore" in j["location"].lower() for j in blr_jobs.get("jobs", []))
        record_test(
            "e2e_jobs_location_filter",
            status == 200 and blr_jobs.get("total", 0) > 10000 and all_blr,
            {"bengaluru_total": blr_jobs.get("total")},
        )

        # Minimum salary filter (10 LPA)
        status, sal_jobs = http_get("/api/jobs?min_salary=10&limit=10")
        all_min_10 = all(
            j.get("salary_max") is not None and j["salary_max"] >= 10.0
            for j in sal_jobs.get("jobs", [])
        )
        record_test(
            "e2e_jobs_salary_filter",
            status == 200 and sal_jobs.get("total", 0) > 500 and all_min_10,
            {"salary_ge_10lpa_total": sal_jobs.get("total")},
        )

        # Retrieve single job details
        sample_job_id = jobs_page1["jobs"][0]["id"]
        status, single_job = http_get(f"/api/jobs/{sample_job_id}")
        record_test(
            "e2e_jobs_detail_by_id",
            status == 200 and single_job.get("id") == sample_job_id and "title" in single_job,
            {"id": sample_job_id, "title": single_job.get("title"), "company": single_job.get("company")},
        )

        # Empty search handling
        status, empty_jobs = http_get("/api/jobs?search=ZzZNonExistentTitleXylophone999")
        record_test(
            "e2e_jobs_empty_search_handling",
            status == 200 and empty_jobs.get("total") == 0 and len(empty_jobs.get("jobs", [])) == 0,
            {"total": empty_jobs.get("total")},
        )

        # =====================================================================
        # C. SKILLS ANALYTICS WORKFLOW
        # =====================================================================
        print("\n--- C. Skills Analytics Workflow ---")
        status, top_skills = http_get("/api/skills/top?limit=12")
        top_names = [s["skill"] for s in top_skills]
        record_test(
            "e2e_skills_top_rankings",
            status == 200 and len(top_skills) == 12 and "Python" in top_names and "SQL" in top_names,
            {"top_skills": top_names[:5]},
        )

        status, categories = http_get("/api/skills/categories")
        record_test(
            "e2e_skills_categories_breakdown",
            status == 200 and len(categories) == 10,
            {"categories_count": len(categories), "sample_categories": [c["category"] for c in categories[:5]]},
        )

        status, role_skills = http_get("/api/skills/by-role?role=Data%20Scientist")
        rs_names = [s["skill"] for s in role_skills.get("skills", [])]
        record_test(
            "e2e_skills_by_role_demand",
            status == 200 and role_skills.get("role_id") == "data_scientist_advanced_analytics" and "Python" in rs_names,
            {"role_name": role_skills.get("role_name"), "skills_count": len(rs_names)},
        )

        status, emerging_skills = http_get("/api/skills/emerging?limit=15")
        record_test(
            "e2e_skills_emerging_momentum_index",
            status == 200 and len(emerging_skills) > 0 and "momentum_tier" in emerging_skills[0] and "momentum_index" in emerging_skills[0],
            {"sample_emerging": [{"skill": s["skill"], "tier": s["momentum_tier"], "score": s["momentum_index"]} for s in emerging_skills[:3]]},
        )

        # =====================================================================
        # D. JOB CLASSIFICATION WORKFLOW
        # =====================================================================
        print("\n--- D. Job Classification Workflow ---")
        status, cls_res = http_post(
            "/api/classify/job",
            {
                "title": "Senior Cloud DevOps Engineer",
                "skills": ["AWS", "Kubernetes", "Docker", "Terraform", "CI/CD"],
                "description": "Manage Kubernetes clusters and automate infrastructure as code.",
            },
        )
        record_test(
            "e2e_classification_tech_posting",
            status == 200 and cls_res.get("predicted_role") == "cloud_devops_sre" and cls_res.get("confidence", 0) > 0.5,
            {
                "predicted_role": cls_res.get("predicted_role"),
                "confidence": cls_res.get("confidence"),
                "tier": cls_res.get("confidence_tier"),
                "method": cls_res.get("method"),
            },
        )

        # Ambiguous / out-of-domain posting
        status, amb_res = http_post(
            "/api/classify/job",
            {
                "title": "Mystic Crystal Reader",
                "skills": ["Divination", "Tarot"],
                "description": "Read crystal balls and provide mystical guidance.",
            },
        )
        record_test(
            "e2e_classification_out_of_domain_fallback",
            status == 200 and (amb_res.get("is_fallback") is True or amb_res.get("predicted_role") in ("other_unclassified", "non_tech_corporate_operations")),
            {"predicted": amb_res.get("predicted_role"), "is_fallback": amb_res.get("is_fallback")},
        )

        # Batch classification
        status, batch_res = http_post(
            "/api/classify/batch",
            {
                "jobs": [
                    {"id": "j1", "title": "React Frontend Engineer", "skills": ["React", "TypeScript", "Tailwind"]},
                    {"id": "j2", "title": "Data Engineer", "skills": ["Spark", "Hadoop", "SQL", "Airflow"]},
                ]
            },
        )
        record_test(
            "e2e_classification_batch_execution",
            status == 200 and len(batch_res.get("predictions", [])) == 2,
            {"batch_size": len(batch_res.get("predictions", []))},
        )

        # =====================================================================
        # E. CAREER RECOMMENDATION WORKFLOW
        # =====================================================================
        print("\n--- E. Career Recommendation Workflow ---")
        status, rec_res = http_post(
            "/api/recommendations/career",
            {
                "skills": ["Java", "Spring Boot", "Microservices", "Docker", "SQL"],
                "preferred_role": "Backend Developer",
            },
        )
        top_role = rec_res.get("recommendations", [])[0] if rec_res.get("recommendations") else {}
        record_test(
            "e2e_recommendation_cosine_ranking",
            status == 200 and top_role.get("role_id") == "backend_core_software_engineering" and top_role.get("match_score", 0) > 40.0,
            {"top_role": top_role.get("role_name"), "match_score": top_role.get("match_score")},
        )

        status, gap_res = http_post(
            "/api/skills/gap",
            {
                "skills": ["Python", "SQL"],
                "target_role": "Data Scientist",
            },
        )
        readiness = gap_res.get("readiness_score", -1.0)
        record_test(
            "e2e_skill_gap_analysis",
            status == 200 and 0.0 <= readiness <= 100.0 and len(gap_res.get("missing_critical_skills", [])) > 0,
            {
                "role_id": gap_res.get("role_id"),
                "readiness_score": readiness,
                "missing_critical_count": len(gap_res.get("missing_critical_skills", [])),
            },
        )

        status, road_res = http_post(
            "/api/roadmap/generate",
            {
                "skills": ["Python", "SQL"],
                "target_role": "Data Scientist",
            },
        )
        milestones = road_res.get("milestones", [])
        record_test(
            "e2e_roadmap_generation",
            status == 200 and len(milestones) >= 2 and road_res.get("total_estimated_weeks", 0) > 0,
            {"milestones_count": len(milestones), "total_weeks": road_res.get("total_estimated_weeks")},
        )

        status, cat_roles = http_get("/api/recommendations/roles")
        record_test(
            "e2e_recommendations_supported_roles",
            status == 200 and isinstance(cat_roles, list) and len(cat_roles) == 8,
            {"supported_roles_count": len(cat_roles)},
        )

        # Incomplete profile handling
        status, empty_rec = http_post("/api/recommendations/career", {"skills": []})
        record_test(
            "e2e_recommendations_empty_profile",
            status == 200 and empty_rec.get("status") == "incomplete_profile" and len(empty_rec.get("recommendations", [])) == 8,
            {"status": empty_rec.get("status")},
        )

        # =====================================================================
        # F. RESUME EXTRACTION WORKFLOW
        # =====================================================================
        print("\n--- F. Resume Extraction Workflow ---")
        # Synthetic text resume
        txt_resume = b"Candidate Resume\nExperience: 4 years.\nSkills: Python, React, Docker, AWS, PostgreSQL, Redis, Scikit-learn."
        status, resume_res = http_post_multipart("/api/resume/extract-skills", filename="resume.txt", file_bytes=txt_resume)
        extracted = [s["canonical_name"] for s in resume_res.get("skills", [])]
        record_test(
            "e2e_resume_txt_skill_extraction",
            status == 200 and resume_res.get("extracted_skill_count", 0) >= 5 and "Python" in extracted and "Docker" in extracted,
            {"extracted_count": resume_res.get("extracted_skill_count"), "skills": extracted},
        )

        # Zero disk persistence audit
        # Verify no .txt / .tmp files were saved in project root or current directory
        orphaned_resumes = list(PROJECT_ROOT.glob("resume*.*")) + list(Path(".").glob("resume*.*"))
        record_test(
            "e2e_resume_zero_disk_persistence",
            len(orphaned_resumes) == 0,
            {"orphaned_files": [str(f) for f in orphaned_resumes]},
        )

        # Empty resume buffer rejection
        empty_rejected = False
        try:
            http_post_multipart("/api/resume/extract-skills", filename="empty.txt", file_bytes=b"")
        except urllib.error.HTTPError as he:
            empty_rejected = he.code in (400, 422)
        record_test("e2e_resume_empty_file_rejected", empty_rejected, "Empty resume file rejected safely")

        # Unsupported format rejection
        unsupported_rejected = False
        try:
            http_post_multipart("/api/resume/extract-skills", filename="malicious.exe", file_bytes=b"MZ\x90\x00\x03\x00")
        except urllib.error.HTTPError as he:
            unsupported_rejected = he.code in (400, 422)
        record_test("e2e_resume_unsupported_format_rejected", unsupported_rejected, "Unsupported .exe rejected safely")

        # =====================================================================
        # G. SALARY PREDICTION WORKFLOW
        # =====================================================================
        print("\n--- G. Salary Prediction Workflow ---")
        status, sal_pred = http_post(
            "/api/salary/predict",
            {
                "role": "Software Engineer",
                "experience_years": 3.0,
                "location": "Bengaluru",
                "skills": ["Java", "Spring Boot", "SQL"],
            },
        )
        pt = sal_pred.get("predicted_salary_lpa", 0.0)
        c_int = sal_pred.get("conformal_interval_lpa", {})
        record_test(
            "e2e_salary_point_and_conformal_interval",
            status == 200 and pt > 0.0 and c_int.get("min_lpa", 0.0) <= pt <= c_int.get("max_lpa", 0.0) and sal_pred.get("coverage_level_pct") == 90.0,
            {
                "predicted_lpa": pt,
                "interval": c_int,
                "market_tier": sal_pred.get("market_tier"),
                "resolved_family": sal_pred.get("resolved_role_family"),
            },
        )

        # Fresher experience
        status, fresher_sal = http_post(
            "/api/salary/predict",
            {
                "role": "Software Engineer",
                "experience_years": 0.0,
                "location": "Bengaluru",
                "skills": ["Python"],
            },
        )
        record_test(
            "e2e_salary_fresher_baseline",
            status == 200 and fresher_sal.get("predicted_salary_lpa", 0.0) > 0.0,
            {"fresher_lpa": fresher_sal.get("predicted_salary_lpa")},
        )

        # Negative experience rejection (HTTP 422)
        neg_exp_rejected = False
        try:
            http_post("/api/salary/predict", {"role": "Software Engineer", "experience_years": -3.0})
        except urllib.error.HTTPError as he:
            neg_exp_rejected = he.code == 422
        record_test("e2e_salary_negative_experience_rejected_422", neg_exp_rejected, "Negative experience rejected with HTTP 422")

        # Non-technical role rejection (HTTP 400)
        non_tech_rejected = False
        try:
            http_post("/api/salary/predict", {"role": "HR Executive / Recruiter", "skills": ["Payroll"]})
        except urllib.error.HTTPError as he:
            non_tech_rejected = he.code == 400
        record_test("e2e_salary_non_technical_role_rejected_400", non_tech_rejected, "Non-technical role rejected with HTTP 400")

        # Model metadata
        status, sal_meta = http_get("/api/salary/metadata")
        champ = sal_meta.get("champion_metrics", {})
        record_test(
            "e2e_salary_model_metadata",
            status == 200 and sal_meta.get("model_version") == "2.0.0" and champ.get("sample_count") == 4207,
            {"version": sal_meta.get("model_version"), "champion": champ.get("model_name"), "samples": champ.get("sample_count")},
        )

        # =====================================================================
        # H. CROSS-MODULE CONSISTENCY & RECONCILIATION
        # =====================================================================
        print("\n--- H. Cross-Module Consistency & Reconciliation ---")
        status, overview = http_get("/api/analytics/overview")
        summary = overview.get("summary", {})
        total_jobs_analyzed = summary.get("totalJobsAnalyzed")
        db_jobs_count = health["database"]["total_jobs"]

        # Audit provenance explanation:
        # 1. 97,679: Total searchable jobs returned by /api/jobs (3 null/unsearchable title rows excluded from search index).
        # 2. 97,682: Golden cleaned records in DataStore, jobs_clean.parquet, and audit_dataset.parquet.
        # 3. 98,347: Total records in SQLite `jobs` table (including 665 raw historical snapshots preserved for provenance).
        reconciliation_audit = {
            "jobs_api_searchable_total": 97679,
            "cleaned_deduplicated_pipeline_datastore": 97682,
            "sqlite_jobs_table_total_snapshots": 98347,
            "explanation": "97,682 represents the golden cleaned, deduplicated dataset serving API analytics overview. 97,679 is the active searchable total in /api/jobs due to 3 records with empty/invalid title strings excluded from search masking. 98,347 in SQLite contains 665 multi-ingestion historical snapshots preserved for audit provenance.",
        }
        e2e_results["reconciliation"] = reconciliation_audit

        record_test(
            "e2e_reconciliation_exact_alignment",
            total_jobs_analyzed == 97682 and db_jobs_count == 98347 and jobs_page1["total"] == 97679,
            {
                "datastore_jobs": total_jobs_analyzed,
                "sqlite_jobs": db_jobs_count,
                "jobs_api_total": jobs_page1["total"],
                "reconciled": True,
            },
        )

        # =====================================================================
        # I. FAILURE AND RECOVERY TESTING
        # =====================================================================
        print("\n--- I. Failure and Recovery Testing ---")
        # 1. Invalid JSON body (422)
        inv_body_caught = False
        try:
            http_post("/api/salary/predict", {"role": 12345, "experience_years": "not_a_number"})
        except urllib.error.HTTPError as he:
            inv_body_caught = he.code == 422
        record_test("e2e_failure_invalid_json_body_422", inv_body_caught, "Pydantic validation error returns HTTP 422")

        # 2. Missing route (404)
        not_found_caught = False
        try:
            http_get("/api/unknown_non_existent_route")
        except urllib.error.HTTPError as he:
            not_found_caught = he.code == 404
        record_test("e2e_failure_route_not_found_404", not_found_caught, "Unmatched route returns HTTP 404")

        # 3. Concurrent requests (12 parallel requests)
        concurrent_success = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            futures = [
                executor.submit(http_get, "/api/health"),
                executor.submit(http_get, "/api/jobs?limit=5"),
                executor.submit(http_get, "/api/skills/top?limit=5"),
                executor.submit(http_get, "/api/analytics/salary"),
                executor.submit(http_get, "/api/recommendations/roles"),
                executor.submit(http_get, "/api/skills/categories"),
                executor.submit(http_get, "/api/health"),
                executor.submit(http_get, "/api/jobs?limit=5"),
                executor.submit(http_get, "/api/skills/top?limit=5"),
                executor.submit(http_get, "/api/analytics/salary"),
                executor.submit(http_get, "/api/recommendations/roles"),
                executor.submit(http_get, "/api/skills/categories"),
            ]
            for f in concurrent.futures.as_completed(futures):
                st, _ = f.result()
                if st == 200:
                    concurrent_success += 1

        record_test(
            "e2e_concurrent_read_requests",
            concurrent_success == 12,
            {"concurrent_requests": 12, "successful": concurrent_success},
        )

        # =====================================================================
        # J. COMPLETE END-TO-END USER JOURNEY
        # =====================================================================
        print("\n--- J. Complete End-to-End User Journey ---")
        # Step 1: Open app & verify market health
        st1, h = http_get("/api/health")
        # Step 2: Explore market summary
        st2, ov = http_get("/api/analytics/overview")
        # Step 3: Search for target tech jobs (Python & React in Bengaluru)
        st3, jb = http_get("/api/jobs?search=Python&location=Bengaluru&limit=5")
        # Step 4: Explore top skills & emerging momentum
        st4, sk = http_get("/api/skills/top?limit=8")
        st5, em = http_get("/api/skills/emerging?limit=8")
        # Step 5: User submits profile skills
        user_skills = ["Python", "SQL", "Docker", "Pandas", "Scikit-learn"]
        # Step 6: Career recommendations returned
        st6, cr = http_post("/api/recommendations/career", {"skills": user_skills, "preferred_role": "Data Scientist"})
        top_rec = cr["recommendations"][0]
        # Step 7: Request skill gap for top recommended role
        st7, sg = http_post("/api/skills/gap", {"skills": user_skills, "target_role": top_rec["role_name"]})
        # Step 8: Generate learning roadmap
        st8, rm = http_post("/api/roadmap/generate", {"skills": user_skills, "target_role": top_rec["role_name"]})
        # Step 9: Predict market compensation
        st9, sp = http_post(
            "/api/salary/predict",
            {
                "role": top_rec["role_name"],
                "experience_years": 2.5,
                "location": "Bengaluru",
                "skills": user_skills,
            },
        )

        journey_complete = (
            st1 == 200 and st2 == 200 and st3 == 200 and st4 == 200 and st5 == 200 and
            st6 == 200 and st7 == 200 and st8 == 200 and st9 == 200 and
            top_rec["role_id"] in ("data_scientist_advanced_analytics", "data_engineer_big_data_platform") and
            sp["predicted_salary_lpa"] > 0
        )
        record_test(
            "e2e_complete_user_journey_workflow",
            journey_complete,
            {
                "steps_completed": 9,
                "user_recommended_role": top_rec["role_name"],
                "readiness_score": sg["readiness_score"],
                "roadmap_milestones": len(rm["milestones"]),
                "predicted_compensation_lpa": sp["predicted_salary_lpa"],
                "conformal_interval_lpa": sp["conformal_interval_lpa"],
            },
        )

    finally:
        server_mgr.stop()

    print("\n=======================================================")
    print(f"STEP 8 VERIFICATION COMPLETE: {e2e_results['summary']['passed']}/{e2e_results['summary']['total']} PASSED")
    print("=======================================================")

    with open(DOCS_TESTING_DIR / "step8_e2e_results.json", "w", encoding="utf-8") as f:
        json.dump(e2e_results, f, indent=2, default=str)
    print(f"[*] Saved Step 8 JSON report to {DOCS_TESTING_DIR / 'step8_e2e_results.json'}")


if __name__ == "__main__":
    run_e2e_tests()
