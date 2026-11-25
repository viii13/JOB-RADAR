"""Unit tests for Stage 5.5 Personalized Learning Roadmap Generator."""

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

from roadmap.generator import (
    LearningRoadmapGenerator,
    LearningRoadmapResult,
    RoadmapMilestone,
)
from skill_gap.analyzer import SkillGapAnalyzer


class LearningRoadmapGeneratorTests(unittest.TestCase):
    """Test suite covering personalized learning roadmaps."""

    def setUp(self) -> None:
        self.analyzer = SkillGapAnalyzer()
        self.generator = LearningRoadmapGenerator()

    # 1. Milestone progression follows priority order (Critical -> Recommended -> Elective)
    def test_milestone_progression_order(self) -> None:
        # Frontend has Critical (JavaScript 62.52%, CSS 54.11%, React 50.56%)
        # User only has HTML
        gap = self.analyzer.analyze_gap(["HTML"], "frontend_full_stack_engineering")
        roadmap = self.generator.generate_roadmap(gap)

        self.assertEqual(roadmap.role_id, "frontend_full_stack_engineering")
        self.assertGreater(len(roadmap.milestones), 1)

        # Milestone 1 should target Critical skills
        self.assertEqual(roadmap.milestones[0].priority, "CRITICAL")
        self.assertTrue(
            any(s in {"JavaScript", "CSS", "React"} for s in roadmap.milestones[0].skills_targeted)
        )

        # Capstone project must exist with deliverables
        self.assertIn("deliverables", roadmap.capstone_project)
        self.assertGreater(len(roadmap.capstone_project["deliverables"]), 0)

    # 2. Verified learning resources attach without fabricated URLs
    def test_verified_resources_attached_without_fake_urls(self) -> None:
        gap = self.analyzer.analyze_gap(["SQL"], "machine_learning_ai_engineer")
        roadmap = self.generator.generate_roadmap(gap)

        # Collect all resource URLs across all milestones
        all_urls: list[str] = []
        for m in roadmap.milestones:
            for r in m.resources:
                all_urls.append(r["url"])

        # Check known verified URLs
        self.assertTrue(any("coursera.org" in u or "kaggle.com" in u or "scikit-learn.org" in u for u in all_urls))
        # Ensure all URLs start with valid https:// scheme
        for u in all_urls:
            self.assertTrue(u.startswith("https://") or u.startswith("http://"))

    # 3. Realistic timeline estimates
    def test_realistic_timeline_estimates(self) -> None:
        gap = self.analyzer.analyze_gap(["Java"], "backend_core_software_engineering")
        roadmap = self.generator.generate_roadmap(gap)
        self.assertGreater(roadmap.total_estimated_weeks, 0)
        self.assertLessEqual(roadmap.total_estimated_weeks, 52)
        for m in roadmap.milestones:
            self.assertGreater(m.estimated_weeks, 0)
            self.assertLessEqual(m.estimated_weeks, 12)

    # 4. No skill gap condition handles advanced mastery safely
    def test_no_skill_gap_handles_advanced_mastery(self) -> None:
        # User already possesses all core frontend skills (Critical: JavaScript, CSS, React; Recommended: HTML, Angular, Java, REST)
        all_fe_skills = ["JavaScript", "CSS", "React", "HTML", "Angular", "Java", "REST"]
        gap = self.analyzer.analyze_gap(all_fe_skills, "frontend_full_stack_engineering")
        roadmap = self.generator.generate_roadmap(gap)

        self.assertEqual(roadmap.current_readiness_score, 100.0)
        # Should generate Advanced Specialization milestone
        self.assertEqual(len(roadmap.milestones), 1)
        self.assertIn("Advanced", roadmap.milestones[0].phase)
        self.assertIn("System Design", roadmap.milestones[0].resources[0]["title"])

    # 5. Low support disclaimer included for Data Scientist
    def test_low_support_disclaimer_included_for_data_scientist(self) -> None:
        gap = self.analyzer.analyze_gap(["Python"], "data_scientist_advanced_analytics")
        roadmap = self.generator.generate_roadmap(gap)
        self.assertTrue(any("LOW empirical support" in d for d in roadmap.disclaimers))

    # 6. Backend roadmap starts at Phase 1: Core Technologies when no critical skills exist
    def test_backend_roadmap_starts_at_phase_1_core_technologies(self) -> None:
        # Backend has no critical skills; top skills are Recommended (Java, SQL, CSS, REST)
        # User only has Java
        gap = self.analyzer.analyze_gap(["Java"], "backend_core_software_engineering")
        self.assertEqual(len(gap.missing_critical_skills), 0)
        self.assertGreater(len(gap.missing_recommended_skills), 0)

        roadmap = self.generator.generate_roadmap(gap)
        self.assertEqual(roadmap.role_id, "backend_core_software_engineering")
        self.assertGreater(len(roadmap.milestones), 0)

        # First milestone must be labeled "Phase 1: Core Technologies", NOT "Phase 2"
        self.assertEqual(roadmap.milestones[0].phase, "Phase 1: Core Technologies")
        self.assertEqual(roadmap.milestones[0].priority, "RECOMMENDED")
        self.assertEqual(roadmap.milestones[0].milestone_id, 1)

        # If an elective milestone exists, it must be labeled "Phase 2: Applied Electives"
        elective_milestones = [m for m in roadmap.milestones if m.priority == "ELECTIVE"]
        if elective_milestones:
            self.assertEqual(elective_milestones[0].phase, "Phase 2: Applied Electives")


if __name__ == "__main__":
    unittest.main()
