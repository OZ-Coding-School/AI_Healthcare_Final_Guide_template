from datetime import datetime
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.core.enums import WithdrawalReason
from app.core.validators import optional_after_validator, validate_phone_number
from app.schemas.base import BaseSerializerModel


class UserUpdateRequest(BaseModel):
    nickname: Annotated[str | None, Field(None, max_length=10)]
    phone_number: Annotated[
        str | None,
        Field(None, description="Available Format: +8201011112222, 01011112222, 010-1111-2222"),
        optional_after_validator(validate_phone_number),
    ]

    @model_validator(mode="after")
    def validate_update_fields(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("수정할 항목을 한 개 이상 입력해야 합니다.")
        if any(getattr(self, field_name) is None for field_name in self.model_fields_set):
            raise ValueError("수정 항목은 null일 수 없습니다.")
        return self


class UserWithdrawRequest(BaseModel):
    reason: WithdrawalReason
    reason_detail: str | None = None
    feedback: str | None = None


class SendVerificationMailRequest(BaseModel):
    email: Annotated[EmailStr, Field(str, max_length=40)]


class VerifyMailRequest(SendVerificationMailRequest):
    code: Annotated[str, Field(str, max_length=6)]


class UserInfoResponse(BaseSerializerModel):
    id: UUID
    name: str
    nickname: str
    email: str
    phone_number: str
    created_at: datetime
