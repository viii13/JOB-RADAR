"""Approved SQLAlchemy schema for JobRadar's database foundation."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp for model defaults."""
    return datetime.now(UTC)


class Source(Base):
    """A historical file, manual import, or future live provider."""

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    base_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    ingestion_runs: Mapped[list[IngestionRun]] = relationship(back_populates="source")
    jobs: Mapped[list[Job]] = relationship(back_populates="source")
    external_skill_benchmarks: Mapped[list[ExternalSkillBenchmark]] = relationship(back_populates="source")
    external_salary_benchmarks: Mapped[list[ExternalSalaryBenchmark]] = relationship(back_populates="source")

    __table_args__ = (
        CheckConstraint("source_type IN ('historical_file', 'api', 'manual_import')", name="ck_sources_type"),
    )


class IngestionRun(Base):
    """Auditable state for one import, reprocessing operation, or API fetch."""

    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), nullable=False)
    run_type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    is_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    transform_version: Mapped[str] = mapped_column(String(100), nullable=False)
    migration_key: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    input_manifest_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cursor_or_checkpoint: Mapped[str | None] = mapped_column(Text, nullable=True)
    records_received: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_inserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    source: Mapped[Source] = relationship(back_populates="ingestion_runs")
    raw_snapshots: Mapped[list[RawSnapshot]] = relationship(back_populates="ingestion_run")
    last_seen_jobs: Mapped[list[Job]] = relationship(
        back_populates="last_seen_run", foreign_keys="Job.last_seen_run_id"
    )

    __table_args__ = (
        CheckConstraint("run_type IN ('historical_import', 'incremental_fetch', 'reprocess')", name="ck_runs_type"),
        CheckConstraint("status IN ('running', 'succeeded', 'partial', 'failed')", name="ck_runs_status"),
        CheckConstraint("retry_count >= 0", name="ck_runs_retry_count"),
        CheckConstraint("records_received >= 0 AND records_inserted >= 0 AND records_updated >= 0 AND records_skipped >= 0 AND records_failed >= 0", name="ck_runs_record_counts"),
        Index("ix_ingestion_runs_source_started", "source_id", "started_at"),
    )


class RawSnapshot(Base):
    """A raw file or response captured before JobRadar transforms it."""

    __tablename__ = "raw_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ingestion_run_id: Mapped[int] = mapped_column(ForeignKey("ingestion_runs.id"), nullable=False)
    snapshot_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_kind: Mapped[str] = mapped_column(String(30), nullable=False)
    source_record_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    storage_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    record_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    ingestion_run: Mapped[IngestionRun] = relationship(back_populates="raw_snapshots")
    job_versions: Mapped[list[JobVersion]] = relationship(back_populates="raw_snapshot")
    external_skill_benchmarks: Mapped[list[ExternalSkillBenchmark]] = relationship(back_populates="raw_snapshot")
    external_salary_benchmarks: Mapped[list[ExternalSalaryBenchmark]] = relationship(back_populates="raw_snapshot")

    __table_args__ = (
        UniqueConstraint("ingestion_run_id", "snapshot_sequence", name="uq_snapshots_run_sequence"),
        CheckConstraint("snapshot_sequence >= 0", name="ck_snapshots_sequence"),
        CheckConstraint("snapshot_kind IN ('file', 'api_page', 'api_response')", name="ck_snapshots_kind"),
        CheckConstraint("storage_mode IN ('file_ref', 'inline_text')", name="ck_snapshots_storage_mode"),
        CheckConstraint("(storage_mode = 'file_ref' AND storage_ref IS NOT NULL) OR (storage_mode = 'inline_text' AND payload_text IS NOT NULL)", name="ck_snapshots_storage_location"),
        CheckConstraint("record_count >= 0", name="ck_snapshots_record_count"),
        Index("ix_raw_snapshots_content_hash", "content_sha256"),
    )


