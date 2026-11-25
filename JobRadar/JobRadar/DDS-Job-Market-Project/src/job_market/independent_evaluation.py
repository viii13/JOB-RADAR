"""Independent evaluation harness for JobRadar role classifiers using human-verified annotations.

Provides:
1. Strict audit of human-verified gold labels in annotation files.
2. Cross-set leakage checks against ALL Stage 2.2 model splits: training, validation, and test.
3. Comparative benchmarking (ML model vs. rule baseline vs. majority-class baseline)
   on identical, non-overlapping evaluation records.
4. Defensible limitation reporting when annotations are incomplete or overlapping.
"""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import sqlite3
from typing import Any, Sequence

import pandas as pd

from .classification import (
    FALLBACK_ROLE_ID,
    GOLD_HUMAN_LABEL_SOURCE,
    ROLE_TAXONOMY_PATH,
    TAXONOMY_ROLE_NAMES,
    ModelEvaluationReport,
    RoleClassifierBundle,
    classify_job_by_rules,
    clean_text_snippet,
    evaluate_role_classifier,
    load_role_classifier,
    load_role_taxonomy,
    make_grouped_train_val_test_split,
    prepare_classification_text,
    prepare_labeled_dataset,
)

DEFAULT_ANNOTATION_PATHS: tuple[Path, ...] = (
    Path(__file__).resolve().parents[2] / "data" / "annotations" / "role_annotation_sample.csv",
    Path(__file__).resolve().parents[2] / "data" / "annotations" / "targeted_data_ai_role_annotation_batch.csv",
)

MINIMUM_EVALUATION_SAMPLES = 30


@dataclass(frozen=True)
class AnnotationAuditSummary:
    """Audit summary of human annotation files, label counts, and leakage checks."""

    files_inspected: list[str]
    total_records_inspected: int
    unique_job_version_ids: int
    completed_human_labels_count: int
    blank_labels_count: int
    label_distribution: dict[str, int]
    training_id_overlaps: list[int]
    validation_id_overlaps: list[int]
    test_id_overlaps: list[int]
    all_excluded_overlaps: list[int]
    is_ready_for_evaluation: bool
    status_reason: str
    limitations: list[str]


@dataclass(frozen=True)
class IndependentEvaluationResult:
    """Outcome of Stage 2.3 independent benchmark evaluation."""

    audit_summary: AnnotationAuditSummary
    evaluation_report: ModelEvaluationReport | None
    can_benchmark: bool
    status_message: str
    limitations: list[str]
    recommendations: list[str]


def get_stage2_split_job_version_ids(
    db_path: Path | str | None = None,
    sample_limit: int = 3000,
    seed: int = 20261111,
) -> dict[str, set[int]]:
    """Retrieve job_version_ids partitioned across Stage 2.2 train, val, and test splits."""
    resolved_db = (
        Path(db_path) if db_path else Path(__file__).resolve().parents[2] / "data" / "jobradar.db"
    )
    if not resolved_db.is_file():
        return {"train": set(), "val": set(), "test": set()}

    conn = sqlite3.connect(resolved_db)
    try:
        query = f"""
            SELECT id as job_version_id, title, company_name, content_fingerprint
            FROM job_versions
            WHERE is_current = 1
            LIMIT {int(sample_limit)}
        """
        df = pd.read_sql(query, conn)
        split_df, _ = make_grouped_train_val_test_split(df, seed=seed)
        return {
            "train": set(split_df[split_df["split"] == "train"]["job_version_id"].astype(int)),
            "val": set(split_df[split_df["split"] == "val"]["job_version_id"].astype(int)),
            "test": set(split_df[split_df["split"] == "test"]["job_version_id"].astype(int)),
        }
    finally:
        conn.close()


