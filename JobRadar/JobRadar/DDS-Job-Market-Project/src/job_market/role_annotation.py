"""Create deterministic, human-label-ready samples from current job versions."""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import re
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Job, JobSkill, JobVersion, Skill, Source


ANNOTATION_COLUMNS = (
    "annotation_record_id",
    "source_code",
    "job_id",
    "job_version_id",
    "source_job_id",
    "origin_record_key",
    "title",
    "company",
    "location",
    "description_excerpt",
    "human_verified_role_label",
    "annotation_notes",
)
DEFAULT_SOURCE_CODES = ("historical_2025_xlsx", "adzuna_india")
DEFAULT_SAMPLE_PER_SOURCE = 60
DEFAULT_RANDOM_SEED = 20261111
DESCRIPTION_EXCERPT_LENGTH = 600
TARGETED_ANNOTATION_COLUMNS = ANNOTATION_COLUMNS + (
    "candidate_target_family",
    "selection_rule",
)
TARGETED_SAMPLE_PER_FAMILY = 18
TARGETED_RANDOM_SEED = 20261112
ADZUNA_DIVERSITY_TARGET = 3

# These rules identify annotation candidates only.  They never write a gold
# label; a human annotator makes the final decision in the CSV.
TARGET_ROLE_RULES = {
    "data_scientist_advanced_analytics": {
        "title_terms": ("data scientist", "statistician", "research scientist", "quantitative analyst", "analytics scientist"),
        "skill_terms": ("data science", "data analysis"),
        "description_terms": ("statistical modeling", "hypothesis testing", "a/b testing", "forecasting", "predictive analytics", "experimentation"),
    },
    "machine_learning_ai_engineer": {
        "title_terms": ("machine learning", "ml engineer", "ai engineer", "artificial intelligence", "computer vision", "nlp engineer", "generative ai", "genai"),
        "skill_terms": ("machine learning", "deep learning", "nlp", "computer vision", "tensorflow", "pytorch"),
        "description_terms": ("machine learning", "model deployment", "deep learning", "neural network", "natural language processing", "large language model", "generative ai", "computer vision"),
    },
    "data_engineer_big_data_platform": {
        "title_terms": ("data engineer", "big data engineer", "etl developer", "etl engineer", "data warehouse engineer", "data platform engineer"),
        "skill_terms": ("hadoop", "kafka", "spark", "snowflake", "data modeling"),
        "description_terms": ("data pipeline", "etl", "elt", "data warehouse", "apache spark", "kafka", "airflow", "databricks", "snowflake"),
    },
    "data_analyst_business_intelligence": {
        "title_terms": ("data analyst", "business intelligence", "bi developer", "bi analyst", "tableau developer", "reporting analyst", "analytics analyst"),
        "skill_terms": ("power bi", "tableau", "excel", "data analysis"),
        "description_terms": ("power bi", "tableau", "dashboard", "reporting", "business intelligence", "kpi"),
    },
}


@dataclass(frozen=True)
class AnnotationSampleResult:
    """Summary of a generated annotation CSV."""

    output_path: Path
    records_written: int
    records_by_source: dict[str, int]


@dataclass(frozen=True)
class TargetedAnnotationSampleResult:
    """Reconciliation details for a rule-selected, human-label-ready batch."""

    output_path: Path
    report_path: Path
    records_written: int
    selected_by_family: dict[str, int]
    available_by_family: dict[str, int]
    records_by_source: dict[str, int]
    excluded_original_records: int
    ambiguous_candidate_records: int
    unmatched_candidate_records: int


def _compact_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _deduplication_key(version: JobVersion) -> tuple[str, str, str]:
    """Suppress exact and near-identical copies without assigning a role."""
    return (
        _compact_text(version.title).casefold(),
        _compact_text(version.company_name).casefold(),
        _compact_text(version.job_description)[:DESCRIPTION_EXCERPT_LENGTH].casefold(),
    )