class Job(Base):
    """Logical source-aware job identity, independent of its versions."""

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), nullable=False)
    source_job_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_record_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    identity_key: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    identity_status: Mapped[str] = mapped_column(String(30), nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_run_id: Mapped[int | None] = mapped_column(ForeignKey("ingestion_runs.id"), nullable=True)
    consecutive_complete_misses: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    source: Mapped[Source] = relationship(back_populates="jobs")
    last_seen_run: Mapped[IngestionRun | None] = relationship(
        back_populates="last_seen_jobs", foreign_keys=[last_seen_run_id]
    )
    versions: Mapped[list[JobVersion]] = relationship(back_populates="job")

    __table_args__ = (
        CheckConstraint("identity_status IN ('provider_id', 'stable_reference', 'provisional', 'conflict')", name="ck_jobs_identity_status"),
        CheckConstraint("consecutive_complete_misses >= 0", name="ck_jobs_miss_count"),
        Index("ix_jobs_source_source_job_id", "source_id", "source_job_id"),
        Index("ix_jobs_source_active_last_seen", "source_id", "is_active", "last_seen_at"),
    )


class JobVersion(Base):
    """One observed normalized record for a logical job."""

    __tablename__ = "job_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False)
    raw_snapshot_id: Mapped[int | None] = mapped_column(ForeignKey("raw_snapshots.id"), nullable=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    origin_record_key: Mapped[str] = mapped_column(Text, nullable=False)
    content_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mapping_status: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    company_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    employment_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    job_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_tags_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    salary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    salary_status: Mapped[str] = mapped_column(String(30), nullable=False, default="not_disclosed")
    salary_currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    salary_period: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    salary_min_source: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    salary_max_source: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    salary_min_annual_inr: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    salary_max_annual_inr: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    experience_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    experience_min_years: Mapped[float | None] = mapped_column(Numeric(4, 1), nullable=True)
    experience_max_years: Mapped[float | None] = mapped_column(Numeric(4, 1), nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    posted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    transform_version: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    job: Mapped[Job] = relationship(back_populates="versions")
    raw_snapshot: Mapped[RawSnapshot | None] = relationship(back_populates="job_versions")
    skill_requirements: Mapped[list[JobSkill]] = relationship(back_populates="job_version")

    __table_args__ = (
        UniqueConstraint("job_id", "version_number", name="uq_job_versions_number"),
        UniqueConstraint("job_id", "origin_record_key", name="uq_job_versions_origin_record"),
        CheckConstraint("version_number >= 1", name="ck_job_versions_number"),
        CheckConstraint("mapping_status IN ('exact', 'ambiguous', 'conflict')", name="ck_job_versions_mapping_status"),
        CheckConstraint("salary_status IN ('valid', 'not_disclosed', 'missing_bounds', 'zero_unknown', 'incomplete_range', 'invalid_range')", name="ck_job_versions_salary_status"),
        CheckConstraint("salary_period IN ('annual', 'monthly', 'weekly', 'daily', 'hourly', 'unknown')", name="ck_job_versions_salary_period"),
        Index("uq_job_versions_one_current", "job_id", unique=True, sqlite_where=text("is_current = 1")),
        Index("ix_job_versions_job_fingerprint", "job_id", "content_fingerprint"),
        Index("ix_job_versions_posted_at", "posted_at"),
        Index("ix_job_versions_location", "location"),
        Index("ix_job_versions_salary_max_inr", "salary_max_annual_inr"),
    )


class Skill(Base):
    """Canonical normalized skill used for demand analysis."""

    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    job_requirements: Mapped[list[JobSkill]] = relationship(back_populates="skill")
    external_skill_benchmarks: Mapped[list[ExternalSkillBenchmark]] = relationship(back_populates="skill")
    external_salary_benchmarks: Mapped[list[ExternalSalaryBenchmark]] = relationship(back_populates="skill")

    __table_args__ = (Index("ix_skills_category", "category"),)


class JobSkill(Base):
    """Canonical skill requirement and merged raw evidence for one job version."""

    __tablename__ = "job_skills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_version_id: Mapped[int] = mapped_column(ForeignKey("job_versions.id"), nullable=False)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"), nullable=False)
    skill_raw: Mapped[str] = mapped_column(Text, nullable=False)
    extraction_source: Mapped[str] = mapped_column(String(30), nullable=False, default="tagsAndSkills")
    tags_match_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    description_match_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    raw_match_evidence_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    extraction_version: Mapped[str] = mapped_column(String(100), nullable=False)
    mapping_status: Mapped[str] = mapped_column(String(20), nullable=False, default="exact")
    source_record_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    job_version: Mapped[JobVersion] = relationship(back_populates="skill_requirements")
    skill: Mapped[Skill] = relationship(back_populates="job_requirements")

    __table_args__ = (
        UniqueConstraint("job_version_id", "skill_id", "extraction_version", name="uq_job_skills_version_skill_extraction"),
        CheckConstraint("extraction_source IN ('tagsAndSkills', 'jobDescription', 'both')", name="ck_job_skills_source"),
        CheckConstraint("mapping_status IN ('exact', 'ambiguous')", name="ck_job_skills_mapping_status"),
        CheckConstraint("tags_match_count >= 0 AND description_match_count >= 0", name="ck_job_skills_match_counts"),
        Index("ix_job_skills_skill_version", "skill_id", "job_version_id"),
        Index("ix_job_skills_job_version", "job_version_id"),
    )

    @property
    def evidence(self) -> list[dict[str, str]]:
        """Return parsed raw skill evidence without exposing JSON handling to callers."""
        if not self.raw_match_evidence_json:
            return []
        try:
            evidence = json.loads(self.raw_match_evidence_json)
        except json.JSONDecodeError:
            return []
        return evidence if isinstance(evidence, list) else []

    def add_evidence(self, raw_skill: str, source: str) -> None:
        """Merge one raw match while retaining tag/description provenance."""
        if source not in {"tagsAndSkills", "jobDescription"}:
            raise ValueError("Evidence source must be tagsAndSkills or jobDescription")
        entry: dict[str, str] = {"raw": raw_skill, "source": source}
        evidence = self.evidence
        if entry not in evidence:
            evidence.append(entry)
            self.raw_match_evidence_json = json.dumps(evidence, ensure_ascii=False, sort_keys=True)
        self.tags_match_count = sum(item.get("source") == "tagsAndSkills" for item in evidence)
        self.description_match_count = sum(item.get("source") == "jobDescription" for item in evidence)
        if self.tags_match_count and self.description_match_count:
            self.extraction_source = "both"
        elif self.description_match_count:
            self.extraction_source = "jobDescription"
        else:
            self.extraction_source = "tagsAndSkills"


class ExternalSkillBenchmark(Base):
    """One externally published skill-demand benchmark, kept outside job records."""

    __tablename__ = "external_skill_benchmarks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), nullable=False)
    raw_snapshot_id: Mapped[int] = mapped_column(ForeignKey("raw_snapshots.id"), nullable=False)
    skill_id: Mapped[int | None] = mapped_column(ForeignKey("skills.id"), nullable=True)
    external_skill_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mapping_status: Mapped[str] = mapped_column(String(20), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    active_jobs: Mapped[int] = mapped_column(Integer, nullable=False)
    share_of_tech_jobs_pct: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False)
    page_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    attribution: Mapped[str] = mapped_column(Text, nullable=False)
    original_values_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    source: Mapped[Source] = relationship(back_populates="external_skill_benchmarks")
    raw_snapshot: Mapped[RawSnapshot] = relationship(back_populates="external_skill_benchmarks")
    skill: Mapped[Skill | None] = relationship(back_populates="external_skill_benchmarks")

    __table_args__ = (
        UniqueConstraint("raw_snapshot_id", "external_skill_name", name="uq_external_skill_benchmarks_snapshot_skill"),
        CheckConstraint("mapping_status IN ('exact', 'alias', 'ambiguous', 'unmapped')", name="ck_external_skill_benchmarks_mapping_status"),
        CheckConstraint("rank >= 1", name="ck_external_skill_benchmarks_rank"),
        CheckConstraint("active_jobs >= 0", name="ck_external_skill_benchmarks_active_jobs"),
        CheckConstraint("share_of_tech_jobs_pct >= 0 AND share_of_tech_jobs_pct <= 100", name="ck_external_skill_benchmarks_share"),
        CheckConstraint("window_days > 0", name="ck_external_skill_benchmarks_window"),
        Index("ix_external_skill_benchmarks_source_as_of", "source_id", "as_of"),
        Index("ix_external_skill_benchmarks_skill_as_of", "skill_id", "as_of"),
    )


class ExternalSalaryBenchmark(Base):
    """One externally published salary benchmark, separate from JobRadar salary analytics."""

    __tablename__ = "external_salary_benchmarks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), nullable=False)
    raw_snapshot_id: Mapped[int] = mapped_column(ForeignKey("raw_snapshots.id"), nullable=False)
    skill_id: Mapped[int | None] = mapped_column(ForeignKey("skills.id"), nullable=True)
    group_type: Mapped[str] = mapped_column(String(30), nullable=False)
    group_label: Mapped[str] = mapped_column(Text, nullable=False)
    mapping_status: Mapped[str] = mapped_column(String(20), nullable=False)
    stated_salaries: Mapped[int] = mapped_column(Integer, nullable=False)
    lower_quartile_lpa: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    median_lpa: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    upper_quartile_lpa: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    attribution: Mapped[str] = mapped_column(Text, nullable=False)
    original_values_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    source: Mapped[Source] = relationship(back_populates="external_salary_benchmarks")
    raw_snapshot: Mapped[RawSnapshot] = relationship(back_populates="external_salary_benchmarks")
    skill: Mapped[Skill | None] = relationship(back_populates="external_salary_benchmarks")

    __table_args__ = (
        UniqueConstraint("raw_snapshot_id", "group_type", "group_label", name="uq_external_salary_benchmarks_snapshot_group"),
        CheckConstraint("group_type IN ('overall', 'experience', 'role_family', 'skill')", name="ck_external_salary_benchmarks_group_type"),
        CheckConstraint("mapping_status IN ('not_applicable', 'exact', 'alias', 'ambiguous', 'unmapped')", name="ck_external_salary_benchmarks_mapping_status"),
        CheckConstraint("(group_type = 'skill') OR (skill_id IS NULL)", name="ck_external_salary_benchmarks_skill_link"),
        CheckConstraint("stated_salaries >= 0", name="ck_external_salary_benchmarks_stated_salaries"),
        CheckConstraint("window_days > 0", name="ck_external_salary_benchmarks_window"),
        Index("ix_external_salary_benchmarks_source_as_of", "source_id", "as_of"),
        Index("ix_external_salary_benchmarks_skill_as_of", "skill_id", "as_of"),
        Index("ix_external_salary_benchmarks_group", "group_type", "group_label"),
    )
