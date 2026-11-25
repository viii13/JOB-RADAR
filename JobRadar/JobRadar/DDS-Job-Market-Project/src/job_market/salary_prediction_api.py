"""
FastAPI Salary Prediction API Router (Phase 6 Stage 6.12)
Provides endpoints for compensation estimation, uncertainty ranges, and model metadata.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

salary_router = APIRouter(prefix="/api/salary", tags=["Salary Prediction"])

# Lazy-loaded singleton engine
_engine = None

def _get_engine():
    global _engine
    if _engine is None:
        import sys
        # Ensure Phase 6 package is importable
        proj_root = Path(__file__).resolve().parents[3]
        aiml_dir = proj_root / "AI_ML"
        if str(aiml_dir) not in sys.path:
            sys.path.insert(0, str(aiml_dir))

        from Phase_6_Salary_Prediction.api.prediction_service import SalaryPredictionEngine
        _engine = SalaryPredictionEngine()
    return _engine


# ---------------------------------------------------------
# Request & Response Pydantic Schemas
# ---------------------------------------------------------

class SalaryPredictionRequest(BaseModel):
    role: str = Field(default="Software Engineer", description="Target job title or career track")
    experience_years: float = Field(default=2.0, ge=0.0, le=40.0, description="Years of professional experience")
    location: str = Field(default="Bengaluru", description="Geographic city or working mode (e.g. Remote, Bengaluru)")
    skills: list[str] = Field(default_factory=list, description="List of technical competencies")


class SalaryPredictionResponse(BaseModel):
    target_role: str
    resolved_role_family: str = Field(default="backend_core_software_engineering", description="Classified technical career family")
    is_technical: bool = Field(default=True, description="Whether role is an approved technical career")
    experience_years: float
    location: str
    skills_provided: list[str]
    predicted_salary_lpa: float
    predicted_salary_annual_inr: float
    conformal_interval_lpa: dict[str, float] = Field(description="90% calibrated conformal prediction interval in LPA")
    conformal_interval_annual_inr: dict[str, float] = Field(description="90% calibrated conformal prediction interval in INR")
    conformal_uncertainty_lpa: float = Field(description="Calibrated empirical non-conformity margin in LPA")
    coverage_level_pct: float = Field(default=90.0, description="Nominal empirical coverage percentage")
    salary_range_lpa: dict[str, float] = Field(description="Backwards-compatible calibrated range in LPA")
    salary_range_annual_inr: dict[str, float] = Field(description="Backwards-compatible calibrated range in INR")
    role_median_lpa: float
    market_tier: str
    model_name: str
    model_version: str
    mae_uncertainty_lpa: float = Field(description="Backwards-compatible uncertainty margin in LPA")
    calibration_method: str = Field(default="role_stratified_conformal", description="Conformal calibration method")
    contributing_factors: list[str]
    disclaimers: list[str]


# ---------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------

@salary_router.post(
    "/predict",
    response_model=SalaryPredictionResponse,
    summary="Predict market compensation with statistical uncertainty range",
    description="Estimates expected annual salary in LPA and INR from job role, experience years, location, and technical skills.",
)
def predict_salary_endpoint(req: SalaryPredictionRequest) -> dict[str, Any]:
    """Generate empirical salary estimate."""
    if req.experience_years < 0 or req.experience_years > 40:
        raise HTTPException(status_code=400, detail="Experience years must be between 0.0 and 40.0.")

    if not req.role or not req.role.strip():
        raise HTTPException(status_code=400, detail="Target role must be a non-empty string.")

    try:
        engine = _get_engine()
        result = engine.predict(
            role=req.role,
            experience_years=req.experience_years,
            location=req.location,
            skills=req.skills,
        )
        return result.to_dict()
    except ValueError as val_err:
        logger.warning(f"Salary prediction validation/scope error: {val_err}")
        raise HTTPException(status_code=400, detail=str(val_err))
    except Exception as exc:
        logger.error(f"Salary prediction error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Salary prediction failed: {str(exc)}")


@salary_router.get(
    "/metadata",
    summary="Get salary model card, validation metrics, and training metadata",
)
def get_salary_model_metadata() -> dict[str, Any]:
    """Retrieve model comparison, champion metrics, and feature importances."""
    proj_root = Path(__file__).resolve().parents[3]
    v2_path = proj_root / "AI_ML" / "Phase_6_Salary_Prediction" / "models" / "artifacts" / "salary_model_metadata_v2.json"
    v1_path = proj_root / "AI_ML" / "Phase_6_Salary_Prediction" / "models" / "artifacts" / "salary_model_metadata.json"

    meta_path = v2_path if v2_path.is_file() else v1_path

    if not meta_path.is_file():
        raise HTTPException(status_code=404, detail="Salary model metadata artifact not found.")

    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        return data
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load model metadata: {str(exc)}")
