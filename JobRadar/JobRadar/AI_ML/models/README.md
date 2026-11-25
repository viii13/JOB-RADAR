# Central Model Registry (`models/`)

## 1. Overview & Purpose
This directory serves as the centralized, auditable model registry for all serialized machine learning pipelines, vectorizers, and trained estimators across JobRadar.

---

## 2. Model Storage & Naming Conventions

All persisted models must follow standardized semantic versioning and artifact naming:

$$\text{<task>}\_\text{<algorithm>}\_\text{<version>}.\text{joblib}$$

Examples:
- `role_classifier_baseline_v0.1.0.joblib` (Phase 4 TF-IDF + Logistic Regression)
- `salary_estimator_ridge_v0.1.0.joblib` (Phase 6 Salary Prediction Baseline)

---

## 3. Mandatory Provenance Metadata

Every serialized artifact must be packaged inside a container (e.g. `RoleClassifierBundle`) storing explicit provenance metadata:

```python
@dataclass
class ModelMetadata:
    model_name: str                 # e.g. "tfidf_logistic_regression"
    model_version: str              # e.g. "0.1.0"
    label_source: str               # e.g. "provisional_silver_rule_v1"
    is_provisional: bool            # True until independently validated
    classes_: list[str]             # List of output classes
    num_features: int               # Feature vocabulary length
    hyperparameters: dict[str, Any] # Hyperparameter configuration
    random_state: int               # Seed for reproducible execution
    trained_at: str                 # ISO-8601 UTC timestamp
    training_sample_size: int       # Exact record count in training split
```

---

## 4. Current Registry State

| Model Artifact | Phase | Algorithm | Classes | Provenance Status | Current Location |
|---|:---:|---|:---:|:---:|---|
| `role_classifier_baseline_v0.1.0.joblib` | 4 | TF-IDF + Logistic Regression (`class_weight="balanced"`) | 5 active | Provisional (Trained on silver labels) | `DDS-Job-Market-Project/data/models/` |

*(Note: The active artifact currently resides in `DDS-Job-Market-Project/data/models/` for backward compatibility with existing tests and API endpoints).*
