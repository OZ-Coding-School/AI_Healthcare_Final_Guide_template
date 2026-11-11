import json
import logging
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from src.components.data_preprocessor import KnhanesPreprocessor
from src.components.knhanes_inference_errors import InferenceInputError, ModelArtifactError
from src.components.knhanes_input_adapter import to_knhanes_raw_frame
from src.components.knhanes_probability_calibrator import ProbabilityCalibrator
from src.components.knhanes_service_input import parse_service_input
from src.components.knhanes_serving_bundle import (
    build_display_feature_metadata,
    build_serving_metadata,
    file_sha256,
    load_serving_bundle,
    write_manifest,
)
from src.components.model_trainer import BinaryClassificationModelTrainer, ModelBundle
from src.enums import ModelAlgorithm, ModelType
from src.knhanes_inference_configs import SERVING_MODEL_DIR, serving_bundle_filename
from src.pipelines.inference_pipeline import KnhanesRiskPredictor
from tests.test_knhanes_input_adapter import valid_payload

SYNTHETIC_ROWS = 300


def _random_payload(rng: np.random.Generator) -> dict[str, Any]:
    sbp = int(rng.integers(100, 170))
    drinking = str(rng.choice(["NEVER", "FORMER", "CURRENT"]))
    smoking = str(rng.choice(["NEVER", "FORMER", "CURRENT"]))
    return valid_payload(
        gender=str(rng.choice(["M", "F"])),
        birth_date=f"{int(rng.integers(1940, 2000))}-0{int(rng.integers(1, 9))}-15",
        has_diabetes=bool(rng.random() < 0.15),
        has_hypertension=bool(rng.random() < 0.3),
        height=float(rng.uniform(150, 190)),
        weight=float(rng.uniform(45, 100)),
        waist_circumference=float(rng.uniform(65, 110)),
        sbp=sbp,
        dbp=int(sbp - rng.integers(30, 60)),
        fbs=int(rng.integers(75, 160)),
        hba1c=float(rng.uniform(4.8, 8.0)),
        triglyceride=int(rng.integers(50, 400)),
        total_cholesterol=int(rng.integers(130, 280)),
        hdl=int(rng.integers(30, 80)),
        urine_protein=str(rng.choice(["-", "±", "1+"])),
        urine_glucose=str(rng.choice(["-", "±", "1+"])),
        diabetes_family_history={
            "father": str(rng.choice(["YES", "NO", "UNKNOWN"])),
            "mother": str(rng.choice(["YES", "NO", "UNKNOWN"])),
            "siblings": str(rng.choice(["YES", "NO", "UNKNOWN", "NO_SIBLINGS"])),
        },
        hypertension_family_history={
            "father": str(rng.choice(["YES", "NO", "UNKNOWN"])),
            "mother": str(rng.choice(["YES", "NO", "UNKNOWN"])),
            "siblings": str(rng.choice(["YES", "NO", "UNKNOWN", "NO_SIBLINGS"])),
        },
        smoking_status=smoking,
        cigarettes_per_day=int(rng.integers(1, 30)) if smoking == "CURRENT" else None,
        drinking_status=drinking,
        drinking_frequency="WEEKLY_2_TO_3" if drinking == "CURRENT" else "NOT_APPLICABLE",
        drinks_per_session=int(rng.integers(1, 12)) if drinking == "CURRENT" else None,
    )


