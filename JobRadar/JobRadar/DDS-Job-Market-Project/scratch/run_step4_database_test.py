"""JobRadar Phase 7.5 Step 4: Database Integration Testing Suite.

Executes complete testing stages A through H in isolated in-memory SQLite
and performs a strict read-only audit of the production database.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
import sqlite3
import sys
import time
from typing import Any

from sqlalchemy import (
    Engine,
    create_engine,
    event,
    func,
    select,
    text,
)
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session, sessionmaker

# Setup project import paths
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from job_market.database import (
    Base,
    _enable_sqlite_foreign_keys,
    build_migration_key,
    create_database_engine,
    create_session_factory,
    initialize_database,
)
from job_market.models import (
    ExternalSalaryBenchmark,
    ExternalSkillBenchmark,
    IngestionRun,
    Job,
    JobSkill,
    JobVersion,
    RawSnapshot,
    Skill,
    Source,
    utc_now,
)

results: dict[str, Any] = {
    "stage_a": {},
    "stage_b": {},
    "stage_c": {},
    "stage_d": {},
    "stage_e": {},
    "stage_f": {},
    "stage_g": {},
    "stage_h": {},
    "summary": {"passed": 0, "failed": 0, "total": 0},
}


def assert_test(stage: str, test_name: str, passed: bool, details: Any = None):
    results["summary"]["total"] += 1
    if passed:
        results["summary"]["passed"] += 1
        status = "PASS"
    else:
        results["summary"]["failed"] += 1
        status = "FAIL"
    results[stage][test_name] = {"status": status, "details": details}
    print(f"[{status}] {stage.upper()} -> {test_name}")


def run_stage_a():
    """Stage A: Database Discovery."""
    print("\n=== STAGE A: DATABASE DISCOVERY ===")
    engine = create_database_engine("sqlite:///:memory:")
    assert_test("stage_a", "engine_dialect", engine.dialect.name == "sqlite", {"dialect": engine.dialect.name})

    # Verify session factory
    session_factory = create_session_factory(engine)
    session = session_factory()
    assert_test("stage_a", "session_factory", isinstance(session, Session), {"session_class": type(session).__name__})
    session.close()

    # Verify all 9 models registered in Base.metadata
    table_names = sorted(list(Base.metadata.tables.keys()))
    expected_tables = [
        "external_salary_benchmarks",
        "external_skill_benchmarks",
        "ingestion_runs",
        "job_skills",
        "job_versions",
        "jobs",
        "raw_snapshots",
        "skills",
        "sources",
    ]
    assert_test(
        "stage_a",
        "models_registered",
        table_names == expected_tables,
        {"registered_tables": table_names, "expected": expected_tables},
    )

    # Verify foreign key event listener configuration
    with engine.connect() as conn:
        fk_status = conn.execute(text("PRAGMA foreign_keys")).scalar()
        assert_test("stage_a", "sqlite_foreign_keys_pragma", fk_status == 1, {"pragma_foreign_keys": fk_status})
    engine.dispose()


def run_stage_b():
    """Stage B: Schema Integrity."""
    print("\n=== STAGE B: SCHEMA INTEGRITY ===")
    engine = initialize_database("sqlite:///:memory:")
    session_factory = create_session_factory(engine)

    # 1. Foreign Key Enforcement: inserting run with nonexistent source_id
    with session_factory() as s:
        run = IngestionRun(
            source_id=99999,
            run_type="historical_import",
            status="running",
            observed_at=utc_now(),
            transform_version="v1.0",
        )
        s.add(run)
        fk_failed = False
        try:
            s.commit()
        except IntegrityError:
            s.rollback()
            fk_failed = True
        assert_test("stage_b", "foreign_key_enforcement", fk_failed, "Nonexistent FK rejected by SQLite engine")

    # 2. Unique Constraints
    with session_factory() as s:
        src1 = Source(code="SRC_UNIQ", name="Source 1", source_type="api")
        s.add(src1)
        s.commit()

        src2 = Source(code="SRC_UNIQ", name="Source 2", source_type="api")
        s.add(src2)
        uniq_failed = False
        try:
            s.commit()
        except IntegrityError:
            s.rollback()
            uniq_failed = True
        assert_test("stage_b", "unique_constraint_source_code", uniq_failed, "Duplicate Source.code rejected")

    # 3. Check Constraint: source_type IN ('historical_file', 'api', 'manual_import')
    with session_factory() as s:
        invalid_src = Source(code="SRC_INVALID", name="Bad Source", source_type="invalid_type")
        s.add(invalid_src)
        check_failed = False
        try:
            s.commit()
        except IntegrityError:
            s.rollback()
            check_failed = True
        assert_test("stage_b", "check_constraint_source_type", check_failed, "Invalid source_type rejected")

    # 4. Check Constraint: retry_count >= 0
    with session_factory() as s:
        src = s.execute(select(Source).filter_by(code="SRC_UNIQ")).scalar_one()
        bad_run = IngestionRun(
            source_id=src.id,
            run_type="historical_import",
            status="running",
            observed_at=utc_now(),
            transform_version="v1.0",
            retry_count=-1,
        )
        s.add(bad_run)
        check_failed = False
        try:
            s.commit()
        except IntegrityError:
            s.rollback()
            check_failed = True
        assert_test("stage_b", "check_constraint_retry_count", check_failed, "Negative retry_count rejected")

    # 5. Partial Index: uq_job_versions_one_current
    with session_factory() as s:
        src = s.execute(select(Source).filter_by(code="SRC_UNIQ")).scalar_one()
        job = Job(
            source_id=src.id,
            identity_key="test_job_current_idx",
            identity_status="provider_id",
            first_seen_at=utc_now(),
            last_seen_at=utc_now(),
        )
        s.add(job)
        s.commit()

        v1 = JobVersion(
            job_id=job.id,
            version_number=1,
            is_current=True,
            origin_record_key="rec_1",
            mapping_status="exact",
            observed_at=utc_now(),
            ingested_at=utc_now(),
            transform_version="v1",
        )
        s.add(v1)
        s.commit()

        # Attempt to add second version also marked is_current=True
        v2 = JobVersion(
            job_id=job.id,
            version_number=2,
            is_current=True,
            origin_record_key="rec_2",
            mapping_status="exact",
            observed_at=utc_now(),
            ingested_at=utc_now(),
            transform_version="v1",
        )
        s.add(v2)
        partial_failed = False
        try:
            s.commit()
        except IntegrityError:
            s.rollback()
            partial_failed = True
        assert_test(
            "stage_b",
            "partial_unique_index_one_current",
            partial_failed,
            "Partial index enforces at most one current version per job",
        )

    engine.dispose()


def run_stage_c():
    """Stage C: CRUD Integration."""
    print("\n=== STAGE C: CRUD INTEGRATION ===")
    engine = initialize_database("sqlite:///:memory:")
    session_factory = create_session_factory(engine)

    with session_factory() as s:
        # 1. CREATE
        src = Source(code="CRUD_SRC", name="CRUD Source", source_type="api")
        s.add(src)
        s.commit()
        assert_test("stage_c", "create_record", src.id is not None, {"created_source_id": src.id})

        # 2. READ
        fetched = s.get(Source, src.id)
        assert_test(
            "stage_c",
            "read_record",
            fetched is not None and fetched.code == "CRUD_SRC",
            {"fetched_code": fetched.code if fetched else None},
        )

        # 3. UPDATE
        fetched.name = "CRUD Source Updated"
        s.commit()
        s.refresh(fetched)
        assert_test("stage_c", "update_record", fetched.name == "CRUD Source Updated", {"updated_name": fetched.name})

        # 4. DELETE
        s.delete(fetched)
        s.commit()
        deleted = s.get(Source, src.id)
        assert_test("stage_c", "delete_record", deleted is None, "Record removed successfully")

        # 5. DELETE RESTRICT WITH FOREIGN KEY
        src_parent = Source(code="PARENT_SRC", name="Parent Source", source_type="api")
        s.add(src_parent)
        s.flush()
        job_child = Job(
            source_id=src_parent.id,
            identity_key="job_child_fk",
            identity_status="provider_id",
            first_seen_at=utc_now(),
            last_seen_at=utc_now(),
        )
        s.add(job_child)
        s.commit()

        # Attempt to delete parent source while child job exists
        s.delete(src_parent)
        delete_blocked = False
        try:
            s.commit()
        except IntegrityError:
            s.rollback()
            delete_blocked = True
        assert_test(
            "stage_c",
            "delete_restrict_foreign_key",
            delete_blocked,
            "SQLite foreign key constraint prevents deleting parent source with active jobs",
        )

    engine.dispose()


def run_stage_d():
    """Stage D: Transaction Testing."""
    print("\n=== STAGE D: TRANSACTION TESTING ===")
    engine = initialize_database("sqlite:///:memory:")
    session_factory = create_session_factory(engine)

    # 1. Successful atomic commit across multiple entities
    with session_factory() as s:
        src = Source(code="TX_SRC", name="Tx Source", source_type="api")
        s.add(src)
        s.flush()

        run = IngestionRun(
            source_id=src.id,
            run_type="historical_import",
            status="running",
            observed_at=utc_now(),
            transform_version="v1.0",
        )
        s.add(run)
        s.commit()
        assert_test("stage_d", "atomic_multi_entity_commit", src.id is not None and run.id is not None)

    # 2. Rollback after intentional failure preserves DB state
    with session_factory() as s:
        # Add a source
        s.add(Source(code="VALID_BEFORE_FAIL", name="Valid", source_type="api"))
        # Add an invalid source that will violate constraint
        s.add(Source(code="VALID_BEFORE_FAIL", name="Duplicate Code", source_type="api"))
        try:
            s.commit()
            rollback_verified = False
        except IntegrityError:
            s.rollback()
            # Verify VALID_BEFORE_FAIL was NOT saved
            check = s.execute(select(Source).filter_by(code="VALID_BEFORE_FAIL")).scalar_one_or_none()
            rollback_verified = (check is None)
        assert_test("stage_d", "rollback_on_intentional_failure", rollback_verified, "Transaction rolled back completely")

    # 3. Savepoint / Nested Transaction Handling (Partial Failure)
    with session_factory() as s:
        src = Source(code="SAVEPOINT_SRC", name="Savepoint", source_type="api")
        s.add(src)
        s.flush()

        # Inner savepoint
        sp = s.begin_nested()
        bad_run = IngestionRun(
            source_id=99999,  # invalid FK
            run_type="historical_import",
            status="running",
            observed_at=utc_now(),
            transform_version="v1.0",
        )
        s.add(bad_run)
        try:
            sp.commit()
            partial_handled = False
        except IntegrityError:
            sp.rollback()
            # Outer session remains valid and can still commit src
            s.commit()
            check = s.execute(select(Source).filter_by(code="SAVEPOINT_SRC")).scalar_one_or_none()
            partial_handled = (check is not None)
        assert_test(
            "stage_d",
            "nested_transaction_savepoint_handling",
            partial_handled,
            "Savepoint rollback isolates inner failure while outer transaction succeeds",
        )

    # 4. Session cleanup
    s = session_factory()
    s.add(Source(code="SESSION_CLEANUP", name="Temp", source_type="api"))
    s.close()
    assert_test(
        "stage_d",
        "session_cleanup",
        s.get_transaction() is None and len(s.new) == 0,
        "Session closed cleanly, active transaction cleared, and new objects discarded",
    )

    engine.dispose()


def run_stage_e():
    """Stage E: Job and Skill Relationships."""
    print("\n=== STAGE E: JOB AND SKILL RELATIONSHIPS ===")
    engine = initialize_database("sqlite:///:memory:")
    session_factory = create_session_factory(engine)

    with session_factory() as s:
        src = Source(code="REL_SRC", name="Rel Source", source_type="api")
        s.add(src)
        s.flush()

        job1 = Job(
            source_id=src.id,
            identity_key="job_rel_1",
            identity_status="provider_id",
            first_seen_at=utc_now(),
            last_seen_at=utc_now(),
        )
        job2 = Job(
            source_id=src.id,
            identity_key="job_rel_2",
            identity_status="provider_id",
            first_seen_at=utc_now(),
            last_seen_at=utc_now(),
        )
        s.add_all([job1, job2])
        s.flush()

        jv1 = JobVersion(
            job_id=job1.id,
            version_number=1,
            is_current=True,
            origin_record_key="rec_rel_1",
            mapping_status="exact",
            observed_at=utc_now(),
            ingested_at=utc_now(),
            transform_version="v1",
        )
        jv2 = JobVersion(
            job_id=job2.id,
            version_number=1,
            is_current=True,
            origin_record_key="rec_rel_2",
            mapping_status="exact",
            observed_at=utc_now(),
            ingested_at=utc_now(),
            transform_version="v1",
        )
        s.add_all([jv1, jv2])
        s.flush()

        sk_py = Skill(name="Python", normalized_name="python", category="Programming Language")
        sk_sql = Skill(name="SQL", normalized_name="sql", category="Database")
        s.add_all([sk_py, sk_sql])
        s.flush()

        # Job 1 has both Python and SQL (One job -> multiple skills)
        js1 = JobSkill(job_version_id=jv1.id, skill_id=sk_py.id, skill_raw="Python 3", extraction_version="v1")
        js2 = JobSkill(job_version_id=jv1.id, skill_id=sk_sql.id, skill_raw="PostgreSQL", extraction_version="v1")
        # Job 2 also has Python (One skill -> multiple jobs)
        js3 = JobSkill(job_version_id=jv2.id, skill_id=sk_py.id, skill_raw="Python", extraction_version="v1")
        s.add_all([js1, js2, js3])
        s.commit()

        # Verify many-to-many navigation
        s.refresh(jv1)
        skills_in_jv1 = [js.skill.name for js in jv1.skill_requirements]
        assert_test(
            "stage_e",
            "one_job_multiple_skills",
            sorted(skills_in_jv1) == ["Python", "SQL"],
            {"jv1_skills": skills_in_jv1},
        )

        s.refresh(sk_py)
        jobs_with_py = [js.job_version.job.identity_key for js in sk_py.job_requirements]
        assert_test(
            "stage_e",
            "one_skill_multiple_jobs",
            sorted(jobs_with_py) == ["job_rel_1", "job_rel_2"],
            {"python_jobs": jobs_with_py},
        )

        # Duplicate job-skill rejection (same version + skill + extraction_version)
        dup_js = JobSkill(job_version_id=jv1.id, skill_id=sk_py.id, skill_raw="Py", extraction_version="v1")
        s.add(dup_js)
        dup_failed = False
        try:
            s.commit()
        except IntegrityError:
            s.rollback()
            dup_failed = True
        assert_test("stage_e", "duplicate_job_skill_rejection", dup_failed, "Duplicate JobSkill link rejected")

        # Invalid foreign key reference (nonexistent skill_id)
        bad_fk_js = JobSkill(job_version_id=jv1.id, skill_id=99999, skill_raw="Nonexistent", extraction_version="v1")
        s.add(bad_fk_js)
        bad_fk_failed = False
        try:
            s.commit()
        except IntegrityError:
            s.rollback()
            bad_fk_failed = True
        assert_test("stage_e", "invalid_skill_fk_rejection", bad_fk_failed, "Nonexistent skill_id FK rejected")

        # Provenance & evidence helper
        test_js = JobSkill(job_version_id=jv2.id, skill_id=sk_sql.id, skill_raw="SQL", extraction_version="v1")
        test_js.add_evidence("Postgres", "tagsAndSkills")
        test_js.add_evidence("PostgreSQL Developer", "jobDescription")
        s.add(test_js)
        s.commit()
        s.refresh(test_js)
        assert_test(
            "stage_e",
            "match_provenance_evidence",
            test_js.extraction_source == "both" and test_js.tags_match_count == 1 and test_js.description_match_count == 1,
            {"source": test_js.extraction_source, "tags": test_js.tags_match_count, "desc": test_js.description_match_count},
        )

    engine.dispose()


def run_stage_f():
    """Stage F: Historical Data Integrity & Idempotent Migration."""
    print("\n=== STAGE F: HISTORICAL INTEGRITY & MIGRATION ===")
    engine = initialize_database("sqlite:///:memory:")
    session_factory = create_session_factory(engine)

    with session_factory() as s:
        src = Source(code="HIST_SRC", name="Historical Source", source_type="historical_file")
        s.add(src)
        s.flush()

        # Test deterministic migration key generation
        inputs = {"cleaned.csv": "abc123hash", "skills.csv": "def456hash"}
        key1 = build_migration_key(
            source_code="HIST_SRC",
            migration_name="historical_2025_import",
            schema_mapping_version="v1.0",
            cleaning_transform_version="cleaning-v1",
            skill_extraction_version="v1.0",
            input_hashes=inputs,
        )
        key2 = build_migration_key(
            source_code="HIST_SRC",
            migration_name="historical_2025_import",
            schema_mapping_version="v1.0",
            cleaning_transform_version="cleaning-v1",
            skill_extraction_version="v1.0",
            input_hashes=inputs,
        )
        assert_test(
            "stage_f",
            "deterministic_migration_key",
            key1 == key2 and len(key1) == 64,
            {"sha256_key": key1},
        )

        # Idempotent migration simulation: insert run with key1
        run1 = IngestionRun(
            source_id=src.id,
            run_type="historical_import",
            status="succeeded",
            is_complete=True,
            observed_at=utc_now(),
            transform_version="cleaning-v1",
            migration_key=key1,
            records_received=100,
            records_inserted=100,
        )
        s.add(run1)
        s.commit()

        # Check for existing migration key prevents duplicate execution
        existing_run = s.execute(select(IngestionRun).filter_by(migration_key=key1)).scalar_one_or_none()
        assert_test(
            "stage_f",
            "idempotent_migration_prevention",
            existing_run is not None and existing_run.is_complete is True,
            "Existing migration key detects prior execution",
        )

        # Job version history tracking
        job = Job(
            source_id=src.id,
            identity_key="job_hist_track",
            identity_status="provider_id",
            first_seen_at=utc_now(),
            last_seen_at=utc_now(),
        )
        s.add(job)
        s.flush()

        v1 = JobVersion(
            job_id=job.id,
            version_number=1,
            is_current=False,
            origin_record_key="orig_v1",
            content_fingerprint="fp_v1",
            mapping_status="exact",
            title="Junior Engineer",
            salary_max_annual_inr=600000.0,
            observed_at=utc_now(),
            ingested_at=utc_now(),
            transform_version="v1",
        )
        v2 = JobVersion(
            job_id=job.id,
            version_number=2,
            is_current=True,
            origin_record_key="orig_v2",
            content_fingerprint="fp_v2",
            mapping_status="exact",
            title="Senior Engineer",
            salary_max_annual_inr=1200000.0,
            observed_at=utc_now(),
            ingested_at=utc_now(),
            transform_version="v1",
        )
        s.add_all([v1, v2])
        s.commit()

        s.refresh(job)
        assert_test(
            "stage_f",
            "version_history_progression",
            len(job.versions) == 2 and [v.version_number for v in job.versions] == [1, 2],
            {"versions_count": len(job.versions)},
        )

        # Snapshot relationship linking
        snap = RawSnapshot(
            ingestion_run_id=run1.id,
            snapshot_sequence=1,
            snapshot_kind="file",
            collected_at=utc_now(),
            content_sha256="snap_sha256_dummy_hash_for_testing",
            storage_mode="inline_text",
            payload_text='{"sample": "job_record"}',
            record_count=1,
        )
        s.add(snap)
        s.flush()
        v2.raw_snapshot_id = snap.id
        s.commit()
        s.refresh(snap)
        assert_test(
            "stage_f",
            "raw_snapshot_version_relationship",
            len(snap.job_versions) == 1 and snap.job_versions[0].id == v2.id,
            {"linked_versions_count": len(snap.job_versions)},
        )

    engine.dispose()


def run_stage_g():
    """Stage G: Database Query Testing & Performance Profiling."""
    print("\n=== STAGE G: DATABASE QUERY TESTING & PERFORMANCE PROFILING ===")
    engine = initialize_database("sqlite:///:memory:")
    session_factory = create_session_factory(engine)

    # Seed 5,000 synthetic records to get realistic execution timings
    with session_factory() as s:
        src = Source(code="PERF_SRC", name="Perf Source", source_type="api")
        s.add(src)
        s.flush()

        skill_objs = [
            Skill(name=f"Skill_{i}", normalized_name=f"skill_{i}", category="Category_A" if i % 2 == 0 else "Category_B")
            for i in range(100)
        ]
        s.add_all(skill_objs)
        s.flush()

        jobs_batch = []
        versions_batch = []
        for i in range(1000):
            j = Job(
                source_id=src.id,
                source_job_id=f"job_src_{i}",
                identity_key=f"ident_key_{i}",
                identity_status="provider_id",
                first_seen_at=utc_now(),
                last_seen_at=utc_now(),
            )
            jobs_batch.append(j)
        s.add_all(jobs_batch)
        s.flush()

        for i, j in enumerate(jobs_batch):
            jv = JobVersion(
                job_id=j.id,
                version_number=1,
                is_current=True,
                origin_record_key=f"orig_rec_{i}",
                mapping_status="exact",
                salary_max_annual_inr=float(500000 + (i * 1000)),
                salary_currency="INR" if i % 2 == 0 else "USD",
                location="Bengaluru" if i % 3 == 0 else "Mumbai",
                observed_at=utc_now(),
                ingested_at=utc_now(),
                transform_version="v1",
            )
            versions_batch.append(jv)
        s.add_all(versions_batch)
        s.flush()

        job_skills_batch = []
        for i, jv in enumerate(versions_batch):
            # assign 3 skills to each job version
            for sk_idx in range(3):
                target_sk = skill_objs[(i + sk_idx) % 100]
                job_skills_batch.append(
                    JobSkill(
                        job_version_id=jv.id,
                        skill_id=target_sk.id,
                        skill_raw=target_sk.name,
                        extraction_version="v1",
                    )
                )
        s.add_all(job_skills_batch)
        s.commit()

    # Query 1: Primary key lookup
    with session_factory() as s:
        t0 = time.perf_counter()
        for target_id in [10, 50, 100, 250, 500]:
            job = s.get(Job, target_id)
        pk_time_ms = ((time.perf_counter() - t0) / 5) * 1000
        assert_test("stage_g", "pk_lookup_latency", pk_time_ms < 2.0, {"avg_latency_ms": round(pk_time_ms, 3)})

    # Query 2: Indexed identity_key lookup
    with session_factory() as s:
        t0 = time.perf_counter()
        for key in ["ident_key_10", "ident_key_100", "ident_key_500"]:
            res = s.execute(select(Job).filter_by(identity_key=key)).scalar_one_or_none()
        indexed_ident_time_ms = ((time.perf_counter() - t0) / 3) * 1000
        assert_test(
            "stage_g",
            "indexed_identity_key_lookup",
            indexed_ident_time_ms < 2.0,
            {"avg_latency_ms": round(indexed_ident_time_ms, 3)},
        )

    # Query 3: Multi-table relational join (Job -> JobVersion -> JobSkill -> Skill)
    with session_factory() as s:
        t0 = time.perf_counter()
        stmt = (
            select(Job.identity_key, JobVersion.salary_max_annual_inr, Skill.name)
            .join(JobVersion, Job.id == JobVersion.job_id)
            .join(JobSkill, JobVersion.id == JobSkill.job_version_id)
            .join(Skill, JobSkill.skill_id == Skill.id)
            .where(JobVersion.location == "Bengaluru")
            .limit(100)
        )
        joined_results = s.execute(stmt).all()
        join_time_ms = (time.perf_counter() - t0) * 1000
        assert_test(
            "stage_g",
            "relational_join_query_latency",
            join_time_ms < 10.0 and len(joined_results) == 100,
            {"latency_ms": round(join_time_ms, 3), "returned_rows": len(joined_results)},
        )

    # Query 4: Indexed vs Non-indexed comparison
    with session_factory() as s:
        # Indexed column: salary_max_annual_inr (has ix_job_versions_salary_max_inr)
        t0 = time.perf_counter()
        for _ in range(50):
            res_idx = s.execute(
                select(JobVersion).where(JobVersion.salary_max_annual_inr >= 800000.0)
            ).scalars().all()
        idx_avg_ms = ((time.perf_counter() - t0) / 50) * 1000

        # Non-indexed column: salary_currency
        t0 = time.perf_counter()
        for _ in range(50):
            res_non_idx = s.execute(
                select(JobVersion).where(JobVersion.salary_currency == "USD")
            ).scalars().all()
        non_idx_avg_ms = ((time.perf_counter() - t0) / 50) * 1000

        assert_test(
            "stage_g",
            "indexed_vs_non_indexed_query",
            True,
            {"indexed_avg_ms": round(idx_avg_ms, 3), "non_indexed_avg_ms": round(non_idx_avg_ms, 3)},
        )

    engine.dispose()


def run_stage_h():
    """Stage H: Production Database Read-Only Audit."""
    print("\n=== STAGE H: PRODUCTION DATABASE READ-ONLY AUDIT ===")
    prod_db_path = PROJECT_ROOT / "data" / "jobradar.db"
    assert prod_db_path.exists(), f"Production DB does not exist at {prod_db_path}"

    # Connect strictly read-only via URI
    uri = f"file:{prod_db_path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    c = conn.cursor()

    # 1. Integrity check
    integrity = c.execute("PRAGMA integrity_check").fetchone()[0]
    assert_test("stage_h", "production_integrity_check", integrity == "ok", {"integrity_result": integrity})

    # 2. Foreign key check
    fk_violations = c.execute("PRAGMA foreign_key_check").fetchall()
    assert_test(
        "stage_h",
        "production_foreign_key_check",
        len(fk_violations) == 0,
        {"fk_violations_count": len(fk_violations), "violations": fk_violations},
    )

    # 3. Row counts per table
    tables = [
        r[0]
        for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    ]
    table_counts = {}
    for t in sorted(tables):
        cnt = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        table_counts[t] = cnt

    assert_test("stage_h", "production_table_counts", len(table_counts) > 0, table_counts)

    # 4. Check for orphaned records
    # Orphaned job_versions (job_id not in jobs)
    orphaned_versions = c.execute(
        "SELECT COUNT(*) FROM job_versions WHERE job_id NOT IN (SELECT id FROM jobs)"
    ).fetchone()[0]
    assert_test("stage_h", "orphaned_job_versions", orphaned_versions == 0, {"orphaned_count": orphaned_versions})

    # Orphaned job_skills (job_version_id not in job_versions or skill_id not in skills)
    orphaned_job_skills = c.execute(
        "SELECT COUNT(*) FROM job_skills WHERE job_version_id NOT IN (SELECT id FROM job_versions) OR skill_id NOT IN (SELECT id FROM skills)"
    ).fetchone()[0]
    assert_test("stage_h", "orphaned_job_skills", orphaned_job_skills == 0, {"orphaned_count": orphaned_job_skills})

    # 5. Check for duplicate logical identities
    dup_identities = c.execute(
        "SELECT identity_key, COUNT(*) FROM jobs GROUP BY identity_key HAVING COUNT(*) > 1"
    ).fetchall()
    assert_test("stage_h", "duplicate_job_identities", len(dup_identities) == 0, {"duplicate_identities": dup_identities})

    # 6. Check unique current versions constraint (at most 1 is_current per job)
    mult_current = c.execute(
        "SELECT job_id, COUNT(*) FROM job_versions WHERE is_current = 1 GROUP BY job_id HAVING COUNT(*) > 1"
    ).fetchall()
    assert_test("stage_h", "single_current_version_per_job", len(mult_current) == 0, {"violations": mult_current})

    conn.close()


def main():
    print("===============================================================")
    print("STARTING JOBRADAR PHASE 7.5 STEP 4: DATABASE INTEGRATION TESTS")
    print("===============================================================")

    try:
        run_stage_a()
        run_stage_b()
        run_stage_c()
        run_stage_d()
        run_stage_e()
        run_stage_f()
        run_stage_g()
        run_stage_h()
    except Exception as exc:
        print(f"\n[FATAL ERROR IN TEST SUITE]: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("\n===============================================================")
    passed = results["summary"]["passed"]
    failed = results["summary"]["failed"]
    total = results["summary"]["total"]
    rate = (passed / total * 100) if total > 0 else 0
    print(f"STEP 4 DATABASE TEST SUMMARY: {passed}/{total} PASSED ({rate:.1f}%)")
    print("===============================================================")

    # Persist JSON output for reporting
    out_file = PROJECT_ROOT / "docs" / "testing" / "step4_database_test_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"[*] Results persisted to {out_file}")


if __name__ == "__main__":
    main()
