"""Milestone 4 — Cross-sectional Hiring Momentum & Salary Premium Index.

Calculates an explainable momentum index across skills using 2025 dataset
characteristics: posting recency share (urgency) and salary premium ratio.
Does NOT claim longitudinal trend forecasting or future prediction.
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd


DEFAULT_MIN_JOBS: int = 30
DEFAULT_RECENCY_DAYS: int = 3
DEFAULT_MIN_SALARY_SAMPLES: int = 10
DEFAULT_WEIGHT_RECENCY: float = 0.60
DEFAULT_WEIGHT_SALARY: float = 0.40


def parse_relative_upload_days(value: object) -> int | None:
    """Parse relative posting age strings into integer days.

    Examples:
    - 'Just Now', 'Few Hours Ago', 'Today' -> 0
    - '1 Day Ago', '4 Days Ago' -> 1, 4
    - Unrelated strings ('Starts in 1 month') -> None
    """
    if value is None or pd.isna(value):
        return None
    text = str(value).strip().lower()
    if text in {"just now", "few hours ago", "today"}:
        return 0
    match = re.search(r"(\d+)\s+days?\s+ago", text)
    if match:
        return int(match.group(1))
    return None


def compute_hiring_momentum_index(
    jobs_df: pd.DataFrame,
    skills_df: pd.DataFrame,
    min_job_threshold: int = DEFAULT_MIN_JOBS,
    recent_days_threshold: int = DEFAULT_RECENCY_DAYS,
    min_salary_samples: int = DEFAULT_MIN_SALARY_SAMPLES,
    weight_recency: float = DEFAULT_WEIGHT_RECENCY,
    weight_salary: float = DEFAULT_WEIGHT_SALARY,
) -> pd.DataFrame:
    """Compute the cross-sectional Hiring Momentum & Salary Premium Index.

    Demand is strictly measured by unique jobId counts to avoid double-counting.
    Skills with insufficient salary samples rely transparently on recency share
    rather than imputed values.
    """
    if "jobId" not in jobs_df.columns or "jobId" not in skills_df.columns:
        raise ValueError("Both DataFrames must include a 'jobId' column.")

    # 1. Prepare job-level attributes
    jobs = jobs_df.copy()
    if "jobUploaded" in jobs.columns:
        days_ago = jobs["jobUploaded"].map(parse_relative_upload_days)
    else:
        days_ago = pd.Series(None, index=jobs.index, dtype="object")

    is_recent = days_ago.notna() & days_ago.le(recent_days_threshold)

    # Clean salary midpoint
    has_salary = (
        "minimumSalary_clean" in jobs.columns
        and "maximumSalary_clean" in jobs.columns
    )
    if has_salary:
        valid_sal = (
            jobs["minimumSalary_clean"].notna()
            & jobs["maximumSalary_clean"].notna()
            & jobs["minimumSalary_clean"].gt(0)
            & jobs["maximumSalary_clean"].ge(jobs["minimumSalary_clean"])
        )
        mid_salary = pd.Series(float("nan"), index=jobs.index)
        mid_salary.loc[valid_sal] = (
            jobs.loc[valid_sal, "minimumSalary_clean"]
            + jobs.loc[valid_sal, "maximumSalary_clean"]
        ) / 2.0
    else:
        mid_salary = pd.Series(float("nan"), index=jobs.index)

    min_exp = (
        jobs["minimumExperience_clean"]
        if "minimumExperience_clean" in jobs.columns
        else pd.Series(float("nan"), index=jobs.index)
    )

    job_lookup = pd.DataFrame({
        "jobId": jobs["jobId"],
        "_is_recent": is_recent,
        "_mid_salary": mid_salary,
        "_min_exp": min_exp,
    }).drop_duplicates(subset=["jobId"])

    # 2. Deduplicate (jobId, skill_normalized) to avoid multiple counts
    clean_skills = (
        skills_df.loc[skills_df["skill_normalized"].notna() & skills_df["skill_normalized"].astype(str).str.strip().ne("")]
        [["jobId", "skill_normalized", "skill_category"]]
        .drop_duplicates(subset=["jobId", "skill_normalized"])
    )

    merged = clean_skills.merge(job_lookup, on="jobId", how="inner")

    # Overall benchmark median salary
    overall_median_salary = job_lookup["_mid_salary"].dropna().median()
    if pd.isna(overall_median_salary) or overall_median_salary <= 0:
        overall_median_salary = None

    # 3. Aggregate per skill
    records: list[dict[str, Any]] = []
    for skill_name, group in merged.groupby("skill_normalized"):
        total_jobs = int(group["jobId"].nunique())
        if total_jobs < min_job_threshold:
            continue

        recent_jobs = int(group.loc[group["_is_recent"], "jobId"].nunique())
        recency_share = round(recent_jobs / total_jobs, 4) if total_jobs > 0 else 0.0

        category = str(group["skill_category"].dropna().iloc[0]) if not group["skill_category"].dropna().empty else "Other"

        valid_salaries = group["_mid_salary"].dropna()
        salary_count = int(len(valid_salaries))
        if salary_count >= min_salary_samples and overall_median_salary:
            median_salary = float(valid_salaries.median())
            salary_ratio = round(median_salary / overall_median_salary, 4)
        else:
            median_salary = None
            salary_ratio = None

        valid_exp = group["_min_exp"].dropna()
        avg_exp = round(float(valid_exp.mean()), 2) if not valid_exp.empty else None

        records.append({
            "skill": str(skill_name),
            "category": category,
            "total_jobs": total_jobs,
            "recent_jobs": recent_jobs,
            "recency_share": recency_share,
            "salary_sample_count": salary_count,
            "median_salary": median_salary,
            "salary_premium_ratio": salary_ratio,
            "avg_min_experience": avg_exp,
        })

    if not records:
        return pd.DataFrame(columns=[
            "skill", "category", "total_jobs", "recent_jobs", "recency_share",
            "recency_score", "salary_sample_count", "median_salary",
            "salary_premium_ratio", "salary_score", "avg_min_experience",
            "momentum_index", "momentum_tier"
        ])

    result = pd.DataFrame(records)

    # 4. Transparent Min-Max Normalization (0 to 100)
    # Recency normalization
    min_rec = result["recency_share"].min()
    max_rec = result["recency_share"].max()
    if max_rec > min_rec:
        result["recency_score"] = ((result["recency_share"] - min_rec) / (max_rec - min_rec) * 100).round(2)
    else:
        result["recency_score"] = 50.0

    # Salary normalization (only where sample threshold is met)
    result["salary_score"] = None
    has_ratio = result["salary_premium_ratio"].notna()
    if has_ratio.any():
        min_sal = result.loc[has_ratio, "salary_premium_ratio"].min()
        max_sal = result.loc[has_ratio, "salary_premium_ratio"].max()
        if max_sal > min_sal:
            result.loc[has_ratio, "salary_score"] = (
                (result.loc[has_ratio, "salary_premium_ratio"] - min_sal) / (max_sal - min_sal) * 100
            ).round(2)
        else:
            result.loc[has_ratio, "salary_score"] = 50.0

    # 5. Composite Momentum Index
    def calc_index(row: pd.Series) -> float:
        rec_s = float(row["recency_score"])
        sal_s = row["salary_score"]
        if sal_s is not None and not pd.isna(sal_s):
            return round(weight_recency * rec_s + weight_salary * float(sal_s), 2)
        return round(rec_s, 2)

    result["momentum_index"] = result.apply(calc_index, axis=1)

    # 6. Assign qualitative tiers
    def assign_tier(score: float) -> str:
        if score >= 70.0:
            return "High Momentum"
        if score >= 40.0:
            return "Moderate Momentum"
        return "Low / Stable"

    result["momentum_tier"] = result["momentum_index"].map(assign_tier)
    result = result.sort_values(by=["momentum_index", "total_jobs"], ascending=[False, False]).reset_index(drop=True)

    columns_order = [
        "skill", "category", "total_jobs", "recent_jobs", "recency_share",
        "recency_score", "salary_sample_count", "median_salary",
        "salary_premium_ratio", "salary_score", "avg_min_experience",
        "momentum_index", "momentum_tier"
    ]
    return result[columns_order]


def render_emerging_summary(df: pd.DataFrame, top_n: int = 20) -> str:
    """Render a concise Markdown report explaining the index and top skills."""
    top_df = df.head(top_n)
    lines = [
        "# Hiring Momentum & Salary Premium Index Report",
        "",
        "## Overview",
        "",
        "This analysis evaluates skill demand momentum using cross-sectional indicators from the 2025 dataset.",
        "**Important Methodology Note:** Because historical multi-period logs were unavailable in this dataset,",
        "this score represents a **cross-sectional hiring urgency and wage premium proxy**, NOT longitudinal trend forecasting.",
        "",
        rf"- Skills evaluated ($\ge 30$ postings): {len(df)}",
        f"- Top momentum tier: {(df['momentum_tier'] == 'High Momentum').sum()} skills",
        f"- Moderate momentum tier: {(df['momentum_tier'] == 'Moderate Momentum').sum()} skills",
        f"- Low / Stable tier: {(df['momentum_tier'] == 'Low / Stable').sum()} skills",
        "",
        f"## Top {top_n} Skills by Momentum Index",
        "",
        "| Rank | Skill | Category | Total Jobs | Recent Jobs | Recency Share | Median Salary (INR) | Salary Ratio | Momentum Index | Tier |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    for rank, row in enumerate(top_df.itertuples(), start=1):
        sal_str = f"₹{row.median_salary:,.0f}" if row.median_salary else "N/A"
        ratio_str = f"{row.salary_premium_ratio:.2f}x" if row.salary_premium_ratio else "N/A"
        lines.append(
            f"| {rank} | {row.skill} | {row.category} | {row.total_jobs:,} | {row.recent_jobs:,} | "
            f"{row.recency_share:.1%} | {sal_str} | {ratio_str} | {row.momentum_index:.1f} | {row.momentum_tier} |"
        )

    lines.extend([
        "",
        "## Methodology & Component Weights",
        "",
        "- **Demand Measurement:** Unique job postings (`nunique(jobId)`). No job's skill is double-counted.",
        r"- **Recency Share (60% weight):** Proportion of postings uploaded $\le 3$ days ago (*'Just Now'*, *'Today'*, *'1-3 Days Ago'*).",
        r"- **Salary Premium Ratio (40% weight):** Skill median midpoint salary relative to dataset benchmark (₹425,000 INR). Required $\ge 10$ salary samples.",
        "- **Missing Salary Handling:** When salary data points are insufficient (< 10), index score relies 100% on recency share without inventing fake salaries.",
        "",
        "## Limitations",
        "",
        "- Relies on relative posting tags spanning a ~10-day scrape snapshot.",
        "- Only ~34% of postings report structured salaries; salary ratios reflect disclosed packages only.",
        "- A longitudinal comparison (e.g. against a 2026 dataset) will provide true year-over-year growth velocity.",
        "",
    ])
    return "\n".join(lines)
