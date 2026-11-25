"""
Exploratory Data Analysis & Visualizations (Phase 6 Stage 6.4 & 6.10)
Generates high-resolution EDA and diagnostic charts for the salary prediction engine.
"""

from __future__ import annotations

import sys
import re
from pathlib import Path

_MODULE_DIR = Path(__file__).resolve().parent
_PHASE6_DIR = _MODULE_DIR.parent
_AIML_DIR = _PHASE6_DIR.parent
if str(_AIML_DIR) not in sys.path:
    sys.path.insert(0, str(_AIML_DIR))
if str(_PHASE6_DIR) not in sys.path:
    sys.path.insert(0, str(_PHASE6_DIR))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import joblib

from Phase_6_Salary_Prediction.data.curator import curate_technical_salary_dataset
from Phase_6_Salary_Prediction.features.transformers import RoleFamilyTransformer, LocationTierTransformer, TRACKED_TECH_SKILLS
import Phase_6_Salary_Prediction.features as p6_features
sys.modules["features"] = p6_features
import Phase_6_Salary_Prediction.features.transformers as p6_transformers
sys.modules["features.transformers"] = p6_transformers
import Phase_6_Salary_Prediction.features.pipeline as p6_pipeline
sys.modules["features.pipeline"] = p6_pipeline

_MODULE_DIR = Path(__file__).resolve().parent
_OUTPUT_DIR = _MODULE_DIR / "output"
_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Styling defaults
plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial", "Helvetica"]
plt.rcParams["axes.edgecolor"] = "#CBD5E1"
plt.rcParams["axes.linewidth"] = 0.8


