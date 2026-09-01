from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest
from lightgbm import LGBMClassifier
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier

from src.components.model_trainer import (
    BinaryClassificationModelTrainer,
    ModelBundle,
    ModelFactory,
)
from src.enums import ModelAlgorithm


@pytest.fixture
def sample_dataset() -> tuple[pd.DataFrame, pd.Series]:
    np.random.seed(42)
    df = pd.DataFrame(
        {
            "age": [25, 30, 45, 50, 60, 35, 40, 55, 65, 70] * 5,
            "bmi": [22.5, 24.0, 28.5, 31.0, 26.0, 23.0, 29.0, 32.0, 27.0, 33.0] * 5,
            "gender": ["M", "F", "F", "M", "M", "F", "M", "F", "M", "F"] * 5,
        }
    )
    y = pd.Series([0, 0, 1, 1, 1, 0, 1, 1, 1, 1] * 5, name="target")
    return df, y


@pytest.fixture
def numeric_only_dataset() -> tuple[pd.DataFrame, pd.Series]:
    df = pd.DataFrame(
        {
            "age": [25, 30, 45, 50, 60, 35, 40, 55, 65, 70] * 5,
            "bmi": [22.5, 24.0, 28.5, 31.0, 26.0, 23.0, 29.0, 32.0, 27.0, 33.0] * 5,
        }
    )
    y = pd.Series([0, 0, 1, 1, 1, 0, 1, 1, 1, 1] * 5, name="target")
    return df, y


def test_model_factory_creation():
    model = ModelFactory.create(
        algorithm=ModelAlgorithm.RANDOM_FOREST,
        random_state=42,
        hyperparameters={"n_estimators": 50, "max_depth": 5},
    )
    assert isinstance(model, RandomForestClassifier)
    assert model.n_estimators == 50
    assert model.max_depth == 5
    assert model.random_state == 42


def test_model_factory_invalid_algorithm():
    with pytest.raises(ValueError, match="Invalid algorithm"):
        ModelFactory.create("unsupported_algo")  # type: ignore


def test_trainer_without_saving(sample_dataset, tmp_path: Path):
    x_train, y_train = sample_dataset
    trainer = BinaryClassificationModelTrainer(
        x_train=x_train,
        y_train=y_train,
        output_filename="test_model",
        algorithm=ModelAlgorithm.RANDOM_FOREST,
        model_dir=tmp_path,
    )
    bundle = trainer.train(auto_save=False)

    assert isinstance(bundle, ModelBundle)
    assert "age" in bundle.feature_names
    assert "bmi" in bundle.feature_names
    # auto_save=False should not create any file
    assert not list(tmp_path.glob("*.pkl"))


def test_trainer_with_saving_and_load(sample_dataset, tmp_path: Path):
    x_train, y_train = sample_dataset
    trainer = BinaryClassificationModelTrainer(
        x_train=x_train,
        y_train=y_train,
        output_filename="test_model",
        algorithm=ModelAlgorithm.LIGHTGBM,
        use_resampling=True,
        model_dir=tmp_path,
    )
    bundle = trainer.train(auto_save=True)

    expected_path = tmp_path / f"test_model_{ModelAlgorithm.LIGHTGBM}_resampled.pkl"
    assert expected_path.exists()

    loaded_bundle = ModelBundle.load(expected_path)

    assert isinstance(loaded_bundle.model, LGBMClassifier)
    assert loaded_bundle.feature_names == bundle.feature_names


def test_trainer_numeric_only_dataset(numeric_only_dataset, tmp_path: Path):
    x_train, y_train = numeric_only_dataset
    trainer = BinaryClassificationModelTrainer(
        x_train=x_train,
        y_train=y_train,
        algorithm=ModelAlgorithm.LOGISTIC_REGRESSION,
        model_dir=tmp_path,
    )
    bundle = trainer.train()

    assert isinstance(bundle, ModelBundle)
    assert bundle.feature_names == ["age", "bmi"]


