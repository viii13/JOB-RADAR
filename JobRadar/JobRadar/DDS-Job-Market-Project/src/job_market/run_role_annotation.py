"""Generate the reproducible human annotation sample for Phase 4 Stage 1."""

from __future__ import annotations

from pathlib import Path

from .database import PROJECT_ROOT, create_database_engine, create_session_factory
from .role_annotation import generate_annotation_sample


DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "annotations" / "role_annotation_sample.csv"


def main() -> None:
    engine = create_database_engine()
    try:
        with create_session_factory(engine)() as session:
            result = generate_annotation_sample(session, DEFAULT_OUTPUT)
    finally:
        engine.dispose()
    print(f"Wrote {result.records_written} records to {result.output_path}")
    for source_code, count in result.records_by_source.items():
        print(f"{source_code}: {count}")


if __name__ == "__main__":
    main()
