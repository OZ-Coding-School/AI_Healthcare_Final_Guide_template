from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.core.enums import ChallengeRecommendationStatus, ChallengeStatus, ChallengeType, PredictionModelType
from app.models.challenge_models import PersonalChallenge
from app.models.disease_prediction_models import DiseasePrediction


class ChallengeTargetDiseaseResponse(BaseModel):
    model_type: PredictionModelType
    disease_name: str


class ChallengeBasisResponse(BaseModel):
    model_type: PredictionModelType
    feature: str
    display_name: str


class PersonalChallengeResponse(BaseModel):
    id: int
    prediction_id: UUID | None
    title: str
    description: str
    challenge_type: ChallengeType
    challenge_type_label: str
    total_rounds: int | None
    expected_effect: str
    target_diseases: list[ChallengeTargetDiseaseResponse]
    basis: list[ChallengeBasisResponse]
    status: ChallengeStatus
    status_label: str
    expired_at: datetime
    joined_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    @classmethod
    def from_model(cls, challenge: PersonalChallenge) -> "PersonalChallengeResponse":
        diseases = [PredictionModelType(value) for value in challenge.target_diseases or []]
        return cls(
            id=challenge.id,
            prediction_id=challenge.prediction_id,  # type: ignore[attr-defined]
            title=challenge.title,
            description=challenge.description,
            challenge_type=challenge.challenge_type,
            challenge_type_label=challenge.challenge_type.label,
            total_rounds=challenge.total_rounds,
            expected_effect=challenge.expected_effect,
            target_diseases=[
                ChallengeTargetDiseaseResponse(model_type=disease, disease_name=disease.label) for disease in diseases
            ],
            basis=[ChallengeBasisResponse.model_validate(item) for item in challenge.basis or []],
            status=challenge.status,
            status_label=challenge.status.label,
            expired_at=challenge.expired_at,
            joined_at=challenge.joined_at,
            completed_at=challenge.completed_at,
            created_at=challenge.created_at,
        )


class ChallengeRecommendationResponse(BaseModel):
    prediction_id: UUID
    # 예측 완료 직후 아주 짧은 순간에는 null일 수 있습니다. PROCESSING이면 잠시 후 다시 조회합니다.
    status: ChallengeRecommendationStatus | None
    status_label: str | None
    error_code: str | None
    model_name: str | None
    started_at: datetime | None
    completed_at: datetime | None
    challenges: list[PersonalChallengeResponse]

    @classmethod
    def from_model(
        cls, prediction: DiseasePrediction, challenges: list[PersonalChallenge]
    ) -> "ChallengeRecommendationResponse":
        challenge_status = prediction.challenge_status
        return cls(
            prediction_id=prediction.id,
            status=challenge_status,
            status_label=challenge_status.label if challenge_status else None,
            error_code=prediction.challenge_error_code,
            model_name=prediction.challenge_model_name,
            started_at=prediction.challenge_started_at,
            completed_at=prediction.challenge_completed_at,
            challenges=[PersonalChallengeResponse.from_model(challenge) for challenge in challenges],
        )
