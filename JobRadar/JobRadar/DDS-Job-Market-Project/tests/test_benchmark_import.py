"""Tests for read-only import of the audited Jobspiq benchmark CSV files."""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import func, select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from job_market.benchmark_import import import_jobspiq_benchmarks
from job_market.database import create_session_factory, initialize_database
from job_market.models import (
    ExternalSalaryBenchmark,
    ExternalSkillBenchmark,
    IngestionRun,
    RawSnapshot,
    Skill,
    Source,
)

SKILLS_CSV = PROJECT_ROOT / "data" / "external" / "jobspiq" / "benchmarks" / "skills-demand-india.csv"
SALARIES_CSV = PROJECT_ROOT / "data" / "external" / "jobspiq" / "benchmarks" / "tech-salaries-stated-india.csv"


class JobspiqBenchmarkImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = initialize_database("sqlite:///:memory:")
        self.Session = create_session_factory(self.engine)
        self.observed_at = datetime(2026, 11, 8, tzinfo=UTC)

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_imports_audited_files_with_source_snapshot_and_original_values(self) -> None:
        with self.Session() as session:
            session.add(Skill(name="Python", normalized_name="python", category="Programming Language"))
            session.commit()

            result = import_jobspiq_benchmarks(
                session,
                skills_csv=SKILLS_CSV,
                salaries_csv=SALARIES_CSV,
                observed_at=self.observed_at,
            )

            self.assertFalse(result.already_imported)
            self.assertEqual(result.skill_records, 76)
            self.assertEqual(result.salary_records, 25)
            self.assertEqual(session.scalar(select(func.count()).select_from(Source)), 1)
            self.assertEqual(session.scalar(select(func.count()).select_from(IngestionRun)), 1)
            self.assertEqual(session.scalar(select(func.count()).select_from(RawSnapshot)), 2)
            self.assertEqual(session.scalar(select(func.count()).select_from(ExternalSkillBenchmark)), 76)
            self.assertEqual(session.scalar(select(func.count()).select_from(ExternalSalaryBenchmark)), 25)

            python = session.scalar(
                select(ExternalSkillBenchmark).where(ExternalSkillBenchmark.external_skill_name == "Python")
            )
            self.assertEqual(python.mapping_status, "exact")
            self.assertEqual(python.raw_snapshot.record_count, 76)
            self.assertEqual(python.window_days, 30)
            self.assertIn("Jobspiq", python.attribution)
            self.assertIn('"active_jobs":"20331"', python.original_values_json)

            unresolved = session.scalar(
                select(ExternalSkillBenchmark).where(
                    ExternalSkillBenchmark.external_skill_name == "Google Cloud (GCP)"
                )
            )
            self.assertEqual(unresolved.mapping_status, "unmapped")
            self.assertIsNone(unresolved.skill_id)

    def test_unchanged_files_are_idempotent(self) -> None:
        with self.Session() as session:
            first = import_jobspiq_benchmarks(
                session, skills_csv=SKILLS_CSV, salaries_csv=SALARIES_CSV, observed_at=self.observed_at
            )
            second = import_jobspiq_benchmarks(
                session, skills_csv=SKILLS_CSV, salaries_csv=SALARIES_CSV, observed_at=self.observed_at
            )
            self.assertFalse(first.already_imported)
            self.assertTrue(second.already_imported)
            self.assertEqual(session.scalar(select(func.count()).select_from(IngestionRun)), 1)
            self.assertEqual(session.scalar(select(func.count()).select_from(RawSnapshot)), 2)
            self.assertEqual(session.scalar(select(func.count()).select_from(ExternalSkillBenchmark)), 76)
            self.assertEqual(session.scalar(select(func.count()).select_from(ExternalSalaryBenchmark)), 25)

    def test_changed_file_hash_creates_new_snapshots(self) -> None:
        temp_parent = PROJECT_ROOT / ".venv" / "temp"
        temp_parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp_parent) as temp_dir:
            changed_skills = Path(temp_dir) / "skills-demand-india-changed.csv"
            shutil.copyfile(SKILLS_CSV, changed_skills)
            content = changed_skills.read_text(encoding="utf-8")
            changed_skills.write_text(content.replace("1,Python,20331", "1,Python,20332", 1), encoding="utf-8")

            with self.Session() as session:
                import_jobspiq_benchmarks(
                    session, skills_csv=SKILLS_CSV, salaries_csv=SALARIES_CSV, observed_at=self.observed_at
                )
                result = import_jobspiq_benchmarks(
                    session,
                    skills_csv=changed_skills,
                    salaries_csv=SALARIES_CSV,
                    observed_at=datetime(2026, 11, 9, tzinfo=UTC),
                )
                self.assertFalse(result.already_imported)
                self.assertEqual(session.scalar(select(func.count()).select_from(IngestionRun)), 2)
                self.assertEqual(session.scalar(select(func.count()).select_from(RawSnapshot)), 4)
                self.assertEqual(session.scalar(select(func.count()).select_from(ExternalSkillBenchmark)), 152)
                self.assertEqual(session.scalar(select(func.count()).select_from(ExternalSalaryBenchmark)), 50)

    def test_failure_rolls_back_source_run_snapshots_and_benchmarks(self) -> None:
        with self.Session() as session:
            with patch(
                "job_market.benchmark_import._build_salary_benchmark",
                side_effect=RuntimeError("simulated benchmark failure"),
            ):
                with self.assertRaisesRegex(RuntimeError, "simulated benchmark failure"):
                    import_jobspiq_benchmarks(
                        session,
                        skills_csv=SKILLS_CSV,
                        salaries_csv=SALARIES_CSV,
                        observed_at=self.observed_at,
                    )

            self.assertEqual(session.scalar(select(func.count()).select_from(Source)), 0)
            self.assertEqual(session.scalar(select(func.count()).select_from(IngestionRun)), 0)
            self.assertEqual(session.scalar(select(func.count()).select_from(RawSnapshot)), 0)
            self.assertEqual(session.scalar(select(func.count()).select_from(ExternalSkillBenchmark)), 0)
            self.assertEqual(session.scalar(select(func.count()).select_from(ExternalSalaryBenchmark)), 0)


if __name__ == "__main__":
    unittest.main()
