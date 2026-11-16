from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core import settings
from app.core.enums import Gender
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

    @model_validator(mode="after")
    def validate_update_fields(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("수정할 항목을 한 개 이상 입력해야 합니다.")
        if any(getattr(self, field_name) is None for field_name in self.model_fields_set):
            raise ValueError("수정 항목은 null일 수 없습니다.")
        return self


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
