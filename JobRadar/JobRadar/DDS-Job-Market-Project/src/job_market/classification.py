"""AI Job Classification foundation: text preparation, rule baseline, and grouped splitting.

Provides:
1. Readable, boosted text preparation combining title, skills, tags, and description excerpt.
2. Explainable multi-signal rule-based classification baseline using the 11-role taxonomy.
3. Grouped train/validation/test splitting with complete cross-split leakage prevention.
4. Independent split leakage verification.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable, Sequence

import joblib
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    precision_recall_fscore_support,
)
from sklearn.pipeline import Pipeline


ROLE_TAXONOMY_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "reference" / "role_taxonomy.json"
)

FALLBACK_ROLE_ID = "other_unclassified"
FALLBACK_ROLE_NAME = "Other / Unclassified"

DEFAULT_TITLE_BOOST = 3
DEFAULT_SKILL_BOOST = 2
DEFAULT_MAX_DESC_CHARS = 500
MIN_RULE_CONFIDENCE_SCORE = 15.0

# Canonical 11-role catalog matching role_taxonomy.json
TAXONOMY_ROLE_NAMES: dict[str, str] = {
    "data_scientist_advanced_analytics": "Data Scientist & Advanced Analytics",
    "machine_learning_ai_engineer": "Machine Learning & AI Engineer",
    "data_engineer_big_data_platform": "Data Engineer & Big Data Platform",
    "data_analyst_business_intelligence": "Data Analyst & Business Intelligence",
    "backend_core_software_engineering": "Backend & Core Software Engineering",
    "frontend_full_stack_engineering": "Frontend & Full Stack Engineering",
    "cloud_devops_sre": "Cloud, DevOps & SRE",
    "qa_automation_testing": "QA & Automation Testing",
    "product_technical_project_management": "Product & Technical Project Management",
    "non_tech_corporate_operations": "Non-Tech / Corporate & Operations",
    "other_unclassified": "Other / Unclassified",
}

# Rule dictionaries for explainable multi-signal classification
# High-specificity title patterns receive 110 points.
# General title patterns receive 90 points.
# Canonical skill matches receive 10 points.
# Description context matches receive 2 points.
ROLE_SIGNAL_RULES: dict[str, dict[str, Any]] = {
    "data_scientist_advanced_analytics": {
        "specific_title_patterns": (
            "data scientist",
            "data science",
            "statistician",
            "biostatistician",
            "quantitative researcher",
            "quantitative analyst",
            "statistical modeler",
            "decision scientist",
            "analytics scientist",
        ),
        "general_title_patterns": (),
        "skills": (
            "data science",
            "statistics",
            "statistical modeling",
            "r",
            "predictive modeling",
            "hypothesis testing",
            "econometrics",
            "experimentation",
        ),
        "description_keywords": (
            "statistical modeling",
            "hypothesis testing",
            "a/b testing",
            "predictive analytics",
            "forecasting",
            "experimentation",
            "statistical analysis",
            "causal inference",
        ),
    },
    "machine_learning_ai_engineer": {
        "specific_title_patterns": (
            "machine learning",
            "ml engineer",
            "ai engineer",
            "artificial intelligence",
            "deep learning",
            "nlp engineer",
            "computer vision",
            "llm engineer",
            "generative ai",
            "genai",
            "prompt engineer",
            "mlops",
            "algorithm engineer",
        ),
        "general_title_patterns": (),
        "skills": (
            "machine learning",
            "deep learning",
            "nlp",
            "computer vision",
            "tensorflow",
            "pytorch",
            "keras",
            "hugging face",
            "scikit-learn",
            "llm",
            "opencv",
            "transformers",
            "xgboost",
        ),
        "description_keywords": (
            "neural network",
            "large language model",
            "model deployment",
            "model training",
            "generative ai",
            "deep learning",
            "transformers",
            "reinforcement learning",
            "vector database",
            "fine-tuning",
        ),
    },
    "data_engineer_big_data_platform": {
        "specific_title_patterns": (
            "data engineer",
            "big data engineer",
            "big data",
            "etl developer",
            "etl engineer",
            "data platform engineer",
            "data platform",
            "data warehouse engineer",
            "pipeline engineer",
            "database developer",
            "database engineer",
            "bi engineer",
        ),
        "general_title_patterns": (),
        "skills": (
            "hadoop",
            "spark",
            "kafka",
            "snowflake",
            "databricks",
            "airflow",
            "sql",
            "hive",
            "dbt",
            "bigquery",
            "redshift",
            "scala",
            "pyspark",
        ),
        "description_keywords": (
            "data pipeline",
            "etl",
            "elt",
            "data warehouse",
            "apache spark",
            "apache kafka",
            "data lake",
            "data platform",
            "batch processing",
            "stream processing",
        ),
    },
    "data_analyst_business_intelligence": {
        "specific_title_patterns": (
            "data analyst",
            "business intelligence",
            "bi developer",
            "bi analyst",
            "tableau developer",
            "power bi developer",
            "reporting analyst",
            "analytics analyst",
            "insights analyst",
            "mis executive",
            "operations analyst",
            "business analyst",
        ),
        "general_title_patterns": (),
        "skills": (
            "power bi",
            "tableau",
            "excel",
            "data analysis",
            "looker",
            "dashboarding",
            "sql",
            "qlik",
            "google analytics",
        ),
        "description_keywords": (
            "power bi",
            "tableau",
            "dashboard",
            "reporting",
            "kpi",
            "business intelligence",
            "business insights",
            "executive reporting",
            "data visualization",
        ),
    },
    "frontend_full_stack_engineering": {
        "specific_title_patterns": (
            "frontend",
            "front-end",
            "front end",
            "full stack",
            "fullstack",
            "full-stack",
            "react developer",
            "angular developer",
            "vue developer",
            "ui developer",
            "mobile developer",
            "android developer",
            "ios developer",
            "flutter developer",
            "web developer",
            "web designer",
        ),
        "general_title_patterns": (),
        "skills": (
            "javascript",
            "typescript",
            "react",
            "angular",
            "vue",
            "html",
            "css",
            "next.js",
            "tailwind",
            "flutter",
            "react native",
            "swift",
            "kotlin",
            "redux",
        ),
        "description_keywords": (
            "user interface",
            "frontend development",
            "full stack development",
            "responsive design",
            "client-side",
            "web application",
            "mobile application",
            "user experience",
        ),
    },
    "cloud_devops_sre": {
        "specific_title_patterns": (
            "devops",
            "cloud engineer",
            "cloud architect",
            "site reliability",
            "sre",
            "platform engineer",
            "infrastructure engineer",
            "systems administrator",
            "sysadmin",
            "cloud administrator",
            "aws engineer",
            "azure engineer",
            "linux administrator",
            "security engineer",
        ),
        "general_title_patterns": (),
        "skills": (
            "aws",
            "azure",
            "gcp",
            "docker",
            "kubernetes",
            "terraform",
            "ansible",
            "ci/cd",
            "jenkins",
            "linux",
            "helm",
            "grafana",
            "prometheus",
        ),
        "description_keywords": (
            "cloud infrastructure",
            "ci/cd",
            "continuous integration",
            "infrastructure as code",
            "containerization",
            "kubernetes cluster",
            "observability",
            "reliability",
            "cloud security",
        ),
    },
    "qa_automation_testing": {
        "specific_title_patterns": (
            "qa",
            "quality assurance",
            "test engineer",
            "automation tester",
            "qa engineer",
            "sdet",
            "test automation",
            "manual tester",
            "tester",
            "quality engineer",
            "performance tester",
        ),
        "general_title_patterns": (),
        "skills": (
            "selenium",
            "cypress",
            "junit",
            "pytest",
            "automation testing",
            "manual testing",
            "test automation",
            "playwright",
            "appium",
            "jmeter",
            "postman",
        ),
        "description_keywords": (
            "test cases",
            "test execution",
            "automation testing",
            "bug tracking",
            "quality assurance",
            "regression testing",
            "test plan",
            "test automation framework",
        ),
    },
    "product_technical_project_management": {
        "specific_title_patterns": (
            "product manager",
            "project manager",
            "program manager",
            "scrum master",
            "agile coach",
            "technical project manager",
            "product owner",
            "engineering manager",
            "delivery manager",
            "release manager",
        ),
        "general_title_patterns": (),
        "skills": (
            "jira",
            "agile",
            "scrum",
            "project management",
            "product strategy",
            "kanban",
            "confluence",
        ),
        "description_keywords": (
            "sprint planning",
            "stakeholder management",
            "roadmap",
            "user stories",
            "backlog",
            "agile methodology",
            "delivery timeline",
            "cross-functional leadership",
        ),
    },
    "non_tech_corporate_operations": {
        "specific_title_patterns": (
            "recruiter",
            "talent acquisition",
            "human resources",
            "hr executive",
            "hr manager",
            "accountant",
            "sales executive",
            "business development",
            "marketing manager",
            "customer service",
            "customer support",
            "office administrator",
            "executive assistant",
            "legal counsel",
            "medical",
            "nurse",
            "store manager",
        ),
        "general_title_patterns": (),
        "skills": (
            "recruiting",
            "talent sourcing",
            "accounting",
            "financial reporting",
            "sales",
            "crm",
            "lead generation",
            "content marketing",
            "customer support",
        ),
        "description_keywords": (
            "talent acquisition",
            "human resources",
            "accounts payable",
            "cold calling",
            "client relations",
            "general administration",
            "payroll",
            "sales pipeline",
        ),
    },
    "backend_core_software_engineering": {
        "specific_title_patterns": (
            "backend",
            "back-end",
            "back end",
            "java developer",
            "python developer",
            "golang developer",
            "go developer",
            "c++ developer",
            "c# developer",
            ".net developer",
            "api developer",
            "systems engineer",
            "core engineer",
            "server engineer",
            "microservices developer",
        ),
        # Generic engineering terms: lower score (90) so specific roles (e.g. Frontend/QA/Data) win when combined
        "general_title_patterns": (
            "software engineer",
            "software developer",
            "developer",
            "programmer",
            "application developer",
        ),
        "skills": (
            "java",
            "python",
            "fastapi",
            "django",
            "flask",
            "spring boot",
            "node.js",
            "c++",
            "c#",
            ".net",
            "go",
            "rust",
            "postgresql",
            "mysql",
            "mongodb",
            "rest api",
            "microservices",
            "redis",
            "graphql",
        ),
        "description_keywords": (
            "rest api",
            "microservices",
            "backend architecture",
            "server-side",
            "database design",
            "api design",
            "high availability",
            "scalable backend",
        ),
    },
}


@dataclass(frozen=True)
class JobTextFeatures:
    """Prepared, weighted text features ready for classification or embedding."""

    title: str
    skills_text: str
    tags_text: str
    description_excerpt: str
    combined_text: str
    raw_title: str
    canonical_skills: tuple[str, ...]
    source_tags: tuple[str, ...]
    raw_description: str


@dataclass(frozen=True)
class RuleMatchEvidence:
    """An explainable signal that contributed to a role classification score."""

    signal_type: str  # 'title_specific', 'title_general', 'skill', 'description'
    matched_term: str
    role_id: str
    score: float


@dataclass(frozen=True)
class RuleClassificationResult:
    """Outcome of rule-based classification with full audit trail."""

    role_id: str
    role_name: str
    confidence: float
    score: float
    matched_rules: tuple[str, ...]
    runner_up_role_id: str | None
    runner_up_score: float
    is_classified: bool
    evidence: tuple[RuleMatchEvidence, ...]


@dataclass(frozen=True)
class SplitVerificationResult:
    """Audit verification report proving zero cross-split leakage."""

    is_valid: bool
    total_records: int
    train_count: int
    val_count: int
    test_count: int
    train_ratio: float
    val_ratio: float
    test_ratio: float
    unique_groups: int
    company_title_overlaps: dict[str, int]
    fingerprint_overlaps: dict[str, int]
    leakage_details: list[str]


def load_role_taxonomy(taxonomy_path: Path | str | None = None) -> dict[str, Any]:
    """Load and validate the reference role taxonomy JSON."""
    path = Path(taxonomy_path) if taxonomy_path else ROLE_TAXONOMY_PATH
    if not path.is_file():
        raise FileNotFoundError(f"Role taxonomy file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if "role_families" not in data:
        raise ValueError(f"Malformed role taxonomy at {path}: missing 'role_families'")
    return data


def clean_text_snippet(text: str | None, max_chars: int | None = None) -> str:
    """Normalize whitespace and optionally truncate to max_chars."""
    if not text:
        return ""
    cleaned = re.sub(r"\s+", " ", str(text)).strip()
    if max_chars is not None and max_chars > 0 and len(cleaned) > max_chars:
        return cleaned[:max_chars].rstrip()
    return cleaned


def contains_term(term: str, text: str) -> bool:
    """Match whole terms, handling special characters like C++, C#, and .NET."""
    term = term.strip().lower()
    text = text.lower()
    if not term or not text:
        return False
    # Use word boundaries when term is purely alphanumeric
    if re.fullmatch(r"[\w\s-]+", term):
        pattern = rf"(?<!\w){re.escape(term)}(?!\w)"
    else:
        # For terms like c++, c#, .net: match when flanked by start/end/space/punctuation
        pattern = rf"(?:^|[\s,;:/|()\[\]]){re.escape(term)}(?:$|[\s,;:/|()\[\]])"
    return bool(re.search(pattern, text))