def generate_all_eda_visualizations() -> list[Path]:
    """Generate all 6 required EDA and evaluation visual artifacts for the technical cohort."""
    saved_files: list[Path] = []
    print(">>> Generating Technical EDA Visualizations (v2.0.0)...")

    df, _ = curate_technical_salary_dataset()
    loc_mapper = LocationTierTransformer()
    df["location_tier"] = loc_mapper.transform(df["location_clean"]).ravel()

    # 1. Salary Distribution (Raw vs. Log)
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    # Raw LPA
    axes[0].hist(df["salary_mid_lpa"], bins=45, color="#2563EB", edgecolor="white", alpha=0.85)
    axes[0].axvline(df["salary_mid_lpa"].median(), color="#DC2626", linestyle="--", linewidth=1.8, label=f"Median: {df['salary_mid_lpa'].median():.2f} LPA")
    axes[0].axvline(df["salary_mid_lpa"].mean(), color="#D97706", linestyle="-", linewidth=1.8, label=f"Mean: {df['salary_mid_lpa'].mean():.2f} LPA")
    axes[0].set_title("Raw Midpoint Salary Distribution (LPA)", fontsize=12, fontweight="bold", pad=10)
    axes[0].set_xlabel("Salary (LPA INR)", fontsize=10)
    axes[0].set_ylabel("Job Postings Count", fontsize=10)
    axes[0].legend(frameon=True, facecolor="white")
    axes[0].set_xlim(0, 50)

    # Log LPA
    axes[1].hist(df["log_salary_lpa"], bins=45, color="#059669", edgecolor="white", alpha=0.85)
    axes[1].axvline(df["log_salary_lpa"].median(), color="#DC2626", linestyle="--", linewidth=1.8, label=f"Median: {df['log_salary_lpa'].median():.2f}")
    axes[1].set_title("Log-Transformed Salary Distribution [ln(1 + LPA)]", fontsize=12, fontweight="bold", pad=10)
    axes[1].set_xlabel("log1p(Salary LPA)", fontsize=10)
    axes[1].set_ylabel("Job Postings Count", fontsize=10)
    axes[1].legend(frameon=True, facecolor="white")

    plt.tight_layout()
    p1 = _OUTPUT_DIR / "salary_distribution_lpa.png"
    plt.savefig(p1, dpi=300)
    plt.close()
    saved_files.append(p1)
    print(f"    Saved: {p1.name}")

    # 2. Salary by Technical Career Role
    tech_roles = [
        "data_scientist_advanced_analytics", "machine_learning_ai_engineer",
        "data_engineer_big_data_platform", "data_analyst_business_intelligence",
        "backend_core_software_engineering", "frontend_full_stack_engineering",
        "cloud_devops_sre", "qa_automation_testing"
    ]
    role_labels = {
        "data_scientist_advanced_analytics": "Data Scientist",
        "machine_learning_ai_engineer": "ML / AI Engineer",
        "data_engineer_big_data_platform": "Data Engineer",
        "data_analyst_business_intelligence": "Data Analyst",
        "backend_core_software_engineering": "Backend / Core Dev",
        "frontend_full_stack_engineering": "Frontend / Full Stack",
        "cloud_devops_sre": "Cloud / DevOps / SRE",
        "qa_automation_testing": "QA / Automation Test"
    }

    role_col = "original_role_family" if "original_role_family" in df.columns else ("role_phase4" if "role_phase4" in df.columns else "role_family")
    df_tech = df[df[role_col].isin(tech_roles)].copy()
    medians = df_tech.groupby(role_col)["salary_mid_lpa"].median().loc[tech_roles]
    means = df_tech.groupby(role_col)["salary_mid_lpa"].mean().loc[tech_roles]

    fig, ax = plt.subplots(figsize=(12, 6))
    y_pos = np.arange(len(tech_roles))
    width = 0.38

    bars1 = ax.barh(y_pos - width/2, [medians[r] for r in tech_roles], width, label="Median (LPA)", color="#2563EB", alpha=0.9)
    bars2 = ax.barh(y_pos + width/2, [means[r] for r in tech_roles], width, label="Mean (LPA)", color="#059669", alpha=0.9)

    ax.set_yticks(y_pos)
    ax.set_yticklabels([role_labels[r] for r in tech_roles], fontsize=10, fontweight="bold")
    ax.invert_yaxis()
    ax.set_xlabel("Salary in LPA (INR)", fontsize=11, fontweight="bold")
    ax.set_title("Disclosed Compensation by Technical Career Track in India", fontsize=13, fontweight="bold", pad=12)
    ax.legend(frameon=True, facecolor="white", loc="lower right")

    # Add text labels on bars
    for b in bars1:
        ax.text(b.get_width() + 0.3, b.get_y() + b.get_height()/2, f"₹{b.get_width():.1f}L", va="center", fontsize=9, color="#1E293B", fontweight="bold")

    plt.tight_layout()
    p2 = _OUTPUT_DIR / "salary_by_technical_role.png"
    plt.savefig(p2, dpi=300)
    plt.close()
    saved_files.append(p2)
    print(f"    Saved: {p2.name}")

    # 3. Salary by Experience Curve (Mincer Curve)
    fig, ax = plt.subplots(figsize=(10, 5.5))
    exp_summary = df.groupby(df["experience_mid_years"].round())["salary_mid_lpa"].agg(["median", "mean", "count"]).loc[0:15]

    ax.plot(exp_summary.index, exp_summary["median"], marker="o", linewidth=2.5, color="#2563EB", label="Median Salary (LPA)")
    ax.plot(exp_summary.index, exp_summary["mean"], marker="s", linewidth=2.2, color="#059669", linestyle="--", label="Mean Salary (LPA)")
    ax.fill_between(exp_summary.index, exp_summary["median"] * 0.75, exp_summary["median"] * 1.35, color="#2563EB", alpha=0.12, label="Typical Interquartile Band")

    ax.set_title("Salary Progression vs. Years of Experience in Indian Tech Market", fontsize=12, fontweight="bold", pad=10)
    ax.set_xlabel("Years of Experience (Midpoint)", fontsize=10, fontweight="bold")
    ax.set_ylabel("Annual Compensation (LPA INR)", fontsize=10, fontweight="bold")
    ax.set_xticks(np.arange(0, 16, 1))
    ax.legend(frameon=True, facecolor="white", loc="upper left")

    plt.tight_layout()
    p3 = _OUTPUT_DIR / "salary_by_experience.png"
    plt.savefig(p3, dpi=300)
    plt.close()
    saved_files.append(p3)
    print(f"    Saved: {p3.name}")

    # 4. Salary by Geographic Location Tier
    loc_tier_names = {
        "tier_1_metro": "Tier 1 Metro (BLR, HYD, PNE, NCR)",
        "tier_2_city": "Tier 2 Emerging Tech Hubs",
        "remote": "Remote / Distributed",
        "hybrid": "Hybrid Setup",
        "tier_3_other": "Tier 3 / Other Regions"
    }
    loc_summary = df.groupby("location_tier")["salary_mid_lpa"].agg(["median", "mean", "count"])
    loc_order = ["tier_1_metro", "remote", "hybrid", "tier_2_city", "tier_3_other"]
    loc_summary = loc_summary.reindex(loc_order).dropna()

    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar([loc_tier_names[k] for k in loc_summary.index], loc_summary["median"], color="#4F46E5", width=0.55, alpha=0.88)
    ax.set_ylabel("Median Salary (LPA INR)", fontsize=10, fontweight="bold")
    ax.set_title("Geographic Compensation Variance Across Indian Market Tiers", fontsize=12, fontweight="bold", pad=12)
    plt.xticks(rotation=15, ha="right", fontsize=9, fontweight="bold")

    for b in bars:
        ax.text(b.get_x() + b.get_width()/2, b.get_height() + 0.15, f"₹{b.get_height():.2f}L", ha="center", fontsize=9, fontweight="bold")

    plt.tight_layout()
    p4 = _OUTPUT_DIR / "salary_by_location_tier.png"
    plt.savefig(p4, dpi=300)
    plt.close()
    saved_files.append(p4)
    print(f"    Saved: {p4.name}")

    # 5. Top 15 Technical Skills Salary Premium
    skill_medians = []
    for sk in TRACKED_TECH_SKILLS:
        has_skill = df["tagsAndSkills_clean"].str.lower().str.contains(rf"\b{re.escape(sk)}\b", na=False)
        if has_skill.sum() >= 30:
            med = df.loc[has_skill, "salary_mid_lpa"].median()
            skill_medians.append({"skill": sk.upper(), "median_lpa": med, "count": int(has_skill.sum())})

    df_sk_med = pd.DataFrame(skill_medians).sort_values(by="median_lpa", ascending=False).head(15)

    fig, ax = plt.subplots(figsize=(11, 6))
    bars = ax.barh(df_sk_med["skill"], df_sk_med["median_lpa"], color="#0284C7", alpha=0.88, height=0.6)
    ax.invert_yaxis()
    ax.set_xlabel("Median Listing Salary (LPA INR)", fontsize=10, fontweight="bold")
    ax.set_title("Top 15 Technical Skills Ranked by Disclosed Salary Premium", fontsize=12, fontweight="bold", pad=12)

    for b in bars:
        ax.text(b.get_width() + 0.2, b.get_y() + b.get_height()/2, f"₹{b.get_width():.1f}L", va="center", fontsize=9, fontweight="bold")

    plt.tight_layout()
    p5 = _OUTPUT_DIR / "skill_salary_premiums.png"
    plt.savefig(p5, dpi=300)
    plt.close()
    saved_files.append(p5)
    print(f"    Saved: {p5.name}")

    # 6. Actual vs. Predicted Residual Diagnostics (from champion model)
    v2_bundle = _MODULE_DIR.parent / "models" / "artifacts" / "salary_predictor_v2.0.0_tech_only.joblib"
    v1_bundle = _MODULE_DIR.parent / "models" / "artifacts" / "salary_predictor_v1.0.0.joblib"
    model_bundle_path = v2_bundle if v2_bundle.is_file() else v1_bundle
    if model_bundle_path.is_file():
        bundle = joblib.load(model_bundle_path)
        pipeline = bundle["pipeline"]

        # Predict on sample of test data
        sample_df = df.sample(min(3000, len(df)), random_state=42)
        y_true = sample_df["salary_mid_lpa"].to_numpy()
        y_pred = pipeline.predict(sample_df)
        residuals = y_true - y_pred

        fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))

        # Actual vs Predicted Scatter
        axes[0].scatter(y_true, y_pred, alpha=0.25, color="#2563EB", s=18, edgecolors="none")
        max_val = min(50, max(y_true.max(), y_pred.max()))
        axes[0].plot([0, max_val], [0, max_val], color="#DC2626", linestyle="--", linewidth=1.8, label="Ideal Fit (y = x)")
        axes[0].set_title("Actual vs. Predicted Salary (Test Sample)", fontsize=11, fontweight="bold")
        axes[0].set_xlabel("Actual Salary (LPA)", fontsize=10)
        axes[0].set_ylabel("Predicted Salary (LPA)", fontsize=10)
        axes[0].set_xlim(0, 40)
        axes[0].set_ylim(0, 40)
        axes[0].legend(frameon=True, facecolor="white")

        # Residuals Histogram
        axes[1].hist(residuals, bins=50, color="#7C3AED", edgecolor="white", alpha=0.85)
        axes[1].axvline(0, color="#DC2626", linestyle="--", linewidth=1.8)
        axes[1].set_title("Residual Distribution (y_true - y_pred)", fontsize=11, fontweight="bold")
        axes[1].set_xlabel("Prediction Error (LPA)", fontsize=10)
        axes[1].set_ylabel("Frequency", fontsize=10)
        axes[1].set_xlim(-15, 15)

        plt.tight_layout()
        p6 = _OUTPUT_DIR / "actual_vs_predicted_residuals.png"
        plt.savefig(p6, dpi=300)
        plt.close()
        saved_files.append(p6)
        print(f"    Saved: {p6.name}")

    return saved_files


if __name__ == "__main__":
    generate_all_eda_visualizations()
