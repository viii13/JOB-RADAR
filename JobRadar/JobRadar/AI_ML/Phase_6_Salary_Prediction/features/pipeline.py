"""
Salary Feature Pipeline (Phase 6 Stage 6.3 & 6.5)
Assembles modular feature extractors, categorical encoders, and scalers
into a unified, reproducible, scikit-learn compatible ColumnTransformer.
"""

from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .transformers import (
    ExperienceFeaturesTransformer,
    LocationTierTransformer,
    RoleFamilyTransformer,
    SeniorityTransformer,
    SkillIndicatorsTransformer,
    TRACKED_TECH_SKILLS,
    TECHNICAL_ROLE_FAMILIES,
)


def create_feature_pipeline() -> Pipeline:
    """Build a comprehensive feature transformation pipeline."""
    return Pipeline([
        ("preprocessor", SalaryFeatureUnion()),
    ])


class SalaryFeatureUnion(BaseEstimator, TransformerMixin):
    """
    Unified feature extractor transforming an input DataFrame into
    a clean 2D numerical numpy feature matrix.
    """

    def __init__(self, consolidate_ds_ml: bool = True) -> None:
        self.consolidate_ds_ml = consolidate_ds_ml
        self.role_mapper = RoleFamilyTransformer(consolidate_ds_ml=consolidate_ds_ml)
        self.role_encoder = OneHotEncoder(handle_unknown="ignore", sparse_output=False)

        self.seniority_extractor = SeniorityTransformer()
        self.seniority_encoder = OneHotEncoder(handle_unknown="ignore", sparse_output=False)

        self.location_tier_extractor = LocationTierTransformer()
        self.location_encoder = OneHotEncoder(handle_unknown="ignore", sparse_output=False)

        self.experience_extractor = ExperienceFeaturesTransformer()
        self.exp_num_scaler = StandardScaler()
        self.exp_cat_encoder = OneHotEncoder(handle_unknown="ignore", sparse_output=False)

        self.skills_extractor = SkillIndicatorsTransformer()

        self.feature_names_: list[str] = []

    def fit(self, X: pd.DataFrame, y: Any = None) -> SalaryFeatureUnion:
        # Title and role features
        titles = X["title_clean"] if "title_clean" in X.columns else X.get("title", pd.Series([""] * len(X)))
        roles = self.role_mapper.transform(X if "role_model" in X.columns else titles)
        self.role_encoder.fit(roles)

        seniorities = self.seniority_extractor.transform(titles)
        self.seniority_encoder.fit(seniorities)

        # Location features
        locations = X["location_clean"] if "location_clean" in X.columns else X.get("location", pd.Series([""] * len(X)))
        loc_tiers = self.location_tier_extractor.transform(locations)
        self.location_encoder.fit(loc_tiers)

        # Experience features
        exp_feats = self.experience_extractor.transform(X)
        exp_num = exp_feats[:, :2].astype(float)
        exp_cat = exp_feats[:, 2:].reshape(-1, 1)

        self.exp_num_scaler.fit(exp_num)
        self.exp_cat_encoder.fit(exp_cat)

        # Skills features (fixed indicators)
        skills_text = X["tagsAndSkills_clean"] if "tagsAndSkills_clean" in X.columns else X.get("skills", pd.Series([""] * len(X)))
        self.skills_extractor.fit(skills_text)

        # Build feature names
        self.feature_names_ = [
            *[f"role_{c}" for c in self.role_encoder.get_feature_names_out(["role"])],
            *[f"sen_{c}" for c in self.seniority_encoder.get_feature_names_out(["sen"])],
            *[f"loc_{c}" for c in self.location_encoder.get_feature_names_out(["loc"])],
            "exp_mid_years_scaled",
            "exp_mid_years_sq_scaled",
            *[f"exp_{c}" for c in self.exp_cat_encoder.get_feature_names_out(["tier"])],
            *self.skills_extractor.get_feature_names_out(),
        ]
        return self

    def transform(self, X: pd.DataFrame) -> np.ndarray:
        titles = X["title_clean"] if "title_clean" in X.columns else X.get("title", pd.Series([""] * len(X)))
        roles = self.role_mapper.transform(X if "role_model" in X.columns else titles)
        role_mat = self.role_encoder.transform(roles)

        seniorities = self.seniority_extractor.transform(titles)
        sen_mat = self.seniority_encoder.transform(seniorities)

        locations = X["location_clean"] if "location_clean" in X.columns else X.get("location", pd.Series([""] * len(X)))
        loc_tiers = self.location_tier_extractor.transform(locations)
        loc_mat = self.location_encoder.transform(loc_tiers)

        exp_feats = self.experience_extractor.transform(X)
        exp_num = exp_feats[:, :2].astype(float)
        exp_cat = exp_feats[:, 2:].reshape(-1, 1)
        exp_num_scaled = self.exp_num_scaler.transform(exp_num)
        exp_cat_mat = self.exp_cat_encoder.transform(exp_cat)

        skills_text = X["tagsAndSkills_clean"] if "tagsAndSkills_clean" in X.columns else X.get("skills", pd.Series([""] * len(X)))
        skills_mat = self.skills_extractor.transform(skills_text)

        return np.column_stack([
            role_mat,
            sen_mat,
            loc_mat,
            exp_num_scaled,
            exp_cat_mat,
            skills_mat,
        ])

    def fit_transform(self, X: pd.DataFrame, y: Any = None) -> np.ndarray:
        return self.fit(X, y).transform(X)

    def get_feature_names_out(self, input_features: Any = None) -> list[str]:
        return self.feature_names_
