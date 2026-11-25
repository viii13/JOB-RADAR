"""
Salary Dataset Curator & Preprocessing Pipeline (Phase 6 Stage 6.1 & 6.2)
Extracts, cleans, standardizes, and deduplicates verified disclosed salary listings
from the cleaned Indian job market dataset without target leakage.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Established domain thresholds for domestic Indian annual salaries
MIN_SALARY_LPA_THRESHOLD = 0.60    # 60,000 INR/yr (filters out hourly/daily misparses)
MAX_SALARY_LPA_THRESHOLD = 100.00  # 1 Crore INR/yr (filters out extreme C-suite outliers)
DEFAULT_MIN_ROLE_CONFIDENCE = 0.20  # Consistent with Phase 5 benchmark extractor threshold

# The 8 Approved Technical Role Families from role_taxonomy.json & Phase 4 Classifier
APPROVED_TECHNICAL_ROLE_FAMILIES = (
    "backend_core_software_engineering",
    "frontend_full_stack_engineering",
    "qa_automation_testing",
    "cloud_devops_sre",
    "data_engineer_big_data_platform",
    "data_analyst_business_intelligence",
    "data_scientist_advanced_analytics",
    "machine_learning_ai_engineer",
)

# Consolidation mapping: combine Data Science and ML/AI under data_science_ml_ai for primary modeling
PRIMARY_ROLE_MODEL_MAPPING = {
    "data_scientist_advanced_analytics": "data_science_ml_ai",
    "machine_learning_ai_engineer": "data_science_ml_ai",
}

# Project paths
_MODULE_DIR = Path(__file__).resolve().parent
_PHASE6_DIR = _MODULE_DIR.parent
_PROJECT_ROOT = _PHASE6_DIR.parent.parent
_DEFAULT_CSV_PATH = _PROJECT_ROOT / "DDS-Job-Market-Project" / "data" / "processed" / "cleaned_indian_job_market_2025.csv"
_DEFAULT_SKILLS_CSV_PATH = _PROJECT_ROOT / "DDS-Job-Market-Project" / "data" / "processed" / "job_skills.csv"
_DEFAULT_ROLE_MODEL_PATH = _PROJECT_ROOT / "DDS-Job-Market-Project" / "data" / "models" / "role_classifier_baseline_v0.1.0.joblib"
_DEFAULT_TECH_CSV_PATH = _PHASE6_DIR / "data" / "curated_technical_salary_data.csv"


@dataclass(frozen=True)
class TechnicalDatasetCurationReport:
    """Summary of technical-only filtering, role consolidation, and company distributions."""
    total_raw_rows: int
    raw_disclosed_valid_rows: int
    base_curated_rows: int
    excluded_non_technical_rows: int
    excluded_low_confidence_rows: int
    final_technical_rows: int
    unique_companies_count: int
    role_distribution: dict[str, int]
    original_role_distribution: dict[str, int]
    median_midpoint_lpa: float
    mean_midpoint_lpa: float
    std_midpoint_lpa: float
    min_midpoint_lpa: float
    max_midpoint_lpa: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_raw_rows": self.total_raw_rows,
            "raw_disclosed_valid_rows": self.raw_disclosed_valid_rows,
            "base_curated_rows": self.base_curated_rows,
            "excluded_non_technical_rows": self.excluded_non_technical_rows,
            "excluded_low_confidence_rows": self.excluded_low_confidence_rows,
            "final_technical_rows": self.final_technical_rows,
            "unique_companies_count": self.unique_companies_count,
            "role_distribution": self.role_distribution,
            "original_role_distribution": self.original_role_distribution,
            "median_midpoint_lpa": round(self.median_midpoint_lpa, 3),
            "mean_midpoint_lpa": round(self.mean_midpoint_lpa, 3),
            "std_midpoint_lpa": round(self.std_midpoint_lpa, 3),
            "min_midpoint_lpa": round(self.min_midpoint_lpa, 3),
            "max_midpoint_lpa": round(self.max_midpoint_lpa, 3),
        }


@dataclass(frozen=True)
class DatasetCurationReport:
    """Summary of curation, filtering, and exclusion decisions."""
    total_raw_rows: int
    raw_disclosed_valid_rows: int
    excluded_non_inr_rows: int
    excluded_low_outlier_rows: int
    excluded_high_outlier_rows: int
    excluded_duplicate_rows: int
    final_curated_rows: int
    median_midpoint_lpa: float
    mean_midpoint_lpa: float
    std_midpoint_lpa: float
    min_midpoint_lpa: float
    max_midpoint_lpa: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_raw_rows": self.total_raw_rows,
            "raw_disclosed_valid_rows": self.raw_disclosed_valid_rows,
            "excluded_non_inr_rows": self.excluded_non_inr_rows,
            "excluded_low_outlier_rows": self.excluded_low_outlier_rows,
            "excluded_high_outlier_rows": self.excluded_high_outlier_rows,
            "excluded_duplicate_rows": self.excluded_duplicate_rows,
            "final_curated_rows": self.final_curated_rows,
            "median_midpoint_lpa": round(self.median_midpoint_lpa, 3),
            "mean_midpoint_lpa": round(self.mean_midpoint_lpa, 3),
            "std_midpoint_lpa": round(self.std_midpoint_lpa, 3),
            "min_midpoint_lpa": round(self.min_midpoint_lpa, 3),
            "max_midpoint_lpa": round(self.max_midpoint_lpa, 3),
        }


def curate_salary_dataset(
    csv_path: str | Path | None = None,
    min_lpa: float = MIN_SALARY_LPA_THRESHOLD,
    max_lpa: float = MAX_SALARY_LPA_THRESHOLD,
) -> tuple[pd.DataFrame, DatasetCurationReport]:
    """
    Curate and standardize verified salary listings.
    
    Processing Steps:
    1. Filter strictly for `salary_status == 'valid'` (no synthetic/imputed targets).
    2. Filter currency for domestic INR (exclude 20 ambiguous USD records).
    3. Ensure minimumSalary_clean <= maximumSalary_clean.
    4. Compute midpoint annual salary in INR and LPA.
    5. Exclude sub-minimum wage daily/hourly noise (< min_lpa).
    6. Exclude extreme executive/C-suite outliers (> max_lpa).
    7. Deduplicate identical listings on core attributes to prevent train/test leakage.
    8. Calculate midpoint experience in years.
    """
    source_file = Path(csv_path) if csv_path else _DEFAULT_CSV_PATH
    if not source_file.is_file():
        raise FileNotFoundError(f"Source dataset not found at: {source_file}")

    df_raw = pd.read_csv(source_file, low_memory=False)
    total_raw_rows = len(df_raw)

    # 1. Strictly disclosed valid salaries
    valid_mask = df_raw["salary_status"] == "valid"
    df_valid = df_raw[valid_mask].copy()
    raw_disclosed_valid_rows = len(df_valid)

    # 2. Exclude non-INR currency
    inr_mask = df_valid["currency"].str.upper() == "INR"
    excluded_non_inr_rows = int((~inr_mask).sum())
    df_inr = df_valid[inr_mask].copy()

    # 3. Compute salary figures in LPA
    df_inr["salary_min_lpa"] = df_inr["minimumSalary_clean"] / 100000.0
    df_inr["salary_max_lpa"] = df_inr["maximumSalary_clean"] / 100000.0
    df_inr["salary_mid_lpa"] = (df_inr["salary_min_lpa"] + df_inr["salary_max_lpa"]) / 2.0
    df_inr["salary_annual_inr"] = (df_inr["minimumSalary_clean"] + df_inr["maximumSalary_clean"]) / 2.0

    # 4. Outlier filtering
    low_mask = df_inr["salary_mid_lpa"] < min_lpa
    excluded_low_outlier_rows = int(low_mask.sum())

    high_mask = df_inr["salary_mid_lpa"] > max_lpa
    excluded_high_outlier_rows = int(high_mask.sum())

    bounds_mask = (~low_mask) & (~high_mask) & (df_inr["salary_min_lpa"] <= df_inr["salary_max_lpa"])
    df_bounded = df_inr[bounds_mask].copy()

    # 5. Deduplication to prevent cross-split leakage
    dup_cols = [
        "title_clean",
        "companyName_clean",
        "location_clean",
        "minimumExperience_clean",
        "maximumExperience_clean",
        "salary_mid_lpa",
    ]
    is_dup = df_bounded.duplicated(subset=dup_cols, keep="first")
    excluded_duplicate_rows = int(is_dup.sum())
    df_curated = df_bounded[~is_dup].copy()

    # 6. Feature normalization
    df_curated["experience_min_years"] = df_curated["minimumExperience_clean"].clip(lower=0.0, upper=30.0)
    df_curated["experience_max_years"] = df_curated["maximumExperience_clean"].clip(lower=0.0, upper=30.0)
    df_curated["experience_mid_years"] = (df_curated["experience_min_years"] + df_curated["experience_max_years"]) / 2.0
    df_curated["log_salary_lpa"] = np.log1p(df_curated["salary_mid_lpa"])

    # Build report
    final_rows = len(df_curated)
    report = DatasetCurationReport(
        total_raw_rows=total_raw_rows,
        raw_disclosed_valid_rows=raw_disclosed_valid_rows,
        excluded_non_inr_rows=excluded_non_inr_rows,
        excluded_low_outlier_rows=excluded_low_outlier_rows,
        excluded_high_outlier_rows=excluded_high_outlier_rows,
        excluded_duplicate_rows=excluded_duplicate_rows,
        final_curated_rows=final_rows,
        median_midpoint_lpa=float(df_curated["salary_mid_lpa"].median()),
        mean_midpoint_lpa=float(df_curated["salary_mid_lpa"].mean()),
        std_midpoint_lpa=float(df_curated["salary_mid_lpa"].std()),
        min_midpoint_lpa=float(df_curated["salary_mid_lpa"].min()),
        max_midpoint_lpa=float(df_curated["salary_mid_lpa"].max()),
    )

    return df_curated, report


def curate_technical_salary_dataset(
    csv_path: str | Path | None = None,
    min_lpa: float = MIN_SALARY_LPA_THRESHOLD,
    max_lpa: float = MAX_SALARY_LPA_THRESHOLD,
    min_confidence: float = DEFAULT_MIN_ROLE_CONFIDENCE,
    save_csv: bool = True,
) -> tuple[pd.DataFrame, TechnicalDatasetCurationReport]:
    """
    Curate and filter strictly for approved Phase 4 core technical career families.
    
    Processing Steps:
    1. Run baseline curation (domestic INR, valid disclosed status, 0.60-100 LPA, deduplicated).
    2. Join canonical normalized skills from job_skills.csv.
    3. Generate multi-field boosted text representation (title 3x + skills 2x + tags + desc 500c).
    4. Run Phase 4 classifier bundle to predict role family probabilities.
    5. Filter for confidence >= min_confidence (default 0.20).
    6. Exclude all non-technical (non_tech_corporate_operations), unclassified (other_unclassified),
       and techno-managerial (product_technical_project_management) roles.
    7. Retain the 8 approved technical career families and consolidate Data Science + ML/AI
       under primary model role 'data_science_ml_ai'.
    8. Check and clean companyName_clean for leak-free GroupKFold grouping.
    9. Persist the curated technical dataset to curated_technical_salary_data.csv.
    """
    df_base, base_report = curate_salary_dataset(csv_path, min_lpa, max_lpa)
    df_base["jobId"] = df_base["jobId"].astype(str)

    # Load canonical skills
    skills_file = _DEFAULT_SKILLS_CSV_PATH
    if skills_file.is_file():
        df_skills = pd.read_csv(skills_file, dtype={"jobId": str}, usecols=["jobId", "skill_normalized"])
        df_skills = df_skills.drop_duplicates(subset=["jobId", "skill_normalized"], keep="first")
        skills_series = (
            df_skills.groupby("jobId")["skill_normalized"]
            .apply(lambda s: ", ".join(s))
            .rename("skills_str")
        )
        df_merged = df_base.merge(skills_series, on="jobId", how="left")
    else:
        df_merged = df_base.copy()
        df_merged["skills_str"] = ""

    # Load Phase 4 Classifier
    backend_src = _PROJECT_ROOT / "DDS-Job-Market-Project" / "src"
    if str(backend_src) not in sys.path:
        sys.path.insert(0, str(backend_src))

    from job_market.classification import load_role_classifier, prepare_classification_text

    bundle = load_role_classifier(_DEFAULT_ROLE_MODEL_PATH)

    # Prepare boosted multi-field texts
    texts: list[str] = []
    for t, s, tags, d in zip(
        df_merged["title_clean"].fillna(""),
        df_merged["skills_str"].fillna(""),
        df_merged["tagsAndSkills_clean"].fillna(""),
        df_merged["jobDescription_clean"].fillna(""),
    ):
        s_list = [x.strip() for x in str(s).split(",") if x.strip()]
        tag_list = [x.strip() for x in str(tags).split(",") if x.strip()]
        feat = prepare_classification_text(
            title=t,
            skills=s_list,
            tags=tag_list,
            description=str(d)[:500],
        )
        texts.append(feat.combined_text)

    # Classify via Phase 4 model
    probs = bundle.pipeline.predict_proba(texts)
    classes = bundle.metadata.classes_
    max_idx = np.argmax(probs, axis=1)
    max_probs = np.max(probs, axis=1)

    df_merged["role_phase4"] = [classes[i] for i in max_idx]
    df_merged["conf_phase4"] = max_probs

    # Filter strictly for approved technical scope
    is_tech = df_merged["role_phase4"].isin(APPROVED_TECHNICAL_ROLE_FAMILIES)
    excluded_non_technical = int((~is_tech).sum())

    is_confident = df_merged["conf_phase4"] >= min_confidence
    excluded_low_conf = int((is_tech & (~is_confident)).sum())

    df_tech = df_merged[is_tech & is_confident].copy()

    # Retain original role and assign consolidated primary modeling role
    df_tech["original_role_family"] = df_tech["role_phase4"]
    df_tech["role_model"] = df_tech["role_phase4"].replace(PRIMARY_ROLE_MODEL_MAPPING)

    # Clean companyName_clean for GroupKFold: ensure no nulls
    missing_comp_mask = df_tech["companyName_clean"].isna() | (df_tech["companyName_clean"].str.strip() == "")
    if missing_comp_mask.any():
        df_tech.loc[missing_comp_mask, "companyName_clean"] = "Unknown_Company_" + df_tech.loc[missing_comp_mask, "jobId"]

    # Save to dedicated technical dataset CSV
    if save_csv:
        _DEFAULT_TECH_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
        df_tech.to_csv(_DEFAULT_TECH_CSV_PATH, index=False)
        logger.info(f"Saved {len(df_tech)} curated technical salary records to {_DEFAULT_TECH_CSV_PATH}")

    # Build technical curation report
    role_dist = df_tech["role_model"].value_counts().to_dict()
    orig_dist = df_tech["original_role_family"].value_counts().to_dict()
    unique_companies = int(df_tech["companyName_clean"].nunique())

    tech_report = TechnicalDatasetCurationReport(
        total_raw_rows=base_report.total_raw_rows,
        raw_disclosed_valid_rows=base_report.raw_disclosed_valid_rows,
        base_curated_rows=base_report.final_curated_rows,
        excluded_non_technical_rows=excluded_non_technical,
        excluded_low_confidence_rows=excluded_low_conf,
        final_technical_rows=len(df_tech),
        unique_companies_count=unique_companies,
        role_distribution=role_dist,
        original_role_distribution=orig_dist,
        median_midpoint_lpa=float(df_tech["salary_mid_lpa"].median()),
        mean_midpoint_lpa=float(df_tech["salary_mid_lpa"].mean()),
        std_midpoint_lpa=float(df_tech["salary_mid_lpa"].std()),
        min_midpoint_lpa=float(df_tech["salary_mid_lpa"].min()),
        max_midpoint_lpa=float(df_tech["salary_mid_lpa"].max()),
    )

    return df_tech, tech_report
