"""
Feature Engineering Transformers (Phase 6 Stage 6.3)
Scikit-learn compatible transformers for experience, geographic location tiers,
seniority level, role family mapping, and technical skill indicators.
"""

from __future__ import annotations

import re
from typing import Any
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin

# Top tech hub cities in India (Tier 1)
TIER_1_METROS = {
    "bengaluru", "bangalore", "hyderabad", "pune", "mumbai", "navi mumbai",
    "chennai", "gurugram", "gurgaon", "noida", "delhi", "new delhi", "delhi / ncr"
}

# Major emerging Tier 2 technical cities
TIER_2_CITIES = {
    "ahmedabad", "kolkata", "jaipur", "kochi", "coimbatore", "chandigarh",
    "indore", "surat", "vadodara", "bhubaneswar", "nagpur", "thiruvananthapuram",
    "trivandrum", "mysuru", "mysore", "visakhapatnam", "vizag"
}

# High-utility technical competencies tracked in JobRadar
TRACKED_TECH_SKILLS = [
    "python", "java", "sql", "aws", "docker", "kubernetes", "react",
    "machine learning", "data science", "spark", "deep learning", "pytorch",
    "tensorflow", "scikit-learn", "pandas", "fastapi", "spring boot",
    "microservices", "azure", "gcp", "ci/cd", "linux", "git", "rest",
    "mongodb", "postgresql", "kafka", "tableau", "power bi", "excel",
    "selenium", "automation testing", "node.js", "typescript", "c++", "go"
]


class LocationTierTransformer(BaseEstimator, TransformerMixin):
    """Categorizes location strings into standard macroeconomic compensation tiers."""

    def fit(self, X: pd.Series | np.ndarray, y: Any = None) -> LocationTierTransformer:
        return self

    def transform(self, X: pd.Series | np.ndarray) -> np.ndarray:
        series = pd.Series(X).astype(str).str.lower()
        tiers = []
        for loc in series:
            if "remote" in loc or "work from home" in loc:
                tiers.append("remote")
            elif "hybrid" in loc:
                tiers.append("hybrid")
            elif any(metro in loc for metro in TIER_1_METROS):
                tiers.append("tier_1_metro")
            elif any(t2 in loc for t2 in TIER_2_CITIES):
                tiers.append("tier_2_city")
            else:
                tiers.append("tier_3_other")
        return np.array(tiers, dtype=object).reshape(-1, 1)


class SeniorityTransformer(BaseEstimator, TransformerMixin):
    """Extracts job seniority level from job titles."""

    def fit(self, X: pd.Series | np.ndarray, y: Any = None) -> SeniorityTransformer:
        return self

    def transform(self, X: pd.Series | np.ndarray) -> np.ndarray:
        series = pd.Series(X).astype(str).str.lower()
        seniorities = []
        for t in series:
            if re.search(r"\b(intern|internship|trainee|apprentice)\b", t):
                seniorities.append("intern")
            elif re.search(r"\b(junior|jr|entry|associate|fresher|graduate)\b", t):
                seniorities.append("junior")
            elif re.search(r"\b(director|vp|head|chief|cto|cfo|coo|avp)\b", t):
                seniorities.append("executive")
            elif re.search(r"\b(manager|engineering manager|tech manager|lead manager)\b", t):
                seniorities.append("manager")
            elif re.search(r"\b(principal|staff|distinguished|architect)\b", t):
                seniorities.append("principal_architect")
            elif re.search(r"\b(lead|team lead|tech lead)\b", t):
                seniorities.append("lead")
            elif re.search(r"\b(senior|sr)\b", t):
                seniorities.append("senior")
            else:
                seniorities.append("mid")
        return np.array(seniorities, dtype=object).reshape(-1, 1)


