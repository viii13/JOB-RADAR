"""Generate the targeted Data/AI annotation batch for Phase 4 Stage 1.1."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from .database import PROJECT_ROOT, create_database_engine, create_session_factory
from .role_annotation import (
    create_blinded_annotation_batch,
    generate_targeted_annotation_sample,
)


ANNOTATIONS_DIR = PROJECT_ROOT / "data" / "annotations"
DEFAULT_OUTPUT = ANNOTATIONS_DIR / "targeted_data_ai_role_annotation_batch.csv"
DEFAULT_BLINDED_OUTPUT = ANNOTATIONS_DIR / "targeted_data_ai_role_annotation_batch_blind.csv"
DEFAULT_REPORT = ANNOTATIONS_DIR / "targeted_data_ai_role_annotation_report.md"
ORIGINAL_SAMPLE = ANNOTATIONS_DIR / "role_annotation_sample.csv"


def file_has_human_labels(path: Path) -> bool:
    """Check if an annotation CSV exists and contains human labels or notes."""
    if not path.exists():
        return False
    try:
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                label = (row.get("human_verified_role_label") or "").strip()
                notes = (row.get("annotation_notes") or "").strip()
                if label or notes:
                    return True
    except Exception:
        return False
    return False


def validate_safe_to_overwrite(
    paths: list[Path],
    *,
    force: bool = False,
    confirm_annotated: bool = False,
) -> None:
    """Ensure existing annotation files are not overwritten without explicit flags.

    - If any file exists and ``force`` is False, raises FileExistsError.
    - If any file contains human annotations and ``confirm_annotated`` is False,
      raises PermissionError even if ``force`` is True.
    """
    existing_annotated = [p for p in paths if file_has_human_labels(p)]
    if existing_annotated and not confirm_annotated:
        filenames = ", ".join(p.name for p in existing_annotated)
        raise PermissionError(
            f"Refusing to overwrite file(s) containing human annotations: {filenames}. "
            "Explicit confirmation (--confirm-overwrite-annotated) is required to overwrite human labels."
        )

    existing_files = [p for p in paths if p.exists()]
    if existing_files and not force and not confirm_annotated:
        filenames = ", ".join(p.name for p in existing_files)
        raise FileExistsError(
            f"Target annotation file(s) already exist: {filenames}. "
            "Use --force to overwrite unannotated files."
        )


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Generate the targeted Data/AI annotation batch for Phase 4 Stage 1.1.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Path to the targeted audit annotation CSV.",
    )
    parser.add_argument(
        "--blinded-output",
        type=Path,
        default=DEFAULT_BLINDED_OUTPUT,
        help="Path to the blinded annotator CSV.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT,
        help="Path to the generation report markdown.",
    )
    parser.add_argument(
        "--original-sample",
        type=Path,
        default=ORIGINAL_SAMPLE,
        help="Path to the original 120-record sample CSV.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow overwriting existing unannotated files.",
    )
    parser.add_argument(
        "--confirm-overwrite-annotated",
        action="store_true",
        help="Explicit confirmation required to overwrite files containing human annotations.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    validate_safe_to_overwrite(
        [args.output, args.blinded_output],
        force=args.force,
        confirm_annotated=args.confirm_overwrite_annotated,
    )

    engine = create_database_engine()
    try:
        with create_session_factory(engine)() as session:
            result = generate_targeted_annotation_sample(
                session,
                args.output,
                original_sample_path=args.original_sample,
                report_path=args.report,
            )
    finally:
        engine.dispose()
    blinded_result = create_blinded_annotation_batch(args.output, args.blinded_output)
    print(f"Wrote {result.records_written} targeted records to {result.output_path}")
    print(f"Wrote {blinded_result.records_written} blinded records to {blinded_result.output_path}")
    for family, count in result.selected_by_family.items():
        print(f"{family}: {count} selected from {result.available_by_family[family]} eligible")


if __name__ == "__main__":
    main()

