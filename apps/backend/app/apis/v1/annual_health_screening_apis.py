from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path
from starlette import status

from app.dependencies.security import get_request_user
from app.models.user_models import User
from app.schemas.annual_health_screenings import (
    AnnualHealthScreeningCreateRequest,
    AnnualHealthScreeningListResponse,
    AnnualHealthScreeningResponse,
)
from app.services.annual_health_screening import AnnualHealthScreeningService, get_annual_health_screening_service

annual_health_screening_router = APIRouter(prefix="/annual-health-screenings", tags=["annual-health-screening"])


@annual_health_screening_router.post(path="", status_code=status.HTTP_201_CREATED)
async def get_annual_health_screening(
    request_data: AnnualHealthScreeningCreateRequest,
    request_user: User = Depends(get_request_user),
    service: AnnualHealthScreeningService = Depends(get_annual_health_screening_service),
) -> None:
    await service.create_annual_health_screening(request_user.id, request_data)


@annual_health_screening_router.get(
    path="", response_model=list[AnnualHealthScreeningListResponse], status_code=status.HTTP_200_OK
)
async def get_annual_health_screening_list(
    request_user: User = Depends(get_request_user),
    service: AnnualHealthScreeningService = Depends(get_annual_health_screening_service),
) -> list[AnnualHealthScreeningListResponse]:
    screenings = await service.get_list_by_user(request_user.id)
    return [AnnualHealthScreeningListResponse.model_validate(screening) for screening in screenings]


@annual_health_screening_router.get(
    path="/{screening_id}", response_model=AnnualHealthScreeningResponse, status_code=status.HTTP_200_OK
)
async def get_annual_health_screening_by_id(
    screening_id: Annotated[UUID, Path(description="Annual health screening ID")],
    request_user: User = Depends(get_request_user),
    service: AnnualHealthScreeningService = Depends(get_annual_health_screening_service),
) -> AnnualHealthScreeningResponse:
    screening = await service.get_by_id(request_user.id, screening_id)
    return AnnualHealthScreeningResponse.model_validate(screening)


@annual_health_screening_router.delete(path="/{screening_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_annual_health_screening(
    screening_id: Annotated[UUID, Path(description="Annual health screening ID")],
    request_user: User = Depends(get_request_user),
    service: AnnualHealthScreeningService = Depends(get_annual_health_screening_service),
) -> None:
    await service.delete_by_id(request_user.id, screening_id)
