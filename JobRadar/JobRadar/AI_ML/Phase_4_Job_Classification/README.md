# Phase 4: AI Job Classification

## 1. Overview & Purpose
Phase 4 implements the automated mapping of raw, unstructured tech job postings into an approved **11-family role taxonomy**. It provides explainable, reproducible classification using both supervised linear baselines and canonical semantic profile matching.

---

## 2. Key Components & Responsibilities

1. **Role Taxonomy & Annotation Safety:**
   - 11 canonical role families defined in `role_taxonomy.json` mapping to frontend role filters.
   - Annotation batch sampling: 120-job random baseline sample and 72-job targeted Data/AI batch.
   - Blinded evaluation dataset (`targeted_data_ai_role_annotation_batch_blind.csv`) preventing annotator confirmation bias.
   - Strict overwrite protection preventing automatic regeneration from destroying human annotations.
2. **Text Feature Representation (`JobTextFeatures`):**
   - Weighted multi-signal text representation:
     $$\text{Combined Text} = \text{Job Title} \times 2 + \text{Canonical Skills} \times 2 + \text{Source Tags} + \text{Description Preview (500 chars)}$$
3. **Zero-Leakage Grouped Splitting:**
   - Grouping by company and normalized title with strict duplicate content fingerprint exclusion across splits.
4. **Supervised Baseline Model:**
   - Word n-gram TF-IDF vectorizer + Logistic Regression with `class_weight="balanced"`.
   - Serialized as versioned bundle with metadata: `role_classifier_baseline_v0.1.0.joblib`.
5. **Error Analysis & Heuristic Stratification Bands:**
   - Confusion matrix extraction, per-class error summaries, and multi-class Brier score ($0.0917$ on silver validation set).
   - Heuristic, uncalibrated stratification bands: `HIGH` ($\ge 0.50$), `MEDIUM` ($\ge 0.30$), `LOW` ($\ge 0.20$), `UNCERTAIN` ($< 0.20$).
   - Automated safe fallback to `other_unclassified` for ambiguous or low-confidence postings.
6. **Semantic Role Matching:**
   - 11 canonical role semantic profiles (headline, core competencies, detailed narrative).
   - Full cosine similarity ranking, margin computation, and ambiguity detection (`is_ambiguous`).
   - Resilient dual-backend: operational `vector_cosine_space` (lexical TF-IDF cosine matching) with architectural hooks for `sentence-transformers` (`all-MiniLM-L6-v2`).
7. **Serving Endpoints:**
   - Single (`/api/classify/job`) and batch (`/api/classify/batch`) FastAPI endpoints with startup in-memory model caching.

---

## 3. Existing Implementation Files in Repo

| Logical Component | Current Location in `DDS-Job-Market-Project` | Planned Target in `AI_ML` |
|---|---|---|
| **Pipeline & Baseline** | `src/job_market/classification.py` | `AI_ML/Phase_4_Job_Classification/classification_pipeline.py` |
| **Semantic Matching** | `src/job_market/semantic_matching.py` | `AI_ML/Phase_4_Job_Classification/semantic_matcher.py` |
| **Annotation Tools** | `src/job_market/role_annotation.py` | `AI_ML/Phase_4_Job_Classification/annotation_manager.py` |
| **Targeted Annotation** | `src/job_market/run_targeted_role_annotation.py` | `AI_ML/Phase_4_Job_Classification/run_targeted_annotation.py` |
| **Independent Eval** | `src/job_market/independent_evaluation.py` | `AI_ML/Phase_4_Job_Classification/independent_evaluation.py` |
| **Taxonomy JSON** | `data/reference/role_taxonomy.json` | Symlinked or referenced from `shared/taxonomy/` |
| **Trained Artifact** | `data/models/role_classifier_baseline_v0.1.0.joblib` | `AI_ML/models/role_classifier_baseline_v0.1.0.joblib` |
| **Unit Tests** | `tests/test_classification.py`, `tests/test_semantic_matching.py` | `AI_ML/Phase_4_Job_Classification/tests/` |

*(Note: Per migration safety rules, existing files remain at their current locations until formal migration execution).*
