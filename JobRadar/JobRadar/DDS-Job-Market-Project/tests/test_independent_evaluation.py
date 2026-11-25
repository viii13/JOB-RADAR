"""Unit tests for Stage 2.3 Independent Evaluation using human-verified annotations."""

from __future__ import annotations

import csv
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from job_market.classification import (
    fit_role_classifier,
    load_role_classifier,
    save_role_classifier,
)
from job_market.independent_evaluation import (
    DEFAULT_ANNOTATION_PATHS,
    AnnotationAuditSummary,
    IndependentEvaluationResult,
    audit_annotation_records,
    get_stage2_split_job_version_ids,
    run_independent_evaluation,
)


class IndependentEvaluationTests(unittest.TestCase):
    """Test audit verification, cross-split leakage prevention, and benchmark evaluation."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="test_indep_eval_"))

        # Train a small temporary model bundle
        train_texts = [
            "Senior Data Scientist Python Statistics",
            "Staff Data Scientist R Modeling",
            "Machine Learning Engineer PyTorch Deep Learning",
            "AI Engineer NLP Transformers",
            "Python Backend Developer FastAPI PostgreSQL",
            "Java Software Engineer Spring Boot Microservices",
            "DevOps Cloud Engineer AWS Kubernetes",
            "Site Reliability Engineer Linux Terraform",
            "QA Automation Test Engineer Selenium Cypress",
            "SDET Software Quality Testing PyTest",
        ]
        train_labels = [
            "data_scientist_advanced_analytics",
            "data_scientist_advanced_analytics",
            "machine_learning_ai_engineer",
            "machine_learning_ai_engineer",
            "backend_core_software_engineering",
            "backend_core_software_engineering",
            "cloud_devops_sre",
            "cloud_devops_sre",
            "qa_automation_testing",
            "qa_automation_testing",
        ]
        self.bundle = fit_role_classifier(
            train_texts,
            train_labels,
            label_source="provisional_silver_rule_v1",
            min_df=1,
            random_state=42,
        )
        self.model_path = self.temp_dir / "test_model.joblib"
        save_role_classifier(self.bundle, self.model_path)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_audit_actual_repo_annotation_files(self) -> None:
        # Audit the genuine repo annotation files with all 3 Stage 2.2 splits
        summary, clean_df = audit_annotation_records(
            annotation_paths=DEFAULT_ANNOTATION_PATHS,
            training_job_version_ids={2333, 2748, 2961},
            validation_job_version_ids={1662},
            test_job_version_ids={2390},
        )
        self.assertIsInstance(summary, AnnotationAuditSummary)
        self.assertEqual(len(summary.files_inspected), 2)
        self.assertIn("role_annotation_sample.csv", summary.files_inspected)
        self.assertIn("targeted_data_ai_role_annotation_batch.csv", summary.files_inspected)

        # 120 (sample) + 72 (targeted) = 192 total records
        self.assertEqual(summary.total_records_inspected, 192)
        self.assertEqual(summary.unique_job_version_ids, 192)

        # Confirm 0 human labels are completed in the repo files
        self.assertEqual(summary.completed_human_labels_count, 0)
        self.assertEqual(summary.blank_labels_count, 192)
        self.assertFalse(summary.is_ready_for_evaluation)
        self.assertTrue(clean_df.empty)

        # Verify all three split overlap categories
        self.assertEqual(summary.training_id_overlaps, [2333, 2748, 2961])
        self.assertEqual(summary.validation_id_overlaps, [1662])
        self.assertEqual(summary.test_id_overlaps, [2390])
        self.assertEqual(summary.all_excluded_overlaps, [1662, 2333, 2390, 2748, 2961])

        # Honest limitation reporting
        self.assertIn("Zero human-verified labels available", summary.limitations[0])
        self.assertTrue(any("Cross-split leakage prevention: 5 annotated records overlap" in lim for lim in summary.limitations))

    def test_leakage_detection_across_all_three_splits(self) -> None:
        # Create synthetic CSV with records overlapping train, val, and test splits
        synthetic_csv = self.temp_dir / "synthetic_splits_test.csv"
        rows = [
            {"job_version_id": "1001", "title": "Data Scientist", "human_verified_role_label": "data_scientist_advanced_analytics"},
            {"job_version_id": "1002", "title": "Backend Dev", "human_verified_role_label": "backend_core_software_engineering"},
            {"job_version_id": "2001", "title": "Train Overlap", "human_verified_role_label": "cloud_devops_sre"},  # Train overlap
            {"job_version_id": "2002", "title": "Val Overlap", "human_verified_role_label": "qa_automation_testing"},  # Val overlap
            {"job_version_id": "2003", "title": "Test Overlap", "human_verified_role_label": "data_scientist_advanced_analytics"},  # Test overlap
        ]
        with synthetic_csv.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["job_version_id", "title", "human_verified_role_label"])
            writer.writeheader()
            writer.writerows(rows)

        summary, clean_df = audit_annotation_records(
            annotation_paths=[synthetic_csv],
            training_job_version_ids={2001},
            validation_job_version_ids={2002},
            test_job_version_ids={2003},
        )

        self.assertEqual(summary.completed_human_labels_count, 5)
        self.assertEqual(summary.training_id_overlaps, [2001])
        self.assertEqual(summary.validation_id_overlaps, [2002])
        self.assertEqual(summary.test_id_overlaps, [2003])
        self.assertEqual(summary.all_excluded_overlaps, [2001, 2002, 2003])

        # Clean dataframe must EXCLUDE all three overlapping records
        clean_ids = set(clean_df["job_version_id"].astype(str))
        self.assertNotIn("2001", clean_ids)
        self.assertNotIn("2002", clean_ids)
        self.assertNotIn("2003", clean_ids)
        self.assertEqual(clean_ids, {"1001", "1002"})
        self.assertEqual(len(clean_df), 2)

    def test_run_independent_evaluation_on_incomplete_repo_csvs(self) -> None:
        result = run_independent_evaluation(
            bundle_or_path=self.bundle,
            annotation_paths=DEFAULT_ANNOTATION_PATHS,
            training_job_version_ids={2333, 2748, 2961},
            validation_job_version_ids={1662},
            test_job_version_ids={2390},
        )
        self.assertIsInstance(result, IndependentEvaluationResult)
        # Cannot benchmark when human annotations are 0
        self.assertFalse(result.can_benchmark)
        self.assertIsNone(result.evaluation_report)
        self.assertIn("No completed human-verified labels", result.status_message)
        self.assertGreater(len(result.recommendations), 0)
        self.assertEqual(result.audit_summary.all_excluded_overlaps, [1662, 2333, 2390, 2748, 2961])

    def test_run_independent_evaluation_on_synthetic_gold_data(self) -> None:
        # Create a synthetic verified gold dataset with 38 records
        synthetic_csv = self.temp_dir / "gold_benchmark_sample.csv"
        roles = [
            ("data_scientist_advanced_analytics", "Senior Data Scientist", "statistics, r", "A/B testing"),
            ("machine_learning_ai_engineer", "Machine Learning Engineer", "pytorch, deep learning", "Neural nets"),
            ("backend_core_software_engineering", "Backend Developer", "python, fastapi", "REST APIs"),
            ("cloud_devops_sre", "DevOps Engineer", "aws, docker, kubernetes", "CI/CD"),
            ("qa_automation_testing", "QA Automation Tester", "selenium, pytest", "Test automation"),
        ]

        rows = []
        for i in range(38):
            role_id, title, skills, desc = roles[i % len(roles)]
            rows.append({
                "job_version_id": str(2000 + i),
                "title": f"{title} #{i}",
                "skills": skills,
                "source_tags_text": "tech",
                "description_excerpt": desc,
                "human_verified_role_label": role_id,
            })

        with synthetic_csv.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

        # Exclude records overlapping with all 3 splits:
        # Train: 2000, Val: 2001, Test: 2002 -> 3 excluded, 35 clean records remain
        result = run_independent_evaluation(
            bundle_or_path=self.model_path,
            annotation_paths=[synthetic_csv],
            training_job_version_ids={2000},
            validation_job_version_ids={2001},
            test_job_version_ids={2002},
            min_samples_threshold=30,
        )

        self.assertTrue(result.can_benchmark)
        self.assertIsNotNone(result.evaluation_report)
        report = result.evaluation_report
        self.assertEqual(report.split_name, "human_gold_benchmark")
        self.assertEqual(report.num_samples, 35)  # 38 - 3 excluded = 35
        self.assertGreaterEqual(report.model_accuracy, 0.70)
        self.assertGreaterEqual(report.model_macro_f1, 0.70)
        self.assertIsNotNone(report.rule_baseline_accuracy)
        self.assertIsNotNone(report.majority_class_accuracy)
        self.assertGreater(len(report.per_class_metrics), 0)


if __name__ == "__main__":
    unittest.main()
