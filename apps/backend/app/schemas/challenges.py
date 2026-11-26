from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.core.enums import ChallengeRecommendationStatus, ChallengeStatus, ChallengeType, PredictionModelType
from app.models.challenge_models import PersonalChallenge, PersonalChallengeHistory
from app.models.disease_prediction_models import DiseasePrediction
from app.services.challenge_progress import ChallengeProgress

HISTORY_MEMO_MAX_LENGTH = 300  # PersonalChallengeHistory.memo 길이와 같게 유지합니다.


class ChallengeTargetDiseaseResponse(BaseModel):
    model_type: PredictionModelType
    disease_name: str


class ChallengeBasisResponse(BaseModel):
    model_type: PredictionModelType
    feature: str
    display_name: str


class ChallengeProgressResponse(BaseModel):
    total_rounds: int
    required_success: int
    success_count: int
    recorded_count: int
    ends_on: date
    current_round: int | None
    can_record: bool

    @classmethod
    def from_progress(cls, progress: ChallengeProgress) -> "ChallengeProgressResponse":
        return cls(
            total_rounds=progress.total_rounds,
            required_success=progress.required_success,
            success_count=progress.success_count,
            recorded_count=progress.recorded_count,
            ends_on=progress.ends_on,
            current_round=progress.current_round,
            can_record=progress.can_record,
        )


class ChallengeHistoryResponse(BaseModel):
    id: int
    current_round: int
    is_success: bool
    memo: str | None
    created_at: datetime

    @classmethod
    def from_model(cls, history: PersonalChallengeHistory) -> "ChallengeHistoryResponse":
        return cls(
            id=history.id,
            current_round=history.current_round,
            is_success=history.is_success,
            memo=history.memo,
            created_at=history.created_at,
        )


class ChallengeHistoryCreateRequest(BaseModel):
    is_success: bool
    memo: str | None = Field(default=None, max_length=HISTORY_MEMO_MAX_LENGTH)

    @field_validator("memo")
    @classmethod
    def strip_memo(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


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
    # 수락한 챌린지의 진행 상황. 수락 전(PENDING)이거나 계산하지 않은 응답(예측별 추천 조회)에서는 null입니다.
    progress: ChallengeProgressResponse | None = None

    @classmethod
    def from_model(
        cls, challenge: PersonalChallenge, progress: ChallengeProgress | None = None
    ) -> "PersonalChallengeResponse":
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
            progress=ChallengeProgressResponse.from_progress(progress) if progress else None,
        )


class PersonalChallengeDetailResponse(PersonalChallengeResponse):
    histories: list[ChallengeHistoryResponse]

    @classmethod
    def from_detail(
        cls,
        challenge: PersonalChallenge,
        histories: list[PersonalChallengeHistory],
        progress: ChallengeProgress | None,
    ) -> "PersonalChallengeDetailResponse":
        base = PersonalChallengeResponse.from_model(challenge, progress)
        return cls(
            **base.model_dump(exclude={"progress"}),
            progress=base.progress,
            histories=[
                ChallengeHistoryResponse.from_model(history)
                for history in sorted(histories, key=lambda item: item.current_round)
            ],
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
