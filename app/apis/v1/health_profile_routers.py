from fastapi import APIRouter, Depends
from starlette import status

from app.dependencies.security import get_request_user
from app.models.user_models import User
from app.schemas.health_profiles import HealthProfileCreateRequest, HealthProfileResponse, HealthProfileUpdateRequest
from app.services.health_profiles import HealthProfileService, get_health_profile_service

health_profile_router = APIRouter(prefix="/health-profile", tags=["health-profile"])


@health_profile_router.post("/", status_code=status.HTTP_201_CREATED)
async def create_health_profile(
    request_data: HealthProfileCreateRequest,
    request_user: User = Depends(get_request_user),
    health_profile_service: HealthProfileService = Depends(get_health_profile_service),
) -> None:
    await health_profile_service.create_health_profile(request_user.id, request_data)


@health_profile_router.get("/", response_model=HealthProfileResponse, status_code=status.HTTP_200_OK)
async def get_health_profile(
    request_user: User = Depends(get_request_user),
    health_profile_service: HealthProfileService = Depends(get_health_profile_service),
) -> HealthProfileResponse:
    health_profile = await health_profile_service.get_health_profile_by_user_id(request_user.id)
    return HealthProfileResponse.model_validate(health_profile)


@health_profile_router.patch("/", response_model=HealthProfileResponse, status_code=status.HTTP_200_OK)
async def update_health_profile(
    request_data: HealthProfileUpdateRequest,
    request_user: User = Depends(get_request_user),
    health_profile_service: HealthProfileService = Depends(get_health_profile_service),
) -> HealthProfileResponse:
    health_profile = await health_profile_service.update_health_profile(request_user.id, request_data)
    return HealthProfileResponse.model_validate(health_profile)
