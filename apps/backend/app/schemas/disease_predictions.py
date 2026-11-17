from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.enums import DiseasePredictionStatus, DiseaseRiskLevel, PredictionModelType
from app.models.disease_prediction_models import DiseasePrediction, DiseasePredictionResult


class DiseasePredictionCreateRequest(BaseModel):
    """비워 두면 가장 최근 건강검진·월간 설문을 사용합니다."""

    model_config = ConfigDict(extra="forbid")

    annual_health_screening_id: UUID | None = None
    monthly_health_survey_id: UUID | None = None


class DiseasePredictionCreateResponse(BaseModel):
    id: UUID
    status: DiseasePredictionStatus
    events_url: str
    created_at: datetime


class RiskFactorResponse(BaseModel):
    feature: str
    display_name: str
    value: Any = None
    shap_value: float
    direction: str
    # False이면 생활습관으로 바꿀 수 없거나 역인과가 의심되는 요인으로, 챌린지 추천 근거로 쓰지 않습니다.
    actionable: bool
    reverse_causation_suspected: bool


class RiskThresholdsResponse(BaseModel):
    moderate: float
    high: float


class DiseasePredictionResultResponse(BaseModel):
    model_type: PredictionModelType
    disease_name: str
    model_version: str
    risk_probability: float
    risk_score: float
    risk_level: DiseaseRiskLevel
    risk_level_label: str
    risk_thresholds: RiskThresholdsResponse
    shap_output_space: str
    base_value: float
    risk_factors: list[RiskFactorResponse]
    out_of_training_range: list[str]

    @classmethod
    def from_model(cls, result: DiseasePredictionResult) -> "DiseasePredictionResultResponse":
        return cls(
            model_type=result.model_type,
            disease_name=result.model_type.label,
            model_version=result.model_version,
            risk_probability=float(result.risk_probability),
            risk_score=float(result.risk_score),
            risk_level=result.risk_level,
            risk_level_label=result.risk_level.label,
            risk_thresholds=RiskThresholdsResponse(
                moderate=float(result.threshold_moderate), high=float(result.threshold_high)
            ),
            shap_output_space=result.shap_output_space,
            base_value=float(result.base_value),
            risk_factors=[RiskFactorResponse.model_validate(factor) for factor in result.shap_results],
            out_of_training_range=list(result.out_of_training_range),
        )


class PredictionFieldErrorResponse(BaseModel):
    field: str
    reason: str


class DiseasePredictionResultSummaryResponse(BaseModel):
    model_type: PredictionModelType
    disease_name: str
    risk_score: float
    risk_level: DiseaseRiskLevel
    risk_level_label: str


class DiseasePredictionListResponse(BaseModel):
    id: UUID
    status: DiseasePredictionStatus
    created_at: datetime
    completed_at: datetime | None
    results: list[DiseasePredictionResultSummaryResponse]

    @classmethod
    def from_model(cls, prediction: DiseasePrediction) -> "DiseasePredictionListResponse":
        return cls(
            id=prediction.id,
            status=prediction.status,
            created_at=prediction.created_at,
            completed_at=prediction.completed_at,
            results=[
                DiseasePredictionResultSummaryResponse(
                    model_type=result.model_type,
                    disease_name=result.model_type.label,
                    risk_score=float(result.risk_score),
                    risk_level=result.risk_level,
                    risk_level_label=result.risk_level.label,
                )
                for result in _sorted_results(prediction)
            ],
        )


class DiseasePredictionResponse(BaseModel):
    id: UUID
    status: DiseasePredictionStatus
    status_label: str
    annual_health_screening_id: UUID | None
    monthly_health_survey_id: UUID | None
    error_code: str | None
    errors: list[PredictionFieldErrorResponse]
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    results: list[DiseasePredictionResultResponse]

    @classmethod
    def from_model(cls, prediction: DiseasePrediction) -> "DiseasePredictionResponse":
        return cls(
            id=prediction.id,
            status=prediction.status,
            status_label=prediction.status.label,
            annual_health_screening_id=prediction.annual_health_screening_id,  # type: ignore[attr-defined]
            monthly_health_survey_id=prediction.monthly_health_survey_id,  # type: ignore[attr-defined]
            error_code=prediction.error_code,
            errors=[PredictionFieldErrorResponse.model_validate(error) for error in prediction.errors or []],
            created_at=prediction.created_at,
            started_at=prediction.started_at,
            completed_at=prediction.completed_at,
            results=[DiseasePredictionResultResponse.from_model(result) for result in _sorted_results(prediction)],
        )


def _sorted_results(prediction: DiseasePrediction) -> list[DiseasePredictionResult]:
    """results는 prefetch되어 있어야 합니다. 질환 순서를 Enum 정의 순서로 고정합니다."""
    order = {model_type: index for index, model_type in enumerate(PredictionModelType)}
    return sorted(prediction.results, key=lambda result: order[result.model_type])
