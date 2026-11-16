from typing import TYPE_CHECKING, Any

from tortoise import fields
from uuid6 import uuid7

from ..core.enums import (
    ChallengeRecommendationStatus,
    DiseasePredictionStatus,
    DiseaseRiskLevel,
    PredictionModelType,
)
from ..core.utils.common import get_enum_max_length
from .base import TimestampModel

if TYPE_CHECKING:
    from .challenge_models import PersonalChallenge
    from .health_profiles import AnnualHealthScreening, MonthlyHealthSurvey
    from .user_models import User


class DiseasePrediction(TimestampModel):
    """
    위험도 예측 요청 1건입니다. id는 AI Worker에 보내는 task_id로 그대로 사용합니다.
    질환별 결과(당뇨·고혈압)는 DiseasePredictionResult에 저장합니다.
    """

    id = fields.UUIDField(primary_key=True, default=uuid7)
    user: fields.ForeignKeyRelation["User"] = fields.ForeignKeyField("models.User", related_name="disease_predictions")
    annual_health_screening: fields.ForeignKeyNullableRelation["AnnualHealthScreening"] = fields.ForeignKeyField(
        "models.AnnualHealthScreening",
        related_name="disease_predictions",
        null=True,
        on_delete=fields.SET_NULL,
        description="예측에 사용한 건강검진 기록",
    )
    monthly_health_survey: fields.ForeignKeyNullableRelation["MonthlyHealthSurvey"] = fields.ForeignKeyField(
        "models.MonthlyHealthSurvey",
        related_name="disease_predictions",
        null=True,
        on_delete=fields.SET_NULL,
        description="예측에 사용한 월간 건강 설문",
    )
    status = fields.CharEnumField(
        enum_type=DiseasePredictionStatus,
        max_length=get_enum_max_length(DiseasePredictionStatus),
        default=DiseasePredictionStatus.PENDING,
        description="예측 진행 상태",
    )
    feature: dict[str, Any] = fields.JSONField(description="AI Worker에 보낸 예측 입력")
    error_code = fields.CharField(max_length=30, null=True, description="예측 실패 코드")
    errors: list[dict[str, str]] | None = fields.JSONField(null=True, description="입력 오류 필드와 사유")
    started_at = fields.DatetimeField(null=True, description="AI Worker가 추론을 시작한 시간")
    completed_at = fields.DatetimeField(null=True, description="예측 완료(성공·실패) 시간")
    challenge_status = fields.CharEnumField(
        enum_type=ChallengeRecommendationStatus,
        max_length=get_enum_max_length(ChallengeRecommendationStatus),
        null=True,
        description="LLM 챌린지 추천 상태 (예측 완료 전에는 null)",
    )
    challenge_error_code = fields.CharField(max_length=30, null=True, description="챌린지 추천 실패 코드")
    challenge_model_name = fields.CharField(max_length=100, null=True, description="챌린지 추천에 사용한 LLM 모델 이름")
    challenge_started_at = fields.DatetimeField(null=True, description="챌린지 추천 생성 시작 시간")
    challenge_completed_at = fields.DatetimeField(null=True, description="챌린지 추천 완료(성공·실패) 시간")

    results: fields.ReverseRelation["DiseasePredictionResult"]
    challenges: fields.ReverseRelation["PersonalChallenge"]

    class Meta:
        table = "disease_predictions"


class DiseasePredictionResult(TimestampModel):
    id = fields.UUIDField(primary_key=True, default=uuid7)
    prediction: fields.ForeignKeyRelation["DiseasePrediction"] = fields.ForeignKeyField(
        "models.DiseasePrediction", related_name="results", on_delete=fields.CASCADE
    )
    model_type = fields.CharEnumField(
        enum_type=PredictionModelType,
        max_length=get_enum_max_length(PredictionModelType),
        description="예측 질환(모델 종류)",
    )
    model_version = fields.CharField(max_length=100, description="예측에 사용한 서빙 모델 버전")
    risk_probability = fields.DecimalField(max_digits=6, decimal_places=5, description="보정된 위험 확률(0~1)")
    risk_score = fields.DecimalField(max_digits=5, decimal_places=2, description="질병 위험도 점수(%, 0~100)")
    risk_level = fields.CharEnumField(
        enum_type=DiseaseRiskLevel, max_length=get_enum_max_length(DiseaseRiskLevel), description="질병 위험도 레벨"
    )
    threshold_moderate = fields.DecimalField(max_digits=6, decimal_places=5, description="MODERATE 등급 경계 확률")
    threshold_high = fields.DecimalField(max_digits=6, decimal_places=5, description="HIGH 등급 경계 확률")
    confidence_score = fields.DecimalField(
        max_digits=5, decimal_places=2, null=True, description="질병 위험도 예측 신뢰도 점수(현재 모델은 산출하지 않음)"
    )
    summary = fields.TextField(null=True, description="질병 위험도 예측 결과 요약")
    shap_output_space = fields.CharField(max_length=20, description="SHAP 값의 공간(probability, log_odds, raw)")
    base_value = fields.DecimalField(max_digits=12, decimal_places=6, description="SHAP 기준값")
    shap_results: list[dict[str, Any]] = fields.JSONField(description="위험도에 기여한 상위 요인의 SHAP 분석 결과")
    out_of_training_range: list[str] = fields.JSONField(description="학습 데이터 범위를 벗어난 입력 변수")

    class Meta:
        table = "disease_prediction_results"
        unique_together = (("prediction", "model_type"),)


class DiseasePredictionReport(TimestampModel):
    id = fields.UUIDField(primary_key=True, default=uuid7)
    prediction: fields.OneToOneRelation["DiseasePrediction"] = fields.OneToOneField(
        "models.DiseasePrediction", related_name="report"
    )
    using_model_name = fields.CharField(max_length=30, description="질병 위험도 예측에 사용한 모델 이름")
    content = fields.TextField(max_length=3000, description="질병 위험도 예측 결과 요약")

    class Meta:
        table = "disease_prediction_reports"
