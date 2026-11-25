"""Tests for the JobRadar FastAPI backend endpoints and CORS configuration."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from job_market.api import ALLOWED_ORIGINS, create_app


class ApiEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = create_app()
        # Find the route functions from app routes
        cls.routes = {route.path: route.endpoint for route in cls.app.routes if hasattr(route, "endpoint")}

    def test_health_endpoint(self) -> None:
        handler = self.routes["/api/health"]
        response = handler()
        self.assertEqual(response["status"], "healthy")
        self.assertEqual(response["service"], "JobRadar API")
        dataset = response["dataset"]
        self.assertGreater(dataset["total_jobs_processed"], 0)
        self.assertGreater(dataset["unique_skills"], 0)

    def test_top_skills_default_limit_and_order(self) -> None:
        handler = self.routes["/api/skills/top"]
        response = handler(limit=20, category=None)
        self.assertLessEqual(len(response), 20)
        self.assertGreater(len(response), 0)
        counts = [item["demand_job_count"] for item in response]
        self.assertEqual(counts, sorted(counts, reverse=True))

    def test_top_skills_limit_and_category_filtering(self) -> None:
        handler = self.routes["/api/skills/top"]
        limit_5 = handler(limit=5, category=None)
        self.assertEqual(len(limit_5), 5)

        filtered = handler(limit=50, category="Programming Language")
        self.assertTrue(all(item["category"] == "Programming Language" for item in filtered))
        self.assertGreater(len(filtered), 0)

    def test_categories_endpoint(self) -> None:
        handler = self.routes["/api/skills/categories"]
        response = handler()
        self.assertGreater(len(response), 0)
        first = response[0]
        self.assertIn("category", first)
        self.assertIn("skill_count", first)
        self.assertIn("total_demand", first)
        self.assertGreater(first["total_demand"], 0)

    def test_emerging_skills_default_limit(self) -> None:
        handler = self.routes["/api/skills/emerging"]
        response = handler(limit=10, tier=None, category=None)
        self.assertLessEqual(len(response), 10)
        self.assertGreater(len(response), 0)
        first = response[0]
        self.assertIn("momentum_index", first)
        self.assertIn("momentum_tier", first)

    def test_emerging_skills_filtering(self) -> None:
        handler = self.routes["/api/skills/emerging"]
        high_tier = handler(limit=50, tier="High Momentum", category=None)
        self.assertTrue(all(item["momentum_tier"] == "High Momentum" for item in high_tier))
        self.assertGreater(len(high_tier), 0)

        ml_emerging = handler(limit=50, tier=None, category="Data/ML")
        self.assertTrue(all(item["category"] == "Data/ML" for item in ml_emerging))

    def test_cors_configuration(self) -> None:
        """Verify CORS middleware is active and contains the expected development origins."""
        cors_middlewares = [
            m for m in self.app.user_middleware if "CORSMiddleware" in str(m.cls)
        ]
        self.assertEqual(len(cors_middlewares), 1)
        options = cors_middlewares[0].kwargs
        self.assertIn("http://localhost:5173", options["allow_origins"])
        self.assertIn("http://localhost:3000", options["allow_origins"])
        self.assertIn("http://127.0.0.1:5173", options["allow_origins"])
        self.assertTrue(options["allow_credentials"])

    def test_salary_analytics_endpoint(self) -> None:
        handler = self.routes["/api/analytics/salary"]
        response = handler()
        self.assertEqual(response["status"], "success")
        self.assertEqual(response["scope"], "valid_disclosed_salaries_only")
        self.assertEqual(response["total_jobs_processed"], 97682)
        self.assertEqual(response["disclosed_jobs_count"], 33138)
        self.assertEqual(response["undisclosed_jobs_count"], 64544)
        self.assertEqual(response["disclosure_rate_pct"], 33.9)
        self.assertEqual(response["average_salary_lpa"], 7.57)
        self.assertEqual(response["median_salary_lpa"], 4.25)
        self.assertIn("note", response)

    def test_salary_bracket_distribution_sum(self) -> None:
        handler = self.routes["/api/analytics/salary"]
        response = handler()
        dist = response["distribution"]
        self.assertEqual(len(dist), 6)
        expected_brackets = ["< 3 LPA", "3-6 LPA", "6-10 LPA", "10-16 LPA", "16-25 LPA", "25+ LPA"]
        self.assertEqual([d["bracket"] for d in dist], expected_brackets)
        total_in_brackets = sum(d["count"] for d in dist)
        self.assertEqual(total_in_brackets, response["disclosed_jobs_count"])
        self.assertEqual(total_in_brackets, 33138)
        for item in dist:
            self.assertIn("label", item)
            self.assertGreater(item["count"], 0)

    def test_salary_analytics_empty_dir(self) -> None:
        empty_app = create_app(processed_dir=PROJECT_ROOT / "nonexistent_dir")
        routes = {route.path: route.endpoint for route in empty_app.routes if hasattr(route, "endpoint")}
        response = routes["/api/analytics/salary"]()
        self.assertEqual(response["status"], "empty")
        self.assertEqual(response["disclosed_jobs_count"], 0)
        self.assertEqual(response["distribution"], [])

    def test_get_jobs_pagination_and_defaults(self) -> None:
        handler = self.routes["/api/jobs"]
        response = handler(
            search=None,
            role=None,
            location=None,
            experience=None,
            min_salary=None,
            skill=None,
            work_type=None,
            sort_by="relevance",
            page=1,
            limit=20,
        )
        self.assertGreater(response["total"], 90000)
        self.assertEqual(response["page"], 1)
        self.assertEqual(response["limit"], 20)
        self.assertGreater(response["total_pages"], 4000)
        self.assertEqual(len(response["jobs"]), 20)

        first_job = response["jobs"][0]
        for field in [
            "id",
            "title",
            "company",
            "companyLogoText",
            "location",
            "salary_display",
            "experience_display",
            "work_type",
            "skills",
            "description",
        ]:
            self.assertIn(field, first_job)

    def test_get_jobs_search_and_skill_filter(self) -> None:
        handler = self.routes["/api/jobs"]
        res = handler(
            search="Python",
            role=None,
            location=None,
            experience=None,
            min_salary=None,
            skill=None,
            work_type=None,
            sort_by="relevance",
            page=1,
            limit=10,
        )
        self.assertGreater(res["total"], 0)
        self.assertLessEqual(len(res["jobs"]), 10)

        # Skill specific filter
        skill_res = handler(
            search=None,
            role=None,
            location=None,
            experience=None,
            min_salary=None,
            skill="Python",
            work_type=None,
            sort_by="relevance",
            page=1,
            limit=10,
        )
        self.assertGreater(skill_res["total"], 0)
        for job in skill_res["jobs"]:
            self.assertTrue(any("python" in s.lower() for s in job["skills"]))

    def test_get_jobs_role_and_location_filter(self) -> None:
        handler = self.routes["/api/jobs"]
        res = handler(
            search=None,
            role="Data Scientist",
            location="Bangalore",
            experience=None,
            min_salary=None,
            skill=None,
            work_type=None,
            sort_by="relevance",
            page=1,
            limit=10,
        )
        self.assertGreater(res["total"], 0)
        for job in res["jobs"]:
            self.assertIn("data scientist", job["title"].lower())
            loc_l = job["location"].lower()
            self.assertTrue("bangalore" in loc_l or "bengaluru" in loc_l)

    def test_get_jobs_min_salary_filter(self) -> None:
        handler = self.routes["/api/jobs"]
        res = handler(
            search=None,
            role=None,
            location=None,
            experience=None,
            min_salary=20.0,
            skill=None,
            work_type=None,
            sort_by="relevance",
            page=1,
            limit=10,
        )
        self.assertGreater(res["total"], 0)
        for job in res["jobs"]:
            self.assertIsNotNone(job["salary_max"])
            self.assertGreaterEqual(job["salary_max"], 20.0)

    def test_get_jobs_sorting(self) -> None:
        handler = self.routes["/api/jobs"]
        res = handler(
            search=None,
            role=None,
            location=None,
            experience=None,
            min_salary=5.0,
            skill=None,
            work_type=None,
            sort_by="salary_desc",
            page=1,
            limit=10,
        )
        salaries = [j["salary_max"] for j in res["jobs"] if j["salary_max"] is not None]
        self.assertEqual(salaries, sorted(salaries, reverse=True))

    def test_get_job_by_id_and_not_found(self) -> None:
        search_handler = self.routes["/api/jobs"]
        first_page = search_handler(
            search=None,
            role=None,
            location=None,
            experience=None,
            min_salary=None,
            skill=None,
            work_type=None,
            sort_by="relevance",
            page=1,
            limit=1,
        )
        target_id = first_page["jobs"][0]["id"]

        detail_handler = self.routes["/api/jobs/{job_id}"]
        job = detail_handler(job_id=target_id)
        self.assertEqual(job["id"], target_id)
        self.assertIn("title", job)
        self.assertIn("company", job)

        from fastapi import HTTPException

        with self.assertRaises(HTTPException) as ctx:
            detail_handler(job_id="nonexistent_id_999999")
        self.assertEqual(ctx.exception.status_code, 404)

    def test_get_jobs_empty_dir(self) -> None:
        empty_app = create_app(processed_dir=PROJECT_ROOT / "nonexistent_dir")
        routes = {route.path: route.endpoint for route in empty_app.routes if hasattr(route, "endpoint")}
        response = routes["/api/jobs"](
            search=None,
            role=None,
            location=None,
            experience=None,
            min_salary=None,
            skill=None,
            work_type=None,
            sort_by="relevance",
            page=1,
            limit=10,
        )
        self.assertEqual(response["total"], 0)
        self.assertEqual(response["jobs"], [])

    def test_classify_single_job_endpoint(self) -> None:
        from job_market.api import JobClassificationRequest

        handler = self.routes["/api/classify/job"]
        req = JobClassificationRequest(
            title="Senior Machine Learning Engineer",
            skills=["PyTorch", "Transformers", "Deep Learning"],
            description="Developing large scale recommendation systems.",
        )
        res = handler(request=req)
        self.assertEqual(res.predicted_role, "machine_learning_ai_engineer")
        self.assertIn(res.confidence_tier, ("HIGH", "MEDIUM", "LOW", "UNCERTAIN"))
        self.assertGreater(res.confidence, 0.0)
        self.assertIn("machine_learning_ai_engineer", res.class_probabilities)
        self.assertFalse(res.is_fallback)

    def test_classify_batch_jobs_endpoint(self) -> None:
        from job_market.api import BatchClassificationRequest, BatchJobItem

        handler = self.routes["/api/classify/batch"]
        req = BatchClassificationRequest(
            jobs=[
                BatchJobItem(id="j1", title="Python FastAPI Developer", skills=["Python", "FastAPI"]),
                BatchJobItem(id="j2", title="Cloud DevOps SRE", skills=["AWS", "Kubernetes", "Terraform"]),
            ]
        )
        res = handler(request=req)
        self.assertEqual(res.total, 2)
        self.assertEqual(len(res.predictions), 2)
        self.assertEqual(res.predictions[0].id, "j1")
        self.assertEqual(res.predictions[0].predicted_role, "backend_core_software_engineering")
        self.assertEqual(res.predictions[1].id, "j2")
        self.assertEqual(res.predictions[1].predicted_role, "cloud_devops_sre")

    def test_classify_batch_empty_raises_400(self) -> None:
        from fastapi import HTTPException
        from job_market.api import BatchClassificationRequest

        handler = self.routes["/api/classify/batch"]
        with self.assertRaises(HTTPException) as ctx:
            handler(request=BatchClassificationRequest(jobs=[]))
        self.assertEqual(ctx.exception.status_code, 400)

    def test_classify_taxonomy_endpoint(self) -> None:
        handler = self.routes["/api/classify/taxonomy"]
        res = handler()
        self.assertIn("role_families", res)
        self.assertEqual(len(res["role_families"]), 11)
        self.assertIn("frontend_filter_mapping", res)

    def test_classify_info_endpoint(self) -> None:
        handler = self.routes["/api/classify/info"]
        res = handler()
        self.assertIn(res["status"], ("loaded", "fallback_rules"))
        self.assertIn("model_version", res)
        self.assertIn("classes", res)
        self.assertEqual(len(res["classes"]), 11)

    def test_market_overview_endpoint(self) -> None:
        handler = self.routes["/api/analytics/overview"]
        res = handler()
        self.assertEqual(res["status"], "success")
        self.assertIn("summary", res)
        self.assertIn("locationDemand", res)
        self.assertIn("experienceDistribution", res)
        self.assertIn("roleDemand", res)
        self.assertIn("salaryDistribution", res)
        self.assertIn("postingVolumeTrend", res)
        self.assertGreater(len(res["locationDemand"]), 0)
        self.assertGreater(len(res["experienceDistribution"]), 0)

    def test_cors_origins_include_preview(self) -> None:
        self.assertIn("http://localhost:4173", ALLOWED_ORIGINS)
        self.assertIn("http://127.0.0.1:4173", ALLOWED_ORIGINS)