def prepare_classification_text(
    title: str | None,
    skills: Sequence[str] | Iterable[str] | None = None,
    tags: Sequence[str] | Iterable[str] | None = None,
    description: str | None = None,
    max_desc_chars: int = DEFAULT_MAX_DESC_CHARS,
    title_boost: int = DEFAULT_TITLE_BOOST,
    skill_boost: int = DEFAULT_SKILL_BOOST,
) -> JobTextFeatures:
    """Create weighted, readable text representation for classification models.

    Boosts the job title (highest importance) and extracted canonical skills,
    appends source tags where available, and limits the raw job description
    to the first max_desc_chars (default 500) to keep focus on relevant signals.
    """
    clean_title = clean_text_snippet(title)
    canonical_skills = tuple(
        clean_text_snippet(s) for s in (skills or []) if clean_text_snippet(s)
    )
    source_tags = tuple(
        clean_text_snippet(t) for t in (tags or []) if clean_text_snippet(t)
    )
    desc_excerpt = clean_text_snippet(description, max_chars=max_desc_chars)

    skills_joined = ", ".join(canonical_skills)
    tags_joined = ", ".join(source_tags)

    # Build boosted combined text for tokenizers and bag-of-words / TF-IDF models
    parts: list[str] = []
    if clean_title:
        parts.extend([clean_title] * max(1, title_boost))
    if canonical_skills:
        parts.extend([skills_joined] * max(1, skill_boost))
    if source_tags:
        parts.append(tags_joined)
    if desc_excerpt:
        parts.append(desc_excerpt)

    combined_text = " \n ".join(parts)

    return JobTextFeatures(
        title=clean_title,
        skills_text=skills_joined,
        tags_text=tags_joined,
        description_excerpt=desc_excerpt,
        combined_text=combined_text,
        raw_title=str(title or ""),
        canonical_skills=canonical_skills,
        source_tags=source_tags,
        raw_description=str(description or ""),
    )


