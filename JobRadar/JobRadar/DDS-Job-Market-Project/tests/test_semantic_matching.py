"""Focused unit tests for Stage 3 Semantic Role Matching and comparison framework."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from job_market.classification import (
    FALLBACK_ROLE_ID,
    fit_role_classifier,
    load_role_taxonomy,
)
from job_market.semantic_matching import (
    ROLE_SEMANTIC_PROFILES,
    SemanticComparisonReport,
    SemanticMatchingResult,
    SemanticRoleMatcher,
    compare_semantic_and_baseline_models,
)


class SemanticRoleMatchingTests(unittest.TestCase):
    """Test semantic embedding matching, cosine ranking, ambiguity handling, and baseline comparison."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.matcher = SemanticRoleMatcher(backend="vector_cosine_space")
        # Lightweight baseline bundle for comparison test
        cls.baseline_bundle = fit_role_classifier(
            X_train=[
                "Senior Data Scientist Python Statistics",
                "Machine Learning Engineer PyTorch Deep Learning",
                "Backend Software Engineer FastAPI PostgreSQL",
                "Cloud DevOps SRE AWS Kubernetes",
                "QA Automation Test Engineer Selenium PyTest",
            ],
            y_train=[
                "data_scientist_advanced_analytics",
                "machine_learning_ai_engineer",
                "backend_core_software_engineering",
                "cloud_devops_sre",
                "qa_automation_testing",
            ],
            min_df=1,
            random_state=42,
        )

    def test_canonical_role_profiles_completeness(self) -> None:
        taxonomy = load_role_taxonomy()
        taxonomy_ids = {f["id"] for f in taxonomy["role_families"]}
        profile_ids = set(ROLE_SEMANTIC_PROFILES.keys())

        # Exact match with approved 11-family taxonomy
        self.assertEqual(profile_ids, taxonomy_ids)
        self.assertEqual(len(ROLE_SEMANTIC_PROFILES), 11)

        for rid, prof in ROLE_SEMANTIC_PROFILES.items():
            self.assertIn("headline", prof)
            self.assertIn("core_competencies", prof)
            self.assertIn("profile_text", prof)
            self.assertGreater(len(prof["core_competencies"]), 0)
            self.assertGreater(len(prof["profile_text"]), 50)

    def test_semantic_matching_key_families(self) -> None:
        test_queries = [
            (
                "Senior Data Scientist",
                ["statistics", "predictive analytics", "r"],
                "Statistical modeling, hypothesis testing, causal inference.",
                "data_scientist_advanced_analytics",
            ),
            (
                "Lead Machine Learning Engineer",
                ["pytorch", "deep learning", "transformers"],
                "Train large language models, generative AI and neural networks.",
                "machine_learning_ai_engineer",
            ),
            (
                "Backend API Software Engineer",
                ["python", "fastapi", "postgresql", "rest api"],
                "Build scalable microservices and server databases.",
                "backend_core_software_engineering",
            ),
            (
                "DevOps / SRE Platform Lead",
                ["aws", "kubernetes", "terraform", "ci/cd"],
                "Manage cloud infrastructure, container orchestration, and reliability.",
                "cloud_devops_sre",
            ),
            (
                "QA Automation SDET",
                ["selenium", "cypress", "pytest"],
                "Automate regression test suites and verify quality standards.",
                "qa_automation_testing",
            ),
        ]

        for title, skills, desc, expected_role in test_queries:
            with self.subTest(title=title, expected_role=expected_role):
                res = self.matcher.match_job(
                    title=title,
                    skills=skills,
                    description=desc,
                )
                self.assertIsInstance(res, SemanticMatchingResult)
                self.assertEqual(res.predicted_role, expected_role)
                self.assertGreater(res.similarity_score, 0.25)
                self.assertIn(res.confidence_tier, ("HIGH", "MEDIUM", "LOW"))
                self.assertFalse(res.is_fallback)

    def test_ranking_and_similarity_properties(self) -> None:
        res = self.matcher.match_job(
            title="Senior Python Backend Developer",
            skills=["FastAPI", "PostgreSQL"],
        )
        # All 11 taxonomy roles are ranked
        self.assertEqual(len(res.ranked_matches), 11)
        ranks = [m.rank for m in res.ranked_matches]
        self.assertEqual(ranks, list(range(1, 12)))

        # Similarities are monotonically non-increasing
        sims = [m.similarity for m in res.ranked_matches]
        self.assertEqual(sims, sorted(sims, reverse=True))

        # Margin is difference between top match and runner up
        expected_margin = round(sims[0] - sims[1], 4)
        self.assertEqual(res.similarity_margin, expected_margin)

    def test_low_similarity_fallback(self) -> None:
        # Require a high similarity threshold (0.95) on generic text to force fallback
        res = self.matcher.match_job(
            title="General Consultant",
            description="Client meetings and general travel.",
            min_similarity=0.95,
        )
        self.assertEqual(res.predicted_role, FALLBACK_ROLE_ID)
        self.assertTrue(res.is_fallback)

    def test_ambiguity_margin_flag(self) -> None:
        # Require a wide margin (0.90) to force ambiguity flag
        res = self.matcher.match_job(
            title="Data Scientist",
            skills=["Python"],
            ambiguity_margin=0.90,
        )
        self.assertTrue(res.is_ambiguous)

    def test_batch_matching(self) -> None:
        batch = [
            {"title": "DevOps Engineer", "skills": ["AWS", "Terraform"]},
            {"title": "QA Tester", "skills": ["Selenium", "PyTest"]},
        ]
        results = self.matcher.match_batch(batch)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].predicted_role, "cloud_devops_sre")
        self.assertEqual(results[1].predicted_role, "qa_automation_testing")

    def test_compare_semantic_and_baseline_pending_gold(self) -> None:
        report = compare_semantic_and_baseline_models(
            matcher=self.matcher,
            baseline_bundle=self.baseline_bundle,
        )
        self.assertIsInstance(report, SemanticComparisonReport)
        # Because repo annotation files have 0 human labels, status must be pending_gold_labels
        self.assertEqual(report.evaluation_status, "pending_gold_labels")
        self.assertIsNone(report.semantic_accuracy)
        self.assertIsNone(report.baseline_accuracy)
        self.assertGreaterEqual(report.agreement_rate_between_models, 0.60)
        self.assertGreater(len(report.sample_comparisons), 0)
        self.assertIn("Recommendation", report.recommendation)


if __name__ == "__main__":
    unittest.main()
