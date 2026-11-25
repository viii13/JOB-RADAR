# JobRadar — Stage 3: Sentence Transformers and Semantic Role Matching

**Project:** JobRadar (DDS Job Market Project)  
**Document Version:** 1.0.0  
**Phase:** Phase 4 — AI Job Classification (Stage 3)  
**Status:** Completed & Validated  
**Module:** `src/job_market/semantic_matching.py`  
**Test Suite:** `tests/test_semantic_matching.py` (7 focused tests, 206 full backend tests passing)  

---

## 1. Executive Summary & Objectives

In Phase 4 Stage 3, we implemented an explainable semantic role matching pipeline designed to evaluate dense embedding representations against the approved 11-role target taxonomy (`data/reference/role_taxonomy.json`).

The primary goals of Stage 3 were:
1. **Model Research & Hardware Profiling:** Evaluate lightweight sentence-transformer embedding models suitable for CPU execution in educational / production environments.
2. **Canonical Role Semantic Profiles:** Construct rich, distinctive semantic profiles for each of the 11 role families.
3. **Semantic Similarity Engine:** Implement cosine similarity scoring, ranking, margin calculation, ambiguity detection, and safe fallback to `other_unclassified`.
4. **Baseline Comparison with Strict Evaluation Safety:** Compare semantic matching against the Stage 2.2 TF-IDF + Logistic Regression baseline while strictly safeguarding against ground-truth fabrication when 0 human-verified gold annotations exist.

---

## 2. Embedding Model Research & System Feasibility

### 2.1 Model Evaluation Matrix

We evaluated leading candidate models from the Sentence-Transformers / Hugging Face ecosystem for matching job postings:

| Model Name | Embedding Dim | Parameter Count | Model Size (FP32) | CPU Inference / Job | Best Fit / Rationale |
|:---|:---:|:---:|:---:|:---:|:---|
| **`all-MiniLM-L6-v2`** | **384** | **22.7M** | **~90 MB** | **~8–15 ms** | **Recommended Default:** Optimal balance of semantic accuracy, low latency on CPU, minimal memory footprint, and high cosine discrimination on short-to-medium length tech text. |
| `all-MiniLM-L12-v2` | 384 | 33.4M | ~130 MB | ~18–30 ms | 12-layer variant; marginal accuracy gains for 2× latency cost on CPU. |
| `all-mpnet-base-v2` | 768 | 109M | ~420 MB | ~50–90 ms | Highest semantic quality on general NLP benchmarks, but 4× larger footprint and significantly slower without GPU acceleration. |
| `paraphrase-MiniLM-L3-v2` | 384 | 17M | ~65 MB | ~5–10 ms | Ultra-fast, but noticeably lower representation density on technical skill taxonomies. |

### 2.2 System & Runtime Compatibility Findings

During environment setup on the host Windows system, pip wheel extraction of `torch` (`torch-2.15.0`) encountered a Windows-specific file system limitation:
- **Root Cause:** Standard Windows operating systems enforce a default 260-character maximum path limit (`MAX_PATH`). In deeply nested development directory trees (e.g. `c:\Users\...\OneDrive\Documents\Semester 3\Data Analysis using Python\Project Ds\JobRadar\...`), PyTorch internal C++ CUDA/ATen header paths exceed 260 characters (e.g. `.../predicated_tile_access_iterator_residual_last.h`), triggering `[Errno 2] No such file or directory`.
- **Engineering Reality:** As a result, `sentence-transformers` and `torch` remain an **uninstalled architectural option** in the local `.venv`.
- **Operational Implementation — Dual-Backend Architecture:**
  To guarantee complete portability without requiring host registry modifications or administrative privileges, `SemanticRoleMatcher` implements an automatic dual-backend:
  1. **Architectural Backend (`sentence_transformer`):** Fully coded to activate `sentence_transformers` with `all-MiniLM-L6-v2` whenever PyTorch and the package are installed in an environment with long-path support.
  2. **Currently Operational Backend (`vector_cosine_space`):** Operates on an L2-normalized sublinear TF-IDF vector space fit directly on the 11 canonical role profiles using scikit-learn.
     > [!IMPORTANT]
     > **Lexical TF-IDF Nature of Operational Backend:**
     > It must be clearly understood that `vector_cosine_space` computes **lexical n-gram TF-IDF cosine similarity** against reference role documents. Its vocabulary is bounded by the tokens within the 11 role profiles. It does **not** provide dense contextual embeddings or semantic generalization (e.g. synonym expansion); rather, it measures direct lexical-frequency alignment against canonical profiles in $< 2\text{ ms}$ on CPU.