def _stable_rank(seed: int, source_code: str, identity_key: str) -> str:
    payload = f"{seed}:{source_code}:{identity_key}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _annotation_row(source: Source, job: Job, version: JobVersion) -> dict[str, str]:
    annotation_id = hashlib.sha256(
        f"{source.code}:{job.identity_key}:{version.id}".encode("utf-8")
    ).hexdigest()[:20]
    return {
        "annotation_record_id": annotation_id,
        "source_code": source.code,
        "job_id": str(job.id),
        "job_version_id": str(version.id),
        "source_job_id": job.source_job_id or "",
        "origin_record_key": version.origin_record_key,
        "title": _compact_text(version.title),
        "company": _compact_text(version.company_name),
        "location": _compact_text(version.location),
        "description_excerpt": _compact_text(version.job_description)[:DESCRIPTION_EXCERPT_LENGTH],
        "human_verified_role_label": "",
        "annotation_notes": "",
    }


def _rule_evidence(
    version: JobVersion, skill_names: set[str], rule: dict[str, tuple[str, ...]]
) -> tuple[int, str] | None:
    """Return an explainable candidate score, never a role prediction."""
    title = _compact_text(version.title).casefold()
    description = _compact_text(version.job_description).casefold()
    title_hits = [term for term in rule["title_terms"] if term in title]
    skill_hits = [term for term in rule["skill_terms"] if term in skill_names]
    description_hits = [term for term in rule["description_terms"] if term in description]
    if not (title_hits or skill_hits or description_hits):
        return None
    score = 100 * len(title_hits) + 10 * len(skill_hits) + len(description_hits)
    evidence: list[str] = []
    if title_hits:
        evidence.append("title=" + ", ".join(title_hits))
    if skill_hits:
        evidence.append("skills=" + ", ".join(skill_hits))
    if description_hits:
        evidence.append("description=" + ", ".join(description_hits))
    return score, "; ".join(evidence)


def _original_sample_exclusions(path: Path) -> tuple[set[str], set[tuple[str, str, str]]]:
    """Load stable IDs and excerpt keys from the immutable original sample."""
    if not path.is_file():
        raise FileNotFoundError(f"Original annotation sample was not found: {path}")
    with path.open(encoding="utf-8", newline="") as sample_file:
        rows = list(csv.DictReader(sample_file))
    required = {"job_version_id", "title", "company", "description_excerpt"}
    if not rows or not required.issubset(rows[0]):
        raise ValueError("Original annotation sample is missing required traceability columns")
    version_ids = {row["job_version_id"] for row in rows if row["job_version_id"]}
    duplicate_keys = {
        (
            _compact_text(row["title"]).casefold(),
            _compact_text(row["company"]).casefold(),
            _compact_text(row["description_excerpt"])[:DESCRIPTION_EXCERPT_LENGTH].casefold(),
        )
        for row in rows
    }
    return version_ids, duplicate_keys


def _targeted_report(result: TargetedAnnotationSampleResult) -> str:
    """Render an audit-friendly report beside the targeted CSV."""
    lines = [
        "# Targeted Data/AI Annotation Batch Report",
        "",
        "## Selection rules",
        "",
        "Candidates are selected only when a transparent title, extracted-skill, or description-term rule matches. "
        "Title matches rank above skills, and skills rank above description-only matches. "
        "`candidate_target_family` and `selection_rule` are selection aids, not human-verified labels.",
        "",
        "## Counts by target family",
        "",
        "| Family ID | Eligible candidates after original-sample exclusions | Selected |",
        "| --- | ---: | ---: |",
    ]
    for family in TARGET_ROLE_RULES:
        lines.append(f"| {family} | {result.available_by_family[family]} | {result.selected_by_family[family]} |")
    lines.extend(["", "## Source distribution", ""])
    for source, count in sorted(result.records_by_source.items()):
        lines.append(f"- {source}: {count}")
    lines.extend([
        "",
        "## Duplicate and ambiguity checks",
        "",
        f"- Excluded because they were already in the original 120-record sample: {result.excluded_original_records}",
        "- Exact title/company/description-excerpt duplicates were excluded against the original sample and within this batch.",
        f"- Candidates matching more than one target rule set: {result.ambiguous_candidate_records}",
        "- Ambiguous candidates may appear in this batch once only; their human label remains blank for reviewer judgment.",
        f"- Current historical/Adzuna records with no target-rule match after original-sample exclusions: {result.unmatched_candidate_records}",
        "",
        "## Limitations",
        "",
        "- This is a targeted, rule-selected batch, so it is deliberately not representative of the overall job-market distribution.",
        "- Description and skill terminology can produce false positives; annotators must rely on the guide and enter the final gold label themselves.",
        "- Adzuna has fewer available Data/AI candidates than the historical source, so source balance is improved where available but not forced.",
        "",
    ])
    return "\n".join(lines)


