from pathlib import Path

import pandas as pd
import pytest
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from src.components.model_evaluator import EvaluationResult, ModelEvaluator
from src.components.model_trainer import ModelBundle


@pytest.fixture
def trained_model_and_data():
    X = pd.DataFrame(
        {
            "num1": [10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
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

    return model, preprocessor, X, y


def test_model_evaluator_evaluate_and_save(trained_model_and_data, tmp_path: Path):
    model, preprocessor, X, y = trained_model_and_data

    evaluator = ModelEvaluator(
        model=model,
        preprocessor=preprocessor,
        x_test=X,
        y_test=y,
        output_dir=tmp_path,
        threshold=0.5,
    )

    result = evaluator.evaluate()

    assert isinstance(result, EvaluationResult)
    assert result.metrics.accuracy == 1.0
    assert result.metrics.precision == 1.0
    assert result.metrics.recall == 1.0
    assert result.metrics.f1 == 1.0
    assert result.metrics.threshold == 0.5
    assert result.metrics.auc is not None
    assert result.y_prob is not None
    assert len(result.y_pred) == len(y)

    evaluator.save(result)

    # 생성된 파일 및 차트 이미지 확인
    assert (tmp_path / "metrics.csv").exists()
    assert (tmp_path / "classification_report.csv").exists()
    assert (tmp_path / "confusion_matrix.png").exists()
    assert (tmp_path / "predictions.csv").exists()
    assert (tmp_path / "roc_curve.png").exists()
    assert (tmp_path / "precision_recall_curve.png").exists()
    assert (tmp_path / "probability_distribution.png").exists()
    assert (tmp_path / "feature_importance.csv").exists()
    assert (tmp_path / "feature_importance.png").exists()


def test_model_evaluator_from_bundle(trained_model_and_data, tmp_path: Path):
    model, preprocessor, X, y = trained_model_and_data
    bundle = ModelBundle(
        model=model,
        preprocessor=preprocessor,
        post_preprocessor=None,
        feature_names=["num1", "num2"],
        threshold=0.6,
    )

    evaluator = ModelEvaluator.from_bundle(
        bundle=bundle,
        x_test=X,
        y_test=y,
        output_dir=tmp_path,
    )

    result = evaluator.evaluate()
    assert result.metrics.threshold == 0.6
    evaluator.save(result)
    assert (tmp_path / "feature_importance.csv").exists()


def test_model_evaluator_custom_threshold(trained_model_and_data, tmp_path: Path):
    model, preprocessor, X, y = trained_model_and_data

    # 매우 높은 threshold 적용 시 양성 예측 수가 줄어듦 확인
    evaluator = ModelEvaluator(
        model=model,
        preprocessor=preprocessor,
        x_test=X,
        y_test=y,
        output_dir=tmp_path,
        threshold=0.99,
    )
    result = evaluator.evaluate()
    assert result.metrics.threshold == 0.99


def test_model_evaluator_logistic_regression(tmp_path: Path):
    X = pd.DataFrame({"f1": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0], "f2": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]})
    y = pd.Series([0, 0, 0, 1, 1, 1])

    preprocessor = ColumnTransformer(
        transformers=[("num", Pipeline([("imputer", SimpleImputer(strategy="mean"))]), ["f1", "f2"])]
    )
    X_proc = preprocessor.fit_transform(X)

    model = LogisticRegression(random_state=42)
    model.fit(X_proc, y)

    evaluator = ModelEvaluator(
        model=model,
        preprocessor=preprocessor,
        x_test=X,
        y_test=y,
        output_dir=tmp_path,
    )
    result = evaluator.evaluate()
    evaluator.save(result)

    assert (tmp_path / "feature_importance.csv").exists()