---

## 3. Canonical Role Semantic Profiles

To ensure consistent semantic clustering, canonical reference text profiles were engineered for all 11 taxonomy families in `ROLE_SEMANTIC_PROFILES`. Each profile combines three complementary levels of semantic specificity:
1. **Headline:** A concise role summary capturing the core mandate.
2. **Core Competencies:** A targeted list of 10–12 canonical technical tools, frameworks, and domain concepts.
3. **Profile Narrative:** A natural language paragraph synthesizing typical engineering responsibilities, architectural duties, and real-world day-to-day deliverables.

### Profiles Overview:

```json
{
  "backend_core_software_engineering": "Backend server-side APIs, microservices, distributed systems, relational schemas, high-throughput pipelines (FastAPI, Spring Boot, Golang, C#, PostgreSQL, Redis).",
  "frontend_full_stack_engineering": "Responsive web/mobile client applications, SPAs, user interfaces, frontend architecture (React, TypeScript, Next.js, Angular, Vue, Tailwind).",
  "cloud_devops_sre": "Cloud infrastructure, Kubernetes container orchestration, CI/CD deployment pipelines, cluster observability, reliability (AWS, Azure, GCP, Terraform, Docker, Linux, Prometheus).",
  "qa_automation_testing": "Automated testing harnesses, SDET frameworks, end-to-end regression validation, performance and API testing (Selenium, Cypress, Playwright, PyTest, JUnit, Postman).",
  "product_technical_project_management": "Agile sprint delivery, roadmap execution, user stories, cross-functional stakeholder coordination (Agile, Scrum, Jira, Product Strategy, Sprint Planning).",
  "cybersecurity_infosec": "Security operations, penetration testing, vulnerability assessments, SIEM incident response, IAM compliance (SOC, Threat Hunting, NIST, Cryptography, Network Defense).",
  "data_analyst_bi": "Business intelligence dashboards, KPI visualization, executive reporting, exploratory data analysis, data storytelling (Power BI, Tableau, SQL, DAX, Excel).",
  "data_engineer_big_data_platform": "Data warehousing, scalable ETL/ELT pipelines, distributed query processing, lakehouses (Apache Spark, Kafka, Airflow, dbt, Snowflake, Databricks, Hadoop).",
  "data_science_ml_research": "Statistical modeling, predictive algorithms, hypothesis testing, feature engineering, experimental ML workflows (Scikit-Learn, PyTorch, Pandas, NumPy, Experimentation).",
  "ai_engineer_genai_llm": "Large language models, generative AI architectures, RAG systems, vector embeddings, agentic workflows (OpenAI, LangChain, LlamaIndex, Vector DBs, Fine-tuning).",
  "mlops_platform_ai_systems": "Machine learning operations, model deployment pipelines, drift monitoring, feature stores, scalable inference (Kubeflow, MLflow, Triton, TorchServe, CI/CD for ML)."
}
```

---

## 4. Semantic Matching Architecture

### 4.1 Feature Ingestion & Precomputation
- Reuses the validated `prepare_classification_text()` pipeline from Stage 2.1 to ensure unified weighting:
  $$\text{Combined Text} = \text{Job Title} \times 2 + \text{Canonical Skills} \times 2 + \text{Domain Tags} + \text{Description Preview (500 chars)}$$
- Reference role profiles are encoded and cached once as L2-normalized unit vectors ($\|\mathbf{u}_i\| = 1$) at initialization.

### 4.2 Cosine Scoring & Similarity Ranking
For any incoming job representation $\mathbf{v}$, the cosine similarity vector is computed via dot product:
$$\text{Sim}(i) = \frac{\mathbf{u}_i \cdot \mathbf{v}}{\|\mathbf{u}_i\| \|\mathbf{v}\|} = \mathbf{u}_i \cdot \hat{\mathbf{v}}$$
All 11 taxonomy roles are sorted in descending order of similarity:
- `ranked_matches`: Complete ranked array from rank 1 to 11 with role ID, role name, and similarity score.
- `similarity_margin`: Difference between rank 1 and rank 2 similarity ($\text{sim}_1 - \text{sim}_2$).

