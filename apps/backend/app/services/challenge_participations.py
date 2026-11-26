"""
챌린지 수락·회차 기록·완료 판정을 담당합니다.

흐름
    1. 수락: 수락 기한 안의 PENDING 챌린지를 IN_PROGRESS로 바꾸고 joined_at을 기록합니다.
    2. 회차 기록: 현재 회차만, 회차당 1건 기록합니다. 기록한 뒤 완료·실패를 판정합니다.
    3. 판정: 별도 스케줄러 없이 기록·조회할 때 합니다 (ChallengeProgressTracker).
       기간이 끝난 챌린지는 다음 조회 때 완료·실패로 바뀝니다.
회차·판정 규칙은 app.services.challenge_progress를 따릅니다.

챌린지가 바뀌면 목록 캐시와, 그 챌린지가 속한 예측의 추천 조회 캐시(챌린지 상태를 담고 있음)를 무효화합니다.
"""

from collections.abc import Callable, Iterable, Sequence
from dataclasses import replace
from datetime import date, datetime
from uuid import UUID

from fastapi import Depends, HTTPException
from starlette import status
from tortoise.exceptions import IntegrityError

from app.core import settings
from app.core.enums import ChallengeStatus
from app.models.challenge_models import PersonalChallenge
from app.repositories.challenge_cache_repository import ChallengeCacheRepository
from app.repositories.challenge_repository import ChallengeRepository
from app.schemas.challenges import ChallengeHistoryCreateRequest, PersonalChallengeDetailResponse
from app.services.challenge_progress import ChallengeProgress, HistoryEntry, calculate_progress

# 진행률을 계산하는 상태: 수락한 뒤의 상태들
TRACKED_STATUSES = {ChallengeStatus.IN_PROGRESS, ChallengeStatus.COMPLETED, ChallengeStatus.FAILED}


def _now() -> datetime:
    return datetime.now(settings.TIMEZONE)


def local_date(value: datetime) -> date:
    """회차는 설정 시간대(한국 시간)의 날짜로 계산합니다."""
    return value.astimezone(settings.TIMEZONE).date()


class ChallengeProgressTracker:
    """챌린지별 진행 상황을 계산하고, 판정이 끝난 진행 중 챌린지를 완료·실패로 저장합니다."""

    def __init__(self, repository: ChallengeRepository, cache: ChallengeCacheRepository) -> None:
        self.repo = repository
        self.cache = cache

    def progress_of(self, challenge: PersonalChallenge, now: datetime) -> ChallengeProgress | None:
        """수락하지 않았거나 목표 회차가 없는 챌린지는 None입니다. histories가 미리 조회돼 있어야 합니다."""
        if challenge.status not in TRACKED_STATUSES or challenge.joined_at is None or not challenge.total_rounds:
            return None
        finished = challenge.status is not ChallengeStatus.IN_PROGRESS
        # 판정이 끝난 챌린지는 끝난 날짜 기준으로 계산합니다 (이후 날짜가 지나도 숫자가 바뀌지 않도록).
        today = local_date(challenge.completed_at or now) if finished else local_date(now)
        entries = [
            HistoryEntry(history.current_round, history.is_success, local_date(history.created_at))
            for history in challenge.histories
        ]
        progress = calculate_progress(
            challenge.challenge_type,
            challenge.total_rounds,
            local_date(challenge.joined_at),
            today,
            entries,
            settings.CHALLENGE_SUCCESS_RATE,
            settings.CHALLENGE_COUNT_BASED_DAYS,
        )
        if finished:
            progress = replace(progress, can_record=False, current_round=None)
        return progress

    async def refresh(self, challenges: Sequence[PersonalChallenge], now: datetime) -> dict[int, ChallengeProgress]:
        """
        진행 중 챌린지 중 판정이 끝난 것을 완료·실패로 저장하고, 챌린지 id별 진행 상황을 반환합니다.
        상태가 바뀐 챌린지가 있으면 캐시를 무효화합니다.
        """
        progresses: dict[int, ChallengeProgress] = {}
        changed: list[PersonalChallenge] = []
        for challenge in challenges:
            progress = self.progress_of(challenge, now)
            if progress is None:
                continue
            if challenge.status is ChallengeStatus.IN_PROGRESS and progress.outcome is not None:
                if await self.repo.finish(challenge.id, progress.outcome, now):
                    challenge.status = progress.outcome
                    challenge.completed_at = now
                    changed.append(challenge)
                else:
                    # 다른 요청이 먼저 판정했습니다. 저장된 상태를 다시 읽습니다.
                    await challenge.refresh_from_db(fields=["status", "completed_at"])
                progress = replace(progress, can_record=False, current_round=None)
            progresses[challenge.id] = progress
        if changed:
            await self.invalidate(
                changed[0].user_id,  # type: ignore[attr-defined]
                (item.prediction_id for item in changed),  # type: ignore[attr-defined]
            )
        return progresses

    async def invalidate(self, user_id: UUID, prediction_ids: Iterable[UUID | None]) -> None:
        await self.cache.invalidate_list(user_id)
        for prediction_id in {item for item in prediction_ids if item is not None}:
            await self.cache.delete_recommendation(user_id, prediction_id)