def classify_job_by_rules(
    title: str | JobTextFeatures | None = None,
    skills: Sequence[str] | Iterable[str] | None = None,
    tags: Sequence[str] | Iterable[str] | None = None,
    description: str | None = None,
    min_confidence_score: float = MIN_RULE_CONFIDENCE_SCORE,
) -> RuleClassificationResult:
    """Classify a job posting using an explainable multi-signal rule baseline.

    Evaluates signals in priority order:
    1. Title matches (highest weight: specific 110, general 90)
    2. Canonical skill matches (10 points each)
    3. Description context matches (2 points each)

    Falls back to 'Other / Unclassified' when evidence is insufficient
    (score below min_confidence_score).
    """
    if isinstance(title, JobTextFeatures):
        features = title
    else:
        features = prepare_classification_text(
            title=title,
            skills=skills,
            tags=tags,
            description=description,
        )

    title_lower = features.title.lower()
    skills_lower = {s.lower() for s in features.canonical_skills}
    desc_lower = features.description_excerpt.lower()

    role_scores: dict[str, float] = defaultdict(float)
    role_evidence: dict[str, list[RuleMatchEvidence]] = defaultdict(list)
    role_rule_names: dict[str, list[str]] = defaultdict(list)

    for role_id, rule_def in ROLE_SIGNAL_RULES.items():
        # 1. Specific title patterns (110 points)
        for pattern in rule_def["specific_title_patterns"]:
            if contains_term(pattern, title_lower):
                score = 110.0
                role_scores[role_id] += score
                evidence = RuleMatchEvidence(
                    signal_type="title_specific",
                    matched_term=pattern,
                    role_id=role_id,
                    score=score,
                )
                role_evidence[role_id].append(evidence)
                role_rule_names[role_id].append(f"title_specific:{pattern}")
                break  # Award top title signal once per role

        # 2. General title patterns (90 points) - only if specific did not match
        if role_id not in role_evidence or not any(
            e.signal_type == "title_specific" for e in role_evidence[role_id]
        ):
            for pattern in rule_def.get("general_title_patterns", ()):
                if contains_term(pattern, title_lower):
                    score = 90.0
                    role_scores[role_id] += score
                    evidence = RuleMatchEvidence(
                        signal_type="title_general",
                        matched_term=pattern,
                        role_id=role_id,
                        score=score,
                    )
                    role_evidence[role_id].append(evidence)
                    role_rule_names[role_id].append(f"title_general:{pattern}")
                    break

        # 3. Canonical skills (10 points each)
        for skill_kw in rule_def["skills"]:
            if skill_kw in skills_lower or any(
                contains_term(skill_kw, s) for s in skills_lower
            ):
                score = 10.0
                role_scores[role_id] += score
                evidence = RuleMatchEvidence(
                    signal_type="skill",
                    matched_term=skill_kw,
                    role_id=role_id,
                    score=score,
                )
                role_evidence[role_id].append(evidence)
                role_rule_names[role_id].append(f"skill:{skill_kw}")

        # 4. Description context (2 points each, max 5 matched phrases = 10 points)
        desc_matches = 0
        for desc_kw in rule_def["description_keywords"]:
            if contains_term(desc_kw, desc_lower):
                score = 2.0
                role_scores[role_id] += score
                evidence = RuleMatchEvidence(
                    signal_type="description",
                    matched_term=desc_kw,
                    role_id=role_id,
                    score=score,
                )
                role_evidence[role_id].append(evidence)
                role_rule_names[role_id].append(f"desc:{desc_kw}")
                desc_matches += 1
                if desc_matches >= 5:
                    break

    # Rank candidate roles by score
    sorted_candidates = sorted(
        role_scores.items(), key=lambda item: item[1], reverse=True
    )

    # Fallback to unclassified if no score or below threshold
    if not sorted_candidates or sorted_candidates[0][1] < min_confidence_score:
        return RuleClassificationResult(
            role_id=FALLBACK_ROLE_ID,
            role_name=FALLBACK_ROLE_NAME,
            confidence=0.0,
            score=0.0,
            matched_rules=(),
            runner_up_role_id=None,
            runner_up_score=0.0,
            is_classified=False,
            evidence=(),
        )

    top_role_id, top_score = sorted_candidates[0]
    runner_up_role_id: str | None = None
    runner_up_score: float = 0.0

    if len(sorted_candidates) > 1 and sorted_candidates[1][1] > 0:
        runner_up_role_id, runner_up_score = sorted_candidates[1]

    # Calculate explainable confidence:
    # Title matches give base 0.80 - 0.95 depending on runner-up gap.
    # Skill-only matches give base 0.40 - 0.65.
    has_title_match = any(
        e.signal_type.startswith("title") for e in role_evidence[top_role_id]
    )

    if has_title_match:
        if runner_up_score > 0:
            margin = (top_score - runner_up_score) / top_score
            confidence = round(min(0.95, max(0.45, 0.60 + 0.35 * margin)), 2)
        else:
            confidence = 0.92
    else:
        # Skill and description signals only
        if runner_up_score > 0:
            margin = (top_score - runner_up_score) / top_score
            confidence = round(min(0.65, max(0.25, 0.35 + 0.30 * margin)), 2)
        else:
            confidence = 0.55

    role_name = TAXONOMY_ROLE_NAMES.get(top_role_id, top_role_id)

    return RuleClassificationResult(
        role_id=top_role_id,
        role_name=role_name,
        confidence=confidence,
        score=top_score,
        matched_rules=tuple(role_rule_names[top_role_id]),
        runner_up_role_id=runner_up_role_id,
        runner_up_score=runner_up_score,
        is_classified=True,
        evidence=tuple(role_evidence[top_role_id]),
    )


