from datetime import datetime
from typing import Any
from uuid import UUID

from tortoise.expressions import Q
from tortoise.transactions import in_transaction

from app.core.enums import ChallengeRecommendationStatus, ChallengeStatus, DiseasePredictionStatus
from app.models.challenge_models import PersonalChallenge
from app.models.disease_prediction_models import DiseasePrediction


class ChallengeRepository:
    async def claim_recommendation(
        self,
        prediction_id: UUID,
        started_at: datetime,
        stale_before: datetime,
        retry: bool = False,
    ) -> bool:
        """
        완료된(COMPLETED) 예측의 챌린지 추천을 PROCESSING으로 선점합니다. 선점하지 못하면 False를 반환합니다.

        선점 가능한 상태
            - 아직 시작하지 않음(null)
            - 생성 중(PROCESSING)이지만 stale_before보다 먼저 시작해 중단된 것으로 보이는 경우
            - retry=True이면 실패(FAILED)
        조건부 UPDATE 한 번으로 처리하므로, 여러 요청이 동시에 시도해도 한 곳만 선점합니다.
        """
        claimable = Q(challenge_status__isnull=True) | Q(
            challenge_status=ChallengeRecommendationStatus.PROCESSING, challenge_started_at__lt=stale_before
        )
        if retry:
            claimable |= Q(challenge_status=ChallengeRecommendationStatus.FAILED)
        updated = (
            await DiseasePrediction.filter(id=prediction_id, status=DiseasePredictionStatus.COMPLETED)
            .filter(claimable)
            .update(
                challenge_status=ChallengeRecommendationStatus.PROCESSING,
                challenge_started_at=started_at,
                challenge_error_code=None,
                challenge_model_name=None,
                challenge_completed_at=None,
            )
        )
        return updated > 0

    async def get_prediction_for_recommendation(self, prediction_id: UUID) -> DiseasePrediction | None:
        return (
            await DiseasePrediction.filter(id=prediction_id)
            .prefetch_related("results", "monthly_health_survey")
            .first()
        )

    async def save_recommendations(
        self,
        prediction_id: UUID,
        claimed_at: datetime,
        challenges: list[dict[str, Any]],
        model_name: str,
        completed_at: datetime,
    ) -> bool:
        """
        선점한 실행(claimed_at)만 결과를 저장합니다. 그 사이 다른 실행이 다시 선점했다면 False를 반환하고 저장하지 않습니다.
        상태 변경과 챌린지 저장을 한 트랜잭션으로 묶습니다.
        """
        async with in_transaction():
            updated = await DiseasePrediction.filter(
                id=prediction_id,
                challenge_status=ChallengeRecommendationStatus.PROCESSING,
                challenge_started_at=claimed_at,
            ).update(
                challenge_status=ChallengeRecommendationStatus.COMPLETED,
                challenge_model_name=model_name,
                challenge_completed_at=completed_at,
            )
            if updated == 0:
                return False
            await PersonalChallenge.bulk_create([PersonalChallenge(**challenge) for challenge in challenges])
        return True

    async def mark_recommendation_failed(
        self, prediction_id: UUID, claimed_at: datetime, error_code: str, completed_at: datetime
    ) -> bool:
        updated = await DiseasePrediction.filter(
            id=prediction_id,
            challenge_status=ChallengeRecommendationStatus.PROCESSING,
            challenge_started_at=claimed_at,
        ).update(
            challenge_status=ChallengeRecommendationStatus.FAILED,
            challenge_error_code=error_code,
            challenge_completed_at=completed_at,
        )
        return updated > 0

    async def get_list_by_prediction(self, prediction_id: UUID) -> list[PersonalChallenge]:
        return await PersonalChallenge.filter(prediction_id=prediction_id).order_by("id")

    async def get_list_by_user(self, user_id: UUID, status: ChallengeStatus | None = None) -> list[PersonalChallenge]:
        queryset = PersonalChallenge.filter(user_id=user_id)
        if status is not None:
            queryset = queryset.filter(status=status)
        return await queryset.order_by("-created_at", "-id")
