"""
Automated Integration Tests for Phase 6 Salary Prediction API
Tests POST /api/salary/predict and GET /api/salary/metadata.
"""

from __future__ import annotations

import sys
from pathlib import Path
_tests_dir = Path(__file__).resolve().parent
_src_dir = _tests_dir.parent / "src"
_aiml_dir = _tests_dir.parent.parent / "AI_ML"
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))
if str(_aiml_dir) not in sys.path:
    sys.path.insert(0, str(_aiml_dir))

import unittest

from job_market.api import create_app
from job_market.salary_prediction_api import SalaryPredictionRequest, predict_salary_endpoint, get_salary_model_metadata


class SalaryPredictionApiTests(unittest.TestCase):
    """Test suite for salary prediction API endpoints and contract validation."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = create_app()

    # 1. Successful prediction for entry-level / fresher profile
    def test_predict_fresher_data_scientist(self) -> None:
        req = SalaryPredictionRequest(
            role="Data Scientist",
            experience_years=0.5,
            location="Bengaluru",
            skills=["Python", "SQL", "Pandas"],
        )
        resp = predict_salary_endpoint(req)
        self.assertIn("predicted_salary_lpa", resp)
        self.assertIn("predicted_salary_annual_inr", resp)
        self.assertIn("salary_range_lpa", resp)
        self.assertIn("salary_range_annual_inr", resp)
        self.assertIn("contributing_factors", resp)
        self.assertIn("disclaimers", resp)

        pred_lpa = resp["predicted_salary_lpa"]
        self.assertGreater(pred_lpa, 1.0)
        self.assertLess(pred_lpa, 15.0)
        self.assertEqual(resp["market_tier"], "tier_1_metro")
        self.assertTrue(any("Entry-level" in f for f in resp["contributing_factors"]))

    # 2. Successful prediction for experienced senior backend engineer
    def test_predict_senior_backend_developer(self) -> None:
        req = SalaryPredictionRequest(
            role="Senior Backend Developer",
            experience_years=8.0,
            location="Hyderabad",
            skills=["Java", "Spring Boot", "AWS", "Microservices"],
        )
        resp = predict_salary_endpoint(req)
        pred_lpa = resp["predicted_salary_lpa"]
        self.assertGreater(pred_lpa, 10.0)
        self.assertLess(pred_lpa, 50.0)
        self.assertTrue(any("Seniority premium" in f for f in resp["contributing_factors"]))

    # 3. Successful prediction for remote engineer
    def test_predict_remote_frontend_developer(self) -> None:
        req = SalaryPredictionRequest(
            role="Frontend Developer",
            experience_years=3.0,
            location="Remote",
            skills=["React", "TypeScript", "Node.js"],
        )
        resp = predict_salary_endpoint(req)
        self.assertEqual(resp["market_tier"], "remote")
        self.assertTrue(any("Remote" in f for f in resp["contributing_factors"]))

    # 4. Input validation: negative experience years
    def test_predict_negative_experience_rejected(self) -> None:
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            SalaryPredictionRequest(
                role="Software Engineer",
                experience_years=-2.0,
                location="Pune",
                skills=["Python"],
            )

    # 5. Input validation: empty role
    def test_predict_empty_role_rejected(self) -> None:
        from fastapi import HTTPException
        req = SalaryPredictionRequest(
            role="   ",
            experience_years=2.0,
            location="Pune",
            skills=[],
        )
        with self.assertRaises(HTTPException) as ctx:
            predict_salary_endpoint(req)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("non-empty string", ctx.exception.detail)

    # 6. Metadata endpoint returns champion metrics and feature importances
    def test_get_salary_model_metadata(self) -> None:
        meta = get_salary_model_metadata()
        self.assertIn("champion_model_name", meta)
        self.assertIn("curation_summary", meta)
        self.assertIn("model_comparison", meta)
        self.assertIn("top_features", meta)

        comp = meta["model_comparison"]
        self.assertGreaterEqual(len(comp), 4)
        champ = meta["champion_model_name"]
        self.assertTrue("Ridge" in champ or "Random Forest" in champ)

        top_feats = meta["top_features"]
        self.assertGreater(len(top_feats), 0)
        self.assertIn("feature", top_feats[0])
        self.assertIn("importance", top_feats[0])

    # 7. Non-technical role is rejected with HTTP 400
    def test_predict_non_technical_role_rejected(self) -> None:
        from fastapi import HTTPException
        req = SalaryPredictionRequest(
            role="HR Executive / Recruiter",
            experience_years=3.0,
            location="Bengaluru",
            skills=[],
        )
        with self.assertRaises(HTTPException) as ctx:
            predict_salary_endpoint(req)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("calibrated exclusively for core technical engineering", ctx.exception.detail)

    # 8. Conformal prediction interval fields returned
    def test_predict_conformal_interval_fields(self) -> None:
        req = SalaryPredictionRequest(
            role="Machine Learning Engineer",
            experience_years=4.0,
            location="Bengaluru",
            skills=["Python", "PyTorch"],
        )
        res = predict_salary_endpoint(req)
        self.assertIn("conformal_interval_lpa", res)
        self.assertIn("conformal_uncertainty_lpa", res)
        self.assertEqual(res["coverage_level_pct"], 90.0)
        self.assertEqual(res["calibration_method"], "role_stratified_conformal")


if __name__ == "__main__":
    unittest.main()
