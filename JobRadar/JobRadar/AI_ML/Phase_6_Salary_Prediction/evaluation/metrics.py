"""
Salary Prediction Evaluation Metrics (Phase 6 Stage 6.8 & 6.10)
Calculates MAE, MedAE, RMSE, R², MAPE, and role/experience stratified benchmarks.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, median_absolute_error, root_mean_squared_error, r2_score


@dataclass(frozen=True)
class RegressionEvaluationResult:
    """Standard evaluation metrics container for compensation modeling."""
    model_name: str
    sample_count: int
    mae_lpa: float
    medae_lpa: float
    rmse_lpa: float
    r2_score: float
    mape_pct: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "sample_count": self.sample_count,
            "mae_lpa": round(self.mae_lpa, 3),
            "medae_lpa": round(self.medae_lpa, 3),
            "rmse_lpa": round(self.rmse_lpa, 3),
            "r2_score": round(self.r2_score, 4),
            "mape_pct": round(self.mape_pct, 2),
        }


def compute_regression_metrics(
    y_true_lpa: np.ndarray | pd.Series,
    y_pred_lpa: np.ndarray | pd.Series,
    model_name: str = "Regressor",
) -> RegressionEvaluationResult:
    """Compute overall regression benchmark metrics in actual LPA units."""
    y_true = np.asarray(y_true_lpa, dtype=float).ravel()
    y_pred = np.asarray(y_pred_lpa, dtype=float).ravel()

    # Clamp predictions to realistic positive bounds
    y_pred_clamped = np.clip(y_pred, 0.5, 120.0)

    mae = float(mean_absolute_error(y_true, y_pred_clamped))
    medae = float(median_absolute_error(y_true, y_pred_clamped))
    rmse = float(root_mean_squared_error(y_true, y_pred_clamped))
    r2 = float(r2_score(y_true, y_pred_clamped))

    # Safe MAPE calculation
    valid_nonzero = y_true > 0.1
    if np.any(valid_nonzero):
        mape = float(np.mean(np.abs((y_true[valid_nonzero] - y_pred_clamped[valid_nonzero]) / y_true[valid_nonzero])) * 100.0)
    else:
        mape = 0.0

    return RegressionEvaluationResult(
        model_name=model_name,
        sample_count=len(y_true),
        mae_lpa=mae,
        medae_lpa=medae,
        rmse_lpa=rmse,
        r2_score=r2,
        mape_pct=mape,
    )


def compute_stratified_metrics(
    df_eval: pd.DataFrame,
    group_col: str,
    y_true_col: str = "y_true",
    y_pred_col: str = "y_pred",
) -> pd.DataFrame:
    """Compute performance breakdown across distinct groups (e.g. roles or experience)."""
    rows = []
    for grp, subset in df_eval.groupby(group_col):
        if len(subset) < 5:
            continue
        y_true = subset[y_true_col].to_numpy()
        y_pred = np.clip(subset[y_pred_col].to_numpy(), 0.5, 120.0)

        mae = mean_absolute_error(y_true, y_pred)
        medae = median_absolute_error(y_true, y_pred)
        rmse = root_mean_squared_error(y_true, y_pred)
        r2 = r2_score(y_true, y_pred) if len(y_true) > 1 and np.var(y_true) > 1e-4 else 0.0

        rows.append({
            group_col: grp,
            "sample_count": len(subset),
            "median_actual_lpa": round(float(np.median(y_true)), 2),
            "mean_actual_lpa": round(float(np.mean(y_true)), 2),
            "mae_lpa": round(float(mae), 3),
            "medae_lpa": round(float(medae), 3),
            "rmse_lpa": round(float(rmse), 3),
            "r2": round(float(r2), 4),
        })

    res_df = pd.DataFrame(rows)
    if not res_df.empty:
        res_df.sort_values(by="sample_count", ascending=False, inplace=True)
    return res_df
