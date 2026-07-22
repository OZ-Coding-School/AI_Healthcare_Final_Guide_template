from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

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
