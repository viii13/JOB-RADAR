"""
Technical Salary Model Trainer & Benchmark Comparison Suite (Phase 6 v2.0.0)
Trains, evaluates with 5-fold GroupKFold, computes conformal calibration,
calculates permutation importance, and persists v2.0.0 artifacts.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import TransformedTargetRegressor
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline

try:
    from ..data.curator import (
        curate_technical_salary_dataset,
        TechnicalDatasetCurationReport,
    )
    from ..evaluation.metrics import compute_regression_metrics, compute_stratified_metrics
    from ..features.pipeline import SalaryFeatureUnion
    from ..features.transformers import TECHNICAL_ROLE_FAMILIES
except ImportError:
    from data.curator import (
        curate_technical_salary_dataset,
        TechnicalDatasetCurationReport,
    )
    from evaluation.metrics import compute_regression_metrics, compute_stratified_metrics
    from features.pipeline import SalaryFeatureUnion
    from features.transformers import TECHNICAL_ROLE_FAMILIES

logger = logging.getLogger(__name__)

_MODULE_DIR = Path(__file__).resolve().parent
_ARTIFACTS_DIR = _MODULE_DIR / "artifacts"


def train_and_evaluate_technical_salary_models(
    csv_path: str | Path | None = None,
    save_artifacts: bool = True,
    random_state: int = 42,
) -> dict[str, Any]:
    """
    Train and benchmark technical-only compensation models under 5-fold GroupKFold.
    
    Leakage Prevention:
    - Strict GroupKFold on companyName_clean ensures zero same-company leakage.
    - Explicitly excludes all salary-related fields, target derivatives, and IDs from X.
    - Conformal prediction intervals calibrated on out-of-group residuals.
    """
    _ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    print(">>> 1. Curating technical salary dataset (Option A: Core Technical Scope)...")
    df_tech, tech_report = curate_technical_salary_dataset(csv_path)
    total_tech_samples = len(df_tech)
    print(f"    Curated {total_tech_samples:,} verified technical listings across {tech_report.unique_companies_count:,} unique companies.")

    # Target and predictor matrix definition
    target_col = "salary_mid_lpa"
    y = df_tech[target_col].to_numpy(dtype=float)

    # Explicitly exclude all salary-related fields and IDs from X
    leakage_cols = [
        "salary_mid_lpa", "salary_min_lpa", "salary_max_lpa", "salary_annual_inr",
        "log_salary_lpa", "minimumSalary_clean", "maximumSalary_clean",
        "minimumSalary", "maximumSalary", "salary", "salary_status",
        "salary_range_invalid", "jobId", "duplicate_jobid_conflict",
    ]
    X = df_tech.drop(columns=[c for c in leakage_cols if c in df_tech.columns])
    groups = df_tech["companyName_clean"]

    print(f"    Features shape: {X.shape}, Target entries: {len(y)}, Groups: {groups.nunique()}")

    # Define candidate models wrapped with TransformedTargetRegressor (log1p/expm1)
    candidate_estimators = {
        "DummyRegressor (Median Baseline)": DummyRegressor(strategy="median"),
        "Linear Regression (OLS)": TransformedTargetRegressor(
            regressor=LinearRegression(),
            func=np.log1p,
            inverse_func=np.expm1,
        ),
        "Ridge Regression (alpha=1.0)": TransformedTargetRegressor(
            regressor=Ridge(alpha=1.0, random_state=random_state),
            func=np.log1p,
            inverse_func=np.expm1,
        ),
        "Ridge Regression (alpha=10.0)": TransformedTargetRegressor(
            regressor=Ridge(alpha=10.0, random_state=random_state),
            func=np.log1p,
            inverse_func=np.expm1,
        ),
        "Random Forest Regressor (n=100)": TransformedTargetRegressor(
            regressor=RandomForestRegressor(
                n_estimators=100,
                max_depth=12,
                min_samples_leaf=3,
                max_features=0.8,
                random_state=random_state,
                n_jobs=-1,
            ),
            func=np.log1p,
            inverse_func=np.expm1,
        ),
    }

    # 5-fold GroupKFold cross-validation
    print(">>> 2. Performing 5-fold GroupKFold Cross-Validation on employer groups...")
    gkf = GroupKFold(n_splits=5)

    comparison_results = []
    oof_predictions_dict: dict[str, np.ndarray] = {}

    for name, estimator in candidate_estimators.items():
        print(f"    Evaluating {name}...")
        oof_preds = np.zeros(total_tech_samples, dtype=float)

        for fold, (train_idx, val_idx) in enumerate(gkf.split(X, y, groups=groups)):
            X_tr, y_tr = X.iloc[train_idx], y[train_idx]
            X_val, y_val = X.iloc[val_idx], y[val_idx]

            fold_pipe = Pipeline([
                ("features", SalaryFeatureUnion(consolidate_ds_ml=True)),
                ("regressor", estimator),
            ])
            fold_pipe.fit(X_tr, y_tr)
            oof_preds[val_idx] = fold_pipe.predict(X_val)

        oof_predictions_dict[name] = oof_preds
        metrics = compute_regression_metrics(y, oof_preds, name)

        res_dict = {
            "model_name": name,
            "validation_strategy": "5-Fold GroupKFold (companyName_clean)",
            "sample_count": total_tech_samples,
            "cv_mae_lpa": round(metrics.mae_lpa, 3),
            "cv_medae_lpa": round(metrics.medae_lpa, 3),
            "cv_rmse_lpa": round(metrics.rmse_lpa, 3),
            "cv_r2_score": round(metrics.r2_score, 4),
            "cv_mape_pct": round(metrics.mape_pct, 2),
        }
        comparison_results.append(res_dict)
        print(f"      Out-of-Group CV -> MAE: {metrics.mae_lpa:.3f} LPA | RMSE: {metrics.rmse_lpa:.3f} LPA | R²: {metrics.r2_score:.4f} | MedAE: {metrics.medae_lpa:.3f} LPA")

    # Select champion model based on lowest Out-of-Group CV MAE
    sorted_models = sorted(comparison_results, key=lambda x: x["cv_mae_lpa"])
    champion_name = sorted_models[0]["model_name"]
    champion_cv_metrics = sorted_models[0]
    champion_oof_preds = oof_predictions_dict[champion_name]

    print(f"\n>>> 3. Champion Model Selected: '{champion_name}' (CV MAE: {champion_cv_metrics['cv_mae_lpa']:.3f} LPA, R²: {champion_cv_metrics['cv_r2_score']:.4f})")

    # Fit final champion pipeline on full technical dataset
    print(">>> 4. Fitting final champion pipeline on full technical cohort...")
    champion_estimator = candidate_estimators[champion_name]
    champion_pipeline = Pipeline([
        ("features", SalaryFeatureUnion(consolidate_ds_ml=True)),
        ("regressor", champion_estimator),
    ])
    champion_pipeline.fit(X, y)
    feature_names = champion_pipeline.named_steps["features"].get_feature_names_out()

    # Stratified role-wise evaluation on out-of-group predictions
    df_eval = df_tech.copy()
    df_eval["y_true"] = y
    df_eval["y_pred"] = champion_oof_preds
    df_eval["abs_error"] = np.abs(y - champion_oof_preds)

    def get_exp_tier(yrs: float) -> str:
        if yrs <= 1.0:
            return "0-1_years (Fresher)"
        elif yrs <= 4.0:
            return "2-4_years (Early Career)"
        elif yrs <= 8.0:
            return "5-8_years (Mid-Level)"
        elif yrs <= 12.0:
            return "9-12_years (Senior)"
        return "13+_years (Lead / Principal)"

    df_eval["exp_bracket"] = df_eval["experience_mid_years"].apply(get_exp_tier)

    # Consolidated 7-role metrics
    role_metrics = compute_stratified_metrics(df_eval, "role_model")
    # Original 8-role metrics (including DS vs ML individually)
    orig_role_metrics = compute_stratified_metrics(df_eval, "original_role_family")
    exp_metrics = compute_stratified_metrics(df_eval, "exp_bracket")

    # Calibrated Conformal Prediction Intervals (Group-aware)
    print(">>> 5. Calibrating Conformal Prediction Intervals on out-of-group residuals...")
    abs_res = df_eval["abs_error"].to_numpy()
    global_q90 = float(np.quantile(abs_res, 0.90))
    global_q80 = float(np.quantile(abs_res, 0.80))
    global_cov_90 = float(np.mean(abs_res <= global_q90) * 100.0)
    global_cov_80 = float(np.mean(abs_res <= global_q80) * 100.0)

    # Role-stratified conformal calibration
    role_conformal_calib: dict[str, dict[str, float]] = {}
    for r_name, group in df_eval.groupby("role_model"):
        r_err = group["abs_error"].to_numpy()
        r_q90 = float(np.quantile(r_err, 0.90))
        r_q80 = float(np.quantile(r_err, 0.80))
        role_conformal_calib[str(r_name)] = {
            "sample_count": len(group),
            "q90_lpa": round(r_q90, 3),
            "q80_lpa": round(r_q80, 3),
            "empirical_cov_90_pct": round(float(np.mean(r_err <= r_q90) * 100.0), 2),
            "empirical_cov_80_pct": round(float(np.mean(r_err <= r_q80) * 100.0), 2),
        }

    conformal_summary = {
        "calibration_strategy": "Out-of-Group Residual Non-Conformity (GroupKFold)",
        "nominal_coverage_targets_pct": [90.0, 80.0],
        "global_q90_lpa": round(global_q90, 3),
        "global_q80_lpa": round(global_q80, 3),
        "global_empirical_cov_90_pct": round(global_cov_90, 2),
        "global_empirical_cov_80_pct": round(global_cov_80, 2),
        "role_stratified_calibration": role_conformal_calib,
    }
    print(f"      Global 90% Conformal Quantile: {global_q90:.3f} LPA (Empirical Coverage: {global_cov_90:.2f}%)")
    print(f"      Global 80% Conformal Quantile: {global_q80:.3f} LPA (Empirical Coverage: {global_cov_80:.2f}%)")

    # Permutation Importance on champion pipeline
    print(">>> 6. Calculating Permutation Feature Importance...")
    perm_res = permutation_importance(
        champion_pipeline,
        X,
        y,
        n_repeats=5,
        random_state=random_state,
        scoring="neg_mean_absolute_error",
        n_jobs=-1,
    )
    sorted_importances_idx = perm_res.importances_mean.argsort()[::-1]
    top_permutation_features: list[dict[str, Any]] = []

    for idx in sorted_importances_idx[:25]:
        feat_name = feature_names[idx] if idx < len(feature_names) else f"feature_{idx}"
        top_permutation_features.append({
            "feature": feat_name,
            "importance": round(float(perm_res.importances_mean[idx]), 4),
            "mae_penalty_lpa": round(float(perm_res.importances_mean[idx]), 4),
            "std": round(float(perm_res.importances_std[idx]), 4),
        })

    # Empirical Role Medians for reference display
    role_medians = df_eval.groupby("role_model")["y_true"].median().to_dict()
    role_medians = {str(k): round(float(v), 2) for k, v in role_medians.items()}

    # Metadata payload
    output_payload = {
        "model_version": "2.0.0",
        "scope": "Core Technical Careers Only (Option A)",
        "champion_model_name": champion_name,
        "validation_strategy": "5-Fold GroupKFold on companyName_clean",
        "training_samples_count": total_tech_samples,
        "unique_companies_count": tech_report.unique_companies_count,
        "curation_summary": tech_report.to_dict(),
        "model_comparison": comparison_results,
        "champion_metrics": champion_cv_metrics,
        "role_breakdown_consolidated": role_metrics.to_dict(orient="records"),
        "role_breakdown_original": orig_role_metrics.to_dict(orient="records"),
        "experience_breakdown": exp_metrics.to_dict(orient="records"),
        "conformal_calibration": conformal_summary,
        "top_features": top_permutation_features,
        "top_permutation_features": top_permutation_features,
        "role_empirical_medians": role_medians,
    }

    if save_artifacts:
        # 1. Save v2.0.0 model artifact
        model_artifact_path = _ARTIFACTS_DIR / "salary_predictor_v2.0.0_tech_only.joblib"
        bundle_obj = {
            "pipeline": champion_pipeline,
            "champion_model_name": champion_name,
            "model_version": "2.0.0",
            "scope": "technical_careers_only",
            "feature_names": feature_names,
            "training_samples": total_tech_samples,
            "unique_companies": tech_report.unique_companies_count,
            "metrics": champion_cv_metrics,
            "role_medians": role_medians,
            "conformal_calibration": conformal_summary,
            "random_state": random_state,
        }
        joblib.dump(bundle_obj, model_artifact_path, compress=3)
        print(f">>> Saved champion v2.0.0 model artifact to: {model_artifact_path}")

        # 2. Save v2 metadata JSON
        metadata_path = _ARTIFACTS_DIR / "salary_model_metadata_v2.json"
        metadata_path.write_text(json.dumps(output_payload, indent=2), encoding="utf-8")
        print(f">>> Saved v2 metadata and evaluation report to: {metadata_path}")

        # 3. Save v2 model comparison JSON
        comp_path = _ARTIFACTS_DIR / "model_comparison_v2.json"
        comp_path.write_text(json.dumps(comparison_results, indent=2), encoding="utf-8")

    return output_payload


# Backwards compatibility alias
def train_and_evaluate_salary_models(
    csv_path: str | Path | None = None,
    save_artifacts: bool = True,
    random_state: int = 42,
) -> dict[str, Any]:
    """Train and evaluate the technical-only salary model v2.0.0."""
    return train_and_evaluate_technical_salary_models(
        csv_path=csv_path,
        save_artifacts=save_artifacts,
        random_state=random_state,
    )