def _build_synthetic_bundle(model_type: ModelType, raw: pd.DataFrame, rng: np.random.Generator) -> ModelBundle:
    features = KnhanesPreprocessor(use_case=model_type).preprocess(raw)
    score = (features["나이"] - 55) / 15 + (features["허리둘레"] - 85) / 15 + rng.normal(0, 0.7, len(features))
    y = pd.Series((score > 0.3).astype(int), name="label")

    bundle = BinaryClassificationModelTrainer(
        features,
        y,
        algorithm=ModelAlgorithm.LIGHTGBM,
        hyperparameters={"n_estimators": 30, "verbose": -1},
    ).train()
    raw_prob = np.asarray(bundle.model.predict_proba(bundle.transform(features)))[:, 1]
    bundle.calibrator = ProbabilityCalibrator("sigmoid").fit(raw_prob, y)
    bundle.risk_thresholds = {"moderate": 0.2, "high": 0.6}
    bundle.feature_metadata = build_display_feature_metadata(bundle)
    bundle.metadata = build_serving_metadata(
        bundle=bundle,
        model_type=model_type,
        train_set="synthetic",
        algorithm=str(ModelAlgorithm.LIGHTGBM),
        source_model_sha256="0" * 64,
        X_train=features,
        test_metrics={},
    )
    return bundle


def _write_serving_dir(model_dir: Path, bundles: dict[ModelType, ModelBundle]) -> None:
    model_dir.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for model_type, bundle in bundles.items():
        path = model_dir / serving_bundle_filename(model_type)
        bundle.save(path)
        manifest[str(model_type)] = {"file": path.name, "sha256": file_sha256(path)}
    write_manifest(model_dir, manifest)


@pytest.fixture(scope="module")
def serving_dir(tmp_path_factory) -> Path:
    rng = np.random.default_rng(42)
    raw = pd.concat(
        [to_knhanes_raw_frame(parse_service_input(_random_payload(rng))) for _ in range(SYNTHETIC_ROWS)],
        ignore_index=True,
    )
    model_dir = tmp_path_factory.mktemp("serving")
    _write_serving_dir(
        model_dir, {model_type: _build_synthetic_bundle(model_type, raw, rng) for model_type in ModelType}
    )
    return model_dir


@pytest.fixture(scope="module")
def predictor(serving_dir: Path) -> KnhanesRiskPredictor:
    return KnhanesRiskPredictor(model_dir=serving_dir)


def _copy_serving_dir(serving_dir: Path, tmp_path: Path) -> Path:
    target = tmp_path / "serving_copy"
    shutil.copytree(serving_dir, target)
    return target