def generate_annotation_sample(
    session: Session,
    output_path: str | Path,
    *,
    source_codes: tuple[str, ...] = DEFAULT_SOURCE_CODES,
    per_source: int = DEFAULT_SAMPLE_PER_SOURCE,
    seed: int = DEFAULT_RANDOM_SEED,
) -> AnnotationSampleResult:
    """Write a deterministic, source-balanced CSV of current job versions.

    No role labels are inferred or written.  The function only reads job data
    and writes the requested annotation CSV.
    """
    if per_source < 1:
        raise ValueError("per_source must be at least 1")

    rows: list[dict[str, str]] = []
    records_by_source: dict[str, int] = {}
    for source_code in source_codes:
        candidates = session.execute(
            select(Source, Job, JobVersion)
            .join(Job, Job.source_id == Source.id)
            .join(JobVersion, JobVersion.job_id == Job.id)
            .where(Source.code == source_code, JobVersion.is_current.is_(True))
        ).all()
        ranked = sorted(
            candidates,
            key=lambda item: _stable_rank(seed, source_code, item[1].identity_key),
        )
        seen: set[tuple[str, str, str]] = set()
        selected = 0
        for source, job, version in ranked:
            duplicate_key = _deduplication_key(version)
            if duplicate_key in seen:
                continue
            seen.add(duplicate_key)
            rows.append(_annotation_row(source, job, version))
            selected += 1
            if selected == per_source:
                break
        records_by_source[source_code] = selected

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=ANNOTATION_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return AnnotationSampleResult(destination, len(rows), records_by_source)


