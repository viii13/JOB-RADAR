"""SQLite engine, session, and schema-initialization helpers for JobRadar."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Mapping

from sqlalchemy import Engine, event, create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_URL = f"sqlite:///{PROJECT_ROOT / 'data' / 'jobradar.db'}"


class Base(DeclarativeBase):
    """Base class shared by the JobRadar SQLAlchemy models."""


def build_migration_key(
    *,
    source_code: str,
    migration_name: str,
    schema_mapping_version: str,
    cleaning_transform_version: str,
    skill_extraction_version: str,
    input_hashes: Mapping[str, str],
) -> str:
    """Build a stable SHA-256 key for one idempotent historical migration.

    The source code is deliberately included so identical files registered
    under different sources cannot share a migration identity.
    """
    manifest = {
        "source_code": source_code,
        "migration_name": migration_name,
        "schema_mapping_version": schema_mapping_version,
        "cleaning_transform_version": cleaning_transform_version,
        "skill_extraction_version": skill_extraction_version,
        "input_hashes": dict(sorted(input_hashes.items())),
    }
    encoded_manifest = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded_manifest.encode("utf-8")).hexdigest()


def _enable_sqlite_foreign_keys(dbapi_connection: object, _connection_record: object) -> None:
    """Enable SQLite foreign-key checks for every new database connection."""
    cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


def create_database_engine(database_url: str | URL = DEFAULT_DATABASE_URL) -> Engine:
    """Create an engine and enforce foreign keys when the target is SQLite."""
    engine = create_engine(database_url, future=True)
    if engine.dialect.name == "sqlite":
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return a reusable session factory for the provided engine."""
    return sessionmaker(bind=engine, expire_on_commit=False)


def initialize_database(database_url: str | URL = DEFAULT_DATABASE_URL) -> Engine:
    """Create the approved database schema if it does not already exist."""
    # Importing registers every model with Base.metadata without creating data.
    from . import models  # noqa: F401

    engine = create_database_engine(database_url)
    Base.metadata.create_all(engine)
    return engine
