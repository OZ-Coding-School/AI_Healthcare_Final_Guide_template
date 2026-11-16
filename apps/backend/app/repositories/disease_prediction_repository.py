from datetime import datetime
from typing import Any
from uuid import UUID

from tortoise.transactions import in_transaction

from app.core.enums import DiseasePredictionStatus
from app.models.disease_prediction_models import DiseasePrediction, DiseasePredictionResult

IN_PROGRESS = DiseasePredictionStatus.in_progress()


class DiseasePredictionRepository:
    async def create_pending(
        self,
        user_id: UUID,
        feature: dict[str, Any],
        annual_health_screening_id: UUID,
        monthly_health_survey_id: UUID,
    ) -> DiseasePrediction:
        return await DiseasePrediction.create(
            user_id=user_id,
            feature=feature,
            annual_health_screening_id=annual_health_screening_id,
            monthly_health_survey_id=monthly_health_survey_id,
            status=DiseasePredictionStatus.PENDING,
        )

    async def get_by_id(self, user_id: UUID, prediction_id: UUID) -> DiseasePrediction | None:
        return await DiseasePrediction.filter(user_id=user_id, id=prediction_id).prefetch_related("results").first()

    async def get_list_by_user_id(self, user_id: UUID) -> list[DiseasePrediction]:
        return await DiseasePrediction.filter(user_id=user_id).order_by("-created_at").prefetch_related("results")

    async def exists_in_progress_since(self, user_id: UUID, since: datetime) -> bool:
        return await DiseasePrediction.filter(user_id=user_id, status__in=IN_PROGRESS, created_at__gte=since).exists()

    async def mark_processing(self, prediction_id: UUID, started_at: datetime) -> bool:
        """PENDING인 예측만 PROCESSING으로 바꿉니다. 이미 처리 중이거나 확정된 예측이면 False를 반환합니다."""
        updated = await DiseasePrediction.filter(id=prediction_id, status=DiseasePredictionStatus.PENDING).update(
            status=DiseasePredictionStatus.PROCESSING,
            started_at=started_at,
        )
        return updated > 0

    async def mark_failed(
        self,
        prediction_id: UUID,
        error_code: str,
        errors: list[dict[str, str]],
        completed_at: datetime,
        created_before: datetime | None = None,
    ) -> bool:
        """
        확정되지 않은(PENDING·PROCESSING) 예측만 실패로 바꿉니다. 이미 확정된 예측이면 False를 반환합니다.

        :param created_before: 지정하면 이 시각 이전에 만든 예측만 바꿉니다 (결과 보관 시간 초과 처리).
        """
        queryset = DiseasePrediction.filter(id=prediction_id, status__in=IN_PROGRESS)
        if created_before is not None:
            queryset = queryset.filter(created_at__lt=created_before)
        updated = await queryset.update(
            status=DiseasePredictionStatus.FAILED,
            error_code=error_code,
            errors=errors,
            completed_at=completed_at,
        )
        return updated > 0

    async def save_completed(
        self,
        prediction_id: UUID,
        results: list[dict[str, Any]],
        completed_at: datetime,
    ) -> bool:
        """
        확정되지 않은 예측만 COMPLETED로 바꾸고 질환별 결과를 저장합니다. 이미 확정된 예측이면 False를 반환합니다.
        상태 변경과 결과 저장을 한 트랜잭션으로 묶어, 동시에 확정을 시도해도 결과가 한 번만 저장됩니다.
        """
        async with in_transaction():
            updated = await DiseasePrediction.filter(id=prediction_id, status__in=IN_PROGRESS).update(
                status=DiseasePredictionStatus.COMPLETED,
                completed_at=completed_at,
            )
            if updated == 0:
                return False
            await DiseasePredictionResult.bulk_create(
                [DiseasePredictionResult(prediction_id=prediction_id, **result) for result in results]
            )
        return True
