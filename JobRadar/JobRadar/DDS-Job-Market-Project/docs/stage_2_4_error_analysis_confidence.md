# Stage 2.4: Error Analysis and Confidence Handling

## 1. Overview

In Stage 2.4, we implemented systematic error analysis and explainable confidence handling for the JobRadar Phase 4 classification pipeline:
- Multi-class confusion-matrix and per-class error analysis (`analyze_classification_errors()`).
- Tiered, explainable confidence stratification (`HIGH`, `MEDIUM`, `LOW`, `UNCERTAIN`).
- Safe fallback mechanism routing ambiguous or low-confidence predictions to `other_unclassified`.
- Rigorous assessment of probability calibration limits.

---

## 2. Confidence Tiers & Decision Rules (Heuristic Stratification Bands)

> [!IMPORTANT]
> **Heuristic Stratification Bands (Uncalibrated):**
> These confidence tiers are heuristic, uncalibrated stratification bands designed for explainable risk tiering. They do NOT represent frequentist probabilities derived from empirical calibration algorithms (such as Platt scaling or isotonic regression).

Uniform random guessing across the 11 candidate role families yields a prior of $\approx 0.0909$ ($9.1\%$), while across the 5 active silver training classes the uniform prior is $0.20$ ($20.0\%$). Based on these priors and relative ranking on held-out validation samples, four heuristic stratification bands are established:

| Confidence Tier | Decision Score Range ($p$) | Interpretation | Action / Behavior |
|---|---|---|---|
| **HIGH** | $p \ge 0.50$ | Dominant majority probability (> 50% across classes) | Standard prediction |
| **MEDIUM** | $0.30 \le p < 0.50$ | Strong plurality; model has clear leading preference | Standard prediction |
| **LOW** | $0.20 \le p < 0.30$ | Weak plurality; notable competition from runner-up | Flagged as low-confidence |
| **UNCERTAIN** | $p < 0.20$ | At or below chance prior; insufficient signal | Safe fallback to `other_unclassified` |

### Fallback to `other_unclassified`
When `min_confidence_threshold` is configured (e.g. 0.20) or when `confidence_margin_threshold` (e.g. 0.05 margin over runner-up) is violated:
- `predicted_role` is safely overridden to `other_unclassified` ("Other / Unclassified").
- `is_fallback` is set to `True`.
- Full underlying class probabilities and the original unadjusted runner-up are preserved in the result metadata for complete auditability.

---

## 3. Probability Calibration Limitations & Brier Score

> [!WARNING]
> **Probability Calibration Status:**
> The decision scores produced by the classifier are generated via softmax on L2-regularized Logistic Regression with `class_weight="balanced"`.
> 
> 1. **Uncalibrated Heuristics:** Because class weights distort empirical prior frequencies, softmax outputs represent relative decision scores rather than true objective frequentist probabilities.
> 2. **Monotonicity Without Calibration:** While confidence monotonically correlates with accuracy across the defined tiers (HIGH confidence yields higher empirical accuracy than LOW confidence), raw scores must **never** be cited as true calibrated odds without post-hoc isotonic regression or Platt scaling against verified gold labels.
> 3. **Brier Score Label Source:** The pipeline tracks the multi-class Brier score ($BS = \frac{1}{N} \sum_{i} \sum_{k} (p_{ik} - y_{ik})^2 = 0.0917$). This metric was computed on the **held-out validation split** ($N = 2,544$) labeled with **provisional silver rule labels** (`provisional_silver_rule_v1`). It is **not** an evaluation on human-verified gold ground truth.

---

## 4. Per-Class Error Patterns

Analysis of the Stage 2.2 validation split identified the following primary confusion patterns:
1. **Frontend vs. Backend:** Fullstack postings mentioning both client-side UI and server APIs can lean towards Backend if backend framework tokens (`spring`, `microservices`) outnumber UI tokens.
2. **Data Analyst vs. Data Scientist:** Postings with mixed titles ("Analytics Specialist") where description emphasizes SQL reporting rather than statistical experimentation.
3. **Product Management vs. Corporate Operations:** Technical project managers in operations roles frequently overlap with corporate administration when titles omit "Agile" or "Software".

These confusion patterns are transparently surfaced by `analyze_classification_errors()` for active monitoring.
