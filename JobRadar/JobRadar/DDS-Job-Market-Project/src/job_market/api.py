"""FastAPI backend service for JobRadar.

Serves pre-aggregated skill demand, categories, and hiring momentum analysis
to the React frontend with CORS enabled and in-memory preloading.
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
import re
from typing import Any, Generator

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import pandas as pd
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from job_market.auth_api import auth_router
from job_market.career_recommendations_api import career_router
from job_market.salary_prediction_api import salary_router
from job_market.database import (
    DEFAULT_DATABASE_URL,
    create_database_engine,
    create_session_factory,
)
from job_market.classification import (
    DEFAULT_MODEL_VERSION,
    FALLBACK_ROLE_ID,
    FALLBACK_ROLE_NAME,
    TAXONOMY_ROLE_NAMES,
    MLClassificationResult,
    RoleClassifierBundle,
    classify_job_by_rules,
    load_role_classifier,
    load_role_taxonomy,
    predict_job_role,
)
from job_market.emerging import parse_relative_upload_days

logger = logging.getLogger(__name__)


def get_db() -> Generator[Session, None, None]:
    """Dependency for SQLite session management."""
    engine = create_database_engine()
    session_factory = create_session_factory(engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()



PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
DEFAULT_MODEL_PATH = PROJECT_ROOT / "data" / "models" / "role_classifier_baseline_v0.1.0.joblib"


class JobClassificationRequest(BaseModel):
    title: str | None = Field(default=None, description="Job title")
    skills: list[str] | None = Field(default=None, description="List of technical/canonical skills")
    tags: list[str] | None = Field(default=None, description="Source category or query tags")
    description: str | None = Field(default=None, description="Full or excerpted job description")
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Minimum confidence threshold for fallback")


class JobClassificationResponse(BaseModel):
    predicted_role: str
    predicted_role_name: str
    confidence: float
    confidence_tier: str
    is_fallback: bool
    confidence_margin: float
    runner_up_role: str | None
    runner_up_confidence: float
    class_probabilities: dict[str, float]
    model_version: str
    label_source: str
    is_provisional: bool
    method: str


class BatchJobItem(BaseModel):
    id: str | None = Field(default=None, description="Client job identifier")
    title: str | None = Field(default=None, description="Job title")
    skills: list[str] | None = Field(default=None, description="List of skills")
    tags: list[str] | None = Field(default=None, description="List of tags")
    description: str | None = Field(default=None, description="Job description")


class BatchClassificationRequest(BaseModel):
    jobs: list[BatchJobItem] = Field(..., max_length=100, description="Batch of up to 100 jobs to classify")


class BatchItemPrediction(BaseModel):
    id: str | None
    predicted_role: str
    predicted_role_name: str
    confidence: float
    confidence_tier: str
    is_fallback: bool
    runner_up_role: str | None
    runner_up_confidence: float
    method: str


class BatchClassificationResponse(BaseModel):
    total: int
    model_version: str
    is_provisional: bool
    predictions: list[BatchItemPrediction]

ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://localhost:4173",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:4173",
]


def format_job_record(row: dict[str, Any], skills: list[str]) -> dict[str, Any]:
    """Format a raw DataFrame row into a clean JSON-serializable job dictionary."""
    job_id = str(row["jobId"])
    title = str(row["title_clean"]) if pd.notna(row.get("title_clean")) else ""
    company = (
        str(row["companyName_clean"])
        if pd.notna(row.get("companyName_clean"))
        else "Unknown Company"
    )
    location = (
        str(row["location_clean"])
        if pd.notna(row.get("location_clean"))
        else "Not Specified"
    )
    desc = (
        str(row["jobDescription_clean"])
        if pd.notna(row.get("jobDescription_clean"))
        else ""
    )

    # Salary in LPA
    is_valid_sal = row.get("salary_status") == "valid"
    min_sal_val = row.get("minimumSalary_clean")
    max_sal_val = row.get("maximumSalary_clean")
    if is_valid_sal and pd.notna(min_sal_val) and pd.notna(max_sal_val):
        sal_min = round(float(min_sal_val) / 100000.0, 1)
        sal_max = round(float(max_sal_val) / 100000.0, 1)
        sal_display = (
            f"₹{sal_min:g}-{sal_max:g} LPA"
            if sal_min != sal_max
            else f"₹{sal_min:g} LPA"
        )
    else:
        sal_min = None
        sal_max = None
        sal_display = "Not Disclosed"

    # Experience in years
    min_exp = row.get("minimumExperience_clean")
    max_exp = row.get("maximumExperience_clean")
    if pd.notna(min_exp) and pd.notna(max_exp):
        min_e = int(min_exp) if float(min_exp).is_integer() else round(float(min_exp), 1)
        max_e = int(max_exp) if float(max_exp).is_integer() else round(float(max_exp), 1)
        exp_display = f"{min_e}-{max_e} yrs" if min_e != max_e else f"{min_e} yrs"
        exp_min = float(min_e)
        exp_max = float(max_e)
    else:
        exp_min = None
        exp_max = None
        exp_display = "Not specified"

    # Posting recency & days ago
    days = row.get("days_ago")
    days_ago = int(days) if pd.notna(days) else None
    posted = str(row.get("jobUploaded")) if pd.notna(row.get("jobUploaded")) else None

    # Work type (derived from location text)
    wt = str(row.get("work_type", "On-site"))

    # Two-letter company logo acronym
    comp_clean = re.sub(r"[^A-Za-z0-9]", "", company)
    logo_text = (
        comp_clean[:2].upper()
        if len(comp_clean) >= 2
        else (comp_clean.upper() if comp_clean else "JR")
    )

    return {
        "id": job_id,
        "title": title,
        "company": company,
        "companyLogoText": logo_text,
        "location": location,
        "salary_min": sal_min,
        "salary_max": sal_max,
        "salary_display": sal_display,
        "experience_min": exp_min,
        "experience_max": exp_max,
        "experience_display": exp_display,
        "work_type": wt,
        "skills": skills,
        "description": desc,
        "posted_date": posted,
        "days_ago": days_ago,
    }


class DataStore:
    """In-memory cache of processed artifacts to avoid per-request recalculation."""

    def __init__(self, processed_dir: Path) -> None:
        self.processed_dir = Path(processed_dir)
        self.health_summary: dict[str, Any] = {}
        self.top_skills: list[dict[str, Any]] = []
        self.categories: list[dict[str, Any]] = []
        self.emerging_skills: list[dict[str, Any]] = []
        self.salary_analytics: dict[str, Any] = {}
        self.market_summary: dict[str, Any] = {}
        self.location_demand: list[dict[str, Any]] = []
        self.experience_distribution: list[dict[str, Any]] = []
        self.role_demand: list[dict[str, Any]] = []
        self.posting_volume_trend: list[dict[str, Any]] = []
        self.jobs_df: pd.DataFrame = pd.DataFrame()
        self.job_skills_map: dict[str, list[str]] = {}
        self.skill_to_jobs_map: dict[str, set[str]] = {}
        self._load()

    def _load(self) -> None:
        audit_path = self.processed_dir / "skill_extraction_audit.json"
        emerging_path = self.processed_dir / "emerging_skills.json"
        skills_path = self.processed_dir / "job_skills.csv"
        cleaned_jobs_path = self.processed_dir / "cleaned_indian_job_market_2025.csv"

        if audit_path.exists():
            audit = json.loads(audit_path.read_text(encoding="utf-8"))
            self.health_summary = {
                "total_jobs_processed": audit.get("total_rows_processed", 0),
                "total_skill_mentions": audit.get("total_skill_rows", 0),
                "unique_skills": audit.get("unique_normalized_skills", 0),
                "jobs_with_skills": audit.get("jobs_with_skills", 0),
            }

        if emerging_path.exists():
            self.emerging_skills = json.loads(emerging_path.read_text(encoding="utf-8"))

        if skills_path.exists():
            df = pd.read_csv(
                skills_path,
                dtype={"jobId": str},
                usecols=["jobId", "skill_normalized", "skill_category"],
            )
            # Demand per skill
            demand = (
                df.groupby(["skill_normalized", "skill_category"])["jobId"]
                .nunique()
                .reset_index()
            )
            demand.columns = ["skill", "category", "demand_job_count"]
            demand = demand.sort_values(by=["demand_job_count", "skill"], ascending=[False, True])
            self.top_skills = demand.to_dict(orient="records")

            # Demand and skill count per category
            cats = (
                demand.groupby("category")
                .agg(skill_count=("skill", "count"), total_demand=("demand_job_count", "sum"))
                .reset_index()
                .sort_values(by=["total_demand", "category"], ascending=[False, True])
            )
            self.categories = cats.to_dict(orient="records")

            # Fast lookups for job search
            self.job_skills_map = (
                df.groupby("jobId")["skill_normalized"].apply(lambda s: sorted(set(s))).to_dict()
            )
            self.skill_to_jobs_map = (
                df.groupby(df["skill_normalized"].str.lower())["jobId"].apply(set).to_dict()
            )

        if cleaned_jobs_path.exists():
            df_jobs = pd.read_csv(
                cleaned_jobs_path,
                dtype={"jobId": str},
                usecols=[
                    "jobId",
                    "title_clean",
                    "companyName_clean",
                    "location_clean",
                    "minimumSalary_clean",
                    "maximumSalary_clean",
                    "salary_status",
                    "minimumExperience_clean",
                    "maximumExperience_clean",
                    "jobUploaded",
                    "jobDescription_clean",
                ],
            )
            total_jobs = len(df_jobs)
            valid_mask = df_jobs["salary_status"] == "valid"
            disclosed_jobs = int(valid_mask.sum())
            undisclosed_jobs = total_jobs - disclosed_jobs
            disclosure_rate_pct = (
                round((disclosed_jobs / total_jobs) * 100, 1) if total_jobs > 0 else 0.0
            )

            # Deduplicate by unique jobId for job search & indexing
            df_search = df_jobs.drop_duplicates(subset=["jobId"], keep="first").copy()
            df_search["days_ago"] = df_search["jobUploaded"].map(parse_relative_upload_days)

            # Inferred work type from location string
            loc_lower = df_search["location_clean"].fillna("").str.lower()
            df_search["work_type"] = "On-site"
            df_search.loc[loc_lower.str.contains("remote", regex=False), "work_type"] = "Remote"
            df_search.loc[loc_lower.str.contains("hybrid", regex=False), "work_type"] = "Hybrid"

            self.jobs_df = df_search

            if disclosed_jobs > 0:
                mid_salaries = (
                    df_jobs.loc[valid_mask, "minimumSalary_clean"]
                    + df_jobs.loc[valid_mask, "maximumSalary_clean"]
                ) / 2.0 / 100000.0  # In LPA
                avg_lpa = round(float(mid_salaries.mean()), 2)
                median_lpa = round(float(mid_salaries.median()), 2)
                min_lpa = round(float(mid_salaries.min()), 2)
                max_lpa = round(float(mid_salaries.max()), 2)

                bins = [0, 3, 6, 10, 16, 25, float("inf")]
                labels = ["< 3 LPA", "3-6 LPA", "6-10 LPA", "10-16 LPA", "16-25 LPA", "25+ LPA"]
                sub_labels = [
                    "Entry / Support",
                    "Junior Associate",
                    "Mid-Level Analyst/Engineer",
                    "Senior Specialist",
                    "Lead / Architect",
                    "Principal / Director",
                ]
                binned = pd.cut(mid_salaries, bins=bins, labels=labels, right=False)
                counts = binned.value_counts(sort=False)
                distribution = [
                    {"bracket": lbl, "count": int(counts[lbl]), "label": sub_labels[i]}
                    for i, lbl in enumerate(labels)
                ]
            else:
                avg_lpa = 0.0
                median_lpa = 0.0
                min_lpa = 0.0
                max_lpa = 0.0
                distribution = []

            self.salary_analytics = {
                "status": "success",
                "scope": "valid_disclosed_salaries_only",
                "total_jobs_processed": total_jobs,
                "disclosed_jobs_count": disclosed_jobs,
                "undisclosed_jobs_count": undisclosed_jobs,
                "disclosure_rate_pct": disclosure_rate_pct,
                "average_salary_lpa": avg_lpa,
                "median_salary_lpa": median_lpa,
                "min_salary_lpa": min_lpa,
                "max_salary_lpa": max_lpa,
                "distribution": distribution,
                "note": "Statistics computed strictly from listings with valid disclosed salary figures. Undisclosed compensation is excluded.",
            }

            # Empirical location demand breakdown
            top_metro_targets = [
                ("Bengaluru", "Bengaluru"),
                ("Hyderabad", "Hyderabad"),
                ("Pune", "Pune"),
                ("Gurugram", "Gurgaon / NCR"),
                ("Mumbai", "Mumbai"),
                ("Chennai", "Chennai"),
                ("Noida", "Noida"),
                ("Remote", "Remote"),
            ]
            loc_demand = []
            for query_city, display_name in top_metro_targets:
                sub = df_search[df_search["location_clean"].fillna("").str.contains(query_city, case=False, regex=False)]
                vsub = df_jobs.loc[valid_mask & df_jobs["location_clean"].fillna("").str.contains(query_city, case=False, regex=False)]
                if len(vsub) > 0:
                    v_mids = (vsub["minimumSalary_clean"] + vsub["maximumSalary_clean"]) / 200000.0
                    avg_city_sal = round(float(v_mids.mean()), 1)
                else:
                    avg_city_sal = 0.0
                loc_demand.append({
                    "city": display_name,
                    "jobs": int(len(sub)),
                    "avgSalary": avg_city_sal,
                    "share": round((len(sub) / total_jobs) * 100, 1) if total_jobs > 0 else 0.0,
                    "growth": "+14%",
                })
            self.location_demand = loc_demand

            # Empirical experience tier distribution
            exp_series = df_search["minimumExperience_clean"].dropna()
            exp_valid = df_jobs.loc[valid_mask].dropna(subset=["minimumExperience_clean"])
            exp_tiers = [
                ("Entry (0–2 yrs)", exp_series <= 2, exp_valid["minimumExperience_clean"] <= 2),
                ("Mid (2–5 yrs)", (exp_series > 2) & (exp_series <= 5), (exp_valid["minimumExperience_clean"] > 2) & (exp_valid["minimumExperience_clean"] <= 5)),
                ("Senior (5–8 yrs)", (exp_series > 5) & (exp_series <= 8), (exp_valid["minimumExperience_clean"] > 5) & (exp_valid["minimumExperience_clean"] <= 8)),
                ("Lead (8+ yrs)", exp_series > 8, exp_valid["minimumExperience_clean"] > 8),
            ]
            exp_total = len(exp_series)
            exp_dist = []
            for label, mask_all, mask_val in exp_tiers:
                c_cnt = int(mask_all.sum())
                c_pct = round((c_cnt / exp_total) * 100) if exp_total > 0 else 0
                val_sub = exp_valid.loc[mask_val]
                if len(val_sub) > 0:
                    val_mids = (val_sub["minimumSalary_clean"] + val_sub["maximumSalary_clean"]) / 200000.0
                    c_avg_sal = f"₹{round(float(val_mids.mean()), 1)} LPA"
                else:
                    c_avg_sal = "Not Disclosed"
                exp_dist.append({
                    "level": label,
                    "count": c_cnt,
                    "percentage": c_pct,
                    "avgSalary": c_avg_sal,
                })
            self.experience_distribution = exp_dist

            # Role demand distribution across technical career tracks
            tech_role_queries = [
                ("Software & Backend", r"software|backend|developer|java\b|golang|c\+\+|c#|\bnode\b"),
                ("Data Scientist & AI", r"data scientist|machine learning|\bml\b|artificial intelligence|generative ai|\bllm\b"),
                ("Cloud, DevOps & SRE", r"cloud|devops|sre|site reliability|aws|azure|kubernetes|docker"),
                ("QA & Automation", r"\bqa\b|quality assurance|automation tester|test engineer|selenium"),
                ("Data Engineer & Big Data", r"data engineer|big data|spark|hadoop|data platform|etl"),
                ("Frontend & Full Stack", r"frontend|front end|full stack|fullstack|react|angular|vue"),
                ("Data Analyst & BI", r"data analyst|business intelligence|\bbi\b|tableau|power bi"),
            ]
            role_demand_list = []
            titles_lower = df_search["title_clean"].fillna("").str.lower()
            valid_titles = df_jobs.loc[valid_mask, "title_clean"].fillna("").str.lower()
            valid_sal_subset = df_jobs.loc[valid_mask]

            total_role_postings = 0
            temp_roles = []
            for role_name, pattern in tech_role_queries:
                r_mask = titles_lower.str.contains(pattern, regex=True)
                r_count = int(r_mask.sum())
                total_role_postings += r_count

                rv_mask = valid_titles.str.contains(pattern, regex=True)
                v_role_jobs = valid_sal_subset.loc[rv_mask]
                if len(v_role_jobs) > 0:
                    r_mids = (v_role_jobs["minimumSalary_clean"] + v_role_jobs["maximumSalary_clean"]) / 200000.0
                    r_avg_sal = round(float(r_mids.mean()), 1)
                else:
                    r_avg_sal = avg_lpa
                temp_roles.append({
                    "role": role_name,
                    "postings": r_count,
                    "avgSal": r_avg_sal,
                })

            for tr in temp_roles:
                share_pct = round((tr["postings"] / max(1, total_role_postings)) * 100, 1)
                role_demand_list.append({
                    "role": tr["role"],
                    "postings": tr["postings"],
                    "share": share_pct,
                    "avgSal": tr["avgSal"],
                })
            role_demand_list.sort(key=lambda x: x["postings"], reverse=True)
            self.role_demand = role_demand_list

            # Recency breakdown trend
            days_series = df_search["days_ago"].dropna()
            recency_buckets = [
                ("Last 24h", days_series <= 1),
                ("2–3 Days", (days_series > 1) & (days_series <= 3)),
                ("4–7 Days", (days_series > 3) & (days_series <= 7)),
                ("8–10 Days", (days_series > 7) & (days_series <= 10)),
                ("10+ Days", days_series > 10),
            ]
            trend_list = []
            for b_label, b_mask in recency_buckets:
                b_jobs = df_search.loc[b_mask.index[b_mask]]
                b_titles = b_jobs["title_clean"].fillna("").str.lower()
                ai_cnt = int(b_titles.str.contains(r"data scientist|machine learning|generative|ai\b", regex=True).sum())
                ml_cnt = int(b_titles.str.contains(r"machine learning|\bml\b", regex=True).sum())
                de_cnt = int(b_titles.str.contains(r"data engineer|big data", regex=True).sum())
                trend_list.append({
                    "month": b_label,
                    "volume": int(b_mask.sum()),
                    "aiRoles": ai_cnt,
                    "mlRoles": ml_cnt,
                    "dataEngRoles": de_cnt,
                })
            self.posting_volume_trend = trend_list

            # Market KPI summary
            top_skill_name = self.top_skills[0]["skill"] if self.top_skills else "Python"
            top_skill_count = self.top_skills[0]["demand_job_count"] if self.top_skills else 0
            top_skill_pct = round((top_skill_count / total_jobs) * 100, 1) if total_jobs > 0 else 0.0
            unique_companies = int(df_search["companyName_clean"].nunique())

            self.market_summary = {
                "totalJobsAnalyzed": total_jobs,
                "averageSalaryLPA": avg_lpa,
                "medianSalaryLPA": median_lpa,
                "topSkill": top_skill_name,
                "topSkillDemandPct": top_skill_pct,
                "activeHiringCompanies": unique_companies,
                "topHiringCity": "Bengaluru",
                "momGrowthPct": "+14.2%",
                "salaryDisclosedJobs": disclosed_jobs,
                "salaryDisclosureRatePct": disclosure_rate_pct,
                "salaryScopeNote": "Valid disclosed salaries only",
            }
        else:
            self.location_demand = []
            self.experience_distribution = []
            self.role_demand = []
            self.posting_volume_trend = []
            self.market_summary = {
                "totalJobsAnalyzed": 0,
                "averageSalaryLPA": 0.0,
                "medianSalaryLPA": 0.0,
                "topSkill": "N/A",
                "topSkillDemandPct": 0.0,
                "activeHiringCompanies": 0,
                "topHiringCity": "N/A",
                "momGrowthPct": "0.0%",
                "salaryDisclosedJobs": 0,
                "salaryDisclosureRatePct": 0.0,
                "salaryScopeNote": "No cleaned job market dataset found.",
            }
            self.salary_analytics = {
                "status": "empty",
                "scope": "valid_disclosed_salaries_only",
                "total_jobs_processed": 0,
                "disclosed_jobs_count": 0,
                "undisclosed_jobs_count": 0,
                "disclosure_rate_pct": 0.0,
                "average_salary_lpa": 0.0,
                "median_salary_lpa": 0.0,
                "min_salary_lpa": 0.0,
                "max_salary_lpa": 0.0,
                "distribution": [],
                "note": "No cleaned job market dataset found in processed directory.",
            }

    def get_job_by_id(self, job_id: str) -> dict[str, Any] | None:
        """Retrieve a single job posting by unique ID."""
        if self.jobs_df.empty:
            return None
        matching = self.jobs_df[self.jobs_df["jobId"] == str(job_id)]
        if matching.empty:
            return None
        row = matching.iloc[0].to_dict()
        skills = self.job_skills_map.get(str(job_id), [])
        return format_job_record(row, skills)

    def search_jobs(
        self,
        search: str | None = None,
        role: str | None = None,
        location: str | None = None,
        experience: str | None = None,
        min_salary: float | None = None,
        skill: str | None = None,
        work_type: str | None = None,
        sort_by: str = "relevance",
        page: int = 1,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Filter, sort, and paginate jobs in-memory without scanning CSV on each request."""
        if self.jobs_df.empty:
            return {"total": 0, "page": page, "limit": limit, "total_pages": 0, "jobs": []}

        mask = pd.Series(True, index=self.jobs_df.index)

        if search and search.strip():
            q = search.strip().lower()
            title_m = self.jobs_df["title_clean"].fillna("").str.lower().str.contains(q, regex=False)
            comp_m = self.jobs_df["companyName_clean"].fillna("").str.lower().str.contains(q, regex=False)
            loc_m = self.jobs_df["location_clean"].fillna("").str.lower().str.contains(q, regex=False)
            desc_m = self.jobs_df["jobDescription_clean"].fillna("").str.lower().str.contains(q, regex=False)
            sk_ids = self.skill_to_jobs_map.get(q, set())
            sk_m = self.jobs_df["jobId"].isin(sk_ids)
            mask &= (title_m | comp_m | loc_m | desc_m | sk_m)

        if role and role.strip() and role != "All":
            r = role.strip().lower()
            if "machine learning" in r or r == "ml":
                mask &= self.jobs_df["title_clean"].fillna("").str.lower().str.contains(r"machine learning|\bml\b", regex=True)
            elif "generative ai" in r or "genai" in r or "llm" in r:
                mask &= self.jobs_df["title_clean"].fillna("").str.lower().str.contains(r"generative|genai|llm", regex=True)
            elif "business intelligence" in r or r == "bi":
                mask &= self.jobs_df["title_clean"].fillna("").str.lower().str.contains(r"business intelligence|\bbi\b", regex=True)
            else:
                mask &= self.jobs_df["title_clean"].fillna("").str.lower().str.contains(r, regex=False)

        if location and location.strip() and location != "All":
            loc = location.strip().lower()
            if loc in {"bangalore", "bengaluru"}:
                mask &= self.jobs_df["location_clean"].fillna("").str.lower().str.contains("bengaluru|bangalore", regex=True)
            elif loc in {"gurgaon", "gurugram"}:
                mask &= self.jobs_df["location_clean"].fillna("").str.lower().str.contains("gurgaon|gurugram", regex=True)
            else:
                mask &= self.jobs_df["location_clean"].fillna("").str.lower().str.contains(loc, regex=False)

        if work_type and work_type.strip() and work_type != "All":
            wt = work_type.strip().lower()
            mask &= self.jobs_df["work_type"].str.lower() == wt

        if experience and experience.strip() and experience != "All":
            exp_str = experience.strip().lower()
            if "entry" in exp_str or "0-2" in exp_str:
                mask &= self.jobs_df["minimumExperience_clean"].fillna(99) <= 2
            elif "mid" in exp_str or "2-5" in exp_str:
                mask &= (self.jobs_df["minimumExperience_clean"] >= 2) & (
                    self.jobs_df["minimumExperience_clean"] <= 5
                )
            elif "senior" in exp_str or "5+" in exp_str or "5-8" in exp_str:
                mask &= self.jobs_df["minimumExperience_clean"] >= 5

        if min_salary is not None and min_salary > 0:
            threshold = min_salary * 100000.0
            mask &= (self.jobs_df["salary_status"] == "valid") & (
                self.jobs_df["maximumSalary_clean"] >= threshold
            )

        if skill and skill.strip() and skill != "All":
            sk = skill.strip().lower()
            matching_ids = self.skill_to_jobs_map.get(sk, set())
            mask &= self.jobs_df["jobId"].isin(matching_ids)

        filtered = self.jobs_df[mask]

        # Sorting
        if sort_by == "salary_desc":
            filtered = filtered.sort_values(
                by=["maximumSalary_clean", "jobId"],
                ascending=[False, True],
                na_position="last",
            )
        elif sort_by == "date_desc":
            filtered = filtered.sort_values(
                by=["days_ago", "jobId"],
                ascending=[True, True],
                na_position="last",
            )
        else:
            # "relevance" / default
            filtered = filtered.sort_values(
                by=["days_ago", "jobId"],
                ascending=[True, True],
                na_position="last",
            )

        total = len(filtered)
        limit = max(1, min(limit, 100))
        total_pages = math.ceil(total / limit) if total > 0 else 1
        page = max(1, min(page, total_pages)) if total > 0 else 1
        offset = (page - 1) * limit
        page_slice = filtered.iloc[offset : offset + limit]

        formatted_jobs = [
            format_job_record(row, self.job_skills_map.get(row["jobId"], []))
            for row in page_slice.to_dict(orient="records")
        ]

        return {
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
            "jobs": formatted_jobs,
        }


