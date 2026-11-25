"""Tests for the isolated JobRadar SQLite database foundation."""

from __future__ import annotations

import sys
import unittest
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from job_market.database import build_migration_key, create_session_factory, initialize_database
from job_market.models import (
    IngestionRun,
    ExternalSalaryBenchmark,
    ExternalSkillBenchmark,
    Job,
    JobSkill,
    JobVersion,
    RawSnapshot,
    Skill,
    Source,
)


class DatabaseFoundationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = initialize_database("sqlite:///:memory:")
        self.Session = create_session_factory(self.engine)

    def tearDown(self) -> None:
        self.engine.dispose()

    def _source(self, code: str = "historical_2025_xlsx") -> Source:
        return Source(
            code=code,
            name="Historical 2025 workbook",
            source_type="historical_file",
        )

    def _run(self, source: Source, key: str = "migration-a") -> IngestionRun:
        return IngestionRun(
            source=source,
            run_type="historical_import",
            status="succeeded",
            is_complete=True,
            observed_at=datetime.now(UTC),
            transform_version="skills-v1",
            migration_key=key,
            input_manifest_sha256="manifest-a",
        )

    def test_initialization_creates_all_approved_tables(self) -> None:
        table_names = set(inspect(self.engine).get_table_names())
        self.assertEqual(
            table_names,
            {
                "sources",
                "ingestion_runs",
                "raw_snapshots",
                "jobs",
                "job_versions",
                "skills",
                "job_skills",
                "external_skill_benchmarks",
                "external_salary_benchmarks",
            },
        )

    def test_foreign_keys_are_enforced(self) -> None:
        with self.Session() as session:
            session.add(
                Job(
                    source_id=999999,
                    identity_key="missing-source:1",
                    identity_status="provider_id",
                    first_seen_at=datetime.now(UTC),
                    last_seen_at=datetime.now(UTC),
                )
            )
            with self.assertRaises(IntegrityError):
                session.flush()

    def test_source_and_migration_keys_are_unique(self) -> None:
        with self.Session() as session:
            source = self._source()
            session.add(source)
            session.flush()
            session.add(self._source())
            with self.assertRaises(IntegrityError):
                session.flush()
            session.rollback()

            source = self._source()
            run_one = self._run(source, key="same-key")
            run_two = self._run(source, key="same-key")
            session.add_all([source, run_one, run_two])
            with self.assertRaises(IntegrityError):
                session.flush()

    def test_migration_key_includes_stable_source_code(self) -> None:
        common_inputs = {
            "migration_name": "historical-import-v1",
            "schema_mapping_version": "schema-v1",
            "cleaning_transform_version": "cleaning-v1",
            "skill_extraction_version": "skills-v1",
            "input_hashes": {"cleaned_jobs": "same-file-hash"},
        }
        first = build_migration_key(source_code="source-a", **common_inputs)
        second = build_migration_key(source_code="source-b", **common_inputs)
        self.assertNotEqual(first, second)

    def test_job_can_keep_multiple_versions_with_a_returned_fingerprint(self) -> None:
        with self.Session() as session:
            source = self._source()
            job = Job(
                source=source,
                source_job_id="123",
                identity_key="historical_2025_xlsx:123",
                identity_status="provider_id",
                first_seen_at=datetime.now(UTC),
                last_seen_at=datetime.now(UTC),
            )
            session.add_all(
                [
                    JobVersion(
                        job=job,
                        version_number=1,
                        is_current=False,
                        origin_record_key="raw:a:sheet:Sheet1:row:2",
                        content_fingerprint="fingerprint-a",
                        mapping_status="exact",
                        observed_at=datetime.now(UTC),
                        ingested_at=datetime.now(UTC),
                        transform_version="cleaning-v1",
                    ),
                    JobVersion(
                        job=job,
                        version_number=2,
                        is_current=False,
                        origin_record_key="snapshot:2:record:results[0]",
                        content_fingerprint="fingerprint-b",
                        mapping_status="exact",
                        observed_at=datetime.now(UTC),
                        ingested_at=datetime.now(UTC),
                        transform_version="cleaning-v1",
                    ),
                    JobVersion(
                        job=job,
                        version_number=3,
                        is_current=True,
                        origin_record_key="snapshot:3:record:results[0]",
                        content_fingerprint="fingerprint-a",
                        mapping_status="exact",
                        observed_at=datetime.now(UTC),
                        ingested_at=datetime.now(UTC),
                        transform_version="cleaning-v1",
                    ),
                ]
            )
            session.commit()
            self.assertEqual(len(job.versions), 3)

    def test_conflicting_historical_rows_have_independent_identities(self) -> None:
        with self.Session() as session:
            source = self._source()
            session.add_all(
                [
                    Job(
                        source=source,
                        source_job_id="duplicate-id",
                        identity_key="raw:hash:sheet:Sheet1:row:1842",
                        identity_status="conflict",
                        first_seen_at=datetime.now(UTC),
                        last_seen_at=datetime.now(UTC),
                    ),
                    Job(
                        source=source,
                        source_job_id="duplicate-id",
                        identity_key="raw:hash:sheet:Sheet1:row:67291",
                        identity_status="conflict",
                        first_seen_at=datetime.now(UTC),
                        last_seen_at=datetime.now(UTC),
                    ),
                ]
            )
            session.commit()
            self.assertEqual(session.query(Job).count(), 2)

    def test_identical_snapshot_hashes_are_preserved_across_runs(self) -> None:
        with self.Session() as session:
            source = self._source()
            first_run = self._run(source, "migration-one")
            second_run = self._run(source, "migration-two")
            session.add_all(
                [
                    RawSnapshot(
                        ingestion_run=first_run,
                        snapshot_sequence=1,
                        snapshot_kind="file",
                        collected_at=datetime.now(UTC),
                        content_sha256="same-content",
                        storage_mode="file_ref",
                        storage_ref="data/raw/source.xlsx",
                        record_count=1,
                    ),
                    RawSnapshot(
                        ingestion_run=second_run,
                        snapshot_sequence=1,
                        snapshot_kind="file",
                        collected_at=datetime.now(UTC),
                        content_sha256="same-content",
                        storage_mode="file_ref",
                        storage_ref="data/raw/source.xlsx",
                        record_count=1,
                    ),
                ]
            )
            session.commit()
            self.assertEqual(session.query(RawSnapshot).count(), 2)

    def test_skill_evidence_merges_without_losing_extraction_version_history(self) -> None:
        with self.Session() as session:
            source = self._source()
            job = Job(
                source=source,
                identity_key="historical_2025_xlsx:skill-job",
                identity_status="provider_id",
                first_seen_at=datetime.now(UTC),
                last_seen_at=datetime.now(UTC),
            )
            version = JobVersion(
                job=job,
                version_number=1,
                is_current=True,
                origin_record_key="raw:hash:sheet:Sheet1:row:4",
                content_fingerprint="skill-version",
                mapping_status="exact",
                observed_at=datetime.now(UTC),
                ingested_at=datetime.now(UTC),
                transform_version="cleaning-v1",
            )
            skill = Skill(name="Python", normalized_name="python", category="Programming Language")
            requirement = JobSkill(
                job_version=version,
                skill=skill,
                skill_raw="Python",
                extraction_version="skills-v1",
            )
            requirement.add_evidence("Python", "tagsAndSkills")
            requirement.add_evidence("python programming", "jobDescription")
            requirement.add_evidence("Python", "tagsAndSkills")
            session.add(requirement)
            session.commit()

            self.assertEqual(requirement.extraction_source, "both")
            self.assertEqual(requirement.tags_match_count, 1)
            self.assertEqual(requirement.description_match_count, 1)
            self.assertEqual(len(requirement.evidence), 2)

            session.add(
                JobSkill(
                    job_version=version,
                    skill=skill,
                    skill_raw="Python",
                    extraction_version="skills-v2",
                )
            )
            session.commit()
            self.assertEqual(session.query(JobSkill).count(), 2)

    def test_external_benchmarks_preserve_source_snapshot_and_attribution(self) -> None:
        with self.Session() as session:
            source = self._source("jobspiq_india")
            run = self._run(source, "jobspiq-import-v1")
            snapshot = RawSnapshot(
                ingestion_run=run,
                snapshot_sequence=1,
                snapshot_kind="file",
                collected_at=datetime.now(UTC),
                content_sha256="jobspiq-skills-file",
                storage_mode="file_ref",
                storage_ref="data/external/jobspiq/benchmarks/skills-demand-india.csv",
                record_count=76,
            )
            skill = Skill(name="Python", normalized_name="python", category="Programming Language")
            skill_benchmark = ExternalSkillBenchmark(
                source=source,
                raw_snapshot=snapshot,
                skill=skill,
                external_skill_name="Python",
                mapping_status="exact",
                rank=1,
                active_jobs=20331,
                share_of_tech_jobs_pct=29.4,
                page_url="https://jobspiq.in/skills/python",
                as_of=date(2026, 10, 18),
                window_days=30,
                attribution="Jobspiq, CC BY 4.0",
                original_values_json='{"skill":"Python"}',
            )
            salary_benchmark = ExternalSalaryBenchmark(
                source=source,
                raw_snapshot=snapshot,
                skill=skill,
                group_type="skill",
                group_label="Python",
                mapping_status="exact",
                stated_salaries=214,
                lower_quartile_lpa=8.6,
                median_lpa=16.8,
                upper_quartile_lpa=31,
                as_of=date(2026, 10, 18),
                window_days=90,
                attribution="Jobspiq, CC BY 4.0",
                original_values_json='{"group":"Python"}',
            )
            session.add_all([skill_benchmark, salary_benchmark])
            session.commit()

            self.assertEqual(source.external_skill_benchmarks, [skill_benchmark])
            self.assertEqual(snapshot.external_salary_benchmarks, [salary_benchmark])
            self.assertEqual(skill.external_skill_benchmarks, [skill_benchmark])

    def test_external_benchmark_mapping_status_is_validated(self) -> None:
        with self.Session() as session:
            source = self._source("jobspiq_india")
            run = self._run(source, "jobspiq-invalid-v1")
            snapshot = RawSnapshot(
                ingestion_run=run,
                snapshot_sequence=1,
                snapshot_kind="file",
                collected_at=datetime.now(UTC),
                content_sha256="jobspiq-invalid-file",
                storage_mode="file_ref",
                storage_ref="data/external/jobspiq/benchmarks/skills-demand-india.csv",
                record_count=1,
            )
            session.add(
                ExternalSkillBenchmark(
                    source=source,
                    raw_snapshot=snapshot,
                    external_skill_name="Unknown Skill",
                    mapping_status="guessed",
                    rank=1,
                    active_jobs=1,
                    share_of_tech_jobs_pct=1,
                    as_of=date(2026, 10, 18),
                    window_days=30,
                    attribution="Jobspiq, CC BY 4.0",
                    original_values_json="{}",
                )
            )
            with self.assertRaises(IntegrityError):
                session.flush()

    def test_external_benchmarks_allow_the_same_skill_across_snapshots(self) -> None:
        with self.Session() as session:
            source = self._source("jobspiq_india")
            first_run = self._run(source, "jobspiq-snapshot-one")
            second_run = self._run(source, "jobspiq-snapshot-two")
            first_snapshot = RawSnapshot(
                ingestion_run=first_run,
                snapshot_sequence=1,
                snapshot_kind="file",
                collected_at=datetime.now(UTC),
                content_sha256="jobspiq-file-one",
                storage_mode="file_ref",
                storage_ref="data/external/jobspiq/benchmarks/skills-demand-india.csv",
                record_count=76,
            )
            second_snapshot = RawSnapshot(
                ingestion_run=second_run,
                snapshot_sequence=1,
                snapshot_kind="file",
                collected_at=datetime.now(UTC),
                content_sha256="jobspiq-file-two",
                storage_mode="file_ref",
                storage_ref="data/external/jobspiq/benchmarks/skills-demand-india.csv",
                record_count=76,
            )
            session.add_all(
                [
                    ExternalSkillBenchmark(
                        source=source,
                        raw_snapshot=first_snapshot,
                        external_skill_name="Python",
                        mapping_status="exact",
                        rank=1,
                        active_jobs=100,
                        share_of_tech_jobs_pct=10,
                        as_of=date(2026, 10, 18),
                        window_days=30,
                        attribution="Jobspiq, CC BY 4.0",
                        original_values_json="{}",
                    ),
                    ExternalSkillBenchmark(
                        source=source,
                        raw_snapshot=second_snapshot,
                        external_skill_name="Python",
                        mapping_status="exact",
                        rank=1,
                        active_jobs=120,
                        share_of_tech_jobs_pct=11,
                        as_of=date(2026, 11, 18),
                        window_days=30,
                        attribution="Jobspiq, CC BY 4.0",
                        original_values_json="{}",
                    ),
                ]
            )
            session.commit()
            self.assertEqual(session.query(ExternalSkillBenchmark).count(), 2)


if __name__ == "__main__":
    unittest.main()