def audit_annotation_records(
    annotation_paths: Sequence[Path | str] | None = None,
    training_job_version_ids: Sequence[int] | set[int] | None = None,
    validation_job_version_ids: Sequence[int] | set[int] | None = None,
    test_job_version_ids: Sequence[int] | set[int] | None = None,
    excluded_job_version_ids: Sequence[int] | set[int] | None = None,
    valid_roles: Sequence[str] | None = None,
    min_samples: int = MINIMUM_EVALUATION_SAMPLES,
    auto_detect_splits: bool = True,
) -> tuple[AnnotationAuditSummary, pd.DataFrame]:
    """Audit existing annotation CSVs for human-verified labels and split leakage.

    Guarantees:
    - Never treats 'candidate_target_family' or 'selection_rule' as gold labels.
    - Only reads 'human_verified_role_label' when non-blank.
    - Excludes annotation records overlapping with ANY Stage 2.2 split:
      training, validation, or test.
    - Returns clean, verified DataFrame ready for evaluation.
    """
    paths = [Path(p) for p in (annotation_paths or DEFAULT_ANNOTATION_PATHS)]

    # Resolve split ID sets
    if auto_detect_splits and (
        training_job_version_ids is None
        and validation_job_version_ids is None
        and test_job_version_ids is None
    ):
        split_ids = get_stage2_split_job_version_ids()
        train_set = set(split_ids.get("train", set()))
        val_set = set(split_ids.get("val", set()))
        test_set = set(split_ids.get("test", set()))
    else:
        train_set = set(training_job_version_ids or ())
        val_set = set(validation_job_version_ids or ())
        test_set = set(test_job_version_ids or ())

    explicit_excluded = set(excluded_job_version_ids or ())
    all_excluded_set = train_set | val_set | test_set | explicit_excluded

    if valid_roles is None:
        try:
            taxonomy = load_role_taxonomy()
            valid_roles_set = {f["id"] for f in taxonomy.get("role_families", [])}
        except Exception:
            valid_roles_set = set(TAXONOMY_ROLE_NAMES.keys())
    else:
        valid_roles_set = set(valid_roles)

    files_inspected: list[str] = []
    seen_job_version_ids: set[int] = set()
    completed_labels: list[str] = []
    train_overlaps: set[int] = set()
    val_overlaps: set[int] = set()
    test_overlaps: set[int] = set()
    all_overlaps: set[int] = set()

    clean_rows: list[dict[str, Any]] = []
    total_inspected = 0
    blank_count = 0

    for path in paths:
        if not path.is_file():
            continue
        files_inspected.append(path.name)
        with path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                total_inspected += 1
                raw_id = row.get("job_version_id", "").strip()
                jvid = int(raw_id) if raw_id.isdigit() else None
                if jvid is not None:
                    seen_job_version_ids.add(jvid)

                # Check split overlaps
                if jvid is not None:
                    if jvid in train_set:
                        train_overlaps.add(jvid)
                    if jvid in val_set:
                        val_overlaps.add(jvid)
                    if jvid in test_set:
                        test_overlaps.add(jvid)
                    if jvid in all_excluded_set:
                        all_overlaps.add(jvid)

                # Check human label
                human_label = clean_text_snippet(row.get("human_verified_role_label"))

                # Strict gold safety: candidates or selection rules are NEVER gold labels
                if not human_label or human_label.lower() in ("nan", "none"):
                    blank_count += 1
                    continue

                if human_label not in valid_roles_set:
                    # Ignore invalid role labels
                    blank_count += 1
                    continue

                completed_labels.append(human_label)

                # Exclude if overlapping with ANY split (train, val, or test)
                if jvid is not None and jvid in all_excluded_set:
                    continue

                clean_rows.append(row)

    label_dist = dict(Counter(completed_labels))
    limitations: list[str] = []

    if len(completed_labels) == 0:
        is_ready = False
        status_reason = (
            "No completed human-verified labels found in annotation files. "
            "Human annotation is currently in progress."
        )
        limitations.append(
            f"Zero human-verified labels available across {total_inspected} inspected records."
        )
    elif len(clean_rows) < min_samples:
        is_ready = False
        status_reason = (
            f"Insufficient clean annotations ({len(clean_rows)} clean samples available after excluding "
            f"{len(all_overlaps)} overlapping split records; minimum {min_samples} required for defensible evaluation)."
        )
        limitations.append(status_reason)
    else:
        is_ready = True
        status_reason = f"Ready for independent evaluation with {len(clean_rows)} clean records."

    if all_overlaps:
        limitations.append(
            f"Cross-split leakage prevention: {len(all_overlaps)} annotated records overlap with Stage 2.2 splits "
            f"({len(train_overlaps)} training: {sorted(train_overlaps)}, "
            f"{len(val_overlaps)} validation: {sorted(val_overlaps)}, "
            f"{len(test_overlaps)} test: {sorted(test_overlaps)}). "
            "All overlapping records are strictly excluded from the independent evaluation pool."
        )

    clean_df = pd.DataFrame(clean_rows) if clean_rows else pd.DataFrame()

    summary = AnnotationAuditSummary(
        files_inspected=files_inspected,
        total_records_inspected=total_inspected,
        unique_job_version_ids=len(seen_job_version_ids),
        completed_human_labels_count=len(completed_labels),
        blank_labels_count=blank_count,
        label_distribution=label_dist,
        training_id_overlaps=sorted(train_overlaps),
        validation_id_overlaps=sorted(val_overlaps),
        test_id_overlaps=sorted(test_overlaps),
        all_excluded_overlaps=sorted(all_overlaps),
        is_ready_for_evaluation=is_ready,
        status_reason=status_reason,
        limitations=limitations,
    )

    return summary, clean_df


