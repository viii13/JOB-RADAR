"""Empirical Role-Skill Benchmark Extraction for Technical Careers.

Computes reproducible, evidence-based skill demand percentages and priority tiers
across JobRadar's 8 approved technical career families using observed job-market data
and Phase 4 role classifications.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd

# Centralized Product-Design Priority Thresholds
DEFAULT_CRITICAL_THRESHOLD: float = 50.0
DEFAULT_RECOMMENDED_THRESHOLD: float = 20.0
DEFAULT_MIN_CONFIDENCE_THRESHOLD: float = 0.20
DEFAULT_SUPPORT_HIGH_THRESHOLD: int = 2500
DEFAULT_SUPPORT_MODERATE_THRESHOLD: int = 1000
BENCHMARK_CALCULATION_VERSION: str = "1.1.0"
TAXONOMY_SCHEMA_REFERENCE: str = "role-taxonomy-v1"

# The 8 Approved Technical Role Families from role_taxonomy.json
# Excludes non-tech corporate operations (non_tech_corporate_operations),
# unclassified fallbacks (other_unclassified), and hybrid management (product_technical_project_management).
SUPPORTED_TECHNICAL_ROLES: dict[str, dict[str, str]] = {
    "data_scientist_advanced_analytics": {
        "role_id": "data_scientist_advanced_analytics",
        "role_name": "Data Scientist & Advanced Analytics",
        "description": "Uses statistics, experimentation, forecasting, or advanced analytical methods to answer business or research questions.",
        "frontend_filter_key": "Data Scientist",
    },
    "machine_learning_ai_engineer": {
        "role_id": "machine_learning_ai_engineer",
        "role_name": "Machine Learning & AI Engineer",
        "description": "Builds, deploys, evaluates, or operates machine-learning, AI, computer-vision, NLP, LLM, or generative-AI systems. Note: Generative AI Engineer is treated as a specialization within this family.",
        "frontend_filter_key": "Machine Learning Engineer",
    },
    "data_engineer_big_data_platform": {
        "role_id": "data_engineer_big_data_platform",
        "role_name": "Data Engineer & Big Data Platform",
        "description": "Builds data pipelines, warehouses, ETL/ELT workflows, streaming systems, or data-platform infrastructure.",
        "frontend_filter_key": "Data Engineer",
    },
    "data_analyst_business_intelligence": {
        "role_id": "data_analyst_business_intelligence",
        "role_name": "Data Analyst & Business Intelligence",
        "description": "Produces reports, dashboards, SQL analysis, metrics, and business insights without primary responsibility for advanced modeling.",
        "frontend_filter_key": "Data Analyst",
    },
    "backend_core_software_engineering": {
        "role_id": "backend_core_software_engineering",
        "role_name": "Backend & Core Software Engineering",
        "description": "Builds APIs, services, application logic, databases, integrations, or general software systems.",
        "frontend_filter_key": "Backend Developer",
    },
    "frontend_full_stack_engineering": {
        "role_id": "frontend_full_stack_engineering",
        "role_name": "Frontend & Full Stack Engineering",
        "description": "Builds user interfaces, web or mobile clients, or end-to-end applications with a meaningful frontend responsibility.",
        "frontend_filter_key": "Frontend / Full Stack",
    },
    "cloud_devops_sre": {
        "role_id": "cloud_devops_sre",
        "role_name": "Cloud, DevOps & SRE",
        "description": "Operates cloud infrastructure, CI/CD, reliability, observability, deployment, security automation, or platform operations.",
        "frontend_filter_key": "Cloud / DevOps",
    },
    "qa_automation_testing": {
        "role_id": "qa_automation_testing",
        "role_name": "QA & Automation Testing",
        "description": "Validates software quality through manual testing, test automation, performance testing, or quality engineering.",
        "frontend_filter_key": "QA / Testing",
    },
}


@dataclass(frozen=True)
class RoleSkillBenchmark:
    """Benchmark metrics for a single canonical skill within a technical role."""

    skill_name: str
    distinct_job_count: int
    demand_percentage: float  # Primary denominator: all eligible role jobs
    disclosed_job_demand_pct: float  # Secondary denominator: eligible jobs with >= 1 skill
    priority_category: str  # "CRITICAL" | "RECOMMENDED" | "ELECTIVE" based on demand_percentage


@dataclass(frozen=True)
class RoleBenchmarkSummary:
    """Consolidated benchmark profile for a single technical career family."""

    role_id: str
    role_name: str
    description: str
    eligible_job_count: int
    skill_disclosed_job_count: int
    zero_skill_job_count: int
    skill_disclosure_rate: float
    support_tier: str  # "HIGH" | "MODERATE" | "LOW"
    distinct_skills_count: int
    critical_skills_count: int
    recommended_skills_count: int
    elective_skills_count: int
    classification_source: str
    limitations: list[str]
    skills: list[RoleSkillBenchmark]


@dataclass(frozen=True)
class BenchmarkMetadata:
    """Provenance and audit metadata for generated role benchmarks."""

    generated_at: str
    calculation_version: str
    taxonomy_reference: str
    supported_roles_count: int
    total_eligible_jobs_analyzed: int
    critical_threshold_pct: float
    recommended_threshold_pct: float
    min_confidence_threshold: float
    source_datasets: list[dict[str, Any]]
    assumptions_and_limitations: list[str]


@dataclass(frozen=True)
class RoleSkillBenchmarksResult:
    """Complete container for role-skill benchmarks and execution metadata."""

    metadata: BenchmarkMetadata
    roles: dict[str, RoleBenchmarkSummary]

    def to_dict(self) -> dict[str, Any]:
        """Convert entire benchmark result to serializable dictionary."""
        return {
            "metadata": asdict(self.metadata),
            "roles": {rid: asdict(summary) for rid, summary in self.roles.items()},
        }


def assign_priority_category(
    demand_pct: float,
    critical_threshold: float = DEFAULT_CRITICAL_THRESHOLD,
    recommended_threshold: float = DEFAULT_RECOMMENDED_THRESHOLD,
) -> str:
    """Assign explainable priority category based on configurable thresholds.

    - CRITICAL: demand >= critical_threshold (default 50.0%)
    - RECOMMENDED: demand >= recommended_threshold and < critical_threshold (default 20.0% - 49.9%)
    - ELECTIVE: demand < recommended_threshold (default < 20.0%)
    """
    if demand_pct >= critical_threshold:
        return "CRITICAL"
    if demand_pct >= recommended_threshold:
        return "RECOMMENDED"
    return "ELECTIVE"


def assign_support_tier(
    eligible_job_count: int,
    high_threshold: int = DEFAULT_SUPPORT_HIGH_THRESHOLD,
    moderate_threshold: int = DEFAULT_SUPPORT_MODERATE_THRESHOLD,
) -> str:
    """Assign role support tier based on sample size thresholds.

    - HIGH: >= 2,500 eligible jobs
    - MODERATE: 1,000 - 2,499 eligible jobs
    - LOW: < 1,000 eligible jobs
    """
    if eligible_job_count >= high_threshold:
        return "HIGH"
    if eligible_job_count >= moderate_threshold:
        return "MODERATE"
    return "LOW"


def calculate_role_benchmarks(
    classified_jobs_df: pd.DataFrame,
    job_skills_df: pd.DataFrame,
    critical_threshold: float = DEFAULT_CRITICAL_THRESHOLD,
    recommended_threshold: float = DEFAULT_RECOMMENDED_THRESHOLD,
    min_confidence_threshold: float = DEFAULT_MIN_CONFIDENCE_THRESHOLD,
    support_high_threshold: int = DEFAULT_SUPPORT_HIGH_THRESHOLD,
    support_moderate_threshold: int = DEFAULT_SUPPORT_MODERATE_THRESHOLD,
    supported_roles: dict[str, dict[str, str]] | None = None,
) -> dict[str, RoleBenchmarkSummary]:
    """Calculate empirical skill demand percentages and priority tiers for supported roles.

    Deduplication and Safety Guarantees:
    - Excludes jobs where role is missing, unknown, or not in supported technical roles.
    - Excludes jobs where confidence is strictly below min_confidence_threshold (confidence >= threshold retained).
    - Deduplicates classified_jobs_df by jobId so each job is counted exactly once (preserves first occurrence).
    - Deduplicates job_skills_df by (jobId, skill_normalized) so a skill is counted
      at most once per distinct job.
    - Zero-skill jobs remain in the primary eligible_job_count denominator.
    - A secondary disclosed_job_demand_pct is calculated using skill_disclosed_job_count.
    - Does not count duplicate records as additional demand.
    - Returns deterministic results with skills sorted descending by demand percentage,
      then alphabetically by skill name.
    """
    roles_lookup = supported_roles or SUPPORTED_TECHNICAL_ROLES
    results: dict[str, RoleBenchmarkSummary] = {}

    if classified_jobs_df.empty:
        for rid, meta in roles_lookup.items():
            results[rid] = RoleBenchmarkSummary(
                role_id=rid,
                role_name=meta["role_name"],
                description=meta["description"],
                eligible_job_count=0,
                skill_disclosed_job_count=0,
                zero_skill_job_count=0,
                skill_disclosure_rate=0.0,
                support_tier="LOW",
                distinct_skills_count=0,
                critical_skills_count=0,
                recommended_skills_count=0,
                elective_skills_count=0,
                classification_source="No data provided",
                limitations=["Eligible job count is 0; benchmark cannot be computed."],
                skills=[],
            )
        return results

    # Standardize column references
    jobs = classified_jobs_df.copy()
    if "jobId" not in jobs.columns:
        raise ValueError("classified_jobs_df must contain 'jobId' column.")
    if "predicted_role" not in jobs.columns:
        raise ValueError("classified_jobs_df must contain 'predicted_role' column.")

    # Cast jobId to string and deduplicate jobs (keeping first record, order dependent)
    jobs["jobId"] = jobs["jobId"].astype(str).str.strip()
    jobs = jobs[jobs["jobId"] != ""].drop_duplicates(subset=["jobId"], keep="first")

    # Filter by confidence if confidence column exists (inclusive of threshold: >=)
    if "confidence" in jobs.columns:
        jobs = jobs[jobs["confidence"].fillna(0.0) >= min_confidence_threshold]

    # Filter to supported technical roles only
    jobs = jobs[jobs["predicted_role"].isin(roles_lookup.keys())]

    # Prepare skills DataFrame
    skills = job_skills_df.copy() if not job_skills_df.empty else pd.DataFrame(columns=["jobId", "skill_normalized"])
    if not skills.empty:
        if "jobId" not in skills.columns or "skill_normalized" not in skills.columns:
            raise ValueError("job_skills_df must contain 'jobId' and 'skill_normalized' columns.")
        skills["jobId"] = skills["jobId"].astype(str).str.strip()
        skills["skill_normalized"] = skills["skill_normalized"].astype(str).str.strip()
        # Drop empty/invalid skills
        skills = skills[
            (skills["jobId"] != "")
            & (skills["skill_normalized"] != "")
            & (skills["skill_normalized"].str.lower() != "nan")
            & (skills["skill_normalized"].str.lower() != "none")
        ]
        # Deduplicate (jobId, skill_normalized) pairs
        skills = skills.drop_duplicates(subset=["jobId", "skill_normalized"], keep="first")

    for rid, meta in sorted(roles_lookup.items()):
        role_jobs = jobs[jobs["predicted_role"] == rid]
        total_eligible_jobs = len(role_jobs)

        if total_eligible_jobs == 0:
            results[rid] = RoleBenchmarkSummary(
                role_id=rid,
                role_name=meta["role_name"],
                description=meta["description"],
                eligible_job_count=0,
                skill_disclosed_job_count=0,
                zero_skill_job_count=0,
                skill_disclosure_rate=0.0,
                support_tier="LOW",
                distinct_skills_count=0,
                critical_skills_count=0,
                recommended_skills_count=0,
                elective_skills_count=0,
                classification_source="Phase 4 provisional classifier (confidence >= 0.20)",
                limitations=[
                    "No eligible jobs found meeting role criteria and confidence threshold in current dataset."
                ],
                skills=[],
            )
            continue

        role_job_ids = set(role_jobs["jobId"])
        role_skills = skills[skills["jobId"].isin(role_job_ids)]

        # Calculate skill coverage metrics
        skill_disclosed_job_ids = set(role_skills["jobId"].unique()) if not role_skills.empty else set()
        skill_disclosed_count = len(skill_disclosed_job_ids)
        zero_skill_count = total_eligible_jobs - skill_disclosed_count
        disclosure_rate = round((skill_disclosed_count / total_eligible_jobs) * 100.0, 2)
        role_support_tier = assign_support_tier(
            total_eligible_jobs,
            high_threshold=support_high_threshold,
            moderate_threshold=support_moderate_threshold,
        )

        benchmarks_list: list[RoleSkillBenchmark] = []
        if not role_skills.empty:
            skill_counts = (
                role_skills.groupby("skill_normalized")["jobId"]
                .nunique()
                .to_dict()
            )
            for sk_name, count in skill_counts.items():
                demand_pct = round((count / total_eligible_jobs) * 100.0, 2)
                disclosed_demand_pct = (
                    round((count / skill_disclosed_count) * 100.0, 2)
                    if skill_disclosed_count > 0
                    else 0.0
                )
                p_cat = assign_priority_category(
                    demand_pct,
                    critical_threshold=critical_threshold,
                    recommended_threshold=recommended_threshold,
                )
                benchmarks_list.append(
                    RoleSkillBenchmark(
                        skill_name=sk_name,
                        distinct_job_count=count,
                        demand_percentage=demand_pct,
                        disclosed_job_demand_pct=disclosed_demand_pct,
                        priority_category=p_cat,
                    )
                )

        # Sort deterministic: descending demand_percentage, then ascending skill_name
        benchmarks_list.sort(key=lambda x: (-x.demand_percentage, x.skill_name))

        crit_count = sum(1 for b in benchmarks_list if b.priority_category == "CRITICAL")
        rec_count = sum(1 for b in benchmarks_list if b.priority_category == "RECOMMENDED")
        elec_count = sum(1 for b in benchmarks_list if b.priority_category == "ELECTIVE")

        role_limitations = [
            f"Classified using Phase 4 provisional TF-IDF + Logistic Regression model (v0.1.0) with confidence >= {min_confidence_threshold:.2f}.",
            "Confidence threshold is an inherited heuristic filter; model outputs are uncalibrated decision scores, not frequentist probabilities or classification accuracy.",
            "Role labels are model-derived estimates based on silver training data; independent human gold benchmark validation is pending.",
            f"Primary demand percentage uses all eligible jobs (N={total_eligible_jobs}); secondary disclosed_job_demand_pct uses jobs with >= 1 skill (N={skill_disclosed_count}).",
            f"Priority tiers (CRITICAL >= {critical_threshold}%, RECOMMENDED >= {recommended_threshold}%) are product design thresholds for curriculum guidance.",
            f"Support tier is '{role_support_tier}' based on sample volume ({total_eligible_jobs} eligible jobs).",
        ]

        results[rid] = RoleBenchmarkSummary(
            role_id=rid,
            role_name=meta["role_name"],
            description=meta["description"],
            eligible_job_count=total_eligible_jobs,
            skill_disclosed_job_count=skill_disclosed_count,
            zero_skill_job_count=zero_skill_count,
            skill_disclosure_rate=disclosure_rate,
            support_tier=role_support_tier,
            distinct_skills_count=len(benchmarks_list),
            critical_skills_count=crit_count,
            recommended_skills_count=rec_count,
            elective_skills_count=elec_count,
            classification_source="Phase 4 provisional ML model (role_classifier_baseline_v0.1.0.joblib)",
            limitations=role_limitations,
            skills=benchmarks_list,
        )

    return results


def build_role_skill_benchmarks(
    processed_dir: Path | str,
    model_path: Path | str,
    critical_threshold: float = DEFAULT_CRITICAL_THRESHOLD,
    recommended_threshold: float = DEFAULT_RECOMMENDED_THRESHOLD,
    min_confidence_threshold: float = DEFAULT_MIN_CONFIDENCE_THRESHOLD,
    support_high_threshold: int = DEFAULT_SUPPORT_HIGH_THRESHOLD,
    support_moderate_threshold: int = DEFAULT_SUPPORT_MODERATE_THRESHOLD,
) -> RoleSkillBenchmarksResult:
    """End-to-end benchmark extraction from source CSV datasets and Phase 4 model bundle."""
    proc_path = Path(processed_dir)
    jobs_csv = proc_path / "cleaned_indian_job_market_2025.csv"
    skills_csv = proc_path / "job_skills.csv"

    if not jobs_csv.is_file():
        raise FileNotFoundError(f"Cleaned jobs CSV not found at: {jobs_csv}")
    if not skills_csv.is_file():
        raise FileNotFoundError(f"Job skills CSV not found at: {skills_csv}")

    # Read jobs CSV
    df_jobs = pd.read_csv(
        jobs_csv,
        dtype={"jobId": str},
        usecols=[
            "jobId",
            "title_clean",
            "tagsAndSkills_clean",
            "jobDescription_clean",
        ],
    )
    raw_jobs_count = len(df_jobs)

    # Read skills CSV
    df_skills = pd.read_csv(
        skills_csv,
        dtype={"jobId": str},
        usecols=["jobId", "skill_normalized"],
    )
    raw_skills_count = len(df_skills)

    # Deduplicate unique jobs (preserving first occurrence, documented order dependence)
    df_jobs = df_jobs.drop_duplicates(subset=["jobId"], keep="first")
    df_skills = df_skills.drop_duplicates(subset=["jobId", "skill_normalized"], keep="first")

    # Map skills per job for text preparation
    skills_series = (
        df_skills.groupby("jobId")["skill_normalized"]
        .apply(lambda s: ", ".join(s))
        .rename("skills_str")
    )
    df_merged = df_jobs.merge(skills_series, on="jobId", how="left")

    # Import Phase 4 classification tools dynamically to avoid circular dependencies
    try:
        from job_market.classification import (
            load_role_classifier,
            prepare_classification_text,
        )
    except ImportError:
        import sys
        backend_src = Path(__file__).resolve().parents[3] / "DDS-Job-Market-Project" / "src"
        if str(backend_src) not in sys.path:
            sys.path.insert(0, str(backend_src))
        from job_market.classification import (
            load_role_classifier,
            prepare_classification_text,
        )

    bundle = load_role_classifier(model_path)

    # Prepare classification texts
    texts: list[str] = []
    for t, s, tags, d in zip(
        df_merged["title_clean"].fillna(""),
        df_merged["skills_str"].fillna(""),
        df_merged["tagsAndSkills_clean"].fillna(""),
        df_merged["jobDescription_clean"].fillna(""),
    ):
        s_list = [x.strip() for x in s.split(",") if x.strip()]
        tag_list = [x.strip() for x in tags.split(",") if x.strip()]
        feat = prepare_classification_text(
            title=t,
            skills=s_list,
            tags=tag_list,
            description=d[:500],
        )
        texts.append(feat.combined_text)

    # Run vectorized batch classification
    proba_matrix = bundle.pipeline.predict_proba(texts)
    classes = bundle.metadata.classes_

    max_indices = np.argmax(proba_matrix, axis=1)
    max_probs = np.max(proba_matrix, axis=1)

    predicted_roles = [classes[i] for i in max_indices]
    df_merged["predicted_role"] = predicted_roles
    df_merged["confidence"] = max_probs

    # Calculate benchmarks
    role_benchmarks = calculate_role_benchmarks(
        classified_jobs_df=df_merged,
        job_skills_df=df_skills,
        critical_threshold=critical_threshold,
        recommended_threshold=recommended_threshold,
        min_confidence_threshold=min_confidence_threshold,
        support_high_threshold=support_high_threshold,
        support_moderate_threshold=support_moderate_threshold,
    )

    total_eligible = sum(summary.eligible_job_count for summary in role_benchmarks.values())

    metadata = BenchmarkMetadata(
        generated_at=datetime.now(UTC).isoformat(),
        calculation_version=BENCHMARK_CALCULATION_VERSION,
        taxonomy_reference=TAXONOMY_SCHEMA_REFERENCE,
        supported_roles_count=len(SUPPORTED_TECHNICAL_ROLES),
        total_eligible_jobs_analyzed=total_eligible,
        critical_threshold_pct=critical_threshold,
        recommended_threshold_pct=recommended_threshold,
        min_confidence_threshold=min_confidence_threshold,
        source_datasets=[
            {
                "file_name": jobs_csv.name,
                "raw_row_count": raw_jobs_count,
                "deduplicated_job_count": len(df_jobs),
            },
            {
                "file_name": skills_csv.name,
                "raw_row_count": raw_skills_count,
                "deduplicated_skill_pairs_count": len(df_skills),
            },
        ],
        assumptions_and_limitations=[
            "Data Source: Extracted strictly from cleaned Indian tech job postings (cleaned_indian_job_market_2025.csv).",
            "Role Classification: Roles assigned using Phase 4 provisional TF-IDF + Logistic Regression model (v0.1.0).",
            "Provisional Status: Labels are silver model-derived classifications; independent gold human verification remains pending.",
            f"Confidence Gate (0.20): Postings with model confidence < {min_confidence_threshold:.2f} are classified as uncertain and excluded from benchmarks. The 0.20 cutoff is an inherited heuristic filter from earlier 5-class experiments; in the 11-class model, it requires >= 2.2x uniform random prior (9.09%). Softmax outputs are uncalibrated decision scores and must NOT be interpreted as true probabilities or classification accuracy.",
            "Denominator Methodology: 'demand_percentage' uses all eligible role jobs as the primary denominator. 'disclosed_job_demand_pct' is provided as a secondary metric using only jobs with >= 1 extracted skill.",
            "Support Tiers: Roles are categorized as HIGH (>= 2,500 jobs), MODERATE (1,000-2,499 jobs), or LOW (< 1,000 jobs). Data Scientist (272 jobs) is explicitly flagged as LOW support.",
            "Specialization Handling: 'Generative AI Engineer' is treated as an applied specialization within 'Machine Learning & AI Engineer'.",
            "Deduplication Order Dependence: Job deduplication enforces drop_duplicates(subset=['jobId'], keep='first'). For the 3 duplicate job IDs with multi-city variants, keeping the first occurrence discards secondary location text without impacting role classification or skills.",
            "Threshold Meaning: Priority tiers (CRITICAL, RECOMMENDED, ELECTIVE) represent empirical relative demand within JobRadar, not external formal accreditations.",
        ],
    )

    return RoleSkillBenchmarksResult(metadata=metadata, roles=role_benchmarks)


def export_role_skill_benchmarks(
    benchmark_result: RoleSkillBenchmarksResult,
    output_filepath: Path | str,
) -> Path:
    """Export benchmark result to deterministic, beautifully indented JSON."""
    out_path = Path(output_filepath)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_dict = benchmark_result.to_dict()
    out_path.write_text(json.dumps(out_dict, indent=2, ensure_ascii=False), encoding="utf-8")
    return out_path.resolve()


def load_role_skill_benchmarks(
    filepath: Path | str,
) -> dict[str, Any]:
    """Load and validate benchmark JSON artifact from disk."""
    path = Path(filepath)
    if not path.is_file():
        raise FileNotFoundError(f"Benchmark artifact not found at: {path}")
    raw_data = json.loads(path.read_text(encoding="utf-8"))
    if "metadata" not in raw_data or "roles" not in raw_data:
        raise ValueError(f"Malformed benchmark JSON structure at: {path}")
    return raw_data
