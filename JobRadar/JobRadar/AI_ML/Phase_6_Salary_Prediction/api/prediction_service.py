"""
Salary Prediction Service (Phase 6 Stage 6.11 & 6.12 — v2.0.0 Technical-Only)
Provides a clean, validated prediction interface for the JobRadar Salary Prediction Engine.
Calibrated exclusively on approved technical engineering and data roles with conformal intervals.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
import joblib
import numpy as np
import pandas as pd

_MODULE_DIR = Path(__file__).resolve().parent
_PHASE6_DIR = _MODULE_DIR.parent
_AIML_DIR = _PHASE6_DIR.parent
if str(_AIML_DIR) not in sys.path:
    sys.path.insert(0, str(_AIML_DIR))
if str(_PHASE6_DIR) not in sys.path:
    sys.path.insert(0, str(_PHASE6_DIR))

try:
    import features
    sys.modules["features"] = features
    import features.pipeline
    sys.modules["features.pipeline"] = features.pipeline
    import features.transformers
    sys.modules["features.transformers"] = features.transformers
except Exception:
    pass

from ..features.transformers import RoleFamilyTransformer, TECHNICAL_ROLE_FAMILIES
_ARTIFACTS_DIR = _PHASE6_DIR / "models" / "artifacts"
_MODEL_V2_PATH = _ARTIFACTS_DIR / "salary_predictor_v2.0.0_tech_only.joblib"
_MODEL_V1_PATH = _ARTIFACTS_DIR / "salary_predictor_v1.0.0.joblib"
_METADATA_V2_PATH = _ARTIFACTS_DIR / "salary_model_metadata_v2.json"
_METADATA_V1_PATH = _ARTIFACTS_DIR / "salary_model_metadata.json"


@dataclass(frozen=True)
class SalaryPredictionResult:
    """Standard container for salary prediction engine response."""
    target_role: str
    resolved_role_family: str
    is_technical: bool
    experience_years: float
    location: str
    skills_provided: list[str]
    predicted_salary_lpa: float
    predicted_salary_annual_inr: float
    conformal_interval_lpa: dict[str, float]
    conformal_interval_annual_inr: dict[str, float]
    conformal_uncertainty_lpa: float
    coverage_level_pct: float
    salary_range_lpa: dict[str, float]
    salary_range_annual_inr: dict[str, float]
    role_median_lpa: float
    market_tier: str
    model_name: str
    model_version: str
    mae_uncertainty_lpa: float
    calibration_method: str
    contributing_factors: list[str]
    disclaimers: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_role": self.target_role,
            "resolved_role_family": self.resolved_role_family,
            "is_technical": self.is_technical,
            "experience_years": self.experience_years,
            "location": self.location,
            "skills_provided": self.skills_provided,
            "predicted_salary_lpa": round(self.predicted_salary_lpa, 2),
            "predicted_salary_annual_inr": round(self.predicted_salary_annual_inr, 0),
            "conformal_interval_lpa": {k: round(v, 2) for k, v in self.conformal_interval_lpa.items()},
            "conformal_interval_annual_inr": {k: round(v, 0) for k, v in self.conformal_interval_annual_inr.items()},
            "conformal_uncertainty_lpa": round(self.conformal_uncertainty_lpa, 2),
            "coverage_level_pct": self.coverage_level_pct,
            "salary_range_lpa": {k: round(v, 2) for k, v in self.salary_range_lpa.items()},
            "salary_range_annual_inr": {k: round(v, 0) for k, v in self.salary_range_annual_inr.items()},
            "role_median_lpa": round(self.role_median_lpa, 2),
            "market_tier": self.market_tier,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "mae_uncertainty_lpa": round(self.mae_uncertainty_lpa, 2),
            "calibration_method": self.calibration_method,
            "contributing_factors": self.contributing_factors,
            "disclaimers": self.disclaimers,
        }


class SalaryPredictionEngine:
    """Predicts market compensation for core technical careers using conformal intervals."""

    def __init__(self, model_version: str = "2.0.0", model_path: str | Path | None = None) -> None:
        self.requested_version = model_version
        self.role_mapper = RoleFamilyTransformer(consolidate_ds_ml=True)

        if model_path:
            self.model_path = Path(model_path)
            default_ver = "1.0.0" if "v1.0.0" in str(self.model_path) else "2.0.0"
        elif model_version == "1.0.0":
            self.model_path = _MODEL_V1_PATH
            default_ver = "1.0.0"
        else:
            self.model_path = _MODEL_V2_PATH if _MODEL_V2_PATH.is_file() else _MODEL_V1_PATH
            default_ver = "2.0.0" if "v2.0.0" in str(self.model_path) else "1.0.0"

        if not self.model_path.is_file():
            raise FileNotFoundError(
                f"Trained salary model artifact not found at: {self.model_path}. "
                "Ensure train_and_evaluate_technical_salary_models() has been executed."
            )

        bundle = joblib.load(self.model_path)
        self.pipeline = bundle["pipeline"]
        self.model_name = bundle.get("champion_model_name", "Ridge Regression (alpha=10.0)")
        self.model_version = bundle.get("model_version") or default_ver
        self.conformal_calib = bundle.get("conformal_calibration", {})
        self.role_medians = bundle.get("role_medians", {})
        self.test_mae = bundle.get("metrics", {}).get("cv_mae_lpa", bundle.get("metrics", {}).get("test_mae_lpa", 4.74))

    def predict(
        self,
        role: str,
        experience_years: float,
        location: str = "Bengaluru",
        skills: list[str] | None = None,
    ) -> SalaryPredictionResult:
        """
        Generate statistical compensation forecast with group-aware conformal intervals.
        Rejects non-technical roles with a clear descriptive ValueError.
        """
        clean_role = (role or "Software Engineer").strip()
        clamped_exp = max(0.0, min(float(experience_years), 30.0))
        clean_loc = (location or "Bengaluru").strip()
        clean_skills = [s.strip() for s in (skills or []) if s.strip()]
        skills_text = " ".join(clean_skills)

        # 1. Scope Validation: Check technical domain applicability
        is_tech, resolved_family = self.role_mapper.is_technical_role(clean_role)
        if not is_tech:
            raise ValueError(
                f"Salary prediction is currently calibrated exclusively for core technical engineering "
                f"and data roles (Backend, Frontend, Full Stack, QA, Cloud/DevOps, Data Engineering, "
                f"Data Analytics, and Data Science / AI). The requested role '{clean_role}' is not within technical scope."
            )

        # 2. Input DataFrame matching feature pipeline schema
        df_input = pd.DataFrame([{
            "title_clean": clean_role,
            "role_model": resolved_family,
            "experience_mid_years": clamped_exp,
            "minimumExperience_clean": max(0.0, clamped_exp - 1.0),
            "maximumExperience_clean": clamped_exp + 1.0,
            "location_clean": clean_loc,
            "tagsAndSkills_clean": skills_text,
        }])

        # 3. Predict point estimate
        raw_pred = float(self.pipeline.predict(df_input)[0])
        pred_lpa = max(1.2, min(raw_pred, 95.0))
        pred_inr = pred_lpa * 100000.0

        # 4. Calibrated Conformal Prediction Interval (Group-Aware / Role-Stratified)
        role_calib = self.conformal_calib.get("role_stratified_calibration", {}).get(resolved_family, {})
        conformal_q90 = role_calib.get("q90_lpa", self.conformal_calib.get("global_q90_lpa", 10.60))
        coverage_pct = 90.0

        min_range_lpa = max(0.60, pred_lpa - conformal_q90)
        max_range_lpa = pred_lpa + conformal_q90

        # Market tier and role median
        features_union = self.pipeline.named_steps["features"]
        market_tier = features_union.location_tier_extractor.transform([clean_loc])[0, 0]
        role_median = self.role_medians.get(resolved_family, 14.0)

        # Explainable contributing factors
        factors = []
        if clamped_exp <= 1.0:
            factors.append("Entry-level / fresher baseline calibration applied.")
        elif clamped_exp >= 8.0:
            factors.append(f"Seniority premium applied for {clamped_exp:.1f} years of technical experience.")
        else:
            factors.append(f"Core career progression curve applied for {clamped_exp:.1f} years experience.")

        if market_tier == "tier_1_metro":
            factors.append(f"Tier-1 tech metro compensation premium applied for {clean_loc}.")
        elif market_tier == "remote":
            factors.append("Remote / distributed compensation index applied.")
        elif market_tier == "tier_2_city":
            factors.append(f"Tier-2 emerging regional cost-of-living index applied for {clean_loc}.")

        if clean_skills:
            matched_tech = [s for s in clean_skills if s.lower() in [
                "python", "java", "sql", "aws", "docker", "kubernetes", "react",
                "machine learning", "fastapi", "spring boot", "spark", "pytorch"
            ]]
            if matched_tech:
                factors.append(f"Valued technical competencies detected: {', '.join(matched_tech[:4])}.")

        disclaimers = [
            "Empirical statistical estimation calibrated on 4,207 verified technical Indian job postings across 8 approved engineering & data families.",
            f"Prediction interval reflects 90% calibrated conformal market coverage (empirical non-conformity margin: ±{conformal_q90:.2f} LPA).",
            "Actual compensation offers vary with candidate evaluation, technical depth, employer tier, and stock/bonus equity.",
        ]

        conformal_lpa = {"min_lpa": round(min_range_lpa, 2), "max_lpa": round(max_range_lpa, 2)}
        conformal_inr = {"min_inr": round(min_range_lpa * 100000.0), "max_inr": round(max_range_lpa * 100000.0)}

        return SalaryPredictionResult(
            target_role=clean_role,
            resolved_role_family=resolved_family,
            is_technical=True,
            experience_years=clamped_exp,
            location=clean_loc,
            skills_provided=clean_skills,
            predicted_salary_lpa=pred_lpa,
            predicted_salary_annual_inr=pred_inr,
            conformal_interval_lpa=conformal_lpa,
            conformal_interval_annual_inr=conformal_inr,
            conformal_uncertainty_lpa=conformal_q90,
            coverage_level_pct=coverage_pct,
            salary_range_lpa=conformal_lpa,
            salary_range_annual_inr=conformal_inr,
            role_median_lpa=role_median,
            market_tier=market_tier,
            model_name=self.model_name,
            model_version=self.model_version,
            mae_uncertainty_lpa=conformal_q90,
            calibration_method="role_stratified_conformal",
            contributing_factors=factors,
            disclaimers=disclaimers,
        )