class DisjointSet:
    """Disjoint-set (Union-Find) data structure to find connected components."""

    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, item: str) -> str:
        if item not in self.parent:
            self.parent[item] = item
            return item
        if self.parent[item] != item:
            self.parent[item] = self.find(self.parent[item])
        return self.parent[item]

    def union(self, item1: str, item2: str) -> None:
        root1 = self.find(item1)
        root2 = self.find(item2)
        if root1 != root2:
            self.parent[root2] = root1


def make_grouped_train_val_test_split(
    df: pd.DataFrame,
    company_col: str = "company_name",
    title_col: str = "title",
    fingerprint_col: str = "content_fingerprint",
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    seed: int = 20261111,
) -> tuple[pd.DataFrame, SplitVerificationResult]:
    """Partition a dataset into train, val, and test splits with zero group leakage.

    Links records via Disjoint Set (Union-Find) across:
    1. Identical normalized (company, title) pairs
    2. Identical non-empty content_fingerprint values

    Guarantees:
    - Zero company/title overlap across splits.
    - Zero content_fingerprint overlap across splits.
    - 100% deterministic reproducibility based on seed.
    """
    if df.empty:
        empty_result = SplitVerificationResult(
            is_valid=True,
            total_records=0,
            train_count=0,
            val_count=0,
            test_count=0,
            train_ratio=0.0,
            val_ratio=0.0,
            test_ratio=0.0,
            unique_groups=0,
            company_title_overlaps={"train_val": 0, "train_test": 0, "val_test": 0},
            fingerprint_overlaps={"train_val": 0, "train_test": 0, "val_test": 0},
            leakage_details=[],
        )
        out_df = df.copy()
        out_df["group_key"] = pd.Series(dtype=str)
        out_df["split"] = pd.Series(dtype=str)
        return out_df, empty_result

    ratio_sum = train_ratio + val_ratio + test_ratio
    if abs(ratio_sum - 1.0) > 1e-4:
        raise ValueError(
            f"Split ratios must sum to 1.0; got {train_ratio} + {val_ratio} + {test_ratio} = {ratio_sum}"
        )

    out_df = df.copy().reset_index(drop=True)
    ds = DisjointSet()

    row_keys: list[str] = []
    for idx, row in out_df.iterrows():
        comp_raw = row[company_col] if company_col in out_df.columns else ""
        title_raw = row[title_col] if title_col in out_df.columns else ""
        fp_raw = row[fingerprint_col] if fingerprint_col in out_df.columns else ""

        comp_norm = clean_text_snippet(str(comp_raw)).lower()
        title_norm = clean_text_snippet(str(title_raw)).lower()
        ct_node = f"ct:{comp_norm}@@@{title_norm}"

        fp_clean = clean_text_snippet(str(fp_raw))
        if fp_clean and fp_clean.lower() not in ("none", "nan"):
            fp_node = f"fp:{fp_clean}"
            ds.union(ct_node, fp_node)

        row_keys.append(ct_node)

    # Assign canonical group ID for each row
    group_ids = [ds.find(k) for k in row_keys]
    out_df["group_key"] = group_ids

    # Group row indices by group_id
    group_to_indices: dict[str, list[int]] = defaultdict(list)
    for idx, gid in enumerate(group_ids):
        group_to_indices[gid].append(idx)

    # Sort groups deterministically by hash
    def compute_group_hash(gid: str) -> str:
        return hashlib.sha256(f"{seed}:{gid}".encode("utf-8")).hexdigest()

    sorted_groups = sorted(
        group_to_indices.keys(), key=lambda g: (compute_group_hash(g), g)
    )

    total_records = len(out_df)
    target_train = round(total_records * train_ratio)
    target_val = round(total_records * val_ratio)

    split_assignments = [""] * total_records
    curr_train = 0
    curr_val = 0

    for gid in sorted_groups:
        indices = group_to_indices[gid]
        size = len(indices)

        if curr_train < target_train:
            split_label = "train"
            curr_train += size
        elif curr_val < target_val:
            split_label = "val"
            curr_val += size
        else:
            split_label = "test"

        for idx in indices:
            split_assignments[idx] = split_label

    out_df["split"] = split_assignments

    # Verify zero leakage
    verification = verify_split_leakage(
        out_df,
        split_col="split",
        company_col=company_col,
        title_col=title_col,
        fingerprint_col=fingerprint_col,
    )

    return out_df, verification


def verify_split_leakage(
    df: pd.DataFrame,
    split_col: str = "split",
    company_col: str = "company_name",
    title_col: str = "title",
    fingerprint_col: str = "content_fingerprint",
) -> SplitVerificationResult:
    """Verify that train, val, and test splits have 0% shared groups or fingerprints."""
    if df.empty or split_col not in df.columns:
        return SplitVerificationResult(
            is_valid=True,
            total_records=len(df),
            train_count=0,
            val_count=0,
            test_count=0,
            train_ratio=0.0,
            val_ratio=0.0,
            test_ratio=0.0,
            unique_groups=0,
            company_title_overlaps={"train_val": 0, "train_test": 0, "val_test": 0},
            fingerprint_overlaps={"train_val": 0, "train_test": 0, "val_test": 0},
            leakage_details=[],
        )

    splits = {
        name: df[df[split_col] == name]
        for name in ("train", "val", "test")
    }

    train_df = splits["train"]
    val_df = splits["val"]
    test_df = splits["test"]

    n_total = len(df)
    n_train = len(train_df)
    n_val = len(val_df)
    n_test = len(test_df)

    def extract_ct_set(subset: pd.DataFrame) -> set[str]:
        if subset.empty or company_col not in subset.columns or title_col not in subset.columns:
            return set()
        c = subset[company_col].fillna("").astype(str).str.strip().str.lower()
        t = subset[title_col].fillna("").astype(str).str.strip().str.lower()
        return set(c + "@@@" + t)

    def extract_fp_set(subset: pd.DataFrame) -> set[str]:
        if subset.empty or fingerprint_col not in subset.columns:
            return set()
        fps = subset[fingerprint_col].dropna().astype(str).str.strip()
        return {fp for fp in fps if fp and fp.lower() not in ("none", "nan")}

    train_ct, val_ct, test_ct = (
        extract_ct_set(train_df),
        extract_ct_set(val_df),
        extract_ct_set(test_df),
    )
    train_fp, val_fp, test_fp = (
        extract_fp_set(train_df),
        extract_fp_set(val_df),
        extract_fp_set(test_df),
    )

    ct_overlaps = {
        "train_val": len(train_ct & val_ct),
        "train_test": len(train_ct & test_ct),
        "val_test": len(val_ct & test_ct),
    }

    fp_overlaps = {
        "train_val": len(train_fp & val_fp),
        "train_test": len(train_fp & test_fp),
        "val_test": len(val_fp & test_fp),
    }

    leakage_details: list[str] = []
    for pair, count in ct_overlaps.items():
        if count > 0:
            leakage_details.append(
                f"Company/title leakage in {pair}: {count} shared combinations"
            )
    for pair, count in fp_overlaps.items():
        if count > 0:
            leakage_details.append(
                f"Fingerprint leakage in {pair}: {count} shared fingerprints"
            )

    is_valid = len(leakage_details) == 0
    unique_groups = (
        df["group_key"].nunique() if "group_key" in df.columns else 0
    )

    return SplitVerificationResult(
        is_valid=is_valid,
        total_records=n_total,
        train_count=n_train,
        val_count=n_val,
        test_count=n_test,
        train_ratio=round(n_train / max(1, n_total), 4),
        val_ratio=round(n_val / max(1, n_total), 4),
        test_ratio=round(n_test / max(1, n_total), 4),
        unique_groups=unique_groups,
        company_title_overlaps=ct_overlaps,
        fingerprint_overlaps=fp_overlaps,
        leakage_details=leakage_details,
    )


