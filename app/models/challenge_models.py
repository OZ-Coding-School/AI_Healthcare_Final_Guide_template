from typing import TYPE_CHECKING

from tortoise import fields
from uuid6 import uuid7

from app.core.enums import ChallengeStatus, ChallengeType
from app.models.base import TimestampModel

if TYPE_CHECKING:
    from .user_models import User


class PersonalChallenge(TimestampModel):
    id = fields.BigIntField(primary_key=True, auto_increment=True)
    user: fields.ForeignKeyRelation["User"] = fields.ForeignKeyField("models.User", related_name="personal_challenges")
    title = fields.CharField(max_length=30, description="개인 챌린지 제목")
    description = fields.TextField(max_length=1000, description="개인 챌린지 설명")
    challenge_type = fields.CharEnumField(ChallengeType, description="챌린지 유형(일간, 주간, 월간, 횟수 기반)")
    expected_effect = fields.TextField(max_length=300, description="챌린지 수행 후 기대 효과")
    status = fields.CharEnumField(
        ChallengeStatus, default=ChallengeStatus.PENDING, description="챌린지 상태(진행중, 완료)"
    )
    expired_at = fields.DatetimeField(description="챌린지 수락 만료 시간")
    joined_at = fields.DatetimeField(null=True, description="챌린지 참여(수락) 시간")
    completed_at = fields.DatetimeField(null=True, description="챌린지 완료 시간")

    class Meta:
        table = "personal_challenges"


class PersonalChallengeHistory(TimestampModel):
    id = fields.BigIntField(primary_key=True, auto_increment=True)
    challenge: fields.ForeignKeyRelation["PersonalChallenge"] = fields.ForeignKeyField(
        "models.PersonalChallenge", related_name="histories"
    )
    current_round = fields.SmallIntField(description="현재 진행 회차")
    is_success = fields.BooleanField(description="회차 챌린지 성공 여부")
    memo = fields.TextField(
        max_length=300, null=True, description="챌린지 수행 관련 메모(어떤 것을 했는지, 계획, 다짐, 느낀점 등)"
    )

    class Meta:
        table = "personal_challenge_histories"
        unique_together = ("challenge", "current_round")


class ChallengeProofFile(TimestampModel):
    id = fields.UUIDField(primary_key=True, default=uuid7)
    challenge_history: fields.ForeignKeyRelation["PersonalChallengeHistory"] = fields.ForeignKeyField(
        "models.PersonalChallengeHistory", related_name="proof_files"
    )
    file_name = fields.CharField(max_length=100, description="파일 이름")
    file_ext = fields.CharField(max_length=10, description="파일 확장자")
    file_url = fields.CharField(max_length=512, description="파일 URL")

    class Meta:
        table = "challenge_proof_files"


class ChallengeReport(TimestampModel):
    id = fields.UUIDField(primary_key=True, default=uuid7)
    user: fields.ForeignKeyRelation["User"] = fields.ForeignKeyField("models.User", related_name="challenge_reports")
    using_model_name = fields.CharField(max_length=100, description="리포트 생성시 사용한 LLM 모델 이름")
    content = fields.TextField(max_length=3000, description="챌린지 리포트 내용")

    class Meta:
        table = "challenge_reports"
