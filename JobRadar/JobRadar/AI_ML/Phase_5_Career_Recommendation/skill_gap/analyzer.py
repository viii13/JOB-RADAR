"""Skill-Gap Analysis and Role Readiness Evaluation.

Stage 5.4 — Compares acquired student skills against empirical role benchmarks,
identifies missing critical, recommended, and elective competencies, and calculates
an explainable readiness score.
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


@dataclass(frozen=True)
class BenchmarkSkillDetail:
    """Detailed benchmark metadata for a skill in a specific role."""

    skill_name: str
    demand_percentage: float
    disclosed_job_demand_pct: float
    priority_category: str
    distinct_job_count: int


@dataclass(frozen=True)
class SkillGapResult:
    """Complete results of skill-gap analysis for a target technical career."""

    role_id: str
    role_name: str
    readiness_score: float  # 0.0 to 100.0
    acquired_skills: list[BenchmarkSkillDetail]
    missing_critical_skills: list[BenchmarkSkillDetail]
    missing_recommended_skills: list[BenchmarkSkillDetail]
    missing_elective_skills: list[BenchmarkSkillDetail]
    transferable_skills: list[str]
    support_tier: str
    eligible_job_count: int
    skill_disclosed_job_count: int
    skill_disclosure_rate: float
    methodology_notes: list[str]
    limitations: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Convert result container to serializable dictionary."""
        return {
            "role_id": self.role_id,
            "role_name": self.role_name,
            "readiness_score": self.readiness_score,
            "acquired_skills": [asdict(s) for s in self.acquired_skills],
            "missing_critical_skills": [asdict(s) for s in self.missing_critical_skills],
            "missing_recommended_skills": [asdict(s) for s in self.missing_recommended_skills],
            "missing_elective_skills": [asdict(s) for s in self.missing_elective_skills],
            "transferable_skills": self.transferable_skills,
            "support_tier": self.support_tier,
            "eligible_job_count": self.eligible_job_count,
            "skill_disclosed_job_count": self.skill_disclosed_job_count,
            "skill_disclosure_rate": self.skill_disclosure_rate,
            "methodology_notes": self.methodology_notes,
            "limitations": self.limitations,
        }