def run_independent_evaluation(
    bundle_or_path: RoleClassifierBundle | Path | str,
    annotation_paths: Sequence[Path | str] | None = None,
    training_job_version_ids: Sequence[int] | set[int] | None = None,
    validation_job_version_ids: Sequence[int] | set[int] | None = None,
    test_job_version_ids: Sequence[int] | set[int] | None = None,
    excluded_job_version_ids: Sequence[int] | set[int] | None = None,
    min_samples_threshold: int = MINIMUM_EVALUATION_SAMPLES,
    auto_detect_splits: bool = True,
) -> IndependentEvaluationResult:
    """Run independent evaluation of the classifier against human-verified gold labels.

    Evaluates:
    - Majority-class baseline
    - Rule-based baseline
    - Logistic Regression classifier
    on exactly the same clean, non-overlapping gold records (excluding any Stage 2.2 train, val, or test overlap).

    If annotations are incomplete or insufficient, strictly refuses to fabricate results.
    """
    if isinstance(bundle_or_path, (str, Path)):
        bundle = load_role_classifier(bundle_or_path)
    else:
        bundle = bundle_or_path

    audit_summary, clean_df = audit_annotation_records(
        annotation_paths=annotation_paths,
        training_job_version_ids=training_job_version_ids,
        validation_job_version_ids=validation_job_version_ids,
        test_job_version_ids=test_job_version_ids,
        excluded_job_version_ids=excluded_job_version_ids,
        min_samples=min_samples_threshold,
        auto_detect_splits=auto_detect_splits,
    )

    recommendations = [
        "Complete manual human annotation for data/annotations/role_annotation_sample.csv (120 records).",
        "Complete manual human annotation for data/annotations/targeted_data_ai_role_annotation_batch_blind.csv (72 records).",
        "Ensure annotators follow data/reference/role_annotation_guide.md without seeing model predictions.",
        (
            f"Exclude all {len(audit_summary.all_excluded_overlaps)} overlapping job_version_ids "
            f"(train: {audit_summary.training_id_overlaps}, val: {audit_summary.validation_id_overlaps}, "
            f"test: {audit_summary.test_id_overlaps}) to ensure zero cross-split leakage."
        ),
        "Re-run Stage 2.3 independent evaluation once at least 30 clean gold labels are verified.",
    ]

    if not audit_summary.is_ready_for_evaluation or clean_df.empty:
        return IndependentEvaluationResult(
            audit_summary=audit_summary,
            evaluation_report=None,
            can_benchmark=False,
            status_message=audit_summary.status_reason,
            limitations=audit_summary.limitations,
            recommendations=recommendations,
        )

    # Prepare features and labels
    texts: list[str] = []
    labels: list[str] = []
    rule_preds: list[str] = []

    for _, row in clean_df.iterrows():
        title = str(row.get("title", "") or "")
        desc = str(row.get("description_excerpt", "") or row.get("job_description", "") or "")
        skills_raw = row.get("skills", "") or ""
        skills_list = [s.strip() for s in str(skills_raw).split(",") if s.strip()]
        tags_raw = row.get("source_tags_text", "") or ""
        tags_list = [t.strip() for t in str(tags_raw).split(",") if t.strip()]

        feat = prepare_classification_text(
            title=title,
            skills=skills_list,
            tags=tags_list,
            description=desc,
        )
        texts.append(feat.combined_text)
        labels.append(str(row["human_verified_role_label"]))

        rule_res = classify_job_by_rules(
            title=title,
            skills=skills_list,
            tags=tags_list,
            description=desc,
        )
        rule_preds.append(rule_res.role_id)

    report = evaluate_role_classifier(
        bundle=bundle,
        X_eval=texts,
        y_eval=labels,
        split_name="human_gold_benchmark",
        rule_baseline_preds=rule_preds,
    )

    return IndependentEvaluationResult(
        audit_summary=audit_summary,
        evaluation_report=report,
        can_benchmark=True,
        status_message="Independent evaluation successfully completed against human gold labels.",
        limitations=audit_summary.limitations,
        recommendations=recommendations,
    )
