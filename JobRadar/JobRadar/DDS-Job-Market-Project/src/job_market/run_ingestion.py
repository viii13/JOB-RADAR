"""Command-line entry point for the Milestone 1 workbook quality check."""

from __future__ import annotations

import argparse
from pathlib import Path

from .ingestion import write_reports


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = PROJECT_ROOT / "data" / "raw" / "indian-job-market-dataset-2025.xlsx"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "processed"


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect a job-market Excel workbook without modifying it.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Path to the source .xlsx workbook")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Directory for report artifacts")
    arguments = parser.parse_args()

    reports = write_reports(arguments.input, arguments.output)
    print(f"Selected report source: {arguments.input}")
    for label, path in reports.items():
        print(f"{label}: {path}")


if __name__ == "__main__":
    main()
