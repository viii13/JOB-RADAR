"""Live HTTP server integration tests for JobRadar Phase 7 API."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import threading
import time
import unittest
import urllib.error
import urllib.request

import uvicorn

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
JOBRADAR_ROOT = PROJECT_ROOT.parent
if str(JOBRADAR_ROOT) not in sys.path:
    sys.path.insert(0, str(JOBRADAR_ROOT))

from job_market.api import create_app


class LiveApiIntegrationTests(unittest.TestCase):
    server: uvicorn.Server | None = None
    server_thread: threading.Thread | None = None
    port: int = 8019
    base_url: str = f"http://127.0.0.1:{port}"

    @classmethod
    def setUpClass(cls) -> None:
        app = create_app()
        config = uvicorn.Config(app=app, host="127.0.0.1", port=cls.port, log_level="warning")
        cls.server = uvicorn.Server(config)
        cls.server_thread = threading.Thread(target=cls.server.run, daemon=True)
        cls.server_thread.start()

        # Wait for server to become responsive
        started = False
        for _ in range(30):
            try:
                with urllib.request.urlopen(f"{cls.base_url}/api/health", timeout=1.0) as resp:
                    if resp.status == 200:
                        started = True
                        break
            except Exception:
                time.sleep(0.2)

        if not started:
            raise RuntimeError(f"Uvicorn live test server failed to start within 6s on port {cls.port}")

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.server:
            cls.server.should_exit = True
        if cls.server_thread and cls.server_thread.is_alive():
            cls.server_thread.join(timeout=3.0)

    def _get(self, path: str) -> tuple[int, dict]:
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(url, headers={"User-Agent": "JobRadar-Test/1.0"})
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return resp.status, data

    def _post(self, path: str, payload: dict) -> tuple[int, dict]:
        url = f"{self.base_url}{path}"
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json", "User-Agent": "JobRadar-Test/1.0"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return resp.status, data

    def test_01_health_endpoint(self) -> None:
        status, data = self._get("/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["service"], "JobRadar API")
        self.assertTrue(data["database"]["connected"])
        self.assertGreater(data["database"]["total_jobs"], 0)
        self.assertTrue(data["models"]["salary_predictor_loaded"])
        self.assertTrue(data["models"]["career_recommendations_loaded"])
        self.assertTrue(data["models"]["emerging_skills_index_loaded"])

    def test_02_analytics_overview(self) -> None:
        status, data = self._get("/api/analytics/overview")
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "success")
        self.assertIn("summary", data)
        self.assertGreater(data["summary"]["totalJobsAnalyzed"], 90000)
        self.assertGreater(len(data["locationDemand"]), 0)
        self.assertGreater(len(data["experienceDistribution"]), 0)
        self.assertGreater(len(data["roleDemand"]), 0)
        self.assertGreater(len(data["salaryDistribution"]), 0)

    def test_03_top_skills(self) -> None:
        status, data = self._get("/api/skills/top?limit=5")
        self.assertEqual(status, 200)
        self.assertEqual(len(data), 5)
        self.assertIn("skill", data[0])
        self.assertIn("demand_job_count", data[0])

    def test_04_skills_by_role(self) -> None:
        status, data = self._get("/api/skills/by-role?role=Data+Scientist")
        self.assertEqual(status, 200)
        self.assertTrue(data["success"])
        self.assertEqual(data["role_id"], "data_scientist_advanced_analytics")
        self.assertGreater(len(data["skills"]), 0)
        skill_names = [s["skill"] for s in data["skills"]]
        self.assertIn("Python", skill_names)

    def test_05_emerging_skills(self) -> None:
        status, data = self._get("/api/skills/emerging?limit=5")
        self.assertEqual(status, 200)
        self.assertLessEqual(len(data), 5)
        self.assertGreater(len(data), 0)
        self.assertIn("momentum_tier", data[0])

    def test_06_salary_prediction(self) -> None:
        status, data = self._post(
            "/api/salary/predict",
            {
                "role": "Data Scientist",
                "experience_years": 3.0,
                "location": "Bengaluru",
                "skills": ["Python", "SQL", "Machine Learning"],
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(data["target_role"], "Data Scientist")
        self.assertGreater(data["predicted_salary_lpa"], 0)
        self.assertEqual(data["coverage_level_pct"], 90.0)
        self.assertIn("conformal_interval_lpa", data)
        self.assertGreaterEqual(
            data["conformal_interval_lpa"]["max_lpa"],
            data["conformal_interval_lpa"]["min_lpa"],
        )

    def test_07_salary_metadata(self) -> None:
        status, data = self._get("/api/salary/metadata")
        self.assertEqual(status, 200)
        self.assertIn("champion_model_name", data)
        self.assertIn("model_version", data)

    def test_08_classify_job(self) -> None:
        status, data = self._post(
            "/api/classify/job",
            {
                "title": "Senior Data Scientist",
                "skills": ["Python", "Machine Learning", "PyTorch"],
                "description": "Looking for a seasoned data scientist to build ML models.",
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(data["predicted_role"], "data_scientist_advanced_analytics")
        self.assertGreater(data["confidence"], 0.2)


    def test_09_career_recommendations(self) -> None:
        status, data = self._post(
            "/api/recommendations/career",
            {
                "skills": ["Python", "Pandas", "Scikit-learn", "SQL"],
                "preferred_role": "Data Scientist",
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "success")
        self.assertEqual(len(data["recommendations"]), 8)

    def test_10_skill_gap(self) -> None:
        status, data = self._post(
            "/api/skills/gap",
            {
                "skills": ["Python", "SQL"],
                "target_role": "Data Scientist",
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(data["role_id"], "data_scientist_advanced_analytics")
        self.assertGreaterEqual(data["readiness_score"], 0)
        self.assertLessEqual(data["readiness_score"], 100)

    def test_11_roadmap_generation(self) -> None:
        status, data = self._post(
            "/api/roadmap/generate",
            {
                "skills": ["Python"],
                "target_role": "Data Scientist",
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(data["role_id"], "data_scientist_advanced_analytics")
        self.assertGreater(len(data["milestones"]), 0)

    def test_12_jobs_search(self) -> None:
        status, data = self._get("/api/jobs?limit=5&location=Bengaluru")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(data["total"], 1)
        self.assertLessEqual(len(data["jobs"]), 5)
        first_job = data["jobs"][0]
        self.assertIn("id", first_job)
        self.assertIn("title", first_job)
        self.assertIn("location", first_job)


if __name__ == "__main__":
    unittest.main()
