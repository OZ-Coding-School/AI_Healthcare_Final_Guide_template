"""
질병 위험도 예측 요청 발행, 결과 확정, SSE 전송을 담당합니다.

흐름
    1. 프로필·건강검진·월간 설문을 예측 입력으로 조합하고 미리 검증합니다.
    2. DiseasePrediction(PENDING)을 만들고 id를 task_id로 요청 Stream에 발행합니다.
    3. AI Worker가 Task를 가져가면 결과 Stream에 처리 시작 항목을 남기고(→ PROCESSING),
       추론을 마치면 최종 결과로 대체합니다(→ COMPLETED·FAILED).
    4. SSE 또는 상세 조회에서 결과 Stream을 읽어 상태를 DB에 반영합니다.

Task 상태: 정상 PENDING → PROCESSING → COMPLETED, 비정상 PENDING → PROCESSING → FAILED.
결과 Stream 항목은 _apply_result_entry 한 곳에서만 반영하며, 상태 조건부 업데이트로 여러 번 호출되어도 한 번만 저장됩니다.
건강 정보 보호를 위해 입력값과 위험도는 로그에 남기지 않습니다.
"""

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID

import redis.asyncio as redis
from fastapi import Depends, HTTPException
from fastapi.exceptions import RequestValidationError
from redis.exceptions import RedisError
from starlette import status

from app.core import logger, settings
from app.core.enums import DiseasePredictionStatus
from app.core.utils.prediction_stream import (
    PREDICTION_REQUEST_STREAM,
    REQUEST_STREAM_MAXLEN,
    RESULT_TTL_SECONDS,
    DiseaseRiskMessage,
    PredictionErrorCode,
    PredictionProcessingMessage,
    PredictionResultParseError,
    PredictionTaskStatus,
    build_request_fields,
    parse_result_fields,
    result_stream_key,
)
from app.core.utils.redis import get_redis
from app.models.disease_prediction_models import DiseasePrediction
from app.models.health_profiles import AnnualHealthScreening, MonthlyHealthSurvey
from app.repositories.annual_health_screening_repository import AnnualHealthScreeningRepository
from app.repositories.disease_prediction_repository import DiseasePredictionRepository
from app.repositories.health_profile_repository import HealthProfileRepository
from app.repositories.monthly_health_survey_repository import MonthlyHealthSurveyRepository
from app.schemas.disease_predictions import DiseasePredictionCreateRequest, DiseasePredictionResponse
from app.services.disease_prediction_input import PredictionInputError, build_prediction_payload

# SSE 이벤트 이름
SSE_EVENT_STATUS = "status"  # 진행 상태 (연결 시 현재 상태, PROCESSING으로 바뀔 때)
SSE_EVENT_RESULT = "result"  # 예측 성공
SSE_EVENT_FAILED = "failed"  # 예측 실패 (입력 오류, 모델 오류 등)
SSE_EVENT_TIMEOUT = "timeout"  # 대기 시간 초과 (예측은 계속 진행 중일 수 있음)
SSE_EVENT_ERROR = "error"  # 서버 오류로 결과를 확인할 수 없음

# Worker 오류 중 사용자에게 필드별 사유를 보여줄 코드: 나머지는 내부 사정이므로 사유를 숨깁니다.
USER_VISIBLE_ERROR_CODES = {PredictionErrorCode.INVALID_INPUT}


def _now() -> datetime:
    return datetime.now(settings.TIMEZONE)


def format_sse(event: str, data: str) -> str:
    """SSE 이벤트 1건입니다. data는 줄바꿈이 없는 JSON 문자열이어야 합니다."""
    return f"event: {event}\ndata: {data}\n\n"


SSE_HEARTBEAT = ": heartbeat\n\n"


