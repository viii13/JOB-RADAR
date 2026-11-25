"""Simple, auditable cleaning rules for the primary job-market dataset."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

import pandas as pd


REQUIRED_COLUMNS = {
    "title",
    "jobId",
    "jobUploaded",
    "companyName",
    "tagsAndSkills",
    "experience",
    "salary",
    "location",
    "jobDescription",
    "minimumSalary",
    "maximumSalary",
    "minimumExperience",
    "maximumExperience",
}


def clean_text(value: object) -> str | None:
    """Remove simple HTML and extra whitespace without changing source fields."""
    if value is None or pd.isna(value):
        return None
    text = html.unescape(str(value))
    text = re.sub(r"<\s*br\s*/?\s*>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = " ".join(text.split())
    return text or None


def clean_location(value: object) -> str | None:
    text = clean_text(value)
    if text is None:
        return None
    return re.sub(r"\s*,\s*", ", ", text)


def clean_skills(value: object) -> str | None:
    """Standardize separators and remove repeated tags within one listing."""
    text = clean_text(value)
    if text is None:
        return None
    seen: set[str] = set()
    skills: list[str] = []
    for part in re.split(r"[;,|]", text):
        skill = " ".join(part.split())
        key = skill.casefold()
        if skill and key not in seen:
            seen.add(key)
            skills.append(skill)
    return ", ".join(skills) or None


def parse_experience(value: object) -> tuple[float, float] | None:
    """Parse only clear values such as '2-4 Yrs' or '0 Yrs'."""
    text = clean_text(value)
    if text is None:
        return None
    range_match = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)\s*(?:yrs?|years?)\b",
        text,
        flags=re.IGNORECASE,
    )
    if range_match:
        return float(range_match.group(1)), float(range_match.group(2))
    single_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:yrs?|years?)\b", text, flags=re.IGNORECASE)
    if single_match:
        years = float(single_match.group(1))
        return years, years
    return None


def _status_counts(values: pd.Series) -> dict[str, int]:
    return {str(status): int(count) for status, count in values.value_counts(dropna=False).items()}


def _validate_columns(data: pd.DataFrame) -> None:
    missing_columns = sorted(REQUIRED_COLUMNS.difference(data.columns))
    if missing_columns:
        raise ValueError(f"Dataset is missing required columns: {', '.join(missing_columns)}")


def clean_job_data(data: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any], pd.DataFrame]:
    """Clean a job-postings DataFrame while preserving every original column."""
    _validate_columns(data)
    rows_before = len(data)
    original_columns = list(data.columns)

    exact_duplicate_rows = data.duplicated(keep="first")
    cleaned = data.loc[~exact_duplicate_rows].copy()

    job_id_group_size = cleaned.groupby("jobId", dropna=False)["jobId"].transform("size")
    cleaned["duplicate_jobid_conflict"] = job_id_group_size.gt(1)
    conflict_rows = cleaned.loc[cleaned["duplicate_jobid_conflict"]].copy()

    cleaned["title_clean"] = cleaned["title"].map(clean_text)
    cleaned["jobDescription_clean"] = cleaned["jobDescription"].map(clean_text)
    cleaned["jobDescription_missing"] = cleaned["jobDescription_clean"].isna()
    cleaned["tagsAndSkills_clean"] = cleaned["tagsAndSkills"].map(clean_skills)
    cleaned["tagsAndSkills_missing"] = cleaned["tagsAndSkills_clean"].isna()
    cleaned["location_clean"] = cleaned["location"].map(clean_location)
    cleaned["companyName_clean"] = cleaned["companyName"].map(clean_text)

    salary_text = cleaned["salary"].map(clean_text)
    salary_minimum = pd.to_numeric(cleaned["minimumSalary"], errors="coerce")
    salary_maximum = pd.to_numeric(cleaned["maximumSalary"], errors="coerce")
    salary_status = pd.Series("valid", index=cleaned.index, dtype="string")
    salary_status[salary_minimum.isna() | salary_maximum.isna()] = "missing_bounds"
    salary_status[salary_minimum.eq(0) & salary_maximum.eq(0)] = "zero_unknown"
    salary_status[salary_minimum.eq(0) ^ salary_maximum.eq(0)] = "incomplete_range"
    salary_status[salary_minimum.gt(salary_maximum)] = "invalid_range"
    salary_status[salary_text.str.casefold().eq("not disclosed").fillna(False)] = "not_disclosed"
    cleaned["salary_status"] = salary_status
    cleaned["salary_range_invalid"] = salary_status.isin(["incomplete_range", "invalid_range"])
    cleaned["minimumSalary_clean"] = salary_minimum.where(salary_status.eq("valid"))
    cleaned["maximumSalary_clean"] = salary_maximum.where(salary_status.eq("valid"))

    source_experience_minimum = pd.to_numeric(cleaned["minimumExperience"], errors="coerce")
    source_experience_maximum = pd.to_numeric(cleaned["maximumExperience"], errors="coerce")
    experience_status = pd.Series("missing_or_unparseable", index=cleaned.index, dtype="string")
    experience_minimum = pd.Series(float("nan"), index=cleaned.index)
    experience_maximum = pd.Series(float("nan"), index=cleaned.index)
    numeric_experience = source_experience_minimum.notna() & source_experience_maximum.notna()
    invalid_experience = numeric_experience & (
        source_experience_minimum.lt(0)
        | source_experience_maximum.lt(0)
        | source_experience_minimum.gt(source_experience_maximum)
    )
    valid_numeric_experience = numeric_experience & ~invalid_experience
    experience_status[valid_numeric_experience] = "valid_numeric"
    experience_status[invalid_experience] = "invalid_range"
    experience_minimum[valid_numeric_experience] = source_experience_minimum[valid_numeric_experience]
    experience_maximum[valid_numeric_experience] = source_experience_maximum[valid_numeric_experience]

    parsed_experience = cleaned.loc[~numeric_experience, "experience"].map(parse_experience)
    for index, parsed_range in parsed_experience.items():
        if parsed_range is not None and parsed_range[0] <= parsed_range[1]:
            experience_minimum.loc[index] = parsed_range[0]
            experience_maximum.loc[index] = parsed_range[1]
            experience_status.loc[index] = "parsed_from_text"
        elif parsed_range is not None:
            experience_status.loc[index] = "invalid_range"

    cleaned["experience_status"] = experience_status
    cleaned["experience_range_invalid"] = experience_status.eq("invalid_range")
    cleaned["minimumExperience_clean"] = experience_minimum
    cleaned["maximumExperience_clean"] = experience_maximum

    columns_added = [column for column in cleaned.columns if column not in original_columns]
    audit = {
        "rows_before_cleaning": int(rows_before),
        "rows_after_cleaning": int(len(cleaned)),
        "duplicate_rows_removed": int(exact_duplicate_rows.sum()),
        "duplicate_jobid_conflict_groups": int(conflict_rows["jobId"].nunique(dropna=False)),
        "duplicate_jobid_conflict_rows": int(len(conflict_rows)),
        "missing_values_after_cleaning": {
            "jobDescription_missing": int(cleaned["jobDescription_missing"].sum()),
            "tagsAndSkills_missing": int(cleaned["tagsAndSkills_missing"].sum()),
            "experience_source_missing": int(cleaned["experience"].isna().sum()),
        },
        "salary_status_counts": _status_counts(cleaned["salary_status"]),
        "experience_status_counts": _status_counts(cleaned["experience_status"]),
        "columns_added": columns_added,
        "important_decisions": [
            "All original source columns are preserved in the cleaned dataset.",
            "Only exact full-row duplicates are removed; conflicting jobId records are retained and flagged.",
            "Salary 0-0 and 'Not disclosed' are unavailable values, not zero salary.",
            "jobUploaded is preserved exactly; no historical dates are created from relative labels.",
        ],
    }
    return cleaned, audit, conflict_rows


def render_cleaning_audit(audit: dict[str, Any]) -> str:
    """Create a short, viva-friendly summary of the cleaning decisions."""
    lines = [
        "# Cleaning Audit Report",
        "",
        "## Row counts",
        "",
        f"- Rows before cleaning: {audit['rows_before_cleaning']:,}",
        f"- Rows after cleaning: {audit['rows_after_cleaning']:,}",
        f"- Verified exact duplicate rows removed: {audit['duplicate_rows_removed']:,}",
        "",
        "## Duplicate jobId conflicts retained",
        "",
        f"- Conflicting jobId groups: {audit['duplicate_jobid_conflict_groups']:,}",
        f"- Rows retained for review: {audit['duplicate_jobid_conflict_rows']:,}",
        "",
        "## Missing values after cleaning",
        "",
    ]
    lines.extend(f"- {field}: {count:,}" for field, count in audit["missing_values_after_cleaning"].items())
    lines.extend(["", "## Salary status counts", ""])
    lines.extend(f"- {status}: {count:,}" for status, count in audit["salary_status_counts"].items())
    lines.extend(["", "## Experience status counts", ""])
    lines.extend(f"- {status}: {count:,}" for status, count in audit["experience_status_counts"].items())
    lines.extend(["", "## Columns added", ""])
    lines.extend(f"- {column}" for column in audit["columns_added"])
    lines.extend(["", "## Important decisions", ""])
    lines.extend(f"- {decision}" for decision in audit["important_decisions"])
    return "\n".join(lines) + "\n"


def write_cleaning_outputs(
    data: pd.DataFrame, output_dir: str | Path, source_file: str | None = None
) -> dict[str, Path]:
    """Write the necessary Milestone 2 outputs without modifying source data."""
    cleaned, audit, conflict_rows = clean_job_data(data)
    if source_file is not None:
        audit["source_file"] = source_file
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    paths = {
        "cleaned_data": destination / "cleaned_indian_job_market_2025.csv",
        "duplicate_jobid_conflicts": destination / "duplicate_jobid_conflicts.csv",
        "audit_json": destination / "cleaning_audit.json",
        "audit_markdown": destination / "cleaning_audit.md",
    }
    cleaned.to_csv(paths["cleaned_data"], index=False, encoding="utf-8")
    conflict_rows.to_csv(paths["duplicate_jobid_conflicts"], index=False, encoding="utf-8")
    paths["audit_json"].write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    paths["audit_markdown"].write_text(render_cleaning_audit(audit), encoding="utf-8")
    return paths