class SkillGapAnalyzer:
    """Analyzes differences between student competencies and role benchmarks."""

    def __init__(
        self,
        benchmarks_path: str | Path | None = None,
        alias_path: str | Path | None = None,
    ) -> None:
        """Initialize analyzer with role benchmarks and alias mapping."""
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

    def analyze_gap(
        self,
        user_skills: Sequence[str],
        target_role_id: str,
    ) -> SkillGapResult:
        """Perform comprehensive skill gap analysis against a selected target role."""
        if not target_role_id or target_role_id not in self.roles_data:
            valid_roles = ", ".join(sorted(self.roles_data.keys()))
            raise ValueError(
                f"Target role '{target_role_id}' is not an approved technical role family. Supported roles are: {valid_roles}"
            )

        role_info = self.roles_data[target_role_id]
        role_name = role_info.get("role_name", target_role_id)
        eligible_jobs = role_info.get("eligible_job_count", 0)
        disclosed_jobs = role_info.get("skill_disclosed_job_count", 0)
        disclosure_rate = role_info.get("skill_disclosure_rate", 0.0)
        support_tier = role_info.get("support_tier", "LOW")
        benchmark_skills = role_info.get("skills", [])

        # Normalize student skills
        norm_user_skills: set[str] = set()
        for s in user_skills:
            if s and s.strip():
                norm = self.normalize_skill(s)
                if norm:
                    norm_user_skills.add(norm)

        user_cf_set = {s.casefold() for s in norm_user_skills}

        acquired_skills: list[BenchmarkSkillDetail] = []
        missing_critical: list[BenchmarkSkillDetail] = []
        missing_recommended: list[BenchmarkSkillDetail] = []
        missing_elective: list[BenchmarkSkillDetail] = []

        benchmark_skill_names_cf: set[str] = set()

        for sk in benchmark_skills:
            sk_name = sk["skill_name"]
            benchmark_skill_names_cf.add(sk_name.casefold())

            detail = BenchmarkSkillDetail(
                skill_name=sk_name,
                demand_percentage=sk["demand_percentage"],
                disclosed_job_demand_pct=sk.get("disclosed_job_demand_pct", sk["demand_percentage"]),
                priority_category=sk["priority_category"],
                distinct_job_count=sk["distinct_job_count"],
            )

            if sk_name.casefold() in user_cf_set:
                acquired_skills.append(detail)
            else:
                if detail.priority_category == "CRITICAL":
                    missing_critical.append(detail)
                elif detail.priority_category == "RECOMMENDED":
                    missing_recommended.append(detail)
                else:
                    missing_elective.append(detail)

        # Identify transferable skills (user skills not present in this role's benchmark)
        transferable = [
            s for s in sorted(norm_user_skills) if s.casefold() not in benchmark_skill_names_cf
        ]

        # Calculate readiness score
        readiness_score = self._calculate_readiness_score(
            benchmark_skills=benchmark_skills,
            user_cf_set=user_cf_set,
        )

        methodology_notes = [
            "Readiness Score Formula: Evaluates demand-weighted coverage of role core competencies (Critical weight=2.0, Recommended weight=1.0).",
            "Scope: Readiness score measures empirical alignment with JobRadar job postings; it does NOT represent a statistical probability of receiving a job offer.",
            "Demand Percentages: Primary demand uses all eligible role jobs as denominator; disclosed percentage isolates postings that published structured skills.",
        ]

        limitations: list[str] = []
        if support_tier == "LOW":
            limitations.append(
                f"Sample Warning: '{role_name}' has LOW empirical support ({eligible_jobs} postings in JobRadar dataset). Skill distributions should be treated as indicative rather than comprehensive."
            )
        if disclosure_rate < 85.0:
            limitations.append(
                f"Disclosure Notice: Only {disclosure_rate}% of postings in this role explicitly disclosed skills in their postings."
            )
        if not norm_user_skills:
            limitations.append(
                "Profile Incomplete: No acquired skills were provided. All role competencies are classified as gaps."
            )

        return SkillGapResult(
            role_id=target_role_id,
            role_name=role_name,
            readiness_score=readiness_score,
            acquired_skills=acquired_skills,
            missing_critical_skills=missing_critical,
            missing_recommended_skills=missing_recommended,
            missing_elective_skills=missing_elective,
            transferable_skills=transferable,
            support_tier=support_tier,
            eligible_job_count=eligible_jobs,
            skill_disclosed_job_count=disclosed_jobs,
            skill_disclosure_rate=disclosure_rate,
            methodology_notes=methodology_notes,
            limitations=limitations,
        )

    def _calculate_readiness_score(
        self,
        benchmark_skills: list[dict[str, Any]],
        user_cf_set: set[str],
    ) -> float:
        """Calculate weighted readiness percentage against role core requirements."""
        if not benchmark_skills:
            return 0.0

        # Filter to core skills (Critical >= 50% or Recommended >= 20%)
        critical = [s for s in benchmark_skills if s.get("priority_category") == "CRITICAL"]
        recommended = [s for s in benchmark_skills if s.get("priority_category") == "RECOMMENDED"]

        core_skills = critical + recommended
        if not core_skills:
            # Fallback if no skills exceed 20%: use top 5 skills
            core_skills = benchmark_skills[:5]

        total_weighted_points = 0.0
        acquired_weighted_points = 0.0

        for sk in core_skills:
            p_cat = sk.get("priority_category", "RECOMMENDED")
            weight = 2.0 if p_cat == "CRITICAL" else 1.0
            demand = sk.get("demand_percentage", 0.0)

            points = weight * demand
            total_weighted_points += points

            if sk["skill_name"].casefold() in user_cf_set:
                acquired_weighted_points += points

        if total_weighted_points == 0.0:
            return 0.0

        raw_score = (acquired_weighted_points / total_weighted_points) * 100.0
        return round(min(100.0, max(0.0, raw_score)), 1)
