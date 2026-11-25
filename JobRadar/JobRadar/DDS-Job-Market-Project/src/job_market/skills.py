"""Milestone 3A — Deterministic skill extraction and normalization.

Extracts skills from two sources (tagsAndSkills, jobDescription),
normalizes them via a curated alias map, assigns categories, and
tracks provenance.  Designed as a clean baseline so that a
transformer-based semantic matcher (Milestone 3B) can be added later
without modifying this module.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd


# ---------------------------------------------------------------------------
# 1. Reference-data loaders
# ---------------------------------------------------------------------------

def load_alias_map(path: str | Path) -> dict[str, str]:
    """Return ``{lowercase_alias: canonical_name}`` from *skill_aliases.json*.

    The JSON file maps ``canonical_name -> [alias_1, alias_2, …]``.
    This function inverts it for O(1) lookup during normalization.
    """
    raw: dict[str, list[str]] = json.loads(Path(path).read_text(encoding="utf-8"))
    lookup: dict[str, str] = {}
    for canonical, aliases in raw.items():
        for alias in aliases:
            lookup[alias.casefold()] = canonical
    return lookup


def load_category_map(path: str | Path) -> dict[str, str]:
    """Return ``{canonical_name: category}`` from *skill_categories.json*."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 2. Normalization
# ---------------------------------------------------------------------------

# Canonical uppercase forms for common acronyms/symbols observed in the data.
_UPPERCASE_CANONICALS: dict[str, str] = {
    "sql": "SQL", "html": "HTML", "css": "CSS", "aws": "AWS",
    "gcp": "GCP", "erp": "ERP", "bpo": "BPO", "sap": "SAP",
    "php": "PHP", "nlp": "NLP", "rest": "REST", "soap": "SOAP",
    "j2ee": "J2EE", "tds": "TDS", "qa": "QA", "hr": "HR",
    "ci/cd": "CI/CD", "devops": "DevOps",
    "c": "C", "r": "R",
    "c++": "C++", "c#": "C#", ".net": ".NET",
    ".net core": ".NET Core", "asp.net": "ASP.NET", "ado.net": "ADO.NET",
    "react.js": "React.js", "node.js": "Node.js", "vue.js": "Vue.js",
    "mongodb": "MongoDB", "mysql": "MySQL", "postgresql": "PostgreSQL",
    "elasticsearch": "Elasticsearch", "tensorflow": "TensorFlow",
    "pytorch": "PyTorch", "autocad": "AutoCAD", "javascript": "JavaScript",
    "typescript": "TypeScript", "power bi": "Power BI",
    "sap hana": "SAP HANA", "kubernetes": "Kubernetes",
    "it": "IT", "ai": "AI",
    "microservices": "Microservices",
}


def normalize_skill(raw_skill: str, alias_lookup: dict[str, str]) -> str:
    """Normalize a single raw skill string.

    Resolution order:
    1. Exact alias match (case-insensitive) → canonical name.
    2. Known acronym/symbol match → standard casing.
    3. Unknown value → empty string (not a recognized skill).
    """
    trimmed = raw_skill.strip()
    if not trimmed:
        return ""
    key = trimmed.casefold()

    # Priority 1: alias map
    if key in alias_lookup:
        return alias_lookup[key]

    # Priority 2: known acronyms / special-character names
    if key in _UPPERCASE_CANONICALS:
        return _UPPERCASE_CANONICALS[key]

    # Unknown values are rejected rather than converted into arbitrary skills.
    return ""


# ---------------------------------------------------------------------------
# 3. Tag extraction (Source A — tagsAndSkills)
# ---------------------------------------------------------------------------

MAX_TAG_LENGTH = 80  # tokens longer than this are likely description noise