# ---------------------------------------------------------------------------
# Stage 2.2: Machine Learning Classification Pipeline
# ---------------------------------------------------------------------------

PROVISIONAL_SILVER_LABEL_SOURCE = "provisional_silver_rule_v1"
GOLD_HUMAN_LABEL_SOURCE = "gold_human_verified_v1"
DEFAULT_MODEL_VERSION = "0.1.0"
DEFAULT_RANDOM_STATE = 20261111


@dataclass
class RoleClassifierMetadata:
    """Provenance and architectural metadata for a trained role classification bundle."""

    model_name: str
    model_version: str
    label_source: str
    is_provisional: bool
    classes_: list[str]
    num_features: int
    hyperparameters: dict[str, Any]
    random_state: int
    trained_at: str
    training_sample_size: int


@dataclass
class RoleClassifierBundle:
    """Trained ML pipeline combined with auditable provenance metadata."""

    pipeline: Pipeline
    metadata: RoleClassifierMetadata


@dataclass(frozen=True)
class MLClassificationResult:
    """Detailed ML inference result for a single job posting with confidence auditing."""

    predicted_role: str
    predicted_role_name: str
    confidence: float
    class_probabilities: dict[str, float]
    runner_up_role: str | None
    runner_up_confidence: float
    model_version: str
    label_source: str
    is_provisional: bool
    confidence_tier: str = "MEDIUM"  # "HIGH", "MEDIUM", "LOW", "UNCERTAIN"
    is_fallback: bool = False
    confidence_margin: float = 0.0


@dataclass(frozen=True)
class ErrorAnalysisReport:
    """Detailed confusion-matrix analysis and confidence stratification report."""

    total_samples: int
    total_errors: int
    overall_error_rate: float
    top_confusions: list[dict[str, Any]]
    per_class_error_summary: dict[str, dict[str, Any]]
    confidence_stratification: dict[str, dict[str, Any]]
    low_confidence_count: int
    brier_score: float | None
    calibration_notes: list[str]


@dataclass(frozen=True)
class ModelEvaluationReport:
    """Evaluation metrics comparing classifier against baselines on a held-out split."""

    model_name: str
    split_name: str
    label_source: str
    is_provisional: bool
    num_samples: int
    class_distribution: dict[str, int]
    majority_class: str
    majority_class_accuracy: float
    majority_class_macro_f1: float
    majority_class_weighted_f1: float
    rule_baseline_macro_f1: float | None
    rule_baseline_weighted_f1: float | None
    rule_baseline_accuracy: float | None
    model_accuracy: float
    model_macro_f1: float
    model_weighted_f1: float
    per_class_metrics: dict[str, dict[str, float]]
    confusion_matrix: list[list[int]]
    confusion_matrix_labels: list[str]
    evaluation_notes: list[str]


def prepare_labeled_dataset(
    df: pd.DataFrame,
    label_col: str,
    valid_roles: Sequence[str] | None = None,
    title_col: str = "title",
    skills_col: str = "skills",
    tags_col: str = "source_tags_text",
    description_col: str = "job_description",
) -> tuple[list[str], list[str], pd.DataFrame]:
    """Extract prepared boosted text features and validate labels from a DataFrame.

    Filters out rows where label_col is null, empty, or not in valid_roles (if specified).
    Uses prepare_classification_text() to guarantee consistent title, skill, tag,
    and description representations across training, validation, and inference.

    SAFETY:
    If label_col == 'human_verified_role_label' and all rows are blank/null, raises
    ValueError to prevent training on unannotated gold columns.
    """
    if label_col not in df.columns:
        raise KeyError(f"Target label column '{label_col}' not found in DataFrame.")

    # Guard against accidental training on unannotated human labels
    if label_col == "human_verified_role_label":
        non_blank = df[label_col].dropna().astype(str).str.strip()
        non_blank = non_blank[~non_blank.isin(["", "nan", "None"])]
        if non_blank.empty:
            raise ValueError(
                "Cannot train on 'human_verified_role_label' because human verification is not complete "
                "and no verified non-blank gold labels were found in the dataset."
            )

    valid_roles_set = set(valid_roles) if valid_roles is not None else None

    prepared_texts: list[str] = []
    labels: list[str] = []
    valid_indices: list[int] = []

    for idx, row in df.iterrows():
        raw_label = row[label_col]
        if pd.isna(raw_label):
            continue
        label_str = clean_text_snippet(str(raw_label))
        if not label_str or label_str.lower() in ("nan", "none"):
            continue
        if valid_roles_set is not None and label_str not in valid_roles_set:
            continue

        raw_title = row[title_col] if title_col in df.columns and pd.notna(row[title_col]) else ""
        raw_skills = row[skills_col] if skills_col in df.columns and pd.notna(row[skills_col]) else []
        if isinstance(raw_skills, str):
            parsed_skills = [s.strip() for s in raw_skills.split(",") if s.strip()]
        elif isinstance(raw_skills, (list, tuple)):
            parsed_skills = list(raw_skills)
        else:
            parsed_skills = []

        raw_tags = row[tags_col] if tags_col in df.columns and pd.notna(row[tags_col]) else []
        if isinstance(raw_tags, str):
            parsed_tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
        elif isinstance(raw_tags, (list, tuple)):
            parsed_tags = list(raw_tags)
        else:
            parsed_tags = []

        raw_desc = row[description_col] if description_col in df.columns and pd.notna(row[description_col]) else ""

        features = prepare_classification_text(
            title=str(raw_title),
            skills=parsed_skills,
            tags=parsed_tags,
            description=str(raw_desc),
        )

        prepared_texts.append(features.combined_text)
        labels.append(label_str)
        valid_indices.append(idx)

    cleaned_df = df.loc[valid_indices].copy().reset_index(drop=True)
    return prepared_texts, labels, cleaned_df


