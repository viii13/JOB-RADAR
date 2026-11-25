# AI/ML Experimental Laboratory (`experiments/`)

## 1. Overview & Purpose
This directory stores exploratory analysis scripts, prototyping notebooks, ablation studies, diagnostic benchmarks, and model error audits. 

Work here is exploratory and designed to benchmark hypotheses before graduating production-ready components into their respective Phase directories.

---

## 2. Directory Layout

```text
experiments/
├── phase_4_classification/     # Classifier ablation, threshold scans, ambiguity audits
├── phase_5_recommendation/     # Skill weighting studies, career fit formulas, parser evaluations
├── phase_6_salary/             # Regression comparisons, non-linear tree models, feature importances
└── README.md                   # This guide
```

---

## 3. Experimentation Rules

1. **Isolation:** Experimental scripts must never overwrite production model bundles or modify core database records.
2. **Deterministic Seeds:** Always pin random seeds (`random_state=20261111`) to ensure full experimental reproducibility.
3. **No Synthetic Benchmarks:** Diagnostic comparisons must clearly differentiate between gold annotations, silver heuristics, and synthetic diagnostic samples. Never report exploratory agreement rates as empirical model accuracy.
