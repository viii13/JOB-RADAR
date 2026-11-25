"""Personalized Learning Roadmap Generator.

Stage 5.5 — Converts skill gaps into a structured, deterministic learning roadmap
with concrete milestones, verified resources, practical coding projects, and realistic estimates.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

from .resources import (
    LearningResource,
    PracticalProject,
    PracticePlatform,
    generate_fallback_project,
    get_skill_resource_package,
)

# Resolve paths
_current_dir = Path(__file__).resolve().parent
_phase5_root = _current_dir.parent
_project_root = _phase5_root.parent.parent
_benchmarks_json = _phase5_root / "benchmarks" / "role_skill_benchmarks.json"


@dataclass(frozen=True)
class RoadmapMilestone:
    """Individual learning milestone focused on closing specific skill gaps."""

    milestone_id: int
    title: str
    phase: str
    priority: str  # "CRITICAL", "RECOMMENDED", "ELECTIVE"
    skills_targeted: list[str]
    learning_objectives: list[str]
    resources: list[dict[str, Any]]
    practice_platforms: list[dict[str, Any]]
    practical_project: dict[str, Any]
    estimated_weeks: int
    completion_criteria: str

    def to_dict(self) -> dict[str, Any]:
        """Convert milestone to dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class LearningRoadmapResult:
    """Complete personalized learning roadmap for a student and target role."""

    role_id: str
    role_name: str
    current_readiness_score: float
    total_estimated_weeks: int
    milestones: list[RoadmapMilestone]
    capstone_project: dict[str, Any]
    disclaimers: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Convert container to serializable dictionary."""
        return {
            "role_id": self.role_id,
            "role_name": self.role_name,
            "current_readiness_score": self.current_readiness_score,
            "total_estimated_weeks": self.total_estimated_weeks,
            "milestones": [m.to_dict() for m in self.milestones],
            "capstone_project": self.capstone_project,
            "disclaimers": self.disclaimers,
        }


class LearningRoadmapGenerator:
    """Generates personalized learning roadmaps based on skill gap analysis."""

    def __init__(self, benchmarks_path: str | Path | None = None) -> None:
        """Initialize generator with role benchmarks."""
        bench_file = Path(benchmarks_path) if benchmarks_path else _benchmarks_json
        if not bench_file.is_file():
            raise FileNotFoundError(f"Role benchmarks file not found at: {bench_file}")

        self.benchmarks_data = json.loads(bench_file.read_text(encoding="utf-8"))
        self.roles_data: dict[str, Any] = self.benchmarks_data.get("roles", {})

    def generate_roadmap(
        self,
        skill_gap_result: Any,  # SkillGapResult
    ) -> LearningRoadmapResult:
        """Build deterministic learning roadmap from a SkillGapResult."""
        role_id = skill_gap_result.role_id
        role_name = skill_gap_result.role_name
        readiness = skill_gap_result.readiness_score

        missing_critical = [s.skill_name for s in skill_gap_result.missing_critical_skills]
        missing_recommended = [s.skill_name for s in skill_gap_result.missing_recommended_skills]
        missing_elective = [s.skill_name for s in skill_gap_result.missing_elective_skills]

        milestones: list[RoadmapMilestone] = []
        milestone_counter = 1

        # Case 1: No skill gaps at all!
        if not missing_critical and not missing_recommended:
            # Student has achieved high alignment with role core
            milestones.append(
                RoadmapMilestone(
                    milestone_id=1,
                    title="Advanced Mastery & System Architecture",
                    phase="Phase 1: Advanced Specialization",
                    priority="RECOMMENDED",
                    skills_targeted=missing_elective[:3] if missing_elective else ["System Design"],
                    learning_objectives=[
                        "Deepen expertise in end-to-end architecture, distributed systems, and scalability.",
                        "Contribute to open-source software repositories aligned with this career family.",
                    ],
                    resources=[
                        {
                            "title": "System Design Primer",
                            "provider": "GitHub (donnemartin)",
                            "url": "https://github.com/donnemartin/system-design-primer",
                            "type": "Documentation",
                            "badge": "Community Gold Standard",
                            "free": True,
                        }
                    ],
                    practice_platforms=[
                        {"name": "LeetCode / HackerRank", "url": "https://leetcode.com/"}
                    ],
                    practical_project=asdict(
                        PracticalProject(
                            title=f"Production-Grade {role_name} Capstone Service",
                            difficulty="Advanced",
                            skills_applied=[s.skill_name for s in skill_gap_result.acquired_skills[:4]],
                            summary="Architect, deploy, and benchmark a high-throughput technical service with full test coverage and automated CI/CD pipeline.",
                            deliverables=[
                                "Production code repository on GitHub",
                                "Continuous Integration pipeline configuration",
                                "Performance benchmarking report with latency percentiles",
                            ],
                        )
                    ),
                    estimated_weeks=4,
                    completion_criteria="Public GitHub repository with 90%+ test coverage, passing CI/CD, and architecture documentation.",
                )
            )
            capstone = milestones[0].practical_project
            total_weeks = 4
        else:
            # Standard Gap Progression
            phase_num = 1

            # Phase for Critical Skills (priority >= 50%)
            if missing_critical:
                # Group critical skills into chunks of up to 2 skills
                for i in range(0, len(missing_critical), 2):
                    chunk = missing_critical[i : i + 2]
                    chunk_title = " & ".join(chunk)
                    res_list, plat_list, obj_list, proj = self._compile_milestone_assets(
                        skills=chunk, priority="CRITICAL", role_name=role_name
                    )
                    milestones.append(
                        RoadmapMilestone(
                            milestone_id=milestone_counter,
                            title=f"Master Critical Core: {chunk_title}",
                            phase=f"Phase {phase_num}: Critical Foundations",
                            priority="CRITICAL",
                            skills_targeted=chunk,
                            learning_objectives=obj_list,
                            resources=res_list,
                            practice_platforms=plat_list,
                            practical_project=asdict(proj),
                            estimated_weeks=4 * len(chunk),
                            completion_criteria=f"Complete hands-on implementation project demonstrating operational competency in {chunk_title}.",
                        )
                    )
                    milestone_counter += 1
                phase_num += 1

            # Phase for Recommended Skills (20% to 49.9%)
            if missing_recommended:
                # Prioritize top 4 recommended skills
                top_recommended = missing_recommended[:4]
                rec_phase_label = (
                    f"Phase {phase_num}: High-Demand Tools"
                    if missing_critical
                    else f"Phase {phase_num}: Core Technologies"
                )
                for i in range(0, len(top_recommended), 2):
                    chunk = top_recommended[i : i + 2]
                    chunk_title = " & ".join(chunk)
                    res_list, plat_list, obj_list, proj = self._compile_milestone_assets(
                        skills=chunk, priority="RECOMMENDED", role_name=role_name
                    )
                    milestones.append(
                        RoadmapMilestone(
                            milestone_id=milestone_counter,
                            title=f"Core Tooling & Frameworks: {chunk_title}",
                            phase=rec_phase_label,
                            priority="RECOMMENDED",
                            skills_targeted=chunk,
                            learning_objectives=obj_list,
                            resources=res_list,
                            practice_platforms=plat_list,
                            practical_project=asdict(proj),
                            estimated_weeks=3 * len(chunk),
                            completion_criteria=f"Build and test modular functionality incorporating {chunk_title}.",
                        )
                    )
                    milestone_counter += 1
                phase_num += 1

            # Phase for Applied Electives / High-Impact Enhancements
            if missing_elective:
                elective_chunk = missing_elective[:2]
                chunk_title = " & ".join(elective_chunk)
                res_list, plat_list, obj_list, proj = self._compile_milestone_assets(
                    skills=elective_chunk, priority="ELECTIVE", role_name=role_name
                )
                milestones.append(
                    RoadmapMilestone(
                        milestone_id=milestone_counter,
                        title=f"Specialized Competencies: {chunk_title}",
                        phase=f"Phase {phase_num}: Applied Electives",
                        priority="ELECTIVE",
                        skills_targeted=elective_chunk,
                        learning_objectives=obj_list,
                        resources=res_list,
                        practice_platforms=plat_list,
                        practical_project=asdict(proj),
                        estimated_weeks=2 * len(elective_chunk),
                        completion_criteria=f"Document practical integration of {chunk_title} into an existing software service or workflow.",
                    )
                )
                milestone_counter += 1
                phase_num += 1

            # Phase 4: Capstone Portfolio Integration Project
            top_acquired = [s.skill_name for s in skill_gap_result.acquired_skills[:2]]
            top_new = (missing_critical + missing_recommended)[:2]
            combined_skills = top_acquired + top_new
            capstone_proj = PracticalProject(
                title=f"Comprehensive {role_name} Capstone Portfolio Project",
                difficulty="Intermediate-to-Advanced",
                skills_applied=combined_skills,
                summary=f"Synthesize acquired competencies ({', '.join(top_acquired) if top_acquired else 'Foundations'}) and newly mastered tools ({', '.join(top_new)}) into a deployed end-to-end technical system.",
                deliverables=[
                    "Public GitHub repository with comprehensive README and setup script",
                    "Modular application code with docstrings and type annotations",
                    "Automated test suite achieving >= 80% coverage",
                    "Live deployed web demo, REST API, or cloud infrastructure template",
                ],
            )
            capstone = asdict(capstone_proj)
            total_weeks = sum(m.estimated_weeks for m in milestones)

        disclaimers = [
            "Estimates Notice: Timeline estimates (weeks) are indicative guidelines based on 10-15 hours/week of dedicated study.",
            "Resource Verification: Curated courses and documentation links are verified official or reputable sources. No commercial guarantees or endorsements are implied.",
            "Employment Disclaimer: Completing roadmap milestones improves empirical skill alignment with JobRadar job market data; it does NOT guarantee job placement or interview invitations.",
        ]
        if skill_gap_result.support_tier == "LOW":
            disclaimers.append(
                f"Sample Warning: '{role_name}' has LOW empirical support ({skill_gap_result.eligible_job_count} postings) in current job data. Learning priorities should be cross-referenced with university curricula."
            )

        return LearningRoadmapResult(
            role_id=role_id,
            role_name=role_name,
            current_readiness_score=readiness,
            total_estimated_weeks=total_weeks,
            milestones=milestones,
            capstone_project=capstone,
            disclaimers=disclaimers,
        )

    def _compile_milestone_assets(
        self,
        skills: list[str],
        priority: str,
        role_name: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str], PracticalProject]:
        """Collect verified resources, platforms, objectives, and project for a skill chunk."""
        resources: list[dict[str, Any]] = []
        platforms: list[dict[str, Any]] = []
        objectives: list[str] = []
        project_candidates: list[PracticalProject] = []

        for s in skills:
            pkg = get_skill_resource_package(s)
            if pkg:
                for r in pkg.resources:
                    resources.append(asdict(r))
                for p in pkg.practice_platforms:
                    platforms.append(asdict(p))
                for step in pkg.implementation_steps[:2]:
                    objectives.append(f"[{s}] {step}")
                if pkg.projects:
                    project_candidates.append(pkg.projects[0])
            else:
                objectives.append(
                    f"[{s}] Learn core concepts, API syntax, and best practices through official reference documentation."
                )
                objectives.append(
                    f"[{s}] Build a modular coding exercise demonstrating practical usage in {role_name} workflows."
                )

        # Deduplicate resources and platforms by URL
        seen_r_urls: set[str] = set()
        dedup_resources: list[dict[str, Any]] = []
        for r in resources:
            if r["url"] not in seen_r_urls:
                seen_r_urls.add(r["url"])
                dedup_resources.append(r)

        seen_p_urls: set[str] = set()
        dedup_platforms: list[dict[str, Any]] = []
        for p in platforms:
            if p["url"] not in seen_p_urls:
                seen_p_urls.add(p["url"])
                dedup_platforms.append(p)

        # Pick or generate practical project
        if project_candidates:
            project = project_candidates[0]
        else:
            project = generate_fallback_project(skills[0], priority)

        return dedup_resources, dedup_platforms, objectives, project
