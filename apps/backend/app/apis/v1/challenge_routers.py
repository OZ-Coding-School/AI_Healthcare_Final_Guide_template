from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query
from starlette import status

from app.core.enums import ChallengeStatus
from app.dependencies.security import get_request_user
from app.models.user_models import User
from app.schemas.challenges import (
    ChallengeHistoryCreateRequest,
    ChallengeRecommendationResponse,
    PersonalChallengeDetailResponse,
    PersonalChallengeResponse,
)
from app.services.challenge_participations import (
    ChallengeParticipationService,
    get_challenge_participation_service,
)
from app.services.challenge_recommendations import (
    ChallengeRecommendationService,
    get_challenge_recommendation_service,
)

challenge_router = APIRouter(tags=["challenge"])


@challenge_router.get(
    path="/disease-predictions/{prediction_id}/challenges",
    response_model=ChallengeRecommendationResponse,
    status_code=status.HTTP_200_OK,
    summary="예측 결과 기반 LLM 챌린지 추천 조회",
)
async def get_challenge_recommendation(
    prediction_id: Annotated[UUID, Path(description="Disease prediction ID")],
    request_user: User = Depends(get_request_user),
    service: ChallengeRecommendationService = Depends(get_challenge_recommendation_service),
) -> ChallengeRecommendationResponse:
    return await service.get_recommendation(request_user.id, prediction_id)


@challenge_router.post(
    path="/disease-predictions/{prediction_id}/challenges/retry",
    response_model=ChallengeRecommendationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="실패한 LLM 챌린지 추천 다시 생성",
)
async def retry_challenge_recommendation(
    prediction_id: Annotated[UUID, Path(description="Disease prediction ID")],
    request_user: User = Depends(get_request_user),
    service: ChallengeRecommendationService = Depends(get_challenge_recommendation_service),
) -> ChallengeRecommendationResponse:
    return await service.retry(request_user.id, prediction_id)


@challenge_router.get(
    path="/challenges",
    response_model=list[PersonalChallengeResponse],
    status_code=status.HTTP_200_OK,
    summary="내 챌린지 목록 조회",
)
async def get_challenge_list(
    challenge_status: Annotated[ChallengeStatus | None, Query(alias="status", description="챌린지 상태 필터")] = None,
    request_user: User = Depends(get_request_user),
    service: ChallengeRecommendationService = Depends(get_challenge_recommendation_service),
) -> list[PersonalChallengeResponse]:
    return await service.get_challenge_list(request_user.id, challenge_status)


@challenge_router.get(
    path="/challenges/{challenge_id}",
    response_model=PersonalChallengeDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="내 챌린지 상세 조회 (진행 상황·회차 기록 포함)",
)
async def get_challenge_detail(
    challenge_id: Annotated[int, Path(gt=0, description="Personal challenge ID")],
    request_user: User = Depends(get_request_user),
    service: ChallengeParticipationService = Depends(get_challenge_participation_service),
) -> PersonalChallengeDetailResponse:
    return await service.get_detail(request_user.id, challenge_id)


@challenge_router.post(
    path="/challenges/{challenge_id}/accept",
    response_model=PersonalChallengeDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="추천 챌린지 수락 (진행 시작)",
)
async def accept_challenge(
    challenge_id: Annotated[int, Path(gt=0, description="Personal challenge ID")],
    request_user: User = Depends(get_request_user),
    service: ChallengeParticipationService = Depends(get_challenge_participation_service),
) -> PersonalChallengeDetailResponse:
    return await service.accept(request_user.id, challenge_id)


@challenge_router.post(
    path="/challenges/{challenge_id}/histories",
    response_model=PersonalChallengeDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="현재 회차 수행 기록",
)
async def record_challenge_history(
    challenge_id: Annotated[int, Path(gt=0, description="Personal challenge ID")],
    request: ChallengeHistoryCreateRequest,
    request_user: User = Depends(get_request_user),
    service: ChallengeParticipationService = Depends(get_challenge_participation_service),
) -> PersonalChallengeDetailResponse:
    return await service.record(request_user.id, challenge_id, request)
