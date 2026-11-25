"""Unit tests for Stage 5.4 Skill-Gap Analysis."""

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

from skill_gap.analyzer import (
    BenchmarkSkillDetail,
    SkillGapAnalyzer,
    SkillGapResult,
)


class SkillGapAnalyzerTests(unittest.TestCase):
    """Test suite covering skill gap analysis and readiness scoring."""

    def setUp(self) -> None:
        self.analyzer = SkillGapAnalyzer()

    # 1. Valid gap analysis partitions skills correctly
    def test_valid_gap_analysis_partitions(self) -> None:
        # Data Engineer has Python (66.18%), SQL (54.85%), Spark (35.92%)
        user_skills = ["Python", "SQL"]
        res = self.analyzer.analyze_gap(user_skills, "data_engineer_big_data_platform")
        self.assertEqual(res.role_id, "data_engineer_big_data_platform")

        acquired_names = {s.skill_name for s in res.acquired_skills}
        self.assertIn("Python", acquired_names)
        self.assertIn("SQL", acquired_names)

        missing_rec_names = {s.skill_name for s in res.missing_recommended_skills}
        self.assertIn("Spark", missing_rec_names)
        self.assertIn("Scala", missing_rec_names)

        # Readiness should be positive and bounded
        self.assertGreater(res.readiness_score, 0.0)
        self.assertLessEqual(res.readiness_score, 100.0)

    # 2. Invalid role ID raises ValueError with supported roles list
    def test_invalid_role_id_raises_value_error(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            self.analyzer.analyze_gap(["Python"], "invalid_nonexistent_role")
        self.assertIn("is not an approved technical role family", str(ctx.exception))

    # 3. Transferable skills properly categorized
    def test_transferable_skills_categorized(self) -> None:
        # Provide skills not present in Cloud/DevOps benchmark (e.g. Photoshop, Accounting, Selenium)
        user_skills = ["AWS", "Docker", "Photoshop", "Selenium"]
        res = self.analyzer.analyze_gap(user_skills, "cloud_devops_sre")

        acquired_names = {s.skill_name for s in res.acquired_skills}
        self.assertIn("AWS", acquired_names)
        self.assertIn("Docker", acquired_names)

        # Photoshop and Selenium should appear in transferable skills
        self.assertIn("Photoshop", res.transferable_skills)
        self.assertIn("Selenium", res.transferable_skills)

    # 4. Readiness score bounded strictly between 0.0 and 100.0
    def test_readiness_score_bounded(self) -> None:
        # Full coverage
        all_cloud_skills = [
            "Microsoft Azure", "AWS", "Kubernetes", "DevOps", "Python",
            "Linux", "Terraform", "CI/CD", "Docker", "Git"
        ]
        res_full = self.analyzer.analyze_gap(all_cloud_skills, "cloud_devops_sre")
        self.assertLessEqual(res_full.readiness_score, 100.0)
        self.assertGreater(res_full.readiness_score, 80.0)

        # Empty coverage
        res_empty = self.analyzer.analyze_gap([], "cloud_devops_sre")
        self.assertEqual(res_empty.readiness_score, 0.0)

    # 5. Low support notice flagged for Data Scientist
    def test_low_support_notice_flagged_for_data_scientist(self) -> None:
        res = self.analyzer.analyze_gap(["Python", "SQL"], "data_scientist_advanced_analytics")
        self.assertEqual(res.support_tier, "LOW")
        self.assertEqual(res.eligible_job_count, 272)
        self.assertTrue(any("LOW empirical support" in lim for lim in res.limitations))

    # 6. Primary and disclosed demand percentages are both preserved
    def test_dual_denominators_preserved(self) -> None:
        res = self.analyzer.analyze_gap(["Python"], "qa_automation_testing")
        # In QA, Automation Testing has distinct primary vs disclosed demand
        auto_test_skill = next(s for s in res.missing_recommended_skills if s.skill_name == "Automation Testing")
        self.assertEqual(auto_test_skill.demand_percentage, 38.22)
        self.assertEqual(auto_test_skill.disclosed_job_demand_pct, 49.79)


if __name__ == "__main__":
    unittest.main()
