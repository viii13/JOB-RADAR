"""
Unit & Integration Tests for Phase 6 Technical Salary Prediction Engine (v2.0.0)
Tests technical curation, feature transformers, conformal calibration, and error boundaries.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
import numpy as np
import pandas as pd

_MODULE_DIR = Path(__file__).resolve().parent
_PHASE6_DIR = _MODULE_DIR.parent
_AIML_DIR = _PHASE6_DIR.parent
_PROJ_ROOT = _AIML_DIR.parent
if str(_AIML_DIR) not in sys.path:
    sys.path.insert(0, str(_AIML_DIR))
if str(_PHASE6_DIR) not in sys.path:
    sys.path.insert(0, str(_PHASE6_DIR))
if str(_PROJ_ROOT / "DDS-Job-Market-Project" / "src") not in sys.path:
    sys.path.insert(0, str(_PROJ_ROOT / "DDS-Job-Market-Project" / "src"))

from Phase_6_Salary_Prediction.features.transformers import (
    ExperienceFeaturesTransformer,
    LocationTierTransformer,
    RoleFamilyTransformer,
    SeniorityTransformer,
    SkillIndicatorsTransformer,
    TECHNICAL_ROLE_FAMILIES,
)
from Phase_6_Salary_Prediction.api.prediction_service import SalaryPredictionEngine
from Phase_6_Salary_Prediction.data.curator import (
    APPROVED_TECHNICAL_ROLE_FAMILIES,
    curate_technical_salary_dataset,
)


class TechnicalSalaryEngineUnitTests(unittest.TestCase):
    """Test suite for v2.0.0 feature transformations, conformal intervals, and scope boundaries."""

    # 1. Location tier mapping
    def test_location_tier_transformer(self) -> None:
        transformer = LocationTierTransformer()
        locs = ["Bengaluru", "Hyderabad, Telangana", "Jaipur", "Work from Home", "Coimbatore", "Unknown Village"]
        tiers = transformer.transform(locs).ravel()
        self.assertEqual(tiers[0], "tier_1_metro")
        self.assertEqual(tiers[1], "tier_1_metro")
        self.assertEqual(tiers[2], "tier_2_city")
        self.assertEqual(tiers[3], "remote")
        self.assertEqual(tiers[4], "tier_2_city")
        self.assertEqual(tiers[5], "tier_3_other")

    # 2. Seniority level extraction
    def test_seniority_transformer(self) -> None:
        transformer = SeniorityTransformer()
        titles = [
            "Data Science Intern",
            "Junior Web Developer",
            "Senior Backend Engineer",
            "Tech Lead - Cloud",
            "Principal Software Architect",
            "Engineering Manager",
            "Director of Engineering",
            "Python Programmer",
        ]
        sen = transformer.transform(titles).ravel()
        self.assertEqual(sen[0], "intern")
        self.assertEqual(sen[1], "junior")
        self.assertEqual(sen[2], "senior")
        self.assertEqual(sen[3], "lead")
        self.assertEqual(sen[4], "principal_architect")
        self.assertEqual(sen[5], "manager")
        self.assertEqual(sen[6], "executive")
        self.assertEqual(sen[7], "mid")

    # 3. Role family mapping & consolidation (v2.0.0)
    def test_role_family_transformer_consolidation(self) -> None:
        transformer = RoleFamilyTransformer(consolidate_ds_ml=True)
        titles = [
            "Senior Machine Learning Engineer",
            "Lead Data Scientist",
            "Data Analyst / Power BI",
            "Cloud DevOps Engineer",
            "QA Automation Test Engineer",
            "Full Stack Developer",
            "Backend Java Developer",
        ]
        roles = transformer.transform(titles).ravel()
        # Data Science and ML are consolidated under data_science_ml_ai
        self.assertEqual(roles[0], "data_science_ml_ai")
        self.assertEqual(roles[1], "data_science_ml_ai")
        self.assertEqual(roles[2], "data_analyst_business_intelligence")
        self.assertEqual(roles[3], "cloud_devops_sre")
        self.assertEqual(roles[4], "qa_automation_testing")
        self.assertEqual(roles[5], "frontend_full_stack_engineering")
        self.assertEqual(roles[6], "backend_core_software_engineering")

    # 4. Scope Boundary Check: Rejection of non-technical roles
    def test_non_technical_role_rejection(self) -> None:
        transformer = RoleFamilyTransformer()
        non_tech_roles = [
            "Human Resources Manager",
            "Sales Executive",
            "Telecaller / BPO",
            "Senior Accountant",
            "Recruitment Lead",
            "Customer Support Associate",
        ]
        for role in non_tech_roles:
            is_tech, resolved = transformer.is_technical_role(role)
            self.assertFalse(is_tech, f"Expected {role} to be rejected as non-technical")
            self.assertEqual(resolved, "non_technical_rejected")

    # 5. Experience features
    def test_experience_features_transformer(self) -> None:
        transformer = ExperienceFeaturesTransformer()
        df_exp = pd.DataFrame({
            "minimumExperience_clean": [0.0, 3.0, 10.0],
            "maximumExperience_clean": [1.0, 5.0, 14.0],
        })
        res = transformer.transform(df_exp)
        self.assertEqual(res.shape[0], 3)
        self.assertAlmostEqual(res[0, 0], 0.5)
        self.assertAlmostEqual(res[0, 1], 0.25)
        self.assertEqual(res[0, 2], "0-1_years")
        self.assertAlmostEqual(res[1, 0], 4.0)
        self.assertEqual(res[1, 2], "2-4_years")
        self.assertAlmostEqual(res[2, 0], 12.0)
        self.assertEqual(res[2, 2], "9-12_years")

    # 6. Technical skill multi-hot indicators
    def test_skill_indicators_transformer(self) -> None:
        transformer = SkillIndicatorsTransformer(["python", "sql", "aws", "docker"])
        skills_text = ["Required: Python, SQL, and Docker containerization.", "Java and Spring Boot developer"]
        mat = transformer.transform(skills_text)
        self.assertEqual(mat.shape, (2, 4))
        self.assertEqual(mat[0, 0], 1.0)  # python
        self.assertEqual(mat[0, 1], 1.0)  # sql
        self.assertEqual(mat[0, 2], 0.0)  # aws
        self.assertEqual(mat[0, 3], 1.0)  # docker
        self.assertEqual(list(mat[1]), [0.0, 0.0, 0.0, 0.0])

    # 7. Prediction engine output contract with conformal intervals
    def test_prediction_engine_v2_contract(self) -> None:
        engine = SalaryPredictionEngine()
        pred = engine.predict("Full Stack Developer", 2.5, "Pune", ["React", "Node.js", "MongoDB"])

        self.assertGreater(pred.predicted_salary_lpa, 0.0)
        self.assertGreater(pred.predicted_salary_annual_inr, 0.0)
        self.assertTrue(pred.is_technical)
        self.assertEqual(pred.model_version, "2.0.0")

        # Conformal prediction interval check
        self.assertIn("min_lpa", pred.conformal_interval_lpa)
        self.assertIn("max_lpa", pred.conformal_interval_lpa)
        self.assertLessEqual(pred.conformal_interval_lpa["min_lpa"], pred.predicted_salary_lpa)
        self.assertGreaterEqual(pred.conformal_interval_lpa["max_lpa"], pred.predicted_salary_lpa)
        self.assertEqual(pred.coverage_level_pct, 90.0)
        self.assertEqual(pred.calibration_method, "role_stratified_conformal")

        # Disclaimers & factors
        self.assertGreater(len(pred.contributing_factors), 0)
        self.assertGreater(len(pred.disclaimers), 0)

    # 8. Engine rejects non-technical roles with descriptive ValueError
    def test_engine_rejects_non_technical(self) -> None:
        engine = SalaryPredictionEngine()
        with self.assertRaises(ValueError) as ctx:
            engine.predict("Talent Acquisition Specialist", 3.0, "Mumbai")
        self.assertIn("calibrated exclusively for core technical engineering", str(ctx.exception))

    # 9. Backward compatibility rollback to v1.0.0
    def test_rollback_to_v1(self) -> None:
        engine_v1 = SalaryPredictionEngine(model_version="1.0.0")
        self.assertEqual(engine_v1.model_version, "1.0.0")
        pred_v1 = engine_v1.predict("Software Engineer", 3.0, "Bengaluru")
        self.assertGreater(pred_v1.predicted_salary_lpa, 0.0)


if __name__ == "__main__":
    unittest.main()