def generate_targeted_annotation_sample(
    session: Session,
    output_path: str | Path,
    *,
    original_sample_path: str | Path,
    report_path: str | Path,
    per_family: int = TARGETED_SAMPLE_PER_FAMILY,
    seed: int = TARGETED_RANDOM_SEED,
) -> TargetedAnnotationSampleResult:
    """Write a separate Data/AI candidate batch without inferring gold labels.

    The rules expose why a record was selected.  They are deliberately kept
    separate from the blank human-verified label column so future training can
    distinguish selection metadata from annotation ground truth.
    """
    if per_family < 1:
        raise ValueError("per_family must be at least 1")
    original_ids, original_keys = _original_sample_exclusions(Path(original_sample_path))
    source_codes = DEFAULT_SOURCE_CODES
    candidates = session.execute(
        select(Source, Job, JobVersion)
        .join(Job, Job.source_id == Source.id)
        .join(JobVersion, JobVersion.job_id == Job.id)
        .where(Source.code.in_(source_codes), JobVersion.is_current.is_(True))
    ).all()
    version_skills: dict[int, set[str]] = defaultdict(set)
    for version_id, skill_name in session.execute(
        select(JobSkill.job_version_id, Skill.name).join(Skill, Skill.id == JobSkill.skill_id)
    ):
        version_skills[version_id].add(skill_name.casefold())

    eligible: dict[str, list[tuple[int, str, Source, Job, JobVersion]]] = {
        family: [] for family in TARGET_ROLE_RULES
    }
    excluded_original_records = 0
    ambiguity_by_version: dict[int, int] = defaultdict(int)
    seen_candidate_versions: set[int] = set()
    unmatched_candidate_records = 0
    for source, job, version in candidates:
        duplicate_key = _deduplication_key(version)
        if str(version.id) in original_ids or duplicate_key in original_keys:
            if version.id not in seen_candidate_versions:
                excluded_original_records += 1
                seen_candidate_versions.add(version.id)
            continue
        matches = 0
        for family, rule in TARGET_ROLE_RULES.items():
            evidence = _rule_evidence(version, version_skills[version.id], rule)
            if evidence is None:
                continue
            matches += 1
            score, reason = evidence
            eligible[family].append((score, reason, source, job, version))
            ambiguity_by_version[version.id] += 1
        if matches == 0:
            unmatched_candidate_records += 1

    selected_rows: list[dict[str, str]] = []
    selected_by_family: dict[str, int] = {}
    selected_versions: set[int] = set()
    selected_keys: set[tuple[str, str, str]] = set()
    for family in TARGET_ROLE_RULES:
        ranked = sorted(
            eligible[family],
            key=lambda item: (-item[0], _stable_rank(seed, item[2].code, item[3].identity_key)),
        )
        selected = 0
        # Use up to three genuine Adzuna candidates first when available. The
        # remaining places are filled by the overall deterministic ranking.
        first_pass = [item for item in ranked if item[2].code == "adzuna_india"]
        for candidate_pool, limit in ((first_pass, min(ADZUNA_DIVERSITY_TARGET, per_family)), (ranked, per_family)):
            for score, reason, source, job, version in candidate_pool:
                duplicate_key = _deduplication_key(version)
                if selected == limit or selected == per_family:
                    break
                if version.id in selected_versions or duplicate_key in selected_keys:
                    continue
                row = _annotation_row(source, job, version)
                row["candidate_target_family"] = family
                row["selection_rule"] = reason
                selected_rows.append(row)
                selected_versions.add(version.id)
                selected_keys.add(duplicate_key)
                selected += 1
        selected_by_family[family] = selected

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=TARGETED_ANNOTATION_COLUMNS)
        writer.writeheader()
        writer.writerows(selected_rows)
    records_by_source = dict(sorted(Counter(row["source_code"] for row in selected_rows).items()))
    result = TargetedAnnotationSampleResult(
        output_path=destination,
        report_path=Path(report_path),
        records_written=len(selected_rows),
        selected_by_family=selected_by_family,
        available_by_family={family: len(items) for family, items in eligible.items()},
        records_by_source=records_by_source,
        excluded_original_records=excluded_original_records,
        ambiguous_candidate_records=sum(count > 1 for count in ambiguity_by_version.values()),
        unmatched_candidate_records=unmatched_candidate_records,
    )
    result.report_path.parent.mkdir(parents=True, exist_ok=True)
    result.report_path.write_text(_targeted_report(result), encoding="utf-8")
    return result


def create_blinded_annotation_batch(
    source_path: str | Path,
    output_path: str | Path,
) -> AnnotationSampleResult:
    """Create a blinded copy of an annotation batch by removing candidate metadata.

    Preserves row order, IDs, and blank label fields while keeping only the
    canonical ``ANNOTATION_COLUMNS``. Does not alter the source file.
    """
    src = Path(source_path)
    dest = Path(output_path)
    if not src.exists():
        raise FileNotFoundError(f"Source annotation file does not exist: {src}")

    with src.open("r", encoding="utf-8", newline="") as infile:
        reader = csv.DictReader(infile)
        rows: list[dict[str, str]] = []
        source_codes: list[str] = []
        for row in reader:
            blinded_row = {col: row.get(col, "") for col in ANNOTATION_COLUMNS}
            rows.append(blinded_row)
            if row.get("source_code"):
                source_codes.append(row["source_code"])

    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8", newline="") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=ANNOTATION_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    records_by_source = dict(sorted(Counter(source_codes).items()))
    return AnnotationSampleResult(
        output_path=dest,
        records_written=len(rows),
        records_by_source=records_by_source,
    )