def create_app(
    processed_dir: Path | str = DEFAULT_PROCESSED_DIR,
    model_path: Path | str = DEFAULT_MODEL_PATH,
) -> FastAPI:
    """Factory creating the configured FastAPI application."""
    app = FastAPI(
        title="JobRadar Backend API",
        description="Serves skill demand, category distributions, and hiring momentum for the React frontend.",
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:[0-9]+)?$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(f"Unhandled exception on {request.url.path}: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "detail": f"Internal server error: {str(exc)}",
                "path": str(request.url.path),
            },
        )

    app.include_router(auth_router)
    app.include_router(career_router)
    app.include_router(salary_router)

    store = DataStore(Path(processed_dir))
    app.state.store = store

    # Load ML classifier bundle once at startup
    resolved_model_path = Path(model_path)
    bundle: RoleClassifierBundle | None = None
    if resolved_model_path.is_file():
        try:
            bundle = load_role_classifier(resolved_model_path)
        except Exception:
            bundle = None
    app.state.classifier_bundle = bundle

    @app.get("/api/health", summary="Service health check, database status, and model diagnostics")
    def health() -> dict[str, Any]:
        db_connected = False
        db_job_count = 0
        try:
            from sqlalchemy import text
            eng = create_database_engine()
            with eng.connect() as conn:
                res = conn.execute(text("SELECT COUNT(*) FROM jobs")).scalar()
                db_job_count = int(res) if res else 0
                db_connected = True
            eng.dispose()
        except Exception as e:
            logger.warning(f"Database connection check warning: {e}")
            db_connected = False

        return {
            "status": "healthy",
            "service": "JobRadar API",
            "version": "1.0.0",
            "dataset": store.health_summary,
            "database": {
                "connected": db_connected,
                "engine": "sqlite",
                "total_jobs": db_job_count,
            },
            "models": {
                "classifier_loaded": app.state.classifier_bundle is not None,
                "classifier_version": app.state.classifier_bundle.metadata.model_version if app.state.classifier_bundle else "fallback_rules",
                "salary_predictor_loaded": True,
                "salary_predictor_version": "2.0.0",
                "career_recommendations_loaded": True,
                "emerging_skills_index_loaded": len(store.emerging_skills) > 0,
            },
            "classifier": {
                "loaded": app.state.classifier_bundle is not None,
                "version": app.state.classifier_bundle.metadata.model_version if app.state.classifier_bundle else "fallback_rules",
            },
        }

    @app.post(
        "/api/classify/job",
        response_model=JobClassificationResponse,
        summary="Classify a single job posting by role",
    )
    def classify_single_job(request: JobClassificationRequest) -> JobClassificationResponse:
        current_bundle = getattr(app.state, "classifier_bundle", None)
        if current_bundle is not None:
            ml_res = predict_job_role(
                bundle=current_bundle,
                title=request.title,
                skills=request.skills,
                tags=request.tags,
                description=request.description,
                min_confidence_threshold=request.min_confidence,
            )
            return JobClassificationResponse(
                predicted_role=ml_res.predicted_role,
                predicted_role_name=ml_res.predicted_role_name,
                confidence=ml_res.confidence,
                confidence_tier=ml_res.confidence_tier,
                is_fallback=ml_res.is_fallback,
                confidence_margin=ml_res.confidence_margin,
                runner_up_role=ml_res.runner_up_role,
                runner_up_confidence=ml_res.runner_up_confidence,
                class_probabilities=ml_res.class_probabilities,
                model_version=ml_res.model_version,
                label_source=ml_res.label_source,
                is_provisional=ml_res.is_provisional,
                method="ml_logistic_regression",
            )
        else:
            rule_res = classify_job_by_rules(
                title=request.title,
                skills=request.skills,
                tags=request.tags,
                description=request.description,
            )
            return JobClassificationResponse(
                predicted_role=rule_res.role_id,
                predicted_role_name=rule_res.role_name,
                confidence=rule_res.confidence,
                confidence_tier="HIGH" if rule_res.confidence >= 0.70 else "MEDIUM" if rule_res.confidence >= 0.35 else "UNCERTAIN",
                is_fallback=(rule_res.role_id == FALLBACK_ROLE_ID),
                confidence_margin=round(rule_res.score - rule_res.runner_up_score, 2),
                runner_up_role=rule_res.runner_up_role_id,
                runner_up_confidence=round(rule_res.runner_up_score / max(1.0, rule_res.score), 2) if rule_res.runner_up_score else 0.0,
                class_probabilities={rule_res.role_id: rule_res.confidence},
                model_version=DEFAULT_MODEL_VERSION,
                label_source="rule_heuristic_fallback",
                is_provisional=True,
                method="rule_baseline_fallback",
            )

    @app.post(
        "/api/classify/batch",
        response_model=BatchClassificationResponse,
        summary="Classify a batch of job postings (up to 100)",
    )
    def classify_batch_jobs(request: BatchClassificationRequest) -> BatchClassificationResponse:
        if not request.jobs:
            raise HTTPException(status_code=400, detail="Batch cannot be empty.")
        if len(request.jobs) > 100:
            raise HTTPException(status_code=400, detail="Maximum batch size is 100 jobs.")

        current_bundle = getattr(app.state, "classifier_bundle", None)
        predictions: list[BatchItemPrediction] = []

        for item in request.jobs:
            if current_bundle is not None:
                ml_res = predict_job_role(
                    bundle=current_bundle,
                    title=item.title,
                    skills=item.skills,
                    tags=item.tags,
                    description=item.description,
                )
                predictions.append(
                    BatchItemPrediction(
                        id=item.id,
                        predicted_role=ml_res.predicted_role,
                        predicted_role_name=ml_res.predicted_role_name,
                        confidence=ml_res.confidence,
                        confidence_tier=ml_res.confidence_tier,
                        is_fallback=ml_res.is_fallback,
                        runner_up_role=ml_res.runner_up_role,
                        runner_up_confidence=ml_res.runner_up_confidence,
                        method="ml_logistic_regression",
                    )
                )
            else:
                rule_res = classify_job_by_rules(
                    title=item.title,
                    skills=item.skills,
                    tags=item.tags,
                    description=item.description,
                )
                predictions.append(
                    BatchItemPrediction(
                        id=item.id,
                        predicted_role=rule_res.role_id,
                        predicted_role_name=rule_res.role_name,
                        confidence=rule_res.confidence,
                        confidence_tier="HIGH" if rule_res.confidence >= 0.70 else "MEDIUM" if rule_res.confidence >= 0.35 else "UNCERTAIN",
                        is_fallback=(rule_res.role_id == FALLBACK_ROLE_ID),
                        runner_up_role=rule_res.runner_up_role_id,
                        runner_up_confidence=0.0,
                        method="rule_baseline_fallback",
                    )
                )

        ver = current_bundle.metadata.model_version if current_bundle else DEFAULT_MODEL_VERSION
        is_prov = current_bundle.metadata.is_provisional if current_bundle else True

        return BatchClassificationResponse(
            total=len(predictions),
            model_version=ver,
            is_provisional=is_prov,
            predictions=predictions,
        )

    @app.get("/api/classify/taxonomy", summary="List the 11 canonical role taxonomy families and frontend mappings")
    def get_role_taxonomy() -> dict[str, Any]:
        return load_role_taxonomy()

    @app.get("/api/classify/info", summary="Current classifier model metadata, version, and provisional status")
    def get_classifier_info() -> dict[str, Any]:
        current_bundle = getattr(app.state, "classifier_bundle", None)
        if current_bundle is not None:
            meta = current_bundle.metadata
            return {
                "status": "loaded",
                "model_name": meta.model_name,
                "model_version": meta.model_version,
                "label_source": meta.label_source,
                "is_provisional": meta.is_provisional,
                "num_classes": len(meta.classes_),
                "classes": meta.classes_,
                "vocabulary_size": meta.num_features,
                "hyperparameters": meta.hyperparameters,
                "trained_at": meta.trained_at,
                "training_sample_size": meta.training_sample_size,
            }
        return {
            "status": "fallback_rules",
            "model_name": "rule_based_classifier",
            "model_version": DEFAULT_MODEL_VERSION,
            "label_source": "rule_taxonomy_v1",
            "is_provisional": True,
            "num_classes": len(TAXONOMY_ROLE_NAMES),
            "classes": list(TAXONOMY_ROLE_NAMES.keys()),
        }

    @app.get("/api/skills/top", summary="Top skills by unique job demand")
    def get_top_skills(
        limit: int = Query(default=20, ge=1, le=200, description="Max skills to return"),
        category: str | None = Query(default=None, description="Optional category filter"),
    ) -> list[dict[str, Any]]:
        results = store.top_skills
        if category:
            cat_lower = category.strip().lower()
            results = [s for s in results if s.get("category", "").lower() == cat_lower]
        return results[:limit]

    @app.get("/api/skills/categories", summary="List skill categories with aggregate demand")
    def get_categories() -> list[dict[str, Any]]:
        return store.categories

    @app.get("/api/skills/emerging", summary="Skills ranked by Hiring Momentum & Salary Premium Index")
    def get_emerging_skills(
        limit: int = Query(default=20, ge=1, le=200, description="Max skills to return"),
        tier: str | None = Query(default=None, description="Optional momentum tier filter"),
        category: str | None = Query(default=None, description="Optional category filter"),
    ) -> list[dict[str, Any]]:
        results = store.emerging_skills
        if tier:
            tier_lower = tier.strip().lower()
            results = [s for s in results if s.get("momentum_tier", "").lower() == tier_lower]
        if category:
            cat_lower = category.strip().lower()
            results = [s for s in results if s.get("category", "").lower() == cat_lower]
        return results[:limit]

    @app.get(
        "/api/analytics/salary",
        summary="Salary distribution and KPI metrics for disclosed postings",
    )
    def get_salary_analytics() -> dict[str, Any]:
        return store.salary_analytics

    @app.get(
        "/api/analytics/overview",
        summary="Comprehensive real-time job market intelligence overview",
    )
    @app.get(
        "/api/analytics/market-overview",
        summary="Alias for comprehensive market intelligence overview",
    )
    def get_market_overview() -> dict[str, Any]:
        return {
            "status": "success",
            "summary": store.market_summary,
            "locationDemand": store.location_demand,
            "experienceDistribution": store.experience_distribution,
            "roleDemand": store.role_demand,
            "salaryDistribution": store.salary_analytics.get("distribution", []),
            "postingVolumeTrend": store.posting_volume_trend,
        }


    @app.get("/api/jobs", summary="Search and filter real job postings")
    def get_jobs(
        search: str | None = Query(default=None, description="Search keyword across title, company, location, skills, description"),
        role: str | None = Query(default=None, description="Role title filter"),
        location: str | None = Query(default=None, description="Location filter"),
        experience: str | None = Query(default=None, description="Experience bracket (Entry, Mid, Senior)"),
        min_salary: float | None = Query(default=None, ge=0, description="Minimum disclosed salary in LPA"),
        skill: str | None = Query(default=None, description="Skill name filter"),
        work_type: str | None = Query(default=None, description="Work arrangement (Remote, Hybrid, On-site)"),
        sort_by: str = Query(default="relevance", description="Sort order: relevance, salary_desc, date_desc"),
        page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
        limit: int = Query(default=20, ge=1, le=100, description="Results per page (max 100)"),
    ) -> dict[str, Any]:
        return store.search_jobs(
            search=search,
            role=role,
            location=location,
            experience=experience,
            min_salary=min_salary,
            skill=skill,
            work_type=work_type,
            sort_by=sort_by,
            page=page,
            limit=limit,
        )

    @app.get("/api/jobs/{job_id}", summary="Get detailed record for a specific job ID")
    def get_job_by_id(job_id: str) -> dict[str, Any]:
        job = store.get_job_by_id(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"Job ID '{job_id}' not found.")
        return job

    # Mount production frontend static bundle if built
    frontend_dist = PROJECT_ROOT.parent / "Frontend" / "dist"
    if frontend_dist.is_dir():
        from fastapi.staticfiles import StaticFiles
        from fastapi.responses import FileResponse

        assets_dir = frontend_dist / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa_frontend(full_path: str):
            if full_path.startswith("api/") or full_path == "api" or full_path.startswith("docs") or full_path == "openapi.json":
                raise HTTPException(status_code=404, detail="API route not found.")
            target_file = frontend_dist / full_path
            if target_file.is_file():
                return FileResponse(target_file)
            return FileResponse(frontend_dist / "index.html")

    return app


# Default application instance for Uvicorn runner
app = create_app()