class DiseasePredictionService:
    def __init__(
        self,
        repository: DiseasePredictionRepository,
        health_profile_repo: HealthProfileRepository,
        annual_health_screening_repo: AnnualHealthScreeningRepository,
        monthly_health_survey_repo: MonthlyHealthSurveyRepository,
        redis_client: redis.Redis,
        clock: Callable[[], datetime] = _now,
    ) -> None:
        self.repo = repository
        self.health_profile_repo = health_profile_repo
        self.screening_repo = annual_health_screening_repo
        self.survey_repo = monthly_health_survey_repo
        self.redis = redis_client
        self.clock = clock

    async def request_prediction(self, user_id: UUID, data: DiseasePredictionCreateRequest) -> DiseasePrediction:
        profile = await self.health_profile_repo.get_health_profile_by_user_id(user_id)
        if profile is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Health Profile Not Found.")
        screening = await self._get_screening(user_id, data.annual_health_screening_id)
        survey = await self._get_survey(user_id, data.monthly_health_survey_id)

        now = self.clock()
        # 결과 보관 시간 안의 PENDING 요청이 있으면 중복 요청으로 봅니다. 그보다 오래된 요청은 만료 대상입니다.
        if await self.repo.exists_in_progress_since(user_id, now - timedelta(seconds=RESULT_TTL_SECONDS)):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Disease prediction is already in progress."
            )

        try:
            payload = build_prediction_payload(profile, screening, survey, today=now.date())
        except PredictionInputError as error:
            raise RequestValidationError(
                [
                    {"type": "value_error", "loc": tuple(item.field.split(".")), "msg": item.reason}
                    for item in error.errors
                ]
            ) from None

        prediction = await self.repo.create_pending(user_id, payload, screening.id, survey.id)
        fields = build_request_fields(str(prediction.id), payload, now)
        try:
            await self.redis.xadd(PREDICTION_REQUEST_STREAM, fields, maxlen=REQUEST_STREAM_MAXLEN, approximate=True)  # type: ignore[arg-type]
        except RedisError:
            logger.exception("Failed to publish disease prediction %s", prediction.id)
            await self.repo.mark_failed(prediction.id, PredictionErrorCode.PUBLISH_FAILED, [], self.clock())
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Disease prediction service is temporarily unavailable.",
            ) from None

        logger.info("Published disease prediction %s", prediction.id)
        return prediction

    async def get_owned_prediction(self, user_id: UUID, prediction_id: UUID) -> DiseasePrediction:
        prediction = await self.repo.get_by_id(user_id, prediction_id)
        if prediction is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Disease Prediction Not Found.")
        return prediction

    async def get_prediction(self, user_id: UUID, prediction_id: UUID) -> DiseasePrediction:
        """확정 전이면 결과 Stream을 확인해 상태를 반영한 뒤 반환합니다 (SSE를 받지 못한 경우 대비)."""
        prediction = await self.get_owned_prediction(user_id, prediction_id)
        if prediction.status in DiseasePredictionStatus.in_progress() and await self._sync_from_result_stream(
            prediction
        ):
            prediction = await self.get_owned_prediction(user_id, prediction_id)
        return prediction

    async def get_prediction_list(self, user_id: UUID) -> list[DiseasePrediction]:
        return await self.repo.get_list_by_user_id(user_id)

    async def stream_events(
        self,
        user_id: UUID,
        prediction: DiseasePrediction,
        is_disconnected: Callable[[], Awaitable[bool]],
    ) -> AsyncIterator[str]:
        """
        진행 상태를 보내고, 결과가 확정되면 최종 이벤트 1건을 보낸 뒤 끝냅니다.
        이미 확정된 예측이면 최종 이벤트만 보냅니다.
        """
        try:
            if prediction.status in DiseasePredictionStatus.in_progress():
                async for chunk in self._follow_result_stream(prediction, is_disconnected):
                    if chunk is None:
                        break
                    yield chunk
                else:
                    # 결과가 확정되기 전에 연결이 끊기거나 대기 시간이 끝났습니다.
                    return
                prediction = await self.get_owned_prediction(user_id, prediction.id)
            yield self._final_event(prediction)
        except RedisError:
            logger.exception("Redis error while streaming disease prediction %s", prediction.id)
            yield format_sse(SSE_EVENT_ERROR, _error_json(prediction, "SERVICE_UNAVAILABLE"))
        except Exception:
            logger.exception("Unexpected error while streaming disease prediction %s", prediction.id)
            yield format_sse(SSE_EVENT_ERROR, _error_json(prediction, "INTERNAL_SERVER_ERROR"))

    async def _follow_result_stream(
        self,
        prediction: DiseasePrediction,
        is_disconnected: Callable[[], Awaitable[bool]],
    ) -> AsyncIterator[str | None]:
        """
        결과 Stream을 따라가며 status·heartbeat·timeout 이벤트를 내보내고, 결과가 확정되면 None을 내보낸 뒤 끝냅니다.

        - 연결하면 현재 상태(PENDING·PROCESSING)를 보내고, PROCESSING으로 바뀌면 다시 보냅니다.
        - heartbeat 간격으로 나눠 기다리며, 그 사이마다 heartbeat를 보내고 연결 종료를 확인합니다.
        - 처음(0)부터 읽어 대기 시작 전에 남은 항목도 받고, 이후에는 마지막으로 읽은 항목 다음부터 읽습니다.
        """
        sent_status = prediction.status
        yield format_sse(SSE_EVENT_STATUS, _status_json(prediction.id, sent_status))

        loop = asyncio.get_running_loop()
        deadline = loop.time() + settings.PREDICTION_SSE_TIMEOUT_SECONDS
        key = result_stream_key(str(prediction.id))
        last_id = "0"
        while not await is_disconnected():
            remaining = deadline - loop.time()
            if remaining <= 0:
                if await self._expire_if_needed(prediction):
                    yield None
                else:
                    yield format_sse(SSE_EVENT_TIMEOUT, _status_json(prediction.id, sent_status))
                return
            block_ms = max(1, int(min(settings.PREDICTION_SSE_HEARTBEAT_SECONDS, remaining) * 1000))
            entries = await self.redis.xread({key: last_id}, count=10, block=block_ms)
            if not entries:
                if await self._expire_if_needed(prediction):
                    yield None
                    return
                yield SSE_HEARTBEAT
                continue
            for message_id, fields in entries[0][1]:
                last_id = message_id
                state = await self._apply_result_entry(prediction.id, fields)
                if state is not DiseasePredictionStatus.PROCESSING:
                    yield None
                    return
                if sent_status is not state:
                    sent_status = state
                    yield format_sse(SSE_EVENT_STATUS, _status_json(prediction.id, sent_status))

    async def _sync_from_result_stream(self, prediction: DiseasePrediction) -> bool:
        """
        결과 Stream의 마지막 항목을 반영합니다. 상태가 바뀌었을 수 있으면 True를 반환합니다.
        Redis 장애 시에는 상태를 그대로 둡니다.
        """
        try:
            entries = await self.redis.xrevrange(result_stream_key(str(prediction.id)), count=1)
        except RedisError:
            logger.warning("Redis error while checking disease prediction %s", prediction.id)
            return False
        if entries:
            state = await self._apply_result_entry(prediction.id, entries[0][1])
            return state is not prediction.status
        return await self._expire_if_needed(prediction)

    async def _expire_if_needed(self, prediction: DiseasePrediction) -> bool:
        """결과 보관 시간이 지나도 확정되지 않은 예측은 결과를 받을 수 없으므로 실패로 확정합니다."""
        now = self.clock()
        return await self.repo.mark_failed(
            prediction.id,
            PredictionErrorCode.RESULT_EXPIRED,
            [],
            now,
            created_before=now - timedelta(seconds=RESULT_TTL_SECONDS),
        )

    async def _apply_result_entry(self, prediction_id: UUID, fields: Mapping[str, str]) -> DiseasePredictionStatus:
        """
        결과 Stream 항목 1건을 DB에 반영하고, 그 항목이 나타내는 상태를 반환합니다.
        처리 시작 항목이면 PROCESSING, 최종 결과면 COMPLETED·FAILED입니다.
        """
        now = self.clock()
        try:
            message = parse_result_fields(fields)
        except PredictionResultParseError as error:
            logger.error("Disease prediction %s has an invalid result: %s", prediction_id, error)
            await self.repo.mark_failed(prediction_id, PredictionErrorCode.INVALID_RESULT, [], now)
            return DiseasePredictionStatus.FAILED
        if message.task_id != str(prediction_id):
            logger.error("Disease prediction %s received a result for another task", prediction_id)
            await self.repo.mark_failed(prediction_id, PredictionErrorCode.INVALID_RESULT, [], now)
            return DiseasePredictionStatus.FAILED

        if isinstance(message, PredictionProcessingMessage):
            if await self.repo.mark_processing(prediction_id, message.started_at):
                logger.info("Disease prediction %s is processing", prediction_id)
            return DiseasePredictionStatus.PROCESSING

        if message.status is PredictionTaskStatus.SUCCEEDED:
            assert message.result is not None
            saved = await self.repo.save_completed(
                prediction_id, [_result_record(result) for result in message.result.values()], now
            )
            state = DiseasePredictionStatus.COMPLETED
        else:
            assert message.error_code is not None
            errors = (
                [error.model_dump() for error in message.errors]
                if message.error_code in USER_VISIBLE_ERROR_CODES
                else []
            )
            saved = await self.repo.mark_failed(prediction_id, message.error_code, errors, now)
            if saved:
                logger.warning("Disease prediction %s failed: %s", prediction_id, message.error_code)
            state = DiseasePredictionStatus.FAILED
        if saved:
            logger.info("Disease prediction %s finalized as %s", prediction_id, state)
        return state

    def _final_event(self, prediction: DiseasePrediction) -> str:
        data = DiseasePredictionResponse.from_model(prediction).model_dump_json()
        if prediction.status is DiseasePredictionStatus.COMPLETED:
            return format_sse(SSE_EVENT_RESULT, data)
        return format_sse(SSE_EVENT_FAILED, data)

    async def _get_screening(self, user_id: UUID, screening_id: UUID | None) -> AnnualHealthScreening:
        if screening_id is None:
            screening = await self.screening_repo.get_latest_by_user_id(user_id)
        else:
            screening = await self.screening_repo.get_by_id(user_id, screening_id)
        if screening is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Annual Health Screening Not Found.")
        return screening

    async def _get_survey(self, user_id: UUID, survey_id: UUID | None) -> MonthlyHealthSurvey:
        if survey_id is None:
            survey = await self.survey_repo.get_latest_by_user_id(user_id)
        else:
            survey = await self.survey_repo.get_by_id(user_id, survey_id)
        if survey is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Monthly Health Survey Not Found.")
        return survey