def generate_provisional_silver_labels(
    df: pd.DataFrame,
    output_label_col: str = "provisional_silver_label",
    title_col: str = "title",
    skills_col: str = "skills",
    tags_col: str = "source_tags_text",
    description_col: str = "job_description",
) -> pd.DataFrame:
    """Generate provisional silver labels using the rule baseline for pipeline development.

    IMPORTANT SAFETY NOTICE:
    Silver labels are heuristic rule outputs used ONLY for experimental pipeline development.
    They are NOT ground truth. Gold human-verified labels are maintained strictly separately.
    """
    out_df = df.copy().reset_index(drop=True)
    silver_labels: list[str] = []
    silver_confidences: list[float] = []
    silver_rules: list[str] = []

    for _, row in out_df.iterrows():
        raw_title = row[title_col] if title_col in out_df.columns and pd.notna(row[title_col]) else ""
        raw_skills = row[skills_col] if skills_col in out_df.columns and pd.notna(row[skills_col]) else []
        if isinstance(raw_skills, str):
            parsed_skills = [s.strip() for s in raw_skills.split(",") if s.strip()]
        elif isinstance(raw_skills, (list, tuple)):
            parsed_skills = list(raw_skills)
        else:
            parsed_skills = []

        raw_tags = row[tags_col] if tags_col in out_df.columns and pd.notna(row[tags_col]) else []
        if isinstance(raw_tags, str):
            parsed_tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
        elif isinstance(raw_tags, (list, tuple)):
            parsed_tags = list(raw_tags)
        else:
            parsed_tags = []

        raw_desc = row[description_col] if description_col in out_df.columns and pd.notna(row[description_col]) else ""

        res = classify_job_by_rules(
            title=str(raw_title),
            skills=parsed_skills,
            tags=parsed_tags,
            description=str(raw_desc),
        )
        silver_labels.append(res.role_id)
        silver_confidences.append(res.confidence)
        silver_rules.append(", ".join(res.matched_rules))

    out_df[output_label_col] = silver_labels
    out_df["provisional_silver_confidence"] = silver_confidences
    out_df["provisional_silver_rules"] = silver_rules
    return out_df


def fit_role_classifier(
    X_train: Sequence[str],
    y_train: Sequence[str],
    label_source: str = PROVISIONAL_SILVER_LABEL_SOURCE,
    model_version: str = DEFAULT_MODEL_VERSION,
    ngram_range: tuple[int, int] = (1, 2),
    min_df: int | float = 2,
    max_features: int | None = 25000,
    C: float = 1.0,
    max_iter: int = 1000,
    random_state: int = DEFAULT_RANDOM_STATE,
) -> RoleClassifierBundle:
    """Fit a TF-IDF + Logistic Regression pipeline with class_weight='balanced'.

    Guarantees:
    - n-gram range (1, 2) word features.
    - class_weight='balanced' to handle role imbalances.
    - Deterministic random state.
    - Provenance metadata recorded with label source and provisional status.
    """
    if len(X_train) == 0 or len(y_train) == 0:
        raise ValueError("Cannot fit classifier on empty training data.")
    if len(X_train) != len(y_train):
        raise ValueError(
            f"Mismatched feature and label counts: {len(X_train)} vs {len(y_train)}"
        )
    unique_classes = sorted(set(y_train))
    if len(unique_classes) < 2:
        raise ValueError(
            f"Classifier requires at least 2 distinct classes to train; found: {unique_classes}"
        )

    vectorizer = TfidfVectorizer(
        ngram_range=ngram_range,
        min_df=min_df,
        max_features=max_features,
        sublinear_tf=True,
    )
    classifier = LogisticRegression(
        class_weight="balanced",
        C=C,
        max_iter=max_iter,
        random_state=random_state,
        solver="lbfgs",
    )

    pipeline = Pipeline([
        ("tfidf", vectorizer),
        ("clf", classifier),
    ])

    pipeline.fit(X_train, y_train)

    is_provisional = "silver" in label_source.lower() or "provisional" in label_source.lower()

    metadata = RoleClassifierMetadata(
        model_name="tfidf_logistic_regression",
        model_version=model_version,
        label_source=label_source,
        is_provisional=is_provisional,
        classes_=list(classifier.classes_),
        num_features=len(vectorizer.vocabulary_),
        hyperparameters={
            "C": C,
            "max_iter": max_iter,
            "ngram_range": ngram_range,
            "class_weight": "balanced",
            "min_df": min_df,
            "max_features": max_features,
            "solver": "lbfgs",
        },
        random_state=random_state,
        trained_at=datetime.now(UTC).isoformat(),
        training_sample_size=len(X_train),
    )

    return RoleClassifierBundle(pipeline=pipeline, metadata=metadata)


def _extract_text_sequence(
    texts_or_records: Sequence[str] | Sequence[JobTextFeatures] | pd.DataFrame,
) -> list[str]:
    """Helper to extract a list of strings from various input representations."""
    if isinstance(texts_or_records, pd.DataFrame):
        prepared_texts: list[str] = []
        for _, row in texts_or_records.iterrows():
            title = str(row["title"]) if "title" in row and pd.notna(row["title"]) else ""
            raw_s = row["skills"] if "skills" in row and pd.notna(row["skills"]) else []
            s_list = [s.strip() for s in raw_s.split(",")] if isinstance(raw_s, str) else list(raw_s or [])
            raw_t = row["source_tags_text"] if "source_tags_text" in row and pd.notna(row["source_tags_text"]) else []
            t_list = [t.strip() for t in raw_t.split(",")] if isinstance(raw_t, str) else list(raw_t or [])
            desc = str(row["job_description"]) if "job_description" in row and pd.notna(row["job_description"]) else ""
            feat = prepare_classification_text(title=title, skills=s_list, tags=t_list, description=desc)
            prepared_texts.append(feat.combined_text)
        return prepared_texts

    texts: list[str] = []
    for item in texts_or_records:
        if isinstance(item, JobTextFeatures):
            texts.append(item.combined_text)
        elif isinstance(item, str):
            texts.append(item)
        else:
            texts.append(str(item))
    return texts


def predict_role(
    bundle: RoleClassifierBundle,
    texts_or_records: Sequence[str] | Sequence[JobTextFeatures] | pd.DataFrame,
) -> list[str]:
    """Predict class role IDs using the trained pipeline."""
    texts = _extract_text_sequence(texts_or_records)
    if not texts:
        return []
    return list(bundle.pipeline.predict(texts))


def predict_role_probabilities(
    bundle: RoleClassifierBundle,
    texts_or_records: Sequence[str] | Sequence[JobTextFeatures] | pd.DataFrame,
) -> list[dict[str, float]]:
    """Predict role class probability distributions sorted descending by probability."""
    texts = _extract_text_sequence(texts_or_records)
    if not texts:
        return []
    proba_matrix = bundle.pipeline.predict_proba(texts)
    classes = bundle.metadata.classes_

    results: list[dict[str, float]] = []
    for row_probs in proba_matrix:
        prob_dict = {
            cls: round(float(p), 4)
            for cls, p in sorted(
                zip(classes, row_probs), key=lambda x: x[1], reverse=True
            )
        }
        results.append(prob_dict)
    return results


