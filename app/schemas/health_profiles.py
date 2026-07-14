from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer, field_validator

from app.core import settings
from app.core.enums import Gender
from app.core.utils.date import normalize_datetime
from app.schemas.base import BaseSerializerModel

Height = Annotated[
    Decimal,
    Field(gt=0, le=300, max_digits=4, decimal_places=1),
]
Weight = Annotated[
    Decimal,
    Field(gt=0, le=500, max_digits=4, decimal_places=1),
]


class HealthProfileCreateRequest(BaseModel):
    gender: Gender
    birth_date: date
    height: Height
    weight: Weight
    has_diabetes: bool
    has_hypertension: bool

    @field_validator("birth_date")
    @classmethod
    def validate_birthdate(cls, v: date) -> date:
        now = datetime.now(tz=settings.TIMEZONE).date()
        if v > now:
            raise ValueError("생년월일은 미래일 수 없습니다.")
        return v


class HealthProfileUpdateRequest(BaseModel):
    height: Height | None = None
    weight: Weight | None = None
    has_diabetes: bool | None = None
    has_hypertension: bool | None = None


class HealthProfileResponse(BaseSerializerModel):
    id: UUID
    gender: Gender
    birth_date: date
    height: Height
    weight: Weight
    has_diabetes: bool
    has_hypertension: bool
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def serialize_datetime_fields(self, value: datetime) -> str:
        return normalize_datetime(value)
