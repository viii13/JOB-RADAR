"""Read-only inspection utilities for Excel job-market datasets."""

from __future__ import annotations

from pathlib import Path
import json
import re
from typing import Any

import pandas as pd


MAX_CATEGORY_EXAMPLES = 20
MAX_TEXT_EXAMPLES = 3

FIELD_ALIASES = {
    "job_id": {"jobid", "jobidentifier", "jobcode", "jobnumber"},
    "job_title": {"jobtitle", "jobrole", "title", "designation", "position"},
    "company": {"company", "companyname", "employer", "organization"},
    "location": {"location", "city", "state", "region", "joblocation"},
    "job_description": {"jobdescription", "description", "jobdetails", "jobsummary"},
    "skills": {"tagsandskills", "skills", "tags", "skillset", "requiredskills"},
    "posting_date": {"jobuploaded", "postingdate", "posteddate", "dateposted", "uploaddate"},
    "experience": {"experience", "experiencerequired", "experiencelevel", "yoe"},
    "salary": {"salary", "salaryrange", "compensation", "ctc"},
    "minimum_salary": {"minimumsalary", "minsalary", "salarymin"},
    "maximum_salary": {"maximumsalary", "maxsalary", "salarymax"},
    "minimum_experience": {"minimumexperience", "minexperience", "experiencemin"},
    "maximum_experience": {"maximumexperience", "maxexperience", "experiencemax"},
    "job_openings": {"jobopenings", "openings", "vacancies", "vacancy"},
    "employment_type": {"jobtype", "employmenttype", "worktype"},
    "industry": {"industry", "sector"},
    "category": {"category", "jobcategory", "functionalarea"},
}

FIELD_DESCRIPTIONS = {
    "job_id": "Identifier for a job posting; used to assess duplicate postings.",
    "job_title": "Role title advertised by the employer.",
    "company": "Employer or hiring organization name.",
    "location": "Location associated with the role.",
    "job_description": "Free-text description of duties, requirements, or role context.",
    "skills": "Tags or skills associated with the role; the future skill-demand pipeline will normalize this field.",
    "posting_date": "Date or timestamp when the posting was uploaded or published.",
    "experience": "Required candidate experience level or range.",
    "salary": "Advertised compensation or salary range.",
    "minimum_salary": "Structured lower salary bound supplied by the source dataset.",
    "maximum_salary": "Structured upper salary bound supplied by the source dataset.",
    "minimum_experience": "Structured lower experience bound supplied by the source dataset.",
    "maximum_experience": "Structured upper experience bound supplied by the source dataset.",
    "job_openings": "Number of openings advertised for the role.",
    "employment_type": "Employment arrangement, such as full-time or contract.",
    "industry": "Industry or sector associated with the role or employer.",
    "category": "Dataset-defined job category or functional area.",
}


def _normalized_name(name: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(name).lower())


def _to_builtin(value: Any) -> Any:
    """Convert pandas/numpy scalar values to values JSON can serialize."""
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def _find_important_columns(columns: list[object]) -> dict[str, str]:
    normalized_columns = {_normalized_name(column): str(column) for column in columns}
    matches: dict[str, str] = {}
    for field, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            if alias in normalized_columns:
                matches[field] = normalized_columns[alias]
                break
    return matches


def _sheet_score(columns: list[object], row_count: int) -> int:
    matches = _find_important_columns(columns)
    high_value_fields = {"job_id", "job_title", "job_description", "skills", "posting_date", "location"}
    return sum(3 if field in high_value_fields else 1 for field in matches) + int(row_count > 0)


def _sample_text(values: pd.Series) -> list[str]:
    examples: list[str] = []
    for value in values.dropna().astype(str):
        clean_value = " ".join(value.split())
        if clean_value:
            examples.append(clean_value[:500])
        if len(examples) == MAX_TEXT_EXAMPLES:
            break
    return examples


def _categorical_values(data: pd.DataFrame, important_columns: dict[str, str]) -> dict[str, list[str]]:
    fields = ("job_title", "company", "location", "experience", "employment_type", "industry", "category")
    summaries: dict[str, list[str]] = {}
    for field in fields:
        column = important_columns.get(field)
        if column is None:
            continue
        values = sorted({str(value) for value in data[column].dropna() if str(value).strip()})
        summaries[column] = values[:MAX_CATEGORY_EXAMPLES]
    return summaries


def _numeric_statistics(data: pd.DataFrame) -> dict[str, dict[str, float | None]]:
    numeric_data = data.select_dtypes(include="number")
    statistics: dict[str, dict[str, float | None]] = {}
    for column in numeric_data.columns:
        series = numeric_data[column]
        statistics[str(column)] = {
            "count": float(series.count()),
            "mean": _to_builtin(series.mean()),
            "std": _to_builtin(series.std()),
            "min": _to_builtin(series.min()),
            "median": _to_builtin(series.median()),
            "max": _to_builtin(series.max()),
        }
    return statistics