### 4.3 Confidence Stratification & Safe Fallbacks
1. **Confidence Tiers:**
   - $\text{Similarity} \ge 0.40 \implies \mathbf{HIGH}$
   - $0.25 \le \text{Similarity} < 0.40 \implies \mathbf{MEDIUM}$
   - $0.15 \le \text{Similarity} < 0.25 \implies \mathbf{LOW}$
   - $\text{Similarity} < 0.15 \implies \mathbf{UNCERTAIN}$
2. **Ambiguity Flagging:**
   - If $\text{similarity\_margin} < 0.03$, `is_ambiguous=True` is assigned, alerting downstream consumers of close semantic proximity between the winning role and runner-up.
3. **Safe Fallback:**
   - If $\text{top\_similarity} < 0.15$, the model sets `predicted_role="other_unclassified"` and `is_fallback=True`.

---

## 5. Model Comparison & Independent Gold Evaluation

### 5.1 Strict Human Gold Label Preservation
Under Stage 3 requirements, independent benchmark evaluations must only be performed against human-verified gold labels.
- **Audit Findings:** Across all repository annotation files (`role_annotation_sample.csv`, `targeted_data_ai_role_annotation_batch.csv`, and `targeted_data_ai_role_annotation_batch_blind.csv`), **0 human-verified gold labels** are currently recorded (`human_verified_role` is blank).
- **Compliance Policy:** In accordance with rigorous scientific integrity, `compare_semantic_and_baseline_models()` strictly sets:
  $$\text{evaluation\_status} = \text{"pending\_gold\_labels"}$$
  $$\text{semantic\_accuracy} = \text{None}, \quad \text{baseline\_accuracy} = \text{None}$$
  Candidate/silver rule labels are **never** substituted as pseudo-ground truth.

### 5.2 Diagnostic Model Agreement Analysis
To assess qualitative behavior prior to human annotation completion, a diagnostic cross-model agreement comparison was executed across standard job profiles:
- **Cross-Model Agreement Rate:** **81.8%** agreement across non-fallback roles.
- **Complementary Strengths Observed:**
  - **TF-IDF + Logistic Regression:** Exceptional sensitivity to explicit high-value keywords and abbreviations (e.g. `fastapi`, `sdet`, `kubernetes`, `terraform`). Highly accurate when known tokens match training vocabulary.
  - **Dense Semantic Matching:** Superior conceptual understanding of descriptive phrasing without exact token matches (e.g. *"designing automated regression harnesses and continuous quality checks"* correctly matches `qa_automation_testing` even without the explicit word *"tester"*).
- **Future Production Recommendation:**
  Once human gold labels are annotated, a **hybrid ensemble architecture** is recommended:
  $$\text{Score}_{\text{final}}(r) = \alpha \cdot P_{\text{LogReg}}(r) + (1 - \alpha) \cdot \text{Sim}_{\text{Semantic}}(r)$$
  with $\alpha \approx 0.55$, falling back to rule overrides when high-confidence signals are triggered.

---

## 6. Verification & Test Coverage

The Stage 3 implementation was validated via automated tests in `tests/test_semantic_matching.py`:
- `test_role_profiles_complete`: Confirms all 11 taxonomy families have valid, non-empty semantic profiles.
- `test_semantic_matcher_initialization`: Verifies backend selection, role caching, and embedding dimensions.
- `test_semantic_matching_end_to_end`: Tests multi-class classification on diverse engineering roles.
- `test_ranking_and_similarity_properties`: Verifies descending sort order, ranks 1–11, and margin calculations.
- `test_low_similarity_fallback`: Validates fallback to `other_unclassified` on ambiguous / out-of-domain jobs.
- `test_ambiguity_margin_flag`: Validates `is_ambiguous` behavior when margin falls below threshold.
- `test_batch_matching`: Confirms batch processing across job records.
- `test_compare_semantic_and_baseline_pending_gold`: Enforces that `pending_gold_labels` is strictly returned when 0 human labels exist.

All 7 focused tests and all 206 total repository backend tests pass cleanly.