class ChallengeParticipationService:
    def __init__(
        self,
        repository: ChallengeRepository,
        cache: ChallengeCacheRepository,
        clock: Callable[[], datetime] = _now,
    ) -> None:
        self.repo = repository
        self.tracker = ChallengeProgressTracker(repository, cache)
        self.clock = clock

    async def get_detail(self, user_id: UUID, challenge_id: int) -> PersonalChallengeDetailResponse:
        challenge = await self._get(user_id, challenge_id)
        progresses = await self.tracker.refresh([challenge], self.clock())
        return PersonalChallengeDetailResponse.from_detail(
            challenge, list(challenge.histories), progresses.get(challenge.id)
        )

    async def accept(self, user_id: UUID, challenge_id: int) -> PersonalChallengeDetailResponse:
        now = self.clock()
        challenge = await self._get(user_id, challenge_id)
        if challenge.status is not ChallengeStatus.PENDING:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only pending challenges can be accepted.")
        if challenge.expired_at <= now:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="The challenge acceptance period has expired."
            )
        if not challenge.total_rounds:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The challenge has no target rounds.")
        if not await self.repo.accept(user_id, challenge_id, now):
            # 조회와 수락 사이에 다른 요청이 먼저 수락했습니다.
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only pending challenges can be accepted.")

        await self.tracker.invalidate(user_id, [challenge.prediction_id])  # type: ignore[attr-defined]
        challenge = await self._get(user_id, challenge_id)
        return PersonalChallengeDetailResponse.from_detail(
            challenge, list(challenge.histories), self.tracker.progress_of(challenge, now)
        )

    async def record(
        self, user_id: UUID, challenge_id: int, request: ChallengeHistoryCreateRequest
    ) -> PersonalChallengeDetailResponse:
        now = self.clock()
        challenge = await self._get(user_id, challenge_id)
        if challenge.status is not ChallengeStatus.IN_PROGRESS:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Only challenges in progress can be recorded."
            )
        # 기록 전에 판정합니다. 기간이 이미 끝났다면 여기서 완료·실패로 바뀝니다.
        progress = (await self.tracker.refresh([challenge], now)).get(challenge.id)
        if challenge.status is not ChallengeStatus.IN_PROGRESS:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The challenge has already ended.")
        if progress is None or not progress.can_record or progress.current_round is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The current round is already recorded.")

        try:
            await self.repo.create_history(challenge.id, progress.current_round, request.is_success, request.memo)
        except IntegrityError:
            # 같은 회차를 동시에 기록한 경우입니다 (challenge·current_round 유니크 제약).
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="The current round is already recorded."
            ) from None

        challenge = await self._get(user_id, challenge_id)
        progresses = await self.tracker.refresh([challenge], now)
        # 상태가 그대로여도 진행률이 바뀌었으므로 목록 캐시를 무효화합니다.
        await self.tracker.invalidate(user_id, [challenge.prediction_id])  # type: ignore[attr-defined]
        return PersonalChallengeDetailResponse.from_detail(
            challenge, list(challenge.histories), progresses.get(challenge.id)
        )

    async def _get(self, user_id: UUID, challenge_id: int) -> PersonalChallenge:
        challenge = await self.repo.get_by_id_for_user(user_id, challenge_id)
        if challenge is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Challenge Not Found.")
        return challenge


def get_challenge_participation_service(
    repository: ChallengeRepository = Depends(ChallengeRepository),
    cache: ChallengeCacheRepository = Depends(ChallengeCacheRepository),
) -> ChallengeParticipationService:
    return ChallengeParticipationService(repository=repository, cache=cache)
