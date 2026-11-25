"""Learning roadmap package for Phase 5."""

from .generator import (
    LearningRoadmapGenerator,
    LearningRoadmapResult,
    RoadmapMilestone,
)
from .resources import (
    LearningResource,
    PracticalProject,
    PracticePlatform,
    SkillResourcePackage,
    VERIFIED_SKILL_RESOURCES,
    generate_fallback_project,
    get_skill_resource_package,
)

__all__ = [
    "LearningRoadmapGenerator",
    "LearningRoadmapResult",
    "RoadmapMilestone",
    "LearningResource",
    "PracticalProject",
    "PracticePlatform",
    "SkillResourcePackage",
    "VERIFIED_SKILL_RESOURCES",
    "generate_fallback_project",
    "get_skill_resource_package",
]