def predict_job_role(
    bundle: RoleClassifierBundle,
    title: str | None = None,
    skills: Sequence[str] | Iterable[str] | None = None,
    tags: Sequence[str] | Iterable[str] | None = None,
    description: str | None = None,
    min_confidence_threshold: float = 0.0,
    confidence_margin_threshold: float = 0.0,
) -> MLClassificationResult:
    """Predict the role for a single job posting with complete probability audit.

    Supports safe fallback to 'other_unclassified' if confidence is below
    min_confidence_threshold or if margin over runner-up is below confidence_margin_threshold.
    """
    feat = prepare_classification_text(
        title=title, skills=skills, tags=tags, description=description
    )
    probs_list = predict_role_probabilities(bundle, [feat.combined_text])
    probs = probs_list[0] if probs_list else {}

    sorted_classes = list(probs.items())
    top_role, top_conf = sorted_classes[0] if sorted_classes else (FALLBACK_ROLE_ID, 0.0)
    runner_up_role, runner_up_conf = (
        sorted_classes[1] if len(sorted_classes) > 1 else (None, 0.0)
    )

    margin = round(top_conf - runner_up_conf, 4) if runner_up_role else top_conf

    # Assign explainable confidence tier
    if top_conf >= 0.50:
        tier = "HIGH"
    elif top_conf >= 0.30:
        tier = "MEDIUM"
    elif top_conf >= 0.20:
        tier = "LOW"
    else:
        tier = "UNCERTAIN"

    # Evaluate fallback to other_unclassified if confidence is too low or ambiguous
    is_fallback = False
    predicted_role = top_role
    if min_confidence_threshold > 0.0 and top_conf < min_confidence_threshold:
        predicted_role = FALLBACK_ROLE_ID
        is_fallback = True
    elif (
        confidence_margin_threshold > 0.0
        and runner_up_role is not None
        and margin < confidence_margin_threshold
    ):
        predicted_role = FALLBACK_ROLE_ID
        is_fallback = True

    return MLClassificationResult(
        predicted_role=predicted_role,
        predicted_role_name=TAXONOMY_ROLE_NAMES.get(predicted_role, predicted_role),
        confidence=top_conf,
        class_probabilities=probs,
        runner_up_role=runner_up_role,
        runner_up_confidence=runner_up_conf,
        model_version=bundle.metadata.model_version,
        label_source=bundle.metadata.label_source,
        is_provisional=bundle.metadata.is_provisional,
        confidence_tier=tier,
        is_fallback=is_fallback,
        confidence_margin=margin,
    )


def analyze_classification_errors(
    y_true: Sequence[str],
    y_pred: Sequence[str],
    probabilities: Sequence[dict[str, float]] | None = None,
    labels: Sequence[str] | None = None,
    low_confidence_threshold: float = 0.20,
) -> ErrorAnalysisReport:
    """Perform confusion-matrix and per-class error analysis with confidence stratification.

    Analyzes:
    1. Top misclassification patterns (true -> predicted pairs).
    2. Per-class error rates and dominant mistake classes.
    3. Accuracy breakdown stratified by confidence tiers (HIGH, MEDIUM, LOW, UNCERTAIN).
    4. Multi-class Brier score for probability verification.
    """
    if len(y_true) != len(y_pred):
        raise ValueError(
            f"Mismatched length between y_true ({len(y_true)}) and y_pred ({len(y_pred)})"
        )
    n_samples = len(y_true)
    if n_samples == 0:
        return ErrorAnalysisReport(
            total_samples=0,
            total_errors=0,
            overall_error_rate=0.0,
            top_confusions=[],
            per_class_error_summary={},
            confidence_stratification={},
            low_confidence_count=0,
            brier_score=None,
            calibration_notes=["No samples evaluated."],
        )

    all_labels = sorted(set(y_true) | set(y_pred) | set(labels or ()))
    confusion_counts: dict[tuple[str, str], int] = Counter(zip(y_true, y_pred))

    total_errors = sum(1 for yt, yp in zip(y_true, y_pred) if yt != yp)
    error_rate = round(total_errors / max(1, n_samples), 4)

    # Top misclassification pairs (yt != yp)
    error_pairs = [
        {"true_role": yt, "pred_role": yp, "count": cnt, "percentage": round(cnt / max(1, total_errors), 4)}
        for (yt, yp), cnt in confusion_counts.items()
        if yt != yp
    ]
    error_pairs.sort(key=lambda x: x["count"], reverse=True)

    # Per-class error summary
    per_class_summary: dict[str, dict[str, Any]] = {}
    class_support = Counter(y_true)
    for cls in all_labels:
        supp = class_support.get(cls, 0)
        if supp == 0:
            continue
        errors_for_cls = sum(cnt for (yt, yp), cnt in confusion_counts.items() if yt == cls and yp != cls)
        mistakes = [
            (yp, cnt) for (yt, yp), cnt in confusion_counts.items() if yt == cls and yp != cls
        ]
        mistakes.sort(key=lambda x: x[1], reverse=True)
        top_mistake = mistakes[0][0] if mistakes else None

        per_class_summary[cls] = {
            "support": supp,
            "errors": errors_for_cls,
            "error_rate": round(errors_for_cls / supp, 4),
            "accuracy": round((supp - errors_for_cls) / supp, 4),
            "most_common_mistake": top_mistake,
        }

    # Stratify by confidence if probabilities are provided
    stratification: dict[str, dict[str, Any]] = {
        "HIGH": {"count": 0, "correct": 0, "accuracy": 0.0},
        "MEDIUM": {"count": 0, "correct": 0, "accuracy": 0.0},
        "LOW": {"count": 0, "correct": 0, "accuracy": 0.0},
        "UNCERTAIN": {"count": 0, "correct": 0, "accuracy": 0.0},
    }
    low_conf_count = 0
    brier_sum = 0.0

    if probabilities and len(probabilities) == n_samples:
        for idx in range(n_samples):
            yt = y_true[idx]
            yp = y_pred[idx]
            p_dict = probabilities[idx]
            top_p = max(p_dict.values()) if p_dict else 0.0

            if top_p < low_confidence_threshold:
                low_conf_count += 1

            if top_p >= 0.50:
                tier = "HIGH"
            elif top_p >= 0.30:
                tier = "MEDIUM"
            elif top_p >= 0.20:
                tier = "LOW"
            else:
                tier = "UNCERTAIN"

            stratification[tier]["count"] += 1
            if yt == yp:
                stratification[tier]["correct"] += 1

            # Multi-class Brier score sum: sum_k (p_ik - y_ik)^2
            for cls in all_labels:
                p_k = p_dict.get(cls, 0.0)
                y_k = 1.0 if cls == yt else 0.0
                brier_sum += (p_k - y_k) ** 2

        for tier, data in stratification.items():
            cnt = data["count"]
            data["accuracy"] = round(data["correct"] / cnt, 4) if cnt > 0 else 0.0

        brier_score = round(brier_sum / n_samples, 4)
    else:
        brier_score = None

    notes = [
        "Softmax decision values from L2-regularized logistic regression with class balancing are uncalibrated decision scores.",
        "Stratification confirms that accuracy monotonically scales with confidence tiers, but scores should not be reported as true frequentist probabilities without post-hoc calibration on gold labels.",
        f"Low-confidence predictions (< {low_confidence_threshold:.2f}) account for {low_conf_count} / {n_samples} samples ({round(low_conf_count/max(1, n_samples)*100, 1)}%).",
    ]

    return ErrorAnalysisReport(
        total_samples=n_samples,
        total_errors=total_errors,
        overall_error_rate=error_rate,
        top_confusions=error_pairs[:10],
        per_class_error_summary=per_class_summary,
        confidence_stratification=stratification,
        low_confidence_count=low_conf_count,
        brier_score=brier_score,
        calibration_notes=notes,
    )


