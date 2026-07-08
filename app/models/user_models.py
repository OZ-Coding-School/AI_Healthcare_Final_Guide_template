from tortoise import fields
from tortoise.fields import OneToOneNullableRelation
from uuid_utils import uuid7

from ..core.enums import WithdrawalReason
from ..core.utils.common import get_enum_max_length
from .base import TimestampModel


class User(TimestampModel):
    id = fields.UUIDField(primary_key=True, default=uuid7)
    email = fields.CharField(max_length=40, unique=True)
    hashed_password = fields.CharField(max_length=255)
    nickname = fields.CharField(max_length=10)
    name = fields.CharField(max_length=20)
    phone_number = fields.CharField(max_length=11, unique=True, description="Available Format: 01011112222")
    is_active = fields.BooleanField(default=True)
    is_admin = fields.BooleanField(default=False)
    last_login = fields.DatetimeField(null=True)

    withdrawal: OneToOneNullableRelation["UserWithdrawal"]

    class Meta:
        table = "users"


class UserWithdrawal(TimestampModel):
    id = fields.UUIDField(primary_key=True, default=uuid7)
    user: fields.OneToOneRelation["User"] | None = fields.OneToOneField(
        "models.User", related_name="withdrawal", null=True
    )
    reason = fields.CharEnumField(enum_type=WithdrawalReason, max_length=get_enum_max_length(WithdrawalReason))
    reason_detail = fields.TextField(max_length=500, null=True)
    feedback = fields.TextField(max_length=500, null=True)

    class Meta:
        table = "user_withdrawals"