def test_trainer_smotenc_with_categorical_and_nan():
    # 불균형 데이터셋 및 결측치 포함 데이터 생성
    df = pd.DataFrame(
        {
            "age": [25, np.nan, 45, 50, 60, 35, 40, 55, 65, 70] * 5,
            "bmi": [22.5, 24.0, np.nan, 31.0, 26.0, 23.0, 29.0, 32.0, 27.0, 33.0] * 5,
            "category": ["A", "B", None, "A", "B", "C", "A", "B", "C", "A"] * 5,
        }
    )
    # 극심한 불균형 타겟 (클래스 0: 45개, 클래스 1: 5개)
    y = pd.Series([0] * 45 + [1] * 5, name="target")

    trainer = BinaryClassificationModelTrainer(
        x_train=df,
        y_train=y,
        algorithm=ModelAlgorithm.RANDOM_FOREST,
        use_resampling=True,
        random_state=42,
    )
    bundle = trainer.train()

    assert isinstance(bundle, ModelBundle)
    assert any("category" in f or "A" in f for f in bundle.feature_names)

    # 테스트 데이터 변환 및 예측 정상 수행 확인
    test_df = pd.DataFrame(
        {
            "age": [30, np.nan],
            "bmi": [np.nan, 25.0],
            "category": ["A", "missing"],
        }
    )
    x_test_proc = bundle.preprocessor.transform(test_df)
    if bundle.post_preprocessor is not None:
        x_test_proc = bundle.post_preprocessor.transform(x_test_proc)
    predictions = bundle.model.predict(x_test_proc)
    assert len(predictions) == 2


def test_trainer_numeric_only_with_smote(numeric_only_dataset):
    x_train, y_train = numeric_only_dataset
    trainer = BinaryClassificationModelTrainer(
        x_train=x_train,
        y_train=y_train,
        algorithm=ModelAlgorithm.RANDOM_FOREST,
        use_resampling=True,
    )
    bundle = trainer.train()
    assert isinstance(bundle, ModelBundle)
    assert bundle.feature_names == ["age", "bmi"]


def test_trainer_custom_threshold(sample_dataset, tmp_path: Path):
    x_train, y_train = sample_dataset
    trainer = BinaryClassificationModelTrainer(
        x_train=x_train,
        y_train=y_train,
        algorithm=ModelAlgorithm.RANDOM_FOREST,
        threshold=0.65,
        model_dir=tmp_path,
    )
    bundle = trainer.train()
    assert isinstance(bundle, ModelBundle)
    assert bundle.threshold == 0.65


def test_bundle_transform_and_direct_load(sample_dataset, tmp_path: Path):
    x_train, y_train = sample_dataset
    trainer = BinaryClassificationModelTrainer(
        x_train=x_train,
        y_train=y_train,
        algorithm=ModelAlgorithm.RANDOM_FOREST,
        use_resampling=True,
        model_dir=tmp_path,
    )
    bundle = trainer.train()
    save_file = tmp_path / "bundle_test.pkl"
    bundle.save(save_file)

    loaded_bundle = ModelBundle.load(save_file)
    assert isinstance(loaded_bundle, ModelBundle)
    assert loaded_bundle.feature_metadata is not None

    transformed_arr = loaded_bundle.transform(x_train.head(5))
    assert isinstance(transformed_arr, np.ndarray)
    assert transformed_arr.shape == (5, len(loaded_bundle.feature_names))


def test_model_bundle_load_file_not_found(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        ModelBundle.load(tmp_path / "non_existing.pkl")


def test_model_bundle_load_backward_compatibility(tmp_path: Path):
    # post_preprocessor 및 threshold 키가 없는 이전 버전 번들 파일 로드 테스트
    model_path = tmp_path / "legacy_model.pkl"
    legacy_bundle_data = {
        "model": RandomForestClassifier(),
        "preprocessor": ColumnTransformer(transformers=[]),
        "feature_names": ["feat1", "feat2"],
    }
    joblib.dump(legacy_bundle_data, model_path)

    bundle = ModelBundle.load(model_path)
    assert isinstance(bundle, ModelBundle)
    assert bundle.post_preprocessor is None
    assert bundle.feature_names == ["feat1", "feat2"]
    assert bundle.threshold == 0.5