def _quantize(value: float, places: int) -> Decimal:
    return Decimal(str(value)).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def _result_record(result: DiseaseRiskMessage) -> dict[str, Any]:
    """Worker 결과 1건을 DiseasePredictionResult 생성 인자로 바꿉니다."""
    return {
        "model_type": result.model_type,
        "model_version": result.model_version,
        "risk_probability": _quantize(result.risk_probability, 5),
        "risk_score": _quantize(result.risk_probability * 100, 2),
        "risk_level": result.risk_level,
        "threshold_moderate": _quantize(result.risk_thresholds.moderate, 5),
        "threshold_high": _quantize(result.risk_thresholds.high, 5),
        "shap_output_space": result.shap_output_space,
        "base_value": _quantize(result.shap_base_value, 6),
        "shap_results": [factor.model_dump(mode="json") for factor in result.risk_factors],
        "out_of_training_range": list(result.out_of_training_range),
    }


def _status_json(prediction_id: UUID, status: DiseasePredictionStatus) -> str:
    return json.dumps(
        {"id": str(prediction_id), "status": str(status), "status_label": status.label}, ensure_ascii=False
    )


def _error_json(prediction: DiseasePrediction, code: str) -> str:
    return json.dumps({"id": str(prediction.id), "code": code})


def get_disease_prediction_service(
    repository: DiseasePredictionRepository = Depends(DiseasePredictionRepository),
    health_profile_repo: HealthProfileRepository = Depends(HealthProfileRepository),
    annual_health_screening_repo: AnnualHealthScreeningRepository = Depends(AnnualHealthScreeningRepository),
    monthly_health_survey_repo: MonthlyHealthSurveyRepository = Depends(MonthlyHealthSurveyRepository),
    redis_client: redis.Redis = Depends(get_redis),
) -> DiseasePredictionService:
    return DiseasePredictionService(
        repository=repository,
        health_profile_repo=health_profile_repo,
        annual_health_screening_repo=annual_health_screening_repo,
        monthly_health_survey_repo=monthly_health_survey_repo,
        redis_client=redis_client,
    )
