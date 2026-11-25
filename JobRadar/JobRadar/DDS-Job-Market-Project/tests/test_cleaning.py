"""Tests for the simple, auditable Milestone 2 data cleaner."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def job_row(**changes: object) -> dict[str, object]:
    row: dict[str, object] = {
        "title": "Data  Analyst",
        "jobId": 1,
        "currency": "INR",
        "jobUploaded": "6 Days Ago",
        "companyName": " Acme   Ltd ",
        "tagsAndSkills": "Python, python; SQL | ML",
        "experience": "2-4 Yrs",
        "salary": "3-5 Lacs PA",
        "location": "Mumbai ,  India",
        "companyId": 10,
        "ReviewsCount": 20.0,
        "AggregateRating": 4.2,
        "jobDescription": "Build <br> dashboards",
        "minimumSalary": 300000.0,
        "maximumSalary": 500000.0,
        "minimumExperience": 2.0,
        "maximumExperience": 4.0,
    }
    row.update(changes)
    return row


class CleanJobDataTests(unittest.TestCase):
    def tearDown(self) -> None:
        output_dir = PROJECT_ROOT / "tests" / "_cleaning_output_fixture"
        if output_dir.exists():
            for output_file in output_dir.iterdir():
                output_file.unlink()

    def cleaner(self):
        try:
            from job_market.cleaning import clean_job_data
        except ModuleNotFoundError:
            return None
        return clean_job_data

    def test_removes_exact_repeats_but_keeps_and_flags_conflicting_job_ids(self) -> None:
        """Breaks if ID-based deduplication removes non-identical job postings."""
        clean_job_data = self.cleaner()
        self.assertIsNotNone(clean_job_data)
        source = pd.DataFrame(
            [
                job_row(),
                job_row(),
                job_row(jobId=2, title="Data Engineer"),
                job_row(jobId=2, title="Senior Data Engineer"),
                job_row(
                    jobId=3,
                    jobDescription=" ",
                    tagsAndSkills=None,
                    salary="Not disclosed",
                    minimumSalary=0.0,
                    maximumSalary=0.0,
                    minimumExperience=float("nan"),
                    maximumExperience=float("nan"),
                ),
            ]
        )

        cleaned, audit, conflicts = clean_job_data(source)

        self.assertEqual(len(cleaned), 4)
        self.assertEqual(audit["duplicate_rows_removed"], 1)
        self.assertEqual(audit["duplicate_jobid_conflict_groups"], 1)
        self.assertEqual(len(conflicts), 2)
        self.assertTrue(cleaned.loc[cleaned["jobId"].eq(2), "duplicate_jobid_conflict"].all())
        self.assertEqual(cleaned.loc[cleaned["jobId"].eq(1), "title"].iloc[0], "Data  Analyst")

    def test_cleans_derived_values_without_changing_source_fields(self) -> None:
        """Breaks if unknown salary, valid zero experience, or raw fields are changed."""
        clean_job_data = self.cleaner()
        self.assertIsNotNone(clean_job_data)
        source = pd.DataFrame(
            [
                job_row(
                    jobId=3,
                    jobDescription=" ",
                    tagsAndSkills=None,
                    salary="Not disclosed",
                    minimumSalary=0.0,
                    maximumSalary=0.0,
                    minimumExperience=float("nan"),
                    maximumExperience=float("nan"),
                ),
                job_row(
                    jobId=4,
                    experience="0 Yrs",
                    minimumExperience=0.0,
                    maximumExperience=0.0,
                    minimumSalary=500000.0,
                    maximumSalary=300000.0,
                ),
                job_row(
                    jobId=5,
                    experience="2-4 Yrs",
                    minimumExperience=float("nan"),
                    maximumExperience=float("nan"),
                ),
            ]
        )

        cleaned, _, _ = clean_job_data(source)
        unknown_salary = cleaned.loc[cleaned["jobId"].eq(3)].iloc[0]
        zero_experience = cleaned.loc[cleaned["jobId"].eq(4)].iloc[0]
        parsed_experience = cleaned.loc[cleaned["jobId"].eq(5)].iloc[0]

        self.assertEqual(unknown_salary["salary_status"], "not_disclosed")
        self.assertTrue(pd.isna(unknown_salary["minimumSalary_clean"]))
        self.assertTrue(unknown_salary["jobDescription_missing"])
        self.assertTrue(unknown_salary["tagsAndSkills_missing"])
        self.assertEqual(zero_experience["experience_status"], "valid_numeric")
        self.assertEqual(zero_experience["minimumExperience_clean"], 0.0)
        self.assertTrue(zero_experience["salary_range_invalid"])
        self.assertEqual(parsed_experience["experience_status"], "parsed_from_text")
        self.assertEqual(parsed_experience["maximumExperience_clean"], 4.0)
        self.assertEqual(parsed_experience["title_clean"], "Data Analyst")
        self.assertEqual(parsed_experience["jobDescription_clean"], "Build dashboards")
        self.assertEqual(parsed_experience["tagsAndSkills_clean"], "Python, SQL, ML")
        self.assertEqual(parsed_experience["location_clean"], "Mumbai, India")
        self.assertEqual(parsed_experience["companyName_clean"], "Acme Ltd")
        self.assertEqual(parsed_experience["jobUploaded"], "6 Days Ago")

    def test_writes_cleaned_data_conflicts_and_audit_reports(self) -> None:
        """Breaks if the reproducible cleaner omits its useful audit artifacts."""
        try:
            from job_market.cleaning import write_cleaning_outputs
        except ImportError:
            write_cleaning_outputs = None
        self.assertIsNotNone(write_cleaning_outputs)
        output_dir = PROJECT_ROOT / "tests" / "_cleaning_output_fixture"

        written = write_cleaning_outputs(pd.DataFrame([job_row(), job_row()]), output_dir)

        self.assertEqual(
            set(written),
            {"cleaned_data", "duplicate_jobid_conflicts", "audit_json", "audit_markdown"},
        )
        self.assertTrue(all(path.is_file() for path in written.values()))
        cleaned_file = pd.read_csv(written["cleaned_data"])
        self.assertEqual(len(cleaned_file), 1)
        self.assertEqual(cleaned_file.loc[0, "jobUploaded"], "6 Days Ago")
        audit = json.loads(written["audit_json"].read_text(encoding="utf-8"))
        self.assertEqual(audit["duplicate_rows_removed"], 1)
        self.assertIn("# Cleaning Audit Report", written["audit_markdown"].read_text(encoding="utf-8"))

