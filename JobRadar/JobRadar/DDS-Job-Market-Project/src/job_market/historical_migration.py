"""Auditable, idempotent migration of JobRadar's cleaned historical files."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from .benchmark_import import file_sha256
from .database import PROJECT_ROOT, build_migration_key
from .models import IngestionRun, Job, JobSkill, JobVersion, RawSnapshot, Skill, Source
from .skills import build_description_patterns, extract_job_skills, load_alias_map, load_category_map


HISTORICAL_SOURCE_CODE = "historical_2025_xlsx"
HISTORICAL_SCHEMA_VERSION = "historical-schema-v1"
HISTORICAL_TRANSFORM_VERSION = "cleaning-v1"
HISTORICAL_SKILL_EXTRACTION_VERSION = "expanded-deterministic-v1"
EXPECTED_JOB_RECORDS = 97_682
EXPECTED_LEGACY_SKILL_RECORDS = 210_043
RAW_WORKBOOK_RECORDS = 97_929
DEFAULT_RAW_WORKBOOK = PROJECT_ROOT / "data" / "raw" / "indian-job-market-dataset-2025.xlsx"
DEFAULT_CLEANED_CSV = PROJECT_ROOT / "data" / "processed" / "cleaned_indian_job_market_2025.csv"
DEFAULT_LEGACY_SKILLS_CSV = PROJECT_ROOT / "data" / "processed" / "job_skills.csv"
DEFAULT_ALIASES = PROJECT_ROOT / "data" / "reference" / "skill_aliases.json"
DEFAULT_CATEGORIES = PROJECT_ROOT / "data" / "reference" / "skill_categories.json"


@dataclass(frozen=True)
class HistoricalMigrationResult:
    """Counts from a historical import attempt, suitable for reconciliation."""

    migration_key: str
    job_records: int
    job_versions: int
    conflict_records: int
    legacy_skill_records: int
    expanded_skill_records: int
    skills_created: int
    already_imported: bool


def _relative_storage_reference(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _manifest_hash(input_hashes: dict[str, str]) -> str:
    payload = json.dumps(input_hashes, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _optional_text(value: Any) -> str | None:
    return None if pd.isna(value) else str(value)


def _optional_float(value: Any) -> float | None:
    return None if pd.isna(value) else float(value)


def _origin_record_key(cleaned_sha256: str, row_number: int) -> str:
    """Stable reference to a one-based data row in the immutable cleaned CSV."""
    return f"cleaned:{cleaned_sha256}:row:{row_number}"


def _identity_key(source_code: str, source_job_id: str | None, origin_key: str, is_conflict: bool) -> str:
    """Build source-aware identity without merging ambiguous historical rows."""
    if is_conflict or not source_job_id:
        material = f"{source_code}:provisional:{origin_key}"
    else:
        material = f"{source_code}:provider_id:{source_job_id}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _row_fingerprint(row: pd.Series) -> str:
    """Content signal only; it is deliberately not a global unique identity."""
    keys = ("title_clean", "companyName_clean", "location_clean", "jobDescription_clean", "tagsAndSkills_clean", "salary")
    payload = {key: _optional_text(row.get(key)) for key in keys}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _read_cleaned_csv(path: Path, expected_rows: int) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f"Cleaned historical CSV was not found: {path}")
    frame = pd.read_csv(path)
    required = {
        "jobId", "duplicate_jobid_conflict", "title_clean", "companyName_clean", "location_clean",
        "jobDescription_clean", "tagsAndSkills_clean", "salary_status", "currency", "jobUploaded",
    }
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"{path.name} is missing required columns: {', '.join(sorted(missing))}")
    if len(frame) != expected_rows:
        raise ValueError(f"{path.name} expected {expected_rows} rows, found {len(frame)}")
    return frame


def _read_legacy_skills(path: Path, expected_rows: int) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f"Historical skill CSV was not found: {path}")
    frame = pd.read_csv(path)
    required = {"jobId", "skill_raw", "skill_normalized", "skill_source", "skill_category"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"{path.name} is missing required columns: {', '.join(sorted(missing))}")
    if len(frame) != expected_rows:
        raise ValueError(f"{path.name} expected {expected_rows} rows, found {len(frame)}")
    return frame


def import_historical_dataset(
    session: Session,
    *,
    cleaned_csv: str | Path = DEFAULT_CLEANED_CSV,
    legacy_skills_csv: str | Path = DEFAULT_LEGACY_SKILLS_CSV,
    raw_workbook: str | Path = DEFAULT_RAW_WORKBOOK,
    aliases_path: str | Path = DEFAULT_ALIASES,
    categories_path: str | Path = DEFAULT_CATEGORIES,
    observed_at: datetime | None = None,
    expected_job_records: int = EXPECTED_JOB_RECORDS,
    expected_legacy_skill_records: int = EXPECTED_LEGACY_SKILL_RECORDS,
) -> HistoricalMigrationResult:
    """Import historical rows in CSV order, preserving all ambiguous identities.

    The legacy skill file remains immutable evidence. Skills are re-extracted in
    memory from uniquely labelled cleaned rows so duplicate provider IDs cannot
    attach evidence to the wrong historical version.
    """
    cleaned_path, legacy_path, workbook_path = map(Path, (cleaned_csv, legacy_skills_csv, raw_workbook))
    aliases_path, categories_path = map(Path, (aliases_path, categories_path))
    if not workbook_path.is_file():
        raise FileNotFoundError(f"Historical workbook was not found: {workbook_path}")
    cleaned = _read_cleaned_csv(cleaned_path, expected_job_records)
    legacy_skills = _read_legacy_skills(legacy_path, expected_legacy_skill_records)
    legacy_count = len(legacy_skills)
    if not aliases_path.is_file() or not categories_path.is_file():
        raise FileNotFoundError("Historical skill reference files were not found")

    input_hashes = {
        "raw_workbook": file_sha256(workbook_path),
        "cleaned_csv": file_sha256(cleaned_path),
        "legacy_job_skills_csv": file_sha256(legacy_path),
        "skill_aliases_json": file_sha256(aliases_path),
        "skill_categories_json": file_sha256(categories_path),
    }
    migration_key = build_migration_key(
        source_code=HISTORICAL_SOURCE_CODE,
        migration_name="historical-cleaned-jobs-import",
        schema_mapping_version=HISTORICAL_SCHEMA_VERSION,
        cleaning_transform_version=HISTORICAL_TRANSFORM_VERSION,
        skill_extraction_version=HISTORICAL_SKILL_EXTRACTION_VERSION,
        input_hashes=input_hashes,
    )
    import_time = observed_at or datetime.now(UTC)

    # Check the immutable migration identity before performing the expensive
    # whole-dataset extraction.  Roll back the read-only implicit transaction
    # so the following write transaction is clean and atomic.
    existing = session.scalar(select(IngestionRun).where(IngestionRun.migration_key == migration_key))
    if existing is not None and existing.status == "succeeded":
        session.rollback()
        return HistoricalMigrationResult(
            migration_key=migration_key, job_records=0, job_versions=0, conflict_records=0,
            legacy_skill_records=0, expanded_skill_records=0, skills_created=0, already_imported=True,
        )
    session.rollback()

    # Re-labeling is in-memory only and makes every row-to-skill mapping
    # unambiguous, including the six rows with conflicting provider IDs.
    extraction_input = cleaned.copy()
    extraction_input["jobId"] = [f"row:{index + 1}" for index in range(len(cleaned))]
    raw_aliases = json.loads(aliases_path.read_text(encoding="utf-8"))
    expanded_skills = extract_job_skills(
        extraction_input,
        load_alias_map(aliases_path),
        load_category_map(categories_path),
        build_description_patterns(raw_aliases),
    )

    with session.begin():
        source = session.scalar(select(Source).where(Source.code == HISTORICAL_SOURCE_CODE))
        if source is None:
            source = Source(
                code=HISTORICAL_SOURCE_CODE, name="Indian Job Market Dataset 2025",
                source_type="historical_file", base_url=_relative_storage_reference(workbook_path),
            )
            session.add(source)

        run = IngestionRun(
            source=source, run_type="historical_import", status="running", is_complete=False,
            observed_at=import_time, transform_version=HISTORICAL_TRANSFORM_VERSION,
            migration_key=migration_key, input_manifest_sha256=_manifest_hash(input_hashes),
            records_received=len(cleaned),
        )
        session.add(run)
        session.flush()
        workbook_snapshot = RawSnapshot(
            ingestion_run=run, snapshot_sequence=1, snapshot_kind="file",
            source_record_ref=_relative_storage_reference(workbook_path), collected_at=import_time,
            content_sha256=input_hashes["raw_workbook"], storage_mode="file_ref",
            storage_ref=_relative_storage_reference(workbook_path), mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            record_count=RAW_WORKBOOK_RECORDS,
        )
        cleaned_snapshot = RawSnapshot(
            ingestion_run=run, snapshot_sequence=2, snapshot_kind="file",
            source_record_ref=_relative_storage_reference(cleaned_path), collected_at=import_time,
            content_sha256=input_hashes["cleaned_csv"], storage_mode="file_ref",
            storage_ref=_relative_storage_reference(cleaned_path), mime_type="text/csv", record_count=len(cleaned),
        )
        legacy_snapshot = RawSnapshot(
            ingestion_run=run, snapshot_sequence=3, snapshot_kind="file",
            source_record_ref=_relative_storage_reference(legacy_path), collected_at=import_time,
            content_sha256=input_hashes["legacy_job_skills_csv"], storage_mode="file_ref",
            storage_ref=_relative_storage_reference(legacy_path), mime_type="text/csv", record_count=legacy_count,
        )
        session.add_all((workbook_snapshot, cleaned_snapshot, legacy_snapshot))
        session.flush()

        versions_by_row: dict[str, JobVersion] = {}
        conflict_count = 0
        for row_index, (_, row) in enumerate(cleaned.iterrows(), start=1):
            origin_key = _origin_record_key(input_hashes["cleaned_csv"], row_index)
            source_job_id = _optional_text(row.get("jobId"))
            is_conflict = bool(row.get("duplicate_jobid_conflict", False))
            if is_conflict:
                conflict_count += 1
            job = Job(
                source=source, source_job_id=source_job_id, source_record_ref=origin_key,
                identity_key=_identity_key(HISTORICAL_SOURCE_CODE, source_job_id, origin_key, is_conflict),
                identity_status="conflict" if is_conflict else "provider_id",
                first_seen_at=import_time, last_seen_at=import_time, last_seen_run=run,
            )
            salary_status = _optional_text(row.get("salary_status")) or "not_disclosed"
            version = JobVersion(
                job=job, raw_snapshot=cleaned_snapshot, version_number=1, is_current=True,
                origin_record_key=origin_key, content_fingerprint=_row_fingerprint(row),
                mapping_status="conflict" if is_conflict else "exact",
                title=_optional_text(row.get("title_clean")), company_name=_optional_text(row.get("companyName_clean")),
                location=_optional_text(row.get("location_clean")), job_description=_optional_text(row.get("jobDescription_clean")),
                source_tags_text=_optional_text(row.get("tagsAndSkills_clean")), salary_text=_optional_text(row.get("salary")),
                salary_status=salary_status, salary_currency=_optional_text(row.get("currency")),
                salary_period="annual" if salary_status == "valid" else "unknown",
                salary_min_source=_optional_float(row.get("minimumSalary_clean")),
                salary_max_source=_optional_float(row.get("maximumSalary_clean")),
                salary_min_annual_inr=_optional_float(row.get("minimumSalary_clean")) if _optional_text(row.get("currency")) == "INR" else None,
                salary_max_annual_inr=_optional_float(row.get("maximumSalary_clean")) if _optional_text(row.get("currency")) == "INR" else None,
                experience_text=_optional_text(row.get("experience")),
                experience_min_years=_optional_float(row.get("minimumExperience_clean")),
                experience_max_years=_optional_float(row.get("maximumExperience_clean")),
                posted_text=_optional_text(row.get("jobUploaded")), observed_at=import_time, ingested_at=import_time,
                transform_version=HISTORICAL_TRANSFORM_VERSION,
            )
            session.add(version)
            versions_by_row[f"row:{row_index}"] = version
        session.flush()

        skills_by_name = {skill.normalized_name: skill for skill in session.scalars(select(Skill)).all()}
        created_skills = 0
        for name, category in expanded_skills[["skill_normalized", "skill_category"]].drop_duplicates().itertuples(index=False):
            normalized = str(name).casefold()
            if normalized not in skills_by_name:
                skills_by_name[normalized] = Skill(name=str(name), normalized_name=normalized, category=str(category))
                session.add(skills_by_name[normalized])
                created_skills += 1
        session.flush()
        for row in expanded_skills.itertuples(index=False):
            source_name = str(row.skill_source)
            evidence_sources = ["tagsAndSkills", "jobDescription"] if source_name == "both" else [source_name]
            evidence = [{"raw": str(row.skill_raw), "source": evidence_source} for evidence_source in evidence_sources]
            session.add(JobSkill(
                job_version=versions_by_row[str(row.jobId)], skill=skills_by_name[str(row.skill_normalized).casefold()],
                skill_raw=str(row.skill_raw), extraction_source=source_name,
                tags_match_count=int(source_name in {"tagsAndSkills", "both"}),
                description_match_count=int(source_name in {"jobDescription", "both"}),
                raw_match_evidence_json=json.dumps(evidence, ensure_ascii=False, sort_keys=True),
                extraction_version=HISTORICAL_SKILL_EXTRACTION_VERSION, mapping_status="exact",
                source_record_ref=f"{_origin_record_key(input_hashes['cleaned_csv'], int(str(row.jobId).split(':')[1]))}:skill:{str(row.skill_normalized).casefold()}",
            ))
        run.records_inserted = len(cleaned) + len(expanded_skills)
        run.status, run.is_complete, run.completed_at = "succeeded", True, import_time

    return HistoricalMigrationResult(
        migration_key=migration_key, job_records=len(cleaned), job_versions=len(cleaned),
        conflict_records=conflict_count, legacy_skill_records=legacy_count,
        expanded_skill_records=len(expanded_skills), skills_created=created_skills, already_imported=False,
    )
