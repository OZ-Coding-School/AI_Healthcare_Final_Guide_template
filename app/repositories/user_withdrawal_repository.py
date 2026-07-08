from uuid import UUID

from app.core.enums import WithdrawalReason
from app.models.user_models import UserWithdrawal


class UserWithdrawalRepository:
    async def create_withdrawal(
        self,
        user_id: UUID,
        reason: WithdrawalReason,
        reason_detail: str | None = None,
        feedback: str | None = None,
    ) -> None:
        await UserWithdrawal.create(
            user_id=user_id,
            reason=reason,
            reason_detail=reason_detail,
            feedback=feedback,
        )

    async def delete_withdrawal_by_user_id(self, user_id: UUID) -> None:
        await UserWithdrawal.filter(user_id=user_id).delete()
