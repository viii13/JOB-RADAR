"""Career Recommendation Engine API Router for JobRadar Phase 5.6.

Exposes verified Phase 5 backend services through FastAPI endpoints:
1. POST /api/resume/extract-skills — In-memory resume text extraction & skill parsing
2. POST /api/recommendations/career — Objective technical career recommendations
3. POST /api/skills/gap — Role-specific empirical skill gap & readiness score
4. POST /api/roadmap/generate — Personalized milestone learning roadmap
5. GET  /api/recommendations/roles — Supported technical career roles & metadata
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
import sys
from typing import Any

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field

# Ensure JobRadar root is in sys.path for importing AI_ML
PROJECT_ROOT = Path(__file__).resolve().parents[2]
JOBRADAR_ROOT = PROJECT_ROOT.parent
if str(JOBRADAR_ROOT) not in sys.path:
    sys.path.insert(0, str(JOBRADAR_ROOT))

from AI_ML.Phase_5_Career_Recommendation.benchmarks import (
    SUPPORTED_TECHNICAL_ROLES,
    load_role_skill_benchmarks,
)
from AI_ML.Phase_5_Career_Recommendation.recommendations import (
    CareerRecommendationEngine,
)
from AI_ML.Phase_5_Career_Recommendation.resume import (
    ResumeSkillExtractor,
)
from AI_ML.Phase_5_Career_Recommendation.roadmap import (
    LearningRoadmapGenerator,
)
from AI_ML.Phase_5_Career_Recommendation.skill_gap import (
    SkillGapAnalyzer,
)

career_router = APIRouter(prefix="/api", tags=["Phase 5 Career Recommendations"])

# Singletons for thread-safe in-memory Phase 5 engines
_extractor = ResumeSkillExtractor()
_recommender = CareerRecommendationEngine()
_gap_analyzer = SkillGapAnalyzer()
_roadmap_generator = LearningRoadmapGenerator()

MAX_RESUME_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
ALLOWED_RESUME_EXTENSIONS = {".pdf", ".docx", ".txt"}


def resolve_target_role_id(role_input: str | None) -> str:
    """Normalize input role name or ID into the canonical technical role ID."""
    if not role_input or not str(role_input).strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Target role cannot be empty.",
        )

    r_clean = str(role_input).strip()
    if r_clean in SUPPORTED_TECHNICAL_ROLES:
        return r_clean

    r_lower = r_clean.lower()
    for rid, meta in SUPPORTED_TECHNICAL_ROLES.items():
        if r_lower == rid.lower():
            return rid
        if r_lower == meta.get("role_name", "").lower():
            return rid
        if r_lower == meta.get("frontend_filter_key", "").lower():
            return rid

    # Heuristic substring matching
    if "data scientist" in r_lower:
        return "data_scientist_advanced_analytics"
    if any(k in r_lower for k in ["machine learning", "ml engineer", "generative ai", "ai engineer"]):
        return "machine_learning_ai_engineer"
    if "data engineer" in r_lower:
        return "data_engineer_big_data_platform"
    if any(k in r_lower for k in ["data analyst", "business intelligence", "bi analyst"]):
        return "data_analyst_business_intelligence"
    if "backend" in r_lower:
        return "backend_core_software_engineering"
    if any(k in r_lower for k in ["frontend", "full stack", "fullstack"]):
        return "frontend_full_stack_engineering"
    if any(k in r_lower for k in ["cloud", "devops", "sre"]):
        return "cloud_devops_sre"
    if any(k in r_lower for k in ["qa", "testing", "quality"]):
        return "qa_automation_testing"

    valid_keys = list(SUPPORTED_TECHNICAL_ROLES.keys())
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Target role '{role_input}' is not a supported technical role. Supported roles: {valid_keys}",
    )


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------

class ExtractedSkillItem(BaseModel):
    canonical_name: str
    category: str
    evidence: str


class ResumeSkillExtractionResponse(BaseModel):
    filename: str
    file_type: str
    file_size_bytes: int
    extracted_skill_count: int
    skills: list[ExtractedSkillItem]
    skill_names: list[str]
    status: str
    warnings: list[str]


class CareerRecommendationRequest(BaseModel):
    skills: list[str] = Field(default_factory=list, description="Canonical or extracted student skills")
    preferred_role: str | None = Field(default=None, description="Optional target or preferred career role")
    education_background: str | None = Field(default=None, description="Optional degree or major")
    experience_level: str | None = Field(default=None, description="Optional experience tier")


class MatchingSkillItem(BaseModel):
    skill_name: str
    demand_percentage: float
    disclosed_job_demand_pct: float
    priority_category: str


class RoleRecommendationItem(BaseModel):
    role_id: str
    role_name: str
    match_score: float
    matching_skills: list[MatchingSkillItem]
    missing_critical_skills: list[MatchingSkillItem]
    missing_recommended_skills: list[MatchingSkillItem]
    support_tier: str
    eligible_job_count: int
    skill_disclosed_job_count: int
    skill_disclosure_rate: float
    is_preferred: bool
    explanation: str
    limitations: list[str]


class CareerRecommendationResponse(BaseModel):
    status: str
    user_skills_provided: list[str]
    normalized_skills: list[str]
    recommendations: list[RoleRecommendationItem]
    warnings: list[str]


class SkillGapRequest(BaseModel):
    skills: list[str] = Field(default_factory=list, description="List of student skills")
    target_role: str = Field(..., description="Target technical role ID or name")


class BenchmarkSkillItem(BaseModel):
    skill_name: str
    demand_percentage: float
    disclosed_job_demand_pct: float
    priority_category: str
    distinct_job_count: int | None = None


class SkillGapResponse(BaseModel):
    role_id: str
    role_name: str
    readiness_score: float
    acquired_skills: list[BenchmarkSkillItem]
    missing_critical_skills: list[BenchmarkSkillItem]
    missing_recommended_skills: list[BenchmarkSkillItem]
    missing_elective_skills: list[BenchmarkSkillItem]
    transferable_skills: list[str]
    support_tier: str
    eligible_job_count: int
    skill_disclosed_job_count: int
    skill_disclosure_rate: float
    methodology_notes: list[str]
    limitations: list[str]


class RoadmapRequest(BaseModel):
    skills: list[str] = Field(default_factory=list, description="List of student skills")
    target_role: str = Field(..., description="Target technical role ID or name")


class LearningResourceItem(BaseModel):
    title: str
    provider: str | None = None
    url: str
    type: str
    badge: str | None = None
    free: bool = True


class PracticePlatformItem(BaseModel):
    name: str
    url: str


class PracticalProjectItem(BaseModel):
    title: str
    difficulty: str | None = None
    skills_applied: list[str] = Field(default_factory=list)
    summary: str | None = None
    deliverables: list[str] = Field(default_factory=list)


class RoadmapMilestoneItem(BaseModel):
    milestone_id: int | str
    title: str
    phase: str
    priority: str
    skills_targeted: list[str]
    learning_objectives: list[str]
    resources: list[LearningResourceItem]
    practice_platforms: list[PracticePlatformItem]
    practical_project: PracticalProjectItem | None = None
    estimated_weeks: int
    completion_criteria: str | list[str]


class RoadmapResponse(BaseModel):
    role_id: str
    role_name: str
    current_readiness_score: float
    total_estimated_weeks: int
    milestones: list[RoadmapMilestoneItem]
    capstone_project: PracticalProjectItem | None = None
    disclaimers: list[str]


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@career_router.post(
    "/resume/extract-skills",
    response_model=ResumeSkillExtractionResponse,
    summary="Extract technical skills from student resume (PDF, DOCX, TXT) in-memory",
)
async def extract_resume_skills(file: UploadFile = File(...)) -> ResumeSkillExtractionResponse:
    """Extract skills from an uploaded resume strictly in-memory without disk persistence or logging."""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided in upload.",
        )

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_RESUME_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. Allowed formats: PDF (.pdf), Word (.docx), Plain Text (.txt).",
        )

    # Read bytes into memory
    content = await file.read()
    file_size = len(content)

    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded resume file is empty (0 bytes).",
        )

    if file_size > MAX_RESUME_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of 5 MB ({file_size} bytes received).",
        )

    # Process purely in-memory
    result = _extractor.extract_from_bytes(file_bytes=content, file_name=file.filename)

    if result.status == "CORRUPT_FILE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File corruption detected: {'; '.join(result.warnings)}",
        )

    warnings = list(result.warnings)
    if len(result.skills) == 0 and result.status == "success":
        warnings.append("No recognizable technical skills were detected in the uploaded resume.")

    extracted_items = [
        ExtractedSkillItem(
            canonical_name=s.canonical_name,
            category=s.category,
            evidence=s.evidence,
        )
        for s in result.skills
    ]

    return ResumeSkillExtractionResponse(
        filename=file.filename,
        file_type=result.file_type,
        file_size_bytes=file_size,
        extracted_skill_count=result.extracted_skill_count,
        skills=extracted_items,
        skill_names=[s.canonical_name for s in result.skills],
        status=result.status,
        warnings=warnings,
    )


@career_router.post(
    "/recommendations/career",
    response_model=CareerRecommendationResponse,
    summary="Rank supported technical careers against student skill profile",
)
def get_career_recommendations(
    request: CareerRecommendationRequest,
) -> CareerRecommendationResponse:
    """Calculate objective skill fit scores for 8 supported technical careers with explainability."""
    try:
        pref_id = None
        if request.preferred_role and request.preferred_role.strip():
            try:
                pref_id = resolve_target_role_id(request.preferred_role)
            except HTTPException:
                pref_id = request.preferred_role.strip()

        rec_result = _recommender.recommend(
            user_skills=request.skills,
            target_career_preference=pref_id,
            experience_level=request.experience_level,
            education_background=request.education_background,
        )

        res_dict = dataclasses.asdict(rec_result)
        return CareerRecommendationResponse(**res_dict)
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error computing career recommendations: {str(e)}",
        )


@career_router.post(
    "/skills/gap",
    response_model=SkillGapResponse,
    summary="Calculate empirical skill gap and readiness score for a target technical career",
)
def get_skill_gap_analysis(request: SkillGapRequest) -> SkillGapResponse:
    """Evaluate differential skill coverage across acquired, transferable, missing critical/recommended/elective."""
    role_id = resolve_target_role_id(request.target_role)

    try:
        gap_result = _gap_analyzer.analyze_gap(
            user_skills=request.skills,
            target_role_id=role_id,
        )
        return SkillGapResponse(**dataclasses.asdict(gap_result))
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error performing skill-gap analysis: {str(e)}",
        )


@career_router.post(
    "/roadmap/generate",
    response_model=RoadmapResponse,
    summary="Generate personalized milestone learning roadmap with verified resources",
)
def generate_learning_roadmap(request: RoadmapRequest) -> RoadmapResponse:
    """Generate ordered milestones, practice platforms, and projects tailored to missing skills."""
    role_id = resolve_target_role_id(request.target_role)

    try:
        gap_result = _gap_analyzer.analyze_gap(
            user_skills=request.skills,
            target_role_id=role_id,
        )
        roadmap_result = _roadmap_generator.generate_roadmap(skill_gap_result=gap_result)
        return RoadmapResponse(**dataclasses.asdict(roadmap_result))
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating learning roadmap: {str(e)}",
        )


@career_router.get(
    "/recommendations/roles",
    summary="List all supported technical career roles with metadata and benchmark provenance",
)
def get_supported_roles() -> list[dict[str, Any]]:
    """Return catalog of 8 supported technical careers with description and frontend mapping keys."""
    roles = []
    for role_id, meta in SUPPORTED_TECHNICAL_ROLES.items():
        roles.append({
            "role_id": role_id,
            "role_name": meta.get("role_name"),
            "frontend_filter_key": meta.get("frontend_filter_key"),
            "description": meta.get("description"),
        })
    return roles


@career_router.get(
    "/skills/by-role",
    summary="List empirical benchmark skill demand for a specific technical career role",
)
def get_skills_by_role(
    role: str = Query(default="Data Scientist", description="Target technical role name or canonical ID"),
) -> dict[str, Any]:
    """Retrieve verified hard skill frequencies for the specified technical role."""
    role_id = resolve_target_role_id(role)
    role_meta = _gap_analyzer.roles_data.get(role_id, {})
    raw_skills = role_meta.get("skills", [])
    skills = [
        {
            "skill": s["skill_name"],
            "pct": round(float(s.get("disclosed_job_demand_pct", s.get("demand_percentage", 0))), 1),
            "priority": s.get("priority_category", "RECOMMENDED"),
        }
        for s in raw_skills
    ]
    return {
        "success": True,
        "role_id": role_id,
        "role_name": role_meta.get("role_name", role),
        "skills": skills,
    }

