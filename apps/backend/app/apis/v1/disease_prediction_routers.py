from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request
from fastapi.responses import StreamingResponse
from starlette import status

from app.dependencies.security import get_request_user
from app.models.user_models import User
from app.schemas.disease_predictions import (
    DiseasePredictionCreateRequest,
    DiseasePredictionCreateResponse,
    DiseasePredictionListResponse,
    DiseasePredictionResponse,
)
from app.services.disease_predictions import DiseasePredictionService, get_disease_prediction_service

disease_prediction_router = APIRouter(prefix="/disease-predictions", tags=["disease-prediction"])

# SSE는 프록시·브라우저가 버퍼링하거나 캐시하지 않아야 이벤트가 바로 전달됩니다.
SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


@disease_prediction_router.post(
    path="", response_model=DiseasePredictionCreateResponse, status_code=status.HTTP_202_ACCEPTED
)
async def create_disease_prediction(
    request: Request,
    request_data: DiseasePredictionCreateRequest,
    request_user: User = Depends(get_request_user),
    service: DiseasePredictionService = Depends(get_disease_prediction_service),
) -> DiseasePredictionCreateResponse:
    prediction = await service.request_prediction(request_user.id, request_data)
    return DiseasePredictionCreateResponse(
        id=prediction.id,
        status=prediction.status,
        events_url=request.app.url_path_for("stream_disease_prediction_events", prediction_id=str(prediction.id)),
        created_at=prediction.created_at,
    )


@disease_prediction_router.get(
    path="", response_model=list[DiseasePredictionListResponse], status_code=status.HTTP_200_OK
)
async def get_disease_prediction_list(
    request_user: User = Depends(get_request_user),
    service: DiseasePredictionService = Depends(get_disease_prediction_service),
) -> list[DiseasePredictionListResponse]:
    predictions = await service.get_prediction_list(request_user.id)
    return [DiseasePredictionListResponse.from_model(prediction) for prediction in predictions]


@disease_prediction_router.get(
    path="/{prediction_id}", response_model=DiseasePredictionResponse, status_code=status.HTTP_200_OK
)
async def get_disease_prediction(
    prediction_id: Annotated[UUID, Path(description="Disease prediction ID")],
    request_user: User = Depends(get_request_user),
    service: DiseasePredictionService = Depends(get_disease_prediction_service),
) -> DiseasePredictionResponse:
    prediction = await service.get_prediction(request_user.id, prediction_id)
    return DiseasePredictionResponse.from_model(prediction)


@disease_prediction_router.get(
    path="/{prediction_id}/events",
    response_class=StreamingResponse,
    status_code=status.HTTP_200_OK,
    responses={200: {"content": {"text/event-stream": {}}, "description": "예측 결과 SSE (이벤트 1건 후 종료)"}},
)
async def stream_disease_prediction_events(
    request: Request,
    prediction_id: Annotated[UUID, Path(description="Disease prediction ID")],
    request_user: User = Depends(get_request_user),
    service: DiseasePredictionService = Depends(get_disease_prediction_service),
) -> StreamingResponse:
    # 스트림을 시작하기 전에 소유권을 확인해야 404를 정상 응답으로 돌려줄 수 있습니다.
    prediction = await service.get_owned_prediction(request_user.id, prediction_id)
    return StreamingResponse(
        service.stream_events(request_user.id, prediction, request.is_disconnected),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
