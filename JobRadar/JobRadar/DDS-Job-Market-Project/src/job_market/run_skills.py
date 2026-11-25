"""Command-line entry point for Milestone 3A skill extraction."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .skills import (
    build_description_patterns,
    build_extraction_audit,
    extract_job_skills,
    load_alias_map,
    load_category_map,
    render_extraction_audit,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = PROJECT_ROOT / "data" / "processed" / "cleaned_indian_job_market_2025.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "processed"
DEFAULT_ALIASES = PROJECT_ROOT / "data" / "reference" / "skill_aliases.json"
DEFAULT_CATEGORIES = PROJECT_ROOT / "data" / "reference" / "skill_categories.json"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract and normalize skills from the cleaned job-market dataset (Milestone 3A).",
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Cleaned CSV")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output directory")
    parser.add_argument("--aliases", type=Path, default=DEFAULT_ALIASES, help="Alias map JSON")
    parser.add_argument("--categories", type=Path, default=DEFAULT_CATEGORIES, help="Category map JSON")
    args = parser.parse_args()

    print(f"Loading cleaned data from {args.input} …")
    df = pd.read_csv(args.input, low_memory=False)
    print(f"  {len(df):,} rows loaded.")

    print("Loading reference data …")
    alias_lookup = load_alias_map(args.aliases)
    category_lookup = load_category_map(args.categories)

    # Load the raw alias map for pattern building.
    alias_map_raw = json.loads(args.aliases.read_text(encoding="utf-8"))
    patterns = build_description_patterns(alias_map_raw)
    print(f"  {len(alias_lookup):,} aliases, {len(category_lookup):,} categories, {len(patterns)} description patterns.")

    print("Extracting skills …")
    skills_df = extract_job_skills(df, alias_lookup, category_lookup, patterns)
    print(f"  {len(skills_df):,} (jobId, skill) pairs extracted.")

    # Write outputs.
    args.output.mkdir(parents=True, exist_ok=True)
    skills_path = args.output / "job_skills.csv"
    skills_df.to_csv(skills_path, index=False, encoding="utf-8")
    print(f"  Written: {skills_path}")

    audit = build_extraction_audit(df, skills_df)
    audit_json_path = args.output / "skill_extraction_audit.json"
    audit_json_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  Written: {audit_json_path}")

    audit_md_path = args.output / "skill_extraction_audit.md"
    audit_md_path.write_text(render_extraction_audit(audit), encoding="utf-8")
    print(f"  Written: {audit_md_path}")

    # Quick summary.
    print()
    print("=== Quick summary ===")
    print(f"  Unique normalized skills: {audit['unique_normalized_skills']:,}")
    print(f"  Jobs with >=1 skill:       {audit['jobs_with_skills']:,}")
    print(f"  Top 5 skills by demand:")
    for i, (skill, count) in enumerate(list(audit["top_20_skills_by_demand"].items())[:5], 1):
        print(f"    {i}. {skill}: {count:,} postings")


if __name__ == "__main__":
    main()