def _date_summary(data: pd.DataFrame, column: str | None) -> dict[str, Any] | None:
    if column is None:
        return None
    source = data[column]
    non_null = source.dropna()
    parsed = pd.to_datetime(non_null, errors="coerce", format="mixed")
    return {
        "column": column,
        "data_type": str(source.dtype),
        "sample_values": _sample_text(source),
        "parseable_values": int(parsed.notna().sum()),
        "non_null_values": int(non_null.shape[0]),
    }


def build_data_dictionary(data: pd.DataFrame, important_columns: dict[str, str]) -> list[dict[str, Any]]:
    """Describe important source columns without modifying their values."""
    entries: list[dict[str, Any]] = []
    for field, column in important_columns.items():
        source = data[column]
        entries.append(
            {
                "field": field,
                "column": column,
                "data_type": str(source.dtype),
                "description": FIELD_DESCRIPTIONS[field],
                "missing_values": int(source.isna().sum()),
                "unique_non_null_values": int(source.nunique(dropna=True)),
                "sample_values": _sample_text(source),
            }
        )
    return entries


def inspect_workbook(workbook_path: str | Path) -> dict[str, Any]:
    """Inspect every worksheet and return a JSON-serializable quality report.

    This function only reads the workbook. It does not alter the raw source or
    write an intermediate dataset.
    """
    path = Path(workbook_path)
    if not path.is_file():
        raise FileNotFoundError(f"Workbook was not found: {path}")
    if path.suffix.lower() not in {".xlsx", ".xlsm", ".xls"}:
        raise ValueError(f"Expected an Excel workbook, received: {path.name}")

    with pd.ExcelFile(path, engine="openpyxl") as workbook:
        sheet_data = {sheet_name: workbook.parse(sheet_name=sheet_name) for sheet_name in workbook.sheet_names}

    sheets = [
        {
            "name": name,
            "rows": int(frame.shape[0]),
            "columns": int(frame.shape[1]),
            "detected_job_fields": _find_important_columns(list(frame.columns)),
            "selection_score": _sheet_score(list(frame.columns), frame.shape[0]),
        }
        for name, frame in sheet_data.items()
    ]
    selected_sheet = max(sheets, key=lambda sheet: (sheet["selection_score"], sheet["rows"]))["name"]
    data = sheet_data[selected_sheet]
    important_columns = _find_important_columns(list(data.columns))
    job_id_column = important_columns.get("job_id")
    duplicate_job_ids = (
        int(data[job_id_column].dropna().duplicated().sum()) if job_id_column is not None else None
    )

    missing_values = {
        str(column): {"count": int(data[column].isna().sum()), "percent": round(float(data[column].isna().mean() * 100), 2)}
        for column in data.columns
    }
    quality = {
        "shape": {"rows": int(data.shape[0]), "columns": int(data.shape[1])},
        "columns": [str(column) for column in data.columns],
        "data_types": {str(column): str(dtype) for column, dtype in data.dtypes.items()},
        "missing_values": missing_values,
        "duplicate_rows": int(data.duplicated().sum()),
        "duplicate_job_ids": duplicate_job_ids,
        "categorical_values": _categorical_values(data, important_columns),
        "numeric_statistics": _numeric_statistics(data),
        "job_description_examples": _sample_text(data[important_columns["job_description"]])
        if "job_description" in important_columns
        else [],
        "tags_and_skills_examples": _sample_text(data[important_columns["skills"]])
        if "skills" in important_columns
        else [],
        "posting_date_format": _date_summary(data, important_columns.get("posting_date")),
    }
    return {
        "source_workbook": str(path),
        "sheets": sheets,
        "selected_sheet": selected_sheet,
        "important_columns": important_columns,
        "quality": quality,
        "data_dictionary": build_data_dictionary(data, important_columns),
    }


def _markdown_table(headers: list[str], rows: list[list[object]]) -> str:
    header_line = "| " + " | ".join(headers) + " |"
    divider_line = "| " + " | ".join("---" for _ in headers) + " |"
    body_lines = []
    for row in rows:
        cells = [str(cell).replace("|", "\\|").replace("\n", " ") for cell in row]
        body_lines.append("| " + " | ".join(cells) + " |")
    return "\n".join([header_line, divider_line, *body_lines])


def _markdown_list(values: list[object]) -> str:
    if not values:
        return "- None detected"
    return "\n".join(f"- {value}" for value in values)


