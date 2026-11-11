"""
당뇨·고혈압 위험도 추론 파이프라인입니다.

입력 검증 → KNHANES 코드 변환 → 학습과 같은 전처리 → 보정 확률 → 위험 등급 → SHAP 설명 순서로 처리합니다.
번들과 SHAP Explainer는 생성 시 1회만 준비하므로, Worker는 KnhanesRiskPredictor를 한 번 만들어 재사용합니다.

위험도는 현재 건강 데이터가 비슷한 집단의 유병 확률이며 미래 발병 예측이나 진단이 아닙니다.
건강 정보 보호를 위해 이 모듈은 입력값과 위험도를 로그에 남기지 않습니다.
"""

import logging
import math
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.components.data_preprocessor import KnhanesPreprocessor
from src.components.knhanes_inference_errors import ModelArtifactError
from src.components.knhanes_input_adapter import to_knhanes_raw_frame
from src.components.knhanes_multi_year_loader import KnhanesDataValidationError
from src.components.knhanes_risk_threshold import RiskThresholds
from src.components.knhanes_service_input import ServiceHealthInput, parse_service_input
from src.components.knhanes_serving_bundle import load_serving_bundle, model_version
from src.components.model_trainer import ModelBundle
from src.components.shap_explainer import ShapExplainer
from src.enums import ModelType
from src.knhanes_inference_configs import (
    NON_ACTIONABLE_FEATURES,
    REVERSE_CAUSATION_SUSPECTED_FEATURES_MAP,
    SERVING_MODEL_DIR,
    SHAP_TOP_K,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RiskFactor:
    feature: str
    display_name: str
    value: Any
    shap_value: float
    direction: str
    actionable: bool
    reverse_causation_suspected: bool


@dataclass(frozen=True)
class DiseaseRiskPrediction:
    model_type: str
    model_version: str
    risk_probability: float
    risk_level: str
    risk_thresholds: dict[str, float]
    shap_output_space: str
    shap_base_value: float
    risk_factors: list[RiskFactor] = field(default_factory=list)
    out_of_training_range: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class _LoadedModel:
    bundle: ModelBundle
    preprocessor: KnhanesPreprocessor
    explainer: ShapExplainer
    thresholds: RiskThresholds
    version: str


class KnhanesRiskPredictor:
    def __init__(
        self,
        model_dir: Path = SERVING_MODEL_DIR,
        model_types: Iterable[ModelType] = tuple(ModelType),
        top_k: int = SHAP_TOP_K,
    ) -> None:
        if top_k < 1:
            raise ValueError("top_k must be at least 1")
        self.top_k = top_k
        self._models: dict[ModelType, _LoadedModel] = {}
        for model_type in model_types:
            bundle = load_serving_bundle(model_dir, model_type)
            self._models[model_type] = _LoadedModel(
                bundle=bundle,
                preprocessor=KnhanesPreprocessor(use_case=model_type),
                explainer=ShapExplainer.from_bundle(bundle),
                thresholds=RiskThresholds(**bundle.risk_thresholds),  # type: ignore[arg-type]
                version=model_version(bundle),
            )
            logger.info("Loaded serving bundle %s", self._models[model_type].version)

    @property
    def model_types(self) -> list[ModelType]:
        return list(self._models)

    def predict(self, payload: ServiceHealthInput | Mapping[str, Any], model_type: ModelType) -> DiseaseRiskPrediction:
        if model_type not in self._models:
            raise ModelArtifactError(f"{model_type}: model is not loaded")
        service_input = parse_service_input(payload)
        return self._predict(service_input, model_type)

    def predict_all(self, payload: ServiceHealthInput | Mapping[str, Any]) -> dict[ModelType, DiseaseRiskPrediction]:
        """입력을 한 번만 검증하고, 불러온 모든 모델로 위험도를 계산합니다."""
        service_input = parse_service_input(payload)
        return {model_type: self._predict(service_input, model_type) for model_type in self._models}

    def _predict(self, service_input: ServiceHealthInput, model_type: ModelType) -> DiseaseRiskPrediction:
        loaded = self._models[model_type]
        features = self._prepare_features(service_input, model_type)

        probability = float(loaded.bundle.predict_proba(features)[0])
        if not math.isfinite(probability) or not 0 <= probability <= 1:
            raise ModelArtifactError(f"{model_type}: model returned an invalid probability")
        risk_level = str(loaded.thresholds.classify(np.array([probability]))[0])

        explanation = loaded.explainer.explain_instance(features, top_k=self.top_k, group_by_original=True)
        reverse_suspected = REVERSE_CAUSATION_SUSPECTED_FEATURES_MAP.get(model_type, set())
        risk_factors = [
            RiskFactor(
                feature=contribution.feature,
                display_name=contribution.display_name,
                value=_to_json_value(contribution.value),
                shap_value=float(contribution.shap_value),
                direction=contribution.direction,
                actionable=contribution.feature not in NON_ACTIONABLE_FEATURES
                and contribution.feature not in reverse_suspected,
                reverse_causation_suspected=contribution.feature in reverse_suspected,
            )
            for contribution in explanation.contributions
        ]

        return DiseaseRiskPrediction(
            model_type=str(model_type),
            model_version=loaded.version,
            risk_probability=probability,
            risk_level=risk_level,
            risk_thresholds=loaded.thresholds.to_dict(),
            shap_output_space=explanation.output_space,
            shap_base_value=float(explanation.base_value),
            risk_factors=risk_factors,
            out_of_training_range=self._out_of_training_range(features, loaded.bundle),
        )

    def _prepare_features(self, service_input: ServiceHealthInput, model_type: ModelType) -> pd.DataFrame:
        """학습과 같은 전처리를 적용하고 번들의 입력 스키마와 대조합니다."""
        loaded = self._models[model_type]
        raw = to_knhanes_raw_frame(service_input)
        try:
            features = loaded.preprocessor.preprocess(raw)
        except KnhanesDataValidationError as error:
            # 서비스 입력은 이미 검증했으므로 여기서 실패하면 변환 규칙과 모델의 불일치입니다.
            raise ModelArtifactError(f"{model_type}: converted input failed preprocessing") from error

        schema = loaded.bundle.metadata["input_schema"]  # type: ignore[index]
        if features.columns.tolist() != schema["columns"]:
            raise ModelArtifactError(f"{model_type}: preprocessed columns differ from the model input schema")

        unknown = [
            column
            for column, allowed in schema["categorical"].items()
            if features[column].notna().any() and str(features[column].iloc[0]) not in allowed
        ]
        if unknown:
            # OneHotEncoder는 처음 보는 범주를 오류 없이 무시하므로 여기서 막습니다.
            raise ModelArtifactError(f"{model_type}: categories unseen in training: {unknown}")
        return features

    @staticmethod
    def _out_of_training_range(features: pd.DataFrame, bundle: ModelBundle) -> list[str]:
        """학습 데이터 범위를 벗어난 수치 입력입니다. 트리 모델은 범위 끝값처럼 예측하므로 해석에 주의가 필요합니다."""
        ranges = bundle.metadata["numeric_ranges"]  # type: ignore[index]
        result = []
        for column, bounds in ranges.items():
            value = features[column].iloc[0]
            if pd.notna(value) and not bounds["min"] <= float(value) <= bounds["max"]:
                result.append(column)
        return result


def _to_json_value(value: Any) -> Any:
    """numpy·pandas 값과 Enum을 JSON으로 직렬화 가능한 값으로 바꿉니다. 결측은 None입니다."""
    if value is None:
        return None
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, (bool, int, float)):
        return value
    if pd.isna(value):
        return None
    return str(value)
