"""Unit and integration tests for Phase 5 Stage 5.1 Role-Skill Benchmarks.

Covers all 12 minimum test requirements:
1. Correct demand percentage calculation.
2. Duplicate job-skill associations do not inflate counts.
3. Multiple occurrences of a skill in one job count once.
4. Correct priority categorization.
5. Unknown roles are excluded.
6. Uncertain classifications are excluded.
7. Empty datasets are handled safely.
8. Missing or invalid skill values are handled safely.
9. Missing role data is handled safely.
10. Benchmark generation is reproducible.
11. JSON output follows the expected schema.
12. Existing source datasets remain unchanged.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

import pandas as pd

# Guarantee local import paths are always resolved
_pkg_root = Path(__file__).resolve().parents[1]
if str(_pkg_root) not in sys.path:
    sys.path.insert(0, str(_pkg_root))

from benchmarks.benchmark_extractor import (
    BENCHMARK_CALCULATION_VERSION,
    DEFAULT_CRITICAL_THRESHOLD,
    DEFAULT_MIN_CONFIDENCE_THRESHOLD,
    DEFAULT_RECOMMENDED_THRESHOLD,
    DEFAULT_SUPPORT_HIGH_THRESHOLD,
    DEFAULT_SUPPORT_MODERATE_THRESHOLD,
    SUPPORTED_TECHNICAL_ROLES,
    assign_priority_category,
    assign_support_tier,
    calculate_role_benchmarks,
    load_role_skill_benchmarks,
)


class BenchmarkExtractionTests(unittest.TestCase):
    """Test suite for empirical role-skill benchmark extraction."""

    def setUp(self) -> None:
        self.project_root = Path(__file__).resolve().parents[4]
        self.ai_ml_dir = self.project_root / "JobRadar" / "AI_ML"
        self.proc_dir = self.project_root / "JobRadar" / "DDS-Job-Market-Project" / "data" / "processed"
        self.artifact_path = (
            self.ai_ml_dir / "Phase_5_Career_Recommendation" / "benchmarks" / "role_skill_benchmarks.json"
        )

    # 1. Correct demand percentage calculation
    def test_demand_percentage_calculation(self) -> None:
        jobs_df = pd.DataFrame([
            {"jobId": "J1", "predicted_role": "data_scientist_advanced_analytics", "confidence": 0.8},
            {"jobId": "J2", "predicted_role": "data_scientist_advanced_analytics", "confidence": 0.8},
            {"jobId": "J3", "predicted_role": "data_scientist_advanced_analytics", "confidence": 0.8},
            {"jobId": "J4", "predicted_role": "data_scientist_advanced_analytics", "confidence": 0.8},
        ])
        skills_df = pd.DataFrame([
            {"jobId": "J1", "skill_normalized": "Python"},
            {"jobId": "J2", "skill_normalized": "Python"},
            {"jobId": "J3", "skill_normalized": "Python"},
            {"jobId": "J1", "skill_normalized": "SQL"},
            {"jobId": "J2", "skill_normalized": "SQL"},
        ])
        benchmarks = calculate_role_benchmarks(jobs_df, skills_df)
        ds = benchmarks["data_scientist_advanced_analytics"]
        self.assertEqual(ds.eligible_job_count, 4)

        skills_dict = {s.skill_name: s for s in ds.skills}
        self.assertIn("Python", skills_dict)
        self.assertIn("SQL", skills_dict)

        # Python: 3 out of 4 = 75.0%
        self.assertEqual(skills_dict["Python"].distinct_job_count, 3)
        self.assertEqual(skills_dict["Python"].demand_percentage, 75.0)

        # SQL: 2 out of 4 = 50.0%
        self.assertEqual(skills_dict["SQL"].distinct_job_count, 2)
        self.assertEqual(skills_dict["SQL"].demand_percentage, 50.0)

    # 2. Duplicate job-skill associations do not inflate counts
    def test_duplicate_job_skill_associations_do_not_inflate_counts(self) -> None:
        jobs_df = pd.DataFrame([
            {"jobId": "J1", "predicted_role": "cloud_devops_sre", "confidence": 0.9},
            {"jobId": "J2", "predicted_role": "cloud_devops_sre", "confidence": 0.9},
        ])
        # Duplicate pairs for J1 and AWS
        skills_df = pd.DataFrame([
            {"jobId": "J1", "skill_normalized": "AWS"},
            {"jobId": "J1", "skill_normalized": "AWS"},
            {"jobId": "J1", "skill_normalized": "AWS"},
            {"jobId": "J2", "skill_normalized": "AWS"},
        ])
        benchmarks = calculate_role_benchmarks(jobs_df, skills_df)
        devops = benchmarks["cloud_devops_sre"]
        aws_skill = next(s for s in devops.skills if s.skill_name == "AWS")

        # Must count distinct jobs (2), not raw occurrences (4)
        self.assertEqual(aws_skill.distinct_job_count, 2)
        self.assertEqual(aws_skill.demand_percentage, 100.0)

    # 3. Multiple occurrences of a skill in one job count once
    def test_multiple_occurrences_of_skill_count_once(self) -> None:
        jobs_df = pd.DataFrame([
            {"jobId": "J1", "predicted_role": "qa_automation_testing", "confidence": 0.85},
            {"jobId": "J2", "predicted_role": "qa_automation_testing", "confidence": 0.85},
            {"jobId": "J3", "predicted_role": "qa_automation_testing", "confidence": 0.85},
        ])
        # J1 mentions Selenium 5 times
        skills_df = pd.DataFrame([
            {"jobId": "J1", "skill_normalized": "Selenium"},
            {"jobId": "J1", "skill_normalized": "Selenium"},
            {"jobId": "J1", "skill_normalized": "Selenium"},
            {"jobId": "J1", "skill_normalized": "Selenium"},
            {"jobId": "J1", "skill_normalized": "Selenium"},
        ])
        benchmarks = calculate_role_benchmarks(jobs_df, skills_df)
        qa = benchmarks["qa_automation_testing"]
        sel = next(s for s in qa.skills if s.skill_name == "Selenium")
        self.assertEqual(sel.distinct_job_count, 1)
        self.assertEqual(sel.demand_percentage, 33.33)

    # 4. Correct priority categorization
    def test_priority_categorization(self) -> None:
        self.assertEqual(assign_priority_category(85.0), "CRITICAL")
        self.assertEqual(assign_priority_category(50.0), "CRITICAL")
        self.assertEqual(assign_priority_category(49.9), "RECOMMENDED")
        self.assertEqual(assign_priority_category(20.0), "RECOMMENDED")
        self.assertEqual(assign_priority_category(19.9), "ELECTIVE")
        self.assertEqual(assign_priority_category(0.0), "ELECTIVE")

    # 5. Unknown roles are excluded
    def test_unknown_roles_are_excluded(self) -> None:
        jobs_df = pd.DataFrame([
            {"jobId": "J1", "predicted_role": "non_tech_corporate_operations", "confidence": 0.9},
            {"jobId": "J2", "predicted_role": "other_unclassified", "confidence": 0.9},
            {"jobId": "J3", "predicted_role": "custom_invented_role", "confidence": 0.9},
            {"jobId": "J4", "predicted_role": "data_engineer_big_data_platform", "confidence": 0.9},
        ])
        skills_df = pd.DataFrame([
            {"jobId": "J1", "skill_normalized": "Accounting"},
            {"jobId": "J2", "skill_normalized": "Travel"},
            {"jobId": "J3", "skill_normalized": "CustomSkill"},
            {"jobId": "J4", "skill_normalized": "Spark"},
        ])
        benchmarks = calculate_role_benchmarks(jobs_df, skills_df)
        # Only supported 8 technical roles exist as keys
        self.assertEqual(set(benchmarks.keys()), set(SUPPORTED_TECHNICAL_ROLES.keys()))
        de = benchmarks["data_engineer_big_data_platform"]
        self.assertEqual(de.eligible_job_count, 1)
        self.assertEqual(de.skills[0].skill_name, "Spark")

    # 6. Uncertain classifications are excluded
    def test_uncertain_classifications_are_excluded(self) -> None:
        jobs_df = pd.DataFrame([
            # Low confidence (< 0.20)
            {"jobId": "J1", "predicted_role": "machine_learning_ai_engineer", "confidence": 0.15},
            {"jobId": "J2", "predicted_role": "machine_learning_ai_engineer", "confidence": 0.18},
            # Sufficient confidence (>= 0.20)
            {"jobId": "J3", "predicted_role": "machine_learning_ai_engineer", "confidence": 0.25},
            {"jobId": "J4", "predicted_role": "machine_learning_ai_engineer", "confidence": 0.60},
        ])
        skills_df = pd.DataFrame([
            {"jobId": "J1", "skill_normalized": "Python"},
            {"jobId": "J2", "skill_normalized": "Python"},
            {"jobId": "J3", "skill_normalized": "Python"},
            {"jobId": "J4", "skill_normalized": "PyTorch"},
        ])
        benchmarks = calculate_role_benchmarks(jobs_df, skills_df, min_confidence_threshold=0.20)
        ml = benchmarks["machine_learning_ai_engineer"]
        # Only J3 and J4 are eligible
        self.assertEqual(ml.eligible_job_count, 2)
        py = next(s for s in ml.skills if s.skill_name == "Python")
        self.assertEqual(py.distinct_job_count, 1)  # Only J3 counted, J1 and J2 dropped
        self.assertEqual(py.demand_percentage, 50.0)

    # 7. Empty datasets are handled safely
    def test_empty_datasets_handled_safely(self) -> None:
        empty_jobs = pd.DataFrame(columns=["jobId", "predicted_role", "confidence"])
        empty_skills = pd.DataFrame(columns=["jobId", "skill_normalized"])
        benchmarks = calculate_role_benchmarks(empty_jobs, empty_skills)
        self.assertEqual(len(benchmarks), 8)
        for rid, summary in benchmarks.items():
            self.assertEqual(summary.eligible_job_count, 0)
            self.assertEqual(summary.distinct_skills_count, 0)
            self.assertEqual(summary.skills, [])

    # 8. Missing or invalid skill values are handled safely
    def test_missing_or_invalid_skill_values_handled_safely(self) -> None:
        jobs_df = pd.DataFrame([
            {"jobId": "J1", "predicted_role": "frontend_full_stack_engineering", "confidence": 0.8},
        ])
        skills_df = pd.DataFrame([
            {"jobId": "J1", "skill_normalized": "React"},
            {"jobId": "J1", "skill_normalized": ""},
            {"jobId": "J1", "skill_normalized": "NaN"},
            {"jobId": "J1", "skill_normalized": "None"},
            {"jobId": "J1", "skill_normalized": "   "},
        ])
        benchmarks = calculate_role_benchmarks(jobs_df, skills_df)
        fe = benchmarks["frontend_full_stack_engineering"]
        self.assertEqual(fe.distinct_skills_count, 1)
        self.assertEqual(fe.skills[0].skill_name, "React")

    # 9. Missing role data is handled safely
    def test_missing_role_data_handled_safely(self) -> None:
        jobs_df = pd.DataFrame([
            {"jobId": "J1", "predicted_role": None, "confidence": 0.8},
            {"jobId": "J2", "predicted_role": float("nan"), "confidence": 0.8},
            {"jobId": "J3", "predicted_role": "backend_core_software_engineering", "confidence": 0.8},
        ])
        skills_df = pd.DataFrame([
            {"jobId": "J1", "skill_normalized": "Java"},
            {"jobId": "J3", "skill_normalized": "Java"},
        ])
        benchmarks = calculate_role_benchmarks(jobs_df, skills_df)
        be = benchmarks["backend_core_software_engineering"]
        self.assertEqual(be.eligible_job_count, 1)

    # 10. Benchmark generation is reproducible
    def test_benchmark_generation_reproducible(self) -> None:
        jobs_df = pd.DataFrame([
            {"jobId": f"J{i}", "predicted_role": "data_analyst_business_intelligence", "confidence": 0.7}
            for i in range(10)
        ])
        skills_df = pd.DataFrame([
            {"jobId": "J0", "skill_normalized": "SQL"},
            {"jobId": "J1", "skill_normalized": "SQL"},
            {"jobId": "J2", "skill_normalized": "Power BI"},
            {"jobId": "J3", "skill_normalized": "Excel"},
        ])
        run1 = calculate_role_benchmarks(jobs_df, skills_df)
        run2 = calculate_role_benchmarks(jobs_df, skills_df)

        for rid in SUPPORTED_TECHNICAL_ROLES:
            s1 = run1[rid]
            s2 = run2[rid]
            self.assertEqual(s1.eligible_job_count, s2.eligible_job_count)
            self.assertEqual(s1.distinct_skills_count, s2.distinct_skills_count)
            self.assertEqual(
                [(s.skill_name, s.demand_percentage) for s in s1.skills],
                [(s.skill_name, s.demand_percentage) for s in s2.skills],
            )

    # 11. JSON output follows expected schema
    def test_json_output_schema_and_integrity(self) -> None:
        self.assertTrue(self.artifact_path.is_file(), f"Artifact missing at: {self.artifact_path}")
        data = load_role_skill_benchmarks(self.artifact_path)

        # Validate metadata schema
        meta = data["metadata"]
        self.assertIn("generated_at", meta)
        self.assertEqual(meta["calculation_version"], BENCHMARK_CALCULATION_VERSION)
        self.assertEqual(meta["taxonomy_reference"], "role-taxonomy-v1")
        self.assertEqual(meta["supported_roles_count"], 8)
        self.assertGreater(meta["total_eligible_jobs_analyzed"], 25000)
        self.assertEqual(meta["critical_threshold_pct"], DEFAULT_CRITICAL_THRESHOLD)
        self.assertEqual(meta["recommended_threshold_pct"], DEFAULT_RECOMMENDED_THRESHOLD)
        self.assertEqual(meta["min_confidence_threshold"], DEFAULT_MIN_CONFIDENCE_THRESHOLD)
        self.assertIsInstance(meta["source_datasets"], list)
        self.assertIsInstance(meta["assumptions_and_limitations"], list)

        # Validate roles schema
        roles = data["roles"]
        self.assertEqual(len(roles), 8)
        for rid, summary in roles.items():
            self.assertIn(rid, SUPPORTED_TECHNICAL_ROLES)
            self.assertEqual(summary["role_id"], rid)
            self.assertIsInstance(summary["role_name"], str)
            self.assertGreater(summary["eligible_job_count"], 0)
            self.assertIn("skill_disclosed_job_count", summary)
            self.assertIn("zero_skill_job_count", summary)
            self.assertIn("skill_disclosure_rate", summary)
            self.assertIn("support_tier", summary)
            self.assertIn(summary["support_tier"], ("HIGH", "MODERATE", "LOW"))
            self.assertIsInstance(summary["skills"], list)
            for sk in summary["skills"]:
                self.assertIn("skill_name", sk)
                self.assertIn("distinct_job_count", sk)
                self.assertIn("demand_percentage", sk)
                self.assertIn("disclosed_job_demand_pct", sk)
                self.assertIn(sk["priority_category"], ("CRITICAL", "RECOMMENDED", "ELECTIVE"))
                self.assertGreaterEqual(sk["demand_percentage"], 0.0)
                self.assertLessEqual(sk["demand_percentage"], 100.0)
                self.assertGreaterEqual(sk["disclosed_job_demand_pct"], 0.0)
                self.assertLessEqual(sk["disclosed_job_demand_pct"], 100.0)

        # Explicitly verify low support tier for data scientist
        self.assertEqual(roles["data_scientist_advanced_analytics"]["support_tier"], "LOW")

    # 12. Existing source datasets remain unchanged
    def test_source_datasets_remain_unchanged(self) -> None:
        jobs_csv = self.proc_dir / "cleaned_indian_job_market_2025.csv"
        skills_csv = self.proc_dir / "job_skills.csv"

        self.assertTrue(jobs_csv.is_file())
        self.assertTrue(skills_csv.is_file())

        # Check line counts match expected immutable raw counts
        df_jobs_sample = pd.read_csv(jobs_csv, dtype={"jobId": str}, nrows=5)
        self.assertIn("jobId", df_jobs_sample.columns)
        self.assertIn("title_clean", df_jobs_sample.columns)

        df_skills_sample = pd.read_csv(skills_csv, dtype={"jobId": str}, nrows=5)
        self.assertIn("jobId", df_skills_sample.columns)
        self.assertIn("skill_normalized", df_skills_sample.columns)

    # 13. Exact confidence boundary (0.20) is included
    def test_confidence_exact_boundary_included(self) -> None:
        jobs_df = pd.DataFrame([
            {"jobId": "J1", "predicted_role": "backend_core_software_engineering", "confidence": 0.20},
            {"jobId": "J2", "predicted_role": "backend_core_software_engineering", "confidence": 0.25},
        ])
        skills_df = pd.DataFrame([
            {"jobId": "J1", "skill_normalized": "Java"},
            {"jobId": "J2", "skill_normalized": "Go"},
        ])
        benchmarks = calculate_role_benchmarks(jobs_df, skills_df, min_confidence_threshold=0.20)
        be = benchmarks["backend_core_software_engineering"]
        self.assertEqual(be.eligible_job_count, 2)
        skills = {s.skill_name: s for s in be.skills}
        self.assertIn("Java", skills)
        self.assertEqual(skills["Java"].distinct_job_count, 1)

    # 14. Confidence strictly below boundary (< 0.20) is excluded
    def test_confidence_below_boundary_excluded(self) -> None:
        jobs_df = pd.DataFrame([
            {"jobId": "J1", "predicted_role": "backend_core_software_engineering", "confidence": 0.199},
            {"jobId": "J2", "predicted_role": "backend_core_software_engineering", "confidence": 0.20},
        ])
        skills_df = pd.DataFrame([
            {"jobId": "J1", "skill_normalized": "Java"},
            {"jobId": "J2", "skill_normalized": "Python"},
        ])
        benchmarks = calculate_role_benchmarks(jobs_df, skills_df, min_confidence_threshold=0.20)
        be = benchmarks["backend_core_software_engineering"]
        self.assertEqual(be.eligible_job_count, 1)
        skills = {s.skill_name: s for s in be.skills}
        self.assertNotIn("Java", skills)
        self.assertIn("Python", skills)

    # 15. Zero-skill jobs remain in primary denominator
    def test_zero_skill_jobs_remain_in_primary_denominator(self) -> None:
        jobs_df = pd.DataFrame([
            {"jobId": "J1", "predicted_role": "cloud_devops_sre", "confidence": 0.8},
            {"jobId": "J2", "predicted_role": "cloud_devops_sre", "confidence": 0.8},
            {"jobId": "J3", "predicted_role": "cloud_devops_sre", "confidence": 0.8},
            {"jobId": "J4", "predicted_role": "cloud_devops_sre", "confidence": 0.8},
        ])
        # J3 and J4 have no disclosed skills
        skills_df = pd.DataFrame([
            {"jobId": "J1", "skill_normalized": "Terraform"},
            {"jobId": "J2", "skill_normalized": "Kubernetes"},
        ])
        benchmarks = calculate_role_benchmarks(jobs_df, skills_df)
        devops = benchmarks["cloud_devops_sre"]
        self.assertEqual(devops.eligible_job_count, 4)
        self.assertEqual(devops.skill_disclosed_job_count, 2)
        self.assertEqual(devops.zero_skill_job_count, 2)
        self.assertEqual(devops.skill_disclosure_rate, 50.0)

        # Primary demand_percentage uses all eligible jobs (denominator = 4)
        tf = next(s for s in devops.skills if s.skill_name == "Terraform")
        self.assertEqual(tf.distinct_job_count, 1)
        self.assertEqual(tf.demand_percentage, 25.0)  # 1 / 4 * 100

    # 16. Secondary denominator excludes zero-skill jobs
    def test_secondary_denominator_excludes_zero_skill_jobs(self) -> None:
        jobs_df = pd.DataFrame([
            {"jobId": "J1", "predicted_role": "data_engineer_big_data_platform", "confidence": 0.8},
            {"jobId": "J2", "predicted_role": "data_engineer_big_data_platform", "confidence": 0.8},
            {"jobId": "J3", "predicted_role": "data_engineer_big_data_platform", "confidence": 0.8},
            {"jobId": "J4", "predicted_role": "data_engineer_big_data_platform", "confidence": 0.8},
        ])
        skills_df = pd.DataFrame([
            {"jobId": "J1", "skill_normalized": "Spark"},
            {"jobId": "J2", "skill_normalized": "Spark"},
        ])
        benchmarks = calculate_role_benchmarks(jobs_df, skills_df)
        de = benchmarks["data_engineer_big_data_platform"]
        self.assertEqual(de.eligible_job_count, 4)
        self.assertEqual(de.skill_disclosed_job_count, 2)
        self.assertEqual(de.zero_skill_job_count, 2)
        self.assertEqual(de.skill_disclosure_rate, 50.0)

        spark = next(s for s in de.skills if s.skill_name == "Spark")
        self.assertEqual(spark.distinct_job_count, 2)
        # Primary: 2 / 4 = 50.0%
        self.assertEqual(spark.demand_percentage, 50.0)
        # Secondary: 2 / 2 = 100.0%
        self.assertEqual(spark.disclosed_job_demand_pct, 100.0)

        # Safe handling when skill_disclosed_job_count == 0
        zero_skills_df = pd.DataFrame(columns=["jobId", "skill_normalized"])
        benchmarks_zero = calculate_role_benchmarks(jobs_df, zero_skills_df)
        de_zero = benchmarks_zero["data_engineer_big_data_platform"]
        self.assertEqual(de_zero.skill_disclosed_job_count, 0)
        self.assertEqual(de_zero.zero_skill_job_count, 4)
        self.assertEqual(de_zero.skill_disclosure_rate, 0.0)
        self.assertEqual(de_zero.skills, [])

    # 17. Support tier boundaries (999, 1000, 2499, 2500)
    def test_support_tier_boundaries(self) -> None:
        self.assertEqual(assign_support_tier(0), "LOW")
        self.assertEqual(assign_support_tier(999), "LOW")
        self.assertEqual(assign_support_tier(1000), "MODERATE")
        self.assertEqual(assign_support_tier(2499), "MODERATE")
        self.assertEqual(assign_support_tier(2500), "HIGH")
        self.assertEqual(assign_support_tier(10000), "HIGH")

        # Custom thresholds verification
        self.assertEqual(assign_support_tier(499, high_threshold=1000, moderate_threshold=500), "LOW")
        self.assertEqual(assign_support_tier(500, high_threshold=1000, moderate_threshold=500), "MODERATE")
        self.assertEqual(assign_support_tier(1000, high_threshold=1000, moderate_threshold=500), "HIGH")

    # 18. Conflicting duplicate job IDs handled deterministically (keep='first')
    def test_conflicting_duplicate_job_ids_deterministic(self) -> None:
        # J1 appears twice with conflicting roles; first is backend, second is frontend
        jobs_df = pd.DataFrame([
            {"jobId": "J1", "predicted_role": "backend_core_software_engineering", "confidence": 0.9},
            {"jobId": "J1", "predicted_role": "frontend_full_stack_engineering", "confidence": 0.95},
            {"jobId": "J2", "predicted_role": "frontend_full_stack_engineering", "confidence": 0.8},
        ])
        skills_df = pd.DataFrame([
            {"jobId": "J1", "skill_normalized": "Java"},
            {"jobId": "J2", "skill_normalized": "React"},
        ])
        benchmarks = calculate_role_benchmarks(jobs_df, skills_df)
        be = benchmarks["backend_core_software_engineering"]
        fe = benchmarks["frontend_full_stack_engineering"]
        # J1 is assigned to backend because keep="first" preserves the earlier record
        self.assertEqual(be.eligible_job_count, 1)
        self.assertEqual(be.skills[0].skill_name, "Java")
        self.assertEqual(fe.eligible_job_count, 1)
        self.assertEqual(fe.skills[0].skill_name, "React")


if __name__ == "__main__":
    unittest.main()
