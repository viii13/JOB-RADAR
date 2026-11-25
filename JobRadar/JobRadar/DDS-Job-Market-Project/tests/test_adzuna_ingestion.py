"""Unit tests for the Adzuna live database ingestion service in JobRadar."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from job_market.adzuna_client import (
    AdzunaBudgetExhaustedError,
    AdzunaClient,
    AdzunaConfig,
    AdzunaConfigError,
    AdzunaHTTPError,
    AdzunaJob,
    AdzunaPage,
    AdzunaTimeoutError,
)
from sqlalchemy import select
from job_market.adzuna_ingestion import (
    ADZUNA_SOURCE_CODE,
    ADZUNA_TRANSFORM_VERSION,
    DEFAULT_PILOT_SEGMENTS,
    PILOT_M4_MATRIX_VERSION,
    AdzunaIngestionService,
    AdzunaPilotBatchResult,
    SegmentRequestLimiter,
    build_run_scope_checkpoint,
    compute_job_content_fingerprint,
    ingest_adzuna_jobs,
    ingest_adzuna_pilot_batch,
    verify_account_quota_config,
)
from job_market.database import create_session_factory, initialize_database
from job_market.models import IngestionRun, Job, JobSkill, JobVersion, RawSnapshot, Skill, Source


def sample_adzuna_job_payload(
    job_id: str,
    title: str = "Senior Python Developer",
    description: str = "Expert in Python, SQL, and Docker with cloud AWS experience.",
    salary_min: float | None = 1500000.0,
    salary_max: float | None = 2500000.0,
    company: str = "Innovatech India",
    location: str = "Bengaluru, Karnataka",
) -> dict:
    return {
        "id": job_id,
        "title": title,
        "description": description,
        "company": {"display_name": company},
        "location": {
            "display_name": location,
            "area": ["India", "Karnataka", "Bengaluru"],
        },
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary_is_predicted": "0",
        "contract_time": "full_time",
        "contract_type": "permanent",
        "redirect_url": f"https://www.adzuna.in/land/ad/{job_id}",
        "category": {"tag": "it-jobs", "label": "IT Jobs"},
        "created": "2026-03-01T12:00:00Z",
    }


def create_mock_adzuna_page(
    page_num: int,
    jobs_data: list[dict],
    total_count: int = 100,
) -> AdzunaPage:
    payload = {
        "__class": "Adzuna::API::Response::JobSearchResults",
        "count": total_count,
        "results": jobs_data,
    }
    raw_json = json.dumps(payload, indent=2)
    jobs = [AdzunaJob.from_dict(d) for d in jobs_data]
    return AdzunaPage(
        page=page_num,
        total_count=total_count,
        results=jobs,
        raw_json=raw_json,
        raw_payload=payload,
        http_status=200,
    )


class MockHTTPResponse:
    """Mock urllib response object."""

    def __init__(
        self,
        status: int = 200,
        body: bytes = b"{}",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status = status
        self.code = status
        self._body = body
        self.headers = headers or {}

    def read(self) -> bytes:
        return self._body


class MockOpener:
    """Mock OpenerDirector that returns pre-configured responses or raises errors."""

    def __init__(self, outcomes: list[Any]) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[Any] = []

    def open(self, request: Any, timeout: float = 10.0) -> Any:
        self.calls.append({"request": request, "timeout": timeout})
        if not self.outcomes:
            raise RuntimeError("MockOpener ran out of configured outcomes.")
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class MockPaginatedClient:
    """Mock AdzunaClient that returns configured AdzunaPage instances or raises errors."""

    def __init__(self, pages_or_errors: list[AdzunaPage | Exception]) -> None:
        self.pages_or_errors = list(pages_or_errors)
        self.config = AdzunaConfig(app_id="test-app-id", app_key="test-app-key", country="in")

    def paginate(self, *args, **kwargs):
        for item in self.pages_or_errors:
            if isinstance(item, Exception):
                raise item
            yield item


class AdzunaIngestionTests(unittest.TestCase):
    """Tests for Adzuna live database ingestion."""

    def setUp(self) -> None:
        self.engine = initialize_database("sqlite:///:memory:")
        self.Session = create_session_factory(self.engine)
        self.temp_dir = tempfile.mkdtemp()
        self.snapshot_dir = Path(self.temp_dir) / "snapshots"

    def tearDown(self) -> None:
        self.engine.dispose()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_ingest_new_jobs_creates_source_run_snapshot_and_jobs(self) -> None:
        j1 = sample_adzuna_job_payload("adzuna-101", title="Python Engineer")
        j2 = sample_adzuna_job_payload("adzuna-102", title="React Frontend Developer", description="React, JavaScript and CSS")
        page = create_mock_adzuna_page(1, [j1, j2], total_count=2)
        client = MockPaginatedClient([page])

        with self.Session() as session:
            result = ingest_adzuna_jobs(
                session=session,
                client=client,  # type: ignore[arg-type]
                snapshot_dir=self.snapshot_dir,
            )

            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.pages_processed, 1)
            self.assertEqual(result.snapshots_created, 1)
            self.assertEqual(result.jobs_received, 2)
            self.assertEqual(result.jobs_inserted, 2)
            self.assertEqual(result.jobs_updated, 0)
            self.assertEqual(result.jobs_skipped, 0)
            self.assertGreater(result.skills_extracted, 0)

            # Verify Source
            source = session.scalar(select(Source).where(Source.code == ADZUNA_SOURCE_CODE))
            self.assertIsNotNone(source)
            self.assertEqual(source.source_type, "api")

            # Verify IngestionRun
            run = session.get(IngestionRun, result.run_id)
            self.assertIsNotNone(run)
            self.assertTrue(run.is_complete)
            self.assertEqual(run.status, "succeeded")
            self.assertEqual(run.records_inserted, 2)
            # Verify scope checkpoint persisted on IngestionRun
            self.assertIsNotNone(run.cursor_or_checkpoint)
            cp = json.loads(run.cursor_or_checkpoint)
            self.assertIn("eligible_for_full_scope_reconciliation", cp)
            # Unbounded, unfiltered run â†’ eligible for full-scope reconciliation
            self.assertTrue(cp["eligible_for_full_scope_reconciliation"])
            self.assertFalse(cp["is_bounded"])
            self.assertFalse(cp["is_filtered"])
            # Result object also carries the scope
            self.assertIsNotNone(result.scope_checkpoint)
            self.assertTrue(result.scope_checkpoint["eligible_for_full_scope_reconciliation"])

            # Verify RawSnapshot
            snapshot = session.scalar(select(RawSnapshot).where(RawSnapshot.ingestion_run_id == run.id))
            self.assertIsNotNone(snapshot)
            self.assertEqual(snapshot.snapshot_kind, "api_page")
            self.assertEqual(snapshot.record_count, 2)
            self.assertEqual(snapshot.content_sha256, page.content_sha256)

            # Verify hash-addressed file on disk
            snapshot_file = self.snapshot_dir / f"{page.content_sha256}.json"
            self.assertTrue(snapshot_file.exists())
            self.assertEqual(snapshot_file.read_text(encoding="utf-8"), page.raw_json)

            # Verify Jobs
            jobs = session.scalars(select(Job)).all()
            self.assertEqual(len(jobs), 2)
            for j in jobs:
                self.assertEqual(j.identity_status, "provider_id")
                self.assertTrue(j.identity_key.startswith("adzuna_india:provider_id:"))
                self.assertEqual(len(j.versions), 1)
                v = j.versions[0]
                self.assertEqual(v.version_number, 1)
                self.assertTrue(v.is_current)
                self.assertEqual(v.mapping_status, "exact")

    def test_ingest_unchanged_jobs_updates_last_seen_without_new_versions(self) -> None:
        j1 = sample_adzuna_job_payload("adzuna-201", title="Backend Go Developer")
        page = create_mock_adzuna_page(1, [j1], total_count=1)

        t1 = datetime(2026, 3, 1, 10, 0, 0, tzinfo=UTC)
        t2 = datetime(2026, 3, 2, 10, 0, 0, tzinfo=UTC)

        with self.Session() as session:
            # First ingestion pass
            res1 = ingest_adzuna_jobs(
                session=session,
                client=MockPaginatedClient([page]),  # type: ignore[arg-type]
                snapshot_dir=self.snapshot_dir,
                observed_at=t1,
            )
            self.assertEqual(res1.jobs_inserted, 1)

            job = session.scalar(select(Job).where(Job.source_job_id == "adzuna-201"))
            self.assertEqual(job.first_seen_at.replace(tzinfo=UTC), t1)
            self.assertEqual(job.last_seen_at.replace(tzinfo=UTC), t1)
            self.assertEqual(len(job.versions), 1)

            # Second ingestion pass with identical job
            res2 = ingest_adzuna_jobs(
                session=session,
                client=MockPaginatedClient([page]),  # type: ignore[arg-type]
                snapshot_dir=self.snapshot_dir,
                observed_at=t2,
            )
            self.assertEqual(res2.jobs_inserted, 0)
            self.assertEqual(res2.jobs_updated, 0)
            self.assertEqual(res2.jobs_skipped, 1)

            # Assert Job entity last_seen was updated, but versions did not duplicate
            session.refresh(job)
            self.assertEqual(job.first_seen_at.replace(tzinfo=UTC), t1)
            self.assertEqual(job.last_seen_at.replace(tzinfo=UTC), t2)
            self.assertEqual(job.last_seen_run_id, res2.run_id)
            self.assertEqual(len(job.versions), 1)
            self.assertTrue(job.versions[0].is_current)

    def test_ingest_changed_jobs_creates_new_version_and_updates_current(self) -> None:
        j_initial = sample_adzuna_job_payload("adzuna-301", title="DevOps Engineer", salary_min=1000000.0, salary_max=1500000.0)
        page1 = create_mock_adzuna_page(1, [j_initial], total_count=1)

        j_updated = sample_adzuna_job_payload("adzuna-301", title="Lead DevOps Engineer", salary_min=2000000.0, salary_max=3000000.0)
        page2 = create_mock_adzuna_page(1, [j_updated], total_count=1)

        t1 = datetime(2026, 3, 1, 10, 0, 0, tzinfo=UTC)
        t2 = datetime(2026, 3, 5, 10, 0, 0, tzinfo=UTC)

        with self.Session() as session:
            res1 = ingest_adzuna_jobs(
                session=session,
                client=MockPaginatedClient([page1]),  # type: ignore[arg-type]
                snapshot_dir=self.snapshot_dir,
                observed_at=t1,
            )
            self.assertEqual(res1.jobs_inserted, 1)

            job = session.scalar(select(Job).where(Job.source_job_id == "adzuna-301"))
            self.assertEqual(len(job.versions), 1)
            self.assertEqual(job.versions[0].title, "DevOps Engineer")

            res2 = ingest_adzuna_jobs(
                session=session,
                client=MockPaginatedClient([page2]),  # type: ignore[arg-type]
                snapshot_dir=self.snapshot_dir,
                observed_at=t2,
            )
            self.assertEqual(res2.jobs_inserted, 0)
            self.assertEqual(res2.jobs_updated, 1)
            self.assertEqual(res2.jobs_skipped, 0)

            session.refresh(job)
            self.assertEqual(len(job.versions), 2)

            v1 = [v for v in job.versions if v.version_number == 1][0]
            v2 = [v for v in job.versions if v.version_number == 2][0]

            # Assert SCD Version 1 transitioned to inactive
            self.assertFalse(v1.is_current)
            self.assertEqual(v1.title, "DevOps Engineer")
            self.assertEqual(float(v1.salary_min_source), 1000000.0)

            # Assert SCD Version 2 is current
            self.assertTrue(v2.is_current)
            self.assertEqual(v2.title, "Lead DevOps Engineer")
            self.assertEqual(float(v2.salary_min_source), 2000000.0)

    def test_repeated_ids_within_same_run_are_handled_cleanly(self) -> None:
        # Simulate job 'adzuna-401' appearing on page 1 and repeated on page 2
        j1 = sample_adzuna_job_payload("adzuna-401", title="Cloud Architect")
        page1 = create_mock_adzuna_page(1, [j1], total_count=2)
        page2 = create_mock_adzuna_page(2, [j1], total_count=2)

        client = MockPaginatedClient([page1, page2])

        with self.Session() as session:
            result = ingest_adzuna_jobs(
                session=session,
                client=client,  # type: ignore[arg-type]
                snapshot_dir=self.snapshot_dir,
            )
            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.pages_processed, 2)
            self.assertEqual(result.jobs_inserted, 1)
            self.assertEqual(result.jobs_skipped, 1)

            jobs = session.scalars(select(Job).where(Job.source_job_id == "adzuna-401")).all()
            self.assertEqual(len(jobs), 1)
            self.assertEqual(len(jobs[0].versions), 1)

    def test_skill_extraction_attaches_to_correct_version(self) -> None:
        j = sample_adzuna_job_payload(
            "adzuna-501",
            title="Senior Python & Kubernetes Specialist",
            description="Must know Python, Docker, Kubernetes, and PostgreSQL.",
        )
        page = create_mock_adzuna_page(1, [j], total_count=1)

        with self.Session() as session:
            result = ingest_adzuna_jobs(
                session=session,
                client=MockPaginatedClient([page]),  # type: ignore[arg-type]
                snapshot_dir=self.snapshot_dir,
            )
            self.assertEqual(result.status, "succeeded")
            self.assertGreaterEqual(result.skills_extracted, 3)

            job = session.scalar(select(Job).where(Job.source_job_id == "adzuna-501"))
            version = job.versions[0]

            skills = {js.skill.name for js in version.skill_requirements}
            self.assertIn("Python", skills)
            self.assertIn("Docker", skills)
            self.assertIn("Kubernetes", skills)
            self.assertIn("PostgreSQL", skills)

            for js in version.skill_requirements:
                self.assertEqual(js.job_version_id, version.id)
                self.assertEqual(js.mapping_status, "exact")
                self.assertTrue(len(js.evidence) > 0)

    def test_failed_run_recorded_when_page_1_fails(self) -> None:
        err = AdzunaHTTPError("Adzuna API returned HTTP 500 on endpoint", status_code=500)
        client = MockPaginatedClient([err])

        with self.Session() as session:
            result = ingest_adzuna_jobs(
                session=session,
                client=client,  # type: ignore[arg-type]
                snapshot_dir=self.snapshot_dir,
            )

            self.assertEqual(result.status, "failed")
            self.assertEqual(result.pages_processed, 0)
            self.assertEqual(result.jobs_received, 0)
            self.assertIsNotNone(result.error_summary)
            self.assertIn("500", result.error_summary)

            run = session.get(IngestionRun, result.run_id)
            self.assertIsNotNone(run)
            self.assertEqual(run.status, "failed")
            self.assertFalse(run.is_complete)
            self.assertEqual(session.scalar(select(Job)), None)

    def test_partial_run_recorded_when_later_page_fails(self) -> None:
        j1 = sample_adzuna_job_payload("adzuna-601", title="Data Analyst")
        page1 = create_mock_adzuna_page(1, [j1], total_count=10)
        err = AdzunaTimeoutError("Request to endpoint timed out")

        client = MockPaginatedClient([page1, err])

        with self.Session() as session:
            result = ingest_adzuna_jobs(
                session=session,
                client=client,  # type: ignore[arg-type]
                snapshot_dir=self.snapshot_dir,
            )

            self.assertEqual(result.status, "partial")
            self.assertEqual(result.pages_processed, 1)
            self.assertEqual(result.snapshots_created, 1)
            self.assertEqual(result.jobs_inserted, 1)
            self.assertIsNotNone(result.error_summary)

            run = session.get(IngestionRun, result.run_id)
            self.assertEqual(run.status, "partial")
            self.assertFalse(run.is_complete)

            # Ensure page 1 data was committed and preserved
            job = session.scalar(select(Job).where(Job.source_job_id == "adzuna-601"))
            self.assertIsNotNone(job)
            self.assertEqual(len(job.versions), 1)

    def test_rollback_on_page_exception(self) -> None:
        j1 = sample_adzuna_job_payload("adzuna-701", title="QA Automation Engineer")
        page = create_mock_adzuna_page(1, [j1], total_count=1)

        with self.Session() as session:
            service = AdzunaIngestionService(
                session=session,
                client=MockPaginatedClient([page]),  # type: ignore[arg-type]
                snapshot_dir=self.snapshot_dir,
            )

            # Monkey-patch _extract_and_attach_skills to simulate unexpected runtime error
            def _exploding_extractor(*args, **kwargs):
                raise RuntimeError("Simulated unhandled processing failure")

            service._extract_and_attach_skills = _exploding_extractor  # type: ignore[assignment]

            result = service.run_ingestion()
            self.assertEqual(result.status, "failed")
            self.assertEqual(result.jobs_inserted, 0)

            # Assert rollback cleaned up partial Job and JobVersion
            self.assertEqual(session.scalar(select(Job).where(Job.source_job_id == "adzuna-701")), None)

    def test_idempotent_repeated_ingestion_runs(self) -> None:
        j1 = sample_adzuna_job_payload("adzuna-801", title="Site Reliability Engineer")
        j2 = sample_adzuna_job_payload("adzuna-802", title="MLOps Engineer")
        page = create_mock_adzuna_page(1, [j1, j2], total_count=2)

        with self.Session() as session:
            res1 = ingest_adzuna_jobs(
                session=session,
                client=MockPaginatedClient([page]),  # type: ignore[arg-type]
                snapshot_dir=self.snapshot_dir,
            )
            self.assertEqual(res1.jobs_inserted, 2)
            self.assertEqual(res1.jobs_skipped, 0)

            # Re-run identical ingestion
            res2 = ingest_adzuna_jobs(
                session=session,
                client=MockPaginatedClient([page]),  # type: ignore[arg-type]
                snapshot_dir=self.snapshot_dir,
            )
            self.assertEqual(res2.jobs_inserted, 0)
            self.assertEqual(res2.jobs_skipped, 2)

            # Confirm no duplicate Job or JobVersion entities
            jobs = session.scalars(select(Job).where(Job.source_job_id.in_(["adzuna-801", "adzuna-802"]))).all()
            self.assertEqual(len(jobs), 2)
            for j in jobs:
                self.assertEqual(len(j.versions), 1)

    def test_no_credential_leakage_in_error_summary(self) -> None:
        secret_key = "super-secret-adzuna-key-1234"
        client = MockPaginatedClient([
            AdzunaHTTPError(f"HTTP 403 Forbidden with key {secret_key}", status_code=403)
        ])
        client.config = AdzunaConfig(app_id="app-id", app_key=secret_key, country="in")

        with self.Session() as session:
            result = ingest_adzuna_jobs(
                session=session,
                client=client,  # type: ignore[arg-type]
                snapshot_dir=self.snapshot_dir,
            )
            self.assertEqual(result.status, "failed")
            self.assertNotIn(secret_key, result.error_summary or "")


class RunScopeCheckpointUnitTests(unittest.TestCase):
    """Unit tests for build_run_scope_checkpoint â€” no DB required."""

    def _build(self, **kwargs) -> dict:
        defaults = dict(
            what=None, where=None, max_pages=None, max_results=None,
            results_per_page=None, pages_processed=0, records_received=0,
        )
        defaults.update(kwargs)
        return build_run_scope_checkpoint(**defaults)

    def test_unbounded_unfiltered_run_is_eligible(self) -> None:
        """An unbounded, unfiltered run with no keyword/geo filter qualifies."""
        cp = self._build()
        self.assertFalse(cp["is_bounded"])
        self.assertFalse(cp["is_filtered"])
        self.assertTrue(cp["eligible_for_full_scope_reconciliation"])

    def test_max_results_bounded_run_is_not_eligible(self) -> None:
        """A run bounded by max_results=5 must not qualify for reconciliation."""
        cp = self._build(max_results=5)
        self.assertTrue(cp["is_bounded"])
        self.assertFalse(cp["eligible_for_full_scope_reconciliation"])
        self.assertEqual(cp["max_results"], 5)

    def test_max_pages_bounded_run_is_not_eligible(self) -> None:
        """A run bounded by max_pages=1 must not qualify for reconciliation."""
        cp = self._build(max_pages=1)
        self.assertTrue(cp["is_bounded"])
        self.assertFalse(cp["eligible_for_full_scope_reconciliation"])
        self.assertEqual(cp["max_pages"], 1)

    def test_keyword_filtered_run_is_not_eligible(self) -> None:
        """A run filtered by what='developer' must not qualify for reconciliation."""
        cp = self._build(what="developer")
        self.assertTrue(cp["is_filtered"])
        self.assertFalse(cp["eligible_for_full_scope_reconciliation"])
        self.assertEqual(cp["what"], "developer")

    def test_geo_filtered_run_is_not_eligible(self) -> None:
        """A run filtered by where='Bangalore' must not qualify for reconciliation."""
        cp = self._build(where="Bangalore")
        self.assertTrue(cp["is_filtered"])
        self.assertFalse(cp["eligible_for_full_scope_reconciliation"])

    def test_bounded_and_filtered_run_captures_all_params(self) -> None:
        """Combined bounded+filtered run captures all scope fields correctly."""
        cp = self._build(
            what="developer", where="Bangalore", max_pages=1, max_results=5,
            results_per_page=5, pages_processed=1, records_received=5,
        )
        self.assertTrue(cp["is_bounded"])
        self.assertTrue(cp["is_filtered"])
        self.assertFalse(cp["eligible_for_full_scope_reconciliation"])
        self.assertEqual(cp["pages_processed"], 1)
        self.assertEqual(cp["records_received"], 5)


class RunScopeIntegrationTests(unittest.TestCase):
    """Integration tests: scope checkpoint persisted on IngestionRun in DB."""

    def setUp(self) -> None:
        self.engine = initialize_database("sqlite:///:memory:")
        self.Session = create_session_factory(self.engine)
        self.temp_dir = tempfile.mkdtemp()
        self.snapshot_dir = Path(self.temp_dir) / "snapshots"

    def tearDown(self) -> None:
        self.engine.dispose()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_bounded_five_result_run_scope_stored_and_not_eligible(self) -> None:
        """Bounded run (max_results=5) records scope and sets eligible=False."""
        j1 = sample_adzuna_job_payload("scope-101")
        page = create_mock_adzuna_page(1, [j1])
        client = MockPaginatedClient([page])

        with self.Session() as session:
            result = ingest_adzuna_jobs(
                session=session,
                client=client,  # type: ignore[arg-type]
                snapshot_dir=self.snapshot_dir,
                max_results=5,
            )

        self.assertEqual(result.status, "succeeded")
        # Result object carries the scope
        self.assertIsNotNone(result.scope_checkpoint)
        sc = result.scope_checkpoint
        self.assertTrue(sc["is_bounded"])
        self.assertFalse(sc["eligible_for_full_scope_reconciliation"])
        self.assertEqual(sc["max_results"], 5)

        # Also verify persisted on the DB row
        with self.Session() as session:
            run = session.get(IngestionRun, result.run_id)
            self.assertIsNotNone(run.cursor_or_checkpoint)
            db_sc = json.loads(run.cursor_or_checkpoint)
            self.assertFalse(db_sc["eligible_for_full_scope_reconciliation"])
            self.assertTrue(db_sc["is_bounded"])

    def test_filtered_developer_search_scope_stored_and_not_eligible(self) -> None:
        """Filtered run (what='developer') is not eligible for reconciliation."""
        j1 = sample_adzuna_job_payload("scope-201")
        page = create_mock_adzuna_page(1, [j1])

        with self.Session() as session:
            result = ingest_adzuna_jobs(
                session=session,
                client=MockPaginatedClient([page]),  # type: ignore[arg-type]
                snapshot_dir=self.snapshot_dir,
                what="developer",
            )

        sc = result.scope_checkpoint
        self.assertIsNotNone(sc)
        self.assertTrue(sc["is_filtered"])
        self.assertEqual(sc["what"], "developer")
        self.assertFalse(sc["eligible_for_full_scope_reconciliation"])

    def test_pagination_ending_normally_stores_pages_processed(self) -> None:
        """Multi-page unbounded run records accurate pages_processed count."""
        j1 = sample_adzuna_job_payload("scope-301")
        j2 = sample_adzuna_job_payload("scope-302")
        page1 = create_mock_adzuna_page(1, [j1])
        page2 = create_mock_adzuna_page(2, [j2])

        with self.Session() as session:
            result = ingest_adzuna_jobs(
                session=session,
                client=MockPaginatedClient([page1, page2]),  # type: ignore[arg-type]
                snapshot_dir=self.snapshot_dir,
            )

        self.assertEqual(result.status, "succeeded")
        sc = result.scope_checkpoint
        self.assertEqual(sc["pages_processed"], 2)
        self.assertEqual(sc["records_received"], 2)
        self.assertEqual(sc["max_pages"], None)
        self.assertEqual(sc["max_results"], None)
        # Unbounded, unfiltered â†’ eligible
        self.assertTrue(sc["eligible_for_full_scope_reconciliation"])

    def test_failed_run_still_stores_scope_checkpoint(self) -> None:
        """A fully failed run (page 1 error) still persists scope to DB."""
        err = AdzunaHTTPError("HTTP 500", status_code=500)

        with self.Session() as session:
            result = ingest_adzuna_jobs(
                session=session,
                client=MockPaginatedClient([err]),  # type: ignore[arg-type]
                snapshot_dir=self.snapshot_dir,
                what="developer",
                max_results=5,
            )

        self.assertEqual(result.status, "failed")
        self.assertFalse(result.scope_checkpoint["eligible_for_full_scope_reconciliation"])

        with self.Session() as session:
            run = session.get(IngestionRun, result.run_id)
            self.assertFalse(run.is_complete)
            self.assertIsNotNone(run.cursor_or_checkpoint)
            db_sc = json.loads(run.cursor_or_checkpoint)
            self.assertTrue(db_sc["is_bounded"])
            self.assertTrue(db_sc["is_filtered"])
            self.assertFalse(db_sc["eligible_for_full_scope_reconciliation"])

    def test_partial_run_scope_stored_and_not_eligible(self) -> None:
        """Partial run (page 2 error) persists scope and is not eligible."""
        j1 = sample_adzuna_job_payload("scope-401")
        page1 = create_mock_adzuna_page(1, [j1])
        err = AdzunaTimeoutError("timeout")

        with self.Session() as session:
            result = ingest_adzuna_jobs(
                session=session,
                client=MockPaginatedClient([page1, err]),  # type: ignore[arg-type]
                snapshot_dir=self.snapshot_dir,
            )

        self.assertEqual(result.status, "partial")
        # Even an unbounded run is not eligible when it failed mid-way (is_complete=False)
        sc = result.scope_checkpoint
        self.assertIsNotNone(sc)
        # pages_processed reflects only what succeeded before the error
        self.assertEqual(sc["pages_processed"], 1)

        with self.Session() as session:
            run = session.get(IngestionRun, result.run_id)
            self.assertFalse(run.is_complete)
            db_sc = json.loads(run.cursor_or_checkpoint)
            self.assertEqual(db_sc["pages_processed"], 1)


class MockSegmentedClient:
    """Mock Adzuna client providing segmented page responses by location."""

    def __init__(self, pages_by_where: dict[str, list[AdzunaPage | Exception]]) -> None:
        self.pages_by_where = pages_by_where
        self.calls: list[dict[str, Any]] = []
        self.config = AdzunaConfig(app_id="test-app-id", app_key="test-app-key", country="in")
        self.request_hook: Any | None = None

    def paginate(self, *args, **kwargs):
        self.calls.append(kwargs)
        where = kwargs.get("where")
        start_page = kwargs.get("start_page", 1)
        max_pages = kwargs.get("max_pages")
        pages = self.pages_by_where.get(where, [])

        start_idx = max(0, start_page - 1)
        sliced_pages = pages[start_idx:]
        if max_pages is not None:
            sliced_pages = sliced_pages[:max_pages]

        for item in sliced_pages:
            if getattr(self, "request_hook", None) is not None:
                self.request_hook()
            if isinstance(item, Exception):
                raise item
            yield item


class AdzunaSegmentedBatchTests(unittest.TestCase):
    """Tests for Milestone 4: Controlled Segmented Pilot Collection."""

    def setUp(self) -> None:
        self.engine = initialize_database("sqlite:///:memory:")
        self.Session = create_session_factory(self.engine)
        self.temp_dir = tempfile.mkdtemp()
        self.snapshot_dir = Path(self.temp_dir) / "snapshots"

    def tearDown(self) -> None:
        self.engine.dispose()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_verify_account_quota_config_safe(self) -> None:
        """Verify account quota without leaking credentials."""
        config = AdzunaConfig(app_id="my-secret-id", app_key="my-secret-key-12345", country="in")
        quota = verify_account_quota_config(config)

        self.assertTrue(quota["credentials_configured"])
        self.assertEqual(quota["app_id_length"], len("my-secret-id"))
        self.assertEqual(quota["app_key_length"], len("my-secret-key-12345"))
        self.assertTrue(quota["within_daily_quota"])
        self.assertTrue(quota["within_minute_rate_limit"])
        self.assertEqual(quota["daily_quota_consumption_pct"], 14.0)
        self.assertEqual(quota["quota_verification_status"], "verified_within_limits")

        # Confirm no credentials leak in output
        dumped = json.dumps(quota)
        self.assertNotIn("my-secret-id", dumped)
        self.assertNotIn("my-secret-key-12345", dumped)

    def test_pilot_batch_executes_all_seven_segments(self) -> None:
        """All seven segments execute sequentially with correct parameters and SCD versioning."""
        cities = ["Bengaluru", "Hyderabad", "Pune", "Mumbai", "Delhi", "Noida", "Gurgaon"]
        pages_by_city: dict[str, list[AdzunaPage]] = {}

        for idx, city in enumerate(cities, 1):
            j = sample_adzuna_job_payload(f"job-seg-{idx}", title=f"{city} Software Engineer", location=f"{city}, India")
            p = create_mock_adzuna_page(1, [j], total_count=1)
            pages_by_city[city] = [p]

        client = MockSegmentedClient(pages_by_city)

        with self.Session() as session:
            result = ingest_adzuna_pilot_batch(
                session=session,
                client=client,
                snapshot_dir=self.snapshot_dir,
                sleep_fn=lambda s: None,
            )

        self.assertEqual(result.status, "succeeded")
        self.assertTrue(result.is_complete)
        self.assertEqual(result.total_segments_planned, 7)
        self.assertEqual(result.segments_completed, 7)
        self.assertEqual(result.total_jobs_received, 7)
        self.assertEqual(result.total_jobs_inserted, 7)
        self.assertEqual(result.total_jobs_skipped, 0)
        self.assertEqual(result.matrix_version, PILOT_M4_MATRIX_VERSION)
        self.assertFalse(result.eligible_for_full_scope_reconciliation)
        self.assertEqual(len(client.calls), 7)

        # Verify all 7 segments are represented in checkpoint
        sc = result.checkpoint
        self.assertEqual(len(sc["segments"]), 7)
        for s in sc["segments"]:
            self.assertEqual(s["status"], "succeeded")
            self.assertEqual(s["params"]["what"], "developer")
            self.assertEqual(s["params"]["category"], "it-jobs")
            self.assertEqual(s["params"]["max_pages"], 5)

        # Verify DB records
        with self.Session() as session:
            jobs = session.scalars(select(Job)).all()
            self.assertEqual(len(jobs), 7)
            runs = session.scalars(select(IngestionRun)).all()
            self.assertEqual(len(runs), 1)
            self.assertEqual(runs[0].status, "succeeded")
            self.assertTrue(runs[0].is_complete)

    def test_pilot_batch_enforces_request_limit_ceiling(self) -> None:
        """Batch halts when cumulative total requests reaches max_total_requests."""
        cities = ["Bengaluru", "Hyderabad", "Pune", "Mumbai", "Delhi", "Noida", "Gurgaon"]
        pages_by_city: dict[str, list[AdzunaPage]] = {}

        # Give each city 5 pages
        for idx, city in enumerate(cities, 1):
            pages = [
                create_mock_adzuna_page(p, [sample_adzuna_job_payload(f"job-{idx}-{p}")])
                for p in range(1, 6)
            ]
            pages_by_city[city] = pages

        client = MockSegmentedClient(pages_by_city)

        # Cap requests at 3
        with self.Session() as session:
            result = ingest_adzuna_pilot_batch(
                session=session,
                client=client,
                snapshot_dir=self.snapshot_dir,
                max_total_requests=3,
                sleep_fn=lambda s: None,
            )

        self.assertEqual(result.status, "partial")
        self.assertFalse(result.is_complete)
        self.assertEqual(result.total_requests_made, 3)
        self.assertEqual(result.total_jobs_received, 3)

        # Remaining segments must be flagged as stopped by limit
        sc = result.checkpoint
        stopped_segs = [s for s in sc["segments"] if s["status"] == "stopped_by_request_limit"]
        self.assertGreater(len(stopped_segs), 0)

    def test_pilot_batch_enforces_minimum_request_interval(self) -> None:
        """Requests must enforce >= 2.5s interval, including across segment boundaries."""
        cities = ["Bengaluru", "Hyderabad"]
        pages_by_city = {
            "Bengaluru": [
                create_mock_adzuna_page(1, [sample_adzuna_job_payload("j-blr-1")]),
                create_mock_adzuna_page(2, [sample_adzuna_job_payload("j-blr-2")]),
            ],
            "Hyderabad": [
                create_mock_adzuna_page(1, [sample_adzuna_job_payload("j-hyd-1")]),
            ],
        }

        two_segments = [
            {"segment_id": "SEG-BLR", "where": "Bengaluru", "what": "developer", "category": "it-jobs", "results_per_page": 20, "max_pages": 2},
            {"segment_id": "SEG-HYD", "where": "Hyderabad", "what": "developer", "category": "it-jobs", "results_per_page": 20, "max_pages": 1},
        ]

        current_time = [1000.0]
        sleep_durations: list[float] = []

        def mock_time() -> float:
            return current_time[0]

        def mock_sleep(seconds: float) -> None:
            sleep_durations.append(seconds)
            current_time[0] += seconds

        client = MockSegmentedClient(pages_by_city)

        with self.Session() as session:
            result = ingest_adzuna_pilot_batch(
                session=session,
                client=client,
                segments=two_segments,
                snapshot_dir=self.snapshot_dir,
                min_request_interval_seconds=2.5,
                sleep_fn=mock_sleep,
                time_fn=mock_time,
            )

        self.assertEqual(result.status, "succeeded")
        self.assertEqual(result.total_requests_made, 3)
        # 3 requests means 2 intervals slept:
        # 1: between BLR page 1 and BLR page 2
        # 2: between BLR page 2 and HYD page 1 (cross-segment boundary!)
        self.assertEqual(len(sleep_durations), 2)
        for s in sleep_durations:
            self.assertEqual(s, 2.5)

    def test_pilot_batch_cross_segment_deduplication(self) -> None:
        """Job appearing in both Delhi and Noida is inserted once and skipped in the second."""
        shared_job = sample_adzuna_job_payload("ncr-shared-001", title="Fullstack Lead", location="Noida/Delhi")
        delhi_only = sample_adzuna_job_payload("del-only-002", title="Delhi Dev", location="Delhi")
        noida_only = sample_adzuna_job_payload("noi-only-003", title="Noida Dev", location="Noida")

        pages_by_city = {
            "Delhi": [create_mock_adzuna_page(1, [shared_job, delhi_only])],
            "Noida": [create_mock_adzuna_page(1, [shared_job, noida_only])],
        }

        two_segments = [
            {"segment_id": "SEG-DEL", "where": "Delhi", "what": "developer", "category": "it-jobs", "results_per_page": 20, "max_pages": 1},
            {"segment_id": "SEG-NOI", "where": "Noida", "what": "developer", "category": "it-jobs", "results_per_page": 20, "max_pages": 1},
        ]

        client = MockSegmentedClient(pages_by_city)

        with self.Session() as session:
            result = ingest_adzuna_pilot_batch(
                session=session,
                client=client,
                segments=two_segments,
                snapshot_dir=self.snapshot_dir,
                sleep_fn=lambda s: None,
            )

        self.assertEqual(result.status, "succeeded")
        self.assertEqual(result.total_jobs_received, 4)
        self.assertEqual(result.total_jobs_inserted, 3)
        self.assertEqual(result.total_jobs_skipped, 1)

        # Check DB: exactly 3 Job entities, each with exactly 1 version
        with self.Session() as session:
            jobs = session.scalars(select(Job)).all()
            self.assertEqual(len(jobs), 3)
            shared_db = session.scalar(select(Job).where(Job.source_job_id == "ncr-shared-001"))
            self.assertIsNotNone(shared_db)
            self.assertEqual(len(shared_db.versions), 1)

    def test_pilot_batch_changed_and_unchanged_jobs(self) -> None:
        """Segment 1 sees initial job, Segment 2 sees changed salary for that job."""
        job_v1 = sample_adzuna_job_payload("dyn-001", title="Cloud Dev", salary_min=1000000.0, salary_max=1500000.0)
        job_v2 = sample_adzuna_job_payload("dyn-001", title="Cloud Dev", salary_min=1800000.0, salary_max=2400000.0)

        pages_by_city = {
            "Bengaluru": [create_mock_adzuna_page(1, [job_v1])],
            "Hyderabad": [create_mock_adzuna_page(1, [job_v2])],
        }

        two_segments = [
            {"segment_id": "SEG-BLR", "where": "Bengaluru", "what": "developer", "category": "it-jobs", "results_per_page": 20, "max_pages": 1},
            {"segment_id": "SEG-HYD", "where": "Hyderabad", "what": "developer", "category": "it-jobs", "results_per_page": 20, "max_pages": 1},
        ]

        client = MockSegmentedClient(pages_by_city)

        with self.Session() as session:
            result = ingest_adzuna_pilot_batch(
                session=session,
                client=client,
                segments=two_segments,
                snapshot_dir=self.snapshot_dir,
                sleep_fn=lambda s: None,
            )

        self.assertEqual(result.status, "succeeded")
        self.assertEqual(result.total_jobs_inserted, 1)
        self.assertEqual(result.total_jobs_updated, 1)

        with self.Session() as session:
            job = session.scalar(select(Job).where(Job.source_job_id == "dyn-001"))
            self.assertEqual(len(job.versions), 2)
            v1 = [v for v in job.versions if v.version_number == 1][0]
            v2 = [v for v in job.versions if v.version_number == 2][0]
            self.assertFalse(v1.is_current)
            self.assertTrue(v2.is_current)

    def test_pilot_batch_partial_failure_and_safe_resume(self) -> None:
        """Failing segment halts batch; resume skips successful segments and completes."""
        pages_by_city_pass1 = {
            "Bengaluru": [create_mock_adzuna_page(1, [sample_adzuna_job_payload("blr-1")])],
            "Hyderabad": [create_mock_adzuna_page(1, [sample_adzuna_job_payload("hyd-1")])],
            "Pune": [AdzunaHTTPError("HTTP 500 error on Pune", status_code=500)],
            "Mumbai": [create_mock_adzuna_page(1, [sample_adzuna_job_payload("mum-1")])],
        }

        four_segments = [
            {"segment_id": "SEG-BLR", "where": "Bengaluru", "what": "developer", "category": "it-jobs", "results_per_page": 20, "max_pages": 1},
            {"segment_id": "SEG-HYD", "where": "Hyderabad", "what": "developer", "category": "it-jobs", "results_per_page": 20, "max_pages": 1},
            {"segment_id": "SEG-PUN", "where": "Pune", "what": "developer", "category": "it-jobs", "results_per_page": 20, "max_pages": 1},
            {"segment_id": "SEG-MUM", "where": "Mumbai", "what": "developer", "category": "it-jobs", "results_per_page": 20, "max_pages": 1},
        ]

        client1 = MockSegmentedClient(pages_by_city_pass1)

        with self.Session() as session:
            res1 = ingest_adzuna_pilot_batch(
                session=session,
                client=client1,
                segments=four_segments,
                snapshot_dir=self.snapshot_dir,
                sleep_fn=lambda s: None,
            )

        self.assertEqual(res1.status, "partial")
        self.assertFalse(res1.is_complete)
        self.assertEqual(res1.segments_completed, 2)  # BLR and HYD succeeded
        self.assertEqual(res1.total_jobs_inserted, 2)
        initial_batch_id = res1.batch_id

        # Pass 2: Resume with fixed Pune
        pages_by_city_pass2 = {
            "Pune": [create_mock_adzuna_page(1, [sample_adzuna_job_payload("pun-1")])],
            "Mumbai": [create_mock_adzuna_page(1, [sample_adzuna_job_payload("mum-1")])],
        }
        client2 = MockSegmentedClient(pages_by_city_pass2)

        with self.Session() as session:
            res2 = ingest_adzuna_pilot_batch(
                session=session,
                client=client2,
                segments=four_segments,
                resume_run_id=res1.run_id,
                snapshot_dir=self.snapshot_dir,
                sleep_fn=lambda s: None,
            )

        self.assertEqual(res2.status, "succeeded")
        self.assertTrue(res2.is_complete)
        self.assertEqual(res2.batch_id, initial_batch_id)  # Preserved batch identity
        self.assertEqual(res2.segments_completed, 4)
        self.assertEqual(res2.total_jobs_inserted, 4)

        # BLR and HYD should NOT have been re-requested
        requested_cities = [c.get("where") for c in client2.calls]
        self.assertNotIn("Bengaluru", requested_cities)
        self.assertNotIn("Hyderabad", requested_cities)
        self.assertIn("Pune", requested_cities)
        self.assertIn("Mumbai", requested_cities)

    def test_pilot_batch_rejects_matrix_version_mismatch_on_resume(self) -> None:
        """Resuming with altered matrix version raises ValueError."""
        two_segments = [
            {"segment_id": "SEG-BLR", "where": "Bengaluru", "what": "developer", "category": "it-jobs", "results_per_page": 20, "max_pages": 1},
        ]
        client = MockSegmentedClient({"Bengaluru": [create_mock_adzuna_page(1, [sample_adzuna_job_payload("blr-1")])]})

        with self.Session() as session:
            res1 = ingest_adzuna_pilot_batch(
                session=session,
                client=client,
                segments=two_segments,
                matrix_version="m4_pilot_v1",
                snapshot_dir=self.snapshot_dir,
                sleep_fn=lambda s: None,
            )

            with self.assertRaises(ValueError) as ctx:
                ingest_adzuna_pilot_batch(
                    session=session,
                    client=client,
                    segments=two_segments,
                    matrix_version="m4_pilot_v2",  # Mismatch!
                    resume_run_id=res1.run_id,
                    snapshot_dir=self.snapshot_dir,
                )
            self.assertIn("Matrix version mismatch", str(ctx.exception))

    def test_pilot_batch_rejects_incompatible_parameters_on_resume(self) -> None:
        """Resuming with altered query parameters raises ValueError."""
        seg_orig = [{"segment_id": "SEG-BLR", "where": "Bengaluru", "what": "developer", "category": "it-jobs", "results_per_page": 20, "max_pages": 1}]
        seg_changed = [{"segment_id": "SEG-BLR", "where": "Chennai", "what": "developer", "category": "it-jobs", "results_per_page": 20, "max_pages": 1}]

        client = MockSegmentedClient({"Bengaluru": [create_mock_adzuna_page(1, [sample_adzuna_job_payload("blr-1")])]})

        with self.Session() as session:
            res1 = ingest_adzuna_pilot_batch(
                session=session,
                client=client,
                segments=seg_orig,
                snapshot_dir=self.snapshot_dir,
                sleep_fn=lambda s: None,
            )

            with self.assertRaises(ValueError) as ctx:
                ingest_adzuna_pilot_batch(
                    session=session,
                    client=client,
                    segments=seg_changed,  # Parameter changed!
                    resume_run_id=res1.run_id,
                    snapshot_dir=self.snapshot_dir,
                )
            self.assertIn("Incompatible query parameters on resume", str(ctx.exception))

    def test_pilot_batch_reconciliation_permanently_disabled(self) -> None:
        """Assert reconciliation eligibility is hardcoded to False across batch states."""
        client = MockSegmentedClient({"Bengaluru": [create_mock_adzuna_page(1, [sample_adzuna_job_payload("blr-1")])]})
        one_seg = [{"segment_id": "SEG-BLR", "where": "Bengaluru", "what": "developer", "category": "it-jobs", "results_per_page": 20, "max_pages": 1}]

        with self.Session() as session:
            res = ingest_adzuna_pilot_batch(
                session=session,
                client=client,
                segments=one_seg,
                snapshot_dir=self.snapshot_dir,
                sleep_fn=lambda s: None,
            )

        self.assertFalse(res.eligible_for_full_scope_reconciliation)
        self.assertFalse(res.checkpoint["eligible_for_full_scope_reconciliation"])
        self.assertIn("permanently disabled", res.checkpoint["reconciliation_lock_reason"])

    def test_pilot_batch_resume_after_25_requests_allows_only_10_more(self) -> None:
        """Fix 1: Resuming after 25 requests permits only 10 more to strictly cap total requests at 35."""
        cities = ["Bengaluru", "Hyderabad", "Pune", "Mumbai", "Delhi", "Noida", "Gurgaon"]
        pages_by_city: dict[str, list[AdzunaPage]] = {
            city: [create_mock_adzuna_page(p, [sample_adzuna_job_payload(f"job-{city}-{p}")]) for p in range(1, 6)]
            for city in cities
        }
        client = MockSegmentedClient(pages_by_city)

        # Pass 1: Cap at 25 requests
        with self.Session() as session:
            res1 = ingest_adzuna_pilot_batch(
                session=session,
                client=client,
                snapshot_dir=self.snapshot_dir,
                max_total_requests=25,
                sleep_fn=lambda s: None,
            )

        self.assertEqual(res1.status, "partial")
        self.assertEqual(res1.total_requests_made, 25)
        self.assertEqual(res1.checkpoint["total_requests_made"], 25)

        # Pass 2: Resume with max 30 requests (should allow exactly 30 - 25 = 5 more requests)
        with self.Session() as session:
            res2 = ingest_adzuna_pilot_batch(
                session=session,
                client=client,
                resume_run_id=res1.run_id,
                snapshot_dir=self.snapshot_dir,
                max_total_requests=30,
                sleep_fn=lambda s: None,
            )

        self.assertEqual(res2.status, "partial")
        self.assertEqual(res2.total_requests_made, 30)
        self.assertEqual(res2.checkpoint["total_requests_made"], 30)

        # Pass 3: Resume with max 35 requests (allows 5 more to reach 35 total)
        with self.Session() as session:
            res3 = ingest_adzuna_pilot_batch(
                session=session,
                client=client,
                resume_run_id=res2.run_id,
                snapshot_dir=self.snapshot_dir,
                max_total_requests=35,
                sleep_fn=lambda s: None,
            )

        self.assertEqual(res3.status, "succeeded")
        self.assertEqual(res3.total_requests_made, 35)
        self.assertEqual(res3.checkpoint["total_requests_made"], 35)

    def test_pilot_batch_request_budget_counts_http_retries(self) -> None:
        """Fix 2: Request limiter hook meters internal HTTP retries in AdzunaClient."""
        job_json = json.dumps({
            "__class": "Adzuna::API::Response::JobSearchResults",
            "count": 1,
            "results": [sample_adzuna_job_payload("retry-job-1")],
        }).encode("utf-8")

        # Attempt 1: HTTP 500 error; Attempt 2: 200 OK
        opener = MockOpener([
            MockHTTPResponse(status=500, body=b"Internal Server Error"),
            MockHTTPResponse(status=200, body=job_json),
        ])
        config = AdzunaConfig(app_id="test-id", app_key="test-key", country="in", max_retries=2, backoff_factor=0.01)
        client = AdzunaClient(config, opener=opener, sleep_fn=lambda s: None)

        one_seg = [{"segment_id": "SEG-BLR", "where": "Bengaluru", "what": "developer", "category": "it-jobs", "results_per_page": 20, "max_pages": 1}]

        with self.Session() as session:
            res = ingest_adzuna_pilot_batch(
                session=session,
                client=client,
                segments=one_seg,
                snapshot_dir=self.snapshot_dir,
                max_total_requests=35,
                sleep_fn=lambda s: None,
            )

        self.assertEqual(res.status, "succeeded")
        # 1 page was retrieved, but it required 2 HTTP attempts (1 failure + 1 retry)
        self.assertEqual(res.total_requests_made, 2)
        self.assertEqual(res.checkpoint["total_requests_made"], 2)

    def test_pilot_batch_retry_attempts_respect_minimum_interval(self) -> None:
        """Fix 2: HTTP retries must respect the minimum 2.5-second interval between request starts."""
        job_json = json.dumps({
            "__class": "Adzuna::API::Response::JobSearchResults",
            "count": 1,
            "results": [sample_adzuna_job_payload("retry-delay-job")],
        }).encode("utf-8")

        opener = MockOpener([
            MockHTTPResponse(status=500, body=b"Internal Server Error"),
            MockHTTPResponse(status=200, body=job_json),
        ])
        config = AdzunaConfig(app_id="test-id", app_key="test-key", country="in", max_retries=2, backoff_factor=0.01)
        client = AdzunaClient(config, opener=opener)

        current_time = [1000.0]
        intervals_slept: list[float] = []

        def mock_time() -> float:
            return current_time[0]

        def mock_sleep(seconds: float) -> None:
            intervals_slept.append(seconds)
            current_time[0] += seconds

        one_seg = [{"segment_id": "SEG-BLR", "where": "Bengaluru", "what": "developer", "category": "it-jobs", "results_per_page": 20, "max_pages": 1}]

        with self.Session() as session:
            res = ingest_adzuna_pilot_batch(
                session=session,
                client=client,
                segments=one_seg,
                snapshot_dir=self.snapshot_dir,
                min_request_interval_seconds=2.5,
                sleep_fn=mock_sleep,
                time_fn=mock_time,
            )

        self.assertEqual(res.status, "succeeded")
        self.assertEqual(res.total_requests_made, 2)
        # Attempt 1 -> Attempt 2 had interval slept >= 2.5
        self.assertGreaterEqual(sum(intervals_slept), 2.5)

    def test_pilot_batch_page_checkpoint_updated_after_every_committed_page(self) -> None:
        """Fix 3: IngestionRun.cursor_or_checkpoint is updated and committed after each page."""
        pages = [
            create_mock_adzuna_page(1, [sample_adzuna_job_payload("chk-1")]),
            create_mock_adzuna_page(2, [sample_adzuna_job_payload("chk-2")]),
            create_mock_adzuna_page(3, [sample_adzuna_job_payload("chk-3")]),
        ]
        client = MockSegmentedClient({"Bengaluru": pages})
        one_seg = [{"segment_id": "SEG-BLR", "where": "Bengaluru", "what": "developer", "category": "it-jobs", "results_per_page": 20, "max_pages": 3}]

        with self.Session() as session:
            res = ingest_adzuna_pilot_batch(
                session=session,
                client=client,
                segments=one_seg,
                snapshot_dir=self.snapshot_dir,
                sleep_fn=lambda s: None,
            )

        self.assertEqual(res.status, "succeeded")
        self.assertEqual(res.checkpoint["segments"][0]["pages_processed"], 3)
        self.assertEqual(res.checkpoint["records_received"], 3)

        with self.Session() as session:
            run = session.get(IngestionRun, res.run_id)
            db_chk = json.loads(run.cursor_or_checkpoint)
            self.assertEqual(db_chk["segments"][0]["pages_processed"], 3)
            self.assertEqual(db_chk["records_received"], 3)

    def test_pilot_batch_simulated_failure_after_page_2_and_safe_resume(self) -> None:
        """Fix 3 & Fix 4: Mid-segment failure after page 2 preserves committed pages and resumes from page 3."""
        pages_pass1 = [
            create_mock_adzuna_page(1, [sample_adzuna_job_payload("sim-1")]),
            create_mock_adzuna_page(2, [sample_adzuna_job_payload("sim-2")]),
            AdzunaHTTPError("HTTP 500 on page 3", status_code=500),
        ]
        client1 = MockSegmentedClient({"Bengaluru": pages_pass1})
        one_seg = [{"segment_id": "SEG-BLR", "where": "Bengaluru", "what": "developer", "category": "it-jobs", "results_per_page": 20, "max_pages": 5}]

        # Pass 1: Fails on page 3
        with self.Session() as session:
            res1 = ingest_adzuna_pilot_batch(
                session=session,
                client=client1,
                segments=one_seg,
                snapshot_dir=self.snapshot_dir,
                sleep_fn=lambda s: None,
            )

        self.assertEqual(res1.status, "partial")
        self.assertEqual(res1.checkpoint["segments"][0]["status"], "failed")
        self.assertEqual(res1.checkpoint["segments"][0]["pages_processed"], 2)
        self.assertEqual(res1.checkpoint["records_received"], 2)
        self.assertEqual(res1.total_jobs_inserted, 2)

        # Confirm DB has exactly 2 snapshots and 2 jobs committed from pass 1
        with self.Session() as session:
            snaps = session.scalars(select(RawSnapshot)).all()
            self.assertEqual(len(snaps), 2)
            jobs = session.scalars(select(Job)).all()
            self.assertEqual(len(jobs), 2)

        # Pass 2: Resume with pages 1..5 available (should resume from page 3 and not duplicate pages 1 & 2)
        pages_pass2 = [
            create_mock_adzuna_page(1, [sample_adzuna_job_payload("sim-1")]),
            create_mock_adzuna_page(2, [sample_adzuna_job_payload("sim-2")]),
            create_mock_adzuna_page(3, [sample_adzuna_job_payload("sim-3")]),
            create_mock_adzuna_page(4, [sample_adzuna_job_payload("sim-4")]),
            create_mock_adzuna_page(5, [sample_adzuna_job_payload("sim-5")]),
        ]
        client2 = MockSegmentedClient({"Bengaluru": pages_pass2})

        with self.Session() as session:
            res2 = ingest_adzuna_pilot_batch(
                session=session,
                client=client2,
                segments=one_seg,
                resume_run_id=res1.run_id,
                snapshot_dir=self.snapshot_dir,
                sleep_fn=lambda s: None,
            )

        self.assertEqual(res2.status, "succeeded")
        self.assertTrue(res2.is_complete)
        self.assertEqual(res2.checkpoint["segments"][0]["pages_processed"], 5)
        self.assertEqual(res2.total_jobs_inserted, 5)

        # Check pagination call in client2 requested start_page=3
        self.assertEqual(len(client2.calls), 1)
        self.assertEqual(client2.calls[0]["start_page"], 3)
        self.assertEqual(client2.calls[0]["max_pages"], 3)

        # Confirm total DB entities: 2 (from pass 1) + 3 (from pass 2) = 5 snapshots and 5 jobs total
        with self.Session() as session:
            snaps = session.scalars(select(RawSnapshot)).all()
            self.assertEqual(len(snaps), 5)
            jobs = session.scalars(select(Job)).all()
            self.assertEqual(len(jobs), 5)
            versions = session.scalars(select(JobVersion)).all()
            self.assertEqual(len(versions), 5)

    def test_pilot_batch_request_budget_remains_cumulative_across_multiple_resumes(self) -> None:
        """Fix 1: Request budget remains cumulative across multiple sequential resume attempts."""
        cities = ["Bengaluru", "Hyderabad", "Pune", "Mumbai", "Delhi", "Noida", "Gurgaon"]
        pages_by_city: dict[str, list[AdzunaPage]] = {
            city: [create_mock_adzuna_page(p, [sample_adzuna_job_payload(f"multi-{city}-{p}")]) for p in range(1, 6)]
            for city in cities
        }
        client = MockSegmentedClient(pages_by_city)

        # Attempt 1: 10 requests
        with self.Session() as session:
            r1 = ingest_adzuna_pilot_batch(session=session, client=client, snapshot_dir=self.snapshot_dir, max_total_requests=10, sleep_fn=lambda s: None)
        self.assertEqual(r1.total_requests_made, 10)
        self.assertEqual(r1.status, "partial")

        # Attempt 2: Resume with max 20 requests (makes 10 more -> total 20)
        with self.Session() as session:
            r2 = ingest_adzuna_pilot_batch(session=session, client=client, resume_run_id=r1.run_id, snapshot_dir=self.snapshot_dir, max_total_requests=20, sleep_fn=lambda s: None)
        self.assertEqual(r2.total_requests_made, 20)
        self.assertEqual(r2.status, "partial")

        # Attempt 3: Resume with max 30 requests (makes 10 more -> total 30)
        with self.Session() as session:
            r3 = ingest_adzuna_pilot_batch(session=session, client=client, resume_run_id=r2.run_id, snapshot_dir=self.snapshot_dir, max_total_requests=30, sleep_fn=lambda s: None)
        self.assertEqual(r3.total_requests_made, 30)
        self.assertEqual(r3.status, "partial")

        # Attempt 4: Resume with max 30 requests (budget already at 30, 0 more allowed, remains partial)
        with self.Session() as session:
            r4 = ingest_adzuna_pilot_batch(session=session, client=client, resume_run_id=r3.run_id, snapshot_dir=self.snapshot_dir, max_total_requests=30, sleep_fn=lambda s: None)
        self.assertEqual(r4.total_requests_made, 30)
        self.assertEqual(r4.status, "partial")

        # Attempt 5: Resume with max 35 requests (makes 5 more -> total 35, all 7 segments complete)
        with self.Session() as session:
            r5 = ingest_adzuna_pilot_batch(session=session, client=client, resume_run_id=r4.run_id, snapshot_dir=self.snapshot_dir, max_total_requests=35, sleep_fn=lambda s: None)
        self.assertEqual(r5.total_requests_made, 35)
        self.assertEqual(r5.status, "succeeded")
        self.assertTrue(r5.is_complete)


if __name__ == "__main__":
    unittest.main()

