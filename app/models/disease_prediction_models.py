from typing import TYPE_CHECKING, Any

from tortoise import fields
from uuid_utils import uuid7

from ..core.enums import DiseaseRiskLevel
from ..core.utils.common import get_enum_max_length
from .base import TimestampModel

if TYPE_CHECKING:
    from .user_models import User


class DiseasePrediction(TimestampModel):
    id = fields.UUIDField(primary_key=True, default=uuid7)
    user: fields.ForeignKeyRelation["User"] = fields.ForeignKeyField("models.User", related_name="disease_predictions")
    using_model_name = fields.CharField(max_length=30, description="질병 위험도 예측에 사용한 모델 이름")
    threshold = fields.DecimalField(
        max_digits=3, decimal_places=2, description="질병 위험도 예측에 사용한 모델의 임계값(0~1)"
    )
    feature: dict[str, Any] = fields.JSONField(description="질병 위험도 예측에 사용한 변수 파라미터")

    class Meta:
        table = "disease_predictions"


class DiseasePredictionResult(TimestampModel):
    id = fields.UUIDField(primary_key=True, default=uuid7)
    prediction: fields.OneToOneRelation["DiseasePrediction"] = fields.OneToOneField(
        "models.DiseasePrediction", related_name="result"
    )
    confidence_score = fields.DecimalField(max_digits=5, decimal_places=2, description="질병 위험도 예측 신뢰도 점수")
    risk_score = fields.DecimalField(max_digits=5, decimal_places=2, description="질병 위험도 점수")
    risk_level = fields.CharEnumField(
        enum_type=DiseaseRiskLevel, max_length=get_enum_max_length(DiseaseRiskLevel), description="질병 위험도 레벨"
    )
    summary = fields.TextField(null=True, description="질병 위험도 예측 결과 요약")
    base_value = fields.DecimalField(
        max_digits=5, decimal_places=2, description="질병 위험도 예측에 사용한 모델의 기반값"
    )
    shap_results: dict[str, dict[str, Any]] = fields.JSONField(
        description="예측에 활용된 변수들의 가중치, 기여도 SHAP 분석 결과"
    )

    class Meta:
        table = "disease_prediction_results"


class DiseasePredictionReport(TimestampModel):
    id = fields.UUIDField(primary_key=True, default=uuid7)
    prediction: fields.OneToOneRelation["DiseasePrediction"] = fields.OneToOneField(
        "models.DiseasePrediction", related_name="report"
    )
    using_model_name = fields.CharField(max_length=30, description="질병 위험도 예측에 사용한 모델 이름")
    content = fields.TextField(max_length=3000, description="질병 위험도 예측 결과 요약")

    class Meta:
        table = "disease_prediction_reports"
