# JobRadar — AI & Machine Learning Architecture (`AI_ML`)

Welcome to the centralized AI/ML workspace for the **JobRadar** project.

This directory consolidates and standardizes the machine learning pipelines, research experiments, model registries, and algorithmic services across all analytical phases of JobRadar.

---

## 1. Directory Structure

```text
AI_ML/
├── Phase_4_Job_Classification/     # Role Taxonomy, TF-IDF + Logistic Regression, Semantic Profiles
├── Phase_5_Career_Recommendation/  # Resume Parsing, Skill Benchmarks, Skill Gap, Roadmaps
├── Phase_6_Salary_Prediction/      # Salary Estimation Models, Compensation Feature Engineering
├── shared/                         # Reusable ML utilities (text cleaning, metrics, splitters)
├── models/                         # Serialized model artifact registry & provenance metadata
├── experiments/                    # Exploratory notebooks, ablation studies, error analyses
├── docs/                           # Architecture decision records, research notes, benchmark reports
└── README.md                       # This top-level orientation guide
```

---

## 2. Phase Responsibilities Overview

| Directory / Phase | Core Objective | Primary Techniques & Algorithms | Status |
|---|---|---|:---:|
| **`Phase_4_Job_Classification`** | Classify unstructured job postings into 11 canonical role families. | Grouped splitting, TF-IDF n-grams, balanced Logistic Regression, lexical cosine profile matching, heuristic stratification bands. | Complete (In Core) |
| **`Phase_5_Career_Recommendation`** | Recommend career paths, identify skill gaps, and generate learning roadmaps. | Empirical role-skill benchmarks, regex resume skill extraction, demand-weighted Jaccard/set-overlap fit scoring. | Planned / Next |
| **`Phase_6_Salary_Prediction`** | Predict salary ranges for job listings and evaluate skill compensation premiums. | Feature encoding (experience, location, skills, role), regularized regressors (Ridge, Random Forest/GBDT), salary analytics. | Future |
| **`shared/`** | Common utilities across all modeling pipelines. | Text normalization, zero-leakage cross-validation splitters, multi-class/regression metrics. | Cross-cutting |
| **`models/`** | Central registry for versioned model bundles. | `joblib` artifacts with embedded provenance metadata (`classes_`, `hyperparameters`, `is_provisional`). | Central Store |
| **`experiments/`** | Diagnostic benchmarks & error audits. | Confusion matrix diagnostics, model agreement checks, diagnostic logs. | Research |
| **`docs/`** | Technical reports & documentation. | Architectural specifications, calibration analyses, audit summaries. | Knowledge Base |

---

## 3. Strict Engineering & Data Safety Principles

1. **Zero Data Leakage:** All training, validation, and test splits must enforce strict entity grouping (e.g., by company and title) and duplicate content fingerprint exclusion.
2. **Evaluation Integrity:** Never fabricate evaluation benchmarks or substitute silver pseudo-labels as gold ground truth. When human gold labels are pending, evaluations must strictly be labeled `pending_gold_labels`.
3. **No Redundant Dependencies:** Favor simple, explainable, and lightweight methods (e.g. scikit-learn, regex, pure Python) suitable for university B.Tech and production web environments before introducing heavy deep-learning frameworks.
4. **Model Provenance & Auditing:** Every persisted model bundle must contain auditable metadata: model version, training timestamp, training sample size, random state, feature dimensions, and provisional status flags.
5. **Safe Coexistence with Backend:** The primary FastAPI backend currently resides in `DDS-Job-Market-Project`. Code in `AI_ML` will be integrated through planned, backward-compatible facades and import migration bridges.