def extract_tagged_skills(
    tags_string: str | None,
    alias_lookup: dict[str, str],
) -> list[dict[str, str]]:
    """Split *tagsAndSkills_clean* and normalize each token.

    Returns a list of ``{skill_raw, skill_normalized}`` dicts,
    deduplicated by normalized name within one job posting.
    """
    if tags_string is None or (isinstance(tags_string, float) and pd.isna(tags_string)):
        return []
    if not isinstance(tags_string, str) or not tags_string.strip():
        return []

    seen: set[str] = set()
    results: list[dict[str, str]] = []
    for token in tags_string.split(", "):
        raw = token.strip()
        if not raw or len(raw) > MAX_TAG_LENGTH:
            continue
        normalized = normalize_skill(raw, alias_lookup)
        if not normalized:
            continue
        norm_key = normalized.casefold()
        if norm_key not in seen:
            seen.add(norm_key)
            results.append({"skill_raw": raw, "skill_normalized": normalized})
    return results


# ---------------------------------------------------------------------------
# 4. Description extraction (Source B — jobDescription)
# ---------------------------------------------------------------------------

# Skills that must NEVER be searched as standalone words in free text.
# Handled via _SPECIAL_DESCRIPTION_PATTERNS instead.
_DESCRIPTION_EXCLUDED: set[str] = frozenset()

# Skills requiring special (often case-sensitive or context-restricted) patterns.
_SPECIAL_DESCRIPTION_PATTERNS: dict[str, re.Pattern[str]] = {
    "C": re.compile(
        r"\bC\s+programming\b|\bC\s+language\b",
        re.IGNORECASE,
    ),
    "R": re.compile(
        r"\bR\s+programming\b|\bR\s+language\b|\bR\s+studio\b|\bRstudio\b",
        re.IGNORECASE,
    ),
    "Golang": re.compile(
        r"\bgolang\b|\bgo\s+programming\b|\bgo\s+language\b|\bgo\s+lang\b",
        re.IGNORECASE,
    ),
    # Case-sensitive: uppercase only.
    "IT": re.compile(r"\bIT\b"),
    "AI": re.compile(r"\bAI\b"),
}


def build_description_patterns(
    alias_map_raw: dict[str, list[str]],
) -> list[tuple[str, re.Pattern[str]]]:
    """Build compiled regex patterns for searching job descriptions.

    Returns ``[(canonical_name, compiled_pattern), …]``.
    Excludes ambiguous single-letter skills and applies special rules.
    """
    patterns: list[tuple[str, re.Pattern[str]]] = []

    # Add the hand-crafted special patterns first.
    for canonical, pattern in _SPECIAL_DESCRIPTION_PATTERNS.items():
        patterns.append((canonical, pattern))

    handled = set(_SPECIAL_DESCRIPTION_PATTERNS.keys()) | _DESCRIPTION_EXCLUDED

    for canonical, aliases in alias_map_raw.items():
        if canonical in handled:
            continue

        # Build alternatives from all aliases + canonical itself.
        alternatives: list[str] = []
        all_terms = list(aliases) + [canonical.casefold()]
        for alias in all_terms:
            escaped = re.escape(alias)
            # Word-boundary handling for special characters:
            #  - Leading non-word char (e.g. '.net'): no \b prefix, use as-is.
            #  - Trailing non-word char (e.g. 'c++', 'c#'): use (?!\w) instead
            #    of \b, because \b between two non-word chars doesn't match.
            starts_special = not alias[0].isalnum() and alias[0] != "_"
            ends_special = not alias[-1].isalnum() and alias[-1] != "_"
            prefix = "" if starts_special else r"\b"
            suffix = r"(?!\w)" if ends_special else r"\b"
            alternatives.append(prefix + escaped + suffix)

        combined = "|".join(sorted(set(alternatives), key=len, reverse=True))
        patterns.append((canonical, re.compile(combined, re.IGNORECASE)))

    return patterns


def extract_description_skills(
    description: str | None,
    patterns: list[tuple[str, re.Pattern[str]]],
) -> list[dict[str, str]]:
    """Search *jobDescription_clean* for skills using compiled patterns.

    Each skill is recorded **at most once** per description.
    Returns ``[{skill_raw, skill_normalized}, …]``.
    """
    if description is None or (isinstance(description, float) and pd.isna(description)):
        return []
    if not isinstance(description, str) or not description.strip():
        return []

    results: list[dict[str, str]] = []
    for canonical, pattern in patterns:
        match = pattern.search(description)
        if match:
            results.append({
                "skill_raw": match.group(0).strip(),
                "skill_normalized": canonical,
            })
    return results


