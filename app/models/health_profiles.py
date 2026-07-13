from collections.abc import Iterable
from datetime import datetime
from typing import TYPE_CHECKING

from tortoise import BaseDBAsyncClient, fields
from uuid6 import uuid7

from ..core.enums import BloodSugarMeasurementType, ExerciseType, Gender, HabitStatus
from ..core.utils.common import get_enum_max_length
from .base import TimestampModel

if TYPE_CHECKING:
    from .user_models import User


class HealthProfile(TimestampModel):
    id = fields.UUIDField(primary_key=True, default=uuid7)
    user: fields.OneToOneRelation["User"] = fields.OneToOneField("models.User", related_name="profile")
    gender = fields.CharEnumField(enum_type=Gender, max_length=get_enum_max_length(Gender))
    birth_date = fields.DateField()
    height = fields.DecimalField(max_digits=4, decimal_places=1)
    weight = fields.DecimalField(max_digits=4, decimal_places=1)
    has_diabetes = fields.BooleanField()
    has_hypertension = fields.BooleanField()

    class Meta:
        table = "health_profiles"


class MonthlyHealthSurvey(TimestampModel):
    id = fields.UUIDField(primary_key=True, default=uuid7)
    user: fields.ForeignKeyRelation["User"] = fields.ForeignKeyField(
        "models.User", related_name="monthly_health_surveys"
    )
    title = fields.CharField(max_length=255, description="월간 건강 조사 제목")
    # 흡연 데이터
    smoking_status = fields.CharEnumField(
        enum_type=HabitStatus,
        max_length=get_enum_max_length(HabitStatus),
    )
    smoking_fr_per_day = fields.SmallIntField(null=True, description="일당 흡연 빈도")
    # 음주 데이터
    drinking_status = fields.CharEnumField(
        enum_type=HabitStatus, max_length=get_enum_max_length(HabitStatus), description="음주상태"
    )
    drinking_fr_per_week = fields.SmallIntField(null=True, description="주당 음주 빈도")
    drinking_amount_per_session = fields.SmallIntField(null=True, description="회당 음주량(잔)")
    # 혈압, 맥박 데이터
    systolic_bp = fields.SmallIntField(description="수축기 혈압(최고 혈압, mmHg)")
    diastolic_bp = fields.SmallIntField(description="이완기 혈압(최저 혈압, mmHg)")
    pulse = fields.SmallIntField(null=True, description="맥박수(분당 횟수)")

    class Meta:
        table = "monthly_health_surveys"

    async def save(
        self,
        using_db: BaseDBAsyncClient | None = None,
        update_fields: Iterable[str] | None = None,
        force_create: bool = False,
        force_update: bool = False,
    ) -> None:
        if self.title is None:
            now = self.created_at or datetime.now()
            self.title = f"{now.strftime('%Y년 %m월')} 건강 설문 조사"

        return await super().save(
            using_db=using_db,
            update_fields=update_fields,
            force_create=force_create,
            force_update=force_update,
        )


class BloodSugarMeasurement(TimestampModel):
    id = fields.UUIDField(primary_key=True, default=uuid7)
    user: fields.ForeignKeyRelation["User"] = fields.ForeignKeyField(
        "models.User", related_name="blood_sugar_measurements"
    )
    measure_type = fields.CharEnumField(
        enum_type=BloodSugarMeasurementType,
        max_length=get_enum_max_length(BloodSugarMeasurementType),
        description="혈당 수치 테스트 유형",
    )
    blood_glucose = fields.SmallIntField(description="혈당 수치(mg/dL)")
    minutes_since_meal = fields.SmallIntField(null=True, description="식후 경과 시간(분)")
    has_exercised = fields.BooleanField(description="운동 여부")
    exercise_type = fields.CharEnumField(
        enum_type=ExerciseType,
        max_length=get_enum_max_length(ExerciseType),
        null=True,
        description="운동 유형",
    )
    exercise_minutes = fields.SmallIntField(null=True, description="운동 시간(분)")
    minutes_since_exercise = fields.SmallIntField(null=True, description="운동 후 경과 시간(분)")
    has_medicated = fields.BooleanField(description="복약 여부")
    medicine_name = fields.CharField(max_length=100, null=True, description="복용한 약물명")
    minutes_since_medication = fields.SmallIntField(null=True, description="복약 후 경과 시간(분)")
    memo = fields.TextField(null=True, max_length=500, description="참고사항(ex. 어떤걸 먹었고, 어떤 운동을 했는지 등)")
    measured_at = fields.DatetimeField(description="측정시간")

    class Meta:
        table = "blood_sugar_measurements"
