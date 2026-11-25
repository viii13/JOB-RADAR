"""Career Recommendation Engine for Technical Roles.

Stage 5.3 — Generates transparent, deterministic career recommendations
for JobRadar's 8 approved technical career families using empirical role-skill benchmarks.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

# Resolve paths
_current_dir = Path(__file__).resolve().parent
_phase5_root = _current_dir.parent
_project_root = _phase5_root.parent.parent
_benchmarks_json = _phase5_root / "benchmarks" / "role_skill_benchmarks.json"
_ref_dir = _project_root / "DDS-Job-Market-Project" / "data" / "reference"

# Weightings for explainable scoring formula
WEIGHT_CRITICAL_COVERAGE: float = 0.50
WEIGHT_CORE_DEMAND_COVERAGE: float = 0.40
MAX_BREADTH_BONUS: float = 10.0
# Note: Preference is used strictly as a deterministic tie-breaker in sorting,
# not as an additive score bonus, ensuring match_score represents objective skill fit only.


@dataclass(frozen=True)
class MatchingSkillInfo:
    """Detailed metadata for a matched or missing benchmark skill."""

    skill_name: str
    demand_percentage: float
    disclosed_job_demand_pct: float
    priority_category: str


@dataclass(frozen=True)
class RoleRecommendation:
    """Individual career recommendation for a supported technical role."""

    role_id: str
    role_name: str
    match_score: float
    matching_skills: list[MatchingSkillInfo]
    missing_critical_skills: list[MatchingSkillInfo]
    missing_recommended_skills: list[MatchingSkillInfo]
    support_tier: str
    eligible_job_count: int
    skill_disclosed_job_count: int
    skill_disclosure_rate: float
    is_preferred: bool
    explanation: str
    limitations: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Convert recommendation to dictionary."""
        return {
            "role_id": self.role_id,
            "role_name": self.role_name,
            "match_score": self.match_score,
            "matching_skills": [asdict(s) for s in self.matching_skills],
            "missing_critical_skills": [asdict(s) for s in self.missing_critical_skills],
            "missing_recommended_skills": [asdict(s) for s in self.missing_recommended_skills],
            "support_tier": self.support_tier,
            "eligible_job_count": self.eligible_job_count,
            "skill_disclosed_job_count": self.skill_disclosed_job_count,
            "skill_disclosure_rate": self.skill_disclosure_rate,
            "is_preferred": self.is_preferred,
            "explanation": self.explanation,
            "limitations": self.limitations,
        }