class TestKnhanesRiskPredictor:
    @pytest.mark.parametrize("model_type", list(ModelType))
    def test_predict_returns_risk_and_grouped_factors(self, predictor, model_type):
        result = predictor.predict(valid_payload(), model_type)

        assert 0 <= result.risk_probability <= 1
        thresholds = result.risk_thresholds
        expected_level = (
            "HIGH"
            if result.risk_probability >= thresholds["high"]
            else "MODERATE"
            if result.risk_probability >= thresholds["moderate"]
            else "LOW"
        )
        assert result.risk_level == expected_level
        assert result.shap_output_space == "log_odds"
        assert result.model_version.startswith(f"{model_type}:synthetic:LightGBM:")
        assert 0 < len(result.risk_factors) <= 5

        schema_columns = predictor._models[model_type].bundle.metadata["input_schema"]["columns"]
        assert all(factor.feature in schema_columns for factor in result.risk_factors)
        assert json.loads(json.dumps(result.to_dict(), ensure_ascii=False))["model_type"] == str(model_type)

    def test_predict_all_returns_both_models(self, predictor):
        results = predictor.predict_all(valid_payload())
        assert set(results) == set(ModelType)

    @pytest.mark.parametrize("model_type", list(ModelType))
    def test_probability_is_calibrated_and_shap_adds_up_to_raw_logit(self, serving_dir, model_type):
        predictor = KnhanesRiskPredictor(model_dir=serving_dir, model_types=[model_type], top_k=100)
        bundle = predictor._models[model_type].bundle
        features = predictor._prepare_features(parse_service_input(valid_payload()), model_type)

        result = predictor.predict(valid_payload(), model_type)
        raw_prob = float(np.asarray(bundle.model.predict_proba(bundle.transform(features)))[0, 1])

        assert result.risk_probability == pytest.approx(float(bundle.predict_proba(features)[0]))
        assert result.risk_probability != pytest.approx(raw_prob)
        total = result.shap_base_value + sum(factor.shap_value for factor in result.risk_factors)
        assert total == pytest.approx(np.log(raw_prob / (1 - raw_prob)), abs=1e-6)

    def test_non_actionable_and_reverse_causation_flags(self, serving_dir):
        predictor = KnhanesRiskPredictor(model_dir=serving_dir, model_types=[ModelType.DIABETES_RISK], top_k=100)
        factors = {f.feature: f for f in predictor.predict(valid_payload(), ModelType.DIABETES_RISK).risk_factors}

        assert factors["나이"].actionable is False
        assert factors["총콜레스테롤"].reverse_causation_suspected is True
        assert factors["총콜레스테롤"].actionable is False
        assert factors["허리둘레"].actionable is True
        assert factors["당뇨병 가족력(부)"].display_name == "당뇨병 가족력(아버지)"

    def test_invalid_input_raises_input_error(self, predictor):
        with pytest.raises(InferenceInputError):
            predictor.predict(valid_payload(height=10.0), ModelType.DIABETES_RISK)

    def test_out_of_training_range_is_flagged(self, predictor):
        result = predictor.predict(valid_payload(height=210.0), ModelType.HYPERTENSION_RISK)
        assert "키" in result.out_of_training_range

    def test_unseen_category_is_rejected(self, serving_dir):
        predictor = KnhanesRiskPredictor(model_dir=serving_dir, model_types=[ModelType.DIABETES_RISK])
        predictor._models[ModelType.DIABETES_RISK].bundle.metadata["input_schema"]["categorical"]["성별"] = ["F"]
        with pytest.raises(ModelArtifactError, match="성별"):
            predictor.predict(valid_payload(gender="M"), ModelType.DIABETES_RISK)

    def test_unloaded_model_type_is_rejected(self, serving_dir):
        predictor = KnhanesRiskPredictor(model_dir=serving_dir, model_types=[ModelType.DIABETES_RISK])
        with pytest.raises(ModelArtifactError):
            predictor.predict(valid_payload(), ModelType.HYPERTENSION_RISK)

    def test_logs_do_not_contain_input_values(self, predictor, caplog):
        caplog.set_level(logging.DEBUG)
        predictor.predict_all(valid_payload(height=181.3, total_cholesterol=247))
        assert "181.3" not in caplog.text
        assert "247" not in caplog.text


class TestServingBundleLoading:
    def test_saved_bundle_reloads_with_identical_predictions(self, serving_dir):
        features = KnhanesPreprocessor(use_case=ModelType.DIABETES_RISK).preprocess(
            to_knhanes_raw_frame(parse_service_input(valid_payload()))
        )
        loaded = load_serving_bundle(serving_dir, ModelType.DIABETES_RISK)
        direct = ModelBundle.load(serving_dir / serving_bundle_filename(ModelType.DIABETES_RISK))
        assert np.array_equal(loaded.predict_proba(features), direct.predict_proba(features))

    def test_hash_mismatch_is_rejected(self, serving_dir, tmp_path):
        model_dir = _copy_serving_dir(serving_dir, tmp_path)
        with (model_dir / serving_bundle_filename(ModelType.DIABETES_RISK)).open("ab") as file:
            file.write(b"tampered")
        with pytest.raises(ModelArtifactError, match="hash"):
            load_serving_bundle(model_dir, ModelType.DIABETES_RISK)

    def test_missing_manifest_is_rejected(self, tmp_path):
        with pytest.raises(ModelArtifactError, match="manifest"):
            KnhanesRiskPredictor(model_dir=tmp_path)

    def test_bundle_for_another_model_type_is_rejected(self, serving_dir, tmp_path):
        model_dir = _copy_serving_dir(serving_dir, tmp_path)
        bundle = ModelBundle.load(model_dir / serving_bundle_filename(ModelType.DIABETES_RISK))
        _write_serving_dir(model_dir, {ModelType.DIABETES_RISK: bundle, ModelType.HYPERTENSION_RISK: bundle})
        with pytest.raises(ModelArtifactError, match="built for"):
            load_serving_bundle(model_dir, ModelType.HYPERTENSION_RISK)

    def test_bundle_without_metadata_is_rejected(self, serving_dir, tmp_path):
        model_dir = _copy_serving_dir(serving_dir, tmp_path)
        bundle = ModelBundle.load(model_dir / serving_bundle_filename(ModelType.DIABETES_RISK))
        bundle.metadata = None
        _write_serving_dir(model_dir, {ModelType.DIABETES_RISK: bundle})
        with pytest.raises(ModelArtifactError, match="metadata"):
            load_serving_bundle(model_dir, ModelType.DIABETES_RISK)

    def test_training_bundle_without_metadata_still_loads(self, serving_dir, tmp_path):
        bundle = ModelBundle.load(serving_dir / serving_bundle_filename(ModelType.DIABETES_RISK))
        legacy_path = tmp_path / "legacy.pkl"
        bundle.metadata = None
        bundle.save(legacy_path)
        assert ModelBundle.load(legacy_path).metadata is None


