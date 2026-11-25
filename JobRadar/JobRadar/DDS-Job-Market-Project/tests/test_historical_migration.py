"""Tests for the auditable historical CSV-to-SQLite migration."""

from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from job_market.database import create_session_factory, initialize_database
from job_market.historical_migration import import_historical_dataset
from job_market.models import IngestionRun, Job, JobSkill, JobVersion, RawSnapshot, Source


class HistoricalMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = initialize_database("sqlite:///:memory:")
        self.Session = create_session_factory(self.engine)
        fixture_root = Path(__file__).resolve().parent / "_historical_migration_fixture"
        self.cleaned_path = fixture_root / "cleaned.csv"
        self.legacy_skills_path = fixture_root / "job_skills.csv"
        self.workbook_path = PROJECT_ROOT / "data" / "raw" / "indian-job-market-dataset-2025.xlsx"

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_import_preserves_conflicts_skills_and_source_evidence(self) -> None:
        with self.Session() as session:
            result = import_historical_dataset(
                session, cleaned_csv=self.cleaned_path, legacy_skills_csv=self.legacy_skills_path,
                raw_workbook=self.workbook_path, expected_job_records=3, expected_legacy_skill_records=2,
                observed_at=datetime(2026, 11, 9, tzinfo=UTC),
            )
            self.assertEqual(result.job_records, 3)
            self.assertEqual(result.conflict_records, 2)
            self.assertEqual(result.legacy_skill_records, 2)
            self.assertEqual(session.scalar(select(func.count()).select_from(Job)), 3)
            self.assertEqual(session.scalar(select(func.count()).select_from(JobVersion)), 3)
            self.assertGreaterEqual(session.scalar(select(func.count()).select_from(JobSkill)), 3)
            self.assertEqual(session.scalar(select(func.count()).select_from(RawSnapshot)), 3)
            conflicts = session.scalars(select(Job).where(Job.source_job_id == "conflict-id")).all()
            self.assertEqual(len(conflicts), 2)
            self.assertTrue(all(job.identity_status == "conflict" for job in conflicts))
            self.assertEqual(len({job.identity_key for job in conflicts}), 2)
            conflict_versions = session.scalars(
                select(JobVersion).join(Job).where(Job.source_job_id == "conflict-id")
            ).all()
            self.assertTrue(all(version.mapping_status == "conflict" for version in conflict_versions))
            self.assertTrue(all(":row:" in version.origin_record_key for version in conflict_versions))

    def test_unchanged_import_is_idempotent(self) -> None:
        with self.Session() as session:
            first = import_historical_dataset(session, cleaned_csv=self.cleaned_path, legacy_skills_csv=self.legacy_skills_path,
                raw_workbook=self.workbook_path, expected_job_records=3, expected_legacy_skill_records=2)
            second = import_historical_dataset(session, cleaned_csv=self.cleaned_path, legacy_skills_csv=self.legacy_skills_path,
                raw_workbook=self.workbook_path, expected_job_records=3, expected_legacy_skill_records=2)
            self.assertFalse(first.already_imported)
            self.assertTrue(second.already_imported)
            self.assertEqual(session.scalar(select(func.count()).select_from(IngestionRun)), 1)
            self.assertEqual(session.scalar(select(func.count()).select_from(Job)), 3)
            self.assertEqual(session.scalar(select(func.count()).select_from(JobVersion)), 3)

    def test_failed_import_rolls_back_source_run_and_rows(self) -> None:
        invalid_cleaned = Path(__file__).resolve().parent / "_historical_migration_fixture" / "invalid_salary.csv"
        with self.Session() as session:
            with self.assertRaises(IntegrityError):
                import_historical_dataset(
                    session, cleaned_csv=invalid_cleaned, legacy_skills_csv=self.legacy_skills_path,
                    raw_workbook=self.workbook_path, expected_job_records=1, expected_legacy_skill_records=2,
                )
            self.assertEqual(session.scalar(select(func.count()).select_from(Source)), 0)
            self.assertEqual(session.scalar(select(func.count()).select_from(IngestionRun)), 0)
            self.assertEqual(session.scalar(select(func.count()).select_from(Job)), 0)


if __name__ == "__main__":
    unittest.main()
