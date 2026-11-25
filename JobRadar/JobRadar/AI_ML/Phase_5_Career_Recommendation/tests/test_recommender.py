"""Unit tests for Stage 5.3 Career Recommendation Engine."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

# Ensure local package resolution
_pkg_root = Path(__file__).resolve().parents[1]
_project_root = _pkg_root.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
if str(_pkg_root) not in sys.path:
    sys.path.insert(0, str(_pkg_root))

from recommendations.recommender import (
    CareerRecommendationEngine,
    CareerRecommendationResult,
    RoleRecommendation,
)


class CareerRecommendationEngineTests(unittest.TestCase):
    """Test suite covering deterministic career recommendations."""

    def setUp(self) -> None:
        self.engine = CareerRecommendationEngine()

    # 1. Exactly 8 approved technical roles are recommended
    def test_eight_technical_roles_recommended(self) -> None:
        res = self.engine.recommend(["Python", "SQL"])
        self.assertEqual(res.status, "success")
        self.assertEqual(len(res.recommendations), 8)
        role_ids = {r.role_id for r in res.recommendations}
        expected_roles = {
            "backend_core_software_engineering",
            "data_analyst_business_intelligence",
            "frontend_full_stack_engineering",
            "qa_automation_testing",
            "cloud_devops_sre",
            "data_engineer_big_data_platform",
            "machine_learning_ai_engineer",
            "data_scientist_advanced_analytics",
        }
        self.assertEqual(role_ids, expected_roles)
        # Ensure non-tech and fallback roles are strictly excluded
        self.assertNotIn("non_tech_corporate_operations", role_ids)
        self.assertNotIn("other_unclassified", role_ids)
        self.assertNotIn("product_technical_project_management", role_ids)

    # 2. Bounded match scores (0.0 to 100.0)
    def test_match_scores_bounded(self) -> None:
        all_skills = [
            "Python", "SQL", "Java", "JavaScript", "React", "AWS", "Docker",
            "Kubernetes", "Selenium", "Spark", "Machine Learning", "PyTorch"
        ]
        res = self.engine.recommend(all_skills)
        for r in res.recommendations:
            self.assertGreaterEqual(r.match_score, 0.0)
            self.assertLessEqual(r.match_score, 100.0)

    # 3. Empty user skills profile handled safely
    def test_empty_user_skills_profile(self) -> None:
        res = self.engine.recommend([])
        self.assertEqual(res.status, "incomplete_profile")
        self.assertEqual(len(res.recommendations), 8)
        for r in res.recommendations:
            self.assertEqual(r.match_score, 0.0)
            self.assertEqual(r.matching_skills, [])
        self.assertIn("No technical skills were provided", res.warnings[0])

    # 4. Preference does not change the reported objective match score
    def test_preference_does_not_change_reported_match_score(self) -> None:
        skills = ["Python", "SQL"]
        # Run without preference
        res_no_pref = self.engine.recommend(skills)
        de_no_pref = next(r for r in res_no_pref.recommendations if r.role_id == "data_engineer_big_data_platform")

        # Run with preference for Data Engineer
        res_with_pref = self.engine.recommend(skills, target_career_preference="data_engineer_big_data_platform")
        de_with_pref = next(r for r in res_with_pref.recommendations if r.role_id == "data_engineer_big_data_platform")

        self.assertTrue(de_with_pref.is_preferred)
        # Match score must represent objective skill fit ONLY (no additive score points)
        self.assertEqual(de_with_pref.match_score, de_no_pref.match_score)
        self.assertIn("Target career preference indicated", de_with_pref.explanation)

    # 5. Preferred role wins when objective scores are exactly equal
    def test_preferred_role_wins_on_exact_equal_scores(self) -> None:
        # User provides no skills -> all roles have match_score == 0.0
        # By default, Data Analyst and Backend have equal 0.0 scores
        res_pref_be = self.engine.recommend([], target_career_preference="backend_core_software_engineering")
        # Backend should be placed at the very top of the list because it is preferred among 0.0 ties
        self.assertEqual(res_pref_be.recommendations[0].role_id, "backend_core_software_engineering")
        self.assertEqual(res_pref_be.recommendations[0].match_score, 0.0)

    # 6. Preferred role does NOT overtake a role with a higher objective score
    def test_preferred_role_does_not_overtake_higher_score(self) -> None:
        # Frontend skills: JavaScript, React, CSS
        skills = ["JavaScript", "React", "CSS"]
        # Student preferences Cloud/DevOps, but their skills are clearly Frontend
        res = self.engine.recommend(skills, target_career_preference="cloud_devops_sre")

        top_role = res.recommendations[0]
        # Frontend must still be ranked #1 because its objective score is far higher
        self.assertEqual(top_role.role_id, "frontend_full_stack_engineering")
        devops_role = next(r for r in res.recommendations if r.role_id == "cloud_devops_sre")
        self.assertTrue(devops_role.is_preferred)
        self.assertLess(devops_role.match_score, top_role.match_score)
        # Verify ranking order: Frontend comes before Cloud/DevOps
        ranks = [r.role_id for r in res.recommendations]
        self.assertLess(ranks.index("frontend_full_stack_engineering"), ranks.index("cloud_devops_sre"))

    # 7. Backend recommended skills are not double-counted
    def test_backend_recommended_skills_not_double_counted(self) -> None:
        # Backend has no critical skills (Java 25.61%, SQL 22.52%, CSS 22.33%, REST 20.54% are all Recommended)
        # Core demand = 25.61 + 22.52 + 22.33 + 20.54 = 91.0%
        # User with only Java: core_coverage = (25.61 / 91.0) * 100 = 28.1428%
        # Base score must be: 0.90 * core_coverage = 25.328% -> rounds to 25.3%
        res = self.engine.recommend(["Java"])
        be = next(r for r in res.recommendations if r.role_id == "backend_core_software_engineering")
        self.assertEqual(be.match_score, 25.3)

    # 8. Existing roles with critical skills retain original scoring behavior
    def test_roles_with_critical_skills_retain_original_behavior(self) -> None:
        # Frontend has Critical skills: JavaScript (62.52%), CSS (54.11%), React (50.56%)
        # and Recommended skills: HTML (38.63%), Angular (35.94%), Java (34.93%), REST (29.43%)
        # Total core demand = 306.12%
        # User with React: matched 1 of 3 critical skills (crit_coverage = 33.333%)
        # Core coverage = (50.56 / 306.12) * 100 = 16.516%
        # Base score = 0.50 * 33.333 + 0.40 * 16.516 = 16.666 + 6.606 = 23.273% -> rounds to 23.3%
        res = self.engine.recommend(["React"])
        fe = next(r for r in res.recommendations if r.role_id == "frontend_full_stack_engineering")
        self.assertEqual(fe.match_score, 23.3)

    # 6. Sorting order deterministic (score DESC, support tier DESC, role name ASC)
    def test_sorting_order_deterministic(self) -> None:
        skills = ["JavaScript", "React", "CSS", "HTML"]
        res = self.engine.recommend(skills)
        scores = [r.match_score for r in res.recommendations]
        # Must be descending
        self.assertEqual(scores, sorted(scores, reverse=True))
        # Top role must be Frontend
        self.assertEqual(res.recommendations[0].role_id, "frontend_full_stack_engineering")

    # 7. Low support tier notice flagged for Data Scientist
    def test_low_support_tier_notice_flagged(self) -> None:
        res = self.engine.recommend(["Python", "Machine Learning"])
        ds = next(r for r in res.recommendations if r.role_id == "data_scientist_advanced_analytics")
        self.assertEqual(ds.support_tier, "LOW")
        self.assertEqual(ds.eligible_job_count, 272)
        self.assertTrue(any("LOW empirical support" in lim for lim in ds.limitations))

    # 8. Unrecognized skills handled safely
    def test_unrecognized_skills_handled_safely(self) -> None:
        res = self.engine.recommend(["UnicornMagicLanguage", "FakeTech999"])
        self.assertEqual(res.status, "no_skills_matched")
        for r in res.recommendations:
            self.assertEqual(r.match_score, 0.0)


if __name__ == "__main__":
    unittest.main()
