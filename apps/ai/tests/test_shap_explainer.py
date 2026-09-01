from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.components.model_trainer import ModelBundle
from src.components.shap_explainer import (
    FeatureContribution,
    FeatureMetadata,
    LocalExplanation,
    ShapExplainer,
    ShapExplanationResult,
)


@pytest.fixture
def sample_data():
    X = pd.DataFrame(
        {
            "num1": [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0],
            "num2": [1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5, 8.5, 9.5, 10.5],
        }
    )
    y = pd.Series([0, 0, 0, 0, 0, 1, 1, 1, 1, 1], name="target")

    preprocessor = ColumnTransformer(
        transformers=[("num", Pipeline([("imputer", SimpleImputer(strategy="mean"))]), ["num1", "num2"])]
    )
    X_proc = preprocessor.fit_transform(X)

    model = RandomForestClassifier(random_state=42, n_estimators=10)
    model.fit(X_proc, y)

    bundle = ModelBundle(
        model=model,
        preprocessor=preprocessor,
        post_preprocessor=None,
        feature_names=["num1", "num2"],
        threshold=0.5,
    )
    return bundle, X, y


def test_shap_explainer_explain_dataset(sample_data, tmp_path: Path):
    bundle, X, _ = sample_data
    explainer = ShapExplainer.from_bundle(bundle)

    result = explainer.explain_dataset(X, output_dir=tmp_path, max_samples=5)

    assert isinstance(result, ShapExplanationResult)
    assert len(result.feature_importances) == 2
    assert "feature" in result.feature_importances.columns
    assert "importance" in result.feature_importances.columns
    assert "importance_ratio" in result.feature_importances.columns
    assert np.isclose(result.feature_importances["importance_ratio"].sum(), 1.0)
    assert result.shap_values.shape == (5, 2)
    assert result.feature_names == ["num1", "num2"]
    assert result.output_space in ["probability", "log_odds", "raw"]

    # 산출 파일 검증
    assert (tmp_path / "shap_feature_importance.csv").exists()
    assert (tmp_path / "shap_summary.png").exists()
    assert (tmp_path / "shap_bar.png").exists()


def test_shap_explainer_explain_instance(sample_data):
    bundle, X, _ = sample_data
    explainer = ShapExplainer.from_bundle(bundle)

    single_row = X.iloc[0]
    local_exp = explainer.explain_instance(single_row, top_k=1)

    assert isinstance(local_exp, LocalExplanation)
    assert isinstance(local_exp.base_value, float)
    assert isinstance(local_exp.prediction_value, float)
    assert local_exp.output_space in ["probability", "log_odds", "raw"]
    assert len(local_exp.contributions) == 1

    contrib = local_exp.contributions[0]
    assert isinstance(contrib, FeatureContribution)
    assert contrib.feature in ["num1", "num2"]
    assert contrib.direction in ["increase", "decrease"]
    assert contrib.value == 10.0 or contrib.value == 1.5


def test_shap_explainer_with_metadata(tmp_path: Path):
    X = pd.DataFrame(
        {
            "age": [25, 45, 65, 30, 50, 70],
            "smoking": ["NO", "YES", "YES", "NO", "YES", "NO"],
        }
    )
    y = pd.Series([0, 1, 1, 0, 1, 0])

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), ["age"]),
            ("cat", OneHotEncoder(sparse_output=False, handle_unknown="ignore"), ["smoking"]),
        ]
    )

    X_proc = preprocessor.fit_transform(X)
    model = RandomForestClassifier(random_state=42, n_estimators=10)
    model.fit(X_proc, y)

    feature_metadata = [
        FeatureMetadata(
            model_feature_name="num__age",
            original_feature_name="age",
            display_name="연령",
        ),
        FeatureMetadata(
            model_feature_name="cat__smoking_NO",
            original_feature_name="smoking",
            display_name="비흡연",
        ),
        FeatureMetadata(
            model_feature_name="cat__smoking_YES",
            original_feature_name="smoking",
            display_name="흡연",
        ),
    ]

    bundle = ModelBundle(
        model=model,
        preprocessor=preprocessor,
        post_preprocessor=None,
        feature_names=["num__age", "cat__smoking_NO", "cat__smoking_YES"],
        feature_metadata=feature_metadata,
        threshold=0.5,
    )

    explainer = ShapExplainer.from_bundle(bundle)
    local_exp = explainer.explain_instance({"age": 45, "smoking": "YES"})

    assert isinstance(local_exp, LocalExplanation)
    assert len(local_exp.contributions) == 3

    # UI display_name과 actual value(45, YES) 매핑 확인
    contrib_map = {c.feature: c for c in local_exp.contributions}
    assert contrib_map["num__age"].display_name == "연령"
    assert contrib_map["num__age"].value == 45
    assert contrib_map["cat__smoking_YES"].display_name == "흡연"
    assert contrib_map["cat__smoking_YES"].value == "YES"

    # positive_contributions / negative_contributions property 검증
    pos_contribs = local_exp.positive_contributions
    neg_contribs = local_exp.negative_contributions
    assert isinstance(pos_contribs, list)
    assert isinstance(neg_contribs, list)
    assert all(c.shap_value > 0 for c in pos_contribs)
    assert all(c.shap_value < 0 for c in neg_contribs)


def test_shap_explainer_linear_model(tmp_path: Path):
    X = pd.DataFrame({"f1": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0], "f2": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]})
    y = pd.Series([0, 0, 0, 1, 1, 1])

    preprocessor = ColumnTransformer(
        transformers=[("num", Pipeline([("imputer", SimpleImputer(strategy="mean"))]), ["f1", "f2"])]
    )
    X_proc = preprocessor.fit_transform(X)

    model = LogisticRegression(random_state=42)
    model.fit(X_proc, y)

    bundle = ModelBundle(
        model=model,
        preprocessor=preprocessor,
        post_preprocessor=None,
        feature_names=["f1", "f2"],
        threshold=0.5,
    )

    explainer = ShapExplainer.from_bundle(bundle, background_data=X, background_size=4)
    assert len(explainer.background_data) == 4

    result = explainer.explain_dataset(X, output_dir=tmp_path)

    assert isinstance(result, ShapExplanationResult)
    assert (tmp_path / "shap_feature_importance.csv").exists()

    single_dict = {"f1": 3.5, "f2": 0.35}
    local_expl = explainer.explain_instance(single_dict)
    assert isinstance(local_expl, LocalExplanation)
    assert len(local_expl.contributions) == 2