class ExperienceFeaturesTransformer(BaseEstimator, TransformerMixin):
    """
    Extracts experience midpoint, quadratic term (Mincer returns),
    and experience category brackets.
    """

    def fit(self, X: pd.DataFrame | np.ndarray, y: Any = None) -> ExperienceFeaturesTransformer:
        return self

    def transform(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        if isinstance(X, pd.DataFrame):
            if "experience_mid_years" in X.columns:
                mid = X["experience_mid_years"].to_numpy(dtype=float)
            elif "minimumExperience_clean" in X.columns and "maximumExperience_clean" in X.columns:
                mid = (X["minimumExperience_clean"].to_numpy(dtype=float) + X["maximumExperience_clean"].to_numpy(dtype=float)) / 2.0
            else:
                mid = X.iloc[:, 0].to_numpy(dtype=float)
        else:
            mid = np.asarray(X, dtype=float).ravel()

        mid_clamped = np.clip(mid, 0.0, 30.0)
        mid_sq = mid_clamped ** 2

        # Brackets
        brackets = []
        for yrs in mid_clamped:
            if yrs <= 1.0:
                brackets.append("0-1_years")
            elif yrs <= 4.0:
                brackets.append("2-4_years")
            elif yrs <= 8.0:
                brackets.append("5-8_years")
            elif yrs <= 12.0:
                brackets.append("9-12_years")
            else:
                brackets.append("13+_years")

        return np.column_stack([
            mid_clamped,
            mid_sq,
            np.array(brackets, dtype=object)
        ])


class SkillIndicatorsTransformer(BaseEstimator, TransformerMixin):
    """
    Constructs multi-hot binary indicator vectors for tracked
    high-demand technical competencies from tag strings.
    """

    def __init__(self, tracked_skills: list[str] | None = None) -> None:
        self.tracked_skills = [s.lower() for s in (tracked_skills or TRACKED_TECH_SKILLS)]

    def fit(self, X: pd.Series | np.ndarray, y: Any = None) -> SkillIndicatorsTransformer:
        return self

    def transform(self, X: pd.Series | np.ndarray) -> np.ndarray:
        series = pd.Series(X).astype(str).str.lower()
        matrix = np.zeros((len(series), len(self.tracked_skills)), dtype=float)

        for i, text in enumerate(series):
            for j, sk in enumerate(self.tracked_skills):
                # Word boundary match for short acronyms like 'go', 'c++', 'sql'
                if len(sk) <= 3:
                    pattern = rf"(?:\b|[^a-zA-Z0-9]){re.escape(sk)}(?:\b|[^a-zA-Z0-9])"
                    if re.search(pattern, text):
                        matrix[i, j] = 1.0
                else:
                    if sk in text:
                        matrix[i, j] = 1.0

        return matrix

    def get_feature_names_out(self, input_features: Any = None) -> list[str]:
        return [f"skill_{s.replace(' ', '_').replace('/', '_').replace('.', '_').replace('+', 'p')}" for s in self.tracked_skills]


# Technical role family canonical identifiers
TECHNICAL_ROLE_FAMILIES = [
    "backend_core_software_engineering",
    "frontend_full_stack_engineering",
    "qa_automation_testing",
    "cloud_devops_sre",
    "data_engineer_big_data_platform",
    "data_analyst_business_intelligence",
    "data_science_ml_ai",
]


class RoleFamilyTransformer(BaseEstimator, TransformerMixin):
    """
    Maps job titles or role labels to approved JobRadar technical career families.
    Consolidates Data Science & AI/ML under 'data_science_ml_ai' for primary regression.
    Rejects and categorizes out-of-scope non-technical roles.
    """

    def __init__(self, consolidate_ds_ml: bool = True) -> None:
        self.consolidate_ds_ml = consolidate_ds_ml

        # Explicit regex rules ordered by specificity
        self.role_patterns = [
            # Data Science, ML & AI (specializations prioritized)
            ("data_science_ml_ai" if consolidate_ds_ml else "machine_learning_ai_engineer",
             r"\b(machine learning|ml engineer|ai engineer|artificial intelligence|computer vision|llm engineer|deep learning|genai|generative ai|mlops|ai architect|nlp engineer)\b"),
            ("data_science_ml_ai" if consolidate_ds_ml else "data_scientist_advanced_analytics",
             r"\b(data scientist|applied scientist|analytics consultant|decision scientist|nlp scientist|data science)\b"),

            # Data Engineering & Big Data
            ("data_engineer_big_data_platform",
             r"\b(data engineer|big data|etl developer|data warehouse|spark developer|pyspark|data pipeline|database engineer|dba)\b"),

            # Data Analyst & BI
            ("data_analyst_business_intelligence",
             r"\b(data analyst|bi analyst|business intelligence|tableau developer|power bi analyst|power bi developer|reporting analyst|bi developer|analytics analyst)\b"),

            # Cloud, DevOps & SRE
            ("cloud_devops_sre",
             r"\b(devops|cloud engineer|sre|site reliability|aws engineer|azure engineer|kubernetes engineer|infrastructure engineer|platform engineer|cloud architect)\b"),

            # QA & Automation Testing
            ("qa_automation_testing",
             r"\b(qa|quality assurance|software tester|automation test|test engineer|sdet|manual tester|selenium|qa automation|quality engineer)\b"),

            # Frontend & Full Stack
            ("frontend_full_stack_engineering",
             r"\b(frontend|front end|ui developer|react developer|angular developer|vue developer|web developer|javascript developer|full stack|fullstack|full-stack)\b"),

            # Backend & Core Software Engineering
            ("backend_core_software_engineering",
             r"\b(backend|software engineer|software developer|java developer|python developer|golang developer|c\+\+ developer|\.net developer|core developer|systems engineer|programmer|backend engineer)\b"),
        ]

        # Explicit non-technical signals
        self.non_tech_pattern = re.compile(
            r"\b(recruiter|recruitment|talent acquisition|hr|human resources|sales|telesales|bpo|telecaller|voice process|"
            r"customer care|customer support|operations associate|executive assistant|office assistant|accountant|"
            r"accounts executive|audit executive|finance executive|marketing executive|business development|seo executive|"
            r"content writer|graphic designer|legal counsel|pharmacist|nurse|receptionist|back office)\b",
            re.IGNORECASE
        )

    def is_technical_role(self, role_str: str) -> tuple[bool, str]:
        """
        Determine if an input role string maps to an approved technical family.
        Returns (is_technical, resolved_role_family).
        """
        cleaned = str(role_str).strip().lower()

        # Direct canonical role name matches
        if cleaned in TECHNICAL_ROLE_FAMILIES:
            return True, cleaned
        if cleaned in ("data_scientist_advanced_analytics", "machine_learning_ai_engineer"):
            return True, ("data_science_ml_ai" if self.consolidate_ds_ml else cleaned)

        # Check for explicit non-tech patterns first
        if self.non_tech_pattern.search(cleaned):
            return False, "non_technical_rejected"

        # Check technical role patterns
        for family_name, pattern in self.role_patterns:
            if re.search(pattern, cleaned):
                return True, family_name

        # Check general tech words
        if re.search(r"\b(engineer|developer|architect|programmer|tech|system|database|cloud|devops)\b", cleaned):
            return True, "backend_core_software_engineering"  # Fallback to software engineering core

        return False, "non_technical_rejected"

    def fit(self, X: Any, y: Any = None) -> RoleFamilyTransformer:
        return self

    def transform(self, X: Any) -> np.ndarray:
        if isinstance(X, pd.DataFrame):
            if "role_model" in X.columns:
                series = X["role_model"].astype(str)
            elif "role_phase4" in X.columns:
                if self.consolidate_ds_ml:
                    series = X["role_phase4"].replace({
                        "data_scientist_advanced_analytics": "data_science_ml_ai",
                        "machine_learning_ai_engineer": "data_science_ml_ai",
                    }).astype(str)
                else:
                    series = X["role_phase4"].astype(str)
            elif "title_clean" in X.columns:
                series = X["title_clean"].astype(str)
            else:
                series = X.iloc[:, 0].astype(str)
        else:
            series = pd.Series(X).astype(str)

        families = []
        for text in series:
            is_tech, family = self.is_technical_role(text)
            if is_tech:
                families.append(family)
            else:
                families.append("non_technical_rejected")

        return np.array(families, dtype=object).reshape(-1, 1)
