"""Command-line runner for the Hiring Momentum & Salary Premium Index."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .emerging import (
    DEFAULT_MIN_JOBS,
    DEFAULT_MIN_SALARY_SAMPLES,
    DEFAULT_RECENCY_DAYS,
    DEFAULT_WEIGHT_RECENCY,
    DEFAULT_WEIGHT_SALARY,
    compute_hiring_momentum_index,
    render_emerging_summary,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_JOBS = PROJECT_ROOT / "data" / "processed" / "cleaned_indian_job_market_2025.csv"
DEFAULT_SKILLS = PROJECT_ROOT / "data" / "processed" / "job_skills.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "processed"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute Hiring Momentum & Salary Premium Index for job skills.",
    )
    parser.add_argument("--jobs", type=Path, default=DEFAULT_JOBS, help="Cleaned jobs CSV")
    parser.add_argument("--skills", type=Path, default=DEFAULT_SKILLS, help="Job skills CSV")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output directory")
    parser.add_argument("--min-jobs", type=int, default=DEFAULT_MIN_JOBS, help="Min unique jobs threshold")
    parser.add_argument("--recent-days", type=int, default=DEFAULT_RECENCY_DAYS, help="Recent days threshold")
    parser.add_argument("--min-salaries", type=int, default=DEFAULT_MIN_SALARY_SAMPLES, help="Min salary sample count")
    parser.add_argument("--weight-recency", type=float, default=DEFAULT_WEIGHT_RECENCY, help="Recency weight (0.0 - 1.0)")
    parser.add_argument("--weight-salary", type=float, default=DEFAULT_WEIGHT_SALARY, help="Salary weight (0.0 - 1.0)")
    args = parser.parse_args()

    print(f"Loading cleaned jobs from {args.jobs} ...")
    jobs_df = pd.read_csv(args.jobs, low_memory=False)
    print(f"  {len(jobs_df):,} job rows loaded.")

    print(f"Loading extracted skills from {args.skills} ...")
    skills_df = pd.read_csv(args.skills, low_memory=False)
    print(f"  {len(skills_df):,} skill rows loaded.")

    print("Computing Hiring Momentum & Salary Premium Index ...")
    result_df = compute_hiring_momentum_index(
        jobs_df=jobs_df,
        skills_df=skills_df,
        min_job_threshold=args.min_jobs,
        recent_days_threshold=args.recent_days,
        min_salary_samples=args.min_salaries,
        weight_recency=args.weight_recency,
        weight_salary=args.weight_salary,
    )
    print(f"  {len(result_df)} skills evaluated (>= {args.min_jobs} postings).")

    args.output.mkdir(parents=True, exist_ok=True)

    # 1. Save CSV
    csv_path = args.output / "emerging_skills.csv"
    result_df.to_csv(csv_path, index=False, encoding="utf-8")
    print(f"  Written: {csv_path}")

    # 2. Save JSON for FastAPI & React dashboard
    json_path = args.output / "emerging_skills.json"
    records = result_df.to_dict(orient="records")
    json_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  Written: {json_path}")

    # 3. Save Summary Markdown Report
    summary_path = args.output / "emerging_skills_summary.md"
    summary_md = render_emerging_summary(result_df)
    summary_path.write_text(summary_md, encoding="utf-8")
    print(f"  Written: {summary_path}")

    print("\n=== Top 5 Momentum Skills ===")
    for rank, row in enumerate(result_df.head(5).itertuples(), start=1):
        sal_str = f"INR {row.median_salary:,.0f}" if row.median_salary else "N/A"
        print(f"  {rank}. {row.skill} ({row.category}): Score {row.momentum_index:.1f} | Recent {row.recent_jobs}/{row.total_jobs} ({row.recency_share:.1%}) | Median {sal_str}")


if __name__ == "__main__":
    main()
