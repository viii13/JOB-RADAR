"""Tests for the Hiring Momentum & Salary Premium Index."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from job_market.emerging import (
    compute_hiring_momentum_index,
    parse_relative_upload_days,
)


class RelativeUploadParserTests(unittest.TestCase):
    def test_parses_zero_day_labels(self) -> None:
        self.assertEqual(parse_relative_upload_days("Just Now"), 0)
        self.assertEqual(parse_relative_upload_days("Few Hours Ago"), 0)
        self.assertEqual(parse_relative_upload_days("Today"), 0)
        self.assertEqual(parse_relative_upload_days("today"), 0)

    def test_parses_n_days_ago(self) -> None:
        self.assertEqual(parse_relative_upload_days("1 Day Ago"), 1)
        self.assertEqual(parse_relative_upload_days("4 Days Ago"), 4)
        self.assertEqual(parse_relative_upload_days("10 days ago"), 10)

    def test_unrelated_and_null_strings_return_none(self) -> None:
        self.assertIsNone(parse_relative_upload_days("Starts in 1-3 months"))
        self.assertIsNone(parse_relative_upload_days("Starts : 6th Oct' 25"))
        self.assertIsNone(parse_relative_upload_days(None))
        self.assertIsNone(parse_relative_upload_days(float("nan")))
        self.assertIsNone(parse_relative_upload_days(""))


class HiringMomentumIndexTests(unittest.TestCase):
    def test_unique_job_demand_and_no_double_counting(self) -> None:
        """A skill appearing multiple times for the same jobId must only count as 1 job."""
        jobs_df = pd.DataFrame([
            {"jobId": 1, "jobUploaded": "1 Day Ago", "minimumSalary_clean": 500000, "maximumSalary_clean": 700000, "minimumExperience_clean": 2},
            {"jobId": 2, "jobUploaded": "5 Days Ago", "minimumSalary_clean": 600000, "maximumSalary_clean": 800000, "minimumExperience_clean": 3},
        ])
        # Python listed twice for jobId 1
        skills_df = pd.DataFrame([
            {"jobId": 1, "skill_normalized": "Python", "skill_category": "Programming Language"},
            {"jobId": 1, "skill_normalized": "Python", "skill_category": "Programming Language"},
            {"jobId": 2, "skill_normalized": "Python", "skill_category": "Programming Language"},
        ])

        result = compute_hiring_momentum_index(
            jobs_df, skills_df, min_job_threshold=1, recent_days_threshold=3, min_salary_samples=1
        )
        self.assertEqual(len(result), 1)
        python_row = result.iloc[0]
        self.assertEqual(python_row["total_jobs"], 2)
        self.assertEqual(python_row["recent_jobs"], 1)
        self.assertAlmostEqual(python_row["recency_share"], 0.5)

    def test_duplicate_job_ids_in_jobs_df_deduplicated(self) -> None:
        """Conflicting or repeated job IDs in jobs_df are deduplicated by jobId."""
        jobs_df = pd.DataFrame([
            {"jobId": 1, "jobUploaded": "1 Day Ago", "minimumSalary_clean": 500000, "maximumSalary_clean": 500000, "minimumExperience_clean": 2},
            {"jobId": 1, "jobUploaded": "1 Day Ago", "minimumSalary_clean": 500000, "maximumSalary_clean": 500000, "minimumExperience_clean": 2},
        ])
        skills_df = pd.DataFrame([
            {"jobId": 1, "skill_normalized": "SQL", "skill_category": "Database"},
        ])

        result = compute_hiring_momentum_index(
            jobs_df, skills_df, min_job_threshold=1, recent_days_threshold=3, min_salary_samples=1
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["total_jobs"], 1)

    def test_minimum_support_filter(self) -> None:
        """Skills with fewer unique jobs than min_job_threshold are excluded."""
        jobs_df = pd.DataFrame([
            {"jobId": i, "jobUploaded": "2 Days Ago", "minimumSalary_clean": 400000, "maximumSalary_clean": 400000, "minimumExperience_clean": 1}
            for i in range(1, 10)
        ])
        skills_df = pd.DataFrame(
            [{"jobId": i, "skill_normalized": "Python", "skill_category": "Programming Language"} for i in range(1, 10)]
            + [{"jobId": 1, "skill_normalized": "RareSkill", "skill_category": "Other"}]
        )

        result = compute_hiring_momentum_index(
            jobs_df, skills_df, min_job_threshold=5, recent_days_threshold=3
        )
        skills_present = set(result["skill"])
        self.assertIn("Python", skills_present)
        self.assertNotIn("RareSkill", skills_present)

    def test_missing_salary_data_handled_transparently(self) -> None:
        """When salary samples are below min_salary_samples, salary_score is None and recency is used 100%."""
        jobs_df = pd.DataFrame([
            {"jobId": 1, "jobUploaded": "1 Day Ago", "minimumSalary_clean": float("nan"), "maximumSalary_clean": float("nan"), "minimumExperience_clean": 2},
            {"jobId": 2, "jobUploaded": "2 Days Ago", "minimumSalary_clean": float("nan"), "maximumSalary_clean": float("nan"), "minimumExperience_clean": 3},
        ])
        skills_df = pd.DataFrame([
            {"jobId": 1, "skill_normalized": "Git", "skill_category": "Tools"},
            {"jobId": 2, "skill_normalized": "Git", "skill_category": "Tools"},
        ])

        result = compute_hiring_momentum_index(
            jobs_df, skills_df, min_job_threshold=1, recent_days_threshold=3, min_salary_samples=5
        )
        self.assertEqual(len(result), 1)
        row = result.iloc[0]
        self.assertIsNone(row["median_salary"])
        self.assertIsNone(row["salary_premium_ratio"])
        self.assertIsNone(row["salary_score"])
        self.assertEqual(row["salary_sample_count"], 0)
        # With single skill, min == max recency, score defaults to 50.0
        self.assertEqual(row["recency_score"], 50.0)
        self.assertEqual(row["momentum_index"], 50.0)

    def test_scoring_weights_and_tier_assignment(self) -> None:
        """Verify 60/40 recency/salary weighting and tier labels."""
        # Skill A: High recency, High salary
        # Skill B: Low recency, Low salary
        jobs_data = []
        # Job 1-10: Recent, High Salary (1,000,000)
        for i in range(1, 11):
            jobs_data.append({"jobId": i, "jobUploaded": "1 Day Ago", "minimumSalary_clean": 1000000, "maximumSalary_clean": 1000000, "minimumExperience_clean": 3})
        # Job 11-20: Old, Low Salary (500,000)
        for i in range(11, 21):
            jobs_data.append({"jobId": i, "jobUploaded": "8 Days Ago", "minimumSalary_clean": 500000, "maximumSalary_clean": 500000, "minimumExperience_clean": 1})

        jobs_df = pd.DataFrame(jobs_data)

        # SkillA has 10 recent jobs, 0 old jobs (recency_share = 1.0)
        # SkillB has 0 recent jobs, 10 old jobs (recency_share = 0.0)
        skills_data = (
            [{"jobId": i, "skill_normalized": "SkillA", "skill_category": "Tech"} for i in range(1, 11)]
            + [{"jobId": i, "skill_normalized": "SkillB", "skill_category": "Tech"} for i in range(11, 21)]
        )
        skills_df = pd.DataFrame(skills_data)

        result = compute_hiring_momentum_index(
            jobs_df,
            skills_df,
            min_job_threshold=5,
            recent_days_threshold=3,
            min_salary_samples=5,
            weight_recency=0.60,
            weight_salary=0.40,
        )

        skill_a = result[result["skill"] == "SkillA"].iloc[0]
        skill_b = result[result["skill"] == "SkillB"].iloc[0]

        # SkillA: max recency (100) and max salary (100) -> 0.60*100 + 0.40*100 = 100
        self.assertEqual(skill_a["recency_score"], 100.0)
        self.assertEqual(skill_a["salary_score"], 100.0)
        self.assertEqual(skill_a["momentum_index"], 100.0)
        self.assertEqual(skill_a["momentum_tier"], "High Momentum")

        # SkillB: min recency (0) and min salary (0) -> 0
        self.assertEqual(skill_b["recency_score"], 0.0)
        self.assertEqual(skill_b["salary_score"], 0.0)
        self.assertEqual(skill_b["momentum_index"], 0.0)
        self.assertEqual(skill_b["momentum_tier"], "Low / Stable")