# 실제 산출물 검증: 원시 데이터·서빙 번들이 없는 환경에서는 건너뜁니다.
REAL_SPLIT_DIR = Path(__file__).resolve().parents[1] / "data" / "processed" / "knhanes"
REAL_LABELED_DIR = Path(__file__).resolve().parents[1] / "data" / "interim" / "labeled"
real_artifacts = pytest.mark.skipif(
    not (SERVING_MODEL_DIR / "serving_manifest.json").exists() or not REAL_SPLIT_DIR.exists(),
    reason="KNHANES serving bundles or split data are not available",
)


@real_artifacts
@pytest.mark.parametrize("model_type", list(ModelType))
def test_real_training_and_inference_preprocessing_match(model_type):
    """Validation 원시 코드를 추론용 전처리에 넣으면 학습에 쓴 X_validation과 같아야 합니다."""
    bundle = load_serving_bundle(SERVING_MODEL_DIR, model_type)
    split_dir = REAL_SPLIT_DIR / str(model_type) / bundle.metadata["train_set"]
    X_validation = pd.read_parquet(split_dir / "X_validation.parquet")
    ids = pd.read_parquet(split_dir / "meta_validation.parquet")["ID"]

    labeled = pd.read_parquet(REAL_LABELED_DIR / f"{model_type}.parquet").set_index("ID").loc[ids].reset_index()
    features = KnhanesPreprocessor(use_case=model_type).preprocess(labeled)

    assert features.columns.tolist() == X_validation.columns.tolist()
    pd.testing.assert_frame_equal(
        features.astype(str).reset_index(drop=True), X_validation.astype(str).reset_index(drop=True)
    )
    assert np.array_equal(bundle.predict_proba(features), bundle.predict_proba(X_validation))


@real_artifacts
@pytest.mark.parametrize("model_type", list(ModelType))
def test_real_serving_bundle_matches_evaluated_model(model_type):
    bundle = load_serving_bundle(SERVING_MODEL_DIR, model_type)
    source_dir = SERVING_MODEL_DIR.parent / "knhanes_tuned"
    meta = bundle.metadata
    source_path = source_dir / f"{model_type}_{meta['train_set']}_{meta['algorithm']}.pkl"
    if not source_path.exists():
        pytest.skip("Source tuned bundle is not available")

    assert file_sha256(source_path) == meta["source_model_sha256"]
    X_validation = pd.read_parquet(REAL_SPLIT_DIR / str(model_type) / meta["train_set"] / "X_validation.parquet")
    assert np.array_equal(ModelBundle.load(source_path).predict_proba(X_validation), bundle.predict_proba(X_validation))
