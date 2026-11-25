"""Idempotent importer for audited Jobspiq benchmark CSV files."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import PROJECT_ROOT, build_migration_key
from .models import (
    ExternalSalaryBenchmark,
    ExternalSkillBenchmark,
    IngestionRun,
    RawSnapshot,
    Skill,
    Source,
)


JOBSPIQ_SOURCE_CODE = "jobspiq_india"
BENCHMARK_SCHEMA_VERSION = "jobspiq-benchmark-schema-v1"
BENCHMARK_TRANSFORM_VERSION = "jobspiq-benchmark-v1"
EXPECTED_SKILL_RECORDS = 76
EXPECTED_SALARY_RECORDS = 25
DEFAULT_SKILLS_CSV = PROJECT_ROOT / "data" / "external" / "jobspiq" / "benchmarks" / "skills-demand-india.csv"
DEFAULT_SALARIES_CSV = PROJECT_ROOT / "data" / "external" / "jobspiq" / "benchmarks" / "tech-salaries-stated-india.csv"


@dataclass(frozen=True)
class BenchmarkImportResult:
    """Safe summary of one benchmark import attempt."""

    migration_key: str
    skill_records: int
    salary_records: int
    already_imported: bool


def file_sha256(path: Path) -> str:
    """Return the SHA-256 hash of a source file without altering it."""
    digest = hashlib.sha256()
    with path.open("rb") as source_file:
        for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_csv(path: Path, required_columns: set[str], expected_rows: int) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"Benchmark CSV was not found: {path}")
    with path.open(encoding="utf-8-sig", newline="") as source_file:
        reader = csv.DictReader(source_file)
        columns = set(reader.fieldnames or [])
        missing_columns = required_columns.difference(columns)
        if missing_columns:
            raise ValueError(f"{path.name} is missing required columns: {', '.join(sorted(missing_columns))}")
        rows = [dict(row) for row in reader]
    if len(rows) != expected_rows:
        raise ValueError(f"{path.name} expected {expected_rows} rows, found {len(rows)}")
    return rows


def _relative_storage_reference(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _decimal(value: str) -> Decimal:
    return Decimal(value)


def _skill_mapping(raw_name: str, skills_by_name: dict[str, Skill]) -> tuple[Skill | None, str]:
    """Map only an exact existing canonical skill; never invent aliases."""
    skill = skills_by_name.get(raw_name.casefold())
    return (skill, "exact") if skill is not None else (None, "unmapped")


def _build_skill_benchmark(
    *, source: Source, snapshot: RawSnapshot, row: dict[str, str], skills_by_name: dict[str, Skill]
) -> ExternalSkillBenchmark:
    skill, mapping_status = _skill_mapping(row["skill"], skills_by_name)
    return ExternalSkillBenchmark(
        source=source,
        raw_snapshot=snapshot,
        skill=skill,
        external_skill_name=row["skill"],
        mapping_status=mapping_status,
        rank=int(row["rank"]),
        active_jobs=int(row["active_jobs"]),
        share_of_tech_jobs_pct=_decimal(row["share_of_tech_jobs_pct"]),
        page_url=row["page_url"] or None,
        as_of=date.fromisoformat(row["as_of"]),
        window_days=int(row["window_days"]),
        attribution=row["attribution"],
        original_values_json=json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
    )


def _build_salary_benchmark(
    *, source: Source, snapshot: RawSnapshot, row: dict[str, str], skills_by_name: dict[str, Skill]
) -> ExternalSalaryBenchmark:
    skill: Skill | None = None
    mapping_status = "not_applicable"
    if row["group_type"] == "skill":
        skill, mapping_status = _skill_mapping(row["group"], skills_by_name)
    return ExternalSalaryBenchmark(
        source=source,
        raw_snapshot=snapshot,
        skill=skill,
        group_type=row["group_type"],
        group_label=row["group"],
        mapping_status=mapping_status,
        stated_salaries=int(row["stated_salaries"]),
        lower_quartile_lpa=_decimal(row["lower_quartile_lpa"]),
        median_lpa=_decimal(row["median_lpa"]),
        upper_quartile_lpa=_decimal(row["upper_quartile_lpa"]),
        as_of=date.fromisoformat(row["as_of"]),
        window_days=int(row["window_days"]),
        attribution=row["attribution"],
        original_values_json=json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
    )


def import_jobspiq_benchmarks(
    session: Session,
    *,
    skills_csv: str | Path = DEFAULT_SKILLS_CSV,
    salaries_csv: str | Path = DEFAULT_SALARIES_CSV,
    observed_at: datetime | None = None,
) -> BenchmarkImportResult:
    """Import the two audited Jobspiq files transactionally and idempotently."""
    skills_path = Path(skills_csv)
    salaries_path = Path(salaries_csv)
    skill_rows = _read_csv(
        skills_path,
        {"rank", "skill", "active_jobs", "share_of_tech_jobs_pct", "page_url", "as_of", "window_days", "attribution"},
        EXPECTED_SKILL_RECORDS,
    )
    salary_rows = _read_csv(
        salaries_path,
        {"group_type", "group", "stated_salaries", "lower_quartile_lpa", "median_lpa", "upper_quartile_lpa", "as_of", "window_days", "attribution"},
        EXPECTED_SALARY_RECORDS,
    )
    input_hashes = {
        "skills-demand-india.csv": file_sha256(skills_path),
        "tech-salaries-stated-india.csv": file_sha256(salaries_path),
    }
    migration_key = build_migration_key(
        source_code=JOBSPIQ_SOURCE_CODE,
        migration_name="jobspiq-benchmark-import",
        schema_mapping_version=BENCHMARK_SCHEMA_VERSION,
        cleaning_transform_version="not-applicable",
        skill_extraction_version="not-applicable",
        input_hashes=input_hashes,
    )
    import_time = observed_at or datetime.now(UTC)
    manifest_hash = hashlib.sha256(
        json.dumps(input_hashes, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    with session.begin():
        existing_run = session.scalar(
            select(IngestionRun).where(IngestionRun.migration_key == migration_key)
        )
        if existing_run is not None and existing_run.status == "succeeded":
            return BenchmarkImportResult(
                migration_key=migration_key,
                skill_records=0,
                salary_records=0,
                already_imported=True,
            )

        source = session.scalar(select(Source).where(Source.code == JOBSPIQ_SOURCE_CODE))
        if source is None:
            source = Source(
                code=JOBSPIQ_SOURCE_CODE,
                name="Jobspiq India benchmark datasets",
                source_type="manual_import",
                base_url="https://jobspiq.in/data",
            )
            session.add(source)

        run = IngestionRun(
            source=source,
            run_type="historical_import",
            status="running",
            is_complete=False,
            observed_at=import_time,
            transform_version=BENCHMARK_TRANSFORM_VERSION,
            migration_key=migration_key,
            input_manifest_sha256=manifest_hash,
            records_received=len(skill_rows) + len(salary_rows),
        )
        session.add(run)
        session.flush()

        skill_snapshot = RawSnapshot(
            ingestion_run=run,
            snapshot_sequence=1,
            snapshot_kind="file",
            source_record_ref=_relative_storage_reference(skills_path),
            collected_at=import_time,
            content_sha256=input_hashes["skills-demand-india.csv"],
            storage_mode="file_ref",
            storage_ref=_relative_storage_reference(skills_path),
            mime_type="text/csv",
            record_count=len(skill_rows),
        )
        salary_snapshot = RawSnapshot(
            ingestion_run=run,
            snapshot_sequence=2,
            snapshot_kind="file",
            source_record_ref=_relative_storage_reference(salaries_path),
            collected_at=import_time,
            content_sha256=input_hashes["tech-salaries-stated-india.csv"],
            storage_mode="file_ref",
            storage_ref=_relative_storage_reference(salaries_path),
            mime_type="text/csv",
            record_count=len(salary_rows),
        )
        session.add_all([skill_snapshot, salary_snapshot])

        skills_by_name = {
            skill.normalized_name.casefold(): skill for skill in session.scalars(select(Skill)).all()
        }
        session.add_all(
            _build_skill_benchmark(
                source=source, snapshot=skill_snapshot, row=row, skills_by_name=skills_by_name
            )
            for row in skill_rows
        )
        session.add_all(
            _build_salary_benchmark(
                source=source, snapshot=salary_snapshot, row=row, skills_by_name=skills_by_name
            )
            for row in salary_rows
        )
        run.records_inserted = len(skill_rows) + len(salary_rows)
        run.status = "succeeded"
        run.is_complete = True
        run.completed_at = import_time

    return BenchmarkImportResult(
        migration_key=migration_key,
        skill_records=len(skill_rows),
        salary_records=len(salary_rows),
        already_imported=False,
    )