def render_quality_report(report: dict[str, Any]) -> str:
    """Render a concise, readable companion to the machine-readable report."""
    quality = report["quality"]
    lines = [
        "# Data Quality Report",
        "",
        f"**Source workbook:** `{report['source_workbook']}`",
        f"**Selected sheet:** {report['selected_sheet']}",
        f"**Shape:** {quality['shape']['rows']:,} rows × {quality['shape']['columns']:,} columns",
        "",
        "## Workbook sheets",
        "",
        _markdown_table(
            ["Sheet", "Rows", "Columns", "Selection score", "Detected job fields"],
            [
                [
                    sheet["name"],
                    sheet["rows"],
                    sheet["columns"],
                    sheet["selection_score"],
                    ", ".join(sheet["detected_job_fields"]) or "None",
                ]
                for sheet in report["sheets"]
            ],
        ),
        "",
        "## Important columns detected",
        "",
        _markdown_table(["Pipeline field", "Workbook column"], [[field, column] for field, column in report["important_columns"].items()]),
        "",
        "## Columns, data types, and missing values",
        "",
        _markdown_table(
            ["Column", "Data type", "Missing", "Missing %"],
            [
                [column, quality["data_types"][column], details["count"], details["percent"]]
                for column, details in quality["missing_values"].items()
            ],
        ),
        "",
        "## Duplicate checks",
        "",
        f"- Duplicate full rows: {quality['duplicate_rows']:,}",
        f"- Duplicate job IDs (additional occurrences): {quality['duplicate_job_ids'] if quality['duplicate_job_ids'] is not None else 'No job-ID column detected'}",
        "",
        "## Important categorical values (up to 20 values each)",
        "",
    ]
    if quality["categorical_values"]:
        for column, values in quality["categorical_values"].items():
            lines.extend([f"### {column}", "", _markdown_list(values), ""])
    else:
        lines.extend(["No important categorical columns were detected.", ""])

    lines.extend(["## Numeric field statistics", ""])
    if quality["numeric_statistics"]:
        lines.append(
            _markdown_table(
                ["Column", "Count", "Mean", "Std", "Min", "Median", "Max"],
                [
                    [column, *[statistics[key] for key in ("count", "mean", "std", "min", "median", "max")]]
                    for column, statistics in quality["numeric_statistics"].items()
                ],
            )
        )
    else:
        lines.append("No columns were stored as numeric values in the workbook.")

    lines.extend(
        [
            "",
            "## Job description examples",
            "",
            _markdown_list(quality["job_description_examples"]),
            "",
            "## TagsAndSkills / skills examples",
            "",
            _markdown_list(quality["tags_and_skills_examples"]),
            "",
            "## Posting date / jobUploaded format",
            "",
        ]
    )
    date_summary = quality["posting_date_format"]
    if date_summary is None:
        lines.append("No posting-date or jobUploaded column was detected.")
    else:
        lines.extend(
            [
                f"- Column: {date_summary['column']}",
                f"- Stored data type: {date_summary['data_type']}",
                f"- Parseable non-null values: {date_summary['parseable_values']:,} of {date_summary['non_null_values']:,}",
                "- Example stored values:",
                _markdown_list(date_summary["sample_values"]),
            ]
        )
    return "\n".join(lines) + "\n"


def render_data_dictionary(entries: list[dict[str, Any]]) -> str:
    """Render a data dictionary for the columns relevant to later pipeline stages."""
    lines = ["# Important Column Data Dictionary", ""]
    if not entries:
        return "\n".join(lines + ["No expected job-market columns were detected.", ""])
    lines.append(
        _markdown_table(
            ["Pipeline field", "Workbook column", "Type", "Meaning", "Missing", "Unique non-null", "Examples"],
            [
                [
                    entry["field"],
                    entry["column"],
                    entry["data_type"],
                    entry["description"],
                    entry["missing_values"],
                    entry["unique_non_null_values"],
                    "; ".join(entry["sample_values"]),
                ]
                for entry in entries
            ],
        )
    )
    return "\n".join(lines) + "\n"


def write_reports(workbook_path: str | Path, output_dir: str | Path) -> dict[str, Path]:
    """Write only report artifacts for a workbook inspection."""
    report = inspect_workbook(workbook_path)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    paths = {
        "sheet_inventory": destination / "sheet_inventory.json",
        "quality_report_json": destination / "data_quality_report.json",
        "quality_report_markdown": destination / "data_quality_report.md",
        "data_dictionary": destination / "data_dictionary.md",
    }
    paths["sheet_inventory"].write_text(
        json.dumps(report["sheets"], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    paths["quality_report_json"].write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    paths["quality_report_markdown"].write_text(render_quality_report(report), encoding="utf-8")
    paths["data_dictionary"].write_text(render_data_dictionary(report["data_dictionary"]), encoding="utf-8")
    return paths
