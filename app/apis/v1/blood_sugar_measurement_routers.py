from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path
from starlette import status

from app.dependencies.security import get_request_user
from app.models.user_models import User
from app.schemas.blood_sugar_measurements import BloodSugarMeasurementCreateRequest, BloodSugarMeasurementResponse
from app.services.blood_sugar_measurements import BloodSugarMeasurementService, get_blood_sugar_measurement_service

blood_sugar_measurement_router = APIRouter(prefix="/blood-sugar-measurements", tags=["blood-sugar-measurement"])


@blood_sugar_measurement_router.post(
    "", response_model=BloodSugarMeasurementResponse, status_code=status.HTTP_201_CREATED
)
async def create_blood_sugar_measurement(
    request_data: BloodSugarMeasurementCreateRequest,
    request_user: User = Depends(get_request_user),
    blood_sugar_measurement_service: BloodSugarMeasurementService = Depends(get_blood_sugar_measurement_service),
) -> BloodSugarMeasurementResponse:
    created = await blood_sugar_measurement_service.create_blood_sugar_measurement(
        user_id=request_user.id, data=request_data
    )
    return BloodSugarMeasurementResponse.model_validate(created)


@blood_sugar_measurement_router.get(
    path="", response_model=list[BloodSugarMeasurementResponse], status_code=status.HTTP_200_OK
)
async def get_blood_sugar_measurements(
    request_user: User = Depends(get_request_user),
    blood_sugar_measurement_service: BloodSugarMeasurementService = Depends(get_blood_sugar_measurement_service),
) -> list[BloodSugarMeasurementResponse]:
    measurements = await blood_sugar_measurement_service.get_blood_sugar_measurements(user_id=request_user.id)
    return [BloodSugarMeasurementResponse.model_validate(measurement) for measurement in measurements]


@blood_sugar_measurement_router.get(
    "/{measurement_id}", response_model=BloodSugarMeasurementResponse, status_code=status.HTTP_200_OK
)
async def get_blood_sugar_measurement(
    measurement_id: Annotated[UUID, Path(title="ID of the blood sugar measurement to get")],
    request_user: User = Depends(get_request_user),
    blood_sugar_measurement_service: BloodSugarMeasurementService = Depends(get_blood_sugar_measurement_service),
) -> BloodSugarMeasurementResponse:
    measurement = await blood_sugar_measurement_service.get_blood_sugar_measurement_by_id(
        user_id=request_user.id, measurement_id=measurement_id
    )
    return BloodSugarMeasurementResponse.model_validate(measurement)
