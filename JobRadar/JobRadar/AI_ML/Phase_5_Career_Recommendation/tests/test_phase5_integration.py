"""Integration tests for Phase 5 End-to-End Pipeline (Stages 5.2 - 5.5)."""

from __future__ import annotations

import io
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

from recommendations.recommender import CareerRecommendationEngine
from resume.resume_extractor import ResumeSkillExtractor
from roadmap.generator import LearningRoadmapGenerator
from skill_gap.analyzer import SkillGapAnalyzer


class Phase5EndToEndIntegrationTests(unittest.TestCase):
    """End-to-end integration tests verifying the full Phase 5 workflow."""

    def setUp(self) -> None:
        self.extractor = ResumeSkillExtractor()
        self.recommender = CareerRecommendationEngine()
        self.gap_analyzer = SkillGapAnalyzer()
        self.roadmap_gen = LearningRoadmapGenerator()

    # Flow 1: Full-Stack Developer Synthetic Resume through entire workflow
    def test_full_stack_resume_to_roadmap_pipeline(self) -> None:
        # Step 1: Synthetic Resume Content
        resume_text = (
            "Jordan Lee\n"
            "Full Stack Web Developer\n"
            "Email: redacted@example.com\n\n"
            "Technical Skills:\n"
            "- Languages: JavaScript, Python, HTML5, CSS3\n"
            "- Frameworks & Libraries: React, Node.js, Express\n"
            "- Tools & Platforms: Git, GitHub, REST APIs\n\n"
            "Experience:\n"
            "Built responsive Single Page Applications with React and modern JavaScript. "
            "Integrated backend microservices using REST endpoints."
        )

        # Step 2: Resume Extraction & Skill Parsing
        extraction_res = self.extractor.extract_from_bytes(resume_text.encode("utf-8"), "jordan_resume.txt")
        self.assertEqual(extraction_res.status, "success")
        extracted_skills = [s.canonical_name for s in extraction_res.skills]
        self.assertIn("JavaScript", extracted_skills)
        self.assertIn("React", extracted_skills)
        self.assertIn("Python", extracted_skills)
        self.assertIn("CSS", extracted_skills)
        self.assertIn("HTML", extracted_skills)

        # Step 3: Career Recommendations
        rec_res = self.recommender.recommend(extracted_skills)
        self.assertEqual(rec_res.status, "success")
        self.assertEqual(len(rec_res.recommendations), 8)
        top_role = rec_res.recommendations[0]
        # Frontend & Full Stack Engineering should be recommended #1
        self.assertEqual(top_role.role_id, "frontend_full_stack_engineering")
        self.assertGreater(top_role.match_score, 70.0)

        # Step 4: Skill-Gap Analysis on Recommended Top Role
        gap_res = self.gap_analyzer.analyze_gap(extracted_skills, top_role.role_id)
        self.assertEqual(gap_res.role_id, "frontend_full_stack_engineering")
        self.assertGreater(gap_res.readiness_score, 70.0)
        acquired_names = {s.skill_name for s in gap_res.acquired_skills}
        self.assertIn("JavaScript", acquired_names)
        self.assertIn("React", acquired_names)
        self.assertIn("CSS", acquired_names)

        # Step 5: Learning Roadmap Generation
        roadmap_res = self.roadmap_gen.generate_roadmap(gap_res)
        self.assertEqual(roadmap_res.role_id, "frontend_full_stack_engineering")
        self.assertGreater(len(roadmap_res.milestones), 0)
        self.assertIn("deliverables", roadmap_res.capstone_project)

    # Flow 2: Data Science / ML Synthetic Resume Pipeline
    def test_data_science_resume_to_roadmap_pipeline(self) -> None:
        resume_text = (
            "Samir Gupta\n"
            "Data Science Enthusiast\n"
            "Skills: Python, SQL, Machine Learning, Pandas, Scikit-learn.\n"
            "Built classification models and regression models on tabular datasets."
        )
        extraction_res = self.extractor.extract_from_bytes(resume_text.encode("utf-8"), "samir.txt")
        extracted_skills = [s.canonical_name for s in extraction_res.skills]
        self.assertIn("Python", extracted_skills)
        self.assertIn("Machine Learning", extracted_skills)
        self.assertIn("SQL", extracted_skills)

        rec_res = self.recommender.recommend(extracted_skills)
        top_roles = [r.role_id for r in rec_res.recommendations[:2]]
        self.assertTrue(
            "machine_learning_ai_engineer" in top_roles
            or "data_scientist_advanced_analytics" in top_roles
        )

        # Target ML Engineer
        gap_res = self.gap_analyzer.analyze_gap(extracted_skills, "machine_learning_ai_engineer")
        roadmap_res = self.roadmap_gen.generate_roadmap(gap_res)
        self.assertEqual(roadmap_res.role_id, "machine_learning_ai_engineer")
        self.assertGreater(len(roadmap_res.milestones), 0)

    # Flow 3: Manual Student Profile (No Resume Upload)
    def test_manual_student_profile_without_resume(self) -> None:
        manual_skills = ["Java", "Spring Boot", "SQL", "Docker"]
        rec_res = self.recommender.recommend(manual_skills, target_career_preference="backend_core_software_engineering")
        top_role = rec_res.recommendations[0]
        self.assertEqual(top_role.role_id, "backend_core_software_engineering")

        gap_res = self.gap_analyzer.analyze_gap(manual_skills, "backend_core_software_engineering")
        roadmap_res = self.roadmap_gen.generate_roadmap(gap_res)
        self.assertGreater(roadmap_res.current_readiness_score, 0.0)
        self.assertGreater(len(roadmap_res.milestones), 0)


if __name__ == "__main__":
    unittest.main()