def _extract_tags_for_row(row, alias_lookup):
    """Helper for apply() — extract tagged skills for one row."""
    tagged = extract_tagged_skills(row.get("tagsAndSkills_clean"), alias_lookup)
    return {entry["skill_normalized"].casefold(): entry for entry in tagged}


def extract_job_skills(
    df: pd.DataFrame,
    alias_lookup: dict[str, str],
    category_lookup: dict[str, str],
    description_patterns: list[tuple[str, re.Pattern[str]]],
) -> pd.DataFrame:
    """Extract, normalize, and deduplicate skills across all jobs.

    Returns a DataFrame with columns:
        jobId, skill_raw, skill_normalized, skill_source, skill_category

    ``skill_source`` is one of ``tagsAndSkills``, ``jobDescription``,
    or ``both``.

    This function is the **Milestone 3A baseline**.  Milestone 3B can
    later add a ``extract_semantic_skills()`` function whose output is
    merged here in the same format.
    """
    job_ids = df["jobId"].values
    tags_col = df["tagsAndSkills_clean"].values
    desc_col = df["jobDescription_clean"].values
    n = len(df)

    # --- Source A: extract tagged skills per row (vectorized via list comp) ---
    tagged_maps: list[dict[str, dict[str, str]]] = []
    for i in range(n):
        tagged = extract_tagged_skills(tags_col[i], alias_lookup)
        tagged_maps.append({
            entry["skill_normalized"].casefold(): entry for entry in tagged
        })

    # --- Source B: description matching (pattern-major loop) ---
    # For each pattern, search the entire description column at once.
    desc_maps: list[dict[str, dict[str, str]]] = [{} for _ in range(n)]

    desc_series = pd.Series(desc_col, dtype="object")
    desc_valid = desc_series.notna() & desc_series.astype(str).str.len().gt(0)

    for canonical, pattern in description_patterns:
        # Use pandas str.contains for vectorized matching.
        matches = desc_series.str.contains(pattern, na=False)
        for idx in matches[matches & desc_valid].index:
            norm_key = canonical.casefold()
            if norm_key not in desc_maps[idx]:
                # Extract the actual matched text.
                match = pattern.search(str(desc_col[idx]))
                raw_text = match.group(0).strip() if match else canonical
                desc_maps[idx][norm_key] = {
                    "skill_raw": raw_text,
                    "skill_normalized": canonical,
                }

    # --- Merge tagged + detected, assign source and category ---
    records: list[dict[str, object]] = []
    for i in range(n):
        job_id = job_ids[i]
        tagged_map = tagged_maps[i]
        detected_map = desc_maps[i]

        all_keys = set(tagged_map.keys()) | set(detected_map.keys())
        for norm_key in all_keys:
            in_tags = norm_key in tagged_map
            in_desc = norm_key in detected_map

            if in_tags and in_desc:
                source = "both"
                raw = tagged_map[norm_key]["skill_raw"]
                normalized = tagged_map[norm_key]["skill_normalized"]
            elif in_tags:
                source = "tagsAndSkills"
                raw = tagged_map[norm_key]["skill_raw"]
                normalized = tagged_map[norm_key]["skill_normalized"]
            else:
                source = "jobDescription"
                raw = detected_map[norm_key]["skill_raw"]
                normalized = detected_map[norm_key]["skill_normalized"]

            if not normalized or not str(normalized).strip():
                continue

            category = category_lookup.get(normalized, "Other")

            records.append({
                "jobId": job_id,
                "skill_raw": raw,
                "skill_normalized": normalized,
                "skill_source": source,
                "skill_category": category,
            })

    result = pd.DataFrame(
        records,
        columns=["jobId", "skill_raw", "skill_normalized", "skill_source", "skill_category"],
    )
    return result


# ---------------------------------------------------------------------------
# 6. Audit helpers
# ---------------------------------------------------------------------------

