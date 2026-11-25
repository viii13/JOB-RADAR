"""Command-line entry point for the Milestone 2 cleaning pipeline."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .cleaning import write_cleaning_outputs
from .ingestion import inspect_workbook


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = PROJECT_ROOT / "data" / "raw" / "indian-job-market-dataset-2025.xlsx"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "processed"


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean the primary job-market workbook without changing it.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Path to the source .xlsx workbook")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Directory for cleaned outputs")
    arguments = parser.parse_args()

    workbook_report = inspect_workbook(arguments.input)
    sheet_name = workbook_report["selected_sheet"]
    source_data = pd.read_excel(arguments.input, sheet_name=sheet_name, engine="openpyxl")
    outputs = write_cleaning_outputs(source_data, arguments.output, str(arguments.input))

    print(f"Cleaned sheet: {sheet_name}")
    for label, path in outputs.items():
        print(f"{label}: {path}")


if __name__ == "__main__":
    main()