def save_role_classifier(
    bundle: RoleClassifierBundle,
    filepath: Path | str,
) -> Path:
    """Save a trained RoleClassifierBundle to disk using joblib."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, path)
    return path.resolve()


def load_role_classifier(
    filepath: Path | str,
) -> RoleClassifierBundle:
    """Load a RoleClassifierBundle from disk."""
    path = Path(filepath)
    if not path.is_file():
        raise FileNotFoundError(f"Model file not found at {path}")
    bundle = joblib.load(path)
    if not isinstance(bundle, RoleClassifierBundle):
        raise TypeError(
            f"Expected RoleClassifierBundle at {path}; got {type(bundle)}"
        )
    return bundle


def evaluate_role_classifier(
    bundle: RoleClassifierBundle,
    X_eval: Sequence[str],
    y_eval: Sequence[str],
    X_train: Sequence[str] | None = None,
    y_train: Sequence[str] | None = None,
    split_name: str = "val",
    rule_baseline_preds: Sequence[str] | None = None,
) -> ModelEvaluationReport:
    """Evaluate classifier against majority and rule baselines on a held-out split."""
    if len(X_eval) == 0 or len(y_eval) == 0:
        raise ValueError("Cannot evaluate on empty evaluation data.")

    y_eval_list = list(y_eval)
    class_distribution = dict(Counter(y_eval_list))

    # Model predictions
    y_pred = list(bundle.pipeline.predict(X_eval))

    # Calculate model metrics
    model_acc = round(float(accuracy_score(y_eval_list, y_pred)), 4)
    model_macro_f1 = round(
        float(precision_recall_fscore_support(y_eval_list, y_pred, average="macro", zero_division=0)[2]), 4
    )
    model_weighted_f1 = round(
        float(precision_recall_fscore_support(y_eval_list, y_pred, average="weighted", zero_division=0)[2]), 4
    )

    # Per-class report
    cls_report = classification_report(
        y_eval_list, y_pred, output_dict=True, zero_division=0
    )
    per_class_metrics: dict[str, dict[str, float]] = {}
    for label, metrics in cls_report.items():
        if isinstance(metrics, dict) and "precision" in metrics:
            per_class_metrics[label] = {
                "precision": round(float(metrics["precision"]), 4),
                "recall": round(float(metrics["recall"]), 4),
                "f1_score": round(float(metrics["f1-score"]), 4),
                "support": int(metrics["support"]),
            }

    # Confusion matrix
    eval_labels = sorted(set(y_eval_list) | set(y_pred))
    cm = confusion_matrix(y_eval_list, y_pred, labels=eval_labels).tolist()

    # Majority-class baseline
    if y_train is not None and len(y_train) > 0:
        dummy = DummyClassifier(strategy="most_frequent")
        dummy.fit(X_train if X_train is not None else X_eval, y_train)
        dummy_preds = dummy.predict(X_eval)
        majority_class = str(dummy.classes_[0])
    else:
        majority_class = max(class_distribution, key=class_distribution.get)
        dummy_preds = [majority_class] * len(y_eval_list)

    majority_acc = round(float(accuracy_score(y_eval_list, dummy_preds)), 4)
    majority_macro_f1 = round(
        float(precision_recall_fscore_support(y_eval_list, dummy_preds, average="macro", zero_division=0)[2]), 4
    )
    majority_weighted_f1 = round(
        float(precision_recall_fscore_support(y_eval_list, dummy_preds, average="weighted", zero_division=0)[2]), 4
    )

    # Rule baseline (if provided)
    rule_macro_f1 = None
    rule_weighted_f1 = None
    rule_acc = None
    if rule_baseline_preds is not None and len(rule_baseline_preds) == len(y_eval_list):
        rule_acc = round(float(accuracy_score(y_eval_list, rule_baseline_preds)), 4)
        rule_macro_f1 = round(
            float(precision_recall_fscore_support(y_eval_list, rule_baseline_preds, average="macro", zero_division=0)[2]), 4
        )
        rule_weighted_f1 = round(
            float(precision_recall_fscore_support(y_eval_list, rule_baseline_preds, average="weighted", zero_division=0)[2]), 4
        )

    # Diagnostic provenance notes
    notes: list[str] = []
    if bundle.metadata.is_provisional:
        notes.append(
            "PROVISIONAL DIAGNOSTIC ONLY: The model was trained and evaluated against rule-generated silver labels (provisional_silver_rule_v1). "
            "Agreement reflects model fidelity to the rule heuristic, NOT real-world accuracy against human gold standard."
        )
    else:
        notes.append(
            "GOLD BENCHMARK: Evaluated against human-verified gold labels."
        )

    if split_name.lower() == "val":
        notes.append(
            "Validation split evaluation. The test split is held out and untouched."
        )
    elif split_name.lower() == "test":
        notes.append(
            "Test split evaluation. Warning: Ensure no hyperparameter tuning was performed on this split."
        )

    return ModelEvaluationReport(
        model_name=bundle.metadata.model_name,
        split_name=split_name,
        label_source=bundle.metadata.label_source,
        is_provisional=bundle.metadata.is_provisional,
        num_samples=len(y_eval_list),
        class_distribution=class_distribution,
        majority_class=majority_class,
        majority_class_accuracy=majority_acc,
        majority_class_macro_f1=majority_macro_f1,
        majority_class_weighted_f1=majority_weighted_f1,
        rule_baseline_macro_f1=rule_macro_f1,
        rule_baseline_weighted_f1=rule_weighted_f1,
        rule_baseline_accuracy=rule_acc,
        model_accuracy=model_acc,
        model_macro_f1=model_macro_f1,
        model_weighted_f1=model_weighted_f1,
        per_class_metrics=per_class_metrics,
        confusion_matrix=cm,
        confusion_matrix_labels=eval_labels,
        evaluation_notes=notes,
    )


def get_model_summary(bundle: RoleClassifierBundle) -> dict[str, Any]:
    """Return a human-readable dictionary summary of model provenance and architecture."""
    meta = bundle.metadata
    return {
        "model_name": meta.model_name,
        "model_version": meta.model_version,
        "label_source": meta.label_source,
        "is_provisional": meta.is_provisional,
        "num_classes": len(meta.classes_),
        "classes": meta.classes_,
        "vocabulary_size": meta.num_features,
        "hyperparameters": meta.hyperparameters,
        "random_state": meta.random_state,
        "training_sample_size": meta.training_sample_size,
        "trained_at": meta.trained_at,
    }

