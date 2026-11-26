"""
수락한 챌린지의 회차 계산과 완료·실패 판정입니다. DB·네트워크에 의존하지 않는 순수 함수입니다.

회차 규칙 (수락일 기준, 설정 시간대(한국 시간)의 날짜로 계산)
    - 일간(DAILY) 1일, 주간(WEEKLY) 7일, 월간(MONTHLY) 30일이 1회차입니다.
      기간은 목표 회차 × 회차 길이입니다. 예) 14회차 일간 챌린지는 수락일부터 14일
    - 횟수형(COUNT_BASED)은 기록할 때마다 1회차입니다. 하루 최대 1회, 수락 후 count_based_days일 안에 채웁니다.

기록 규칙
    - 현재 회차만 기록할 수 있습니다. 기록하지 않고 지나간 회차는 미달성으로 봅니다.
    - 회차당 1건입니다 (personal_challenge_histories의 challenge·current_round 유니크 제약).

판정 규칙
    - 주기형: 기간이 끝나거나 마지막 회차까지 기록하면 판정합니다.
      성공 회차가 목표의 success_rate 이상이면 완료, 미만이면 실패입니다.
      남은 회차를 모두 성공해도 기준에 못 미치면 기간 중이라도 실패로 판정합니다.
    - 횟수형: 성공 횟수가 목표에 닿으면 바로 완료합니다.
      기한이 지나거나, 남은 날을 모두 채워도 목표에 못 미치면 실패입니다.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta

from app.core.enums import ChallengeStatus, ChallengeType

# 주기형 챌린지의 1회차 길이(일)
PERIOD_DAYS: dict[ChallengeType, int] = {
    ChallengeType.DAILY: 1,
    ChallengeType.WEEKLY: 7,
    ChallengeType.MONTHLY: 30,
}


@dataclass(frozen=True)
class HistoryEntry:
    current_round: int
    is_success: bool
    recorded_on: date  # 기록한 날짜 (설정 시간대 기준)


@dataclass(frozen=True)
class ChallengeProgress:
    total_rounds: int
    required_success: int  # 완료에 필요한 성공 회차 수
    success_count: int
    recorded_count: int
    ends_on: date  # 기록할 수 있는 마지막 날짜
    current_round: int | None  # 지금 기록할 수 있는 회차. 기록할 수 없으면 None
    can_record: bool
    outcome: ChallengeStatus | None  # 판정이 끝났으면 COMPLETED 또는 FAILED, 진행 중이면 None


def required_success_count(challenge_type: ChallengeType, total_rounds: int, success_rate: float) -> int:
    """완료에 필요한 성공 회차 수입니다. 횟수형은 목표 횟수 전부, 주기형은 목표 회차 × 비율(올림)입니다."""
    if challenge_type is ChallengeType.COUNT_BASED:
        return total_rounds
    # 0.7 × 10 = 7.000000000000001처럼 부동소수점 오차로 1회 더 요구하지 않도록 반올림한 뒤 올림합니다.
    required = math.ceil(round(total_rounds * success_rate, 6))
    return min(max(required, 1), total_rounds)


def calculate_progress(
    challenge_type: ChallengeType,
    total_rounds: int,
    joined_on: date,
    today: date,
    histories: Sequence[HistoryEntry],
    success_rate: float,
    count_based_days: int,
) -> ChallengeProgress:
    if total_rounds < 1:
        raise ValueError("total_rounds must be at least 1.")
    if challenge_type is ChallengeType.COUNT_BASED:
        return _count_based(total_rounds, joined_on, today, histories, count_based_days)
    return _periodic(challenge_type, total_rounds, joined_on, today, histories, success_rate)


def _periodic(
    challenge_type: ChallengeType,
    total_rounds: int,
    joined_on: date,
    today: date,
    histories: Sequence[HistoryEntry],
    success_rate: float,
) -> ChallengeProgress:
    period = PERIOD_DAYS[challenge_type]
    day_index = max((today - joined_on).days, 0)
    round_now = day_index // period + 1
    ends_on = joined_on + timedelta(days=total_rounds * period - 1)

    in_range = [history for history in histories if 1 <= history.current_round <= total_rounds]
    recorded_rounds = {history.current_round for history in in_range}
    success_count = sum(1 for history in in_range if history.is_success)
    required = required_success_count(challenge_type, total_rounds, success_rate)

    period_over = round_now > total_rounds
    # 아직 기록할 기회가 남은 회차: 현재 회차부터 마지막 회차 중 기록하지 않은 것
    remaining = 0 if period_over else sum(1 for r in range(round_now, total_rounds + 1) if r not in recorded_rounds)

    outcome: ChallengeStatus | None = None
    if remaining == 0:
        outcome = ChallengeStatus.COMPLETED if success_count >= required else ChallengeStatus.FAILED
    elif success_count + remaining < required:
        outcome = ChallengeStatus.FAILED

    can_record = outcome is None and round_now not in recorded_rounds
    return ChallengeProgress(
        total_rounds=total_rounds,
        required_success=required,
        success_count=success_count,
        recorded_count=len(recorded_rounds),
        ends_on=ends_on,
        current_round=round_now if can_record else None,
        can_record=can_record,
        outcome=outcome,
    )


def _count_based(
    total_rounds: int,
    joined_on: date,
    today: date,
    histories: Sequence[HistoryEntry],
    count_based_days: int,
) -> ChallengeProgress:
    ends_on = joined_on + timedelta(days=count_based_days - 1)
    success_count = sum(1 for history in histories if history.is_success)
    recorded_today = any(history.recorded_on == today for history in histories)
    deadline_over = today > ends_on
    # 남은 기록 기회(일): 오늘을 포함해 마지막 날까지, 오늘 이미 기록했으면 오늘은 제외
    remaining_days = 0 if deadline_over else (ends_on - today).days + 1 - (1 if recorded_today else 0)

    outcome: ChallengeStatus | None = None
    if success_count >= total_rounds:
        outcome = ChallengeStatus.COMPLETED
    elif success_count + remaining_days < total_rounds:
        outcome = ChallengeStatus.FAILED

    can_record = outcome is None and not recorded_today
    next_round = max((history.current_round for history in histories), default=0) + 1
    return ChallengeProgress(
        total_rounds=total_rounds,
        required_success=total_rounds,
        success_count=success_count,
        recorded_count=len(histories),
        ends_on=ends_on,
        current_round=next_round if can_record else None,
        can_record=can_record,
        outcome=outcome,
    )
