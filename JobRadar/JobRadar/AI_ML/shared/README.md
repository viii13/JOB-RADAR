# Shared AI/ML Utilities (`shared/`)

## 1. Overview & Purpose
This directory houses reusable, cross-cutting machine learning utilities, feature encoders, evaluation metrics, and data integrity tools shared across Phase 4 (Job Classification), Phase 5 (Career Recommendation), and Phase 6 (Salary Prediction).

---

## 2. Directory Layout & Modules

```text
shared/
├── text/               # Text cleaning, normalization, regex utilities, skill matching
├── evaluation/         # Zero-leakage splitters, Brier score, multi-class metrics, regression metrics
├── taxonomy/           # Role taxonomy helpers, canonical label loaders, frontend mappings
├── types/              # Typed dataclasses and Pydantic schemas for features and predictions
├── utils/              # General helper functions, random seed managers, provenance loggers
└── README.md           # This guide
```

---

## 3. Core Modules & Responsibilities

1. **`shared/text/`:**
   - Text cleaning functions (`clean_text_snippet`, lowercasing, whitespace normalization).
   - Domain-specific tokenizers preserving technical acronyms (`C++`, `.NET`, `CI/CD`).
   - Unified feature text preparation combining titles, skill sets, tags, and description previews.
2. **`shared/evaluation/`:**
   - Grouped splitting utilities (`create_grouped_splits` by company and title).
   - Split verification checks (`verify_split_leakage`) enforcing 0 entity and 0 content fingerprint leakage.
   - Comprehensive error analytics: confusion matrices, top confusion pairs, stratification bands, and Brier scores.
3. **`shared/taxonomy/`:**
   - Taxonomy definition loaders reading from `role_taxonomy.json`.
   - Bidirectional translators between internal taxonomy IDs and frontend filter labels.
4. **`shared/types/`:**
   - Shared dataclasses: `JobTextFeatures`, `RoleSimilarityMatch`, `SemanticMatchingResult`, `MLClassificationResult`, `RoleClassifierMetadata`.