def build_extraction_audit(
    source_df: pd.DataFrame,
    skills_df: pd.DataFrame,
) -> dict[str, Any]:
    """Compute summary statistics for the extraction run."""
    source_counts = skills_df["skill_source"].value_counts(dropna=False)
    top_skills = (
        skills_df.groupby("skill_normalized")["jobId"]
        .nunique()
        .sort_values(ascending=False)
        .head(20)
    )
    category_counts = skills_df["skill_category"].value_counts(dropna=False)
    categorized = int((skills_df["skill_category"] != "Other").sum())

    return {
        "total_rows_processed": int(len(source_df)),
        "rows_with_tags": int(source_df["tagsAndSkills_clean"].notna().sum()),
        "rows_without_tags": int(source_df["tagsAndSkills_clean"].isna().sum()),
        "rows_with_description": int(source_df["jobDescription_clean"].notna().sum()),
        "rows_without_description": int(source_df["jobDescription_clean"].isna().sum()),
        "total_skill_rows": int(len(skills_df)),
        "unique_normalized_skills": int(skills_df["skill_normalized"].nunique()),
        "jobs_with_skills": int(skills_df["jobId"].nunique()),
        "skill_source_counts": {
            str(k): int(v) for k, v in source_counts.items()
        },
        "category_counts": {str(k): int(v) for k, v in category_counts.items()},
        "categorized_rows": categorized,
        "uncategorized_rows": int(len(skills_df)) - categorized,
        "top_20_skills_by_demand": {
            str(skill): int(count) for skill, count in top_skills.items()
        },
    }


def render_extraction_audit(audit: dict[str, Any]) -> str:
    """Render a human-readable extraction audit report."""
    lines = [
        "# Skill Extraction Audit Report (Milestone 3A — Deterministic Baseline)",
        "",
        "## Dataset",
        "",
        f"- Total rows processed: {audit['total_rows_processed']:,}",
        f"- Rows with tagsAndSkills: {audit['rows_with_tags']:,}",
        f"- Rows without tagsAndSkills: {audit['rows_without_tags']:,}",
        f"- Rows with jobDescription: {audit['rows_with_description']:,}",
        f"- Rows without jobDescription: {audit['rows_without_description']:,}",
        "",
        "## Extraction results",
        "",
        f"- Total (jobId, skill) pairs: {audit['total_skill_rows']:,}",
        f"- Unique normalized skills: {audit['unique_normalized_skills']:,}",
        f"- Jobs with at least one skill: {audit['jobs_with_skills']:,}",
        "",
        "## Skill source breakdown",
        "",
    ]
    for source, count in audit["skill_source_counts"].items():
        lines.append(f"- {source}: {count:,}")
    lines.extend(["", "## Category breakdown", ""])
    for category, count in audit["category_counts"].items():
        lines.append(f"- {category}: {count:,}")
    lines.append(f"- _Categorized rows_: {audit['categorized_rows']:,}")
    lines.append(f"- _Uncategorized (Other) rows_: {audit['uncategorized_rows']:,}")
    lines.extend(["", "## Top 20 skills by demand (unique job postings)", ""])
    for rank, (skill, count) in enumerate(audit["top_20_skills_by_demand"].items(), 1):
        lines.append(f"{rank:>3}. {skill}: {count:,}")
    lines.extend([
        "",
        "## Methodology",
        "",
        "- **Source A (tagsAndSkills):** comma-separated tags split, filtered (≤80 chars), normalized.",
        "- **Source B (jobDescription):** curated dictionary matched with word-boundary regex.",
        "- **Normalization:** alias map → acronym preservation → title-case fallback.",
        "- **Ambiguous skills:** C excluded from description search; R/Go restricted to contextual phrases; IT/AI case-sensitive.",
        "- **Deduplication:** one row per (jobId, skill_normalized); source='both' when found in both.",
        "",
        "## Limitations",
        "",
        "- This is a **deterministic, rule-based baseline** (Milestone 3A).",
        "- Skills not in the curated dictionary are missed in description-only detection.",
        "- Ambiguous short tokens (C, R, Go) may have residual false positives from tags.",
        "- jobUploaded provides only ~10 days of relative posting age — no historical calendar dates.",
        "- A pretrained transformer-based semantic matcher (Milestone 3B) can later complement this baseline.",
        "",
    ])
    return "\n".join(lines)
