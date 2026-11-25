"""Behavioral tests for the Milestone 1 workbook inspection boundary."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_WORKBOOK = PROJECT_ROOT / "tests" / "_ingestion_fixture.xlsx"
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def build_workbook(path: Path) -> None:
    jobs = pd.DataFrame(
        {
            "Job ID": ["J-001", "J-002", "J-001"],
            "Job Title": ["Data Analyst", "Data Scientist", "Data Analyst"],
            "Company Name": ["Acme", "Beta", "Acme"],
            "Location": ["Mumbai", "Bengaluru", "Mumbai"],
            "Job Description": ["Analyse data", "Build models", "Analyse data"],
            "TagsAndSkills": ["Python, SQL", "Python, ML", "Python, SQL"],
            "jobUploaded": ["2025-01-01", "2025-01-02", "2025-01-01"],
            "Job Openings": [2, 4, 2],
            "minimumSalary": [200000, 300000, 200000],
            "maximumSalary": [400000, 500000, 400000],
            "minimumExperience": [1, 2, 1],
            "maximumExperience": [3, 5, 3],
        }
    )
    notes = pd.DataFrame({"note": ["not job data"]})
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        notes.to_excel(writer, sheet_name="Notes", index=False)
        jobs.to_excel(writer, sheet_name="Jobs", index=False)


class InspectWorkbookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workbook = TEST_WORKBOOK
        build_workbook(self.workbook)

    def tearDown(self) -> None:
        self.workbook.unlink(missing_ok=True)
        output_dir = PROJECT_ROOT / "tests" / "_report_fixture"
        if output_dir.exists():
            for report_path in output_dir.iterdir():
                report_path.unlink()

    def inspection_function(self):
        try:
            from job_market.ingestion import inspect_workbook
        except ModuleNotFoundError:
            return None
        return inspect_workbook

    def report_writer(self):
        try:
            from job_market.ingestion import write_reports
        except ImportError:
            return None
        return write_reports

    def test_selects_job_sheet_and_reports_core_quality_metrics(self) -> None:
        """Breaks if sheet scoring or duplicate metrics are removed or miscomputed."""
        inspect_workbook = self.inspection_function()
        self.assertIsNotNone(inspect_workbook)

        report = inspect_workbook(self.workbook)

        self.assertEqual(report["selected_sheet"], "Jobs")
        self.assertEqual([sheet["name"] for sheet in report["sheets"]], ["Notes", "Jobs"])
        self.assertEqual(report["quality"]["shape"], {"rows": 3, "columns": 12})
        self.assertEqual(report["quality"]["duplicate_rows"], 1)
        self.assertEqual(report["quality"]["duplicate_job_ids"], 1)
        self.assertEqual(report["important_columns"]["job_id"], "Job ID")
        self.assertEqual(report["important_columns"]["posting_date"], "jobUploaded")
        self.assertEqual(report["quality"]["categorical_values"]["Location"], ["Bengaluru", "Mumbai"])
        self.assertEqual(report["quality"]["numeric_statistics"]["Job Openings"]["max"], 4.0)
        self.assertEqual(report["important_columns"]["minimum_salary"], "minimumSalary")

    def test_missing_workbook_has_actionable_error(self) -> None:
        """Breaks if a wrong input path silently produces an empty report."""
        inspect_workbook = self.inspection_function()
        self.assertIsNotNone(inspect_workbook)

        with self.assertRaisesRegex(FileNotFoundError, "Workbook was not found"):
            inspect_workbook(PROJECT_ROOT / "tests" / "missing-workbook.xlsx")

    def test_report_writer_creates_readable_reports_and_data_dictionary(self) -> None:
        """Breaks if report files or their core, user-facing content are missing."""
        write_reports = self.report_writer()
        self.assertIsNotNone(write_reports)
        output_dir = PROJECT_ROOT / "tests" / "_report_fixture"

        written = write_reports(self.workbook, output_dir)

        self.assertEqual(set(written), {"sheet_inventory", "quality_report_json", "quality_report_markdown", "data_dictionary"})
        for report_path in written.values():
            self.assertTrue(report_path.is_file())
        quality_report = json.loads(written["quality_report_json"].read_text(encoding="utf-8"))
        self.assertEqual(quality_report["selected_sheet"], "Jobs")
        self.assertIn("# Data Quality Report", written["quality_report_markdown"].read_text(encoding="utf-8"))
        data_dictionary = written["data_dictionary"].read_text(encoding="utf-8")
        self.assertIn("Job ID", data_dictionary)
        self.assertIn("minimum_salary", data_dictionary)

