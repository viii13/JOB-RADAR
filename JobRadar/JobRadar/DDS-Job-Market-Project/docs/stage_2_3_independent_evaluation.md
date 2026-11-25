# Stage 2.3: Independent Evaluation Audit Report

## 1. Executive Summary

This report documents the independent evaluation audit conducted for JobRadar Phase 4, Stage 2.3. The objective was to benchmark the experimental TF-IDF + Logistic Regression role classifier against human-verified gold annotations under strict zero-leakage conditions.

The audit determined that **human annotation is currently 100% incomplete** (0 human gold labels across all 192 inspected records). In strict adherence to scientific integrity principles, **no benchmark metrics have been fabricated**. The evaluation harness correctly halted, reported the limitations, and established the precise protocol required to execute the benchmark once human annotations are completed.

---

## 2. Annotation Inventory & Label Inspection

We audited all canonical annotation files in `data/annotations/`:

| File | Type | Total Rows | Human-Verified Gold Labels | Blank / Incomplete |
|---|---|---:|---:|---:|
| `role_annotation_sample.csv` | Balanced Random Sample (60 hist / 60 Adzuna) | 120 | 0 | 120 |
| `targeted_data_ai_role_annotation_batch.csv` | Targeted Candidate Batch (18 per Data/AI family) | 72 | 0 | 72 |
| `targeted_data_ai_role_annotation_batch_blind.csv` | Blinded Annotator Batch (no candidate hints) | 72 | 0 | 72 |
| **Total Unique Records** | Combined non-overlapping records | **192** | **0** | **192** |

### Gold Label Safety Protocol
- Columns `candidate_target_family` and `selection_rule` in the targeted batch are heuristic selection aids only. They are **never** treated as gold labels.
- The pipeline strictly reads `human_verified_role_label`.
- Because all 192 records have blank `human_verified_role_label` fields, the independent benchmark cannot defensibly execute until human annotators review and submit their judgments.

---

## 3. Data Leakage & Cross-Split Overlap Audit

We cross-referenced all 192 unique annotation `job_version_id` records against **all three Stage 2.2 model partitions** (training, validation, and test splits):

| Overlap Category | Overlapping `job_version_id` Records | Status / Treatment |
|---|---|---|
| **Training Split Overlap** | `2333`, `2748`, `2961` (3 records) | **EXCLUDED** from evaluation pool to prevent train-test contamination. |
| **Validation Split Overlap** | `1662` (1 record) | **EXCLUDED** from evaluation pool to prevent validation tuning leakage. |
| **Test Split Overlap** | `2390` (1 record) | **EXCLUDED** from evaluation pool to prevent test partition leakage. |
| **Total Excluded Overlaps** | `1662`, `2333`, `2390`, `2748`, `2961` (**5 records**) | **STRICTLY EXCLUDED** from independent gold evaluation pool. |

The evaluation harness in `src/job_market/independent_evaluation.py` enforces this three-way filter automatically: any record whose `job_version_id` appears in **any Stage 2.2 split** (training, validation, or test) is strictly excluded from the independent evaluation pool.

---

## 4. Evaluation Methodology (When Unblocked)

Once human annotations are completed, `run_independent_evaluation()` evaluates three models on the remaining 187 clean, non-overlapping gold records:
1. **Majority-Class Baseline:** Predicts the most frequent class in the training split.
2. **Rule-Based Baseline:** Evaluates Stage 2.1 explainable rules on the gold records.
3. **Logistic Regression Classifier:** Evaluates the Stage 2.2 model bundle (`data/models/role_classifier_baseline_v0.1.0.joblib`).

Metrics computed across identical evaluation records:
- Overall Accuracy
- Macro-averaged F1 score
- Weighted F1 score
- Per-class Precision, Recall, F1 score, and Support ($N$)
- Multi-class Confusion Matrix

---

## 5. Limitations & Next Steps

### Limitations
1. **No Ground Truth Available:** Current models can only be diagnosed against heuristic silver labels until human annotators complete the gold review.
2. **Cross-Split Overlap Exclusions:** Exactly 5 candidate annotation records overlap with Stage 2.2 splits (3 training, 1 validation, 1 test). These 5 records are permanently excluded from independent gold evaluation, leaving up to 187 eligible non-overlapping gold records.

### Actionable Next Steps
1. **Complete Annotation:** Human annotators review `targeted_data_ai_role_annotation_batch_blind.csv` (72 records) and `role_annotation_sample.csv` (120 records) using `data/reference/role_annotation_guide.md`.
2. **Execute Stage 2.3 Benchmark:** Run `run_independent_evaluation()` to compute the first genuine gold benchmark on the 187 clean records.