@dataclass(frozen=True)
class CareerRecommendationResult:
    """Container for complete career recommendation response."""

    status: str  # "success", "incomplete_profile", "no_skills_matched"
    user_skills_provided: list[str]
    normalized_skills: list[str]
    recommendations: list[RoleRecommendation]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Convert container to dictionary."""
        return {
            "status": self.status,
            "user_skills_provided": self.user_skills_provided,
            "normalized_skills": self.normalized_skills,
            "recommendations": [r.to_dict() for r in self.recommendations],
            "warnings": self.warnings,
        }


class CareerRecommendationEngine:
    """Deterministic, explainable career recommendation engine."""

    def __init__(
        self,
        benchmarks_path: str | Path | None = None,
        alias_path: str | Path | None = None,
    ) -> None:
        """Initialize engine with role benchmarks and alias mapping."""
        bench_file = Path(benchmarks_path) if benchmarks_path else _benchmarks_json
        alias_file = Path(alias_path) if alias_path else _ref_dir / "skill_aliases.json"

        if not bench_file.is_file():
            raise FileNotFoundError(f"Role benchmarks file not found at: {bench_file}")

        self.benchmarks_data = json.loads(bench_file.read_text(encoding="utf-8"))
        self.roles_data: dict[str, Any] = self.benchmarks_data.get("roles", {})

        self.alias_lookup: dict[str, str] = {}
        if alias_file.is_file():
            raw_aliases = json.loads(alias_file.read_text(encoding="utf-8"))
            for canonical, aliases in raw_aliases.items():
                self.alias_lookup[canonical.casefold()] = canonical
                for a in aliases:
                    self.alias_lookup[a.casefold()] = canonical

    def normalize_skill(self, raw_skill: str) -> str:
        """Normalize raw skill name using alias dictionary."""
        trimmed = raw_skill.strip()
        if not trimmed:
            return ""
        cf = trimmed.casefold()
        if cf in self.alias_lookup:
            return self.alias_lookup[cf]
        return trimmed

    def recommend(
        self,
        user_skills: Sequence[str],
        target_career_preference: str | Sequence[str] | None = None,
        experience_level: str | None = None,
        education_background: str | None = None,
    ) -> CareerRecommendationResult:
        """Compute ranked career recommendations based on acquired skills."""
        # Clean and normalize user skills
        raw_list = [s.strip() for s in user_skills if s and s.strip()]
        normalized_set: set[str] = set()
        normalized_list: list[str] = []

        for s in raw_list:
            norm = self.normalize_skill(s)
            if norm and norm.casefold() not in {n.casefold() for n in normalized_set}:
                normalized_set.add(norm)
                normalized_list.append(norm)

        # Parse preferences
        preferences: set[str] = set()
        if target_career_preference:
            if isinstance(target_career_preference, str):
                preferences.add(target_career_preference.strip())
            else:
                preferences.update(p.strip() for p in target_career_preference if p and p.strip())

        warnings: list[str] = []
        if not normalized_list:
            # Handle empty profile
            warnings.append(
                "No technical skills were provided. To receive personalized career recommendations, please list your technical skills or upload a resume."
            )
            empty_recs = self._build_empty_recommendations(preferences)
            return CareerRecommendationResult(
                status="incomplete_profile",
                user_skills_provided=raw_list,
                normalized_skills=[],
                recommendations=empty_recs,
                warnings=warnings,
            )

        recommendations: list[RoleRecommendation] = []
        normalized_cf_set = {s.casefold() for s in normalized_set}

        for role_id, role_info in self.roles_data.items():
            role_name = role_info.get("role_name", role_id)
            eligible_jobs = role_info.get("eligible_job_count", 0)
            disclosed_jobs = role_info.get("skill_disclosed_job_count", 0)
            disclosure_rate = role_info.get("skill_disclosure_rate", 0.0)
            support_tier = role_info.get("support_tier", "LOW")
            benchmark_skills = role_info.get("skills", [])

            # Categorize benchmark skills
            matching_skills: list[MatchingSkillInfo] = []
            missing_critical: list[MatchingSkillInfo] = []
            missing_recommended: list[MatchingSkillInfo] = []

            critical_skills_all: list[dict[str, Any]] = []
            recommended_skills_all: list[dict[str, Any]] = []
            elective_skills_all: list[dict[str, Any]] = []

            for sk in benchmark_skills:
                sk_name = sk["skill_name"]
                demand_pct = sk["demand_percentage"]
                disc_pct = sk.get("disclosed_job_demand_pct", demand_pct)
                priority = sk["priority_category"]

                info = MatchingSkillInfo(
                    skill_name=sk_name,
                    demand_percentage=demand_pct,
                    disclosed_job_demand_pct=disc_pct,
                    priority_category=priority,
                )

                if priority == "CRITICAL":
                    critical_skills_all.append(sk)
                elif priority == "RECOMMENDED":
                    recommended_skills_all.append(sk)
                else:
                    elective_skills_all.append(sk)

                if sk_name.casefold() in normalized_cf_set:
                    matching_skills.append(info)
                else:
                    if priority == "CRITICAL":
                        missing_critical.append(info)
                    elif priority == "RECOMMENDED":
                        missing_recommended.append(info)

            # --- Scoring Calculation ---
            # 1. Critical Skill Coverage
            if critical_skills_all:
                matched_crit_count = sum(
                    1 for sk in critical_skills_all if sk["skill_name"].casefold() in normalized_cf_set
                )
                crit_coverage = (matched_crit_count / len(critical_skills_all)) * 100.0
            else:
                crit_coverage = 0.0

            # 2. Core Demand Coverage (Critical + Recommended)
            core_skills_all = critical_skills_all + recommended_skills_all
            if core_skills_all:
                total_core_demand = sum(s["demand_percentage"] for s in core_skills_all)
                matched_core_demand = sum(
                    s["demand_percentage"]
                    for s in core_skills_all
                    if s["skill_name"].casefold() in normalized_cf_set
                )
                core_coverage = (matched_core_demand / total_core_demand) * 100.0 if total_core_demand > 0 else 0.0
            else:
                total_core_demand = 0.0
                core_coverage = 0.0

            # 3. Breadth / Elective Bonus
            matched_elective_demand = sum(
                s["demand_percentage"]
                for s in elective_skills_all
                if s["skill_name"].casefold() in normalized_cf_set
            )
            breadth_bonus = min(MAX_BREADTH_BONUS, matched_elective_demand / 10.0)

            # Base score:
            # - For roles with critical skills: 0.50 * crit_coverage + 0.40 * core_coverage + breadth_bonus
            # - For roles without critical skills: allocate combined 0.90 weight directly to demand-weighted
            #   core coverage to prevent recommended skills from being counted twice.
            if critical_skills_all:
                base_score = (
                    WEIGHT_CRITICAL_COVERAGE * crit_coverage
                    + WEIGHT_CORE_DEMAND_COVERAGE * core_coverage
                    + breadth_bonus
                )
            else:
                base_score = (
                    (WEIGHT_CRITICAL_COVERAGE + WEIGHT_CORE_DEMAND_COVERAGE) * core_coverage
                    + breadth_bonus
                )

            # Objective match score (strictly skill fit only; preference is handled in sort key)
            is_pref = (role_id in preferences) or (role_name in preferences)
            final_score = min(100.0, max(0.0, round(base_score, 1)))

            # Build limitations & warnings
            role_limitations: list[str] = []
            if support_tier == "LOW":
                role_limitations.append(
                    f"Sample Notice: This career family has LOW empirical support in current job data ({eligible_jobs} postings). Skill demands should be treated with caution."
                )
            if disclosure_rate < 85.0:
                role_limitations.append(
                    f"Disclosure Notice: Only {disclosure_rate}% of postings in this role explicitly published skills."
                )

            # Formulate clear explainable text
            explanation = self._build_explanation(
                role_name=role_name,
                match_score=final_score,
                matching_skills=matching_skills,
                missing_critical=missing_critical,
                missing_recommended=missing_recommended,
                is_pref=is_pref,
            )

            recommendations.append(
                RoleRecommendation(
                    role_id=role_id,
                    role_name=role_name,
                    match_score=final_score,
                    matching_skills=matching_skills,
                    missing_critical_skills=missing_critical,
                    missing_recommended_skills=missing_recommended,
                    support_tier=support_tier,
                    eligible_job_count=eligible_jobs,
                    skill_disclosed_job_count=disclosed_jobs,
                    skill_disclosure_rate=disclosure_rate,
                    is_preferred=is_pref,
                    explanation=explanation,
                    limitations=role_limitations,
                )
            )

        # Sort recommendations:
        # 1. match_score DESC (objective skill fit)
        # 2. is_preferred DESC (preference acts strictly as a tie-breaker on equal scores)
        # 3. support_tier rank DESC (HIGH > MODERATE > LOW)
        # 4. role_name ASC (deterministic alphabetical resolution)
        tier_weight = {"HIGH": 3, "MODERATE": 2, "LOW": 1}
        recommendations.sort(
            key=lambda r: (
                -r.match_score,
                -int(r.is_preferred),
                -tier_weight.get(r.support_tier, 0),
                r.role_name,
            )
        )

        status = "success" if any(r.match_score > 0 for r in recommendations) else "no_skills_matched"
        if status == "no_skills_matched":
            warnings.append(
                "None of the provided skills matched benchmark requirements for JobRadar's technical roles."
            )

        return CareerRecommendationResult(
            status=status,
            user_skills_provided=raw_list,
            normalized_skills=normalized_list,
            recommendations=recommendations,
            warnings=warnings,
        )

    def _build_explanation(
        self,
        role_name: str,
        match_score: float,
        matching_skills: list[MatchingSkillInfo],
        missing_critical: list[MatchingSkillInfo],
        missing_recommended: list[MatchingSkillInfo],
        is_pref: bool,
    ) -> str:
        """Generate human-readable explanation of match score."""
        if match_score == 0.0 or not matching_skills:
            if missing_critical:
                crit_names = ", ".join(s.skill_name for s in missing_critical[:3])
                return f"No match found for {role_name}. Missing core competencies: {crit_names}."
            return f"No matching skills found for {role_name}."

        matched_names = ", ".join(s.skill_name for s in matching_skills[:4])
        parts = [f"Matches {len(matching_skills)} benchmark skills ({matched_names})."]

        if missing_critical:
            crit_names = ", ".join(s.skill_name for s in missing_critical[:2])
            parts.append(f"Key missing critical skills: {crit_names}.")
        elif missing_recommended:
            rec_names = ", ".join(s.skill_name for s in missing_recommended[:2])
            parts.append(f"High-value skills to add: {rec_names}.")
        else:
            parts.append("Excellent coverage of core benchmark requirements.")

        if is_pref:
            parts.append("Target career preference indicated (used as tie-breaker).")

        return " ".join(parts)

    def _build_empty_recommendations(self, preferences: set[str]) -> list[RoleRecommendation]:
        """Construct zero-score recommendations when student profile is empty."""
        empty_list: list[RoleRecommendation] = []
        for role_id, role_info in self.roles_data.items():
            role_name = role_info.get("role_name", role_id)
            eligible_jobs = role_info.get("eligible_job_count", 0)
            disclosed_jobs = role_info.get("skill_disclosed_job_count", 0)
            disclosure_rate = role_info.get("skill_disclosure_rate", 0.0)
            support_tier = role_info.get("support_tier", "LOW")
            is_pref = (role_id in preferences) or (role_name in preferences)

            empty_list.append(
                RoleRecommendation(
                    role_id=role_id,
                    role_name=role_name,
                    match_score=0.0,
                    matching_skills=[],
                    missing_critical_skills=[],
                    missing_recommended_skills=[],
                    support_tier=support_tier,
                    eligible_job_count=eligible_jobs,
                    skill_disclosed_job_count=disclosed_jobs,
                    skill_disclosure_rate=disclosure_rate,
                    is_preferred=is_pref,
                    explanation="No skills provided to evaluate fit.",
                    limitations=[],
                )
            )
        tier_weight = {"HIGH": 3, "MODERATE": 2, "LOW": 1}
        empty_list.sort(key=lambda r: (-int(r.is_preferred), -tier_weight.get(r.support_tier, 0), r.role_name))
        return empty_list
