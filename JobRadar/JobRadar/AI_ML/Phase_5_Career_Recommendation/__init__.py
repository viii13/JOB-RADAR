"""JobRadar Phase 5 — Student Career Recommendation Engine.

Exposes end-to-end functionality across:
- Stage 5.1: Empirical Role-Skill Benchmarks
- Stage 5.2: Resume Extraction and Skill Parsing
- Stage 5.3: Career Recommendation Engine
- Stage 5.4: Skill-Gap Analysis
- Stage 5.5: Personalized Learning Roadmap
"""

from .benchmarks import (
    DEFAULT_CRITICAL_THRESHOLD,
    DEFAULT_MIN_CONFIDENCE_THRESHOLD,
    DEFAULT_RECOMMENDED_THRESHOLD,
    DEFAULT_SUPPORT_HIGH_THRESHOLD,
    DEFAULT_SUPPORT_MODERATE_THRESHOLD,
    SUPPORTED_TECHNICAL_ROLES,
    BenchmarkMetadata,
    RoleBenchmarkSummary,
    RoleSkillBenchmark,
    RoleSkillBenchmarksResult,
    assign_priority_category,
    assign_support_tier,
    calculate_role_benchmarks,
    load_role_skill_benchmarks,
)
from .recommendations import (
    CareerRecommendationEngine,
    CareerRecommendationResult,
    MatchingSkillInfo,
    RoleRecommendation,
)
from .resume import (
    ExtractedSkill,
    ResumeExtractionResult,
    ResumeSkillExtractor,
)
from .roadmap import (
    LearningResource,
    LearningRoadmapGenerator,
    LearningRoadmapResult,
    PracticalProject,
    PracticePlatform,
    RoadmapMilestone,
    SkillResourcePackage,
)
from .skill_gap import (
    BenchmarkSkillDetail,
    SkillGapAnalyzer,
    SkillGapResult,
)

__all__ = [
    # Benchmarks
    "DEFAULT_CRITICAL_THRESHOLD",
    "DEFAULT_MIN_CONFIDENCE_THRESHOLD",
    "DEFAULT_RECOMMENDED_THRESHOLD",
    "DEFAULT_SUPPORT_HIGH_THRESHOLD",
    "DEFAULT_SUPPORT_MODERATE_THRESHOLD",
    "SUPPORTED_TECHNICAL_ROLES",
    "BenchmarkMetadata",
    "RoleBenchmarkSummary",
    "RoleSkillBenchmark",
    "RoleSkillBenchmarksResult",
    "assign_priority_category",
    "assign_support_tier",
    "calculate_role_benchmarks",
    "load_role_skill_benchmarks",
    # Resume
    "ExtractedSkill",
    "ResumeExtractionResult",
    "ResumeSkillExtractor",
    # Recommender
    "CareerRecommendationEngine",
    "CareerRecommendationResult",
    "MatchingSkillInfo",
    "RoleRecommendation",
    # Skill Gap
    "BenchmarkSkillDetail",
    "SkillGapAnalyzer",
    "SkillGapResult",
    # Roadmap
    "LearningResource",
    "LearningRoadmapGenerator",
    "LearningRoadmapResult",
    "PracticalProject",
    "PracticePlatform",
    "RoadmapMilestone",
    "SkillResourcePackage",
]
