"""Transactional live-ingestion service for the Adzuna Job Search API.

Ingests Adzuna API pages into JobRadar's database foundation:
- Registers/reuses source `adzuna_india`
- Creates auditable `ingestion_runs` and `raw_snapshots`
- Stores raw API responses as hash-addressed JSON files on disk
- Tracks source-aware job identities and content fingerprints
- Implements SCD: creates new `job_versions` only on content change
- Updates `last_seen` timestamp and run reference on unchanged jobs
- Runs deterministic skill extraction and attaches skills to `job_versions`
- Transactional and idempotent with partial/failed run accounting
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
import logging
from pathlib import Path
import time
from typing import Any, Callable

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from .adzuna_client import (
    AdzunaBudgetExhaustedError,
    AdzunaClient,
    AdzunaConfig,
    AdzunaConfigError,
    AdzunaError,
    AdzunaJob,
    AdzunaPage,
    redact_text,
)
from .database import PROJECT_ROOT
from .models import IngestionRun, Job, JobSkill, JobVersion, RawSnapshot, Skill, Source
from .skills import (
    build_description_patterns,
    extract_job_skills,
    load_alias_map,
    load_category_map,
)


ADZUNA_SOURCE_CODE = "adzuna_india"
ADZUNA_SOURCE_NAME = "Adzuna India API"
ADZUNA_BASE_URL = "https://api.adzuna.com/v1/api/jobs/in"
DEFAULT_SNAPSHOT_DIR = PROJECT_ROOT / "data" / "snapshots" / "adzuna"
ADZUNA_TRANSFORM_VERSION = "adzuna-transform-v1"
ADZUNA_SKILL_EXTRACTION_VERSION = "expanded-deterministic-v1"
DEFAULT_ALIASES = PROJECT_ROOT / "data" / "reference" / "skill_aliases.json"
DEFAULT_CATEGORIES = PROJECT_ROOT / "data" / "reference" / "skill_categories.json"

PILOT_M4_MATRIX_VERSION = "m4_pilot_v1"
DEFAULT_MIN_REQUEST_INTERVAL_SECONDS = 2.5
DEFAULT_MAX_PILOT_REQUESTS = 35
DEFAULT_MAX_PILOT_RESULTS = 700

DEFAULT_PILOT_SEGMENTS: list[dict[str, Any]] = [
    {"segment_id": "SEG-BLR", "where": "Bengaluru", "what": "developer", "category": "it-jobs", "results_per_page": 20, "max_pages": 5},
    {"segment_id": "SEG-HYD", "where": "Hyderabad", "what": "developer", "category": "it-jobs", "results_per_page": 20, "max_pages": 5},
    {"segment_id": "SEG-PUN", "where": "Pune", "what": "developer", "category": "it-jobs", "results_per_page": 20, "max_pages": 5},
    {"segment_id": "SEG-MUM", "where": "Mumbai", "what": "developer", "category": "it-jobs", "results_per_page": 20, "max_pages": 5},
    {"segment_id": "SEG-DEL", "where": "Delhi", "what": "developer", "category": "it-jobs", "results_per_page": 20, "max_pages": 5},
    {"segment_id": "SEG-NOI", "where": "Noida", "what": "developer", "category": "it-jobs", "results_per_page": 20, "max_pages": 5},
    {"segment_id": "SEG-GGN", "where": "Gurgaon", "what": "developer", "category": "it-jobs", "results_per_page": 20, "max_pages": 5},
]


@dataclass(frozen=True)
class AdzunaIngestionResult:
    """Summary of an Adzuna ingestion execution."""

    run_id: int
    status: str
    pages_processed: int
    snapshots_created: int
    jobs_received: int
    jobs_inserted: int
    jobs_updated: int
    jobs_skipped: int
    skills_extracted: int
    scope_checkpoint: dict[str, Any] | None = None
    error_summary: str | None = None


@dataclass(frozen=True)
class AdzunaPilotBatchResult:
    """Summary of an Adzuna segmented pilot batch execution."""

    run_id: int
    batch_id: str
    matrix_version: str
    status: str
    total_segments_planned: int
    segments_completed: int
    total_requests_made: int
    total_jobs_received: int
    total_jobs_inserted: int
    total_jobs_updated: int
    total_jobs_skipped: int
    total_skills_extracted: int
    is_complete: bool
    eligible_for_full_scope_reconciliation: bool
    checkpoint: dict[str, Any]
    resumed_from_run_id: int | None = None
    error_summary: str | None = None


def verify_account_quota_config(
    config: AdzunaConfig,
    *,
    planned_requests: int = DEFAULT_MAX_PILOT_REQUESTS,
    min_interval_seconds: float = DEFAULT_MIN_REQUEST_INTERVAL_SECONDS,
) -> dict[str, Any]:
    """Verify configured account quota and rate limit safety without exposing credentials."""
    app_id_valid = bool(config.app_id and str(config.app_id).strip())
    app_key_valid = bool(config.app_key and str(config.app_key).strip())

    if not app_id_valid or not app_key_valid:
        raise AdzunaConfigError("Missing or empty Adzuna credentials in configuration.")

    daily_limit = 250
    minute_limit = 25
    weekly_limit = 1000
    monthly_limit = 2500

    daily_consumption_pct = round((planned_requests / daily_limit) * 100.0, 1)
    max_rpm_at_interval = round(60.0 / max(0.1, min_interval_seconds), 1)

    verification = {
        "credentials_configured": True,
        "app_id_length": len(config.app_id),
        "app_key_length": len(config.app_key),
        "country": config.country,
        "base_url": config.base_url,
        "daily_limit_calls": daily_limit,
        "minute_limit_calls": minute_limit,
        "weekly_limit_calls": weekly_limit,
        "monthly_limit_calls": monthly_limit,
        "planned_requests": planned_requests,
        "daily_quota_consumption_pct": daily_consumption_pct,
        "within_daily_quota": planned_requests <= daily_limit,
        "min_request_interval_seconds": min_interval_seconds,
        "max_requests_per_minute_at_interval": max_rpm_at_interval,
        "within_minute_rate_limit": max_rpm_at_interval < minute_limit,
        "quota_verification_status": (
            "verified_within_limits"
            if (planned_requests <= daily_limit and max_rpm_at_interval < minute_limit)
            else "quota_exceeded"
        ),
    }

    # Verify no secrets leaked in output
    for key, val in verification.items():
        val_str = str(val)
        if config.app_id in val_str or config.app_key in val_str:
            raise RuntimeError("CRITICAL: Credential leakage detected in quota verification output.")

    return verification


class SegmentRequestLimiter:
    """Enforces minimum interval between consecutive requests and hard cap on total requests."""

    def __init__(
        self,
        *,
        min_interval_seconds: float = DEFAULT_MIN_REQUEST_INTERVAL_SECONDS,
        max_total_requests: int = DEFAULT_MAX_PILOT_REQUESTS,
        initial_requests_made: int = 0,
        sleep_fn: Callable[[float], None] | None = None,
        time_fn: Callable[[], float] | None = None,
    ) -> None:
        self.min_interval = max(0.0, float(min_interval_seconds))
        self.max_total_requests = max(1, int(max_total_requests))
        self.sleep_fn = sleep_fn or time.sleep
        self.time_fn = time_fn or time.monotonic
        self.last_request_time: float | None = None
        self.total_requests_made: int = max(0, int(initial_requests_made))
        self.intervals_slept: list[float] = []

    def can_request(self) -> bool:
        """Return True if under max_total_requests limit."""
        return self.total_requests_made < self.max_total_requests

    def record_request_start(self) -> float:
        """Enforces minimum interval since previous request, across segments.

        Returns the number of seconds slept (if any).
        Raises AdzunaBudgetExhaustedError if the request limit ceiling is reached.
        """
        if not self.can_request():
            raise AdzunaBudgetExhaustedError(
                f"Maximum request budget of {self.max_total_requests} reached "
                f"({self.total_requests_made} requests already made)."
            )
        slept = 0.0
        now = self.time_fn()
        if self.last_request_time is not None:
            elapsed = now - self.last_request_time
            if elapsed < self.min_interval:
                slept = self.min_interval - elapsed
                self.sleep_fn(slept)
                self.intervals_slept.append(slept)
                now = self.time_fn()

        self.last_request_time = now
        self.total_requests_made += 1
        return slept


def build_run_scope_checkpoint(
    *,
    what: str | None,
    where: str | None,
    max_pages: int | None,
    max_results: int | None,
    results_per_page: int | None,
    pages_processed: int,
    records_received: int,
) -> dict[str, Any]:
    """Build a JSON-serialisable scope descriptor for an Adzuna ingestion run.

    Three separate flags are encoded:

    ``is_bounded``
        True when the caller imposed any hard limit on how many pages or
        results were fetched.  A bounded run intentionally stopped early
        and therefore never represents a complete India-wide sweep.

    ``is_filtered``
        True when keyword or geographic filters were applied, narrowing
        the result set to a subset of all live Adzuna India postings.

    ``eligible_for_full_scope_reconciliation``
        True only when the run was neither bounded nor filtered — i.e. it
        was a genuine attempt to retrieve *all* active Adzuna India jobs.
        Even then, the reconciliation guard must separately verify that the
        run ``status == 'succeeded'`` and ``is_complete == True`` before
        inferring that absent jobs have become inactive.

        **No Adzuna run with any ``what``, ``where``, ``max_pages``, or
        ``max_results`` restriction should ever qualify.**
    """
    is_bounded = max_pages is not None or max_results is not None
    is_filtered = what is not None or where is not None

    return {
        "what": what,
        "where": where,
        "max_pages": max_pages,
        "max_results": max_results,
        "results_per_page": results_per_page,
        "pages_processed": pages_processed,
        "records_received": records_received,
        "is_bounded": is_bounded,
        "is_filtered": is_filtered,
        "eligible_for_full_scope_reconciliation": not is_bounded and not is_filtered,
    }


def _relative_storage_reference(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _parse_posted_at(date_str: str | None) -> datetime | None:
    if not date_str:
        return None
    cleaned = date_str.strip()
    try:
        if cleaned.endswith("Z"):
            cleaned = cleaned[:-1] + "+00:00"
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except (ValueError, TypeError):
        return None


def _compute_salary_status(salary_min: float | None, salary_max: float | None) -> str:
    if salary_min is None and salary_max is None:
        return "not_disclosed"
    if salary_min is not None and salary_max is not None:
        if salary_min == 0 and salary_max == 0:
            return "zero_unknown"
        if salary_min < 0 or salary_max < 0 or salary_min > salary_max:
            return "invalid_range"
        return "valid"
    return "incomplete_range"


def _format_salary_text(job: AdzunaJob) -> str | None:
    if job.salary_min is not None and job.salary_max is not None:
        return f"{job.salary_min:.0f} - {job.salary_max:.0f} INR"
    if job.salary_min is not None:
        return f"From {job.salary_min:.0f} INR"
    if job.salary_max is not None:
        return f"Up to {job.salary_max:.0f} INR"
    return "Not disclosed"


def compute_job_content_fingerprint(job: AdzunaJob) -> str:
    """Stable fingerprint of normalized job content to detect changes."""
    payload = {
        "title": (job.title or "").strip(),
        "company": (job.company_name or "").strip(),
        "location": (job.location_display_name or "").strip(),
        "description": (job.description or "").strip(),
        "salary_min": job.salary_min,
        "salary_max": job.salary_max,
        "contract_time": job.contract_time or "",
        "contract_type": job.contract_type or "",
        "category_tag": job.category_tag or "",
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class AdzunaIngestionService:
    """Manages idempotent live ingestion of Adzuna job postings."""

    def __init__(
        self,
        session: Session,
        client: AdzunaClient,
        *,
        snapshot_dir: Path | str | None = None,
        aliases_path: Path | str | None = None,
        categories_path: Path | str | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.session = session
        self.client = client
        self.snapshot_dir = Path(snapshot_dir) if snapshot_dir else DEFAULT_SNAPSHOT_DIR
        self.aliases_path = Path(aliases_path) if aliases_path else DEFAULT_ALIASES
        self.categories_path = Path(categories_path) if categories_path else DEFAULT_CATEGORIES
        self.logger = logger or logging.getLogger("job_market.adzuna_ingestion")

        # Load skill extraction dictionaries once
        if not self.aliases_path.is_file() or not self.categories_path.is_file():
            raise FileNotFoundError("Skill reference dictionaries not found for Adzuna ingestion")

        raw_aliases = json.loads(self.aliases_path.read_text(encoding="utf-8"))
        self.alias_lookup = load_alias_map(self.aliases_path)
        self.category_lookup = load_category_map(self.categories_path)
        self.patterns = build_description_patterns(raw_aliases)

    def _sanitize(self, text: str) -> str:
        return redact_text(text, [self.client.config.app_id, self.client.config.app_key])

    def get_or_create_source(self) -> Source:
        """Fetch or register the Adzuna India Source entity."""
        source = self.session.scalar(select(Source).where(Source.code == ADZUNA_SOURCE_CODE))
        if source is None:
            source = Source(
                code=ADZUNA_SOURCE_CODE,
                name=ADZUNA_SOURCE_NAME,
                source_type="api",
                base_url=ADZUNA_BASE_URL,
                is_active=True,
            )
            self.session.add(source)
            self.session.flush()
        return source

    def save_raw_snapshot_file(self, content_sha256: str, raw_json: str) -> Path:
        """Store raw API response as a hash-addressed JSON file on disk."""
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        file_path = self.snapshot_dir / f"{content_sha256}.json"
        if not file_path.exists():
            file_path.write_text(raw_json, encoding="utf-8")
        return file_path

    def run_ingestion(
        self,
        *,
        start_page: int = 1,
        max_pages: int | None = None,
        max_results: int | None = None,
        results_per_page: int | None = None,
        what: str | None = None,
        where: str | None = None,
        observed_at: datetime | None = None,
    ) -> AdzunaIngestionResult:
        """Execute transactional live ingestion across paginated API responses."""
        run_time = observed_at or datetime.now(UTC)
        source = self.get_or_create_source()

        # Initialize IngestionRun
        run = IngestionRun(
            source=source,
            run_type="incremental_fetch",
            status="running",
            is_complete=False,
            started_at=run_time,
            observed_at=run_time,
            transform_version=ADZUNA_TRANSFORM_VERSION,
        )
        self.session.add(run)
        self.session.commit()

        pages_processed = 0
        snapshots_created = 0
        jobs_received = 0
        jobs_inserted = 0
        jobs_updated = 0
        jobs_skipped = 0
        skills_extracted = 0
        error_summary: str | None = None

        # Cache existing skills in memory to minimize DB queries
        skills_by_name = {
            skill.normalized_name: skill
            for skill in self.session.scalars(select(Skill)).all()
        }

        scope_checkpoint: dict[str, Any] | None = None

        try:
            page_iterator = self.client.paginate(
                start_page=start_page,
                max_pages=max_pages,
                max_results=max_results,
                results_per_page=results_per_page,
                what=what,
                where=where,
            )

            for page in page_iterator:
                pages_processed += 1
                try:
                    # Execute per-page transactional unit
                    (
                        page_inserted,
                        page_updated,
                        page_skipped,
                        page_skills,
                    ) = self._process_page(
                        page=page,
                        run=run,
                        source=source,
                        run_time=run_time,
                        sequence=pages_processed,
                        skills_by_name=skills_by_name,
                    )
                    self.session.commit()

                    snapshots_created += 1
                    jobs_received += len(page.results)
                    jobs_inserted += page_inserted
                    jobs_updated += page_updated
                    jobs_skipped += page_skipped
                    skills_extracted += page_skills

                except Exception as page_err:
                    self.session.rollback()
                    clean_err = self._sanitize(str(page_err))
                    self.logger.error("Error processing Adzuna page %d: %s", page.page, clean_err)
                    raise

            # Successful completion.
            #
            # is_complete reflects whether the requested scope was fully fetched
            # without error — it does NOT imply India-wide coverage.
            # A bounded or filtered run sets is_complete=True only in the sense
            # that the *requested* scope finished cleanly.  The scope checkpoint
            # documents the actual boundaries so callers can distinguish it from
            # a full unbounded sweep.
            scope_checkpoint = build_run_scope_checkpoint(
                what=what,
                where=where,
                max_pages=max_pages,
                max_results=max_results,
                results_per_page=results_per_page,
                pages_processed=pages_processed,
                records_received=jobs_received,
            )
            run.status = "succeeded"
            run.is_complete = True  # the requested scope completed without exception
            run.completed_at = datetime.now(UTC)
            run.records_received = jobs_received
            run.records_inserted = jobs_inserted
            run.records_updated = jobs_updated
            run.records_skipped = jobs_skipped
            run.cursor_or_checkpoint = json.dumps(scope_checkpoint, separators=(",", ":"))
            self.session.commit()

        except Exception as err:
            self.session.rollback()
            error_summary = self._sanitize(str(err))
            run.status = "partial" if (snapshots_created > 0 or jobs_received > 0) else "failed"
            run.is_complete = False
            run.completed_at = datetime.now(UTC)
            run.records_received = jobs_received
            run.records_inserted = jobs_inserted
            run.records_updated = jobs_updated
            run.records_skipped = jobs_skipped
            run.error_summary = error_summary[:500]
            # Persist scope even on failure so the interrupted boundary is auditable.
            scope_checkpoint = build_run_scope_checkpoint(
                what=what,
                where=where,
                max_pages=max_pages,
                max_results=max_results,
                results_per_page=results_per_page,
                pages_processed=pages_processed,
                records_received=jobs_received,
            )
            run.cursor_or_checkpoint = json.dumps(scope_checkpoint, separators=(",", ":"))
            self.session.commit()

        return AdzunaIngestionResult(
            run_id=run.id,
            status=run.status,
            pages_processed=pages_processed,
            snapshots_created=snapshots_created,
            jobs_received=jobs_received,
            jobs_inserted=jobs_inserted,
            jobs_updated=jobs_updated,
            jobs_skipped=jobs_skipped,
            skills_extracted=skills_extracted,
            scope_checkpoint=scope_checkpoint,
            error_summary=error_summary,
        )

    def run_pilot_batch(
        self,
        *,
        segments: list[dict[str, Any]] | None = None,
        matrix_version: str = PILOT_M4_MATRIX_VERSION,
        batch_id: str | None = None,
        resume_run_id: int | None = None,
        max_total_requests: int = DEFAULT_MAX_PILOT_REQUESTS,
        min_request_interval_seconds: float = DEFAULT_MIN_REQUEST_INTERVAL_SECONDS,
        sleep_fn: Callable[[float], None] | None = None,
        time_fn: Callable[[], float] | None = None,
        observed_at: datetime | None = None,
    ) -> AdzunaPilotBatchResult:
        """Execute a controlled multi-segment pilot batch across Indian tech hubs.

        Safety and compliance constraints:
        - Strict ceiling on total API requests across all segments (default 35)
        - Enforces minimum 2.5s interval between consecutive requests, including cross-segment
        - Resumes only failed or pending segments without re-running successful ones
        - Rejects resume attempts with mismatched matrix versions or incompatible parameters
        - Cross-segment SCD Type 2 deduplication via content fingerprints
        - Inactive-job reconciliation permanently disabled (eligible_for_full_scope_reconciliation: False)
        """
        run_time = observed_at or datetime.now(UTC)
        source = self.get_or_create_source()
        pilot_segments = [dict(s) for s in (segments or DEFAULT_PILOT_SEGMENTS)]

        # Validate resume state or initialize fresh run
        prev_checkpoint: dict[str, Any] = {}
        if resume_run_id is not None:
            run = self.session.get(IngestionRun, resume_run_id)
            if run is None:
                raise ValueError(f"Run ID {resume_run_id} not found to resume.")
            if not run.cursor_or_checkpoint:
                raise ValueError(f"Run ID {resume_run_id} has no checkpoint data to resume.")
            try:
                prev_checkpoint = json.loads(run.cursor_or_checkpoint)
            except Exception as json_err:
                raise ValueError(f"Corrupt checkpoint JSON on run {resume_run_id}: {json_err}") from json_err

            prev_matrix = prev_checkpoint.get("matrix_version")
            if prev_matrix != matrix_version:
                raise ValueError(
                    f"Matrix version mismatch: cannot resume run {resume_run_id} recorded with "
                    f"matrix_version={prev_matrix!r} using matrix_version={matrix_version!r}."
                )

            prev_batch_id = prev_checkpoint.get("batch_id")
            if batch_id is not None and batch_id != prev_batch_id:
                raise ValueError(
                    f"Batch identity mismatch: cannot resume run {resume_run_id} with batch_id={batch_id!r} "
                    f"(recorded as {prev_batch_id!r})."
                )
            batch_id = prev_batch_id

            # Validate parameter compatibility for existing segments
            prev_seg_map = {s["segment_id"]: s for s in prev_checkpoint.get("segments", [])}
            for seg in pilot_segments:
                sid = seg["segment_id"]
                if sid in prev_seg_map:
                    prev_p = prev_seg_map[sid].get("params", {})
                    for param_key in ("where", "what", "category", "results_per_page", "max_pages"):
                        if seg.get(param_key) != prev_p.get(param_key):
                            raise ValueError(
                                f"Incompatible query parameters on resume for segment {sid!r}: "
                                f"parameter {param_key!r} changed from {prev_p.get(param_key)!r} to {seg.get(param_key)!r}."
                            )

            run.status = "running"
            run.completed_at = None
            self.session.commit()
        else:
            batch_id = batch_id or f"adzuna_pilot_{matrix_version}_{int(run_time.timestamp())}"
            run = IngestionRun(
                source=source,
                run_type="incremental_fetch",
                status="running",
                is_complete=False,
                started_at=run_time,
                observed_at=run_time,
                transform_version=ADZUNA_TRANSFORM_VERSION,
            )
            self.session.add(run)
            self.session.commit()

        # Cache existing skills in memory to minimize DB lookups
        skills_by_name = {
            skill.normalized_name: skill
            for skill in self.session.scalars(select(Skill)).all()
        }

        # Fix 1: Restore cumulative requests made in previous runs of this batch
        prev_requests = int(prev_checkpoint.get("total_requests_made", 0)) if prev_checkpoint else 0

        limiter = SegmentRequestLimiter(
            min_interval_seconds=min_request_interval_seconds,
            max_total_requests=max_total_requests,
            initial_requests_made=prev_requests,
            sleep_fn=sleep_fn,
            time_fn=time_fn,
        )

        # Fix 2: Hook limiter into client's HTTP execution to meter every request attempt and retry
        original_hook = getattr(self.client, "request_hook", None)
        self.client.request_hook = limiter.record_request_start
        original_client_sleep = getattr(self.client, "_sleep", None)
        if sleep_fn is not None and hasattr(self.client, "_sleep"):
            self.client._sleep = sleep_fn

        segment_records: list[dict[str, Any]] = []
        total_jobs_received = 0
        total_jobs_inserted = 0
        total_jobs_updated = 0
        total_jobs_skipped = 0
        total_skills_extracted = 0
        total_pages_processed = 0
        segments_completed = 0
        batch_error_summary: str | None = None

        prev_seg_map = {s["segment_id"]: s for s in prev_checkpoint.get("segments", [])} if prev_checkpoint else {}

        try:
            for seg in pilot_segments:
                sid = seg["segment_id"]

                # If segment already succeeded in a prior run, preserve its exact counts and skip re-fetch
                if sid in prev_seg_map and prev_seg_map[sid].get("status") == "succeeded":
                    prev_record = dict(prev_seg_map[sid])
                    segment_records.append(prev_record)
                    total_jobs_received += prev_record.get("records_received", 0)
                    total_jobs_inserted += prev_record.get("records_inserted", 0)
                    total_jobs_updated += prev_record.get("records_updated", 0)
                    total_jobs_skipped += prev_record.get("records_skipped", 0)
                    total_skills_extracted += prev_record.get("skills_extracted", 0)
                    total_pages_processed += prev_record.get("pages_processed", 0)
                    segments_completed += 1
                    continue

                # Check if total request budget has been exhausted
                if not limiter.can_request():
                    segment_records.append({
                        "segment_id": sid,
                        "status": "stopped_by_request_limit",
                        "params": dict(seg),
                        "pages_processed": 0,
                        "records_received": 0,
                        "records_inserted": 0,
                        "records_updated": 0,
                        "records_skipped": 0,
                        "skills_extracted": 0,
                        "error_summary": "Skipped: maximum total request budget reached.",
                    })
                    continue

                # Fix 4: Determine previous committed pages for this segment if resuming
                prev_seg_record = prev_seg_map.get(sid, {})
                prev_pages = int(prev_seg_record.get("pages_processed", 0))
                planned_max_pages = seg.get("max_pages", 5)

                if prev_pages >= planned_max_pages:
                    prev_record = dict(prev_seg_record)
                    prev_record["status"] = "succeeded"
                    segment_records.append(prev_record)
                    total_jobs_received += prev_record.get("records_received", 0)
                    total_jobs_inserted += prev_record.get("records_inserted", 0)
                    total_jobs_updated += prev_record.get("records_updated", 0)
                    total_jobs_skipped += prev_record.get("records_skipped", 0)
                    total_skills_extracted += prev_record.get("skills_extracted", 0)
                    total_pages_processed += prev_pages
                    segments_completed += 1
                    continue

                start_page = prev_pages + 1
                remaining_pages = planned_max_pages - prev_pages

                seg_pages = prev_pages
                seg_received = prev_seg_record.get("records_received", 0)
                seg_inserted = prev_seg_record.get("records_inserted", 0)
                seg_updated = prev_seg_record.get("records_updated", 0)
                seg_skipped = prev_seg_record.get("records_skipped", 0)
                seg_skills = prev_seg_record.get("skills_extracted", 0)
                seg_status = "succeeded"
                seg_err: str | None = None

                # Account for previously committed records of this segment in cumulative totals
                total_jobs_received += seg_received
                total_jobs_inserted += seg_inserted
                total_jobs_updated += seg_updated
                total_jobs_skipped += seg_skipped
                total_skills_extracted += seg_skills
                total_pages_processed += prev_pages

                paginate_kwargs = {
                    "start_page": start_page,
                    "max_pages": remaining_pages,
                    "results_per_page": seg.get("results_per_page", 20),
                    "what": seg.get("what"),
                    "where": seg.get("where"),
                }
                if seg.get("category"):
                    paginate_kwargs["category"] = seg["category"]

                try:
                    page_iterator = self.client.paginate(**paginate_kwargs)

                    while seg_pages < planned_max_pages:
                        if not limiter.can_request():
                            seg_status = "stopped_by_request_limit"
                            break

                        reqs_before = limiter.total_requests_made
                        try:
                            page = next(page_iterator)
                        except StopIteration:
                            break
                        except AdzunaBudgetExhaustedError:
                            seg_status = "stopped_by_request_limit"
                            break
                        except Exception as fetch_err:
                            seg_err = self._sanitize(str(fetch_err))
                            seg_status = "failed"
                            batch_error_summary = seg_err
                            self.logger.error("Segment %s page fetch failed: %s", sid, seg_err)
                            break

                        # Fallback: if client did not call request_hook internally, record request now
                        if limiter.total_requests_made == reqs_before:
                            try:
                                limiter.record_request_start()
                            except AdzunaBudgetExhaustedError:
                                seg_status = "stopped_by_request_limit"
                                break

                        try:
                            p_ins, p_upd, p_skp, p_skl = self._process_page(
                                page=page,
                                run=run,
                                source=source,
                                run_time=run_time,
                                sequence=total_pages_processed + 1,
                                skills_by_name=skills_by_name,
                            )
                        except Exception as page_err:
                            self.session.rollback()
                            seg_err = self._sanitize(str(page_err))
                            seg_status = "failed"
                            batch_error_summary = seg_err
                            self.logger.error("Segment %s page processing failed: %s", sid, seg_err)
                            break

                        # Fix 3: Update segment and cumulative counters atomically per page
                        seg_pages += 1
                        seg_received += len(page.results)
                        seg_inserted += p_ins
                        seg_updated += p_upd
                        seg_skipped += p_skp
                        seg_skills += p_skl

                        total_jobs_received += len(page.results)
                        total_jobs_inserted += p_ins
                        total_jobs_updated += p_upd
                        total_jobs_skipped += p_skp
                        total_skills_extracted += p_skl
                        total_pages_processed += 1

                        run.records_received = total_jobs_received
                        run.records_inserted = total_jobs_inserted
                        run.records_updated = total_jobs_updated
                        run.records_skipped = total_jobs_skipped

                        current_seg_record = {
                            "segment_id": sid,
                            "status": "running" if seg_pages < planned_max_pages else "succeeded",
                            "params": dict(seg),
                            "pages_processed": seg_pages,
                            "records_received": seg_received,
                            "records_inserted": seg_inserted,
                            "records_updated": seg_updated,
                            "records_skipped": seg_skipped,
                            "skills_extracted": seg_skills,
                            "error_summary": None,
                        }

                        page_checkpoint = {
                            "batch_id": batch_id,
                            "matrix_version": matrix_version,
                            "batch_status": "running",
                            "started_at": run.started_at.isoformat(),
                            "total_segments_planned": len(pilot_segments),
                            "segments_completed": segments_completed,
                            "all_segments_succeeded": False,
                            "eligible_for_full_scope_reconciliation": False,
                            "reconciliation_lock_reason": "Pilot segmented collection; inactive-job reconciliation permanently disabled.",
                            "max_total_requests_configured": max_total_requests,
                            "min_request_interval_seconds": min_request_interval_seconds,
                            "total_requests_made": limiter.total_requests_made,
                            "records_received": total_jobs_received,
                            "records_inserted": total_jobs_inserted,
                            "records_updated": total_jobs_updated,
                            "records_skipped": total_jobs_skipped,
                            "skills_extracted": total_skills_extracted,
                            "resumed_from_run_id": resume_run_id,
                            "segments": segment_records + [current_seg_record],
                        }
                        run.cursor_or_checkpoint = json.dumps(page_checkpoint, separators=(",", ":"))
                        self.session.commit()

                    if seg_status == "succeeded":
                        segments_completed += 1

                except Exception as seg_exc:
                    seg_status = "failed"
                    seg_err = self._sanitize(str(seg_exc))
                    batch_error_summary = seg_err
                    self.logger.error("Segment %s unexpected error: %s", sid, seg_err)

                seg_record = {
                    "segment_id": sid,
                    "status": seg_status,
                    "params": dict(seg),
                    "pages_processed": seg_pages,
                    "records_received": seg_received,
                    "records_inserted": seg_inserted,
                    "records_updated": seg_updated,
                    "records_skipped": seg_skipped,
                    "skills_extracted": seg_skills,
                    "error_summary": seg_err,
                }
                segment_records.append(seg_record)

                checkpoint = {
                    "batch_id": batch_id,
                    "matrix_version": matrix_version,
                    "batch_status": "running",
                    "started_at": run.started_at.isoformat(),
                    "total_segments_planned": len(pilot_segments),
                    "segments_completed": segments_completed,
                    "all_segments_succeeded": False,
                    "eligible_for_full_scope_reconciliation": False,
                    "reconciliation_lock_reason": "Pilot segmented collection; inactive-job reconciliation permanently disabled.",
                    "max_total_requests_configured": max_total_requests,
                    "min_request_interval_seconds": min_request_interval_seconds,
                    "total_requests_made": limiter.total_requests_made,
                    "records_received": total_jobs_received,
                    "records_inserted": total_jobs_inserted,
                    "records_updated": total_jobs_updated,
                    "records_skipped": total_jobs_skipped,
                    "skills_extracted": total_skills_extracted,
                    "resumed_from_run_id": resume_run_id,
                    "segments": segment_records,
                }
                run.cursor_or_checkpoint = json.dumps(checkpoint, separators=(",", ":"))
                run.records_received = total_jobs_received
                run.records_inserted = total_jobs_inserted
                run.records_updated = total_jobs_updated
                run.records_skipped = total_jobs_skipped
                self.session.commit()

                if seg_status in {"failed", "stopped_by_request_limit"}:
                    # Mark any remaining unprocessed segments in checkpoint
                    processed_sids = {s["segment_id"] for s in segment_records}
                    for rem_seg in pilot_segments:
                        rem_sid = rem_seg["segment_id"]
                        if rem_sid not in processed_sids:
                            rem_status = "stopped_by_request_limit" if seg_status == "stopped_by_request_limit" else "pending"
                            segment_records.append({
                                "segment_id": rem_sid,
                                "status": rem_status,
                                "params": dict(rem_seg),
                                "pages_processed": 0,
                                "records_received": 0,
                                "records_inserted": 0,
                                "records_updated": 0,
                                "records_skipped": 0,
                                "skills_extracted": 0,
                                "error_summary": f"Not executed: batch halted due to segment {sid} ({seg_status}).",
                            })
                    break

            all_succeeded = (segments_completed == len(pilot_segments)) and all(
                s.get("status") == "succeeded" for s in segment_records
            )

            if all_succeeded:
                run.status = "succeeded"
                run.is_complete = True
            else:
                run.status = "partial" if (total_pages_processed > 0 or total_jobs_received > 0) else "failed"
                run.is_complete = False

            completed_time = datetime.now(UTC)
            run.completed_at = completed_time
            run.records_received = total_jobs_received
            run.records_inserted = total_jobs_inserted
            run.records_updated = total_jobs_updated
            run.records_skipped = total_jobs_skipped
            if batch_error_summary:
                run.error_summary = batch_error_summary[:500]

            checkpoint = {
                "batch_id": batch_id,
                "matrix_version": matrix_version,
                "batch_status": run.status,
                "started_at": run.started_at.isoformat(),
                "completed_at": completed_time.isoformat(),
                "total_segments_planned": len(pilot_segments),
                "segments_completed": segments_completed,
                "all_segments_succeeded": all_succeeded,
                "eligible_for_full_scope_reconciliation": False,
                "reconciliation_lock_reason": "Pilot segmented collection; inactive-job reconciliation permanently disabled.",
                "max_total_requests_configured": max_total_requests,
                "min_request_interval_seconds": min_request_interval_seconds,
                "total_requests_made": limiter.total_requests_made,
                "records_received": total_jobs_received,
                "records_inserted": total_jobs_inserted,
                "records_updated": total_jobs_updated,
                "records_skipped": total_jobs_skipped,
                "skills_extracted": total_skills_extracted,
                "resumed_from_run_id": resume_run_id,
                "segments": segment_records,
            }

            run.cursor_or_checkpoint = json.dumps(checkpoint, separators=(",", ":"))
            self.session.commit()

        finally:
            if hasattr(self.client, "request_hook"):
                self.client.request_hook = original_hook
            if hasattr(self.client, "_sleep") and original_client_sleep is not None:
                self.client._sleep = original_client_sleep

        return AdzunaPilotBatchResult(
            run_id=run.id,
            batch_id=batch_id,
            matrix_version=matrix_version,
            status=run.status,
            total_segments_planned=len(pilot_segments),
            segments_completed=segments_completed,
            total_requests_made=limiter.total_requests_made,
            total_jobs_received=total_jobs_received,
            total_jobs_inserted=total_jobs_inserted,
            total_jobs_updated=total_jobs_updated,
            total_jobs_skipped=total_jobs_skipped,
            total_skills_extracted=total_skills_extracted,
            is_complete=run.is_complete,
            eligible_for_full_scope_reconciliation=False,
            checkpoint=checkpoint,
            resumed_from_run_id=resume_run_id,
            error_summary=batch_error_summary,
        )

    def _process_page(
        self,
        *,
        page: AdzunaPage,
        run: IngestionRun,
        source: Source,
        run_time: datetime,
        sequence: int,
        skills_by_name: dict[str, Skill],
    ) -> tuple[int, int, int, int]:
        """Process a single AdzunaPage and its job postings within a transaction."""
        # 1. Write hash-addressed snapshot file
        file_path = self.save_raw_snapshot_file(page.content_sha256, page.raw_json)
        storage_ref = _relative_storage_reference(file_path)

        # 2. Register RawSnapshot entity
        snapshot = RawSnapshot(
            ingestion_run=run,
            snapshot_sequence=sequence,
            snapshot_kind="api_page",
            source_record_ref=f"adzuna:page:{page.page}",
            collected_at=run_time,
            content_sha256=page.content_sha256,
            storage_mode="file_ref",
            storage_ref=storage_ref,
            payload_text=page.raw_json,
            mime_type="application/json",
            record_count=len(page.results),
            http_status=page.http_status,
        )
        self.session.add(snapshot)
        self.session.flush()

        inserted_count = 0
        updated_count = 0
        skipped_count = 0
        skills_count = 0

        # Cache existing jobs by source_job_id within this source
        job_ids = [job.id for job in page.results]
        existing_jobs = {
            job.source_job_id: job
            for job in self.session.scalars(
                select(Job).where(
                    Job.source_id == source.id,
                    Job.source_job_id.in_(job_ids),
                )
            ).all()
        }

        # Keep track of jobs seen on this page to handle repeated IDs in the same page
        seen_on_page: set[str] = set()

        for job_record in page.results:
            if job_record.id in seen_on_page:
                # Repeated ID on the same page; skip re-insertion
                skipped_count += 1
                continue
            seen_on_page.add(job_record.id)

            fingerprint = compute_job_content_fingerprint(job_record)
            salary_status = _compute_salary_status(job_record.salary_min, job_record.salary_max)

            existing_job = existing_jobs.get(job_record.id)

            if existing_job is None:
                # -----------------------------------------------------------
                # New Job
                # -----------------------------------------------------------
                identity_key = f"adzuna_india:provider_id:{job_record.id}"
                job = Job(
                    source=source,
                    source_job_id=job_record.id,
                    source_record_ref=f"adzuna:snapshot:{snapshot.id}:job:{job_record.id}",
                    identity_key=identity_key,
                    identity_status="provider_id",
                    first_seen_at=run_time,
                    last_seen_at=run_time,
                    last_seen_run=run,
                    is_active=True,
                )
                self.session.add(job)
                self.session.flush()
                existing_jobs[job_record.id] = job

                version = JobVersion(
                    job=job,
                    raw_snapshot=snapshot,
                    version_number=1,
                    is_current=True,
                    origin_record_key=f"adzuna:snapshot:{snapshot.id}:job:{job_record.id}",
                    content_fingerprint=fingerprint,
                    mapping_status="exact",
                    title=job_record.title,
                    company_name=job_record.company_name,
                    location=job_record.location_display_name,
                    job_description=job_record.description,
                    source_tags_text=job_record.category_tag,
                    salary_text=_format_salary_text(job_record),
                    salary_status=salary_status,
                    salary_currency="INR",
                    salary_period="annual" if salary_status == "valid" else "unknown",
                    salary_min_source=job_record.salary_min,
                    salary_max_source=job_record.salary_max,
                    salary_min_annual_inr=job_record.salary_min if salary_status == "valid" else None,
                    salary_max_annual_inr=job_record.salary_max if salary_status == "valid" else None,
                    employment_type=job_record.contract_time,
                    posted_at=_parse_posted_at(job_record.created),
                    posted_text=job_record.created,
                    observed_at=run_time,
                    ingested_at=run_time,
                    transform_version=ADZUNA_TRANSFORM_VERSION,
                )
                self.session.add(version)
                self.session.flush()

                # Extract and attach skills for this new version
                extracted = self._extract_and_attach_skills(version, job_record, skills_by_name)
                skills_count += extracted
                inserted_count += 1

            else:
                # -----------------------------------------------------------
                # Existing Job: check content fingerprint
                # -----------------------------------------------------------
                existing_job.last_seen_at = run_time
                existing_job.last_seen_run = run

                # Find the current version
                current_version = self.session.scalar(
                    select(JobVersion).where(
                        JobVersion.job_id == existing_job.id,
                        JobVersion.is_current.is_(True),
                    )
                )

                if current_version is not None and current_version.content_fingerprint == fingerprint:
                    # Unchanged job: update last_seen, do not create duplicate version
                    skipped_count += 1
                else:
                    # Content changed: transition current version and create version N+1
                    new_version_num = (current_version.version_number + 1) if current_version else 1
                    if current_version is not None:
                        current_version.is_current = False
                        self.session.flush()

                    new_version = JobVersion(
                        job=existing_job,
                        raw_snapshot=snapshot,
                        version_number=new_version_num,
                        is_current=True,
                        origin_record_key=f"adzuna:snapshot:{snapshot.id}:job:{job_record.id}:v{new_version_num}",
                        content_fingerprint=fingerprint,
                        mapping_status="exact",
                        title=job_record.title,
                        company_name=job_record.company_name,
                        location=job_record.location_display_name,
                        job_description=job_record.description,
                        source_tags_text=job_record.category_tag,
                        salary_text=_format_salary_text(job_record),
                        salary_status=salary_status,
                        salary_currency="INR",
                        salary_period="annual" if salary_status == "valid" else "unknown",
                        salary_min_source=job_record.salary_min,
                        salary_max_source=job_record.salary_max,
                        salary_min_annual_inr=job_record.salary_min if salary_status == "valid" else None,
                        salary_max_annual_inr=job_record.salary_max if salary_status == "valid" else None,
                        employment_type=job_record.contract_time,
                        posted_at=_parse_posted_at(job_record.created),
                        posted_text=job_record.created,
                        observed_at=run_time,
                        ingested_at=run_time,
                        transform_version=ADZUNA_TRANSFORM_VERSION,
                    )
                    self.session.add(new_version)
                    self.session.flush()

                    extracted = self._extract_and_attach_skills(new_version, job_record, skills_by_name)
                    skills_count += extracted
                    updated_count += 1

        return inserted_count, updated_count, skipped_count, skills_count

    def _extract_and_attach_skills(
        self,
        version: JobVersion,
        job_record: AdzunaJob,
        skills_by_name: dict[str, Skill],
    ) -> int:
        """Run deterministic skill extraction and attach JobSkill requirements to version."""
        text_for_desc = f"{job_record.title}. {job_record.description}" if job_record.title else job_record.description
        df_for_extraction = pd.DataFrame([{
            "jobId": str(version.id),
            "tagsAndSkills_clean": job_record.category_tag or "",
            "jobDescription_clean": text_for_desc,
        }])

        skills_df = extract_job_skills(
            df_for_extraction,
            self.alias_lookup,
            self.category_lookup,
            self.patterns,
        )

        extracted_count = 0
        for row in skills_df.itertuples(index=False):
            canonical_name = str(row.skill_normalized)
            norm_key = canonical_name.casefold()

            # Ensure Skill entity exists in database
            if norm_key not in skills_by_name:
                skill_entity = Skill(
                    name=canonical_name,
                    normalized_name=norm_key,
                    category=str(row.skill_category),
                )
                self.session.add(skill_entity)
                self.session.flush()
                skills_by_name[norm_key] = skill_entity
            else:
                skill_entity = skills_by_name[norm_key]

            source_name = str(row.skill_source)
            evidence_sources = ["tagsAndSkills", "jobDescription"] if source_name == "both" else [source_name]
            evidence = [{"raw": str(row.skill_raw), "source": s} for s in evidence_sources]

            job_skill = JobSkill(
                job_version=version,
                skill=skill_entity,
                skill_raw=str(row.skill_raw),
                extraction_source=source_name,
                tags_match_count=int(source_name in {"tagsAndSkills", "both"}),
                description_match_count=int(source_name in {"jobDescription", "both"}),
                raw_match_evidence_json=json.dumps(evidence, ensure_ascii=False, sort_keys=True),
                extraction_version=ADZUNA_SKILL_EXTRACTION_VERSION,
                mapping_status="exact",
                source_record_ref=f"adzuna:version:{version.id}:skill:{norm_key}",
            )
            self.session.add(job_skill)
            extracted_count += 1

        return extracted_count


def ingest_adzuna_jobs(
    session: Session,
    client: AdzunaClient,
    *,
    start_page: int = 1,
    max_pages: int | None = None,
    max_results: int | None = None,
    results_per_page: int | None = None,
    what: str | None = None,
    where: str | None = None,
    snapshot_dir: Path | str | None = None,
    aliases_path: Path | str | None = None,
    categories_path: Path | str | None = None,
    observed_at: datetime | None = None,
) -> AdzunaIngestionResult:
    """Convenience functional interface for Adzuna live ingestion."""
    service = AdzunaIngestionService(
        session=session,
        client=client,
        snapshot_dir=snapshot_dir,
        aliases_path=aliases_path,
        categories_path=categories_path,
    )
    return service.run_ingestion(
        start_page=start_page,
        max_pages=max_pages,
        max_results=max_results,
        results_per_page=results_per_page,
        what=what,
        where=where,
        observed_at=observed_at,
    )


def ingest_adzuna_pilot_batch(
    session: Session,
    client: Any,
    *,
    segments: list[dict[str, Any]] | None = None,
    matrix_version: str = PILOT_M4_MATRIX_VERSION,
    batch_id: str | None = None,
    resume_run_id: int | None = None,
    max_total_requests: int = DEFAULT_MAX_PILOT_REQUESTS,
    min_request_interval_seconds: float = DEFAULT_MIN_REQUEST_INTERVAL_SECONDS,
    sleep_fn: Callable[[float], None] | None = None,
    time_fn: Callable[[], float] | None = None,
    snapshot_dir: Path | str | None = None,
    aliases_path: Path | str | None = None,
    categories_path: Path | str | None = None,
    observed_at: datetime | None = None,
) -> AdzunaPilotBatchResult:
    """Convenience functional interface for Adzuna segmented pilot batch live ingestion."""
    service = AdzunaIngestionService(
        session=session,
        client=client,
        snapshot_dir=snapshot_dir,
        aliases_path=aliases_path,
        categories_path=categories_path,
    )
    return service.run_pilot_batch(
        segments=segments,
        matrix_version=matrix_version,
        batch_id=batch_id,
        resume_run_id=resume_run_id,
        max_total_requests=max_total_requests,
        min_request_interval_seconds=min_request_interval_seconds,
        sleep_fn=sleep_fn,
        time_fn=time_fn,
        observed_at=observed_at,
    )
